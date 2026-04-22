"""
文件系统处理器

处理文件系统相关的系统技能：
- run_shell: 执行 Shell 命令（持久会话 + 后台进程支持）
- write_file: 写入文件
- read_file: 读取文件
- edit_file: 精确字符串替换编辑
- list_directory: 列出目录
- grep: 内容搜索
- glob: 文件名模式搜索
- delete_file: 删除文件
"""

import logging
import re
import weakref
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...core.agent import Agent

logger = logging.getLogger(__name__)

_terminal_managers: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
_terminal_mgr_strong_refs: dict[int, Any] = {}


def _get_terminal_manager(agent: "Agent") -> Any:
    """Get or create a TerminalSessionManager for this agent instance.

    Uses agent object id as key. A strong reference is stored alongside the agent
    so the manager lives as long as the agent does. When the agent is GC'd,
    clean up on next access.
    """
    from ..terminal import TerminalSessionManager

    agent_id = id(agent)
    mgr = _terminal_mgr_strong_refs.get(agent_id)
    if mgr is not None:
        return mgr
    cwd = getattr(agent, "default_cwd", None) or str(Path.cwd())
    mgr = TerminalSessionManager(default_cwd=cwd)
    _terminal_mgr_strong_refs[agent_id] = mgr
    try:
        weakref.finalize(agent, _terminal_mgr_strong_refs.pop, agent_id, None)
    except TypeError:
        pass
    return mgr


class FilesystemHandler:
    """
    文件系统处理器

    处理所有文件系统相关的工具调用
    """

    # 该处理器处理的工具
    TOOLS = [
        "run_shell",
        "write_file",
        "read_file",
        "edit_file",
        "list_directory",
        "grep",
        "glob",
        "delete_file",
    ]

    def __init__(self, agent: "Agent"):
        """
        初始化处理器

        Args:
            agent: Agent 实例，用于访问 shell_tool 和 file_tool
        """
        self.agent = agent

    def _get_fix_policy(self) -> dict | None:
        """
        获取自检自动修复策略（可选）

        当 SelfChecker 创建的修复 Agent 注入 _selfcheck_fix_policy 时启用。
        """
        policy = getattr(self.agent, "_selfcheck_fix_policy", None)
        if isinstance(policy, dict) and policy.get("enabled"):
            return policy
        return None

    def _resolve_to_abs(self, raw: str) -> Path:
        p = Path(raw)
        if p.is_absolute():
            return p.resolve()
        # FileTool 以 cwd 为 base_path；这里保持一致
        return (Path.cwd() / p).resolve()

    def _is_under_any_root(self, target: Path, roots: list[str]) -> bool:
        for r in roots or []:
            try:
                root = Path(r).resolve()
                if target == root or target.is_relative_to(root):
                    return True
            except Exception:
                continue
        return False

    async def handle(self, tool_name: str, params: dict[str, Any]) -> str:
        """
        处理工具调用

        Args:
            tool_name: 工具名称
            params: 参数字典

        Returns:
            执行结果字符串
        """
        if tool_name == "run_shell":
            return await self._run_shell(params)
        elif tool_name == "write_file":
            return await self._write_file(params)
        elif tool_name == "read_file":
            return await self._read_file(params)
        elif tool_name == "edit_file":
            return await self._edit_file(params)
        elif tool_name == "list_directory":
            return await self._list_directory(params)
        elif tool_name == "grep":
            return await self._grep(params)
        elif tool_name == "glob":
            return await self._glob(params)
        elif tool_name == "delete_file":
            return await self._delete_file(params)
        else:
            return f"❌ Unknown filesystem tool: {tool_name}"

    @staticmethod
    def _fix_windows_python_c(command: str) -> str:
        """Windows 多行 python -c 修复。

        Windows cmd.exe 无法正确处理 python -c "..." 中的换行符，
        会导致 Python 只执行第一行（通常是 import），stdout 为空。
        检测到多行 python -c 时，自动写入临时 .py 文件后执行。
        """
        import tempfile

        stripped = command.strip()

        # 匹配 python -c "..." 或 python -c '...' 或 python - <<'EOF'
        # 只处理包含换行的情况
        m = re.match(
            r'^python(?:3)?(?:\.exe)?\s+-c\s+["\'](.+)["\']$',
            stripped,
            re.DOTALL,
        )
        if not m:
            # 也匹配 heredoc 形式：python - <<'PY' ... PY
            m2 = re.match(
                r"^python(?:3)?(?:\.exe)?\s+-\s*<<\s*['\"]?(\w+)['\"]?\s*\n(.*?)\n\1$",
                stripped,
                re.DOTALL,
            )
            if m2:
                code = m2.group(2)
            else:
                return command
        else:
            code = m.group(1)

        # 只有多行才需要修复
        if "\n" not in code:
            return command

        # 写入临时文件 (delete=False requires manual cleanup, not context manager)
        tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode="w",
            suffix=".py",
            prefix="oa_shell_",
            dir=tempfile.gettempdir(),
            delete=False,
            encoding="utf-8",
        )
        tmp.write(code)
        tmp.close()

        logger.info("[Windows fix] Multiline python -c → temp file: %s", tmp.name)
        return f'python "{tmp.name}"'

    # run_shell 成功输出最大行数
    SHELL_MAX_LINES = 200

    _EXIT_CODE_SEMANTICS: dict[str, dict[int, str]] = {
        "grep": {1: "no matches (non-error)"},
        "egrep": {1: "no matches (non-error)"},
        "fgrep": {1: "no matches (non-error)"},
        "rg": {1: "no matches (non-error)"},
        "diff": {1: "files differ (non-error)"},
        "test": {1: "condition false (non-error)"},
        "find": {1: "partial paths inaccessible (non-error)"},
        "cmp": {1: "files differ (non-error)"},
        "where": {1: "command not found (non-error)"},
    }

    @classmethod
    def _format_run_shell_missing_command(cls, params: dict) -> str:
        """缺 'command' 参数时返回引导式错误，识别常见误传字段。

        - 列出实际收到的键，方便 LLM 发现自己传错；
        - 若误传 script/cmd/shell/bash/code，特别提示重命名为 'command'。
        """
        try:
            keys = list(params.keys()) if isinstance(params, dict) else []
        except Exception:
            keys = []

        wrong_alias = None
        if isinstance(params, dict):
            for alias in cls._RUN_SHELL_ALIAS_KEYS:
                if alias in params and params.get(alias):
                    wrong_alias = alias
                    break

        lines = [
            "❌ run_shell missing required parameter 'command'.",
            'Usage: run_shell(command="ls -la", working_directory=None, timeout=60)',
            f"You passed keys: {keys}",
        ]
        if wrong_alias is not None:
            lines.append(
                f"Detected '{wrong_alias}' — rename it to 'command' and retry; keep the value as-is."
            )
        else:
            lines.append(
                "Common misnamed fields: script / cmd / shell / bash / code → all should use 'command'."
            )
        return "\n".join(lines)

    @classmethod
    def _interpret_exit_code(cls, command: str, exit_code: int) -> str | None:
        """Return a human-readable meaning if the exit code is a known
        non-error for the given command, or ``None`` otherwise."""
        stripped = command.strip()
        if not stripped:
            return None
        # Extract the first command segment, handling pipes / && / ;
        first_segment = (
            stripped.split("|")[0].strip().split("&&")[0].strip().split(";")[0].strip()
        )
        # Split into tokens; skip leading env-var assignments (VAR=val)
        tokens = first_segment.split()
        while tokens and "=" in tokens[0]:
            tokens = tokens[1:]
        if not tokens:
            return None
        cmd_name = Path(tokens[0]).stem
        meanings = cls._EXIT_CODE_SEMANTICS.get(cmd_name, {})
        return meanings.get(exit_code)

    # 常见的 LLM 误传字段名 -> 都应改写为 'command'
    _RUN_SHELL_ALIAS_KEYS = ("script", "cmd", "shell", "bash", "code")

    async def _run_shell(self, params: dict) -> str:
        """Execute shell command with persistent session + background support."""
        command = params.get("command", "")
        if not command:
            return self._format_run_shell_missing_command(params)

        policy = self._get_fix_policy()
        if policy:
            deny_patterns = policy.get("deny_shell_patterns") or []
            for pat in deny_patterns:
                try:
                    if re.search(pat, command, flags=re.IGNORECASE):
                        msg = (
                            "❌ Self-check auto-fix guardrail: execution of commands that may affect the system/Windows layer is blocked."
                            f"\nCommand: {command}"
                        )
                        logger.warning(msg)
                        return msg
                except re.error:
                    continue

        import platform

        if platform.system() == "Windows":
            command = self._fix_windows_python_c(command)

        working_directory = params.get("working_directory") or params.get("cwd")

        block_timeout_ms = params.get("block_timeout_ms")
        if block_timeout_ms is None:
            timeout_s = params.get("timeout", 60)
            # 确保 timeout_s 是整数类型（防止外部传入字符串导致 TypeError）
            try:
                timeout_s = int(timeout_s)
            except (ValueError, TypeError):
                timeout_s = 60
            timeout_s = max(10, min(timeout_s, 600))
            block_timeout_ms = timeout_s * 1000

        session_id = params.get("session_id", 1)

        terminal_mgr = _get_terminal_manager(self.agent)
        result = await terminal_mgr.execute(
            command,
            session_id=session_id,
            block_timeout_ms=block_timeout_ms,
            working_directory=working_directory,
        )

        from ...logging import get_session_log_buffer

        log_buffer = get_session_log_buffer()

        if result.backgrounded:
            log_buffer.add_log(
                level="INFO",
                module="shell",
                message=f"$ {command}\n[backgrounded, pid: {result.pid}]",
            )
            return result.stdout

        if result.success:
            log_buffer.add_log(
                level="INFO",
                module="shell",
                message=f"$ {command}\n[exit: 0]\n{result.stdout}"
                + (f"\n[stderr]: {result.stderr}" if result.stderr else ""),
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[Warning]:\n{result.stderr}"

            full_text = f"Command executed successfully (exit code: 0):\n{output}"
            return self._truncate_shell_output(full_text)
        else:
            # Check for known non-error exit codes before treating as failure
            exit_meaning = self._interpret_exit_code(command, result.returncode)
            if exit_meaning:
                log_buffer.add_log(
                    level="INFO",
                    module="shell",
                    message=f"$ {command}\n[exit: {result.returncode}, {exit_meaning}]\n{result.stdout}",
                )
                output = result.stdout or ""
                if result.stderr:
                    output += f"\n[Info]:\n{result.stderr}"
                full_text = (
                    f"Command completed (exit code: {result.returncode}, {exit_meaning}):\n{output}"
                )
                return self._truncate_shell_output(full_text)

            log_buffer.add_log(
                level="ERROR",
                module="shell",
                message=f"$ {command}\n[exit: {result.returncode}]\nstdout: {result.stdout}\nstderr: {result.stderr}",
            )

            def _tail(text: str, max_chars: int = 4000, max_lines: int = 120) -> str:
                if not text:
                    return ""
                lines = text.splitlines()
                if len(lines) > max_lines:
                    lines = lines[-max_lines:]
                    text = "\n".join(lines)
                    text = f"...(truncated, showing last {max_lines} lines)\n{text}"
                if len(text) > max_chars:
                    text = text[-max_chars:]
                    text = f"...(truncated, showing last {max_chars} chars)\n{text}"
                return text

            output_parts = [f"Command failed (exit code: {result.returncode})"]

            if result.returncode == 9009:
                cmd_lower = command.strip().lower()
                if cmd_lower.startswith(("python", "python3")):
                    output_parts.append(
                        "⚠️ Python is not on the system PATH (Windows 9009 = command not found).\n"
                        "Install Python first: run_shell with 'winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements'\n"
                        "The system will detect it automatically after installation — no restart needed. Do not retry python/python3 commands."
                    )
                else:
                    first_word = command.strip().split()[0] if command.strip() else command
                    output_parts.append(
                        f"⚠️ '{first_word}' is not on the system PATH (Windows 9009 = command not found).\n"
                        "Check whether the program is installed, or use its full path."
                    )

            if result.stdout:
                output_parts.append(f"[stdout-tail]:\n{_tail(result.stdout)}")
            if result.stderr:
                output_parts.append(f"[stderr-tail]:\n{_tail(result.stderr)}")
            if not result.stdout and not result.stderr and result.returncode != 9009:
                output_parts.append("(no output — command may not exist or has a syntax error)")

            full_error = "\n".join(output_parts)
            truncated_result = self._truncate_shell_output(full_error)
            truncated_result += (
                "\nHint: If the cause is unclear, call get_session_logs for detailed logs, or try a different command."
            )
            return truncated_result

    def _truncate_shell_output(self, text: str) -> str:
        """截断 shell 输出，大输出保存到溢出文件并附分页提示。"""
        lines = text.split("\n")
        if len(lines) <= self.SHELL_MAX_LINES:
            return text

        total_lines = len(lines)
        from ...core.tool_executor import save_overflow

        overflow_path = save_overflow("run_shell", text)
        truncated = "\n".join(lines[: self.SHELL_MAX_LINES])
        truncated += (
            f"\n\n[OUTPUT_TRUNCATED] Command output has {total_lines} lines total; "
            f"showing first {self.SHELL_MAX_LINES} lines.\n"
            f"Full output saved to: {overflow_path}\n"
            f'Use read_file(path="{overflow_path}", offset={self.SHELL_MAX_LINES + 1}) '
            f"to view the rest."
        )
        return truncated

    @staticmethod
    def _check_unc(path: str | None) -> str | None:
        """Block UNC paths to prevent NTLM credential leaks."""
        if path and path.startswith("\\\\"):
            return (
                f"Blocked: UNC path detected ({path}). "
                "UNC paths can trigger automatic NTLM authentication and leak "
                "credentials. Use a local path or mapped drive letter instead."
            )
        return None

    async def _write_file(self, params: dict) -> str:
        """写入文件"""
        # 规范 path 名是 "path"；但 LLM 经常写成 filename/filepath/file_path。
        # 这里做一次保守兜底——只当权威的 path 缺失时才回退到别名，
        # 并且和 runtime._record_file_output 使用同一组别名，确保写盘成功后
        # 附件登记链路也能识别到同一个文件。schema 仍只声明 "path" 为主键
        # （见 tools/definitions/filesystem.py），tool description 会明确要求。
        path = (
            params.get("path")
            or params.get("filepath")
            or params.get("file_path")
            or params.get("filename")
        )
        unc_err = self._check_unc(path)
        if unc_err:
            return f"❌ {unc_err}"
        content = params.get("content")
        if not path:
            content_len = len(str(content)) if content else 0
            if content_len > 5000:
                return (
                    f"❌ write_file missing required parameter 'path' (content length {content_len} chars; "
                    "likely the JSON parameters were truncated due to oversized content).\n"
                    "Shorten the content and retry:\n"
                    "1. Split large files into multiple writes (< 8000 chars each)\n"
                    "2. Or use run_shell to run a Python script that generates the large file"
                )
            return "❌ write_file missing required parameter 'path'. Provide a file path and content, then retry."
        if content is None:
            return "❌ write_file missing required parameter 'content'. Provide the file content and retry."
        policy = self._get_fix_policy()
        if policy:
            target = self._resolve_to_abs(path)
            write_roots = policy.get("write_roots") or []
            if not self._is_under_any_root(target, write_roots):
                msg = (
                    "❌ Self-check auto-fix guardrail: writing to this path is blocked (only tools/skills/mcps/channels directories are allowed)."
                    f"\nTarget: {target}"
                )
                logger.warning(msg)
                return msg
        await self.agent.file_tool.write(path, content)
        try:
            file_path = self.agent.file_tool._resolve_path(path)
            size = file_path.stat().st_size
            result = f"File written: {path} ({size} bytes)"
        except OSError:
            result = f"File written: {path}"

        from ...core.im_context import get_im_session

        if not get_im_session():
            result += (
                "\n\n💡 Currently in Desktop mode — users cannot access server files directly. "
                "Include the key file content in your reply, "
                "or call deliver_artifacts(artifacts=[{type: 'file', path: '"
                + str(path)
                + "'}]) to make the file downloadable in the frontend."
            )
        return result

    # read_file 默认最大行数（参考 Claude Code 的 2000 行，我们用 300 更保守）
    READ_FILE_DEFAULT_LIMIT = 300

    async def _read_file(self, params: dict) -> str:
        """读取文件（支持 offset/limit 分页）"""
        path = params.get("path", "")
        if not path:
            return "❌ read_file missing required parameter 'path'."
        unc_err = self._check_unc(path)
        if unc_err:
            return f"❌ {unc_err}"

        policy = self._get_fix_policy()
        if policy:
            target = self._resolve_to_abs(path)
            read_roots = policy.get("read_roots") or []
            if not self._is_under_any_root(target, read_roots):
                msg = f"❌ Self-check auto-fix guardrail: reading this path is blocked.\nTarget: {target}"
                logger.warning(msg)
                return msg

        content = await self.agent.file_tool.read(path)

        offset = params.get("offset", 1)  # 起始行号（1-based），默认第 1 行
        limit = params.get("limit", self.READ_FILE_DEFAULT_LIMIT)

        # 确保 offset/limit 合法
        try:
            offset = max(1, int(offset))
            limit = max(1, int(limit))
        except (TypeError, ValueError):
            offset, limit = 1, self.READ_FILE_DEFAULT_LIMIT

        lines = content.split("\n")
        total_lines = len(lines)

        # If file fits within limit and reading from the start, return everything
        if total_lines <= limit and offset <= 1:
            return f"File contents ({total_lines} lines):\n{content}"

        # Paginated slice
        start = offset - 1  # convert to 0-based
        end = min(start + limit, total_lines)

        if start >= total_lines:
            return (
                f"⚠️ offset={offset} exceeds file length (file has {total_lines} lines).\n"
                f'Use read_file(path="{path}", offset=1, limit={limit}) to read from the beginning.'
            )

        shown = "\n".join(lines[start:end])
        result = f"File contents (lines {start + 1}-{end} of {total_lines}):\n{shown}"

        # Append pagination hint if there is more content
        if end < total_lines:
            remaining = total_lines - end
            result += (
                f"\n\n[OUTPUT_TRUNCATED] File has {total_lines} lines total; "
                f"showing lines {start + 1}-{end}, {remaining} remaining.\n"
                f'Use read_file(path="{path}", offset={end + 1}, limit={limit}) '
                f"to view more."
            )

        return result

    # list_directory 默认最大条目数
    LIST_DIR_DEFAULT_MAX = 200

    async def _edit_file(self, params: dict) -> str:
        """精确字符串替换编辑"""
        path = params.get("path", "")
        old_string = params.get("old_string")
        new_string = params.get("new_string")

        if not path:
            return "❌ edit_file missing required parameter 'path'."
        if old_string is None:
            return "❌ edit_file missing required parameter 'old_string'."
        if new_string is None:
            return "❌ edit_file missing required parameter 'new_string'."
        if old_string == new_string:
            return "❌ old_string and new_string are identical — no replacement needed."

        policy = self._get_fix_policy()
        if policy:
            target = self._resolve_to_abs(path)
            write_roots = policy.get("write_roots") or []
            if not self._is_under_any_root(target, write_roots):
                msg = f"❌ Self-check auto-fix guardrail: editing this path is blocked.\nTarget: {target}"
                logger.warning(msg)
                return msg

        replace_all = params.get("replace_all", False)

        try:
            result = await self.agent.file_tool.edit(
                path,
                old_string,
                new_string,
                replace_all=replace_all,
            )
            replaced = result["replaced"]
            try:
                file_path = self.agent.file_tool._resolve_path(path)
                size = file_path.stat().st_size
                size_info = f" ({size} bytes)"
            except OSError:
                size_info = ""
            if replace_all and replaced > 1:
                return f"File edited: {path} ({replaced} matches replaced){size_info}"
            return f"File edited: {path}{size_info}"
        except FileNotFoundError:
            return f"❌ File not found: {path}"
        except ValueError as e:
            return f"❌ edit_file failed: {e}"

    async def _list_directory(self, params: dict) -> str:
        """列出目录（支持 pattern/recursive/max_items）"""
        path = params.get("path", "")
        if not path:
            return "❌ list_directory missing required parameter 'path'."

        policy = self._get_fix_policy()
        if policy:
            target = self._resolve_to_abs(path)
            read_roots = policy.get("read_roots") or []
            if not self._is_under_any_root(target, read_roots):
                msg = f"❌ Self-check auto-fix guardrail: listing this directory is blocked.\nTarget: {target}"
                logger.warning(msg)
                return msg

        pattern = params.get("pattern", "*")
        recursive = params.get("recursive", False)
        files = await self.agent.file_tool.list_dir(
            path,
            pattern=pattern,
            recursive=recursive,
        )

        max_items = params.get("max_items", self.LIST_DIR_DEFAULT_MAX)
        try:
            max_items = max(1, int(max_items))
        except (TypeError, ValueError):
            max_items = self.LIST_DIR_DEFAULT_MAX

        total = len(files)
        if total <= max_items:
            result = f"Directory contents ({total} items):\n" + "\n".join(files)
        else:
            shown = files[:max_items]
            result = f"Directory contents (showing {max_items} of {total}):\n" + "\n".join(shown)
            result += (
                f"\n\n[OUTPUT_TRUNCATED] Directory has {total} entries; showing first {max_items}.\n"
                f'Use list_directory(path="{path}", max_items={total}) '
                f"to see more, or narrow your query."
            )

        from ...utils.subdir_context import inject_subdir_context

        return inject_subdir_context(result, path)

    # grep 最大结果条目数
    GREP_MAX_RESULTS = 200

    async def _grep(self, params: dict) -> str:
        """内容搜索"""
        pattern = params.get("pattern", "")
        if not pattern:
            return "❌ grep missing required parameter 'pattern'."

        path = params.get("path", ".")
        include = params.get("include")
        context_lines = params.get("context_lines", 0)
        max_results = params.get("max_results", 50)
        case_insensitive = params.get("case_insensitive", False)

        try:
            context_lines = max(0, int(context_lines))
        except (TypeError, ValueError):
            context_lines = 0
        try:
            max_results = max(1, min(int(max_results), self.GREP_MAX_RESULTS))
        except (TypeError, ValueError):
            max_results = 50

        try:
            results = await self.agent.file_tool.grep(
                pattern,
                path,
                include=include,
                context_lines=context_lines,
                max_results=max_results,
                case_insensitive=case_insensitive,
            )
        except FileNotFoundError as e:
            return f"❌ {e}"
        except ValueError as e:
            return f"❌ Regex error: {e}"

        if not results:
            return f"No matches found for '{pattern}'."

        lines: list[str] = []
        for m in results:
            if context_lines > 0 and "context_before" in m:
                for ctx_line in m["context_before"]:
                    lines.append(f"{m['file']}-{ctx_line}")
            lines.append(f"{m['file']}:{m['line']}:{m['text']}")
            if context_lines > 0 and "context_after" in m:
                for ctx_line in m["context_after"]:
                    lines.append(f"{m['file']}-{ctx_line}")
                lines.append("")

        total = len(results)
        header = f"Found {total} matches"
        if total >= max_results:
            header += f" (limit {max_results} reached — there may be more)"
        header += ":\n"

        output = header + "\n".join(lines)

        if len(output.split("\n")) > self.SHELL_MAX_LINES:
            from ...core.tool_executor import save_overflow

            overflow_path = save_overflow("grep", output)
            truncated = "\n".join(output.split("\n")[: self.SHELL_MAX_LINES])
            truncated += (
                f"\n\n[OUTPUT_TRUNCATED] Full results saved to: {overflow_path}\n"
                f'Use read_file(path="{overflow_path}", offset={self.SHELL_MAX_LINES + 1}) '
                f"to view the rest."
            )
            return truncated

        return output

    async def _glob(self, params: dict) -> str:
        """文件名模式搜索"""
        pattern = params.get("pattern", "")
        if not pattern:
            return "❌ glob missing required parameter 'pattern'."

        path = params.get("path", ".")

        # 不以 **/ 开头的 pattern 自动加 **/ 前缀，使其递归搜索
        if not pattern.startswith("**/"):
            pattern = f"**/{pattern}"

        dir_path = self.agent.file_tool._resolve_path(path)
        if not dir_path.is_dir():
            return f"❌ Directory not found: {path}"

        from ..file import DEFAULT_IGNORE_DIRS

        results: list[tuple[str, float]] = []
        glob_pattern = pattern[3:] if pattern.startswith("**/") else pattern
        for p in dir_path.rglob(glob_pattern):
            if not p.is_file():
                continue
            parts = p.relative_to(dir_path).parts
            if any(part in DEFAULT_IGNORE_DIRS for part in parts):
                continue
            if any(
                part.startswith(".") and part not in (".github", ".vscode", ".cursor")
                for part in parts[:-1]
            ):
                continue
            try:
                mtime = p.stat().st_mtime
            except OSError:
                mtime = 0
            results.append((str(p.relative_to(dir_path)), mtime))

        # 按修改时间降序排序
        results.sort(key=lambda x: x[1], reverse=True)

        if not results:
            return f"No files found matching '{pattern}'."

        total = len(results)
        max_show = self.LIST_DIR_DEFAULT_MAX
        file_list = [r[0] for r in results[:max_show]]
        output = f"Found {total} files (sorted by modification time):\n" + "\n".join(file_list)

        if total > max_show:
            output += f"\n\n[OUTPUT_TRUNCATED] {total} files total; showing first {max_show}."

        return output

    async def _delete_file(self, params: dict) -> str:
        """删除文件或空目录"""
        path = params.get("path", "")
        if not path:
            return "❌ delete_file missing required parameter 'path'."

        policy = self._get_fix_policy()
        if policy:
            target = self._resolve_to_abs(path)
            write_roots = policy.get("write_roots") or []
            if not self._is_under_any_root(target, write_roots):
                msg = f"❌ Self-check auto-fix guardrail: deleting this path is blocked.\nTarget: {target}"
                logger.warning(msg)
                return msg

        file_path = self.agent.file_tool._resolve_path(path)

        if not file_path.exists():
            return f"❌ Path not found: {path}"

        if file_path.is_dir():
            try:
                children = list(file_path.iterdir())
            except PermissionError:
                return f"❌ Permission denied accessing directory: {path}"
            if children:
                return (
                    f"❌ Directory is not empty ({len(children)} items) — direct deletion is not allowed. "
                    f"Confirm that you really want to delete this directory and all its contents."
                )

        is_dir = file_path.is_dir()
        success = await self.agent.file_tool.delete(path)
        if success:
            if file_path.exists():
                return f"⚠️ Delete returned success but path still exists: {path}"
            kind = "Directory" if is_dir else "File"
            return f"{kind} deleted: {path}"
        return f"❌ Delete failed: {path}"


def create_handler(agent: "Agent"):
    """
    创建文件系统处理器

    Args:
        agent: Agent 实例

    Returns:
        处理器的 handle 方法
    """
    handler = FilesystemHandler(agent)
    return handler.handle
