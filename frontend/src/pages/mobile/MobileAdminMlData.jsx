import { useEffect, useEffectEvent, useMemo, useState } from 'react'
import Header from '../../components/Header.jsx'
import { supabase } from '../../supabaseClient'
import MobileAdminInquiries from './MobileAdminInquiries.jsx'
import AdminSymbolReconciliation from '../AdminSymbolReconciliation.jsx'
import { ActiveSignalPanel, AuditBadge, GuardSummary, JobLogModal, ModelSwitchPanel, RegistryPanel, ServingAuditPanel, StatusPanel, VersionDeltaPanel } from '../adminMlDataPanels.jsx'
import {
  buildQualityDetail,
  findGuardCheck,
  formatMetric,
  formatPath,
  formatPathInText,
  formatPercent,
  formatReturnPercent,
  formatTime,
  formatTrustValue,
  formatVersionBacktest,
  legacyAutomationPresets,
  operationalAutomationPresets,
  presets,
  summarizeFailedChecks,
  trainingPresets,
  tuningPresets,
  v8TuningPresets,
} from '../adminMlDataModel.js'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5050'

function TrustMetric({ label, check, hint }) {
  const status = check?.passed ? 'healthy' : 'warning'
  return (
    <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2">
        <p className="min-w-0 break-keep text-xs font-bold leading-5 text-white">{label}</p>
        <AuditBadge status={status}>{check?.passed ? '통과' : '확인'}</AuditBadge>
      </div>
      <p className="mt-2 break-words font-mono text-base font-bold text-ai-cyan">{formatTrustValue(check)}</p>
      <p className="mt-1 break-keep text-[10px] leading-4 text-slate-500">{hint}</p>
    </div>
  )
}

function OperationalTrustPanel({ data, loading, error }) {
  const assets = data?.assets || {}

  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Operational Trust</p>
        <h2 className="mt-1 text-xl font-bold text-white">운영 신뢰도 검증</h2>
        <p className="mt-2 text-xs leading-5 text-slate-400">
          모델 정확도만 보지 않고 데이터 품질, 시계열 검증, 상위 후보 품질, 비용 반영 초과수익, 최대 낙폭을 함께 확인합니다.
        </p>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          운영 신뢰도 정보를 불러오는 중입니다.
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm leading-6 text-red-300">
          {error}
        </div>
      ) : !data ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          아직 운영 신뢰도 정보가 없습니다.
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {Object.entries(assets).map(([assetKey, report]) => {
            const guard = report.current_guard || report.recommended_guard
            const failedCount = guard?.failed_checks?.length ?? 0
            const totalCount = guard?.checks?.length ?? 0
            const passedCount = Math.max(0, totalCount - failedCount)
            const status = guard?.passed ? 'healthy' : 'warning'
            const failedLines = summarizeFailedChecks(guard, 3)

            return (
              <div key={assetKey} className="rounded-lg border border-slate-800 bg-black/10 p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-bold text-white">{report.asset_type === 'STOCK' ? '주식 모델' : '코인 모델'}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">
                      {guard?.passed
                        ? '참고 신호 운영 기준을 통과했습니다. 그래도 주문 실행은 사용자 승인 흐름을 유지합니다.'
                        : '일부 기준이 부족합니다. 참고 신호 노출은 가능하지만 승격/자동화 판단은 보류해야 합니다.'}
                    </p>
                  </div>
                  <AuditBadge status={status}>{guard?.passed ? '참고 신호 가능' : '보강 필요'}</AuditBadge>
                </div>

                <div className="mt-3 flex flex-wrap gap-2 text-[10px]">
                  <span className="rounded border border-slate-700 px-2 py-1 font-bold text-slate-300">
                    통과 {passedCount}/{totalCount || '-'}
                  </span>
                  <span className="rounded border border-fuchsia-500/30 px-2 py-1 font-bold text-fuchsia-300">
                    SERVING {report.serving_version || '-'}
                  </span>
                  <span className="rounded border border-emerald-500/30 px-2 py-1 font-bold text-emerald-300">
                    PICK {report.recommended_version || '-'}
                  </span>
                </div>

                <div className="mt-4 grid gap-2.5">
                  <TrustMetric
                    label="데이터 품질"
                    check={findGuardCheck(guard, 'dataset_quality')}
                    hint="중복, 결측, 이상치, 최신성 기준"
                  />
                  <TrustMetric
                    label="시계열 CV"
                    check={findGuardCheck(guard, 'cv_roc_auc')}
                    hint="기간을 나눠도 구분력이 유지되는지"
                  />
                  <TrustMetric
                    label="상위 후보 적중"
                    check={findGuardCheck(guard, 'precision_at_top_10pct')}
                    hint="모델이 자신 있는 후보의 품질"
                  />
                  <TrustMetric
                    label="비용 반영 초과수익"
                    check={findGuardCheck(guard, 'composite_excess_return_net')}
                    hint="수수료/슬리피지 반영 후 시장 대비 우위"
                  />
                  <TrustMetric
                    label="최대 낙폭"
                    check={findGuardCheck(guard, 'max_drawdown_net')}
                    hint="운영 중 감당해야 하는 최대 손실 구간"
                  />
                  <TrustMetric
                    label="하락 위험 모델"
                    check={findGuardCheck(guard, 'risk_cv_roc_auc')}
                    hint="위험 신호를 분리해서 볼 수 있는지"
                  />
                </div>

                {failedLines.length ? (
                  <div className="mt-4 rounded-lg border border-amber-500/30 bg-amber-950/10 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-amber-300">보강 필요 항목</p>
                    <div className="mt-2 space-y-1">
                      {failedLines.map((line) => (
                        <p key={line} className="break-words text-[10px] leading-5 text-amber-100">{line}</p>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}

function V8OptunaPanel({
  presets,
  trials,
  updateConfig,
  loadingKey,
  message,
  isLoggedIn,
  onTrialsChange,
  onUpdateConfigChange,
  onRun,
}) {
  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Optuna HPO</p>
          <h2 className="mt-1 text-xl font-bold text-white">v8 하이퍼파라미터 튜닝</h2>
          <p className="mt-2 text-xs leading-5 text-slate-400">
            v8 Optuna는 이미 구성되어 있습니다. 실행 전 피처를 자동 생성한 뒤 LightGBM 파라미터를 탐색합니다.
          </p>
        </div>
        <span className="w-fit rounded border border-emerald-500/40 bg-emerald-950/20 px-2 py-1 text-[10px] font-bold text-emerald-300">
          V8 READY
        </span>
      </div>

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <label className="flex flex-col gap-1.5 text-xs">
          <span className="font-bold text-slate-400">탐색 시도 횟수</span>
          <input
            type="number"
            min="5"
            max="100"
            value={trials}
            onChange={(event) => onTrialsChange(Number(event.target.value))}
            className="rounded border border-slate-700 bg-[#0f172a] px-3 py-2 font-mono text-white outline-none focus:border-ai-cyan"
          />
        </label>
        <label className="flex items-center gap-2 rounded border border-slate-800 bg-[#0f172a]/70 px-3 py-2">
          <input
            type="checkbox"
            checked={updateConfig}
            onChange={(event) => onUpdateConfigChange(event.target.checked)}
            className="h-4 w-4 accent-ai-cyan"
          />
          <span className="font-bold text-slate-300">최적 파라미터 YAML 자동 저장</span>
        </label>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {presets.map((preset) => (
          <button
            key={preset.key}
            type="button"
            onClick={() => onRun(preset)}
            disabled={loadingKey === preset.key || !isLoggedIn}
            className="rounded border border-ai-cyan/40 bg-ai-cyan/5 px-4 py-3 text-left transition hover:border-ai-cyan hover:bg-ai-cyan/10 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <p className="text-sm font-bold text-white">
              {loadingKey === preset.key ? '튜닝 진행 중...' : preset.label}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-400">{preset.summary}</p>
            <p className="mt-1 break-all font-mono text-[10px] text-slate-500">{formatPath(preset.config)}</p>
          </button>
        ))}
      </div>

      {message ? (
        <div className="mt-4 rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm text-ai-cyan">
          {message}
        </div>
      ) : null}
    </section>
  )
}

function JobHistoryPanel({ jobs = [], loading, error, onShowLog }) {
  if (loading) {
    return (
      <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
        작업 이력을 불러오는 중입니다.
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

  if (!jobs.length) {
    return (
      <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
        아직 기록된 작업이 없습니다.
      </div>
    )
  }

  return (
    <div className="grid gap-2.5">
      {jobs.map((job) => (
        <article key={job.id} className="rounded-lg border border-slate-800 bg-[#0f172a] p-3 text-xs text-slate-300">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-bold text-white" title={job.label || job.exchange || job.id}>
                {job.label || job.exchange || job.id}
              </p>
              <p className="mt-1 truncate font-mono text-[10px] text-slate-500" title={job.output || job.config || ''}>
                {formatPath(job.output) || formatPath(job.config) || job.interval || '-'}
              </p>
            </div>
            <span className={`shrink-0 rounded border px-2 py-1 text-[9px] font-bold ${
              job.status === 'success'
                ? 'border-emerald-500/40 bg-emerald-950/20 text-emerald-300'
                : job.status === 'failed'
                  ? 'border-red-500/40 bg-red-950/20 text-red-300'
                  : 'border-ai-cyan/40 bg-ai-cyan/5 text-ai-cyan'
            }`}>
              {String(job.status || 'running').toUpperCase()}
            </span>
          </div>

          <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="rounded bg-slate-950/50 px-2.5 py-2">
              <p className="text-[10px] font-bold text-slate-500">유형</p>
              <p className="mt-1 truncate font-mono text-[11px] text-slate-300">{job.type || '-'}</p>
            </div>
            <div className="rounded bg-slate-950/50 px-2.5 py-2">
              <p className="text-[10px] font-bold text-slate-500">실패</p>
              <p className="mt-1 font-mono text-[11px] text-amber-300">{job.failure_count || 0}건</p>
            </div>
            <div className="rounded bg-slate-950/50 px-2.5 py-2">
              <p className="text-[10px] font-bold text-slate-500">시작</p>
              <p className="mt-1 font-mono text-[11px] text-slate-300">{formatTime(job.started_at)}</p>
            </div>
            <div className="rounded bg-slate-950/50 px-2.5 py-2">
              <p className="text-[10px] font-bold text-slate-500">종료</p>
              <p className="mt-1 font-mono text-[11px] text-slate-300">{formatTime(job.finished_at)}</p>
            </div>
          </div>

          <div className="mt-3 rounded bg-slate-950/50 px-2.5 py-2">
            {job.training_audit?.promotion_guard ? (
              <GuardSummary guardReport={job.training_audit.promotion_guard} compact />
            ) : job.guard_report ? (
              <GuardSummary guardReport={job.guard_report} compact />
            ) : job.serving_audit_report ? (
              <div className="space-y-1">
                <AuditBadge status={job.serving_audit_report.status}>
                  {job.serving_audit_report.status === 'healthy' ? '서빙 정상' : '서빙 경고'}
                </AuditBadge>
                <p className="text-[10px] text-slate-500">
                  차단 {job.serving_audit_report.blocking_count ?? 0}건
                </p>
              </div>
            ) : (
              <p className="text-[10px] text-slate-500">감사 정보 없음</p>
            )}
          </div>

          <button
            type="button"
            onClick={() => onShowLog?.(job)}
            className="mt-3 w-full rounded border border-slate-700 bg-slate-800/40 px-3 py-2 text-[11px] font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white"
          >
            로그 보기
          </button>
        </article>
      ))}
    </div>
  )
}

function ReadinessItem({ label, status, detail }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
        <p className="min-w-0 break-keep text-sm font-bold leading-5 text-white">{label}</p>
        <span className={`rounded border px-2 py-1 text-[10px] font-bold ${
          status ? 'border-emerald-500/40 text-emerald-300' : 'border-amber-500/40 text-amber-300'
        }`}>
          {status ? '준비 완료' : '확인 필요'}
        </span>
      </div>
      <p className="mt-2 whitespace-pre-wrap break-words font-mono text-[10px] leading-5 text-slate-500">{formatPathInText(detail)}</p>
    </div>
  )
}

function ReadinessPanel({ data, loading, error, onRefresh }) {
  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Readiness</p>
          <h2 className="mt-1 text-xl font-bold text-white">운영 준비 상태</h2>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="w-full rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {loading ? '불러오는 중' : '준비 상태 새로고침'}
        </button>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          운영 준비 상태를 불러오는 중입니다.
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm leading-6 text-red-300">
          {error}
        </div>
      ) : !data ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          아직 준비 상태 정보가 없습니다.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ReadinessItem
            label="Toss 키"
            status={data.keys?.toss_ready}
            detail={data.keys?.toss_ready
              ? `Supabase 저장 키를 백엔드에서 복호화해 사용 가능\nsource: ${data.keys?.toss_source || '-'}\naccountSeq: ${data.keys?.toss_account_seq_ready ? 'READY' : 'CHECK'} / env: ${data.keys?.toss_broker_env || '-'} / records: ${data.keys?.toss_record_count ?? 0}`
              : `Toss 키 저장 또는 연결 확인 필요\nsource: ${data.keys?.toss_source || '-'}`}
          />
          <ReadinessItem
            label="주식 원천 CSV"
            status={data.datasets?.stock_raw?.quality?.status === 'healthy'}
            detail={buildQualityDetail(data.datasets?.stock_raw)}
          />
          <ReadinessItem
            label="코인 원천 CSV"
            status={data.datasets?.crypto_raw?.quality?.status === 'healthy'}
            detail={buildQualityDetail(data.datasets?.crypto_raw)}
          />
          <ReadinessItem
            label="매크로 지표"
            status={data.datasets?.macro_raw?.exists}
            detail={`${data.datasets?.macro_raw?.rows ?? 0} rows\n${data.datasets?.macro_raw?.path || '-'}`}
          />
          <ReadinessItem
            label="외부 피처"
            status={Boolean(data.feature_sources?.news_features?.exists || data.feature_sources?.crypto_market_features?.exists || data.feature_sources?.stock_event_features?.exists)}
            detail={`news ${data.feature_sources?.news_features?.rows ?? 0} / crypto ${data.feature_sources?.crypto_market_features?.rows ?? 0} / stock ${data.feature_sources?.stock_event_features?.rows ?? 0}`}
          />
          <ReadinessItem
            label="SERVING 상태"
            status={Boolean(data.registry?.stock_serving || data.registry?.crypto_serving)}
            detail={`stock: ${data.registry?.stock_serving || '-'}\ncrypto: ${data.registry?.crypto_serving || '-'}`}
          />
        </div>
      )}
    </section>
  )
}

function ExecutionChecklistPanel() {
  const steps = [
    '운영 준비 상태에서 Toss 키와 원천 CSV 상태를 먼저 확인',
    '필요하면 CSV 생성 또는 stock-v7-full / crypto-v7-full 실행',
    '작업 이력 success와 summary 파일 생성 여부 확인',
    '버전 비교 표에서 SERVING / PICK / LATEST와 백테스트 비교',
    '레지스트리 패널에서 검토 완료 버전을 서비스 반영',
    'active-model 기준 선택 결과가 기대와 같은지 재확인',
  ]

  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Checklist</p>
        <h2 className="mt-1 text-xl font-bold text-white">실행 순서</h2>
      </div>
      <div className="grid gap-3">
        {steps.map((step, index) => (
          <div key={step} className="flex gap-3 rounded-lg border border-slate-800 bg-[#0f172a] p-3">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-ai-cyan/40 font-mono text-[10px] font-bold text-ai-cyan">
              {index + 1}
            </div>
            <p className="text-sm leading-6 text-slate-300">{step}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function ReportPanel({ loading, message, onGenerate }) {
  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Report</p>
        <h2 className="mt-1 text-xl font-bold text-white">실험 리포트 저장</h2>
      </div>
      <p className="text-sm leading-6 text-slate-400">
        현재 summary JSON과 serving 상태를 기준으로 Markdown 리포트를 생성합니다.
      </p>
      <div className="mt-4">
        <button
          type="button"
          onClick={onGenerate}
          disabled={loading}
          className="rounded border border-ai-cyan/40 px-4 py-2 text-xs font-bold text-ai-cyan transition hover:bg-ai-cyan/10 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? '리포트 생성 중...' : '리포트 생성'}
        </button>
      </div>
      {message ? (
        <div className="mt-4 rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-4 text-sm text-ai-cyan">
          {message}
        </div>
      ) : null}
    </section>
  )
}

function ReportHistoryPanel({ reports = [], loading, error, onRefresh }) {
  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Reports</p>
          <h2 className="mt-1 text-xl font-bold text-white">최근 실험 리포트</h2>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="w-full rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {loading ? '불러오는 중' : '리포트 목록 새로고침'}
        </button>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          리포트 목록을 불러오는 중입니다.
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm leading-6 text-red-300">
          {error}
        </div>
      ) : !reports.length ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          아직 생성된 실험 리포트가 없습니다.
        </div>
      ) : (
        <div className="grid gap-3">
          {reports.map((report) => (
            <div key={report.path} className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
              <p className="break-all font-mono text-sm text-white">{report.name}</p>
              <p className="mt-1 font-mono text-[10px] text-slate-500 truncate block" title={report.path}>
                {formatPath(report.path)}
              </p>
              <div className="mt-2 flex flex-wrap gap-2 text-[10px] text-slate-400">
                <span>{report.updated_at}</span>
                <span>{report.size_bytes} bytes</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}

function VersionComparisonTable({ versions = [], selectedVersion, recommendedVersion, latestVersion, servingVersion, onSelectVersion }) {
  if (!versions.length) {
    return null
  }

  return (
    <div className="mt-5 rounded-lg border border-slate-800 bg-[#0f172a] p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-400">버전 비교</p>
        <div className="flex flex-wrap gap-2">
          <span className="rounded border border-ai-cyan/40 px-2 py-1 text-[10px] font-bold text-ai-cyan">
            현재 선택: {selectedVersion || '-'}
          </span>
          <span className="rounded border border-fuchsia-500/40 px-2 py-1 text-[10px] font-bold text-fuchsia-300">
            서비스 반영: {servingVersion || '-'}
          </span>
          <span className="rounded border border-emerald-500/40 px-2 py-1 text-[10px] font-bold text-emerald-300">
            추천: {recommendedVersion || '-'}
          </span>
          <span className="rounded border border-slate-600 px-2 py-1 text-[10px] font-bold text-slate-300">
            최신: {latestVersion || '-'}
          </span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-xs text-slate-300">
          <thead className="text-[10px] uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-2 py-2">버전</th>
              <th className="px-2 py-2">CV 구분력</th>
              <th className="px-2 py-2">상위 10% 적중</th>
              <th className="px-2 py-2">하락 구분력</th>
              <th className="px-2 py-2">복합 초과수익(순)</th>
              <th className="px-2 py-2">복합 승률</th>
              <th className="px-2 py-2">최대낙폭</th>
              <th className="px-2 py-2">검증 행 수</th>
              <th className="px-2 py-2">상태</th>
            </tr>
          </thead>
          <tbody>
            {versions
              .slice()
              .sort((a, b) => (b.version_number || 0) - (a.version_number || 0))
              .map((version) => (
                <tr
                  key={version.version}
                  className="cursor-pointer border-t border-slate-800 transition hover:bg-white/5"
                  onClick={() => onSelectVersion?.(version.version)}
                >
                  <td className="px-2 py-2 font-mono text-white">{version.version}</td>
                  <td className="px-2 py-2">{formatMetric(version.metrics?.time_series_cv_average?.roc_auc || version.metrics?.roc_auc)}</td>
                  <td className="px-2 py-2">{formatMetric(version.metrics?.time_series_cv_average?.precision_at_top_10pct || version.metrics?.precision_at_top_10pct)}</td>
                  <td className="px-2 py-2">{formatMetric(version.risk_metrics?.time_series_cv_average?.roc_auc || version.risk_metrics?.roc_auc)}</td>
                  <td className="px-2 py-2 font-mono">{formatVersionBacktest(version, 'excess_return_net')}</td>
                  <td className="px-2 py-2">{formatPercent(version.backtests?.composite?.data?.selection_win_rate_net ?? version.backtests?.composite?.data?.selection_win_rate)}</td>
                  <td className="px-2 py-2 font-mono">{formatReturnPercent(version.backtests?.composite?.data?.max_drawdown_net ?? version.backtests?.composite?.data?.max_drawdown)}</td>
                  <td className="px-2 py-2">{version.metrics?.valid_rows ?? '-'}</td>
                  <td className="px-2 py-2">
                    <div className="flex flex-wrap gap-1">
                      <span className={`rounded border px-2 py-1 text-[10px] font-bold ${
                        version.version === selectedVersion
                          ? 'border-ai-cyan/40 text-ai-cyan'
                          : version.updated
                            ? 'border-emerald-500/40 text-emerald-300'
                            : 'border-slate-700 text-slate-500'
                      }`}>
                        {version.version === selectedVersion ? '분석 중' : version.updated ? '준비 완료' : '데이터 없음'}
                      </span>
                      {version.version === recommendedVersion ? (
                        <span className="rounded border border-emerald-500/30 px-2 py-1 text-[10px] font-bold text-emerald-300">
                          추천
                        </span>
                      ) : null}
                      {version.version === servingVersion || version.is_serving ? (
                        <span className="rounded border border-fuchsia-500/30 px-2 py-1 text-[10px] font-bold text-fuchsia-300">
                          서비스 적용
                        </span>
                      ) : null}
                      {version.version === latestVersion ? (
                        <span className="rounded border border-slate-600 px-2 py-1 text-[10px] font-bold text-slate-300">
                          최신
                        </span>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ModelResultCard({ title, result }) {
  const versions = useMemo(() => result?.versions || [], [result?.versions])
  const defaultSelectedVersion = result?.serving_version || result?.recommended_version || result?.selected_version || ''
  const [selectedVersion, setSelectedVersion] = useState(defaultSelectedVersion)
  const resolvedSelectedVersion = versions.some((item) => item.version === selectedVersion)
    ? selectedVersion
    : defaultSelectedVersion

  const activeResult = useMemo(() => {
    if (!versions.length) return result
    return versions.find((item) => item.version === resolvedSelectedVersion) || result
  }, [result, resolvedSelectedVersion, versions])

  const metrics = activeResult?.metrics
  const riskMetrics = activeResult?.risk_metrics
  const predictions = activeResult?.predictions || []
  const upOnlyBacktest = activeResult?.backtests?.up_only?.data
  const compositeBacktest = activeResult?.backtests?.composite?.data
  const comparisonBaselines = useMemo(() => {
    const candidates = [
      { label: '서비스 반영 기준', version: result?.serving_version },
      { label: '추천 기준', version: result?.recommended_version },
      { label: '최신 기준', version: result?.latest_version },
    ]

    return candidates
      .filter((candidate, index, array) => candidate.version && array.findIndex((item) => item.version === candidate.version) === index)
      .map((candidate) => ({
        ...candidate,
        ...versions.find((item) => item.version === candidate.version),
      }))
      .filter((candidate) => candidate.version)
  }, [result?.latest_version, result?.recommended_version, result?.serving_version, versions])

  const renderProgressBar = (value, minVal = 0.5, maxVal = 0.65) => {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return null
    const num = Number(value)
    const percent = Math.max(0, Math.min(100, ((num - minVal) / (maxVal - minVal)) * 100))
    
    let colorClass = 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]'
    if (num >= 0.55) {
      colorClass = 'bg-ai-cyan shadow-[0_0_8px_rgba(0,243,255,0.5)]'
    } else if (num >= 0.51) {
      colorClass = 'bg-amber-500 shadow-[0_0_8px_rgba(245,158,11,0.5)]'
    }

    return (
      <div className="mt-2 h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
        <div 
          className={`h-full rounded-full transition-all duration-500 ${colorClass}`}
          style={{ width: `${percent}%` }}
        />
      </div>
    )
  }

  const renderMetricValue = (val, isPercent = false, isReturn = false) => {
    if (val === null || val === undefined || Number.isNaN(Number(val))) {
      return <span className="font-mono text-slate-500">-</span>
    }
    const num = Number(val)
    const text = isPercent ? formatPercent(num) : (isReturn ? formatReturnPercent(num) : formatMetric(num))
    
    if (num > 0) {
      return <span className="font-mono text-emerald-400 font-bold">+{text}</span>
    } else if (num < 0) {
      return <span className="font-mono text-rose-500 font-bold">{text}</span>
    }
    return <span className="font-mono text-slate-300">{text}</span>
  }

  return (
    <article className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">{activeResult?.asset_type || result?.asset_type || '-'}</p>
          <h3 className="mt-1 text-sm font-bold uppercase tracking-wider text-white">{title}</h3>
        </div>
        <span className={`w-fit rounded border px-2 py-1 text-[10px] font-bold ${
          activeResult?.updated ? 'border-emerald-500/40 text-emerald-300' : 'border-slate-700 text-slate-500'
        }`}>
          {activeResult?.updated ? 'READY' : 'NO DATA'}
        </span>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <span className="rounded border border-fuchsia-500/30 px-2 py-1 text-[10px] font-bold text-fuchsia-300">
          SERVING {result?.serving_version || '-'}
        </span>
        <span className="rounded border border-emerald-500/30 px-2 py-1 text-[10px] font-bold text-emerald-300">
          PICK {result?.recommended_version || '-'}
        </span>
        <span className="rounded border border-slate-600 px-2 py-1 text-[10px] font-bold text-slate-300">
          LATEST {result?.latest_version || '-'}
        </span>
      </div>

      {metrics ? (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-lg bg-[#0f172a] p-3 border border-slate-800 hover:border-slate-700 transition">
            <p className="text-xs font-bold text-slate-400">구분력 (ROC-AUC)</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500 font-sans">상승/비상승을 가르는 전체 힘</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.roc_auc)}</p>
            {renderProgressBar(metrics.roc_auc, 0.5, 0.65)}
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3 border border-slate-800 hover:border-slate-700 transition">
            <p className="text-xs font-bold text-slate-400">시계열 CV 구분력</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500 font-sans">기간 분할 검증 평균 구분력</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.time_series_cv_average?.roc_auc || metrics.roc_auc)}</p>
            {renderProgressBar(metrics.time_series_cv_average?.roc_auc || metrics.roc_auc, 0.5, 0.65)}
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3 border border-slate-800 hover:border-slate-700 transition">
            <p className="text-xs font-bold text-slate-400">상위 10% 적중</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500 font-sans">점수 상위 후보의 실제 상승 비율</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.time_series_cv_average?.precision_at_top_10pct || metrics.precision_at_top_10pct)}</p>
            {renderProgressBar(metrics.time_series_cv_average?.precision_at_top_10pct || metrics.precision_at_top_10pct, 0.1, 0.3)}
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3 border border-slate-800 hover:border-slate-700 transition">
            <p className="text-xs font-bold text-slate-400">상승 적중도 (AP)</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500 font-sans font-sans">상승 후보 쪽 랭킹 신뢰도</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.average_precision)}</p>
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3 border border-slate-800 hover:border-slate-700 transition">
            <p className="text-xs font-bold text-slate-400">Precision / Recall</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500 font-sans">예측 정확도 / 탐지 커버리지</p>
            <p className="mt-1 font-mono text-sm font-bold text-white">
              {formatMetric(metrics.precision)} / {formatMetric(metrics.recall)}
            </p>
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3 border border-slate-800 hover:border-slate-700 transition">
            <p className="text-xs font-bold text-slate-400">전체 정답률</p>
            <p className="mt-0.5 text-[10px] leading-4 text-slate-500 font-sans">전체 0/1 매칭 비율</p>
            <p className="mt-1 font-mono text-xl font-bold text-white">{formatMetric(metrics.accuracy)}</p>
          </div>
          <div className="rounded-lg bg-[#0f172a] p-3 sm:col-span-3 border border-slate-800 font-sans">
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
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400 font-sans">
          아직 학습 결과 파일이 없습니다.
        </div>
      )}

      <div className="mt-5 grid gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">하락 위험 모델</p>
          {riskMetrics ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              <div>
                <p className="text-[10px] text-slate-500 font-sans">구분력 (ROC-AUC)</p>
                <p className="font-mono text-sm text-white">{formatMetric(riskMetrics.roc_auc)}</p>
                {renderProgressBar(riskMetrics.roc_auc, 0.5, 0.65)}
              </div>
              <div>
                <p className="text-[10px] text-slate-500 font-sans">상위후보 적중도</p>
                <p className="font-mono text-sm text-white">{formatMetric(riskMetrics.average_precision)}</p>
              </div>
              <div>
                <p className="text-[10px] text-slate-500 font-sans">전체 정답률</p>
                <p className="font-mono text-sm text-white">{formatMetric(riskMetrics.accuracy)}</p>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-slate-400 font-sans">아직 risk_label 모델 결과가 없습니다.</p>
          )}
        </div>

        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
          <p className="text-xs font-bold uppercase tracking-wider text-slate-400">백테스트 요약</p>
          <div className="mt-3 grid gap-3">
            <div className="rounded-lg border border-slate-800 bg-black/10 p-3 font-sans">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">상승 점수 기준</p>
              {upOnlyBacktest ? (
                <div className="mt-2 grid gap-1 text-xs text-slate-300">
                  <p>상위 {upOnlyBacktest.top_n}개 평균 수익률: {renderMetricValue(upOnlyBacktest.top_avg_future_return, false, true)}</p>
                  <p>비용 반영 평균 수익률: {renderMetricValue(upOnlyBacktest.top_avg_future_return_net, false, true)}</p>
                  <p>전체 평균 수익률: {renderMetricValue(upOnlyBacktest.universe_avg_future_return, false, true)}</p>
                  <p>순 초과 수익률: {renderMetricValue(upOnlyBacktest.excess_return_net ?? upOnlyBacktest.excess_return, false, true)}</p>
                  <p>후보 승률: <span className="font-mono text-white">{formatPercent(upOnlyBacktest.selection_win_rate_net ?? upOnlyBacktest.selection_win_rate)}</span></p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-400">아직 단순 백테스트 결과가 없습니다.</p>
              )}
            </div>

            <div className="rounded-lg border border-slate-800 bg-black/10 p-3 font-sans">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">복합 점수 기준</p>
              {compositeBacktest ? (
                <div className="mt-2 grid gap-1 text-xs text-slate-300">
                  <p>상위 {compositeBacktest.top_n}개 평균 수익률: {renderMetricValue(compositeBacktest.top_avg_future_return, false, true)}</p>
                  <p>비용 반영 평균 수익률: {renderMetricValue(compositeBacktest.top_avg_future_return_net, false, true)}</p>
                  <p>전체 평균 수익률: {renderMetricValue(compositeBacktest.universe_avg_future_return, false, true)}</p>
                  <p>순 초과 수익률: {renderMetricValue(compositeBacktest.excess_return_net ?? compositeBacktest.excess_return, false, true)}</p>
                  <p>후보 승률: <span className="font-mono text-white">{formatPercent(compositeBacktest.selection_win_rate_net ?? compositeBacktest.selection_win_rate)}</span></p>
                  <p>최대 낙폭: <span className="font-mono text-rose-450 font-bold">{formatReturnPercent(compositeBacktest.max_drawdown_net)}</span></p>
                </div>
              ) : (
                <p className="mt-2 text-sm text-slate-400">아직 복합 백테스트 결과가 없습니다.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      <VersionComparisonTable
        versions={versions}
        selectedVersion={resolvedSelectedVersion}
        recommendedVersion={result?.recommended_version}
        latestVersion={result?.latest_version}
        servingVersion={result?.serving_version}
        onSelectVersion={setSelectedVersion}
      />

      <VersionDeltaPanel activeVersion={activeResult} baselines={comparisonBaselines} />

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
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-words text-sm font-bold text-white">{row.display_name || row.symbol}</p>
                    {row.position ? (
                      <span className={`rounded px-1.5 py-0.5 text-[9px] font-black tracking-widest ${
                        row.position === 'SHORT'
                          ? 'bg-rose-950/80 text-rose-300 border border-rose-700/60'
                          : 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60'
                      }`}>
                        {row.position}
                      </span>
                    ) : null}
                  </div>
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

      <main className="mx-auto flex max-w-7xl flex-col gap-4">
        {/* 관리자 내부 탭 */}
        <div className="grid grid-cols-3 gap-2 rounded-lg border border-slate-800 bg-[#0f172a] p-1">
          <button
            type="button"
            onClick={() => setAdminTab('ml')}
            className={`rounded-md px-3 py-2 text-xs font-bold transition ${
              adminTab === 'ml'
                ? 'bg-ai-cyan text-slate-950'
                : 'text-slate-400 hover:bg-slate-800/70 hover:text-white'
            }`}
          >
            ML 운영 콘솔
          </button>
          <button
            type="button"
            onClick={() => setAdminTab('inquiries')}
            className={`rounded-md px-3 py-2 text-xs font-bold transition ${
              adminTab === 'inquiries'
                ? 'bg-ai-cyan text-slate-950'
                : 'text-slate-400 hover:bg-slate-800/70 hover:text-white'
            }`}
          >
            사용자 문의 관리
          </button>
          <button
            type="button"
            onClick={() => setAdminTab('symbols')}
            className={`rounded-md px-3 py-2 text-xs font-bold transition ${
              adminTab === 'symbols'
                ? 'bg-ai-cyan text-slate-950'
                : 'text-slate-400 hover:bg-slate-800/70 hover:text-white'
            }`}
          >
            종목 정리
          </button>
        </div>

        {adminTab === 'ml' && (
          <>
            <section className="ai-glass rounded-lg p-4">
          <div className="grid gap-3">
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">ML Operations</p>
              <h2 className="mt-1 text-xl font-bold text-white">ML 운영 콘솔</h2>
              <p className="mt-1 break-keep text-xs leading-5 text-slate-400">
                기본 화면은 운영 상태, 서빙 감사, 활성 신호, v8 자동화 실행, 최근 작업 이력만 표시합니다.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowAdvancedTools((prev) => !prev)}
              className="w-full rounded border border-slate-700 bg-[#0f172a] px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white"
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
          compactGuards
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
            variant="mobile"
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
            variant="mobile"
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
          <MobileAdminInquiries
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
