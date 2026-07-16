# Final QA - news-auto-retention-quality-gate

Role: F3 hands-on QA executor / F4 DB count spot-check. Product files were not edited.

## Verdict

FAIL

Confidence: high. Backend unit/route tests pass, but live Supabase invariants required by F4 currently fail, and live `/api/news?symbol=005930&limit=5` returns newly fetched rows with null quality metadata.

## Commands Run

- Read plan: `Get-Content -Raw .omo/plans/news-auto-retention-quality-gate.md`
- Read task evidence 1-6: `Get-Content -Raw .omo/evidence/task-{1..6}-news-auto-retention-quality-gate.md` via PowerShell parallel reads.
- Backend gate: `python -m pytest backend/tests -k "news_retention or news_quality or news_symbol_lookup or news_cleanup_scheduler" -q -p no:cacheprovider`
- Artifacted backend gate: `python -m pytest backend/tests -k "news_retention or news_quality or news_symbol_lookup or news_cleanup_scheduler" -q -p no:cacheprovider | Tee-Object -FilePath .omo/evidence/f3-pytest-news-gate.txt`
- Local server start: `python -m flask --app backend.app run --host 127.0.0.1 --port 5057` with scheduler flags disabled.
- Health probe: `curl.exe -i "http://127.0.0.1:5057/api/health"`
- KR API probe: `curl.exe -i "http://127.0.0.1:5057/api/news?symbol=005930&limit=5" | Tee-Object -FilePath .omo/evidence/f3-curl-news-005930.txt`
- Crypto-like API probe: `curl.exe -i "http://127.0.0.1:5057/api/news?symbol=BTC&limit=5" | Tee-Object -FilePath .omo/evidence/f3-curl-news-btc.txt`
- Supabase MCP read-only policy count/size query for expired general news, expired high-quality news, expired logs, high-quality under 30 days, null quality rows, and relation sizes.
- Supabase MCP read-only breakdown query for null-quality and expired general article rows.

## Scenario Coverage

| Scenario ID | Criterion Reference | Surface | Exact Invocation | Verdict | Artifact Refs |
| --- | --- | --- | --- | --- | --- |
| F3-T1 | Backend tests for retention/quality/symbol lookup/scheduler | CLI pytest | `python -m pytest backend/tests -k "news_retention or news_quality or news_symbol_lookup or news_cleanup_scheduler" -q -p no:cacheprovider` | PASS: `12 passed, 370 deselected` | A1 |
| F3-H1 | Local backend availability | HTTP | `curl.exe -i "http://127.0.0.1:5057/api/health"` | PASS: `HTTP/1.1 200 OK`, `{"status":"ok","success":true}` | A4, A5 |
| F3-H2 | KR symbol route `/api/news?symbol=005930&limit=5` | HTTP | `curl.exe -i "http://127.0.0.1:5057/api/news?symbol=005930&limit=5"` | FAIL: returned 200 and exact symbol rows, but all 5 returned rows had `quality_status:null` and `relevance_score:null`; this contradicts ingest-time quality metadata expectations for newly fetched rows. | A2 |
| F3-H3 | Non-KR / crypto-like route path | HTTP | `curl.exe -i "http://127.0.0.1:5057/api/news?symbol=BTC&limit=5"` | PASS with caveat: returned 200 and 5 items; quality metadata present (`PASS,PASS,HIGH_QUALITY,PASS,PASS`). Because no exact BTC symbol rows were found, fallback text search returned mixed symbols (`<empty>,<empty>,NVDA,<empty>,<empty>`), which matches fallback behavior but is broad. | A3 |
| F4-DB1 | Expired general news must be 0 | Supabase MCP SQL | read-only count query at `2026-07-16 07:12:32 UTC` | FAIL: `expired_general_news=58`. | A6 |
| F4-DB2 | Expired high-quality news must be 0 | Supabase MCP SQL | same as F4-DB1 | PASS: `expired_high_quality_news=0`. | A6 |
| F4-DB3 | Expired logs must be 0 | Supabase MCP SQL | same as F4-DB1 | FAIL: `expired_fetch_logs=120`. | A6 |
| F4-DB4 | High-quality under 30 days remains | Supabase MCP SQL | same as F4-DB1 | PASS: `high_quality_under_30d=9372`. | A6 |
| F4-DB5 | DB size/headroom recorded | Supabase MCP SQL | same as F4-DB1 | PASS: DB `406,031,507` bytes / `387 MB`, news_articles `146 MB`, news_fetch_logs `18 MB`; about 113 MiB headroom against 500 MiB. | A6 |

## Adversarial Cases

| Scenario ID | Criterion Reference | Adversarial Class | Expected Behavior | Verdict | Artifact Refs |
| --- | --- | --- | --- | --- | --- |
| ADV-1 | Ingest quality gate | Newly inserted articles after backfill/cleanup | New rows should include quality metadata before upsert. | FAIL: current DB has `null_quality_status_news=136`; these rows were published `2026-07-16 06:17:00+00` to `07:05:00+00` and fetched `2026-07-16 07:04:01+00` to `07:06:10+00`. The KR API response exposed null quality metadata for all 5 returned rows. | A2, A6 |
| ADV-2 | Retention cleanup invariant | Time boundary drift after cleanup | Expired general rows/logs should remain zero after cleanup, or scheduler should remove them automatically. | FAIL: `58` expired `PASS` news rows and `120` expired fetch logs existed at the fresh check. Expired logs had `started_at` from `2026-07-09 07:08:04+00` to `07:09:46+00`; expired PASS news had `published_at` from `2026-07-09 06:56:00+00` to `07:12:00+00`. | A6 |
| ADV-3 | HTTP side effects/secrets | GET route should be safe to exercise without secret exposure | QA should not expose secrets; ideally GET should not invoke external summarization/update work unexpectedly. | PARTIAL/FAIL-RISK: no secrets were printed in artifacts, but despite attempting to disable summary keys for the local server, `/api/news?symbol=005930` generated and saved an `ai_summary` for the first returned article (`ai_summary_generated_at=2026-07-16T07:12:00.554169Z`). This indicates the GET path can mutate summary state during manual QA. | A2 |
| ADV-4 | Fallback query breadth | Crypto-like query should not crash and should return active rows | HTTP route should return a structured 200 response or clean error. | PASS: BTC query returned 200 with 5 items and `totalCount=29`; metadata present. | A3 |

## Artifact Refs

| ID | Kind | Description | Path |
| --- | --- | --- | --- |
| A1 | pytest transcript | Backend retention/quality/symbol/scheduler selector output. | `.omo/evidence/f3-pytest-news-gate.txt` |
| A2 | HTTP transcript | Raw `curl -i` response for `/api/news?symbol=005930&limit=5`. | `.omo/evidence/f3-curl-news-005930.txt` |
| A3 | HTTP transcript | Raw `curl -i` response for `/api/news?symbol=BTC&limit=5`. | `.omo/evidence/f3-curl-news-btc.txt` |
| A4 | server log | Flask server stderr log showing dev server start and health request. | `.omo/evidence/f3-flask-server.stderr.log` |
| A5 | server log | Flask server stdout log. | `.omo/evidence/f3-flask-server.stdout.log` |
| A6 | final QA note | This file; includes fresh Supabase MCP count/size results and breakdown. | `.omo/evidence/final-qa-news-auto-retention-quality-gate.md` |

## Blocking Issues

1. F4 cannot be marked complete: fresh Supabase read-only checks showed `expired_general_news=58` and `expired_fetch_logs=120`, not zero.
2. F3 should not be marked complete as passing: the KR route call succeeded but returned rows missing quality metadata, and the live GET path triggered summary mutation despite the QA attempt to disable summaries.
3. The likely operational gap is that new scheduled/live ingest after the one-off backfill is still producing `quality_status:null` rows, or a running worker is using code without the quality gate. That is an inference from timestamps and should be verified by the implementation lane.

## F3/F4 Checkbox Recommendation

- F3: do not mark complete as PASS. Mark complete only if the lane accepts a FAIL result as completed review work; the product criterion itself failed.
- F4: do not mark complete as PASS. Required zero-count cleanup invariants are currently false.
