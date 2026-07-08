from backend.services.chatbot.function_calling import FUNCTION_SCHEMAS
from backend.services.chatbot.llm_client import ChatbotLLMClient
from backend.services.chatbot.prompt_registry import build_system_prompt
from backend.services.chatbot.tool_registry import list_available_tools, run_chatbot_tool
from backend.services.supabase_client import safe_query_supabase


INVESTMENT_PROFILE_GUIDES = {
    "안정형": "원금 보전, 낮은 변동성, 손절 기준, 현금 비중과 분산 투자를 우선해서 설명합니다.",
    "안정추구형": "안정성을 우선하되 제한적인 수익 기회를 함께 검토하고, 과도한 집중 투자를 피하도록 설명합니다.",
    "위험중립형": "기대수익과 리스크의 균형, 분할 매수·매도, 포트폴리오 비중 조절을 함께 설명합니다.",
    "적극투자형": "성장성과 수익 기회를 검토하되 변동성, 손실 가능성, 익절·손절 시나리오를 함께 설명합니다.",
    "공격투자형": "높은 변동성과 손실 가능성을 명확히 경고하면서 성장성, 모멘텀, 손익 시나리오를 함께 설명합니다.",
}


def load_user_investment_profile_context(auth_header: str | None, user_id: str | None = None) -> str:
    """로그인 사용자의 투자성향을 시스템 프롬프트에 붙일 문맥으로 변환합니다."""
    if not auth_header or not user_id:
        return ""

    rows = safe_query_supabase(
        auth_header,
        "profiles",
        "GET",
        params={
            "id": f"eq.{user_id}",
            "select": "invest_type,invest_score",
            "limit": "1",
        },
    ) or []
    if not rows:
        return ""

    profile = rows[0] or {}
    invest_type = str(profile.get("invest_type") or "").strip()
    if not invest_type or invest_type == "미정":
        return ""

    score = profile.get("invest_score")
    guide = INVESTMENT_PROFILE_GUIDES.get(invest_type, "해당 투자성향에 맞춰 위험 설명과 제안 강도를 보수적으로 조절합니다.")
    score_text = f" / 점수: {score}" if score is not None else ""

    return "\n".join(
        [
            "로그인 사용자 투자성향 문맥:",
            f"- 투자성향: {invest_type}{score_text}",
            f"- 제안 기준: {guide}",
            "- 매매 제안 시 사용자의 투자성향에 맞지 않는 과도한 위험은 먼저 경고하고, 가능한 대안을 함께 제시합니다.",
        ]
    )


class ChatbotService:
    """AE trading chatbot first-pass service."""

    def __init__(self):
        self.system_prompt = build_system_prompt()
        self.llm_client = ChatbotLLMClient()

    def _build_prompt_for_user(self, auth_header: str | None, user_id: str | None) -> str:
        profile_context = load_user_investment_profile_context(auth_header, user_id)
        if not profile_context:
            return self.system_prompt
        return f"{self.system_prompt}\n\n{profile_context}"

    def reply(self, message: str, user_id: str | None = None, auth_header: str | None = None) -> dict:
        text = str(message or "").strip()
        if not text:
            return {
                "reply": "궁금한 내용을 입력해 주세요. 예: 내 보유자산 요약해줘, XRP 시세 알려줘",
                "actions": [],
            }

        tool_result = run_chatbot_tool(auth_header, text)
        if tool_result:
            return {
                "reply": tool_result["reply"],
                "actions": [],
                "meta": {
                    "user_id": user_id,
                    "available_tools": list_available_tools(),
                    "tool_result": tool_result.get("data"),
                    "source": "PROJECT_TOOL",
                },
            }

        result = self.llm_client.generate_reply(
            system_prompt=self._build_prompt_for_user(auth_header, user_id),
            user_message=text,
            user_id=user_id,
            function_schemas=FUNCTION_SCHEMAS,
        )

        return {
            "reply": result["reply"],
            "actions": [],
            "meta": {
                "user_id": user_id,
                "available_tools": list_available_tools(),
                "function_schemas": FUNCTION_SCHEMAS,
                "model": result.get("model"),
                "usage": result.get("usage"),
                "tool_calls": result.get("tool_calls"),
            },
        }
