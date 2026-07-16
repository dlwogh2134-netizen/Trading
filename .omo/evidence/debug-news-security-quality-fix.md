# News Security Quality Fix Evidence

## Scope Notes

- Touched only the news route, news ingest error handling, news repository validation/delegation, focused news helper services, and a new targeted security test file.
- Preserved concurrent quality-gate edits already present in `news_repository.py` and `news_ingest.py`, including quality metadata defaults, visible quality filters, and symbol quality ordering.
- Retention deletion mechanics were moved out of oversized `news_repository.py` into `backend/services/news_retention_service.py`; repository API compatibility remains through `cleanup_expired_news_retention()`.
- Finnhub token redaction was moved into `backend/services/news_error_sanitizer.py` instead of growing oversized `news_ingest.py`.

## Red Evidence

- Scenario: unauthenticated `/api/news/sync`, Finnhub `HTTPError` with `token=secret-token`, and malformed PostgREST filter inputs.
- Invocation: `python -m pytest -p no:cacheprovider backend/tests/test_news_sync_security.py -q`
- Binary observable: exit code `1`, with `5 failed, 1 passed`.
- Captured artifact path: `.omo/evidence/debug-news-security-quality-fix-red.txt`

## Green Evidence

- Scenario: news sync security, retention cleanup, ingest quality gate, symbol lookup, and scheduler cleanup.
- Invocation: `python -m pytest -p no:cacheprovider backend/tests/test_news_sync_security.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_ingest_quality.py backend/tests/test_news_symbol_lookup.py backend/tests/test_news_cleanup_scheduler.py -q`
- Binary observable: exit code `0`, `22 passed in 10.41s`.
- Captured artifact path: `.omo/evidence/debug-news-security-quality-fix-pytest.txt`

## Compile Evidence

- Scenario: changed news modules and targeted tests compile.
- Invocation: `python -m py_compile backend/routes/news.py backend/services/news_ingest.py backend/services/news_repository.py backend/services/news_filter_validation.py backend/services/news_retention_service.py backend/services/news_error_sanitizer.py backend/tests/test_news_sync_security.py backend/tests/test_news_retention_cleanup.py backend/tests/test_news_ingest_quality.py backend/tests/test_news_symbol_lookup.py backend/tests/test_news_cleanup_scheduler.py`
- Binary observable: exit code `0`.
- Captured artifact path: `.omo/evidence/debug-news-security-quality-fix-pycompile.txt`

## Required Assertions Covered

- Unauthenticated sync denied: `test_news_sync_rejects_unauthenticated_cost_write_route` drives `POST /api/news/sync` without `X-Admin-Token`; response is `403`, and fake sync service is not called.
- Authenticated sync allowed: `test_news_sync_accepts_configured_admin_token` drives the same route with `X-Admin-Token: admin-secret`; response is `200`, and service is called.
- No secret leakage: `test_finnhub_http_error_token_is_not_returned_or_logged` drives `POST /api/news/sync` with a fake Finnhub `HTTPError` URL containing `token=secret-token`; response body and captured fetch log both exclude `secret-token` and `token=secret-token`.
- Malformed query handling: `test_news_query_rejects_postgrest_filter_injection_inputs` drives `/api/news` with invalid `market`, invalid `symbol`, and query filter metacharacters; each response is `400`, and repository access is not called.
- Retention containment: `backend/services/news_retention_service.py` now owns the physical DELETE request construction and count parsing; existing retention tests still pass through `NewsRepository.cleanup_expired_news_retention()`.
