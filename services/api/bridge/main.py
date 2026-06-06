import asyncio

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from bridge.config import load_settings
from bridge.demo.runner import build_demo_events_async, dump_events
from bridge.records import build_record, render_record_html

app = FastAPI(title="Bridge API")


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


@app.get("/session/{session_id}/record.json")
async def get_session_record_json(session_id: str) -> dict[str, object]:
    settings = load_settings()
    events = await build_demo_events_async(settings, session_id=session_id)
    return dict(build_record(events))


@app.get("/session/{session_id}/record.html", response_class=HTMLResponse)
async def get_session_record_html(session_id: str) -> str:
    settings = load_settings()
    events = await build_demo_events_async(settings, session_id=session_id)
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
