import {
  buildJobLogClipboardText,
  formatSignedDelta,
  getHealthLabel,
  getHealthTone,
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
