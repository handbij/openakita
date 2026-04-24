"""Tests for WebFetchHandler."""

from unittest.mock import AsyncMock, MagicMock, patch
import httpx


async def test_web_fetch_max_length_string_coercion():
    """Verify max_length string is coerced to int during truncation.

    When LLM sends max_length as "100" (string) instead of 100 (int),
    the slice operation markdown[:max_length] should still work.
    """
    from openakita.tools.handlers.web_fetch import WebFetchHandler

    mock_agent = MagicMock()
    handler = WebFetchHandler(mock_agent)

    # Create a mock response with long content
    long_content = "x" * 500  # Content longer than max_length

    mock_response = MagicMock()
    mock_response.text = f"<html><body>{long_content}</body></html>"
    mock_response.headers = {"content-type": "text/html"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(httpx, "AsyncClient", return_value=mock_client):
        with patch("openakita.utils.url_safety.is_safe_url", return_value=(True, None)):
            # Call with string max_length (simulates LLM sending wrong type)
            # This would raise TypeError before the fix when doing markdown[:max_length]
            params = {"url": "https://example.com", "max_length": "100"}

            result = await handler._web_fetch(params)

            # Should truncate and include truncation message
            assert "[CONTENT_TRUNCATED]" in result
            assert "100" in result  # The max_length value should appear in message


async def test_web_fetch_max_length_int_preserved():
    """Verify int max_length works correctly."""
    from openakita.tools.handlers.web_fetch import WebFetchHandler

    mock_agent = MagicMock()
    handler = WebFetchHandler(mock_agent)

    # Create a mock response with long content
    long_content = "y" * 500

    mock_response = MagicMock()
    mock_response.text = f"<html><body>{long_content}</body></html>"
    mock_response.headers = {"content-type": "text/html"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(httpx, "AsyncClient", return_value=mock_client):
        with patch("openakita.utils.url_safety.is_safe_url", return_value=(True, None)):
            # Call with int max_length (normal case)
            params = {"url": "https://example.com", "max_length": 100}

            result = await handler._web_fetch(params)

            # Should truncate and include truncation message
            assert "[CONTENT_TRUNCATED]" in result
            assert "100" in result


async def test_web_fetch_max_length_non_numeric_string_fallback():
    """Verify non-numeric max_length (like 'unlimited') falls back to default."""
    from openakita.tools.handlers.web_fetch import WebFetchHandler

    mock_agent = MagicMock()
    handler = WebFetchHandler(mock_agent)

    # Create a mock response with content longer than default 15000
    long_content = "z" * 20000

    mock_response = MagicMock()
    mock_response.text = f"<html><body>{long_content}</body></html>"
    mock_response.headers = {"content-type": "text/html"}
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch.object(httpx, "AsyncClient", return_value=mock_client):
        with patch("openakita.utils.url_safety.is_safe_url", return_value=(True, None)):
            # Call with non-numeric string like "unlimited" or "auto"
            # Should fall back to default 15000 instead of raising ValueError
            params = {"url": "https://example.com", "max_length": "unlimited"}

            result = await handler._web_fetch(params)

            # Should truncate at default 15000 and include truncation message
            assert "[CONTENT_TRUNCATED]" in result
            assert "15000" in result  # Default max_length value
