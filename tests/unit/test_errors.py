"""L1 Unit Tests: Error types, classification, and tool errors."""

import pytest

from openakita.core.errors import UserCancelledError
from openakita.tools.errors import ErrorType, ToolError, classify_cli_error, classify_error


class TestUserCancelledError:
    def test_create_basic(self):
        err = UserCancelledError()
        assert isinstance(err, Exception)

    def test_create_with_reason(self):
        err = UserCancelledError(reason="用户按了取消", source="cli")
        assert "取消" in err.reason
        assert err.source == "cli"


class TestToolError:
    def test_create_tool_error(self):
        err = ToolError(
            error_type=ErrorType.TRANSIENT,
            tool_name="web_search",
            message="Connection timeout",
        )
        assert err.error_type == ErrorType.TRANSIENT
        assert err.tool_name == "web_search"

    def test_to_dict(self):
        err = ToolError(
            error_type=ErrorType.PERMISSION,
            tool_name="write_file",
            message="Permission denied",
            retry_suggestion="Try a different path",
        )
        d = err.to_dict()
        assert d["error_type"] == "permission"
        assert d["tool_name"] == "write_file"
        assert "retry_suggestion" in d

    def test_to_tool_result(self):
        err = ToolError(
            error_type=ErrorType.RESOURCE_NOT_FOUND,
            tool_name="read_file",
            message="File not found",
        )
        result = err.to_tool_result()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_alternatives(self):
        err = ToolError(
            error_type=ErrorType.PERMANENT,
            tool_name="browser_open",
            message="Browser not available",
            alternative_tools=["web_search"],
        )
        assert err.alternative_tools == ["web_search"]


class TestErrorClassification:
    def test_classify_timeout(self):
        err = classify_error(TimeoutError("Request timed out"), tool_name="web_search")
        assert isinstance(err, ToolError)
        assert err.error_type in (ErrorType.TIMEOUT, ErrorType.TRANSIENT)

    def test_classify_permission(self):
        err = classify_error(PermissionError("Access denied"), tool_name="write_file")
        assert isinstance(err, ToolError)
        assert err.error_type == ErrorType.PERMISSION

    def test_classify_file_not_found(self):
        err = classify_error(FileNotFoundError("No such file"), tool_name="read_file")
        assert isinstance(err, ToolError)
        assert err.error_type == ErrorType.RESOURCE_NOT_FOUND

    def test_classify_generic(self):
        err = classify_error(RuntimeError("Something broke"), tool_name="unknown")
        assert isinstance(err, ToolError)


class TestErrorTypes:
    def test_all_types_exist(self):
        types = [
            ErrorType.TRANSIENT, ErrorType.PERMANENT, ErrorType.PERMISSION,
            ErrorType.TIMEOUT, ErrorType.VALIDATION, ErrorType.RESOURCE_NOT_FOUND,
            ErrorType.RATE_LIMIT, ErrorType.DEPENDENCY,
        ]
        assert len(types) == 8


# ---------------------------------------------------------------------------
# Plan 06: CLI ErrorType extensions + classify_cli_error
# ---------------------------------------------------------------------------

def test_new_error_type_members_present():
    for name in (
        "AUTH", "AUTH_PERMANENT", "BILLING", "OVERLOADED",
        "MODEL_NOT_FOUND", "CONTEXT_OVERFLOW", "SERVER",
        "NETWORK", "CONTENT_FILTER", "FORMAT",
    ):
        assert hasattr(ErrorType, name), f"missing: {name}"


@pytest.mark.parametrize(
    "exit_code, stderr, expected",
    [
        (1,   "Not logged in. Run: claude auth", ErrorType.AUTH_PERMANENT),
        (1,   "authentication failed",           ErrorType.AUTH),
        (2,   "rate limit exceeded",             ErrorType.RATE_LIMIT),
        (1,   "429 Too Many Requests",           ErrorType.RATE_LIMIT),
        (1,   "payment required",                ErrorType.BILLING),
        (1,   "billing account inactive",        ErrorType.BILLING),
        (124, "",                                ErrorType.TIMEOUT),
        (137, "killed",                          ErrorType.OVERLOADED),
        (1,   "model not found: claude-3.5",    ErrorType.MODEL_NOT_FOUND),
        (1,   "context window exceeded",         ErrorType.CONTEXT_OVERFLOW),
        (1,   "prompt tokens exceed limit",      ErrorType.CONTEXT_OVERFLOW),
        (1,   "500 internal server error",       ErrorType.SERVER),
        (1,   "503 service unavailable",         ErrorType.SERVER),
        (1,   "network unreachable",             ErrorType.NETWORK),
        (1,   "response blocked by safety filter", ErrorType.CONTENT_FILTER),
        (1,   "unexpected format in stream-json", ErrorType.FORMAT),
        (127, "claude: command not found",       ErrorType.DEPENDENCY),
    ],
)
def test_classify_cli_error_rules(exit_code: int, stderr: str, expected: ErrorType):
    assert classify_cli_error(exit_code=exit_code, stderr=stderr) == expected


def test_classify_cli_error_falls_back_to_permanent():
    assert classify_cli_error(exit_code=1, stderr="weird unclassified thing") == ErrorType.PERMANENT


def test_classify_cli_error_uses_exception_fallback():
    assert classify_cli_error(
        exit_code=1, stderr="",
        exception=TimeoutError("wall-clock")
    ) == ErrorType.TIMEOUT
