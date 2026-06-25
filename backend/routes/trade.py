import re
import time
import requests
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from backend.services.supabase_client import query_supabase
from backend.services.auth_service import get_user_id_from_header
from backend.services.toss_client import TossClient
from backend.services.kis_client import KISClient

# 단기 인메모리 시세 캐시 정의 (Rate limit 방지용)
CANDLE_CACHE = {}
CACHE_TTL_SECONDS = 10  # 10초 유효

trade_bp = Blueprint("trade", __name__)

@trade_bp.route("/api/trade/order", methods=["POST"])
def place_manual_order():
    """
    통합 수동 주문 API 엔드포인트.
    프론트엔드에서 수동으로 입력한 주문을 처리하고, 
    주문 금액이 10만원 이하인지 가드 검증을 거친 후 해당하는 거래소 API를 기동합니다.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return jsonify({"success": False, "message": "인증 헤더가 누락되었습니다."}), 401
    
    try:
        user_id, token = get_user_id_from_header(auth_header)
    except Exception as e:
        return jsonify({"success": False, "message": f"인증 실패: {str(e)}"}), 401

    data = request.json or {}
    exchange = data.get("exchange")
    symbol = data.get("symbol")
    action = data.get("action")  # BUY or SELL
    order_type = data.get("order_type")  # LIMIT or MARKET
    price = data.get("price")  # LIMIT일 때 필수
    quantity = data.get("quantity")  # 필수
    broker_env = data.get("broker_env", "REAL")  # MOCK or REAL
    
    # 1. 필수 파라미터 검증
    if not exchange or not symbol or not action or not order_type or quantity is None:
        return jsonify({"success": False, "message": "필수 주문 파라미터가 누락되었습니다."}), 400
    
    if exchange not in ("TOSS", "KIS", "COINONE", "BINANCE"):
        return jsonify({"success": False, "message": "지원하지 않는 거래소입니다."}), 400

    if action.upper() not in ("BUY", "SELL"):
        return jsonify({"success": False, "message": "올바르지 않은 주문 방향(action)입니다."}), 400

    if order_type.upper() not in ("LIMIT", "MARKET"):
        return jsonify({"success": False, "message": "올바르지 않은 주문 유형(order_type)입니다."}), 400

    try:
        qty = float(quantity)
        if qty <= 0:
            return jsonify({"success": False, "message": "주문 수량은 0보다 커야 합니다."}), 400
    except ValueError:
        return jsonify({"success": False, "message": "올바르지 않은 주문 수량 포맷입니다."}), 400

    # 2. 거래소 API 크리덴셜 정보 가져오기 및 복호화
    crypto_helper = current_app.crypto
    try:
        params = {
            "user_id": f"eq.{user_id}",
            "exchange": f"eq.{exchange}",
            "broker_env": f"eq.{broker_env}"
        }
        records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
        if not records or len(records) == 0:
            return jsonify({"success": False, "message": f"등록된 {exchange} ({broker_env}) API 크리덴셜 정보가 없습니다."}), 400
        
        record = records[0]
        access_key = crypto_helper.decrypt(record.get("encrypted_access_key"))
        secret_key = crypto_helper.decrypt(record.get("encrypted_secret_key"))
    except Exception as e:
        return jsonify({"success": False, "message": f"API 크리덴셜 로드 및 복호화 실패: {str(e)}"}), 500

    # 3. 1회 주문 한도 10만원 이하 가드 캡 검증
    order_price = 0.0
    if order_type.upper() == "LIMIT":
        if price is None:
            return jsonify({"success": False, "message": "지정가 주문에는 단가(price)가 필수적입니다."}), 400
        try:
            order_price = float(price)
        except ValueError:
            return jsonify({"success": False, "message": "올바르지 않은 단가 포맷입니다."}), 400
    else:
        # 시장가 주문인 경우 실시간 현재가를 가져와 계산
        try:
            if exchange == "TOSS":
                toss_account_seq = record.get("toss_account_seq")
                client = TossClient(client_id=access_key, client_secret=secret_key, account_seq=toss_account_seq, env=broker_env)
                price_info = client.get_price(symbol)
                order_price = price_info.get("current_price", 0.0)
            elif exchange == "KIS":
                cano = record.get("kis_account_no")
                acnt_prdt_cd = record.get("kis_account_code", "01")
                client = KISClient(appkey=access_key, appsecret=secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=broker_env)
                price_info = client.get_price(symbol)
                order_price = price_info.get("current_price", 0.0)
            else:
                return jsonify({"success": False, "message": f"{exchange} 거래소는 현재 시장가 조회가 지원되지 않습니다."}), 400
        except Exception as e:
            return jsonify({"success": False, "message": f"시장가 검증을 위한 시세 조회 실패: {str(e)}"}), 500

    total_amount = order_price * qty
    limit_krw = 100000.0
    if exchange == "BINANCE":
        # 1달러 = 1400원 기준으로 가치 환산하여 10만원 한도 체크
        total_amount_krw = total_amount * 1400.0
    else:
        total_amount_krw = total_amount

    if broker_env == "REAL" and total_amount_krw > limit_krw:
        return jsonify({
            "success": False, 
            "message": f"실거래 1회 주문 한도(100,000원)를 초과할 수 없습니다. (신청 금액: {total_amount_krw:,.0f}원)"
        }), 400

    # 4. 주문 실행
    try:
        if exchange == "TOSS":
            toss_account_seq = record.get("toss_account_seq")
            client = TossClient(client_id=access_key, client_secret=secret_key, account_seq=toss_account_seq, env=broker_env)
            order_res = client.place_order(symbol=symbol, qty=qty, side=action, ord_type=order_type, price=order_price)
        elif exchange == "KIS":
            cano = record.get("kis_account_no")
            acnt_prdt_cd = record.get("kis_account_code", "01")
            client = KISClient(appkey=access_key, appsecret=secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=broker_env)
            order_res = client.place_order(symbol=symbol, qty=qty, side=action, ord_type=order_type, price=order_price)
        else:
            return jsonify({"success": False, "message": f"{exchange} 거래소는 현재 수동 주문 기능이 지원되지 않습니다."}), 400
    except Exception as e:
        return jsonify({"success": False, "message": f"주문 전송 실패: {str(e)}"}), 500

    # 5. 주문 체결 성공 후 자동 감시(Stop-loss, Take-profit) 바인딩
    auto_exit_result = None
    auto_exit = data.get("auto_exit", False)
    if auto_exit and action.upper() == "BUY":
        target_profit_rate = float(data.get("target_profit_rate", 5.0))
        stop_loss_rate = float(data.get("stop_loss_rate", -3.0))
        
        # asset_type 및 market_country 판정
        asset_type = "STOCK" if exchange in ("TOSS", "KIS") else "CRYPTO"
        market_country = None
        if asset_type == "STOCK":
            market_country = "KR" if re.match(r"^\d{6}$", symbol) else "US"

        try:
            rule_data = {
                "user_id": user_id,
                "exchange": exchange,
                "asset_type": asset_type,
                "ticker": symbol,
                "symbol": symbol,
                "market_country": market_country,
                "entry_price": order_price,
                "investment_amount": total_amount,
                "target_profit_rate": target_profit_rate,
                "stop_loss_rate": stop_loss_rate,
                "status": "RUNNING"
            }
            # Supabase에 감시 조건 등록
            query_supabase(auth_header, "auto_trading_rules", "POST", json_data=rule_data)
            auto_exit_result = "감시 조건 등록 완료"
        except Exception as e:
            auto_exit_result = f"감시 조건 등록 실패: {str(e)}"

    # 6. 주문 이력 trade_proposals에 EXECUTED 상태로 등록 (수동 거래 히스토리 기록용)
    try:
        asset_type = "STOCK" if exchange in ("TOSS", "KIS") else "CRYPTO"
        market_country = None
        if asset_type == "STOCK":
            market_country = "KR" if re.match(r"^\d{6}$", symbol) else "US"
        currency = "KRW" if (exchange != "BINANCE" and market_country != "US") else "USD"
        
        proposal_data = {
            "user_id": user_id,
            "exchange": exchange,
            "asset_type": asset_type,
            "ticker": symbol,
            "symbol": symbol,
            "side": action.upper(),
            "price": order_price,
            "volume": qty,
            "ord_type": order_type.upper(),
            "market_country": market_country,
            "currency": currency,
            "external_order_id": order_res.get("order_id"),
            "status": "EXECUTED",
            "created_at": datetime.now().isoformat()
        }
        query_supabase(auth_header, "trade_proposals", "POST", json_data=proposal_data)
    except Exception as e:
        current_app.logger.error(f"주문 이력 기록 실패: {str(e)}")

    return jsonify({
        "success": True,
        "message": "주문이 성공적으로 전송되었습니다.",
        "order_id": order_res.get("order_id"),
        "status": order_res.get("status"),
        "auto_exit": auto_exit_result,
        "detail": order_res
    })

@trade_bp.route("/api/chart/candles", methods=["GET"])
def get_chart_candles():
    """
    통합 캔들 시세 조회 API 엔드포인트.
    각 거래소 클라이언트를 활용해 캔들 시세를 가져와 Lightweight Charts용 단일 포맷으로 어댑팅하여 반환합니다.
    """
    exchange = request.args.get("exchange")
    symbol = request.args.get("symbol")
    interval = request.args.get("interval", "1d")
    count = int(request.args.get("count", 120))
    broker_env = request.args.get("broker_env", "REAL")

    if not exchange or not symbol:
        return jsonify({"success": False, "message": "exchange 및 symbol 파라미터가 필수적입니다."}), 400

    auth_header = request.headers.get("Authorization")

    # 10초 단기 캐싱 조회
    cache_key = (exchange, symbol, interval, broker_env)
    now = time.time()
    if cache_key in CANDLE_CACHE:
        expire_time, cached_data = CANDLE_CACHE[cache_key]
        if now < expire_time:
            return jsonify({"success": True, "data": cached_data})

    try:
        # 1. TOSS 캔들
        if exchange == "TOSS":
            if not auth_header:
                return jsonify({"success": False, "message": "인증 헤더가 필요합니다."}), 401
            user_id, token = get_user_id_from_header(auth_header)
            crypto_helper = current_app.crypto
            params = {"user_id": f"eq.{user_id}", "exchange": "eq.TOSS", "broker_env": f"eq.{broker_env}"}
            records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
            
            # Toss 미지원 주기(5m, 15m, 30m, 60m, 1h, 1w, 1M 등)인 경우
            # KIS API Key가 등록되어 있다면 KIS API를 타서 리샘플링 및 풍부한 분봉 데이터를 안정적으로 제공받음
            is_native_toss = interval in ("1d", "D", "1m")
            
            # KIS API 키가 있는지 선체크 (Toss 키가 없거나, 혹은 Toss 미지원 주기인 경우 우회 사용 목적)
            params_kis = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS"}
            records_kis = query_supabase(auth_header, "user_api_keys", "GET", params=params_kis)
            
            # 만약 Toss 키가 없거나, 혹은 미지원 주기인데 KIS 키가 있는 경우 KIS로 처리
            if (not records or not is_native_toss) and records_kis:
                kis_access_key = crypto_helper.decrypt(records_kis[0].get("encrypted_access_key"))
                kis_secret_key = crypto_helper.decrypt(records_kis[0].get("encrypted_secret_key"))
                cano = records_kis[0].get("kis_account_no")
                acnt_prdt_cd = records_kis[0].get("kis_account_code", "01")
                kis_env = records_kis[0].get("broker_env", "MOCK")
                
                client = KISClient(appkey=kis_access_key, appsecret=kis_secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=kis_env)
                if interval in ("1d", "D"):
                    candles = client.get_candles(symbol, interval="D", count=count)
                elif interval in ("1w", "W"):
                    candles = client.get_candles(symbol, interval="W", count=count)
                elif interval in ("1M", "M"):
                    candles = client.get_candles(symbol, interval="M", count=count)
                elif interval == "1m":
                    candles = client.get_minute_candles(symbol, interval_minutes=1, count=count)
                elif interval == "5m":
                    candles = client.get_minute_candles(symbol, interval_minutes=5, count=count)
                elif interval == "15m":
                    candles = client.get_minute_candles(symbol, interval_minutes=15, count=count)
                elif interval == "30m":
                    candles = client.get_minute_candles(symbol, interval_minutes=30, count=count)
                elif interval in ("60m", "1h"):
                    candles = client.get_minute_candles(symbol, interval_minutes=60, count=count)
                else:
                    candles = client.get_candles(symbol, interval="D", count=count)
                    
                CANDLE_CACHE[cache_key] = (time.time() + CACHE_TTL_SECONDS, candles)
                return jsonify({"success": True, "data": candles})
            
            # Toss 키가 없는 경우 KIS 키도 없다면 에러 반환
            if not records:
                return jsonify({"success": False, "message": "등록된 Toss 또는 KIS API 키가 없습니다."}), 400
                
            # Toss 키가 있고 네이티브 주기를 요청했거나, KIS 키가 없어 자체 리샘플링을 해야 하는 경우
            access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
            secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
            toss_account_seq = records[0].get("toss_account_seq")
            
            client = TossClient(client_id=access_key, client_secret=secret_key, account_seq=toss_account_seq, env=broker_env)
            candles = client.get_candles(symbol, interval=interval, count=count)
            CANDLE_CACHE[cache_key] = (time.time() + CACHE_TTL_SECONDS, candles)
            return jsonify({"success": True, "data": candles})

        # 2. KIS 캔들
        elif exchange == "KIS":
            if not auth_header:
                return jsonify({"success": False, "message": "인증 헤더가 필요합니다."}), 401
            user_id, token = get_user_id_from_header(auth_header)
            crypto_helper = current_app.crypto
            params = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS", "broker_env": f"eq.{broker_env}"}
            records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
            if not records:
                return jsonify({"success": False, "message": "등록된 KIS API 키가 없습니다."}), 400
            access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
            secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
            cano = records[0].get("kis_account_no")
            acnt_prdt_cd = records[0].get("kis_account_code", "01")
            
            client = KISClient(appkey=access_key, appsecret=secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=broker_env)
            
            # interval 판별 및 리샘플링 적용
            if interval in ("1d", "D"):
                candles = client.get_candles(symbol, interval="D", count=count)
            elif interval in ("1w", "W"):
                candles = client.get_candles(symbol, interval="W", count=count)
            elif interval in ("1M", "M"):
                candles = client.get_candles(symbol, interval="M", count=count)
            elif interval == "1m":
                candles = client.get_minute_candles(symbol, interval_minutes=1, count=count)
            elif interval == "5m":
                candles = client.get_minute_candles(symbol, interval_minutes=5, count=count)
            elif interval == "15m":
                candles = client.get_minute_candles(symbol, interval_minutes=15, count=count)
            elif interval == "30m":
                candles = client.get_minute_candles(symbol, interval_minutes=30, count=count)
            elif interval in ("60m", "1h"):
                candles = client.get_minute_candles(symbol, interval_minutes=60, count=count)
            else:
                candles = client.get_candles(symbol, interval="D", count=count)
                
            CANDLE_CACHE[cache_key] = (time.time() + CACHE_TTL_SECONDS, candles)
            return jsonify({"success": True, "data": candles})

        # 3. COINONE 캔들
        elif exchange == "COINONE":
            # Coinone은 1m, 3m, 5m, 10m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w 지원
            coinone_interval = interval
            if interval in ("1d", "day"):
                coinone_interval = "1d"
            elif interval in ("1w", "week"):
                coinone_interval = "1w"
            elif interval in ("1h", "60m"):
                coinone_interval = "1h"
                
            url = f"https://api.coinone.co.kr/public/v2/chart/KRW/{symbol.upper()}"
            res = requests.get(url, params={"interval": coinone_interval})
            if res.status_code != 200:
                return jsonify({"success": False, "message": f"Coinone 차트 조회 실패: {res.text}"}), 500
                
            data = res.json()
            if data.get("result") != "success":
                return jsonify({"success": False, "message": "Coinone 차트 조회 실패"}), 500
                
            candles = []
            is_intraday = coinone_interval not in ("1d", "1w")
            for item in data.get("chart", []):
                try:
                    ts = int(item.get("timestamp")) // 1000
                    if is_intraday:
                        time_val = ts
                    else:
                        time_val = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        
                    candles.append({
                        "time": time_val,
                        "open": float(item.get("open", 0)),
                        "high": float(item.get("high", 0)),
                        "low": float(item.get("low", 0)),
                        "close": float(item.get("close", 0)),
                        "volume": float(item.get("volume", 0))
                    })
                except (ValueError, TypeError):
                    pass
            candles_subset = candles[-count:]
            CANDLE_CACHE[cache_key] = (time.time() + CACHE_TTL_SECONDS, candles_subset)
            return jsonify({"success": True, "data": candles_subset})

        # 4. BINANCE 캔들
        elif exchange == "BINANCE":
            # Binance는 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M 지원
            binance_interval = interval
            if interval in ("1d", "day"):
                binance_interval = "1d"
            elif interval in ("1w", "week"):
                binance_interval = "1w"
            elif interval in ("1M", "month"):
                binance_interval = "1M"
            elif interval in ("1h", "60m"):
                binance_interval = "1h"
                
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol.upper(),
                "interval": binance_interval,
                "limit": min(count, 1000)
            }
            res = requests.get(url, params=params)
            if res.status_code != 200:
                return jsonify({"success": False, "message": f"Binance 차트 조회 실패: {res.text}"}), 500
                
            data = res.json()
            candles = []
            is_intraday = binance_interval not in ("1d", "1w", "1M")
            for item in data:
                try:
                    ts = int(item[0]) // 1000
                    if is_intraday:
                        time_val = ts
                    else:
                        time_val = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                        
                    candles.append({
                        "time": time_val,
                        "open": float(item[1]),
                        "high": float(item[2]),
                        "low": float(item[3]),
                        "close": float(item[4]),
                        "volume": float(item[5])
                    })
                except (ValueError, TypeError, IndexError):
                    pass
            CANDLE_CACHE[cache_key] = (time.time() + CACHE_TTL_SECONDS, candles)
            return jsonify({"success": True, "data": candles})

        else:
            return jsonify({"success": False, "message": f"지원하지 않는 거래소: {exchange}"}), 400

    except Exception as e:
        import traceback
        current_app.logger.error(f"시세 차트 조회 에러 발생: {str(e)}\n{traceback.format_exc()}")
        return jsonify({"success": False, "message": f"시세 차트 조회 실패: {str(e)}"}), 500


def generate_mock_orderbook(symbol, base_price=150000):
    import random
    if base_price <= 0:
        base_price = 150000
    
    # 주식 호가 단위 (10만원 이상 50만원 미만: 500원 단위, 50만원 이상: 1000원 단위, 그 이하는 적절히)
    if base_price >= 500000:
        unit = 1000
    elif base_price >= 100000:
        unit = 500
    elif base_price >= 50000:
        unit = 100
    else:
        unit = 10
        
    asks = []
    bids = []
    
    for i in range(1, 11):
        price = int((base_price // unit) * unit) + (i * unit)
        size = random.randint(10, 1500)
        asks.append({"price": price, "size": size})
        
    for i in range(0, 10):
        price = int((base_price // unit) * unit) - (i * unit)
        size = random.randint(10, 2000)
        bids.append({"price": price, "size": size})
        
    # 매도는 가격 오름차순, 매수는 가격 내림차순 정렬 상태 유지
    asks.sort(key=lambda x: x["price"])
    bids.sort(key=lambda x: x["price"], reverse=True)
    
    return {
        "symbol": symbol,
        "timestamp": int(time.time()),
        "total_ask_size": sum(x["size"] for x in asks),
        "total_bid_size": sum(x["size"] for x in bids),
        "asks": asks,
        "bids": bids
    }


def generate_mock_trades(symbol, base_price=150000):
    import random
    if base_price <= 0:
        base_price = 150000
        
    trades = []
    now = int(time.time())
    
    for i in range(20):
        trade_time = now - (i * random.randint(1, 10))
        time_str = datetime.fromtimestamp(trade_time).strftime("%H:%M:%S")
        
        price_diff = random.choice([-2, -1, 0, 1, 2]) * (500 if base_price >= 100000 else 10)
        price = base_price + price_diff
        qty = random.randint(1, 200)
        side = random.choice(["BUY", "SELL"])
        
        trades.append({
            "time": time_str,
            "timestamp": trade_time,
            "price": price,
            "qty": qty,
            "side": side,
            "change_rate": round(random.uniform(-0.5, 0.5), 2)
        })
    return trades


@trade_bp.route("/api/chart/orderbook", methods=["GET"])
def get_orderbook_api():
    """
    통합 호가(Orderbook) 조회 API 엔드포인트.
    거래소 API 장애 또는 장외 시간일 경우 자동으로 가상 호가 시뮬레이션을 생성하여 제공합니다.
    """
    exchange = request.args.get("exchange")
    symbol = request.args.get("symbol")
    broker_env = request.args.get("broker_env", "REAL")

    if not exchange or not symbol:
        return jsonify({"success": False, "message": "exchange 및 symbol 파라미터가 필수적입니다."}), 400

    auth_header = request.headers.get("Authorization")
    
    # 기본 Mock 기준 가격 조회 시도 (캐시된 캔들 종가가 존재한다면 동적으로 보정)
    base_price = 150000  # 디폴트
    cached_close = None
    for cache_key, (expire, candles) in CANDLE_CACHE.items():
        if len(cache_key) >= 4 and cache_key[1].upper() == symbol.upper() and candles:
            cached_close = candles[-1]["close"]
            break
            
    if cached_close is not None and cached_close > 0:
        base_price = cached_close
    else:
        # 캐시가 없는 진입 극초기에는 동기식으로 시세를 직접 1회 조회하여 보정
        try:
            if exchange == "KIS" and auth_header:
                user_id, token = get_user_id_from_header(auth_header)
                crypto_helper = current_app.crypto
                params_db = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS", "broker_env": f"eq.{broker_env}"}
                records = query_supabase(auth_header, "user_api_keys", "GET", params=params_db)
                if records:
                    access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                    secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                    cano = records[0].get("kis_account_no")
                    acnt_prdt_cd = records[0].get("kis_account_code", "01")
                    kis_env = records[0].get("broker_env", "MOCK")
                    client = KISClient(appkey=access_key, appsecret=secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=kis_env)
                    price_info = client.get_price(symbol)
                    if price_info and price_info.get("current_price"):
                        base_price = price_info["current_price"]
            elif exchange == "TOSS" and auth_header:
                user_id, token = get_user_id_from_header(auth_header)
                crypto_helper = current_app.crypto
                params_db = {"user_id": f"eq.{user_id}", "exchange": "eq.TOSS", "broker_env": f"eq.{broker_env}"}
                records = query_supabase(auth_header, "user_api_keys", "GET", params=params_db)
                if records:
                    access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                    secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                    toss_account_seq = records[0].get("toss_account_seq")
                    client = TossClient(client_id=access_key, client_secret=secret_key, account_seq=toss_account_seq, env=broker_env)
                    price_info = client.get_price(symbol)
                    if price_info and price_info.get("current_price"):
                        base_price = price_info["current_price"]
            elif exchange == "COINONE":
                res_c = requests.get(f"https://api.coinone.co.kr/public/v2/ticker/KRW/{symbol.upper()}", timeout=3)
                if res_c.status_code == 200:
                    ticker_data = res_c.json().get("ticker")
                    if ticker_data and ticker_data.get("last"):
                        base_price = float(ticker_data["last"])
            elif exchange == "BINANCE":
                res_b = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": symbol.upper()}, timeout=3)
                if res_b.status_code == 200:
                    price_data = res_b.json()
                    if price_data and price_data.get("price"):
                        base_price = float(price_data["price"])
        except Exception as price_err:
            current_app.logger.warning(f"진입 초기 base_price 실시간 획득 실패: {str(price_err)}")
    
    try:
        # 1. COINONE 호가 조회
        if exchange == "COINONE":
            url = f"https://api.coinone.co.kr/public/v2/orderbook/KRW/{symbol.upper()}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get("result") == "success":
                    asks = []
                    bids = []
                    for item in data.get("asks", []):
                        asks.append({"price": float(item.get("price")), "size": float(item.get("qty"))})
                    for item in data.get("bids", []):
                        bids.append({"price": float(item.get("price")), "size": float(item.get("qty"))})
                    
                    asks.sort(key=lambda x: x["price"])
                    bids.sort(key=lambda x: x["price"], reverse=True)
                    
                    return jsonify({
                        "success": True,
                        "data": {
                            "symbol": symbol,
                            "timestamp": int(time.time()),
                            "total_ask_size": sum(x["size"] for x in asks),
                            "total_bid_size": sum(x["size"] for x in bids),
                            "asks": asks[:10],
                            "bids": bids[:10]
                        }
                    })

        # 2. BINANCE 호가 조회
        elif exchange == "BINANCE":
            url = "https://api.binance.com/api/v3/depth"
            res = requests.get(url, params={"symbol": symbol.upper(), "limit": 10}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                asks = [{"price": float(x[0]), "size": float(x[1])} for x in data.get("asks", [])]
                bids = [{"price": float(x[0]), "size": float(x[1])} for x in data.get("bids", [])]
                return jsonify({
                    "success": True,
                    "data": {
                        "symbol": symbol,
                        "timestamp": int(time.time()),
                        "total_ask_size": sum(x["size"] for x in asks),
                        "total_bid_size": sum(x["size"] for x in bids),
                        "asks": asks,
                        "bids": bids
                    }
                })

        # 3. KIS 호가 조회
        elif exchange == "KIS" and auth_header:
            user_id, token = get_user_id_from_header(auth_header)
            crypto_helper = current_app.crypto
            params = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS", "broker_env": f"eq.{broker_env}"}
            records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
            if records:
                access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                cano = records[0].get("kis_account_no")
                acnt_prdt_cd = records[0].get("kis_account_code", "01")
                kis_env = records[0].get("broker_env", "MOCK")
                
                client = KISClient(appkey=access_key, appsecret=secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=kis_env)
                kis_data = client.get_orderbook(symbol)
                output = kis_data.get("output", {})
                
                asks = []
                bids = []
                for i in range(1, 11):
                    ask_p = float(output.get(f"askp{i}", 0))
                    ask_s = float(output.get(f"askp_rsqn{i}", 0))
                    bid_p = float(output.get(f"bidp{i}", 0))
                    bid_s = float(output.get(f"bidp_rsqn{i}", 0))
                    if ask_p > 0:
                        asks.append({"price": ask_p, "size": ask_s})
                    if bid_p > 0:
                        bids.append({"price": bid_p, "size": bid_s})
                
                asks.sort(key=lambda x: x["price"])
                bids.sort(key=lambda x: x["price"], reverse=True)
                
                base_price = float(output.get("askp1", base_price))
                
                if asks or bids:
                    return jsonify({
                        "success": True,
                        "data": {
                            "symbol": symbol,
                            "timestamp": int(time.time()),
                            "total_ask_size": float(output.get("tot_ask_rsqn", 0)),
                            "total_bid_size": float(output.get("tot_bid_rsqn", 0)),
                            "asks": asks,
                            "bids": bids
                        }
                    })

        # 4. TOSS 호가 조회
        elif exchange == "TOSS" and auth_header:
            user_id, token = get_user_id_from_header(auth_header)
            crypto_helper = current_app.crypto
            params = {"user_id": f"eq.{user_id}", "exchange": "eq.TOSS", "broker_env": f"eq.{broker_env}"}
            records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
            
            # Toss 키가 없을 때 KIS로 우회
            if not records:
                params_kis = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS"}
                records_kis = query_supabase(auth_header, "user_api_keys", "GET", params=params_kis)
                if records_kis:
                    kis_access_key = crypto_helper.decrypt(records_kis[0].get("encrypted_access_key"))
                    kis_secret_key = crypto_helper.decrypt(records_kis[0].get("encrypted_secret_key"))
                    cano = records_kis[0].get("kis_account_no")
                    acnt_prdt_cd = records_kis[0].get("kis_account_code", "01")
                    kis_env = records_kis[0].get("broker_env", "MOCK")
                    
                    client = KISClient(appkey=kis_access_key, appsecret=kis_secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=kis_env)
                    kis_data = client.get_orderbook(symbol)
                    output = kis_data.get("output", {})
                    asks = []
                    bids = []
                    for i in range(1, 11):
                        ask_p = float(output.get(f"askp{i}", 0))
                        ask_s = float(output.get(f"askp_rsqn{i}", 0))
                        bid_p = float(output.get(f"bidp{i}", 0))
                        bid_s = float(output.get(f"bidp_rsqn{i}", 0))
                        if ask_p > 0:
                            asks.append({"price": ask_p, "size": ask_s})
                        if bid_p > 0:
                            bids.append({"price": bid_p, "size": bid_s})
                    asks.sort(key=lambda x: x["price"])
                    bids.sort(key=lambda x: x["price"], reverse=True)
                    
                    base_price = float(output.get("askp1", base_price))
                    
                    return jsonify({
                        "success": True,
                        "data": {
                            "symbol": symbol,
                            "timestamp": int(time.time()),
                            "total_ask_size": float(output.get("tot_ask_rsqn", 0)),
                            "total_bid_size": float(output.get("tot_bid_rsqn", 0)),
                            "asks": asks,
                            "bids": bids
                        }
                    })
            else:
                access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                toss_account_seq = records[0].get("toss_account_seq")
                
                client = TossClient(client_id=access_key, client_secret=secret_key, account_seq=toss_account_seq, env=broker_env)
                toss_data = client.get_orderbook(symbol)
                
                result = {}
                if isinstance(toss_data, dict):
                    result = toss_data.get("result", {})
                elif isinstance(toss_data, list) and len(toss_data) > 0:
                    result = toss_data[0] if isinstance(toss_data[0], dict) else {}
                
                # Toss 호가 스키마에 부합하게 데이터 매핑
                asks = []
                bids = []
                for i in range(1, 11):
                    ask_p = float(result.get(f"askPrice{i}", 0))
                    ask_s = float(result.get(f"askSize{i}", 0))
                    bid_p = float(result.get(f"bidPrice{i}", 0))
                    bid_s = float(result.get(f"bidSize{i}", 0))
                    if ask_p > 0:
                        asks.append({"price": ask_p, "size": ask_s})
                    if bid_p > 0:
                        bids.append({"price": bid_p, "size": bid_s})
                
                asks.sort(key=lambda x: x["price"])
                bids.sort(key=lambda x: x["price"], reverse=True)
                
                base_price = float(result.get("askPrice1", base_price))
                
                if asks or bids:
                    return jsonify({
                        "success": True,
                        "data": {
                            "symbol": symbol,
                            "timestamp": int(time.time()),
                            "total_ask_size": float(result.get("totalAskSize", 0)),
                            "total_bid_size": float(result.get("totalBidSize", 0)),
                            "asks": asks,
                            "bids": bids
                        }
                    })

    except Exception as e:
        current_app.logger.warning(f"실시간 호가 API 조회 실패로 인한 Mock 활성화: {str(e)}")

    # 5. 모든 조회 실패 또는 장외 시간 시 시뮬레이션 Mock 반환
    mock_data = generate_mock_orderbook(symbol, base_price=base_price)
    return jsonify({"success": True, "data": mock_data, "is_mock": True})


@trade_bp.route("/api/chart/trades", methods=["GET"])
def get_trades_api():
    """
    통합 실시간 체결(Trades) 조회 API 엔드포인트.
    거래소 API 장애 또는 장외 시간일 경우 자동으로 가상 체결 시뮬레이션을 생성하여 제공합니다.
    """
    exchange = request.args.get("exchange")
    symbol = request.args.get("symbol")
    broker_env = request.args.get("broker_env", "REAL")

    if not exchange or not symbol:
        return jsonify({"success": False, "message": "exchange 및 symbol 파라미터가 필수적입니다."}), 400

    auth_header = request.headers.get("Authorization")
    # 기본 Mock 기준 가격 조회 시도 (캐시된 캔들 종가가 존재한다면 동적으로 보정)
    base_price = 150000
    cached_close = None
    for cache_key, (expire, candles) in CANDLE_CACHE.items():
        if len(cache_key) >= 4 and cache_key[1].upper() == symbol.upper() and candles:
            cached_close = candles[-1]["close"]
            break
            
    if cached_close is not None and cached_close > 0:
        base_price = cached_close
    else:
        # 캐시가 없는 진입 극초기에는 동기식으로 시세를 직접 1회 조회하여 보정
        try:
            if exchange == "KIS" and auth_header:
                user_id, token = get_user_id_from_header(auth_header)
                crypto_helper = current_app.crypto
                params_db = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS", "broker_env": f"eq.{broker_env}"}
                records = query_supabase(auth_header, "user_api_keys", "GET", params=params_db)
                if records:
                    access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                    secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                    cano = records[0].get("kis_account_no")
                    acnt_prdt_cd = records[0].get("kis_account_code", "01")
                    kis_env = records[0].get("broker_env", "MOCK")
                    client = KISClient(appkey=access_key, appsecret=secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=kis_env)
                    price_info = client.get_price(symbol)
                    if price_info and price_info.get("current_price"):
                        base_price = price_info["current_price"]
            elif exchange == "TOSS" and auth_header:
                user_id, token = get_user_id_from_header(auth_header)
                crypto_helper = current_app.crypto
                params_db = {"user_id": f"eq.{user_id}", "exchange": "eq.TOSS", "broker_env": f"eq.{broker_env}"}
                records = query_supabase(auth_header, "user_api_keys", "GET", params=params_db)
                if records:
                    access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                    secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                    toss_account_seq = records[0].get("toss_account_seq")
                    client = TossClient(client_id=access_key, client_secret=secret_key, account_seq=toss_account_seq, env=broker_env)
                    price_info = client.get_price(symbol)
                    if price_info and price_info.get("current_price"):
                        base_price = price_info["current_price"]
            elif exchange == "COINONE":
                res_c = requests.get(f"https://api.coinone.co.kr/public/v2/ticker/KRW/{symbol.upper()}", timeout=3)
                if res_c.status_code == 200:
                    ticker_data = res_c.json().get("ticker")
                    if ticker_data and ticker_data.get("last"):
                        base_price = float(ticker_data["last"])
            elif exchange == "BINANCE":
                res_b = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": symbol.upper()}, timeout=3)
                if res_b.status_code == 200:
                    price_data = res_b.json()
                    if price_data and price_data.get("price"):
                        base_price = float(price_data["price"])
        except Exception as price_err:
            current_app.logger.warning(f"진입 초기 base_price 실시간 획득 실패: {str(price_err)}")
    
    try:
        # 1. COINONE 체결 조회
        if exchange == "COINONE":
            url = f"https://api.coinone.co.kr/public/v2/trades/KRW/{symbol.upper()}"
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                data = res.json()
                if data.get("result") == "success":
                    trades = []
                    for item in data.get("transactions", [])[:20]:
                        ts = int(item.get("timestamp")) // 1000
                        time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                        side = "SELL" if item.get("is_seller_maker") else "BUY"
                        trades.append({
                            "time": time_str,
                            "timestamp": ts,
                            "price": float(item.get("price")),
                            "qty": float(item.get("qty")),
                            "side": side,
                            "change_rate": 0.0
                        })
                    return jsonify({"success": True, "data": trades})

        # 2. BINANCE 체결 조회
        elif exchange == "BINANCE":
            url = "https://api.binance.com/api/v3/trades"
            res = requests.get(url, params={"symbol": symbol.upper(), "limit": 20}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                trades = []
                for item in data:
                    ts = int(item.get("time")) // 1000
                    time_str = datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                    side = "SELL" if item.get("isBuyerMaker") else "BUY"
                    trades.append({
                        "time": time_str,
                        "timestamp": ts,
                        "price": float(item.get("price")),
                        "qty": float(item.get("qty")),
                        "side": side,
                        "change_rate": 0.0
                    })
                return jsonify({"success": True, "data": trades})

        # 3. KIS 체결 조회
        elif exchange == "KIS" and auth_header:
            user_id, token = get_user_id_from_header(auth_header)
            crypto_helper = current_app.crypto
            params = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS", "broker_env": f"eq.{broker_env}"}
            records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
            if records:
                access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                cano = records[0].get("kis_account_no")
                acnt_prdt_cd = records[0].get("kis_account_code", "01")
                kis_env = records[0].get("broker_env", "MOCK")
                
                client = KISClient(appkey=access_key, appsecret=secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=kis_env)
                kis_data = client.get_trades(symbol)
                output2 = kis_data.get("output2", [])
                
                trades = []
                for item in output2[:20]:
                    t_str = item.get("stck_cntg_hour")  # "HHMMSS"
                    try:
                        time_str = f"{t_str[0:2]}:{t_str[2:4]}:{t_str[4:6]}"
                    except IndexError:
                        time_str = t_str
                        
                    price_val = float(item.get("stck_prpr", 0))
                    qty_val = float(item.get("cntg_vol", 0))
                    
                    # 1:매수체결, 5:매도체결
                    side = "SELL" if item.get("tday_ccld_xe_yn") == "5" else "BUY"
                    
                    trades.append({
                        "time": time_str,
                        "timestamp": int(time.time()),
                        "price": price_val,
                        "qty": qty_val,
                        "side": side,
                        "change_rate": float(item.get("prdy_ctrt", 0.0))
                    })
                
                if output2:
                    base_price = float(output2[0].get("stck_prpr", base_price))
                    return jsonify({"success": True, "data": trades})

        # 4. TOSS 체결 조회
        elif exchange == "TOSS" and auth_header:
            user_id, token = get_user_id_from_header(auth_header)
            crypto_helper = current_app.crypto
            params = {"user_id": f"eq.{user_id}", "exchange": "eq.TOSS", "broker_env": f"eq.{broker_env}"}
            records = query_supabase(auth_header, "user_api_keys", "GET", params=params)
            
            # Toss 키가 없을 때 KIS로 우회
            if not records:
                params_kis = {"user_id": f"eq.{user_id}", "exchange": "eq.KIS"}
                records_kis = query_supabase(auth_header, "user_api_keys", "GET", params=params_kis)
                if records_kis:
                    kis_access_key = crypto_helper.decrypt(records_kis[0].get("encrypted_access_key"))
                    kis_secret_key = crypto_helper.decrypt(records_kis[0].get("encrypted_secret_key"))
                    cano = records_kis[0].get("kis_account_no")
                    acnt_prdt_cd = records_kis[0].get("kis_account_code", "01")
                    kis_env = records_kis[0].get("broker_env", "MOCK")
                    
                    client = KISClient(appkey=kis_access_key, appsecret=kis_secret_key, cano=cano, acnt_prdt_cd=acnt_prdt_cd, env=kis_env)
                    kis_data = client.get_trades(symbol)
                    output2 = kis_data.get("output2", [])
                    trades = []
                    for item in output2[:20]:
                        t_str = item.get("stck_cntg_hour")
                        try:
                            time_str = f"{t_str[0:2]}:{t_str[2:4]}:{t_str[4:6]}"
                        except IndexError:
                            time_str = t_str
                        trades.append({
                            "time": time_str,
                            "timestamp": int(time.time()),
                            "price": float(item.get("stck_prpr", 0)),
                            "qty": float(item.get("cntg_vol", 0)),
                            "side": "SELL" if item.get("tday_ccld_xe_yn") == "5" else "BUY",
                            "change_rate": float(item.get("prdy_ctrt", 0.0))
                        })
                    
                    if output2:
                        base_price = float(output2[0].get("stck_prpr", base_price))
                    return jsonify({"success": True, "data": trades})
            else:
                access_key = crypto_helper.decrypt(records[0].get("encrypted_access_key"))
                secret_key = crypto_helper.decrypt(records[0].get("encrypted_secret_key"))
                toss_account_seq = records[0].get("toss_account_seq")
                
                client = TossClient(client_id=access_key, client_secret=secret_key, account_seq=toss_account_seq, env=broker_env)
                toss_data = client.get_trades(symbol)
                
                raw_trades = []
                if isinstance(toss_data, list):
                    raw_trades = toss_data
                elif isinstance(toss_data, dict):
                    result = toss_data.get("result", {})
                    if isinstance(result, list):
                        raw_trades = result
                    elif isinstance(result, dict):
                        raw_trades = result.get("trades", [])
                
                trades = []
                for item in raw_trades[:20]:
                    trades.append({
                        "time": item.get("timestamp", "").split(" ")[1] if " " in item.get("timestamp", "") else item.get("timestamp"),
                        "timestamp": int(time.time()),
                        "price": float(item.get("price", 0)),
                        "qty": float(item.get("quantity", 0)),
                        "side": item.get("side", "BUY").upper(),
                        "change_rate": float(item.get("changeRate", 0))
                    })
                
                if raw_trades:
                    base_price = float(raw_trades[0].get("price", base_price))
                    
                if trades:
                    return jsonify({"success": True, "data": trades})

    except Exception as e:
        current_app.logger.warning(f"실시간 체결 API 조회 실패로 인한 Mock 활성화: {str(e)}")

    # 5. 모든 조회 실패 또는 장외 시간 시 시뮬레이션 Mock 반환
    mock_data = generate_mock_trades(symbol, base_price=base_price)
    return jsonify({"success": True, "data": mock_data, "is_mock": True})


@trade_bp.route("/api/symbol/lookup", methods=["GET"])
def lookup_symbol():
    """
    종목명(예: 'SK하이닉스', '하이닉스') 또는 심볼(예: '000660', 'BTC')을 기반으로
    정밀 매핑된 종목코드와 자산 타입(STOCK | CRYPTO)을 찾아 반환합니다.
    """
    query = request.args.get("query", "").strip().upper()
    if not query:
        return jsonify({"success": False, "message": "query 파라미터가 필수적입니다."}), 400

    from backend.services.symbol_metadata import SYMBOL_METADATA

    # 1. 완전 일치 매칭 (종목코드 또는 display_name)
    for sym, meta in SYMBOL_METADATA.items():
        if sym.upper() == query or meta.get("display_name", "").upper() == query:
            return jsonify({
                "success": True,
                "data": {
                    "symbol": sym,
                    "display_name": meta.get("display_name"),
                    "asset_type": meta.get("asset_type"),
                    "market": meta.get("market")
                }
            })

    # 2. 부분 일치 매칭
    for sym, meta in SYMBOL_METADATA.items():
        if query in meta.get("display_name", "").upper() or query in sym:
            return jsonify({
                "success": True,
                "data": {
                    "symbol": sym,
                    "display_name": meta.get("display_name"),
                    "asset_type": meta.get("asset_type"),
                    "market": meta.get("market")
                }
            })

    # 3. 매칭 실패 시 기본값 반환 (Toss 등 신규 등록 주식/코인 대비)
    return jsonify({
        "success": True,
        "data": {
            "symbol": query,
            "display_name": query,
            "asset_type": "STOCK",
            "market": ""
        }
    })


@trade_bp.route("/api/symbol/search", methods=["GET"])
def search_symbols():
    """
    종목명 또는 심볼의 부분 입력을 받아 매칭되는 후보군 최대 10개를 자동완성용 목록으로 리턴합니다.
    """
    query = request.args.get("query", "").strip().upper()
    if not query:
        return jsonify({"success": True, "data": []})

    from backend.services.symbol_metadata import SYMBOL_METADATA
    results = []

    for sym, meta in SYMBOL_METADATA.items():
        display_name = meta.get("display_name", "")
        # 종목코드 또는 display_name에 입력어가 포함되어 있는지 체크
        if query in sym or query in display_name.upper():
            results.append({
                "symbol": sym,
                "display_name": display_name,
                "asset_type": meta.get("asset_type"),
                "market": meta.get("market")
            })

    # 가독성을 위해 코드 길이 순 및 사전 순 정렬
    results.sort(key=lambda x: (len(x["symbol"]), x["display_name"]))

    return jsonify({"success": True, "data": results[:10]})
