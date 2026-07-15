import {
  buildJobLogClipboardText,
  findRegistryRow,
  formatMetric,
  formatPath,
  formatPercent,
  formatReturnPercent,
  formatSignedDelta,
  formatStaleness,
  getHealthLabel,
  getHealthTone,
  getSignalGradeLabel,
  getSignalGradeTone,
  getSimpleGuardStatus,
  getVersionSnapshot,
  summarizeFailedChecks,
} from './adminMlDataModel.js'

export function StatusPanel({ result, error, loading }) {
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
        <div>
          <dt className="text-xs text-slate-500">실패 심볼 수</dt>
          <dd className="font-mono text-white">{result.data.failure_count ?? 0}</dd>
        </div>
        <div className="md:col-span-2">
          <dt className="text-xs text-slate-500">파일 경로</dt>
          <dd className="break-all font-mono text-white">{result.data.output}</dd>
        </div>
        {result.data.failures?.length ? (
          <div className="md:col-span-2">
            <dt className="text-xs text-slate-500">실패 목록</dt>
            <dd className="mt-1 space-y-1">
              {result.data.failures.map((failure) => (
                <p key={`${failure.symbol}-${failure.reason}`} className="break-all font-mono text-xs text-amber-200">
                  {failure.symbol}: {failure.reason}
                </p>
              ))}
            </dd>
          </div>
        ) : null}
      </dl>
    </div>
  )
}

export function AuditBadge({ status, children }) {
  return (
    <span className={`inline-flex shrink-0 items-center whitespace-nowrap rounded border px-2 py-1 text-[10px] font-bold ${getHealthTone(status)}`}>
      {children || getHealthLabel(status)}
    </span>
  )
}

export function GuardSummary({ guardReport, compact = false }) {
  if (!guardReport) {
    return <p className="text-[10px] text-slate-500">승격 검증 정보가 아직 없습니다.</p>
  }

  const failedLines = summarizeFailedChecks(guardReport, compact ? 2 : 5)
  const tooltipText = failedLines.length ? failedLines.join('\n') : '모든 승격 기준을 통과했습니다.'
  const failedCount = guardReport.failed_checks?.length ?? 0

  return (
    <div className="min-w-0 space-y-1 inline-block" title={tooltipText}>
      <div className="flex min-w-0 items-center gap-1 whitespace-nowrap">
        <AuditBadge status={guardReport.passed ? 'healthy' : 'warning'}>
          {guardReport.passed
            ? '승격 통과'
            : `차단 (실패 ${failedCount}건)`}
        </AuditBadge>
      </div>
      {!compact && failedLines.length ? (
        <div className="space-y-1 mt-1">
          {failedLines.map((line) => (
            <p key={line} className="break-words text-[10px] leading-4 text-amber-200">
              {line}
            </p>
          ))}
        </div>
      ) : !compact ? (
        <p className="text-[10px] text-emerald-300">모든 승격 기준을 통과했습니다.</p>
      ) : null}
    </div>
  )
}

export function JobLogModal({ job, onClose }) {
  if (!job) return null

  const handleCopy = () => {
    navigator.clipboard.writeText(buildJobLogClipboardText(job))
    alert('로그가 클립보드에 복사되었습니다.')
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-4xl max-h-[85vh] flex flex-col rounded-lg border border-slate-700 bg-[#0f172a] text-[#e2e2ec] shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="rounded border border-ai-cyan/40 px-2 py-0.5 text-[10px] font-bold text-ai-cyan">
              {String(job.type || 'job').toUpperCase()}
            </span>
            <span className="text-sm font-bold text-white">
              {job.label || job.id} 작업 상세 로그
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-400 hover:text-white text-xl font-bold transition-colors"
          >
            &times;
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-4 font-mono text-xs leading-5">
          {job.config || job.interval ? (
            <div className="rounded bg-black/30 p-3 border border-slate-800/60 text-slate-400">
              <p>설정: {job.config || '-'}</p>
              <p>인터벌: {job.interval || '-'}</p>
            </div>
          ) : null}

          {job.training_audit || job.guard_report || job.serving_audit_report ? (
            <div className="grid gap-4 xl:grid-cols-3">
              <div className="rounded border border-slate-800 bg-black/30 p-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">학습 감사</p>
                {job.training_audit?.promotion_guard ? (
                  <GuardSummary guardReport={job.training_audit.promotion_guard} />
                ) : (
                  <p className="text-[10px] text-slate-500">학습 감사 정보가 없습니다.</p>
                )}
              </div>
              <div className="rounded border border-slate-800 bg-black/30 p-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">승격 검증</p>
                <GuardSummary guardReport={job.guard_report} />
              </div>
              <div className="rounded border border-slate-800 bg-black/30 p-3">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">서빙 감사</p>
                {job.serving_audit_report ? (
                  <div className="space-y-2">
                    <AuditBadge status={job.serving_audit_report.status}>
                      {job.serving_audit_report.status === 'healthy' ? '전체 정상' : '경고'}
                    </AuditBadge>
                    <p className="text-[10px] text-slate-400">차단 항목 {job.serving_audit_report.blocking_count ?? 0}건</p>
                  </div>
                ) : job.training_audit?.serving_audit ? (
                  <div className="space-y-2">
                    <AuditBadge status={job.training_audit.serving_audit.status}>
                      {job.training_audit.serving_audit.status === 'healthy' ? '전체 정상' : '경고'}
                    </AuditBadge>
                    <p className="text-[10px] text-slate-400">차단 항목 {job.training_audit.serving_audit.blocking_count ?? 0}건</p>
                  </div>
                ) : (
                  <p className="text-[10px] text-slate-500">서빙 감사 정보가 없습니다.</p>
                )}
              </div>
            </div>
          ) : null}

          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex flex-col rounded border border-slate-800 bg-black/40">
              <div className="flex items-center justify-between border-b border-slate-800 px-3 py-1.5 bg-black/20">
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">STDOUT (출력)</span>
              </div>
              <pre className="h-[40vh] overflow-auto p-3 whitespace-pre-wrap text-emerald-200 text-[11px] leading-relaxed">
                {job.stdout || '출력 로그가 없습니다.'}
              </pre>
            </div>

            <div className="flex flex-col rounded border border-slate-800 bg-black/40">
              <div className="flex items-center justify-between border-b border-slate-800 px-3 py-1.5 bg-black/20">
                <span className="text-[10px] font-bold uppercase tracking-wider text-rose-400">STDERR (에러)</span>
              </div>
              <pre className="h-[40vh] overflow-auto p-3 whitespace-pre-wrap text-rose-300 text-[11px] leading-relaxed">
                {job.stderr || '에러 로그가 없습니다.'}
              </pre>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 border-t border-slate-800 px-5 py-3.5 bg-black/10">
          <button
            type="button"
            onClick={handleCopy}
            className="rounded border border-ai-cyan/40 px-4 py-2 text-xs font-bold text-ai-cyan transition hover:bg-ai-cyan/10"
          >
            전체 복사
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-bold text-white transition hover:bg-slate-700"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  )
}

export function VersionDeltaPanel({ activeVersion, baselines = [] }) {
  const activeSnapshot = getVersionSnapshot(activeVersion)
  const visibleBaselines = baselines.filter((baseline) => baseline?.version && baseline.version !== activeVersion?.version)

  if (!activeVersion?.version || !activeSnapshot || !visibleBaselines.length) {
    return null
  }

  return (
    <div className="mt-5 rounded-lg border border-slate-800 bg-[#0f172a] p-4">
      <div className="mb-3">
        <p className="text-xs font-bold uppercase tracking-wider text-slate-400">버전 차이 요약</p>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          현재 선택 버전이 비교 기준보다 얼마나 좋아졌는지 빠르게 확인합니다.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {visibleBaselines.map((baseline) => {
          const baselineSnapshot = getVersionSnapshot(baseline)
          if (!baselineSnapshot) return null

          return (
            <div key={`${activeVersion.version}-${baseline.version}`} className="rounded-lg border border-slate-800 bg-black/10 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold text-white">{baseline.label}</p>
                  <p className="mt-1 font-mono text-[10px] text-slate-500">
                    {baseline.version} {'->'} {activeVersion.version}
                  </p>
                </div>
                <span className="rounded border border-ai-cyan/30 px-2 py-1 text-[10px] font-bold text-ai-cyan">
                  DELTA
                </span>
              </div>
              <div className="mt-3 grid gap-2 text-xs text-slate-300">
                <p>
                  시계열 CV 구분력: <span className="font-mono text-white">{formatSignedDelta(activeSnapshot.cvRocAuc - baselineSnapshot.cvRocAuc)}</span>
                </p>
                <p>
                  상위 10% 적중: <span className="font-mono text-white">{formatSignedDelta(activeSnapshot.top10Precision - baselineSnapshot.top10Precision)}</span>
                </p>
                <p>
                  하락 구분력: <span className="font-mono text-white">{formatSignedDelta(activeSnapshot.riskCvRocAuc - baselineSnapshot.riskCvRocAuc)}</span>
                </p>
                <p>
                  복합 초과수익(순): <span className="font-mono text-ai-cyan">{formatSignedDelta(activeSnapshot.compositeExcessReturnNet - baselineSnapshot.compositeExcessReturnNet, 'return')}</span>
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function ActiveSignalPanel({ title, data, loading, error, guardReport, onRefresh }) {
  const overview = data?.overview
  const filteredOverview = data?.filtered_overview
  const performance = data?.performance
  const predictions = data?.predictions || []
  const gradeCounts = filteredOverview?.grade_counts || overview?.grade_counts || {}

  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Active Signals</p>
          <h2 className="mt-1 text-xl font-bold text-white">{title}</h2>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="w-full rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {loading ? '불러오는 중' : '신호 새로고침'}
        </button>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          활성 신호를 불러오는 중입니다.
        </div>
      ) : error ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-amber-800 bg-amber-950/20 p-4 text-sm leading-6 text-amber-200">
            {error}
          </div>
          {guardReport ? (
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">차단 사유</p>
              <GuardSummary guardReport={guardReport} compact />
            </div>
          ) : null}
        </div>
      ) : !data ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
            아직 활성 신호 데이터가 없습니다.
          </div>
          {guardReport ? (
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">현재 검증 상태</p>
              <GuardSummary guardReport={guardReport} compact />
            </div>
          ) : null}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
            <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">승격 검증 요약</p>
            <GuardSummary guardReport={guardReport} compact />
          </div>

          <div className="flex flex-wrap gap-2 text-[10px]">
            <span className="rounded border border-fuchsia-500/30 px-2 py-1 font-bold text-fuchsia-300">SERVING {data.serving_version || '-'}</span>
            <span className="rounded border border-emerald-500/30 px-2 py-1 font-bold text-emerald-300">PICK {data.recommended_version || '-'}</span>
            <span className="rounded border border-slate-600 px-2 py-1 font-bold text-slate-300">LATEST {data.latest_version || '-'}</span>
            <span className="rounded border border-ai-cyan/30 px-2 py-1 font-bold text-ai-cyan">{data.model_version || '-'}</span>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
              <p className="text-[10px] text-slate-500">전체 예측 수</p>
              <p className="mt-1 font-mono text-lg font-bold text-white">{overview?.total_predictions ?? 0}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
              <p className="text-[10px] text-slate-500">LONG / HOLD / SHORT</p>
              <p className="mt-1 font-mono text-sm font-bold text-white">
                {overview?.long_count ?? 0} / {overview?.hold_count ?? 0} / {overview?.short_count ?? 0}
              </p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
              <p className="text-[10px] text-slate-500">평균 상승 확률</p>
              <p className="mt-1 font-mono text-lg font-bold text-emerald-300">{formatPercent(filteredOverview?.avg_up_probability)}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
              <p className="text-[10px] text-slate-500">평균 하락 위험</p>
              <p className="mt-1 font-mono text-lg font-bold text-amber-300">{formatPercent(filteredOverview?.avg_risk_probability)}</p>
            </div>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/10 p-3">
              <p className="text-[10px] text-emerald-300">강한 후보</p>
              <p className="mt-1 font-mono text-lg font-bold text-white">{gradeCounts.strong_buy_candidate ?? 0}</p>
            </div>
            <div className="rounded-lg border border-ai-cyan/20 bg-ai-cyan/5 p-3">
              <p className="text-[10px] text-ai-cyan">관찰</p>
              <p className="mt-1 font-mono text-lg font-bold text-white">{gradeCounts.watch ?? 0}</p>
            </div>
            <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-3">
              <p className="text-[10px] text-rose-300">위험</p>
              <p className="mt-1 font-mono text-lg font-bold text-white">{gradeCounts.risky ?? 0}</p>
            </div>
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-3">
              <p className="text-[10px] text-slate-500">신호 없음</p>
              <p className="mt-1 font-mono text-lg font-bold text-white">{gradeCounts.no_signal ?? 0}</p>
            </div>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">성능 스냅샷</p>
              <div className="mt-3 grid gap-2 text-xs text-slate-300">
                <p>시계열 CV 구분력: <span className="font-mono text-white">{formatMetric(performance?.cv_roc_auc)}</span></p>
                <p>상위 10% 적중: <span className="font-mono text-white">{formatMetric(performance?.precision_at_top_10pct)}</span></p>
                <p>하락 구분력: <span className="font-mono text-white">{formatMetric(performance?.risk_cv_roc_auc)}</span></p>
                <p>복합 초과수익(순): <span className="font-mono text-ai-cyan">{formatReturnPercent(performance?.composite_excess_return_net)}</span></p>
                <p>복합 적중률: <span className="font-mono text-white">{formatMetric(performance?.composite_precision_at_top_n)}</span></p>
              </div>
            </div>

            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">현재 필터 결과</p>
              <div className="mt-3 grid gap-2 text-xs text-slate-300">
                <p>표시 개수: <span className="font-mono text-white">{predictions.length}</span></p>
                <p>최대 점수: <span className="font-mono text-white">{formatMetric(filteredOverview?.max_signal_score)}</span></p>
                <p>최소 점수: <span className="font-mono text-white">{formatMetric(filteredOverview?.min_signal_score)}</span></p>
                <p>평균 점수: <span className="font-mono text-white">{formatMetric(filteredOverview?.avg_signal_score)}</span></p>
                <p>마지막 예측 시각: <span className="font-mono break-all text-white">{filteredOverview?.latest_prediction_time || overview?.latest_prediction_time || '-'}</span></p>
              </div>
            </div>
          </div>

          {predictions.length ? (
            <div className="grid gap-2">
              {predictions.slice(0, 8).map((row) => (
                <div
                  key={`${data.asset_type}-${row.symbol}-${row.date}`}
                  className="grid gap-3 rounded-lg border border-slate-800 bg-[#0f172a] p-3 sm:grid-cols-[1fr_auto_auto_auto]"
                >
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="break-words text-sm font-bold text-white">{row.display_name || row.symbol}</p>
                      {row.position ? (
                        <span className={`rounded px-1.5 py-0.5 text-[9px] font-black tracking-widest ${
                          row.position === 'SHORT'
                            ? 'bg-rose-950/80 text-rose-300 border border-rose-700/60'
                            : row.position === 'LONG'
                              ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60'
                              : 'bg-slate-900/80 text-slate-300 border border-slate-700/60'
                        }`}>
                          {row.position}
                        </span>
                      ) : null}
                      <span className={`rounded border px-1.5 py-0.5 text-[9px] font-black tracking-widest ${getSignalGradeTone(row.signal_grade)}`}>
                        {getSignalGradeLabel(row.signal_grade)}
                      </span>
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
                    </div>
                    <p className="mt-1 break-words text-xs text-slate-500">
                      {row.reason_summary || row.date}
                    </p>
                    <p className="mt-1 font-mono text-[10px] text-slate-600">
                      예측 {formatStaleness(row.staleness_minutes)} · {row.predicted_at || row.date || '-'}
                    </p>
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
                    <p className="font-mono text-sm text-ai-cyan">{formatMetric(row.signal_score)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
              현재 필터에 맞는 활성 신호가 없습니다.
            </div>
          )}
        </div>
      )}
    </section>
  )
}

export function ServingAuditPanel({ data, loading, error, onRefresh, compactGuards = false }) {
  const guardGridClass = compactGuards ? 'mt-4 grid gap-2' : 'mt-4 grid gap-3 md:grid-cols-2'
  const guardCardClass = compactGuards
    ? 'min-w-0 rounded border border-slate-800 bg-black/10 p-3'
    : 'rounded border border-slate-800 bg-black/10 p-3'
  const guardTitleClass = compactGuards
    ? 'mb-2 break-keep text-[10px] font-bold uppercase tracking-wider text-slate-500'
    : 'mb-2 text-[10px] font-bold uppercase tracking-wider text-slate-500'

  return (
    <section className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Serving Audit</p>
          <h2 className="mt-1 text-xl font-bold text-white">운영 모델 감사</h2>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loading}
          className="w-full rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-ai-cyan hover:text-white disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {loading ? '불러오는 중' : '감사 결과 새로고침'}
        </button>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          운영 감사 정보를 불러오는 중입니다.
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm leading-6 text-red-300">
          {error}
        </div>
      ) : !data ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          아직 운영 감사 정보가 없습니다.
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-800 bg-[#0f172a] p-4">
            <AuditBadge status={data.status}>{data.status === 'healthy' ? '전체 정상' : '즉시 확인 필요'}</AuditBadge>
            <span className="text-sm text-slate-300">차단 항목 {data.blocking_count ?? 0}건</span>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            {Object.entries(data.assets || {}).map(([assetKey, report]) => (
              <div key={assetKey} className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-bold text-white">{report.asset_type === 'STOCK' ? '주식 모델' : '코인 모델'}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">{report.message}</p>
                  </div>
                  <AuditBadge status={report.status} />
                </div>

                <div className="mt-3 flex flex-wrap gap-2 text-[10px]">
                  <span className="rounded border border-fuchsia-500/30 px-2 py-1 font-bold text-fuchsia-300">SERVING {report.serving_version || '-'}</span>
                  <span className="rounded border border-emerald-500/30 px-2 py-1 font-bold text-emerald-300">PICK {report.recommended_version || '-'}</span>
                  <span className="rounded border border-slate-600 px-2 py-1 font-bold text-slate-300">LATEST {report.latest_version || '-'}</span>
                </div>

                {report.actions?.length ? (
                  <div className="mt-3 space-y-1">
                    {report.actions.map((action) => (
                      <p key={action} className="text-[10px] leading-5 text-slate-300">{action}</p>
                    ))}
                  </div>
                ) : null}

                <div className={guardGridClass}>
                  <div className={guardCardClass}>
                    <p className={guardTitleClass}>현재 서빙 기준</p>
                    <GuardSummary guardReport={report.current_guard} compact />
                  </div>
                  <div className={guardCardClass}>
                    <p className={guardTitleClass}>추천 후보 기준</p>
                    <GuardSummary guardReport={report.recommended_guard} compact />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}

export function ModelSwitchPanel({ data, rowsByAsset, promotionChecks, loading, onActivate, activatingKey }) {
  const reports = Object.values(data?.assets || {})

  return (
    <section className="rounded-lg border border-ai-cyan/30 bg-ai-cyan/5 p-5">
      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Model Switch</p>
        <h2 className="mt-1 text-xl font-bold text-white">모델 교체 판단</h2>
        <p className="mt-2 text-xs leading-5 text-slate-400">
          자동학습 결과 중 추천 후보가 기준을 통과하면 여기에서 바로 서비스 모델로 바꿀 수 있습니다.
        </p>
      </div>

      {loading ? (
        <div className="mt-4 rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          모델 교체 정보를 불러오는 중입니다.
        </div>
      ) : !reports.length ? (
        <div className="mt-4 rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          아직 교체 판단에 사용할 서빙 감사 정보가 없습니다.
        </div>
      ) : (
        <div className="mt-4 grid gap-3 lg:grid-cols-2">
          {reports.map((report) => {
            const recommendedVersion = report.recommended_model_version || report.recommended_version
            const servingVersion = report.serving_model_version || report.serving_version
            const recommendedRow = findRegistryRow(rowsByAsset, report.asset_type, recommendedVersion)
            const guardReport = recommendedVersion ? promotionChecks?.[`${report.asset_type}:${recommendedVersion}`] : null
            const guardStatus = getSimpleGuardStatus(guardReport)
            const canActivate = Boolean(recommendedRow && !recommendedRow.is_serving)
            const failedChecks = summarizeFailedChecks(guardReport, 2)

            return (
              <article key={report.asset_type} className="rounded-lg border border-slate-800 bg-[#0f172a] p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-sm font-bold text-white">{report.asset_type === 'STOCK' ? '주식 모델' : '코인 모델'}</p>
                    <p className="mt-1 text-xs leading-5 text-slate-400">{report.message}</p>
                  </div>
                  <span className={`rounded border px-2 py-1 text-[10px] font-bold ${guardStatus.tone}`}>
                    {guardStatus.label}
                  </span>
                </div>

                <div className="mt-4 grid gap-2 text-xs sm:grid-cols-2">
                  <div className="rounded border border-slate-800 bg-black/15 p-3">
                    <p className="text-[10px] text-slate-500">현재 사용 중</p>
                    <p className="mt-1 break-all font-mono font-bold text-white">{servingVersion || '-'}</p>
                  </div>
                  <div className="rounded border border-slate-800 bg-black/15 p-3">
                    <p className="text-[10px] text-slate-500">추천 후보</p>
                    <p className="mt-1 break-all font-mono font-bold text-emerald-300">{recommendedVersion || '-'}</p>
                  </div>
                </div>

                {failedChecks.length ? (
                  <div className="mt-3 rounded border border-amber-500/30 bg-amber-950/10 px-3 py-2">
                    {failedChecks.map((item) => (
                      <p key={item} className="text-[10px] leading-5 text-amber-200">{item}</p>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-[10px] leading-5 text-slate-400">
                    기준을 통과한 후보는 강제 옵션 없이 서비스 반영할 수 있습니다.
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => recommendedRow && onActivate?.(recommendedRow)}
                  disabled={!canActivate || Boolean(activatingKey)}
                  className="mt-4 w-full rounded border border-ai-cyan/40 px-3 py-2 text-xs font-bold text-ai-cyan transition hover:bg-ai-cyan/10 disabled:cursor-not-allowed disabled:border-slate-700 disabled:text-slate-500"
                >
                  {recommendedRow?.is_serving
                    ? '이미 반영됨'
                    : activatingKey === `${recommendedRow?.asset_type}:${recommendedRow?.model_version}`
                      ? '반영 중...'
                      : canActivate
                        ? '추천 후보로 교체'
                        : '교체 후보 없음'}
                </button>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}

function RegistryStatusBadges({ row, compact = false }) {
  return (
    <>
      {row.is_latest ? (
        <span className="rounded border border-slate-600 px-2 py-1 text-[10px] font-bold text-slate-300">최신</span>
      ) : null}
      {row.is_recommended ? (
        <span className="rounded border border-emerald-500/40 px-2 py-1 text-[10px] font-bold text-emerald-300">추천</span>
      ) : null}
      {row.is_serving ? (
        <span className="rounded border border-ai-cyan/40 px-2 py-1 text-[10px] font-bold text-ai-cyan">
          {compact ? '서비스' : '서비스 적용'}
        </span>
      ) : null}
      {!row.is_latest && !row.is_recommended && !row.is_serving ? (
        <span className="rounded border border-slate-700 px-2 py-1 text-[10px] font-bold text-slate-500">분석 중</span>
      ) : null}
    </>
  )
}

function RegistryActivateButton({ row, onActivate, activatingKey, mobile = false }) {
  return (
    <button
      type="button"
      onClick={() => onActivate?.(row)}
      disabled={Boolean(activatingKey) || row.is_serving}
      className={`${mobile ? 'mt-3 w-full px-3 py-2 text-[11px]' : 'px-2 py-1 text-[10px]'} rounded border font-bold transition ${
        row.is_serving
          ? 'border-slate-700 text-slate-500'
          : 'border-ai-cyan/40 text-ai-cyan hover:bg-ai-cyan/10'
      } disabled:cursor-not-allowed disabled:opacity-50`}
    >
      {activatingKey === `${row.asset_type}:${row.model_version}`
        ? '반영 중...'
        : row.is_serving
          ? '반영됨'
          : '서비스 반영'}
    </button>
  )
}

export function RegistryPanel({
  title,
  rows = [],
  loading,
  error,
  onActivate,
  activatingKey,
  promotionChecks = {},
  promotionChecksLoading = false,
  variant = 'desktop',
}) {
  const isMobile = variant === 'mobile'

  return (
    <div className="rounded-lg border border-slate-700/80 bg-slate-surface p-5">
      <div className="mb-4">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Model Registry</p>
        <h3 className="mt-1 text-lg font-bold text-white">{title}</h3>
      </div>

      {loading ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          레지스트리 상태를 불러오는 중입니다.
        </div>
      ) : error ? (
        <div className="rounded-lg border border-red-800 bg-red-950/30 p-4 text-sm leading-6 text-red-300">
          {error}
        </div>
      ) : !rows.length ? (
        <div className="rounded-lg border border-slate-800 bg-[#0f172a] p-4 text-sm text-slate-400">
          아직 레지스트리 정보가 없습니다.
        </div>
      ) : isMobile ? (
        <div className="grid gap-2.5">
          {rows.map((row) => {
            const guardReport = promotionChecks[`${row.asset_type}:${row.model_version}`]

            return (
              <article key={`${row.asset_type}-${row.model_version}`} className="rounded-lg border border-slate-800 bg-[#0f172a] p-3 text-xs text-slate-300">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate font-mono text-sm font-bold text-white">{row.model_version}</p>
                    <p className="mt-1 truncate text-[10px] text-slate-500">{row.version || '-'}</p>
                  </div>
                  <div className="flex shrink-0 flex-wrap justify-end gap-1">
                    <RegistryStatusBadges row={row} compact />
                  </div>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="rounded bg-slate-950/50 px-2.5 py-2">
                    <p className="text-[10px] font-bold text-slate-500">CV 구분력</p>
                    <p className="mt-1 font-mono text-[11px] text-white">{formatMetric(row.cv_roc_auc || row.roc_auc)}</p>
                  </div>
                  <div className="rounded bg-slate-950/50 px-2.5 py-2">
                    <p className="text-[10px] font-bold text-slate-500">상위 10%</p>
                    <p className="mt-1 font-mono text-[11px] text-white">{formatMetric(row.cv_top10_precision)}</p>
                  </div>
                </div>

                <div className="mt-3 rounded bg-slate-950/50 px-2.5 py-2">
                  {guardReport ? (
                    <GuardSummary guardReport={guardReport} compact />
                  ) : promotionChecksLoading ? (
                    <p className="text-[10px] text-slate-500">검증 중...</p>
                  ) : (
                    <p className="text-[10px] text-slate-500">검증 정보 없음</p>
                  )}
                </div>

                <p className="mt-2 truncate font-mono text-[10px] text-slate-500" title={row.summary_path || row.metrics_path}>
                  {formatPath(row.summary_path || row.metrics_path)}
                </p>

                <RegistryActivateButton row={row} onActivate={onActivate} activatingKey={activatingKey} mobile />
              </article>
            )
          })}
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-800 bg-[#0f172a]">
          <table className="min-w-full text-left text-xs text-slate-300">
            <thead className="text-[10px] uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-3 py-2">모델 버전</th>
                <th className="px-3 py-2">CV 구분력</th>
                <th className="px-3 py-2">상위 10%</th>
                <th className="px-3 py-2">상태</th>
                <th className="px-3 py-2">승격 검증</th>
                <th className="px-3 py-2">작업</th>
                <th className="px-3 py-2">경로</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const guardReport = promotionChecks[`${row.asset_type}:${row.model_version}`]

                return (
                  <tr key={`${row.asset_type}-${row.model_version}`} className="border-t border-slate-800 align-top">
                    <td className="px-3 py-2">
                      <p className="font-mono text-white">{row.model_version}</p>
                      <p className="mt-1 text-[10px] text-slate-500">{row.version || '-'}</p>
                    </td>
                    <td className="px-3 py-2 font-mono">{formatMetric(row.cv_roc_auc || row.roc_auc)}</td>
                    <td className="px-3 py-2 font-mono">{formatMetric(row.cv_top10_precision)}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        <RegistryStatusBadges row={row} />
                      </div>
                    </td>
                    <td className="px-3 py-2">
                      {guardReport ? (
                        <GuardSummary guardReport={guardReport} compact />
                      ) : promotionChecksLoading ? (
                        <p className="text-[10px] text-slate-500">검증 중...</p>
                      ) : (
                        <p className="text-[10px] text-slate-500">검증 정보 없음</p>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <RegistryActivateButton row={row} onActivate={onActivate} activatingKey={activatingKey} />
                    </td>
                    <td className="px-3 py-2 font-mono text-[10px] text-slate-500">
                      <div className="max-w-[200px] truncate block" title={row.summary_path || row.metrics_path}>
                        {formatPath(row.summary_path || row.metrics_path)}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
