from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Final
from uuid import UUID


ALLOWED_NEWS_MARKETS: Final[frozenset[str]] = frozenset({"ALL", "DOMESTIC", "GLOBAL"})
MAX_PUBLIC_NEWS_OFFSET: Final[int] = 1000
NEWS_SYMBOL_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Z0-9._-]{1,32}$")
NEWS_QUERY_FORBIDDEN_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\x00-\x1f\x7f,()*\"\\]")


@dataclass(frozen=True, slots=True)
class NewsFeedFilters:
    market: str
    query: str
    symbol: str
    limit: int
    offset: int


class NewsFilterValidationError(ValueError):
    def __init__(self, *, field: str, message: str) -> None:
        self.field = field
        super().__init__(f"{field}: {message}")


def normalize_news_market(value: str) -> str:
    market = str(value or "ALL").strip().upper()
    if market not in ALLOWED_NEWS_MARKETS:
        raise NewsFilterValidationError(
            field="market",
            message="ALL, DOMESTIC, GLOBAL 중 하나만 사용할 수 있습니다.",
        )
    return market


def normalize_news_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()
    if symbol and not NEWS_SYMBOL_PATTERN.fullmatch(symbol):
        raise NewsFilterValidationError(
            field="symbol",
            message="대문자 영문, 숫자, 점, 대시, 밑줄만 사용할 수 있습니다.",
        )
    return symbol


def normalize_news_query(value: str) -> str:
    query = str(value or "").strip()
    if NEWS_QUERY_FORBIDDEN_PATTERN.search(query):
        raise NewsFilterValidationError(
            field="query",
            message="PostgREST 필터 문법 문자는 검색어로 사용할 수 없습니다.",
        )
    return query


def normalize_news_limit(value: str | int) -> int:
    try:
        limit = int(value)
    except (TypeError, ValueError) as error:
        raise NewsFilterValidationError(field="limit", message="정수여야 합니다.") from error
    if limit < 1 or limit > 100:
        raise NewsFilterValidationError(field="limit", message="1 이상 100 이하만 사용할 수 있습니다.")
    return limit


def normalize_news_offset(value: str | int) -> int:
    try:
        offset = int(value)
    except (TypeError, ValueError) as error:
        raise NewsFilterValidationError(field="offset", message="정수여야 합니다.") from error
    if offset < 0 or offset > MAX_PUBLIC_NEWS_OFFSET:
        raise NewsFilterValidationError(
            field="offset",
            message=f"0 이상 {MAX_PUBLIC_NEWS_OFFSET} 이하만 사용할 수 있습니다.",
        )
    return offset


def normalize_news_article_ids(values: list[str]) -> list[str]:
    article_ids: list[str] = []
    for value in values:
        article_id = str(value or "").strip()
        if not article_id:
            continue
        try:
            article_ids.append(str(UUID(article_id)))
        except ValueError as error:
            raise NewsFilterValidationError(
                field="article_ids",
                message="UUID 형식의 기사 ID만 사용할 수 있습니다.",
            ) from error
    return article_ids


def parse_news_feed_filters(args: Mapping[str, str | int | None]) -> NewsFeedFilters:
    return NewsFeedFilters(
        market=normalize_news_market(str(args.get("market", "ALL") or "ALL")),
        query=normalize_news_query(str(args.get("query", "") or "")),
        symbol=normalize_news_symbol(str(args.get("symbol", "") or "")),
        limit=normalize_news_limit(args.get("limit", 10) or 10),
        offset=normalize_news_offset(args.get("offset", 0) or 0),
    )
