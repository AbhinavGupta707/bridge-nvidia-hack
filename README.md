# Bridge

Bridge is a local-first, multi-agent public-service appointment assistant for
Londoners with limited English proficiency. It is designed for the NVIDIA Hack
for Impact London brief: open models, local edge deployment on DGX Spark or HP
ZGX Nano AI Station, London open data, and measurable public-service impact.

## Current Status

This repository is at deterministic demo integration stage. It contains:

- the product specification
- the implementation handoff plan
- branch and parallel-agent workflow rules
- backend/frontend/data scaffolding
- shared event contracts for the four agents and session lifecycle
- an agent-orchestrated demo event stream for `BRIDGE_MODE=demo`
- a browser UI that consumes the event stream over WebSocket
- a typed manual rehearsal path that runs Policy, Question, and Record agents
  without live audio hardware
- curated source registry placeholders

`BRIDGE_MODE=demo` is the primary integration safety rail. Live audio, local
model serving, RAG indexes, and ElevenLabs integrations must be layered on top
of the same event contracts without breaking the deterministic fixture path.

## Core Demo

The Sunday demo should show:

1. a bilingual housing/homelessness appointment
2. live Interpreter, Policy, Question, and Record agent activity
3. a cited policy card grounded in local corpus data
4. a conservative resident question prompt
5. an offline/local proof
6. a one-tap bilingual record with citations

## Quick Start

Copy the default local configuration:

```bash
cp .env.example .env
```

Run the full demo stack:

```bash
docker compose up --build
```

Open the web client at `http://localhost:5173`. The API is available at
`http://localhost:8080`, and the default WebSocket stream is
`ws://localhost:8080/ws/session/demo-001`.

Run the deterministic event stream without Docker:

```bash
python3 scripts/run_demo_mode.py --session-id demo-001
```

Record endpoints are generated from the same event log:

```bash
curl http://localhost:8080/session/demo-001/record.json
open http://localhost:8080/session/demo-001/record.html
```

Run a typed rehearsal without microphones or NVIDIA hardware:

```bash
curl -X POST http://localhost:8080/session/manual-001/manual_utterance \
  -H 'Content-Type: application/json' \
  -d '{"speaker":"resident","language":"en","text":"I am homeless tonight and need emergency accommodation.","resident_language":"bn"}'
curl http://localhost:8080/session/manual-001/record.json
```

Run the API locally:

```bash
cd services/api
python3 -m pip install -e ".[dev]"
uvicorn bridge.main:app --reload --host 0.0.0.0 --port 8080
```

Run the web client locally:

```bash
cd apps/web
npm install
npm run dev -- --host 0.0.0.0
```

## Runtime Modes

Demo mode must remain deterministic and cloud-free:

```env
BRIDGE_MODE=demo
ASR_PROVIDER=demo
TTS_PROVIDER=demo
LLM_PROVIDER=demo
RAG_PROVIDER=local
ALLOW_CLOUD=false
```

Use `BRIDGE_MODE=hybrid` or `BRIDGE_MODE=live` only after the feature is present
and its official activation/discovery flow has been checked. Cloud providers
must stay guarded by `ALLOW_CLOUD=true`, and the UI/pitch must not claim local
sovereignty in that mode.

## Event Contract

`services/api/bridge/bus/events.py` is the shared contract. The integration
branch keeps existing event names and required fields stable. The current
contract includes additive session lifecycle, transcript, translation, policy,
question, commitment, record, and agent-status events so each parallel branch
can work against the same stream.

No existing required event fields were removed or renamed in the integration
demo pass. Add optional fields only when existing demo consumers keep working.

## Verification

Backend contract and demo tests:

```bash
cd services/api
python3 -m pytest
```

Frontend type/build check:

```bash
cd apps/web
npm run build
```

API health and event stream:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/session/demo-001/events
curl http://localhost:8080/session/demo-001/record.json
```

Before the event hardware arrives, use
[docs/pre-hardware-checklist.md](docs/pre-hardware-checklist.md) to complete
all non-hardware work and keep tomorrow's pass focused on provider activation,
local model residency, and latency proof.

## Repo Layout

```text
apps/web/                 Browser client
services/api/             FastAPI backend and agent bus
data/                     Source registry, fixtures, processed corpus
docs/                     Runbooks, data notes, branch workflow
scripts/                  Ingest, model smoke, offline validation scripts
```

## Parallel Work Rule

All parallel sessions must branch from `main` after the scaffold commit. Do not
work directly on `main`.

Use branch names:

- `agent/infra-models`
- `agent/voice-interpreter`
- `agent/data-policy-rag`
- `agent/frontend-ux`
- `agent/question-record`
- `agent/integration`

Read [docs/parallel-agent-workflow.md](docs/parallel-agent-workflow.md) before
starting a branch.

## Data And Claim Hygiene

The impact statistic must be re-verified before the pitch. Current working
language is "around 350,000 Londoners cannot speak English well or at all",
based on a London Datastore Census 2021 excerpt showing 303,000 "not well" and
52,000 "not at all".

No runtime demo should claim "nothing leaves the box" unless `ALLOW_CLOUD=false`
and the selected ASR, TTS, LLM, and RAG providers are all local.

Policy and data facts shown in the pitch must be re-verified against official
sources before judging. Demo fixtures should stay conservative and cited.
