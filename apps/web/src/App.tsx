import { useEffect, useMemo, useReducer, useState, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Circle,
  Cloud,
  FileText,
  Languages,
  Mic,
  Pause,
  Play,
  Scale,
  ShieldCheck,
  Sparkles,
  WifiOff,
} from "lucide-react";
import type {
  AgentName,
  AgentState,
  BridgeEvent,
  CommitmentEvent,
  FinalUtteranceEvent,
  PartialTranscriptEvent,
  PolicyCardEvent,
  QuestionPromptEvent,
  RecordSnapshotEvent,
  TranscriptTurn,
} from "./types";

type AgentMeta = {
  name: AgentName;
  label: string;
  icon: ReactNode;
};

type AppointmentState = {
  agentStatus: Record<AgentName, { status: AgentState; message: string }>;
  turns: TranscriptTurn[];
  partials: Record<string, PartialTranscriptEvent>;
  policyCards: PolicyCardEvent[];
  prompts: QuestionPromptEvent[];
  commitments: CommitmentEvent[];
  record: RecordSnapshotEvent;
  eventCount: number;
  lastEvent: string;
};

type RuntimeEnv = Record<string, string | boolean | undefined>;

const runtimeEnv = import.meta.env as unknown as RuntimeEnv;
const allowCloud =
  String(runtimeEnv.ALLOW_CLOUD ?? runtimeEnv.VITE_ALLOW_CLOUD ?? "false").toLowerCase() === "true";
const apiWsUrl = String(runtimeEnv.VITE_API_WS_URL ?? "ws://localhost:8080/ws/session/demo-001");

const agents: AgentMeta[] = [
  { name: "interpreter", label: "Interpreter", icon: <Languages size={18} /> },
  { name: "policy", label: "Policy", icon: <Scale size={18} /> },
  { name: "question", label: "Question", icon: <Sparkles size={18} /> },
  { name: "record", label: "Record", icon: <FileText size={18} /> },
];

const initialAgentStatus: AppointmentState["agentStatus"] = {
  interpreter: { status: "idle", message: "Ready for bilingual speech" },
  policy: { status: "idle", message: "Waiting for cited triggers" },
  question: { status: "idle", message: "Checklist loaded" },
  record: { status: "idle", message: "Draft record open" },
};

const initialRecord: RecordSnapshotEvent = {
  type: "record_snapshot",
  session_id: "demo-001",
  record_id: "record-demo-001",
  status: "draft",
  summary:
    "Record preview will update as transcript turns, cited policy cards, and resident questions arrive.",
  html_path: null,
  json_path: null,
};

const initialState: AppointmentState = {
  agentStatus: initialAgentStatus,
  turns: [],
  partials: {},
  policyCards: [],
  prompts: [],
  commitments: [],
  record: initialRecord,
  eventCount: 0,
  lastEvent: "awaiting_start",
};

const mockEvents: BridgeEvent[] = [
  {
    type: "agent_status",
    session_id: "demo-001",
    agent: "interpreter",
    status: "listening",
    message: "Resident channel live",
  },
  {
    type: "partial_transcript",
    session_id: "demo-001",
    turn_id: "t-001",
    speaker: "resident",
    language: "bn",
    text: "আমি আজ রাতে থাকার",
    translated_text: "I need somewhere to stay tonight",
    start_ms: 900,
    end_ms: 2800,
    confidence: 0.82,
    stability: 0.67,
  },
  {
    type: "final_utterance",
    session_id: "demo-001",
    turn_id: "t-001",
    speaker: "resident",
    language: "bn",
    text: "আমি আজ রাতে থাকার জায়গা নেই। আমার দুই সন্তান আছে।",
    translated_text: "I have nowhere to stay tonight. I have two children.",
    start_ms: 900,
    end_ms: 5200,
    confidence: 0.92,
  },
  {
    type: "agent_status",
    session_id: "demo-001",
    agent: "policy",
    status: "thinking",
    message: "Checking homelessness duties",
  },
  {
    type: "policy_card",
    session_id: "demo-001",
    card_id: "pc-001",
    title: "Interim accommodation where there may be priority need",
    claim:
      "If the authority has reason to believe someone may be homeless, eligible, and in priority need, it can owe an interim accommodation duty while enquiries continue.",
    source_title: "Rights of people who are homeless - City of London",
    source_url:
      "https://www.cityoflondon.gov.uk/services/housing-and-homelessness/homelessness-or-at-risk/rights-of-people-who-are-homeless",
    source_span:
      "The council explains that help can include temporary accommodation while it looks into the application.",
    authority: "City of London",
    confidence: 0.84,
    trigger_turn_ids: ["t-001"],
  },
  {
    type: "question_prompt",
    session_id: "demo-001",
    prompt_id: "qp-001",
    language: "bn",
    text: "কাউন্সিল কি মনে করছে আজ রাতের জন্য অন্তর্বর্তীকালীন থাকার ব্যবস্থা দেওয়া উচিত?",
    english_text:
      "Ask whether the council believes it has reason to provide interim accommodation tonight.",
    trigger_turn_ids: ["t-001", "pc-001"],
  },
  {
    type: "final_utterance",
    session_id: "demo-001",
    turn_id: "t-002",
    speaker: "caseworker",
    language: "en",
    text: "I understand. I will ask some questions about your children and where you stayed last night.",
    translated_text:
      "আমি বুঝতে পারছি। আপনার সন্তানদের এবং গত রাতে কোথায় ছিলেন সে বিষয়ে কিছু প্রশ্ন করব।",
    start_ms: 7200,
    end_ms: 11300,
    confidence: 0.95,
  },
  {
    type: "commitment",
    session_id: "demo-001",
    commitment_id: "cm-001",
    owner: "caseworker",
    text: "Caseworker will assess whether interim accommodation is needed tonight.",
    due: "today",
    trigger_turn_ids: ["t-001", "t-002"],
  },
  {
    type: "record_snapshot",
    session_id: "demo-001",
    record_id: "record-demo-001",
    status: "draft",
    summary:
      "Resident reported having nowhere to stay tonight and caring for two children. Bridge surfaced a cited interim accommodation policy card and one conservative resident question.",
    html_path: "/session/demo-001/record.html",
    json_path: "/session/demo-001/record.json",
    citations_count: 1,
  },
  {
    type: "final_utterance",
    session_id: "demo-001",
    turn_id: "t-003",
    speaker: "resident",
    language: "bn",
    text: "আমার কাছে জন্ম সনদ আছে, কিন্তু ঠিকানার কাগজ নেই।",
    translated_text: "I have birth certificates, but I do not have proof of address.",
    start_ms: 12400,
    end_ms: 16100,
    confidence: 0.9,
  },
  {
    type: "policy_card",
    session_id: "demo-001",
    card_id: "pc-002",
    title: "Record missing documents without delaying urgent assessment",
    claim:
      "The appointment should record available evidence and outstanding documents, while urgent homelessness help is still assessed where risk is immediate.",
    source_title: "Preventing homelessness - City of London",
    source_url:
      "https://www.cityoflondon.gov.uk/services/housing-and-homelessness/homelessness-or-at-risk/preventing-homelessness",
    source_span:
      "The council asks residents at risk of homelessness to contact the service as soon as possible so options can be considered.",
    authority: "City of London",
    confidence: 0.73,
    trigger_turn_ids: ["t-003"],
  },
  {
    type: "record_snapshot",
    session_id: "demo-001",
    record_id: "record-demo-001",
    status: "ready",
    summary:
      "Draft record is ready with three transcript turns, two cited policy cards, one resident question prompt, and file links for HTML and JSON export.",
    html_path: "/session/demo-001/record.html",
    json_path: "/session/demo-001/record.json",
    citations_count: 2,
  },
  {
    type: "agent_status",
    session_id: "demo-001",
    agent: "interpreter",
    status: "idle",
    message: "Stream paused",
  },
  {
    type: "agent_status",
    session_id: "demo-001",
    agent: "policy",
    status: "idle",
    message: "Cards pinned",
  },
  {
    type: "agent_status",
    session_id: "demo-001",
    agent: "question",
    status: "idle",
    message: "No repeat prompts",
  },
  {
    type: "agent_status",
    session_id: "demo-001",
    agent: "record",
    status: "idle",
    message: "Ready for review",
  },
];

type AppointmentAction = { type: "reset" } | { type: "event"; event: BridgeEvent };

function reducer(state: AppointmentState, action: AppointmentAction): AppointmentState {
  if (action.type === "reset") {
    return initialState;
  }

  const { event } = action;

  if (event.type === "session_started") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `session:${event.mode}`,
    };
  }

  if (event.type === "session_ended") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `session:${event.reason}`,
    };
  }

  if (event.type === "agent_status") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `${event.agent}:${event.status}`,
      agentStatus: {
        ...state.agentStatus,
        [event.agent]: { status: event.status, message: event.message ?? "" },
      },
    };
  }

  if (event.type === "partial_transcript") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `partial:${event.turn_id}`,
      partials: { ...state.partials, [event.turn_id]: event },
    };
  }

  if (event.type === "final_utterance") {
    const { [event.turn_id]: _finished, ...nextPartials } = state.partials;
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `final:${event.turn_id}`,
      partials: nextPartials,
      turns: [...state.turns.filter((turn) => turn.turn_id !== event.turn_id), event],
    };
  }

  if (event.type === "translation") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `translation:${event.turn_id}`,
    };
  }

  if (event.type === "policy_card") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `policy:${event.card_id}`,
      policyCards: [
        event,
        ...state.policyCards.filter((card) => card.card_id !== event.card_id),
      ],
    };
  }

  if (event.type === "question_prompt") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `prompt:${event.prompt_id}`,
      prompts: [event, ...state.prompts.filter((prompt) => prompt.prompt_id !== event.prompt_id)],
    };
  }

  if (event.type === "commitment") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `commitment:${event.commitment_id}`,
      commitments: [
        event,
        ...state.commitments.filter(
          (commitment) => commitment.commitment_id !== event.commitment_id,
        ),
      ],
    };
  }

  if (event.type === "record_snapshot") {
    return {
      ...state,
      eventCount: state.eventCount + 1,
      lastEvent: `record:${event.status}`,
      record: event,
    };
  }

  return state;
}

function formatTime(ms?: number | null) {
  if (ms == null) return "--:--";
  const seconds = Math.floor(ms / 1000);
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(
    2,
    "0",
  )}`;
}

function confidenceLabel(confidence?: number | null) {
  if (confidence == null) return "confidence pending";
  return `${Math.round(confidence * 100)}% confidence`;
}

function httpBaseFromWs(wsUrl: string) {
  try {
    const parsed = new URL(wsUrl, window.location.href);
    parsed.protocol = parsed.protocol === "wss:" ? "https:" : "http:";
    parsed.pathname = "";
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return "http://localhost:8080";
  }
}

function endpointUrl(path: string | null | undefined, apiBaseUrl: string) {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`;
}

function displayForPane(turn: FinalUtteranceEvent | PartialTranscriptEvent, pane: "resident" | "english") {
  if (pane === "resident") {
    return turn.speaker === "resident" ? turn.text : turn.translated_text ?? turn.text;
  }

  return turn.speaker === "resident" ? turn.translated_text ?? turn.text : turn.text;
}

function secondaryForPane(
  turn: FinalUtteranceEvent | PartialTranscriptEvent,
  pane: "resident" | "english",
) {
  if (pane === "resident") {
    return turn.speaker === "resident" ? turn.translated_text : turn.text;
  }

  return turn.speaker === "resident" ? turn.text : turn.translated_text;
}

export function App() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [consentChecked, setConsentChecked] = useState(false);
  const [recording, setRecording] = useState(false);
  const [streamComplete, setStreamComplete] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<"idle" | "connecting" | "streaming" | "complete" | "error">(
    "idle",
  );
  const [recordRevealed, setRecordRevealed] = useState(false);
  const apiBaseUrl = useMemo(() => httpBaseFromWs(apiWsUrl), []);

  const liveTurns = useMemo(() => {
    const partials = Object.values(state.partials).map((partial) => ({ ...partial, partial: true }));
    return [...state.turns, ...partials].sort(
      (a, b) => (a.start_ms ?? Number.MAX_SAFE_INTEGER) - (b.start_ms ?? Number.MAX_SAFE_INTEGER),
    );
  }, [state.partials, state.turns]);

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get("autoplay") !== "1") return;
    setConsentChecked(true);
    setStreamComplete(false);
    setRecording(true);
  }, []);

  useEffect(() => {
    if (!recording || streamComplete) return;

    setConnectionStatus("connecting");

    if (new URLSearchParams(window.location.search).get("fallback") === "1") {
      let index = 0;
      const timers: number[] = [];

      const schedule = () => {
        const event = mockEvents[index];
        if (!event) {
          setConnectionStatus("complete");
          setStreamComplete(true);
          setRecording(false);
          return;
        }

        timers.push(
          window.setTimeout(() => {
            setConnectionStatus("streaming");
            dispatch({ type: "event", event });
            index += 1;
            schedule();
          }, index === 0 ? 250 : 850),
        );
      };

      schedule();

      return () => {
        timers.forEach((timer) => window.clearTimeout(timer));
      };
    }

    let completedByServer = false;
    let socket: WebSocket;
    try {
      socket = new WebSocket(apiWsUrl);
    } catch {
      setConnectionStatus("error");
      setStreamComplete(true);
      setRecording(false);
      return;
    }

    socket.onopen = () => {
      setConnectionStatus("streaming");
    };

    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as BridgeEvent;
      dispatch({ type: "event", event });
      if (event.type === "session_ended") {
        completedByServer = true;
        setConnectionStatus("complete");
        setStreamComplete(true);
        setRecording(false);
        socket.close();
      }
    };

    socket.onerror = () => {
      if (!completedByServer) {
        setConnectionStatus("error");
      }
    };

    socket.onclose = () => {
      if (!completedByServer) {
        setConnectionStatus("error");
        setStreamComplete(true);
        setRecording(false);
      }
    };

    return () => {
      completedByServer = true;
      socket.close();
    };
  }, [recording, streamComplete]);

  const startSession = () => {
    if (!consentChecked) return;
    dispatch({ type: "reset" });
    setRecordRevealed(false);
    setStreamComplete(false);
    setRecording(true);
  };

  const modeLabel = allowCloud ? "Cloud mode enabled" : "Local/offline mode";
  const modeDetail = allowCloud
    ? "ALLOW_CLOUD=true; cloud providers must be labelled during use."
    : "ALLOW_CLOUD=false; backend demo stream does not require internet.";
  const recordHtmlUrl = endpointUrl(state.record.html_path, apiBaseUrl);
  const recordJsonUrl = endpointUrl(state.record.json_path, apiBaseUrl);

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-block">
          <div className="service-mark">Bridge</div>
          <div>
            <p className="eyebrow">Public-service appointment</p>
            <h1>Housing support session</h1>
          </div>
        </div>

        <div className={`mode-banner ${allowCloud ? "is-cloud" : "is-local"}`} aria-label={modeLabel}>
          {allowCloud ? <Cloud size={18} /> : <WifiOff size={18} />}
          <div>
            <strong>{modeLabel}</strong>
            <span>{modeDetail}</span>
          </div>
        </div>
      </header>

      <section className="appointment-grid" aria-label="Bridge appointment tool">
        <aside className="setup-panel" aria-label="Consent and setup">
          <div className="section-heading">
            <ShieldCheck size={18} />
            <h2>Consent and Setup</h2>
          </div>

          <label className="check-row">
            <input
              type="checkbox"
              checked={consentChecked}
              onChange={(event) => setConsentChecked(event.target.checked)}
            />
            <span>Resident consent confirmed for interpretation, notes, and record preview.</span>
          </label>

          <div className="setup-fields">
            <div>
              <span>Resident language</span>
              <strong>Bengali</strong>
            </div>
            <div>
              <span>Caseworker language</span>
              <strong>English</strong>
            </div>
            <div>
              <span>Scenario</span>
              <strong>Homelessness risk</strong>
            </div>
          </div>

          <button
            className="primary-action"
            type="button"
            disabled={!consentChecked || recording}
            onClick={startSession}
          >
            {recording ? <Pause size={18} /> : <Play size={18} />}
            {recording ? "Streaming demo" : streamComplete ? "Replay demo stream" : "Start appointment"}
          </button>

          <div className="local-status">
            <div>
              <WifiOff size={17} />
              <strong>{allowCloud ? "Hybrid labelled" : "Offline ready"}</strong>
            </div>
            <p>Events stream from the Bridge backend WebSocket. Add <code>?fallback=1</code> only for fixture-only playback.</p>
          </div>

          <div className="event-meter" aria-label="Backend event progress">
            <span>Backend WS events</span>
            <strong>{connectionStatus}: {state.eventCount}</strong>
          </div>
        </aside>

        <section className="transcript-board" aria-label="Synchronized transcripts">
          <TranscriptPane
            title="Resident transcript"
            subtitle="Bengali with English support"
            pane="resident"
            turns={liveTurns}
          />
          <TranscriptPane
            title="Caseworker transcript"
            subtitle="English working view"
            pane="english"
            turns={liveTurns}
          />
        </section>

        <aside className="evidence-rail" aria-label="Policy, questions, and record">
          <section className="rail-section">
            <div className="section-heading">
              <Scale size={18} />
              <h2>Policy Cards</h2>
            </div>
            <div className="card-stack">
              {state.policyCards.length === 0 ? (
                <EmptyState text="Cited cards appear after relevant transcript turns." />
              ) : (
                state.policyCards.map((card) => <PolicyCard key={card.card_id} card={card} />)
              )}
            </div>
          </section>

          <section className="rail-section">
            <div className="section-heading">
              <Sparkles size={18} />
              <h2>Question Prompts</h2>
            </div>
            <div className="card-stack">
              {state.prompts.length === 0 ? (
                <EmptyState text="Conservative resident prompts are held until useful." />
              ) : (
                state.prompts.map((prompt) => <QuestionPrompt key={prompt.prompt_id} prompt={prompt} />)
              )}
            </div>
          </section>

          <section className="record-preview" aria-label="Record preview">
            <div className="section-heading">
              <FileText size={18} />
              <h2>Record Preview</h2>
            </div>
            <div className={`record-status is-${state.record.status}`}>
              {state.record.status === "ready" ? <CheckCircle2 size={17} /> : <Circle size={17} />}
              <strong>{state.record.status}</strong>
            </div>
            {state.record.status === "ready" && !recordRevealed ? (
              <button
                className="secondary-action"
                type="button"
                onClick={() => setRecordRevealed(true)}
              >
                <FileText size={17} />
                Generate record
              </button>
            ) : (
	              <>
	                <p>{state.record.summary}</p>
	                <dl>
                  <div>
                    <dt>Transcript turns</dt>
                    <dd>{state.turns.length}</dd>
                  </div>
                  <div>
                    <dt>Citations</dt>
                    <dd>{state.policyCards.length}</dd>
                  </div>
                  <div>
                    <dt>Prompts</dt>
                    <dd>{state.prompts.length}</dd>
                  </div>
                  <div>
                    <dt>Commitments</dt>
                    <dd>{state.commitments.length}</dd>
	                  </div>
	                </dl>
	                <div className="record-links">
	                  {recordHtmlUrl ? (
	                    <a href={recordHtmlUrl} target="_blank" rel="noreferrer">Open HTML record</a>
	                  ) : null}
	                  {recordJsonUrl ? (
	                    <a href={recordJsonUrl} target="_blank" rel="noreferrer">Open JSON record</a>
	                  ) : null}
	                </div>
	              </>
	            )}
          </section>
        </aside>
      </section>

      <footer className="activity-strip" aria-label="Agent activity">
        {agents.map((agent) => (
          <div className={`agent-chip is-${state.agentStatus[agent.name].status}`} key={agent.name}>
            {agent.icon}
            <div>
              <span>{agent.label}</span>
              <strong>
                <Activity size={14} />
                {state.agentStatus[agent.name].status}
              </strong>
            </div>
            <p>{state.agentStatus[agent.name].message}</p>
          </div>
        ))}
        <div className="last-event">
          <span>Latest event</span>
          <strong>{state.lastEvent}</strong>
        </div>
      </footer>
    </main>
  );
}

function TranscriptPane({
  title,
  subtitle,
  pane,
  turns,
}: {
  title: string;
  subtitle: string;
  pane: "resident" | "english";
  turns: Array<FinalUtteranceEvent | (PartialTranscriptEvent & { partial: boolean })>;
}) {
  return (
    <section className="transcript-pane">
      <div className="pane-header">
        <div>
          <h2>{title}</h2>
          <span>{subtitle}</span>
        </div>
        <Mic size={18} />
      </div>

      <div className="turn-list">
        {turns.length === 0 ? (
          <EmptyState text="Start the appointment to stream synchronized turns." />
        ) : (
          turns.map((turn) => {
            const display = displayForPane(turn, pane);
            const secondary = secondaryForPane(turn, pane);
            const isPartial = "partial" in turn && turn.partial;

            return (
              <article
                className={`turn-row is-${turn.speaker} ${isPartial ? "is-partial" : ""}`}
                key={`${pane}-${turn.turn_id}-${isPartial ? "partial" : "final"}`}
              >
                <div className="turn-meta">
                  <strong>{turn.speaker}</strong>
                  <span>{formatTime(turn.start_ms)}</span>
                  <span>{turn.turn_id}</span>
                </div>
                <p>{display}</p>
                {secondary ? <small>{secondary}</small> : null}
                <div className="turn-footer">
                  <span>{isPartial ? "partial" : "final"}</span>
                  <span>{confidenceLabel(turn.confidence)}</span>
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}

function PolicyCard({ card }: { card: PolicyCardEvent }) {
  return (
    <article className="policy-card">
      <div className="card-topline">
        <span>{card.authority}</span>
        <strong>{Math.round(card.confidence * 100)}%</strong>
      </div>
      <h3>{card.title}</h3>
      <p>{card.claim}</p>
      <footer>
        <a href={card.source_url} target="_blank" rel="noreferrer">
          {card.source_title}
        </a>
        <small>{card.source_span}</small>
      </footer>
    </article>
  );
}

function QuestionPrompt({ prompt }: { prompt: QuestionPromptEvent }) {
  return (
    <article className="prompt-card">
      <div className="card-topline">
        <span>Resident prompt</span>
        <strong>{prompt.language.toUpperCase()}</strong>
      </div>
      <p>{prompt.text}</p>
      <small>{prompt.english_text}</small>
    </article>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="empty-state">
      <AlertTriangle size={16} />
      <span>{text}</span>
    </div>
  );
}
