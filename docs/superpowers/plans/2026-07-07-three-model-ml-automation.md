# Three Model ML Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 통합 주식 자동화를 유지한 채 국내주식, 해외주식, 코인 3개 모델 자동 수집+학습을 shadow로 추가하고, 성능이 더 뛰어난 경우 교체 후보로 관리자가 확인할 수 있게 만든다.

**Architecture:** 학습 유니버스와 raw/features/model output 파일을 국내주식, 해외주식, 코인으로 분리한다. 자동화 preset과 스케줄러는 동일한 실행 함수를 공유하고, 교체 판단은 serving 모델 대비 성능 비교 결과를 별도 리포트/잡 감사 데이터에 기록한다. 관리자 화면은 기존 ML 페이지 안에 `머신러닝`과 `문의답변` 내부 탭을 두어 팀원이 문의답변 콘텐츠를 나중에 붙일 수 있게 한다.

**Tech Stack:** Flask, Python 3, pandas, LightGBM, YAML, React 19, Vite, Tailwind CSS v4, Supabase REST.

## Global Constraints

- 모든 설명과 계획서는 반드시 한국어로 작성한다.
- 코드 주석은 한국어로 작성하되, 외부 API 필드명과 표준 용어는 영문을 허용한다.
- 기존 `stock-v8-full` 자동화는 제거하지 않는다. 신규 3분리 모델은 shadow preset으로 추가한다.
- 국내주식 모델에만 DART 공시 피처를 병합한다.
- 해외주식 모델에는 DART 피처를 넣지 않는다.
- 코인 모델은 기존 30분봉 v8 자동화 흐름을 유지하고, 명명 정리는 별도 신규 config에서만 한다.
- 신규 실거래 주문 기능은 추가하지 않는다.
- 환경 변수를 새로 추가하면 `.env.example`을 갱신한다.
- 사용자 화면에 원문 예외를 그대로 노출하지 않고 `format_error_payload()`를 사용한다.
- 자동 serving 교체는 구현하지 않는다. 성능 우위 시 `promotion_candidate` 상태를 기록하고 관리자 승인 흐름으로 연결한다.

---

## File Structure

- Modify: `ml/data/reference/training_universes.json`
  - `stock_kr_core_45`, `stock_us_core_45` 프리셋을 추가한다.
- Create: `tests/ml/test_training_universes.py`
  - 3분리 유니버스가 중복 없이 기존 `stock_core_90`을 정확히 나누는지 검증한다.
- Modify: `ml/src/build_features.py`
  - config 기반 선택 피처 경로를 지원하고 DART 피처 기본 컬럼을 국내주식 config에서만 사용할 수 있게 한다.
- Create: `tests/ml/test_build_features_optional_paths.py`
  - `optional_features.dart_features_path`가 있을 때만 DART 피처를 병합하는지 검증한다.
- Create: `backend/scripts/export_dart_features.py`
  - Supabase `dart_disclosures`와 `dart_disclosure_analyses`를 일별/종목별 CSV로 집계한다.
- Create: `tests/backend/test_export_dart_features.py`
  - 공시 요약 집계와 하루 shift 기준 피처 생성 함수를 검증한다.
- Create: `ml/configs/lgbm_kr_stock_v1.yaml`
- Create: `ml/configs/lgbm_kr_stock_risk_v1.yaml`
- Create: `ml/configs/lgbm_us_stock_v1.yaml`
- Create: `ml/configs/lgbm_us_stock_risk_v1.yaml`
  - 기존 v11/v8 설정을 기반으로 raw/features/predictions/model output을 분리한다.
- Modify: `backend/services/ml_automation_service.py`
  - `kr-stock-v1-full`, `us-stock-v1-full`, `crypto-v8-full` 운영 shadow preset을 추가한다.
- Modify: `backend/routes/ml.py`
  - full-run에서 `raw_output`, `post_dataset_commands`, `asset_key`를 처리한다.
- Modify: `backend/services/ml_scheduler.py`
  - 주식 자동화 시간대에 `kr-stock-v1-full`과 `us-stock-v1-full`을 순차 실행하고, 기존 `stock-v8-full`은 안전망으로 유지한다.
- Create: `backend/services/ml_split_model_promotion_service.py`
  - 3분리 모델의 성능을 기존 serving 모델과 비교해 교체 후보 여부를 산출한다.
- Create: `tests/backend/test_ml_split_model_promotion_service.py`
  - 성능 우위/열위 판정을 검증한다.
- Modify: `frontend/src/pages/AdminMlData.jsx`
  - 내부 탭을 `머신러닝`, `문의답변`으로 분리하고 3분리 자동화 버튼과 교체 후보 상태를 표시한다.
- Create: `frontend/src/pages/AdminInquiryPanel.jsx`
  - 팀원이 이후 문의답변 UI를 붙일 수 있는 빈 연결 영역을 제공한다.
- Modify: `project_structure.md`
  - 새 ML config, DART feature export, 관리자 탭 구조를 반영한다.
- Modify: `ml/README.md`
  - 3분리 모델 수집/학습/승격 후보 기준을 문서화한다.

---

### Task 1: 학습 유니버스 3분리

**Files:**
- Modify: `ml/data/reference/training_universes.json`
- Create: `tests/ml/test_training_universes.py`

**Interfaces:**
- Consumes: 기존 JSON 키 `stock_core_90`
- Produces:
  - JSON key `stock_kr_core_45: list[str]`
  - JSON key `stock_us_core_45: list[str]`

- [ ] **Step 1: Write the failing test**

Create `tests/ml/test_training_universes.py`:

```python
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
UNIVERSE_PATH = PROJECT_ROOT / "ml" / "data" / "reference" / "training_universes.json"


def test_stock_core_90_is_split_into_kr_and_us_universes():
    payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))

    stock_core = payload["stock_core_90"]
    kr_core = payload["stock_kr_core_45"]
    us_core = payload["stock_us_core_45"]

    assert len(stock_core) == 90
    assert len(kr_core) == 45
    assert len(us_core) == 45
    assert kr_core + us_core == stock_core
    assert len(set(kr_core)) == 45
    assert len(set(us_core)) == 45
    assert set(kr_core).isdisjoint(set(us_core))
    assert all(symbol.isdigit() and len(symbol) == 6 for symbol in kr_core)
    assert all(not (symbol.isdigit() and len(symbol) == 6) for symbol in us_core)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/ml/test_training_universes.py -v
```

Expected: FAIL with `KeyError: 'stock_kr_core_45'`.

- [ ] **Step 3: Add split universes**

Modify `ml/data/reference/training_universes.json` so it contains these keys immediately after `stock_core_90`:

```json
  "stock_kr_core_45": [
    "005930", "000660", "035420", "035720", "005380", "000270", "051910", "068270", "373220", "006400",
    "207940", "105560", "055550", "086790", "012330", "028260", "066570", "096770", "003550", "034020",
    "011200", "010130", "017670", "009150", "018260", "010950", "032830", "042660", "000810", "316140",
    "035250", "251270", "361610", "018880", "329180", "259960", "352820", "138040", "267250", "302440",
    "005387", "090430", "271560", "034730", "097950"
  ],
  "stock_us_core_45": [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AMD", "AVGO", "LLY",
    "NFLX", "COST", "JPM", "V", "MA", "XOM", "UNH", "ORCL", "CRM", "ADBE",
    "QCOM", "INTC", "MU", "PLTR", "SMCI", "PANW", "ASML", "TSM", "UBER", "SHOP",
    "SNOW", "COIN", "SOFI", "ARM", "RDDT", "QQQ", "SPY", "DIA", "IWM", "SOXX",
    "XLK", "XLF", "XLE", "GLD", "TLT"
  ],
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
python3 -m pytest tests/ml/test_training_universes.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ml/data/reference/training_universes.json tests/ml/test_training_universes.py
git commit -m "feat: split stock training universes"
```

---

### Task 2: DART 공시 피처 export 스크립트

**Files:**
- Create: `backend/scripts/export_dart_features.py`
- Create: `tests/backend/test_export_dart_features.py`

**Interfaces:**
- Consumes:
  - `dart_disclosures` rows with `rcept_no`, `stock_code`, `report_nm`, `rcept_dt`
  - `dart_disclosure_analyses` rows with `rcept_no`, `category`, `sentiment`, `confidence`
- Produces:
  - Function `normalize_stock_code(value: object) -> str`
  - Function `build_daily_dart_features(disclosures: list[dict], analyses: list[dict]) -> pandas.DataFrame`
  - Function `build_shifted_dart_features(feature_dates: pandas.DataFrame, daily_features: pandas.DataFrame) -> pandas.DataFrame`
  - CLI output CSV columns:
    - `symbol`
    - `date`
    - `dart_disclosure_count_3d`
    - `dart_sentiment_sum_3d`
    - `dart_negative_count_3d`
    - `dart_positive_count_3d`
    - `dart_caution_count_3d`
    - `dart_disclosure_count_7d`
    - `dart_sentiment_sum_7d`
    - `dart_negative_count_7d`
    - `dart_positive_count_7d`
    - `dart_caution_count_7d`
    - `dart_disclosure_count_20d`
    - `dart_sentiment_sum_20d`
    - `dart_negative_count_20d`
    - `dart_positive_count_20d`
    - `dart_caution_count_20d`
    - `dart_ai_analyzed_count_20d`
    - `dart_contract_flag_20d`
    - `dart_financing_flag_20d`
    - `dart_shareholder_return_flag_20d`
    - `dart_risk_event_flag_20d`
    - `dart_earnings_flag_20d`

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_export_dart_features.py`:

```python
import pandas as pd

from backend.scripts.export_dart_features import (
    build_daily_dart_features,
    build_shifted_dart_features,
    normalize_stock_code,
)


def test_normalize_stock_code_preserves_six_digit_symbols():
    assert normalize_stock_code("5930") == "005930"
    assert normalize_stock_code("005930") == "005930"
    assert normalize_stock_code("005930.0") == "005930"
    assert normalize_stock_code(None) == ""


def test_build_daily_dart_features_uses_analysis_sentiment_and_category():
    disclosures = [
        {
            "rcept_no": "202607070001",
            "stock_code": "005930",
            "report_nm": "단일판매ㆍ공급계약체결",
            "rcept_dt": "2026-07-07",
        },
        {
            "rcept_no": "202607070002",
            "stock_code": "005930",
            "report_nm": "유상증자결정",
            "rcept_dt": "2026-07-07",
        },
    ]
    analyses = [
        {
            "rcept_no": "202607070001",
            "category": "수주·공급계약",
            "sentiment": "positive",
            "confidence": "high",
        },
        {
            "rcept_no": "202607070002",
            "category": "자금조달·증권발행",
            "sentiment": "caution",
            "confidence": "medium",
        },
    ]

    frame = build_daily_dart_features(disclosures, analyses)
    row = frame.iloc[0].to_dict()

    assert row["symbol"] == "005930"
    assert row["date"] == "2026-07-07"
    assert row["dart_disclosure_count"] == 2.0
    assert row["dart_sentiment_score"] == 0.5
    assert row["dart_positive_count"] == 1.0
    assert row["dart_caution_count"] == 1.0
    assert row["dart_contract_flag"] == 1.0
    assert row["dart_financing_flag"] == 1.0


def test_build_shifted_dart_features_uses_only_prior_disclosures():
    feature_dates = pd.DataFrame(
        {
            "symbol": ["005930", "005930", "005930"],
            "date": pd.to_datetime(["2026-07-07", "2026-07-08", "2026-07-09"]),
        }
    )
    daily_features = pd.DataFrame(
        {
            "symbol": ["005930"],
            "date": ["2026-07-07"],
            "dart_disclosure_count": [1.0],
            "dart_sentiment_score": [1.0],
            "dart_negative_count": [0.0],
            "dart_positive_count": [1.0],
            "dart_caution_count": [0.0],
            "dart_info_count": [0.0],
            "dart_ai_analyzed_count": [1.0],
            "dart_contract_flag": [1.0],
            "dart_financing_flag": [0.0],
            "dart_shareholder_return_flag": [0.0],
            "dart_risk_event_flag": [0.0],
            "dart_earnings_flag": [0.0],
        }
    )

    shifted = build_shifted_dart_features(feature_dates, daily_features)
    rows = shifted.sort_values("date").to_dict("records")

    assert rows[0]["dart_disclosure_count_3d"] == 0.0
    assert rows[1]["dart_disclosure_count_3d"] == 1.0
    assert rows[2]["dart_disclosure_count_3d"] == 1.0
    assert rows[1]["dart_contract_flag_20d"] == 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/backend/test_export_dart_features.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.scripts.export_dart_features'`.

- [ ] **Step 3: Implement `export_dart_features.py`**

Create `backend/scripts/export_dart_features.py`:

```python
import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


SENTIMENT_SCORE = {
    "positive": 1.0,
    "negative": -1.0,
    "caution": -0.5,
    "info": 0.0,
}

CATEGORY_GROUPS = {
    "dart_contract_flag": ["수주", "공급계약", "계약"],
    "dart_financing_flag": ["유상증자", "자금조달", "증권", "사채", "전환"],
    "dart_shareholder_return_flag": ["배당", "자사주", "주주환원", "소각"],
    "dart_risk_event_flag": ["거래정지", "상장폐지", "관리종목", "불성실", "감사의견", "횡령", "배임", "회생", "영업정지", "감자"],
    "dart_earnings_flag": ["영업실적", "손익구조", "매출액", "영업이익"],
}

BASE_DART_COLUMNS = [
    "dart_disclosure_count",
    "dart_sentiment_score",
    "dart_positive_count",
    "dart_negative_count",
    "dart_caution_count",
    "dart_info_count",
    "dart_ai_analyzed_count",
    *CATEGORY_GROUPS.keys(),
]


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def normalize_stock_code(value: object) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip().upper()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit() and len(text) <= 6:
        return text.zfill(6)
    return text


def build_daily_dart_features(disclosures: list[dict[str, Any]], analyses: list[dict[str, Any]]) -> pd.DataFrame:
    analysis_by_receipt = {str(row.get("rcept_no") or ""): row for row in analyses}
    rows: list[dict[str, Any]] = []

    for disclosure in disclosures:
        symbol = normalize_stock_code(disclosure.get("stock_code"))
        receipt_no = str(disclosure.get("rcept_no") or "")
        received_date = pd.to_datetime(disclosure.get("rcept_dt"), errors="coerce")
        if not symbol or not receipt_no or pd.isna(received_date):
            continue

        analysis = analysis_by_receipt.get(receipt_no) or {}
        sentiment = str(analysis.get("sentiment") or "info")
        category = str(analysis.get("category") or "")
        report_name = str(disclosure.get("report_nm") or "")
        category_text = f"{report_name} {category}"

        row = {
            "symbol": symbol,
            "date": received_date.strftime("%Y-%m-%d"),
            "dart_disclosure_count": 1.0,
            "dart_sentiment_score": SENTIMENT_SCORE.get(sentiment, 0.0),
            "dart_positive_count": 1.0 if sentiment == "positive" else 0.0,
            "dart_negative_count": 1.0 if sentiment == "negative" else 0.0,
            "dart_caution_count": 1.0 if sentiment == "caution" else 0.0,
            "dart_info_count": 1.0 if sentiment == "info" else 0.0,
            "dart_ai_analyzed_count": 1.0 if analysis else 0.0,
        }
        for column, keywords in CATEGORY_GROUPS.items():
            row[column] = 1.0 if any(keyword in category_text for keyword in keywords) else 0.0
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["symbol", "date", *BASE_DART_COLUMNS])

    return (
        pd.DataFrame(rows)
        .groupby(["symbol", "date"], as_index=False)[BASE_DART_COLUMNS]
        .sum()
        .sort_values(["symbol", "date"])
        .reset_index(drop=True)
    )


def build_shifted_dart_features(feature_dates: pd.DataFrame, daily_features: pd.DataFrame) -> pd.DataFrame:
    base = feature_dates[["symbol", "date"]].copy()
    base["symbol"] = base["symbol"].map(normalize_stock_code)
    base["date"] = pd.to_datetime(base["date"], errors="coerce")
    base = base.dropna(subset=["date"]).sort_values(["symbol", "date"])
    base["date_key"] = base["date"].dt.strftime("%Y-%m-%d")

    daily = daily_features.copy()
    if daily.empty:
        daily = pd.DataFrame(columns=["symbol", "date", *BASE_DART_COLUMNS])
    daily["symbol"] = daily["symbol"].map(normalize_stock_code)
    daily["date_key"] = pd.to_datetime(daily["date"], errors="coerce").dt.strftime("%Y-%m-%d")

    merged = base.merge(daily[["symbol", "date_key", *BASE_DART_COLUMNS]], on=["symbol", "date_key"], how="left")
    merged[BASE_DART_COLUMNS] = merged[BASE_DART_COLUMNS].fillna(0.0)

    frames: list[pd.DataFrame] = []
    for symbol, group in merged.groupby("symbol", sort=False):
        group = group.sort_values("date").copy()
        shifted = group[BASE_DART_COLUMNS].shift(1).fillna(0.0)
        output = group[["symbol", "date"]].copy()
        for window in [3, 7, 20]:
            rolling = shifted.rolling(window, min_periods=1).sum()
            output[f"dart_disclosure_count_{window}d"] = rolling["dart_disclosure_count"]
            output[f"dart_sentiment_sum_{window}d"] = rolling["dart_sentiment_score"]
            output[f"dart_negative_count_{window}d"] = rolling["dart_negative_count"]
            output[f"dart_positive_count_{window}d"] = rolling["dart_positive_count"]
            output[f"dart_caution_count_{window}d"] = rolling["dart_caution_count"]
        output["dart_ai_analyzed_count_20d"] = shifted["dart_ai_analyzed_count"].rolling(20, min_periods=1).sum()
        for column in CATEGORY_GROUPS:
            output[f"{column}_20d"] = shifted[column].rolling(20, min_periods=1).max()
        frames.append(output)

    result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["symbol", "date"])
    result["date"] = pd.to_datetime(result["date"]).dt.strftime("%Y-%m-%d")
    return result


def fetch_supabase_rows(table: str, select: str, params: dict[str, str], batch_size: int = 1000) -> list[dict[str, Any]]:
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not supabase_url or not service_key:
        raise RuntimeError("SUPABASE_URL과 SUPABASE_SERVICE_ROLE_KEY가 필요합니다.")

    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    }
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        request_params = {"select": select, "limit": str(batch_size), "offset": str(offset), **params}
        response = requests.get(
            f"{supabase_url}/rest/v1/{table}",
            headers=headers,
            params=request_params,
            timeout=30,
        )
        response.raise_for_status()
        batch = response.json()
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < batch_size:
            break
        offset += batch_size
    return rows


def main() -> None:
    load_env_file(PROJECT_ROOT / "backend" / ".env")
    parser = argparse.ArgumentParser(description="DART 공시 분석 결과를 ML raw 피처 CSV로 변환합니다.")
    parser.add_argument("--dates-source-path", default="ml/data/raw/kr_stock_candles.csv")
    parser.add_argument("--output", default="ml/data/raw/dart_features.csv")
    parser.add_argument("--start-date", default="")
    parser.add_argument("--end-date", default="")
    args = parser.parse_args()

    dates_source_path = (PROJECT_ROOT / args.dates_source_path).resolve()
    dates_source_frame = pd.read_csv(dates_source_path, dtype={"symbol": "string"}, low_memory=False)
    feature_dates = dates_source_frame[["symbol", "date"]].drop_duplicates()
    start_date = args.start_date or pd.to_datetime(feature_dates["date"]).min().strftime("%Y-%m-%d")
    end_date = args.end_date or pd.to_datetime(feature_dates["date"]).max().strftime("%Y-%m-%d")

    disclosures = fetch_supabase_rows(
        "dart_disclosures",
        "rcept_no,stock_code,report_nm,rcept_dt",
        {"rcept_dt": f"gte.{start_date}", "order": "rcept_dt.asc,rcept_no.asc"},
    )
    disclosures = [
        row
        for row in disclosures
        if pd.to_datetime(row.get("rcept_dt"), errors="coerce").strftime("%Y-%m-%d") <= end_date
    ]
    analyses = fetch_supabase_rows(
        "dart_disclosure_analyses",
        "rcept_no,category,sentiment,confidence",
        {},
    )

    daily = build_daily_dart_features(disclosures, analyses)
    shifted = build_shifted_dart_features(feature_dates, daily)
    output_path = (PROJECT_ROOT / args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shifted.to_csv(output_path, index=False)
    print(json.dumps({"output": str(output_path), "rows": len(shifted)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/backend/test_export_dart_features.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/export_dart_features.py tests/backend/test_export_dart_features.py
git commit -m "feat: export dart features for kr stock models"
```

---

### Task 3: 선택 피처 경로와 DART 컬럼 병합 지원

**Files:**
- Modify: `ml/src/build_features.py`
- Create: `tests/ml/test_build_features_optional_paths.py`

**Interfaces:**
- Consumes:
  - config key `optional_features.news_features_path: str | None`
  - config key `optional_features.stock_event_features_path: str | None`
  - config key `optional_features.dart_features_path: str | None`
- Produces:
  - Function behavior: `apply_optional_features(features: pandas.DataFrame, config: dict) -> pandas.DataFrame` merges DART columns only when `dart_features_path` is configured.

- [ ] **Step 1: Write the failing tests**

Create `tests/ml/test_build_features_optional_paths.py`:

```python
from pathlib import Path

import pandas as pd

from ml.src.build_features import apply_optional_features


def test_apply_optional_features_merges_configured_dart_features(tmp_path: Path):
    dart_path = tmp_path / "dart_features.csv"
    dart_path.write_text(
        "\n".join(
            [
                "symbol,date,dart_disclosure_count_3d,dart_sentiment_sum_3d,dart_negative_count_3d,dart_positive_count_3d,dart_caution_count_3d,dart_disclosure_count_7d,dart_sentiment_sum_7d,dart_negative_count_7d,dart_positive_count_7d,dart_caution_count_7d,dart_disclosure_count_20d,dart_sentiment_sum_20d,dart_negative_count_20d,dart_positive_count_20d,dart_caution_count_20d,dart_ai_analyzed_count_20d,dart_contract_flag_20d,dart_financing_flag_20d,dart_shareholder_return_flag_20d,dart_risk_event_flag_20d,dart_earnings_flag_20d",
                "005930,2026-07-08,1,1,0,1,0,1,1,0,1,0,1,1,0,1,0,1,1,0,0,0,0",
            ]
        ),
        encoding="utf-8",
    )
    features = pd.DataFrame(
        {
            "symbol": ["005930"],
            "date_merge_key": ["2026-07-08"],
        }
    )
    config = {
        "model": {"asset_type": "STOCK"},
        "optional_features": {"dart_features_path": str(dart_path)},
    }

    merged = apply_optional_features(features, config)

    assert merged.loc[0, "dart_disclosure_count_3d"] == 1
    assert merged.loc[0, "dart_contract_flag_20d"] == 1


def test_apply_optional_features_does_not_add_dart_columns_without_path():
    features = pd.DataFrame(
        {
            "symbol": ["005930"],
            "date_merge_key": ["2026-07-08"],
        }
    )
    config = {"model": {"asset_type": "STOCK"}}

    merged = apply_optional_features(features, config)

    assert "dart_disclosure_count_3d" not in merged.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/ml/test_build_features_optional_paths.py -v
```

Expected: first test FAIL because `dart_features_path` is not merged.

- [ ] **Step 3: Implement configurable optional paths**

Modify `ml/src/build_features.py`.

Add this helper near `load_optional_feature_source`:

```python
def resolve_optional_feature_path(config: dict, key: str, default_relative_path: str) -> Path:
    configured_path = (config.get("optional_features") or {}).get(key)
    if configured_path:
        path = Path(str(configured_path))
        return path if path.is_absolute() else PROJECT_ROOT / path
    return PROJECT_ROOT / default_relative_path
```

In `apply_optional_features`, replace hard-coded path assignments:

```python
news_path = resolve_optional_feature_path(config, "news_features_path", "ml/data/raw/news_features.csv")
```

```python
crypto_path = resolve_optional_feature_path(config, "crypto_market_features_path", "ml/data/raw/crypto_market_features.csv")
```

```python
stock_path = resolve_optional_feature_path(config, "stock_event_features_path", "ml/data/raw/stock_event_features.csv")
```

Then add this block inside `if asset_type == "STOCK":` after `stock_df` merge:

```python
        dart_defaults = [
            "dart_disclosure_count_3d",
            "dart_sentiment_sum_3d",
            "dart_negative_count_3d",
            "dart_positive_count_3d",
            "dart_caution_count_3d",
            "dart_disclosure_count_7d",
            "dart_sentiment_sum_7d",
            "dart_negative_count_7d",
            "dart_positive_count_7d",
            "dart_caution_count_7d",
            "dart_disclosure_count_20d",
            "dart_sentiment_sum_20d",
            "dart_negative_count_20d",
            "dart_positive_count_20d",
            "dart_caution_count_20d",
            "dart_ai_analyzed_count_20d",
            "dart_contract_flag_20d",
            "dart_financing_flag_20d",
            "dart_shareholder_return_flag_20d",
            "dart_risk_event_flag_20d",
            "dart_earnings_flag_20d",
        ]
        dart_path_text = (config.get("optional_features") or {}).get("dart_features_path")
        if dart_path_text:
            dart_path = resolve_optional_feature_path(config, "dart_features_path", "ml/data/raw/dart_features.csv")
            dart_df = load_optional_feature_source(dart_path, asset_type, dart_defaults)
            if not dart_df.empty:
                features = pd.merge(features, dart_df, on=["symbol", "date_merge_key"], how="left")
```

Also add all `dart_defaults` values to the later zero-fill column list in `build_features`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/ml/test_build_features_optional_paths.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ml/src/build_features.py tests/ml/test_build_features_optional_paths.py
git commit -m "feat: support configured optional ml feature sources"
```

---

### Task 4: 국내/해외 주식 모델 config 추가

**Files:**
- Create: `ml/configs/lgbm_kr_stock_v1.yaml`
- Create: `ml/configs/lgbm_kr_stock_risk_v1.yaml`
- Create: `ml/configs/lgbm_us_stock_v1.yaml`
- Create: `ml/configs/lgbm_us_stock_risk_v1.yaml`
- Create: `tests/ml/test_split_stock_configs.py`

**Interfaces:**
- Consumes:
  - `ml/configs/lgbm_stock_v11.yaml`
  - `ml/configs/lgbm_stock_risk_v11.yaml`
  - Task 3 `optional_features.dart_features_path`
- Produces:
  - model versions `lgbm_kr_stock_signal_v1`, `lgbm_kr_stock_risk_v1`
  - model versions `lgbm_us_stock_signal_v1`, `lgbm_us_stock_risk_v1`

- [ ] **Step 1: Write the failing tests**

Create `tests/ml/test_split_stock_configs.py`:

```python
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(name: str) -> dict:
    return yaml.safe_load((PROJECT_ROOT / "ml" / "configs" / name).read_text(encoding="utf-8"))


def test_kr_stock_config_uses_separate_paths_and_dart_features():
    config = load_config("lgbm_kr_stock_v1.yaml")
    risk_config = load_config("lgbm_kr_stock_risk_v1.yaml")

    assert config["data"]["raw_candles_path"] == "data/raw/kr_stock_candles.csv"
    assert config["data"]["features_path"] == "data/processed/kr_stock_features_lgbm_v1.csv"
    assert config["model"]["version"] == "lgbm_kr_stock_signal_v1"
    assert config["model"]["asset_type"] == "STOCK"
    assert config["optional_features"]["dart_features_path"] == "ml/data/raw/dart_features.csv"
    assert "dart_disclosure_count_20d" in config["model"]["feature_columns"]
    assert risk_config["model"]["version"] == "lgbm_kr_stock_risk_v1"
    assert risk_config["data"]["features_path"] == config["data"]["features_path"]


def test_us_stock_config_uses_separate_paths_and_excludes_dart_features():
    config = load_config("lgbm_us_stock_v1.yaml")
    risk_config = load_config("lgbm_us_stock_risk_v1.yaml")

    assert config["data"]["raw_candles_path"] == "data/raw/us_stock_candles.csv"
    assert config["data"]["features_path"] == "data/processed/us_stock_features_lgbm_v1.csv"
    assert config["model"]["version"] == "lgbm_us_stock_signal_v1"
    assert config["model"]["asset_type"] == "STOCK"
    assert "dart_features_path" not in config.get("optional_features", {})
    assert "dart_disclosure_count_20d" not in config["model"]["feature_columns"]
    assert risk_config["model"]["version"] == "lgbm_us_stock_risk_v1"
    assert risk_config["data"]["features_path"] == config["data"]["features_path"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/ml/test_split_stock_configs.py -v
```

Expected: FAIL because config files do not exist.

- [ ] **Step 3: Create config files**

Create the four config files by copying `lgbm_stock_v11.yaml` and `lgbm_stock_risk_v11.yaml`, then make these exact changes.

For `ml/configs/lgbm_kr_stock_v1.yaml`:

```yaml
data:
  raw_candles_path: data/raw/kr_stock_candles.csv
  features_path: data/processed/kr_stock_features_lgbm_v1.csv
  predictions_path: data/processed/kr_stock_predictions_lgbm_v1.csv
  backtest_up_only_summary_path: data/processed/kr_stock_backtest_up_only_v1.json
  backtest_up_only_daily_path: data/processed/kr_stock_backtest_up_only_daily_v1.csv
  backtest_composite_summary_path: data/processed/kr_stock_backtest_composite_v1.json
  backtest_composite_daily_path: data/processed/kr_stock_backtest_composite_daily_v1.csv
model:
  version: lgbm_kr_stock_signal_v1
  asset_type: STOCK
  output_path: models/lgbm_kr_stock_signal_v1.joblib
```

Keep the v11 feature columns and append the 21 DART columns from Task 2 to `model.feature_columns`.

Add:

```yaml
optional_features:
  dart_features_path: ml/data/raw/dart_features.csv
```

Set prediction risk path:

```yaml
prediction:
  risk_model_path: models/lgbm_kr_stock_risk_v1.joblib
```

For `ml/configs/lgbm_kr_stock_risk_v1.yaml`, copy `lgbm_stock_risk_v11.yaml`, point it to `data/processed/kr_stock_features_lgbm_v1.csv`, set version `lgbm_kr_stock_risk_v1`, output `models/lgbm_kr_stock_risk_v1.joblib`, and append the same 21 DART feature columns.

For `ml/configs/lgbm_us_stock_v1.yaml`, copy `lgbm_stock_v11.yaml`, use:

```yaml
data:
  raw_candles_path: data/raw/us_stock_candles.csv
  features_path: data/processed/us_stock_features_lgbm_v1.csv
  predictions_path: data/processed/us_stock_predictions_lgbm_v1.csv
  backtest_up_only_summary_path: data/processed/us_stock_backtest_up_only_v1.json
  backtest_up_only_daily_path: data/processed/us_stock_backtest_up_only_daily_v1.csv
  backtest_composite_summary_path: data/processed/us_stock_backtest_composite_v1.json
  backtest_composite_daily_path: data/processed/us_stock_backtest_composite_daily_v1.csv
model:
  version: lgbm_us_stock_signal_v1
  asset_type: STOCK
  output_path: models/lgbm_us_stock_signal_v1.joblib
prediction:
  risk_model_path: models/lgbm_us_stock_risk_v1.joblib
```

Do not add `optional_features.dart_features_path` and do not include DART columns.

For `ml/configs/lgbm_us_stock_risk_v1.yaml`, copy `lgbm_stock_risk_v11.yaml`, point it to `data/processed/us_stock_features_lgbm_v1.csv`, set version `lgbm_us_stock_risk_v1`, and output `models/lgbm_us_stock_risk_v1.joblib`.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/ml/test_split_stock_configs.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ml/configs/lgbm_kr_stock_v1.yaml ml/configs/lgbm_kr_stock_risk_v1.yaml ml/configs/lgbm_us_stock_v1.yaml ml/configs/lgbm_us_stock_risk_v1.yaml tests/ml/test_split_stock_configs.py
git commit -m "feat: add split stock model configs"
```

---

### Task 5: 자동화 preset과 full-run 출력 분리

**Files:**
- Modify: `backend/services/ml_automation_service.py`
- Modify: `backend/routes/ml.py`
- Create: `tests/backend/test_ml_automation_presets.py`

**Interfaces:**
- Consumes:
  - Task 1 universe keys
  - Task 4 config files
- Produces:
  - preset key `kr-stock-v1-full`
  - preset key `us-stock-v1-full`
  - full-run support for `dataset.raw_output`
  - full-run support for `training.pre_build_commands: list[list[str]]`

- [ ] **Step 1: Write the failing tests**

Create `tests/backend/test_ml_automation_presets.py`:

```python
from backend.services.ml_automation_service import resolve_automation_preset


def test_kr_stock_automation_preset_uses_kr_universe_and_dart_prebuild():
    preset = resolve_automation_preset("kr-stock-v1-full")

    assert preset["dataset"]["preset"] == "stock_kr_core_45"
    assert preset["dataset"]["raw_output"] == "kr_stock_candles.csv"
    assert preset["training"]["config"] == "ml/configs/lgbm_kr_stock_v1.yaml"
    assert preset["training"]["risk_config"] == "ml/configs/lgbm_kr_stock_risk_v1.yaml"
    assert preset["training"]["summary_output"] == "ml/data/processed/kr_stock_v1_summary.json"
    assert preset["training"]["pre_build_commands"] == [
        [
            "python",
            "backend/scripts/export_dart_features.py",
            "--dates-source-path",
            "ml/data/raw/kr_stock_candles.csv",
            "--output",
            "ml/data/raw/dart_features.csv",
        ]
    ]


def test_us_stock_automation_preset_uses_us_universe_without_dart_prebuild():
    preset = resolve_automation_preset("us-stock-v1-full")

    assert preset["dataset"]["preset"] == "stock_us_core_45"
    assert preset["dataset"]["raw_output"] == "us_stock_candles.csv"
    assert preset["training"]["config"] == "ml/configs/lgbm_us_stock_v1.yaml"
    assert preset["training"]["risk_config"] == "ml/configs/lgbm_us_stock_risk_v1.yaml"
    assert "pre_build_commands" not in preset["training"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/backend/test_ml_automation_presets.py -v
```

Expected: FAIL with `ValueError: 알 수 없는 자동화 프리셋입니다: kr-stock-v1-full`.

- [ ] **Step 3: Add automation presets**

Modify `backend/services/ml_automation_service.py` and add:

```python
    "kr-stock-v1-full": {
        "label": "국내주식 v1 자동 수집+학습 (DART shadow)",
        "dataset": {
            "asset_type": "STOCK",
            "exchange": "TOSS",
            "preset": "stock_kr_core_45",
            "symbols": [],
            "interval": "1d",
            "count": 700,
            "sleep_seconds": 2.0,
            "retry": 3,
            "retry_wait_seconds": 60.0,
            "append": True,
            "include_macro": True,
            "chunk_size": 0,
            "chunk_index": 1,
            "raw_output": "kr_stock_candles.csv",
        },
        "training": {
            "config": "ml/configs/lgbm_kr_stock_v1.yaml",
            "risk_config": "ml/configs/lgbm_kr_stock_risk_v1.yaml",
            "summary_output": "ml/data/processed/kr_stock_v1_summary.json",
            "skip_build_features": False,
            "pre_build_commands": [
                [
                    "python",
                    "backend/scripts/export_dart_features.py",
                    "--dates-source-path",
                    "ml/data/raw/kr_stock_candles.csv",
                    "--output",
                    "ml/data/raw/dart_features.csv",
                ]
            ],
        },
    },
    "us-stock-v1-full": {
        "label": "해외주식 v1 자동 수집+학습 (shadow)",
        "dataset": {
            "asset_type": "STOCK",
            "exchange": "TOSS",
            "preset": "stock_us_core_45",
            "symbols": [],
            "interval": "1d",
            "count": 700,
            "sleep_seconds": 2.0,
            "retry": 3,
            "retry_wait_seconds": 60.0,
            "append": True,
            "include_macro": True,
            "chunk_size": 0,
            "chunk_index": 1,
            "raw_output": "us_stock_candles.csv",
        },
        "training": {
            "config": "ml/configs/lgbm_us_stock_v1.yaml",
            "risk_config": "ml/configs/lgbm_us_stock_risk_v1.yaml",
            "summary_output": "ml/data/processed/us_stock_v1_summary.json",
            "skip_build_features": False,
        },
    },
```

- [ ] **Step 4: Modify full-run output and pre-build handling**

Modify `backend/routes/ml.py`.

In the TOSS/STOCK branch of `run_ml_full_pipeline_job`, replace:

```python
output = os.path.join(project_root_path, "ml", "data", "raw", "stock_candles.csv")
```

with:

```python
raw_output_name = dataset_config.get("raw_output", "stock_candles.csv")
output = os.path.join(project_root_path, "ml", "data", "raw", raw_output_name)
```

Before `result = run_ml_pipeline(...)`, run configured pre-build commands:

```python
        for command in training_config.get("pre_build_commands") or []:
            resolved_command = [
                sys.executable if token == "python" else token
                for token in command
            ]
            completed = subprocess.run(
                resolved_command,
                cwd=project_root_path,
                check=False,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    "사전 피처 생성 명령이 실패했습니다: "
                    + " ".join(command)
                    + "\n"
                    + completed.stderr[-4000:]
                )
```

Add imports at top:

```python
import subprocess
import sys
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/backend/test_ml_automation_presets.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/ml_automation_service.py backend/routes/ml.py tests/backend/test_ml_automation_presets.py
git commit -m "feat: add split stock automation presets"
```

---

### Task 6: 스케줄러 3분리 shadow 실행

**Files:**
- Modify: `backend/services/ml_scheduler.py`
- Create: `tests/backend/test_ml_scheduler_presets.py`

**Interfaces:**
- Consumes:
  - `resolve_automation_preset(key: str) -> dict`
  - Task 5 preset keys
- Produces:
  - Function `get_stock_shadow_preset_keys() -> list[str]`
  - Scheduler runs `kr-stock-v1-full`, `us-stock-v1-full`, then legacy `stock-v8-full`

- [ ] **Step 1: Write the failing test**

Create `tests/backend/test_ml_scheduler_presets.py`:

```python
from backend.services.ml_scheduler import get_stock_shadow_preset_keys


def test_stock_shadow_preset_order_keeps_legacy_safety_net_last():
    assert get_stock_shadow_preset_keys() == [
        "kr-stock-v1-full",
        "us-stock-v1-full",
        "stock-v8-full",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python3 -m pytest tests/backend/test_ml_scheduler_presets.py -v
```

Expected: FAIL with import error for `get_stock_shadow_preset_keys`.

- [ ] **Step 3: Add preset order helper**

Modify `backend/services/ml_scheduler.py` near module globals:

```python
def get_stock_shadow_preset_keys() -> list[str]:
    """주식 자동화는 분리 모델을 먼저 shadow 학습하고 기존 통합 모델을 안전망으로 유지합니다."""
    return ["kr-stock-v1-full", "us-stock-v1-full", "stock-v8-full"]
```

- [ ] **Step 4: Replace single stock preset execution with loop**

Inside the stock automation block, replace the single:

```python
preset = resolve_automation_preset("stock-v8-full")
```

flow with a loop over `get_stock_shadow_preset_keys()`. Each loop must create its own dataset job and training job. Preserve current Toss token acquisition and macro fetch behavior. For each preset, use:

```python
for preset_key in get_stock_shadow_preset_keys():
    preset = resolve_automation_preset(preset_key)
    dataset_config = preset["dataset"]
    training_config = preset["training"]
    preset_symbols = load_preset_symbols(dataset_config["preset"], DEFAULT_UNIVERSE_PATH)
    symbols = list(dict.fromkeys([*(dataset_config.get("symbols") or []), *preset_symbols]))
```

For stock raw output, use:

```python
raw_output_name = dataset_config.get("raw_output", "stock_candles.csv")
output = PROJECT_ROOT / "ml" / "data" / "raw" / raw_output_name
```

Before `run_ml_pipeline`, execute `training_config.get("pre_build_commands") or []` with the same subprocess logic from Task 5.

- [ ] **Step 5: Run focused test**

Run:

```bash
python3 -m pytest tests/backend/test_ml_scheduler_presets.py -v
```

Expected: PASS.

- [ ] **Step 6: Static syntax check**

Run:

```bash
python3 -m py_compile backend/services/ml_scheduler.py
```

Expected: exit code 0.

- [ ] **Step 7: Commit**

```bash
git add backend/services/ml_scheduler.py tests/backend/test_ml_scheduler_presets.py
git commit -m "feat: schedule split stock shadow training"
```

---

### Task 7: 분리 모델 교체 후보 판정 서비스

**Files:**
- Create: `backend/services/ml_split_model_promotion_service.py`
- Create: `tests/backend/test_ml_split_model_promotion_service.py`

**Interfaces:**
- Consumes:
  - summary JSON dicts from `ml/src/run_pipeline_bundle.py`
- Produces:
  - Function `evaluate_split_model_candidate(baseline: dict, candidate: dict) -> dict[str, object]`
  - Return keys: `passed`, `checks`, `baseline`, `candidate`

- [ ] **Step 1: Write failing tests**

Create `tests/backend/test_ml_split_model_promotion_service.py`:

```python
from backend.services.ml_split_model_promotion_service import evaluate_split_model_candidate


def build_summary(excess: float, mdd: float, risk_auc: float, risk_top10: float) -> dict:
    return {
        "backtest_composite_summary": {
            "excess_return_net": excess,
            "max_drawdown_net": mdd,
        },
        "risk_metrics": {
            "roc_auc": risk_auc,
            "precision_at_top_10pct": risk_top10,
        },
    }


def test_candidate_passes_when_return_improves_without_worse_risk():
    baseline = build_summary(0.02, -0.25, 0.58, 0.45)
    candidate = build_summary(0.03, -0.20, 0.59, 0.46)

    result = evaluate_split_model_candidate(baseline, candidate)

    assert result["passed"] is True
    assert all(check["passed"] for check in result["checks"])


def test_candidate_fails_when_mdd_is_worse_even_if_return_improves():
    baseline = build_summary(0.02, -0.25, 0.58, 0.45)
    candidate = build_summary(0.03, -0.40, 0.59, 0.46)

    result = evaluate_split_model_candidate(baseline, candidate)

    assert result["passed"] is False
    assert any(check["name"] == "max_drawdown_not_worse" and not check["passed"] for check in result["checks"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python3 -m pytest tests/backend/test_ml_split_model_promotion_service.py -v
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement promotion service**

Create `backend/services/ml_split_model_promotion_service.py`:

```python
from typing import Any


def safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def evaluate_split_model_candidate(baseline: dict, candidate: dict) -> dict[str, object]:
    baseline_backtest = baseline.get("backtest_composite_summary") or {}
    candidate_backtest = candidate.get("backtest_composite_summary") or {}
    baseline_risk = baseline.get("risk_metrics") or {}
    candidate_risk = candidate.get("risk_metrics") or {}

    baseline_excess = safe_float(baseline_backtest.get("excess_return_net"))
    candidate_excess = safe_float(candidate_backtest.get("excess_return_net"))
    baseline_mdd = safe_float(baseline_backtest.get("max_drawdown_net"))
    candidate_mdd = safe_float(candidate_backtest.get("max_drawdown_net"))
    baseline_risk_auc = safe_float(baseline_risk.get("roc_auc"))
    candidate_risk_auc = safe_float(candidate_risk.get("roc_auc"))
    baseline_risk_top10 = safe_float(baseline_risk.get("precision_at_top_10pct"))
    candidate_risk_top10 = safe_float(candidate_risk.get("precision_at_top_10pct"))

    checks = [
        {
            "name": "composite_excess_return_improved",
            "passed": candidate_excess > baseline_excess,
            "candidate": candidate_excess,
            "baseline": baseline_excess,
        },
        {
            "name": "max_drawdown_not_worse",
            "passed": candidate_mdd >= baseline_mdd,
            "candidate": candidate_mdd,
            "baseline": baseline_mdd,
        },
        {
            "name": "risk_auc_not_worse",
            "passed": candidate_risk_auc >= baseline_risk_auc,
            "candidate": candidate_risk_auc,
            "baseline": baseline_risk_auc,
        },
        {
            "name": "risk_top10_not_worse",
            "passed": candidate_risk_top10 >= baseline_risk_top10,
            "candidate": candidate_risk_top10,
            "baseline": baseline_risk_top10,
        },
    ]

    return {
        "passed": all(check["passed"] for check in checks),
        "checks": checks,
        "baseline": {
            "composite_excess_return_net": baseline_excess,
            "max_drawdown_net": baseline_mdd,
            "risk_roc_auc": baseline_risk_auc,
            "risk_precision_at_top_10pct": baseline_risk_top10,
        },
        "candidate": {
            "composite_excess_return_net": candidate_excess,
            "max_drawdown_net": candidate_mdd,
            "risk_roc_auc": candidate_risk_auc,
            "risk_precision_at_top_10pct": candidate_risk_top10,
        },
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
python3 -m pytest tests/backend/test_ml_split_model_promotion_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/ml_split_model_promotion_service.py tests/backend/test_ml_split_model_promotion_service.py
git commit -m "feat: evaluate split model promotion candidates"
```

---

### Task 8: 관리자 페이지 내부 탭 분리

**Files:**
- Modify: `frontend/src/pages/AdminMlData.jsx`
- Create: `frontend/src/pages/AdminInquiryPanel.jsx`

**Interfaces:**
- Consumes: existing `AdminMlData` props `isLoggedIn`, `userEmail`, `handleLogout`
- Produces:
  - component `AdminInquiryPanel()`
  - state `adminTab: "ml" | "inquiries"`

- [ ] **Step 1: Create inquiry panel component**

Create `frontend/src/pages/AdminInquiryPanel.jsx`:

```jsx
export default function AdminInquiryPanel() {
  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <h2 className="text-lg font-bold text-white">문의답변</h2>
    </section>
  )
}
```

- [ ] **Step 2: Modify AdminMlData imports and state**

At the top of `frontend/src/pages/AdminMlData.jsx`, add:

```jsx
import AdminInquiryPanel from './AdminInquiryPanel.jsx'
```

Inside `AdminMlData`, add:

```jsx
const [adminTab, setAdminTab] = useState('ml')
```

- [ ] **Step 3: Add tab buttons**

Near the top of the page content after `<Header ... />`, render:

```jsx
<div className="mx-auto flex w-full max-w-7xl gap-2 px-4 pt-6 sm:px-6 lg:px-8">
  {[
    { key: 'ml', label: '머신러닝' },
    { key: 'inquiries', label: '문의답변' },
  ].map((tab) => (
    <button
      key={tab.key}
      type="button"
      onClick={() => setAdminTab(tab.key)}
      className={`rounded border px-4 py-2 text-xs font-bold transition ${
        adminTab === tab.key
          ? 'border-ai-cyan bg-ai-cyan text-[#07111f]'
          : 'border-slate-700 bg-[#0f172a] text-slate-400 hover:text-white'
      }`}
    >
      {tab.label}
    </button>
  ))}
</div>
```

- [ ] **Step 4: Wrap ML content and inquiry panel**

Wrap the existing ML sections in:

```jsx
{adminTab === 'ml' ? (
  <>
    {/* existing ML content */}
  </>
) : (
  <AdminInquiryPanel />
)}
```

Keep the existing ML content unchanged inside the fragment.

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build exits 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/AdminMlData.jsx frontend/src/pages/AdminInquiryPanel.jsx
git commit -m "feat: split admin page into ml and inquiry tabs"
```

---

### Task 9: 관리자 ML 버튼 3분리 preset 노출

**Files:**
- Modify: `frontend/src/pages/AdminMlData.jsx`

**Interfaces:**
- Consumes:
  - backend preset keys `kr-stock-v1-full`, `us-stock-v1-full`, `crypto-v8-full`
- Produces:
  - UI buttons for three shadow model runs

- [ ] **Step 1: Update automation presets**

In `frontend/src/pages/AdminMlData.jsx`, add these entries to `automationPresets`:

```jsx
{
  key: 'kr-stock-v1-full',
  label: '국내주식 v1 자동 수집+학습',
  summary: 'stock_kr_core_45 + DART 공시 피처를 포함한 국내주식 shadow 모델',
  version: 'split-v1',
  isNew: true,
},
{
  key: 'us-stock-v1-full',
  label: '해외주식 v1 자동 수집+학습',
  summary: 'stock_us_core_45 기반 해외주식 shadow 모델. DART 피처는 제외합니다.',
  version: 'split-v1',
  isNew: true,
},
```

Replace:

```jsx
const operationalAutomationPresets = automationPresets.filter((preset) => preset.version === 'v8')
```

with:

```jsx
const operationalAutomationPresets = automationPresets.filter((preset) => ['v8', 'split-v1'].includes(preset.version))
```

- [ ] **Step 2: Update active signal refresh logic**

In `handleRunFullAutomation`, replace:

```jsx
await loadActiveSignals(preset.key.includes('crypto') ? 'CRYPTO' : 'STOCK')
```

with:

```jsx
await loadActiveSignals(preset.key.includes('crypto') ? 'CRYPTO' : 'STOCK')
```

This line remains unchanged because backend registry currently groups domestic and overseas stock under `STOCK`. Add a Korean code comment directly above it:

```jsx
// 국내/해외 분리 모델도 현재 registry asset_type은 STOCK으로 동기화합니다.
```

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build exits 0.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AdminMlData.jsx
git commit -m "feat: expose split model automation controls"
```

---

### Task 10: 문서 갱신과 최종 검증

**Files:**
- Modify: `ml/README.md`
- Modify: `project_structure.md`

**Interfaces:**
- Consumes: Tasks 1-9 delivered files
- Produces: up-to-date project documentation

- [ ] **Step 1: Update `ml/README.md`**

Add a section named `3분리 모델 자동화`:

```markdown
## 3분리 모델 자동화

주식 통합 모델은 안전망으로 유지하며, 신규 shadow 모델은 국내주식, 해외주식, 코인으로 분리해 자동 수집+학습한다.

| 모델 | 유니버스 | raw 파일 | config | 공시 피처 |
| --- | --- | --- | --- | --- |
| 국내주식 | `stock_kr_core_45` | `ml/data/raw/kr_stock_candles.csv` | `ml/configs/lgbm_kr_stock_v1.yaml` | DART 사용 |
| 해외주식 | `stock_us_core_45` | `ml/data/raw/us_stock_candles.csv` | `ml/configs/lgbm_us_stock_v1.yaml` | DART 미사용 |
| 코인 | `crypto_core_30` | `ml/data/raw/crypto_candles_30m.csv` | `ml/configs/lgbm_crypto_v8.yaml` | 미사용 |

교체 판단은 자동 serving 교체가 아니라 `promotion_candidate` 판정으로 남긴다. 관리자는 composite 순초과수익, 최대낙폭, risk AUC, risk 상위 10% precision을 확인한 뒤 serving 교체 여부를 결정한다.
```

- [ ] **Step 2: Update `project_structure.md`**

Add entries for:

```text
backend/scripts/export_dart_features.py
backend/services/ml_split_model_promotion_service.py
ml/configs/lgbm_kr_stock_v1.yaml
ml/configs/lgbm_kr_stock_risk_v1.yaml
ml/configs/lgbm_us_stock_v1.yaml
ml/configs/lgbm_us_stock_risk_v1.yaml
frontend/src/pages/AdminInquiryPanel.jsx
```

- [ ] **Step 3: Run backend focused tests**

Run:

```bash
python3 -m pytest tests/backend/test_export_dart_features.py tests/backend/test_ml_automation_presets.py tests/backend/test_ml_scheduler_presets.py tests/backend/test_ml_split_model_promotion_service.py -v
```

Expected: all selected backend tests PASS.

- [ ] **Step 4: Run ML focused tests**

Run:

```bash
python3 -m pytest tests/ml/test_training_universes.py tests/ml/test_build_features_optional_paths.py tests/ml/test_split_stock_configs.py -v
```

Expected: all selected ML tests PASS.

- [ ] **Step 5: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: build exits 0.

- [ ] **Step 6: Run smoke config commands without external network**

Run:

```bash
python3 ml/src/build_features.py --config ml/configs/lgbm_kr_stock_v1.yaml
```

Expected: if `ml/data/raw/kr_stock_candles.csv` does not exist, command fails with a missing file error. That is acceptable before real collection. If the file exists, command exits 0 and writes `ml/data/processed/kr_stock_features_lgbm_v1.csv`.

Run:

```bash
python3 ml/src/build_features.py --config ml/configs/lgbm_us_stock_v1.yaml
```

Expected: if `ml/data/raw/us_stock_candles.csv` does not exist, command fails with a missing file error. That is acceptable before real collection. If the file exists, command exits 0 and writes `ml/data/processed/us_stock_features_lgbm_v1.csv`.

- [ ] **Step 7: Commit**

```bash
git add ml/README.md project_structure.md
git commit -m "docs: document split model automation"
```

---

## Final Verification Checklist

- [ ] `python3 -m pytest tests/backend/test_export_dart_features.py tests/backend/test_ml_automation_presets.py tests/backend/test_ml_scheduler_presets.py tests/backend/test_ml_split_model_promotion_service.py -v` passes.
- [ ] `python3 -m pytest tests/ml/test_training_universes.py tests/ml/test_build_features_optional_paths.py tests/ml/test_split_stock_configs.py -v` passes.
- [ ] `cd frontend && npm run build` exits 0.
- [ ] `/api/ml/automation/presets` returns `kr-stock-v1-full`, `us-stock-v1-full`, and `crypto-v8-full`.
- [ ] Existing `stock-v8-full` still exists.
- [ ] `ml/data/reference/training_universes.json` keeps `stock_core_90` unchanged.
- [ ] DART feature columns appear only in KR stock configs.
- [ ] Admin page shows `머신러닝` and `문의답변` tabs.
- [ ] No serving model is automatically changed by training completion.

## Self-Review Notes

- Spec coverage: 3분리 모델, shadow 자동화, 성능 우위 시 교체 후보, 관리자 내부 탭 분리를 모두 태스크로 반영했다.
- Placeholder scan: 실행자가 작성해야 할 파일명, 함수명, 주요 코드, 명령, 기대 결과를 명시했다.
- Type consistency: preset key, config key, 함수명, 반환 key를 태스크 간 동일하게 유지했다.
