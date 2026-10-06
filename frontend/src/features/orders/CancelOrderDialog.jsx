import { useState } from "react";
import { XCircle, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { overlayDismiss } from "../../utils/overlayDismiss";
import { apiErrorText } from "../../utils/apiError";

/** 2026-10 — Batalkan SO dengan alasan (izin order.cancel); reservasi dilepas, sales diberi tahu. */
export default function CancelOrderDialog({ order, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit() {
    setBusy(true); setError("");
    try {
      const res = await axios.post(`${API}/sales-orders/${order.id}/cancel`, { reason: reason.trim() });
      const refs = res.data.open_fulfillment_refs || [];
      onDone?.(`${order.number} dibatalkan, stok dilepas.` + (refs.length ? ` Tindak lanjuti dokumen pemenuhan: ${refs.join(", ")}.` : ""));
    } catch (e) { setError(apiErrorText(e, "Gagal membatalkan pesanan.")); }
    finally { setBusy(false); }
  }

  return (
    <div className="modal-overlay" style={{ zIndex: 180 }} data-testid="cancel-order-dialog" {...overlayDismiss(onClose)}>
      <div className="modal-card" style={{ maxWidth: 460 }} onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-2">
          <p className="modal-title flex items-center gap-2"><XCircle size={15} className="text-[#C0392B]" /> Batalkan {order.number}?</p>
          <button className="icon-button" onClick={onClose} data-testid="cancel-order-close"><X size={16} /></button>
        </div>
        <p className="modal-subtitle mt-1">Roll yang direservasi dilepas dan tugas gudang dibatalkan. Sales pemilik pesanan mendapat pemberitahuan.</p>
        {error && <div className="notice-bar danger mt-2" data-testid="cancel-order-error"><span>{error}</span></div>}
        <textarea data-testid="cancel-order-reason" className="field mt-3 w-full" rows={3} placeholder="Alasan pembatalan (wajib, min. 5 karakter)"
          value={reason} onChange={(e) => setReason(e.target.value)} />
        <div className="mt-3 flex justify-end gap-2">
          <button className="secondary-button" onClick={onClose} data-testid="cancel-order-back">Kembali</button>
          <button className="primary-button !bg-[#C0392B]" data-testid="cancel-order-confirm" disabled={busy || reason.trim().length < 5} onClick={submit}>
            {busy ? "Membatalkan…" : "Ya, Batalkan SO"}
          </button>
        </div>
      </div>
    </div>
  );
}
