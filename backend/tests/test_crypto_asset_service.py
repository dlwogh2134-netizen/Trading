from backend.services import crypto_asset_service
from backend.services import crypto_asset_sync_service


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


def test_patch_crypto_asset_rejects_unlisted_default_exchange(monkeypatch):
    row = {
        "base_symbol": "ALICE",
        "display_name_en": "Alice",
        "default_exchange": "BINANCE",
        "coinone_listed": False,
        "coinone_tradable": False,
        "binance_listed": True,
        "binance_tradable": True,
    }
    monkeypatch.setattr(crypto_asset_service, "get_crypto_asset", lambda symbol: row)

    patch = crypto_asset_service.CryptoAssetPatch(default_exchange="COINONE")

    try:
        crypto_asset_service.patch_crypto_asset("ALICE", patch)
    except ValueError as error:
        assert "상장되어 있지 않아" in str(error)
    else:
        raise AssertionError("unlisted default exchange was accepted")


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_sync_crypto_assets_resets_stale_exchange_flags(monkeypatch):
    existing = [{
        "base_symbol": "H",
        "default_exchange": "COINONE",
        "is_visible": True,
        "admin_trading_blocked": False,
        "coinone_listed": True,
        "coinone_tradable": True,
        "binance_listed": True,
        "binance_tradable": True,
    }]
    writes = []

    def fake_get(url, timeout=10):
        if "coinone" in url:
            return FakeResponse({"currencies": [{"symbol": "H", "name": "Humanity"}]})
        return FakeResponse({"symbols": []})

    monkeypatch.setattr(crypto_asset_sync_service, "list_crypto_assets", lambda limit=1000: existing)
    monkeypatch.setattr(crypto_asset_sync_service.requests, "get", fake_get)
    monkeypatch.setattr(
        crypto_asset_sync_service,
        "query_supabase_as_service_role",
        lambda endpoint, method, json_data=None, params=None, extra_headers=None: writes.append(
            (endpoint, method, json_data, params, extra_headers)
        ),
    )

    result = crypto_asset_sync_service.sync_crypto_assets()

    assert result["synced_count"] == 1
    assert writes[0][0] == "crypto_assets"
    assert writes[0][1] == "POST"
    assert writes[0][3] == {"on_conflict": "base_symbol"}
    assert writes[0][4] == {"Prefer": "resolution=merge-duplicates"}
    assert writes[0][2][0]["coinone_listed"] is True
    assert writes[0][2][0]["coinone_tradable"] is True
    assert writes[0][2][0]["binance_listed"] is False
    assert writes[0][2][0]["binance_tradable"] is False


def test_sync_crypto_assets_bulk_upserts_all_payloads(monkeypatch):
    existing = []
    writes = []

    def fake_get(url, timeout=10):
        if "coinone" in url:
            return FakeResponse({"currencies": [{"symbol": "H", "name": "Humanity"}]})
        return FakeResponse({"symbols": [{
            "baseAsset": "ALICE",
            "quoteAsset": "USDT",
            "symbol": "ALICEUSDT",
            "status": "TRADING",
            "isSpotTradingAllowed": True,
        }]})

    monkeypatch.setattr(crypto_asset_sync_service, "list_crypto_assets", lambda limit=1000: existing)
    monkeypatch.setattr(crypto_asset_sync_service.requests, "get", fake_get)
    monkeypatch.setattr(
        crypto_asset_sync_service,
        "query_supabase_as_service_role",
        lambda endpoint, method, json_data=None, params=None, extra_headers=None: writes.append(
            (endpoint, method, json_data, params, extra_headers)
        ),
    )

    result = crypto_asset_sync_service.sync_crypto_assets()

    assert result["synced_count"] == 2
    assert len(writes) == 1
    assert writes[0][0] == "crypto_assets"
    assert writes[0][1] == "POST"
    assert writes[0][3] == {"on_conflict": "base_symbol"}
    assert writes[0][4] == {"Prefer": "resolution=merge-duplicates"}
    assert {payload["base_symbol"] for payload in writes[0][2]} == {"H", "ALICE"}
    key_sets = {tuple(sorted(payload)) for payload in writes[0][2]}
    assert len(key_sets) == 1
