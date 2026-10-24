"""Command-line interface: ``schemaflow generate | build | watch``."""

from __future__ import annotations

import argparse
import sys
import threading
from collections.abc import Callable
from pathlib import Path

from . import __version__
from .config import Job, find_config, jobs_for, load_config, output_name
from .errors import ConfigError, SchemaflowError
from .mapper import Options
from .pipeline import Result, generate_from_path
from .watcher import watch

COMMANDS = ("generate", "build", "watch")


class UsageError(SchemaflowError):
    """Bad command-line arguments (reported like any other error, exit code 2)."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schemaflow",
        description="Generate TypeScript interfaces from JSON Schema files.",
    )
    parser.add_argument("--version", action="version", version=f"schemaflow {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{generate,build,watch}")

    def common(p: argparse.ArgumentParser, source: bool) -> None:
        if source:
            p.add_argument("-i", "--input", metavar="PATH",
                           help="a schema file, or a directory of *.json schemas")
            p.add_argument("-o", "--output", metavar="PATH",
                           help="output file or directory ('-' or omitted: standard output)")
            p.add_argument("--name", help="name of the root type (single file only)")
            p.add_argument("--readonly", action="store_true", help="mark every property readonly")
            p.add_argument("--no-banner", action="store_true",
                           help="omit the 'generated file' header")
        p.add_argument("-q", "--quiet", action="store_true", help="only print warnings and errors")

    generate = sub.add_parser("generate", help="convert one schema (or a directory) to TypeScript")
    common(generate, True)
    generate.add_argument("--check", action="store_true",
                          help="do not write; exit 1 if an output file is missing or stale")
    generate.add_argument("--strict", action="store_true",
                          help="exit 1 if any schema keyword had to be ignored")

    config_help = (
        "config file (default: search upwards for .schemaflowrc, schemaflow.json or "
        "[tool.schemaflow] in pyproject.toml)"
    )
    build = sub.add_parser("build", help="generate everything listed in the config file")
    common(build, False)
    build.add_argument("-c", "--config", metavar="FILE", help=config_help)
    build.add_argument("--check", action="store_true",
                       help="do not write; exit 1 if an output file is missing or stale")
    build.add_argument("--strict", action="store_true",
                       help="exit 1 if any schema keyword had to be ignored")

    watch_cmd = sub.add_parser("watch", help="regenerate whenever a schema is saved")
    common(watch_cmd, True)
    watch_cmd.add_argument("-c", "--config", metavar="FILE", help=config_help)
    watch_cmd.add_argument("--interval", type=float, default=0.5, metavar="SECONDS",
                           help="how often to look for changes (default 0.5)")
    watch_cmd.add_argument("--once", action="store_true",
                           help="build once and exit instead of waiting for changes")
    return parser


# -- job planning --------------------------------------------------------------------------


def plan(args: argparse.Namespace) -> tuple[Callable[[], list[Job]], Options]:
    """Return a function listing the current jobs, and the generation options."""
    cmd = args.command
    if cmd == "build" or (cmd == "watch" and not args.input):
        path = Path(args.config) if args.config else find_config(Path.cwd())
        if path is None:
            raise ConfigError("no config file found; create .schemaflowrc or pass --input")
        config = load_config(path)
        return config.jobs, config.options()

    if not args.input:
        raise UsageError("--input is required (or use 'schemaflow build' with a config file)")
    options = Options(readonly=args.readonly, banner=not args.no_banner, name=args.name)
    source = Path(args.input)
    if not source.exists():
        raise UsageError(f"input not found: {source}")
    if source.is_dir():
        if not args.output or args.output == "-":
            raise UsageError("a directory input needs --output DIR")
        if args.name:
            raise UsageError("--name only applies to a single schema file")
        out_dir = Path(args.output)
        return (lambda: jobs_for(sorted(source.rglob("*.json")), out_dir)), options
    return (lambda: [Job(source, _single_dest(source, args.output))]), options


def _single_dest(source: Path, output: str | None) -> Path | None:
    if not output or output == "-":
        return None
    dest = Path(output)
    return dest / output_name(source) if dest.is_dir() else dest


# -- running -------------------------------------------------------------------------------


def _say(args_quiet: bool, message: str) -> None:
    if not args_quiet:
        print(message)


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n")


def build_job(job: Job, options: Options, *, check: bool, quiet: bool) -> tuple[Result, bool]:
    """Generate one job. Returns the result and whether the output was stale (check mode)."""
    result = generate_from_path(job.source, options)
    for warning in result.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if job.dest is None:
        sys.stdout.write(result.code)
        return result, False
    existing: str | None = None
    if job.dest.is_file():
        existing = _normalise(job.dest.read_text(encoding="utf-8", errors="replace"))
    stale = existing != result.code
    if check:
        if stale:
            print(f"out of date: {job.dest} (from {job.source})")
        return result, stale
    if stale:
        job.dest.parent.mkdir(parents=True, exist_ok=True)
        with job.dest.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(result.code)
        _say(quiet, f"wrote {job.dest} ({len(result.names)} types)")
    else:
        _say(quiet, f"unchanged {job.dest}")
    return result, False


def run_once(jobs: list[Job], options: Options, args: argparse.Namespace) -> int:
    check = getattr(args, "check", False)
    strict = getattr(args, "strict", False)
    failed = stale = warned = 0
    for job in jobs:
        try:
            result, is_stale = build_job(job, options, check=check, quiet=args.quiet)
        except SchemaflowError as exc:
            print(f"schemaflow: error: {exc}", file=sys.stderr)
            failed += 1
            continue
        stale += is_stale
        warned += len(result.warnings)
    if failed:
        return 2
    if check:
        if stale:
            return 1
        _say(args.quiet, f"{len(jobs)} file(s) up to date")
    return 1 if strict and warned else 0


def run_watch(
    jobs_fn: Callable[[], list[Job]],
    options: Options,
    quiet: bool = False,
    interval: float = 0.5,
    stop: threading.Event | None = None,
) -> None:
    """Build everything, then rebuild jobs whose schema (or $ref'd file) is saved."""
    deps: dict[Path, list[Path]] = {}

    def safe_jobs() -> list[Job]:
        try:
            return jobs_fn()
        except SchemaflowError:
            return []

    def rebuild(changed: list[Path]) -> list[Path]:
        touched = {p.resolve() for p in changed}
        for job in safe_jobs():
            related = {job.source.resolve(), *deps.get(job.source, [])}
            if not related & touched:
                continue
            try:
                result, _ = build_job(job, options, check=False, quiet=quiet)
                deps[job.source] = result.dependencies
            except SchemaflowError as exc:
                print(f"schemaflow: error: {exc}", file=sys.stderr)
        return [d for found in deps.values() for d in found]

    jobs = jobs_fn()
    for job in jobs:  # initial build
        try:
            result, _ = build_job(job, options, check=False, quiet=quiet)
            deps[job.source] = result.dependencies
        except SchemaflowError as exc:
            print(f"schemaflow: error: {exc}", file=sys.stderr)
    _say(quiet, f"watching {len(jobs)} schema(s); press Ctrl+C to stop")
    sys.stdout.flush()
    watch(
        lambda: [job.source.resolve() for job in safe_jobs()],
        rebuild,
        interval=interval,
        stop=stop,
        depends_on=[d for found in deps.values() for d in found],
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in COMMANDS and argv[0] not in ("-h", "--help", "--version"):
        argv.insert(0, "generate")  # `schemaflow -i a.json -o a.ts` means `schemaflow generate ...`
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        jobs_fn, options = plan(args)
        if args.command == "watch":
            if args.interval <= 0:
                raise UsageError("--interval must be positive")
            if args.once:
                return run_once(jobs_fn(), options, args)
            try:
                run_watch(jobs_fn, options, args.quiet, args.interval)
            except KeyboardInterrupt:
                return 0
            return 0
        return run_once(jobs_fn(), options, args)
    except SchemaflowError as exc:
        print(f"schemaflow: error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    sys.exit(main())
