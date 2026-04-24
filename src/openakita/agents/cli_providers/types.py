"""Type definitions for CLI providers.

Defines recoverable failure categories that trigger auto-retry with
modified instructions rather than terminal failure.
"""

from enum import Enum


class RecoverableFailure(Enum):
    """Failure types that can be recovered via auto-retry."""

    EMPTY_TURN = "empty_turn"
    SANDBOX_BLOCKED = "sandbox_blocked"
    PERMISSION_DENIED = "permission_denied"


RECOVERABLE_FAILURES: frozenset[RecoverableFailure] = frozenset(RecoverableFailure)


def is_recoverable_failure(error_message: str | None) -> bool:
    """Check if error message indicates a recoverable failure."""
    if not error_message:
        return False
    return any(rf.value in error_message for rf in RecoverableFailure)
