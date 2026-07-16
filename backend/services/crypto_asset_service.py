from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

from backend.services.supabase_client import (
    query_supabase_as_service_role,
    safe_query_supabase_as_service_role,
)

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]

CRYPTO_ASSET_SELECT: Final = (
    "id,base_symbol,display_name_ko,display_name_en,aliases,default_exchange,"
    "is_visible,admin_trading_blocked,admin_block_reason,admin_note,"
    "coinone_listed,coinone_symbol,coinone_tradable,coinone_exchange_status,"
    "coinone_deposit_status,coinone_withdraw_status,coinone_raw_status,coinone_last_synced_at,"
    "binance_listed,binance_symbol,binance_tradable,binance_status,binance_raw_status,"
    "binance_last_synced_at,source,last_synced_at,created_at,updated_at"
)
VALID_DEFAULT_EXCHANGES: Final = {"COINONE", "BINANCE", "BINANCE_UM_FUTURES"}


@dataclass(frozen=True, slots=True)
class CryptoAssetPatch:
    display_name_ko: str | None = None
    display_name_en: str | None = None
    aliases: tuple[str, ...] | None = None
    default_exchange: str | None = None
    is_visible: bool | None = None
    admin_trading_blocked: bool | None = None
    admin_block_reason: str | None = None
    admin_note: str | None = None
    coinone_symbol: str | None = None
    binance_symbol: str | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_symbol(value: str | None) -> str:
    return str(value or "").strip().upper()


def _compact_text(value: JsonValue) -> str:
    return str(value or "").strip()


def _exchange_options(row: dict[str, JsonValue]) -> list[str]:
    options: list[str] = []
    if row.get("coinone_listed"):
        options.append("COINONE")
    if row.get("binance_listed"):
        options.append("BINANCE")
    return options


def _display_name(row: dict[str, JsonValue]) -> str:
    return (
        _compact_text(row.get("display_name_ko"))
        or _compact_text(row.get("display_name_en"))
        or _compact_text(row.get("base_symbol"))
    )


def _asset_row_for_search(row: dict[str, JsonValue]) -> dict[str, JsonValue]:
    markets: list[str] = []
    if row.get("coinone_listed"):
        markets.append("KRW")
    if row.get("binance_listed"):
        markets.append("USDT")

    return {
        "symbol": row.get("base_symbol"),
        "display_name": _display_name(row),
        "asset_type": "CRYPTO",
        "market": " · ".join(markets),
        "markets": markets,
        "exchanges": _exchange_options(row),
        "exchange_options": _exchange_options(row),
        "default_exchange": row.get("default_exchange") or "COINONE",
        "coinone_listed": bool(row.get("coinone_listed")),
        "coinone_tradable": bool(row.get("coinone_tradable")),
        "binance_listed": bool(row.get("binance_listed")),
        "binance_tradable": bool(row.get("binance_tradable")),
        "admin_trading_blocked": bool(row.get("admin_trading_blocked")),
        "admin_block_reason": row.get("admin_block_reason"),
        "aliases": row.get("aliases") or [],
    }


def _normalize_aliases(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if not values:
        return []
    aliases: list[str] = []
    for value in values:
        alias = str(value or "").strip()
        if alias and alias not in aliases:
            aliases.append(alias)
    return aliases


def _query_filter(query: str) -> str:
    escaped = query.replace("*", "").replace(",", " ").strip()
    return (
        f"(base_symbol.ilike.*{escaped}*,display_name_ko.ilike.*{escaped}*,"
        f"display_name_en.ilike.*{escaped}*)"
    )


def list_crypto_assets(
    query: str = "",
    exchange: str = "ALL",
    tradable: str = "ALL",
    blocked: str = "ALL",
    limit: int = 200,
) -> list[dict[str, JsonValue]]:
    params: dict[str, str] = {
        "select": CRYPTO_ASSET_SELECT,
        "order": "base_symbol.asc",
        "limit": str(max(1, min(int(limit or 200), 1000))),
    }
    normalized_query = str(query or "").strip()
    if normalized_query:
        params["or"] = _query_filter(normalized_query)

    normalized_exchange = str(exchange or "ALL").upper()
    if normalized_exchange == "COINONE":
        params["coinone_listed"] = "eq.true"
    elif normalized_exchange in {"BINANCE", "BINANCE_UM_FUTURES"}:
        params["binance_listed"] = "eq.true"

    normalized_tradable = str(tradable or "ALL").upper()
    if normalized_tradable == "TRUE":
        if normalized_exchange == "COINONE":
            params["coinone_tradable"] = "eq.true"
        elif normalized_exchange in {"BINANCE", "BINANCE_UM_FUTURES"}:
            params["binance_tradable"] = "eq.true"
    elif normalized_tradable == "FALSE":
        if normalized_exchange == "COINONE":
            params["coinone_tradable"] = "eq.false"
        elif normalized_exchange in {"BINANCE", "BINANCE_UM_FUTURES"}:
            params["binance_tradable"] = "eq.false"

    normalized_blocked = str(blocked or "ALL").upper()
    if normalized_blocked in {"TRUE", "FALSE"}:
        params["admin_trading_blocked"] = f"eq.{normalized_blocked.lower()}"

    rows = safe_query_supabase_as_service_role("crypto_assets", "GET", params=params) or []
    return rows if isinstance(rows, list) else []


def get_crypto_asset(base_symbol: str) -> dict[str, JsonValue] | None:
    symbol = _normalize_symbol(base_symbol)
    if not symbol:
        return None
    rows = safe_query_supabase_as_service_role(
        "crypto_assets",
        "GET",
        params={"select": CRYPTO_ASSET_SELECT, "base_symbol": f"eq.{symbol}", "limit": "1"},
    ) or []
    if not rows:
        return None
    return rows[0] if isinstance(rows[0], dict) else None


def search_crypto_assets(query: str, limit: int = 10) -> list[dict[str, JsonValue]]:
    text = str(query or "").strip()
    if not text:
        return []

    rows = list_crypto_assets(query=text, limit=limit)
    query_upper = text.upper()
    alias_matches = []
    for row in list_crypto_assets(limit=1000):
        aliases = row.get("aliases") or []
        if isinstance(aliases, list) and any(query_upper in str(alias).upper() for alias in aliases):
            alias_matches.append(row)

    merged: dict[str, dict[str, JsonValue]] = {}
    for row in [*rows, *alias_matches]:
        symbol = _normalize_symbol(str(row.get("base_symbol") or ""))
        if symbol and row.get("is_visible", True):
            merged[symbol] = row

    results = [_asset_row_for_search(row) for row in merged.values()]
    results.sort(key=lambda item: (0 if item.get("symbol") == query_upper else 1, len(str(item.get("symbol") or "")), str(item.get("symbol") or "")))
    return results[:limit]


def find_crypto_asset_for_query(query: str) -> dict[str, JsonValue] | None:
    text = str(query or "").strip()
    if not text:
        return None
    normalized = _normalize_symbol(text)
    direct = get_crypto_asset(normalized)
    if direct:
        return _asset_row_for_search(direct)

    for row in list_crypto_assets(query=text, limit=10):
        if normalized in {
            _normalize_symbol(str(row.get("base_symbol") or "")),
            _normalize_symbol(str(row.get("display_name_ko") or "")),
            _normalize_symbol(str(row.get("display_name_en") or "")),
        }:
            return _asset_row_for_search(row)

    for result in search_crypto_assets(text, limit=10):
        aliases = result.get("aliases") or []
        alias_hit = isinstance(aliases, list) and normalized in {_normalize_symbol(str(alias)) for alias in aliases}
        if result.get("symbol") == normalized or _normalize_symbol(str(result.get("display_name") or "")) == normalized or alias_hit:
            return result
    return None


def patch_crypto_asset(base_symbol: str, patch: CryptoAssetPatch) -> dict[str, JsonValue]:
    symbol = _normalize_symbol(base_symbol)
    if not symbol:
        raise ValueError("수정할 코인 심볼을 입력해 주세요.")

    payload: dict[str, JsonValue] = {"updated_at": _utc_now()}
    if patch.display_name_ko is not None:
        payload["display_name_ko"] = patch.display_name_ko.strip() or None
    if patch.display_name_en is not None:
        payload["display_name_en"] = patch.display_name_en.strip() or None
    if patch.aliases is not None:
        payload["aliases"] = _normalize_aliases(patch.aliases)
    if patch.default_exchange is not None:
        default_exchange = _normalize_symbol(patch.default_exchange)
        if default_exchange not in VALID_DEFAULT_EXCHANGES:
            raise ValueError("기본 거래소는 COINONE, BINANCE, BINANCE_UM_FUTURES 중 하나여야 합니다.")
        payload["default_exchange"] = default_exchange
    if patch.is_visible is not None:
        payload["is_visible"] = patch.is_visible
    if patch.admin_trading_blocked is not None:
        payload["admin_trading_blocked"] = patch.admin_trading_blocked
    if patch.admin_block_reason is not None:
        payload["admin_block_reason"] = patch.admin_block_reason.strip() or None
    if patch.admin_note is not None:
        payload["admin_note"] = patch.admin_note.strip() or None
    if patch.coinone_symbol is not None:
        payload["coinone_symbol"] = _normalize_symbol(patch.coinone_symbol) or None
    if patch.binance_symbol is not None:
        payload["binance_symbol"] = _normalize_symbol(patch.binance_symbol) or None

    query_supabase_as_service_role(f"crypto_assets?base_symbol=eq.{symbol}", "PATCH", json_data=payload)
    updated = get_crypto_asset(symbol)
    if not updated:
        raise ValueError("수정한 코인 종목을 다시 조회하지 못했습니다.")
    return updated
