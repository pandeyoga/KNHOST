/**
 * GrIrView — PK-28 (IV-03) · Keuangan › Hutang › GR/IR (Diterima Belum Ditagih).
 * Sisa akun GR/IR per PO (dari buku besar) beserta umurnya, dan kliring sisa yang tidak akan tertagih.
 * MP-T4b (K-82) — juga baris per SPK makloon: jasa yang hasilnya sudah diterima tetapi faktur mitranya belum dicocokkan
 * (penyelesaiannya "Cocokkan faktur" di rincian SPK, bukan kliring).
 * Sumber: GET /api/finance/gr-ir?status&bucket&q&page&page_size · POST /api/finance/gr-ir/{po_id}/clear
 *
 * Satu PT saja (mode "Semua PT" = petunjuk pilih PT). Tiga keadaan dibedakan: memuat · galat (kotak merah + Coba lagi)
 * · kosong. Kaki tabel mencocokkan total sisa per PO dengan saldo akun GR/IR di buku besar; selisihnya (jurnal yang
 * tidak terhubung ke PO) ditulis merah. Tombol Kliring hanya untuk baris yang boleh dikliring dan pemegang
 * `accounting.manage`; dialognya menyebut nominal, PO, dan PT, dan menuntut alasan (`02` N5).
 */
import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Ban, CheckCircle2, Circle, Clock, RefreshCw, XCircle } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import EntityScopeBanner from "../../components/EntityScopeBanner";
import EntityRequiredNotice from "../../components/EntityRequiredNotice";
import ErrorNotice from "../../components/ErrorNotice";
import FilterChips from "../../components/FilterChips";
import KNPager from "../../components/KNPager";
import { SearchBox } from "../../components/ListPageParts";
import { askReason } from "../../services/confirmService";
import { apiErrorText } from "../../utils/apiError";
import { formatCurrency } from "../../utils/formatters";
import { entityFullById } from "../../utils/entityLabel";
import { moneyPost } from "../../utils/moneyRequest";
import useIntentKey from "../../hooks/useIntentKey";
import { useAppNav } from "../../context/AppNavContext";
import { useEntityScope } from "../../context/EntityScopeContext";
import { canCurrent } from "../../config/roles";
import StatusBadge from "../../components/StatusBadge";

const PAGE_SIZE = 50;
export const TEKS_MEMUAT = "Memuat GR/IR…";
export const TEKS_KOSONG = "Tidak ada sisa GR/IR.";
export const TEKS_GALAT = "Daftar GR/IR tidak bisa dimuat.";
export const TEKS_SEMUA_PT = "Pilih satu PT untuk melihat GR/IR.";
export const KETERANGAN = "Barang yang sudah diterima tetapi belum ditagih pemasok (per PO) dan jasa makloon yang "
  + "faktur mitranya belum dicocokkan (per SPK), dari saldo akun GR/IR di buku besar. Sisa PO yang tidak akan tertagih "
  + "dikliring ke akun selisih harga pembelian.";
const TANPA_IZIN = "Kliring butuh akses kelola Akuntansi.";
const AKUN_BELUM = "Akun “Selisih harga pembelian” belum diatur untuk PT ini: selisih harga faktur tetap di GR/IR dan "
  + "kliring belum bisa dilakukan. Isi di Pengaturan › Keuangan & Pajak › Pemetaan Akun.";
const UMUR = [
  { key: "", label: "Semua" }, { key: "0-30", label: "0–30 hari" }, { key: "31-60", label: "31–60 hari" },
  { key: "61-90", label: "61–90 hari" }, { key: ">90", label: "Lebih dari 90 hari" },
];
const BOLEH_KLIRING = ["completed", "closed_short", "cancelled"];

/** Status PO: ikon + teks + warna (label dari server, kode mentah tidak tampil). */
function PoStatus({ status, label }) {
  const [cls, Icon] = status === "completed" ? ["status-done", CheckCircle2]
    : status === "cancelled" ? ["status-cancelled", XCircle]
      : status === "closed_short" ? ["status-draft", Ban]
        : ["receiving", "partial", "pending", "approved"].includes(status) ? ["status-pending", Clock]
          : ["status-draft", Circle];
  const teks = label ? label.charAt(0).toUpperCase() + label.slice(1) : "—";
  return (
    <span className={`status-pill ${cls} inline-flex items-center gap-1 whitespace-nowrap`} data-testid="grir-po-status">
      <Icon size={12} aria-hidden="true" />{teks}</span>
  );
}

/** Alasan baris tidak bisa dikliring (ditulis di kolom aksi, bukan tooltip — daftar periksa layar butir 4). */
export function alasanTidakKliring(it, mappingReady) {
  if (Math.abs(Number(it.balance) || 0) <= 0.005) return "Sisa sudah nol";
  if (it.kind === "makloon") return it.action_hint || "Selesaikan di rincian SPK";
  if (!BOLEH_KLIRING.includes(it.po_status)) return "PO masih berjalan";
  if (it.open_bill_number) return `Faktur ${it.open_bill_number} belum diposting`;
  if (!mappingReady) return "Akun selisih belum diatur";
  return "";
}

export default function GrIrView() {
  const { openDocument } = useAppNav();
  const { canWrite, selectedEntity, entities } = useEntityScope();
  const [data, setData] = useState({ items: [], total: 0 });
  const [state, setState] = useState("loading");   // loading | error | ready
  const [loadErr, setLoadErr] = useState("");
  const [bucket, setBucket] = useState("");
  const [showZero, setShowZero] = useState(false);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  const [qDebounced, setQDebounced] = useState("");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const intent = useIntentKey("grir");
  const canClear = canCurrent("accounting", "manage");

  useEffect(() => {
    const t = setTimeout(() => setQDebounced(q.trim()), 300);
    return () => clearTimeout(t);
  }, [q]);

  const load = useCallback(async () => {
    if (!canWrite) return;
    setState("loading");
    try {
      const r = await axios.get(`${API}/finance/gr-ir`, { params: {
        status: showZero ? "semua" : "terbuka", bucket: bucket || undefined, q: qDebounced || undefined,
        page, page_size: PAGE_SIZE } });
      setData(r.data || {});
      setLoadErr("");
      setState("ready");
    } catch (e) {
      setLoadErr(apiErrorText(e) || "");
      setState("error");
    }
  }, [canWrite, showZero, bucket, qDebounced, page]);
  useEffect(() => { load(); }, [load, selectedEntity]);

  const clear = async (it) => {
    const nominal = formatCurrency(Math.abs(Number(it.balance) || 0));
    const pt = entityFullById(entities, data.entity_id || selectedEntity);
    const alasan = await askReason({
      title: "Kliring sisa GR/IR?",
      message: `Sisa GR/IR ${nominal} pada PO ${it.po_number} (${pt}) akan dipindahkan ke akun selisih harga pembelian. `
        + "Tindakan ini menerbitkan jurnal.",
      reasonLabel: "Alasan", confirmLabel: "Kliring", cancelLabel: "Batal",
    });
    if (alasan === null) return;
    setBusy(it.po_id);
    try {
      const body = { reason: alasan };
      const r = await intent.send(body, (k) => moneyPost(`${API}/finance/gr-ir/${encodeURIComponent(it.po_id)}/clear`, body, k));
      const st = r.data?.clearing?.gl_status;
      setMsg(st === "posted" ? `${it.po_number}: sisa GR/IR ${nominal} dikliring, jurnal terbit.`
        : `${it.po_number}: kliring tercatat, tetapi jurnalnya gagal — ulang dari Tutup Buku › Posting Gagal.`);
      await load();
      window.dispatchEvent(new CustomEvent("kn-posting-failures-changed"));
    } catch (e) {
      setMsg(`${it.po_number}: ${apiErrorText(e) || "kliring gagal"}`);
    } finally { setBusy(""); }
  };

  if (!canWrite) {
    return (
      <div className="space-y-4" data-testid="grir-view">
        <EntityRequiredNotice what="daftar GR/IR" reason={TEKS_SEMUA_PT} when testId="grir-entity-required" />
      </div>
    );
  }

  const rows = data.items || [];
  const unlinked = Number(data.unlinked_balance) || 0;
  const filtered = Boolean(bucket || qDebounced);
  return (
    <div className="space-y-4" data-testid="grir-view">
      <EntityScopeBanner testId="grir-scope" />
      <div className="section-card">
        <div className="section-head flex-wrap gap-2">
          <h2 data-testid="grir-title">GR/IR — Diterima Belum Ditagih</h2>
          <button type="button" data-testid="grir-refresh" onClick={load} className="secondary-button btn-sm ml-auto whitespace-nowrap">
            <RefreshCw size={13} /> Muat ulang</button>
        </div>
        <div className="section-body space-y-2">
          <p className="text-[12px] text-kn-text-2" data-testid="grir-keterangan">{KETERANGAN}</p>
          <SearchBox value={q} onChange={(v) => { setQ(v); setPage(1); }} placeholder="Cari nomor PO/SPK, pemasok, atau mitra…" testId="grir-search">
            <FilterChips testId="grir-umur" value={bucket || "semua"} ariaLabel="Umur"
              onChange={(k) => { setBucket(k === "semua" ? "" : k || ""); setPage(1); }}
              options={UMUR.map((u) => ({ key: u.key || "semua", label: u.label }))} />
          </SearchBox>
          <label className="inline-flex items-center gap-2 text-[12px] text-kn-text">
            <input type="checkbox" role="switch" className="h-4 w-4" data-testid="grir-show-zero" checked={showZero}
              onChange={(e) => { setShowZero(e.target.checked); setPage(1); }} />
            Tampilkan yang sudah nol
          </label>
          {!canClear && <p className="text-[12px] text-kn-text-2" data-testid="grir-no-manage">{TANPA_IZIN}</p>}
        </div>
      </div>

      {state === "ready" && data.mapping_ready === false && (
        <div data-testid="grir-mapping-missing" className="notice-bar warning">
          <AlertTriangle size={14} aria-hidden="true" /><span className="text-[12px]">{AKUN_BELUM}</span></div>
      )}
      {msg && <div data-testid="grir-msg" className="notice-bar warning"><span className="text-[12px]">{msg}</span></div>}

      {state === "loading" && (
        <div data-testid="grir-loading" className="section-card section-pad text-[13px] text-kn-text-2" role="status">{TEKS_MEMUAT}</div>
      )}
      {state === "error" && (
        <ErrorNotice testId="grir-error" message={`${TEKS_GALAT} ${loadErr}`.trim()} onRetry={load} />
      )}
      {state === "ready" && rows.length === 0 && (
        <div data-testid="grir-empty" className="section-card section-pad text-center text-[13px] text-kn-text-2">
          {filtered ? "Tidak ada sisa GR/IR yang cocok dengan saringan." : TEKS_KOSONG}</div>
      )}
      {state === "ready" && rows.length > 0 && (
        <div className="section-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="data-table head-wrap w-full text-[12px]" data-testid="grir-table">
              <thead>
                <tr><th>PO / SPK</th><th>Pemasok / mitra</th><th>Status</th><th className="text-right">Nilai diterima</th>
                  <th className="text-right">Sudah ditagih</th><th className="text-right">Diretur / klaim</th>
                  <th className="text-right">Dikliring</th><th className="text-right">Sisa GR/IR</th>
                  <th className="text-right">Umur (hari)</th><th className="col-sticky-end text-right">Aksi</th></tr>
              </thead>
              <tbody>
                {rows.map((it) => {
                  const alasan = alasanTidakKliring(it, data.mapping_ready);
                  const spk = it.kind === "makloon";
                  const key = spk ? `mko-${it.doc_id}` : it.po_id;   // MP-T4b — baris SPK makloon
                  const nomor = it.doc_number || it.po_number;
                  return (
                    <tr key={key} data-testid={`grir-row-${key}`}>
                      <td className="font-mono whitespace-nowrap">
                        {it.link?.view ? (
                          <button type="button" className="link-button" data-testid={`grir-open-${key}`}
                            onClick={() => openDocument({ ...it.link, number: nomor })}>{nomor}</button>
                        ) : nomor}
                      </td>
                      <td className="max-w-[180px] break-words">{it.supplier_name || "—"}</td>
                      <td>{spk ? <StatusBadge tone="info" label={it.po_status_label} testId={`grir-mko-status-${it.doc_id}`} />
                        : <PoStatus status={it.po_status} label={it.po_status_label} />}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(it.received_value)}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(it.billed_value)}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(it.returned_value)}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(it.cleared_value)}</td>
                      <td className="whitespace-nowrap text-right tabular-nums font-semibold" data-testid={`grir-balance-${key}`}>
                        {formatCurrency(it.balance)}
                        {spk && (it.awaiting_bills || []).length > 0 && (
                          <p className="ml-auto max-w-[150px] whitespace-normal text-[12px] font-normal text-kn-text-2"
                            data-testid={`grir-awaiting-${it.doc_id}`}>
                            menunggu faktur: {it.awaiting_bills.map((n, i) => (
                              <span key={n} className="whitespace-nowrap">{i ? ", " : ""}{n}</span>))}</p>
                        )}
                        {Number(it.unposted_variance) !== 0 && (
                          <p className="text-[12px] font-normal text-kn-text-2" data-testid={`grir-variance-${it.po_id}`}>
                            termasuk selisih harga {formatCurrency(it.unposted_variance)}</p>
                        )}
                      </td>
                      <td className="whitespace-nowrap text-right tabular-nums">{it.age_days}</td>
                      <td className="col-sticky-end text-right">
                        {it.can_clear && canClear ? (
                          <button type="button" data-testid={`grir-clear-${it.po_id}`} disabled={busy === it.po_id}
                            onClick={() => clear(it)} className="primary-button btn-sm whitespace-nowrap">
                            {busy === it.po_id ? "Memproses…" : "Kliring"}</button>
                        ) : (
                          // Cek layar 14 Nov — alasan boleh turun baris: kolom aksi lekat tetap ramping di 1024 px
                          // (dulu satu baris lebar menutupi kolom Sisa GR/IR). Baris SPK: petunjuk untuk semua pembaca.
                          <span className="inline-block max-w-[110px] whitespace-normal text-left text-fs-12 leading-tight text-kn-text-2"
                            data-testid={`grir-why-${key}`}>
                            {canClear || spk ? (alasan || "—") : "—"}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="space-y-1 border-t border-kn-divider px-3 py-2 text-[12px]" data-testid="grir-footer">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span>Total sisa GR/IR: <b className="tabular-nums" data-testid="grir-total">{formatCurrency(data.total_balance)}</b>
                {filtered && <span className="text-kn-text-2"> · yang tampil {formatCurrency(data.filtered_balance)}</span>}</span>
              <span>Saldo akun GR/IR di buku besar: <b className="tabular-nums" data-testid="grir-ledger">{formatCurrency(data.ledger_balance)}</b></span>
            </div>
            {Math.abs(unlinked) > 0.005 && (
              <p className="text-kn-danger-text" data-testid="grir-unlinked">
                {formatCurrency(unlinked)} berasal dari jurnal yang tidak terhubung ke PO atau SPK makloon.</p>
            )}
            <div className="flex flex-wrap items-center justify-between gap-2 text-kn-text-2">
              <span data-testid="grir-count">{data.total || 0} dokumen</span>
              <KNPager page={page} pageSize={PAGE_SIZE} total={data.total || 0} onChange={setPage} testId="grir-pager" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
