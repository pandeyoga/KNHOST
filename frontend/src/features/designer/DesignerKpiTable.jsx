/**
 * DesignerKpiTable (PS-18) — tabel kinerja per desainer.
 *
 * Semua kolom lahir dari jejak round yang sudah wajib ber-bukti (lampiran + catatan),
 * jadi TIDAK ada angka yang diisi tangan. Bisa diurutkan supaya pemilik bisa bertanya
 * dari sudut berbeda ("siapa paling sering terlambat?", "siapa paling sering diulang?").
 *
 * Fase 4 · R4 (L-06) — dulu 17 kolom grid (min 1.560 px) yang bergulir ke samping di 1440 px; nama desainer, NILAI
 * & "Rapor PDF" keluar layar. Kini `.data-table` dengan KOLOM PRIORITAS (desainer · ronde · tepat waktu · diulang ·
 * rata skor · versi & nilai desain · nilai) + pemilih **Kolom** untuk kolom tambahan (pilihan diingat per peramban)
 * + tombol **Rincian** per baris → `DetailModal` berisi SEMUA angka desainer itu (tidak ada angka yang hilang).
 * Kolom Desainer beku saat tabel digulir. Aksen ungu kolom Divisi → biru baku (L-08).
 */
import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, Columns3, FileText, ListTree, Users } from "lucide-react";
import DetailModal from "../../components/DetailModal";
import { badPctTone, goodPctTone, gradeMeta, num } from "./designerMeta";
import { actorLabel } from "../../utils/actorLabel";

export const KPI_COLS = [
  { key: "designer", label: "Desainer", core: true, fixed: true },
  { key: "division_name", label: "Divisi", hint: "Divisi R&D (PS-17)", noSort: true },
  { key: "rounds", label: "Ronde", hint: "Jumlah ronde yang ditangani", core: true },
  { key: "acc", label: "ACC", hint: "Ronde yang langsung diterima" },
  { key: "revisi", label: "Revisi", hint: "Diminta perbaikan" },
  { key: "tolak", label: "Tolak", hint: "Hasil ditolak" },
  { key: "late_total", label: "Terlambat", hint: "Disetor melewati tenggat + yang masih menggantung" },
  { key: "on_time_pct", label: "Tepat waktu", hint: "Patuh tenggat SLA", core: true },
  { key: "rework_pct", label: "Diulang", hint: "Revisi + tolak dari yang dinilai", core: true },
  { key: "avg_score", label: "Rata skor", hint: "Skor penilaian manajer", core: true },
  { key: "avg_days", label: "Rata hari", hint: "Lama ronde dari kirim ke setor" },
  { key: "design_versions", label: "Versi desain", hint: "Design Studio: jumlah versi desain yang dibuat pada periode ini", core: true },
  { key: "design_avg_score", label: "Nilai desain", hint: "Design Studio: rata-rata nilai versi (skala 0–2)", core: true },
  { key: "design_acc", label: "ACC desain", hint: "Design Studio: versi yang disetujui (ACC)" },
  { key: "design_revisions", label: "Revisi desain", hint: "Design Studio: berapa kali diminta revisi oleh penilai" },
  { key: "grade_score", label: "Nilai", hint: "Nilai komposit + huruf", core: true },
];
const EXTRA_KEYS = KPI_COLS.filter((c) => !c.core).map((c) => c.key);
const STORE_KEY = "kn.designer-kpi.cols";

function loadExtra() {
  try {
    const v = JSON.parse(window.localStorage.getItem(STORE_KEY) || "[]");
    return Array.isArray(v) ? v.filter((k) => EXTRA_KEYS.includes(k)) : [];
  } catch { return []; }
}
function saveExtra(keys) {
  try { window.localStorage.setItem(STORE_KEY, JSON.stringify(keys)); } catch { /* penyimpanan peramban tak tersedia */ }
}

const designScoreTone = (v) => (v === null || v === undefined ? "#8E8E93" : v >= 1.5 ? "#1B7F4B" : v >= 1 ? "#B26A00" : "#C0392B");
const gradeTitle = (r) => (r.grade_score === null ? "Data belum cukup untuk dinilai"
  : `Nilai dasar ${r.grade_base} − penalti ${r.grade_penalty} = ${r.grade_score} (${r.grade_meaning})`
    + (r.grade_design_pts != null ? ` · nilai desain dikonversi ${r.grade_design_pts}/100` : ""));

/** Isi satu sel — dipakai tabel DAN pop-up rincian (satu sumber, angka sama). */
export function KpiCell({ k, r, tid = true }) {
  const t = (id) => (tid ? id : undefined);   // di pop-up rincian tanpa testid (hindari testid ganda dengan tabel)
  switch (k) {
    case "designer":
      return (
        <span className="font-semibold text-[#1C1C1E]" data-testid={t(`designer-kpi-name-${r.designer}`)}>
          <span className="mr-1 text-[10.5px] text-[#8E8E93]">#{r.rank}</span>{actorLabel(r.designer)}
        </span>
      );
    case "division_name":
      return r.division_name
        ? <span className="inline-block rounded-full bg-[#EAF2FF] px-2 py-0.5 text-[10px] font-semibold text-[#0058CC]" data-testid={t(`designer-kpi-division-${r.designer}`)}>{r.division_name}</span>
        : <span className="text-[10.5px] text-[#B8B9C0]" data-testid={t(`designer-kpi-division-${r.designer}`)}>—</span>;
    case "acc": return <span className="font-bold text-[#1B7F4B]">{r.acc}</span>;
    case "revisi": return <span className="text-[#B26A00]">{r.revisi}</span>;
    case "tolak": return <span className="text-[#C0392B]">{r.tolak}</span>;
    case "late_total":
      return (
        <span className="font-semibold" style={{ color: r.late_total > 0 ? "#C0392B" : "#1B7F4B" }}>
          {r.late_total}
          {r.overdue_now > 0 && <span className="ml-1 text-[9.5px] font-bold text-[#C0392B]">({r.overdue_now} nunggak)</span>}
        </span>
      );
    case "on_time_pct": return <span className="font-semibold" style={{ color: goodPctTone(r.on_time_pct) }}>{num(r.on_time_pct, "%")}</span>;
    case "rework_pct": return <span className="font-semibold" style={{ color: badPctTone(r.rework_pct) }}>{num(r.rework_pct, "%")}</span>;
    case "avg_score": return num(r.avg_score);
    case "avg_days": return num(r.avg_days);
    case "design_versions":
      return (
        <span data-testid={t(`designer-kpi-design-versions-${r.designer}`)}>
          {r.design_versions || 0}
          {r.designs > 0 && <span className="ml-1 text-[9.5px] text-[#9A9BA3]">({r.designs} desain)</span>}
        </span>
      );
    case "design_avg_score":
      return (
        <span className="font-semibold" data-testid={t(`designer-kpi-design-score-${r.designer}`)} style={{ color: designScoreTone(r.design_avg_score) }}>
          {r.design_avg_score === null || r.design_avg_score === undefined ? "—" : `${String(r.design_avg_score).replace(".", ",")}/2`}
        </span>
      );
    case "design_acc": return <span className="font-bold text-[#1B7F4B]">{r.design_acc || 0}</span>;
    case "design_revisions": return <span className="text-[#B26A00]" data-testid={t(`designer-kpi-design-revisions-${r.designer}`)}>{r.design_revisions || 0}</span>;
    case "grade_score": {
      const g = gradeMeta(r.grade_letter);
      return (
        <span className="inline-flex items-center gap-1 whitespace-nowrap" title={gradeTitle(r)}>
          <span className="font-bold" style={{ color: g.tone }}>{num(r.grade_score)}</span>
          <span className={`status-pill ${g.cls}`} data-testid={t(`designer-kpi-grade-${r.designer}`)}>{g.label}</span>
        </span>
      );
    }
    default: return r[k] ?? "—";
  }
}

export default function DesignerKpiTable({ items, onSelect, selected, loading = false,
  onDownloadReport, downloadingReport = "" }) {
  const [sortKey, setSortKey] = useState("grade_score");
  const [asc, setAsc] = useState(false);
  const [extra, setExtra] = useState(loadExtra);
  const [showCols, setShowCols] = useState(false);
  const [detail, setDetail] = useState(null);

  const rows = useMemo(() => {
    const out = [...(items || [])];
    out.sort((a, b) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      if (typeof va === "string" || typeof vb === "string") {
        return String(va || "").localeCompare(String(vb || "")) * (asc ? 1 : -1);
      }
      const na = va === null || va === undefined ? -1 : Number(va);
      const nb = vb === null || vb === undefined ? -1 : Number(vb);
      return (na - nb) * (asc ? 1 : -1);
    });
    return out;
  }, [items, sortKey, asc]);

  // Kolom Divisi hanya ditawarkan bila ada desainer berdivisi (dulu kolom penuh "—").
  const hasDivision = (items || []).some((r) => r.division_name);
  const offered = KPI_COLS.filter((c) => !c.core && (c.key !== "division_name" || hasDivision));
  const cols = KPI_COLS.filter((c) => c.core || (extra.includes(c.key) && offered.some((o) => o.key === c.key)));
  const extraShown = cols.filter((c) => !c.core).length;

  function toggle(key) {
    if (key === sortKey) setAsc(!asc);
    else { setSortKey(key); setAsc(key === "designer"); }
  }
  function toggleCol(key) {
    const next = extra.includes(key) ? extra.filter((k) => k !== key) : [...extra, key];
    setExtra(next); saveExtra(next);
  }

  if (loading) {
    return (
      <div className="space-y-1.5 py-2" data-testid="designer-kpi-table-skeleton">
        <p className="text-[12px] text-[#6B6B73]">Memuat kinerja desainer…</p>
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-7 animate-pulse rounded-md bg-[#F2F3F5]" />
        ))}
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className="py-10 text-center" data-testid="designer-kpi-empty">
        <Users size={26} className="mx-auto mb-2 text-[#C7C9CF]" />
        <p className="text-[13px] font-semibold text-[#3A3B42]">
          Belum ada kinerja desainer pada periode ini
        </p>
        <p className="mt-0.5 text-[12px] text-[#6B6B73]">
          Angka di sini terbentuk sendiri begitu desainer menyetor hasil ronde sample
          (lampiran + catatan wajib) — tidak pernah diisi manual. Coba pilih periode
          yang lebih panjang, atau mulai dari menu R&amp;D &rsaquo; Permintaan Sample.
        </p>
      </div>
    );
  }

  const reportBtn = (r, testId = `designer-kpi-report-${r.designer}`) => {
    const busyReport = downloadingReport === r.designer;
    return (
      <button type="button" data-testid={testId} title={`Unduh rapor PDF ${r.designer}`}
        disabled={busyReport} onClick={(e) => { e.stopPropagation(); onDownloadReport && onDownloadReport(r.designer); }}
        className={`inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-[#D5DBE6] px-1.5 py-0.5 text-[10.5px] font-semibold text-[#0058CC] ${busyReport ? "opacity-60" : "hover:bg-[#F2F7FF]"}`}>
        <FileText size={11} className={busyReport ? "animate-pulse" : ""} />{busyReport ? "Menyiapkan…" : "Rapor PDF"}
      </button>
    );
  };

  return (
    <div className="grid grid-cols-1 gap-2" data-testid="designer-kpi-table">
      {offered.length > 0 && (
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button type="button" className="secondary-button !py-1 text-[11px]" aria-expanded={showCols}
            onClick={() => setShowCols((v) => !v)} data-testid="designer-kpi-columns-toggle">
            <Columns3 size={12} /> Kolom{extraShown ? ` (+${extraShown})` : ""}
          </button>
        </div>
      )}
      {showCols && (
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 rounded-lg border border-[#EFF0F2] bg-[#FAFBFC] px-3 py-2" data-testid="designer-kpi-columns">
          <span className="w-full text-[10.5px] font-semibold text-[#6B6B73]">Kolom tambahan (semua angka tetap ada di Rincian tiap desainer):</span>
          {offered.map((c) => (
            <label key={c.key} className="inline-flex items-center gap-1.5 text-[11.5px]" title={c.hint}>
              <input type="checkbox" checked={extra.includes(c.key)} onChange={() => toggleCol(c.key)} data-testid={`designer-kpi-col-${c.key}`} />
              {c.label}
            </label>
          ))}
        </div>
      )}
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              {cols.map((c) => (
                <th key={c.key} title={c.hint || c.label}
                  className={`${c.key === "designer" ? "sticky left-0 z-[2] bg-[#FAFBFC]" : ""} ${c.key !== "designer" && c.key !== "division_name" ? "text-right" : ""}`.trim() || undefined}>
                  {c.noSort ? c.label : (
                    <button type="button" data-testid={`designer-kpi-sort-${c.key}`} onClick={() => toggle(c.key)}
                      className={`inline-flex items-center gap-0.5 uppercase ${sortKey === c.key ? "text-[#0058CC]" : ""}`}>
                      {c.label}{sortKey === c.key && (asc ? <ArrowUp size={9} /> : <ArrowDown size={9} />)}
                    </button>
                  )}
                </th>
              ))}
              <th className="text-right">Aksi</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const active = selected === r.designer;
              const pick = () => onSelect && onSelect(active ? "" : r.designer);
              return (
                <tr key={r.designer_key || r.designer} tabIndex={0} aria-selected={active}
                  data-testid={`designer-kpi-row-${r.designer}`} onClick={pick}
                  onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); pick(); } }}
                  className={`cursor-pointer text-[11.5px] ${active ? "!bg-[#F2F7FF]" : ""}`}>
                  {cols.map((c) => (
                    <td key={c.key}
                      className={c.key === "designer"
                        ? `sticky left-0 z-[1] max-w-[200px] truncate ${active ? "bg-[#F2F7FF]" : "bg-white"}`
                        : `tabular-nums ${c.key !== "division_name" ? "text-right" : ""}`}>
                      <KpiCell k={c.key} r={r} />
                    </td>
                  ))}
                  <td className="text-right">
                    <span className="inline-flex items-center justify-end gap-1">
                      <button type="button" className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-[#D5DBE6] px-1.5 py-0.5 text-[10.5px] font-semibold text-[#3C3C43] hover:bg-[#F2F5FA]"
                        data-testid={`designer-kpi-detail-${r.designer}`} title={`Semua angka ${actorLabel(r.designer)}`}
                        onClick={(e) => { e.stopPropagation(); setDetail(r); }}>
                        <ListTree size={11} /> Rincian
                      </button>
                      {reportBtn(r)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <DetailModal open={!!detail} onClose={() => setDetail(null)} size="md" framed label="Rincian KPI desainer" testId="designer-kpi-detail">
        {detail && (
          <div className="grid grid-cols-1 gap-3">
            <div className="flex flex-wrap items-start justify-between gap-2 pr-6">
              <div className="min-w-0">
                <p className="kicker">Rincian KPI desainer</p>
                <p className="text-[15px] font-bold text-[#1C1C1E]">{actorLabel(detail.designer)}</p>
              </div>
              {reportBtn(detail, "designer-kpi-detail-report")}
            </div>
            <dl className="grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2" data-testid="designer-kpi-detail-list">
              {KPI_COLS.filter((c) => c.key !== "designer" && (c.key !== "division_name" || hasDivision)).map((c) => (
                <div key={c.key} className="flex items-baseline justify-between gap-3 border-b border-dashed border-[#EFF0F2] py-1 text-[12px]" title={c.hint}>
                  <dt className="text-[#6B6B73]">{c.label}</dt>
                  <dd className="m-0 text-right tabular-nums" data-testid={`designer-kpi-detail-val-${c.key}`}><KpiCell k={c.key} r={detail} tid={false} /></dd>
                </div>
              ))}
            </dl>
          </div>
        )}
      </DetailModal>
    </div>
  );
}
