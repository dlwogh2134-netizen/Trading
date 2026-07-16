# Task 6 Evidence - News Backfill, DB Impact, Documentation

## Scope
- Todo: `6. Backfill, verify DB impact, and update documentation`
- Supabase project: `fdvhoaytcqnswuebocmr`
- Production DDL applied: yes, through Supabase MCP `_apply_migration(name="add_news_quality_metadata_retention_indexes")`.
- Production backfill applied: yes, through Supabase MCP `_execute_sql`.
- Production cleanup applied: yes, through Supabase MCP `_execute_sql` filtered physical deletes.
- Added SQL/script file: none. The one-off backfill and cleanup SQL is recorded below.

## Required Test Gate Before Cleanup
- Scenario: Todo 2-5 backend tests pass before live cleanup.
- Invocation: `python -m pytest backend/tests -k "news_retention or news_quality or news_symbol_lookup or news_cleanup_scheduler" -q -p no:cacheprovider`
- Binary observable: `12 passed, 370 deselected in 11.33s`
- Captured artifact: `.omo/evidence/task-6-news-auto-retention-quality-gate.md`

## Supabase Changelog Check
- Scenario: Supabase skill-required changelog scan before DB work.
- Invocation: `Invoke-WebRequest -Uri 'https://supabase.com/changelog.md' -UseBasicParsing -TimeoutSec 20`
- Result summary: changelog reachable. Relevant breaking changes found were Data API exposure for new tables and pg_graphql/self-hosted items; this task altered existing `public.news_articles`/`public.news_fetch_logs` columns and indexes, so no blocker applied.

## Before Counts And Sizes

### Size Snapshot Before DDL/Backfill/Cleanup
- Scenario: record database and relation sizes before any mutation.
- Invocation: Supabase MCP `_execute_sql`
```sql
select
  current_timestamp as measured_at,
  pg_database_size(current_database()) as database_bytes,
  pg_size_pretty(pg_database_size(current_database())) as database_size,
  pg_total_relation_size('public.news_articles'::regclass) as news_articles_bytes,
  pg_size_pretty(pg_total_relation_size('public.news_articles'::regclass)) as news_articles_size,
  pg_total_relation_size('public.news_fetch_logs'::regclass) as news_fetch_logs_bytes,
  pg_size_pretty(pg_total_relation_size('public.news_fetch_logs'::regclass)) as news_fetch_logs_size,
  exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='news_articles' and column_name='quality_status'
  ) as has_quality_status;
```
- Result summary: `measured_at=2026-07-16 06:49:16.892204+00`; DB `343,772,307` bytes (`328 MB`); `news_articles` `91,914,240` bytes (`88 MB`); `news_fetch_logs` `18,153,472` bytes (`17 MB`); `has_quality_status=false`.

### Count Snapshot Before DDL/Backfill/Cleanup
- Scenario: retention counts before quality metadata existed.
- Invocation: Supabase MCP `_execute_sql`
```sql
select
  count(*) as news_total,
  count(*) filter (where published_at >= current_timestamp - interval '7 days') as news_recent_under_7d,
  count(*) filter (where published_at < current_timestamp - interval '7 days') as news_expired_normal_policy,
  0 as news_high_quality_under_30d_pre_migration,
  0 as news_expired_high_quality_policy_pre_migration,
  count(*) filter (where published_at is null) as news_without_published_at
from public.news_articles;
```
- Result summary: total `37,103`; recent under 7 days `12,036`; expired normal-policy rows `25,067`; pre-migration high-quality rows `0`; rows without `published_at` `0`.
- Invocation: Supabase MCP `_execute_sql`
```sql
select
  count(*) as fetch_logs_total,
  count(*) filter (where started_at >= current_timestamp - interval '7 days') as fetch_logs_recent_under_7d,
  count(*) filter (where started_at < current_timestamp - interval '7 days') as fetch_logs_expired_7d,
  count(*) filter (where started_at is null) as fetch_logs_without_started_at
from public.news_fetch_logs;
```
- Result summary: total `47,862`; recent under 7 days `15,192`; expired 7-day logs `32,670`; rows without `started_at` `0`.

## DDL Verification
- Scenario: migration history lacked the Todo 1 migration before applying.
- Invocation: Supabase MCP `_list_migrations(project_id="fdvhoaytcqnswuebocmr")`
- Result summary: latest listed migration before this work was `20260715110000 create_admin_symbol_reconciliation`; `add_news_quality_metadata_retention_indexes` was absent.
- Scenario: apply additive, idempotent quality metadata migration.
- Invocation: Supabase MCP `_apply_migration(name="add_news_quality_metadata_retention_indexes")`
- Binary observable: `{"success":true}`
- Scenario: inspect quality columns after DDL.
- Invocation: Supabase MCP `_execute_sql` against `information_schema.columns`.
- Result summary: `excluded_reason text`, `quality_checked_at timestamp with time zone`, `quality_status text`, `relevance_score integer`; all nullable.
- Scenario: inspect cleanup indexes after DDL.
- Invocation: Supabase MCP `_execute_sql` against `pg_indexes`.
- Result summary: `idx_news_articles_quality_status_published_at`, `idx_news_articles_symbol_quality_status_published_at`, and `idx_news_fetch_logs_started_at` exist.
- Scenario: check constraint rejects invalid status.
- Invocation: Supabase MCP `_execute_sql` attempted `quality_status='BAD'` insert inside a transaction.
- Binary observable: rejected with Postgres `23514` on `news_articles_quality_status_check`.
- Follow-up invocation: Supabase MCP `_execute_sql` counted `url='https://example.invalid/news-quality-constraint-test'`.
- Result summary: `invalid_constraint_test_rows=0`.

## Backfill SQL And Results
- Scenario: estimate conservative high-quality candidates before update.
- Invocation: Supabase MCP `_execute_sql`.
- Result summary: under-30-day candidate rows `36,991`; high-quality candidates `9,372`; rows under 7 days with symbol and company `5,061`.
- Scenario: classify recent rows with default metadata.
- Invocation: Supabase MCP `_execute_sql`
```sql
with classified as (
  select
    id,
    case
      when nullif(btrim(symbol), '') is not null
        and nullif(btrim(company_name), '') is not null
        and (
          lower(coalesce(title, '') || ' ' || coalesce(summary, '')) like '%' || lower(company_name) || '%'
          or lower(coalesce(title, '') || ' ' || coalesce(summary, '')) like '%' || lower(symbol) || '%'
        )
        and (
          coalesce(title, '') || ' ' || coalesce(summary, '') ~* '(주가|증시|시장|실적|매출|영업이익|전망|투자|반도체|코스피|나스닥|stock|earnings|revenue|market|crypto|bitcoin|etf|price)'
        )
      then 'HIGH_QUALITY'
      else 'PASS'
    end as new_quality_status,
    case
      when nullif(btrim(symbol), '') is not null
        and nullif(btrim(company_name), '') is not null
        and (
          lower(coalesce(title, '') || ' ' || coalesce(summary, '')) like '%' || lower(company_name) || '%'
          or lower(coalesce(title, '') || ' ' || coalesce(summary, '')) like '%' || lower(symbol) || '%'
        )
        and (
          coalesce(title, '') || ' ' || coalesce(summary, '') ~* '(주가|증시|시장|실적|매출|영업이익|전망|투자|반도체|코스피|나스닥|stock|earnings|revenue|market|crypto|bitcoin|etf|price)'
        )
      then 80
      else 45
    end as new_relevance_score
  from public.news_articles
  where quality_status is null
    and published_at >= current_timestamp - interval '30 days'
), updated as (
  update public.news_articles article
  set quality_status = classified.new_quality_status,
      relevance_score = classified.new_relevance_score,
      excluded_reason = null,
      quality_checked_at = current_timestamp
  from classified
  where article.id = classified.id
  returning article.quality_status
)
select
  count(*) as updated_total,
  count(*) filter (where quality_status = 'HIGH_QUALITY') as updated_high_quality,
  count(*) filter (where quality_status = 'PASS') as updated_pass
from updated;
```
- Result summary: updated `36,991` rows; `9,372` `HIGH_QUALITY`; `27,619` `PASS`.
- Pre-delete after-backfill snapshot: news total `37,103`; `HIGH_QUALITY` under 30 days `9,372`; expired high-quality `0`; expired normal-policy rows `19,084`; `PASS` under 7 days `8,647`; quality null `112`.

## Cleanup SQL And Results
- Scenario: physically delete expired rows only.
- Invocation: Supabase MCP `_execute_sql`
```sql
with deleted_high_quality as (
  delete from public.news_articles
  where quality_status = 'HIGH_QUALITY'
    and published_at < current_timestamp - interval '30 days'
  returning id
), deleted_normal as (
  delete from public.news_articles
  where (quality_status is distinct from 'HIGH_QUALITY')
    and published_at < current_timestamp - interval '7 days'
  returning id
), deleted_logs as (
  delete from public.news_fetch_logs
  where started_at < current_timestamp - interval '7 days'
  returning id
)
select
  (select count(*) from deleted_high_quality) as deleted_high_quality_news,
  (select count(*) from deleted_normal) as deleted_normal_news,
  (select count(*) from deleted_logs) as deleted_fetch_logs;
```
- Result summary: deleted high-quality news `0`; deleted normal news `19,084`; deleted fetch logs `32,670`.

## After Verification

### Policy Counts
- Scenario: expired news gone and high-quality under 30 days remains.
- Invocation: Supabase MCP `_execute_sql`.
- Result summary: `measured_at=2026-07-16 06:55:14.45158+00`; news total `18,019`; expired general news remaining `0`; expired high-quality news remaining `0`; high-quality under 30 days remaining `9,372`; `PASS` under 7 days remaining `8,647`; null quality status remaining `0`; oldest remaining news `2026-06-16 21:00:00+00`; newest remaining news `2026-07-16 06:28:00+00`.
- Scenario: expired fetch logs gone.
- Invocation: Supabase MCP `_execute_sql`.
- Result summary: `measured_at=2026-07-16 06:55:24.247598+00`; fetch logs total `15,192`; expired fetch logs remaining `0`; recent fetch logs remaining `15,192`; oldest remaining fetch log `2026-07-09 07:08:04.940796+00`; newest remaining fetch log `2026-07-16 06:32:33.57864+00`.

### Size And Headroom
- Scenario: measure database and relation size after DDL/backfill/cleanup.
- Invocation: Supabase MCP `_execute_sql` with `pg_database_size` and `pg_total_relation_size`.
- Result summary: `measured_at=2026-07-16 06:55:04.380249+00`; DB `406,006,931` bytes (`387 MB`); `news_articles` `153,559,040` bytes (`146 MB`); `news_fetch_logs` `18,726,912` bytes (`18 MB`).
- Headroom summary: against a 500 MiB Free-plan database allowance, measured database size is about 387 MiB, leaving about 113 MiB measured headroom.
- Reclaimed bytes claim: not made. The measured DB/relation sizes increased after adding indexes and updating rows; deleted tuple space may be reusable internally but physical file shrink was not observed with these size functions.

## Documentation Updates
- `database_specification.md`: added news quality metadata columns, normal/HIGH_QUALITY/fetch-log physical delete policy, Tavily fallback-only note, and DART retention separation.
- `docs/2026-07-09-obsidian-vector-tavily-status.md`: added 2026-07-16 status, updated Tavily from scheduled provider recommendation to chatbot fallback only, and recorded post-cleanup row counts.
- `project_structure.md`: added `news_quality_service.py` to the service tree and described news quality/retention scheduler responsibilities.
- `backend/routes/news.py`: corrected the existing `/api/news/sync` docstring so it documents Naver/Finnhub scheduled sync and explicitly excludes Tavily scheduled ingestion.

## Final Local Verification
- Scenario: changed Python route still compiles after the docstring correction.
- Invocation: `python -m py_compile backend/routes/news.py`
- Binary observable: exit code `0`, no compiler output.
- Scenario: relevant Todo 2-5 test selectors still pass after docs/evidence/docstring updates.
- Invocation: `python -m pytest backend/tests -k "news_retention or news_quality or news_symbol_lookup or news_cleanup_scheduler" -q -p no:cacheprovider`
- Binary observable: `12 passed, 370 deselected in 15.56s`.
- Scenario: docs contain the final retention/Tavily/DART policy.
- Invocation: `rg -n "normal news 7|HIGH_QUALITY.*30|fetch logs 7|Tavily.*fallback|챗봇 최신 검색 폴백|DART.*분리|DART.*separate|일반 뉴스.*7일|news_fetch_logs.*7일|예약 뉴스 수집.*Tavily" database_specification.md docs\2026-07-09-obsidian-vector-tavily-status.md project_structure.md .omo\evidence\task-6-news-auto-retention-quality-gate.md`
- Result summary: matched policy lines in `database_specification.md`, `docs/2026-07-09-obsidian-vector-tavily-status.md`, `project_structure.md`, and this evidence file.
- Scenario: stale scheduled-Tavily wording is absent from the status doc.
- Invocation: `rg -n "Tavily 추가|Tavily provider 추가|NewsIngestService.*Tavily fetcher 추가|NewsQueryPlanner.*Tavily query|NEWS_TAVILY|_fetch_tavily|Tavily 기사도|Tavily provider는 아직 없음|provider로 저장하는 방식이 좋습니다" docs\2026-07-09-obsidian-vector-tavily-status.md`
- Binary observable: exit code `1`, no matches.
- Scenario: code guard for budgets/cadence, Tavily scheduled ingestion, and DART separation.
- Invocation: `rg -n "NEWS_NAVER_DAILY_QUERY_BUDGET|NEWS_MAX_QUERIES_PER_RUN|NEWS_MAX_ITEMS_PER_QUERY|NEWS_INGEST_INTERVAL_SECONDS|TAVILY|Tavily|tavily|dart_|DART|disclosure" backend\services\news_ingest.py backend\services\news_query_planner.py backend\services\ml_scheduler.py backend\routes\news.py backend\services\news_repository.py`
- Result summary: budget/cadence matches remain existing reads only; no `NEWS_INGEST_INTERVAL_SECONDS` edit; only Tavily match is the `/api/news/sync` docstring saying Tavily is not used for scheduled ingestion; DART matches are pre-existing DART scheduler/query-category references and no DART cleanup path was added.
- Scenario: Python changed file size check after docstring correction.
- Invocation: PowerShell pure LOC count for `backend\routes\news.py`.
- Binary observable: `backend\routes\news.py pure_loc=156`.
- Scenario: whitespace check for files touched by Todo 6.
- Invocation: `git diff --check -- database_specification.md docs\2026-07-09-obsidian-vector-tavily-status.md project_structure.md .omo\evidence\task-6-news-auto-retention-quality-gate.md .omo\plans\news-auto-retention-quality-gate.md backend\routes\news.py`
- Binary observable: exit code `0`; output contained only Git line-ending warnings (`LF will be replaced by CRLF`) and no whitespace errors.
- Scenario: final worktree audit.
- Invocation: `git status --short`
- Result summary: Todo 6 files are modified/added as expected; unrelated pre-existing modified backend trade/crypto files and prior Todo 1-5 files remain present and were not reverted.

## Adversarial Notes
- Destructive delete: live deletes were filtered by retention policy only: `HIGH_QUALITY` older than 30 days, all other news older than 7 days, and fetch logs older than 7 days. No DART table, disclosure table, `TRUNCATE`, `DROP`, or unfiltered delete was used.
- Stale state: all counts and sizes above are fresh Supabase MCP reads from 2026-07-16 after applying DDL/backfill/cleanup. Existing evidence files were read but not trusted as proof of live DB state.
- Misleading success output: `_apply_migration` success was followed by catalog checks, a check-constraint rejection test, and post-cleanup zero-expired count queries.
- Dirty worktree: unrelated modified backend/trade/crypto files and prior Todo 1-5 changes were present before this task. Todo 6 touched only documentation, this evidence file, and the Todo 6 checkbox after verification.
- Secrets redaction: `.env` and command output contained Supabase keys during local discovery; no secret values are copied into this evidence file or final report.

## Acceptance Result
- Passed: production schema metadata exists, recent rows are classified, expired general news/logs are physically deleted, `HIGH_QUALITY` news younger than 30 days remains, measured DB size/headroom is recorded, and documentation matches the final policy.
