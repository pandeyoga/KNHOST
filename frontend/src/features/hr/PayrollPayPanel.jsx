/**
 * PayrollPayPanel — PY-T4 (PY-11, K-41) · SDM › Penggajian › Setoran & Pajak › "Gaji siap dibayar" + pop-up Bayar gaji.
 *
 * Sumber: GET /api/hr/payroll/pay-queue (proses Diposting, tanpa rincian slip) · GET /api/hr/payroll/pay-accounts
 * (rekening berperuntukan Gaji, tanpa saldo) · GET …/runs/{id}/transfer-list · POST …/runs/{id}/pay
 * (`{account_id, paid_date}`, ber-Idempotency-Key). Semua butuh izin `payroll.pay` — Finance memegangnya tanpa `hr.view`,
 * jadi layar ini tidak membuka karyawan maupun slip rinci.
 *
 * Tabel antrean: Nomor · Periode · Jenis · Karyawan · Total bersih · aksi (kolom lekat kanan, `col-sticky-end`: "Daftar
 * transfer", "Bayar"). "Semua PT" → Bayar mati dengan "Pilih satu PT dulu." tertulis; PT tanpa rekening gaji → Bayar mati
 * dengan pesan cara mengaturnya. `PayDialog` dipakai juga tombol Bayar di rincian Proses Gaji.
 */
import { useCallback, useEffect, useState } from "react";
import { Banknote, ListChecks, Wallet } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import ErrorNotice from "../../components/ErrorNotice";
import FormModal from "../../components/FormModal";
import KNDatePicker from "../../components/KNDatePicker";
import KNPager from "../../components/KNPager";
import KNSelect from "../../components/KNSelect";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, formatPeriod, todayWib } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { moneyPost } from "../../utils/moneyRequest";
import useIntentKey from "../../hooks/useIntentKey";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";
import TransferListPanel from "./TransferListPanel";
import { runTypeLabel } from "./payrollUtils";

const PAGE_SIZE = 20;
export const TEKS_PILIH_PT = "Pilih satu PT dulu.";
export const TEKS_TANPA_REKENING_GAJI = "Belum ada rekening berperuntukan Gaji di PT ini. Atur di Keuangan › Kas & Bank › Rekening & Saldo.";
export const TEKS_ANTREAN_KOSONG = "Tidak ada penggajian yang menunggu dibayar.";

/** Label pilihan rekening: nama · bank · nomor (tanpa saldo). */
export const labelRekening = (a) => [a.name, a.bank_name || (a.cash_type === "kas_kecil" ? "Kas kecil" : ""), a.account_number]
  .filter(Boolean).join(" · ");

/** "Total bersih Rp … untuk {n} karyawan ({m} tanpa rekening, dibayar tunai)". */
export function ringkasBayar({ net, count, withoutAccount }) {
  const tunai = withoutAccount > 0 ? ` (${withoutAccount} tanpa rekening, dibayar tunai)` : "";
  return `Total bersih ${formatCurrency(net)} untuk ${count} karyawan${tunai}`;
}

/** Konfirmasi N5: "Bayar gaji {nomor} — {bulan tahun}? Rp … dari {nama rekening} · {nama PT}." */
export function konfirmasiBayar(run, rekening, pt) {
  return {
    title: `Bayar gaji ${run.number} — ${formatPeriod(run.period)}?`,
    message: `${formatCurrency(run.net)} dari ${rekening} · ${pt}.`,
  };
}

/** Alasan tombol Bayar mati (ditulis di samping tombol, bukan tooltip); "" = boleh. */
export function alasanTidakBisaBayar({ canWrite, canPay, adaRekening }) {
  if (!canPay) return "Membayar gaji butuh izin membayar gaji.";
  if (!canWrite) return TEKS_PILIH_PT;
  if (adaRekening === false) return TEKS_TANPA_REKENING_GAJI;
  return "";
}

/** Pop-up Bayar gaji. `run` = {id, number, period, entity_id, net, employees, journal_date?}. */
export function PayDialog({ run, open, onClose, onPaid, pt }) {
  const { canWrite } = useEntityScope();
  const [accs, setAccs] = useState([]);
  const [info, setInfo] = useState(null);
  const [state, setState] = useState("loading");
  const [loadErr, setLoadErr] = useState("");
  const [acc, setAcc] = useState("");
  const [tgl, setTgl] = useState(todayWib());
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const intent = useIntentKey("bayar-gaji");

  useEffect(() => {
    if (!open || !run?.id) return undefined;
    let batal = false;
    setState("loading"); setErr(""); setTgl(todayWib());
    Promise.all([
      axios.get(`${API}/hr/payroll/pay-accounts`, { params: { entity_id: run.entity_id } }),
      axios.get(`${API}/hr/payroll/runs/${run.id}/transfer-list`),
    ]).then(([a, t]) => {
      if (batal) return;
      const list = Array.isArray(a.data) ? a.data : [];
      setAccs(list); setAcc(list.length === 1 ? list[0].id : ""); setInfo(t.data || null); setState("ready");
    }).catch((e) => { if (!batal) { setLoadErr(apiErrorText(e) || ""); setState("error"); } });
    return () => { batal = true; };
  }, [open, run?.id, run?.entity_id]);

  if (!open || !run) return null;
  const pilih = accs.find((a) => a.id === acc);
  const net = info?.total ?? run.net;
  const minTgl = run.journal_date ? String(run.journal_date).slice(0, 10) : "";
  const alasan = state !== "ready" ? "" : !canWrite ? TEKS_PILIH_PT : accs.length === 0 ? TEKS_TANPA_REKENING_GAJI
    : !pilih ? "Pilih rekening pembayaran gaji." : !tgl ? "Isi tanggal bayar." : "";

  const kirim = async () => {
    if (alasan || !pilih) { setErr(alasan); return; }
    const c = konfirmasiBayar({ ...run, net }, pilih.name, pt);
    const ok = await askConfirm({ ...c, message: `${c.message} ${ringkasBayar({ net, count: info?.count ?? run.employees,
      withoutAccount: info?.without_account || 0 })}. Kas keluar dan jurnal (hutang gaji berkurang, kas berkurang) dibuat bertanggal ${formatDate(tgl)}.`,
    confirmLabel: "Bayar gaji", danger: true });
    if (!ok) return;
    setBusy(true); setErr("");
    try {
      const body = { account_id: pilih.id, paid_date: tgl };
      const r = await intent.send({ id: run.id, ...body }, (k) => moneyPost(`${API}/hr/payroll/runs/${run.id}/pay`, body, k));
      onPaid?.(r.data);
    } catch (e) { setErr(apiErrorText(e) || "Pembayaran gaji gagal."); }
    finally { setBusy(false); }
  };

  return (
    <FormModal open={open} onClose={onClose} title="Bayar gaji" subtitle={`${run.number} · ${formatPeriod(run.period)} · ${pt}`}
      icon={Wallet} testId="pay-form" onSubmit={kirim} submitLabel="Bayar gaji" busy={busy}
      submitDisabled={state !== "ready" || !!alasan} error={err}>
      {state === "loading" ? (
        <p className="text-fs-13 text-kn-text-2" role="status" data-testid="pay-form-loading">Memuat rekening dan daftar transfer…</p>
      ) : state === "error" ? (
        <ErrorNotice testId="pay-form-load-error" message={`Data pembayaran tidak bisa dimuat. ${loadErr}`.trim()} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2"><label className="field-label">Rekening pembayaran <span className="req">*</span></label>
            <KNSelect data-testid="pay-form-account" value={acc} onValueChange={setAcc} className="field"
              placeholder={accs.length ? "Pilih rekening berperuntukan Gaji" : "Tidak ada rekening gaji"}
              options={accs.map((a) => ({ value: a.id, label: labelRekening(a) }))} />
            <p className="mt-1 text-fs-12 text-kn-text-2">Hanya rekening yang ditandai untuk pembayaran gaji.</p></div>
          <div><label className="field-label">Tanggal bayar <span className="req">*</span></label>
            <KNDatePicker data-testid="pay-form-date" value={tgl} onChange={setTgl} min={minTgl || undefined} clearable={false} />
            {minTgl && <p className="mt-1 text-fs-12 text-kn-text-2">Tidak boleh sebelum {formatDate(minTgl)} (tanggal jurnal gaji).</p>}</div>
          <div className="section-card section-pad sm:col-span-2" data-testid="pay-form-summary">
            <p className="text-fs-13 font-semibold text-kn-text">{ringkasBayar({ net, count: info?.count ?? run.employees,
              withoutAccount: info?.without_account || 0 })}</p>
            <p className="mt-1 text-fs-12 text-kn-text-2">Satu kas keluar sebesar total bersih; transfer per karyawan mengikuti Daftar transfer.</p></div>
          {alasan && <p className="sm:col-span-2 text-fs-12 text-kn-warning-text" data-testid="pay-form-why">{alasan}</p>}
        </div>
      )}
    </FormModal>
  );
}

export default function PayrollPayPanel({ onPaid }) {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canPay = canCurrent("payroll", "pay");
  const [data, setData] = useState({ items: [], total: 0 });
  const [state, setState] = useState("loading");
  const [err, setErr] = useState("");
  const [page, setPage] = useState(1);
  const [adaRekening, setAdaRekening] = useState(null);
  const [lihat, setLihat] = useState("");
  const [bayar, setBayar] = useState(null);
  const [msg, setMsg] = useState("");

  const load = useCallback(async () => {
    setState("loading");
    try {
      const r = await axios.get(`${API}/hr/payroll/pay-queue`, { params: { page, page_size: PAGE_SIZE } });
      setData({ items: r.data?.items || [], total: r.data?.total || 0 }); setErr(""); setState("ready");
    } catch (e) { setErr(apiErrorText(e) || ""); setState("error"); }
  }, [page]);
  useEffect(() => { load(); }, [load, selectedEntity]);
  useEffect(() => {
    if (!canWrite) { setAdaRekening(null); return; }
    axios.get(`${API}/hr/payroll/pay-accounts`).then((r) => setAdaRekening((r.data || []).length > 0))
      .catch(() => setAdaRekening(null));
  }, [canWrite, selectedEntity]);

  const ptOf = (eid) => entityFullById(entities, eid, "PT ini");
  const alasan = alasanTidakBisaBayar({ canWrite, canPay, adaRekening });
  const rows = data.items || [];

  return (
    <div className="section-card" data-testid="pay-queue">
      <div className="section-head flex-wrap gap-2">
        <h2 className="flex items-center gap-2"><Banknote size={16} className="text-kn-action" aria-hidden="true" />Gaji siap dibayar</h2>
      </div>
      <div className="section-body space-y-2">
        <p className="text-fs-12 text-kn-text-2">Penggajian yang sudah diposting dan menunggu dibayar. Bayar = satu kas keluar dari rekening berperuntukan Gaji sebesar total bersih.</p>
        {alasan && rows.length > 0 && <p className="text-fs-12 text-kn-warning-text" data-testid="pay-queue-why">Bayar: {alasan}</p>}
        {msg && <div className="notice-bar success" data-testid="pay-queue-msg"><span className="text-fs-12">{msg}</span>
          <button type="button" className="icon-button" aria-label="Tutup" onClick={() => setMsg("")}>×</button></div>}
      </div>
      {state === "loading" ? (
        <p className="section-pad text-fs-13 text-kn-text-2" role="status" data-testid="pay-queue-loading">Memuat antrean bayar…</p>
      ) : state === "error" ? (
        <div className="section-pad"><ErrorNotice testId="pay-queue-error" message={`Antrean bayar tidak bisa dimuat. ${err}`.trim()} onRetry={load} /></div>
      ) : rows.length === 0 ? (
        <p className="section-pad py-6 text-center text-fs-13 text-kn-text-2" data-testid="pay-queue-empty">{TEKS_ANTREAN_KOSONG}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full" data-testid="pay-queue-table">
              <thead><tr><th>Nomor</th><th>Periode</th><th>Jenis</th><th className="text-right">Karyawan</th>
                <th className="text-right">Total bersih</th><th className="col-sticky-end text-right">Aksi</th></tr></thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} data-testid={`pay-queue-row-${r.id}`}>
                    <td className="font-mono whitespace-nowrap">{r.number}</td>
                    <td className="whitespace-nowrap">{formatPeriod(r.period)}</td>
                    <td className="whitespace-nowrap">{runTypeLabel(r.run_type)}</td>
                    <td className="text-right tabular-nums">{r.employees}</td>
                    <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(r.net_total)}</td>
                    <td className="col-sticky-end">
                      <div className="flex justify-end gap-1.5">
                        <button type="button" data-testid={`pay-queue-transfer-${r.id}`} onClick={() => setLihat(r.id)}
                          className="secondary-button btn-sm whitespace-nowrap"><ListChecks size={13} aria-hidden="true" /> Daftar transfer</button>
                        <button type="button" data-testid={`pay-queue-pay-${r.id}`} disabled={!!alasan}
                          onClick={() => setBayar({ id: r.id, number: r.number, period: r.period, entity_id: r.entity_id,
                            net: r.net_total, employees: r.employees, journal_date: r.journal_date })}
                          className="primary-button btn-sm whitespace-nowrap"><Wallet size={13} aria-hidden="true" /> Bayar</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2">
            <span data-testid="pay-queue-count">{data.total} penggajian menunggu dibayar</span>
            <KNPager page={page} pageSize={PAGE_SIZE} total={data.total} onChange={setPage} testId="pay-queue-pager" />
          </div>
        </>
      )}
      {lihat && <TransferListPanel runId={lihat} onClose={() => setLihat("")} />}
      <PayDialog open={!!bayar} run={bayar} pt={ptOf(bayar?.entity_id)} onClose={() => setBayar(null)}
        onPaid={(run) => {
          setMsg(`Gaji ${run.number} dibayar ${formatCurrency(run.transfer_total)} dari ${run.pay_account_name || "rekening gaji"} (kas ${run.cash_txn_number || ""}).`);
          setBayar(null); setLihat(run.id); load(); onPaid?.(run);
        }} />
    </div>
  );
}
