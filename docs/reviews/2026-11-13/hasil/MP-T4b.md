# MP-T4b — Jurnal makloon: hutang jasa saat faktur mitra dicocokkan, hasil klaim per keadaan roll, borongan per SPK

- Commit awal: `168914a`        - Commit akhir: `cc6f0d8` · `90f77a7` (perbaikan gate)        - Branch: `claude/nifty-carson-jjx3c8`
- Spesifikasi `docs/blueprint/unit/MP-T4b.md`; keputusan K-63, K-64, K-68 dengan jawaban pemilik 16 Nov **K-78…K-81**
  (GR/IR 2-1150 · klaim mengurangi persediaan · sakelar per PT bawaan cara lama · borongan sekali di langkah terakhir).
- Butir MP-T4 lain (teruskan mitra→mitra, hasil akhir saja, validasi klaim saat diajukan, tolak klaim tidak menutup SPK,
  QC tolak membuka klaim) sudah selesai di MP-T4a.

## Cek ulang di HEAD
- `makloon_order_service.receive_step` dan `record_service_step` membuat `vendor_bills` jasa berstatus `posted` lalu
  `posting_registry.post_makloon_step` → `gl.post_subcon_service` (Dr 1-1350 + Dr 1-1500 / Cr 2-1100).
- `makloon_claim_service.approve_claim` → `gl.post_makloon_claim`: potong bon Dr 2-1100 / Cr 4-9200 walau roll di stok;
  tagih ganti Dr 1-1260 / Cr 4-9200.
- Kontrak basis `lot` dihitung `1 × tarif` (`contract_service.compute_tariff`) di **setiap** langkah yang memakainya —
  SPK dua langkah satu kontrak borongan Rp 2.500.000 merencanakan jasa Rp 5.000.000 (uji U6 merah sebelum kode).
- Akun yang dipakai sudah ada di bagan akun: 2-1150 GR/IR, 1-1300, 1-1350, 1-1500, 2-1100, 1-1260, 4-9200. Tidak ada
  akun baru.

## Perubahan

### Sakelar per PT (K-80)
`makloon.jasa_jadi_hutang` (Pengaturan › Pembelian › Makloon, "Jasa makloon menjadi hutang"): `saat_terima` (bawaan =
cara lama, tidak ada yang berubah) · `saat_faktur`. Wajib alasan, risiko tinggi, izin modul makloon. Mode **dipotret di
tagihan** (`vendor_bills.ap_mode`) saat lahir, sehingga ulang posting tidak berubah walau sakelar diganti kemudian.
Menyalakan untuk PT nyata = H5 (keputusan pemilik), tidak dilakukan di sini.

### Mode `saat_faktur` (K-63, K-78)
- Terima hasil / catat jasa → tagihan `awaiting_invoice`, PPN 0, langkah `service_invoice_status = menunggu_faktur`;
  jurnal **Dr WIP 1-1350 / Cr GR/IR 2-1150** sebesar nilai jasa.
- `POST /api/makloon-orders/{id}/steps/{seq}/service-invoice` (izin `vendor_bill.create`, sama dengan pengisi nilai
  tagihan jasa PK-38): no. faktur wajib, nilai jasa di faktur harus sama dengan nilai tagihan sesudah potongan klaim
  (toleransi Rp 1) — selisih ditolak dengan pesan "Selesaikan selisihnya dulu — ubah tarif atau ajukan klaim"; periode
  buku diperiksa. Tagihan → `posted` (masuk hutang, bisa dibayar), total = nilai + PPN; jurnal
  **Dr 2-1150 + Dr PPN Masukan 1-1500 / Cr Hutang 2-1100** (`subcon_service_invoice`, lewat pintu tahan-gagal
  `durable_makloon_step`, terdaftar di `posting_registry.KINDS`).
- Layar: rincian SPK › Tagihan jasa — lencana "Menunggu faktur", tombol "Cocokkan faktur" (pemegang `vendor_bill.create`),
  pop-up isian faktur. Status `awaiting_invoice` masuk kosakata status ("Menunggu faktur", nada peringatan).

### Klaim (K-64, K-79) — hanya di mode `saat_faktur`
Nilai klaim dibagi ke roll hasil langkah (roll asli + potongannya) menurut panjang awal: tarif = klaim ÷ Σ panjang awal.
Roll masih di stok → **Cr Persediaan 1-1300** dan `unit_cost` roll turun (riwayat biaya roll + `claim_refs`, idempoten,
dibatalkan bila jurnal gagal); roll di mitra (`subcon`) → Cr 1-1350; roll sudah keluar/terjual → Cr 4-9200. Sisi debit
potong bon: 2-1150 bila faktur belum dicocokkan (tagihan dikurangi, tetap menunggu faktur), 2-1100 bila sudah. Mode cara
lama tidak berubah.

### Borongan (K-81) — tanpa sakelar
Kontrak basis `lot` yang sama di beberapa langkah SPK: langkah sebelumnya tarif 0 dengan catatan "Borongan {kontrak}:
ditagih sekali di langkah {n}.", langkah terakhir tarif penuh; rencana jasa SPK = satu tarif. Saat terima/teruskan
langkah non-terakhir tidak ada tagihan (jejak tarif bersumber `borongan`). Ganti mitra/kontrak langkah: kelompok
dibentuk ulang; bila langkah penagih keluar, tagihan pindah ke langkah terakhir yang tersisa (ditolak 409 bila langkah
itu sudah berjalan).

## Contoh hitungan tangan (sama dengan uji)
- Terima 190 yd × Rp 5.000 = **Rp 950.000** → Dr 1-1350 950.000 / Cr 2-1150 950.000.
- Faktur mitra Rp 950.000 + PPN 11 % = 104.500 → Dr 2-1150 950.000 + Dr 1-1500 104.500 / Cr 2-1100 **1.054.500**.
  Saldo 2-1150 dari tagihan ini = 950.000 − 950.000 = 0.
- Klaim potong bon Rp 1.000.000 atas hasil 200 yd → Rp 5.000/yd. Roll A 100 yd di gudang @ Rp 30.000 → turun
  100 × 5.000 = Rp 500.000 (biaya 30.000 → 25.000) → Cr 1-1300 500.000. Roll B 100 yd sudah terkirim ke pelanggan →
  Cr 4-9200 500.000. Faktur belum dicocokkan → Dr 2-1150 1.000.000; tagihan 2.000.000 → 1.000.000.
- Borongan Rp 2.500.000 dipakai langkah 1 dan 2 → rencana langkah 1 Rp 0, langkah 2 Rp 2.500.000, rencana jasa SPK
  Rp 2.500.000 (sebelumnya Rp 5.000.000).

## Uji penerimaan
Lapis B (`backend/tests_mem/test_MPT4b_jurnal_makloon.py`) — merah sebelum kode (fungsi/akun belum ada; U6 `[2500000,
2500000] != [0, 2500000]`):

| ID | Hasil |
|---|---|
| U1 | lulus — jurnal jasa mode faktur Dr 1-1350 / Cr 2-1150 950.000 |
| U2 | lulus — jurnal faktur Dr 2-1150 950.000 + 1-1500 104.500 / Cr 2-1100 1.054.500 |
| U3 | lulus — klaim mode faktur: Cr 1-1300 500.000 + Cr 4-9200 500.000, Dr 2-1150; biaya roll A 25.000; tagihan 1.000.000 tetap menunggu faktur |
| U4 | lulus — klaim sesudah faktur dicocokkan: Dr 2-1100 |
| U5 | lulus — mode cara lama: Dr 2-1100 / Cr 4-9200, biaya roll tidak berubah |
| U6 | lulus — borongan [0; 2.500.000], rencana 2.500.000; ganti kontrak langkah 2 → tagihan pindah ke langkah 1 |
| U7 | lulus — API cocokkan faktur: nilai beda 400; cocok 200, tagihan posted 2.220.000, jurnal benar; ulang 409 |

Lapis A, MongoDB asli (`backend/tests/test_bp_MPT4b_grir_makloon.py`; PT KSC disetel `saat_faktur` selama uji lalu
dikembalikan `saat_terima`):

| ID | Hasil |
|---|---|
| U8 (spek U3) | lulus — terima hasil (jalur teruskan; KSC memakai mode Kedatangan): tagihan `awaiting_invoice`, jurnal Dr 1-1350 / Cr 2-1150 950.000, belum ada hutang; sesudah faktur → posted 1.054.500, jurnal faktur benar, saldo 2-1150 tagihan = 0 |
| U9 (spek U2) | lulus — mitra ujung-ke-ujung satu kontrak borongan: rencana [0; 2.500.000]; teruskan langkah 1 tanpa tagihan jasa (jejak `borongan`) |

Spek U1 (teruskan A→B) dan U4 (klaim, roll di stok) ditutup MP-T4a (`test_bp_MPT4a_teruskan.py`) dan U3 lapis B di atas.

Uji lama terdampak (default mode tidak berubah): MPT2, MPT4a (klaim), PK18, PK37, PK38, PK44, KPT4a — **107 lulus**;
KFT1 (`MPT4B_KUNCI = 1` di U04) + KFT8 — **524 lulus, 2 xfail**; lapis A MPT4a + MPT5 — **5 lulus**. Penjaga:
`verify_config_text` 0, `verify_config_fallback` 0, INV-POST-01 (setelah `post_subcon_service_invoice` didaftarkan) hijau,
`verify_codebase_map` hijau (peta dihasilkan ulang); `verify_ui_standard` tidak ada pelanggaran di berkas unit ini (100
pelanggaran yang tampil = garis dasar). Jest kosakata status: 4 suite / 22 uji lulus; `fix8StandarUi2.test.js` gagal
dimuat karena modul `@radix-ui/primitive/is-development` tidak ada di node_modules lingkungan uji (bukan kode unit ini).

## Gate
`gate.sh --ci` sekali sesudah unit: putaran pertama 1 pelanggaran baru terhadap garis dasar R0 — INV-ATOMIC-01, endpoint
`POST /makloon-orders/{id}/steps/{seq}/service-invoice` menulis `vendor_bills` + `makloon_orders` tanpa tercatat di
REVIEWED. Tulisan induk memang sudah CAS (tagihan `awaiting_invoice` → `posted`, `modified_count` 0 → 409); bentuknya
dirapikan supaya dikenali penjaga dan dicatat `service_cas` (`90f77a7`). Putaran konfirmasi: **tidak ada pelanggaran
baru**; gate tetap merah seperti garis dasar (38 pemeriksaan FAIL). Log `docs/blueprint/garis-dasar-gate/2026-11-16_MPT4b_gate_ci.log`.

## Cek layar (`bukti/MP-T4b/uji_jalan_cocokkan_faktur.js`, data dari `siapkan_spk_menunggu_faktur.py`)
Admin, 1280 px: tagihan "VBM-… Rp 950.000 · Menunggu faktur · Cocokkan faktur" (`1280-01-menunggu-faktur.png`);
nilai 900.000 ditolak dengan pesan selisih (`1280-02-nilai-beda-ditolak.png`); isian 950.000 + PPN 104.500, "Total hutang:
Rp 1.054.500" (`1280-03-faktur-diisi.png`); sesudah dicocokkan tagihan Rp 1.054.500 tanpa lencana
(`1280-04-sesudah-cocok.png`). Baris tagihan semula satu baris dan nominal terpotong di kolom sempit — disusun ulang dua
baris.

## Asumsi dan catatan
- ASUMSI: satu faktur mitra yang mencakup beberapa langkah/SPK dicocokkan per tagihan (nilai jasa per langkah); nomor
  faktur yang sama boleh dipakai di beberapa tagihan.
- ASUMSI: di mode `saat_faktur` PPN saat terima diabaikan (PPN datang bersama faktur).
- ~~CATATAN: GR/IR jasa makloon masuk baris "tidak terhubung ke PO"~~ — ditutup di bagian K-82 di bawah.
- CATATAN: klaim yang sudah disetujui tidak dihitung ulang. Mode klaim diambil dari tagihan jasa langkahnya (`ap_mode`);
  tagihan lama tanpa `ap_mode` atau langkah tanpa tagihan memakai sakelar PT saat klaim disetujui.
- ~~H5: sakelar untuk PT nyata dinyalakan pemilik~~ — dijawab K-82 (semua PT), lihat bagian di bawah.

## K-82 — semua PT "saat faktur" + celah ditutup (pemilik 16 Nov: "ya nyalakan semua pt, sisakan celah bereskan")

### Perubahan
- **Semua PT:** bawaan registri `makloon.jasa_jadi_hutang` diubah `saat_terima` → **`saat_faktur`**, cadangan kode
  `makloon_ap_service.ap_mode` ikut (INV-CFG-09). Tidak ada lapisan PT yang disetel, jadi PT yang ada dan PT baru semuanya
  memakai "saat faktur" begitu kode ini dipasang; "saat terima" tetap bisa dipilih per PT dengan alasan. Tagihan jasa yang
  sudah lahir tidak berubah (mode dipotret di tagihan; tagihan lama tanpa `ap_mode` diulang-posting dengan cara lama).
  Pemasangan ke server produksi tetap langkah pemilik (H2).
- **Celah GR/IR per SPK:** jurnal makloon yang menyentuh GR/IR membawa `ref.grir_mko_id` (jasa diterima, faktur dicocokkan,
  klaim dengan debit GR/IR, potongan susut dengan debit GR/IR); `vendor_bill_service.grir_by_po` mengelompokkannya dengan
  kunci `mko:<id>` (jurnal tanpa ref dicari lewat tagihan/sumbernya). Hutang › GR/IR menampilkan baris SPK: nomor SPK
  bertaut ke rincian SPK, mitra, "Makloon · {status}", nilai diterima / sudah difakturkan / klaim, sisa, umur, tagihan
  yang menunggu faktur, dan petunjuk "Cocokkan faktur di rincian SPK" (tanpa tombol Kliring — sisa jasa diselesaikan
  dengan faktur atau klaim). Kaki tabel: Σ sisa per dokumen + tak terhubung = saldo buku besar.
- **Celah susut di mitra (L01):** potong tagihan jasa atas susut di atas toleransi kini juga bisa memilih tagihan yang
  menunggu faktur — jurnal Dr GR/IR 2-1150 (bukan Hutang) dengan rujukan SPK pemilik tagihan; tagihan yang sudah dicocokkan
  tetap Dr Hutang 2-1100. Dulu daftar tagihan yang bisa dipotong hanya `posted`, sehingga dengan bawaan baru pilihannya
  akan kosong.
- Jejak dokumen: jurnal `subcon_service_invoice` bertaut ke tagihan jasanya.

### Uji
- `test_MPT4b_U11` (lapis B): tagihan menunggu faktur 950.000 → baris SPK sisa 950.000 + petunjuk; susut dipotong
  50.000 dari tagihan itu → Dr 2-1150 / Cr 1-1350, sisa 900.000; faktur 900.000 → sisa 0; Σ sisa + tak terhubung = saldo
  buku besar.
- Lapis A (`test_bp_MPT4b_grir_makloon.py`): U8 kini juga memeriksa daftar GR/IR (baris SPK 950.000 → 0, Σ = saldo buku
  besar); **U10** — setiap PT di data uji memakai `saat_faktur` tanpa lapisan PT (sisa lapisan KSC dari uji lama dicabut).
- Uji lama disesuaikan: `test_PK18_U5b` (jurnal jasa gagal → diulang) kini memakai akun GR/IR 2-1150 karena bawaan baru.
- Terdampak, lolos: tests_mem makloon/posting/pengaturan **617 lulus** (termasuk KFT8), PK-28 + MP-T4b **27 lulus**;
  lapis A MP-T4b, PK-28 (kliring bersamaan), MP-T4a, MP-T5 **9 lulus**; jest `pk28GrIr` **11 lulus** (+1 baris SPK).
  `test_l01_material_loss.py` (lapis A) tidak bisa dimuat di lingkungan ini: modul pembantunya
  (`test_p05_acceptance_acc31_33_34.py`) mencari pemasok ber-`entity_id: "all"` yang tidak ada di data lokal — prasyarat
  data, bukan kode unit ini; jalur potong susut diuji di U11.
- Penjaga: config fallback/teks, atomic_claim, posting coverage hijau; `verify_ui_standard` untuk `GrIrView.jsx` menandai
  `chip_custom`/`empty_false` yang sudah ada di `HEAD` sebelum perubahan (garis dasar), bukan dari unit ini.
- Cek layar (`bukti/MP-T4b/uji_jalan_grir_per_spk.js`): baris "KSC/MKO-… · Makloon · diproses · Rp 950.000 · menunggu
  faktur: VBM-… · Cocokkan faktur di rincian SPK", total sisa = saldo buku besar (`1280-05-grir-per-spk.png`); tautan
  membuka rincian SPK dengan "Kembali ke GR/IR" (`1280-06-grir-buka-spk.png`). Putaran pertama kolom "Umur (hari)"
  tertutup kolom Aksi lekat karena catatan tagihan tidak boleh turun baris — diperbaiki (catatan turun baris, nomor tagihan
  utuh, label status dipendekkan).

## Perbaikan layar dari cek pemilik 16 Nov (rincian SPK dibuka dari GR/IR)

Pemilik: "ini kenapa ada 2 kembali?" lalu "terus lalu lihat itu deskripsi cardnya bertumpuk".

- **Dua "Kembali" bertumpuk** — bilah layar asal (PK-44 `BackToOriginBar`) dan tombol kembali rincian tampil berdua. Kini
  satu komponen `DetailBack` (`components/DetailParts.jsx`): bila ada layar asal → satu baris "← Kembali ke {asal}"
  (utama, `back-to-origin`) · tautan kecil "{Daftar …}"; bilah asal tidak dirender selama rincian tampil
  (`AppNavContext.registerDetailBack`). Tanpa layar asal tetap seperti dulu. Dipakai `DetailHeader` (Order Makloon,
  Kedatangan, Perbaikan, Retur) dan rincian Pesanan Khusus, 360 Pelanggan/Pemasok/Mitra Makloon/Karyawan. Uji jest
  `detailBackSatuBaris.test.js` (3) + `pk44JejakDokumen` lolos. Commit `f204b80`.
- **Deskripsi kartu Buku Bahan menumpuk** — enam baris keterangan di bawah tujuh kotak angka, sebagian mengulang angka
  kotaknya. Kini yang perlu tindakan (kunci roll, belum terkunci, kekurangan, selisih belum dijelaskan) tetap tampil;
  stok gudang, butir penjelasan, dan hasil aktual vs estimasi dilipat di "Lihat penjelasan angka"
  (`1280-08-buku-bahan-penjelasan-dibuka.png`).
- **HPP berjenjang terpotong** (ditemukan saat memeriksa halaman penuh) — tabel empat kolom di kolom kiri sempit memotong
  "HPP/unit" dan menulis kode proses mentah (`pre_treatment`). Kini daftar dua baris per langkah: "Langkah n · {label
  tahap}" + "Rp …/yard", lalu mitra + hasil ("(estimasi)" bila belum diterima).
- **Grid wizard tanpa kolom dasar HP** (ditemukan jest `phase4R3`, dari MP-T2) — blok "Isi dari rute produk" kini
  `grid-cols-1` di HP.
- Cek halaman penuh 1366/1280/1024 (`bukti/MP-T4b/uji_jalan_spk_penuh_tumpuk.js`): satu teks "Kembali ke GR/IR", teks
  bertumpuk 0 (isi `<details>` tertutup dan bilah navigasi tidak dihitung); `1280-07-spk-satu-kembali-penuh.png`.
