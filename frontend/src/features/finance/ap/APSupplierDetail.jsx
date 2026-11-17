/**
 * APSupplierDetail (S5, pelatihan keuangan 18 Nov) — rincian hutang SATU pemasok (pop-up dari Keuangan › Hutang ›
 * Hutang per Pemasok). Sumber: `GET /vendor-bills/payables/by-supplier/{id}` (`ap_party_service.supplier_detail`).
 *
 *  · Kepala: nama pemasok (tautan kartu pemasok) · PT · kartu angka yang menyaring tabel tagihan (Sisa hutang · Lewat jatuh
 *    tempo · Bisa dibayar langsung · Lewat kontrabon).
 *  · Bilah: cari tagihan · saringan · jumlah · [Unduh rekap] (CSV, `utils/csvExport`) · [Bayar terpilih].
 *  · Tabel tagihan terbuka: centang (hanya tagihan yang bisa dibayar langsung) · umur · sisa · [Bayar] (form satu tagihan
 *    `PaySupplierModal`). Tagihan yang dipegang kontrabon aktif tidak bisa dicentang/dibayar langsung (PK-05) — ditulis
 *    "Bayar lewat kontrabon …".
 *  · Kontrabon terbuka: status, sisa bersih, [Bayar] bila status kontrabon boleh dibayar (kebijakan PT dari server).
 *  · Potongan belum dipakai (nota debit + uang muka ke pemasok): dipotong lewat kontrabon.
 *  · Semua PT: tombol bayar mati + alasan tertulis (L4).
 */
import { useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Download, FileText, Layers, PiggyBank, Wallet, X } from "lucide-react";
import { formatCurrency, formatDate } from "../../../utils/formatters";
import { ListToolbar, MetricRow, SearchInput } from "../../../components/ListPageParts";
import KNSelect from "../../../components/KNSelect";
import PagedRows from "../../../components/PagedRows";
import { can } from "../../../config/roles";
import { buildCsv, csvFilename, downloadCsv } from "../../../utils/csvExport";
import { openTrace } from "../../documents/trace/traceDeepLink";
import { DocPill, SupplierCardLink } from "../cards/partyCards";
import StatusBadge from "../../../components/StatusBadge";
import EmptyState from "../../../components/EmptyState";
import { TEKS_PILIH_PT } from "../payments/ReceivePaymentModal";
import { CSV_TAGIHAN, bisaDibayarLangsung } from "./apPartyApi";

const SARING_TAGIHAN = [
  { value: "semua", label: "Semua tagihan" },
  { value: "lewat", label: "Lewat jatuh tempo" },
  { value: "langsung", label: "Bisa dibayar langsung" },
  { value: "kontrabon", label: "Lewat kontrabon" },
];

/** Umur tagihan: ikon + teks + warna (StatusBadge), bukan warna saja. */
function UmurPill({ b }) {
  const lewat = b.days_past_due > 0;
  return (
    <StatusBadge testId={`ap-detail-age-${b.bill_id}`} className="whitespace-nowrap" tone={lewat ? "danger" : "success"}
      icon={lewat ? "alert" : "check"}
      label={lewat ? `Lewat ${b.days_past_due} hari` : b.days_past_due === 0 ? "Jatuh tempo hari ini" : `${-b.days_past_due} hari lagi`} />
  );
}

export default function APSupplierDetail({ detail, loading, error, onRetry, onClose, currentUser, allPt, ptName,
  onPayOne, onPayMany, notice = "" }) {
  const perms = currentUser?.permissions;
  const canPayBill = can(perms, "vendor_bill", "pay");
  const canPayCb = can(perms, "contra_bon", "pay");
  const [q, setQ] = useState("");
  const [saring, setSaring] = useState("semua");
  const [pilih, setPilih] = useState({});
  const bills = detail?.bills || [];
  const t = detail?.totals || {};
  const nama = detail?.supplier?.name || "Rincian hutang pemasok";

  const rows = useMemo(() => {
    const kata = q.trim().toLowerCase();
    return bills.filter((b) => (saring === "lewat" ? b.days_past_due > 0
      : saring === "langsung" ? bisaDibayarLangsung(b) : saring === "kontrabon" ? Boolean(b.contra_bon) : true))
      .filter((b) => !kata || [b.bill_number, b.supplier_invoice_no, b.po_number, b.contra_bon?.number]
        .some((v) => String(v || "").toLowerCase().includes(kata)));
  }, [bills, q, saring]);
  const bisa = bills.filter(bisaDibayarLangsung);
  const terpilih = bisa.filter((b) => pilih[b.bill_id]);
  const totalPilih = terpilih.reduce((s, b) => s + Number(b.outstanding || 0), 0);
  const semuaDipilih = bisa.length > 0 && terpilih.length === bisa.length;
  const toggleSemua = () => setPilih(semuaDipilih ? {} : Object.fromEntries(bisa.map((b) => [b.bill_id, true])));

  function unduh() {
    const base = `rekap-hutang-${(detail?.supplier?.code || nama).replace(/[^\w-]+/g, "-").toLowerCase()}`;
    downloadCsv(csvFilename(base, "all"), buildCsv(bills, CSV_TAGIHAN));
  }

  const kartu = [
    { k: "semua", label: "Sisa hutang", value: formatCurrency(t.outstanding), icon: Wallet, hint: `${t.bill_count || 0} tagihan`, testId: "ap-detail-total" },
    { k: "lewat", label: "Lewat jatuh tempo", value: formatCurrency(t.overdue), icon: AlertTriangle, tone: "var(--kn-danger-text)", testId: "ap-detail-overdue" },
    { k: "langsung", label: "Bisa dibayar langsung", value: formatCurrency(t.payable_direct), icon: CheckCircle2, testId: "ap-detail-direct" },
    { k: "kontrabon", label: "Lewat kontrabon", value: formatCurrency(t.held), icon: Layers, testId: "ap-detail-held" },
  ].map(({ k, ...c }) => ({ ...c, active: saring === k, onClick: () => setSaring(saring === k ? "semua" : k) }));

  return (
    <div className="section-card" data-testid="ap-supplier-detail">
      <div className="section-head flex-wrap items-start gap-x-2 gap-y-1.5">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-2 gap-y-1">
          <FileText size={15} className="flex-shrink-0 text-kn-action" aria-hidden="true" />
          <h2 className="min-w-0 normal-case break-words" data-testid="ap-detail-supplier">
            {detail?.supplier?.id
              ? <SupplierCardLink id={detail.supplier.id} name={nama} perms={perms} testId="ap-detail-card" />
              : nama}
          </h2>
          {detail?.supplier?.code && <span className="text-fs-12 font-bold text-kn-action">{detail.supplier.code}</span>}
          {(detail?.entities || []).length > 0 && (
            <span className="text-fs-12 text-kn-text-2" data-testid="ap-detail-pt">· PT {(detail.entities || []).map((e) => e.label).join(", ")}</span>
          )}
        </div>
        <button type="button" data-testid="ap-detail-close" className="icon-button flex-shrink-0" onClick={onClose} aria-label="Tutup"><X size={14} /></button>
      </div>
      <div className="section-body space-y-3">
        {notice && <div className="notice-bar success" role="status" data-testid="ap-detail-notice">{notice}</div>}
        {loading && !detail ? (
          <div className="grid gap-2" data-testid="ap-detail-loading">{[0, 1, 2].map((i) => <div key={i} className="h-9 animate-pulse rounded bg-kn-neutral-soft" />)}</div>
        ) : error ? (
          <div className="notice-bar danger flex flex-wrap items-center gap-2" role="alert" data-testid="ap-detail-error">
            <AlertTriangle size={14} aria-hidden="true" /><span className="min-w-0 flex-1">{error}</span>
            {onRetry && <button type="button" className="secondary-button btn-sm" onClick={onRetry}>Coba lagi</button>}
          </div>
        ) : detail && (
          <>
            <MetricRow testId="ap-detail-metrics" items={kartu} />
            {(canPayBill || canPayCb) && allPt && <p className="text-fs-12 text-kn-text-2" data-testid="ap-detail-pay-scope-note">{TEKS_PILIH_PT}</p>}
            <ListToolbar testId="ap-detail-toolbar" count={`${rows.length} tagihan`}
              actions={<>
                <button type="button" className="secondary-button btn-sm whitespace-nowrap" onClick={unduh} disabled={!bills.length}
                  data-testid="ap-detail-download"><Download size={13} aria-hidden="true" /> Unduh rekap</button>
                {canPayBill && (
                  <button type="button" className="primary-button btn-sm whitespace-nowrap" data-testid="ap-detail-pay-many"
                    disabled={allPt || !terpilih.length} title={!terpilih.length ? "Centang tagihan yang akan dibayar." : undefined}
                    onClick={() => onPayMany?.(terpilih)}>
                    <Wallet size={13} aria-hidden="true" /> Bayar terpilih ({terpilih.length}){terpilih.length ? ` · ${formatCurrency(totalPilih)}` : ""}
                  </button>
                )}
              </>}>
              <SearchInput testId="ap-detail-search" placeholder="Cari no. tagihan / faktur / PO…" value={q} onChange={setQ}
                className="min-w-[200px] flex-1 sm:max-w-[300px]" />
              <KNSelect data-testid="ap-detail-filter" aria-label="Saringan tagihan" value={saring} onValueChange={(v) => setSaring(v || "semua")}
                options={SARING_TAGIHAN} className="!h-auto !w-auto min-w-[190px] rounded-lg border border-kn-field-border bg-white !px-2 !py-1.5 text-fs-13" />
            </ListToolbar>
            {!rows.length ? (
              <EmptyState compact kind={bills.length ? "filtered" : "empty"} what="tagihan terbuka"
                title={bills.length ? undefined : "Tidak ada tagihan terbuka."} onReset={() => { setQ(""); setSaring("semua"); }}
                testId={bills.length ? "ap-detail-nomatch" : "ap-detail-empty"} />
            ) : (
              <div className="table-wrap">
                <table className="data-table head-wrap min-w-[860px]" data-testid="ap-detail-bills">
                  <thead>
                    <tr>
                      <th className="w-8">
                        {canPayBill && bisa.length > 0 && (
                          <input type="checkbox" aria-label="Pilih semua tagihan yang bisa dibayar langsung" checked={semuaDipilih}
                            disabled={allPt} onChange={toggleSemua} data-testid="ap-detail-check-all" />
                        )}
                      </th>
                      <th>Tagihan</th><th>PO</th><th>Jatuh tempo</th><th>Umur</th>
                      <th className="text-right">Total</th><th className="text-right">Dibayar</th><th className="text-right">Sisa</th>
                      <th className="col-sticky-end text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody>
                    <PagedRows rows={rows} pageSize={10} testId="ap-detail-bills-pager">{(b) => (
                      <tr key={b.bill_id} data-testid={`ap-detail-bill-${b.bill_id}`}>
                        <td>
                          {canPayBill && bisaDibayarLangsung(b) && (
                            <input type="checkbox" aria-label={`Pilih ${b.bill_number}`} checked={!!pilih[b.bill_id]} disabled={allPt}
                              onChange={(e) => setPilih((p) => ({ ...p, [b.bill_id]: e.target.checked }))} data-testid={`ap-detail-check-${b.bill_id}`} />
                          )}
                        </td>
                        <td className="whitespace-nowrap">
                          <button type="button" className="link-button font-semibold"
                            onClick={() => openTrace({ docType: "vendor_bill", docId: b.bill_id, number: b.bill_number })}>{b.bill_number}</button>
                          {b.supplier_invoice_no && <span className="block text-fs-12 text-kn-text-2">{b.supplier_invoice_no}</span>}
                        </td>
                        <td className="whitespace-nowrap">{b.po_number || "—"}</td>
                        <td className="whitespace-nowrap">{b.due_date ? formatDate(b.due_date) : "—"}</td>
                        <td><UmurPill b={b} /></td>
                        <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(b.grand_total)}</td>
                        <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(b.amount_paid)}</td>
                        <td className="whitespace-nowrap text-right font-semibold tabular-nums" data-testid={`ap-detail-sisa-${b.bill_id}`}>{formatCurrency(b.outstanding)}</td>
                        <td className="col-sticky-end text-right">
                          {b.contra_bon ? (
                            <span className="text-fs-12 text-kn-text-2" data-testid={`ap-detail-held-${b.bill_id}`}>
                              Bayar lewat kontrabon {b.contra_bon.number}
                            </span>
                          ) : canPayBill ? (
                            <button type="button" className="secondary-button btn-sm whitespace-nowrap" disabled={allPt}
                              data-testid={`ap-detail-pay-${b.bill_id}`} onClick={() => onPayOne?.({ type: "vendor_bill", id: b.bill_id })}>
                              <Wallet size={12} aria-hidden="true" /> Bayar
                            </button>
                          ) : <span className="text-fs-12 text-kn-text-2">—</span>}
                        </td>
                      </tr>
                    )}</PagedRows>
                  </tbody>
                </table>
              </div>
            )}

            {detail.contra_bons !== null && (
              <div data-testid="ap-detail-contra-bons">
                <h3 className="mb-1.5 flex items-center gap-1.5 text-fs-13 font-bold text-kn-text"><Layers size={14} aria-hidden="true" />Kontrabon terbuka</h3>
                {!(detail.contra_bons || []).length ? (
                  <EmptyState compact kind="empty" what="kontrabon" title="Tidak ada kontrabon terbuka." testId="ap-detail-cb-empty" />
                ) : (
                  <div className="table-wrap">
                    <table className="data-table head-wrap" data-testid="ap-detail-cb-table">
                      <thead><tr><th>Nomor</th><th>Status</th><th className="text-right">Faktur</th><th className="text-right">Bersih</th>
                        <th className="text-right">Sisa</th><th className="col-sticky-end text-right">Aksi</th></tr></thead>
                      <tbody>
                        {(detail.contra_bons || []).map((c) => (
                          <tr key={c.id} data-testid={`ap-detail-cb-${c.id}`}>
                            <td className="whitespace-nowrap">
                              <button type="button" className="link-button font-semibold"
                                onClick={() => openTrace({ docType: "contra_bon", docId: c.id, number: c.number })}>{c.number}</button>
                            </td>
                            <td><DocPill status={c.status === "scheduled_payment" ? "scheduled" : c.status} label={c.status_label} /></td>
                            <td className="text-right tabular-nums">{c.bill_count}</td>
                            <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(c.net_payable)}</td>
                            <td className="whitespace-nowrap text-right font-semibold tabular-nums">{formatCurrency(c.outstanding)}</td>
                            <td className="col-sticky-end text-right">
                              {c.payable && canPayCb && Number(c.outstanding) > 0.005 ? (
                                <button type="button" className="secondary-button btn-sm whitespace-nowrap" disabled={allPt}
                                  data-testid={`ap-detail-cb-pay-${c.id}`} onClick={() => onPayOne?.({ type: "contra_bon", id: c.id })}>
                                  <Wallet size={12} aria-hidden="true" /> Bayar
                                </button>
                              ) : (
                                <span className="text-fs-12 text-kn-text-2" data-testid={`ap-detail-cb-wait-${c.id}`}>
                                  {c.payable ? "—" : "Belum bisa dibayar — selesaikan dulu langkah kontrabonnya"}
                                </span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            <div data-testid="ap-detail-credits">
              <h3 className="mb-1.5 flex items-center gap-1.5 text-fs-13 font-bold text-kn-text"><PiggyBank size={14} aria-hidden="true" />Potongan belum dipakai</h3>
              {!(detail.credits || []).length ? (
                <EmptyState compact kind="empty" what="potongan" title="Tidak ada nota debit atau uang muka ke pemasok yang belum dipotong."
                  testId="ap-detail-credits-empty" />
              ) : (
                <>
                  <div className="table-wrap">
                    <table className="data-table head-wrap" data-testid="ap-detail-credits-table">
                      <thead><tr><th>Dokumen</th><th>Tanggal</th><th className="text-right">Sisa belum dipotong</th></tr></thead>
                      <tbody>
                        {(detail.credits || []).map((c) => (
                          <tr key={c.ref_id} data-testid={`ap-detail-credit-${c.ref_id}`}>
                            <td>{c.label}{c.po_number ? <span className="block text-fs-12 text-kn-text-2">PO {c.po_number}</span> : null}</td>
                            <td className="whitespace-nowrap">{c.date ? formatDate(c.date) : "—"}</td>
                            <td className="whitespace-nowrap text-right tabular-nums">{formatCurrency(c.amount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-1 text-fs-12 text-kn-text-2">Potongan dipakai lewat kontrabon (Hutang › Kontrabon), bukan di form bayar.</p>
                </>
              )}
            </div>
            {ptName && !allPt && <p className="text-fs-12 text-kn-text-2">Angka milik PT {ptName} saja.</p>}
          </>
        )}
      </div>
    </div>
  );
}
