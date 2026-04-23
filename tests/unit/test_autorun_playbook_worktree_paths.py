from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def make_task():
    def _make(
        *,
        task_id: str = "tsk-abc",
        documents: list[dict] | None = None,
        prompt: str = "Do the next task.",
        loop_enabled: bool = False,
        max_loops: int | None = None,
        worktree: dict | None = None,
        agent_profile_id: str = "default",
    ):
        t = MagicMock()
        t.task_id = task_id
        t.agent_profile_id = agent_profile_id
        t.metadata = {
            "playbook": {
                "documents": documents
                or [{"filename": "/tmp/x.md", "reset_on_completion": False}],
                "prompt": prompt,
                "loop_enabled": loop_enabled,
                "max_loops": max_loops,
                "worktree": worktree or {"enabled": False},
            }
        }
        return t

    return _make


@pytest.fixture
def profile_store_mock():
    store = MagicMock()
    store.get = MagicMock(return_value=MagicMock(profile_id="default"))
    return store


@pytest.fixture
def agent_factory_mock():
    agent = AsyncMock()
    agent.execute_task_from_message = AsyncMock(return_value=None)
    agent.shutdown = AsyncMock(return_value=None)
    factory = MagicMock()
    factory.create = AsyncMock(return_value=agent)
    return factory, agent


def test_playbook_maps_project_relative_doc_into_worktree(
    tmp_path,
    make_task,
    profile_store_mock,
    agent_factory_mock,
):
    from openakita.scheduler.autorun_playbook import PlaybookDocumentSpec, PlaybookRun
    from openakita.utils.worktree import WorktreeInfo

    root = tmp_path / "repo"
    root.mkdir()
    (root / "docs").mkdir()
    (root / "docs" / "plan.md").write_text("- [ ] work\n")
    worktree = tmp_path / "wt"
    (worktree / "docs").mkdir(parents=True)
    (worktree / "docs" / "plan.md").write_text("- [ ] work\n")

    factory, _agent = agent_factory_mock
    task = make_task(
        documents=[{"filename": str(root / "docs" / "plan.md"), "reset_on_completion": False}],
        worktree={"enabled": True, "project_root": str(root)},
    )
    run = PlaybookRun(task, executor=MagicMock(), profile_store=profile_store_mock, agent_factory=factory)
    run.wt_info = WorktreeInfo(path=worktree, branch="b", agent_id="a", created_at=datetime.now())

    mapped = Path(run._effective_path(PlaybookDocumentSpec(filename=str(root / "docs" / "plan.md")), 0))

    assert mapped == worktree / "docs" / "plan.md"


def test_playbook_maps_relative_doc_into_configured_project_worktree(
    tmp_path,
    make_task,
    profile_store_mock,
    agent_factory_mock,
):
    from openakita.scheduler.autorun_playbook import PlaybookDocumentSpec, PlaybookRun
    from openakita.utils.worktree import WorktreeInfo

    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "plan.md").write_text("- [ ] work\n")
    worktree = tmp_path / "wt"
    (worktree / "docs").mkdir(parents=True)
    (worktree / "docs" / "plan.md").write_text("- [ ] work\n")

    factory, _agent = agent_factory_mock
    task = make_task(
        documents=[{"filename": "docs/plan.md", "reset_on_completion": False}],
        worktree={"enabled": True, "project_root": str(root)},
    )
    run = PlaybookRun(task, executor=MagicMock(), profile_store=profile_store_mock, agent_factory=factory)
    run.wt_info = WorktreeInfo(path=worktree, branch="b", agent_id="a", created_at=datetime.now())

    mapped = Path(run._effective_path(PlaybookDocumentSpec(filename="docs/plan.md"), 0))

    assert mapped == worktree / "docs" / "plan.md"


@pytest.mark.asyncio
async def test_playbook_without_project_root_uses_cwd_for_worktree_creation_and_mapping(
    tmp_path,
    make_task,
    profile_store_mock,
    agent_factory_mock,
    monkeypatch,
):
    from openakita.scheduler import autorun_playbook as ap
    from openakita.scheduler.autorun_playbook import PlaybookDocumentSpec, PlaybookRun
    from openakita.utils.worktree import WorktreeInfo

    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "plan.md").write_text("- [ ] work\n")
    worktree = tmp_path / "wt"
    (worktree / "docs").mkdir(parents=True)
    (worktree / "docs" / "plan.md").write_text("- [ ] work\n")
    monkeypatch.chdir(root)

    factory, _agent = agent_factory_mock
    task = make_task(
        documents=[{"filename": "docs/plan.md", "reset_on_completion": False}],
        worktree={"enabled": True},
    )
    run = PlaybookRun(task, executor=MagicMock(), profile_store=profile_store_mock, agent_factory=factory)

    wt_info = WorktreeInfo(path=worktree, branch="b", agent_id="a", created_at=datetime.now())
    create_worktree = AsyncMock(return_value=wt_info)
    monkeypatch.setattr(ap, "create_agent_worktree", create_worktree)

    run.wt_info = await run._maybe_create_worktree()

    create_worktree.assert_awaited_once_with(agent_id=run.run_id, project_root=root.resolve())
    mapped = Path(run._effective_path(PlaybookDocumentSpec(filename="docs/plan.md"), 0))
    assert mapped == worktree / "docs" / "plan.md"


def test_playbook_rejects_doc_outside_project_root(
    tmp_path,
    make_task,
    profile_store_mock,
    agent_factory_mock,
):
    from openakita.scheduler.autorun_playbook import PlaybookDocumentSpec, PlaybookRun
    from openakita.utils.worktree import WorktreeInfo

    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.md"
    outside.write_text("- [ ] no\n")
    worktree = tmp_path / "wt"
    worktree.mkdir()

    factory, _agent = agent_factory_mock
    task = make_task(
        documents=[{"filename": str(outside), "reset_on_completion": False}],
        worktree={"enabled": True, "project_root": str(root)},
    )
    run = PlaybookRun(task, executor=MagicMock(), profile_store=profile_store_mock, agent_factory=factory)
    run.wt_info = WorktreeInfo(path=worktree, branch="b", agent_id="a", created_at=datetime.now())

    with pytest.raises(ValueError, match="outside project_root"):
        run._effective_path(PlaybookDocumentSpec(filename=str(outside)), 0)
