"""Backward-compatibility facade for presence_service.

Canonical domain implementation: app.domain.consultations.presence_service.
This facade preserves existing imports across legacy callers, static type checking, and tests.
"""

import sys

# Static re-exports for static type checkers (mypy, pyright)
from app.domain.consultations.presence_service import *  # noqa: F403
import app.domain.consultations.presence_service as _canonical

# Runtime module aliasing for monkeypatching, mock patching, and single-module identity
sys.modules[__name__] = _canonical
