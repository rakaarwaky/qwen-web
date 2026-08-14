"""Regression tests for the shared taxonomy event/error refactor."""

from dataclasses import FrozenInstanceError

import pytest

from modules.shared.src import (
    EVENT_FILE_UPLOADED,
    EVENT_ORDER,
    EVENT_PROMPT_INJECTED,
    EVENT_WEB_LOADED,
    PIPELINE_EVENT_SEQUENCE,
)
from modules.shared.src.taxonomy_core_entity import LifecycleEmitter, LifecycleState
from modules.shared.src.taxonomy_core_error import ErrorCategory, QwenCliError
from modules.shared.src.taxonomy_core_event import (
    EVENT_DOCUMENT_PARSED,
    EVENT_GENERATION_FINISHED,
    EVENT_OUTPUT_COPIED,
    EVENT_SEND_CLICKED,
    EVENT_STREAMING_GENERATION,
    EVENT_THINKING_STARTED,
    LifecycleEvent,
    QwenEventType,
)
from modules.shared.src.taxonomy_core_vo import (
    EVENT_WEB_LOADED as LEGACY_EVENT_WEB_LOADED,
)
from modules.shared.src.taxonomy_core_vo import (
    EventDetails,
    EventOrderMap,
)
from modules.shared.src.taxonomy_domain_error import QwenCliError as LEGACY_QWEN_CLI_ERROR


def test_pipeline_event_sequence_is_canonical_and_ordered() -> None:
    assert PIPELINE_EVENT_SEQUENCE == (
        QwenEventType.WEB_LOADED,
        QwenEventType.FILE_UPLOADED,
        QwenEventType.PROMPT_INJECTED,
        QwenEventType.DOCUMENT_PARSED,
        QwenEventType.SEND_CLICKED,
        QwenEventType.THINKING_STARTED,
        QwenEventType.STREAMING_GENERATION,
        QwenEventType.GENERATION_FINISHED,
        QwenEventType.OUTPUT_COPIED,
    )
    assert EVENT_ORDER[QwenEventType.WEB_LOADED] < EVENT_ORDER[QwenEventType.FILE_UPLOADED]
    assert EVENT_ORDER[QwenEventType.FILE_UPLOADED] < EVENT_ORDER[QwenEventType.PROMPT_INJECTED]
    assert EVENT_ORDER[QwenEventType.PROMPT_INJECTED] < EVENT_ORDER[QwenEventType.DOCUMENT_PARSED]
    assert EVENT_ORDER[QwenEventType.DOCUMENT_PARSED] < EVENT_ORDER[QwenEventType.SEND_CLICKED]
    assert EVENT_ORDER[QwenEventType.SEND_CLICKED] < EVENT_ORDER[QwenEventType.THINKING_STARTED]
    assert EVENT_ORDER[QwenEventType.THINKING_STARTED] < EVENT_ORDER[QwenEventType.STREAMING_GENERATION]
    assert EVENT_ORDER[QwenEventType.STREAMING_GENERATION] < EVENT_ORDER[QwenEventType.GENERATION_FINISHED]
    assert EVENT_ORDER[QwenEventType.GENERATION_FINISHED] < EVENT_ORDER[QwenEventType.OUTPUT_COPIED]


def test_event_exports_are_available_and_legacy_vo_alias_is_compatible() -> None:
    assert EVENT_WEB_LOADED == LEGACY_EVENT_WEB_LOADED
    assert EVENT_FILE_UPLOADED == QwenEventType.FILE_UPLOADED
    assert EVENT_PROMPT_INJECTED == QwenEventType.PROMPT_INJECTED
    assert EVENT_DOCUMENT_PARSED == QwenEventType.DOCUMENT_PARSED
    assert EVENT_SEND_CLICKED == QwenEventType.SEND_CLICKED
    assert EVENT_THINKING_STARTED == QwenEventType.THINKING_STARTED
    assert EVENT_STREAMING_GENERATION == QwenEventType.STREAMING_GENERATION
    assert EVENT_GENERATION_FINISHED == QwenEventType.GENERATION_FINISHED
    assert EVENT_OUTPUT_COPIED == QwenEventType.OUTPUT_COPIED


def test_lifecycle_event_is_immutable_and_legacy_vo_classes_are_constructible() -> None:
    details = EventDetails({"source": "test"})
    event = LifecycleEvent(name="EVENT_TEST", details=details)

    assert isinstance(details, EventDetails)
    assert isinstance(EventOrderMap({QwenEventType.WEB_LOADED: 0}), EventOrderMap)
    assert dict(event.details) == {"source": "test"}
    with pytest.raises(TypeError):
        event.details["source"] = "changed"
    with pytest.raises(FrozenInstanceError):
        event.name = "EVENT_CHANGED"


def test_entity_remains_for_stateful_runtime_behavior() -> None:
    state = LifecycleState()
    state.mark(EVENT_WEB_LOADED)
    assert state.web_loaded is True
    assert state.document_parsed is False
    assert isinstance(LifecycleEmitter(), LifecycleEmitter)


def test_error_taxonomy_has_new_source_and_legacy_facade() -> None:
    assert LEGACY_QWEN_CLI_ERROR is QwenCliError
    assert ErrorCategory.categorize(RuntimeError("network timeout")) == "network"
