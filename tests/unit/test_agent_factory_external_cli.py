"""Tests for AgentFactory EXTERNAL_CLI branch + Pool special-case."""
from __future__ import annotations

import pytest

from openakita.config import Settings


def test_settings_external_cli_max_concurrent_default():
    s = Settings()
    assert s.external_cli_max_concurrent == 3
