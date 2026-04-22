from openakita.agents.profile import AgentProfile, AgentType


def test_agent_profile_to_dict_exposes_definition_metadata():
    profile = AgentProfile(
        id="planner",
        name="Planner",
        type=AgentType.SYSTEM,
        role="coordinator",
    )

    payload = profile.to_dict()
    assert payload["origin"] == "system"
    assert payload["namespace"] == "system"
    assert payload["definition_id"].endswith("agent_definition:planner")


from openakita.agents.cli_detector import CliProviderId
from openakita.agents.profile import (
    AgentProfile,
    AgentType,
    CliPermissionMode,
    FilterMode,
)


def test_agent_type_has_external_cli_member():
    assert AgentType.EXTERNAL_CLI.value == "external_cli"
    assert AgentType("external_cli") is AgentType.EXTERNAL_CLI


def test_filter_mode_replaces_raw_strings():
    assert FilterMode.ALL.value == "all"
    assert FilterMode.INCLUSIVE.value == "inclusive"
    assert FilterMode.EXCLUSIVE.value == "exclusive"


def test_cli_permission_mode_values():
    assert CliPermissionMode.PLAN.value == "plan"
    assert CliPermissionMode.WRITE.value == "write"


def test_agent_profile_defaults_for_cli_fields():
    p = AgentProfile(id="x", name="x")
    assert p.cli_provider_id is None
    assert p.cli_permission_mode == CliPermissionMode.WRITE


def test_agent_profile_roundtrip_with_cli_fields():
    p = AgentProfile(
        id="cli-1",
        name="cli",
        type=AgentType.EXTERNAL_CLI,
        cli_provider_id=CliProviderId.CLAUDE_CODE,
        cli_permission_mode=CliPermissionMode.PLAN,
    )
    d = p.to_dict()
    assert d["cli_provider_id"] == "claude_code"
    assert d["cli_permission_mode"] == "plan"
    reloaded = AgentProfile.from_dict(d)
    assert reloaded.cli_provider_id == CliProviderId.CLAUDE_CODE
    assert reloaded.cli_permission_mode == CliPermissionMode.PLAN


def test_from_dict_accepts_legacy_mode_strings():
    d = {"id": "x", "name": "x", "tools_mode": "inclusive",
         "mcp_mode": "all", "plugins_mode": "exclusive"}
    p = AgentProfile.from_dict(d)
    assert p.tools_mode == FilterMode.INCLUSIVE
    assert p.mcp_mode == FilterMode.ALL
    assert p.plugins_mode == FilterMode.EXCLUSIVE


def test_derive_ephemeral_from_clones_cli_fields():
    base = AgentProfile(
        id="claude-code-pair",
        name="Claude Pair",
        type=AgentType.EXTERNAL_CLI,
        cli_provider_id=CliProviderId.CLAUDE_CODE,
        cli_permission_mode=CliPermissionMode.WRITE,
        mcp_servers=["web-search"],
        mcp_mode=FilterMode.INCLUSIVE,
        permission_rules=[{"permission": "edit", "pattern": "*", "action": "allow"}],
    )
    eph = AgentProfile.derive_ephemeral_from(
        base, id="eph-1", cli_permission_mode=CliPermissionMode.PLAN,
    )
    assert eph.id == "eph-1"
    assert eph.ephemeral is True
    assert eph.inherit_from == "claude-code-pair"
    assert eph.cli_provider_id == CliProviderId.CLAUDE_CODE
    assert eph.cli_permission_mode == CliPermissionMode.PLAN
    assert eph.mcp_servers == ["web-search"]
    assert eph.mcp_mode == FilterMode.INCLUSIVE
    assert eph.permission_rules == base.permission_rules
    # Must not share mutable state
    assert eph.mcp_servers is not base.mcp_servers
