export default function AdminDeleteConfirmModal({ deleteConfirm, actionLoading, onCancel, onConfirm }) {
  if (!deleteConfirm) return null

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="w-full max-w-sm rounded-lg border border-red-500/30 bg-[#0f172a] p-5 shadow-2xl">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-red-300">삭제 확인</p>
        <h3 className="mt-2 text-lg font-black text-white">선택한 종목을 삭제하시겠습니까?</h3>
        <p className="mt-3 text-sm leading-6 text-slate-300">
          선택한 {deleteConfirm.symbols.length}개 종목의 캐시 데이터를 삭제합니다. 서버에서 참조 여부를 다시 확인하며, 참조가 있는 종목은 삭제되지 않습니다.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 transition hover:border-slate-500 hover:text-white">
            취소
          </button>
          <button type="button" onClick={onConfirm} disabled={actionLoading === 'delete'} className="rounded bg-red-500 px-4 py-2 text-xs font-black text-white transition hover:bg-red-400 disabled:opacity-60">
            삭제
          </button>
        </div>
      </div>
    </div>
  )
}
