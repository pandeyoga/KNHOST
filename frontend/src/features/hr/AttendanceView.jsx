import KNDatePicker from "@/components/KNDatePicker";
import apiErrorText from "../../utils/apiError";
import KNPager from "@/components/KNPager";
import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import KNMonthPicker from "@/components/KNMonthPicker";
import KNTimePicker from "@/components/KNTimePicker";
import { Clock, CalendarDays, BarChart3, Upload, CheckCircle2, Plus, FileSpreadsheet, AlertTriangle } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import PageTabs from "../../components/PageTabs";
import { OptionTabs } from "../../components/ListControls";
import useListSearch from "@/hooks/useListSearch";
import ConfirmModal from "../../components/ConfirmModal";
import FormModal from "../../components/FormModal";
import ResponsiveTable from "../../components/ResponsiveTable";
import { MetricRow } from "../../components/ListPageParts";
import { can } from "../../config/roles";

// UAT 24 Okt (audit UI tahap 2) — G5-31: istilah Indonesia ("Perlu ditinjau", "Alpa"; dulu "Perlu Review"/"Alpha").
export const STATUS_PILL = {
  hadir: { cls: "pill-success", label: "Hadir" },
  telat: { cls: "pill-warning", label: "Telat" },
  flagged: { cls: "pill-danger", label: "Perlu ditinjau" },
  izin: { cls: "pill-info", label: "Izin" },
  cuti: { cls: "pill-info", label: "Cuti" },
  alpha: { cls: "pill-danger", label: "Alpa" },
  libur: { cls: "pill-muted", label: "Libur" },
};
const METHOD_LABEL = { geo: "GPS", fingerprint: "Sidik jari", manual: "Manual" };
// UAT 24 Okt (audit UI tahap 2) — G5-04: placeholder multi-baris harus ekspresi JS; string atribut JSX
// menampilkan "\n" mentah.
const CSV_PLACEHOLDER = "user_id,timestamp\n1001,2026-05-04 08:01:00\n1001,2026-05-04 17:05:00";
const STATUS_OPTS = ["hadir", "telat", "izin", "cuti", "alpha", "libur"].map((v) => ({ value: v, label: STATUS_PILL[v]?.label || v }));

export const fmtTime = (iso) => (iso && iso.length >= 16 ? iso.slice(11, 16) : "—");
export const fmtMin = (m) => {
  m = Number(m) || 0;
  if (m <= 0) return "—";
  return m < 60 ? `${m}m` : `${Math.floor(m / 60)}j ${m % 60 ? `${m % 60}m` : ""}`.trim();
};
const todayStr = () => new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 10);
const monthStr = () => new Date(Date.now() + 7 * 3600 * 1000).toISOString().slice(0, 7);

export default function AttendanceView({ currentUser, selectedEntity }) {
  const [tab, setTab] = useState("harian");
  const canManage = can(currentUser?.permissions, "hr", "manage_attendance");   // Sisir gerbang peran (2026-10-20) — endpoint absensi/cuti/lembur/KPI
  const params = useMemo(() => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}), [selectedEntity]);

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  // daily
  const [date, setDate] = useState(todayStr());
  const [statusFilter, setStatusFilter] = useState("");
  const [rows, setRows] = useState([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const PAGE_SIZE = 50;
  const [loadingDaily, setLoadingDaily] = useState(true);
  const [approveTarget, setApproveTarget] = useState(null);

  // recap
  const [month, setMonth] = useState(monthStr());
  const [recap, setRecap] = useState(null);
  const [loadingRecap, setLoadingRecap] = useState(false);

  // employees (for manual)
  const [employees, setEmployees] = useState([]);
  const [showManual, setShowManual] = useState(false);
  const [manual, setManual] = useState({ employee_id: "", date: todayStr(), clock_in: "", clock_out: "", status: "hadir", note: "" });
  const [savingManual, setSavingManual] = useState(false);
  const [manualErr, setManualErr] = useState("");

  // import
  const [csvText, setCsvText] = useState("");
  const [fileName, setFileName] = useState("");
  const [devices, setDevices] = useState([]);
  const [deviceId, setDeviceId] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [importErr, setImportErr] = useState("");

  useEffect(() => { axios.get(`${API}/hr/employees`, { params }).then((r) => setEmployees(Array.isArray(r.data) ? r.data : [])).catch(() => {}); }, [selectedEntity]); // eslint-disable-line
  useEffect(() => { if (tab === "harian") loadDaily(); }, [tab, date, selectedEntity, page]); // eslint-disable-line
  useEffect(() => { if (tab === "rekap") loadRecap(); }, [tab, month, selectedEntity]); // eslint-disable-line
  useEffect(() => { if (tab === "import") axios.get(`${API}/hr/devices`, { params }).then((r) => setDevices(Array.isArray(r.data) ? r.data : [])).catch(() => {}); }, [tab, selectedEntity]); // eslint-disable-line

  async function loadDaily() {
    setLoadingDaily(true);
    try {
      // T-03 Lapis 4 — paginasi server (envelope) supaya ribuan baris tidak dimuat sekaligus.
      const r = await axios.get(`${API}/hr/attendance`, { params: { ...params, date_from: date, date_to: date, page, page_size: PAGE_SIZE } });
      setRows(Array.isArray(r.data?.items) ? r.data.items : []);
      setTotal(Number(r.data?.total || 0));
      setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat kehadiran.")); }
    finally { setLoadingDaily(false); }
  }
  async function loadRecap() {
    setLoadingRecap(true);
    try {
      const r = await axios.get(`${API}/hr/attendance/recap`, { params: { ...params, month } });
      setRecap(r.data || null); setError("");
    } catch (e) { setError(apiErrorText(e, "Gagal memuat rekap.")); }
    finally { setLoadingRecap(false); }
  }

  async function approve(rec) {
    try {
      await axios.patch(`${API}/hr/attendance/${rec.id}`, { data: { approved: true, status: "hadir" } });
      setNotice(`Absen ${rec.employee_name} disetujui.`); setApproveTarget(null); loadDaily();
    } catch (e) { setError(apiErrorText(e, "Gagal menyetujui absen.")); setApproveTarget(null); }
  }

  // UAT 24 Okt (audit UI tahap 2) — G5-31: galat validasi/simpan input manual & impor tampil DI DEKAT form
  // (dulu banner galat global dengan "Coba lagi" yang malah memuat ulang data harian).
  async function submitManual() {
    if (!manual.employee_id) { setManualErr("Pilih karyawan dulu."); return; }
    if (!manual.date) { setManualErr("Isi tanggal dulu."); return; }
    setSavingManual(true); setManualErr("");
    try {
      await axios.post(`${API}/hr/attendance/manual`, manual);
      setNotice("Absen manual tersimpan."); setShowManual(false);
      setManual({ employee_id: "", date: todayStr(), clock_in: "", clock_out: "", status: "hadir", note: "" });
      if (manual.date === date) loadDaily();
    } catch (e) { setManualErr(apiErrorText(e, "Gagal menyimpan absen manual.")); }
    finally { setSavingManual(false); }
  }

  function handleFile(e) {
    const f = e.target.files?.[0]; if (!f) return;
    const r = new FileReader();
    r.onload = () => { setCsvText(String(r.result || "")); setImportResult(null); setImportErr(""); };
    r.readAsText(f); setFileName(f.name);
  }
  async function runImport() {
    if (!csvText.trim()) { setImportErr("Pilih berkas CSV atau tempel data terlebih dahulu."); return; }
    setImporting(true); setImportResult(null); setImportErr("");
    try {
      const body = { csv_text: csvText, device_id: deviceId || "" };
      if (selectedEntity && selectedEntity !== "all") body.entity_id = selectedEntity;
      const r = await axios.post(`${API}/hr/attendance/import`, body);
      setImportResult(r.data); setNotice(`Impor selesai: ${r.data.imported || 0} kehadiran.`);
    } catch (e) { setImportErr(apiErrorText(e, "Gagal mengimpor CSV.")); }
    finally { setImporting(false); }
  }

  const shown = rows.filter((r) => (statusFilter ? r.status === statusFilter : true));
  const srch = useListSearch(shown, (r) => [r.employee_name, r.employee_code, r.shift_name, r.status, r.method],
    { testId: "attendance", placeholder: "Cari karyawan / shift…" });
  const counts = useMemo(() => {
    const c = { total: rows.length, hadir: 0, telat: 0, flagged: 0 };
    rows.forEach((r) => { if (r.status === "hadir") c.hadir++; else if (r.status === "telat") c.telat++; else if (r.status === "flagged") c.flagged++; });
    return c;
  }, [rows]);
  // Hanya karyawan aktif yang bisa diberi absen manual (karyawan keluar/nonaktif tidak ditawarkan).
  const empOpts = employees.filter((e) => (e.status || "active") === "active")
    .map((e) => ({ value: e.id, label: e.code ? `${e.name} (${e.code})` : e.name }));
  const closeManual = () => { if (!savingManual) { setShowManual(false); setManualErr(""); } };
  const lbl = "block text-[10.5px] font-semibold text-[#6B6B73] mb-1";

  return (
    <div data-testid="attendance-view">
      {notice && (<div className="notice-bar success" data-testid="attendance-notice"><span>{notice}</span><button onClick={() => setNotice("")}>×</button></div>)}
      <ErrorNotice message={error} onRetry={tab === "rekap" ? loadRecap : loadDaily} onDismiss={() => setError("")} testId="attendance-error" />

      <div className="section-card mb-3">
        <div className="section-head">
          <div className="flex items-center gap-2"><Clock size={16} className="text-[#0058CC]" /><h2 data-testid="attendance-title">Presensi & Kehadiran</h2></div>
        </div>
        {/* Fase 3 · P6 (L-01) — tab tingkat-2 = PageTabs baku (dulu tombol-toggle `TabBtn` buatan sendiri). */}
        <PageTabs testId="attendance-tabs" value={tab} onChange={setTab} ariaLabel="Presensi" className="!mb-0 px-3"
          tabs={[
            { key: "harian", label: "Kehadiran Harian", icon: CalendarDays, testId: "attendance-tab-harian" },
            { key: "rekap", label: "Rekap Periode", icon: BarChart3, testId: "attendance-tab-rekap" },
            { key: "import", label: "Impor Sidik Jari", icon: Upload, testId: "attendance-tab-import", hidden: !canManage },
          ]} />
      </div>

      {tab === "harian" && (
        <>
          {/* Fase 4 · R4 (L-07/L-08) — KPI = MetricRow baku (nilai 0 netral). */}
          <div className="mb-3"><MetricRow testId="attendance-stats" items={[
            { label: "Total Hari Ini", value: loadingDaily ? "—" : String(total || counts.total) },
            { label: "Hadir", value: loadingDaily ? "—" : String(counts.hadir), tone: "#1F9D55" },
            { label: "Telat", value: loadingDaily ? "—" : String(counts.telat), tone: "#B7791F" },
            { label: "Perlu ditinjau", value: loadingDaily ? "—" : String(counts.flagged), tone: "#C0392B" },
          ]} /></div>
          <KNPager page={page} pageSize={PAGE_SIZE} total={total} onChange={setPage} testId="attendance-pager" />
          <div className="section-card mb-3">
            {/* Fase 4 · R4 — grid berkolom eksplisit di HP (dulu `md:grid-cols-[…]` tanpa kolom dasar + sel kosong). */}
            <div className="section-body grid grid-cols-1 items-end gap-2 md:grid-cols-[200px_minmax(0,1fr)]">
              <div>
                <label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Tanggal</label>
                <KNDatePicker data-testid="attendance-date" value={date} onChange={(v) => setDate(v || date)} clearable={false} />
              </div>
              {canManage ? (
                <div className="flex items-end md:justify-end">
                  <button data-testid="attendance-manual-button" onClick={() => { setShowManual(true); setManualErr(""); setManual((m) => ({ ...m, date })); }} className="primary-button"><Plus size={13} /> Input manual</button>
                </div>
              ) : <span className="hidden md:block" />}
              <div className="min-w-0 md:col-span-full">
                <OptionTabs testId="attendance-status-filter" value={statusFilter} onChange={setStatusFilter}
                  countOf={(v) => (v === "flagged" ? undefined : rows.filter((r) => !v || r.status === v).length)}
                  options={[{ value: "", label: "Semua Status" }, ...STATUS_OPTS, { value: "flagged", label: "Perlu ditinjau" }]} />
              </div>
            </div>
          </div>
          {/* UAT 24 Okt (audit UI tahap 2) — G5-31: input manual sebagai pop-up standar berlabel (dulu 5 isian
              tanpa label menempel di kartu filter, tanggal/jam terpotong, tanpa Batal). */}
          <FormModal open={showManual && canManage} onClose={closeManual} title="Input Absen Manual"
            subtitle="Catat kehadiran karyawan yang tidak terekam GPS/mesin sidik jari." icon={Clock} size="sm"
            testId="attendance-manual-panel" submitTestId="manual-save" onSubmit={submitManual} submitLabel="Simpan absen"
            busy={savingManual} error={manualErr} submitDisabled={!manual.employee_id || !manual.date}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="sm:col-span-2"><label className={lbl}>Karyawan *</label>
                <KNSelect data-testid="manual-employee" value={manual.employee_id} onValueChange={(v) => { setManual((m) => ({ ...m, employee_id: v })); setManualErr(""); }} className="field" placeholder="Pilih karyawan aktif" searchable options={empOpts} /></div>
              <div><label className={lbl}>Tanggal *</label>
                <KNDatePicker data-testid="manual-date" value={manual.date} onChange={(v) => setManual((m) => ({ ...m, date: v }))} /></div>
              <div><label className={lbl}>Status *</label>
                <KNSelect data-testid="manual-status" value={manual.status} onValueChange={(v) => setManual((m) => ({ ...m, status: v }))} className="field" options={STATUS_OPTS} /></div>
              <div><label className={lbl}>Jam masuk (opsional)</label>
                <KNTimePicker data-testid="manual-in" placeholder="Pilih jam" value={manual.clock_in} onChange={(v) => setManual((m) => ({ ...m, clock_in: v }))} /></div>
              <div><label className={lbl}>Jam keluar (opsional)</label>
                <KNTimePicker data-testid="manual-out" placeholder="Pilih jam" value={manual.clock_out} onChange={(v) => setManual((m) => ({ ...m, clock_out: v }))} /></div>
            </div>
          </FormModal>

          <div className="section-card">
            {srch.toolbar}
            {/* Fase 4 · R4 (L-07) — `.data-table` lewat ResponsiveTable (dulu tabel grid 9 kolom min 920 px buatan
                sendiri); di HP kartu per karyawan, tanpa gulir samping. */}
            <ResponsiveTable testId="attendance-table" rows={srch.pageRows} rowKey="id" loading={loadingDaily}
              rowTestId={(r) => `attendance-row-${r.id}`}
              empty={<div className="py-8" data-testid="attendance-empty"><CalendarDays className="mx-auto mb-2 text-gray-300" size={28} /><p>{srch.shown.length === 0 && rows.length > 0 ? "Tidak ada kehadiran yang cocok dengan saringan." : "Belum ada kehadiran pada tanggal ini."}</p></div>}
              columns={[
                { key: "employee_name", header: "Karyawan", mobile: "title", render: (r) => <span className="inline-flex min-w-0 items-center gap-1"><EntityBadge entityId={r.entity_id} /><span className="truncate font-semibold">{r.employee_name}</span></span> },
                { key: "status", header: "Status", mobile: "badge", render: (r) => { const pill = STATUS_PILL[r.status] || STATUS_PILL.hadir; return <span data-testid={`attendance-status-${r.id}`} className={`status-pill ${pill.cls}`}>{pill.label}</span>; } },
                { key: "shift_name", header: "Shift", mobile: "subtitle", render: (r) => <span className="text-[#6B6B73]">{r.shift_name || "—"}</span> },
                { key: "clock_in", header: "Masuk", priority: 1, render: (r) => <span className="tabular-nums">{fmtTime(r.clock_in)}</span> },
                { key: "clock_out", header: "Keluar", priority: 2, render: (r) => <span className="tabular-nums">{fmtTime(r.clock_out)}</span> },
                { key: "late_min", header: "Telat", priority: 3, render: (r) => <span className="tabular-nums" style={{ color: r.late_min > 0 ? "#B7791F" : "#9A9BA3" }}>{fmtMin(r.late_min)}</span> },
                { key: "work_min", header: "Kerja", priority: 4, render: (r) => <span className="tabular-nums">{fmtMin(r.work_min)}</span> },
                { key: "method", header: "Metode", priority: 5, render: (r) => METHOD_LABEL[r.method] || r.method },
              ]}
              actions={canManage ? (r) => (r.status === "flagged" ? (
                <button data-testid={`approve-attendance-${r.id}`} onClick={() => setApproveTarget(r)} className="icon-button text-[#1F9D55]" title="Setujui" aria-label={`Setujui absen ${r.employee_name}`}><CheckCircle2 size={15} /></button>
              ) : null) : undefined} />
          </div>
        </>
      )}

      {tab === "rekap" && (
        <>
          <div className="section-card mb-3"><div className="section-body flex items-end gap-2">
            <div><label className="block text-[10.5px] font-semibold text-[#6B6B73] mb-1">Periode (Bulan)</label>
              <div className="w-[190px]"><KNMonthPicker data-testid="recap-month" value={month} onChange={setMonth} /></div></div>
          </div></div>
          {loadingRecap ? (
            <div className="section-card py-10 text-center text-[12px] text-[#6B6B73]" data-testid="recap-loading">Memuat rekap...</div>
          ) : (
            <>
              <div className="mb-3"><MetricRow testId="recap-stats" items={[
                { label: "Karyawan", value: String(recap?.totals?.employees ?? 0) },
                { label: "Total Hadir (hari)", value: String(recap?.totals?.present_days ?? 0), tone: "#1F9D55" },
                { label: "Total Telat (hari)", value: String(recap?.totals?.late_days ?? 0), tone: "#B7791F" },
                { label: "Total Lembur", value: fmtMin(recap?.totals?.total_overtime_min), tone: "#0058CC" },
              ]} /></div>
              <div className="section-card">
                {/* Fase 4 · R4 (L-07) — `.data-table` lewat ResponsiveTable (dulu tabel grid min 680 px). */}
                <ResponsiveTable testId="recap-table" rows={recap?.rows || []} rowKey="employee_id"
                  rowTestId={(r) => `recap-row-${r.employee_id}`}
                  empty={<div className="py-8" data-testid="recap-empty"><BarChart3 className="mx-auto mb-2 text-gray-300" size={28} /><p>Belum ada data kehadiran pada periode ini.</p></div>}
                  columns={[
                    { key: "employee_name", header: "Nama", mobile: "title", render: (r) => <span className="font-semibold">{r.employee_name}</span> },
                    { key: "code", header: "Kode", mobile: "subtitle", render: (r) => <span className="font-bold text-[#0058CC]">{r.code || "—"}</span> },
                    { key: "department_name", header: "Departemen", priority: 5, render: (r) => <span className="text-[#6B6B73]">{r.department_name || "—"}</span> },
                    { key: "present_days", header: "Hadir", align: "right", priority: 1, render: (r) => <span className="tabular-nums">{r.present_days}</span> },
                    { key: "late_days", header: "Telat", align: "right", priority: 2, render: (r) => <span className="tabular-nums" style={{ color: r.late_days ? "#B7791F" : "#9A9BA3" }}>{r.late_days}</span> },
                    { key: "flagged_days", header: "Ditinjau", align: "right", priority: 3, render: (r) => <span className="tabular-nums" style={{ color: r.flagged_days ? "#C0392B" : "#9A9BA3" }}>{r.flagged_days}</span> },
                    { key: "total_overtime_min", header: "Lembur", align: "right", priority: 4, render: (r) => <span className="tabular-nums">{fmtMin(r.total_overtime_min)}</span> },
                  ]} />
              </div>
            </>
          )}
        </>
      )}

      {tab === "import" && canManage && (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.3fr_1fr]">
          <div className="section-card">
            <div className="section-head"><div className="flex items-center gap-2"><FileSpreadsheet size={15} className="text-[#0058CC]" /><h2>Impor Log Mesin Sidik Jari (ZKTeco)</h2></div></div>
            <div className="section-body space-y-3">
              <div>
                <label className={lbl}>Berkas CSV</label>
                {/* G5-31: input berkas bawaan ("Choose File") disembunyikan; tombol berlabel Indonesia. */}
                <label className="secondary-button inline-flex cursor-pointer items-center gap-1.5" data-testid="import-file-button">
                  <Upload size={13} /> Pilih berkas CSV
                  <input data-testid="import-file" type="file" accept=".csv,text/csv" onChange={handleFile} className="sr-only" />
                </label>
                <p className="text-[11px] text-[#6B6B73] mt-1">{fileName || "Belum ada berkas dipilih."}</p>
              </div>
              <div>
                <label className={lbl}>atau tempel data CSV</label>
                <textarea data-testid="import-textarea" value={csvText} onChange={(e) => { setCsvText(e.target.value); setImportResult(null); setImportErr(""); }} rows="6" className="field font-mono text-[11px]" placeholder={CSV_PLACEHOLDER} />
              </div>
              <div className="grid grid-cols-[1fr_auto] gap-2 items-end">
                <div><label className={lbl}>Perangkat (opsional)</label>
                  <KNSelect data-testid="import-device" value={deviceId} onValueChange={setDeviceId} className="field" placeholder="— tanpa perangkat —"
                    options={[{ value: "", label: "— tanpa perangkat —" }, ...devices.map((d) => ({ value: d.id, label: d.name }))]} /></div>
                <button data-testid="import-run" disabled={importing || !csvText.trim()} onClick={runImport} className="primary-button justify-center"
                  title={!csvText.trim() ? "Pilih berkas CSV atau tempel data dulu" : undefined}><Upload size={13} /> {importing ? "Mengimpor..." : "Impor"}</button>
              </div>
              {importErr && <p data-testid="import-error" className="rounded-md border border-[#FCA5A5] bg-[#FEF2F2] px-2.5 py-1.5 text-[11.5px] font-semibold text-[#B91C1C]">{importErr}</p>}
            </div>
          </div>
          <div className="space-y-3">
            <div className="section-card"><div className="section-body text-[11.5px] text-[#6B6B73] space-y-1">
              <p className="font-semibold text-[#1A1A1F]">Format kolom CSV:</p>
              <p><code className="text-[#0058CC]">user_id</code> = ID enroll mesin (cocok dgn <em>ID Mesin Fingerprint</em> karyawan).</p>
              <p><code className="text-[#0058CC]">timestamp</code> = <code>YYYY-MM-DD HH:MM:SS</code>. Beberapa kali pindai dalam sehari otomatis digabung (masuk = pindai pertama, keluar = pindai terakhir).</p>
              <p className="flex items-start gap-1"><AlertTriangle size={13} className="text-[#B7791F] mt-0.5" /> Aman diimpor ulang: data yang sama tidak digandakan.</p>
            </div></div>
            {importResult && (
              <div className="section-card" data-testid="import-result"><div className="section-body">
                <p className="text-[12px] font-bold mb-2">Hasil Impor</p>
                <div className="mb-2"><MetricRow testId="import-stats" items={[
                  { label: "Kehadiran terbentuk", value: String(importResult.imported || 0), tone: "#1F9D55" },
                  { label: "Baris dilewati", value: String(importResult.skipped_rows || 0), tone: "#B7791F" },
                ]} /></div>
                {importResult.message && <p className="text-[11.5px] text-[#B7791F]">{importResult.message}</p>}
                <div className="divide-y divide-[#EFF0F2] max-h-[200px] overflow-y-auto">
                  {(importResult.records || []).map((r, i) => (
                    <div key={i} className="flex items-center justify-between py-1.5 text-[11.5px]"><span className="truncate">{r.employee_name} · {r.date}</span><span className="text-[#6B6B73]">{r.punches}× pindai · {STATUS_PILL[r.status]?.label || r.status}</span></div>
                  ))}
                </div>
              </div></div>
            )}
          </div>
        </div>
      )}

      <ConfirmModal open={!!approveTarget} title={`Setujui Absen · ${approveTarget?.employee_name || ""}`}
        message="Absen di luar geofence ini akan disetujui dan ditandai Hadir." confirmLabel="Setujui"
        onConfirm={() => approve(approveTarget)} onCancel={() => setApproveTarget(null)} testId="approve-attendance-modal" />
    </div>
  );
}
