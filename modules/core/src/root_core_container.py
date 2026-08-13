"""Root: single DI container for CLI and MCP features.

root_core_container.py is the only container file. Both entry points use it.
No new files are created — no root_shared_container.py, no duplicate containers.
"""

from __future__ import annotations

from pathlib import Path

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

from .agent_core_orchestrator import CoreOrchestrator


class SharedContainer:
    """Single dependency injection container shared by CLI and MCP features."""

    def __init__(
        self,
        log_path: Path | str | None = None,
        use_linux_guard: bool = True,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_window: int = 30,
        rate_limit_per_minute: int = 60,
    ) -> None:
        """Wire capabilities with injected dependencies.

        Parameters
        ----------
        log_path : optional
            Override for the application log directory. Defaults to DEFAULT_LOG.
        use_linux_guard : bool
            Include LinuxGuard (CLI-only). MCP sets False.
        circuit_breaker_threshold : int
            Number of consecutive failures before the circuit opens.
        circuit_breaker_window : int
            Time window in seconds for counting consecutive failures.
        rate_limit_per_minute : int
            Maximum number of requests per minute.
        """
        log = Path(log_path) if log_path else DEFAULT_LOG

        self.cb = CircuitBreaker(
            FailureThreshold(circuit_breaker_threshold),
            WindowSec(circuit_breaker_window),
        )
        self.rl = RateLimiter(MaxPerMinute(rate_limit_per_minute))

        self.browser = BrowserAdapter()
        self.injector = PromptInjector()
        self.sender = SendDispatcher()
        self.streamer = StreamMonitor()
        self.uploader = FileUploader()
        self.saver = Saver()
        self.audit = AuditRepository(log)
        self.observability = ObservabilitySetup(log)

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

        # LinuxGuard is CLI-only
        linux: LinuxGuard | None = LinuxGuard() if use_linux_guard else None
        self.linux = linux

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None
