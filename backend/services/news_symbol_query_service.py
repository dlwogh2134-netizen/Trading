from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Final

import requests

from backend.services.news_article_query_constants import (
    HIGH_QUALITY_STATUS,
    GENERAL_NEWS_VISIBLE_DAYS,
    HIGH_QUALITY_NEWS_VISIBLE_DAYS,
    NEWS_ARTICLE_SELECT,
    SYMBOL_ARTICLE_ORDER,
    VISIBLE_QUALITY_STATUS_FILTER,
)
from backend.services.news_quality_service import NewsQualityService


NewsArticleRow = dict[str, Any]
FetchArticles = Callable[[dict[str, str]], list[NewsArticleRow]]
CountArticles = Callable[[dict[str, str]], int]
BuildTextSearchFilter = Callable[[str], str]

MAX_EXACT_ID_EXCLUSION_COUNT: Final[int] = 1100


@dataclass(frozen=True, slots=True)
class NewsSymbolQueryDependencies:
    fetch_articles: FetchArticles
    fetch_article_count: CountArticles
    fetch_bounded_article_count: CountArticles
    build_text_search_filter: BuildTextSearchFilter


@dataclass(frozen=True, slots=True)
class SymbolArticleQuery:
    market: str
    query: str
    symbol: str
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class SymbolArticleCountQuery:
    market: str
    query: str
    symbol: str


@dataclass(frozen=True, slots=True)
class ArticleCountResult:
    count: int
    is_exact: bool


@dataclass(frozen=True, slots=True)
class FallbackArticleQuery:
    market: str
    text: str
    excluded_ids: list[str]
    limit: int
    offset: int


@dataclass(frozen=True, slots=True)
class ExactArticleQuery:
    market: str
    symbol: str
    limit: int
    offset: int = 0


class NewsSymbolQueryService:
    def __init__(self, dependencies: NewsSymbolQueryDependencies) -> None:
        self.dependencies = dependencies
        self.quality_service = NewsQualityService()

    def list_articles(self, query: SymbolArticleQuery) -> list[NewsArticleRow]:
        exact_rows = self._sort_symbol_articles(
            self._visible_articles(
                self.dependencies.fetch_articles(
                    self._exact_params(
                        ExactArticleQuery(
                            market=query.market,
                            symbol=query.symbol,
                            limit=query.limit,
                            offset=query.offset,
                        )
                    )
                ),
                symbol=query.symbol,
                company_name=query.query,
            )
        )
        selected_rows = exact_rows[: query.limit]
        remaining = query.limit - len(selected_rows)
        if remaining <= 0:
            return selected_rows

        if query.offset == 0:
            known_exact_count = len(exact_rows)
            excluded_ids = self._article_ids(exact_rows)
        else:
            exact_count = self._count_with_bounded_fallback(
                self._exact_params(
                    ExactArticleQuery(market=query.market, symbol=query.symbol, limit=0)
                )
            )
            known_exact_count = (
                exact_count.count
                if exact_count.is_exact
                else max(exact_count.count, query.offset + len(exact_rows))
            )
            excluded_ids = self._fetch_exact_ids_for_exclusion(
                query.market,
                query.symbol,
                known_exact_count,
            )
        fallback_rows = self._visible_articles(
            self.dependencies.fetch_articles(
                self._fallback_params(
                    FallbackArticleQuery(
                        market=query.market,
                        text=self._fallback_query(query),
                        excluded_ids=excluded_ids,
                        limit=remaining,
                        offset=max(0, query.offset - known_exact_count),
                    )
                )
            ),
            symbol=query.symbol,
            company_name=query.query,
        )
        return self._sort_symbol_articles([*selected_rows, *fallback_rows[:remaining]])

    def count_articles(self, query: SymbolArticleCountQuery) -> int:
        exact_params = self._exact_params(
            ExactArticleQuery(market=query.market, symbol=query.symbol, limit=0)
        )
        exact_count = self._count_with_bounded_fallback(exact_params)
        if exact_count.count > 0 and not exact_count.is_exact:
            return exact_count.count

        excluded_ids = self._fetch_exact_ids_for_exclusion(
            query.market,
            query.symbol,
            exact_count.count,
        )
        fallback_count = self._count_with_bounded_fallback(
            self._fallback_params(
                FallbackArticleQuery(
                    market=query.market,
                    text=self._fallback_query(query),
                    excluded_ids=excluded_ids,
                    limit=0,
                    offset=0,
                )
            )
        )
        return exact_count.count + fallback_count.count

    def _exact_params(self, query: ExactArticleQuery) -> dict[str, str]:
        params = {
            "select": NEWS_ARTICLE_SELECT,
            "order": SYMBOL_ARTICLE_ORDER,
            "is_active": "eq.true",
            "quality_status": VISIBLE_QUALITY_STATUS_FILTER,
            "published_at": f"gte.{self._oldest_visible_published_at()}",
            "symbol": f"eq.{query.symbol}",
        }
        if query.limit > 0:
            params["limit"] = str(query.limit)
        if query.offset > 0:
            params["offset"] = str(query.offset)
        if query.market != "ALL":
            params["market"] = f"eq.{query.market}"
        return params

    def _fallback_params(self, query: FallbackArticleQuery) -> dict[str, str]:
        params = {
            "select": NEWS_ARTICLE_SELECT,
            "order": "published_at.desc",
            "is_active": "eq.true",
            "quality_status": VISIBLE_QUALITY_STATUS_FILTER,
            "published_at": f"gte.{self._oldest_visible_published_at()}",
            "or": self.dependencies.build_text_search_filter(query.text),
        }
        if query.limit > 0:
            params["limit"] = str(query.limit)
            params["offset"] = str(query.offset)
        if query.excluded_ids:
            params["id"] = f"not.in.({','.join(query.excluded_ids)})"
        if query.market != "ALL":
            params["market"] = f"eq.{query.market}"
        return params

    def _fetch_exact_ids(self, market: str, symbol: str, exact_count: int) -> list[str]:
        params = self._exact_params(
            ExactArticleQuery(
                market=market,
                symbol=symbol,
                limit=max(exact_count, 1),
            )
        )
        params["select"] = "id"
        return self._article_ids(self.dependencies.fetch_articles(params))

    def _fetch_exact_ids_for_exclusion(
        self,
        market: str,
        symbol: str,
        exact_count: int,
    ) -> list[str]:
        if exact_count <= 0 or exact_count > MAX_EXACT_ID_EXCLUSION_COUNT:
            return []
        return self._fetch_exact_ids(market, symbol, exact_count)

    def _count_with_bounded_fallback(self, params: dict[str, str]) -> ArticleCountResult:
        try:
            return ArticleCountResult(
                count=self.dependencies.fetch_article_count(params),
                is_exact=True,
            )
        except requests.exceptions.HTTPError:
            return ArticleCountResult(
                count=self.dependencies.fetch_bounded_article_count(params),
                is_exact=False,
            )

    def _fallback_query(
        self,
        query: SymbolArticleQuery | SymbolArticleCountQuery,
    ) -> str:
        return query.query or query.symbol

    def _article_ids(self, articles: list[NewsArticleRow]) -> list[str]:
        return [str(article["id"]) for article in articles if article.get("id")]

    def _sort_symbol_articles(self, articles: list[NewsArticleRow]) -> list[NewsArticleRow]:
        return sorted(articles, key=self._symbol_article_sort_key)

    def _visible_articles(
        self,
        articles: list[NewsArticleRow],
        *,
        symbol: str,
        company_name: str,
    ) -> list[NewsArticleRow]:
        return [
            article
            for article in articles
            if self._is_visible_by_retention(article)
            and self.quality_service.is_symbol_article_relevant(
                article,
                symbol=symbol,
                company_name=company_name,
            )
        ]

    def _is_visible_by_retention(self, article: NewsArticleRow) -> bool:
        published_timestamp = self._published_timestamp(article.get("published_at"))
        if published_timestamp <= 0:
            return False
        age_seconds = datetime.now(timezone.utc).timestamp() - published_timestamp
        max_days = (
            HIGH_QUALITY_NEWS_VISIBLE_DAYS
            if article.get("quality_status") == HIGH_QUALITY_STATUS
            else GENERAL_NEWS_VISIBLE_DAYS
        )
        return age_seconds <= max_days * 24 * 60 * 60

    def _oldest_visible_published_at(self) -> str:
        return (
            datetime.now(timezone.utc) - timedelta(days=HIGH_QUALITY_NEWS_VISIBLE_DAYS)
        ).isoformat()

    def _symbol_article_sort_key(self, article: NewsArticleRow) -> tuple[int, int, float]:
        quality_rank = 0 if article.get("quality_status") == HIGH_QUALITY_STATUS else 1
        return (
            -self._published_timestamp(article.get("published_at")),
            -self._as_int(article.get("relevance_score")),
            quality_rank,
        )

    def _as_int(self, value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _published_timestamp(self, value: Any) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0
