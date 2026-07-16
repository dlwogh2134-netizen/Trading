# Crypto Symbol Admin Follow-up Evidence

## Gate blockers addressed

- Chatbot default exchange now consults `crypto_assets` through `find_crypto_asset_for_query(symbol)`.
- Chatbot order proposal creation now rejects crypto assets blocked by admin, not listed on the selected exchange, or not tradable.
- Manual order precheck and direct order routes now call the same crypto asset policy before exchange client loading.
- Sync starts each existing asset with `coinone_*` and `binance_*` listed/tradable flags reset to false, then fills only exchanges present in fresh API responses.
- Admin PATCH now rejects `default_exchange` values that are not listed for the asset.

## Verification commands

```text
python -m py_compile backend/services/crypto_asset_service.py backend/services/crypto_asset_sync_service.py backend/routes/trade.py backend/services/chatbot/tool_registry.py
```

Result: passed.

```text
python -m pytest backend/tests/test_crypto_asset_service.py backend/tests/test_admin_crypto_symbols.py backend/tests/test_symbol_lookup.py backend/tests/test_trade_order_entry_routes.py backend/tests/test_chatbot_crypto_asset_policy.py
```

Result: 25 passed, 1 warning. The warning is pytest cache permission for `.pytest_cache`.

Follow-up after real Supabase sync optimization:

```text
PYTHONIOENCODING=utf-8 python -m pytest backend/tests/test_crypto_asset_service.py backend/tests/test_admin_crypto_symbols.py backend/tests/test_symbol_lookup.py backend/tests/test_trade_order_entry_routes.py backend/tests/test_chatbot_crypto_asset_policy.py -q
```

Result: 26 passed, 1 warning. The warning is pytest cache permission for `.pytest_cache`.

```text
npm run build
```

Result: passed. Vite still reports the existing chunk-size warning over 500 kB.

```text
npm run lint
```

Result: 0 errors, 3 warnings in unrelated existing files:

- `frontend/src/pages/WatchlistTab.jsx`
- `frontend/src/pages/assetsTabModel.js`
- `frontend/src/pages/mobile/MobileWatchlistTab.jsx`

```text
git diff --check
```

Result: no whitespace errors. Git reports LF to CRLF normalization warnings.

## Remaining runtime prerequisites

- Applied `supabase/migrations/20260716103000_create_crypto_assets.sql` to the active Supabase project (`fdvhoaytcqnswuebocmr`) and sent `NOTIFY pgrst, 'reload schema'`.
- Ran real crypto asset sync after changing the service to bulk upsert. Result: `synced_count=972`, `coinone_count=600`, `binance_count=661`.
- Verified production rows:
  - `H`: `display_name_ko=휴머니티`, `display_name_en=Humanity`, `default_exchange=COINONE`, `coinone_listed=true`, `coinone_tradable=true`, `binance_listed=false`.
  - `ALICE`: `display_name_en=Alice`, `default_exchange=BINANCE`, `coinone_listed=false`, `binance_listed=true`, `binance_tradable=true`.
- Supabase security advisor produced no new `crypto_assets`-specific finding. It still reports pre-existing warnings on unrelated tables/functions such as `chatbot_qa_events`, `match_knowledge_chunks`, lock functions, and Auth leaked password protection.
- Authenticated admin browser QA still needs a valid admin session. Existing screenshots only prove unauthenticated protection.
