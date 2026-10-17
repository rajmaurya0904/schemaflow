"""Unit tests for schemaflow.mapper module."""

from schemaflow.mapper import map_to_ts_type


def test_string_type() -> None:
    """Test mapping of string type."""
    assert map_to_ts_type({"type": "string"}) == "string"


def test_number_type() -> None:
    """Test mapping of number type."""
    assert map_to_ts_type({"type": "number"}) == "number"


def test_integer_type() -> None:
    """Test mapping of integer type."""
    assert map_to_ts_type({"type": "integer"}) == "number"


def test_boolean_type() -> None:
    """Test mapping of boolean type."""
    assert map_to_ts_type({"type": "boolean"}) == "boolean"


def test_null_type() -> None:
    """Test mapping of null type."""
    assert map_to_ts_type({"type": "null"}) == "null"


def test_array_of_strings() -> None:
    """Test mapping of array of strings."""
    schema = {"type": "array", "items": {"type": "string"}}
    assert map_to_ts_type(schema) == "string[]"


def test_array_of_numbers() -> None:
    """Test mapping of array of numbers."""
    schema = {"type": "array", "items": {"type": "number"}}
    assert map_to_ts_type(schema) == "number[]"


def test_array_of_booleans() -> None:
    """Test mapping of array of booleans."""
    schema = {"type": "array", "items": {"type": "boolean"}}
    assert map_to_ts_type(schema) == "boolean[]"


def test_array_of_objects() -> None:
    """Test mapping of array of objects."""
    schema = {"type": "array", "items": {"type": "object"}}
    assert map_to_ts_type(schema) == "object[]"


def test_array_without_items() -> None:
    """Test mapping of array without items definition."""
    schema = {"type": "array"}
    assert map_to_ts_type(schema) == "unknown[]"


def test_object_type() -> None:
    """Test mapping of object type."""
    assert map_to_ts_type({"type": "object"}) == "object"


def test_union_type() -> None:
    """Test mapping of union type (string or number)."""
    schema = {"type": ["string", "number"]}
    assert map_to_ts_type(schema) == "string | number"


def test_tuple_type() -> None:
    """Test mapping of tuple type."""
    schema = {
        "type": "array",
        "items": [
            {"type": "string"},
            {"type": "number"},
        ],
    }
    assert map_to_ts_type(schema) == "[string, number]"


def test_unknown_type() -> None:
    """Test mapping of unknown type."""
    assert map_to_ts_type({"type": "unknown"}) == "unknown"
    # Also test empty schema
    assert map_to_ts_type({}) == "unknown"