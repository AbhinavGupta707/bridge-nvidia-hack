# Bridge — Product & Technical Specification

**A multilingual, multi-agent advocate for Londoners navigating public services.**

| | |
|---|---|
| **Version** | 0.1 (hackathon build spec) |
| **Event** | NVIDIA Hack for Impact — London, 5–7 June 2026 |
| **Track** | Public Services (touches Economic Systems) |
| **Hardware** | NVIDIA DGX Spark / ZGX Nano (GB10 Grace Blackwell, 128 GB unified memory) |
| **Model sponsor fit** | ElevenLabs (Scribe v2 ASR + multilingual TTS, on-device) |
| **One-liner** | A private, on-device voice agent that sits on a council desk or in a clinic room and lets a resident who doesn't speak English well attend a public-service appointment with a real-time interpreter, a policy advocate, and an automatic record-keeper — none of which ever sends their data to the cloud. |

---

## 1. Executive summary

Bridge is a **local-first, multi-agent voice system** that runs entirely on a single DGX Spark. During a live public-service interaction (housing assessment, GP appointment, benefits review, school-admissions meeting, social-care review), four specialised agents run concurrently in the Spark's unified memory:

1. **Interpreter Agent** — real-time, two-way speech-to-speech translation between the resident's language and English.
2. **Policy Agent** — retrieval-grounded over the specific borough's or trust's published policies; surfaces the rule or entitlement that applies as the conversation unfolds, with citations.
3. **Question Agent** — listens to the conversation and prompts the resident with the question they didn't think to ask.
4. **Record Agent** — produces a timestamped, structured record afterwards (what was said, which policies were cited, what was promised, next steps), formatted for appeals, ombudsman complaints, and Subject Access Requests.

The product exists *because* it runs locally. The data involved — immigration status, domestic abuse disclosures, mental-health history, child-protection details — is the most sensitive the state holds, and routing it to a cloud LLM cannot clear the UK GDPR / ICO and clinical-governance bar for this conversation type. A DGX Spark on the desk can. Local execution also removes the cloud network round-trip (typically 400–500 ms for a cloud STT→LLM→TTS loop), which is what makes natural turn-taking possible.

This spec is written so a team of 3–5 can build a credible, demo-ready prototype across the weekend and defend every architectural choice to a technical judge.

---

## 2. Problem statement (verified)

- **English-language barrier in London is the highest of any UK region.** ONS Census 2021: about **4.1% of Londoners (~320,000 people) cannot speak English well or at all** — the largest share of any UK region. A further large fraction speak English as a second language. Boroughs such as **Newham, Brent, Ealing and Harrow** have the highest share of residents whose main language is not English.
- **These residents still attend high-stakes appointments alone** — GP visits, housing assessments, benefits reviews, social-care reviews, school admissions — often relying on a child to interpret, which is inappropriate for sensitive content and frequently inaccurate.
- **The cost is measurable**: missed entitlements, denied or delayed applications, repeat appointments, safeguarding risks, and downstream ombudsman escalations and appeals — all of which are more expensive for the state than getting the first interaction right.
- **Professional interpreter provision is thin and slow.** Phone-interpreter lines have wait times, drop-outs, and cannot produce a usable record of what was agreed.

A judge can verify the headline statistic in under a minute against the ONS Census 2021 language bulletin.

---

## 3. Users and use cases

### 3.1 Primary user
A London resident with limited English proficiency attending a public-service appointment. Top target languages (London prevalence): **Bengali, Urdu, Punjabi, Polish, Romanian, Arabic, Somali, Gujarati, Tamil, Portuguese, Turkish, Spanish, French** (prioritised per borough using ONS borough-level proficiency data).

### 3.2 Secondary users
- **Caseworker / clinician / housing officer** — the public-service professional on the other side of the desk, who gets a clean English transcript and a record.
- **The resident's advocate / family member** — receives the structured record for follow-up.

### 3.3 Core scenarios
1. **Housing options interview** (demo scenario): a Bengali-speaking resident in Newham presenting as homeless. Bridge interprets, surfaces the borough's allocation-scheme entitlements, prompts the resident to ask about emergency accommodation duty, and produces an appeal-ready record.
2. **GP appointment**: an Arabic-speaking patient describing symptoms; Bridge interprets, flags relevant patient rights (e.g. interpreter entitlement), and records the care plan.
3. **Benefits review**: a Romanian-speaking claimant; Bridge interprets, surfaces Council Tax Support / discretionary-fund eligibility, and records what was promised.

### 3.4 Explicit non-goals
- Bridge **does not replace a professional interpreter for legally binding decisions**; it is decision-support and accessibility augmentation, with that limitation stated to the user.
- Bridge **does not give legal advice**; it surfaces published policy with citations and lets the human decide.

---

## 4. Why local, why the DGX Spark (the technical thesis)

This section is the spine of the pitch. Memorise it.

### 4.1 Why it must be local
- **Data sensitivity / legal.** The conversation routinely contains UK GDPR special-category data (Article 9: health, etc.) and immigration/safeguarding data. Sending raw audio of these conversations to a third-party cloud LLM is, for many councils and NHS trusts, a non-starter under their information-governance and clinical-governance regimes. On-device processing keeps the data inside the room and inside the public body's control.
- **Latency.** Natural turn-taking needs the response to *start* fast. A cloud STT→LLM→TTS loop is typically **400–500 ms before you account for model think-time**, purely from network round-trips and queueing. Removing the network removes that floor.
- **Resilience.** Works in a clinic room or community centre with poor or no connectivity.

### 4.2 Why the Spark specifically
Bridge runs **five model contexts simultaneously** — fast conversational LLM, deeper reasoning/policy LLM, streaming ASR, multilingual TTS, and an embedding model + vector index — and they must all be **addressable at once** to keep the voice loop unbroken.

- The DGX Spark's **128 GB of coherent, unified CPU/GPU memory (LPDDR5X)** holds them in a single pool. As models hand off mid-conversation, there is **no paging across PCIe** between separate GPU VRAM and system RAM.
- A discrete consumer GPU (e.g. 24 GB) plus separate system RAM cannot keep this stack resident; it must swap weights/contexts across PCIe, which breaks real-time turn-taking.
- **Honest caveat we design around:** the Spark's memory *bandwidth* (~273 GB/s) means a single very large model (120 B+) decodes slowly (tens of tokens/sec). Bridge therefore does **not** rely on one giant model for the live loop — it uses a small fast model for turn-taking and reserves the large model for asynchronous policy reasoning (see §6.2). This is the architecture that fits what the hardware is actually good at: many models resident, moderate sizes, concurrent.

---

## 5. System architecture

### 5.1 High-level diagram

```
 ┌──────────────────────────── CLIENT (tablet / laptop / kiosk) ────────────────────────────┐
 │  Mic capture + VAD  │  Resident-language UI  │  Caseworker English view  │  Consent screen │
 └───────────────▲───────────────────────────────────────────────────────────────▼──────────┘
                 │  encrypted WebSocket (audio in / audio + events out) over LAN  │
 ┌───────────────┴───────────────────────────────────────────────────────────────┴──────────┐
 │                              DGX SPARK  (Ubuntu 24.04 ARM64, DGX OS)                        │
 │                                                                                            │
 │   ┌────────────────────────────  ORCHESTRATOR (async event bus)  ───────────────────────┐  │
 │   │                                                                                      │  │
 │   │   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐  │  │
 │   │   │ Interpreter │   │   Policy     │   │   Question   │   │      Record          │  │  │
 │   │   │   Agent     │   │   Agent      │   │   Agent      │   │      Agent           │  │  │
 │   │   └─────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────────┬───────────┘  │  │
 │   └─────────┼──────────────────┼──────────────────┼─────────────────────┼──────────────┘  │
 │             │                  │                  │                     │                  │
 │   ┌─────────▼──────────────────▼──────────────────▼─────────────────────▼───────────────┐ │
 │   │  SHARED MODEL POOL  (single 128 GB unified memory space, no PCIe paging)             │ │
 │   │  • ASR: ElevenLabs Scribe v2 on-device (Whisper-large-v3 fallback)                   │ │
 │   │  • Fast LLM: 8–14 B (turn-taking, interpretation)                                    │ │
 │   │  • Reasoning LLM: 70–72 B 4-bit (policy reasoning, async)                             │ │
 │   │  • TTS: ElevenLabs multilingual on-device (Kokoro/Piper fallback)                    │ │
 │   │  • Embeddings: multilingual (BGE-M3 / e5-large) + in-memory vector index             │ │
 │   └──────────────────────────────────────────────────────────────────────────────────┘ │
 │                                                                                            │
 │   Local encrypted store (records, consent log, audit trail)  ── exported on demand ──►     │
 └────────────────────────────────────────────────────────────────────────────────────────┘
            NO inference-time egress to the public internet (the sovereignty guarantee)
```

### 5.2 The four agents in detail

**Interpreter Agent (real-time path).**
Owns the live voice loop. Pipeline: client VAD/endpointing → streamed audio → **Scribe v2** ASR (with speaker diarization + word-level timestamps) → **fast LLM** for translation + light disambiguation between turns → **ElevenLabs multilingual TTS** → streamed audio back. Bidirectional: resident-language ⇄ English. Streaming throughout (partial transcripts, partial speech) with barge-in support so either party can interrupt.

**Policy Agent (grounding path).**
Runs asynchronously off the conversation stream. Continuously embeds the rolling transcript, retrieves the most relevant passages from the borough/trust policy corpus (hybrid dense+keyword search), and asks the **reasoning LLM** "given what's being discussed, what entitlement or rule applies?" Emits cards to the caseworker view: *the rule, the entitlement, the source citation*. Never invents policy — every claim is anchored to a retrieved source span or it is not shown.

**Question Agent.**
A lightweight monitor on the transcript that pattern-matches the conversation against a checklist of high-value, commonly-missed questions for the service domain (e.g. "Have you asked whether you're owed a relief duty?"). Surfaces 0–2 prompts at a time in the resident's language, spoken or on-screen. Deliberately conservative to avoid noise.

**Record Agent.**
Post-conversation (and incrementally during). Consumes the diarized, timestamped transcript + the policy citations + extracted commitments and produces a structured record: who attended, what was said (bilingual), which policies were cited (with sources), what was promised, agreed next steps, and a timeline. Output formats: a human-readable PDF/HTML and a structured JSON. Designed to be directly usable for an appeal, an ombudsman complaint, or a Subject Access Request. **This is Bridge's most defensible, least-copied feature — lead the demo on it.**

### 5.3 Orchestration
A lightweight **async event bus** (Python `asyncio`) is preferable to a heavyweight agent framework for the real-time loop, because you need tight control over latency and streaming. The bus carries: `audio_chunk`, `partial_transcript`, `final_utterance`, `translation`, `policy_card`, `question_prompt`, `commitment`. Optionally wrap the non-real-time agents (Policy, Question, Record) in **NVIDIA's NeMo Agent toolkit / NemoClaw** for sponsor alignment and sandboxed tool execution, while keeping the Interpreter loop hand-rolled for speed.

---

## 6. Model selection and rationale

### 6.1 Components

| Role | Primary choice | Fallback / alt | Notes |
|---|---|---|---|
| ASR | ElevenLabs **Scribe v2** (on-device) | Whisper-large-v3 (local) | Scribe v2 gives ~150 ms p50 streaming transcription, diarization, word timestamps — directly powers the Record Agent. |
| Fast LLM (turn-taking) | Qwen2.5-14B-Instruct or Llama 3.1 8B | Gemma 2 9B | Must be quick to first token; handles interpretation + light disambiguation. |
| Reasoning LLM (policy) | Qwen2.5-72B or **Aya Expanse 32B** | Llama 3.3 70B | Aya is explicitly multilingual; benchmark on target languages before committing. Runs async, so its slower decode is acceptable. |
| TTS | ElevenLabs **multilingual** (on-device) | Kokoro (82 M) / Piper | Expressive, multilingual; on-device keeps audio in-box. |
| Embeddings | BGE-M3 (multilingual) | multilingual-e5-large | Cross-lingual retrieval so a Bengali utterance retrieves English policy. |

### 6.2 The dual-LLM pattern (key design decision)
Run **two** language models resident at once:
- a **small fast model** drives the interpretation loop and turn-taking (low latency is everything here), and
- a **large reasoning model** is invoked asynchronously by the Policy Agent for grounded policy reasoning (latency-tolerant because it produces background cards, not the live voice).

This is only practical because unified memory lets both stay resident with the ASR, TTS, embedding model and vector index — the concurrency that justifies the Spark.

### 6.3 Language quality — the honest risk
Open multilingual model quality **varies sharply by language**. Polish/Romanian/Spanish/French are strong; Somali, Bengali, Punjabi, and Gujarati can be weaker. **Action:** benchmark the shortlist on 2–3 target languages early (Saturday morning), pick the demo languages where quality is defensibly good, and state the limitation openly. Do not claim flawless coverage of 20 languages; claim strong coverage of the demo languages and a clear path to evaluate the rest.

---

## 7. Memory and latency budgets

### 7.1 Memory budget (fits 128 GB with headroom)

| Component | Approx. resident size |
|---|---|
| Reasoning LLM 70–72 B @ 4-bit (weights) | ~40 GB |
| Reasoning LLM KV cache (long context + RAG) | ~8–14 GB |
| Fast LLM 8–14 B @ 4–8-bit | ~6–10 GB |
| ASR (Scribe v2 / Whisper) | ~2–4 GB |
| TTS (multilingual) | ~2–5 GB |
| Embedding model | ~1–2 GB |
| Vector index (one borough, ~10k–100k chunks) | ~1–5 GB |
| OS + app + audio buffers + overhead | ~8–12 GB |
| **Total** | **~70–90 GB** |

Comfortable headroom remains for batching and for serving a second concurrent session — the explicit "many contexts at once" advantage.

### 7.2 Latency budget (honest, streaming)
**Reframing your draft's "sub-300 ms bidirectional speech-to-speech":** that figure is not achievable as a *full* round-trip with a 70 B model in the loop; it is realistic only for the *ASR stage* or as the cloud-penalty you're eliminating. The correct, defensible targets are streaming, first-audio-oriented:

| Stage | Target |
|---|---|
| Endpointing / VAD (client) | 50–150 ms |
| ASR to final utterance (streaming, on-device) | 150–300 ms |
| Fast LLM time-to-first-token | 100–300 ms |
| TTS time-to-first-audio (streaming) | 100–200 ms |
| **Perceived time-to-first-audio (end-to-end)** | **~600–900 ms** |

Pitch it as: *"Running locally removes the 400–500 ms cloud round-trip that makes interpreted conversations feel broken; with streaming and barge-in, the resident hears their language come back in under a second."* That is true, defensible, and still impressive.

---

## 8. Data foundation (London open data + policy corpus)

**Hard requirement satisfied:** London open data is the project's foundation.

- **ONS Census 2021 — borough-level English proficiency / main-language tables** (via London Datastore / ONS): drives per-borough language prioritisation and the impact framing.
- **London Datastore** — housing supply and homelessness statistics, council policy registers, benefits guidance, service directories.
- **Borough policy documents** (demo: Newham) — housing allocation scheme, Council Tax Support scheme, homelessness service guidance.
- **NHS trust accessibility / interpreting frameworks** — for the clinical scenario.

**RAG corpus for the demo:** curate ~50–100 documents for **one borough + one service domain** (Newham homelessness/housing). Pipeline: parse (many are PDFs) → clean → chunk (semantic, ~300–500 tokens, with source metadata) → embed (BGE-M3) → index. Retrieval is hybrid (dense + BM25) with source spans returned for citation. Scope tightly — one borough, one domain — and say so; breadth is a roadmap item, not a weekend deliverable.

---

## 9. Integrations required

| Integration | Purpose | Procurement / access plan |
|---|---|---|
| **ElevenLabs on-device** (Scribe v2 + multilingual TTS) | Core voice in/out, kept on-box | **Ask the ElevenLabs reps at the event** for on-device / enterprise / Government-tier access and credits on day one. Fallback: cloud Scribe v2 + TTS with zero-retention mode + EU data residency for the build, with on-device documented as the production path. |
| **Ollama** (or NVIDIA NIM) | Serve the local LLMs on the Spark | Pre-installed/standard on Spark; use ARM64 builds. |
| **Vector DB** — Qdrant or LanceDB (local) | Policy retrieval index | Run as a local container; no external service. |
| **NeMo Agent toolkit / NemoClaw** (optional) | Sandboxed orchestration of non-real-time agents | Sponsor-aligned; optional. |
| **Client audio transport** — WebSocket (or WebRTC) | Low-latency streaming between client and Spark | Self-hosted; no third party. |
| **London Datastore / ONS** | Data foundation + RAG corpus | Public download; ingest offline before the demo. |

**Sovereignty note on ElevenLabs:** the entire "nothing leaves the box" claim depends on running ElevenLabs **on-device**, not via cloud. If only cloud access is available for the build, the live demo's pull-the-cable moment must instead use the **local open-model fallback** (Whisper + Kokoro/Piper) so the offline proof is real; keep ElevenLabs as the "production-quality voice" showcase. Decide this Friday night based on what access ElevenLabs grants.

---

## 10. Infrastructure and deployment

- **Compute:** 1× DGX Spark (GB10, 128 GB unified), DGX OS / Ubuntu 24.04 **ARM64**.
- **Runtime:** Docker containers (use ARM64/NGC images). Expect occasional missing arm64 Python wheels — budget Friday-evening time for environment setup; prefer NVIDIA-provided containers and Ollama to minimise this friction tax.
- **Services on the Spark:** LLM server (Ollama/NIM) · ElevenLabs on-device container · vector DB container · app backend (**FastAPI + WebSocket**) · local encrypted store.
- **Networking for the build:** access the Spark from laptops via **NVIDIA Sync** or SSH (`dgx-spark.local` via mDNS); use **SSH port-forwarding** to reach the backend from a laptop during development.
- **Networking for the demo:** put the Spark and the client device on a **dedicated travel router** (or the Spark's own WiFi hotspot) so you control the network completely and can cleanly perform the offline proof. The client (tablet/laptop browser) hits the Spark's WebSocket endpoint over this LAN.
- **No inference-time internet dependency.** All data downloads (datasets, policy corpus, model weights) happen *before* the demo; at run time the box is self-contained.

---

## 11. Tech stack (concrete)

- **Backend:** Python 3.11, `asyncio`, FastAPI, `websockets`.
- **Inference serving:** Ollama (LLMs), ElevenLabs on-device SDK/container (ASR+TTS), `sentence-transformers`/BGE-M3 (embeddings).
- **Vector store:** Qdrant or LanceDB (local).
- **Client:** React / Next.js PWA (or a single-page app), Web Audio API for mic capture + client-side VAD, WebSocket streaming. Two synchronized panes: resident-language view and caseworker English view.
- **Record output:** structured JSON → rendered to PDF/HTML (e.g. via a templating step).
- **Orchestration (optional):** NeMo Agent toolkit for the non-real-time agents.

---

## 12. Security, privacy and governance

- **Legal frame:** UK GDPR + Data Protection Act 2018; special-category data (Art. 9). A real deployment requires a **DPIA** (Data Protection Impact Assessment) — name this; it signals you understand the domain.
- **Data flow:** audio captured on client → encrypted local-network transport (WSS/DTLS) → processed in-memory on the Spark → record written only with consent → stored **encrypted at rest** on the Spark → exported on demand (SAR/appeal). **No cloud egress at inference time.**
- **Consent:** explicit, multilingual consent at session start; the resident can decline recording and still use interpretation.
- **Retention:** ephemeral by default; the structured record is generated only on consent and held under a configurable retention policy controlled by the public body.
- **Auditability:** every policy claim carries a source citation + timestamp; the Record Agent's output is itself the audit trail.
- **Safety positioning:** Bridge augments, it does not replace, professional interpreters for legally binding or clinical decisions; this limitation is shown to users. Human-in-the-loop throughout.
- **ElevenLabs compliance (cloud fallback only):** Scribe v2 / platform offers SOC 2, ISO 27001, HIPAA, GDPR, EU/India residency, and zero-retention mode — relevant only if the build uses the cloud path; the on-device path is stronger and preferred.

---

## 13. Client UX and the demo device

- **Form factor:** a tablet (or laptop) standing on the desk between resident and caseworker, talking to the Spark over the local network. The Spark is the engine under the table; the tablet is what everyone looks at.
- **Two synchronized views:** the resident sees their language (large type, calm, minimal); the caseworker sees the English transcript plus live **Policy cards** and **Question prompts**.
- **Live "agent activity" strip:** a subtle, real-time trace showing the four agents working — this is the visual proof of the multi-agent system for judges (design counts for a full quarter of the score).
- **End-of-session:** one tap generates the structured record; show it on screen and "hand it" to the resident.

---

## 14. Demo plan (≈3 minutes)

1. **Frame (15s):** "320,000 Londoners can't navigate public services in English. Today they bring a child to interpret. Here's Bridge — and everything you're about to see runs on this box, on this table." (Point at the Spark.)
2. **Live interpretation (60s):** a teammate plays a Bengali-speaking resident in a Newham housing interview; Bridge interprets both directions in near-real-time. The activity strip shows all four agents live.
3. **Policy + Question moment (45s):** as "homelessness" is mentioned, a **Policy card** surfaces the relief-duty entitlement with its source; the **Question Agent** prompts the resident to ask about emergency accommodation. This is the "it's not just translating, it's advocating" beat.
4. **The offline proof (20s):** pull the network cable / flip the router off. Continue the conversation. Nothing breaks. "Their data never left this room."
5. **The record (30s):** one tap → an appeal-ready, bilingual, citation-backed record appears. "If this decision is wrong, she can challenge it — with evidence."
6. **Close (10s):** one line on impact and the production path (on-device ElevenLabs, multi-borough roadmap).

---

## 15. Build plan (weekend)

| When | Goal | Owners (team of 4–5) |
|---|---|---|
| **Fri eve** | Spark setup (first boot via monitor+keyboard+ethernet), env + containers, Ollama models pulled, ElevenLabs access decided, dataset + policy corpus downloaded | All; 1 lead on infra |
| **Sat AM** | Interpreter loop end-to-end (one language pair), streaming audio in/out, language quality benchmark → pick demo languages | 2 on voice loop |
| **Sat PM** | Policy Agent RAG over Newham corpus + Policy cards; client two-pane UI | 1 on RAG, 1 on frontend |
| **Sat eve** | Question Agent + activity strip; integrate agents on the event bus | 2 |
| **Sun AM** | Record Agent → structured + PDF/HTML; offline-proof rehearsal on dedicated router | 1 + 1 |
| **Sun midday** | Polish, demo script rehearsal x3, failure-mode fallbacks (canned audio backup) | All |

---

## 16. Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Open-model quality weak in a target language | High | Benchmark Sat AM; pick demo languages where quality is strong; state limitation. |
| On-device ElevenLabs access not granted in time | Medium | Local open-model fallback (Whisper + Kokoro/Piper) so the offline proof still works; ElevenLabs cloud as quality showcase. |
| Latency feels laggy | Medium | Streaming + barge-in; small fast model in the loop; pre-warm models; target time-to-first-audio not full round-trip. |
| RAG surfaces wrong/irrelevant policy | Medium | Show citations always; suppress low-confidence cards; never show an unsourced claim. |
| ARM64 dependency friction | Medium | Use NVIDIA containers + Ollama; resolve Friday night, not Sunday. |
| Live demo network/mic failure | Medium | Dedicated router; canned-audio backup path; rehearse the offline proof. |
| Scope creep (20 languages, 5 boroughs) | High | One borough, one domain, 2–3 languages. Underclaim scope; over-deliver depth. |

---

## 17. How Bridge maps to the judging rubric

NVIDIA's standard four equally-weighted axes, plus the ElevenLabs panel:

- **Technical implementation:** five concurrent model contexts in unified memory; dual-LLM pattern; streaming voice loop; genuine use of the hardware's actual strength. Strong.
- **Design / UX:** two-pane bilingual client, live agent-activity strip, the record artifact. Demo-spectacle and clarity. Strong.
- **Potential impact:** 320,000 Londoners; measurable reduction in missed entitlements, repeat appointments, escalations. Strong.
- **Quality / creativity:** the multi-agent advocacy framing and especially the **Record Agent** (appeal/ombudsman/SAR-ready output) differentiate it from the plain "translation bot" others will build. Lead here.
- **ElevenLabs "Best Use of Voice":** voice is the product, not a feature; on-device Scribe v2 + multilingual TTS; diarized, timestamped transcripts feeding the record. Strong sponsor fit.

---

## 18. Roadmap (post-hackathon)

- Multi-borough policy corpora; automated policy-register ingestion.
- Full on-device ElevenLabs deployment + DPIA with a pilot council/trust.
- Evaluation harness for per-language interpretation quality with community reviewers.
- Integration into existing case-management systems (record export via standard formats).
- Accessibility extensions (BSL, low-literacy modes).

---

## 19. Sources / references

- ONS, *Language, England and Wales: Census 2021* (English-proficiency statistics; ~320,000 Londoners unable to speak English well or at all).
- London Datastore — `data.london.gov.uk` (housing/homelessness data, council policy registers, service guidance).
- NVIDIA DGX Spark documentation and reviews (GB10, 128 GB unified LPDDR5X ~273 GB/s, ~1 PFLOP FP4, Ubuntu 24.04 ARM64, NVIDIA Sync, Ollama).
- ElevenLabs — on-premise/on-device deployment (shipped April 2026), Scribe v2 Realtime (~150 ms p50; diarization, word timestamps), Government tier, EU data residency, zero-retention mode.
- NVIDIA Hack for Impact — London event brief (tracks, hardware, sponsors, London open-data requirement).

*All figures above were verified against primary sources during research; re-confirm the language statistic and any model latency/quality claims immediately before the pitch.*
