from typing import Literal, Union

from pydantic import BaseModel, Field


AgentName = Literal["interpreter", "policy", "question", "record"]
AgentState = Literal["idle", "listening", "thinking", "emitting", "error"]
BridgeMode = Literal["demo", "hybrid", "live"]
Speaker = Literal["resident", "caseworker", "system"]


class BaseBridgeEvent(BaseModel):
    session_id: str
    type: str
    occurred_at_ms: int | None = None


class SessionStartedEvent(BaseBridgeEvent):
    type: Literal["session_started"] = "session_started"
    mode: BridgeMode
    scenario: str
    resident_language: str
    caseworker_language: str = "en"
    allow_cloud: bool = False


class SessionEndedEvent(BaseBridgeEvent):
    type: Literal["session_ended"] = "session_ended"
    reason: str = "completed"
    record_id: str | None = None


class AgentStatusEvent(BaseBridgeEvent):
    type: Literal["agent_status"] = "agent_status"
    agent: AgentName
    status: AgentState
    message: str | None = None


class AudioChunkEvent(BaseBridgeEvent):
    type: Literal["audio_chunk"] = "audio_chunk"
    chunk_id: str
    speaker: Speaker | None = None
    mime_type: str = "audio/pcm"
    duration_ms: int | None = None
    payload_ref: str | None = None


class FinalUtteranceEvent(BaseBridgeEvent):
    type: Literal["final_utterance"] = "final_utterance"
    turn_id: str
    speaker: Speaker
    language: str
    text: str
    translated_text: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)


class PartialTranscriptEvent(BaseBridgeEvent):
    type: Literal["partial_transcript"] = "partial_transcript"
    turn_id: str
    speaker: Speaker
    language: str
    text: str
    translated_text: str | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    stability: float | None = Field(default=None, ge=0, le=1)


class TranslationEvent(BaseBridgeEvent):
    type: Literal["translation"] = "translation"
    turn_id: str
    speaker: Speaker
    source_language: str
    target_language: str
    source_text: str
    translated_text: str
    confidence: float | None = Field(default=None, ge=0, le=1)


class PolicyCardEvent(BaseBridgeEvent):
    type: Literal["policy_card"] = "policy_card"
    card_id: str
    title: str
    claim: str
    source_title: str
    source_url: str
    source_span: str
    authority: str
    confidence: float = Field(ge=0, le=1)
    trigger_turn_ids: list[str]


class QuestionPromptEvent(BaseBridgeEvent):
    type: Literal["question_prompt"] = "question_prompt"
    prompt_id: str
    language: str
    text: str
    english_text: str
    trigger_turn_ids: list[str]


class CommitmentEvent(BaseBridgeEvent):
    type: Literal["commitment"] = "commitment"
    commitment_id: str
    owner: Speaker
    text: str
    due: str | None = None
    trigger_turn_ids: list[str]


class RecordSnapshotEvent(BaseBridgeEvent):
    type: Literal["record_snapshot"] = "record_snapshot"
    record_id: str
    status: Literal["draft", "ready", "error"]
    summary: str
    html_path: str | None = None
    json_path: str | None = None
    citations_count: int | None = None


BridgeEvent = Union[
    SessionStartedEvent,
    SessionEndedEvent,
    AgentStatusEvent,
    AudioChunkEvent,
    PartialTranscriptEvent,
    FinalUtteranceEvent,
    TranslationEvent,
    PolicyCardEvent,
    QuestionPromptEvent,
    CommitmentEvent,
    RecordSnapshotEvent,
]
