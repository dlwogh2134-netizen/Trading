import os

import requests
from flask import Blueprint, jsonify, request

from backend.services.error_message_service import format_error_payload


admin_users_bp = Blueprint("admin_users", __name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

ALLOWED_SORTS = {
    "today_tokens",
    "tokens_7d",
    "tokens_30d",
    "total_tokens",
    "recent_used_at",
    "created_at",
}


class InvalidQueryParameter(ValueError):
    pass


def _json_error(error, title, status_code):
    payload = format_error_payload(error, title)
    return jsonify(payload), status_code


def _extract_bearer_token(auth_header):
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("로그인이 필요합니다.")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise ValueError("로그인이 필요합니다.")
    return token


def _require_supabase_config():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase 관리자 조회 환경변수가 설정되어 있지 않습니다.")


def _service_headers(extra_headers=None):
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def _supabase_request(endpoint, method="GET", params=None, json_data=None, extra_headers=None):
    _require_supabase_config()
    response = requests.request(
        method,
        f"{SUPABASE_URL}/rest/v1/{endpoint}",
        headers=_service_headers(extra_headers),
        params=params,
        json=json_data,
        timeout=15,
    )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(f"Supabase 관리자 조회에 실패했습니다. HTTP {response.status_code}")
    if not response.text:
        return None
    return response.json()


def _verify_admin(auth_header):
    _require_supabase_config()
    token = _extract_bearer_token(auth_header)
    user_response = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if user_response.status_code != 200:
        raise PermissionError("유효한 로그인이 필요합니다.")
    user = user_response.json() or {}
    user_id = user.get("id")
    if not user_id:
        raise PermissionError("유효한 로그인이 필요합니다.")
    rows = _supabase_request(
        "profiles",
        params={"select": "id,email,nickname,role", "id": f"eq.{user_id}", "limit": "1"},
    ) or []
    profile = rows[0] if rows else {}
    if profile.get("role") != "ADMIN":
        raise PermissionError("관리자 권한이 필요합니다.")
    return {"id": user_id, "email": user.get("email") or profile.get("email"), "profile": profile}


def _bounded_query_int(value, default, minimum, maximum, name):
    if value is None or value == "":
        return default
    try:
        return min(max(int(value), minimum), maximum)
    except (TypeError, ValueError) as error:
        raise InvalidQueryParameter(f"{name} 값은 숫자여야 합니다.") from error


@admin_users_bp.route("/api/admin/users", methods=["GET"])
def list_admin_users():
    try:
        _verify_admin(request.headers.get("Authorization"))
        query = str(request.args.get("q") or "").strip()
        sort = str(request.args.get("sort") or "tokens_30d")
        order = str(request.args.get("order") or "desc").lower()
        limit = _bounded_query_int(request.args.get("limit"), 50, 1, 200, "limit")
        offset = _bounded_query_int(request.args.get("offset"), 0, 0, 1000000, "offset")
        if sort not in ALLOWED_SORTS:
            sort = "tokens_30d"
        if order not in {"asc", "desc"}:
            order = "desc"

        result = _supabase_request(
            "rpc/admin_list_user_token_usage",
            method="POST",
            json_data={
                "p_query": query,
                "p_sort": sort,
                "p_order": order,
                "p_limit": limit,
                "p_offset": offset,
            },
        ) or {}
        if not isinstance(result, dict):
            raise RuntimeError("유저 사용량 집계 응답 형식이 올바르지 않습니다.")

        summary = result.get("summary") or {
            "totalUsers": 0,
            "todayTokens": 0,
            "tokens30d": 0,
            "activeUsers24h": 0,
        }
        return jsonify({"success": True, "data": result.get("data") or [], "summary": summary})
    except InvalidQueryParameter as error:
        return _json_error(error, "유저 관리 조회 실패", 400)
    except ValueError as error:
        return _json_error(error, "유저 관리 조회 실패", 401)
    except PermissionError as error:
        return _json_error(error, "유저 관리 권한 확인 실패", 403)
    except Exception as error:
        return _json_error(error, "유저 관리 조회 실패", 500)


@admin_users_bp.route("/api/admin/users/<user_id>/chatbot-usage", methods=["GET"])
def get_admin_user_chatbot_usage(user_id):
    try:
        _verify_admin(request.headers.get("Authorization"))
        days = _bounded_query_int(request.args.get("days"), 30, 1, 180, "days")
        limit = _bounded_query_int(request.args.get("limit"), 50, 1, 200, "limit")
        result = _supabase_request(
            "rpc/admin_get_user_token_usage",
            method="POST",
            json_data={
                "p_user_id": user_id,
                "p_days": days,
                "p_limit": limit,
            },
        )
        if result is None:
            return _json_error(ValueError("사용자를 찾을 수 없습니다."), "유저 사용량 조회 실패", 404)
        if not isinstance(result, dict):
            raise RuntimeError("유저 사용량 상세 응답 형식이 올바르지 않습니다.")
        return jsonify({"success": True, **result})
    except InvalidQueryParameter as error:
        return _json_error(error, "유저 사용량 조회 실패", 400)
    except ValueError as error:
        return _json_error(error, "유저 사용량 조회 실패", 401)
    except PermissionError as error:
        return _json_error(error, "유저 사용량 권한 확인 실패", 403)
    except Exception as error:
        return _json_error(error, "유저 사용량 조회 실패", 500)
