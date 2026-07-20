# backend/tests/chatbot/test_integration_agent.py
import os
import pytest


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")


def test_full_pipeline_chatbot_service_creates_agent():
    from backend.services.chatbot.chat_service import ChatbotService
    service = ChatbotService()
    assert service.agent is not None


def test_full_pipeline_agent_has_tool_schemas():
    from backend.services.chatbot.langchain_tools import build_tool_schemas
    schemas = build_tool_schemas()
    names = [s["function"]["name"] for s in schemas]
    expected_tools = [
        "get_asset_price", "get_asset_orderbook", "get_asset_candles",
        "get_holdings", "get_portfolio_summary", "get_exchange_rate",
        "get_market_calendar", "search_web", "get_crypto_market_context",
        "get_asset_outlook", "get_home_market_rankings",
        "search_trade_history", "list_open_orders",
        "add_watchlist_item", "remove_watchlist_item",
        "get_asset_krw_conversion",
    ]
    for tool_name in expected_tools:
        assert tool_name in names, f"Missing tool: {tool_name}"


def test_full_pipeline_failover_chain_structure():
    from backend.services.chatbot.llm_provider import create_chatbot_llm
    llm = create_chatbot_llm()
    assert hasattr(llm, "invoke")
    # with_fallbacks creates a RunnableWithFallbacks
    assert hasattr(llm, "first") or hasattr(llm, "fallbacks")


def test_full_pipeline_config_values():
    from backend.services.chatbot.llm_provider import get_chatbot_config
    config = get_chatbot_config()
    assert config["max_input_chars"] >= 50000
    assert config["max_history_messages"] >= 50
    assert config["max_tool_rounds"] >= 5
    assert config["max_output_tokens"] >= 2048
