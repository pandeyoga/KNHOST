import { useCallback, useEffect, useState } from "react";
import { Plus, ScanLine, Undo2 } from "lucide-react";
import { KNSelect } from "../../../components/KNSelect";
import useDomainEnums from "../../../hooks/useDomainEnums";
import { ErrorBox, inputCls } from "./GrnBits";
import { errText, grnApi } from "./grnApi";

function CountLine({ grn, ln, rolls, gradeOptions, run, canCount }) {
  const [raw, setRaw] = useState("");
  const [m, setM] = useState({ length: "", weight_kg: "", lot: "", grade: "A" });
  const t = ln.target || {};
  const scan = async () => { if (raw.trim() && await run(() => grnApi.post(grn.id, `lines/${ln.line_no}/scan-label`, { raw: raw.trim() }))) setRaw(""); };
  const add = async () => {
    const ok = await run(() => grnApi.post(grn.id, `lines/${ln.line_no}/rolls`, { length: Number(m.length || 0), weight_kg: Number(m.weight_kg || 0), lot: m.lot, grade: m.grade }));
    if (ok) setM((x) => ({ ...x, length: "", weight_kg: "" }));
  };
  const editable = canCount && grn.status === "counting";
  return (
    <div data-testid={`grn-count-line-${ln.line_no}`} className="space-y-2 rounded-xl border border-[#EFF0F2] p-3">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-[12px] font-bold">{ln.line_no}. {t.product_name || ln.read?.description}</p>
          <p className="text-[10.5px] text-[#6B6B73]">{t.po_number || `${t.mko_number || ""} langkah ${t.step_seq || ""}`} · {t.sku} · satuan {t.unit}</p>
        </div>
        <p data-testid={`grn-count-total-${ln.line_no}`} className="text-right text-[12px] font-bold tabular-nums">
          {ln.counted?.rolls || 0} roll<span className="block text-[10.5px] font-semibold text-[#0058CC]">{ln.counted?.qty || 0} {t.unit}</span>
        </p>
      </div>
      {editable && (<>
        {t.type === "po_task" && (
          <div className="flex gap-2">
            <input data-testid={`grn-count-scan-${ln.line_no}`} className={`${inputCls} font-mono`} placeholder="Scan / ketik label roll supplier lalu Enter"
              value={raw} onChange={(e) => setRaw(e.target.value)} onKeyDown={(e) => e.key === "Enter" && scan()} />
            <button data-testid={`grn-count-scan-btn-${ln.line_no}`} className="primary-button" onClick={scan}><ScanLine size={13} /></button>
          </div>
        )}
        <div className="grid grid-cols-5 gap-2">
          <input data-testid={`grn-count-length-${ln.line_no}`} type="number" className={inputCls} placeholder={`Panjang (${t.unit})`} value={m.length} onChange={(e) => setM({ ...m, length: e.target.value })} />
          <input data-testid={`grn-count-kg-${ln.line_no}`} type="number" className={inputCls} placeholder="Kg" value={m.weight_kg} onChange={(e) => setM({ ...m, weight_kg: e.target.value })} />
          <input data-testid={`grn-count-lot-${ln.line_no}`} className={inputCls} placeholder="Lot" value={m.lot} onChange={(e) => setM({ ...m, lot: e.target.value })} />
          <KNSelect data-testid={`grn-count-grade-${ln.line_no}`} value={m.grade} onValueChange={(v) => setM({ ...m, grade: v })} options={gradeOptions} searchable={false} />
          <button data-testid={`grn-count-add-${ln.line_no}`} className="secondary-button justify-center" onClick={add}><Plus size={13} /> Roll manual</button>
        </div>
      </>)}
      <ul className="divide-y divide-[#EFF0F2] text-[11px]">
        {rolls.map((r) => (
          <li key={r.id} data-testid={`grn-count-roll-${r.id}`} className="flex items-center gap-2 py-1">
            <span className="w-20 font-mono font-semibold">{r.roll_no || "makloon"}</span>
            <span className="flex-1 tabular-nums">{r.length_initial} {r.unit}{r.weight_kg ? ` · ${r.weight_kg} kg` : ""} · lot {r.lot || "-"} · {r.grade}</span>
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
