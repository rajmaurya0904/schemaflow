"""Tests for mapping JSON Schema constructs to TypeScript type expressions."""

import pytest

from schemaflow.errors import SchemaError
from schemaflow.mapper import map_to_ts_type


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("string", "string"),
        ("number", "number"),
        ("integer", "number"),
        ("boolean", "boolean"),
        ("null", "null"),
    ],
)
def test_primitives(kind, expected):
    assert map_to_ts_type({"type": kind}) == expected


def test_boolean_schemas():
    assert map_to_ts_type(True) == "unknown"
    assert map_to_ts_type(False) == "never"


def test_empty_schema_and_unknown_keywords_are_unknown():
    assert map_to_ts_type({}) == "unknown"
    assert map_to_ts_type({"description": "anything"}) == "unknown"


def test_type_union():
    assert map_to_ts_type({"type": ["string", "number"]}) == "string | number"
    assert map_to_ts_type({"type": ["string", "null"]}) == "string | null"
    assert map_to_ts_type({"type": ["integer", "number"]}) == "number"


def test_unknown_type_name_is_an_error():
    with pytest.raises(SchemaError, match="unknown type 'strng'") as info:
        map_to_ts_type({"type": "strng"})
    assert info.value.pointer == "/type"


def test_empty_type_list_is_an_error():
    with pytest.raises(SchemaError, match="empty array"):
        map_to_ts_type({"type": []})


def test_arrays():
    assert map_to_ts_type({"type": "array", "items": {"type": "string"}}) == "string[]"
    assert map_to_ts_type({"type": "array"}) == "unknown[]"
    assert map_to_ts_type({"items": {"type": "number"}}) == "number[]"
    assert map_to_ts_type({"type": "array", "items": False}) == "never[]"


def test_array_of_union_is_parenthesised():
    schema = {"type": "array", "items": {"type": ["string", "number"]}}
    assert map_to_ts_type(schema) == "(string | number)[]"
    schema = {"type": "array", "items": {"oneOf": [{"type": "string"}, {"type": "null"}]}}
    assert map_to_ts_type(schema) == "(string | null)[]"


def test_tuple_forms():
    draft7 = {"type": "array", "items": [{"type": "string"}, {"type": "number"}]}
    assert map_to_ts_type(draft7) == "[string, number, ...unknown[]]"
    closed = {**draft7, "additionalItems": False}
    assert map_to_ts_type(closed) == "[string, number]"
    modern = {
        "type": "array",
        "prefixItems": [{"type": "string"}],
        "items": {"type": "boolean"},
    }
    assert map_to_ts_type(modern) == "[string, ...boolean[]]"
    assert map_to_ts_type({"prefixItems": [{"type": "string"}], "items": False}) == "[string]"


def test_enum_and_const():
    assert map_to_ts_type({"enum": ["a", "b"]}) == '"a" | "b"'
    assert map_to_ts_type({"enum": [1, 2.5, True, None]}) == "1 | 2.5 | true | null"
    assert map_to_ts_type({"const": "x"}) == '"x"'
    assert map_to_ts_type({"const": {"a": 1}}) == "unknown"
    assert map_to_ts_type({"type": "string", "enum": ["a"]}) == '"a"'


def test_enum_must_be_a_non_empty_list():
    for bad in ([], "abc", {}):
        with pytest.raises(SchemaError, match="non-empty array"):
            map_to_ts_type({"enum": bad})


def test_enum_values_are_escaped():
    assert map_to_ts_type({"enum": ['say "hi"']}) == '"say \\"hi\\""'


def test_any_of_and_one_of_make_unions():
    schema = {"anyOf": [{"type": "string"}, {"type": "number"}]}
    assert map_to_ts_type(schema) == "string | number"
    schema = {"oneOf": [{"const": "a"}, {"const": "b"}, {"const": "a"}]}
    assert map_to_ts_type(schema) == '"a" | "b"'


def test_union_with_unconstrained_member_collapses():
    assert map_to_ts_type({"anyOf": [{"type": "string"}, {}]}) == "unknown"


def test_all_of_makes_an_intersection():
    schema = {
        "allOf": [
            {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]},
            {"type": "object", "properties": {"b": {"type": "number"}}},
        ]
    }
    assert map_to_ts_type(schema) == "{\n  a: string;\n} & {\n  b?: number;\n}"


def test_all_of_with_own_properties_includes_them():
    schema = {
        "type": "object",
        "properties": {"id": {"type": "string"}},
        "allOf": [{"type": "object", "properties": {"x": {"type": "number"}}}],
    }
    result = map_to_ts_type(schema)
    assert "id?: string;" in result and " & " in result and "x?: number;" in result


def test_union_inside_intersection_is_parenthesised():
    schema = {
        "allOf": [{"type": "object"}],
        "anyOf": [{"type": "string"}, {"type": "number"}],
    }
    assert map_to_ts_type(schema) == "Record<string, unknown> & (string | number)"


def test_nullable_extension():
    assert map_to_ts_type({"type": "string", "nullable": True}) == "string | null"
    assert map_to_ts_type({"type": "string", "nullable": False}) == "string"


def test_sub_schemas_must_be_non_empty_arrays():
    with pytest.raises(SchemaError, match="'allOf' must be a non-empty array"):
        map_to_ts_type({"allOf": []})
    with pytest.raises(SchemaError, match="'oneOf' must be a non-empty array"):
        map_to_ts_type({"oneOf": {"type": "string"}})


def test_non_schema_value_is_an_error():
    with pytest.raises(SchemaError, match="expected a schema object or boolean"):
        map_to_ts_type({"items": "string", "type": "array"})
