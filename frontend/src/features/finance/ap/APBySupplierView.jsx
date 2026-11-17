/**
 * APBySupplierView (S5, pelatihan keuangan 18 Nov) — Keuangan › Hutang › **Hutang per Pemasok** (view `ap-by-supplier`).
 *
 * Permintaan pemilik (kata asli): "untuk hutang piutang saya ingin tambahkan pengelompokan berdasarkan subject yang
 * dibayar atau membayar … ui interface di finance yang viewnya per orang atau suplier di klik muncul semua hutang atau
 * piutangnya dan bisa aksi bayar juga". Sisi piutang = Piutang › Saldo & Umur (`ARAgingView`); layar ini padanannya
 * untuk hutang.
 *
 * Pola UI §2.A: kepala satu baris (?) · kartu angka = saringan cepat · bilah daftar (cari · saringan · urutan · jumlah ·
 * Unduh) · tabel berhalaman. Satu baris = satu pemasok di satu PT: tagihan terbuka, kelompok umur (sama dengan Hutang ›
 * Tagihan), sisa hutang, jatuh tempo terdekat, potongan belum dipakai. Klik baris / [Rincian] → pop-up rincian
 * (`APSupplierDetail`) dengan aksi Bayar per tagihan/kontrabon (`PaySupplierModal`) dan Bayar terpilih
 * (`PayManyBillsModal`). Sumber: `GET /vendor-bills/payables/by-supplier` (izin `vendor_bill.view`).
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, Building2, Download, Layers, PiggyBank, Truck, Wallet } from "lucide-react";
import axios, { API } from "../../../services/apiClient";
import ErrorNotice from "../../../components/ErrorNotice";
import EmptyState, { listStateKind } from "../../../components/EmptyState";
import DetailModal from "../../../components/DetailModal";
import KNSelect from "../../../components/KNSelect";
import PagedRows from "../../../components/PagedRows";
import { ListToolbar, MetricRow, PageHeader, SearchInput } from "../../../components/ListPageParts";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { apiErrorText } from "../../../utils/apiError";
import { buildCsv, csvFilename, downloadCsv } from "../../../utils/csvExport";
import { useEntityScope } from "../../../context/EntityScopeContext";
import { entityShortById } from "../../../utils/entityLabel";
import { SupplierCardLink } from "../cards/partyCards";
import PaySupplierModal from "../payments/PaySupplierModal";
import APSupplierDetail from "./APSupplierDetail";
import PayManyBillsModal from "./PayManyBillsModal";
import { CSV_PEMASOK, SARINGAN, URUTAN, apBucketColumns, filterSupplierRows, potonganOf, sumSupplierRows } from "./apPartyApi";

const sel = "!h-auto !w-auto min-w-[200px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13";
const TONE = { "1-30": "text-kn-warning-text", "31-60": "text-kn-warning-text", "61-90": "text-kn-danger-text", ">90": "text-kn-danger-text" };

function Cell({ v, k }) {
  const n = Number(v || 0);
  return <td className={`whitespace-nowrap text-right tabular-nums ${n > 0.005 ? TONE[k] || "" : "text-kn-text-2"}`}>{n > 0.005 ? formatCurrency(n) : "—"}</td>;
}

export default function APBySupplierView({ currentUser, selectedEntity }) {
  const { entities } = useEntityScope();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [saring, setSaring] = useState("semua");
  const [urut, setUrut] = useState("telat");
  const [open, setOpen] = useState(null);          // { supplier_id, entity_id, supplier_name }
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [notice, setNotice] = useState("");
  const [payOne, setPayOne] = useState(null);      // { type, id }
  const [payMany, setPayMany] = useState(null);    // [bill rows]
  const allPt = !selectedEntity || selectedEntity === "all";
  const ptName = entityShortById(entities, selectedEntity, "PT");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (selectedEntity && selectedEntity !== "all") params.entity_id = selectedEntity;
      const r = await axios.get(`${API}/vendor-bills/payables/by-supplier`, { params });
      setData(r.data || null); setError("");
    } catch (e) {
      setError(apiErrorText(e, "Hutang per pemasok belum bisa dimuat."));
    } finally { setLoading(false); }
  }, [selectedEntity]);
  useEffect(() => { load(); }, [load]);

  const loadDetail = useCallback(async (row) => {
    if (!row) return;
    setDetailLoading(true); setDetailError("");
    try {
      const params = row.entity_id && allPt ? { entity_id: row.entity_id } : {};
      const r = await axios.get(`${API}/vendor-bills/payables/by-supplier/${row.supplier_id}`, { params });
      setDetail(r.data || null);
    } catch (e) {
      setDetail(null);
      setDetailError(apiErrorText(e, "Rincian hutang pemasok ini gagal dimuat. Periksa koneksi lalu coba lagi."));
    } finally { setDetailLoading(false); }
  }, [allPt]);

  function buka(row) { setOpen(row); setDetail(null); setNotice(""); loadDetail(row); }
  function tutup() { setOpen(null); setDetail(null); setNotice(""); setDetailError(""); }
  function sesudahBayar(msg) { setNotice(msg); loadDetail(open); load(); }

  const cols = useMemo(() => apBucketColumns(data?.aging_labels), [data]);
  const rows = useMemo(() => filterSupplierRows(data?.rows, { q, saring, urut }), [data, q, saring, urut]);
  const foot = useMemo(() => sumSupplierRows(rows), [rows]);
  const tot = data?.totals || {};
  const disaring = Boolean(q.trim()) || saring !== "semua";
  // Memuat / galat / kosong / tidak cocok saringan dibedakan (EmptyState); galat tetap tampil juga di bilah atas.
  const keadaan = listStateKind({ loading: loading && !data, error: data ? null : error, count: rows.length, filtered: disaring });

  const kartu = [
    { k: "semua", label: "Total hutang", value: formatCurrency(tot.outstanding), icon: Wallet, hint: `${tot.supplier_count || 0} pemasok · ${tot.bill_count || 0} tagihan`, testId: "ap-party-kpi-total" },
    { k: "lewat", label: "Lewat jatuh tempo", value: formatCurrency(tot.overdue), icon: AlertTriangle, tone: "var(--kn-danger-text)", testId: "ap-party-kpi-overdue" },
    { k: "lewat60", label: "Lewat lebih dari 60 hari", value: formatCurrency(Number(tot.aging?.["61-90"] || 0) + Number(tot.aging?.[">90"] || 0)), icon: AlertTriangle, tone: "var(--kn-danger-text)", testId: "ap-party-kpi-60" },
    { k: "potongan", label: "Potongan belum dipakai", value: formatCurrency(Number(tot.advance || 0) + Number(tot.debit_notes || 0)), icon: PiggyBank, hint: "nota debit + uang muka", testId: "ap-party-kpi-credit" },
  ].map(({ k, ...c }) => ({ ...c, active: saring === k, onClick: () => setSaring(saring === k ? "semua" : k) }));

  function unduh() {
    downloadCsv(csvFilename("hutang-per-pemasok", "all"), buildCsv(rows, CSV_PEMASOK));
  }

  return (
    <div data-testid="ap-party-view" className="view-container">
      <PageHeader icon={Truck} title={<span data-testid="ap-party-title">Hutang per Pemasok</span>} testId="ap-party-header"
        help="Semua tagihan pemasok yang belum lunas dikelompokkan per pemasok. Klik baris untuk melihat tagihan, kontrabon, dan potongan pemasok itu, lalu bayar satu tagihan atau beberapa sekaligus. Umur = hari lewat jatuh tempo (sama dengan Hutang › Tagihan)." />
      {data && (
        <p className={`mb-2 flex items-center gap-1.5 text-fs-12 ${data.combined ? "text-kn-warning-text" : "text-kn-text-2"}`} data-testid="ap-party-entity">
          <Building2 size={13} aria-hidden="true" />
          {data.combined ? "Semua PT: satu baris per pemasok per PT (tidak dijumlah lintas PT). Pilih satu PT untuk membayar." : `PT ${ptName}: angka milik PT ini saja.`}
        </p>
      )}
      <MetricRow testId="ap-party-kpi" items={kartu} />
      <ErrorNotice message={data ? error : ""} onRetry={load} onDismiss={() => setError("")} testId="ap-party-error" />

      <div className="mt-3">
        <ListToolbar testId="ap-party-toolbar" count={`${rows.length} pemasok`}
          actions={<button type="button" className="secondary-button btn-sm whitespace-nowrap" disabled={!rows.length} onClick={unduh}
            data-testid="ap-party-download"><Download size={13} aria-hidden="true" /> Unduh</button>}>
          <SearchInput testId="ap-party-search" placeholder="Cari pemasok / PT…" value={q} onChange={setQ}
            className="min-w-[200px] flex-1 sm:max-w-[300px]" />
          <KNSelect data-testid="ap-party-filter" aria-label="Saringan" value={saring} onValueChange={(v) => setSaring(v || "semua")}
            options={SARINGAN} className={sel} />
          <KNSelect data-testid="ap-party-sort" aria-label="Urutan" value={urut} onValueChange={(v) => setUrut(v || "telat")}
            options={URUTAN} className={sel} />
        </ListToolbar>
      </div>

      {keadaan ? (
        <EmptyState kind={keadaan} what="hutang pemasok" error={error || null} onRetry={load}
          title={keadaan === "empty" ? "Tidak ada hutang pemasok yang belum lunas." : undefined}
          onReset={() => { setQ(""); setSaring("semua"); }} icon={Layers}
          testId={keadaan === "loading" ? "ap-party-loading" : keadaan === "empty" || keadaan === "filtered" ? "ap-party-empty" : "ap-party-state"} />
      ) : (
        <div className="table-wrap">
          <table className="data-table head-wrap min-w-[980px]" data-testid="ap-party-table">
            <thead>
              <tr>
                <th>Pemasok</th>
                {cols.map((b) => <th key={b.key} className="text-right" data-testid={`ap-party-col-${b.key}`}>{b.label}</th>)}
                <th className="text-right">Sisa hutang</th>
                <th>Jatuh tempo terdekat</th>
                <th className="text-right" title="Nota debit + uang muka ke pemasok yang belum dipotong lewat kontrabon">Potongan</th>
                <th className="col-sticky-end text-right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              <PagedRows rows={rows} pageSize={25} testId="ap-party-pager">{(r) => {
                const key = `${r.supplier_id}:${r.entity_id}`;
                const aktif = open && `${open.supplier_id}:${open.entity_id}` === key;
                return (
                  <tr key={key} data-testid={`ap-party-row-${r.supplier_id}`} onClick={() => buka(r)}
                    className={`cursor-pointer ${aktif ? "bg-kn-action-soft" : ""}`}>
                    <td className="max-w-[300px]">
                      <p className="truncate font-semibold"><SupplierCardLink id={r.supplier_id} name={r.supplier_name}
                        perms={currentUser?.permissions} testId={`ap-party-card-${r.supplier_id}`} /></p>
                      <p className="truncate text-fs-12 text-kn-text-2">
                        PT {r.entity_label} · {r.bill_count} tagihan{r.max_days_past_due > 0 ? ` · telat ${r.max_days_past_due} hari` : ""}
                        {r.held_count > 0 ? ` · ${r.held_count} di kontrabon` : ""}
                      </p>
                    </td>
                    {cols.map((b) => <Cell key={b.key} k={b.key} v={r.aging?.[b.key]} />)}
                    <td className="whitespace-nowrap text-right font-bold tabular-nums" data-testid={`ap-party-total-${r.supplier_id}`}>{formatCurrency(r.outstanding)}</td>
                    <td className="whitespace-nowrap">{r.nearest_due ? formatDate(r.nearest_due) : "—"}</td>
                    <td className="whitespace-nowrap text-right tabular-nums">{potonganOf(r) > 0.005 ? formatCurrency(potonganOf(r)) : "—"}</td>
                    <td className="col-sticky-end text-right">
                      <button type="button" className="secondary-button btn-sm whitespace-nowrap" data-testid={`ap-party-open-${r.supplier_id}`}
                        onClick={(e) => { e.stopPropagation(); buka(r); }}>Rincian & bayar</button>
                    </td>
                  </tr>
                );
              }}</PagedRows>
            </tbody>
            <tfoot>
              <tr className="font-bold">
                <td className="text-fs-12 uppercase text-kn-text-2" data-testid="ap-party-foot-label">
                  {disaring ? `Total yang tampil (${rows.length} pemasok)` : "Total"}
                </td>
                {cols.map((b) => <td key={b.key} className="whitespace-nowrap text-right tabular-nums">{formatCurrency(foot.aging[b.key])}</td>)}
                <td className="whitespace-nowrap text-right tabular-nums" data-testid="ap-party-foot-total">{formatCurrency(foot.outstanding)}</td>
                <td />
                <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(foot.potongan)}</td>
                <td className="col-sticky-end" />
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      {open && (
        <DetailModal onClose={tutup} label="Rincian hutang pemasok" testId="ap-party-detail-modal">
          <APSupplierDetail detail={detail} loading={detailLoading} error={detailError} onRetry={() => loadDetail(open)}
            onClose={tutup} currentUser={currentUser} allPt={allPt} ptName={allPt ? "" : ptName} notice={notice}
            onPayOne={(t) => setPayOne(t)} onPayMany={(bills) => setPayMany(bills)} />
        </DetailModal>
      )}
      {payOne && (
        <PaySupplierModal target={payOne} onClose={() => setPayOne(null)}
          onPaid={(_, msg) => { setPayOne(null); sesudahBayar(msg || "Pembayaran dicatat."); }} />
      )}
      {payMany && (
        <PayManyBillsModal supplierName={detail?.supplier?.name || open?.supplier_name || ""} entityId={payMany[0]?.entity_id || selectedEntity}
          ptName={ptName} bills={payMany} allPt={allPt} onClose={() => setPayMany(null)}
          onDone={(_, msg) => sesudahBayar(msg)} />
      )}
    </div>
  );
}
