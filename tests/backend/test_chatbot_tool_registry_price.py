from backend.services.chatbot import tool_registry
from flask import Flask

from backend.routes import trade


def test_price_question_routes_to_asset_price_lookup(monkeypatch):
    calls = []

    def fake_get_internal(path, auth_header, params=None):
        calls.append((path, params))
        if path == "/api/symbol/lookup":
            return {
                "data": {
                    "symbol": "RDDT",
                    "display_name": "Reddit",
                    "asset_type": "STOCK",
                    "market": "US",
                }
            }
        if path == "/api/chart/quote":
            return {
                "data": {
                    "symbol": "RDDT",
                    "exchange": "TOSS",
                    "current_price": 151.25,
                    "change_rate": 2.35,
                    "currency": "USD",
                }
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(tool_registry, "_get_internal", fake_get_internal)

    result = tool_registry.run_chatbot_tool("Bearer test", "Reddit 지금 얼마야")

    assert result is not None
    assert result["data"]["source"] == "ASSET_PRICE"
    assert result["data"]["symbol"] == "RDDT"
    assert "Reddit(RDDT) 현재가는 $151.25" in result["reply"]
    assert calls == [
        ("/api/symbol/lookup", {"query": "RDDT"}),
        ("/api/chart/quote", {"exchange": "TOSS", "symbol": "RDDT", "broker_env": "REAL"}),
    ]


def test_chart_quote_includes_current_price_from_exchange_client(monkeypatch):
    class FakeClient:
        def get_price(self, symbol):
            assert symbol == "RDDT"
            return {"current_price": 151.25, "change_rate": 2.35}

    app = Flask(__name__)
    app.register_blueprint(trade.trade_bp)
    trade.PRICE_CHANGE_CACHE.clear()
    monkeypatch.setattr(trade, "get_cached_change_rate", lambda exchange, symbol, broker_env, auth_header: 2.35)
    monkeypatch.setattr(trade, "get_user_id_from_header", lambda auth_header: ("user-1", "token"))
    monkeypatch.setattr(
        trade,
        "_load_user_exchange_record",
        lambda auth_header, user_id, exchange, broker_env: ({"user_id": user_id}, "access", "secret"),
    )
    monkeypatch.setattr(
        trade,
        "_build_exchange_client",
        lambda exchange, broker_env, record, access_key, secret_key: FakeClient(),
    )

    response = app.test_client().get(
        "/api/chart/quote?exchange=TOSS&symbol=RDDT&broker_env=REAL",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 200
    assert response.json["data"]["current_price"] == 151.25
    assert response.json["data"]["change_rate"] == 2.35


def test_portfolio_summary_omits_missing_optional_mock_accounts(monkeypatch):
    calls = []

    def fake_post_internal(path, auth_header, body=None):
        calls.append(body)
        exchange = body["exchange"]
        env = body["env"]
        if env == "MOCK" and exchange in {"TOSS", "COINONE"}:
            raise RuntimeError(f"등록된 {exchange} ({env}) API 키 정보가 없습니다.")
        return {
            "data": {
                "currency": "KRW",
                "total_evaluation": 1000,
                "available_cash": 100,
                "holdings": [],
            }
        }

    monkeypatch.setattr(tool_registry, "_post_internal", fake_post_internal)

    result = tool_registry.get_portfolio_summary("Bearer test", "내 자산 얼마 있어?")

    assert "TOSS MOCK 계좌 조회 실패" not in result["reply"]
    assert "COINONE MOCK 계좌 조회 실패" not in result["reply"]
    assert result["data"]["errors"] == []
    assert {"exchange": "TOSS", "env": "MOCK"} in calls


def test_recommendation_reference_defaults_to_real_when_env_is_not_explicit(monkeypatch):
    class FakeRepository:
        def load_recommendations(self, auth_header, user_id):
            return [{"symbol": "RDDT", "display_name": "Reddit"}]

    monkeypatch.setattr(tool_registry, "get_user_id_from_header", lambda auth_header: ("user-1", "token"))
    monkeypatch.setattr(tool_registry, "_conversation_repository", FakeRepository())

    rewritten, error = tool_registry._with_referenced_recommendation_symbol(
        "Bearer test",
        "1번 1주 매수 제안 만들어줘",
    )

    assert error is None
    assert rewritten == "RDDT 실거래 1번 1주 매수 제안 만들어줘"


def test_real_market_precheck_error_explains_limit_price_requirement(monkeypatch):
    def fake_resolve_symbol(auth_header, query):
        assert query == "RDDT"
        return {
            "symbol": "RDDT",
            "display_name": "Reddit",
            "asset_type": "STOCK",
            "market": "US",
        }

    def fake_run_precheck(**kwargs):
        raise RuntimeError("실거래 시장가 주문은 100,000원 하드캡을 보장할 수 없어 지원하지 않습니다. 지정가를 입력해 주세요.")

    monkeypatch.setattr(tool_registry, "_resolve_symbol", fake_resolve_symbol)
    monkeypatch.setattr(tool_registry, "_run_chatbot_precheck", fake_run_precheck)

    result = tool_registry.create_trade_proposal_from_message(
        "Bearer test",
        "RDDT 실거래 1주 매수 제안 만들어줘",
    )

    assert result["data"]["reason"] == "precheck_failed"
    assert "실거래 시장가 제안은 만들 수 없습니다" in result["reply"]
    assert "지정가" in result["reply"]
    assert "10만원" in result["reply"]
