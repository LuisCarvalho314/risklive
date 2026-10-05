# Frozen CSV regression snapshot

These files are repository test inputs, not a runtime database. No production path
or archive discovery is used by normal tests. The loader copies them into tmp_path.

## Provenance and selection

Read-only inspection on 2026-10-05 of
`/home/azureuser/opt/risklive/repo/risklive/results/data/`:
`news_data.csv`, `news_data_with_llm_info.csv`,
`df_with_response_and_topics.csv`, and `df_report.csv`.
Only headers, counts, categorical values and empty/duplicate shapes were printed.
No operational pipeline was run and no production file was written.

Selected enriched CSV data-row ordinals (one-based, excluding header):
1, 12, 13, 14, 32, 45, 58, 95, 100, 101, 102, 103, 104, 121, 138.
Raw and topic rows were selected by matching original URL. This gives 15 raw rows,
15 enriched rows and 13 topic rows (43 rows total). Source order is preserved.
These ordinals document provenance; regeneration from changing production is
neither needed nor expected.

Selection preserves all six nonempty categories plus an empty category;
Red/Yellow/Green; Yes/No relevance; empty keywords and summary; two enriched
rows absent from topic output; duplicate titles with distinct URLs (articles
03 and 09); noise topic -1; and Red topics -1, 9, 10 and 15, with two Red rows
in topic 15. The enriched topic column is empty, requiring the dashboard URL
join to topic output. Topic identifiers were retained as structural group keys.

Titles, URLs, descriptions, queries, summaries, reasons, keywords, raw LLM
responses and usage/cost metadata were replaced with deterministic placeholders.
Empty cells remain empty. URLs use the reserved example domain. No article text,
personal names, original URLs, credentials or secrets are retained. Timestamps
are fixed hourly offsets from 2026-01-15T12:00:00Z; API timestamps are fixed too.
Dashboard time is frozen to that instant for these integration/regression tests.

## Existing contracts

* Raw CSV: populated Title, URL, Timestamp columns.
* Enriched CSV: Title, URL, AlertFlag, RelevantKeywords; dashboard additionally
  uses Timestamp, Description, Relevance, NewsCategory, ShortSummary, AlertReason.
* Topic CSV: Title, URL, AlertFlag, topic, RelevantKeywords; typed row parsing
  uses the same realistic complete production headers as the enriched CSV.
* Reports are generated with a stub at the external report-agent boundary.
  Output columns are topic, keyword, input_prompt, response. Exactly one report
  per distinct Red non-null topic is asserted, including topic -1.
* Dashboard must export its JSON and schema, all required top-level sections,
  populated alerts/newsmap, and topic keyword/response fields. Empty or malformed
  report files must yield an empty topic list.

No existing assertion requires historical continuity, exact production topic
numbers, duplicate winners, null timestamps, timestamp ordering, or report text.
Those assertions were not changed. Production had no null timestamps; none were
invented. Deduplication, relevance filtering, category routing, URL joins, missing
assignments and recency paths are exercised by the snapshot, although the existing
assertions do not individually verify every one of those behaviors. No stored
report is necessary because every dashboard test generates or replaces it.
Report tests sort topics with nulls last because generate_report requires a
non-null first topic. Dashboard category and alert sorting remain production code.

This is a useful future CSV-vs-DuckDB input baseline. Migration tests should add
explicit normalized comparisons of joins, nulls, grouping, deduplication and
ordering; current tests alone do not prove storage-engine equivalence.
