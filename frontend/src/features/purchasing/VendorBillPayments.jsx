import { useState } from "react";
import { Undo2 } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import { askReason } from "../../services/confirmService";

// P18 APAR-01 — daftar pembayaran bill + batalkan satu pembayaran (alasan wajib).
export default function VendorBillPayments({ bill, canVoid, onAction, onError }) {
  const [busy, setBusy] = useState("");
  const pays = bill.payments || [];
  if (!pays.length) return null;

  async function voidPay(p) {
    const reason = await askReason({
      title: `Batalkan pembayaran ${formatCurrency(p.amount)}?`,
      message: `Kas ${p.cash_txn_number || ""} di-void dan jurnalnya dibalik; hutang kembali terbuka.`,
      reasonLabel: "Alasan pembatalan (min. 5 karakter)", reasonRequired: true, reasonMinLength: 5,
      confirmLabel: "Batalkan pembayaran", danger: true, testId: "vb-payment-void-confirm",
    });
    if (!reason) return;
    setBusy(p.id);
    try {
      const r = await axios.post(`${API}/vendor-bills/${bill.id}/payments/${p.id}/void`, { notes: reason });
      onAction?.("payment_void", r.data);
    } catch (e) {
      onError?.(e.response?.data?.detail || "Gagal membatalkan pembayaran.");
    } finally { setBusy(""); }
  }

  return (
    <div className="rounded-md border border-[#EFF0F2] overflow-hidden" data-testid="vb-payments">
      <div className="px-3 py-1.5 bg-[#FAFBFC] text-[10px] font-bold uppercase text-[#6B6B73]">Pembayaran</div>
      <ul className="divide-y divide-[#EFF0F2]">
        {pays.map((p) => (
          <li key={p.id} className="flex items-center gap-2 px-3 py-1.5 text-[11.5px]" data-testid={`vb-payment-${p.id}`}>
            <span className={`font-bold tabular-nums ${p.voided ? "line-through text-[#9A9BA3]" : ""}`}>{formatCurrency(p.amount)}</span>
            <span className="text-[#6B6B73]">{p.method} · {p.cash_txn_number}</span>
            {p.voided && <span className="pill pill-danger" data-testid={`vb-payment-voided-${p.id}`}>Dibatalkan — {p.void_reason}</span>}
            {!p.voided && canVoid && (
              <button className="ghost-button ml-auto flex items-center gap-1 text-[11px]" disabled={!!busy}
                      data-testid={`vb-payment-void-${p.id}`} onClick={() => voidPay(p)}>
                <Undo2 size={12} /> Batalkan
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
