# Task 3 Evidence - News Ingest Quality Gate

## Changed Files
- `backend/services/news_quality_service.py`
- `backend/services/news_ingest.py`
- `backend/tests/test_news_ingest_quality.py`
- `.omo/plans/news-auto-retention-quality-gate.md`

## Fresh Verification
| Scenario | Invocation | Binary observable | Captured artifact |
| --- | --- | --- | --- |
| Direct Todo 3 quality tests | `PYTHONPATH=. pytest backend/tests/test_news_ingest_quality.py -q` | exit `0`; `3 passed, 1 warning in 19.91s` | `.omo/evidence/task-3-news-auto-retention-quality-gate.md` |
| Plan target quality selector | `PYTHONPATH=. pytest backend/tests -k news_quality -q` | exit `0`; final fresh run `3 passed, 372 deselected, 1 warning in 10.82s` | `.omo/evidence/task-3-news-auto-retention-quality-gate.md` |
| Python syntax compile | `python -m py_compile backend/services/news_quality_service.py backend/services/news_ingest.py backend/tests/test_news_ingest_quality.py` | exit `0`; no compiler output | `.omo/evidence/task-3-news-auto-retention-quality-gate.md` |
| Scope guard | `rg "TAVILY|Tavily|tavily|NEWS_NAVER_DAILY_QUERY_BUDGET|NEWS_MAX_QUERIES_PER_RUN|NEWS_MAX_ITEMS_PER_QUERY|NEWS_INGEST_INTERVAL_SECONDS" backend/services/news_ingest.py backend/services/news_quality_service.py backend/tests/test_news_ingest_quality.py` | exit `0`; only existing `NEWS_MAX_ITEMS_PER_QUERY` line in `news_ingest.py`; no Tavily or cadence/budget edits | `.omo/evidence/task-3-news-auto-retention-quality-gate.md` |
| Diff whitespace check | `git diff --check -- backend/services/news_ingest.py backend/services/news_quality_service.py backend/tests/test_news_ingest_quality.py` | exit `0`; only CRLF warning for existing `backend/services/news_ingest.py` working-copy conversion | `.omo/evidence/task-3-news-auto-retention-quality-gate.md` |

`pytest` emitted a cache warning because `.pytest_cache` cannot be written under this workspace, but tests completed with exit `0`.

## Local Audit
| Check | Observable |
| --- | --- |
| No-excuse script | `scripts/python/check-no-excuse-rules.py` is absent in this repo, so that checker could not be run. |
| Pure LOC | `backend/services/news_quality_service.py`: 186, `backend/services/news_ingest.py`: 376, `backend/tests/test_news_ingest_quality.py`: 163. `news_ingest.py` was already oversized; this task kept the new scoring logic in a focused helper and only added wiring there. |

## Accepted / Rejected Matrix
| Sample | Expected decision | Observed in tests |
| --- | --- | --- |
| 삼성전자 article with `005930`, 반도체/실적/매출/전망 keywords | accepted with quality metadata | reaches fake `upsert_articles`; `quality_status` is `PASS` or `HIGH_QUALITY`; `excluded_reason is None` |
| Nvidia/NVDA article with earnings/revenue/guidance/stock keywords | accepted | reaches fake `upsert_articles`; exact recent strong sample is `HIGH_QUALITY` with score `>= 80` |
| Bitcoin/BTC article with ETF/market/crypto/price keywords | accepted | reaches fake `upsert_articles`; quality metadata included |
| Wikipedia URL | rejected | not passed to fake `upsert_articles`; counted in `rejected` and `query_results[0].rejected_count` |
| Namu URL | rejected | not passed to fake `upsert_articles`; counted as rejected |
| Naver Kin URL | rejected | not passed to fake `upsert_articles`; counted as rejected |
| Dictionary URL | rejected | not passed to fake `upsert_articles`; counted as rejected |
| Community/off-topic URL | rejected | not passed to fake `upsert_articles`; counted as rejected |
| Samsung query returning unrelated real-estate article | rejected | first test observes one off-topic article rejected; `result["rejected"] == 1` |

## Adversarial Notes
- Untrusted external text: title, summary, and URL from Naver/Finnhub are treated as untrusted scoring inputs only. The implementation uses deterministic keyword/domain matching and does not call an LLM.
- Stale state: pre-existing reports/logs were not trusted. Tests were created and run fresh in this session after the code change.
- Misleading success output: the first `pytest backend/tests -k news_quality -q` run selected zero tests despite exit `1`; test names were changed to include `news_quality`, then the exact command was rerun and selected/passed 3 tests.
- Dirty worktree: unrelated pre-existing modifications remain in trade/crypto files and untracked Task 1 migration/evidence. This task did not revert or edit those files.
- Environment issue: the first broad selector run initially failed during unrelated collection due `flask_cors` import failure; the declared `backend/requirements.txt` dependency imports successfully after checking/installing, and the exact target then passed.
