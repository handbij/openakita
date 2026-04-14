from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from openakita.api.attachment_store import AttachmentStore


class TestAttachmentStore:
    def test_save_uploaded_file_returns_reference_attachment(self, tmp_path):
        store = AttachmentStore(root=tmp_path)

        record = store.save_uploaded_file(
            content=b"hello attachment",
            filename="note.txt",
            mime_type="text/plain",
            conversation_id="conv-a",
        )

        assert record["conversation_id"] == "conv-a"
        assert record["type"] == "document"
        assert record["content_url"].startswith("/api/attachments/")
        assert Path(record["storage_path"]).exists()
        assert "hello attachment" in record["text_preview"]

    def test_import_local_directory_as_listing_reference(self, tmp_path):
        store = AttachmentStore(root=tmp_path / "store")
        folder = tmp_path / "folder"
        folder.mkdir()
        (folder / "a.txt").write_text("a", encoding="utf-8")
        (folder / "b.txt").write_text("b", encoding="utf-8")

        record = store.import_local_path(path=str(folder), conversation_id="conv-dir")

        assert record["type"] == "directory"
        assert record["storage_path"] == ""
        assert sorted(record["entries"]) == ["a.txt", "b.txt"]

    def test_assign_to_conversation_moves_file(self, tmp_path):
        store = AttachmentStore(root=tmp_path)
        record = store.save_uploaded_file(
            content=b"abc",
            filename="image.png",
            mime_type="image/png",
            conversation_id=None,
        )

        old_path = Path(record["storage_path"])
        moved = store.assign_to_conversation(record["id"], "conv-final")

        assert moved is not None
        assert moved["conversation_id"] == "conv-final"
        assert Path(moved["storage_path"]).exists()
        assert not old_path.exists()

    def test_cleanup_stale_shared_removes_orphans(self, tmp_path):
        store = AttachmentStore(root=tmp_path)
        record = store.save_uploaded_file(
            content=b"old",
            filename="old.txt",
            mime_type="text/plain",
            conversation_id=None,
        )
        record_path = store._record_path(record["id"])
        data = json.loads(record_path.read_text(encoding="utf-8"))
        data["created_at"] = (datetime.now() - timedelta(days=2)).isoformat()
        record_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        deleted = store.cleanup_stale_shared(max_age_hours=24)

        assert deleted == 1
        assert store.get(record["id"]) is None
