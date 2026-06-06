"""ASR and TTS provider adapters."""
from bridge.audio.providers import (
    ASRProvider,
    AudioProviderSettings,
    ProviderUnavailableError,
    SpeechSynthesisResult,
    TTSProvider,
    TranscriptSegment,
    TranslationProvider,
    TranslationResult,
    build_asr_provider,
    build_translation_provider,
    build_tts_provider,
)

__all__ = [
    "ASRProvider",
    "AudioProviderSettings",
    "ProviderUnavailableError",
    "SpeechSynthesisResult",
    "TTSProvider",
    "TranscriptSegment",
    "TranslationProvider",
    "TranslationResult",
    "build_asr_provider",
    "build_translation_provider",
    "build_tts_provider",
]
