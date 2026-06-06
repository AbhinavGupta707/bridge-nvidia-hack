export type AgentName = "interpreter" | "policy" | "question" | "record";
export type AgentState = "idle" | "listening" | "thinking" | "emitting" | "error";

export type AgentStatusEvent = {
  type: "agent_status";
  session_id: string;
  agent: AgentName;
  status: AgentState;
  message?: string | null;
};

export type PolicyCardEvent = {
  type: "policy_card";
  session_id: string;
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

export type BridgeEvent = AgentStatusEvent | PolicyCardEvent;

