# tests/unit/test_cli_providers_codex.py
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openakita.agents.cli_providers import PROVIDERS
from openakita.agents.cli_detector import CliProviderId
from openakita.agents.cli_runner import CliRunRequest, ExitReason, ProviderRunResult
from openakita.agents.profile import AgentProfile, AgentType, CliPermissionMode


def _make_profile(**overrides) -> AgentProfile:
    base = dict(
        id="codex-writer",
        name="Codex Writer",
        type=AgentType.EXTERNAL_CLI,
        cli_provider_id=CliProviderId.CODEX,
        cli_permission_mode=CliPermissionMode.PLAN,
    )
    base.update(overrides)
    return AgentProfile(**base)


def _make_request(profile, *, cwd=Path("/tmp"), resume_id=None,
                  system_prompt_extra="", mcp_servers=()):
    return CliRunRequest(
        message="Refactor module X",
        resume_id=resume_id,
        profile=profile,
        cwd=cwd,
        cancelled=asyncio.Event(),
        session=None,
        system_prompt_extra=system_prompt_extra,
        mcp_servers=mcp_servers,
    )


def test_provider_registered_under_codex():
    assert CliProviderId.CODEX in PROVIDERS


def test_build_argv_base_flags():
    from openakita.agents.cli_providers import codex

    with patch.object(codex, "_resolve_binary", return_value="/usr/bin/codex"):
        argv = PROVIDERS[CliProviderId.CODEX].build_argv(
            _make_request(_make_profile())
        )

    assert argv[0] == "/usr/bin/codex"
    assert "exec" in argv
    assert "--json" in argv
    # Message is the trailing positional
    assert argv[-1] == "Refactor module X"


def test_build_argv_write_mode_adds_skip_checks():
    """In WRITE mode Codex skips the git-repo-dirty check so it can edit files."""
    from openakita.agents.cli_providers import codex

    profile = _make_profile(cli_permission_mode=CliPermissionMode.WRITE)
    with patch.object(codex, "_resolve_binary", return_value="/usr/bin/codex"):
        argv = PROVIDERS[CliProviderId.CODEX].build_argv(_make_request(profile))

    assert "--skip-git-repo-check" in argv


def test_build_argv_resume_uses_session_id():
    from openakita.agents.cli_providers import codex

    with patch.object(codex, "_resolve_binary", return_value="/usr/bin/codex"):
        argv = PROVIDERS[CliProviderId.CODEX].build_argv(
            _make_request(_make_profile(), resume_id="codex-session-abc")
        )

    # Codex resume takes a session id via a positional or --session flag;
    # the adapter emits `--session <id>` for grep-friendly test assertions.
    assert "--session" in argv
    assert argv[argv.index("--session") + 1] == "codex-session-abc"


def test_build_env_sets_codex_home_to_per_turn_tempdir():
    from openakita.agents.cli_providers import codex

    profile = _make_profile()
    req = _make_request(profile, mcp_servers=("web-search",))
    with patch.object(codex, "_resolve_binary", return_value="/usr/bin/codex"):
        env = PROVIDERS[CliProviderId.CODEX].build_env(req)

    assert "CODEX_HOME" in env
    # Path exists only for the scope of this turn — we don't check existence here;
    # that's covered by the end-to-end run test. We check the value is absolute.
    assert os.path.isabs(env["CODEX_HOME"])


def test_write_mcp_config_toml_contains_server_sections(tmp_path):
    from openakita.agents.cli_providers.codex import write_mcp_config

    fake_info = MagicMock(command="npx", args=["-y", "pkg"], env={})
    with patch("openakita.agents.cli_providers.codex.MCPCatalog") as Catalog:
        Catalog.return_value.get_server = MagicMock(return_value=fake_info)
        path = write_mcp_config(tmp_path, ("web-search", "github"), fmt="toml")

    assert path is not None
    text = path.read_text()
    assert "[mcp_servers.web_search]" in text or "[mcp_servers.web-search]" in text
    assert "[mcp_servers.github]" in text


def test_write_mcp_config_json_contains_server_keys(tmp_path):
    from openakita.agents.cli_providers.codex import write_mcp_config

    fake_info = MagicMock(command="npx", args=["-y", "pkg"], env={})
    with patch("openakita.agents.cli_providers.codex.MCPCatalog") as Catalog:
        Catalog.return_value.get_server = MagicMock(return_value=fake_info)
        path = write_mcp_config(tmp_path, ("web-search", "github"), fmt="json")

    assert path is not None
    obj = json.loads(path.read_text())
    assert "mcpServers" in obj
    assert set(obj["mcpServers"].keys()) == {"web-search", "github"}


def test_write_mcp_config_returns_none_for_empty():
    from openakita.agents.cli_providers.codex import write_mcp_config

    assert write_mcp_config(Path("/tmp"), (), fmt="toml") is None
    assert write_mcp_config(Path("/tmp"), (), fmt="json") is None


def test_session_root_is_codex_sessions():
    from openakita.agents.cli_providers import codex

    assert codex.SESSION_ROOT == Path.home() / ".codex" / "sessions"
