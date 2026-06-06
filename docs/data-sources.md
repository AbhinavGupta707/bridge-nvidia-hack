# Data Sources

Bridge needs two kinds of data:

1. impact and prioritization data, such as London Census 2021 language
   proficiency by borough or ward
2. policy data used by the Policy Agent RAG corpus

## P0 Sources

- London Datastore Census 2021 language/proficiency data
- London Datastore homelessness provision by borough
- City of London homelessness pages
- City of London rights and prevention pages

## P1 Sources

- Newham homelessness prevention and advice pages
- Newham housing allocation scheme PDF
- Newham housing placements policy

## Current Statistic To Verify

Use cautious pitch language until the exact source table is in the repo:

> Around 350,000 Londoners cannot speak English well or at all.

This is based on a London Datastore Census 2021 excerpt listing 303,000 "cannot
speak English well" and 52,000 "cannot speak English at all".

## Source Hygiene

Every policy card must include:

- source title
- source URL or local document path
- source span
- authority
- confidence score
- triggering turn id

## Current Registry Status

`data/sources.yml` now contains the P0 London Datastore and City of London
sources plus P1 Newham housing/homelessness sources. Each source has a cautious
`local_seed_text` fallback so the demo can build a local index without network
access. The ingester still attempts live refresh first by default.

Verified on 2026-06-06:

- London Datastore Census 2021 page lists `English Proficiency.xlsx`.
- London Datastore homelessness provision page lists `Homelessness.xlsx`.
- City of London pages are reachable for homelessness landing, rights, and
  prevention content.
- Newham homelessness advice and council-housing pages are reachable.
- Newham allocation scheme PDF currently resolves to the 2025 version at
  `/downloads/file/9713/housing-allocation-policy-04-09-2025-v3-0-1`.

## Ingestion And Index

Run a live refresh when network access is available:

```bash
python scripts/ingest_corpus.py --fetch --fail-on-empty
```

Require every source to refresh from its official URL/resource:

```bash
python scripts/ingest_corpus.py --fetch --require-live
```

Run deterministic offline/demo indexing from registry seed notes:

```bash
python scripts/ingest_corpus.py --no-fetch --fail-on-empty
```

The local index is written to `data/processed/`:

- `corpus_chunks.jsonl` stores chunk text and citation metadata.
- `manifest.json` records source status, chunk count, and index kind.
- `raw/` stores downloaded source bytes when live fetch is enabled.

The retriever is local and dependency-light. It combines BM25-style keyword
scoring, query expansion for homelessness terms, phrase bonuses for policy
concepts, and hashed character 3-gram similarity. This is not a model embedding
index yet, but it gives a deterministic hybrid retrieval path until BGE-M3 or
multilingual-e5 is installed on the target machine.

## Policy Card Guardrails

The Policy Agent has no generative policy mode. It emits `policy_card` events
only when all of the following are true:

- retrieval confidence is above threshold
- source title, URL, authority, and span are present
- a relevant claim sentence can be selected from the cited chunk
- the card remains compatible with `PolicyCardEvent`

Low-confidence or uncited matches return no card.
