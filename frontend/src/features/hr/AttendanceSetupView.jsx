import { useEffect, useMemo, useState } from "react";
import apiErrorText from "../../utils/apiError";
import axios, { API } from "../../services/apiClient";
import KNTimePicker from "@/components/KNTimePicker";
import { Clock, MapPin, Cpu, Plus, Pencil, Power, Save, Crosshair, Copy, CheckCircle2 } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import ConfirmModal from "../../components/ConfirmModal";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { can } from "../../config/roles";

const DAYS = [[1, "Sen"], [2, "Sel"], [3, "Rab"], [4, "Kam"], [5, "Jum"], [6, "Sab"], [7, "Min"]];
const KIND = {
  shift: { ep: "shifts", label: "Shift", icon: Clock },
  geofence: { ep: "geofences", label: "Geofence", icon: MapPin },
  device: { ep: "devices", label: "Perangkat", icon: Cpu },
};
// Literal endpoint paths (statically verifiable FE↔BE contract — verify_api_contract gate)
const ENDPOINTS = {
  shift: { list: `${API}/hr/shifts`, item: (id) => `${API}/hr/shifts/${id}` },
  geofence: { list: `${API}/hr/geofences`, item: (id) => `${API}/hr/geofences/${id}` },
  device: { list: `${API}/hr/devices`, item: (id) => `${API}/hr/devices/${id}` },
};
const EMPTY = {
  shift: { name: "", code: "", jam_in: "08:00", jam_out: "17:00", grace_late_min: 10, break_min: 60, work_days: [1, 2, 3, 4, 5] },
  geofence: { name: "", lat: "", lon: "", radius_m: 150, address: "" },
  device: { name: "", code: "", location: "" },
};

function TabBtn({ id, active, onClick, icon: Icon, children }) {
  return (
    <button data-testid={`setup-tab-${id}`} onClick={() => onClick(id)}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition ${active ? "bg-[#0058CC] text-white" : "text-[#6B6B73] hover:bg-[#F2F4F7]"}`}>
      <Icon size={14} /> {children}
    </button>
  );
}
// UAT 24 Okt (audit UI tahap 2) — G5-28: penanda wajib (*) / "(opsional)" seragam.
function Field({ label, required = false, optional = false, children }) {
  return (<div><label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">{label}{required && <span className="text-[#C0392B]"> *</span>}{optional && <span className="font-normal text-[#9A9BA3]"> (opsional)</span>}</label>{children}</div>);
}

export default function AttendanceSetupView({ currentUser, selectedEntity }) {
  const canManage = can(currentUser?.permissions, "hr", "manage_attendance");   // Sisir gerbang peran (2026-10-20) — endpoint absensi/cuti/lembur/KPI
  const [tab, setTab] = useState("shift");
  const params = useMemo(() => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}), [selectedEntity]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [form, setForm] = useState(EMPTY.shift);
  const [editId, setEditId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deactivate, setDeactivate] = useState(null);
  const [copied, setCopied] = useState("");
  const [formErr, setFormErr] = useState("");
  const cfg = KIND[tab];
  // G5-28: tombol simpan nonaktif sampai isian wajib terisi; galat simpan tampil DI DALAM laci (dulu di bilah
  // halaman yang tertutup laci).
  const missing = !form.name?.trim() ? "Nama"
    : tab === "shift" && (!form.jam_in || !form.jam_out) ? "Jam masuk & jam keluar"
      : tab === "geofence" && (String(form.lat ?? "").trim() === "" || String(form.lon ?? "").trim() === "") ? "Latitude & longitude"
        : "";

  useEffect(() => { load(); }, [tab, selectedEntity]); // eslint-disable-line

  async function load() {
    setLoading(true);
    try {
      const r = await axios.get(ENDPOINTS[tab].list, { params });
      setItems(Array.isArray(r.data) ? r.data : []); setError("");
    } catch (e) { setError(apiErrorText(e, `Gagal memuat ${cfg.label}.`)); }
    finally { setLoading(false); }
  }
  function openCreate() { setEditId(null); setForm({ ...EMPTY[tab] }); setFormErr(""); setDrawerOpen(true); }
  function openEdit(it) {
    setEditId(it.id);
    setForm({ ...EMPTY[tab], ...it, lat: it.lat != null ? String(it.lat) : "", lon: it.lon != null ? String(it.lon) : "" });
    setFormErr("");
    setDrawerOpen(true);
  }
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const toggleDay = (d) => set("work_days", (form.work_days || []).includes(d) ? form.work_days.filter((x) => x !== d) : [...(form.work_days || []), d].sort());

  function useMyLocation() {
    if (!navigator.geolocation) { setError("Browser tidak mendukung geolokasi."); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => setForm((f) => ({ ...f, lat: pos.coords.latitude.toFixed(6), lon: pos.coords.longitude.toFixed(6) })),
      () => setError("Gagal mengambil lokasi. Pastikan izin lokasi aktif."), { enableHighAccuracy: true, timeout: 10000 });
  }

  async function submit() {
    if (missing) { setFormErr(`${missing} wajib diisi.`); return; }
    setSaving(true); setFormErr("");
    let payload = { ...form };
    if (tab === "geofence") payload = { ...payload, lat: parseFloat(form.lat) || 0, lon: parseFloat(form.lon) || 0, radius_m: parseInt(form.radius_m) || 150 };
    if (tab === "shift") payload = { ...payload, grace_late_min: parseInt(form.grace_late_min) || 0, break_min: parseInt(form.break_min) || 0 };
    if (selectedEntity && selectedEntity !== "all") payload.entity_id = selectedEntity;
    try {
      if (editId) await axios.patch(ENDPOINTS[tab].item(editId), { data: payload });
      else await axios.post(ENDPOINTS[tab].list, payload);
      setNotice(editId ? `${cfg.label} diperbarui.` : `${cfg.label} baru dibuat.`); setDrawerOpen(false); load();
    } catch (e) { setFormErr(apiErrorText(e, `Gagal menyimpan ${cfg.label}.`)); }
    finally { setSaving(false); }
  }
  async function doDeactivate(it) {
    try { await axios.delete(ENDPOINTS[tab].item(it.id)); setNotice(`${it.name} dinonaktifkan.`); setDeactivate(null); load(); }
    catch (e) { setError(apiErrorText(e, "Gagal menonaktifkan.")); setDeactivate(null); }
  }
  function copyToken(t) { navigator.clipboard?.writeText(t); setCopied(t); setTimeout(() => setCopied(""), 1500); }

  return (
    <div data-testid="attendance-setup-view">
      {notice && (<div className="notice-bar success" data-testid="setup-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>)}
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="setup-error" />

      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2"><cfg.icon size={16} className="text-[#0058CC]" /><h2 data-testid="setup-title">Shift & Geofence</h2></div>
          <div className="flex items-center gap-1 bg-[#F7F8FA] rounded-lg p-1">
            <TabBtn id="shift" active={tab === "shift"} onClick={setTab} icon={Clock}>Shift</TabBtn>
            <TabBtn id="geofence" active={tab === "geofence"} onClick={setTab} icon={MapPin}>Geofence</TabBtn>
            <TabBtn id="device" active={tab === "device"} onClick={setTab} icon={Cpu}>Perangkat</TabBtn>
          </div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-head">
          <h3 className="text-[12px] font-bold">Daftar {cfg.label}</h3>
          {canManage && <button data-testid="setup-create-button" onClick={openCreate} className="primary-button"><Plus size={13} /> Tambah {cfg.label}</button>}
        </div>
        {loading ? (
          <div className="py-10 text-center text-[12px] text-[#6B6B73]" data-testid="setup-loading">Memuat {cfg.label}...</div>
        ) : items.length === 0 ? (
          <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="setup-empty"><cfg.icon className="mx-auto mb-2 text-gray-300" size={28} /><p>Belum ada {cfg.label}. Tambah {cfg.label} pertama.</p></div>
        ) : (
          <div className="divide-y divide-[#EFF0F2]">
            {items.map((it) => (
              <div key={it.id} data-testid={`setup-row-${it.id}`} className="flex items-center justify-between px-3 py-2.5 hover:bg-[#FAFBFC] gap-3">
                <div className="min-w-0 flex items-center gap-2">
                  <EntityBadge entityId={it.entity_id} />
                  <div className="min-w-0">
                    <p className="text-[12px] font-semibold truncate">{it.name} {it.status === "inactive" && <span className="status-pill pill-muted ml-1">Nonaktif</span>}</p>
                    <p className="text-[10.5px] text-[#6B6B73] truncate">
                      {tab === "shift" && `${it.jam_in}–${it.jam_out} · toleransi ${it.grace_late_min} mnt · ${(it.work_days || []).map((d) => DAYS.find((x) => x[0] === d)?.[1]).join(",")}`}
                      {tab === "geofence" && `${Number(it.lat).toFixed(5)}, ${Number(it.lon).toFixed(5)} · radius ${it.radius_m}m${it.address ? ` · ${it.address}` : ""}`}
                      {tab === "device" && `${it.code || "—"}${it.location ? ` · ${it.location}` : ""} · sync: ${it.last_sync ? it.last_sync.slice(0, 16).replace("T", " ") : "belum pernah"}`}
                    </p>
                    {tab === "device" && (
                      <button data-testid={`device-token-${it.id}`} onClick={() => copyToken(it.device_token)} className="mt-1 inline-flex items-center gap-1 text-[10.5px] text-[#0058CC] hover:underline">
                        {copied === it.device_token ? <><CheckCircle2 size={11} /> Token disalin</> : <><Copy size={11} /> Salin token perangkat</>}
                      </button>
                    )}
                  </div>
                </div>
                {canManage && (
                  <div className="flex items-center gap-1 shrink-0">
                    <button data-testid={`setup-edit-${it.id}`} onClick={() => openEdit(it)} className="icon-button" title="Ubah"><Pencil size={13} /></button>
                    {it.status !== "inactive" && <button data-testid={`setup-deactivate-${it.id}`} onClick={() => setDeactivate(it)} className="icon-button text-red-400 hover:text-red-600" title="Nonaktifkan"><Power size={13} /></button>}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <Sheet open={drawerOpen} onOpenChange={(o) => { if (!o) setDrawerOpen(false); }}>
        <SheetContent side="right" className="w-full sm:max-w-md overflow-y-auto p-0" data-testid="setup-drawer">
          <SheetHeader className="px-5 py-4 border-b border-[#EFF0F2]"><SheetTitle data-testid="setup-drawer-title">{editId ? `Ubah ${cfg.label}` : `Tambah ${cfg.label}`}</SheetTitle></SheetHeader>
          <div className="px-5 py-4 space-y-3">
            <Field label="Nama" required><input data-testid="setup-name" value={form.name} onChange={(e) => set("name", e.target.value)} className="field" placeholder={tab === "shift" ? "mis. Shift Pagi" : tab === "geofence" ? "mis. Kantor Pusat" : "mis. Mesin absen pintu utama"} /></Field>

            {tab === "shift" && (<>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Jam Masuk" required><KNTimePicker data-testid="setup-jam-in" clearable={false} value={form.jam_in} onChange={(v) => set("jam_in", v)} /></Field>
                <Field label="Jam Keluar" required><KNTimePicker data-testid="setup-jam-out" clearable={false} value={form.jam_out} onChange={(v) => set("jam_out", v)} /></Field>
                <Field label="Toleransi Telat (menit)"><input data-testid="setup-grace" type="number" value={form.grace_late_min} onChange={(e) => set("grace_late_min", e.target.value)} className="field tabular-nums" /></Field>
                <Field label="Istirahat (menit)"><input data-testid="setup-break" type="number" value={form.break_min} onChange={(e) => set("break_min", e.target.value)} className="field tabular-nums" /></Field>
              </div>
              <Field label="Hari Kerja">
                <div className="flex flex-wrap gap-1">
                  {DAYS.map(([d, lbl]) => (
                    <button key={d} type="button" data-testid={`setup-day-${d}`} onClick={() => toggleDay(d)}
                      className={`px-2.5 py-1 rounded-md text-[11px] font-semibold border ${(form.work_days || []).includes(d) ? "bg-[#0058CC] text-white border-[#0058CC]" : "bg-white text-[#6B6B73] border-[#E2E4E8]"}`}>{lbl}</button>
                  ))}
                </div>
              </Field>
            </>)}

            {tab === "geofence" && (<>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Latitude" required><input data-testid="setup-lat" value={form.lat} onChange={(e) => set("lat", e.target.value)} className="field tabular-nums" placeholder="mis. -6.9" /></Field>
                <Field label="Longitude" required><input data-testid="setup-lon" value={form.lon} onChange={(e) => set("lon", e.target.value)} className="field tabular-nums" placeholder="mis. 107.6" /></Field>
              </div>
              <button type="button" data-testid="setup-use-location" onClick={useMyLocation} className="secondary-button"><Crosshair size={13} /> Gunakan Lokasi Saya</button>
              <Field label="Radius (meter)"><input data-testid="setup-radius" type="number" value={form.radius_m} onChange={(e) => set("radius_m", e.target.value)} className="field tabular-nums" /></Field>
              <Field label="Alamat" optional><input data-testid="setup-address" value={form.address} onChange={(e) => set("address", e.target.value)} className="field" placeholder="mis. Jl. Asia Afrika No. 1" /></Field>
            </>)}

            {tab === "device" && (<>
              <Field label="Nomor seri / kode" optional><input data-testid="setup-code" value={form.code} onChange={(e) => set("code", e.target.value)} className="field" placeholder="mis. nomor seri di label mesin" /></Field>
              <Field label="Lokasi pemasangan" optional><input data-testid="setup-location" value={form.location} onChange={(e) => set("location", e.target.value)} className="field" placeholder="mis. Lobi kantor pusat" /></Field>
              <p className="text-[11px] text-[#6B6B73]">Setelah dibuat, salin <b>token perangkat</b> dari daftar untuk dipasang di aplikasi penghubung mesin absen.</p>
            </>)}
          </div>
          {/* G5-28: kaki standar — Batal kiri, tombol utama kanan berukuran normal (dulu terbalik & lebar penuh). */}
          <div className="sticky bottom-0 bg-white border-t border-[#EFF0F2] px-5 py-3">
            {formErr && <p data-testid="setup-form-error" className="mb-2 rounded-md border border-[#FCA5A5] bg-[#FEF2F2] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#B91C1C]">{formErr}</p>}
            <div className="flex justify-end gap-2">
              <button data-testid="setup-cancel" onClick={() => setDrawerOpen(false)} className="secondary-button">Batal</button>
              <button data-testid="setup-save" disabled={saving || !!missing} title={missing ? `${missing} wajib diisi` : undefined} onClick={submit} className="primary-button"><Save size={14} /> {saving ? "Menyimpan..." : editId ? "Simpan Perubahan" : `Buat ${cfg.label}`}</button>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      <ConfirmModal open={!!deactivate} title={`Nonaktifkan ${cfg.label} · ${deactivate?.name || ""}`}
        message={`${cfg.label} akan dinonaktifkan dan tidak dipakai untuk absensi baru.`} confirmLabel="Nonaktifkan" danger
        onConfirm={() => doDeactivate(deactivate)} onCancel={() => setDeactivate(null)} testId="setup-deactivate-modal" />
    </div>
  );
}
