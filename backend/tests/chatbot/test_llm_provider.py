# backend/tests/chatbot/test_llm_provider.py
import os
import pytest


def test_create_chatbot_llm_returns_model_with_fallbacks(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("CHATBOT_PRIMARY_MODEL", "gemini-3.5-pro")
    monkeypatch.setenv("CHATBOT_SECONDARY_MODEL", "gemini-3.5-flash")
    monkeypatch.setenv("CHATBOT_FALLBACK_MODEL", "gpt-4.1-mini")

    from backend.services.chatbot.llm_provider import create_chatbot_llm
    llm = create_chatbot_llm()
    assert llm is not None
    assert hasattr(llm, "invoke")


def test_create_chatbot_llm_gemini_only(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from backend.services.chatbot.llm_provider import create_chatbot_llm
    llm = create_chatbot_llm()
    assert llm is not None


def test_create_chatbot_llm_openai_only(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    from backend.services.chatbot.llm_provider import create_chatbot_llm
    llm = create_chatbot_llm()
    assert llm is not None


def test_create_chatbot_llm_no_keys_raises(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from backend.services.chatbot.llm_provider import create_chatbot_llm
    with pytest.raises(RuntimeError, match="API"):
        create_chatbot_llm()


def test_get_chatbot_config_defaults(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")

    from backend.services.chatbot.llm_provider import get_chatbot_config
    config = get_chatbot_config()
    assert config["primary_model"] == "gemini-3.5-pro"
    assert config["secondary_model"] == "gemini-3.5-flash"
    assert config["fallback_model"] == "gpt-4.1-mini"
    assert config["temperature"] == 0.3
    assert config["max_output_tokens"] >= 2048
    assert config["max_history_messages"] >= 50
    assert config["max_tool_rounds"] >= 5
