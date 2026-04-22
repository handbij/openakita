"""
User Profile 工具定义

包含用户档案管理相关的工具：
- update_user_profile: 更新用户档案
- skip_profile_question: 跳过档案问题
- get_user_profile: 获取用户档案
"""

PROFILE_TOOLS = [
    {
        "name": "update_user_profile",
        "category": "Profile",
        "description": "Update structured user profile fields (name, work_field, os, ide, timezone, etc.) when user shares personal info. When you need to: (1) Save user preferences to a structured field, (2) Remember user's work domain, (3) Provide personalized service. NOTE: For persona/communication-style preferences (sticker_preference, emoji_usage, humor, formality, etc.), use update_persona_trait instead. For free-form observations, lessons, or patterns that don't map to a profile field, use add_memory instead.",
        "detail": """Update user profile information.

**When to use**:
When the user tells you about their preferences, habits, or work domain, use this tool to save it. This helps you better understand the user and provide personalized service.

**Supported profile fields**:
- name: how to address the user
- agent_role: **the role the Agent plays** (e.g. "work assistant", "technical advisor") — **not the user's profession**. If the user says "I'm a backend engineer / product manager / teacher", use `key="profession"` instead; the handler will automatically save it to long-term memory — **do not** put it in agent_role
- work_field: **work domain / industry** (e.g. internet / finance / education) — **not a geographic location**. If the user says "I live in Shanghai / Guangzhou", use `key="city"` or `key="location"` instead — **do not** put it in work_field
- preferred_language: programming language preference
- os: operating system
- ide: development tool
- detail_level: preferred level of detail
- code_comment_lang: code comment language
- indent_style: indentation style (2 spaces / 4 spaces / tab)
- code_style: code style standard (PEP8 / Google Style / Prettier, etc.)
- work_hours: working hours
- timezone: time zone
- confirm_preference: confirmation preference
- hobbies: hobbies and interests
- health_habits: health habits
- communication_style: communication style preference
- humor_preference: humor preference
- proactive_preference: proactive messaging preference
- emoji_preference: emoji preference
- care_topics: topics the user cares about

**Note**: communication style preferences such as sticker_preference, emoji_usage, humor, and formality belong to the persona system — use `update_persona_trait` instead of this tool.

**Important: avoid field mismatches**:
- User's "profession / job / occupation" (backend engineer, product manager, designer, teacher, etc.) → use `key="profession"` — **do not** put it in agent_role
- User's "geographic location / place of residence" (Shanghai, Beijing, Guangzhou, Hong Kong, etc.) → use `key="city"` or `key="location"` — **do not** put it in work_field
- Keys not on the whitelist are not lost: the handler has a fallback that automatically saves them to long-term memory. Choose the semantically closest field name (even if not on the whitelist) and let the handler decide where it lands.""",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Profile field key name"},
                "value": {"type": "string", "description": "Value provided by the user"},
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "skip_profile_question",
        "category": "Profile",
        "description": "Skip profile question when user explicitly refuses to answer. When user says 'I don't want to answer' or 'skip this question', use this tool to stop asking about that item.",
        "detail": """Skip a profile question when the user explicitly indicates they do not want to answer it (and stop asking about it in the future).

**When to use**:
- The user says "I don't want to answer"
- The user says "skip this question"
- The user indicates they are unwilling to share certain information""",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Profile field key to skip"}},
            "required": ["key"],
        },
    },
    {
        "name": "get_user_profile",
        "category": "Profile",
        "description": "Get current user profile summary to understand user's preferences and context. When you need to: (1) Check known user info, (2) Personalize responses.",
        "detail": """Get the current user profile information summary.

**Returned information**:
- Filled-in profile fields
- User preference settings
- Work-related information

**When to use**:
- Check known user information
- Personalize responses""",
        "input_schema": {"type": "object", "properties": {}},
    },
]
