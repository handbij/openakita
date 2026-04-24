from __future__ import annotations

import asyncio

import pytest

from openakita.agents.task_queue import Priority, TaskQueue, TaskStatus


@pytest.mark.asyncio
async def test_wait_for_can_retain_result_for_multiple_observers():
    queue = TaskQueue(max_concurrent=1)

    async def handler(task):
        return f"done:{task.task_id}"

    queue.set_handler(handler)
    await queue.start()
    try:
        task_id = await queue.enqueue("session", "helper", {}, Priority.NORMAL)

        first = await queue.wait_for(task_id, timeout=1.0, consume=False)
        second = await queue.wait_for(task_id, timeout=1.0, consume=False)

        assert first == f"done:{task_id}"
        assert second == first
        assert queue.has_task(task_id) is True

        removed = await queue.forget(task_id)
        assert removed is True
        assert queue.has_task(task_id) is False
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_wait_for_default_still_consumes_result_for_compatibility():
    queue = TaskQueue(max_concurrent=1)

    async def handler(task):
        return "done"

    queue.set_handler(handler)
    await queue.start()
    try:
        task_id = await queue.enqueue("session", "helper", {}, Priority.NORMAL)
        assert await queue.wait_for(task_id, timeout=1.0) == "done"

        with pytest.raises(KeyError, match=f"Unknown task: {task_id}"):
            await queue.wait_for(task_id, timeout=0.01, consume=False)
    finally:
        await queue.stop()


@pytest.mark.asyncio
async def test_get_task_status_reports_lifecycle():
    queue = TaskQueue(max_concurrent=1)
    release = asyncio.Event()

    async def handler(task):
        await release.wait()
        return "done"

    queue.set_handler(handler)
    queued_id = await queue.enqueue("session", "helper", {}, Priority.NORMAL)
    assert queue.get_task_status(queued_id) == TaskStatus.QUEUED

    await queue.start()
    try:
        for _ in range(20):
            if queue.get_task_status(queued_id) == TaskStatus.RUNNING:
                break
            await asyncio.sleep(0.01)
        assert queue.get_task_status(queued_id) == TaskStatus.RUNNING

        release.set()
        assert await queue.wait_for(queued_id, timeout=1.0, consume=False) == "done"
        assert queue.get_task_status(queued_id) == TaskStatus.COMPLETED

        cancelled_id = await queue.enqueue("session", "helper", {}, Priority.NORMAL)
        assert await queue.cancel(cancelled_id) is True
        assert queue.get_task_status(cancelled_id) == TaskStatus.CANCELLED
    finally:
        await queue.stop()
