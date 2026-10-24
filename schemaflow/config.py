"""Project configuration (``.schemaflowrc``, ``schemaflow.json`` or ``[tool.schemaflow]``)."""

from __future__ import annotations

import glob
import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError
from .mapper import Options

CONFIG_NAMES = (".schemaflowrc", "schemaflow.json")
KNOWN_KEYS = {"input", "outDir", "extension", "readonly", "banner"}


@dataclass(frozen=True)
class Job:
    """One schema file and the TypeScript file it is generated into."""

    source: Path
    dest: Path | None  # None means standard output


@dataclass
class Config:
    """Settings read from a config file; paths are relative to ``base``."""

    base: Path
    input: list[str] = field(default_factory=list)
    out_dir: str = "."
    extension: str = ".ts"
    readonly: bool = False
    banner: bool = True
    origin: Path | None = None

    def options(self) -> Options:
        return Options(readonly=self.readonly, banner=self.banner)

    def jobs(self) -> list[Job]:
        """Expand the input globs into jobs. Raises if nothing matches or names collide."""
        found: list[Path] = []
        for pattern in self.input:
            full = pattern if os.path.isabs(pattern) else os.path.join(self.base, pattern)
            for match in sorted(glob.glob(full, recursive=True)):
                path = Path(match)
                if path.is_file() and path not in found:
                    found.append(path)
        if not found:
            raise ConfigError(
                f"no schema files match {', '.join(self.input)}", self.origin, None
            )
        return jobs_for(found, self.base / self.out_dir, self.extension)


def output_name(source: Path, extension: str = ".ts") -> str:
    """``user.schema.json`` -> ``user.ts``."""
    stem = source.name
    for suffix in (".json",):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
    if stem.lower().endswith(".schema"):
        stem = stem[: -len(".schema")]
    return (stem or "schema") + (extension if extension.startswith(".") else "." + extension)


def jobs_for(sources: list[Path], out_dir: Path, extension: str = ".ts") -> list[Job]:
    """Pair each source with ``out_dir/<name>.ts``; two sources must not share an output."""
    jobs: list[Job] = []
    taken: dict[Path, Path] = {}
    for source in sources:
        dest = out_dir / output_name(source, extension)
        if dest in taken:
            raise ConfigError(f"{taken[dest]} and {source} would both be written to {dest}")
        taken[dest] = source
        jobs.append(Job(source, dest))
    return jobs


def find_config(start: Path) -> Path | None:
    """Look for a config file in ``start`` and its parents."""
    start = start.resolve()
    for folder in [start, *start.parents]:
        for name in CONFIG_NAMES:
            if (folder / name).is_file():
                return folder / name
        pyproject = folder / "pyproject.toml"
        if pyproject.is_file() and _pyproject_table(pyproject) is not None:
            return pyproject
    return None


def _pyproject_table(path: Path) -> dict[str, Any] | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    table = data.get("tool", {}).get("schemaflow")
    return table if isinstance(table, dict) else None


def load_config(path: str | Path) -> Config:
    """Read and validate a config file."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError("config file not found", path)
    try:
        if path.name == "pyproject.toml":
            raw: Any = _pyproject_table(path)
            if raw is None:
                raise ConfigError("no [tool.schemaflow] table", path)
        elif path.suffix == ".toml":
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        else:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"invalid syntax: {exc}", path) from None
    except OSError as exc:
        raise ConfigError(f"cannot read config ({exc.strerror or exc})", path) from None
    return _from_mapping(raw, path)


def _from_mapping(raw: Any, path: Path) -> Config:
    if not isinstance(raw, dict):
        raise ConfigError("the config must be an object", path)
    unknown = sorted(set(raw) - KNOWN_KEYS)
    if unknown:
        raise ConfigError(
            f"unknown option {unknown[0]!r}; expected one of {', '.join(sorted(KNOWN_KEYS))}", path
        )
    patterns = raw.get("input")
    if isinstance(patterns, str):
        patterns = [patterns]
    if not isinstance(patterns, list) or not patterns or not all(
        isinstance(p, str) and p for p in patterns
    ):
        raise ConfigError("'input' must be a glob string or a non-empty list of globs", path)
    config = Config(base=path.parent, input=patterns, origin=path)
    for key, attr, kind in (
        ("outDir", "out_dir", str),
        ("extension", "extension", str),
        ("readonly", "readonly", bool),
        ("banner", "banner", bool),
    ):
        if key in raw:
            if not isinstance(raw[key], kind):
                raise ConfigError(f"'{key}' must be a {kind.__name__}", path)
            setattr(config, attr, raw[key])
    return config
