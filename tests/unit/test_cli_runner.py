# tests/unit/test_cli_runner.py
from __future__ import annotations

import asyncio
import signal
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from openakita.agents.cli_runner import (
    CliRunRequest,
    DEFAULT_MAX_CONCURRENT_EXTERNAL_CLIS,
    ExitReason,
    ExternalCliLimiter,
    ProviderRunResult,
    SubprocessRunner,
)


def test_exit_reason_values():
    assert ExitReason.COMPLETED.value == "completed"
    assert ExitReason.ERROR.value == "error"
    assert ExitReason.TIMEOUT.value == "timeout"
    assert ExitReason.CANCELLED.value == "cancelled"


def test_cli_run_request_is_frozen():
    req = CliRunRequest(
        message="hi",
        resume_id=None,
        profile=None,
        cwd=Path("/tmp"),
        cancelled=asyncio.Event(),
        session=None,
        system_prompt_extra="",
    )
    with pytest.raises(Exception):
        req.message = "other"


def test_provider_run_result_is_frozen():
    r = ProviderRunResult(
        final_text="ok", tools_used=[], artifacts=[],
        session_id=None, input_tokens=0, output_tokens=0,
        exit_reason=ExitReason.COMPLETED, errored=False, error_message=None,
    )
    with pytest.raises(Exception):
        r.final_text = "other"


@pytest.mark.asyncio
async def test_limiter_bounds_concurrency():
    lim = ExternalCliLimiter(max_concurrent=2)
    inflight = {"n": 0, "peak": 0}

    async def worker():
        async with lim:
            inflight["n"] += 1
            inflight["peak"] = max(inflight["peak"], inflight["n"])
            await asyncio.sleep(0.01)
            inflight["n"] -= 1

    await asyncio.gather(*(worker() for _ in range(10)))
    assert inflight["peak"] == 2


@pytest.mark.asyncio
async def test_limiter_default_is_from_constant():
    lim = ExternalCliLimiter()
    assert lim._sem._value == DEFAULT_MAX_CONCURRENT_EXTERNAL_CLIS


@pytest.mark.asyncio
async def test_limiter_clamps_non_positive_to_one():
    lim = ExternalCliLimiter(max_concurrent=0)
    assert lim._sem._value == 1


class _FakeProc:
    """Drop-in substitute for asyncio.subprocess.Process."""

    def __init__(self, survive_signals: int = 0):
        self.returncode: int | None = None
        self.signals_sent: list[str] = []
        self._survive = survive_signals

    def send_signal(self, sig):
        self.signals_sent.append("SIGINT" if sig == signal.SIGINT else str(sig))
        self._tick()

    def terminate(self):
        self.signals_sent.append("SIGTERM")
        self._tick()

    def kill(self):
        self.signals_sent.append("SIGKILL")
        self.returncode = -9

    def _tick(self):
        if len(self.signals_sent) > self._survive:
            self.returncode = -1

    async def wait(self):
        while self.returncode is None:
            await asyncio.sleep(0.01)
        return self.returncode


@pytest.mark.asyncio
async def test_terminate_and_wait_exits_after_sigint(monkeypatch):
    monkeypatch.setattr("openakita.agents.cli_runner._SIGINT_GRACE_S", 0.05)
    monkeypatch.setattr("openakita.agents.cli_runner._SIGTERM_GRACE_S", 0.05)
    monkeypatch.setattr("openakita.agents.cli_runner._SIGKILL_GRACE_S", 0.05)
    adapter = MagicMock()
    runner = SubprocessRunner(adapter, ExternalCliLimiter(1))
    fake = _FakeProc(survive_signals=0)
    runner._track_proc(fake)
    await runner.terminate_and_wait()
    assert fake.signals_sent == ["SIGINT"]
    assert fake.returncode is not None


@pytest.mark.asyncio
async def test_terminate_and_wait_escalates_to_sigkill(monkeypatch):
    monkeypatch.setattr("openakita.agents.cli_runner._SIGINT_GRACE_S", 0.05)
    monkeypatch.setattr("openakita.agents.cli_runner._SIGTERM_GRACE_S", 0.05)
    monkeypatch.setattr("openakita.agents.cli_runner._SIGKILL_GRACE_S", 0.1)
    adapter = MagicMock()
    runner = SubprocessRunner(adapter, ExternalCliLimiter(1))
    fake = _FakeProc(survive_signals=2)
    runner._track_proc(fake)
    await runner.terminate_and_wait()
    assert fake.signals_sent == ["SIGINT", "SIGTERM", "SIGKILL"]


@pytest.mark.asyncio
async def test_terminate_and_wait_idempotent_on_finished_proc():
    adapter = MagicMock()
    runner = SubprocessRunner(adapter, ExternalCliLimiter(1))
    fake = _FakeProc(survive_signals=0)
    fake.returncode = 0
    runner._track_proc(fake)
    await runner.terminate_and_wait()
    assert fake.signals_sent == []


@pytest.mark.asyncio
async def test_terminate_and_wait_no_proc_is_noop():
    adapter = MagicMock()
    runner = SubprocessRunner(adapter, ExternalCliLimiter(1))
    await runner.terminate_and_wait()
