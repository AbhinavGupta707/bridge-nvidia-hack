# Demo Script

## Three-Minute Flow

Bridge is a private, local advocate and record keeper for people navigating
public services in another language. This demo uses a Bengali housing options
appointment in the City of London.

### 0:00-0:25 - Frame

Say:

"A resident is at the housing desk. They have limited English, a child with
them, and nowhere safe tonight. Bridge runs four local agents: Interpreter,
Policy, Question, and Record."

Show:

- Offline/local indicator visible.
- Interpreter, Policy, Question, and Record agents idle.
- Scenario loaded from `data/fixtures/demo_scenario.json`.

### 0:25-0:55 - Interpreter Agent

Play resident turn `t-001` in Bengali. The caseworker sees:

"I have been told to leave where I am staying tonight. I do not know where I can
sleep."

Then play caseworker turn `t-002`. The resident pane shows Bengali output.

Say:

"The point is not just translation. The final utterance is a structured event
that every other agent can use."

### 0:55-1:30 - Policy Agent

Play resident turn `t-003`: the resident says their six-year-old child is with
them and there is no family option tonight.

Show cited policy cards:

- City of London rights page: relief duty and interim accommodation.
- GOV.UK Homelessness Code of Guidance: priority need and interim duty context.

Say:

"Bridge only surfaces policy claims with source metadata: title, URL, authority,
source span, confidence, and the turns that triggered it."

### 1:30-2:00 - Question Agent

Show one conservative prompt in Bengali and English:

"Ask what safe option is available for tonight while they review your
situation."

Say:

"The Question Agent is checklist-based. It does not decide the law for the
resident; it helps them ask the question that often gets missed under pressure."

### 2:00-2:25 - Fallback Proof

Disable the network or switch provider status to deterministic local mode.

Say:

"If live audio or a cloud sponsor mode fails, the demo continues from the local
event log. We do not claim 'nothing leaves the box' unless `ALLOW_CLOUD=false`
and every selected provider is local."

Play turns `t-005` through `t-008`: documents, written contact details, and
out-of-hours follow-up.

### 2:25-3:00 - Record Agent

Tap Generate Record.

Show the HTML record sections:

- session summary
- participants
- bilingual transcript
- policy citations
- question prompts
- commitments
- next steps
- safety disclaimer

Say:

"The record is why Bridge matters. The resident leaves with a bilingual,
timestamped account of what was said, what was promised, what to ask next, and
the sources behind every policy claim."

## Presenter Backup Lines

If audio fails:

"We are switching to fixture-backed ASR. The same final utterance events are
emitted, so Policy, Question, and Record keep working."

If policy retrieval fails:

"We are using the curated local policy-card fixture. Notice the record still
refuses uncited policy claims."

If HTML export fails:

"The JSON record is the source of truth. The HTML renderer is a readable view of
the same record."

## Run Commands

```bash
cp .env.example .env
docker compose up --build
```

Fast event-stream check:

```bash
python3 scripts/run_demo_mode.py --session-id demo-001
```

## Demo Safety Line

Bridge does not replace legal advice, clinical judgement, or a qualified
interpreter for legally binding decisions. It surfaces cited public information,
helps residents ask better questions, and gives them an evidence record.

Only use "nothing leaves the box" language when `ALLOW_CLOUD=false` and the
selected ASR, TTS, LLM, and RAG providers are local or demo fixtures.
