"""
Priority TaskQueue for multi-agent task management.

Provides async priority-based task scheduling with cancellation support.
"""

import asyncio
import enum
import heapq
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """Task priority levels. Lower value = higher priority."""

    URGENT = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


@dataclass(order=True)
class QueuedTask:
    """A task in the priority queue."""

    priority: int
    created_at: float = field(compare=True)
    task_id: str = field(default_factory=lambda: f"qt_{uuid.uuid4().hex[:10]}", compare=False)
    agent_profile_id: str = field(default="default", compare=False)
    session_key: str = field(default="", compare=False)
    payload: dict = field(default_factory=dict, compare=False)
    cancelled: bool = field(default=False, compare=False)


class TaskQueue:
    """
    Async priority task queue with cancellation and metrics.

    Usage:
        queue = TaskQueue(max_concurrent=3)
        await queue.start()
        task_id = await queue.enqueue("session_key", "agent_id", payload, Priority.NORMAL)
        result = await queue.wait_for(task_id)
        await queue.stop()
    """

    def __init__(self, max_concurrent: int = 5):
        self._heap: list[QueuedTask] = []
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Event()
        self._results: dict[str, asyncio.Future] = {}
        self._active: dict[str, asyncio.Task] = {}
        self._queued_ids: set[str] = set()
        self._max_concurrent = max_concurrent
        self._handler: Callable[[QueuedTask], Awaitable[Any]] | None = None
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._total_enqueued = 0
        self._total_completed = 0
        self._total_failed = 0
        self._total_cancelled = 0

    def set_handler(self, handler: Callable[[QueuedTask], Awaitable[Any]]) -> None:
        """Set the function that processes each task."""
        self._handler = handler

    async def start(self) -> None:
        """Start the queue worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("[TaskQueue] Started")

    async def stop(self) -> None:
        """Stop the queue worker, cancel active tasks, and resolve pending futures."""
        self._running = False
        self._not_empty.set()
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except (asyncio.CancelledError, Exception):
                pass

        for _task_id, task in self._active.items():
            if not task.done():
                task.cancel()
        self._active.clear()

        # Clean up unexecuted futures in the heap to prevent leaks
        for qt in self._heap:
            fut = self._results.pop(qt.task_id, None)
            if fut and not fut.done():
                fut.cancel()
        self._heap.clear()

        # Clean up any remaining futures
        for _tid, fut in list(self._results.items()):
            if not fut.done():
                fut.cancel()
        self._results.clear()

        logger.info("[TaskQueue] Stopped")

    async def enqueue(
        self,
        session_key: str,
        agent_profile_id: str,
        payload: dict,
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """Add a task to the queue. Returns the task_id."""
        task = QueuedTask(
            priority=priority.value,
            created_at=time.time(),
            agent_profile_id=agent_profile_id,
            session_key=session_key,
            payload=payload,
        )
        async with self._lock:
            heapq.heappush(self._heap, task)
            self._results[task.task_id] = asyncio.get_running_loop().create_future()
            self._queued_ids.add(task.task_id)
            self._total_enqueued += 1
        self._not_empty.set()
        logger.debug(f"[TaskQueue] Enqueued {task.task_id} (priority={priority.name})")
        return task.task_id

    async def cancel(self, task_id: str) -> bool:
        """Cancel a queued or active task."""
        async with self._lock:
            for t in self._heap:
                if t.task_id == task_id and not t.cancelled:
                    t.cancelled = True
                    self._total_cancelled += 1
                    fut = self._results.get(task_id)
                    if fut and not fut.done():
                        fut.cancel()
                    return True
        # Check active tasks
        active = self._active.get(task_id)
        if active and not active.done():
            active.cancel()
            self._total_cancelled += 1
            return True
        return False

    async def wait_for(
        self,
        task_id: str,
        timeout: float = 120.0,
        *,
        consume: bool = True,
    ) -> Any:
        """Wait for a task result."""
        fut = self._results.get(task_id)
        if fut is None:
            raise KeyError(f"Unknown task: {task_id}")
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        finally:
            if consume:
                self._results.pop(task_id, None)

    def has_task(self, task_id: str) -> bool:
        """Check if a task exists in the queue."""
        return task_id in self._results or task_id in self._active or task_id in self._queued_ids

    def get_task_status(self, task_id: str) -> TaskStatus:
        """Get the current status of a task."""
        if (active := self._active.get(task_id)) is not None:
            if active.cancelled():
                return TaskStatus.CANCELLED
            if not active.done():
                return TaskStatus.RUNNING

        if (fut := self._results.get(task_id)) is not None:
            if fut.cancelled():
                return TaskStatus.CANCELLED
            if not fut.done():
                return TaskStatus.QUEUED
            if fut.exception() is not None:
                return TaskStatus.FAILED
            return TaskStatus.COMPLETED

        if task_id in self._queued_ids:
            return TaskStatus.QUEUED

        return TaskStatus.UNKNOWN

    def peek_result(self, task_id: str) -> Any:
        """Peek at a task result without consuming it."""
        fut = self._results.get(task_id)
        if fut is None:
            raise KeyError(f"Unknown task: {task_id}")
        if not fut.done():
            raise asyncio.InvalidStateError(f"Task is not complete: {task_id}")
        return fut.result()

    async def forget(self, task_id: str) -> bool:
        """Remove a task from the queue. Returns True if the task was found and removed."""
        removed = False
        async with self._lock:
            if self._results.pop(task_id, None) is not None:
                removed = True
            if self._active.pop(task_id, None) is not None:
                removed = True
            if task_id in self._queued_ids:
                self._queued_ids.discard(task_id)
                removed = True
        return removed

    async def _worker_loop(self) -> None:
        """Main worker loop: picks tasks from queue and executes them."""
        while self._running:
            async with self._lock:
                task = heapq.heappop(self._heap) if self._heap else None

            if task is None:
                self._not_empty.clear()
                await self._not_empty.wait()
                if not self._running:
                    break
                continue  # Go back and check heap under lock

            self._queued_ids.discard(task.task_id)

            if task.cancelled:
                fut = self._results.pop(task.task_id, None)
                if fut and not fut.done():
                    fut.cancel()
                continue

            # Wait for concurrency slot
            while len(self._active) >= self._max_concurrent and self._active:
                tasks = list(self._active.values())
                if not tasks:
                    break
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                finished_ids = [tid for tid, t in self._active.items() if t.done()]
                for tid in finished_ids:
                    self._active.pop(tid, None)

            self._active[task.task_id] = asyncio.create_task(self._execute_task(task))

    async def _execute_task(self, task: QueuedTask) -> None:
        """Execute a single task and resolve its future."""
        fut = self._results.get(task.task_id)
        try:
            if self._handler is None:
                raise RuntimeError("No handler set")
            result = await self._handler(task)
            if fut and not fut.done():
                fut.set_result(result)
            self._total_completed += 1
        except asyncio.CancelledError:
            if fut and not fut.done():
                fut.cancel()
            self._total_cancelled += 1
        except Exception as e:
            if fut and not fut.done():
                fut.set_exception(e)
            self._total_failed += 1
            logger.error(f"[TaskQueue] Task {task.task_id} failed: {e}")

    def get_stats(self) -> dict:
        """Get queue statistics."""
        return {
            "pending": len(self._heap),
            "active": len(self._active),
            "total_enqueued": self._total_enqueued,
            "total_completed": self._total_completed,
            "total_failed": self._total_failed,
            "total_cancelled": self._total_cancelled,
            "max_concurrent": self._max_concurrent,
        }
