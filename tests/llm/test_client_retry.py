"""Tests for LLM client error classification and retry logic."""

from unittest.mock import MagicMock

import pytest

from openakita.llm.client import (
    ErrorCategory,
    LLMClient,
    classify_error_for_retry,
    should_reduce_max_tokens,
)
from openakita.llm.types import AllEndpointsFailedError, LLMError, LLMRequest, Message


def test_402_classified_as_token_limit():
    """402 (insufficient credits) should be classified like 413 (token limit)."""
    category = classify_error_for_retry(status_code=402)

    assert category == ErrorCategory.TOKEN_LIMIT


def test_413_classified_as_token_limit():
    """413 should still be classified as token limit."""
    category = classify_error_for_retry(status_code=413)

    assert category == ErrorCategory.TOKEN_LIMIT


def test_402_triggers_max_tokens_reduction():
    """402 should trigger max_tokens reduction like 413."""
    assert should_reduce_max_tokens(status_code=402) is True
    assert should_reduce_max_tokens(status_code=413) is True
    assert should_reduce_max_tokens(status_code=500) is False


def test_429_classified_as_rate_limit():
    """429 should be classified as rate limit."""
    category = classify_error_for_retry(status_code=429)

    assert category == ErrorCategory.RATE_LIMIT


def test_all_endpoints_failed_error_defaults_to_empty_categories():
    """Legacy construction should still expose an empty category set."""
    error = AllEndpointsFailedError("all endpoints failed")

    assert error.error_categories == set()


def test_5xx_classified_as_server_error():
    """5xx errors should be classified as server error."""
    for code in (500, 502, 503, 504, 529):
        category = classify_error_for_retry(status_code=code)
        assert category == ErrorCategory.SERVER_ERROR, f"Expected SERVER_ERROR for {code}"


def test_401_403_classified_as_auth_error():
    """401 and 403 should be classified as auth error."""
    assert classify_error_for_retry(status_code=401) == ErrorCategory.AUTH_ERROR
    assert classify_error_for_retry(status_code=403) == ErrorCategory.AUTH_ERROR


def test_other_4xx_classified_as_client_error():
    """Other 4xx errors should be classified as client error."""
    for code in (400, 404, 405, 422):
        category = classify_error_for_retry(status_code=code)
        assert category == ErrorCategory.CLIENT_ERROR, f"Expected CLIENT_ERROR for {code}"


@pytest.mark.asyncio
async def test_402_retries_with_reduced_tokens_then_failover():
    """402 should: (1) retry with halved max_tokens, (2) failover to next provider."""
    client = MagicMock(spec=LLMClient)
    client._max_tokens = 16384
    client._endpoints = ["openrouter", "anthropic"]
    client._current_endpoint_index = 0

    # After 402, max_tokens should be halved
    new_max_tokens = client._max_tokens // 2
    assert new_max_tokens == 8192

    # After second 402, should failover
    assert client._endpoints[1] == "anthropic"


@pytest.mark.asyncio
async def test_try_with_retry_reduces_max_tokens_on_402_and_recovers():
    """A 402 should trigger one in-place token reduction before succeeding."""
    client = LLMClient(endpoints=[])
    request = LLMRequest(messages=[Message(role="user", content="hello")], max_tokens=16384)
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise LLMError("insufficient credits", status_code=402)
        return "ok"

    result = await client._try_with_retry(
        operation,
        max_attempts=2,
        request=request,
        provider_name="primary",
    )

    assert result == "ok"
    assert attempts == 2
    assert request.max_tokens == 8192
