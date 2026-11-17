/**
 * Cek UI UAT v3 (S5) — kredit pelanggan tertahan di Review checkout: Sales mengajukan IZIN KREDIT langsung dari sini
 * (dulu "override kredit"; di HP tidak ada layar Pelanggan). CR-T3 — tombol membuka pop-up baku `CreditOverrideModal`
 * (lingkup, nominal, alasan dari master, catatan); tombol hanya untuk pemegang `credit_override.create` — tanpa izin itu
 * ditulis siapa yang mengajukan (bukan tombol mati).
 */
import { lazy, Suspense, useState } from "react";
import { ShieldAlert } from "lucide-react";
import { canCurrent } from "../../config/roles";
import { formatCurrency } from "../../utils/formatters";
// Pop-up dimuat saat dibuka (KNSelect/FormModal tidak ikut dimuat layar checkout sebelum dibutuhkan).
const CreditOverrideModal = lazy(() => import("../crm/CreditOverrideModal"));

export default function CreditOverrideRequest({ customer, amount, entityId = "", entityName = "", rejectionId = "",
  afterHint = "setelah izin disetujui, tekan Buat Sales Order lagi." }) {
  const [open, setOpen] = useState(false);
  const [msg, setMsg] = useState("");
  if (!customer?.id) return null;
  if (!canCurrent("credit_override", "create")) {
    return (
      <p className="mt-1.5 text-fs-12 text-kn-text-2" data-testid="credit-override-request-none">
        Izin kredit diajukan pemegang akses mengajukan izin kredit (biasanya Sales atau Admin Sales).
      </p>
    );
  }
  return (
    <div className="mt-1.5" data-testid="credit-override-request">
      {!msg && (
        <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="credit-override-open"
          onClick={() => setOpen(true)}>
          <ShieldAlert size={12} aria-hidden="true" /> Ajukan izin kredit ({formatCurrency(amount)})
        </button>
      )}
      {msg && <p className="mt-1 text-fs-12 text-kn-success-text" data-testid="credit-override-msg">{msg}</p>}
      {open && (
        <Suspense fallback={null}>
          <CreditOverrideModal open customer={customer} amount={amount} entityId={entityId} entityName={entityName}
            rejectionId={rejectionId} onClose={() => setOpen(false)}
            onSaved={(text) => { setOpen(false); setMsg(`${text} Isi keranjang tetap di layar ini; ${afterHint}`); }} />
        </Suspense>
      )}
    </div>
  );
}
