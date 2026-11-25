/**
 * customerReassign — satu jalur "Pindahkan / tetapkan sales penanggung jawab" (`POST /customers/{id}/reassign`,
 * izin `sales_force.assign`). Dipakai kartu pelanggan (`ReassignModal`) dan Meja Admin Sales (`AssignSalesDialog`,
 * Meja gelombang 2 Task 8) — teks & pilihan sales tujuan satu sumber.
 */
import axios, { API } from "../../services/apiClient";

export const TEKS_PILIH_SALES = "Pilih sales tujuan.";
export const TEKS_GAGAL_PINDAH = "Gagal memindahkan pelanggan.";
export const TEKS_BERHASIL_PINDAH = "Pelanggan dipindahkan ke sales baru.";
export const CONTOH_ALASAN = "mis. wilayah sales berubah";

/** Opsi dropdown sales tujuan: semua sales kecuali yang sedang menjabat. */
export const salesTujuanOptions = (salesUsers, assignedSalesId) =>
  (salesUsers || []).filter((s) => s.id !== assignedSalesId).map((s) => ({ value: s.id, label: s.name }));

/** Kirim penetapan; galat dilempar ke pemanggil. */
export async function reassignCustomer(customerId, { assigned_sales_id, reason }) {
  await axios.post(`${API}/customers/${customerId}/reassign`, { assigned_sales_id, reason });
}
