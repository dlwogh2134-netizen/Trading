export default function AdminSummaryCard({ label, value }) {
  return (
    <div className="rounded border border-slate-800 bg-[#0f172a] p-4">
      <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-2 text-xl font-black text-white">{Number(value || 0).toLocaleString()}</p>
    </div>
  )
}
