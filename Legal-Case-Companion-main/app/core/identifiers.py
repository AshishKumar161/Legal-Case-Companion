"""
Centralized identifier generation for the Legal Case Companion.

Architecture Decision (15_ARCHITECTURE_DECISION_REGISTER.md):
  - Primary keys: UUIDv7, application-generated.
  - UUIDv7 provides time-ordered identifiers with better B-tree insertion
    locality than fully random UUIDv4.

This module uses the `uuid-utils` library to provide UUIDv7 on Python 3.11+.
All application code MUST use `generate_uuid7()` from this module.
Do NOT use `uuid.uuid4()` or `uuid.uuid7()` directly.
"""

import uuid

from uuid_utils import uuid7 as _uuid7


def generate_uuid7() -> uuid.UUID:
    """Generate a UUIDv7 identifier.

    Returns a standard ``uuid.UUID`` instance with UUIDv7 semantics
    (time-ordered, sortable, application-generated).
    """
    return uuid.UUID(str(_uuid7()))
