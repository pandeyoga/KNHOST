/**
 * HolidaysView — PY-T3 (PY-07, K-39) · Pengaturan › SDM › Kalender Libur.
 *
 * Hari libur PT aktif per tahun (`hr_holidays`). Dipakai penghitung gaji: jenis hari lembur (hari libur = pengali hari
 * libur) dan hitungan hari kerja untuk prorata dan potongan. Sistem TIDAK mengisinya sendiri — tanggal libur nasional
 * dan cuti bersama berasal dari keputusan resmi.
 *
 * Sumber: GET /api/hr/holidays?year= (`hr.view`) · POST /api/hr/holidays · DELETE /api/hr/holidays/{id}
 * (`hr.manage_attendance`; 409 tanggal kembar dan saat "Semua PT"). Keadaan memuat · galat (+ Coba lagi) · kosong
 * dibedakan; tombol mati menulis alasannya di sampingnya.
 */
import { useCallback, useEffect, useState } from "react";
import { CalendarDays, CalendarPlus, Flag, Building2, Plus, RefreshCw, Trash2, Users } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import KNSelect from "../../components/KNSelect";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatDate, todayWib } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";

export const KETERANGAN = "Isi dari keputusan resmi libur nasional dan cuti bersama. Sistem tidak mengisinya sendiri.";
export const KOSONG = "Belum ada hari libur untuk tahun ini.";
/** Jenis hari libur: ikon + teks + warna (bukan warna saja). */
export const JENIS = {
  nasional: { label: "Nasional", cls: "status-shipped", Icon: Flag },
  cuti_bersama: { label: "Cuti bersama", cls: "status-pending", Icon: Users },
  perusahaan: { label: "Perusahaan", cls: "status-draft", Icon: Building2 },
};
export const JENIS_OPTS = Object.entries(JENIS).map(([value, v]) => ({ value, label: v.label }));

/** Alasan tombol "Tambah hari libur" mati (ditulis di samping tombol). */
export function alasanTambahLibur({ canWrite, canManage }) {
  if (!canWrite) return "Pilih satu PT dulu untuk menambah hari libur.";
  if (!canManage) return "Mengubah kalender libur butuh izin mengatur absensi.";
  return "";
}

/** Galat isian hari libur; "" = siap kirim. */
export function galatLibur(f) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(f?.date || ""))) return "Pilih tanggal.";
  if (!String(f?.name || "").trim()) return "Isi nama hari libur.";
  if (!JENIS[f?.kind]) return "Pilih jenis hari libur.";
  return "";
}

export function JenisLibur({ kind, testId }) {
  const j = JENIS[kind] || JENIS.perusahaan;
  const { Icon } = j;
  return <span className={`status-pill ${j.cls} inline-flex items-center gap-1 whitespace-nowrap`} data-testid={testId}><Icon size={12} aria-hidden="true" />{j.label}</span>;
}

export default function HolidaysView() {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canManage = canCurrent("hr", "manage_attendance");
  const thisYear = Number(String(todayWib()).slice(0, 4)) || new Date().getFullYear();
  const [year, setYear] = useState(thisYear);
  const [rows, setRows] = useState([]);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [form, setForm] = useState(null);
  const [formErr, setFormErr] = useState("");
  const [busy, setBusy] = useState("");
  const pt = entityFullById(entities, selectedEntity, "PT ini");
  const alasan = alasanTambahLibur({ canWrite, canManage });
  const yearOpts = [thisYear - 1, thisYear, thisYear + 1].map((y) => ({ value: String(y), label: String(y) }));

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/hr/holidays`, { params: { year } });
      setRows(Array.isArray(r.data?.rows) ? r.data.rows : []); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [year]);
  useEffect(() => { load(); }, [load, selectedEntity]);

  function buka() { setFormErr(""); setForm({ date: "", name: "", kind: "nasional" }); }
  async function kirim() {
    const g = galatLibur(form);
    if (g) { setFormErr(g); return; }
    setBusy("tambah");
    try {
      const body = { date: form.date, name: String(form.name).trim(), kind: form.kind };
      await axios.post(`${API}/hr/holidays`, body);
      setForm(null); setMsg(`Hari libur ${formatDate(body.date)} (${body.name}) ditambahkan untuk ${pt}.`);
      if (String(body.date).slice(0, 4) !== String(year)) setYear(Number(String(body.date).slice(0, 4)));
      else await load();
    } catch (e) { setFormErr(apiErrorText(e) || "Hari libur gagal disimpan."); }
    finally { setBusy(""); }
  }
  async function hapus(row) {
    const ok = await askConfirm({ title: "Hapus hari libur?", danger: true, confirmLabel: "Hapus",
      message: `Hapus ${formatDate(row.date)} (${row.name}) dari kalender libur ${entityFullById(entities, row.entity_id, pt)}? Proses gaji yang dihitung ulang sesudahnya memperlakukan tanggal itu sebagai hari biasa.` });
    if (!ok) return;
    setBusy(`hapus-${row.id}`);
    try {
      await axios.delete(`${API}/hr/holidays/${row.id}`);
      setMsg(`Hari libur ${formatDate(row.date)} dihapus.`); await load();
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
    finally { setBusy(""); }
  }

  const aksi = canManage && canWrite;
  return (
    <div className="space-y-3" data-testid="hr-holidays-view">
      <EntityScopeBanner />
      {msg && <div className="notice-bar success" data-testid="hr-holidays-msg"><span className="text-fs-12">{msg}</span><button type="button" className="icon-button" aria-label="Tutup" onClick={() => setMsg("")}>×</button></div>}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h3 className="flex items-center gap-2"><CalendarDays size={14} className="text-kn-action" aria-hidden="true" />Kalender Libur</h3>
          <button type="button" data-testid="hr-holidays-refresh" onClick={load} className="secondary-button btn-sm ml-auto whitespace-nowrap"><RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2" data-testid="hr-holidays-note">{KETERANGAN}</p>
          <p className="text-fs-12 text-kn-text-2">Dipakai hitungan gaji: lembur pada hari libur memakai pengali hari libur, dan hari libur tidak dihitung sebagai hari kerja untuk prorata dan potongan.</p>
          <div className="flex flex-wrap items-center gap-2">
            <div className="w-28"><KNSelect data-testid="hr-holidays-year" value={String(year)} onValueChange={(v) => setYear(Number(v))} className="field" options={yearOpts} aria-label="Tahun" /></div>
            <button type="button" data-testid="hr-holidays-add" disabled={!!alasan} onClick={buka} className="primary-button btn-sm whitespace-nowrap"><Plus size={13} /> Tambah hari libur</button>
            {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="hr-holidays-add-why">{alasan}</span>}
          </div>
        </div>
        {state === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="hr-holidays-loading">Memuat kalender libur…</div>
        ) : state === "error" ? (
          <div className="section-pad"><ErrorNotice testId="hr-holidays-error" message={`Kalender libur tidak bisa dimuat atau diproses. ${err}`.trim()} onRetry={load} /></div>
        ) : rows.length === 0 ? (
          <div className="section-pad py-6 text-center text-fs-13 text-kn-text-2" data-testid="hr-holidays-empty">{KOSONG}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="hr-holidays-table">
              <thead><tr>
                <th>Tanggal</th><th>Nama</th><th>Jenis</th>{!canWrite && <th>PT</th>}
                {aksi && <th className="col-sticky-end">Aksi</th>}
              </tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} data-testid={`hr-holidays-row-${r.id}`}>
                    <td className="whitespace-nowrap">{formatDate(r.date)}</td>
                    <td className="min-w-[160px] break-words">{r.name}</td>
                    <td><JenisLibur kind={r.kind} testId={`hr-holidays-kind-${r.id}`} /></td>
                    {!canWrite && <td>{entityFullById(entities, r.entity_id, "PT")}</td>}
                    {aksi && <td className="col-sticky-end"><button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`hr-holidays-del-${r.id}`} disabled={!!busy} onClick={() => hapus(r)}><Trash2 size={12} /> Hapus</button></td>}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="section-pad !pt-2 text-fs-12 text-kn-text-2" data-testid="hr-holidays-count">{rows.length} hari libur pada {year}.</p>
          </div>
        )}
      </div>

      <FormModal open={!!form} onClose={() => setForm(null)} title="Tambah hari libur" subtitle={pt} icon={CalendarPlus}
        testId="hr-holidays-form" onSubmit={kirim} submitLabel="Simpan" busy={busy === "tambah"} error={formErr}>
        {form && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="field-label">Tanggal <span className="req">*</span></label>
              <KNDatePicker data-testid="hr-holidays-form-date" value={form.date} onChange={(v) => setForm((f) => ({ ...f, date: v || "" }))} placeholder="Pilih tanggal" /></div>
            <div><label className="field-label">Jenis <span className="req">*</span></label>
              <KNSelect data-testid="hr-holidays-form-kind" value={form.kind} onValueChange={(v) => setForm((f) => ({ ...f, kind: v }))} className="field" options={JENIS_OPTS} /></div>
            <div className="sm:col-span-2"><label className="field-label">Nama <span className="req">*</span></label>
              <input data-testid="hr-holidays-form-name" className="field" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="Contoh: Hari Raya Natal" maxLength={120} /></div>
            <p className="sm:col-span-2 text-fs-12 text-kn-text-2">{KETERANGAN}</p>
          </div>
        )}
      </FormModal>
    </div>
  );
}
