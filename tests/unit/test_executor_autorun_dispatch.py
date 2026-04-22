"""Dispatch routing for the autorun_playbook system action."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_task(action: str = "system:autorun_playbook"):
    t = MagicMock()
    t.action = action
    t.task_id = "tsk-xyz"
    t.agent_profile_id = "default"
    t.metadata = {
        "playbook": {
            "documents": [{"filename": "/tmp/plan.md"}],
            "prompt": "do the thing",
        }
    }
    return t


@pytest.mark.asyncio
async def test_system_autorun_playbook_delegates_to_playbookrun():
    from openakita.scheduler.executor import TaskExecutor

    exec_ = TaskExecutor()
    task = _make_task()

    run_instance = MagicMock()
    run_instance.execute = AsyncMock(return_value=(True, "completed 1 loop(s)"))
    store_sentinel = MagicMock(name="ProfileStore")

    with patch("openakita.scheduler.autorun_playbook.PlaybookRun",
               return_value=run_instance) as run_cls, \
         patch("openakita.agents.profile.get_profile_store",
               return_value=store_sentinel):
        ok, msg = await exec_._system_autorun_playbook(task)

    assert (ok, msg) == (True, "completed 1 loop(s)")
    run_cls.assert_called_once_with(task, executor=exec_, profile_store=store_sentinel)
    run_instance.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_system_task_routes_autorun_to_method():
    """_execute_system_task must route 'system:autorun_playbook' into the
    dedicated handler (and bypass SYSTEM_TASK_TIMEOUTS — confirmed by the
    fact that the mocked method is awaited exactly once with no wrapping)."""
    from openakita.scheduler.executor import TaskExecutor

    exec_ = TaskExecutor()
    task = _make_task()

    async def fake_handler(t):
        assert t is task
        return True, "ok"

    with patch.object(exec_, "_system_autorun_playbook",
                      side_effect=fake_handler) as handler:
        ok, msg = await exec_._execute_system_task(task)

    assert (ok, msg) == (True, "ok")
    handler.assert_called_once_with(task)


@pytest.mark.asyncio
async def test_execute_system_task_unknown_action_still_rejected():
    """Regression guard: adding the autorun branch must not break the existing
    unknown-action error path."""
    from openakita.scheduler.executor import TaskExecutor

    exec_ = TaskExecutor()
    task = _make_task(action="system:does_not_exist")

    ok, msg = await exec_._execute_system_task(task)
    assert ok is False
    assert "Unknown system action" in msg
