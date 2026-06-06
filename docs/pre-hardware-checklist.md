# Pre-Hardware Checklist

Use this checklist before the DGX Spark / ZGX Nano arrives. The goal is to
finish every product, contract, rehearsal, and integration surface that does
not require the target NVIDIA runtime.

## What Can Be Completed Now

- Deterministic offline demo with `BRIDGE_MODE=demo` and `ALLOW_CLOUD=false`.
- Backend event contracts for Interpreter, Policy, Question, and Record agents.
- WebSocket-driven web UI and one-click record links.
- Typed manual rehearsal through the same backend agent path.
- Local source ingestion and cited policy-card generation.
- Record JSON/HTML rendering from event logs.
- Cloud guardrails, provider env vars, and hardware activation docs.
- Unit tests, type checks, fixture validation, and demo script rehearsal.

## What Requires Hardware Tomorrow

- NVIDIA driver/runtime proof with `nvidia-smi` and Docker GPU runtime.
- Local model residency, speed, and memory checks for Ollama or NIM.
- Actual ASR/TTS latency and quality with local Whisper, Piper, Kokoro, or
  confirmed on-device ElevenLabs.
- NGC model access, NIM image pulls, and `/v1/models` discovery.
- ElevenLabs access-mode confirmation. Cloud keys are not equivalent to
  on-device processing.
- Offline claim validation with the real selected providers.

## Tonight's Verification Pass

Run these from repo root:

```bash
cp .env.example .env
python3 scripts/run_demo_mode.py --session-id demo-001 --compact
./scripts/validate_offline.sh
cd services/api && python3 -m pytest
cd services/api && python3 -m ruff check
cd apps/web && npm run build
```

Start the API and web UI:

```bash
cd services/api
uvicorn bridge.main:app --reload --host 0.0.0.0 --port 8080
```

```bash
cd apps/web
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173`, start the demo, then try the Manual Rehearsal
panel with these two turns:

```text
Resident: I am homeless tonight and need emergency accommodation.
Caseworker: I will call you today after checking the emergency accommodation options.
```

Expected result:

- transcript panes update
- at least one cited policy card appears
- a conservative question prompt appears
- a caseworker commitment appears
- the record links open JSON and HTML for the same manual session

The same rehearsal path is also available by API:

```bash
curl -X POST http://localhost:8080/session/manual-001/manual_utterance \
  -H 'Content-Type: application/json' \
  -d '{"speaker":"resident","language":"en","text":"I am homeless tonight and need emergency accommodation.","resident_language":"bn"}'

curl http://localhost:8080/session/manual-001/record.json
curl http://localhost:8080/session/manual-001/record.html
```

## Tomorrow's First-Hour Hardware Pass

Follow [model-runtime.md](model-runtime.md) in layer order:

1. Confirm hardware and OS discovery: `uname -m`, `/etc/os-release`,
   `nvidia-smi`.
2. Confirm Docker and NVIDIA runtime discovery before pulling containers.
3. Confirm provider registration: `ollama list`, `curl /api/tags`,
   `curl /v1/models`, ElevenLabs access mode and endpoint.
4. Only after the provider exists, debug permissions, ports, model loading, or
   performance.
5. Switch one provider at a time from demo to local live mode.
6. Re-run `./scripts/validate_offline.sh --audio-smoke` before making any
   "nothing leaves the box" claim.

## No-Hardware Stop Line

Do not burn time faking hardware proof. If the device is not present, keep the
product in deterministic demo plus manual rehearsal mode, and list hardware
checks as pending. That is the honest and useful state before the box arrives.
