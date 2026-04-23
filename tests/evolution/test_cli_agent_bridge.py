"""Tests for :mod:`openakita.evolution.cli_agent_bridge`.

Covers the self-improvement bridge's public call shape while asserting the
implementation goes through configured external CLI agent profiles instead of
raw subprocess spawning.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from openakita.agents.profile import AgentProfile, AgentType, ProfileStore
from openakita.evolution import cli_agent_bridge
from openakita.evolution.cli_agent_bridge import resolve_profile_id, run_external_cli_agent


class _AgentStub:
    def __init__(
        self,
        result: Any,
        *,
        delay_s: float = 0.0,
        execute_error: BaseException | None = None,
    ) -> None:
        self._result = result
        self._delay_s = delay_s
        self._execute_error = execute_error
        self.messages: list[str] = []
        self.cwd: str | None = None
        self.cancel = AsyncMock()
        self.shutdown = AsyncMock()

    async def execute_task_from_message(self, message: str, *, cwd: str | None = None) -> Any:
        self.messages.append(message)
        self.cwd = cwd
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        if self._execute_error is not None:
            raise self._execute_error
        return self._result


def _store_with_profile(tmp_path, profile_id: str = "claude-code-pair") -> ProfileStore:
    store = ProfileStore(tmp_path / "agents")
    store.save(
        AgentProfile(
            id=profile_id,
            name="External CLI",
            type=AgentType.EXTERNAL_CLI,
            cli_provider_id="claude_code",
        )
    )
    return store


def _patch_factory(monkeypatch: pytest.MonkeyPatch, agent: _AgentStub) -> MagicMock:
    factory = MagicMock()
    factory.create = AsyncMock(return_value=agent)
    monkeypatch.setattr(cli_agent_bridge, "AgentFactory", lambda: factory)
    return factory


def _patch_failing_factory(monkeypatch: pytest.MonkeyPatch, exc: Exception) -> MagicMock:
    factory = MagicMock()
    factory.create = AsyncMock(side_effect=exc)
    monkeypatch.setattr(cli_agent_bridge, "AgentFactory", lambda: factory)
    return factory


def test_resolve_profile_id_unknown_key() -> None:
    assert resolve_profile_id("not-a-real-agent") is None


def test_resolve_profile_id_known_keys() -> None:
    assert resolve_profile_id("claude-code") == "claude-code-pair"
    assert resolve_profile_id("codex") == "codex-writer"
    assert resolve_profile_id("goose") == "local-goose"


def test_profile_keys_set() -> None:
    assert set(cli_agent_bridge._AGENT_PROFILE.keys()) == {"claude-code", "codex", "goose"}


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
async def test_missing_profile_returns_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    store = ProfileStore(tmp_path / "agents")
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="whatever",
        working_directory="/tmp",
    )

    assert success is False
    assert output == "not_found"


@pytest.mark.asyncio
async def test_successful_dict_result_returns_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub({"success": True, "data": "finished", "error": None})
    factory = _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="describe",
        working_directory="/tmp/project",
    )

    assert success is True
    assert output == "finished"
    assert agent.messages == ["describe"]
    assert agent.cwd == "/tmp/project"
    factory.create.assert_awaited_once_with(store.get("claude-code-pair"))
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_error_after_success_does_not_replace_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub({"success": True, "data": "finished", "error": None})
    agent.shutdown = AsyncMock(side_effect=RuntimeError("shutdown boom"))
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="describe",
        working_directory="/tmp/project",
    )

    assert success is True
    assert output == "finished"
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_factory_create_error_returns_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    factory = _patch_failing_factory(monkeypatch, ValueError("missing provider"))

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
    )

    assert success is False
    assert output == "create_error:ValueError:missing provider"
    factory.create.assert_awaited_once_with(store.get("claude-code-pair"))


@pytest.mark.asyncio
async def test_failed_dict_result_returns_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub({"success": False, "data": "", "error": "boom"})
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
    )

    assert success is False
    assert output == "boom"
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_error_returns_diagnostic_and_shuts_down(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub(None, execute_error=RuntimeError("boom"))
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
    )

    assert success is False
    assert output == "execute_error:RuntimeError:boom"
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_shutdown_error_after_execute_error_does_not_replace_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub(None, execute_error=RuntimeError("boom"))
    agent.shutdown = AsyncMock(side_effect=RuntimeError("shutdown boom"))
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
    )

    assert success is False
    assert output == "execute_error:RuntimeError:boom"
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_cancelled_error_propagates_and_attempts_shutdown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub(None, execute_error=asyncio.CancelledError())
    _patch_factory(monkeypatch, agent)

    with pytest.raises(asyncio.CancelledError):
        await run_external_cli_agent(
            agent_type="claude-code",
            task_description="task",
            working_directory="/tmp",
        )

    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_dict_result_returns_data_when_error_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub({"success": False, "data": "useful output", "error": None})
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
    )

    assert success is False
    assert output == "useful output"
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_object_result_shape_is_supported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub(SimpleNamespace(success=True, data="object-data", error=None))
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
    )

    assert success is True
    assert output == "object-data"


@pytest.mark.asyncio
async def test_failed_object_result_returns_data_when_error_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub(SimpleNamespace(success=False, data="object diagnostic", error=None))
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
    )

    assert success is False
    assert output == "object diagnostic"
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_extra_args_are_folded_into_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub({"success": True, "data": "", "error": None})
    _patch_factory(monkeypatch, agent)

    await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
        extra_args=["--yes", "-p"],
    )

    assert agent.messages == ["--yes -p\n\ntask"]


@pytest.mark.asyncio
async def test_timeout_cancels_and_shuts_down_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub({"success": True, "data": "", "error": None}, delay_s=1.0)
    _patch_factory(monkeypatch, agent)

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="slow task",
        working_directory="/tmp",
        timeout_seconds=0.01,
    )

    assert success is False
    assert output == "timed_out"
    agent.cancel.assert_awaited_once()
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_env_and_subprocess_factory_are_ignored_for_compatibility(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    store = _store_with_profile(tmp_path)
    monkeypatch.setattr(cli_agent_bridge, "get_profile_store", lambda: store)
    agent = _AgentStub({"success": True, "data": "ok", "error": None})
    _patch_factory(monkeypatch, agent)

    async def broken_factory(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("raw subprocess factory should not be called")

    success, output = await run_external_cli_agent(
        agent_type="claude-code",
        task_description="task",
        working_directory="/tmp",
        env={"CUSTOM": "v"},
        subprocess_factory=broken_factory,
    )

    assert success is True
    assert output == "ok"
