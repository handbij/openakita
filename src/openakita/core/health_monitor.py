"""Unified health monitoring for failure recovery.

Single periodic loop that checks for:
- Stale tasks (ongoing too long without progress)
- Stale delegations (via orchestrator.cleanup_expired_delegations)
- Orphaned processes (external CLI agents)

Uses HealthConfig for all thresholds to avoid magic values.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..agents.orchestrator import AgentOrchestrator

from .health_config import HealthConfig

logger = logging.getLogger(__name__)


@dataclass
class HealthReport:
    """Result of a single health check."""

    stale_tasks: list[str] = field(default_factory=list)
    stale_delegations: list[str] = field(default_factory=list)
    orphaned_processes: list[int] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    @property
    def has_issues(self) -> bool:
        return bool(self.stale_tasks or self.stale_delegations or self.orphaned_processes)


class HealthMonitor:
    """Unified health monitoring with single periodic loop."""

    def __init__(self, config: HealthConfig | None = None):
        self.config = config or HealthConfig()
        self._active_tasks: dict[str, dict] = {}
        self._agents: dict[str, Any] = {}
        self._running = False
        self._task: asyncio.Task | None = None

    def register_task(self, session_id: str, task_id: str) -> None:
        """Register a task for staleness tracking."""
        if session_id in self._active_tasks:
            logger.debug(
                f"[HealthMonitor] Re-registering task for session={session_id}, "
                f"replacing task_id={self._active_tasks[session_id]['task_id']}"
            )
        self._active_tasks[session_id] = {
            "task_id": task_id,
            "start_time": time.time(),
        }

    def unregister_task(self, session_id: str) -> None:
        """Remove a task from tracking (completed or cancelled)."""
        self._active_tasks.pop(session_id, None)

    def register_agent(self, session_id: str, agent: Any) -> None:
        """Register an agent for auto-recovery."""
        self._agents[session_id] = agent

    async def check_health(
        self,
        orchestrator: "AgentOrchestrator | None" = None,
        auto_recover: bool = False,
    ) -> HealthReport:
        """Run a single health check across all subsystems.

        Args:
            orchestrator: Optional orchestrator for delegation cleanup
            auto_recover: If True, automatically cancel stale tasks
        """
        stale_tasks = self._find_stale_tasks()
        stale_delegations = []

        if orchestrator is not None:
            stale_delegations = await orchestrator.cleanup_expired_delegations()

        orphaned = self._find_orphaned_processes()

        if auto_recover and stale_tasks:
            await self._recover_stale_tasks(stale_tasks)

        report = HealthReport(
            stale_tasks=stale_tasks,
            stale_delegations=stale_delegations,
            orphaned_processes=orphaned,
        )

        if report.has_issues:
            logger.warning(
                f"[HealthMonitor] Issues found: "
                f"stale_tasks={len(stale_tasks)}, "
                f"stale_delegations={len(stale_delegations)}, "
                f"orphaned_procs={len(orphaned)}"
            )

        return report

    async def _recover_stale_tasks(self, session_ids: list[str]) -> None:
        """Cancel stale tasks and notify users."""
        for session_id in session_ids:
            agent = self._agents.get(session_id)
            if agent and hasattr(agent, 'cancel_current_task'):
                logger.warning(f"[HealthMonitor] Auto-cancelling stale task: {session_id}")
                agent.cancel_current_task(
                    reason="Task cancelled by health monitor (exceeded max age)",
                    session_id=session_id,
                )
            self.unregister_task(session_id)

    def _find_stale_tasks(self) -> list[str]:
        """Find tasks that have been running too long."""
        now = time.time()
        stale = []

        for session_id, info in list(self._active_tasks.items()):
            age = now - info["start_time"]
            if age > self.config.stale_task_age:
                stale.append(session_id)
                logger.warning(
                    f"[HealthMonitor] Stale task: session={session_id}, "
                    f"age={age:.0f}s > {self.config.stale_task_age}s"
                )

        return stale

    def _find_orphaned_processes(self) -> list[int]:
        """Find orphaned external CLI processes."""
        # TODO: Implement process scanning for external agents
        return []

    async def start(self, orchestrator: "AgentOrchestrator | None" = None) -> None:
        """Start the periodic health check loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._loop(orchestrator))
        logger.info(
            f"[HealthMonitor] Started with interval={self.config.check_interval}s"
        )

    async def stop(self) -> None:
        """Stop the health check loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[HealthMonitor] Stopped")

    async def _loop(self, orchestrator: "AgentOrchestrator | None") -> None:
        """Periodic health check loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval)
                await self.check_health(orchestrator)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[HealthMonitor] Error in health check: {e}")
