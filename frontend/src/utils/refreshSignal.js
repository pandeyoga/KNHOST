/**
 * refreshSignal — sinyal "muat ulang" global (meja gelombang 1, spek 2026-11-25 §5.1).
 *
 * Tombol muat ulang di bilah atas (`TopBar` `refresh-data-button`) memuat ulang data inti aplikasi DAN mengirim sinyal
 * ini; layar yang mendengarkannya (mis. kerangka meja `DeskFrame`) memuat ulang datanya sendiri. Dengan begitu meja
 * tidak lagi butuh tombol muat ulang sendiri di kepala halaman.
 */
export const MUAT_ULANG_EVENT = "kn:muat-ulang";

/** Kirim sinyal muat ulang ke semua pendengar `MUAT_ULANG_EVENT` di jendela ini. */
export function kirimMuatUlang() {
  window.dispatchEvent(new Event(MUAT_ULANG_EVENT));
}
