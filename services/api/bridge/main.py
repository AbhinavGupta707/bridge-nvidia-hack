import asyncio
import re
from typing import Literal

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from bridge.agents.question import QuestionAgent
from bridge.agents.record import RecordAgent
from bridge.bus.events import (
    AgentStatusEvent,
    BridgeMode,
    BridgeEvent,
    CommitmentEvent,
    FinalUtteranceEvent,
    PolicyCardEvent,
    SessionStartedEvent,
)
from bridge.config import BridgeSettings, load_settings
from bridge.demo.runner import build_demo_events_async, build_policy_agent, dump_events
from bridge.records import build_record, render_record_html

app = FastAPI(title="Bridge API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ManualUtteranceRequest(BaseModel):
    speaker: Literal["resident", "caseworker"] = "resident"
    language: str = "en"
    text: str
    translated_text: str | None = None
    resident_language: str = "bn"


MANUAL_SESSIONS: dict[str, list[BridgeEvent]] = {}


@app.get("/health")
async def health() -> dict[str, object]:
    settings = load_settings()
    return {
        "status": "ok",
        "mode": settings.mode,
        "deterministic_demo": settings.deterministic_demo,
        "allow_cloud": settings.allow_cloud,
        "providers": {
            "asr": settings.asr_provider,
            "tts": settings.tts_provider,
            "llm": settings.llm_provider,
            "rag": settings.rag_provider,
        },
    }


@app.post("/session")
async def create_session() -> dict[str, str]:
    settings = load_settings()
    return {"session_id": "demo-001", "mode": settings.mode}


@app.get("/session/{session_id}")
async def get_session(session_id: str) -> dict[str, object]:
    settings = load_settings()
    events = await build_demo_events_async(settings, session_id=session_id)
    return {
        "session_id": session_id,
        "mode": settings.mode,
        "event_count": len(events),
        "deterministic_demo": settings.deterministic_demo,
    }


@app.get("/session/{session_id}/events")
async def get_session_events(session_id: str) -> list[dict[str, object]]:
    settings = load_settings()
    return dump_events(await build_demo_events_async(settings, session_id=session_id))


@app.get("/session/{session_id}/manual_events")
async def get_manual_session_events(session_id: str) -> list[dict[str, object]]:
    return dump_events(MANUAL_SESSIONS.get(session_id, []))


@app.post("/session/{session_id}/manual_utterance")
async def add_manual_utterance(
    session_id: str,
    request: ManualUtteranceRequest,
) -> list[dict[str, object]]:
    settings = load_settings()
    events = manual_session_events(
        session_id,
        request.resident_language,
        mode=settings.mode,
        allow_cloud=settings.allow_cloud,
    )
    include_session_start = not any(event.type == "final_utterance" for event in events)
    new_events = build_manual_turn_events(settings, events, session_id, request)
    events.extend(new_events)
    if include_session_start:
        return dump_events([events[0], *new_events])
    return dump_events(new_events)


@app.get("/session/{session_id}/record.json")
async def get_session_record_json(session_id: str) -> dict[str, object]:
    settings = load_settings()
    events = await events_for_record(settings, session_id)
    return dict(build_record(events))


@app.get("/session/{session_id}/record.html", response_class=HTMLResponse)
async def get_session_record_html(session_id: str) -> str:
    settings = load_settings()
    events = await events_for_record(settings, session_id)
    return render_record_html(build_record(events))


@app.websocket("/ws/session/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    settings = load_settings()
    try:
        for event in await build_demo_events_async(settings, session_id=session_id):
            await websocket.send_json(event.model_dump(exclude_none=True))
            if settings.demo_step_ms:
                await asyncio.sleep(settings.demo_step_ms / 1000)
    except WebSocketDisconnect:
        return


async def events_for_record(settings: BridgeSettings, session_id: str) -> list[BridgeEvent]:
    manual_events = MANUAL_SESSIONS.get(session_id)
    if manual_events and any(event.type == "final_utterance" for event in manual_events):
        return manual_events
    return await build_demo_events_async(settings, session_id=session_id)


def manual_session_events(
    session_id: str,
    resident_language: str,
    *,
    mode: BridgeMode,
    allow_cloud: bool,
) -> list[BridgeEvent]:
    if session_id not in MANUAL_SESSIONS:
        MANUAL_SESSIONS[session_id] = [
            SessionStartedEvent(
                session_id=session_id,
                mode=mode,
                scenario="Manual typed rehearsal",
                resident_language=resident_language,
                caseworker_language="en",
                allow_cloud=allow_cloud,
                occurred_at_ms=0,
            )
        ]
    return MANUAL_SESSIONS[session_id]


def build_manual_turn_events(
    settings: BridgeSettings,
    existing_events: list[BridgeEvent],
    session_id: str,
    request: ManualUtteranceRequest,
) -> list[BridgeEvent]:
    event_clock_ms = next_event_time(existing_events)
    turn_id = f"m-{sum(1 for event in existing_events if event.type == 'final_utterance') + 1:03d}"
    translated_text = request.translated_text or request.text
    final = FinalUtteranceEvent(
        session_id=session_id,
        occurred_at_ms=event_clock_ms,
        turn_id=turn_id,
        speaker=request.speaker,
        language=request.language,
        text=request.text,
        translated_text=translated_text,
        confidence=1.0,
    )

    new_events: list[BridgeEvent] = [
        AgentStatusEvent(
            session_id=session_id,
            occurred_at_ms=event_clock_ms - 100,
            agent="interpreter",
            status="emitting",
            message="Manual typed utterance accepted",
        ),
        final,
    ]

    policy_agent = build_policy_agent(settings)
    policy_cards = policy_agent.handle_final_utterance(final) if policy_agent else []
    if policy_cards:
        new_events.append(
            AgentStatusEvent(
                session_id=session_id,
                occurred_at_ms=event_clock_ms + 100,
                agent="policy",
                status="thinking",
                message="Checking local cited policy corpus",
            )
        )
        for index, card in enumerate(policy_cards):
            card.occurred_at_ms = event_clock_ms + 200 + (index * 100)
            new_events.append(card)
        new_events.append(
            AgentStatusEvent(
                session_id=session_id,
                occurred_at_ms=event_clock_ms + 250 + (len(policy_cards) * 100),
                agent="policy",
                status="idle",
                message="Cited policy card emitted",
            )
        )

    question_agent = QuestionAgent(resident_language=request.resident_language)
    prompts = question_agent.suggest([*existing_events, *new_events])
    if prompts:
        new_events.append(
            AgentStatusEvent(
                session_id=session_id,
                occurred_at_ms=event_clock_ms + 450,
                agent="question",
                status="thinking",
                message="Selecting conservative checklist prompt",
            )
        )
        for index, prompt in enumerate(prompts):
            prompt.occurred_at_ms = event_clock_ms + 550 + (index * 100)
            new_events.append(prompt)
        new_events.append(
            AgentStatusEvent(
                session_id=session_id,
                occurred_at_ms=event_clock_ms + 600 + (len(prompts) * 100),
                agent="question",
                status="idle",
                message="Resident prompt ready",
            )
        )

    commitment = commitment_from_caseworker(final)
    if commitment:
        commitment.occurred_at_ms = event_clock_ms + 800
        new_events.append(commitment)

    record_snapshot = RecordAgent(output_dir=settings.record_output_dir).generate_snapshot(
        [*existing_events, *new_events]
    )
    record_snapshot.occurred_at_ms = event_clock_ms + 900
    record_snapshot.html_path = f"/session/{session_id}/record.html"
    record_snapshot.json_path = f"/session/{session_id}/record.json"
    record_snapshot.citations_count = sum(
        1 for event in [*existing_events, *new_events] if isinstance(event, PolicyCardEvent)
    )
    new_events.append(record_snapshot)
    new_events.append(
        AgentStatusEvent(
            session_id=session_id,
            occurred_at_ms=event_clock_ms + 950,
            agent="record",
            status="idle",
            message="Manual record updated",
        )
    )
    return new_events


def next_event_time(events: list[BridgeEvent]) -> int:
    return max((event.occurred_at_ms or 0 for event in events), default=0) + 1000


def commitment_from_caseworker(event: FinalUtteranceEvent) -> CommitmentEvent | None:
    if event.speaker != "caseworker":
        return None
    if not re.search(r"\b(i|we)\s+will\b|\bwill\s+(send|call|check|book|review|contact)\b", event.text, re.I):
        return None
    return CommitmentEvent(
        session_id=event.session_id,
        commitment_id=f"commitment-{event.turn_id}",
        owner="caseworker",
        text=event.text,
        due="today" if re.search(r"\b(today|tonight|now)\b", event.text, re.I) else None,
        trigger_turn_ids=[event.turn_id],
    )
