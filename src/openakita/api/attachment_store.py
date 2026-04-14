from __future__ import annotations

import base64
import json
import logging
import mimetypes
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from contextlib import suppress

logger = logging.getLogger(__name__)

_TEXT_PREVIEW_LIMIT = 32_000
_MAX_DIRECTORY_ENTRIES = 1000
_DOCUMENT_MIME_PREFIXES = (
    "text/",
    "application/pdf",
    "application/json",
    "application/xml",
    "application/yaml",
)
_DOCUMENT_EXTENSIONS = {
    ".md", ".markdown", ".txt", ".json", ".yaml", ".yml", ".csv",
    ".py", ".ts", ".tsx", ".js", ".jsx", ".html", ".css", ".scss",
    ".java", ".go", ".rs", ".sh", ".bat", ".ps1", ".toml", ".ini",
    ".cfg", ".log", ".sql",
}


def _get_default_root() -> Path:
    try:
        from openakita.config import settings

        base = settings.data_dir
    except Exception:
        import os

        root = os.environ.get("OPENAKITA_ROOT", "").strip()
        base = Path(root) if root else Path.home() / ".openakita"
    path = Path(base) / "attachments"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_conversation_id(conversation_id: str | None) -> str:
    raw = (conversation_id or "shared").strip() or "shared"
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in raw)


def _guess_mime_type(filename: str, explicit_mime: str | None = None) -> str:
    if explicit_mime:
        return explicit_mime
    guessed = mimetypes.guess_type(filename)[0]
    return guessed or "application/octet-stream"


def classify_attachment_type(
    mime_type: str | None,
    filename: str = "",
    hinted_type: str | None = None,
) -> str:
    if hinted_type == "directory":
        return "directory"
    mime = (mime_type or "").lower()
    if hinted_type in {"image", "video", "voice", "audio", "document", "file"}:
        if hinted_type == "audio":
            return "voice"
        return hinted_type
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "voice"
    ext = Path(filename).suffix.lower()
    if mime in _DOCUMENT_MIME_PREFIXES or any(
        mime.startswith(prefix) for prefix in ("text/",)
    ) or ext in _DOCUMENT_EXTENSIONS:
        return "document"
    return "file"


def _is_text_like(mime_type: str, filename: str) -> bool:
    mime = (mime_type or "").lower()
    ext = Path(filename).suffix.lower()
    return mime.startswith("text/") or mime in _DOCUMENT_MIME_PREFIXES or ext in _DOCUMENT_EXTENSIONS


class AttachmentStore:
    def __init__(self, root: Path | None = None):
        self.root = root or _get_default_root()
        self.records_dir = self.root / "records"
        self.files_dir = self.root / "files"
        self.records_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, attachment_id: str) -> Path:
        return self.records_dir / f"{attachment_id}.json"

    def _conversation_dir(self, conversation_id: str | None) -> Path:
        path = self.files_dir / _safe_conversation_id(conversation_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_record(self, record: dict) -> dict:
        self._record_path(record["id"]).write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return record

    def get(self, attachment_id: str) -> dict | None:
        record_path = self._record_path(attachment_id)
        if not record_path.exists():
            return None
        try:
            return json.loads(record_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load attachment record %s: %s", attachment_id, exc)
            return None

    def resolve_content_path(self, record: dict) -> Path | None:
        storage_path = record.get("storage_path")
        if not storage_path:
            return None
        path = Path(storage_path)
        return path if path.exists() and path.is_file() else None

    def read_bytes(self, record: dict) -> bytes | None:
        path = self.resolve_content_path(record)
        if not path:
            return None
        try:
            return path.read_bytes()
        except Exception as exc:
            logger.warning("Failed to read attachment bytes %s: %s", record.get("id", ""), exc)
            return None

    def to_data_url(self, record: dict) -> str | None:
        data = self.read_bytes(record)
        if data is None:
            return None
        mime_type = record.get("mime_type") or "application/octet-stream"
        return f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"

    def build_client_attachment(self, record: dict) -> dict:
        return {
            "id": record["id"],
            "type": record["type"],
            "name": record["name"],
            "url": record.get("content_url"),
            "mime_type": record.get("mime_type"),
            "size": record.get("size"),
            "source_path": record.get("source_path"),
            "display_path": record.get("display_path"),
            "entries": record.get("entries"),
            "text_preview": record.get("text_preview"),
        }

    def _build_record(
        self,
        *,
        conversation_id: str | None,
        name: str,
        mime_type: str,
        attachment_type: str,
        size: int = 0,
        storage_path: str = "",
        source_path: str = "",
        display_path: str = "",
        entries: list[str] | None = None,
        text_preview: str = "",
        original_name: str = "",
    ) -> dict:
        attachment_id = uuid.uuid4().hex[:12]
        record = {
            "id": attachment_id,
            "conversation_id": _safe_conversation_id(conversation_id),
            "name": name,
            "original_name": original_name or name,
            "type": attachment_type,
            "mime_type": mime_type,
            "size": size,
            "storage_path": storage_path,
            "source_path": source_path,
            "display_path": display_path,
            "entries": entries or [],
            "text_preview": text_preview,
            "created_at": datetime.now().isoformat(),
            "content_url": f"/api/attachments/{attachment_id}/content" if storage_path else None,
        }
        return record

    def save_uploaded_file(
        self,
        *,
        content: bytes,
        filename: str,
        mime_type: str | None,
        conversation_id: str | None,
        hinted_type: str | None = None,
    ) -> dict:
        name = Path(filename or "file").name or "file"
        resolved_mime = _guess_mime_type(name, mime_type)
        attachment_type = classify_attachment_type(resolved_mime, name, hinted_type)
        ext = Path(name).suffix or mimetypes.guess_extension(resolved_mime) or ""
        attachment_id = uuid.uuid4().hex[:12]
        target = self._conversation_dir(conversation_id) / f"{attachment_id}{ext}"
        target.write_bytes(content)
        text_preview = ""
        if _is_text_like(resolved_mime, name):
            try:
                text_preview = content[:_TEXT_PREVIEW_LIMIT].decode("utf-8", errors="replace")
            except Exception:
                text_preview = ""
        record = {
            "id": attachment_id,
            "conversation_id": _safe_conversation_id(conversation_id),
            "name": name,
            "original_name": name,
            "type": attachment_type,
            "mime_type": resolved_mime,
            "size": len(content),
            "storage_path": str(target),
            "source_path": "",
            "display_path": "",
            "entries": [],
            "text_preview": text_preview,
            "created_at": datetime.now().isoformat(),
            "content_url": f"/api/attachments/{attachment_id}/content",
        }
        return self._write_record(record)

    def assign_to_conversation(self, attachment_id: str, conversation_id: str | None) -> dict | None:
        record = self.get(attachment_id)
        if not record:
            return None
        target_conversation = _safe_conversation_id(conversation_id)
        if record.get("conversation_id") == target_conversation:
            return record
        storage_path = record.get("storage_path", "")
        if storage_path:
            src = Path(storage_path)
            if src.exists() and src.is_file():
                target_dir = self._conversation_dir(target_conversation)
                target = target_dir / src.name
                if src.resolve() != target.resolve():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(target))
                    record["storage_path"] = str(target)
        record["conversation_id"] = target_conversation
        return self._write_record(record)

    def import_local_path(self, *, path: str, conversation_id: str | None) -> dict:
        source = Path(path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(path)
        if source.is_dir():
            all_entries = sorted(p.name for p in source.iterdir())
            entries = all_entries
            if len(all_entries) > _MAX_DIRECTORY_ENTRIES:
                entries = all_entries[:_MAX_DIRECTORY_ENTRIES] + [
                    f"... and {len(all_entries) - _MAX_DIRECTORY_ENTRIES} more entries",
                ]
            record = self._build_record(
                conversation_id=conversation_id,
                name=source.name or str(source),
                mime_type="inode/directory",
                attachment_type="directory",
                source_path=str(source),
                display_path=str(source),
                entries=entries,
            )
            return self._write_record(record)

        resolved_mime = _guess_mime_type(source.name, None)
        attachment_type = classify_attachment_type(resolved_mime, source.name, None)
        attachment_id = uuid.uuid4().hex[:12]
        target = self._conversation_dir(conversation_id) / f"{attachment_id}{source.suffix}"
        shutil.copy2(source, target)
        text_preview = ""
        if _is_text_like(resolved_mime, source.name):
            try:
                text_preview = source.read_text(encoding="utf-8", errors="replace")[:_TEXT_PREVIEW_LIMIT]
            except Exception:
                text_preview = ""
        record = {
            "id": attachment_id,
            "conversation_id": _safe_conversation_id(conversation_id),
            "name": source.name,
            "original_name": source.name,
            "type": attachment_type,
            "mime_type": resolved_mime,
            "size": source.stat().st_size,
            "storage_path": str(target),
            "source_path": str(source),
            "display_path": str(source),
            "entries": [],
            "text_preview": text_preview,
            "created_at": datetime.now().isoformat(),
            "content_url": f"/api/attachments/{attachment_id}/content",
        }
        return self._write_record(record)

    def delete_conversation(self, conversation_id: str | None) -> int:
        target_conversation = _safe_conversation_id(conversation_id)
        deleted = 0
        for record_path in self.records_dir.glob("*.json"):
            with suppress(Exception):
                record = json.loads(record_path.read_text(encoding="utf-8"))
                if record.get("conversation_id") != target_conversation:
                    continue
                storage_path = record.get("storage_path", "")
                if storage_path:
                    with suppress(FileNotFoundError):
                        Path(storage_path).unlink()
                record_path.unlink(missing_ok=True)
                deleted += 1
        conv_dir = self.files_dir / target_conversation
        with suppress(Exception):
            shutil.rmtree(conv_dir, ignore_errors=True)
        return deleted

    def cleanup_stale_shared(self, max_age_hours: int = 24) -> int:
        cutoff = datetime.now().timestamp() - max_age_hours * 3600
        deleted = 0
        for record_path in self.records_dir.glob("*.json"):
            with suppress(Exception):
                record = json.loads(record_path.read_text(encoding="utf-8"))
                if record.get("conversation_id") != "shared":
                    continue
                created_at = datetime.fromisoformat(record.get("created_at", datetime.now().isoformat()))
                if created_at.timestamp() >= cutoff:
                    continue
                storage_path = record.get("storage_path", "")
                if storage_path:
                    with suppress(FileNotFoundError):
                        Path(storage_path).unlink()
                record_path.unlink(missing_ok=True)
                deleted += 1
        if deleted:
            with suppress(Exception):
                shutil.rmtree(self.files_dir / "shared", ignore_errors=True)
        return deleted


_STORE: AttachmentStore | None = None


def get_attachment_store() -> AttachmentStore:
    global _STORE
    if _STORE is None:
        _STORE = AttachmentStore()
        _STORE.cleanup_stale_shared()
    return _STORE
