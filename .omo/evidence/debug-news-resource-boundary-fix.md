# Debug News Resource Boundary Fix

## Changed files

- `backend/services/news_filter_validation.py`
- `backend/services/news_symbol_query_service.py`
- `backend/tests/test_news_symbol_lookup.py`
- `backend/tests/test_news_sync_security.py`

## Resource-boundary contract

- Public `GET /api/news` accepts `offset` only in the inclusive range `0..1000`; out-of-range values raise `NewsFilterValidationError` and the route returns `400` before repository access.
- Public `GET /api/news` still accepts `limit` only in the inclusive range `1..100`.
- Symbol article listing fetches exact symbol rows as the requested page only: `limit <= 100`, with the normalized `offset`. It no longer requests `offset + limit` exact rows.
- Symbol fallback listing preserves exact-first virtual pagination. When exact rows do not fill the requested page, fallback offset is computed from the exact symbol count, and exact IDs are excluded only when the exclusion set is bounded.
- Exact ID exclusion is capped at `1100` IDs. This covers the public offset window (`1000`) plus max page size (`100`) without allowing unbounded ID reads.
- Symbol count is exact while exact ID exclusion is within `1100`. When exact count is above `1100`, fallback count is deterministic but approximate because it skips ID exclusion rather than fetching all exact IDs.

## Verification

- Scenario: huge public offset rejected before repository requests.
  - Invocation: `PYTHONPATH=. pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py -q`
  - Binary observable: `28 passed`
  - Test observable: `test_news_query_rejects_postgrest_filter_injection_inputs[/api/news?offset=1000000-offset]` asserts `400` and `repository.called is False`.
  - Artifact: `.omo/evidence/debug-news-resource-boundary-fix-targeted-pytest.txt`

- Scenario: large allowed symbol list offset does not request `offset + limit` exact rows.
  - Invocation: `PYTHONPATH=. pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py -q`
  - Binary observable: `28 passed`
  - Test observable: `test_symbol_lookup_large_offset_uses_bounded_exact_page` asserts exact params `limit == "100"`, `offset == "900"`, and no `limit == "1000"`.
  - Artifact: `.omo/evidence/debug-news-resource-boundary-fix-targeted-pytest.txt`

- Scenario: large exact symbol count does not fetch all exact IDs.
  - Invocation: `PYTHONPATH=. pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py -q`
  - Binary observable: `28 passed`
  - Test observable: `test_symbol_count_large_exact_count_does_not_fetch_all_exact_ids` asserts no `limit == "100000"`, no fallback `id` exclusion, and deterministic approximate count `100500`.
  - Artifact: `.omo/evidence/debug-news-resource-boundary-fix-targeted-pytest.txt`

- Scenario: impacted news suite remains green.
  - Invocation: `PYTHONPATH=. pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py backend/tests/test_news_ingest_quality.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_cleanup_scheduler.py backend/tests/test_chatbot_web_fallback_news_quality.py -q`
  - Binary observable: `36 passed`
  - Artifact: `.omo/evidence/debug-news-resource-boundary-fix-impacted-pytest.txt`

- Scenario: changed Python files compile.
  - Invocation: `python -m py_compile backend/services/news_filter_validation.py backend/services/news_symbol_query_service.py backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py`
  - Binary observable: exit `0`
  - Artifact: `.omo/evidence/debug-news-resource-boundary-fix-pycompile.txt`

- Scenario: post-write LOC audit recorded for changed files.
  - Invocation: `awk` non-blank, non-comment line count over changed files.
  - Binary observable: evidence file written with counts.
  - Artifact: `.omo/evidence/debug-news-resource-boundary-fix-loc.txt`

## Remaining risk

- For symbols with more than `1100` exact rows, `totalCount` may overcount fallback rows that duplicate exact rows. This is intentional to avoid unbounded public reads.
- Pytest emitted a `.pytest_cache` permission warning, but all invoked tests exited `0`.
