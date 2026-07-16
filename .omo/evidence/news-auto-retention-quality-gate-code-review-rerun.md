# F2 Code Quality + Security Review Rerun - news-auto-retention-quality-gate

Date: 2026-07-16

## Verdict

- F2: FAIL
- codeQualityStatus: BLOCK
- recommendation: REQUEST_CHANGES
- reportPath: `.omo/evidence/news-auto-retention-quality-gate-code-review-rerun.md`

## Scope Reviewed

- `backend/routes/news.py`
- `backend/services/news_repository.py`
- `backend/services/news_symbol_query_service.py`
- `backend/services/news_article_query_constants.py`
- `backend/services/news_filter_validation.py`
- `backend/services/news_retention_service.py`
- `backend/services/news_error_sanitizer.py`
- `backend/services/news_quality_service.py`
- `backend/services/news_ingest.py`
- `backend/services/chatbot/web_fallback_search_service.py`
- `backend/services/ml_scheduler.py`
- `backend/services/supabase_client.py` news-adjacent service-role helper diff
- `backend/tests/test_news_symbol_lookup.py`
- `backend/tests/test_news_sync_security.py`
- `backend/tests/test_news_retention_cleanup.py`
- `backend/tests/test_news_ingest_quality.py`
- `backend/tests/test_chatbot_web_fallback_news_quality.py`
- `backend/tests/test_news_cleanup_scheduler.py`
- `supabase/migrations/20260716151440_add_news_quality_metadata_retention_indexes.sql`
- Evidence files requested by user:
  - `.omo/evidence/debug-news-security-quality-fix.md`
  - `.omo/evidence/debug-news-summary-security-fix.md`
  - `.omo/evidence/debug-news-symbol-pagination-refactor.md`

## Skill Perspective Check

- `omo:remove-ai-slops`: available and loaded. Applied as a review pass over production code and tests. The added tests are mostly behavior-focused and not deletion-only or assertion-light. However, the suite misses an adversarial resource-boundary case for public symbol pagination/count.
- `omo:programming`: available and loaded with `references/python/README.md` and `references/code-smells.md`. Applied to boundary validation, typed-ish seams, raw exception handling, and oversized modules.
- Result: skill-perspective check ran. The previous repository-size blocker is no longer a standalone blocker because symbol query composition, retention, validation, constants, and sanitization have been extracted. The diff still violates the programming/security perspective through unbounded public pagination work.

## Verification Run By Reviewer

- `python -m py_compile backend/routes/news.py backend/services/news_repository.py backend/services/news_symbol_query_service.py backend/services/news_filter_validation.py backend/services/news_retention_service.py backend/services/news_error_sanitizer.py backend/services/news_quality_service.py backend/services/news_ingest.py backend/services/chatbot/web_fallback_search_service.py backend/services/ml_scheduler.py backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_ingest_quality.py backend/tests/test_chatbot_web_fallback_news_quality.py backend/tests/test_news_cleanup_scheduler.py`
  - PASS, exit code 0.
- `python -m pytest -p no:cacheprovider backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py backend/tests/test_news_ingest_quality.py backend/tests/test_chatbot_web_fallback_news_quality.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_cleanup_scheduler.py -q`
  - PASS, `33 passed in 12.39s`.
- `python -m pytest -p no:cacheprovider backend/tests -k "news" -q`
  - PASS, `97 passed, 306 deselected in 35.71s`.
- `git diff --check -- backend/routes/news.py backend/services/news_repository.py backend/services/news_ingest.py backend/services/chatbot/web_fallback_search_service.py backend/services/ml_scheduler.py backend/services/supabase_client.py`
  - PASS for whitespace errors; only LF-to-CRLF warnings.
- Pure LOC check:
  - `backend/routes/news.py`: 168
  - `backend/services/news_repository.py`: 342
  - `backend/services/news_symbol_query_service.py`: 164
  - `backend/services/news_filter_validation.py`: 82
  - `backend/services/news_retention_service.py`: 87
  - `backend/services/news_error_sanitizer.py`: 9
  - `backend/services/news_quality_service.py`: 186
  - `backend/services/news_ingest.py`: 384
  - `backend/services/chatbot/web_fallback_search_service.py`: 1345
  - `backend/services/ml_scheduler.py`: 610

## CRITICAL

None.

## HIGH

1. Public symbol pagination can trigger unbounded Supabase reads and very large ID filters.

   - `GET /api/news` is public and passes `symbol`, `limit`, and `offset` into repository listing/counting at `backend/routes/news.py:17` and `backend/routes/news.py:41`.
   - `normalize_news_offset()` only checks `offset >= 0`; it has no upper bound at `backend/services/news_filter_validation.py:70`.
   - `NewsSymbolQueryService.list_articles()` converts public offset into a Supabase `limit` using `query.limit + query.offset` at `backend/services/news_symbol_query_service.py:67`.
   - `NewsSymbolQueryService.count_articles()` fetches every exact ID when exact count is nonzero at `backend/services/news_symbol_query_service.py:97`, then `_fetch_exact_ids()` sends `limit=max(exact_count, 1)` at `backend/services/news_symbol_query_service.py:146`.
   - Reviewer reproduction:
     - `list_articles(symbol="005930", query="Samsung", limit=100, offset=1000000)` produced first Supabase params with `limit: "1000100"`.
     - `count_articles(symbol="005930", query="Samsung")` with exact count `100000` produced a second Supabase ID-fetch request with `limit: "100000"`.
   - This is an unauthenticated resource-amplification path introduced by the exact-first pagination/count implementation. The green tests do not cover it.

   Exact fix requested:
   - Add a hard maximum for public `offset` in `normalize_news_offset()` and route tests proving excessive offsets return 400 before repository access.
   - Refactor symbol list/count composition so it never fetches `offset + limit` exact rows or all exact IDs from a public request.
   - Replace all-exact-ID duplicate suppression with a bounded strategy, such as symbol-based exclusion where equivalent, or a capped/degraded count contract that is explicit in API metadata.
   - Add regression tests for large offset and large exact-count cases proving Supabase request params stay bounded.

## MEDIUM

1. Bounded count fallback is intentionally approximate but not exposed as such.

   - `backend/services/news_symbol_query_service.py:91` returns combined unique counts when exact count calls succeed.
   - If exact count fails and the bounded exact read returns rows, `backend/services/news_symbol_query_service.py:94` returns only that bounded exact count and skips fallback counting.
   - This is acceptable as a degradation strategy only if the API makes clear that `totalCount` is approximate in this path. Today it silently looks exact.

   Exact fix requested:
   - Either preserve exact combined count semantics in this path, or return/count through an explicit approximate metadata contract and test it.

## LOW

1. Oversized inherited modules remain a residual maintainability risk.

   - The prior `news_repository.py` blocker is materially addressed: symbol query behavior moved to `news_symbol_query_service.py`; constants, validation, retention, and sanitization are also extracted.
   - `news_repository.py` remains 342 pure LOC, while `news_ingest.py`, `web_fallback_search_service.py`, and `ml_scheduler.py` remain much larger. These are not blocking this rerun under the user's reassessment criterion, but future changes should continue extracting responsibilities instead of adding to these files.

## Checks That Passed

- Normal exact-first symbol semantics are now coherent in the green tests:
  - exact rows rank before fallback rows;
  - fallback excludes exact IDs;
  - offsets crossing from exact rows into fallback rows are covered;
  - exact plus fallback count is covered for ordinary exact-count success.
- Public `GET /api/news` is read-only in the inspected route; it no longer generates summaries or performs service-role writes.
- `POST /api/news/sync` and `POST /api/news/summaries/ensure` are protected by `X-Admin-Token`.
- Query, symbol, market, limit, offset, and article ID validation now run before route/repository PostgREST filter construction, except for the unbounded offset issue above.
- Finnhub token leakage through per-query error output/log rows is covered by tests and sanitized by `news_error_sanitizer.py`.
- Retention deletion is scoped to `news_articles` and `news_fetch_logs` in `news_retention_service.py`; no DART delete path was introduced.
- The migration adds quality metadata, quality status check constraint, and news/fetch-log retention indexes without touching DART tables.

## Test Quality Review

- The new symbol, route security, retention, ingest quality, fallback quality, and scheduler tests assert observable behavior and request shapes. They are not merely deletion-only or tautological.
- The meaningful missing test is adversarial: large public offset and large exact-count conditions should prove request parameters remain bounded.

## Prior Blocker Status

- Mixed exact-symbol + fallback pagination/count semantics: mostly fixed for ordinary exact-count success.
- `news_repository.py` oversized/new responsibilities: pass under the user-specified reassessment criterion; the new responsibilities are sufficiently extracted even though inherited size remains high.
- Security around unauthenticated cost/write routes and filter/ID validation: mostly fixed, but the public offset/resource-amplification issue remains a HIGH security-quality blocker.

## Blockers

- Bound public news pagination and refactor symbol list/count so unauthenticated requests cannot create massive Supabase reads or massive `not.in.(...)` ID filters.
- Add adversarial regression tests for large offset and large exact count.

## Final Status

FAIL. F2 should remain open.
