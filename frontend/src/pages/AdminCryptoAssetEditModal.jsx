export default function AdminCryptoAssetEditModal({ editingCrypto, setEditingCrypto, saveCryptoAsset, cryptoActionLoading }) {
  if (!editingCrypto) return null

  const updateField = (field, value) => {
    setEditingCrypto((current) => ({ ...current, [field]: value }))
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm">
      <div className="w-full max-w-2xl rounded-lg border border-slate-700 bg-[#0f172a] p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-ai-cyan">Crypto Edit</p>
            <h3 className="mt-2 text-lg font-black text-white">{editingCrypto.base_symbol} 설정</h3>
          </div>
          <button type="button" onClick={() => setEditingCrypto(null)} className="rounded border border-slate-700 px-3 py-1.5 text-xs font-bold text-slate-300 hover:text-white">
            닫기
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          <label className="text-xs font-bold text-slate-300">
            한글명
            <input value={editingCrypto.display_name_ko} onChange={(event) => updateField('display_name_ko', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 text-white outline-none focus:border-ai-cyan" />
          </label>
          <label className="text-xs font-bold text-slate-300">
            영문명
            <input value={editingCrypto.display_name_en} onChange={(event) => updateField('display_name_en', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 text-white outline-none focus:border-ai-cyan" />
          </label>
          <label className="text-xs font-bold text-slate-300">
            별칭
            <input value={editingCrypto.aliases} onChange={(event) => updateField('aliases', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 text-white outline-none focus:border-ai-cyan" />
          </label>
          <label className="text-xs font-bold text-slate-300">
            기본 거래소
            <select value={editingCrypto.default_exchange} onChange={(event) => updateField('default_exchange', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 text-white outline-none focus:border-ai-cyan">
              <option value="COINONE">코인원</option>
              <option value="BINANCE">바이낸스</option>
              <option value="BINANCE_UM_FUTURES">바이낸스 선물</option>
            </select>
          </label>
          <label className="text-xs font-bold text-slate-300">
            코인원 심볼
            <input value={editingCrypto.coinone_symbol} onChange={(event) => updateField('coinone_symbol', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 font-mono text-white outline-none focus:border-ai-cyan" />
          </label>
          <label className="text-xs font-bold text-slate-300">
            바이낸스 심볼
            <input value={editingCrypto.binance_symbol} onChange={(event) => updateField('binance_symbol', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 font-mono text-white outline-none focus:border-ai-cyan" />
          </label>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <label className="flex items-center gap-2 rounded border border-slate-800 bg-[#0b1020] px-3 py-2 text-xs font-bold text-slate-300">
            <input type="checkbox" checked={editingCrypto.is_visible} onChange={(event) => updateField('is_visible', event.target.checked)} />
            검색 노출
          </label>
          <label className="flex items-center gap-2 rounded border border-slate-800 bg-[#0b1020] px-3 py-2 text-xs font-bold text-slate-300">
            <input type="checkbox" checked={editingCrypto.admin_trading_blocked} onChange={(event) => updateField('admin_trading_blocked', event.target.checked)} />
            관리자 거래 차단
          </label>
        </div>

        <label className="mt-3 block text-xs font-bold text-slate-300">
          차단 사유
          <input value={editingCrypto.admin_block_reason} onChange={(event) => updateField('admin_block_reason', event.target.value)} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 text-white outline-none focus:border-ai-cyan" />
        </label>
        <label className="mt-3 block text-xs font-bold text-slate-300">
          관리자 메모
          <textarea value={editingCrypto.admin_note} onChange={(event) => updateField('admin_note', event.target.value)} rows={3} className="mt-1 w-full rounded border border-slate-700 bg-[#0b1020] px-3 py-2 text-white outline-none focus:border-ai-cyan" />
        </label>

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={() => setEditingCrypto(null)} className="rounded border border-slate-700 px-4 py-2 text-xs font-bold text-slate-300 hover:text-white">
            취소
          </button>
          <button type="button" onClick={saveCryptoAsset} disabled={cryptoActionLoading.startsWith('save:')} className="rounded bg-blue-600 px-4 py-2 text-xs font-black text-white transition hover:bg-blue-700 disabled:opacity-60">
            {cryptoActionLoading.startsWith('save:') ? '저장 중...' : '저장'}
          </button>
        </div>
      </div>
    </div>
  )
}
