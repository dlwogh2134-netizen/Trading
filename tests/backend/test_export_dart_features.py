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


def test_build_daily_dart_features_skips_blank_rcept_no():
    disclosures = [
        {
            "rcept_no": "   ",
            "stock_code": "005930",
            "report_nm": "단일판매ㆍ공급계약체결",
            "rcept_dt": "2026-07-07",
        }
    ]

    frame = build_daily_dart_features(disclosures, analyses=[])

    assert frame.empty


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


def test_build_shifted_dart_features_carries_weekend_disclosure_to_next_feature_date():
    feature_dates = pd.DataFrame(
        {
            "symbol": ["005930", "005930", "005930"],
            "date": pd.to_datetime(["2026-07-03", "2026-07-06", "2026-07-07"]),
        }
    )
    daily_features = pd.DataFrame(
        {
            "symbol": ["005930"],
            "date": ["2026-07-04"],
            "dart_disclosure_count": [1.0],
            "dart_sentiment_score": [-1.0],
            "dart_negative_count": [1.0],
            "dart_positive_count": [0.0],
            "dart_caution_count": [0.0],
            "dart_info_count": [0.0],
            "dart_ai_analyzed_count": [1.0],
            "dart_contract_flag": [0.0],
            "dart_financing_flag": [0.0],
            "dart_shareholder_return_flag": [0.0],
            "dart_risk_event_flag": [1.0],
            "dart_earnings_flag": [0.0],
        }
    )

    shifted = build_shifted_dart_features(feature_dates, daily_features)
    rows = shifted.sort_values("date").to_dict("records")

    assert rows[0]["dart_disclosure_count_3d"] == 0.0
    assert rows[1]["dart_disclosure_count_3d"] == 1.0
    assert rows[1]["dart_disclosure_count_7d"] == 1.0
    assert rows[1]["dart_disclosure_count_20d"] == 1.0
    assert rows[1]["dart_sentiment_sum_3d"] == -1.0
    assert rows[1]["dart_negative_count_3d"] == 1.0
    assert rows[1]["dart_risk_event_flag_20d"] == 1.0
    assert rows[2]["dart_disclosure_count_3d"] == 1.0
