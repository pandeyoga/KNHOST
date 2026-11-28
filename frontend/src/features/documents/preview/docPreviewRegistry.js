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
  loadSalesReturn, loadSpecialOrder, loadInternalRequest, loadFundTransfer, loadCashOutRequest,
  loadCashCount,
} from "./docLoaders";
import SalesOrderPreview from "./bodies/SalesOrderPreview";
import VendorBillPreview from "./bodies/VendorBillPreview";
import PurchaseOrderPreview from "./bodies/PurchaseOrderPreview";
import ArReceiptPreview from "./bodies/ArReceiptPreview";
import ContraBonPreview from "./bodies/ContraBonPreview";
import SalesReturnPreview from "./bodies/SalesReturnPreview";
import SpecialOrderPreview from "./bodies/SpecialOrderPreview";
import InternalRequestPreview from "./bodies/InternalRequestPreview";
import FundTransferPreview from "./bodies/FundTransferPreview";
import CashOutRequestPreview from "./bodies/CashOutRequestPreview";
import CashCountPreview from "./bodies/CashCountPreview";

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
  // Kas & Bank bagian 1 (Tugas 6) — Pindah Dana (`GET /fund-transfers/{id}` = `cash.view`); label sama dengan
  // `cash_ledger.REF_LABEL["fund_transfer"]`. Layar penuh = Kas & Bank › Pindah Dana (aksi Setujui / Terima / Batal).
  fund_transfer: {
    label: "Pindah Dana",
    perm: ["cash", "view"],
    load: loadFundTransfer,
    Body: FundTransferPreview,
    full: (doc) => ({ view: "fund-transfers", nav_id: "cash-bank", focus_type: "fund_transfer", focus_id: doc.id,
      number: doc.number }),
  },
  // Kas & Bank bagian 2 (Tugas 4) — pengajuan kas keluar manual di atas batas (`GET /cash-out-requests/{id}` = `cash.view`).
  // Layar penuh: pengajuan menunggu → Transaksi Kas bagian "Menunggu persetujuan" (baris disorot; aksi Setujui / Tolak /
  // Batal di sana); disetujui → baris kas yang terbit di Transaksi Kas; ditolak/dibatalkan → tanpa tombol (tidak ada kerja).
  cash_out_request: {
    label: "Pengajuan kas keluar",
    perm: ["cash", "view"],
    load: loadCashOutRequest,
    Body: CashOutRequestPreview,
    full: (doc) => {
      if (doc.status === "disetujui" && doc.cash_id) {
        return { view: "cash-management", nav_id: "cash-bank", focus_type: "cash_transaction", focus_id: doc.cash_id,
          number: doc.cash_number || "" };
      }
      if (doc.status === "menunggu_persetujuan") {
        return { view: "cash-management", nav_id: "cash-bank", preset: { status: "menunggu_persetujuan", sorot: doc.id } };
      }
      return null;
    },
  },
  // Kas & Bank bagian 3 (Tugas 4b) — opname kas `OPK-` (`GET /cash-counts/{id}` = `cash.view`); label sama dengan
  // `cash_ledger.REF_LABEL["cash_count"]`. Layar penuh = Kas & Bank › Opname Kas (tab tersembunyi; aksi Setujui / Tolak):
  // menunggu → saringan "Menunggu persetujuan"; selain itu → riwayat opname rekening itu; barisnya disorot.
  cash_count: {
    label: "Opname kas",
    perm: ["cash", "view"],
    load: loadCashCount,
    Body: CashCountPreview,
    full: (doc) => ({ view: "cash-counts", nav_id: "cash-bank", preset: doc.status === "menunggu_persetujuan"
      ? { status: "menunggu_persetujuan", sorot: doc.id }
      : { status: "", account_id: doc.account_id || "", sorot: doc.id } }),
  },
};

export const previewFor = (docType) => (docType && Object.prototype.hasOwnProperty.call(DOC_PREVIEWS, docType) ? DOC_PREVIEWS[docType] : null);

export const canPreview = (perms, docType) => {
  const entry = previewFor(docType);
  return !!entry && can(perms, ...entry.perm);
};
