"""Map JSON Schema to TypeScript types and declarations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .errors import SchemaError
from .naming import comment_lines, literal, parens, pascal_case, prop_key
from .resolver import Document, Resolver, Target, split_pointer

PRIMITIVES = {
    "string": "string",
    "number": "number",
    "integer": "number",
    "boolean": "boolean",
    "null": "null",
}
JSON_TYPES = (*PRIMITIVES, "array", "object")
DEFINITION_KEYS = ("definitions", "$defs")
INDENT = "  "

# keyword -> what is lost when it is ignored
UNSUPPORTED = {
    "if": "conditional subschemas (if/then/else) are ignored",
    "not": "'not' is ignored",
    "dependentSchemas": "'dependentSchemas' is ignored",
    "dependencies": "'dependencies' is ignored",
    "propertyNames": "'propertyNames' is ignored",
    "unevaluatedProperties": "'unevaluatedProperties' is ignored",
    "contains": "'contains' is ignored",
}


@dataclass
class Options:
    """Switches for the generated code."""

    readonly: bool = False  # mark every property readonly
    banner: bool = True  # "generated, do not edit" header
    name: str | None = None  # name of the root type; default comes from title or file name


@dataclass
class _Pending:
    name: str
    target: Target


def _join(parts: list[str]) -> list[str]:
    seen: list[str] = []
    for part in parts:
        if part not in seen:
            seen.append(part)
    return seen


def union(parts: list[str]) -> str:
    """``a | b`` with duplicates removed; ``unknown`` swallows everything, ``never`` vanishes."""
    parts = [part for part in _join(parts) if part != "never"]
    if not parts:
        return "never"
    if "unknown" in parts:
        return "unknown"
    return " | ".join(parts)


def intersection(parts: list[str]) -> str:
    parts = [part for part in _join(parts) if part != "unknown"]
    if not parts:
        return "unknown"
    if "never" in parts:
        return "never"
    if len(parts) == 1:
        return parts[0]
    return " & ".join(parens(part) if " | " in part else part for part in parts)


class TypeBuilder:
    """Walks a schema and builds named TypeScript declarations.

    Every ``$ref`` target becomes one named declaration, referenced by name, so shared and
    recursive definitions are emitted once.
    """

    def __init__(self, root: Document, options: Options | None = None) -> None:
        self.root = root
        self.options = options or Options()
        self.resolver = Resolver(root)
        self.warnings: list[str] = []
        self.declared: list[str] = []
        self._names: dict[tuple[str, str], str] = {}
        self._used: set[str] = set()
        self._queue: list[_Pending] = []
        self._declarations: list[str] = []
        self._warned: set[tuple[str, str]] = set()

    # -- public ---------------------------------------------------------------------

    def build(self) -> list[str]:
        """Return all declarations, the root type first."""
        root_schema = self.root.root
        if not isinstance(root_schema, (dict, bool)):
            raise SchemaError("a schema must be an object or a boolean", self.root.label, "")
        target = Target(self.root, root_schema, "")
        self._name_for(target, self._root_name(root_schema))
        if isinstance(root_schema, dict):
            for keyword in DEFINITION_KEYS:
                definitions = root_schema.get(keyword)
                if definitions is None:
                    continue
                if not isinstance(definitions, dict):
                    raise SchemaError(f"'{keyword}' must be an object", self.root.label,
                                      f"/{keyword}")
                for key in definitions:
                    escaped = key.replace("~", "~0").replace("/", "~1")
                    self._name_for(Target(self.root, definitions[key], f"/{keyword}/{escaped}"))
        while self._queue:
            pending = self._queue.pop(0)
            self.declared.append(pending.name)
            self._declarations.append(self._declare(pending.name, pending.target))
        return self._declarations

    def type_of(self, schema: Any, document: Document | None = None, pointer: str = "",
                level: int = 0) -> str:
        """TypeScript type expression for ``schema`` (may span lines when it holds an object)."""
        document = document or self.root
        if schema is True:
            return "unknown"
        if schema is False:
            return "never"
        if not isinstance(schema, dict):
            raise SchemaError(
                f"expected a schema object or boolean, found {type(schema).__name__}",
                document.label,
                pointer,
            )
        self._warn_unsupported(schema, document, pointer)

        pieces: list[str] = []
        if "$ref" in schema:
            pieces.append(self._ref_type(schema["$ref"], document, pointer))
        elif "const" in schema:
            pieces.append(literal(schema["const"]) or "unknown")
        elif "enum" in schema:
            pieces.append(self._enum_type(schema["enum"], document, pointer))
        else:
            base = self._typed(schema, document, pointer, level)
            if base is not None:
                pieces.append(base)

        all_of = self._subschemas(schema, "allOf", document, pointer, level)
        pieces.extend(all_of)
        for keyword in ("anyOf", "oneOf"):
            options = self._subschemas(schema, keyword, document, pointer, level)
            if options:
                pieces.append(union(options))

        result = intersection(pieces) if pieces else "unknown"
        if schema.get("nullable") is True:
            result = union([result, "null"]) if result != "unknown" else result
        return result

    # -- declarations -----------------------------------------------------------------

    def _root_name(self, schema: Any) -> str:
        if self.options.name:
            return pascal_case(self.options.name)
        if isinstance(schema, dict) and isinstance(schema.get("title"), str):
            title = pascal_case(schema["title"])
            if title != "Schema":
                return title
        if self.root.path is not None:
            return pascal_case(self.root.path.name.split(".")[0])
        return "Root"

    def _name_for(self, target: Target, preferred: str | None = None) -> str:
        key = target.key
        if key in self._names:
            return self._names[key]
        base = preferred or self._derive_name(target)
        name, n = base, 2
        while name in self._used:
            name, n = f"{base}{n}", n + 1
        self._used.add(name)
        self._names[key] = name
        self._queue.append(_Pending(name, target))
        return name

    def _derive_name(self, target: Target) -> str:
        tokens = split_pointer(target.pointer)
        if not tokens:
            doc = target.document
            title = target.schema.get("title") if isinstance(target.schema, dict) else None
            if isinstance(title, str) and pascal_case(title) != "Schema":
                return pascal_case(title)
            return pascal_case(doc.path.name.split(".")[0]) if doc.path else "Root"
        if len(tokens) >= 2 and tokens[-2] in DEFINITION_KEYS:
            return pascal_case(tokens[-1])
        meaningful = [t for t in tokens if t not in ("properties", "items", *DEFINITION_KEYS)]
        return pascal_case(" ".join(meaningful or tokens))

    def _declare(self, name: str, target: Target) -> str:
        schema, document, pointer = target.schema, target.document, target.pointer
        header: list[str] = []
        if isinstance(schema, dict):
            header = self._doc_comment(schema, "")
        if isinstance(schema, dict) and self._is_plain_object(schema):
            members = self._object_members(schema, document, pointer, 1) or [
                f"{INDENT}[key: string]: unknown;"
            ]
            return "\n".join([*header, f"export interface {name} {{", *members, "}"])
        expr = self.type_of(schema, document, pointer, 0)
        return "\n".join([*header, f"export type {name} = {expr};"])

    @staticmethod
    def _is_plain_object(schema: dict[str, Any]) -> bool:
        if any(k in schema for k in ("$ref", "allOf", "anyOf", "oneOf", "enum", "const")):
            return False
        if schema.get("nullable") is True:
            return False
        kind = schema.get("type")
        if kind == "object":
            return True
        return kind is None and any(
            k in schema for k in ("properties", "additionalProperties", "patternProperties")
        )

    # -- type pieces ---------------------------------------------------------------------

    def _ref_type(self, ref: Any, document: Document, pointer: str) -> str:
        target = self.resolver.resolve(ref, document, f"{pointer}/$ref")
        return self._name_for(target)

    def _enum_type(self, values: Any, document: Document, pointer: str) -> str:
        if not isinstance(values, list) or not values:
            raise SchemaError("'enum' must be a non-empty array", document.label,
                              f"{pointer}/enum")
        return union([literal(value) or "unknown" for value in values])

    def _subschemas(self, schema: dict[str, Any], keyword: str, document: Document,
                    pointer: str, level: int) -> list[str]:
        value = schema.get(keyword)
        if value is None:
            return []
        if not isinstance(value, list) or not value:
            raise SchemaError(f"'{keyword}' must be a non-empty array", document.label,
                              f"{pointer}/{keyword}")
        return [
            self.type_of(item, document, f"{pointer}/{keyword}/{index}", level)
            for index, item in enumerate(value)
        ]

    def _typed(self, schema: dict[str, Any], document: Document, pointer: str,
               level: int) -> str | None:
        kind = schema.get("type")
        if kind is None:
            if any(k in schema for k in ("properties", "additionalProperties",
                                         "patternProperties", "required")):
                kind = "object"
            elif any(k in schema for k in ("items", "prefixItems")):
                kind = "array"
            elif any(k in schema for k in ("allOf", "anyOf", "oneOf")):
                return None
            else:
                return "unknown"
        kinds = kind if isinstance(kind, list) else [kind]
        if not kinds:
            raise SchemaError("'type' must not be an empty array", document.label,
                              f"{pointer}/type")
        out = []
        for item in kinds:
            if item not in JSON_TYPES:
                raise SchemaError(
                    f"unknown type {item!r}; expected one of {', '.join(JSON_TYPES)}",
                    document.label,
                    f"{pointer}/type",
                )
            out.append(self._single(item, schema, document, pointer, level))
        return union(out)

    def _single(self, kind: str, schema: dict[str, Any], document: Document, pointer: str,
                level: int) -> str:
        if kind in PRIMITIVES:
            return PRIMITIVES[kind]
        if kind == "array":
            return self._array(schema, document, pointer, level)
        return self._object(schema, document, pointer, level)

    def _array(self, schema: dict[str, Any], document: Document, pointer: str,
               level: int) -> str:
        items = schema.get("items")
        prefix = schema.get("prefixItems")
        if isinstance(items, list):  # draft-07 tuple form
            prefix, rest = items, schema.get("additionalItems", True)
        else:
            rest = items if items is not None else True
        if prefix is not None:
            if not isinstance(prefix, list):
                raise SchemaError("'prefixItems' must be an array", document.label,
                                  f"{pointer}/prefixItems")
            parts = [
                self.type_of(item, document, f"{pointer}/prefixItems/{i}", level)
                for i, item in enumerate(prefix)
            ]
            if rest is not False:
                tail = self.type_of(rest, document, f"{pointer}/items", level)
                parts.append(f"...{parens(tail)}[]")
            return f"[{', '.join(parts)}]"
        element = self.type_of(items, document, f"{pointer}/items", level) \
            if items is not None else "unknown"
        return f"{parens(element)}[]"

    def _object(self, schema: dict[str, Any], document: Document, pointer: str,
                level: int) -> str:
        if not schema.get("properties") and not schema.get("required"):
            extras = self._extra_types(schema, document, pointer, level)
            if schema.get("additionalProperties") is False and not extras:
                return "Record<string, never>"
            return f"Record<string, {union(extras or ['unknown'])}>"
        members = self._object_members(schema, document, pointer, level + 1)
        return "\n".join(["{", *members, f"{INDENT * level}}}"])

    def _extra_types(self, schema: dict[str, Any], document: Document, pointer: str,
                     level: int) -> list[str]:
        """Value types allowed for properties that are not listed by name."""
        extras: list[str] = []
        additional = schema.get("additionalProperties")
        if additional is True:
            extras.append("unknown")
        elif additional is not None and additional is not False:
            extras.append(self.type_of(additional, document, f"{pointer}/additionalProperties",
                                       level))
        patterns = schema.get("patternProperties")
        if patterns is not None:
            if not isinstance(patterns, dict):
                raise SchemaError("'patternProperties' must be an object", document.label,
                                  f"{pointer}/patternProperties")
            for regex, sub in patterns.items():
                extras.append(self.type_of(sub, document, f"{pointer}/patternProperties/{regex}",
                                           level))
        return extras

    def _object_members(self, schema: dict[str, Any], document: Document, pointer: str,
                        level: int) -> list[str]:
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict):
            raise SchemaError("'properties' must be an object", document.label,
                              f"{pointer}/properties")
        if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
            raise SchemaError("'required' must be an array of property names",
                              document.label, f"{pointer}/required")
        pad = INDENT * level
        lines: list[str] = []
        value_types: list[str] = []
        for name, sub in properties.items():
            sub_pointer = f"{pointer}/properties/{name.replace('~', '~0').replace('/', '~1')}"
            expr = self.type_of(sub, document, sub_pointer, level)
            value_types.append(expr)
            if isinstance(sub, dict):
                lines.extend(self._doc_comment(sub, pad))
            read_only = isinstance(sub, dict) and sub.get("readOnly") is True
            modifier = "readonly " if self.options.readonly or read_only else ""
            optional = "" if name in required else "?"
            lines.append(f"{pad}{modifier}{prop_key(name)}{optional}: {expr};")
        for name in required:
            if name not in properties:
                lines.append(f"{pad}{prop_key(name)}: unknown;")
                value_types.append("unknown")

        extras = self._extra_types(schema, document, pointer, level)
        if extras:
            # An index signature must accept every named property too.
            lines.append(f"{pad}[key: string]: {union(extras + value_types)};")
        return lines

    # -- comments and warnings -------------------------------------------------------------

    @staticmethod
    def _doc_comment(schema: dict[str, Any], pad: str) -> list[str]:
        text: list[str] = []
        for key in ("description", "title"):
            value = schema.get(key)
            if isinstance(value, str) and value.strip():
                text.append(value.strip())
                break
        if "default" in schema:
            text.append(f"@default {json.dumps(schema['default'], ensure_ascii=False)}")
        if schema.get("deprecated") is True:
            text.append("@deprecated")
        for key in ("format", "pattern", "minimum", "maximum"):
            if key in schema and isinstance(schema[key], (str, int, float)):
                text.append(f"@{key} {schema[key]}")
        return comment_lines("\n".join(text), pad)

    def _warn_unsupported(self, schema: dict[str, Any], document: Document, pointer: str) -> None:
        for keyword, message in UNSUPPORTED.items():
            if keyword in schema and (keyword, message) not in self._warned:
                self._warned.add((keyword, message))
                where = f"{document.label or ''}#{pointer}".lstrip("#") if document.label \
                    else f"#{pointer}"
                self.warnings.append(f"{where}: {message}")


def map_to_ts_type(schema: Any) -> str:
    """Type expression for a schema; any ``$ref`` shows up as the name of its target."""
    builder = TypeBuilder(Document(schema))
    return builder.type_of(schema)
