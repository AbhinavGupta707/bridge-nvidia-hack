# Parallel Agent Workflow

This repo is intended for multiple Codex sessions working at the same time.
The coordination rule is simple: shared contracts first, isolated branches
afterwards, integration through reviewed merges.

## Starting Rule

All agents start from the scaffold commit on `main`.

Never commit directly to `main` during parallel work. Create a branch:

```bash
git switch -c agent/<workstream>
```

Recommended branches:

- `agent/infra-models`
- `agent/voice-interpreter`
- `agent/data-policy-rag`
- `agent/frontend-ux`
- `agent/question-record`
- `agent/integration`

Before handing work to `agent/integration`, also read
[docs/integration-runbook.md](integration-runbook.md).

## File Ownership

Use these ownership boundaries to avoid conflicts:

| Branch | Owns |
| --- | --- |
| `agent/infra-models` | `scripts/smoke_models.py`, `scripts/validate_offline.sh`, `docs/model-runtime.md`, Docker/runtime notes |
| `agent/voice-interpreter` | `services/api/bridge/audio/`, `services/api/bridge/agents/interpreter.py`, voice fixtures |
| `agent/data-policy-rag` | `data/sources.yml`, `scripts/ingest_corpus.py`, `services/api/bridge/rag/`, `services/api/bridge/agents/policy.py`, `docs/data-sources.md` |
| `agent/frontend-ux` | `apps/web/` |
| `agent/question-record` | `services/api/bridge/agents/question.py`, `services/api/bridge/agents/record.py`, `services/api/bridge/records/`, `data/fixtures/`, `docs/demo-script.md` |
| `agent/integration` | `README.md`, `.env.example`, `docker-compose.yml`, merge glue, runbook updates |

## Contract Rule

The event contract in `services/api/bridge/bus/events.py` is shared. Any change
to event names, required fields, or session semantics must be proposed in the
integration branch first.

Agents may add optional fields if the existing consumers keep working.

`agent/integration` has landed additive lifecycle and commitment events to match
the implementation plan. Do not remove or rename existing event names or
required fields; keep `BRIDGE_MODE=demo` green after optional additions.

## Commit Rule

Use small commits with clear messages:

```text
agent-name: implement policy card retrieval
agent-name: add record renderer smoke test
```

Before asking for merge:

1. Rebase or merge latest `main`.
2. Run the tests for your area.
3. Include a short handoff note with changed files, test results, and any
   blocked assumptions.

## Merge Order

Suggested merge order:

1. `agent/question-record`
2. `agent/data-policy-rag`
3. `agent/frontend-ux`
4. `agent/voice-interpreter`
5. `agent/infra-models`
6. `agent/integration`

The integration branch keeps demo mode working throughout. Live model features
must not break deterministic demo mode.

## Cloud Claim Rule

If an agent enables a cloud provider, it must be guarded by `ALLOW_CLOUD=true`
and visually labelled in the UI. The offline demo path must keep working with
`ALLOW_CLOUD=false`.
