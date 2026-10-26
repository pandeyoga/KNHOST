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
import { ClipboardCheck, Lock, Plus, RefreshCw, ShieldAlert, Shuffle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import DetailModal from "../../components/DetailModal";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import LineFilter from "../../components/LineFilter";
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
  INS_STATUS_CLASS, INS_STATUS_LABEL, inspectionsMeta, qcTasksWithoutDoc,
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

// Kolom daftar SPK (satu definisi → tabel di desktop, kartu di HP; fase 3 · P5 L-04).
const INS_COLUMNS = (openDetail) => [
  { key: "number", header: "Nomor", mobile: "title",
    render: (r) => {
      const s = r.summary || {};
      return (
        <span className="font-semibold text-[#1C1C1E]">
          {/* UAT 24 Okt (audit UI tahap 2) — nomor SPK sendiri membuka rincian. */}
          <button type="button" data-testid={`ins-open-${r.id}`} className="link-button !p-0 font-semibold"
            onClick={(e) => { e.stopPropagation(); openDetail(r.id); }}>{r.number}</button>
          {s.hold ? (
            <span data-testid={`ins-hold-badge-${r.id}`} className="ml-1 status-pill pill-danger">
              <Lock size={9} className="mr-0.5 inline" />{s.hold} ditahan
            </span>
          ) : null}
        </span>
      );
    } },
  { key: "status", header: "Status", mobile: "badge",
    render: (r) => {
      const s = r.summary || {};
      return (
        <span>
          <span className={`status-pill ${INS_STATUS_CLASS[r.status] || "pill-muted"}`}>
            {INS_STATUS_LABEL[r.status] || r.status}
          </span>
          {r.decision_label ? <span className="block text-[10px] text-[#6B6B73]">{r.decision_label}</span> : null}
          {/* UAT 24 Okt (audit UI tahap 2) — roll yang GAGAL 4-point/random check tetap ditahan walau SPK ditutup. */}
          {r.status === "done" && s.hold ? (
            <span data-testid={`ins-done-hold-${r.id}`} className="block text-[10px] font-semibold text-[#B4231F]">
              {s.hold} roll masih ditahan — lepas/tolak di rincian SPK
            </span>
          ) : null}
        </span>
      );
    } },
  { key: "kind", header: "Jenis", mobile: "subtitle", render: (r) => INS_KIND_SHORT[r.kind] || r.kind },
  { key: "ref", header: "Dokumen sumber", priority: 1,
    render: (r) => (
      <span className="text-[#3C3C43]">
        {r.ref_doc_number || "—"}
        <span className="block text-[10px] text-[#8E8E93]">{r.supplier_name || r.customer_name || ""}</span>
      </span>
    ) },
  { key: "assigned", header: "Petugas", priority: 2,
    render: (r) => r.assigned_name
      || (r.status === "draft" ? "Belum ditugaskan" : <span className="text-[#8E8E93]">tidak tercatat</span>) },
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

  const kindChips = [{ key: "all", label: "Semua jenis" }].concat(
    (meta.all_kinds || meta.kinds || []).map((k) => ({ key: k.value, label: INS_KIND_SHORT[k.value] || k.label })));
  const statusChips = [{ key: "all", label: "Semua status" }].concat(
    INS_BOARD_ORDER.map((s) => ({ key: s, label: INS_STATUS_LABEL[s] })));

  const policy = meta.policy || {};
  const activeFilters = [
    kindFilter && `jenis ${INS_KIND_SHORT[kindFilter] || kindFilter}`,
    statusFilter && `status ${INS_STATUS_LABEL[statusFilter] || statusFilter}`,
    line && "lini produk",
    search && `cari “${search}”`,
  ].filter(Boolean);

  return (
    <div data-testid="inspections-view" className="grid grid-cols-[minmax(0,1fr)] gap-3">
      {error && (
        <ErrorNotice message={error} onRetry={refreshAll} onDismiss={() => setError("")}
          testId="ins-error" />
      )}
      {paged.error && !error && (
        <ErrorNotice message={paged.error} onRetry={paged.refresh} testId="ins-list-error" />
      )}

      {/* Kepala + aksi */}
      <div className="section-card">
        <div className="section-head max-sm:!flex-col max-sm:!items-start max-sm:gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <ClipboardCheck size={15} className="text-[#1F6FEB]" />
            <div className="min-w-0">
              <span className="kicker">Kualitas</span>
              <h2 data-testid="panel-title" className="text-[13px] font-bold">SPK Inspeksi &amp; QC</h2>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <LineFilter value={line} onChange={setLine} storageKey="inspections"
              allowed={currentUser?.allowed_line_codes} className="!py-1.5"
              testId="ins-line-filter" />
            <input data-testid="ins-search" className="field !py-1.5 !text-[11.5px] w-full sm:w-56"
              placeholder="Cari nomor / dokumen sumber / petugas…"
              value={search} onChange={(e) => setSearch(e.target.value)} />
            <button data-testid="ins-refresh" className="secondary-button !py-1.5"
              onClick={refreshAll}>
              <RefreshCw size={12} /> Muat ulang
            </button>
            {canCreate && (
              <button data-testid="ins-create-button" className="primary-button"
                onClick={() => setShowCreate(true)}>
                <Plus size={13} /> Buat SPK Inspeksi
              </button>
            )}
            {meta.can_random_check && (
              <button data-testid="ins-random-check-button" className="secondary-button"
                onClick={() => setShowRandom(true)}>
                <Shuffle size={13} /> Random check stok
              </button>
            )}
          </div>
        </div>

        {/* Kartu ringkasan — dari agregat SERVER (bukan dari isi halaman).
            UAT 24 Okt (audit UI tahap 2): dulu 5 KPI bertumpuk satu kolom di HP & menempel tepi kartu. */}
        <div className="px-3 pb-3 pt-2">
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {[
            ["Total SPK", stats.total ?? 0, "ins-kpi-total"],
            ["Belum ditugaskan", stats.draft ?? 0, "ins-kpi-draft"],
            ["Sedang diperiksa", stats.in_progress ?? 0, "ins-kpi-progress"],
            ["Barang DITAHAN", stats.hold ?? 0, "ins-kpi-hold"],
            ["Ditolak", stats.rejected ?? 0, "ins-kpi-rejected"],
          ].map(([label, value, tid]) => (
            <div key={tid} className="min-w-0 rounded-lg border border-[#EFF0F2] bg-white px-2.5 py-2 sm:px-3">
              <p className="text-[10px] font-bold uppercase tracking-wide text-[#9A9BA3]">{label}</p>
              <p data-testid={tid} className="text-[15px] font-bold tabular-nums text-[#1C1C1E]">{value}</p>
            </div>
          ))}
        </div>

        {/* Kebijakan yang BERLAKU — supaya petugas tahu akibat sebelum mengisi */}
        <p data-testid="ins-policy-note" className="mt-2 text-[11px] text-[#6B6B73]">
          Kebijakan berlaku: warna beda dari sample &rarr;{" "}
          <strong>{policy.color_mismatch_label || "—"}</strong> · handfeel beda &rarr;{" "}
          <strong>{policy.handfeel_mismatch_label || "—"}</strong>. Warna &amp; handfeel penerimaan PO/hasil
          makloon diperiksa <strong>MD Quality</strong> (yang melepas/menolak tahanan); cacat 4-point &amp; grade
          diisi <strong>QC</strong>. Manajer tetap bisa melepas tahanan sebagai cadangan, dengan alasan tertulis.
        </p>
        </div>
      </div>

      {/* Jaring pengaman: tugas QC tanpa SPK (biasanya kosong) */}
      {orphanTasks.length > 0 && (
        <div data-testid="ins-orphan-tasks" className="section-card section-pad border-l-2 border-l-[#FF9500]">
          <div className="flex items-start gap-2">
            <ShieldAlert size={15} className="mt-0.5 shrink-0 text-[#B45309]" />
            <div>
              <p className="text-[12px] font-bold text-[#1C1C1E]">
                {orphanTasks.length} tugas QC belum punya SPK Inspeksi
              </p>
              <p className="mt-0.5 text-[11px] text-[#6B6B73]">
                SPK penerimaan PO seharusnya lahir otomatis saat barang masuk antrean QC.
                Barang di bawah ini masuk sebelum aturan itu berlaku — terbitkan SPK-nya
                lewat tombol <strong>Buat SPK Inspeksi</strong> (jenis “Penerimaan PO”).
              </p>
              <ul className="mt-1 grid gap-0.5">
                {orphanTasks.slice(0, 5).map((t) => (
                  <li key={t.id} data-testid={`ins-orphan-${t.id}`} className="text-[11px] text-[#3C3C43]">
                    {t.po_number || "(tanpa PO)"} · {t.product_name || "—"} ·{" "}
                    <QtyDual rolls={t.qty_rolls} measure={t.quantity} unit={t.unit}
                      testId={`ins-orphan-qty-${t.id}`} compact />
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Penyaring — Fase 3 · P5 (L-01/L-04): jenis & status dulu campuran pil + `.tab-bar` (saringan berlagak tab);
          kini FilterChips baku, satu baris bergulir di HP. "Hanya yang DITAHAN" = preset papan "Barang ditahan QC" (D-28). */}
      <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-1.5" data-testid="ins-filters">
        <FilterChips ariaLabel="Jenis inspeksi" value={kindFilter || "all"}
          onChange={(k) => setKindFilter(k === "all" ? "" : k)}
          chipTestId={(k) => `ins-chip-kind-${k}`} options={kindChips} />
        <div className="flex flex-wrap items-center gap-1.5">
          <FilterChips ariaLabel="Status SPK" value={statusFilter || "all"}
            onChange={(k) => setStatusFilter(k === "all" ? "" : k)}
            chipTestId={(k) => `ins-chip-status-${k}`} options={statusChips} className="min-w-0 max-w-full" />
          <FilterChips ariaLabel="Barang ditahan" multiple value={holdOnly ? ["hold"] : []}
            onChange={(v) => setHoldOnly(v.includes("hold"))}
            options={[{ key: "hold", label: "Hanya yang DITAHAN", icon: Lock, testId: "ins-chip-hold" }]} />
        </div>
      </div>

      {paged.loading ? (
        <div data-testid="ins-loading" className="section-card section-pad grid gap-2">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-9 animate-pulse rounded-md bg-[#F2F2F5]" />)}
        </div>
      ) : (paged.items || []).length === 0 ? (
        <div className="section-card section-pad">
          {/* UAT 24 Okt (audit UI tahap 2) — dulu "Belum ada SPK inspeksi" walau penyebabnya penyaring (mis. lini). */}
          <EmptyState icon={ClipboardCheck}
            title={activeFilters.length ? "Tidak ada SPK yang cocok dengan penyaring" : "Belum ada SPK inspeksi"}
            hint={holdOnly
              ? "Tidak ada barang yang sedang ditahan. Hapus penyaring “Hanya yang DITAHAN” untuk melihat seluruh SPK."
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
