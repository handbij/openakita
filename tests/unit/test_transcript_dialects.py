from __future__ import annotations

import json

import pytest

from openakita.sessions.transcript import (
    TranscriptEntry,
    parse_claude_stream_json,
    parse_codex_jsonl,
)


def test_claude_user_line_is_mapped():
    line = json.dumps({
        "type": "user",
        "message": {"role": "user", "content": "hello"},
        "timestamp": "2026-04-22T10:00:00Z",
        "session_id": "abc",
    })
    entry = parse_claude_stream_json(line)
    assert entry == {
        "type": "message",
        "role": "user",
        "content": "hello",
        "_ts": "2026-04-22T10:00:00Z",
        "_source": "claude",
    }


def test_claude_assistant_tool_use_is_mapped():
    line = json.dumps({
        "type": "assistant",
        "message": {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Running grep."},
                {"type": "tool_use", "id": "tu_1", "name": "Bash", "input": {"command": "grep foo"}},
            ],
        },
        "timestamp": "2026-04-22T10:00:01Z",
    })
    entry = parse_claude_stream_json(line)
    assert entry is not None
    assert entry["type"] == "message"
    assert entry["role"] == "assistant"
    assert isinstance(entry["content"], list)
    assert entry["content"][1]["type"] == "tool_use"


def test_claude_tool_result_is_mapped():
    line = json.dumps({
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "matched 3 lines", "is_error": False}
            ],
        },
        "timestamp": "2026-04-22T10:00:02Z",
    })
    entry = parse_claude_stream_json(line)
    assert entry == {
        "type": "tool_result",
        "tool_use_id": "tu_1",
        "tool_name": "",
        "content": "matched 3 lines",
        "is_error": False,
        "_ts": "2026-04-22T10:00:02Z",
        "_source": "claude",
    }


def test_claude_system_line_is_skipped():
    assert parse_claude_stream_json(json.dumps({"type": "system", "subtype": "init"})) is None


def test_claude_malformed_line_returns_none():
    assert parse_claude_stream_json("not-json") is None
    assert parse_claude_stream_json("") is None
