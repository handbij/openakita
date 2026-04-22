"""Shared streaming helper for provider adapters.

stream_cli_subprocess() spawns a subprocess with asyncio.create_subprocess_exec
(shell=False always), calls the caller's on_spawn hook synchronously so the
runner can track the process for signal escalation, then yields stdout lines
until EOF or cancellation.

Streaming-only. Does NOT replace the blocking _run_cmd helpers in
tools/handlers/opencli.py — those are one-shot Popen.communicate calls.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from pathlib import Path


async def stream_cli_subprocess(
    argv: list[str],
    env: dict[str, str],
    cwd: Path,
    cancelled: asyncio.Event,
    *,
    on_spawn: Callable[[asyncio.subprocess.Process], None],
) -> AsyncIterator[bytes]:
    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd) if cwd else None,
        env={**env} if env else None,
    )
    on_spawn(proc)
    assert proc.stdout is not None
    while True:
        if cancelled.is_set():
            return
        read_task = asyncio.create_task(proc.stdout.readline())
        cancel_task = asyncio.create_task(cancelled.wait())
        done, _pending = await asyncio.wait(
            {read_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if cancel_task in done and read_task not in done:
            read_task.cancel()
            return
        cancel_task.cancel()
        line = await read_task
        if not line:
            return
        yield line
