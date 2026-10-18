/** L10 LN-101 — ringkasan rekonsiliasi opname per roll; tiap situasi dibedakan. */
const TONE = {
  matched: "text-[#1B7E3B]", missing: "text-[#C0392B]", wrong_address: "text-[#B26A00]", qty_diff: "text-[#B26A00]",
  tag_damaged: "text-[#B26A00]", unreadable: "text-[#6B6B73]", foreign: "text-[#C0392B]", unknown: "text-[#C0392B]",
  moved_after_cutoff: "text-[#0058CC]", delta_in: "text-[#0058CC]",
};

export default function RollReconcileTable({ rec, open, onRecount, binName }) {
  const L = rec.labels || {};
  const chips = Object.entries(rec.counts || {}).filter(([, n]) => n > 0);
  return (
    <div className="grid gap-2" data-testid="roll-reconcile">
      <div className="flex flex-wrap gap-2 text-[11.5px]">
        <span data-testid="roll-reconcile-expected">Diharapkan <b>{rec.expected_rolls}</b></span>
        <span data-testid="roll-reconcile-scanned">· Discan <b>{rec.scanned_rolls}</b></span>
        <span data-testid="roll-reconcile-duplicates">· Scan ganda <b>{rec.duplicates}</b> (tidak menambah stok)</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chips.map(([k, n]) => (
          <span key={k} data-testid={`roll-kind-${k}`} className={`rounded border border-[#EFF0F2] px-2 py-0.5 text-[11px] font-semibold ${TONE[k] || ""}`}>{L[k] || k}: {n}</span>
        ))}
      </div>
      <div className="max-h-72 overflow-auto rounded border border-[#EFF0F2]">
        <table className="w-full text-[11.5px]">
          <thead className="bg-[#FAFBFC] text-[10px] uppercase text-[#6B6B73]"><tr><th className="p-1.5 text-left">Roll</th><th className="text-left">Situasi</th><th className="text-right">Sistem</th><th className="text-right">Fisik</th><th className="text-left pl-2">Penerapan</th></tr></thead>
          <tbody>
            {(rec.lines || []).map((s) => (
              <tr key={s.id} className="border-t border-[#F2F3F5]" data-testid={`roll-line-${s.roll_id || s.code}`}>
                <td className="p-1.5 font-mono">{s.roll_no || s.code}</td>
                <td>{s.kinds.map((k) => <span key={k} className={`mr-1 ${TONE[k] || ""}`}>{L[k] || k}</span>)}</td>
                <td className="text-right tabular-nums">{s.roll_id ? `${s.live_qty} ${s.unit}` : "—"}</td>
                <td className="text-right tabular-nums">{s.measured_qty ?? "—"}</td>
                <td className="pl-2" data-testid={`roll-line-adj-${s.roll_id || s.code}`}>{s.adjustment ? (s.adjustment.status === "applied"
                  ? [s.adjustment.new_roll_no && `roll baru ${s.adjustment.new_roll_no} · ${s.adjustment.qty} ${s.unit || ""}`,
                     s.adjustment.relocated && `dipindah ke ${binName?.(s.adjustment.relocated.to) || s.adjustment.relocated.to}`,
                     s.adjustment.qty_diff && `qty ${s.adjustment.qty_diff > 0 ? "+" : ""}${s.adjustment.qty_diff}`].filter(Boolean).join(" · ") || "diterapkan"
                  : s.adjustment.message) : ""}</td>
              </tr>
            ))}
            {(rec.missing || []).map((e) => (
              <tr key={e.roll_id} className="border-t border-[#F2F3F5]" data-testid={`roll-missing-${e.roll_id}`}>
                <td className="p-1.5 font-mono">{e.roll_no}</td><td className={TONE.missing}>{L.missing}</td>
                <td className="text-right tabular-nums">{e.qty} {e.unit}</td><td className="text-right">—</td>
                <td className="pl-2 text-[#6B6B73]" data-testid={`roll-missing-state-${e.roll_id}`}>
                  {e.adjustment ? `dihapus dari stok (${e.adjustment.written_off} ${e.unit})`
                    : e.recount ? `dihitung ulang oleh ${e.recount.by} — dihapus saat finalisasi`
                      : open ? <button className="secondary-button !py-0.5 !text-[11px]" data-testid={`roll-missing-recount-${e.roll_id}`} onClick={() => onRecount(e.roll_id)}>Hitung ulang: tetap tidak ada</button>
                        : "belum dihitung ulang — tidak dihapus"}
                </td>
              </tr>
            ))}
            {(rec.moved_after_cutoff || []).map((e) => (
              <tr key={e.roll_id} className="border-t border-[#F2F3F5]" data-testid={`roll-moved-${e.roll_id}`}>
                <td className="p-1.5 font-mono">{e.roll_no}</td><td className={TONE.moved_after_cutoff}>{L.moved_after_cutoff}</td>
                <td className="text-right tabular-nums">{e.qty} → {e.live_qty} {e.unit}</td><td className="text-right">—</td><td className="pl-2 text-[#6B6B73]">sudah diposting, tidak diulang</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-[10.5px] text-[#6B6B73]" data-testid="roll-policy">{rec.policy}</p>
    </div>
  );
}
