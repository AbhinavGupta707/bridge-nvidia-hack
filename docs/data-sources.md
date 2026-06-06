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

