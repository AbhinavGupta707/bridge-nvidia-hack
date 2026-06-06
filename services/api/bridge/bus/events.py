from typing import Literal, Union

from pydantic import BaseModel, Field


AgentName = Literal["interpreter", "policy", "question", "record"]
AgentState = Literal["idle", "listening", "thinking", "emitting", "error"]
Speaker = Literal["resident", "caseworker", "system"]


class BaseBridgeEvent(BaseModel):
    session_id: str
    type: str


class AgentStatusEvent(BaseBridgeEvent):
    type: Literal["agent_status"] = "agent_status"
    agent: AgentName
    status: AgentState
    message: str | None = None


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


class RecordSnapshotEvent(BaseBridgeEvent):
    type: Literal["record_snapshot"] = "record_snapshot"
    record_id: str
    status: Literal["draft", "ready", "error"]
    summary: str
    html_path: str | None = None
    json_path: str | None = None


BridgeEvent = Union[
    AgentStatusEvent,
    FinalUtteranceEvent,
    PolicyCardEvent,
    QuestionPromptEvent,
    RecordSnapshotEvent,
]

