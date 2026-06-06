# Bridge

Bridge is a local-first AI assistant for public-service appointments.

It helps a caseworker and a resident who do not share the same language have a
clearer, fairer appointment. During a housing or homelessness conversation,
Bridge can translate the discussion, surface relevant policy cards, suggest
useful follow-up questions, and produce a bilingual record at the end.

The project was built for the NVIDIA Hack for Impact London challenge:

- open models
- local edge deployment on DGX Spark or HP ZGX Nano AI Station
- City of London / London open data
- public-service impact

## Why It Matters

Many Londoners struggle to access essential services because language, process,
and policy complexity get in the way. Bridge is designed to support both sides
of a public-service appointment:

- residents get clearer interpretation and prompts for questions they may not
  know to ask
- caseworkers get cited policy context and a structured appointment record
- sensitive conversations can be run in a local/offline mode where supported by
  the selected providers

## What The Demo Shows

The current demo focuses on a Bengali-speaking resident at risk of homelessness.

Bridge shows four cooperating agents:

- Interpreter Agent: turns speech or fixture text into bilingual transcript
- Policy Agent: retrieves cited housing and homelessness policy cards
- Question Agent: suggests conservative resident-led questions
- Record Agent: creates a bilingual JSON/HTML appointment record

The deterministic demo works without the NVIDIA hardware. Live local models can
be activated later on the DGX Spark / ZGX Nano using the same event contracts.

## Current Status

This repository currently includes:

- FastAPI backend with shared event stream contracts
- React/Vite web appointment UI
- deterministic demo mode for reliable rehearsal
- typed manual rehearsal mode for testing without microphones or hardware
- local policy/RAG corpus scaffolding and cited policy cards
- record generation as JSON and HTML
- offline validation and model smoke-check scripts
- runbooks for parallel agents, hardware activation, and pre-hardware work

The main safety rail is:

```env
BRIDGE_MODE=demo
ALLOW_CLOUD=false
```

Do not claim "nothing leaves the box" unless `ALLOW_CLOUD=false` and the
selected ASR, TTS, LLM, embedding, and RAG providers are all local or demo
fixtures.

## Run Locally

Copy the default environment:

```bash
cp .env.example .env
```

Run the full stack with Docker:

```bash
docker compose up --build
```

Open:

- web app: `http://localhost:5173`
- API: `http://localhost:8080`
- WebSocket stream: `ws://localhost:8080/ws/session/demo-001`

## Run Without Docker

Start the API:

```bash
cd services/api
python3 -m pip install -e ".[dev]"
uvicorn bridge.main:app --reload --host 0.0.0.0 --port 8080
```

Start the web app:

```bash
cd apps/web
npm install
npm run dev -- --host 0.0.0.0
```

## Try The Demo Stream

Print the deterministic event stream:

```bash
python3 scripts/run_demo_mode.py --session-id demo-001
```

Fetch the generated appointment record:

```bash
curl http://localhost:8080/session/demo-001/record.json
open http://localhost:8080/session/demo-001/record.html
```

## Try Manual Rehearsal

Manual rehearsal lets you type a turn and run it through the Policy, Question,
and Record agents without live audio or NVIDIA hardware.

```bash
curl -X POST http://localhost:8080/session/manual-001/manual_utterance \
  -H 'Content-Type: application/json' \
  -d '{"speaker":"resident","language":"en","text":"I am homeless tonight and need emergency accommodation.","resident_language":"bn"}'

curl http://localhost:8080/session/manual-001/record.json
```

You can also use the Manual Rehearsal panel in the web app.

## Verification

Backend tests:

```bash
cd services/api
python3 -m pytest
```

Backend lint:

```bash
cd services/api
python3 -m ruff check
```

Frontend build:

```bash
cd apps/web
npm run build
```

Offline validation:

```bash
./scripts/validate_offline.sh
```

On a normal laptop this may warn that NVIDIA runtime, Ollama, or NIM are not
available. That is expected before the event hardware arrives.

## Hardware Activation

The product can be developed and rehearsed without the DGX Spark / ZGX Nano.
The hardware is required for:

- NVIDIA runtime proof with `nvidia-smi`
- local model residency and performance checks
- Ollama or NIM model activation
- local ASR/TTS latency checks
- verified offline/local claims with the final selected providers

See:

- [docs/pre-hardware-checklist.md](docs/pre-hardware-checklist.md)
- [docs/model-runtime.md](docs/model-runtime.md)
- [docs/integration-runbook.md](docs/integration-runbook.md)

## Repository Layout

```text
apps/web/       React appointment UI
services/api/   FastAPI backend, agents, events, and records
data/           source registry, fixtures, and processed corpus output
docs/           runbooks and implementation notes
scripts/        ingestion, demo, smoke, and offline validation scripts
```

## Data And Claims

Policy cards and pitch claims should stay cited and conservative. Public demo
facts should be re-verified against official sources before judging.
