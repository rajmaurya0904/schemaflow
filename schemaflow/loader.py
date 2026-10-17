"""Utility functions for loading JSON Schema files."""

import json
from pathlib import Path
from typing import Any


def load_schema(file_path: str | Path) -> dict[str, Any]:
    """
    Load and parse a JSON Schema file from disk.

    Args:
        file_path: Path to the JSON Schema file.

    Returns:
        Parsed JSON Schema as a dictionary.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        ValueError: If the file is empty or not a JSON object.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Schema file not found: {path}")

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"Schema file is empty: {path}")

    try:
        schema = json.loads(content)
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(
            f"Invalid JSON in schema file {path}: {e.msg}", e.doc, e.pos
        ) from e

    if not isinstance(schema, dict):
        raise ValueError(
            f"Schema file must contain a JSON object, got {type(schema).__name__}"
        )

    return schema