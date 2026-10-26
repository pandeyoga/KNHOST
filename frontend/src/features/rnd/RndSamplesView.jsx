/**
 * RndSamplesView — layar **Sample R&D** (labdip · handfeel · proofing), dibuat SEMIRIP mungkin dengan
 * papan Permintaan Desain: kartu ringkasan, PageTabs **Papan** (kolom per status) · **Daftar** (tabel/kartu)
 * · **Galeri** (kartu bersampul foto bukti), chip jenis dari MASTER `/api/rnd/sample-types`, lalu pop-up
 * rincian bergaya studio dengan tab per jenis.
 *
 * Fase 3 · P6 (D-24b, keputusan pemilik 26 Okt): Labdip/Handfeel/Proofing (`SampleTypeGalleryView`) bukan
 * lagi layar sendiri — galeri per jenis = mode Galeri + chip jenis di layar ini. Id lama `rnd-labdip` dkk.
 * menjadi alias `rnd-samples` dengan preset `{ mode: "gallery", type, purpose: "all" }` (diaktifkan P8),
 * dibaca lewat `useViewPreset`. Aturan L-01: satu bilah tab (PageTabs) + saringan berupa chip/KNSelect.
 *
 * Mekanisme di server TIDAK berubah (kirim ke supplier → round → nilai → pemenang).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Beaker, Plus, RefreshCw } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import OkNotice from "../../components/OkNotice";
import LineFilter from "../../components/LineFilter";
import DetailModal from "../../components/DetailModal";
import KNSelect from "../../components/KNSelect";
import PageTabs from "../../components/PageTabs";
import FilterChips from "../../components/FilterChips";
import { REVISION_FILTER_OPTIONS } from "../../components/RevisionProgress";
import { useAppNav } from "../../context/AppNavContext";
import useViewPreset from "../../hooks/useViewPreset";
import { canWriteInScope, WRITE_BLOCK_HINT } from "../../utils/writeScope";
import { EmptyState } from "../finance/financeShared";
import SampleFormModal from "./SampleFormModal";
import PicQueuePanel from "./PicQueuePanel";
import SampleDetailPanel from "./SampleDetailPanel";
import SampleBoard from "./SampleBoard";
import SampleListTable from "./SampleListTable";
import SampleGalleryPanel from "./SampleGalleryPanel";
import { listSamples, sampleTypes } from "./rndApi";
import { cleanRndNote, errMsg, SAMPLE_BOARD_ORDER, SAMPLE_STATUS_META } from "./rndMeta";
import { typeLabel, typeMeta } from "./sampleTypeMeta";
import {
  filterSamples, galleryKpis, LEGACY_TYPE_VIEW, PURPOSE_OPTIONS, purposeParam, SAMPLE_MODES, statusCounts,
} from "./sampleViewUtils";
import { roleIs } from "../../config/roles";

const TITLE = { revalidation: "Uji Ulang SKU", new_development: "R&D Produk Baru" };
const STATUS_KEYS = [...SAMPLE_BOARD_ORDER, "cancelled"];
const MODE_KEYS = SAMPLE_MODES.map((m) => m.key);
const PURPOSE_KEYS = PURPOSE_OPTIONS.map((p) => p.key);

export default function RndSamplesView({ currentUser, selectedEntity, focus, onFocusConsumed, purpose = "",
  view = "", initialMode = "board", initialType = "" }) {
  // Preset navigasi (alias `rnd-labdip` → `rnd-samples` {mode:"gallery", type:"labdip", purpose:"all"}).
  const presetView = view || (purpose === "revalidation" ? "rnd-revalidation" : "rnd-samples");
  const preset = useViewPreset(presetView, (p) => applyPreset(p));
  const [mode, setMode] = useState(() => (MODE_KEYS.includes(preset?.mode) ? preset.mode : initialMode));
  const [type, setType] = useState(() => (preset?.type !== undefined ? preset.type || "" : initialType));
  const [galleryPurpose, setGalleryPurpose] = useState(() => (PURPOSE_KEYS.includes(preset?.purpose) ? preset.purpose : "all"));
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState({});
  const [types, setTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [minRevision, setMinRevision] = useState("");
  const [lineFilter, setLineFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [openId, setOpenId] = useState("");
  const [openType, setOpenType] = useState("");
  const [focusRoundId, setFocusRoundId] = useState("");
  const [prefill, setPrefill] = useState(null);
  const [pendingNumber, setPendingNumber] = useState("");
  const [queueKey, setQueueKey] = useState(0);

  function applyPreset(p) {
    if (MODE_KEYS.includes(p?.mode)) setMode(p.mode);
    if (p?.type !== undefined) setType(p.type || "");
    if (PURPOSE_KEYS.includes(p?.purpose)) setGalleryPurpose(p.purpose);
  }

  const role = currentUser?.role;
  const canCreate = roleIs(role, ["admin", "manager", "sales", "md"]);
  const canPic = roleIs(role, ["admin", "manager", "md"]);
  // UAT 24 Okt (audit UI tahap 2) — G5-63: mode "Semua badan usaha" hanya-lihat → tombol buat nonaktif.
  const scopeWritable = canWriteInScope(selectedEntity);
  const gallery = mode === "gallery";
  const serverPurpose = purposeParam(mode, purpose, galleryPurpose);

  // `hidden_views` peran kustom terhadap id lama (`rnd-labdip` dkk.) menyembunyikan chip jenisnya (§1.1.6).
  // Di luar AppNavProvider (`role` kosong) tidak ada gerbang — server tetap penjaga data.
  const nav = useAppNav();
  const typeAllowed = useCallback((code) => !nav.role || !LEGACY_TYPE_VIEW[code] || nav.canOpen(LEGACY_TYPE_VIEW[code]),
    [nav]);
  useEffect(() => { if (type && !typeAllowed(type)) setType(""); }, [type, typeAllowed]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 300 };
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (type) params.sample_type = type;
      if (lineFilter) params.line = lineFilter;
      if (serverPurpose) params.purpose = serverPurpose;   // UAT 24 Okt (P4.1) — dua pintu: produk baru / uji ulang
      const res = await listSamples(params);
      setRows(res?.items || []);
      setStats(res?.stats || {});
      setError("");
      setQueueKey((k) => k + 1);
    } catch (e) {
      setError(errMsg(e, "Gagal memuat permintaan sample."));
    } finally { setLoading(false); }
  }, [selectedEntity, type, lineFilter, serverPurpose]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const p = {};
    if (selectedEntity && selectedEntity !== "all") p.entity_id = selectedEntity;
    if (lineFilter) p.line = lineFilter;
    sampleTypes(p).then((r) => setTypes(Array.isArray(r) ? r : [])).catch(() => {});
  }, [selectedEntity, lineFilter]);

  // Deep-link masuk (Pustaka Warna / kartu desain / tautan "asal harga").
  useEffect(() => {
    if (!focus?.nonce) return;
    if (focus.sampleId) { setOpenId(focus.sampleId); setFocusRoundId(focus.roundId || ""); }
    else if (focus.sampleNumber) setPendingNumber(focus.sampleNumber);
    if (focus.productId) {   // UAT 24 Okt (P5.2) — "Uji ulang SKU ini" dari spesifikasi yang kombinasinya sudah ada
      setPrefill({ product: focus.product || { id: focus.productId }, source_label: focus.productLabel || "" });
      setShowForm(true);
    }
    if (focus.colorId || focus.designId) {
      setPrefill({
        color_id: focus.colorId || "", design_id: focus.designId || "",
        need_design: Boolean(focus.designId),
        source_label: focus.colorLabel || focus.designLabel || "",
      });
      setShowForm(true);
    }
    onFocusConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focus?.nonce]);

  useEffect(() => {
    if (!pendingNumber || rows.length === 0) return;
    const hit = rows.find((r) => r.number === pendingNumber);
    if (hit) { setOpenId(hit.id); setPendingNumber(""); }
  }, [pendingNumber, rows]);

  const filtered = useMemo(() => filterSamples(rows, { status: statusFilter, minRevision, q, gallery }),
    [rows, statusFilter, minRevision, q, gallery]);
  const counts = useMemo(() => statusCounts(rows, { gallery }), [rows, gallery]);
  const kpi = gallery ? galleryKpis(rows, type) : stats;

  const typeLbl = type ? typeLabel(type, types).split(" (")[0] : "";
  const meta = type ? typeMeta(type, types) : {};
  const typeOptions = [{ key: "", label: "Semua jenis", testId: "rnd-samples-filter-all" },
    ...types.filter((t) => typeAllowed(t.value)).map((t) => ({ key: t.value, label: t.label.split(" (")[0], testId: `rnd-samples-filter-${t.value}` }))];
  const statusOptions = [{ key: "", label: "Semua", count: counts[""] || 0, testId: "rnd-samples-chip-all" },
    ...STATUS_KEYS.filter((s) => !gallery || s !== "cancelled" || counts.cancelled)
      .map((s) => ({ key: s, label: SAMPLE_STATUS_META[s].label, count: counts[s] || 0, testId: `rnd-samples-chip-${s}` }))];
  const closeDetail = () => { setOpenId(""); setOpenType(""); setFocusRoundId(""); };
  const openSample = (id, code = "") => { setOpenId(id); setOpenType(code); };
  const resetFilters = () => { setStatusFilter(""); setMinRevision(""); setQ(""); };
  const createLabel = purpose === "revalidation" ? "Buat Uji Ulang" : "Buat Permintaan";
  const hasFilter = Boolean(statusFilter || minRevision || q.trim());

  const emptyNode = minRevision && !statusFilter && !q.trim() ? (
    <EmptyState icon={Beaker} testId="rnd-samples-empty" title={`Tidak ada sample dengan revisi ≥ ${minRevision}`}
      hint={"Tidak ada yang tersendat di revisi berulang. Pilih \"Semua ronde\" untuk melihat seluruhnya."} />
  ) : hasFilter ? (
    <EmptyState icon={Beaker} testId="rnd-samples-empty" title="Tidak ada permintaan yang cocok dengan saringan"
      hint={<button type="button" className="link-button" data-testid="rnd-samples-clear" onClick={resetFilters}>Hapus saringan</button>} />
  ) : (
    <EmptyState icon={Beaker} testId="rnd-samples-empty"
      title={typeLbl ? `Belum ada sample ${typeLbl.toLowerCase()}` : purpose === "revalidation" ? "Belum ada uji ulang SKU" : "Belum ada permintaan sample"}
      hint={!canCreate ? "Permintaan sample badan usaha ini akan muncul di sini."
        : purpose === "revalidation" && !gallery
          ? "Uji ulang SKU aktif ke supplier yang berkontrak (atau pernah PO) — klik Buat Uji Ulang."
          : typeLbl ? `Klik ${createLabel} — jenis ${typeLbl} sudah terpilih, tinggal tulis brief & target.`
            : "Buat permintaan labdip / handfeel / proofing, lalu kirim ke satu atau beberapa supplier untuk dibandingkan."} />
  );

  return (
    <div data-testid="rnd-samples-view" data-mode={mode} className="grid grid-cols-[minmax(0,1fr)] gap-3">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="rnd-samples-error" />

      <div className="section-card">
        {/* Audit UI 24 Okt (038) — kepala boleh turun baris: di HP judul dulu terjepit ("Permin/Sample") oleh filter & tombol. */}
        <div className="section-head flex-wrap">
          <div className="flex min-w-[200px] flex-1 items-center gap-2">
            <Beaker size={15} className="text-[#0058CC]" />
            <div className="min-w-0">
              <span className="kicker">R&amp;D</span>
              <h2 data-testid="rnd-samples-title" className="text-[13px] font-bold">{TITLE[purpose] || "Permintaan Sample"}</h2>
              {purpose === "new_development" && <p className="text-[11px] text-[#6B6B73]">Urutan: handfeel → labdip (dari handfeel ACC, banyak warna sekaligus) → spesifikasi/SKU · proofing di atas kain dasar yang sudah lolos.</p>}
              {purpose === "revalidation" && <p className="text-[11px] text-[#6B6B73]">Uji ulang SKU aktif ke supplier yang berkontrak (atau pernah PO) — tidak melahirkan SKU baru.</p>}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" className="secondary-button !py-1.5" onClick={load} data-testid="rnd-samples-refresh">
              <RefreshCw size={12} /> Muat ulang
            </button>
            {canCreate && (
              <button type="button" className="primary-button" data-testid="rnd-sample-create-button" onClick={() => setShowForm(true)}
                disabled={!scopeWritable} title={scopeWritable ? (typeLbl ? `Jenis ${typeLbl} terkunci dari chip jenis` : undefined) : WRITE_BLOCK_HINT}>
                <Plus size={13} /> {createLabel}
              </button>
            )}
          </div>
        </div>
        {pendingNumber && (
          <div className="mb-2 rounded-lg bg-[#FFF6E5] px-3 py-2 text-[11.5px] text-[#8C4A00]" data-testid="rnd-samples-pending-number">
            Mencari permintaan <b>{pendingNumber}</b>… Bila tidak ditemukan, permintaan itu mungkin milik entitas (PT) lain.
          </div>
        )}
        <div className="grid grid-cols-2 gap-2 p-2 sm:grid-cols-3 lg:grid-cols-6" data-testid="rnd-samples-stats">
          {[
            ["Total", kpi.total ?? 0, "rnd-samples-kpi-total"],
            ["Terkirim", kpi.sent ?? 0, "rnd-samples-kpi-sent"],
            ["Dikerjakan", kpi.in_progress ?? 0, "rnd-samples-kpi-in-progress"],
            ["Ada ACC", kpi.assessed ?? 0, "rnd-samples-kpi-assessed"],
            ["Pemenang dipilih", kpi.decided ?? 0, "rnd-samples-kpi-decided"],
            ["Ronde terlambat", kpi.overdue_rounds ?? 0, "rnd-samples-kpi-overdue"],
          ].map(([label, value, tid]) => (
            <div key={tid} className="rounded-lg border border-[#EFF0F2] bg-white px-3 py-2">
              <p className="text-[10.5px] font-bold uppercase tracking-wide text-[#8E8E93]">{label}</p>
              <p data-testid={tid} className={`text-[15px] font-bold tabular-nums ${tid.endsWith("overdue") && value ? "text-[#C62828]" : value ? "text-[#1C1C1E]" : "text-[#8E8E93]"}`}>{value}</p>
            </div>
          ))}
        </div>
      </div>

      {canPic && !gallery && <PicQueuePanel refreshKey={queueKey} onOpen={setOpenId} />}

      {/* L-01: satu bilah tab (mode tampilan); semua yang lain adalah saringan. */}
      <div className="section-card">
        <PageTabs testId="rnd-samples-tabs" value={mode} onChange={setMode} tabs={SAMPLE_MODES} ariaLabel="Tampilan sample" className="!mb-0 px-3" />
        <div className="section-body space-y-2">
          <FilterChips testId="rnd-samples-filters" ariaLabel="Jenis sampling" value={type} onChange={(v) => setType(v || "")} options={typeOptions} />
          {gallery && (
            <FilterChips testId="rnd-samples-purpose" ariaLabel="Tujuan sample" value={galleryPurpose} onChange={setGalleryPurpose}
              options={PURPOSE_OPTIONS.map((p) => ({ ...p, testId: `rnd-samples-purpose-${p.key}` }))} />
          )}
          <div className="flex flex-wrap items-center gap-2">
            <input data-testid="rnd-samples-search" className="field w-full sm:w-64 !py-1.5 !text-[11.5px]" value={q}
              onChange={(e) => setQ(e.target.value)} placeholder="Cari nomor / judul / supplier / warna…" />
            <LineFilter value={lineFilter} onChange={setLineFilter} storageKey="rnd-samples"
              allowed={currentUser?.allowed_line_codes} className="!py-1.5" testId="rnd-samples-line-filter" />
            <div className="w-[150px]" title="Saring dokumen yang berulang kali direvisi">
              <KNSelect data-testid="rnd-samples-revision-filter" className="field !py-1.5" value={minRevision}
                options={REVISION_FILTER_OPTIONS} onValueChange={setMinRevision} />
            </div>
          </div>
          <FilterChips testId="rnd-samples-status" ariaLabel="Status sample" value={statusFilter} onChange={(v) => setStatusFilter(v || "")} options={statusOptions} />
          {gallery && meta.notes && <p className="text-[11px] text-[#6B6B73]" data-testid="rnd-samples-type-notes">{cleanRndNote(meta.notes)}</p>}
        </div>
      </div>

      <OkNotice message={okMsg} onDismiss={() => setOkMsg("")} testId="rnd-samples-ok" />

      {gallery ? (
        <SampleGalleryPanel rows={filtered} code={type} label={typeLbl} loading={loading} emptyNode={emptyNode} onOpen={openSample} />
      ) : loading ? (
        <div data-testid="rnd-samples-loading" className="section-card grid gap-2 section-pad">
          {[0, 1, 2, 3].map((i) => <div key={i} className="h-9 animate-pulse rounded-md bg-[#F2F2F5]" />)}
        </div>
      ) : filtered.length === 0 ? (
        <div className="section-card section-pad">{emptyNode}</div>
      ) : mode === "board" ? (
        <SampleBoard rows={filtered} types={types} statusFilter={statusFilter} onOpen={(id) => openSample(id)} onShowList={() => setMode("list")} />
      ) : (
        <SampleListTable rows={filtered} types={types} onOpen={(id) => openSample(id)} />
      )}

      {showForm && (
        <SampleFormModal selectedEntity={selectedEntity} prefill={prefill} purpose={purpose} lockType={prefill ? "" : type}
          onClose={() => { setShowForm(false); setPrefill(null); }}
          onSaved={(created) => {
            setShowForm(false); setPrefill(null); load(); setOpenId(created?.id || "");
            if (created?.number) setOkMsg(`Permintaan ${created.number} tersimpan.`);
          }} />
      )}
      {openId && (
        <DetailModal framed onClose={closeDetail} label="Rincian sample" testId="sample-detail-modal">
          <SampleDetailPanel key={openId} sampleId={openId} currentUser={currentUser} types={types} initialType={openType || type}
            focusRoundId={focusRoundId} onClose={closeDetail} onChanged={load} onOpenSample={(id) => openSample(id)} />
        </DetailModal>
      )}
    </div>
  );
}
