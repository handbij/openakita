"""Tests for the setup_organization tool (definition + handler).

Validates:
1. get_resources returns agents, templates, tool_categories
2. create builds org with auto-generated edges and positions
3. preview returns structured text without creating
4. create_from_template delegates to OrgManager
5. agent_profile_id mapping and agent_source auto-set
6. Tool registered only when multi_agent_enabled
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def handler():
    """Create an OrgSetupHandler with a mocked agent."""
    from openakita.tools.handlers.org_setup import OrgSetupHandler
    mock_agent = MagicMock()
    return OrgSetupHandler(mock_agent)


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Create a temp data dir for OrgManager."""
    orgs_dir = tmp_path / "orgs"
    orgs_dir.mkdir()
    templates_dir = tmp_path / "org_templates"
    templates_dir.mkdir()
    return tmp_path


class TestGetResources:
    """Test action=get_resources."""

    def test_returns_agents(self, handler):
        result = json.loads(handler._get_resources())
        assert "agents" in result
        assert len(result["agents"]) > 0
        agent = result["agents"][0]
        assert "id" in agent
        assert "name" in agent
        assert "description" in agent

    def test_returns_templates(self, handler, tmp_data_dir):
        with patch("openakita.config.settings") as mock_settings:
            mock_settings.data_dir = tmp_data_dir
            result = json.loads(handler._get_resources())
        assert "templates" in result

    def test_returns_tool_categories(self, handler):
        result = json.loads(handler._get_resources())
        assert "tool_categories" in result
        cats = result["tool_categories"]
        assert "research" in cats
        assert "filesystem" in cats

    def test_returns_usage_hint(self, handler):
        result = json.loads(handler._get_resources())
        assert "usage_hint" in result

    def test_default_agent_in_list(self, handler):
        result = json.loads(handler._get_resources())
        agent_ids = [a["id"] for a in result["agents"]]
        assert "default" in agent_ids

    def test_code_assistant_in_list(self, handler):
        result = json.loads(handler._get_resources())
        agent_ids = [a["id"] for a in result["agents"]]
        assert "code-assistant" in agent_ids


class TestPreview:
    """Test action=preview."""

    def test_preview_returns_text(self, handler):
        params = {
            "action": "preview",
            "name": "测试团队",
            "core_business": "软件开发",
            "nodes": [
                {"role_title": "CTO", "level": 0, "department": "技术部",
                 "agent_profile_id": "architect"},
                {"role_title": "开发工程师", "level": 1, "department": "技术部",
                 "agent_profile_id": "code-assistant", "parent_role_title": "CTO"},
            ],
        }
        result = handler._preview(params)
        assert "测试团队" in result
        assert "CTO" in result
        assert "开发工程师" in result
        assert "架构师" in result or "architect" in result

    def test_preview_no_name_error(self, handler):
        result = handler._preview({"action": "preview", "nodes": [{"role_title": "A"}]})
        assert "❌" in result

    def test_preview_no_nodes_error(self, handler):
        result = handler._preview({"action": "preview", "name": "X"})
        assert "❌" in result

    def test_preview_shows_hierarchy(self, handler):
        params = {
            "action": "preview",
            "name": "测试",
            "nodes": [
                {"role_title": "Boss", "level": 0},
                {"role_title": "Worker", "level": 1, "parent_role_title": "Boss"},
            ],
        }
        result = handler._preview(params)
        assert "Boss" in result
        assert "Worker" in result
        assert "→" in result


class TestBuildOrgStructure:
    """Test the internal _build_org_structure method."""

    def test_auto_generates_node_ids(self, handler):
        params = {
            "nodes": [
                {"role_title": "CEO", "level": 0},
                {"role_title": "CTO", "level": 1, "parent_role_title": "CEO"},
            ],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        assert len(errors) == 0
        assert len(nodes) == 2
        assert all(n["id"].startswith("node_") for n in nodes)

    def test_auto_creates_edges(self, handler):
        params = {
            "nodes": [
                {"role_title": "CEO", "level": 0},
                {"role_title": "CTO", "level": 1, "parent_role_title": "CEO"},
                {"role_title": "CPO", "level": 1, "parent_role_title": "CEO"},
            ],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        assert len(errors) == 0
        assert len(edges) == 2
        assert all(e["edge_type"] == "hierarchy" for e in edges)

    def test_agent_source_set_correctly(self, handler):
        params = {
            "nodes": [
                {"role_title": "Dev", "level": 0, "agent_profile_id": "code-assistant"},
                {"role_title": "PM", "level": 0},
            ],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        dev = next(n for n in nodes if n["role_title"] == "Dev")
        pm = next(n for n in nodes if n["role_title"] == "PM")
        assert dev["agent_source"] == "ref:code-assistant"
        assert pm["agent_source"] == "local"

    def test_auto_assigns_positions(self, handler):
        params = {
            "nodes": [
                {"role_title": "A", "level": 0},
                {"role_title": "B", "level": 1},
                {"role_title": "C", "level": 1},
            ],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        positions = [n["position"] for n in nodes]
        assert all(p["x"] >= 0 for p in positions)
        level1_nodes = [n for n in nodes if n["level"] == 1]
        assert level1_nodes[0]["position"]["x"] != level1_nodes[1]["position"]["x"]

    def test_auto_assigns_tools_from_role(self, handler):
        params = {
            "nodes": [
                {"role_title": "CTO", "level": 0},
            ],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        assert len(nodes[0]["external_tools"]) > 0
        assert "research" in nodes[0]["external_tools"] or "filesystem" in nodes[0]["external_tools"]

    def test_error_on_missing_parent(self, handler):
        params = {
            "nodes": [
                {"role_title": "Worker", "level": 1, "parent_role_title": "NonExistent"},
            ],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        assert len(errors) > 0
        assert "NonExistent" in errors[0]

    def test_error_on_no_root(self, handler):
        params = {
            "nodes": [
                {"role_title": "Worker", "level": 1},
            ],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        assert any("根节点" in e for e in errors)

    def test_auto_assigns_avatar(self, handler):
        params = {
            "nodes": [{"role_title": "CTO / 技术总监", "level": 0}],
        }
        nodes, edges, errors = handler._build_org_structure(params)
        assert nodes[0].get("avatar") is not None


class TestCreate:
    """Test action=create."""

    @pytest.mark.asyncio
    async def test_create_success(self, handler, tmp_data_dir):
        with patch("openakita.config.settings") as mock_settings:
            mock_settings.data_dir = tmp_data_dir
            result = await handler._create({
                "name": "测试组织",
                "description": "测试描述",
                "core_business": "软件开发",
                "nodes": [
                    {"role_title": "CEO", "level": 0, "agent_profile_id": "default"},
                    {"role_title": "CTO", "level": 1, "parent_role_title": "CEO",
                     "agent_profile_id": "architect"},
                ],
            })
        assert "✅" in result
        assert "测试组织" in result
        assert "节点数: 2" in result
        assert "层级关系: 1" in result

    @pytest.mark.asyncio
    async def test_create_no_name_error(self, handler):
        result = await handler._create({"nodes": [{"role_title": "A", "level": 0}]})
        assert "❌" in result

    @pytest.mark.asyncio
    async def test_create_no_nodes_error(self, handler):
        result = await handler._create({"name": "X"})
        assert "❌" in result


class TestCreateFromTemplate:
    """Test action=create_from_template."""

    @pytest.mark.asyncio
    async def test_missing_template_id(self, handler):
        result = await handler._create_from_template({})
        assert "❌" in result
        assert "template_id" in result

    @pytest.mark.asyncio
    async def test_nonexistent_template(self, handler, tmp_data_dir):
        with patch("openakita.config.settings") as mock_settings:
            mock_settings.data_dir = tmp_data_dir
            result = await handler._create_from_template({"template_id": "nonexistent"})
        assert "❌" in result
        assert "不存在" in result


class TestToolDefinition:
    """Test tool definition structure."""

    def test_tool_definition_valid(self):
        from openakita.tools.definitions.org_setup import ORG_SETUP_TOOLS
        assert len(ORG_SETUP_TOOLS) == 1
        tool = ORG_SETUP_TOOLS[0]
        assert tool["name"] == "setup_organization"
        assert tool["category"] == "Organization"
        assert "input_schema" in tool
        assert "action" in tool["input_schema"]["properties"]

    def test_tool_has_examples(self):
        from openakita.tools.definitions.org_setup import ORG_SETUP_TOOLS
        tool = ORG_SETUP_TOOLS[0]
        assert "examples" in tool
        assert len(tool["examples"]) >= 2


class TestToolRegistration:
    """Test that the tool is properly exported and available."""

    def test_exported_from_definitions(self):
        from openakita.tools.definitions import ORG_SETUP_TOOLS
        assert len(ORG_SETUP_TOOLS) > 0

    def test_not_in_base_tools(self):
        from openakita.tools.definitions import BASE_TOOLS, ORG_SETUP_TOOLS
        base_names = {t["name"] for t in BASE_TOOLS}
        org_names = {t["name"] for t in ORG_SETUP_TOOLS}
        assert not base_names.intersection(org_names)

    def test_handler_has_create_handler(self):
        from openakita.tools.handlers.org_setup import create_handler
        assert callable(create_handler)

    def test_handler_accepts_agent(self):
        from openakita.tools.handlers.org_setup import create_handler
        mock_agent = MagicMock()
        handler_fn = create_handler(mock_agent)
        assert callable(handler_fn)
