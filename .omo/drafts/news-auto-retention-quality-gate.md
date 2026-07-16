---
slug: news-auto-retention-quality-gate
status: plan-written
intent: clear
pending-action: write .omo/plans/news-auto-retention-quality-gate.md
approach: keep current collection volume, add automatic physical retention cleanup, add ingest-time quality scoring, and make symbol news retrieval exact-first.
---

# Draft: news-auto-retention-quality-gate

## Components (topology ledger)
<!-- Lock the SHAPE before depth. One row per top-level component that can succeed or fail independently. -->
<!-- id | outcome (one line) | status: active|deferred | evidence path -->
- C1 | Supabase news retention policy physically deletes expired rows automatically | active | .omo/evidence/task-1-news-auto-retention-quality-gate.md
- C2 | News ingest quality gate rejects off-topic/non-news rows before upsert | active | .omo/evidence/task-2-news-auto-retention-quality-gate.md
- C3 | News repository and API retrieve symbol news by exact symbol/relevance first | active | .omo/evidence/task-4-news-auto-retention-quality-gate.md
- C4 | Tests, DB verification, docs, and rollout controls prove Free-plan storage safety | active | .omo/evidence/task-6-news-auto-retention-quality-gate.md

## Open assumptions (announced defaults)
<!-- Record any default you adopt instead of asking, so the user can veto it at the gate. -->
<!-- assumption | adopted default | rationale | reversible? -->
- Collection volume | Do not reduce current query budgets or scheduler interval | Recent live average is about 650 API requests/day and is safe once 7-day cleanup runs | reversible
- General news retention | Physically delete after 7 days | Supabase Free storage is the constraint; inactive rows do not recover space | reversible by changing retention days before deployment
- High-quality news retention | Physically delete after 30 days | Keeps important symbol context without allowing unlimited growth | reversible by changing retention days before deployment
- Fetch log retention | Physically delete after 7 days | Fetch logs are operational diagnostics, not product content | reversible
- Tavily | Keep chatbot fallback, keep out of scheduled ingestion | Avoid paid fallback becoming a background storage/cost source while preserving emergency web search | reversible
- DART disclosures | Out of scope for this plan | User said DART cleanup will be handled separately | yes

## Findings (cited - path:lines)
- `backend/services/news_ingest.py:123` to `backend/services/news_ingest.py:149` fetches and upserts deduplicated articles without an article relevance/quality gate.
- `backend/services/news_ingest.py:188` to `backend/services/news_ingest.py:235` Naver ingestion only checks a Korean-text predicate before saving.
- `backend/services/news_ingest.py:237` to `backend/services/news_ingest.py:277` Finnhub ingestion saves company-news rows without storing relevance status.
- `backend/services/news_repository.py:18` to `backend/services/news_repository.py:55` retrieves active news by broad `ilike` query fields.
- `backend/routes/news.py:18` to `backend/routes/news.py:34` converts `symbol` to display-name query, which weakens exact symbol matching.
- `backend/services/ml_scheduler.py:145` to `backend/services/ml_scheduler.py:179` already runs the news scheduler loop and can call cleanup once per loop/day under the existing distributed lock.
- `supabase/migrations/20260624013000_enhance_news_ingest.sql:1` to `supabase/migrations/20260624013000_enhance_news_ingest.sql:21` defines `news_articles` without quality metadata columns.
- `supabase/migrations/20260624013000_enhance_news_ingest.sql:53` to `supabase/migrations/20260624013000_enhance_news_ingest.sql:66` defines `news_fetch_logs` without retention metadata, but `started_at` is enough for time-based cleanup.
- Supabase MCP live check: database is about 325MB, `news_articles` about 87MB, `news_fetch_logs` about 17MB, and 7-day news/log retention projects database around 255MB.

## Decisions (with rationale)
- Add `relevance_score`, `quality_status`, `excluded_reason`, and `quality_checked_at` to `news_articles`.
- Use quality statuses `PASS`, `HIGH_QUALITY`, `LOW_CONFIDENCE`, and `REJECTED`; only persisted rows should normally be `PASS`, `HIGH_QUALITY`, or explicit diagnostic `LOW_CONFIDENCE` when configured.
- General persisted news expires after 7 days.
- `HIGH_QUALITY` persisted news expires after 30 days.
- Rejected rows should not be inserted by default; rejection counts should be returned in ingest results and written into fetch logs or query result diagnostics.
- Cleanup must use physical delete, not `is_active=false`, because storage size is the Free-plan pressure.
- Keep current API query budget and scheduler cadence unchanged.

## Scope IN
- Supabase migration for news quality metadata and cleanup indexes if needed.
- Repository methods for deleting expired news and fetch logs.
- Worker/scheduler wiring for automatic cleanup.
- Naver/Finnhub ingest quality scoring before upsert.
- Symbol exact-first news lookup and count behavior.
- Tests and DB verification evidence.
- Project docs update for retention and quality policy.

## Scope OUT (Must NOT have)
- Do not reduce `NEWS_NAVER_DAILY_QUERY_BUDGET`, `NEWS_MAX_QUERIES_PER_RUN`, or scheduler interval as part of this plan.
- Do not add Tavily to scheduled ingestion; chatbot fallback usage remains in scope.
- Do not change DART retention in this plan.
- Do not delete ML model/job data.
- Do not expose service-role cleanup endpoints publicly.

## Open questions
- None. User selected current-volume retention approach and explicitly excluded collection-rate reduction.

## Approval gate
status: plan-written
<!-- When exploration is exhausted and unknowns are answered, set status: awaiting-approval. -->
<!-- That durable record is the loop guard: on a later turn read it and resume at the gate instead of re-running exploration. -->
