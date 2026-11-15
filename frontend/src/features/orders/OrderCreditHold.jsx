/**
 * CR-T3 — kartu kredit di detail pesanan: lencana **Tahan kredit** + alasan + tombol **Periksa ulang kredit**
 * (`POST /api/sales-orders/{id}/credit-recheck`, izin `order.update`), "Izin kredit dipakai", dan "Bayar penuh sebelum
 * kirim" untuk pesanan yang lolos gerbang karena termin bayar dulu (K-27). Tidak tampil bila tidak ada yang perlu dikatakan.
 */
import { lazy, Suspense, useState } from "react";
import { Loader2, RefreshCw, ShieldAlert, ShieldCheck, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { can } from "../../config/roles";
import { formatCurrency, formatDateTime } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
const CreditOverrideModal = lazy(() => import("../crm/CreditOverrideModal"));   // dimuat saat dibuka

const TITIK = { pesanan_dibuat: "saat pesanan dibuat", pesanan_diubah: "saat nilai pesanan naik",
  lepas_gudang: "saat dilepas ke gudang", surat_jalan: "saat barang akan dikirim", periksa_ulang: "saat diperiksa ulang" };

export default function OrderCreditHold({ order, user, onRefresh }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [izin, setIzin] = useState(false);
  if (!order) return null;
  const held = !!order.credit_hold;
  const used = order.credit_override_used || null;
  const payFirst = !!order.pay_before_ship;
  if (!held && !used && !payFirst) return null;
  const info = order.credit_hold_info || {};
  const canRecheck = can(user?.permissions, "order", "update");
  const canAsk = can(user?.permissions, "credit_override", "create");

  async function recheck() {
    setBusy(true); setErr(""); setMsg("");
    try {
      const r = await axios.post(`${API}/sales-orders/${order.id}/credit-recheck`, {});
      setMsg(r.data?.released ? "Kredit kini memenuhi syarat — tahanan dilepas." : `Masih ditahan: ${r.data?.message || "kredit belum memenuhi syarat."}`);
      await onRefresh?.();
    } catch (e) {
      setErr(apiErrorText(e, "Periksa ulang kredit gagal."));
    } finally { setBusy(false); }
  }

  return (
    <div className="section-card section-pad" data-testid="order-credit-card">
      {held && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            <span className="status-pill status-rejected whitespace-nowrap" data-testid="order-credit-hold-badge">
              <ShieldAlert size={12} aria-hidden="true" /> Tahan kredit
            </span>
            <span className="text-fs-12 text-kn-text-2">
              sejak {formatDateTime(info.since)}{info.checkpoint ? ` · ${TITIK[info.checkpoint] || "diperiksa"}` : ""}
            </span>
          </div>
          <ul className="mt-1.5 space-y-0.5 text-fs-12 text-kn-text" data-testid="order-credit-hold-reasons">
            {(info.reasons || []).map((r, i) => <li key={i}>• {r.message}</li>)}
            {!(info.reasons || []).length && <li>• Menunggu keputusan izin kredit.</li>}
          </ul>
          <p className="mt-1 text-fs-12 text-kn-text-2">Pesanan tidak bisa dilepas ke gudang atau dikirim sampai kredit memenuhi syarat:
            pembayaran yang tercatat melepas tahanan sendiri, atau izin kredit disetujui.</p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {canRecheck ? (
              <button type="button" className="secondary-button btn-sm whitespace-nowrap" disabled={busy} onClick={recheck}
                data-testid="order-credit-recheck">
                {busy ? <Loader2 size={12} className="animate-spin" aria-hidden="true" /> : <RefreshCw size={12} aria-hidden="true" />}
                Periksa ulang kredit
              </button>
            ) : (
              <span className="text-fs-12 text-kn-text-2" data-testid="order-credit-recheck-none">Periksa ulang dilakukan pemegang akses mengubah pesanan.</span>
            )}
            {canAsk && (
              <button type="button" className="secondary-button btn-sm whitespace-nowrap" onClick={() => setIzin(true)}
                data-testid="order-credit-ask">
                <ShieldCheck size={12} aria-hidden="true" /> Ajukan izin kredit
              </button>
            )}
          </div>
          {msg && <p className="mt-1.5 text-fs-12 text-kn-text" role="status" data-testid="order-credit-msg">{msg}</p>}
          {err && <p className="mt-1.5 text-fs-12 text-kn-danger-text" role="alert" data-testid="order-credit-err">{err}</p>}
        </>
      )}
      {used && (
        <p className={`${held ? "mt-2 " : ""}flex items-center gap-1.5 text-fs-12 text-kn-text`} data-testid="order-credit-used">
          <ShieldCheck size={12} className="text-kn-success-text" aria-hidden="true" />
          Izin kredit dipakai: {used.reason_label || "izin kredit"} · {formatCurrency(used.amount)}
          {used.decided_by ? ` · disetujui ${used.decided_by}` : ""}
        </p>
      )}
      {payFirst && (
        <p className={`${held || used ? "mt-2 " : ""}flex items-center gap-1.5 text-fs-12 text-kn-warning-text`} data-testid="order-pay-before-ship">
          <Wallet size={12} aria-hidden="true" /> Bayar penuh sebelum kirim (pelanggan sedang ditahan)
        </p>
      )}
      {izin && (
        <Suspense fallback={null}>
          <CreditOverrideModal open customer={{ id: order.customer_id, name: order.customer_name }}
            entityId={order.entity_id || ""} amount={Number(order.grand_total || 0)} order={{ id: order.id, number: order.number }}
            onClose={() => setIzin(false)} onSaved={(t) => { setIzin(false); setMsg(t); }} />
        </Suspense>
      )}
    </div>
  );
}
