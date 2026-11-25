/**
 * Isi pratinjau permintaan internal (PIN antar-PT): fakta (peminta, alasan utuh, PT sumber, pesanan terkait, keputusan)
 * dan tabel barang yang diminta. Data dari `GET /internal-requests/{id}` (sudah termuat).
 * Label status memakai `PIN_STATUS_LABEL` milik layar asalnya.
 */
import { useEntityScope } from "../../../../context/EntityScopeContext";
import QtyDual from "../../../../components/QtyDual";
import { actorLabel } from "../../../../utils/actorLabel";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate } from "../../../../utils/formatters";
import { DocPill } from "../../../finance/cards/partyCards";
import { PIN_STATUS_LABEL } from "../../../internal_requests/internalRequestsApi";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

export default function InternalRequestPreview({ doc }) {
  const { entities } = useEntityScope();
  const items = Array.isArray(doc.items) ? doc.items : [];
  const peminta = [doc.requested_by ? actorLabel(doc.requested_by) : "", doc.requester_entity_name ? `(${doc.requester_entity_name})` : ""].filter(Boolean).join(" ");

  const kolom = [
    { key: "product", label: "Barang", render: (it) => (
      <div>
        <span className="font-semibold">{it.product_name}</span>
        {(it.sku || it.notes) && <span className="block text-fs-12 text-kn-text-2">{[it.sku, it.notes].filter(Boolean).join(" · ")}</span>}
      </div>) },
    { key: "quantity", label: "Diminta", align: "right", render: (it) => <QtyDual rolls={it.qty_rolls} measure={it.quantity} unit={it.unit} /> },
    { key: "est", label: "Taksiran", align: "right", render: (it) => (it.est_value != null ? `≈ ${formatCurrency(it.est_value)}` : "") },
  ];

  return (
    <div className="grid gap-3" data-testid="doc-preview-internal-request">
      <PreviewFacts items={[
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} label={PIN_STATUS_LABEL[doc.status]} testId="doc-preview-status" /> : "" },
        { key: "requester", label: "Peminta", content: peminta },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "source", label: "PT sumber", content: doc.source_entity_name },
        { key: "reason", label: "Alasan", content: doc.reason },
        { key: "needed", label: "Dibutuhkan sebelum", content: doc.needed_date ? formatDate(doc.needed_date) : "" },
        { key: "order", label: "Untuk pesanan", content: doc.source_order_number },
        { key: "interco", label: "Transaksi antar-PT", content: doc.interco_number_buyer ? `${doc.interco_number_buyer} ⇄ ${doc.interco_number_seller || ""}`.trim() : "" },
        { key: "decision", label: "Alasan keputusan", content: doc.decision_reason },
      ]} />
      <PreviewLines columns={kolom} rows={items} empty="Belum ada barang." />
      <PreviewTotals rows={[{ label: "Taksiran nilai", value: doc.est_value != null ? formatCurrency(doc.est_value) : "", strong: true }]} />
    </div>
  );
}
