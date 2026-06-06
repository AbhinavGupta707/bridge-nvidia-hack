from __future__ import annotations

import hashlib
from dataclasses import dataclass

from bridge.bus.events import FinalUtteranceEvent, PolicyCardEvent
from bridge.rag.corpus import SENTENCE_RE, clean_text, tokenize
from bridge.rag.retriever import SearchResult


@dataclass(frozen=True)
class PolicyCardSettings:
    min_confidence: float = 0.48
    max_span_chars: int = 420


def build_policy_card(
    *,
    session_id: str,
    turn_id: str,
    query: str,
    result: SearchResult,
    settings: PolicyCardSettings | None = None,
) -> PolicyCardEvent | None:
    settings = settings or PolicyCardSettings()
    chunk = result.chunk
    if result.confidence < settings.min_confidence:
        return None
    if not all([chunk.source_title, chunk.source_url, chunk.authority, chunk.content]):
        return None

    claim = select_claim_sentence(query, chunk.content)
    if not claim:
        return None
    source_span = source_span_for_claim(chunk.content, claim, max_chars=settings.max_span_chars)
    if not source_span:
        return None

    card_id = hashlib.sha1(
        f"{session_id}:{turn_id}:{chunk.chunk_id}:{claim}".encode("utf-8")
    ).hexdigest()[:14]
    title = title_for_claim(chunk.source_title, claim)
    return PolicyCardEvent(
        session_id=session_id,
        card_id=f"policy-{card_id}",
        title=title,
        claim=claim,
        source_title=chunk.source_title,
        source_url=chunk.source_url,
        source_span=source_span,
        authority=chunk.authority,
        confidence=result.confidence,
        trigger_turn_ids=[turn_id],
    )


def build_policy_card_for_utterance(
    event: FinalUtteranceEvent,
    result: SearchResult,
    settings: PolicyCardSettings | None = None,
) -> PolicyCardEvent | None:
    query = event.translated_text or event.text
    return build_policy_card(
        session_id=event.session_id,
        turn_id=event.turn_id,
        query=query,
        result=result,
        settings=settings,
    )


def select_claim_sentence(query: str, content: str) -> str | None:
    query_terms = set(tokenize(query))
    best_sentence = ""
    best_score = 0
    for sentence in SENTENCE_RE.split(content):
        sentence = clean_text(sentence)
        sentence_terms = set(tokenize(sentence))
        if len(sentence_terms) < 5:
            continue
        overlap = len(query_terms & sentence_terms)
        policy_bonus = sum(
            1
            for term in (
                "homeless",
                "homelessness",
                "accommodation",
                "duty",
                "eligible",
                "application",
                "assessment",
                "register",
                "review",
            )
            if term in sentence_terms
        )
        score = overlap + policy_bonus
        if score > best_score:
            best_sentence = sentence
            best_score = score
    if best_score < 2:
        return None
    return best_sentence[:480].strip()


def source_span_for_claim(content: str, claim: str, *, max_chars: int) -> str:
    start = content.find(claim)
    if start < 0:
        return claim[:max_chars].strip()
    left = max(0, start - 80)
    right = min(len(content), start + len(claim) + 80)
    return clean_text(content[left:right])[:max_chars].strip()


def title_for_claim(source_title: str, claim: str) -> str:
    lower_claim = claim.lower()
    if "interim accommodation" in lower_claim or "emergency" in lower_claim:
        return "Emergency interim accommodation"
    if "prevention" in lower_claim:
        return "Homelessness prevention duty"
    if "relief" in lower_claim:
        return "Homelessness relief duty"
    if "housing register" in lower_claim or "allocation" in lower_claim:
        return "Housing register eligibility"
    return source_title
