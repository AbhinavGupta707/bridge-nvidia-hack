export type AgentName = "interpreter" | "policy" | "question" | "record";
export type AgentState = "idle" | "listening" | "thinking" | "emitting" | "error";
export type BridgeMode = "demo" | "hybrid" | "live";
export type Speaker = "resident" | "caseworker" | "system";

export type BaseBridgeEvent = {
  session_id: string;
  type: string;
  occurred_at_ms?: number | null;
};

export type SessionStartedEvent = BaseBridgeEvent & {
  type: "session_started";
  mode: BridgeMode;
  scenario: string;
  resident_language: string;
  caseworker_language: string;
  allow_cloud: boolean;
};

export type SessionEndedEvent = BaseBridgeEvent & {
  type: "session_ended";
  reason: string;
  record_id?: string | null;
};

export type AgentStatusEvent = BaseBridgeEvent & {
  type: "agent_status";
  agent: AgentName;
  status: AgentState;
  message?: string | null;
};

export type FinalUtteranceEvent = BaseBridgeEvent & {
  type: "final_utterance";
  turn_id: string;
  speaker: Speaker;
  language: string;
  text: string;
  translated_text?: string | null;
  start_ms?: number | null;
  end_ms?: number | null;
  confidence?: number | null;
};

export type PartialTranscriptEvent = BaseBridgeEvent & {
  type: "partial_transcript";
  turn_id: string;
  speaker: Speaker;
  language: string;
  text: string;
  translated_text?: string | null;
  start_ms?: number | null;
  end_ms?: number | null;
  confidence?: number | null;
  stability?: number | null;
};

export type TranslationEvent = BaseBridgeEvent & {
  type: "translation";
  turn_id: string;
  speaker: Speaker;
  source_language: string;
  target_language: string;
  source_text: string;
  translated_text: string;
  confidence?: number | null;
};

export type PolicyCardEvent = BaseBridgeEvent & {
  type: "policy_card";
  card_id: string;
  title: string;
  claim: string;
  source_title: string;
  source_url: string;
  source_span: string;
  authority: string;
  confidence: number;
  trigger_turn_ids: string[];
};

export type QuestionPromptEvent = BaseBridgeEvent & {
  type: "question_prompt";
  prompt_id: string;
  language: string;
  text: string;
  english_text: string;
  trigger_turn_ids: string[];
};

export type CommitmentEvent = BaseBridgeEvent & {
  type: "commitment";
  commitment_id: string;
  owner: Speaker;
  text: string;
  due?: string | null;
  trigger_turn_ids: string[];
};

export type RecordSnapshotEvent = BaseBridgeEvent & {
  type: "record_snapshot";
  record_id: string;
  status: "draft" | "ready" | "error";
  summary: string;
  html_path?: string | null;
  json_path?: string | null;
  citations_count?: number | null;
};

export type BridgeEvent =
  | SessionStartedEvent
  | SessionEndedEvent
  | AgentStatusEvent
  | FinalUtteranceEvent
  | PartialTranscriptEvent
  | TranslationEvent
  | PolicyCardEvent
  | QuestionPromptEvent
  | CommitmentEvent
  | RecordSnapshotEvent;

export type TranscriptTurn = FinalUtteranceEvent & {
  partial?: false;
};

export type PartialTurn = PartialTranscriptEvent & {
  partial: true;
};
