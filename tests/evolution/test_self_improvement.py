"""Tests for :mod:`openakita.evolution.self_improvement`.

Covers:
- Issue extraction from synthetic DailyReport objects
- Deduplication of issues by (source, component, evidence)
- ImprovementRun state transitions and terminal detection
- Persistence round-trip (save → load)
- ``run_from_report`` end-to-end flow with approval/rejection and empty report
- Settings defaults keep the workflow disabled
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from openakita.config import Settings
from openakita.evolution.self_check import DailyReport, FixRecord
from openakita.evolution.self_improvement import (
    STATUS_AWAITING_APPROVAL,
    STATUS_BLOCKED,
    STATUS_COMPLETED,
    ImprovementRun,
    SelfImprovementIssue,
    SelfImprovementOrchestrator,
)


def _make_orchestrator(tmp_path: Path) -> SelfImprovementOrchestrator:
    storage = tmp_path / "improvements"
    plans = tmp_path / "plans"
    return SelfImprovementOrchestrator(storage_dir=storage, plans_dir=plans)


def _empty_report(date: str = "2026-04-23") -> DailyReport:
    return DailyReport(date=date, timestamp=datetime(2026, 4, 23, 3, 0, 0))


def _rich_report(date: str = "2026-04-23") -> DailyReport:
    return DailyReport(
        date=date,
        timestamp=datetime(2026, 4, 23, 3, 0, 0),
        core_error_patterns=[
            {
                "pattern": "TokenBudgetExhaustedError",
                "count": 7,
                "logger": "openakita.core.reasoning_engine",
                "message": "Budget exceeded on iteration 14",
                "last_seen": "2026-04-23T02:45:00",
            },
            {
                "pattern": "StreamParseError",
                "count": 1,
                "logger": "openakita.llm.parser",
                "message": "Stream disconnect during SSE",
            },
        ],
        fix_records=[
            FixRecord(
                error_pattern="FileWriteRace",
                component="tools.file",
                fix_action="retry_on_race",
                fix_time=datetime(2026, 4, 23, 2, 30, 0),
                success=False,
                verification_result="still races when parallel",
            ),
            FixRecord(
                error_pattern="ShellTimeoutIgnored",
                component="tools.shell",
                fix_action="propagate_timeout",
                fix_time=datetime(2026, 4, 23, 2, 40, 0),
                success=True,
                verification_result="",
            ),
        ],
        retrospect_summary={
            "common_issues": [
                {"description": "ReAct loop stalls after tool errors", "component": "reasoning_engine"},
                "Tool chaining regresses on long plans",
            ],
        },
        memory_insights={
            "optimization_suggestions": [
                {
                    "rationale": "Duplicate user memories persist for weeks",
                    "component": "memory",
                    "severity": "medium",
                },
                "Consider indexing by source session id",
            ],
        },
    )


# ── Issue extraction ──


def test_extract_issues_empty_report(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    assert orchestrator.extract_issues(_empty_report()) == []


def test_extract_issues_from_rich_report(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    issues = orchestrator.extract_issues(_rich_report())

    sources = {i.source for i in issues}
    assert sources == {
        "core_error_patterns",
        "failed_fix_records",
        "retrospect_summary",
        "memory_insights",
    }

    critical_core = [i for i in issues if i.source == "core_error_patterns" and i.severity == "critical"]
    assert len(critical_core) == 1
    assert critical_core[0].component == "openakita.core.reasoning_engine"

    failed = [i for i in issues if i.source == "failed_fix_records"]
    assert len(failed) == 1
    assert failed[0].component == "tools.file"


def test_extract_issues_skips_successful_fix_records(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    report = DailyReport(
        date="2026-04-23",
        timestamp=datetime(2026, 4, 23),
        fix_records=[
            FixRecord(
                error_pattern="x",
                component="c",
                fix_action="a",
                fix_time=datetime(2026, 4, 23),
                success=True,
            ),
        ],
    )
    assert orchestrator.extract_issues(report) == []


def test_extract_issues_deduplicates(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    report = DailyReport(
        date="2026-04-23",
        timestamp=datetime(2026, 4, 23),
        core_error_patterns=[
            {"pattern": "E1", "count": 2, "logger": "m", "message": "boom"},
            {"pattern": "E1", "count": 3, "logger": "m", "message": "boom"},
        ],
    )
    issues = orchestrator.extract_issues(report)
    assert len(issues) == 1


# ── Plan writing + persistence ──


def test_create_plan_file_writes_markdown(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    issues = orchestrator.extract_issues(_rich_report())
    run = ImprovementRun(
        id="run001",
        report_date="2026-04-23",
        status="detected",
    )
    plan = asyncio.run(orchestrator.create_plan_file(issues, run))
    content = plan.read_text(encoding="utf-8")
    assert "Self-Improvement Plan" in content
    assert "CRITICAL" in content
    assert plan.name.endswith(".md")
    assert plan.parent == tmp_path / "plans"


def test_save_and_load_run_round_trip(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    run = ImprovementRun(
        id="abc123",
        report_date="2026-04-23",
        status="detected",
        approval_required=False,
        runner="native",
    )
    orchestrator._save_run(run)
    loaded = orchestrator._load_run("abc123")
    assert loaded is not None
    assert loaded.report_date == "2026-04-23"
    assert loaded.runner == "native"

    latest = tmp_path / "improvements" / "latest_run.json"
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["id"] == "abc123"


def test_is_terminal(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    assert orchestrator.is_terminal(ImprovementRun(id="x", report_date="d", status=STATUS_COMPLETED))
    assert orchestrator.is_terminal(ImprovementRun(id="x", report_date="d", status=STATUS_BLOCKED))
    assert not orchestrator.is_terminal(ImprovementRun(id="x", report_date="d", status="executing"))


# ── run_from_report end-to-end flows ──


@pytest.mark.asyncio
async def test_run_from_report_with_no_issues_completes_immediately(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    run = await orchestrator.run_from_report(_empty_report())
    assert run.status == STATUS_COMPLETED
    assert "no_actionable_issues" in run.blockers


@pytest.mark.asyncio
async def test_run_from_report_blocks_when_approval_denied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orchestrator = _make_orchestrator(tmp_path)

    async def fast_wait(run: ImprovementRun, **_: object) -> bool:  # type: ignore[override]
        reject = orchestrator._storage_dir / f"{run.id}.rejected"
        reject.touch()
        return False

    monkeypatch.setattr(orchestrator, "wait_for_approval", fast_wait)
    # Ensure the global approval_required flag is on for this run.
    monkeypatch.setattr(
        "openakita.evolution.self_improvement.settings.self_improvement_requires_approval",
        True,
        raising=False,
    )

    run = await orchestrator.run_from_report(_rich_report())
    assert run.status == STATUS_BLOCKED
    assert "approval_denied_or_timed_out" in run.blockers


@pytest.mark.asyncio
async def test_run_from_report_without_approval_runs_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    # Drop the approval gate for this scenario and force native runner so
    # we don't even attempt to spawn a CLI subprocess.
    monkeypatch.setattr(
        "openakita.evolution.self_improvement.settings.self_improvement_requires_approval",
        False,
        raising=False,
    )
    monkeypatch.setattr(
        "openakita.evolution.self_improvement.settings.self_improvement_runner",
        "native",
        raising=False,
    )

    run = await orchestrator.run_from_report(_rich_report())
    assert run.status == STATUS_COMPLETED
    assert run.plan_path is not None
    assert run.verification_results.get("final", {}).get("passed") is True


@pytest.mark.asyncio
async def test_wait_for_approval_returns_false_on_timeout(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    run = ImprovementRun(
        id="timeout-run",
        report_date="2026-04-23",
        status=STATUS_AWAITING_APPROVAL,
    )
    # Give it a tiny deadline so the test is fast.
    approved = await orchestrator.wait_for_approval(
        run, poll_interval_seconds=0.01, max_wait_seconds=0.05
    )
    assert approved is False


@pytest.mark.asyncio
async def test_wait_for_approval_sees_approved_sentinel(tmp_path: Path) -> None:
    orchestrator = _make_orchestrator(tmp_path)
    run = ImprovementRun(
        id="approved-run",
        report_date="2026-04-23",
        status=STATUS_AWAITING_APPROVAL,
    )
    # Write the sentinel up-front so the first poll sees it.
    (orchestrator._storage_dir / f"{run.id}.approved").touch()
    approved = await orchestrator.wait_for_approval(
        run, poll_interval_seconds=0.01, max_wait_seconds=0.5
    )
    assert approved is True


# ── Settings defaults ──


def test_settings_defaults_keep_workflow_disabled() -> None:
    s = Settings()
    assert s.self_improvement_enabled is False
    assert s.self_improvement_requires_approval is True
    assert s.self_improvement_runner == "hybrid"
    assert s.self_improvement_max_parallel_reviewers >= 1


def test_self_improvement_runner_validator_rejects_bad_value() -> None:
    with pytest.raises(ValueError):
        Settings(self_improvement_runner="nonsense")


# ── Issue dataclass sanity ──


def test_self_improvement_issue_fields() -> None:
    i = SelfImprovementIssue(
        source="core_error_patterns",
        severity="high",
        component="mod",
        evidence="boom",
        suggested_goal="fix",
    )
    assert i.severity == "high"
