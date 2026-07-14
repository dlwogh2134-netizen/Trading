const SIDE_LABELS = {
  BUY: '매수',
  SELL: '매도',
}

const STATUS_LABELS = {
  PENDING: '미체결',
  APPROVED: '주문 완료',
  ORDERED: '주문 완료',
  OPEN: '미체결',
  REJECTED: '구매실패',
  CANCELED: '취소완료',
  CANCELLED: '취소완료',
  EXECUTED: '체결완료',
  SUBMITTED: '주문 완료',
  FILLED: '체결완료',
  FAILED: '구매실패',
  EXPIRED: '구매실패',
  PARTIALLY_FILLED: '미체결',
  MODIFIED: '미체결',
}

function normalizeTradeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function formatNumber(value, options = {}) {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return '-'
  return numericValue.toLocaleString('ko-KR', options)
}

function formatTradeCurrency(value, currency = 'KRW', unit = 'total') {
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return '-'
  const normalizedCurrency = normalizeTradeText(currency).toUpperCase()
  const prefix = normalizedCurrency === 'USD' ? '$' : '₩'

  return `${prefix}${formatNumber(numericValue, {
    minimumFractionDigits: normalizedCurrency === 'USD' && unit === 'total' ? 2 : 0,
    maximumFractionDigits: normalizedCurrency === 'USD' && unit === 'total' ? 2 : 1,
  })}`
}

function formatTradeQuantity(value) {
  return formatNumber(value, { maximumFractionDigits: 8 })
}

function mapStatus(value, side) {
  const normalized = normalizeTradeText(value).toUpperCase()
  if (['FAILED', 'REJECTED', 'EXPIRED'].includes(normalized)) {
    return normalizeTradeText(side).toUpperCase() === 'SELL' ? '판매실패' : '구매실패'
  }
  return STATUS_LABELS[normalized] || normalized || '-'
}

function mapSide(value) {
  const normalized = normalizeTradeText(value).toUpperCase()
  return SIDE_LABELS[normalized] || normalized || '-'
}

export function buildTradeHistoryPresentation(toolResult) {
  const source = normalizeTradeText(toolResult?.source).toUpperCase()
  const isTradeTableSource = source === 'TRADE_HISTORY' || source === 'OPEN_ORDERS'
  if (!isTradeTableSource || !Array.isArray(toolResult.items)) {
    return { shouldRender: false, count: 0, items: [] }
  }

  const items = toolResult.items.map((item) => {
    const exchange = normalizeTradeText(item?.exchange)
    const brokerEnv = normalizeTradeText(item?.broker_env)

    return {
      date: normalizeTradeText(item?.date) || '-',
      time: normalizeTradeText(item?.time) || '-',
      exchange: exchange ? `${exchange}${brokerEnv ? ` (${brokerEnv})` : ''}` : '-',
      assetName: normalizeTradeText(item?.asset_name || item?.symbol) || '-',
      symbol: normalizeTradeText(item?.symbol) || '-',
      side: mapSide(item?.side),
      status: mapStatus(item?.status, item?.side),
      priceText: formatTradeCurrency(item?.price, item?.currency, 'unit'),
      quantityText: formatTradeQuantity(item?.quantity),
      amountText: formatTradeCurrency(item?.amount, item?.currency, 'total'),
    }
  })

  return {
    shouldRender: items.length > 0,
    title: source === 'OPEN_ORDERS' ? '미체결 주문' : '거래내역',
    count: items.length,
    items,
  }
}
