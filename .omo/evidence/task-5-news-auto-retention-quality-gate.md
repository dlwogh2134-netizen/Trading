# Task 5 Evidence - News Retention Cleanup Scheduler Wiring

## Implementation

- Wired automatic retention cleanup into `backend/services/ml_scheduler.py` through `run_news_ingest_scheduler_once()`.
- Cleanup runs under the existing `news_ingest` distributed lock before `news_ingest_service.run_once()`.
- Cleanup calls `news_ingest_service.repository.cleanup_expired_news_retention()` and logs deleted normal news, high-quality news, and fetch-log counts.
- The scheduler stores the last attempted Korea date in the news scheduler loop so cleanup is attempted at most once per Korea date for the running worker process.
- `backend/app.py`, `backend/worker.py`, HTTP routes, and `backend/services/news_ingest.py` quality logic were not changed.

## Verification

### Red Test Proof

- Scenario: scheduler cleanup helper is required and absent before implementation.
- Invocation: `python -m pytest backend/tests/test_news_cleanup_scheduler.py -q`
- Binary observable: exit code `1`.
- Captured output: both tests failed with `AttributeError: module 'backend.services.ml_scheduler' has no attribute 'run_news_ingest_scheduler_once'`.

### Happy Path

- Scenario: two scheduler iterations on the same Korea date under an acquired `news_ingest` lock.
- Invocation: `python -m pytest backend/tests -k "news_cleanup_scheduler or news_retention" -q -p no:cacheprovider`
- Binary observable: exit code `0`.
- Captured output: `4 passed, 378 deselected in 15.49s`.
- Assertions:
  - cleanup invoked once for `2026-07-16`;
  - `run_once()` invoked twice;
  - log contains `deleted_normal=2 deleted_high_quality=1 deleted_logs=3`;
  - existing Todo 2 repository cleanup tests still pass.

### Failure Path

- Scenario: `cleanup_expired_news_retention()` raises before ingestion.
- Invocation: `python -m pytest backend/tests -k "news_cleanup_scheduler or news_retention" -q -p no:cacheprovider`
- Binary observable: exit code `0`.
- Captured output: `4 passed, 378 deselected in 15.49s`.
- Assertions:
  - log contains `[NewsRetentionCleanup] run failed date=2026-07-16`;
  - cleanup date is still recorded as `2026-07-16`;
  - `run_once()` still executes once.

### Compile Gate

- Scenario: changed scheduler and scheduler test compile.
- Invocation: `python -m py_compile backend/services/ml_scheduler.py backend/tests/test_news_cleanup_scheduler.py`
- Binary observable: exit code `0`.
- Captured output: no stderr/stdout.

## Adversarial Notes

- Destructive delete path: scheduler only reaches the existing Todo 2 repository method; it does not add new SQL, a new HTTP endpoint, route-triggered cleanup, or a second delete implementation.
- Long-running loops: tests call `run_news_ingest_scheduler_once()` directly, so no background thread, `while True`, or `time.sleep()` is exercised in tests.
- Stale state: once-per-day state is in the running scheduler process. A worker restart can attempt cleanup again, but the repository cleanup is physically destructive and date-filtered, so a second same-day run should delete zero additional rows beyond rows that still match the same retention filters.
- Misleading success output: cleanup failure is logged with `logger.exception()` and does not log deleted counts.
- Dirty worktree: pre-existing unrelated changes remain in `backend/routes/trade.py`, crypto/chatbot services/tests, news ingestion/repository files, `.omo` drafts/evidence, and the migration from earlier todos; this task only changed `backend/services/ml_scheduler.py`, added `backend/tests/test_news_cleanup_scheduler.py`, created this evidence file, and updates the Todo 5 checkbox.

## Evidence Artifact

- Path: `.omo/evidence/task-5-news-auto-retention-quality-gate.md`
