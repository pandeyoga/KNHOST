/**
 * OrderPrintModal — pop-up "Cetak dokumen" sebuah pesanan (Meja Admin Sales, baris "Siap cetak").
 * Isinya panel cetak yang sama dengan rincian pesanan; izin cetak diperiksa di dalam `RelatedDocsPanel`.
 */
import DetailModal from "../../components/DetailModal";
import RelatedDocsPanel from "./RelatedDocsPanel";
import { ORDER_PRINT_DOCS } from "./orderPrintDocs";

export default function OrderPrintModal({ order, currentUser, onClose }) {
  if (!order) return null;
  return (
    <DetailModal open onClose={onClose} framed size="md" label={`Cetak dokumen ${order.number || ""}`.trim()} testId="order-print">
      <div className="grid gap-3">
        <h2 data-testid="order-print-title" className="text-fs-16 font-semibold text-kn-text">
          {`Cetak dokumen · ${order.number}`}
        </h2>
        {order.title ? <p className="text-fs-13 text-kn-text-2">{order.title}</p> : null}
        <RelatedDocsPanel title="Cetak Dokumen · Gudang & Penagihan" docs={ORDER_PRINT_DOCS}
          sourceId={order.id} entityId={order.entity_id} number={order.number} currentUser={currentUser} />
      </div>
    </DetailModal>
  );
}
