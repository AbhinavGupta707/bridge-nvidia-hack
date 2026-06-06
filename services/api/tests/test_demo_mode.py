from bridge.config import load_settings
from bridge.demo.runner import build_demo_events, dump_events


def test_demo_mode_emits_required_demo_events(monkeypatch) -> None:
    monkeypatch.setenv("BRIDGE_MODE", "demo")
    monkeypatch.setenv("ASR_PROVIDER", "demo")
    monkeypatch.setenv("TTS_PROVIDER", "demo")
    monkeypatch.setenv("LLM_PROVIDER", "demo")
    monkeypatch.setenv("ALLOW_CLOUD", "false")

    settings = load_settings()
    events = dump_events(build_demo_events(settings, session_id="demo-test"))
    event_types = {event["type"] for event in events}

    assert events[0]["type"] == "session_started"
    assert "final_utterance" in event_types
    assert "translation" in event_types
    assert "policy_card" in event_types
    assert "question_prompt" in event_types
    assert "commitment" in event_types
    assert "record_snapshot" in event_types
    assert events[-1]["type"] == "session_ended"
    first_policy = next(event for event in events if event["type"] == "policy_card")
    assert first_policy["authority"] == "City of London Corporation"
    record = next(event for event in events if event["type"] == "record_snapshot")
    assert record["html_path"] == "/session/demo-test/record.html"
    assert record["json_path"] == "/session/demo-test/record.json"


def test_demo_mode_is_deterministic_and_cloud_off_by_default(monkeypatch) -> None:
    monkeypatch.delenv("BRIDGE_MODE", raising=False)
    monkeypatch.delenv("ASR_PROVIDER", raising=False)
    monkeypatch.delenv("TTS_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ALLOW_CLOUD", raising=False)

    settings = load_settings()
    first = dump_events(build_demo_events(settings, session_id="demo-test"))
    second = dump_events(build_demo_events(settings, session_id="demo-test"))

    assert settings.deterministic_demo is True
    assert first == second
    assert first[0]["allow_cloud"] is False
