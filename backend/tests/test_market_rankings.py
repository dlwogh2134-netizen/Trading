from datetime import datetime, timedelta, timezone

from backend.routes.home import (
    build_direct_stock_ranking_rows,
    build_live_stock_ranking_rows,
    merge_rank_rows,
    sort_stock_rows_by_ranking,
)
from backend.services.home_service import enrich_stock_rows_with_toss, is_fresh_live_quote, parse_change_rate


def test_ranking_sort_prefers_live_change_rate():
    rows = [
        {"symbol": "STALE", "change_rate": 20, "live_change_rate": 1},
        {"symbol": "LIVE", "change_rate": 1, "live_change_rate": 12},
    ]

    sorted_rows = sort_stock_rows_by_ranking(rows, "상승률")

    assert [row["symbol"] for row in sorted_rows] == ["LIVE", "STALE"]
    assert parse_change_rate(rows[0]) == 1


def test_merge_rank_rows_fills_missing_value_from_same_symbol_fallback():
    primary_rows = [
        {
            "symbol": "AAPL",
            "current_price": 195,
            "change_rate": 8,
            "trading_value": 0,
            "trading_volume": 0,
        }
    ]
    fallback_rows = [
        {
            "symbol": "AAPL",
            "trading_value": 123_000,
            "trading_volume": 456,
            "as_of": "2026-07-20T09:00:00+00:00",
        }
    ]

    merged_rows = merge_rank_rows(primary_rows, fallback_rows, "상승률", 10)

    assert merged_rows[0]["trading_value"] == 123_000
    assert merged_rows[0]["trading_volume"] == 456
    assert merged_rows[0]["current_price"] == 195


def test_foreign_ranking_keeps_available_trading_value():
    rows = build_direct_stock_ranking_rows(
        [
            {
                "symbol": "AAPL",
                "current_price": 195.5,
                "change_rate": 4.2,
                "trading_value": 2_500_000,
                "trading_volume": 12_000,
            }
        ],
        "상승률",
        10,
        is_foreign=True,
    )

    assert rows[0]["trading_value"] == 2_500_000
    assert rows[0]["value"] != "-"


def test_expired_live_quote_is_not_eligible_for_ranking():
    now = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    fresh = {"live_quote_as_of": (now - timedelta(seconds=10)).isoformat()}
    expired = {"live_quote_as_of": (now - timedelta(seconds=31)).isoformat()}

    assert is_fresh_live_quote(fresh, now=now, max_age_seconds=30)
    assert not is_fresh_live_quote(expired, now=now, max_age_seconds=30)


def test_live_ranking_drops_expired_quotes_when_toss_is_configured(monkeypatch):
    import backend.routes.home as home_route

    monkeypatch.setattr(
        home_route,
        "get_toss_env_credentials",
        lambda: {"client_id": "client", "client_secret": "secret"},
    )
    monkeypatch.setattr(
        home_route,
        "enrich_stock_rows_with_toss",
        lambda rows, user_id=None, require_fresh=False, allow_network=True: rows,
    )

    rows = build_live_stock_ranking_rows(
        [
            {
                "symbol": "STALE",
                "current_price": 100,
                "change_rate": 20,
                "trading_value": 100,
                "live_quote_as_of": "2026-07-19T12:00:00+00:00",
            }
        ],
        "상승률",
        10,
        is_foreign=False,
    )

    assert rows == []


def test_home_enrichment_does_not_block_or_drop_base_rows_without_network(monkeypatch):
    monkeypatch.setattr(
        "backend.services.home_service.fetch_toss_price",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network call not allowed")),
    )

    rows = enrich_stock_rows_with_toss(
        [{"symbol": "005930", "current_price": 75_000, "change_rate": 1.2}],
        allow_network=False,
    )

    assert rows[0]["symbol"] == "005930"
    assert rows[0]["current_price"] == 75_000


def test_market_rankings_uses_home_snapshot_for_domestic_stock(monkeypatch):
    import backend.app as backend_app
    import backend.routes.home as home_route

    monkeypatch.setattr(
        home_route,
        "fetch_top_turnover_stock_rows",
        lambda **kwargs: [
            {
                "rank": 1,
                "code": "010170",
                "name": "대한광통신",
                "price": "11,230",
                "change": "-10.87%",
                "trading_volume": 11_357_787,
                "trading_value": 138_801_023_295,
            }
        ],
    )

    response = backend_app.app.test_client().get(
        "/api/market/rankings?asset_type=STOCK&region=국내&ranking=거래량&limit=100"
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["data"]["items"][0]["code"] == "010170"
