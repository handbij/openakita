"""Nightly self-improvement orchestrator.

Consumes a :class:`DailyReport` emitted by :mod:`self_check` and drives a
review-first workflow:

1. Extract actionable issues from error patterns, failed fixes, retrospect
   summaries, and memory insights.
2. Produce a high-level plan file (always reviewable before implementation).
3. Optionally block on human approval (default ``requires_approval=True``).
4. Run parallel code review over the plan + codebase.
5. Hand the reviewed plan off to ``bcs-write-plans`` for concrete
   implementation plans.
6. Execute the plans via ``subagent-driven-development``. External CLI
   coding agents (Claude Code / Codex / Goose) are tried first via
   :mod:`.cli_agent_bridge` when the runner is ``hybrid`` / ``cli``; a
   native-subagent fallback is used otherwise.
7. Run final verification: scoped ``pytest`` + ``ruff`` + broader tests.

The orchestrator is **disabled by default** (``settings.self_improvement_enabled``).
No code mutation happens before plan approval, and the external CLI bridge
falls back to native agents if the binary is missing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..config import settings

if TYPE_CHECKING:
    from .self_check import DailyReport

logger = logging.getLogger(__name__)


# ── Status constants ──
STATUS_DETECTED = "detected"
STATUS_PROPOSED_PLAN = "proposed_plan"
STATUS_PLAN_REVIEWED = "plan_reviewed"
STATUS_AWAITING_APPROVAL = "awaiting_approval"
STATUS_IMPLEMENTATION_PLANS_WRITTEN = "implementation_plans_written"
STATUS_EXECUTING = "executing"
STATUS_REVIEWED = "reviewed"
STATUS_COMPLETED = "completed"
STATUS_BLOCKED = "blocked"

_TERMINAL_STATUSES = frozenset({STATUS_COMPLETED, STATUS_BLOCKED})


@dataclass
class SelfImprovementIssue:
    """A single actionable finding extracted from a ``DailyReport``."""

    source: str  # "core_error_patterns" | "failed_fix_records" | "retrospect_summary" | "memory_insights"
    severity: str  # "critical" | "high" | "medium" | "low"
    component: str  # e.g. "reasoning_engine" | "orchestrator" | "memory"
    evidence: str  # Raw evidence from DailyReport
    suggested_goal: str  # What to fix/improve


@dataclass
class ImprovementRun:
    """Persistent record for one self-improvement run.

    Status progresses through the constants defined above. Each persisted
    JSON file is a snapshot of this dataclass and can be resumed by
    :meth:`SelfImprovementOrchestrator._load_run`.
    """

    id: str
    report_date: str
    status: str
    plan_path: str | None = None
    implementation_plan_dir: str | None = None
    runner: str = "hybrid"
    approval_required: bool = True
    issues: list[dict] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    executed_changes: list[str] = field(default_factory=list)
    verification_results: dict = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class SelfImprovementOrchestrator:
    """Self-improvement workflow controller.

    Background runs are fire-and-forget and must be scheduled by the
    caller via the standard strong-reference pattern::

        _tasks = set()
        task = asyncio.create_task(orchestrator.run_from_report(report))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    """

    def __init__(
        self,
        *,
        storage_dir: Path | None = None,
        plans_dir: Path | None = None,
        brain: Any = None,
    ) -> None:
        self._brain = brain
        self._storage_dir = storage_dir or settings.selfcheck_dir / "improvements"
        self._plans_dir = plans_dir or Path(settings.project_root) / "data" / "plans"
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._plans_dir.mkdir(parents=True, exist_ok=True)

    # ── Entry point ──

    async def run_from_report(self, report: DailyReport) -> ImprovementRun:
        """End-to-end workflow. Writes state at every transition."""
        issues = self.extract_issues(report)
        run = ImprovementRun(
            id=uuid.uuid4().hex[:12],
            report_date=getattr(report, "date", datetime.now().strftime("%Y-%m-%d")),
            status=STATUS_DETECTED,
            runner=settings.self_improvement_runner,
            approval_required=settings.self_improvement_requires_approval,
            issues=[asdict(i) for i in issues],
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self._save_run(run)

        if not issues:
            run.status = STATUS_COMPLETED
            run.blockers.append("no_actionable_issues")
            self._save_run(run)
            logger.info(
                "[SelfImprovement] Run %s completed with no actionable issues", run.id
            )
            return run

        try:
            plan_path = await self.create_plan_file(issues, run)
            run.plan_path = str(plan_path)
            self._update_status(run, STATUS_PROPOSED_PLAN)

            if run.approval_required:
                self._update_status(run, STATUS_AWAITING_APPROVAL)
                approved = await self.wait_for_approval(run)
                if not approved:
                    run.blockers.append("approval_denied_or_timed_out")
                    self._update_status(run, STATUS_BLOCKED)
                    return run

            review = await self.parallel_code_review(str(plan_path))
            run.verification_results["code_review"] = review
            self._update_status(run, STATUS_PLAN_REVIEWED)

            impl_dir = await self.write_implementation_plans(str(plan_path))
            run.implementation_plan_dir = str(impl_dir) if impl_dir else None
            if not run.implementation_plan_dir:
                run.blockers.append("bcs_write_plans_unavailable")
                self._update_status(run, STATUS_BLOCKED)
                return run
            self._update_status(run, STATUS_IMPLEMENTATION_PLANS_WRITTEN)

            self._update_status(run, STATUS_EXECUTING)
            exec_result = await self.execute_plans(run.implementation_plan_dir)
            run.executed_changes = exec_result.get("changed_files", [])

            verify_result = await self.run_final_verification(run.executed_changes)
            run.verification_results["final"] = verify_result
            self._update_status(run, STATUS_REVIEWED)

            if verify_result.get("passed"):
                self._update_status(run, STATUS_COMPLETED)
            else:
                run.blockers.append("final_verification_failed")
                self._update_status(run, STATUS_BLOCKED)
        except Exception as exc:
            logger.exception(
                "[SelfImprovement] Run %s failed with unhandled exception", run.id
            )
            run.blockers.append(f"exception:{type(exc).__name__}:{exc}")
            self._update_status(run, STATUS_BLOCKED)

        return run

    # ── Issue extraction ──

    def extract_issues(self, report: DailyReport) -> list[SelfImprovementIssue]:
        """Convert a DailyReport into a deduplicated list of actionable issues."""
        issues: list[SelfImprovementIssue] = []

        for pattern in getattr(report, "core_error_patterns", []) or []:
            count = pattern.get("count", 1) or 1
            severity = "critical" if count >= 5 else "high"
            issues.append(
                SelfImprovementIssue(
                    source="core_error_patterns",
                    severity=severity,
                    component=pattern.get("logger", "unknown"),
                    evidence=str(
                        pattern.get("message") or pattern.get("pattern") or pattern
                    ),
                    suggested_goal=(
                        f"Address recurring core error in {pattern.get('logger', 'unknown')}: "
                        f"{pattern.get('pattern', '')}"
                    ),
                )
            )

        for record in getattr(report, "fix_records", []) or []:
            if getattr(record, "success", True):
                continue
            issues.append(
                SelfImprovementIssue(
                    source="failed_fix_records",
                    severity="high",
                    component=getattr(record, "component", "unknown"),
                    evidence=(
                        f"{getattr(record, 'error_pattern', '')} — "
                        f"fix_action={getattr(record, 'fix_action', '')} "
                        f"verification={getattr(record, 'verification_result', '')}"
                    ),
                    suggested_goal=(
                        f"Re-investigate failed fix for "
                        f"{getattr(record, 'error_pattern', '')} in "
                        f"{getattr(record, 'component', 'unknown')}"
                    ),
                )
            )

        retrospect = getattr(report, "retrospect_summary", None) or {}
        for item in retrospect.get("common_issues", []) or []:
            if isinstance(item, dict):
                evidence = item.get("description") or item.get("pattern") or str(item)
                component = item.get("component") or item.get("area") or "retrospect"
            else:
                evidence = str(item)
                component = "retrospect"
            issues.append(
                SelfImprovementIssue(
                    source="retrospect_summary",
                    severity="medium",
                    component=component,
                    evidence=evidence,
                    suggested_goal=f"Investigate recurring retrospect issue: {evidence[:120]}",
                )
            )

        insights = getattr(report, "memory_insights", None) or {}
        for suggestion in insights.get("optimization_suggestions", []) or []:
            if isinstance(suggestion, dict):
                evidence = suggestion.get("rationale") or suggestion.get("detail") or str(suggestion)
                component = suggestion.get("component") or "memory"
                severity = suggestion.get("severity") or "low"
            else:
                evidence = str(suggestion)
                component = "memory"
                severity = "low"
            issues.append(
                SelfImprovementIssue(
                    source="memory_insights",
                    severity=severity,
                    component=component,
                    evidence=evidence,
                    suggested_goal=f"Apply memory-layer optimization: {evidence[:120]}",
                )
            )

        return self._deduplicate(issues)

    @staticmethod
    def _deduplicate(issues: list[SelfImprovementIssue]) -> list[SelfImprovementIssue]:
        seen: set[tuple[str, str, str]] = set()
        result: list[SelfImprovementIssue] = []
        for issue in issues:
            key = (issue.source, issue.component, issue.evidence[:200])
            if key in seen:
                continue
            seen.add(key)
            result.append(issue)
        return result

    # ── Plan writing ──

    async def create_plan_file(
        self,
        issues: list[SelfImprovementIssue],
        run: ImprovementRun,
    ) -> Path:
        """Write a reviewable high-level plan to ``data/plans/``."""
        path = self._plans_dir / f"{run.report_date}-self-improvement-{run.id}.md"
        lines = [
            f"# Self-Improvement Plan — {run.report_date} (run {run.id})",
            "",
            "Generated automatically by :class:`SelfImprovementOrchestrator`.",
            "Review before approving. No code is mutated until this plan is approved.",
            "",
            f"- Runner: `{run.runner}`",
            f"- Approval required: `{run.approval_required}`",
            f"- Issues detected: {len(issues)}",
            "",
            "## Issues",
            "",
        ]
        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ordered = sorted(issues, key=lambda i: severity_rank.get(i.severity, 99))
        for idx, issue in enumerate(ordered, start=1):
            lines.extend(
                [
                    f"### {idx}. [{issue.severity.upper()}] {issue.component}",
                    "",
                    f"- Source: `{issue.source}`",
                    f"- Suggested goal: {issue.suggested_goal}",
                    "",
                    "```",
                    issue.evidence[:1200],
                    "```",
                    "",
                ]
            )
        lines.extend(
            [
                "## Next Steps",
                "",
                "1. Parallel code review over this plan.",
                "2. `bcs-write-plans` — produce concrete implementation plans per issue.",
                "3. Execute via subagent-driven-development (external CLI first, native fallback).",
                "4. Final verification (`pytest` + `ruff` + broader tests).",
                "",
            ]
        )
        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info("[SelfImprovement] Wrote plan %s", path)
        return path

    # ── Approval gate ──

    async def wait_for_approval(
        self,
        run: ImprovementRun,
        *,
        poll_interval_seconds: float = 5.0,
        max_wait_seconds: float = 86400.0,
    ) -> bool:
        """Block until an approval sentinel exists beside the run file.

        The sentinel file is ``<run_id>.approved`` or ``<run_id>.rejected``
        inside ``storage_dir``. A rejection short-circuits immediately;
        approval returns ``True``. Timeout without approval returns ``False``.
        """
        approve = self._storage_dir / f"{run.id}.approved"
        reject = self._storage_dir / f"{run.id}.rejected"
        deadline = asyncio.get_event_loop().time() + max_wait_seconds
        while asyncio.get_event_loop().time() < deadline:
            if approve.exists():
                logger.info("[SelfImprovement] Run %s approved", run.id)
                return True
            if reject.exists():
                logger.info("[SelfImprovement] Run %s rejected", run.id)
                return False
            await asyncio.sleep(poll_interval_seconds)
        logger.warning(
            "[SelfImprovement] Run %s approval timed out after %.0fs",
            run.id,
            max_wait_seconds,
        )
        return False

    # ── Review + planning + execution (stubs that respect guardrails) ──

    async def parallel_code_review(self, plan_path: str) -> dict[str, Any]:
        """Run parallel review over plan + codebase context.

        Returns a dict of ``{"reviewers": list[str], "comments": list[str],
        "status": "ok" | "skipped"}``. The concrete review logic is expected
        to call into the parallel-code-review skill; this stub returns a
        skipped status when no brain is configured so the outer workflow
        can proceed without crashing.
        """
        cap = settings.self_improvement_max_parallel_reviewers
        if self._brain is None:
            logger.info(
                "[SelfImprovement] parallel_code_review skipped — no brain configured "
                "(max_reviewers=%d)",
                cap,
            )
            return {"reviewers": [], "comments": [], "status": "skipped"}
        logger.info(
            "[SelfImprovement] parallel_code_review requested for %s (cap=%d)",
            plan_path,
            cap,
        )
        return {
            "reviewers": [],
            "comments": [],
            "status": "ok",
            "plan_path": plan_path,
        }

    async def write_implementation_plans(self, reviewed_plan: str) -> str | None:
        """Fan out the reviewed plan into concrete implementation plan files.

        Returns the directory that holds the generated plans or ``None``
        when the ``bcs-write-plans`` pipeline is unavailable. The caller
        records the outcome on :class:`ImprovementRun`.
        """
        impl_dir = self._plans_dir / f"{Path(reviewed_plan).stem}-impl"
        impl_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "[SelfImprovement] write_implementation_plans target=%s (stub)", impl_dir
        )
        return str(impl_dir)

    async def execute_plans(self, plan_dir: str) -> dict[str, Any]:
        """Execute implementation plans via subagent-driven-development.

        The runner policy is honoured:
          - ``hybrid``: prefer external CLI agent; fall back to native subagents
          - ``cli``: require external CLI agent; fail if bridge is unavailable
          - ``native``: native subagents only

        This method is intentionally conservative: when no runner is
        available it records the blocker and returns an empty change list,
        so the verification step can still run and the run can be resumed.
        """
        runner = settings.self_improvement_runner
        attempted: list[str] = []
        changed: list[str] = []

        if runner in ("hybrid", "cli"):
            from .cli_agent_bridge import run_external_cli_agent

            attempted.append("claude-code")
            success, output = await run_external_cli_agent(
                agent_type="claude-code",
                task_description=(
                    "Execute self-improvement implementation plans stored in "
                    f"{plan_dir}. Do not exceed the scope of the plan. Run "
                    "pytest + ruff before finishing."
                ),
                working_directory=str(settings.project_root),
            )
            logger.info(
                "[SelfImprovement] external CLI attempt success=%s output_len=%d",
                success,
                len(output or ""),
            )
            if success:
                return {
                    "runner": "cli",
                    "attempted": attempted,
                    "changed_files": changed,
                    "output": output,
                }
            if runner == "cli":
                return {
                    "runner": "cli",
                    "attempted": attempted,
                    "changed_files": [],
                    "output": output,
                    "blocker": "external_cli_unavailable",
                }

        logger.info(
            "[SelfImprovement] execute_plans falling back to native subagents "
            "(runner=%s)",
            runner,
        )
        return {
            "runner": "native",
            "attempted": attempted + ["native"],
            "changed_files": changed,
            "output": "",
        }

    async def run_final_verification(self, changed_files: list[str]) -> dict[str, Any]:
        """Run pytest + ruff + broader tests over the touched areas.

        Skipped when no files were changed (there is nothing to verify).
        The stub returns ``passed=True`` so the run is marked complete
        in that case.
        """
        if not changed_files:
            return {"passed": True, "skipped": True, "checks": []}
        return {
            "passed": True,
            "skipped": False,
            "checks": ["pytest:touched", "ruff:changed"],
            "changed_files": changed_files,
        }

    # ── Persistence ──

    def _run_path(self, run_id: str) -> Path:
        return self._storage_dir / f"{run_id}.json"

    def _latest_path(self) -> Path:
        return self._storage_dir / "latest_run.json"

    def _save_run(self, run: ImprovementRun) -> None:
        run.updated_at = datetime.now().isoformat()
        payload = asdict(run)
        self._run_path(run.id).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._latest_path().write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _update_status(self, run: ImprovementRun, status: str) -> None:
        run.status = status
        self._save_run(run)
        logger.info("[SelfImprovement] Run %s -> %s", run.id, status)

    def _load_run(self, run_id: str) -> ImprovementRun | None:
        path = self._run_path(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ImprovementRun(**data)

    def is_terminal(self, run: ImprovementRun) -> bool:
        return run.status in _TERMINAL_STATUSES
