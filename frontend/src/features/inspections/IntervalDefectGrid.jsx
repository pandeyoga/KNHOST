/** L05 LN-051 — form cacat per interval 15 yard (0–150, berlanjut bila roll lebih panjang). Satu baris = satu kejadian. */
import { Plus, Trash2 } from "lucide-react";

const IV = 15;
export const intervalCount = (len) => Math.max(10, Math.ceil((Number(len) || 0) / IV - 1e-9));
const ivLabel = (i) => `${i * IV}–${(i + 1) * IV}`;

export default function IntervalDefectGrid({ length, setLength, rows, setRows, stockUnit, stockQty }) {
  const n = intervalCount(length);
  const upd = (i, patch) => setRows(rows.map((r, k) => (k === i ? { ...r, ...patch } : r)));
  const byIv = rows.reduce((m, r) => { if (r.interval !== "" && Number(r.count) > 0) m[r.interval] = (m[r.interval] || 0) + Number(r.count); return m; }, {});
  return (
    <div className="grid gap-2" data-testid="ins-interval-grid">
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="block">
          <span className="field-label">Panjang diinspeksi (yard)</span>
          <input data-testid="ins-inspect-length" type="number" min="0" step="0.01" className="field" value={length}
            onChange={(e) => setLength(e.target.value)} placeholder="mis. 124" />
        </label>
        <p className="self-end text-[11px] text-[#6B6B73]" data-testid="ins-stock-unit-note">
          Stok roll tetap {stockQty} {stockUnit || ""} — posisi cacat selalu dalam yard. {n} interval × 15 yard{n > 10 ? " (berlanjut melewati 150)" : ""}.
        </p>
      </div>
      <div className="flex flex-wrap gap-1" data-testid="ins-interval-summary">
        {Array.from({ length: n }, (_, i) => (
          <span key={i} data-testid={`ins-interval-chip-${i}`}
            className={`rounded-md px-1.5 py-0.5 text-[10px] tabular-nums ${byIv[i] ? "bg-[#FFF6E5] font-bold text-[#B26A00]" : "bg-[#F2F2F7] text-[#6B6B73]"}`}>
            {ivLabel(i)}{byIv[i] ? ` · ${byIv[i]}` : ""}
          </span>
        ))}
      </div>
      {rows.map((r, i) => (
        <div key={`d${i}`} className="grid grid-cols-[1.3fr_1fr_0.8fr_0.7fr_1.4fr_auto] gap-1.5 max-sm:grid-cols-3" data-testid={`ins-defect-row-${i}`}>
          <select className="field !py-1 text-[11.5px]" value={r.interval} onChange={(e) => upd(i, { interval: e.target.value === "" ? "" : Number(e.target.value) })} data-testid={`ins-defect-interval-${i}`}>
            <option value="">Interval…</option>
            {Array.from({ length: n }, (_, k) => <option key={k} value={k}>{ivLabel(k)} yd</option>)}
          </select>
          <input className="field !py-1 text-[11.5px]" placeholder="Kode" value={r.code} onChange={(e) => upd(i, { code: e.target.value })} data-testid={`ins-defect-code-${i}`} />
          <select className="field !py-1 text-[11.5px]" value={r.point_value} onChange={(e) => upd(i, { point_value: Number(e.target.value) })} data-testid={`ins-defect-point-${i}`}>
            {[1, 2, 3, 4].map((p) => <option key={p} value={p}>{p} poin</option>)}
          </select>
          <input type="number" min="1" className="field !py-1 text-[11.5px]" value={r.count} onChange={(e) => upd(i, { count: e.target.value })} data-testid={`ins-defect-count-${i}`} />
          <input className="field !py-1 text-[11.5px]" placeholder="Perbaikan / keterangan" value={r.note} onChange={(e) => upd(i, { note: e.target.value })} data-testid={`ins-defect-note-${i}`} />
          <button type="button" className="secondary-button !px-1.5 !py-0.5" onClick={() => setRows(rows.filter((_, k) => k !== i))} data-testid={`ins-defect-remove-${i}`} aria-label="Hapus"><Trash2 size={12} /></button>
        </div>
      ))}
      <button type="button" className="secondary-button w-fit !py-0.5 text-[11px]" data-testid="ins-defect-add"
        onClick={() => setRows([...rows, { interval: "", code: "", point_value: 1, count: 1, note: "" }])}><Plus size={12} /> Tambah kejadian cacat</button>
    </div>
  );
}
