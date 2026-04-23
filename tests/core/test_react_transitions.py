"""Tests for :mod:`openakita.core.react_transitions` and
:mod:`openakita.core.transition_helpers`.

Covers:
- ``ReActLoopState`` counters, accumulation/reset, budget predicates
- ``evaluate_transition`` priority ordering
  (cancel > budget > tool follow-up > max_output > pending-todo > nudge > complete)
- ``build_continuation_nudge`` and ``build_max_tokens_recovery_prompt``
- ``transition_helpers.is_in_progress_promise`` pattern classification
- ``transition_helpers.build_*_prompt`` builders
"""

from __future__ import annotations

import pytest

from openakita.core.react_transitions import (
    ReActLoopState,
    ReActTerminalStatus,
    ReActTransitionReason,
    build_continuation_nudge,
    build_max_tokens_recovery_prompt,
    detect_repeated_output,
    evaluate_transition,
    should_nudge_continuation,
)
from openakita.core.transition_helpers import (
    build_force_tool_call_prompt,
    build_max_tokens_continuation_prompt,
    build_pending_todo_prompt,
    is_in_progress_promise,
)

# ── ReActLoopState ──


def test_loop_state_defaults() -> None:
    state = ReActLoopState()
    assert state.max_output_recovery_count == 0
    assert state.continuation_nudge_count == 0
    assert state.last_output_hash == ""
    assert state.max_output_recovery_limit == 2
    assert state.continuation_nudge_max == 3
    assert state.accumulated_text_parts == []
    assert state.can_recover_max_output is True
    assert state.can_nudge_continuation is True


def test_loop_state_budget_exhaustion() -> None:
    state = ReActLoopState(
        max_output_recovery_count=2,
        continuation_nudge_count=3,
        max_output_recovery_limit=2,
        continuation_nudge_max=3,
    )
    assert state.can_recover_max_output is False
    assert state.can_nudge_continuation is False


def test_loop_state_text_accumulation_and_reset() -> None:
    state = ReActLoopState()
    assert state.reset_text_accumulation() == ""
    state.accumulated_text_parts.extend(["Hello, ", "world", "!"])
    joined = state.reset_text_accumulation()
    assert joined == "Hello, world!"
    assert state.accumulated_text_parts == []


# ── detect_repeated_output ──


def test_detect_repeated_output_no_prior_hash() -> None:
    assert detect_repeated_output("something", "") is False


def test_detect_repeated_output_mismatch() -> None:
    from openakita.core.react_transitions import _hash_output

    first = _hash_output("foo")
    assert detect_repeated_output("bar", first) is False


def test_detect_repeated_output_match() -> None:
    from openakita.core.react_transitions import _hash_output

    h = _hash_output("same text")
    assert detect_repeated_output("same text", h) is True


# ── should_nudge_continuation ──


@pytest.mark.parametrize(
    "response",
    ["done", "done.", "Done!", "complete", "finished.", "ready", "task complete"],
)
def test_should_nudge_on_premature_completion(response: str) -> None:
    state = ReActLoopState()
    assert should_nudge_continuation(response, has_tools=False, loop_state=state) is True


def test_should_not_nudge_when_tools_present() -> None:
    state = ReActLoopState()
    assert should_nudge_continuation("done", has_tools=True, loop_state=state) is False


def test_should_not_nudge_when_conversational() -> None:
    state = ReActLoopState()
    assert (
        should_nudge_continuation(
            "Let me know if you have any other questions!",
            has_tools=False,
            loop_state=state,
        )
        is False
    )


def test_should_not_nudge_when_budget_exhausted() -> None:
    state = ReActLoopState(continuation_nudge_count=3, continuation_nudge_max=3)
    assert should_nudge_continuation("done", has_tools=False, loop_state=state) is False


# ── evaluate_transition priority order ──


def test_evaluate_transition_cancellation_takes_priority() -> None:
    state = ReActLoopState()
    decision = evaluate_transition(
        stop_reason="cancelled",
        response="partial",
        has_tools=True,
        has_pending_todos=True,
        loop_state=state,
    )
    assert decision.action == "cancel"
    assert decision.reason == ReActTransitionReason.CANCELLATION
    assert decision.status == ReActTerminalStatus.CANCELLED


def test_evaluate_transition_budget_pause_before_tool_follow_up() -> None:
    state = ReActLoopState()
    decision = evaluate_transition(
        stop_reason="budget_exceeded",
        response="",
        has_tools=True,
        has_pending_todos=False,
        loop_state=state,
    )
    assert decision.action == "pause"
    assert decision.status == ReActTerminalStatus.PAUSED


def test_evaluate_transition_tool_follow_up() -> None:
    state = ReActLoopState()
    decision = evaluate_transition(
        stop_reason="tool_calls",
        response="calling tool",
        has_tools=True,
        has_pending_todos=False,
        loop_state=state,
    )
    assert decision.action == "continue"
    assert decision.reason == ReActTransitionReason.TOOL_FOLLOW_UP


def test_evaluate_transition_max_output_recovery_increments() -> None:
    state = ReActLoopState(max_output_recovery_count=0, max_output_recovery_limit=2)
    decision = evaluate_transition(
        stop_reason="max_tokens",
        response="truncated...",
        has_tools=False,
        has_pending_todos=False,
        loop_state=state,
    )
    assert decision.action == "recover"
    assert state.max_output_recovery_count == 1


def test_evaluate_transition_max_output_recovery_exhausted_blocks() -> None:
    state = ReActLoopState(max_output_recovery_count=2, max_output_recovery_limit=2)
    decision = evaluate_transition(
        stop_reason="max_tokens",
        response="truncated...",
        has_tools=False,
        has_pending_todos=False,
        loop_state=state,
    )
    assert decision.action == "block"
    assert decision.status == ReActTerminalStatus.BLOCKED


def test_evaluate_transition_pending_todos_nudge() -> None:
    state = ReActLoopState()
    decision = evaluate_transition(
        stop_reason="stop",
        response="All clear.",
        has_tools=False,
        has_pending_todos=True,
        loop_state=state,
    )
    assert decision.action == "nudge"
    assert decision.reason == ReActTransitionReason.CONTINUATION_NUDGE


def test_evaluate_transition_premature_completion_nudge() -> None:
    state = ReActLoopState()
    decision = evaluate_transition(
        stop_reason="stop",
        response="done",
        has_tools=False,
        has_pending_todos=False,
        loop_state=state,
    )
    assert decision.action == "nudge"
    assert state.continuation_nudge_count == 1


def test_evaluate_transition_default_completed() -> None:
    state = ReActLoopState()
    decision = evaluate_transition(
        stop_reason="stop",
        response="Here is the full plan for the project with all required steps.",
        has_tools=False,
        has_pending_todos=False,
        loop_state=state,
    )
    assert decision.action == "complete"
    assert decision.status == ReActTerminalStatus.COMPLETED


# ── builders ──


def test_build_continuation_nudge_with_pending() -> None:
    msg = build_continuation_nudge(ReActLoopState(), pending_todos=["step 2", "step 3"])
    assert "step 2" in msg and "step 3" in msg


def test_build_continuation_nudge_without_pending() -> None:
    msg = build_continuation_nudge(ReActLoopState(), pending_todos=None)
    assert "continue" in msg.lower()


def test_build_max_tokens_recovery_prompt_with_cutoff() -> None:
    msg = build_max_tokens_recovery_prompt(ReActLoopState(), cutoff_hint="the last sentence")
    assert "the last sentence" in msg


def test_build_max_tokens_recovery_prompt_default() -> None:
    msg = build_max_tokens_recovery_prompt(ReActLoopState())
    assert "truncated" in msg.lower()


# ── transition_helpers ──


@pytest.mark.parametrize(
    "text",
    [
        "正在生成报告中",
        "文件生成中",
        "稍等一下",
        "请稍候",
        "Let me execute that now",
        "I'll generate the file now",
        "I am creating the document",
    ],
)
def test_is_in_progress_promise_positive(text: str) -> None:
    assert is_in_progress_promise(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Here is the final result with all relevant details.",
        "Task completed successfully.",
    ],
)
def test_is_in_progress_promise_negative(text: str) -> None:
    assert is_in_progress_promise(text) is False


def test_is_in_progress_promise_skips_overlong_text() -> None:
    huge = "正在生成报告" * 200
    assert is_in_progress_promise(huge) is False


def test_build_force_tool_call_prompt_variants() -> None:
    plain = build_force_tool_call_prompt()
    assert "tool_calls=0" in plain

    with_hint = build_force_tool_call_prompt(pending_tool_name="run_shell", context="ctx")
    assert "run_shell" in with_hint
    assert "ctx" in with_hint


def test_build_pending_todo_prompt_variants() -> None:
    assert "pending" in build_pending_todo_prompt().lower()

    with_ctx = build_pending_todo_prompt(todo_context="- step A\n- step B")
    assert "step A" in with_ctx


def test_build_max_tokens_continuation_prompt_with_cutoff_truncates_long_snippet() -> None:
    long_hint = "x" * 500
    msg = build_max_tokens_continuation_prompt(attempt=1, limit=2, cutoff_hint=long_hint)
    # Only last 200 chars should be embedded.
    assert "x" * 200 in msg
    assert "x" * 201 not in msg


def test_build_max_tokens_continuation_prompt_no_cutoff() -> None:
    msg = build_max_tokens_continuation_prompt(attempt=1, limit=2)
    assert "断点" in msg or "continue" in msg.lower() or "截断" in msg
