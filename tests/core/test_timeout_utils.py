"""Tests for :mod:`openakita.core.timeout_utils`.

Covers:
- ``is_meaningful_progress`` classification (empty/heartbeat/real work)
- ``check_progress_timeout`` progress and hard-timeout paths
- ``run_with_progress_polling`` task-completion, signature-change resets,
  timeout cancellation, and on_progress/on_timeout callbacks
"""

from __future__ import annotations

import asyncio
import itertools

import pytest

from openakita.core.timeout_utils import (
    check_progress_timeout,
    is_meaningful_progress,
    run_with_progress_polling,
)

# ── is_meaningful_progress ──


@pytest.mark.parametrize(
    "line,expected",
    [
        ("", False),
        ("   ", False),
        ("heartbeat ping", False),
        ("KEEPALIVE", False),
        ("Waiting for task to finish", False),
        ("polling subagent", False),
        ("idle check completed", False),
        ("[timestamp] 2026-04-23T10:00:00Z", False),
        ("Running tool: shell", True),
        ("Generated 3 files", True),
        ("Step 2: processing results", True),
    ],
)
def test_is_meaningful_progress(line: str, expected: bool) -> None:
    assert is_meaningful_progress(line) is expected


def test_is_meaningful_progress_custom_patterns() -> None:
    extra = [r"ignored noise"]
    assert is_meaningful_progress("ignored noise here", ignored_patterns=extra) is False
    assert is_meaningful_progress("real work done", ignored_patterns=extra) is True


# ── check_progress_timeout ──


@pytest.mark.asyncio
async def test_check_progress_timeout_no_timeouts_configured() -> None:
    timed_out, reason = await check_progress_timeout(
        last_progress_timestamp=100.0,
        session_id="s1",
        timeout_seconds=0,
        hard_timeout_seconds=0,
        now_fn=lambda: 200.0,
    )
    assert timed_out is False
    assert reason is None


@pytest.mark.asyncio
async def test_check_progress_timeout_progress_timeout() -> None:
    timed_out, reason = await check_progress_timeout(
        last_progress_timestamp=100.0,
        session_id="s1",
        timeout_seconds=30,
        hard_timeout_seconds=0,
        now_fn=lambda: 200.0,
    )
    assert timed_out is True
    assert reason == "progress_timeout"


@pytest.mark.asyncio
async def test_check_progress_timeout_within_progress_budget() -> None:
    timed_out, reason = await check_progress_timeout(
        last_progress_timestamp=100.0,
        session_id="s1",
        timeout_seconds=300,
        hard_timeout_seconds=0,
        now_fn=lambda: 150.0,
    )
    assert timed_out is False
    assert reason is None


@pytest.mark.asyncio
async def test_check_progress_timeout_hard_cap_overrides_active_progress() -> None:
    timed_out, reason = await check_progress_timeout(
        last_progress_timestamp=199.0,
        session_id="s1",
        timeout_seconds=300,
        hard_timeout_seconds=60,
        start_time=100.0,
        now_fn=lambda: 200.0,
    )
    assert timed_out is True
    assert reason == "hard_timeout"


@pytest.mark.asyncio
async def test_check_progress_timeout_hard_cap_disabled_when_zero() -> None:
    timed_out, reason = await check_progress_timeout(
        last_progress_timestamp=199.0,
        session_id="s1",
        timeout_seconds=300,
        hard_timeout_seconds=0,
        start_time=100.0,
        now_fn=lambda: 200.0,
    )
    assert timed_out is False
    assert reason is None


# ── run_with_progress_polling ──


@pytest.mark.asyncio
async def test_run_with_progress_polling_completes() -> None:
    async def work() -> str:
        await asyncio.sleep(0.05)
        return "done"

    task = asyncio.create_task(work())
    result = await run_with_progress_polling(
        task,
        progress_timeout_seconds=5,
        hard_timeout_seconds=0,
        check_interval=0.01,
        session_id="test",
    )
    assert result == "done"


@pytest.mark.asyncio
async def test_run_with_progress_polling_signature_resets_progress() -> None:
    counter = itertools.count()
    observed: list[int] = []

    def sig() -> int:
        # Advances every poll — simulates agent iteration progress.
        return next(counter)

    async def work() -> str:
        await asyncio.sleep(0.2)
        return "ok"

    task = asyncio.create_task(work())
    result = await run_with_progress_polling(
        task,
        progress_timeout_seconds=1,
        hard_timeout_seconds=0,
        check_interval=0.02,
        session_id="test",
        get_progress_signature=sig,
        on_progress=observed.append,
    )
    assert result == "ok"
    assert len(observed) >= 2


@pytest.mark.asyncio
async def test_run_with_progress_polling_times_out_when_idle() -> None:
    calls: list[str] = []

    async def never_done() -> str:
        await asyncio.sleep(10)
        return "unreachable"

    task = asyncio.create_task(never_done())

    def on_timeout(reason: str) -> None:
        calls.append(reason)

    with pytest.raises(asyncio.TimeoutError):
        await run_with_progress_polling(
            task,
            progress_timeout_seconds=1,
            hard_timeout_seconds=0,
            check_interval=0.05,
            session_id="idle",
            get_progress_signature=lambda: 42,
            on_timeout=on_timeout,
        )
    assert calls == ["progress_timeout"]
    assert task.cancelled() or task.done()


@pytest.mark.asyncio
async def test_run_with_progress_polling_hard_timeout() -> None:
    counter = itertools.count()
    observed_reasons: list[str] = []

    async def never_done() -> str:
        await asyncio.sleep(10)
        return "unreachable"

    task = asyncio.create_task(never_done())

    with pytest.raises(asyncio.TimeoutError):
        await run_with_progress_polling(
            task,
            progress_timeout_seconds=60,
            hard_timeout_seconds=1,
            check_interval=0.05,
            session_id="hard",
            get_progress_signature=lambda: next(counter),
            on_timeout=observed_reasons.append,
        )
    assert observed_reasons == ["hard_timeout"]


@pytest.mark.asyncio
async def test_run_with_progress_polling_signature_callback_failure_is_tolerated() -> None:
    async def work() -> str:
        await asyncio.sleep(0.05)
        return "ok"

    def bad_sig() -> int:
        raise RuntimeError("boom")

    task = asyncio.create_task(work())
    result = await run_with_progress_polling(
        task,
        progress_timeout_seconds=2,
        hard_timeout_seconds=0,
        check_interval=0.01,
        session_id="bad",
        get_progress_signature=bad_sig,
    )
    assert result == "ok"
