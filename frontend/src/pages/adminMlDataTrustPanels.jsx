import {
  findGuardCheck,
  formatPath,
  formatTrustValue,
  summarizeFailedChecks,
} from './adminMlDataModel.js'
import { AuditBadge } from './adminMlDataCorePanels.jsx'

function TrustMetric({ label, check, hint, mobile = false }) {
  const status = check?.passed ? 'healthy' : 'warning'
  return (
    <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
      <div className={mobile ? 'grid grid-cols-[minmax(0,1fr)_auto] items-start gap-2' : 'flex items-center justify-between gap-2'}>
        <p className={mobile ? 'min-w-0 break-keep text-xs font-bold leading-5 text-white' : 'text-xs font-bold text-white'}>{label}</p>
        <AuditBadge status={status}>{check?.passed ? '통과' : '확인'}</AuditBadge>
      </div>
      <p className={mobile ? 'mt-2 break-words font-mono text-base font-bold text-ai-cyan' : 'mt-2 font-mono text-lg font-bold text-ai-cyan'}>{formatTrustValue(check)}</p>
      <p className={mobile ? 'mt-1 break-keep text-[10px] leading-4 text-slate-500' : 'mt-1 text-[10px] leading-4 text-slate-500'}>{hint}</p>
    </div>
  )
}

export function OperationalTrustPanel({ data, loading, error, variant = 'desktop' }) {
  const isMobile = variant === 'mobile'
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

                <div className={isMobile ? 'mt-4 grid gap-2.5' : 'mt-4 grid gap-3 sm:grid-cols-2'}>
                  <TrustMetric
                    mobile={isMobile}
                    label="데이터 품질"
                    check={findGuardCheck(guard, 'dataset_quality')}
                    hint="중복, 결측, 이상치, 최신성 기준"
                  />
                  <TrustMetric
                    mobile={isMobile}
                    label="시계열 CV"
                    check={findGuardCheck(guard, 'cv_roc_auc')}
                    hint="기간을 나눠도 구분력이 유지되는지"
                  />
                  <TrustMetric
                    mobile={isMobile}
                    label="상위 후보 적중"
                    check={findGuardCheck(guard, 'precision_at_top_10pct')}
                    hint="모델이 자신 있는 후보의 품질"
                  />
                  <TrustMetric
                    mobile={isMobile}
                    label="비용 반영 초과수익"
                    check={findGuardCheck(guard, 'composite_excess_return_net')}
                    hint="수수료/슬리피지 반영 후 시장 대비 우위"
                  />
                  <TrustMetric
                    mobile={isMobile}
                    label="최대 낙폭"
                    check={findGuardCheck(guard, 'max_drawdown_net')}
                    hint="운영 중 감당해야 하는 최대 손실 구간"
                  />
                  <TrustMetric
                    mobile={isMobile}
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
                        <p key={line} className={isMobile ? 'break-words text-[10px] leading-5 text-amber-100' : 'break-all text-[10px] leading-5 text-amber-100'}>{line}</p>
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

export function V8OptunaPanel({
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
