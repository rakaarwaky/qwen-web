"""Utility layer (utility_core_agent_helper): stateless functions for agent orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Tuple

from playwright.sync_api import Page, Locator

from modules.core.src.utility_core_dom_helper import setup_lifecycle_state
from modules.core.src.utility_core_dom_query import latest_message_text
from modules.core.src.utility_core_dom_helper import click_send
from modules.shared.src.taxonomy_core_vo import RunContext, PollIntervalSec, TimeoutSec, MessageCount
from modules.shared.src.taxonomy_core_event import (
    EVENT_WEB_LOADED,
    EVENT_LOGIN_VERIFIED,
    EVENT_MODEL_VERIFIED,
    EVENT_PROMPT_INJECTED,
    EVENT_SEND_CLICKED,
    EVENT_DISPATCH_ACKNOWLEDGED,
    EVENT_THINKING_STARTED,
    EVENT_STREAMING_GENERATION,
    EVENT_GENERATION_FINISHED,
    EVENT_OUTPUT_COPIED,
)


def execute_direct_on_page(
    page: Page,
    filepath: Path | str,
    prompt: str,
    timeout_sec: int,
    active_cfg: Any,
    emitter: Any,
    state: Any,
    sender: Any,
) -> str:
    """Execute direct text prompt on page with common logic."""
    # Setup lifecycle state
    direct_prompt_events = (
        EVENT_WEB_LOADED,
        EVENT_LOGIN_VERIFIED,
        EVENT_MODEL_VERIFIED,
        EVENT_PROMPT_INJECTED,
        EVENT_SEND_CLICKED,
        EVENT_DISPATCH_ACKNOWLEDGED,
        EVENT_THINKING_STARTED,
        EVENT_STREAMING_GENERATION,
        EVENT_GENERATION_FINISHED,
        EVENT_OUTPUT_COPIED,
    )
    emitter, state = setup_lifecycle_state(emitter, direct_prompt_events)

    # Navigate to chat
    # (This is simplified - actual implementation would be more detailed)
    # In real implementation, this would navigate to the chat interface
    
    # Check auth (simplified)
    # (Actual implementation would check authentication status)
    
    # Inject text
    from modules.shared.src.taxonomy_core_vo import PromptText
    prompt_text = PromptText(prompt)
    sender.inject_text(page, prompt_text)
    emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})
    
    # Click send
    sender.click_send(page, emitter, document_parsed=True)
    
    if not state.dispatch_acknowledged:
        raise RuntimeError("Cannot wait for response: prompt dispatch is incomplete")
    
    # Wait for response
    stream_timeout_sec = min(timeout_sec, active_cfg.streaming_timeout)
    response = sender.wait_for_response(
        page,
        TimeoutSec(stream_timeout_sec),
        MessageCount(0),  # Simplified - actual implementation would track message count
        emitter,
        polling_interval_sec=PollIntervalSec(active_cfg.poll_interval),
        dispatch_acknowledged=True,
        baseline_text=None,
    )
    
    if response and len(response.strip()) > 0:
        return response.strip()
    raise Exception("Response detection timeout")


def execute_file_on_page(
    page: Page,
    filepath: Path,
    timeout_sec: int,
    active_cfg: Any,
    emitter: Any,
    state: Any,
    sender: Any,
) -> str:
    """Execute file-based prompt on page with common logic."""
    # Setup lifecycle state
    file_prompt_events = (
        EVENT_WEB_LOADED,
        EVENT_LOGIN_VERIFIED,
        EVENT_MODEL_VERIFIED,
        EVENT_PROMPT_INJECTED,
        EVENT_SEND_CLICKED,
        EVENT_DISPATCH_ACKNOWLEDGED,
        EVENT_THINKING_STARTED,
        EVENT_STREAMING_GENERATION,
        EVENT_GENERATION_FINISHED,
        EVENT_OUTPUT_COPIED,
    )
    emitter, state = setup_lifecycle_state(emitter, file_prompt_events)

    # Read prompt file
    prompt = filepath.read_text(encoding="utf-8").strip()
    
    # Navigate to chat
    # (Simplified - actual implementation would be more detailed)
    
    # Check auth
    # (Actual implementation would check authentication status)
    
    # Inject text
    from modules.shared.src.taxonomy_core_vo import PromptText
    prompt_text = PromptText(prompt)
    sender.inject_text(page, prompt_text)
    emitter.emit(EVENT_PROMPT_INJECTED, {"file": str(filepath), "char_count": len(prompt)})
    
    # Click send
    sender.click_send(page, emitter, document_parsed=True)
    
    if not state.dispatch_acknowledged:
        raise RuntimeError("Cannot wait for response: prompt dispatch is incomplete")
    
    # Wait for response
    stream_timeout_sec = min(timeout_sec, active_cfg.streaming_timeout)
    response = sender.wait_for_response(
        page,
        TimeoutSec(stream_timeout_sec),
        MessageCount(0),  # Simplified - actual implementation would track message count
        emitter,
        polling_interval_sec=PollIntervalSec(active_cfg.poll_interval),
        dispatch_acknowledged=True,
        baseline_text=None,
    )
    
    if response and len(response.strip()) > 0:
        return response.strip()
    raise Exception("Response detection timeout")