/**
 * docPreviewRegistry (Meja gelombang 2) — daftar jenis dokumen yang punya pratinjau pop-up.
 *
 * Satu entri per `docType`:
 *   · `label` — nama jenis untuk judul pop-up;
 *   · `perm`  — [resource, action] izin baca (`can(perms, ...perm)`); tanpa izin `DocLink` hanya teks;
 *   · `load(id, { entityId })` — memuat dokumen lewat endpoint baca yang sudah ada. Bila `entityId` (PT dokumen, mode
 *     "Semua PT") diberikan, PT itu diingat di `docEntityRegistry`; interseptor `apiClient` lalu mengirim `X-Entity-Id`
 *     PT dokumen HANYA bila PT itu ada di penugasan akun, dan server tetap memeriksa;
 *   · `Body`  — komponen isi `{ doc, push(target), canPush(docType), currentUser }`; `push` mengabaikan jenis tanpa izin,
 *     `canPush(docType)` dipakai Body untuk memilih tombol (`canPush` benar) atau teks biasa; dipakai di `DocPreviewModal` maupun mandiri
 *     (mis. di pop-up meja — `push` boleh no-op);
 *   · `full(doc)` — tautan navigasi untuk "Buka layar penuh" (`null` = tombol tidak ditampilkan).
 */
import { can } from "../../../config/roles";
import { ROW_TARGET } from "../../sales_admin/workDeskApi";
import {
  loadDoc, loadSalesOrder, loadVendorBill, loadPurchaseOrder, loadArReceipt, loadContraBon,
  loadSalesReturn, loadSpecialOrder, loadInternalRequest,
} from "./docLoaders";
import SalesOrderPreview from "./bodies/SalesOrderPreview";
import VendorBillPreview from "./bodies/VendorBillPreview";
import PurchaseOrderPreview from "./bodies/PurchaseOrderPreview";
import ArReceiptPreview from "./bodies/ArReceiptPreview";
import ContraBonPreview from "./bodies/ContraBonPreview";
import SalesReturnPreview from "./bodies/SalesReturnPreview";
import SpecialOrderPreview from "./bodies/SpecialOrderPreview";
import InternalRequestPreview from "./bodies/InternalRequestPreview";

// Pemuat tinggal di `docLoaders.js` (bebas siklus); `loadDoc` tetap diekspor dari sini untuk pemakai lama.
export { loadDoc };

export const DOC_PREVIEWS = {
  sales_order: {
    label: "Pesanan penjualan",
    perm: ["order", "view"],
    load: loadSalesOrder,
    Body: SalesOrderPreview,
    full: (doc) => ({ ...ROW_TARGET.sales_order, focus_id: doc.id, number: doc.number }),
  },
  // Tagihan pemasok, kwitansi, kontrabon: belum ada tujuan navigasi baku di `ROW_TARGET`/`waitingBoards` → tanpa "Buka layar penuh".
  vendor_bill: {
    label: "Tagihan pemasok",
    perm: ["vendor_bill", "view"],
    load: loadVendorBill,
    Body: VendorBillPreview,
    full: () => null,
  },
  purchase_order: {
    label: "Purchase order",
    perm: ["purchase_order", "view"],
    load: loadPurchaseOrder,
    Body: PurchaseOrderPreview,
    full: (doc) => ({ ...ROW_TARGET.purchase_order, focus_id: doc.id, number: doc.number }),
  },
  ar_receipt: {
    label: "Kwitansi",
    perm: ["ar_receipt", "view"],
    load: loadArReceipt,
    Body: ArReceiptPreview,
    full: () => null,
  },
  contra_bon: {
    label: "Kontrabon",
    perm: ["contra_bon", "view"],
    load: loadContraBon,
    Body: ContraBonPreview,
    full: () => null,
  },
  // Retur, pesanan khusus, permintaan internal: `full` memakai `ROW_TARGET` (sama dengan baris meja).
  sales_return: {
    label: "Retur penjualan",
    perm: ["sales_return", "view"],
    load: loadSalesReturn,
    Body: SalesReturnPreview,
    full: (doc) => ({ ...ROW_TARGET.sales_return, focus_id: doc.id, number: doc.number }),
  },
  // Rute `GET /special-orders/{id}` memeriksa izin `order.view` (tidak ada sumber daya `special_order`).
  special_order: {
    label: "Pesanan khusus",
    perm: ["order", "view"],
    load: loadSpecialOrder,
    Body: SpecialOrderPreview,
    full: (doc) => ({ ...ROW_TARGET.special_order, focus_id: doc.id, number: doc.number }),
  },
  internal_request: {
    label: "Permintaan internal",
    perm: ["internal_request", "view"],
    load: loadInternalRequest,
    Body: InternalRequestPreview,
    full: (doc) => ({ ...ROW_TARGET.internal_request, focus_id: doc.id, number: doc.number }),
  },
};

export const previewFor = (docType) => (docType && Object.prototype.hasOwnProperty.call(DOC_PREVIEWS, docType) ? DOC_PREVIEWS[docType] : null);

export const canPreview = (perms, docType) => {
  const entry = previewFor(docType);
  return !!entry && can(perms, ...entry.perm);
};
