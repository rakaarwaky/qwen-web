"""Root: MCP feature DI container.

Wires capabilities → agent → surface for the MCP feature. The MCP surface
shares the single ICoreAggregate with the CLI surface.
"""

from __future__ import annotations

from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_stream_monitor import StreamMonitor
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG
from modules.shared.src.taxonomy_core_entity import CircuitBreaker, RateLimiter
from modules.shared.src.taxonomy_core_vo import FailureThreshold, MaxPerMinute, WindowSec


class McpContainer:
    """Dependency injection container for the MCP feature."""

    def __init__(
        self,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_window: int = 30,
        rate_limit_per_minute: int = 60,
    ) -> None:
        """Wire capabilities with injected dependencies."""
        self.cb = CircuitBreaker(FailureThreshold(circuit_breaker_threshold), WindowSec(circuit_breaker_window))
        self.rl = RateLimiter(MaxPerMinute(rate_limit_per_minute))

        self.browser = BrowserAdapter()
        self.injector = PromptInjector()
        self.sender = SendDispatcher()
        self.streamer = StreamMonitor()
        self.uploader = FileUploader()
        self.saver = Saver()
        self.audit = AuditRepository(DEFAULT_LOG)
        self.observability = ObservabilitySetup(DEFAULT_LOG)

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

    def wire(self) -> None:
        """Wire the container (idempotent — attributes already composed)."""
        return None


def create_mcp_feature() -> McpContainer:
    """Factory returning a fully wired MCP container."""
    container = McpContainer()
    container.wire()
    return container
