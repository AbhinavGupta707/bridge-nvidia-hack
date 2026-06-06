from bridge.agents.question import QuestionAgent
from bridge.agents.record import RecordAgent
from bridge.bus.events import FinalUtteranceEvent, PolicyCardEvent, QuestionPromptEvent


def _housing_events():
    return [
        FinalUtteranceEvent(
            session_id="demo-001",
            turn_id="t-001",
            speaker="resident",
            language="bn",
            text="আজ রাতে থাকার জায়গা নেই।",
            translated_text="I have nowhere safe to sleep tonight.",
        ),
        PolicyCardEvent(
            session_id="demo-001",
            card_id="policy-001",
            title="Interim accommodation while inquiries are made",
            claim="Where there is reason to believe an applicant may be homeless, eligible, and in priority need, interim accommodation can be considered while inquiries continue.",
            source_title="Homelessness Code of Guidance for Local Authorities",
            source_url="https://www.gov.uk/guidance/homelessness-code-of-guidance-for-local-authorities",
            source_span="Chapter 15: accommodation duties pending inquiries and decisions.",
            authority="DLUHC",
            confidence=0.84,
            trigger_turn_ids=["t-001"],
        ),
    ]


def test_question_agent_emits_conservative_housing_prompt() -> None:
    prompts = QuestionAgent(resident_language="bn").suggest(_housing_events())

    assert len(prompts) == 1
    assert prompts[0].prompt_id == "housing-tonight"
    assert prompts[0].english_text.startswith("Ask what safe option")
    assert prompts[0].trigger_turn_ids == ["t-001"]


def test_question_agent_respects_existing_prompt_cooldown() -> None:
    events = [
        *_housing_events(),
        QuestionPromptEvent(
            session_id="demo-001",
            prompt_id="housing-tonight",
            language="bn",
            text="already shown",
            english_text="already shown",
            trigger_turn_ids=["t-001"],
        ),
    ]

    prompts = QuestionAgent(resident_language="bn").suggest(events)

    assert [prompt.prompt_id for prompt in prompts] == []


def test_record_agent_writes_json_and_html_with_policy_source_metadata(tmp_path) -> None:
    prompts = QuestionAgent(resident_language="bn").suggest(_housing_events())
    events = [
        {
            "type": "session_started",
            "session_id": "demo-001",
            "mode": "demo",
            "scenario": "Housing options interview",
            "resident_language": "bn",
            "caseworker_language": "en",
        },
        *_housing_events(),
        *prompts,
        {
            "type": "final_utterance",
            "session_id": "demo-001",
            "turn_id": "t-002",
            "speaker": "caseworker",
            "language": "en",
            "text": "We will call the out-of-hours team tonight and send you the written decision.",
            "translated_text": "আমরা আজ রাতে আউট-অফ-আওয়ার্স টিমকে ফোন করব এবং লিখিত সিদ্ধান্ত পাঠাব।",
        },
    ]

    snapshot = RecordAgent(output_dir=tmp_path).generate_snapshot(events)

    assert snapshot.status == "ready"
    assert snapshot.json_path is not None
    assert snapshot.html_path is not None
    json_text = tmp_path.joinpath("demo-001-record.json").read_text(encoding="utf-8")
    html_text = tmp_path.joinpath("demo-001-record.html").read_text(encoding="utf-8")
    assert "source_title" in json_text
    assert "Homelessness Code of Guidance" in html_text
    assert "not legal advice" in html_text
