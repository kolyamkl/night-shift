"""Deprecated import path: address widening lives in app.redaction.addresses.

Kept for scripts/readme_numbers.py; remove once it imports app.redaction.addresses.
"""

from app.redaction.addresses import expand

__all__ = ["expand"]
