# MP-T3 — R&D tersambung ke mitra makloon: putusan melahirkan rute dan kontrak yang benar

| | |
|---|---|
| Gelombang | Modul master produk & makloon |
| Jenis | fitur + perbaikan |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | MP-T1 |
| Menutup temuan | Telusur 16 Nov P1, P3, P4, P5, P7, P8 |
| Keputusan | K-65, K-68, K-70, K-72 |
| Standar | `02` §2, §3, §4, §6 |
| Lingkungan uji | B + A (alur R&D lengkap) |

## Tujuan

Labdip, proofing, handfeel bisa dikerjakan pemasok **atau mitra makloon**. Putusan pemenang melahirkan produk yang
tertaut warna, desain, dan kain dasar, plus rute utama dan kontrak sesuai jalurnya (pembelian, atau makloon per proses /
borongan dengan tarif dari harga sample).

## Keadaan sekarang

- Sample hanya ke pemasok: `backend/services/rnd_sample_service.py:230` (`_supplier_snapshot` membaca `db.suppliers`). [dijalankan]
- Putusan selalu membuat kontrak `purchase` (`:1295`) dan sumber restock "supplier" (`_bind_product` `:1187`). [dijalankan]
- Produk lahir tanpa `color_id` walau sample menautkan pustaka warna; tanpa tautan kain dasar. [dijalankan: AUD-RND-5266D]
- Gerbang kain dasar meloloskan kain tahap jadi dan jenis kain berbeda (`backend/services/rnd_flow_service.py`
  `base_fabric_passed`). [dijalankan]
- Desain berstatus "approved" ditolak saat kirim sample (harus `final_submitted`), pesan galat menyesatkan
  (`rnd_flow_service.assert_design_usable`). [dijalankan]
- Pelaksana putaran = staf internal (`schemas_rnd.RoundSubmitBody.performed_by_user_id`). [dibaca]

## Perubahan

### Data / Server
- Peserta sample: `partner_kind` `supplier` · `makloon`; snapshot dari koleksi yang sesuai; mitra makloon disaring proses
  jenis sample (labdip → celup, proofing → printing, handfeel → tenun/rajut/pre-treatment).
- Putusan pemenang makloon: kontrak `makloon` (proses = proses jenis sample; tarif per proses atau borongan, K-68) +
  rute utama `origin=rnd`: kain dasar (input) → tahap proses @ mitra pemenang → produk. Pemenang pemasok: seperti MP-T1.
- Produk lahir membawa `color_id`, `design_id`, `base_fabric_template_id` dari sample/spesifikasi.
- Gerbang kain dasar (K-72): tahap PFP (proofing) / PFD (labdip), jenis kain sama dengan target; menyimpang boleh dengan
  alasan yang dicatat.
- Pesan desain: "Desain sudah disetujui tetapi berkas final belum diajukan. Unggah mockup, file asli, dan gambar cetak,
  lalu ajukan final."
- Putaran mencatat mitra pelaksana (peserta sample) terpisah dari staf yang menginput.

## Uji penerimaan

| ID | Lapis | Persiapan | Langkah | Hasil |
|---|---|---|---|---|
| U1 | B | mitra celup C | sample labdip → kirim ke C → ACC → putus C tarif 9.000/kg | kontrak makloon proses celup @C 9.000/kg; rute PFD→celup@C→jadi; produk ber-`color_id` |
| U2 | B | mitra printing tanpa proses celup | kirim labdip ke mitra printing | 400 "tidak mengerjakan celup" |
| U3 | B | kain dasar tahap jadi | proofing dengan kain dasar itu tanpa alasan · dengan alasan | 400 · 200 + alasan tercatat |
| U4 | B | desain approved belum final | kirim sample | 400 pesan baru |
| U5 | A | alur proofing lengkap ke mitra printing | putus → rilis → plan-from-route (MP-T2) | rilis lolos; SPK terisi mitra pemenang tanpa peringatan menyimpang |

## Di luar lingkup
Penyatuan dua siklus desain (galeri vs studio) — dicatat sebagai temuan, unit tersendiri.

## Asumsi dan risiko
ASUMSI: pemetaan jenis sample → proses mitra adalah pengaturan (daftar), bawaan seperti di atas.
