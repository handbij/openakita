# tests/agents/cli_providers/test_types.py
import pytest
from openakita.agents.cli_providers.types import RecoverableFailure, RECOVERABLE_FAILURES


def test_recoverable_failure_enum_values():
    assert RecoverableFailure.EMPTY_TURN.value == "empty_turn"
    assert RecoverableFailure.SANDBOX_BLOCKED.value == "sandbox_blocked"
    assert RecoverableFailure.PERMISSION_DENIED.value == "permission_denied"


def test_recoverable_failures_is_frozenset():
    assert isinstance(RECOVERABLE_FAILURES, frozenset)
    assert len(RECOVERABLE_FAILURES) == 3


def test_recoverable_failure_membership():
    assert RecoverableFailure.EMPTY_TURN in RECOVERABLE_FAILURES
    assert "empty_turn" not in RECOVERABLE_FAILURES  # Must use enum, not string


def test_is_recoverable_helper():
    from openakita.agents.cli_providers.types import is_recoverable_failure

    assert is_recoverable_failure("empty_turn") is True
    assert is_recoverable_failure("sandbox_blocked") is True
    assert is_recoverable_failure("unknown_error") is False
    assert is_recoverable_failure(None) is False
