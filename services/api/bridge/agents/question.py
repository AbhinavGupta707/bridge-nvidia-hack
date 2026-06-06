"""Checklist-based Question Agent.

This agent intentionally avoids legal conclusions. It watches the shared event
log for housing/homelessness signals and emits a small number of resident-led
questions that help clarify the appointment record.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bridge.bus.events import BridgeEvent, QuestionPromptEvent


MAX_PROMPTS_PER_PASS = 2


@dataclass(frozen=True)
class QuestionRule:
    prompt_id: str
    english_text: str
    translations: dict[str, str]
    keywords: tuple[str, ...]
    policy_terms: tuple[str, ...] = ()

    def render(self, language: str) -> tuple[str, str]:
        return self.translations.get(language, self.english_text), self.english_text


HOUSING_CHECKLIST: tuple[QuestionRule, ...] = (
    QuestionRule(
        prompt_id="housing-tonight",
        english_text="Ask what safe option is available for tonight while they review your situation.",
        translations={
            "bn": "আপনার পরিস্থিতি দেখা পর্যন্ত আজ রাতে নিরাপদে থাকার কী ব্যবস্থা আছে তা জিজ্ঞেস করুন।",
        },
        keywords=("sleep tonight", "tonight", "nowhere", "homeless", "leave where i am staying"),
        policy_terms=("interim accommodation", "emergency accommodation", "relief duty"),
    ),
    QuestionRule(
        prompt_id="housing-written-decision",
        english_text="Ask for any decision, reason, and next action in writing before you leave.",
        translations={
            "bn": "চলে যাওয়ার আগে যেকোনো সিদ্ধান্ত, কারণ এবং পরের পদক্ষেপ লিখিতভাবে চাইতে বলুন।",
        },
        keywords=("decision", "letter", "writing", "written", "refuse", "review"),
        policy_terms=("written decision", "notification", "review rights"),
    ),
    QuestionRule(
        prompt_id="housing-documents",
        english_text="Ask which documents they need today and whether you can send missing evidence later.",
        translations={
            "bn": "আজ কোন কাগজ দরকার এবং বাকি প্রমাণ পরে পাঠানো যাবে কি না জিজ্ঞেস করুন।",
        },
        keywords=("documents", "passport", "evidence", "proof", "bank", "tenancy", "notice"),
    ),
    QuestionRule(
        prompt_id="housing-children-health-risk",
        english_text="Ask them to record any children, pregnancy, disability, illness, or safety risk.",
        translations={
            "bn": "শিশু, গর্ভাবস্থা, প্রতিবন্ধকতা, অসুস্থতা বা নিরাপত্তার ঝুঁকি নথিভুক্ত করতে বলুন।",
        },
        keywords=("child", "children", "pregnant", "disability", "ill", "medicine", "unsafe", "violence"),
    ),
    QuestionRule(
        prompt_id="housing-contact-details",
        english_text="Ask who will contact you next, when, and what number or email they will use.",
        translations={
            "bn": "পরের যোগাযোগ কে করবে, কখন করবে এবং কোন ফোন বা ইমেইল ব্যবহার করবে তা জিজ্ঞেস করুন।",
        },
        keywords=("call", "contact", "email", "phone", "tomorrow", "next"),
    ),
)


@dataclass(frozen=True)
class QuestionAgent:
    resident_language: str = "bn"
    rules: tuple[QuestionRule, ...] = HOUSING_CHECKLIST
    max_prompts: int = MAX_PROMPTS_PER_PASS

    def suggest(self, events: list[BridgeEvent | dict[str, Any]]) -> list[QuestionPromptEvent]:
        emitted_prompt_ids = {
            event_dict["prompt_id"]
            for event_dict in map(_event_dict, events)
            if event_dict.get("type") == "question_prompt" and event_dict.get("prompt_id")
        }
        conversation_text = _conversation_text(events)
        policy_text_by_turn = _policy_text_by_turn(events)

        prompts: list[QuestionPromptEvent] = []
        for rule in self.rules:
            if rule.prompt_id in emitted_prompt_ids:
                continue

            trigger_turn_ids = _matching_turn_ids(rule, events, policy_text_by_turn)
            if not trigger_turn_ids and not _contains_any(conversation_text, rule.keywords):
                continue

            text, english_text = rule.render(self.resident_language)
            prompts.append(
                QuestionPromptEvent(
                    session_id=_session_id(events),
                    prompt_id=rule.prompt_id,
                    language=self.resident_language,
                    text=text,
                    english_text=english_text,
                    trigger_turn_ids=trigger_turn_ids or _recent_turn_ids(events),
                )
            )
            if len(prompts) >= self.max_prompts:
                break

        return prompts


def suggest_question_prompts(
    events: list[BridgeEvent | dict[str, Any]],
    *,
    resident_language: str = "bn",
    max_prompts: int = MAX_PROMPTS_PER_PASS,
) -> list[QuestionPromptEvent]:
    return QuestionAgent(resident_language=resident_language, max_prompts=max_prompts).suggest(events)


def _event_dict(event: BridgeEvent | dict[str, Any]) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump()
    return dict(event)


def _session_id(events: list[BridgeEvent | dict[str, Any]]) -> str:
    for event in events:
        session_id = _event_dict(event).get("session_id")
        if session_id:
            return str(session_id)
    return "demo-001"


def _conversation_text(events: list[BridgeEvent | dict[str, Any]]) -> str:
    parts: list[str] = []
    for event in map(_event_dict, events):
        if event.get("type") == "final_utterance":
            parts.extend([str(event.get("text", "")), str(event.get("translated_text", ""))])
        if event.get("type") == "policy_card":
            parts.extend([str(event.get("title", "")), str(event.get("claim", ""))])
    return " ".join(parts).lower()


def _policy_text_by_turn(events: list[BridgeEvent | dict[str, Any]]) -> dict[str, str]:
    policy_text: dict[str, list[str]] = {}
    for event in map(_event_dict, events):
        if event.get("type") != "policy_card":
            continue
        text = f"{event.get('title', '')} {event.get('claim', '')}".lower()
        for turn_id in event.get("trigger_turn_ids", []):
            policy_text.setdefault(turn_id, []).append(text)
    return {turn_id: " ".join(parts) for turn_id, parts in policy_text.items()}


def _matching_turn_ids(
    rule: QuestionRule,
    events: list[BridgeEvent | dict[str, Any]],
    policy_text_by_turn: dict[str, str],
) -> list[str]:
    turn_ids: list[str] = []
    for event in map(_event_dict, events):
        if event.get("type") != "final_utterance":
            continue
        turn_id = str(event.get("turn_id", ""))
        utterance_text = f"{event.get('text', '')} {event.get('translated_text', '')}".lower()
        policy_text = policy_text_by_turn.get(turn_id, "")
        if _contains_any(utterance_text, rule.keywords) or _contains_any(policy_text, rule.policy_terms):
            turn_ids.append(turn_id)
    return turn_ids


def _recent_turn_ids(events: list[BridgeEvent | dict[str, Any]]) -> list[str]:
    turn_ids = [
        str(event.get("turn_id"))
        for event in map(_event_dict, events)
        if event.get("type") == "final_utterance" and event.get("turn_id")
    ]
    return turn_ids[-2:]


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)
