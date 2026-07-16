recommendation: REJECT
securityVerdict: FAIL
securitySeverity: HIGH

## securityAuditAddendum

- HIGH - `backend/routes/news.py:90-107` exposes unauthenticated `POST /api/news/sync`, which can trigger Naver/Finnhub ingestion and service-role `news_articles` / `news_fetch_logs` writes through `backend/services/news_repository.py:361-382`. This is not a public cleanup endpoint, but it is a public external-API cost and DB-write trigger in the reviewed news ingestion surface.
- MEDIUM - `backend/routes/news.py:12-16` accepts raw `market`, `query`, and `symbol`; `backend/services/news_repository.py:81`, `:99`, `:101`, `:109`, `:111`, `:133`, `:136`, `:151`, `:154`, and `:195-202` concatenate those values into PostgREST operator grammar. Direct hostile-input proof: `_text_search_filter("삼성전자*,id.not.is.null,summary.ilike.*")` injects extra filter tokens into the generated `or=(...)` expression. No adversarial test covers commas, parentheses, operators, wildcards, negative limits, or unexpected market/symbol characters.
- PASS - no public cleanup route was found; retention cleanup is referenced through scheduler/repository paths only.
- PASS - the destructive retention implementation uses fixed table names and retention filters for `news_articles` and `news_fetch_logs`; scoped scans found no unfiltered cleanup delete, `TRUNCATE`, `DROP`, or DART table deletion in the changed retention code.
- PASS - the migration is additive and does not alter RLS policies.
- PASS - scoped scheduled-ingestion code does not add Tavily fetchers, Tavily query planner entries, or `source='TAVILY'` scheduled writes. Tavily remains documented as chatbot fallback only.
- PASS - scoped docs/evidence scans found environment variable names and test placeholders, but no real service-role/Naver/Finnhub/Tavily secret values copied into reviewed artifacts.

## blockers

1. Fresh user-visible news rows can still have null quality metadata after the claimed live backfill/cleanup.
   - `.omo/evidence/task-6-news-auto-retention-quality-gate.md` records post-cleanup `null quality status remaining 0` at `2026-07-16 06:55 UTC`.
   - `.omo/evidence/f3-curl-news-005930.txt` records `/api/news?symbol=005930&limit=5` at `2026-07-16 07:12:07 UTC` returning five rows fetched at `2026-07-16T07:05:36` to `07:05:43 UTC` with `quality_status=null`, `relevance_score=null`, and `quality_checked_at=null`.
   - This contradicts the original outcome that new articles are scored before saving and leaves the active environment able to accumulate unclassified rows.

2. Not every `news_articles` writer is behind the new quality gate.
   - `backend/services/news_ingest.py:147` to `backend/services/news_ingest.py:154` applies `NewsQualityService` before scheduled ingest upsert.
   - `backend/services/chatbot/web_fallback_search_service.py:654` and `backend/services/chatbot/web_fallback_search_service.py:703` still call `_try_upsert_news()`, which directly calls `news_repository.upsert_articles()` at `backend/services/chatbot/web_fallback_search_service.py:798` to `backend/services/chatbot/web_fallback_search_service.py:802` without quality metadata.
   - The plan requirement was an ingest quality gate for Naver/Finnhub before `upsert_articles`; the implementation covers only one caller path.

3. Exact-symbol retrieval is not actually quality/relevance-ranked over the full exact result set.
   - `backend/services/news_repository.py:128` to `backend/services/news_repository.py:133` requests exact symbol rows ordered only by `published_at.desc` and limits to `limit + offset`.
   - `backend/services/news_repository.py:138` then sorts that truncated subset locally by `HIGH_QUALITY`, `relevance_score`, and `published_at`.
   - If an older `HIGH_QUALITY` exact-symbol article falls outside the first `limit + offset` newest rows, it is never fetched and cannot rank first. This violates Todo 4's relevance-ranked exact-symbol lookup requirement.

4. Required independent review artifacts are absent for this gate.
   - No news-specific code review report artifact was found under `.omo/evidence`, `.omo/drafts`, or `.omo/plans`.
   - No report shows the required `remove-ai-slops`/`programming` perspective coverage, overfit-test review, or slop criterion coverage.
   - Raw F3 curl outputs exist, but no manual QA matrix artifact ties them to pass/fail criteria.

## originalIntent

Implement the final news retention and quality plan:
- normal news physically auto-deletes after 7 days;
- `HIGH_QUALITY` news physically auto-deletes after 30 days;
- `news_fetch_logs` physically auto-delete after 7 days;
- current collection volume and scheduler cadence remain unchanged;
- Tavily remains chatbot fallback only and is not added to scheduled ingestion;
- DART cleanup is excluded and handled separately;
- fresh Naver/Finnhub articles are quality-scored before persistence;
- exact symbol news lookup prefers exact symbol rows and ranks by quality/relevance.

## desiredOutcome

A user or operator should be able to rely on the running news system to keep storage bounded without reducing collection volume, while the articles shown in `/api/news` are classified with quality metadata and symbol pages prefer truly high-quality exact-symbol news.

## userOutcomeReview

The retention schema, physical delete methods, scheduler hook, tests, and live cleanup evidence are present, and the broad F1 guardrails mostly hold:
- no collection-rate reduction was found in the scoped diff;
- no scheduled Tavily provider/fetcher was added;
- no DART cleanup path was added;
- live evidence honestly records that measured DB size increased to about 387 MiB after indexes/backfill/cleanup, leaving about 113 MiB of 500 MiB Free-plan headroom.

However, the shipped outcome is not reliable from the user's perspective. The manual API artifact shows fresh `005930` rows with null quality metadata after cleanup, and the code still has at least one direct writer bypassing the new scoring service. Symbol lookup also does not rank globally by quality/relevance because it limits by recency before sorting.

## slopAndProgrammingReview

Direct pass applied from `remove-ai-slops` and `programming` criteria:
- Overfit coverage found: `backend/tests/test_news_symbol_lookup.py` verifies local sorting of a fake response where all exact rows are already returned; it does not cover the adversarial class where PostgREST returns only the newest `limit` exact rows and an older `HIGH_QUALITY` row is omitted before local sorting.
- Missing behavior coverage found: no test covers all callers of `NewsRepository.upsert_articles()` or proves that chatbot Naver/Finnhub fallback writes include `relevance_score`, `quality_status`, `excluded_reason`, and `quality_checked_at`.
- Maintenance/slop issue found: quality metadata is enforced in `NewsIngestService` instead of at the repository write boundary or every writer seam, allowing bypasses and false confidence.
- Oversized-file risk remains: `backend/services/news_repository.py` and `backend/services/news_ingest.py` are over the 250 pure LOC criterion in evidence. This is not the primary blocker for F1, but the direct pass confirms the branch did not resolve the size smell.
- Required external review coverage is absent; no code review report independently documents this same skill-perspective and overfit/slop pass.

## checkedArtifactPaths

- `.omo/plans/news-auto-retention-quality-gate.md`
- `.omo/drafts/news-auto-retention-quality-gate.md`
- `.omo/evidence/task-1-news-auto-retention-quality-gate.md`
- `.omo/evidence/task-2-news-auto-retention-quality-gate.md`
- `.omo/evidence/task-3-news-auto-retention-quality-gate.md`
- `.omo/evidence/task-4-news-auto-retention-quality-gate.md`
- `.omo/evidence/task-4-news-auto-retention-quality-gate-pycompile.txt`
- `.omo/evidence/task-4-news-auto-retention-quality-gate-pytest.txt`
- `.omo/evidence/task-5-news-auto-retention-quality-gate.md`
- `.omo/evidence/task-6-news-auto-retention-quality-gate.md`
- `.omo/evidence/f3-curl-news-005930.txt`
- `.omo/evidence/f3-curl-news-btc.txt`
- `.omo/evidence/f3-flask-server.stderr.log`
- `.omo/evidence/f3-flask-server.stdout.log`
- `supabase/migrations/20260716151440_add_news_quality_metadata_retention_indexes.sql`
- `backend/services/news_repository.py`
- `backend/services/news_quality_service.py`
- `backend/services/news_ingest.py`
- `backend/services/ml_scheduler.py`
- `backend/routes/news.py`
- `backend/services/chatbot/web_fallback_search_service.py`
- `backend/tests/test_news_retention_cleanup.py`
- `backend/tests/test_news_ingest_quality.py`
- `backend/tests/test_news_symbol_lookup.py`
- `backend/tests/test_news_cleanup_scheduler.py`
- `database_specification.md`
- `docs/2026-07-09-obsidian-vector-tavily-status.md`
- `project_structure.md`

## exactEvidenceGaps

- No post-ingestion live DB query proves rows inserted after the migration/backfill have non-null quality metadata.
- No evidence explains why fresh rows in `.omo/evidence/f3-curl-news-005930.txt` have null quality fields after task 6 reported zero null-quality rows.
- No test covers the exact-symbol retrieval case where an older `HIGH_QUALITY` row is outside the initial recency-limited fetch.
- No test or code review covers the direct chatbot fallback upsert path.
- No news-specific code review report, manual QA matrix, or notepad path was supplied.

## F1Verdict

FAIL. The F1 checkbox may not be marked complete.
