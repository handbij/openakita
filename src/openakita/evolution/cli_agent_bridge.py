"""External coding-CLI agent bridge.

Launches supported external coding agents (``claude-code`` / ``codex`` /
``goose``) as subprocesses when the operator wants the self-improvement
orchestrator to hand execution off to a dedicated harness. Falls back to
reporting ``(False, "not_found")`` when the requested binary is missing on
``PATH`` — the caller is expected to drop back to native subagents.

The binaries are documented here for clarity::

    claude-code → executable "claude"  (Claude Code CLI)
    codex       → executable "codex"   (OpenAI Codex CLI)
    goose       → executable "goose"   (Block Goose)

The bridge does **not** pipe the task description to stdin by default —
most CLI agents expect it on the command line or via a ``-p`` flag. The
task description is passed as the final positional argument, which works
for ``claude`` and ``codex``; callers can customise per-agent invocation
by passing ``extra_args``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import shutil
from typing import Any

logger = logging.getLogger(__name__)


_AGENT_BINARY: dict[str, str] = {
    "claude-code": "claude",
    "codex": "codex",
    "goose": "goose",
}


def resolve_binary(agent_type: str) -> str | None:
    """Return the binary on ``PATH`` for ``agent_type`` or ``None``."""
    binary = _AGENT_BINARY.get(agent_type)
    if not binary:
        return None
    return shutil.which(binary)


async def run_external_cli_agent(
    agent_type: str,
    task_description: str,
    working_directory: str,
    timeout_seconds: int = 3600,
    *,
    extra_args: list[str] | None = None,
    env: dict[str, str] | None = None,
    subprocess_factory: Any = None,
) -> tuple[bool, str]:
    """Run a supported external CLI coding agent.

    Parameters
    ----------
    agent_type:
        One of the supported keys in ``_AGENT_BINARY``.
    task_description:
        Prompt/task to hand to the CLI agent.
    working_directory:
        Directory to ``cd`` into before spawning the subprocess.
    timeout_seconds:
        Hard wall-clock cap. ``0`` disables the cap (not recommended).
    extra_args:
        Extra CLI args inserted before ``task_description``.
    env:
        Optional environment mapping merged over the parent env.
    subprocess_factory:
        Injectable hook for tests — when set, called with the argv/kwargs
        instead of ``asyncio.create_subprocess_exec``. Must return an
        awaitable yielding a process-like object exposing ``communicate``
        and ``returncode``.

    Returns
    -------
    (success, output)
        ``success`` is ``True`` only when the subprocess exits with code 0
        **and** the binary existed. Otherwise ``output`` carries a short
        diagnostic string (``"not_found"``, ``"timed_out"``,
        ``"exit=N"``, etc.) suitable for run-record storage.
    """
    if agent_type not in _AGENT_BINARY:
        return False, f"unsupported_agent:{agent_type}"

    binary_path = resolve_binary(agent_type)
    if binary_path is None:
        logger.info(
            "[cli_agent_bridge] Binary for %s not on PATH; caller should fall back",
            agent_type,
        )
        return False, "not_found"

    argv: list[str] = [binary_path]
    if extra_args:
        argv.extend(extra_args)
    argv.append(task_description)

    import os

    process_env = {**os.environ}
    if env:
        process_env.update(env)

    factory = subprocess_factory or asyncio.create_subprocess_exec

    try:
        proc = await factory(
            *argv,
            cwd=working_directory,
            env=process_env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return False, "not_found"
    except Exception as exc:
        logger.exception("[cli_agent_bridge] Failed to launch %s", agent_type)
        return False, f"launch_error:{type(exc).__name__}:{exc}"

    try:
        if timeout_seconds and timeout_seconds > 0:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_seconds
            )
        else:
            stdout, stderr = await proc.communicate()
    except TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        with contextlib.suppress(Exception):
            await proc.wait()
        return False, "timed_out"

    rc = proc.returncode or 0
    stdout_text = (stdout or b"").decode("utf-8", errors="replace")
    stderr_text = (stderr or b"").decode("utf-8", errors="replace")

    if rc != 0:
        logger.info(
            "[cli_agent_bridge] %s exited with code %d (stderr=%d bytes)",
            agent_type,
            rc,
            len(stderr_text),
        )
        merged = stdout_text + ("\n" + stderr_text if stderr_text else "")
        return False, merged or f"exit={rc}"

    return True, stdout_text
