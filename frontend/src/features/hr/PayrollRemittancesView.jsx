/**
 * PayrollRemittancesView — PK-22 (FY-07) · SDM › Penggajian › Setoran Kewajiban.
 *
 * Hutang BPJS dan PPh 21 yang timbul saat gaji diposting turun lewat dokumen setoran: satu setoran = satu kas keluar
 * Dr hutang / Cr kas (rekening wajib). Sumber: GET /api/hr/payroll/remittances/outstanding?period · GET
 * /api/hr/payroll/remittances?period&kind&page&page_size · POST /api/hr/payroll/remittances (`payroll.pay`).
 *
 * Satu PT saja: mode "Semua PT" → kartu kewajiban diganti petunjuk dan tombol Catat Setoran mati dengan alasan
 * "Pilih satu PT dulu" tertulis di sampingnya. Keadaan memuat · galat (+ Coba lagi) · kosong dibedakan. Konfirmasi
 * menyebut nominal, jenis, masa, dan PT (`02` N5); kirim ulang memakai kunci yang sama (`02` N4).
 */
import { useCallback, useEffect, useState } from "react";
import { HandCoins, Landmark, ReceiptText, RefreshCw } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import FormModal from "../../components/FormModal";
import KNPager from "../../components/KNPager";
import KNSelect from "../../components/KNSelect";
import CashAccountField, { cashAccountBlocked, cashAccountBlockReason } from "../../components/CashAccountField";
import { askConfirm } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency, formatDate, formatPeriod, todayWib } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { moneyPost } from "../../utils/moneyRequest";
import useIntentKey from "../../hooks/useIntentKey";
import { canCurrent } from "../../config/roles";
import { useEntityScope } from "../../context/EntityScopeContext";
import { curMonth, recentMonths } from "./payrollUtils";

const PAGE_SIZE = 20;
export const KIND_LABEL = { bpjs: "BPJS", pph21: "PPh 21" };
export const TEKS_SEMUA_PT = "Pilih satu PT dulu";
export const TEKS_TANPA_IZIN = "Mencatat setoran butuh izin membayar gaji.";
const KIND_ICON = { bpjs: Landmark, pph21: ReceiptText };
const JENIS = [{ key: "semua", label: "Semua jenis" }, { key: "bpjs", label: "BPJS" }, { key: "pph21", label: "PPh 21" }];

/** Alasan tombol Catat Setoran mati (ditulis di samping tombol — bukan tooltip). */
export function alasanTidakBisaSetor({ canWrite, canPay, sisaTotal = null }) {
  if (!canWrite) return TEKS_SEMUA_PT;
  if (!canPay) return TEKS_TANPA_IZIN;
  // Cek layar 15 Nov — tombol tidak aktif bila tidak ada yang bisa disetor (dulu aktif lalu ditolak saat simpan).
  if (sisaTotal != null && sisaTotal <= 0.005) return "Tidak ada sisa kewajiban untuk masa ini.";
  return "";
}

/** Galat isian form setoran (sebelum kirim); "" = siap dikirim. */
export function galatForm(f, sisa) {
  const n = Number(f.amount);
  if (!f.kind || !f.period) return "Pilih jenis dan masa.";
  if (!(n > 0)) return "Nominal harus lebih dari 0.";
  if (sisa != null && n > sisa + 0.005) return `Nominal melebihi sisa kewajiban (${formatCurrency(sisa)}).`;
  if (!f.paid_date) return "Isi tanggal setor.";
  return "";
}

function KartuKewajiban({ item, testId }) {
  const Icon = KIND_ICON[item.kind] || Landmark;
  const lunas = Math.abs(Number(item.sisa) || 0) <= 0.005;
  return (
    <div className="section-card section-pad" data-testid={testId}>
      <div className="flex items-center justify-between gap-2 mb-2">
        <h3 className="flex items-center gap-2 text-fs-14 font-bold text-kn-text"><Icon size={15} aria-hidden="true" />{item.label}</h3>
        {Number(item.kewajiban) > 0 && (
          <span className={`status-pill ${lunas ? "status-done" : "status-pending"} whitespace-nowrap`} data-testid={`${testId}-status`}>
            {lunas ? "Sudah disetor penuh" : "Masih ada sisa"}</span>
        )}
      </div>
      <dl className="grid grid-cols-3 gap-2 text-fs-12">
        <div><dt className="text-kn-text-2">Kewajiban</dt><dd className="text-fs-14 font-semibold tabular-nums" data-testid={`${testId}-kewajiban`}>{formatCurrency(item.kewajiban)}</dd></div>
        <div><dt className="text-kn-text-2">Sudah disetor</dt><dd className="text-fs-14 font-semibold tabular-nums" data-testid={`${testId}-disetor`}>{formatCurrency(item.disetor)}</dd></div>
        <div><dt className="text-kn-text-2">Sisa</dt><dd className={`text-fs-14 font-bold tabular-nums ${lunas ? "text-kn-success-text" : "text-kn-warning-text"}`} data-testid={`${testId}-sisa`}>{formatCurrency(item.sisa)}</dd></div>
      </dl>
    </div>
  );
}

export default function PayrollRemittancesView() {
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const canPay = canCurrent("payroll", "pay");
  const [period, setPeriod] = useState(curMonth());
  const [out, setOut] = useState(null);
  const [outState, setOutState] = useState("loading");   // loading | error | ready
  const [outErr, setOutErr] = useState("");
  const [list, setList] = useState({ items: [], total: 0 });
  const [listState, setListState] = useState("loading");
  const [listErr, setListErr] = useState("");
  const [kind, setKind] = useState("semua");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({});
  const [acc, setAcc] = useState("");
  const [accState, setAccState] = useState("");
  const [busy, setBusy] = useState(false);
  const [formErr, setFormErr] = useState("");
  const [msg, setMsg] = useState("");
  const intent = useIntentKey("setor");
  const pt = entityFullById(entities, selectedEntity, "PT ini");

  const loadOut = useCallback(async () => {
    if (!canWrite) { setOut(null); setOutState("ready"); return; }
    setOutState("loading");
    try {
      const r = await axios.get(`${API}/hr/payroll/remittances/outstanding`, { params: { period } });
      setOut(r.data || null); setOutErr(""); setOutState("ready");
    } catch (e) { setOutErr(apiErrorText(e) || ""); setOutState("error"); }
  }, [canWrite, period]);
  const loadList = useCallback(async () => {
    setListState("loading");
    try {
      const r = await axios.get(`${API}/hr/payroll/remittances`, { params: {
        period, kind: kind === "semua" ? undefined : kind, page, page_size: PAGE_SIZE } });
      setList(r.data || { items: [], total: 0 }); setListErr(""); setListState("ready");
    } catch (e) { setListErr(apiErrorText(e) || ""); setListState("error"); }
  }, [period, kind, page]);
  useEffect(() => { loadOut(); }, [loadOut, selectedEntity]);
  useEffect(() => { loadList(); }, [loadList, selectedEntity]);

  const sisaOf = (k) => (out && out[k] ? Number(out[k].sisa) || 0 : null);
  const buka = (k = "bpjs") => {
    const sisa = sisaOf(k);
    setForm({ kind: k, period, amount: sisa > 0 ? String(sisa) : "", paid_date: todayWib(), cash_type: "kas_besar",
      reference: "", notes: "" });
    setAcc(""); setFormErr(""); setOpen(true);
  };
  const ubah = (patch) => setForm((f) => ({ ...f, ...patch }));

  const simpan = async () => {
    const g = galatForm(form, form.period === period ? sisaOf(form.kind) : null);
    if (g) { setFormErr(g); return; }
    const nominal = formatCurrency(Number(form.amount));
    const ok = await askConfirm({
      title: `Catat setoran ${KIND_LABEL[form.kind]} ${nominal}?`,
      message: `Setoran ${KIND_LABEL[form.kind]} masa ${formatPeriod(form.period)} sebesar ${nominal} untuk ${pt}. `
        + "Kas keluar dan jurnal (hutang berkurang, kas berkurang) dibuat.",
      confirmLabel: "Catat setoran",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      const body = { kind: form.kind, period: form.period, amount: Number(form.amount), paid_date: form.paid_date,
        account_id: acc || "", cash_type: form.cash_type, reference: form.reference || "", notes: form.notes || "" };
      const r = await intent.send(body, (k) => moneyPost(`${API}/hr/payroll/remittances`, body, k));
      setOpen(false);
      setMsg(`Setoran ${r.data?.number || ""} tercatat: ${KIND_LABEL[form.kind]} ${nominal}.`);
      await Promise.all([loadOut(), loadList()]);
    } catch (e) {
      setFormErr(apiErrorText(e) || "Setoran gagal dicatat.");
      await loadOut();
    } finally { setBusy(false); }
  };

  const sisaTotal = out ? (sisaOf("bpjs") || 0) + (sisaOf("pph21") || 0) : null;
  const alasan = alasanTidakBisaSetor({ canWrite, canPay, sisaTotal });
  const monthOpts = recentMonths().map((m) => ({ value: m, label: formatPeriod(m) }));
  const rows = list.items || [];
  const blokRekening = cashAccountBlocked(accState, acc);

  return (
    <div className="space-y-4" data-testid="remit-view">
      <EntityScopeBanner testId="remit-scope" />
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h2 className="flex items-center gap-2" data-testid="remit-title"><HandCoins size={16} className="text-kn-action" aria-hidden="true" />Setoran Kewajiban</h2>
          <button type="button" data-testid="remit-refresh" onClick={() => { loadOut(); loadList(); }} className="secondary-button btn-sm ml-auto whitespace-nowrap">
            <RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-fs-12 text-kn-text-2">Hutang BPJS dan PPh 21 dari gaji yang sudah diposting, dan setoran yang sudah dicatat. Setoran mengurangi hutangnya lewat kas keluar.</p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="w-[200px]"><label className="field-label">Masa gaji</label>
              <KNSelect data-testid="remit-period" value={period} onValueChange={(v) => { setPeriod(v); setPage(1); }} className="field" options={monthOpts} /></div>
            <button type="button" data-testid="remit-create" disabled={!!alasan} onClick={() => buka("bpjs")}
              className="primary-button btn-sm whitespace-nowrap">Catat Setoran</button>
            {alasan && <span className="text-fs-12 text-kn-text-2" data-testid="remit-create-why">{alasan}</span>}
          </div>
        </div>
      </div>

      {msg && <div className="notice-bar success" data-testid="remit-msg"><span className="text-fs-12">{msg}</span><button type="button" className="icon-button" aria-label="Tutup" onClick={() => setMsg("")}>×</button></div>}

      {!canWrite ? (
        <div className="section-card section-pad text-fs-13 text-kn-text-2" data-testid="remit-all-pt">
          Kewajiban dan sisa setoran dihitung per PT. {TEKS_SEMUA_PT} di pemilih PT (kanan atas) untuk melihatnya.</div>
      ) : outState === "loading" ? (
        <div className="section-card section-pad text-fs-13 text-kn-text-2" data-testid="remit-out-loading" role="status">Memuat kewajiban…</div>
      ) : outState === "error" ? (
        <ErrorNotice testId="remit-out-error" message={`Kewajiban tidak bisa dimuat. ${outErr}`.trim()} onRetry={loadOut} />
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {(out?.items || []).map((it) => <KartuKewajiban key={it.kind} item={it} testId={`remit-card-${it.kind}`} />)}
          {out && out.runs === 0 && (
            <p className="text-fs-12 text-kn-text-2 md:col-span-2" data-testid="remit-no-run">Belum ada gaji {formatPeriod(period)} yang diposting di {pt}, jadi belum ada kewajiban masa ini.</p>
          )}
        </div>
      )}

      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h3 className="text-fs-14 font-bold">Riwayat setoran {formatPeriod(period)}</h3>
          <FilterChips testId="remit-kind" value={kind} ariaLabel="Jenis setoran" onChange={(k) => { setKind(k || "semua"); setPage(1); }} options={JENIS} />
        </div>
        {listState === "loading" ? (
          <div className="section-pad text-fs-13 text-kn-text-2" data-testid="remit-list-loading" role="status">Memuat riwayat…</div>
        ) : listState === "error" ? (
          <div className="section-pad"><ErrorNotice testId="remit-list-error" message={`Riwayat setoran tidak bisa dimuat. ${listErr}`.trim()} onRetry={loadList} /></div>
        ) : rows.length === 0 ? (
          <div className="section-pad py-6 text-center text-fs-13 text-kn-text-2" data-testid="remit-list-empty">
            {kind !== "semua" ? `Belum ada setoran ${KIND_LABEL[kind]} untuk masa ini.` : "Belum ada setoran untuk masa ini."}</div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="data-table head-wrap w-full" data-testid="remit-table">
                <thead><tr><th>Nomor</th><th>Jenis</th><th>Tanggal setor</th><th className="text-right">Nominal</th><th>Nomor bukti</th><th>Status</th></tr></thead>
                <tbody>
                  {rows.map((d) => (
                    <tr key={d.id} data-testid={`remit-row-${d.id}`}>
                      <td className="font-mono whitespace-nowrap">{d.number}</td>
                      <td className="whitespace-nowrap">{KIND_LABEL[d.kind] || "—"}</td>
                      <td className="whitespace-nowrap">{formatDate(d.paid_date)}</td>
                      <td className="text-right tabular-nums whitespace-nowrap">{formatCurrency(d.amount)}</td>
                      <td className="max-w-[160px] break-words">{d.reference || "—"}</td>
                      <td><span className={`status-pill ${d.status === "done" ? "status-done" : d.gl_status === "failed" ? "status-rejected" : "status-pending"} whitespace-nowrap`}>
                        {d.status === "done" ? "Tercatat" : d.gl_status === "failed" ? "Jurnal gagal" : "Diproses"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-kn-divider px-3 py-2 text-fs-12 text-kn-text-2">
              <span data-testid="remit-count">{list.total || 0} setoran</span>
              <KNPager page={page} pageSize={PAGE_SIZE} total={list.total || 0} onChange={setPage} testId="remit-pager" />
            </div>
          </>
        )}
      </div>

      <FormModal open={open} onClose={() => setOpen(false)} title="Catat Setoran Kewajiban" subtitle={pt} icon={HandCoins}
        testId="remit-form" onSubmit={simpan} submitLabel="Catat Setoran" busy={busy} submitDisabled={blokRekening}
        error={formErr}>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div><label className="field-label">Jenis <span className="req">*</span></label>
            <KNSelect data-testid="remit-form-kind" value={form.kind} className="field"
              onValueChange={(v) => { const s = form.period === period ? sisaOf(v) : null; ubah({ kind: v, amount: s > 0 ? String(s) : form.amount }); }}
              options={[{ value: "bpjs", label: "BPJS" }, { value: "pph21", label: "PPh 21" }]} /></div>
          <div><label className="field-label">Masa <span className="req">*</span></label>
            <KNSelect data-testid="remit-form-period" value={form.period} className="field" onValueChange={(v) => ubah({ period: v })} options={monthOpts} /></div>
          <div><label className="field-label">Nominal (Rp) <span className="req">*</span></label>
            <input data-testid="remit-form-amount" className="field" inputMode="decimal" value={form.amount || ""} onChange={(e) => ubah({ amount: e.target.value.replace(/[^\d.]/g, "") })} />
            {form.period === period && sisaOf(form.kind) != null && <p className="text-fs-12 text-kn-text-2 mt-1">Sisa kewajiban: {formatCurrency(sisaOf(form.kind))}</p>}</div>
          <div><label className="field-label">Tanggal setor <span className="req">*</span></label>
            <input data-testid="remit-form-date" type="date" className="field" value={form.paid_date || ""} onChange={(e) => ubah({ paid_date: e.target.value })} />
            <p className="text-fs-12 text-kn-text-2 mt-1">Tanggal ini menjadi tanggal jurnal.</p></div>
          <div className="sm:col-span-2">
            <CashAccountField entityId={selectedEntity} cashType={form.cash_type} value={acc} onChange={setAcc} onState={setAccState} testId="remit-form-account" />
            {blokRekening && <p className="text-fs-12 text-kn-danger-text mt-1" data-testid="remit-form-account-why">{cashAccountBlockReason(accState)}</p>}</div>
          <div><label className="field-label">Nomor bukti setor</label>
            <input data-testid="remit-form-ref" className="field" value={form.reference || ""} onChange={(e) => ubah({ reference: e.target.value })} placeholder="Contoh: NTPN / nomor bukti bank" /></div>
          <div><label className="field-label">Catatan</label>
            <input data-testid="remit-form-notes" className="field" value={form.notes || ""} onChange={(e) => ubah({ notes: e.target.value })} /></div>
        </div>
      </FormModal>
    </div>
  );
}
