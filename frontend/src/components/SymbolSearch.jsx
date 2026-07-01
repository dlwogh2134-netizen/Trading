import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

// 종목 퀵 검색 공통 컴포넌트
// - 주식/코인 자산 유형 선택 + 심볼 입력 + 자동완성 드롭다운 + 이동 기능
// - Header, Dashboard 등 여러 위치에서 재사용 가능
export default function SymbolSearch({ className = '' }) {
  const [assetType, setAssetType] = useState('STOCK')
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const navigate = useNavigate()

  const navigateToSearchNotFound = (searchText) => {
    const params = new URLSearchParams({
      query: searchText,
      assetType,
    })
    navigate(`/search/not-found?${params.toString()}`)
  }

  // 폼 제출: 심볼 매핑 후 상세 페이지로 이동
  const handleSubmit = async (e) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return

    try {
      const res = await fetch(
        `http://localhost:5050/api/symbol/lookup?query=${encodeURIComponent(trimmed)}`
      )
      const resData = await res.json()
      if (resData.success && resData.data) {
        const { symbol, asset_type } = resData.data
        navigate(`/asset/${String(asset_type || assetType).toUpperCase()}/${symbol}`)
      } else {
        navigateToSearchNotFound(trimmed)
      }
    } catch {
      navigateToSearchNotFound(trimmed)
    }
    setQuery('')
    setSuggestions([])
    setShowSuggestions(false)
  }

  // 입력 변경 시 실시간 자동완성 요청
  const handleInputChange = async (e) => {
    const val = e.target.value
    setQuery(val)

    if (val.trim().length > 0) {
      try {
        const res = await fetch(
          `http://localhost:5050/api/symbol/search?query=${encodeURIComponent(val)}`
        )
        const resData = await res.json()
        if (resData.success && resData.data) {
          setSuggestions(resData.data)
          setShowSuggestions(true)
        }
      } catch {
        // 자동완성 실패 시 조용히 무시
      }
    } else {
      setSuggestions([])
      setShowSuggestions(false)
    }
  }

  // 추천 항목 클릭 시 즉시 이동
  const handleSuggestionClick = (item) => {
    navigate(`/asset/${String(item.asset_type || 'STOCK').toUpperCase()}/${item.symbol}`)
    setQuery('')
    setSuggestions([])
    setShowSuggestions(false)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={`flex items-center gap-2 ${className}`}
      autoComplete="off"
    >
      {/* 자산 유형 토글 */}
      <div className="flex bg-slate-800 p-0.5 rounded border border-slate-700 text-xs shrink-0">
        <button
          type="button"
          onClick={() => setAssetType('STOCK')}
          className={`px-2.5 py-1 rounded transition-all cursor-pointer font-bold ${
            assetType === 'STOCK' ? 'bg-blue-600 text-white' : 'text-slate-400'
          }`}
        >
          주식
        </button>
        <button
          type="button"
          onClick={() => setAssetType('CRYPTO')}
          className={`px-2.5 py-1 rounded transition-all cursor-pointer font-bold ${
            assetType === 'CRYPTO' ? 'bg-blue-600 text-white' : 'text-slate-400'
          }`}
        >
          코인
        </button>
      </div>

      {/* 검색 입력 + 자동완성 드롭다운 */}
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={handleInputChange}
          onFocus={() => { if (query.trim()) setShowSuggestions(true) }}
          onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
          placeholder={assetType === 'STOCK' ? '005930 · AAPL · 삼성전자' : 'BTC · ETH · XRP'}
          className="bg-[#0f172a] border border-slate-700 text-[#e2e2ec] font-mono text-xs rounded px-3 py-1.5 w-44 focus:outline-none focus:border-blue-500 transition-colors"
          required
        />

        {showSuggestions && suggestions.length > 0 && (
          <div className="absolute left-0 right-0 mt-1 bg-[#090d1a]/95 border border-[#1f2945] rounded-lg shadow-2xl z-50 max-h-60 overflow-y-auto backdrop-blur-md">
            {suggestions.map((item) => (
              <div
                key={item.symbol}
                onMouseDown={() => handleSuggestionClick(item)}
                className="flex justify-between items-center px-3 py-2.5 hover:bg-blue-950/40 cursor-pointer border-b border-[#1f2945]/30 last:border-none transition-all"
              >
                <div className="flex flex-col">
                  <span className="text-xs font-bold text-white">{item.display_name}</span>
                  <span className="text-[9px] text-slate-500 font-mono">{item.symbol}</span>
                </div>
                <span className="text-[9px] font-bold text-cyan-400 bg-cyan-950/60 px-1.5 py-0.5 rounded border border-cyan-900/60 uppercase tracking-widest font-mono">
                  {item.asset_type === 'STOCK' ? '주식' : '코인'}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 이동 버튼 */}
      <button
        type="submit"
        className="bg-blue-600 hover:bg-blue-700 active:scale-95 text-white text-xs font-bold px-3 py-1.5 rounded transition-all cursor-pointer shrink-0"
      >
        이동
      </button>
    </form>
  )
}
