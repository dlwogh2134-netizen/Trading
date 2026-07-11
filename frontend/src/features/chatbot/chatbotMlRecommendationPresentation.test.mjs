import assert from 'node:assert/strict'
import test from 'node:test'

import { buildMlRecommendationPresentation } from './chatbotMlRecommendationPresentation.js'

test('builds compact ML recommendation card data', () => {
  const presentation = buildMlRecommendationPresentation({
    source: 'ML_ACTIVE_SIGNAL',
    asset_key: 'us_stock',
    model_version: 'lgbm_us_stock_signal_v1',
    items: [
      {
        display_name: 'Reddit',
        symbol: 'RDDT',
        signal_score: 63.13,
        up_probability: 0.767,
        risk_probability: 0.106,
        reason_summary: '상승 후보입니다. 상승 확률 76.7%, 하락 위험 10.6%, 조정 스프레드 0.631입니다.',
      },
    ],
  })

  assert.equal(presentation.shouldRender, true)
  assert.equal(presentation.title, '미국주식 ML 추천 후보')
  assert.equal(presentation.modelVersion, 'lgbm_us_stock_signal_v1')
  assert.deepEqual(presentation.items[0], {
    rank: 1,
    name: 'Reddit',
    symbol: 'RDDT',
    title: 'Reddit (RDDT)',
    scoreText: '63.13',
    upText: '76.7%',
    riskText: '10.6%',
    reason: '상승 후보입니다. 조정 스프레드 0.631입니다.',
  })
})

test('does not render non-ML or empty recommendation results as cards', () => {
  assert.equal(buildMlRecommendationPresentation({ source: 'DISCLOSURE_DB', items: [] }).shouldRender, false)
  assert.equal(buildMlRecommendationPresentation({ source: 'ML_ACTIVE_SIGNAL', items: [] }).shouldRender, false)
})
