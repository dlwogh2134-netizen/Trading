import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  deleteUserWatchlistItem,
  fetchUserWatchlist,
  normalizeWatchlistItem,
  upsertUserWatchlistItem,
} from '../supabaseClient'

const API_BASE_URL = 'http://localhost:5050'

function getKoreanMarketState() {
  const now = new Date()
  const kstText = now.toLocaleString('en-US', { timeZone: 'Asia/Seoul' })
  const kst = new Date(kstText)
  const day = kst.getDay()
  const minutes = kst.getHours() * 60 + kst.getMinutes()
  const isWeekday = day >= 1 && day <= 5
  const isOpen = isWeekday && minutes >= 9 * 60 && minutes <= 15 * 60 + 30

  return {
    isOpen,
    label: isOpen ? '실시간 자동 갱신: 60초' : '장 마감 자동 갱신: 10분',
  }
}

export function getMobileHomeWatchlistKey(row = {}, assetType = 'STOCK') {
  const item = normalizeWatchlistItem({ ...row, asset_type: assetType })
  return `${item.asset_type}:${item.exchange}:${item.symbol}`
}

export default function useMobileHomeMarket({ isLoggedIn, activeCategory, activeMetric }) {
  const navigate = useNavigate()
  const [stockRows, setStockRows] = useState([])
  const [coinRows, setCoinRows] = useState([])
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')
  const [favoriteKeys, setFavoriteKeys] = useState(new Set())
  const [marketState, setMarketState] = useState(getKoreanMarketState())

  const loadFavorites = async () => {
    if (!isLoggedIn) {
      setFavoriteKeys(new Set())
      return
    }

    try {
      const items = await fetchUserWatchlist()
      setFavoriteKeys(new Set(items.map((item) => getMobileHomeWatchlistKey(item, item.assetType))))
    } catch (error) {
      console.warn('Failed to load watchlist.', error)
      setFavoriteKeys(new Set())
    }
  }

  const loadOverview = async (forceRefresh = false) => {
    try {
      setStatus('loading')
      const currentMarketState = getKoreanMarketState()
      setMarketState(currentMarketState)
      const response = await fetch(`${API_BASE_URL}/api/home/market`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          filters: {
            region: activeCategory.region || '국내',
            ranking: activeMetric.ranking,
            horizon: '실시간',
            forceRefresh,
          },
        }),
      })

      const data = await response.json()
      if (!response.ok || !data.success) {
        throw new Error(data.message || '시세를 불러오지 못했습니다.')
      }

      setStockRows(Array.isArray(data.data?.stocks) ? data.data.stocks : [])
      setCoinRows(Array.isArray(data.data?.coins) ? data.data.coins : [])
      setMessage(data.data?.message || '')
      setStatus('ready')
    } catch (error) {
      setStockRows([])
      setCoinRows([])
      setMessage(error.message || '시장 데이터를 불러오지 못했습니다.')
      setStatus('error')
    }
  }

  const handleToggleFavorite = async (row, assetType) => {
    if (!isLoggedIn) {
      alert('로그인이 필요한 서비스입니다.')
      navigate('/login')
      return
    }

    const key = getMobileHomeWatchlistKey(row, assetType)
    const nextKeys = new Set(favoriteKeys)
    const isFavorite = nextKeys.has(key)

    try {
      if (isFavorite) {
        nextKeys.delete(key)
        setFavoriteKeys(nextKeys)
        await deleteUserWatchlistItem({ ...row, asset_type: assetType })
      } else {
        nextKeys.add(key)
        setFavoriteKeys(nextKeys)
        await upsertUserWatchlistItem({ ...row, asset_type: assetType })
      }
    } catch (error) {
      await loadFavorites()
      alert(error.message || '관심종목 저장 중 문제가 발생했습니다.')
    }
  }

  useEffect(() => {
    loadFavorites()
  }, [isLoggedIn])

  useEffect(() => {
    loadOverview(false)
  }, [activeCategory.key, activeCategory.region, activeMetric.ranking])

  return {
    stockRows,
    coinRows,
    status,
    message,
    favoriteKeys,
    marketState,
    loadOverview,
    handleToggleFavorite,
  }
}
