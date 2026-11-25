/**
 * deskRowActions — aksi di tempat Meja Admin Sales (Meja gelombang 2, Task 8), satu sumber untuk meja desktop & HP.
 * Server mengirim baris ber-`action_kind: "open"` (pindah layar); di sini aksinya DITUKAR menurut izin pengguna —
 * izin yang sama dengan pemeriksaan server (alamatnya di komentar tiap aksi). Tanpa izin → baris tak diubah (navigasi lama).
 *
 * Jenis aksi baru: `assign_sales` · `mark_reminded` · `reject_internal` (hanya lewat `_moreActions`) · `view` (pop-up saja).
 * Yang SENGAJA tetap pindah layar: `retur`, `retur_tukar` (proses retur bertahap: penerimaan barang, penyelesaian),
 * `od_*` (catat ACC / kunci harga / siapkan memakai formulir pesanan khusus bertahap), "Tindak" permintaan internal
 * (konversi ke transfer/PO bertahap).
 */
import { can } from "../../config/roles";
import { askReason } from "../../services/confirmService";
import { markReminded } from "../crm/collectionMark";
import { rejectInternalRequest } from "../internal_requests/internalRequestsApi";
import { inPlaceOf } from "./DeskQueueCard";

export const IN_PLACE_KINDS = ["assign_sales", "mark_reminded", "reject_internal"];
export const inPlaceAdminSales = inPlaceOf(IN_PLACE_KINDS);

const TOLAK = "Tolak";

function barisMeja(row, queueId, perms) {
  // `POST /customers/{id}/reassign` — `sales_force.assign` (backend/routers/crm.py:87).
  if (queueId === "pelanggan_tanpa_sales" && can(perms, "sales_force", "assign")) {
    return { ...row, action_kind: "assign_sales" };
  }
  // `POST /collection-reminders/mark` — `order.update`; baris yang sudah diingatkan (≤ 7 hari) tidak ditawarkan ulang.
  if (queueId === "jatuh_tempo" && row.customer_id && !row.reminded && can(perms, "order", "update")) {
    return { ...row, action: "Catat sudah diingatkan", action_kind: "mark_reminded" };
  }
  // `POST /internal-requests/{id}/reject` — `internal_request.reject` (backend/routers/internal_requests.py:165).
  // "Tindak" (konversi) tetap pindah layar; "Tolak" ikut sebagai aksi tambahan di pop-up.
  if (queueId === "permintaan_internal" && can(perms, "internal_request", "reject")) {
    return { ...row, _moreActions: [...(row._moreActions || []),
      { label: TOLAK, row: { ...row, action: TOLAK, action_kind: "reject_internal" } }] };
  }
  // "Lihat": hanya pratinjau (pop-up); mengubah harga = "Buka layar penuh".
  if (queueId === "menunggu_manajer" || queueId === "harga_ditolak") return { ...row, action_kind: "view" };
  return row;
}

/** Antrean server → antrean meja (baris ditukar aksinya menurut izin). */
export function adminSalesQueues(queues, perms) {
  return (Array.isArray(queues) ? queues : []).map((q) => ({
    ...q, rows: (Array.isArray(q.rows) ? q.rows : []).map((r) => barisMeja(r, q.id, perms)),
  }));
}

/** "Catat sudah diingatkan": satu jalur dengan Reminder Penagihan & Meja Keuangan. Galat dilempar. Mengembalikan pesan sukses. */
export async function catatDiingatkan(row) {
  await markReminded({ customer_id: row.customer_id, order_id: row.order_id || row.ref_id, order_number: row.number });
  return `${row.title} ditandai sudah diingatkan.`;
}

/**
 * "Tolak" permintaan internal: alasan wajib (min. 5 huruf — aturan server) lewat `askReason`, teks sama dengan layar
 * asal (`InternalRequestsView`). Batal → null (tanpa panggilan); sukses → pesan; galat dilempar.
 */
export async function tolakPermintaanInternal(row) {
  const alasan = await askReason({
    title: `Tolak ${row.number}?`, danger: true, confirmLabel: "Tolak Permintaan", reasonLabel: "Alasan penolakan",
    message: "Alasan penolakan dikirim ke peminta — tulis langkah berikutnya yang jelas (beli ke pemasok? tunggu? ubah jumlah?).",
    reasonPlaceholder: "mis. stok Kanda dipakai pesanan sendiri — ajukan PR ke pemasok",
  });
  if (alasan === null) return null;
  await rejectInternalRequest(row.ref_id, alasan);
  return `${row.number} ditolak.`;
}
