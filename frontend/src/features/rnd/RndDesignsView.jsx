/**
 * RndDesignsView — **Desain & Pattern (Master)**: daftar berkartu + filter lengkap
 * (jenis · kategori · status · desainer · tag · produk · warna · nilai · artwork) dan
 * halaman detail per desain (siklus hidup, versi & nilai, timeline, umpan balik, colorway).
 *
 * Fase 3 · P6 (D-09, keputusan pemilik 26 Okt) — "Galeri Desain (Showcase)" (`cs-design-gallery`,
 * `DesignGalleryView`) bukan lagi layar kedua: kini mode tampilan **Galeri** di sini (kartu sampul besar +
 * saringan kepemilikan/diproduksi, hanya desain ACC). Klik kartu di mode mana pun membuka rincian desain yang
 * SAMA (`DesignDetailPage`; kepemilikan & klaim = tab di rincian). Alias `cs-design-gallery` → `rnd-designs`
 * preset `{ mode: "gallery", status: "acc" }` diaktifkan P8 dan dibaca lewat `useViewPreset`.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Filter, Layers, Plus, RefreshCw, Search, Tags, X } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import OkNotice from "../../components/OkNotice";
import LineFilter from "../../components/LineFilter";
import KNSelect from "../../components/KNSelect";
import PageTabs from "../../components/PageTabs";
import FilterChips from "../../components/FilterChips";
import useViewPreset from "../../hooks/useViewPreset";
import { useAppNav } from "../../context/AppNavContext";
import DesignFormModal from "./DesignFormModal";
import DesignDetailPage from "./design/DesignDetailPage";
import CategoryManagerModal from "./design/CategoryManagerModal";
import DateQuickNav from "./design/DateQuickNav";
import { DesignCard, FilterField, Kpi, ShowcaseCard } from "./design/DesignCards";
import {
  activeFilterCount, ARTWORK_OPTS, DESIGN_MODES, designStats, EMPTY_DATE, EMPTY_FILTER, filterDesigns, HOLD_OPTS,
  ORIGIN_OPTS, OWN_OPTS, PROD_OPTS, PROOFING_OPTS, REVISION_OPTS, rowsForMode, SCORE_OPTS, statusCounts, statusOptions,
} from "./design/designFilters";
import { listDesigns, studioCategories } from "./rndApi";
import { DESIGN_STATUS_META, errMsg } from "./rndMeta";
import { roleIs, can } from "../../config/roles";
import { actorLabel } from "../../utils/actorLabel";

// Audit UI 24 Okt (049) — di HP 11 dropdown saringan (±1.300px) dilipat dulu; layar lebar tetap terbuka.
const wideScreen = () => (typeof window === "undefined" || !window.matchMedia ? true : window.matchMedia("(min-width: 768px)").matches);
const MODE_KEYS = DESIGN_MODES.map((m) => m.key);
const presetStatus = (s) => (s && s !== "acc" ? s : "");

export default function RndDesignsView({ currentUser, selectedEntity, focus, onFocusConsumed, initialMode = "master" }) {
  const preset = useViewPreset("rnd-designs", (p) => applyPreset(p));
  const [modeRaw, setMode] = useState(() => (MODE_KEYS.includes(preset?.mode) ? preset.mode : initialMode));
  // Fase 3 · P8 (D-09, §1.1 butir 6) — mode Galeri = layar lama `cs-design-gallery`: `hidden_views` peran kustom terhadap
  // id lama menyembunyikan mode ini. Di luar AppNavProvider (aplikasi HP/uji) peran kosong → tetap tampil.
  const nav = useAppNav();
  const galleryAllowed = !nav.role || nav.canOpen("cs-design-gallery");
  const mode = modeRaw === "gallery" && !galleryAllowed ? "master" : modeRaw;
  const modeTabs = useMemo(() => DESIGN_MODES.map((m) => (m.key === "gallery" ? { ...m, hidden: !galleryAllowed } : m)),
    [galleryAllowed]);
  const [rows, setRows] = useState([]);
  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [f, setF] = useState(() => ({ ...EMPTY_FILTER, status: presetStatus(preset?.status) }));
  const [date, setDate] = useState(EMPTY_DATE);
  const [showFilters, setShowFilters] = useState(wideScreen);
  const [modal, setModal] = useState(null);
  const [openId, setOpenId] = useState(focus?.designId || null);
  const [catModal, setCatModal] = useState(false);

  function applyPreset(p) {
    if (MODE_KEYS.includes(p?.mode)) setMode(p.mode);
    if (p?.status !== undefined) setF((prev) => ({ ...prev, status: presetStatus(p.status) }));
    if (p?.designId) setOpenId(p.designId);
  }

  // Deep-link (Permintaan Desain → "Buka" / "Buat & buka desain") → langsung halaman detail.
  useEffect(() => {
    if (focus?.designId) { setOpenId(focus.designId); onFocusConsumed?.(); }
  }, [focus?.nonce]); // eslint-disable-line

  const role = currentUser?.role;
  const canAssess = roleIs(role, ["admin", "manager"]);
  const canCreate = canAssess || can(currentUser?.permissions, "design_request", "deliver") || can(currentUser?.permissions, "rnd", "manage");   // Sisir lanjutan gerbang peran (2026-10-21)
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const gallery = mode === "gallery";
  const switchMode = (m) => {
    setMode(m);
    // Status yang bukan ACC tidak ada di Galeri → kembali ke "Semua".
    if (m === "gallery" && f.status && !statusOptions("gallery").some((o) => o.key === f.status)) set("status", "");
  };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (f.line) params.line = f.line;
      const res = await listDesigns(params);
      setRows(Array.isArray(res) ? res : res?.items || []);
      setError("");
    } catch (e) { setError(errMsg(e, "Gagal memuat master desain.")); } finally { setLoading(false); }
  }, [selectedEntity, f.line]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { studioCategories({ status: "all" }).then(setCats).catch(() => setCats([])); }, [catModal]);

  const modeRows = useMemo(() => rowsForMode(rows, mode), [rows, mode]);
  const designers = useMemo(() => [...new Set(modeRows.map((r) => r.created_by).filter(Boolean))].sort(), [modeRows]);
  const tags = useMemo(() => [...new Set(modeRows.flatMap((r) => r.tags || []))].sort(), [modeRows]);
  const products = useMemo(() => {
    const m = new Map(); modeRows.forEach((r) => (r.recommended_products || []).forEach((p) => m.set(p.id, p))); return [...m.values()];
  }, [modeRows]);
  const catOpts = useMemo(() => [{ value: "", label: "Semua kategori pattern" },
    ...cats.filter((c) => c.design_type === "pattern").map((c) => ({ value: c.code, label: `${c.code} — ${c.name}` }))], [cats]);
  const dcatOpts = useMemo(() => [{ value: "", label: "Semua kategori desain" },
    ...cats.filter((c) => c.design_type === "design").map((c) => ({ value: c.code, label: `${c.code} — ${c.name}` }))], [cats]);

  const filtered = useMemo(() => filterDesigns(modeRows, f, date), [modeRows, f, date]);
  const stats = useMemo(() => designStats(rows), [rows]);
  const activeFilters = activeFilterCount(f, date, mode);
  // UAT 24 Okt (audit UI tahap 2) — G5-41: hitungan per chip status = jumlah desain berstatus itu.
  const counts = useMemo(() => statusCounts(modeRows), [modeRows]);
  const resetFilters = () => { setF({ ...EMPTY_FILTER, line: f.line, status: gallery ? f.status : "" }); setDate(EMPTY_DATE); };

  if (openId) {
    return <DesignDetailPage designId={openId} currentUser={currentUser} onBack={() => setOpenId(null)} onChanged={load} />;
  }

  return (
    <div data-testid="rnd-designs-view" data-mode={mode}>
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="rnd-designs-error" />

      <div className="section-card mb-3">
        {/* Audit UI 24 Okt (049) — kepala boleh turun baris: "Desain Baru" dulu keluar layar di HP. */}
        <div className="section-head flex-wrap">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-[#0058CC]" />
            <h2 data-testid="rnd-designs-title">Desain & Pattern (Master)</h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {canAssess && (
              <button className="secondary-button" onClick={() => setCatModal(true)} data-testid="rnd-designs-categories"><Tags size={13} /> Kategori</button>
            )}
            <button className="secondary-button" onClick={load} data-testid="rnd-designs-refresh"><RefreshCw size={13} /> Muat ulang</button>
            {canCreate && (
              <button className="primary-button" data-testid="design-create-button" onClick={() => setModal({ mode: "create" })}>
                <Plus size={13} /> Desain Baru
              </button>
            )}
          </div>
        </div>
        <PageTabs testId="rnd-designs-tabs" value={mode} onChange={switchMode} tabs={modeTabs} ariaLabel="Tampilan desain" className="!mb-0 px-3" />
        <div className="section-body space-y-2.5">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4 lg:grid-cols-8" data-testid="rnd-designs-stats">
            <Kpi label="Total desain" value={stats.total} />
            <Kpi label="Menunggu review" value={stats.review} tone="#0058CC" />
            <Kpi label="Perlu revisi" value={stats.revision} tone="#C62828" />
            <Kpi label="Tahap final" value={stats.final} tone="#A05000" />
            <Kpi label="ACC / Aktif" value={stats.acc} tone="#1B7F4B" />
            <Kpi label="Sedang ditahan" value={stats.hold} tone="#B24A00" testId="rnd-designs-kpi-hold" onClick={() => set("hold", f.hold === "yes" ? "" : "yes")} active={f.hold === "yes"} />
            <Kpi label="Proofing berjalan" value={stats.proofing} tone="#6B219A" testId="rnd-designs-kpi-proofing" onClick={() => set("proofing", f.proofing === "in_progress" ? "" : "in_progress")} active={f.proofing === "in_progress"} />
            <Kpi label="Jadi master produk" value={stats.master} tone="#0058CC" testId="rnd-designs-kpi-master" onClick={() => set("proofing", f.proofing === "master" ? "" : "master")} active={f.proofing === "master"} />
          </div>
          <OkNotice message={okMsg} onDismiss={() => setOkMsg("")} testId="rnd-designs-ok" />
          {gallery && (
            <p className="text-[11px] text-[#6B6B73]" data-testid="rnd-designs-gallery-note">
              Galeri hanya memuat desain yang sudah disetujui penilai (ACC / final / aktif). Klik kartu untuk rincian, kepemilikan &amp; klaim.
            </p>
          )}
          <DateQuickNav value={date} onChange={setDate} testId="design-date-nav" />
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[200px] max-w-sm flex-1">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="rnd-designs-search" value={f.q} onChange={(e) => set("q", e.target.value)} className="field !pl-8"
                placeholder="Cari kode / judul / tag / desainer / SKU master…" />
            </div>
            <LineFilter value={f.line} onChange={(v) => set("line", v)} storageKey="rnd-designs"
              allowed={currentUser?.allowed_line_codes} testId="rnd-designs-line-filter" />
            <button className={`secondary-button ${activeFilters ? "!border-[#0058CC] !text-[#0058CC]" : ""}`} onClick={() => setShowFilters((s) => !s)}
              data-testid="rnd-designs-toggle-filters">
              <Filter size={13} /> Filter {activeFilters ? `(${activeFilters})` : ""}
            </button>
            {activeFilters > 0 && (
              <button className="text-[11px] text-[#0058CC] underline" onClick={resetFilters} data-testid="rnd-designs-reset-filter">
                <X size={10} className="inline" /> reset
              </button>
            )}
          </div>
          {/* L-01: status = FilterChips (dulu tab garis di dalam panel saringan). */}
          <FilterChips testId="rnd-filter-status" ariaLabel="Status desain" value={f.status} onChange={(v) => set("status", v || "")}
            options={statusOptions(mode).map((o) => ({ ...o, count: counts[o.key] || 0, testId: `rnd-filter-status-${o.key || "all"}` }))} />
          {showFilters && (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-5" data-testid="rnd-designs-filters">
              {/* G5-41: setiap saringan diberi label ringkas di atasnya (dulu 11 dropdown tanpa label). */}
              {gallery && <FilterField label="Kepemilikan"><KNSelect data-testid="rnd-filter-ownership" className="field" value={f.own} options={OWN_OPTS} onValueChange={(v) => set("own", v)} /></FilterField>}
              {gallery && <FilterField label="Produksi"><KNSelect data-testid="rnd-filter-produced" className="field" value={f.produced} options={PROD_OPTS} onValueChange={(v) => set("produced", v)} /></FilterField>}
              <FilterField label="Ditahan"><KNSelect data-testid="rnd-filter-hold" className="field" value={f.hold} options={HOLD_OPTS} onValueChange={(v) => set("hold", v)} /></FilterField>
              <FilterField label="Asal desain"><KNSelect data-testid="rnd-filter-origin" className="field" value={f.origin} options={ORIGIN_OPTS} onValueChange={(v) => set("origin", v)} /></FilterField>
              <FilterField label="Proofing"><KNSelect data-testid="rnd-filter-proofing" className="field" value={f.proofing} options={PROOFING_OPTS} onValueChange={(v) => set("proofing", v)} /></FilterField>
              <FilterField label="Kategori pattern"><KNSelect data-testid="rnd-filter-category" className="field" value={f.cat} options={catOpts} onValueChange={(v) => set("cat", v)} searchable /></FilterField>
              <FilterField label="Kategori desain"><KNSelect data-testid="rnd-filter-dcategory" className="field" value={f.dcat} options={dcatOpts} onValueChange={(v) => set("dcat", v)} /></FilterField>
              <FilterField label="Desainer"><KNSelect data-testid="rnd-filter-designer" className="field" value={f.designer} searchable
                options={[{ value: "", label: "Semua desainer" }, ...designers.map((n) => ({ value: n, label: actorLabel(n) }))]} onValueChange={(v) => set("designer", v)} /></FilterField>
              <FilterField label="Tag"><KNSelect data-testid="rnd-filter-tag" className="field" value={f.tag} searchable
                options={[{ value: "", label: "Semua tag" }, ...tags.map((t) => ({ value: t, label: t }))]} onValueChange={(v) => set("tag", v)} /></FilterField>
              <FilterField label="Peruntukan produk"><KNSelect data-testid="rnd-filter-product" className="field" value={f.product} searchable
                options={[{ value: "", label: "Semua peruntukan produk" }, ...products.map((p) => ({ value: p.id, label: `${p.sku} — ${p.name}` }))]} onValueChange={(v) => set("product", v)} /></FilterField>
              <FilterField label="Ronde revisi"><KNSelect data-testid="rnd-filter-revision" className="field" value={f.revision} options={REVISION_OPTS} onValueChange={(v) => set("revision", v)} /></FilterField>
              <FilterField label="Nilai ACC"><KNSelect data-testid="rnd-filter-score" className="field" value={f.score} options={SCORE_OPTS} onValueChange={(v) => set("score", v)} /></FilterField>
              <FilterField label="Berkas desain"><KNSelect data-testid="rnd-filter-artwork" className="field" value={f.artwork} options={ARTWORK_OPTS} onValueChange={(v) => set("artwork", v)} /></FilterField>
            </div>
          )}
          {gallery && <p className="text-[11px] text-[#6B6B73]" data-testid="gallery-count"><b>{filtered.length}</b> dari {modeRows.length} desain ACC</p>}
        </div>
      </div>

      <div className="section-card">
        <div className="section-body">
          {loading ? (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
              {Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-[230px] animate-pulse rounded-lg bg-[#F5F5F7]" />)}
            </div>
          ) : filtered.length === 0 ? (
            <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid="rnd-designs-empty">
              <Layers className="mx-auto mb-2 text-gray-300" size={28} />
              {(f.status && activeFilters === (gallery ? 0 : 1) && !f.q.trim()) ? (
                <p>Tidak ada desain berstatus <b>{DESIGN_STATUS_META[f.status]?.label || f.status}</b>.{" "}
                  <button type="button" className="link-button" data-testid="rnd-designs-show-all" onClick={() => set("status", "")}>Tampilkan semua</button></p>
              ) : (activeFilters || f.q.trim()) ? <p>Tidak ada desain yang cocok dengan saringan saat ini.{" "}
                  <button type="button" className="link-button" data-testid="rnd-designs-clear" onClick={resetFilters}>Hapus saringan</button></p>
                : gallery ? <p data-testid="gallery-empty">Belum ada desain yang di-ACC. Desain tampil di sini otomatis setelah disetujui penilai.</p>
                  : <p>Belum ada desain. Buat desain baru — kode terbentuk otomatis dari inisial desainer, jenis, dan kategori.</p>}
            </div>
          ) : gallery ? (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" data-testid="gallery-grid">
              {filtered.map((g) => <ShowcaseCard key={g.id} g={g} onOpen={() => setOpenId(g.id)} />)}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
              {filtered.map((d) => <DesignCard key={d.id} d={d} onOpen={() => setOpenId(d.id)} />)}
            </div>
          )}
        </div>
      </div>

      {modal && (
        <DesignFormModal mode={modal.mode} design={modal.design} canManageMaster={canAssess} onClose={() => setModal(null)}
          onSaved={(res) => { setModal(null); setOkMsg(`Desain ${res?.code || ""} tersimpan.`); load(); if (res?.id) setOpenId(res.id); }} />
      )}
      {catModal && <CategoryManagerModal onClose={() => setCatModal(false)} />}
    </div>
  );
}
