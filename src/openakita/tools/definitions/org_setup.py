"""
Organization setup tool — create organizations through natural language.

Only injected when settings.multi_agent_enabled is True, alongside AGENT_TOOLS.
"""

ORG_SETUP_TOOLS = [
    {
        "name": "setup_organization",
        "category": "Organization",
        "description": (
            "Create and manage organizational structures for multi-agent collaboration. "
            "Supports: listing available agents/templates (get_resources), "
            "previewing an org before creation (preview), "
            "creating from scratch (create), or from a template (create_from_template). "
            "ALWAYS call get_resources first, then ask the user clarifying questions "
            "before creating."
        ),
        "detail": (
            "通过自然语言创建组织编排架构。\n\n"
            "## 使用流程（必须遵循）\n\n"
            "1. **首先调用 get_resources** — 获取可用的系统 Agent 列表、组织模板、工具类目\n"
            "2. **向用户了解需求** — 在信息不足时主动询问，至少确认：\n"
            "   - 组织的目标和业务场景\n"
            "   - 大致的团队规模和部门划分\n"
            "   - 核心岗位及其职责\n"
            "3. **为每个节点匹配合适的系统 Agent**（agent_profile_id）\n"
            "   - 这是**最重要**的配置，决定节点的专业能力\n"
            "   - 优先选择专业对口的 Agent，避免全部使用 default\n"
            "   - 参考 get_resources 返回的 Agent 列表中的 description 和 category\n"
            "4. **用 preview 生成草案** — 展示给用户确认架构和 Agent 匹配\n"
            "5. **用户确认后再 create** — 正式创建组织\n\n"
            "## 注意事项\n"
            "- 信息不足时**主动询问**，不要猜测用户意图\n"
            "- 每个节点建议配置 external_tools（工具类目），否则节点只有 org_* 工具\n"
            "- parent_role_title 用于自动创建层级关系（hierarchy edges）\n"
            "- 创建成功后用户可在前端组织编排页面查看和微调"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["get_resources", "preview", "create", "create_from_template"],
                    "description": (
                        "操作类型：get_resources=获取可用资源清单；"
                        "preview=预览组织架构（不创建）；"
                        "create=创建组织；"
                        "create_from_template=从模板创建"
                    ),
                },
                "name": {
                    "type": "string",
                    "description": "组织名称（create/preview 时必填）",
                },
                "description": {
                    "type": "string",
                    "description": "组织描述",
                },
                "core_business": {
                    "type": "string",
                    "description": "核心业务描述（如：跨境电商运营、SaaS 产品研发）",
                },
                "nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role_title": {
                                "type": "string",
                                "description": "岗位名称（必填，如 CEO、CTO、前端开发）",
                            },
                            "role_goal": {
                                "type": "string",
                                "description": "岗位目标（如：制定技术路线，保障系统稳定）",
                            },
                            "department": {
                                "type": "string",
                                "description": "所属部门（如：技术部、产品部）",
                            },
                            "level": {
                                "type": "integer",
                                "description": "层级（0=最高层/根，1=中层，2=基层）",
                            },
                            "agent_profile_id": {
                                "type": "string",
                                "description": (
                                    "关联的系统 Agent ID（非常重要！决定节点的专业能力。"
                                    "从 get_resources 返回的 agents 列表中选择最合适的）"
                                ),
                            },
                            "parent_role_title": {
                                "type": "string",
                                "description": (
                                    "上级岗位名称（用于自动创建层级关系。"
                                    "根节点不需要填写）"
                                ),
                            },
                            "external_tools": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "外部工具（类目名或工具名，如 "
                                    "'research'、'filesystem'、'planning'、'browser'）"
                                ),
                            },
                            "custom_prompt": {
                                "type": "string",
                                "description": "自定义提示词（可选，用于精细控制节点行为）",
                            },
                        },
                        "required": ["role_title"],
                    },
                    "description": "节点列表（create/preview 时必填）",
                },
                "template_id": {
                    "type": "string",
                    "description": "模板 ID（create_from_template 时必填）",
                },
                "overrides": {
                    "type": "object",
                    "description": "模板覆盖字段（create_from_template 时可选，如 name、description）",
                },
            },
            "required": ["action"],
        },
        "examples": [
            {
                "scenario": "第一步：获取可用资源",
                "params": {"action": "get_resources"},
                "expected": "返回 Agent 列表、模板列表、工具类目",
            },
            {
                "scenario": "预览电商运营团队架构",
                "params": {
                    "action": "preview",
                    "name": "电商运营团队",
                    "core_business": "自营电商运营",
                    "nodes": [
                        {
                            "role_title": "运营总监",
                            "role_goal": "统筹运营策略，达成销售目标",
                            "department": "运营部",
                            "level": 0,
                            "agent_profile_id": "project-manager",
                            "external_tools": ["research", "planning", "memory"],
                        },
                        {
                            "role_title": "内容运营",
                            "role_goal": "负责商品描述和社媒内容",
                            "department": "运营部",
                            "level": 1,
                            "agent_profile_id": "content-creator",
                            "parent_role_title": "运营总监",
                            "external_tools": ["research", "filesystem"],
                        },
                    ],
                },
                "expected": "返回组织架构预览，包含节点树和 Agent 匹配摘要",
            },
            {
                "scenario": "从模板创建",
                "params": {
                    "action": "create_from_template",
                    "template_id": "startup-company",
                    "overrides": {"name": "我的创业公司"},
                },
                "expected": "从模板创建组织，返回 org_id",
            },
        ],
    },
]
