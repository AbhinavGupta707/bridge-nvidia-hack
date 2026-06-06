# Integration Runbook

This runbook is owned by `agent/integration`. Its job is to keep Bridge
demoable while parallel branches land.

## Golden Path

Use deterministic demo mode as the baseline before and after every merge:

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:5173` and confirm:

1. the session shows `Local/offline mode`
2. resident and caseworker transcripts stream in
3. at least one cited policy card appears
4. one resident question prompt appears
5. the record summary appears with a citation count and HTML/JSON links

## Fast Checks

Run these from the repo root unless noted:

```bash
python3 scripts/run_demo_mode.py --session-id demo-001
cd services/api && python3 -m pytest
cd apps/web && npm run build
```

When the API is running:

```bash
curl http://localhost:8080/health
curl http://localhost:8080/session/demo-001/events
curl http://localhost:8080/session/demo-001/record.json
```

Typed manual rehearsal can be used before audio hardware is available:

```bash
curl -X POST http://localhost:8080/session/manual-001/manual_utterance \
  -H 'Content-Type: application/json' \
  -d '{"speaker":"resident","language":"en","text":"I am homeless tonight and need emergency accommodation.","resident_language":"bn"}'
curl http://localhost:8080/session/manual-001/record.json
```

Use [pre-hardware-checklist.md](pre-hardware-checklist.md) when developing
before the DGX Spark / ZGX Nano is available.

## Merge Gate

Before merging a parallel branch, confirm:

- `BRIDGE_MODE=demo` still runs with `ALLOW_CLOUD=false`
- no existing event names or required fields in `services/api/bridge/bus/events.py`
  were removed or renamed
- any new cloud provider is disabled unless `ALLOW_CLOUD=true`
- policy claims shown in UI or record include citation metadata
- handoff notes include changed files, verification commands, and blockers

## Event Contract Notes

The integration branch made an additive contract update to match the
implementation plan:

- added `session_started` and `session_ended`
- added `audio_chunk` for live-provider handoff
- added `commitment`
- added optional `occurred_at_ms` and `citations_count`

Existing event names and required fields were not changed. Parallel agents may
add optional fields only if the deterministic demo stream and web consumer keep
working.

## Layer-Order Diagnosis

If a feature is missing or unavailable, diagnose in this order:

1. registration, discovery, install state, and official activation flow
2. feature presence in config and provider selection
3. permissions, runtime, drivers, or network

Do not debug runtime permissions for a provider that has not been registered or
activated yet.

## Demo Fallback

If live providers are unreliable, keep the public demo on:

```env
BRIDGE_MODE=demo
ASR_PROVIDER=demo
TTS_PROVIDER=demo
LLM_PROVIDER=demo
RAG_PROVIDER=local
ALLOW_CLOUD=false
```

Then explain that live providers are an optional layer over the same event bus,
while the shown path proves the offline/local orchestration contract.

The web client uses the backend WebSocket by default. `?fallback=1` is available
only as a fixture-only browser fallback if the API cannot be started.
