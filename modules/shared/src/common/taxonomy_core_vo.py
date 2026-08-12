"""Core brand types (NewType value objects) shared across the qwen-web domain.

Taxonomy layer (taxonomy(vo)): type-level brand aliases, no behavior.
"""

from __future__ import annotations

from typing import NewType

PromptText = NewType("PromptText", str)
InputPath = NewType("InputPath", str)
OutputPath = NewType("OutputPath", str)
FilePath = NewType("FilePath", str)
RunId = NewType("RunId", str)
MessageCount = NewType("MessageCount", int)
ResponseText = NewType("ResponseText", str)
StabilityCount = NewType("StabilityCount", int)
TimeoutSec = NewType("TimeoutSec", int)
PollIntervalSec = NewType("PollIntervalSec", float)
HeadlessFlag = NewType("HeadlessFlag", bool)
Mode = NewType("Mode", str)
