---
date: 2026-02-13
aliases:
---

# LangExtract in RiskLive: Story-Clustering Support, Downstream Benefits, and High-Risk Follow-up Search

## Context and goal
RiskLive ingests a stream of news items and produces topic clusters and risk outputs for reporting. A key requirement is to **cluster all articles that describe the same story** (not deduplicate/remove them). The current pipeline relies on LLM-enriched fields and BERTopic to organise content; however, “same story” coverage can fragment across outlets due to differences in framing, boilerplate, and writing style.

This note proposes using **LangExtract** to generate a compact, typed intermediate representation (“Story Frame”) to improve clustering quality, explainability, agentic workflows, and to enable a cleaner transition from CSV-based storage to a RAG-style database. It also describes how Story Frames can improve **Valyu follow-up search** for high-risk clusters.

---

## What LangExtract provides (in practice)
LangExtract is an LLM-assisted extraction layer that produces **typed extractions** from text using a defined schema (entity/event types) and example-driven prompting. It is designed to return structured extractions that can be anchored to the source text (e.g., by quotes/spans), and it can perform internal alignment/validation, which may involve multiple passes.

The important capability for RiskLive is: **convert unstructured article text into consistent, comparable fields** that are useful for clustering, retrieval, and automated follow-up.

---

## Proposed intermediate representation: “Story Frame”
A **Story Frame** is a minimal schema optimised for story identity and retrieval rather than full risk judgement:

- `event_type` (controlled label; e.g., treaty change, legal investigation, incident, sanctions, policy)
- `actors` (ORG/PER/COUNTRY)
- `dates` (explicit references; plus publication date where available)
- `locations`
- `key_claims` (1–5 short claims; optionally evidence-anchored)
- `key_terms` (5–15 keywords / phrases for topic labelling and BERTopic inputs)

This is distinct from the full risk report schema (severity/actions/stakeholders). It focuses on features that remain stable across outlets covering the same story.

---

## Where LangExtract fits in the RiskLive pipeline

### Baseline (today)
1) Ingest (Valyu)  
2) Persist to CSV  
3) LLM extraction (adds fields like `RelevantKeywords`, `ShortSummary`, `AlertFlag`, etc.)  
4) BERTopic topic modelling  
5) Report generation

### Proposed (story clustering enhancement)
1) Ingest (Valyu) — unchanged  
2) **LangExtract Story Frame** — new  
3) **Clustering on a hybrid representation**:
   - semantic embeddings of `title + snippet` (robust to paraphrase)
   - + Story Frame overlap signals (shared actors/date/event_type/claims) to reduce fragmentation
4) Cluster-level outputs drive:
   - cluster naming (from shared actors/event_type/claims)
   - cluster summaries (from a representative article + frames)
   - selective deeper analysis (only for clusters requiring risk judgement)
5) Persist to a store suitable for RAG (raw text + frames + clusters), while continuing CSV export during transition

---

## Benefits

### 1) Improved “same story” clustering quality
- **Reduced fragmentation**: articles about the same event often share actors, time, and event-type even when prose differs.
- **Higher cluster purity**: structured overlap helps avoid mixing adjacent but distinct stories.

### 2) Better cluster interpretability
- Clusters can be explained using shared fields: “same actors + same event type + same date window + common claims.”
- If evidence anchoring is enabled, clusters can include supporting snippets that justify why articles are grouped.

### 3) Agentic workflow enablement
- Agents can operate on a stable intermediate object (Story Frame + cluster metadata) instead of repeatedly parsing raw text.
- Enables cluster-level actions: one analysis/plan per cluster, linked to all member articles.

### 4) RAG readiness (better than CSV as a primary store)
- Story Frames become metadata for retrieval filters (actors/date/event_type/location).
- Retrieval can return compact frames or cluster summaries rather than long raw articles.
- Supports auditing: “why did we retrieve this?” and “what claim supports this?”

### 5) Improved Valyu follow-up searches for high-risk clusters
For clusters flagged as high-risk (e.g., “Red” or high-priority categories), Story Frames can generate **targeted query packs** for coverage expansion:

**How it helps**
- **Higher precision queries**: queries built from `actors + event_type + distinctive key_claims` reduce drift into adjacent stories.
- **Higher recall coverage expansion**: systematic query variants (aliases, “update/statement/investigation” terms) pull in follow-ups and authoritative sources.
- **Cluster-aware attachment**: newly retrieved candidates can be frame-compared to the cluster (actor overlap + event_type + date window) before attachment, reducing false positives.
- **Reduced redundant searching**: cluster-level tracking prevents re-querying the same terms every run unless the story evolves (new actor/date/claim triggers new searches).

**Example query pack pattern (per high-risk cluster)**
- `Q1`: `"PRIMARY_ACTOR" AND "DISTINCTIVE_PHRASE"`  
- `Q2`: `"PRIMARY_ACTOR" AND EVENT_TYPE_TERM AND (DATE_OR_LOCATION)`  
- `Q3`: `ALIAS_1 OR ALIAS_2 AND "DISTINCTIVE_PHRASE"`  
- `Q4`: `"PRIMARY_ACTOR" AND (update OR statement OR response OR investigation)`  

This supports an agentic loop: **cluster → build queries → Valyu search → extract frames for results → attach to cluster if match**.

---

## Costs and risks

### 1) Compute cost
LangExtract is not inherently cheaper. Its alignment/validation can be multi-pass. It only reduces total compute if it:
- replaces existing extraction calls, or
- reduces downstream deep analysis (e.g., analyse at cluster level rather than per article), or
- is applied selectively (e.g., high-salience clusters only).

### 2) Engineering complexity
- Schema design and versioning
- Example maintenance and regression testing
- Caching (URL/content-hash) and failure handling
- Merge logic if articles are chunked

### 3) Extraction brittleness
- If span/evidence anchoring is used, exact-string matching can break when text changes (whitespace, punctuation, encoding).
- Mitigation: normalise inputs; compute spans programmatically from final stored text; allow graceful fallback to non-span extraction when needed.

### 4) Error propagation
If extraction misses entities/claims, clustering can degrade if frames are the sole signal. Mitigation:
- keep clustering hybrid (embeddings + frame overlap), and
- fall back to `title + snippet` embeddings when frames are incomplete.

### 5) Over-normalisation risk
Compressing story identity into a short frame can collapse genuinely different stories that share actors (e.g., multiple concurrent policy actions by the same ministry). Mitigation:
- include date windows and a short `event_statement`/`key_claims`
- require multiple signals (actors + event_type + claim overlap) for cluster attachment/merging.

---

## Recommended implementation strategy (low-risk)

### Phase 1: Story Frame only (pilot)
- Run LangExtract on bounded input (`title + snippet` or first N chars) to avoid chunking.
- Output minimal frame fields + keywords.
- Cluster using embeddings, then use frames for merge/refinement and cluster labelling.
- Evaluate on a labelled set of “should be same story” examples.

### Phase 2: High-risk coverage expansion with Valyu (closed loop)
- For clusters above a salience threshold, generate query packs from Story Frames.
- Run Valyu searches; extract frames for returned results.
- Attach results to clusters using a similarity threshold (actors/event_type/date/claims).

### Phase 3: Evidence anchoring for high-impact clusters
- Add evidence snippets/spans only for clusters above a salience threshold.
- Use for audit trail and supervisor-facing defensibility.

### Phase 4: RAG store migration
- Store raw articles, Story Frames, and cluster summaries as first-class objects.
- Keep CSV exports for compatibility until dashboards are migrated.

---

## Success criteria
- Fewer “same story split into multiple clusters” errors (higher story recall)
- Higher cluster purity (fewer mixed-story clusters)
- Faster analyst understanding (better cluster names + shared-claim summaries)
- Stable downstream reporting inputs (keywords consistently available; less topic drift)
- Improved follow-up search yield for high-risk clusters (more relevant updates attached; less drift)
- Improved retrieval quality once moved to RAG (precision/recall on internal queries)

---
