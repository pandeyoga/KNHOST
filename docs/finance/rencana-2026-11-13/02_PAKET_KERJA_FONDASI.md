# Paket kerja fondasi keuangan

Tanggal: 13 Nov 2026 · Dasar: [`../AUDIT_KEUANGAN_2026-11-13.md`](../AUDIT_KEUANGAN_2026-11-13.md) (139 temuan, dibaca di
`cd6963a`…`9834947`) · Status: **rencana, belum ada kode aplikasi yang diubah**.

Dokumen ini membagi 139 temuan audit menjadi 44 paket kerja (PK-01 … PK-44) yang berurutan, ditambah dua paket
(PK-45, PK-46) untuk temuan tambahan yang murah dari riset lanjutan ([`11_TEMUAN_TAMBAHAN.md`](11_TEMUAN_TAMBAHAN.md)). Satu paket = satu sesi
kerja agen pelaksana = satu laporan di `docs/reviews/…/hasil/` = satu kali validasi reviewer. Cara menjalankan satu
paket ada di [`03_PANDUAN_PELAKSANA.md`](03_PANDUAN_PELAKSANA.md).

Setiap temuan dipegang **tepat satu** paket (baris "Temuan"). Temuan lain yang ikut tersentuh ditulis di baris
"Terkait" dan tidak ditutup oleh paket itu.

## Cara membaca satu paket

| Baris | Arti |
|---|---|
| Temuan | ID di laporan audit yang ditutup paket ini |
| Keputusan | Nomor keputusan pemilik di [`10_KEPUTUSAN_PEMILIK.md`](10_KEPUTUSAN_PEMILIK.md). "Menahan" = paket tidak boleh dimulai sebelum dijawab. "Sebagian" = hanya butir yang disebut yang tertahan |
| Setelah | Paket yang harus sudah `implemented_pending_review` lebih dulu |
| Berkas | Titik masuk; daftar lengkap ada di kolom Bukti laporan audit |
| Perilaku baru | Yang harus berubah, dilihat dari luar |
| Selesai bila | Uji yang harus ada dan hijau. Tiap butir menjadi satu tes otomatis kecuali ditulis "uji jalan" |

Dua aturan berlaku untuk semua paket dan tidak diulang di tiap paket:

1. `skenario1.py` (19 titik uji laporan inti) dan `skenario4.py` (kas akhir = neraca, ekuitas akhir = neraca) harus
   tetap lulus sesudah paket apa pun.
2. Paket tidak menambah aturan bisnis baru. Bila perbaikan butuh aturan yang belum diputuskan, butir itu menjadi
   `pending_decision` dan sisanya dilanjutkan.

## Peta urutan

| Gelombang | Isi | Paket | Mengapa di urutan ini |
|---|---|---|---|
| 0 | Persiapan | PK-01 … 04 | Tanpa garis dasar dan tes regresi, tidak ada cara membuktikan sebuah perbaikan |
| 1 | Dua temuan kritis | PK-05, 06 | Satu-satunya yang merusak buku tanpa jalan memperbaiki dari aplikasi |
| 2 | Tinggi yang murah | PK-07 … 17, PK-45, PK-46 | Kecil, terisolasi, tidak butuh keputusan; menutup lubang terbanyak per jam kerja |
| 3 | Pola posting | PK-18 … 25 | Satu pola dipasang ke semua jalur uang; pola diturunkan dari PK-05 dan PK-06 |
| 4 | Nilai persediaan dan antar-PT | PK-26 … 32 | Logika akuntansi; sebagian besar menunggu keputusan pemilik |
| 5 | Infrastruktur | PK-33 … 35 | Transaksi database baru berguna setelah urutan tulis di kode benar |
| 6 | Kontrol | PK-36 … 40 | Mengubah siapa boleh apa; menunggu keputusan pemilik |
| 7 | Laporan dan layar | PK-41 … 44 | Paling terlihat pengguna, paling aman dikerjakan setelah angka di bawahnya benar |

Gelombang 2 boleh berjalan sebelum gelombang 1 selesai divalidasi. Gelombang 3 jangan dimulai sebelum PK-05 dan PK-06
divalidasi reviewer, karena polanya dipakai ulang.

Modul baru (insentif, piutang lanjut, pembayaran, pajak, asisten keuangan) punya prasyarat paket masing-masing; lihat
tabel di akhir dokumen ini.

---

## Gelombang 0 — Persiapan

### PK-01 — Garis dasar dan pendaftaran temuan

- **Temuan:** —
- **Keputusan:** —
- **Berkas:** `docs/reviews/TRACKER.md`, `docs/reviews/2026-11-13/` (baru), `memory/GATE_RECEIPT.json`
- **Perilaku baru:** tidak ada. Hasilnya dokumen.
- **Langkah:**
  1. Catat SHA `HEAD`. Jalankan gate di `docs/KN_00_AGENT_QUICK_START.md` pada data acuan
     (`bash scripts/dev_restore_demo.sh`) dan simpan keluaran apa adanya, termasuk yang merah.
  2. Jalankan `python scripts/verify_data_integrity.py` (semua kelompok) dan `python scripts/guardrails/verify_atomic_claim.py`;
     simpan keluaran.
  3. Buat paket `docs/reviews/2026-11-13/README.md` yang menunjuk laporan audit dan dokumen ini, lalu tambah 139 baris
     ke tracker dengan status `open`, kolom Fase berisi nomor paket.
- **Selesai bila:** berkas `hasil/PK-01.md` memuat SHA, tiap perintah, keluarannya, dan daftar gate yang merah; tracker
  memuat 139 ID tanpa kembar (dicek dengan skrip hitung).
- **Jangan:** memperbaiki apa pun di paket ini, termasuk gate yang merah.

### PK-02 — Tes regresi dari bukti audit

- **Temuan:** —
- **Setelah:** PK-01
- **Berkas:** `docs/finance/bukti-2026-11-13/*.py` → `backend/tests/finance_regress/` (baru)
- **Perilaku baru:** tidak ada.
- **Langkah:** pindahkan tiap titik uji dari `skenario1…4.py` menjadi tes `pytest` di atas `mongomock-motor`. Titik uji
  laporan inti menjadi tes biasa. Sepuluh reproduksi temuan ditulis sebagai **perilaku yang benar** dan ditandai
  "diharapkan gagal" dengan menyebut ID temuannya; tanda itu dicabut oleh paket yang memperbaikinya.
- **Selesai bila:** satu perintah menjalankan seluruh folder; hasilnya 0 gagal, dan jumlah "diharapkan gagal" = 10
  dengan ID: GL-01, GL-04, GL-05, GL-07, IC-01, IC-05, IV-01, FX-02, RC-01, RP-06.
- **Jangan:** mengubah angka harapan agar lulus; menandai "diharapkan gagal" tanpa ID temuan.

### PK-03 — Cek data nyata (dijalankan pemilik atau orang yang memegang data)

- **Temuan:** —
- **Berkas:** laporan audit §12.1 dan §12.2; [`../KUERI_CEK_DATA_LANJUTAN_2026-11-13.md`](../KUERI_CEK_DATA_LANJUTAN_2026-11-13.md)
- **Langkah:** pulihkan cadangan produksi ke database terpisah; jalankan penjaga data dan kueri baca-saja; isi
  `hasil/CEK_DATA.md` dengan jumlah baris per kueri.
- **Selesai bila:** tiap kueri punya angka. Kueri yang hasilnya > 0 diberi satu dari tiga label: "perbaiki data",
  "biarkan + alasan", "tanya pemilik".
- **Catatan:** paket ini menentukan apakah perlu **paket perbaikan data** terpisah (jurnal sebelah antar-PT, kas tanpa
  jurnal, setoran karyawan ganda). Perbaikan data tidak boleh digabung dengan perbaikan kode.

### PK-04 — Cadangan lebih sering dan uji pulih

- **Temuan:** DB-03
- **Keputusan:** pemilik menyetujui perubahan di jalur produksi (`deploy/backup.sh`)
- **Berkas:** `deploy/backup.sh`
- **Perilaku baru:** cadangan lebih dari sekali sehari, retensi lebih panjang untuk cadangan akhir bulan, dan satu
  prosedur pulih yang sudah pernah dicoba.
- **Selesai bila:** (uji jalan) cadangan terbaru dipulihkan ke database kosong dan `verify_data_integrity.py`
  berjalan di atasnya; langkahnya ditulis di `docs/LOCAL_DEV.md` atau dokumen operasi.
- **Catatan:** pemulihan ke titik waktu baru mungkin setelah PK-34 (`mongodump --oplog`).

---

## Gelombang 1 — Kritis

### PK-05 — Bayar hutang supplier lewat satu pintu yang aman

- **Temuan:** SL-01, SL-02, SL-12, GL-03, UX-10
- **Keputusan:** —
- **Setelah:** PK-02
- **Berkas:** `backend/services/contra_bon_service.py:1190-1262`, `backend/routers/vendor_bills.py:501-628`,
  `backend/services/gl_service.py:569-575` (`preflight_posting`, `post_cash_durable`), layar
  `frontend/src/features/purchasing/VendorBill*.jsx`, `contrabon/`
- **Perilaku baru:**
  1. Satu fungsi layanan `bayar hutang` dipakai oleh bayar-langsung dan bayar-kontrabon.
  2. Urutan tetap: periksa periode dan akun → periksa semua faktur (status, sisa, tidak sedang dipegang kontrabon lain)
     → simpan **niat bayar** berstatus `pending` dengan id tetap → kas (id diturunkan dari niat) → jurnal lewat
     `post_cash_durable` → faktur → niat menjadi `done`.
  3. Panggilan ulang dengan niat yang sama meneruskan dari langkah terakhir, tidak mengulang langkah yang sudah jadi.
  4. `POST /vendor-bills/{id}/pay` menolak faktur yang sedang dipegang kontrabon.
  5. Entitas kas = entitas faktur; nilai dari klien diabaikan.
  6. Form bayar meminta tanggal, rekening, catatan; server mewajibkan rekening.
  7. Kontrabon disimpan dengan syarat versi; nomor faktur supplier unik per supplier per entitas.
- **Selesai bila:**
  1. Tanggal bayar di periode tertutup → ditolak **sebelum** ada tulisan apa pun (kas, faktur, kontrabon tidak berubah).
  2. Jurnal dipaksa gagal di tengah → kas bertanda `gl_status=failed`, tampil di panel Posting Gagal, pembayaran
     tercatat; diulang → tepat satu kas, satu jurnal, potongan terpakai sekali.
  3. Dua permintaan bayar bersamaan untuk nominal parsial yang sama dengan kunci idempotensi sama → satu pembayaran.
  4. Bayar-langsung atas faktur yang ada di kontrabon aktif → 409.
  5. Kirim `entity_id` PT lain di isi permintaan → kas tetap di entitas faktur.
- **Jangan:** menghapus endpoint lama sebelum layar dialihkan; mengubah arti status kontrabon.

### PK-06 — Jurnal kembar antar-PT yang utuh dan bisa diulang

- **Temuan:** IC-01, IC-08
- **Keputusan:** —
- **Setelah:** PK-02
- **Berkas:** `backend/services/interco_service.py:500-505, 645-693, 1098-1346`,
  `backend/services/interco_return_service.py:516-518`, `backend/routers/posting_failures.py`
- **Perilaku baru:**
  1. Satu pembantu "jurnal kembar" dipakai konfirmasi, settlement, dan retur: periksa periode dan akun **kedua** PT
     sebelum status berubah; penjaga "sudah ada" diperiksa **per sisi**.
  2. Dokumen antar-PT menyimpan `gl_status` per sisi. Sisi yang gagal tampil di panel Posting Gagal dan punya tombol
     ulang yang hanya menerbitkan sisi yang kurang.
  3. Settlement membuat transaksi kas kembar (keluar di pembayar, masuk di penerima) dan tidak bisa dilunasi dua kali
     (operasi bersyarat pada sisa).
- **Selesai bila:**
  1. Tes "diharapkan gagal" IC-01 lulus tanpa tanda: akun pembeli dinonaktifkan → konfirmasi ditolak, status tetap draf,
     tidak ada jurnal di PT mana pun.
  2. Sisi pembeli dipaksa gagal setelah sisi penjual terbit → `gl_status` pembeli `failed`; ulang → sisi pembeli terbit,
     sisi penjual tetap satu.
  3. Dua settlement bersamaan atas dokumen yang sama → total pelunasan ≤ sisa.
  4. Untuk tiap settlement: Σ kas keluar pembayar = Σ kas masuk penerima = nominal jurnal.
- **Jangan:** menyentuh eliminasi konsolidasi (PK-31) atau panjang roll (PK-30).

---

## Gelombang 2 — Tinggi yang murah

### PK-07 — Setoran karyawan pada kasus keuangan terbukukan dua kali

- **Temuan:** FX-01
- **Berkas:** `backend/services/finance_case_actions.py:345-375`
- **Perilaku baru:** satu aksi setor = satu kas masuk = satu jurnal.
- **Selesai bila:** setor 10 jt → tepat satu `cash_transactions` senilai 10 jt dan saldo 1-1280 berkurang 10 jt.
- **Catatan:** kasus lama yang sudah terlanjur ganda adalah urusan perbaikan data (PK-03), bukan paket ini.

### PK-08 — Denda keterlambatan dihitung dan dijurnal dengan benar

- **Temuan:** FX-02, FX-03, FX-04
- **Berkas:** `backend/services/penalty_service.py`, `backend/services/gl_service.py:2017-2046`,
  `backend/routers/payment_plans.py:175-184`
- **Perilaku baru:** kunci jurnal per **kejadian** (tiap bayar, tiap ubah); bebas-denda membalik **sisa**; ubah di bawah
  yang sudah dibayar ditolak; hari telat nota berikutnya = selisih dari nota sebelumnya; tanggal "hari ini" dari
  server; bayar denda membuat transaksi kas dengan rekening, bukan hanya jurnal.
- **Selesai bila:** tes FX-02 lulus tanpa tanda; bayar parsial dua kali → dua jurnal, piutang denda = nota − Σ bayar;
  bebas setelah bayar sebagian → piutang denda 0, tidak negatif; telat 49 hari lintas dua bulan → Σ hari di dua nota =
  49; saldo rekening naik sebesar bayar denda.
- **Catatan:** paket ini prasyarat modul piutang lanjut ([`06_PIUTANG_LANJUT.md`](06_PIUTANG_LANJUT.md)).

### PK-09 — Entitas tidak boleh datang dari isi permintaan

- **Temuan:** IC-05, IC-11, SL-07, FX-08, FX-17, FY-15
- **Berkas:** `backend/entity_scope.py:622` (`resolve_requested_entity`), `backend/routers/gl.py:147-159`,
  `backend/services/gl_service.py:665`, `backend/routers/cash.py:142-167`, `backend/services/finance_case_actions.py`,
  `backend/routers/payment_plans.py`, `payment_variance.py`, `tax_center.py`, `input_tax.py`, `interco.py`,
  `consolidation.py`
- **Perilaku baru:** setiap titik tulis dan baca-ber-id di daftar berkas memakai `resolve_requested_entity()`; dokumen
  yang dirujuk lewat id (pesanan, kwitansi, rekening, pelanggan) diadu dengan entitas dokumen induk dan cakupan
  pengguna; kas manual menolak `ref_type` dari klien; kasus tanpa PT ditolak.
- **Selesai bila:** tes IC-05 lulus tanpa tanda; untuk tiap endpoint di daftar ada tes "pengguna PT-B mengirim id atau
  `entity_id` PT-A → 403/404, tanpa tulisan"; `scripts/guardrails/verify_cross_entity.py` tetap hijau.
- **Jangan:** mengubah arti mode "Semua Entitas" untuk baca.

### PK-10 — Jurnal manual lewat validator pusat; satu penanda pembalik

- **Temuan:** GL-01, GL-07
- **Berkas:** `backend/services/gl_service.py:555, 684-691, 805-849, 1519-1540, 2239-2255`
- **Perilaku baru:** jurnal manual memanggil validator pusat (selisih dibandingkan dalam sen bulat); pembalik manual dan
  pembalik dokumen menulis dan memeriksa penanda yang sama; semua jurnal bertipe pembalik tidak bisa dibalik.
- **Selesai bila:** tes GL-01 (dua mekanisme) dan GL-01b (membalik jurnal pembalik otomatis) serta GL-07 (selisih 1 sen)
  lulus tanpa tanda.

### PK-11 — Periode yang belum berakhir tidak bisa ditutup

- **Temuan:** GL-04
- **Berkas:** `backend/services/closing_service.py:297-309`
- **Perilaku baru:** tutup ditolak bila akhir periode ≥ hari ini (WIB); catatan "sedang ditutup" ditulis lebih dulu
  sebagai kunci dan dilepas hanya oleh pemiliknya.
- **Selesai bila:** tes GL-04 lulus tanpa tanda; dua permintaan tutup bersamaan → satu berhasil.

### PK-12 — Kunci idempotensi dan penahan klik ganda di semua form uang

- **Temuan:** UX-01, UX-02, GL-08, FY-18
- **Berkas:** `backend/idempotency.py:21-25`, `frontend/src/hooks/useIntentKey.js`,
  `frontend/src/features/purchasing/CashManagementView.jsx`, form jurnal, aset, kas kecil, pajak, antar-PT
- **Perilaku baru:** awalan `/api/gl`, `/api/cash`, `/api/vendor-bills`, `/api/contra-bons`, `/api/interco`,
  `/api/fixed-assets`, `/api/cash-advances`, `/api/settlements`, `/api/payment-plans`, `/api/payment-variance`,
  `/api/finance-cases` masuk daftar server; tiap form uang mengirim kunci dan mematikan tombol selama menunggu.
- **Selesai bila:** untuk tiap awalan: dua POST dengan kunci sama → satu dokumen, jawaban kedua = jawaban pertama; tes
  layar: klik ganda "Catat Transaksi" → satu permintaan.
- **Jangan:** memakai kunci sebagai pengganti penjaga status di server.

### PK-13 — Konfirmasi untuk aksi uang sekali klik

- **Temuan:** UX-03, FY-17
- **Berkas:** `frontend/src/features/purchasing/VendorBillsView.jsx`, `VendorBillDetailPanel.jsx`,
  `features/pettycash/SettlementDetail.jsx`, `features/finance/FixedAssetsView.jsx`, `TaxCenterView.jsx`
- **Perilaku baru:** setujui/batalkan faktur, setujui & posting LPJ, bayar reimburse, bayar pindah aset, hapus pagu,
  hapus rekaman PPh meminta konfirmasi yang menyebut nominal dan PT; pembatalan meminta alasan.
- **Selesai bila:** tes layar per aksi: tanpa konfirmasi tidak ada permintaan ke server.

### PK-14 — Indeks unik wajib ada

- **Temuan:** GL-09, IC-12, FX-19
- **Setelah:** PK-03 (indeks unik gagal dibuat bila data kembar sudah ada)
- **Berkas:** `backend/indexes.py:570-590`, `backend/bootstrap.py:1793-1797`
- **Perilaku baru:** daftar indeks keuangan wajib (jurnal per sumber, nomor antar-PT, nota denda per periode, rencana
  aktif per dokumen, kasus per sumber) diperiksa saat mulai; bila tidak ada, aplikasi **tidak mulai** dan menulis
  indeks mana yang kurang serta kueri pencari kembarnya.
- **Selesai bila:** (uji di MongoDB asli, bukan tiruan) menghapus satu indeks wajib → aplikasi gagal mulai dengan pesan
  itu; dua sisipan kembar bersamaan → satu ditolak.
- **STOP & ASK:** bila data nyata sudah punya kembar, jangan menghapus atau menggabung sendiri.

### PK-15 — Alokasi titipan bank dan biaya bank

- **Temuan:** SL-03, SL-04
- **Berkas:** `backend/services/bank_recon_service.py:972-984, 1225-1241`
- **Perilaku baru:** `source_id` jurnal unik per alokasi; sisa titipan ditulis per alokasi dengan syarat nilai lama;
  biaya/bunga bank memeriksa periode dulu dan memakai ulang kas per rujukan.
- **Selesai bila:** dua alokasi dari titipan yang sama ke pesanan yang sama → dua jurnal; gagal di alokasi kedua →
  sisa titipan = awal − alokasi pertama; biaya bank di periode tertutup → ditolak tanpa kas; diulang → satu kas.

### PK-16 — Laporan menyebut entitasnya; mode gabungan diberi label

- **Temuan:** UX-06, UX-07, UX-14, RC-01, RP-02, RP-04
- **Keputusan:** K-15 (sebagian: versi murah di sini hanya label; memakai mesin konsolidasi menunggu keputusan)
- **Berkas:** `frontend/src/features/finance/FinancialStatementsView.jsx`, `GeneralLedger.jsx`, `BiFinanceView.jsx`,
  `FinanceTowerView.jsx`, `JournalEntryModal.jsx`, `features/purchasing/CashManagementView.jsx`,
  `backend/services/analytics_engine.py:209-215`
- **Perilaku baru:** satu komponen banner entitas di semua laporan, form uang, dan berkas ekspor; mode gabungan menulis
  "Penjumlahan semua PT — transaksi antar-PT **belum** dieliminasi"; angka lama tidak ditampilkan saat gagal memuat;
  "pendapatan diakui" Tanya KN mengecualikan jurnal penutup; nama PT bawaan yang ditulis mati dihapus.
- **Selesai bila:** tes RP-04 (Oktober 500 ditutup, November 200 → November tampil 200); tes layar: banner ada di tiap
  laporan dan di kepala CSV; gagal muat → area angka kosong + galat.
- **Catatan:** tes RC-01 tetap "diharapkan gagal" sampai K-15 dijawab.

### PK-17 — Nominal keuangan hanya untuk yang berizin

- **Temuan:** IA-01, IA-02, IA-03, IA-09
- **Keputusan:** K-18 (menahan butir IA-01 saja)
- **Berkas:** `backend/routers/home.py:98-110`, `backend/routers/documents.py:97, 142`,
  `backend/services/doc_refs_service.py:360, 611-634`, `backend/services/export_registry.py:210`,
  `backend/routers/bank.py:49, 68`, `backend/routers/interco.py:64-68`
- **Perilaku baru:** papan Meja Finance memeriksa izin; ekspor dan rekening mengikuti izin modulnya; saldo antar-PT dan
  daftar kontrabon bernilai tidak tampil untuk peran tanpa izin keuangan.
- **Selesai bila:** tes per endpoint dengan peran gudang/sales: 403 atau nominal disembunyikan;
  `scripts/guardrails/verify_auth_coverage.py` tetap hijau.

### PK-45 — Penjaga cepat dari riset lanjutan (plafon, faktur pajak, gaji)

- **Temuan:** CR-01, TX-01, TX-02, TX-03, TX-04, PY-05, PY-10
- **Terkait:** CR-04 (hanya penjaga entitas dan nominal > 0; sisanya di CR-T3)
- **Keputusan:** K-28 (menahan butir CR-01 saja)
- **Berkas:** `backend/routers/customers.py:171-184`, `backend/routers/crm.py:91-156`,
  `backend/services/tax_invoice_service.py:182-248`, `backend/services/input_tax_service.py:122-134`,
  `backend/services/amendment_service.py:277-278`, `backend/routers/tax_invoices.py:61-88`,
  `backend/routers/sales_orders.py:308`, `backend/services/hr_payroll_service.py:241, 337-338`,
  `backend/routers/hr_payroll.py:106-112`
- **Perilaku baru:**
  1. `PATCH /customers/{id}` tidak lagi menerima `credit_limit` dan `status`; keduanya lewat endpoint tersendiri
     berizin khusus (jalur sementara sampai CR-T1).
  2. Daftar dan keputusan izin kredit diadu dengan entitas pelanggan; nominal izin wajib > 0.
  3. Faktur yang sudah diganti tidak ikut dijumlah di rekap PPN.
  4. Faktur batal melepas kunci amandemen pesanan.
  5. Ubah NSFP, ganti, dan batal faktur mengadu entitas faktur dengan cakupan pengguna.
  6. `tax_override = non_ppn` pada pesanan memerlukan izin khusus dan alasan.
  7. Penggajian membaca `separation_date`.
  8. Pratinjau gaji memakai `resolve_requested_entity`.
- **Selesai bila:**
  1. Sales mengirim `credit_limit` → nilai tidak berubah.
  2. **TX-01 diuji lebih dulu** (temuan ini baru dibaca, belum dijalankan): faktur PPN 110 diganti dengan faktur PPN 99
     di masa yang sama → rekap 99. Bila tes sudah hijau sebelum kode diubah, tulis "tidak dapat direproduksi" beserta
     langkahnya.
  3. Faktur dibatalkan → amandemen pesanan tidak lagi ditolak karena faktur.
  4. Pengguna PT-B membatalkan faktur PT-A → 403/404.
  5. Pesanan non-PPN tanpa izin → 403.
  6. Karyawan dengan `separation_date` di bulan berjalan → ikut proses gaji bulan itu dan pajaknya dihitung ulang
     tahunan.
  7. Pratinjau gaji dengan `entity_id` PT lain atau `all` → ditolak.

### PK-46 — Tabel tarif PPh 21 dari pengaturan bertanggal berlaku

- **Temuan:** PY-03
- **Keputusan:** K-42 (menahan: tabel harus diverifikasi orang pajak terhadap lampiran peraturan)
- **Berkas:** `backend/services/hr_payroll_service.py:23-70`, `backend/config_catalog_ops.py`
- **Perilaku baru:** tabel tarif efektif (tiga kategori) dan PTKP dibaca dari pengaturan bertanggal berlaku; isi awalnya
  tabel yang sudah diverifikasi dan dilampirkan di laporan paket beserta sumbernya.
- **Selesai bila:** untuk tiap kategori, lima titik uji dari tabel terverifikasi (batas bawah, tengah, batas atas, satu
  di atas 100 jt, satu di atas batas tertinggi) menghasilkan tarif yang sama; mengganti tabel untuk tahun depan tidak
  mengubah slip tahun ini.
- **STOP & ASK:** jangan mengisi tabel dari ingatan atau dari sumber tidak resmi.

---

## Gelombang 3 — Pola posting

Pola yang dipasang di gelombang ini ditulis lengkap di [`04_ATURAN_MODUL_BARU.md`](04_ATURAN_MODUL_BARU.md) §1
("kontrak posting"). Ringkasnya: periksa dulu → simpan niat → efek → jurnal tahan-gagal → selesai; setiap dokumen
menyimpan `gl_status`; setiap jenis terdaftar di panel Posting Gagal.

### PK-18 — Penanda gagal dan panel untuk semua jenis dokumen

- **Temuan:** GL-02, GL-12, IV-04, UX-04
- **Setelah:** PK-05, PK-06 divalidasi
- **Berkas:** `backend/routers/posting_failures.py:17-23`, `backend/routers/vendor_bills.py:423-427`,
  `backend/routers/landed_cost.py:262-284`, `backend/services/makloon_order_service.py:726-738`,
  `backend/services/roll_service.py:741-749`, `frontend/src/features/finance/PostingFailuresView.jsx`
- **Perilaku baru:** faktur supplier, landed cost, langkah makloon, susut potong, nota kredit, void kwitansi, aset,
  antar-PT menulis `gl_status` dari **hasil** posting (bukan menulis "posted" lebih dulu) dan terdaftar di panel;
  panel membedakan "memuat", "galat", "kosong"; dokumen sumber menampilkan lencana status jurnal; akun yang bersaldo
  atau terpetakan tidak bisa dinonaktifkan.
- **Selesai bila:** untuk tiap jenis: jurnal dipaksa gagal → dokumen `failed`, muncul di panel, ulang → terbit sekali;
  penjaga baru `scripts/guardrails/verify_posting_coverage.py` (lihat `04` §4) hijau.

### PK-19 — Kwitansi, deposit, selisih bayar: satu fungsi alokasi

- **Temuan:** SL-05, SL-06, SL-08, SL-14, FX-05, FX-06, FX-07, IA-07
- **Setelah:** PK-18
- **Berkas:** `backend/services/ar_receipt_service.py`, `backend/services/payment_variance_service.py`,
  `backend/routers/invoices.py:37-155`, `frontend/src/hooks/useAppActions.js:485`,
  `frontend/src/features/orders/OrderDetailPanel.jsx:101, 636`
- **Perilaku baru:** satu fungsi alokasi memvalidasi pelanggan, entitas, status pesanan, dan sisa untuk **semua**
  sumber (kwitansi, deposit, titipan, kasus, saldo kredit); deposit berkurang per alokasi; void kwitansi menandai tiap
  langkah di dokumen sehingga aman diulang; hapus sisa memakai klaim dan menyimpan keputusan `pending` lebih dulu;
  batal keputusan selisih hutang membalik jurnalnya; "simulasi bayar" dimatikan dan tombolnya dihapus.
- **Selesai bila:** deposit pelanggan A ke pesanan pelanggan B atau PT lain → ditolak; alokasi ke pesanan batal/draf →
  ditolak; alokasi kedua gagal → deposit = awal − alokasi pertama; void diulang setelah gagal di tengah → deposit
  bergeser sekali; dua klik hapus sisa → satu hapus-buku; `POST /invoices/.../simulate-payment` → 410 dan tidak ada
  pemanggil di layar.
- **Catatan:** paket ini prasyarat modul insentif (angka pencairan) dan piutang lanjut.

### PK-20 — Kas dibuat lewat satu pembuat

- **Temuan:** SL-11
- **Terkait:** duplikasi no. 5 dan 6 di laporan audit §4
- **Setelah:** PK-18
- **Berkas:** `backend/services/cash_ledger.py`, `backend/services/gl_service.py:575, 2683`, ±10 pemanggil
  `post_cash_transaction`
- **Perilaku baru:** satu fungsi membuat `cash_transactions` (rekening wajib, entitas dari dokumen, id deterministik
  dari rujukan) dan selalu memposting lewat `post_cash_durable`; field rekening tidak lagi berisi kode akun.
- **Selesai bila:** tidak ada sisipan langsung ke `cash_transactions` di luar pembuat (penjaga statis); semua pemanggil
  lama `post_cash_transaction` dialihkan; kas tanpa rekening → ditolak.
- **Catatan:** prasyarat rancangan pembayaran ([`07_PAJAK_DAN_PEMBAYARAN.md`](07_PAJAK_DAN_PEMBAYARAN.md)).

### PK-21 — Rekonsiliasi bank satu mekanisme

- **Temuan:** SL-10
- **Berkas:** `backend/services/bank_recon_service.py:654-670, 860-874`, `backend/services/bank_service.py:267-277`
- **Perilaku baru:** cocok dan lepas-cocok adalah operasi bersyarat; tombol `reconciled` manual dihapus dan nilainya
  diturunkan dari alokasi.
- **Selesai bila:** dua lepas-cocok bersamaan → satu berhasil; Σ `reconciled_amount` = Σ alokasi untuk tiap mutasi.

### PK-22 — Penggajian: tanggal buku, hitung ulang, batal, setoran kewajiban

- **Temuan:** FY-02, FY-06, FY-07, FY-08, FY-09
- **Keputusan:** K-13 (menahan FY-02), K-22 (menahan FY-08; lihat rancangan insentif)
- **Berkas:** `backend/services/hr_payroll_service.py`, `backend/services/gl_service.py:2894-2938, 3042-3124`,
  `backend/services/fixed_asset_service.py:263-267`, `frontend/src/features/hr/PayrollRunsView.jsx`
- **Perilaku baru:** jurnal periodik (gaji, penyusutan, insentif, LPJ) bertanggal akhir periodenya dan menolak periode
  depan; proses gaji berstatus draf bisa dihitung ulang; sebelum posting bisa dibatalkan; sesudah posting bisa di-void
  dengan jurnal balik; ada dokumen "setor kewajiban" (Dr hutang BPJS/PPh 21, Cr kas) per periode; akun bayar gaji
  dibatasi ke akun kas/bank; ajukan, sahkan, posting, bayar memakai izin terpisah.
- **Selesai bila:** gaji Oktober diposting 3 Nov → jurnal bertanggal 31 Okt; ubah tunjangan lalu hitung ulang draf →
  slip berubah; void → saldo beban gaji periode itu 0; setor BPJS → saldo 2-1700 turun, beban tidak naik; satu
  pengguna tanpa izin sahkan tidak bisa menyahkan ajuannya sendiri.
- **Catatan:** rincian struktur slip (komponen) ada di [`09_HR_DAN_PAYROLL.md`](09_HR_DAN_PAYROLL.md); paket ini
  hanya menutup temuan audit.

### PK-23 — Aset tetap

- **Temuan:** FY-01, FY-03, FY-04, FY-05, FY-20
- **Setelah:** PK-06 (pembantu jurnal kembar), PK-18
- **Berkas:** `backend/services/fixed_asset_service.py`, `backend/routers/fixed_assets.py:188-199`,
  `backend/services/gl_service.py:2346-2362`, `frontend/src/features/finance/FixedAssetsParts.jsx`
- **Perilaku baru:** periksa periode sebelum aset disimpan; aset menyimpan `gl_status`; sumber dana wajib dipilih (kas +
  rekening / hutang supplier / saldo awal) dan menentukan akun kredit; pindah aset antar-PT memakai pembantu jurnal
  kembar; aset `transferred` tidak bisa disusutkan, diubah, atau dilepas; sisa pembulatan disusutkan di bulan terakhir.
- **Selesai bila:** perolehan di periode tertutup → ditolak tanpa baris aset; perolehan "hutang" → kas buku besar tidak
  berubah; pindah aset dengan periode pengirim tertutup → ditolak di kedua PT; Σ penyusutan seumur aset = nilai yang
  disusutkan, tepat.

### PK-24 — Kas kecil dan pertanggungjawaban

- **Temuan:** SL-09, FY-13, FY-14, FY-19, IA-05
- **Keputusan:** K-17 (menahan IA-05)
- **Berkas:** `backend/services/cash_advance_service.py`, `backend/schemas_cash_advance.py:71-75`,
  `frontend/src/features/pettycash/`
- **Perilaku baru:** ada dokumen pengembalian sisa uang muka; pembuat ≠ penyetuju; peta kategori→akun memakai lapisan
  entitas; LPJ terkunci setelah diajukan dan wajib berlampiran; teks "Sisa Dikembalikan" hanya tampil bila alurnya
  ada.
- **Selesai bila:** uang muka 1 jt, LPJ 800 rb, kembali 200 rb → saldo 1-1400 untuk orang itu 0; LPJ PT-A dengan
  override PT-B → terposting ke akun PT-A; ubah LPJ setelah diajukan → ditolak.

### PK-25 — Kasus keuangan: periksa dulu, efek kemudian

- **Temuan:** FX-09, FX-11, FX-18
- **Setelah:** PK-09, PK-19
- **Berkas:** `backend/services/finance_case_actions.py`, `finance_case_service.py`, `finance_case_scan.py`
- **Perilaku baru:** tiap aksi memeriksa syarat sebelum efek dan memakai id pembayaran deterministik; kasus "salah
  entitas" membuat dokumen antar-PT kembar; pemindai mengingat keputusan per kwitansi.
- **Selesai bila:** langkah dijalankan dua kali → satu pembayaran, satu jurnal; kasus "bayar dobel" yang sudah ditutup
  tidak lahir lagi pada pemindaian berikutnya; kasus salah entitas → saldo antar-PT tampil di layar Saldo Antar-PT.

---

## Gelombang 4 — Nilai persediaan dan antar-PT

### PK-26 — Landed cost untuk roll yang sudah terjual

- **Temuan:** IV-01, IV-10
- **Keputusan:** K-05 (menahan)
- **Berkas:** `backend/services/landed_cost_service.py`, `backend/services/gl_service.py:2479-2495`
- **Perilaku baru:** jurnal landed cost dipecah: porsi roll yang masih dimiliki → persediaan; porsi terjual → HPP atau
  varians (sesuai keputusan); porsi di mitra → WIP makloon. Hapus-buku susut memakai biaya termasuk landed.
- **Selesai bila:** tes IV-01 lulus tanpa tanda: Σ kenaikan biaya roll hidup = debit persediaan.

### PK-27 — Biaya roll pada scrap, retur, dan HPP

- **Temuan:** IV-02, IV-06, IV-07, IV-08
- **Berkas:** `backend/services/return_service.py:244, 1126-1131, 1299-1311`,
  `backend/services/purchase_return_service.py:107-134`, `backend/services/gl_service.py:1154-1260, 3282-3286`
- **Perilaku baru:** roll scrap tidak lagi masuk valuasi; retur beli mengkredit persediaan pada nilai buku, selisih ke
  varians; HPP memakai biaya per roll apa adanya dan roll berbiaya 0 dilaporkan; barang retur masuk pada HPP surat
  jalan asalnya.
- **Selesai bila:** setelah scrap, selisih rekonsiliasi persediaan tidak berubah; satu roll berbiaya 0 di surat jalan →
  HPP roll lain tidak berubah dan roll itu muncul di daftar "biaya 0"; retur → nilai masuk = HPP asal.

### PK-28 — GR/IR: varians, umur, kliring

- **Temuan:** IV-03
- **Berkas:** `backend/services/gl_service.py:1832-1848, 2460-2464`, `backend/services/vendor_bill_service.py:128-134`,
  `backend/services/po_close_settlement_service.py`
- **Perilaku baru:** selisih harga faktur vs PO masuk akun varians; jumlah tertagih dikurangi retur; tutup-kurang PO
  menjurnal sisa GR/IR; ada laporan GR/IR per PO berumur.
- **Selesai bila:** terima 100 @10, faktur 100 @11 → GR/IR 0, varians 100; terima 100, retur 20, faktur 80 → GR/IR 0.

### PK-29 — Rekonsiliasi persediaan per PT; true-up dibatasi

- **Temuan:** IV-05, IV-09, GL-13
- **Keputusan:** K-06 (menahan butir true-up)
- **Berkas:** `backend/services/gl_service.py:3282-3321, 3600-3645`, `backend/services/gl_mapping_service.py:54-66`
- **Perilaku baru:** `reconciled` dihitung per PT dengan akun hasil pemetaan; agregasi dilakukan di database tanpa batas
  baris diam-diam; true-up hanya untuk saldo awal (bila diputuskan begitu) dan butuh alasan + penyetuju.
- **Selesai bila:** PT-A lebih 5, PT-B kurang 5 → keduanya "tidak sinkron"; 150.000 roll → total = hitungan tangan.

### PK-30 — Antar-PT: panjang aktual, jalur lama, harga dan PPN

- **Temuan:** IC-02, IC-09, IC-10
- **Keputusan:** K-07 (menahan IC-02)
- **Berkas:** `backend/services/interco_service.py:166-168, 306-312, 747-760, 1773-1791`,
  `backend/routers/transfers.py:337-345`, `frontend/src/features/pos/CheckoutDrawer.jsx`
- **Perilaku baru:** selisih panjang roll vs pesanan diselesaikan sebelum jurnal barang (dokumen menyesuaikan, atau
  transfer ditolak); kasir memakai mesin antar-PT; ubah harga atau mode PPN butuh izin dan alasan; status PKP dua sisi
  divalidasi.
- **Selesai bila:** pesan 100 m, roll 130 m → nilai persediaan pembeli = HPP penjual-ke-pembeli untuk panjang yang
  sama; tidak ada pemanggil jalur transfer lama.

### PK-31 — Eliminasi per periode; rantai A→B→C; retur setelah lunas

- **Temuan:** IC-03, IC-04, IC-07, RP-10
- **Keputusan:** K-10 (kepemilikan grup)
- **Berkas:** `backend/services/consolidation_service.py`, `backend/services/interco_margin.py`,
  `backend/services/interco_return_service.py`
- **Perilaku baru:** eliminasi dihitung dari jurnal ≤ tanggal laporan dan disimpan per periode; laba belum terealisasi
  mengikuti rantai sampai barang keluar grup; retur setelah lunas tercatat sebagai klaim balik dengan jalur refund.
- **Selesai bila:** neraca konsolidasi 31 Des yang dibuka pada dua tanggal berbeda menghasilkan angka sama; konfirmasi
  28 Des, kirim 5 Jan, belum terjual → laba konsolidasi kedua tahun 0; retur setelah lunas → layar Saldo Antar-PT
  menampilkan utang refund = saldo buku besar.

### PK-32 — Nota kredit satu mesin

- **Temuan:** FX-12, FX-13, FX-14, FX-15
- **Keputusan:** K-14 (menahan FX-15)
- **Berkas:** `backend/services/amendment_service.py`, `backend/services/return_service.py:204-223`,
  `backend/services/od_cancel_credit_note.py`, `backend/services/gl_service.py:2613-2623`
- **Perilaku baru:** satu pembuat nota kredit dengan satu kosakata status dan `gl_status`; Σ nota kredit ≤ nilai
  pesanan; retur memakai nilai efektif setelah koreksi harga; pendapatan hanya dibalik bila sudah diakui.
- **Selesai bila:** koreksi turun 20 % lalu retur penuh → Σ kredit = 100 %; pesanan dibayar, belum dikirim, dikoreksi →
  pendapatan tidak negatif.

---

## Gelombang 5 — Infrastruktur

### PK-33 — Hijaukan penjaga atomisitas

- **Temuan:** DB-01
- **Berkas:** `scripts/guardrails/verify_atomic_claim.py`, `scripts/guardrails/baselines/`
- **Perilaku baru:** 97 endpoint tulis multi-koleksi yang belum ditinjau diberi salah satu dari: klaim saga, alasan
  tertulis mengapa aman, atau masuk daftar paket gelombang 3–4.
- **Selesai bila:** penjaga keluar 0; daftar "aman karena…" ditinjau reviewer.

### PK-34 — Replica set satu node, transaksi di jalur uang, pustaka database

- **Temuan:** DB-04
- **Terkait:** DB-01
- **Keputusan:** K-01 (menahan); jendela henti produksi
- **Setelah:** gelombang 3 divalidasi
- **Berkas:** `deploy/docker-compose.yml` (jalur produksi — hanya dengan persetujuan pemilik), `docker-compose.dev.yml`,
  `backend/db.py`, `backend/requirements.txt`
- **Perilaku baru:** `mongod` berjalan sebagai replica set satu anggota; jalur uang gelombang 1 dan 3 dibungkus transaksi
  (dokumen + buku pembantu + jurnal; dua sisi antar-PT; bayar multi-faktur); Motor diganti PyMongo Async; cadangan
  memakai `--oplog`.
- **Selesai bila:** (uji di MongoDB asli) proses dimatikan di tengah bayar kontrabon → tidak ada tulisan sebagian; gate
  penuh hijau; uji pulih dari cadangan `--oplog` berhasil.
- **STOP & ASK:** sebelum menyentuh `deploy/`; bila transaksi pada replica set satu anggota tidak berjalan di versi
  yang dipakai.

### PK-35 — Uang sebagai bilangan bulat; validator; penomoran

- **Temuan:** DB-02, IV-11, GL-11
- **Keputusan:** K-01
- **Setelah:** PK-34
- **Berkas:** `backend/services/gl_service.py:450-451, 607, 621`, `backend/core_utils.py:204-207`, skrip migrasi baru
- **Perilaku baru:** nominal jurnal disimpan sebagai rupiah bulat (atau Decimal128, sesuai keputusan); validator skema
  memaksa Σdebit = Σkredit per jurnal; sisa sen per penerimaan tidak menumpuk; satu deret nomor per entitas dan laporan
  celah nomor.
- **Selesai bila:** migrasi diuji di salinan data: Σ saldo tiap akun sebelum = sesudah; sisipan jurnal tak seimbang
  ditolak **oleh database**.
- **STOP & ASK:** sebelum menjalankan migrasi pada data nyata.

---

## Gelombang 6 — Kontrol

### PK-36 — Akun kontrol tertutup dari jurnal manual

- **Temuan:** IC-06, GL-10
- **Keputusan:** K-02 (menahan)
- **Berkas:** `backend/services/gl_service.py:425-439, 666-673, 821`
- **Perilaku baru:** piutang, hutang, persediaan, antar-PT menolak jurnal manual dan pembalikan sepihak; koreksi lewat
  dokumennya; akun yang pernah dipakai tidak bisa dihapus.
- **Selesai bila:** jurnal manual ke akun kontrol → 422 dengan pesan yang menyebut dokumen pengganti; hapus akun
  berjurnal → ditolak.
- **Catatan:** prasyarat asisten keuangan yang boleh menulis jurnal.

### PK-37 — Tanggal buku WIB dan kunci periode untuk dokumen

- **Temuan:** GL-05
- **Keputusan:** K-03 (menahan butir kunci dokumen)
- **Berkas:** `backend/core_utils.py:15-16`, `backend/services/gl_service.py:494`
- **Perilaku baru:** satu fungsi "tanggal buku" (WIB) untuk semua jurnal; bila diputuskan, dokumen, pembayaran, dan
  mutasi stok bertanggal di periode tertutup ditolak.
- **Selesai bila:** tes GL-05 lulus tanpa tanda (transaksi 00:30 WIB tanggal 1 masuk bulan itu).

### PK-38 — Pemisahan tugas dan satu batas wewenang

- **Temuan:** GL-06, FX-10, FX-16, IA-08, IA-12
- **Keputusan:** K-04, K-11, K-14 (menahan)
- **Berkas:** `backend/services/period_unlock_service.py:197-198`, `backend/routers/closing.py:104-109`,
  `backend/services/finance_case_service.py`, `finance_case_playbooks.py`, `so_override_service.py:87-93`,
  `backend/permissions_config.py`, `frontend/src/features/purchasing/makloon/MkoStepModals.jsx`
- **Perilaku baru:** pembuat ≠ penyetuju tanpa pengecualian admin (bila diputuskan); satu batas nominal untuk semua
  pengurang piutang tanpa kas; ganti termin ke yang lebih longgar butuh izin setara pelepasan; nilai tagihan jasa
  makloon diisi pembelian, bukan gudang; izin bayar kontrabon terpisah dari izin setujui.
- **Selesai bila:** tes per kontrol: pelaku yang sama → 403.

### PK-39 — Anggaran

- **Temuan:** FY-10, FY-11, FY-12
- **Keputusan:** K-12 (menahan FY-12)
- **Berkas:** `backend/services/budget_service.py`, `backend/routers/budgets.py`
- **Perilaku baru:** realisasi dari tanggal jurnal; akun persediaan memakai debit penerimaan; komitmen = sisa PO;
  hitung per PT; pagu unik per (PT, tahun, kategori) dengan riwayat ubah.
- **Selesai bila:** PO 100 diterima 40 → realisasi 40, komitmen 60, total 100.

### PK-40 — Pajak: keunikan, masa pajak, basis

- **Temuan:** SL-13, FY-16
- **Keputusan:** K-08 (menahan butir ekspor Coretax/PPh 23)
- **Berkas:** `backend/services/tax_invoice_service.py:142-173`, `backend/services/input_tax_service.py:131-132`,
  `backend/services/tax_center_service.py`
- **Perilaku baru:** satu faktur pajak per pesanan dan nomor seri unik dijamin indeks; rekap difilter di kueri tanpa
  batas 5.000; masa pajak yang sudah dilaporkan terkunci; basis PPh 21 di rekap = basis di jurnal.
- **Selesai bila:** dua terbit bersamaan untuk satu pesanan → satu faktur; rekap 6.000 baris = jumlah jurnal PPN.
- **Catatan:** rancangan konfigurasi faktur pajak ada di [`07_PAJAK_DAN_PEMBAYARAN.md`](07_PAJAK_DAN_PEMBAYARAN.md).

---

## Gelombang 7 — Laporan dan layar

### PK-41 — Laporan pendukung

- **Temuan:** RP-01, RP-03, RP-05, RP-06, RP-07, RP-08, RP-09, RP-11, RP-12
- **Keputusan:** K-16 (menahan RP-03)
- **Berkas:** `backend/services/ar_aging_service.py`, `backend/routers/vendor_bills.py:55-84`,
  `backend/services/cash_flow_service.py`, `profitability_service.py`, `finance_tower_service.py`,
  `cashflow_forecast_service.py`
- **Perilaku baru:** daftar piutang dan hutang menyaring "belum lunas" di kueri tanpa batas diam-diam; umur piutang per
  surat jalan atau per baris rencana (sesuai keputusan); "per tanggal" menyaring transaksi ≤ tanggal itu; klasifikasi
  arus kas per jenis sumber; kolom "belum jatuh tempo" di hutang; profitabilitas dikurangi nota kredit dan punya baris
  rekonsiliasi ke Laba-Rugi; satu fungsi hitung hari.
- **Selesai bila:** sepuluh kasus uji di lampiran kueri bagian C lulus; tes RP-06 lulus tanpa tanda; Total umur piutang
  = saldo akun piutang dengan daftar selisih yang dijelaskan.
- **Catatan:** RP-03 prasyarat blokir kredit di modul piutang lanjut; RP-08 prasyarat angka "kualitas harga" di modul
  insentif.

### PK-42 — Layar: perbaikan cepat per berkas

- **Temuan:** UX-05, UX-09, UX-11, UX-12, UX-18
- **Berkas:** lihat laporan audit §3.6 dan §7
- **Perilaku baru:** tombol buat mati dengan petunjuk saat "Semua Entitas"; galat tampil di dalam pop-up; teks
  peringatan periode diperbarui; daftar berhalaman dengan keterangan jumlah; isian uang berpemisah ribuan; satu
  `fmtDate` WIB.
- **Selesai bila:** tes layar per butir; `scripts/guardrails/verify_error_notice.py` dan `verify_modal_dismiss.py` hijau.

### PK-43 — Layar: struktural

- **Temuan:** UX-08, UX-13, UX-15, UX-16
- **Setelah:** PK-06, PK-19
- **Perilaku baru:** kandidat settlement antar-PT dimuat dari server per pasangan PT, form punya tanggal dan rekening;
  laporan → akun → jurnal → dokumen bisa ditelusuri, buku besar punya filter tanggal; layar piutang punya tombol catat
  bayar; tutup buku punya daftar periksa dan indikator selisih saldo antar-PT.
- **Selesai bila:** (uji jalan dengan rekaman) tiap alur selesai tanpa pindah menu.

### PK-44 — Struktur menu dan jejak dokumen

- **Temuan:** UX-17, IA-04, IA-06, IA-10, IA-11, IA-13, IA-14, IA-15
- **Keputusan:** K-09, K-17 (menahan cakupan peran Finance)
- **Berkas:** `frontend/src/config/navStructure.js`, `hubTabs.js`, `roles.js`, `backend/services/doc_refs_service.py`,
  `frontend/src/AppViewRouter.jsx`, `docs/KN_13`, `KN_14`, `KN_16`
- **Perilaku baru:** struktur menu di [`01_PENGGABUNGAN_MENU.md`](01_PENGGABUNGAN_MENU.md) tahap 1; menu sampai ke
  peran yang punya izin; jejak dokumen menaut ke layar yang ada dan meneruskan fokus; gaji, kas kecil, aset, klaim
  makloon terdaftar sebagai jenis dokumen; satu panel relasi; satu istilah per dokumen; dokumen IA diperbarui.
- **Selesai bila:** `scripts/guardrails/verify_access_catalog_nav.py`, `verify_desk_targets.py`, `verify_page_tabs.py`
  hijau; tiap view lama masih terbuka lewat alias; (uji jalan) tiap tautan jejak dokumen membuka dokumennya.

---

## Prasyarat modul baru

| Modul | Rancangan | Paket yang harus sudah divalidasi | Alasan |
|---|---|---|---|
| Pembayaran dan rekening tujuan | `07` | PK-12, PK-19, PK-20 | Kas satu pintu, rekening wajib, idempotensi |
| Piutang lanjut (plafon, blokir, denda) | `06` | PK-08, PK-19, PK-38 (FX-16), PK-41 (RP-03) | Denda benar; umur piutang yang memblokir harus benar dulu |
| Faktur pajak yang bisa diatur | `07` | PK-40 | Keunikan nomor dan masa pajak |
| Meja insentif | `05` | PK-19, PK-22, PK-41 (RP-08) | Angka pencairan dan retur; slip gaji bisa menerima komponen |
| Komponen gaji dan tunjangan | `09` | PK-22 | Hitung ulang dan void |
| Asisten keuangan — baca | `08` | PK-09, PK-16, PK-17 | Entitas, label gabungan, izin nominal |
| Asisten keuangan — tulis | `08` | PK-05, PK-09, PK-10, PK-12, PK-18, PK-36 | Pintu yang dipanggil asisten harus sudah aman untuk diulang |
| Penggabungan menu tahap 1 | `01` | — (boleh kapan saja; hanya konfigurasi) | — |

## Paket yang tertahan keputusan pemilik

| Paket | Keputusan | Yang tertahan |
|---|---|---|
| PK-04 | izin ubah `deploy/backup.sh` | seluruhnya |
| PK-16 | K-15 | hanya pemakaian mesin konsolidasi untuk mode gabungan |
| PK-17 | K-18 | butir IA-01 |
| PK-22 | K-13, K-22 | FY-02, FY-08 |
| PK-24 | K-17 | IA-05 |
| PK-26 | K-05 | seluruhnya |
| PK-29 | K-06 | butir true-up |
| PK-30 | K-07 | IC-02 |
| PK-31 | K-10 | persentase kepemilikan |
| PK-32 | K-14 | FX-15 |
| PK-34, PK-35 | K-01 | seluruhnya |
| PK-36 | K-02 | seluruhnya |
| PK-37 | K-03 | kunci dokumen |
| PK-38 | K-04, K-11, K-14 | seluruhnya |
| PK-39 | K-12 | FY-12 |
| PK-40 | K-08 | ekspor Coretax, PPh 23 |
| PK-41 | K-16 | RP-03 |
| PK-44 | K-09, K-17 | cakupan peran Finance |
| PK-45 | K-28 | butir CR-01 |
| PK-46 | K-42 | seluruhnya |

Paket yang tidak ada di tabel ini tidak butuh keputusan dan bisa dimulai setelah PK-01 dan PK-02.
