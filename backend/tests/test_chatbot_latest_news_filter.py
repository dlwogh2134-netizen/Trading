from backend.services.chatbot.web_fallback_search_service import ChatbotWebFallbackSearchService


def test_news_query_removes_price_intent_from_mixed_request():
    query = ChatbotWebFallbackSearchService._normalize_news_query(
        "한성기업 현재 주가랑 뉴스"
    )

    assert query == "한성기업"


def test_disclosure_query_removes_price_intent_from_mixed_request():
    query = ChatbotWebFallbackSearchService._normalize_disclosure_query(
        "한성기업 현재 주가랑 공시"
    )

    assert query == "한성기업"


def test_empty_disclosure_notice_uses_normalized_subject():
    notice = ChatbotWebFallbackSearchService._combined_disclosure_result_not_found(
        "한성기업 현재 주가랑 공시"
    )["data"]["message"]

    assert "한성기업에 맞는" in notice
    assert "현재 주가랑" not in notice


def test_quote_only_headline_is_excluded_from_company_news():
    assert ChatbotWebFallbackSearchService._is_quote_only_news_article(
        {"title": "Hansung Ent 오늘의 주가 | 003680 실시간 티커", "summary": ""}
    )
    assert not ChatbotWebFallbackSearchService._is_quote_only_news_article(
        {"title": "한성기업, 신규 공급계약 체결", "summary": "매출 확대가 기대된다."}
    )
