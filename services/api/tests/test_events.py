from bridge.bus.events import AgentStatusEvent, PolicyCardEvent


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

