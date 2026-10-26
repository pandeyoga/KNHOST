import { useEffect, useMemo, useState } from "react";
import { roleIs } from "../../config/roles";
import { MapPin, Package, Layers, Boxes, RefreshCw, PackageCheck, AlertOctagon, ChevronRight } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import PageTabs from "../../components/PageTabs";
import { PageHeader } from "../../components/ListPageParts";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import PutawayOrdersPanel from "./PutawayOrdersPanel";
import PendingCutsPanel from "./PendingCutsPanel";
import { useLocationScope, LocationScopeBadge } from "./LocationScopeBadge";
import StructureEditor from "./location/StructureEditor";
import BinOccupancyGrid from "./location/BinOccupancyGrid";
import PutawayRow from "./location/PutawayRow";
import OrphanPanel from "./location/OrphanPanel";
import StockTreePanel from "./location/StockTreePanel";
import { askReason } from "../../services/confirmService";
import { normalizeZones, fmtUnits, TERMS } from "./location/locUtils";

const SUPERVISORS = ["warehouse_admin", "manager", "admin"];
const isActiveWh = (w) => (w.status || "active") === "active" && w.active !== false;

export default function LocationPutawayView({ currentUser, selectedEntity }) {
  const [tab, setTab] = useState("putaway");
  const locScope = useLocationScope();
  const [warehouses, setWarehouses] = useState([]);
  const [whId, setWhId] = useState("");
  const [loc, setLoc] = useState(null);
  const [zones, setZones] = useState([]);
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState("");
  const [owners, setOwners] = useState([]);
  useEffect(() => {
    axios.get(`${API}/entities`).then((r) => setOwners((Array.isArray(r.data) ? r.data : r.data?.items || [])
      .map((e) => ({ value: e.id, label: e.short_name || e.name || e.id })))).catch(() => setOwners([]));
  }, []);
  const isSup = roleIs(currentUser?.role, SUPERVISORS);   // FE-04 — sama dengan placement_rules.is_supervisor (kenal peran acuan)

  useEffect(() => {
    if (locScope === null) return;
    axios.get(`${API}/warehouses`).then((r) => {
      const ids = locScope?.restricted ? locScope.warehouse_ids || [] : null;
      const rows = (r.data || []).filter((w) => !ids || ids.includes(w.id));
      setWarehouses(rows);
      // Gudang aktif lebih dulu — dulu gudang pertama (bisa nonaktif & kosong) terpilih,
      // sehingga KPI "0 roll / semua sudah ditempatkan" menyesatkan.
      if (rows.length && !whId) setWhId((rows.find(isActiveWh) || rows[0]).id);
      if (!rows.length) setLoading(false);
    }).catch((e) => setError(apiErrorText(e)));
  }, [locScope]); // eslint-disable-line

  const loadAll = async () => {
    if (!whId) return;
    setLoading(true); setError(null);
    try {
      const ent = selectedEntity && selectedEntity !== "all" ? selectedEntity : "all";
      const [l, qd] = await Promise.all([
        axios.get(`${API}/warehouses/${whId}/locations`, { params: { entity_id: ent } }),
        axios.get(`${API}/inventory/putaway/queue`, { params: { warehouse_id: whId, entity_id: ent } }),
      ]);
      setLoc(l.data);
      setZones(normalizeZones(l.data.zones));
      setQueue(qd.data.rolls || []);
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data lokasi"));
    } finally { setLoading(false); }
  };
  useEffect(() => { loadAll(); }, [whId, selectedEntity]); // eslint-disable-line

  const occByBin = useMemo(() => Object.fromEntries((loc?.bins || []).map((b) => [b.bin_id, b])), [loc]);
  const binOptions = useMemo(() => (loc?.bins || []).map((b) => ({ value: b.bin_id, label: `${b.code} — ${b.path}` })), [loc]);

  const saveStructure = async (migrationReason = "") => {
    setSaving(true); setError(null); setMsg("");
    try {
      await axios.put(`${API}/warehouses/${whId}/structure`, { zones, migration_reason: migrationReason });
      setMsg(migrationReason ? "Struktur lokasi tersimpan — migrasi alamat tercatat." : "Struktur lokasi tersimpan.");
      await loadAll();
      setTimeout(() => setMsg(""), 2500);
    } catch (e) {
      const d = e?.response?.data?.detail;
      if (e?.response?.status === 409 && d?.code === "LOCATION_MIGRATION_REASON" && !migrationReason) {
        setSaving(false);
        const reason = await askReason({ title: "Alasan migrasi alamat", message: d.message, confirmLabel: "Simpan dengan migrasi" });
        if (reason) await saveStructure(reason);
        return;
      }
      setError(apiErrorText(e, "Gagal menyimpan struktur"));
    } finally { setSaving(false); }
  };

  const w = loc?.warehouse || {};
  const capTxt = loc?.capacity_rolls_total ? `${loc.capacity_rolls_total} roll` : "Belum diatur";
  return (
    <div data-testid="location-putaway-view" className="space-y-4">
      {/* Fase 4 · R3 (L-01/L-02) — kepala = PageHeader baku (dulu kicker "GUDANG" + h1 20 px buatan sendiri); tab = PageTabs
          (dulu TabBtn buatan sendiri; testid `lp-tab-*` tetap). Di HP bilah tab satu baris bergulir (aturan baku P1). */}
      <PageHeader icon={MapPin} title="Lokasi Gudang & Penempatan Rak" testId="lp-header"
        actions={(
          <>
            <KNSelect data-testid="lp-warehouse" value={whId} onValueChange={setWhId}
              options={warehouses.map((x) => ({ value: x.id, label: isActiveWh(x) ? x.name : `${x.name} (nonaktif)` }))}
              className="field !py-1 !px-2 text-[12px] w-auto" placeholder="Gudang" />
            <button type="button" data-testid="lp-refresh" onClick={loadAll} className="secondary-button">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} /> Muat ulang
            </button>
          </>
        )} />
      <div className="-mt-2">
        <p data-testid="lp-hierarchy" className="text-[12px] text-[#6B6B73] flex flex-wrap items-center gap-1">
          {[TERMS.site, TERMS.warehouse, TERMS.zone, TERMS.rack, TERMS.level, TERMS.bin].map((t, i) => (
            <span key={t} className="inline-flex items-center gap-1">{i > 0 && <ChevronRight size={11} />}{t}</span>))}
          {w.name && <span className="ml-2 font-semibold text-[#1C1C1E]">· {w.site ? `${w.site} › ` : ""}{w.name}</span>}
        </p>
        <div className="mt-1"><LocationScopeBadge scope={locScope} /></div>
      </div>

      {error && <ErrorNotice message={error} onRetry={loadAll} />}
      {msg && <div data-testid="lp-msg" className="rounded-lg bg-[#E7F7EC] text-[#1B7E3B] text-[12px] font-semibold px-3 py-2">{msg}</div>}

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <Stat icon={Boxes} label="Total Bin" value={loc?.bin_count ?? 0} sub={loc?.bins_without_capacity ? `${loc.bins_without_capacity} tanpa kapasitas` : ""} color="#0058CC" loading={loading} testId="lp-kpi-bins" />
        <Stat icon={Package} label="Kapasitas" value={capTxt} color="#5856D6" loading={loading} testId="lp-kpi-capacity" />
        <Stat icon={PackageCheck} label="Terisi di Rak" value={`${loc?.binned_rolls ?? 0} roll`} sub={fmtUnits(loc?.binned_by_unit)} color="#34C759" loading={loading} testId="lp-kpi-occupied" />
        <Stat icon={Layers} label="Belum Ditempatkan" value={`${loc?.unassigned?.rolls ?? 0} roll`} sub={fmtUnits(loc?.unassigned?.by_unit)} color="#FF9500" loading={loading} testId="lp-unassigned" />
        <Stat icon={AlertOctagon} label="Alamat Tak Terdaftar" value={`${loc?.orphan?.rolls ?? 0} roll`} sub={fmtUnits(loc?.orphan?.by_unit)} color="#C0341D" loading={loading} testId="lp-kpi-orphan" />
      </div>

      <PageTabs value={tab} onChange={setTab} testId="lp-tab" ariaLabel="Lokasi gudang" tabs={[
        { key: "putaway", label: `Penempatan Rak${queue.length ? ` (${queue.length})` : ""}` },
        { key: "structure", label: "Struktur Lokasi" },
        { key: "stock", label: "Stok per Alamat" },
        { key: "bins", label: "Okupansi Bin" },
        { key: "orphans", label: `Alamat Tak Terdaftar${loc?.orphan?.rolls ? ` (${loc.orphan.rolls})` : ""}` },
        { key: "pa", label: "Perintah Simpan ke Rak (Antar Gedung)" },
        { key: "cuts", label: "Antrean Potong" },
      ]} />

      {tab === "pa" ? <PutawayOrdersPanel whId={whId} selectedEntity={selectedEntity} />
        : tab === "cuts" ? <PendingCutsPanel whId={whId} />
        : tab === "stock" ? <StockTreePanel whId={whId} ownerOptions={owners} />
        : tab === "structure" ? <StructureEditor zones={zones} setZones={setZones} occByBin={occByBin} canEdit={isSup} saving={saving} onSave={() => saveStructure()} />
        : tab === "bins" ? <BinOccupancyGrid bins={loc?.bins} />
        : tab === "orphans" ? <OrphanPanel whId={whId} binOptions={binOptions} onChanged={loadAll} />
        : (
          <div className="section-card section-pad">
            <h3 className="text-[13px] font-bold mb-1">Antrean Penempatan Rak — roll belum ditempatkan</h3>
            <p className="text-[11.5px] text-[#6B6B73] mb-3">Saran bin hanya menampilkan bin yang lolos aturan & kapasitas; server tetap memeriksa ulang saat disimpan.</p>
            {loading ? <div className="h-16 bg-[#F5F5F7] rounded animate-pulse" />
              : queue.length === 0 ? <p data-testid="lp-queue-empty" className="py-8 text-center text-[12px] text-[#6B6B73]">Semua roll sudah ditempatkan ke bin.</p>
              : <div className="space-y-2">{queue.map((r) => <PutawayRow key={r.id} roll={r} binOptions={binOptions} canOverride={isSup} onDone={loadAll} />)}</div>}
          </div>
        )}
    </div>
  );
}

function Stat({ icon: Icon, label, value, sub, color, loading, testId }) {
  return (
    <div data-testid={testId} className="rounded-xl border border-[#EFF0F2] bg-white p-4 flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <div className="rounded-lg p-1.5" style={{ background: `${color}18` }}><Icon size={15} style={{ color }} /></div>
        <span className="text-[12px] font-semibold text-[#6B6B73]">{label}</span>
      </div>
      {loading ? <div className="h-6 bg-[#F5F5F7] rounded animate-pulse" />
        : <p className="text-[18px] font-bold text-[#1C1C1E] tabular-nums leading-tight">{value}</p>}
      {sub && <p className="text-[11px] text-[#6B6B73] truncate" title={sub}>{sub}</p>}
    </div>
  );
}
