import hashlib
import html
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from backend.services.news_query_planner import NewsQuery, NewsQueryPlanner
from backend.services.news_repository import NewsRepository


class NewsIngestService:
    def __init__(self) -> None:
        self.naver_client_id = os.getenv("NAVER_CLIENT_ID", "")
        self.naver_client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
        self.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")
        self.repository = NewsRepository()
        self.query_planner = NewsQueryPlanner(self.repository)
        self.max_items_per_source = int(os.getenv("NEWS_MAX_ITEMS_PER_QUERY", "12"))

    def run_once(self) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        selected_queries, skipped_queries = self.query_planner.build_plan(
            include_naver=bool(self.naver_client_id and self.naver_client_secret),
            include_finnhub=bool(self.finnhub_api_key),
        )
        batches: list[dict[str, Any]] = []
        per_query_results: list[dict[str, Any]] = []
        saved_count = 0
        duplicate_count = 0

        for query in selected_queries:
            query_started_at = datetime.now(timezone.utc).isoformat()
            try:
                if query.provider == "NAVER":
                    articles = self._fetch_naver(query)
                elif query.provider == "FINNHUB":
                    articles = self._fetch_finnhub(query)
                else:
                    articles = []

                batches.extend(articles)
                deduplicated = self._deduplicate(articles)
                duplicate_count += len(articles) - len(deduplicated)
                if deduplicated:
                    self.repository.upsert_articles(deduplicated)
                    saved_count += len(deduplicated)
                per_query_results.append(
                    {
                        "provider": query.provider,
                        "query_key": query.query_key,
                        "query_text": query.query_text,
                        "query_category": query.category,
                        "status": "SUCCESS",
                        "fetched_count": len(articles),
                    }
                )
                self._insert_query_log(query, "SUCCESS", len(articles), query_started_at)
            except Exception as exc:
                per_query_results.append(
                    {
                        "provider": query.provider,
                        "query_key": query.query_key,
                        "query_text": query.query_text,
                        "query_category": query.category,
                        "status": "FAILED",
                        "fetched_count": 0,
                        "error_message": str(exc),
                    }
                )
                self._insert_query_log(query, "FAILED", 0, query_started_at, error_message=str(exc))

        for skipped in skipped_queries:
            self._insert_skipped_log(skipped, started_at)

        return {
            "inserted": saved_count,
            "fetched": len(batches),
            "deduplicated": duplicate_count,
            "queries_called": len(selected_queries),
            "queries_skipped": len(skipped_queries),
            "skipped": skipped_queries[:20],
            "query_results": per_query_results,
        }

    def _fetch_naver(self, query: NewsQuery) -> list[dict[str, Any]]:
        response = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers={
                "X-Naver-Client-Id": self.naver_client_id,
                "X-Naver-Client-Secret": self.naver_client_secret,
            },
            params={
                "query": query.query_text,
                "display": min(self.max_items_per_source, 12),
                "sort": "date",
            },
            timeout=15,
        )
        response.raise_for_status()
        items = response.json().get("items", [])
        articles = []
        for item in items:
            title = self._clean(item.get("title", ""))
            summary = self._shorten(self._clean(item.get("description", "")))
            if not self._has_korean(title) and not self._has_korean(summary):
                continue

            url = item.get("originallink") or item.get("link") or ""
            published_at = self._parse_naver_date(item.get("pubDate"))
            raw_payload = {
                **item,
                "query_key": query.query_key,
                "query_text": query.query_text,
                "query_category": query.category,
                "collection_reason": query.reason,
            }
            articles.append(
                self._to_article(
                    market="DOMESTIC",
                    source="NAVER",
                    source_article_id=url or f"naver:{hashlib.sha256((title + query.query_key).encode()).hexdigest()}",
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=published_at,
                    company_name=query.company_name or query.query_text,
                    symbol=query.symbol,
                    language="ko",
                    raw_payload=raw_payload,
                )
            )
        return articles

    def _fetch_finnhub(self, query: NewsQuery) -> list[dict[str, Any]]:
        response = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": query.symbol,
                "from": self._days_ago_iso(7),
                "to": self._today_iso(),
                "token": self.finnhub_api_key,
            },
            timeout=15,
        )
        response.raise_for_status()
        items = response.json()[: self.max_items_per_source]
        articles = []
        for item in items:
            title = self._clean(item.get("headline", ""))
            summary = self._shorten(self._clean(item.get("summary", "")))
            url = item.get("url", "")
            raw_payload = {
                **item,
                "query_key": query.query_key,
                "query_text": query.query_text,
                "query_category": query.category,
                "collection_reason": query.reason,
            }
            articles.append(
                self._to_article(
                    market="GLOBAL",
                    source="FINNHUB",
                    source_article_id=str(item.get("id") or item.get("datetime") or url),
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=self._normalize_timestamp(item.get("datetime")),
                    company_name=item.get("related", query.symbol),
                    symbol=query.symbol,
                    language="en",
                    raw_payload=raw_payload,
                )
            )
        return articles

    def _to_article(
        self,
        market: str,
        source: str,
        source_article_id: str,
        title: str,
        summary: str,
        url: str,
        published_at: str,
        company_name: str,
        symbol: str,
        language: str,
        raw_payload: dict[str, Any],
    ) -> dict[str, Any]:
        content_hash = hashlib.sha256(f"{source}|{source_article_id}|{url}|{title}".encode("utf-8")).hexdigest()
        return {
            "market": market,
            "source": source,
            "source_article_id": source_article_id,
            "title": title or "뉴스",
            "summary": summary or "",
            "url": url,
            "published_at": published_at,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "company_name": company_name or "",
            "symbol": symbol or "",
            "language": language,
            "sentiment": None,
            "content_hash": content_hash,
            "is_active": True,
            "raw_payload": raw_payload,
        }

    def _insert_query_log(
        self,
        query: NewsQuery,
        status: str,
        fetched_count: int,
        started_at: str,
        error_message: str | None = None,
    ) -> None:
        self.repository.insert_fetch_log(
            {
                "source": query.provider,
                "query_key": query.query_key,
                "query_category": query.category,
                "query_text": query.query_text,
                "status": status,
                "fetched_count": fetched_count,
                "request_count": 1,
                "error_message": error_message,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _insert_skipped_log(self, skipped: dict[str, Any], started_at: str) -> None:
        self.repository.insert_fetch_log(
            {
                "source": skipped["provider"],
                "query_key": skipped["query_key"],
                "query_category": skipped["query_category"],
                "query_text": skipped["query_text"],
                "status": "SKIPPED",
                "fetched_count": 0,
                "request_count": 0,
                "skipped_reason": skipped["skipped_reason"],
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _deduplicate(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for article in articles:
            key = article.get("url") or article["content_hash"]
            if key in seen:
                continue
            seen.add(key)
            result.append(article)
        return result

    def _clean(self, value: str) -> str:
        clean = html.unescape(re.sub(r"<[^>]+>", "", value or "")).strip()
        return clean.replace("&quot;", "").replace('"', "").replace("'", "")

    def _shorten(self, value: str, length: int = 120) -> str:
        clean = re.sub(r"\s+", " ", value or "").strip()
        return clean if len(clean) <= length else clean[: length - 1].rstrip() + "..."

    def _has_korean(self, text: str) -> bool:
        return bool(re.search(r"[가-힣]", text or ""))

    def _parse_naver_date(self, value: str | None) -> str:
        if not value:
            return datetime.now(timezone.utc).isoformat()
        try:
            parsed = datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z")
            return parsed.astimezone(timezone.utc).isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()

    def _normalize_timestamp(self, value: Any) -> str:
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc).isoformat()
        except Exception:
            return datetime.now(timezone.utc).isoformat()

    def _today_iso(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _days_ago_iso(self, days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
