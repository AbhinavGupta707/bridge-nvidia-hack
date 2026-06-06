"""Interpreter Agent.

The first supported mode is deterministic demo playback from fixtures. Live ASR,
translation, and TTS providers plug into the same provider interfaces and are
kept behind explicit environment flags.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

from bridge.audio import (
    ASRProvider,
    AudioProviderSettings,
    TTSProvider,
    TranslationProvider,
    build_asr_provider,
    build_translation_provider,
    build_tts_provider,
)
from bridge.bus.events import (
    AgentStatusEvent,
    BridgeEvent,
    FinalUtteranceEvent,
    PartialTranscriptEvent,
    TranslationEvent,
)


DEFAULT_FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "fixtures" / "demo_scenario.json"
)


@dataclass(frozen=True)
class InterpreterAgent:
    asr: ASRProvider
    translator: TranslationProvider
    tts: TTSProvider
    partial_delay_s: float = 0.0
    turn_delay_s: float = 0.0

    @classmethod
    def from_env(
        cls,
        *,
        partial_delay_s: float = 0.0,
        turn_delay_s: float = 0.0,
    ) -> "InterpreterAgent":
        settings = AudioProviderSettings.from_env()
        return cls(
            asr=build_asr_provider(settings),
            translator=build_translation_provider(settings),
            tts=build_tts_provider(settings),
            partial_delay_s=partial_delay_s,
            turn_delay_s=turn_delay_s,
        )

    async def run_fixture(
        self,
        fixture_path: Path = DEFAULT_FIXTURE_PATH,
        *,
        session_id: str | None = None,
    ) -> AsyncIterator[BridgeEvent]:
        scenario = load_demo_scenario(fixture_path)
        active_session_id = session_id or scenario["session_id"]
        resident_language = scenario.get("resident_language", "en")

        yield AgentStatusEvent(
            session_id=active_session_id,
            agent="interpreter",
            status="listening",
            message=f"ASR={self.asr.name}, translation={self.translator.name}, TTS={self.tts.name}",
        )

        for turn in scenario["turns"]:
            target_language = _target_language_for_turn(turn["language"], resident_language)

            for partial in await self.asr.partials_for_turn(turn):
                yield PartialTranscriptEvent(
                    session_id=active_session_id,
                    turn_id=partial.turn_id,
                    speaker=partial.speaker,
                    language=partial.language,
                    text=partial.text,
                    start_ms=partial.start_ms,
                    end_ms=partial.end_ms,
                    confidence=partial.confidence,
                    stability=partial.stability,
                )
                if self.partial_delay_s:
                    await asyncio.sleep(self.partial_delay_s)

            final = await self.asr.final_for_turn(turn)
            translation = await self.translator.translate_turn(turn, target_language)
            await self.tts.synthesize(
                turn_id=translation.turn_id,
                text=translation.translated_text,
                language=translation.target_language,
            )

            yield TranslationEvent(
                session_id=active_session_id,
                turn_id=translation.turn_id,
                speaker=translation.speaker,
                source_language=translation.source_language,
                target_language=translation.target_language,
                source_text=translation.source_text,
                translated_text=translation.translated_text,
                confidence=translation.confidence,
            )
            yield FinalUtteranceEvent(
                session_id=active_session_id,
                turn_id=final.turn_id,
                speaker=final.speaker,
                language=final.language,
                text=final.text,
                translated_text=translation.translated_text,
                start_ms=final.start_ms,
                end_ms=final.end_ms,
                confidence=final.confidence,
            )

            if self.turn_delay_s:
                await asyncio.sleep(self.turn_delay_s)

        yield AgentStatusEvent(
            session_id=active_session_id,
            agent="interpreter",
            status="idle",
            message="Demo fixture complete",
        )


def load_demo_scenario(fixture_path: Path = DEFAULT_FIXTURE_PATH) -> dict:
    with fixture_path.open(encoding="utf-8") as fixture_file:
        scenario = json.load(fixture_file)

    if not scenario.get("session_id"):
        raise ValueError(f"Fixture {fixture_path} must include session_id.")
    if not scenario.get("turns"):
        raise ValueError(f"Fixture {fixture_path} must include at least one turn.")

    required_turn_fields = {"turn_id", "speaker", "language", "text"}
    for turn in scenario["turns"]:
        missing = sorted(required_turn_fields - set(turn))
        if missing:
            raise ValueError(f"Fixture turn {turn.get('turn_id', '<unknown>')} missing {missing}.")

    return scenario


def _target_language_for_turn(source_language: str, resident_language: str) -> str:
    if source_language == "en":
        return resident_language
    return "en"
