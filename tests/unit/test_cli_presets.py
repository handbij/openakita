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


def test_codex_writer_preset_exists():
    preset = get_preset_by_id("codex-writer")
    assert preset is not None
    assert preset.type == AgentType.EXTERNAL_CLI
    assert preset.cli_provider_id == CliProviderId.CODEX
    assert preset.cli_permission_mode == CliPermissionMode.WRITE
    assert preset.fallback_profile_id == "local-goose"
    assert preset.category == "cli-agents"


def test_local_goose_preset_exists():
    preset = get_preset_by_id("local-goose")
    assert preset is not None
    assert preset.type == AgentType.EXTERNAL_CLI
    assert preset.cli_provider_id == CliProviderId.GOOSE
    assert preset.cli_permission_mode == CliPermissionMode.WRITE
    assert preset.fallback_profile_id == "default"  # goose has no further CLI sibling
    assert preset.category == "cli-agents"


def test_cli_preset_fallback_chain_forms_a_line():
    """claude-code-pair -> codex-writer -> local-goose -> default -- no cycles."""
    chain = []
    current = "claude-code-pair"
    seen = set()
    while current and current not in seen:
        seen.add(current)
        chain.append(current)
        p = get_preset_by_id(current)
        current = p.fallback_profile_id if p else None
    assert chain == ["claude-code-pair", "codex-writer", "local-goose", "default"]


def test_multi_cli_planner_preset_exists():
    preset = get_preset_by_id("multi-cli-planner")
    assert preset is not None
    assert preset.type == AgentType.SYSTEM  # native ReAct, not a CLI
    assert preset.cli_provider_id is None
    assert preset.category == "cli-agents"
    assert preset.fallback_profile_id == "default"


def test_multi_cli_planner_allows_three_cli_presets_as_delegation_targets():
    preset = get_preset_by_id("multi-cli-planner")
    rules = preset.permission_rules
    assert rules, "multi-cli-planner must declare permission_rules"

    # Extract the allow-list for `delegate_to_agent` — each rule has shape
    # {"permission": "delegate_to_agent", "pattern": <profile_id>, "action": "allow"}
    allowed = {
        r["pattern"]
        for r in rules
        if r.get("permission") == "delegate_to_agent" and r.get("action") == "allow"
    }
    assert allowed == {"claude-code-pair", "codex-writer", "local-goose"}


def test_multi_cli_planner_denies_other_profiles_by_default():
    """A catch-all deny rule must be present so the allow-list is exclusive."""
    preset = get_preset_by_id("multi-cli-planner")
    rules = preset.permission_rules
    has_catch_all_deny = any(
        r.get("permission") == "delegate_to_agent"
        and r.get("pattern") == "*"
        and r.get("action") == "deny"
        for r in rules
    )
    assert has_catch_all_deny, \
        "multi-cli-planner needs a catch-all `delegate_to_agent: * -> deny` rule"
