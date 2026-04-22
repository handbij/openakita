from __future__ import annotations

import asyncio

import pytest

from openakita.agents.cli_providers import PROVIDERS, ProviderAdapter
from openakita.agents.cli_providers._common import stream_cli_subprocess


def test_providers_registry_is_dict():
    assert isinstance(PROVIDERS, dict)


def test_provider_adapter_protocol_is_runtime_checkable():
    class _MinAdapter:
        def build_argv(self, request): return []
        def build_env(self, request): return {}
        async def run(self, request, argv, env, *, on_spawn): return None
        async def cleanup(self): pass

    assert isinstance(_MinAdapter(), ProviderAdapter)


def test_protocol_rejects_missing_methods():
    class _BadAdapter:
        def build_argv(self, request): return []

    assert not isinstance(_BadAdapter(), ProviderAdapter)


@pytest.mark.asyncio
async def test_stream_cli_subprocess_yields_lines_from_echo(tmp_path):
    cancelled = asyncio.Event()
    tracked = {"proc": None}

    def track(proc):
        tracked["proc"] = proc

    lines = []
    async for line in stream_cli_subprocess(
        ["sh", "-c", "printf 'one\\ntwo\\nthree\\n'"],
        env={},
        cwd=tmp_path,
        cancelled=cancelled,
        on_spawn=track,
    ):
        lines.append(line.rstrip(b"\n"))

    assert lines == [b"one", b"two", b"three"]
    assert tracked["proc"] is not None


@pytest.mark.asyncio
async def test_stream_cli_subprocess_honors_cancellation(tmp_path):
    cancelled = asyncio.Event()
    lines = []

    async def consume():
        async for line in stream_cli_subprocess(
            ["sh", "-c", "for i in $(seq 1 100); do echo $i; sleep 0.05; done"],
            env={}, cwd=tmp_path, cancelled=cancelled, on_spawn=lambda _: None,
        ):
            lines.append(line)
            if len(lines) == 2:
                cancelled.set()

    await consume()
    assert len(lines) < 50
