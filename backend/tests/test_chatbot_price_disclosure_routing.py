import jwt
from backend.services.chatbot.chat_service import ChatbotService


def test_mixed_price_news_disclosure_request_keeps_price_tool_routing(monkeypatch):
    calls = []

    def fake_run_chatbot_tool(auth_header, text):
        calls.append(("tool", text))
        return {
            "reply": "주가·뉴스·공시 응답",
            "data": {
                "source": "COMPOUND_INFO",
                "price": {"source": "ASSET_PRICE", "symbol": "003680", "current_price": 8460},
                "secondary": {"source": "NEWS_DISCLOSURE_COMBINED"},
            },
        }

    def fail_direct_search(*_args):
        raise AssertionError("혼합 요청은 공시 전용 검색으로 우회하면 안 됩니다.")

    monkeypatch.setattr("backend.services.chatbot.chat_service.run_chatbot_tool", fake_run_chatbot_tool)
    monkeypatch.setattr("backend.services.chatbot.chat_service.search_web", fail_direct_search)
    
    import requests
    def fake_request_with_retry(*args, **kwargs):
        res = requests.Response()
        res.status_code = 200
        res._content = b"[]"
        return res
    monkeypatch.setattr("backend.services.supabase_client._supabase_request_with_retry", fake_request_with_retry)

    service = ChatbotService()
    service._record_exchange = lambda *_args, **_kwargs: None
    service.agent = None

    fake_token = jwt.encode({"sub": "user-1"}, "secret", algorithm="HS256")
    auth_header = f"Bearer {fake_token}"

    result = service.reply(
        "한성기업 현재 주가랑 뉴스 공시 보여줘",
        user_id="user-1",
        auth_header=auth_header,
    )

    assert result["meta"]["tool_result"]["price"]["current_price"] == 8460
    assert calls == [("tool", "한성기업 현재 주가랑 뉴스 공시 보여줘")]
