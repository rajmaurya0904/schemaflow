"""Tests for the TypeScript text helpers."""

import pytest

from schemaflow.naming import (
    comment_lines,
    literal,
    needs_parens,
    parens,
    pascal_case,
    prop_key,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("user", "User"),
        ("user_profile", "UserProfile"),
        ("user-profile.schema", "UserProfileSchema"),
        ("userProfile", "UserProfile"),
        ("HTTPServer", "HTTPServer"),
        ("2fa", "_2fa"),
        ("", "Schema"),
        ("!!!", "Schema"),
        ("Record", "RecordType"),
        ("date", "Date" + "Type"),
    ],
)
def test_pascal_case(raw, expected):
    assert pascal_case(raw) == expected


def test_prop_key_quotes_only_when_needed():
    assert prop_key("name") == "name"
    assert prop_key("_id") == "_id"
    assert prop_key("$ref") == "$ref"
    assert prop_key("first-name") == '"first-name"'
    assert prop_key("1st") == '"1st"'
    assert prop_key("with space") == '"with space"'
    assert prop_key("é") == '"é"'


def test_literal():
    assert literal("a") == '"a"'
    assert literal('q"uote') == '"q\\"uote"'
    assert literal(3) == "3"
    assert literal(True) == "true"
    assert literal(None) == "null"
    assert literal([1]) is None
    assert literal({"a": 1}) is None


@pytest.mark.parametrize(
    ("expr", "expected"),
    [
        ("string", False),
        ("string | number", True),
        ("A & B", True),
        ("{ a: string | number; }", False),
        ("Array<string | null>", False),
        ('"a|b"', False),
        ('"say \\" | hi"', False),
        ("[string, number]", False),
    ],
)
def test_needs_parens(expr, expected):
    assert needs_parens(expr) is expected


def test_parens():
    assert parens("string | null") == "(string | null)"
    assert parens("string") == "string"


def test_comment_lines():
    assert comment_lines("Hello", "  ") == ["  /** Hello */"]
    assert comment_lines("a\nb", "") == ["/**", " * a", " * b", " */"]
    assert comment_lines("ends */ here", "") == ["/** ends *\\/ here */"]
    assert comment_lines("  \n ", "") == []
