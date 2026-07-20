# Chatbot Price News Disclosure UI Gate Review

## recommendation
REJECT

## verdict
REVISE

## originalIntent
Chatbot queries asking for current price plus news and disclosures should render three separate user-visible result sections: current price, news, and disclosures. When no disclosures are available, the disclosure empty state must explicitly say that there are no disclosures within the recent 30-day window.

## desiredOutcome
- A compound chatbot tool result containing price plus `NEWS_DISCLOSURE_COMBINED` data renders a visible current-price section, a visible news section, and a visible disclosure section.
- The disclosure section remains present when empty and clearly states the recent 30-day window.
- Backend disclosure listing/counting respects the same 30-day cutoff used by the user-visible empty state.
- QA evidence includes the actual chatbot interaction state, not only the general app shell.

## userOutcomeReview
The shipped code partially supports the intent but does not prove or fully deliver the visible outcome. `buildPricePresentation()` extracts the price from `COMPOUND_INFO`, and `buildNewsPresentation()` / `buildDisclosurePresentation()` now unwrap `COMPOUND_INFO.secondary`. Direct function simulation confirmed a compound result with one news item and no disclosures produces:

```json
{
  "price.shouldRender": true,
  "newsItems": 1,
  "disclosureItems": 0,
  "notices": ["최근 30일 이내 DART 공시가 없습니다."]
}
```

That means the empty disclosure case renders through `CombinedResultNotices`, not through `DisclosureResults`; the notice block has no `DART 공시 요약` heading or disclosure count and is not a separate disclosure section. This fails the user-visible requirement for three separate result sections when disclosures are empty.

The screenshot `qa-chatbot-home.png` is fresh relative to the changed source files and shows no obvious home-surface overlap, but it only shows the dashboard and closed chatbot launcher. It does not exercise the requested chatbot interaction state.

## blockers
1. Missing distinct disclosure section for empty compound results.
   - Evidence: `frontend/src/features/chatbot/ChatbotWidget.jsx:205` renders a structured block; `frontend/src/features/chatbot/ChatbotWidget.jsx:209` only renders `DisclosureResults` when `hasDisclosureCards` is true; `frontend/src/features/chatbot/ChatbotWidget.jsx:211` renders no-result disclosure copy as `CombinedResultNotices`.
   - Evidence: `frontend/src/features/chatbot/ChatbotWidget.jsx:256` to `frontend/src/features/chatbot/ChatbotWidget.jsx:268` renders notices as plain paragraphs with no section label.
   - User impact: price and news can be visibly separated, but "no disclosures" is an unlabeled notice, not a third disclosure result section.

2. Direct chatbot disclosure empty state still has a generic no-result message.
   - Evidence: `backend/services/chatbot/web_fallback_search_service.py:145` to `backend/services/chatbot/web_fallback_search_service.py:149` returns `조건에 맞는 DART 공시 결과를 찾지 못했습니다.` with no 30-day window message.
   - Evidence: `frontend/src/features/chatbot/chatbotCombinedNotice.js:18` to `frontend/src/features/chatbot/chatbotCombinedNotice.js:21` still falls back to generic DART no-result text when the backend does not provide a `message`.
   - User impact: the explicit 30-day empty-state guarantee is not consistently true for disclosure queries.

3. Target UI state was not manually QA'd.
   - Evidence: checked `qa-chatbot-home.png`; it shows only the general home dashboard and closed chatbot launcher.
   - Evidence gap: no screenshot, DOM capture, browser trace, or manual QA matrix shows a chatbot message with price, news, and disclosure sections.

4. Asset detail crypto exchange changes introduce a functional regression outside the stated chatbot outcome.
   - Evidence: `frontend/src/pages/assetDetailModel.js:121` to `frontend/src/pages/assetDetailModel.js:129` returns `[]` for metadata that explicitly says no exchange is listed/tradable.
   - Evidence: `frontend/src/pages/AssetDetail.jsx:416` to `frontend/src/pages/AssetDetail.jsx:421` and `frontend/src/pages/mobile/MobileAssetDetail.jsx:416` to `frontend/src/pages/mobile/MobileAssetDetail.jsx:421` treat an empty supported-exchange list as "not unavailable" because of `cryptoOrderExchanges.length > 0`.
   - User impact: a crypto asset with known unsupported metadata can remain order-enabled instead of blocked with the unsupported-exchange message.

5. Required gate artifacts are missing for approval.
   - Evidence gap: no code review report for this specific chatbot/disclosure UI goal was found under `.omo/evidence`, `.omo/plans`, or `.omo/drafts`.
   - Evidence gap: no manual QA matrix or notepad path was provided.
   - Evidence gap: no current review report demonstrating direct `remove-ai-slops` and `programming` perspective coverage for this goal.

## checkedArtifactPaths
- `D:\KDH\Trading\qa-chatbot-home.png`
- `D:\KDH\Trading\frontend\src\features\chatbot\ChatbotWidget.jsx`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotPricePresentation.js`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotNewsPresentation.js`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotDisclosurePresentation.js`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotCombinedNotice.js`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotCombinedNotice.test.mjs`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotPricePresentation.test.mjs`
- `D:\KDH\Trading\frontend\src\pages\AssetDetail.jsx`
- `D:\KDH\Trading\frontend\src\pages\assetDetailModel.js`
- `D:\KDH\Trading\frontend\src\pages\assetDetailModel.test.mjs`
- `D:\KDH\Trading\frontend\src\pages\assetDetailNewsDisclosurePanel.jsx`
- `D:\KDH\Trading\frontend\src\pages\mobile\MobileAssetDetail.jsx`
- `D:\KDH\Trading\backend\services\dart_repository.py`
- `D:\KDH\Trading\backend\services\chatbot\web_fallback_search_service.py`
- `D:\KDH\Trading\backend\services\news_retention_service.py`
- `D:\KDH\Trading\backend\services\news_repository.py`
- `D:\KDH\Trading\backend\services\ml_scheduler.py`
- `D:\KDH\Trading\backend\tests\test_dart_repository_retention.py`
- `D:\KDH\Trading\backend\tests\test_news_retention_cleanup.py`
- `D:\KDH\Trading\backend\tests\test_news_cleanup_scheduler.py`
- `D:\KDH\Trading\supabase\migrations\20260720120000_add_disclosure_retention_cleanup.sql`
- `D:\KDH\Trading\database_specification.md`
- `D:\KDH\Trading\design.md`

## exactEvidenceGaps
- No rendered evidence for the actual chatbot interaction state.
- No proof that the disclosure no-result UI is presented as its own titled section.
- No test rendering `ChatbotWidget` or equivalent DOM output for a `COMPOUND_INFO` result with price, news, and empty disclosure.
- No test covering direct disclosure no-result copy after 30-day filtering.
- No test covering known-zero supported crypto exchanges in asset detail desktop/mobile order blocking.
- No code review report, manual QA matrix, or notepad path for this goal.

## directRemoveAiSlopsAndProgrammingPass
- Scope drift: asset-detail crypto exchange behavior and broad news retention changes are included in the dirty tree while the stated review intent is chatbot price/news/disclosure UI.
- Oversized edited source files remain unresolved: `ChatbotWidget.jsx` ~1140 pure LOC, `AssetDetail.jsx` ~3356 pure LOC, and `MobileAssetDetail.jsx` ~3222 pure LOC. The branch adds behavior inside these oversized modules without isolating the touched UI path.
- Test coverage is narrow and partially implementation-mirroring: `chatbotPricePresentation.test.mjs` verifies extraction/formatting only; `chatbotCombinedNotice.test.mjs` verifies notice text only. Neither proves the rendered three-section chatbot outcome.
- `backend/tests/test_dart_repository_retention.py` monkeypatches the private cutoff method, so it proves the parameter is threaded into list/count requests but does not test the actual 30-day date calculation.

## positiveEvidence
- `buildPricePresentation()` correctly extracts a valid `COMPOUND_INFO.price` result and formats KRW/USD prices.
- `buildNewsPresentation()` and `buildDisclosurePresentation()` now unwrap `COMPOUND_INFO.secondary` before parsing combined news/disclosure data.
- `_combined_disclosure_result_not_found()` returns a Korean message explicitly naming the recent 30-day DART disclosure window.
- `DartRepository.list_disclosures()` and `DartRepository.count_disclosures()` add `rcept_dt=gte.<cutoff>` filters.
- `qa-chatbot-home.png` is newer than the changed chatbot files and shows no obvious regression on the closed-launcher home surface.

## verificationPerformed
- Inspected source via codegraph and direct shell reads.
- Opened `qa-chatbot-home.png` with image viewer.
- Ran direct Node import simulation for compound price/news/no-disclosure presentation helpers.
- Ran `git diff --check` on the stated chatbot/backend disclosure files; it reported only line-ending warnings and no whitespace errors.

