from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from openakita.agents.profile import AgentProfile, AgentType, ProfileStore


@pytest.mark.asyncio
async def test_cli_bridge_runs_profile_backed_agent(monkeypatch, tmp_path):
    from openakita.evolution import cli_agent_bridge as bridge

    store = ProfileStore(tmp_path / "agents")
    store.save(
        AgentProfile(
            id="claude-code-pair",
            name="Claude",
            type=AgentType.EXTERNAL_CLI,
            cli_provider_id="claude_code",
        )
    )

    class AgentStub:
        def __init__(self):
            self.cwd = None
            self.shutdown = AsyncMock()

        async def execute_task_from_message(self, message, *, cwd=None):
            self.cwd = cwd
            return {"success": True, "data": "done", "error": None}

    agent = AgentStub()

    factory = MagicMock()
    factory.create = AsyncMock(return_value=agent)

    monkeypatch.setattr(bridge, "get_profile_store", lambda: store)
    monkeypatch.setattr(bridge, "AgentFactory", lambda: factory)

    ok, output = await bridge.run_external_cli_agent(
        "claude-code",
        "fix this",
        str(tmp_path),
        timeout_seconds=30,
    )

    assert ok is True
    assert output == "done"
    assert agent.cwd == str(tmp_path)
    factory.create.assert_awaited_once()
    agent.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_cli_bridge_returns_not_found_when_profile_missing(monkeypatch, tmp_path):
    from openakita.evolution import cli_agent_bridge as bridge

    store = ProfileStore(tmp_path / "agents")
    monkeypatch.setattr(bridge, "get_profile_store", lambda: store)

    ok, output = await bridge.run_external_cli_agent(
        "claude-code",
        "fix this",
        str(tmp_path),
        timeout_seconds=30,
    )

    assert ok is False
    assert output == "not_found"
