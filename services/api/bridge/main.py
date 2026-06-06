from fastapi import FastAPI, WebSocket

from bridge.bus.events import AgentStatusEvent, BridgeEvent

app = FastAPI(title="Bridge API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mode": "demo"}


@app.websocket("/ws/session/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    initial = AgentStatusEvent(
        session_id=session_id,
        agent="interpreter",
        status="idle",
        message="Demo session connected",
    )
    await websocket.send_json(initial.model_dump())
    while True:
        inbound = await websocket.receive_json()
        if inbound.get("type") == "ping":
            event: BridgeEvent = AgentStatusEvent(
                session_id=session_id,
                agent="record",
                status="idle",
                message="pong",
            )
            await websocket.send_json(event.model_dump())
        if inbound.get("type") == "end_session":
            break

