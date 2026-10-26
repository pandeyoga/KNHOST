/**
 * MyApprovalDecisionModal — pop-up Setujui/Tolak panel Matriks divisi untuk ACC desain, permintaan pembelian dan
 * klaim selisih makloon (fase 3 · P3: `.modal-card` buatan sendiri → `FormModal`, L-03).
 *
 * PO Custom TIDAK lewat sini: dialognya `services/approvalDecisions.js` (D-07, satu dialog dengan Pesanan Khusus &
 * HP Persetujuan). ACC Sample tidak diputus dari panel (butuh pemenang supplier + harga → layar Permintaan Sample).
 * Keputusan dikirim ke endpoint dokumen ASLI (`approvalsMatrixApi`) — tidak ada jalur tulis status kedua.
 */
import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import FormModal from "../../components/FormModal";
import { formatCurrency } from "../../utils/formatters";
import { REASON_MIN_LENGTH } from "../../services/confirmService";
import {
  apiErr, approveMakloonClaim, approvePr, approveSpec, rejectMakloonClaim, rejectPr, rejectSpec,
} from "./approvalsMatrixApi";
import { STAGE_META } from "./myApprovalsParts";

async function send(item, action, form) {
  const approve = action === "approve";
  if (item.stage === "design_acc") {
    return approve
      ? approveSpec(item.id, { sku: form.sku.trim(), name: form.name.trim(), note: form.note })
      : rejectSpec(item.id, { reason: form.reason });
  }
  if (item.stage === "purchase_request") {
    return approve ? approvePr(item.id, { notes: form.note }) : rejectPr(item.id, { notes: form.reason });
  }
  if (item.stage === "makloon_claim") {
    return approve
      ? approveMakloonClaim(item.id, { step_seq: item.step_seq, note: form.note })
      : rejectMakloonClaim(item.id, { step_seq: item.step_seq, reason: form.reason });
  }
  throw new Error("Tahap ini tidak diputus dari panel Matriks divisi.");
}

/** `modal` = `{ item, action: "approve"|"reject" }` | null. `onDone(text)` setelah tersimpan. */
export default function MyApprovalDecisionModal({ modal, requesterText = (v) => v, onClose, onDone }) {
  const [form, setForm] = useState({ sku: "", name: "", note: "", reason: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const item = modal?.item;
  useEffect(() => {
    if (!modal) return;
    setForm({ sku: "", name: modal.item?.title || "", note: "", reason: "" });
    setError("");
  }, [modal]);
  if (!modal) return null;

  const approve = modal.action === "approve";
  const needSku = approve && item.stage === "design_acc";
  const canSubmit = approve
    ? (!needSku || form.sku.trim().length >= 3)
    : form.reason.trim().length >= REASON_MIN_LENGTH;   // K-14 (26 Okt): alasan minimum seragam 5 huruf

  async function submit() {
    setBusy(true); setError("");
    try {
      await send(item, modal.action, form);
      onDone?.(`${item.number} — ${approve ? "disetujui" : "ditolak"}.`);
    } catch (e) {
      setError(apiErr(e, "Keputusan gagal disimpan."));
    } finally { setBusy(false); }
  }

  return (
    <FormModal open onClose={onClose} size="sm" busy={busy} error={error} testId="my-approvals-modal"
      icon={approve ? Check : X}
      title={`${approve ? "Setujui" : "Tolak"} ${STAGE_META[item.stage]?.label || ""} · ${item.number}`}
      subtitle={`${item.title || ""}${item.amount ? ` · ${formatCurrency(item.amount)}` : ""} · diajukan ${requesterText(item.requester)}`}
      onSubmit={submit} submitDisabled={!canSubmit} submitLabel={approve ? "Setujui" : "Tolak"}
      submitTestId="my-approvals-modal-submit">
      <div className="grid gap-2.5">
        {needSku && (
          <>
            <label className="grid gap-1 text-[11px] font-semibold text-[#4A4B52]">
              Kode SKU produk baru (wajib, min. 3 huruf)
              <input className="field" data-testid="my-approvals-sku"
                value={form.sku} placeholder="mis. KN-RAYON-PARANG"
                onChange={(e) => setForm({ ...form, sku: e.target.value.toUpperCase() })} />
            </label>
            <label className="grid gap-1 text-[11px] font-semibold text-[#4A4B52]">
              Nama produk
              <input className="field" data-testid="my-approvals-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <p className="text-[10.5px] text-[#8E8E93]">
              ACC desain melahirkan produk berstatus <strong>disetujui</strong> — belum
              boleh dijual sampai dirilis ke produksi.
            </p>
          </>
        )}
        {approve ? (
          <label className="grid gap-1 text-[11px] font-semibold text-[#4A4B52]">
            Catatan (opsional)
            <textarea className="field !h-16" data-testid="my-approvals-note"
              value={form.note}
              onChange={(e) => setForm({ ...form, note: e.target.value })} />
          </label>
        ) : (
          <label className="grid gap-1 text-[11px] font-semibold text-[#4A4B52]">
            Alasan penolakan (wajib, min. {REASON_MIN_LENGTH} huruf)
            <textarea className="field !h-16" data-testid="my-approvals-reason"
              value={form.reason}
              onChange={(e) => setForm({ ...form, reason: e.target.value })} />
          </label>
        )}
      </div>
    </FormModal>
  );
}
