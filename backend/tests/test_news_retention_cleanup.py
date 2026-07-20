from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
import requests

from backend.services.news_repository import NewsRepository, NewsRetentionDeleteError
from backend.services.news_retention_service import DisclosureRetentionDeleteError


@dataclass(frozen=True, slots=True)
class DeleteCall:
    url: str
    headers: dict[str, str]
    params: dict[str, str]
    timeout: int


@dataclass(frozen=True, slots=True)
class FakeDeleteResponse:
    status_code: int
    content_range: str
    text: str = ""

    @property
    def headers(self) -> dict[str, str]:
        return {"Content-Range": self.content_range}


@dataclass(frozen=True, slots=True)
class FakeRpcResponse:
    status_code: int
    payload: list[dict[str, int | bool]]
    text: str = ""

    def json(self) -> list[dict[str, int | bool]]:
        return self.payload


def test_cleanup_expired_news_retention_deletes_expected_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: Supabase service-role configuration and three successful DELETE responses.
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    calls: list[DeleteCall] = []
    responses = [
        FakeDeleteResponse(status_code=204, content_range="*/3"),
        FakeDeleteResponse(status_code=200, content_range="0-1/2"),
        FakeDeleteResponse(status_code=204, content_range="*/4"),
    ]

    def fake_delete(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeDeleteResponse:
        calls.append(DeleteCall(url=url, headers=headers, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "delete", fake_delete)
    repository = NewsRepository()

    # When: retention cleanup runs at a fixed UTC instant.
    result = repository.cleanup_expired_news_retention(
        now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
    )

    # Then: physical DELETE calls use the exact retention filters and parsed counts.
    assert result.high_quality_news == 3
    assert result.normal_news == 2
    assert result.logs == 4
    assert calls == [
        DeleteCall(
            url="https://project.supabase.co/rest/v1/news_articles",
            headers={
                "apikey": "service-key",
                "Authorization": "Bearer service-key",
                "Content-Type": "application/json",
                "Prefer": "count=exact,return=minimal",
            },
            params={
                "quality_status": "eq.HIGH_QUALITY",
                "published_at": "lt.2026-06-16T12:00:00+00:00",
            },
            timeout=30,
        ),
        DeleteCall(
            url="https://project.supabase.co/rest/v1/news_articles",
            headers={
                "apikey": "service-key",
                "Authorization": "Bearer service-key",
                "Content-Type": "application/json",
                "Prefer": "count=exact,return=minimal",
            },
            params={
                "or": "(quality_status.neq.HIGH_QUALITY,quality_status.is.null)",
                "published_at": "lt.2026-07-09T12:00:00+00:00",
            },
            timeout=30,
        ),
        DeleteCall(
            url="https://project.supabase.co/rest/v1/news_fetch_logs",
            headers={
                "apikey": "service-key",
                "Authorization": "Bearer service-key",
                "Content-Type": "application/json",
                "Prefer": "count=exact,return=minimal",
            },
            params={"started_at": "lt.2026-07-09T12:00:00+00:00"},
            timeout=30,
        ),
    ]


def test_cleanup_expired_news_retention_raises_structured_error_on_delete_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: Supabase returns a server error for the first destructive DELETE.
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    calls: list[DeleteCall] = []

    def fake_delete(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeDeleteResponse:
        calls.append(DeleteCall(url=url, headers=headers, params=params, timeout=timeout))
        return FakeDeleteResponse(status_code=500, content_range="*/0", text='{"message":"boom"}')

    monkeypatch.setattr(requests, "delete", fake_delete)
    repository = NewsRepository()

    # When / Then: the cleanup fails loudly with structured fields instead of returning success counts.
    with pytest.raises(NewsRetentionDeleteError) as exc_info:
        repository.cleanup_expired_news_retention(
            now=datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc),
        )

    error = exc_info.value
    assert getattr(error, "table") == "news_articles"
    assert getattr(error, "status_code") == 500
    assert getattr(error, "response_text") == '{"message":"boom"}'
    assert len(calls) == 1


def test_cleanup_expired_disclosure_retention_deletes_atomic_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    calls: list[dict[str, object]] = []
    responses = [
        FakeRpcResponse(
            status_code=200,
            payload=[
                {
                    "deleted_disclosures": 5000,
                    "deleted_analyses": 90,
                    "deleted_chunks": 100,
                    "has_more": True,
                }
            ],
        ),
        FakeRpcResponse(
            status_code=200,
            payload=[
                {
                    "deleted_disclosures": 12,
                    "deleted_analyses": 3,
                    "deleted_chunks": 6,
                    "has_more": False,
                }
            ],
        ),
    ]

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: int,
    ) -> FakeRpcResponse:
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return responses.pop(0)

    monkeypatch.setattr(requests, "post", fake_post)
    repository = NewsRepository()

    result = repository.cleanup_expired_disclosure_retention(
        now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
    )

    assert result.disclosures == 5012
    assert result.analyses == 93
    assert result.chunks == 106
    assert result.batches == 2
    assert len(calls) == 2
    assert calls[0]["url"] == "https://project.supabase.co/rest/v1/rpc/cleanup_expired_disclosures"
    assert calls[0]["json"] == {"p_cutoff_date": "2026-06-20", "p_batch_size": 5000}
    assert calls[0]["timeout"] == 60


def test_cleanup_expired_disclosure_retention_raises_structured_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: int,
    ) -> FakeRpcResponse:
        return FakeRpcResponse(status_code=500, payload=[], text='{"message":"boom"}')

    monkeypatch.setattr(requests, "post", fake_post)
    repository = NewsRepository()

    with pytest.raises(DisclosureRetentionDeleteError) as exc_info:
        repository.cleanup_expired_disclosure_retention(
            now=datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        )

    error = exc_info.value
    assert error.table == "rpc/cleanup_expired_disclosures"
    assert error.status_code == 500
    assert error.response_text == '{"message":"boom"}'
