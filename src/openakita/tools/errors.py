"""
Structured tool errors

Provides the ToolError exception class and ErrorType enum,
allowing the LLM to decide based on error type: retry / try another approach / report to user.

Usage:
    from openakita.tools.errors import ToolError, ErrorType

    try:
        result = await shell_tool.run(command)
    except TimeoutError:
        raise ToolError(
            error_type=ErrorType.TIMEOUT,
            tool_name="run_shell",
            message="Command execution timed out",
            retry_suggestion="Please increase the timeout parameter and retry",
        )
"""

import json
import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ErrorType(Enum):
    """Tool error types"""

    TRANSIENT = "transient"  # Transient error (network timeout, service unavailable, etc.), retryable
    PERMANENT = "permanent"  # Permanent error (logic error, unsupported operation), try another approach
    PERMISSION = "permission"  # Permission error, operation not allowed
    TIMEOUT = "timeout"  # Timeout, may retry with a longer timeout
    VALIDATION = "validation"  # Parameter validation failed, fix parameters
    RESOURCE_NOT_FOUND = "not_found"  # Resource not found (file, URL, etc.)
    RATE_LIMIT = "rate_limit"  # Rate limit exceeded, retry after waiting
    DEPENDENCY = "dependency"  # Dependency missing (missing command, library, etc.)
    # Added for external-CLI fallback routing (plan 06)
    AUTH = "auth"
    AUTH_PERMANENT = "auth_permanent"
    BILLING = "billing"
    OVERLOADED = "overloaded"
    MODEL_NOT_FOUND = "model_not_found"
    CONTEXT_OVERFLOW = "context_overflow"
    SERVER = "server"
    NETWORK = "network"
    CONTENT_FILTER = "content_filter"
    FORMAT = "format"


# LLM-friendly error type hints, injected into tool_result to help the LLM decide
_ERROR_TYPE_HINTS: dict[ErrorType, str] = {
    ErrorType.TRANSIENT: "Transient error, you can retry directly",
    ErrorType.PERMANENT: "Permanent error, please try a different method or tool",
    ErrorType.PERMISSION: "Insufficient permissions, unable to perform this operation",
    ErrorType.TIMEOUT: "Execution timed out, you can increase the timeout parameter and retry",
    ErrorType.VALIDATION: "Invalid parameters, please check and correct the parameters before retrying",
    ErrorType.RESOURCE_NOT_FOUND: "Target resource not found, please confirm the path/URL and retry",
    ErrorType.RATE_LIMIT: "Request rate too high, please wait a few seconds and retry",
    ErrorType.DEPENDENCY: "Missing dependency (command or library), please install it first and retry",
    ErrorType.AUTH: "Authentication issue — refresh credentials and retry",
    ErrorType.AUTH_PERMANENT: "Authentication permanently failed — user must re-auth manually",
    ErrorType.BILLING: "Billing error — check account quota or payment method",
    ErrorType.OVERLOADED: "Provider is overloaded — retry later or use a fallback profile",
    ErrorType.MODEL_NOT_FOUND: "Requested model not available — check model id in profile",
    ErrorType.CONTEXT_OVERFLOW: "Context window exceeded — shorten input or switch to a longer-context model",
    ErrorType.SERVER: "Provider server error (5xx) — retry after brief wait",
    ErrorType.NETWORK: "Network error — check connectivity and retry",
    ErrorType.CONTENT_FILTER: "Response blocked by content filter — rephrase the prompt",
    ErrorType.FORMAT: "Provider returned malformed output — retry once; if persistent, file a bug",
}


class ToolError(Exception):
    """
    Structured tool error.

    Contains error type, retry suggestion, alternative tools, and other info,
    serialized as JSON and returned to the LLM to help it make better decisions.
    """

    def __init__(
        self,
        error_type: ErrorType,
        tool_name: str,
        message: str,
        *,
        retry_suggestion: str | None = None,
        alternative_tools: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.error_type = error_type
        self.tool_name = tool_name
        self.message = message
        self.retry_suggestion = retry_suggestion
        self.alternative_tools = alternative_tools
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        result: dict[str, Any] = {
            "error": True,
            "error_type": self.error_type.value,
            "message": self.message,
            "tool_name": self.tool_name,
            "hint": _ERROR_TYPE_HINTS.get(self.error_type, ""),
        }
        if self.retry_suggestion:
            result["retry_suggestion"] = self.retry_suggestion
        if self.alternative_tools:
            result["alternative_tools"] = self.alternative_tools
        if self.details:
            result["details"] = self.details
        return result

    def to_tool_result(self) -> str:
        """
        Serialize as a tool_result string.

        Returned in JSON format so the LLM can parse the error_type field for decision-making.
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)


def classify_error(
    error: Exception,
    tool_name: str = "",
) -> ToolError:
    """
    Classify a generic exception as a structured ToolError.

    Automatically infers ErrorType based on exception type:
    - TimeoutError -> TIMEOUT
    - FileNotFoundError -> RESOURCE_NOT_FOUND
    - PermissionError -> PERMISSION
    - ValueError -> VALIDATION
    - ConnectionError -> TRANSIENT
    - Other -> PERMANENT
    """
    error_msg = str(error)

    if isinstance(error, ToolError):
        return error

    if isinstance(error, TimeoutError):
        return ToolError(
            error_type=ErrorType.TIMEOUT,
            tool_name=tool_name,
            message=error_msg,
            retry_suggestion="Increase the timeout parameter and retry",
        )

    if isinstance(error, FileNotFoundError):
        return ToolError(
            error_type=ErrorType.RESOURCE_NOT_FOUND,
            tool_name=tool_name,
            message=error_msg,
            retry_suggestion="Please confirm the file path is correct",
        )

    if isinstance(error, PermissionError):
        return ToolError(
            error_type=ErrorType.PERMISSION,
            tool_name=tool_name,
            message=error_msg,
        )

    if isinstance(error, ValueError):
        return ToolError(
            error_type=ErrorType.VALIDATION,
            tool_name=tool_name,
            message=error_msg,
            retry_suggestion="Please check the parameter format and value range",
        )

    if isinstance(error, (ConnectionError, OSError)):
        # Check if it's connection/network related
        lower_msg = error_msg.lower()
        if any(kw in lower_msg for kw in ("connect", "network", "refused", "timeout", "dns")):
            return ToolError(
                error_type=ErrorType.TRANSIENT,
                tool_name=tool_name,
                message=error_msg,
                retry_suggestion="Network issue, please retry later",
            )

    # Check common error patterns
    lower_msg = error_msg.lower()

    if "rate limit" in lower_msg or "too many requests" in lower_msg or "429" in lower_msg:
        return ToolError(
            error_type=ErrorType.RATE_LIMIT,
            tool_name=tool_name,
            message=error_msg,
            retry_suggestion="Please wait 5 seconds and retry",
        )

    if "not found" in lower_msg or "no such file" in lower_msg or "does not exist" in lower_msg:
        return ToolError(
            error_type=ErrorType.RESOURCE_NOT_FOUND,
            tool_name=tool_name,
            message=error_msg,
        )

    if "command not found" in lower_msg or "not recognized" in lower_msg:
        return ToolError(
            error_type=ErrorType.DEPENDENCY,
            tool_name=tool_name,
            message=error_msg,
            retry_suggestion="Please install the required command or tool first",
        )

    # Default to permanent error
    return ToolError(
        error_type=ErrorType.PERMANENT,
        tool_name=tool_name,
        message=error_msg,
    )


# ---------------------------------------------------------------------------
# CLI-specific error classification (Phase 2a)
# ---------------------------------------------------------------------------
# Rules fire top-to-bottom; first match wins. Keyword-only signature so
# callers don't accidentally swap `exit_code` and the old positional
# `tool_name` of `classify_error`.


_CONTEXT_OVERFLOW_NEEDLES = (
    "context window exceeded",
    "prompt tokens exceed",
    "token limit",
    "context length",
)
_AUTH_PERMANENT_NEEDLES = (
    "not logged in",
    "run: claude auth",
    "codex login",
    "token has expired",
)
_AUTH_NEEDLES = (
    "authentication failed",
    "401 unauthorized",
    "invalid api key",
)
_BILLING_NEEDLES = (
    "billing",
    "payment required",
    "quota exceeded",
    "402",
)
_RATE_LIMIT_NEEDLES = (
    "rate limit",
    "too many requests",
    "429",
)
_SERVER_NEEDLES = (
    "500 internal server error",
    "502 bad gateway",
    "503 service unavailable",
    "504 gateway timeout",
)
_NETWORK_NEEDLES = (
    "network unreachable",
    "connection refused",
    "connection reset",
    "dns resolution failed",
    "enotfound",
)
_MODEL_NOT_FOUND_NEEDLES = (
    "model not found",
    "unknown model",
    "unsupported model",
)
_CONTENT_FILTER_NEEDLES = (
    "content filter",
    "safety filter",
    "response blocked",
)
_FORMAT_NEEDLES = (
    "unexpected format",
    "malformed stream",
    "invalid jsonl",
    "could not parse",
)
_DEPENDENCY_NEEDLES = (
    "command not found",
    "not recognized",
    "no such file or directory",
)


def _any_match(haystack: str, needles: tuple[str, ...]) -> bool:
    lo = haystack.lower()
    return any(n in lo for n in needles)


def classify_cli_error(
    *,
    exit_code: int,
    stderr: str,
    exception: Exception | None = None,
) -> ErrorType:
    """Return the `ErrorType` that best matches a failed external-CLI run.

    Rule order (first match wins):
      1. Exit code specifics (124=timeout, 137=oomkill, 127=dep-missing).
      2. Stderr substring matching against needle lists above.
      3. Exception-type fallback via existing `classify_error`.
      4. Default: `ErrorType.PERMANENT`.
    """
    if exit_code == 124:
        return ErrorType.TIMEOUT
    if exit_code == 137:
        return ErrorType.OVERLOADED
    if exit_code == 127 or _any_match(stderr, _DEPENDENCY_NEEDLES):
        return ErrorType.DEPENDENCY

    if _any_match(stderr, _AUTH_PERMANENT_NEEDLES):
        return ErrorType.AUTH_PERMANENT
    if _any_match(stderr, _AUTH_NEEDLES):
        return ErrorType.AUTH
    if _any_match(stderr, _RATE_LIMIT_NEEDLES):
        return ErrorType.RATE_LIMIT
    if _any_match(stderr, _BILLING_NEEDLES):
        return ErrorType.BILLING
    if _any_match(stderr, _CONTEXT_OVERFLOW_NEEDLES):
        return ErrorType.CONTEXT_OVERFLOW
    if _any_match(stderr, _MODEL_NOT_FOUND_NEEDLES):
        return ErrorType.MODEL_NOT_FOUND
    if _any_match(stderr, _SERVER_NEEDLES):
        return ErrorType.SERVER
    if _any_match(stderr, _NETWORK_NEEDLES):
        return ErrorType.NETWORK
    if _any_match(stderr, _CONTENT_FILTER_NEEDLES):
        return ErrorType.CONTENT_FILTER
    if _any_match(stderr, _FORMAT_NEEDLES):
        return ErrorType.FORMAT

    if exception is not None:
        return classify_error(exception).error_type

    return ErrorType.PERMANENT
