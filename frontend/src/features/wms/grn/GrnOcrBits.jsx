import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, ScanText, Split } from "lucide-react";
import { grnApi } from "./grnApi";

const PHASES = ["Menyiapkan foto…", "Membaca surat jalan…", "Mencocokkan baris dengan PO…", "Memeriksa angka & total…"];
const FIELD_LABEL = { dn_number: "Nomor SJ", dn_date: "Tanggal", po_refs: "Nomor PO" };
const UNIT = { yd: "yard", m: "meter", mtr: "meter" };
const fmt = (v) => (Array.isArray(v) ? v.join(", ") : v == null || v === "" ? "—" : String(v));

export function ReadingProgress({ testId = "grn-ocr-progress" }) {
  const [sec, setSec] = useState(0);
  useEffect(() => { const t = setInterval(() => setSec((s) => s + 1), 1000); return () => clearInterval(t); }, []);
  const phase = PHASES[Math.min(PHASES.length - 1, Math.floor(sec / 8))];
  return (
    <div data-testid={testId} className="flex items-center gap-3 rounded-xl border border-[#CFE0FF] bg-[#F4F8FF] p-3 text-[11.5px] text-[#0058CC]">
      <Loader2 size={16} className="animate-spin" />
      <div className="flex-1">
        <p className="font-semibold">{phase}</p>
        <div className="mt-1 h-1 overflow-hidden rounded-full bg-[#DCE8FF]">
          <div className="h-full rounded-full bg-[#0058CC] transition-[width] duration-1000" style={{ width: `${Math.min(95, 8 + sec * 1.2)}%` }} />
        </div>
      </div>
      <span className="font-mono text-[10.5px]" data-testid="grn-ocr-elapsed">{sec} dtk</span>
    </div>
  );
}

/** Draf: baca otomatis (bila OCR aktif) atau isi manual. */
export function GrnDraftActions({ grn, run, busy }) {
  const [reading, setReading] = useState(false);
  const manual = <button data-testid="grn-manual-entry" className={grn.ocr_enabled ? "secondary-button" : "primary-button"} disabled={busy || reading}
    onClick={() => run(() => grnApi.post(grn.id, "manual-entry", { expected_version: grn.version }))}>{grn.ocr_enabled ? "Isi manual saja" : "Isi manual"}</button>;
  if (grn.status === "reading" || reading) return <ReadingProgress />;
  if (!grn.ocr_enabled) {
    return (
      <div className="flex items-center justify-between rounded-xl border border-[#FFE3B3] bg-[#FFF9EE] p-3 text-[11px]" data-testid="grn-ocr-off">
        <span>OCR belum aktif. Isi surat jalan secara manual dari foto.</span>{manual}
      </div>
    );
  }
  const read = async () => { setReading(true); await run(() => grnApi.post(grn.id, "read", { expected_version: grn.version })); setReading(false); };
  const noFiles = !(grn.files || []).length;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#CFE0FF] bg-[#F9FBFF] p-3 text-[11px]" data-testid="grn-ocr-ready">
      <span>{noFiles ? "Unggah foto surat jalan dulu untuk dibaca otomatis." : "Sistem bisa membaca foto surat jalan dan mengisi kepala SJ serta baris barang. Periksa hasilnya sebelum hitung."}</span>
      <div className="flex gap-2">
        {manual}
        <button data-testid="grn-ocr-read" className="primary-button" disabled={busy || noFiles} onClick={read}><ScanText size={13} /> Baca otomatis</button>
      </div>
    </div>
  );
}

/** Hasil baca: gagal, peringatan, beda pembaca kedua (kepala SJ), ringkas run. */
export function GrnExtractionNotice({ grn }) {
  const x = grn.extraction;
  if (!x) return null;
  const runs = x.runs || [];
  const cost = runs.reduce((s, r) => s + (r.cost_usd || 0), 0);
  return (
    <div className="space-y-2" data-testid="grn-extraction">
      {x.read_failed && (
        <div data-testid="grn-ocr-failed" className="flex gap-2 rounded-xl border border-[#F5C2C0] bg-[#FDECEC] p-3 text-[11px] text-[#B4231F]">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <div><p className="font-semibold">Baca otomatis gagal <span className="font-mono">({x.error_code})</span></p><p>{x.error_message} Isi kepala SJ & baris secara manual dari foto.</p></div>
        </div>
      )}
      {(x.warnings || []).length > 0 && (
        <ul data-testid="grn-ocr-warnings" className="space-y-1 rounded-xl border border-[#FFE3B3] bg-[#FFF9EE] p-3 text-[11px] text-[#8A5300]">
          {x.warnings.map((w, i) => <li key={i} data-testid={`grn-ocr-warning-${i}`} className="flex gap-1.5"><AlertTriangle size={12} className="mt-0.5 shrink-0" />{w}</li>)}
        </ul>
      )}
      {(x.header_diff || []).length > 0 && (
        <div data-testid="grn-ocr-header-diff" className="rounded-xl border border-[#F1D08A] bg-[#FFF6E0] p-3 text-[11px]">
          <p className="mb-1 flex items-center gap-1 font-semibold text-[#8A5300]"><Split size={12} /> Pembaca kedua membaca berbeda — pastikan dari foto</p>
          {x.header_diff.map((d) => (
            <p key={d.field} data-testid={`grn-ocr-header-diff-${d.field}`}>{FIELD_LABEL[d.field] || d.field}: <span className="font-mono">{fmt(d.primary)}</span> vs <span className="font-mono">{fmt(d.second)}</span></p>
          ))}
        </div>
      )}
      {!x.read_failed && runs.length > 0 && (
        <p data-testid="grn-ocr-runs" className="text-[10px] text-[#8E8E93]">
          Dibaca otomatis ({x.prompt_version}) · {runs.map((r) => `${r.role === "second" ? "pembaca kedua" : "pembaca utama"} ${r.model}${r.status !== "ok" ? " gagal" : ""}`).join(" · ")} · biaya US${cost.toFixed(4)}
        </p>
      )}
    </div>
  );
}

/** Angka SJ yang tertulis (qty_text) untuk kolom "Tertulis". */
export function writtenQty(ln) {
  const qs = (ln.read?.quantities || []).filter((q) => String(q.role || "").startsWith("delivered_") && q.role !== "delivered_count");
  return qs.map((q) => `${q.qty_text}${q.unit_text ? ` ${q.unit_text}` : ""}`).join(" · ");
}

/** Pilihan angka untuk baris ragu (ambigu/beda) + beda pembaca kedua per baris. */
export function LineDoubtRow({ ln, colSpan, onPick }) {
  const diffs = ln.checks?.second_reader_diff || [];
  const doubt = ["ambiguous", "mismatch"].includes(ln.checks?.qty_parse);
  const [val, setVal] = useState("");
  if (!doubt && !diffs.length) return null;
  const d = ln.declared || {};
  const q = (ln.read?.quantities || []).find((x) => ["ambiguous", "mismatch"].includes(x.status) && String(x.role || "").startsWith("delivered_") && x.role !== "delivered_count");
  const cands = [...new Set([...(q?.candidates || []), q?.qty].filter((v) => v != null))];
  const unit = d.unit || UNIT[q?.unit] || q?.unit || "";
  const pick = (v) => onPick({ qty: Number(v), unit, rolls: d.rolls ?? null, weight_kg: d.weight_kg ?? null, weight_basis: d.weight_basis || null, grade: d.grade || "", lot: d.lot || "" });
  return (
    <tr data-testid={`grn-line-doubt-${ln.line_no}`} className="bg-[#FFFBF2] text-[10.5px]">
      <td />
      <td colSpan={colSpan} className="px-2 py-1.5">
        {doubt && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="font-semibold text-[#B4231F]">Angka ragu{q ? <> — tertulis <span className="font-mono">"{q.qty_text}"</span></> : ""}. Pilih yang benar:</span>
            {cands.map((c) => <button key={c} data-testid={`grn-line-pick-${ln.line_no}-${c}`} onClick={() => pick(c)} className="rounded-full border border-[#E5B34A] bg-white px-2 py-0.5 font-mono font-semibold text-[#8A5300] hover:bg-[#FFF1D1]">{c} {unit}</button>)}
            <input data-testid={`grn-line-fix-qty-${ln.line_no}`} type="number" value={val} onChange={(e) => setVal(e.target.value)} placeholder="lainnya" className="w-20 rounded border border-[#E5E5EA] px-1.5 py-0.5 font-mono" />
            <button data-testid={`grn-line-fix-save-${ln.line_no}`} disabled={val === ""} onClick={() => pick(val)} className="font-semibold text-[#0058CC] disabled:opacity-40">Simpan</button>
          </div>
        )}
        {diffs.length > 0 && (
          <p data-testid={`grn-line-diff-${ln.line_no}`} className="mt-0.5 text-[#8A5300]"><Split size={11} className="mr-1 inline" />Pembaca kedua: {diffs.map((x) => `${x.field.replace("qty:", "qty ")} ${fmt(x.primary)} → ${fmt(x.second)}`).join(" · ")}</p>
        )}
      </td>
    </tr>
  );
}
