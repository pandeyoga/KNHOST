# MP-T3 — R&D tersambung ke mitra makloon: putusan melahirkan rute dan kontrak yang benar

- Commit awal: `86cd75…` (MP-T2 status)        - Commit akhir: `f6ebfb8`        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: telusur 16 Nov P1, P3, P4, P5, P7, P8 — spesifikasi `docs/blueprint/unit/MP-T3.md`; keputusan K-65, K-68,
  K-70, K-72
- Risiko tinggi; (a)+(b) satu putaran: jalur pemasok tidak berubah (cabang baru hanya untuk peserta mitra makloon).

## Cek ulang "Keadaan sekarang" (spesifikasi `a98754f`, diperiksa di HEAD MP-T2)

| Butir | Hasil |
|---|---|
| Sample hanya ke pemasok (`rnd_sample_service.py:230` `_supplier_snapshot`) | Berlaku; tiga pemanggil (kirim, buka round, putus) |
| Putusan selalu kontrak `purchase` (`:1295`), sumber restock "supplier" (`_bind_product`) | Berlaku |
| Produk tanpa `color_id` | Berlaku — `_product_draft` menyalin kode/nama/hex warna tanpa id; `design_id` & `base_fabric_*` **sudah** tersalin (koreksi telusur: hanya kosong pada uji labdip tanpa desain/kain dasar) |
| Gerbang kain dasar meloloskan tahap jadi & jenis kain beda (`rnd_flow_service.base_fabric_passed`) | Berlaku |
| Desain "approved" ditolak dengan pesan berkas belum lengkap (`assert_design_usable`) | Berlaku |
| Pelaksana putaran = staf internal | Berlaku, dan **tetap** (staf yang menginput hasil); mitra pengerja tercatat sebagai peserta round (`supplier_id` + `partner_kind`) — kini bisa mitra makloon |

## Perubahan

- **Master Jenis Sampling**: benih `partner_process_types` (labdip → celup; proofing → printing; handfeel → tenun, rajut,
  pre-treatment; bulk_sample → tidak dibatasi). Baris hidup tanpa field ini memakai benih.
- **Peserta sample**: `_supplier_snapshot` menerima pemasok atau mitra makloon; mitra makloon ditolak bila tidak mengerjakan
  proses jenis sample ("Printing Uji tidak mengerjakan Celup (Dyeing) — jenis Labdip dikerjakan mitra dengan proses itu
  atau oleh pemasok."). Peserta & round membawa `partner_kind`.
- `GET /api/rnd/samples/{id}/partner-options` (izin `rnd.submit`) — pemasok aktif + mitra makloon tersaring proses. Pop-up
  kirim sample memakainya (tidak lagi `/suppliers`, sehingga tidak butuh izin pemasok).
- **Putusan pemenang mitra makloon**: kontrak `makloon` dengan proses dari jenis sample ACC yang dikerjakan mitra,
  tarif per satuan kain (bawaan) atau borongan `lot` (`tariff_mode: "borongan"`, K-68); tanpa barang supplier; sumber
  restock "makloon"; rute utama `origin=rnd` "<tahap> di <mitra>" (bahan masuk = varian kain dasar spesifikasi yang
  bertahap asal tahap itu; bila kontrak/bahan tidak lolos aturan rute, rute dibuat tanpa bagian itu).
- **Gerbang kain dasar proofing (K-72)**: tahap induk kain dasar wajib PFP dan jenis kain sama dengan target; menyimpang
  boleh dengan `base_fabric_override_reason` (≥ batas huruf alasan rantai) yang tercatat di sample (`base_fabric_override`).
- **Pesan desain**: "Desain … sudah disetujui tetapi berkas final belum diajukan. Unggah mockup, file asli, dan gambar
  cetak (bila belum), lalu tekan "Ajukan final" di Studio Desain."
- **Produk** dari spesifikasi membawa `color_id`.
- **Layar**: pop-up kirim sample ("Cari pemasok atau mitra makloon…", baris berlabel "Pemasok"/"Mitra makloon"); form putus
  pemenang — "Cara tarif mitra makloon" (Per proses / Borongan), label harga menyesuaikan; form permintaan proofing —
  "Alasan bila kain dasar menyimpang …".

## Berkas

| Berkas | Isi |
|---|---|
| `backend/domain_registry.py` | benih `partner_process_types` |
| `backend/services/rnd_sample_service.py` | `partner_processes`, `partner_options`, `_winner_process`, `_supplier_snapshot`, putusan & `_bind_product` |
| `backend/services/product_route_service.py` | `ensure_rnd_makloon_route` |
| `backend/services/rnd_flow_service.py` | gerbang kain dasar, pesan desain |
| `backend/services/rnd_spec_service.py` | `color_id` |
| `backend/routers/rnd.py`, `backend/schemas_rnd.py` | `partner-options`; `base_fabric_override_reason`, `tariff_mode` |
| `frontend/src/features/rnd/SampleSendModal.jsx`, `DecideModal.jsx`, `SampleFormModal.jsx` | layar |
| Uji | `backend/tests_mem/test_MPT3_rnd_mitra_makloon.py` (6, baru) |
| Bukti lapis A | `bukti/MP-T3/telusur_rnd_mitra_makloon.py`, `telusur_proofing_mitra_printing.log` |
| Dokumen | `ENTITY_REGISTRY.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` §9.35, `CODEBASE_MAP.md` |

## Uji penerimaan

Merah sebelum kode: U1/U1b "Supplier '…' tidak ditemukan." (400); U2 sama; U3 tidak menolak; U4 pesan lama; U6 `KeyError`.

| ID | Lapis | Hasil |
|---|---|---|
| U1 | B | lulus — kontrak `makloon` @pencelup proses `celup` basis `yard` 9.000; tanpa barang supplier; rute `origin=rnd` utama `celup`@pencelup + kontrak; sumber restock "makloon" |
| U1b | B | lulus — borongan: basis `lot`, tarif 2.500.000 |
| U2 | B | lulus — labdip ke mitra printing 400 "tidak mengerjakan"; ke pencelup 200, peserta `partner_kind=makloon` |
| U3 | B | lulus — kain dasar tahap jadi ditolak tanpa alasan, diterima dengan alasan (tercatat); jenis kain beda (rajut vs tenun) ditolak; PFP tenun lolos |
| U4 | B | lulus — pesan baru desain disetujui belum final |
| U5 | A | lulus — proofing KSC/SMP-00012/00013 ke PT Rotary Print Indah: daftar tujuan 4 mitra printing + 6 pemasok; putus → KSC/SCT-00016 makloon printing 6.500/yard; rute "Printing di PT Rotary Print Indah" bahan PFP-KTN-001 + kontrak; restock "makloon"; produk ber-`design_id` & kain dasar; rilis 200; `plan-from-route` 100 → bahan PFP 100, langkah printing @Rotary berkontrak; SPK makloon lahir **tanpa peringatan** (sebelumnya 2 peringatan) |
| U6 | B | lulus — `color_id` terbawa |

Uji terarah: semua `tests_mem` yang menyentuh R&D (4 berkas) + MP-T1/T2/T3 — 70 lulus.

## Cek layar

Belum ada potret khusus MP-T3: perubahan layar kecil (sumber daftar & label kirim sample, satu pilihan di form putus, satu
isian alasan) — dikompilasi dan diperiksa `verify_ui_standard` (tanpa temuan untuk tiga berkas). **Belum diuji jalan di
peramban**; alurnya dibuktikan lewat API di lapis A (U5).

## Menyimpang dari blueprint

- Pemetaan jenis sample → proses mitra disimpan di master Jenis Sampling (bisa diubah pemilik), bukan kunci pengaturan
  baru. Layar master belum punya isian untuk field ini (pakai benih) — dicatat.
- "Pelaksana putaran" tetap staf penginput; mitra pengerja = peserta round (sudah tercatat).
- Gerbang kain dasar K-72 hanya untuk proofing (labdip tidak memakai kain dasar di alur sekarang).

## Asumsi

- ASUMSI: proses kontrak pemenang = proses pertama jenis sample ACC yang dikerjakan mitra.
- ASUMSI: borongan = basis `lot` (satu harga per lot/SPK) di mesin tarif yang ada.
- ASUMSI: rute R&D tidak menimpa rute yang sudah ada di PT itu.

## Gate

Gate penuh sekali di akhir gelombang MP.

## Yang perlu direview

- Daftar tujuan kirim sample kini memuat mitra makloon; mitra yang prosesnya tidak cocok tidak muncul.
- Proofing dengan kain dasar bukan PFP kini butuh alasan (sebelumnya lolos).
