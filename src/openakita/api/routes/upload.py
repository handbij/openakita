"""
Upload route: POST /api/upload, GET /api/uploads/{filename}

文件/图片/语音上传和下载端点。
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from openakita.api.attachment_store import get_attachment_store

logger = logging.getLogger(__name__)

router = APIRouter()


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB
BLOCKED_EXTENSIONS = {".exe", ".bat", ".cmd", ".com", ".scr", ".pif", ".msi", ".sh", ".ps1"}


@router.post("/api/upload")
async def upload_file(  # noqa: B008
    file: UploadFile = File(...),
    conversation_id: str | None = Form(None),
    type: str | None = Form(None),
):
    """
    Upload a file (image, audio, document).
    Returns the file URL for use in chat messages.
    """
    store = get_attachment_store()

    # 安全检查：阻止危险文件扩展名
    ext = Path(file.filename or "file").suffix.lower()
    if ext in BLOCKED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不允许上传该类型文件: {ext}")

    # Save file（带大小限制）
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大: {len(content) / 1024 / 1024:.1f} MB（最大 {MAX_UPLOAD_SIZE // 1024 // 1024} MB）",
        )
    attachment_record = store.save_uploaded_file(
        content=content,
        filename=file.filename or "file",
        mime_type=file.content_type,
        conversation_id=conversation_id,
        hinted_type=type,
    )
    attachment = store.build_client_attachment(attachment_record)

    return {
        "status": "ok",
        "filename": attachment_record["name"],
        "original_name": file.filename,
        "size": len(content),
        "content_type": file.content_type,
        "url": attachment_record["content_url"],
        "attachment_id": attachment_record["id"],
        "attachment": attachment,
    }


@router.get("/api/uploads/{filename}")
async def serve_upload(filename: str):
    """
    Serve an uploaded file by its unique filename.
    """
    # Legacy compatibility endpoint. Chat attachments now use /api/attachments/{id}/content.
    try:
        from openakita.config import settings

        upload_dir = Path(settings.data_dir) / "uploads"
    except Exception:
        upload_dir = Path.home() / ".openakita" / "uploads"
    filepath = (upload_dir / filename).resolve()

    # 防止路径穿越：确保文件在 upload_dir 内
    # 使用 is_relative_to（比 str.startswith 更安全，避免前缀碰撞如 uploads_evil/）
    upload_dir_resolved = upload_dir.resolve()
    try:
        filepath.relative_to(upload_dir_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not filepath.exists() or not filepath.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # 推断 MIME 类型
    media_type = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"
    return FileResponse(filepath, media_type=media_type)


@router.get("/api/attachments/{attachment_id}/content")
async def serve_attachment_content(attachment_id: str):
    record = get_attachment_store().get(attachment_id)
    if not record:
        raise HTTPException(status_code=404, detail="Attachment not found")
    content_path = get_attachment_store().resolve_content_path(record)
    if not content_path:
        raise HTTPException(status_code=404, detail="Attachment has no stored file")
    media_type = record.get("mime_type") or mimetypes.guess_type(str(content_path))[0]
    return FileResponse(content_path, media_type=media_type or "application/octet-stream")


@router.post("/api/attachments/reference")
async def create_local_path_reference():
    raise HTTPException(
        status_code=410,
        detail=(
            "该接口已停用。请改为直接上传文件内容；"
            "目录引用请由本地桌面端先解析目录元数据后再随聊天请求发送。"
        ),
    )
