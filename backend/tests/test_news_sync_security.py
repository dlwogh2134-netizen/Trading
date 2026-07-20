from __future__ import annotations

from typing import Any

import pytest
import requests
from flask import Flask

from backend.routes.news import news_bp
from backend.services.news_filter_validation import NewsFilterValidationError
from backend.services.news_ingest import NewsIngestService
from backend.services.news_repository import NewsRepository


class FakeNewsRepository:
    def __init__(self) -> None:
        self.fetch_logs: list[dict[str, Any]] = []
        self.upserted_articles: list[dict[str, Any]] = []

    def insert_fetch_log(self, payload: dict[str, Any]) -> None:
        self.fetch_logs.append(payload)

    def upsert_articles(self, articles: list[dict[str, Any]]) -> None:
        self.upserted_articles.extend(articles)


class DisabledSummaryService:
    enabled = False


class CapturingSummaryService:
    enabled = True

    def __init__(self) -> None:
        self.summarized_articles: list[dict[str, Any]] = []

    def summarize(self, article: dict[str, Any]) -> dict[str, str]:
        self.summarized_articles.append(article)
        return {
            "ai_summary": "요약된 뉴스입니다.",
            "ai_summary_model": "test-model",
            "ai_summary_prompt_version": "test-v1",
        }


class CapturingRepository:
    def __init__(self) -> None:
        self.called = False
        self.articles: list[dict[str, Any]] = []
        self.listed_article_ids: list[list[str]] = []
        self.upserted_summaries: list[dict[str, Any]] = []

    def list_articles(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.called = True
        return self.articles

    def count_articles(self, **kwargs: Any) -> int:
        self.called = True
        return len(self.articles)

    def list_articles_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        self.called = True
        self.listed_article_ids.append(ids)
        return [article for article in self.articles if article.get("id") in ids]

    def upsert_article_summaries(self, rows: list[dict[str, Any]]) -> None:
        self.called = True
        self.upserted_summaries.extend(rows)


class RaisingFinnhubResponse:
    def raise_for_status(self) -> None:
        raise requests.exceptions.HTTPError(
            "500 Server Error: Internal Server Error for url: "
            "https://finnhub.io/api/v1/company-news?symbol=AAPL&token=secret-token"
        )

    def json(self) -> list[dict[str, Any]]:
        return []


@pytest.fixture
def news_app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    monkeypatch.setenv("NEWS_SYNC_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setattr(
        "backend.routes.news.validate_access_token",
        lambda auth_header: ("user-1", auth_header.removeprefix("Bearer ")),
        raising=False,
    )
    app = Flask(__name__)
    app.news_repository = CapturingRepository()
    app.news_summary_service = DisabledSummaryService()
    app.news_ingest_service = object()
    app.register_blueprint(news_bp)
    return app


def test_news_feed_is_read_only_when_cached_summary_is_missing(news_app: Flask) -> None:
    # Given: 조회 결과의 최신 기사에 AI 요약이 없고 요약 서비스가 활성화되어 있습니다.
    repository = news_app.news_repository
    summary_service = CapturingSummaryService()
    news_app.news_summary_service = summary_service
    repository.articles = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "삼성전자 투자 확대",
            "ai_summary": "",
            "ai_summary_model": None,
        }
    ]

    # When: 인증 없이 공개 뉴스 목록을 조회합니다.
    response = news_app.test_client().get("/api/news")

    # Then: GET 요청은 LLM 비용 호출이나 service-role 쓰기를 실행하지 않습니다.
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["data"]["items"][0]["ai_summary"] == ""
    assert summary_service.summarized_articles == []
    assert repository.upserted_summaries == []


def test_news_summary_ensure_rejects_unauthenticated_cost_write_route(news_app: Flask) -> None:
    # Given: 요약 생성 대상 기사가 있고 요약 서비스가 활성화되어 있습니다.
    repository = news_app.news_repository
    summary_service = CapturingSummaryService()
    news_app.news_summary_service = summary_service
    repository.articles = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "삼성전자 투자 확대",
            "ai_summary": "",
        }
    ]

    # When: 관리자 토큰 없이 요약 보장을 요청합니다.
    response = news_app.test_client().post(
        "/api/news/summaries/ensure",
        json={"article_ids": ["550e8400-e29b-41d4-a716-446655440000"]},
    )

    # Then: Repository 조회, LLM 요약, DB 쓰기를 모두 실행하지 않고 거부합니다.
    assert response.status_code == 403
    assert response.get_json()["success"] is False
    assert repository.listed_article_ids == []
    assert summary_service.summarized_articles == []
    assert repository.upserted_summaries == []


def test_news_summary_ensure_accepts_logged_in_user(news_app: Flask) -> None:
    # Given: 로그인 사용자가 요약이 없는 기사 ID를 전달합니다.
    repository = news_app.news_repository
    summary_service = CapturingSummaryService()
    news_app.news_summary_service = summary_service
    repository.articles = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "삼성전자 투자 확대",
            "ai_summary": "",
        }
    ]

    # When: 사용자 JWT로 요약 보장을 요청합니다.
    response = news_app.test_client().post(
        "/api/news/summaries/ensure",
        headers={"Authorization": "Bearer user-token"},
        json={"article_ids": ["550e8400-e29b-41d4-a716-446655440000"]},
    )

    # Then: 종목 상세 뉴스 탭의 요약보기가 정상적으로 요약을 생성합니다.
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["data"]["generatedCount"] == 1
    assert repository.listed_article_ids == [["550e8400-e29b-41d4-a716-446655440000"]]
    assert len(summary_service.summarized_articles) == 1
    assert repository.upserted_summaries[0]["ai_summary"] == "요약된 뉴스입니다."


def test_news_summary_ensure_accepts_configured_admin_token(news_app: Flask) -> None:
    # Given: 관리자가 요약이 없는 기사 ID를 전달합니다.
    repository = news_app.news_repository
    summary_service = CapturingSummaryService()
    news_app.news_summary_service = summary_service
    repository.articles = [
        {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "title": "삼성전자 투자 확대",
            "ai_summary": "",
        }
    ]

    # When: 올바른 관리자 토큰으로 요약 보장을 요청합니다.
    response = news_app.test_client().post(
        "/api/news/summaries/ensure",
        headers={"X-Admin-Token": "admin-secret"},
        json={"article_ids": ["550e8400-e29b-41d4-a716-446655440000"]},
    )

    # Then: 해당 기사만 조회해 요약을 생성하고 저장합니다.
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["data"]["generatedCount"] == 1
    assert repository.listed_article_ids == [["550e8400-e29b-41d4-a716-446655440000"]]
    assert len(summary_service.summarized_articles) == 1
    assert repository.upserted_summaries[0]["ai_summary"] == "요약된 뉴스입니다."


def test_news_summary_ensure_rejects_invalid_article_id_before_repository(
    news_app: Flask,
) -> None:
    # Given: PostgREST 필터 문법을 포함한 article_ids 값입니다.
    repository = news_app.news_repository
    news_app.news_summary_service = CapturingSummaryService()

    # When: 관리자가 잘못된 기사 ID로 요약 보장을 요청합니다.
    response = news_app.test_client().post(
        "/api/news/summaries/ensure",
        headers={"X-Admin-Token": "admin-secret"},
        json={"article_ids": ["550e8400-e29b-41d4-a716-446655440000),id.not.is.null,("]},
    )

    # Then: Repository의 raw id=in.(...) 필터 구성 전에 400으로 거부합니다.
    payload = response.get_json()
    assert response.status_code == 400
    assert payload["success"] is False
    assert "article_ids" in payload["error"]["raw_message"]
    assert repository.listed_article_ids == []
    assert repository.upserted_summaries == []


def test_news_repository_rejects_invalid_article_id_before_postgrest_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: Repository가 Supabase 설정을 가지고 있고 악성 article id를 받습니다.
    monkeypatch.setenv("SUPABASE_URL", "https://supabase.example.test")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")

    def fail_if_requested(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("PostgREST request must not be called for invalid article_ids")

    monkeypatch.setattr(requests, "get", fail_if_requested)
    repository = NewsRepository()

    # When / Then: id=in.(...) 필터 문자열 생성 전에 검증 오류를 발생시킵니다.
    with pytest.raises(NewsFilterValidationError):
        repository.list_articles_by_ids(["550e8400-e29b-41d4-a716-446655440000),id.not.is.null,("])


def test_finnhub_http_error_token_is_not_returned_or_logged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: Finnhub 실패 예외 문자열에 token 쿼리 파라미터가 포함됩니다.
    monkeypatch.setenv("NEWS_SYNC_ADMIN_TOKEN", "admin-secret")
    repository = FakeNewsRepository()
    service = object.__new__(NewsIngestService)
    service.naver_client_id = ""
    service.naver_client_secret = ""
    service.finnhub_api_key = "secret-token"
    service.repository = repository
    service.max_items_per_source = 3
    service.quality_service = object()
    service.query_planner = object()
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: RaisingFinnhubResponse())

    app = Flask(__name__)
    app.news_repository = repository
    app.news_summary_service = DisabledSummaryService()
    app.news_ingest_service = service
    app.register_blueprint(news_bp)

    # When: 관리자 토큰으로 미국 주식 뉴스 수집을 실행합니다.
    response = app.test_client().post(
        "/api/news/sync",
        headers={"X-Admin-Token": "admin-secret"},
        json={"symbol": "AAPL", "market": "GLOBAL", "asset_type": "STOCK"},
    )

    # Then: API 응답과 fetch log 어디에도 Finnhub 토큰이 남지 않습니다.
    response_text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "secret-token" not in response_text
    assert "token=secret-token" not in response_text
    assert repository.fetch_logs
    logged_error = repository.fetch_logs[0]["error_message"]
    assert "secret-token" not in logged_error
    assert "token=secret-token" not in logged_error


@pytest.mark.parametrize(
    ("path", "field"),
    [
        ("/api/news?market=KOSPI", "market"),
        ("/api/news?symbol=005930)", "symbol"),
        ("/api/news?query=삼성*,id.not.is.null,summary.ilike.*", "query"),
        ("/api/news?offset=1000000", "offset"),
    ],
)
def test_news_query_rejects_postgrest_filter_injection_inputs(
    news_app: Flask,
    path: str,
    field: str,
) -> None:
    # Given: PostgREST 필터 문법을 깨뜨릴 수 있는 조회 파라미터입니다.
    repository = news_app.news_repository

    # When: 뉴스 목록 API가 해당 파라미터를 받습니다.
    response = news_app.test_client().get(path)

    # Then: Repository에 전달하기 전에 400으로 거부합니다.
    payload = response.get_json()
    assert response.status_code == 400
    assert payload["success"] is False
    assert field in payload["error"]["raw_message"]
    assert repository.called is False
