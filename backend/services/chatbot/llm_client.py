import os
import json
import logging
from datetime import date
from typing import Callable

import requests

from backend.services.auth_service import get_user_id_from_header
from backend.services.supabase_client import query_supabase, query_supabase_as_service_role


OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
logger = logging.getLogger(__name__)


class ChatbotLimitError(Exception):
    """챗봇 사용량 제한에 도달했을 때 발생하는 예외입니다."""


class ChatbotLLMClient:
    """OpenAI 챗봇 호출과 기본 사용량 제한을 담당합니다."""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
        self.max_input_chars = self._read_int_env("CHATBOT_MAX_INPUT_CHARS", 2000)
        self.max_output_tokens = self._read_int_env("CHATBOT_MAX_OUTPUT_TOKENS", 1024)
        self.max_history_messages = self._read_int_env("CHATBOT_MAX_HISTORY_MESSAGES", 16)
        self.max_tool_calls = self._read_int_env("CHATBOT_MAX_TOOL_CALLS", 3)
        self.daily_request_limit = self._read_int_env("CHATBOT_DAILY_REQUEST_LIMIT", 500)
        self.daily_token_limit = self._read_int_env("CHATBOT_DAILY_TOKEN_LIMIT", 50000)
        self.timeout_seconds = self._read_int_env("CHATBOT_OPENAI_TIMEOUT_SECONDS", 30)

    @staticmethod
    def _read_int_env(name: str, default: int) -> int:
        try:
            value = int(os.getenv(name, default))
            return value if value > 0 else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(text or "") // 4)

    def _consume_shared_usage(self, auth_header: str | None, user_id: str | None, estimated_tokens: int) -> None:
        if not auth_header or not user_id:
            raise ChatbotLimitError("로그인 사용자만 챗봇 사용량을 확인할 수 있습니다.")

        try:
            result = query_supabase(
                auth_header,
                "rpc/consume_chatbot_usage",
                "POST",
                json_data={
                    "p_user_id": user_id,
                    "p_usage_date": date.today().isoformat(),
                    "p_request_increment": 1,
                    "p_token_increment": estimated_tokens,
                    "p_request_limit": self.daily_request_limit,
                    "p_token_limit": self.daily_token_limit,
                },
            )
        except Exception as error:
            raise ChatbotLimitError("챗봇 사용량 제한 저장소를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.") from error

        row = result[0] if isinstance(result, list) and result else result
        if not isinstance(row, dict) or not row.get("allowed"):
            raise ChatbotLimitError("챗봇 사용량 제한에 도달했습니다. 잠시 후 다시 시도해 주세요.")

    @staticmethod
    def _usage_int(value) -> int:
        try:
            parsed = int(value or 0)
            return parsed if parsed >= 0 else 0
        except (TypeError, ValueError):
            return 0

    def _normalize_usage(self, usage: dict | None) -> dict | None:
        if not isinstance(usage, dict):
            return None

        normalized = {
            "prompt_tokens": self._usage_int(usage.get("prompt_tokens")),
            "completion_tokens": self._usage_int(usage.get("completion_tokens")),
            "total_tokens": self._usage_int(usage.get("total_tokens")),
        }
        if normalized["total_tokens"] <= 0:
            return None
        return normalized

    def _record_actual_usage(
        self,
        *,
        auth_header: str | None,
        user_id: str | None,
        usage: dict | None,
        request_type: str,
        request_id: str | None = None,
    ) -> None:
        normalized = self._normalize_usage(usage)
        authenticated_user_id = str(user_id or "").strip()
        if not auth_header or not authenticated_user_id or not normalized:
            return
        try:
            token_user_id, _ = get_user_id_from_header(auth_header)
        except Exception:
            return
        if str(token_user_id).strip() != authenticated_user_id:
            return

        normalized_request_type = str(request_type or "chat_reply").strip() or "chat_reply"
        normalized_request_id = str(request_id or "").strip() or None
        payload = {
            "user_id": authenticated_user_id,
            "request_type": normalized_request_type,
            "model": self.model,
            **normalized,
        }
        if normalized_request_id:
            payload["request_id"] = normalized_request_id
        try:
            query_supabase_as_service_role(
                "chatbot_token_usage_logs",
                "POST",
                json_data=payload,
            )
        except Exception:
            safe_user_id = authenticated_user_id.replace("\r", "").replace("\n", "")[:128]
            safe_request_id = (normalized_request_id or "-").replace("\r", "").replace("\n", "")[:128]
            logger.warning(
                "챗봇 실제 토큰 사용량 저장 실패: request_type=%s user_id=%s request_id=%s",
                normalized_request_type,
                safe_user_id,
                safe_request_id,
            )
            return

    def _to_openai_tools(self, function_schemas: list[dict] | None) -> list[dict]:
        tools = []
        for schema in (function_schemas or []):
            tools.append({
                "type": "function",
                "function": schema,
            })
        return tools

    def _build_request_payload(
        self,
        *,
        system_prompt: str,
        user_message: str,
        user_id: str | None,
        auth_header: str | None,
        function_schemas: list[dict] | None,
        history: list[dict] | None,
    ) -> dict:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

        text = str(user_message or "").strip()
        if len(text) > self.max_input_chars:
            raise ChatbotLimitError(f"입력은 최대 {self.max_input_chars}자까지 가능합니다.")

        estimated_tokens = (
            self._estimate_tokens(system_prompt)
            + self._estimate_tokens(text)
            + self.max_output_tokens
        )
        self._consume_shared_usage(auth_header, user_id, estimated_tokens)

        history_messages = []
        for item in history or []:
            role = item.get("role")
            content = str(item.get("content") or "").strip()
            if role in {"user", "assistant"} and content:
                history_messages.append({"role": role, "content": content})

        messages = [
            {"role": "system", "content": system_prompt},
            *history_messages,
            {"role": "user", "content": text},
        ]
        if len(messages) > self.max_history_messages + 1:
            messages = [messages[0], *messages[-self.max_history_messages:]]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": self.max_output_tokens,
        }
        tools = self._to_openai_tools(function_schemas)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    def generate_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        user_id: str | None = None,
        auth_header: str | None = None,
        function_schemas: list[dict] | None = None,
        history: list[dict] | None = None,
        request_id: str | None = None,
    ) -> dict:
        payload = self._build_request_payload(
            system_prompt=system_prompt,
            user_message=user_message,
            user_id=user_id,
            auth_header=auth_header,
            function_schemas=function_schemas,
            history=history,
        )

        response = requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI 챗봇 요청 실패: HTTP {response.status_code}")

        data = response.json()
        usage = data.get("usage") or {}
        message = (data.get("choices") or [{}])[0].get("message") or {}
        content = (message.get("content") or "").strip()
        tool_calls = message.get("tool_calls") or []

        if not content:
            content = "응답을 만들지 못했습니다. 잠시 후 다시 시도해 주세요."

        self._record_actual_usage(
            auth_header=auth_header,
            user_id=user_id,
            usage=usage,
            request_type="chat_reply",
            request_id=request_id,
        )

        return {
            "reply": content,
            "usage": usage,
            "tool_calls": tool_calls[: self.max_tool_calls],
            "model": self.model,
        }

    @staticmethod
    def _redact_tool_data(value):
        if isinstance(value, dict):
            redacted = {}
            for key, item in value.items():
                key_text = str(key).lower()
                if any(marker in key_text for marker in ["secret", "token", "api_key", "apikey", "account", "password"]):
                    redacted[key] = "[REDACTED]"
                else:
                    redacted[key] = ChatbotLLMClient._redact_tool_data(item)
            return redacted
        if isinstance(value, list):
            return [ChatbotLLMClient._redact_tool_data(item) for item in value]
        return value

    def synthesize_tool_result_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tool_name: str | None,
        tool_reply: str,
        tool_data: dict | None,
        user_id: str | None = None,
        auth_header: str | None = None,
        request_id: str | None = None,
    ) -> dict:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다.")

        safe_tool_data = self._redact_tool_data(tool_data if isinstance(tool_data, dict) else {})
        serialized_tool_data = json.dumps(safe_tool_data, ensure_ascii=False, default=str)
        max_tool_data_chars = min(6000, max(1000, self.max_input_chars * 3))
        if len(serialized_tool_data) > max_tool_data_chars:
            serialized_tool_data = f"{serialized_tool_data[:max_tool_data_chars]}\n...[TRUNCATED]"

        messages = [
            {
                "role": "system",
                "content": "\n".join([
                    system_prompt,
                    "도구 실행 결과를 바탕으로 최종 답변을 재작성합니다.",
                    "반드시 한국어로 답변하세요.",
                    "제공된 도구 결과에 없는 사실을 추가하지 마세요.",
                    "간결하고 사용자가 바로 행동할 수 있게 답변하세요.",
                    "투자 판단에는 손실 가능성과 사용자의 최종 확인이 필요하다는 안전 문맥을 유지하세요.",
                ]),
            },
            {
                "role": "user",
                "content": "\n".join([
                    f"사용자 질문: {str(user_message or '').strip()}",
                    f"도구 이름: {str(tool_name or '').strip() or 'unknown'}",
                    f"도구 기본 답변: {str(tool_reply or '').strip()}",
                    "도구 데이터:",
                    serialized_tool_data,
                ]),
            },
        ]
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": min(512, self.max_output_tokens),
        }

        response = requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI 챗봇 재합성 요청 실패: HTTP {response.status_code}")

        data = response.json()
        usage = data.get("usage") or {}
        message = (data.get("choices") or [{}])[0].get("message") or {}
        content = (message.get("content") or "").strip()
        if not content:
            raise RuntimeError("OpenAI 챗봇 재합성 응답이 비어 있습니다.")

        self._record_actual_usage(
            auth_header=auth_header,
            user_id=user_id,
            usage=usage,
            request_type="tool_synthesis",
            request_id=request_id,
        )

        return {
            "reply": content,
            "usage": usage,
            "model": self.model,
        }

    def stream_reply(
        self,
        *,
        system_prompt: str,
        user_message: str,
        user_id: str | None,
        auth_header: str | None,
        function_schemas: list[dict] | None,
        history: list[dict] | None,
        on_delta: Callable[[str], None],
        request_id: str | None = None,
    ) -> dict:
        payload = {
            **self._build_request_payload(
                system_prompt=system_prompt,
                user_message=user_message,
                user_id=user_id,
                auth_header=auth_header,
                function_schemas=function_schemas,
                history=history,
            ),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        response = requests.post(
            OPENAI_CHAT_COMPLETIONS_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.timeout_seconds,
            stream=True,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI 챗봇 요청 실패: HTTP {response.status_code}")

        reply_parts = []
        usage = {}
        tool_call_deltas: dict[int, dict] = {}
        response_mode = None
        saw_done = False

        for raw_line in response.iter_lines(decode_unicode=True):
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", errors="replace")
            else:
                line = str(raw_line or "")
            if not line.startswith("data:"):
                continue

            event_data = line[5:].strip()
            if event_data == "[DONE]":
                saw_done = True
                break
            if not event_data:
                continue

            try:
                chunk = json.loads(event_data)
            except (TypeError, ValueError) as error:
                raise RuntimeError("OpenAI 챗봇 스트림 응답을 해석하지 못했습니다.") from error
            if not isinstance(chunk, dict):
                raise RuntimeError("OpenAI 챗봇 스트림 응답을 해석하지 못했습니다.")
            if chunk.get("error"):
                raise RuntimeError("OpenAI 챗봇 스트림 처리에 실패했습니다.")

            chunk_usage = chunk.get("usage")
            if isinstance(chunk_usage, dict):
                usage = chunk_usage

            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            tool_call_chunks = delta.get("tool_calls") or []
            if response_mode is None:
                if tool_call_chunks:
                    response_mode = "tool"
                elif isinstance(content, str) and content:
                    response_mode = "text"

            if response_mode == "text" and isinstance(content, str) and content:
                reply_parts.append(content)
                on_delta(content)

            if response_mode != "tool":
                continue
            for tool_call_delta in tool_call_chunks:
                index = tool_call_delta.get("index")
                if not isinstance(index, int):
                    index = len(tool_call_deltas)
                current = tool_call_deltas.setdefault(
                    index,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                call_id = tool_call_delta.get("id")
                if isinstance(call_id, str):
                    current["id"] += call_id
                call_type = tool_call_delta.get("type")
                if isinstance(call_type, str) and call_type:
                    current["type"] = call_type

                function_delta = tool_call_delta.get("function") or {}
                function_name = function_delta.get("name")
                if isinstance(function_name, str):
                    current["function"]["name"] += function_name
                arguments = function_delta.get("arguments")
                if isinstance(arguments, str):
                    current["function"]["arguments"] += arguments

        if not saw_done:
            raise RuntimeError("OpenAI 챗봇 스트림이 비정상 종료되었습니다.")

        reply_text = "".join(reply_parts)
        if not reply_text:
            reply_text = "응답을 만들지 못했습니다. 잠시 후 다시 시도해 주세요."

        tool_calls = [tool_call_deltas[index] for index in sorted(tool_call_deltas)]
        self._record_actual_usage(
            auth_header=auth_header,
            user_id=user_id,
            usage=usage,
            request_type="chat_stream",
            request_id=request_id,
        )
        return {
            "reply": reply_text,
            "usage": usage,
            "tool_calls": tool_calls[: self.max_tool_calls],
            "model": self.model,
        }
