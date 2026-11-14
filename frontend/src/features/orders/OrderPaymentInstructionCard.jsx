import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Copy, Info, Landmark } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import { apiErrorText } from "../../utils/apiError";
import { usePaymentMethods } from "../../config/paymentMethods";
import { accountText } from "../pos/CheckoutPaymentDestination";

export const PESAN_DISALIN = "Instruksi bayar disalin.";

async function salinTeks(text) {
  try {
    if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return true; }
  } catch { /* jatuh ke cara lama di bawah */ }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch { return false; }
}

/**
 * PM-T2 — detail pesanan: baris "Cara bayar" & "Rekening tujuan" (potret di pesanan) + kartu "Instruksi Pembayaran"
 * (`GET /api/sales-orders/{id}/payment-instruction`): satu blok per tagihan berkode yang belum lunas, tombol
 * **Salin instruksi bayar** (menyalin `text` — teks yang sama dengan dokumen cetak / WhatsApp). Tanpa kode: kalimat
 * sebab dari server ("…setelah pesanan dikonfirmasi." / "…setelah barang dikirim.").
 */
export default function OrderPaymentInstructionCard({ order }) {
  const pm = usePaymentMethods("masuk", order?.entity_id || "");
  const [state, setState] = useState({ loading: true, data: null, error: "" });
  const [flash, setFlash] = useState(null);   // {ok, text}
  const oid = order?.id;

  useEffect(() => {
    if (!oid) return undefined;
    let alive = true;
    setState({ loading: true, data: null, error: "" });
    axios.get(`${API}/sales-orders/${oid}/payment-instruction`)
      .then((r) => { if (alive) setState({ loading: false, data: r.data || null, error: "" }); })
      .catch((e) => { if (alive) setState({ loading: false, data: null, error: apiErrorText(e, "Instruksi bayar gagal dimuat.") }); });
    return () => { alive = false; };
  }, [oid, order?.status, order?.receiving_account_id, order?.payment_method_code, order?.payment_code]);

  const methodCode = order?.payment_method_code || "";
  const methodLabel = methodCode ? pm.labelOf(methodCode) : "Belum ditentukan";
  const accLabel = order?.receiving_account_id ? accountText(order.receiving_account) : "—";
  const items = state.data?.items || [];

  const salin = async () => {
    const ok = await salinTeks(state.data?.text || "");
    setFlash(ok ? { ok: true, text: PESAN_DISALIN }
      : { ok: false, text: "Instruksi bayar gagal disalin — pilih teksnya di dokumen lalu salin manual." });
  };

  return (
    <div data-testid="order-payment-instruction" className="rounded-md border border-kn-divider bg-white p-2.5 space-y-2">
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-fs-12">
        <dt className="text-kn-text-2">Cara bayar</dt>
        <dd data-testid="order-payment-method" className="font-semibold text-kn-text break-words">{methodLabel}</dd>
        <dt className="text-kn-text-2">Rekening tujuan</dt>
        <dd data-testid="order-receiving-account" className="font-semibold text-kn-text break-words">{accLabel}</dd>
      </dl>
      <div className="border-t border-kn-divider pt-2">
        <p className="mb-1.5 flex items-center gap-1.5 text-fs-12 font-bold uppercase tracking-wide text-kn-action">
          <Landmark size={13} /> Instruksi Pembayaran
        </p>
        {state.loading ? (
          <p className="text-fs-12 text-kn-text-2" data-testid="order-payment-instruction-loading">Memuat instruksi bayar…</p>
        ) : state.error ? (
          <p className="notice-bar danger" data-testid="order-payment-instruction-error"><span>{state.error}</span></p>
        ) : items.length === 0 ? (
          <p className="flex items-start gap-1.5 text-fs-12 text-kn-text-2" data-testid="order-payment-instruction-note">
            <Info size={13} className="mt-0.5 shrink-0" /> {state.data?.note || "Belum ada tagihan berkode."}
          </p>
        ) : (
          <>
            <ul className="space-y-1.5" data-testid="order-payment-instruction-items">
              {items.map((it) => (
                <li key={it.pay_code} className="rounded-md bg-kn-neutral-soft px-2.5 py-1.5 text-fs-12 text-kn-text">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                    <span className="font-semibold">{it.label}</span>
                    <span className="font-bold tabular-nums">{formatCurrency(it.amount)}</span>
                  </div>
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-kn-text-2">
                    <span>Jatuh tempo: {it.due_label}</span>
                    <span>Kode bayar: <b className="font-mono text-kn-text" data-testid={`order-pay-code-${it.pay_code}`}>{it.pay_code}</b></span>
                  </div>
                </li>
              ))}
            </ul>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="copy-payment-instruction" onClick={salin}>
                <Copy size={13} /> Salin instruksi bayar
              </button>
              {flash && (
                <span role="status" data-testid="copy-payment-instruction-flash"
                  className={`flex items-center gap-1 text-fs-12 ${flash.ok ? "text-kn-success-text" : "text-kn-danger-text"}`}>
                  {flash.ok ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />} {flash.text}
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
