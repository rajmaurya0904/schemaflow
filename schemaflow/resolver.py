"""Resolve ``$ref`` pointers inside one schema file or across local files."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .errors import LoadError, RefError
from .loader import load_json


@dataclass(eq=False)
class Document:
    """A parsed schema file. ``path`` is ``None`` for schemas passed in as Python data."""

    root: Any
    path: Path | None = None

    @property
    def label(self) -> str | None:
        return str(self.path) if self.path else None

    @property
    def key(self) -> str:
        return str(self.path) if self.path else "<root>"


@dataclass
class Target:
    """What a reference points at: the schema, the document it lives in and its pointer."""

    document: Document
    schema: Any
    pointer: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.document.key, self.pointer)


def split_pointer(pointer: str) -> list[str]:
    """``/a~1b/c`` -> ``["a/b", "c"]`` (RFC 6901, plus percent-decoding)."""
    if not pointer:
        return []
    return [unquote(part).replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]


def find_anchor(node: Any, name: str) -> tuple[Any, str] | None:
    """Locate a subschema declaring ``$anchor: name`` (or ``$id: "#name"``)."""
    stack: list[tuple[Any, str]] = [(node, "")]
    while stack:
        current, pointer = stack.pop()
        if isinstance(current, dict):
            if current.get("$anchor") == name or current.get("$id") == f"#{name}":
                return current, pointer
            for key, value in current.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                stack.append((value, f"{pointer}/{escaped}"))
        elif isinstance(current, list):
            for index, value in enumerate(current):
                stack.append((value, f"{pointer}/{index}"))
    return None


@dataclass
class Resolver:
    """Resolves references relative to the document that contains them."""

    root: Document
    _cache: dict[Path, Document] = field(default_factory=dict)

    def resolve(self, ref: Any, document: Document, pointer: str = "") -> Target:
        if not isinstance(ref, str):
            raise RefError("$ref must be a string", document.label, pointer)
        file_part, _, fragment = ref.partition("#")
        if "://" in file_part:
            raise RefError(
                f"remote reference {ref!r} is not supported (only local files)",
                document.label,
                pointer,
            )
        target_doc = document
        if file_part:
            target_doc = self._document_for(file_part, document, ref, pointer)
        if fragment and not fragment.startswith("/"):
            found = find_anchor(target_doc.root, fragment)
            if not found:
                raise RefError(f"cannot resolve {ref!r}: no anchor {fragment!r}",
                               document.label, pointer)
            return Target(target_doc, found[0], found[1])
        node = target_doc.root
        for token in split_pointer(fragment):
            if isinstance(node, dict) and token in node:
                node = node[token]
            elif isinstance(node, list) and token.isdigit() and int(token) < len(node):
                node = node[int(token)]
            else:
                raise RefError(
                    f"cannot resolve {ref!r}: {token!r} not found",
                    document.label,
                    pointer,
                )
        return Target(target_doc, node, fragment)

    def _document_for(self, file_part: str, document: Document, ref: str, pointer: str) -> Document:
        base = document.path.parent if document.path else None
        if base is None:
            raise RefError(
                f"cannot resolve file reference {ref!r} for a schema that was not read from a file",
                document.label,
                pointer,
            )
        path = (base / unquote(file_part)).resolve()
        if self.root.path is not None and path == self.root.path:
            return self.root
        if path not in self._cache:
            try:
                self._cache[path] = Document(load_json(path), path)
            except LoadError as exc:
                raise RefError(
                    f"cannot resolve {ref!r}: {exc.message}", document.label, pointer
                ) from None
        return self._cache[path]
