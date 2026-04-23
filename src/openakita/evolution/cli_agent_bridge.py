"""External coding-CLI agent bridge.

Routes supported external coding agent keys (``claude-code`` / ``codex`` /
``goose``) through configured external CLI agent profiles. The bridge keeps the
self-improvement orchestrator's public call shape stable while letting
``AgentFactory`` own profile fields, fallbacks, limiter settings, environment
filtering, MCP filtering, and ``ExternalCliAgent`` lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from openakita.agents.factory import AgentFactory
from openakita.agents.profile import get_profile_store

logger = logging.getLogger(__name__)


_AGENT_PROFILE: dict[str, str] = {
    "claude-code": "claude-code-pair",
    "codex": "codex-writer",
    "goose": "local-goose",
}


def resolve_profile_id(agent_type: str) -> str | None:
    """Return the configured profile id for ``agent_type`` or ``None``."""
    return _AGENT_PROFILE.get(agent_type)


async def _cleanup_agent(agent: Any, method_name: str, profile_id: str) -> None:
    cleanup = getattr(agent, method_name, None)
    if cleanup is None:
        return
    try:
        await cleanup()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning(
            "[cli_agent_bridge] %s cleanup failed for profile-backed agent %s",
            method_name,
            profile_id,
            exc_info=True,
        )


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
        One of the supported keys in ``_AGENT_PROFILE``.
    task_description:
        Prompt/task to hand to the CLI agent.
    working_directory:
        Directory passed to the profile-backed agent as a cwd override.
    timeout_seconds:
        Hard wall-clock cap. ``0`` disables the cap (not recommended).
    extra_args:
        Deprecated compatibility parameter. When present, values are folded
        into prompt text before ``task_description`` instead of being passed as
        CLI argv.
    env:
        Deprecated compatibility parameter. Profile-backed execution owns
        environment through ``AgentProfile.cli_env`` and adapter filtering.
    subprocess_factory:
        Deprecated compatibility parameter. Ignored by profile-backed execution.

    Returns
    -------
    (success, output)
        ``success`` is ``True`` when the profile-backed agent reports success.
        Otherwise ``output`` carries a short diagnostic string suitable for
        run-record storage.
    """
    profile_id = resolve_profile_id(agent_type)
    if profile_id is None:
        return False, f"unsupported_agent:{agent_type}"

    store = get_profile_store()
    profile = store.get(profile_id)
    if profile is None:
        logger.info(
            "[cli_agent_bridge] Profile %s not configured; caller should fall back",
            profile_id,
        )
        return False, "not_found"

    prompt = task_description
    if extra_args:
        prompt = " ".join(extra_args) + "\n\n" + task_description

    try:
        factory = AgentFactory()
        agent = await factory.create(profile)
    except Exception as exc:
        logger.exception("[cli_agent_bridge] Failed to create profile-backed agent %s", profile_id)
        return False, f"create_error:{type(exc).__name__}:{exc}"

    try:
        coro = agent.execute_task_from_message(prompt, cwd=working_directory)
        if timeout_seconds:
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
        else:
            result = await coro
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        await _cleanup_agent(agent, "cancel", profile_id)
        return False, "timed_out"
    except Exception as exc:
        logger.exception("[cli_agent_bridge] Profile-backed agent %s failed", profile_id)
        return False, f"execute_error:{type(exc).__name__}:{exc}"
    finally:
        await _cleanup_agent(agent, "shutdown", profile_id)

    if isinstance(result, dict):
        if result.get("success"):
            return True, str(result.get("data") or "")
        return False, str(result.get("error") or result.get("data") or "agent_failed")

    success = bool(getattr(result, "success", False))
    if success:
        return True, str(getattr(result, "data", ""))
    return False, str(
        getattr(result, "error", None) or getattr(result, "data", None) or "agent_failed"
    )
