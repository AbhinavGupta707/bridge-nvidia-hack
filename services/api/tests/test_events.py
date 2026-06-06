from bridge.bus.events import (
    AgentStatusEvent,
    PartialTranscriptEvent,
    PolicyCardEvent,
    TranslationEvent,
)


def test_agent_status_event_type_defaults() -> None:
    event = AgentStatusEvent(
        session_id="demo-001",
        agent="interpreter",
        status="idle",
    )

    assert event.type == "agent_status"


def test_policy_card_requires_citation_metadata() -> None:
    event = PolicyCardEvent(
        session_id="demo-001",
        card_id="policy-001",
        title="Interim accommodation",
        claim="A cited policy claim.",
        source_title="Rights of people who are homeless",
        source_url="https://www.cityoflondon.gov.uk/example",
        source_span="The relevant source span.",
        authority="City of London",
        confidence=0.8,
        trigger_turn_ids=["t-001"],
    )

    assert event.source_url.startswith("https://")
    assert event.trigger_turn_ids == ["t-001"]


def test_partial_transcript_event_type_defaults() -> None:
    event = PartialTranscriptEvent(
        session_id="demo-001",
        turn_id="t-001",
        speaker="resident",
        language="bn",
        text="partial text",
        stability=0.7,
    )

    assert event.type == "partial_transcript"


def test_translation_event_type_defaults() -> None:
    event = TranslationEvent(
        session_id="demo-001",
        turn_id="t-001",
        speaker="resident",
        source_language="bn",
        target_language="en",
        source_text="source",
        translated_text="translated",
    )

    assert event.type == "translation"
