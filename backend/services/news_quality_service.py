from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse


FINANCE_KEYWORDS = frozenset(
    {
        "stock",
        "stocks",
        "share",
        "shares",
        "market",
        "earnings",
        "revenue",
        "profit",
        "guidance",
        "outlook",
        "price",
        "trading",
        "analyst",
        "etf",
        "crypto",
        "bitcoin",
        "btc",
        "semiconductor",
        "chip",
        "ai",
        "주가",
        "증시",
        "시장",
        "실적",
        "매출",
        "영업이익",
        "전망",
        "공시",
        "투자",
        "반도체",
        "환율",
        "금리",
        "코인",
        "비트코인",
        "거래량",
        "수익률",
    }
)

TRUSTED_FINANCE_DOMAINS = frozenset(
    {
        "reuters.com",
        "bloomberg.com",
        "cnbc.com",
        "marketwatch.com",
        "finance.yahoo.com",
        "coindesk.com",
        "cointelegraph.com",
        "hankyung.com",
        "mk.co.kr",
        "sedaily.com",
        "edaily.co.kr",
        "fnnews.com",
        "etnews.com",
        "thebell.co.kr",
        "finance.example.com",
    }
)

EXCLUDED_DOMAIN_PARTS = frozenset(
    {
        "wikipedia.org",
        "namu.wiki",
        "kin.naver.com",
        "dict.naver.com",
        "ko.dict.",
        "terms.naver.com",
        "dcinside.com",
        "fmkorea.com",
        "theqoo.net",
        "clien.net",
        "ruliweb.com",
        "instiz.net",
        "mlbpark.donga.com",
    }
)

EXCLUDED_URL_WORDS = frozenset(
    {
        "wiki",
        "namu",
        "dictionary",
        "dict",
        "kin",
        "qna",
        "community",
        "board",
        "forum",
    }
)

LISTED_COMPANY_CONTEXT_KEYWORDS = frozenset(
    {
        "stock",
        "stocks",
        "share",
        "shares",
        "market",
        "earnings",
        "revenue",
        "profit",
        "guidance",
        "outlook",
        "trading",
        "analyst",
        "investment",
        "contract",
        "supply",
        "주가",
        "주식",
        "증시",
        "증권",
        "시장",
        "코스피",
        "코스닥",
        "상장",
        "상장사",
        "매출",
        "영업이익",
        "순이익",
        "공시",
        "투자",
        "목표가",
        "리포트",
        "계약",
        "공급",
        "수주",
        "분기",
        "배당",
        "자사주",
        "인수",
        "합병",
    }
)

COMMON_ALIASES = {
    "005930": frozenset({"삼성전자", "samsung electronics", "samsung"}),
    "000660": frozenset({"sk하이닉스", "하이닉스", "sk hynix", "hynix"}),
    "NVDA": frozenset({"nvidia", "엔비디아"}),
    "AAPL": frozenset({"apple", "애플"}),
    "MSFT": frozenset({"microsoft", "마이크로소프트"}),
    "TSLA": frozenset({"tesla", "테슬라"}),
    "BTC": frozenset({"bitcoin", "비트코인", "btc"}),
    "ETH": frozenset({"ethereum", "이더리움", "eth"}),
    "XRP": frozenset({"xrp", "ripple", "리플"}),
}


@dataclass(frozen=True, slots=True)
class NewsQualityResult:
    relevance_score: int
    quality_status: str
    excluded_reason: str | None
    quality_checked_at: str

    @property
    def is_accepted(self) -> bool:
        return self.quality_status in {"PASS", "HIGH_QUALITY"}


class NewsQualityService:
    def score_article(self, article: dict[str, Any]) -> NewsQualityResult:
        checked_at = datetime.now(timezone.utc).isoformat()
        title = str(article.get("title") or "")
        summary = str(article.get("summary") or "")
        url = str(article.get("url") or "")
        symbol = str(article.get("symbol") or "").strip().upper()
        company_name = str(article.get("company_name") or "").strip()
        text = f"{title} {summary}".lower()
        url_text = url.lower()
        domain = self._domain(url)

        excluded_reason = self._excluded_reason(domain, url_text)
        if excluded_reason:
            return NewsQualityResult(0, "REJECTED", excluded_reason, checked_at)

        aliases = self._aliases(symbol, company_name)
        exact_signal = any(alias in text or alias in url_text for alias in aliases)
        finance_keyword_count = sum(1 for keyword in FINANCE_KEYWORDS if keyword in text or keyword in url_text)
        trusted_domain = self._is_trusted_finance_domain(domain)
        score = self._score(exact_signal, finance_keyword_count, trusted_domain, self._is_recent(article))

        if not exact_signal and symbol:
            return NewsQualityResult(score, "REJECTED", "NO_SYMBOL_SIGNAL", checked_at)
        if exact_signal and self._is_missing_listed_company_context(symbol, text, url_text):
            return NewsQualityResult(score, "REJECTED", "NO_LISTED_COMPANY_CONTEXT", checked_at)
        listed_company_context = self._has_listed_company_context(text, url_text)
        if finance_keyword_count == 0 and not trusted_domain and not listed_company_context:
            return NewsQualityResult(score, "REJECTED", "NO_FINANCE_SIGNAL", checked_at)
        if score < 35:
            return NewsQualityResult(score, "REJECTED", "LOW_RELEVANCE", checked_at)

        status = "HIGH_QUALITY" if exact_signal and finance_keyword_count > 0 and self._is_recent(article) and score >= 80 else "PASS"
        return NewsQualityResult(score, status, None, checked_at)

    def apply_quality(self, article: dict[str, Any]) -> dict[str, Any] | None:
        result = self.score_article(article)
        if not result.is_accepted:
            return None
        return {
            **article,
            "relevance_score": result.relevance_score,
            "quality_status": result.quality_status,
            "excluded_reason": result.excluded_reason,
            "quality_checked_at": result.quality_checked_at,
        }

    def is_symbol_article_relevant(
        self,
        article: dict[str, Any],
        *,
        symbol: str = "",
        company_name: str = "",
    ) -> bool:
        merged_article = {
            **article,
            "symbol": str(symbol or article.get("symbol") or "").strip().upper(),
            "company_name": str(company_name or article.get("company_name") or "").strip(),
        }
        if not any(str(merged_article.get(field) or "").strip() for field in ("title", "summary", "url")):
            return True
        title = str(merged_article.get("title") or "").lower()
        if title and merged_article["symbol"]:
            aliases = self._aliases(merged_article["symbol"], merged_article["company_name"])
            if not any(alias in title for alias in aliases):
                return False
        result = self.score_article(merged_article)
        return result.is_accepted

    def _aliases(self, symbol: str, company_name: str) -> frozenset[str]:
        candidates = {symbol.lower(), company_name.lower()}
        candidates.update(COMMON_ALIASES.get(symbol, frozenset()))
        return frozenset(candidate for candidate in candidates if candidate)

    def _domain(self, url: str) -> str:
        parsed = urlparse(url if "://" in url else f"https://{url}")
        return parsed.netloc.lower().removeprefix("www.")

    def _excluded_reason(self, domain: str, url_text: str) -> str | None:
        if any(part in domain for part in EXCLUDED_DOMAIN_PARTS):
            return "EXCLUDED_DOMAIN"
        if any(word in url_text for word in EXCLUDED_URL_WORDS):
            return "EXCLUDED_URL_PATTERN"
        return None

    def _is_trusted_finance_domain(self, domain: str) -> bool:
        return any(domain == trusted or domain.endswith(f".{trusted}") for trusted in TRUSTED_FINANCE_DOMAINS)

    def _is_missing_listed_company_context(self, symbol: str, text: str, url_text: str) -> bool:
        if symbol.lower() in text or symbol.lower() in url_text:
            return False
        return not self._has_listed_company_context(text, url_text)

    def _has_listed_company_context(self, text: str, url_text: str) -> bool:
        combined_text = f"{text} {url_text}"
        return any(keyword in combined_text for keyword in LISTED_COMPANY_CONTEXT_KEYWORDS)

    def _is_recent(self, article: dict[str, Any]) -> bool:
        raw_value = str(article.get("published_at") or "")
        try:
            published_at = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
        except ValueError:
            return False
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        return published_at >= datetime.now(timezone.utc) - timedelta(days=3)

    def _score(self, exact_signal: bool, finance_keyword_count: int, trusted_domain: bool, recent: bool) -> int:
        score = 0
        if exact_signal:
            score += 45
        score += min(finance_keyword_count, 4) * 12
        if trusted_domain:
            score += 15
        if recent:
            score += 10
        return min(score, 100)
