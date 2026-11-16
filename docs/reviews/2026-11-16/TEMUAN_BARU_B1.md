# Temuan baru reviewer — batch B1 (16 Nov 2026, HEAD `91a3ec0`)

Tingkat bukti ditulis jujur per temuan: **terbukti runtime** (uji dijalankan dan hasilnya dicatat) atau **dugaan — baca
kode** (belum dijalankan).

## RV-01 — Batal keputusan selisih bayar tanpa langkah PERIKSA periode

- Keparahan: Sedang · Lensa: keuangan · Tingkat bukti: **terbukti runtime** (lapis B)
- Bukti: `backend/services/payment_variance_service.py:1072` (`reverse_decision`) langsung klaim → efek → jurnal
  pembalik tahan-gagal; tidak memanggil `_periksa_periode` (`:105`) yang dipakai jalur putus, dan tidak seperti void
  kwitansi (`backend/services/ar_receipt_service.py:701`) atau void pembayaran faktur
  (`backend/routers/vendor_bills.py:687`) yang menolak sebelum efek.
- Reproduksi: faktur 5.000.000 dibayar 4.990.000 dengan keputusan `ap_writeoff` 10.000 → tutup periode bulan berjalan
  PT itu → `POST /api/payment-variances/{id}/reverse`. Hasil: 200; keputusan `reversed`, faktur terbuka lagi (sisa
  10.000), jurnal pembalik 0, `reversal_gl_status: failed`.
  Uji: `test_FX07_periode_tertutup_batal_tutup_sisa_hutang` di `2026-11-13/hasil/bukti/review-B1/test_bantah_PK19.py`.
- Dampak: buku pembantu hutang (atau piutang, untuk hapus sisa) dan buku besar berselisih sampai periode dibuka dan
  jurnal diulang dari panel Posting Gagal. Bertanda, jadi tidak diam-diam — tetapi melanggar urutan `02_STANDAR.md` §1
  (PERIKSA sebelum efek).
- Arah perbaikan: panggil pemeriksa periode hari ini di awal `reverse_decision` untuk jenis berjurnal; tolak 409 tanpa
  menulis.
- Keputusan pemilik: tidak perlu.

## RV-02 — Graf relasi dokumen mengirim nominal tanpa penyaring izin dan salah baca field

- Keparahan: Sedang · Lensa: izin / tampilan · Tingkat bukti: nominal kosong **terbukti runtime**; ketiadaan penyaring
  **baca kode**
- Bukti: `backend/services/document_relations_service.py:248` (`amount=v.get("total_amount")` untuk landed cost) dan
  `:262` (`amount=b.get("total_amount") or b.get("amount")` untuk tagihan pemasok — dokumen tagihan menyimpan
  `grand_total`). Pintu `GET /documents/relations/{doc_type}/{doc_id}` (`backend/routers/documents.py:189`) hanya
  memeriksa izin modul jangkar (`purchase_order.view`), tidak memakai `redact_node` PK-17.
- Reproduksi: peran ber-`purchase_order.view` + `document.view` → `GET /api/documents/relations/purchase_order/po_x`.
  Hasil: 200, simpul tagihan tanpa nominal (bukan karena dijaga, karena field salah). Uji:
  `test_IA01_jalur_lain_relasi_dokumen_po` di `test_bantah_PK17.py`.
- Dampak: dua sisi — (a) pemegang izin tagihan tidak pernah melihat nominal tagihan di linimasa proses PO (cacat
  tampilan); (b) begitu field dibetulkan, nominal bocor ke pembaca tanpa `vendor_bill.view` (IA-01 lewat pintu lain).
  Landed cost: bila dokumennya menyimpan `total_amount`, kebocoran itu sudah nyata hari ini — belum dijalankan.
- Arah perbaikan: baca field yang benar dan lewatkan simpul ke penyaring izin yang sama dengan Jejak Dokumen.
- Keputusan pemilik: tidak perlu.

## RV-03 — Bayar landed cost: kas ber-urutan acak lahir sebelum dokumen diperbarui

- Keparahan: Sedang · Lensa: keuangan · Tingkat bukti: **dugaan — baca kode** (belum dijalankan)
- Bukti: `backend/routers/landed_cost.py:372` — `pay_id = new_id("pay")` lalu `cash_ledger.create_cash(…, seq=pay_id)`;
  dokumen voucher baru diperbarui di `:396-399`. Bila proses terhenti di antara keduanya, kas sudah ada tanpa catatan
  pembayaran, dan pengulangan memakai `pay_id` baru → kas kedua. Pintu ini tidak lewat `ap_payment_service` (PK-05).
- Reproduksi (yang perlu dijalankan pelaksana): paksa galat sesudah `create_cash` berhasil, lepaskan kunci, ulangi bayar
  → hitung kas ber-`ref_type: landed_cost` untuk voucher itu.
- Dampak: pola SL-01/GL-03 pada pintu hutang lain (kas keluar ganda sesudah gagal di tengah).
- Arah perbaikan: id pembayaran turunan dari kunci idempotensi (seperti niat bayar PK-05) atau pindahkan ke
  `ap_payment_service`.
- Keputusan pemilik: tidak perlu. Catatan: bisa tumpang-tindih dengan temuan audit IV-04 (batch B3) — cocokkan saat B3.
