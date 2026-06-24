import React, { useEffect, useState } from 'react'
import Header from '../components/Header.jsx'
import Settings from './Settings'
import { fetchNewsArticles } from '../lib/supabaseClient.js'

// 등락률 표시 컴포넌트 (한글 주석 준수)
function Rate({ value }) {
  if (!value) return <span className="text-slate-400">0.00%</span>;
  const isPositive = value.startsWith('+');
  const isNegative = value.startsWith('-');
  return (
    <span className={`font-mono font-semibold ${isPositive ? 'text-emerald-400' : isNegative ? 'text-red-400' : 'text-slate-400'}`}>
      {value}
    </span>
  )
}

// 자산 추이 그래프 Sparkline 컴포넌트
function Sparkline() {
  const assetTrend = [68, 72, 70, 78, 76, 84, 88, 91, 86, 94, 101, 108];
  const points = assetTrend
    .map((val, index) => `${(index / (assetTrend.length - 1)) * 100},${110 - val}`)
    .join(' ');

  return (
    <svg className="h-32 w-full" viewBox="0 0 100 56" preserveAspectRatio="none" role="img" aria-label="총 자산 가치 그래프">
      <defs>
        <linearGradient id="assetFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#00f2fe" stopOpacity="0.2" />
          <stop offset="100%" stopColor="#00f2fe" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={`0,56 ${points} 100,56`} fill="url(#assetFill)" stroke="none" />
      <polyline points={points} fill="none" stroke="#00f2fe" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// 섹션 헤더 컴포넌트
function SectionHeader({ eyebrow, title, action }) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        {eyebrow && <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">{eyebrow}</p>}
        <h2 className="text-sm font-bold text-white uppercase tracking-wider">{title}</h2>
      </div>
      {action && (
        <button className="rounded border border-slate-700 px-2 py-1 text-[10px] font-bold text-slate-400 hover:border-ai-cyan hover:text-white transition-all cursor-pointer" type="button">
          {action}
        </button>
      )}
    </div>
  );
}

// 고정 목업 관심 종목 리스트
const WATCHLIST_MOCK = [
  { id: '005930', name: '삼성전자', market: '국내 주식', account: 'KIS 모의', quantity: '18주', average: '72,400원', change: '+2.14%' },
  { id: '000660', name: 'SK하이닉스', market: '국내 주식', account: 'KIS 모의', quantity: '6주', average: '182,000원', change: '+7.82%' },
  { id: 'NVDA', name: 'NVIDIA', market: '해외 주식', account: '해외 위탁', quantity: '4주', average: '$126.40', change: '+4.31%' },
  { id: 'TSLA', name: 'Tesla', market: '해외 주식', account: '해외 위탁', quantity: '3주', average: '$188.20', change: '-1.26%' }
];

const DASHBOARD_TABS = [
  { key: 'dashboard', label: '대시보드', enabled: true },
  { key: 'watchlist', label: '관심종목', enabled: true },
  { key: 'assets', label: '내 자산', enabled: true },
  { key: 'history', label: '거래 내역', enabled: true },
  { key: 'settings', label: '설정', enabled: true }
]

const WATCH_CHARTS_MOCK = {
  '005930': [44, 47, 45, 51, 49, 55, 58, 62, 60, 66, 64, 71],
  '000660': [38, 42, 46, 44, 53, 57, 63, 66, 70, 74, 78, 83],
  NVDA: [52, 54, 51, 59, 62, 61, 66, 69, 73, 70, 76, 79],
  TSLA: [70, 68, 66, 69, 64, 62, 60, 58, 61, 57, 55, 54]
}

const ASSET_ACCOUNTS_MOCK = [
  { id: 'krw-stock', title: '주식계좌', accountType: '원화', maskedAccountNumber: '123-45-****01', balanceLabel: '원화 잔고', balance: '1,186,900원' },
  { id: 'usd-stock', title: '해외주식계좌', accountType: '달러', maskedAccountNumber: '987-65-****09', balanceLabel: '달러 잔고', balance: '$842.16' },
  { id: 'coin-wallet', title: '코인계좌', accountType: '코인', maskedAccountNumber: 'UPBIT-****-001', balanceLabel: '코인 평가금', balance: '489,500원' }
]

const FALLBACK_HOLDINGS = [
  { id: 'holding-005930', name: '삼성전자', account: '국내 주식', quantity: '18주', average: '72,400원', returnRate: '+2.14%', weight: 26 },
  { id: 'holding-000660', name: 'SK하이닉스', account: '국내 주식', quantity: '6주', average: '182,000원', returnRate: '+7.82%', weight: 24 },
  { id: 'holding-NVDA', name: 'NVIDIA', account: '해외 주식', quantity: '4주', average: '$126.40', returnRate: '+4.31%', weight: 14 },
  { id: 'holding-TSLA', name: 'Tesla', account: '해외 주식', quantity: '3주', average: '$188.20', returnRate: '-1.26%', weight: 12 },
  { id: 'holding-BTC', name: 'Bitcoin', account: '코인', quantity: '0.0038 BTC', average: '128,600,000원', returnRate: '+3.18%', weight: 9 }
]

const TRADE_HISTORY_MOCK = [
  { id: 'trade-1', date: '2026-06-23', time: '14:18:35', exchange: 'TOSS', symbolName: '삼성전자', ticker: '005930', side: '매수', currency: 'KRW', price: '68,500', quantity: '100', amount: '₩6,850,000', status: '체결완료', exchangeRate: '-', fees: '1,370원', orderNumber: 'TOSS-260623-001' },
  { id: 'trade-2', date: '2026-06-23', time: '11:02:10', exchange: 'KIS', symbolName: 'NVIDIA Corp', ticker: 'NVDA', side: '매도', currency: 'USD', price: '$425.10', quantity: '50', amount: '$21,255.00', status: '체결완료', exchangeRate: '1,385.50 KRW', fees: '185원', orderNumber: 'KIS-260623-118' },
  { id: 'trade-3', date: '2026-06-22', time: '15:21:44', exchange: 'COINONE', symbolName: 'Bitcoin', ticker: 'BTC/KRW', side: '매수', currency: 'KRW', price: '45,200,000', quantity: '0.5', amount: '₩22,600,000', status: '체결완료', exchangeRate: '-', fees: '11,300원', orderNumber: 'COIN-260622-039' },
  { id: 'trade-4', date: '2026-06-22', time: '08:45:00', exchange: 'BINANCE', symbolName: 'Ethereum', ticker: 'ETH/USDT', side: '매도', currency: 'USD', price: '$1,780.50', quantity: '10.0', amount: '$17,805.00', status: '미체결', exchangeRate: '1,385.50 KRW', fees: '$8.90', orderNumber: 'BN-260622-204' },
  { id: 'trade-5', date: '2026-06-21', time: '09:41:08', exchange: 'TOSS', symbolName: 'SK하이닉스', ticker: '000660', side: '매수', currency: 'KRW', price: '124,000', quantity: '200', amount: '₩24,800,000', status: '체결완료', exchangeRate: '-', fees: '4,960원', orderNumber: 'TOSS-260621-091' }
]

// 사이드 바 관리
function SidebarNav({ activeTab, isOpen, onClose, onOpen, onTabChange }) {
  if (!isOpen) {
    return (
      <button
        className="fixed left-4 top-4 z-40 grid h-11 w-11 place-items-center rounded-lg border border-slate-700 bg-[#0F172A] text-lg font-black text-white shadow-xl transition hover:border-ai-cyan hover:text-ai-cyan"
        type="button"
        aria-label="사이드바 열기"
        onClick={onOpen}
      >
        ☰
      </button>
    )
  }

  return (
    <aside className="shrink-0 border-b border-slate-800 bg-[#0F172A] lg:min-h-screen lg:w-64 lg:border-b-0 lg:border-r">
      <div className="sticky top-0 flex gap-3 overflow-x-auto p-4 lg:h-screen lg:flex-col lg:overflow-visible lg:p-5">
        <div className="flex items-center gap-3 lg:pb-5">
          <span className="grid h-10 w-10 place-items-center overflow-hidden rounded-lg">
            <img className="h-full w-full object-contain" src="/logo.png" alt="Trading AI" />
          </span>
          <div className="min-w-28">
            <p className="text-sm font-extrabold text-white">AE STOCK</p>
            <p className="text-xs text-slate-500">Dashboard</p>
          </div>
          <button
            className="ml-auto grid h-8 w-8 place-items-center rounded-lg border border-slate-700 text-lg font-black text-slate-400 transition hover:border-ai-cyan hover:text-white"
            type="button"
            aria-label="사이드바 닫기"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        {DASHBOARD_TABS.map((tab) => (
          <button
            key={tab.key}
            className={`shrink-0 rounded-lg px-4 py-3 text-left text-sm font-bold transition ${activeTab === tab.key
                ? 'bg-institutional-blue text-white shadow-[0_10px_24px_rgba(0,71,187,0.25)]'
                : tab.enabled
                  ? 'text-slate-400 hover:bg-white/5 hover:text-white'
                  : 'cursor-default text-slate-600'
              }`}
            type="button"
            onClick={() => {
              if (tab.enabled) onTabChange(tab.key)
            }}
          >
            {tab.label}
          </button>
        ))}

        <div className="mt-auto hidden rounded-lg border border-ai-cyan/20 bg-white/[0.04] p-4 lg:block">
          <p className="text-xs font-bold text-ai-cyan">AI Layer</p>
          <p className="mt-2 text-sm leading-6 text-slate-300">매매 제안은 사용자 승인 전까지 실행되지 않습니다.</p>
        </div>
      </div>
    </aside>
  )
}


function MiniSparkline({ values = [], height = 'h-52' }) {
  const points = values
    .map((val, index) => `${(index / Math.max(values.length - 1, 1)) * 100},${110 - val}`)
    .join(' ')

  if (!values.length) {
    return <div className={`${height} grid place-items-center text-xs text-slate-500`}>차트 데이터가 없습니다.</div>
  }

  return (
    <svg className={`${height} w-full`} viewBox="0 0 100 56" preserveAspectRatio="none" role="img" aria-label="관심종목 가격 흐름">
      <defs>
        <linearGradient id="watchFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#00e0ff" stopOpacity="0.24" />
          <stop offset="100%" stopColor="#00e0ff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline points={`0,56 ${points} 100,56`} fill="url(#watchFill)" stroke="none" />
      <polyline points={points} fill="none" stroke="#00e0ff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function formatNewsDate(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function getWatchlistNewsMarket(item) {
  return /[a-zA-Z]/.test(item?.id || '') ? 'GLOBAL' : 'DOMESTIC'
}

function mergeLatestNews(items) {
  const seen = new Set()
  return items
    .filter((item) => {
      const key = item.id || item.url || item.source_article_id || item.title
      if (!key || seen.has(key)) return false
      seen.add(key)
      return true
    })
    .sort((a, b) => new Date(b.published_at || 0) - new Date(a.published_at || 0))
    .slice(0, 4)
}

function WatchlistTab() {
  const [selectedId, setSelectedId] = useState(WATCHLIST_MOCK[0]?.id || '')
  const [newsItems, setNewsItems] = useState([])
  const [newsLoading, setNewsLoading] = useState(false)
  const [newsError, setNewsError] = useState('')
  const selectedItem = WATCHLIST_MOCK.find((item) => item.id === selectedId) || WATCHLIST_MOCK[0]
  const useSlider = WATCHLIST_MOCK.length >= 5

  useEffect(() => {
    if (!selectedItem) return

    let isMounted = true
    const queries = [selectedItem.id, selectedItem.name].filter(Boolean)
    const uniqueQueries = [...new Set(queries)]

    async function loadWatchlistNews() {
      setNewsLoading(true)
      setNewsError('')

      try {
        const results = await Promise.all(
          uniqueQueries.map((query) =>
            fetchNewsArticles({
              market: getWatchlistNewsMarket(selectedItem),
              query,
              limit: 4,
              offset: 0,
            }),
          ),
        )

        if (!isMounted) return
        setNewsItems(mergeLatestNews(results.flatMap((result) => result.items || [])))
      } catch (error) {
        if (!isMounted) return
        setNewsItems([])
        setNewsError(error.message || '뉴스를 불러오지 못했습니다.')
      } finally {
        if (isMounted) setNewsLoading(false)
      }
    }

    loadWatchlistNews()

    return () => {
      isMounted = false
    }
  }, [selectedItem])

  return (
    <main className="max-w-7xl mx-auto flex flex-col gap-6">
      <section className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
        <SectionHeader title="관심종목 명단" />
        <div className={useSlider ? 'flex snap-x gap-2 overflow-x-auto pb-2' : 'grid gap-2 md:grid-cols-2 xl:grid-cols-4'}>
          {WATCHLIST_MOCK.map((item) => (
            <button
              key={item.id}
              className={`${useSlider ? 'min-w-60 snap-start' : 'w-full'} rounded-lg px-4 py-3 text-left transition ${selectedItem?.id === item.id ? 'bg-institutional-blue text-white' : 'bg-[#0f172a] text-slate-300 hover:bg-white/5'
                }`}
              type="button"
              onClick={() => setSelectedId(item.id)}
            >
              <span className="block font-bold">{item.name}</span>
              <span className="mt-1 block text-xs opacity-70 font-mono">{item.market} · {item.account}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
        <SectionHeader title="관심 종목의 차트" action={selectedItem?.id} />
        <div className="rounded-lg border border-slate-800 bg-[#0f172a]/70 p-4">
          <MiniSparkline values={WATCH_CHARTS_MOCK[selectedItem?.id]} />
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-5">
          {[
            ['종목명', selectedItem?.name],
            ['계좌종류', selectedItem?.account],
            ['수량', selectedItem?.quantity],
            ['평균 단가', selectedItem?.average],
            ['등락율', selectedItem?.change],
          ].map(([label, value]) => (
            <div key={label} className="rounded-lg bg-[#0f172a] p-4">
              <p className="text-xs font-bold text-slate-500">{label}</p>
              <p className="mt-2 font-bold text-white font-mono">{label === '등락율' ? <Rate value={value} /> : value}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
        <SectionHeader title="관심종목 관련 최근 뉴스피드" />
        <div className="grid gap-3 lg:grid-cols-2">
          {newsLoading && newsItems.length === 0 ? (
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400 lg:col-span-2">
              최신 뉴스피드를 불러오는 중입니다...
            </div>
          ) : null}

          {newsError ? (
            <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm text-red-300 lg:col-span-2">
              {newsError}
            </div>
          ) : null}

          {!newsLoading && newsItems.length === 0 && !newsError ? (
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400 lg:col-span-2">
              선택한 관심종목과 연결된 최신 뉴스가 없습니다.
            </div>
          ) : null}

          {newsItems.map((news, index) => (
            <article key={news.id || news.url || `${news.title}-${index}`} className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
              <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
                <span className="font-bold text-ai-cyan">{news.source}</span>
                <span className="font-mono">{formatNewsDate(news.published_at)}</span>
              </div>
              <h3 className="mt-3 text-sm font-bold leading-6 text-white">{news.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{news.summary}</p>
              <a className="mt-4 inline-flex rounded-lg bg-ai-cyan px-4 py-2 text-sm font-bold text-[#07111f] transition hover:bg-ai-cyan/80" href={news.url || '#'} rel="noreferrer" target="_blank">
                원문 열기
              </a>
            </article>
          ))}
        </div>
      </section>
    </main>
  )
}

function AssetsTab({ balance, allocation }) {
  const displayAccounts = ASSET_ACCOUNTS_MOCK.map((account) => {
    if (account.id !== 'krw-stock' || !balance) return account

    return {
      ...account,
      balance: `₩${(balance.available_cash || 0).toLocaleString()}`,
    }
  })
  const holdings = balance?.holdings?.length
    ? balance.holdings.map((stock) => ({
      id: stock.symbol,
      name: stock.name,
      account: /[a-zA-Z]/.test(stock.symbol) ? '해외 주식' : '국내 주식',
      quantity: `${stock.qty}`,
      average: `₩${stock.avg_price.toLocaleString()}`,
      returnRate: `${stock.profit_rate >= 0 ? '+' : ''}${stock.profit_rate.toFixed(2)}%`,
    }))
    : FALLBACK_HOLDINGS

  return (
    <main className="max-w-7xl mx-auto flex flex-col gap-6">
      <section className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
        <SectionHeader eyebrow="Private Asset" title="주식계좌 및 계좌번호" />
        <div className="grid gap-3">
          {displayAccounts.map((account) => (
            <div key={account.id} className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-bold text-white">{account.title}</p>
                    <span className="rounded-md bg-ai-cyan/10 px-2 py-1 text-xs font-bold text-ai-cyan">{account.accountType}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-400 font-mono">계좌번호 {account.maskedAccountNumber}</p>
                </div>
                <div className="md:text-right">
                  <p className="text-xs font-bold text-slate-500">{account.balanceLabel}</p>
                  <p className="mt-1 text-xl font-extrabold text-white font-mono">{account.balance}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
        <SectionHeader title="보유자산 현황 및 자산 배분 상태" />
        <div className="flex h-4 overflow-hidden rounded-full bg-[#0f172a]">
          {allocation.map((item) => (
            <span key={item.id} className={item.color} style={{ width: `${item.value}%` }} />
          ))}
        </div>
        <div className="mt-5 grid gap-3">
          {allocation.map((item) => (
            <div key={item.id} className="rounded-lg bg-[#0f172a] p-4">
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-sm font-bold text-white">
                  <span className={`h-2 w-2 rounded-full ${item.color}`} />
                  {item.label}
                </span>
                <span className="font-mono font-bold text-slate-300">{item.value}%</span>
              </div>
              <div className="mt-3 h-2 rounded-full bg-white/5">
                <div className={`h-2 rounded-full ${item.color}`} style={{ width: `${item.value}%` }} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-slate-surface border border-slate-700/80 rounded-lg overflow-hidden">
        <div className="p-5 pb-2">
          <SectionHeader title="투자종목 보유 현황" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] border-collapse text-sm">
            <thead className="border-y border-slate-800 bg-[#0f172a] text-xs text-slate-400">
              <tr>
                {['투자종목 명', '계좌 종류', '수량', '평균단가', '수익률'].map((head) => (
                  <th key={head} className="px-5 py-3 text-left font-bold">{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {holdings.map((item) => (
                <tr key={item.id} className="border-b border-slate-800/80 last:border-b-0">
                  <td className="px-5 py-4 font-bold text-white">{item.name}</td>
                  <td className="px-5 py-4 text-slate-300">{item.account}</td>
                  <td className="px-5 py-4 font-mono">{item.quantity}</td>
                  <td className="px-5 py-4 font-mono">{item.average}</td>
                  <td className="px-5 py-4"><Rate value={item.returnRate} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}

function TradeHistoryTab() {
  const tradeHistory = TRADE_HISTORY_MOCK
  const [selectedTrade, setSelectedTrade] = useState(null)
  const [selectedExchange, setSelectedExchange] = useState('ALL')
  const [dateRange, setDateRange] = useState({
    start: '2026-06-21',
    end: '2026-06-23',
  })
  const exchangeTone = {
    TOSS: 'border-blue-500/40 bg-blue-500/15 text-blue-300',
    KIS: 'border-rose-500/40 bg-rose-500/15 text-rose-300',
    COINONE: 'border-sky-500/40 bg-sky-500/15 text-sky-300',
    BINANCE: 'border-yellow-400/40 bg-yellow-400/15 text-yellow-300',
  }
  const filteredTrades = tradeHistory.filter((trade) => {
    const exchangeMatched = selectedExchange === 'ALL' || trade.exchange === selectedExchange
    const startMatched = !dateRange.start || trade.date >= dateRange.start
    const endMatched = !dateRange.end || trade.date <= dateRange.end

    return exchangeMatched && startMatched && endMatched
  })

  return (
    <main className="relative max-w-7xl mx-auto flex flex-col gap-3">
      <section className="rounded-lg border border-slate-700 bg-slate-surface/90 p-2">
        <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex flex-1 flex-col gap-2 md:flex-row md:items-center">
            <label className="flex h-10 min-w-52 items-center gap-2 rounded border border-slate-700 bg-[#0f172a] px-3 text-sm text-slate-500">
              <span>⌕</span>
              <input className="w-full bg-transparent text-slate-200 outline-none placeholder:text-slate-500" placeholder="Search Ticker..." type="text" />
            </label>
            <div className="flex h-10 items-center gap-2 rounded border border-slate-700 bg-[#0f172a] px-3 text-sm font-bold text-slate-300">
              <input
                className="w-32 bg-transparent font-mono text-xs text-slate-200 outline-none [color-scheme:dark]"
                type="date"
                value={dateRange.start}
                onChange={(event) => setDateRange((prev) => ({ ...prev, start: event.target.value }))}
              />
              <span className="text-slate-600">-</span>
              <input
                className="w-32 bg-transparent font-mono text-xs text-slate-200 outline-none [color-scheme:dark]"
                type="date"
                value={dateRange.end}
                onChange={(event) => setDateRange((prev) => ({ ...prev, end: event.target.value }))}
              />
            </div>
            <div className="flex flex-wrap items-center gap-2 text-sm text-slate-400">
              <span>Exchange:</span>
              {['ALL', 'TOSS', 'KIS', 'COINONE', 'BINANCE'].map((item) => (
                <button
                  key={item}
                  className={`rounded px-3 py-2 text-xs font-bold transition ${selectedExchange === item
                      ? 'bg-ai-cyan text-[#07111f]'
                      : 'bg-slate-700/70 text-slate-200 hover:bg-slate-600'
                    }`}
                  type="button"
                  onClick={() => setSelectedExchange(item)}
                >
                  {item}
                </button>
              ))}
            </div>
          </div>
          <button className="h-10 rounded border border-slate-700 bg-[#0f172a] px-4 text-sm font-bold text-slate-200 hover:border-ai-cyan" type="button">
            More Filters
          </button>
        </div>
      </section>

      <section className="bg-slate-surface border border-slate-700/80 rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1040px] border-collapse text-sm">
            <thead className="border-b border-slate-700 bg-slate-800/70 text-xs text-slate-300">
              <tr>
                {['일시 (Date)', '거래소 (Exchange)', '종목명 (Asset/Ticker)', '구분 (Side)', '체결가 (Price)', '수량 (Qty)', '정산금액 (Total)', '상태 (Status)'].map((head) => (
                  <th key={head} className="px-4 py-3 text-left font-bold">{head}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredTrades.map((trade) => (
                <tr
                  key={trade.id}
                  className="cursor-pointer border-b border-slate-700/70 last:border-b-0 hover:bg-white/[0.04]"
                  onClick={() => setSelectedTrade(trade)}
                >
                  <td className="px-4 py-4 font-mono text-xs text-slate-300">{trade.date.replaceAll('-', '.')} {trade.time}</td>
                  <td className="px-4 py-4">
                    <span className={`rounded border px-2 py-1 text-xs font-black ${exchangeTone[trade.exchange] || 'border-slate-600 bg-slate-700 text-slate-200'}`}>
                      {trade.exchange}
                    </span>
                  </td>
                  <td className="px-4 py-4">
                    <p className="font-bold text-white">{trade.symbolName}</p>
                    <p className="mt-1 text-xs text-slate-500 font-mono">{trade.ticker}</p>
                  </td>
                  <td className="px-4 py-4">
                    <span className={`font-bold ${trade.side === '매수'
                        ? 'text-emerald-300'
                        : 'text-rose-300'
                      }`}>
                      {trade.side} {trade.side === '매수' ? '(Buy)' : '(Sell)'}
                    </span>
                  </td>
                  <td className="px-4 py-4 font-mono font-bold text-slate-100">{trade.price}</td>
                  <td className="px-4 py-4 font-mono font-bold text-slate-100">{trade.quantity}</td>
                  <td className="px-4 py-4 font-mono font-bold text-slate-100">{trade.amount}</td>
                  <td className="px-4 py-4">
                    <span className={`rounded-full px-3 py-1 text-xs font-bold ${trade.status === '체결완료'
                        ? 'bg-slate-600/60 text-slate-200'
                        : 'border border-slate-600 bg-slate-700/30 text-slate-200'
                      }`}>
                      {trade.status}{trade.status === '미체결' ? ' (Pending)' : ''}
                    </span>
                  </td>
                </tr>
              ))}
              {filteredTrades.length === 0 && (
                <tr>
                  <td className="px-4 py-12 text-center text-sm text-slate-500" colSpan={8}>
                    선택한 조건에 맞는 거래 내역이 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {selectedTrade && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <button className="flex-1 bg-black/55 backdrop-blur-[1px]" type="button" aria-label="거래 상세 닫기" onClick={() => setSelectedTrade(null)} />
          <aside className="h-full w-full max-w-md border-l border-slate-700 bg-[#0f172a] shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-700 px-6 py-6">
              <h2 className="text-lg font-extrabold text-white">거래 상세 내역</h2>
              <button className="grid h-8 w-8 place-items-center rounded text-2xl text-slate-300 hover:bg-white/5 hover:text-white" type="button" aria-label="닫기" onClick={() => setSelectedTrade(null)}>
                ×
              </button>
            </div>

            <div className="space-y-6 p-6">
              <div className="rounded-lg border border-slate-700 bg-slate-800/70 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-4">
                    <div className="grid h-11 w-11 place-items-center rounded-lg border border-slate-600 bg-[#0f172a] text-lg font-bold text-ai-cyan">
                      {selectedTrade.symbolName.slice(0, 1)}
                    </div>
                    <div>
                      <p className="text-lg font-extrabold text-white">{selectedTrade.symbolName}</p>
                      <p className="mt-1 text-xs font-mono text-slate-400">{selectedTrade.ticker}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-white">지정가 {selectedTrade.side}</p>
                    <span className={`mt-2 inline-flex rounded-full px-3 py-1 text-xs font-bold ${selectedTrade.status === '체결완료' ? 'bg-emerald-400/15 text-emerald-300' : 'bg-slate-700 text-slate-200'
                      }`}>
                      {selectedTrade.status}
                    </span>
                  </div>
                </div>
              </div>

              <dl className="space-y-4 border-t border-slate-700 pt-5 text-sm">
                {[
                  ['체결 단가 (Execution Price)', selectedTrade.price],
                  ['수량 (Quantity)', selectedTrade.quantity],
                  ['주문 금액 (Total Amount)', selectedTrade.amount],
                  ['적용 환율 (Exchange Rate)', selectedTrade.exchangeRate],
                  ['수수료 (Fees)', selectedTrade.fees],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between gap-4">
                    <dt className="font-bold text-slate-400">{label}</dt>
                    <dd className="font-mono font-bold text-slate-100">{value}</dd>
                  </div>
                ))}
              </dl>

              <div className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800/70 px-4 py-3">
                <span className="font-extrabold text-white">총 정산 금액</span>
                <span className="font-mono text-2xl font-extrabold text-emerald-300">{selectedTrade.amount}</span>
              </div>

              <dl className="space-y-2 border-t border-slate-800 pt-4 text-xs text-slate-500">
                <div className="flex items-center justify-between">
                  <dt>주문 일시</dt>
                  <dd className="font-mono">{selectedTrade.date} {selectedTrade.time}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt>주문 번호</dt>
                  <dd className="font-mono">{selectedTrade.orderNumber}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt>거래소</dt>
                  <dd className="font-mono">{selectedTrade.exchange}</dd>
                </div>
              </dl>
            </div>
          </aside>
        </div>
      )}
    </main>
  )
}

export default function Dashboard({ isLoggedIn, userEmail, handleLogout, userProfile }) {
  const [inputs, setInputs] = useState({
    appkey: '',
    appsecret: '',
    cano: '',
    env: 'MOCK'
  })
  const [activeTab, setActiveTab] = useState('dashboard')
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)

  const [encrypted, setEncrypted] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState({ text: '', isError: false })
  const [balance, setBalance] = useState(null)

  const handleInputChange = (e) => {
    const { name, value } = e.target
    setInputs(prev => ({ ...prev, [name]: value }))
  }

  const handleTestKeys = async (e) => {
    e.preventDefault()
    if (!inputs.appkey || !inputs.appsecret || !inputs.cano) {
      setMessage({ text: 'Please fill in all API Key fields.', isError: true })
      return
    }

    setLoading(true)
    setMessage({ text: '', isError: false })

    try {
      const response = await fetch('http://localhost:5050/api/keys/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputs)
      })

      const resData = await response.json()

      if (resData.success) {
        setMessage({ text: resData.message, isError: false })
        setEncrypted(resData.data.encrypted)
        setBalance(resData.data.balance)
      } else {
        setMessage({ text: resData.message || 'Key validation failed.', isError: true })
      }
    } catch (error) {
      setMessage({ text: `Failed to connect to backend server: ${error.message}`, isError: true })
    } finally {
      setLoading(false)
    }
  }

  const refreshBalance = async () => {
    if (!encrypted) return
    setLoading(true)
    try {
      const response = await fetch('http://localhost:5050/api/dashboard/balance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...encrypted,
          env: inputs.env
        })
      })
      const resData = await response.json()
      if (resData.success) {
        setBalance(resData.data)
      } else {
        setMessage({ text: resData.message || 'Failed to refresh balance.', isError: true })
      }
    } catch (error) {
      setMessage({ text: `Refresh error: ${error.message}`, isError: true })
    } finally {
      setLoading(false)
    }
  }

  // 자산 배분 비중 동적 계산 헬퍼 함수
  const getAllocationData = () => {
    if (!balance || !balance.holdings || balance.holdings.length === 0) {
      return [
        { id: 'domestic', label: '국내 주식', value: 0, color: 'bg-institutional-blue' },
        { id: 'overseas', label: '해외 주식', value: 0, color: 'bg-ai-cyan' },
        { id: 'cash', label: '현금', value: 100, color: 'bg-slate-500' }
      ]
    }

    const totalEval = balance.total_evaluation || 0
    if (totalEval === 0) {
      return [
        { id: 'domestic', label: '국내 주식', value: 0, color: 'bg-institutional-blue' },
        { id: 'overseas', label: '해외 주식', value: 0, color: 'bg-ai-cyan' },
        { id: 'cash', label: '현금', value: 100, color: 'bg-slate-500' }
      ]
    }

    let domesticValue = 0
    let overseasValue = 0

    balance.holdings.forEach(stock => {
      // 심볼에 영문 알파벳이 있으면 해외 주식으로 대략적 분류
      const isOverseas = /[a-zA-Z]/.test(stock.symbol)
      const stockEval = stock.current_price * stock.qty
      if (isOverseas) {
        overseasValue += stockEval
      } else {
        domesticValue += stockEval
      }
    })

    const domesticPercent = Math.round((domesticValue / totalEval) * 100)
    const overseasPercent = Math.round((overseasValue / totalEval) * 100)
    const cashPercent = 100 - domesticPercent - overseasPercent

    return [
      { id: 'domestic', label: '국내 주식', value: domesticPercent, color: 'bg-blue-600' },
      { id: 'overseas', label: '해외 주식', value: overseasPercent, color: 'bg-ai-cyan' },
      { id: 'cash', label: '현금', value: Math.max(0, cashPercent), color: 'bg-slate-500' }
    ]
  }

  const allocation = getAllocationData()

  // 투자 성향 가이드 텍스트 매퍼
  const getProfileDescription = (profile) => {
    switch (profile) {
      case '안정형': return '원금 보존이 최우선이며 안전 자산 위주로 포트폴리오를 구성합니다.'
      case '안정추구형': return '원금 손실을 최소화하면서 예적금보다 약간 높은 수익을 기대합니다.'
      case '위험중립형': return '안정성과 수익성을 균형 있게 추구하며 적절한 위험을 감수합니다.'
      case '적극투자형': return '높은 수익을 위해 상당한 위험을 감수하며 투자 자산 비중이 높습니다.'
      case '공격투자형': return '매우 높은 수익을 기대하며 자산 손실 위험을 적극적으로 감수합니다.'
      default: return '설문 조사를 통해 본인의 상세 투자 성향을 측정할 수 있습니다.'
    }
  }

  return (
    <div className="min-h-screen bg-obsidian-bg text-[#e2e2ec] font-inter">
      <div className="flex min-h-screen flex-col lg:flex-row">
        <SidebarNav
          activeTab={activeTab}
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          onOpen={() => setIsSidebarOpen(true)}
          onTabChange={setActiveTab}
        />

        <div className={`min-w-0 flex-1 px-6 py-8 ${!isSidebarOpen ? 'pt-20 lg:pt-8' : ''}`}>
          {/* 공통 통합 헤더 네비게이션 */}
          <Header isLoggedIn={isLoggedIn} userEmail={userEmail} handleLogout={handleLogout} userProfile={userProfile} />

          {/* 메인 레이아웃 2단 그리드 */}
          {activeTab === 'dashboard' && (
            <main className="max-w-7xl mx-auto flex flex-col gap-6">

              {/* 자산 요약 카드 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
                  <span className="text-xs font-bold text-slate-400">총 평가 자산 (KRW)</span>
                  <div className="text-xl font-bold font-mono text-white mt-1">
                    {balance ? `₩${balance.total_evaluation.toLocaleString()}` : '₩0'}
                  </div>
                </div>

                <div className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
                  <span className="text-xs font-bold text-slate-400">가용 예수금 (Cash)</span>
                  <div className="text-xl font-bold font-mono text-white mt-1">
                    {balance ? `₩${balance.available_cash.toLocaleString()}` : '₩0'}
                  </div>
                </div>

                <div className="bg-slate-surface border border-slate-700/80 rounded-lg p-5">
                  <span className="text-xs font-bold text-slate-400">포트폴리오 수익률</span>
                  <div className="mt-1">
                    <Rate value={balance && balance.holdings.length > 0 ? '+1.45%' : '0.00%'} />
                  </div>
                </div>
              </div>

              <section className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
                {/* 총 자산 가치 그래프 (Sparkline) */}
                <div className="bg-slate-surface border border-slate-700/80 rounded-lg p-5 flex flex-col gap-3">
                  <SectionHeader eyebrow="Portfolio Trend" title="자산 가치 변화 추이 (예시)" action="기간 변경" />
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
                    <div>
                      <p className="text-2xl font-bold text-white font-mono">{balance ? `₩${balance.total_evaluation.toLocaleString()}` : '₩5,109,700'}</p>
                      <p className="text-[11px] text-slate-400 mt-1">지난 30일 기준 <span className="text-emerald-400 font-bold font-mono">+₩235,400</span></p>
                    </div>
                    <div className="flex gap-1.5 text-[10px] font-bold text-slate-400">
                      {["1주", "1개월", "3개월", "1년"].map((item, index) => (
                        <button key={item} className={`rounded px-2.5 py-1 cursor-pointer transition-all ${index === 1 ? "bg-ai-cyan/10 text-ai-cyan border border-ai-cyan/30" : "bg-[#0f172a] hover:bg-slate-800"}`} type="button">
                          {item}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="mt-2 rounded border border-slate-800 bg-[#0f172a]/60 p-4">
                    <Sparkline />
                  </div>
                </div>

                {/* AI Profile (유저 실제 투자 성향 연동) */}
                <div className="ai-glass rounded-lg p-6 flex flex-col gap-4">
                  <SectionHeader eyebrow="AI Profile" title="나의 투자 성향 분석" />
                  {isLoggedIn && userProfile ? (
                    <div className="rounded-lg border border-ai-cyan/20 bg-[#0c0e15]/60 p-4">
                      <p className="text-base font-extrabold text-white">
                        당신은 <span className="text-ai-cyan">{userProfile.invest_type || '미정'}</span> 성향입니다.
                      </p>
                      <div className="mt-2 text-xs text-slate-400 flex justify-between">
                        <span>진단 점수:</span>
                        <span className="font-bold text-white">{userProfile.invest_score || 0} / 50점</span>
                      </div>
                      <p className="mt-3 text-xs leading-5 text-slate-300 border-t border-slate-800/80 pt-3">
                        {getProfileDescription(userProfile.invest_type)}
                      </p>
                    </div>
                  ) : (
                    <div className="grid min-h-40 place-items-center rounded border border-slate-800 bg-[#0c0e15]/40 p-5 text-center text-xs text-slate-400">
                      로그인 후 투자 성향 진단을 완료하시면 성향 맞춤형 포트폴리오 관리가 제공됩니다.
                    </div>
                  )}
                </div>
              </section>

              {/* 자산 배분 상태 및 관심 종목 그리드 */}
              <div className="grid grid-cols-1 md:grid-cols-12 gap-6">

                {/* 자산 배분 상태 (Allocation) */}
                <div className="bg-slate-surface border border-slate-700/80 rounded-lg p-5 md:col-span-5 flex flex-col gap-4">
                  <SectionHeader title="자산 배분 상태" />
                  <div className="flex h-3.5 overflow-hidden rounded-full bg-[#0c0e15] border border-slate-800">
                    {allocation.map((item) => (
                      <span key={item.id} className={`${item.color} h-full transition-all`} style={{ width: `${item.value}%` }} />
                    ))}
                  </div>
                  <div className="flex flex-col gap-2">
                    {allocation.map((item) => (
                      <div key={item.id} className="flex items-center justify-between rounded bg-[#0c0e15]/40 px-3 py-2 border border-slate-800/40 text-xs">
                        <span className="flex items-center gap-2 font-bold">
                          <span className={`w-2 h-2 rounded-full ${item.color}`} />
                          {item.label}
                        </span>
                        <span className="font-mono font-bold text-slate-300">{item.value}%</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 관심 종목 명단 */}
                <div className="bg-slate-surface border border-slate-700/80 rounded-lg p-5 md:col-span-7 flex flex-col gap-3">
                  <SectionHeader title="관심 종목 명단 (시세 모니터링)" action="관리" />
                  <div className="overflow-x-auto max-h-[180px] overflow-y-auto">
                    <table className="w-full border-collapse text-xs">
                      <thead className="border-b border-slate-800 text-slate-400 bg-[#0c0e15]/50 sticky top-0">
                        <tr>
                          <th className="px-3 py-2 text-left font-bold">종목명</th>
                          <th className="px-3 py-2 text-left font-bold">시장</th>
                          <th className="px-3 py-2 text-right font-bold">평균가</th>
                          <th className="px-3 py-2 text-right font-bold">등락률</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/40">
                        {WATCHLIST_MOCK.map((item) => (
                          <tr key={item.id} className="hover:bg-slate-800/20 transition-colors">
                            <td className="px-3 py-2.5 font-bold text-white">{item.name}</td>
                            <td className="px-3 py-2.5 text-slate-400">{item.market}</td>
                            <td className="px-3 py-2.5 text-right font-mono text-slate-300">{item.average}</td>
                            <td className="px-3 py-2.5 text-right"><Rate value={item.change} /></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

              </div>

              {/* 보유 재산 현황 (실제 holdings 연동 테이블) */}
              <div className="bg-slate-surface border border-slate-700/80 rounded-lg p-6 flex flex-col gap-4">
                <div className="flex justify-between items-center border-b border-slate-800 pb-2">
                  <h2 className="text-sm font-bold text-white flex items-center gap-2 uppercase tracking-wider">
                    <span className="w-2 h-2 rounded bg-indigo-500" />
                    Held Positions (보유 주식 자산 현황)
                  </h2>
                  {encrypted && (
                    <button
                      onClick={refreshBalance}
                      disabled={loading}
                      className="text-xs border border-slate-700 hover:border-slate-500 rounded px-2.5 py-1 text-slate-300 font-medium transition-all cursor-pointer disabled:opacity-50"
                    >
                      {loading ? 'LOADING...' : 'REFRESH'}
                    </button>
                  )}
                </div>

                {balance && balance.holdings.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-slate-400 bg-[#0c0e15]/30">
                          <th className="py-2 px-3 font-bold">종목명/코드</th>
                          <th className="py-2 px-3 text-right font-bold">보유수량</th>
                          <th className="py-2 px-3 text-right font-bold">평균단가</th>
                          <th className="py-2 px-3 text-right font-bold">현재가</th>
                          <th className="py-2 px-3 text-right font-bold">평가손익</th>
                          <th className="py-2 px-3 text-right font-bold">수익률</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono">
                        {balance.holdings.map((stock) => (
                          <tr key={stock.symbol} className="hover:bg-slate-800/40 transition-colors">
                            <td className="py-3 px-3 font-sans">
                              <div className="font-semibold text-white">{stock.name}</div>
                              <div className="text-[10px] text-slate-500 font-mono">{stock.symbol}</div>
                            </td>
                            <td className="py-3 px-3 text-right text-slate-300">{stock.qty}</td>
                            <td className="py-3 px-3 text-right text-slate-300">₩{stock.avg_price.toLocaleString()}</td>
                            <td className="py-3 px-3 text-right text-slate-100">₩{stock.current_price.toLocaleString()}</td>
                            <td className={`py-3 px-3 text-right font-semibold ${stock.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                              {stock.profit >= 0 ? '+' : ''}₩{stock.profit.toLocaleString()}
                            </td>
                            <td className={`py-3 px-3 text-right font-semibold`}>
                              <Rate value={(stock.profit_rate >= 0 ? '+' : '') + stock.profit_rate.toFixed(2) + '%'} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col justify-center items-center py-16 text-center">
                    <svg className="w-12 h-12 text-slate-600 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"></path>
                    </svg>
                    <p className="text-xs font-semibold text-slate-400">대시보드 자산 데이터가 비활성화되어 있습니다.</p>
                    <p className="text-[11px] text-slate-500 mt-1 max-w-sm">백엔드에서 계좌 자산 데이터가 연결되면 보유 종목과 평가 손익이 표시됩니다.</p>
                  </div>
                )}
              </div>
            </main>
          )}

          {activeTab === 'watchlist' && <WatchlistTab />}
          {activeTab === 'assets' && <AssetsTab balance={balance} allocation={allocation} />}
          {activeTab === 'history' && <TradeHistoryTab />}
          {activeTab === 'settings' && (
            <Settings
              isLoggedIn={isLoggedIn}
              userEmail={userEmail}
              handleLogout={handleLogout}
              userProfile={userProfile}
              hideHeader={true}
            />
          )}
        </div>
      </div>
    </div>
  )
}
