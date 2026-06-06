"""Deterministic fixture-backed voice providers."""

from __future__ import annotations

from bridge.audio.providers import (
    SpeechSynthesisResult,
    TranscriptSegment,
    TranslationResult,
)


class DemoASRProvider:
    name = "demo"

    async def partials_for_turn(self, turn: dict) -> list[TranscriptSegment]:
        partials = turn.get("partials") or _single_partial(turn) or _word_partials(turn["text"])
        return [
            TranscriptSegment(
                turn_id=turn["turn_id"],
                speaker=turn["speaker"],
                language=turn["language"],
                text=partial["text"],
                start_ms=partial.get("start_ms", turn.get("start_ms")),
                end_ms=partial.get("end_ms"),
                confidence=partial.get("confidence", turn.get("confidence")),
                stability=partial.get("stability"),
            )
            for partial in partials
        ]

    async def final_for_turn(self, turn: dict) -> TranscriptSegment:
        return TranscriptSegment(
            turn_id=turn["turn_id"],
            speaker=turn["speaker"],
            language=turn["language"],
            text=turn["text"],
            start_ms=turn.get("start_ms"),
            end_ms=turn.get("end_ms"),
            confidence=turn.get("confidence", 1.0),
            stability=1.0,
        )


class DemoTranslationProvider:
    name = "demo"

    async def translate_turn(self, turn: dict, target_language: str) -> TranslationResult:
        translated_text = turn.get("translated_text")
        if translated_text is None:
            translated_text = turn["text"]
        return TranslationResult(
            turn_id=turn["turn_id"],
            speaker=turn["speaker"],
            source_language=turn["language"],
            target_language=target_language,
            source_text=turn["text"],
            translated_text=translated_text,
            confidence=turn.get("translation_confidence", turn.get("confidence", 1.0)),
        )


class DemoTTSProvider:
    name = "demo"

    async def synthesize(self, turn_id: str, text: str, language: str) -> SpeechSynthesisResult:
        return SpeechSynthesisResult(
            turn_id=turn_id,
            language=language,
            text=text,
            audio_path=None,
            provider=self.name,
        )


def _single_partial(turn: dict) -> list[dict] | None:
    partial_text = turn.get("partial_text")
    if not partial_text:
        return None
    return [
        {
            "text": partial_text,
            "start_ms": turn.get("start_ms"),
            "end_ms": turn.get("end_ms"),
            "confidence": turn.get("confidence"),
            "stability": 0.78,
        }
    ]


def _word_partials(text: str) -> list[dict[str, float | int | str]]:
    words = text.split()
    if len(words) <= 1:
        return [{"text": text, "stability": 0.75}]

    checkpoints = sorted({max(1, len(words) // 3), max(1, (len(words) * 2) // 3), len(words)})
    return [
        {
            "text": " ".join(words[:checkpoint]),
            "end_ms": checkpoint * 350,
            "stability": min(0.95, 0.45 + (checkpoint / len(words)) * 0.45),
        }
        for checkpoint in checkpoints
    ]
