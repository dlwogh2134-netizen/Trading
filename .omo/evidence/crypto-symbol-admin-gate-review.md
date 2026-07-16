# Crypto Symbol Admin Gate Review

## recommendation

REJECT

## originalIntent

The user wanted the crypto coin master/admin implementation completed per the local plan and docs:

- Use a single `crypto_assets` table for Coinone/Binance crypto symbol identity and exchange status.
- Add admin UI/API surfaces to list, sync, and edit crypto symbols.
- Make Coinone-only symbols such as `H`/Humanity open/use Coinone, not Binance.
- Make Binance-only symbols such as `ALICE` open/use Binance, not Coinone.
- Ensure listing/tradable/default exchange behavior is consistent across search, detail, chatbot, and order entry.
- Ensure `admin_trading_blocked` and non-tradable status block order proposal/execution paths.
- Update docs and provide verification artifacts.

## desiredOutcome

A reviewer should be able to observe, from code and artifacts, that:

- `crypto_assets` is the authoritative crypto symbol master.
- Sync stores current Coinone/Binance listed/tradable status correctly in one row per base symbol.
- Admin can view, sync, and edit the master.
- Detail/search/order/chatbot behavior uses the master and does not infer exchange only from symbol suffix.
- Invalid exchange choices are blocked or surfaced as unavailable.
- Tests and manual QA cover H/Humanity, Binance-only symbols, shared symbols, blocked symbols, and admin UI workflows.

## userOutcomeReview

The shipped working tree does not yet satisfy the expected user-visible outcome.

The admin UI exists in code, but the supplied admin screenshot only shows the unauthenticated member-only gate. The detail screenshots are blank shells with no asset detail, exchange selection, or H/ALICE behavior visible. The chatbot/order completion criteria from the implementation plan are not met: chatbot tool routing still defaults every crypto asset to Coinone, and `admin_trading_blocked` is not enforced at order proposal/execution boundaries.

## blockers

1. Chatbot crypto exchange routing is not wired to `crypto_assets`.

   Evidence: `backend/services/chatbot/tool_registry.py:205` still defines `_default_exchange_for_asset()` as `COINONE` for every `CRYPTO`. The call sites at `backend/services/chatbot/tool_registry.py:874`, `backend/services/chatbot/tool_registry.py:1212`, `backend/services/chatbot/tool_registry.py:1339`, `backend/services/chatbot/tool_registry.py:1439`, and `backend/services/chatbot/tool_registry.py:2004` continue to use that default. The changed chatbot file, `backend/services/chatbot/web_fallback_search_service.py`, only uses `find_crypto_asset_for_query()` for combined news/disclosure target recognition, not trading/market-context exchange selection. This fails the plan criteria for "ALICE" and other Binance-only assets in chatbot flows.

2. `admin_trading_blocked` is not enforced at order proposal/execution boundaries.

   Evidence: occurrences of `admin_trading_blocked` in `backend/routes/trade.py` are limited to order-entry search filtering around `backend/routes/trade.py:2430` and lookup payload fields around `backend/routes/trade.py:5387` / `backend/routes/trade.py:5428`. Direct order/precheck/proposal paths can still receive a known symbol without passing through the filtered search list. This fails the final completion criterion that blocked assets do not proceed to order proposal or execution.

3. Sync can leave stale exchange listing/tradable state in `crypto_assets`.

   Evidence: `backend/services/crypto_asset_sync_service.py:30` to `backend/services/crypto_asset_sync_service.py:40` builds the base payload without resetting `coinone_listed`, `coinone_tradable`, `binance_listed`, or `binance_tradable` to false. `sync_crypto_assets()` seeds every existing row with that partial payload at `backend/services/crypto_asset_sync_service.py:124` to `backend/services/crypto_asset_sync_service.py:133`, then patches it. If a symbol disappears from Coinone or Binance, the old true flags can survive. That does not support current listing/tradable correctness.

4. Invalid defaults can be saved for exchange-exclusive assets.

   Evidence: `backend/services/crypto_asset_service.py:230` to `backend/services/crypto_asset_service.py:234` validates only that `default_exchange` is one of the allowed enum values. It does not verify that the target asset is listed/tradable on that exchange. The admin modal also offers every exchange unconditionally in `frontend/src/pages/AdminCryptoAssetEditModal.jsx:36` to `frontend/src/pages/AdminCryptoAssetEditModal.jsx:40`. A Binance-only asset can therefore be set to `COINONE`, after which `SymbolSearch.jsx` and the detail pages will route to the wrong exchange from the saved default.

5. Manual QA artifacts do not demonstrate the requested behavior.

   Evidence checked:

   - `qa-artifacts/crypto-symbol-admin/admin-protected.png` shows only the member-only gate.
   - `qa-artifacts/crypto-symbol-admin/crypto-detail-exchange-query.png` is a blank app shell; it does not show asset details, exchange selection, or Binance/Coinone state.
   - `qa-artifacts/crypto-symbol-admin/crypto-detail-mobile.png` is also a blank shell.
   - `qa-artifacts/crypto-symbol-admin/qa-summary.json` only records text snippets and `desktopHasBinance=false` / `mobileHasBinance=false`; it does not prove H/Humanity, ALICE, admin sync/edit, or invalid exchange handling.

6. Required review/evidence artifacts are missing.

   Evidence checked:

   - `.omo/evidence/` contained only `member-only-access-gate-review.md` before this gate report.
   - No code review report for this crypto-symbol task was present.
   - No manual QA matrix was present.
   - No notepad path/artifact was provided.
   - No persisted pytest/lint/build logs were present for the claimed commands, except `qa-artifacts-crypto-vite.log`, which only shows the Vite dev server starting and HMR updates.

7. Scope drift is present in the working tree.

   Evidence: the current changed file set includes unrelated news/chatbot combined-result work and artifacts, including `backend/services/chatbot/web_fallback_search_service.py`, `backend/tests/test_news_freshness_and_summary_fallback.py`, `frontend/src/pages/News.jsx`, `frontend/src/pages/mobile/MobileNewsPage.jsx`, `frontend/src/features/chatbot/chatbotCombinedNotice.js`, and `qa-artifacts/news-search/news-gukmin-growth-fund.png`. Those are not part of the crypto symbol master/admin brief and make the branch harder to approve as a focused delivery.

8. The tests are too narrow and partially implementation-mirroring.

   Evidence:

   - `backend/tests/test_symbol_lookup.py:78` to `backend/tests/test_symbol_lookup.py:99` monkeypatches `find_crypto_asset_for_query()` to return the expected crypto payload, then verifies route serialization. It does not exercise real lookup/search behavior through `crypto_assets`.
   - `backend/tests/test_trade_order_entry_routes.py:130` to `backend/tests/test_trade_order_entry_routes.py:148` monkeypatches `search_crypto_assets()` with a hand-built result. It does not prove DB-backed listing/tradable filtering, blocked direct-order prevention, or fallback behavior.
   - There is no sync regression test for delisting/stale flags in `backend/services/crypto_asset_sync_service.py`.
   - There is no UI/manual test evidence for authenticated admin list/sync/edit.

## removeAiSlopAndProgrammingPass

Direct pass applied from `remove-ai-slops` and `programming` criteria:

- Overfit/tautological tests found: route tests mock the exact service output under review and assert pass-through fields, leaving core behavior unpinned.
- Missing behavior tests found: sync delisting reset, invalid default exchange validation, admin blocked direct order path, chatbot Binance-only exchange selection, and authenticated admin edit flow.
- Scope drift found: unrelated news/chatbot combined-result changes and QA artifact.
- Oversized edited files found: `backend/routes/trade.py` has 5274 pure LOC, `backend/services/chatbot/web_fallback_search_service.py` has 1332 pure LOC, `frontend/src/features/chatbot/ChatbotWidget.jsx` has 1107 pure LOC, `frontend/src/pages/AssetDetail.jsx` has 3174 pure LOC, and `frontend/src/pages/mobile/MobileAssetDetail.jsx` has 3171 pure LOC. The new target service files are within the 250 pure LOC limit, but the branch adds logic to several oversized legacy files without extracting the touched behavior.
- Required code-review report coverage for this skill-perspective check is absent; there is no report artifact showing the same slop/overfit coverage.

## checkedArtifactPaths

- `docs/superpowers/plans/2026-07-16-crypto-symbol-admin-management.md`
- `supabase/migrations/20260716103000_create_crypto_assets.sql`
- `backend/services/crypto_asset_service.py`
- `backend/services/crypto_asset_sync_service.py`
- `backend/routes/admin_symbols.py`
- `backend/routes/trade.py`
- `backend/services/symbol_metadata.py`
- `backend/services/chatbot/web_fallback_search_service.py`
- `backend/services/chatbot/tool_registry.py`
- `backend/tests/test_crypto_asset_service.py`
- `backend/tests/test_admin_crypto_symbols.py`
- `backend/tests/test_symbol_lookup.py`
- `backend/tests/test_trade_order_entry_routes.py`
- `frontend/src/components/SymbolSearch.jsx`
- `frontend/src/pages/AdminSymbolReconciliation.jsx`
- `frontend/src/pages/AdminCryptoAssetsPanel.jsx`
- `frontend/src/pages/AdminCryptoAssetEditModal.jsx`
- `frontend/src/pages/adminCryptoAssetModel.js`
- `frontend/src/pages/AssetDetail.jsx`
- `frontend/src/pages/mobile/MobileAssetDetail.jsx`
- `database_specification.md`
- `project_structure.md`
- `qa-artifacts/crypto-symbol-admin/admin-protected.png`
- `qa-artifacts/crypto-symbol-admin/crypto-detail-exchange-query.png`
- `qa-artifacts/crypto-symbol-admin/crypto-detail-mobile.png`
- `qa-artifacts/crypto-symbol-admin/qa-summary.json`
- `qa-artifacts-crypto-vite.log`

## exactEvidenceGaps

- No authenticated admin screenshot or trace showing the crypto master table.
- No admin sync QA showing Coinone/Binance rows populated.
- No admin edit QA showing PATCH works and persisted state refreshes.
- No H/Humanity detail QA showing Coinone selected and Binance unavailable.
- No Binance-only detail QA showing Binance selected and Coinone unavailable.
- No chatbot QA for H/Humanity, Binance H unavailable, ALICE Binance-only, or blocked assets.
- No order execution/precheck QA proving blocked or untradable assets are rejected outside autocomplete.
- No persisted pytest, lint, or build logs for the claimed verification commands.
- No code review report and no manual QA matrix.
