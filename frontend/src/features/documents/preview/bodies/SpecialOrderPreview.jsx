/**
 * Isi pratinjau pesanan khusus (OD): fakta, judul, catatan utuh, tabel item (item batal tidak ikut), nilai pesanan.
 * Data dari `GET /special-orders/{id}` (sudah termuat). Label status mengikuti kamus layar asalnya (`SpecialOrderShared`):
 * status "confirmed" memakai label fase bila fase lebih rinci. Dokumen lama tanpa `items[]` memakai `custom_item`.
 */
import { useEntityScope } from "../../../../context/EntityScopeContext";
import { entityShortById } from "../../../../utils/entityLabel";
import { formatCurrency, formatDate, formatDateTime, formatQty } from "../../../../utils/formatters";
import { CustomerCardLink, DocPill } from "../../../finance/cards/partyCards";
import { STATUS_STYLE, PHASE_LABEL, odPhaseOf, docStatus } from "../../../sales/SpecialOrderShared";
import { PreviewFacts, PreviewLines, PreviewTotals } from "../previewParts";

const num = (v) => Number(v) || 0;

const labelStatus = (doc) => (doc.status === "confirmed" && PHASE_LABEL[odPhaseOf(doc)]) || (STATUS_STYLE[doc.status] || {}).label || docStatus(doc.status);

export default function SpecialOrderPreview({ doc, currentUser }) {
  const { entities } = useEntityScope();
  const perms = currentUser?.permissions;
  const dariItems = (Array.isArray(doc.items) ? doc.items : []).filter((i) => i.status !== "cancelled");
  const ci = doc.custom_item || {};
  const items = dariItems.length || !ci.description ? dariItems : [{ ...ci, id: "custom" }];

  const kolom = [
    { key: "description", label: "Item", render: (it) => (
      <div>
        <span className="font-semibold">{it.description || "—"}</span>
        {it.notes && <span className="block text-fs-12 text-kn-text-2">{it.notes}</span>}
      </div>) },
    { key: "quantity", label: "Jumlah", align: "right", render: (it) => `${formatQty(it.quantity)} ${it.unit || "meter"}`.trim() },
    { key: "target", label: "Harga target", align: "right", render: (it) => (num(it.target_price) > 0 ? formatCurrency(it.target_price) : "") },
  ];

  return (
    <div className="grid gap-3" data-testid="doc-preview-special-order">
      <PreviewFacts items={[
        { key: "title", label: "Judul", content: doc.title || ci.description },
        { key: "customer", label: "Pelanggan", content: doc.customer_name
          ? <CustomerCardLink id={doc.customer_id} name={doc.customer_name} perms={perms} testId="doc-preview-customer" /> : "" },
        { key: "status", label: "Status", content: doc.status ? <DocPill status={doc.status} label={labelStatus(doc)} testId="doc-preview-status" /> : "" },
        { key: "origin", label: "Asal", content: doc.origin === "redesign" ? "Redesign" : "" },
        { key: "entity", label: "PT", content: doc.entity_id ? entityShortById(entities, doc.entity_id, "") : "" },
        { key: "date", label: "Dibuat", content: doc.created_at ? formatDateTime(doc.created_at) : "" },
        { key: "by", label: "Oleh", content: doc.created_by_name || doc.created_by },
        { key: "eta", label: "Tenggat kirim", content: doc.expected_delivery ? formatDate(doc.expected_delivery) : "" },
        { key: "notes", label: "Catatan", content: doc.notes },
        { key: "reject", label: "Alasan ditolak", content: doc.reject_reason },
      ]} />
      <PreviewLines columns={kolom} rows={items} empty="Belum ada item." />
      <PreviewTotals rows={[{ label: "Nilai pesanan", value: doc.total_amount != null ? formatCurrency(doc.total_amount) : "", strong: true }]} />
    </div>
  );
}
