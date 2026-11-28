/**
 * docLoaders (Meja gelombang 2) — pemuat dokumen untuk pratinjau, TANPA mengimpor isi (`bodies/*`) maupun registri.
 * Registri dan isi pratinjau yang perlu memuat dokumen lain (mis. kontrabon → faktur) sama-sama mengimpor modul ini,
 * sehingga urutan impor tidak lagi berpengaruh (tidak ada siklus registri ↔ isi).
 */
import axios, { API } from "../../../services/apiClient";
import { rememberDocEntities } from "../../../services/docEntityRegistry";

/** Pemuat standar: GET `${API}${path}/{id}` dengan PT dokumen diingat lebih dulu. */
export const loadDoc = (path) => async (id, { entityId } = {}) => {
  if (entityId) rememberDocEntities([{ id, entity_id: entityId }]);
  const res = await axios.get(`${API}${path}/${id}`);
  return res.data;
};

/** Dokumen pembelian/kas memakai nama kolom nomor sendiri (`bill_number`, `po_number`); judul pop-up membaca `number`. */
export const loadBernomor = (path, field) => {
  const muat = loadDoc(path);
  return async (id, opts) => {
    const d = await muat(id, opts);
    return d && !d.number && d[field] ? { ...d, number: d[field] } : d;
  };
};

export const loadSalesOrder = loadDoc("/sales-orders");
export const loadVendorBill = loadBernomor("/vendor-bills", "bill_number");
export const loadPurchaseOrder = loadBernomor("/purchase-orders", "po_number");
export const loadArReceipt = loadDoc("/ar-receipts");
export const loadContraBon = loadDoc("/contra-bons");
export const loadSalesReturn = loadDoc("/sales-returns");
export const loadSpecialOrder = loadDoc("/special-orders");
export const loadInternalRequest = loadDoc("/internal-requests");
// Kas & Bank bagian 1 (Tugas 6) — Pindah Dana: dokumen + kas-kasnya + penilaian kontrol untuk pembuka.
export const loadFundTransfer = loadDoc("/fund-transfers");
// Kas & Bank bagian 2 (Tugas 4) — pengajuan kas keluar manual: pengajuan + kas yang terbit + penilaian kontrol pembuka.
export const loadCashOutRequest = loadDoc("/cash-out-requests");
// Kas & Bank bagian 3 (Tugas 4b) — opname kas: opname + kas penyesuaian + penilaian kontrol pembuka.
export const loadCashCount = loadDoc("/cash-counts");
