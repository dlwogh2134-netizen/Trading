import { useEffect, useMemo, useState } from 'react'
import Header from '../components/Header.jsx'
import { supabase } from '../supabaseClient'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050'

const presets = {
  stock: {
    title: 'Toss 주식 데이터',
    assetType: 'STOCK',
    exchange: 'TOSS',
    symbols: '005930,NVDA',
    interval: '1d',
    count: 200,
    output: 'ml/data/raw/stock_candles.csv',
    sleepSeconds: 2,
    retry: 3,
    retryWaitSeconds: 60,
    append: true,
  },
  crypto: {
    title: 'Binance 코인 데이터',
    assetType: 'CRYPTO',
    exchange: 'BINANCE',
    symbols: 'BTCUSDT,ETHUSDT',
    interval: '1h',
    count: 500,
    output: 'ml/data/raw/crypto_candles.csv',
    sleepSeconds: 0.2,
    retry: 2,
    retryWaitSeconds: 10,
    append: true,
  },
}

function StatusPanel({ result, error, loading }) {
  if (loading) {
    return (
      <div className="rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm text-ai-cyan">
        학습용 캔들 CSV를 생성하는 중입니다.
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm leading-6 text-red-300">
        {error}
      </div>
    )
  }

  if (!result) {
    return (
      <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm leading-6 text-slate-400">
        수집 버튼을 누르면 결과 파일 경로와 생성 행 수가 여기에 표시됩니다.
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-4 text-sm leading-6 text-emerald-200">
      <p className="font-bold text-emerald-300">{result.message}</p>
      <dl className="mt-3 grid gap-2 md:grid-cols-2">
        <div>
          <dt className="text-xs text-slate-500">거래소</dt>
          <dd className="font-mono text-white">{result.data.exchange}</dd>
        </div>
        <div>
          <dt className="text-xs text-slate-500">생성 행 수</dt>
          <dd className="font-mono text-white">{result.data.row_count}</dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-xs text-slate-500">파일 경로</dt>
          <dd className="break-all font-mono text-white">{result.data.output}</dd>
        </div>
      </dl>
    </div>
  )
}

function formatMetric(value) {
  if (value === null || value === undefined || value === '') return '-'
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return String(value)
  return numberValue.toFixed(4)
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '-'
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return String(value)
  return `${(numberValue * 100).toFixed(1)}%`
}

function formatReturnPercent(value) {
  if (value === null || value === undefined || value === '') return '-'
  const numberValue = Number(value)
  if (Number.isNaN(numberValue)) return String(value)
  return `${(numberValue * 100).toFixed(2)}%`
}

function ModelResultCard({ title, result }) {
  const metrics = result?.metrics
  const riskMetrics = result?.risk_metrics
  const predictions = result?.predictions || []
  const upOnlyBacktest = result?.backtests?.up_only?.data
  const compositeBacktest = result?.backtests?.composite?.data

  return (
    <article className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">{result?.asset_type || '-'}</p>
          <h3 className="mt-1 text-sm font-bold uppercase tracking-wider text-white">{title}</h3>
        </div>
        <span className={`w-fit rounded border px-2 py-1 text-[10px] font-bold ${
          result?.updated ? 'border-emerald-500/40 text-emerald-300' : 'border-slate-700 text-slate-500'
        }`}>
          {result?.updated ? 'READY' : 'NO DATA'}
        </span>
      </div>

      {metrics ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg bg-[#0f172a] p-3">
            <p className="text-xs font-bold text-slate-400">구분력</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500">상승/비상승을 가르는 힘</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.roc_auc)}</p>
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3">
            <p className="text-xs font-bold text-slate-400">상위후보 적중도</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500">점수 높은 후보의 실제 적중</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.average_precision)}</p>
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3">
            <p className="text-xs font-bold text-slate-400">전체 정답률</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500">전체 0/1 판단 정답 비율</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.accuracy)}</p>
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3 sm:col-span-3">
            <p className="text-xs text-slate-500">학습/검증 구간</p>
            <p className="mt-1 break-words font-mono text-xs leading-5 text-slate-300">
              train {metrics.train_rows} rows: {metrics.train_start_date} ~ {metrics.train_end_date}
            </p>
            <p className="break-words font-mono text-xs leading-5 text-slate-300">
              valid {metrics.valid_rows} rows: {metrics.valid_start_date} ~ {metrics.valid_end_date}
            </p>
          </div>
        </div>
      ) : (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          아직 학습 결과 파일이 없습니다.
        </div>
      )}

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">하락 위험 모델</p>
          {riskMetrics ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              <div>
                <p className="text-[10px] text-slate-500">구분력</p>
                <p className="font-mono text-sm text-white">{formatMetric(riskMetrics.roc_auc)}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500">상위후보 적중도</p>
                <p className="font-mono text-sm text-white">{formatMetric(riskMetrics.average_precision)}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500">전체 정답률</p>
                <p className="font-mono text-sm text-white">{formatMetric(riskMetrics.accuracy)}</p>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-400">아직 risk_label 모델 결과가 없습니다.</p>
          )}
        </div>

        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">백테스트 요약</p>
          <div className="mt-3 grid gap-3">
            <div className="rounded-lg border border-slate-800 bg-black/10 p-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">상승 점수 기준</p>
              {upOnlyBacktest ? (
                <div className="mt-2 grid gap-1 text-xs text-slate-300">
                  <p>상위 {upOnlyBacktest.top_n}개 평균 수익률: <span className="font-mono text-white">{formatReturnPercent(upOnlyBacktest.top_avg_future_return)}</span></p>
                  <p>전체 평균 수익률: <span className="font-mono text-white">{formatReturnPercent(upOnlyBacktest.universe_avg_future_return)}</span></p>
                  <p>초과 수익률: <span className="font-mono text-ai-cyan">{formatReturnPercent(upOnlyBacktest.excess_return)}</span></p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-400">아직 단순 백테스트 결과가 없습니다.</p>
              )}
            </div>

            <div className="rounded-lg border border-slate-800 bg-black/10 p-3">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">복합 점수 기준</p>
              {compositeBacktest ? (
                <div className="mt-2 grid gap-1 text-xs text-slate-300">
                  <p>상위 {compositeBacktest.top_n}개 평균 수익률: <span className="font-mono text-white">{formatReturnPercent(compositeBacktest.top_avg_future_return)}</span></p>
                  <p>전체 평균 수익률: <span className="font-mono text-white">{formatReturnPercent(compositeBacktest.universe_avg_future_return)}</span></p>
                  <p>초과 수익률: <span className="font-mono text-ai-cyan">{formatReturnPercent(compositeBacktest.excess_return)}</span></p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-400">아직 복합 백테스트 결과가 없습니다.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5">
        <h4 className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">예측 순위</h4>
        {predictions.length ? (
          <div className="grid gap-2">
            {predictions.slice(0, 10).map((row) => (
              <div
                key={`${row.model_version}-${row.symbol}`}
                className="grid gap-3 rounded-lg border border-slate-800 bg-[#0f172a] p-3 sm:grid-cols-[1fr_auto_auto_auto]"
              >
                <div className="min-w-0">
                  <p className="break-words text-sm font-bold text-white">{row.display_name || row.symbol}</p>
                  <div className="mt-1 flex flex-wrap gap-1.5">
                    <span className="rounded border border-slate-700 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                      {row.symbol}
                    </span>
                    {row.market ? (
                      <span className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] text-slate-400">
                        {row.market}
                      </span>
                    ) : null}
                    {row.sector ? (
                      <span className="rounded border border-ai-cyan/30 px-1.5 py-0.5 text-[10px] text-ai-cyan">
                        {row.sector}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 break-words text-xs text-slate-500">{row.date}</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">상승 확률</p>
                  <p className="font-mono text-sm text-emerald-300">{formatPercent(row.up_probability)}</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">하락 위험</p>
                  <p className="font-mono text-sm text-amber-300">{formatPercent(row.risk_probability)}</p>
                </div>
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">복합 점수</p>
                  <p className="font-mono text-sm text-ai-cyan">{row.signal_score}</p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
            아직 예측 CSV가 없습니다.
          </div>
        )}
      </div>
    </article>
  )
}

export default function AdminMlData({ isLoggedIn, userEmail, handleLogout }) {
  const [mode, setMode] = useState('crypto')
  const [form, setForm] = useState(presets.crypto)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [modelResults, setModelResults] = useState(null)
  const [modelResultsLoading, setModelResultsLoading] = useState(false)
  const [modelResultsError, setModelResultsError] = useState('')

  const selectedPreset = useMemo(() => presets[mode], [mode])

  const applyPreset = (nextMode) => {
    setMode(nextMode)
    setForm(presets[nextMode])
    setResult(null)
    setError('')
  }

  const updateField = (key, value) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const loadModelResults = async () => {
    if (!isLoggedIn) return

    setModelResultsLoading(true)
    setModelResultsError('')

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setModelResultsError('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/model-results`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setModelResultsError(payload.message || '모델 결과 조회에 실패했습니다.')
        return
      }
      setModelResults(payload.data)
    } catch (requestError) {
      setModelResultsError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setModelResultsLoading(false)
    }
  }

  useEffect(() => {
    loadModelResults()
  }, [isLoggedIn])

  const handleExport = async () => {
    if (!isLoggedIn) {
      setError('로그인 후 사용할 수 있습니다.')
      return
    }

    setLoading(true)
    setError('')
    setResult(null)

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setError('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/export-candles`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          asset_type: form.assetType,
          exchange: form.exchange,
          symbols: form.symbols,
          interval: form.interval,
          count: Number(form.count),
          sleep_seconds: Number(form.sleepSeconds),
          retry: Number(form.retry),
          retry_wait_seconds: Number(form.retryWaitSeconds),
          append: form.append,
        }),
      })

      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setError(payload.message || 'CSV 생성에 실패했습니다.')
        return
      }

      setResult(payload)
      loadModelResults()
    } catch (requestError) {
      setError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-obsidian-bg px-6 py-8 text-[#e2e2ec]">
      <Header isLoggedIn={isLoggedIn} userEmail={userEmail} handleLogout={handleLogout} />

      <main className="mx-auto flex max-w-7xl flex-col gap-6">
        <section className="ai-glass rounded-lg p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Admin ML Data</p>
              <h2 className="mt-2 text-2xl font-bold text-white">학습 데이터 수집 관리</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                로그인한 사용자의 저장된 API Key를 백엔드에서만 복호화해 학습용 캔들 CSV를 생성합니다.
              </p>
            </div>

            <div className="flex rounded-lg border border-slate-700 bg-[#0f172a] p-1">
              {Object.entries(presets).map(([key, preset]) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => applyPreset(key)}
                  className={`rounded-md px-4 py-2 text-xs font-bold transition ${
                    mode === key ? 'bg-ai-cyan text-[#07111f]' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {preset.title}
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
            <div className="mb-5 flex items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-white">{selectedPreset.title}</h3>
                <p className="mt-1 text-xs text-slate-500">{form.output}</p>
              </div>
              <span className="rounded border border-ai-cyan/40 px-2 py-1 text-[10px] font-bold text-ai-cyan">
                {form.exchange}
              </span>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">심볼</span>
                <input
                  value={form.symbols}
                  onChange={(event) => updateField('symbols', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">봉 간격</span>
                <input
                  value={form.interval}
                  onChange={(event) => updateField('interval', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">수집 개수</span>
                <input
                  type="number"
                  min="1"
                  max="1000"
                  value={form.count}
                  onChange={(event) => updateField('count', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">자산 구분</span>
                <input
                  value={`${form.assetType} / ${form.exchange}`}
                  readOnly
                  className="rounded border border-slate-800 bg-[#0f172a]/70 px-3 py-2 text-sm text-slate-400 outline-none"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">요청 간 대기초</span>
                <input
                  type="number"
                  min="0"
                  step="0.1"
                  value={form.sleepSeconds}
                  onChange={(event) => updateField('sleepSeconds', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">429 재시도 횟수</span>
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={form.retry}
                  onChange={(event) => updateField('retry', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">재시도 대기초</span>
                <input
                  type="number"
                  min="1"
                  value={form.retryWaitSeconds}
                  onChange={(event) => updateField('retryWaitSeconds', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                />
              </label>

              <label className="flex items-center gap-3 rounded border border-slate-800 bg-[#0f172a]/70 px-3 py-2">
                <input
                  type="checkbox"
                  checked={form.append}
                  onChange={(event) => updateField('append', event.target.checked)}
                  className="h-4 w-4 accent-ai-cyan"
                />
                <span className="text-sm font-bold text-slate-300">기존 CSV에 병합 저장</span>
              </label>
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleExport}
                disabled={loading}
                className="rounded bg-ai-cyan px-5 py-2.5 text-sm font-bold text-[#07111f] transition hover:bg-ai-cyan/80 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? 'CSV 생성 중' : 'CSV 생성'}
              </button>
              <p className="text-xs leading-5 text-slate-500">
                Toss는 요청 제한을 피하기 위해 종목 사이 대기와 429 재시도를 사용합니다.
              </p>
            </div>
          </div>

          <div className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
            <h3 className="mb-4 text-sm font-bold uppercase tracking-wider text-white">실행 결과</h3>
            <StatusPanel result={result} error={error} loading={loading} />
          </div>
        </section>

        <section className="flex flex-col gap-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Model Results</p>
              <h2 className="mt-1 text-xl font-bold text-white">최근 학습 결과와 예측 순위</h2>
            </div>
            <button
              type="button"
              onClick={loadModelResults}
              disabled={modelResultsLoading || !isLoggedIn}
              className="w-full rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
            >
              {modelResultsLoading ? '불러오는 중' : '결과 새로고침'}
            </button>
          </div>

          {modelResultsError ? (
            <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm leading-6 text-red-300">
              {modelResultsError}
            </div>
          ) : null}

          <div className="grid gap-6 xl:grid-cols-2">
            <ModelResultCard title="주식 모델" result={modelResults?.stock} />
            <ModelResultCard title="코인 모델" result={modelResults?.crypto} />
          </div>
        </section>
      </main>
    </div>
  )
}
