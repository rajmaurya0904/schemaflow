"""Read JSON Schema files from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import LoadError


def load_json(path: str | Path) -> Any:
    """Parse a JSON file, raising :class:`LoadError` with a readable message on any failure."""
    target = Path(path)
    if not target.exists():
        raise LoadError("file not found", target)
    if target.is_dir():
        raise LoadError("expected a file, got a directory", target)
    try:
        text = target.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise LoadError("file is not valid UTF-8", target) from None
    except OSError as exc:
        raise LoadError(f"cannot read file ({exc.strerror or exc})", target) from None
    if not text.strip():
        raise LoadError("file is empty", target)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise LoadError(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}",
                        target) from None


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load a JSON Schema whose root is an object."""
    data = load_json(path)
    if not isinstance(data, dict):
        raise LoadError(f"a schema file must contain a JSON object, found {_kind(data)}", path)
    return data


def _kind(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "a boolean"
    return {list: "an array", str: "a string", int: "a number", float: "a number"}.get(
        type(value), type(value).__name__
    )
