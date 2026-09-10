"""Backward-compatibility facade for document_processor.

Canonical domain implementation: app.domain.documents.document_processor.
This facade preserves existing imports across legacy callers, static type checking, and tests.
"""

import sys

# Static re-exports for static type checkers (mypy, pyright)
from app.domain.documents.document_processor import *  # noqa: F403
import app.domain.documents.document_processor as _canonical

# Runtime module aliasing for monkeypatching, mock patching, and single-module identity
sys.modules[__name__] = _canonical
