recommendation: REJECT
visualVerdict: REVISE

## blockers

1. Available screenshot does not exercise the changed UI.
   - Evidence: `D:\KDH\Trading\qa-chatbot-home.png` shows the desktop home/market ranking screen with the chatbot closed as a floating launcher. It does not show an opened chatbot message, price card, news card, disclosure card, or asset-detail disclosure empty state.
   - Impact: Korean/CJK wrapping, price/news/disclosure hierarchy, and dark stock-detail/chat-result fidelity cannot be approved from the provided pixels.

2. Browser interaction capture and reference screenshots are unavailable in the reviewed artifacts.
   - Evidence: the user stated browser interaction capture was unavailable. The only local PNG directly requested for inspection is `qa-chatbot-home.png`; the two intended user-provided reference screenshots are not available as local artifact paths in this review context.
   - Impact: no same-state pixel comparison or responsive breakpoint validation can be performed.

3. Required final-gate review inputs are missing for this specific visual review.
   - Missing: original implementation brief beyond the current review request, goal slug, success criteria, executor evidence, current code-review report, manual QA matrix, and notepad path.
   - Evidence: `.omo/evidence` contains older news/crypto gate artifacts, but no current report tied to `qa-chatbot-home.png` or this chatbot home visual-fidelity review.

4. Required `remove-ai-slops` / `programming` report coverage is absent.
   - Direct pass was applied in this report over the diff and source. However, no supplied/current code-review report explicitly documents the same slop, overfit-test, and programming-perspective coverage for this change.
   - Under the final-gate instruction, absent coverage is blocking.

5. Programming/slop direct pass found unresolved maintainability risk in touched UI files.
   - Evidence: touched files remain far above the 250 pure-LOC programming criterion: `frontend/src/features/chatbot/ChatbotWidget.jsx` 1140, `frontend/src/pages/AssetDetail.jsx` 3356, `frontend/src/pages/mobile/MobileAssetDetail.jsx` 3222, `frontend/src/pages/assetDetailNewsDisclosurePanel.jsx` 351.
   - Impact: the diff adds UI logic inside oversized legacy files without extraction. This is not a visual-pixel defect by itself, but it is unresolved under the required programming/remove-ai-slops gate.

## originalIntent

Review the chatbot/home visual change for fidelity to the two dark stock-detail/chat-result reference screenshots, with particular attention to responsive wrapping, Korean/CJK labels, price/news/disclosure hierarchy, disclosure/news empty-state copy, and whether the implementation is live DOM rather than a mock or pasted screenshot.

## desiredOutcome

The user expected a read-only verdict of PASS/REVISE/FAIL grounded in `qa-chatbot-home.png` and changed UI source, with concrete findings and blockers. Because browser capture was unavailable, judgment should be limited to the static PNG plus local source.

## userOutcomeReview

The shipped artifact cannot be accepted as visually verified. The available PNG demonstrates the dark navy/cyan home styling and Korean dashboard labels, but it does not show the changed chatbot result UI. Source inspection supports that the chatbot result implementation is real React DOM, not a raster mock, and the source hierarchy is price first, then news, then DART disclosure. The disclosure empty-state copy now states the 30-day window. Those source-level positives are insufficient for PASS because the relevant states were not rendered in evidence.

## checkedArtifactPaths

- `D:\KDH\Trading\qa-chatbot-home.png`
- `D:\KDH\Trading\design.md`
- `D:\KDH\Trading\frontend\src\features\chatbot\ChatbotWidget.jsx`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotPricePresentation.js`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotNewsPresentation.js`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotDisclosurePresentation.js`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotCombinedNotice.js`
- `D:\KDH\Trading\frontend\src\pages\assetDetailNewsDisclosurePanel.jsx`
- `D:\KDH\Trading\frontend\src\pages\AssetDetail.jsx`
- `D:\KDH\Trading\frontend\src\pages\mobile\MobileAssetDetail.jsx`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotPricePresentation.test.mjs`
- `D:\KDH\Trading\frontend\src\features\chatbot\chatbotCombinedNotice.test.mjs`
- `D:\KDH\Trading\frontend\src\pages\assetDetailModel.test.mjs`

## visualFindings

- Good: `qa-chatbot-home.png` uses the expected dark navy/cyan financial-terminal style. Visible Korean labels such as `주식 필터`, `국내`, `해외`, `시장 데이터를 불러오는 중입니다.`, `표시할 데이터가 없습니다.`, and `더보기` render legibly with no visible clipping in the desktop screenshot.
- Good: the implementation is real DOM for the reviewed chatbot result branch. `ChatbotWidget.jsx:205-209` renders `<PriceResults>`, `<NewsResults>`, and `<DisclosureResults>` as React components; no screenshot/background-image substitute was found for those cards.
- Good: hierarchy is source-correct for compound results: price is rendered before news and disclosure at `ChatbotWidget.jsx:205-209`.
- Good: the new price card uses mono numeric styling and semantic green/red/neutral change-rate tone at `ChatbotWidget.jsx:599-621`.
- Good: news and disclosure cards use `break-words`, `min-w-0`, and flex wrapping in key title/summary/metadata regions (`ChatbotWidget.jsx:424-473`, `ChatbotWidget.jsx:530-585`).
- Good: asset-detail disclosure empty state now says `최근 30일 이내 투자 관련 공시가 없습니다.` at `assetDetailNewsDisclosurePanel.jsx:331-334`.
- Finding: `PriceResults` truncates the Korean display name/symbol line (`ChatbotWidget.jsx:611`). This is probably acceptable for a compact sublabel, but if the reference expects full Korean names on narrow widths it should become wrapping text with a tooltip or title.
- Finding: `chatbotPricePresentation.test.mjs` contains mojibake in the Korean fixture display name (`?쒖꽦湲곗뾽`). It is not production-visible, but it weakens Korean/CJK precision coverage.

## exactEvidenceGaps

- No opened chatbot screenshot showing price/news/disclosure cards.
- No mobile screenshot at 360px or 430px.
- No tablet screenshot at 768px.
- No browser DOM capture or interaction evidence.
- No pixel-diff evidence against the two intended reference screenshots.
- No rendered evidence for long Korean titles, particles/endings, parentheticals, or long display names in the changed chatbot cards.
- No rendered evidence for the asset-detail disclosure empty state.
- No current code-review report with `remove-ai-slops` and `programming` coverage.
- No manual QA matrix for the visual states under review.

## verification

- Static image inspection: opened `D:\KDH\Trading\qa-chatbot-home.png`.
- Source inspection: inspected git diff and source via codegraph/shell for changed UI files.
- Targeted tests run: `node --test frontend/src/features/chatbot/chatbotPricePresentation.test.mjs frontend/src/features/chatbot/chatbotCombinedNotice.test.mjs frontend/src/pages/assetDetailModel.test.mjs`
- Test result: 13 tests passed, 0 failed.
- Whitespace check: `git diff --check` reported only LF-to-CRLF warnings, no whitespace error output.

## final

REJECT. The source direction is plausible and uses real DOM, but available visual evidence does not render the changed UI and required review artifacts are missing.
