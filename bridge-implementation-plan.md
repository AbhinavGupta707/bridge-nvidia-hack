# Bridge Implementation Plan

This is the execution handoff for building Bridge, based on
`bridge-product-spec.md` and the NVIDIA Hack for Impact London event brief.

Current date assumption: Saturday, 6 June 2026. The event runs 5-7 June 2026,
so any "Friday setup" work in the product spec should be treated as immediate
catch-up work. The plan below prioritizes a credible Sunday demo over full
production completeness.

## 1. Product Read

Bridge is a local-first, multilingual public-service appointment assistant. It
does four jobs during and after a high-stakes public-service conversation:

1. Interpret live speech between a resident language and English.
2. Retrieve and surface relevant public-service policy with citations.
3. Suggest useful resident questions at the right moment.
4. Produce a structured, bilingual, timestamped record that can support appeal,
   ombudsman, or Subject Access Request workflows.

The strongest product thesis is not "translation". It is "local private
advocacy at the desk, with evidence afterwards". The record artifact is the
most defensible differentiator and must not be left until the end as a nice-to-have.

## 2. Event Fit And Compliance

The official event brief requires:

- Agentic application.
- Open models.
- Deployment on DGX Spark or HP ZGX Nano AI Station.
- Local-first intelligence and orchestration.
- Positive real-world impact.
- Open data from the City of London or London open data ecosystem as the
  project foundation.
- Track alignment with Public Services, with possible Economic Systems overlap.

Compliance choices:

- Primary track: Public Services.
- Hardware thesis: run local inference and orchestration on DGX Spark or ZGX
  Nano; avoid any runtime dependency on public internet for the final demo.
- Open-model thesis: use open-weight LLMs locally for translation, policy
  reasoning, and record generation.
- Voice sponsor fit: use ElevenLabs Scribe v2 Realtime and TTS if event access
  allows local/on-prem deployment. If only cloud access is available, use it as
  a quality/sponsor mode only and use the local fallback for the offline proof.
- Open data foundation: use London Datastore Census 2021 language proficiency
  data plus London/City public-service or homelessness data and policy pages.
  If judges interpret "City of London" strictly as City of London Corporation,
  the safest demo corpus should include City of London homelessness rights and
  prevention pages in addition to any Newham-specific corpus.

Important fact correction:

- The product spec says about 320,000 Londoners cannot speak English well or at
  all. A London Datastore Census 2021 excerpt says 303,000 cannot speak English
  well and 52,000 cannot speak English at all. Use "around 350,000 Londoners"
  unless the team re-validates an official source that supports a different
  number. Do not pitch an unverified statistic.

## 3. Demo North Star

The demo should be a three-minute appointment:

1. Resident starts a housing/homelessness conversation in Bengali, Arabic, or
   another selected language.
2. Caseworker sees English transcript and can reply in English.
3. Bridge shows visible activity from Interpreter, Policy, Question, and Record
   agents.
4. As the resident describes homelessness risk, the Policy Agent surfaces a
   cited policy card.
5. The Question Agent suggests one high-value prompt, such as asking about
   emergency accommodation or relief duty.
6. The network is disconnected or internet is disabled. The demo continues in
   local fallback mode.
7. One tap generates a bilingual, citation-backed record.

The demo must work even if live audio or a model call fails. Build a deterministic
scripted demo path first, then layer live capabilities on top.

## 4. MVP Definition

P0 means demo must work. P1 means strong if time. P2 means polish.

P0:

- Greenfield repo scaffold with backend, frontend, data ingest scripts, and demo
  fixtures.
- Shared event schema for all agents.
- Deterministic scripted demo mode using canned bilingual transcript/audio.
- Local RAG index over a small curated policy corpus.
- Policy cards with source title, URL/path, chunk excerpt, and confidence.
- Conservative Question Agent prompts from rule/checklist logic.
- Record Agent JSON plus readable HTML. PDF only if easy.
- Two-pane browser UI: resident view, caseworker view, agent activity strip,
  policy cards, question prompts, record preview.
- Offline proof path that does not depend on cloud APIs.

P1:

- Real microphone capture over WebSocket.
- Streaming ASR adapter with provider interface.
- Local Whisper fallback for speech-to-text.
- Local TTS fallback with Piper/Kokoro or browser speech synthesis if local TTS
  setup is blocked.
- Local LLM translation through Ollama/NIM.
- Exportable record file.

P2:

- ElevenLabs Scribe v2 Realtime and TTS integration.
- Barge-in support.
- Word-level timestamps and diarization if provider supports them.
- Encrypted local store.
- NemoClaw or NeMo Agent Toolkit integration for sponsor alignment.
- Full PDF formatting.

## 5. Proposed Repo Shape

Use this structure unless an implementation agent creates a materially better
scaffold:

```text
.
├── apps/
│   └── web/                         # React/Vite or Next.js client
├── services/
│   └── api/                         # FastAPI websocket backend
│       ├── bridge/
│       │   ├── agents/              # interpreter, policy, question, record
│       │   ├── audio/               # ASR/TTS adapters
│       │   ├── bus/                 # event bus and schemas
│       │   ├── rag/                 # retrieval/index/query
│       │   ├── records/             # record rendering
│       │   └── demo/                # scripted demo runner
│       └── tests/
├── data/
│   ├── sources/                     # raw downloaded docs, excluded if large
│   ├── processed/                   # chunks, metadata, indexes
│   └── fixtures/                    # demo transcripts and scenario data
├── scripts/
│   ├── ingest_corpus.py
│   ├── smoke_models.py
│   ├── run_demo_mode.py
│   └── validate_offline.sh
├── docs/
│   ├── demo-script.md
│   ├── data-sources.md
│   └── architecture.md
├── docker-compose.yml
├── .env.example
└── README.md
```

Keep large model weights, downloaded PDFs, and generated indexes out of git
unless the hackathon repo intentionally stores small fixtures.

## 6. Architecture Contracts

Build a small async event bus first. Every agent should consume and emit typed
events. This lets frontend, RAG, and record work proceed in parallel before live
audio is ready.

Core event types:

```json
{
  "type": "final_utterance",
  "session_id": "demo-001",
  "turn_id": "t-004",
  "speaker": "resident",
  "language": "bn",
  "text": "...",
  "translated_text": "...",
  "start_ms": 12000,
  "end_ms": 18400,
  "confidence": 0.91
}
```

Required events:

- `session_started`
- `audio_chunk`
- `partial_transcript`
- `final_utterance`
- `translation`
- `policy_card`
- `question_prompt`
- `commitment`
- `record_snapshot`
- `agent_status`
- `session_ended`

The UI should work entirely from this event stream. The demo runner should emit
the same events as the live path.

## 7. Agent Responsibilities

### 7.1 Interpreter Agent

P0:

- Consume scripted resident/caseworker utterances.
- Emit bilingual transcripts and translation events.
- Simulate streaming with timed partials.

P1:

- Browser mic capture to backend WebSocket.
- VAD/endpointing in browser or backend.
- ASR adapter interface:
  - `ElevenLabsRealtimeASR`
  - `WhisperLocalASR`
  - `DemoASR`
- Translation adapter interface:
  - `OllamaTranslator`
  - `NIMTranslator`
  - `DemoTranslator`
- TTS adapter interface:
  - `ElevenLabsTTS`
  - `PiperTTS` or `KokoroTTS`
  - `BrowserTTS`
  - `DemoTTS`

Acceptance criteria:

- A resident utterance appears in resident language and English.
- A caseworker reply appears in English and resident language.
- The rest of the system receives `final_utterance` events without knowing
  whether they came from live audio or demo mode.

### 7.2 Policy Agent

P0:

- Ingest a small curated policy corpus.
- Chunk text with metadata.
- Build dense index plus simple keyword fallback.
- Query on each final utterance and rolling conversation summary.
- Emit only cited policy cards.
- Suppress cards below a confidence threshold.

Policy card schema:

```json
{
  "type": "policy_card",
  "title": "Interim accommodation during relief duty",
  "claim": "If there is reason to believe the applicant is homeless, eligible, and in priority need, interim accommodation may be provided while the duty is assessed.",
  "source_title": "Rights of people who are homeless - City of London",
  "source_url": "https://www.cityoflondon.gov.uk/...",
  "source_span": "...",
  "confidence": 0.82,
  "trigger_turn_ids": ["t-004"]
}
```

Acceptance criteria:

- No uncited policy claims.
- The card is visibly tied to the conversation turn that triggered it.
- Retrieval works offline from local files/index.

### 7.3 Question Agent

P0:

- Rule/checklist based, not a complex LLM agent.
- Maintain a per-domain list of 8-12 high-value prompts.
- Trigger at most two prompts at once.
- Cooldown repeated prompts.
- Translate prompt into resident language using translation adapter or fixture.

Example prompt:

- English: "Ask whether the council believes it has reason to provide interim accommodation tonight."
- Bengali fixture translation for demo.

Acceptance criteria:

- Prompt appears only when relevant terms or policy cards appear.
- It is conservative, helpful, and never sounds like legal advice.

### 7.4 Record Agent

P0:

- Consume full event log.
- Generate structured JSON.
- Render HTML record with:
  - session summary
  - participants
  - bilingual transcript
  - policy citations
  - questions prompted
  - commitments and next steps
  - limitation/disclaimer

P1:

- PDF export from HTML.
- Better commitment extraction with local LLM.

Acceptance criteria:

- One tap produces a readable record in under 5 seconds in demo mode.
- Every policy claim in the record includes its citation.
- The record can be shown as the final "why this matters" artifact.

## 8. Data Plan

### 8.1 Minimum Corpus

Use a tiny but defensible corpus first:

- London Datastore Census 2021 English proficiency by borough/ward/LSOA.
- London Datastore homelessness provision by borough.
- City of London homelessness pages:
  - "Homeless, rough sleeping or at risk"
  - "Rights of people who are homeless"
  - "Preventing homelessness"
- Newham housing/homelessness pages and PDFs as optional demo depth:
  - Homelessness prevention and advice
  - Housing allocations
  - Housing allocation scheme PDF
  - Housing placements policy

If time is tight, prioritize City of London pages plus one Newham PDF. It is
better to have five well-cited documents than fifty noisy ones.

### 8.2 Source Registry

Create `data/sources.yml`:

```yaml
sources:
  - id: city_homeless_rights
    title: Rights of people who are homeless - City of London
    type: html
    url: https://www.cityoflondon.gov.uk/services/housing-and-homelessness/homelessness-or-at-risk/rights-of-people-who-are-homeless
    domain: housing
    authority: City of London
    priority: p0
  - id: newham_allocations_scheme
    title: London Borough of Newham Housing Allocation Scheme
    type: pdf
    url: https://www.newham.gov.uk/downloads/file/839/housing-allocation-policy
    domain: housing
    authority: Newham
    priority: p1
```

### 8.3 Ingestion Steps

1. Download sources to `data/sources/raw/`.
2. Extract text:
   - HTML with `trafilatura`, `readability-lxml`, or BeautifulSoup.
   - PDF with PyMuPDF.
3. Clean boilerplate.
4. Chunk at 300-500 tokens with overlap.
5. Attach metadata:
   - source id
   - title
   - URL
   - authority
   - page number or heading
   - chunk hash
6. Embed with BGE-M3 or multilingual-e5.
7. Store local index:
   - P0: LanceDB or simple FAISS plus JSON metadata.
   - P1: Qdrant local container.
8. Also build BM25 keyword index.
9. Query hybrid: combine dense top-k and keyword top-k, rerank lightly.

## 9. Model And Runtime Plan

Follow the layer-order instruction from `AGENTS.md`: if a model, feature, or
integration is missing or unavailable, first check registration, discovery,
install state, and official activation flows. Only debug permissions/runtime
after the feature is actually present.

### 9.1 First-Hour Model Discovery

On the Spark/ZGX:

1. Confirm OS and architecture: `uname -m`, `lsb_release -a`.
2. Confirm GPU visibility: `nvidia-smi`.
3. Confirm Docker and NVIDIA container runtime.
4. Confirm Ollama and/or NIM availability.
5. List already-installed models before pulling anything.
6. Confirm ElevenLabs access mode with sponsor reps:
   - on-prem/on-device granted
   - cloud API only
   - no access yet
7. Run one smoke prompt through the selected LLM.
8. Run one local embedding smoke test.
9. Run one local ASR/TTS fallback smoke test.

### 9.2 Recommended Model Ladder

Use the first working rung. Do not lose half a day chasing the ideal model.

Fast live path:

1. NVIDIA-tuned Nemotron/Qwen model already present on the device.
2. Qwen 2.5/3 7B-14B instruct via Ollama/NIM.
3. Llama 3.1/3.2 8B instruct.
4. Demo translation fixtures.

Policy/record reasoning:

1. NVIDIA-tuned 30B-40B open model if present and fast enough.
2. Qwen 2.5/3 32B instruct.
3. Llama 3.3 70B quantized if loading and decode speed are acceptable.
4. Fast model plus stricter prompts.

Embeddings:

1. BGE-M3.
2. multilingual-e5-large.
3. Smaller multilingual sentence-transformer if wheels or memory block the
   better options.

ASR:

1. ElevenLabs on-device/on-prem Scribe if granted.
2. Whisper large-v3 or faster-whisper local.
3. Browser speech recognition only as non-offline dev fallback.
4. Demo transcripts.

TTS:

1. ElevenLabs on-device/on-prem if granted.
2. Piper/Kokoro local.
3. Browser speech synthesis as dev fallback.
4. Pre-rendered demo audio.

### 9.3 Runtime Modes

Expose explicit modes with environment variables:

```env
BRIDGE_MODE=demo        # demo | hybrid | live
ASR_PROVIDER=demo       # demo | elevenlabs | whisper
TTS_PROVIDER=demo       # demo | elevenlabs | piper | browser
LLM_PROVIDER=demo       # demo | ollama | nim
RAG_PROVIDER=local      # local | qdrant | disabled
ALLOW_CLOUD=false
```

The UI should visibly show a local/offline indicator. If `ALLOW_CLOUD=true`,
do not claim that no data leaves the box.

## 10. Frontend Plan

The first screen is the actual tool, not a landing page.

Required views:

- Session setup/consent view.
- Live appointment view.
- End-of-session record view.

Live appointment layout:

- Left/resident pane:
  - large resident-language transcript
  - translated caseworker speech
  - question prompts
  - consent/recording state
- Right/caseworker pane:
  - English transcript
  - live policy cards
  - commitments/next steps
- Bottom/top activity strip:
  - Interpreter
  - Policy
  - Question
  - Record
  - each with idle/listening/thinking/emitting/error states

Design constraints:

- Dense, calm public-service UI, not a marketing hero.
- No decorative gradients or oversized card stacks.
- Strong offline/local status.
- Text must not overflow on a tablet viewport.
- The record view must feel official and legible.

## 11. Backend API Plan

Endpoints:

- `GET /health`
- `GET /session/{id}`
- `POST /session`
- `POST /session/{id}/end`
- `GET /session/{id}/record.json`
- `GET /session/{id}/record.html`
- `WS /ws/session/{id}`

WebSocket inbound messages:

- `start_session`
- `audio_chunk`
- `manual_utterance`
- `end_session`
- `generate_record`
- `set_mode`

WebSocket outbound messages:

- all bus events listed in section 6.

Implementation order:

1. FastAPI app with health check.
2. In-memory session manager.
3. Event bus.
4. Demo runner that emits events.
5. Frontend WebSocket integration.
6. Agents attached to bus.
7. Live audio path.

## 12. Parallel Workstreams

The work can be parallelized safely if contracts and file ownership are set
early. The first agent must create the repo scaffold and event schemas, then
parallel agents can work without stepping on each other.

### 12.0 GitHub Branch And Session Protocol

The project should run as a public GitHub repository with `main` reserved for
reviewed integration checkpoints. Parallel Codex sessions must never work
directly on `main`.

Initial setup:

1. Create the GitHub repo.
2. Commit this scaffold to `main`.
3. Push `main`.
4. Launch each parallel session from `main` into its own branch.

Branch names:

- `agent/infra-models`
- `agent/voice-interpreter`
- `agent/data-policy-rag`
- `agent/frontend-ux`
- `agent/question-record`
- `agent/integration`

Conflict avoidance rules:

- Each agent owns the files listed in its workstream section below.
- `services/api/bridge/bus/events.py` is a shared contract. Do not change event
  names, required fields, or session semantics without first landing the change
  through `agent/integration`.
- Agents may add optional event fields only if existing demo-mode consumers keep
  working.
- Every branch must keep `BRIDGE_MODE=demo` working, even if live model work is
  incomplete.
- Any cloud provider must be guarded by `ALLOW_CLOUD=true`; the offline path
  must remain available with `ALLOW_CLOUD=false`.
- Before merge, each branch should pull/rebase latest `main`, run its local
  tests, and include a short handoff note with changed files, verification, and
  blockers.

Suggested merge order:

1. `agent/question-record`
2. `agent/data-policy-rag`
3. `agent/frontend-ux`
4. `agent/voice-interpreter`
5. `agent/infra-models`
6. `agent/integration`

The integration branch is responsible for final wiring, demo runbook updates,
and keeping the main branch demoable after every merge.

### Agent 0: Integration Lead

Owns:

- `README.md`
- `docker-compose.yml`
- `.env.example`
- root package/tooling
- final merge
- demo script

Tasks:

- Create scaffold and run commands.
- Define event schemas.
- Keep modes working.
- Integrate parallel work.
- Own final demo rehearsal.

Do not delegate acceptance decisions away from this role.

### Agent A: Hardware, Infra, Models

Owns:

- `scripts/smoke_models.py`
- `scripts/validate_offline.sh`
- `docs/model-runtime.md`
- deployment/docker files with Agent 0 coordination

Tasks:

- Discover Spark/ZGX model/runtime state.
- Check official activation flows before debugging missing integrations.
- Stand up Ollama/NIM path.
- Smoke test local LLM and embedding model.
- Determine ElevenLabs access mode.
- Document exact commands that worked.
- Produce fallback recommendation within 90 minutes.

Non-conflict boundary:

- Does not touch frontend.
- Does not change event schemas without Agent 0.

### Agent B: Voice And Interpreter

Owns:

- `services/api/bridge/audio/`
- `services/api/bridge/agents/interpreter.py`
- demo audio/transcript fixtures relevant to voice

Tasks:

- Implement ASR/TTS/translation provider interfaces.
- Implement demo interpreter path first.
- Add Whisper/Piper or browser fallback if possible.
- Add ElevenLabs adapter only after access is confirmed.
- Emit `partial_transcript`, `final_utterance`, and `translation` events.

Non-conflict boundary:

- Depends only on event schemas and adapter config.
- Does not modify RAG internals.

### Agent C: Data And Policy RAG

Owns:

- `data/sources.yml`
- `scripts/ingest_corpus.py`
- `services/api/bridge/rag/`
- `services/api/bridge/agents/policy.py`
- `docs/data-sources.md`

Tasks:

- Build source registry.
- Download and parse minimum corpus.
- Chunk, embed, and index.
- Implement retrieval and policy card generation.
- Guarantee citation metadata.
- Add a retrieval smoke test for the demo scenario.

Non-conflict boundary:

- Does not touch live audio.
- Emits `policy_card` events only through the shared bus.

### Agent D: Frontend UX

Owns:

- `apps/web/`

Tasks:

- Build session setup/consent screen.
- Build two-pane live appointment screen.
- Build activity strip.
- Build policy card and question prompt surfaces.
- Build record preview screen.
- Connect to WebSocket demo stream.

Non-conflict boundary:

- Works against mocked WebSocket events until backend is ready.
- Does not modify backend except generated client types if agreed.

### Agent E: Question And Record

Owns:

- `services/api/bridge/agents/question.py`
- `services/api/bridge/agents/record.py`
- `services/api/bridge/records/`
- `data/fixtures/demo_scenario.*`
- `docs/demo-script.md`

Tasks:

- Write demo scenario transcript.
- Implement question checklist logic.
- Implement record JSON and HTML renderer.
- Extract commitments and next steps.
- Ensure final record carries citations.
- Write final three-minute script and fallback beats.

Non-conflict boundary:

- Does not change RAG retrieval.
- Consumes events and emits `question_prompt`, `commitment`, and
  `record_snapshot`.

## 13. Suggested Spawn Prompts

Use these if launching parallel coding agents.

Agent A prompt:

```text
You are Agent A for Bridge. Own hardware/infra/model readiness only. In this
greenfield repo, create scripts to discover runtime state, smoke test Ollama/NIM,
embedding, ASR/TTS fallback, and offline readiness. Follow layer-order diagnosis:
if a feature is missing, first check registration/discovery/install state and
official activation flow before runtime/permission debugging. Do not touch
frontend or RAG internals. Deliver exact commands, env vars, and fallback choice.
```

Agent B prompt:

```text
You are Agent B for Bridge. Own voice and Interpreter Agent. Implement provider
interfaces for ASR, translation, and TTS, with demo providers first and live
providers behind env flags. Emit shared bus events for partial transcript, final
utterance, translation, and agent status. Do not touch frontend or RAG. The demo
must work from fixtures even before live audio works.
```

Agent C prompt:

```text
You are Agent C for Bridge. Own data ingestion and Policy Agent RAG. Build
data/sources.yml, ingestion, chunking, local indexing, hybrid retrieval, and
cited policy card generation. Use City/London open public-service data and
policy pages first. Never emit an uncited policy claim. Do not touch live audio
or frontend except by documenting the policy_card event shape.
```

Agent D prompt:

```text
You are Agent D for Bridge. Own the web client. Build the actual appointment
tool as the first screen: consent/setup, two synchronized transcript panes,
policy cards, question prompts, agent activity strip, and record preview. Work
against mocked WebSocket events until backend is ready. Keep the design calm,
dense, tablet-friendly, and public-service appropriate.
```

Agent E prompt:

```text
You are Agent E for Bridge. Own Question Agent, Record Agent, fixtures, and demo
script. Implement conservative checklist prompts and a one-tap JSON/HTML record
from the event log. Create a compelling three-minute scripted scenario and
fallback path. Every cited policy in the record must include source metadata.
```

## 14. Timebox Plan From Saturday 6 June

### T+0 to T+2 hours: Scaffold and proof skeleton

Goal:

- One command starts backend and frontend.
- Demo stream emits fake events to UI.
- Event schemas stable.

Tasks:

- Agent 0 scaffolds repo.
- Agent D starts UI against mock events.
- Agent E writes demo transcript.
- Agent C creates source registry.
- Agent A starts hardware/model discovery.

Exit criteria:

- Browser shows a scripted appointment advancing through events.
- No live model dependency yet.

### T+2 to T+5 hours: RAG and record become real

Goal:

- Demo policy cards and record are generated from local data.

Tasks:

- Agent C ingests minimum corpus and emits cited policy cards.
- Agent E renders JSON/HTML record.
- Agent D integrates real policy/record event surfaces.
- Agent B implements demo interpreter adapters.

Exit criteria:

- Scripted demo shows policy card at the right moment.
- One tap generates record.

### T+5 to T+8 hours: Live path and model smoke

Goal:

- At least one real local model path works.

Tasks:

- Agent A confirms LLM/embedding/voice fallback.
- Agent B wires live mic or manual utterance to backend.
- Agent C switches retrieval to real embeddings if available.
- Agent 0 keeps `BRIDGE_MODE=demo` stable while live work proceeds.

Exit criteria:

- Live or manual utterance can trigger a real policy card.
- Demo mode still works.

### T+8 to T+11 hours: Offline proof and polish

Goal:

- Make the demo robust.

Tasks:

- Agent A validates no internet needed for selected demo mode.
- Agent D polishes layout for tablet/laptop.
- Agent E tightens script and record language.
- Agent 0 creates runbook.

Exit criteria:

- Team can perform full demo twice without edits.
- A fallback mode is one env var away.

### Sunday 7 June morning: Rehearsal and risk burn-down

Goal:

- Stop adding features unless they directly improve the demo.

Tasks:

- Rehearse three times.
- Measure perceived latency if live path is used.
- Check citations open locally.
- Check audio levels.
- Prepare fallback explanation if ElevenLabs is cloud-only.

Exit criteria:

- One primary demo path.
- One fallback demo path.
- One clear pitch line for every architectural tradeoff.

## 15. Implementation Backlog

P0 backend:

- FastAPI app and health endpoint.
- Session manager.
- Event bus.
- Shared Pydantic event models.
- Demo runner.
- WebSocket endpoint.
- Provider config from env.

P0 frontend:

- Vite/React or Next app.
- WebSocket event reducer.
- Consent/setup view.
- Appointment view.
- Activity strip.
- Policy cards.
- Question prompts.
- Record preview.

P0 data/RAG:

- Source registry.
- Corpus downloader.
- HTML/PDF parser.
- Chunker.
- Embedding/index fallback.
- Policy card generator.
- Retrieval smoke test.

P0 agents:

- Interpreter demo adapter.
- Policy Agent.
- Question Agent.
- Record Agent.
- Agent status events.

P0 demo:

- Bilingual scenario transcript.
- At least one pre-rendered/audio fallback if possible.
- Demo script.
- Offline validation checklist.

P1:

- Mic capture.
- Local ASR.
- Local TTS.
- Local LLM translation.
- PDF export.
- Better commitment extraction.

P2:

- ElevenLabs on-prem/on-device adapters.
- NemoClaw/NeMo Agent Toolkit wrapper for non-live agents.
- Encrypted storage.
- Barge-in.
- Diarized word timestamps.

## 16. Test And Verification Plan

Automated tests:

- Event schema validation.
- Demo runner emits expected event order.
- Question Agent cooldown and relevance rules.
- Policy Agent suppresses uncited claims.
- Record Agent includes citations for policy claims.
- Ingest script creates chunks with source metadata.

Manual tests:

- Start backend and frontend from README.
- Run `BRIDGE_MODE=demo`.
- Step through the scripted demo.
- Generate record.
- Disable internet and repeat.
- If live mode exists, test mic permissions and audio path.
- If ElevenLabs is enabled, test with `ALLOW_CLOUD=false` first, then only use
  cloud path with explicit label.

Demo acceptance checklist:

- UI loads in under 5 seconds.
- Agent activity visibly changes during the demo.
- At least one policy card is cited.
- At least one resident question prompt appears.
- Record appears in under 5 seconds after tap.
- Offline mode still works.
- Pitch statistic is verified or softened.

## 17. Risk Register

High risk: Event data requirement interpreted strictly as City of London
Corporation data.

- Mitigation: include City of London homelessness pages and/or public datasets
  in the P0 corpus. Use Newham as optional extension for language-impact depth.

High risk: Voice stack unavailable or cloud-only.

- Mitigation: demo mode and local fallback must exist before live voice work.
  Do not claim no data leaves the box when using cloud voice.

High risk: ARM64 dependency friction on Spark/ZGX.

- Mitigation: prefer preinstalled runtimes, NVIDIA containers, Ollama/NIM, and
  simple Python packages. Avoid exotic wheels unless already present.

High risk: RAG hallucination or weak citations.

- Mitigation: retrieve first, cite always, suppress low confidence, use template
  claims for demo if needed.

High risk: Open multilingual quality weak for chosen language.

- Mitigation: benchmark early. Choose demo language based on quality, not just
  impact story. Keep fixtures ready.

High risk: Integration conflict between parallel agents.

- Mitigation: event schemas and file ownership are locked early. Demo mode is
  protected by Agent 0.

## 18. Pitch Guidance For Builders

Lead with:

- "Bridge is not a translation bot. It is a private advocate and record keeper
  for people navigating public services."

Defend local-first with:

- "The conversation may include health, immigration, safeguarding, or domestic
  abuse details. Local inference keeps it in the room and removes the network
  latency floor."

Defend the hardware with:

- "The box can keep ASR, TTS, embeddings, a fast LLM, and a deeper reasoning
  model resident at once. The architecture uses many concurrent model contexts,
  not one huge model in the live loop."

Defend scope:

- "For the weekend, we focused on one public-service domain and a small cited
  corpus. The architecture is built to add boroughs and domains."

Defend safety:

- "Bridge does not make legal or clinical decisions. It surfaces cited published
  policy, suggests questions, and gives the resident an evidence record."

## 19. Source Links To Keep In The Repo

- NVIDIA Hack for Impact London event brief:
  https://luma.com/NVIDIA-Hack-London
- NVIDIA DGX Spark user guide:
  https://docs.nvidia.com/dgx/dgx-spark/index.html
- NVIDIA DGX Spark hardware overview:
  https://docs.nvidia.com/dgx/dgx-spark/hardware.html
- NVIDIA DGX Spark porting guide:
  https://docs.nvidia.com/dgx/dgx-spark-porting-guide/overview.html
- NVIDIA NemoClaw overview:
  https://docs.nvidia.com/nemoclaw/latest/home
- ElevenLabs Scribe v2 Realtime:
  https://elevenlabs.io/realtime-speech-to-text
- ElevenLabs models documentation:
  https://elevenlabs.io/docs/models
- ElevenLabs on-prem deployments:
  https://elevenlabs.io/on-prem-deployments
- London Datastore guidance:
  https://data.london.gov.uk/guidance/finding-and-accessing-data/
- London Datastore Census 2021 language dataset:
  https://data.london.gov.uk/dataset/2021-census-wards-ethnicity-language-identity-religion/
- London Datastore homelessness provision:
  https://data.london.gov.uk/dataset/homelessness
- City of London homelessness page:
  https://www.cityoflondon.gov.uk/services/housing-and-homelessness/homelessness-or-at-risk
- City of London rights of people who are homeless:
  https://www.cityoflondon.gov.uk/services/housing-and-homelessness/homelessness-or-at-risk/rights-of-people-who-are-homeless
- City of London preventing homelessness:
  https://www.cityoflondon.gov.uk/services/housing-and-homelessness/homelessness-or-at-risk/preventing-homelessness
- Newham homelessness prevention and advice:
  https://www.newham.gov.uk/housing-homes-homelessness/homelessness-prevention-advice/1
- Newham housing allocations:
  https://www.newham.gov.uk/housing-homes-homelessness/apply-council-housing/1
- Newham housing allocation scheme PDF:
  https://www.newham.gov.uk/downloads/file/839/housing-allocation-policy

## 20. Definition Of Done

Bridge is demo-ready when:

- The repo starts locally from documented commands.
- Demo mode works without network.
- The UI shows all four agents doing useful work.
- A policy card appears with a source citation.
- A resident question prompt appears.
- A record is generated and looks credible.
- The pitch uses a verified or cautious impact statistic.
- The team can explain exactly what runs locally, what uses open models, and
  what changes if ElevenLabs access is cloud-only.
