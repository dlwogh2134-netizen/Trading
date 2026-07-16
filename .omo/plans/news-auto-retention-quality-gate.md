# news-auto-retention-quality-gate - Work Plan

## TL;DR (For humans)
**What you'll get:** News storage will clean itself automatically: normal news is physically deleted after 7 days, high-quality symbol news after 30 days, and old fetch logs after 7 days. New articles will be scored before saving so wiki-like, off-topic, or non-financial results do not pollute the news DB.

**Why this approach:** Current API volume is already safe if retention runs; the storage problem comes from unlimited accumulation and weak pre-save filtering. Physical deletion is required because simply hiding rows does not recover Supabase Free-plan capacity.

**What it will NOT do:** It will not reduce current news collection cadence or Naver query budgets. It will not add Tavily to scheduled ingestion; Tavily remains available only as chatbot fallback. It will not change DART disclosure retention, which is a separate cleanup track.

**Effort:** Medium
**Risk:** Medium - schema and cleanup behavior affect production data, so rollback and DB verification must be explicit.
**Decisions to sanity-check:** General news 7 days, high-quality news 30 days, fetch logs 7 days, and current collection volume unchanged.

Your next move: approve implementation/start work when ready. Full execution detail follows below.

---

> TL;DR (machine): Medium risk storage/quality plan: add quality metadata, cleanup job, ingest scoring, exact symbol lookup, tests, DB evidence, and docs; do not reduce collection volume.

## Scope
### Must have
- Add news quality metadata to Supabase: `relevance_score`, `quality_status`, `excluded_reason`, `quality_checked_at`.
- Add a retention cleanup path that physically deletes expired news:
  - `quality_status='HIGH_QUALITY'`: delete after 30 days.
  - every other persisted news row: delete after 7 days.
  - `news_fetch_logs`: delete after 7 days.
- Wire cleanup into the existing backend worker/scheduler path so it runs automatically without a public unauthenticated endpoint.
- Add an ingest quality gate for Naver and Finnhub before `upsert_articles`.
- Preserve current collection volume and scheduler cadence.
- Change symbol news lookup to exact symbol first, then fallback search only when exact results are insufficient.
- Add tests and agent-executed Supabase verification evidence.
- Update docs that describe DB schema and news retention behavior.
- Preserve the current Tavily chatbot fallback path and add a guard that scheduled ingestion does not use Tavily.

### Must NOT have (guardrails, anti-slop, scope boundaries)
- Must not reduce `NEWS_NAVER_DAILY_QUERY_BUDGET`, `NEWS_MAX_QUERIES_PER_RUN`, `NEWS_MAX_ITEMS_PER_QUERY`, or `NEWS_INGEST_INTERVAL_SECONDS`.
- Must not add Tavily to scheduled ingestion; only chatbot fallback usage is allowed.
- Must not include DART disclosure cleanup.
- Must not make a public cleanup route callable by anonymous users.
- Must not use `is_active=false` as the retention storage-control mechanism.
- Must not weaken existing RLS policies or expose service-role keys.

## Verification strategy
> Zero human intervention - all verification is agent-executed.
- Test decision: tests-after with `pytest` for backend services/routes and Supabase SQL verification through the Supabase MCP.
- Evidence: `.omo/evidence/task-1-news-auto-retention-quality-gate.md` through `.omo/evidence/task-6-news-auto-retention-quality-gate.md`, plus final DB-size/count query output.

## Execution strategy
### Parallel execution waves
> Target 5-8 todos per wave. Fewer than 3 (except the final) means you under-split.
- Wave 1: schema/retention service and quality scoring can be developed after migration shape is clear; retrieval changes depend on schema fields but can be prepared with fallback defaults.
- Wave 2: scheduler wiring, route/repository integration, and tests depend on Wave 1 interfaces.
- Wave 3: DB verification, docs, and final review depend on all code changes.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
| --- | --- | --- | --- |
| 1 | none | 2, 3, 5, 6 | none |
| 2 | 1 | 5, 6 | 3 |
| 3 | 1 | 4, 6 | 2 |
| 4 | 3 | 6 | 5 |
| 5 | 1, 2 | 6 | 4 |
| 6 | 2, 4, 5 | final verification | none |

## Todos
> Implementation + Test = ONE todo. Never separate.
<!-- APPEND TASK BATCHES BELOW THIS LINE WITH edit/apply_patch - never rewrite the headers above. -->
- [x] 1. Add Supabase quality metadata and retention indexes
  What to do / Must NOT do: Create a new migration via `supabase migration new` or the repo's existing migration convention, then add columns to `public.news_articles`: `relevance_score integer`, `quality_status text`, `excluded_reason text`, `quality_checked_at timestamptz`. Add a check constraint for `quality_status in ('PASS','HIGH_QUALITY','LOW_CONFIDENCE','REJECTED')` while allowing null during migration/backfill. Add indexes that support cleanup and lookup: `(quality_status, published_at)`, `(symbol, quality_status, published_at desc)`, and a fetch-log cleanup index if existing `idx_news_fetch_logs_source_started` is insufficient for `started_at`. Must not remove or rewrite existing migrations.
  Parallelization: Wave 1 | Blocked by: none | Blocks: 2, 3, 5, 6
  References (executor has NO interview context - be exhaustive): `supabase/migrations/20260624013000_enhance_news_ingest.sql:1`, `supabase/migrations/20260624013000_enhance_news_ingest.sql:21`, `supabase/migrations/20260624013000_enhance_news_ingest.sql:33`, `supabase/migrations/20260624013000_enhance_news_ingest.sql:49`, `supabase/migrations/20260624013000_enhance_news_ingest.sql:53`, `supabase/migrations/20260624013000_enhance_news_ingest.sql:66`, `supabase/migrations/20260624013000_enhance_news_ingest.sql:81`, `supabase/migrations/20260624013000_enhance_news_ingest.sql:85`
  Acceptance criteria (agent-executable): Run a schema inspection SQL against Supabase/local DB showing the four columns and indexes exist; run migration syntax validation if local Supabase is unavailable.
  QA scenarios (name the exact tool + invocation): Happy: Supabase MCP `_execute_sql` selects from `information_schema.columns` and `pg_indexes` and writes output to `.omo/evidence/task-1-news-auto-retention-quality-gate.md`. Failure: attempt invalid `quality_status='BAD'` in a rolled-back transaction or local test DB and confirm check constraint rejects it; record evidence.
  Commit: Y | `feat(news): 뉴스 품질 메타데이터 스키마 추가`

- [x] 2. Implement retention cleanup repository/service behavior
  What to do / Must NOT do: Add repository methods that physically delete expired news and fetch logs using service-role headers. Policy: delete `news_articles` where `quality_status='HIGH_QUALITY'` and `published_at < now - 30 days`; delete all other news where `published_at < now - 7 days`; delete `news_fetch_logs` where `started_at < now - 7 days`. Return counts for deleted normal news, high-quality news, and logs. Must not use `is_active=false` for retention. Must not delete DART tables.
  Parallelization: Wave 1 | Blocked by: 1 | Blocks: 5, 6
  References (executor has NO interview context - be exhaustive): `backend/services/news_repository.py:8`, `backend/services/news_repository.py:16`, `backend/services/news_repository.py:227`, `backend/services/news_repository.py:248`, `backend/services/news_repository.py:258`, `backend/services/news_repository.py:270`
  Acceptance criteria (agent-executable): Unit tests with a fake requests client assert exact DELETE URLs/filters for 7-day general news, 30-day high-quality news, and 7-day logs; deletion count parsing is covered.
  QA scenarios (name the exact tool + invocation): Happy: `pytest backend/tests -k news_retention` passes and evidence saved to `.omo/evidence/task-2-news-auto-retention-quality-gate.md`. Failure: fake 500 response from Supabase causes a structured exception/log result without silently reporting success; record evidence.
  Commit: Y | `feat(news): 뉴스 자동 보관 정리 서비스 추가`

- [x] 3. Add ingest-time article quality scoring
  What to do / Must NOT do: Add a focused quality helper used by `NewsIngestService` before upsert. Score article title/summary/url against symbol, company name, aliases, source domain, finance keywords, and excluded domains. Reject wiki/namu/kin/dictionary/community-like URLs and non-financial/off-topic articles. Mark normal accepted rows `PASS`; mark rows `HIGH_QUALITY` when exact symbol/company signal plus finance keyword plus recent article meets threshold. Include `relevance_score`, `quality_status`, `excluded_reason`, and `quality_checked_at` in saved article rows. Count rejected rows in query results. Must not add an LLM call for quality scoring.
  Parallelization: Wave 1 | Blocked by: 1 | Blocks: 4, 6
  References (executor has NO interview context - be exhaustive): `backend/services/news_ingest.py:123`, `backend/services/news_ingest.py:149`, `backend/services/news_ingest.py:188`, `backend/services/news_ingest.py:235`, `backend/services/news_ingest.py:237`, `backend/services/news_ingest.py:277`, `backend/services/news_ingest.py:279`, `backend/services/news_ingest.py:310`
  Acceptance criteria (agent-executable): Tests prove Samsung/Nvidia/Bitcoin relevant samples pass, exact high-quality samples get 30-day status, and Wikipedia/Namu/Kin/dictionary/off-topic samples are rejected before repository upsert.
  QA scenarios (name the exact tool + invocation): Happy: `pytest backend/tests -k news_quality` passes and captures accepted/rejected status matrix in `.omo/evidence/task-3-news-auto-retention-quality-gate.md`. Failure: a Naver result returned for a Samsung query but with no Samsung/symbol/alias mention is rejected and counted; record evidence.
  Commit: Y | `feat(news): 종목 뉴스 저장 전 품질 게이트 추가`

- [x] 4. Make symbol news retrieval exact-first and relevance-ranked
  What to do / Must NOT do: Extend `NewsRepository.list_articles` and `count_articles` to accept `symbol` separately from free-text `query`. For symbol requests, query exact `symbol=eq.<SYMBOL>` first, order by `quality_status` high-quality priority, `relevance_score.desc`, then `published_at.desc`; only fallback to text search when exact rows are below the requested limit. Update `/api/news` so `symbol` is passed as symbol, not converted into display-name-only query. Keep existing free-text query behavior for non-symbol searches.
  Parallelization: Wave 2 | Blocked by: 3 | Blocks: 6
  References (executor has NO interview context - be exhaustive): `backend/routes/news.py:9`, `backend/routes/news.py:24`, `backend/routes/news.py:29`, `backend/routes/news.py:34`, `backend/routes/news.py:67`, `backend/routes/news.py:70`, `backend/services/news_repository.py:18`, `backend/services/news_repository.py:55`, `backend/services/news_repository.py:57`, `backend/services/news_repository.py:93`
  Acceptance criteria (agent-executable): Route/repository tests show `/api/news?symbol=005930` prioritizes `symbol='005930'` rows over title-only matches, and free-text `/api/news?query=반도체` still works.
  QA scenarios (name the exact tool + invocation): Happy: `pytest backend/tests -k news_symbol_lookup` passes and writes response ordering evidence to `.omo/evidence/task-4-news-auto-retention-quality-gate.md`. Failure: when exact symbol results are empty, fallback text search runs and returns only active rows; record evidence.
  Commit: Y | `fix(news): 종목 뉴스 조회를 정확 매칭 우선으로 변경`

- [x] 5. Wire automatic cleanup into the worker/scheduler safely
  What to do / Must NOT do: Add cleanup execution to the existing news scheduler path under the same distributed lock or a dedicated `news_retention_cleanup` lock. Ensure cleanup runs at most once per day, preferably before or after `run_once`, and logs deleted counts. Provide an explicit service method callable in tests. Must not create an unauthenticated HTTP cleanup endpoint. Must not run cleanup on every request to `/api/news`.
  Parallelization: Wave 2 | Blocked by: 1, 2 | Blocks: 6
  References (executor has NO interview context - be exhaustive): `backend/services/ml_scheduler.py:145`, `backend/services/ml_scheduler.py:159`, `backend/services/ml_scheduler.py:161`, `backend/services/ml_scheduler.py:171`, `backend/services/ml_scheduler.py:178`, `backend/app.py:155`, `backend/worker.py:60`
  Acceptance criteria (agent-executable): Scheduler tests/fakes prove cleanup is invoked once per day, uses service-role repository methods, and does not block news ingestion if cleanup fails.
  QA scenarios (name the exact tool + invocation): Happy: `pytest backend/tests -k news_cleanup_scheduler` passes and writes invocation/log evidence to `.omo/evidence/task-5-news-auto-retention-quality-gate.md`. Failure: fake cleanup exception logs an error and subsequent ingest still executes; record evidence.
  Commit: Y | `feat(news): 뉴스 보관 정리를 스케줄러에 연결`

- [x] 6. Backfill, verify DB impact, and update documentation
  What to do / Must NOT do: Add a safe backfill/one-off script or migration-safe SQL plan to classify recent rows with default `PASS`/`HIGH_QUALITY` where possible, then run cleanup against expired rows only after tests pass. Update `database_specification.md`, `project_structure.md` if applicable, and any news/Tavily status docs that describe current provider/retention behavior. Capture before/after Supabase counts and sizes. Must not claim reclaimed disk bytes unless measured with `pg_database_size`/`pg_total_relation_size` after cleanup.
  Parallelization: Wave 3 | Blocked by: 2, 4, 5 | Blocks: final verification
  References (executor has NO interview context - be exhaustive): `database_specification.md:225`, `database_specification.md:247`, `docs/2026-07-09-obsidian-vector-tavily-status.md:160`, `docs/2026-07-09-obsidian-vector-tavily-status.md:168`, `docs/2026-07-09-obsidian-vector-tavily-status.md:402`, `docs/2026-07-09-obsidian-vector-tavily-status.md:410`
  Acceptance criteria (agent-executable): Supabase MCP queries show expired general news/logs are gone, high-quality news younger than 30 days remains, and current DB size/headroom is recorded.
  QA scenarios (name the exact tool + invocation): Happy: Supabase MCP `_execute_sql` count/size query output is saved to `.omo/evidence/task-6-news-auto-retention-quality-gate.md`. Failure: if cleanup cannot run due to permissions or constraints, evidence records exact error and no documentation claims cleanup succeeded.
  Commit: Y | `docs(news): 뉴스 보관 정책과 검증 결과 기록`

## Final verification wave
> Runs in parallel after ALL todos. ALL must APPROVE. Surface results and wait for the user's explicit okay before declaring complete.
- [x] F1. Plan compliance audit: verify all six todos are complete, no collection-rate reductions were made, Tavily remains chatbot fallback only, Tavily was not added to scheduled ingestion, and DART cleanup was not touched.
- [x] F2. Code quality review: inspect changed backend services/routes/migrations for raw secret exposure, raw exception exposure, broad destructive SQL, and broken Korean comments/strings.
- [x] F3. Real manual QA: run backend tests, call `/api/news?symbol=005930&limit=5` and one crypto/US-stock symbol path through the local API if a server is available, and capture response ordering.
- [x] F4. Scope fidelity: run Supabase MCP count/size checks and confirm Free-plan projection is safe after cleanup.

## Commit strategy
- Prefer atomic commits by todo after tests pass.
- Commit messages must keep Conventional Commit prefix in English and Korean summary after the colon:
  - `feat(news): 뉴스 품질 메타데이터 스키마 추가`
  - `feat(news): 뉴스 자동 보관 정리 서비스 추가`
  - `feat(news): 종목 뉴스 저장 전 품질 게이트 추가`
  - `fix(news): 종목 뉴스 조회를 정확 매칭 우선으로 변경`
  - `feat(news): 뉴스 보관 정리를 스케줄러에 연결`
  - `docs(news): 뉴스 보관 정책과 검증 결과 기록`
- Do not amend or squash unless the user explicitly requests it.

## Success criteria
- Supabase schema has quality metadata and cleanup-supporting indexes.
- General news older than 7 days is physically deleted by automatic cleanup.
- High-quality news is retained until 30 days and physically deleted after that.
- News fetch logs older than 7 days are physically deleted.
- Current news collection budget/cadence remains unchanged.
- Naver/Finnhub ingestion rejects wiki-like, off-topic, and non-financial results before upsert.
- Tavily remains available for chatbot fallback but is not used by scheduled ingestion.
- Symbol news lookup is exact-first and relevance-ranked.
- Tests pass and Supabase DB count/size evidence is saved under `.omo/evidence`.
- Documentation matches the implemented retention and quality policy.
