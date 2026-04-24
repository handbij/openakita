"""Health monitoring configuration.

Centralizes all timeout thresholds and escalation settings for the
failure recovery infrastructure. Data-first: define types before behavior.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthConfig:
    """Configuration for health monitoring loops."""

    stale_task_age: int = 3600
    stale_delegation_age: int = 1800
    check_interval: int = 300
    max_sub_agent_states: int = 1000


@dataclass(frozen=True)
class EscalationThresholds:
    """Idle loop escalation thresholds.

    Defines iteration counts that trigger escalating interventions.
    """

    soft_nudge: int = 3
    force_tool: int = 5
    model_switch: int = 7
    terminate: int = 10

    def level_for_count(self, count: int) -> str | None:
        """Return escalation level name for iteration count, or None if below threshold."""
        if count >= self.terminate:
            return "terminate"
        if count >= self.model_switch:
            return "model_switch"
        if count >= self.force_tool:
            return "force_tool"
        if count >= self.soft_nudge:
            return "soft_nudge"
        return None
