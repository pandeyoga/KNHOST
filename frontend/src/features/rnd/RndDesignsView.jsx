/**
 * RndDesignsView — **Desain & Pattern (Master)**: daftar berkartu + filter lengkap
 * (jenis · kategori · status · desainer · tag · produk · warna · nilai · artwork) dan
 * halaman detail per desain (siklus hidup, versi & nilai, timeline, umpan balik, colorway).
 */
import DesignImage from "./design/DesignImage";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Filter, Layers, Plus, RefreshCw, Search, Tags, X } from "lucide-react";
import ErrorNotice from "../../components/ErrorNotice";
import OkNotice from "../../components/OkNotice";
import LineFilter from "../../components/LineFilter";
import KNSelect from "../../components/KNSelect";
import { OptionTabs } from "../../components/ListControls";
import DesignFormModal from "./DesignFormModal";
import DesignDetailPage from "./design/DesignDetailPage";
import CategoryManagerModal from "./design/CategoryManagerModal";
import { ScoreBadge } from "./design/ScoreInput";
import { RoundBadge } from "./design/RoundsProgress";
import { HoldBadge, OriginBadge, ProofingBadge } from "./design/DesignBadges";
import DateQuickNav, { inDateRange } from "./design/DateQuickNav";
import { designFileUrl, listDesigns, studioCategories } from "./rndApi";
import { DESIGN_STATUS_META, PROOFING_STATE_META, errMsg } from "./rndMeta";
import { roleIs, can } from "../../config/roles";
import { formatDate } from "../../utils/formatters";
import { actorLabel } from "../../utils/actorLabel";

const STATUS_OPTS = [
  { value: "", label: "Semua status" },
  ...Object.entries(DESIGN_STATUS_META).filter(([k]) => k !== "retired").map(([k, m]) => ({ value: k, label: m.label })),
];
const REVISION_OPTS = [
  { value: "", label: "Semua ronde" }, { value: "0", label: "Pengajuan awal (belum revisi)" },
  { value: "1", label: "≥ 1× revisi" }, { value: "2", label: "≥ 2× revisi" }, { value: "3", label: "≥ 3× revisi" },
];
const SCORE_OPTS = [
  { value: "", label: "Semua nilai ACC" }, { value: "unscored", label: "Belum ACC / belum dinilai" },
  { value: "1", label: "≥ 1,00" }, { value: "1.5", label: "≥ 1,50" }, { value: "1.75", label: "≥ 1,75" }, { value: "2", label: "= 2,00" },
];
const ARTWORK_OPTS = [{ value: "", label: "Berkas: semua" }, { value: "yes", label: "Sudah ada berkas desain" }, { value: "no", label: "Belum ada berkas" }];
const HOLD_OPTS = [{ value: "", label: "Ditahan: semua" }, { value: "yes", label: "Sedang ditahan" }, { value: "no", label: "Tidak ditahan" }];
const PROOFING_OPTS = [{ value: "", label: "Proofing: semua" },
  ...Object.entries(PROOFING_STATE_META).map(([k, m]) => ({ value: k, label: m.label }))];
const ORIGIN_OPTS = [{ value: "", label: "Asal: semua" }, { value: "internal", label: "Desain internal" }, { value: "special_order", label: "Pesanan Khusus" }, { value: "redesign", label: "Redesign" }];
const EMPTY = { q: "", status: "", cat: "", dcat: "", designer: "", tag: "", product: "", revision: "", score: "", artwork: "", line: "", hold: "", proofing: "", origin: "" };
const EMPTY_DATE = { field: "approved_at", from: "", to: "", preset: "" };
// Audit UI 24 Okt (049) — di HP 11 dropdown saringan (±1.300px) dilipat dulu; layar lebar tetap terbuka.
const wideScreen = () => (typeof window === "undefined" || !window.matchMedia ? true : window.matchMedia("(min-width: 768px)").matches);

export default function RndDesignsView({ currentUser, selectedEntity, focus, onFocusConsumed }) {
  const [rows, setRows] = useState([]);
  const [cats, setCats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [f, setF] = useState(EMPTY);
  const [date, setDate] = useState(EMPTY_DATE);
  const [showFilters, setShowFilters] = useState(wideScreen);
  const [modal, setModal] = useState(null);
  const [openId, setOpenId] = useState(focus?.designId || null);
  const [catModal, setCatModal] = useState(false);

  // Deep-link (Permintaan Desain → "Buka" / "Buat & buka desain") → langsung halaman detail.
  useEffect(() => {
    if (focus?.designId) { setOpenId(focus.designId); onFocusConsumed?.(); }
  }, [focus?.nonce]); // eslint-disable-line

  const role = currentUser?.role;
  const canAssess = roleIs(role, ["admin", "manager"]);
  const canCreate = canAssess || can(currentUser?.permissions, "design_request", "deliver") || can(currentUser?.permissions, "rnd", "manage");   // Sisir lanjutan gerbang peran (2026-10-21)
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

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

  const designers = useMemo(() => [...new Set(rows.map((r) => r.created_by).filter(Boolean))].sort(), [rows]);
  const tags = useMemo(() => [...new Set(rows.flatMap((r) => r.tags || []))].sort(), [rows]);
  const products = useMemo(() => {
    const m = new Map(); rows.forEach((r) => (r.recommended_products || []).forEach((p) => m.set(p.id, p))); return [...m.values()];
  }, [rows]);
  const catOpts = useMemo(() => [{ value: "", label: "Semua kategori pattern" },
    ...cats.filter((c) => c.design_type === "pattern").map((c) => ({ value: c.code, label: `${c.code} — ${c.name}` }))], [cats]);
  const dcatOpts = useMemo(() => [{ value: "", label: "Semua kategori desain" },
    ...cats.filter((c) => c.design_type === "design").map((c) => ({ value: c.code, label: `${c.code} — ${c.name}` }))], [cats]);

  const filtered = useMemo(() => {
    const term = f.q.trim().toLowerCase();
    return rows.filter((d) => {
      const status = d.status === "retired" ? "archived" : (d.status || "draft");
      if (f.status && status !== f.status) return false;
      if (f.cat && d.category_code !== f.cat) return false;
      if (f.dcat && d.design_category_code !== f.dcat) return false;
      if (f.designer && d.created_by !== f.designer) return false;
      if (f.tag && !(d.tags || []).includes(f.tag)) return false;
      if (f.product && !(d.recommended_product_ids || []).includes(f.product)) return false;
      const rev = d.revision_count ?? Math.max(0, (d.version || 1) - 1);
      if (f.revision === "0" && rev !== 0) return false;
      if (f.revision && f.revision !== "0" && rev < Number(f.revision)) return false;
      const sc = d.final_score;
      if (f.score === "unscored" && sc !== null && sc !== undefined) return false;
      if (f.score && f.score !== "unscored" && !(sc !== null && sc !== undefined && Number(sc) >= Number(f.score))) return false;
      if (f.artwork === "yes" && !d.artwork_count) return false;
      if (f.artwork === "no" && d.artwork_count) return false;
      if (f.hold === "yes" && !d.on_hold) return false;
      if (f.hold === "no" && d.on_hold) return false;
      if (f.proofing && (d.proofing?.state || "none") !== f.proofing) return false;
      if (f.origin && (d.origin || "internal") !== f.origin) return false;
      if (!inDateRange(d[date.field], date.from, date.to)) return false;
      if (!term) return true;
      return [d.code, d.title, d.story, d.category_name, d.design_category_name, d.created_by, d.proofing?.detail, d.proofing?.master_product?.sku, ...(d.tags || [])].some((v) => (v || "").toLowerCase().includes(term));
    });
  }, [rows, f, date]);

  const stats = useMemo(() => ({
    total: rows.length,
    review: rows.filter((d) => ["pending_approval", "in_review"].includes(d.status)).length,
    revision: rows.filter((d) => d.status === "revision").length,
    final: rows.filter((d) => ["approved", "final_submitted"].includes(d.status)).length,
    acc: rows.filter((d) => ["approved", "final_submitted", "active"].includes(d.status)).length,
    hold: rows.filter((d) => d.on_hold).length,
    proofing: rows.filter((d) => d.proofing?.state === "in_progress").length,
    master: rows.filter((d) => d.proofing?.state === "master").length,
  }), [rows]);
  const activeFilters = Object.entries(f).filter(([k, v]) => v && k !== "q" && k !== "line").length + (date.from || date.to ? 1 : 0);
  // UAT 24 Okt (audit UI tahap 2) — G5-41: hitungan per tab status = jumlah desain berstatus itu (dulu tab aktif
  // menampilkan `rows.length` = semua desain termuat, tab lain tanpa angka).
  const statusCounts = useMemo(() => {
    const c = { "": rows.length };
    rows.forEach((d) => { const k = d.status === "retired" ? "archived" : (d.status || "draft"); c[k] = (c[k] || 0) + 1; });
    return c;
  }, [rows]);

  if (openId) {
    return <DesignDetailPage designId={openId} currentUser={currentUser} onBack={() => setOpenId(null)} onChanged={load} />;
  }

  return (
    <div data-testid="rnd-designs-view">
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId="rnd-designs-error" />

      <div className="section-card mb-3">
        {/* Audit UI 24 Okt (049) — kepala boleh turun baris: "Desain Baru" dulu keluar layar di HP. */}
        <div className="section-head flex-wrap">
          <div className="flex items-center gap-2">
            <Layers size={16} className="text-[#6B219A]" />
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
          <DateQuickNav value={date} onChange={setDate} testId="design-date-nav" />
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[200px] max-w-sm flex-1">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid="rnd-designs-search" value={f.q} onChange={(e) => set("q", e.target.value)} className="field !pl-8"
                placeholder="Cari kode / judul / tag / desainer / SKU master…" />
            </div>
            <LineFilter value={f.line} onChange={(v) => set("line", v)} storageKey="rnd-designs"
              allowed={currentUser?.allowed_line_codes} testId="rnd-designs-line-filter" />
            <button className={`secondary-button ${activeFilters ? "!border-[#6B219A] !text-[#6B219A]" : ""}`} onClick={() => setShowFilters((s) => !s)}
              data-testid="rnd-designs-toggle-filters">
              <Filter size={13} /> Filter {activeFilters ? `(${activeFilters})` : ""}
            </button>
            {activeFilters > 0 && (
              <button className="text-[11px] text-[#6B219A] underline" onClick={() => { setF({ ...EMPTY, line: f.line }); setDate(EMPTY_DATE); }} data-testid="rnd-designs-reset-filter">
                <X size={10} className="inline" /> reset
              </button>
            )}
          </div>
          {showFilters && (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5" data-testid="rnd-designs-filters">
              <div className="col-span-full"><OptionTabs testId="rnd-filter-status" value={f.status} options={STATUS_OPTS} onChange={(v) => set("status", v)}
                countOf={(v) => statusCounts[v || ""] || 0} /></div>
              {/* G5-41: setiap saringan diberi label ringkas di atasnya (dulu 11 dropdown tanpa label). */}
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
              {(f.status && activeFilters === 1 && !f.q.trim()) ? (
                <p>Tidak ada desain berstatus <b>{DESIGN_STATUS_META[f.status]?.label || f.status}</b>.{" "}
                  <button type="button" className="link-button" data-testid="rnd-designs-show-all" onClick={() => set("status", "")}>Tampilkan semua</button></p>
              ) : (activeFilters || f.q.trim()) ? <p>Tidak ada desain yang cocok dengan saringan saat ini.{" "}
                  <button type="button" className="link-button" data-testid="rnd-designs-clear" onClick={() => { setF({ ...EMPTY, line: f.line }); setDate(EMPTY_DATE); }}>Hapus saringan</button></p>
                : <p>Belum ada desain. Buat desain baru — kode terbentuk otomatis dari inisial desainer, jenis, dan kategori.</p>}
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

function DesignCard({ d, onOpen }) {
  const meta = DESIGN_STATUS_META[d.status || "draft"] || DESIGN_STATUS_META.draft;
  const cover = (d.files || []).find((x) => (x.kind || "artwork") === "artwork" && (x.version || 1) === d.version)
    || (d.files || []).find((x) => (x.kind || "artwork") === "artwork");
  const fin = d.final || {};
  const acc = ["approved", "final_submitted", "active"].includes(d.status);
  return (
    <button type="button" onClick={onOpen} data-testid={`design-card-${d.id}`}
      className={`overflow-hidden rounded-lg border bg-white text-left transition-shadow hover:shadow-md focus:outline-none focus:ring-2 focus:ring-[#6B219A]/40 ${d.on_hold ? "border-[#F2B48A]" : "border-[#E5E5EA]"}`}>
      <div className="relative flex h-28 items-center justify-center bg-[#F5F5F7]">
        {cover ? <DesignImage src={designFileUrl(d.id, cover.id)} alt={d.title} data-testid={`design-cover-${d.id}`} className={`h-full w-full object-cover ${d.on_hold ? "opacity-70" : ""}`} loading="lazy" />
          : <span className="text-[10.5px] text-[#9A9BA3]">belum ada berkas</span>}
        <span className="absolute inset-x-1.5 top-1.5 flex flex-wrap items-start justify-between gap-1">
          <span className="flex flex-wrap gap-1"><RoundBadge design={d} testId={`design-round-${d.id}`} /><HoldBadge design={d} testId={`design-hold-${d.id}`} />{d.origin && d.origin !== "internal" && <OriginBadge design={d} testId={`design-origin-${d.id}`} />}</span>
          {acc && (
            <span className="rounded bg-white/90 px-1.5 py-0.5 text-[10px] font-bold text-[#6B219A]" data-testid={`design-final-${d.id}`}>
              final {fin.mockup_files ?? 0}/1 mockup · {fin.source_files ?? 0}/1 file asli
            </span>
          )}
        </span>
      </div>
      <div className="space-y-1 p-2">
        <div className="flex flex-wrap items-center justify-between gap-1">
          <span className="min-w-0 break-all font-mono text-[11.5px] font-bold" data-testid={`design-code-${d.id}`}>{d.code || "tanpa kode"}</span>
          <ScoreBadge value={acc ? d.final_score : null} acc={acc} testId={`design-score-${d.id}`} />
        </div>
        <p className="truncate text-[11px] text-[#1C1C1E]">{d.title}</p>
        <p className="truncate text-[10.5px] text-[#8E8E93]" data-testid={`design-meta-${d.id}`}>
          {[d.category_name || d.category_code, d.design_category_name || d.design_category_code, d.created_by && actorLabel(d.created_by)]
            .filter(Boolean).join(" · ") || "—"}
        </p>
        <div className="flex flex-wrap items-center justify-between gap-1">
          <span className={`status-pill ${meta.cls}`} data-testid={`design-status-${d.id}`}>{meta.label}</span>
          <span className="text-[10.5px] text-[#8E8E93]">{d.artwork_count || 0} berkas</span>
        </div>
        {d.rounds_total > 0 && (
          <p className={`text-[11px] font-semibold ${d.paper_rounds_done >= d.rounds_total ? "text-[#1A5C2E]" : "text-[#6B6B73]"}`} data-testid={`design-paper-count-${d.id}`}>
            Print paper {d.paper_rounds_done || 0}/{d.rounds_total} ronde
          </p>
        )}
        <ProofingBadge design={d} testId={`design-proofing-${d.id}`} showDetail />
        {d.proofing?.master_product && (
          <p className="truncate text-[10.5px] font-semibold text-[#0058CC]" data-testid={`design-master-${d.id}`}>
            master: <span className="font-mono">{d.proofing.master_product.sku}</span>{d.proofing.master_product.name ? ` — ${d.proofing.master_product.name}` : ""}
          </p>
        )}
        {(d.recommended_products || []).length > 0 && (
          <p className="truncate text-[10.5px] text-[#0058CC]">untuk: {d.recommended_products.map((p) => p.sku).join(", ")}</p>
        )}
        <p className="text-[10.5px] text-[#8E8E93]" data-testid={`design-dates-${d.id}`}>
          {d.approved_at ? `ACC ${formatDate(d.approved_at)} · ` : ""}update {formatDate(d.updated_at)}
        </p>
      </div>
    </button>
  );
}

function FilterField({ label, children }) {
  return (
    <div className="min-w-0">
      <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wide text-[#6B6B73]">{label}</p>
      {children}
    </div>
  );
}

function Kpi({ label, value, tone = "#1C1C1E", testId, onClick, active = false }) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag type={onClick ? "button" : undefined} onClick={onClick} data-testid={testId}
      className={`rounded-lg border p-2 text-left ${active ? "border-[#6B219A] bg-[#F1E9F7]" : "border-[#EFF0F2] bg-[#FAFBFC]"} ${onClick ? "hover:border-[#6B219A]" : ""}`}>
      <p className="text-[10.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[14px] font-bold tabular-nums leading-tight" style={{ color: tone }}>{value}</p>
    </Tag>
  );
}
