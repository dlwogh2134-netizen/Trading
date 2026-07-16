# Task 2 Evidence - News Retention Cleanup Repository Behavior

## Scope
- Todo: `2. Implement retention cleanup repository/service behavior`
- Changed code: `backend/services/news_repository.py`
- Added tests: `backend/tests/test_news_retention_cleanup.py`
- Production database mutation: not performed.
- Public route: not created.

## Implementation Observable
- Scenario: service-role retention cleanup physically deletes expired `news_articles` and `news_fetch_logs`.
- Invocation: `python -m pytest backend/tests/test_news_retention_cleanup.py -k news_retention -q`
- Binary observable: `2 passed, 1 warning in 2.95s`
- Captured artifact: this file, `.omo/evidence/task-2-news-auto-retention-quality-gate.md`

## Acceptance Verification
- Scenario: requested targeted selector across backend tests.
- Initial invocation: `python -m pytest backend/tests -k news_retention -q`
- Initial result: failed during unrelated collection before retention tests because `backend.app` imports `flask_cors` and the package was missing from the active Python environment.
- Dependency check: `rg -n "flask-cors|Flask-Cors|flask_cors|pytest|requests" backend/requirements.txt`
- Result summary: `backend/requirements.txt` already declares `Flask-Cors>=4.0.0`.
- Environment repair invocation: `python -m pip install "Flask-Cors>=4.0.0"`
- Result summary: installed `Flask-Cors-6.0.5`.
- Final invocation: `python -m pytest backend/tests -k news_retention -q`
- Binary observable: `2 passed, 373 deselected, 1 warning in 19.85s`
- Warning note: pytest could not write `.pytest_cache` because that directory is permission-denied in this workspace; the tests still passed.

## Static Verification
- Scenario: changed Python files compile.
- Invocation: `python -m py_compile backend/services/news_repository.py backend/tests/test_news_retention_cleanup.py`
- Binary observable: exit code 0.
- Scenario: retention implementation does not use soft-delete `is_active=false` and does not touch DART/disclosure cleanup.
- Invocation: `rg -n "dart_|DART|disclosure|is_active\\s*=\\s*false|is_active=false|is_active.*eq.false" backend/services/news_repository.py backend/tests/test_news_retention_cleanup.py`
- Binary observable: no matches, exit code 1 from `rg`.
- Scenario: pure LOC measurement after edit.
- Invocation: PowerShell count excluding blank/comment lines for `backend/services/news_repository.py` and `backend/tests/test_news_retention_cleanup.py`
- Result summary: `backend/services/news_repository.py 312`, `backend/tests/test_news_retention_cleanup.py 112`. `news_repository.py` was already a large repository module; no scope-broadening split was performed for this Todo.

## DELETE Surface Covered By Tests
- High-quality news: `DELETE https://project.supabase.co/rest/v1/news_articles` with headers using `apikey: service-key`, `Authorization: Bearer service-key`, `Prefer: count=exact,return=minimal`, and filters `quality_status=eq.HIGH_QUALITY`, `published_at=lt.2026-06-16T12:00:00+00:00`.
- Normal news: `DELETE https://project.supabase.co/rest/v1/news_articles` with service-role headers and filters `or=(quality_status.neq.HIGH_QUALITY,quality_status.is.null)`, `published_at=lt.2026-07-09T12:00:00+00:00`.
- Fetch logs: `DELETE https://project.supabase.co/rest/v1/news_fetch_logs` with service-role headers and filter `started_at=lt.2026-07-09T12:00:00+00:00`.
- Count parsing: tests cover `Content-Range: */3`, `Content-Range: 0-1/2`, and `Content-Range: */4`, returning counts for high-quality news, normal news, and logs.
- Failure path: fake 500 response raises `NewsRetentionDeleteError` with `table="news_articles"`, `status_code=500`, and the response body preserved; cleanup stops after the first failed DELETE and does not return success counts.

## Supabase Documentation Checked
- Official Supabase REST API docs confirm Supabase exposes PostgREST at `/rest/v1/` and supports CRUD, including Delete.
- Official Supabase API security docs confirm service-role server-side access is a separate Data API role and should be granted only server-side.
- PostgREST docs confirm DELETE uses horizontal filtering and warn against unfiltered deletes.
- PostgREST docs confirm `Prefer: count=exact` returns exact count metadata through `Content-Range`.

## Adversarial Notes
- Destructive SQL/HTTP delete: implementation uses only filtered REST `DELETE` calls; there is no unfiltered table delete, no `TRUNCATE`, no `DROP`, and no DART table reference.
- Stale state: no live Supabase delete was executed. Tests use a fake `requests.delete` boundary and assert the exact URL, headers, filters, timeout, and count parsing.
- Misleading success output: a fake 500 response is covered and raises a structured exception instead of returning zero or partial success counts.
- Dirty worktree: unrelated pre-existing changes were present, including `backend/services/news_ingest.py` and other backend files. This Todo changed only `backend/services/news_repository.py`, added `backend/tests/test_news_retention_cleanup.py`, added this evidence file, and updates the Todo 2 checkbox in the plan.

## Acceptance Result
- Passed for this executor scope: repository/service retention cleanup behavior and tests are implemented, verified, and evidence-recorded.
