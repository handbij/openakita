# tests/core/test_health_config.py
import pytest
from openakita.core.health_config import HealthConfig, EscalationThresholds


def test_health_config_defaults():
    config = HealthConfig()
    assert config.stale_task_age == 3600
    assert config.stale_delegation_age == 1800
    assert config.check_interval == 300
    assert config.max_sub_agent_states == 1000


def test_health_config_custom_values():
    config = HealthConfig(stale_task_age=1800, check_interval=60)
    assert config.stale_task_age == 1800
    assert config.check_interval == 60


def test_escalation_thresholds_defaults():
    thresholds = EscalationThresholds()
    assert thresholds.soft_nudge == 3
    assert thresholds.force_tool == 5
    assert thresholds.model_switch == 7
    assert thresholds.terminate == 10


def test_escalation_level_for_count():
    thresholds = EscalationThresholds()
    assert thresholds.level_for_count(2) is None
    assert thresholds.level_for_count(3) == "soft_nudge"
    assert thresholds.level_for_count(5) == "force_tool"
    assert thresholds.level_for_count(7) == "model_switch"
    assert thresholds.level_for_count(10) == "terminate"
    assert thresholds.level_for_count(15) == "terminate"
