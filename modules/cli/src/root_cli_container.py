"""Root: CLI feature DI container.

Wires capabilities → agent → surface for the CLI feature.
"""

from __future__ import annotations

from pathlib import Path

from modules.core.src.agent_cli_orchestrator import CliOrchestrator
from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_linux_guard import LinuxGuard
from modules.core.src.capabilities_observability import ObservabilitySetup
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.core.src.capabilities_saver import Saver
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter


class CliContainer:
    """Dependency injection container for the CLI feature."""

    def __init__(
        self,
        log_path: Path | str | None = None,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_window: int = 30,
        rate_limit_per_minute: int = 60,
    ) -> None:
        """Wire capabilities with injected dependencies."""
        self.log_path: Path | None = Path(log_path) if log_path else None
        self.cb = CircuitBreaker(circuit_breaker_threshold, circuit_breaker_window)
        self.rl = RateLimiter(rate_limit_per_minute)

        self.browser = BrowserAdapter()
        self.injector = PromptInjector()
        self.sender = SendDispatcher()
        self.streamer = StreamMonitor()
        self.uploader = FileUploader()
        self.saver = Saver()
        self.audit = AuditRepository(self.log_path) if self.log_path else AuditRepository()
        self.observability = ObservabilitySetup(self.log_path) if self.log_path else ObservabilitySetup(DEFAULT_LOG)

        self.core = CoreOrchestrator(
            browser=self.browser,
            injector=self.injector,
            sender=self.sender,
            streamer=self.streamer,
            uploader=self.uploader,
            saver=self.saver,
            audit=self.audit,
            observability=self.observability,
            circuit_breaker=self.cb,
            rate_limiter=self.rl,
        )
        self.cli = CliOrchestrator(self.browser)
        self.linux = LinuxGuard()

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None
