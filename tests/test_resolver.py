"""Tests for $ref resolution."""

import json

import pytest

from schemaflow.errors import RefError
from schemaflow.resolver import Document, Resolver, find_anchor, split_pointer


def doc(root, path=None):
    return Document(root, path)


def test_split_pointer():
    assert split_pointer("") == []
    assert split_pointer("/definitions/a") == ["definitions", "a"]
    assert split_pointer("/a~1b/c~0d") == ["a/b", "c~d"]
    assert split_pointer("/with%20space") == ["with space"]


def test_root_reference():
    root = doc({"type": "object"})
    target = Resolver(root).resolve("#", root)
    assert target.schema is root.root and target.pointer == ""


def test_definitions_and_defs():
    root = doc({"definitions": {"a": {"type": "string"}}, "$defs": {"b": {"type": "number"}}})
    resolver = Resolver(root)
    assert resolver.resolve("#/definitions/a", root).schema == {"type": "string"}
    assert resolver.resolve("#/$defs/b", root).schema == {"type": "number"}


def test_array_index_in_pointer():
    root = doc({"allOf": [{"type": "string"}, {"type": "number"}]})
    assert Resolver(root).resolve("#/allOf/1", root).schema == {"type": "number"}


def test_escaped_keys():
    root = doc({"definitions": {"a/b": {"type": "string"}}})
    assert Resolver(root).resolve("#/definitions/a~1b", root).schema == {"type": "string"}


def test_missing_target_names_the_missing_segment():
    root = doc({"definitions": {}})
    with pytest.raises(RefError, match="'Nope' not found"):
        Resolver(root).resolve("#/definitions/Nope", root, "/properties/x")


def test_index_out_of_range():
    root = doc({"allOf": []})
    with pytest.raises(RefError, match="not found"):
        Resolver(root).resolve("#/allOf/0", root)


def test_non_string_ref():
    root = doc({})
    with pytest.raises(RefError, match="must be a string"):
        Resolver(root).resolve(5, root)


def test_remote_references_are_refused():
    root = doc({})
    with pytest.raises(RefError, match="remote reference"):
        Resolver(root).resolve("https://example.com/s.json#/a", root)


def test_file_reference_needs_a_file_context():
    root = doc({})
    with pytest.raises(RefError, match="not read from a file"):
        Resolver(root).resolve("other.json", root)


def test_relative_file_reference(tmp_path):
    (tmp_path / "common.json").write_text(
        json.dumps({"definitions": {"Id": {"type": "string"}}}), encoding="utf-8"
    )
    main = tmp_path / "main.json"
    main.write_text("{}")
    root = doc({}, main.resolve())
    resolver = Resolver(root)
    target = resolver.resolve("common.json#/definitions/Id", root)
    assert target.schema == {"type": "string"}
    assert target.document.path == (tmp_path / "common.json").resolve()
    # the file is only parsed once
    again = resolver.resolve("common.json#/definitions/Id", root)
    assert again.document is target.document


def test_reference_inside_external_file_is_relative_to_that_file(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "inner.json").write_text('{"type": "boolean"}')
    (sub / "outer.json").write_text(json.dumps({"x": {"$ref": "inner.json"}}))
    main = tmp_path / "main.json"
    root = doc({}, main.resolve())
    resolver = Resolver(root)
    outer = resolver.resolve("sub/outer.json#/x", root)
    inner = resolver.resolve(outer.schema["$ref"], outer.document)
    assert inner.schema == {"type": "boolean"}


def test_missing_external_file(tmp_path):
    root = doc({}, (tmp_path / "main.json").resolve())
    with pytest.raises(RefError, match="file not found"):
        Resolver(root).resolve("gone.json", root)


def test_reference_back_to_the_root_file(tmp_path):
    main = (tmp_path / "main.json").resolve()
    main.write_text("{}")
    root = doc({"definitions": {"a": {"type": "string"}}}, main)
    target = Resolver(root).resolve("main.json#/definitions/a", root)
    assert target.document is root


def test_anchors():
    root = doc({"definitions": {"a": {"$anchor": "thing", "type": "string"}}})
    target = Resolver(root).resolve("#thing", root)
    assert target.schema["type"] == "string"
    assert target.pointer == "/definitions/a"
    assert find_anchor(root.root, "missing") is None
    with pytest.raises(RefError, match="no anchor"):
        Resolver(root).resolve("#missing", root)
