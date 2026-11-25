/**
 * Isi pratinjau kwitansi: fakta + alokasi ke pesanan. Data dari `GET /ar-receipts/{id}` (sudah termuat).
 * Alokasi dengan `order_id` dan izin baca pesanan = tombol yang menumpuk pratinjau pesanan; selain itu teks biasa.
 */
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate } from "../../../../utils/formatters";
import { CustomerCardLink, DocPill } from "../../../finance/cards/partyCards";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

export default function ArReceiptPreview({ doc, push, canPush, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const alokasi = (Array.isArray(doc.allocations) ? doc.allocations : []).map((a, i) => ({ ...a, idx: i }));
  const bisaBuka = canPush("sales_order");

  const kolom = [
    { key: "order", label: "Pesanan", render: (a) => {
      const nomor = a.order_number || "—";
      if (!a.order_id || !bisaBuka) return <span data-testid={`doc-preview-alloc-${a.idx}-text`}>{nomor}</span>;
      return (
        <button type="button" className="link-button text-left" data-testid={`doc-preview-alloc-${a.idx}`}
          title="Lihat ringkasan pesanan"
          onClick={() => push({ docType: "sales_order", docId: a.order_id, number: a.order_number, ...(doc.entity_id ? { entityId: doc.entity_id } : {}) })}>
          {nomor}
        </button>);
    } },
    { key: "applied", label: "Dialokasikan", align: "right", render: (a) => <span className="font-semibold">{formatCurrency(a.applied)}</span> },
  ];

  return (
    <div className="grid gap-3" data-testid="doc-preview-ar-receipt">
      <PreviewFacts items={[
        { key: "customer", label: "Pelanggan", content: doc.customer_name
          ? <CustomerCardLink id={doc.customer_id} name={doc.customer_name} perms={perms} testId="doc-preview-customer" /> : "" },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} testId="doc-preview-status" /> : "" },
        { key: "date", label: "Tanggal", content: doc.receipt_date ? formatDate(doc.receipt_date) : "" },
        { key: "method", label: "Metode", content: doc.method || doc.payment_method_code },
        { key: "reference", label: "Referensi", content: doc.reference_no },
      ]} />
      <PreviewLines columns={kolom} rows={alokasi} empty="Belum dialokasikan ke pesanan." />
      <PreviewTotals rows={[{ label: "Jumlah kwitansi", value: doc.amount != null ? formatCurrency(doc.amount) : "", strong: true }]} />
    </div>
  );
}
