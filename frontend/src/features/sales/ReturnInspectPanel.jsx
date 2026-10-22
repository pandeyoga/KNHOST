/** R2 — Panel inspeksi retur (4-point). approved → inspecting → inspected.
 *  Entry defect 4-point (P1..P4) → poin & grade + rekomendasi outcome.
 *  Trial 22 Okt (F5, keputusan pemilik) — grade DIPILIH petugas QC dari total poin; sistem tidak mengisi otomatis
 *  (kecuali `qc.grade_from_points` dinyalakan → kosong = saran sistem). */
import { useEffect, useState } from "react";
import { ClipboardCheck, Loader2, Play } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import { fmtNum } from "./ReturnShared";

const CONDITIONS = [{ value: "ok", label: "Baik" }, { value: "minor", label: "Cacat ringan" }, { value: "damaged", label: "Rusak" }];
const PTS = [1, 2, 3, 4];

// Preview grade sisi klien (ambang default A<=20, B<=40); backend tetap otoritatif.
function previewGrade(pts) { return pts <= 20 ? "A" : pts <= 40 ? "B" : "C"; }
function recFromGrade(g, cond) {
  if (cond === "damaged" && g === "C") return "reject";
  return { A: "refund", B: "store_credit", C: "nego" }[g] || "refund";
}
const OUT_LABEL = { refund: "Refund", store_credit: "Store Credit", nego: "Nego", reject: "Tolak" };

export default function ReturnInspectPanel({ ret, onStartInspect, onCompleteInspect }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [grades, setGrades] = useState([]);
  const [gradeAuto, setGradeAuto] = useState(false);
  useEffect(() => {
    axios.get(`${API}/master/grades`).then((r) => setGrades((r.data || []).filter((g) => g.active !== false))).catch(() => setGrades([]));
    axios.get(`${API}/qc/grade-thresholds`, { params: ret.entity_id ? { entity_id: ret.entity_id } : {} })
      .then((r) => setGradeAuto(Boolean(r.data?.grade_auto))).catch(() => setGradeAuto(false));
  }, [ret.entity_id]);
  const [rows, setRows] = useState(() =>
    (ret.items || []).map((it) => ({
      p: { 1: 0, 2: 0, 3: 0, 4: 0 },
      grade: "",
      condition: it.condition || "ok",
      accepted_qty: it.quantity_returned ?? 0,
      // L08 LN-082 — qty aktual hasil ukur per roll (default = klaim per roll).
      roll_actuals: Object.fromEntries((it.roll_ids || []).map((rid) => [rid, (it.roll_qtys || {})[rid] ?? ""])),
    })));

  const upd = (i, patch) => setRows((r) => r.map((x, idx) => (idx === i ? { ...x, ...patch } : x)));
  const setPt = (i, pv, v) => setRows((r) => r.map((x, idx) => (idx === i ? { ...x, p: { ...x.p, [pv]: Math.max(0, parseInt(v, 10) || 0) } } : x)));
  const points = (row) => PTS.reduce((s, pv) => s + pv * (row.p[pv] || 0), 0);

  async function start() { setBusy(true); try { await onStartInspect(ret); } finally { setBusy(false); } }
  async function complete() {
    const noGrade = gradeAuto ? [] : rows.map((r, i) => (r.grade ? null : (ret.items?.[i]?.product_name || `baris ${i + 1}`))).filter(Boolean);
    if (noGrade.length) { setErr(`Pilih grade: ${noGrade.join(", ")} — grade ditentukan petugas QC dari total poin.`); return; }
    setErr("");
    setBusy(true);
    try {
      const inspections = rows.map((r, i) => ({
        index: i,
        grade: r.grade || "",
        defects: PTS.map((pv) => ({ point_value: pv, count: r.p[pv] || 0 })).filter((d) => d.count > 0),
        condition: r.condition,
        accepted_qty: parseFloat(r.accepted_qty) || 0,
        roll_actuals: Object.fromEntries(Object.entries(r.roll_actuals || {})
          .filter(([, v]) => v !== "" && !Number.isNaN(parseFloat(v))).map(([k, v]) => [k, parseFloat(v)])),
      }));
      await onCompleteInspect(ret, inspections, "");
    } finally { setBusy(false); }
  }

  if (ret.status === "approved") {
    return (
      <div className="section-card" data-testid="inspect-start-card">
        <div className="section-header"><ClipboardCheck size={14} /> Inspeksi Barang (Wajib · 4-point)</div>
        <div className="section-notes text-muted">
          Kebijakan mewajibkan inspeksi 4-point sebelum retur diselesaikan. Mulai inspeksi untuk menilai defect → grade → rekomendasi outcome.
        </div>
        <button data-testid="start-inspect-btn" className="primary-button mt-2" onClick={start} disabled={busy}>
          {busy ? <Loader2 size={13} className="spin" /> : <Play size={13} />} Mulai Inspeksi
        </button>
      </div>
    );
  }
  if (ret.status !== "inspecting") return null;

  return (
    <div className="section-card" data-testid="inspect-form-card">
      <div className="section-header"><ClipboardCheck size={14} /> Inspeksi 4-Point</div>
      <div className="text-[10.5px] text-[#6B6B73] mb-2">Isi jumlah defect per bobot poin (1–4). Poin = Σ(bobot × jumlah). Grade: A ≤20 · B ≤40 · C &gt;40.</div>
      <div className="overflow-x-auto">
        <table className="data-table">
          <thead>
            <tr><th>Produk</th><th>Qty</th><th>P1</th><th>P2</th><th>P3</th><th>P4</th><th>Poin</th><th>Grade ≈</th><th>Rekomendasi</th><th>Kondisi</th><th>Qty OK</th></tr>
          </thead>
          <tbody>
            {(ret.items || []).map((it, i) => {
              const pts = points(rows[i]); const g = rows[i].grade || (gradeAuto ? previewGrade(pts) : "");
              return (
                <tr key={i} data-testid={`inspect-row-${i}`}>
                  <td className="max-w-[140px] truncate">{it.product_name || it.product_id}</td>
                  <td className="font-mono">{fmtNum(it.quantity_returned)}</td>
                  {PTS.map((pv) => (
                    <td key={pv} style={{ maxWidth: 52 }}>
                      <input data-testid={`inspect-p${pv}-${i}`} type="number" min="0" className="field tabular-nums"
                        value={rows[i].p[pv]} onChange={(e) => setPt(i, pv, e.target.value)} />
                    </td>
                  ))}
                  <td className="font-mono font-semibold tabular-nums" data-testid={`inspect-points-${i}`}>{pts}</td>
                  <td style={{ minWidth: 92 }}>
                    <KNSelect data-testid={`inspect-grade-${i}`} value={rows[i].grade} className="field" searchable={false}
                      placeholder={gradeAuto ? `saran ${previewGrade(pts)}` : "Pilih"} onValueChange={(v) => upd(i, { grade: v })}
                      options={grades.map((gr) => ({ value: gr.code, label: gr.code }))} />
                  </td>
                  <td className="text-[10.5px]" data-testid={`inspect-rec-${i}`}>{g ? OUT_LABEL[recFromGrade(g, rows[i].condition)] : "—"}</td>
                  <td style={{ minWidth: 110 }}>
                    <KNSelect data-testid={`inspect-condition-${i}`} value={rows[i].condition} className="field"
                      onValueChange={(v) => upd(i, { condition: v })} options={CONDITIONS} />
                  </td>
                  <td style={{ maxWidth: 80 }}>
                    <input data-testid={`inspect-acceptedqty-${i}`} type="number" min="0" className="field tabular-nums"
                      value={rows[i].accepted_qty} onChange={(e) => upd(i, { accepted_qty: e.target.value })} />
                  </td>
                </tr>
              );
            })}
            {(ret.items || []).map((it, i) => (it.roll_ids || []).length > 0 && (
              <tr key={`ra-${i}`} data-testid={`inspect-roll-actuals-${i}`}>
                <td colSpan={11} className="text-[10.5px]">
                  <span className="mr-2 font-semibold text-[#6B6B73]">Qty aktual per roll ({it.unit}):</span>
                  {it.roll_ids.map((rid) => (
                    <label key={rid} className="mr-3 inline-flex items-center gap-1">
                      <span className="font-mono">{(it.roll_nos || {})[rid] || rid}</span>
                      <span className="text-[#9A9BA3]">klaim {fmtNum((it.roll_qtys || {})[rid])}</span>
                      <input data-testid={`inspect-roll-actual-${rid}`} type="number" min="0" step="0.01"
                        className="field tabular-nums" style={{ width: 80 }} value={rows[i].roll_actuals[rid]}
                        onChange={(e) => upd(i, { roll_actuals: { ...rows[i].roll_actuals, [rid]: e.target.value } })} />
                    </label>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {err && <p data-testid="inspect-error" className="mt-2 rounded bg-[#FDECEC] px-2 py-1 text-[11px] font-semibold text-[#9B1C1C]">{err}</p>}
      <button data-testid="complete-inspect-btn" className="primary-button mt-2" onClick={complete} disabled={busy}>
        {busy ? <Loader2 size={13} className="spin" /> : <ClipboardCheck size={13} />} Selesaikan Inspeksi
      </button>
    </div>
  );
}
