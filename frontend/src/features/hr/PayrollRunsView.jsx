/**
 * PayrollRunsView — SDM › Penggajian › Proses Gaji.
 *
 * Daur proses (PK-22): Draf → Diajukan → Disahkan → Diposting → Dibayar; Batalkan dari tiga status pertama; Anulir dari
 * Diposting (jurnal gaji dibalik; izin `payroll.void`). Tiap tombol mengikuti izin `payroll.*` (`canCurrent`), bukan nama peran:
 *   create = Hitung gaji · Hitung Ulang · Ajukan · Batalkan draf   approve = Sahkan · Kembalikan · Batalkan yang diajukan
 *   post = Posting Jurnal   void = Anulir   pay = Bayar
 * Aksi uang meminta konfirmasi yang menyebut periode, jumlah karyawan, gaji bersih, dan PT; batal & void meminta alasan.
 * Jurnal gagal (posting) tampil di bilah sendiri; prosesnya tetap Disahkan dan bisa diulang dari Posting Gagal.
 */
import { useEffect, useMemo, useState } from "react";
import { apiErrorText } from "../../utils/apiError";
import axios, { API } from "../../services/apiClient";
import { Ban, Banknote, BookCheck, Calculator, CheckCircle2, Circle, Clock, FileText, Plus, RefreshCw, RotateCcw,
  Send, Undo2, XCircle } from "lucide-react";
import { askConfirm, askReason } from "../../services/confirmService";
import KNSelect from "../../components/KNSelect";
import EntityBadge from "../../components/EntityBadge";
import ErrorNotice from "../../components/ErrorNotice";
import FocusNotice from "../../components/FocusNotice";
import { JournalStatusBar } from "../../components/JournalStatusBadge";
import useFocusDoc from "../../hooks/useFocusDoc";
import useIntentKey from "../../hooks/useIntentKey";
import { moneyPost } from "../../utils/moneyRequest";
import { canCurrent } from "../../config/roles";
import { rp, pct, RUN_STATUS, CAN_CANCEL, CAN_RECALC, CAN_VOID, recentMonths, curMonth } from "./payrollUtils";
import { entityFullById, entityOptions } from "../../utils/entityLabel";
import { formatDate, formatPeriod } from "../../utils/formatters";

const ICON = { draft: Circle, pending_approval: Clock, approved: CheckCircle2, posting: Clock, posted: BookCheck,
  paying: Clock, paid: Banknote, cancelled: Ban, voiding: Clock, void: XCircle };

/** Status proses gaji: ikon + teks + warna (bukan warna saja). */
export function PayrollRunStatus({ status, testId }) {
  const st = RUN_STATUS[status] || RUN_STATUS.draft;
  const Icon = ICON[status] || Circle;
  return (
    <span className={`status-pill ${st.cls} inline-flex items-center gap-1 whitespace-nowrap`} data-testid={testId}>
      <Icon size={12} aria-hidden="true" />{st.label}</span>
  );
}

function Stat({ label, value, tone = "text-kn-text" }) {
  return (
    <div className="section-card section-pad">
      <p className="text-fs-12 font-semibold text-kn-text-2">{label}</p>
      <p className={`text-fs-14 font-bold tabular-nums leading-tight ${tone}`}>{value}</p>
    </div>
  );
}

/** Izin tiap langkah (`payroll.<aksi>`) — dibaca sekali per render. */
export function payrollPerms() {
  return { create: canCurrent("payroll", "create"), approve: canCurrent("payroll", "approve"),
    post: canCurrent("payroll", "post"), void: canCurrent("payroll", "void"), pay: canCurrent("payroll", "pay") };
}

/** Langkah berikutnya yang tertahan izin → kalimat alasan (ditulis di layar, bukan tooltip). */
export function nextStepHint(status, perms) {
  if (status === "draft" && !perms.create) return "Menyiapkan penggajian butuh izin menyiapkan gaji.";
  if (status === "pending_approval" && !perms.approve) return "Mengesahkan penggajian butuh izin mengesahkan gaji.";
  if (status === "approved" && !perms.post) return "Memposting jurnal gaji butuh izin memposting gaji.";
  if (status === "posted" && !perms.pay) return "Membayar gaji butuh izin membayar gaji.";
  return "";
}

export default function PayrollRunsView({ selectedEntity, focusDoc, onClearFocus }) {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [entities, setEntities] = useState([]);
  const [form, setForm] = useState({ entity_id: "", period: curMonth() });
  const [busy, setBusy] = useState("");
  const [sel, setSel] = useState(null);
  const intent = useIntentKey("gaji");
  const perms = payrollPerms();

  const params = useMemo(() => (selectedEntity && selectedEntity !== "all" ? { entity_id: selectedEntity } : {}), [selectedEntity]);

  useEffect(() => { loadRuns(); }, [selectedEntity]); // eslint-disable-line
  useEffect(() => {
    axios.get(`${API}/entities`).then((r) => {
      const list = Array.isArray(r.data) ? r.data : [];
      setEntities(list);
      setForm((f) => ({ ...f, entity_id: (selectedEntity && selectedEntity !== "all") ? selectedEntity : (list[0]?.id || "") }));
    }).catch(() => {});
  }, [selectedEntity]); // eslint-disable-line

  async function loadRuns() {
    setLoading(true);
    try { const r = await axios.get(`${API}/hr/payroll/runs`, { params }); setRuns(Array.isArray(r.data) ? r.data : []); setError(""); }
    catch (e) { setError(apiErrorText(e, "Gagal memuat daftar penggajian.")); }
    finally { setLoading(false); }
  }
  async function openRun(id) {
    try { const r = await axios.get(`${API}/hr/payroll/runs/${id}`); setSel(r.data || null); }
    catch (e) { setError(apiErrorText(e, "Gagal memuat rincian penggajian.")); }
  }
  async function createRun() {
    if (!form.entity_id || !form.period) { setError("Pilih PT & periode."); return; }
    setBusy("create");
    try {
      const r = await axios.post(`${API}/hr/payroll/runs`, { entity_id: form.entity_id, period: form.period });
      setNotice(`Penggajian ${r.data.number} siap (${r.data.totals.employees} karyawan).`); setError("");
      await loadRuns(); setSel(r.data);
    } catch (e) { setError(apiErrorText(e, "Gagal menghitung penggajian.")); }
    finally { setBusy(""); }
  }

  const ptName = (run) => entityFullById(entities, run?.entity_id, "PT ini");
  const ringkas = (run) => `${formatPeriod(run.period)} · ${run.totals?.employees ?? 0} karyawan · gaji bersih `
    + `${rp(run.totals?.net)} · ${ptName(run)}.`;

  // UAT 24 Okt (audit UI tahap 2) — G5-33: Sahkan / Posting / Bayar menulis jurnal & mengunci gaji → konfirmasi dulu
  // dengan periode, total, PT, dan akibatnya (PK-22: `02` N5).
  const ACT_CONFIRM = {
    approve: { title: "Sahkan penggajian", effect: "Gaji periode ini dikunci; perubahan berikutnya harus lewat pengembalian ke draf.", label: "Sahkan" },
    "post-gl": { title: "Posting jurnal gaji", effect: "Jurnal beban gaji & utang gaji dibuat di buku besar, bertanggal akhir periode gajinya.", label: "Posting" },
    pay: { title: "Catat pembayaran gaji", effect: "Jurnal pembayaran gaji dan kas keluar dibuat.", label: "Catat pembayaran" },
    recalculate: { title: "Hitung ulang penggajian", effect: "Slip dihitung lagi dari data karyawan, lembur, dan komisi terbaru.", label: "Hitung ulang" },
  };
  async function act(id, action, label) {
    const c = ACT_CONFIRM[action];
    if (c && sel) {
      const ok = await askConfirm({
        title: `${c.title} ${sel.number}?`,
        message: `${ringkas(sel)} ${c.effect}`,
        confirmLabel: c.label,
        danger: action === "pay",
      });
      if (!ok) return;
    }
    setBusy(action);
    try {
      // Path eksplisit (literal) — agar kontrak FE↔BE terverifikasi statis.
      let r;
      if (action === "submit") r = await axios.post(`${API}/hr/payroll/runs/${id}/submit`);
      else if (action === "approve") r = await axios.post(`${API}/hr/payroll/runs/${id}/approve`);
      else if (action === "recalculate") r = await axios.post(`${API}/hr/payroll/runs/${id}/recalculate`);
      else if (action === "post-gl") r = await intent.send({ id, action }, (k) => moneyPost(`${API}/hr/payroll/runs/${id}/post-gl`, {}, k));
      else r = await intent.send({ id, action }, (k) => moneyPost(`${API}/hr/payroll/runs/${id}/pay`, {}, k));
      const failed = action === "post-gl" && r.data?.gl_status === "failed";
      setNotice(failed ? `Jurnal gaji ${r.data.number} gagal — penggajian tetap Disahkan. Perbaiki penyebabnya lalu posting lagi.`
        : `${label} berhasil.`);
      setError("");
      setSel(r.data); await loadRuns();
      if (failed) window.dispatchEvent(new CustomEvent("kn-posting-failures-changed"));
    } catch (e) { setError(apiErrorText(e, `Gagal: ${label}.`)); }
    finally { setBusy(""); }
  }

  // UTANG ALUR F-6.7 — kembalikan payroll yang diajukan ke draf. Alasan WAJIB dan ditanyakan lewat `askReason()`.
  async function rejectRun(id) {
    const reason = await askReason({
      title: "Kembalikan penggajian ini ke draf?",
      description: "Penggajian akan kembali bisa diubah HR. Alasannya tersimpan di dokumen.",
      confirmLabel: "Kembalikan ke draf",
      reasonPlaceholder: "Contoh: tunjangan transport 3 karyawan belum masuk",
      danger: true,
    });
    if (!reason) return;
    setBusy("reject");
    try {
      const r = await axios.post(`${API}/hr/payroll/runs/${id}/reject`, { reason });
      setNotice("Penggajian dikembalikan ke draf."); setError("");
      setSel(r.data); await loadRuns();
    } catch (e) { setError(apiErrorText(e, "Gagal mengembalikan penggajian.")); }
    finally { setBusy(""); }
  }

  // PK-22 — batal (tanpa jurnal) dan anulir (jurnal dibalik): alasan wajib, pesan menyebut periode, nominal, PT.
  async function cancelRun(run) {
    const reason = await askReason({
      title: `Batalkan penggajian ${run.number}?`,
      description: `${ringkas(run)} Slip ikut dibatalkan; belum ada jurnal yang dibuat. Proses baru untuk periode ini bisa dibuat sesudahnya.`,
      confirmLabel: "Batalkan penggajian",
      reasonPlaceholder: "Contoh: periode lembur salah, akan dihitung ulang",
      danger: true,
    });
    if (!reason) return;
    setBusy("cancel");
    try {
      const r = await axios.post(`${API}/hr/payroll/runs/${run.id}/cancel`, { reason });
      setNotice(`Penggajian ${run.number} dibatalkan.`); setError("");
      setSel(r.data); await loadRuns();
    } catch (e) { setError(apiErrorText(e, "Gagal membatalkan penggajian.")); }
    finally { setBusy(""); }
  }
  async function voidRun(run) {
    const reason = await askReason({
      title: `Anulir penggajian ${run.number}?`,
      description: `${ringkas(run)} Jurnal gaji akan dibalik.`,
      confirmLabel: "Anulir",
      reasonPlaceholder: "Contoh: tunjangan transport salah hitung",
      danger: true,
    });
    if (!reason) return;
    setBusy("void");
    try {
      const body = { reason };
      const r = await intent.send({ id: run.id, ...body }, (k) => moneyPost(`${API}/hr/payroll/runs/${run.id}/void`, body, k));
      setNotice(`Penggajian ${run.number} dianulir; jurnal gaji dibalik.`); setError("");
      setSel(r.data); await loadRuns();
    } catch (e) { setError(apiErrorText(e, "Gagal menganulir penggajian.")); }
    finally { setBusy(""); }
  }

  // `/api/entities` tak punya field `name` — dulu label pilihan entitas KOSONG.
  const entOpts = entityOptions(entities);
  const monthOpts = recentMonths().map((m) => ({ value: m, label: formatPeriod(m) }));
  // Audit UI 24 Okt (082): daftar run dulu tidak kronologis (PR-00002 2026-08 di atas PR-00001 2026-09).
  const sortedRuns = [...runs].sort((a, b) => String(b.period || "").localeCompare(String(a.period || ""))
    || String(b.number || "").localeCompare(String(a.number || "")));
  // PK-44 (IA-10) — tautan dokumen (Jejak Dokumen / rincian jurnal gaji) membuka rincian penggajian ber-id itu.
  const fokus = useFocusDoc(focusDoc, "payroll_run", async (id) => {
    setSel((await axios.get(`${API}/hr/payroll/runs/${id}`)).data || null);
  }, onClearFocus);

  const st = sel?.status;
  const hint = sel ? nextStepHint(st, perms) : "";
  const bisaBatal = sel && CAN_CANCEL.includes(st) && (st === "draft" ? perms.create : perms.approve);

  return (
    <div data-testid="payroll-runs-view">
      {notice && (<div className="notice-bar success" data-testid="payroll-notice"><span>{notice}</span><button type="button" className="icon-button" aria-label="Tutup" onClick={() => setNotice("")}>×</button></div>)}
      <ErrorNotice message={error} onRetry={loadRuns} onDismiss={() => setError("")} testId="payroll-runs-error" />
      <FocusNotice {...fokus} testId="payroll-focus-notice" />

      {/* Buat proses */}
      <div className="section-card mb-3">
        <div className="section-head"><div className="flex items-center gap-2"><Calculator size={16} className="text-kn-action" /><h2 data-testid="payroll-runs-title">Penggajian</h2></div>
          <button type="button" data-testid="payroll-runs-refresh" onClick={loadRuns} className="icon-button" title="Muat ulang" aria-label="Muat ulang"><RefreshCw size={15} /></button>
        </div>
        <div className="section-body grid grid-cols-1 gap-2 md:grid-cols-[1fr_180px_auto] items-end">
          <div><label className="field-label">PT <span className="req">*</span></label>
            <KNSelect data-testid="payroll-create-entity" value={form.entity_id} onValueChange={(v) => setForm((f) => ({ ...f, entity_id: v }))} className="field" options={entOpts} placeholder="Pilih PT" /></div>
          <div><label className="field-label">Periode <span className="req">*</span></label>
            <KNSelect data-testid="payroll-create-period" value={form.period} onValueChange={(v) => setForm((f) => ({ ...f, period: v }))} className="field" options={monthOpts} placeholder="Pilih periode" /></div>
          <button type="button" data-testid="payroll-create-submit" disabled={busy === "create" || !form.entity_id || !form.period || !perms.create} onClick={createRun} className="primary-button justify-center whitespace-nowrap">
            <Plus size={14} /> {busy === "create" ? "Memproses..." : form.period ? `Hitung gaji ${formatPeriod(form.period)}` : "Hitung gaji"}</button>
        </div>
        {!perms.create && <p className="section-body !pt-0 text-fs-12 text-kn-text-2" data-testid="payroll-create-no-perm">Menghitung gaji baru butuh izin menyiapkan gaji.</p>}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[300px_1fr]">
        {/* Daftar proses */}
        <div className="section-card">
          <div className="section-head"><h3 className="text-fs-12 font-bold text-kn-text-2">Daftar penggajian</h3></div>
          {loading ? (
            <div className="section-pad text-center text-fs-12 text-kn-text-2" data-testid="payroll-runs-loading" role="status">Memuat...</div>
          ) : runs.length === 0 ? (
            <div className="section-pad text-center text-fs-12 text-kn-text-2" data-testid="payroll-runs-empty"><Calculator className="mx-auto mb-2 text-kn-text-2" size={26} aria-hidden="true" /><p>Belum ada penggajian.</p></div>
          ) : (
            <div className="divide-y divide-kn-divider max-h-[560px] overflow-y-auto">
              {sortedRuns.map((r) => (
                <button type="button" key={r.id} data-testid={`payroll-run-${r.id}`} onClick={() => openRun(r.id)}
                  className={`link-button block w-full text-left px-3 py-2 no-underline ${sel?.id === r.id ? "bg-kn-action-soft" : ""}`}>
                  <span className="flex items-center justify-between gap-2"><span className="text-fs-13 font-semibold text-kn-text">{r.number}</span><PayrollRunStatus status={r.status} /></span>
                  <span className="flex items-center gap-2 mt-1 text-fs-12 text-kn-text-2"><EntityBadge entityId={r.entity_id} /><span>{formatPeriod(r.period)}</span><span className="ml-auto tabular-nums">{rp(r.totals?.net)}</span></span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Rincian proses */}
        <div className="section-card">
          {!sel ? (
            <div className="section-pad text-center text-fs-12 text-kn-text-2" data-testid="payroll-detail-empty"><FileText className="mx-auto mb-2 text-kn-text-2" size={28} aria-hidden="true" /><p>Pilih penggajian untuk melihat rincian slip gaji & alur persetujuan.</p></div>
          ) : (
            <div data-testid="payroll-run-detail">
              <div className="section-head">
                <div className="flex flex-wrap items-center gap-2"><h2>{sel.number} · {formatPeriod(sel.period)}</h2><PayrollRunStatus status={st} testId="payroll-detail-status" /></div>
              </div>
              <div className="section-body">
                {/* Bilah aksi sendiri (bukan di kepala kartu) */}
                <div className="flex flex-wrap items-center gap-2 mb-3" data-testid="payroll-actions">
                  {st === "draft" && perms.create && <>
                    <button type="button" data-testid="payroll-submit" disabled={!!busy} onClick={() => act(sel.id, "submit", "Ajukan")} className="primary-button btn-sm whitespace-nowrap"><Send size={13} /> Ajukan</button>
                    {CAN_RECALC.includes(st) && <button type="button" data-testid="payroll-recalc" disabled={!!busy} onClick={() => act(sel.id, "recalculate", "Hitung ulang")} className="secondary-button btn-sm whitespace-nowrap"><RotateCcw size={13} /> {busy === "recalculate" ? "Menghitung..." : "Hitung Ulang"}</button>}
                  </>}
                  {st === "pending_approval" && perms.approve && <>
                    <button type="button" data-testid="payroll-approve" disabled={!!busy} onClick={() => act(sel.id, "approve", "Sahkan")} className="primary-button btn-sm whitespace-nowrap"><CheckCircle2 size={13} /> Sahkan</button>
                    <button type="button" data-testid="payroll-reject" disabled={!!busy} onClick={() => rejectRun(sel.id)} className="secondary-button btn-sm whitespace-nowrap"><Undo2 size={13} /> Kembalikan ke Draf</button>
                  </>}
                  {st === "approved" && perms.post && <button type="button" data-testid="payroll-post-gl" disabled={!!busy} onClick={() => act(sel.id, "post-gl", "Posting jurnal")} className="primary-button btn-sm whitespace-nowrap"><BookCheck size={13} /> {sel.gl_status === "failed" ? "Posting Ulang" : "Posting Jurnal"}</button>}
                  {st === "posted" && perms.pay && <button type="button" data-testid="payroll-pay" disabled={!!busy} onClick={() => act(sel.id, "pay", "Bayar")} className="primary-button btn-sm whitespace-nowrap"><Banknote size={13} /> Bayar</button>}
                  {bisaBatal && <button type="button" data-testid="payroll-cancel" disabled={!!busy} onClick={() => cancelRun(sel)} className="secondary-button btn-sm whitespace-nowrap"><Ban size={13} /> Batalkan</button>}
                  {CAN_VOID.includes(st) && perms.void && <button type="button" data-testid="payroll-void" disabled={!!busy} onClick={() => voidRun(sel)} className="danger-button btn-sm whitespace-nowrap"><XCircle size={13} /> Anulir</button>}
                  {hint && <span className="text-fs-12 text-kn-text-2" data-testid="payroll-next-hint">{hint}</span>}
                  {st === "paid" && <span className="text-fs-12 text-kn-text-2" data-testid="payroll-paid-hint">Gaji yang sudah dibayar tidak bisa dianulir; koreksinya lewat proses susulan.</span>}
                </div>
                <div className="grid gap-2 grid-cols-2 md:grid-cols-4 mb-3">
                  <Stat label="Karyawan" value={sel.totals?.employees ?? 0} />
                  <Stat label="Bruto" value={rp(sel.totals?.gross)} tone="text-kn-action" />
                  <Stat label="Potongan + pajak" value={rp((sel.totals?.bpjs_emp || 0) + (sel.totals?.pph21 || 0))} tone="text-kn-danger-text" />
                  <Stat label="Gaji bersih" value={rp(sel.totals?.net)} tone="text-kn-success-text" />
                </div>
                {sel.status === "approved" && <JournalStatusBar doc={sel} testId="payroll-gl-status" />}
                {sel.reject_reason && st === "draft" && (
                  <div className="notice-bar warning !mb-3" data-testid="payroll-reject-reason">
                    <span><b>Dikembalikan ke draf</b>{sel.rejected_by ? ` oleh ${sel.rejected_by}` : ""}: {sel.reject_reason}</span>
                  </div>
                )}
                {st === "cancelled" && (
                  <div className="notice-bar warning !mb-3" data-testid="payroll-cancel-reason">
                    <span><b>Dibatalkan</b>{sel.cancelled_by ? ` oleh ${sel.cancelled_by}` : ""}{sel.cancelled_at ? ` · ${formatDate(sel.cancelled_at)}` : ""}: {sel.cancel_reason}</span>
                  </div>
                )}
                {st === "void" && (
                  <div className="notice-bar warning !mb-3" data-testid="payroll-void-reason">
                    <span><b>Dianulir</b>{sel.voided_by ? ` oleh ${sel.voided_by}` : ""}{sel.void_journal_number ? ` · jurnal pembalik ${sel.void_journal_number}` : ""}: {sel.void_reason}</span>
                  </div>
                )}
                {sel.recalc_count > 0 && st === "draft" && (
                  <p className="text-fs-12 text-kn-text-2 mb-2" data-testid="payroll-recalc-info">Dihitung ulang {sel.recalc_count}× · terakhir oleh {sel.recalculated_by || "—"}{sel.recalculated_at ? `, ${formatDate(sel.recalculated_at)}` : ""}.</p>
                )}
                {(sel.journal_number || sel.paid_journal_number) && (
                  <div className="text-fs-12 text-kn-text-2 mb-2 flex flex-wrap gap-3">
                    {sel.journal_number && <span data-testid="payroll-journal-ref">Jurnal gaji: <b className="text-kn-action">{sel.journal_number}</b>{sel.journal_date ? ` · tanggal buku ${formatDate(sel.journal_date)}` : ""}</span>}
                    {sel.paid_journal_number && <span data-testid="payroll-paid-ref">Jurnal bayar: <b className="text-kn-success-text">{sel.paid_journal_number}</b></span>}
                  </div>
                )}
                <div className="overflow-x-auto">
                  <table className="data-table head-wrap w-full tabular-nums" data-testid="payroll-payslips-table">
                    <thead><tr>
                      <th className="text-left">Karyawan</th><th className="text-right">Pokok</th><th className="text-right">Tunjangan</th><th className="text-right">Lembur</th><th className="text-right">Komisi</th><th className="text-right">Bruto</th><th className="text-right">BPJS</th><th className="text-right">PPh 21</th><th className="text-right">Bersih</th>
                    </tr></thead>
                    <tbody>
                      {(sel.payslips || []).map((s) => (
                        <tr key={s.id} data-testid={`payslip-${s.id}`}>
                          <td className="text-left font-semibold">{s.employee_name}</td>
                          <td className="text-right">{rp(s.base_salary)}</td><td className="text-right">{rp(s.allowances)}</td><td className="text-right">{rp(s.overtime)}</td><td className="text-right">{rp(s.commission)}</td>
                          <td className="text-right font-semibold text-kn-action">{rp(s.gross)}</td><td className="text-right text-kn-danger-text">{rp(s.bpjs_emp_total)}</td><td className="text-right text-kn-danger-text" title={s.ter_category ? `Tarif efektif PPh 21 kategori ${s.ter_category}` : undefined}>{rp(s.pph21)} <span className="text-fs-12 text-kn-text-2">{pct(s.pph21_rate)}</span></td>
                          <td className="text-right font-bold text-kn-success-text">{rp(s.net)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
