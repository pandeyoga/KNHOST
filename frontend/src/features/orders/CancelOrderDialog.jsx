import { useEffect, useState } from "react";
import { XCircle, X } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { overlayDismiss } from "../../utils/overlayDismiss";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";
import { alasanPersetujuan, diajukan, pesanDiajukan, pesanHasil } from "./cancelRequestUtil";

/** 2026-10 — Batalkan SO dengan alasan (izin order.cancel); reservasi dilepas, sales diberi tahu.
 *  S3 (pelatihan 18 Nov) — pesanan yang sudah menerima pembayaran (uang muka): uangnya dipindah server menjadi titipan
 *  pelanggan; dialog memberi tahu sebelum dibatalkan dan pesan sesudahnya menyebut nominal yang dipindah.
 *  BTP-6 — dialog menanyakan `cancel-check`: bila wajib persetujuan, alasannya ditulis dan tombolnya menjadi
 *  "Ajukan pembatalan" (server menjawab 202, pesanan belum batal). */
export default function CancelOrderDialog({ order, onClose, onDone }) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [check, setCheck] = useState(null);

  useEffect(() => {
    let hidup = true;
    (async () => {
      try {
        const res = await axios.get(`${API}/sales-orders/${order.id}/cancel-check`, { params: { action: "cancel" } });
        if (hidup) setCheck(res?.data || null);
      } catch { /* penilaian gagal → perilaku lama; server tetap memutuskan saat kirim */ }
    })();
    return () => { hidup = false; };
  }, [order.id]);

  const perluSetuju = Boolean(check?.needs_approval);

  async function submit() {
    setBusy(true); setError("");
    try {
      const res = await axios.post(`${API}/sales-orders/${order.id}/cancel`, { reason: reason.trim() });
      if (diajukan(res)) { onDone?.(pesanDiajukan(order, res.data)); return; }
      onDone?.(pesanHasil(order, "cancel", res.data));
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
        {perluSetuju && (
          <div className="notice-bar warning mt-2" data-testid="cancel-order-approval-note">
            <span>Perlu persetujuan karena {alasanPersetujuan(check.basis, order).join(" dan ")}.
              {check.can_self_approve ? " Anda berwenang memutus, jadi pembatalan langsung dijalankan." : " Permintaan dikirim ke penyetuju; stok tetap dipesan sampai diputus."}</span>
          </div>
        )}
        {Number(order.paid_total || 0) > 0 && (
          <div className="notice-bar warning mt-2" data-testid="cancel-order-paid-note">
            <span>Pesanan ini sudah dibayar {formatCurrency(order.paid_total)}. Sesudah dibatalkan, uang itu menjadi
              titipan pelanggan (Keuangan › Piutang › Titipan & Saldo Kredit). Finance mengembalikannya lewat Kasus
              atau memakainya untuk pesanan lain.</span>
          </div>
        )}
        {error && <div className="notice-bar danger mt-2" data-testid="cancel-order-error"><span>{error}</span></div>}
        <textarea data-testid="cancel-order-reason" className="field mt-3 w-full" rows={3} placeholder="Alasan pembatalan (wajib, min. 5 karakter)"
          value={reason} onChange={(e) => setReason(e.target.value)} />
        <div className="mt-3 flex justify-end gap-2">
          <button className="secondary-button" onClick={onClose} data-testid="cancel-order-back">Kembali</button>
          <button className="primary-button !bg-[#C0392B]" data-testid="cancel-order-confirm" disabled={busy || reason.trim().length < 5} onClick={submit}>
            {busy ? (perluSetuju ? "Mengajukan…" : "Membatalkan…") : (perluSetuju && !check.can_self_approve ? "Ajukan pembatalan" : "Ya, Batalkan SO")}
          </button>
        </div>
      </div>
    </div>
  );
}
