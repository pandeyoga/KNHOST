/**
 * markReminded — "Tandai sudah diingatkan / Catat sudah ditagih" (`POST /collection-reminders/mark`, izin `order.update`).
 * Satu jalur untuk Reminder Penagihan (web & HP) dan Meja Keuangan (Meja gelombang 2, Task 7).
 * row: { customer_id, order_id, order_number }. Galat dilempar ke pemanggil.
 */
import axios, { API } from "../../services/apiClient";

export async function markReminded({ customer_id, order_id, order_number }) {
  await axios.post(`${API}/collection-reminders/mark`, {
    customer_id, order_id, note: `Pengingat penagihan ${order_number}`,
  });
}
