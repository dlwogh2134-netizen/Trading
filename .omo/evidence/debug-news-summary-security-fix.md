# News Summary Security Fix Evidence

## Scope

- Route: `backend/routes/news.py`
- Repository: `backend/services/news_repository.py`
- Validation: `backend/services/news_filter_validation.py`
- Tests: `backend/tests/test_news_sync_security.py`

## Root Cause

- `GET /api/news` summarized the newest article on a public read request and wrote the result through `upsert_article_summaries`.
- `POST /api/news/summaries/ensure` entered repository reads, LLM summary generation, and service-role writes without checking the admin token.
- `NewsRepository.list_articles_by_ids` interpolated unvalidated caller input into `id=in.(...)`.

## Fix Notes

- `GET /api/news` is read-only: no summary service access and no summary upsert path.
- `POST /api/news/summaries/ensure` now uses the same `X-Admin-Token` gate as `/api/news/sync`; unauthenticated requests return 403 before repository/LLM/write calls.
- `article_ids` are parsed as UUIDs in `normalize_news_article_ids` before route and repository use. Invalid IDs return 400 at the route and raise before `requests.get` in the repository.
- Admin ensure still generates missing summaries and writes only after token and UUID validation.
- Secret/cost/write note: unauthenticated summary endpoints perform zero LLM summarize calls, zero service-role summary writes, and invalid `article_ids` cannot reach raw PostgREST filter construction.

## Red Evidence

Scenario: public GET with missing cached summary must be read-only.

- Invocation: `python -m pytest backend/tests/test_news_sync_security.py -q`
- Observable before fix: `test_news_feed_is_read_only_when_cached_summary_is_missing` failed because returned `ai_summary` was `요약된 뉴스입니다.`
- Captured artifact: `.omo/evidence/debug-news-summary-security-fix.md`

Scenario: unauthenticated ensure must be denied before cost/write.

- Invocation: `python -m pytest backend/tests/test_news_sync_security.py -q`
- Observable before fix: `test_news_summary_ensure_rejects_unauthenticated_cost_write_route` failed with `assert 200 == 403`
- Captured artifact: `.omo/evidence/debug-news-summary-security-fix.md`

Scenario: invalid article ID must not reach PostgREST filter/request.

- Invocation: `python -m pytest backend/tests/test_news_sync_security.py -q`
- Observable before fix: `test_news_summary_ensure_rejects_invalid_article_id_before_repository` failed with `assert 200 == 400`
- Observable before fix: `test_news_repository_rejects_invalid_article_id_before_postgrest_filter` failed because `requests.get` was called with invalid `article_ids`
- Captured artifact: `.omo/evidence/debug-news-summary-security-fix.md`

## Green Evidence

Scenario: focused news security route and repository tests.

- Invocation: `python -m pytest backend/tests/test_news_sync_security.py -q`
- Observable after fix: `11 passed, 1 warning in 7.12s`
- Captured artifact: `.omo/evidence/debug-news-summary-security-fix.md`

Scenario: requested news security/symbol/retention/quality/scheduler pytest set.

- Invocation: `python -m pytest backend/tests/test_news_sync_security.py backend/tests/test_news_symbol_lookup.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_ingest_quality.py backend/tests/test_chatbot_web_fallback_news_quality.py backend/tests/test_news_cleanup_scheduler.py -q`
- Observable after fix: `31 passed, 1 warning in 6.79s`
- Captured artifact: `.omo/evidence/debug-news-summary-security-fix.md`

Scenario: Python compile diagnostics for changed news modules/tests.

- Invocation: `python -m py_compile backend/routes/news.py backend/services/news_repository.py backend/services/news_filter_validation.py backend/tests/test_news_sync_security.py`
- Observable after fix: exit code `0`, no stdout/stderr.
- Captured artifact: `.omo/evidence/debug-news-summary-security-fix.md`

Scenario: whitespace/conflict scan for touched files.

- Invocation: `git diff --check -- backend/routes/news.py backend/services/news_repository.py backend/services/news_filter_validation.py backend/tests/test_news_sync_security.py`
- Observable after fix: exit code `0`; only CRLF normalization warnings for existing tracked files.
- Captured artifact: `.omo/evidence/debug-news-summary-security-fix.md`

## Changed Files

- `backend/routes/news.py`
- `backend/services/news_repository.py`
- `backend/services/news_filter_validation.py`
- `backend/tests/test_news_sync_security.py`
- `.omo/evidence/debug-news-summary-security-fix.md`

## Residual Notes

- `backend/services/news_repository.py` is an inherited oversized module at 404 pure LOC. I did not split it because the requested security fix was narrow and the worktree already contains broader unrelated edits.
- Pytest reported a pre-existing `.pytest_cache` permission warning: `could not create cache path D:\KDH\Trading\.pytest_cache\... [WinError 5]`.
