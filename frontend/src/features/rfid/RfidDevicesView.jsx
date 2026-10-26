/**
 * RfidDevicesView — perangkat RFID (pembaca / gerbang / printer) per gudang.
 *
 * Fase 3 · P2 — D-29: dirender sebagai tab "RFID (pembaca/gerbang)" di Pengaturan › Integrasi & Sistem ›
 * Perangkat (`settings-devices`, `embedded`); alamat lama `cs-rfid-devices` = alias ke tab itu. L-02: kepala
 * halaman baku (`PageHeader`); L-03: form "Perangkat Baru" yang dulu diselipkan di tengah halaman → `FormModal`.
 */
import { useEffect, useState } from "react";
import { Wifi, RefreshCw, Trash2, Plus, Cpu, Router, Power, RadioTower } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import { PageHeader } from "../../components/ListPageParts";
import axios, { API } from "../../services/apiClient";
import { askConfirm } from "../../services/confirmService";
import { Stat, EmptyBox, Pill, SectionCard, fmtTime, useWarehouses } from "./rfidShared";

const EMPTY_FORM = { code: "", name: "", type: "gate", direction: "out", warehouse_id: "", location: "" };

const TYPE_LABEL = { gate: "Gerbang", fixed_reader: "Pembaca tetap", handheld: "Pembaca genggam", printer: "Printer RFID" };
const TYPE_OPTS = [
  { value: "gate", label: "Gerbang (pintu masuk/keluar)" },
  { value: "fixed_reader", label: "Pembaca tetap (zona)" },
  { value: "handheld", label: "Pembaca genggam" },
  { value: "printer", label: "Printer RFID (cetak tag)" },
];
const DIR_OPTS = [{ value: "in", label: "Masuk (in)" }, { value: "out", label: "Keluar (out)" }];

export default function RfidDevicesView({ currentUser, embedded = false }) {
  const { warehouses, whId, setWhId, whOpts } = useWarehouses();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [revealed, setRevealed] = useState(null); // RF-12 — key tampil sekali, hanya di memori layar
  const [form, setForm] = useState(EMPTY_FORM);
  const [formErr, setFormErr] = useState("");
  // Aturan gudang: lokasi perangkat mengikuti master zona/rak/bin gudang — bukan ketik bebas.
  const locOpts = (() => {
    const wh = (warehouses || []).find((w) => w.id === form.warehouse_id);
    const out = [{ value: "", label: "— Pilih lokasi —" }];
    const DOCKS = ["Dock Terima", "Dock Kirim", "Gate Utama"];
    DOCKS.forEach((d) => out.push({ value: d, label: `${d} (area)` }));
    (wh?.zones || []).forEach((z) => {
      out.push({ value: z.name || z.id, label: `Zona ${z.name || z.id}` });
      (z.racks || []).forEach((r) => {
        const bins = (r.bins || []).concat(...(r.levels || []).map((lv) => lv.bins || []));
        bins.forEach((b) => { const code = b.code || b.id; out.push({ value: code, label: `${z.name || z.id} › ${r.name || r.code || r.id} › ${code}` }); });
      });
    });
    return out;
  })();
  const isAdmin = currentUser?.role === "admin";

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const params = whId ? { warehouse_id: whId } : {};
      const r = await axios.get(`${API}/rfid/devices`, { params });
      setDevices(r.data.devices || []);
    } catch (e) { setError(e.response?.data?.detail || e.message || "Gagal memuat perangkat RFID"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, [whId]); // eslint-disable-line

  const flash = (m) => { setMsg(m); setTimeout(() => setMsg(""), 2500); };
  const issueKey = async (d) => {
    setBusy(true); setError(null);
    try {
      if (d.has_api_key && !(await askConfirm({
        title: `Rotasi API key ${d.code}?`, danger: true,
        message: "Key lama langsung tidak berlaku. Middleware harus diperbarui dengan key baru.",
      }))) return;
      const r = await axios.post(`${API}/rfid/devices/${d.id}/api-key`, null, { params: { regenerate: !!d.has_api_key } });
      setRevealed({ id: d.id, key: r.data.api_key });
      flash(d.has_api_key ? "API key dirotasi." : "API key diterbitkan.");
      await load();
    } catch (e) { setError(e.response?.data?.detail || "Gagal menerbitkan API key"); } finally { setBusy(false); }
  };
  // UAT 24 Okt (audit UI tahap 2) — dulu langsung POST sekali klik. Server membuat untuk SEMUA gudang (bukan hanya
  // gudang terpilih): 2 gerbang + 1 pembaca tetap per gudang yang belum punya (rfid_service.seed_default_devices).
  const seedDefaults = async () => {
    const n = (warehouses || []).length;
    if (!(await askConfirm({
      title: `Buat perangkat bawaan untuk ${n} gudang?`,
      message: `Untuk setiap gudang dibuat Gerbang Masuk, Gerbang Keluar, dan 1 Pembaca tetap bila kodenya belum ada (paling banyak ${n * 3} perangkat). Perangkat yang sudah ada tidak diubah.`,
      confirmLabel: "Buat perangkat",
    }))) return;
    setBusy(true); setError(null);
    try { const r = await axios.post(`${API}/rfid/devices/seed-defaults`); flash(`${r.data.created} perangkat bawaan dibuat.`); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal membuat perangkat bawaan"); } finally { setBusy(false); }
  };
  const toggleStatus = async (d) => {
    setBusy(true); setError(null);
    try { await axios.patch(`${API}/rfid/devices/${d.id}`, { status: d.status === "online" ? "offline" : "online" }); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal mengubah status perangkat"); } finally { setBusy(false); }
  };
  const toggleEnabled = async (d) => {
    if (d.enabled && !(await askConfirm({
      title: `Nonaktifkan ${d.code}?`, danger: true,
      message: "Perangkat nonaktif ditolak sistem (sinyal, kiriman bacaan, dan tugas cetak) sampai diaktifkan lagi.",
    }))) return;
    setBusy(true); setError(null);
    try { await axios.patch(`${API}/rfid/devices/${d.id}`, { enabled: !d.enabled }); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal mengubah aktivasi perangkat"); } finally { setBusy(false); }
  };
  const remove = async (d) => {
    if (!(await askConfirm({
      title: `Hapus perangkat ${d.code}?`, danger: true, confirmLabel: "Hapus",
      message: `${d.name || d.code} di ${d.warehouse_name || "gudang ini"} dihapus dari daftar; kunci aksesnya ikut tidak berlaku.`,
    }))) return;
    setBusy(true); setError(null);
    try { await axios.delete(`${API}/rfid/devices/${d.id}`); flash("Perangkat dihapus."); await load(); }
    catch (e) { setError(e.response?.data?.detail || "Gagal menghapus perangkat"); } finally { setBusy(false); }
  };
  const formValid = !!(form.name.trim() && form.warehouse_id);
  const submit = async () => {
    if (!formValid) { setFormErr("Nama & gudang wajib diisi"); return; }
    setBusy(true); setFormErr("");
    try {
      await axios.post(`${API}/rfid/devices`, { ...form, direction: form.type === "gate" ? form.direction : undefined });
      flash("Perangkat dibuat."); setShowForm(false);
      setForm(EMPTY_FORM);
      await load();
    } catch (e) { setFormErr(e.response?.data?.detail || "Gagal membuat perangkat"); } finally { setBusy(false); }
  };
  const closeForm = () => { setShowForm(false); setFormErr(""); };

  const online = devices.filter((d) => d.status === "online").length;
  const gates = devices.filter((d) => d.type === "gate").length;
  const readers = devices.filter((d) => d.type !== "gate").length;
  const whFormOpts = warehouses.map((w) => ({ value: w.id, label: w.name }));
  const headActions = (
    <>
      <KNSelect data-testid="rfid-dev-wh" value={whId} onValueChange={setWhId} options={whOpts}
        className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Gudang" />
      <button data-testid="rfid-dev-refresh" onClick={load} className="secondary-button">
        <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Muat ulang
      </button>
    </>
  );

  return (
    <div data-testid="rfid-devices-view" className="space-y-4">
      {embedded ? (
        <div className="flex flex-wrap items-center justify-between gap-2" data-testid="rfid-devices-head">
          <p className="text-[11.5px] text-[#6B6B73]">Perangkat RFID per gudang. Nyalakan/matikan, tambah gerbang &amp; pembaca.</p>
          <div className="flex flex-wrap items-center gap-2">{headActions}</div>
        </div>
      ) : (
        <PageHeader icon={Wifi} testId="rfid-devices-head" title="Perangkat (Pembaca / Gerbang)"
          subtitle="Perangkat RFID per gudang. Nyalakan/matikan, tambah gerbang & pembaca." actions={headActions} />
      )}

      {error && <ErrorNotice message={error} onRetry={load} />}
      {msg && <div className="rounded-lg bg-[#E7F7EC] text-[#1B7E3B] text-[12px] font-semibold px-3 py-2">{msg}</div>}
      {!isAdmin && <div className="rounded-lg bg-[#FFF6E5] text-[#8A5A00] text-[11px] px-3 py-2">Mode baca-saja. Perubahan perangkat memerlukan peran admin.</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat icon={Cpu} label="Total Perangkat" value={devices.length} color="#0058CC" loading={loading} />
        <Stat icon={Power} label="Menyala" value={online} color="#34C759" loading={loading} testId="rfid-dev-online" />
        <Stat icon={RadioTower} label="Gerbang" value={gates} color="#5856D6" loading={loading} />
        <Stat icon={Router} label="Pembaca" value={readers} color="#FF9500" loading={loading} />
      </div>

      {isAdmin && (
        <div className="flex flex-wrap gap-2">
          <button data-testid="rfid-seed-devices" disabled={busy} onClick={seedDefaults}
            className="secondary-button flex items-center gap-1">
            <RadioTower size={14} /> Buat Perangkat Bawaan (per gudang)
          </button>
          <button data-testid="rfid-add-device" onClick={() => { setFormErr(""); setShowForm(true); }}
            className="primary-button flex items-center gap-1">
            <Plus size={14} /> Tambah Perangkat
          </button>
        </div>
      )}

      <FormModal open={showForm && isAdmin} onClose={closeForm} testId="rfid-device-form" icon={Wifi} size="lg"
        title="Perangkat Baru" subtitle="Gerbang, pembaca tetap/genggam, atau printer RFID di satu gudang."
        onSubmit={submit} busy={busy} error={formErr} submitDisabled={!formValid} submitLabel="Simpan"
        submitTestId="rfid-form-submit" cancelTestId="rfid-form-cancel">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div><label className="text-[11px] text-[#6B6B73]">Kode <span className="text-[#8E8E93]">(opsional)</span></label>
              <input data-testid="rfid-form-code" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })}
                className="field mt-1 text-[12px]" placeholder="mis. GATE-JKT-OUT" /></div>
            <div><label className="text-[11px] text-[#6B6B73]">Nama *</label>
              <input data-testid="rfid-form-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="field mt-1 text-[12px]" placeholder="mis. Gerbang Keluar Jakarta" /></div>
            <div><label className="text-[11px] text-[#6B6B73]">Tipe *</label>
              <KNSelect data-testid="rfid-form-type" value={form.type} onValueChange={(v) => setForm({ ...form, type: v })} options={TYPE_OPTS} className="field mt-1 text-[12px]" /></div>
            {form.type === "gate" && (
              <div><label className="text-[11px] text-[#6B6B73]">Arah *</label>
                <KNSelect data-testid="rfid-form-dir" value={form.direction} onValueChange={(v) => setForm({ ...form, direction: v })} options={DIR_OPTS} className="field mt-1 text-[12px]" /></div>
            )}
            <div><label className="text-[11px] text-[#6B6B73]">Gudang *</label>
              <KNSelect data-testid="rfid-form-wh" value={form.warehouse_id} onValueChange={(v) => setForm({ ...form, warehouse_id: v })} options={whFormOpts} className="field mt-1 text-[12px]" placeholder="Pilih gudang" /></div>
            <div><label className="text-[11px] text-[#6B6B73]">Lokasi <span className="text-[#8E8E93]">(opsional, dari master zona/bin gudang)</span></label>
              <KNSelect data-testid="rfid-form-loc" value={form.location} onValueChange={(v) => setForm({ ...form, location: v })}
                options={locOpts} searchable disabled={!form.warehouse_id} className="field mt-1 text-[12px]"
                placeholder={form.warehouse_id ? "Pilih zona / bin" : "Pilih gudang dahulu"} /></div>
          </div>
          {/* UAT 24 Okt (audit UI tahap 2) — Simpan nonaktif sampai isian wajib (Nama, Gudang) lengkap. */}
      </FormModal>

      <SectionCard title="Daftar Perangkat">
        {loading ? <div className="h-16 bg-[#F5F5F7] rounded animate-pulse" />
          : devices.length === 0 ? <EmptyBox icon={Wifi} text="Belum ada perangkat. Klik 'Buat Perangkat Bawaan' untuk mulai." />
            : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
                {devices.map((d) => (
                  <div key={d.id} data-testid={`rfid-device-${d.id}`} className="rounded-lg border border-[#EFF0F2] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] font-mono font-semibold">{d.code}</span>
                      <span className="flex items-center gap-1">
                        {!d.enabled && <Pill color="red" testId={`rfid-device-disabled-${d.id}`}>nonaktif</Pill>}
                        <Pill color={d.status === "online" ? "green" : "gray"} testId={`rfid-device-status-${d.id}`}>{d.status === "online" ? "menyala" : d.status === "offline" ? "mati" : d.status}</Pill>
                      </span>
                    </div>
                    <p className="text-[12px] font-semibold mt-1">{d.name}</p>
                    <p className="text-[11px] text-[#6B6B73]">{TYPE_LABEL[d.type] || d.type}{d.type === "gate" ? ` · ${d.direction === "in" ? "masuk" : d.direction === "out" ? "keluar" : d.direction}` : ""} · {d.warehouse_name || "—"}</p>
                    <p className="text-[10px] text-[#8E8E93]">{d.location || "—"} · sinyal terakhir {fmtTime(d.last_heartbeat)}</p>
                    {isAdmin && (
                      <div className="flex gap-2 mt-2">
                        <button data-testid={`rfid-toggle-${d.id}`} disabled={busy || !d.enabled} onClick={() => toggleStatus(d)}
                          title="Matikan/nyalakan sementara (mis. perawatan). Perangkat tetap terdaftar dan boleh dinyalakan lagi kapan saja."
                          className="flex-1 flex items-center justify-center gap-1 rounded-lg border border-[#EFF0F2] px-2 py-1 text-[11px] font-semibold hover:bg-[#F5F5F7] disabled:opacity-40">
                          <Power size={12} /> {d.status === "online" ? "Matikan" : "Nyalakan"}
                        </button>
                        <button data-testid={`rfid-apikey-${d.id}`} disabled={busy} onClick={() => issueKey(d)}
                          title="Kunci akses untuk aplikasi penghubung pembaca RFID"
                          className="rounded-lg border border-[#EFF0F2] px-2 py-1 text-[11px] font-semibold text-[#6B219A] hover:bg-[#F3E9FA] disabled:opacity-40">
                          {d.has_api_key ? "Ganti Kunci" : "Buat Kunci"}
                        </button>
                        <button data-testid={`rfid-enable-toggle-${d.id}`} disabled={busy} onClick={() => toggleEnabled(d)}
                          title={d.enabled ? "Blokir perangkat: semua kiriman bacaan & tugas cetaknya ditolak sampai diaktifkan lagi." : "Cabut blokir perangkat."}
                          className={`rounded-lg border border-[#EFF0F2] px-2 py-1 text-[11px] font-semibold disabled:opacity-40 ${d.enabled ? "text-[#C0341D] hover:bg-[#FBE9E7]" : "text-[#1B7E3B] hover:bg-[#E7F7EC]"}`}>
                          {d.enabled ? "Nonaktifkan" : "Aktifkan"}
                        </button>
                        <button data-testid={`rfid-del-device-${d.id}`} disabled={busy} onClick={() => remove(d)} title="Hapus perangkat" aria-label="Hapus perangkat"
                          className="rounded-lg border border-[#EFF0F2] px-2 py-1 text-[#C0341D] hover:bg-[#FBE9E7] disabled:opacity-40"><Trash2 size={12} /></button>
                      </div>
                    )}
                    {d.has_api_key && (
                      <p data-testid={`rfid-apikey-hint-${d.id}`} className="mt-1 text-[10px] text-[#6B6B73]">
                        Kunci aktif ••••{d.api_key_hint || "????"}
                        {d.key_rotation_required && <span data-testid={`rfid-apikey-rotate-warn-${d.id}`} className="ml-1 font-semibold text-[#C0341D]">· wajib diganti (kunci lama pernah terlihat)</span>}
                      </p>
                    )}
                    {revealed?.id === d.id && isAdmin && (
                      <div data-testid={`rfid-apikey-once-${d.id}`} className="mt-1 rounded bg-[#FFF6E5] px-1.5 py-1">
                        <p className="text-[10px] font-semibold text-[#8A5A00]">Salin sekarang — key tidak akan ditampilkan lagi.</p>
                        <p data-testid={`rfid-apikey-val-${d.id}`} className="break-all font-mono text-[9.5px] text-[#3C3C43]">X-Device-Key: {revealed.key}</p>
                        <div className="mt-1 flex gap-2">
                          <button data-testid={`rfid-apikey-copy-${d.id}`} onClick={() => { navigator.clipboard?.writeText(revealed.key); flash("Key disalin."); }}
                            className="rounded border border-[#EFF0F2] bg-white px-2 py-0.5 text-[10px] font-semibold">Salin</button>
                          <button data-testid={`rfid-apikey-dismiss-${d.id}`} onClick={() => setRevealed(null)}
                            className="rounded border border-[#EFF0F2] bg-white px-2 py-0.5 text-[10px] font-semibold">Sudah disimpan</button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
      </SectionCard>
    </div>
  );
}
