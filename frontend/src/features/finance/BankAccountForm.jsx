/**
 * BankAccountForm (PM-T1) — buat / ubah rekening kas & bank: identitas, atas nama, "Dipakai untuk", cara bayar yang
 * dilayani (dari daftar induk Cara Bayar), bawaan penerimaan, dan tanda "Tampilkan di dokumen pelanggan".
 *
 * Kirim lewat `moneyPost`/`moneyPatch` + `useIntentKey` (awalan `/api/bank-accounts` berkunci idempotensi). Jawaban
 * 202 = perubahan butuh orang kedua (`kontrol.ubah_rekening`): belum berlaku, disimpan sebagai pengajuan —
 * `onSaved({ pending: true })`; pemanggil menampilkan pemberitahuannya. Ubah hanya mengirim isian yang berubah.
 */
import { useEffect, useMemo, useState } from "react";
import { Landmark } from "lucide-react";
import { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import FormSection from "../../components/FormSection";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "@/components/MoneyInput";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPatch, moneyPost } from "../../utils/moneyRequest";
import { apiErrorText } from "../../utils/apiError";
import { usePaymentMethods } from "../../config/paymentMethods";

export const ACCOUNT_KIND_OPTIONS = [
  { value: "bank", label: "Rekening bank" },
  { value: "cash", label: "Kas tunai" },
];

/** Peruntukan rekening (urutan = server `bank_service.PERUNTUKAN`). */
export const PURPOSES = [
  { value: "penerimaan_pelanggan", label: "Penerimaan pelanggan" },
  { value: "pembayaran_pemasok", label: "Pembayaran pemasok" },
  { value: "gaji", label: "Gaji" },
  { value: "operasional", label: "Operasional" },
];
export const purposeLabel = (v) => PURPOSES.find((p) => p.value === v)?.label || v;

const ALL_PURPOSES = PURPOSES.map((p) => p.value);
const needOf = (type) => (type === "cash" ? "kas" : "bank");

function initial(account) {
  if (!account) {
    return { name: "", account_type: "bank", bank_name: "", account_number: "", holder_name: "", opening_balance: "",
      purposes: [...ALL_PURPOSES], payment_method_codes: null, default_receiving_methods: [], show_on_documents: false,
      is_active: true, reason: "" };
  }
  return { name: account.name || "", account_type: account.account_type || "bank", bank_name: account.bank_name || "",
    account_number: account.account_number || "", holder_name: account.holder_name || "", opening_balance: "",
    purposes: [...(account.purposes || ALL_PURPOSES)], payment_method_codes: [...(account.payment_method_codes || [])],
    default_receiving_methods: [...(account.default_receiving_methods || [])],
    show_on_documents: Boolean(account.show_on_documents), is_active: account.is_active !== false, reason: "" };
}

const toggle = (list, v) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
const sameList = (a, b) => JSON.stringify([...(a || [])].sort()) === JSON.stringify([...(b || [])].sort());

function CheckList({ items, value, onChange, testId, disabledReason = "" }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2" data-testid={testId}>
      {items.map((it) => (
        <label key={it.value} className="inline-flex items-center gap-2 text-fs-13 text-kn-text">
          <input type="checkbox" className="h-4 w-4" data-testid={`${testId}-${it.value}`}
            checked={value.includes(it.value)} onChange={() => onChange(toggle(value, it.value))} />
          {it.label}
        </label>
      ))}
      {!items.length && disabledReason && <p className="text-fs-12 text-kn-text-2">{disabledReason}</p>}
    </div>
  );
}

export default function BankAccountForm({ open, account = null, entityId = "", entityLabel = "", onClose, onSaved }) {
  const isEdit = Boolean(account);
  const [form, setForm] = useState(() => initial(account));
  const [err, setErr] = useState("");
  const [saving, setSaving] = useState(false);
  const intent = useIntentKey("rek");
  const pm = usePaymentMethods("", isEdit ? account.entity_id : entityId);
  const pmIn = usePaymentMethods("masuk", isEdit ? account.entity_id : entityId);
  useEffect(() => { if (open) { setForm(initial(account)); setErr(""); } }, [open, account]);

  // Cara bayar yang cocok dengan jenis rekening (bank: transfer/giro/QRIS…; kas: tunai). Titipan tidak ber-rekening.
  const served = useMemo(() => pm.methods.filter((m) => m.needs_account === needOf(form.account_type))
    .map((m) => ({ value: m.code, label: m.name })), [pm.methods, form.account_type]);
  const codes = form.payment_method_codes ?? served.map((s) => s.value);
  const receivable = useMemo(() => {
    const masuk = new Set(pmIn.methods.map((m) => m.code));
    return served.filter((s) => codes.includes(s.value) && masuk.has(s.value));
  }, [served, codes, pmIn.methods]);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const docBlocked = form.account_type !== "bank" ? "Hanya rekening bank yang bisa tampil di dokumen pelanggan."
    : !form.holder_name.trim() || !form.account_number.trim() ? "Isi atas nama dan nomor rekening lebih dulu." : "";

  const body = () => {
    const full = {
      name: form.name.trim(), bank_name: form.account_type === "bank" ? form.bank_name.trim() : "",
      account_number: form.account_type === "bank" ? form.account_number.trim() : "",
      holder_name: form.holder_name.trim(), purposes: form.purposes, payment_method_codes: codes,
      default_receiving_methods: form.default_receiving_methods.filter((c) => codes.includes(c)),
      show_on_documents: form.show_on_documents && !docBlocked, reason: form.reason.trim(),
    };
    if (!isEdit) return { ...full, account_type: form.account_type, opening_balance: Number(form.opening_balance || 0) };
    const out = {};
    ["name", "bank_name", "account_number", "holder_name"].forEach((k) => {
      if ((account[k] || "") !== full[k]) out[k] = full[k];
    });
    ["purposes", "payment_method_codes", "default_receiving_methods"].forEach((k) => {
      if (!sameList(account[k], full[k])) out[k] = full[k];
    });
    if (Boolean(account.show_on_documents) !== full.show_on_documents) out.show_on_documents = full.show_on_documents;
    if ((account.is_active !== false) !== form.is_active) out.is_active = form.is_active;
    if (full.reason) out.reason = full.reason;
    return out;
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!form.name.trim()) { setErr("Nama akun wajib diisi."); return; }
    const payload = body();
    if (isEdit && !Object.keys(payload).filter((k) => k !== "reason").length) { setErr("Belum ada yang diubah."); return; }
    setSaving(true);
    setErr("");
    try {
      const r = await intent.send(payload, (key) => (isEdit
        ? moneyPatch(`${API}/bank-accounts/${account.id}`, payload, key)
        : moneyPost(`${API}/bank-accounts`, payload, key)));
      onSaved?.({ pending: r?.status === 202, data: r?.data });
    } catch (ex) {
      setErr(apiErrorText(ex, isEdit ? "Gagal menyimpan perubahan rekening." : "Gagal membuat akun."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <FormModal open={open} onClose={onClose} size="lg" icon={Landmark}
      title={isEdit ? `Ubah ${account?.name || "rekening"}` : "Tambah Akun Kas / Bank"}
      subtitle={isEdit ? `Milik ${entityLabel || "PT ini"}. Perubahan nomor, atas nama, peruntukan, atau cara bayar bisa butuh persetujuan orang lain.`
        : `Rekening bank atau kas tunai milik ${entityLabel || "PT aktif"}.`}
      testId="bank-add-form" onSubmit={submit} submitLabel={isEdit ? "Simpan Perubahan" : "Simpan Akun"}
      submitTestId="bank-form-submit" busy={saving} error={err}>
      <FormSection number={1} title="Identitas rekening" testId="bank-form-sec-id">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="field-label">Nama Akun <span className="req">*</span></label>
            <input data-testid="bank-form-name" className="field" value={form.name} onChange={(e) => set({ name: e.target.value })} placeholder="mis. BCA Operasional" />
          </div>
          <div>
            <label className="field-label">Jenis <span className="req">*</span></label>
            <KNSelect data-testid="bank-form-type" value={form.account_type} options={ACCOUNT_KIND_OPTIONS} disabled={isEdit}
              onValueChange={(v) => set({ account_type: v || "bank", payment_method_codes: null, default_receiving_methods: [], show_on_documents: false })} />
            {isEdit && <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="bank-form-type-reason">Jenis tidak bisa diubah sesudah rekening dibuat.</p>}
          </div>
          {form.account_type === "bank" && (
            <>
              <div>
                <label className="field-label">Nama Bank</label>
                <input data-testid="bank-form-bankname" className="field" value={form.bank_name} onChange={(e) => set({ bank_name: e.target.value })} placeholder="mis. BCA" />
              </div>
              <div>
                <label className="field-label">No. Rekening</label>
                <input data-testid="bank-form-accountno" className="field tabular-nums" value={form.account_number} onChange={(e) => set({ account_number: e.target.value })} placeholder="0123456789" />
              </div>
            </>
          )}
          <div>
            <label className="field-label">Atas nama</label>
            <input data-testid="bank-form-holder" className="field" value={form.holder_name} onChange={(e) => set({ holder_name: e.target.value })}
              placeholder={form.account_type === "bank" ? "mis. PT Kain Suka Cita" : "mis. Kasir toko"} />
          </div>
          {!isEdit && (
            <div>
              <label className="field-label">Saldo Awal</label>
              <MoneyInput testId="bank-form-opening" value={form.opening_balance} onChange={(v) => set({ opening_balance: v })} placeholder="0" />
            </div>
          )}
          {isEdit && (
            <label className="inline-flex items-center gap-2 self-end text-fs-13 text-kn-text">
              <input type="checkbox" className="h-4 w-4" data-testid="bank-form-active" checked={form.is_active}
                onChange={(e) => set({ is_active: e.target.checked })} />
              Rekening aktif
            </label>
          )}
        </div>
      </FormSection>
      <FormSection number={2} title="Dipakai untuk" subtitle="Rekening hanya ditawarkan di layar yang peruntukannya dicentang." testId="bank-form-sec-use">
        <CheckList items={PURPOSES} value={form.purposes} onChange={(v) => set({ purposes: v })} testId="bank-form-purpose" />
      </FormSection>
      <FormSection number={3} title="Cara bayar" testId="bank-form-sec-pay"
        subtitle="Daftar dari Pengaturan › Keuangan & Pajak › Cara Bayar.">
        <div className="grid gap-3">
          <div>
            <p className="field-label">Cara bayar yang dilayani</p>
            <CheckList items={served} value={codes} testId="bank-form-method"
              onChange={(v) => set({ payment_method_codes: v, default_receiving_methods: form.default_receiving_methods.filter((c) => v.includes(c)) })}
              disabledReason="Belum ada cara bayar aktif untuk jenis rekening ini." />
          </div>
          <div>
            <p className="field-label">Jadikan bawaan penerimaan untuk</p>
            <CheckList items={receivable} value={form.default_receiving_methods} testId="bank-form-default"
              onChange={(v) => set({ default_receiving_methods: v })}
              disabledReason="Centang dulu cara bayar penerimaan yang dilayani rekening ini." />
            <p className="mt-1 text-fs-12 text-kn-text-2">Satu cara bayar hanya punya satu rekening bawaan per PT; rekening bawaan lama untuk cara bayar itu otomatis dilepas.</p>
          </div>
          <div>
            <label className="inline-flex items-center gap-2 text-fs-13 text-kn-text">
              <input type="checkbox" role="switch" className="h-4 w-4" data-testid="bank-form-show-docs"
                checked={form.show_on_documents && !docBlocked} disabled={Boolean(docBlocked)}
                onChange={(e) => set({ show_on_documents: e.target.checked })} />
              Tampilkan di dokumen pelanggan
            </label>
            {docBlocked && <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="bank-form-show-docs-reason">{docBlocked}</p>}
          </div>
        </div>
      </FormSection>
      <FormSection number={4} title="Catatan untuk penyetuju" collapsible defaultOpen={false} testId="bank-form-sec-reason"
        summary={form.reason ? form.reason : "Opsional"}>
        <textarea data-testid="bank-form-reason" className="field min-h-[64px]" value={form.reason}
          onChange={(e) => set({ reason: e.target.value })} placeholder="mis. Rekening baru sesuai surat bank 12 Nov" />
      </FormSection>
    </FormModal>
  );
}
