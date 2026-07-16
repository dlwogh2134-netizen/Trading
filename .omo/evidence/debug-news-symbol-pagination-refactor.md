# debug-news-symbol-pagination-refactor

## Changed files

- `backend/services/news_repository.py`
  - Delegates symbol-specific list/count behavior to `NewsSymbolQueryService`.
  - Keeps free-text non-symbol list/count request shape unchanged.
  - Keeps visible reads constrained to `quality_status=in.(PASS,HIGH_QUALITY,LOW_CONFIDENCE)`.
- `backend/services/news_symbol_query_service.py`
  - New focused symbol query composition service.
  - Builds the virtual result list as exact symbol rows first, then fallback text rows excluding exact IDs.
  - Applies fallback offsets as `max(0, requested_offset - exact_row_count)`.
  - Combines counts as exact count plus fallback count with `id=not.in.(exact IDs)`.
- `backend/services/news_article_query_constants.py`
  - Extracted shared news article select/order/quality constants.
- `backend/tests/test_news_symbol_lookup.py`
  - Added red/green coverage for combined exact+fallback count and fallback offset crossing.
  - Existing coverage continues to verify older `HIGH_QUALITY` exact rows rank above newer `PASS` exact rows.

## Behavior contract verified

- Scenario: exact rows fewer than requested and fallback text rows exist.
  - Invocation: `NewsRepository.count_articles(query="삼성전자", symbol="005930")`.
  - Binary observable: returns `5` from 2 exact rows plus 3 fallback rows, and fallback count request includes `id=not.in.(exact-1,exact-2)`.
  - Artifact: this file, plus test `test_symbol_count_combines_exact_and_fallback_unique_rows`.
- Scenario: requested offset crosses exact rows into fallback rows.
  - Invocation: two consecutive `NewsRepository.list_articles(query="삼성전자", symbol="005930", limit=3, offset=0/3)` calls.
  - Binary observable: first page IDs are `exact-1, exact-2, fallback-1`; second page IDs are `fallback-2, fallback-3, fallback-4`; page ID sets are disjoint; second fallback request uses `offset=1`.
  - Artifact: this file, plus test `test_symbol_lookup_offsets_across_exact_then_fallback_without_duplicates`.
- Scenario: older high-quality exact row competes with newer pass exact row.
  - Invocation: `NewsRepository.list_articles(symbol="005930", limit=1)`.
  - Binary observable: returns `older-high`, preserving exact symbol ranking by quality before recency.
  - Artifact: this file, plus existing test `test_symbol_lookup_fetches_exact_rows_by_quality_before_recency_limit`.

## Verification commands and results

- Red test run:
  - Command: `$env:PYTHONPATH='.'; pytest backend/tests/test_news_symbol_lookup.py -q`
  - Result: failed for the intended behavior, with `assert 2 == 5` in `test_symbol_count_combines_exact_and_fallback_unique_rows` and missing fallback `id=not.in.(exact-1,exact-2)` in `test_symbol_lookup_offsets_across_exact_then_fallback_without_duplicates`.
- Focused green run:
  - Command: `$env:PYTHONPATH='.'; pytest backend/tests/test_news_symbol_lookup.py -q`
  - Result: `14 passed, 1 warning in 12.20s`.
- Impacted news suite:
  - Command: `$env:PYTHONPATH='.'; pytest backend/tests/test_news_sync_security.py backend/tests/test_news_ingest_quality.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_cleanup_scheduler.py backend/tests/test_chatbot_web_fallback_news_quality.py -q`
  - Result: `19 passed, 1 warning in 13.04s`.
- Combined impacted suite:
  - Command: `$env:PYTHONPATH='.'; pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py backend/tests/test_news_ingest_quality.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_cleanup_scheduler.py backend/tests/test_chatbot_web_fallback_news_quality.py -q`
  - Result: `33 passed, 1 warning in 7.49s`.
- Bytecode compile:
  - Command: `python -m py_compile backend/services/news_repository.py backend/services/news_symbol_query_service.py backend/services/news_article_query_constants.py backend/tests/test_news_symbol_lookup.py`
  - Result: exit code `0`.
- LSP diagnostics:
  - Command: `mcp__lsp.diagnostics` on `backend/services/news_repository.py`, `backend/services/news_symbol_query_service.py`, `backend/services/news_article_query_constants.py`, and `backend/tests/test_news_symbol_lookup.py`.
  - Result: no diagnostics found.
- Size check:
  - Command: pure LOC counter over changed Python files.
  - Result: `backend/services/news_repository.py: 342 pure LOC`; `backend/services/news_symbol_query_service.py: 164 pure LOC`; `backend/services/news_article_query_constants.py: 14 pure LOC`; `backend/tests/test_news_symbol_lookup.py: 487 pure LOC`.

## Notes

- `backend/services/news_repository.py` remains above 250 pure LOC because this branch already contains unrelated repository duties. The symbol exact-first lookup, fallback pagination, count composition, and ranking behavior have been removed into `backend/services/news_symbol_query_service.py`.
- Pytest emitted a pre-existing cache warning because `.pytest_cache` is not writable in this workspace: `PytestCacheWarning: could not create cache path D:\KDH\Trading\.pytest_cache\... [WinError 5] 액세스가 거부되었습니다`.
