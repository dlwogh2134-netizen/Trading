import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
import yaml


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def resolve_ml_path(config_path: str, target_path: str) -> Path:
    base_dir = Path(config_path).resolve().parent.parent
    path = Path(target_path)
    return path if path.is_absolute() else base_dir / path


def split_by_time(df: pd.DataFrame, validation_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.Series(pd.to_datetime(df["date"]).sort_values().unique())
    split_index = max(1, int(len(dates) * (1 - validation_ratio)))
    split_date = dates.iloc[split_index - 1]
    train_df = df[pd.to_datetime(df["date"]) <= split_date].copy()
    valid_df = df[pd.to_datetime(df["date"]) > split_date].copy()
    if train_df.empty or valid_df.empty:
        raise ValueError("시계열 검증 분할 결과가 비어 있습니다. 데이터 기간을 늘려주세요.")
    return train_df, valid_df


def load_model_payload(path: Path) -> dict:
    return joblib.load(path)


def resolve_output_paths(config: dict, strategy: str) -> tuple[Path, Path]:
    if strategy == "composite":
        return (
            Path(config["data"]["backtest_composite_summary_path"]),
            Path(config["data"]["backtest_composite_daily_path"]),
        )
    return (
        Path(config["data"]["backtest_up_only_summary_path"]),
        Path(config["data"]["backtest_up_only_daily_path"]),
    )


def build_daily_backtest(
    valid_df: pd.DataFrame,
    top_n: int,
) -> tuple[pd.DataFrame, dict]:
    daily_rows = []
    selection_rows = []

    for date, group in valid_df.groupby("date", sort=True):
        ranked = group.sort_values("signal_score", ascending=False).copy()
        selected = ranked.head(min(top_n, len(ranked))).copy()
        if selected.empty:
            continue

        top_avg_return = float(selected["future_return"].mean())
        universe_avg_return = float(ranked["future_return"].mean())
        excess_return = top_avg_return - universe_avg_return

        daily_rows.append({
            "date": date,
            "selected_symbols": ",".join(selected["symbol"].astype(str).tolist()),
            "selected_count": int(len(selected)),
            "top_avg_future_return": top_avg_return,
            "universe_avg_future_return": universe_avg_return,
            "excess_return": excess_return,
            "avg_signal_score": float(selected["signal_score"].mean()),
            "avg_up_probability": float(selected["up_probability"].mean()),
            "avg_risk_probability": float(selected["risk_probability"].mean()),
        })

        selection_rows.append(selected[[
            "symbol",
            "future_return",
            "up_probability",
            "risk_probability",
            "signal_score",
        ]].assign(date=date))

    daily_df = pd.DataFrame(daily_rows)
    selections_df = pd.concat(selection_rows, ignore_index=True) if selection_rows else pd.DataFrame()

    summary = {
        "test_periods": int(len(daily_df)),
        "top_n": int(top_n),
        "top_avg_future_return": float(daily_df["top_avg_future_return"].mean()) if not daily_df.empty else 0.0,
        "universe_avg_future_return": float(daily_df["universe_avg_future_return"].mean()) if not daily_df.empty else 0.0,
        "excess_return": float(daily_df["excess_return"].mean()) if not daily_df.empty else 0.0,
        "date_win_rate": float((daily_df["top_avg_future_return"] > 0).mean()) if not daily_df.empty else 0.0,
        "selection_win_rate": float((selections_df["future_return"] > 0).mean()) if not selections_df.empty else 0.0,
        "avg_signal_score": float(selections_df["signal_score"].mean()) if not selections_df.empty else 0.0,
        "avg_up_probability": float(selections_df["up_probability"].mean()) if not selections_df.empty else 0.0,
        "avg_risk_probability": float(selections_df["risk_probability"].mean()) if not selections_df.empty else 0.0,
        "selected_rows": int(len(selections_df)),
    }
    return daily_df, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="signal_score 기준 단순 백테스트를 수행합니다.")
    parser.add_argument("--config", default="configs/lgbm_stock_v1.yaml", help="상승 모델 설정 파일 경로")
    parser.add_argument("--model", default=None, help="상승 모델 파일 경로")
    parser.add_argument("--risk-model", default=None, help="하락 위험 모델 파일 경로")
    parser.add_argument("--strategy", choices=["up_only", "composite"], default="up_only")
    parser.add_argument("--top-n", type=int, default=3, help="날짜별 상위 후보 개수")
    parser.add_argument("--summary-output", default=None, help="백테스트 요약 JSON 경로")
    parser.add_argument("--daily-output", default=None, help="백테스트 일별 CSV 경로")
    args = parser.parse_args()

    config = load_config(args.config)
    features_path = resolve_ml_path(args.config, config["data"]["features_path"])
    model_path = resolve_ml_path(args.config, args.model or config["model"]["output_path"])
    risk_model_path = args.risk_model or config.get("prediction", {}).get("risk_model_path")

    features_df = pd.read_csv(features_path)
    _, valid_df = split_by_time(features_df, float(config["model"]["validation_ratio"]))

    up_payload = load_model_payload(model_path)
    up_model = up_payload["model"]
    up_feature_columns = up_payload["config"]["model"]["feature_columns"]
    valid_df = valid_df.copy()
    valid_df["up_probability"] = up_model.predict_proba(valid_df[up_feature_columns])[:, 1]
    valid_df["risk_probability"] = 1 - valid_df["up_probability"]
    valid_df["scoring_strategy"] = "up_only"
    valid_df["up_model_version"] = up_payload["config"]["model"]["version"]
    valid_df["risk_model_version"] = ""
    valid_df["signal_score"] = valid_df["up_probability"] * 100

    if args.strategy == "composite":
        if not risk_model_path:
            raise ValueError("복합 백테스트에는 risk 모델 경로가 필요합니다.")
        risk_payload = load_model_payload(resolve_ml_path(args.config, str(risk_model_path)))
        risk_model = risk_payload["model"]
        risk_feature_columns = risk_payload["config"]["model"]["feature_columns"]
        valid_df["risk_probability"] = risk_model.predict_proba(valid_df[risk_feature_columns])[:, 1]
        valid_df["risk_model_version"] = risk_payload["config"]["model"]["version"]
        valid_df["signal_score"] = (valid_df["up_probability"] - valid_df["risk_probability"]) * 100
        valid_df["scoring_strategy"] = "composite"

    summary_output, daily_output = resolve_output_paths(config, args.strategy)
    if not summary_output.is_absolute():
        summary_output = resolve_ml_path(args.config, str(summary_output))
    if not daily_output.is_absolute():
        daily_output = resolve_ml_path(args.config, str(daily_output))
    if args.summary_output:
        summary_output = Path(args.summary_output)
    if args.daily_output:
        daily_output = Path(args.daily_output)

    daily_df, summary = build_daily_backtest(valid_df, args.top_n)
    summary.update({
        "strategy": args.strategy,
        "asset_type": config["model"]["asset_type"],
        "model_version": up_payload["config"]["model"]["version"],
        "risk_model_version": valid_df["risk_model_version"].iloc[0] if not valid_df.empty else "",
        "top_n": args.top_n,
        "valid_rows": int(len(valid_df)),
        "valid_start_date": str(valid_df["date"].min()) if not valid_df.empty else "",
        "valid_end_date": str(valid_df["date"].max()) if not valid_df.empty else "",
    })

    summary_output.parent.mkdir(parents=True, exist_ok=True)
    daily_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    daily_df.to_csv(daily_output, index=False)

    print(f"백테스트 요약 저장 완료: {summary_output}")
    print(f"백테스트 일별 결과 저장 완료: {daily_output}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
