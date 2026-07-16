from __future__ import annotations

from typing import Final

import requests

from backend.services.crypto_asset_service import (
    JsonValue,
    _compact_text,
    _normalize_symbol,
    _utc_now,
    list_crypto_assets,
)
from backend.services.supabase_client import query_supabase_as_service_role

COINONE_CURRENCIES_URL: Final = "https://api.coinone.co.kr/public/v2/currencies"
BINANCE_EXCHANGE_INFO_URL: Final = "https://api.binance.com/api/v3/exchangeInfo"


def _coinone_tradable(currency: dict[str, JsonValue]) -> bool:
    status_values = [
        _compact_text(currency.get("trade_status")).lower(),
        _compact_text(currency.get("status")).lower(),
        _compact_text(currency.get("currency_status")).lower(),
    ]
    blocked_terms = {"suspended", "stopped", "delisted", "disabled", "paused", "terminated"}
    return not any(value in blocked_terms for value in status_values if value)


def _merge_payload(base_symbol: str, existing: dict[str, JsonValue] | None) -> dict[str, JsonValue]:
    now = _utc_now()
    return {
        "base_symbol": base_symbol,
        "default_exchange": existing.get("default_exchange") if existing else "COINONE",
        "is_visible": existing.get("is_visible") if existing else True,
        "admin_trading_blocked": existing.get("admin_trading_blocked") if existing else False,
        "source": "API_SYNC",
        "last_synced_at": now,
        "updated_at": now,
    }


def _upsert_asset(payload: dict[str, JsonValue], existing_symbols: set[str]) -> None:
    symbol = str(payload.get("base_symbol") or "")
    if symbol in existing_symbols:
        query_supabase_as_service_role(f"crypto_assets?base_symbol=eq.{symbol}", "PATCH", json_data=payload)
        return
    query_supabase_as_service_role("crypto_assets", "POST", json_data=payload)
    existing_symbols.add(symbol)


def _merge_coinone_assets(
    merged: dict[str, dict[str, JsonValue]],
    existing_by_symbol: dict[str, dict[str, JsonValue]],
    synced_at: str,
) -> int:
    response = requests.get(COINONE_CURRENCIES_URL, timeout=10)
    response.raise_for_status()
    count = 0
    for currency in response.json().get("currencies", []):
        if not isinstance(currency, dict):
            continue
        base_symbol = _normalize_symbol(str(currency.get("symbol") or ""))
        if not base_symbol:
            continue
        payload = merged.setdefault(base_symbol, _merge_payload(base_symbol, existing_by_symbol.get(base_symbol)))
        payload.update({
            "display_name_en": payload.get("display_name_en") or _compact_text(currency.get("name")) or None,
            "coinone_listed": True,
            "coinone_symbol": base_symbol,
            "coinone_tradable": _coinone_tradable(currency),
            "coinone_exchange_status": _compact_text(currency.get("trade_status") or currency.get("status")) or None,
            "coinone_deposit_status": _compact_text(currency.get("deposit_status")) or None,
            "coinone_withdraw_status": _compact_text(currency.get("withdraw_status")) or None,
            "coinone_raw_status": currency,
            "coinone_last_synced_at": synced_at,
            "default_exchange": payload.get("default_exchange") or "COINONE",
        })
        count += 1
    return count


def _merge_binance_assets(
    merged: dict[str, dict[str, JsonValue]],
    existing_by_symbol: dict[str, dict[str, JsonValue]],
    synced_at: str,
) -> int:
    response = requests.get(BINANCE_EXCHANGE_INFO_URL, timeout=15)
    response.raise_for_status()
    count = 0
    for item in response.json().get("symbols", []):
        if not isinstance(item, dict) or item.get("quoteAsset") != "USDT":
            continue
        if item.get("isSpotTradingAllowed") is False:
            continue
        base_symbol = _normalize_symbol(str(item.get("baseAsset") or ""))
        market_symbol = _normalize_symbol(str(item.get("symbol") or ""))
        if not base_symbol or not market_symbol:
            continue
        payload = merged.setdefault(base_symbol, _merge_payload(base_symbol, existing_by_symbol.get(base_symbol)))
        has_coinone = bool(payload.get("coinone_listed"))
        payload.update({
            "binance_listed": True,
            "binance_symbol": market_symbol,
            "binance_tradable": item.get("status") == "TRADING",
            "binance_status": _compact_text(item.get("status")) or None,
            "binance_raw_status": item,
            "binance_last_synced_at": synced_at,
            "default_exchange": payload.get("default_exchange") or ("COINONE" if has_coinone else "BINANCE"),
        })
        if not has_coinone and payload.get("default_exchange") == "COINONE":
            payload["default_exchange"] = "BINANCE"
        count += 1
    return count


def sync_crypto_assets() -> dict[str, JsonValue]:
    existing_rows = list_crypto_assets(limit=1000)
    existing_by_symbol = {
        str(row.get("base_symbol") or ""): row
        for row in existing_rows
        if row.get("base_symbol")
    }
    merged = {
        symbol: _merge_payload(symbol, row)
        for symbol, row in existing_by_symbol.items()
    }
    synced_at = _utc_now()
    coinone_count = _merge_coinone_assets(merged, existing_by_symbol, synced_at)
    binance_count = _merge_binance_assets(merged, existing_by_symbol, synced_at)
    existing_symbols = set(existing_by_symbol)
    for payload in merged.values():
        _upsert_asset(payload, existing_symbols)

    return {
        "synced_count": len(merged),
        "coinone_count": coinone_count,
        "binance_count": binance_count,
        "synced_at": synced_at,
    }
