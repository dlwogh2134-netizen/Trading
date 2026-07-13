import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildNewsPresentation,
  normalizeNewsText,
} from './chatbotNewsPresentation.js'

test('normalizes chatbot news items from supported search sources', () => {
  const result = buildNewsPresentation({
    source: 'NAVER_API',
    items: [
      {
        title: '  삼성전자   반도체 투자 확대 ',
        ai_summary: '1. 삼성전자가 투자 계획을 공개했습니다.\n2. 생산라인 확대가 핵심입니다.\n3. 일정은 원문 확인이 필요합니다.',
        source: 'NAVER',
        market: 'DOMESTIC',
        symbol: '005930',
        company_name: '삼성전자',
        published_at: '2026-07-13T01:00:00Z',
        url: 'https://example.com/news',
        raw_payload: { query_category: 'stock_news' },
      },
    ],
  })

  assert.equal(result.items.length, 1)
  assert.equal(result.items[0].title, '삼성전자 반도체 투자 확대')
  assert.equal(result.items[0].market, '국내')
  assert.equal(result.items[0].category, '주식')
  assert.equal(result.items[0].summaryLines.length, 3)
  assert.equal(result.items[0].url, 'https://example.com/news')
})

test('ignores unsupported tool result sources', () => {
  const result = buildNewsPresentation({
    source: 'DISCLOSURE_DB',
    items: [{ title: '공시' }],
  })

  assert.deepEqual(result, { items: [] })
})

test('normalizes repeated news whitespace', () => {
  assert.equal(normalizeNewsText('삼성전자\n\n  최신\t뉴스'), '삼성전자 최신 뉴스')
})
