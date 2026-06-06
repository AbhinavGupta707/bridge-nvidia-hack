import asyncio

import pytest

from bridge.audio import ProviderUnavailableError
from bridge.agents.interpreter import InterpreterAgent, load_demo_scenario
from bridge.bus.events import FinalUtteranceEvent, PartialTranscriptEvent, TranslationEvent


def test_interpreter_fixture_emits_demo_voice_events() -> None:
    agent = InterpreterAgent.from_env()

    async def collect_events() -> list:
        return [event async for event in agent.run_fixture()]

    events = asyncio.run(collect_events())

    assert events[0].type == "agent_status"
    assert events[-1].type == "agent_status"
    assert any(isinstance(event, PartialTranscriptEvent) for event in events)
    assert any(isinstance(event, TranslationEvent) for event in events)

    scenario = load_demo_scenario()
    final_utterances = [event for event in events if isinstance(event, FinalUtteranceEvent)]
    assert [event.turn_id for event in final_utterances] == [
        turn["turn_id"] for turn in scenario["turns"]
    ]
    assert final_utterances[0].translated_text == scenario["turns"][0]["translated_text"]
    assert final_utterances[-1].translated_text == scenario["turns"][-1]["translated_text"]


def test_interpreter_from_env_uses_demo_providers_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ASR_PROVIDER", raising=False)
    monkeypatch.delenv("TTS_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ALLOW_CLOUD", "false")

    agent = InterpreterAgent.from_env()

    assert agent.asr.name == "demo"
    assert agent.translator.name == "demo"
    assert agent.tts.name == "demo"


def test_cloud_asr_requires_allow_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_PROVIDER", "elevenlabs")
    monkeypatch.setenv("TTS_PROVIDER", "demo")
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.setenv("ALLOW_CLOUD", "false")

    with pytest.raises(ProviderUnavailableError, match="ALLOW_CLOUD=true"):
        InterpreterAgent.from_env()
