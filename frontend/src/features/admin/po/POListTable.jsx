/**
 * POListTable — daftar Pesanan Pembelian LEBAR PENUH (fase 3 · P5, D-18 + L-06).
 *
 * Dulu: tabel `min-w-[860px]` berbagi layar dengan panel kanan 360 px ("Pilih PO untuk lihat detail" — kosong
 * sampai baris diklik), lalu panel ringkas itu punya tombol "Lihat detail lengkap" ke pop-up kedua. Dua tingkat
 * rincian untuk satu dokumen. Kini klik baris = SATU pop-up rincian (ringkasan + aksi + isi lengkap), daftar
 * memakai lebar penuh; di HP baris menjadi kartu (ResponsiveTable). Testid baris lama dipertahankan.
 */
import { Package } from "lucide-react";
import ResponsiveTable from "../../../components/ResponsiveTable";
import { formatCurrency } from "../../../utils/formatters";
import { getStatusBadge, billingState, lateState } from "./poUtils";
import { receiptVarianceSummary } from "./POReceiptVariancePanel";

const nf = new Intl.NumberFormat("id-ID");

function qtyOf(po) {
  const items = po.items || [];
  const qOrder = items.reduce((s, it) => s + Number(it.quantity || 0), 0);
  const qRecv = items.reduce((s, it) => s + Number(it.received_qty || 0), 0);
  const units = [...new Set(items.map((it) => it.unit).filter(Boolean))];
  return { items, qOrder, qRecv, unit: units.length === 1 ? units[0] : "" };
}

const COLUMNS = [
  { key: "po_number", header: "Nomor", mobile: "title",
    render: (po) => <span data-testid={`po-number-${po.id}`} className="font-bold text-[#007AFF] whitespace-nowrap">{po.po_number}</span> },
  { key: "status", header: "Status", mobile: "badge",
    render: (po) => {
      // b/d — badge penagihan di baris; telat & selisih terima ikut tampil tanpa membuka rincian.
      const bill = billingState(po);
      const late = lateState(po);
      const rvar = receiptVarianceSummary(po.receipt_variances);
      return (
        <span className="flex flex-col items-start gap-0.5 min-w-0">
          {getStatusBadge(po.status)}
          {bill && (
            <span data-testid={`po-row-billing-${po.id}`}
              className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[9.5px] font-semibold ${bill.cls}`}>{bill.label}</span>
          )}
          {late && (
            <span data-testid={`po-row-late-${po.id}`} title={`Janji kirim supplier: ${late.eta}`}
              className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[9.5px] font-semibold ${late.cls}`}>{late.label}</span>
          )}
          {rvar && (
            <span data-testid={`po-row-variance-${po.id}`} title={`Catatan gudang: ${rvar.label}`}
              className="whitespace-nowrap rounded px-1.5 py-0.5 text-[9.5px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">Selisih terima {rvar.label}</span>
          )}
        </span>
      );
    } },
  { key: "supplier", header: "Supplier", mobile: "subtitle",
    render: (po) => (
      <span className="min-w-0">
        <span data-testid={`po-supplier-${po.id}`} className="block font-semibold">{po.supplier_name}</span>
        <span className="block text-[10.5px] text-[#6B6B73]">{(po.items || []).length} item</span>
      </span>
    ) },
  { key: "warehouse", header: "Gudang", priority: 3, render: (po) => po.warehouse_name },
  { key: "qty", header: "Qty Pesan / Terima", priority: 2,
    render: (po) => {
      /* UI/UX 2026-06 — qty pesan vs terima; "terima 0" disembunyikan bila barang memang belum mungkin diterima. */
      const { qOrder, qRecv, unit } = qtyOf(po);
      const showReceive = !["waiting_approval", "rejected", "cancelled"].includes(po.status);
      return (
        <span className="tabular-nums" data-testid={`po-qty-${po.id}`}>
          <span className="block font-semibold">{nf.format(qOrder)} {unit}</span>
          {showReceive && (
            <span className={`block text-[10px] ${qRecv >= qOrder && qOrder > 0 ? "text-green-600" : "text-[#6B6B73]"}`}>
              terima {nf.format(qRecv)}{qOrder > 0 ? ` (${Math.round((qRecv / qOrder) * 100)}%)` : ""}
            </span>
          )}
        </span>
      );
    } },
  { key: "total", header: "Total", align: "right", priority: 1,
    render: (po) => <span className="font-bold tabular-nums" data-testid={`po-total-${po.id}`}>{formatCurrency(po.grand_total ?? po.total_amount)}</span> },
  { key: "date", header: "Tanggal", priority: 4,
    render: (po) => (po.created_at
      ? new Date(po.created_at).toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "2-digit" }) : "—") },
];

export default function POListTable({ rows = [], loading = false, onOpen, emptyText, footer, selectedId }) {
  return (
    <ResponsiveTable testId="po-list" rows={rows} rowKey="id" loading={loading} columns={COLUMNS}
      onRowClick={(po) => onOpen?.(po.id)} rowTestId={(po) => `po-card-${po.id}`}
      rowClassName={(po) => (po.id === selectedId ? "bg-[#EFF4FF]" : "")}
      empty={(
        <span className="block py-4 text-center text-[12px] text-[#6B6B73]">
          <Package className="mx-auto mb-2 text-gray-300" size={28} />
          {emptyText}
        </span>
      )}
      footer={footer} />
  );
}
