"""Small text helpers for emitting TypeScript."""

from __future__ import annotations

import json
import re
from typing import Any

# Names that would shadow globals the generated code relies on.
RESERVED_TYPE_NAMES = {
    "Array",
    "Record",
    "Object",
    "String",
    "Number",
    "Boolean",
    "Symbol",
    "BigInt",
    "Date",
    "Function",
    "Promise",
    "Partial",
    "Readonly",
}

_IDENTIFIER = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_WORDS = re.compile(r"[A-Za-z0-9]+")


def pascal_case(text: str) -> str:
    """``user_profile`` / ``user-profile`` / ``userProfile`` -> ``UserProfile``."""
    words = _WORDS.findall(text)
    name = "".join(word[0].upper() + word[1:] for word in words)
    if not name:
        return "Schema"
    if name[0].isdigit():
        name = "_" + name
    return name + "Type" if name in RESERVED_TYPE_NAMES else name


def is_identifier(text: str) -> bool:
    return bool(_IDENTIFIER.match(text))


def prop_key(name: str) -> str:
    """A property name, quoted only when it is not a valid identifier."""
    return name if is_identifier(name) else json.dumps(name, ensure_ascii=False)


def literal(value: Any) -> str | None:
    """TypeScript literal type for a JSON scalar, ``None`` for arrays and objects."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return None


def needs_parens(expr: str) -> bool:
    """True if ``expr`` has a ``|`` or ``&`` outside brackets and string literals."""
    depth = 0
    in_string = False
    skip = False
    for char in expr:
        if skip:
            skip = False
        elif in_string:
            if char == "\\":
                skip = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "({[<":
            depth += 1
        elif char in ")}]>":
            depth -= 1
        elif depth == 0 and char in "|&":
            return True
    return False


def parens(expr: str) -> str:
    return f"({expr})" if needs_parens(expr) else expr


def comment_lines(text: str, indent: str) -> list[str]:
    """A ``/** ... */`` block (one line when it fits) for ``text``."""
    lines = [line.rstrip() for line in text.replace("*/", "*\\/").strip().splitlines()]
    if not lines:
        return []
    if len(lines) == 1:
        return [f"{indent}/** {lines[0]} */"]
    body = [f"{indent} * {line}".rstrip() for line in lines]
    return [f"{indent}/**", *body, f"{indent} */"]
