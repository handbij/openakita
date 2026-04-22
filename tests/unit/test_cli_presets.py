"""Tests for CLI-backed system presets."""
from __future__ import annotations

from openakita.agents.presets import SYSTEM_PRESETS, get_preset_by_id
from openakita.agents.profile import (
    AgentProfile,
    AgentType,
    CliPermissionMode,
)
from openakita.agents.cli_detector import CliProviderId


def test_claude_code_pair_preset_exists():
    preset = get_preset_by_id("claude-code-pair")
    assert preset is not None
    assert preset.type == AgentType.EXTERNAL_CLI
    assert preset.cli_provider_id == CliProviderId.CLAUDE_CODE
    assert preset.cli_permission_mode == CliPermissionMode.WRITE
    assert preset.fallback_profile_id == "codex-writer"
    assert preset.category == "cli-agents"
    assert preset.created_by == "system"
    assert preset.icon  # non-empty
