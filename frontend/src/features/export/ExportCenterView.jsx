import { useEffect, useMemo, useState } from "react";
import { FileSpreadsheet, Eye, FileDown, Info } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import KNSelect from "../../components/KNSelect";
import KNDatePicker from "../../components/KNDatePicker";
import DatasetPicker from "./DatasetPicker";
import ColumnPicker from "./ColumnPicker";
import FilterGroup, { emptyGroup } from "./FilterBuilder";
import PreviewTable from "./PreviewTable";
import JobsPanel from "./JobsPanel";
import CoveragePanel from "./CoveragePanel";
import TemplatesPanel from "./TemplatesPanel";

const errText = (e) => {
  const d = e.response?.data?.detail;
  if (d && typeof d === "object") return d.fields?.length ? `${d.message}: ${d.fields.join(", ")}` : d.message;
  return d || e.message;
};

function Step({ n, title, children, right }) {
  return (
    <section className="rounded-xl border border-[#EFF0F2] bg-white p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="h-5 w-5 rounded-full bg-[#1C1C1E] text-white text-[11px] font-bold grid place-items-center">{n}</span>
        <h3 className="text-[13px] font-bold text-[#1C1C1E]">{title}</h3>
        <span className="ml-auto">{right}</span>
      </div>
      {children}
    </section>
  );
}

function PeriodStep({ ds, spec, set }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="w-60"><KNSelect data-testid="export-date-field" value={spec.date_field || ""} searchable={false}
        options={[{ value: "", label: "Semua tanggal" }, ...ds.date_fields.map((d) => ({ value: d.key, label: d.label }))]}
        onValueChange={(v) => set({ date_field: v })} /></div>
      {spec.date_field && <>
        <KNDatePicker data-testid="export-date-from" value={spec.date_from} onChange={(v) => set({ date_from: v || "" })} placeholder="Dari" />
        <span className="text-[12px] text-[#6B6B73]">s/d</span>
        <KNDatePicker data-testid="export-date-to" value={spec.date_to} onChange={(v) => set({ date_to: v || "" })} placeholder="Sampai" />
        <span className="text-[11px] text-[#8E8E93]">Inklusif, zona WIB</span>
      </>}
    </div>
  );
}

function SortStep({ cols, spec, set }) {
  const s = spec.sort[0] || { key: "", dir: "asc" };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="w-60"><KNSelect data-testid="export-sort-key" value={s.key}
        options={[{ value: "", label: "Bawaan (kunci dataset)" }, ...cols.map((c) => ({ value: c.key, label: c.label }))]}
        onValueChange={(v) => set({ sort: v ? [{ key: v, dir: s.dir }] : [] })} /></div>
      {s.key && <div className="w-40"><KNSelect data-testid="export-sort-dir" value={s.dir} searchable={false}
        options={[{ value: "asc", label: "Naik (A→Z, kecil→besar)" }, { value: "desc", label: "Turun" }]}
        onValueChange={(v) => set({ sort: [{ key: s.key, dir: v }] })} /></div>}
    </div>
  );
}

// Kondisi tanpa nilai belum lengkap → tidak dikirim (kecuali pembanding kosong/tidak kosong).
function cleanFilter(node) {
  if (!node) return null;
  if (node.items) {
    const items = node.items.map(cleanFilter).filter(Boolean);
    return items.length ? { ...node, items } : null;
  }
  const noValue = ["empty", "not_empty"].includes(node.cmp);
  return noValue || String(node.value ?? "").trim() !== "" ? node : null;
}

const freshSpec = (ds) => ({
  dataset: ds.id, columns: ds.columns.filter((c) => c.source === "base").map((c) => c.key),
  filter: emptyGroup(), date_field: "", date_from: "", date_to: "", sort: [], group_by: [],
});

function GroupStep({ ds, cols, spec, set }) {
  const opts = cols.filter((c) => !["number", "money"].includes(c.type));
  const g = spec.group_by?.[0] || "";
  const sumLabel = (ds.summary_by || []).map((k) => ds.columns.find((c) => c.key === k)?.label || k).join(", ");
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <div className="w-60"><KNSelect data-testid="export-group-by" value={g}
          options={[{ value: "", label: "Tanpa ringkasan (detail per baris)" }, ...opts.map((c) => ({ value: c.key, label: c.label }))]}
          onValueChange={(v) => set({ group_by: v ? [v] : [] })} /></div>
        <span className="text-[11.5px] text-[#8E8E93]">Angka dijumlah per kelompok dari grain yang sama — tidak ada perkalian baris.</span>
      </div>
      {sumLabel && !g && (
        <p data-testid="export-report-note" className="text-[11.5px] text-[#0058CC]">
          Rapor: file XLSX berisi detail + sheet “Ringkasan per {sumLabel}” dari filter & periode yang sama.
        </p>
      )}
    </div>
  );
}

export default function ExportCenterView({ selectedEntity }) {
  const [meta, setMeta] = useState(null);
  const [tab, setTab] = useState("builder");
  const [spec, setSpec] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");
  const [rowsPerSheet, setRowsPerSheet] = useState(1000000);
  const [jobsKey, setJobsKey] = useState(0);
  const [tplName, setTplName] = useState("");
  const [tplKey, setTplKey] = useState(0);

  useEffect(() => {
    axios.get(`${API}/export-center/datasets`).then((r) => {
      setMeta(r.data);
      if (r.data.datasets[0]) setSpec(freshSpec(r.data.datasets[0]));
    }).catch((e) => setError(errText(e)));
  }, [selectedEntity]);

  const ds = useMemo(() => meta?.datasets.find((d) => d.id === spec?.dataset), [meta, spec]);
  const baseCols = useMemo(() => (ds ? ds.columns.filter((c) => c.filterable) : []), [ds]);
  const set = (patch) => { setSpec((s) => ({ ...s, ...patch })); setPreview(null); };
  const body = () => ({ ...spec, filter: cleanFilter(spec.filter), entity_scope: selectedEntity === "all" ? "all" : "active" });

  const runPreview = async () => {
    setBusy("preview"); setError(null);
    try { setPreview((await axios.post(`${API}/export-center/preview`, body())).data); } catch (e) { setError(errText(e)); }
    setBusy("");
  };
  const runExport = async (format) => {
    setBusy(format); setError(null); setNotice("");
    try {
      const r = await axios.post(`${API}/export-center/jobs`, { ...body(), format, rows_per_sheet: Number(rowsPerSheet) || 1000000 });
      setNotice(`Export ${format.toUpperCase()} ${r.data.total_rows.toLocaleString("id-ID")} baris sedang diproses — lihat tab Pekerjaan.`);
      setJobsKey((k) => k + 1);
    } catch (e) { setError(errText(e)); }
    setBusy("");
  };

  const saveTemplate = async (format) => {
    setBusy("tpl"); setError(null); setNotice("");
    try {
      const r = await axios.post(`${API}/export-center/templates`, { name: tplName, spec: body(), format,
                                                                      rows_per_sheet: Number(rowsPerSheet) || 1000000 });
      setNotice(`Template “${r.data.name}” tersimpan — jalankan dari tab Template.`);
      setTplName(""); setTplKey((k) => k + 1);
    } catch (e) { setError(errText(e)); }
    setBusy("");
  };
  const useTemplate = (t) => {
    const d = meta.datasets.find((x) => x.id === t.dataset);
    if (!d) { setError("Dataset template tidak tersedia untuk peran Anda."); return; }
    setSpec({ ...freshSpec(d), ...t.spec, filter: t.spec.filter || emptyGroup() });
    setPreview(null); setTab("builder");
  };

  return (
    <div data-testid="export-center-view" className="space-y-4">
      <div>
        <p className="text-[12px] font-semibold text-[#0058CC] tracking-wide">LAPORAN</p>
        <h1 className="text-[20px] font-bold text-[#1C1C1E] flex items-center gap-2"><FileSpreadsheet size={20} className="text-[#0058CC]" /> Pusat Export</h1>
        <p className="text-[12px] text-[#6B6B73] mt-0.5">Pilih dataset → kolom → periode → filter → pratinjau → unduh. Isi mengikuti hak akses, badan usaha, dan lokasi Anda.</p>
      </div>
      <div className="flex gap-1.5">
        {[["builder", "Buat export"], ["templates", "Template"], ["jobs", "Pekerjaan"], ["coverage", "Cakupan data"]].map(([id, label]) => (
          <button key={id} type="button" data-testid={`export-tab-${id}`} onClick={() => setTab(id)}
                  className={`px-3.5 py-1.5 rounded-full text-[12.5px] font-semibold border ${tab === id ? "bg-[#1C1C1E] text-white border-[#1C1C1E]" : "bg-white text-[#3A3A3C] border-[#E5E5EA]"}`}>{label}</button>
        ))}
      </div>
      {error && <ErrorNotice message={error} onDismiss={() => setError(null)} testId="export-error" />}
      {notice && <p data-testid="export-notice" className="rounded-lg bg-[#34C759]/10 text-[#1E7B3A] text-[12.5px] px-3 py-2">{notice}</p>}
      {tab === "jobs" && <JobsPanel refreshKey={jobsKey} />}
      {tab === "coverage" && <CoveragePanel />}
      {tab === "templates" && meta && <TemplatesPanel refreshKey={tplKey} onUse={useTemplate} onRan={() => setJobsKey((k) => k + 1)} />}
      {tab === "builder" && meta && (
        <div className="grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-4 items-start">
          <DatasetPicker datasets={meta.datasets} unavailable={meta.unavailable} value={spec?.dataset}
                         onChange={(id) => { setSpec(freshSpec(meta.datasets.find((d) => d.id === id))); setPreview(null); }} />
          {ds && spec && (
            <div className="space-y-3 min-w-0">
              <p data-testid="export-dataset-grain" className="flex items-center gap-1.5 text-[12px] text-[#6B6B73]"><Info size={13} /> {ds.label} · {ds.grain}</p>
              <Step n="1" title="Kolom"><ColumnPicker dataset={ds} selected={spec.columns} onChange={(columns) => set({ columns })} /></Step>
              <Step n="2" title="Periode"><PeriodStep ds={ds} spec={spec} set={set} /></Step>
              <Step n="3" title="Filter">
                <FilterGroup node={spec.filter} cols={baseCols} labels={meta.comparators} onChange={(filter) => set({ filter })} />
              </Step>
              <Step n="4" title="Urutan"><SortStep cols={baseCols} spec={spec} set={set} /></Step>
              <Step n="5" title="Ringkasan (opsional)"><GroupStep ds={ds} cols={baseCols} spec={spec} set={set} /></Step>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" data-testid="export-preview-button" onClick={runPreview} disabled={!!busy || !spec.columns.length}
                        className="inline-flex items-center gap-1.5 rounded-full border border-[#1C1C1E] px-4 py-2 text-[12.5px] font-semibold disabled:opacity-50"><Eye size={14} /> {busy === "preview" ? "Memuat…" : "Pratinjau"}</button>
                <button type="button" data-testid="export-xlsx-button" onClick={() => runExport("xlsx")} disabled={!!busy || !spec.columns.length}
                        className="inline-flex items-center gap-1.5 rounded-full bg-[#0058CC] text-white px-4 py-2 text-[12.5px] font-semibold disabled:opacity-50"><FileDown size={14} /> Export XLSX</button>
                <button type="button" data-testid="export-csv-button" onClick={() => runExport("csv")} disabled={!!busy || !spec.columns.length}
                        className="inline-flex items-center gap-1.5 rounded-full bg-[#1C1C1E] text-white px-4 py-2 text-[12.5px] font-semibold disabled:opacity-50"><FileDown size={14} /> Export CSV</button>
                <label className="ml-auto flex items-center gap-1.5 text-[11.5px] text-[#6B6B73]">Baris per sheet XLSX
                  <input data-testid="export-rows-per-sheet" type="number" min={100} max={1000000} value={rowsPerSheet}
                         onChange={(e) => setRowsPerSheet(e.target.value)} className="field w-28 text-[12px]" />
                </label>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input data-testid="export-template-name" value={tplName} onChange={(e) => setTplName(e.target.value)}
                       placeholder="Nama template (mis. Omzet bulanan per pelanggan)" className="field w-80 text-[12.5px]" />
                <button type="button" data-testid="export-template-save" onClick={() => saveTemplate("xlsx")}
                        disabled={!!busy || tplName.trim().length < 3 || !spec.columns.length}
                        className="rounded-full border border-[#0058CC] text-[#0058CC] px-4 py-1.5 text-[12.5px] font-semibold disabled:opacity-50">Simpan template</button>
              </div>
              {preview && <Step n="6" title="Pratinjau"><PreviewTable data={preview} /></Step>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
