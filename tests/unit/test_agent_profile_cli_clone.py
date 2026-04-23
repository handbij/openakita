from __future__ import annotations

from datetime import datetime

from openakita.agents.cli_detector import CliProviderId
from openakita.agents.profile import (
    AgentProfile,
    AgentType,
    CliPermissionMode,
    SkillsMode,
)


def test_derive_ephemeral_from_external_cli_preserves_cli_fields():
    base = AgentProfile(
        id="claude-code-pair",
        name="Claude Code Pair",
        type=AgentType.EXTERNAL_CLI,
        cli_provider_id=CliProviderId.CLAUDE_CODE,
        cli_permission_mode=CliPermissionMode.WRITE,
        cli_env={"CLAUDE_CONFIG_DIR": "${HOME}/.claude"},
        fallback_profile_id="codex-writer",
        custom_prompt="base prompt",
    )

    clone = AgentProfile.derive_ephemeral_from(
        base,
        id="ephemeral_claude_1",
        name="Claude clone",
        custom_prompt="base prompt\n\nextra",
        created_by="test",
    )

    assert clone.id == "ephemeral_claude_1"
    assert clone.type == AgentType.EXTERNAL_CLI
    assert clone.cli_provider_id == CliProviderId.CLAUDE_CODE
    assert clone.cli_permission_mode == CliPermissionMode.WRITE
    assert clone.cli_env == {"CLAUDE_CONFIG_DIR": "${HOME}/.claude"}
    assert clone.fallback_profile_id == "codex-writer"
    assert clone.ephemeral is True
    assert clone.inherit_from == "claude-code-pair"
    assert clone.custom_prompt == "base prompt\n\nextra"


def test_derive_ephemeral_from_native_profile_becomes_dynamic():
    base = AgentProfile(
        id="code-assistant",
        name="Code Assistant",
        type=AgentType.SYSTEM,
        skills=["run-shell"],
        skills_mode=SkillsMode.INCLUSIVE,
    )

    clone = AgentProfile.derive_ephemeral_from(
        base,
        id="ephemeral_code_1",
        created_by="test",
    )

    assert clone.type == AgentType.DYNAMIC
    assert clone.skills == ["run-shell"]
    assert clone.skills is not base.skills
    assert clone.ephemeral is True


def test_derive_ephemeral_from_enforces_clone_invariants_after_overrides():
    base = AgentProfile(
        id="code-assistant",
        name="Code Assistant",
        type=AgentType.SYSTEM,
    )

    clone = AgentProfile.derive_ephemeral_from(
        base,
        id="ephemeral_code_2",
        type=AgentType.EXTERNAL_CLI,
        ephemeral=False,
        inherit_from="wrong-parent",
    )

    assert clone.id == "ephemeral_code_2"
    assert clone.type == AgentType.DYNAMIC
    assert clone.ephemeral is True
    assert clone.inherit_from == "code-assistant"


def test_derive_ephemeral_from_external_cli_type_cannot_be_overridden():
    base = AgentProfile(
        id="claude-code-pair",
        name="Claude Code Pair",
        type=AgentType.EXTERNAL_CLI,
        cli_provider_id=CliProviderId.CLAUDE_CODE,
    )

    clone = AgentProfile.derive_ephemeral_from(
        base,
        id="ephemeral_claude_2",
        type=AgentType.DYNAMIC,
    )

    assert clone.type == AgentType.EXTERNAL_CLI


def test_derive_ephemeral_from_uses_fresh_created_at():
    base = AgentProfile(
        id="code-assistant",
        name="Code Assistant",
        type=AgentType.SYSTEM,
        created_at="2000-01-01T00:00:00+00:00",
    )

    clone = AgentProfile.derive_ephemeral_from(
        base,
        id="ephemeral_code_3",
    )

    assert clone.created_at != base.created_at
    datetime.fromisoformat(clone.created_at)
