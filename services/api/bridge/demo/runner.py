import asyncio
import json
from typing import Any

from bridge.agents.interpreter import InterpreterAgent
from bridge.agents.policy import PolicyAgent
from bridge.agents.question import QuestionAgent
from bridge.agents.record import RecordAgent
from bridge.audio.providers import (
    AudioProviderSettings,
    build_asr_provider,
    build_translation_provider,
    build_tts_provider,
)
from bridge.bus.events import (
    AgentStatusEvent,
    BridgeEvent,
    CommitmentEvent,
    FinalUtteranceEvent,
    PolicyCardEvent,
    SessionEndedEvent,
    SessionStartedEvent,
)
from bridge.config import BridgeSettings
from bridge.rag import LocalHybridRetriever, PolicyCardSettings, build_corpus, load_index


def load_demo_scenario(settings: BridgeSettings) -> dict[str, Any]:
    scenario_path = settings.data_dir / settings.demo_scenario
    with scenario_path.open(encoding="utf-8") as scenario_file:
        return json.load(scenario_file)


def build_demo_events(settings: BridgeSettings, session_id: str | None = None) -> list[BridgeEvent]:
    return asyncio.run(build_demo_events_async(settings, session_id=session_id))


async def build_demo_events_async(
    settings: BridgeSettings,
    session_id: str | None = None,
) -> list[BridgeEvent]:
    scenario = load_demo_scenario(settings)
    active_session_id = session_id or scenario["session_id"]
    resident_language = scenario.get("resident_language", "bn")
    caseworker_language = scenario.get("caseworker_language", "en")
    event_clock_ms = 0
    events: list[BridgeEvent] = [
        SessionStartedEvent(
            session_id=active_session_id,
            occurred_at_ms=event_clock_ms,
            mode=settings.mode,
            scenario=scenario["scenario"],
            resident_language=resident_language,
            caseworker_language=caseworker_language,
            allow_cloud=settings.allow_cloud,
        )
    ]

    def tick(step_ms: int = 250) -> int:
        nonlocal event_clock_ms
        event_clock_ms += step_ms
        return event_clock_ms

    def append(event: BridgeEvent, step_ms: int = 250) -> None:
        if event.occurred_at_ms is None:
            event.occurred_at_ms = tick(step_ms)
        events.append(event)

    def status(agent: str, state: str, message: str, step_ms: int = 150) -> None:
        events.append(
            AgentStatusEvent(
                session_id=active_session_id,
                occurred_at_ms=tick(step_ms),
                agent=agent,  # type: ignore[arg-type]
                status=state,  # type: ignore[arg-type]
                message=message,
            )
        )

    audio_settings = AudioProviderSettings(
        asr_provider=settings.asr_provider,
        tts_provider=settings.tts_provider,
        llm_provider=settings.llm_provider,
        allow_cloud=settings.allow_cloud,
    )
    interpreter = InterpreterAgent(
        asr=build_asr_provider(audio_settings),
        translator=build_translation_provider(audio_settings),
        tts=build_tts_provider(audio_settings),
    )
    policy_agent = build_policy_agent(
        settings,
        authority_filter=scenario.get(
            "authority_filter",
            ["City of London", "City of London Corporation", "Greater London Authority"],
        ),
    )
    question_agent = QuestionAgent(resident_language=resident_language)
    commitments_by_turn = commitments_by_trigger(scenario.get("commitments", []))
    fallback_policy_cards_by_turn = policy_cards_by_trigger(
        scenario.get("policy_cards", []),
        session_id=active_session_id,
    )
    emitted_policy_card_ids: set[str] = set()

    async for event in interpreter.run_fixture(
        settings.data_dir / settings.demo_scenario,
        session_id=active_session_id,
    ):
        append(event, step_ms=180)
        if not isinstance(event, FinalUtteranceEvent):
            continue

        generated_policy_cards = policy_agent.handle_final_utterance(event) if policy_agent else []
        policy_cards = fallback_policy_cards_by_turn.get(event.turn_id, []) or generated_policy_cards
        policy_cards = [
            card for card in policy_cards if card.card_id not in emitted_policy_card_ids
        ]
        if policy_cards:
            status("policy", "thinking", "Checking local cited policy corpus")
            for card in policy_cards:
                if card.occurred_at_ms is None:
                    card.occurred_at_ms = tick(260)
                events.append(card)
                emitted_policy_card_ids.add(card.card_id)
            status("policy", "idle", "Cited policy card emitted")

        prompts = question_agent.suggest(events)
        if prompts:
            status("question", "thinking", "Selecting conservative checklist prompt")
            for prompt in prompts:
                append(prompt, step_ms=180)
            status("question", "idle", "Resident prompt ready")

        for commitment in commitments_by_turn.get(event.turn_id, []):
            append(commitment_for_session(commitment, active_session_id), step_ms=100)

    status("record", "emitting", "Rendering deterministic bilingual record")
    record_agent = RecordAgent(output_dir=settings.record_output_dir)
    record_snapshot = record_agent.generate_snapshot(events)
    record_snapshot.occurred_at_ms = tick(300)
    record_snapshot.html_path = f"/session/{active_session_id}/record.html"
    record_snapshot.json_path = f"/session/{active_session_id}/record.json"
    record_snapshot.citations_count = sum(1 for event in events if isinstance(event, PolicyCardEvent))
    events.append(record_snapshot)
    status("record", "idle", "Record ready")
    events.append(
        SessionEndedEvent(
            session_id=active_session_id,
            occurred_at_ms=tick(100),
            reason="demo_complete",
            record_id=record_snapshot.record_id,
        )
    )
    return events


def dump_events(events: list[BridgeEvent]) -> list[dict[str, Any]]:
    return [event.model_dump(exclude_none=True) for event in events]


def build_policy_agent(
    settings: BridgeSettings,
    *,
    authority_filter: list[str] | None = None,
) -> PolicyAgent | None:
    if settings.rag_provider in {"disabled", "none"}:
        return None

    index_dir = settings.data_dir / "processed"
    chunks = load_index(index_dir)
    if not chunks:
        report = build_corpus(settings.data_dir / "sources.yml", fetch=False)
        chunks = report.chunks
    if authority_filter:
        allowed_authorities = set(authority_filter)
        chunks = [chunk for chunk in chunks if chunk.authority in allowed_authorities]
    return PolicyAgent(
        LocalHybridRetriever(chunks),
        settings=PolicyCardSettings(min_confidence=0.42),
    )


def policy_cards_by_trigger(
    raw_cards: list[dict[str, Any]],
    *,
    session_id: str,
) -> dict[str, list[PolicyCardEvent]]:
    by_turn: dict[str, list[PolicyCardEvent]] = {}
    for card in raw_cards:
        event = PolicyCardEvent(
            session_id=session_id,
            card_id=card["card_id"],
            title=card["title"],
            claim=card["claim"],
            source_title=card["source_title"],
            source_url=card["source_url"],
            source_span=card["source_span"],
            authority=card["authority"],
            confidence=card["confidence"],
            trigger_turn_ids=card["trigger_turn_ids"],
        )
        for turn_id in card.get("trigger_turn_ids", []):
            by_turn.setdefault(turn_id, []).append(event)
    return by_turn


def commitments_by_trigger(raw_commitments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_turn: dict[str, list[dict[str, Any]]] = {}
    for commitment in raw_commitments:
        for turn_id in commitment.get("trigger_turn_ids", []):
            by_turn.setdefault(turn_id, []).append(commitment)
    return by_turn


def commitment_for_session(commitment: dict[str, Any], session_id: str) -> CommitmentEvent:
    return CommitmentEvent(
        session_id=session_id,
        commitment_id=commitment["commitment_id"],
        owner=commitment["owner"],
        text=commitment["text"],
        due=commitment.get("due"),
        trigger_turn_ids=commitment["trigger_turn_ids"],
    )
