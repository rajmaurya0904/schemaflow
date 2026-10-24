"""Exceptions raised by schemaflow. All of them derive from :class:`SchemaflowError`."""

from __future__ import annotations


class SchemaflowError(Exception):
    """Base class. ``str(error)`` is a complete, human readable message.

    ``source`` is the file the problem was found in and ``pointer`` a JSON pointer
    (``/properties/age``) to the offending part of the schema, when known.
    """

    def __init__(self, message: str, source: object = None, pointer: str | None = None) -> None:
        self.message = message
        self.source = str(source) if source is not None else None
        self.pointer = pointer
        super().__init__(self._format())

    def _format(self) -> str:
        where = self.source or ""
        if self.pointer is not None:
            where = f"{where}#{self.pointer}" if where else f"#{self.pointer}"
        return f"{where}: {self.message}" if where else self.message


class LoadError(SchemaflowError):
    """A schema file is missing, unreadable, empty or not valid JSON."""


class SchemaError(SchemaflowError):
    """The schema is well-formed JSON but not a usable JSON Schema."""


class RefError(SchemaflowError):
    """A ``$ref`` cannot be resolved."""


class ConfigError(SchemaflowError):
    """The schemaflow configuration file is invalid."""
