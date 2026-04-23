"""Shared progress-aware timeout helpers.

Goal: avoid hangs without penalising long-running tasks that are still
making progress. A task is considered "stuck" only when no meaningful
progress signal has been observed for ``progress_timeout_seconds``.
A ``hard_timeout_seconds`` cap is honoured as a final safety net and is
never bypassed by progress activity.

These helpers are consumed by:
  * ``agents.orchestrator`` — sub-agent dispatch polling loop
  * ``scheduler.executor`` — scheduled complex task execution

A meaningful progress signal is anything the caller tracks by updating
``last_progress_timestamp``. Empty heartbeats (pure timestamp churn or
log lines matching ``ignored_patterns``) must not reset progress.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


# Default patterns that should NOT count as progress — pure log churn.
_DEFAULT_IGNORED_PATTERNS: tuple[str, ...] = (
    r"^\s*$",                             # empty lines
    r"heartbeat",                          # periodic heartbeat
    r"keepalive",                          # keepalive ping
    r"waiting for",                        # "waiting for X" noise
    r"polling",                            # poll loop logs
    r"idle check",                         # idle loop logs
    r"^\[timestamp\]",                     # bare timestamp entries
)


def _compile_patterns(patterns: list[str] | None) -> list[re.Pattern[str]]:
    if not patterns:
        patterns = list(_DEFAULT_IGNORED_PATTERNS)
    return [re.compile(p, re.IGNORECASE) for p in patterns]


def is_meaningful_progress(
    activity_line: str,
    ignored_patterns: list[str] | None = None,
) -> bool:
    """Classify a single activity record.

    Returns ``False`` if the line matches any ignored pattern (pure log churn),
    ``True`` otherwise. Callers should only reset their progress timestamp
    when this returns ``True``.
    """
    if not activity_line or not activity_line.strip():
        return False
    compiled = _compile_patterns(ignored_patterns)
    return not any(p.search(activity_line) for p in compiled)


async def check_progress_timeout(
    last_progress_timestamp: float,
    session_id: str,
    timeout_seconds: int,
    hard_timeout_seconds: int = 0,
    activity_log: list[str] | None = None,
    ignored_patterns: list[str] | None = None,
    *,
    start_time: float | None = None,
    now_fn: Callable[[], float] = time.monotonic,
) -> tuple[bool, str | None]:
    """Return ``(is_timeout, reason)`` based on progress and hard caps.

    Parameters
    ----------
    last_progress_timestamp:
        Monotonic timestamp when the caller last observed meaningful progress.
        The caller owns updating this value; see :func:`is_meaningful_progress`.
    session_id:
        Opaque id used only in log lines to disambiguate concurrent tasks.
    timeout_seconds:
        No-progress threshold. If ``now - last_progress_timestamp`` exceeds
        this and no recent activity log entry is "meaningful", return timeout.
    hard_timeout_seconds:
        Absolute wall-clock cap from ``start_time``. ``0`` disables. This is
        always honoured regardless of progress activity.
    activity_log:
        Optional list of recent activity lines. If the tail contains at least
        one meaningful entry newer than the last timestamp reset, the caller
        is expected to have already updated ``last_progress_timestamp``; this
        argument is only used for diagnostic strings.
    ignored_patterns:
        Extra regex patterns to treat as non-progress. Defaults apply to
        empty/heartbeat/log-churn noise.
    start_time:
        Monotonic start. Required when ``hard_timeout_seconds > 0``. If
        omitted, falls back to ``last_progress_timestamp`` (never ideal for
        hard timeout).
    now_fn:
        Injectable clock for tests.

    Returns
    -------
    (is_timeout, reason)
        ``reason`` is one of ``"hard_timeout"`` / ``"progress_timeout"`` /
        ``None``.
    """
    now = now_fn()

    if hard_timeout_seconds and hard_timeout_seconds > 0:
        effective_start = start_time if start_time is not None else last_progress_timestamp
        elapsed = now - effective_start
        if elapsed >= hard_timeout_seconds:
            logger.warning(
                "[timeout_utils:%s] Hard timeout reached: elapsed=%.1fs cap=%ds",
                session_id, elapsed, hard_timeout_seconds,
            )
            return True, "hard_timeout"

    if timeout_seconds <= 0:
        return False, None

    idle = now - last_progress_timestamp
    if idle >= timeout_seconds:
        tail_preview = ""
        if activity_log:
            tail = activity_log[-3:]
            tail_preview = " | ".join(line[:80] for line in tail)
        logger.warning(
            "[timeout_utils:%s] Progress timeout: idle=%.1fs threshold=%ds "
            "recent_activity=[%s]",
            session_id, idle, timeout_seconds, tail_preview,
        )
        return True, "progress_timeout"

    return False, None


async def run_with_progress_polling(
    task: asyncio.Task[Any],
    *,
    progress_timeout_seconds: int,
    hard_timeout_seconds: int = 0,
    get_progress_signature: Callable[[], Any] | None = None,
    session_id: str = "",
    check_interval: float = 1.0,
    on_progress: Callable[[Any], None] | None = None,
    on_timeout: Callable[[str], None] | None = None,
) -> Any:
    """Await ``task`` with progress-aware timeout enforcement.

    The task runs until either it completes or the shared timeout logic in
    :func:`check_progress_timeout` reports a timeout. ``get_progress_signature``
    is polled on every check; whenever the signature changes, the progress
    timestamp resets.

    Raises :class:`asyncio.TimeoutError` on timeout after cancelling the task.
    """
    start = time.monotonic()
    last_progress = start
    last_signature: Any = None

    try:
        while not task.done():
            await asyncio.sleep(check_interval)

            if get_progress_signature is not None:
                try:
                    sig = get_progress_signature()
                except Exception as e:
                    logger.debug("[timeout_utils:%s] signature error: %s", session_id, e)
                    sig = last_signature
                if sig != last_signature:
                    last_signature = sig
                    last_progress = time.monotonic()
                    if on_progress is not None:
                        try:
                            on_progress(sig)
                        except Exception as e:
                            logger.debug(
                                "[timeout_utils:%s] on_progress callback error: %s",
                                session_id, e,
                            )

            timed_out, reason = await check_progress_timeout(
                last_progress_timestamp=last_progress,
                session_id=session_id,
                timeout_seconds=progress_timeout_seconds,
                hard_timeout_seconds=hard_timeout_seconds,
                start_time=start,
            )
            if timed_out:
                if on_timeout is not None:
                    try:
                        on_timeout(reason or "timeout")
                    except Exception as e:
                        logger.debug(
                            "[timeout_utils:%s] on_timeout callback error: %s",
                            session_id, e,
                        )
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                raise TimeoutError(reason or "timeout")

        return task.result()
    except asyncio.CancelledError:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        raise
