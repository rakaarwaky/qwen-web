"""Pure lifecycle/streaming predicate helpers.

Taxonomy layer (utility): stateless functions, taxonomy imports only. Used by the
stream monitor capability to keep the stability loop logic testable and side-effect free.
"""

from __future__ import annotations


def should_treat_as_new_response(
    text: str | None,
    baseline: str | None,
    min_text_length: int,
) -> bool:
    """True when text is non-empty, long enough, and differs from the baseline."""
    return text is not None and len(text) >= min_text_length and text != baseline


def is_stability_satisfied(
    stable_count: int,
    stability_checks: int,
    has_thinking: bool,
    has_streaming: bool,
    is_complete: bool,
) -> bool:
    """Decide whether the response has stabilized enough to accept it."""
    _ = (has_thinking, has_streaming)
    force_complete = stable_count >= (stability_checks * 6)
    return bool(stable_count >= stability_checks and (is_complete or force_complete))
