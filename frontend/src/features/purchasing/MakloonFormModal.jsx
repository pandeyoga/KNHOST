/**
 * MakloonFormModal (M1) — buat/edit master makloon.
 * POST /makloons | PATCH /makloons/{id} (via {data}).
 */
import { useState } from "react";
import LocationFields, { locationIncomplete } from "../../components/LocationFields";
const LOC_KEYS = ["country", "country_code", "province", "province_code", "city", "city_code", "district", "district_code", "postal_code"];
const pickLoc = (o = {}) => Object.fromEntries(LOC_KEYS.map((k) => [k, o[k] || ""]));
import MoneyInput from "@/components/MoneyInput";
import { Factory, Save } from "lucide-react";
import FormModal from "../../components/FormModal";
import axios, { API } from "../../services/apiClient";
import KNSelect from "../../components/KNSelect";
import useProcessTypes from "../../hooks/useProcessTypes";
import useUomConversions from "../../hooks/useUomConversions";
import { uomSelectOptions } from "../../utils/uomCatalog";
import apiErrorText from "../../utils/apiError";

const TARIFF_UNITS = [
  { value: "output", label: "per Output" }, { value: "input", label: "per Input" }, { value: "roll", label: "per Roll" },
];

export default function MakloonFormModal({ open, editTarget, entities = [], terms = [], selectedEntity, onClose, onSaved, onError }) {
  const isEdit = !!editTarget;
  // FASE T (4a) — daftar kemampuan mitra dari registry hidup. Dulu daftarnya hardcode 5
  // nilai, sehingga mitra ber-kemampuan `screen`/`rajut`/`pre_treatment` tidak bisa
  // dicentang sama sekali: kemampuan yang sudah ada pun tak terlihat saat disunting.
  const { options: processOptions } = useProcessTypes();
  const procList = processOptions();
  // FASE U — satuan kapasitas mitra dari MASTER satuan (panjang · berat · hitungan).
  // Dulu daftarnya diketik 4 nilai, jadi mitra yang mengukur kapasitasnya dalam
  // `panel` (satuan yang baru ditambah pemilik) tidak bisa dicatat sama sekali.
  useUomConversions();          // memuat & membagikan katalog satuan ke penyimpan modul
  const capacityUnitOptions = uomSelectOptions({
    dimensions: ["length", "weight", "count"],
    extra: [editTarget?.capacity_unit || "yard"],
  });
  const [form, setForm] = useState(() => ({
    name: editTarget?.name || "", npwp: editTarget?.npwp || "", pic_name: editTarget?.pic_name || "",
    phone: editTarget?.phone || "", email: editTarget?.email || "", city: editTarget?.city || "", ...pickLoc(editTarget || {}),
    address: editTarget?.address || "", process_types: editTarget?.process_types || [],
    capacity_per_month: editTarget?.capacity_per_month ? String(editTarget.capacity_per_month) : "",
    capacity_unit: editTarget?.capacity_unit || "yard",
    default_tariff: editTarget?.default_tariff ? String(editTarget.default_tariff) : "",
    tariff_unit: editTarget?.tariff_unit || "output",
    payment_term_code: editTarget?.payment_term_code || "",
    lead_time_days: editTarget?.lead_time_days != null ? String(editTarget.lead_time_days) : "",
    entity_id: editTarget?.entity_id || (selectedEntity && selectedEntity !== "all" ? selectedEntity : ""),
    notes: editTarget?.notes || "",
  }));
  const [saving, setSaving] = useState(false);
  const [modalErr, setModalErr] = useState("");   // galat tampil di modal ini
  const [tried, setTried] = useState(false);       // G0-08 — galat blok alamat tampil setelah Simpan ditekan
  if (!open) return null;
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggleProc = (p) => setForm((f) => ({ ...f, process_types: f.process_types.includes(p) ? f.process_types.filter((x) => x !== p) : [...f.process_types, p] }));

  const save = async () => {
    setTried(true);
    if (!form.name.trim()) { setModalErr("Nama mitra makloon wajib diisi."); return; }
    const locErr = locationIncomplete(pickLoc(form));
    if (locErr) { setModalErr(`Alamat: ${locErr}`); return; }
    setSaving(true);
    const payload = {
      ...form,
      capacity_per_month: parseFloat(form.capacity_per_month) || 0,
      default_tariff: parseFloat(form.default_tariff) || 0,
      lead_time_days: parseInt(form.lead_time_days, 10) || 0,
    };
    try {
      if (isEdit) await axios.patch(`${API}/makloons/${editTarget.id}`, { data: payload });
      else await axios.post(`${API}/makloons`, payload);
      onSaved?.();
    } catch (e) { setModalErr(apiErrorText(e, "Gagal menyimpan mitra makloon.")); setSaving(false); }
  };

  // Fase 3 · P5 (L-03) — dulu `div fixed inset-0` buatan sendiri; kini FormModal baku (layar penuh 1 kolom di HP,
  // Esc berlapis, tombol simpan & galat di kaki yang selalu terlihat). Isian sama.
  return (
    <FormModal open={open} onClose={onClose} icon={Factory} size="lg" testId="makloon-form-modal"
      title={isEdit ? "Ubah Mitra Makloon" : "Tambah Mitra Makloon"} busy={saving} error={modalErr}
      footer={(
        <div className="flex justify-end gap-2">
          <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
          <button type="button" data-testid="makloon-form-save" className="primary-button" disabled={saving} onClick={save}><Save size={14} /> {saving ? "Menyimpan…" : isEdit ? "Simpan Perubahan" : "Tambah Mitra Makloon"}</button>
        </div>
      )}>
        <div className="space-y-3">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Nama Mitra Makloon" req><input data-testid="makloon-name-input" className="field" value={form.name} onChange={set("name")} placeholder="PT Tenun Nusantara" /></Field>
            <Field label="NPWP"><input data-testid="makloon-npwp-input" className="field" value={form.npwp} onChange={set("npwp")} placeholder="00.000.000.0-000.000" /></Field>
            <Field label="Nama PIC"><input data-testid="makloon-pic-input" className="field" value={form.pic_name} onChange={set("pic_name")} placeholder="Nama kontak" /></Field>
            <Field label="Telepon"><input data-testid="makloon-phone-input" className="field" value={form.phone} onChange={set("phone")} placeholder="0812xxxx" /></Field>
            <Field label="Email"><input data-testid="makloon-email-input" className="field" value={form.email} onChange={set("email")} placeholder="pic@makloon.co.id" /></Field>
            <LocationFields testId="makloon-loc" value={pickLoc(form)} showErrors={tried} onChange={(patch) => setForm((p) => ({ ...p, ...patch }))} />
          </div>
          <Field label="Jenis Proses (Kemampuan)">
            <div className="flex flex-wrap gap-1.5" data-testid="makloon-process-types">
              {procList.map(({ value: k, label: lbl }) => (
                <button key={k} type="button" data-testid={`makloon-proc-${k}`} onClick={() => toggleProc(k)}
                  className={`rounded-full border px-3 py-1 text-[11.5px] font-medium ${form.process_types.includes(k) ? "border-[#0058CC] bg-[#0058CC] text-white" : "border-[#E5E5EA] bg-white text-[#3C3C43] hover:border-[#0058CC]"}`}>{lbl}</button>
              ))}
            </div>
          </Field>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field label="Kapasitas / Bulan"><input data-testid="makloon-capacity-input" type="number" className="field" value={form.capacity_per_month} onChange={set("capacity_per_month")} placeholder="mis. 50000" /></Field>
            <Field label="Satuan Kapasitas">
              <KNSelect data-testid="makloon-capacity-unit" className="field" value={form.capacity_unit} onValueChange={(v) => setForm({ ...form, capacity_unit: v })}
                options={capacityUnitOptions} />
            </Field>
            <Field label="Tarif Jasa Default (Rp)"><MoneyInput testId="makloon-tariff-input" className="field" value={form.default_tariff} onChange={(v) => set("default_tariff")({ target: { value: v } })} placeholder="mis. 3500" /></Field>
            <Field label="Basis Tarif">
              <KNSelect data-testid="makloon-tariff-unit" className="field" value={form.tariff_unit} onValueChange={(v) => setForm({ ...form, tariff_unit: v })} options={TARIFF_UNITS} />
            </Field>
            <Field label="Lead Time (hari)"><input data-testid="makloon-leadtime-input" type="number" className="field" value={form.lead_time_days} onChange={set("lead_time_days")} placeholder="mis. 10" /></Field>
            <Field label="Termin Pembayaran">
              <KNSelect data-testid="makloon-term-select" className="field" value={form.payment_term_code} onValueChange={(v) => setForm({ ...form, payment_term_code: v })}
                options={[{ value: "", label: "— Tidak ditentukan —" }, ...terms.map((t) => ({ value: t.code, label: t.name }))]} />
            </Field>
            <Field label="Badan Usaha">
              <KNSelect data-testid="makloon-entity-select" className="field" value={form.entity_id} onValueChange={(v) => setForm({ ...form, entity_id: v })}
                options={[{ value: "", label: "— Default (KSC) —" }, ...entities.map((e) => ({ value: e.id, label: e.short_name || e.legal_name }))]} />
            </Field>
            <Field label="Alamat"><input data-testid="makloon-address-input" className="field" value={form.address} onChange={set("address")} placeholder="Alamat lengkap" /></Field>
          </div>
          <Field label="Catatan / Kapasitas"><textarea data-testid="makloon-notes-input" className="field" rows="2" value={form.notes} onChange={set("notes")} placeholder="Catatan kapasitas / spesialisasi…" /></Field>
        </div>
    </FormModal>
  );
}

function Field({ label, req, children }) {
  return (
    <label className="block">
      {/* G4-16 — label 11px seragam dengan form lain (blok lokasi MAJUSCULE milik LocationFields → G0-08). */}
      <span className="mb-1 block text-[11px] font-semibold text-[#6B6B73]">{label} {req && <span className="text-[#D14343]">*</span>}</span>
      {children}
    </label>
  );
}
