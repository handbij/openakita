"""
Organization setup handler — create organizations through natural language.

Only registered when settings.multi_agent_enabled is True.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...core.agent import Agent

logger = logging.getLogger(__name__)


class OrgSetupHandler:
    """Handles the setup_organization tool with sub-actions."""

    TOOLS = ["setup_organization"]

    def __init__(self, agent: Agent):
        self.agent = agent

    async def handle(self, tool_name: str, params: dict[str, Any]) -> str:
        if tool_name != "setup_organization":
            return f"❌ Unknown tool: {tool_name}"

        action = params.get("action", "")
        if action == "get_resources":
            return self._get_resources()
        elif action == "preview":
            return self._preview(params)
        elif action == "create":
            return await self._create(params)
        elif action == "create_from_template":
            return await self._create_from_template(params)
        return f"❌ Unknown action: {action}. Valid: get_resources, preview, create, create_from_template"

    # ------------------------------------------------------------------
    # get_resources
    # ------------------------------------------------------------------

    def _get_resources(self) -> str:
        result: dict[str, Any] = {}

        # 1. Agent profiles
        try:
            from ...agents.presets import SYSTEM_PRESETS
            agents = []
            for p in SYSTEM_PRESETS:
                if getattr(p, "hidden", False):
                    continue
                agents.append({
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "category": getattr(p, "category", "general"),
                    "skills_summary": p.skills[:5] if p.skills else ["all (全能)"],
                })
            result["agents"] = agents
        except Exception as e:
            logger.warning(f"[OrgSetup] Failed to load agent presets: {e}")
            result["agents"] = []

        # 2. Templates
        try:
            manager = self._get_org_manager()
            if manager:
                result["templates"] = manager.list_templates()
            else:
                result["templates"] = []
        except Exception as e:
            logger.warning(f"[OrgSetup] Failed to load templates: {e}")
            result["templates"] = []

        # 3. Tool categories
        try:
            from ...orgs.tool_categories import TOOL_CATEGORIES
            result["tool_categories"] = {
                name: tools for name, tools in TOOL_CATEGORIES.items()
            }
        except Exception:
            result["tool_categories"] = {}

        # 4. Usage hint
        result["usage_hint"] = (
            "请根据以上信息为用户设计组织架构。"
            "为每个节点选择最合适的 agent（agent_profile_id），"
            "并配置合适的工具类目（external_tools）。"
            "信息不足时请向用户询问。"
        )

        return json.dumps(result, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # preview
    # ------------------------------------------------------------------

    def _preview(self, params: dict[str, Any]) -> str:
        name = params.get("name", "")
        if not name:
            return "❌ preview 需要提供 name（组织名称）"

        nodes_raw = params.get("nodes", [])
        if not nodes_raw:
            return "❌ preview 需要提供 nodes（节点列表）"

        nodes, edges, errors = self._build_org_structure(params)
        if errors:
            return "⚠️ 结构校验发现问题：\n" + "\n".join(f"- {e}" for e in errors)

        lines = [f"## 组织架构预览：{name}\n"]
        if params.get("core_business"):
            lines.append(f"核心业务：{params['core_business']}\n")

        lines.append(f"节点数：{len(nodes)}，层级关系：{len(edges)} 条\n")
        lines.append("### 节点明细\n")

        for n in sorted(nodes, key=lambda x: (x.get("level", 0), x.get("department", ""))):
            indent = "  " * n.get("level", 0)
            agent_id = n.get("agent_profile_id", "default")
            agent_label = self._get_agent_label(agent_id)
            dept = n.get("department", "")
            dept_str = f" [{dept}]" if dept else ""
            tools = n.get("external_tools", [])
            tools_str = f" 工具: {', '.join(tools)}" if tools else ""

            lines.append(
                f"{indent}- **{n['role_title']}**{dept_str} → Agent: {agent_label}"
                f"{tools_str}"
            )

        lines.append("\n### 层级关系\n")
        for e in edges:
            src = self._find_title_by_id(nodes, e["source"])
            tgt = self._find_title_by_id(nodes, e["target"])
            lines.append(f"- {src} → {tgt}")

        lines.append("\n---\n确认无误后请调用 create 正式创建。")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    async def _create(self, params: dict[str, Any]) -> str:
        name = params.get("name", "")
        if not name:
            return "❌ create 需要提供 name（组织名称）"

        nodes_raw = params.get("nodes", [])
        if not nodes_raw:
            return "❌ create 需要提供 nodes（节点列表）"

        nodes, edges, errors = self._build_org_structure(params)
        if errors:
            return "⚠️ 结构有问题，请修正后重试：\n" + "\n".join(f"- {e}" for e in errors)

        manager = self._get_org_manager()
        if manager is None:
            return "❌ 组织管理器未初始化，请确认服务已启动"

        org_data = {
            "name": name,
            "description": params.get("description", ""),
            "core_business": params.get("core_business", ""),
            "nodes": nodes,
            "edges": edges,
        }

        try:
            org = manager.create(org_data)
            node_count = len(org.nodes)
            edge_count = len(org.edges)
            return (
                f"✅ 组织「{org.name}」创建成功！\n"
                f"- ID: {org.id}\n"
                f"- 节点数: {node_count}\n"
                f"- 层级关系: {edge_count} 条\n"
                f"- 状态: dormant（需在前端启动）\n\n"
                f"用户可在组织编排页面查看和微调架构。"
            )
        except Exception as e:
            logger.error(f"[OrgSetup] Failed to create org: {e}", exc_info=True)
            return f"❌ 创建失败: {e}"

    # ------------------------------------------------------------------
    # create_from_template
    # ------------------------------------------------------------------

    async def _create_from_template(self, params: dict[str, Any]) -> str:
        template_id = params.get("template_id", "")
        if not template_id:
            return "❌ create_from_template 需要提供 template_id"

        manager = self._get_org_manager()
        if manager is None:
            return "❌ 组织管理器未初始化，请确认服务已启动"

        overrides = params.get("overrides") or {}

        try:
            org = manager.create_from_template(template_id, overrides)
            return (
                f"✅ 从模板「{template_id}」创建组织成功！\n"
                f"- 名称: {org.name}\n"
                f"- ID: {org.id}\n"
                f"- 节点数: {len(org.nodes)}\n"
                f"- 状态: dormant（需在前端启动）"
            )
        except FileNotFoundError:
            return f"❌ 模板 '{template_id}' 不存在。请先调用 get_resources 查看可用模板。"
        except Exception as e:
            logger.error(f"[OrgSetup] Failed to create from template: {e}", exc_info=True)
            return f"❌ 创建失败: {e}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_org_manager(self):
        """Get OrgManager from the running app or create one."""
        from ...config import settings
        try:
            from ...orgs.manager import OrgManager
            return OrgManager(settings.data_dir)
        except Exception as e:
            logger.error(f"[OrgSetup] Cannot get OrgManager: {e}")
            return None

    def _build_org_structure(
        self, params: dict[str, Any]
    ) -> tuple[list[dict], list[dict], list[str]]:
        """Build nodes and edges from params, auto-generating IDs and layout.

        Returns (nodes, edges, errors).
        """
        from ...orgs.tool_categories import get_preset_for_role, get_avatar_for_role

        nodes_raw = params.get("nodes", [])
        errors: list[str] = []
        nodes: list[dict] = []
        title_to_id: dict[str, str] = {}

        # Pass 1: create nodes with IDs
        for i, nr in enumerate(nodes_raw):
            title = nr.get("role_title", "").strip()
            if not title:
                errors.append(f"节点 #{i + 1} 缺少 role_title")
                continue

            node_id = f"node_{uuid.uuid4().hex[:12]}"
            title_to_id[title] = node_id

            level = nr.get("level", 0)
            agent_profile_id = nr.get("agent_profile_id")
            agent_source = "local"
            if agent_profile_id:
                agent_source = f"ref:{agent_profile_id}"

            ext_tools = nr.get("external_tools")
            if not ext_tools:
                ext_tools = get_preset_for_role(title)

            avatar = get_avatar_for_role(title)

            node = {
                "id": node_id,
                "role_title": title,
                "role_goal": nr.get("role_goal", ""),
                "department": nr.get("department", ""),
                "level": level,
                "agent_profile_id": agent_profile_id,
                "agent_source": agent_source,
                "external_tools": ext_tools,
                "custom_prompt": nr.get("custom_prompt", ""),
                "avatar": avatar,
                "position": {"x": 0, "y": 0},
            }
            nodes.append(node)

        if errors:
            return nodes, [], errors

        # Pass 2: calculate layout positions (tree layout)
        self._calculate_positions(nodes)

        # Pass 3: create edges from parent_role_title
        edges: list[dict] = []
        for nr, node in zip(nodes_raw, nodes):
            parent_title = nr.get("parent_role_title", "").strip()
            if not parent_title:
                continue
            parent_id = title_to_id.get(parent_title)
            if parent_id is None:
                errors.append(
                    f"节点「{node['role_title']}」的上级「{parent_title}」未找到"
                )
                continue
            edge_id = f"edge_{uuid.uuid4().hex[:12]}"
            edges.append({
                "id": edge_id,
                "source": parent_id,
                "target": node["id"],
                "edge_type": "hierarchy",
                "bidirectional": True,
            })

        # Validate: root nodes should have level 0
        root_nodes = [n for n in nodes if n["level"] == 0]
        if not root_nodes:
            errors.append("至少需要一个 level=0 的根节点")

        return nodes, edges, errors

    def _calculate_positions(self, nodes: list[dict]) -> None:
        """Assign canvas positions based on level (tree layout)."""
        by_level: dict[int, list[dict]] = {}
        for n in nodes:
            level = n.get("level", 0)
            by_level.setdefault(level, []).append(n)

        y_spacing = 180
        x_spacing = 250

        for level, level_nodes in sorted(by_level.items()):
            count = len(level_nodes)
            total_width = (count - 1) * x_spacing
            start_x = 400 - total_width // 2

            for i, node in enumerate(level_nodes):
                node["position"] = {
                    "x": start_x + i * x_spacing,
                    "y": level * y_spacing,
                }

    def _get_agent_label(self, agent_id: str) -> str:
        """Get human-readable label for an agent ID."""
        try:
            from ...agents.presets import SYSTEM_PRESETS
            for p in SYSTEM_PRESETS:
                if p.id == agent_id:
                    return f"{p.name} ({p.id})"
        except Exception:
            pass
        return agent_id or "default"

    def _find_title_by_id(self, nodes: list[dict], node_id: str) -> str:
        for n in nodes:
            if n["id"] == node_id:
                return n["role_title"]
        return node_id


def create_handler(agent: Agent):
    """Factory function following the project convention."""
    handler = OrgSetupHandler(agent)
    return handler.handle
