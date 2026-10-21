/**
 * Cek UI UAT v3 (S5) — kredit pelanggan terblokir di Review checkout: dulu tombol [Buat Sales Order] mati tanpa jalan
 * keluar (di HP tidak ada layar Pelanggan › Ajukan Override). Kini Sales mengajukan override kredit langsung dari sini;
 * setelah Manajer/Finance menyetujui (Pusat Persetujuan / Pelanggan › Override Kredit), checkout membuka pembuatan SO.
 */
import { useState } from "react";
import { Loader2, Send } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";

export default function CreditOverrideRequest({ customer, amount }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  if (!customer?.id) return null;
  const send = async () => {
    setBusy(true); setMsg(null);
    try {
      await axios.post(`${API}/customers/${customer.id}/credit-override`,
        { customer_id: customer.id, amount: Math.round(Number(amount) || 0), reason: reason.trim() });
      setMsg({ ok: true, text: "Override kredit diajukan — menunggu persetujuan Manajer/Finance. Setelah disetujui, buka lagi checkout ini lalu [Buat Sales Order]." });
      setOpen(false);
    } catch (e) {
      setMsg({ ok: false, text: e?.response?.data?.detail || "Gagal mengajukan override kredit." });
    } finally { setBusy(false); }
  };
  return (
    <div className="mt-1.5" data-testid="credit-override-request">
      {!open && !msg?.ok && (
        <button type="button" className="secondary-button !py-1 !text-[11px]" data-testid="credit-override-open" onClick={() => setOpen(true)}>
          Ajukan Override Kredit ({formatCurrency(amount)})
        </button>
      )}
      {open && (
        <div className="space-y-1">
          <textarea className="field w-full !py-1 text-[11px]" rows={2} value={reason} data-testid="credit-override-reason"
                    onChange={(e) => setReason(e.target.value)} placeholder="Alasan (wajib) — mis. pelanggan lama, pembayaran lancar, PO besar sudah dikonfirmasi" />
          <div className="flex gap-1">
            <button type="button" className="primary-button !py-1 !text-[11px]" disabled={busy || reason.trim().length < 5}
                    data-testid="credit-override-submit" onClick={send}>
              {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />} Ajukan
            </button>
            <button type="button" className="secondary-button !py-1 !text-[11px]" onClick={() => setOpen(false)}>Batal</button>
          </div>
        </div>
      )}
      {msg && <p className={`mt-1 text-[10.5px] ${msg.ok ? "text-[#1B7F4B]" : "text-[#C0392B]"}`} data-testid="credit-override-msg">{msg.text}</p>}
    </div>
  );
}
