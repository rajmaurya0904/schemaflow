"""Example programmatic usage of Schemaflow pipeline."""

import json
import sys
from pathlib import Path


def main() -> None:
    # Ensure the package can be imported when running this script directly.
    # Add the repository root (parent of the examples directory) to sys.path.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))

    # Import after sys.path manipulation.
    from schemaflow.mapper import map_to_ts_type

    # Example JSON Schema for a Person
    person_schema = {
        "type": "object",
        "properties": {
            "id": {"type": "integer"},
            "name": {"type": "string"},
            "email": {"type": "string", "format": "email"},
            "age": {"type": "integer", "minimum": 0},
            "is_active": {"type": "boolean"},
            "tags": {
                "type": "array",
                "items": {"type": "string"}
            },
            "address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"}
                },
                "required": ["street", "city"]
            }
        },
        "required": ["id", "name"]
    }

    # Convert to TypeScript type
    ts_type = map_to_ts_type(person_schema)

    # Print the result
    print("JSON Schema:")
    print(json.dumps(person_schema, indent=2))
    print("\nEquivalent TypeScript type:")
    print(ts_type)


if __name__ == "__main__":
    main()