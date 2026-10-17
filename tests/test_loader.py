"""Unit tests for schemaflow.loader module."""

import json
from pathlib import Path

from schemaflow.loader import load_schema


def test_load_schema_valid_json(tmp_path: Path) -> None:
    """Test loading a valid JSON Schema file returns parsed dictionary."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name"],
    }
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")

    result = load_schema(schema_file)

    assert result == schema
    assert isinstance(result, dict)


def test_load_schema_with_string_path(tmp_path: Path) -> None:
    """Test loading works with string path."""
    schema = {"type": "string"}
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")

    result = load_schema(str(schema_file))

    assert result == schema