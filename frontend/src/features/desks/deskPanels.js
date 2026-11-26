// Registri panel rincian baris meja (Meja gelombang 2).
//
// Kunci pencarian, berurutan: `queue:<id antrean asal baris>` (`row._queue` — kelompok Meja Keuangan memakai id kelompok
// sebagai `queue.id`, mis. "denda" untuk antrean "denda_draft"), `queue:<queue.id>`, lalu `<ref_type>`.
// Kontrak props panel: { row, queue, currentUser, testPrefix, pt, onAction(row, queue), onClose(), onOpenFull(row, queue) }.
//
// `DESK_DOC_OF` = satu tabel pemetaan kunci → dokumen yang dipratinjau (`docType`, `docId` dari baris). Kunci `customer`
// SENGAJA tidak dipetakan (dua arti: pelanggan tanpa sales vs uang masuk) — antrean `pelanggan_tanpa_sales` punya
// `CustomerQueuePanel` sendiri (Tugas 8). `queue:lapor_bayar` (LB-T8) memakai `PayReportQueuePanel`: laporan + pratinjau pesanan.
import CustomerQueuePanel from "./CustomerQueuePanel";
import DeskDocPanel from "./DeskDocPanel";
import PayReportQueuePanel from "./PayReportQueuePanel";

const dari = (docType, kunci) => (row) => ({ docType, docId: row?.[kunci] });

export const DESK_DOC_OF = {
  sales_order: dari("sales_order", "ref_id"),
  "queue:uang_masuk": dari("sales_order", "order_id"),          // baris ber-ref_type customer; dokumen = order_id
  "queue:bayar_sebelum_kirim": dari("sales_order", "order_id"),
  "queue:lapor_bayar": dari("sales_order", "order_id"),          // LB-T8 — baris ber-ref_type payment_report; dokumen = pesanan laporan
  "queue:selisih_bayar": dari("ar_receipt", "ref_id"),
  "queue:denda_draft": (row) => (row?.doc_type === "sales_order" ? { docType: "sales_order", docId: row.doc_id } : null),
  vendor_bill: dari("vendor_bill", "ref_id"),                 // baris papan `vendor_bill`: ref_id = id tagihan
  purchase_order: dari("purchase_order", "ref_id"),
  sales_return: dari("sales_return", "ref_id"),
  special_order: dari("special_order", "ref_id"),
  internal_request: dari("internal_request", "ref_id"),
  // Papan kontrabon (`GET /api/home/finance`): `ref_id` = `r.id` baris papan = id kontrabon.
  contra_bon_verify: dari("contra_bon", "ref_id"),
  contra_bon_approve: dari("contra_bon", "ref_id"),
  contra_bon_dispute: dari("contra_bon", "ref_id"),
};

/** Panel kunci terpetakan: menentukan dokumen dari `DESK_DOC_OF`, lalu menyerahkannya ke `DeskDocPanel`. */
function MappedDocPanel(props) {
  const d = docOfRow(props.row, props.queue);
  return <DeskDocPanel {...props} docType={d?.docType || ""} docId={d?.docId || ""} />;
}

/** Panel per kunci: setiap kunci terpetakan memakai `MappedDocPanel`; jenis lain dapat diisi gelombang berikut. */
export const DESK_PANELS = {
  ...Object.fromEntries(Object.keys(DESK_DOC_OF).map((k) => [k, MappedDocPanel])),
  "queue:pelanggan_tanpa_sales": CustomerQueuePanel,
  "queue:lapor_bayar": PayReportQueuePanel,                    // LB-T8 — laporan + bukti + pratinjau pesanan + Terima/Tolak di tempat
};

const kunciCari = (row, queue) => [
  row?._queue ? `queue:${row._queue}` : "", queue?.id ? `queue:${queue.id}` : "", row?.ref_type || "",
].filter(Boolean);

const punya = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

/** Kunci registri pertama yang punya panel, atau "". */
export function panelKey(row, queue) {
  return kunciCari(row, queue).find((k) => punya(DESK_PANELS, k)) || "";
}

/** `panelFor(row, queue)`; bentuk lama `panelFor(refType)` (string) tetap berlaku. */
export function panelFor(row, queue) {
  if (typeof row === "string") return (row && punya(DESK_PANELS, row) && DESK_PANELS[row]) || null;
  const k = panelKey(row, queue);
  return k ? DESK_PANELS[k] : null;
}

/** Dokumen yang dipratinjau untuk baris ini: `{ docType, docId }` atau null (panel umum). */
export function docOfRow(row, queue) {
  for (const k of kunciCari(row, queue)) {
    if (!punya(DESK_DOC_OF, k)) continue;
    const d = DESK_DOC_OF[k](row);
    return d && d.docType && d.docId ? d : null;
  }
  return null;
}
