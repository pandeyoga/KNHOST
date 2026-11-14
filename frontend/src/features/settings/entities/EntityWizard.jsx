/**
 * EntityWizard (FASE E-3) — tambah badan usaha dalam 4 langkah yang bisa dimundurkan.
 *
 * Kenapa wizard, bukan satu formulir panjang: membuka badan usaha baru menyangkut
 * empat keputusan yang berbeda sifatnya (identitas legal · pajak & keuangan ·
 * penomoran dokumen · akses). Dicampur jadi satu layar, orang mengisi NPWP di
 * badan usaha non-PKP atau salah kode dokumen — dan kode dokumen TIDAK BISA
 * diubah setelah dokumen pertama terbit. Karena itu langkah 3 menampilkan
 * pratinjau nomor langsung dan peringatan bahwa kode akan terkunci.
 *
 * KP-T1 (KP-01, KP-23) — isian yang tidak dibaca mesin dibuang ("Skema penomoran", "Penanggung insentif sales", nama
 * templat bagan akun). Mata uang dan tahun buku dipilih dari kunci Pusat Pengaturan (`finance.base_currency`,
 * `finance.fiscal_year_end_month`) berbawaan nilai grup; server menulisnya ke lapisan PT hanya bila berbeda. NPWP
 * diperiksa di tempat dengan pola yang sama dengan server; sakelar PT induk + persen kepemilikan (K-10).
 */
import { useEffect, useMemo, useState } from "react";
import LocationFields from "../../../components/LocationFields";
const LOC_KEYS = ["country", "country_code", "province", "province_code", "city", "city_code", "district", "district_code", "postal_code"];
const pickLoc = (o = {}) => Object.fromEntries(LOC_KEYS.map((k) => [k, o[k] || ""]));
import { Building2, Loader2, X, ArrowLeft, ArrowRight, Save, ShieldCheck,
  Hash, ClipboardCheck, AlertTriangle } from "lucide-react";

import KNSelect from "../../../components/KNSelect";
import { BULAN_ID, createEntity, entityTypes, errText, fiscalYearText, NPWP_MESSAGE, npwpValid,
  profileSettingItems } from "./entityApi";

const STEPS = [
  { key: 1, label: "Identitas", icon: Building2 },
  { key: 2, label: "Pajak & Keuangan", icon: ShieldCheck },
  { key: 3, label: "Penomoran & Dokumen", icon: Hash },
  { key: 4, label: "Ringkasan & Kesiapan", icon: ClipboardCheck },
];

const PERSONAL_TYPES = ["Perorangan", "UD"];

const EMPTY = {
  type: "PT",
  legal_name: "",
  short_name: "",
  owner_name: "",
  business_label: "",
  address: "",
  city: "",
  phone: "",
  email: "",
  logo_url: "",
  npwp: "",
  default_tax_mode: "ppn",
  base_currency: "",          // KP-T1 — diisi nilai grup dari Pusat Pengaturan saat wizard dibuka
  fiscal_year_end_month: "",
  is_group: false,
  ownership_pct: "100",
  doc_prefix: "",
};
const OWNERSHIP_MESSAGE = "Persen kepemilikan harus lebih dari 0 dan paling banyak 100.";

function slugPrefix(shortName) {
  return (shortName || "").replace(/[^A-Za-z0-9]/g, "").toUpperCase().slice(0, 6);
}

function Field({ label, hint, children, testId }) {
  return (
    <div className="grid gap-1" data-testid={testId}>
      <label className="kicker">{label}</label>
      {children}
      {hint && <p className="text-[10px] text-[#8E8E93]">{hint}</p>}
    </div>
  );
}

export default function EntityWizard({ entities = [], onClose, onCreated }) {
  const [step, setStep] = useState(1);
  const [form, setForm] = useState(EMPTY);
  const [types, setTypes] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // KP-T1 — entri registry dua kunci profil PT; null = tidak bisa dibaca (pemilih disembunyikan, PT mengikuti grup).
  const [profile, setProfile] = useState(undefined);

  useEffect(() => {
    entityTypes().then(setTypes).catch(() => setTypes([]));
    profileSettingItems().then((p) => {
      setProfile(p);
      setForm((f) => ({
        ...f,
        base_currency: f.base_currency || String(p.currency?.value ?? ""),
        fiscal_year_end_month: f.fiscal_year_end_month || String(p.fiscalYear?.value ?? ""),
      }));
    }).catch(() => setProfile(null));   // tanpa akses baca pengaturan: tampil keterangan "mengikuti grup"
  }, []);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const isPersonal = PERSONAL_TYPES.includes(form.type);
  const isPkp = form.default_tax_mode === "ppn";
  const typeMeta = useMemo(
    () => types.find((t) => t.value === form.type),
    [types, form.type]
  );

  const effectiveLegalName = isPersonal
    ? [form.owner_name.trim(), form.business_label.trim() ? `(${form.business_label.trim()})` : ""]
      .filter(Boolean).join(" ")
    : form.legal_name.trim();
  const effectivePrefix = (form.doc_prefix || slugPrefix(form.short_name)).toUpperCase();

  const prefixTaken = entities.some(
    (e) => (e.doc_prefix || "").toUpperCase() === effectivePrefix && effectivePrefix
  );
  const shortTaken = entities.some(
    (e) => (e.short_name || "").toLowerCase() === form.short_name.trim().toLowerCase()
      && form.short_name.trim()
  );

  const stepErrors = useMemo(() => {
    const errs = [];
    if (step === 1) {
      if (isPersonal && !form.owner_name.trim()) {
        errs.push("Nama pemilik wajib — usaha perorangan tidak punya badan hukum "
          + "terpisah, jadi nama legalnya adalah nama orangnya.");
      }
      if (!isPersonal && !form.legal_name.trim()) errs.push("Nama legal wajib diisi.");
      if (!form.short_name.trim()) errs.push("Nama singkat wajib diisi.");
      if (shortTaken) errs.push(`Nama singkat “${form.short_name}” sudah dipakai badan usaha lain.`);
    }
    if (step === 2 && isPkp && !form.npwp.trim()) {
      errs.push("Badan usaha PKP wajib mengisi NPWP karena akan menerbitkan faktur pajak. "
        + "Kalau belum PKP, pilih “Non-PKP”.");
    }
    if (step === 2 && form.npwp.trim() && !npwpValid(form.npwp)) errs.push(NPWP_MESSAGE);
    if (step === 2 && !form.is_group) {
      const pct = Number(form.ownership_pct);
      if (String(form.ownership_pct).trim() === "" || !Number.isFinite(pct) || pct <= 0 || pct > 100) {
        errs.push(OWNERSHIP_MESSAGE);
      }
    }
    if (step === 3) {
      if (!effectivePrefix) errs.push("Kode dokumen wajib diisi.");
      if (effectivePrefix && !/^[A-Z0-9]{2,10}$/.test(effectivePrefix)) {
        errs.push("Kode dokumen hanya boleh huruf/angka, 2–10 karakter.");
      }
      if (prefixTaken) errs.push(`Kode dokumen “${effectivePrefix}” sudah dipakai badan usaha lain.`);
    }
    return errs;
  }, [step, form, isPersonal, isPkp, effectivePrefix, prefixTaken, shortTaken]);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const { base_currency: cur, fiscal_year_end_month: fy, ownership_pct: pct, ...rest } = form;
      const body = { ...rest, doc_prefix: effectivePrefix, ownership_pct: form.is_group ? 100 : Number(pct) };
      if (profile && cur) body.base_currency = cur;
      if (profile && fy) body.fiscal_year_end_month = Number(fy);
      if (isPersonal) body.legal_name = "";   // server yang menyusun dari nama pemilik
      const created = await createEntity(body);
      onCreated?.(created);
    } catch (e) {
      setError(errText(e, "Gagal membuat badan usaha."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" data-testid="entity-wizard"
         onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}>
      <div className="modal-card" style={{ maxWidth: 720, width: "95vw" }}>
        <div className="flex items-start gap-2 border-b border-[#EFF0F2] px-4 py-3">
          <Building2 size={16} className="mt-0.5 text-[#0058CC]" />
          <div className="min-w-0 flex-1">
            <h3 className="text-[13.5px] font-bold">Tambah Badan Usaha</h3>
            <p className="text-[11px] text-[#6B6B73]">
              Langkah {step} dari 4 · {STEPS[step - 1].label}
            </p>
          </div>
          <button type="button" className="icon-button" aria-label="Tutup"
                  data-testid="entity-wizard-close" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        {/* Progres: jelas di mana kita, dan bisa mundur ke langkah yang sudah dilewati */}
        <div className="flex flex-wrap gap-1.5 border-b border-[#EFF0F2] px-4 py-2"
             data-testid="entity-wizard-steps">
          {STEPS.map((s) => {
            const Icon = s.icon;
            const done = s.key < step;
            const active = s.key === step;
            return (
              <button
                key={s.key}
                type="button"
                data-testid={`entity-wizard-step-${s.key}`}
                disabled={s.key > step}
                onClick={() => setStep(s.key)}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold disabled:opacity-45 ${
                  active ? "border-[#0058CC] bg-[#EAF2FF] text-[#0058CC]"
                    : done ? "border-[#BFE3CC] bg-[#EEF9F1] text-[#1B7F4B]"
                      : "border-[#E5E5EA] bg-white text-[#8E8E93]"
                }`}
              >
                <Icon size={11} /> {s.key}. {s.label}
              </button>
            );
          })}
        </div>

        <div className="space-y-3 p-4" style={{ maxHeight: "58vh", overflowY: "auto" }}>
          {step === 1 && (
            <div className="grid gap-2.5" data-testid="entity-wizard-panel-1">
              <Field label="Jenis badan usaha" testId="entity-wizard-type"
                     hint={typeMeta?.description
                       || "Jenis TIDAK menentukan PKP — status PKP diatur di langkah berikutnya."}>
                <KNSelect
                  className="field"
                  data-testid="entity-wizard-type-select"
                  value={form.type}
                  onValueChange={(v) => set({ type: v })}
                  options={(types.length ? types : [{ value: "PT", label: "PT" }])
                    .map((t) => ({ value: t.value, label: t.label }))}
                  placeholder="Pilih jenis…"
                />
              </Field>

              {isPersonal ? (
                <>
                  <Field label="Nama pemilik (wajib)" testId="entity-wizard-owner"
                         hint="Usaha perorangan tidak berbadan hukum terpisah — nama legalnya nama Anda.">
                    <input className="field" data-testid="entity-wizard-owner-input"
                           placeholder="mis. Sutrisno"
                           value={form.owner_name}
                           onChange={(e) => set({ owner_name: e.target.value })} />
                  </Field>
                  <Field label="Label usaha / nama dagang" testId="entity-wizard-business-label">
                    <input className="field" data-testid="entity-wizard-business-label-input"
                           placeholder="mis. Toko Kain Berkah"
                           value={form.business_label}
                           onChange={(e) => set({ business_label: e.target.value })} />
                  </Field>
                  <p className="rounded-md bg-[#F2F7FF] px-2.5 py-1.5 text-[11px] text-[#0058CC]"
                     data-testid="entity-wizard-legal-preview">
                    Nama legal yang akan tersimpan: <b>{effectiveLegalName || "—"}</b>
                  </p>
                </>
              ) : (
                <Field label="Nama legal (sesuai dokumen resmi)" testId="entity-wizard-legal">
                  <input className="field" data-testid="entity-wizard-legal-input"
                         placeholder="mis. PT Kain Suka Cita"
                         value={form.legal_name}
                         onChange={(e) => set({ legal_name: e.target.value })} />
                </Field>
              )}

              <Field label="Nama singkat (dipakai di layar)" testId="entity-wizard-short">
                <input className="field" data-testid="entity-wizard-short-input"
                       placeholder="mis. KSC"
                       value={form.short_name}
                       onChange={(e) => set({ short_name: e.target.value })} />
              </Field>
              <div className="grid gap-2.5 sm:grid-cols-2">
                <LocationFields testId="entity-wizard-loc" compact required={false} value={pickLoc(form)} onChange={(patch) => set(patch)} />
                <Field label="Telepon" testId="entity-wizard-phone">
                  <input className="field" data-testid="entity-wizard-phone-input"
                         value={form.phone} onChange={(e) => set({ phone: e.target.value })} />
                </Field>
              </div>
              <Field label="Alamat" testId="entity-wizard-address">
                <input className="field" data-testid="entity-wizard-address-input"
                       value={form.address} onChange={(e) => set({ address: e.target.value })} />
              </Field>
              <Field label="URL logo (opsional)" testId="entity-wizard-logo"
                     hint="Dipakai di kop dokumen cetak. Bisa diatur belakangan.">
                <input className="field" data-testid="entity-wizard-logo-input"
                       value={form.logo_url} onChange={(e) => set({ logo_url: e.target.value })} />
              </Field>
            </div>
          )}

          {step === 2 && (
            <div className="grid gap-2.5" data-testid="entity-wizard-panel-2">
              <Field label="Status pajak" testId="entity-wizard-tax-mode">
                <div className="grid gap-2 sm:grid-cols-2">
                  {[
                    { v: "ppn", t: "PKP (memungut PPN)",
                      d: "Menerbitkan faktur pajak. NPWP wajib. PPN mengikuti tarif di Pusat Pengaturan." },
                    { v: "non_ppn", t: "Non-PKP (tanpa PPN)",
                      d: "Tidak memungut PPN. Harga jual biasanya lebih bersaing untuk pelanggan kecil." },
                  ].map((o) => (
                    <button
                      key={o.v}
                      type="button"
                      data-testid={`entity-wizard-tax-${o.v}`}
                      onClick={() => set({ default_tax_mode: o.v })}
                      className={`rounded-md border p-2.5 text-left transition-colors ${
                        form.default_tax_mode === o.v
                          ? "border-[#0058CC] bg-[#EAF2FF]"
                          : "border-[#E5E5EA] bg-white hover:border-[#0058CC]/40"
                      }`}
                    >
                      <p className="text-[12px] font-bold text-[#1C1C1E]">{o.t}</p>
                      <p className="text-[10.5px] text-[#6B6B73]">{o.d}</p>
                    </button>
                  ))}
                </div>
              </Field>
              <Field label={`NPWP ${isPkp ? "(wajib untuk PKP)" : "(opsional)"}`}
                     testId="entity-wizard-npwp">
                <input className="field" data-testid="entity-wizard-npwp-input"
                       placeholder="00.000.000.0-000.000"
                       value={form.npwp} onChange={(e) => set({ npwp: e.target.value })} />
              </Field>
              {profile ? (
                <div className="grid gap-2.5 sm:grid-cols-2">
                  <Field label="Mata uang pembukuan" testId="entity-wizard-currency">
                    <KNSelect
                      className="field"
                      data-testid="entity-wizard-currency-select"
                      value={form.base_currency}
                      onValueChange={(v) => set({ base_currency: v })}
                      options={(profile.currency?.options || []).map((o) => ({ value: String(o.value), label: o.label }))}
                    />
                  </Field>
                  <Field label="Tahun buku berakhir pada bulan" testId="entity-wizard-fiscal"
                         hint="Menentukan batas tahun buku pada laporan dan tutup buku tahunan.">
                    <KNSelect
                      className="field"
                      data-testid="entity-wizard-fiscal-select"
                      value={form.fiscal_year_end_month}
                      onValueChange={(v) => set({ fiscal_year_end_month: v })}
                      options={BULAN_ID.map((b, i) => ({ value: String(i + 1), label: b }))}
                    />
                  </Field>
                </div>
              ) : profile === null ? (
                <p className="text-fs-12 text-kn-text-2" data-testid="entity-wizard-profile-readonly">
                  Mata uang pembukuan dan tahun buku mengikuti pengaturan grup. Pemegang akses pengaturan keuangan
                  bisa mengubahnya khusus untuk PT ini dari detail PT.
                </p>
              ) : null}
              <div className="grid gap-2.5 sm:grid-cols-2">
                <Field label="PT induk (konsolidasi)" testId="entity-wizard-group"
                       hint="PT induk tidak ikut dijumlahkan sebagai baris di laporan konsolidasi dan tidak muncul di pilihan PT pada tutup buku.">
                  <label className="flex items-center gap-2 text-fs-13 text-kn-text">
                    <input type="checkbox" data-testid="entity-wizard-group-input" checked={form.is_group}
                           onChange={(e) => set({ is_group: e.target.checked })} />
                    Ini PT induk grup
                  </label>
                </Field>
                <Field label="Persen kepemilikan (%)" testId="entity-wizard-ownership"
                       hint="Belum memengaruhi angka — dipakai laporan konsolidasi setelah eliminasi per periode aktif.">
                  <input className="field" type="number" min="0.01" max="100" step="0.01"
                         data-testid="entity-wizard-ownership-input" disabled={form.is_group}
                         value={form.ownership_pct} onChange={(e) => set({ ownership_pct: e.target.value })} />
                </Field>
              </div>
              <p className="text-fs-12 text-kn-text-2" data-testid="entity-wizard-coa-note">
                Bagan akun dipakai bersama semua PT — kode akun sama, bukunya terpisah.
              </p>
            </div>
          )}

          {step === 3 && (
            <div className="grid gap-2.5" data-testid="entity-wizard-panel-3">
              <Field label="Kode dokumen" testId="entity-wizard-prefix"
                     hint="Dipakai sebagai awalan nomor dokumen yang bernomor per PT, mis. pesanan, faktur pajak, kwitansi.">
                <input className="field font-mono" data-testid="entity-wizard-prefix-input"
                       placeholder={slugPrefix(form.short_name) || "KSC"}
                       value={form.doc_prefix}
                       onChange={(e) => set({ doc_prefix: e.target.value.toUpperCase() })} />
              </Field>
              <div className="rounded-md border border-[#C9DBF7] bg-[#F2F7FF] p-2.5"
                   data-testid="entity-wizard-number-preview">
                <p className="kicker mb-1">Pratinjau nomor dokumen</p>
                <div className="grid gap-1 sm:grid-cols-2">
                  {[["Pesanan penjualan", "SO-00001"], ["Pesanan pembelian", "PO-00001"],
                    ["Faktur pajak", "FKT-00001"], ["Kwitansi", "AR-00001"]].map(([l, n]) => (
                    <p key={n} className="text-[11.5px] text-[#3C3C43]">
                      {l}: <b className="font-mono">{effectivePrefix || "KODE"}/{n}</b>
                    </p>
                  ))}
                </div>
              </div>
              <div className="flex items-start gap-1.5 rounded-md border border-[#F0C88A] bg-[#FEF7EC] p-2.5">
                <AlertTriangle size={13} className="mt-0.5 shrink-0 text-[#8C4A00]" />
                <p className="text-[11px] text-[#3C3C43]">
                  <b>Kode ini akan TERKUNCI</b> begitu badan usaha menerbitkan dokumen
                  pertamanya. Alasannya: kalau kode berubah di tengah jalan, nomor dokumen
                  lama dan baru tidak bisa dibedakan lagi saat audit pajak. Pastikan sekarang.
                </p>
              </div>
            </div>
          )}

          {step === 4 && (
            <div className="grid gap-2.5" data-testid="entity-wizard-panel-4">
              <div className="rounded-md border border-[#EFF0F2] bg-[#FAFBFC] p-3"
                   data-testid="entity-wizard-summary">
                <p className="kicker mb-1.5">Ringkasan sebelum disimpan</p>
                {[
                  ["Jenis", form.type],
                  ["Nama legal", effectiveLegalName || "—"],
                  ["Nama singkat", form.short_name || "—"],
                  ["Kota", form.city || "—"],
                  ["Status pajak", isPkp ? "PKP (memungut PPN)" : "Non-PKP"],
                  ["NPWP", form.npwp || "—"],
                  ["Mata uang pembukuan", profile ? (profile.currency?.options || []).find(
                    (o) => String(o.value) === form.base_currency)?.label || form.base_currency : "Mengikuti pengaturan grup"],
                  ["Tahun buku", profile && form.fiscal_year_end_month
                    ? fiscalYearText(form.fiscal_year_end_month) : "Mengikuti pengaturan grup"],
                  ["PT induk (konsolidasi)", form.is_group ? "Ya" : "Tidak"],
                  ["Persen kepemilikan", form.is_group ? "—" : `${form.ownership_pct} %`],
                  ["Kode dokumen", effectivePrefix],
                  ["Contoh nomor", `${effectivePrefix}/SO-00001`],
                ].map(([k, v]) => (
                  <p key={k} className="flex justify-between gap-2 border-b border-[#F5F5F7] py-1 text-[11.5px] last:border-0">
                    <span className="text-[#6B6B73]">{k}</span>
                    <b className="text-right text-[#1C1C1E]">{v}</b>
                  </p>
                ))}
              </div>
              <div className="rounded-md border border-[#C9DBF7] bg-[#F2F7FF] p-2.5">
                <p className="text-[11.5px] font-bold text-[#1C1C1E]">Setelah disimpan</p>
                <p className="text-[10.5px] text-[#6B6B73]">
                  Badan usaha langsung siap dipakai: bagan akun tersedia, penomoran aktif,
                  dan lapisan konfigurasinya dibuat. Layar berikutnya menampilkan
                  <b> daftar kesiapan</b> — pengguna, gudang, rekening, harga jual, saldo awal,
                  dan kop surat — supaya Anda tahu apa lagi yang perlu dilengkapi.
                </p>
              </div>
            </div>
          )}

          {stepErrors.length > 0 && (
            <ul className="space-y-1 rounded-md border border-[#F0B5AE] bg-[#FCEBEA] p-2.5"
                data-testid="entity-wizard-step-errors">
              {stepErrors.map((e, i) => (
                <li key={i} className="text-[11px] text-[#A8221A]">• {e}</li>
              ))}
            </ul>
          )}
          {error && (
            <div className="notice-bar danger !py-1.5" data-testid="entity-wizard-error">
              <span className="text-[11.5px]">{error}</span>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-[#EFF0F2] px-4 py-3">
          <button type="button" className="secondary-button"
                  data-testid="entity-wizard-back"
                  disabled={step === 1}
                  onClick={() => setStep((s) => Math.max(1, s - 1))}>
            <ArrowLeft size={13} /> Kembali
          </button>
          <div className="flex gap-2">
            <button type="button" className="secondary-button"
                    data-testid="entity-wizard-cancel" onClick={onClose}>
              Batal
            </button>
            {step < 4 ? (
              <button type="button" className="primary-button"
                      data-testid="entity-wizard-next"
                      disabled={stepErrors.length > 0}
                      onClick={() => setStep((s) => Math.min(4, s + 1))}>
                Lanjut <ArrowRight size={13} />
              </button>
            ) : (
              <button type="button" className="primary-button"
                      data-testid="entity-wizard-submit"
                      disabled={busy || stepErrors.length > 0}
                      onClick={submit}>
                {busy ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                Simpan Badan Usaha
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
