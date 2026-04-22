"""Provider-adapter package for external-CLI agents.

Auto-discovery: any *.py file in this directory (other than __init__ / _common)
that exports a module-level PROVIDER: ProviderAdapter and a
CLI_PROVIDER_ID: CliProviderId is registered in PROVIDERS at import time.

Adding a new CLI means dropping a new file — no edit to this module.
"""
from __future__ import annotations

import asyncio
import importlib
import logging
import pkgutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from openakita.agents.cli_detector import CliProviderId
    from openakita.agents.cli_runner import CliRunRequest, ProviderRunResult

logger = logging.getLogger(__name__)


@runtime_checkable
class ProviderAdapter(Protocol):
    """Stateless-across-calls adapter for one CLI provider.

    Adapters DO NOT cache last_session_id, session, or any per-turn state —
    ExternalCliAgent owns those. Adapters read everything they need from
    CliRunRequest and return everything they produced in ProviderRunResult.
    """

    def build_argv(self, request: CliRunRequest) -> list[str]: ...
    def build_env(self, request: CliRunRequest) -> dict[str, str]: ...

    async def run(
        self,
        request: CliRunRequest,
        argv: list[str],
        env: dict[str, str],
        *,
        on_spawn: Callable[[asyncio.subprocess.Process], None],
    ) -> ProviderRunResult: ...

    async def cleanup(self) -> None: ...


PROVIDERS: dict[CliProviderId, ProviderAdapter] = {}


def _autoload() -> None:
    pkg_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_path)]):
        name = info.name
        if name.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"{__name__}.{name}")
        except Exception as exc:
            logger.warning("cli_providers: failed to import %s: %s", name, exc)
            continue
        provider = getattr(mod, "PROVIDER", None)
        pid = getattr(mod, "CLI_PROVIDER_ID", None)
        if provider is None or pid is None:
            continue
        if not isinstance(provider, ProviderAdapter):
            logger.warning("cli_providers: %s PROVIDER does not satisfy protocol", name)
            continue
        PROVIDERS[pid] = provider


_autoload()
