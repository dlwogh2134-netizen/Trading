from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.services.news_ingest import NewsIngestService
from backend.services.news_query_planner import NewsQuery
from backend.services.news_quality_service import NewsQualityService


class FakeNewsRepository:
    def __init__(self) -> None:
        self.upserted_articles: list[dict[str, Any]] = []
        self.fetch_logs: list[dict[str, Any]] = []

    def upsert_articles(self, articles: list[dict[str, Any]]) -> None:
        self.upserted_articles.extend(articles)

    def insert_fetch_log(self, payload: dict[str, Any]) -> None:
        self.fetch_logs.append(payload)


def _article(
    *,
    title: str,
    summary: str,
    url: str,
    symbol: str,
    company_name: str,
    published_at: datetime | None = None,
) -> dict[str, Any]:
    issued_at = published_at or datetime.now(timezone.utc)
    return {
        "market": "DOMESTIC",
        "source": "NAVER",
        "source_article_id": url,
        "title": title,
        "summary": summary,
        "url": url,
        "published_at": issued_at.isoformat(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "company_name": company_name,
        "symbol": symbol,
        "language": "ko",
        "sentiment": None,
        "content_hash": url,
        "is_active": True,
        "raw_payload": {},
    }


def _query(symbol: str, company_name: str) -> NewsQuery:
    return NewsQuery(
        provider="NAVER",
        query_key=f"naver:test:{symbol}",
        query_text=company_name,
        category="symbol",
        market="DOMESTIC",
        priority=1,
        symbol=symbol,
        company_name=company_name,
        reason="test",
    )


def _service_with_articles(articles: list[dict[str, Any]]) -> tuple[NewsIngestService, FakeNewsRepository]:
    service = object.__new__(NewsIngestService)
    repository = FakeNewsRepository()
    service.repository = repository
    service.quality_service = NewsQualityService()
    service._fetch_naver = lambda query: articles
    service._fetch_finnhub = lambda query: []
    return service, repository


def test_news_quality_symbol_articles_are_scored_before_upsert() -> None:
    # Given: 삼성전자, Nvidia, Bitcoin 관련 기사와 외부 텍스트가 섞여 있습니다.
    articles = [
        _article(
            title="삼성전자 반도체 실적 전망 개선",
            summary="삼성전자 005930 실적과 매출 전망을 다룬 기사입니다.",
            url="https://finance.example.com/samsung-earnings",
            symbol="005930",
            company_name="삼성전자",
        ),
        _article(
            title="Nvidia NVDA earnings lift AI chip outlook",
            summary="Nvidia revenue guidance and stock market reaction improved.",
            url="https://www.reuters.com/markets/nvidia-earnings",
            symbol="NVDA",
            company_name="Nvidia",
        ),
        _article(
            title="Bitcoin price rises as ETF inflows grow",
            summary="BTC market volume and crypto price momentum increased.",
            url="https://www.coindesk.com/markets/bitcoin-price",
            symbol="BTC",
            company_name="Bitcoin",
        ),
        _article(
            title="서울 아파트 청약 일정 정리",
            summary="부동산 분양 일정과 생활 정보를 정리한 기사입니다.",
            url="https://example.com/real-estate",
            symbol="005930",
            company_name="삼성전자",
        ),
    ]
    service, repository = _service_with_articles(articles)

    # When: 수집 결과를 저장합니다.
    result = service._run_queries([_query("005930", "삼성전자")], [], datetime.now(timezone.utc).isoformat())

    # Then: 관련 기사만 품질 메타데이터와 함께 upsert되고 거절 수가 집계됩니다.
    assert result["inserted"] == 3
    assert result["rejected"] == 1
    assert result["query_results"][0]["rejected_count"] == 1
    assert [article["symbol"] for article in repository.upserted_articles] == ["005930", "NVDA", "BTC"]
    for article in repository.upserted_articles:
        assert article["quality_status"] in {"PASS", "HIGH_QUALITY"}
        assert isinstance(article["relevance_score"], int)
        assert article["excluded_reason"] is None
        assert article["quality_checked_at"]


def test_news_quality_strong_exact_recent_article_is_high_quality() -> None:
    # Given: 정확한 종목 신호, 금융 키워드, 최신 발행일을 가진 기사입니다.
    articles = [
        _article(
            title="Nvidia NVDA earnings beat boosts stock outlook",
            summary="Nvidia revenue, guidance, and share price moved after earnings.",
            url="https://www.reuters.com/technology/nvidia-nvda-earnings",
            symbol="NVDA",
            company_name="Nvidia",
            published_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )
    ]
    service, repository = _service_with_articles(articles)

    # When: 수집 결과를 저장합니다.
    result = service._run_queries([_query("NVDA", "Nvidia")], [], datetime.now(timezone.utc).isoformat())

    # Then: 강한 최신 금융 기사는 HIGH_QUALITY로 저장됩니다.
    assert result["inserted"] == 1
    assert repository.upserted_articles[0]["quality_status"] == "HIGH_QUALITY"
    assert repository.upserted_articles[0]["relevance_score"] >= 80


def test_news_quality_rejects_ambiguous_company_name_without_listed_context() -> None:
    # Given: 종목명과 같은 일반 단어가 들어갔지만 상장사 맥락이 없는 기사입니다.
    articles = [
        _article(
            title="신지, 인바디 측정불가 결과 공개",
            summary="방송인이 체성분 검사 결과와 일상 근황을 전했습니다.",
            url="https://www.example.com/entertainment/inbody-check",
            symbol="041830",
            company_name="인바디",
        ),
        _article(
            title="에코프로머티리얼즈, 임직원 인바디 검사 프로그램 운영",
            summary="회사는 인바디 점수 향상과 체중 감량 실적을 평가했습니다.",
            url="https://www.example.com/company/inbody-program",
            symbol="041830",
            company_name="인바디",
        ),
        _article(
            title="인바디, 코스닥 상장사 실적 개선 전망",
            summary="인바디 매출과 영업이익이 헬스케어 장비 공급 계약 확대로 증가했습니다.",
            url="https://www.example.com/markets/inbody-earnings",
            symbol="041830",
            company_name="인바디",
        ),
    ]
    service, repository = _service_with_articles(articles)

    # When: 종목별 뉴스 수집 품질 게이트를 통과시킵니다.
    result = service._run_queries([_query("041830", "인바디")], [], datetime.now(timezone.utc).isoformat())

    # Then: 생활/연예 맥락의 동명이의어 기사는 저장하지 않고 상장사 기사만 저장합니다.
    assert result["inserted"] == 1
    assert result["rejected"] == 2
    assert [article["title"] for article in repository.upserted_articles] == [
        "인바디, 코스닥 상장사 실적 개선 전망"
    ]


def test_news_quality_does_not_treat_ir_substrings_in_urls_as_listed_context() -> None:
    # Given: URL에 우연히 ir 문자열이 포함된 생활/연예 기사입니다.
    service = NewsQualityService()
    articles = [
        _article(
            title="신지, 인바디 측정불가 결과 공개",
            summary="방송인이 체성분 검사 결과와 일상 근황을 전했습니다.",
            url="https://www.ziksir.com/news/articleView.html?idxno=140397",
            symbol="041830",
            company_name="인바디",
        ),
        _article(
            title="제이쓴, 근육량 유지하고 체지방만 감소",
            summary="방송인이 인바디 측정 결과를 공개했습니다.",
            url="https://health.chosun.com/site/data/html_dir/2026071602410.html",
            symbol="041830",
            company_name="인바디",
        ),
    ]

    # When: 종목별 품질 판정을 수행합니다.
    results = [service.score_article(article) for article in articles]

    # Then: URL의 우연한 부분문자열만으로 상장사 맥락으로 통과하지 않습니다.
    assert [result.quality_status for result in results] == ["REJECTED", "REJECTED"]
    assert [result.excluded_reason for result in results] == [
        "NO_LISTED_COMPANY_CONTEXT",
        "NO_LISTED_COMPANY_CONTEXT",
    ]


def test_news_quality_excluded_and_off_topic_articles_do_not_reach_upsert() -> None:
    # Given: 위키/나무/지식인/사전/커뮤니티/비금융 결과가 섞여 있습니다.
    articles = [
        _article(
            title="삼성전자 - 위키백과",
            summary="백과사전 설명입니다.",
            url="https://ko.wikipedia.org/wiki/삼성전자",
            symbol="005930",
            company_name="삼성전자",
        ),
        _article(
            title="삼성전자 주가 나무위키",
            summary="문서형 설명입니다.",
            url="https://namu.wiki/w/삼성전자",
            symbol="005930",
            company_name="삼성전자",
        ),
        _article(
            title="삼성전자 면접 질문",
            summary="네이버 지식인 질문입니다.",
            url="https://kin.naver.com/qna/detail.naver?d1id=4",
            symbol="005930",
            company_name="삼성전자",
        ),
        _article(
            title="삼성전자 뜻",
            summary="국어사전 검색 결과입니다.",
            url="https://ko.dict.naver.com/#/entry/koko/example",
            symbol="005930",
            company_name="삼성전자",
        ),
        _article(
            title="오늘 점심 메뉴 추천",
            summary="생활 커뮤니티 인기글입니다.",
            url="https://www.clien.net/service/board/park/1",
            symbol="005930",
            company_name="삼성전자",
        ),
    ]
    service, repository = _service_with_articles(articles)

    # When: 수집 결과를 저장합니다.
    result = service._run_queries([_query("005930", "삼성전자")], [], datetime.now(timezone.utc).isoformat())

    # Then: 거절된 행은 저장소 upsert에 전달되지 않습니다.
    assert result["inserted"] == 0
    assert result["rejected"] == 5
    assert repository.upserted_articles == []
    assert result["query_results"][0]["rejected_count"] == 5


def test_news_quality_rejects_apple_product_mentions_without_investment_context() -> None:
    service = NewsQualityService()
    result = service.score_article(
        _article(
            title="하나카드, 다양한 혜택 담은 2026 쿨 썸머 페스티벌 진행",
            summary="Apple AirPods 4와 커피 쿠폰을 경품으로 제공한다.",
            url="https://www.example.com/news/apple-airpods",
            symbol="AAPL",
            company_name="Apple",
        )
    )

    assert result.quality_status == "REJECTED"
    assert result.excluded_reason == "NO_LISTED_COMPANY_CONTEXT"


def test_symbol_relevance_uses_requested_apple_identity_over_stale_row_metadata() -> None:
    service = NewsQualityService()

    assert not service.is_symbol_article_relevant(
        {
            "title": "TSMC, 스마트폰 비중 반토막...AI 매출 비중은 66% 돌파",
            "summary": "NVIDIA 관련 반도체 시장의 AI 매출 소식입니다.",
            "url": "https://www.example.com/semiconductor",
            "symbol": "AAPL",
            "company_name": "NVIDIA",
            "published_at": "2026-07-20T00:00:00+00:00",
        },
        symbol="AAPL",
        company_name="Apple",
    )
