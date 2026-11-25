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
import axios, { API } from "../../../services/apiClient";
import { rememberDocEntities } from "../../../services/docEntityRegistry";
import { can } from "../../../config/roles";
import { ROW_TARGET } from "../../sales_admin/workDeskApi";
import SalesOrderPreview from "./bodies/SalesOrderPreview";
import VendorBillPreview from "./bodies/VendorBillPreview";
import PurchaseOrderPreview from "./bodies/PurchaseOrderPreview";
import ArReceiptPreview from "./bodies/ArReceiptPreview";
import ContraBonPreview from "./bodies/ContraBonPreview";

/** Pemuat standar: GET `${API}${path}/{id}` dengan PT dokumen diingat lebih dulu. */
export const loadDoc = (path) => async (id, { entityId } = {}) => {
  if (entityId) rememberDocEntities([{ id, entity_id: entityId }]);
  const res = await axios.get(`${API}${path}/${id}`);
  return res.data;
};

/** Dokumen pembelian/kas memakai nama kolom nomor sendiri (`bill_number`, `po_number`); judul pop-up membaca `number`. */
const loadBernomor = (path, field) => {
  const muat = loadDoc(path);
  return async (id, opts) => {
    const d = await muat(id, opts);
    return d && !d.number && d[field] ? { ...d, number: d[field] } : d;
  };
};

export const DOC_PREVIEWS = {
  sales_order: {
    label: "Pesanan penjualan",
    perm: ["order", "view"],
    load: loadDoc("/sales-orders"),
    Body: SalesOrderPreview,
    full: (doc) => ({ ...ROW_TARGET.sales_order, focus_id: doc.id, number: doc.number }),
  },
  // Tagihan pemasok, kwitansi, kontrabon: belum ada tujuan navigasi baku di `ROW_TARGET`/`waitingBoards` → tanpa "Buka layar penuh".
  vendor_bill: {
    label: "Tagihan pemasok",
    perm: ["vendor_bill", "view"],
    load: loadBernomor("/vendor-bills", "bill_number"),
    Body: VendorBillPreview,
    full: () => null,
  },
  purchase_order: {
    label: "Purchase order",
    perm: ["purchase_order", "view"],
    load: loadBernomor("/purchase-orders", "po_number"),
    Body: PurchaseOrderPreview,
    full: (doc) => ({ ...ROW_TARGET.purchase_order, focus_id: doc.id, number: doc.number }),
  },
  ar_receipt: {
    label: "Kwitansi",
    perm: ["ar_receipt", "view"],
    load: loadDoc("/ar-receipts"),
    Body: ArReceiptPreview,
    full: () => null,
  },
  contra_bon: {
    label: "Kontrabon",
    perm: ["contra_bon", "view"],
    load: loadDoc("/contra-bons"),
    Body: ContraBonPreview,
    full: () => null,
  },
};

export const previewFor = (docType) => (docType && Object.prototype.hasOwnProperty.call(DOC_PREVIEWS, docType) ? DOC_PREVIEWS[docType] : null);

export const canPreview = (perms, docType) => {
  const entry = previewFor(docType);
  return !!entry && can(perms, ...entry.perm);
};
