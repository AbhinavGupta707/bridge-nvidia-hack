from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from bridge.rag.corpus import CorpusChunk, cosine, hashed_char_ngrams, load_index, tokenize


QUERY_EXPANSIONS = {
    "homeless": {"homelessness", "rough", "sleeping", "accommodation"},
    "homelessness": {"homeless", "rough", "sleeping", "accommodation"},
    "sleep": {"rough", "sleeping", "accommodation", "tonight"},
    "tonight": {"emergency", "interim", "accommodation"},
    "emergency": {"interim", "priority", "need", "accommodation"},
    "evict": {"eviction", "notice", "landlord", "prevention"},
    "eviction": {"evict", "notice", "landlord", "prevention"},
    "rent": {"arrears", "deposit", "benefit"},
    "domestic": {"abuse", "violence", "refuge"},
    "register": {"allocation", "housing", "application"},
    "council": {"local", "authority", "housing"},
}

PHRASE_BONUSES = (
    "priority need",
    "interim accommodation",
    "emergency interim accommodation",
    "relief duty",
    "prevention duty",
    "temporary accommodation",
    "housing register",
    "rent arrears",
    "domestic abuse",
    "personalised housing plan",
)


@dataclass(frozen=True)
class SearchResult:
    chunk: CorpusChunk
    score: float
    confidence: float
    keyword_score: float
    vector_score: float
    phrase_score: float


class LocalHybridRetriever:
    def __init__(self, chunks: list[CorpusChunk]) -> None:
        self.chunks = chunks
        self.chunk_terms = [Counter(tokenize(chunk.content)) for chunk in chunks]
        self.chunk_vectors = [hashed_char_ngrams(chunk.content) for chunk in chunks]
        self.avg_len = (
            sum(sum(counter.values()) for counter in self.chunk_terms) / len(self.chunk_terms)
            if self.chunk_terms
            else 1.0
        )
        self.doc_freq: Counter[str] = Counter()
        for counter in self.chunk_terms:
            self.doc_freq.update(counter.keys())

    @classmethod
    def from_index_dir(cls, index_dir: Path) -> LocalHybridRetriever:
        return cls(load_index(index_dir))

    def search(self, query: str, *, top_k: int = 4, min_confidence: float = 0.36) -> list[SearchResult]:
        query_terms = expanded_query_terms(query)
        if not query_terms or not self.chunks:
            return []

        query_vector = hashed_char_ngrams(" ".join(query_terms))
        raw_results: list[SearchResult] = []
        for index, chunk in enumerate(self.chunks):
            keyword = self._bm25(query_terms, self.chunk_terms[index])
            vector = cosine(query_vector, self.chunk_vectors[index])
            phrase = phrase_bonus(query, chunk.content)
            priority = 0.12 if chunk.priority == "p0" else 0.0
            score = keyword + (1.8 * vector) + phrase + priority
            confidence = confidence_from_score(score, keyword, vector, phrase)
            if confidence >= min_confidence:
                raw_results.append(
                    SearchResult(
                        chunk=chunk,
                        score=score,
                        confidence=confidence,
                        keyword_score=keyword,
                        vector_score=vector,
                        phrase_score=phrase,
                    )
                )
        return sorted(raw_results, key=lambda result: result.score, reverse=True)[:top_k]

    def _bm25(self, query_terms: list[str], terms: Counter[str]) -> float:
        if not terms:
            return 0.0
        k1 = 1.2
        b = 0.75
        doc_len = sum(terms.values())
        score = 0.0
        total_docs = max(len(self.chunks), 1)
        for term in query_terms:
            freq = terms.get(term, 0)
            if not freq:
                continue
            idf = math.log(1 + (total_docs - self.doc_freq[term] + 0.5) / (self.doc_freq[term] + 0.5))
            denom = freq + k1 * (1 - b + b * doc_len / max(self.avg_len, 1))
            score += idf * ((freq * (k1 + 1)) / denom)
        return score


def expanded_query_terms(query: str) -> list[str]:
    terms = tokenize(query)
    expanded: list[str] = []
    for term in terms:
        expanded.append(term)
        expanded.extend(sorted(QUERY_EXPANSIONS.get(term, set())))
    return expanded


def phrase_bonus(query: str, content: str) -> float:
    query_text = query.lower()
    content_text = content.lower()
    score = 0.0
    for phrase in PHRASE_BONUSES:
        phrase_terms = phrase.split()
        in_query = any(term in query_text for term in phrase_terms)
        if in_query and phrase in content_text:
            score += 0.42
    if re.search(r"\b(tonight|now|today)\b", query_text) and "interim accommodation" in content_text:
        score += 0.5
    return min(score, 2.0)


def confidence_from_score(score: float, keyword: float, vector: float, phrase: float) -> float:
    if keyword <= 0 and phrase <= 0:
        return 0.0
    confidence = 0.22 + min(score / 8.0, 0.55) + min(vector * 0.16, 0.12)
    if phrase > 0:
        confidence += min(phrase * 0.08, 0.12)
    return round(min(confidence, 0.95), 3)
