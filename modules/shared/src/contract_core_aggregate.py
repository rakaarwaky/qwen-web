"""Core aggregate contracts — business-logic APIs for all surfaces.

Taxonomy layer (contract(aggregate)): implemented by agent orchestrators and
consumed by CLI and MCP surfaces.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

from modules.shared.src.taxonomy_core_vo import (
    AttachmentPath,
    HeadlessFlag,
    OutputPath,
    PromptPath,
    PromptText,
    ResponseText,
    TimeoutSec,
)


class IDirectPromptAggregate(ABC):
    """Direct string prompt processing aggregate contract."""

    @abstractmethod
    def process_direct_prompt(
        self,
        prompt: PromptText | str,
        timeout_sec: TimeoutSec = TimeoutSec(120),
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
    ) -> ResponseText:
        """Process a direct text prompt string."""


class IPromptFileAggregate(ABC):
    """Prompt file processing aggregate contract."""

    @abstractmethod
    def process_prompt_file_only(
        self,
        prompt_file: Path | PromptPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
    ) -> ResponseText:
        """Process a prompt file from disk without attachment."""


class IAttachmentPromptAggregate(ABC):
    """Attachment prompt processing aggregate contract."""

    @abstractmethod
    def process_prompt_with_attachment(
        self,
        prompt_file: Path | PromptPath | str,
        attachment_file: Path | AttachmentPath | str,
        output_file: Path | OutputPath | str | None = None,
        headless: HeadlessFlag = HeadlessFlag(True),
    ) -> ResponseText:
        """Process a prompt file from disk with document attachment."""


class ISessionAggregate(ABC):
    """Session aggregate contract for session validation and deletion."""

    @abstractmethod
    def validate_session(self, session_path: Path | None = None) -> tuple[bool, str]:
        """Return session validity and a human-readable status message."""

    @abstractmethod
    def delete_session(self, session_path: Path | None = None) -> ResponseText:
        """Delete the persistent login session at ``session_path``."""


class ISetupAggregate(ABC):
    """Setup aggregate contract for interactive manual login."""

    @abstractmethod
    def setup_session(
        self,
        wait_for_confirmation: Callable[[], None] | None = None,
        session_path: Path | None = None,
    ) -> ResponseText:
        """Validate or establish a persistent manual login session."""


__all__ = [
    "IAttachmentPromptAggregate",
    "IDirectPromptAggregate",
    "IPromptFileAggregate",
    "ISessionAggregate",
    "ISetupAggregate",
]
