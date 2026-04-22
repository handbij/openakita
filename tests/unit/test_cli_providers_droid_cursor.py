from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from openakita.agents.cli_providers import PROVIDERS
from openakita.agents.cli_detector import CliProviderId
from openakita.agents.cli_runner import CliRunRequest, ExitReason, ProviderRunResult
from openakita.agents.profile import AgentProfile, AgentType, CliPermissionMode


def _profile(provider_id, permission=CliPermissionMode.PLAN) -> AgentProfile:
    return AgentProfile(
        id=f"{provider_id.value}-agent",
        name=f"{provider_id.value} agent",
        type=AgentType.EXTERNAL_CLI,
        cli_provider_id=provider_id,
        cli_permission_mode=permission,
    )


def _request(profile, *, cwd=Path("/tmp"), resume_id=None):
    return CliRunRequest(
        message="Build a CLI",
        resume_id=resume_id,
        profile=profile,
        cwd=cwd,
        cancelled=asyncio.Event(),
        session=None,
        system_prompt_extra="",
    )


# --- Droid --------------------------------------------------------------------

def test_droid_registered():
    assert CliProviderId.DROID in PROVIDERS


def test_droid_build_argv_base():
    from openakita.agents.cli_providers import droid

    with patch.object(droid, "_resolve_binary", return_value="/usr/bin/droid"):
        argv = PROVIDERS[CliProviderId.DROID].build_argv(_request(_profile(CliProviderId.DROID)))

    assert argv[0] == "/usr/bin/droid"
    assert "run" in argv
    assert "--output" in argv
    assert argv[argv.index("--output") + 1] == "jsonl"
    assert argv[-1] == "Build a CLI"


def test_droid_write_mode_adds_autoexec():
    from openakita.agents.cli_providers import droid

    profile = _profile(CliProviderId.DROID, CliPermissionMode.WRITE)
    with patch.object(droid, "_resolve_binary", return_value="/usr/bin/droid"):
        argv = PROVIDERS[CliProviderId.DROID].build_argv(_request(profile))

    assert "--auto-exec" in argv


def test_droid_resume():
    from openakita.agents.cli_providers import droid

    with patch.object(droid, "_resolve_binary", return_value="/usr/bin/droid"):
        argv = PROVIDERS[CliProviderId.DROID].build_argv(
            _request(_profile(CliProviderId.DROID), resume_id="droid-s5")
        )

    assert "--session-id" in argv
    assert argv[argv.index("--session-id") + 1] == "droid-s5"


def test_droid_session_root():
    from openakita.agents.cli_providers import droid

    assert droid.SESSION_ROOT == Path.home() / ".factory" / "sessions"


@pytest.mark.asyncio
async def test_droid_run_end_to_end(tmp_path):
    from openakita.agents.cli_providers import droid

    events = [
        {"event": "session.created", "session_id": "droid-sA"},
        {"event": "message.delta", "text": "Working... "},
        {"event": "tool.invoked", "tool": "write_file"},
        {"event": "message.delta", "text": "done."},
        {"event": "run.completed", "usage": {"input_tokens": 6, "output_tokens": 2}},
    ]
    script = "\n".join("echo " + json.dumps(json.dumps(e)) for e in events)
    argv = ["sh", "-c", script]

    result = await droid.PROVIDER.run(
        _request(_profile(CliProviderId.DROID), cwd=tmp_path),
        argv, env={}, on_spawn=lambda _: None,
    )
    assert result.session_id == "droid-sA"
    assert result.final_text == "Working... done."
    assert result.tools_used == ["write_file"]
    assert result.exit_reason == ExitReason.COMPLETED


# --- Cursor -------------------------------------------------------------------

def test_cursor_registered():
    assert CliProviderId.CURSOR in PROVIDERS


def test_cursor_build_argv_base():
    from openakita.agents.cli_providers import cursor

    with patch.object(cursor, "_resolve_binary", return_value="/usr/bin/cursor-agent"):
        argv = PROVIDERS[CliProviderId.CURSOR].build_argv(_request(_profile(CliProviderId.CURSOR)))

    assert argv[0] == "/usr/bin/cursor-agent"
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert argv[-1] == "Build a CLI"


def test_cursor_write_mode_adds_force():
    from openakita.agents.cli_providers import cursor

    profile = _profile(CliProviderId.CURSOR, CliPermissionMode.WRITE)
    with patch.object(cursor, "_resolve_binary", return_value="/usr/bin/cursor-agent"):
        argv = PROVIDERS[CliProviderId.CURSOR].build_argv(_request(profile))

    assert "--force" in argv


def test_cursor_resume():
    from openakita.agents.cli_providers import cursor

    with patch.object(cursor, "_resolve_binary", return_value="/usr/bin/cursor-agent"):
        argv = PROVIDERS[CliProviderId.CURSOR].build_argv(
            _request(_profile(CliProviderId.CURSOR), resume_id="cursor-s4")
        )

    assert "--resume" in argv
    assert argv[argv.index("--resume") + 1] == "cursor-s4"


def test_cursor_session_root():
    from openakita.agents.cli_providers import cursor

    assert cursor.SESSION_ROOT == Path.home() / ".cursor" / "sessions"


@pytest.mark.asyncio
async def test_cursor_run_end_to_end(tmp_path):
    from openakita.agents.cli_providers import cursor

    events = [
        {"type": "session_start", "sessionId": "cursor-sB"},
        {"type": "assistant", "text": "Building"},
        {"type": "tool_use", "name": "edit"},
        {"type": "done", "usage": {"input": 5, "output": 1}},
    ]
    script = "\n".join("echo " + json.dumps(json.dumps(e)) for e in events)
    argv = ["sh", "-c", script]

    result = await cursor.PROVIDER.run(
        _request(_profile(CliProviderId.CURSOR), cwd=tmp_path),
        argv, env={}, on_spawn=lambda _: None,
    )
    assert result.session_id == "cursor-sB"
    assert result.final_text == "Building"
    assert result.tools_used == ["edit"]
    assert result.input_tokens == 5
    assert result.output_tokens == 1
    assert result.exit_reason == ExitReason.COMPLETED
