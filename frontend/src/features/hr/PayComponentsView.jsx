/**
 * PayComponentsView — PY-T1 (K-37, K-40) · SDM › Penggajian › Komponen & Masukan.
 *
 * Bagian **Komponen gaji**: daftar komponen PT aktif (isi awal bawaan + buatan pengguna). Komponen bawaan tidak bisa
 * dihapus atau diganti jenisnya; komponen baru saat ini berjenis hitung "masukan" (nilainya dari antrean di bawah).
 * Tanda Dasar BPJS, Dasar lembur, Diprorata disimpan tetapi belum dipakai hitungan gaji (menyusul) — ditulis di layar.
 * Sumber: GET/POST/PATCH /api/hr/payroll/components (ubah = `hr.manage_payroll`).
 *
 * Bagian **Masukan**: antrean masukan komponen (bonus, THR, potongan, …) yang masuk ke proses gaji periode bayarnya.
 * Isian manual berstatus "Menunggu disahkan" sampai disahkan (`payroll.approve`). Sumber: GET/POST
 * /api/hr/payroll/inputs, POST …/{id}/approve, …/{id}/cancel (alasan wajib).
 *
 * Satu PT saja untuk menulis: mode "Semua PT" → tombol tambah mati dengan alasan tertulis di sampingnya. Keadaan
 * memuat · galat (+ Coba lagi) · kosong dibedakan; daftar masukan berhalaman dengan jumlah total.
 */
import { useCallback, useEffect, useState } from "react";
import { Ban, CheckCircle2, Circle, Clock, Layers, ListPlus, Pencil, Plus, RefreshCw, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import FormModal from "../../components/FormModal";
import KNPager from "../../components/KNPager";
import KNSelect from "../../components/KNSelect";
import { askConfirm, askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatPeriod } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { moneyPost } from "../../utils/moneyRequest";
import useIntentKey from "../../hooks/useIntentKey";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";
import { curMonth, recentMonths } from "./payrollUtils";

const PAGE_SIZE = 20;
export const TEKS_SEMUA_PT = "Pilih satu PT dulu";
export const KIND_LABEL = { pendapatan: "Pendapatan", potongan: "Potongan", tanggungan_perusahaan: "Tanggungan perusahaan" };
export const CALC_LABEL = { tetap_bulanan: "Tetap bulanan", per_jam: "Per jam", masukan: "Masukan", undang_undang: "Menurut undang-undang" };
export const RUN_TYPE_LABEL = { regular: "Reguler", thr: "THR", susulan: "Susulan" };
export const SOURCE_LABEL = { incentive_sheet: "Lembar insentif", overtime: "Lembur", cash_advance: "Kasbon", rapel: "Rapel", manual: "Isian manual" };
/** Status masukan: ikon + teks + warna (bukan warna saja). */
export const INPUT_STATUS = {
  pending: { label: "Menunggu disahkan", cls: "status-pending", Icon: Clock },
  approved: { label: "Disahkan", cls: "status-approved", Icon: CheckCircle2 },
  used: { label: "Terpakai", cls: "status-done", Icon: Layers },
  cancelled: { label: "Dibatalkan", cls: "status-rejected", Icon: XCircle },
};
const STATUS_CHIPS = [{ key: "semua", label: "Semua status" },
  ...Object.entries(INPUT_STATUS).map(([key, v]) => ({ key, label: v.label }))];

/** Alasan tombol "Tambah komponen" mati (ditulis di samping tombol — bukan tooltip). */
export function alasanTambahKomponen({ canWrite, canManage }) {
  if (!canWrite) return TEKS_SEMUA_PT;
  if (!canManage) return "Mengubah komponen gaji butuh izin mengatur penggajian.";
  return "";
}
/** Alasan tombol "Tambah masukan" mati. */
export function alasanTambahMasukan({ canWrite, canCreate }) {
  if (!canWrite) return TEKS_SEMUA_PT;
  if (!canCreate) return "Menambah masukan butuh izin menyiapkan gaji.";
  return "";
}

/** Galat isian komponen baru (sebelum kirim); "" = siap. */
export function galatKomponen(f) {
  if (!/^[A-Z][A-Z0-9_]{1,29}$/.test(String(f.code || ""))) return "Kode 2–30 huruf besar, angka, atau garis bawah, diawali huruf (mis. BONUS).";
  if (!String(f.name || "").trim()) return "Isi nama komponen.";
  if (f.kind === "potongan" && !String(f.account_code || "").trim()) return "Komponen potongan wajib punya akun.";
  if (!(f.allowed_run_types || []).length) return "Pilih minimal satu jenis proses gaji.";
  return "";
}
/** Galat isian masukan baru; "" = siap. */
export function galatMasukan(f) {
  if (!f.employee_id) return "Pilih karyawan.";
  if (!f.component_code) return "Pilih komponen.";
  if (!f.pay_period) return "Pilih periode bayar.";
  const n = Number(f.amount);
  if (!Number.isInteger(n) || n === 0) return "Nominal harus rupiah bulat dan tidak nol (boleh negatif untuk penyesuaian).";
  if (!String(f.reason || "").trim()) return "Alasan wajib diisi.";
  return "";
}

function YaTidak({ v, testId }) {
  return v ? <span className="inline-flex items-center gap-1 whitespace-nowrap text-kn-text" data-testid={testId}><CheckCircle2 size={12} aria-hidden="true" />Ya</span>
    : <span className="inline-flex items-center gap-1 whitespace-nowrap text-kn-text-2" data-testid={testId}><Circle size={12} aria-hidden="true" />Tidak</span>;
}

export function InputStatus({ status, testId }) {
  const st = INPUT_STATUS[status] || INPUT_STATUS.pending;
  const { Icon } = st;
  return <span className={`status-pill ${st.cls} inline-flex items-center gap-1 whitespace-nowrap`} data-testid={testId}><Icon size={12} aria-hidden="true" />{st.label}</span>;
}

const KOSONG_KOMPONEN = { code: "", name: "", kind: "pendapatan", account_code: "", taxable: true, allowed_run_types: ["regular", "susulan"],
  in_bpjs_base: false, in_overtime_base: false, prorate: false, sort: 300, is_active: true };

export default function PayComponentsView() {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canManage = canCurrent("hr", "manage_payroll");
  const canCreate = canCurrent("payroll", "create");
  const canApprove = canCurrent("payroll", "approve");
  const pt = entityFullById(entities, selectedEntity, "PT ini");
  const intent = useIntentKey("masukan-gaji");

  const [comps, setComps] = useState([]);
  const [compState, setCompState] = useState("loading");
  const [compErr, setCompErr] = useState("");
  const [period, setPeriod] = useState(curMonth());
  const [status, setStatus] = useState("semua");
  const [page, setPage] = useState(1);
  const [list, setList] = useState({ items: [], total: 0 });
  const [listState, setListState] = useState("loading");
  const [listErr, setListErr] = useState("");
  const [emps, setEmps] = useState([]);
  const [msg, setMsg] = useState("");
  const [compForm, setCompForm] = useState(null);   // null = tertutup; {…, id?} = buat / ubah
  const [inpForm, setInpForm] = useState(null);
  const [busy, setBusy] = useState("");
  const [formErr, setFormErr] = useState("");

  const loadComps = useCallback(async () => {
    if (!canWrite) { setComps([]); setCompState("ready"); return; }
    setCompState("loading");
    try {
      const r = await axios.get(`${API}/hr/payroll/components`);
      setComps(Array.isArray(r.data?.items) ? r.data.items : []); setCompErr(""); setCompState("ready");
    } catch (e) { setCompErr(apiErrorText(e) || ""); setCompState("error"); }
  }, [canWrite]);
  const loadList = useCallback(async () => {
    setListState("loading");
    try {
      const r = await axios.get(`${API}/hr/payroll/inputs`, { params: {
        pay_period: period || undefined, status: status === "semua" ? undefined : status, page, page_size: PAGE_SIZE } });
      setList(r.data || { items: [], total: 0 }); setListErr(""); setListState("ready");
    } catch (e) { setListErr(apiErrorText(e) || ""); setListState("error"); }
  }, [period, status, page]);
  useEffect(() => { loadComps(); }, [loadComps, selectedEntity]);
  useEffect(() => { loadList(); }, [loadList, selectedEntity]);

  const bukaKomponen = (c = null) => {
    setFormErr("");
    setCompForm(c ? { ...KOSONG_KOMPONEN, ...c } : { ...KOSONG_KOMPONEN });
  };
  const ubahKomp = (patch) => setCompForm((f) => ({ ...f, ...patch }));
  const toggleRunType = (rt) => setCompForm((f) => {
    const cur = f.allowed_run_types || [];
    return { ...f, allowed_run_types: cur.includes(rt) ? cur.filter((x) => x !== rt) : [...cur, rt] };
  });
  async function simpanKomponen() {
    const f = compForm;
    const g = f.id ? (String(f.name || "").trim() ? "" : "Isi nama komponen.") : galatKomponen(f);
    if (g) { setFormErr(g); return; }
    setBusy("komponen");
    try {
      if (f.id) {
        const body = f.system ? { name: f.name, sort: Number(f.sort) || 0, in_bpjs_base: f.in_bpjs_base, in_overtime_base: f.in_overtime_base, prorate: f.prorate,
          ...(f.kind === "pendapatan" && f.bucket !== "commission" ? { account_code: f.account_code || "" } : {}) }
          : { name: f.name, sort: Number(f.sort) || 0, account_code: f.account_code || "", taxable: !!f.taxable, is_active: !!f.is_active,
            allowed_run_types: f.allowed_run_types, in_bpjs_base: f.in_bpjs_base, in_overtime_base: f.in_overtime_base, prorate: f.prorate };
        await axios.patch(`${API}/hr/payroll/components/${f.id}`, body);
        setMsg(`Komponen ${f.code} diperbarui.`);
      } else {
        const body = { code: f.code, name: f.name, kind: f.kind, calc: "masukan", account_code: f.account_code || "",
          taxable: f.kind === "pendapatan" ? !!f.taxable : false, allowed_run_types: f.allowed_run_types, sort: Number(f.sort) || 300,
          in_bpjs_base: f.in_bpjs_base, in_overtime_base: f.in_overtime_base, prorate: f.prorate };
        await axios.post(`${API}/hr/payroll/components`, body);
        setMsg(`Komponen ${f.code} ditambahkan.`);
      }
      setCompForm(null); await loadComps();
    } catch (e) { setFormErr(apiErrorText(e) || "Komponen gagal disimpan."); }
    finally { setBusy(""); }
  }

  const masukanOpts = comps.filter((c) => c.calc === "masukan" && c.is_active !== false).map((c) => ({ value: c.code, label: `${c.name} (${KIND_LABEL[c.kind] || ""})` }));
  async function bukaMasukan() {
    setFormErr("");
    setInpForm({ employee_id: "", component_code: masukanOpts[0]?.value || "", pay_period: period || curMonth(), amount: "", label: "", basis_period: "", reason: "" });
    try {
      const r = await axios.get(`${API}/hr/employees`, { params: { status: "active" } });
      setEmps((Array.isArray(r.data) ? r.data : []).map((e) => ({ value: e.id, label: e.name || e.code || e.id })));
    } catch (e) { setFormErr(`Daftar karyawan tidak bisa dimuat. ${apiErrorText(e) || ""}`.trim()); }
  }
  const ubahInp = (patch) => setInpForm((f) => ({ ...f, ...patch }));
  async function simpanMasukan() {
    const g = galatMasukan(inpForm);
    if (g) { setFormErr(g); return; }
    setBusy("masukan");
    try {
      const body = { ...inpForm, amount: Number(inpForm.amount) };
      const r = await intent.send(body, (k) => moneyPost(`${API}/hr/payroll/inputs`, body, k));
      setInpForm(null);
      setMsg(`Masukan ${r.data?.label || ""} ${formatCurrency(r.data?.amount)} dicatat, menunggu disahkan.`);
      await loadList();
    } catch (e) { setFormErr(apiErrorText(e) || "Masukan gagal dicatat."); }
    finally { setBusy(""); }
  }
  async function sahkan(row) {
    const ok = await askConfirm({
      title: `Sahkan masukan ${formatCurrency(row.amount)}?`,
      message: `${row.label} untuk ${row.employee_name} · periode bayar ${formatPeriod(row.pay_period)} · ${pt}. Sesudah disahkan, masukan ini ikut dihitung di proses gaji periode itu.`,
      confirmLabel: "Sahkan",
    });
    if (!ok) return;
    setBusy(`ok-${row.id}`);
    try {
      await intent.send({ id: row.id, aksi: "sahkan" }, (k) => moneyPost(`${API}/hr/payroll/inputs/${row.id}/approve`, {}, k));
      setMsg(`Masukan ${row.label} disahkan.`); await loadList();
    }
    catch (e) { setListErr(apiErrorText(e) || ""); setMsg(""); setListState("error"); }
    finally { setBusy(""); }
  }
  async function batalkan(row) {
    const reason = await askReason({
      title: `Batalkan masukan ${formatCurrency(row.amount)}?`,
      description: `${row.label} untuk ${row.employee_name} · periode bayar ${formatPeriod(row.pay_period)} · ${pt}. Masukan yang dibatalkan tidak ikut proses gaji.`,
      confirmLabel: "Batalkan masukan",
      reasonPlaceholder: "Contoh: nominal bonus salah ketik",
      danger: true,
    });
    if (!reason) return;
    setBusy(`x-${row.id}`);
    try {
      const body = { reason };
      await intent.send({ id: row.id, aksi: "batal", ...body }, (k) => moneyPost(`${API}/hr/payroll/inputs/${row.id}/cancel`, body, k));
      setMsg(row.status === "used" ? `Masukan ${row.label} dibatalkan. Hitung ulang penggajian ${row.used_run_number || ""} sebelum diajukan.` : `Masukan ${row.label} dibatalkan.`);
      await loadList();
    } catch (e) { setListErr(apiErrorText(e) || ""); setListState("error"); }
    finally { setBusy(""); }
  }

  const alasanKomp = alasanTambahKomponen({ canWrite, canManage });
  const alasanInp = alasanTambahMasukan({ canWrite, canCreate });
  const periodOpts = [{ value: "", label: "Semua periode" }, ...recentMonths().map((m) => ({ value: m, label: formatPeriod(m) }))];
  const monthOpts = recentMonths().map((m) => ({ value: m, label: formatPeriod(m) }));
  const rows = list.items || [];
  const f = compForm;

  return (
    <div className="space-y-4" data-testid="paycomp-view">
      <EntityScopeBanner testId="paycomp-scope" />
      {msg && <div className="notice-bar success" data-testid="paycomp-msg"><span className="text-fs-12">{msg}</span><button type="button" className="icon-button" aria-label="Tutup" onClick={() => setMsg("")}>×</button></div>}

      {/* ── Komponen gaji ── */}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h2 className="flex items-center gap-2" data-testid="paycomp-title"><Layers size={16} className="text-kn-action" aria-hidden="true" />Komponen gaji</h2>
          <button type="button" data-testid="paycomp-refresh" onClick={loadComps} className="secondary-button btn-sm ml-auto whitespace-nowrap"><RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2">Daftar baris yang bisa muncul di slip gaji {pt}. Komponen bawaan tidak bisa dihapus atau diganti jenisnya; komponen baru berjenis hitung masukan (nilainya dari daftar Masukan di bawah).</p>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" data-testid="paycomp-add" disabled={!!alasanKomp} onClick={() => bukaKomponen()} className="primary-button btn-sm whitespace-nowrap"><Plus size={13} /> Tambah komponen</button>
            {alasanKomp && <span className="text-fs-12 text-kn-text-2" data-testid="paycomp-add-why">{alasanKomp}</span>}
          </div>
        </div>
        {!canWrite ? (
          <div className="section-pad text-fs-13 text-kn-text-2" data-testid="paycomp-all-pt">Komponen gaji diatur per PT. {TEKS_SEMUA_PT} di pemilih PT (kanan atas) untuk melihatnya.</div>
        ) : compState === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="paycomp-loading">Memuat komponen…</div>
        ) : compState === "error" ? (
          <div className="section-pad"><ErrorNotice testId="paycomp-error" message={`Komponen gaji tidak bisa dimuat. ${compErr}`.trim()} onRetry={loadComps} /></div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="paycomp-table">
                <thead><tr>
                  <th>Kode</th><th>Nama</th><th>Jenis</th><th>Cara hitung</th><th>Kena pajak</th>
                  <th>Dasar BPJS*</th><th>Dasar lembur*</th><th>Diprorata*</th><th>Akun</th><th>Aktif</th>
                  {canManage && <th className="col-sticky-end">Aksi</th>}
                </tr></thead>
                <tbody>
                  {comps.map((c) => (
                    <tr key={c.id} data-testid={`paycomp-row-${c.code}`}>
                      <td className="font-mono whitespace-nowrap">{c.code}</td>
                      <td className="min-w-[140px]">{c.name}{c.system && <span className="block text-fs-12 text-kn-text-2">Bawaan</span>}</td>
                      <td>{KIND_LABEL[c.kind] || "—"}</td>
                      <td>{CALC_LABEL[c.calc] || "—"}</td>
                      <td><YaTidak v={c.taxable} /></td>
                      <td><YaTidak v={c.in_bpjs_base} /></td>
                      <td><YaTidak v={c.in_overtime_base} /></td>
                      <td><YaTidak v={c.prorate} /></td>
                      <td className="font-mono whitespace-nowrap">{c.account_code || <span className="font-sans text-kn-text-2">Bawaan</span>}</td>
                      <td>{c.is_active !== false
                        ? <span className="status-pill status-done inline-flex items-center gap-1 whitespace-nowrap"><CheckCircle2 size={12} aria-hidden="true" />Aktif</span>
                        : <span className="status-pill status-rejected inline-flex items-center gap-1 whitespace-nowrap"><Ban size={12} aria-hidden="true" />Nonaktif</span>}</td>
                      {canManage && <td className="col-sticky-end"><button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`paycomp-edit-${c.code}`} onClick={() => bukaKomponen(c)}><Pencil size={12} /> Ubah</button></td>}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="section-pad !pt-2 text-fs-12 text-kn-text-2" data-testid="paycomp-unused-note">* Dasar BPJS, Dasar lembur, dan Diprorata disimpan tetapi belum dipakai hitungan gaji: iuran BPJS dan upah lembur masih dihitung dari gaji pokok, dan gaji belum diprorata.</p>
          </>
        )}
      </div>

      {/* ── Masukan ── */}
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h2 className="flex items-center gap-2"><ListPlus size={16} className="text-kn-action" aria-hidden="true" />Masukan</h2>
          <button type="button" data-testid="payinput-refresh" onClick={loadList} className="secondary-button btn-sm ml-auto whitespace-nowrap"><RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2">Nilai komponen masukan (bonus, THR, potongan, penyesuaian) yang ikut proses gaji periode bayarnya. Isian manual ikut dihitung sesudah disahkan.</p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-[180px]"><label className="field-label">Periode bayar</label>
              <KNSelect data-testid="payinput-period" value={period} onValueChange={(v) => { setPeriod(v); setPage(1); }} className="field" options={periodOpts} /></div>
            <button type="button" data-testid="payinput-add" disabled={!!alasanInp || masukanOpts.length === 0} onClick={bukaMasukan} className="primary-button btn-sm whitespace-nowrap"><Plus size={13} /> Tambah masukan</button>
            {(alasanInp || (canWrite && compState === "ready" && masukanOpts.length === 0)) && <span className="text-fs-12 text-kn-text-2" data-testid="payinput-add-why">{alasanInp || "Belum ada komponen masukan yang aktif."}</span>}
          </div>
          <FilterChips testId="payinput-status" value={status} ariaLabel="Status masukan" onChange={(k) => { setStatus(k || "semua"); setPage(1); }} options={STATUS_CHIPS} />
        </div>
        {listState === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="payinput-loading">Memuat masukan…</div>
        ) : listState === "error" ? (
          <div className="section-pad"><ErrorNotice testId="payinput-error" message={`Masukan tidak bisa dimuat atau diproses. ${listErr}`.trim()} onRetry={loadList} /></div>
        ) : rows.length === 0 ? (
          <div className="section-pad py-6 text-center text-fs-13 text-kn-text-2" data-testid="payinput-empty">Belum ada masukan untuk periode ini.</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="payinput-table">
                <thead><tr>
                  <th>Karyawan</th><th>Komponen</th><th>Keterangan</th><th>Periode dasar</th><th className="text-right">Nominal</th>
                  <th>Sumber</th><th>Status</th><th>Dipakai di</th>
                  {(canApprove) && <th className="col-sticky-end">Aksi</th>}
                </tr></thead>
                <tbody>
                  {rows.map((d) => (
                    <tr key={d.id} data-testid={`payinput-row-${d.id}`}>
                      <td className="min-w-[120px]">{d.employee_name || "—"}</td>
                      <td className="whitespace-nowrap">{d.component_name || d.component_code}</td>
                      <td className="max-w-[200px] break-words">{d.label}{d.reason && <span className="block text-fs-12 text-kn-text-2">{d.reason}</span>}</td>
                      <td className="whitespace-nowrap">{d.basis_period ? formatPeriod(d.basis_period) : "—"}</td>
                      <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(d.amount)}</td>
                      <td className="whitespace-nowrap">{SOURCE_LABEL[d.source_type] || "—"}{d.source_ref?.number && <span className="block text-fs-12 text-kn-text-2">{d.source_ref.number}</span>}</td>
                      <td><InputStatus status={d.status} testId={`payinput-status-${d.id}`} /></td>
                      <td className="whitespace-nowrap">{d.used_run_number || "—"}</td>
                      {canApprove && (
                        <td className="col-sticky-end">
                          <div className="flex flex-wrap items-center gap-1.5">
                            {d.status === "pending" && <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid={`payinput-approve-${d.id}`} disabled={!!busy} onClick={() => sahkan(d)}><CheckCircle2 size={12} /> Sahkan</button>}
                            {["pending", "approved", "used"].includes(d.status) && <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`payinput-cancel-${d.id}`} disabled={!!busy} onClick={() => batalkan(d)}><Ban size={12} /> Batalkan</button>}
                          </div>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2">
              <span data-testid="payinput-count">{list.total || 0} masukan</span>
              <KNPager page={page} pageSize={PAGE_SIZE} total={list.total || 0} onChange={setPage} testId="payinput-pager" />
            </div>
          </>
        )}
        {!canApprove && rows.length > 0 && <p className="section-pad !pt-0 text-fs-12 text-kn-text-2" data-testid="payinput-no-approve">Mengesahkan atau membatalkan masukan butuh izin mengesahkan gaji.</p>}
      </div>

      {/* ── Pop-up komponen ── */}
      <FormModal open={!!f} onClose={() => setCompForm(null)} title={f?.id ? `Ubah komponen ${f.code}` : "Tambah komponen gaji"} subtitle={pt} icon={Layers}
        testId="paycomp-form" onSubmit={simpanKomponen} submitLabel="Simpan komponen" busy={busy === "komponen"} error={formErr}>
        {f && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="field-label">Kode <span className="req">*</span></label>
              <input data-testid="paycomp-form-code" className="field font-mono" value={f.code} disabled={!!f.id} onChange={(e) => ubahKomp({ code: e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "") })} placeholder="Contoh: BONUS" /></div>
            <div><label className="field-label">Nama di slip <span className="req">*</span></label>
              <input data-testid="paycomp-form-name" className="field" value={f.name} onChange={(e) => ubahKomp({ name: e.target.value })} placeholder="Contoh: Bonus kinerja" /></div>
            <div><label className="field-label">Jenis <span className="req">*</span></label>
              <KNSelect data-testid="paycomp-form-kind" value={f.kind} className="field" disabled={!!f.id}
                onValueChange={(v) => ubahKomp({ kind: v, taxable: v === "pendapatan" })}
                options={[{ value: "pendapatan", label: "Pendapatan" }, { value: "potongan", label: "Potongan" }, ...(f.id && f.kind === "tanggungan_perusahaan" ? [{ value: "tanggungan_perusahaan", label: "Tanggungan perusahaan" }] : [])]} />
              <p className="text-fs-12 text-kn-text-2 mt-1">{f.id ? "Jenis tidak bisa diubah." : "Cara hitung: masukan (nilai dari daftar Masukan)."}</p></div>
            <div><label className="field-label">Akun{f.kind === "potongan" && f.calc !== "undang_undang" ? <span className="req"> *</span> : ""}</label>
              <input data-testid="paycomp-form-account" className="field font-mono" value={f.account_code || ""} disabled={f.calc === "undang_undang" || f.bucket === "commission"}
                onChange={(e) => ubahKomp({ account_code: e.target.value.trim() })} placeholder={f.kind === "potongan" ? "Akun yang dikredit, mis. 1-1400" : "Kosong = akun beban gaji bawaan"} />
              <p className="text-fs-12 text-kn-text-2 mt-1">{f.calc === "undang_undang" || f.bucket === "commission" ? "Komponen ini memakai akun bawaannya." : "Kode akun aktif di bagan akun PT ini."}</p></div>
            {f.kind === "pendapatan" && !f.system && (
              <label className="flex items-center gap-2 text-fs-13"><input type="checkbox" data-testid="paycomp-form-taxable" checked={!!f.taxable} onChange={(e) => ubahKomp({ taxable: e.target.checked })} /> Kena pajak (masuk bruto PPh 21)</label>
            )}
            {!f.system && (
              <fieldset className="sm:col-span-2"><legend className="field-label">Dimuat di proses gaji <span className="req">*</span></legend>
                <div className="flex flex-wrap gap-4 text-fs-13">
                  {Object.entries(RUN_TYPE_LABEL).map(([k, lbl]) => (
                    <label key={k} className="flex items-center gap-2"><input type="checkbox" data-testid={`paycomp-form-rt-${k}`} checked={(f.allowed_run_types || []).includes(k)} onChange={() => toggleRunType(k)} /> {lbl}</label>
                  ))}
                </div></fieldset>
            )}
            {f.id && !f.system && (
              <label className="flex items-center gap-2 text-fs-13"><input type="checkbox" data-testid="paycomp-form-active" checked={f.is_active !== false} onChange={(e) => ubahKomp({ is_active: e.target.checked })} /> Aktif</label>
            )}
            <div><label className="field-label">Urutan di slip</label>
              <input data-testid="paycomp-form-sort" className="field" inputMode="numeric" value={f.sort ?? ""} onChange={(e) => ubahKomp({ sort: e.target.value.replace(/[^\d]/g, "") })} /></div>
            <fieldset className="sm:col-span-2"><legend className="field-label">Tanda (disimpan, belum dipakai hitungan gaji)</legend>
              <div className="flex flex-wrap gap-4 text-fs-13">
                <label className="flex items-center gap-2"><input type="checkbox" checked={!!f.in_bpjs_base} onChange={(e) => ubahKomp({ in_bpjs_base: e.target.checked })} /> Dasar BPJS</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={!!f.in_overtime_base} onChange={(e) => ubahKomp({ in_overtime_base: e.target.checked })} /> Dasar lembur</label>
                <label className="flex items-center gap-2"><input type="checkbox" checked={!!f.prorate} onChange={(e) => ubahKomp({ prorate: e.target.checked })} /> Diprorata</label>
              </div></fieldset>
          </div>
        )}
      </FormModal>

      {/* ── Pop-up masukan ── */}
      <FormModal open={!!inpForm} onClose={() => setInpForm(null)} title="Tambah masukan gaji" subtitle={pt} icon={ListPlus}
        testId="payinput-form" onSubmit={simpanMasukan} submitLabel="Simpan masukan" busy={busy === "masukan"} error={formErr}>
        {inpForm && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div><label className="field-label">Karyawan <span className="req">*</span></label>
              <KNSelect data-testid="payinput-form-emp" value={inpForm.employee_id} className="field" onValueChange={(v) => ubahInp({ employee_id: v })} options={emps} placeholder="Pilih karyawan" /></div>
            <div><label className="field-label">Komponen <span className="req">*</span></label>
              <KNSelect data-testid="payinput-form-comp" value={inpForm.component_code} className="field" onValueChange={(v) => ubahInp({ component_code: v })} options={masukanOpts} /></div>
            <div><label className="field-label">Periode bayar <span className="req">*</span></label>
              <KNSelect data-testid="payinput-form-period" value={inpForm.pay_period} className="field" onValueChange={(v) => ubahInp({ pay_period: v })} options={monthOpts} /></div>
            <div><label className="field-label">Nominal (Rp) <span className="req">*</span></label>
              <input data-testid="payinput-form-amount" className="field" inputMode="numeric" value={inpForm.amount} onChange={(e) => ubahInp({ amount: e.target.value.replace(/[^\d-]/g, "") })} />
              <p className="text-fs-12 text-kn-text-2 mt-1">Rupiah bulat; negatif untuk penyesuaian.</p></div>
            <div className="sm:col-span-2"><label className="field-label">Keterangan di slip</label>
              <input data-testid="payinput-form-label" className="field" value={inpForm.label} onChange={(e) => ubahInp({ label: e.target.value })} placeholder="Contoh: Bonus proyek Oktober" /></div>
            <div className="sm:col-span-2"><label className="field-label">Alasan <span className="req">*</span></label>
              <input data-testid="payinput-form-reason" className="field" value={inpForm.reason} onChange={(e) => ubahInp({ reason: e.target.value })} placeholder="Contoh: persetujuan direksi 3 Nov" /></div>
          </div>
        )}
      </FormModal>
    </div>
  );
}
