# F2 Code Quality Review Rerun - news-auto-retention-quality-gate

Date: 2026-07-16

## Verdict

- codeQualityStatus: BLOCK
- recommendation: REQUEST_CHANGES
- confidence: high
- F2 may be marked complete: NO

## Scope Reviewed

- `backend/routes/news.py`
- `backend/services/news_repository.py`
- `backend/services/news_retention_service.py`
- `backend/services/news_error_sanitizer.py`
- `backend/services/news_filter_validation.py`
- `backend/services/news_quality_service.py`
- `backend/services/news_ingest.py`
- `backend/services/ml_scheduler.py`
- `backend/services/chatbot/web_fallback_search_service.py`
- Relevant tests under `backend/tests/*news*`
- `supabase/migrations/20260716151440_add_news_quality_metadata_retention_indexes.sql`
- Docs and evidence under `.omo/evidence`

## Skill Perspective Check

- `omo:remove-ai-slops`: available and loaded. Current tests are mostly behavior-focused and no deletion-only/tautological tests were accepted as proof, but the suite still misses an adversarial symbol fallback pagination/count case.
- `omo:programming`: available and loaded with Python README and code-smell reference. The diff still violates the oversized-module rule, especially `backend/services/news_repository.py`, which grew from 233 to 403 pure LOC.
- Result: the skill-perspective check ran. The current diff still violates both perspectives through an uncovered fallback pagination/count defect and incomplete oversized-module containment.

## Verification Run By Reviewer

- `python -m pytest -p no:cacheprovider backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py backend/tests/test_news_ingest_quality.py backend/tests/test_chatbot_web_fallback_news_quality.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_cleanup_scheduler.py -q`
  - `26 passed in 12.60s`
- `python -m pytest -p no:cacheprovider backend/tests -k "news" -q`
  - `90 passed, 306 deselected in 61.38s`
- Python compile check for scoped services/tests
  - all checked files compiled successfully
- `git diff --check <merge-base> -- <scoped files>`
  - no whitespace errors; only LF-to-CRLF warnings

## CRITICAL

None.

## HIGH

1. Symbol fallback pagination and count semantics are still wrong for sparse exact-symbol result sets.

   - `backend/services/news_repository.py:100` to `backend/services/news_repository.py:118` returns `exact_count` immediately when any exact-symbol rows exist.
   - `backend/services/news_repository.py:141` to `backend/services/news_repository.py:169` can still append fallback text-search rows when exact rows are fewer than the requested page size.
   - That combination can return more items than `totalCount` reports. Reviewer reproduction with two exact rows and three fallback rows returned five list items but `count_articles()` returned `2`.
   - `backend/services/news_repository.py:141` to `backend/services/news_repository.py:169` also applies `offset` only to exact rows. If `offset` crosses the exact rows into fallback rows, fallback starts at the beginning instead of skipping `offset - exact_count` fallback rows. Reviewer reproduction for combined `[e1,e2,f1,f2,f3]`, `limit=2`, `offset=3` returned `['f1','f2']`; expected `['f2','f3']`.
   - Existing `test_news_symbol_lookup.py` covers exact-first ranking and empty-exact fallback, but not this mixed exact+fallback pagination/count edge.

2. Oversized module containment remains incomplete in the main touched repository seam.

   - `backend/services/news_repository.py` grew from 233 pure LOC at merge-base to 403 pure LOC now.
   - The added symbol exact/fallback listing, count fallback, quality defaults, and retention delegation are all in the same repository class.
   - `backend/services/news_ingest.py` remains 384 pure LOC, `backend/services/ml_scheduler.py` remains 610 pure LOC, and `backend/services/chatbot/web_fallback_search_service.py` remains 1345 pure LOC after scoped edits.
   - Some helper extraction happened (`news_retention_service.py`, `news_filter_validation.py`, `news_quality_service.py`, `news_error_sanitizer.py`), but the largest new behavior still expanded the repository past the 250 pure-LOC ceiling. Under the required programming/remove-ai-slops perspectives, this is a blocking maintainability issue for F2.

## MEDIUM

1. The quality scoring boundary still uses raw `dict[str, Any]` and repository-level visible defaults.

   - `backend/services/news_quality_service.py:128` and `backend/services/news_quality_service.py:159` accept and return raw article dictionaries.
   - `backend/services/news_repository.py:405` to `backend/services/news_repository.py:420` turns missing quality metadata into visible `PASS` rows.
   - Current production callers found by `rg "upsert_articles\(" backend` now score before upsert, so this was not elevated to HIGH in this rerun. It remains a programming-perspective violation and should be tightened with a typed article/scored-article boundary.

## LOW

None.

## Prior Blocker Status

- Finnhub token leakage: fixed in the inspected code path. `sanitize_external_error_message()` is used before route results/fetch logs, and `test_news_sync_security.py` covers a Finnhub `HTTPError` containing `token=secret-token`.
- Raw dict scoring boundary: partially mitigated by current caller coverage, not fully fixed.
- Symbol fallback pagination/ranking: not fixed; mixed exact+fallback pagination/count remains HIGH.
- Missing tests: partially fixed, but the mixed exact+fallback pagination/count edge is still missing.
- Oversized module containment: not fixed for `news_repository.py`; still HIGH.

## Blockers

- Fix `NewsRepository` symbol list/count so exact+fallback behaves as one deterministic paginated result surface, including `totalCount` and offsets crossing from exact rows into fallback rows.
- Add regression tests for mixed exact+fallback pagination and count: nonzero exact rows below `limit`, nonzero exact rows below `offset`, fallback duplicate suppression, and count consistency with returned pages.
- Contain the newly added repository responsibilities by extracting symbol lookup/count composition into a focused module or otherwise bringing the touched seam back under the agreed size/maintainability bar.

## Final Status

FAIL. F2 should not be marked complete.
