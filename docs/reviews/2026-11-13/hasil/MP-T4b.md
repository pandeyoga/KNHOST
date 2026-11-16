# MP-T4b — Jurnal makloon: hutang jasa saat faktur mitra dicocokkan, hasil klaim per keadaan roll, borongan per SPK

- Commit awal: `168914a`        - Commit akhir: lihat `STATUS.md` baris 107b        - Branch: `claude/nifty-carson-jjx3c8`
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
- CATATAN: layar Hutang › GR/IR mengelompokkan sisa per PO; jurnal GR/IR jasa makloon tidak ber-PO sehingga masuk baris
  "tidak terhubung ke PO". Daftar GR/IR per SPK makloon belum dibuat — usulan unit lanjutan bila sakelar dinyalakan.
- CATATAN: klaim yang sudah disetujui tidak dihitung ulang. Mode klaim diambil dari tagihan jasa langkahnya (`ap_mode`);
  tagihan lama tanpa `ap_mode` atau langkah tanpa tagihan memakai sakelar PT saat klaim disetujui.
- H5: sakelar untuk PT nyata dinyalakan pemilik sesudah saldo hutang jasa makloon dicocokkan manual.
