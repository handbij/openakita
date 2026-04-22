"""
OrgIdentity — 节点身份解析与 MCP 配置管理

四级身份继承：
  Level 0: 零配置引用（全局 SOUL + AGENT + AgentProfile.custom_prompt）
  Level 1: 有 ROLE.md（全局 SOUL + AGENT + ROLE.md）
  Level 2: ROLE.md + 覆盖 AGENT.md
  Level 3: 完全独立身份（SOUL + AGENT + ROLE）

MCP 叠加继承：
  最终 MCP = 全局已启用 + AgentProfile 关联 + 节点额外 - 节点排除
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .models import EdgeType, Organization, OrgNode

logger = logging.getLogger(__name__)


@dataclass
class ResolvedIdentity:
    soul: str
    agent: str
    role: str
    level: int


class OrgIdentity:
    """Resolve per-node identity files with layered inheritance."""

    def __init__(self, org_dir: Path, global_identity_dir: Path | None = None) -> None:
        self._org_dir = org_dir
        self._nodes_dir = org_dir / "nodes"
        self._global_identity_dir = global_identity_dir

    def resolve(self, node: OrgNode, org: Organization) -> ResolvedIdentity:
        """Resolve the full identity for a node using 4-level inheritance."""
        node_identity_dir = self._nodes_dir / node.id / "identity"

        soul = self._read_file(node_identity_dir / "SOUL.md") or self._global_soul()
        agent = self._read_file(node_identity_dir / "AGENT.md") or self._global_agent()
        role = self._read_file(node_identity_dir / "ROLE.md")

        level = 3
        if role:
            if self._read_file(node_identity_dir / "AGENT.md"):
                level = 3 if self._read_file(node_identity_dir / "SOUL.md") else 2
            else:
                level = 1
        else:
            level = 0
            if node.agent_profile_id:
                role = self._get_profile_prompt(node.agent_profile_id) or ""
            if not role and node.custom_prompt:
                role = node.custom_prompt
            if not role:
                role = self._auto_generate_role(node)

        return ResolvedIdentity(soul=soul, agent=agent, role=role, level=level)

    def build_org_context_prompt(
        self, node: OrgNode, org: Organization, identity: ResolvedIdentity,
        blackboard_summary: str = "",
        dept_summary: str = "",
        node_summary: str = "",
        pending_messages: str = "",
        policy_index: str = "",
        project_tasks_summary: str = "",
        root_intent: str = "",
    ) -> str:
        """Build the full organization context prompt for a node agent.

        Does NOT include identity.soul or identity.agent — those contain
        generic solo-agent philosophies (Ralph Wiggum "never give up",
        "solve everything yourself") that directly conflict with the
        organizational delegation model.  A minimal identity declaration
        is generated instead.
        """
        parent = org.get_parent(node.id)
        children = org.get_children(node.id)
        is_root = (node.level == 0 or not parent)

        connected_peers: list[str] = []
        for e in org.edges:
            if e.edge_type != EdgeType.HIERARCHY:
                if e.source == node.id:
                    peer = org.get_node(e.target)
                    if peer:
                        connected_peers.append(f"**{peer.role_title}** (id: `{peer.id}`)")
                elif e.target == node.id:
                    peer = org.get_node(e.source)
                    if peer:
                        connected_peers.append(f"**{peer.role_title}** (id: `{peer.id}`)")

        org_chart = self._build_brief_org_chart(org)

        parts: list[str] = []

        # BUG-3：用户当前指令贴在最前（最高可见性），让所有子节点都能看到
        # 用户原话的范围/字数/格式约束，避免上级转述时漂移。
        # 仅当 root_intent 非空且当前命令仍在进行时由调用方传入。
        if root_intent:
            _intent_brief = root_intent.strip()
            if len(_intent_brief) > 400:
                _intent_brief = _intent_brief[:400] + "..."
            parts.append(
                "## Current user instruction (highest priority — do not exceed)\n"
                f"\"{_intent_brief}\"\n"
                "Before issuing any subtask, writing any code, or producing any deliverable, "
                "verify that your output strictly falls within the scope, word count, and format constraints of this instruction. "
                "If it conflicts with your superior's paraphrase, the user's original wording takes precedence."
            )

        # Compact identity declaration (replaces full SOUL.md + AGENT.md)
        parts.append(
            f"# OpenAkita Organization Agent\n\n"
            f"You are the **{node.role_title}** in \"{org.name}\" (your node id: `{node.id}`). "
            f"You are an AI Agent powered by OpenAkita.\n\n"
            f"**Critical: whenever a tool parameter requires a target node (`to_node` / `node_id` / `target_node_id`), "
            f"you must supply the exact node id shown in backticks in the org chart below (e.g. `{node.id}`). "
            f"Do not use a role name or your own id. If unsure, call `org_get_org_chart` or "
            f"`org_find_colleague` first.**\n\n"
            f"## Core principles\n"
            f"- Honest: do not fabricate information; state clearly when uncertain\n"
            f"- Safe: do not perform actions that could cause harm\n"
            f"- Collaborative: you are part of a team — achieve goals through teamwork, not alone"
        )

        # Role description
        dept_label = f" ({node.department})" if node.department else ""
        role_section = f"## Your organization role\nYou hold the position of **{node.role_title}**{dept_label} in \"{org.name}\"."
        if identity.role:
            role_section += f"\n{identity.role}"
        parts.append(role_section)

        if org.core_business:
            persona_label = org.user_persona.label if org.user_persona else "commander"
            biz_section = f"## Core business\n{org.core_business}"
            if is_root:
                biz_section += (
                    f"\n\n### Continuous work responsibility\n"
                    f"You are the top-level owner of this organization. You have **ongoing responsibility** to advance the core business above:\n"
                    f"- Independently set work strategies and phase goals — you do not need to wait for {persona_label} to issue instructions step by step\n"
                    f"- Proactively break down tasks, delegate to subordinates, track progress, and adjust\n"
                    f"- When blocked or facing a major decision, record it on the blackboard — but do not stop and wait for approval; execute your best judgment first\n"
                    f"- {persona_label}'s instructions are directional adjustments and supplements; day-to-day work is fully your responsibility\n"
                    f"- Each time you are activated, review blackboard progress first, then advance the next step"
                )
            else:
                biz_section += (
                    "\n\nThe above is the organization's core business direction. Your work should align with it. "
                    "Actively support your superior's task assignments, report promptly when done, and ask for the next step."
                )
            parts.append(biz_section)

        parts.append(
            "## AI efficiency mindset\n"
            "You are an AI Agent — **not constrained by human working hours or physical limits**. Core efficiency principles:\n"
            "- Information gathering, research, and analysis tasks should complete in **minutes** — do not plan in days or weeks\n"
            "- Use **minutes and hours** as time units when creating work plans\n"
            "- When delegating tasks, set reasonable AI-level deadlines (typically 5–30 minutes)\n"
            "- Do not wait. Do not schedule \"do it tomorrow\" — execute immediately\n"
            "- As soon as one task is done, begin the next — maintain a continuous work rhythm"
        )

        parts.append(f"## Organization chart overview\n{org_chart}\n"
                     f"For full details call org_get_org_chart; when unsure who to contact, use org_find_colleague.")

        # Relationships with enhanced delegation guidance
        rel_parts = []
        persona = org.user_persona
        # Always surface the caller's own identity first so the LLM can never
        # delegate/send to itself by mistake — pairs with the strict
        # resolve_reference guard in OrgToolHandler._resolve_node_refs.
        rel_parts.append(
            f"- Yourself: **{node.role_title}** (id: `{node.id}`) ← do not send messages or tasks to this id"
        )
        if parent:
            rel_parts.append(f"- Direct superior: **{parent.role_title}** (id: `{parent.id}`)")
        elif persona and persona.label:
            desc = f" ({persona.description})" if persona.description else " (user)"
            rel_parts.append(
                f"- Commander: {persona.label}{desc} (issues instructions via the command console — not an org node)"
            )
        if children:
            child_lines = []
            for c in children:
                goal_hint = f" — {c.role_goal}" if c.role_goal else ""
                child_lines.append(f"  - **{c.role_title}** (id: `{c.id}`){goal_hint}")
            rel_parts.append("- Direct subordinates:\n" + "\n".join(child_lines))
            rel_parts.append(
                "\n**Important: you are a manager. When you receive a complex task, first break it down and delegate to the right subordinate using org_delegate_task — do not execute it yourself. Only handle simple coordination tasks directly.**"
            )
        else:
            if is_root:
                rel_parts.append(
                    "\nYou are a solo executor (no superior node, no subordinates). When you receive a task, **complete it yourself**. "
                    "Summarize the result directly in your reply — it will be returned automatically to the commander. "
                    "When you need a colleague's help, communicate with them via org_send_message."
                )
            else:
                rel_parts.append(
                    "\nYou are an executor (no subordinates). When you receive a task, **complete it yourself**. "
                    "Submit your deliverable using org_submit_deliverable when done. "
                    "When you need a colleague's help, communicate via org_send_message "
                    "(do not use org_delegate_task — that is for managers with subordinates)."
                )
        if connected_peers:
            rel_parts.append(f"- Collaborators: {', '.join(connected_peers)}")
        if rel_parts:
            parts.append("## Your direct relationships\n" + "\n".join(rel_parts))

        perm_parts = [
            f"- Delegate tasks: {'allowed' if node.can_delegate else 'not allowed'}",
            f"- Escalate issues: {'allowed' if node.can_escalate else 'not allowed'}",
            f"- Request scaling: {'allowed' if node.can_request_scaling else 'not allowed'}",
            f"- Broadcast messages: {'allowed (whole org)' if node.level == 0 else 'allowed (dept only)'}",
        ]
        parts.append("## Your permissions\n" + "\n".join(perm_parts))

        parts.append(
            "## Policy and process\n"
            "The organization has a full policy system. When you are unsure how to execute a process:\n"
            "1. Search for relevant policies with org_search_policy\n"
            "2. Read the policy content with org_read_policy\n"
            "3. Follow the policy\n"
            "Do not guess — look it up. Check relevant policies before any important decision."
        )
        if policy_index:
            parts.append(f"Policy index:\n{policy_index}")

        if is_root:
            delivery_flow = (
                "Task completion flow:\n"
                "1. Start working after receiving the commander's instruction (you may delegate to subordinates or execute yourself)\n"
                "2. When done, summarize the result directly in your reply — it will be returned automatically to the commander\n"
                "3. Write important results to org_write_blackboard for the team to reference\n"
                "4. **Do not** use org_submit_deliverable — you have no superior node to submit to\n\n"
                "When reviewing subordinate deliverables, use org_accept_deliverable (approve) or org_reject_deliverable (reject).\n\n"
                "⚠️ When to report after delegating (very important):\n"
                "- After using org_delegate_task to assign work to a subordinate, **do not** immediately send the commander an interim reply like \"delegated\" or \"in progress\", and do not end the conversation immediately\n"
                "- You must wait for all relevant subordinates to submit via org_submit_deliverable and for you to accept them with org_accept_deliverable before sending **one** consolidated reply to the commander with the final conclusion\n"
                "- If you need to check progress during review, use org_list_delegated_tasks / org_get_task_progress — do not send interim updates to the commander\n"
                "- The \"completed\" message the commander sees should contain the full conclusion, not a process update like \"task assigned to XXX, waiting\"\n\n"
                "⚠️ Strict constraints:\n"
                "- Only execute instructions explicitly issued by the commander — do not extend scope on your own\n"
                "- Stop after completing the instruction — do not proactively start new projects or tasks\n"
                "- If you believe follow-up work is needed, suggest it in your reply and wait for the commander's confirmation before acting"
            )
        else:
            delivery_flow = (
                "Task delivery flow:\n"
                "1. Start working after receiving the task\n"
                "2. When done, submit your deliverable with **org_submit_deliverable** (to_node may be omitted — system auto-submits to your direct superior)\n"
                "3. The delegator reviews with org_accept_deliverable (approve) or org_reject_deliverable (reject)\n"
                "4. If rejected, revise based on feedback and resubmit\n"
                "5. Task is complete once accepted\n\n"
                "If you lack the tools you need, use org_request_tools to request them from your superior.\n\n"
                "⚠️ **Scope hard constraints (higher priority than efficiency mindset)**:\n"
                "- **Strictly align with the user's original instruction**: if a \"Current user instruction\" section appears at the top, your output must stay strictly within its scope, word count, and format; when your superior's paraphrase conflicts with the original, **the user's original wording takes precedence**\n"
                "- **Do less rather than exceed**: if the user asked for a 50-word outline, write only 50 words — do not fill in code, expand unrequested details, or append extra deliverables\n"
                "- Complete only the tasks your superior has explicitly assigned — do not start new projects or expand scope on your own\n"
                "- Stop after the task is complete and accepted; wait for your superior's next instruction\n"
                "- If you believe follow-up work is needed, **suggest** it in the deliverable — let the superior decide whether to act\n"
                "- The \"AI efficiency mindset\" above encourages fast action, but does not mean going beyond the user's boundaries to do extra work"
            )

        has_external = bool(node.external_tools)
        # E0-4: 节点级"基础文件工具"开关。即便没有勾选 external_tools，只要
        # enable_file_tools=True（默认），节点也会被注入安全的 write_file /
        # read_file / edit_file / list_directory；此时 prompt 必须告诉 LLM 这些
        # 工具是可用的，并指导它在交付物是文档/代码时主动落盘 + 走
        # org_submit_deliverable(file_attachments=[...])，否则会出现"工具明明
        # 在但提示词说不可用"的自相矛盾。
        has_basic_file_tools = getattr(node, "enable_file_tools", True)
        if has_external:
            from .tool_categories import TOOL_CATEGORIES, expand_tool_categories
            ext_names = expand_tool_categories(node.external_tools)
            cat_labels = [c for c in node.external_tools if c in TOOL_CATEGORIES]
            ext_desc = ", ".join(cat_labels) if cat_labels else ", ".join(sorted(ext_names)[:5])
            parts.append(
                "## Organization tools and behavior constraints\n"
                f"You have access to org_* collaboration tools and external execution tools ({ext_desc}).\n"
                "Collaboration rules:\n"
                "- Use org_* tools for communicating with colleagues, delegating, and reporting; use external tools for actual execution such as searching, writing files, and planning\n"
                "- Write important results from external tools to org_write_blackboard to share with colleagues\n"
                "- Prefer direct-link relationships for communication (superiors, subordinates, collaborators)\n"
                "- Avoid skipping levels unless necessary\n"
                "- Keep replies concise — 1–3 sentences summarizing your action and result\n\n"
                + delivery_flow
            )
        elif has_basic_file_tools:
            parts.append(
                "## Organization tools and behavior constraints\n"
                "You have access to org_* collaboration tools and a set of basic file tools (write_file / "
                "read_file / edit_file / list_directory) for saving structured deliverables such as documents, "
                "code, and proposals to the organization workspace. Note: advanced tools such as run_shell, "
                "web scraping, and MCP are not authorized — request them via org_request_tools if needed.\n"
                "Collaboration rules:\n"
                "- Use org_* tools for communicating with colleagues, delegating, and reporting\n"
                "- When your deliverable is structured content (document, code, HTML, etc.), **use write_file "
                "to save the file first**, then pass it to the delegator with org_submit_deliverable(file_attachments=[…]) — "
                "do not stuff the entire content into the deliverable field\n"
                "- Write important decisions and proposals to org_write_blackboard; call org_read_blackboard first to avoid duplicates\n"
                "- Keep replies concise — 1–3 sentences summarizing your action and result\n\n"
                + delivery_flow
            )
        else:
            parts.append(
                "## Organization tools and behavior constraints\n"
                "You may **only** use org_* tools. Do not call write_file, read_file, "
                "run_shell, call_mcp_tool, or other non-org tools — they are not available.\n"
                "Collaboration rules:\n"
                "- Prefer direct-link relationships for communication (superiors, subordinates, collaborators)\n"
                "- Avoid skipping levels unless necessary\n"
                "- Write important decisions and proposals to org_write_blackboard; call org_read_blackboard first to avoid duplicates\n"
                "- Keep replies concise — 1–3 sentences summarizing your action and result\n\n"
                + delivery_flow
            )

        if getattr(org, "operation_mode", "") == "command" and not project_tasks_summary:
            project_tasks_summary = self._get_project_tasks_summary(org, node)

        if project_tasks_summary:
            parts.append(f"## Project tasks currently assigned to you\n{project_tasks_summary}")

        if blackboard_summary:
            parts.append(f"## Current organization briefing\n{blackboard_summary}")
        if dept_summary:
            parts.append(f"## Department updates\n{dept_summary}")
        if node_summary:
            parts.append(f"## Your work notes\n{node_summary}")
        if pending_messages:
            parts.append(f"## Pending messages\n{pending_messages}")

        return "\n\n".join(parts)

    def resolve_mcp_config(self, node: OrgNode) -> dict:
        """Resolve MCP configuration with overlay inheritance."""
        mcp_path = self._nodes_dir / node.id / "mcp_config.json"
        if not mcp_path.is_file():
            return {"mode": "inherit"}
        try:
            return json.loads(mcp_path.read_text(encoding="utf-8"))
        except Exception:
            return {"mode": "inherit"}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_brief_org_chart(self, org: Organization) -> str:
        """Build a compact org chart for prompt injection (~200-500 tokens).

        Format includes node IDs so agents can reference colleagues directly.
        """
        departments: dict[str, list[OrgNode]] = {}
        roots: list[OrgNode] = []
        root_ids: set[str] = set()
        for n in org.nodes:
            if n.level == 0:
                roots.append(n)
                root_ids.add(n.id)
            dept = n.department or "Unassigned"
            departments.setdefault(dept, []).append(n)

        lines: list[str] = []
        for root in roots:
            goal = f" -- {root.role_goal[:30]}" if root.role_goal else ""
            lines.append(f"- {root.role_title}(`{root.id}`){goal}")

        for dept_name, members in sorted(departments.items()):
            dept_members = [m for m in members if m.id not in root_ids]
            if not dept_members:
                continue
            member_str = ", ".join(
                f"{m.role_title}(`{m.id}`)" for m in dept_members[:6]
            )
            if len(dept_members) > 6:
                member_str += f" and {len(dept_members)} others"
            lines.append(f"  - {dept_name}: {member_str}")

        return "\n".join(lines) if lines else "(org chart is empty)"

    def _global_soul(self) -> str:
        if self._global_identity_dir:
            return self._read_file(self._global_identity_dir / "SOUL.md") or ""
        return ""

    def _global_agent(self) -> str:
        if self._global_identity_dir:
            core = self._read_file(self._global_identity_dir / "agent.core.md")
            if core:
                return core
            return self._read_file(self._global_identity_dir / "AGENT.md") or ""
        return ""

    def _get_profile_prompt(self, profile_id: str) -> str | None:
        try:
            from openakita.main import _orchestrator
            if _orchestrator and hasattr(_orchestrator, "_profile_store"):
                profile = _orchestrator._profile_store.get(profile_id)
                return profile.custom_prompt if profile else None
        except (ImportError, AttributeError):
            pass
        try:
            from openakita.agents.profile import get_profile_store
            store = get_profile_store()
            profile = store.get(profile_id)
            return profile.custom_prompt if profile else None
        except Exception:
            return None

    def _auto_generate_role(self, node: OrgNode) -> str:
        parts = [f"You are {node.role_title}."]
        if node.role_goal:
            parts.append(f"Goal: {node.role_goal}.")
        if node.role_backstory:
            parts.append(f"Background: {node.role_backstory}.")
        return "".join(parts)

    def _get_project_tasks_summary(self, org: Organization, node: OrgNode) -> str:
        """Get summary of project tasks assigned to this node (for command mode)."""
        if getattr(org, "operation_mode", "") != "command":
            return ""
        try:
            from openakita.orgs.project_store import ProjectStore

            store = ProjectStore(self._org_dir)
            tasks = store.all_tasks(
                assignee=node.id,
                status=None,
            )
            in_progress = [t for t in tasks if t.get("status") == "in_progress"]
            todo = [t for t in tasks if t.get("status") == "todo"]
            if not in_progress and not todo:
                return "(no project tasks currently assigned to you)"
            lines: list[str] = []
            for t in (in_progress + todo)[:5]:
                title = t.get("title", "")[:60]
                status = t.get("status", "")
                pct = t.get("progress_pct", 0)
                proj = t.get("project_name", "")
                lines.append(f"- [{status}] {title} ({proj}) {pct}%")
            return "\n".join(lines) if lines else "(none)"
        except Exception:
            return ""

    @staticmethod
    def _read_file(path: Path) -> str | None:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8").strip()
                return content if content else None
            except Exception:
                return None
        return None
