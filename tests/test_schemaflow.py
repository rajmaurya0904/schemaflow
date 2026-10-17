"""Unit tests for schemaflow package import and namespace."""

import schemaflow


def test_package_imports() -> None:
    """Ensure the package can be imported without error."""
    assert schemaflow is not None


def test_version_attribute() -> None:
    """Ensure __version__ is defined and is a string."""
    assert hasattr(schemaflow, '__version__')
    assert isinstance(schemaflow.__version__, str)
    assert schemaflow.__version__


def test_public_interface() -> None:
    """Ensure the package exposes expected public attributes."""
    # Currently only __version__ is expected; adjust if package grows.
    expected_attrs = {'__version__', '__doc__', '__file__'}
    actual_attrs = set(dir(schemaflow))
    # Check that expected attributes are present (others may be added by Python)
    assert expected_attrs <= actual_attrs