from backend.services import crypto_asset_service


def test_search_crypto_assets_matches_alias_and_returns_exchange_options(monkeypatch):
    rows = [{
        "base_symbol": "H",
        "display_name_ko": "휴머니티",
        "display_name_en": "Humanity",
        "aliases": ["Humanity", "휴머니티"],
        "default_exchange": "COINONE",
        "is_visible": True,
        "admin_trading_blocked": False,
        "coinone_listed": True,
        "coinone_tradable": True,
        "binance_listed": False,
        "binance_tradable": False,
    }]

    def fake_safe_query(endpoint, method="GET", json_data=None, params=None):
        assert endpoint == "crypto_assets"
        return rows

    monkeypatch.setattr(crypto_asset_service, "safe_query_supabase_as_service_role", fake_safe_query)

    results = crypto_asset_service.search_crypto_assets("휴머니티")

    assert results == [{
        "symbol": "H",
        "display_name": "휴머니티",
        "asset_type": "CRYPTO",
        "market": "KRW",
        "markets": ["KRW"],
        "exchanges": ["COINONE"],
        "exchange_options": ["COINONE"],
        "default_exchange": "COINONE",
        "coinone_listed": True,
        "coinone_tradable": True,
        "binance_listed": False,
        "binance_tradable": False,
        "admin_trading_blocked": False,
        "admin_block_reason": None,
        "aliases": ["Humanity", "휴머니티"],
    }]


def test_find_crypto_asset_for_query_returns_binance_only_default(monkeypatch):
    rows = [{
        "base_symbol": "ALICE",
        "display_name_ko": None,
        "display_name_en": "Alice",
        "aliases": [],
        "default_exchange": "BINANCE",
        "is_visible": True,
        "admin_trading_blocked": False,
        "coinone_listed": False,
        "coinone_tradable": False,
        "binance_listed": True,
        "binance_tradable": True,
    }]

    def fake_safe_query(endpoint, method="GET", json_data=None, params=None):
        assert endpoint == "crypto_assets"
        return rows

    monkeypatch.setattr(crypto_asset_service, "safe_query_supabase_as_service_role", fake_safe_query)

    result = crypto_asset_service.find_crypto_asset_for_query("ALICE")

    assert result["symbol"] == "ALICE"
    assert result["default_exchange"] == "BINANCE"
    assert result["exchange_options"] == ["BINANCE"]
