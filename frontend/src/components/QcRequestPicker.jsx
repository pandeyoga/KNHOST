/** L05 LN-050-T01 — Request QC di checkout: tidak / seluruh roll / sampling. Kirim menunggu QC bila diminta. */
const OPTS = [["none", "Tanpa QC"], ["full", "QC seluruh roll"], ["sampling", "QC sampling"]];

export default function QcRequestPicker({ value, onChange }) {
  const v = value || { mode: "none", pct: 10 };
  return (
    <div className="grid gap-1.5 rounded-xl border border-[#EFF0F2] p-2.5" data-testid="checkout-qc-request">
      <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#6B6B73]">Request QC sebelum kirim</p>
      <div className="flex flex-wrap gap-1.5">
        {OPTS.map(([k, label]) => (
          <button key={k} type="button" data-testid={`checkout-qc-${k}`} onClick={() => onChange({ ...v, mode: k })}
            className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${v.mode === k ? "bg-[#0058CC] text-white" : "bg-[#F2F2F7] text-[#3C3C43]"}`}>{label}</button>
        ))}
        {v.mode === "sampling" && (
          <label className="flex items-center gap-1 text-[11px]">
            <input type="number" min="1" max="100" className="field !w-16 !py-0.5" value={v.pct}
              onChange={(e) => onChange({ ...v, pct: e.target.value })} data-testid="checkout-qc-pct" />% roll
          </label>
        )}
      </div>
      {v.mode !== "none" && <p className="text-[10.5px] text-[#B26A00]" data-testid="checkout-qc-note">Pengiriman ditahan sampai SPK QC pesanan selesai & diterima.</p>}
    </div>
  );
}

export const qcPayload = (v) => ({ qc_request: v?.mode || "none", qc_sample_pct: Math.min(100, Math.max(1, Number(v?.pct) || 10)) });
