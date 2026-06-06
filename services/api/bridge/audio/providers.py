"""Voice provider interfaces and configuration-gated factories.

The demo providers are deterministic and fixture-backed. Live providers are
registered here, but intentionally fail closed unless the matching provider
environment variable is selected and cloud use has been explicitly allowed when
needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from bridge.bus.events import Speaker


@dataclass(frozen=True)
class AudioProviderSettings:
    asr_provider: str = "demo"
    tts_provider: str = "demo"
    llm_provider: str = "demo"
    allow_cloud: bool = False

    @classmethod
    def from_env(cls) -> "AudioProviderSettings":
        return cls(
            asr_provider=os.getenv("ASR_PROVIDER", "demo").strip().lower(),
            tts_provider=os.getenv("TTS_PROVIDER", "demo").strip().lower(),
            llm_provider=os.getenv("LLM_PROVIDER", "demo").strip().lower(),
            allow_cloud=os.getenv("ALLOW_CLOUD", "false").strip().lower()
            in {"1", "true", "yes", "on"},
        )


@dataclass(frozen=True)
class TranscriptSegment:
    turn_id: str
    speaker: Speaker
    language: str
    text: str
    start_ms: int | None = None
    end_ms: int | None = None
    confidence: float | None = None
    stability: float | None = None


@dataclass(frozen=True)
class TranslationResult:
    turn_id: str
    speaker: Speaker
    source_language: str
    target_language: str
    source_text: str
    translated_text: str
    confidence: float | None = None


@dataclass(frozen=True)
class SpeechSynthesisResult:
    turn_id: str
    language: str
    text: str
    audio_path: Path | None = None
    provider: str = "demo"


class ASRProvider(Protocol):
    name: str

    async def partials_for_turn(self, turn: dict) -> list[TranscriptSegment]:
        """Return partial transcript segments for a fixture or live turn."""

    async def final_for_turn(self, turn: dict) -> TranscriptSegment:
        """Return the final transcript segment for a fixture or live turn."""


class TranslationProvider(Protocol):
    name: str

    async def translate_turn(self, turn: dict, target_language: str) -> TranslationResult:
        """Translate a completed turn into the requested language."""


class TTSProvider(Protocol):
    name: str

    async def synthesize(self, turn_id: str, text: str, language: str) -> SpeechSynthesisResult:
        """Synthesize translated speech or return a deterministic demo handle."""


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider is selected but cannot be activated safely."""


class LiveProviderStub:
    def __init__(self, provider_kind: str, provider_name: str) -> None:
        self.provider_kind = provider_kind
        self.name = provider_name

    def _raise(self) -> None:
        raise ProviderUnavailableError(
            f"{self.provider_kind} provider '{self.name}' is configured but not implemented in "
            "this branch. Use the demo provider or add the provider adapter behind the same flags."
        )

    async def partials_for_turn(self, turn: dict) -> list[TranscriptSegment]:
        self._raise()

    async def final_for_turn(self, turn: dict) -> TranscriptSegment:
        self._raise()

    async def translate_turn(self, turn: dict, target_language: str) -> TranslationResult:
        self._raise()

    async def synthesize(self, turn_id: str, text: str, language: str) -> SpeechSynthesisResult:
        self._raise()


def require_cloud_allowed(
    provider_kind: str,
    provider_name: str,
    settings: AudioProviderSettings,
) -> None:
    cloud_providers = {
        "asr": {"elevenlabs", "elevenlabs_realtime", "elevenlabs_scribe", "scribe"},
        "tts": {"elevenlabs", "elevenlabs_tts"},
        "llm": {"openai", "anthropic", "elevenlabs", "cloud"},
    }
    if provider_name in cloud_providers.get(provider_kind, set()) and not settings.allow_cloud:
        raise ProviderUnavailableError(
            f"{provider_kind.upper()}_PROVIDER={provider_name} requires ALLOW_CLOUD=true."
        )


def build_asr_provider(settings: AudioProviderSettings) -> ASRProvider:
    from bridge.audio.demo import DemoASRProvider

    if settings.asr_provider == "demo":
        return DemoASRProvider()
    require_cloud_allowed("asr", settings.asr_provider, settings)
    return LiveProviderStub("ASR", settings.asr_provider)


def build_translation_provider(settings: AudioProviderSettings) -> TranslationProvider:
    from bridge.audio.demo import DemoTranslationProvider

    if settings.llm_provider == "demo":
        return DemoTranslationProvider()
    require_cloud_allowed("llm", settings.llm_provider, settings)
    return LiveProviderStub("LLM translation", settings.llm_provider)


def build_tts_provider(settings: AudioProviderSettings) -> TTSProvider:
    from bridge.audio.demo import DemoTTSProvider

    if settings.tts_provider == "demo":
        return DemoTTSProvider()
    require_cloud_allowed("tts", settings.tts_provider, settings)
    return LiveProviderStub("TTS", settings.tts_provider)
