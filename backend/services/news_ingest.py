import hashlib
import html
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from backend.services.news_error_sanitizer import sanitize_external_error_message
from backend.services.news_query_planner import NewsQuery, NewsQueryPlanner
from backend.services.news_quality_service import NewsQualityService
from backend.services.news_repository import NewsRepository
from backend.services.symbol_metadata import SYMBOL_METADATA


class NewsIngestService:
    def __init__(self) -> None:
        self.naver_client_id = os.getenv("NAVER_CLIENT_ID", "")
        self.naver_client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
        self.finnhub_api_key = os.getenv("FINNHUB_API_KEY", "")
        self.repository = NewsRepository()
        self.query_planner = NewsQueryPlanner(self.repository)
        self.quality_service = NewsQualityService()
        self.max_items_per_source = int(os.getenv("NEWS_MAX_ITEMS_PER_QUERY", "12"))

    def run_once(self) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        selected_queries, skipped_queries = self.query_planner.build_plan(
            include_naver=bool(self.naver_client_id and self.naver_client_secret),
            include_finnhub=bool(self.finnhub_api_key),
        )
        return self._run_queries(selected_queries, skipped_queries, started_at)

    def run_for_symbol(
        self,
        symbol: str,
        display_name: str = "",
        market: str = "",
        asset_type: str = "",
    ) -> dict[str, Any]:
        normalized_symbol = str(symbol or "").strip().upper()
        if not normalized_symbol:
            raise ValueError("symbol is required")

        meta = SYMBOL_METADATA.get(normalized_symbol, {})
        resolved_asset_type = str(asset_type or meta.get("asset_type") or "STOCK").strip().upper()
        resolved_display_name = str(display_name or meta.get("display_name") or normalized_symbol).strip()
        resolved_market = str(market or meta.get("market") or "").strip().upper()
        query_market = "GLOBAL" if resolved_market in {"US", "GLOBAL"} else "DOMESTIC"
        started_at = datetime.now(timezone.utc).isoformat()

        selected_queries: list[NewsQuery] = []
        if self.naver_client_id and self.naver_client_secret:
            selected_queries.extend(
                self._build_manual_naver_queries(
                    symbol=normalized_symbol,
                    company_name=resolved_display_name,
                    market=query_market,
                    asset_type=resolved_asset_type,
                )
            )

        if self.finnhub_api_key and resolved_asset_type == "STOCK" and query_market == "GLOBAL":
            selected_queries.append(
                NewsQuery(
                    provider="FINNHUB",
                    query_key=f"finnhub:manual-symbol:{normalized_symbol}",
                    query_text=normalized_symbol,
                    category="symbol",
                    market="GLOBAL",
                    priority=1,
                    symbol=normalized_symbol,
                    company_name=resolved_display_name,
                    reason="manual_symbol_request",
                )
            )

        if not selected_queries:
            raise ValueError("사용 가능한 뉴스 수집 공급원이 없습니다. NAVER 또는 FINNHUB 설정을 확인해 주세요.")

        return self._run_queries(selected_queries, skipped_queries=[], started_at=started_at)

    def _build_manual_naver_queries(
        self,
        symbol: str,
        company_name: str,
        market: str,
        asset_type: str,
    ) -> list[NewsQuery]:
        if asset_type == "CRYPTO":
            variants = [
                ("headline", company_name),
                ("market", f"{company_name} 코인"),
                ("outlook", f"{company_name} 전망"),
            ]
        elif market == "GLOBAL":
            variants = [
                ("headline", company_name),
                ("earnings", f"{company_name} earnings"),
                ("guidance", f"{company_name} outlook"),
            ]
        else:
            variants = [
                ("headline", company_name),
                ("earnings", f"{company_name} 실적"),
                ("disclosure", f"{company_name} 공시"),
            ]

        return [
            NewsQuery(
                provider="NAVER",
                query_key=f"naver:manual-symbol:{symbol}:{variant_key}",
                query_text=query_text,
                category="symbol",
                market=market,
                priority=index + 1,
                symbol=symbol,
                company_name=company_name,
                reason="manual_symbol_request",
            )
            for index, (variant_key, query_text) in enumerate(variants)
            if query_text.strip()
        ]

    def _run_queries(
        self,
        selected_queries: list[NewsQuery],
        skipped_queries: list[dict[str, Any]],
        started_at: str,
    ) -> dict[str, Any]:
        batches: list[dict[str, Any]] = []
        per_query_results: list[dict[str, Any]] = []
        saved_count = 0
        duplicate_count = 0
        rejected_count = 0

        for query in selected_queries:
            query_started_at = datetime.now(timezone.utc).isoformat()
            try:
                if query.provider == "NAVER":
                    articles = self._fetch_naver(query)
                elif query.provider == "FINNHUB":
                    articles = self._fetch_finnhub(query)
                else:
                    articles = []

                accepted_articles = self._apply_quality_gate(articles)
                query_rejected_count = len(articles) - len(accepted_articles)
                rejected_count += query_rejected_count
                batches.extend(articles)
                deduplicated = self._deduplicate(accepted_articles)
                duplicate_count += len(accepted_articles) - len(deduplicated)
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
                        "accepted_count": len(accepted_articles),
                        "rejected_count": query_rejected_count,
                    }
                )
                self._insert_query_log(query, "SUCCESS", len(articles), query_started_at)
            except Exception as exc:
                safe_error_message = sanitize_external_error_message(exc)
                per_query_results.append(
                    {
                        "provider": query.provider,
                        "query_key": query.query_key,
                        "query_text": query.query_text,
                        "query_category": query.category,
                        "status": "FAILED",
                        "fetched_count": 0,
                        "error_message": safe_error_message,
                    }
                )
                self._insert_query_log(
                    query,
                    "FAILED",
                    0,
                    query_started_at,
                    error_message=safe_error_message,
                )

        for skipped in skipped_queries:
            self._insert_skipped_log(skipped, started_at)

        return {
            "inserted": saved_count,
            "fetched": len(batches),
            "deduplicated": duplicate_count,
            "rejected": rejected_count,
            "queries_called": len(selected_queries),
            "queries_skipped": len(skipped_queries),
            "skipped": skipped_queries[:20],
            "query_results": per_query_results,
        }

    def _apply_quality_gate(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        accepted_articles: list[dict[str, Any]] = []
        for article in articles:
            scored_article = self.quality_service.apply_quality(article)
            if scored_article:
                accepted_articles.append(scored_article)
        return accepted_articles

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
