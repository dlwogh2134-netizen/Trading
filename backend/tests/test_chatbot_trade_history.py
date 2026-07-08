from backend.services.chatbot import tool_registry


def test_search_trade_history_displays_crypto_name_instead_of_symbol(monkeypatch):
    monkeypatch.setattr(tool_registry, "get_user_id_from_header", lambda auth_header: ("user-1", "token"))

    def fake_safe_query_supabase(auth_header, endpoint, method="GET", json_data=None, params=None):
        if endpoint == "trade_proposals":
            return [
                {
                    "created_at": "2026-07-02T10:00:00Z",
                    "exchange": "COINONE",
                    "symbol": "DOGE",
                    "side": "BUY",
                    "status": "CANCELED",
                    "order_amount": 11440,
                }
            ]
        return []

    monkeypatch.setattr(tool_registry, "safe_query_supabase", fake_safe_query_supabase)

    result = tool_registry.search_trade_history("Bearer test", "거래내역 보여줘")

    assert "도지코인" in result["reply"]
    assert "/ DOGE /" not in result["reply"]


def test_match_min_amount_treats_bare_manwon_as_ten_thousand_won():
    assert tool_registry._match_min_amount("만원이상 거래내역 보여줘") == 10000
    assert tool_registry._match_min_amount("만원 이상 거래내역 보여줘") == 10000
    assert tool_registry._match_min_amount("1만원 이상 거래내역 보여줘") == 10000
    assert tool_registry._match_min_amount("30만원 이상 거래내역 보여줘") == 300000


def test_match_min_amount_parses_korean_number_amounts():
    assert tool_registry._match_min_amount("오천원이상 거래내역 보여줘") == 5000
    assert tool_registry._match_min_amount("오천 원 이상 거래내역 보여줘") == 5000
    assert tool_registry._match_min_amount("오만원 이상 거래내역 보여줘") == 50000
    assert tool_registry._match_min_amount("삼십만원 이상 거래내역 보여줘") == 300000


def test_extract_symbol_query_keeps_stock_names_and_ignores_amount_only_queries():
    assert tool_registry._extract_symbol_query("테슬라 거래내역 보여줘") == "테슬라"
    assert tool_registry._extract_symbol_query("삼성전자 거래내역 보여줘") == "삼성전자"
    assert tool_registry._extract_symbol_query("오천원이상 거래내역 보여줘") == ""
    assert tool_registry._extract_symbol_query("만원이상 거래내역 보여줘") == ""
    assert tool_registry._extract_symbol_query("30만원 이상 거래내역 보여줘") == ""


def test_search_trade_history_filters_by_symbol_name(monkeypatch):
    captured_params = {}
    monkeypatch.setattr(tool_registry, "get_user_id_from_header", lambda auth_header: ("user-1", "token"))
    monkeypatch.setattr(tool_registry, "_resolve_symbol", lambda auth_header, query: {"symbol": "TSLA"})

    def fake_safe_query_supabase(auth_header, endpoint, method="GET", json_data=None, params=None):
        if endpoint == "trade_proposals":
            captured_params.update(params or {})
        return []

    monkeypatch.setattr(tool_registry, "safe_query_supabase", fake_safe_query_supabase)

    tool_registry.search_trade_history("Bearer test", "테슬라 거래내역 보여줘")

    assert captured_params["symbol"] == "eq.TSLA"
