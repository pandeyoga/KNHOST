import { useEffect, useMemo, useState } from "react";
import { Printer, Save } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { apiText, inspectLine } from "./inspectionsApi";

/**
 * Lembar Inspect — Trial 22 Okt 2026 (F5, permintaan pemilik): form QC 4-point MENYERUPAI kertas "DATA HASIL INSPECT".
 * Satu lembar banyak roll: baris = roll, kolom = interval 15 yard, sel = kode cacat + poin (mis. "CG2 KO1"); kanan:
 * Poin, STDRT (poin × 3600 ÷ (yard × lebar inci)), Grade roll, Grade A / A1 / B (yard), Perbaikan, Keterangan. Disimpan
 * lewat jalur yang SAMA dengan pop-up per roll (`inspectLine`, bagian QC) — tidak ada sumber angka kedua.
 * Keputusan pemilik (F5): grade roll DIISI PETUGAS dari total poin — sistem tidak mengisi otomatis (kecuali
 * `qc.grade_from_points` dinyalakan); kode cacat bebas, artinya ditafsirkan pengguna; yard per grade = catatan.
 */
const IV = 15;
const MIN_COLS = 8;            // kertas: 0-15 … 105-120
const TOKEN = /^([A-Za-z]{1,4})([1-4])$/;
const n2 = (v) => (v === "" || v == null || Number.isNaN(Number(v)) ? "" : String(v));

export const parseCell = (text) => {
  const out = []; const bad = [];
  String(text || "").split(/[\s,;]+/).filter(Boolean).forEach((t) => {
    const m = TOKEN.exec(t.trim());
    if (m) out.push({ code: m[1].toUpperCase(), point_value: Number(m[2]) }); else bad.push(t);
  });
  return { defects: out, bad };
};

export const stdrt = (points, yards, widthInch) => {
  const y = Number(yards); const w = Number(widthInch);
  return y > 0 && w > 0 ? Math.round((Number(points || 0) * 3600 / (y * w)) * 100) / 100 : null;
};

function rowFromLine(ln) {
  const cells = {};
  (ln.defects || []).forEach((d) => {
    if (d.interval == null) return;
    const tok = `${d.code || "X"}${d.point_value}`;
    const rep = Math.max(1, Number(d.count || 1));
    cells[d.interval] = [cells[d.interval], ...Array(rep).fill(tok)].filter(Boolean).join(" ");
  });
  const yd = ln.inspect_form?.inspect_length_yard ?? (String(ln.unit || "").toLowerCase() === "yard" ? ln.quantity : "");
  return {
    cells, yards: n2(yd), widthInch: ln.width_actual ? n2(Math.round((ln.width_actual / 2.54) * 10) / 10) : "",
    A: n2(ln.yard_split?.A), A1: n2(ln.yard_split?.A1), B: n2(ln.yard_split?.B),
    grade: ln.grade_rule?.grade_source === "user" ? (ln.grade_after || "") : "",
    repair: ln.repair_note || "", remark: ln.qc_remark || ln.remark || "", reject: ln.decision === "tolak", dirty: false,
  };
}

export default function InspectSheetGrid({ doc, meta, editable, onSaved }) {
  const lines = useMemo(() => (doc.lines || []).filter((ln) => ln.roll_id), [doc.lines]);
  const [rows, setRows] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [grades, setGrades] = useState([]);
  const gradeAuto = Boolean(meta?.grade_auto);
  useEffect(() => { setRows(Object.fromEntries(lines.map((ln) => [ln.id, rowFromLine(ln)]))); }, [lines]);
  useEffect(() => {
    axios.get(`${API}/master/grades`).then((r) => setGrades((r.data || []).filter((g) => g.active !== false))).catch(() => setGrades([]));
  }, []);

  const cols = Math.max(MIN_COLS, ...lines.map((ln) => Math.ceil(Number(rows[ln.id]?.yards || 0) / IV - 1e-9)));
  const upd = (id, patch) => setRows((r) => ({ ...r, [id]: { ...r[id], ...patch, dirty: true } }));
  const points = (r) => Object.values(r?.cells || {}).reduce((s, c) => s + parseCell(c).defects.reduce((a, d) => a + d.point_value, 0), 0);
  const codes = (meta?.defect_codes || []).map((c) => c.code);

  async function saveAll() {
    const dirty = lines.filter((ln) => rows[ln.id]?.dirty);
    const invalid = dirty.flatMap((ln) => Object.entries(rows[ln.id].cells).flatMap(([iv, c]) => parseCell(c).bad.map((b) => `${ln.roll_no} ${iv * IV}-${(Number(iv) + 1) * IV}: "${b}"`)));
    if (invalid.length) { setErr(`Isian sel tidak dikenali (tulis KODE+POIN, mis. CG2): ${invalid.join("; ")}`); return; }
    const noGrade = gradeAuto ? [] : dirty.filter((ln) => !rows[ln.id].grade).map((ln) => ln.roll_no);
    if (noGrade.length) { setErr(`Pilih grade roll: ${noGrade.join(", ")} — grade ditentukan petugas QC dari total poin.`); return; }
    setBusy(true); setErr("");
    try {
      let fresh = null;
      for (const ln of dirty) {
        const r = rows[ln.id];
        const defects = Object.entries(r.cells).flatMap(([iv, c]) => parseCell(c).defects.map((d) => ({ ...d, interval: Number(iv), count: 1, note: "" })));
        fresh = await inspectLine(doc.id, ln.id, {
          part: "qc", defects, inspect_length_yard: r.yards === "" ? null : Number(r.yards),
          width_actual: r.widthInch === "" ? null : Math.round(Number(r.widthInch) * 2.54 * 10) / 10,
          yard_split: { A: Number(r.A || 0), A1: Number(r.A1 || 0), B: Number(r.B || 0) },
          repair_note: r.repair, remark: r.remark, decision: r.reject ? "tolak" : "", grade: r.grade || "",
        });
      }
      if (fresh) onSaved?.(fresh);
    } catch (e) { setErr(apiText(e, "Gagal menyimpan lembar inspect.")); }
    finally { setBusy(false); }
  }

  function printSheet() {
    const head = Array.from({ length: cols }, (_, i) => `<th>${i * IV}-${(i + 1) * IV}</th>`).join("");
    const body = lines.map((ln) => {
      const r = rows[ln.id] || {}; const p = points(r);
      return `<tr><td>${ln.roll_no || ""}</td><td>${r.yards || ""}</td><td>${r.widthInch ? `${r.widthInch}"` : ""}</td>${Array.from({ length: cols }, (_, i) => `<td>${r.cells?.[i] || ""}</td>`).join("")}<td>${p}</td><td>${stdrt(p, r.yards, r.widthInch) ?? ""}</td><td>${r.grade || ""}</td><td>${r.A || ""}</td><td>${r.A1 || ""}</td><td>${r.B || ""}</td><td>${r.repair || ""}</td><td>${r.remark || ""}</td></tr>`;
    }).join("");
    const w = window.open("", "_blank");
    if (!w) return;
    w.document.write(`<!doctype html><html lang="id"><head><meta charset="utf-8"><title>Data Hasil Inspect ${doc.number}</title><style>body{font-family:Arial;font-size:10px}table{border-collapse:collapse;width:100%}td,th{border:1px solid #000;padding:2px 3px;text-align:center}</style></head><body>
<h3>DATA HASIL INSPECT · ${doc.number}</h3><p>Periode: ${doc.spk_date || ""} · Supplier: ${doc.supplier_name || "-"} · Artikel: ${lines[0]?.article || "-"}</p>
<table><thead><tr><th rowspan="2">No roll</th><th rowspan="2">Yds</th><th rowspan="2">Lebar</th><th colspan="${cols}">Posisi cacat (yard)</th><th rowspan="2">Poin</th><th rowspan="2">STDRT</th><th rowspan="2">Grade roll</th><th colspan="2">Grade A</th><th rowspan="2">B yds</th><th rowspan="2">Perbaikan</th><th rowspan="2">Ket.</th></tr><tr>${head}<th>A</th><th>A1</th></tr></thead><tbody>${body}</tbody></table>
<p>Poin: 1 = s.d. 3" · 2 = 3-6" · 3 = 6-9" · 4 = &gt;9"/lubang · Kode: ${codes.join(", ")}</p><script>window.onload=function(){window.print();}</script></body></html>`);
    w.document.close();
  }

  const cell = "border border-[#D9DCE1] px-1 py-0.5 text-center";
  const inp = "w-full min-w-[44px] bg-transparent text-center text-[11px] outline-none";
  return (
    <div data-testid="ins-sheet" className="section-card overflow-hidden">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#EFF0F2] px-3 py-2">
        <div className="text-[11px] text-[#3C3C43]">
          <b className="text-[12px]">Data hasil inspect</b> · Periode {doc.spk_date || "—"} · Supplier {doc.supplier_name || "—"} · Artikel {lines[0]?.article || "—"}
        </div>
        <div className="flex gap-2">
          <button type="button" className="secondary-button !h-8" onClick={printSheet} data-testid="ins-sheet-print"><Printer size={13} /> Cetak lembar</button>
          {editable && <button type="button" className="primary-button !h-8" disabled={busy} onClick={saveAll} data-testid="ins-sheet-save"><Save size={13} /> {busy ? "Menyimpan…" : "Simpan lembar"}</button>}
        </div>
      </div>
      {err && <p data-testid="ins-sheet-error" className="bg-[#FDECEC] px-3 py-1.5 text-[11px] text-[#9B1C1C]">{err}</p>}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-[11px]">
          <thead className="bg-[#FAFBFC] text-[10.5px] text-[#6B6B73]">
            <tr>
              <th rowSpan={2} className={cell}>No roll</th><th rowSpan={2} className={cell}>Yds</th><th rowSpan={2} className={cell}>Lebar (inci)</th>
              <th colSpan={cols} className={cell}>Posisi cacat (yard) — isi KODE+POIN, mis. CG2 KO1</th>
              <th rowSpan={2} className={cell}>Poin</th><th rowSpan={2} className={cell}>STDRT</th>
              <th rowSpan={2} className={cell}>Grade roll{gradeAuto ? "" : " *"}</th>
              <th colSpan={2} className={cell}>Grade A (yds)</th><th rowSpan={2} className={cell}>B yds</th>
              <th rowSpan={2} className={cell}>Perbaikan</th><th rowSpan={2} className={cell}>Ket.</th><th rowSpan={2} className={cell}>Tolak</th>
            </tr>
            <tr>
              {Array.from({ length: cols }, (_, i) => <th key={i} className={cell}>{i * IV}-{(i + 1) * IV}</th>)}
              <th className={cell}>A</th><th className={cell}>A1</th>
            </tr>
          </thead>
          <tbody>
            {lines.map((ln) => {
              const r = rows[ln.id] || { cells: {} };
              const p = points(r);
              const st = stdrt(p, r.yards, r.widthInch);
              const ro = !editable;
              return (
                <tr key={ln.id} data-testid={`ins-sheet-row-${ln.id}`} className={r.dirty ? "bg-[#FFFBF0]" : ""}>
                  <td className={`${cell} whitespace-nowrap font-semibold`}>{ln.roll_no}</td>
                  <td className={cell}><input className={inp} readOnly={ro} value={r.yards} onChange={(e) => upd(ln.id, { yards: e.target.value })} data-testid={`ins-sheet-yds-${ln.id}`} /></td>
                  <td className={cell}><input className={inp} readOnly={ro} value={r.widthInch} onChange={(e) => upd(ln.id, { widthInch: e.target.value })} data-testid={`ins-sheet-width-${ln.id}`} /></td>
                  {Array.from({ length: cols }, (_, i) => (
                    <td key={i} className={`${cell} ${parseCell(r.cells?.[i]).bad.length ? "bg-[#FDECEC]" : ""}`}>
                      <input className={inp} readOnly={ro} list="ins-defect-codes" value={r.cells?.[i] || ""} data-testid={`ins-sheet-cell-${ln.id}-${i}`}
                        onChange={(e) => upd(ln.id, { cells: { ...r.cells, [i]: e.target.value } })} />
                    </td>
                  ))}
                  <td className={`${cell} font-semibold tabular-nums`} data-testid={`ins-sheet-points-${ln.id}`}>{p}</td>
                  <td className={`${cell} tabular-nums`} data-testid={`ins-sheet-stdrt-${ln.id}`}>{st ?? "—"}</td>
                  <td className={`${cell} ${!gradeAuto && r.dirty && !r.grade ? "bg-[#FFF6E0]" : ""}`}>
                    <select className={`${inp} min-w-[52px]`} disabled={ro} value={r.grade || ""} data-testid={`ins-sheet-grade-${ln.id}`}
                      onChange={(e) => upd(ln.id, { grade: e.target.value })}>
                      <option value="">{gradeAuto ? "saran" : "—"}</option>
                      {grades.map((g) => <option key={g.code} value={g.code}>{g.code}</option>)}
                    </select>
                  </td>
                  {["A", "A1", "B"].map((k) => (
                    <td key={k} className={cell}><input className={inp} readOnly={ro} value={r[k]} onChange={(e) => upd(ln.id, { [k]: e.target.value })} /></td>
                  ))}
                  <td className={cell}><input className={`${inp} min-w-[90px] text-left`} readOnly={ro} value={r.repair} onChange={(e) => upd(ln.id, { repair: e.target.value })} /></td>
                  <td className={cell}><input className={`${inp} min-w-[90px] text-left`} readOnly={ro} value={r.remark} onChange={(e) => upd(ln.id, { remark: e.target.value })} /></td>
                  <td className={cell}><input type="checkbox" disabled={ro} checked={!!r.reject} onChange={(e) => upd(ln.id, { reject: e.target.checked })} data-testid={`ins-sheet-reject-${ln.id}`} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <datalist id="ins-defect-codes">{codes.flatMap((c) => [1, 2, 3, 4].map((n) => <option key={`${c}${n}`} value={`${c}${n}`} />))}</datalist>
      </div>
      <div data-testid="ins-sheet-legend" className="flex flex-wrap gap-x-5 gap-y-1 border-t border-[#EFF0F2] px-3 py-2 text-[10.5px] text-[#6B6B73]">
        <span>Poin: 1 = s.d. 3" · 2 = 3–6" · 3 = 6–9" · 4 = &gt;9" / lubang</span>
        <span>Kode cacat: {(meta?.defect_codes || []).map((c) => (c.label ? `${c.code} (${c.label})` : c.code)).join(" · ") || "—"}</span>
        <span>STDRT = poin × 3600 ÷ (yds × lebar inci)</span>
        <span data-testid="ins-sheet-grade-rule">{gradeAuto ? "Grade roll kosong = saran sistem dari total poin" : "Grade roll diisi petugas QC dari total poin — sistem tidak mengisi otomatis"} · Grade A/A1/B (yds) = catatan pembagian panjang</span>
      </div>
    </div>
  );
}
