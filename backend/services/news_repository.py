import os
from datetime import datetime, timezone
from typing import Any

import requests

from backend.services.news_article_query_constants import (
    DEFAULT_QUALITY_STATUS,
    DEFAULT_RELEVANCE_SCORE,
    NEWS_ARTICLE_SELECT,
    VISIBLE_QUALITY_STATUS_FILTER,
)
from backend.services.news_filter_validation import (
    normalize_news_article_ids,
    normalize_news_limit,
    normalize_news_market,
    normalize_news_offset,
    normalize_news_query,
    normalize_news_symbol,
)
from backend.services.news_retention_service import (
    DisclosureRetentionCleanupCounts,
    DisclosureRetentionCleaner,
    NewsRetentionCleaner,
    NewsRetentionCleanupCounts,
    NewsRetentionDeleteError as NewsRetentionDeleteError,
)
from backend.services.news_symbol_query_service import (
    NewsSymbolQueryDependencies,
    NewsSymbolQueryService,
    SymbolArticleCountQuery,
    SymbolArticleQuery,
)


class NewsRepository:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.supabase_service_role_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.supabase_anon_key = os.getenv("SUPABASE_ANON_KEY", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    def list_articles(
        self,
        market: str = "ALL",
        query: str = "",
        symbol: str = "",
        limit: int = 10,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not self.supabase_url or not self.supabase_anon_key:
            return []

        market = normalize_news_market(market)
        query = normalize_news_query(query)
        normalized_symbol = normalize_news_symbol(symbol)
        limit = normalize_news_limit(limit)
        offset = normalize_news_offset(offset)
        if normalized_symbol:
            return self._symbol_query_service().list_articles(
                SymbolArticleQuery(
                    market=market,
                    query=query,
                    symbol=normalized_symbol,
                    limit=limit,
                    offset=offset,
                )
            )

        params: dict[str, str] = {
            "select": NEWS_ARTICLE_SELECT,
            "order": "published_at.desc",
            "limit": str(limit),
            "offset": str(offset),
            "is_active": "eq.true",
            "quality_status": VISIBLE_QUALITY_STATUS_FILTER,
        }
        if market != "ALL":
            params["market"] = f"eq.{market}"

        if query:
            params["or"] = self._text_search_filter(query)

        return self._fetch_articles(params)

    def count_articles(self, market: str = "ALL", query: str = "", symbol: str = "") -> int:
        if not self.supabase_url or not self.supabase_anon_key:
            return 0

        market = normalize_news_market(market)
        query = normalize_news_query(query)
        normalized_symbol = normalize_news_symbol(symbol)
        params: dict[str, str] = {
            "select": "id",
            "is_active": "eq.true",
            "quality_status": VISIBLE_QUALITY_STATUS_FILTER,
        }

        if normalized_symbol:
            return self._symbol_query_service().count_articles(
                SymbolArticleCountQuery(
                    market=market,
                    query=query,
                    symbol=normalized_symbol,
                )
            )
        elif query:
            params["or"] = self._text_search_filter(query)

        if market != "ALL":
            params["market"] = f"eq.{market}"

        return self._fetch_article_count_with_bounded_fallback(params)

    def _symbol_query_service(self) -> NewsSymbolQueryService:
        return NewsSymbolQueryService(
            NewsSymbolQueryDependencies(
                fetch_articles=self._fetch_articles,
                fetch_article_count=self._fetch_article_count,
                fetch_bounded_article_count=self._fetch_bounded_article_count,
                build_text_search_filter=self._text_search_filter,
            )
        )

    def _fetch_articles(self, params: dict[str, str]) -> list[dict[str, Any]]:
        response = requests.get(
            f"{self.supabase_url}/rest/v1/news_articles",
            headers=self._read_headers(),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def _fetch_article_count(self, params: dict[str, str]) -> int:
        headers = {
            **self._read_headers(),
            "Prefer": "count=exact"
        }

        response = requests.get(
            f"{self.supabase_url}/rest/v1/news_articles",
            headers=headers,
            params=params,
            timeout=15,
        )
        response.raise_for_status()

        # Supabase는 Content-Range 헤더에 전체 count를 반환합니다.
        return int(response.headers.get("Content-Range", "0").split("/")[-1])

    def _fetch_article_count_with_bounded_fallback(self, params: dict[str, str]) -> int:
        try:
            return self._fetch_article_count(params)
        except requests.exceptions.HTTPError:
            return self._fetch_bounded_article_count(params)

    def _fetch_bounded_article_count(self, params: dict[str, str]) -> int:
        bounded_params = {
            **params,
            "select": "id",
            "order": "published_at.desc",
            "limit": "10",
        }
        response = requests.get(
            f"{self.supabase_url}/rest/v1/news_articles",
            headers=self._read_headers(),
            params=bounded_params,
            timeout=15,
        )
        response.raise_for_status()
        return len(response.json())

    def _text_search_filter(self, query: str) -> str:
        or_clauses = [
            f"title.ilike.*{query}*",
            f"summary.ilike.*{query}*",
            f"company_name.ilike.*{query}*",
            f"symbol.ilike.*{query}*",
        ]
        return f"({','.join(or_clauses)})"

    def list_watchlist_symbols(self, limit: int = 5) -> list[dict[str, Any]]:
        if not self.supabase_url or not self.supabase_service_role_key:
            return []

        params = {
            "select": "symbol,name,exchange,asset_type,market_country,is_active,source,created_at",
            "is_active": "eq.true",
            "asset_type": "eq.STOCK",
            "order": "created_at.desc",
            "limit": str(limit),
        }
        try:
            response = requests.get(
                f"{self.supabase_url}/rest/v1/watchlist_symbols",
                headers=self._service_read_headers(),
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError:
            # 동적 종목 테이블이 아직 없거나 RLS가 막힌 경우 정적 키워드 수집만 진행합니다.
            return []

    def list_recent_query_keys(self, since: datetime) -> list[str]:
        if not self.is_configured:
            return []

        params = {
            "select": "query_key",
            "started_at": f"gte.{since.isoformat()}",
            "request_count": "gt.0",
        }
        response = requests.get(
            f"{self.supabase_url}/rest/v1/news_fetch_logs",
            headers=self._service_read_headers(),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return [item["query_key"] for item in response.json() if item.get("query_key")]

    def count_fetch_requests(self, source: str, since: datetime) -> int:
        if not self.is_configured:
            return 0

        params = {
            "select": "request_count",
            "source": f"eq.{source}",
            "started_at": f"gte.{since.isoformat()}",
        }
        response = requests.get(
            f"{self.supabase_url}/rest/v1/news_fetch_logs",
            headers=self._service_read_headers(),
            params=params,
            timeout=15,
        )
        response.raise_for_status()

        total = 0
        for item in response.json():
            try:
                total += int(item.get("request_count") or 0)
            except (TypeError, ValueError):
                total += 0
        return total

    def list_articles_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        if not self.supabase_url or not self.supabase_anon_key or not ids:
            return []

        ids = normalize_news_article_ids(ids)
        if not ids:
            return []

        params = {
            "select": "id,title,summary,url,market,source,company_name,symbol,raw_payload,content_hash,ai_summary,ai_summary_model,ai_summary_generated_at,ai_summary_prompt_version",
            "id": f"in.({','.join(ids)})",
        }
        response = requests.get(
            f"{self.supabase_url}/rest/v1/news_articles",
            headers=self._read_headers(),
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

    def list_recent_articles_for_ml(self, since: datetime, limit: int = 5000, offset: int = 0) -> list[dict[str, Any]]:
        if not self.is_configured:
            return []

        params = {
            "select": "id,market,source,title,summary,url,published_at,company_name,symbol,language,sentiment,raw_payload,ai_summary,ai_summary_model",
            "published_at": f"gte.{since.isoformat()}",
            "order": "published_at.asc",
            "limit": str(limit),
            "offset": str(offset),
            "is_active": "eq.true",
        }
        response = requests.get(
            f"{self.supabase_url}/rest/v1/news_articles",
            headers=self._service_read_headers(),
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def upsert_article_summaries(self, rows: list[dict[str, Any]]) -> None:
        if not self.is_configured or not rows:
            return

        for row in rows:
            article_id = str(row.get("id") or "").strip()
            if not article_id:
                continue

            payload = {
                "ai_summary": row.get("ai_summary"),
                "ai_summary_model": row.get("ai_summary_model"),
                "ai_summary_generated_at": row.get("ai_summary_generated_at"),
                "ai_summary_prompt_version": row.get("ai_summary_prompt_version"),
            }
            response = requests.patch(
                f"{self.supabase_url}/rest/v1/news_articles?id=eq.{article_id}",
                headers=self._write_headers(),
                json=payload,
                timeout=30,
            )
            response.raise_for_status()

    def upsert_articles(self, articles: list[dict[str, Any]]) -> None:
        if not self.is_configured or not articles:
            return

        quality_checked_at = datetime.now(timezone.utc).isoformat()
        normalized_articles = [
            self._with_default_quality_metadata(article, quality_checked_at)
            for article in articles
        ]

        response = requests.post(
            f"{self.supabase_url}/rest/v1/news_articles?on_conflict=url",
            headers=self._write_headers(),
            json=normalized_articles,
            timeout=30,
        )
        response.raise_for_status()

    def _with_default_quality_metadata(
        self,
        article: dict[str, Any],
        quality_checked_at: str,
    ) -> dict[str, Any]:
        status = str(article.get("quality_status") or DEFAULT_QUALITY_STATUS)
        relevance_score = article.get("relevance_score")
        return {
            **article,
            "quality_status": status,
            "relevance_score": (
                DEFAULT_RELEVANCE_SCORE if relevance_score is None else relevance_score
            ),
            "excluded_reason": article.get("excluded_reason"),
            "quality_checked_at": article.get("quality_checked_at") or quality_checked_at,
        }

    def insert_fetch_log(self, payload: dict[str, Any]) -> None:
        if not self.is_configured:
            return
        response = requests.post(
            f"{self.supabase_url}/rest/v1/news_fetch_logs",
            headers=self._write_headers(),
            json=payload,
            timeout=15,
        )
        response.raise_for_status()

    def cleanup_expired_news_retention(
        self,
        now: datetime | None = None,
    ) -> NewsRetentionCleanupCounts:
        return NewsRetentionCleaner(
            supabase_url=self.supabase_url,
            service_role_key=self.supabase_service_role_key,
        ).cleanup_expired(now=now)

    def cleanup_expired_disclosure_retention(
        self,
        now: datetime | None = None,
    ) -> DisclosureRetentionCleanupCounts:
        return DisclosureRetentionCleaner(
            supabase_url=self.supabase_url,
            service_role_key=self.supabase_service_role_key,
        ).cleanup_expired(now=now)

    def _read_headers(self) -> dict[str, str]:
        return {
            "apikey": self.supabase_anon_key,
            "Authorization": f"Bearer {self.supabase_anon_key}",
            "Content-Type": "application/json",
        }

    def _service_read_headers(self) -> dict[str, str]:
        return {
            "apikey": self.supabase_service_role_key,
            "Authorization": f"Bearer {self.supabase_service_role_key}",
            "Content-Type": "application/json",
        }

    def _write_headers(self) -> dict[str, str]:
        return {
            "apikey": self.supabase_service_role_key,
            "Authorization": f"Bearer {self.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        }
