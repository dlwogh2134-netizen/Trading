from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
import requests

from backend.services.chatbot.web_fallback_search_service import ChatbotWebFallbackSearchService
from backend.services.news_quality_service import NewsQualityService


class CapturingNewsRepository:
    def __init__(self) -> None:
        self.saved_articles: list[dict[str, Any]] = []

    def upsert_articles(self, articles: list[dict[str, Any]]) -> None:
        self.saved_articles.extend(articles)


@dataclass(frozen=True, slots=True)
class FakeFinnhubResponse:
    payload: list[dict[str, Any]]

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict[str, Any]]:
        return self.payload


class StubSummaryService:
    def summarize(self, article: dict[str, Any]) -> dict[str, str]:
        return {"ai_summary": f"{article['title']} 요약"}


def test_finnhub_web_fallback_upsert_applies_quality_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: Finnhub fallback returns a finance article that should be persisted.
    repository = CapturingNewsRepository()
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.finnhub_api_key = "test-key"
    service.news_repository = repository
    service.news_summary_service = StubSummaryService()
    service.quality_service = NewsQualityService()

    def fake_get(
        url: str,
        *,
        params: dict[str, str],
        timeout: int,
    ) -> FakeFinnhubResponse:
        return FakeFinnhubResponse(
            payload=[
                {
                    "id": "finnhub-1",
                    "datetime": int(datetime.now(timezone.utc).timestamp()),
                    "headline": "NVIDIA stock earnings outlook improves",
                    "summary": "NVIDIA shares rise as AI chip revenue and profit guidance improve.",
                    "url": "https://finance.example.com/nvidia-stock-earnings",
                }
            ]
        )

    monkeypatch.setattr(requests, "get", fake_get)

    # When: the chatbot fallback uses Finnhub and saves the fetched article.
    result = service._search_finnhub_news("NVDA latest news", 1)

    # Then: the saved row includes deterministic quality metadata before upsert.
    assert result is not None
    assert len(repository.saved_articles) == 1
    saved_article = repository.saved_articles[0]
    assert saved_article["quality_status"] == "HIGH_QUALITY"
    assert saved_article["relevance_score"] > 0
    assert saved_article["excluded_reason"] is None
    assert saved_article["quality_checked_at"]
