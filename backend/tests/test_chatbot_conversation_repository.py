from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock

import pytest

from backend.services import supabase_client
from backend.services.chatbot.conversation_repository import ChatbotConversationRepository


class FakeConversationStateBoundary:
    def __init__(
        self,
        insert_conflict_once: bool = False,
        insert_error: Exception | None = None,
        conflict_row_disappears: bool = False,
        existing_row_disappears_before_patch: bool = False,
    ):
        self.rows = {}
        self.insert_conflict_once = insert_conflict_once
        self.insert_error = insert_error
        self.conflict_row_disappears = conflict_row_disappears
        self.existing_row_disappears_before_patch = existing_row_disappears_before_patch

    def query(
        self,
        auth_header,
        endpoint,
        method="GET",
        json_data=None,
        params=None,
        extra_headers=None,
    ):
        assert endpoint == "chatbot_conversation_states"
        params = params or {}
        user_id = str(params.get("user_id") or "").removeprefix("eq.")

        if method == "GET":
            row = self.rows.get(user_id)
            return [dict(row)] if row else []
        if method == "POST":
            payload = dict(json_data or {})
            user_id = str(payload.get("user_id") or "")
            if self.insert_conflict_once:
                self.insert_conflict_once = False
                if not self.conflict_row_disappears:
                    self.rows[user_id] = {"user_id": user_id}
                raise RuntimeError("23505 duplicate key value violates unique constraint")
            if self.insert_error:
                raise self.insert_error
            self.rows[user_id] = payload
            return [dict(payload)]
        if method == "PATCH":
            if self.existing_row_disappears_before_patch:
                self.existing_row_disappears_before_patch = False
                self.rows.pop(user_id, None)
            row = self.rows.get(user_id)
            if not row:
                return []
            expected_action = params.get("pending_action")
            expected_expires_at = params.get("pending_expires_at")
            if expected_action and expected_action != f"eq.{row.get('pending_action')}":
                return []
            if expected_expires_at and expected_expires_at != f"eq.{row.get('pending_expires_at')}":
                return []
            row.update(json_data or {})
            if (extra_headers or {}).get("Prefer") == "return=representation":
                return [dict(row)]
            return None
        raise AssertionError(f"지원하지 않는 메서드: {method}")


class ConcurrentConsumeBoundary:
    def __init__(self):
        expires_at = (datetime.now(UTC) + timedelta(minutes=5)).isoformat()
        self.row = {
            "user_id": "user-1",
            "pending_action": "portfolio_summary",
            "pending_payload": {"exchange": "TOSS"},
            "pending_expires_at": expires_at,
            "recommendation_items": [],
            "recommendation_source": None,
            "recommendation_expires_at": None,
        }
        self.read_barrier = Barrier(2)
        self.lock = Lock()

    def query(
        self,
        auth_header,
        endpoint,
        method="GET",
        json_data=None,
        params=None,
        extra_headers=None,
    ):
        assert endpoint == "chatbot_conversation_states"
        params = params or {}
        if method == "GET":
            with self.lock:
                snapshot = dict(self.row)
            self.read_barrier.wait(timeout=5)
            return [snapshot]
        if method == "PATCH":
            with self.lock:
                expected_action = params.get("pending_action")
                expected_expires_at = params.get("pending_expires_at")
                if expected_action and expected_action != f"eq.{self.row.get('pending_action')}":
                    return []
                if expected_expires_at and expected_expires_at != f"eq.{self.row.get('pending_expires_at')}":
                    return []
                self.row.update(json_data or {})
                if (extra_headers or {}).get("Prefer") == "return=representation":
                    return [dict(self.row)]
                return None
        raise AssertionError(f"지원하지 않는 메서드: {method}")


class ReplacedPendingStateBoundary(FakeConversationStateBoundary):
    def __init__(self):
        super().__init__()
        self.replaced = False

    def query(
        self,
        auth_header,
        endpoint,
        method="GET",
        json_data=None,
        params=None,
        extra_headers=None,
    ):
        if method == "PATCH" and not self.replaced:
            self.replaced = True
            self.rows["user-1"] = {
                "user_id": "user-1",
                "pending_action": "new_action",
                "pending_payload": {"version": 2},
                "pending_expires_at": (
                    datetime.now(UTC) + timedelta(minutes=10)
                ).isoformat(),
            }
        return super().query(
            auth_header,
            endpoint,
            method,
            json_data,
            params,
            extra_headers,
        )


class FakeChatHistoryBoundary:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def query(self, auth_header, endpoint, method="GET", json_data=None, params=None):
        assert endpoint == "chat_history"
        params = params or {}
        user_id = str(params.get("user_id") or "").removeprefix("eq.")
        rows = [row for row in self.rows if row.get("user_id") == user_id]
        if params.get("order") == "created_at.desc,id.desc":
            rows.sort(
                key=lambda row: (row.get("created_at") or "", row.get("id") or 0),
                reverse=True,
            )
        limit = int(params.get("limit") or len(rows))
        return rows[:limit]


def test_query_supabase_merges_optional_response_headers(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "[]"

        @staticmethod
        def json():
            return []

    def fake_patch(url, headers, json, params):
        captured.update({
            "url": url,
            "headers": headers,
            "json": json,
            "params": params,
        })
        return FakeResponse()

    monkeypatch.setattr(
        supabase_client,
        "get_user_id_from_header",
        lambda auth_header: ("user-1", "token-1"),
    )
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_client, "SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(supabase_client.requests, "patch", fake_patch)

    result = supabase_client.query_supabase(
        "Bearer test",
        "chatbot_conversation_states",
        "PATCH",
        json_data={"pending_action": None},
        params={"user_id": "eq.user-1"},
        extra_headers={"pReFeR": "return=representation"},
    )

    assert result == []
    assert captured["headers"] == {
        "apikey": "anon-key",
        "Authorization": "Bearer token-1",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


@pytest.mark.parametrize(
    "header_name",
    ["authorization", "APIKEY", "content-Type", "X-Trace"],
)
def test_query_supabase_rejects_headers_other_than_prefer(monkeypatch, header_name):
    class FakeResponse:
        status_code = 200
        text = "[]"

        @staticmethod
        def json():
            return []

    monkeypatch.setattr(
        supabase_client,
        "get_user_id_from_header",
        lambda auth_header: ("user-1", "token-1"),
    )
    monkeypatch.setattr(supabase_client, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(supabase_client, "SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(
        supabase_client.requests,
        "patch",
        lambda *args, **kwargs: FakeResponse(),
    )

    with pytest.raises(ValueError, match="Prefer"):
        supabase_client.query_supabase(
            "Bearer test",
            "chatbot_conversation_states",
            "PATCH",
            json_data={"pending_action": None},
            params={"user_id": "eq.user-1"},
            extra_headers={header_name: "attacker-controlled"},
        )


def test_load_recent_history_reads_supabase_on_every_request(monkeypatch):
    calls = []

    def fake_query(auth_header, endpoint, method="GET", json_data=None, params=None):
        calls.append((endpoint, method, params))
        return [
            {"id": 2, "role": "assistant", "message": "두 번째", "created_at": "2026-07-10T01:00:02Z"},
            {"id": 1, "role": "user", "message": "첫 번째", "created_at": "2026-07-10T01:00:01Z"},
        ]

    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        fake_query,
    )
    repository = ChatbotConversationRepository()

    first = repository.load_recent_history("Bearer test", "user-1")
    second = repository.load_recent_history("Bearer test", "user-1")

    assert first == [
        {"role": "user", "content": "첫 번째"},
        {"role": "assistant", "content": "두 번째"},
    ]
    assert second == first
    assert len(calls) == 2


def test_load_recent_history_enforces_user_order_and_limit_contract(monkeypatch):
    rows = [
        {
            "id": index,
            "user_id": "user-1",
            "role": "user",
            "message": f"질문-{index}",
            "created_at": "2026-07-10T01:00:00Z",
        }
        for index in range(1, 56)
    ]
    rows.append({
        "id": 999,
        "user_id": "user-2",
        "role": "assistant",
        "message": "다른 사용자 대화",
        "created_at": "2026-07-10T02:00:00Z",
    })
    boundary = FakeChatHistoryBoundary(rows)
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )

    history = ChatbotConversationRepository().load_recent_history(
        "Bearer test",
        "user-1",
        limit=100,
    )

    assert len(history) == 50
    assert history[0] == {"role": "user", "content": "질문-6"}
    assert history[-1] == {"role": "user", "content": "질문-55"}
    assert all(item["content"] != "다른 사용자 대화" for item in history)


def test_expired_recommendations_are_not_reused(monkeypatch):
    expired_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        lambda *args, **kwargs: [{
            "user_id": "user-1",
            "recommendation_items": [{"symbol": "DOGE"}],
            "recommendation_expires_at": expired_at,
        }],
    )

    result = ChatbotConversationRepository().load_recommendations(
        "Bearer test",
        "user-1",
        now=datetime.now(UTC),
    )

    assert result == []


def test_recorded_exchange_is_visible_to_another_repository_instance(monkeypatch):
    rows = []

    def fake_query(auth_header, endpoint, method="GET", json_data=None, params=None):
        assert endpoint == "chat_history"
        if method == "POST":
            for row in json_data:
                rows.append({
                    **row,
                    "id": len(rows) + 1,
                    "created_at": f"2026-07-10T01:00:0{len(rows) + 1}Z",
                })
            return list(rows)
        return list(reversed(rows))

    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        fake_query,
    )

    ChatbotConversationRepository().record_exchange(
        "Bearer test",
        "user-1",
        " 첫 질문 ",
        " 첫 답변 ",
    )
    history = ChatbotConversationRepository().load_recent_history(
        "Bearer test",
        "user-1",
    )

    assert history == [
        {"role": "user", "content": "첫 질문"},
        {"role": "assistant", "content": "첫 답변"},
    ]


def test_pending_action_is_consumed_across_repository_instances(monkeypatch):
    boundary = FakeConversationStateBoundary()
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )
    writer = ChatbotConversationRepository()
    reader = ChatbotConversationRepository()

    writer.set_pending_action(
        "Bearer test",
        "user-1",
        "portfolio_summary",
        {"exchange": "TOSS"},
    )

    assert reader.peek_pending_action("Bearer test", "user-1") == "portfolio_summary"
    assert reader.consume_pending_action("Bearer test", "user-1") == (
        "portfolio_summary",
        {"exchange": "TOSS"},
    )
    assert writer.peek_pending_action("Bearer test", "user-1") is None


def test_expired_pending_action_is_not_consumed(monkeypatch):
    expired_at = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    boundary = FakeConversationStateBoundary()
    boundary.rows["user-1"] = {
        "user_id": "user-1",
        "pending_action": "portfolio_summary",
        "pending_payload": {"exchange": "TOSS"},
        "pending_expires_at": expired_at,
    }
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )
    repository = ChatbotConversationRepository()

    assert repository.peek_pending_action("Bearer test", "user-1") is None
    assert repository.consume_pending_action("Bearer test", "user-1") == (None, {})


def test_state_insert_race_recovers_by_patching_existing_row(monkeypatch):
    boundary = FakeConversationStateBoundary(insert_conflict_once=True)
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )
    repository = ChatbotConversationRepository()

    repository.set_pending_action(
        "Bearer test",
        "user-1",
        "portfolio_summary",
    )

    assert repository.peek_pending_action("Bearer test", "user-1") == "portfolio_summary"


def test_unique_conflict_with_missing_competing_row_raises(monkeypatch):
    boundary = FakeConversationStateBoundary(
        insert_conflict_once=True,
        conflict_row_disappears=True,
    )
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )

    with pytest.raises(RuntimeError, match="1행"):
        ChatbotConversationRepository().set_pending_action(
            "Bearer test",
            "user-1",
            "portfolio_summary",
        )


def test_existing_state_patch_requires_exactly_one_updated_row(monkeypatch):
    boundary = FakeConversationStateBoundary(
        existing_row_disappears_before_patch=True,
    )
    boundary.rows["user-1"] = {"user_id": "user-1"}
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )

    with pytest.raises(RuntimeError, match="1행"):
        ChatbotConversationRepository().set_pending_action(
            "Bearer test",
            "user-1",
            "portfolio_summary",
        )


def test_existing_state_patch_rejects_malformed_update_result(monkeypatch):
    def fake_query(
        auth_header,
        endpoint,
        method="GET",
        json_data=None,
        params=None,
        extra_headers=None,
    ):
        assert endpoint == "chatbot_conversation_states"
        if method == "GET":
            return [{"user_id": "user-1"}]
        if method == "PATCH":
            return {"user_id": "user-1"}
        raise AssertionError(f"지원하지 않는 메서드: {method}")

    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        fake_query,
    )

    with pytest.raises(RuntimeError, match="1행"):
        ChatbotConversationRepository().set_pending_action(
            "Bearer test",
            "user-1",
            "portfolio_summary",
        )


def test_state_insert_non_unique_error_is_propagated(monkeypatch):
    insert_error = RuntimeError("Supabase REST API 에러 (401): permission denied")
    boundary = FakeConversationStateBoundary(insert_error=insert_error)
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )

    with pytest.raises(RuntimeError) as raised:
        ChatbotConversationRepository().set_pending_action(
            "Bearer test",
            "user-1",
            "portfolio_summary",
        )

    assert raised.value is insert_error
    assert boundary.rows == {}


def test_pending_action_is_claimed_by_exactly_one_concurrent_consumer(monkeypatch):
    boundary = ConcurrentConsumeBoundary()
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )
    repositories = [ChatbotConversationRepository(), ChatbotConversationRepository()]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(
            lambda repository: repository.consume_pending_action(
                "Bearer test",
                "user-1",
            ),
            repositories,
        ))

    assert sum(action == "portfolio_summary" for action, _ in results) == 1
    assert sum(result == (None, {}) for result in results) == 1


def test_consume_does_not_clear_a_replaced_pending_action(monkeypatch):
    boundary = ReplacedPendingStateBoundary()
    boundary.rows["user-1"] = {
        "user_id": "user-1",
        "pending_action": "old_action",
        "pending_payload": {"version": 1},
        "pending_expires_at": (
            datetime.now(UTC) + timedelta(minutes=5)
        ).isoformat(),
    }
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )
    repository = ChatbotConversationRepository()

    result = repository.consume_pending_action("Bearer test", "user-1")

    assert result == (None, {})
    assert repository.peek_pending_action("Bearer test", "user-1") == "new_action"


def test_recommendations_are_shared_across_repository_instances(monkeypatch):
    boundary = FakeConversationStateBoundary()
    monkeypatch.setattr(
        "backend.services.chatbot.conversation_repository.query_supabase",
        boundary.query,
    )
    items = [{"symbol": "005930"}, {"symbol": "000660"}]

    ChatbotConversationRepository().store_recommendations(
        "Bearer test",
        "user-1",
        items,
        "ML_ACTIVE_SIGNAL",
    )
    loaded = ChatbotConversationRepository().load_recommendations(
        "Bearer test",
        "user-1",
    )

    assert loaded == items
