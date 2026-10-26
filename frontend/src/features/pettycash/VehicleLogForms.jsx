/**
 * Pop-up form Log Perjalanan & Master Kendaraan (dipakai VehicleLogsView).
 *
 * Fase 4 · R2 (L-03) — diekstrak dari `VehicleLogsView.jsx`; `.modal-card` buatan sendiri (klik latar tanpa gestur
 * utuh, tanpa Esc, tombol × tanpa nama) → `FormModal` baku: Esc lewat tumpukan lapisan, kaki Simpan menempel, layar
 * penuh 1 kolom di HP (isian SAMA dengan desktop — keputusan pemilik). Galat tetap di DALAM pop-up. Testid tetap
 * (`veh-log-modal`, `veh-form-modal`, `veh-log-*`, `veh-form-*`, `veh-log-save`, `veh-form-save`).
 */
import { useState } from "react";
import { Car, Route } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "../../components/MoneyInput";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatQty } from "../../utils/formatters";

export const JENIS = [
  { value: "mobil", label: "Mobil" }, { value: "motor", label: "Motor" },
  { value: "truk", label: "Truk" }, { value: "lainnya", label: "Lainnya" },
];

function F({ label, req, children }) {
  return (<div className="grid gap-1.5"><label className="text-[11px] font-bold uppercase text-[#6B6B73]">{label}{req && <span className="req"> *</span>}</label>{children}</div>);
}

function Err({ testId, msg, onDismiss }) {
  if (!msg) return null;
  return (
    <div className="notice-bar danger" data-testid={testId}>
      <span>{msg}</span>
      <button type="button" aria-label="Tutup pesan" onClick={onDismiss}>×</button>
    </div>
  );
}

function Footer({ onClose, onSave, busy, testId }) {
  return (
    <div className="flex justify-end gap-2">
      <button type="button" className="secondary-button" onClick={onClose} disabled={busy}>Batal</button>
      <button type="button" data-testid={testId} className="primary-button" onClick={onSave} disabled={busy}>{busy ? "Menyimpan…" : "Simpan"}</button>
    </div>
  );
}

// ─── Log form (modal) ────────────────────────────────────────────────────────
export function LogFormModal({ form, vehicles, entities, selectedEntity, onClose, onSaved }) {
  const [f, setF] = useState(form);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const isEdit = !!f.id;
  const upd = (k, v) => setF({ ...f, [k]: v });
  const total = (Number(f.bbm) || 0) + (Number(f.tol) || 0) + (Number(f.parkir) || 0) + (Number(f.lain_lain) || 0);
  const jarak = Math.max(0, (Number(f.km_akhir) || 0) - (Number(f.km_awal) || 0));

  async function save() {
    setErr("");
    if (!f.vehicle_id && !f.no_polisi) { setErr("Pilih kendaraan atau isi No. Polisi."); return; }
    setBusy(true);
    try {
      const body = {
        vehicle_id: f.vehicle_id || "", no_polisi: f.no_polisi || "", tanggal: f.tanggal,
        km_awal: Number(f.km_awal) || 0, km_akhir: Number(f.km_akhir) || 0,
        bbm: Number(f.bbm) || 0, tol: Number(f.tol) || 0, parkir: Number(f.parkir) || 0, lain_lain: Number(f.lain_lain) || 0,
        tujuan: f.tujuan || "", driver: f.driver || "", pemakai: f.pemakai || "", mengetahui: f.mengetahui || "",
      };
      if (isEdit) await axios.patch(`${API}/vehicle-usage-logs/${f.id}`, body);
      else {
        body.entity_id = selectedEntity && selectedEntity !== "all" ? selectedEntity : (entities[0]?.id || "");
        await axios.post(`${API}/vehicle-usage-logs`, body);
      }
      onSaved(isEdit ? "Log diperbarui." : "Log perjalanan dicatat.");
    } catch (e) { setErr(apiErrorText(e, "Gagal menyimpan log.")); } finally { setBusy(false); }
  }

  return (
    <FormModal open onClose={onClose} icon={Route} testId="veh-log-modal" busy={busy}
      title={isEdit ? "Ubah Log Perjalanan" : "Catat Perjalanan Kendaraan"}
      footer={<Footer onClose={onClose} onSave={save} busy={busy} testId="veh-log-save" />}>
      <Err testId="veh-log-form-error" msg={err} onDismiss={() => setErr("")} />
      <div className="grid gap-3 sm:grid-cols-2">
        {/* Audit UI 24 Okt (137): wajib = kendaraan dari master ATAU No. Polisi (salah satu). */}
        <F label="Kendaraan" req>
          <KNSelect data-testid="veh-log-vehicle" className="form-input" value={f.vehicle_id} onValueChange={(v) => { const veh = vehicles.find((x) => x.id === v); setF({ ...f, vehicle_id: v, no_polisi: veh?.no_polisi || f.no_polisi }); }}
            placeholder="Pilih dari master" options={vehicles.map((v) => ({ value: v.id, label: `${v.no_polisi} · ${v.nama || v.jenis}` }))} />
        </F>
        <F label="No. Polisi (bila tak ada di master)"><input data-testid="veh-log-nopol" className="form-input" value={f.no_polisi} onChange={(e) => upd("no_polisi", e.target.value)} placeholder="B 1234 XX" /></F>
        <F label="Tanggal"><KNDatePicker data-testid="veh-log-tanggal" value={f.tanggal} onChange={(v) => upd("tanggal", v)} clearable={false} /></F>
        <F label="Tujuan"><input data-testid="veh-log-tujuan" className="form-input" value={f.tujuan} onChange={(e) => upd("tujuan", e.target.value)} placeholder="mis. Kirim sample ke pelanggan" /></F>
        <F label="KM Awal"><input type="number" data-testid="veh-log-kmawal" className="form-input text-right" value={f.km_awal} onChange={(e) => upd("km_awal", e.target.value)} /></F>
        <F label="KM Akhir"><input type="number" data-testid="veh-log-kmakhir" className="form-input text-right" value={f.km_akhir} onChange={(e) => upd("km_akhir", e.target.value)} /></F>
        <F label="BBM (Rp)"><MoneyInput testId="veh-log-bbm" className="form-input text-right" value={f.bbm} onChange={(v) => upd("bbm", v)} /></F>
        <F label="Tol (Rp)"><MoneyInput testId="veh-log-tol" className="form-input text-right" value={f.tol} onChange={(v) => upd("tol", v)} /></F>
        <F label="Parkir (Rp)"><MoneyInput testId="veh-log-parkir" className="form-input text-right" value={f.parkir} onChange={(v) => upd("parkir", v)} /></F>
        <F label="Lain-lain (Rp)"><MoneyInput testId="veh-log-lain" className="form-input text-right" value={f.lain_lain} onChange={(v) => upd("lain_lain", v)} /></F>
        <F label="Sopir"><input data-testid="veh-log-driver" className="form-input" value={f.driver} onChange={(e) => upd("driver", e.target.value)} /></F>
        <F label="Pemakai"><input data-testid="veh-log-pemakai" className="form-input" value={f.pemakai} onChange={(e) => upd("pemakai", e.target.value)} /></F>
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2">
        <span className="text-[11.5px] text-[#6B6B73]">Jarak: <b className="tabular-nums">{formatQty(jarak)} km</b></span>
        <span className="text-[12px] font-bold text-[#0058CC]">Total Biaya: <span data-testid="veh-log-total" className="tabular-nums">{formatCurrency(total)}</span></span>
      </div>
    </FormModal>
  );
}

// ─── Vehicle master form (modal) ─────────────────────────────────────────────
export function VehicleFormModal({ form, entities, selectedEntity, onClose, onSaved }) {
  const [f, setF] = useState(form);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const isEdit = !!f.id;
  const upd = (k, v) => setF({ ...f, [k]: v });

  async function save() {
    setErr("");
    if (!f.no_polisi?.trim()) { setErr("No. Polisi wajib diisi."); return; }
    setBusy(true);
    try {
      const body = { no_polisi: f.no_polisi, nama: f.nama || "", jenis: f.jenis || "mobil", active: f.active !== false };
      if (isEdit) await axios.patch(`${API}/vehicles/${f.id}`, body);
      else { body.entity_id = selectedEntity && selectedEntity !== "all" ? selectedEntity : (entities[0]?.id || ""); await axios.post(`${API}/vehicles`, body); }
      onSaved(isEdit ? "Kendaraan diperbarui." : "Kendaraan ditambahkan.");
    } catch (e) { setErr(apiErrorText(e, "Gagal menyimpan kendaraan.")); } finally { setBusy(false); }
  }

  return (
    <FormModal open onClose={onClose} size="sm" icon={Car} testId="veh-form-modal" busy={busy}
      title={isEdit ? "Ubah Kendaraan" : "Tambah Kendaraan"}
      footer={<Footer onClose={onClose} onSave={save} busy={busy} testId="veh-form-save" />}>
      <Err testId="veh-form-error" msg={err} onDismiss={() => setErr("")} />
      <div className="grid gap-3">
        <F label="No. Polisi" req><input data-testid="veh-form-nopol" className="form-input" value={f.no_polisi} onChange={(e) => upd("no_polisi", e.target.value)} placeholder="B 1234 XX" /></F>
        <F label="Nama / Merk"><input data-testid="veh-form-nama" className="form-input" value={f.nama} onChange={(e) => upd("nama", e.target.value)} placeholder="mis. Toyota Avanza" /></F>
        <F label="Jenis"><KNSelect data-testid="veh-form-jenis" className="form-input" value={f.jenis} onValueChange={(v) => upd("jenis", v)} options={JENIS} /></F>
        <label className="flex items-center gap-2 text-[12px]"><input type="checkbox" data-testid="veh-form-active" checked={f.active !== false} onChange={(e) => upd("active", e.target.checked)} /> Aktif</label>
      </div>
    </FormModal>
  );
}
