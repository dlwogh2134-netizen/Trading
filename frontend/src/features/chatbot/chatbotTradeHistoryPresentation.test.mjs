import assert from 'node:assert/strict'
import test from 'node:test'

import { buildTradeHistoryPresentation } from './chatbotTradeHistoryPresentation.js'

test('normalizes chatbot trade history items for table rendering', () => {
  const result = buildTradeHistoryPresentation({
    source: 'TRADE_HISTORY',
    items: [
      {
        date: '2026-07-14',
        time: '10:55:51',
        exchange: 'TOSS',
        asset_name: '이노스페이스',
        symbol: '462350',
        side: 'BUY',
        status: 'APPROVED',
        price: 5000,
        quantity: 1,
        amount: 5000,
      },
      {
        date: '2026-07-10',
        exchange: 'COINONE',
        asset_name: '도지코인',
        symbol: 'DOGE',
        side: 'BUY',
        status: 'REJECTED',
        price: 0,
        quantity: 0,
        amount: 0,
      },
    ],
  })

  assert.equal(result.shouldRender, true)
  assert.equal(result.count, 2)
  assert.deepEqual(result.items[0], {
    date: '2026-07-14',
    time: '10:55:51',
    exchange: 'TOSS',
    assetName: '이노스페이스',
    symbol: '462350',
    side: '매수',
    status: '주문 완료',
    priceText: '₩5,000',
    quantityText: '1',
    amountText: '₩5,000',
  })
  assert.equal(result.items[1].status, '구매실패')
  assert.equal(result.items[1].amountText, '₩0')
})

test('ignores unsupported tool result sources', () => {
  const result = buildTradeHistoryPresentation({
    items: [{ date: '2026-07-14' }],
  })

  assert.deepEqual(result, { shouldRender: false, count: 0, items: [] })
})

test('normalizes open orders for table rendering', () => {
  const result = buildTradeHistoryPresentation({
    source: 'OPEN_ORDERS',
    items: [
      {
        date: '2026-07-14',
        exchange: 'TOSS',
        broker_env: 'REAL',
        asset_name: '이노스페이스',
        symbol: '462350',
        side: 'BUY',
        status: 'APPROVED',
        price: 5000,
        quantity: 2,
        amount: 10000,
      },
    ],
  })

  assert.equal(result.shouldRender, true)
  assert.equal(result.title, '미체결 주문')
  assert.deepEqual(result.items[0], {
    date: '2026-07-14',
    time: '-',
    exchange: 'TOSS (REAL)',
    assetName: '이노스페이스',
    symbol: '462350',
    side: '매수',
    status: '주문 완료',
    priceText: '₩5,000',
    quantityText: '2',
    amountText: '₩10,000',
  })
})
