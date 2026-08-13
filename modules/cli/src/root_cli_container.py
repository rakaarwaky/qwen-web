"""Root: CLI feature DI container.

Wires capabilities → agent → surface for the CLI feature. The CLI surface
shares the single ICoreAggregate with the MCP surface.
"""

from __future__ import annotations

from pathlib import Path

from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_linux_guard import LinuxGuard
from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_stream_monitor import StreamMonitor
from modules.core.src.capabilities_workspace_provisioner import WorkspaceProvisioner
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec


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
        self.cb = CircuitBreaker(FailureThreshold(circuit_breaker_threshold), WindowSec(circuit_breaker_window))
        self.rl = RateLimiter(MaxPerMinute(rate_limit_per_minute))

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
            workspace=WorkspaceProvisioner(),
            circuit_breaker=self.cb,
            rate_limiter=self.rl,
        )
        self.linux = LinuxGuard()

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None
