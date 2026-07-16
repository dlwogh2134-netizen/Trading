# Debug Evidence - news final QA fix

## Verdict

PASS

## Root Causes Confirmed

1. H1 confirmed: `NewsRepository` symbol and fallback list/count reads did not filter `quality_status`, so legacy/concurrent rows with `quality_status=null` were user-visible. Live DB at `2026-07-16 07:25:51 UTC` had `null_quality_symbol_005930=19`; `/api/news?symbol=005930` previously returned null quality rows.
2. H2 confirmed: stale local `worker.py`/`app.py` processes were still running and inserted new null-quality rows after the earlier backfill. Runtime process check showed six stale processes; after stopping them, no stale worker/app process remained.
3. H3 confirmed: once-per-day cleanup can drift at the seven-day boundary. A row crossed expiry between checks (`expired_general_news=1` at `2026-07-16 07:44:50 UTC`), and an immediate filtered cleanup removed it.
4. Additional QA issue fixed: broad fallback count requests could return Supabase `57014` statement timeout. Counts now use a bounded fallback when exact count times out; list reads no longer request `Prefer: count=exact`.

## Code Changes

- `backend/services/news_repository.py`
  - User-visible reads now include `quality_status=in.(PASS,HIGH_QUALITY,LOW_CONFIDENCE)`.
  - `upsert_articles()` now fills missing quality metadata with `PASS`, score `45`, `excluded_reason=null`, and `quality_checked_at`.
  - List reads no longer send `Prefer: count=exact`.
  - Count reads fall back to a bounded list count on Supabase HTTP timeout.
- `backend/tests/test_news_symbol_lookup.py`
  - Added red-first regression coverage for null/rejected filtering, default metadata on upsert, no exact-count header on list reads, and bounded fallback count for exact/fallback timeouts.

## Red / Green Tests

### Red 1

Command:
`python -m pytest backend/tests/test_news_symbol_lookup.py -q -p no:cacheprovider`

Observed before fix:
`3 failed, 6 passed`

Failures:
- `KeyError: 'quality_status'` for symbol list filtering.
- `KeyError: 'quality_status'` for symbol count filtering.
- `KeyError: 'quality_status'` for repository upsert metadata.

### Red 2

Command:
`python -m pytest backend/tests/test_news_symbol_lookup.py::test_article_list_request_does_not_ask_supabase_for_exact_count -q -p no:cacheprovider`

Observed before fix:
`AssertionError: assert 'Prefer' not in ... 'Prefer': 'count=exact'`

### Red 3

Command:
`python -m pytest backend/tests/test_news_symbol_lookup.py::test_symbol_count_uses_bounded_fallback_when_text_count_times_out -q -p no:cacheprovider`

Observed before fix:
`requests.exceptions.HTTPError: 500 Server Error`

### Red 4

Command:
`python -m pytest backend/tests/test_news_symbol_lookup.py::test_symbol_count_uses_bounded_fallback_when_exact_count_times_out -q -p no:cacheprovider`

Observed before fix:
`requests.exceptions.HTTPError: 500 Server Error`

### Green

Command:
`python -m pytest backend/tests/test_news_symbol_lookup.py -q -p no:cacheprovider`

Observed after fix:
`12 passed`

## Automated QA

Command:
`python -m pytest backend/tests -k "news_retention or news_quality or news_symbol_lookup or news_cleanup_scheduler" -q -p no:cacheprovider`

Artifact:
`.omo/evidence/debug-news-final-pytest.txt`

Observed:
`19 passed, 376 deselected in 14.25s`

Command:
`python -m py_compile backend/services/news_repository.py backend/tests/test_news_symbol_lookup.py`

Observed:
exit code `0`.

## Live HTTP QA

Server:
`python -m flask --app backend.app run --host 127.0.0.1 --port 5057`

Server artifacts:
- `.omo/evidence/debug-news-final-flask.pid`
- `.omo/evidence/debug-news-final-flask.stdout.log`
- `.omo/evidence/debug-news-final-flask.stderr.log`

Scenario:
`curl.exe -s -i "http://127.0.0.1:5057/api/news?symbol=005930&limit=5"`

Artifact:
`.omo/evidence/debug-news-final-curl-news-005930.txt`

Parsed observable:
- `success=True`
- `items=5`
- `totalCount=2245`
- `quality_statuses=HIGH_QUALITY,HIGH_QUALITY,HIGH_QUALITY,HIGH_QUALITY,HIGH_QUALITY`
- `relevance_scores=80,80,80,80,80`
- `null_quality_items=0`

Scenario:
`curl.exe -s -i "http://127.0.0.1:5057/api/news?symbol=BTC&limit=5"`

Artifact:
`.omo/evidence/debug-news-final-curl-news-btc.txt`

Parsed observable:
- `success=True`
- `items=5`
- `totalCount=10`
- `quality_statuses=PASS,PASS,HIGH_QUALITY,PASS,PASS`
- `relevance_scores=45,45,80,45,45`
- `null_quality_items=0`

## Live Supabase Repair And Checks

Project:
`fdvhoaytcqnswuebocmr`

Initial observed drift:
- `2026-07-16 07:25:51 UTC`: `expired_general_news=74`, `null_quality_status_news=136`, `null_quality_symbol_005930=19`, DB `387 MB`.
- `2026-07-16 07:26:12 UTC`: `expired_fetch_logs=120`.

Filtered cleanup:
```sql
delete from public.news_articles
where quality_status = 'HIGH_QUALITY'
  and published_at < current_timestamp - interval '30 days';

delete from public.news_articles
where (quality_status is distinct from 'HIGH_QUALITY')
  and published_at < current_timestamp - interval '7 days';

delete from public.news_fetch_logs
where started_at < current_timestamp - interval '7 days';
```

Observed:
`deleted_high_quality_news=0`, `deleted_normal_news=75`, `deleted_fetch_logs=120`.

Stale process cleanup:
- Stopped stale local `worker.py` processes: `25316`, `4552`.
- Stopped stale local `app.py` processes: `23780`, `34748`, `30028`, `36000`, then later `31048`, `40520`, `36780`, `39580`.
- A later process audit showed `app.py` restarted again outside this turn; stopped `39576`, `33928`, `37960`, and `30912`.
- Final process check showed no remaining `python.exe` processes.

Backfill and cleanup after stale-process confirmation:
- `backfilled_null_quality_news=267`
- `deleted_high_quality_news=0`
- `deleted_normal_news=75`
- `deleted_fetch_logs=60`

Final boundary cleanup:
- `2026-07-16 07:45:12 UTC`: `deleted_high_quality_news=0`, `deleted_normal_news=2`, `deleted_fetch_logs=0`.

Final article invariant query at `2026-07-16 07:45:25 UTC`:
- `expired_general_news=0`
- `expired_high_quality_news=0`
- `null_quality_status_news=0`
- `null_quality_symbol_005930=0`
- `visible_quality_symbol_005930=2245`
- `high_quality_under_30d=9372`
- `database_size=387 MB`

Final fetch log invariant query at `2026-07-16 07:45:43 UTC`:
- `expired_fetch_logs=0`
- `recent_fetch_logs=15132`
- `database_size=387 MB`

DB size remains `387 MB`; no physical shrink is claimed because updates/indexes/deleted tuple space remain allocated until database maintenance reuses or compacts it.

## Artifacts

- `.omo/evidence/debug-news-final-qa-fix.md`
- `.omo/evidence/debug-news-final-pytest.txt`
- `.omo/evidence/debug-news-final-curl-news-005930.txt`
- `.omo/evidence/debug-news-final-curl-news-btc.txt`
- `.omo/evidence/debug-news-final-flask.stdout.log`
- `.omo/evidence/debug-news-final-flask.stderr.log`
