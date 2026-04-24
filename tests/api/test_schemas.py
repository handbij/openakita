# tests/api/test_schemas.py
import pytest
from openakita.api.schemas import AttachmentInfo, AttachmentType


def test_attachment_type_enum_values():
    assert AttachmentType.IMAGE.value == "image"
    assert AttachmentType.FILE.value == "file"
    assert AttachmentType.VOICE.value == "voice"


def test_attachment_info_accepts_enum():
    att = AttachmentInfo(
        type=AttachmentType.VOICE,
        name="recording.wav",
    )
    assert att.type == AttachmentType.VOICE


def test_attachment_info_accepts_string_coerces_to_enum():
    att = AttachmentInfo(
        type="voice",
        name="recording.wav",
    )
    assert att.type == AttachmentType.VOICE


def test_attachment_info_rejects_invalid_type():
    with pytest.raises(ValueError):
        AttachmentInfo(
            type="invalid_type",
            name="file.txt",
        )
