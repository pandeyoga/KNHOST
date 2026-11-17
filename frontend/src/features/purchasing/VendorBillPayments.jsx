import { useState } from "react";
import { Ban, Undo2 } from "lucide-react";
import { API } from "../../services/apiClient";
import { moneyPost } from "../../utils/moneyRequest";
import useIntentKey from "../../hooks/useIntentKey";
import { formatCurrency } from "../../utils/formatters";
import { askReason } from "../../services/confirmService";
import ErrorNotice from "../../components/ErrorNotice";
import { apiErrorText } from "../../utils/apiError";

// P18 APAR-01 — daftar pembayaran bill + batalkan satu pembayaran (alasan wajib).
// PK-42 (UX-09) — galat batal-bayar tampil DI SINI (di dalam pop-up rincian tagihan), bukan hanya dikirim ke halaman di
// belakang pop-up yang tak terlihat; `onError` tetap dipanggil.
export default function VendorBillPayments({ bill, canVoid, onAction, onError }) {
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  // PK-12 — anulir bayar: satu niat = satu Idempotency-Key (kirim ulang tidak membalik kas dua kali).
  const intent = useIntentKey("vbvoid");
  const pays = bill.payments || [];
  if (!pays.length) return null;

  async function voidPay(p) {
    const reason = await askReason({
      title: `Batalkan pembayaran ${formatCurrency(p.amount)}?`,
      message: `Kas ${p.cash_txn_number || ""} dianulir dan jurnalnya dibalik; hutang kembali terbuka.`,
      reasonLabel: "Alasan pembatalan (min. 5 karakter)", reasonRequired: true, reasonMinLength: 5,
      confirmLabel: "Batalkan pembayaran", danger: true, testId: "vb-payment-void-confirm",
    });
    if (!reason) return;
    setBusy(p.id);
    setErr("");
    try {
      const body = { notes: reason };
      const r = await intent.send({ id: p.id, aksi: "void", ...body },
        (k) => moneyPost(`${API}/vendor-bills/${bill.id}/payments/${p.id}/void`, body, k));
      onAction?.("payment_void", r.data);
    } catch (e) {
      const msg = apiErrorText(e, "Gagal membatalkan pembayaran.");
      setErr(msg);
      onError?.(msg);
    } finally { setBusy(""); }
  }

  return (
    <div className="rounded-md border border-kn-divider overflow-hidden" data-testid="vb-payments">
      <div className="px-3 py-1.5 bg-kn-neutral-soft text-fs-12 font-bold uppercase text-kn-text-2">Pembayaran</div>
      {err && (
        <div className="px-3 pt-2">
          <ErrorNotice message={err} onDismiss={() => setErr("")} testId="vb-payments-error" />
        </div>
      )}
      <ul className="divide-y divide-kn-divider">
        {pays.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-2 px-3 py-1.5 text-fs-13" data-testid={`vb-payment-${p.id}`}>
            <span className={`font-bold tabular-nums ${p.voided ? "line-through text-kn-text-2" : ""}`}>{formatCurrency(p.amount)}</span>
            <span className="text-kn-text-2">{p.method} · {p.cash_txn_number}</span>
            {p.voided && (
              <>
                <span className="status-pill bg-kn-danger-soft text-kn-danger-text" data-testid={`vb-payment-voided-${p.id}`}>
                  <Ban size={12} aria-hidden="true" /> Dibatalkan
                </span>
                {/* S4 (pelatihan 18 Nov) — alasan & pembatal di luar pil: pil status berhuruf kapital tiap kata dan tidak
                    turun baris, jadi alasan tampil "Salah Rekening: Dibayar Dari Kas Toko…" dan terpotong. */}
                <span className="min-w-0 break-words text-fs-12 text-kn-text-2" data-testid={`vb-payment-void-reason-${p.id}`}>
                  {p.void_reason}{p.voided_by ? ` · ${p.voided_by}` : ""}
                </span>
              </>
            )}
            {!p.voided && canVoid && (
              <button type="button" className="ghost-button btn-sm ml-auto" disabled={!!busy}
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
