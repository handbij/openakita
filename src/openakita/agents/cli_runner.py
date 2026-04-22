# src/openakita/agents/cli_runner.py
"""External-CLI subprocess lifecycle layer.

Owns: spawning, tracking, and terminating the CLI subprocess for one
`ExternalCliAgent` turn. Does NOT own argv building, stream parsing, or
resume-id tracking — those belong to the `ProviderAdapter` (plan 08) and
to `ExternalCliAgent` (plan 09) respectively.

Escalation: `terminate_and_wait()` walks SIGINT → SIGTERM → SIGKILL with
bounded grace. Worst case 6s. Constants are module-level so tests can
monkey-patch them to zero.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openakita.agents.cli_providers import ProviderAdapter  # noqa: F401

# --- cancellation timeouts (named, not magic) ------------------------------
_SIGINT_GRACE_S = 3.0
_SIGTERM_GRACE_S = 2.0
_SIGKILL_GRACE_S = 1.0

# --- concurrency cap --------------------------------------------------------
DEFAULT_MAX_CONCURRENT_EXTERNAL_CLIS = 3  # settings key: external_cli_max_concurrent


class ExitReason(StrEnum):
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class CliRunRequest:
    """Per-turn invocation bundle. Immutable so adapters can't stash it."""
    message: str
    resume_id: str | None
    profile: Any
    cwd: Path
    cancelled: asyncio.Event
    session: Any | None
    system_prompt_extra: str
    images: tuple[Path, ...] = ()
    mcp_servers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProviderRunResult:
    """Per-turn outcome bundle. Everything the agent or UI needs, nothing more."""
    final_text: str
    tools_used: list[str]
    artifacts: list[str]
    session_id: str | None
    input_tokens: int
    output_tokens: int
    exit_reason: ExitReason
    errored: bool
    error_message: str | None


class ExternalCliLimiter:
    def __init__(self, max_concurrent: int = DEFAULT_MAX_CONCURRENT_EXTERNAL_CLIS) -> None:
        self._sem = asyncio.Semaphore(max(1, max_concurrent))

    async def __aenter__(self) -> None:
        await self._sem.acquire()

    async def __aexit__(self, *_exc) -> None:
        self._sem.release()
