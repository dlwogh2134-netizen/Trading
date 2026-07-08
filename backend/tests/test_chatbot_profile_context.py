from backend.services.chatbot.chat_service import ChatbotService


class FakeLLMClient:
    def __init__(self):
        self.system_prompt = None

    def generate_reply(self, system_prompt, user_message, user_id=None, function_schemas=None):
        self.system_prompt = system_prompt
        return {
            "reply": "테스트 응답",
            "model": "fake",
            "usage": {},
            "tool_calls": [],
        }


def test_reply_adds_investment_profile_context_to_system_prompt(monkeypatch):
    monkeypatch.setattr(
        "backend.services.chatbot.chat_service.load_user_investment_profile_context",
        lambda auth_header, user_id=None: "사용자 투자성향: 위험중립형",
    )
    monkeypatch.setattr(
        "backend.services.chatbot.chat_service.run_chatbot_tool",
        lambda auth_header, text: None,
    )

    service = ChatbotService()
    fake_llm = FakeLLMClient()
    service.llm_client = fake_llm

    result = service.reply("삼성전자 투자 의견 알려줘", user_id="user-1", auth_header="Bearer test")

    assert result["reply"] == "테스트 응답"
    assert "사용자 투자성향: 위험중립형" in fake_llm.system_prompt
