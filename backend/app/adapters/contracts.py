from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None
    speaker: str | None = None


@dataclass(frozen=True)
class TranscriptionResult:
    full_text: str
    duration_ms: int
    language: str | None
    segments: list[TranscriptSegment] = field(default_factory=list)


@dataclass(frozen=True)
class SlideVisualAnalysis:
    page_number: int
    summary: str
    key_elements: list[str]
    confidence: float | None = None
    uncertainty: str | None = None


class AsrProvider(Protocol):
    name: str

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> TranscriptionResult:
        """Return model-native timestamps; never fabricate them from an LLM response."""


class VisionProvider(Protocol):
    name: str

    def analyze_slide(
        self,
        image_path: Path,
        *,
        page_number: int,
        native_text: str,
    ) -> SlideVisualAnalysis:
        """Explain visual evidence for a single presentation page."""

