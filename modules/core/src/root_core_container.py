"""Composition root: wires Capabilities to Contract protocols and bootstraps the application.

Root layer (root_core_container): instantiates concrete Capabilities, connects them
to Contract protocols, returns ICoreAggregate. Contains no business logic or
orchestration policy. Surfaces should use build_core_container() instead of
instantiating Capabilities directly.
"""

from __future__ import annotations

from pathlib import Path

from modules.shared.src.contract_core_aggregate import ICoreAggregate
from modules.shared.src.taxonomy_config_vo import DEFAULT_UPLOAD_CONFIG
from modules.shared.src.taxonomy_core_constant import DEFAULT_LOG

from modules.core.src.agent_core_orchestrator import CoreOrchestrator
from modules.core.src.capabilities_audit_repository import AuditRepository
from modules.core.src.capabilities_browser_adapter import BrowserAdapter
from modules.core.src.capabilities_file_uploader import FileUploader
from modules.core.src.capabilities_linux_guard import LinuxGuard
from modules.core.src.capabilities_metrics_collector import MetricsCollector
from modules.core.src.capabilities_observability_setup import ObservabilitySetup
from modules.core.src.capabilities_output_saver import Saver
from modules.core.src.capabilities_prompt_injector import PromptInjector
from modules.core.src.capabilities_send_dispatcher import SendDispatcher
from modules.core.src.capabilities_status_writer import StatusFileWriter
from modules.core.src.capabilities_stream_monitor import StreamMonitor
from modules.core.src.capabilities_workspace_provisioner import WorkspaceProvisioner


def build_core_container() -> ICoreAggregate:
    """Build and return the CoreOrchestrator wired with all Capabilities.

    Returns
    -------
    ICoreAggregate
        The orchestrator ready for use by CLI or MCP surfaces.

    """
    workspace = WorkspaceProvisioner()
    linux_guard = LinuxGuard()
    metrics = MetricsCollector()

    status_writer = StatusFileWriter(DEFAULT_LOG / "status.json")
    observability = ObservabilitySetup(log_path=DEFAULT_LOG, status_writer=status_writer)
    audit = AuditRepository(DEFAULT_LOG)

    browser = BrowserAdapter()
    injector = PromptInjector()
    sender = SendDispatcher()
    streamer = StreamMonitor()
    uploader = FileUploader(config=DEFAULT_UPLOAD_CONFIG)
    saver = Saver()

    return CoreOrchestrator(
        browser=browser,
        injector=injector,
        sender=sender,
        streamer=streamer,
        uploader=uploader,
        saver=saver,
        audit=audit,
        observability=observability,
        workspace=workspace,
    )
