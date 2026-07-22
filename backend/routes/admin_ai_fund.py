from flask import Blueprint, jsonify, request
from backend.services.error_message_service import format_error_payload
from backend.services.supabase_client import safe_query_supabase_as_service_role
from backend.services.admin_ai_managed_trader import AdminAiManagedTrader

admin_ai_fund_bp = Blueprint("admin_ai_fund", __name__)


def _extract_bearer_token(auth_header: str | None) -> str:
    if not auth_header or not auth_header.startswith("Bearer "):
        raise ValueError("로그인이 필요합니다.")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise ValueError("로그인이 필요합니다.")
    return token


@admin_ai_fund_bp.route("/api/admin/ai-fund/configs", methods=["GET"])
def get_ai_fund_configs():
    try:
        auth_header = request.headers.get("Authorization")
        _extract_bearer_token(auth_header)
        
        configs = safe_query_supabase_as_service_role("admin_ai_fund_configs") or []
        return jsonify({"success": True, "configs": configs}), 200
    except ValueError as val_err:
        return jsonify(format_error_payload(val_err, "인증 에러")), 401
    except Exception as err:
        return jsonify(format_error_payload(err, "설정 조회 에러")), 500


@admin_ai_fund_bp.route("/api/admin/ai-fund/configs", methods=["POST"])
def upsert_ai_fund_config():
    try:
        auth_header = request.headers.get("Authorization")
        _extract_bearer_token(auth_header)
        
        data = request.json or {}
        user_id = data.get("user_id")
        exchange_type = data.get("exchange_type", "coinone")
        
        if not user_id:
            return jsonify(format_error_payload(ValueError("user_id는 필수입니다."), "입력값 에러")), 400

        res = safe_query_supabase_as_service_role(
            "admin_ai_fund_configs",
            method="POST",
            json_data=data,
            extra_headers={"Prefer": "resolution=merge-duplicates"}
        )
        return jsonify({"success": True, "config": res}), 200
    except ValueError as val_err:
        return jsonify(format_error_payload(val_err, "인증 에러")), 401
    except Exception as err:
        return jsonify(format_error_payload(err, "설정 저장 에러")), 500


@admin_ai_fund_bp.route("/api/admin/ai-fund/logs", methods=["GET"])
def get_ai_fund_trade_logs():
    try:
        auth_header = request.headers.get("Authorization")
        _extract_bearer_token(auth_header)
        
        logs = safe_query_supabase_as_service_role(
            "admin_ai_trade_logs",
            params={"order": "created_at.desc", "limit": "50"}
        ) or []
        return jsonify({"success": True, "logs": logs}), 200
    except ValueError as val_err:
        return jsonify(format_error_payload(val_err, "인증 에러")), 401
    except Exception as err:
        return jsonify(format_error_payload(err, "트레이딩 로그 조회 에러")), 500


@admin_ai_fund_bp.route("/api/admin/ai-fund/kill-switch", methods=["POST"])
def execute_kill_switch():
    try:
        auth_header = request.headers.get("Authorization")
        _extract_bearer_token(auth_header)
        
        data = request.json or {}
        user_id = data.get("user_id", "00000000-0000-0000-0000-000000000000")
        exchange_type = data.get("exchange_type", "coinone")
        
        trader = AdminAiManagedTrader(user_id=user_id, exchange_type=exchange_type)
        killed = trader.emergency_kill_switch()
        
        return jsonify({"success": killed, "message": "긴급 셧다운 실행 완료" if killed else "셧다운 실패"}), 200
    except ValueError as val_err:
        return jsonify(format_error_payload(val_err, "인증 에러")), 401
    except Exception as err:
        return jsonify(format_error_payload(err, "긴급 셧다운 에러")), 500
