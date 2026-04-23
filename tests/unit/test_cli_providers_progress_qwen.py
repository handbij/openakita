from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from openakita.agents.cli_runner import CliRunRequest, ExitReason
from openakita.agents.profile import AgentProfile


def _request(progress):
    return CliRunRequest(
        message="hello",
        resume_id=None,
        profile=AgentProfile(id="p", name="P"),
        cwd=Path.cwd(),
        cancelled=asyncio.Event(),
        session=None,
        system_prompt_extra="",
        on_progress=progress,
    )


@pytest.mark.asyncio
async def test_qwen_provider_emits_progress(monkeypatch):
    from openakita.agents.cli_providers.qwen import PROVIDER

    events = []
    stderr_callbacks = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"delta","text":"Working"}\n'
        yield b'{"type":"tool","name":"Edit"}\n'
        yield b'{"type":"final","usage":{"prompt_tokens":1,"completion_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.qwen.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(_request(progress), ["qwen"], {}, on_spawn=lambda proc: None)

    assert result.final_text == "Working"
    assert ("assistant_text", {"text": "Working"}) in events
    assert ("tool_use", {"tool_name": "Edit"}) in events
    assert len(stderr_callbacks) == 1
    assert callable(stderr_callbacks[0])


@pytest.mark.asyncio
async def test_qwen_provider_ignores_progress_callback_runtime_error(monkeypatch, caplog):
    from openakita.agents.cli_providers.qwen import PROVIDER

    stderr_callbacks = []
    caplog.set_level(logging.DEBUG, logger="openakita.agents.cli_providers.qwen")

    async def progress(kind, **payload):
        raise RuntimeError("progress sink failed")

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"delta","text":"Working"}\n'
        yield b'{"type":"tool","name":"Edit"}\n'
        yield b'{"type":"final","usage":{"prompt_tokens":1,"completion_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.qwen.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(_request(progress), ["qwen"], {}, on_spawn=lambda proc: None)

    assert result.exit_reason == ExitReason.COMPLETED
    assert result.errored is False
    assert result.final_text == "Working"
    assert result.tools_used == ["Edit"]
    assert len(stderr_callbacks) == 1
    assert "progress callback failed" in caplog.text


@pytest.mark.asyncio
async def test_qwen_provider_propagates_progress_callback_cancelled_error(monkeypatch):
    from openakita.agents.cli_providers.qwen import PROVIDER

    stderr_callbacks = []

    async def progress(kind, **payload):
        raise asyncio.CancelledError

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"delta","text":"Working"}\n'
        yield b'{"type":"final","usage":{"prompt_tokens":1,"completion_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.qwen.stream_cli_subprocess",
        fake_stream,
    )

    with pytest.raises(asyncio.CancelledError):
        await PROVIDER.run(_request(progress), ["qwen"], {}, on_spawn=lambda proc: None)

    assert len(stderr_callbacks) == 1
