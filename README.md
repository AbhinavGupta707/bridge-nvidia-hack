# Bridge

Bridge is a local-first, multi-agent public-service appointment assistant for
Londoners with limited English proficiency. It is designed for the NVIDIA Hack
for Impact London brief: open models, local edge deployment on DGX Spark or HP
ZGX Nano AI Station, London open data, and measurable public-service impact.

## Current Status

This repository is at architecture scaffold stage. It contains:

- the product specification
- the implementation handoff plan
- branch and parallel-agent workflow rules
- backend/frontend/data scaffolding
- shared event contracts for the four agents
- curated source registry placeholders

The first working target is deterministic demo mode. Live audio, local model
serving, and ElevenLabs integrations should be layered on top of the same event
contracts.

## Core Demo

The Sunday demo should show:

1. a bilingual housing/homelessness appointment
2. live Interpreter, Policy, Question, and Record agent activity
3. a cited policy card grounded in local corpus data
4. a conservative resident question prompt
5. an offline/local proof
6. a one-tap bilingual record with citations

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

