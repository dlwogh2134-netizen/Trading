# News Auto-Retention Quality Gate: F2 Code Quality/Security Review Final

## Verdict

- F2: PASS
- codeQualityStatus: WATCH
- recommendation: APPROVE
- blockers: None

## Scope Reviewed

Changed news-related files only. Unrelated trade/crypto changes were ignored.

- `backend/routes/news.py`
- `backend/services/news_filter_validation.py`
- `backend/services/news_symbol_query_service.py`
- `backend/services/news_article_query_constants.py`
- `backend/services/news_error_sanitizer.py`
- `backend/services/news_quality_service.py`
- `backend/services/news_retention_service.py`
- `backend/services/news_ingest.py`
- `backend/services/news_repository.py`
- `backend/services/ml_scheduler.py` news scheduler/retention paths only
- `backend/services/chatbot/web_fallback_search_service.py` news quality upsert path only
- news-related tests under `backend/tests/test_news_*.py` and `backend/tests/test_chatbot_web_fallback_news_quality.py`
- `supabase/migrations/20260716151440_add_news_quality_metadata_retention_indexes.sql`
- `.omo/evidence/debug-news-resource-boundary-fix.md` and referenced verification artifacts

## Skill-Perspective Check

- Loaded `omo:remove-ai-slops` and applied its overfit/slop review pass.
- Loaded `omo:programming`, plus `references/python/README.md` and `references/code-smells.md`, before judging test relevance and maintainability.
- Result: no CRITICAL/HIGH violation from either perspective.
- Test shape is acceptable for this security/resource-boundary gate. The tests inspect PostgREST params where those params are the observable security/resource contract, not arbitrary implementation mirroring.
- No deletion-only tests, tautological removal tests, or tests that only mirror constants were found in the scoped resource-boundary additions.

## Findings By Severity

### CRITICAL

None.

### HIGH

None.

### MEDIUM

None.

### LOW

- `backend/services/news_symbol_query_service.py:22`, `backend/services/news_symbol_query_service.py:126`, `backend/services/news_symbol_query_service.py:196` - Accepted residual risk: when a symbol has more than `MAX_EXACT_ID_EXCLUSION_COUNT` exact rows, fallback count skips exact-ID exclusion and `totalCount` may overcount fallback rows that overlap exact rows. This is deterministic and bounded, and is acceptable because it avoids unbounded public reads.

## Resource-Amplification Blocker Recheck

Previous blocker is fixed.

- `backend/services/news_filter_validation.py:11` and `backend/services/news_filter_validation.py:71` cap public offset at `0..1000`.
- `backend/routes/news.py:20` parses and rejects invalid `/api/news` filters before repository access.
- `backend/services/news_symbol_query_service.py:76` fetches the exact symbol page with `limit=query.limit` and `offset=query.offset`, not `offset + limit`.
- `backend/services/news_symbol_query_service.py:185` only fetches exact IDs when the exact count is within the bounded cap.
- `backend/services/news_symbol_query_service.py:202` skips exact-ID exclusion above `1100`, avoiding unbounded ID reads.
- `backend/tests/test_news_symbol_lookup.py:468` covers the large allowed offset case.
- `backend/tests/test_news_symbol_lookup.py:513` covers large exact count without fetching all IDs.
- `backend/tests/test_news_sync_security.py:313` covers public huge offset rejection before repository access.

## Prior F2 Theme Recheck

- Protected write/cost routes: PASS. `/api/news/sync` and `/api/news/summaries/ensure` require an admin token before service/LLM work (`backend/routes/news.py:71`, `backend/routes/news.py:114`).
- Public `GET /api/news` remains read-only: PASS. Automatic summary generation was removed from the GET path (`backend/routes/news.py:40`).
- Raw secret/raw exception exposure: PASS. Finnhub token-bearing HTTP errors are sanitized before result/log storage (`backend/services/news_ingest.py:170`, `backend/services/news_error_sanitizer.py:13`), and route exceptions use `format_error_payload`.
- PostgREST filter/ID validation: PASS. Market/query/symbol/limit/offset/article IDs are normalized before query construction (`backend/services/news_filter_validation.py`).
- Retention deletion scope: PASS. Deletes are fixed to `news_articles` and `news_fetch_logs` only (`backend/services/news_retention_service.py:52`, `backend/services/news_retention_service.py:59`, `backend/services/news_retention_service.py:66`).
- Tavily not scheduled: PASS. Scheduled/manual news ingest calls Naver/Finnhub fetch paths only (`backend/services/news_ingest.py:27`, `backend/services/news_ingest.py:141`).
- Repository responsibility extraction: PASS. Symbol query and retention cleanup are split into focused services without introducing a blocking maintainability issue.

## Verification

Fresh rerun performed during this review:

```text
python -m pytest backend/tests/test_news_symbol_lookup.py backend/tests/test_news_sync_security.py backend/tests/test_news_ingest_quality.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_cleanup_scheduler.py backend/tests/test_chatbot_web_fallback_news_quality.py -q -p no:cacheprovider
36 passed in 8.71s
```

Fresh compile check performed outside the workspace:

```text
compiled 17 files into C:\Users\404_22\AppData\Local\Temp\news-review-pycompile-2na32iyv
```

Prior evidence inspected:

- `.omo/evidence/debug-news-resource-boundary-fix.md`
- `.omo/evidence/debug-news-resource-boundary-fix-targeted-pytest.txt` (`28 passed`, one pytest cache warning)
- `.omo/evidence/debug-news-resource-boundary-fix-impacted-pytest.txt` (`36 passed`, one pytest cache warning)
- `.omo/evidence/debug-news-resource-boundary-fix-pycompile.txt` (`py_compile exit 0`)

## Final Recommendation

APPROVE. The public `/api/news` resource-amplification blocker is resolved, no new correctness/security blocker was introduced by the bounded approximate count tradeoff, and the remaining approximate `totalCount` behavior above 1100 exact rows is acceptable for this gate.
