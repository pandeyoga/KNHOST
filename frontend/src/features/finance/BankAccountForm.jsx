/**
 * BankAccountForm (PM-T1) — buat / ubah rekening kas & bank: identitas, atas nama, "Dipakai untuk", cara bayar yang
 * dilayani (dari daftar induk Cara Bayar), bawaan penerimaan, dan tanda "Tampilkan di dokumen pelanggan".
 *
 * Kirim lewat `moneyPost`/`moneyPatch` + `useIntentKey` (awalan `/api/bank-accounts` berkunci idempotensi). Jawaban
 * 202 = perubahan butuh orang kedua (`kontrol.ubah_rekening`): belum berlaku, disimpan sebagai pengajuan —
 * `onSaved({ pending: true })`; pemanggil menampilkan pemberitahuannya. Ubah hanya mengirim isian yang berubah.
 *
 * Kas & Bank 3 (Tugas 4a, rancangan §5.1–§5.2) — rekening tunai punya **jenis kas** (rekening baru wajib memilih Kas
 * Kasir / Kas Kecil; bank = kas besar seperti dulu); jenis kas terkunci (`jenis_kas_terkunci`) dengan kalimat server
 * bila rekening sudah punya kas atau akun buku besar. Kas kecil punya **dana tetap** (0 = tidak memakai), kas kasir & kas
 * kecil boleh punya **lokasi** kerja (`warehouse_sites`). Ketiganya field peka (`kontrol.ubah_rekening`) di server.
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
import { useSites } from "../../components/SiteSelect";
import {
  JENIS_BERLOKASI, PESAN_BAWAAN_TUNAI_KASIR, PILIHAN_JENIS_KAS_TUNAI, alasanJenisKasTerkunci, bawaanDipegangKasir,
  jenisKasRekening, labelJenisKas,
} from "./jenisKas";

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
      is_active: true, reason: "", cash_type: "", dana_tetap: "", location_id: "" };
  }
  const tunai = account.account_type === "cash";
  return { name: account.name || "", account_type: account.account_type || "bank", bank_name: account.bank_name || "",
    account_number: account.account_number || "", holder_name: account.holder_name || "", opening_balance: "",
    purposes: [...(account.purposes || ALL_PURPOSES)], payment_method_codes: [...(account.payment_method_codes || [])],
    default_receiving_methods: [...(account.default_receiving_methods || [])],
    show_on_documents: Boolean(account.show_on_documents), is_active: account.is_active !== false, reason: "",
    // Kas & Bank 3 — rekening lama tanpa bidang: jenis kas dari jenis rekening, dana tetap 0, tanpa lokasi (= server).
    cash_type: tunai ? jenisKasRekening(account) : "", location_id: account.location_id || "",
    dana_tetap: Number(account.dana_tetap) > 0 ? String(account.dana_tetap) : "" };
}

/** Kas & Bank 3 — nilai kas yang dikirim dari isian (dana tetap hanya kas kecil, lokasi hanya kas kasir & kas kecil). */
function nilaiKas(form) {
  const ct = form.cash_type;
  return { cash_type: ct, dana_tetap: ct === "kas_kecil" ? Number(form.dana_tetap || 0) : 0,
    location_id: JENIS_BERLOKASI.includes(ct) ? form.location_id || "" : "" };
}

/** Lokasi kerja rekening tunai (kas kasir / kas kecil). Daftar `GET /warehouse-sites` dimuat hanya bila isian ini tampil;
 *  gagal dimuat (mis. tanpa izin gudang) → lokasi tersimpan tetap tampil + kalimat. "" = tanpa lokasi. */
function LokasiKasField({ value, onChange, savedName = "" }) {
  const sites = useSites();
  const options = sites.map((s) => ({ value: s.id, label: `${s.name}${s.city && s.city !== s.name ? ` · ${s.city}` : ""}` }));
  if (value && !options.some((o) => o.value === value)) options.unshift({ value, label: savedName || value });
  return (
    <div>
      <label className="field-label">Lokasi kerja</label>
      <KNSelect data-testid="bank-form-location" className="field" value={value || ""} placeholder="Tanpa lokasi"
        options={options} onValueChange={(v) => onChange(v || "")} />
      {sites.length ? (
        <p className="mt-1 text-fs-12 text-kn-text-2">Satu lokasi hanya untuk satu rekening kas kecil.</p>
      ) : (
        <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="bank-form-location-note">
          Daftar lokasi kerja belum bisa dimuat — lokasi lain belum bisa dipilih.
        </p>
      )}
    </div>
  );
}

const toggle = (list, v) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
const sameList = (a, b) => JSON.stringify([...(a || [])].sort()) === JSON.stringify([...(b || [])].sort());

function CheckList({ items, value, onChange, testId, disabledReason = "" }) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-2" data-testid={testId}>
      {items.map((it) => (
        <label key={it.value} className="inline-flex items-center gap-2 text-fs-13 text-kn-text">
          <input type="checkbox" className="h-4 w-4" data-testid={`${testId}-${it.value}`} disabled={Boolean(it.disabled)}
            checked={value.includes(it.value) && !it.disabled} onChange={() => onChange(toggle(value, it.value))} />
          {it.label}
        </label>
      ))}
      {!items.length && disabledReason && <p className="text-fs-12 text-kn-text-2">{disabledReason}</p>}
    </div>
  );
}

export default function BankAccountForm({ open, account = null, entityId = "", entityLabel = "", rekeningPt = [], onClose, onSaved }) {
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
  // Kas & Bank 3 (R4) — bawaan tunai yang dipegang kas kasir PT: centang nonaktif dengan kalimat server.
  const dipegangKasir = (kode) => bawaanDipegangKasir(rekeningPt, account?.id || "", form.cash_type, kode);
  const receivable = useMemo(() => {
    const masuk = new Set(pmIn.methods.map((m) => m.code));
    return served.filter((s) => codes.includes(s.value) && masuk.has(s.value))
      .map((s) => ({ ...s, disabled: bawaanDipegangKasir(rekeningPt, account?.id || "", form.cash_type, s.value) }));
  }, [served, codes, pmIn.methods, rekeningPt, account, form.cash_type]);
  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const docBlocked = form.account_type !== "bank" ? "Hanya rekening bank yang bisa tampil di dokumen pelanggan."
    : !form.holder_name.trim() || !form.account_number.trim() ? "Isi atas nama dan nomor rekening lebih dulu." : "";
  // Kas & Bank 3 — jenis kas rekening tunai; terkunci = kalimat server (rekening sudah punya kas / akun buku besar).
  const tunai = form.account_type === "cash";
  const kunciJenis = isEdit ? alasanJenisKasTerkunci(account) : "";
  const pilihanJenis = useMemo(() => (PILIHAN_JENIS_KAS_TUNAI.some((o) => o.value === form.cash_type) || !form.cash_type
    ? PILIHAN_JENIS_KAS_TUNAI : [...PILIHAN_JENIS_KAS_TUNAI, { value: form.cash_type, label: labelJenisKas(form.cash_type) }]),
  [form.cash_type]);
  const gantiJenis = (ct) => set({ cash_type: ct || "", ...(ct !== "kas_kecil" ? { dana_tetap: "" } : {}),
    ...(!JENIS_BERLOKASI.includes(ct) ? { location_id: "" } : {}) });

  const body = () => {
    const full = {
      name: form.name.trim(), bank_name: form.account_type === "bank" ? form.bank_name.trim() : "",
      account_number: form.account_type === "bank" ? form.account_number.trim() : "",
      holder_name: form.holder_name.trim(), purposes: form.purposes, payment_method_codes: codes,
      default_receiving_methods: form.default_receiving_methods.filter((c) => codes.includes(c) && !dipegangKasir(c)),
      show_on_documents: form.show_on_documents && !docBlocked, reason: form.reason.trim(),
    };
    if (!isEdit) {
      return { ...full, account_type: form.account_type, opening_balance: Number(form.opening_balance || 0),
        ...(tunai ? nilaiKas(form) : {}) };
    }
    const out = {};
    ["name", "bank_name", "account_number", "holder_name"].forEach((k) => {
      if ((account[k] || "") !== full[k]) out[k] = full[k];
    });
    ["purposes", "payment_method_codes", "default_receiving_methods"].forEach((k) => {
      if (!sameList(account[k], full[k])) out[k] = full[k];
    });
    if (Boolean(account.show_on_documents) !== full.show_on_documents) out.show_on_documents = full.show_on_documents;
    if ((account.is_active !== false) !== form.is_active) out.is_active = form.is_active;
    if (tunai) {   // Kas & Bank 3 — hanya yang berubah; jenis kas terkunci tidak pernah dikirim
      const kas = nilaiKas(form);
      if (!kunciJenis && kas.cash_type !== jenisKasRekening(account)) out.cash_type = kas.cash_type;
      if (Math.round(kas.dana_tetap * 100) !== Math.round(Number(account.dana_tetap || 0) * 100)) out.dana_tetap = kas.dana_tetap;
      if (kas.location_id !== (account.location_id || "")) out.location_id = kas.location_id;
    }
    if (full.reason) out.reason = full.reason;
    return out;
  };

  const submit = async (e) => {
    e?.preventDefault?.();
    if (!form.name.trim()) { setErr("Nama akun wajib diisi."); return; }
    if (tunai && !form.cash_type) { setErr("Pilih jenis kas: Kas Kasir atau Kas Kecil."); return; }
    if (tunai && form.cash_type === "kas_kecil" && Number(form.dana_tetap || 0) < 0) { setErr("Dana tetap tidak boleh negatif."); return; }
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
      subtitle={isEdit ? `Milik ${entityLabel || "PT ini"}. Perubahan nomor, atas nama, peruntukan, cara bayar, jenis kas, dana tetap, atau lokasi bisa butuh persetujuan orang lain.`
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
              onValueChange={(v) => set({ account_type: v || "bank", payment_method_codes: null, default_receiving_methods: [], show_on_documents: false,
                cash_type: "", dana_tetap: "", location_id: "" })} />
            {isEdit && <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="bank-form-type-reason">Jenis tidak bisa diubah sesudah rekening dibuat.</p>}
          </div>
          {tunai && (
            <div>
              <label className="field-label">Jenis kas <span className="req">*</span></label>
              <KNSelect data-testid="bank-form-cash-type" className="field" value={form.cash_type} placeholder="Pilih jenis kas"
                options={pilihanJenis} disabled={Boolean(kunciJenis)} onValueChange={gantiJenis} />
              {kunciJenis ? (
                <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="bank-form-cash-type-reason">{kunciJenis}</p>
              ) : (
                <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="bank-form-cash-type-hint">
                  {form.cash_type === "kas_kasir"
                    ? "Kwitansi tunai pelanggan otomatis masuk ke kas kasir bila PT hanya punya satu kas kasir; dua kas kasir atau lebih → kasir memilih rekening."
                    : "Kas Kasir untuk uang tunai dari pelanggan; Kas Kecil untuk dana operasional (panjar, LPJ, isi ulang)."}
                </p>
              )}
            </div>
          )}
          {tunai && form.cash_type === "kas_kecil" && (
            <div>
              <label className="field-label">Dana tetap</label>
              <MoneyInput testId="bank-form-dana-tetap" value={form.dana_tetap} onChange={(v) => set({ dana_tetap: v })} placeholder="0"
                hint="0 = tidak memakai dana tetap" />
              <p className="mt-1 text-fs-12 text-kn-text-2">Isi ulang diusulkan sebesar dana tetap − saldo buku − panjar yang belum di-LPJ.</p>
            </div>
          )}
          {tunai && JENIS_BERLOKASI.includes(form.cash_type) && (
            <LokasiKasField value={form.location_id} savedName={isEdit ? account?.location_name : ""}
              onChange={(v) => set({ location_id: v })} />
          )}
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
        {isEdit && (
          // Kas & Bank 1 (Tugas 6) — akun buku besar rekening hanya-baca (dibuat saat rekening lahir di PT yang memakai
          // akun per rekening, atau saat pindah saldo PT disiapkan); kodenya tidak berubah walau nama rekening berubah.
          <p className="mt-2 text-fs-12 text-kn-text-2" data-testid="bank-form-gl">
            Akun buku besar:{" "}
            {account?.gl_account_code
              ? <b className="font-mono">{account.gl_account_code}{account.gl_account_name ? ` · ${account.gl_account_name}` : ""}</b>
              : "belum ada — PT belum memakai akun per rekening"}
          </p>
        )}
      </FormSection>
      <FormSection number={2} title="Dipakai untuk" subtitle="Rekening hanya ditawarkan di layar yang peruntukannya dicentang." testId="bank-form-sec-use">
        <CheckList items={PURPOSES} value={form.purposes} onChange={(v) => set({ purposes: v })} testId="bank-form-purpose" />
      </FormSection>
      <FormSection number={3} title="Cara bayar" testId="bank-form-sec-pay"
        subtitle="Daftar dari Pengaturan › Perusahaan (PT) › Master per PT › Cara Bayar.">
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
            {receivable.some((r) => r.disabled) && (
              <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="bank-form-default-kasir">{PESAN_BAWAAN_TUNAI_KASIR}</p>
            )}
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
