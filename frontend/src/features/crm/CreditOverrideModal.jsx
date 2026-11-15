/**
 * CreditOverrideModal (CR-T3) — pop-up baku "Ajukan izin kredit" (checkout, keranjang HP, kartu pelanggan, detail pesanan).
 *
 * Isian: "Lingkup" [Pesanan ini · Pelanggan ini] (Pesanan ini hanya bila ada pesanannya), "Nominal" (> 0), "Alasan"
 * (master alasan izin kredit, `GET /api/credit-override-reasons`), "Catatan" (wajib bila "Lainnya"). Kirim
 * `POST /api/customers/{id}/credit-override` lewat `moneyPost` + `useIntentKey` (klik ganda = satu izin).
 * Galat server tampil di dalam pop-up (INV-UI-03); isian tidak dihapus.
 */
import { useEffect, useState } from "react";
import { Loader2, Send, ShieldAlert } from "lucide-react";
import FormModal from "../../components/FormModal";
import FormSection from "../../components/FormSection";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "../../components/MoneyInput";
import axios, { API } from "../../services/apiClient";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { apiErrorText } from "../../utils/apiError";
import { parseDecimal } from "../../utils/decimalInput";
import { formatCurrency } from "../../utils/formatters";

const MIN_LETTERS = 5;
const countLetters = (t) => (String(t || "").match(/\p{L}/gu) || []).length;
import { SCOPE_LABEL } from "./creditOverrideUi";

export default function CreditOverrideModal({ open, customer, entityId = "", entityName = "", amount = 0, order = null,
  rejectionId = "", onClose, onSaved }) {
  const [scope, setScope] = useState(order ? "pesanan" : "pelanggan");
  const [nominal, setNominal] = useState("");
  const [reasonCode, setReasonCode] = useState("");
  const [note, setNote] = useState("");
  const [reasons, setReasons] = useState([]);
  const [reasonErr, setReasonErr] = useState("");
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const intent = useIntentKey("izin-kredit");

  useEffect(() => {
    if (!open) return undefined;
    setScope(order ? "pesanan" : "pelanggan");
    setNominal(amount > 0 ? String(Math.round(Number(amount))) : "");
    setReasonCode(""); setNote(""); setTried(false); setError(""); setReasonErr("");
    let alive = true;
    axios.get(`${API}/credit-override-reasons`)
      .then((r) => { if (alive) setReasons(Array.isArray(r.data) ? r.data : []); })
      .catch((e) => { if (alive) setReasonErr(apiErrorText(e, "Daftar alasan izin kredit gagal dimuat.")); });
    return () => { alive = false; };
  }, [open, order, amount]);

  if (!open || !customer?.id) return null;
  const num = nominal === "" ? 0 : parseDecimal(nominal);
  const missing = [
    !(Number.isFinite(num) && num > 0) && "nominal lebih dari 0",
    !reasonCode && "alasan",
    reasonCode === "cr_lain" && countLetters(note) < MIN_LETTERS && "catatan (minimal 5 huruf)",
  ].filter(Boolean);

  async function submit() {
    setTried(true); setError("");
    if (missing.length) return;
    setBusy(true);
    const body = { customer_id: customer.id, amount: num, scope, reason_code: reasonCode, reason: note.trim(),
      entity_id: entityId || "", order_id: scope === "pesanan" ? order?.id || "" : "", rejection_id: rejectionId || "" };
    try {
      await intent.send(body, (k) => moneyPost(`${API}/customers/${customer.id}/credit-override`, body, k));
      onSaved?.(`Izin kredit ${formatCurrency(num)} untuk ${customer.name || "pelanggan"} diajukan — menunggu keputusan.`);
    } catch (e) {
      setError(apiErrorText(e, "Izin kredit belum terkirim."));
    } finally { setBusy(false); }
  }

  const scopeOptions = [
    ...(order ? [{ value: "pesanan", label: `${SCOPE_LABEL.pesanan} (${order.number || "pesanan"})` }] : []),
    { value: "pelanggan", label: SCOPE_LABEL.pelanggan },
  ];
  return (
    <FormModal open onClose={onClose} size="md" testId="credit-override-modal" busy={busy} error={error}
      icon={ShieldAlert} title="Ajukan izin kredit"
      subtitle={`${customer.name || ""}${entityName ? ` · ${entityName}` : ""}`}
      footer={(
        <div className="flex flex-wrap items-center justify-end gap-2">
          {tried && missing.length > 0 && (
            <p className="w-full text-fs-12 font-semibold text-kn-danger-text" data-testid="credit-override-missing">Lengkapi: {missing.join(", ")}.</p>
          )}
          <button type="button" className="secondary-button btn-sm" disabled={busy} onClick={() => !busy && onClose?.()}
            data-testid="credit-override-cancel">Batal</button>
          <button type="button" className="primary-button btn-sm whitespace-nowrap" disabled={busy} onClick={submit}
            data-testid="credit-override-submit">
            {busy ? <Loader2 size={13} className="animate-spin" aria-hidden="true" /> : <Send size={13} aria-hidden="true" />}
            {busy ? "Mengirim..." : "Ajukan izin"}
          </button>
        </div>
      )}>
      <FormSection number={1} title="Izin yang diminta" testId="credit-override-section-scope">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="Lingkup" hint={scope === "pesanan" ? "Hanya untuk pesanan ini." : "Untuk pesanan mana pun pelanggan ini di PT ini sampai nominalnya habis."}>
            <KNSelect value={scope} onValueChange={setScope} className="field" data-testid="credit-override-scope" options={scopeOptions} />
          </Field>
          <Field label="Nominal (Rp)" req>
            <MoneyInput testId="credit-override-amount" value={nominal} onChange={(v) => setNominal(v)} className="field" placeholder="Rp 0" />
          </Field>
        </div>
      </FormSection>
      <FormSection number={2} title="Dasar pengajuan" testId="credit-override-section-reason" required>
        <div className="grid gap-3">
          <Field label="Alasan" req>
            <KNSelect value={reasonCode} onValueChange={setReasonCode} className="field" data-testid="credit-override-reason-code"
              placeholder="Pilih alasan" options={reasons.map((r) => ({ value: r.code, label: r.label }))} />
            {reasonErr && <p className="mt-0.5 text-fs-12 text-kn-danger-text" role="alert">{reasonErr}</p>}
          </Field>
          <Field label="Catatan" req={reasonCode === "cr_lain"} optional={reasonCode !== "cr_lain"}
            hint="Dibaca pemutus dan tercatat bersama izin.">
            <textarea className="field" rows={2} data-testid="credit-override-note" value={note}
              onChange={(e) => setNote(e.target.value)} placeholder="mis. pelanggan menyerahkan giro mundur 30 hari" />
          </Field>
        </div>
      </FormSection>
    </FormModal>
  );
}

function Field({ label, req = false, optional = false, hint, children }) {
  return (
    <div>
      <label className="mb-1 block text-fs-12 font-semibold text-kn-text">{label}{req && <span className="text-kn-danger-text"> *</span>}
        {optional && !req && <span className="font-normal text-kn-text-2"> (opsional)</span>}</label>
      {children}
      {hint && <p className="mt-0.5 text-fs-12 text-kn-text-2">{hint}</p>}
    </div>
  );
}
