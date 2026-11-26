import ReceivePaymentModal from "../../finance/payments/ReceivePaymentModal";   // MN-T3 — satu form terima pembayaran
import DetailModal from "../../../components/DetailModal";
import { can } from "../../../config/roles";
import { isPayHeld } from "../../orders/payReport/payReportApi";
import useSalesCashMode from "../../orders/payReport/useSalesCashMode";

export const PESAN_PAKAI_LAPOR_BAYAR = "Pesanan ini menunggu lapor bayar — pakai Lapor bayar di rincian pesanan.";

/** Kwitansi penerimaan dari HP sales.
 *  Fase 4 · R1 — form HP ringkas (jumlah, metode, alokasi, catatan) DIGANTI form desktop `finance/payments/ReceivePaymentModal` (dulu `crm/ARReceiptModal`)
 *  (keputusan pemilik: form input HP tidak diringkas). HP kini juga mendapat tanggal terima, pakai deposit pelanggan,
 *  mode alokasi Otomatis (FIFO) / Manual per Pesanan, petunjuk kas tunai/bank, dan keputusan selisih bayar (dulu
 *  kelebihan bayar HP selalu dijadikan titipan tanpa ditanya). FormModal tampil layar penuh di HP.
 *  Alur khusus HP diteruskan lewat props:
 *   · G2-21 — dibuka dari satu SO (`focusOrderId` / `customer.focus_order_id`) → SO itu di urutan PERTAMA, mode Manual
 *     teralokasi penuh ke SO itu (perilaku desktop "Catat pembayaran" dari SO), bertanda "dibuka".
 *   · `offline` — antrean offline HP (sinyal putus → kwitansi tersimpan di HP & dikirim sekali saat online).
 *  `onDone(pesan, kwitansi)` — `kwitansi` = data server, `null` bila masuk antrean offline.
 *
 *  LB-T8 — `order` (pesanan terpilih) + `user`: pesanan yang ditahan bayar sebelum gudang tidak boleh menerima uang
 *  non-tunai dari pencatat tanpa `payment_report.decide` (server 409). Bagi mereka: bila PT mengizinkan sales menerima tunai
 *  (`pembayaran.sales_terima_tunai` ≠ dilarang) → form khusus TUNAI; selain itu pesan pemandu ke Lapor bayar. Pemutus
 *  (Finance) dan pesanan yang tidak tertahan → form biasa. Server tetap penentu. */
export default function MobileArReceipt({ customer, focusOrderId = "", order = null, user = null, onClose, onDone }) {
  const dibatasi = isPayHeld(order) && !can(user?.permissions, "payment_report", "decide");
  const cash = useSalesCashMode(dibatasi);
  if (dibatasi && !cash.ready) return null;   // mode tunai belum terbaca — jangan berkedip memperlihatkan form penuh
  if (dibatasi && !cash.cashAllowed) {
    return (
      <DetailModal framed size="sm" testId="m-ar-receipt-held" label="Pesanan menunggu lapor bayar" onClose={onClose}>
        <div className="grid gap-3">
          <h2 className="text-fs-16 font-semibold text-kn-text">Pakai Lapor bayar</h2>
          <p className="text-fs-13 text-kn-text" data-testid="m-ar-receipt-held-text">{PESAN_PAKAI_LAPOR_BAYAR}</p>
          <button type="button" className="primary-button btn-sm justify-self-start" data-testid="m-ar-receipt-held-close" onClick={onClose}>Mengerti</button>
        </div>
      </DetailModal>
    );
  }
  return (
    <ReceivePaymentModal customerId={customer.id} customerName={customer.name}
      preselectOrderId={focusOrderId || customer.focus_order_id || ""} cashOnly={dibatasi}
      offline testId="m-ar-receipt" onClose={onClose} onDone={onDone} />
  );
}
