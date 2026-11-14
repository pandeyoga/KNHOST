import KNSelect from "../../components/KNSelect";
import FormSection from "../../components/FormSection";

/**
 * TX-T1 (K-33) — bagian "Data pajak" form pelanggan (`CustomerFormModal`): identitas pajak (NPWP/NIK), nama & alamat di
 * faktur pajak, status PKP pelanggan, kode transaksi bawaan (daftar kode PT + "Ikut PT"), "Selalu minta faktur pajak".
 *
 * `customers.npwp` tetap pemilik nomor NPWP; isian lain disimpan di `customers.tax_profile` (server:
 * `tax_config_service.periksa_profil_pajak`). Bentuk nomor (jumlah digit) hanya PERINGATAN di bawah isian — simpan tidak
 * dihalangi (server sama); huruf di nomor ditolak server. Jumlah digit lazim menunggu konfirmasi konsultan pajak.
 */
const ID_TYPES = [{ value: "npwp", label: "NPWP" }, { value: "nik", label: "NIK" }];
const PKP_OPTIONS = [{ value: "", label: "Belum diisi" }, { value: "pkp", label: "PKP" }, { value: "bukan", label: "Bukan PKP" }];
const DIGIT_LAZIM = { NPWP: [15, 16], NIK: [16] };

export const TAX_FORM_BLANK = {
  id_type: "npwp", nik: "", tax_name: "", tax_address: "", tax_pkp: "", kode_transaksi: "", always_tax_invoice: false,
};

/** Peringatan bentuk nomor NPWP/NIK ("" bila wajar). */
export function taxIdWarning(label, value) {
  const t = String(value || "").trim();
  if (!t) return "";
  if (!/^[0-9.\-/\s]*$/.test(t)) return `${label} hanya boleh berisi angka.`;
  const n = t.replace(/\D/g, "").length;
  const lazim = DIGIT_LAZIM[label] || [];
  return lazim.includes(n) ? "" : `${label} berisi ${n} angka; biasanya ${lazim.join(" atau ")} angka. Periksa lagi sebelum menerbitkan faktur.`;
}

/** `customers.tax_profile` → isian form. */
export function taxFormFromProfile(tp) {
  const p = tp || {};
  return {
    id_type: p.id_type || "npwp", nik: p.nik || "", tax_name: p.tax_name || "", tax_address: p.tax_address || "",
    tax_pkp: p.is_pkp === true ? "pkp" : p.is_pkp === false ? "bukan" : "",
    kode_transaksi: p.kode_transaksi || "", always_tax_invoice: !!p.always_tax_invoice,
  };
}

/** Isian form → `customers.tax_profile` (dikirim di PATCH/POST pelanggan). */
export function taxProfileFromForm(f) {
  return {
    id_type: f.id_type || "", nik: f.id_type === "nik" ? String(f.nik || "").trim() : "",
    tax_name: String(f.tax_name || "").trim(), tax_address: String(f.tax_address || "").trim(),
    is_pkp: f.tax_pkp === "pkp" ? true : f.tax_pkp === "bukan" ? false : null,
    kode_transaksi: f.kode_transaksi || "", always_tax_invoice: !!f.always_tax_invoice,
  };
}

function Field({ label, req = false, optional = false, hint = "", children }) {
  return (
    <div>
      {/* Huruf biasa seperti label bagian lain di form pelanggan yang sama (bukan `field-label` kapital). */}
      <label className="mb-1 block text-fs-12 font-semibold text-kn-text-2">{label}{req && <span className="text-kn-danger-text"> *</span>}
        {optional && !req && <span className="font-normal text-kn-text-2"> (opsional)</span>}</label>
      {children}
      {hint && <p className="mt-0.5 text-fs-12 text-kn-text-2">{hint}</p>}
    </div>
  );
}

export default function CustomerTaxSection({ number, f, set, kodePt = [], defaultOpen = false }) {
  const npwpWarn = f.id_type === "nik" ? "" : taxIdWarning("NPWP", f.npwp);
  const nikWarn = f.id_type === "nik" ? taxIdWarning("NIK", f.nik) : "";
  const kodeOptions = [{ value: "", label: "Ikut PT" },
    ...[...new Set([...(kodePt || []), ...(f.kode_transaksi ? [f.kode_transaksi] : [])])].map((k) => ({ value: k, label: k }))];
  const summary = [
    f.id_type === "nik" ? (f.nik ? `NIK ${f.nik}` : "NIK belum diisi") : (f.npwp ? `NPWP ${f.npwp}` : "tanpa NPWP"),
    (PKP_OPTIONS.find((o) => o.value === f.tax_pkp) || PKP_OPTIONS[0]).label,
    f.kode_transaksi ? `kode ${f.kode_transaksi}` : "kode ikut PT",
    f.always_tax_invoice ? "selalu minta faktur" : "",
  ].filter(Boolean).join(" · ");
  return (
    <FormSection number={number} title="Data pajak" testId="customer-section-tax"
      subtitle="Dipakai di faktur pajak. Kosongkan nama/alamat bila sama dengan data toko."
      collapsible defaultOpen={defaultOpen} summary={summary}>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Identitas pajak">
          <KNSelect data-testid="customer-tax-id-type" className="field w-full" value={f.id_type}
            onValueChange={(v) => set("id_type", v)} options={ID_TYPES} />
        </Field>
        {f.id_type === "nik" ? (
          <Field label="NIK" req>
            <input data-testid="customer-tax-nik" value={f.nik} inputMode="numeric" onChange={(e) => set("nik", e.target.value)}
              className="field" placeholder="16 angka" />
            {nikWarn && <p className="mt-0.5 text-fs-12 text-kn-warning-text" data-testid="customer-tax-nik-warning">{nikWarn}</p>}
          </Field>
        ) : (
          <Field label="NPWP" optional>
            <input data-testid="customer-npwp" value={f.npwp} onChange={(e) => set("npwp", e.target.value)} className="field"
              placeholder="00.000.000.0-000.000" />
            {npwpWarn && <p className="mt-0.5 text-fs-12 text-kn-warning-text" data-testid="customer-npwp-warning">{npwpWarn}</p>}
          </Field>
        )}
        <Field label="Nama di faktur pajak" optional>
          <input data-testid="customer-tax-name" value={f.tax_name} onChange={(e) => set("tax_name", e.target.value)} className="field"
            placeholder={f.name || "Sama dengan nama toko"} />
        </Field>
        <Field label="Alamat di faktur pajak" optional>
          <input data-testid="customer-tax-address" value={f.tax_address} onChange={(e) => set("tax_address", e.target.value)}
            className="field" placeholder="Sama dengan alamat toko" />
        </Field>
        <Field label="Status PKP pelanggan">
          <KNSelect data-testid="customer-tax-pkp" className="field w-full" value={f.tax_pkp}
            onValueChange={(v) => set("tax_pkp", v)} options={PKP_OPTIONS} />
        </Field>
        <Field label="Kode transaksi bawaan" hint="Ikut PT = kode bawaan PT (Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak).">
          <KNSelect data-testid="customer-tax-kode" className="field w-full" value={f.kode_transaksi}
            onValueChange={(v) => set("kode_transaksi", v)} options={kodeOptions} />
        </Field>
        <label className="flex items-center gap-2 text-fs-13 sm:col-span-2" data-testid="customer-tax-always">
          <input type="checkbox" checked={!!f.always_tax_invoice} onChange={(e) => set("always_tax_invoice", e.target.checked)} />
          Selalu minta faktur pajak
        </label>
      </div>
    </FormSection>
  );
}
