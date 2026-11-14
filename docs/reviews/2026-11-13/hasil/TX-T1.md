# TX-T1 — Pengaturan pajak bertanggal berlaku, potret pajak di dokumen, dan data pajak pelanggan

- Commit awal: `b5b7539` (worktree kerja, HEAD terlepas) · digabung pelaksana ke `f05d8da` (sesudah KP-T9, PK-44)
- Commit akhir: `9707664` (dipasang integrator di atas `5097cda`: CR-T1, PK-31, AG-T1, PM-T2)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: TX-06 (spesifikasi `docs/blueprint/unit/TX-T1.md`; keputusan K-33; standar `02_STANDAR.md` §2.1/2.2/2.4,
  §3.1 Z1/Z2/Z6, §3.2, §4 L1/L5/L6, §5 D1/D3/D5, §6)
- Risiko sedang → satu serah-terima. Prasyarat PK-40 selesai; PK-45 (izin `order.tax_override` + alasan) sudah ada —
  tidak dibuat ulang.
- Unit ini **memindah nilai yang sudah tertulis di kode menjadi pengaturan bernilai sama** (H4). Tidak ada tarif, faktor,
  atau kode transaksi baru; bawaan semua kunci = perilaku sebelum unit ini.

## Cek ulang "Keadaan sekarang" (spesifikasi dibaca pada `3132cc4`; dicek di `b5b7539`)

| Fakta | Hasil di `b5b7539` |
|---|---|
| PPN dari pengaturan saat ini tanpa tanggal | Berlaku, bergeser — `config_service.py:326` (`compute_tax`), `:284` (`get_effective_settings`). KF-T4 sudah memisahkan rumus murni `ppn_breakdown` (`:344`) yang juga dipakai "Coba dulu" |
| Faktor 11/12 ditulis mati di empat tempat | Berlaku, bergeser — `config_service.py:353` (`ppn_breakdown`, dulu di `compute_tax`), `interco_tax_service.py:70` (`_faktur_dpp`), `interco_service.py:250` (`_interco_rate`, bukan `dpp_nilai_lain` `:232`), `config_simulator.py:48` (kini memanggil `ppn_breakdown`, faktornya ikut tertulis di sana). Tambahan yang tidak disebut: label cetak `tax_invoice_service.py` ("Nilai Lain 11/12"), `pdf_resolvers.py:81`, layar `utils/pricing.js`, `utils/taxBreakdown.js` |
| Pembulatan dua desimal di tingkat pesanan | Berlaku, bergeser — `config_service.py:357`/`:361` (`ppn_breakdown`) |
| PT non-PKP memaksa tarif 0 | Berlaku — `config_service.py:305`; KF-T3 juga mendaftarkannya sebagai penimpa `config_overrides.pt_bukan_pkp` |
| Resolver mendukung jadwal + baca pada tanggal | Berlaku — `config_resolver.py:498` (`set_value`), `:273` (`resolve(..., at=)`) |
| Tiga kunci pajak terdaftar | Berlaku — `config_catalog_core.py:20/30/40`; kelompoknya kini `pajak-pembukuan`, sub-judul `pajak` (KF-T4) |
| Daftar & bawaan kode transaksi ditulis mati | Berlaku, bergeser — `tax_invoice_service.py:19` (`KODE_TRANSAKSI_VALID`), `:217` dan `:315` (bawaan 04/01) |
| Pesanan tanpa faktor/cara bulat; override menghitung dengan aturan hari itu | Berlaku — `routers/sales_orders.py:638`, `so_override_service.py:326`; bukti merah U3 (2.860.000) |
| Data pajak pelanggan hanya `npwp` | Berlaku — `schemas.py:106`, `tax_invoice_service.py:165` |
| `tax_override: "non_ppn"` | **Sebagian sudah ditutup PK-45**: izin `order.tax_override` + alasan ≥ 10 huruf + pesan 403/400 sudah ada (`routers/sales_orders.py:100` `_periksa_tax_override`); checkout memang belum punya isiannya. Unit ini menambah `tax_override_by`, potret, dan isian checkout |

## TX-06 — Aturan pajak tanpa tanggal, faktor & kode ditulis mati, data pajak pelanggan tidak punya tempat

- Berlaku di HEAD: ya (lihat tabel di atas; bukti merah di `bukti/TX-T1/merah_kode_lama.log`).
- Akar masalah: mesin pajak membaca dokumen pengaturan gabungan "saat ini"; faktor DPP nilai lain, cara bulat, dan daftar
  kode transaksi hanya ada sebagai konstanta; dokumen tidak menyimpan aturan yang dipakainya sehingga hitung ulang
  (override, amandemen) memakai aturan hari itu.
- Perubahan perilaku (sebelum → sesudah):
  - **Satu pintu `backend/services/tax_config_service.py`**: `tax_settings(entity_id, at)` membaca sepuluh kunci lewat
    `config_resolver.resolve_keys` (baru: `resolve()` banyak kunci sekaligus, hemat kueri, hasil identik) pada waktu
    `at`; PT bukan PKP → tarif 0 & `is_pkp` False; hasil = potret + kode transaksi + `sources`. `round_money(v, satuan)`
    satu fungsi bulat (D5; `dua_desimal` = `round(v, 2)` persis, `rupiah_penuh` = setengah ke atas). `default_kode`,
    `periksa_kode`, `potret_dokumen` (potret tersimpan, atau turunan dokumen lama: 11/12 · per dokumen · dua desimal,
    `asal: "dokumen_lama"`), `periksa_profil_pajak`, `customer_tax`, `data_incomplete`, `periksa_pajak_produk`,
    `bagian_pajak_layar`.
  - **Tujuh kunci baru** (`config_catalog_core.py`, kelompok `pajak-pembukuan` sub-judul `pajak`, `global`+`entity`, risiko
    tinggi, wajib alasan, izin `accounting.manage`, `sensitif_baca=False`): `tax.dpp_nilai_lain_pembilang` 11,
    `…_penyebut` 12, `tax.pembulatan_tingkat` `dokumen`, `tax.pembulatan_satuan` `dua_desimal`,
    `tax.kode_transaksi_diizinkan` `["01","02","03","04","06","07","08","09"]` (= `KODE_TRANSAKSI_VALID` lama),
    `tax.kode_transaksi_bawaan` `01`, `tax.kode_transaksi_bawaan_dpp_nilai_lain` `04`. Bisa dijadwalkan "berlaku sejak"
    di Pusat Pengaturan seperti kunci lain (kunci tidak `bertanggal`: tanggal sebelum baris pertama = nilai sekarang,
    sesuai ASUMSI spesifikasi). Pemakai tiga kunci lama dialihkan ke `tax_settings`; label `tax.dpp_nilai_lain` "Pakai DPP
    nilai lain" (tanpa "(11/12)" karena pecahannya kini diatur).
  - **`compute_tax(subtotal, entity_id, mode_override, *, at, snapshot)`** dan **`compute_order_pricing(..., *, at,
    snapshot)`**: potret diberikan → dihitung dari potret; selain itu dari `tax_settings(entity_id, at)`. Hasil
    `compute_order_pricing` memuat `tax_snapshot` (pesanan tanpa PPN: `is_pkp` False, tarif 0). Per baris →
    `items[].ppn_amount` lalu dijumlah (diskon pesanan dibagi sebanding). Rumus tetap; dengan kunci bawaan angkanya persis
    sama (U1, uji KF-T4 U9/U9b, KF-T2 U10b tetap hijau).
  - **Dokumen baru menyimpan potret**: `create_order` (+ `tax_override_by`), PO (`routers/purchase_orders.py`,
    `pr_sourcing_service`, `rfq_service`), tagihan pemasok (`routers/vendor_bills.py`), amandemen PO.
    **Hitung ulang DARI potret**: `so_override_service`, `amendment_service` (3 titik), `so_line_cancel_service`,
    `routers/so_approvals.py`, `routers/outbound_picking.py` (kurang ambil), `cutting_service`, `sample_sale_service`,
    `special_order_fulfillment` (harga kontrak PO), `po_amendment_service` (potret PO bila pilihan pajak tidak diganti).
  - **Antar-PT**: `_interco_rate` membaca tarif, DPP nilai lain, dan faktor dari `tax_settings` PT penjual; transaksi
    menyimpan `tax_dpp_pembilang/penyebut`; DPP faktur internal (`_faktur_dpp`) memakai faktor transaksinya (lama: 11/12);
    faktur internal memuat `tax_snapshot`. **"Coba dulu"** pajak membaca faktor & cara bulat dari kuncinya.
    **PDF** (`pdf_resolvers._total_rows`) dan cetak faktur lama menulis pecahan dari potret dokumen.
  - **Faktur pajak**: kode bawaan = kode pelanggan → bawaan PT menurut DPP nilai lain potret pesanan; kode sah =
    `tax.kode_transaksi_diizinkan` PT (`issue_tax_invoice`, `replace_tax_invoice`, `set_nsfp` — yang terakhir hanya bila
    kodenya diganti) → 400 "Kode transaksi {kode} tidak dipakai PT ini."; faktur menyimpan `tax_snapshot` (potret
    pesanan), `customer_tax`, `data_incomplete` (tidak menolak terbit).
  - **Pelanggan**: `POST/PATCH /api/customers` menerima `tax_profile` (izin `customer.update` seperti `npwp`), NPWP/NIK
    berhuruf → 400 "{NPWP/NIK} hanya boleh berisi angka.", NIK kosong saat `id_type: nik` → 400; jumlah digit menyimpang =
    `tax_data_warnings` (tidak menolak). Kode transaksi pelanggan harus ada di daftar kode PT pelanggan.
    `GET /customers?for_order=true` membawa `tax_profile.always_tax_invoice`.
  - **Produk**: `tax_treatment` (`kena` bawaan · `dibebaskan` · `tidak_dipungut`) dan `tax_item_code` disimpan lewat
    `POST/PATCH /api/products` (nilai tak sah 400); belum dipakai mesin (L5).
  - **`GET /api/settings/effective`**: bagian `tax` diisi nilai yang DIPAKAI mesin (`bagian_pajak_layar`, L6) — termasuk
    bawaan kunci yang belum pernah diatur — untuk pratinjau POS/PO dan pilihan kode transaksi.
  - **Layar**: lihat "Cek layar".
- Berkas berubah (worktree kerja; di worktree tujuan sama, lihat "Penggabungan"):

| Berkas | Isi |
|---|---|
| `backend/services/tax_config_service.py` | Baru — satu pintu aturan pajak, potret, pembulatan, kode, data pajak pelanggan/produk |
| `backend/services/config_resolver.py` | `resolve_keys` (banyak kunci, satu muat) |
| `backend/config_catalog_core.py` | Tujuh kunci; pemakai tiga kunci lama → `tax_settings`; label/penjelasan DPP nilai lain |
| `backend/services/config_service.py` | `compute_tax`/`ppn_breakdown`/`compute_order_pricing` (+ `_ppn_per_baris`), `tax_snapshot` |
| `backend/services/config_simulator.py` | "Coba dulu" pajak: faktor & cara bulat dari kunci |
| `backend/services/interco_service.py`, `interco_tax_service.py` | Faktor antar-PT dari `tax_settings`; potret di transaksi & faktur internal |
| `backend/services/tax_invoice_service.py`, `pdf_resolvers.py` | Kode dari pengaturan/pelanggan; potret pajak & pembeli; pecahan tercetak dari potret |
| `backend/routers/sales_orders.py` | `tax_snapshot`, `tax_override_by` (+ jejak audit) |
| `backend/routers/customers.py`, `backend/schemas.py` | `tax_profile` + pemeriksaan NPWP/NIK + `tax_data_warnings`; `ProductPayload.tax_treatment/tax_item_code`, `CustomerCreate.tax_profile` |
| `backend/routers/products.py` | Perlakuan PPN & kode barang pajak |
| `backend/routers/settings.py` | Bagian `tax` efektif = nilai mesin |
| `backend/routers/purchase_orders.py`, `vendor_bills.py`, `so_approvals.py`, `outbound_picking.py`, `services/{pr_sourcing,rfq,po_amendment,so_override,amendment,so_line_cancel,cutting,sample_sale,special_order_fulfillment}_service.py` | Simpan potret (dokumen baru) / hitung dari potret (dokumen lama) |
| `scripts/guardrails/config_fallback_allow.json` | Tiga pengecualian basi dibuang (baris `compute_tax` lama) — daftar hanya berkurang |
| `frontend/src/utils/pricing.js`, `utils/taxBreakdown.js` | Pratinjau = server (faktor, cara bulat, per baris); pecahan & "aturan pajak" dari potret |
| `frontend/src/features/finance/TaxInvoices.jsx` | Kode dari daftar PT, Rincian faktur (aturan saat terbit, data pembeli), lencana data belum lengkap, status ikon, tabel baku |
| `frontend/src/features/crm/CustomerTaxSection.jsx` (baru), `CustomerFormModal.jsx` | Bagian "Data pajak" |
| `frontend/src/features/pos/CheckoutNonPpn.jsx` (baru), `CheckoutDrawer.jsx`, `CheckoutStep3.jsx`, `hooks/useAppActions.js` | Pesanan tanpa PPN + alasan; "Selalu minta faktur pajak" |
| `frontend/src/features/orders/OrderDetailPanel.jsx` | Baris "Aturan pajak", catatan pesanan tanpa PPN |
| `frontend/src/features/catalog/VariantEditor.jsx` | Perlakuan PPN & kode barang pajak "belum dipakai mesin" |
| `frontend/src/features/settings/config/configKeyIndex.json` | Dibangkitkan ulang (7 kunci) |
| `backend/tests_mem/test_TXT1_pengaturan_pajak.py` (baru), `test_KFT1_izin_pengaturan.py` | Uji penerimaan; `TXT1_KUNCI = 7` (U04 katalog; U02 tetap — izin `accounting.manage`) |
| `backend/tests/test_decisions_d4.py` (lapis A) | Pematok setelan pajak ikut `tax_settings` (lihat Menyimpang 10) |
| `frontend/src/features/__tests__/txt1PengaturanPajak.test.js` (baru) | Uji komponen layar |
| `ENTITY_REGISTRY.md`, `CODEBASE_MAP.md`, `memory/PRD.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` | Dokumen ikut berubah (§9.7 di cabang; §9.5 di worktree kerja) |

- Pengujian: tabel di bawah. tests_mem worktree kerja **1303 lulus / 2 dilewati / 4 xfail → 1330 / 2 / 4** (+20 uji TX-T1,
  +7 kasus putaran KF-T8 untuk tujuh kunci baru); worktree tujuan (HEAD cabang `f05d8da`) **1328 → 1355 / 2 / 4**.
- Bukti UI: dipotret integrator di 1280/1024 px (lihat "Cek layar"); checkout tanpa PPN tidak terjangkau skrip di data acuan.
- Fixture vs proses: produk/pelanggan/kontrak antar-PT uji disisip langsung; naik status pesanan ke `confirmed` sebelum
  terbit faktur disisip langsung (fixture). Pengaturan (tulis, jadwal, batal jadwal, cabut, pulihkan), pesanan, override,
  faktur, NSFP, PATCH pelanggan, transaksi antar-PT, "Coba dulu" — lewat API.
- Dampak pada modul terkait: semua jalur hitung ulang pesanan/PO kini memakai potret dokumen (perilaku baru yang disengaja,
  lihat RISIKO spesifikasi); pesanan tanpa PPN yang dihitung ulang di persetujuan (`so_approvals`, dulu tanpa
  `tax_override`) kini tetap tanpa PPN karena potretnya bukan PKP.
- Keterbatasan / yang belum diuji: checkout "Pesanan tanpa PPN" tidak dipotret (data acuan); lapis A
  `test_decisions_d4.py` disesuaikan — pelaksana di database tiruan (3 lulus), integrator di MongoDB asli (4 lulus); suite jest yang tidak termuat karena `@radix-ui` (kendala
  lingkungan) — asersi pajaknya disalin dan lulus.
- Status: implemented_pending_review

## Uji penerimaan

`backend/tests_mem/test_TXT1_pengaturan_pajak.py` (lingkungan B). "Merah di lama" = berkas uji yang sama dijalankan di
salinan `git archive b5b7539` (`bukti/TX-T1/merah_kode_lama.log`).

| ID | Lapis | Merah di lama (sebab) | Hasil |
|---|---|---|---|
| U1a angka | B | **hijau** (sengaja: bawaan = perilaku lama) | Lulus — DPP 11.000.000, PPN 1.320.000, total 13.320.000 |
| U1b potret | B | ya — `tax_snapshot` tidak ada (`{}`) | Lulus — 12 · 11/12 · `excluded` · `dokumen` · `dua_desimal` · PKP · `berlaku_pada` terisi |
| U2 | B | ya — `compute_tax() got an unexpected keyword argument 'at'` | Lulus — tarif 13 dijadwalkan 2027-01-01 (lapisan PT): pesanan hari ini PPN 1.320.000; `compute_tax(…, at=2027-01-15)` = 1.430.000; jadwal dibatalkan lewat API |
| U3 | B | ya — **2.860.000** (aturan hari itu) | Lulus — override 10 → 20 yard (24.000.000) sesudah tarif 13 berlaku: PPN 2.640.000 dari potret; faktur memuat potret 12 % · 11/12 |
| U4 | B | ya — kunci tidak ada di registry (404) | Lulus — `ent_ksc` pembilang 12: DPP 12.000.000, PPN 1.440.000; PT ketiga (`compute_order_pricing`) tetap 11.000.000 / 1.320.000 |
| U5 | B | ya — kunci tidak ada (404) | Lulus — 1.234.567: PPN 135.802, DPP 1.131.686, total 1.370.369 |
| U6 | B | ya — kunci tidak ada (404) | Lulus — per baris 11.001 + 11.001 = 22.002 (`items[].ppn_amount`); per dokumen 22.001, baris tanpa `ppn_amount` |
| U7 | B | ya — kunci tidak ada (404) | Lulus — "04"; bawaan DPP nilai lain "01" → "01"; pelanggan ber-kode "02" → "02" |
| U8 | B | ya — kunci tidak ada (404) | Lulus — daftar tanpa 07: terbit dengan 07 → 400 "Kode transaksi 07 tidak dipakai PT ini.", tidak ada faktur; 08 sah; ganti kode NSFP ke 07 → 400 |
| U9 | B | ya — PATCH NIK "12ab" diterima 200 | Lulus — 400 "NIK hanya boleh berisi angka."; 400 "NIK wajib diisi …"; NPWP berhuruf 400; NIK 16 angka 200 (`tax_data_warnings` kosong); NIK 5 angka 200 + 1 peringatan; faktur `customer_tax` = nik/nomor/nama/alamat pajak/bukan PKP, `data_incomplete` kosong |
| U10 | B | ya — `KeyError: 'data_incomplete'` | Lulus — 200, `data_incomplete` memuat `identitas_pajak`; alamat pajak kosong = alamat utama |
| U11 | B | ya — `KeyError: 'tax_override_by'` (403/400/200 sudah benar sejak PK-45) | Lulus — `sls` 403 (pesan Z6), `mgr` tanpa alasan 400, "Kawasan berikat" 200: PPN 0, total 12.000.000, alasan + pembuat tersimpan, potret bukan PKP |
| U12 | B | **hijau** — sudah ditutup PK-45 | Lulus — Tanpa Acuan (`order.view/create/tax_override` + `customer.view`) 200; Manajer Kosong 403; Sopir 403 |
| U13a angka | B | **hijau** (perilaku lama) | Lulus — `ent_kanda` (tarif PT 13): PPN 0, total 12.000.000, `is_pkp` false |
| U13b potret | B | ya — `tax_snapshot` tidak ada | Lulus — potret `is_pkp` false, tarif 0 |
| U14 | B | ya — kunci pembilang tidak ada (bagian "sebelum" sudah 11.000.000) | Lulus — transaksi antar-PT 100 m × 120.000 lewat API: DPP faktur 11.000.000 (tarif efektif 11); sesudah pembilang 12 di PT penjual, transaksi baru 12.000.000 (tarif 12), transaksi lama tetap 11.000.000 (lihat Menyimpang 4) |
| U15 | B | ya — kunci tidak ada | Lulus — tujuh kunci: metadata (lingkup, risiko, alasan, izin, kelompok, pemakai), tulis grup → terbaca, lapisan PT → hanya PT itu, nilai tak sah 400, tanpa alasan 400, pulihkan = bawaan; pembilang 0 → 400. Ditambah putaran KF-T8 otomatis: 12 kasus `tax.*` lulus (`bukti/TX-T1/putaran_KFT8_kunci_pajak.log`) |
| U16 | layar (uji jalan) | — | **Diuji jalan** oleh integrator: rincian faktur lama menulis aturan lama (`bukti/TX-T1/layar/fkt_detail_1280.png`); faktur baru berpotret belum ada di data acuan → bagian itu dari uji komponen |
| tambahan | B | ya (modul belum ada) | `round_money` satu fungsi; "Coba dulu" memakai pembilang hipotetis 12 (DPP 12.000.000, PPN 1.440.000); `/settings/effective` (Sales, tanpa `settings.view`) memuat 11/12, `dokumen`, `dua_desimal`, kode 01, daftar kode |

Lapis A: spesifikasi tidak punya butir lapis A. `backend/tests/test_decisions_d4.py` (lapis A lama) disesuaikan — tidak
dijalankan di MongoDB asli (larangan database `backend/.env`); salinannya di database tiruan: 3 lulus, dan tanpa
penyesuaian 1 merah (`'excluded' == 'included'`) — `bukti/TX-T1/salinan_d4_tests_mem.py`.
Integrator menjalankannya di lingkungan A (MongoDB asli, HEAD `a48a0a9`): **4 lulus** — `bukti/TX-T1/lapisA_d4_integrator.txt`.

### Contoh hitung (tangan)

- **U1** subtotal 10 yd × Rp 1.200.000 = 12.000.000. DPP = 12.000.000 × 11 ÷ 12 = 11.000.000. Tarif efektif 12 × 11/12 =
  11 %. PPN = 12.000.000 × 11 % = 1.320.000 (= 12 % × DPP). Total = 12.000.000 + 1.320.000 = 13.320.000.
- **U5** (rupiah penuh) 1.234.567 × 11 % = 135.802,37 → **135.802**. DPP 1.234.567 × 11/12 = 1.131.686,4167 → **1.131.686**.
  Total = 1.234.567 + 135.802 = **1.370.369** (total tidak dibulatkan lagi: harga + PPN).
- **U6** (rupiah penuh) per baris: 100.005 × 11 % = 11.000,55 → 11.001; dua baris 22.002. Per dokumen: 200.010 × 11 % =
  22.001,10 → 22.001. Selisih Rp 1 = alasan pengaturan "PPN dibulatkan per".

## Cek layar

### Hasil potret integrator (lingkungan A, HEAD `a48a0a9` → perbaikan `f1b8239`)

Potret di `bukti/TX-T1/layar/`.

| Layar | Temuan | Perbaikan |
|---|---|---|
| Faktur Keluaran 1280 px (`fkt_1280.png`) | 9 kolom lebih lebar dari kartu: kolom Status **tertutup** kolom aksi lekat, Total terpotong, nomor faktur dan "belum diisi" patah dua baris | Status pindah ke bawah nomor (8 kolom), nomor & "belum diisi" tidak dipatah, baris "nilai lain" boleh turun baris, ikon aksi dua kisi 2×2 berlebar minimum → semua kolom terlihat (`fkt_1280d.png`); 1024 px bergulir dengan aksi lekat (`fkt_1024d.png`) |
| Rincian faktur (`fkt_detail_1280.png`) | "Aturan pajak saat terbit" untuk faktur lama tertulis sebagai kalimat aturan lama, bukan angka 0 | — |
| Form pelanggan › Data pajak (`cust_tax_1280.png` → `cust_tax_1280b.png`) | label bagian 6 kapital (`field-label`) sedangkan bagian 1–5 huruf biasa — tidak seragam dalam satu form | label huruf biasa bertoken (tanpa hex) |
| Checkout › Pesanan tanpa PPN | **tidak dipotret**: di data acuan PT aktif admin (Sukacita) tidak punya lokasi gudang POS dan pemilih PT di bilah atas tidak bisa diklik skrip; komponen `CheckoutNonPpn` diperiksa dari kode (`section-card section-pad`, token, alasan tertulis di bawah isian, label tombol berubah) + jest | — |

### Daftar periksa dari kode (pelaksana)

Acuan `docs/KN_37_STANDAR_UI_GUDANG.md` + KN_08/UX. Semua teks baru memakai `text-fs-*`, token `kn-*`, kelas tombol baku;
tidak ada hex/huruf < 12 px baru (ratchet `verify_ui_standard` tetap 13, per berkas tidak naik). Belum dipotret
(integrator: 1280/1024/390 px).

| Layar | (1) tabel ≤ kartu, aksi lekat | (2) bantalan kartu | (3) kepala tidak dijejali | (4) tombol mati beralasan | (5) status ikon+teks+warna | (6) cari/saring | (7) teks ≠ izin | (8) kosong/angka 0 |
|---|---|---|---|---|---|---|---|---|
| **Faktur Keluaran** (`TaxInvoices.jsx`) | 9 kolom; kini `data-table head-wrap` (judul boleh dua baris), kolom Aksi `col-sticky-end` (+ sorot baris PK-44 tetap); tombol Rincian ikon | `section-head`/`section-body` (tetap); Rincian = `DetailModal` berisi `section-card` + `section-head`/`section-body` | Kepala tetap judul + Muat ulang; lencana ada di sel/rincian, bukan di kepala | Tidak ada tombol mati baru | Status `status-pill` ikon + teks + token (dulu warna+teks hex); lencana "Data pajak belum lengkap" ikon segitiga | Kotak cari + `FilterChips` sudah ada; daftar berhalaman | Teks pilihan kode: "Pilihan = kode transaksi yang dipakai PT ini (Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak)." | Kosong dibedakan: "Belum ada Faktur Pajak." vs "Tidak ada faktur yang cocok dengan saringan."; faktur lama tanpa potret: kalimat aturan lama, bukan angka 0 |
| **Form pelanggan › Data pajak** (`CustomerTaxSection.jsx`) | Tidak ada tabel | `FormSection` bernomor 6, terlipat dengan ringkasan (dibuka saat ubah) | — | Tidak ada tombol mati; NIK wajib → masuk daftar "Lengkapi: …" di kaki pop-up (pola yang ada) | Peringatan bentuk = teks `kn-warning-text` di bawah isian (bukan status) | — | Kode: "Ikut PT" + daftar kode PT | Isian kosong = placeholder "Sama dengan nama/alamat toko" |
| **Checkout › Review** (`CheckoutNonPpn.jsx`, `CheckoutStep3.jsx`) | — | `section-card section-pad` | — | Tombol buat mati saat alasan < 10 huruf: label tombol "Isi Alasan Tanpa PPN" + keterangan di bawah isian "Alasan wajib diisi, minimal 10 huruf (sekarang n)." | — | — | Hanya dirender bila `can(perms,"order","tax_override")` dan PT PKP; tanpa izin tidak tampil (tidak ada teks "bukan wewenang") | Ringkasan "PPN Tanpa PPN (0)" dan "Pesanan tanpa PPN — Faktur Pajak tidak diterbitkan." (bukan "Entitas non-PKP") |
| **Detail pesanan** (`OrderDetailPanel.jsx`) | — | Dalam kotak ringkasan harga yang ada | Satu baris teks, tidak di kepala | — | Catatan tanpa PPN = teks netral (bukan status) | — | — | Baris "Aturan pajak" hanya bila ada potret (pesanan lama: tidak tampil, bukan "0") |
| **Form produk** (`VariantEditor.jsx`) | — | Blok `p-3` berbatas `kn-divider` | Judul blok + lencana dalam satu baris pendek | — | Lencana "belum dipakai mesin" ikon Info + teks | — | — | Keterangan "PPN pesanan masih dihitung dari aturan pajak PT …" |
| **Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak** (sub-judul Pajak) | Kartu baku Pusat Pengaturan (tanpa kode layar baru); 12 kunci di sub-judul (≤ 14) | baku | baku | baku | baku | baku | Izin kunci `accounting.manage` | `verify_config_text` 0 pelanggaran |

## Penggabungan ke HEAD cabang (aturan pemilik 14 Nov)

Worktree tujuan disetel ke HEAD cabang **`f05d8da`** ("STATUS: keputusan pemilik H1 …"; memuat KP-T9, PK-44, perbaikan
tampilan & penjaga sejak `b5b7539`). 47 berkas unit (42 ubah + 5 baru; tanpa `backend/.env` dan `hasil/`):

| Kelompok | Berkas | Keputusan |
|---|---|---|
| Sama di HEAD dan basis → salin | 36 berkas (semua berkas server, uji, `pricing.js`, `taxBreakdown.js`, form pelanggan, checkout, produk, `configKeyIndex.json`, `config_fallback_allow.json`) | Disalin apa adanya |
| Baru → salin | `tax_config_service.py`, `test_TXT1_pengaturan_pajak.py`, `txt1PengaturanPajak.test.js`, `CustomerTaxSection.jsx`, `CheckoutNonPpn.jsx` | Disalin |
| Gabung tiga arah bersih | `ENTITY_REGISTRY.md`, `backend/routers/settings.py` (KP-T9: nama modul 403 dari katalog + TX-T1: bagian pajak efektif), `OrderDetailPanel.jsx` (PK-44 fokus dokumen + baris "Aturan pajak") | `git merge-file` tanpa bentrok |
| **Bentrok** `TaxInvoices.jsx` | PK-44 menambah sorot baris (`row-focus`, `useFocusDoc`, `FocusNotice`) pada baris `<tr>` yang juga diganti TX-T1 (tabel baku) | **Keduanya dipertahankan**: `<tr className={f.id === sorot ? "row-focus" : undefined}>` + sel TX-T1 berkelas token; `FocusNotice` dan pencarian nomor PK-44 tetap |
| **Bentrok** `KN_32_GLOSARIUM…` | KP-T9 §9.5 dan PK-44 §9.6 di tempat yang sama dengan §9.5 TX-T1 | Keduanya dipertahankan; bagian TX-T1 menjadi **§9.7** |
| **Bentrok** `memory/PRD.md` | Entri PK-44 di tempat entri TX-T1 | Keduanya dipertahankan (TX-T1 di atas PK-44) |
| `CODEBASE_MAP.md` | Bentrok angka | Diambil dari HEAD lalu dibangkitkan ulang `gen_codebase_map.py` |
| Penyesuaian dengan KP-T9 | Teks letak di layar | "Pusat Pengaturan › Pajak" → **"Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak"** (hub/tab KP-T9) di Faktur Keluaran dan Data pajak pelanggan; glosarium & PRD ikut (dibuat juga di worktree kerja) |

Hitungan uji lama: registry HEAD = 436 kunci seperti basis (KP-T9/PK-44 tidak menambah kunci, `test_KFT1_izin_pengaturan.py`
sama di HEAD) → `TXT1_KUNCI = 7`, registry 443; `access_modules.py` tidak berubah (fixture akses tidak dibangkitkan);
tidak ada indeks wajib atau izin bawaan baru (PK-14/PRT9 tetap). `configKeyIndex.json` dibangkitkan ulang (+7 kunci).

Perbaikan sesudah gabung (dibuat di kedua worktree): penjaga statik `verify_config_fallback.py --self-test` merah di
tujuan (HEAD hijau) — uji-dirinya menyuntik cadangan palsu `tax.ppn_rate` ke `services/config_service.py`, yang bukan lagi
pemakai terdaftar kunci itu. `services/config_service.py:compute_tax` dipulihkan sebagai pemakai `tax.ppn_rate` (memang
memakai tarif dari potret; docstring menyebut kuncinya) → uji-diri PASS, `verify_config_fallback` 0 pelanggaran,
`audit_config_wiring --strict` bersih; 508 uji terkait (TX-T1, KF-T2/T3/T4, putaran KF-T8) lulus di kedua worktree.

Angka di worktree tujuan (pembanding = salinan bersih `git archive f05d8da`):

| Pemeriksaan | HEAD cabang `f05d8da` | Tujuan (HEAD + TX-T1) |
|---|---|---|
| tests_mem penuh | 1328 lulus / 2 dilewati / 4 xfail | **1355 / 2 / 4** (+20 TX-T1, +7 putaran kunci baru) — diulang sesudah perbaikan uji-diri: 1355 / 2 / 4 |
| jest penuh | 127 suite (35 gagal muat `@radix-ui`), 762 uji lulus | 128 suite (+`txt1PengaturanPajak`, 7 uji); 769 uji: 767 lulus di jalan penuh + 2 uji `prepD1GateV2` (RFID, tidak disentuh) kena batas waktu 5 dtk saat mesin sibuk — dijalankan sendiri 6/6 lulus |
| `hitung_penjaga.sh` | auth 28 · ui_standard 13 · i18n 104 · create_modal 6 · page_tabs 1 · to_list 6 · entity_label 2 · sisanya 0/PASS | **identik** |
| Baris STATIK `gate.sh` (66 + `entity_write_guard`) | 14 baris keluar ≠ 0 | 14 baris yang sama keluar ≠ 0 (semua juga merah di HEAD: auth, compliance, create_modal, page_tabs, to_list ×2, atomic_claim ×2, ux_audit, ref_unlink, i18n, entity_label uji-diri, warehouse_scope uji-diri); `verify_config_fallback --self-test` hijau sesudah perbaikan di atas |
| `verify_role_gate_ui` | PASS 31 | PASS 31 |
| `verify_config_fallback` / `--entity` | 0 tersisa (135 pengecualian) / 0 (1) | 0 tersisa (**132** pengecualian: 3 basi dibuang) / 0 (1); uji-diri PASS |
| `verify_payment_vocab` | PASS 1748 | PASS 1751 |
| `verify_access_catalog_nav` | 0 temuan | 0 temuan |
| `verify_config_text` | PASS (436 kunci) | PASS (443 kunci, 3115 cek) |
| `gen_config_key_index --check` | selaras | selaras |
| `audit_config_wiring --strict` (salinan berjalur) | bersih | bersih — 451 kunci (registry 443), ORPHAN_UI 0; uji-diri PASS |
| `check_nav_map` (salinan berjalur) | PASS | PASS |

### Integrator — pemasangan di cabang (di atas `5097cda`)

Sesudah gabungan pelaksana, cabang maju dengan CR-T1 (profil kredit di form pelanggan), PK-31, AG-T1, dan PM-T2 (cara
bayar di checkout). Bentrok dan keputusan (keduanya dipertahankan):

| Berkas | Bentrok | Keputusan |
|---|---|---|
| `backend/routers/customers.py` (buat pelanggan) | CR-T1 mengganti batas kredit dengan usulan plafon (`credit_limit: 0` + `_usulan_plafon`) di tempat TX-T1 menambah `tax_profile` | `"npwp": _pajak["npwp"], **tax_profile, "credit_limit": 0`; sesudah `_usulan_plafon` jawaban tetap memuat `tax_data_warnings` |
| `frontend/src/features/crm/CustomerFormModal.jsx` | CR-T1 menata ulang bagian (plafon jadi permohonan) | Versi CR-T1 + tambahan TX-T1: `CustomerTaxSection` bernomor 6, kode PT dari `/settings/effective`, validasi NIK, `tax_profile` di muatan; isian NPWP lama dibuang (pindah ke Data pajak) |
| `frontend/src/features/pos/CheckoutDrawer.jsx` | PM-T2 mematikan tombol buat bila cara bayar belum dipilih | Tombol mati bila `payMethodMissing \|\| nonPpnInvalid`; label `"Isi Alasan Tanpa PPN"` bila alasan kurang, label PM-T2 tetap untuk cara bayar |
| `backend/tests_mem/test_KFT1_izin_pengaturan.py` | Konstanta kunci CR-T1, AG-T1, PM-T2 | Total = `... + CRT1_KUNCI + AGT1_KUNCI + PMT2_KUNCI + TXT1_KUNCI` |
| `CODEBASE_MAP.md`, `configKeyIndex.json` | Berkas hasil | Dibangkitkan ulang |

Angka di HEAD cabang sesudah PK-18 (`a48a0a9`, memuat TX-T1): tests_mem **1458 lulus / 2 dilewati / 4 xfail**; jest penuh
**802 lulus**; penjaga statik identik dengan garis dasar sesi; `verify_config_text` 3157/0; `audit_config_wiring --strict`
hijau.

## Bukti

`bukti/TX-T1/`: `merah_kode_lama.log`, `tests_mem_sebelum.log`, `tests_mem_sesudah.log`, `putaran_KFT8_kunci_pajak.log`,
`penjaga_sebelum.log`, `penjaga_sesudah.log`, `hijau_kode_baru.log`, `salinan_d4_tests_mem.py`; gabungan:
`tests_mem_HEAD_cabang.log`, `tests_mem_T_gabungan.log`, `tests_mem_T_gabungan_ulang.log`, `jest_HEAD_jest.log`,
`jest_T_jest.log`, `statik_HEAD.tsv`, `statik_T.tsv` (kode keluar per baris STATIK), `penjaga_HEAD.log`, `penjaga_T.log`,
`catatan_ulang.txt`.

## Gate

Dijalankan integrator di lingkungan A (MongoDB 7 asli) sesudah `restore_demo` (data acuan), di `a48a0a9` — satu gate untuk
enam unit yang digabung bersamaan (CR-T1, PK-31, AG-T1, PM-T2, TX-T1, PK-18) — lalu `--quick` diulang di `f1b8239` sesudah
perbaikan cek layar (hanya layar):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `--quick` (`a48a0a9`) | 14 FAIL | 16 | 1 (ganti nama `guard:page_tabs` oleh MN-T1, merah garis dasar yang sama: `InventoryStockView`) | 2 (`config_wiring` + uji-diri) |
| `--ci` (`a48a0a9`) | 41 FAIL | 43 | 1 (ganti nama) | 2 |
| `--quick` (`f1b8239`) | 14 FAIL | 16 | 1 (ganti nama) | 2 |

Kuitansi: `bukti/TX-T1/gate_quick_receipt.md`, `gate_ci_receipt.md`. Lapis A unit-unit itu (6 berkas `tests/test_bp_*`) di
lingkungan A: 19 lulus.

Pelaksana (tanpa lingkungan A) — pengganti: seluruh
baris STATIK `gate.sh` dijalankan satu per satu di worktree tujuan dan HEAD cabang (`statik_*.tsv`), `hitung_penjaga.sh`,
`verify_config_fallback` (+`--entity`), `verify_payment_vocab`, `verify_access_catalog_nav`, `verify_role_gate_ui`,
`verify_config_text`, `gen_config_key_index --check`, `audit_config_wiring --strict` dan `check_nav_map` lewat salinan
berjalur. Angka di bagian Penggabungan.

## Menyimpang dari blueprint

1. **Kelompok `pajak` → `pajak-pembukuan` sub-judul `pajak`.** Id kelompok `pajak` sudah alias KF-T4
   (`GROUP_ALIASES["pajak"] = ("pajak-pembukuan", "pajak")`); ditulis dengan id baku.
2. **`tax.kode_transaksi_bawaan` dan `…_dpp_nilai_lain` bertipe `enum` (pilihan = delapan kode), bukan `text`.** Nilai
   bawaan sama ("01"/"04"). Alasan: server menolak kode tak dikenal saat disimpan (teks bebas "01 uji" akan tersimpan lalu
   gagal di setiap penerbitan) dan pembangkit putaran KF-T8 bisa memilih nilai sah lain. Label pilihan = kodenya saja
   (keterangan arti kode = isi peraturan, tidak ditulis; lihat Menunggu pemilik).
3. **U1 dan U13 dipecah a/b.** Spesifikasi "merah kecuali U1, U13": bagian angka memang hijau di kode lama (bawaan =
   perilaku lama), bagian potret (`tax_snapshot`) merah. U12 juga hijau di kode lama karena PK-45 sudah menutupnya.
4. **U14 — faktor antar-PT dipotret di transaksinya.** Bacaan "DPP faktur transaksi yang SAMA berubah menjadi
   12.000.000" bertentangan dengan D3 dan tujuan unit (PPN transaksi itu sudah 11 %); maka transaksi yang dibuat sesudah U4
   memakai 12/12 (12.000.000), transaksi lama tetap 11/12. "Faktor dibaca dari tempat yang sama" = `tax_settings`.
5. **Pemanggil hitung ulang lebih banyak dari tabel spesifikasi** (D3 konsisten): batal baris, persetujuan, kurang ambil,
   potong katalog, sampel, harga kontrak pesanan khusus → PO, amandemen PO. Retur (`return_service`,
   `purchase_return_service`) **tidak diubah — tidak berlaku**: sudah memakai rasio PPN dokumen asal, bukan pengaturan.
6. **Dokumen pembelian lama tidak menyimpan `dpp_nilai_lain`** → potret turunan menebak dari angka (DPP ≈ 11/12 × harga
   sebelum PPN), sama dengan `pdf_resolvers._uses_dpp_nilai_lain`. Tanpa ini amandemen PO lama akan pindah ke 12 % datar.
7. **Rupiah penuh**: total = harga + PPN (tidak dibulatkan lagi, D5); harga termasuk PPN menghitung PPN dulu supaya PPN
   bulat dan harga jual + PPN = subtotal. Cara dua desimal memakai urutan lama persis.
8. **`set_nsfp` memeriksa daftar kode hanya bila kodenya diganti** — faktur yang sah saat terbit tetap bisa diisi NSFP
   walau kodenya kemudian dikeluarkan dari daftar PT.
9. **`POST /api/customers` juga menerima `tax_profile`** (form buat = form ubah) dan memeriksa NPWP dengan aturan yang
   sama; spesifikasi hanya menyebut PATCH.
10. **Uji lapis A lama `tests/test_decisions_d4.py` disesuaikan**: uji itu mematok setelan pajak lewat
    `get_effective_settings`; mesin kini membaca `tax_settings`, jadi pematok ikut diarahkan ke sana (setelan sama).
11. **`GET /api/settings/effective` bagian `tax` diisi nilai mesin** (tidak menambah kunci ke `DEFAULT_GLOBAL_SETTINGS`) —
    jalan pratinjau POS/PO dan form pelanggan/faktur mendapat faktor, cara bulat, dan daftar kode per PT.

## Usulan koreksi blueprint (teks pengganti persis)

- Bagian Pengaturan, kalimat pertama: ganti "Semua: group `pajak`, scopes" → "Semua: group `pajak-pembukuan` (sub-judul
  `pajak`), scopes".
- Tabel Pengaturan, baris `tax.kode_transaksi_bawaan`: ganti "`text` · `"01"`" → "`enum` (pilihan = kode
  `tax.kode_transaksi_diizinkan` bawaan) · `"01"`"; baris `tax.kode_transaksi_bawaan_dpp_nilai_lain`: "`text` · `"04"`" →
  "`enum` (pilihan sama) · `"04"`".
- Langkah kerja 1: ganti "U1–U15; merah kecuali U1, U13." → "U1–U15; merah kecuali bagian angka U1 dan U13 (bawaan =
  perilaku lama) dan U12 (sudah ditutup PK-45)."
- Uji U14, kolom Langkah: ganti "Hitung DPP faktur antar-PT sebelum dan sesudah U4" → "Hitung DPP faktur transaksi
  antar-PT yang dibuat sebelum U4 dan transaksi baru sesudah U4"; Hasil: "11.000.000; 12.000.000; transaksi lama tetap
  11.000.000 (faktor dibaca dari tempat yang sama, dipotret di transaksi)".

## Asumsi / Menunggu pemilik

- **(konfirmasi konsultan pajak)** Faktor 11/12, daftar kode transaksi (delapan kode lama, tanpa 05), bawaan 01/04, bentuk
  NPWP 15/16 digit dan NIK 16 digit (hanya peringatan). Nilainya = kode lama; tidak ada yang ditambah (H4).
- Keterangan arti tiap kode transaksi di pilihan (mis. "04 — DPP nilai lain") tidak ditulis: isi peraturan. Usulan:
  pemilik/konsultan memberi teksnya, dipasang sebagai label pilihan registry.
- Cadangan tarif antar-PT `or 12.0` bila tarif PT penjual 0 (`interco_service._interco_rate`) adalah tarif tertulis di
  kode yang **sudah ada**; tidak diubah unit ini (bukan butir spesifikasi). Usulan: unit pajak antar-PT menggantinya dengan
  pengaturan.
- Faktur internal antar-PT tetap berkode bawaan "01" bila tidak diisi (`interco_tax_service`); spesifikasi tidak
  menyebutnya. Usulan: TX-T2 memakai `default_kode`.
- `tax_override_by` menyimpan nama pembuat (tampilan "dibuat {nama}"); id pembuat sudah ada di `created_by`.
- Kunci baru tidak `bertanggal`: tanggal sebelum baris pengaturan pertama = nilai sekarang (ASUMSI spesifikasi).

## Titik henti

- H3: spesifikasi meminta **tanpa migrasi** (dokumen lama dianggap berpotret aturan lama); tidak ada skrip data.
- H4: tidak ada tarif, faktor, kode, atau isi peraturan baru.
- H7: tidak menyentuh RFID/middleware.

## Hambatan lingkungan

- Suite jest yang memuat `cmdk`/`@radix-ui` tidak termuat (sama di HEAD); asersi pajak `decisionsD1` (rincian PPN) dan
  `phase4R2` (Faktur Pajak) disalin ke uji sementara dengan `KNSelect` ditiru → lulus.
- Pelaksana tidak menjalankan lapis A (larangan database `backend/.env`); integrator menjalankan `tests/test_decisions_d4.py` di
  lingkungan A: **4 lulus** (`bukti/TX-T1/lapisA_d4_integrator.txt`).

## Yang perlu direview

- Arah D3 di semua jalur hitung ulang (Menyimpang 5) dan tebakan bendera DPP nilai lain PO lama (Menyimpang 6).
- Pembacaan U14 (Menyimpang 4).
- Kunci kode bawaan sebagai `enum` (Menyimpang 2).
