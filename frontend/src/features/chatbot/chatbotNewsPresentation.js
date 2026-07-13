const NEWS_SOURCES = new Set(['NEWS_DB', 'NAVER_API', 'FINNHUB_API', 'TAVILY_FALLBACK'])

export function normalizeNewsText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim()
}

function formatNewsDate(value) {
  if (!value) return ''

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

function marketLabel(market) {
  if (market === 'DOMESTIC') return '국내'
  if (market === 'GLOBAL') return '해외'
  if (market === 'WEB') return '웹'
  return '뉴스'
}

function categoryLabel(item) {
  const category = item?.raw_payload?.query_category
  if (!category && item?.symbol) return '종목'
  if (category === 'stock_news') return '주식'
  if (category === 'crypto_news') return '코인'
  if (category === 'macro_news') return '거시'
  if (category === 'tavily_fallback') return '웹검색'
  return '일반'
}

function summaryLines(value) {
  const text = String(value || '').trim()
  if (!text) return []

  return text
    .split(/\n+/)
    .map(normalizeNewsText)
    .filter(Boolean)
    .slice(0, 3)
}

export function buildNewsPresentation(toolResult) {
  if (!NEWS_SOURCES.has(toolResult?.source) || !Array.isArray(toolResult.items)) {
    return { items: [] }
  }

  return {
    items: toolResult.items.map((item) => {
      const summary = item?.ai_summary || item?.summary || ''

      return {
        title: normalizeNewsText(item?.title) || '뉴스 제목 없음',
        url: String(item?.url || ''),
        source: normalizeNewsText(item?.source || toolResult.source.replace(/_API$/, '')),
        market: marketLabel(normalizeNewsText(item?.market)),
        category: categoryLabel(item),
        symbol: normalizeNewsText(item?.symbol),
        companyName: normalizeNewsText(item?.company_name),
        publishedAt: formatNewsDate(item?.published_at || item?.fetched_at),
        summaryLines: summaryLines(summary),
      }
    }),
  }
}
