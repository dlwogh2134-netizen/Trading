import { useEffect, useEffectEvent, useMemo, useState } from 'react'
import Header from '../components/Header.jsx'
import { supabase } from '../supabaseClient'
import AdminInquiries from './AdminInquiries.jsx'
import AdminUsers from './AdminUsers.jsx'
import AdminSymbolReconciliation from './AdminSymbolReconciliation.jsx'
import {
  ActiveSignalPanel,
  ExecutionChecklistPanel,
  JobHistoryPanel,
  JobLogModal,
  ModelResultCard,
  ModelSwitchPanel,
  OperationalTrustPanel,
  ReadinessPanel,
  RegistryPanel,
  ReportHistoryPanel,
  ReportPanel,
  ServingAuditPanel,
  StatusPanel,
  V8OptunaPanel,
} from './adminMlDataPanels.jsx'
import {
  formatPath,
  legacyAutomationPresets,
  operationalAutomationPresets,
  presets,
  summarizeFailedChecks,
  trainingPresets,
  tuningPresets,
  v8TuningPresets,
} from './adminMlDataModel.js'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050'

export default function AdminMlData({ isLoggedIn, userEmail, handleLogout, hideHeader = false }) {
  const [adminTab, setAdminTab] = useState('ml')
  const [mode, setMode] = useState('crypto')
  const [form, setForm] = useState(presets.crypto)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [modelResults, setModelResults] = useState(null)
  const [modelResultsLoading, setModelResultsLoading] = useState(false)
  const [modelResultsError, setModelResultsError] = useState('')
  const [jobHistory, setJobHistory] = useState([])
  const [jobHistoryLoading, setJobHistoryLoading] = useState(false)
  const [jobHistoryError, setJobHistoryError] = useState('')
  const [registryRows, setRegistryRows] = useState({ stock: [], crypto: [] })
  const [promotionChecks, setPromotionChecks] = useState({})
  const [promotionChecksLoading, setPromotionChecksLoading] = useState(false)
  const [registryLoading, setRegistryLoading] = useState(false)
  const [registryError, setRegistryError] = useState('')
  const [registryMessage, setRegistryMessage] = useState('')
  const [activatingRegistryKey, setActivatingRegistryKey] = useState('')
  const [servingAudit, setServingAudit] = useState(null)
  const [servingAuditLoading, setServingAuditLoading] = useState(false)
  const [servingAuditError, setServingAuditError] = useState('')
  const [readiness, setReadiness] = useState(null)
  const [readinessLoading, setReadinessLoading] = useState(false)
  const [readinessError, setReadinessError] = useState('')
  const [reportLoading, setReportLoading] = useState(false)
  const [reportMessage, setReportMessage] = useState('')
  const [reportHistory, setReportHistory] = useState([])
  const [reportHistoryLoading, setReportHistoryLoading] = useState(false)
  const [reportHistoryError, setReportHistoryError] = useState('')
  const [activeSignals, setActiveSignals] = useState({ stock: null, crypto: null })
  const [activeSignalsLoading, setActiveSignalsLoading] = useState({ stock: false, crypto: false })
  const [activeSignalsError, setActiveSignalsError] = useState({ stock: '', crypto: '' })
  const [trainingLoadingKey, setTrainingLoadingKey] = useState('')
  const [trainingMessage, setTrainingMessage] = useState('')
  const [automationLoadingKey, setAutomationLoadingKey] = useState('')
  const [automationMessage, setAutomationMessage] = useState('')
  const [tuneTrials, setTuneTrials] = useState(20)
  const [tuneUpdateConfig, setTuneUpdateConfig] = useState(true)
  const [tuningLoadingKey, setTuningLoadingKey] = useState('')
  const [tuningMessage, setTuningMessage] = useState('')
  const [selectedLogJob, setSelectedLogJob] = useState(null)
  const [showAdvancedTools, setShowAdvancedTools] = useState(false)

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

  const loadJobHistory = async () => {
    if (!isLoggedIn) return

    setJobHistoryLoading(true)
    setJobHistoryError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setJobHistoryError('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/jobs?limit=20`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setJobHistoryError(payload.message || '작업 이력 조회에 실패했습니다.')
        return
      }
      setJobHistory(payload.data.jobs || [])
    } catch (requestError) {
      setJobHistoryError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setJobHistoryLoading(false)
    }
  }

  const loadRegistry = async () => {
    if (!isLoggedIn) return

    setRegistryLoading(true)
    setRegistryError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setRegistryError('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/registry`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setRegistryError(payload.message || '레지스트리 조회에 실패했습니다.')
        return
      }
      const nextRows = payload.data || { stock: [], crypto: [] }
      setRegistryRows(nextRows)
      await loadPromotionChecks(nextRows, session.access_token)
    } catch (requestError) {
      setRegistryError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setRegistryLoading(false)
    }
  }

  const loadPromotionChecks = async (rowsByAsset, accessToken) => {
    const allRows = [...(rowsByAsset?.stock || []), ...(rowsByAsset?.crypto || [])]
    if (!allRows.length) {
      setPromotionChecks({})
      return
    }

    setPromotionChecksLoading(true)
    try {
      let token = accessToken
      if (!token) {
        const { data: { session } } = await supabase.auth.getSession()
        token = session?.access_token
      }

      if (!token) {
        setPromotionChecks({})
        return
      }

      const entries = await Promise.all(
        allRows.map(async (row) => {
          try {
            const params = new URLSearchParams({
              asset_type: row.asset_type,
              model_version: row.model_version,
            })
            const response = await fetch(`${API_BASE_URL}/api/ml/registry/promotion-check?${params.toString()}`, {
              method: 'GET',
              headers: {
                'Authorization': `Bearer ${token}`,
              },
            })
            const payload = await response.json()
            if (!response.ok || !payload.success) {
              return [`${row.asset_type}:${row.model_version}`, null]
            }
            return [`${row.asset_type}:${row.model_version}`, payload.data]
          } catch {
            return [`${row.asset_type}:${row.model_version}`, null]
          }
        }),
      )

      setPromotionChecks(Object.fromEntries(entries.filter((entry) => entry[1])))
    } finally {
      setPromotionChecksLoading(false)
    }
  }

  const loadServingAudit = async () => {
    if (!isLoggedIn) return

    setServingAuditLoading(true)
    setServingAuditError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setServingAuditError('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/serving-audit`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setServingAuditError(payload.message || '서빙 감사 조회에 실패했습니다.')
        return
      }
      setServingAudit(payload.data)
    } catch (requestError) {
      setServingAuditError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setServingAuditLoading(false)
    }
  }

  const loadActiveSignals = async (assetType) => {
    if (!isLoggedIn) return

    const assetKey = assetType === 'STOCK' ? 'stock' : 'crypto'
    setActiveSignalsLoading((prev) => ({ ...prev, [assetKey]: true }))
    setActiveSignalsError((prev) => ({ ...prev, [assetKey]: '' }))

    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setActiveSignalsError((prev) => ({ ...prev, [assetKey]: '로그인 세션이 만료되었습니다.' }))
        return
      }

      const params = new URLSearchParams({
        asset_type: assetType,
        limit: '8',
      })
      const response = await fetch(`${API_BASE_URL}/api/ml/predictions/active?${params.toString()}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setActiveSignals((prev) => ({ ...prev, [assetKey]: null }))
        setActiveSignalsError((prev) => ({
          ...prev,
          [assetKey]: response.status === 404
            ? '현재 안전 기준을 통과한 활성 신호가 없어 차단된 상태입니다.'
            : (payload.message || '활성 신호 조회에 실패했습니다.'),
        }))
        return
      }

      setActiveSignals((prev) => ({ ...prev, [assetKey]: payload.data }))
    } catch (requestError) {
      setActiveSignalsError((prev) => ({ ...prev, [assetKey]: `서버 통신 실패: ${requestError.message}` }))
    } finally {
      setActiveSignalsLoading((prev) => ({ ...prev, [assetKey]: false }))
    }
  }

  const loadReadiness = async () => {
    if (!isLoggedIn) return

    setReadinessLoading(true)
    setReadinessError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setReadinessError('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/readiness`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setReadinessError(payload.message || '운영 준비 상태 조회에 실패했습니다.')
        return
      }
      setReadiness(payload.data)
    } catch (requestError) {
      setReadinessError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setReadinessLoading(false)
    }
  }

  const handleGenerateReport = async () => {
    if (!isLoggedIn) {
      setReportMessage('로그인 후 사용할 수 있습니다.')
      return
    }

    setReportLoading(true)
    setReportMessage('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setReportMessage('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/report`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({}),
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setReportMessage(payload.message || '리포트 생성에 실패했습니다.')
        return
      }
      setReportMessage(`${payload.message} (${payload.data.output})`)
      await loadReportHistory()
    } catch (requestError) {
      setReportMessage(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setReportLoading(false)
    }
  }

  const loadReportHistory = async () => {
    if (!isLoggedIn) return

    setReportHistoryLoading(true)
    setReportHistoryError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setReportHistoryError('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/reports?limit=10`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
        },
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setReportHistoryError(payload.message || '리포트 목록 조회에 실패했습니다.')
        return
      }
      setReportHistory(payload.data?.reports || [])
    } catch (requestError) {
      setReportHistoryError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setReportHistoryLoading(false)
    }
  }

  const handleActivateRegistry = async (row) => {
    if (!isLoggedIn) {
      setRegistryMessage('로그인 후 사용할 수 있습니다.')
      return
    }

    const activeKey = `${row.asset_type}:${row.model_version}`
    setActivatingRegistryKey(activeKey)
    setRegistryMessage('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setRegistryMessage('로그인 세션이 만료되었습니다.')
        return
      }

      let response = await fetch(`${API_BASE_URL}/api/ml/registry/activate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          asset_type: row.asset_type,
          model_version: row.model_version,
          force: false,
        }),
      })
      let payload = await response.json()

      // 승격 기준 미달로 차단된 경우 (409)
      if (response.status === 409 && payload.success === false) {
        const failedSummary = summarizeFailedChecks(payload.data, 4)
        const confirmMsg = `${payload.message || '승격 기준 미달로 차단되었습니다.'}\n\n[실패 항목]\n${failedSummary.join('\n')}\n\n⚠️ 위험을 인지하고 강제로 서비스에 반영하시겠습니까?`
        
        if (window.confirm(confirmMsg)) {
          response = await fetch(`${API_BASE_URL}/api/ml/registry/activate`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${session.access_token}`,
            },
            body: JSON.stringify({
              asset_type: row.asset_type,
              model_version: row.model_version,
              force: true,
            }),
          })
          payload = await response.json()
        } else {
          return
        }
      }

      if (!response.ok || !payload.success) {
        const failedSummary = summarizeFailedChecks(payload.data, 4)
        setRegistryMessage(
          failedSummary.length
            ? `${payload.message || '서비스 반영에 실패했습니다.'}\n${failedSummary.join('\n')}`
            : (payload.message || '서비스 반영에 실패했습니다.')
        )
        return
      }

      setRegistryMessage(payload.message || '서비스 반영이 완료되었습니다.')
      await loadRegistry()
      await loadModelResults()
      await loadServingAudit()
      await loadActiveSignals(row.asset_type)
      await loadReadiness()
    } catch (requestError) {
      setRegistryMessage(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setActivatingRegistryKey('')
    }
  }

  const refreshAdminPanels = useEffectEvent(() => {
    loadModelResults()
    loadJobHistory()
    loadRegistry()
    loadServingAudit()
    loadReadiness()
    loadReportHistory()
    loadActiveSignals('STOCK')
    loadActiveSignals('CRYPTO')
  })

  useEffect(() => {
    if (!isLoggedIn) return
    const timer = window.setTimeout(() => {
      refreshAdminPanels()
    }, 0)

    return () => window.clearTimeout(timer)
  }, [isLoggedIn])

  const stockActiveGuardReport = activeSignals.stock?.model_version
    ? promotionChecks[`STOCK:${activeSignals.stock.model_version}`]
    : null
  const cryptoActiveGuardReport = activeSignals.crypto?.model_version
    ? promotionChecks[`CRYPTO:${activeSignals.crypto.model_version}`]
    : null

  const handleRunTraining = async (preset) => {
    if (!isLoggedIn) {
      setTrainingMessage('로그인 후 사용할 수 있습니다.')
      return
    }

    setTrainingLoadingKey(preset.key)
    setTrainingMessage('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setTrainingMessage('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/jobs/train`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          label: preset.label,
          config: preset.config,
          risk_config: preset.riskConfig,
          summary_output: preset.summaryOutput,
          skip_build_features: false,
        }),
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setTrainingMessage(payload.message || '학습 실행에 실패했습니다.')
        return
      }

      const reportPath = payload?.data?.report?.timestamped_output || payload?.data?.report?.latest_output
      setTrainingMessage(
        reportPath
          ? `${preset.label} 작업이 완료되었습니다. 실험 리포트도 갱신되었습니다: ${formatPath(reportPath)}`
          : `${preset.label} 작업이 완료되었습니다.`
      )
      await loadModelResults()
      await loadJobHistory()
      await loadRegistry()
      await loadServingAudit()
      await loadActiveSignals(preset.config.includes('crypto') ? 'CRYPTO' : 'STOCK')
      await loadReadiness()
      await loadReportHistory()
    } catch (requestError) {
      setTrainingMessage(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setTrainingLoadingKey('')
    }
  }

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
          preset: form.preset,
          interval: form.interval,
          count: Number(form.count),
          sleep_seconds: Number(form.sleepSeconds),
          retry: Number(form.retry),
          retry_wait_seconds: Number(form.retryWaitSeconds),
          include_macro: form.includeMacro,
          chunk_size: Number(form.chunkSize || 0),
          chunk_index: Number(form.chunkIndex || 1),
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
      loadRegistry()
      loadServingAudit()
      loadActiveSignals(form.assetType)
      loadReadiness()
    } catch (requestError) {
      setError(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleRunFullAutomation = async (preset) => {
    if (!isLoggedIn) {
      setAutomationMessage('로그인 후 사용할 수 있습니다.')
      return
    }

    setAutomationLoadingKey(preset.key)
    setAutomationMessage('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setAutomationMessage('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/jobs/full-run`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          preset_key: preset.key,
        }),
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setAutomationMessage(payload.message || '자동 수집+학습 실행에 실패했습니다.')
        return
      }

      const reportPath = payload?.data?.report?.timestamped_output || payload?.data?.report?.latest_output
      setAutomationMessage(
        reportPath
          ? `${preset.label} 작업이 완료되었습니다. 실험 리포트도 갱신되었습니다: ${formatPath(reportPath)}`
          : `${preset.label} 작업이 완료되었습니다.`
      )
      await loadModelResults()
      await loadJobHistory()
      await loadRegistry()
      await loadServingAudit()
      // 국내/해외 분리 모델도 현재 registry asset_type은 STOCK으로 동기화합니다.
      await loadActiveSignals(preset.key.includes('crypto') ? 'CRYPTO' : 'STOCK')
      await loadReadiness()
      await loadReportHistory()
    } catch (requestError) {
      setAutomationMessage(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setAutomationLoadingKey('')
    }
  }

  const handleRunTuning = async (preset) => {
    if (!isLoggedIn) {
      setTuningMessage('로그인 후 사용할 수 있습니다.')
      return
    }

    setTuningLoadingKey(preset.key)
    setTuningMessage('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      if (!session) {
        setTuningMessage('로그인 세션이 만료되었습니다.')
        return
      }

      const response = await fetch(`${API_BASE_URL}/api/ml/jobs/tune`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({
          config: preset.config,
          trials: Number(tuneTrials),
          update_config: tuneUpdateConfig,
        }),
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        setTuningMessage(payload.message || '튜닝 실행에 실패했습니다.')
        return
      }

      // Optuna 로그가 payload.data.stdout에 포함되어 있음
      setTuningMessage(
        payload.data?.success
          ? `${preset.label} 작업이 완료되었습니다. (작업 ID: ${payload.data.job_id})`
          : `${preset.label} 작업이 완료되었으나 실패 사유가 있습니다.`
      )
      await loadModelResults()
      await loadJobHistory()
      await loadRegistry()
      await loadServingAudit()
      await loadActiveSignals(preset.config.includes('crypto') ? 'CRYPTO' : 'STOCK')
      await loadReadiness()
      await loadReportHistory()
    } catch (requestError) {
      setTuningMessage(`서버 통신 실패: ${requestError.message}`)
    } finally {
      setTuningLoadingKey('')
    }
  }

  return (
    <div className={hideHeader ? 'text-[#e2e2ec]' : 'min-h-screen bg-obsidian-bg px-6 py-8 text-[#e2e2ec]'}>
      {!hideHeader && (
        <Header isLoggedIn={isLoggedIn} userEmail={userEmail} handleLogout={handleLogout} />
      )}

      <main className="mx-auto flex max-w-7xl flex-col gap-6">
        {/* 관리자 내부 탭 */}
        <div className="flex overflow-x-auto border-b border-slate-800">
          <button
            type="button"
            onClick={() => setAdminTab('ml')}
            className={`shrink-0 px-4 py-3 text-sm font-bold border-b-2 transition sm:px-6 ${
              adminTab === 'ml'
                ? 'border-ai-cyan text-white bg-ai-cyan/5'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            ML 운영 콘솔
          </button>
          <button
            type="button"
            onClick={() => setAdminTab('inquiries')}
            className={`shrink-0 px-4 py-3 text-sm font-bold border-b-2 transition sm:px-6 ${
              adminTab === 'inquiries'
                ? 'border-ai-cyan text-white bg-ai-cyan/5'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            사용자 문의 관리
          </button>
          <button
            type="button"
            onClick={() => setAdminTab('users')}
            className={`shrink-0 px-4 py-3 text-sm font-bold border-b-2 transition sm:px-6 ${
              adminTab === 'users'
                ? 'border-ai-cyan text-white bg-ai-cyan/5'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            유저 관리
          </button>
          <button
            type="button"
            onClick={() => setAdminTab('symbols')}
            className={`shrink-0 px-4 py-3 text-sm font-bold border-b-2 transition sm:px-6 ${
              adminTab === 'symbols'
                ? 'border-ai-cyan text-white bg-ai-cyan/5'
                : 'border-transparent text-slate-400 hover:text-white'
            }`}
          >
            종목 정리
          </button>
        </div>

        {adminTab === 'ml' && (
          <>
            <section className="ai-glass rounded-lg p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">ML Operations</p>
              <h2 className="mt-2 text-2xl font-bold text-white">ML 운영 콘솔</h2>
              <p className="mt-2 text-sm leading-6 text-slate-400">
                기본 화면은 운영 상태, 서빙 감사, 활성 신호, v8 자동화 실행, 최근 작업 이력만 표시합니다.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowAdvancedTools((prev) => !prev)}
              className="w-full rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white sm:w-auto"
            >
              {showAdvancedTools ? '고급 도구 접기' : '고급 도구 열기'}
            </button>
          </div>
        </section>

        <ReadinessPanel
          data={readiness}
          loading={readinessLoading}
          error={readinessError}
          onRefresh={loadReadiness}
        />

        <ServingAuditPanel
          data={servingAudit}
          loading={servingAuditLoading}
          error={servingAuditError}
          onRefresh={loadServingAudit}
        />

        <ModelSwitchPanel
          data={servingAudit}
          rowsByAsset={registryRows}
          promotionChecks={promotionChecks}
          loading={servingAuditLoading || registryLoading || promotionChecksLoading}
          onActivate={handleActivateRegistry}
          activatingKey={activatingRegistryKey}
        />

        <OperationalTrustPanel
          data={servingAudit}
          loading={servingAuditLoading}
          error={servingAuditError}
        />

        <section className="grid gap-6 grid-cols-1">
          <ActiveSignalPanel
            title="주식 활성 신호"
            data={activeSignals.stock}
            loading={activeSignalsLoading.stock}
            error={activeSignalsError.stock}
            guardReport={stockActiveGuardReport}
            onRefresh={() => loadActiveSignals('STOCK')}
          />
          <ActiveSignalPanel
            title="코인 활성 신호"
            data={activeSignals.crypto}
            loading={activeSignalsLoading.crypto}
            error={activeSignalsError.crypto}
            guardReport={cryptoActiveGuardReport}
            onRefresh={() => loadActiveSignals('CRYPTO')}
          />
        </section>

        <section className="rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Full Automation</p>
              <h2 className="mt-1 text-xl font-bold text-white">자동 수집 + 학습</h2>
              <p className="mt-2 text-xs leading-5 text-slate-400">
                운영 기본 버튼은 현재 후보군인 국내주식, 해외주식, 코인 자동학습만 노출합니다. 레거시 모델과 HPO는 고급 도구에서 실행합니다.
              </p>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {operationalAutomationPresets.map((preset) => (
              <button
                key={preset.key}
                type="button"
                onClick={() => handleRunFullAutomation(preset)}
                disabled={automationLoadingKey === preset.key || !isLoggedIn}
                className="rounded border border-ai-cyan/40 bg-[#0f172a] px-4 py-3 text-left transition hover:border-ai-cyan hover:bg-ai-cyan/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <p className="flex items-center gap-2 text-sm font-bold text-white">
                  {automationLoadingKey === preset.key ? '실행 중...' : preset.label}
                  <span className="rounded bg-ai-cyan px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#0a0f1e]">
                    {preset.version}
                  </span>
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-400">{preset.summary}</p>
              </button>
            ))}
          </div>

          {automationMessage ? (
            <div className="mt-4 rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm text-ai-cyan">
              {automationMessage}
            </div>
          ) : null}
        </section>

        {showAdvancedTools ? (
        <>
        <V8OptunaPanel
          presets={v8TuningPresets}
          trials={tuneTrials}
          updateConfig={tuneUpdateConfig}
          loadingKey={tuningLoadingKey}
          message={tuningMessage}
          isLoggedIn={isLoggedIn}
          onTrialsChange={setTuneTrials}
          onUpdateConfigChange={setTuneUpdateConfig}
          onRun={handleRunTuning}
        />

        <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Advanced Data Tools</p>
              <h2 className="mt-1 text-lg font-bold text-white">학습 데이터 수동 수집</h2>
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
                  placeholder="직접 입력 시 005930,NVDA 또는 BTCUSDT,ETHUSDT"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">프리셋</span>
                <input
                  value={form.preset || ''}
                  onChange={(event) => updateField('preset', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                  placeholder="stock_core_90 / crypto_core_30"
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

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">청크 크기</span>
                <input
                  type="number"
                  min="0"
                  value={form.chunkSize}
                  onChange={(event) => updateField('chunkSize', event.target.value)}
                  className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-sm text-white outline-none transition focus:border-ai-cyan"
                />
              </label>

              <label className="flex flex-col gap-2">
                <span className="text-xs font-bold text-slate-400">청크 번호</span>
                <input
                  type="number"
                  min="1"
                  value={form.chunkIndex}
                  onChange={(event) => updateField('chunkIndex', event.target.value)}
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

              <label className="flex items-center gap-3 rounded border border-slate-800 bg-[#0f172a]/70 px-3 py-2">
                <input
                  type="checkbox"
                  checked={form.includeMacro}
                  onChange={(event) => updateField('includeMacro', event.target.checked)}
                  className="h-4 w-4 accent-ai-cyan"
                />
                <span className="text-sm font-bold text-slate-300">매크로 지표도 함께 갱신</span>
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
        </>
        ) : null}

        {showAdvancedTools ? (
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

          <div className="grid gap-6 grid-cols-1">
            <ModelResultCard title="주식 모델" result={modelResults?.stock} />
            <ModelResultCard title="코인 모델" result={modelResults?.crypto} />
          </div>
        </section>
        ) : null}

        {showAdvancedTools ? (
        <>
        <section className="grid gap-6 grid-cols-1">
          <RegistryPanel
            title="주식 레지스트리 상태"
            rows={registryRows.stock}
            loading={registryLoading}
            error={registryError}
            onActivate={handleActivateRegistry}
            activatingKey={activatingRegistryKey}
            promotionChecks={promotionChecks}
            promotionChecksLoading={promotionChecksLoading}
          />
          <RegistryPanel
            title="코인 레지스트리 상태"
            rows={registryRows.crypto}
            loading={registryLoading}
            error={registryError}
            onActivate={handleActivateRegistry}
            activatingKey={activatingRegistryKey}
            promotionChecks={promotionChecks}
            promotionChecksLoading={promotionChecksLoading}
          />
        </section>

        {registryMessage ? (
          <section className="rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm whitespace-pre-line text-ai-cyan">
            {registryMessage}
          </section>
        ) : null}
        </>
        ) : null}

        {showAdvancedTools ? <ExecutionChecklistPanel /> : null}

        {showAdvancedTools ? (
        <ReportPanel
          loading={reportLoading}
          message={reportMessage}
          onGenerate={handleGenerateReport}
        />
        ) : null}

        {showAdvancedTools ? (
        <ReportHistoryPanel
          reports={reportHistory}
          loading={reportHistoryLoading}
          error={reportHistoryError}
          onRefresh={loadReportHistory}
        />
        ) : null}

        <section className="grid gap-6 grid-cols-1">
          {showAdvancedTools ? (
          <div className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Training Jobs</p>
                <h2 className="mt-1 text-xl font-bold text-white">백엔드 학습 실행</h2>
              </div>
            </div>

            <div className="mt-4 grid gap-3">
              {trainingPresets.map((preset) => (
                <button
                  key={preset.key}
                  type="button"
                  onClick={() => handleRunTraining(preset)}
                  disabled={trainingLoadingKey === preset.key || !isLoggedIn}
                  className="rounded border border-slate-700 bg-[#0f172a] px-4 py-3 text-left transition hover:border-ai-cyan disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <p className="text-sm font-bold text-white">
                    {trainingLoadingKey === preset.key ? '실행 중...' : preset.label}
                  </p>
                  <p className="mt-1 break-all font-mono text-[10px] text-slate-500">{formatPath(preset.config)}</p>
                </button>
              ))}
            </div>

            <div className="mt-4 rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-xs leading-6 text-slate-400">
              이 버튼은 백엔드에서 `run_pipeline_bundle.py`를 실행하고, 작업 이력을 `ml/data/ops/job_history.json`에 남깁니다.
            </div>

            {trainingMessage ? (
              <div className="mt-4 rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm text-ai-cyan">
                {trainingMessage}
              </div>
            ) : null}

            <div className="mt-6 border-t border-slate-800 pt-6">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Full Automation</p>
              <h3 className="mt-1 text-sm font-bold text-white">백엔드 자동 수집 + 학습</h3>
              <div className="mt-4 grid gap-3">
                {legacyAutomationPresets.map((preset) => (
                  <button
                    key={preset.key}
                    type="button"
                    onClick={() => handleRunFullAutomation(preset)}
                    disabled={automationLoadingKey === preset.key || !isLoggedIn}
                    className={[
                      'rounded border px-4 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-50',
                      preset.isNew
                        ? 'border-ai-cyan/40 bg-ai-cyan/5 hover:border-ai-cyan hover:bg-ai-cyan/10'
                        : 'border-slate-700 bg-[#0f172a] hover:border-ai-cyan',
                    ].join(' ')}
                  >
                    <p className="flex items-center gap-2 text-sm font-bold text-white">
                      {automationLoadingKey === preset.key ? '실행 중...' : preset.label}
                      {preset.isNew && (
                        <span className="rounded bg-ai-cyan px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#0a0f1e]">
                          NEW
                        </span>
                      )}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">{preset.summary}</p>
                  </button>
                ))}
              </div>

              <div className="mt-4 rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-xs leading-6 text-slate-400">
                이 버튼은 데이터셋 수집과 `run_pipeline_bundle.py` 실행을 순차적으로 수행하고, 결과를 작업 이력과 모델 레지스트리에 반영합니다.
              </div>

              {automationMessage ? (
                <div className="mt-4 rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm text-ai-cyan">
                  {automationMessage}
                </div>
              ) : null}
            </div>

            <div className="mt-6 border-t border-slate-800 pt-6">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Optuna HPO Tuning</p>
              <h3 className="mt-1 text-sm font-bold text-white">Optuna 하이퍼파라미터 최적화 (HPO)</h3>
              
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                <label className="flex flex-col gap-1.5 text-xs">
                  <span className="font-bold text-slate-400">탐색 시도 횟수 (Trials)</span>
                  <input
                    type="number"
                    min="5"
                    max="100"
                    value={tuneTrials}
                    onChange={(e) => setTuneTrials(Number(e.target.value))}
                    className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 text-white outline-none focus:border-ai-cyan font-mono"
                  />
                </label>
                
                <label className="flex items-center gap-2 rounded border border-slate-800 bg-[#0f172a]/70 px-3 py-2">
                  <input
                    type="checkbox"
                    checked={tuneUpdateConfig}
                    onChange={(e) => setTuneUpdateConfig(e.target.checked)}
                    className="h-4 w-4 accent-ai-cyan"
                  />
                  <span className="font-bold text-slate-300">최적 파라미터 자동 저장 (YAML)</span>
                </label>
              </div>

              <div className="mt-4 grid gap-3">
                {tuningPresets.map((preset) => (
                  <button
                    key={preset.key}
                    type="button"
                    onClick={() => handleRunTuning(preset)}
                    disabled={tuningLoadingKey === preset.key || !isLoggedIn}
                    className={[
                      'rounded border px-4 py-3 text-left transition disabled:cursor-not-allowed disabled:opacity-50',
                      preset.isNew
                        ? 'border-ai-cyan/40 bg-ai-cyan/5 hover:border-ai-cyan hover:bg-ai-cyan/10'
                        : 'border-slate-700 bg-[#0f172a] hover:border-ai-cyan',
                    ].join(' ')}
                  >
                    <p className="flex items-center gap-2 text-sm font-bold text-white">
                      {tuningLoadingKey === preset.key ? '튜닝 진행 중...' : preset.label}
                      {preset.isNew && (
                        <span className="rounded bg-ai-cyan px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-[#0a0f1e]">
                          NEW
                        </span>
                      )}
                    </p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">{preset.summary}</p>
                    <p className="mt-1 font-mono text-[9px] text-slate-500 break-all">{formatPath(preset.config)}</p>
                  </button>
                ))}
              </div>

              {tuningMessage ? (
                <div className="mt-4 rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm text-ai-cyan">
                  {tuningMessage}
                </div>
              ) : null}
            </div>
          </div>
          ) : null}

          <div className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Job History</p>
                <h2 className="mt-1 text-xl font-bold text-white">데이터셋/학습 작업 이력</h2>
              </div>
              <button
                type="button"
                onClick={loadJobHistory}
                disabled={jobHistoryLoading || !isLoggedIn}
                className="w-full rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
              >
                {jobHistoryLoading ? '불러오는 중' : '작업 이력 새로고침'}
              </button>
            </div>

            <JobHistoryPanel
              jobs={jobHistory}
              loading={jobHistoryLoading}
              error={jobHistoryError}
              onShowLog={setSelectedLogJob}
            />
          </div>
        </section>
        </>
        )}

        {adminTab === 'inquiries' && (
          <AdminInquiries
            isLoggedIn={isLoggedIn}
            userEmail={userEmail}
            handleLogout={handleLogout}
            hideHeader
          />
        )}

        {adminTab === 'users' && (
          <AdminUsers
            isLoggedIn={isLoggedIn}
            userEmail={userEmail}
            handleLogout={handleLogout}
            hideHeader
          />
        )}

        {adminTab === 'symbols' && (
          <AdminSymbolReconciliation />
        )}
      </main>

      <JobLogModal
        job={selectedLogJob}
        onClose={() => setSelectedLogJob(null)}
      />
    </div>
  )
}
