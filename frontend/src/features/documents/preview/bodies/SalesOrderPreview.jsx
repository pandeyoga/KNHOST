/** Isi pratinjau pesanan penjualan: fakta, baris barang, total. Data dari `GET /sales-orders/{id}` (sudah termuat). */
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { docStatusLabel } from "../../../../utils/docStatus";
import { formatCurrency, formatDate, formatDateTime, formatQty } from "../../../../utils/formatters";
import { CustomerCardLink, DocPill } from "../../../finance/cards/partyCards";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

const num = (v) => Number(v) || 0;

export default function SalesOrderPreview({ doc, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const items = Array.isArray(doc.items) ? doc.items : [];
  const adaDiskon = items.some((it) => num(it.discount_percent) > 0 || num(it.discount_amount) > 0);
  const total = doc.grand_total != null ? num(doc.grand_total) : num(doc.total_amount);
  const dibayar = num(doc.paid_total);

  const kolom = [
    { key: "product", label: "Barang", render: (it) => (
      <div>
        <span className="font-semibold">{it.product_name}</span>
        {it.sku && <span className="block text-fs-12 text-kn-text-2">{it.sku}</span>}
      </div>) },
    { key: "quantity", label: "Jumlah", align: "right", render: (it) => `${formatQty(it.quantity)} ${it.unit || ""}`.trim() },
    { key: "price", label: "Harga", align: "right", render: (it) => formatCurrency(it.price) },
  ];
  if (adaDiskon) {
    kolom.push({ key: "discount", label: "Diskon", align: "right", render: (it) => (num(it.discount_percent) > 0 ? `${formatQty(it.discount_percent)}%` : num(it.discount_amount) > 0 ? formatCurrency(it.discount_amount) : "") });
  }
  kolom.push({ key: "subtotal", label: "Subtotal", align: "right", render: (it) => <span className="font-semibold">{formatCurrency(it.subtotal != null ? it.subtotal : num(it.price) * num(it.quantity))}</span> });

  return (
    <div className="grid gap-3" data-testid="doc-preview-sales-order">
      <PreviewFacts items={[
        { key: "customer", label: "Pelanggan", content: doc.customer_name
          ? <CustomerCardLink id={doc.customer_id} name={doc.customer_name} perms={perms} testId="doc-preview-customer" /> : "" },
        { key: "sales", label: "Sales", content: doc.sales_name },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} testId="doc-preview-status" /> : "" },
        { key: "payment", label: "Pembayaran", content: doc.payment_status ? docStatusLabel(doc.payment_status) : "" },
        { key: "date", label: "Tanggal", content: doc.created_at ? formatDate(doc.created_at) : "" },
        { key: "booking", label: "Batas cadangan", content: doc.booking_until ? formatDateTime(doc.booking_until) : "" },
      ]} />
      <PreviewLines columns={kolom} rows={items} />
      <PreviewTotals rows={[
        { label: "Subtotal", value: doc.total_amount != null ? formatCurrency(doc.total_amount) : "" },
        { label: "Diskon", value: num(doc.discount_total) > 0 ? `− ${formatCurrency(doc.discount_total)}` : "" },
        { label: "PPN", value: num(doc.ppn_amount) > 0 ? formatCurrency(doc.ppn_amount) : "" },
        { label: "Total", value: formatCurrency(total), strong: true },
        { label: "Sudah dibayar", value: formatCurrency(dibayar) },
        { label: "Sisa", value: formatCurrency(Math.max(total - dibayar, 0)), strong: true },
      ]} />
    </div>
  );
}
