from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import requests
from flask import Flask

from backend.routes import news as news_route
from backend.routes.news import news_bp
from backend.services.news_repository import NewsRepository


@dataclass(frozen=True, slots=True)
class GetCall:
    url: str
    params: dict[str, str]
    timeout: int


@dataclass(frozen=True, slots=True)
class PostCall:
    url: str
    json: list[dict[str, Any]]
    timeout: int


@dataclass(frozen=True, slots=True)
class FakeGetResponse:
    payload: list[dict[str, Any]]
    content_range: str = "0-0/0"

    @property
    def headers(self) -> dict[str, str]:
        return {"Content-Range": self.content_range}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, Any]]:
        return self.payload


@dataclass(frozen=True, slots=True)
class FakePostResponse:
    def raise_for_status(self) -> None:
        return None


def _published_days_ago(days: int, hours: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days, hours=hours)).isoformat()


class DisabledSummaryService:
    enabled = False


class CapturingNewsRepository:
    def __init__(self) -> None:
        self.list_kwargs: dict[str, Any] = {}
        self.count_kwargs: dict[str, Any] = {}

    def list_articles(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.list_kwargs = kwargs
        return [
            {
                "id": "exact-high",
                "title": "exact",
                "ai_summary": "cached",
                "ai_summary_model": "fake",
            }
        ]

    def count_articles(self, **kwargs: Any) -> int:
        self.count_kwargs = kwargs
        return 1


@pytest.fixture
def configured_repository(monkeypatch: pytest.MonkeyPatch) -> NewsRepository:
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    return NewsRepository()


def test_symbol_lookup_prioritizes_exact_symbol_rows_before_title_matches(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: exact symbol rows and a title-only fallback row are returned by Supabase.
    calls: list[GetCall] = []
    responses = [
        FakeGetResponse(
            payload=[
                {
                    "id": "exact-pass-newer",
                        "symbol": "005930",
                        "quality_status": "PASS",
                        "relevance_score": 65,
                        "published_at": _published_days_ago(0, 1),
                },
                {
                    "id": "exact-high-older",
                        "symbol": "005930",
                        "quality_status": "HIGH_QUALITY",
                        "relevance_score": 90,
                        "published_at": _published_days_ago(1),
                },
            ]
        ),
        FakeGetResponse(
            payload=[
                {
                    "id": "title-only",
                    "symbol": "",
                    "title": "삼성전자 005930 주가 전망",
                    "summary": "005930 코스피 매출과 영업이익 개선 전망 기사입니다.",
                    "url": "https://finance.example.com/samsung-005930-earnings",
                    "quality_status": "HIGH_QUALITY",
                    "relevance_score": 99,
                    "published_at": _published_days_ago(0),
                }
            ]
        ),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: a symbol-specific news lookup needs fallback rows to fill the requested limit.
    result = configured_repository.list_articles(
        market="DOMESTIC",
        query="삼성전자",
        symbol="005930",
        limit=3,
    )

    # Then: combined exact and fallback rows are shown by newest published date.
    assert [item["id"] for item in result] == ["title-only", "exact-pass-newer", "exact-high-older"]
    assert calls[0].params["symbol"] == "eq.005930"
    assert calls[0].params["order"] == (
        "published_at.desc,relevance_score.desc.nullslast,quality_status.asc.nullslast"
    )
    assert calls[1].params["is_active"] == "eq.true"
    assert "title.ilike.*삼성전자*" in calls[1].params["or"]


def test_symbol_lookup_fetches_exact_rows_by_recency_before_quality_limit(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: an older HIGH_QUALITY row competes with a newer PASS row.
    calls: list[GetCall] = []
    exact_rows = [
        {
            "id": "newer-pass",
            "symbol": "005930",
            "quality_status": "PASS",
            "relevance_score": 70,
            "published_at": _published_days_ago(0),
        },
        {
            "id": "older-high",
            "symbol": "005930",
            "quality_status": "HIGH_QUALITY",
            "relevance_score": 95,
            "published_at": _published_days_ago(2),
        },
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        ordered_rows = exact_rows
        return FakeGetResponse(payload=ordered_rows[: int(params["limit"])])

    monkeypatch.setattr(requests, "get", fake_get)

    # When: only one exact symbol article is requested.
    result = configured_repository.list_articles(symbol="005930", limit=1)

    # Then: the newer article wins before quality status.
    assert [item["id"] for item in result] == ["newer-pass"]
    assert calls[0].params["order"] == (
        "published_at.desc,relevance_score.desc.nullslast,quality_status.asc.nullslast"
    )


def test_symbol_lookup_falls_back_to_active_text_search_when_exact_rows_are_empty(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: Supabase has no exact symbol rows but has an active text-search match.
    calls: list[GetCall] = []
    responses = [
        FakeGetResponse(payload=[]),
        FakeGetResponse(
            payload=[
                {
                    "id": "fallback-active",
                    "title": "005930 공급 계약",
                    "quality_status": "PASS",
                    "published_at": _published_days_ago(0),
                }
            ]
        ),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: a symbol lookup cannot find exact symbol rows.
    result = configured_repository.list_articles(symbol="005930", limit=2)

    # Then: the fallback text query is active-row filtered and uses the symbol text.
    assert [item["id"] for item in result] == ["fallback-active"]
    assert calls[1].params["is_active"] == "eq.true"
    assert "symbol.ilike.*005930*" in calls[1].params["or"]


def test_symbol_lookup_excludes_null_and_rejected_quality_rows(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: Supabase can contain legacy rows whose quality metadata is null or rejected.
    calls: list[GetCall] = []

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return FakeGetResponse(payload=[])

    monkeypatch.setattr(requests, "get", fake_get)

    # When: a symbol lookup runs exact and fallback queries.
    result = configured_repository.list_articles(
        query="삼성전자",
        symbol="005930",
        limit=2,
    )

    # Then: both user-visible reads only request classified, non-rejected rows.
    assert result == []
    assert calls[0].params["quality_status"] == "in.(PASS,HIGH_QUALITY,LOW_CONFIDENCE)"
    assert calls[1].params["quality_status"] == "in.(PASS,HIGH_QUALITY,LOW_CONFIDENCE)"


def test_symbol_lookup_hides_articles_outside_visible_retention_window(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: Supabase still has expired normal and high-quality symbol news rows.
    responses = [
        FakeGetResponse(
            payload=[
                {
                    "id": "fresh-pass",
                    "symbol": "005930",
                    "quality_status": "PASS",
                    "relevance_score": 70,
                    "published_at": _published_days_ago(1),
                },
                {
                    "id": "expired-pass",
                    "symbol": "005930",
                    "quality_status": "PASS",
                    "relevance_score": 100,
                    "published_at": _published_days_ago(9),
                },
                {
                    "id": "expired-high",
                    "symbol": "005930",
                    "quality_status": "HIGH_QUALITY",
                    "relevance_score": 100,
                    "published_at": _published_days_ago(40),
                },
            ]
        ),
        FakeGetResponse(payload=[]),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: the symbol news list is loaded for the detail page.
    result = configured_repository.list_articles(symbol="005930", limit=3)

    # Then: only rows within the user-visible retention window are returned.
    assert [item["id"] for item in result] == ["fresh-pass"]


def test_symbol_lookup_hides_ambiguous_company_name_without_listed_context(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: 같은 종목명 텍스트를 가진 상장사 뉴스와 생활 뉴스가 함께 저장되어 있습니다.
    responses = [
        FakeGetResponse(
            payload=[
                {
                    "id": "off-topic-inbody",
                    "symbol": "041830",
                    "company_name": "인바디",
                    "title": "신지, 인바디 측정불가 결과 공개",
                    "summary": "방송인이 체성분 검사 결과와 일상 근황을 전했습니다.",
                    "url": "https://www.example.com/entertainment/inbody-check",
                    "quality_status": "PASS",
                    "relevance_score": 80,
                    "published_at": _published_days_ago(0),
                },
                {
                    "id": "listed-inbody",
                    "symbol": "041830",
                    "company_name": "인바디",
                    "title": "인바디, 코스닥 상장사 실적 개선 전망",
                    "summary": "인바디 매출과 영업이익이 헬스케어 장비 공급 계약 확대로 증가했습니다.",
                    "url": "https://www.example.com/markets/inbody-earnings",
                    "quality_status": "PASS",
                    "relevance_score": 70,
                    "published_at": _published_days_ago(0, 1),
                },
            ]
        ),
        FakeGetResponse(payload=[]),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: 종목 상세 뉴스탭이 인바디 뉴스를 조회합니다.
    result = configured_repository.list_articles(query="인바디", symbol="041830", limit=2)

    # Then: 일반 체성분 검사 문맥은 숨기고 상장사 맥락의 기사만 반환합니다.
    assert [item["id"] for item in result] == ["listed-inbody"]


def test_free_text_news_query_keeps_existing_text_search_behavior(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: a normal free-text news query.
    calls: list[GetCall] = []

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return FakeGetResponse(payload=[{"id": "text-match"}])

    monkeypatch.setattr(requests, "get", fake_get)

    # When: the repository is called without a symbol.
    result = configured_repository.list_articles(query="반도체", limit=1)

    # Then: only the existing text-search request shape is used.
    assert [item["id"] for item in result] == ["text-match"]
    assert len(calls) == 1
    assert "symbol" not in calls[0].params
    assert "title.ilike.*반도체*" in calls[0].params["or"]


def test_article_list_request_does_not_ask_supabase_for_exact_count(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: a normal list request that has a separate count request at the route layer.
    captured_headers: list[dict[str, str]] = []

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        captured_headers.append(headers)
        return FakeGetResponse(payload=[{"id": "text-match"}])

    monkeypatch.setattr(requests, "get", fake_get)

    # When: the repository lists articles.
    result = configured_repository.list_articles(query="BTC", limit=5)

    # Then: the list request avoids the expensive exact count header.
    assert [item["id"] for item in result] == ["text-match"]
    assert "Prefer" not in captured_headers[0]


def test_symbol_count_falls_back_to_text_count_when_exact_count_is_empty(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: exact symbol count is empty and fallback text count has active matches.
    calls: list[GetCall] = []
    responses = [
        FakeGetResponse(payload=[], content_range="0-0/0"),
        FakeGetResponse(payload=[], content_range="0-6/7"),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: count is requested for a symbol whose exact rows are missing.
    count = configured_repository.count_articles(query="삼성전자", symbol="005930")

    # Then: count falls back to the same active text-search surface used by listing.
    assert count == 7
    assert calls[0].params["symbol"] == "eq.005930"
    assert calls[1].params["is_active"] == "eq.true"
    assert "company_name.ilike.*삼성전자*" in calls[1].params["or"]


def test_symbol_count_combines_exact_and_fallback_unique_rows(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: exact symbol rows are sparse and fallback text rows add more unique matches.
    calls: list[GetCall] = []
    responses = [
        FakeGetResponse(payload=[], content_range="0-1/2"),
        FakeGetResponse(payload=[{"id": "exact-1"}, {"id": "exact-2"}]),
        FakeGetResponse(payload=[], content_range="0-2/3"),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: count is requested for a symbol lookup with exact and fallback matches.
    count = configured_repository.count_articles(query="삼성전자", symbol="005930")

    # Then: pagination metadata reflects the combined exact-first virtual result set.
    assert count == 5
    assert calls[0].params["symbol"] == "eq.005930"
    assert calls[1].params["select"] == "id"
    assert calls[1].params["symbol"] == "eq.005930"
    assert calls[2].params["id"] == "not.in.(exact-1,exact-2)"
    assert "title.ilike.*삼성전자*" in calls[2].params["or"]


def test_symbol_lookup_offsets_across_exact_then_fallback_without_duplicates(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: two exact rows and fallback text rows that also include those exact IDs.
    calls: list[GetCall] = []
    exact_rows = [
        {
            "id": "exact-1",
            "symbol": "005930",
            "quality_status": "HIGH_QUALITY",
            "relevance_score": 90,
            "published_at": "2026-07-16T11:00:00+00:00",
        },
        {
            "id": "exact-2",
            "symbol": "005930",
            "quality_status": "PASS",
            "relevance_score": 80,
            "published_at": "2026-07-16T10:00:00+00:00",
        },
    ]
    fallback_rows = [
        *exact_rows,
        {"id": "fallback-1", "symbol": "", "published_at": "2026-07-16T09:00:00+00:00"},
        {"id": "fallback-2", "symbol": "", "published_at": "2026-07-16T08:00:00+00:00"},
        {"id": "fallback-3", "symbol": "", "published_at": "2026-07-16T07:00:00+00:00"},
        {"id": "fallback-4", "symbol": "", "published_at": "2026-07-16T06:00:00+00:00"},
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        if params.get("symbol") == "eq.005930":
            if "limit" not in params:
                return FakeGetResponse(payload=[], content_range="0-1/2")
            offset = int(params.get("offset", "0"))
            limit = int(params["limit"])
            return FakeGetResponse(payload=exact_rows[offset: offset + limit])
        assert params.get("id") == "not.in.(exact-1,exact-2)"
        offset = int(params.get("offset", "0"))
        limit = int(params["limit"])
        fallback_only = [row for row in fallback_rows if row["id"] not in {"exact-1", "exact-2"}]
        return FakeGetResponse(payload=fallback_only[offset: offset + limit])

    monkeypatch.setattr(requests, "get", fake_get)

    # When: consecutive pages cross from exact rows into fallback rows.
    first_page = configured_repository.list_articles(
        query="삼성전자",
        symbol="005930",
        limit=3,
        offset=0,
    )
    second_page = configured_repository.list_articles(
        query="삼성전자",
        symbol="005930",
        limit=3,
        offset=3,
    )

    # Then: fallback offset skips rows already surfaced on the previous page.
    assert [item["id"] for item in first_page] == ["exact-1", "exact-2", "fallback-1"]
    assert [item["id"] for item in second_page] == ["fallback-2", "fallback-3", "fallback-4"]
    assert set(item["id"] for item in first_page).isdisjoint(
        item["id"] for item in second_page
    )
    fallback_calls = [call for call in calls if "or" in call.params]
    assert fallback_calls[0].params["offset"] == "0"
    assert fallback_calls[1].params["offset"] == "1"


def test_symbol_lookup_large_offset_uses_bounded_exact_page(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: a high but allowed UI page offset still has enough exact symbol rows.
    calls: list[GetCall] = []
    exact_rows = [
        {
            "id": f"exact-{index}",
            "symbol": "005930",
            "quality_status": "PASS",
            "relevance_score": 50,
            "published_at": "2026-07-16T10:00:00+00:00",
        }
        for index in range(100)
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        assert params["limit"] != "1000"
        return FakeGetResponse(payload=exact_rows)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: the repository lists a later symbol page.
    result = configured_repository.list_articles(
        query="삼성전자",
        symbol="005930",
        limit=100,
        offset=900,
    )

    # Then: the exact read is a bounded page, not an offset-plus-limit prefix scan.
    assert len(result) == 100
    assert calls[0].params["limit"] == "100"
    assert calls[0].params["offset"] == "900"
    assert len(calls) == 1


def test_symbol_count_large_exact_count_does_not_fetch_all_exact_ids(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: exact symbol count is far larger than the safe ID exclusion window.
    calls: list[GetCall] = []
    responses = [
        FakeGetResponse(payload=[], content_range="0-0/100000"),
        FakeGetResponse(payload=[], content_range="0-499/500"),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        assert params.get("limit") != "100000"
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: total count is requested for that symbol.
    count = configured_repository.count_articles(query="삼성전자", symbol="005930")

    # Then: fallback count remains bounded and documented approximate without a huge ID fetch.
    assert count == 100500
    assert len(calls) == 2
    assert "id" not in calls[1].params
    assert "title.ilike.*삼성전자*" in calls[1].params["or"]


def test_symbol_count_uses_bounded_fallback_when_exact_count_times_out(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: exact symbol count times out but a bounded exact read can still return rows.
    calls: list[GetCall] = []
    timeout_response = requests.Response()
    timeout_response.status_code = 500
    timeout_response._content = b'{"code":"57014"}'
    responses = [
        timeout_response,
        FakeGetResponse(payload=[{"id": "first"}, {"id": "second"}]),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse | requests.Response:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: count is requested for an exact symbol lookup.
    count = configured_repository.count_articles(symbol="005930")

    # Then: the count falls back to a bounded exact list count.
    assert count == 2
    assert calls[1].params["symbol"] == "eq.005930"
    assert calls[1].params["limit"] == "10"


def test_symbol_count_excludes_null_and_rejected_quality_rows(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: exact count is empty and fallback count is queried.
    calls: list[GetCall] = []
    responses = [
        FakeGetResponse(payload=[], content_range="0-0/0"),
        FakeGetResponse(payload=[], content_range="0-0/0"),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: count is requested for a symbol lookup.
    count = configured_repository.count_articles(query="삼성전자", symbol="005930")

    # Then: both count requests exclude legacy null-quality and rejected rows.
    assert count == 0
    assert calls[0].params["quality_status"] == "in.(PASS,HIGH_QUALITY,LOW_CONFIDENCE)"
    assert calls[1].params["quality_status"] == "in.(PASS,HIGH_QUALITY,LOW_CONFIDENCE)"


def test_symbol_count_uses_bounded_fallback_when_text_count_times_out(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: exact symbol count is empty and broad fallback text count times out.
    calls: list[GetCall] = []
    timeout_response = requests.Response()
    timeout_response.status_code = 500
    timeout_response._content = b'{"code":"57014"}'
    responses = [
        FakeGetResponse(payload=[], content_range="0-0/0"),
        timeout_response,
        FakeGetResponse(payload=[{"id": "first"}, {"id": "second"}]),
    ]

    def fake_get(
        url: str,
        *,
        headers: dict[str, str],
        params: dict[str, str],
        timeout: int,
    ) -> FakeGetResponse | requests.Response:
        calls.append(GetCall(url=url, params=params, timeout=timeout))
        return responses.pop(0)

    monkeypatch.setattr(requests, "get", fake_get)

    # When: count is requested for a broad symbol fallback query.
    count = configured_repository.count_articles(query="BTC", symbol="BTC")

    # Then: the count falls back to a bounded list count instead of failing the route.
    assert count == 2
    assert calls[2].params["limit"] == "10"
    assert calls[2].params["order"] == "published_at.desc"


def test_upsert_articles_adds_default_quality_metadata_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    configured_repository: NewsRepository,
) -> None:
    # Given: a writer reaches the repository with a row that has no quality fields.
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-key")
    configured_repository.supabase_service_role_key = "service-key"
    calls: list[PostCall] = []

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: list[dict[str, Any]],
        timeout: int,
    ) -> FakePostResponse:
        calls.append(PostCall(url=url, json=json, timeout=timeout))
        return FakePostResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    # When: the repository persists that row.
    configured_repository.upsert_articles(
        [
            {
                "title": "삼성전자 시장 전망",
                "summary": "삼성전자 주가와 실적 전망",
                "url": "https://example.com/news",
            }
        ]
    )

    # Then: the stored payload cannot create a new null-quality row.
    stored = calls[0].json[0]
    assert stored["quality_status"] == "PASS"
    assert stored["relevance_score"] == 45
    assert stored["excluded_reason"] is None
    assert stored["quality_checked_at"]


def test_news_route_passes_symbol_separately_from_display_name_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the route has metadata for a stock symbol and a repository capturing call arguments.
    app = Flask(__name__)
    repository = CapturingNewsRepository()
    app.news_repository = repository
    app.news_summary_service = DisabledSummaryService()
    app.register_blueprint(news_bp)
    monkeypatch.setitem(news_route.SYMBOL_METADATA, "005930", {"display_name": "삼성전자"})

    # When: the API is called with a symbol.
    response = app.test_client().get("/api/news?symbol=005930&limit=5")

    # Then: the symbol remains a separate repository argument and the display name is only fallback text.
    assert response.status_code == 200
    assert repository.list_kwargs == {
        "market": "ALL",
        "query": "삼성전자",
        "symbol": "005930",
        "limit": 5,
        "offset": 0,
    }
    assert repository.count_kwargs == {
        "market": "ALL",
        "query": "삼성전자",
        "symbol": "005930",
    }
