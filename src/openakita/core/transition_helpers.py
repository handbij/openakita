"""Shared prompt builders and response classifiers for ReAct transitions.

Centralised here so both ``reasoning_engine.run()`` and
``reasoning_engine.reason_stream()`` (plus any future variant) compose the
same strings and apply the same heuristics, keeping transition behaviour
symmetric between streaming and non-streaming code paths.
"""

from __future__ import annotations

import re

# Regex patterns that signal "I am doing X now" without actually invoking any
# tool. These are deliberately scoped to the Chinese promise idioms the model
# tends to emit when it hallucinates execution.
_PROMISE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"正在.*(?:生成|创建|制作|处理|执行|准备)"),
    re.compile(r"(?:生成|创建|制作|处理).*中"),
    re.compile(r"稍等"),
    re.compile(r"马上.*(?:生成|创建|完成)"),
    re.compile(r"请.*(?:稍候|等待|等一下)"),
    re.compile(r"立即.*(?:开始|为你|帮你)"),
    re.compile(r"文[件档].*(?:生成|创建)中"),
    re.compile(r"let me .*(?:do|execute|run|generate|create)", re.IGNORECASE),
    re.compile(r"i['']ll .*(?:do|execute|run|generate|create) .* now", re.IGNORECASE),
    re.compile(r"i am .*(?:doing|executing|running|generating|creating)", re.IGNORECASE),
)

_PROMISE_MAX_LEN = 500


def is_in_progress_promise(assistant_response: str) -> bool:
    """Detect "I am doing X now" replies with no actual tool_call.

    The caller is still responsible for checking that no tool calls were
    emitted on the same turn — this function only classifies the text.
    """
    text = (assistant_response or "").strip()
    if not text or len(text) > _PROMISE_MAX_LEN:
        return False
    return any(p.search(text) for p in _PROMISE_PATTERNS)


def build_force_tool_call_prompt(
    pending_tool_name: str | None = None,
    context: str | None = None,
) -> str:
    """Prompt pushing the model to actually execute a tool call.

    Used when the model declared an ``[ACTION]`` intent but emitted no tool
    call on the turn, or when a prior turn promised execution but didn't
    deliver.
    """
    hint_tool = (
        f"（建议优先使用工具：{pending_tool_name}）"
        if pending_tool_name
        else ""
    )
    hint_context = f"\n\n上下文：\n{context.strip()}" if context else ""
    return (
        "[系统] ⚠️ 你的上一条回复没有调用任何工具（系统日志确认 tool_calls=0）。"
        "文字描述不等于实际执行。请立即调用工具完成用户的请求"
        f"{hint_tool}。"
        f"{hint_context}"
    )


def build_pending_todo_prompt(todo_context: str | None = None) -> str:
    """Prompt nudging the model to resume pending TODO steps.

    Emitted when the model produced a final answer while the active plan
    still has ``pending``/``in_progress`` steps.
    """
    if todo_context and todo_context.strip():
        return (
            "[系统提示] 当前 Plan 仍有未完成的步骤：\n"
            f"{todo_context.strip()}\n"
            "请立即继续执行下一个 pending 步骤。"
        )
    return (
        "[系统提示] 当前 Plan 仍有未完成的步骤。"
        "请立即继续执行下一个 pending 步骤。"
    )


def build_max_tokens_continuation_prompt(
    attempt: int,
    limit: int,
    cutoff_hint: str | None = None,
) -> str:
    """Prompt asking the model to resume a max_tokens-truncated response.

    ``attempt`` / ``limit`` are included in the log context on the caller
    side; the user-visible prompt is kept short to avoid further bloat.
    """
    base = (
        "你的回答被截断了。请直接从断点处继续输出，"
        "不要重复已说过的内容，不要道歉。"
    )
    if cutoff_hint:
        snippet = cutoff_hint.strip().rstrip("\n")
        if len(snippet) > 200:
            snippet = snippet[-200:]
        base += f"\n\n上一次的结尾是：“{snippet}”。"
    return base
