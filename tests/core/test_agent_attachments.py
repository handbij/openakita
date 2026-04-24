# tests/core/test_agent_attachments.py
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_voice_attachment_resolved_to_local_file():
    """Voice attachment URL should be downloaded to local temp file."""
    from openakita.core.agent import resolve_attachment_to_local

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF....WAVEfmt ")  # Minimal WAV header
        temp_path = f.name

    # file:// URL should resolve directly
    local_path = await resolve_attachment_to_local(f"file://{temp_path}")
    assert local_path == temp_path

    Path(temp_path).unlink()


@pytest.mark.asyncio
async def test_voice_attachment_http_downloaded():
    """HTTP voice attachment should be downloaded."""
    from openakita.core.agent import resolve_attachment_to_local

    with patch("httpx.AsyncClient") as mock_client:
        mock_response = MagicMock()
        mock_response.content = b"RIFF....WAVEfmt "
        mock_response.raise_for_status = MagicMock()

        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_response
        )

        local_path = await resolve_attachment_to_local(
            "https://example.com/audio.wav"
        )

        assert local_path is not None
        assert local_path.endswith(".wav")


@pytest.mark.asyncio
async def test_voice_attachment_transcribed():
    """Voice attachment should be transcribed via MediaHandler."""
    from openakita.core.agent import process_voice_attachment

    # Create a real temp file so resolve_attachment_to_local can find it
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b"RIFF....WAVEfmt ")
        temp_path = f.name

    try:
        mock_handler = MagicMock()
        mock_handler.transcribe_audio = AsyncMock(return_value="Hello world")

        transcript = await process_voice_attachment(
            url=f"file://{temp_path}",
            handler=mock_handler,
        )

        assert transcript == "Hello world"
        mock_handler.transcribe_audio.assert_called_once()
    finally:
        Path(temp_path).unlink()
