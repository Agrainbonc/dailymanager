from __future__ import annotations

from app.adapters.asr import (
    DashScopeAsrProvider,
    MockAsrProvider,
    OpenAiCompatibleAsrProvider,
    QwenAsrLocalProvider,
    ZhixinWsAsrProvider,
    get_asr_provider,
)
from app.adapters.contracts import (
    AsrProvider,
    SlideVisualAnalysis,
    TranscriptionResult,
    TranscriptSegment,
    VisionProvider,
)
from app.adapters.vision import (
    MockVisionProvider,
    OpenAIVisionProvider,
    get_vision_provider,
)

__all__ = [
    "AsrProvider",
    "VisionProvider",
    "TranscriptSegment",
    "TranscriptionResult",
    "SlideVisualAnalysis",
    "ZhixinWsAsrProvider",
    "MockAsrProvider",
    "OpenAiCompatibleAsrProvider",
    "DashScopeAsrProvider",
    "QwenAsrLocalProvider",
    "get_asr_provider",
    "MockVisionProvider",
    "OpenAIVisionProvider",
    "get_vision_provider",
]
