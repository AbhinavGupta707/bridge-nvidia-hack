from pathlib import Path

from bridge.agents.policy import PolicyAgent
from bridge.bus.events import FinalUtteranceEvent
from bridge.rag import LocalHybridRetriever, PolicyCardSettings
from bridge.rag.corpus import build_corpus


ROOT = Path(__file__).resolve().parents[3]


def test_policy_agent_emits_cited_card_from_seed_corpus() -> None:
    report = build_corpus(ROOT / "data" / "sources.yml", fetch=False)
    retriever = LocalHybridRetriever(report.chunks)
    agent = PolicyAgent(
        retriever,
        settings=PolicyCardSettings(min_confidence=0.42),
    )

    cards = agent.handle_final_utterance(
        FinalUtteranceEvent(
            session_id="demo-001",
            turn_id="t-004",
            speaker="resident",
            language="en",
            text="I am homeless tonight and need emergency accommodation.",
            translated_text=None,
            confidence=0.91,
        )
    )

    assert cards
    card = cards[0]
    assert card.type == "policy_card"
    assert card.source_url.startswith("https://")
    assert card.source_span
    assert card.authority
    assert card.trigger_turn_ids == ["t-004"]


def test_policy_agent_suppresses_low_confidence_uncited_topics() -> None:
    report = build_corpus(ROOT / "data" / "sources.yml", fetch=False)
    retriever = LocalHybridRetriever(report.chunks)
    agent = PolicyAgent(
        retriever,
        settings=PolicyCardSettings(min_confidence=0.5),
    )

    cards = agent.handle_final_utterance(
        FinalUtteranceEvent(
            session_id="demo-001",
            turn_id="t-009",
            speaker="resident",
            language="en",
            text="What time does the library open on Sunday?",
        )
    )

    assert cards == []
