"""Local retrieval and citation helpers."""

from bridge.rag.cards import (
    PolicyCardSettings,
    build_policy_card,
    build_policy_card_for_utterance,
)
from bridge.rag.corpus import CorpusChunk, IngestReport, build_corpus, load_index, load_sources
from bridge.rag.retriever import LocalHybridRetriever, SearchResult

__all__ = [
    "CorpusChunk",
    "IngestReport",
    "LocalHybridRetriever",
    "PolicyCardSettings",
    "SearchResult",
    "build_corpus",
    "build_policy_card",
    "build_policy_card_for_utterance",
    "load_index",
    "load_sources",
]
