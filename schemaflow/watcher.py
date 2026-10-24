"""Poll files for changes and rebuild what depends on them (the "on save" loop)."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

Stamp = tuple[int, int]  # (mtime in ns, size)


def stamp(path: Path) -> Stamp | None:
    try:
        info = path.stat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


@dataclass
class Changes:
    added: list[Path] = field(default_factory=list)
    modified: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.added or self.modified or self.removed)

    @property
    def paths(self) -> list[Path]:
        return [*self.added, *self.modified, *self.removed]


class Watcher:
    """Remembers a (mtime, size) stamp per file; :meth:`poll` reports what moved since."""

    def __init__(self, paths: Iterable[Path] = ()) -> None:
        self._stamps: dict[Path, Stamp | None] = {Path(p): stamp(Path(p)) for p in paths}

    def set_paths(self, paths: Iterable[Path]) -> None:
        """Watch exactly ``paths``. Files not seen before count as added on the next poll."""
        wanted = {Path(p) for p in paths}
        self._stamps = {p: self._stamps.get(p) for p in wanted}

    def baseline(self, paths: Iterable[Path]) -> None:
        """Record the current state of ``paths`` so they are not reported as new."""
        for path in paths:
            if path in self._stamps:
                self._stamps[path] = stamp(path)

    def poll(self) -> Changes:
        changes = Changes()
        for path in sorted(self._stamps):
            before, now = self._stamps[path], stamp(path)
            if before == now:
                continue
            self._stamps[path] = now
            if before is None:
                changes.added.append(path)
            elif now is None:
                changes.removed.append(path)
            else:
                changes.modified.append(path)
        return changes


def watch(
    sources: Callable[[], Iterable[Path]],
    rebuild: Callable[[list[Path]], Iterable[Path]],
    interval: float = 0.5,
    stop: threading.Event | None = None,
    settle: float = 0.05,
    depends_on: Iterable[Path] = (),
) -> None:
    """Run ``rebuild`` whenever a watched file changes, until ``stop`` is set.

    ``sources()`` lists the files to watch and is called every cycle, so files that appear
    later are picked up. ``rebuild(changed)`` receives the changed paths and returns the extra
    files the build depended on (such as ``$ref`` targets), which are watched from then on.
    ``depends_on`` seeds that set; the initial build is the caller's job.
    """
    stop = stop or threading.Event()
    extra = {Path(p) for p in depends_on}
    watcher = Watcher([*sources(), *extra])
    while not stop.wait(interval):
        watcher.set_paths([*sources(), *extra])
        changes = watcher.poll()
        if not changes:
            continue
        if settle:  # editors often write a file in several steps; let them finish
            stop.wait(settle)
            watcher.poll()
        extra = {Path(p) for p in rebuild(changes.paths)}
        watcher.set_paths([*sources(), *extra])
        watcher.baseline([*sources(), *extra])
