"""Shared helpers for provider adapters.

stream_cli_subprocess() spawns a subprocess with asyncio.create_subprocess_exec
(shell=False always), calls the caller's on_spawn hook synchronously so the
runner can track the process for signal escalation, then yields stdout lines
until EOF or cancellation.

write_mcp_config() emits an MCP server config for the two CLIs that read one —
Codex (`config.toml`) and Claude Code (`mcp.json`). Lives here so neither
adapter has to reach into the other.

Streaming-only. Does NOT replace the blocking _run_cmd helpers in
tools/handlers/opencli.py — those are one-shot Popen.communicate calls.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from openakita.tools.mcp_catalog import MCPCatalog

logger = logging.getLogger(__name__)


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


def write_mcp_config(
    dst_dir: Path,
    mcp_servers: tuple[str, ...],
    *,
    fmt: str,
) -> Path | None:
    """Write an MCP configuration file under `dst_dir` in the requested shape.

    - `fmt="toml"` -> writes `config.toml` with `[mcp_servers.<id>]` sections
      (Codex expects this inside `$CODEX_HOME`).
    - `fmt="json"` -> writes `mcp.json` with a `{"mcpServers": {…}}` object
      (Claude Code's `--mcp-config` contract).

    Returns None when `mcp_servers` is empty — caller should skip the flag.
    The concrete server command + args come from MCPCatalog.get_server(name);
    a missing catalog entry is logged and skipped (the CLI will error naturally
    if it needs that server).
    """
    if not mcp_servers:
        return None

    try:
        catalog = MCPCatalog()
    except Exception as exc:
        logger.warning("write_mcp_config: catalog unavailable: %s", exc)
        catalog = None

    launch_specs: dict[str, dict] = {}
    for server_id in mcp_servers:
        spec = None
        if catalog is not None:
            info = catalog.get_server(server_id)
            if info is not None and info.command:
                spec = {
                    "command": info.command,
                    "args": list(info.args),
                    "env": dict(info.env),
                }
        if spec is None:
            logger.warning("write_mcp_config: no catalog entry for %r", server_id)
            continue
        launch_specs[server_id] = spec

    if not launch_specs:
        return None

    if fmt == "json":
        path = dst_dir / "mcp.json"
        path.write_text(json.dumps({"mcpServers": launch_specs}, indent=2))
        return path

    if fmt == "toml":
        path = dst_dir / "config.toml"
        lines: list[str] = []
        for server_id, spec in launch_specs.items():
            section = server_id.replace("-", "_")
            lines.append(f"[mcp_servers.{section}]")
            cmd = spec.get("command")
            args = spec.get("args") or []
            env = spec.get("env") or {}
            if cmd:
                lines.append(f'command = {json.dumps(cmd)}')
            if args:
                lines.append(f"args = {json.dumps(list(args))}")
            if env:
                lines.append("env = { " + ", ".join(
                    f'{k} = {json.dumps(v)}' for k, v in env.items()
                ) + " }")
            lines.append("")
        path.write_text("\n".join(lines))
        return path

    raise ValueError(f"unknown fmt={fmt!r}")
