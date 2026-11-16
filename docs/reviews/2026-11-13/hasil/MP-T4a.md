# MP-T4a — Mekanisme makloon tanpa jurnal baru (pecahan MP-T4)

- Commit awal: `d746702`        - Commit akhir: lihat `docs/blueprint/STATUS.md` baris 107        - Branch: `claude/nifty-carson-jjx3c8`
- Spesifikasi `docs/blueprint/unit/MP-T4a.md`; keputusan K-62, K-66, K-67, K-69. Bagian berjurnal baru (K-63, K-64,
  borongan per SPK) = **MP-T4b `tahan`** (H4/H5, pertanyaan di `STATUS.md` "Menunggu pemilik").
- Peta kode: penjelajahan terarah 16 Nov (klaim, QC, batal, terima sebagian, rantai langkah, nilai WIP & jurnal).

## Cek ulang "Keadaan sekarang"

| Butir (audit makloon 16 Nov) | Hasil di `d746702` |
|---|---|
| Hasil langkah antara wajib masuk gudang sendiri sebelum dikirim ke mitra berikut | Berlaku — `issue_step` butuh stok `available` di gudang (`makloon_order_service.py` `_assert_source_stock`) |
| Validasi klaim baru saat setuju | Berlaku — `propose_claim` tidak memeriksa status langkah maupun sisa tagihan; `approve_claim` yang menolak |
| Tolak klaim menutup SPK | Berlaku — `rejected` tidak dihitung "belum beres" di `_recompute_status_and_costing` |
| QC tolak hasil makloon tidak tersambung klaim | Berlaku — `qc_service.process_qc_decision` tidak menyentuh SPK |
| Batal SPK saat bahan di mitra | **Bukan cacat** — sudah ada `awaiting_return` + "Kembalikan bahan" + catat hilang; tidak diubah |
| Terima sebagian lewat pintu langsung menutup langkah | Berlaku — terima bertahap hanya lewat Kedatangan (`mko_partial`); **tidak dikerjakan di unit ini** (dicatat) |

## Perubahan

- **Teruskan ke mitra berikut** (`makloon_order_service.forward_step`, `POST /api/makloon-orders/{id}/steps/{seq}/forward`,
  izin baru `makloon_order.forward` "Teruskan kain ke mitra berikut", bawaan Admin, Manajer, MD — K-66):
  terima hasil langkah N (roll lahir, WIP langkah N ditutup — `subcon_receipt` Dr 1-1300 / Cr 1-1350) lalu kirim roll
  yang SAMA ke mitra langkah N+1 (`subcon_issue` Dr 1-1350 / Cr 1-1300). Tidak ada akun/arah jurnal baru; dua jurnal
  bernilai sama. Ditolak bila langkah N terakhir, langkah N+1 sudah berjalan / jasa murni / tanpa mitra (K-61).
  Rincian roll boleh kosong → satu roll gabungan (K-67); lot kosong diisi `TERUS-<SPK>-<langkah>-<n>` lalu dinomori lot PT.
  Jejak `forwarded_to` / `forwarded_from` + timeline `forwarded`. Pintu ini sengaja tidak lewat Kedatangan (barang tidak
  datang ke gudang).
- **Klaim**: diajukan hanya untuk langkah yang hasilnya sudah diterima; potong bon dicek terhadap sisa tagihan jasa saat
  diajukan; menolak pengajuan mengembalikan klaim ke `open` (alasan & nilai yang ditolak disimpan; SPK tetap Sebagian).
- **Tolak QC hasil makloon** membuka/menambah klaim langkah itu (`makloon_claim_service.open_from_qc`; klaim yang menunggu
  persetujuan/sudah disetujui tidak ditimpa, hanya dicatat). `qc_service` mendapat `logger`.
- **Layar**: tombol "Teruskan ke {mitra}" + pop-up `MkoForwardModal`; catatan "Diteruskan langsung ke …"; panel klaim
  menampilkan pengajuan terakhir yang ditolak dan daftar tolak QC; tab Order Makloon untuk MD.

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/makloon_order_service.py` | `forward_step` |
| `backend/services/makloon_claim_service.py` | validasi saat diajukan, tolak → `open`, `open_from_qc` |
| `backend/services/qc_service.py` | kait klaim dari tolak QC; `logger` |
| `backend/routers/makloon_orders.py` | endpoint teruskan |
| `backend/permissions_config.py`, `backend/access_modules.py` | izin `forward` + label |
| `frontend/src/features/purchasing/MakloonOrderDetailPanel.jsx`, `makloon/MkoForwardModal.jsx` (baru), `makloon/MakloonClaimPanel.jsx`, `frontend/src/config/hubTabs.js` | layar |
| Uji | `backend/tests_mem/test_MPT4a_klaim_makloon.py` (6), `backend/tests/test_bp_MPT4a_teruskan.py` (3, lapis A); disesuaikan `test_PRT9_izin_bawaan.py` |
| Dibangkitkan / dokumen | `access_builtin_fixture.json`, `CODEBASE_MAP.md`, `ENTITY_REGISTRY.md`, `memory/PRD.md`, `KN_32` §9.35 |

## Uji penerimaan

Merah sebelum kode: klaim langkah `issued` 200; potong bon 600.000 > 500.000 diterima saat diajukan; tolak → `rejected`;
`open_from_qc` tidak ada; QC tidak memanggil klaim.

| ID | Lapis | Hasil |
|---|---|---|
| U1 | B | lulus — klaim langkah `issued` 400 "…hasilnya sudah diterima…" |
| U2 | B | lulus — potong bon 600.000 400 "melebihi sisa tagihan jasa Rp 500.000"; 250.000 → 200 |
| U3 | B | lulus — tolak → `open`, `rejected_reason` tersimpan, SPK `partially_received` + hold `claim_unsettled` |
| U4 / U4b | B | lulus — tolak QC 12,5 yd membuka klaim (SPK selesai → Sebagian); klaim menunggu persetujuan tidak ditimpa |
| U5 | B (kode) | lulus — `process_qc_decision` memanggil `open_from_qc` |
| U6 | A | lulus — greige 200 yd Rp 20.000 (Rp 4.000.000) → PFP 190 yd (2 roll 95) diteruskan oleh MD: langkah 1 `received`, langkah 2 `issued` bahan 190 yd, `material_value` = nilai hasil langkah 1; 2 roll PFP `subcon`, 0 `available`; jurnal terima langkah 1 = kirim langkah 2 = Rp 4.000.000 |
| U7 | A | lulus — hanya jumlah 188 yd → 1 roll 188 yd `subcon` |
| U8 | A | lulus — langkah berikut tanpa mitra 400 "Isi mitra langkah 2…"; langkah terakhir 400 "…langkah terakhir…" |
| Layar | A | lulus — lihat Cek layar |

Uji terarah lain: klaim/QC lama (`test_KPT4a_setara`, `test_PK44_jejak_dokumen`, `test_R0_integrasi_fix6`) 33 lulus; sapuan
izin PR-T3/PR-T8/PR-T8b + PR-T5 + PR-T9 + MP-T2/MP-T4a lulus.

## Cek layar (`bukti/MP-T4a/uji_jalan_teruskan.js`, MD)

SPK KSC/MKO-00026: tombol "Teruskan ke Mitra Printing …" pada langkah 1 (`1280-05-teruskan-form.png`), isi 190 + dua roll
95 → catatan "Diteruskan langsung ke Mitra Printing … · 190 oleh Rina Merchandiser" (`1280-06-teruskan-selesai.png`).
Uji jalan pertama menemukan 400 (roll tanpa lot dari layar) → lot kosong kini diisi otomatis. Galat lain: 403
`/api/esign/signatures/...` untuk MD — sudah ada sebelumnya (MD tanpa izin tanda tangan), tidak terkait.

## Menyimpang dari blueprint

- "Paket kerja end-to-end" diwujudkan sebagai SPK berlangkah banyak + teruskan antar-mitra (mitra yang sama boleh
  meneruskan ke dirinya sendiri untuk langkah berikut) — tidak ada dokumen "paket" baru.
- Terima sebagian lewat pintu langsung dan batal SPK tidak diubah (lihat cek ulang).
- Tarif borongan per SPK pindah ke MP-T4b (menyentuh pembentukan tagihan jasa).

## Asumsi

- ASUMSI: roll yang diteruskan "lahir" sesaat di gudang tujuan hasil SPK lalu langsung berstatus di mitra; tidak tersedia
  untuk dijual/dialokasikan di antaranya (satu permintaan).
- ASUMSI: MD tidak mengisi nilai jasa saat meneruskan (`can_set_service_value=False`, nilai dari kontrak/rencana).

## Gate

Gate penuh sekali di akhir gelombang MP. `verify_ui_standard`: tidak ada temuan untuk berkas unit ini (sesudah tombol
memakai `btn-sm`).

## Yang perlu direview

- Bentuk "teruskan = terima + kirim" (dua jurnal saling menetralkan) vs satu dokumen pindah WIP antar-langkah.
- Penolakan klaim kini tidak menutup SPK — butuh keputusan yang disetujui (terima dengan catatan bila tidak dituntut).
