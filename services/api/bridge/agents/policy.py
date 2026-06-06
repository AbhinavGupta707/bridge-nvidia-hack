from __future__ import annotations

from pathlib import Path

from bridge.bus.events import AgentStatusEvent, FinalUtteranceEvent, PolicyCardEvent
from bridge.rag import LocalHybridRetriever, PolicyCardSettings, build_policy_card_for_utterance
from bridge.rag.corpus import tokenize


ROOT = Path(__file__).resolve().parents[4]
DEFAULT_INDEX_DIR = ROOT / "data" / "processed"
POLICY_TRIGGER_TERMS = {
    "accommodation",
    "application",
    "arrears",
    "assessment",
    "council",
    "duty",
    "emergency",
    "evict",
    "eviction",
    "homeless",
    "homelessness",
    "housing",
    "landlord",
    "notice",
    "priority",
    "prevention",
    "register",
    "relief",
    "rent",
    "rough",
    "sleep",
    "sleeping",
    "temporary",
    "threatened",
}


class PolicyAgent:
    """Cited local policy retrieval over the Bridge corpus.

    The agent intentionally has no generative policy mode. It only emits a
    policy_card when retrieval returns a high-confidence chunk with source
    metadata and a claim sentence selected from that cited chunk.
    """

    def __init__(
        self,
        retriever: LocalHybridRetriever,
        *,
        settings: PolicyCardSettings | None = None,
        max_cards_per_turn: int = 1,
    ) -> None:
        self.retriever = retriever
        self.settings = settings or PolicyCardSettings()
        self.max_cards_per_turn = max_cards_per_turn

    @classmethod
    def from_index_dir(
        cls,
        index_dir: Path = DEFAULT_INDEX_DIR,
        *,
        settings: PolicyCardSettings | None = None,
    ) -> PolicyAgent:
        return cls(LocalHybridRetriever.from_index_dir(index_dir), settings=settings)

    def status(self, session_id: str, status: str, message: str | None = None) -> AgentStatusEvent:
        return AgentStatusEvent(
            session_id=session_id,
            agent="policy",
            status=status,  # type: ignore[arg-type]
            message=message,
        )

    def handle_final_utterance(self, event: FinalUtteranceEvent) -> list[PolicyCardEvent]:
        if event.speaker == "system":
            return []
        query = event.translated_text or event.text
        if not is_policy_relevant(query):
            return []
        results = self.retriever.search(
            query,
            top_k=max(3, self.max_cards_per_turn * 3),
            min_confidence=max(0.34, self.settings.min_confidence - 0.14),
        )

        cards: list[PolicyCardEvent] = []
        seen_sources: set[str] = set()
        for result in results:
            if result.chunk.source_id in seen_sources:
                continue
            card = build_policy_card_for_utterance(event, result, self.settings)
            if card is None:
                continue
            cards.append(card)
            seen_sources.add(result.chunk.source_id)
            if len(cards) >= self.max_cards_per_turn:
                break
        return cards


def policy_cards_for_utterance(
    event: FinalUtteranceEvent,
    *,
    index_dir: Path = DEFAULT_INDEX_DIR,
    min_confidence: float = 0.48,
) -> list[PolicyCardEvent]:
    agent = PolicyAgent.from_index_dir(
        index_dir,
        settings=PolicyCardSettings(min_confidence=min_confidence),
    )
    return agent.handle_final_utterance(event)


def is_policy_relevant(text: str) -> bool:
    terms = set(tokenize(text))
    return bool(terms & POLICY_TRIGGER_TERMS)
