"""Smoke test: package imports cleanly. Replace/extend as modules land."""

import schemaflow


def test_version_is_set() -> None:
    assert schemaflow.__version__
