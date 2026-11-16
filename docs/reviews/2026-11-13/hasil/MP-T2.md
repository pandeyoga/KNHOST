# MP-T2 — Satu wizard SPK makloon yang membaca rute; semua pilihan tersaring tahap

- Commit awal: `ce9c3a5`        - Commit akhir: lihat `docs/blueprint/STATUS.md` baris 105        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: telusur 16 Nov P10; audit makloon 16 Nov (dua pintu, dropdown asal, tahap bawaan "Tenun", judul "Buat PO")
  — spesifikasi `docs/blueprint/unit/MP-T2.md`; keputusan K-57, K-59, K-61
- Risiko tinggi. (a) dan (b) satu putaran: pintu lama (`MakloonOrderCreateModal`) dialihkan ke wizard dan dihapus di commit
  yang sama, sesudah pencarian membuktikan satu-satunya pemanggil adalah `PurchaseOrderManagement.jsx`.

## Cek ulang "Keadaan sekarang" (spesifikasi `a98754f`, diperiksa di `ce9c3a5`)

| Butir | Hasil |
|---|---|
| Dua pintu: `MakloonWizard.jsx` (tab Order Makloon, juga PR) dan `MakloonOrderCreateModal.jsx` (menu Pesanan Pembelian, `POCreateMenu.jsx:14-17`) | Berlaku; pemanggil modal hanya `admin/PurchaseOrderManagement.jsx:447` |
| `MakloonStepEditor.jsx`: tahap tidak disaring, `ProductSelect` hasil tanpa `stage`; tahap bawaan "Tenun" | Berlaku — bawaan dari `emptyStep().process_type = "tenun"` + efek pilih tahap `|| stageOptions[0]` |
| Server menerima langkah yang tahapnya tidak sambung (`_resolve_stage` jalur 3) | Berlaku: tahap ditemukan dari master tetapi tahap produk tidak dibandingkan sama sekali |
| (tambahan) "Alasan qty manual" dipaksa | Aturan DEC-07 lama (tanpa resep → alasan wajib); kini resep ikut terisi dari rute bila langkah rute punya resep |
| (tambahan) Kirim bahan tanpa mitra lolos; tidak ada pintu mengisi mitra sesudah SPK lahir | Berlaku — K-61 butuh pintu baru |

## Perubahan

- **Server**
  - `makloon_order_service._assert_stage_chain` — SPK baru: bahan masuk dan hasil tiap langkah wajib bertahap asal/hasil
    master ("Langkah 1 (Printing): bahan masuk harus bertahap PFP; … bertahap Greige."). Produk tanpa tahap tercatat tidak
    ditolak; tahap yang tidak mengubah kain (screen) tidak diperiksa.
  - `GET /api/makloon-orders/plan-from-route?product_id=&qty=` (izin `makloon_order.create`) →
    `product_route_service.plan_makloon`: langkah dari rute utama (tahap, mitra, kontrak, resep, bahan masuk, hasil antara),
    qty bahan dihitung mundur (resep yield × (1 − susut) > susut kontrak > 1, dibulatkan ke atas 2 desimal), mode
    `buy_process` bila rute diawali beli dari pemasok. Rute beli/produksi sendiri → `ready=false` dengan alasan.
  - Prefill PR (`pr_sourcing_service.makloon_prefill`) membaca rute lebih dulu; resep tunggal tetap cadangan.
  - K-61: `issue_step` menolak "Isi mitra langkah N sebelum mengirim bahan." (sesudah pemeriksaan periode buku PK-37);
    `POST /api/makloon-orders/{id}/steps/{seq}/partner` (izin `makloon_order.create`) mengisi/ganti mitra langkah
    `pending` — mitra wajib mengerjakan prosesnya; kontrak dicari ulang; tarif dihitung dari kontrak hanya bila langkah
    belum bertarif; biaya rencana & costing dihitung ulang; jejak `partner_set` di timeline.
- **Layar**
  - Pesanan Pembelian › Buat › "Beli Bahan + Proses Makloon"/"Proses Makloon Saja" membuka `MakloonWizard` (mode terisi);
    `MakloonOrderCreateModal.jsx` dihapus.
  - Wizard: judul "Buat Order Makloon"; kotak "Isi dari rute produk (disarankan)"; tahap bawaan dihapus — tahap dipilih
    otomatis hanya bila calon tunggal; pilihan tahap tiap langkah hanya yang menerima tahap bahan masuknya (pilihan lama
    yang tidak cocok tetap tampak bertanda "(tidak cocok tahap bahan)"); pemilih hasil disaring tahap hasil.
  - Rincian SPK: langkah draf tanpa mitra menampilkan "Mitra langkah ini belum diisi — bahan belum bisa dikirim." +
    "Pilih mitra…" (tersaring proses); tombol "Issue ke Makloon" baru tampil sesudah mitra terisi.
  - Label "Alasan bila menyimpang dari rute utama (isi bila diminta)".
- **Ikut terbawa (MP-T1)**: `FamilyRoutesTab.jsx` memakai token warna `kn-*` + `StatusBadge` (penjaga `verify_ui_standard`
  menandai 23 hex baru dan pil buatan sendiri saat MP-T2 diperiksa).

## Berkas

| Berkas | Isi |
|---|---|
| `backend/services/makloon_order_service.py` | `_assert_stage_chain`, penjaga mitra di `issue_step`, `set_step_partner` |
| `backend/services/product_route_service.py` | `plan_makloon`, `_step_factor` |
| `backend/routers/makloon_orders.py` | `plan-from-route`, `steps/{seq}/partner` (didaftar sebelum `/{mko_id}`) |
| `backend/services/pr_sourcing_service.py` | prefill PR membaca rute; `material_stage` |
| `frontend/src/features/purchasing/makloon/MakloonWizard.jsx`, `MakloonStepEditor.jsx` | isi dari rute, penyaring tahap |
| `frontend/src/features/purchasing/MakloonOrderDetailPanel.jsx` | isi mitra langkah draf |
| `frontend/src/features/admin/PurchaseOrderManagement.jsx`; dihapus `frontend/src/features/purchasing/MakloonOrderCreateModal.jsx` | satu pintu |
| `frontend/src/features/catalog/FamilyRoutesTab.jsx` | token warna (MP-T1) |
| `scripts/audit_sales_roles_ux.py` | teks rujukan modal lama |
| Uji | `backend/tests_mem/test_MPT2_spk_dari_rute.py` (5, baru) |
| Dokumen | `ENTITY_REGISTRY.md` (catatan makloon_orders), `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.35, `CODEBASE_MAP.md` |

## Uji penerimaan

Merah sebelum kode: U1 404 ("Order makloon tidak ditemukan" — jalur tertangkap `/{mko_id}`), U2/U2b 200 (SPK lahir dengan
tahap salah), U3 409 stok (kirim bahan tanpa mitra lolos sampai cek stok), U5 prefill resep tunggal.

| ID | Lapis | Hasil |
|---|---|---|
| U1 | B | lulus — target 95 yard; langkah 2 faktor 1 → 95 PFP; langkah 1 resep yield 0,95 → 95 ÷ 0,95 = 100 greige; langkah `pfp`@A (resep), `printing`@B (kontrak) |
| U2 | B | lulus — 400 "bahan masuk harus bertahap PFP" |
| U2b | B | lulus — 400 "hasil harus bertahap PFP" |
| U3 | B | lulus — SPK draf 200; kirim bahan 400 "Isi mitra langkah 1 sebelum mengirim bahan."; mitra printing ditolak "tidak mengerjakan"; mitra pre-treatment 200, `makloon_name` terisi |
| U5 | B | lulus — prefill PR `source=rute`, langkah `pfp`, `printing`, bahan 100 |
| U4 | layar (uji jalan, A) | lulus — lihat Cek layar |

Uji lama yang terdampak: `test_PK37_kunci_dokumen.py::U9[11]` sempat merah (penjaga mitra mendahului pemeriksaan periode
buku; fixture memakai `partner_id`, bukan `makloon_id`) → penjaga dipindah sesudah pemeriksaan periode; 25 lulus.
Uji terarah lain: semua `tests_mem` yang menyentuh SPK makloon (5 berkas, 94 + 1) lulus; sapuan izin PR-T3/PR-T8/PR-T8b +
MP-T1/MP-T2 47 lulus.

## Cek layar

`bukti/MP-T2/uji_jalan_wizard.js`, `uji_jalan_isi_mitra.js` (lingkungan A, Admin):
- 1280 lewat Pesanan Pembelian › Buat › "Proses Makloon Saja": pop-up yang sama dengan tab Order Makloon; "Isi dari rute
  utama" (AUD-RND-5266D, 300) → bahan "Kain Grey Katun (per Yard)" 300, catatan "Diisi dari rute “Printing di Rotary (uji
  jalan)”" (`1280-01-isi-rute.png`).
- Langkah 1 (bahan Greige): pilihan tahap hanya "PFP", "PFD", "Proofing"; langkah 2 (sesudah PFP): "Printing", "Proofing"
  (`1280-02-rantai.png`). Sebelum perbaikan `material_stage`, langkah 1 masih menampilkan semua tahap — ditemukan oleh uji
  jalan ini dan diperbaiki.
- 390 lewat tab Order Makloon: isi sama, `scrollWidth` 390 (`390-01-isi-rute.png`, `390-02-rantai.png`).
- Rincian SPK draf KSC/MKO-00016: kotak "Mitra langkah ini belum diisi…", tanpa tombol Issue; pemilih mitra hanya 4 mitra
  pre-treatment; sesudah memilih, tombol Issue tampil (`1280-03-mitra-kosong.png`, `1280-04-mitra-terisi.png`).
- Tanpa galat API selama uji.

## Menyimpang dari blueprint

- Judul "Buat Order Makloon" (spesifikasi: "Buat SPK Makloon") — mengikuti istilah tombol & tab yang sudah ada.
- Wizard tetap memakai alur tiga langkah (Bahan & Gudang → Rantai Proses → Ringkasan); "Isi dari rute" diletakkan di
  langkah pertama, bukan langkah baru "Barang yang dibuat".
- `set_step_partner` tidak mengubah susut/toleransi langkah dari kontrak baru (hanya tarif bila belum ada) — supaya angka
  rencana yang sudah dilihat petugas tidak bergeser diam-diam; dicatat untuk MP-T4.

## Asumsi

- ASUMSI: mengisi mitra langkah draf = bagian membuat SPK (izin `makloon_order.create`), bukan izin baru.
- ASUMSI: tahap bertipe sampling (proofing) tanpa tahap asal boleh dipilih untuk bahan bertahap apa pun.
- ASUMSI: MD tetap tanpa izin Order Makloon (bawaan); K-66/K-77 dikerjakan di MP-T4/MP-T5.

## Gate

Gate penuh sekali di akhir gelombang MP. Penjaga yang dijalankan: `verify_ui_standard` — tidak ada temuan untuk berkas unit
ini (sisa temuan garis dasar, mis. hex `#F5D9B0` di `ClosingView.jsx`).

## Yang perlu direview

- Penolakan rantai tahap berlaku untuk semua pembuat SPK (API, PR, seed): data acuan atau skrip yang membuat SPK bertahap
  salah kini ditolak.
- Kirim bahan kini butuh mitra — SPK lama tanpa mitra di data nyata perlu diisi lewat rincian SPK sebelum dikirim.
