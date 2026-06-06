from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from bridge.bus.events import BridgeEvent


SAFETY_DISCLAIMER = (
    "Bridge is not legal advice, clinical advice, or a replacement for a qualified "
    "interpreter in legally binding decisions. It records the conversation, surfaces "
    "cited public information, and helps residents prepare follow-up questions."
)


class BridgeRecord(TypedDict):
    record_id: str
    session_id: str
    session_summary: str
    participants: list[dict[str, str]]
    bilingual_transcript: list[dict[str, Any]]
    policy_citations: list[dict[str, Any]]
    question_prompts: list[dict[str, Any]]
    commitments: list[dict[str, Any]]
    next_steps: list[dict[str, Any]]
    safety_disclaimer: str
    source_integrity: dict[str, Any]
    generated_from_event_count: int
    warnings: NotRequired[list[str]]


def build_record(events: list[BridgeEvent | dict[str, Any]]) -> BridgeRecord:
    event_dicts = [_event_dict(event) for event in events]
    session_id = _session_id(event_dicts)
    transcript = _transcript(event_dicts)
    raw_policy_citations = _policy_citations(event_dicts)
    policy_citations = [
        citation for citation in raw_policy_citations if _has_source_metadata(citation)
    ]
    question_prompts = _question_prompts(event_dicts, policy_citations)
    commitments = _commitments(event_dicts)
    next_steps = _next_steps(question_prompts, commitments)

    record: BridgeRecord = {
        "record_id": f"{session_id}-record",
        "session_id": session_id,
        "session_summary": _session_summary(transcript, policy_citations, question_prompts),
        "participants": _participants(event_dicts, transcript),
        "bilingual_transcript": transcript,
        "policy_citations": policy_citations,
        "question_prompts": question_prompts,
        "commitments": commitments,
        "next_steps": next_steps,
        "safety_disclaimer": SAFETY_DISCLAIMER,
        "source_integrity": {
            "policy_claims_total": len(policy_citations),
            "policy_claims_with_source_metadata": len(policy_citations),
            "policy_cards_skipped_missing_source_metadata": [
                citation["card_id"]
                for citation in raw_policy_citations
                if not _has_source_metadata(citation)
            ],
            "required_source_fields": [
                "source_title",
                "source_url",
                "source_span",
                "authority",
            ],
        },
        "generated_from_event_count": len(event_dicts),
    }
    missing_sources = [
        citation["card_id"] for citation in raw_policy_citations if not _has_source_metadata(citation)
    ]
    if missing_sources:
        record["warnings"] = [
            "Policy cards missing source metadata were kept out of narrative summary: "
            + ", ".join(missing_sources)
        ]
    return record


def render_record_html(record: BridgeRecord) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{_e(record["record_id"])} | Bridge record</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #1f2933; line-height: 1.5; }}
    h1, h2 {{ color: #111827; }}
    section {{ border-top: 1px solid #d9e2ec; padding-top: 16px; margin-top: 22px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #d9e2ec; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f5f7fa; }}
    .claim {{ margin: 0 0 12px; padding: 10px; border-left: 4px solid #2563eb; background: #f8fafc; }}
    .muted {{ color: #52606d; }}
    .disclaimer {{ background: #fff7ed; border: 1px solid #fed7aa; padding: 12px; }}
  </style>
</head>
<body>
  <h1>Bridge Appointment Record</h1>
  <p class="muted">Record ID: {_e(record["record_id"])} | Session: {_e(record["session_id"])}</p>
  <section>
    <h2>Session Summary</h2>
    <p>{_e(record["session_summary"])}</p>
  </section>
  <section>
    <h2>Participants</h2>
    {_items(record["participants"], _participant_item)}
  </section>
  <section>
    <h2>Bilingual Transcript</h2>
    {_transcript_table(record["bilingual_transcript"])}
  </section>
  <section>
    <h2>Policy Citations</h2>
    {_items(record["policy_citations"], _policy_item)}
  </section>
  <section>
    <h2>Question Prompts</h2>
    {_items(record["question_prompts"], _question_item)}
  </section>
  <section>
    <h2>Commitments</h2>
    {_items(record["commitments"], _commitment_item)}
  </section>
  <section>
    <h2>Next Steps</h2>
    {_items(record["next_steps"], _next_step_item)}
  </section>
  <section>
    <h2>Safety Disclaimer</h2>
    <p class="disclaimer">{_e(record["safety_disclaimer"])}</p>
  </section>
</body>
</html>
"""


def write_record_artifacts(record: BridgeRecord, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{record['record_id']}.json"
    html_path = output_dir / f"{record['record_id']}.html"
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_record_html(record), encoding="utf-8")
    return json_path, html_path


def _event_dict(event: BridgeEvent | dict[str, Any]) -> dict[str, Any]:
    if hasattr(event, "model_dump"):
        return event.model_dump()
    return dict(event)


def _session_id(events: list[dict[str, Any]]) -> str:
    for event in events:
        if event.get("session_id"):
            return str(event["session_id"])
    return "demo-001"


def _transcript(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "final_utterance":
            continue
        rows.append(
            {
                "turn_id": event.get("turn_id"),
                "speaker": event.get("speaker"),
                "language": event.get("language"),
                "original_text": event.get("text"),
                "translated_text": event.get("translated_text"),
                "start_ms": event.get("start_ms"),
                "end_ms": event.get("end_ms"),
                "confidence": event.get("confidence"),
            }
        )
    return rows


def _policy_citations(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "policy_card":
            continue
        citations.append(
            {
                "card_id": event.get("card_id"),
                "title": event.get("title"),
                "claim": event.get("claim"),
                "source_title": event.get("source_title"),
                "source_url": event.get("source_url"),
                "source_span": event.get("source_span"),
                "authority": event.get("authority"),
                "confidence": event.get("confidence"),
                "trigger_turn_ids": event.get("trigger_turn_ids", []),
            }
        )
    return citations


def _question_prompts(
    events: list[dict[str, Any]],
    policy_citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "question_prompt":
            continue
        trigger_turn_ids = event.get("trigger_turn_ids", [])
        prompts.append(
            {
                "prompt_id": event.get("prompt_id"),
                "language": event.get("language"),
                "text": event.get("text"),
                "english_text": event.get("english_text"),
                "trigger_turn_ids": trigger_turn_ids,
                "related_policy_sources": _related_policy_sources(trigger_turn_ids, policy_citations),
            }
        )
    return prompts


def _related_policy_sources(
    trigger_turn_ids: list[str],
    policy_citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for citation in policy_citations:
        if not set(trigger_turn_ids).intersection(citation.get("trigger_turn_ids", [])):
            continue
        sources.append(
            {
                "card_id": citation["card_id"],
                "source_title": citation["source_title"],
                "source_url": citation["source_url"],
                "source_span": citation["source_span"],
                "authority": citation["authority"],
            }
        )
    return sources


def _commitments(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    explicit = [
        {
            "commitment_id": event.get("commitment_id"),
            "owner": event.get("owner"),
            "text": event.get("text"),
            "due": event.get("due"),
            "source_turn_ids": event.get("trigger_turn_ids", []),
        }
        for event in events
        if event.get("type") == "commitment"
    ]
    if explicit:
        return explicit

    commitments: list[dict[str, Any]] = []
    for event in events:
        if event.get("type") != "final_utterance" or event.get("speaker") != "caseworker":
            continue
        text = str(event.get("text", ""))
        if re.search(r"\b(i|we)\s+will\b|\bwill\s+(send|call|check|book|review|contact)\b", text, re.I):
            commitments.append(
                {
                    "commitment_id": f"commitment-{len(commitments) + 1:03d}",
                    "owner": "caseworker",
                    "text": text,
                    "due": _due_hint(text),
                    "source_turn_ids": [event.get("turn_id")],
                }
            )
    return commitments


def _next_steps(
    question_prompts: list[dict[str, Any]],
    commitments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for commitment in commitments:
        steps.append(
            {
                "owner": commitment.get("owner", "caseworker"),
                "text": commitment.get("text"),
                "source": "commitment",
                "source_ids": commitment.get("source_turn_ids", []),
            }
        )
    for prompt in question_prompts:
        steps.append(
            {
                "owner": "resident",
                "text": prompt.get("english_text"),
                "source": "question_prompt",
                "source_ids": [prompt.get("prompt_id")],
            }
        )
    if not steps:
        steps.append(
            {
                "owner": "resident",
                "text": "Keep this record and ask for any decision or follow-up action in writing.",
                "source": "record_default",
                "source_ids": [],
            }
        )
    return steps


def _participants(
    events: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
) -> list[dict[str, str]]:
    session_started = next((event for event in events if event.get("type") == "session_started"), {})
    speakers = sorted({str(row["speaker"]) for row in transcript if row.get("speaker")})
    participants = []
    for speaker in speakers:
        language = (
            session_started.get("resident_language")
            if speaker == "resident"
            else session_started.get("caseworker_language", "en")
        )
        participants.append({"role": speaker, "language": str(language or "unknown")})
    return participants


def _session_summary(
    transcript: list[dict[str, Any]],
    policy_citations: list[dict[str, Any]],
    question_prompts: list[dict[str, Any]],
) -> str:
    resident_turns = [row for row in transcript if row.get("speaker") == "resident"]
    caseworker_turns = [row for row in transcript if row.get("speaker") == "caseworker"]
    return (
        f"The record captures {len(transcript)} final utterances: "
        f"{len(resident_turns)} from the resident and {len(caseworker_turns)} from the caseworker. "
        f"Bridge surfaced {len(policy_citations)} cited policy card(s) and "
        f"{len(question_prompts)} resident question prompt(s)."
    )


def _has_source_metadata(citation: dict[str, Any]) -> bool:
    return all(citation.get(field) for field in ("source_title", "source_url", "source_span", "authority"))


def _due_hint(text: str) -> str | None:
    lowered = text.lower()
    if "today" in lowered or "tonight" in lowered:
        return "today"
    if "tomorrow" in lowered:
        return "tomorrow"
    return None


def _items(items: list[dict[str, Any]], formatter: Any) -> str:
    if not items:
        return "<p class=\"muted\">None recorded.</p>"
    return "<ul>" + "".join(formatter(item) for item in items) + "</ul>"


def _participant_item(item: dict[str, Any]) -> str:
    return f"<li>{_e(item.get('role'))}: {_e(item.get('language'))}</li>"


def _policy_item(item: dict[str, Any]) -> str:
    return (
        "<li class=\"claim\">"
        f"<strong>{_e(item.get('title'))}</strong><br>"
        f"Claim: {_e(item.get('claim'))}<br>"
        f"Source: <a href=\"{_e(item.get('source_url'))}\">{_e(item.get('source_title'))}</a>, "
        f"{_e(item.get('authority'))}<br>"
        f"Source span: {_e(item.get('source_span'))}<br>"
        f"Trigger turns: {_e(', '.join(item.get('trigger_turn_ids', [])))}"
        "</li>"
    )


def _question_item(item: dict[str, Any]) -> str:
    sources = item.get("related_policy_sources", [])
    source_text = "No related policy source."
    if sources:
        source_text = "; ".join(
            f"{source.get('source_title')} ({source.get('source_url')})" for source in sources
        )
    return (
        "<li>"
        f"{_e(item.get('english_text'))}<br>"
        f"<span class=\"muted\">Resident language: {_e(item.get('text'))}</span><br>"
        f"<span class=\"muted\">Related sources: {_e(source_text)}</span>"
        "</li>"
    )


def _commitment_item(item: dict[str, Any]) -> str:
    due = f" Due: {_e(item.get('due'))}." if item.get("due") else ""
    return f"<li>{_e(item.get('owner'))}: {_e(item.get('text'))}.{due}</li>"


def _next_step_item(item: dict[str, Any]) -> str:
    return f"<li>{_e(item.get('owner'))}: {_e(item.get('text'))}</li>"


def _transcript_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class=\"muted\">No transcript recorded.</p>"
    body = "".join(
        "<tr>"
        f"<td>{_e(row.get('turn_id'))}</td>"
        f"<td>{_e(row.get('speaker'))}</td>"
        f"<td>{_e(row.get('language'))}</td>"
        f"<td>{_e(row.get('original_text'))}</td>"
        f"<td>{_e(row.get('translated_text'))}</td>"
        "</tr>"
        for row in rows
    )
    return (
        "<table><thead><tr><th>Turn</th><th>Speaker</th><th>Language</th>"
        "<th>Original</th><th>Translation</th></tr></thead><tbody>"
        f"{body}</tbody></table>"
    )


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)
