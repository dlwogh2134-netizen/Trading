import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, timedelta
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from backend.services.home_service import build_home_overview, fetch_coinone_overview, split_kis_holdings, to_float
from backend.services.kis_client import KISClient
from backend.services.toss_client import TossClient
from backend.services.coinone_client import CoinoneClient
from backend.services.binance_client import BinanceClient
from backend.services.market_index_service import (
    collect_market_index_rows,
    get_market_index_cache,
    market_index_rows_need_refresh,
    set_market_index_cache,
    serialize_market_index_rows,
)
from backend.services.auth_service import get_user_id_from_header
from backend.services.supabase_client import query_supabase

home_bp = Blueprint("home", __name__)

KIS_MARKET_MASTER_FILE_PATH = os.getenv("KIS_MARKET_MASTER_FILE_PATH", "")
MARKET_SYNC_ADMIN_TOKEN = os.getenv("MARKET_SYNC_ADMIN_TOKEN", "")


def _log_market_index_snapshot(payload: dict) -> None:
    items = payload.get("items") or []
    for symbol in ("USDKRW", "NASDAQ100_F"):
        item = next((row for row in items if str(row.get("key") or row.get("symbol") or "").upper() == symbol), None)
        if not item:
            continue
        current_price = item.get("current_price", item.get("currentPrice"))
        previous_close = item.get("previous_close", item.get("previousClose"))
        change_price = item.get("change_price", item.get("changePrice"))
        change_rate = item.get("change_rate", item.get("changeRate"))
        current_app.logger.info(
            "[MarketIndex][response] symbol=%s current_price=%s previous_close=%s change_price=%s change_rate=%s source=%s",
            symbol,
            current_price,
            previous_close,
            change_price,
            change_rate,
            item.get("source") or payload.get("source"),
        )


def _call_with_timeout(func, timeout_seconds: float, default):
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(func)
    try:
        return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError:
        future.cancel()
        return default
    except Exception:
        return default
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def parse_date_param(value: str | None, fallback: datetime) -> str:
    if not value:
        return fallback.date().isoformat()
    try:
        return datetime.fromisoformat(value[:10]).date().isoformat()
    except ValueError:
        return fallback.date().isoformat()


def calculate_portfolio_profit_rate(balance: dict) -> float:
    holdings = balance.get("holdings") or []
    total_profit = 0.0
    invested_amount = 0.0

    for item in holdings:
        qty = to_float(item.get("qty"))
        avg_price = to_float(item.get("avg_price"))
        current_price = to_float(item.get("current_price"))
        profit = to_float(item.get("profit"))
        total_profit += profit
        invested_amount += avg_price * qty if avg_price > 0 else max(0.0, current_price * qty - profit)

    if invested_amount <= 0:
        return 0.0
    return (total_profit / invested_amount) * 100


def save_portfolio_snapshot(auth_header: str, user_id: str, balance: dict, exchange_rate: float = 1500.0):
    snapshot_date = datetime.utcnow().date().isoformat()
    total_eval = to_float(balance.get("total_evaluation"))
    avail_cash = to_float(balance.get("available_cash"))

    # ?듯솕媛 USD??寃쎌슦 ?섏쑉???곸슜?섏뿬 ?먰솕(KRW) 湲곗??쇰줈 ?섏궛 ???
    if balance.get("currency") == "USD":
        total_eval = total_eval * exchange_rate
        avail_cash = avail_cash * exchange_rate

    payload = {
        "user_id": user_id,
        "snapshot_date": snapshot_date,
        "total_evaluation": total_eval,
        "available_cash": avail_cash,
        "portfolio_profit_rate": calculate_portfolio_profit_rate(balance),
        "updated_at": datetime.utcnow().isoformat(),
    }

    existing = query_supabase(
        auth_header,
        "portfolio_snapshots",
        "GET",
        params={
            "user_id": f"eq.{user_id}",
            "snapshot_date": f"eq.{snapshot_date}",
            "select": "id",
        },
    )

    if existing:
        query_supabase(
            auth_header,
            f"portfolio_snapshots?id=eq.{existing[0]['id']}",
            "PATCH",
            json_data=payload,
        )
    else:
        query_supabase(
            auth_header,
            "portfolio_snapshots",
            "POST",
            json_data=payload,
        )


def require_market_sync_admin():
    token = request.headers.get("X-Admin-Token", "")
    if not MARKET_SYNC_ADMIN_TOKEN or token != MARKET_SYNC_ADMIN_TOKEN:
        return jsonify({
            "success": False,
            "message": "愿由ъ옄 ?꾩슜 ?묒뾽?낅땲??",
        }), 403
    return None

@home_bp.route("/api/home/market", methods=["POST"])
def get_home_market():
    """???붾㈃??醫낇빀 ?쒖옣 ?꾪솴 ?곗씠?곕? 議고쉶?⑸땲??"""
    try:
        auth_header = request.headers.get("Authorization")
        data = request.json or {}
        overview = build_home_overview(data, auth_header=auth_header)
        return jsonify({
            "success": True,
            "data": overview
        })
    except Exception as error:
        return jsonify({
            "success": False,
            "message": f"???쒖옣 ?곗씠??議고쉶 ?ㅽ뙣: {str(error)}",
        }), 500


@home_bp.route("/api/dashboard/asset-trend", methods=["GET"])
def get_dashboard_asset_trend():
    """濡쒓렇???ъ슜?먯쓽 ?좎쭨蹂?珥??먯궛 ?ㅻ깄?룹쓣 議고쉶?⑸땲??"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "?몄쬆 ?ㅻ뜑媛 ?꾩슂?⑸땲??"}), 401

    now = datetime.utcnow()
    start_date = parse_date_param(request.args.get("start"), now - timedelta(days=30))
    end_date = parse_date_param(request.args.get("end"), now)

    try:
        user_id, _ = get_user_id_from_header(auth_header)
    except Exception as error:
        return jsonify({"success": False, "message": f"?ъ슜???몄쬆 ?뺤씤 ?ㅽ뙣: {str(error)}"}), 401

    try:
        rows = query_supabase(
            auth_header,
            "portfolio_snapshots",
            "GET",
            params={
                "user_id": f"eq.{user_id}",
                "snapshot_date": f"gte.{start_date}",
                "select": "snapshot_date,total_evaluation,available_cash,portfolio_profit_rate",
                "order": "snapshot_date.asc",
            },
        )
        rows = [
            row
            for row in (rows or [])
            if str(row.get("snapshot_date", ""))[:10] <= end_date
        ]
        return jsonify({
            "success": True,
            "data": {
                "items": rows,
                "start": start_date,
                "end": end_date,
                "source": "portfolio_snapshots",
            },
        })
    except Exception as error:
        return jsonify({
            "success": True,
            "data": {
                "items": [],
                "start": start_date,
                "end": end_date,
                "source": "empty",
                "message": f"?먯궛 ?ㅻ깄???곗씠?곌? ?꾩쭅 以鍮꾨릺吏 ?딆븯?듬땲?? {str(error)}",
            },
        })

@home_bp.route("/api/home/overview", methods=["POST"])
def get_home_overview():
    """
    ???붾㈃???쒖옣 ?붿빟 ?곗씠?곕? 援ъ꽦?⑸땲??
    KIS ?몄쬆 ?뺣낫媛 ?덉쑝硫?怨꾩쥖 蹂댁쑀 醫낅ぉ?? ?놁쑝硫?Coinone 怨듦컻 ?쒖꽭留?諛섑솚?⑸땲??
    """
    auth_header = request.headers.get("Authorization")
    user_id = None
    if auth_header:
        try:
            user_id, _ = get_user_id_from_header(auth_header)
        except Exception:
            pass

    data = request.json or {}
    appkey = data.get("appkey")
    appsecret = data.get("appsecret")
    cano = data.get("cano")
    acnt_prdt_cd = data.get("acnt_prdt_cd", "01")
    env = data.get("env", "MOCK")

    result = {
        "kis": None,
        "coins": [],
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "message": "",
    }

    try:
        result["coins"] = fetch_coinone_overview()
    except Exception as coin_error:
        result["message"] = f"Coinone 議고쉶 ?ㅽ뙣: {str(coin_error)}"

    has_kis_credentials = bool(appkey and appsecret and cano)
    if not has_kis_credentials:
        if not result["message"]:
            result["message"] = "KIS ?ㅻ? ?낅젰?섎㈃ 援?궡/?댁쇅 蹂댁쑀 醫낅ぉ???④퍡 遺덈윭?????덉뒿?덈떎."
        return jsonify({
            "success": True,
            "data": result
        })

    try:
        client = KISClient(
            appkey=appkey,
            appsecret=appsecret,
            cano=cano,
            acnt_prdt_cd=acnt_prdt_cd,
            env=env,
            user_id=user_id,
        )

        balance = client.get_balance()
        domestic_holdings, foreign_holdings = split_kis_holdings(balance.get("holdings", []))

        result["kis"] = {
            "total_evaluation": to_float(balance.get("total_evaluation")),
            "available_cash": to_float(balance.get("available_cash")),
            "domestic": domestic_holdings,
            "foreign": foreign_holdings,
        }

        return jsonify({
            "success": True,
            "data": result
        })
    except Exception as kis_error:
        return jsonify({
            "success": False,
            "message": f"KIS 議고쉶 ?ㅽ뙣: {str(kis_error)}",
            "data": result,
        }), 500

@home_bp.route("/api/market/kis/sync", methods=["POST"])
def sync_kis_market_universe():
    """KIS 醫낅ぉ 留덉뒪???뚯씪濡쒕???DB??醫낅ぉ ?좊땲踰꾩뒪瑜??숆린?뷀빀?덈떎."""
    admin_error = require_market_sync_admin()
    if admin_error:
        return admin_error

    data = request.json or {}
    file_paths = data.get("file_paths")
    file_path = data.get("file_path") or KIS_MARKET_MASTER_FILE_PATH
    refresh_quotes = bool(data.get("refresh_quotes", True))
    max_workers = min(max(int(data.get("max_workers") or 4), 1), 4)
    quote_limit_raw = data.get("quote_limit", 300)
    quote_limit = None if quote_limit_raw in (None, "", "all", "ALL") else int(quote_limit_raw)
    if quote_limit is not None:
        quote_limit = min(max(quote_limit, 1), 1000)

    if isinstance(file_paths, str):
        file_paths = [part.strip() for part in file_paths.split(",") if part.strip()]
    elif isinstance(file_paths, list):
        file_paths = [str(part).strip() for part in file_paths if str(part).strip()]
    else:
        file_paths = []

    if file_path and not file_paths:
        file_paths = [part.strip() for part in str(file_path).split(",") if part.strip()]

    if not file_paths:
        return jsonify({
            "success": False,
            "message": "KIS 醫낅ぉ ?뺣낫 ?뚯씪 寃쎈줈媛 ?꾩슂?⑸땲?? body.file_path, body.file_paths ?먮뒗 KIS_MARKET_MASTER_FILE_PATH瑜??ㅼ젙?댁＜?몄슂.",
        }), 400

    project_root = current_app.config.get("PROJECT_ROOT_PATH")
    if project_root:
        root_path = Path(project_root).resolve()
        for item in file_paths:
            resolved_path = Path(item).resolve()
            if root_path not in resolved_path.parents and resolved_path != root_path:
                return jsonify({
                    "success": False,
                    "message": "?꾨줈?앺듃 ?대뜑 諛뽰쓽 ?뚯씪 寃쎈줈???ъ슜?????놁뒿?덈떎.",
                }), 400

    kis_market_universe_service = current_app.kis_market_universe_service
    if not kis_market_universe_service.repository.is_configured:
        return jsonify({
            "success": False,
            "message": "SUPABASE_SERVICE_ROLE_KEY媛 ?꾩슂?⑸땲?? Supabase 愿由??ㅻ? .env???ｌ뼱二쇱꽭??",
        }), 500

    try:
        kis_client = KISClient(
            appkey=current_app.config.get("KIS_APPKEY", ""),
            appsecret=current_app.config.get("KIS_APPSECRET", ""),
            cano=current_app.config.get("KIS_CANO", ""),
            acnt_prdt_cd=current_app.config.get("KIS_ACNT_PRDT_CD", "01"),
            env=current_app.config.get("KIS_ENV", "MOCK"),
        )
        result = kis_market_universe_service.sync_from_files(
            file_paths=file_paths,
            kis_client=kis_client,
            refresh_quotes=refresh_quotes,
            max_workers=max_workers,
            quote_limit=quote_limit,
        )
        return jsonify({
            "success": True,
            "message": "KIS 醫낅ぉ 留덉뒪?곗? 嫄곕옒?湲??ㅻ깄???숆린?붽? ?꾨즺?섏뿀?듬땲??",
            "data": result,
        })
    except Exception as error:
        return jsonify({
            "success": False,
            "message": f"KIS 醫낅ぉ ?숆린???ㅽ뙣: {str(error)}",
        }), 500

@home_bp.route("/api/market/rankings", methods=["GET"])
def get_market_rankings():
    """?좊땲踰꾩뒪??嫄곕옒?湲??쒖쐞瑜?議고쉶?⑸땲??"""
    market_segment = request.args.get("market_segment", "ALL")
    limit = int(request.args.get("limit", 50))

    kis_market_universe_service = current_app.kis_market_universe_service
    try:
        rankings = kis_market_universe_service.repository.list_turnover_rankings(
            market_segment=market_segment,
            limit=limit,
        )
        universe_count = kis_market_universe_service.repository.count_universe(market_segment=market_segment)
        return jsonify({
            "success": True,
            "data": {
                "items": rankings,
                "totalCount": len(rankings),
                "universeCount": universe_count,
                "marketSegment": market_segment.upper(),
                "limit": limit,
            }
        })
    except Exception as error:
        return jsonify({
            "success": False,
            "message": f"嫄곕옒?湲??쒖쐞 議고쉶 ?ㅽ뙣: {str(error)}",
        }), 500

@home_bp.route("/api/market/indices", methods=["GET"])
def get_market_indices():
    """하단 지수 바에 사용할 최신 지수 스냅샷을 반환합니다."""
    repository = getattr(current_app, "market_index_repository", None)
    if repository is None or not repository.is_configured:
        return jsonify({
            "success": False,
            "message": "시장 지수 저장소가 아직 설정되지 않았습니다.",
        }), 500

    try:
        rows = get_market_index_cache()
        if rows:
            payload = serialize_market_index_rows(rows)
            payload["cacheStatus"] = "HIT"
            payload["refreshNeeded"] = market_index_rows_need_refresh(rows)
            _log_market_index_snapshot(payload)
            current_app.logger.info(
                "[MarketIndex] indices loaded count=%s source=%s fetchedAt=%s",
                len(payload.get("items") or []),
                payload.get("source"),
                payload.get("fetchedAt"),
            )
            return jsonify({
                "success": True,
                "data": payload,
            })

        rows = _call_with_timeout(repository.list_latest, 2.0, [])
        if rows:
            payload = serialize_market_index_rows(rows)
            payload["cacheStatus"] = "HIT"
            payload["refreshNeeded"] = market_index_rows_need_refresh(rows)
            set_market_index_cache(rows)
            _log_market_index_snapshot(payload)
            current_app.logger.info(
                "[MarketIndex] indices loaded count=%s source=%s fetchedAt=%s",
                len(payload.get("items") or []),
                payload.get("source"),
                payload.get("fetchedAt"),
            )
            return jsonify({
                "success": True,
                "data": payload,
            })

        live_rows, live_errors = _call_with_timeout(collect_market_index_rows, 8.0, ([], []))
        if live_rows:
            if repository.is_configured:
                try:
                    repository.upsert_latest(live_rows)
                except Exception:
                    pass
            set_market_index_cache(live_rows)
            payload = serialize_market_index_rows(live_rows)
            payload["source"] = "live.collector"
            payload["cacheStatus"] = "MISS"
            payload["bootstrap"] = True
            payload["errors"] = live_errors
            _log_market_index_snapshot(payload)
            current_app.logger.info(
                "[MarketIndex] indices loaded count=%s source=%s fetchedAt=%s",
                len(payload.get("items") or []),
                payload.get("source"),
                payload.get("fetchedAt"),
            )
            return jsonify({
                "success": True,
                "data": payload,
            })

        return jsonify({
            "success": False,
            "message": "지수 캐시를 아직 준비 중입니다. 잠시 후 다시 시도해주세요.",
            "errors": live_errors,
        }), 503
    except Exception as error:
        live_rows, live_errors = _call_with_timeout(collect_market_index_rows, 8.0, ([], []))
        if live_rows:
            if repository.is_configured:
                try:
                    repository.upsert_latest(live_rows)
                except Exception:
                    pass
            set_market_index_cache(live_rows)
            payload = serialize_market_index_rows(live_rows)
            payload["source"] = "live.collector"
            payload["cacheStatus"] = "MISS"
            payload["bootstrap"] = True
            payload["errors"] = [str(error), *[item["message"] for item in live_errors]]
            _log_market_index_snapshot(payload)
            current_app.logger.info(
                "[MarketIndex] indices loaded count=%s source=%s fetchedAt=%s",
                len(payload.get("items") or []),
                payload.get("source"),
                payload.get("fetchedAt"),
            )
            return jsonify({
                "success": True,
                "data": payload,
            })
        return jsonify({
            "success": False,
            "message": f"지수 데이터 조회 실패: {str(error)}",
        }), 500

@home_bp.route("/api/dashboard/balance", methods=["POST"])
def get_dashboard_balance():
    """?뱀젙 嫄곕옒?뚯쓽 ?ㅼ떆媛?怨꾩쥖 ?붽퀬 諛??됯? ?먯궛??議고쉶?⑸땲??"""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "?몄쬆 ?ㅻ뜑媛 ?꾨씫?섏뿀?듬땲??"}), 401

    data = request.json or {}
    exchange = data.get("exchange", "KIS")
    broker_env = data.get("env", "MOCK")

    try:
        user_id, token = get_user_id_from_header(auth_header)
        
        params = {
            "user_id": f"eq.{user_id}",
            "exchange": f"eq.{exchange}",
            "broker_env": f"eq.{broker_env}"
        }
        records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
        if not records or len(records) == 0:
            return jsonify({"success": False, "message": f"?깅줉??{exchange} ({broker_env}) API ?ㅺ? ?놁뒿?덈떎."}), 404
            
        record = records[0]
        crypto_helper = current_app.crypto
        access_key = crypto_helper.decrypt(record.get("encrypted_access_key"))
        secret_key = crypto_helper.decrypt(record.get("encrypted_secret_key"))
        
        if exchange == "TOSS":
            account_seq = record.get("toss_account_seq")
            client = TossClient(
                client_id=access_key,
                client_secret=secret_key,
                account_seq=account_seq,
                env=broker_env,
                user_id=user_id,
            )
            balance = client.get_balance()
        elif exchange == "KIS":
            cano = record.get("kis_account_no")
            acnt_prdt_cd = record.get("kis_account_code", "01")
            client = KISClient(
                appkey=access_key,
                appsecret=secret_key,
                cano=cano,
                acnt_prdt_cd=acnt_prdt_cd,
                env=broker_env,
                user_id=user_id,
            )
            balance = client.get_balance()
        elif exchange == "COINONE":
            client = CoinoneClient(
                access_token=access_key,
                secret_key=secret_key
            )
            balance = client.get_balance()
        elif exchange == "BINANCE":
            client = BinanceClient(
                api_key=access_key,
                secret_key=secret_key
            )
            balance = client.get_balance()
        else:
            return jsonify({"success": False, "message": f"吏?먰븯吏 ?딅뒗 嫄곕옒?? {exchange}"}), 400

        # ?듯솕媛 USD??寃쎌슦 ?먯궛 ?꾩쟻 異붿씠瑜??꾪븳 ?섏쑉 援ы븯湲?
        exchange_rate = 1500.0
        if exchange == "TOSS" and hasattr(client, "get_exchange_rate"):
            exchange_rate = client.get_exchange_rate()

        try:
            save_portfolio_snapshot(auth_header, user_id, balance, exchange_rate)
        except Exception:
            pass

        # ?꾨줎?몄뿏???섏궛????묓븯湲??꾪빐 exchange_rate ?꾨뱶瑜??④퍡 ?묐떟??二쇱엯
        balance["exchange_rate"] = exchange_rate

        return jsonify({
            "success": True,
            "data": balance
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"?붽퀬 議고쉶 以??ㅽ뙣: {str(e)}"
        }), 500

