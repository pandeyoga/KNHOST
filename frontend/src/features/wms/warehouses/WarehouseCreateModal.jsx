/**
 * WarehouseCreateModal — form "Gudang baru" (fase 3 · P5, L-03 md-warehouses).
 *
 * Audit UI tahap 2: Master Gudang memakai EMPAT pola edit di satu halaman — "Lokasi" pop-up FormModal, "Gudang baru"
 * form inline yang mendorong tabel ke bawah, "Atur mode" laci kanan, "Profil" laci lain tanpa Batal. Kini keempatnya
 * FormModal baku. Form ini diekstrak dari WarehouseMasterView (batas 500 baris); isian & aturan simpan TIDAK berubah
 * (state & `onSubmit` tetap milik induk).
 */
import { Save, Warehouse } from "lucide-react";
import FormModal from "../../../components/FormModal";
import LocationFields from "../../../components/LocationFields";
import { entityFullById } from "../../../utils/entityLabel";

export default function WarehouseCreateModal({
  open, onClose, form, setForm, pickLoc, locTried, saving, canWrite, writeBlockHint, entities, selectedEntity,
  onSubmit, error,
}) {
  return (
    <FormModal open={open} onClose={onClose} title="Gudang baru" icon={Warehouse} size="lg" testId="wh-create-form"
      subtitle="Kode, alamat, bin pertama & siapa yang boleh memakai" busy={saving} error={error}
      footer={(
        <div className="grid gap-1">
          <div className="flex justify-end gap-2">
            <button type="button" className="secondary-button" onClick={onClose} disabled={saving}>Batal</button>
            <button type="button" data-testid="wh-form-save" className="primary-button" onClick={onSubmit}
              disabled={saving || (!canWrite && form.sharing_mode === "dedicated")}
              title={!canWrite ? writeBlockHint : ""}>
              <Save size={14} /> {saving ? "Menyimpan…" : "Simpan gudang"}
            </button>
          </div>
          {!canWrite && (
            <p data-testid="wh-form-scope-note" className="text-right text-[11px] text-[#8C4A00]">{writeBlockHint}</p>
          )}
        </div>
      )}>
      <div className="grid gap-2 sm:grid-cols-2">
        {[["code", "Kode gudang *", "mis. WH-SMG"], ["name", "Nama gudang *", "mis. Gudang Semarang"],
          ["bin_code", "Kode bin pertama", "mis. A1-01"]].map(([key, label, ph]) => (
          <label key={key} className="block">
            <span className="field-label">{label}</span>
            <input data-testid={`wh-form-${key}`} className="field" placeholder={ph}
              value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value })} />
          </label>
        ))}
        <label className="block">
          <span className="field-label">Kapasitas bin pertama (roll)</span>
          <input data-testid="wh-form-bin_capacity" className="field" type="number"
            placeholder="mis. 1000" value={form.bin_capacity}
            onChange={(e) => setForm({ ...form, bin_capacity: e.target.value })} />
        </label>
        <LocationFields testId="wh-form-loc" compact showErrors={locTried} value={pickLoc(form)} onChange={(p) => setForm((f) => ({ ...f, ...p }))} />
        <div className="grid grid-cols-2 gap-2">
          <label className="block">
            <span className="field-label">Lintang (opsional)</span>
            <input data-testid="wh-form-lat" className="field" type="number" step="0.0001"
              placeholder="mis. -6.9175" value={form.lat}
              onChange={(e) => setForm({ ...form, lat: e.target.value })} />
          </label>
          <label className="block">
            <span className="field-label">Bujur (opsional)</span>
            <input data-testid="wh-form-lng" className="field" type="number" step="0.0001"
              placeholder="mis. 107.6191" value={form.lng}
              onChange={(e) => setForm({ ...form, lng: e.target.value })} />
          </label>
        </div>
      </div>

      <div className="mt-3 grid gap-1.5">
        <p className="text-[11px] font-bold uppercase tracking-wide text-[#6B6B73]">Siapa yang boleh memakai?</p>
        <div className="grid gap-1.5 sm:grid-cols-2">
          <button type="button" data-testid="wh-form-mode-dedicated"
            onClick={() => setForm({ ...form, sharing_mode: "dedicated" })}
            className={`rounded-md border px-2.5 py-2 text-left text-[12px] ${
              form.sharing_mode === "dedicated" ? "border-[#6B219A] bg-[#F3E9FA]" : "border-[#E5E5EA] bg-white"}`}>
            <span className="block font-bold">Khusus {entityFullById(entities, selectedEntity)}</span>
            <span className="block text-[11px] text-[#6B6B73]">Bawaan — badan usaha lain tidak melihat gudang ini.</span>
          </button>
          <button type="button" data-testid="wh-form-mode-shared"
            onClick={() => setForm({ ...form, sharing_mode: "shared" })}
            className={`rounded-md border px-2.5 py-2 text-left text-[12px] ${
              form.sharing_mode === "shared" ? "border-[#0058CC] bg-[#EAF2FF]" : "border-[#E5E5EA] bg-white"}`}>
            <span className="block font-bold">Bersama semua badan usaha</span>
            <span className="block text-[11px] text-[#6B6B73]">Dipakai bergantian oleh semua badan usaha.</span>
          </button>
        </div>
      </div>
    </FormModal>
  );
}
