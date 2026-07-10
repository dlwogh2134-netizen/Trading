from datetime import UTC, datetime, timedelta

from backend.services.supabase_client import query_supabase


class ChatbotConversationRepository:
    def load_recent_history(
        self,
        auth_header: str,
        user_id: str,
        limit: int = 12,
    ) -> list[dict]:
        rows = query_supabase(
            auth_header,
            "chat_history",
            "GET",
            params={
                "user_id": f"eq.{user_id}",
                "select": "role,message,created_at,id",
                "order": "created_at.desc,id.desc",
                "limit": str(max(1, min(limit, 50))),
            },
        ) or []
        history = []
        for row in reversed(rows):
            role = str((row or {}).get("role") or "").strip()
            message = str((row or {}).get("message") or "").strip()
            if role in {"user", "assistant"} and message:
                history.append({"role": role, "content": message})
        return history

    def record_exchange(
        self,
        auth_header: str,
        user_id: str,
        user_message: str,
        assistant_message: str,
    ) -> None:
        query_supabase(
            auth_header,
            "chat_history",
            "POST",
            json_data=[
                {"user_id": user_id, "role": "user", "message": user_message.strip()},
                {"user_id": user_id, "role": "assistant", "message": assistant_message.strip()},
            ],
        )

    def set_pending_action(
        self,
        auth_header: str,
        user_id: str,
        action: str,
        payload: dict | None = None,
        ttl_seconds: int = 300,
    ) -> None:
        self._patch_or_insert_state(
            auth_header,
            user_id,
            {
                "pending_action": action,
                "pending_payload": payload or {},
                "pending_expires_at": (
                    datetime.now(UTC) + timedelta(seconds=ttl_seconds)
                ).isoformat(),
            },
        )

    def consume_pending_action(
        self,
        auth_header: str,
        user_id: str,
        now: datetime | None = None,
    ) -> tuple[str | None, dict]:
        state = self._load_state(auth_header, user_id)
        action = str(state.get("pending_action") or "").strip()
        raw_expires_at = state.get("pending_expires_at")
        expires_at = self._parse_datetime(raw_expires_at)
        if not action or not self._is_unexpired(expires_at, now):
            return None, {}

        payload = state.get("pending_payload")
        normalized_payload = payload if isinstance(payload, dict) else {}
        claimed_rows = query_supabase(
            auth_header,
            "chatbot_conversation_states",
            "PATCH",
            json_data={
                "pending_action": None,
                "pending_payload": {},
                "pending_expires_at": None,
            },
            params={
                "user_id": f"eq.{user_id}",
                "pending_action": f"eq.{action}",
                "pending_expires_at": f"eq.{raw_expires_at}",
            },
            extra_headers={"Prefer": "return=representation"},
        ) or []
        if not claimed_rows:
            return None, {}
        return action, normalized_payload

    def peek_pending_action(
        self,
        auth_header: str,
        user_id: str,
        now: datetime | None = None,
    ) -> str | None:
        state = self._load_state(auth_header, user_id)
        action = str(state.get("pending_action") or "").strip()
        expires_at = self._parse_datetime(state.get("pending_expires_at"))
        if not action or not self._is_unexpired(expires_at, now):
            return None
        return action

    def store_recommendations(
        self,
        auth_header: str,
        user_id: str,
        items: list[dict],
        source: str | None,
        ttl_seconds: int = 600,
    ) -> None:
        self._patch_or_insert_state(
            auth_header,
            user_id,
            {
                "recommendation_items": items,
                "recommendation_source": source,
                "recommendation_expires_at": (
                    datetime.now(UTC) + timedelta(seconds=ttl_seconds)
                ).isoformat(),
            },
        )

    def load_recommendations(
        self,
        auth_header: str,
        user_id: str,
        now: datetime | None = None,
    ) -> list[dict]:
        state = self._load_state(auth_header, user_id)
        expires_at = self._parse_datetime(state.get("recommendation_expires_at"))
        if not self._is_unexpired(expires_at, now):
            return []

        items = state.get("recommendation_items")
        return items if isinstance(items, list) else []

    def _load_state(self, auth_header: str, user_id: str) -> dict:
        rows = query_supabase(
            auth_header,
            "chatbot_conversation_states",
            "GET",
            params={
                "user_id": f"eq.{user_id}",
                "select": (
                    "user_id,pending_action,pending_payload,pending_expires_at,"
                    "recommendation_items,recommendation_source,recommendation_expires_at"
                ),
                "limit": "1",
            },
        ) or []
        return rows[0] if rows and isinstance(rows[0], dict) else {}

    def _patch_or_insert_state(
        self,
        auth_header: str,
        user_id: str,
        updates: dict,
    ) -> None:
        existing = query_supabase(
            auth_header,
            "chatbot_conversation_states",
            "GET",
            params={
                "user_id": f"eq.{user_id}",
                "select": "user_id",
                "limit": "1",
            },
        ) or []
        if existing:
            self._patch_state(auth_header, user_id, updates)
            return

        try:
            query_supabase(
                auth_header,
                "chatbot_conversation_states",
                "POST",
                json_data={"user_id": user_id, **updates},
            )
        except Exception as error:
            if not self._is_unique_violation(error):
                raise
            self._patch_state(auth_header, user_id, updates)

    @staticmethod
    def _is_unique_violation(error: Exception) -> bool:
        message = str(error).lower()
        return "23505" in message or (
            "duplicate key" in message and "unique" in message
        )

    @staticmethod
    def _patch_state(
        auth_header: str,
        user_id: str,
        updates: dict,
    ) -> None:
        updated_rows = query_supabase(
            auth_header,
            "chatbot_conversation_states",
            "PATCH",
            json_data=updates,
            params={"user_id": f"eq.{user_id}"},
            extra_headers={"Prefer": "return=representation"},
        )
        if (
            not isinstance(updated_rows, list)
            or len(updated_rows) != 1
            or not isinstance(updated_rows[0], dict)
        ):
            raise RuntimeError("챗봇 대화 상태는 정확히 1행 갱신되어야 합니다.")

    @staticmethod
    def _is_unexpired(expires_at: datetime | None, now: datetime | None) -> bool:
        if expires_at is None:
            return False
        current_time = now or datetime.now(UTC)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=UTC)
        return expires_at > current_time

    @staticmethod
    def _parse_datetime(value: object) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
