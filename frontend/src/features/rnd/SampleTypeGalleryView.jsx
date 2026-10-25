/**
 * SampleTypeGalleryView — galeri **per JENIS sampling** (Labdip · Handfeel · Proofing), dibuat
 * SEMIRIP mungkin dengan "Desain & Pattern (Master)" di hub Desainer: KPI → pencarian +
 * saringan → grid kartu bersampul foto bukti. Tombol "Sample <Jenis> Baru" membuka modal
 * permintaan dengan jenis itu sudah terpilih (terkunci). Klik kartu → rincian dengan tab
 * jenis ini aktif. Mekanisme server tetap `md_samples` (satu permintaan bisa >1 jenis).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Filter, FlaskConical, Plus, RefreshCw, Search, X } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import ErrorNotice from "../../components/ErrorNotice";
import OkNotice from "../../components/OkNotice";
import KNSelect from "../../components/KNSelect";
import { OptionTabs } from "../../components/ListControls";
import LineFilter from "../../components/LineFilter";
import { REVISION_FILTER_OPTIONS, sampleRevisionCount } from "../../components/RevisionProgress";
import SampleDetailPanel from "./SampleDetailPanel";
import SampleFormModal from "./SampleFormModal";
import SampleTypeCard, { typeRoundsOf } from "./SampleTypeCard";
import { listSamples, sampleTypes } from "./rndApi";
import { cleanRndNote, errMsg, SAMPLE_STATUS_META, typeTone } from "./rndMeta";
import { typeLabel, typeMeta } from "./sampleTypeMeta";
import { roleIs } from "../../config/roles";
import { canWriteInScope, WRITE_BLOCK_HINT } from "../../utils/writeScope";

const STATUS_OPTS = [{ value: "", label: "Semua status" },
  ...Object.entries(SAMPLE_STATUS_META).map(([k, m]) => ({ value: k, label: m.label }))];
const RESULT_OPTS = [
  { value: "", label: "Semua hasil" }, { value: "acc", label: "Sudah ada ACC" },
  { value: "revisi", label: "Hasil terakhir: revisi" }, { value: "pending", label: "Menunggu hasil supplier" },
  { value: "none", label: "Belum ada ronde" },
];
const PROOF_OPTS = [{ value: "", label: "Bukti: semua" }, { value: "yes", label: "Sudah ada foto bukti" }, { value: "no", label: "Belum ada bukti" }];
const SCORE_OPTS = [
  { value: "", label: "Semua skor" }, { value: "unscored", label: "Belum dinilai" },
  { value: "70", label: "≥ 70" }, { value: "80", label: "≥ 80" }, { value: "90", label: "≥ 90" },
];
const EMPTY = { q: "", status: "", supplier: "", result: "", proof: "", score: "", revision: "", line: "" };
// Di HP saringan lanjutan (±600px) dilipat dulu; di layar lebar tetap terbuka seperti sebelumnya.
const wideScreen = () => (typeof window === "undefined" || !window.matchMedia ? true : window.matchMedia("(min-width: 768px)").matches);

export default function SampleTypeGalleryView({ code, currentUser, selectedEntity }) {
  const [rows, setRows] = useState([]);
  const [types, setTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [okMsg, setOkMsg] = useState("");
  const [f, setF] = useState(EMPTY);
  const [showFilters, setShowFilters] = useState(wideScreen);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState(null);

  const role = currentUser?.role;
  const canCreate = roleIs(role, ["admin", "manager", "sales", "md"]);
  // UAT 24 Okt (audit UI tahap 2) — G5-63: mode "Semua badan usaha" hanya-lihat → tombol buat nonaktif.
  const scopeWritable = canWriteInScope(selectedEntity);
  const tone = typeTone(code);
  const label = typeLabel(code, types).split(" (")[0];
  const meta = typeMeta(code, types);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = { limit: 300, sample_type: code };
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      if (f.line) params.line = f.line;
      const res = await listSamples(params);
      setRows(res?.items || []);
      setError("");
    } catch (e) { setError(errMsg(e, `Gagal memuat sample ${label}.`)); } finally { setLoading(false); }
  }, [selectedEntity, code, f.line]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const p = {};
    if (selectedEntity && selectedEntity !== "all") p.entity_id = selectedEntity;
    sampleTypes(p).then((r) => setTypes(Array.isArray(r) ? r : [])).catch(() => {});
  }, [selectedEntity]);

  const suppliers = useMemo(() => {
    const m = new Map(); rows.forEach((s) => (s.participants || []).forEach((p) => m.set(p.supplier_id, p.supplier_name))); return [...m.entries()];
  }, [rows]);

  const filtered = useMemo(() => {
    const term = f.q.trim().toLowerCase();
    return rows.filter((s) => {
      const rounds = typeRoundsOf(s, code);
      if (f.status ? s.status !== f.status : s.status === "cancelled") return false;
      if (f.supplier && !(s.participants || []).some((p) => p.supplier_id === f.supplier)) return false;
      const last = rounds[rounds.length - 1];
      if (f.result === "acc" && !rounds.some((r) => r.result === "acc")) return false;
      if (f.result === "revisi" && last?.result !== "revisi") return false;
      if (f.result === "pending" && !(last && !last.result)) return false;
      if (f.result === "none" && rounds.length) return false;
      const proofs = rounds.reduce((a, r) => a + (r.attachments || []).length, 0);
      if (f.proof === "yes" && !proofs) return false;
      if (f.proof === "no" && proofs) return false;
      const best = rounds.reduce((a, r) => (r.score != null ? Math.max(a ?? 0, Number(r.score)) : a), null);
      if (f.score === "unscored" && best != null) return false;
      if (f.score && f.score !== "unscored" && !(best != null && best >= Number(f.score))) return false;
      const rev = sampleRevisionCount(s);
      if (f.revision === "0" && rev !== 0) return false;
      if (f.revision && f.revision !== "0" && rev < Number(f.revision)) return false;
      if (!term) return true;
      return [s.number, s.title, s.brief, s.color_target?.name, s.design_code, s.spec_number, s.requested_by,
        ...(s.participants || []).map((p) => p.supplier_name)].some((v) => (v || "").toLowerCase().includes(term));
    });
  }, [rows, f, code]);

  const stats = useMemo(() => {
    const live = rows.filter((s) => s.status !== "cancelled");
    return {
      total: live.length,
      sent: live.filter((s) => s.status === "sent").length,
      progress: live.filter((s) => s.status === "in_progress").length,
      acc: live.filter((s) => typeRoundsOf(s, code).some((r) => r.result === "acc")).length,
      decided: live.filter((s) => s.status === "decided").length,
      overdue: live.filter((s) => typeRoundsOf(s, code).some((r) => r.overdue)).length,
    };
  }, [rows, code]);
  const activeFilters = Object.entries(f).filter(([k, v]) => v && k !== "q" && k !== "line").length;
  // UAT 24 Okt (audit UI tahap 2) — G5-44: hitungan per tab status dihitung dari seluruh sample jenis ini (bukan
  // `rows.length` di tab aktif → dulu "Gagal — menunggu PIC 12" pada daftar kosong). "Semua" = tanpa yang batal,
  // sama dengan saringan di atas.
  const statusCounts = useMemo(() => {
    const c = { "": 0 };
    rows.forEach((s) => { c[s.status] = (c[s.status] || 0) + 1; if (s.status !== "cancelled") c[""] += 1; });
    return c;
  }, [rows]);
  const statusLabel = f.status ? (SAMPLE_STATUS_META[f.status]?.label || f.status) : "";

  return (
    <div data-testid={`sample-gallery-${code}`}>
      <ErrorNotice message={error} onRetry={load} onDismiss={() => setError("")} testId={`sample-gallery-error-${code}`} />

      <div className="section-card mb-3">
        {/* Audit UI 24 Okt (039–041) — kepala boleh turun baris: di HP tombol "Sample … Baru" dulu keluar layar. */}
        <div className="section-head flex-wrap">
          <div className="flex min-w-[180px] flex-1 flex-wrap items-center gap-2">
            <FlaskConical size={16} style={{ color: tone.fg }} />
            <h2 data-testid={`sample-gallery-title-${code}`}>{label} (Master)</h2>
            <span className="rounded-full px-2 py-0.5 text-[10.5px] font-bold" style={{ background: tone.bg, color: tone.fg }}>{typeLabel(code, types)}</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="secondary-button" onClick={load} data-testid={`sample-gallery-refresh-${code}`}><RefreshCw size={13} /> Muat ulang</button>
            {canCreate && (
              <button className="primary-button" data-testid={`sample-gallery-create-${code}`} onClick={() => setCreating(true)}
                disabled={!scopeWritable} title={scopeWritable ? undefined : WRITE_BLOCK_HINT}>
                <Plus size={13} /> Sample {label} Baru
              </button>
            )}
          </div>
        </div>
        <div className="section-body space-y-2.5">
          {meta.notes && <p className="text-[11px] text-[#6B6B73]" data-testid={`sample-gallery-notes-${code}`}>{cleanRndNote(meta.notes)}</p>}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-6" data-testid={`sample-gallery-stats-${code}`}>
            <Kpi label={`Total ${label.toLowerCase()}`} value={stats.total} testId={`sample-gallery-kpi-total-${code}`} />
            <Kpi label="Terkirim" value={stats.sent} tone="#0058CC" testId={`sample-gallery-kpi-sent-${code}`} />
            <Kpi label="Dikerjakan" value={stats.progress} tone="#A05000" testId={`sample-gallery-kpi-progress-${code}`} />
            <Kpi label="Ada ACC" value={stats.acc} tone="#1B7F4B" testId={`sample-gallery-kpi-acc-${code}`} />
            <Kpi label="Pemenang dipilih" value={stats.decided} tone="#1B7F4B" testId={`sample-gallery-kpi-decided-${code}`} />
            <Kpi label="Ronde terlambat" value={stats.overdue} tone="#C62828" testId={`sample-gallery-kpi-overdue-${code}`} />
          </div>
          <OkNotice message={okMsg} onDismiss={() => setOkMsg("")} testId={`sample-gallery-ok-${code}`} />
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-[200px] max-w-sm flex-1">
              <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[#9A9BA3]" />
              <input data-testid={`sample-gallery-search-${code}`} value={f.q} onChange={(e) => set("q", e.target.value)} className="field !pl-8"
                placeholder="Cari nomor / judul / warna / supplier…" />
            </div>
            <LineFilter value={f.line} onChange={(v) => set("line", v)} storageKey={`sample-gallery-${code}`}
              allowed={currentUser?.allowed_line_codes} testId={`sample-gallery-line-filter-${code}`} />
            <button className="secondary-button" style={activeFilters ? { borderColor: tone.fg, color: tone.fg } : undefined}
              onClick={() => setShowFilters((s) => !s)} data-testid={`sample-gallery-toggle-filters-${code}`}>
              <Filter size={13} /> Filter {activeFilters ? `(${activeFilters})` : ""}
            </button>
            {activeFilters > 0 && (
              <button className="text-[11px] underline" style={{ color: tone.fg }} onClick={() => setF({ ...EMPTY, line: f.line })} data-testid={`sample-gallery-reset-filter-${code}`}>
                <X size={10} className="inline" /> reset
              </button>
            )}
          </div>
          {showFilters && (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-6" data-testid={`sample-gallery-filters-${code}`}>
              <div className="col-span-full"><OptionTabs testId={`sample-gallery-filter-status-${code}`} value={f.status} options={STATUS_OPTS} onChange={(v) => set("status", v)}
                countOf={(v) => statusCounts[v || ""] || 0} /></div>
              <KNSelect data-testid={`sample-gallery-filter-supplier-${code}`} className="field" value={f.supplier} searchable
                options={[{ value: "", label: "Semua supplier" }, ...suppliers.map(([id, name]) => ({ value: id, label: name }))]} onValueChange={(v) => set("supplier", v)} />
              <KNSelect data-testid={`sample-gallery-filter-result-${code}`} className="field" value={f.result} options={RESULT_OPTS} onValueChange={(v) => set("result", v)} />
              <KNSelect data-testid={`sample-gallery-filter-score-${code}`} className="field" value={f.score} options={SCORE_OPTS} onValueChange={(v) => set("score", v)} />
              <KNSelect data-testid={`sample-gallery-filter-revision-${code}`} className="field" value={f.revision} options={REVISION_FILTER_OPTIONS} onValueChange={(v) => set("revision", v)} />
              <KNSelect data-testid={`sample-gallery-filter-proof-${code}`} className="field" value={f.proof} options={PROOF_OPTS} onValueChange={(v) => set("proof", v)} />
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
            <div className="py-12 text-center text-[12px] text-[#6B6B73]" data-testid={`sample-gallery-empty-${code}`}>
              <FlaskConical className="mx-auto mb-2 text-gray-300" size={28} />
              {(f.status && activeFilters === 1 && !f.q.trim()) ? (
                <p>Tidak ada sample {label.toLowerCase()} berstatus <b>{statusLabel}</b>.{" "}
                  <button type="button" className="link-button" data-testid={`sample-gallery-show-all-${code}`} onClick={() => set("status", "")}>Tampilkan semua</button></p>
              ) : (activeFilters || f.q.trim()) ? <p>Tidak ada sample {label.toLowerCase()} yang cocok dengan saringan saat ini.{" "}
                  <button type="button" className="link-button" data-testid={`sample-gallery-clear-${code}`} onClick={() => setF({ ...EMPTY, line: f.line })}>Hapus saringan</button></p>
                : <p>Belum ada sample {label.toLowerCase()}. Klik <b>Sample {label} Baru</b> — jenis sudah terpilih, tinggal tulis brief & target.</p>}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4" data-testid={`sample-gallery-grid-${code}`}>
              {filtered.map((s) => <SampleTypeCard key={s.id} s={s} code={code} onOpen={() => setOpenId(s.id)} />)}
            </div>
          )}
        </div>
      </div>

      {creating && (
        <SampleFormModal selectedEntity={selectedEntity} lockType={code} onClose={() => setCreating(false)}
          onSaved={(res) => { setCreating(false); setOkMsg(`Sample ${label} ${res?.number || ""} tersimpan.`); load(); if (res?.id) setOpenId(res.id); }} />
      )}
      {openId && (
        <DetailModal framed onClose={() => setOpenId(null)} label={`Rincian sample ${label}`} testId="sample-detail-modal">
          <SampleDetailPanel sampleId={openId} currentUser={currentUser} types={types} initialType={code}
            onClose={() => setOpenId(null)} onChanged={load} />
        </DetailModal>
      )}
    </div>
  );
}

function Kpi({ label, value, tone = "#1C1C1E", testId }) {
  return (
    <div className="rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] p-2" data-testid={testId}>
      <p className="text-[10.5px] font-bold uppercase text-[#8E8E93]">{label}</p>
      <p className="text-[14px] font-bold tabular-nums leading-tight" style={{ color: tone }}>{value}</p>
    </div>
  );
}
