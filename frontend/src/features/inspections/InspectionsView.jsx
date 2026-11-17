/**
 * InspectionsView — FASE I · **INSPEKSI & QC SEBAGAI DOKUMEN** (`<ENT>/INS-#####`).
 *
 * Lembar kerja pemilik ("Inspect PO", "Inspect Retur", "Inspect retur & replacement")
 * akhirnya punya dokumennya: siapa memeriksa, kapan, atas dasar sample yang mana, dan
 * keputusannya. Tiga peran memakai layar yang sama:
 *  - **Kepala gudang / manajer**: menugaskan petugas (SPK penerimaan PO sudah LAHIR
 *    OTOMATIS saat barang masuk antrean QC — tidak dibuat dari nol), lalu memutuskan.
 *  - **Petugas Bagian Inspect**: mengisi cacat per roll + hasil warna & handfeel
 *    dibanding sample yang di-ACC; grade muncul sendiri dari poin.
 *  - **Manajer**: melepas tahanan barang yang warnanya beda (keputusan pemilik #5).
 *
 * Kartu ringkasan SELALU dari agregat server (`stats`) — pelajaran FASE P5: lencana
 * yang dihitung dari isi halaman diam-diam menyusut begitu daftarnya berhalaman.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { can } from "../../config/roles";
import { ClipboardCheck, Lock, Plus, RefreshCw, ScanSearch, ShieldAlert, Shuffle, UserPlus } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DetailModal from "../../components/DetailModal";
import StatusBadge from "../../components/StatusBadge";   // FIX-8 — lencana status baku
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import LineFilter from "../../components/LineFilter";
import { ListToolbar, MetricRow, PageHeader, SearchInput } from "../../components/ListPageParts";   // pola UI 16 Nov
import PaginationBar from "../../components/PaginationBar";
import QtyDual from "../../components/QtyDual";
import ResponsiveTable from "../../components/ResponsiveTable";
import { usePagedList } from "../../hooks/usePagedList";
import useViewPreset from "../../hooks/useViewPreset";
import { qtyDualCsvColumns } from "../../utils/qtyDualCsv";
import { EmptyState } from "../finance/financeShared";
import InspectionDetailPanel from "./InspectionDetailPanel";
import InspectionFormModal from "./InspectionFormModal";
import RandomCheckModal from "./RandomCheckModal";
import {
  apiText, getInspection, INS_BOARD_ORDER, INS_KIND_LABEL, INS_KIND_SHORT,
  INS_STATUS_LABEL, inspectionsMeta, qcTasksWithoutDoc,
} from "./inspectionsApi";

// Kolom CSV: dua satuan memakai `qtyDualCsvColumns` (FASE U / INV-QTY-01) supaya
// kolom Roll di berkas unduhan TIDAK pernah dihitung ulang di layar — angka yang
// dihitung dua kali adalah angka yang akan menyimpang.
const CSV_COLUMNS = [
  { key: "number", header: "Nomor" },
  { header: "Jenis", get: (r) => INS_KIND_LABEL[r.kind] || r.kind || "" },
  { key: "ref_doc_number", header: "Dokumen sumber" },
  { header: "Supplier / Pelanggan", get: (r) => r.supplier_name || r.customer_name || "" },
  { key: "assigned_name", header: "Petugas inspect" },
  { key: "spk_date", header: "Tanggal SPK" },
  { header: "Status", get: (r) => INS_STATUS_LABEL[r.status] || r.status || "" },
  { key: "baseline_sample_number", header: "Acuan sample" },
].concat(
  qtyDualCsvColumns({ itemsOf: (r) => r.lines || [], rollHeader: "Roll",
                      measureHeader: "Jumlah" }),
).concat([
  { header: "Poin cacat", type: "number", get: (r) => (r.summary || {}).points_total },
  { header: "Baris ditahan", type: "int", get: (r) => (r.summary || {}).hold },
  { key: "decision_label", header: "Keputusan" },
]);

// Dropdown bilah daftar — sama dengan pilot Retur (`SalesReturns.jsx`).
const SELECT_CLASS = "!h-auto !w-auto rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13";

// Kolom daftar SPK (satu definisi → tabel di desktop, kartu di HP; fase 3 · P5 L-04).
const INS_COLUMNS = (openDetail) => [
  { key: "number", header: "Nomor", mobile: "title",
    render: (r) => {
      const s = r.summary || {};
      return (
        <span className="font-semibold text-kn-text">
          {/* UAT 24 Okt (audit UI tahap 2) — nomor SPK sendiri membuka rincian. */}
          <button type="button" data-testid={`ins-open-${r.id}`} className="link-button !p-0 font-semibold"
            onClick={(e) => { e.stopPropagation(); openDetail(r.id); }}>{r.number}</button>
          {s.hold ? (
            <StatusBadge status="hold" tone="danger" icon="lock" className="ml-1" testId={`ins-hold-badge-${r.id}`}>{s.hold} ditahan</StatusBadge>
          ) : null}
        </span>
      );
    } },
  { key: "status", header: "Status", mobile: "badge",
    render: (r) => {
      const s = r.summary || {};
      return (
        <span>
          <StatusBadge status={r.status} domain="inspection" testId={`ins-status-${r.id}`} />
          {r.decision_label ? <span className="block text-fs-12 text-kn-text-2">{r.decision_label}</span> : null}
          {/* UAT 24 Okt (audit UI tahap 2) — roll yang GAGAL 4-point/random check tetap ditahan walau SPK ditutup. */}
          {r.status === "done" && s.hold ? (
            <span data-testid={`ins-done-hold-${r.id}`} className="block text-fs-12 font-semibold text-kn-danger-text">
              {s.hold} roll masih ditahan — lepas/tolak di rincian SPK
            </span>
          ) : null}
        </span>
      );
    } },
  { key: "kind", header: "Jenis", mobile: "subtitle", render: (r) => INS_KIND_SHORT[r.kind] || r.kind },
  { key: "ref", header: "Dokumen sumber", priority: 1,
    render: (r) => (
      <span className="text-kn-neutral">
        {r.ref_doc_number || "—"}
        <span className="block text-fs-12 text-kn-text-2">{r.supplier_name || r.customer_name || ""}</span>
      </span>
    ) },
  { key: "assigned", header: "Petugas", priority: 2,
    render: (r) => r.assigned_name
      || (r.status === "draft" ? "Belum ditugaskan" : <span className="text-kn-text-2">tidak tercatat</span>) },
  { key: "qty", header: "Barang", align: "right", priority: 3,
    render: (r) => {
      const s = r.summary || {};
      return <QtyDual rolls={s.rolls} measure={s.measure} unit={s.unit} testId={`ins-qty-${r.id}`} compact />;
    } },
  { key: "points", header: "Poin", align: "right", priority: 4,
    render: (r) => ((r.summary || {}).points_total ? r.summary.points_total : "—") },
];

export default function InspectionsView({ currentUser, selectedEntity = "all", focusDoc, onClearFocus }) {
  const [meta, setMeta] = useState({
    kinds: [], statuses: [], decisions: [], color_results: [], handfeel_results: [],
    officers: [], policy: {}, role: "", can_release_hold: false,
  });
  const [kindFilter, setKindFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [holdOnly, setHoldOnly] = useState(false);
  const [line, setLine] = useState("");
  const [search, setSearch] = useState("");
  const [detail, setDetail] = useState(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showRandom, setShowRandom] = useState(false);
  const [orphanTasks, setOrphanTasks] = useState([]);
  const [error, setError] = useState("");

  // Fase 3 · P5 — D-28: papan "Barang ditahan QC" (Beranda manajer, Operasi Gudang) kini TAUTAN ke sini dengan
  // preset `{ hold: true }` → saringan "Hanya yang DITAHAN"; keputusan lepas/tolak hanya di rincian SPK.
  useViewPreset("inspections", (p) => { if (p.hold !== undefined) setHoldOnly(!!p.hold); });

  const role = meta.role || currentUser?.role || "";
  const canCreate = can(currentUser?.permissions, "inspection", "create");   // FE-04 — izin efektif

  const params = useMemo(() => {
    const p = {};
    if (kindFilter) p.kind = kindFilter;
    if (statusFilter) p.status = statusFilter;
    if (holdOnly) p.hold_only = true;
    if (line) p.line = line;
    if (selectedEntity && selectedEntity !== "all") p.entity_id = selectedEntity;
    return p;
  }, [kindFilter, statusFilter, holdOnly, line, selectedEntity]);

  const paged = usePagedList("/inspections", { pageSize: 25, params, search });
  const [stats, setStats] = useState({});

  useEffect(() => {
    inspectionsMeta(selectedEntity)
      .then(setMeta)
      .catch((e) => setError(apiText(e, "Gagal memuat pilihan layar inspeksi.")));
  }, [selectedEntity]);

  const loadStats = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/inspections`, {
        params: { ...params, ...(search ? { q: search } : {}), page: 1, page_size: 1 } });
      setStats(r.data?.stats || {});
    } catch (e) { /* bilah galat daftar sudah bicara — jangan dobel */ }
  }, [params, search]);

  useEffect(() => { loadStats(); }, [loadStats]);

  const loadOrphans = useCallback(() => {
    qcTasksWithoutDoc().then(setOrphanTasks).catch(() => setOrphanTasks([]));
  }, []);
  useEffect(() => { loadOrphans(); }, [loadOrphans]);

  // Deep-link dari Meja MD / Meja Admin Gudang: saring ke nomor SPK + buka detailnya.
  useEffect(() => {
    if (focusDoc?.focus_type !== "inspection" || !focusDoc.focus_id) return;
    // Fase 3 · P5 — dulu nomor dikutip (`"KSC/INS-…"`) lalu dikirim apa adanya sebagai regex server → daftar di
    // belakang rincian selalu "Tidak ada SPK yang cocok". Nomor polos = cocok dengan dokumen itu.
    if (focusDoc.number) setSearch(focusDoc.number);
    getInspection(focusDoc.focus_id).then(setDetail).catch(() => {});
    onClearFocus?.();
  }, [focusDoc?.focus_id]); // eslint-disable-line

  const openDetail = useCallback(async (id) => {
    try { setDetail(await getInspection(id)); }
    catch (e) { setError(apiText(e, "Gagal memuat rincian inspeksi.")); }
  }, []);

  const refreshAll = useCallback(() => {
    paged.refresh(); loadStats(); loadOrphans();
  }, [paged, loadStats, loadOrphans]);

  const kindOptions = [{ value: "", label: "Semua jenis" }].concat(
    (meta.all_kinds || meta.kinds || []).map((k) => ({ value: k.value, label: INS_KIND_SHORT[k.value] || k.label })));
  const statusOptions = [{ value: "", label: `Semua status (${stats.total ?? 0})` }].concat(
    INS_BOARD_ORDER.map((s) => ({ value: s, label: `${INS_STATUS_LABEL[s]} (${stats[s] ?? 0})` })));

  const policy = meta.policy || {};
  const activeFilters = [
    kindFilter && `jenis ${INS_KIND_SHORT[kindFilter] || kindFilter}`,
    statusFilter && `status ${INS_STATUS_LABEL[statusFilter] || statusFilter}`,
    holdOnly && "hanya yang DITAHAN",
    line && "lini produk",
    search && `cari “${search}”`,
  ].filter(Boolean);
  // Kartu angka = saringan cepat (pola UI §1.5): klik → daftar tersaring, klik lagi → semua. "Ditolak" tidak dipajang
  // lagi — daftar belum bisa disaring per keputusan, jadi angkanya tidak bisa ditindak dari sini.
  const toggleStatus = (st) => setStatusFilter(statusFilter === st ? "" : st);
  const kpis = [
    { label: "Total SPK", value: stats.total ?? 0, icon: ClipboardCheck, testId: "ins-kpi-total",
      onClick: () => { setStatusFilter(""); setHoldOnly(false); } },
    { label: "Belum ditugaskan", value: stats.draft ?? 0, icon: UserPlus, testId: "ins-kpi-draft",
      active: statusFilter === "draft", onClick: () => toggleStatus("draft") },
    { label: "Sedang diperiksa", value: stats.in_progress ?? 0, icon: ScanSearch, testId: "ins-kpi-progress",
      active: statusFilter === "in_progress", onClick: () => toggleStatus("in_progress") },
    { label: "Barang DITAHAN", value: stats.hold ?? 0, icon: Lock, testId: "ins-kpi-hold",
      active: holdOnly, onClick: () => setHoldOnly((v) => !v) },
  ];

  return (
    <div data-testid="inspections-view" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {error && (
        <ErrorNotice message={error} onRetry={refreshAll} onDismiss={() => setError("")}
          testId="ins-error" />
      )}
      {paged.error && !error && (
        <ErrorNotice message={paged.error} onRetry={paged.refresh} testId="ins-list-error" />
      )}

      {/* Pola UI (pemilik 16 Nov — M24, foto 19): kepala SATU baris + ? (kebijakan berlaku dibuka di ?, bukan paragraf
          permanen); kartu angka = saringan cepat; SATU bilah daftar cari · lini · status ▾ · jenis ▾ · jumlah ·
          aksi. Dulu: kartu kepala berkicker, 5 KPI tanpa aksi, paragraf kebijakan, 9 chip jenis + 7 chip status. */}
      <PageHeader icon={ClipboardCheck} title="SPK Inspeksi & QC" testId="ins-header"
        help={(
          <span data-testid="ins-policy-note">
            Kebijakan berlaku: warna beda dari sample &rarr; <strong>{policy.color_mismatch_label || "—"}</strong> ·
            handfeel beda &rarr; <strong>{policy.handfeel_mismatch_label || "—"}</strong>. Warna &amp; handfeel penerimaan
            PO/hasil makloon diperiksa <strong>MD Quality</strong> (yang melepas/menolak tahanan); cacat 4-point &amp; grade
            diisi <strong>QC</strong>. Manajer tetap bisa melepas tahanan sebagai cadangan, dengan alasan tertulis. SPK
            penerimaan PO lahir otomatis saat barang masuk antrean QC.
          </span>
        )} />

      {/* Kartu ringkasan — dari agregat SERVER (bukan dari isi halaman). */}
      <MetricRow testId="ins-kpis" items={kpis} />

      {/* Jaring pengaman: tugas QC tanpa SPK (biasanya kosong) */}
      {orphanTasks.length > 0 && (
        <div data-testid="ins-orphan-tasks" className="notice-bar warning !mb-0 items-start">
          <ShieldAlert size={15} className="mt-0.5 shrink-0" />
          <div className="min-w-0">
            <p className="text-fs-12 font-bold">
              {orphanTasks.length} tugas QC belum punya SPK Inspeksi — terbitkan lewat <strong>Buat SPK Inspeksi</strong>
              {" "}(jenis “Penerimaan PO”); barang ini masuk sebelum SPK lahir otomatis.
            </p>
            <ul className="mt-1 grid gap-0.5">
              {orphanTasks.slice(0, 5).map((t) => (
                <li key={t.id} data-testid={`ins-orphan-${t.id}`} className="text-fs-12 text-kn-neutral">
                  {t.po_number || "(tanpa PO)"} · {t.product_name || "—"} ·{" "}
                  <QtyDual rolls={t.qty_rolls} measure={t.quantity} unit={t.unit}
                    testId={`ins-orphan-qty-${t.id}`} compact />
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* Bilah daftar — Fase 3 · P5 chip jenis & status (FilterChips) → dropdown (pola UI §1.2, M24). "Hanya yang
          DITAHAN" (preset papan "Barang ditahan QC", D-28) = kartu angka Barang DITAHAN. */}
      <ListToolbar testId="ins-filters" count={`${paged.total ?? 0} SPK`}
        actions={(
          <>
            <button type="button" data-testid="ins-refresh" className="icon-button" onClick={refreshAll}
              aria-label="Muat ulang" title="Muat ulang"><RefreshCw size={14} /></button>
            {meta.can_random_check && (
              <button data-testid="ins-random-check-button" className="secondary-button"
                onClick={() => setShowRandom(true)}>
                <Shuffle size={14} /> Random check stok
              </button>
            )}
            {canCreate && (
              <button data-testid="ins-create-button" className="primary-button"
                onClick={() => setShowCreate(true)}>
                <Plus size={14} /> Buat SPK Inspeksi
              </button>
            )}
          </>
        )}>
        <SearchInput testId="ins-search" placeholder="Cari nomor / dokumen sumber / petugas…" value={search}
          onChange={setSearch} className="min-w-[220px] flex-1 sm:max-w-[320px]" />
        <LineFilter value={line} onChange={setLine} storageKey="inspections"
          allowed={currentUser?.allowed_line_codes} testId="ins-line-filter" />
        <KNSelect data-testid="ins-status-filter" aria-label="Status SPK" className={`${SELECT_CLASS} min-w-[190px]`}
          searchable={false} value={statusFilter} onValueChange={(v) => setStatusFilter(v || "")} options={statusOptions} />
        <KNSelect data-testid="ins-kind-filter" aria-label="Jenis inspeksi" className={`${SELECT_CLASS} min-w-[170px]`}
          searchable={false} value={kindFilter} onValueChange={(v) => setKindFilter(v || "")} options={kindOptions} />
      </ListToolbar>

      {paged.loading ? (
        <div data-testid="ins-loading" className="section-card section-pad grid gap-2">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-9 animate-pulse rounded-md bg-kn-neutral-soft" />)}
        </div>
      ) : (paged.items || []).length === 0 ? (
        <div className="section-card section-pad">
          {/* UAT 24 Okt (audit UI tahap 2) — dulu "Belum ada SPK inspeksi" walau penyebabnya penyaring (mis. lini). */}
          <EmptyState icon={ClipboardCheck}
            title={activeFilters.length ? "Tidak ada SPK yang cocok dengan penyaring" : "Belum ada SPK inspeksi"}
            hint={holdOnly
              ? "Tidak ada barang yang sedang ditahan. Klik kartu “Barang DITAHAN” lagi untuk melihat seluruh SPK."
              : activeFilters.length
                ? `Penyaring aktif: ${activeFilters.join(" · ")}.${line ? " SPK lama yang belum bertanda lini produk tidak ikut tampil saat penyaring lini dipakai." : ""}`
                : "SPK penerimaan PO lahir otomatis saat barang masuk antrean QC. Untuk retur, hasil makloon, atau barang pengganti, terbitkan SPK-nya lewat tombol Buat SPK Inspeksi."}
            testId="ins-empty" />
        </div>
      ) : (
        <div className="section-card section-pad">
          {/* Fase 3 · P5 — L-04/L-07: tabel mentah → ResponsiveTable (kartu di HP 390 px, pager di luar wadah gulir).
              Layar ini dibuka dari aplikasi HP (tombol QC, notifikasi) — kelas B. */}
          <ResponsiveTable testId="ins-list" rows={paged.items || []} rowKey="id"
            rowTestId={(r) => `ins-row-${r.id}`} columns={INS_COLUMNS(openDetail)}
            onRowClick={(r) => openDetail(r.id)}
            actions={(r) => (
              <button data-testid={`ins-detail-${r.id}`} className="link-button" onClick={() => openDetail(r.id)}>Buka SPK</button>
            )}
            footer={(
              <div className="mt-2">
                <PaginationBar
                  page={paged.page} pageSize={paged.pageSize} total={paged.total}
                  hasMore={paged.hasMore} loading={paged.loading}
                  onPrev={paged.prev} onNext={paged.next} onPageSize={paged.setPageSize}
                  testId="ins-pager" label="SPK inspeksi"
                  exportConfig={{ columns: CSV_COLUMNS, rows: paged.items,
                    fetchAll: paged.fetchAll, filename: "inspeksi-qc" }}
                  exportSpec={{ dataset: "inspections", label: "spk-inspeksi", search,
                    filters: [kindFilter && ["kind", "eq", kindFilter], statusFilter && ["status", "eq", statusFilter],
                      line && ["line_code", "eq", line]], sort: [{ key: "created_at", dir: "desc" }],
                    unsupported: holdOnly ? "Saringan “ditahan” belum bisa diikuti berkas Excel — matikan saringan itu atau pakai CSV." : "" }}
                />
              </div>
            )} />
        </div>
      )}

      <InspectionFormModal
        open={showCreate} onClose={() => setShowCreate(false)} meta={meta}
        orphanTasks={orphanTasks}
        onCreated={() => { setShowCreate(false); refreshAll(); }}
      />

      <RandomCheckModal
        open={showRandom} onClose={() => setShowRandom(false)} meta={meta}
        onCreated={(doc) => { setShowRandom(false); refreshAll(); if (doc) setDetail(doc); }}
      />

      {detail && (
        <DetailModal onClose={() => setDetail(null)} label="Rincian SPK inspeksi"
          size="xl" testId="ins-detail-modal" framed>
          <InspectionDetailPanel
            doc={detail} meta={meta} currentUser={currentUser}
            onChanged={(fresh) => {
              if (fresh) setDetail(fresh);
              // B1 (26 Okt) — respons aksi tidak memuat kolom hitungan server (`held_rolls`, `sampling`); muat ulang
              // rincian supaya peringatan "roll masih ditahan" tetap lengkap sesudah baris diperiksa/dilepas.
              if (fresh?.id) getInspection(fresh.id).then((d) => { if (d) setDetail(d); }).catch(() => {});
              refreshAll();
            }}
            onClose={() => { setDetail(null); refreshAll(); }}
          />
        </DetailModal>
      )}
    </div>
  );
}
