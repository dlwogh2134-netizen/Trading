"""가상자산 위탁운용의 ML 후보와 보류 사유를 구성한다."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class AiFundCryptoSelectionService:
    """스케줄러와 운영 화면이 공통으로 쓰는 코인 ML 후보 조회 서비스."""

    def __init__(self, predictions_path: Path):
        self.predictions_path = predictions_path

    def get_snapshot(self, min_confidence_score: float, limit: int = 20) -> dict:
        rows = self._load_rows()
        threshold_score = min_confidence_score * 100.0
        long_rows = [row for row in rows if str(row.get("position") or "").upper() == "LONG"]
        qualified_rows = [row for row in long_rows if _as_float(row.get("signal_score")) >= threshold_score]
        qualified_rows.sort(key=lambda row: _as_float(row.get("signal_score")), reverse=True)

        candidates = [self._to_candidate(row) for row in qualified_rows[:limit]]
        if not rows:
            status, message = "NO_PREDICTIONS", "코인 ML 예측 결과를 찾지 못했습니다."
        elif not long_rows:
            status, message = "NO_LONG_SIGNAL", "현재 모델이 매수 신호를 내지 않아 코인 후보를 보류했습니다."
        elif not qualified_rows:
            status, message = "LOW_CONFIDENCE", f"상승 신호는 있으나 설정 확신도 {min_confidence_score * 100:.0f}%에 미달해 보류했습니다."
        else:
            status, message = "READY", "상승 신호와 확신도 기준을 통과한 코인 후보가 있습니다."

        return {
            "candidates": candidates,
            "availability": {
                "status": status,
                "message": message,
                "total_count": len(rows),
                "long_count": len(long_rows),
                "qualified_count": len(qualified_rows),
            },
        }

    def _load_rows(self) -> list[dict]:
        if not self.predictions_path.exists():
            return []
        with self.predictions_path.open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def _to_candidate(self, row: dict) -> dict:
        score = _as_float(row.get("signal_score"))
        symbol = str(row.get("symbol") or "").upper()
        model_version = str(row.get("model_version") or "")
        prediction_date = str(row.get("date") or "")
        return {
            "symbol": symbol,
            "confidence_score": min(1.0, max(0.0, score / 100.0)),
            "source_exchange": str(row.get("exchange") or "").upper(),
            "model_version": model_version,
            "signal_id": f"crypto:{model_version}:{prediction_date}:{symbol}:{score}",
            "selection_reason": "상승 신호와 확신도 기준을 통과했습니다.",
        }
