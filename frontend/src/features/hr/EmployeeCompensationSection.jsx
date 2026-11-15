/**
 * EmployeeCompensationSection — PY-T2 (PY-09, K-37, K-38) · kartu karyawan › Riwayat Kompensasi & Penugasan PT.
 *
 * Gaji pokok, komponen tetap (tunjangan per nama), dan PT tempat karyawan digaji adalah baris BERTANGGAL BERLAKU yang
 * diajukan (izin mengubah data karyawan) lalu disahkan (izin mengesahkan gaji). Proses gaji membaca baris yang berlaku
 * pada periodenya; data karyawan mengikuti baris yang berlaku hari ini. Hanya tampil bagi pemegang izin melihat data
 * pribadi karyawan (nilai gaji) — server juga menolak tanpa izin itu.
 *
 * Sumber: GET /api/hr/employees/{id}/compensation · POST …/compensation · POST …/assignments ·
 * POST /api/hr/compensation/{id}/approve|reject · POST /api/hr/assignments/{id}/approve|reject (ber-Idempotency-Key).
 * Keadaan memuat · galat (+ Coba lagi) · kosong dibedakan; tombol mati menulis alasannya di sampingnya.
 */
import { useCallback, useEffect, useState } from "react";
import { ArrowRightLeft, Ban, Building2, CalendarClock, CheckCircle2, Clock, History as HistoryIcon, Plus, RefreshCw,
  Trash2, Wallet, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import KNSelect from "../../components/KNSelect";
import MoneyInput from "../../components/MoneyInput";
import { askConfirm, askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, todayWib } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { moneyPost } from "../../utils/moneyRequest";
import useIntentKey from "../../hooks/useIntentKey";
import { can } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";

/** Lencana baris riwayat: ikon + teks + warna (bukan warna saja). */
export const ROW_BADGE = {
  pending: { label: "Menunggu disahkan", cls: "status-pending", Icon: Clock },
  berlaku: { label: "Berlaku", cls: "status-done", Icon: CheckCircle2 },
  akan: { label: "Akan berlaku", cls: "status-shipped", Icon: CalendarClock },
  berakhir: { label: "Berakhir", cls: "status-draft", Icon: HistoryIcon },
  rejected: { label: "Ditolak", cls: "status-rejected", Icon: XCircle },
  cancelled: { label: "Dibatalkan", cls: "status-cancelled", Icon: Ban },
};

/** Kunci lencana baris pada tanggal `today` (YYYY-MM-DD, WIB). Baris sah: belum mulai → Akan berlaku; sudah lewat
 *  `effective_to` → Berakhir; selain itu Berlaku. */
export function rowBadge(row, today) {
  const st = row?.status;
  if (st === "pending" || st === "rejected" || st === "cancelled") return st;
  if ((row?.effective_from || "") > today) return "akan";
  if (row?.effective_to && row.effective_to < today) return "berakhir";
  return "berlaku";
}

export function RowBadge({ row, today, testId }) {
  const b = ROW_BADGE[rowBadge(row, today)] || ROW_BADGE.pending;
  const { Icon } = b;
  return <span className={`status-pill ${b.cls} inline-flex items-center gap-1 whitespace-nowrap`} data-testid={testId}><Icon size={12} aria-hidden="true" />{b.label}</span>;
}

/** Galat isian usulan kompensasi; "" = siap kirim. */
export function galatKompensasi(f) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(f?.effective_from || ""))) return "Pilih tanggal berlaku.";
  const g = Number(f?.base_salary);
  if (f?.base_salary === "" || f?.base_salary === null || !Number.isFinite(g) || g < 0) return "Isi gaji pokok (rupiah, tidak negatif).";
  for (const c of f?.fixed_components || []) {
    if (!c.component_code) return "Pilih komponen untuk tiap baris komponen tetap.";
    if (!Number.isFinite(Number(c.amount)) || Number(c.amount) < 0) return "Nominal komponen tetap harus rupiah, tidak negatif.";
  }
  if (!String(f?.reason || "").trim()) return "Alasan wajib diisi.";
  return "";
}

/** Galat isian pindah PT; "" = siap kirim. */
export function galatPenugasan(f) {
  if (!f?.entity_id) return "Pilih PT tujuan.";
  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(f?.effective_from || ""))) return "Pilih tanggal berlaku.";
  if (!String(f?.reason || "").trim()) return "Alasan wajib diisi.";
  return "";
}

/** Teks konfirmasi sahkan kompensasi (spesifikasi): "Sahkan gaji pokok Rp … untuk {nama}, berlaku {tanggal}, di {PT}?" */
export function teksSahkanGaji(row, nama, pt) {
  return `Sahkan gaji pokok ${formatCurrency(row?.base_salary)} untuk ${nama}, berlaku ${formatDate(row?.effective_from)}, di ${pt}?`;
}

/** Badan permintaan usulan kompensasi (komponen tetap SELALU dikirim: kosong = tanpa komponen tetap). */
export function badanKompensasi(f) {
  return {
    effective_from: f.effective_from, base_salary: Number(f.base_salary), reason: String(f.reason || "").trim(),
    fixed_components: (f.fixed_components || []).map((c) => ({ component_code: c.component_code, label: String(c.label || "").trim(), amount: Number(c.amount) || 0 })),
  };
}

const fixedText = (row) => (row?.fixed_components || []).map((c) => `${c.label || c.component_code} ${formatCurrency(c.amount)}`);
const who = (p) => (p && p.name) || "—";

export default function EmployeeCompensationSection({ employee, currentUser, onChanged }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const canUpdate = can(perms, "hr", "update");
  const canApprove = can(perms, "payroll", "approve");
  const intent = useIntentKey("riwayat-gaji");
  const empId = employee?.id;
  const nama = employee?.name || "karyawan ini";

  const [data, setData] = useState(null);
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");
  const [compForm, setCompForm] = useState(null);
  const [asgForm, setAsgForm] = useState(null);
  const [formErr, setFormErr] = useState("");
  const [units, setUnits] = useState([]);

  const load = useCallback(async () => {
    if (!empId) return;
    setState("loading");
    try {
      const r = await axios.get(`${API}/hr/employees/${empId}/compensation`);
      setData(r.data || {}); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [empId]);
  useEffect(() => { load(); }, [load]);

  const today = data?.today || todayWib();
  const comp = data?.compensation || [];
  const asg = data?.assignments || [];
  const opts = (data?.fixed_component_options || []).map((o) => ({ value: o.code, label: o.name }));
  const ptName = (id) => entityFullById(entities, id, "PT karyawan");
  const berlaku = comp.find((r) => rowBadge(r, today) === "berlaku");
  const alasanUbah = canUpdate ? "" : "Mengajukan perubahan butuh izin mengubah data karyawan.";

  async function selesai(teks) {
    setMsg(teks); await load(); onChanged?.();
  }

  function bukaKompensasi() {
    setFormErr("");
    setCompForm({ effective_from: "", base_salary: berlaku ? String(berlaku.base_salary ?? "") : String(employee?.base_salary ?? ""),
      fixed_components: (berlaku?.fixed_components || []).map((c) => ({ ...c })), reason: "" });
  }
  const ubahKomp = (patch) => setCompForm((f) => ({ ...f, ...patch }));
  const ubahBaris = (i, patch) => setCompForm((f) => ({ ...f, fixed_components: f.fixed_components.map((c, j) => (j === i ? { ...c, ...patch } : c)) }));
  async function kirimKompensasi() {
    const g = galatKompensasi(compForm);
    if (g) { setFormErr(g); return; }
    setBusy("komp");
    try {
      const body = badanKompensasi(compForm);
      await intent.send({ empId, ...body }, (k) => moneyPost(`${API}/hr/employees/${empId}/compensation`, body, k));
      setCompForm(null);
      await selesai(`Perubahan gaji pokok ${formatCurrency(body.base_salary)} berlaku ${formatDate(body.effective_from)} diajukan, menunggu disahkan.`);
    } catch (e) { setFormErr(apiErrorText(e) || "Usulan gagal disimpan."); }
    finally { setBusy(""); }
  }

  async function bukaPenugasan() {
    setFormErr(""); setUnits([]);
    setAsgForm({ entity_id: "", effective_from: "", department_id: "", position_id: "", reason: "" });
  }
  async function pilihPt(eid) {
    setAsgForm((f) => ({ ...f, entity_id: eid, department_id: "", position_id: "" }));
    setUnits([]);
    if (!eid) return;
    try {
      const r = await axios.get(`${API}/hr/org-units`, { params: { entity_id: eid, status: "active" } });
      setUnits(Array.isArray(r.data) ? r.data : []);
    } catch (e) { setFormErr(`Departemen PT itu tidak bisa dimuat. ${apiErrorText(e) || ""}`.trim()); }
  }
  async function kirimPenugasan() {
    const g = galatPenugasan(asgForm);
    if (g) { setFormErr(g); return; }
    setBusy("asg");
    try {
      const body = { ...asgForm, reason: String(asgForm.reason || "").trim() };
      await intent.send({ empId, ...body }, (k) => moneyPost(`${API}/hr/employees/${empId}/assignments`, body, k));
      setAsgForm(null);
      await selesai(`Pemindahan ke ${ptName(body.entity_id)} mulai ${formatDate(body.effective_from)} diajukan, menunggu disahkan.`);
    } catch (e) { setFormErr(apiErrorText(e) || "Usulan gagal disimpan."); }
    finally { setBusy(""); }
  }

  async function sahkan(jalur, row) {
    const ok = await askConfirm(jalur === "compensation"
      ? { title: "Sahkan perubahan gaji?", message: teksSahkanGaji(row, nama, ptName(row.entity_id)), confirmLabel: "Sahkan" }
      : { title: "Sahkan pemindahan PT?", message: `Pindahkan ${nama} ke ${ptName(row.entity_id)}, berlaku ${formatDate(row.effective_from)}?`, confirmLabel: "Sahkan" });
    if (!ok) return;
    setBusy(`ok-${row.id}`);
    try {
      await intent.send({ id: row.id, aksi: "sahkan" }, (k) => moneyPost(`${API}/hr/${jalur}/${row.id}/approve`, {}, k));
      await selesai(jalur === "compensation" ? `Perubahan gaji berlaku ${formatDate(row.effective_from)} disahkan.`
        : `Pemindahan ke ${ptName(row.entity_id)} disahkan.`);
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
    finally { setBusy(""); }
  }
  async function tolak(jalur, row) {
    const reason = await askReason({
      title: jalur === "compensation" ? "Tolak perubahan gaji?" : "Tolak pemindahan PT?",
      description: `${nama} · berlaku ${formatDate(row.effective_from)}. Baris yang ditolak tidak dipakai proses gaji.`,
      confirmLabel: "Tolak", reasonPlaceholder: "Contoh: nominal belum disetujui direksi", danger: true,
    });
    if (!reason) return;
    setBusy(`x-${row.id}`);
    try {
      const body = { reason };
      await intent.send({ id: row.id, aksi: "tolak", ...body }, (k) => moneyPost(`${API}/hr/${jalur}/${row.id}/reject`, body, k));
      await selesai("Usulan ditolak.");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
    finally { setBusy(""); }
  }

  const aksi = (jalur, r) => (r.status === "pending" ? (
    <div className="flex flex-wrap items-center gap-1.5">
      <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid={`emp-hist-approve-${r.id}`} disabled={!!busy} onClick={() => sahkan(jalur, r)}><CheckCircle2 size={12} /> Sahkan</button>
      <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`emp-hist-reject-${r.id}`} disabled={!!busy} onClick={() => tolak(jalur, r)}><XCircle size={12} /> Tolak</button>
    </div>) : null);

  const body = state === "loading" ? (
    <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="emp-comp-loading">Memuat riwayat kompensasi…</div>
  ) : state === "error" ? (
    <div className="section-pad"><ErrorNotice testId="emp-comp-error" message={`Riwayat kompensasi tidak bisa dimuat atau diproses. ${err}`.trim()} onRetry={load} /></div>
  ) : null;
  const deps = units.filter((u) => u.unit_type === "department");
  const poss = units.filter((u) => u.unit_type === "position" && (!asgForm?.department_id || u.parent_id === asgForm.department_id));
  const ptOpts = (entities || []).filter((e) => e && e.id && e.id !== "all").map((e) => ({ value: e.id, label: entityFullById(entities, e.id) }));

  return (
    <div className="space-y-3" data-testid="emp-comp-section">
      {msg && <div className="notice-bar success" data-testid="emp-comp-msg"><span className="text-fs-12">{msg}</span><button type="button" className="icon-button" aria-label="Tutup" onClick={() => setMsg("")}>×</button></div>}

      {/* ── Riwayat Kompensasi ── */}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h3 className="flex items-center gap-2" data-testid="emp-comp-title"><Wallet size={14} className="text-kn-action" aria-hidden="true" />Riwayat Kompensasi</h3>
          <button type="button" data-testid="emp-comp-refresh" onClick={load} className="secondary-button btn-sm ml-auto whitespace-nowrap"><RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2">Gaji pokok dan komponen tetap bertanggal berlaku. Proses gaji memakai baris yang berlaku pada periodenya; perubahan berlaku sesudah disahkan.</p>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" data-testid="emp-comp-add" disabled={!!alasanUbah || state !== "ready"} onClick={bukaKompensasi} className="primary-button btn-sm whitespace-nowrap"><Plus size={13} /> Ajukan perubahan</button>
            {alasanUbah && <span className="text-fs-12 text-kn-text-2" data-testid="emp-comp-add-why">{alasanUbah}</span>}
          </div>
        </div>
        {body || (comp.length === 0 ? (
          <div className="section-pad py-6 text-center text-fs-13 text-kn-text-2" data-testid="emp-comp-empty">Belum ada riwayat kompensasi. Gaji dibaca dari data karyawan sampai baris pertama dibuat.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="emp-comp-table">
              {/* Cek layar — muat di kartu 1024 px: gaji pokok + komponen tetap satu sel; pengaju + pengesah satu sel. */}
              <thead><tr>
                <th>Berlaku sejak</th><th>Gaji pokok · komponen tetap</th><th>Status</th><th>Alasan</th><th>Diajukan · disahkan oleh</th>
                {canApprove && <th className="col-sticky-end">Aksi</th>}
              </tr></thead>
              <tbody>
                {comp.map((r) => (
                  <tr key={r.id} data-testid={`emp-comp-row-${r.id}`}>
                    <td className="whitespace-nowrap">{formatDate(r.effective_from)}{r.effective_to && <span className="block text-fs-12 text-kn-text-2">s.d. {formatDate(r.effective_to)}</span>}</td>
                    <td className="min-w-[150px]"><span className="font-semibold tabular-nums">{formatCurrency(r.base_salary)}</span>
                      {fixedText(r).map((t, i) => <span key={`${r.id}-${i}`} className="block text-fs-12 text-kn-text-2 tabular-nums">{t}</span>)}
                      {!fixedText(r).length && <span className="block text-fs-12 text-kn-text-2">Tanpa komponen tetap</span>}</td>
                    <td><RowBadge row={r} today={today} testId={`emp-comp-status-${r.id}`} /></td>
                    <td className="max-w-[160px] break-words">{r.reason || "—"}{r.decision_reason && <span className="block text-fs-12 text-kn-text-2">{r.decision_reason}</span>}</td>
                    <td className="whitespace-nowrap">{who(r.proposed_by)}<span className="block text-fs-12 text-kn-text-2">{r.status === "approved" ? who(r.approved_by) : "Belum disahkan"}</span></td>
                    {canApprove && <td className="col-sticky-end">{aksi("compensation", r)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
        {!canApprove && state === "ready" && comp.some((r) => r.status === "pending") && <p className="section-pad !pt-2 text-fs-12 text-kn-text-2" data-testid="emp-comp-no-approve">Mengesahkan perubahan gaji butuh izin mengesahkan gaji.</p>}
      </div>

      {/* ── Penugasan PT ── */}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h3 className="flex items-center gap-2" data-testid="emp-asg-title"><Building2 size={14} className="text-kn-action" aria-hidden="true" />Penugasan PT</h3>
        </div>
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2">PT yang menggaji karyawan ini menurut tanggal berlaku. Pindah PT di tengah bulan dibayar menurut pengaturan "Gaji berubah di tengah bulan".</p>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" data-testid="emp-asg-add" disabled={!!alasanUbah || state !== "ready"} onClick={bukaPenugasan} className="primary-button btn-sm whitespace-nowrap"><ArrowRightLeft size={13} /> Pindahkan ke PT lain</button>
            {alasanUbah && <span className="text-fs-12 text-kn-text-2">{alasanUbah}</span>}
          </div>
        </div>
        {state === "ready" && (asg.length === 0 ? (
          <div className="section-pad py-6 text-center text-fs-13 text-kn-text-2" data-testid="emp-asg-empty">Belum ada riwayat penugasan. PT dibaca dari data karyawan: {ptName(employee?.entity_id)}.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="emp-asg-table">
              <thead><tr>
                <th>Berlaku sejak</th><th>PT</th><th>Departemen</th><th>Jabatan</th><th>Status</th>
                {canApprove && <th className="col-sticky-end">Aksi</th>}
              </tr></thead>
              <tbody>
                {asg.map((r) => (
                  <tr key={r.id} data-testid={`emp-asg-row-${r.id}`}>
                    <td className="whitespace-nowrap">{formatDate(r.effective_from)}{r.effective_to && <span className="block text-fs-12 text-kn-text-2">s.d. {formatDate(r.effective_to)}</span>}</td>
                    <td className="min-w-[140px]">{ptName(r.entity_id)}</td>
                    <td>{r.department_name || "—"}</td>
                    <td>{r.position_name || "—"}</td>
                    <td><RowBadge row={r} today={today} testId={`emp-asg-status-${r.id}`} /></td>
                    {canApprove && <td className="col-sticky-end">{aksi("assignments", r)}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {/* ── Pop-up ajukan perubahan kompensasi ── */}
      <FormModal open={!!compForm} onClose={() => setCompForm(null)} title="Ajukan perubahan kompensasi" subtitle={nama} icon={Wallet}
        testId="emp-comp-form" onSubmit={kirimKompensasi} submitLabel="Ajukan" busy={busy === "komp"} error={formErr}>
        {compForm && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="field-label">Berlaku sejak <span className="req">*</span></label>
              <KNDatePicker data-testid="emp-comp-form-date" value={compForm.effective_from} onChange={(v) => ubahKomp({ effective_from: v || "" })} placeholder="Tanggal berlaku" /></div>
            <div><label className="field-label">Gaji pokok <span className="req">*</span></label>
              <MoneyInput testId="emp-comp-form-salary" value={compForm.base_salary} onChange={(v) => ubahKomp({ base_salary: v })} className="field tabular-nums" /></div>
            <fieldset className="sm:col-span-2 space-y-2"><legend className="field-label">Komponen tetap</legend>
              {compForm.fixed_components.map((c, i) => (
                <div key={i} className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1.2fr_1fr_auto] sm:items-start" data-testid={`emp-comp-form-fixed-${i}`}>
                  <KNSelect value={c.component_code} onValueChange={(v) => ubahBaris(i, { component_code: v })} className="field" options={opts} placeholder="Komponen" />
                  <input className="field" value={c.label || ""} onChange={(e) => ubahBaris(i, { label: e.target.value })} placeholder="Keterangan, mis. Transport" aria-label="Keterangan komponen" />
                  <MoneyInput value={c.amount} onChange={(v) => ubahBaris(i, { amount: v })} className="field tabular-nums" />
                  <button type="button" className="icon-button" aria-label="Hapus baris komponen" onClick={() => ubahKomp({ fixed_components: compForm.fixed_components.filter((_, j) => j !== i) })}><Trash2 size={13} /></button>
                </div>
              ))}
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid="emp-comp-form-add-fixed" disabled={!opts.length}
                  onClick={() => ubahKomp({ fixed_components: [...compForm.fixed_components, { component_code: opts[0]?.value || "", label: "", amount: "" }] })}><Plus size={12} /> Tambah komponen tetap</button>
                {!opts.length && <span className="text-fs-12 text-kn-text-2">Belum ada komponen tetap bulanan di PT ini.</span>}
              </div>
              <p className="text-fs-12 text-kn-text-2">Terisi dari baris yang berlaku sekarang. Hapus baris untuk menghentikan komponennya mulai tanggal berlaku.</p>
            </fieldset>
            <div className="sm:col-span-2"><label className="field-label">Alasan <span className="req">*</span></label>
              <input data-testid="emp-comp-form-reason" className="field" value={compForm.reason} onChange={(e) => ubahKomp({ reason: e.target.value })} placeholder="Contoh: kenaikan tahunan sesuai SK direksi" /></div>
            <p className="sm:col-span-2 text-fs-12 text-kn-text-2">Berlaku mundur ke bulan yang gajinya sudah dibayar? Selisihnya dibuat sebagai masukan Rapel bulan ini (menunggu disahkan di Komponen & Masukan).</p>
          </div>
        )}
      </FormModal>

      {/* ── Pop-up pindahkan ke PT lain ── */}
      <FormModal open={!!asgForm} onClose={() => setAsgForm(null)} title="Pindahkan ke PT lain" subtitle={nama} icon={ArrowRightLeft}
        testId="emp-asg-form" onSubmit={kirimPenugasan} submitLabel="Ajukan" busy={busy === "asg"} error={formErr}>
        {asgForm && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="field-label">PT tujuan <span className="req">*</span></label>
              <KNSelect data-testid="emp-asg-form-pt" value={asgForm.entity_id} onValueChange={pilihPt} className="field" options={ptOpts} placeholder="Pilih PT" /></div>
            <div><label className="field-label">Berlaku sejak <span className="req">*</span></label>
              <KNDatePicker data-testid="emp-asg-form-date" value={asgForm.effective_from} onChange={(v) => setAsgForm((f) => ({ ...f, effective_from: v || "" }))} placeholder="Tanggal berlaku" /></div>
            <div><label className="field-label">Departemen</label>
              <KNSelect value={asgForm.department_id} onValueChange={(v) => setAsgForm((f) => ({ ...f, department_id: v, position_id: "" }))} className="field"
                options={[{ value: "", label: "— Tidak ditentukan —" }, ...deps.map((d) => ({ value: d.id, label: d.name }))]} disabled={!asgForm.entity_id} /></div>
            <div><label className="field-label">Jabatan</label>
              <KNSelect value={asgForm.position_id} onValueChange={(v) => setAsgForm((f) => ({ ...f, position_id: v }))} className="field"
                options={[{ value: "", label: "— Tidak ditentukan —" }, ...poss.map((p) => ({ value: p.id, label: p.name }))]} disabled={!asgForm.entity_id} /></div>
            <div className="sm:col-span-2"><label className="field-label">Alasan <span className="req">*</span></label>
              <input data-testid="emp-asg-form-reason" className="field" value={asgForm.reason} onChange={(e) => setAsgForm((f) => ({ ...f, reason: e.target.value }))} placeholder="Contoh: mutasi ke gudang Kanda per SK 12/2026" /></div>
          </div>
        )}
      </FormModal>
    </div>
  );
}
