"""Tests for loading schema files and the error type."""

import json

import pytest

from schemaflow.errors import LoadError, SchemaflowError
from schemaflow.loader import load_json, load_schema


def test_loads_a_valid_schema(tmp_path):
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}
    path = tmp_path / "s.json"
    path.write_text(json.dumps(schema), encoding="utf-8")
    assert load_schema(path) == schema
    assert load_schema(str(path)) == schema


def test_missing_file(tmp_path):
    with pytest.raises(LoadError, match="file not found") as info:
        load_schema(tmp_path / "nope.json")
    assert "nope.json" in str(info.value)


def test_directory_is_rejected(tmp_path):
    with pytest.raises(LoadError, match="directory"):
        load_schema(tmp_path)


def test_empty_file(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("  \n")
    with pytest.raises(LoadError, match="empty"):
        load_schema(path)


def test_malformed_json_reports_position(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('{\n  "type": "object",\n  oops\n}')
    with pytest.raises(LoadError, match=r"line 3, column 3"):
        load_schema(path)


def test_non_object_root(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("[1, 2]")
    with pytest.raises(LoadError, match="found an array"):
        load_schema(path)
    path.write_text("true")
    with pytest.raises(LoadError, match="found a boolean"):
        load_schema(path)


def test_bom_is_tolerated(tmp_path):
    path = tmp_path / "s.json"
    path.write_bytes(b"\xef\xbb\xbf" + b'{"type": "string"}')
    assert load_schema(path) == {"type": "string"}


def test_invalid_utf8(tmp_path):
    path = tmp_path / "s.json"
    path.write_bytes(b'{"a": "\xff\xfe"}')
    with pytest.raises(LoadError, match="UTF-8"):
        load_json(path)


def test_error_message_includes_source_and_pointer():
    error = SchemaflowError("bad type", "a.json", "/properties/x")
    assert str(error) == "a.json#/properties/x: bad type"
    assert error.message == "bad type" and error.pointer == "/properties/x"
    assert str(SchemaflowError("plain")) == "plain"
    assert str(SchemaflowError("m", pointer="/a")) == "#/a: m"
