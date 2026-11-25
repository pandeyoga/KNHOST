/**
 * Isi pratinjau retur penjualan: fakta (jenis, status, pesanan asal, alasan/catatan utuh) dan tabel barang
 * (jumlah, kondisi, alasan per baris). Data dari `GET /sales-returns/{id}` (sudah termuat).
 * Pesanan asal (`order_id`) + izin baca pesanan = tombol yang menumpuk pratinjau pesanan; selain itu teks biasa.
 * Label jenis/status/kondisi memakai kamus layar asalnya (`ReturnShared`, `ReturnRollsPanel`), bukan salinan.
 */
import { useEntityScope } from "../../../../context/EntityScopeContext";
import QtyDual from "../../../../components/QtyDual";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate } from "../../../../utils/formatters";
import { docStatusLabel } from "../../../../utils/docStatus";
import { CustomerCardLink, DocPill } from "../../../finance/cards/partyCards";
import { RETURN_TYPE_LABEL, STATUS_STYLE as RETURN_STATUS_STYLE, OUTCOME_LABEL } from "../../../sales/ReturnShared";
import { COND_LABEL } from "../../../sales/ReturnRollsPanel";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

export default function SalesReturnPreview({ doc, push, canPush, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const items = Array.isArray(doc.items) ? doc.items : [];
  const bisaBuka = canPush("sales_order") && !!doc.order_id;
  const nomorPesanan = doc.order_number || "";
  const labelStatus = (RETURN_STATUS_STYLE[doc.status] || {}).label || docStatusLabel(doc.status);
  const nilai = items.reduce((a, it) => a + (Number(it.line_total_est) || 0), 0);

  const kolom = [
    { key: "product", label: "Barang", render: (it) => (
      <div>
        <span className="font-semibold">{it.product_name}</span>
        {it.sku && <span className="block text-fs-12 text-kn-text-2">{it.sku}</span>}
      </div>) },
    { key: "quantity", label: "Jumlah", align: "right", render: (it) => <QtyDual rolls={it.qty_rolls} measure={it.quantity_returned} unit={it.unit} /> },
    { key: "condition", label: "Kondisi", render: (it) => (it.condition ? (COND_LABEL[it.condition] || [])[1] || it.condition : "") },
    { key: "reason", label: "Alasan", render: (it) => it.reason || "" },
  ];

  return (
    <div className="grid gap-3" data-testid="doc-preview-sales-return">
      <PreviewFacts items={[
        { key: "type", label: "Jenis", content: doc.return_type ? RETURN_TYPE_LABEL[doc.return_type] || doc.return_type : "" },
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} label={labelStatus} testId="doc-preview-status" /> : "" },
        { key: "outcome", label: "Penyelesaian", content: doc.outcome ? OUTCOME_LABEL[doc.outcome] || doc.outcome : "" },
        { key: "customer", label: "Pelanggan", content: doc.customer_name
          ? <CustomerCardLink id={doc.customer_id} name={doc.customer_name} perms={perms} testId="doc-preview-customer" /> : "" },
        { key: "order", label: "Pesanan asal", content: !nomorPesanan ? "" : bisaBuka ? (
          <button type="button" className="link-button text-left" data-testid="doc-preview-return-order" title="Lihat ringkasan pesanan"
            onClick={() => push({ docType: "sales_order", docId: doc.order_id, number: doc.order_number, ...(doc.entity_id ? { entityId: doc.entity_id } : {}) })}>
            {nomorPesanan}
          </button>) : nomorPesanan },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "date", label: "Dibuat", content: doc.created_at ? formatDate(doc.created_at) : "" },
        { key: "by", label: "Oleh", content: doc.created_by },
        { key: "reason", label: "Alasan", content: doc.reason },
        { key: "notes", label: "Catatan", content: doc.notes },
        { key: "reject", label: "Alasan ditolak", content: doc.reject_reason },
        { key: "reversal", label: "Alasan pembalikan", content: doc.reversal_reason },
      ]} />
      <PreviewLines columns={kolom} rows={items} />
      <PreviewTotals rows={[{ label: "Taksiran nilai", value: nilai > 0 ? formatCurrency(nilai) : "", strong: true }]} />
    </div>
  );
}
