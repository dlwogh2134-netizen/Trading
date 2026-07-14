import pytest
from flask import Flask

from backend.routes import admin_users


@pytest.fixture
def client():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(admin_users.admin_users_bp)
    return app.test_client()


def test_list_admin_users_requires_admin(monkeypatch, client):
    monkeypatch.setattr(
        admin_users,
        "_verify_admin",
        lambda auth_header: (_ for _ in ()).throw(PermissionError("관리자 권한이 필요합니다.")),
    )

    response = client.get("/api/admin/users", headers={"Authorization": "Bearer user"})

    assert response.status_code == 403
    payload = response.get_json()
    assert payload["success"] is False
    assert "error" in payload


def test_list_admin_users_uses_database_rpc_for_aggregation_sorting_and_pagination(monkeypatch, client):
    calls = []
    rpc_payload = {
        "data": [
            {
                "id": "user-1",
                "email": "a@example.com",
                "nickname": "alpha",
                "role": "USER",
                "updatedAt": "2026-07-14T00:00:00+00:00",
                "usage": {
                    "todayTokens": 15,
                    "tokens7d": 15,
                    "tokens30d": 45,
                    "totalTokens": 45,
                    "todayRequests": 1,
                    "requests30d": 2,
                    "recentUsedAt": "2026-07-14T01:00:00+00:00",
                },
            },
        ],
        "summary": {
            "totalUsers": 3,
            "todayTokens": 25,
            "tokens30d": 55,
            "activeUsers24h": 2,
        },
    }

    monkeypatch.setattr(admin_users, "_verify_admin", lambda auth_header: {"id": "admin-1"})

    def fake_request(endpoint, method="GET", params=None, json_data=None, extra_headers=None):
        calls.append({
            "endpoint": endpoint,
            "method": method,
            "params": params,
            "json_data": json_data,
        })
        assert endpoint != "profiles"
        assert endpoint != "chatbot_token_usage_logs"
        return rpc_payload

    monkeypatch.setattr(admin_users, "_supabase_request", fake_request)

    response = client.get(
        "/api/admin/users?q=alpha&sort=total_tokens&order=asc&limit=25&offset=50",
        headers={"Authorization": "Bearer admin"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, **rpc_payload}
    assert calls == [{
        "endpoint": "rpc/admin_list_user_token_usage",
        "method": "POST",
        "params": None,
        "json_data": {
            "p_query": "alpha",
            "p_sort": "total_tokens",
            "p_order": "asc",
            "p_limit": 25,
            "p_offset": 50,
        },
    }]


def test_list_admin_users_uses_default_sort_for_unknown_value(monkeypatch, client):
    calls = []
    monkeypatch.setattr(admin_users, "_verify_admin", lambda auth_header: {"id": "admin-1"})
    monkeypatch.setattr(
        admin_users,
        "_supabase_request",
        lambda endpoint, method="GET", params=None, json_data=None, extra_headers=None: (
            calls.append(json_data) or {"data": [], "summary": {}}
        ),
    )

    response = client.get("/api/admin/users?sort=unknown", headers={"Authorization": "Bearer admin"})

    assert response.status_code == 200
    assert calls[0]["p_sort"] == "tokens_30d"


def test_list_admin_users_rejects_invalid_limit(monkeypatch, client):
    monkeypatch.setattr(admin_users, "_verify_admin", lambda auth_header: {"id": "admin-1"})

    response = client.get("/api/admin/users?limit=x", headers={"Authorization": "Bearer admin"})

    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_get_admin_user_chatbot_usage_uses_database_rpc(monkeypatch, client):
    calls = []
    rpc_payload = {
        "user": {
            "id": "user-1",
            "email": "a@example.com",
            "nickname": "alpha",
            "role": "USER",
            "updatedAt": "2026-07-14T00:00:00+00:00",
        },
        "daily": [{
            "date": "2026-07-14",
            "promptTokens": 10,
            "completionTokens": 5,
            "totalTokens": 15,
            "requestCount": 1,
        }],
        "byRequestType": {
            "tool_synthesis": {
                "promptTokens": 20,
                "completionTokens": 10,
                "totalTokens": 30,
                "requestCount": 1,
            },
        },
        "recentLogs": [{
            "createdAt": "2026-07-14T01:00:00+00:00",
            "requestType": "chat_reply",
            "model": "gpt-test",
            "promptTokens": 10,
            "completionTokens": 5,
            "totalTokens": 15,
        }],
    }

    monkeypatch.setattr(admin_users, "_verify_admin", lambda auth_header: {"id": "admin-1"})

    def fake_request(endpoint, method="GET", params=None, json_data=None, extra_headers=None):
        calls.append({"endpoint": endpoint, "method": method, "json_data": json_data})
        assert endpoint != "profiles"
        assert endpoint != "chatbot_token_usage_logs"
        return rpc_payload

    monkeypatch.setattr(admin_users, "_supabase_request", fake_request)

    response = client.get(
        "/api/admin/users/user-1/chatbot-usage?days=45&limit=20",
        headers={"Authorization": "Bearer admin"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, **rpc_payload}
    assert calls == [{
        "endpoint": "rpc/admin_get_user_token_usage",
        "method": "POST",
        "json_data": {
            "p_user_id": "user-1",
            "p_days": 45,
            "p_limit": 20,
        },
    }]


def test_get_admin_user_chatbot_usage_returns_not_found_from_rpc(monkeypatch, client):
    monkeypatch.setattr(admin_users, "_verify_admin", lambda auth_header: {"id": "admin-1"})
    monkeypatch.setattr(admin_users, "_supabase_request", lambda *args, **kwargs: None)

    response = client.get(
        "/api/admin/users/missing/chatbot-usage",
        headers={"Authorization": "Bearer admin"},
    )

    assert response.status_code == 404
    assert response.get_json()["success"] is False
