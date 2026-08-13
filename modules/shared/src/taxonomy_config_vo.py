"""Application and subsystem configuration Value Objects.

Taxonomy layer (taxonomy(vo)): frozen dataclasses, no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from modules.shared.src.taxonomy_core_constant import (
    DEFAULT_LOG,
)


@dataclass(frozen=True)
class UploadConfig:
    """Configuration options for file upload behavior."""

    max_file_size_mb: float = 100.0
    dropdown_timeout_ms: int = 5000
    option_timeout_ms: int = 3000
    file_chooser_timeout_ms: int = 8000
    card_render_timeout_ms: int = 5000
    max_retries: int = 2
    backoff_delay_sec: float = 1.0

    dropdown_selectors: Sequence[str] = field(
        default_factory=lambda: (
            ".mode-select-open",
            "[class*='mode-select']",
            "button:has-text('Upload')",
        )
    )

    upload_option_selectors: Sequence[str] = field(
        default_factory=lambda: (
            ".mode-select-dropdown-item",
            "text='Upload attachment'",
            "text='Upload file'",
        )
    )

    card_selectors: Sequence[str] = field(
        default_factory=lambda: (
            ".file-card-list",
            ".fileitem-btn",
            ".message-input-column-file",
            "[class*='file-card']",
            "[class*='file-item']",
            "[class*='fileitem']",
        )
    )


DEFAULT_UPLOAD_CONFIG = UploadConfig()


@dataclass(frozen=True)
class InjectorConfig:
    """Configuration options for prompt text injection."""

    wait_timeout_ms: int = 10_000
    typing_delay_ms: int = 10
    verify_injection: bool = True
    input_selectors: Sequence[str] = field(
        default_factory=lambda: (
            "textarea.message-input-textarea",
            "textarea",
            "div[contenteditable='true']",
            "#chat-input",
            ".chat-input",
        )
    )


DEFAULT_INJECTOR_CONFIG = InjectorConfig()


@dataclass(frozen=True)
class ObservabilityConfig:
    """Configuration options for observability logging and tracing."""

    log_path: Path
    enable_sentry: bool = True
    enable_otel: bool = True
    environment: str = "production"


@dataclass(frozen=True)
class MCPToolResponse:
    """Structured response payload for MCP tool invocations."""

    success: bool
    data: str
    error: str | None = None


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration options for MCP server entrypoint."""

    server_name: str = "Qwen-Web"
    transport: str = "stdio"


@dataclass(frozen=True)
class QwenClientConfig:
    """Client operational configuration options."""

    timeout_sec: int = 120
    auto_attach_files: bool = True
    retry_upload_on_failure: bool = True


@dataclass(frozen=True)
class BrowserConfig:
    """Browser launch and session configuration options."""

    headless: bool = True
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    viewport_width: int = 1280
    viewport_height: int = 800
    block_media_assets: bool = True
    launch_timeout_sec: int = 30


@dataclass(frozen=True)
class SenderConfig:
    """Configuration options for send button interactions."""

    click_timeout_ms: int = 3000
    try_enter_key_fallback: bool = True


DEFAULT_SENDER_CONFIG = SenderConfig()


@dataclass(frozen=True)
class StreamerConfig:
    """Configuration options for AI response streaming and stability detection."""

    polling_interval_sec: float = 1.0
    stability_checks: int = 4
    min_text_length: int = 1


@dataclass(frozen=True)
class OutputMetadata:
    """Metadata payload recorded with processed output files."""

    run_id: str
    source_file: str
    processed_at: str
    duration_sec: float
    input_chars: int
    output_chars: int


@dataclass(frozen=True)
class SaverConfig:
    """Configuration options for saver module."""

    include_header: bool = True
    generate_sidecar: bool = True
    atomic_write: bool = True


DEFAULT_SAVER_CONFIG = SaverConfig()


@dataclass(frozen=True)
class AppConfig:
    """Application configuration with defaults and validation."""

    mode: str
    input_path: Path
    output_path: Path
    done_path: Path
    failed_path: Path
    proc_path: Path
    session_path: Path
    log_path: Path = DEFAULT_LOG

    interval: int = 3
    timeout: int = 300
    headless: bool = False
    prompt_file: Path | None = None

    chrome_profile: str = "qwen-cli-profile"
    storage_state_file: Path | None = None
    disable_sandbox: bool = True

    request_timeout: int = 120
    poll_interval: float = 1.0
    streaming_timeout: int = 180

    rate_limit_per_minute: int = 60
    circuit_breaker_threshold: int = 5
    circuit_breaker_window: int = 30

    retry_failed: bool = False

    @property
    def status_path(self) -> Path:
        """Path to the JSON status file for monitoring."""
        return self.log_path / "status.json"

    def validate(self) -> None:
        """Validate configuration before execution.

        Raises
        ------
        ValueError
            If any configuration value is invalid.

        """
        if self.timeout < 30:
            raise ValueError(f"timeout must be >= 30s, got {self.timeout}")
        if self.poll_interval < 0.5:
            raise ValueError(f"poll_interval must be >= 0.5s, got {self.poll_interval}")
        if self.request_timeout < 10:
            raise ValueError(f"request_timeout must be >= 10s, got {self.request_timeout}")
        if self.rate_limit_per_minute < 1:
            raise ValueError(f"rate_limit_per_minute must be >= 1, got {self.rate_limit_per_minute}")
        if self.circuit_breaker_threshold < 2:
            raise ValueError(f"circuit_breaker_threshold must be >= 2, got {self.circuit_breaker_threshold}")

    def __post_init__(self) -> None:
        """Validate config on construction."""
        self.validate()
