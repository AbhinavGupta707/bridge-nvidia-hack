from fastapi.testclient import TestClient

from bridge.main import MANUAL_SESSIONS, app


def test_health_reports_demo_mode_by_default(monkeypatch) -> None:
    monkeypatch.delenv("BRIDGE_MODE", raising=False)
    monkeypatch.delenv("ALLOW_CLOUD", raising=False)

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "demo"
    assert payload["deterministic_demo"] is True


def test_session_events_endpoint_returns_demo_stream() -> None:
    client = TestClient(app)
    response = client.get("/session/demo-test/events")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["type"] == "session_started"
    assert any(event["type"] == "policy_card" for event in payload)
    record_snapshot = next(event for event in payload if event["type"] == "record_snapshot")
    assert record_snapshot["html_path"] == "/session/demo-test/record.html"
    assert record_snapshot["json_path"] == "/session/demo-test/record.json"
    assert payload[-1]["type"] == "session_ended"


def test_session_record_endpoints_render_from_event_log() -> None:
    client = TestClient(app)

    json_response = client.get("/session/demo-test/record.json")
    html_response = client.get("/session/demo-test/record.html")

    assert json_response.status_code == 200
    assert html_response.status_code == 200
    record = json_response.json()
    assert record["session_id"] == "demo-test"
    assert record["policy_citations"]
    assert record["bilingual_transcript"]
    assert "Bridge Appointment Record" in html_response.text
    assert "not legal advice" in html_response.text


def test_session_websocket_streams_demo_events(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_DEMO_STEP_MS", "0")

    client = TestClient(app)
    seen: list[str] = []

    with client.websocket_connect("/ws/session/demo-test") as websocket:
        for _ in range(100):
            event = websocket.receive_json()
            seen.append(event["type"])
            if event["type"] == "session_ended":
                break

    assert seen[0] == "session_started"
    assert "record_snapshot" in seen
    assert seen[-1] == "session_ended"


def test_manual_utterance_runs_agents_and_updates_record() -> None:
    MANUAL_SESSIONS.clear()
    client = TestClient(app)

    response = client.post(
        "/session/manual-test/manual_utterance",
        json={
            "speaker": "resident",
            "language": "en",
            "text": "I am homeless tonight and need emergency accommodation.",
            "resident_language": "bn",
        },
    )

    assert response.status_code == 200
    events = response.json()
    event_types = [event["type"] for event in events]
    assert event_types[0] == "session_started"
    assert "final_utterance" in event_types
    assert "policy_card" in event_types
    assert "question_prompt" in event_types
    assert "record_snapshot" in event_types

    record_response = client.get("/session/manual-test/record.json")

    assert record_response.status_code == 200
    record = record_response.json()
    assert record["session_id"] == "manual-test"
    assert record["policy_citations"]
    assert record["question_prompts"]
    assert record["bilingual_transcript"][0]["speaker"] == "resident"


def test_manual_caseworker_turn_extracts_commitment() -> None:
    MANUAL_SESSIONS.clear()
    client = TestClient(app)

    response = client.post(
        "/session/manual-commitment/manual_utterance",
        json={
            "speaker": "caseworker",
            "language": "en",
            "text": "I will call you today after checking the emergency accommodation options.",
        },
    )

    assert response.status_code == 200
    events = response.json()
    commitment = next(event for event in events if event["type"] == "commitment")
    assert commitment["owner"] == "caseworker"
    assert commitment["due"] == "today"
