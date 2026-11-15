import { useEffect, useMemo, useState } from "react";
import axios, { API } from "../../services/apiClient";
import { ArrowLeft, Edit3, Truck, Building2, Clock, MapPin, PhoneCall, Wallet, AlertTriangle, PiggyBank,
  ClipboardList, Receipt, Undo2, FileText } from "lucide-react";
import { formatCurrency, formatDate } from "../../utils/formatters";
import RecordDetailModal from "../documents/RecordDetailModal";
import SupplierPriceList from "./SupplierPriceList";
import SupplierScorecard from "./SupplierScorecard";
import AuditHistoryPanel from "../../components/AuditHistoryPanel";
import FilterChips from "../../components/FilterChips";
import PagedRows from "../../components/PagedRows";
import { MetricRow } from "../../components/ListPageParts";
import { can } from "../../config/roles";
import { PO_PAYMENT_LABEL } from "../admin/po/poUtils";
import { docStatusLabel } from "../../utils/docStatus";
import { DocPill, SectionState } from "../finance/cards/partyCards";
import PaySupplierModal from "../finance/payments/PaySupplierModal";
import { TEKS_PILIH_PT } from "../finance/payments/ReceivePaymentModal";

/**
 * Kartu pemasok (dulu "Supplier 360°") — MN-T3.
 *  · `variant="card"`: dibuka dari baris mana pun lewat `openSupplierCard(id)` (pop-up rincian `PartyCardHost`).
 *  · `variant="page"` (bawaan): layar Pemasok — komponen sama, ditambah kolom profil & tombol Ubah.
 * Kepala: nama, PT, tiga angka "Saldo hutang" · "Jatuh tempo 7 hari" · "Uang muka ke pemasok" (`payables` dari
 * `GET /suppliers/{id}/360`; Semua PT = angka per PT berlabel, tanpa dijumlah). Bagian (enam, menurut `sections_allowed`):
 * Tagihan · Kontrabon · Pembayaran · Retur · PO & Biaya Masuk · Lainnya (harga, dokumen, skor, riwayat perubahan).
 * Baris tagihan/kontrabon yang masih bersisa punya tombol "Bayar" (izin `vendor_bill.pay` / `contra_bon.pay`) yang
 * membuka satu form `PaySupplierModal`; Semua PT → tombol mati + alasan tertulis di atas tabel.
 * Lebar tabel (kartu ±864 px; halaman 1280 px kolom kanan ±686 px): Tagihan 7 kolom ±666 px, Kontrabon 7 kolom ±652 px,
 * Pembayaran 5 kolom ±588 px; kolom aksi `col-sticky-end`.
 */
const SECTIONS = [
  { key: "tagihan", label: "Tagihan" },
  { key: "kontrabon", label: "Kontrabon" },
  { key: "pembayaran", label: "Pembayaran" },
  { key: "retur", label: "Retur" },
  { key: "po_biaya", label: "PO & Biaya Masuk" },
  { key: "lainnya", label: "Lainnya" },
];
const OTHER = [
  { key: "prices", label: "Daftar harga" },
  { key: "documents", label: "Dokumen" },
  { key: "scorecard", label: "Skor" },
];
const CB_PAYABLE = new Set(["approved", "scheduled", "verified"]);
const money = (v) => formatCurrency(Number(v || 0));
const fmtDate = (s) => (s ? formatDate(s) : "—");

export default function Supplier360Panel({ supplierId, currentUser, selectedEntity, onBack, onEdit, onError, variant = "page" }) {
  const isCard = variant === "card";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState("");
  const [section, setSection] = useState("");
  const [other, setOther] = useState("prices");
  const [record, setRecord] = useState(null);
  const [payFor, setPayFor] = useState(null);
  const [notice, setNotice] = useState("");
  const perms = currentUser?.permissions;
  const canManage = can(perms, "supplier", "update");
  const canAudit = can(perms, "audit", "view");
  const canPayBill = can(perms, "vendor_bill", "pay");
  const canPayCb = can(perms, "contra_bon", "pay");
  const allPt = !selectedEntity || selectedEntity === "all";

  useEffect(() => { load(); }, [supplierId]); // eslint-disable-line
  async function load() {
    setLoading(true);
    try { const r = await axios.get(`${API}/suppliers/${supplierId}/360`); setData(r.data); setLoadErr(""); }
    catch (e) {
      const msg = e.response?.data?.detail || "Kartu pemasok belum bisa dimuat.";
      if (isCard) setLoadErr(msg); else { onError?.(msg); onBack?.(); }
    } finally { setLoading(false); }
  }

  const sections = useMemo(() => {
    const ok = new Set(data?.sections_allowed || []);
    return SECTIONS.filter((s) => ok.has(s.key));
  }, [data]);
  const active = sections.some((s) => s.key === section) ? section : sections[0]?.key || "";

  if (loading && !data) return <div className="section-card section-pad text-center text-fs-12 text-kn-text-2" data-testid="supplier-360-loading">Memuat kartu pemasok…</div>;
  if (loadErr) return <div className="section-card section-pad text-fs-13 text-kn-danger-text" role="alert" data-testid="supplier-360-error">{loadErr}</div>;
  if (!data) return null;

  const allowed = new Set(data.sections_allowed || []);
  const pay = data.payables;
  const entityId = data.entity_id;
  const pos = data.purchase_orders || [];
  const bills = data.bills || [];
  const cbs = data.contra_bons || [];
  const lcs = data.landed_costs || [];
  const rets = data.returns || [];
  const docs = data.documents || [];
  const ptOf = (id) => (data.scope_entities || []).find((e) => e.entity_id === id)?.label || "";

  function openPO(p) {
    setRecord({
      icon: <ClipboardList size={17} className="text-kn-action" />, title: p.po_number || p.id, code: p.po_number,
      statusText: docStatusLabel(p.status), statusTone: "muted",
      docType: "purchase_order", sourceId: p.id, number: p.po_number, entityId, esignable: true,
      meta: [
        { label: "Tanggal", value: fmtDate(p.created_at) },
        { label: "Status", value: docStatusLabel(p.status) },
        { label: "Status Bayar", value: PO_PAYMENT_LABEL[p.payment_status] || p.payment_status || "—" },
        { label: "Total", value: money(p.total_amount) },
        { label: "Dibayar", value: money(p.amount_paid) },
        { label: "Sudah Ditagih", value: money(p.billed_total) },
      ],
      items: p.items || [],
      itemColumns: [
        { label: "Produk", render: (r) => <span className="font-medium">{r.product_name || r.sku || r.product_id}</span> },
        { label: "Qty", align: "right", render: (r) => `${r.quantity ?? r.qty ?? 0} ${r.unit || ""}` },
        { label: "Harga", align: "right", render: (r) => money(r.price) },
        { label: "Subtotal", align: "right", render: (r) => money(r.line_total ?? r.subtotal) },
      ],
      totals: [
        { label: "Subtotal", value: money(p.net_subtotal ?? p.total_amount) },
        ...(p.ppn_amount ? [{ label: "PPN", value: money(p.ppn_amount) }] : []),
        { label: "Grand Total", value: money(p.grand_total ?? p.total_amount), bold: true },
      ],
    });
  }
  function openBill(b) {
    const fin = b.financials || {};
    setRecord({
      icon: <Receipt size={17} className="text-kn-action" />, title: b.bill_number || b.id, code: b.bill_number,
      statusText: docStatusLabel(b.status), statusTone: "muted",
      docType: "vendor_bill", sourceId: b.id, number: b.bill_number, entityId: b.entity_id || entityId, esignable: true,
      meta: [
        { label: "Tanggal", value: fmtDate(b.bill_date || b.created_at) },
        { label: "Jatuh Tempo", value: fmtDate(b.due_date) },
        { label: "No. Faktur", value: b.supplier_invoice_no || "—" },
        { label: "Grand Total", value: money(fin.grand_total ?? b.grand_total) },
        { label: "Belum Lunas", value: money(fin.outstanding) },
      ],
      items: b.items || [], itemColumns: [],
      totals: [{ label: "Grand Total", value: money(fin.grand_total ?? b.grand_total), bold: true }],
    });
  }
  function openReturn(r) {
    setRecord({
      icon: <Undo2 size={17} className="text-kn-action" />, title: r.debit_note_number || r.number || r.id,
      code: r.debit_note_number || r.number, statusText: docStatusLabel(r.status), statusTone: "muted",
      docType: "purchase_return", sourceId: r.id, number: r.debit_note_number || r.number, entityId, esignable: false,
      meta: [
        { label: "Tanggal", value: fmtDate(r.created_at) },
        { label: "PO Sumber", value: r.po_number || "—" },
        { label: "Total", value: money(r.total_amount) },
        { label: "Alasan", value: r.reason || "—" },
      ],
      items: r.items || [], itemColumns: [],
      totals: [{ label: "Total Retur", value: money(r.total_amount), bold: true }],
    });
  }
  function openDoc(d) {
    setRecord({
      icon: <FileText size={17} className="text-kn-action" />, title: d.number, code: d.number,
      statusText: docStatusLabel(d.status), statusTone: "muted",
      docType: d.doc_type, sourceId: d.source_id, number: d.number, entityId, label: d.label,
      esignable: ["purchase_order", "vendor_bill"].includes(d.doc_type),
      meta: [{ label: "Jenis", value: d.label }, { label: "Tanggal", value: fmtDate(d.date) }, { label: "Nilai", value: money(d.amount) }],
    });
  }

  const payNote = (canPayBill || canPayCb) && allPt && (
    <p className="mb-2 text-fs-12 text-kn-text-2" data-testid="supplier-360-pay-scope-note">{TEKS_PILIH_PT}</p>
  );
  const PayBtn = ({ type, row, outstanding }) => {
    const ok = type === "vendor_bill" ? canPayBill && row.status === "posted" : canPayCb && CB_PAYABLE.has(row.status);
    if (!ok || !(Number(outstanding) > 0.01)) return <span className="text-fs-12 text-kn-text-2">—</span>;
    return (
      <button type="button" className="primary-button btn-sm whitespace-nowrap" disabled={allPt}
        data-testid={`supplier-360-pay-${row.id}`} onClick={() => setPayFor({ type, id: row.id })}>
        <Wallet size={12} aria-hidden="true" /> Bayar
      </button>
    );
  };

  const head = (
    <div className="section-card mb-3">
      <div className="section-head">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Truck size={18} className="text-kn-action" aria-hidden="true" />
            <h2 className="truncate" data-testid="supplier-360-name">{data.name}</h2>
            <span className="text-fs-12 font-bold text-kn-action">{data.code}</span>
            <DocPill status={data.status === "active" ? "done" : "draft"} label={data.status === "active" ? "Aktif" : "Nonaktif"} />
          </div>
          <p className="mt-0.5 flex flex-wrap items-center gap-2 text-fs-12 text-kn-text-2">
            {data.city && <span className="flex items-center gap-1"><Building2 size={12} aria-hidden="true" />{data.city}</span>}
            {entityId && <span>· PT {ptOf(entityId) || entityId}</span>}
            {data.goods_type && <span>· {data.goods_type}</span>}
            {data.lead_time_days > 0 && <span className="flex items-center gap-1"><Clock size={12} aria-hidden="true" />{data.lead_time_days} hari lead</span>}
          </p>
        </div>
        {!isCard && canManage && <button data-testid="supplier-360-edit" onClick={() => onEdit?.(data)} className="secondary-button btn-sm whitespace-nowrap"><Edit3 size={13} /> Ubah</button>}
      </div>
      {allowed.has("ringkasan") && pay && (
        <div className="section-body pt-0" data-testid="supplier-card-head">
          {pay.single_entity ? (
            <MetricRow testId="supplier-card-metrics" items={[
              { label: "Saldo hutang", value: money(pay.outstanding), icon: Wallet, testId: "supplier-card-payable" },
              { label: `Jatuh tempo ${pay.due_soon_days} hari`, value: money(pay.due_soon), icon: AlertTriangle, testId: "supplier-card-due" },
              { label: "Uang muka ke pemasok", value: money(pay.advance), icon: PiggyBank, testId: "supplier-card-advance" },
            ]} />
          ) : (
            <div className="grid gap-2" data-testid="supplier-card-per-pt">
              {(pay.by_entity || []).map((e) => (
                <div key={e.entity_id}>
                  <p className="field-label">PT {e.label}</p>
                  <MetricRow testId={`supplier-card-metrics-${e.entity_id}`} items={[
                    { label: "Saldo hutang", value: money(e.outstanding), icon: Wallet },
                    { label: `Jatuh tempo ${pay.due_soon_days} hari`, value: money(e.due_soon), icon: AlertTriangle },
                    { label: "Uang muka ke pemasok", value: money(e.advance), icon: PiggyBank },
                  ]} />
                </div>
              ))}
              <p className="text-fs-12 text-kn-text-2">Semua PT: angka per PT, tidak dijumlah lintas PT.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );

  const body = (
    <div className="section-card self-start" data-testid="supplier-360-sections">
      <div className="section-head">
        <FilterChips testId="supplier-360-section" ariaLabel="Bagian kartu pemasok" value={active} onChange={setSection}
          options={sections.map((s) => ({ ...s, count: { tagihan: bills.length, kontrabon: cbs.length, pembayaran: (data.payments || []).length,
            retur: rets.length }[s.key] }))} chipTestId={(k) => `supplier-360-tab-${k}`} />
      </div>
      <div className="section-body">
        {active === "tagihan" && (
          <SectionState empty={!bills.length} testId="supplier-360-bills">
            {payNote}
            <div className="table-wrap">
              <table className="data-table head-wrap" data-testid="supplier-360-bills-table">
                <thead><tr><th>Nomor</th><th>Tanggal</th><th>Jatuh tempo</th><th className="text-right">Total</th>
                  <th className="text-right">Sisa</th><th>Status</th><th className="col-sticky-end text-right">Aksi</th></tr></thead>
                <tbody>
                  <PagedRows rows={bills} pageSize={10} testId="supplier-360-bills-pager">{(b) => (
                    <tr key={b.id} data-testid={`supplier-360-bill-${b.id}`}>
                      <td className="whitespace-nowrap"><button type="button" className="link-button font-semibold" onClick={() => openBill(b)}>{b.bill_number || b.id}</button></td>
                      <td className="whitespace-nowrap">{fmtDate(b.bill_date || b.created_at)}</td>
                      <td className="whitespace-nowrap">{fmtDate(b.due_date)}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{money(b.financials?.grand_total)}</td>
                      <td className="whitespace-nowrap text-right font-semibold tabular-nums">{money(b.financials?.outstanding)}</td>
                      <td><DocPill status={b.status} /></td>
                      <td className="col-sticky-end text-right"><PayBtn type="vendor_bill" row={b} outstanding={b.financials?.outstanding} /></td>
                    </tr>
                  )}</PagedRows>
                </tbody>
              </table>
            </div>
            <p className="mt-1 text-fs-12 text-kn-text-2" data-testid="supplier-360-bills-total">{bills.length} tagihan</p>
          </SectionState>
        )}
        {active === "kontrabon" && (
          <SectionState empty={!cbs.length} testId="supplier-360-cbs">
            {payNote}
            <div className="table-wrap">
              <table className="data-table head-wrap" data-testid="supplier-360-cbs-table">
                <thead><tr><th>Nomor</th><th>Tanggal</th><th className="text-right">Faktur</th><th className="text-right">Bersih</th>
                  <th className="text-right">Sisa</th><th>Status</th><th className="col-sticky-end text-right">Aksi</th></tr></thead>
                <tbody>
                  <PagedRows rows={cbs} pageSize={10} testId="supplier-360-cbs-pager">{(c) => (
                    <tr key={c.id} data-testid={`supplier-360-cb-${c.id}`}>
                      <td className="whitespace-nowrap font-semibold">{c.number}</td>
                      <td className="whitespace-nowrap">{fmtDate(c.created_at)}</td>
                      <td className="text-right tabular-nums">{(c.bills || []).length}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{money(c.totals?.net_payable)}</td>
                      <td className="whitespace-nowrap text-right font-semibold tabular-nums">{money(c.totals?.outstanding)}</td>
                      <td><DocPill status={c.status} label={c.status_label} /></td>
                      <td className="col-sticky-end text-right"><PayBtn type="contra_bon" row={c} outstanding={c.totals?.outstanding} /></td>
                    </tr>
                  )}</PagedRows>
                </tbody>
              </table>
            </div>
            <p className="mt-1 text-fs-12 text-kn-text-2">{cbs.length} kontrabon</p>
          </SectionState>
        )}
        {active === "pembayaran" && (
          <SectionState empty={!(data.payments || []).length} testId="supplier-360-payments">
            <div className="table-wrap">
              <table className="data-table head-wrap" data-testid="supplier-360-payments-table">
                <thead><tr><th>Tanggal</th><th>Dokumen</th><th>Cara bayar</th><th>Kas</th><th className="text-right">Nominal</th></tr></thead>
                <tbody>
                  <PagedRows rows={data.payments || []} pageSize={10} testId="supplier-360-payments-pager">{(p) => (
                    <tr key={p.id} data-testid={`supplier-360-payment-${p.id}`}>
                      <td className="whitespace-nowrap">{fmtDate(p.paid_at)}</td>
                      <td><span className="font-semibold">{p.bill_number}</span>
                        {p.contra_bon_number && <span className="block text-fs-12 text-kn-text-2">lewat {p.contra_bon_number}</span>}</td>
                      <td>{p.non_cash ? "Potongan (non-kas)" : p.method === "kontrabon" ? "Kontrabon" : (p.method || "—")}</td>
                      <td className="whitespace-nowrap">{p.cash_txn_number || "—"}</td>
                      <td className="whitespace-nowrap text-right tabular-nums">{money(p.amount)}</td>
                    </tr>
                  )}</PagedRows>
                </tbody>
              </table>
            </div>
            <p className="mt-1 text-fs-12 text-kn-text-2">{(data.payments || []).length} pembayaran</p>
          </SectionState>
        )}
        {active === "retur" && (
          <RowList testId="supplier-360-list-returns" rows={rets} onClick={openReturn}
            render={(r) => ({ id: r.id, title: r.debit_note_number || r.number || r.id, sub: `${fmtDate(r.created_at)} · ${docStatusLabel(r.status)}`, amount: money(r.total_amount) })} />
        )}
        {active === "po_biaya" && (
          <div className="grid gap-3">
            {data.purchase_orders !== null && (
              <div><h4 className="mb-1 text-fs-13 font-bold">Pesanan pembelian</h4>
                <RowList testId="supplier-360-list-po" rows={pos} onClick={openPO}
                  render={(p) => ({ id: p.id, title: p.po_number || p.id, sub: `${fmtDate(p.created_at)} · ${docStatusLabel(p.status)}`, amount: money(p.total_amount) })} /></div>
            )}
            {data.landed_costs !== null && (
              <div><h4 className="mb-1 text-fs-13 font-bold">Biaya masuk barang</h4>
                <RowList testId="supplier-360-list-landed" rows={lcs} onClick={() => {}}
                  render={(v) => ({ id: v.id, title: v.voucher_number || v.id, sub: `${fmtDate(v.created_at)} · ${docStatusLabel(v.status)} · sisa ${money(v.financials?.outstanding)}`, amount: money(v.financials?.total_cost) })} /></div>
            )}
          </div>
        )}
        {active === "lainnya" && (
          <div className="grid gap-2">
            <FilterChips testId="supplier-360-other" ariaLabel="Lainnya" value={other} onChange={setOther}
              options={[...OTHER, ...(canAudit ? [{ key: "changes", label: "Riwayat perubahan" }] : [])]} chipTestId={(k) => `supplier-360-other-${k}`} />
            {other === "prices" && (
              <div className="space-y-3" data-testid="supplier-360-prices">
                <SupplierPriceList supplierId={data.id} canManage={canManage} />
                <PriceHistory history={data.price_history || []} />
              </div>
            )}
            {other === "documents" && <RowList testId="supplier-360-list-documents" rows={docs} onClick={openDoc}
              render={(d) => ({ id: d.source_id, title: `${d.label} · ${d.number}`, sub: `${fmtDate(d.date)} · ${docStatusLabel(d.status)}`, amount: money(d.amount) })} />}
            {other === "scorecard" && <SupplierScorecard supplierId={data.id} />}
            {other === "changes" && canAudit && <AuditHistoryPanel entityType="supplier" entityId={data.id} testIdPrefix="supplier-360-changes" />}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div data-testid={isCard ? "supplier-card-panel" : "supplier-360-panel"}>
      {!isCard && <button data-testid="supplier-360-back" onClick={onBack} className="secondary-button btn-sm mb-3"><ArrowLeft size={13} /> Kembali ke daftar</button>}
      {notice && (
        <div className="notice-bar success mb-3" data-testid="supplier-360-notice">
          <span>{notice}</span><button type="button" onClick={() => setNotice("")} aria-label="Tutup">×</button>
        </div>
      )}
      {head}
      {isCard ? body : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-[320px_1fr]">
          <ProfileCard data={data} />
          {body}
        </div>
      )}
      <RecordDetailModal open={!!record} onClose={() => setRecord(null)} currentUser={currentUser} onChanged={load} {...(record || {})} />
      {payFor && (
        <PaySupplierModal target={payFor} onClose={() => setPayFor(null)}
          onPaid={(_, msg) => { setPayFor(null); setNotice(msg || "Pembayaran dicatat."); load(); }} />
      )}
    </div>
  );
}

function ProfileCard({ data }) {
  const fin = data.finance || {};
  return (
    <div className="section-card self-start">
      <div className="section-head"><h3 className="text-fs-13 font-bold">Profil & Kontak</h3></div>
      <div className="section-body space-y-2 text-fs-12">
        <p className="flex items-center gap-2"><PhoneCall size={12} className="text-kn-text-2" aria-hidden="true" /><span className="font-semibold">{data.pic_name || "—"}</span>{data.phone ? <span className="ml-auto text-kn-text-2">{data.phone}</span> : null}</p>
        {data.email && <p className="pl-5 text-kn-text-2">{data.email}</p>}
        <p className="flex items-start gap-2"><MapPin size={12} className="mt-0.5 text-kn-text-2" aria-hidden="true" /><span>{[data.address, data.city].filter(Boolean).join(", ") || "—"}</span></p>
        <div className="space-y-1 border-t border-kn-divider pt-2">
          {data.npwp && <p><span className="text-kn-text-2">NPWP:</span> {data.npwp}</p>}
          <p><span className="text-kn-text-2">Jenis Barang:</span> {data.goods_type || "—"}</p>
          <p><span className="text-kn-text-2">Termin Pembayaran:</span> {data.payment_term_code || fin.payment_term_code || "—"}</p>
          <p><span className="text-kn-text-2">Lead time:</span> {fin.lead_time_days || 0} hari{fin.avg_lead_time_days != null ? ` (rata-rata ${fin.avg_lead_time_days})` : ""}</p>
          {fin.rating != null && <p><span className="text-kn-text-2">Rating:</span> {fin.rating} / 5</p>}
        </div>
        {data.notes && <p className="border-t border-kn-divider pt-2">{data.notes}</p>}
      </div>
    </div>
  );
}

function RowList({ rows, render, onClick, testId }) {
  if (!rows.length) return <p className="py-4 text-center text-fs-12 text-kn-text-2" data-testid={`${testId}-empty`}>Belum ada data.</p>;
  return (
    <div data-testid={testId}>
      <table className="w-full"><tbody className="divide-y divide-kn-divider">
        <PagedRows rows={rows} pageSize={10} testId={`${testId}-pager`}>{(row, i) => {
          const r = render(row);
          return (
            <tr key={r.id || i}><td>
              <button type="button" data-testid={`${testId}-row-${r.id || i}`} onClick={() => onClick(row)}
                className="ghost-button flex w-full items-center justify-between gap-2 text-left text-fs-12">
                <span className="min-w-0"><span className="block truncate font-semibold text-kn-action">{r.title}</span><span className="block text-kn-text-2">{r.sub}</span></span>
                <span className="shrink-0 whitespace-nowrap font-semibold tabular-nums">{r.amount}</span>
              </button>
            </td></tr>
          );
        }}</PagedRows>
      </tbody></table>
      <p className="mt-1 text-fs-12 text-kn-text-2">{rows.length} baris</p>
    </div>
  );
}

function PriceHistory({ history }) {
  if (!history.length) return null;
  return (
    <div className="section-card" data-testid="supplier-360-price-history">
      <div className="section-head"><h3 className="text-fs-13 font-bold">Riwayat Harga (dari PO)</h3></div>
      <div className="section-body space-y-2">
        {history.map((h) => (
          <div key={h.product_id} className="rounded-lg border border-kn-divider p-2">
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="text-fs-12 font-semibold">{h.product_name}</p>
              <span className="text-fs-12 text-kn-text-2">terakhir <b className="text-kn-action">{money(h.last_price)}</b> · {h.points} titik</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {h.entries.slice(0, 8).map((e, i) => (
                <span key={i} className="status-pill status-draft" title={`${e.po_number} · ${fmtDate(e.date)}`}>
                  {money(e.price)} · {fmtDate(e.date)}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
