import { useEffect, useMemo, useState } from "react";
import apiErrorText from "../../utils/apiError";
import axios, { API } from "../../services/apiClient";
import { Target, Plus, Pencil, Trash2, RefreshCw, BarChart3 } from "lucide-react";
import KNSelect from "../../components/KNSelect";
import ErrorNotice from "../../components/ErrorNotice";
import ConfirmModal from "../../components/ConfirmModal";
import FormModal from "../../components/FormModal";
import ResponsiveTable from "../../components/ResponsiveTable";
import { MetricRow } from "../../components/ListPageParts";
import { formatDecimal, formatPeriod } from "../../utils/formatters";
import { activeEmployees } from "./leaveUtils";
import { lastMonths, curMonth, scoreCls, scoreBadge, weightedAvg, isCalendarMonth } from "./kpiUtils";
import { can } from "../../config/roles";

// FASE H5 — KPI Design (input KPI manual per karyawan/periode + rekap). Keputusan 2a.
export default function KpiView({ currentUser, selectedEntity }) {
  const canManage = can(currentUser?.permissions, "hr", "manage_attendance");   // Sisir gerbang peran (2026-10-20) — endpoint absensi/cuti/lembur/KPI
  const [rows, setRows] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [period, setPeriod] = useState(curMonth());
  const [empFilter, setEmpFilter] = useState("");
  // modal
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(blankForm());
  const [busy, setBusy] = useState(false);
  const [fErr, setFErr] = useState("");
  const [delTarget, setDelTarget] = useState(null);

  const params = useMemo(
    () => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}),
    [selectedEntity]
  );

  useEffect(() => { loadEmployees(); }, [selectedEntity]); // eslint-disable-line
  useEffect(() => { load(); }, [period, empFilter, selectedEntity]); // eslint-disable-line

  // UAT 24 Okt (audit UI tahap 2) — G5-35: galat muat karyawan ditampilkan (dulu `catch (_) { /* noop */ }` →
  // pemilih karyawan diam-diam kosong).
  async function loadEmployees() {
    try {
      const r = await axios.get(`${API}/hr/employees`, { params });
      setEmployees(Array.isArray(r.data) ? r.data : []);
    } catch (e) { setError(apiErrorText(e, "Gagal memuat daftar karyawan — pemilih karyawan kosong.")); }
  }
  async function load() {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/hr/kpi`, {
        params: { ...params, ...(period ? { period } : {}), ...(empFilter ? { employee_id: empFilter } : {}) },
      });
      setRows(Array.isArray(r.data) ? r.data : []);
      setError("");
    } catch (e) {
      setError(apiErrorText(e, "Gagal memuat data KPI."));
    } finally {
      setLoading(false);
    }
  }

  function blankForm() {
    return { employee_id: "", period: curMonth(), metric: "", target: "", actual: "", score: "", weight: "1", note: "" };
  }
  function openCreate() { setEditing(null); setForm(blankForm()); setFErr(""); setOpen(true); }
  function openEdit(r) {
    setEditing(r);
    setForm({ employee_id: r.employee_id, period: r.period, metric: r.metric, target: String(r.target ?? ""), actual: String(r.actual ?? ""), score: "", weight: String(r.weight ?? "1"), note: r.note || "" });
    setFErr(""); setOpen(true);
  }

  async function save() {
    if (!editing && !form.employee_id) { setFErr("Pilih karyawan."); return; }
    if (!form.metric.trim()) { setFErr("Nama metrik wajib diisi."); return; }
    if (!isCalendarMonth(form.period)) { setFErr("Periode harus bulan kalender YYYY-MM (01–12)."); return; }
    setBusy(true); setFErr("");
    const payload = {
      period: form.period, metric: form.metric.trim(),
      target: parseFloat(form.target) || 0, actual: parseFloat(form.actual) || 0,
      weight: form.weight === "" ? 1 : parseFloat(form.weight), note: form.note,
    };
    if (form.score !== "" && !Number.isNaN(parseFloat(form.score))) payload.score = parseFloat(form.score);
    try {
      if (editing) await axios.put(`${API}/hr/kpi/${editing.id}`, payload);
      else await axios.post(`${API}/hr/kpi`, { ...payload, employee_id: form.employee_id });
      setOpen(false); await load();
    } catch (e) {
      setFErr(apiErrorText(e, "Gagal menyimpan KPI."));
    } finally { setBusy(false); }
  }
  async function doDelete(r) {
    try { await axios.delete(`${API}/hr/kpi/${r.id}`); await load(); }
    catch (e) { setError(apiErrorText(e, "Gagal menghapus KPI.")); }
    finally { setDelTarget(null); }
  }

  const periodOpts = lastMonths(12).map((m) => ({ value: m, label: formatPeriod(m) }));
  const empOpts = [{ value: "", label: "Semua Karyawan" }, ...employees.map((e) => ({ value: e.id, label: e.name }))];
  const avg = weightedAvg(rows);

  return (
    <div className="grid grid-cols-1 gap-3" data-testid="kpi-view">
      {/* Toolbar */}
      <section className="section-card !p-3">
        <div className="flex flex-wrap items-end gap-2.5">
          <div className="grid gap-1">
            <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Periode</label>
            <KNSelect data-testid="kpi-period-filter" value={period} onValueChange={setPeriod} options={periodOpts} className="field !w-[150px]" />
          </div>
          <div className="grid gap-1">
            <label className="text-[11px] font-bold uppercase text-[#6B6B73]">Karyawan</label>
            <KNSelect data-testid="kpi-emp-filter" value={empFilter} onValueChange={setEmpFilter} options={empOpts} className="field !w-[220px]" placeholder="Semua Karyawan" />
          </div>
          <button data-testid="kpi-refresh-button" className="secondary-button" onClick={load}><RefreshCw size={13} /> Muat ulang</button>
          <div className="ml-auto flex items-end gap-2">
            {canManage && (
              <button data-testid="kpi-add-button" className="primary-button" onClick={openCreate}><Plus size={14} /> Tambah KPI</button>
            )}
          </div>
        </div>
      </section>

      {/* Rekap — Fase 4 · R4 (L-08): MetricRow baku (nilai 0 netral; dulu "Rata-rata skor 0" merah saat memuat). */}
      <MetricRow testId="kpi-recap" items={[
        { label: "Total Entri KPI", icon: BarChart3, value: loading ? "—" : String(rows.length) },
        // Audit UI 24 Okt (084): desimal koma + keterangan skala (skor > 100 = aktual melampaui target).
        { label: "Rata-rata Skor (tertimbang)", icon: Target, testId: "kpi-recap-avg",
          value: loading || avg == null ? "—" : Number(avg).toLocaleString("id-ID", { maximumFractionDigits: 1 }),
          tone: loading || avg == null ? undefined : scoreTone(avg), hint: "skala 100 = sesuai target; > 100 = melampaui target" },
        { label: "Periode Aktif", icon: Target, value: period ? formatPeriod(period) : "—" },
      ]} />

      {error && <ErrorNotice message={error} onRetry={load} testId="kpi-error" />}

      {/* Tabel — Fase 4 · R4 (L-07): `.data-table` lewat ResponsiveTable (dulu <table> mentah 12,5 px); kartu di HP. */}
      <section className="section-card">
        <div className="section-head"><h2 className="text-[13px] font-bold">Daftar KPI</h2></div>
        <div className="section-body">
          {rows.length === 0 && !loading ? (
            <div className="py-10 text-center" data-testid="kpi-empty">
              <Target size={28} className="mx-auto text-[#C7C9CF] mb-2" />
              <p className="text-[13px] font-semibold text-[#3A3B42]">Belum ada data KPI</p>
              <p className="text-[12px] text-[#9A9BA3] mt-0.5">Tambahkan KPI karyawan untuk periode {formatPeriod(period)}.</p>
            </div>
          ) : (
            <ResponsiveTable testId="kpi-table" rows={rows} rowKey="id" loading={loading}
              rowTestId={(r) => `kpi-row-${r.id}`} stickyActions
              columns={[
                { key: "employee_name", header: "Karyawan", mobile: "title", render: (r) => <span className="font-medium">{r.employee_name}</span> },
                { key: "period", header: "Periode", mobile: "subtitle", render: (r) => formatPeriod(r.period) },
                { key: "metric", header: "Metrik", priority: 1, render: (r) => <>{r.metric}{r.note ? <span className="block max-w-[220px] truncate text-[11px] text-[#9A9BA3]">{r.note}</span> : null}</> },
                { key: "target", header: "Target", align: "right", priority: 3, render: (r) => formatDecimal(r.target) },
                { key: "actual", header: "Aktual", align: "right", priority: 2, render: (r) => formatDecimal(r.actual) },
                // G5-35: skor desimal koma ("94,4"; dulu "94.4" bercampur dengan rekap "107,4").
                { key: "score", header: "Skor", align: "right", mobile: "badge", render: (r) => {
                  const b = scoreBadge(r.score);
                  return <span className="whitespace-nowrap"><span className={`font-bold tabular-nums ${scoreCls(r.score)}`}>{formatDecimal(r.score, 1)}</span> <span className={`ml-1 rounded px-1.5 py-0.5 text-[11px] font-semibold ${b.cls}`}>{b.label}</span></span>;
                } },
                { key: "weight", header: "Bobot", align: "right", priority: 4, render: (r) => formatDecimal(r.weight) },
              ]}
              actions={canManage ? (r) => (
                <span className="inline-flex whitespace-nowrap">
                  <button data-testid={`kpi-edit-${r.id}-button`} className="icon-button" title="Ubah" aria-label={`Ubah KPI ${r.metric}`} onClick={() => openEdit(r)}><Pencil size={14} /></button>
                  <button data-testid={`kpi-delete-${r.id}-button`} className="icon-button text-[#C0341D]" title="Hapus" aria-label={`Hapus KPI ${r.metric}`} onClick={() => setDelTarget(r)}><Trash2 size={14} /></button>
                </span>
              ) : undefined} />
          )}
        </div>
      </section>

      {/* Modal create/edit — G5-35: FormModal standar (× , deskripsi, kaki) & judul "Ubah KPI" (dulu `.modal-card`
          polos & "Edit KPI"). Fase 3 · P6 (L-03): label membungkus isiannya (crawl: "isian tanpa label"). */}
      <FormModal open={open} onClose={() => { if (!busy) setOpen(false); }} title={editing ? "Ubah KPI" : "Tambah KPI"}
        subtitle="KPI manual per karyawan per bulan; skor bisa dihitung otomatis dari target & aktual." icon={Target} size="sm"
        testId="kpi-modal" onSubmit={save} submitLabel={editing ? "Simpan Perubahan" : "Simpan KPI"} submitTestId="kpi-form-submit"
        busy={busy} error={fErr}>
            <div className="grid gap-2.5">
              {!editing && (
                <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Karyawan *</span>
                  <KNSelect data-testid="kpi-form-employee" value={form.employee_id} onValueChange={(v) => setForm({ ...form, employee_id: v })} options={activeEmployees(employees).map((e) => ({ value: e.id, label: e.name }))} className="field" placeholder="Pilih karyawan aktif" searchable /></label>
              )}
              {editing && <p className="text-[12px] text-[#6B6B73]">Karyawan: <b>{editing.employee_name}</b></p>}
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Periode *</span>
                  <KNSelect data-testid="kpi-form-period" value={form.period} onValueChange={(v) => setForm({ ...form, period: v })} options={periodOpts} className="field" /></label>
                <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Bobot</span>
                  <input data-testid="kpi-form-weight" type="number" step="0.5" min="0" className="form-input" value={form.weight} onChange={(e) => setForm({ ...form, weight: e.target.value })} /></label>
              </div>
              <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Metrik *</span>
                <input data-testid="kpi-form-metric" className="form-input" value={form.metric} onChange={(e) => setForm({ ...form, metric: e.target.value })} placeholder="mis. Jumlah Desain Baru" /></label>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Target</span>
                  <input data-testid="kpi-form-target" type="number" step="any" className="form-input" value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })} /></label>
                <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Aktual</span>
                  <input data-testid="kpi-form-actual" type="number" step="any" className="form-input" value={form.actual} onChange={(e) => setForm({ ...form, actual: e.target.value })} /></label>
                <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Skor (opsional)</span>
                  <input data-testid="kpi-form-score" type="number" step="any" className="form-input" value={form.score} onChange={(e) => setForm({ ...form, score: e.target.value })} placeholder="auto" /></label>
              </div>
              <p className="text-[10.5px] text-[#9A9BA3]">Kosongkan skor untuk dihitung otomatis: skor = capaian ÷ target × 100, maksimal 150.</p>
              <label className="grid gap-1"><span className="text-[11px] font-bold uppercase text-[#6B6B73]">Catatan</span>
                <textarea data-testid="kpi-form-note" className="form-input" rows="2" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Opsional" /></label>
            </div>
      </FormModal>

      <ConfirmModal open={!!delTarget} title="Hapus KPI?" message={delTarget ? `Hapus KPI "${delTarget.metric}" untuk ${delTarget.employee_name}?` : ""} confirmLabel="Hapus" danger onConfirm={() => doDelete(delTarget)} onCancel={() => setDelTarget(null)} testId="kpi-delete-modal" />
    </div>
  );
}

/** Warna nilai rata-rata skor untuk MetricRow (sama dengan `scoreCls`). */
function scoreTone(s) {
  const v = Number(s) || 0;
  return v >= 100 ? "#1F7A45" : v >= 80 ? "#0058CC" : v >= 60 ? "#B7791F" : "#C0341D";
}
