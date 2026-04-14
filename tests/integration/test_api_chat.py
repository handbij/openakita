"""L3 Integration Tests: FastAPI /api/chat SSE endpoint and control routes."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from openakita.api.server import create_app
from openakita.sessions import SessionManager


@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.initialized = True
    agent._initialized = True
    agent.state = MagicMock()
    agent.agent_state = MagicMock()
    agent.state.has_active_task = False
    agent.state.is_task_cancelled = False
    agent.brain = MagicMock()
    agent.brain.model = "mock-model"
    agent.settings = MagicMock()
    agent.settings.max_iterations = 10
    agent.session_manager = None
    agent.build_tool_trace_summary = MagicMock(return_value="")

    async def fake_stream(*args, **kwargs):
        yield "Hello from mock agent"

    agent.chat_with_session_stream = fake_stream
    agent.chat_with_session = AsyncMock(return_value="Hello from mock agent")
    return agent


@pytest.fixture
def app(mock_agent, tmp_path):
    return create_app(
        agent=mock_agent,
        shutdown_event=asyncio.Event(),
        session_manager=SessionManager(storage_path=tmp_path),
    )


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as c:
        yield c


class TestRootEndpoint:
    async def test_root_returns_status(self, client):
        resp = await client.get("/", follow_redirects=True)
        assert resp.status_code == 200


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200


class TestChatEndpoint:
    async def test_chat_returns_sse(self, client):
        resp = await client.post(
            "/api/chat",
            json={"message": "Hello", "conversation_id": "test-conv-1"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

    async def test_chat_empty_message(self, client):
        resp = await client.post(
            "/api/chat",
            json={"message": "", "conversation_id": "test-conv-1"},
        )
        assert resp.status_code == 200

    async def test_chat_history_persists_user_attachments(self, app, client):
        session = app.state.session_manager.get_session(
            channel="desktop",
            chat_id="test-conv-attachments",
            user_id="desktop_user",
            create_if_missing=True,
        )
        session.add_message(
            "user",
            "帮我看看这张图",
            attachments=[
                {
                    "type": "image",
                    "name": "demo.png",
                    "url": "data:image/png;base64,ZmFrZQ==",
                    "mime_type": "image/png",
                }
            ],
        )

        hist = await client.get("/api/sessions/test-conv-attachments/history")
        assert hist.status_code == 200
        data = hist.json()
        user_msgs = [m for m in data["messages"] if m["role"] == "user"]
        assert user_msgs
        assert user_msgs[-1]["attachments"] == [
            {
                "type": "image",
                "name": "demo.png",
                "url": "data:image/png;base64,ZmFrZQ==",
                "mime_type": "image/png",
            }
        ]

    async def test_chat_history_keeps_attachment_only_user_message(self, app, client):
        session = app.state.session_manager.get_session(
            channel="desktop",
            chat_id="test-conv-attachment-only",
            user_id="desktop_user",
            create_if_missing=True,
        )
        session.add_message(
            "user",
            "",
            attachments=[
                {
                    "type": "image",
                    "name": "only-image.png",
                    "url": "data:image/png;base64,ZmFrZQ==",
                    "mime_type": "image/png",
                }
            ],
        )

        hist = await client.get("/api/sessions/test-conv-attachment-only/history")
        assert hist.status_code == 200
        data = hist.json()
        user_msgs = [m for m in data["messages"] if m["role"] == "user"]
        assert user_msgs
        assert user_msgs[-1]["content"] == ""
        assert user_msgs[-1]["attachments"][0]["name"] == "only-image.png"

    async def test_chat_history_keeps_inline_directory_attachment_metadata(self, app, client):
        session = app.state.session_manager.get_session(
            channel="desktop",
            chat_id="test-conv-directory-attachment",
            user_id="desktop_user",
            create_if_missing=True,
        )
        session.add_message(
            "user",
            "看看这个目录结构",
            attachments=[
                {
                    "type": "directory",
                    "name": "project",
                    "display_path": "C:/Users/demo/project",
                    "entries": ["src", "tests", "README.md"],
                }
            ],
        )

        hist = await client.get("/api/sessions/test-conv-directory-attachment/history")
        assert hist.status_code == 200
        data = hist.json()
        user_msgs = [m for m in data["messages"] if m["role"] == "user"]
        assert user_msgs
        assert user_msgs[-1]["attachments"] == [
            {
                "type": "directory",
                "name": "project",
                "display_path": "C:/Users/demo/project",
                "entries": ["src", "tests", "README.md"],
            }
        ]


class TestChatControlEndpoints:
    async def test_cancel_endpoint(self, client, mock_agent):
        mock_agent.state.cancel_task = MagicMock()
        resp = await client.post(
            "/api/chat/cancel",
            json={"conversation_id": "test-conv-1", "reason": "user stopped"},
        )
        assert resp.status_code == 200

    async def test_skip_endpoint(self, client, mock_agent):
        mock_agent.state.skip_current_step = MagicMock()
        resp = await client.post(
            "/api/chat/skip",
            json={"conversation_id": "test-conv-1"},
        )
        assert resp.status_code == 200

    async def test_answer_endpoint(self, client):
        resp = await client.post(
            "/api/chat/answer",
            json={"conversation_id": "test-conv-1", "answer": "Yes"},
        )
        assert resp.status_code == 200

    async def test_insert_endpoint(self, client, mock_agent):
        mock_agent.state.insert_user_message = AsyncMock()
        resp = await client.post(
            "/api/chat/insert",
            json={"conversation_id": "test-conv-1", "message": "new info"},
        )
        assert resp.status_code == 200


class TestShutdownEndpoint:
    async def test_shutdown_sets_event(self, client, app):
        resp = await client.post("/api/shutdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "shutting_down"
        assert app.state.shutdown_event.is_set()
