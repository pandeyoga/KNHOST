import { useCallback, useEffect, useState } from "react";
import { Plus, ScanLine, Undo2 } from "lucide-react";
import { KNSelect } from "../../../components/KNSelect";
import useDomainEnums from "../../../hooks/useDomainEnums";
import { ErrorBox, inputCls } from "./GrnBits";
import { errText, grnApi } from "./grnApi";
import PackingChecklist from "./GrnPackingChecklist";
import useIntentKey from "../../../hooks/useIntentKey";

function CountLine({ grn, ln, rolls, gradeOptions, run, canCount }) {
  const [raw, setRaw] = useState("");
  const [m, setM] = useState({ length: "", weight_kg: "", lot: "", grade: "A" });
  const [seq, setSeq] = useState(null);
  const t = ln.target || {};
  // Trial 22 Okt (D2) — panjang boleh diketik dalam satuan SJ/PO atau satuan dasar produk; server mengonversi.
  // 23 Okt — kg bukan satuan panjang: berat selalu lewat kolom Kg. Kain rajut (kg saja) → kolom panjang disembunyikan.
  const unitChoices = [...new Set([t.unit, t.base_unit].filter((u) => u && u.toLowerCase() !== "kg"))];
  const [lenUnit, setLenUnit] = useState(unitChoices[0] || "");
  const intent = useIntentKey(`grn-${grn.id}-${ln.line_no}`);
  const scan = async () => {
    const body = { raw: raw.trim() };
    if (body.raw && await run(() => intent.send({ scan: body }, (k) => grnApi.post(grn.id, `lines/${ln.line_no}/scan-label`, body, k)))) setRaw("");
  };
  const add = async () => {
    const body = { length: Number(m.length || 0), length_unit: sisa ? "" : lenUnit, weight_kg: Number(m.weight_kg || 0), lot: m.lot, grade: m.grade, expected_seq: seq };
    const ok = await run(() => intent.send({ roll: body }, (k) => grnApi.post(grn.id, `lines/${ln.line_no}/rolls`, body, k)));
    if (ok) { setM((x) => ({ ...x, length: "", weight_kg: "" })); setSeq(null); }
  };
  const editable = canCount && grn.status === "counting";
  const sisa = ln.role === "byproduct";
  const showLen = sisa || unitChoices.length > 0;
  const cols = 4 + (showLen ? 1 : 0) + (!sisa && unitChoices.length > 1 ? 1 : 0);
  return (
    <div data-testid={`grn-count-line-${ln.line_no}`} className="space-y-2 rounded-xl border border-[#EFF0F2] bg-white p-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[12px] font-bold">{ln.line_no}. {t.product_name || ln.read?.description}{sisa && <span data-testid={`grn-count-byproduct-${ln.line_no}`} className="ml-1.5 rounded-full bg-[#FFF6E5] px-1.5 py-0.5 text-[9.5px] font-semibold text-[#B26A00]">Barang sisa</span>}</p>
          {(t.supplier_item_name || t.supplier_color) && <p data-testid={`grn-count-supplier-alias-${ln.line_no}`} className="text-[11px] text-[#8C4A00]">Versi supplier: {[t.supplier_item_name, t.supplier_color && `warna ${t.supplier_color}`].filter(Boolean).join(" · ")}</p>}
          <p className="text-[10.5px] text-[#6B6B73]">{t.po_number || `${t.mko_number || ""} langkah ${t.step_seq || ""}`} · {t.sku} · satuan {t.unit}</p>
        </div>
        <p data-testid={`grn-count-total-${ln.line_no}`} className="text-right text-[12px] font-bold tabular-nums">
          {ln.counted?.rolls || 0} roll<span className="block text-[10.5px] font-semibold text-[#0058CC]">{ln.counted?.qty || 0} {t.unit}</span>
        </p>
      </div>
      {(ln.expected_rolls || []).length > 0 && (
        <PackingChecklist ln={ln} unit={t.unit} picked={seq} editable={editable}
          onPick={(r) => { setSeq(r ? r.seq : null); if (r) setM((x) => ({ ...x, lot: r.lot || x.lot, grade: r.grade || x.grade })); }} />
      )}
      {editable && (<>
        {t.type === "po_task" && (
          <div className="flex gap-2">
            <input data-testid={`grn-count-scan-${ln.line_no}`} className={`${inputCls} font-mono`} placeholder="Scan / ketik label roll supplier lalu Enter"
              value={raw} onChange={(e) => setRaw(e.target.value)} onKeyDown={(e) => e.key === "Enter" && scan()} />
            <button data-testid={`grn-count-scan-btn-${ln.line_no}`} className="primary-button" onClick={scan}><ScanLine size={13} /></button>
          </div>
        )}
        {/* UAT 24 Okt (P16.1) — isian berlabel; HP 2 kolom, tablet 3, desktop sesuai jumlah isian (dulu 4–6 kolom
            tanpa breakpoint → ±50px per kolom di HP, placeholder terpotong). */}
        <div className={`grid grid-cols-2 items-end gap-2 sm:grid-cols-3 ${{ 4: "lg:grid-cols-4", 5: "lg:grid-cols-5", 6: "lg:grid-cols-6" }[cols]}`}>
          {showLen && <label><span className="field-label">{sisa ? "Qty sisa" : `Panjang (${lenUnit})`}</span>
            <input data-testid={`grn-count-length-${ln.line_no}`} type="number" className={inputCls} placeholder={sisa ? "Qty sisa (mis. kg)" : `Panjang (${lenUnit})`} value={m.length} onChange={(e) => setM({ ...m, length: e.target.value })} /></label>}
          {!sisa && unitChoices.length > 1 && (
            <label><span className="field-label">Satuan panjang</span>
              <KNSelect data-testid={`grn-count-unit-${ln.line_no}`} value={lenUnit} onValueChange={setLenUnit} searchable={false}
                options={unitChoices.map((u) => ({ value: u, label: u === t.unit ? `${u} (SJ/PO)` : `${u} (stok)` }))} /></label>
          )}
          <label><span className="field-label">Berat (kg)</span>
            <input data-testid={`grn-count-kg-${ln.line_no}`} type="number" className={inputCls} placeholder="0" value={m.weight_kg} onChange={(e) => setM({ ...m, weight_kg: e.target.value })} /></label>
          <label><span className="field-label">{sisa ? "Lot (opsional)" : "Lot"}</span>
            <input data-testid={`grn-count-lot-${ln.line_no}`} className={inputCls} value={m.lot} onChange={(e) => setM({ ...m, lot: e.target.value })} /></label>
          <label><span className="field-label">Grade</span>
            <KNSelect data-testid={`grn-count-grade-${ln.line_no}`} value={m.grade} onValueChange={(v) => setM({ ...m, grade: v })} options={gradeOptions} searchable={false} /></label>
          <button data-testid={`grn-count-add-${ln.line_no}`} className="secondary-button col-span-2 justify-center sm:col-span-1" onClick={add}><Plus size={13} /> {seq ? `Ukur roll #${seq}` : "Roll manual"}</button>
        </div>
      </>)}
      <ul className="divide-y divide-[#EFF0F2] text-[11px]">
        {rolls.map((r) => (
          <li key={r.id} data-testid={`grn-count-roll-${r.id}`} className="flex items-center gap-2 py-1">
            <span className="w-20 font-mono font-semibold">{r.roll_no || "makloon"}</span>
            <span className="flex-1 tabular-nums">{r.length_initial} {r.unit}{r.actual_task_qty != null && t.unit && r.unit && t.unit !== r.unit ? ` (= ${r.actual_task_qty} ${t.unit})` : ""}{r.weight_kg ? ` · ${r.weight_kg} kg` : ""} · lot {r.lot || "-"} · {r.grade}</span>
            <span className="text-[10px] text-[#6B6B73]">{r.scan_source === "count" ? "hitung" : "label"}</span>
            {editable && ["receiving", "makloon"].includes(r.status) && (
              <button data-testid={`grn-count-undo-${r.id}`} aria-label="Batalkan roll" onClick={() => run(() => grnApi.del(grn.id, `rolls/${r.id}`))}><Undo2 size={13} className="text-[#B4231F]" /></button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function GrnCountPanel({ grn, onChange, canCount }) {
  const [rolls, setRolls] = useState([]);
  const [err, setErr] = useState("");
  const { options } = useDomainEnums();
  const gradeOptions = options("grade");
  const load = useCallback(() => grnApi.rolls(grn.id).then(setRolls).catch(() => {}), [grn.id]);
  useEffect(() => { load(); }, [load, grn.version]);
  const run = async (fn) => {
    setErr("");
    try { const r = await fn(); onChange(r?.grn || r); return true; } catch (e) { setErr(errText(e)); return false; }
  };
  const lines = (grn.lines || []).filter((ln) => !ln.is_non_stock && ln.decision === "accept" && ln.target);
  const total = lines.reduce((s, ln) => s + (ln.counted?.rolls || 0), 0);
  return (
    <div className="space-y-3" data-testid="grn-count-panel">
      {grn.blind && <p data-testid="grn-blind-note" className="rounded-lg bg-[#EEF4FF] px-3 py-2 text-[11px] text-[#0058CC]">Hitung buta aktif — angka surat jalan sengaja tidak ditampilkan. Ukur dan catat apa adanya.</p>}
      {lines.map((ln) => <CountLine key={ln.line_no} grn={grn} ln={ln} rolls={rolls.filter((r) => r.grn_line_no === ln.line_no)} gradeOptions={gradeOptions} run={run} canCount={canCount} />)}
      <ErrorBox text={err} />
      {grn.status === "counting" && canCount && (
        <div className="flex items-center justify-between rounded-xl bg-[#FAFBFC] p-3">
          <span data-testid="grn-count-roll-total" className="text-[12px] font-semibold">{total} roll dihitung</span>
          <button data-testid="grn-finish-count" className="primary-button" onClick={() => run(() => grnApi.post(grn.id, "finish-count", { expected_version: grn.version }))}>Selesai hitung</button>
        </div>
      )}
    </div>
  );
}
