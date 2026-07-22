"""
AI 위탁 자동매매 스케줄러 (admin_ai_fund_trading_scheduler.py)

- DB의 admin_ai_fund_configs (is_active=true) 설정을 읽어 활성 거래소별로 루프 실행
- ML predictions CSV (crypto_predictions_lgbm_v10.csv) 에서 신호를 읽어 임계값 이상이면 실행
- AdminAiManagedTrader.evaluate_and_execute_signal() 을 통해 주문 + 로그 처리
- 각 거래소별 1건씩 분산 락(lock) 확보 후 실행 → 중복 주문 방지
"""
import logging
import os
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# crypto v10 예측 CSV 경로 (ml/configs/lgbm_crypto_v10.yaml 기준)
CRYPTO_PREDICTIONS_PATH = PROJECT_ROOT / "ml" / "data" / "processed" / "crypto_predictions_lgbm_v10.csv"

_ai_fund_started = False


def _load_active_configs() -> list[dict]:
    """admin_ai_fund_configs 에서 is_active=true 설정 목록을 조회합니다."""
    try:
        from backend.services.supabase_client import safe_query_supabase_as_service_role
        configs = safe_query_supabase_as_service_role(
            "admin_ai_fund_configs",
            params={"is_active": "eq.true"},
        ) or []
        return configs
    except Exception as e:
        logger.warning(f"[AiFundScheduler] 설정 조회 실패: {e}")
        return []


def _read_crypto_signals(min_confidence_score: float) -> list[dict]:
    """
    crypto_predictions_lgbm_v10.csv 에서 LONG 신호 중
    signal_score >= min_confidence_score * 100 인 종목을 반환합니다.
    """
    try:
        if not CRYPTO_PREDICTIONS_PATH.exists():
            logger.warning(f"[AiFundScheduler] 예측 파일 없음: {CRYPTO_PREDICTIONS_PATH}")
            return []

        import pandas as pd
        df = pd.read_csv(CRYPTO_PREDICTIONS_PATH, dtype={"symbol": "string"})

        threshold_score = min_confidence_score * 100.0
        mask = (
            (df["position"].str.upper() == "LONG") &
            (df["signal_score"] >= threshold_score)
        )
        candidates = df[mask].sort_values("signal_score", ascending=False)

        signals = []
        for _, row in candidates.iterrows():
            signals.append({
                "symbol": str(row["symbol"]),
                "confidence_score": float(row["signal_score"]) / 100.0,
                "exchange": str(row.get("exchange", "")).upper(),
            })
        return signals

    except Exception as e:
        logger.warning(f"[AiFundScheduler] 예측 파일 읽기 실패: {e}")
        return []


def _get_current_price_coinone(symbol: str) -> float | None:
    """코인원 현재가를 조회합니다. 실패 시 None 반환."""
    try:
        from backend.services.coinone_client import CoinoneClient
        client = CoinoneClient.__new__(CoinoneClient)  # 인증 없이 퍼블릭 API만 사용
        client.access_token = ""
        client.secret_key = b""
        client.base_url = "https://api.coinone.co.kr"
        price_data = client.get_price(symbol)
        price = price_data.get("current_price") or price_data.get("last") or price_data.get("close")
        if price:
            return float(price)
    except Exception as e:
        logger.warning(f"[AiFundScheduler] 코인원 현재가 조회 실패 ({symbol}): {e}")
    return None


def _build_exchange_client(exchange_type: str, config: dict):
    """거래소 클라이언트 인스턴스를 생성합니다. 현재 coinone 지원."""
    exchange = exchange_type.lower()
    if exchange == "coinone":
        from backend.services.coinone_client import CoinoneClient
        access_token = os.getenv("COINONE_ACCESS_TOKEN", "") or os.getenv("COINONE_API_KEY", "")
        secret_key = os.getenv("COINONE_SECRET_KEY", "")
        return CoinoneClient(access_token=access_token, secret_key=secret_key)
    # toss / binance 는 향후 추가
    return None


def _run_ai_fund_cycle() -> None:
    """
    1. 활성 AI 펀드 설정 목록 조회
    2. 거래소별로 ML 신호 읽기
    3. 임계값 초과 신호에 대해 evaluate_and_execute_signal() 실행
    """
    configs = _load_active_configs()
    if not configs:
        return

    from backend.services.admin_ai_managed_trader import AdminAiManagedTrader

    # 거래소별로 configs 그룹화 (여러 user_id가 같은 거래소를 쓸 수 있음)
    for cfg in configs:
        user_id = cfg.get("user_id", "")
        exchange_type = str(cfg.get("exchange_type", "coinone")).lower()
        min_confidence = float(cfg.get("min_signal_confidence", 0.75))
        max_position_size = float(cfg.get("max_position_size", 0.0))

        if not user_id or max_position_size <= 0:
            continue

        # 현재 코인 ML 신호만 지원 (코인원/바이낸스 공통 coinone 예측 CSV 사용)
        if exchange_type not in {"coinone", "binance", "toss"}:
            continue

        signals = _read_crypto_signals(min_confidence)
        if not signals:
            logger.info(
                f"[AiFundScheduler] 확신도 {min_confidence * 100:.0f}% 초과 신호 없음 "
                f"(user={user_id[:8]}, exchange={exchange_type})"
            )
            continue

        trader = AdminAiManagedTrader(user_id=user_id, exchange_type=exchange_type)
        client = _build_exchange_client(exchange_type, cfg)

        # 거래소 클라이언트가 없으면 시뮬레이션 로그만 기록
        if client is None:
            logger.info(
                f"[AiFundScheduler] {exchange_type} 클라이언트 미구현 — "
                f"신호 포착: {[s['symbol'] for s in signals[:3]]} (dry-run 로그)"
            )
            # dry-run: 로그만 insert (실제 주문 없음)
            for sig in signals[:1]:
                try:
                    from backend.services.supabase_client import safe_query_supabase_as_service_role
                    safe_query_supabase_as_service_role(
                        "admin_ai_trade_logs",
                        method="POST",
                        json_data={
                            "user_id": user_id,
                            "exchange_type": exchange_type,
                            "symbol": sig["symbol"],
                            "side": "BUY",
                            "confidence_score": sig["confidence_score"],
                            "executed_price": 0.0,
                            "executed_qty": 0.0,
                            "total_amount": 0.0,
                            "order_id": None,
                            "status": "DRY_RUN",
                        },
                    )
                except Exception as log_err:
                    logger.warning(f"[AiFundScheduler] dry-run 로그 실패: {log_err}")
            continue

        # 실제 주문: 상위 1건만 (과도한 주문 방지)
        top_signal = signals[0]
        symbol = top_signal["symbol"]
        confidence = top_signal["confidence_score"]

        current_price = _get_current_price_coinone(symbol) if exchange_type == "coinone" else None
        if not current_price or current_price <= 0:
            logger.warning(f"[AiFundScheduler] 현재가 조회 실패 ({symbol}) — 매수 건너뜀")
            continue

        try:
            result = trader.evaluate_and_execute_signal(
                symbol=symbol,
                signal_type="BUY",
                confidence_score=confidence,
                current_price=current_price,
                exchange_client=client,
            )
            if result:
                logger.info(
                    f"[AiFundScheduler] BUY 체결 완료 — {symbol} "
                    f"@ {current_price:,.0f} (확신도 {confidence * 100:.1f}%)"
                )
            else:
                logger.info(f"[AiFundScheduler] BUY 조건 미충족 또는 락 점유 — {symbol}")
        except Exception as exec_err:
            logger.exception(f"[AiFundScheduler] 주문 실행 오류 ({symbol}): {exec_err}")


def start_ai_fund_trading_scheduler(
    enabled: bool = True,
    interval_seconds: int = 30,
) -> None:
    """
    AI 위탁 자동매매 스케줄러를 백그라운드 스레드로 구동합니다.

    Args:
        enabled: 환경변수 AI_FUND_TRADING_ENABLED 기반 활성화 여부
        interval_seconds: 실행 주기 (기본 30초)
    """
    global _ai_fund_started
    if _ai_fund_started or not enabled:
        if not enabled:
            logger.info("[AiFundScheduler] AI 위탁 자동매매 스케줄러 비활성화됨 (enabled=false)")
        return

    _ai_fund_started = True
    logger.info(
        f"[AiFundScheduler] AI 위탁 자동매매 스케줄러 시작 "
        f"(주기: {interval_seconds}초, 예측파일: {CRYPTO_PREDICTIONS_PATH.name})"
    )

    def _loop() -> None:
        # 첫 실행 지연 (다른 스케줄러 기동 완료 대기)
        time.sleep(15)
        while True:
            try:
                _run_ai_fund_cycle()
            except Exception as loop_err:
                logger.exception(f"[AiFundScheduler] 루프 오류: {loop_err}")
            time.sleep(interval_seconds)

    thread = threading.Thread(target=_loop, daemon=True, name="ai-fund-trading-scheduler")
    thread.start()
