from __future__ import annotations

import asyncio
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
async def test_claude_provider_emits_thinking_text_and_tool_progress(monkeypatch):
    from openakita.agents.cli_providers.claude_code import PROVIDER

    events = []
    stderr_callbacks = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield (
            b'{"type":"assistant","message":{"content":['
            b'{"type":"thinking","thinking":"Reviewing files..."},'
            b'{"type":"text","text":"Working"},'
            b'{"type":"tool_use","name":"Edit"}]}}\n'
        )
        yield b'{"type":"result","usage":{"input_tokens":1,"output_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code.stream_cli_subprocess",
        fake_stream,
    )
    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code._git_diff_names",
        lambda cwd: set(),
    )

    result = await PROVIDER.run(
        _request(progress),
        ["claude"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.final_text == "Working"
    assert ("assistant_thinking", {"text": "Reviewing files..."}) in events
    assert ("assistant_text", {"text": "Working"}) in events
    assert ("tool_use", {"tool_name": "Edit"}) in events
    assert len(stderr_callbacks) == 1
    assert callable(stderr_callbacks[0])


@pytest.mark.asyncio
async def test_claude_provider_ignores_redacted_thinking(monkeypatch):
    from openakita.agents.cli_providers.claude_code import PROVIDER

    events = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        yield (
            b'{"type":"assistant","message":{"content":['
            b'{"type":"redacted_thinking","data":"secret"},'
            b'{"type":"text","text":"Visible"}]}}\n'
        )
        yield b'{"type":"result","usage":{"input_tokens":1,"output_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code.stream_cli_subprocess",
        fake_stream,
    )
    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code._git_diff_names",
        lambda cwd: set(),
    )

    result = await PROVIDER.run(
        _request(progress),
        ["claude"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.final_text == "Visible"
    assert all(kind != "assistant_thinking" for kind, _payload in events)


@pytest.mark.asyncio
async def test_claude_provider_ignores_progress_callback_runtime_error(monkeypatch):
    from openakita.agents.cli_providers.claude_code import PROVIDER

    stderr_callbacks = []

    async def progress(kind, **payload):
        raise RuntimeError("progress sink failed")

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"assistant","message":{"content":[{"type":"text","text":"Working"}]}}\n'
        yield b'{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit"}]}}\n'
        yield b'{"type":"result","usage":{"input_tokens":1,"output_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code.stream_cli_subprocess",
        fake_stream,
    )
    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code._git_diff_names",
        lambda cwd: set(),
    )

    result = await PROVIDER.run(
        _request(progress),
        ["claude"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.exit_reason == ExitReason.COMPLETED
    assert result.errored is False
    assert result.final_text == "Working"
    assert result.tools_used == ["Edit"]
    assert len(stderr_callbacks) == 1


@pytest.mark.asyncio
async def test_claude_provider_propagates_progress_callback_cancelled_error(monkeypatch):
    from openakita.agents.cli_providers.claude_code import PROVIDER

    stderr_callbacks = []

    async def progress(kind, **payload):
        raise asyncio.CancelledError

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"assistant","message":{"content":[{"type":"text","text":"Working"}]}}\n'
        yield b'{"type":"result","usage":{"input_tokens":1,"output_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code.stream_cli_subprocess",
        fake_stream,
    )
    monkeypatch.setattr(
        "openakita.agents.cli_providers.claude_code._git_diff_names",
        lambda cwd: set(),
    )

    with pytest.raises(asyncio.CancelledError):
        await PROVIDER.run(
            _request(progress),
            ["claude"],
            {},
            on_spawn=lambda proc: None,
        )

    assert len(stderr_callbacks) == 1


@pytest.mark.asyncio
async def test_codex_provider_emits_text_and_tool_progress(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    events = []
    stderr_callbacks = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"assistant_delta","text":"Working"}\n'
        yield b'{"type":"tool_call","name":"shell"}\n'
        yield b'{"type":"turn_end","usage":{"input_tokens":1,"output_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(
        _request(progress),
        ["codex"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.final_text == "Working"
    assert ("assistant_text", {"text": "Working"}) in events
    assert ("tool_use", {"tool_name": "shell"}) in events
    assert len(stderr_callbacks) == 1
    assert callable(stderr_callbacks[0])


@pytest.mark.asyncio
async def test_codex_provider_emits_current_dialect_progress(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    events = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        yield (
            b'{"type":"event_msg","payload":{"type":"reasoning",'
            b'"summary":[{"text":"Reviewing files..."}]}}\n'
        )
        yield (
            b'{"type":"response_item","payload":{"type":"function_call",'
            b'"call_id":"call_1","name":"exec_command","arguments":"{}"}}\n'
        )
        yield (
            b'{"type":"event_msg","payload":{"type":"exec_command_end",'
            b'"call_id":"call_1","status":"completed","exit_code":0}}\n'
        )
        yield (
            b'{"type":"event_msg","payload":{"type":"agent_message",'
            b'"message":"Done","phase":"final"}}\n'
        )
        yield (
            b'{"type":"event_msg","payload":{"type":"token_count",'
            b'"info":{"last_token_usage":{"input_tokens":3,"output_tokens":4}}}}\n'
        )
        yield b'{"type":"event_msg","payload":{"type":"task_complete"}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(
        _request(progress),
        ["codex"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.final_text == "Done"
    assert result.tools_used == ["exec_command"]
    assert result.input_tokens == 3
    assert result.output_tokens == 4
    assert ("assistant_thinking", {"text": "Reviewing files..."}) in events
    assert ("assistant_text", {"text": "Done"}) in events
    assert events.count(("tool_use", {"tool_name": "exec_command"})) == 1


@pytest.mark.asyncio
async def test_codex_provider_emits_status_progress_before_semantic_output(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    events = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        yield b'{"type":"session_start","session_id":"codex-sess-1"}\n'
        yield b'{"type":"task_started","turn_id":"turn-1"}\n'
        yield b'{"type":"agent_message","message":"Done"}\n'
        yield b'{"type":"turn_end","usage":{"input_tokens":1,"output_tokens":1}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(
        _request(progress),
        ["codex"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.exit_reason == ExitReason.COMPLETED
    assert result.session_id == "turn-1"
    assert result.final_text == "Done"
    assert ("assistant_thinking", {"text": "Codex session started."}) in events
    assert ("assistant_thinking", {"text": "Codex started working."}) in events


@pytest.mark.asyncio
async def test_codex_provider_emits_responses_style_item_events(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    events = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        yield b'{"type":"response.created","response":{"id":"resp_1"}}\n'
        yield (
            b'{"type":"response.output_item.added","item":{'
            b'"type":"reasoning","summary":[{"text":"Inspecting workspace"}]}}\n'
        )
        yield (
            b'{"type":"response.output_item.done","item":{'
            b'"type":"function_call","call_id":"call_1","name":"exec_command"}}\n'
        )
        yield b'{"type":"response.output_text.delta","delta":"Done"}\n'
        yield (
            b'{"type":"response.completed","response":{'
            b'"usage":{"input_tokens":5,"output_tokens":6}}}\n'
        )

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(
        _request(progress),
        ["codex"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.final_text == "Done"
    assert result.tools_used == ["exec_command"]
    assert result.input_tokens == 5
    assert result.output_tokens == 6
    assert ("assistant_thinking", {"text": "Codex started working."}) in events
    assert ("assistant_thinking", {"text": "Inspecting workspace"}) in events
    assert ("assistant_text", {"text": "Done"}) in events
    assert ("tool_use", {"tool_name": "exec_command"}) in events


@pytest.mark.asyncio
async def test_codex_provider_emits_codex_0124_item_completed_events(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    events = []

    async def progress(kind, **payload):
        events.append((kind, payload))

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        yield b'{"type":"thread.started","thread_id":"thread-1"}\n'
        yield b'{"type":"turn.started"}\n'
        yield (
            b'{"type":"item.completed","item":{'
            b'"id":"item_0","type":"agent_message","text":"Starting"}}\n'
        )
        yield (
            b'{"type":"item.started","item":{'
            b'"id":"item_1","type":"command_execution","command":"test -e result.txt",'
            b'"status":"in_progress"}}\n'
        )
        yield (
            b'{"type":"item.completed","item":{'
            b'"id":"item_1","type":"command_execution","command":"test -e result.txt",'
            b'"aggregated_output":"missing","exit_code":0,"status":"completed"}}\n'
        )
        yield (
            b'{"type":"item.completed","item":{'
            b'"id":"item_2","type":"file_change",'
            b'"changes":[{"path":"/tmp/result.txt","kind":"add"}],"status":"completed"}}\n'
        )
        yield (
            b'{"type":"item.completed","item":{'
            b'"id":"item_3","type":"agent_message","text":"Created `/tmp/result.txt`"}}\n'
        )
        yield b'{"type":"turn.completed","usage":{"input_tokens":7,"output_tokens":8}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(
        _request(progress),
        ["codex"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.final_text == "StartingCreated `/tmp/result.txt`"
    assert result.tools_used == ["exec_command", "file_change"]
    assert result.input_tokens == 7
    assert result.output_tokens == 8
    assert ("assistant_text", {"text": "Created `/tmp/result.txt`"}) in events
    assert ("tool_use", {"tool_name": "exec_command"}) in events
    assert ("tool_use", {"tool_name": "file_change"}) in events


@pytest.mark.asyncio
async def test_codex_provider_maps_turn_aborted_to_error(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    async def progress(kind, **payload):
        pass

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        yield b'{"type":"event_msg","payload":{"type":"turn_aborted","reason":"interrupted"}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(
        _request(progress),
        ["codex"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.exit_reason == ExitReason.ERROR
    assert result.errored is True
    assert result.error_message == "interrupted"


@pytest.mark.asyncio
async def test_codex_provider_ignores_progress_callback_runtime_error(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    stderr_callbacks = []

    async def progress(kind, **payload):
        raise RuntimeError("progress sink failed")

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"assistant_delta","text":"Working"}\n'
        yield b'{"type":"tool_call","name":"shell"}\n'
        yield b'{"type":"turn_end","usage":{"input_tokens":1,"output_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    result = await PROVIDER.run(
        _request(progress),
        ["codex"],
        {},
        on_spawn=lambda proc: None,
    )

    assert result.exit_reason == ExitReason.COMPLETED
    assert result.errored is False
    assert result.final_text == "Working"
    assert result.tools_used == ["shell"]
    assert len(stderr_callbacks) == 1


@pytest.mark.asyncio
async def test_codex_provider_propagates_progress_callback_cancelled_error(monkeypatch):
    from openakita.agents.cli_providers.codex import PROVIDER

    stderr_callbacks = []

    async def progress(kind, **payload):
        raise asyncio.CancelledError

    async def fake_stream(argv, env, cwd, cancelled, *, on_spawn, on_stderr=None):
        assert on_stderr is not None
        stderr_callbacks.append(on_stderr)
        yield b'{"type":"assistant_delta","text":"Working"}\n'
        yield b'{"type":"turn_end","usage":{"input_tokens":1,"output_tokens":2}}\n'

    monkeypatch.setattr(
        "openakita.agents.cli_providers.codex.stream_cli_subprocess",
        fake_stream,
    )

    with pytest.raises(asyncio.CancelledError):
        await PROVIDER.run(
            _request(progress),
            ["codex"],
            {},
            on_spawn=lambda proc: None,
        )

    assert len(stderr_callbacks) == 1
