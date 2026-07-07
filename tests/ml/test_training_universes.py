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
