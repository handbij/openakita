"""Runtime-checkable Protocols for the agent duck-type surface.

The native `Agent` class and the `ExternalCliAgent` shim both implement these
protocols. Adding a new concrete agent type (e.g., a cloud-hosted agent in a
future phase) means making it pass `isinstance(x, AgentLike)` — nothing more.

Keeping the duck-type documented here (instead of as comments on the consumers)
lets `mypy`/`pyright` catch drift and lets tests assert the shape with one line.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BrainLike(Protocol):
    """Minimal Brain surface the pool's brain-sharing code touches.

    `ExternalCliAgent` returns a `_NullBrain` singleton that no-ops every call,
    because external processes own their own context outside Python.
    """

    def append_user(self, *_a: Any, **_kw: Any) -> None: ...
    def append_assistant(self, *_a: Any, **_kw: Any) -> None: ...
    def append_tool_result(self, *_a: Any, **_kw: Any) -> None: ...
    def is_loaded(self) -> bool: ...


@runtime_checkable
class ChatSessionLike(Protocol):
    """Attributes an agent reads off the session passed to `chat_with_session`."""

    id: str
    cwd: str
    conversation_id: str


@runtime_checkable
class AgentLike(Protocol):
    """Orchestrator/pool/scheduler-facing surface of an agent.

    Every field/method listed here is actually read or called by:
      - `AgentOrchestrator._call_agent` / `_dispatch` / `_run_with_progress_timeout`
      - `AgentInstancePool.get_or_create` / `_find_parent_brain` / idle reaper
      - `scheduler/executor.py::_run_agent`
      - `OrgRuntime._activate_and_run`

    Keep this list minimal. Anything wider — especially `Any`-typed state shims —
    lets drift hide.
    """

    agent_state: Any
    brain: BrainLike
    last_session_id: str | None

    async def initialize(self, *, lightweight: bool = True) -> None: ...
    async def chat_with_session(
        self,
        session: ChatSessionLike,
        message: str,
        *,
        is_sub_agent: bool = False,
        image_paths: tuple[Any, ...] = (),
        **_: Any,
    ) -> Any: ...
    async def execute_task_from_message(self, message: str) -> Any: ...
    async def cancel(self) -> None: ...
    async def shutdown(self) -> None: ...
