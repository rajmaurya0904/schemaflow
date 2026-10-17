"""TypeScript type mapper for JSON Schema."""

def map_to_ts_type(schema: dict) -> str:
    """
    Map a JSON Schema to a TypeScript type string.

    Args:
        schema: A JSON Schema dictionary.

    Returns:
        A TypeScript type string.
    """
    # Handle boolean schema (true/false) - not expected in practice but we can handle
    if schema is True:
        return "unknown"
    if schema is False:
        return "never"

    # If schema has a 'type' field
    if "type" in schema:
        schema_type = schema["type"]
        # If type is an array (union of types)
        if isinstance(schema_type, list):
            # Map each type and join with union
            mapped = [_map_single_type(t) for t in schema_type]
            return " | ".join(mapped)
        else:
            return _map_single_type(schema_type, schema)
    # If no type, but has other properties (like const, enum, etc.) - we ignore for now
    # Return unknown as fallback
    return "unknown"


def _map_single_type(type_name: str, schema: dict | None = None) -> str:
    """Map a single JSON Schema type to TypeScript."""
    if type_name == "string":
        return "string"
    if type_name == "number":
        return "number"
    if type_name == "integer":
        return "number"
    if type_name == "boolean":
        return "boolean"
    if type_name == "null":
        return "null"
    if type_name == "array":
        # Array type: need to map items
        if schema and "items" in schema:
            items_schema = schema["items"]
            # items can be a schema or a list of schemas (for tuple)
            if isinstance(items_schema, list):
                # Tuple type: [item1, item2, ...]
                tuple_types = [map_to_ts_type(item) for item in items_schema]
                return f"[{', '.join(tuple_types)}]"
            else:
                item_type = map_to_ts_type(items_schema)
                return f"{item_type}[]"
        else:
            # Array without items definition
            return "unknown[]"
    if type_name == "object":
        # For now, we return a generic object type.
        # In the future, we can expand to handle properties.
        return "object"
    # Unknown type
    return "unknown"