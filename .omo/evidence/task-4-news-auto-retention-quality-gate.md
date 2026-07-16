# Task 4 Evidence - News Symbol Lookup

## Scope Verified
- Changed `backend/services/news_repository.py` so `list_articles` and `count_articles` accept `symbol` separately from free-text `query`.
- Changed `backend/routes/news.py` so `/api/news?symbol=005930` passes `symbol="005930"` and uses display name only as fallback query text.
- Added `backend/tests/test_news_symbol_lookup.py` route/repository coverage.
- Preserved existing retention cleanup behavior in `backend/services/news_repository.py` and `backend/tests/test_news_retention_cleanup.py`.

## Scenarios
- Exact-first ordering:
  - Invocation: `python -m pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_retention_cleanup.py -q`
  - Test: `test_symbol_lookup_prioritizes_exact_symbol_rows_before_title_matches`
  - Binary observable: response item IDs equal `["exact-high-older", "exact-pass-newer", "title-only"]`.
  - Meaning: exact `symbol=eq.005930` rows are returned before title-only fallback rows, and exact rows are ranked `HIGH_QUALITY`, `relevance_score`, `published_at`.
- Empty exact fallback:
  - Invocation: `python -m pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_retention_cleanup.py -q`
  - Test: `test_symbol_lookup_falls_back_to_active_text_search_when_exact_rows_are_empty`
  - Binary observable: response item IDs equal `["fallback-active"]`; fallback request includes `is_active=eq.true` and `symbol.ilike.*005930*`.
- Free-text preservation:
  - Invocation: `python -m pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_retention_cleanup.py -q`
  - Test: `test_free_text_news_query_keeps_existing_text_search_behavior`
  - Binary observable: one Supabase request, no exact `symbol` filter, text `or` filter includes `title.ilike.*반도체*`.
- Count fallback:
  - Invocation: `python -m pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_retention_cleanup.py -q`
  - Test: `test_symbol_count_falls_back_to_text_count_when_exact_count_is_empty`
  - Binary observable: exact count request uses `symbol=eq.005930`; fallback count returns `7`.
- Route contract:
  - Invocation: `python -m pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_retention_cleanup.py -q`
  - Test: `test_news_route_passes_symbol_separately_from_display_name_query`
  - Binary observable: fake repository receives `{"market": "ALL", "query": "삼성전자", "symbol": "005930", "limit": 5, "offset": 0}`.

## Verification Artifacts
- Pytest artifact: `.omo/evidence/task-4-news-auto-retention-quality-gate-pytest.txt`
  - Result: `7 passed, 1 warning in 9.64s`.
  - Warning: pytest could not write `.pytest_cache` because access was denied; tests still exited 0.
- Compile artifact: `.omo/evidence/task-4-news-auto-retention-quality-gate-pycompile.txt`
  - Result: `py_compile exit_code=0` for `backend/services/news_repository.py`, `backend/routes/news.py`, `backend/tests/test_news_symbol_lookup.py`, and `backend/tests/test_news_retention_cleanup.py`.

## Adversarial Notes
- Stale state: existing evidence and reports were not trusted; final pytest and py_compile were rerun in this workspace after edits, with fresh artifacts above.
- Misleading success output: tests assert concrete request params and response ordering, not only that Flask returned 200 or pytest printed green.
- Dirty worktree: `git status` showed unrelated modified files outside this task plus prior uncommitted retention/quality work. This task only touched `backend/services/news_repository.py`, `backend/routes/news.py`, `backend/tests/test_news_symbol_lookup.py`, this evidence file, captured Task 4 logs, and the Todo 4 checkbox.
- Retention preservation: targeted pytest included `backend/tests/test_news_retention_cleanup.py`, confirming the prior retention cleanup fake DELETE filters and failure path still pass.
