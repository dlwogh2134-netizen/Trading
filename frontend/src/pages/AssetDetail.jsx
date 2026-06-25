import React, { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { createChart, CandlestickSeries } from 'lightweight-charts'
import { supabase } from '../supabaseClient'
import Header from '../components/Header.jsx'

export default function AssetDetail({ isLoggedIn, userEmail, handleLogout, userProfile }) {
  const { assetType, symbol } = useParams()
  const navigate = useNavigate()

  // 1. 거래소 기본값 세팅 (주식은 KIS 모의투자를 기본값으로, 코인은 COINONE)
  const defaultExchange = assetType === 'STOCK' ? 'KIS' : 'COINONE'
  const [exchange, setExchange] = useState(defaultExchange)
  
  // 2. 환경 세팅 (KIS 모의투자를 위해 MOCK 기본값)
  const [brokerEnv, setBrokerEnv] = useState(assetType === 'STOCK' && defaultExchange === 'KIS' ? 'MOCK' : 'REAL')
  const [chartInterval, setChartInterval] = useState(assetType === 'STOCK' ? '1d' : '1h')
  
  // 3. 차트 및 시세 데이터 상태
  const [candleData, setCandleData] = useState([])
  const [loadingChart, setLoadingChart] = useState(true)
  const [currentPrice, setCurrentPrice] = useState(0)
  const [priceChangeRate, setPriceChangeRate] = useState(0)

  // 4. 주문 폼 상태
  const [side, setSide] = useState('BUY') // BUY | SELL
  const [orderType, setOrderType] = useState('LIMIT') // LIMIT | MARKET
  const [price, setPrice] = useState('')
  const [quantity, setQuantity] = useState('')
  const [autoExit, setAutoExit] = useState(false)
  const [targetProfitRate, setTargetProfitRate] = useState(5.0)
  const [stopLossRate, setStopLossRate] = useState(-3.0)

  // 5. 트랜잭션 UI 상태
  const [submitting, setSubmitting] = useState(false)
  const [tradeMessage, setTradeMessage] = useState({ text: '', isError: false })

  // 6. 실시간 호가, 체결, 보유자산 상태 (WTS 연동 고도화)
  const [orderbook, setOrderbook] = useState(null)
  const [trades, setTrades] = useState([])
  const [userBalance, setUserBalance] = useState(null)
  const [activeTab, setActiveTab] = useState('news') // news | community
  const [newsList, setNewsList] = useState([])
  const [loadingNews, setLoadingNews] = useState(false)
  const [displayName, setDisplayName] = useState(symbol)

  const chartContainerRef = useRef(null)
  const chartRef = useRef(null)
  const candleSeriesRef = useRef(null)
  const abortControllerRef = useRef(null)

  // 세션 토큰 헤더 획득 헬퍼
  const getAuthHeader = async () => {
    const { data: { session } } = await supabase.auth.getSession()
    if (!session) return null
    return `Bearer ${session.access_token}`
  }

  // 종목 메타데이터(한글명 등) 조회
  const fetchSymbolMetadata = async () => {
    try {
      const response = await fetch(`http://localhost:5050/api/symbol/lookup?query=${symbol}`)
      const resData = await response.json()
      if (resData.success && resData.data && resData.data.display_name) {
        setDisplayName(resData.data.display_name)
      } else {
        setDisplayName(symbol)
      }
    } catch (e) {
      console.error("종목명 로드 실패:", e)
      setDisplayName(symbol)
    }
  }

  // 실시간 크롤링 뉴스 로드 (종목 한글명/코드 자동 필터링)
  const fetchNewsList = async () => {
    setLoadingNews(true)
    try {
      const response = await fetch(`http://localhost:5050/api/news?symbol=${symbol}&limit=6`)
      const resData = await response.json()
      if (resData.success && resData.data && resData.data.items) {
        setNewsList(resData.data.items)
      }
    } catch (e) {
      console.error("뉴스 로드 실패:", e)
    } finally {
      setLoadingNews(false)
    }
  }

  // 시간 표시 포맷 헬퍼
  const formatTime = (isoString) => {
    if (!isoString) return '';
    try {
      const date = new Date(isoString);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      if (diffMins < 1) return '방금 전';
      if (diffMins < 60) return `${diffMins}분 전`;
      const diffHours = Math.floor(diffMins / 60);
      if (diffHours < 24) return `${diffHours}시간 전`;
      return date.toLocaleDateString();
    } catch (e) {
      return '';
    }
  }

  // 1. 시세 캔들 로드
  const fetchCandles = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const controller = new AbortController()
    abortControllerRef.current = controller

    setLoadingChart(true)
    const authHeader = await getAuthHeader()
    
    try {
      const chartEx = assetType === 'STOCK' ? 'TOSS' : exchange;
      const chartEnv = assetType === 'STOCK' ? 'REAL' : brokerEnv;
      const url = `http://localhost:5050/api/chart/candles?exchange=${chartEx}&symbol=${symbol}&interval=${chartInterval}&broker_env=${chartEnv}&count=300`
      const headers = {}
      if (authHeader) {
        headers['Authorization'] = authHeader
      }

      const response = await fetch(url, { 
        headers,
        signal: controller.signal
      })
      const resData = await response.json()

      if (resData.success && resData.data && resData.data.length > 0) {
        const rawFormatted = resData.data
          .map(item => {
            const originTime = item.time;
            let finalTime = originTime;
            
            if (typeof originTime === 'string') {
              if (originTime.includes('T')) {
                finalTime = originTime.split('T')[0];
              } else if (originTime.includes(' ')) {
                finalTime = originTime.split(' ')[0];
              }
            }
            
            if (typeof finalTime === 'number' || (typeof finalTime === 'string' && /^\d+$/.test(finalTime))) {
              finalTime = parseInt(finalTime, 10);
            } else {
              finalTime = finalTime ? finalTime.toString() : '';
            }
            
            return {
              time: finalTime,
              open: parseFloat(item.open),
              high: parseFloat(item.high),
              low: parseFloat(item.low),
              close: parseFloat(item.close),
              volume: parseFloat(item.volume || 0)
            };
          })
          .filter(item => {
            const isValidTime = (typeof item.time === 'number' && !isNaN(item.time)) || 
                               (typeof item.time === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(item.time));
            return isValidTime && 
                   !isNaN(item.open) && 
                   !isNaN(item.high) && 
                   !isNaN(item.low) && 
                   !isNaN(item.close);
          });

        if (rawFormatted.length === 0) {
          console.error('유효한 시세 데이터 포맷이 없습니다.');
          if (abortControllerRef.current === controller) {
            setLoadingChart(false);
          }
          return;
        }

        rawFormatted.sort((a, b) => {
          if (typeof a.time === 'number' && typeof b.time === 'number') {
            return a.time - b.time;
          }
          return a.time.toString().localeCompare(b.time.toString());
        });

        const uniqueFormatted = [];
        const seenTimes = new Set();
        for (let i = rawFormatted.length - 1; i >= 0; i--) {
          const item = rawFormatted[i];
          if (!seenTimes.has(item.time)) {
            seenTimes.add(item.time);
            uniqueFormatted.push(item);
          }
        }
        uniqueFormatted.reverse();

        if (uniqueFormatted.length === 0) {
          console.error('중복 제거 후 시세 데이터가 없습니다.');
          if (abortControllerRef.current === controller) {
            setLoadingChart(false);
          }
          return;
        }

        setCandleData(uniqueFormatted);
        window.__debug_candle_data = uniqueFormatted;
        
        const lastCandle = uniqueFormatted[uniqueFormatted.length - 1];
        setCurrentPrice(lastCandle.close);
        
        if (uniqueFormatted.length > 1) {
          const prevCandle = uniqueFormatted[uniqueFormatted.length - 2];
          const change = prevCandle.close !== 0 ? ((lastCandle.close - prevCandle.close) / prevCandle.close) * 100 : 0;
          setPriceChangeRate(change);
        } else {
          setPriceChangeRate(0);
        }
        
        setPrice(prev => prev === '' ? lastCandle.close.toString() : prev);
      } else {
        console.error('시세 데이터를 가져오지 못했습니다:', resData.message);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        return
      }
      console.error('시세 API 호출 오류:', error)
    } finally {
      if (abortControllerRef.current === controller) {
        setLoadingChart(false)
      }
    }
  }

  // 2. 실시간 호가/체결 데이터 로드 (폴링)
  const fetchOrderbookAndTrades = async () => {
    try {
      const chartEx = assetType === 'STOCK' ? 'TOSS' : exchange;
      const chartEnv = assetType === 'STOCK' ? 'REAL' : brokerEnv;
      const authHeader = await getAuthHeader()
      
      const headers = {}
      if (authHeader) {
        headers['Authorization'] = authHeader
      }

      // 호가 조회
      const obUrl = `http://localhost:5050/api/chart/orderbook?exchange=${chartEx}&symbol=${symbol}&broker_env=${chartEnv}`;
      const obRes = await fetch(obUrl, { headers });
      const obData = await obRes.json();
      if (obData.success) {
        setOrderbook(obData.data);
      }
      
      // 체결 조회
      const trUrl = `http://localhost:5050/api/chart/trades?exchange=${chartEx}&symbol=${symbol}&broker_env=${chartEnv}`;
      const trRes = await fetch(trUrl, { headers });
      const trData = await trRes.json();
      if (trData.success) {
        setTrades(trData.data);
      }
    } catch (e) {
      console.error("실시간 호가/체결 갱신 오류:", e);
    }
  }

  // 3. 실시간 유저 자산 잔고 로드
  const fetchUserBalance = async () => {
    const authHeader = await getAuthHeader()
    if (!authHeader) return

    try {
      const payload = {
        exchange: exchange,
        env: brokerEnv
      }
      const response = await fetch('http://localhost:5050/api/dashboard/balance', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': authHeader
        },
        body: JSON.stringify(payload)
      })
      const resData = await response.json()
      if (resData.success) {
        setUserBalance(resData.data)
      }
    } catch (error) {
      console.error('잔고 로드 실패:', error)
    }
  }

  // 거래소 토글 시 환경값 변경
  const handleExchangeChange = (newEx) => {
    setExchange(newEx)
    if (newEx === 'KIS') {
      setBrokerEnv('MOCK')
    } else {
      setBrokerEnv('REAL')
    }
    setPrice('')
    setQuantity('')
  }

  // 호가 클릭 시 단가 자동 입력 매핑
  const handlePriceClick = (clickedPrice) => {
    if (orderType === 'LIMIT') {
      setPrice(clickedPrice.toString());
    }
  }

  useEffect(() => {
    fetchCandles()
    fetchUserBalance()
    fetchNewsList()
    fetchSymbolMetadata()
  }, [exchange, symbol, chartInterval, brokerEnv])

  useEffect(() => {
    fetchOrderbookAndTrades();
    const intervalId = setInterval(fetchOrderbookAndTrades, 2000); // 2초마다 갱신
    return () => clearInterval(intervalId);
  }, [exchange, symbol, brokerEnv]);

  // 3. TradingView Lightweight Charts 차트 드로잉 및 리사이즈 대응
  useEffect(() => {
    if (!chartContainerRef.current || candleData.length === 0) return

    if (chartRef.current) {
      try {
        chartRef.current.remove()
      } catch (e) {
        console.error('기존 차트 정리 에러:', e)
      }
      chartRef.current = null
    }

    if (chartContainerRef.current) {
      chartContainerRef.current.innerHTML = ''
    }

    try {
      const containerWidth = chartContainerRef.current.clientWidth || chartContainerRef.current.parentElement?.clientWidth || 800;

      const chart = createChart(chartContainerRef.current, {
        layout: {
          background: { type: 'solid', color: '#0e1529' }, // Obsidian Navy 테마
          textColor: '#94a3b8',
          fontSize: 11,
        },
        grid: {
          vertLines: { color: 'rgba(31, 41, 69, 0.4)' },
          horzLines: { color: 'rgba(31, 41, 69, 0.4)' },
        },
        rightPriceScale: {
          borderColor: '#1f2945',
          autoScale: true,
        },
        timeScale: {
          borderColor: '#1f2945',
          timeVisible: true,
          secondsVisible: false,
        },
        width: containerWidth,
        height: 380,
      })

      const candleSeries = chart.addSeries(CandlestickSeries, {
        upColor: '#ef4444', // 한국 상승 빨강
        downColor: '#3b82f6', // 한국 하락 파랑
        borderVisible: false,
        wickUpColor: '#ef4444',
        wickDownColor: '#3b82f6',
      })

      candleSeries.setData(candleData)
      try {
        chart.timeScale().fitContent()
      } catch (fitErr) {
        console.error('동기 fitContent 에러:', fitErr)
      }
      
      chartRef.current = chart
      candleSeriesRef.current = candleSeries

      const handleResize = () => {
        if (chartRef.current && chartContainerRef.current) {
          try {
            const newWidth = chartContainerRef.current.clientWidth || 800;
            chartRef.current.applyOptions({ width: newWidth })
          } catch (err) {
            console.error('차트 리사이즈 조절 에러:', err)
          }
        }
      }

      window.addEventListener('resize', handleResize)

      setTimeout(() => {
        if (chartRef.current && chartContainerRef.current) {
          const fitWidth = chartContainerRef.current.clientWidth || 800;
          chartRef.current.applyOptions({ width: fitWidth });
          chartRef.current.timeScale().fitContent();
        }
      }, 50)

      return () => {
        window.removeEventListener('resize', handleResize)
        try {
          chart.remove()
        } catch (e) {
          console.error('차트 소멸 정리 에러:', e)
        }
        chartRef.current = null
        if (chartContainerRef.current) {
          chartContainerRef.current.innerHTML = ''
        }
      }
    } catch (err) {
      console.error('TradingView 차트 생성 치명적 에러:', err)
    }
  }, [candleData])

  // 4. 수동 주문 제출 핸들러
  const handlePlaceOrder = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setTradeMessage({ text: '', isError: false })

    const authHeader = await getAuthHeader()
    if (!authHeader) {
      setTradeMessage({ text: '로그인이 필요합니다.', isError: true })
      setSubmitting(false)
      return
    }

    if (!quantity || parseFloat(quantity) <= 0) {
      setTradeMessage({ text: '올바른 주문 수량을 입력하세요.', isError: true })
      setSubmitting(false)
      return
    }

    if (orderType === 'LIMIT' && (!price || parseFloat(price) <= 0)) {
      setTradeMessage({ text: '올바른 지정가 단가를 입력하세요.', isError: true })
      setSubmitting(false)
      return
    }

    try {
      const payload = {
        exchange,
        symbol,
        action: side,
        order_type: orderType,
        quantity: parseFloat(quantity),
        price: orderType === 'LIMIT' ? parseFloat(price) : null,
        broker_env: brokerEnv,
        auto_exit: autoExit,
        target_profit_rate: autoExit ? parseFloat(targetProfitRate) : null,
        stop_loss_rate: autoExit ? parseFloat(stopLossRate) : null
      }

      const response = await fetch('http://localhost:5050/api/trade/order', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': authHeader
        },
        body: JSON.stringify(payload)
      })

      const resData = await response.json()

      if (resData.success) {
        setTradeMessage({
          text: `주문이 성공적으로 전송되었습니다! 주문번호: ${resData.order_id || 'MOCK'}`,
          isError: false
        })
        setQuantity('')
        fetchUserBalance() // 주문 성공 시 보유 자산 즉시 갱신
      } else {
        setTradeMessage({
          text: resData.message || '주문 전송에 실패했습니다.',
          isError: true
        })
      }
    } catch (error) {
      setTradeMessage({
        text: `네트워크 오류가 발생했습니다: ${error.message}`,
        isError: true
      })
    } finally {
      setSubmitting(false)
    }
  }

  // 총액 계산
  const targetPrice = orderType === 'LIMIT' ? parseFloat(price || 0) : currentPrice
  const totalEstimatedAmount = targetPrice * parseFloat(quantity || 0)

  // 보유 주식 필터링
  const myHolding = userBalance?.holdings?.find(h => h.symbol.toUpperCase() === symbol.toUpperCase() || symbol.toUpperCase().includes(h.symbol.toUpperCase()));

  return (
    <div className="min-h-screen bg-[#070b19] text-[#e2e2ec] font-inter">
      <div className="max-w-7xl mx-auto px-4 py-4">
        
        {/* 상단 네비게이션 헤더 */}
        <Header isLoggedIn={isLoggedIn} userEmail={userEmail} handleLogout={handleLogout} userProfile={userProfile} />

        {/* 뒤로가기 버튼 */}
        <div className="mt-2 mb-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex items-center gap-2 text-xs font-bold text-slate-400 hover:text-white transition-all bg-transparent border-none cursor-pointer outline-none"
          >
            <span>← 대시보드로 돌아가기</span>
          </button>
        </div>

        {/* 1. 상단 토스 WTS 스타일 메타 정보 헤더 바 */}
        <div className="bg-[#0e1529]/90 border border-[#1f2945] rounded-xl p-5 mb-5 backdrop-blur-md flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[9px] font-bold text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-900/60 uppercase tracking-widest font-mono">
                {assetType} · {exchange} ({brokerEnv})
              </span>
            </div>
            <h1 className="text-xl font-bold font-mono text-white mt-1.5 flex items-center gap-2">
              {displayName !== symbol ? `${displayName} (${symbol})` : symbol} <span className="text-xs text-slate-400 font-normal">({assetType === 'STOCK' ? '주식' : '가상자산'})</span>
            </h1>
          </div>
          
          <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
            {/* 현재가 */}
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-400 font-bold">현재가</span>
              <span className="text-lg font-bold font-mono text-white mt-0.5">
                {assetType === 'STOCK' ? `₩${currentPrice.toLocaleString()}` : `$${currentPrice.toLocaleString()}`}
              </span>
            </div>

            {/* 등락률 */}
            <div className="flex flex-col">
              <span className="text-[10px] text-slate-400 font-bold">전일대비</span>
              <span className={`text-sm font-bold font-mono mt-0.5 flex items-center ${priceChangeRate >= 0 ? 'text-[#ef4444]' : 'text-[#3b82f6]'}`}>
                {priceChangeRate >= 0 ? '▲' : '▼'} {Math.abs(priceChangeRate).toFixed(2)}%
              </span>
            </div>

            {/* 52주 범위 게이지 바 */}
            <div className="hidden sm:flex flex-col w-48">
              <div className="flex justify-between text-[9px] text-slate-400 font-mono">
                <span>52주 최저</span>
                <span>52주 최고</span>
              </div>
              <div className="w-full bg-[#1b253b] h-1.5 rounded-full mt-1.5 overflow-hidden relative">
                {/* 현재 위치 마커바 */}
                <div 
                  className="bg-cyan-400 h-full absolute rounded-full" 
                  style={{ width: '40%', left: '30%' }}
                />
              </div>
            </div>

            {/* 거래대금 또는 거래소 추가 메타 정보 */}
            <div className="flex flex-col text-right">
              <span className="text-[10px] text-slate-400 font-bold">체결강도</span>
              <span className="text-sm font-mono text-emerald-400 font-bold mt-0.5">
                {orderbook?.is_mock ? '112.4%' : '124.93%'}
              </span>
            </div>
          </div>
        </div>

        {/* 2. 메인 3열(3-column) WTS 레이아웃 */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
          
          {/* [1열: 좌측 - 차트 및 요약 뉴스 탭 (6/12 cols)] */}
          <div className="lg:col-span-6 flex flex-col gap-5">
            
            {/* 차트 카드 */}
            <div className="bg-[#0e1529]/90 border border-[#1f2945] rounded-xl p-4 flex flex-col gap-4 backdrop-blur-md">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <span className="w-1.5 h-3 bg-cyan-400 rounded-full" />
                  <span className="text-xs font-bold text-white">실시간 통합 차트</span>
                </div>
                
                {/* 캔들 주기 변경 탭 */}
                <div className="flex flex-wrap gap-1 bg-[#1b253b] p-0.5 rounded border border-[#2b395b] max-w-[70%] sm:max-w-none justify-end">
                  {assetType === 'STOCK' ? (
                    <>
                      {[
                        { label: '1분', val: '1m' },
                        { label: '5분', val: '5m' },
                        { label: '15분', val: '15m' },
                        { label: '30분', val: '30m' },
                        { label: '1시간', val: '1h' },
                        { label: '일봉', val: '1d' },
                        { label: '주봉', val: '1w' },
                        { label: '월봉', val: '1M' }
                      ].map((item) => (
                        <button
                          key={item.val}
                          onClick={() => setChartInterval(item.val)}
                          className={`text-[9px] sm:text-[10px] font-bold px-1.5 sm:px-2.5 py-0.5 rounded transition-all cursor-pointer ${chartInterval === item.val ? 'bg-cyan-500 text-slate-950 font-black' : 'text-slate-400 hover:text-white'}`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </>
                  ) : (
                    <>
                      {[
                        { label: '1분', val: '1m' },
                        { label: '5분', val: '5m' },
                        { label: '15분', val: '15m' },
                        { label: '30분', val: '30m' },
                        { label: '1시간', val: '1h' },
                        { label: '4시간', val: '4h' },
                        { label: '일봉', val: '1d' },
                        { label: '주봉', val: '1w' },
                        { label: '월봉', val: '1M' }
                      ].map((item) => (
                        <button
                          key={item.val}
                          onClick={() => setChartInterval(item.val)}
                          className={`text-[9px] sm:text-[10px] font-bold px-1.5 sm:px-2.5 py-0.5 rounded transition-all cursor-pointer ${chartInterval === item.val ? 'bg-cyan-500 text-slate-950 font-black' : 'text-slate-400 hover:text-white'}`}
                        >
                          {item.label}
                        </button>
                      ))}
                    </>
                  )}
                </div>
              </div>

              {/* 차트 영역 */}
              <div className="w-full relative min-h-[380px] bg-[#0e1529] rounded-lg overflow-hidden border border-[#1f2945]/60">
                {loadingChart && (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#0e1529]/95 z-10 rounded">
                    <span className="text-xs text-cyan-400 font-mono animate-pulse">시세 차트 로드 중...</span>
                  </div>
                )}
                <div ref={chartContainerRef} className="w-full" />
              </div>
            </div>

            {/* 하단 RAG 뉴스 / 종목 정보 탭 카드 */}
            <div className="bg-[#0e1529]/90 border border-[#1f2945] rounded-xl p-5 backdrop-blur-md">
              <div className="flex border-b border-[#1f2945] pb-2 mb-4">
                {[
                  { id: 'news', label: '뉴스 및 공시' },
                  { id: 'community', label: '토론(커뮤니티)' }
                ].map(t => (
                  <button
                    key={t.id}
                    onClick={() => setActiveTab(t.id)}
                    className={`text-xs font-bold px-4 py-2 border-b-2 transition-all cursor-pointer ${activeTab === t.id ? 'border-cyan-400 text-cyan-400' : 'border-transparent text-slate-400 hover:text-white'}`}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {activeTab === 'news' && (
                <div className="flex flex-col gap-4 max-h-[220px] overflow-y-auto pr-1">
                  {loadingNews ? (
                    <div className="py-8 text-center text-xs text-cyan-400/80 font-mono animate-pulse">
                      실시간 크롤링 뉴스 분석 중...
                    </div>
                  ) : newsList.length > 0 ? (
                    <>
                      <div className="border-l-2 border-cyan-500 pl-3 py-1.5 bg-cyan-950/20 rounded-r">
                        <span className="text-[10px] text-cyan-400 font-bold uppercase tracking-wider">AI RAG 뉴스 핵심 요약</span>
                        <p className="text-xs text-[#e2e2ec] mt-1 leading-relaxed">
                          {newsList.find(n => n.ai_summary)?.ai_summary || newsList[0]?.summary || `${symbol} 종목에 대한 실시간 수집 뉴스를 분석 중입니다.`}
                        </p>
                      </div>
                      {newsList.map(item => (
                        <div key={item.id} className="flex justify-between items-center text-xs py-2 border-b border-[#1f2945]/30 hover:bg-slate-800/10 px-1 rounded transition-all">
                          <a 
                            href={item.url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="text-[#e2e2ec] truncate max-w-[80%] hover:underline cursor-pointer"
                          >
                            {item.title}
                          </a>
                          <span className="text-[10px] text-slate-500 font-mono">{formatTime(item.published_at)}</span>
                        </div>
                      ))}
                    </>
                  ) : (
                    <div className="py-8 text-center text-xs text-slate-500 font-mono">
                      해당 종목의 실시간 수집 뉴스가 존재하지 않습니다.
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'community' && (
                <div className="flex flex-col gap-3 max-h-[220px] overflow-y-auto pr-1 text-xs">
                  <div className="bg-[#1b253b]/40 p-3 rounded border border-[#1f2945]/40 flex flex-col gap-1">
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span className="font-bold text-cyan-400">또치어제자</span>
                      <span>5분 전</span>
                    </div>
                    <p className="text-[#e2e2ec] mt-1 leading-relaxed">진짜 하이닉스 수급 장난아니네요. 다음 타겟은 300만원 갑니다.</p>
                  </div>
                  <div className="bg-[#1b253b]/40 p-3 rounded border border-[#1f2945]/40 flex flex-col gap-1">
                    <div className="flex justify-between text-[10px] text-slate-400">
                      <span className="font-bold text-cyan-400">부자냥냥이</span>
                      <span>20분 전</span>
                    </div>
                    <p className="text-[#e2e2ec] mt-1 leading-relaxed">익절률 5% 조건 주문 걸어놨는데 바로 체결됬네요 꿀맛!</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* [2열: 가운데 - 호가 및 실시간 체결가 (3/12 cols)] */}
          <div className="lg:col-span-3 flex flex-col gap-5">
            
            {/* 호가창 카드 */}
            <div className="bg-[#0e1529]/90 border border-[#1f2945] rounded-xl p-4 flex flex-col gap-3 backdrop-blur-md">
              <div className="flex items-center gap-2 border-b border-[#1f2945] pb-2">
                <span className="w-1.5 h-3 bg-red-400 rounded-full" />
                <span className="text-xs font-bold text-white">실시간 호가 정보</span>
              </div>

              {/* 호가 목록 컨테이너 */}
              <div className="flex flex-col text-xs font-mono select-none">
                {/* 1. 매도 호가 (Asks) - 오름차순의 역순(높은 가격이 위로 가도록) */}
                {[...(orderbook?.asks || [])].reverse().map((ask, idx) => {
                  const maxAskSize = Math.max(...(orderbook?.asks.map(a => a.size) || [1]));
                  const pct = (ask.size / maxAskSize) * 100;
                  return (
                    <div 
                      key={`ask-${idx}`}
                      onClick={() => handlePriceClick(ask.price)}
                      className="flex justify-between items-center py-1.5 px-2 hover:bg-blue-950/30 cursor-pointer border-b border-[#1f2945]/20 relative"
                    >
                      {/* 가로 막대 백그라운드 그래프 */}
                      <div className="absolute right-0 top-0 bottom-0 bg-[#3b82f6]/10 opacity-70 transition-all" style={{ width: `${pct}%` }} />
                      
                      <span className="text-blue-400 z-10">{ask.price.toLocaleString()}</span>
                      <span className="text-slate-400 z-10 text-[10px]">{ask.size.toLocaleString()}</span>
                    </div>
                  )
                })}

                {/* 2. 현재가 중심 표시 */}
                <div className="bg-[#1f2945]/50 border-y border-[#1f2945] py-2 px-3 text-center my-1.5 flex justify-between items-center font-bold">
                  <span className="text-slate-400 text-[10px]">현재가</span>
                  <span className={`text-sm ${priceChangeRate >= 0 ? 'text-[#ef4444]' : 'text-[#3b82f6]'}`}>
                    {currentPrice.toLocaleString()}
                  </span>
                </div>

                {/* 3. 매수 호가 (Bids) - 내림차순 */}
                {(orderbook?.bids || []).map((bid, idx) => {
                  const maxBidSize = Math.max(...(orderbook?.bids.map(b => b.size) || [1]));
                  const pct = (bid.size / maxBidSize) * 100;
                  return (
                    <div 
                      key={`bid-${idx}`}
                      onClick={() => handlePriceClick(bid.price)}
                      className="flex justify-between items-center py-1.5 px-2 hover:bg-red-950/20 cursor-pointer border-b border-[#1f2945]/20 relative"
                    >
                      {/* 가로 막대 백그라운드 그래프 */}
                      <div className="absolute right-0 top-0 bottom-0 bg-[#ef4444]/10 opacity-70 transition-all" style={{ width: `${pct}%` }} />
                      
                      <span className="text-red-400 z-10">{bid.price.toLocaleString()}</span>
                      <span className="text-slate-400 z-10 text-[10px]">{bid.size.toLocaleString()}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* 실시간 체결 기록 */}
            <div className="bg-[#0e1529]/90 border border-[#1f2945] rounded-xl p-4 flex flex-col gap-3 backdrop-blur-md">
              <div className="flex items-center gap-2 border-b border-[#1f2945] pb-2">
                <span className="w-1.5 h-3 bg-cyan-400 rounded-full" />
                <span className="text-xs font-bold text-white">실시간 체결</span>
              </div>

              <div className="flex flex-col gap-2 max-h-[180px] overflow-y-auto font-mono text-[10px] pr-1">
                {trades.map((t, idx) => (
                  <div key={idx} className="flex justify-between items-center py-1 border-b border-[#1f2945]/30">
                    <span className="text-slate-500">{t.time}</span>
                    <span className={t.side === 'BUY' ? 'text-[#ef4444]' : 'text-[#3b82f6]'}>
                      {t.price.toLocaleString()}
                    </span>
                    <span className="text-slate-300 font-bold">{t.qty} 주</span>
                  </div>
                ))}
              </div>
            </div>

          </div>

          {/* [3열: 우측 - 주문 패널 & 내 보유 주식 (3/12 cols)] */}
          <div className="lg:col-span-3 flex flex-col gap-5">
            
            {/* 주문 입력 폼 카드 */}
            <div className="bg-[#0e1529]/90 border border-[#1f2945] rounded-xl p-4 flex flex-col gap-4 backdrop-blur-md">
              <div className="flex justify-between items-center border-b border-[#1f2945] pb-2">
                <span className="text-xs font-bold text-white">수동 주문 제어</span>
                <span className="text-[9px] font-bold text-slate-500">Human-in-the-Loop</span>
              </div>

              {/* 매수/매도 토스형 2분할 버튼 */}
              <div className="grid grid-cols-2 gap-1 bg-[#1b253b] p-0.5 rounded border border-[#2b395b]">
                <button
                  type="button"
                  onClick={() => setSide('BUY')}
                  className={`text-xs font-bold py-1.5 rounded transition-all cursor-pointer ${side === 'BUY' ? 'bg-[#ef4444] text-white' : 'text-slate-400 hover:text-white'}`}
                >
                  구매
                </button>
                <button
                  type="button"
                  onClick={() => setSide('SELL')}
                  className={`text-xs font-bold py-1.5 rounded transition-all cursor-pointer ${side === 'SELL' ? 'bg-[#3b82f6] text-white' : 'text-slate-400 hover:text-white'}`}
                >
                  판매
                </button>
              </div>

              {/* 지정가/시장가 선택 */}
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-400 font-bold">호가 구분</span>
                <div className="flex gap-4">
                  <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer select-none">
                    <input
                      type="radio"
                      name="orderType"
                      value="LIMIT"
                      checked={orderType === 'LIMIT'}
                      onChange={() => setOrderType('LIMIT')}
                      className="accent-cyan-400"
                    />
                    지정가
                  </label>
                  <label className="flex items-center gap-1.5 text-slate-300 cursor-pointer select-none">
                    <input
                      type="radio"
                      name="orderType"
                      value="MARKET"
                      checked={orderType === 'MARKET'}
                      onChange={() => setOrderType('MARKET')}
                      className="accent-cyan-400"
                    />
                    시장가
                  </label>
                </div>
              </div>

              {/* 주문 제출 폼 */}
              <form onSubmit={handlePlaceOrder} className="flex flex-col gap-4">
                {/* 1. 가격 입력 */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] text-slate-400 font-bold">주문 단가 ({assetType === 'STOCK' ? 'KRW' : 'USD'})</span>
                  <input
                    type="number"
                    disabled={orderType === 'MARKET'}
                    value={orderType === 'MARKET' ? currentPrice : price}
                    onChange={(e) => setPrice(e.target.value)}
                    placeholder="단가를 입력하세요"
                    className="w-full bg-[#070b19] border border-[#1f2945] text-[#e2e2ec] font-mono rounded px-3 py-2 text-xs focus:outline-none focus:border-cyan-400 disabled:opacity-50 disabled:bg-[#12192b]"
                  />
                </div>

                {/* 2. 수량 입력 */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] text-slate-400 font-bold">주문 수량</span>
                  <input
                    type="number"
                    step="any"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    placeholder="수량을 입력하세요"
                    className="w-full bg-[#070b19] border border-[#1f2945] text-[#e2e2ec] font-mono rounded px-3 py-2 text-xs focus:outline-none focus:border-cyan-400"
                    required
                  />
                </div>

                {/* 3. 거래 계좌 스위처 토글 */}
                <div className="flex flex-col gap-1.5">
                  <span className="text-[10px] text-slate-400 font-bold">주문 거래소 계좌</span>
                  <div className="grid grid-cols-2 gap-1 bg-[#070b19] p-0.5 rounded border border-[#1f2945]">
                    {assetType === 'STOCK' ? (
                      <>
                        <button
                          type="button"
                          onClick={() => handleExchangeChange('KIS')}
                          className={`text-[10px] font-bold py-1.5 rounded transition-all cursor-pointer ${exchange === 'KIS' ? 'bg-[#1b253b] text-cyan-400 border border-cyan-900/60' : 'text-slate-400 hover:text-white'}`}
                        >
                          한투 모의
                        </button>
                        <button
                          type="button"
                          onClick={() => handleExchangeChange('TOSS')}
                          className={`text-[10px] font-bold py-1.5 rounded transition-all cursor-pointer ${exchange === 'TOSS' ? 'bg-[#1b253b] text-cyan-400 border border-cyan-900/60' : 'text-slate-400 hover:text-white'}`}
                        >
                          토스 실거래
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => handleExchangeChange('COINONE')}
                          className={`text-[10px] font-bold py-1.5 rounded transition-all cursor-pointer ${exchange === 'COINONE' ? 'bg-[#1b253b] text-cyan-400 border border-cyan-900/60' : 'text-slate-400 hover:text-white'}`}
                        >
                          코인원
                        </button>
                        <button
                          type="button"
                          onClick={() => handleExchangeChange('BINANCE')}
                          className={`text-[10px] font-bold py-1.5 rounded transition-all cursor-pointer ${exchange === 'BINANCE' ? 'bg-[#1b253b] text-cyan-400 border border-cyan-900/60' : 'text-slate-400 hover:text-white'}`}
                        >
                          바이낸스
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* 4. 총 주문 예정 금액 */}
                <div className="bg-[#070b19] border border-[#1f2945] rounded p-3 flex justify-between items-center text-xs">
                  <span className="text-slate-400 font-bold">예정 금액</span>
                  <span className="font-mono font-bold text-white">
                    {assetType === 'STOCK'
                      ? `₩${totalEstimatedAmount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                      : `$${totalEstimatedAmount.toLocaleString(undefined, { maximumFractionDigits: 4 })}`}
                  </span>
                </div>

                {/* 5. 자동 감시 조건 체크박스 */}
                {side === 'BUY' && (
                  <div className="border-t border-[#1f2945] pt-3 mt-1 flex flex-col gap-2.5">
                    <label className="flex items-center gap-2 text-[11px] text-slate-300 cursor-pointer select-none">
                      <input
                        type="checkbox"
                        checked={autoExit}
                        onChange={(e) => setAutoExit(e.target.checked)}
                        className="accent-cyan-400 rounded"
                      />
                      체결 시 자동 감시 조건 등록
                    </label>

                    {autoExit && (
                      <div className="grid grid-cols-2 gap-2 bg-[#070b19] border border-[#1f2945] rounded p-2.5">
                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] font-bold text-green-400">목표 익절 (%)</label>
                          <input
                            type="number"
                            step="0.1"
                            value={targetProfitRate}
                            onChange={(e) => setTargetProfitRate(e.target.value)}
                            className="bg-slate-800 border border-slate-700 text-[#e2e2ec] font-mono rounded py-0.5 text-xs text-center"
                          />
                        </div>
                        <div className="flex flex-col gap-1">
                          <label className="text-[9px] font-bold text-red-400">손실 제한 (%)</label>
                          <input
                            type="number"
                            step="0.1"
                            value={stopLossRate}
                            onChange={(e) => setStopLossRate(e.target.value)}
                            className="bg-slate-800 border border-slate-700 text-[#e2e2ec] font-mono rounded py-0.5 text-xs text-center"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* 안전 가드 텍스트 */}
                {brokerEnv === 'REAL' ? (
                  <div className="text-[9px] text-amber-500 bg-amber-950/20 p-2 rounded border border-amber-900/40 leading-relaxed font-mono">
                    실거래 1회 한도 10만원 하드 캐핑 안전 가드 작동 중
                  </div>
                ) : (
                  <div className="text-[9px] text-slate-500 bg-slate-900/40 p-2 rounded border border-[#1f2945]/40 leading-relaxed font-mono">
                    모의투자 테스트 모드 - 주문 한도 무제한
                  </div>
                )}

                {/* 결과 메세지 */}
                {tradeMessage.text && (
                  <div className={`p-2.5 rounded text-xs font-bold leading-relaxed border ${tradeMessage.isError ? 'bg-red-950/40 text-red-400 border-red-900/60' : 'bg-green-950/40 text-green-400 border-green-900/60'}`}>
                    {tradeMessage.text}
                  </div>
                )}

                {/* 주문 제출 버튼 */}
                <button
                  type="submit"
                  disabled={submitting}
                  className={`w-full py-2.5 rounded font-black text-[#070b19] text-xs tracking-wider transition-all active:scale-[0.98] cursor-pointer disabled:opacity-50 ${side === 'BUY' ? 'bg-[#ef4444] text-white hover:bg-red-600' : 'bg-[#3b82f6] text-white hover:bg-blue-600'}`}
                >
                  {submitting ? '주문 전송 중...' : `${side === 'BUY' ? '구매' : '판매'}하기`}
                </button>
              </form>
            </div>

            {/* 내 보유 주식 카드 (토스 WTS 스타일) */}
            <div className="bg-[#0e1529]/90 border border-[#1f2945] rounded-xl p-4 flex flex-col gap-3 backdrop-blur-md font-mono">
              <div className="flex items-center gap-2 border-b border-[#1f2945] pb-2">
                <span className="w-1.5 h-3 bg-cyan-400 rounded-full" />
                <span className="text-xs font-bold text-white">내 보유 현황</span>
              </div>

              {myHolding && myHolding.qty > 0 ? (
                <div className="flex flex-col gap-2.5 text-xs">
                  <div className="flex justify-between border-b border-[#1f2945]/30 py-1">
                    <span className="text-slate-400">보유 수량</span>
                    <span className="text-white font-bold">{myHolding.qty.toLocaleString()} 주</span>
                  </div>
                  <div className="flex justify-between border-b border-[#1f2945]/30 py-1">
                    <span className="text-slate-400">평균 단가</span>
                    <span className="text-white font-bold">
                      {assetType === 'STOCK' ? `₩${myHolding.avg_price.toLocaleString(undefined, {maximumFractionDigits:0})}` : `$${myHolding.avg_price.toLocaleString(undefined, {maximumFractionDigits:4})}`}
                    </span>
                  </div>
                  <div className="flex justify-between border-b border-[#1f2945]/30 py-1">
                    <span className="text-slate-400">현재 평가금</span>
                    <span className="text-white font-bold">
                      {assetType === 'STOCK' ? `₩${(myHolding.current_price * myHolding.qty).toLocaleString(undefined, {maximumFractionDigits:0})}` : `$${(myHolding.current_price * myHolding.qty).toLocaleString(undefined, {maximumFractionDigits:4})}`}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 font-bold">
                    <span className="text-slate-400">평가 손익</span>
                    <span className={myHolding.profit >= 0 ? 'text-[#ef4444]' : 'text-[#3b82f6]'}>
                      {myHolding.profit >= 0 ? '+' : ''}{myHolding.profit.toLocaleString()} ({myHolding.profit_rate.toFixed(2)}%)
                    </span>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-6 text-slate-500 text-xs">
                  <svg className="w-8 h-8 text-slate-600 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0a2 2 0 01-2 2H6a2 2 0 01-2-2m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-4M4 13h4" />
                  </svg>
                  <span>{symbol} 주식을 보유하고 있지 않아요</span>
                </div>
              )}
            </div>

          </div>

        </div>

      </div>
    </div>
  )
}
