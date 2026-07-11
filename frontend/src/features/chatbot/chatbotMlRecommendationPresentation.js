const ASSET_TITLES = {
  stock: '주식 ML 추천 후보',
  kr_stock: '국내주식 ML 추천 후보',
  us_stock: '미국주식 ML 추천 후보',
  crypto: '코인 ML 추천 후보',
}

function toNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function formatNumber(value) {
  const number = toNumber(value)
  return number === null ? '-' : number.toFixed(2)
}

function formatPercent(value) {
  const number = toNumber(value)
  return number === null ? '-' : `${(number * 100).toFixed(1)}%`
}

function compactReason(value) {
  const text = String(value || '').replace(/\s+/g, ' ').trim()
  if (!text) return ''
  return text
    .replace(/상승 확률\s*\d+(?:\.\d+)?%,?\s*/g, '')
    .replace(/하락 위험\s*\d+(?:\.\d+)?%,?\s*/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

export function buildMlRecommendationPresentation(toolResult = {}) {
  const source = String(toolResult?.source || '').toUpperCase()
  const items = Array.isArray(toolResult?.items) ? toolResult.items : []
  if (source !== 'ML_ACTIVE_SIGNAL' || items.length === 0) {
    return { shouldRender: false, items: [] }
  }

  const assetKey = String(toolResult.asset_key || '').trim()
  return {
    shouldRender: true,
    title: ASSET_TITLES[assetKey] || 'ML 추천 후보',
    modelVersion: toolResult.model_version || '',
    items: items.map((item, index) => {
      const name = item.display_name || item.name || item.symbol || '-'
      const symbol = item.symbol || '-'
      const title = name && symbol && name !== symbol ? `${name} (${symbol})` : name || symbol
      return {
        rank: index + 1,
        name,
        symbol,
        title,
        scoreText: formatNumber(item.signal_score),
        upText: formatPercent(item.up_probability),
        riskText: formatPercent(item.risk_probability),
        reason: compactReason(item.reason_summary),
      }
    }),
  }
}
