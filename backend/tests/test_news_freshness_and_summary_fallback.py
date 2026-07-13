import requests

from backend.services.chatbot.web_fallback_search_service import ChatbotWebFallbackSearchService
from backend.services.dart_analysis_service import DartDisclosureAnalysisService
from backend.services.news_summary_service import NewsSummaryService


def test_fresh_news_query_prefers_external_api_before_vector_db(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    calls: list[str] = []

    def fake_api(query, limit):
        calls.append("api")
        return {"reply": "external", "data": {"source": "NAVER_API"}}

    def fake_rag(auth_header, user_id, query, limit):
        calls.append("rag")
        return {"reply": "old-vector", "data": {"source": "VECTOR_DB"}}

    monkeypatch.setattr(service, "_search_existing_open_apis", fake_api)
    monkeypatch.setattr(service, "_search_rag", fake_rag)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "삼성전자 최신 뉴스 요약", limit=3)

    assert result["data"]["source"] == "NAVER_API"
    assert calls == ["api"]


def test_fresh_disclosure_query_does_not_fallback_to_general_news(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    calls: list[str] = []

    monkeypatch.setattr(service, "_sync_and_search_dart", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: {"reply": "disclosure-db", "data": {"source": "DISCLOSURE_DB"}})
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    def fake_naver(query, limit):
        calls.append("naver")
        return {"reply": "general-news", "data": {"source": "NAVER_API"}}

    monkeypatch.setattr(service, "_search_naver_news", fake_naver)
    monkeypatch.setattr(service, "_search_finnhub_news", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "삼성전자 최근 공시 보여줘", limit=3)

    assert result["data"]["source"] == "DISCLOSURE_DB"
    assert calls == []


def test_disclosure_query_limits_results_to_one(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    captured_limits: list[int] = []

    def fake_dart(query, limit):
        captured_limits.append(limit)
        return {"reply": "disclosures", "data": {"source": "DISCLOSURE_DB"}}

    monkeypatch.setattr(service, "_sync_and_search_dart", fake_dart)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "\uc0bc\uc131\uc804\uc790 \uacf5\uc2dc \ubcf4\uc5ec\uc918")

    assert result["data"]["source"] == "DISCLOSURE_DB"
    assert captured_limits == [1]


def test_disclosure_query_uses_one_when_default_limit_passed_without_count(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    captured_limits: list[int] = []

    def fake_dart(query, limit):
        captured_limits.append(limit)
        return {"reply": "disclosures", "data": {"source": "DISCLOSURE_DB"}}

    monkeypatch.setattr(service, "_sync_and_search_dart", fake_dart)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "\uc0bc\uc131\uc804\uc790 \uacf5\uc2dc \ubcf4\uc5ec\uc918", limit=5)

    assert result["data"]["source"] == "DISCLOSURE_DB"
    assert captured_limits == [1]


def test_disclosure_query_respects_requested_result_count(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    captured_limits: list[int] = []

    def fake_dart(query, limit):
        captured_limits.append(limit)
        return {"reply": "disclosures", "data": {"source": "DISCLOSURE_DB"}}

    monkeypatch.setattr(service, "_sync_and_search_dart", fake_dart)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "\uc0bc\uc131\uc804\uc790 \ucd5c\uadfc \uacf5\uc2dc 3\uac1c \ubcf4\uc5ec\uc918", limit=3)

    assert result["data"]["source"] == "DISCLOSURE_DB"
    assert captured_limits == [3]


def test_disclosure_query_rejects_result_count_over_three(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5

    def fail_dart(query, limit):
        raise AssertionError("3건 초과 요청은 DART 조회를 실행하지 않아야 합니다.")

    monkeypatch.setattr(service, "_sync_and_search_dart", fail_dart)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "\uc0bc\uc131\uc804\uc790 \ucd5c\uadfc \uacf5\uc2dc 4\uac1c \ubcf4\uc5ec\uc918", limit=4)

    assert result["data"]["source"] == "DISCLOSURE_LIMIT_EXCEEDED"
    assert result["data"]["max_results"] == 3
    assert "최대 3개까지 조회 가능" in result["reply"]


def test_news_query_limits_results_to_one_when_count_is_omitted(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    captured_limits: list[int] = []

    def fake_api(query, limit):
        captured_limits.append(limit)
        return {"reply": "news", "data": {"source": "NAVER_API"}}

    monkeypatch.setattr(service, "_search_existing_open_apis", fake_api)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "삼성전자 최신 뉴스 보여줘", limit=5)

    assert result["data"]["source"] == "NAVER_API"
    assert captured_limits == [1]


def test_news_query_respects_requested_result_count(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    captured_limits: list[int] = []

    def fake_api(query, limit):
        captured_limits.append(limit)
        return {"reply": "news", "data": {"source": "NAVER_API"}}

    monkeypatch.setattr(service, "_search_existing_open_apis", fake_api)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "삼성전자 최근 뉴스 3개 보여줘", limit=5)

    assert result["data"]["source"] == "NAVER_API"
    assert captured_limits == [3]


def test_news_query_rejects_result_count_over_three(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5

    def fail_api(query, limit):
        raise AssertionError("3건 초과 뉴스 요청은 외부 API 조회를 실행하지 않아야 합니다.")

    monkeypatch.setattr(service, "_search_existing_open_apis", fail_api)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)
    monkeypatch.setattr(service, "_search_tavily", lambda query, limit: None)

    result = service.search("Bearer token", "user-1", "삼성전자 최근 뉴스 4개 보여줘", limit=5)

    assert result["data"]["source"] == "NEWS_LIMIT_EXCEEDED"
    assert result["data"]["max_results"] == 3
    assert "최대 3개까지 조회 가능" in result["reply"]


def test_news_db_generates_summary_when_cached_summary_is_missing():
    service = object.__new__(ChatbotWebFallbackSearchService)

    class FakeRepository:
        def list_articles(self, query, limit):
            return [
                {
                    "title": "삼성전자 반도체 투자 확대",
                    "summary": "삼성전자가 반도체 생산라인 투자 계획을 밝혔다.",
                    "url": "https://example.com/news",
                    "source": "NAVER",
                    "market": "DOMESTIC",
                    "company_name": "삼성전자",
                }
            ]

    class FakeSummaryService:
        def summarize(self, article):
            return {
                "ai_summary": "1. 삼성전자가 반도체 투자 계획을 공개했습니다.\n2. 생산라인 확대와 공급망 대응이 핵심입니다.\n3. 세부 투자 규모와 일정은 원문 확인이 필요합니다.",
                "ai_summary_model": "fake",
                "ai_summary_prompt_version": "test",
            }

    service.news_repository = FakeRepository()
    service.news_summary_service = FakeSummaryService()

    result = service._search_news_db("삼성전자 뉴스 보여줘", 1)

    assert result is not None
    assert result["data"]["source"] == "NEWS_DB"
    assert result["data"]["items"][0]["ai_summary"].startswith("1. 삼성전자가")
    assert "삼성전자가 반도체 투자 계획을 공개했습니다" in result["reply"]


def test_disclosure_query_uses_subject_term_for_dart_db_search(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    captured_queries: list[str] = []

    def fake_list_disclosures(query, limit):
        captured_queries.append(query)
        return [
            {
                "corp_name": "\uc0bc\uc131\uc804\uc790",
                "report_nm": "\ud604\uae08\u318d\ud604\ubb3c\ubc30\ub2f9 \uacb0\uc815",
                "summary": "\ubc30\ub2f9 \uacb0\uc815 \uacf5\uc2dc",
                "url": "https://dart.fss.or.kr/example",
            }
        ]

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return fake_list_disclosures(query, limit)

    service.dart_repository = FakeRepository()

    result = service._search_disclosure_db("\uc0bc\uc131\uc804\uc790 \uacf5\uc2dc \ubcf4\uc5ec\uc918", 3)

    assert result is not None
    assert result["data"]["source"] == "DISCLOSURE_DB"
    assert captured_queries == ["\uc0bc\uc131\uc804\uc790"]


def test_disclosure_query_removes_requested_count_from_dart_db_search(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    captured_queries: list[str] = []

    def fake_list_disclosures(query, limit):
        captured_queries.append(query)
        return [
            {
                "corp_name": "\uc0bc\uc131\uc804\uc790",
                "report_nm": "\uae30\uc5c5\uc124\uba85\ud68c(IR)\uac1c\ucd5c(\uc548\ub0b4\uacf5\uc2dc)",
                "summary": "IR \uc548\ub0b4 \uacf5\uc2dc",
                "url": "https://dart.fss.or.kr/example",
            }
        ]

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return fake_list_disclosures(query, limit)

    service.dart_repository = FakeRepository()

    result = service._search_disclosure_db("\uc0bc\uc131\uc804\uc790 \ucd5c\uadfc \uacf5\uc2dc 3\uac1c \ubcf4\uc5ec\uc918", 3)

    assert result is not None
    assert result["data"]["source"] == "DISCLOSURE_DB"
    assert captured_queries == ["\uc0bc\uc131\uc804\uc790"]


def test_disclosure_db_retries_one_transient_server_error():
    service = object.__new__(ChatbotWebFallbackSearchService)

    class FakeRepository:
        def __init__(self):
            self.calls = 0

        def list_disclosures(self, query, limit):
            self.calls += 1
            if self.calls == 1:
                response = requests.Response()
                response.status_code = 500
                raise requests.HTTPError("temporary supabase failure", response=response)
            return [
                {
                    "corp_name": "\uc774\ub178\uc2a4\ud398\uc774\uc2a4",
                    "report_nm": "\uad8c\ub9ac\ub77d (\ubb34\uc0c1\uc99d\uc790)",
                    "summary": "\ubb34\uc0c1\uc99d\uc790\uc5d0 \ub530\ub978 \uad8c\ub9ac\ub77d \uc548\ub0b4\uc785\ub2c8\ub2e4.",
                    "url": "https://dart.fss.or.kr/example",
                }
            ]

    repository = FakeRepository()
    service.dart_repository = repository

    result = service._search_disclosure_db("\uc774\ub178\uc2a4\ud398\uc774\uc2a4 \uacf5\uc2dc", 3)

    assert result is not None
    assert repository.calls == 2
    assert result["data"]["source"] == "DISCLOSURE_DB"


def test_disclosure_query_does_not_use_tavily_when_dart_and_db_are_empty(monkeypatch):
    service = object.__new__(ChatbotWebFallbackSearchService)
    service.max_results = 5
    calls: list[str] = []

    monkeypatch.setattr(service, "_sync_and_search_dart", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_internal_db", lambda query, limit: None)
    monkeypatch.setattr(service, "_search_rag", lambda auth_header, user_id, query, limit: None)

    def fake_tavily(query, limit):
        calls.append("tavily")
        return {"reply": "web", "data": {"source": "TAVILY_FALLBACK"}}

    monkeypatch.setattr(service, "_search_tavily", fake_tavily)

    result = service.search("Bearer token", "user-1", "\uc0bc\uc131\uc804\uc790 \uacf5\uc2dc \ubcf4\uc5ec\uc918")

    assert result["data"]["source"] == "NO_RESULT"
    assert calls == []


def test_disclosure_db_reply_separates_items_with_blank_lines():
    service = object.__new__(ChatbotWebFallbackSearchService)

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return [
                {
                    "corp_name": "\uc0bc\uc131\uc804\uc790",
                    "report_nm": "1\ubc88 \uacf5\uc2dc",
                    "summary": "\uccab \ubc88\uc9f8 \uc694\uc57d",
                    "url": "https://dart.fss.or.kr/1",
                },
                {
                    "corp_name": "\uc0bc\uc131\uc804\uc790",
                    "report_nm": "2\ubc88 \uacf5\uc2dc",
                    "summary": "\ub450 \ubc88\uc9f8 \uc694\uc57d",
                    "url": "https://dart.fss.or.kr/2",
                },
            ]

    service.dart_repository = FakeRepository()

    result = service._search_disclosure_db("\uc0bc\uc131\uc804\uc790 \uacf5\uc2dc", 3)

    assert result is not None
    assert "https://dart.fss.or.kr/1\n\n2." in result["reply"]


def test_disclosure_db_reply_uses_analysis_summary_and_source_link():
    service = object.__new__(ChatbotWebFallbackSearchService)

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return [
                {
                    "rcept_no": "20260701000123",
                    "corp_name": "\uc0bc\uc131\uc804\uc790",
                    "report_nm": "\ud604\uae08\u318d\ud604\ubb3c\ubc30\ub2f9 \uacb0\uc815",
                    "summary": "\uc0bc\uc131\uc804\uc790 - \ud604\uae08\u318d\ud604\ubb3c\ubc30\ub2f9 \uacb0\uc815 - 2026-07-01",
                    "url": "https://dart.fss.or.kr/example",
                }
            ]

        def get_disclosure_analysis(self, rcept_no):
            return {
                "plain_summary": "\ubc30\ub2f9 \uacb0\uc815\uc744 \uacf5\uc2dc\ud588\uc73c\uba70 \ubc30\ub2f9\uae30\uc900\uc77c\uacfc \uc9c0\uae09\uc608\uc815\uc77c \ud655\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
                "headline": "\ubc30\ub2f9 \uacb0\uc815 \uacf5\uc2dc",
            }

    service.dart_repository = FakeRepository()

    result = service._search_disclosure_db("\uc0bc\uc131\uc804\uc790 \uacf5\uc2dc", 3)

    assert result is not None
    assert "\uc694\uc57d: \ubc30\ub2f9 \uacb0\uc815\uc744 \uacf5\uc2dc" in result["reply"]
    assert "https://dart.fss.or.kr/example\n\n\ucd9c\ucc98:" in result["reply"]
    assert "https://dart.fss.or.kr/dsab007/main.do" in result["reply"]
    assert "textCrpNm=%EC%82%BC%EC%84%B1%EC%A0%84%EC%9E%90" in result["reply"]


def test_disclosure_db_reply_matches_disclosure_tab_summary_view():
    service = object.__new__(ChatbotWebFallbackSearchService)

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return [
                {
                    "rcept_no": "20260701000123",
                    "corp_name": "\uc0bc\uc131\uc804\uc790",
                    "report_nm": "\ud604\uae08\u318d\ud604\ubb3c\ubc30\ub2f9 \uacb0\uc815",
                    "summary": "",
                    "url": "https://dart.fss.or.kr/example",
                }
            ]

        def get_disclosure_analysis(self, rcept_no):
            return None

    class FakeAnalysisService:
        def ensure_analysis(self, rcept_no, force_refresh=False):
            return {
                "analysis": {
                    "headline": "\ubc30\ub2f9 \uacb0\uc815 \uacf5\uc2dc",
                    "plain_summary": "\ud604\uae08\ubc30\ub2f9 \uacb0\uc815\uc744 \uacf5\uc2dc\ud588\uc73c\uba70 \ubc30\ub2f9\uae30\uc900\uc77c\uacfc \uc9c0\uae09\uc77c \ud655\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
                    "metrics": [{"label": "\ubc30\ub2f9 \uc720\ud615", "value": "\ud604\uae08\ubc30\ub2f9"}],
                    "check_items": [{"question": "\ud655\uc778 \ud3ec\uc778\ud2b8", "answer": "\ubc30\ub2f9\uae30\uc900\uc77c"}],
                    "risk_points": ["\ubc30\ub2f9 \uae30\ub300\uac10\uc774 \uc120\ubc18\uc601\ub410\ub294\uc9c0 \ud655\uc778"],
                }
            }

    service.dart_repository = FakeRepository()
    service.dart_analysis_service = FakeAnalysisService()

    result = service._search_disclosure_db("\uc0bc\uc131\uc804\uc790 \uacf5\uc2dc", 3)

    assert result is not None
    assert "\ud575\uc2ec: \ubc30\ub2f9 \uacb0\uc815 \uacf5\uc2dc" not in result["reply"]
    assert "\uc694\uc57d: \ud604\uae08\ubc30\ub2f9 \uacb0\uc815" in result["reply"]
    assert "\uc9c0\ud45c: \ubc30\ub2f9 \uc720\ud615 \u00b7 \ud604\uae08\ubc30\ub2f9" in result["reply"]
    assert "\ud655\uc778: \ud655\uc778 \ud3ec\uc778\ud2b8 \u00b7 \ubc30\ub2f9\uae30\uc900\uc77c" in result["reply"]
    assert "\ub9ac\uc2a4\ud06c: \ubc30\ub2f9 \uae30\ub300\uac10" in result["reply"]


def test_disclosure_db_reply_normalizes_title_and_repeated_headline_text():
    service = object.__new__(ChatbotWebFallbackSearchService)

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return [
                {
                    "rcept_no": "20260701000456",
                    "corp_name": "\uc774\ub178\uc2a4\ud398\uc774\uc2a4",
                    "report_nm": "\uad8c\ub9ac\ub77d              (\ubb34\uc0c1\uc99d\uc790)",
                    "url": "https://dart.fss.or.kr/example",
                }
            ]

        def get_disclosure_analysis(self, rcept_no):
            return {
                "headline": "\uc815\uc815 \uacf5\uc2dc \uacf5\uc2dc\ub85c \uc138\ubd80 \uc870\uac74 \ud655\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
                "plain_summary": "\uae30\uc874 \uacc4\uc57d \ub0b4\uc6a9\uc774 \uc815\uc815\ub410\uc2b5\ub2c8\ub2e4.",
            }

    service.dart_repository = FakeRepository()

    result = service._search_disclosure_db("\uc774\ub178\uc2a4\ud398\uc774\uc2a4 \uacf5\uc2dc", 3)

    assert result is not None
    assert "\uad8c\ub9ac\ub77d (\ubb34\uc0c1\uc99d\uc790)" in result["reply"]
    assert "\uad8c\ub9ac\ub77d              (\ubb34\uc0c1\uc99d\uc790)" not in result["reply"]
    assert "\uacf5\uc2dc \uacf5\uc2dc" not in result["reply"]
    assert "\ud575\uc2ec:" not in result["reply"]


def test_disclosure_db_refreshes_incomplete_cached_analysis_for_real_summary():
    service = object.__new__(ChatbotWebFallbackSearchService)

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return [
                {
                    "rcept_no": "20260701000789",
                    "corp_name": "\uc774\ub178\uc2a4\ud398\uc774\uc2a4",
                    "report_nm": "[\uae30\uc7ac\uc815\uc815]\ub2e8\uc77c\ud310\ub9e4\u318d\uacf5\uae09\uacc4\uc57d\uccb4\uacb0",
                    "url": "https://dart.fss.or.kr/example",
                }
            ]

        def get_disclosure_analysis(self, rcept_no):
            return {
                "headline": "\uc815\uc815 \uacf5\uc2dc\ub85c \uc138\ubd80 \uc870\uac74 \ud655\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
                "plain_summary": "",
                "risk_points": ["\uc6d0\uacf5\uc2dc \ube44\uad50 \ud544\uc694"],
            }

    class FakeAnalysisService:
        def ensure_analysis(self, rcept_no, force_refresh=False):
            return {
                "analysis": {
                    "headline": "\uacf5\uae09\uacc4\uc57d \uc815\uc815 \ub0b4\uc6a9 \ud655\uc778\uc774 \ud544\uc694\ud569\ub2c8\ub2e4.",
                    "plain_summary": "\uae30\uc874 \uacf5\uae09\uacc4\uc57d\uc758 \uae08\uc561\uacfc \uae30\uac04 \ub4f1 \uc870\uac74\uc774 \ubc14\ub00c\uc5c8\uc2b5\ub2c8\ub2e4. \uc815\uc815 \uc804\ud6c4 \ucc28\uc774\ub97c \ud655\uc778\ud574\uc57c \ud569\ub2c8\ub2e4.",
                    "metrics": [],
                    "check_items": [],
                    "risk_points": ["\uacc4\uc57d \uaddc\ubaa8\uc640 \uc77c\uc815 \ubcc0\uacbd \uc5ec\ubd80\ub97c \ud655\uc778\ud574\uc57c \ud569\ub2c8\ub2e4."],
                }
            }

    service.dart_repository = FakeRepository()
    service.dart_analysis_service = FakeAnalysisService()

    result = service._search_disclosure_db("\uc774\ub178\uc2a4\ud398\uc774\uc2a4 \uacf5\uc2dc", 3)

    assert result is not None
    assert "\uc694\uc57d: \uae30\uc874 \uacf5\uae09\uacc4\uc57d\uc758 \uae08\uc561\uacfc \uae30\uac04" in result["reply"]
    assert result["data"]["items"][0]["analysis"]["plain_summary"].startswith("\uae30\uc874 \uacf5\uae09\uacc4\uc57d")


def test_disclosure_db_refreshes_title_only_cached_analysis_before_reply():
    service = object.__new__(ChatbotWebFallbackSearchService)
    refresh_calls: list[tuple[str, bool]] = []

    class FakeRepository:
        def list_disclosures(self, query, limit):
            return [
                {
                    "rcept_no": "20260701000890",
                    "corp_name": "\uc0bc\uc131\uc804\uc790",
                    "report_nm": "\uae30\uc5c5\uc124\uba85\ud68c(IR)\uac1c\ucd5c(\uc548\ub0b4\uacf5\uc2dc)",
                    "url": "https://dart.fss.or.kr/example",
                }
            ]

        def get_disclosure_analysis(self, rcept_no):
            return {
                "analysis_source": "TITLE_ONLY",
                "confidence": "low",
                "plain_summary": "\uc0c1\uc138 \ub0b4\uc6a9\uc744 \uc544\uc9c1 \ud655\uc778\ud558\uc9c0 \ubabb\ud574 \uc81c\ubaa9 \uae30\uc900\uc73c\ub85c\ub9cc \ubd84\ub958\ud55c \uacf5\uc2dc\uc785\ub2c8\ub2e4.",
                "check_items": [{"question": "\uc0c1\uc138 \ud655\uc778", "answer": "\uc81c\ubaa9 \uae30\ubc18"}],
            }

    class FakeAnalysisService:
        def ensure_analysis(self, rcept_no, force_refresh=False):
            refresh_calls.append((rcept_no, force_refresh))
            return {
                "analysis": {
                    "analysis_source": "OPENDART_DOCUMENT",
                    "confidence": "medium",
                    "plain_summary": "\uc0bc\uc131\uc804\uc790\uac00 \uae30\uc5c5\uc124\uba85\ud68c(IR) \uac1c\ucd5c \uc77c\uc815\uacfc \ucc38\uc11d \ubc29\uc2dd\uc744 \uc548\ub0b4\ud55c \uacf5\uc2dc\uc785\ub2c8\ub2e4.",
                    "metrics": [{"label": "\ud589\uc0ac", "value": "IR"}],
                    "check_items": [{"question": "\ud655\uc778 \ud3ec\uc778\ud2b8", "answer": "\uac1c\ucd5c\uc77c\uacfc \ucc38\uc11d \ub300\uc0c1"}],
                    "risk_points": ["\uc2e4\uc801 \ubc0f \uc804\ub9dd \uc5b8\uae09 \uc5ec\ubd80\ub97c \ud655\uc778\ud574\uc57c \ud569\ub2c8\ub2e4."],
                }
            }

    service.dart_repository = FakeRepository()
    service.dart_analysis_service = FakeAnalysisService()

    result = service._search_disclosure_db("\uc0bc\uc131\uc804\uc790 \ucd5c\uadfc \uacf5\uc2dc \ubcf4\uc5ec\uc918", 1)

    assert result is not None
    assert refresh_calls == [("20260701000890", True)]
    assert "\uc694\uc57d: \uc0bc\uc131\uc804\uc790\uac00 \uae30\uc5c5\uc124\uba85\ud68c(IR) \uac1c\ucd5c" in result["reply"]
    assert "\uc0c1\uc138 \ub0b4\uc6a9\uc744 \uc544\uc9c1 \ud655\uc778\ud558\uc9c0 \ubabb\ud574" not in result["reply"]
    assert result["data"]["items"][0]["analysis"]["analysis_source"] == "OPENDART_DOCUMENT"


def test_informational_disclosure_summary_describes_content_not_price_impact():
    service = object.__new__(DartDisclosureAnalysisService)
    disclosure = {
        "rcept_no": "20260701000890",
        "corp_name": "삼성전자",
        "stock_code": "005930",
        "report_nm": "기업설명회(IR)개최(안내공시)",
        "summary": "",
    }
    detail_text = (
        "개최목적 2026년 2분기 경영실적 발표 "
        "개최일시 2026년 7월 31일 10:00 "
        "장소 컨퍼런스콜 대상 국내외 기관투자자 "
        "주요내용 경영실적 설명 및 질의응답"
    )

    analysis = service._analyze(disclosure, detail_text, "OPENDART_DOCUMENT", "")

    assert analysis["category"] == "정보성 공시"
    assert "주가 방향성" not in analysis["plain_summary"]
    assert "직접 연결" not in analysis["plain_summary"]
    assert "기업설명회" in analysis["plain_summary"]
    assert "경영실적" in analysis["plain_summary"]


def test_largest_holder_share_change_disclosure_is_summarized_as_ownership_change():
    service = object.__new__(DartDisclosureAnalysisService)
    disclosure = {
        "rcept_no": "20260706000475",
        "corp_name": "삼성전자",
        "stock_code": "005930",
        "report_nm": "최대주주등소유주식변동신고서",
        "summary": "",
    }

    analysis = service._analyze(disclosure, "", "TITLE_ONLY", "")

    assert analysis["category"] == "최대주주 지분 변동"
    assert "주가 방향성" not in analysis["plain_summary"]
    assert "직접 연결" not in analysis["plain_summary"]
    assert "주가 방향성" not in analysis["sentiment_message"]
    assert all("주가 방향성" not in point for point in analysis["key_points"])
    assert "보유주식" in analysis["plain_summary"]
    assert "변동" in analysis["plain_summary"]


def test_largest_holder_share_change_old_info_cache_is_refreshed_selectively():
    service = object.__new__(DartDisclosureAnalysisService)
    service.api_key = ""
    service.ai_enabled = False
    saved_rows: list[dict] = []

    class FakeRepository:
        def get_disclosure_analysis(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "category": "정보성 공시",
                "plain_summary": "이번 공시는 주가 방향성과 직접적인 연관이 없는 정보성 공시입니다.",
                "raw_payload": {
                    "analysis_version": "v3.33",
                    "report_nm": "최대주주등소유주식변동신고서",
                },
            }

        def get_disclosure_by_rcept_no(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "corp_name": "삼성전자",
                "stock_code": "005930",
                "report_nm": "최대주주등소유주식변동신고서",
                "summary": "",
            }

        def upsert_disclosure_analysis(self, row):
            saved_rows.append(row)
            return row

    service.repository = FakeRepository()

    result = service.ensure_analysis("20260706000475")

    assert result["fromCache"] is False
    assert saved_rows[0]["category"] == "최대주주 지분 변동"
    assert "주가 방향성" not in saved_rows[0]["plain_summary"]


def test_largest_holder_share_change_old_cache_without_report_name_is_refreshed():
    service = object.__new__(DartDisclosureAnalysisService)
    service.api_key = ""
    service.ai_enabled = False
    disclosure_reads: list[str] = []
    saved_rows: list[dict] = []

    class FakeRepository:
        def get_disclosure_analysis(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "category": "정보성 공시",
                "plain_summary": "이번 공시는 주가 방향성과 직접적인 연관이 없는 정보성 공시입니다.",
                "raw_payload": {"analysis_version": "v3.33"},
            }

        def get_disclosure_by_rcept_no(self, rcept_no):
            disclosure_reads.append(rcept_no)
            return {
                "rcept_no": rcept_no,
                "corp_name": "삼성전자",
                "stock_code": "005930",
                "report_nm": "최대주주등소유주식변동신고서",
                "summary": "",
            }

        def upsert_disclosure_analysis(self, row):
            saved_rows.append(row)
            return row

    service.repository = FakeRepository()

    result = service.ensure_analysis("20260706000475")

    assert result["fromCache"] is False
    assert disclosure_reads == ["20260706000475"]
    assert saved_rows[0]["category"] == "최대주주 지분 변동"
    assert "주가 방향성" not in saved_rows[0]["plain_summary"]


def test_largest_holder_share_change_cache_with_stale_key_points_is_refreshed():
    service = object.__new__(DartDisclosureAnalysisService)
    service.api_key = ""
    service.ai_enabled = False
    saved_rows: list[dict] = []

    class FakeRepository:
        def get_disclosure_analysis(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "category": "최대주주 지분 변동",
                "sentiment_message": "주가 방향성과 직접 연결하기 어려운 정보성 공시입니다.",
                "plain_summary": "최대주주 또는 특수관계인의 보유주식 변동을 신고한 공시입니다.",
                "key_points": ["주가 방향성과 직접 연결하기 어려운 정보성 공시입니다."],
                "raw_payload": {
                    "analysis_version": "v3.33",
                    "report_nm": "최대주주등소유주식변동신고서",
                },
            }

        def get_disclosure_by_rcept_no(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "corp_name": "삼성전자",
                "stock_code": "005930",
                "report_nm": "최대주주등소유주식변동신고서",
                "summary": "",
            }

        def upsert_disclosure_analysis(self, row):
            saved_rows.append(row)
            return row

    service.repository = FakeRepository()

    result = service.ensure_analysis("20260706800672")

    assert result["fromCache"] is False
    assert "주가 방향성" not in saved_rows[0]["sentiment_message"]
    assert all("주가 방향성" not in point for point in saved_rows[0]["key_points"])


def test_stock_option_grant_extracts_table_values_and_readable_target():
    service = object.__new__(DartDisclosureAnalysisService)
    disclosure = {
        "rcept_no": "20260706000475",
        "corp_name": "이노스페이스",
        "stock_code": "462350",
        "report_nm": "주식매수선택권부여에관한신고",
        "summary": "",
    }
    detail_text = (
        "주식매수선택권 부여 "
        "1. 부여대상자(명) 해당 상장회사의 이사ㆍ감사 또는 피용자 1 "
        "관계회사의 이사ㆍ감사 또는 피용자 - "
        "2. 당해부여 주식 (주) 보통주식 18,000 기타주식 - "
        "3. 행사 조건 행사기간 시작일 2028년 07월 06일 종료일 2033년 07월 05일 "
        "행사가격 (원) 보통주식 13,810 기타주식 - "
        "6. 부여일자 2026년 07월 06일"
    )

    analysis = service._analyze(disclosure, detail_text, "OPENDART_DOCUMENT", "")
    metric_map = {item["label"]: item["value"] for item in analysis["metrics"]}

    assert metric_map["부여대상"] == "상장회사 임직원 1명"
    assert metric_map["부여주식수"] == "18,000주"
    assert metric_map["행사가격"] == "13,810원"
    assert metric_map["행사기간"] == "2028년 07월 06일~2033년 07월 05일"
    assert "행사가격은 13,810원" in analysis["plain_summary"]
    assert "(명) 해당 상장회사" not in metric_map["부여대상"]


def test_stock_option_grant_bad_target_cache_is_refreshed_selectively():
    service = object.__new__(DartDisclosureAnalysisService)
    service.api_key = "dart-key"
    service.ai_enabled = False
    saved_rows: list[dict] = []
    detail_text = (
        "주식매수선택권 부여 "
        "1. 부여대상자(명) 해당 상장회사의 이사ㆍ감사 또는 피용자 1 "
        "관계회사의 이사ㆍ감사 또는 피용자 - "
        "2. 당해부여 주식 (주) 보통주식 18,000 기타주식 - "
        "3. 행사 조건 행사기간 시작일 2028년 07월 06일 종료일 2033년 07월 05일 "
        "행사가격 (원) 보통주식 13,810 기타주식 -"
    )

    class FakeRepository:
        def get_disclosure_analysis(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "category": "주식매수선택권",
                "plain_summary": "주식선택권 공시입니다. 임직원 보상 성격이지만 행사 물량과 행사가격에 따라 향후 희석 가능성을 확인해야 합니다.",
                "metrics": [{"label": "부여대상", "value": "(명) 해당 상장회사의 이사ㆍ감사 또는 피용자 1 관계회사..."}],
                "raw_payload": {
                    "analysis_version": "v3.33",
                    "report_nm": "주식매수선택권부여에관한신고",
                },
            }

        def get_disclosure_by_rcept_no(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "corp_name": "이노스페이스",
                "stock_code": "462350",
                "report_nm": "주식매수선택권부여에관한신고",
                "summary": "",
            }

        def upsert_disclosure_analysis(self, row):
            saved_rows.append(row)
            return row

    service.repository = FakeRepository()
    service._fetch_document_text = lambda rcept_no: detail_text

    result = service.ensure_analysis("20260706000475")

    metric_map = {item["label"]: item["value"] for item in saved_rows[0]["metrics"]}
    assert result["fromCache"] is False
    assert metric_map["부여대상"] == "상장회사 임직원 1명"
    assert metric_map["부여주식수"] == "18,000주"
    assert metric_map["행사가격"] == "13,810원"


def test_stock_option_ai_refinement_does_not_remove_core_metric_summary():
    service = object.__new__(DartDisclosureAnalysisService)
    service.ai_model = "gpt-test"
    service.ai_provider = "openai"
    service.ai_prompt_version = "v3"
    analysis = {
        "category": "주식매수선택권",
        "plain_summary": (
            "주식매수선택권 공시입니다. 임직원 보상 성격이지만 행사 물량과 행사가격에 따라 "
            "향후 희석 가능성을 확인해야 합니다 (부여 주식 수는 18,000주, 행사가격은 13,810원)."
        ),
        "metrics": [
            {"label": "부여주식수", "value": "18,000주"},
            {"label": "행사가격", "value": "13,810원"},
        ],
        "raw_payload": {},
    }
    refined = {
        "plain_summary": "주식선택권 공시입니다. 임직원 보상 성격이지만 행사 물량과 행사가격을 확인해야 합니다.",
    }

    result = service._merge_ai_refinement(analysis, refined)

    assert "18,000주" in result["plain_summary"]
    assert "13,810원" in result["plain_summary"]


def test_stock_option_cache_with_generic_summary_is_refreshed_selectively():
    service = object.__new__(DartDisclosureAnalysisService)
    service.api_key = "dart-key"
    service.ai_enabled = False
    saved_rows: list[dict] = []
    detail_text = (
        "주식매수선택권 부여 "
        "1. 부여대상자(명) 해당 상장회사의 이사ㆍ감사 또는 피용자 1 "
        "관계회사의 이사ㆍ감사 또는 피용자 - "
        "2. 당해부여 주식 (주) 보통주식 18,000 기타주식 - "
        "3. 행사 조건 행사기간 시작일 2028년 07월 06일 종료일 2033년 07월 05일 "
        "행사가격 (원) 보통주식 13,810 기타주식 -"
    )

    class FakeRepository:
        def get_disclosure_analysis(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "category": "주식매수선택권",
                "plain_summary": "주식선택권 공시입니다. 임직원 보상 성격이지만 행사 물량과 행사가격을 확인해야 합니다.",
                "metrics": [
                    {"label": "부여주식수", "value": "18,000주"},
                    {"label": "행사가격", "value": "13,810원"},
                ],
                "raw_payload": {
                    "analysis_version": "v3.33",
                    "report_nm": "주식매수선택권부여에관한신고",
                },
            }

        def get_disclosure_by_rcept_no(self, rcept_no):
            return {
                "rcept_no": rcept_no,
                "corp_name": "이노스페이스",
                "stock_code": "462350",
                "report_nm": "주식매수선택권부여에관한신고",
                "summary": "",
            }

        def upsert_disclosure_analysis(self, row):
            saved_rows.append(row)
            return row

    service.repository = FakeRepository()
    service._fetch_document_text = lambda rcept_no: detail_text

    result = service.ensure_analysis("20260706000475")

    assert result["fromCache"] is False
    assert "18,000주" in saved_rows[0]["plain_summary"]
    assert "13,810원" in saved_rows[0]["plain_summary"]


def test_openai_summary_failure_uses_gemini_primary(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("NEWS_SUMMARY_GEMINI_PRIMARY_MODEL", "gemini-primary")
    monkeypatch.setenv("NEWS_SUMMARY_GEMINI_FALLBACK_MODEL", "gemini-fallback")
    calls: list[str] = []

    def fake_post(url, **kwargs):
        json_payload = kwargs.get("json") or {}
        if "openai.com" in url:
            calls.append("openai")
            raise requests.Timeout("openai timeout")
        calls.append(json_payload["model"])

        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"output_text": "1. 첫 줄\n2. 둘째 줄\n3. 셋째 줄"}

        return Response()

    monkeypatch.setattr(requests, "post", fake_post)

    result = NewsSummaryService().summarize({
        "title": "삼성전자 뉴스",
        "summary": "실적 관련 기사입니다.",
        "company_name": "삼성전자",
        "source": "NAVER",
    })

    assert calls == ["openai", "gemini-primary"]
    assert result["ai_summary_model"] == "gemini-primary"
    assert result["ai_summary"].startswith("1. 첫 줄")


def test_summary_failure_uses_deterministic_fallback_after_all_ai_failures(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("NEWS_SUMMARY_GEMINI_PRIMARY_MODEL", "gemini-primary")
    monkeypatch.setenv("NEWS_SUMMARY_GEMINI_FALLBACK_MODEL", "gemini-fallback")
    calls: list[str] = []

    def fake_post(url, **kwargs):
        json_payload = kwargs.get("json") or {}
        calls.append("openai" if "openai.com" in url else json_payload["model"])
        raise requests.ConnectionError("temporary failure")

    monkeypatch.setattr(requests, "post", fake_post)

    result = NewsSummaryService().summarize({
        "title": "코인 뉴스",
        "summary": "비트코인 변동성 관련 기사입니다.",
        "company_name": "BTC",
        "source": "TAVILY",
    })

    assert calls == ["openai", "gemini-primary", "gemini-fallback"]
    assert result["ai_summary_model"] == "fallback"
    assert "비트코인 변동성" in result["ai_summary"]
