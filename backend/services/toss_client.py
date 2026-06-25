import os
import json
import time
import uuid
import requests
from datetime import datetime, timedelta, timezone
from backend.services.exchange_client import ExchangeClient

KST = timezone(timedelta(hours=9))

TOSS_TOKEN_CACHE_FILE = ".toss_token_cache.json"

class TossClient(ExchangeClient):
    """
    토스증권 Open API 연동 및 연결 검증을 담당하는 클라이언트 클래스입니다.
    """
    def __init__(self, client_id: str, client_secret: str, account_seq: str = None, env: str = "MOCK"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_seq = account_seq
        self.env = env.upper()
        self.base_url = "https://openapi.tossinvest.com"

    def _clear_token_cache(self):
        """
        로컬 캐시 파일에서 현재 client_id에 해당하는 토큰 정보를 삭제하여 갱신을 강제합니다.
        """
        cache = {}
        if os.path.exists(TOSS_TOKEN_CACHE_FILE):
            try:
                with open(TOSS_TOKEN_CACHE_FILE, "r") as f:
                    cache = json.load(f)
            except Exception:
                pass
        if self.client_id in cache:
            del cache[self.client_id]
            try:
                with open(TOSS_TOKEN_CACHE_FILE, "w") as f:
                    json.dump(cache, f, indent=2)
            except Exception:
                pass

    def _get_cached_token(self) -> str:
        """
        로컬 캐시 파일에서 토스 Access Token을 가져옵니다.
        토큰이 만료되었거나 캐시가 없으면 새로 발급을 요청합니다.
        """
        cache = {}
        if os.path.exists(TOSS_TOKEN_CACHE_FILE):
            try:
                with open(TOSS_TOKEN_CACHE_FILE, "r") as f:
                    cache = json.load(f)
            except Exception:
                pass

        client_cache = cache.get(self.client_id, {})
        token = client_cache.get("access_token")
        expired_at_str = client_cache.get("expired_at")

        if token and expired_at_str:
            try:
                expired_at = datetime.strptime(expired_at_str, "%Y-%m-%d %H:%M:%S")
                # 만료 5분 전(300초) 이상 남아있는 경우에만 기존 토큰 사용
                if (expired_at - datetime.now()).total_seconds() > 300:
                    return token
            except Exception:
                pass

        # 토큰 새로 발급
        token_data = self._request_new_token()
        new_token = token_data["access_token"]
        expires_in = int(token_data.get("expires_in", 86400))

        expired_at = datetime.now() + timedelta(seconds=expires_in)
        cache[self.client_id] = {
            "access_token": new_token,
            "expired_at": expired_at.strftime("%Y-%m-%d %H:%M:%S")
        }

        try:
            with open(TOSS_TOKEN_CACHE_FILE, "w") as f:
                json.dump(cache, f, indent=2)
        except Exception:
            pass

        return new_token

    def _request_new_token(self) -> dict:
        """
        토스 API 서버로부터 새로운 OAuth2 액세스 토큰을 발급받습니다.
        """
        url = f"{self.base_url}/oauth2/token"
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        res = requests.post(url, data=payload, headers=headers)
        if res.status_code != 200:
            err_data = {}
            try:
                err_data = res.json()
            except Exception:
                pass
            err_msg = err_data.get("error_description") or err_data.get("error") or res.text
            raise Exception(f"토스 토큰 발급 실패: {err_msg}")
        return res.json()

    def _get_accounts_impl(self) -> list:
        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/accounts"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        res = requests.get(url, headers=headers)
        
        if res.status_code != 200:
            fallback_url = f"{self.base_url}/v1/accounts"
            res = requests.get(fallback_url, headers=headers)

        if res.status_code != 200:
            raise Exception(f"토스 계좌 목록 조회 실패 (상태 코드 {res.status_code}): {res.text}")

        data = res.json()
        if "error" in data:
            err = data["error"]
            raise Exception(f"토스 계좌 조회 에러 [{err.get('code')}]: {err.get('message')} (Request ID: {err.get('requestId')})")

        result = data.get("result", [])
        if isinstance(result, dict):
            accounts = result.get("accounts", [])
        else:
            accounts = result

        return accounts

    def get_accounts(self) -> list:
        """
        사용자의 계좌 목록 정보를 가져옵니다. (토큰 만료 시 재시도 포함)
        """
        try:
            return self._get_accounts_impl()
        except Exception as e:
            err_str = str(e).lower()
            if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                self._clear_token_cache()
                return self._get_accounts_impl()
            raise e

    def _get_balance_impl(self) -> dict:
        if not self.account_seq:
            accounts = self.get_accounts()
            if not accounts:
                raise Exception("조회 가능한 토스 계좌가 존재하지 않습니다.")
            self.account_seq = accounts[0].get("accountSeq")

        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/holdings"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tossinvest-Account": self.account_seq,
            "Content-Type": "application/json"
        }
        res = requests.get(url, headers=headers)

        if res.status_code != 200:
            fallback_url = f"{self.base_url}/v1/accounts/holdings"
            res = requests.get(fallback_url, headers=headers)

        if res.status_code != 200:
            raise Exception(f"토스 보유 종목 조회 실패 (상태 코드 {res.status_code}): {res.text}")

        data = res.json()
        if "error" in data:
            err = data["error"]
            raise Exception(f"토스 보유자산 조회 에러 [{err.get('code')}]: {err.get('message')}")

        result = data.get("result", {})
        holdings_list = []
        raw_holdings = []
        if isinstance(result, dict):
            raw_holdings = result.get("holdings", [])
        elif isinstance(result, list):
            raw_holdings = result

        total_eval = 0.0
        available_cash = 0.0

        if isinstance(result, dict):
            try:
                total_eval = float(result.get("totalEvaluationAmount", 0.0))
                available_cash = float(result.get("availableCash", 0.0))
            except (ValueError, TypeError):
                pass

        for stock in raw_holdings:
            symbol = stock.get("symbol", "")
            name = stock.get("name", "")
            try:
                qty = float(stock.get("quantity", 0.0))
                avg_price = float(stock.get("averageBuyPrice", 0.0))
                current_price = float(stock.get("currentPrice", 0.0))
                profit = float(stock.get("evaluationProfitLoss", 0.0))
                profit_rate = float(stock.get("evaluationProfitLossRate", 0.0))
            except (ValueError, TypeError):
                qty = 0.0
                avg_price = 0.0
                current_price = 0.0
                profit = 0.0
                profit_rate = 0.0

            if qty <= 0:
                continue

            holdings_list.append({
                "symbol": symbol,
                "name": name,
                "qty": qty,
                "avg_price": avg_price,
                "current_price": current_price,
                "profit": profit,
                "profit_rate": profit_rate
            })

            if total_eval == 0.0:
                total_eval += current_price * qty

        if total_eval == 0.0:
            total_eval = available_cash

        return {
            "total_evaluation": total_eval,
            "available_cash": available_cash,
            "holdings": holdings_list
        }

    def get_balance(self) -> dict:
        """
        보유 자산 정보를 조회합니다. (토큰 만료 시 재시도 포함)
        """
        try:
            return self._get_balance_impl()
        except Exception as e:
            err_str = str(e).lower()
            if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                self._clear_token_cache()
                return self._get_balance_impl()
            raise e

    def _get_price_impl(self, symbol: str) -> dict:
        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/prices"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        params = {"symbol": symbol}
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code != 200:
            raise Exception(f"토스 시세 조회 실패: {res.text}")
            
        data = res.json()
        result = data.get("result", {})
        
        try:
            current_price = float(result.get("currentPrice", 0.0))
            change_rate = float(result.get("changeRate", 0.0))
        except (ValueError, TypeError):
            current_price = 0.0
            change_rate = 0.0

        return {
            "current_price": current_price,
            "change_rate": change_rate,
            "raw": data
        }

    def get_price(self, symbol: str) -> dict:
        """
        현재가를 조회합니다. (토큰 만료 시 재시도 포함)
        """
        try:
            return self._get_price_impl(symbol)
        except Exception as e:
            err_str = str(e).lower()
            if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                self._clear_token_cache()
                return self._get_price_impl(symbol)
            raise e

    def _place_order_impl(self, symbol: str, qty: float, side: str, ord_type: str, price: float = None) -> dict:
        if self.env == "MOCK":
            return {
                "order_id": f"MOCK-TOSS-{int(time.time())}",
                "status": "ORDERED",
                "raw": {"symbol": symbol, "qty": qty, "side": side, "ord_type": ord_type}
            }
            
        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/orders"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tossinvest-Account": self.account_seq,
            "Content-Type": "application/json"
        }
        client_order_id = f"toss-{uuid.uuid4().hex[:16]}"
        payload = {
            "clientOrderId": client_order_id,
            "symbol": symbol,
            "quantity": qty,
            "side": side.upper(),
            "orderType": ord_type.upper(),
        }
        if price:
            payload["price"] = price

        res = requests.post(url, json=payload, headers=headers)
        if res.status_code != 200:
            raise Exception(f"토스 주문 접수 실패: {res.text}")

        data = res.json()
        result = data.get("result", {})
        return {
            "order_id": result.get("orderId"),
            "status": result.get("status"),
            "raw": data
        }

    def place_order(self, symbol: str, qty: float, side: str, ord_type: str, price: float = None) -> dict:
        """
        주문을 접수합니다. (토큰 만료 시 재시도 포함)
        """
        try:
            return self._place_order_impl(symbol, qty, side, ord_type, price)
        except Exception as e:
            err_str = str(e).lower()
            if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                self._clear_token_cache()
                return self._place_order_impl(symbol, qty, side, ord_type, price)
            raise e

    def _get_order_status_impl(self, order_id: str) -> dict:
        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/orders/{order_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tossinvest-Account": self.account_seq,
            "Content-Type": "application/json"
        }
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            raise Exception(f"토스 주문 조회 실패: {res.text}")

        data = res.json()
        result = data.get("result", {})
        return {
            "order_id": result.get("orderId"),
            "status": result.get("status"),
            "qty": float(result.get("quantity", 0)),
            "executed_qty": float(result.get("executedQuantity", 0)),
            "raw": data
        }

    def get_order_status(self, order_id: str) -> dict:
        """
        주문 상태를 조회합니다. (토큰 만료 시 재시도 포함)
        """
        try:
            return self._get_order_status_impl(order_id)
        except Exception as e:
            err_str = str(e).lower()
            if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                self._clear_token_cache()
                return self._get_order_status_impl(order_id)
            raise e

    def _get_candles_impl(self, symbol: str, interval: str = "1d", count: int = 120) -> list:
        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/candles"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        params = {
            "symbol": symbol,
            "interval": interval,
            "count": min(count, 200),
            "adjusted": "true"
        }
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200:
            raise Exception(f"Toss get_candles failed: {res.text}")
            
        data = res.json()
        if "error" in data:
            err = data["error"]
            raise Exception(f"Toss get_candles error [{err.get('code')}]: {err.get('message')}")
            
        result = data.get("result", {})
        candles = []
        is_intraday = interval not in ("1d", "1w", "1M", "day", "week", "month", "D", "W", "M")
        
        for candle in result.get("candles", []):
            try:
                timestamp = candle.get("timestamp", "")
                if is_intraday:
                    try:
                        dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                        dt = dt.replace(tzinfo=KST)
                        time_val = int(dt.timestamp())
                    except ValueError:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            dt = dt.astimezone(KST)
                            time_val = int(dt.timestamp())
                        except ValueError:
                            time_val = timestamp
                else:
                    time_val = timestamp.split(" ")[0] if " " in timestamp else timestamp
                    
                candles.append({
                    "time": time_val,
                    "open": float(candle.get("openPrice", 0)),
                    "high": float(candle.get("highPrice", 0)),
                    "low": float(candle.get("lowPrice", 0)),
                    "close": float(candle.get("closePrice", 0)),
                    "volume": float(candle.get("volume", 0))
                })
            except (ValueError, TypeError):
                pass
                
        seen = set()
        unique_candles = []
        for c in candles:
            if c["time"] not in seen:
                seen.add(c["time"])
                unique_candles.append(c)
                
        unique_candles.sort(key=lambda x: x["time"])
        return unique_candles

    def get_candles(self, symbol: str, interval: str = "1d", count: int = 120) -> list:
        """
        주식 캔들 데이터를 조회합니다. 미지원 주기(5m, 15m, 30m, 1h, 1w, 1M 등)일 경우 자체 리샘플링하여 반환합니다.
        (토큰 만료 시 자동 재시도 포함)
        """
        normalized_interval = interval
        if interval in ("1d", "D", "day"):
            normalized_interval = "1d"
        elif interval in ("1m", "minute"):
            normalized_interval = "1m"

        # 1. 토스 네이티브 지원 주기인 경우 바로 호출
        if normalized_interval in ("1d", "1m"):
            try:
                return self._get_candles_impl(symbol, interval=normalized_interval, count=count)
            except Exception as e:
                err_str = str(e).lower()
                if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                    self._clear_token_cache()
                    return self._get_candles_impl(symbol, interval=normalized_interval, count=count)
                raise e

        # 2. 토스 미지원 주기인 경우 자체 리샘플링
        # 2-A. 분봉/시간봉 리샘플링 (5m, 15m, 30m, 1h, 60m 등)
        if normalized_interval in ("5m", "15m", "30m", "60m", "1h"):
            interval_minutes = 5
            if normalized_interval == "15m":
                interval_minutes = 15
            elif normalized_interval == "30m":
                interval_minutes = 30
            elif normalized_interval in ("60m", "1h"):
                interval_minutes = 60

            # 1분봉 데이터를 최대한 많이 가져옴 (리샘플링하기 위해 count보다 넉넉히 가져옴, 최대 200개 한계)
            raw_candles = self.get_candles(symbol, interval="1m", count=200)
            if not raw_candles:
                return []

            interval_seconds = interval_minutes * 60
            buckets = {}
            for c in raw_candles:
                try:
                    ts = int(c["time"])
                except (ValueError, TypeError):
                    continue
                bucket_ts = (ts // interval_seconds) * interval_seconds
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = []
                buckets[bucket_ts].append(c)

            resampled = []
            for b_ts, c_list in sorted(buckets.items()):
                resampled.append({
                    "time": b_ts,
                    "open": c_list[0]["open"],
                    "high": max(x["high"] for x in c_list),
                    "low": min(x["low"] for x in c_list),
                    "close": c_list[-1]["close"],
                    "volume": sum(x["volume"] for x in c_list)
                })
            return resampled[-count:]

        # 2-B. 주봉/월봉 리샘플링 (1w, W, 1M, M 등)
        elif normalized_interval in ("1w", "W", "week", "1M", "M", "month"):
            raw_candles = self.get_candles(symbol, interval="1d", count=200)
            if not raw_candles:
                return []

            buckets = {}
            is_week = normalized_interval in ("1w", "W", "week")

            for c in raw_candles:
                date_str = c["time"]
                try:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    continue

                if is_week:
                    monday = dt - timedelta(days=dt.weekday())
                    bucket_key = monday.strftime("%Y-%m-%d")
                else:
                    bucket_key = dt.strftime("%Y-%m-01")

                if bucket_key not in buckets:
                    buckets[bucket_key] = []
                buckets[bucket_key].append(c)

            resampled = []
            for b_key, c_list in sorted(buckets.items()):
                resampled.append({
                    "time": b_key,
                    "open": c_list[0]["open"],
                    "high": max(x["high"] for x in c_list),
                    "low": min(x["low"] for x in c_list),
                    "close": c_list[-1]["close"],
                    "volume": sum(x["volume"] for x in c_list)
                })
            return resampled[-count:]

        # 3. 그 외의 경우 일봉으로 폴백
        return self.get_candles(symbol, interval="1d", count=count)

    def _get_orderbook_impl(self, symbol: str) -> dict:
        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/orderbook"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        res = requests.get(url, headers=headers, params={"symbol": symbol})
        if res.status_code != 200:
            raise Exception(f"토스 호가 조회 실패: {res.text}")
        return res.json()

    def get_orderbook(self, symbol: str) -> dict:
        """
        종목코드에 해당하는 호가 정보(Orderbook)를 가져옵니다. (토큰 만료 시 재시도 포함)
        """
        try:
            return self._get_orderbook_impl(symbol)
        except Exception as e:
            err_str = str(e).lower()
            if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                self._clear_token_cache()
                return self._get_orderbook_impl(symbol)
            raise e

    def _get_trades_impl(self, symbol: str) -> dict:
        token = self._get_cached_token()
        url = f"{self.base_url}/api/v1/trades"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        res = requests.get(url, headers=headers, params={"symbol": symbol})
        if res.status_code != 200:
            raise Exception(f"토스 체결 조회 실패: {res.text}")
        return res.json()

    def get_trades(self, symbol: str) -> dict:
        """
        종목코드에 해당하는 실시간 체결 정보(Trades)를 가져옵니다. (토큰 만료 시 재시도 포함)
        """
        try:
            return self._get_trades_impl(symbol)
        except Exception as e:
            err_str = str(e).lower()
            if "invalid-token" in err_str or "invalid_token" in err_str or "unauthorized" in err_str or "401" in err_str:
                self._clear_token_cache()
                return self._get_trades_impl(symbol)
            raise e
