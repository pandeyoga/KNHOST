import { useState } from "react";
import { CheckCircle2, Pencil, Trash2 } from "lucide-react";
import { KNSelect } from "../../../components/KNSelect";
import { LineDoubtBody, writtenQty } from "./GrnOcrBits";
import { LineEditForm, MappingCaption, PoValue, ROLE_OPTIONS, lineState, tgtBody, tgtKey } from "./GrnLineRow";
import { grnApi } from "./grnApi";

/** Baris SJ versi HP: satu kartu per baris — angka besar, tombol besar, edit di tempat. */
export default function GrnLineCard({ grn, ln, targets, gradeOptions, run }) {
  const [edit, setEdit] = useState(false);
  const d = ln.declared || {};
  const [status, tone] = lineState(ln);
  const n = ln.line_no;
  const ocr = ln.read?.source === "ocr";
  const patch = (body) => run(() => grnApi.patch(grn.id, `lines/${n}`, { expected_version: grn.version, ...body }));
  return (
    <div data-testid={`grn-line-card-${n}`} className={`space-y-2 rounded-xl border p-3 ${ocr && !ln.verified ? "border-[#F1D08A] bg-[#FFFCF5]" : "border-[#EFF0F2] bg-white"}`}>
      <div className="flex items-start gap-2">
        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#F2F2F7] text-[11px] font-bold">{n}</span>
        <div className="min-w-0 flex-1">
          <p className="text-[12.5px] font-semibold leading-snug">{ln.read?.description || ln.read?.item_code || "Tanpa deskripsi"}</p>
          {(ln.read?.po_ref || ln.ocr_po_ref !== undefined) && <p className="text-[11px] text-[#6B6B73]">PO <PoValue ln={ln} /></p>}
        </div>
        <span data-testid={`grn-line-card-status-${n}`} className={`whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-semibold ${tone}`}>{status}</span>
      </div>
      {edit ? (
        <LineEditForm ln={ln} gradeOptions={gradeOptions} onCancel={() => setEdit(false)} onSave={async (b) => { if (await patch(b)) setEdit(false); }} />
      ) : (<>
        <div className="grid grid-cols-3 gap-2 rounded-lg bg-[#FAFBFC] p-2 text-center">
          <div><p className="text-[9.5px] font-bold uppercase text-[#8E8E93]">Qty</p><p data-testid={`grn-line-card-qty-${n}`} className="font-mono text-[15px] font-bold tabular-nums">{d.qty ?? "-"} <span className="text-[11px] font-semibold">{d.unit}</span></p></div>
          <div><p className="text-[9.5px] font-bold uppercase text-[#8E8E93]">Roll</p><p className="font-mono text-[15px] font-bold tabular-nums">{d.rolls ?? "-"}</p></div>
          <div><p className="text-[9.5px] font-bold uppercase text-[#8E8E93]">Kg</p><p className="font-mono text-[15px] font-bold tabular-nums">{d.weight_kg ?? "-"}</p></div>
        </div>
        {ocr && <p className="text-[10.5px] text-[#6B6B73]">Tertulis di SJ: <span className="font-mono">{writtenQty(ln) || "-"}</span>{d.lot ? ` · lot ${d.lot}` : ""}{d.grade ? ` · grade ${d.grade}` : ""}</p>}
        <LineDoubtBody ln={ln} onPick={(declared) => patch({ declared })} />
        <KNSelect data-testid={`grn-line-card-target-${n}`} value={tgtKey(ln.target)} onValueChange={(v) => patch({ target: tgtBody(v) })}
          options={targets.map((t) => ({ value: tgtKey(t), label: t.type === "po_task" ? `${t.po_number} · ${t.product_name}` : `${t.mko_number}/${t.step_seq} · ${t.product_name}` }))} placeholder="Pilih target PO…" />
        {ln.target?.type === "mko_step" && !ln.is_non_stock && (
          <KNSelect data-testid={`grn-line-card-role-${n}`} value={ln.role || ""} onValueChange={(v) => patch({ role: v })} options={ROLE_OPTIONS} placeholder="Output atau barang sisa?" searchable={false} />
        )}
        {ocr && ln.target && <MappingCaption ln={ln} />}
        {ln.corrected && <p className="text-[10px] font-semibold text-[#0058CC]">Dikoreksi: {(ln.corrected_fields || []).join(", ")}</p>}
        {ln.checks?.uom_message && <p className="text-[10.5px] text-[#B4231F]">{ln.checks.uom_message}</p>}
        <div className="flex flex-wrap items-center gap-2 pt-1">
          {ocr && !ln.verified && ln.decision !== "reject_line" && (
            <button data-testid={`grn-line-card-verify-${n}`} className="primary-button flex-1 justify-center !py-2" onClick={() => patch({ verified: true })}><CheckCircle2 size={14} /> Sesuai foto</button>
          )}
          <button data-testid={`grn-line-card-edit-${n}`} className="secondary-button flex-1 justify-center !py-2" onClick={() => setEdit(true)}><Pencil size={13} /> Ubah</button>
          <button data-testid={`grn-line-card-toggle-${n}`} className="px-2 py-2 text-[11px] font-semibold text-[#0058CC]" onClick={() => patch({ decision: ln.decision === "reject_line" ? "accept" : "reject_line" })}>{ln.decision === "reject_line" ? "Terima" : "Tolak"}</button>
          <button data-testid={`grn-line-card-delete-${n}`} aria-label="Hapus baris" className="p-2" onClick={() => run(() => grnApi.del(grn.id, `lines/${n}`, { expected_version: grn.version }))}><Trash2 size={14} className="text-[#B4231F]" /></button>
        </div>
      </>)}
    </div>
  );
}
