"""End-to-end tests for schema to TypeScript conversion pipeline."""

import json
from pathlib import Path

from schemaflow.loader import load_schema
from schemaflow.mapper import map_to_ts_type


def test_pipeline_string(tmp_path: Path) -> None:
    """Test pipeline: string schema -> string type."""
    schema = {"type": "string"}
    file_path = tmp_path / "string.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "string"


def test_pipeline_number(tmp_path: Path) -> None:
    """Test pipeline: number schema -> number type."""
    schema = {"type": "number"}
    file_path = tmp_path / "number.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "number"


def test_pipeline_integer(tmp_path: Path) -> None:
    """Test pipeline: integer schema -> number type."""
    schema = {"type": "integer"}
    file_path = tmp_path / "integer.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "number"


def test_pipeline_boolean(tmp_path: Path) -> None:
    """Test pipeline: boolean schema -> boolean type."""
    schema = {"type": "boolean"}
    file_path = tmp_path / "boolean.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "boolean"


def test_pipeline_null(tmp_path: Path) -> None:
    """Test pipeline: null schema -> null type."""
    schema = {"type": "null"}
    file_path = tmp_path / "null.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "null"


def test_pipeline_array_of_string(tmp_path: Path) -> None:
    """Test pipeline: array of strings -> string[]."""
    schema = {"type": "array", "items": {"type": "string"}}
    file_path = tmp_path / "array_string.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "string[]"


def test_pipeline_array_of_number(tmp_path: Path) -> None:
    """Test pipeline: array of numbers -> number[]."""
    schema = {"type": "array", "items": {"type": "number"}}
    file_path = tmp_path / "array_number.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "number[]"


def test_pipeline_array_of_integer(tmp_path: Path) -> None:
    """Test pipeline: array of integers -> number[]."""
    schema = {"type": "array", "items": {"type": "integer"}}
    file_path = tmp_path / "array_integer.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "number[]"


def test_pipeline_array_of_boolean(tmp_path: Path) -> None:
    """Test pipeline: array of booleans -> boolean[]."""
    schema = {"type": "array", "items": {"type": "boolean"}}
    file_path = tmp_path / "array_boolean.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "boolean[]"


def test_pipeline_array_of_null(tmp_path: Path) -> None:
    """Test pipeline: array of nulls -> null[]."""
    schema = {"type": "array", "items": {"type": "null"}}
    file_path = tmp_path / "array_null.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "null[]"


def test_pipeline_array_of_object(tmp_path: Path) -> None:
    """Test pipeline: array of objects -> object[]."""
    schema = {"type": "array", "items": {"type": "object"}}
    file_path = tmp_path / "array_object.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "object[]"


def test_pipeline_union_string_number(tmp_path: Path) -> None:
    """Test pipeline: union of string and number -> string | number."""
    schema = {"type": ["string", "number"]}
    file_path = tmp_path / "union_string_number.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "string | number"


def test_pipeline_tuple(tmp_path: Path) -> None:
    """Test pipeline: tuple schema -> [string, number]."""
    schema = {
        "type": "array",
        "items": [
            {"type": "string"},
            {"type": "number"}
        ]
    }
    file_path = tmp_path / "tuple.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "[string, number]"


def test_pipeline_object(tmp_path: Path) -> None:
    """Test pipeline: object schema -> object type."""
    schema = {"type": "object"}
    file_path = tmp_path / "object.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "object"


def test_pipeline_unknown_type(tmp_path: Path) -> None:
    """Test pipeline: schema with unknown type -> unknown."""
    schema = {"type": "unknown"}
    file_path = tmp_path / "unknown.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "unknown"


def test_pipeline_missing_type(tmp_path: Path) -> None:
    """Test pipeline: schema without type -> unknown."""
    schema = {"description": "A schema without type"}
    file_path = tmp_path / "missing_type.json"
    file_path.write_text(json.dumps(schema))
    loaded = load_schema(file_path)
    assert map_to_ts_type(loaded) == "unknown"