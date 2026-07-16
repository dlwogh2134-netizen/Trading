from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator

import pytest

from backend.services import ml_scheduler
from backend.services.news_repository import NewsRetentionCleanupCounts


class FakeRepository:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.cleanup_calls = 0
        self.should_fail = should_fail

    def cleanup_expired_news_retention(self) -> NewsRetentionCleanupCounts:
        self.cleanup_calls += 1
        if self.should_fail:
            raise RuntimeError("cleanup failed")
        return NewsRetentionCleanupCounts(normal_news=2, high_quality_news=1, logs=3)


class FakeNewsIngestService:
    def __init__(self, *, repository: FakeRepository) -> None:
        self.repository = repository
        self.run_calls = 0

    def run_once(self) -> dict[str, int]:
        self.run_calls += 1
        return {"fetched": 4, "inserted": 3, "queries_skipped": 1}


@contextmanager
def acquired_news_lock(lock_key: str, duration_seconds: int) -> Iterator[bool]:
    assert lock_key == "news_ingest"
    assert duration_seconds == 600
    yield True


def test_news_cleanup_scheduler_invokes_cleanup_once_per_korea_day(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Given: 뉴스 수집 락을 획득한 스케줄러와 같은 한국 날짜의 두 번의 실행입니다.
    service = FakeNewsIngestService(repository=FakeRepository())
    monkeypatch.setattr(ml_scheduler, "distributed_lock", acquired_news_lock)
    caplog.set_level(logging.INFO, logger=ml_scheduler.__name__)

    # When: 같은 한국 날짜에 스케줄러 단일 실행 헬퍼를 두 번 호출합니다.
    first_cleanup_date = ml_scheduler.run_news_ingest_scheduler_once(
        service,
        last_cleanup_date=None,
        now_utc=datetime(2026, 7, 16, 0, 30),
    )
    second_cleanup_date = ml_scheduler.run_news_ingest_scheduler_once(
        service,
        last_cleanup_date=first_cleanup_date,
        now_utc=datetime(2026, 7, 16, 12, 0),
    )

    # Then: 보관 정리는 하루 한 번만 실행되고 뉴스 수집은 매번 실행됩니다.
    assert first_cleanup_date == "2026-07-16"
    assert second_cleanup_date == "2026-07-16"
    assert service.repository.cleanup_calls == 1
    assert service.run_calls == 2
    assert "deleted_normal=2 deleted_high_quality=1 deleted_logs=3" in caplog.text


def test_news_cleanup_scheduler_logs_cleanup_failure_and_still_ingests(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Given: 보관 정리가 실패하지만 뉴스 수집 서비스는 정상 동작합니다.
    service = FakeNewsIngestService(repository=FakeRepository(should_fail=True))
    monkeypatch.setattr(ml_scheduler, "distributed_lock", acquired_news_lock)

    # When: 스케줄러 단일 실행 헬퍼를 호출합니다.
    cleanup_date = ml_scheduler.run_news_ingest_scheduler_once(
        service,
        last_cleanup_date=None,
        now_utc=datetime(2026, 7, 16, 1, 0),
    )

    # Then: 실패는 로그로 남고 당일 재시도를 막기 위해 날짜가 기록되며 수집은 계속 실행됩니다.
    assert cleanup_date == "2026-07-16"
    assert service.repository.cleanup_calls == 1
    assert service.run_calls == 1
    assert "[NewsRetentionCleanup] run failed date=2026-07-16" in caplog.text
