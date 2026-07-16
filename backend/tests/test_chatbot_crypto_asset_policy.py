from backend.services.chatbot import tool_registry
from backend.services.chatbot.order_parser import ParsedOrderIntent


def test_chatbot_default_exchange_uses_crypto_asset_master(monkeypatch):
    monkeypatch.setattr(
        tool_registry,
        "find_crypto_asset_for_query",
        lambda query: {"symbol": "ALICE", "default_exchange": "BINANCE"} if query == "ALICE" else None,
    )

    exchange = tool_registry._default_exchange_for_asset("CRYPTO", "", "ALICE")

    assert exchange == "BINANCE"


def test_chatbot_order_proposal_blocks_admin_blocked_crypto(monkeypatch):
    monkeypatch.setattr(
        tool_registry,
        "_resolve_symbol",
        lambda auth_header, query: {
            "symbol": "H",
            "display_name": "휴머니티",
            "asset_type": "CRYPTO",
            "market": "KRW",
        },
    )
    monkeypatch.setattr(
        tool_registry,
        "find_crypto_asset_for_query",
        lambda query: {"symbol": "H", "default_exchange": "COINONE"},
    )
    monkeypatch.setattr(
        tool_registry,
        "validate_crypto_asset_tradable",
        lambda symbol, exchange: (_ for _ in ()).throw(ValueError("휴머니티(H) 종목은 관리자에 의해 거래가 차단되었습니다.")),
    )
    intent = ParsedOrderIntent(
        is_order_request=True,
        side="BUY",
        symbol_query="휴머니티",
        quantity=1,
        price=100,
        order_type="LIMIT",
        broker_env="REAL",
    )

    result = tool_registry.create_trade_proposal_from_message("Bearer token", "휴머니티 1개 100원에 사줘", intent)

    assert result["data"]["reason"] == "crypto_asset_policy_blocked"
    assert "관리자에 의해 거래가 차단" in result["reply"]
