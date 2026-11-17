import { useEffect, useMemo, useRef, useState } from "react";
import { can } from "../../config/roles";
import { MapPin, Layers, Boxes, RefreshCw, PackageCheck, AlertOctagon } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import PageTabs from "../../components/PageTabs";
import { ListToolbar, MetricRow, PageHeader } from "../../components/ListPageParts";
import EmptyState from "../../components/EmptyState";
import ErrorNotice from "../../components/ErrorNotice";
import axios, { API } from "../../services/apiClient";
import { apiErrorText } from "../../utils/apiError";
import PutawayOrdersPanel from "./PutawayOrdersPanel";
import PendingCutsPanel from "./PendingCutsPanel";
import { useLocationScope, LocationScopeBadge } from "./LocationScopeBadge";
import StructureEditor from "./location/StructureEditor";
import BinOccupancyGrid from "./location/BinOccupancyGrid";
import PutawayRow from "./location/PutawayRow";
import LazyMount from "./location/LazyMount";   // FIX-5 (UI-46) — baris antrean dirender saat mendekati layar
import OrphanPanel from "./location/OrphanPanel";
import StockTreePanel from "./location/StockTreePanel";
import { askReason } from "../../services/confirmService";
import { normalizeZones, fmtUnits, TERMS } from "./location/locUtils";
import { formatQty } from "../../utils/formatters";
import ExportMenu from "../../components/ExportMenu";   // FIX-4 — tombol baku Unduh (Excel/CSV, Pusat Export)
import "./opsList.css";   // pola UI M29 — tabel antrean penempatan

const isActiveWh = (w) => (w.status || "active") === "active" && w.active !== false;

export default function LocationPutawayView({ currentUser, selectedEntity }) {
  const [tab, setTab] = useState("putaway");
  const locScope = useLocationScope();
  const [warehouses, setWarehouses] = useState([]);
  const [whId, setWhId] = useState("");
  const [loc, setLoc] = useState(null);
  const [zones, setZones] = useState([]);
  const [queue, setQueue] = useState([]);
  // FIX-2 (B1b UI-46) — antrean berhalaman dengan jumlah sungguhan; dulu potong 500 diam-diam.
  const [queueMeta, setQueueMeta] = useState({ total: 0, total_building: 0, skip: 0, limit: 100, truncated: false });
  const [queueSkip, setQueueSkip] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState("");
  const [owners, setOwners] = useState([]);
  useEffect(() => {
    axios.get(`${API}/entities`).then((r) => setOwners((Array.isArray(r.data) ? r.data : r.data?.items || [])
      .map((e) => ({ value: e.id, label: e.short_name || e.legal_name || e.name || "PT tanpa nama" })))).catch(() => setOwners([]));
  }, []);
  const isSup = can(currentUser?.permissions, "wms", "approve");   // PR-T7 — = placement_rules.is_supervisor (izin wms.approve sejak PR-T2)

  useEffect(() => {
    if (locScope === null) return;
    axios.get(`${API}/warehouses`).then((r) => {
      const ids = locScope?.restricted ? locScope.warehouse_ids || [] : null;
      const rows = (r.data || []).filter((w) => !ids || ids.includes(w.id));
      setWarehouses(rows);
      // Gudang aktif lebih dulu — dulu gudang pertama (bisa nonaktif & kosong) terpilih,
      // sehingga KPI "0 roll / semua sudah ditempatkan" menyesatkan.
      // FIX-1 (B1 UI-42) — bawaan = gudang di CAKUPAN LOKASI aktif (bilah cakupan), bukan gudang pertama daftar
      // ("Rancamalang · Gudang Knitting" untuk admin Jakarta).
      const inView = locScope?.view?.ids ? rows.filter((w) => locScope.view.ids.includes(w.id)) : [];
      const pool = inView.length ? inView : rows;
      if (pool.length && !whId) setWhId((pool.find(isActiveWh) || pool[0]).id);
      if (!rows.length) setLoading(false);
    }).catch((e) => setError(apiErrorText(e)));
  }, [locScope]); // eslint-disable-line

  // FIX-5 (B1b UI-46) — pindah halaman antrean hanya memuat ulang ANTREAN (dulu struktur & okupansi gudang ikut
  // dimuat ulang setiap "Berikutnya"); muat penuh tetap saat ganti gudang/PT, simpan struktur, atau "Muat ulang".
  const loadAll = async (queueOnly = false) => {
    if (!whId) return;
    setLoading(true); setError(null);
    try {
      const ent = selectedEntity && selectedEntity !== "all" ? selectedEntity : "all";
      const [l, qd] = await Promise.all([
        queueOnly ? Promise.resolve(null) : axios.get(`${API}/warehouses/${whId}/locations`, { params: { entity_id: ent } }),
        axios.get(`${API}/inventory/putaway/queue`, { params: { warehouse_id: whId, entity_id: ent, skip: queueSkip, limit: 100 } }),
      ]);
      if (l) {
        setLoc(l.data);
        setZones(normalizeZones(l.data.zones));
      }
      setQueue(qd.data.rolls || []);
      setQueueMeta({ total: qd.data.total ?? (qd.data.rolls || []).length, total_building: qd.data.total_building ?? 0,
        skip: qd.data.skip || 0, limit: qd.data.limit || 100, truncated: !!qd.data.truncated });
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data lokasi"));
    } finally { setLoading(false); }
  };
  useEffect(() => { setQueueSkip(0); }, [whId, selectedEntity]);
  useEffect(() => { loadAll(); }, [whId, selectedEntity]); // eslint-disable-line
  const firstSkip = useRef(true);
  useEffect(() => {   // halaman antrean berganti → hanya antrean
    if (firstSkip.current) { firstSkip.current = false; return; }
    loadAll(true);
  }, [queueSkip]); // eslint-disable-line

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
  const capTxt = loc?.capacity_rolls_total ? `${formatQty(loc.capacity_rolls_total)} roll` : "belum diatur";
  const kpi = (v) => (loading ? "…" : v);
  // Pola UI (pemilik 16 Nov — M29 "UI masih sangat buruk", foto 24): kartu angka = pintasan ke tab-nya (dulu lima kartu
  // tanpa aksi; Total Bin & Kapasitas kini satu kartu "Bin").
  const kpis = [
    { label: "Belum Ditempatkan", value: kpi(`${formatQty(loc?.unassigned?.rolls ?? 0)} roll`), icon: Layers, tab: "putaway",
      hint: [fmtUnits(loc?.unassigned?.by_unit), "gedung ini · semua PT"].filter(Boolean).join(" · "), testId: "lp-unassigned" },
    { label: "Terisi di Rak", value: kpi(`${formatQty(loc?.binned_rolls ?? 0)} roll`), icon: PackageCheck, tab: "stock",
      hint: fmtUnits(loc?.binned_by_unit), testId: "lp-kpi-occupied" },
    { label: "Bin", value: kpi(`${formatQty(loc?.bin_count ?? 0)} bin`), icon: Boxes, tab: "bins", testId: "lp-kpi-bins",
      hint: `kapasitas ${capTxt}${loc?.bins_without_capacity ? ` · ${formatQty(loc.bins_without_capacity)} tanpa kapasitas` : ""}` },
    { label: "Alamat Tak Terdaftar", value: kpi(`${formatQty(loc?.orphan?.rolls ?? 0)} roll`), icon: AlertOctagon, tab: "orphans",
      hint: fmtUnits(loc?.orphan?.by_unit), testId: "lp-kpi-orphan" },
  ];
  const noAssignment = locScope?.restricted && locScope?.no_assignment;
  return (
    <div data-testid="location-putaway-view" className="view-container">
      {/* Pola UI §2.A — kepala SATU baris: judul (?) · Gudang ▾ · muat ulang. Dulu: kepala + baris hierarki lokasi + lencana
          cakupan (lokasi sudah dipilih di bilah atas) + paragraf saran bin di atas antrean — kini di ?. */}
      <PageHeader icon={MapPin} title="Lokasi Gudang & Penempatan Rak" testId="lp-header"
        help={`Susunan alamat: ${[TERMS.site, TERMS.warehouse, TERMS.zone, TERMS.rack, TERMS.level, TERMS.bin].join(" › ")}`
          + `${w.name ? ` — gudang terpilih: ${w.site ? `${w.site} › ` : ""}${w.name}` : ""}. Klik kartu angka untuk membuka tab-nya. `
          + "Penempatan: saran bin hanya menampilkan bin yang lolos aturan & kapasitas; server tetap memeriksa ulang saat disimpan."}
        actions={(
          <>
            {noAssignment && <LocationScopeBadge scope={locScope} />}
            <KNSelect data-testid="lp-warehouse" aria-label="Gudang" value={whId} onValueChange={setWhId}
              searchable={warehouses.length > 9} placeholder="Gudang"
              options={warehouses.map((x) => ({ value: x.id, label: isActiveWh(x) ? x.name : `${x.name} (nonaktif)` }))}
              className="!h-auto !w-auto min-w-[200px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13" />
            <button type="button" data-testid="lp-refresh" onClick={() => loadAll()} className="icon-button"
              aria-label="Muat ulang" title="Muat ulang">
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            </button>
          </>
        )} />

      {error && <ErrorNotice message={error} onRetry={() => loadAll()} />}
      {msg && <div data-testid="lp-msg" className="notice-bar success !mb-0">{msg}</div>}

      <MetricRow testId="lp-kpis" items={kpis.map(({ tab: t, ...k }) => ({ ...k, active: tab === t, onClick: () => setTab(t) }))} />

      <PageTabs value={tab} onChange={setTab} testId="lp-tab" ariaLabel="Lokasi gudang" tabs={[
        { key: "putaway", label: `Penempatan Rak${queueMeta.total ? ` (${formatQty(queueMeta.total)})` : ""}` },
        { key: "structure", label: "Struktur Lokasi" },
        { key: "stock", label: "Stok per Alamat" },
        { key: "bins", label: "Okupansi Bin" },
        { key: "orphans", label: `Alamat Tak Terdaftar${loc?.orphan?.rolls ? ` (${formatQty(loc.orphan.rolls)})` : ""}` },
        { key: "pa", label: "Perintah Simpan ke Rak (Antar Gedung)" },
        { key: "cuts", label: "Antrean Potong" },
      ]} />

      {tab === "pa" ? <PutawayOrdersPanel whId={whId} selectedEntity={selectedEntity} />
        : tab === "cuts" ? <PendingCutsPanel whId={whId} />
        : tab === "stock" ? <StockTreePanel whId={whId} ownerOptions={owners} />
        : tab === "structure" ? <StructureEditor zones={zones} setZones={setZones} occByBin={occByBin} canEdit={isSup} saving={saving} onSave={() => saveStructure()} />
        : tab === "bins" ? <BinOccupancyGrid bins={loc?.bins} />
        : tab === "orphans" ? <OrphanPanel whId={whId} binOptions={binOptions} onChanged={() => loadAll()} />
        : (
          <div data-testid="lp-queue">
            {/* Bilah daftar (jumlah · Unduh) tepat di atas tabel antrean; dulu judul + paragraf + kalimat jumlah. */}
            <ListToolbar testId="lp-queue-toolbar" actions={(
              <ExportMenu dataset="inventory_rolls" label="antrean-penempatan-rak" testId="lp-queue-export"
                filters={[whId && ["warehouse_id", "eq", whId], ["bin_id", "empty"], ["length_remaining", "gt", 0],
                  ["status", "in", ["available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged"]]]} />
            )}>
              {!loading && queue.length > 0 && (
                <span data-testid="lp-queue-count" className="text-fs-12 text-kn-text-2">
                  Roll {formatQty(queueMeta.skip + 1)}–{formatQty(queueMeta.skip + queue.length)} dari <b className="text-kn-text">{formatQty(queueMeta.total)}</b> belum ditempatkan
                  {queueMeta.total_building > queueMeta.total && (
                    <span> · gedung ini (semua PT): {formatQty(queueMeta.total_building)} roll — roll PT lain tampil saat PT-nya dipilih</span>
                  )}
                </span>
              )}
            </ListToolbar>
            {loading ? <div className="h-16 animate-pulse rounded-xl bg-kn-neutral-soft" />
              : queue.length === 0 ? (
                <div className="kn-putaway-table">
                  <EmptyState compact kind={error ? "error" : "empty"} error={error} onRetry={() => loadAll()} what="antrean penempatan"
                    icon={PackageCheck} title={error ? undefined : "Semua roll sudah ditempatkan ke bin."} testId="lp-queue-empty" />
                </div>
              )
              : <>
                <div className="kn-putaway-table" data-testid="lp-queue-table">
                  <div className="kn-putaway-head" data-testid="lp-queue-head">
                    <span>Roll</span><span>Barang · cek</span><span>Bin tujuan</span><span className="text-right">Aksi</span>
                  </div>
                  {queue.map((r, i) => (
                    <LazyMount key={r.id} eager={i < 12} minHeight={56} testId={`lp-queue-lazy-${r.id}`}>
                      <PutawayRow roll={r} binOptions={binOptions} canOverride={isSup} onDone={() => loadAll()} />
                    </LazyMount>
                  ))}
                </div>
                {(queueMeta.skip > 0 || queueMeta.truncated) && (
                  <div className="mt-3 flex items-center justify-between gap-2" data-testid="lp-queue-pager">
                    <button type="button" className="secondary-button btn-sm" disabled={queueMeta.skip <= 0 || loading}
                      onClick={() => setQueueSkip(Math.max(0, queueMeta.skip - queueMeta.limit))}>Sebelumnya</button>
                    <span className="text-fs-12 text-kn-text-2">Halaman {formatQty(Math.floor(queueMeta.skip / queueMeta.limit) + 1)} dari {formatQty(Math.max(1, Math.ceil(queueMeta.total / queueMeta.limit)))}</span>
                    <button type="button" className="secondary-button btn-sm" disabled={!queueMeta.truncated || loading}
                      onClick={() => setQueueSkip(queueMeta.skip + queueMeta.limit)}>Berikutnya</button>
                  </div>
                )}
              </>}
          </div>
        )}
    </div>
  );
}
