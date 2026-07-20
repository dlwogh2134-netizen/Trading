import os
from datetime import datetime, timezone

import requests
from flask import Blueprint, request, jsonify, current_app
from backend.services.auth_service import validate_access_token
from backend.services.symbol_metadata import SYMBOL_METADATA
from backend.services.error_message_service import format_error_payload
from backend.services.news_filter_validation import (
    NewsFilterValidationError,
    normalize_news_article_ids,
    normalize_news_symbol,
    parse_news_feed_filters,
)

news_bp = Blueprint("news", __name__)

@news_bp.route("/api/news", methods=["GET"])
def get_news_feed():
    """뉴스 데이터베이스로부터 수집된 최근 뉴스 피드 목록을 필터링 및 검색하여 반환합니다."""
    try:
        filters = parse_news_feed_filters(request.args)
    except NewsFilterValidationError as error:
        return jsonify(format_error_payload(error, "뉴스 조회 조건이 올바르지 않습니다.")), 400

    market = filters.market
    query = filters.query
    symbol = filters.symbol
    limit = filters.limit
    offset = filters.offset

    if symbol and not query:
        meta = SYMBOL_METADATA.get(symbol, {})
        display_name = meta.get("display_name", "")
        if display_name:
            query = display_name
        else:
            query = symbol
    
    news_repository = current_app.news_repository
    try:
        items = news_repository.list_articles(
            market=market,
            query=query,
            symbol=symbol,
            limit=limit,
            offset=offset,
        )

        total_count = news_repository.count_articles(
            market=market,
            query=query,
            symbol=symbol,
        )

        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "totalCount": total_count,
                "limit": limit,
                "offset": offset,
                "market": market,
                "query": query,
            }
        })
    except requests.exceptions.HTTPError as e:
        return jsonify(format_error_payload(e, "뉴스 제공자 호출 실패")), 502
    except Exception as e:
        return jsonify(format_error_payload(e, "뉴스 피드 조회 실패")), 500

@news_bp.route("/api/news/sync", methods=["POST"])
def sync_news_feed():
    """Naver/Finnhub 최신 뉴스를 DB에 동기화합니다. Tavily는 예약 수집에 사용하지 않습니다."""
    is_admin_request = _is_news_sync_admin_request()

    news_ingest_service = current_app.news_ingest_service
    try:
        data = request.get_json(silent=True) or {}
        symbol = normalize_news_symbol(str(data.get("symbol") or ""))
        if not is_admin_request and not symbol:
            return jsonify({
                "success": False,
                "message": "뉴스 수집 요청은 symbol 파라미터가 필요합니다.",
            }), 400

        if symbol:
            result = news_ingest_service.run_for_symbol(
                symbol=symbol,
                display_name=str(data.get("display_name") or "").strip(),
                market=str(data.get("market") or "").strip(),
                asset_type=str(data.get("asset_type") or "").strip(),
            )
        else:
            result = news_ingest_service.run_once()
        return jsonify({
            "success": True,
            "data": result,
        })
    except NewsFilterValidationError as error:
        return jsonify(format_error_payload(error, "뉴스 수집 조건이 올바르지 않습니다.")), 400
    except Exception as e:
        return jsonify(format_error_payload(e, "뉴스 수집 실패")), 500


def _is_news_sync_admin_request() -> bool:
    admin_token = (
        os.getenv("NEWS_SYNC_ADMIN_TOKEN")
        or os.getenv("ADMIN_TOKEN")
        or os.getenv("MARKET_SYNC_ADMIN_TOKEN", "")
    )
    if not admin_token:
        return False
    return request.headers.get("X-Admin-Token", "") == admin_token


def _is_news_sync_logged_in_user_request() -> bool:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return False
    try:
        validate_access_token(auth_header)
        return True
    except Exception:
        return False

@news_bp.route("/api/news/summaries/ensure", methods=["POST"])
def ensure_news_summaries():
    """지정 뉴스 목록에 대해 LLM 기반 AI 요약 정보가 적재되어 있는지 확인하고, 누락된 요약을 생성합니다."""
    if not _is_news_sync_admin_request() and not _is_news_sync_logged_in_user_request():
        return jsonify({
            "success": False,
            "message": "로그인이 필요한 작업입니다.",
        }), 403

    news_repository = current_app.news_repository
    news_summary_service = current_app.news_summary_service
    try:
        data = request.get_json(silent=True) or {}
        raw_article_ids = data.get("article_ids") or []
        if not isinstance(raw_article_ids, list):
            raise NewsFilterValidationError(
                field="article_ids",
                message="기사 ID 배열이어야 합니다.",
            )
        article_ids = normalize_news_article_ids(raw_article_ids)

        if not article_ids:
            return jsonify({
                "success": True,
                "data": {
                    "items": [],
                    "generatedCount": 0,
                }
            })

        articles = news_repository.list_articles_by_ids(article_ids)
        article_by_id = {article["id"]: article for article in articles if article.get("id")}
        updates = []
        items = []

        for article_id in article_ids:
            article = article_by_id.get(article_id)
            if not article:
                continue

            existing_summary = (article.get("ai_summary") or "").strip()
            existing_model = article.get("ai_summary_model")
            existing_prompt_version = article.get("ai_summary_prompt_version")
            normalize_summary = getattr(news_summary_service, "_normalize_summary", None)
            normalized_existing_summary = (
                normalize_summary(existing_summary)
                if callable(normalize_summary)
                else existing_summary
            )
            if (
                normalized_existing_summary
                and existing_prompt_version == news_summary_service.prompt_version
                and (existing_model != "fallback" or not news_summary_service.enabled)
            ):
                if normalized_existing_summary != existing_summary:
                    updates.append({
                        "id": article_id,
                        "ai_summary": normalized_existing_summary,
                        "ai_summary_model": existing_model,
                        "ai_summary_generated_at": article.get("ai_summary_generated_at"),
                        "ai_summary_prompt_version": existing_prompt_version,
                    })
                items.append({
                    "id": article_id,
                    "ai_summary": normalized_existing_summary,
                    "ai_summary_model": article.get("ai_summary_model"),
                    "ai_summary_generated_at": article.get("ai_summary_generated_at"),
                    "ai_summary_prompt_version": article.get("ai_summary_prompt_version"),
                })
                continue

            summary_payload = news_summary_service.summarize(article)
            update_row = {
                "id": article_id,
                "ai_summary": summary_payload["ai_summary"],
                "ai_summary_model": summary_payload["ai_summary_model"],
                "ai_summary_generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "ai_summary_prompt_version": summary_payload["ai_summary_prompt_version"],
            }
            updates.append(update_row)
            items.append(update_row)

        if updates:
            news_repository.upsert_article_summaries(updates)

        return jsonify({
            "success": True,
            "data": {
                "items": items,
                "generatedCount": len(updates),
            }
        })
    except NewsFilterValidationError as error:
        return jsonify(format_error_payload(error, "뉴스 요약 대상이 올바르지 않습니다.")), 400
    except Exception as e:
        return jsonify(format_error_payload(e, "뉴스 요약 생성 실패")), 500
