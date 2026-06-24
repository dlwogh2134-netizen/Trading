import argparse
import json
from pathlib import Path

import joblib
import yaml


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def resolve_ml_path(config_path: str, target_path: str) -> Path:
    base_dir = Path(config_path).resolve().parent.parent
    path = Path(target_path)
    return path if path.is_absolute() else base_dir / path


def main() -> None:
    parser = argparse.ArgumentParser(description="저장된 모델의 검증 지표를 출력합니다.")
    parser.add_argument("--config", default=None, help="학습 설정 파일 경로")
    parser.add_argument("--model", default="models/lgbm_stock_signal_v1.joblib", help="모델 파일 경로")
    args = parser.parse_args()

    model_path = Path(args.model)
    if args.config:
        config = load_config(args.config)
        model_path = resolve_ml_path(args.config, config["model"]["output_path"])

    payload = joblib.load(model_path)
    print(json.dumps(payload.get("metrics", {}), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
