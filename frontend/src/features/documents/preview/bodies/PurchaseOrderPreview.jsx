/** Isi pratinjau PO: fakta, baris barang dengan status terima, total. Data dari `GET /purchase-orders/{id}` (sudah termuat). */
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate, formatQty } from "../../../../utils/formatters";
import { DocPill, SupplierCardLink } from "../../../finance/cards/partyCards";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

const num = (v) => Number(v) || 0;

const kolom = [
  { key: "product", label: "Barang", render: (it) => (
    <div>
      <span className="font-semibold">{it.product_name}</span>
      {it.sku && <span className="block text-fs-12 text-kn-text-2">{it.sku}</span>}
    </div>) },
  { key: "quantity", label: "Pesan", align: "right", render: (it) => `${formatQty(it.quantity)} ${it.unit || ""}`.trim() },
  { key: "received", label: "Diterima", align: "right", render: (it) => `${formatQty(it.received_qty || 0)} dari ${formatQty(it.quantity)}` },
  { key: "price", label: "Harga", align: "right", render: (it) => formatCurrency(it.price) },
  { key: "subtotal", label: "Subtotal", align: "right", render: (it) => <span className="font-semibold">{formatCurrency(it.line_total ?? it.subtotal ?? num(it.price) * num(it.quantity))}</span> },
];

export default function PurchaseOrderPreview({ doc, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const items = Array.isArray(doc.items) ? doc.items : [];
  const total = doc.grand_total != null ? doc.grand_total : doc.total_amount;
  return (
    <div className="grid gap-3" data-testid="doc-preview-purchase-order">
      <PreviewFacts items={[
        { key: "supplier", label: "Pemasok", content: doc.supplier_name
          ? <SupplierCardLink id={doc.supplier_id} name={doc.supplier_name} perms={perms} testId="doc-preview-supplier" /> : "" },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} testId="doc-preview-status" /> : "" },
        { key: "warehouse", label: "Gudang", content: doc.warehouse_name },
        { key: "eta", label: "Perkiraan tiba", content: doc.expected_delivery_date ? formatDate(doc.expected_delivery_date) : "" },
        { key: "due", label: "Jatuh tempo bayar", content: doc.payment_due_date ? formatDate(doc.payment_due_date) : "" },
      ]} />
      <PreviewLines columns={kolom} rows={items} />
      <PreviewTotals rows={[
        { label: "Subtotal", value: doc.total_amount != null ? formatCurrency(doc.total_amount) : "" },
        { label: "Diskon", value: num(doc.discount_total) > 0 ? `− ${formatCurrency(doc.discount_total)}` : "" },
        { label: "PPN", value: num(doc.ppn_amount) > 0 ? formatCurrency(doc.ppn_amount) : "" },
        { label: "Total", value: total != null ? formatCurrency(total) : "", strong: true },
      ]} />
    </div>
  );
}
