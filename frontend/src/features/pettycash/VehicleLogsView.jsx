import { apiErrorText } from "../../utils/apiError";
import { useEffect, useState } from "react";
import axios, { API } from "../../services/apiClient";
import {
  Car, Plus, RefreshCw, Trash2, Pencil, Route, Fuel,
} from "lucide-react";
import { formatCurrency, formatQty, todayWib } from "../../utils/formatters";
import ErrorNotice from "../../components/ErrorNotice";
import ConfirmModal from "../../components/ConfirmModal";
import PageTabs from "../../components/PageTabs";
import ResponsiveTable from "../../components/ResponsiveTable";
import { MetricRow } from "../../components/ListPageParts";
import { fmtDate } from "./pettyCashShared";
import { can } from "../../config/roles";
import { LogFormModal, VehicleFormModal } from "./VehicleLogForms";

/**
 * VehicleLogsView — Aset & GA: Laporan Penggunaan & Biaya Kendaraan.
 * Tab: Log & Biaya · Master Kendaraan · Rekap per kendaraan.
 *
 * Fase 4 · R2 — dibuka juga dari aplikasi HP (Lainnya › Kendaraan) → layak 390 px:
 *  · L-03: form Log & Kendaraan (`.modal-card` buatan sendiri) → `FormModal` (diekstrak ke `VehicleLogForms.jsx`);
 *  · L-01: deret `tab-button` lepas → `PageTabs` (`veh-tab-*` tetap);
 *  · L-07/L-08: grid kolom lebar tetap (aksi di luar layar HP) → `ResponsiveTable` (kartu di HP); KPI → `MetricRow`
 *    baku (aksen ungu hilang, nol netral). Testid baris/aksi/kosong tetap.
 */
const TABS = [
  { key: "logs", label: "Log & Biaya" },
  { key: "vehicles", label: "Master Kendaraan" },
  { key: "recap", label: "Rekap" },
];
const emptyLog = () => ({
  vehicle_id: "", no_polisi: "", tanggal: todayWib(),
  km_awal: "", km_akhir: "", bbm: "", tol: "", parkir: "", lain_lain: "",
  tujuan: "", driver: "", pemakai: "", mengetahui: "",
});

export default function VehicleLogsView({ currentUser, selectedEntity = "all", entities = [] }) {
  const [tab, setTab] = useState("logs");
  const [logs, setLogs] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [summary, setSummary] = useState({ grand_total: 0, count: 0, per_vehicle: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const [logForm, setLogForm] = useState(null);   // null | {} (create/edit)
  const [vehForm, setVehForm] = useState(null);
  const [delTarget, setDelTarget] = useState(null); // {kind, item}
  const canCreate = can(currentUser?.permissions, "vehicle_log", "create");   // Sisir lanjutan gerbang peran (2026-10-21) — /vehicle-usage-logs, /vehicles
  const canManageVeh = can(currentUser?.permissions, "vehicle_log", "update");
  const canDelete = can(currentUser?.permissions, "vehicle_log", "delete");

  useEffect(() => { loadAll(); }, [selectedEntity]); // eslint-disable-line

  async function loadAll() {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const [l, v, s] = await Promise.all([
        axios.get(`${API}/vehicle-usage-logs`, { params }),
        axios.get(`${API}/vehicles`, { params }),
        axios.get(`${API}/vehicle-usage-logs/summary`, { params }).catch(() => ({ data: {} })),
      ]);
      setLogs(Array.isArray(l.data) ? l.data : []);
      setVehicles(Array.isArray(v.data) ? v.data : []);
      setSummary(s.data || { grand_total: 0, count: 0, per_vehicle: [] });
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data kendaraan."));
    } finally { setLoading(false); }
  }
  function flash(msg) { setToast(msg); setTimeout(() => setToast(""), 3500); }

  async function doDelete() {
    const { kind, item } = delTarget;
    try {
      if (kind === "log") await axios.delete(`${API}/vehicle-usage-logs/${item.id}`);
      else await axios.delete(`${API}/vehicles/${item.id}`);
      flash("Data dihapus.");
    } catch (e) { flash(apiErrorText(e, "Gagal menghapus.")); }
    finally { setDelTarget(null); loadAll(); }
  }

  const entityName = (id) => entities.find((e) => e.id === id)?.short_name || entities.find((e) => e.id === id)?.legal_name || id || "—";

  return (
    <div data-testid="vehicle-logs-view" className="grid gap-4">
      {toast && <div className="notice-bar success" data-testid="veh-toast"><span>{toast}</span><button type="button" aria-label="Tutup pesan" onClick={() => setToast("")}>×</button></div>}
      <ErrorNotice message={error} onRetry={loadAll} onDismiss={() => setError("")} testId="veh-error" />

      <section className="section-card">
        <div className="section-head flex-wrap gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <Car size={15} className="shrink-0 text-[#0058CC]" />
            <span className="kicker">Aset & GA</span>
            <h2 data-testid="veh-title">Penggunaan & Biaya Kendaraan</h2>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button type="button" data-testid="veh-refresh" className="icon-button" onClick={loadAll} aria-label="Muat ulang"><RefreshCw size={14} className={loading ? "animate-spin" : ""} /></button>
            {tab === "logs" && canCreate && <button type="button" data-testid="veh-log-create-btn" className="primary-button" onClick={() => setLogForm(emptyLog())}><Plus size={14} /> Catat Perjalanan</button>}
            {tab === "vehicles" && canManageVeh && <button type="button" data-testid="veh-create-btn" className="primary-button" onClick={() => setVehForm({ no_polisi: "", nama: "", jenis: "mobil", active: true })}><Plus size={14} /> Kendaraan Baru</button>}
          </div>
        </div>
        <div className="section-body space-y-3">
          <MetricRow testId="veh-metrics" items={[
            { label: "Total Kendaraan", value: vehicles.length, icon: Car, testId: "veh-metric-count" },
            { label: "Total Perjalanan", value: summary.count || 0, icon: Route, testId: "veh-metric-trips" },
            { label: "Total Jarak (km)", value: formatQty(summary.per_vehicle?.reduce((s, v) => s + (v.jarak || 0), 0)), icon: Route, testId: "veh-metric-km" },
            { label: "Total Biaya", value: formatCurrency(summary.grand_total), icon: Fuel, testId: "veh-metric-cost" },
          ]} />
          <PageTabs testId="veh-tabs" ariaLabel="Kendaraan" className="!mb-0" value={tab} onChange={setTab}
            tabs={TABS.map((t) => ({ ...t, testId: `veh-tab-${t.key}` }))} />
        </div>
      </section>

      {tab === "logs" && (
        <section className="section-card">
          <ResponsiveTable testId="veh-log" rows={logs} loading={loading}
            rowTestId={(r) => `veh-log-row-${r.id}`}
            empty={<><Car className="mx-auto mb-2 text-gray-300" size={28} /><p>Belum ada log. Klik <b>Catat Perjalanan</b>.</p></>}
            columns={[
              { key: "number", header: "Nomor", mobile: "title", render: (r) => <span className="text-[11px] font-bold text-[#0058CC]">{r.number}</span> },
              { key: "tanggal", header: "Tanggal", mobile: "badge", render: (r) => <span className="text-[10.5px] text-[#6B6B73]">{fmtDate(r.tanggal)}</span> },
              { key: "tujuan", header: "Tujuan / Kendaraan", mobile: "subtitle", render: (r) => (
                <div className="min-w-0"><p className="text-[12px] font-semibold truncate">{r.tujuan || "—"}</p><p className="text-[10.5px] text-[#9A9BA3] truncate">{r.no_polisi || "—"} · {r.driver || r.pemakai || "—"}</p></div>
              ) },
              { key: "jarak", header: "Jarak", align: "right", priority: 2, render: (r) => <span className="tabular-nums">{formatQty(r.jarak_tempuh)} km</span> },
              { key: "total", header: "Biaya", align: "right", priority: 1, render: (r) => <span className="tabular-nums font-semibold">{formatCurrency(r.total)}</span> },
            ]}
            actions={(canCreate || canDelete) ? (r) => (
              <div className="flex justify-end gap-1">
                {canCreate && <button type="button" data-testid={`veh-log-edit-${r.id}`} className="icon-button" onClick={() => setLogForm({ ...r, tanggal: (r.tanggal || "").slice(0, 10) })} aria-label="Ubah"><Pencil size={13} /></button>}
                {canDelete && <button type="button" data-testid={`veh-log-del-${r.id}`} className="icon-button text-red-400" onClick={() => setDelTarget({ kind: "log", item: r })} aria-label="Hapus"><Trash2 size={13} /></button>}
              </div>
            ) : undefined} />
        </section>
      )}

      {tab === "vehicles" && (
        <section className="section-card">
          <ResponsiveTable testId="veh" rows={vehicles} loading={loading}
            rowTestId={(v) => `veh-row-${v.id}`}
            empty={<><Car className="mx-auto mb-2 text-gray-300" size={28} /><p>Belum ada kendaraan.</p></>}
            columns={[
              { key: "no_polisi", header: "No. Polisi", mobile: "title", render: (v) => <span className="text-[12px] font-bold text-[#0058CC]">{v.no_polisi}</span> },
              { key: "active", header: "Status", mobile: "badge", render: (v) => <span className={`status-pill ${v.active ? "pill-success" : "pill-muted"}`}>{v.active ? "Aktif" : "Nonaktif"}</span> },
              { key: "nama", header: "Nama / Merk", mobile: "subtitle", render: (v) => v.nama || "—" },
              { key: "jenis", header: "Jenis", render: (v) => <span className="capitalize">{v.jenis}</span> },
            ]}
            actions={(canManageVeh || canDelete) ? (v) => (
              <div className="flex justify-end gap-1">
                {canManageVeh && <button type="button" data-testid={`veh-edit-${v.id}`} className="icon-button" onClick={() => setVehForm(v)} aria-label="Ubah"><Pencil size={13} /></button>}
                {canDelete && <button type="button" data-testid={`veh-del-${v.id}`} className="icon-button text-red-400" onClick={() => setDelTarget({ kind: "vehicle", item: v })} aria-label="Hapus"><Trash2 size={13} /></button>}
              </div>
            ) : undefined} />
        </section>
      )}

      {tab === "recap" && (
        <section className="section-card">
          <ResponsiveTable testId="veh-recap" rows={summary.per_vehicle || []} rowKey={(p, i) => `${p.no_polisi}-${i}`}
            rowTestId={(p, i) => `veh-recap-${i}`} empty="Belum ada rekap biaya."
            columns={[
              { key: "no_polisi", header: "Kendaraan", mobile: "title", render: (p) => <span className="font-semibold">{p.no_polisi}</span> },
              { key: "jarak", header: "Total Jarak", align: "right", render: (p) => <span className="tabular-nums">{formatQty(p.jarak)} km</span> },
              { key: "total", header: "Total Biaya", align: "right", render: (p) => <span className="tabular-nums font-semibold">{formatCurrency(p.total)}</span> },
              { key: "count", header: "Perjalanan", align: "right", render: (p) => <span className="tabular-nums">{p.count}</span> },
            ]}
            footer={(summary.per_vehicle || []).length > 0 ? (
              <div className="flex items-center justify-between gap-2 border-t border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2.5">
                <span className="text-[11px] font-bold uppercase text-[#6B6B73]">Grand Total</span>
                <span data-testid="veh-recap-grand" className="text-[13px] tabular-nums font-bold text-[#0058CC]">{formatCurrency(summary.grand_total)}</span>
              </div>
            ) : null} />
        </section>
      )}

      {logForm && <LogFormModal form={logForm} setForm={setLogForm} vehicles={vehicles} entities={entities} selectedEntity={selectedEntity} onClose={() => setLogForm(null)} onSaved={(msg) => { flash(msg); setLogForm(null); loadAll(); }} />}
      {vehForm && <VehicleFormModal form={vehForm} entities={entities} selectedEntity={selectedEntity} onClose={() => setVehForm(null)} onSaved={(msg) => { flash(msg); setVehForm(null); loadAll(); }} />}

      <ConfirmModal open={!!delTarget} title="Hapus Data" message={`Hapus ${delTarget?.kind === "log" ? "log perjalanan" : "kendaraan"} ini? Kendaraan yang sudah dipakai log akan dinonaktifkan.`} confirmLabel="Hapus" danger onConfirm={doDelete} onCancel={() => setDelTarget(null)} testId="veh-del-modal" />
    </div>
  );
}
