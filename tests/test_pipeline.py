"""End-to-end tests: schema in, TypeScript source out."""

import json
import textwrap

import pytest

from schemaflow.errors import LoadError, RefError, SchemaError
from schemaflow.mapper import Options
from schemaflow.pipeline import generate, generate_from_path, generate_ts, generate_ts_from_path


def ts(schema, **kwargs):
    return generate_ts(schema, **kwargs)


def test_simple_object_becomes_an_interface():
    code = ts(
        {
            "title": "Person",
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        }
    )
    assert code == textwrap.dedent(
        """\
        export interface Person {
          name: string;
          age?: number;
        }
        """
    )


def test_root_name_precedence(tmp_path):
    schema = {"title": "from title", "type": "object"}
    assert "export interface FromTitle " in ts(schema)
    assert "export interface Custom " in ts(schema, name="custom")
    path = tmp_path / "order-item.schema.json"
    path.write_text(json.dumps({"type": "object"}))
    assert "export interface OrderItem " in generate_ts_from_path(path)
    assert "export interface Root " in ts({"type": "object"})


def test_object_without_properties_gets_an_index_signature():
    code = ts({"type": "object"}, name="Bag")
    assert code == "export interface Bag {\n  [key: string]: unknown;\n}\n"


def test_nested_objects_are_indented():
    code = ts(
        {
            "type": "object",
            "properties": {
                "a": {
                    "type": "object",
                    "required": ["b"],
                    "properties": {
                        "b": {"type": "object", "properties": {"c": {"type": "string"}}}
                    },
                }
            },
        },
        name="T",
    )
    assert code == textwrap.dedent(
        """\
        export interface T {
          a?: {
            b: {
              c?: string;
            };
          };
        }
        """
    )


def test_array_of_objects_and_nullable_object_close_correctly():
    code = ts(
        {
            "type": "object",
            "properties": {
                "list": {"type": "array", "items": {"type": "object", "properties": {"x": {}}}},
                "maybe": {"type": ["object", "null"], "properties": {"y": {"type": "string"}}},
            },
        },
        name="T",
    )
    assert "  list?: {\n    x?: unknown;\n  }[];" in code
    assert "  maybe?: {\n    y?: string;\n  } | null;" in code


def test_definitions_become_declarations_and_refs_use_names():
    code = ts(
        {
            "type": "object",
            "properties": {"home": {"$ref": "#/definitions/address"}},
            "definitions": {
                "address": {"type": "object", "properties": {"city": {"type": "string"}}},
                "unused": {"type": "string", "enum": ["x"]},
            },
        },
        name="Person",
    )
    assert "home?: Address;" in code
    assert "export interface Address {\n  city?: string;\n}" in code
    assert 'export type Unused = "x";' in code


def test_defs_keyword_and_aliases_between_definitions():
    code = ts(
        {
            "$defs": {"id": {"type": "string"}, "userId": {"$ref": "#/$defs/id"}},
            "type": "object",
            "properties": {"owner": {"$ref": "#/$defs/userId"}},
        },
        name="Doc",
    )
    assert "export type Id = string;" in code
    assert "export type UserId = Id;" in code
    assert "owner?: UserId;" in code


def test_recursive_schema_terminates():
    code = ts(
        {
            "title": "Node",
            "type": "object",
            "properties": {
                "children": {"type": "array", "items": {"$ref": "#"}},
                "parent": {"$ref": "#"},
            },
        }
    )
    assert "children?: Node[];" in code and "parent?: Node;" in code
    assert code.count("export interface") == 1


def test_mutually_recursive_definitions():
    code = ts(
        {
            "$ref": "#/definitions/a",
            "definitions": {
                "a": {"type": "object", "properties": {"b": {"$ref": "#/definitions/b"}}},
                "b": {"type": "object", "properties": {"a": {"$ref": "#/definitions/a"}}},
            },
        },
        name="Root",
    )
    assert "export type Root = A;" in code
    assert "b?: B;" in code and "a?: A;" in code


def test_ref_to_a_nested_property_is_named_after_its_path():
    code = ts(
        {
            "type": "object",
            "properties": {
                "billing": {"type": "object", "properties": {"zip": {"type": "string"}}},
                "shipping": {"$ref": "#/properties/billing"},
            },
        },
        name="Order",
    )
    assert "shipping?: Billing;" in code
    assert "export interface Billing {" in code


def test_name_collisions_get_a_numeric_suffix():
    code = ts(
        {
            "title": "Thing",
            "type": "object",
            "properties": {"t": {"$ref": "#/definitions/thing"}},
            "definitions": {"thing": {"type": "string"}},
        }
    )
    assert "export interface Thing {" in code
    assert "export type Thing2 = string;" in code
    assert "t?: Thing2;" in code


def test_quoted_property_names_and_required_without_declaration():
    code = ts(
        {"type": "object", "required": ["ghost", "a-b"], "properties": {"a-b": {"type": "string"}}},
        name="T",
    )
    assert '"a-b": string;' in code
    assert "ghost: unknown;" in code


def test_additional_properties_forms():
    typed = ts({"type": "object", "additionalProperties": {"type": "number"}}, name="T")
    assert "[key: string]: number;" in typed
    closed = ts({"type": "object", "properties": {"a": {"type": "string"}},
                 "additionalProperties": False}, name="T")
    assert "[key:" not in closed
    mixed = ts({"type": "object", "properties": {"a": {"type": "string"}},
                "additionalProperties": {"type": "number"}}, name="T")
    assert "[key: string]: number | string;" in mixed
    anything = ts({"type": "object", "properties": {"a": {"type": "string"}},
                   "additionalProperties": True}, name="T")
    assert "[key: string]: unknown;" in anything


def test_pattern_properties_become_an_index_signature():
    code = ts({"type": "object", "patternProperties": {"^x-": {"type": "string"}}}, name="T")
    assert "[key: string]: string;" in code


def test_inline_maps():
    code = ts(
        {
            "type": "object",
            "properties": {
                "m": {"type": "object", "additionalProperties": {"type": "boolean"}},
                "closed": {"type": "object", "additionalProperties": False},
                "any": {"type": "object"},
            },
        },
        name="T",
    )
    assert "m?: Record<string, boolean>;" in code
    assert "closed?: Record<string, never>;" in code
    assert "any?: Record<string, unknown>;" in code


def test_comments_from_descriptions_and_annotations():
    code = ts(
        {
            "description": "A thing.",
            "type": "object",
            "properties": {
                "n": {
                    "type": "integer",
                    "description": "How many.\nSecond line.",
                    "default": 3,
                    "minimum": 0,
                    "maximum": 10,
                },
                "old": {"type": "string", "deprecated": True},
            },
        },
        name="T",
    )
    assert code.startswith("/** A thing. */\nexport interface T {")
    assert "  /**\n   * How many.\n   * Second line.\n   * @default 3\n   * @minimum 0" in code
    assert "   * @maximum 10\n   */\n  n?: number;" in code
    assert "  /** @deprecated */\n  old?: string;" in code


def test_readonly_option_and_keyword():
    schema = {"type": "object", "properties": {"a": {"type": "string"},
                                               "b": {"type": "string", "readOnly": True}}}
    plain = ts(schema, name="T")
    assert "  a?: string;" in plain and "  readonly b?: string;" in plain
    forced = ts(schema, options=Options(readonly=True, banner=False, name="T"))
    assert "readonly a?: string;" in forced


def test_non_object_root_is_a_type_alias():
    assert ts({"enum": ["a", "b"]}, name="Mode") == 'export type Mode = "a" | "b";\n'
    assert ts({"type": "array", "items": {"type": "number"}}, name="L") == (
        "export type L = number[];\n"
    )
    assert ts(True, name="Any") == "export type Any = unknown;\n"


def test_unsupported_keywords_produce_warnings_once():
    result = generate(
        {
            "type": "object",
            "properties": {
                "a": {"if": {}, "then": {}},
                "b": {"if": {}, "then": {}},
                "c": {"not": {"type": "string"}},
            },
        },
        options=Options(banner=False, name="T"),
    )
    assert len(result.warnings) == 2
    assert any("if/then/else" in w for w in result.warnings)
    assert any("'not'" in w for w in result.warnings)


def test_invalid_schema_pieces_name_their_location():
    with pytest.raises(SchemaError, match="'properties' must be an object") as info:
        ts({"type": "object", "properties": []})
    assert info.value.pointer == "/properties"
    with pytest.raises(SchemaError, match="'required' must be an array"):
        ts({"type": "object", "required": "id"})
    with pytest.raises(SchemaError, match="unknown type") as info:
        ts({"type": "object", "properties": {"a": {"type": "text"}}})
    assert info.value.pointer == "/properties/a/type"
    with pytest.raises(SchemaError, match="'definitions' must be an object"):
        ts({"definitions": []})
    with pytest.raises(SchemaError, match="must be a JSON object or boolean"):
        generate(["not", "a", "schema"])


def test_dangling_reference():
    with pytest.raises(RefError, match="not found") as info:
        ts({"type": "object", "properties": {"a": {"$ref": "#/definitions/Missing"}}})
    assert info.value.pointer == "/properties/a/$ref"


def test_banner_names_the_source_and_is_deterministic(tmp_path):
    path = tmp_path / "user.json"
    path.write_text(json.dumps({"type": "object", "properties": {"id": {"type": "string"}}}))
    first = generate_ts_from_path(path)
    assert first.startswith("/* eslint-disable */\n/**\n * This file was generated by schemaflow "
                            "from user.json.")
    assert generate_ts_from_path(path) == first
    bare = generate_from_path(path, Options(banner=False)).code
    assert bare.startswith("export interface User ")


def test_references_to_other_files(tmp_path):
    (tmp_path / "common.json").write_text(
        json.dumps(
            {
                "definitions": {
                    "Money": {
                        "type": "object",
                        "required": ["amount"],
                        "properties": {"amount": {"type": "number"}},
                    }
                }
            }
        )
    )
    main = tmp_path / "invoice.json"
    main.write_text(
        json.dumps(
            {
                "type": "object",
                "properties": {"total": {"$ref": "common.json#/definitions/Money"}},
            }
        )
    )
    code = generate_from_path(main).code
    assert "total?: Money;" in code
    assert "export interface Money {\n  amount: number;\n}" in code


def test_missing_input_file(tmp_path):
    with pytest.raises(LoadError, match="file not found"):
        generate_from_path(tmp_path / "missing.json")
