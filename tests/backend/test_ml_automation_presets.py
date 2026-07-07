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
