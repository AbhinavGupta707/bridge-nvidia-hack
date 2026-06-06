import { Activity, FileText, Languages, Scale, Sparkles } from "lucide-react";
import type { AgentName, AgentState } from "./types";

const agents: Array<{ name: AgentName; label: string; icon: JSX.Element }> = [
  { name: "interpreter", label: "Interpreter", icon: <Languages size={18} /> },
  { name: "policy", label: "Policy", icon: <Scale size={18} /> },
  { name: "question", label: "Question", icon: <Sparkles size={18} /> },
  { name: "record", label: "Record", icon: <FileText size={18} /> },
];

const statusByAgent: Record<AgentName, AgentState> = {
  interpreter: "idle",
  policy: "idle",
  question: "idle",
  record: "idle",
};

export function App() {
  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Local session</p>
          <h1>Bridge</h1>
        </div>
        <div className="status-pill">Offline-ready demo</div>
      </header>

      <section className="workspace" aria-label="Appointment workspace">
        <section className="pane resident-pane">
          <div className="pane-header">
            <h2>Resident</h2>
            <span>Bengali</span>
          </div>
          <p className="transcript-line">Demo transcript stream will appear here.</p>
        </section>

        <section className="pane caseworker-pane">
          <div className="pane-header">
            <h2>Caseworker</h2>
            <span>English</span>
          </div>
          <article className="policy-card">
            <p className="eyebrow">Policy card</p>
            <h3>Awaiting cited policy trigger</h3>
            <p>Policy cards must include source title, source span, and confidence.</p>
          </article>
        </section>
      </section>

      <footer className="activity-strip" aria-label="Agent activity">
        {agents.map((agent) => (
          <div className="agent-chip" key={agent.name}>
            {agent.icon}
            <span>{agent.label}</span>
            <strong>
              <Activity size={14} />
              {statusByAgent[agent.name]}
            </strong>
          </div>
        ))}
      </footer>
    </main>
  );
}

