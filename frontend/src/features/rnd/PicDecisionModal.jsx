/** L03 LN-034 — keputusan PIC atas uji ulang GAGAL: uji ulang, keputusan operasional, atau override (tetap GAGAL). */
import { useState } from "react";
import { Gavel } from "lucide-react";
import FormModal from "../../components/FormModal";
import { Field, Footer, Hint } from "./RndField";

const ACTIONS = [
  ["retest", "Uji ulang", "Siklus baru untuk supplier yang sama, mereferensi siklus ini."],
  ["operational_note", "Keputusan operasional", "Catat tindak lanjut & cakupan dokumen/supplier."],
  ["override", "Override", "Lanjut walau gagal — hasil tetap tercatat GAGAL. Butuh izin khusus."],
];

export default function PicDecisionModal({ sample, canOverride, onClose, onConfirm, busy, error = "" }) {
  const rv = sample.revalidation || {};
  const [action, setAction] = useState("retest");
  const [reason, setReason] = useState("");
  const [docs, setDocs] = useState("");
  const [scopeNote, setScopeNote] = useState("");
  const scope = action === "retest" ? {} : { documents: docs.split(",").map((d) => d.trim()).filter(Boolean), note: scopeNote };
  const body = { action, reason, scope };
  return (
    <FormModal open onClose={onClose} size="md" testId="pic-decision-modal" icon={Gavel} error={error}
      title="Keputusan PIC · Uji Ulang Gagal" subtitle={`${sample.number} · ${rv.supplier_name || ""} · ${sample.product_sku || ""}`}
      footer={<Footer onClose={onClose} onConfirm={() => onConfirm(body)} busy={busy} icon={Gavel} testId="pic-decision-confirm"
        confirmLabel="Simpan keputusan" disabled={reason.trim().length < 5} title={reason.trim().length < 5 ? "Alasan min. 5 karakter" : ""} />}>
      <div className="grid gap-3">
        <Hint tone="danger" testId="pic-decision-fail-note">Temuan: <b>{sample.decision?.note || "—"}</b>. Hasil gagal tidak akan berubah menjadi ACC.</Hint>
        <div className="grid gap-1.5" data-testid="pic-action-picker">
          {ACTIONS.map(([v, l, d]) => {
            const locked = v === "override" && !canOverride;
            return (
              <button key={v} type="button" disabled={locked} data-testid={`pic-action-${v}`} onClick={() => setAction(v)}
                className={`rounded-lg border px-3 py-2 text-left text-[11.5px] transition-[background-color,border-color] disabled:opacity-50 ${action === v ? "border-[#0058CC] bg-[#F2F7FF]" : "border-[#EFF0F2] bg-white"}`}>
                <b>{l}</b>{locked ? " · tidak berizin" : ""}<span className="block text-[10.5px] text-[#6B6B73]">{d}</span>
              </button>
            );
          })}
        </div>
        <Field label="Alasan keputusan * (min. 5 karakter)">
          <textarea className="field" rows={2} data-testid="pic-decision-reason" value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="mis. ganti batch benang lalu uji ulang" />
        </Field>
        {action !== "retest" && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Field label="Cakupan dokumen (pisahkan koma)">
              <input className="field" data-testid="pic-scope-documents" value={docs} onChange={(e) => setDocs(e.target.value)} placeholder="mis. PO-00012, MKO-00004" />
            </Field>
            <Field label="Catatan cakupan">
              <input className="field" data-testid="pic-scope-note" value={scopeNote} onChange={(e) => setScopeNote(e.target.value)} placeholder="mis. hanya stok batch lama" />
            </Field>
          </div>
        )}
      </div>
    </FormModal>
  );
}
