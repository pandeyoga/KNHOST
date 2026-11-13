# Rancangan — Faktur pajak yang bisa diatur, dan cara bayar + rekening tujuan yang jelas

Status: rancangan untuk diputuskan pemilik. Belum ada kode. Kode dibaca di `9834947`; butir bertanda ✔ dicek langsung
pada berkas:baris yang disebut.

Dua topik ini satu dokumen karena bertemu di titik yang sama: dokumen yang diterima pelanggan (konfirmasi pesanan,
faktur) harus menyebut dengan benar **berapa**, **pajaknya bagaimana**, **dibayar ke mana**, dan **dengan kode apa**.

---

## Bagian A — Cara bayar dan rekening tujuan

### A0. Ringkasan

- **Temuan utama:** pesanan tidak menyimpan cara bayar maupun rekening tujuan; dokumen untuk pelanggan tidak mencetak
  rekening; kwitansi tidak mencatat uang masuk ke rekening mana. Artinya dari pesanan sampai rekonsiliasi, **tidak ada
  satu titik pun di sistem yang tahu uang seharusnya dan sebenarnya masuk ke rekening mana**. Rekening disampaikan sales
  di luar sistem. Itulah celah salah-orang yang dirasakan pemilik.
- **Mengapa pembayaran di marketplace andal:** tiga hal — setiap tagihan punya **pengenal unik**, **nominalnya pasti**,
  dan ada **batas waktu** dengan **bukti dari bank**, bukan dari pengakuan pembeli. Ketiganya bisa ditiru tanpa
  payment gateway.
- **Usulan:** (1) satu daftar induk cara bayar; (2) rekening bank punya peruntukan dan bawaan per PT; (3) pesanan
  menyimpan cara bayar + rekening tujuan dan dokumennya mencetak **instruksi bayar** dengan **kode bayar**;
  (4) kwitansi wajib menyebut rekening dan nomor referensi; (5) status "tercatat" dibedakan dari "terverifikasi bank".
  Virtual account dan QRIS dinamis adalah tahap berikutnya bila pemilik menghendaki.

### A1. Keadaan sekarang

| Langkah | Yang terjadi | Bukti |
|---|---|---|
| Pesanan | Sales hanya memilih **termin**. Tidak ada field cara bayar atau rekening | `backend/routers/sales_orders.py:591-676` |
| Dokumen ke pelanggan | PDF mencetak termin dan status bayar; kop per PT tanpa data bank. Rekening hanya bisa diketik di teks penutup per jenis dokumen — sama untuk semua PT | `backend/services/pdf_resolvers.py:293-297`; `pdf_service.py:151-158, 233-250` |
| Uang masuk | Ke rekening mana pun | — |
| Kwitansi | Finance memilih metode, tanggal, alokasi. **Tidak** memilih rekening; nomor referensi bank masuk kolom catatan; di server metode adalah teks bebas (bawaan "transfer") | `frontend/src/features/crm/ARReceiptModal.jsx:28-33, 146, 303`; `backend/services/ar_receipt_service.py:439` |
| Kas | Transaksi kas dibuat **tanpa rekening**; tunai → kas kecil, selain itu → "kas besar" ✔ | `backend/services/ar_receipt_service.py:56-98` |
| Rekonsiliasi | Kwitansi menjadi kandidat cocok untuk mutasi rekening **mana pun**; setelah dicocokkan, rekening di transaksi kas tetap kosong | `backend/services/bank_recon_service.py:503-521, 640-651` |
| Salah transfer | Ditangani sesudah kejadian lewat Kasus Keuangan (salah rekening, rekening pribadi karyawan, salah entitas, dana tak dikenal) | `backend/services/finance_case_playbooks.py:49-205` |

### A2. Temuan tambahan

| ID | Tingkat | Temuan | Bukti | Ditutup oleh |
|---|---|---|---|---|
| PM-01 | Tinggi | Pesanan dan dokumen pelanggan tidak memuat cara bayar, rekening tujuan, atau instruksi bayar | Lihat A1 | PM-T2 |
| PM-02 ✔ | Tinggi | Kwitansi tidak mencatat rekening; metode teks bebas; nomor referensi tidak wajib (memperluas SL-11) | `ar_receipt_service.py:56-98, 439` | PK-20, PM-T3 |
| PM-03 | Sedang | Sedikitnya enam kosakata metode yang tidak sama: profil pelanggan (tunai/tempo/dp/bertahap/kontan), jenis termin (cash/credit/dp/installment), kwitansi (transfer/cash/giro/qris), faktur supplier (transfer/tunai/giro), kontrabon (transfer/giro/cash), uang muka karyawan (tunai/transfer) | `features/crm/crmUtils.jsx:58-64`; `services/config_service.py:149-160`; form masing-masing | PM-T1 |
| PM-04 | Sedang | Rekonsiliasi tidak membatasi kandidat ke rekening yang sama dan tidak mengisi rekening setelah cocok | `bank_recon_service.py:503-521, 640-651` | PM-T3 |
| PM-05 ✔ | Sedang | Master rekening tanpa atas nama, peruntukan, bawaan, atau tanda "tampil di dokumen". Fungsi "rekening satu-satunya" menyaring field `status`, padahal master memakai `is_active` — rekening nonaktif ikut terhitung | `schemas_finance.py:9-18`; `bank_service.py:55, 177` | PM-T1 |
| PM-06 | Sedang | Tunai yang diterima sales di lapangan tidak punya alur titipan dan setoran. Sales **bisa** mencatat kwitansi dari HP (izin `ar_receipt.create` diberikan saat server dinyalakan, `bootstrap.py:425, 460`, walau `permissions_config.py:142` menulis hanya lihat — temuan PR-14); kwitansi tunai langsung tercatat sebagai kas kecil padahal uang masih di tangan sales | `features/sales/mobile/MobileArReceipt.jsx`; `backend/bootstrap.py:425, 460` | PM-T4, K-36 |

### A3. Rancangan

#### 1) Daftar induk cara bayar

Satu daftar untuk seluruh sistem (penerimaan, pembayaran supplier, gaji, kas kecil), bisa diaktifkan per PT:

| Kode | Butuh rekening | Butuh nomor referensi | Catatan |
|---|---|---|---|
| Transfer bank | Ya | Ya | — |
| Tunai | Kas (kasir/kas kecil) | Tidak | Di lapangan: lewat titipan sales (PM-T4) |
| Giro / cek | Ya | Nomor giro + tanggal jatuh tempo | Status: diterima → cair / ditolak; piutang baru turun saat cair (K-20) |
| QRIS | Ya | Nomor transaksi | — |
| Virtual account | Ya | Otomatis | Tahap 2 |
| Kartu / EDC | Ya | Nomor jejak | Bila dipakai |
| Titipan / saldo kredit | Tidak | — | Bukan uang masuk baru |

"Termin" (tunai, tempo 30 hari, DP 30 %, cicilan) tetap konsep terpisah: termin menjawab **kapan**, cara bayar
menjawab **lewat apa**. Kosakata lama di tiap layar dipetakan ke daftar ini; penjaga `verify_payment_vocab.py` mencegah
kosakata baru muncul (aturan D8 di `04`).

#### 2) Rekening bank dengan peruntukan

Tambahan pada master rekening (`bank_accounts`):

| Field | Guna |
|---|---|
| Atas nama | Dicetak di instruksi bayar; harus nama PT pemilik |
| Peruntukan | Penerimaan pelanggan · Pembayaran supplier · Gaji · Operasional (boleh lebih dari satu) |
| Cara bayar yang dilayani | Mis. rekening A: transfer + QRIS; rekening B: giro |
| Bawaan penerimaan | Satu per (PT, cara bayar); boleh ditimpa per pelanggan atau per kanal penjualan |
| Tampil di dokumen | Ya / tidak |
| Akun buku besar | Satu akun per rekening, lewat pemetaan |

Membuat atau mengubah rekening memerlukan persetujuan orang kedua, karena rekening yang salah di dokumen berarti uang
pelanggan terkirim ke tempat yang salah.

#### 3) Pesanan menyimpan cara bayar dan rekening tujuan

Di checkout, setelah termin:

```text
Cara bayar      [ Transfer bank ▾ ]        ← hanya yang aktif di PT ini
Rekening tujuan [ BCA 123-456-7890 a.n. PT Kain Suka Cita ]   ← terisi dari bawaan; bisa diganti
                                                                hanya ke rekening penerimaan PT yang sama
```

- Sales **memilih dari daftar**, tidak mengetik. Bila hanya ada satu rekening penerimaan untuk cara bayar itu, isian
  terkunci.
- Rekening dari PT lain tidak mungkin terpilih: daftar disaring oleh PT pesanan.
- Pilihan tersimpan di pesanan dan diwariskan ke tiap **baris tagihan** (rancangan `06` §3.2).

#### 4) Instruksi bayar dan kode bayar

Setiap baris tagihan punya **kode bayar**: pendek, unik, mudah diketik di berita transfer (mis. `KN-7F3K2`).

Blok ini tercetak otomatis di Konfirmasi Pesanan dan Faktur, dan tersedia sebagai teks siap tempel ke WhatsApp:

```text
Pembayaran untuk pesanan SO-KSC-000123
Jumlah        : Rp 12.345.000
Jatuh tempo   : 15 Des 2026
Transfer ke   : BCA 123-456-7890 a.n. PT Kain Suka Cita
Berita/kode   : KN-7F3K2
```

Teks rekening tidak lagi diketik di templat PDF; ia berasal dari master. Templat lama yang memuat nomor rekening
ketikan dibersihkan saat peralihan.

Untuk pesanan tunai/bayar-dulu, pemilik bisa mengaktifkan **nominal unik** (tiga digit terakhir berbeda per tagihan)
sebagai pembeda tambahan. Ini pembeda sekunder; pengenal utamanya tetap kode bayar (K-35).

#### 5) Kwitansi: rekening dan referensi wajib

| Field | Aturan |
|---|---|
| Cara bayar | Dari daftar induk |
| Rekening penerima | Wajib untuk non-tunai; bawaan = rekening tujuan tagihan; hanya rekening PT kwitansi |
| Nomor referensi | Wajib untuk transfer, giro, QRIS |
| Bukti | Lampiran (foto/berkas) — opsional per PT |
| Berbeda dari instruksi | Bila rekening yang dipilih ≠ rekening tujuan tagihan, layar menandai "tidak sesuai instruksi" dan meminta catatan |

Form yang sama dipakai dari semua tempat (Meja Finance, pusat Piutang, detail pesanan, HP). Ini "satu form pembayaran"
di `01` §3.

#### 6) Dua tingkat status uang masuk

| Status | Arti | Siapa |
|---|---|---|
| **Tercatat** | Kwitansi dibuat berdasarkan bukti dari pelanggan | Finance |
| **Terverifikasi bank** | Kwitansi sudah dicocokkan dengan mutasi di rekening yang sama | Rekonsiliasi (otomatis atau manual) |

- Rekonsiliasi hanya menawarkan kwitansi dengan **rekening yang sama** dengan mutasi; kode bayar di berita transfer
  menjadi kunci cocok pertama, lalu nominal persis + pelanggan. Cocok sempurna boleh otomatis; sisanya antrean manual.
- Uang masuk yang tidak dikenal tetap menjadi titipan bank; lebih bayar menjadi titipan pelanggan.
- Daftar "tercatat tetapi belum terverifikasi > N hari" tampil di beranda keuangan. Pemilik bisa memutuskan apakah
  tahan-kirim untuk pesanan bayar-dulu menunggu "terverifikasi" atau cukup "tercatat".

#### 7) Tunai di lapangan (bila diizinkan — K-36)

Sales mencatat **penerimaan titipan**: uang diakui sebagai "kas di tangan sales" (piutang karyawan), pelanggan menerima
tanda terima bernomor, dan piutang pelanggan turun. **Setoran** ke kasir atau bank menutup titipan itu. Batas nominal
dan tenggat setor per PT; titipan yang lewat tenggat tampil di daftar kerja keuangan. Sampai alur ini ada, kwitansi
tunai yang dicatat sales tetap berperilaku seperti hari ini (langsung kas kecil).

#### 8) Tahap 2 — virtual account dan QRIS dinamis (opsional)

Bila volume membenarkan: nomor virtual account **per pelanggan** (cocok untuk pembayaran gabungan beberapa pesanan)
dari bank atau penyedia; pemberitahuan dari server penyedia membuat kwitansi berstatus terverifikasi secara otomatis.
Syarat teknisnya sudah tercakup aturan `04`: penerima pemberitahuan harus idempoten, memeriksa tanda tangan, dan
mengonfirmasi ulang status ke penyedia. Biaya dan syarat tiap bank belum saya periksa.

#### 9) Sisi keluar (bayar supplier, gaji)

Prinsip yang sama: rekening sumber dipilih dari daftar ber-peruntukan (PK-05 untuk supplier; PY-11 untuk gaji — sekarang
gaji selalu keluar dari akun 1-1100). Rekening **supplier** didaftarkan di master supplier, dan perubahannya butuh
persetujuan orang kedua.

### A4. Tahap bangun

| Tahap | Isi | Prasyarat | Selesai bila |
|---|---|---|---|
| PM-T1 Induk | Daftar cara bayar; field baru rekening; bawaan per PT; pemetaan kosakata lama; perbaikan saringan `is_active` | — | Tiap layar yang punya pilihan metode membaca daftar yang sama; penjaga kosakata hijau |
| PM-T2 Pesanan dan dokumen | Cara bayar + rekening tujuan di pesanan; kode bayar per baris tagihan; blok instruksi di PDF dan teks WhatsApp | PM-T1; CR-T2 (jadwal tagihan) untuk pesanan tempo — pesanan tunai/DP bisa lebih dulu | Pesanan PT-A tidak bisa menyimpan rekening PT-B; PDF mencetak rekening dari master; kode bayar unik (indeks) |
| PM-T3 Kwitansi dan rekonsiliasi | Rekening + referensi wajib; satu form; status terverifikasi; kandidat rekonsiliasi per rekening; cocok lewat kode bayar | PK-19, PK-20, PK-21, PM-T2 | Kas dari kwitansi selalu ber-rekening; mutasi rekening A tidak menawarkan kwitansi rekening B; transfer dengan kode bayar benar → cocok otomatis |
| PM-T4 Titipan sales | Penerimaan titipan, setoran, batas dan tenggat | K-36, PM-T3 | Titipan belum disetor tampil sebagai piutang karyawan, bukan kas |
| PM-T5 VA / QRIS | Integrasi penyedia | K-35 | Diputuskan terpisah |

---

## Bagian B — Faktur pajak

### B0. Ringkasan

- **Yang sudah bisa diatur:** tarif PPN, sakelar DPP nilai lain, harga termasuk/belum PPN, status PKP per PT — semuanya
  per PT lewat Pusat Pengaturan atau master badan usaha.
- **Yang belum:** atribut pajak per pelanggan selain NPWP, atribut pajak per barang, kapan faktur terbit, kode transaksi
  bawaan, pembulatan, dan faktor DPP nilai lain (11/12 ditulis mati).
- **Dua cacat yang harus dipastikan dulu** karena menyangkut angka pelaporan: faktur pengganti tampaknya membuat PPN
  keluaran terhitung dua kali di rekap (TX-01), dan pesanan non-PPN bisa dibuat lewat API tanpa izin khusus di PT yang
  PKP (TX-04).
- Hal yang menyangkut peraturan pajak di dokumen ini berasal dari pemahaman umum saya dan **belum dicocokkan dengan
  teks peraturan**; wajib dikonfirmasi konsultan pajak sebelum dibangun.

### B1. Keadaan sekarang

| Aspek | Bisa diatur? | Di mana | Yang kurang |
|---|---|---|---|
| Tarif PPN | Ya, per PT | `tax.ppn_rate` | Satu tarif per pesanan |
| DPP nilai lain | Sakelar per PT | `tax.dpp_nilai_lain` | Faktor 11/12 ditulis mati (`config_service.py:285`; `interco_tax_service.py:70`) |
| Harga termasuk / belum PPN | Ya, per PT | `tax.ppn_mode` | Tidak per pelanggan atau per pesanan |
| Status PKP | Di master badan usaha; menimpa tarif menjadi 0 | `business_entities.default_tax_mode` | Dua sumber dengan `tax.efaktur_enabled` |
| Pesanan tanpa PPN | Lewat field `tax_override = "non_ppn"` di API pesanan ✔ | `routers/sales_orders.py:308`; `schemas.py:542` | Tanpa izin khusus; tidak ada di layar checkout |
| Pembulatan | Tidak | Dua desimal di tingkat pesanan | Ditulis mati |
| Data pajak pelanggan | Hanya `npwp` (teks bebas) | Form pelanggan | Tanpa NIK, status PKP, kode transaksi bawaan, alamat pajak; NPWP kosong hanya peringatan |
| Data pajak barang | Tidak ada | — | — |
| Kode transaksi | Dipilih per faktur dari daftar 01–04, 06–09; bawaan 04 bila DPP nilai lain, selain itu 01 | `tax_invoice_service.py:17, 140` | Daftar dan bawaan ditulis mati |
| Nomor | Nomor internal `FKT-` per PT; NSFP diketik menyusul | `tax_invoice_service.py:28-29, 167-179` | SL-13 |
| Saat terbit | Manual, sejak pesanan dikonfirmasi; **satu faktur untuk seluruh pesanan** | `tax_invoice_service.py:15-16, 134-164` | Tidak per surat jalan atau per uang muka, padahal jurnal PPN dibuat per surat jalan |
| Pengganti / batal | Ada | `tax_invoice_service.py:182-248` | TX-01, TX-02, TX-03 |
| Nota kredit ↔ faktur | Tidak terhubung | — | Retur tidak menghasilkan dokumen pajak |
| Ekspor | CSV umum + cetak | Pusat Export | Tanpa format impor Coretax (SL-13, K-08) |

### B2. Temuan tambahan

| ID | Tingkat | Temuan | Bukti | Ditutup oleh |
|---|---|---|---|---|
| TX-01 ✔ (dijalankan 13 Nov: rekap 110.000 → 220.000) | Tinggi | Saat faktur pengganti dibuat, faktur asli hanya diberi `replaced_by_id`; statusnya tetap. Rekap PPN menyaring `status ≠ batal` saja, sehingga asli dan pengganti sama-sama terjumlah bila berada di masa yang sama | `services/tax_invoice_service.py:182-225`; `services/input_tax_service.py:125-134` | PK-45 (tes dulu, lalu perbaiki) |
| TX-02 ✔ | Sedang | Kunci amandemen pesanan mencari faktur dengan `status ≠ "cancelled"`, sedangkan faktur batal berstatus `"batal"` — pesanan tetap terkunci setelah fakturnya dibatalkan | `services/amendment_service.py:277-278`; `tax_invoice_service.py:236-248` | PK-45 |
| TX-03 ✔ | Tinggi | Ubah NSFP, ganti, dan batal faktur hanya memeriksa izin, tidak mengadu entitas faktur dengan cakupan pengguna (kelas IC-05) | `routers/tax_invoices.py:61-88` | PK-45 |
| TX-04 ✔ | Tinggi | Pesanan non-PPN bisa dibuat dengan mengirim `tax_override` lewat API tanpa izin khusus | `routers/sales_orders.py:308, 616`; `schemas.py:542` | PK-45 |
| TX-05 | Sedang | Faktur per pesanan dan manual; tidak terikat surat jalan, uang muka, maupun retur | Lihat B1 | TX-T2, K-32 |
| TX-06 | Sedang | Faktor DPP nilai lain, pembulatan, daftar dan bawaan kode transaksi ditulis mati; tanpa data pajak pelanggan dan barang | Lihat B1 | TX-T1 |

### B3. Rancangan

#### 1) Pengaturan pajak per PT (bertanggal berlaku)

| Pengaturan | Isi |
|---|---|
| Status PKP | Satu sumber (master badan usaha); `tax.efaktur_enabled` diturunkan darinya |
| Tarif PPN dan faktor DPP nilai lain | Tabel bertanggal berlaku, bukan angka tunggal — perubahan tarif tidak mengubah dokumen lama |
| Harga termasuk / belum PPN | Bawaan PT; boleh ditimpa per pelanggan |
| Pembulatan | Per baris atau per dokumen; ke rupiah penuh atau dua desimal |
| Kode transaksi bawaan | Aturan: menurut jenis pelanggan dan dasar pengenaan |
| Saat faktur terbit | Per surat jalan · per penerimaan uang muka · per pesanan · gabungan bulanan (K-32) |
| Siapa boleh membuat pesanan non-PPN | Izin khusus + alasan |

Setiap pesanan dan faktur menyimpan **potret** pengaturan yang dipakai (tarif, faktor, mode), sehingga bisa dijelaskan
kemudian.

#### 2) Data pajak pelanggan

NPWP (divalidasi bentuknya) atau NIK; nama dan alamat sesuai dokumen pajak (bisa berbeda dari alamat kirim); status PKP;
kode transaksi bawaan; "selalu butuh faktur pajak" ya/tidak. Pesanan ber-PPN untuk pelanggan yang datanya belum lengkap
masuk antrean "lengkapi data pajak", bukan terbit dengan data kosong.

#### 3) Data pajak barang (hanya bila ada barang/jasa dengan perlakuan berbeda — K-33)

Perlakuan PPN per barang/jasa (kena · dibebaskan · tidak dipungut), dan kode barang bila ekspor Coretax memerlukannya.

#### 4) Daur hidup faktur

```text
Pemicu (surat jalan / uang muka / pesanan)  →  DRAF otomatis  →  TERBIT (nomor internal; NSFP menyusul)
        →  DIGANTI (asli berstatus "diganti", tidak ikut rekap)   atau   BATAL (alasan)
Retur / nota kredit  →  DOKUMEN PAJAK RETUR tertaut ke faktur asal
```

- Faktur lahir sebagai draf dari pemicu yang dipilih PT; Finance memeriksa dan menerbitkan. Tidak ada lagi "lupa
  menerbitkan" karena antreannya terisi sendiri.
- Faktur yang diganti keluar dari rekap (menutup TX-01). Faktur batal melepas kunci amandemen (TX-02).
- Semua aksi mengadu entitas (TX-03) dan terdaftar idempoten.
- Masa pajak yang sudah dilaporkan dikunci (PK-40).
- **Pencocokan wajib:** Σ PPN pada faktur terbit per PT per masa = mutasi akun PPN Keluaran; selisih ditampilkan dengan
  daftar penyebab (surat jalan tanpa faktur, faktur tanpa jurnal). Menjadi invarian di `verify_data_integrity.py`.

#### 5) Ekspor dan PPh

Format impor Coretax dan PPh 23 + bukti potong menunggu K-08. Rancangan di atas menyiapkan datanya (data pajak
pelanggan, kode transaksi, potret tarif) sehingga ekspor tinggal memetakan kolom.

### B4. Tahap bangun

| Tahap | Isi | Prasyarat | Selesai bila |
|---|---|---|---|
| (PK-45) | TX-01…04: perbaikan cepat | — | Lihat `02` |
| TX-T1 Pengaturan dan data | Tabel tarif/faktor bertanggal; pembulatan; aturan kode transaksi; data pajak pelanggan (dan barang bila K-33 ya); potret di dokumen | PK-40 | Mengubah tarif untuk bulan depan tidak mengubah faktur bulan ini; pesanan non-PPN tanpa izin → 403 |
| TX-T2 Pemicu dan daur hidup | Draf otomatis dari pemicu pilihan PT; status "diganti"; dokumen pajak retur; pencocokan faktur ↔ akun PPN | TX-T1, K-32, PK-32 (nota kredit) | Tiap surat jalan ber-PPN punya tepat satu faktur atau satu baris di antrean; rekap PPN = mutasi akun PPN Keluaran |
| TX-T3 Ekspor | Format impor Coretax; PPh 23 dan bukti potong | K-08 | Diputuskan terpisah |

### B5. Hal yang harus dikonfirmasi konsultan pajak

1. Saat faktur pajak wajib dibuat untuk tiap pola penjualan Anda (kirim bertahap, uang muka, tukar faktur).
2. Dokumen pajak yang benar untuk retur dan untuk koreksi harga.
3. Faktor DPP nilai lain dan kode transaksi yang berlaku untuk barang Anda.
4. Perlakuan pelanggan tanpa NPWP.
5. Tabel TER PPh 21 di kode (lihat PY-03 di [`09`](09_HR_DAN_PAYROLL.md)).
