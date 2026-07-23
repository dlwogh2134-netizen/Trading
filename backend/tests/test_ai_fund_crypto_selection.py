from backend.services.ai_fund_crypto_selection import AiFundCryptoSelectionService


def test_crypto_candidates_use_the_same_long_signal_threshold_as_the_scheduler(tmp_path):
    predictions = tmp_path / "crypto_predictions.csv"
    predictions.write_text(
        "exchange,symbol,position,signal_score,model_version,date\n"
        "BINANCE,BTCUSDT,LONG,82,lgbm_crypto_signal_v10,2026-07-22\n"
        "BINANCE,ETHUSDT,LONG,70,lgbm_crypto_signal_v10,2026-07-22\n",
        encoding="utf-8",
    )
    service = AiFundCryptoSelectionService(predictions)

    snapshot = service.get_snapshot(min_confidence_score=0.75)

    assert [candidate["symbol"] for candidate in snapshot["candidates"]] == ["BTCUSDT"]
    assert snapshot["availability"]["status"] == "READY"
    assert snapshot["candidates"][0]["selection_reason"] == "상승 신호와 확신도 기준을 통과했습니다."


def test_crypto_snapshot_explains_korean_hold_reason_when_no_long_signal_exists(tmp_path):
    predictions = tmp_path / "crypto_predictions.csv"
    predictions.write_text(
        "exchange,symbol,position,signal_score,model_version,date\n"
        "BINANCE,BTCUSDT,HOLD,0,lgbm_crypto_signal_v10,2026-07-22\n",
        encoding="utf-8",
    )
    service = AiFundCryptoSelectionService(predictions)

    snapshot = service.get_snapshot(min_confidence_score=0.75)

    assert snapshot["candidates"] == []
    assert snapshot["availability"] == {
        "status": "NO_LONG_SIGNAL",
        "message": "현재 모델이 매수 신호를 내지 않아 코인 후보를 보류했습니다.",
        "total_count": 1,
        "long_count": 0,
        "qualified_count": 0,
    }
