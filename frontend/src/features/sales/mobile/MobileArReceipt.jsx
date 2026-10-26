import ARReceiptModal from "../../crm/ARReceiptModal";

/** Kwitansi penerimaan dari HP sales.
 *  Fase 4 · R1 — form HP ringkas (jumlah, metode, alokasi, catatan) DIGANTI form desktop `crm/ARReceiptModal`
 *  (keputusan pemilik: form input HP tidak diringkas). HP kini juga mendapat tanggal terima, pakai deposit pelanggan,
 *  mode alokasi Otomatis (FIFO) / Manual per Pesanan, petunjuk kas tunai/bank, dan keputusan selisih bayar (dulu
 *  kelebihan bayar HP selalu dijadikan titipan tanpa ditanya). FormModal tampil layar penuh di HP.
 *  Alur khusus HP diteruskan lewat props:
 *   · G2-21 — dibuka dari satu SO (`focusOrderId` / `customer.focus_order_id`) → SO itu di urutan PERTAMA, mode Manual
 *     teralokasi penuh ke SO itu (perilaku desktop "Catat pembayaran" dari SO), bertanda "dibuka".
 *   · `offline` — antrean offline HP (sinyal putus → kwitansi tersimpan di HP & dikirim sekali saat online).
 *  `onDone(pesan, kwitansi)` — `kwitansi` = data server, `null` bila masuk antrean offline. */
export default function MobileArReceipt({ customer, focusOrderId = "", onClose, onDone }) {
  return (
    <ARReceiptModal customerId={customer.id} customerName={customer.name}
      preselectOrderId={focusOrderId || customer.focus_order_id || ""}
      offline testId="m-ar-receipt" onClose={onClose} onDone={onDone} />
  );
}
