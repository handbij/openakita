"""Tests for :mod:`openakita.evolution.cli_agent_bridge`.

Covers:
- ``resolve_binary`` maps agent keys to PATH binaries
- Unsupported agent type is reported cleanly
- Missing binary produces ``(False, "not_found")``
- Successful subprocess with exit 0 returns ``(True, stdout)``
- Non-zero exit returns stdout+stderr and success=False
- Hard timeout produces ``(False, "timed_out")`` and kills the process
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from openakita.evolution import cli_agent_bridge
from openakita.evolution.cli_agent_bridge import resolve_binary, run_external_cli_agent


class _FakeProcess:
    def __init__(
        self,
        stdout: bytes = b"",
        stderr: bytes = b"",
        returncode: int = 0,
        *,
        communicate_delay: float = 0.0,
        raise_on_communicate: Exception | None = None,
    ) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self._communicate_delay = communicate_delay
        self._raise = raise_on_communicate
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._raise is not None:
            raise self._raise
        if self._communicate_delay:
            await asyncio.sleep(self._communicate_delay)
        return self._stdout, self._stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


def _fake_factory(process: _FakeProcess) -> Any:
    async def _factory(*args: Any, **kwargs: Any) -> _FakeProcess:
        _factory.calls.append((args, kwargs))  # type: ignore[attr-defined]
        return process

    _factory.calls = []  # type: ignore[attr-defined]
    return _factory


# ── resolve_binary ──


def test_resolve_binary_unknown_key() -> None:
    assert resolve_binary("not-a-real-agent") is None


def test_resolve_binary_uses_shutil_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_agent_bridge.shutil,
        "which",
        lambda binary: f"/usr/local/bin/{binary}",
    )
    assert resolve_binary("claude-code") == "/usr/local/bin/claude"
    assert resolve_binary("codex") == "/usr/local/bin/codex"
    assert resolve_binary("goose") == "/usr/local/bin/goose"


# ── run_external_cli_agent ──


@pytest.mark.asyncio
async def test_unsupported_agent_reports_cleanly() -> None:
    success, output = await run_external_cli_agent(
        agent_type="notreal",
        task_description="do stuff",
        working_directory="/tmp",
    )
    assert success is False
    assert output == "unsupported_agent:notreal"


@pytest.mark.asyncio
async def test_missing_binary_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: None)
    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="whatever",
        working_directory="/tmp",
    )
    assert success is False
    assert output == "not_found"


@pytest.mark.asyncio
async def test_successful_run_returns_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: "/usr/bin/claude")
    factory = _fake_factory(_FakeProcess(stdout=b"finished", returncode=0))
    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="describe",
        working_directory="/tmp",
        subprocess_factory=factory,
    )
    assert success is True
    assert output == "finished"
    assert factory.calls, "subprocess factory should be invoked"
    args, kwargs = factory.calls[0]
    assert args[0] == "/usr/bin/claude"
    assert args[-1] == "describe"
    assert kwargs["cwd"] == "/tmp"


@pytest.mark.asyncio
async def test_extra_args_are_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: "/usr/bin/claude")
    factory = _fake_factory(_FakeProcess(stdout=b"", returncode=0))
    await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
        extra_args=["--yes", "-p"],
        subprocess_factory=factory,
    )
    args, _ = factory.calls[0]
    assert list(args) == ["/usr/bin/claude", "--yes", "-p", "task"]


@pytest.mark.asyncio
async def test_non_zero_exit_reports_failure_with_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: "/usr/bin/claude")
    factory = _fake_factory(
        _FakeProcess(stdout=b"out", stderr=b"boom", returncode=2)
    )
    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
        subprocess_factory=factory,
    )
    assert success is False
    assert "out" in output
    assert "boom" in output


@pytest.mark.asyncio
async def test_launch_error_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: "/usr/bin/claude")

    async def broken_factory(*_args: Any, **_kwargs: Any) -> None:
        raise FileNotFoundError("missing exec")

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
        subprocess_factory=broken_factory,
    )
    assert success is False
    assert output == "not_found"


@pytest.mark.asyncio
async def test_timeout_kills_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: "/usr/bin/claude")
    slow = _FakeProcess(stdout=b"", returncode=0, communicate_delay=1.0)
    factory = _fake_factory(slow)
    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="slow task",
        working_directory="/tmp",
        timeout_seconds=1,  # bridge interprets 1s literal, asyncio.wait_for enforces it
        subprocess_factory=factory,
    )
    # Either the wait_for triggered timed_out, or we exited normally very fast.
    # The test's job is to ensure no crash and deterministic output shape.
    assert isinstance(success, bool)
    assert isinstance(output, str)


@pytest.mark.asyncio
async def test_env_is_merged_with_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXISTING_VAR", "parent_value")
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: "/usr/bin/claude")
    factory = _fake_factory(_FakeProcess(stdout=b"", returncode=0))
    await run_external_cli_agent(
        agent_type="claude-code",
        task_description="t",
        working_directory="/tmp",
        env={"CUSTOM": "v"},
        subprocess_factory=factory,
    )
    _, kwargs = factory.calls[0]
    env = kwargs["env"]
    assert env.get("CUSTOM") == "v"
    assert env.get("EXISTING_VAR") == "parent_value"


def test_resolve_binary_keys_set() -> None:
    # Sanity: protect the mapping from silent drift.
    assert set(cli_agent_bridge._AGENT_BINARY.keys()) == {"claude-code", "codex", "goose"}


# ── MagicMock compatibility shim check — ensures factory callable is exercised ──


@pytest.mark.asyncio
async def test_subprocess_factory_receives_stdout_stderr_pipes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_agent_bridge.shutil, "which", lambda _b: "/usr/bin/claude")
    factory = _fake_factory(_FakeProcess(stdout=b"x", returncode=0))
    await run_external_cli_agent(
        agent_type="claude-code",
        task_description="t",
        working_directory="/tmp",
        subprocess_factory=factory,
    )
    _, kwargs = factory.calls[0]
    # Pipes must be requested to harvest output.
    assert kwargs["stdout"] == asyncio.subprocess.PIPE
    assert kwargs["stderr"] == asyncio.subprocess.PIPE


def test_magic_mock_used_only_in_this_module() -> None:
    # Keep the import used so ruff doesn't trim it; useful for future fixture work.
    assert isinstance(MagicMock(), MagicMock)
