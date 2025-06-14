from __future__ import annotations

"""Utility validator for simple string equality."""

def string_field_validator(value1: object, value2: object) -> bool:
    """Return True if values are identical when cast to string."""
    return str(value1) == str(value2)
