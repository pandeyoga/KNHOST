/** Isi pratinjau tagihan pemasok: fakta, baris barang, total. Data dari `GET /vendor-bills/{id}` (sudah termuat). */
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate, formatQty } from "../../../../utils/formatters";
import { DocPill, SupplierCardLink } from "../../../finance/cards/partyCards";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

const num = (v) => Number(v) || 0;

/** Kolom baris barang tagihan; dipakai juga oleh pratinjau kontrabon (gabungan baris faktur). */
export const kolomBarangTagihan = [
  { key: "product", label: "Barang", render: (it) => (
    <div>
      <span className="font-semibold">{it.product_name}</span>
      {it.sku && <span className="block text-fs-12 text-kn-text-2">{it.sku}</span>}
    </div>) },
  { key: "billed_qty", label: "Ditagih", align: "right", render: (it) => formatQty(it.billed_qty) },
  { key: "price", label: "Harga", align: "right", render: (it) => formatCurrency(it.price) },
  { key: "line_total", label: "Subtotal", align: "right", render: (it) => <span className="font-semibold">{formatCurrency(it.line_total ?? it.subtotal ?? num(it.price) * num(it.billed_qty))}</span> },
];

export default function VendorBillPreview({ doc, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const items = Array.isArray(doc.items) ? doc.items : [];
  const fin = doc.financials || {};
  return (
    <div className="grid gap-3" data-testid="doc-preview-vendor-bill">
      <PreviewFacts items={[
        { key: "supplier", label: "Pemasok", content: doc.supplier_name
          ? <SupplierCardLink id={doc.supplier_id} name={doc.supplier_name} perms={perms} testId="doc-preview-supplier" /> : "" },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} testId="doc-preview-status" /> : "" },
        { key: "po", label: "PO", content: doc.po_number },
        { key: "invoice", label: "Faktur pemasok", content: doc.supplier_invoice_no },
        { key: "due", label: "Jatuh tempo", content: doc.due_date ? formatDate(doc.due_date) : "" },
      ]} />
      <PreviewLines columns={kolomBarangTagihan} rows={items} />
      <PreviewTotals rows={[
        { label: "PPN", value: num(doc.ppn_amount) > 0 ? formatCurrency(doc.ppn_amount) : "" },
        { label: "Total", value: doc.grand_total != null ? formatCurrency(doc.grand_total) : "", strong: true },
        { label: "Sudah dibayar", value: fin.amount_paid != null ? formatCurrency(fin.amount_paid) : "" },
        { label: "Sisa", value: fin.outstanding != null ? formatCurrency(fin.outstanding) : "", strong: true },
      ]} />
    </div>
  );
}
