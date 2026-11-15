# Evaluasi eksekusi blueprint dan bahan review — 15 Nov 2026

Disusun integrator di akhir sesi eksekusi atas permintaan pemilik, sebagai bahan sesi review berikutnya. Semua angka
diukur dari repo, log gate, dan log sesi; cara ukurnya ditulis di tiap bagian. Keputusan dan rencana yang berlaku ada di
`STATUS.md` ("Menunggu pemilik", "Jawaban pemilik 15 Nov 2026", "Rencana berikutnya").

## 1. Keadaan akhir

- Unit: **97 selesai, 7 tahan** (PK-03 H3, PK-04 H2, PK-34 H2, PK-35 H2/H3, PK-46 H4, PM-T5 H8, TX-T3 H8). Tidak ada unit
  `siap`.
- Tracker: 348 temuan `implemented_pending_review` (menunggu validasi reviewer), 6 `open` (DB-02, DB-03, DB-04, GL-11, IV-11
  — semuanya menunggu PK-04/PK-34/PK-35 — dan ENV-03).
- Gate terakhir (`7183e4f`): `--quick` 12 merah, `--ci` 39 merah (garis dasar 13 Nov: 16 / 43).
- Belum ada yang dipasang ke server produksi; belum ada skrip yang dijalankan pada data nyata.

## 2. Perubahan sejak blueprint mulai (basis `fb6bc75`, 13 Nov 19:16 UTC)

`git diff --shortstat fb6bc75 7183e4f` per folder:

| | Jumlah |
|---|---|
| Commit | 276 (sampai `1bbf3b4`) |
| Backend | 727 berkas, +126.844 / −10.929 baris (termasuk uji) |
| Frontend | 552 berkas, +52.343 / −8.946 baris |
| Skrip | 71 berkas, +9.805 / −495 baris |
| Dokumen | 1.567 berkas, +98.903 baris (190 laporan unit, 220 potret layar) |
| Uji | `backend/tests_mem` 0 → 135 berkas (±2.312 uji, hijau); 72 berkas lapis A `test_bp_*`; 90 suite jest baru |

Ringkasan per area (sebelum → sesudah) ada di laporan unit `docs/reviews/2026-11-13/hasil/`; garis besarnya: wewenang dari
izin; aturan bisnis menjadi pengaturan per PT; satu pintu per jenis transaksi uang dengan penanda Posting Gagal;
gerbang kredit satu mesin; cara bayar & rekening ber-peruntukan; pajak bertanggal berlaku; gaji per PT; Capaian dan
Lembar Insentif; asisten AI lewat pintu aplikasi; menu & form bayar disatukan.

## 3. Waktu dan biaya

**Waktu.** Eksekusi berlangsung 13 Nov 19:18 UTC → 15 Nov 18:16 UTC (±47 jam). Diukur dari log sesi (perintah yang
benar-benar menjalankan uji; pola ketat):

| Yang terjadi | Angka |
|---|---|
| Agen pelaksana | 85 agen, total ±162 jam-agen (paralel), rata-rata ±2 jam per agen |
| Langkah model / pemanggilan alat | ±24.300 / ±25.000 |
| `tests_mem` penuh (±7,5 menit) | ±480 kali (±410 agen, ±70 integrator) |
| Jest penuh | ±170 kali |
| Gate (restore + `--quick` 92 dtk + `--ci` 462 dtk) | ±90 kali; tidak bisa paralel (satu lingkungan A) |
| Konteks sesi utama dimampatkan | 8 kali |

Penyebab pengulangan (bukan putaran tanpa akhir): suite penuh yang sama 3–4 kali per unit; gate per unit sebelum mode
hemat; gabung ulang karena cabang bergerak (KM-T3 6 kali); menunggu uji 7–8 menit dengan cache konteks 5 menit sehingga
konteks ±400 ribu token ditulis ulang; sesi utama terlalu panjang. Aturan pencegahnya sekarang `03_LINGKUNGAN_UJI.md` §6.

**Biaya setara harga API** (bukan tagihan langganan; tarif Claude Opus 5.5: input $4, output $20, baca cache $0,20 per juta
token; tulis cache diasumsikan 1,25× input untuk cache 5 menit dan 2× untuk 1 jam; periode sebelum blueprint sebagian besar
memakai Claude Fable 5.2: $8 / $40):

| Periode | Biaya | Rincian |
|---|---|---|
| Eksekusi blueprint | **≈ $3.390** (≈ $35 per unit) | sesi utama $502 + agen $2.887; baca konteks $2.097 (62%), tulis cache $850 (25%), output termasuk berpikir $441 (13%) |
| Sebelum blueprint (8–13 Nov: audit, rencana, penyusunan blueprint) | ≈ $700 | |
| Total sesi | ≈ $4.090 | |

Token eksekusi: 24.314 permintaan, output 22,0 juta, baca cache 10,48 miliar, tulis cache 165 juta; rata-rata konteks
±431 ribu token per langkah. Semua langkah (sesi utama dan agen) memakai effort `xhigh`. Pendorong biaya terbesar adalah
konteks besar × banyak langkah, bukan effort; menurunkan output separuh hanya menghemat ±6–7%.

## 4. Pelanggaran baru yang lolos gate selama eksekusi

Pembanding gate lama menilai per status (hijau → merah). Gate yang sudah merah di garis dasar bisa bertambah pelanggaran
tanpa terlihat. Dibandingkan per pelanggaran (`scripts/blueprint/bandingkan_pelanggaran_gate.py`, garis dasar
`docs/reviews/2026-11-13/garis-dasar/08_gate_ci.log` → log gate `7183e4f`):

| Gate | Baru | Isi |
|---|---|---|
| `guard:approval_queues` | +7 | Pintu keputusan tanpa antrean Pusat Persetujuan: `cash-deposits/{id}/reject`, `hr/compensation/{id}` approve/reject, `hr/assignments/{id}` approve/reject, `hr/payroll/inputs/{id}/approve`; status `waiting_approval` di `fact_sales_lines` |
| `guard:numeric_bounds` | +2 | `PayInputCreate.amount`, `RemittanceInput.amount` menerima negatif |
| `guard:ref_unlink` | +2 | `incentive_facts.py` nama koleksi dinamis; `interco_tax_service.py` menghapus dokumen tanpa menyapu tautan |
| `audit_entity_isolation` | +1 | Router menyentuh koleksi ber-PT tanpa pagar |
| `audit_sales_roles_ux` | +12 | Layar memanggil endpoint yang tidak diizinkan perannya (mis. Piutang → `/bank-accounts` untuk Sales) |
| POC E-7 | +6 | Pemeriksaan pindah aset / pinjaman antar-PT merah — perlu dipilah: regresi atau POC basi |
| `guard:qty_dual` | +1 | Data: `interco_returns` belum punya `items.qty_rolls` |

Belum dibereskan. Garis dasar per pelanggaran yang baru: `docs/blueprint/garis-dasar-gate/2026-11-15_gate_ci.log`.

## 5. Relevansi uji, skrip, dan gate

| Bagian | Isi | Penilaian |
|---|---|---|
| `backend/tests_mem` | 135 berkas, ±2.312 uji, hijau | Relevan; jaring pengaman utama. Kelemahan: database tiruan, bukan MongoDB asli |
| Lapis A blueprint `backend/tests/test_bp_*` | 72 berkas | Relevan (dijalankan integrator di lingkungan A) |
| Uji backend lama `backend/tests/` | ±403 berkas dari sebelum blueprint | Tidak terjamin: tidak dijalankan rutin, sebagian diketahui merah (mis. ubah plafon lewat PATCH yang sudah dicabut PK-45) |
| Jest | 173 suite | 35 suite tidak pernah termuat di lingkungan ini (`cmdk`/`@radix-ui`) — titik buta |
| Gate `--ci` | 141 pemeriksaan, 39 merah permanen | 16 dari 28 POC merah, sebagian basi (POC U dan I gagal karena PT memakai mode GRN); penjaga statik merah sebagian temuan nyata (8 endpoint gudang tanpa pagar PT), sebagian tuduhan palsu (`auth_coverage` menuduh ekspor Tanya KN tanpa login, padahal `get_result` memanggil `_ai_user`) |
| Rantai data acuan | `restore_demo` | Gagal di `seed_demo_transaksi_kn.py` dan `seed_p03_kn.py` sejak sebelum blueprint; sebagian pemeriksaan merah karena data tidak lengkap |

## 6. Peta cakupan: kode yang belum pernah diperiksa

`python3 scripts/blueprint/peta_cakupan_audit.py` — berkas yang tidak disebut dokumen audit (keuangan, konfigurasi-peran,
middleware RFID) maupun spesifikasi unit blueprint, dan tidak diubah sejak `fb6bc75`. "Disentuh" tidak sama dengan
"diperiksa logikanya": banyak berkas disentuh hanya untuk izin atau pagar PT.

| Bagian | Total | Belum disentuh |
|---|---|---|
| `backend/routers` | 176 berkas, 47.901 baris | 20 berkas, 2.755 baris (6%) |
| `backend/services` | 443 berkas, 164.462 baris | **170 berkas, 36.041 baris (22%)** |
| `frontend/src/features` (`.jsx`) | 867 berkas, 154.974 baris | **503 berkas, 68.720 baris (44%)** |

Terbesar yang belum disentuh: gudang & stok (`putaway_order_service`, `receiving_roll_service`, `stock_bucket_service`,
`fulfillment_service`, `fulfillment_decision_service`, `warehouse_profile_service`, `putaway_draft_service`,
`gate_txn_service`); pembelian (`supplier_service`, `supplier_item_service`, `po_board_service`); penjualan
(`pricelist_service`, `sales_p04_service`, `special_order_routing`, router `customer_prices`, `pos`); produksi
(`repair_order_service`, router `process_recipes`); RFID cetak & handheld (`rfid_print_service`, `rfid_printer_protocol`,
`handheld_sync` — aturan H7); `bank_statement_parser`; R&D (`rnd_kpi_service`). Layar: sales ±11 rb baris, WMS ±9,7 rb,
purchasing ±8,9 rb, R&D ±5,3 rb.

Tanda masalah yang sudah terlihat di area ini: nama PT mentah di handheld "Daftar Awal" (`handheld_tasks.py` membaca
koleksi `entities` yang kosong); celah kredit pesanan custom (§7); 8 endpoint tulis memilih gudang tanpa pagar PT
(mis. `cutting.py::receive`); POC lini produk, tahapan proses, sampling merah.

## 7. Celah kredit pada Pesanan Khusus (custom order)

- Pemeriksaan kredit baru berjalan saat harga dikunci: `lock_price` (`routers/special_orders.py:696`) membuat SO lewat
  `convert_special_order_to_so` → `create_order` (titik `pesanan_dibuat`).
- Bila pelanggan tertahan (409 `CREDIT_BLOCKED`), kegagalan ditangkap dan hanya dicatat `shipping_error: "SO otomatis
  gagal: …"` (`routers/special_orders.py:719–723`); kunci harga tetap berhasil.
- Dengan `auto_po`, `p2.lock_price` menjalankan `auto_procure` (PR → PO ke pemasok) sebelum SO dibuat
  (`services/special_order_phase2.py:655`); pengadaan manual (`POST /special-orders/{id}/procure`,
  `routers/special_orders.py:729`) tidak memeriksa kredit.
- Usulan (menunggu konfirmasi pemilik): periksa kredit sebelum pengadaan/produksi Pesanan Khusus; tahan pengadaan sampai
  izin kredit atau DP diterima (persen DP sebagai pengaturan); opsional periksa ulang saat surat jalan. Pesanan biasa
  tetap satu titik (pesanan dibuat) sesuai pemilik.

## 8. Cara insentif yang berlaku sekarang (komisi otomatis) vs Lembar Insentif

Semua PT masih memakai komisi otomatis (`hr.payroll_commission_mode` = `accrue_then_settle`). Lembar Insentif (KM-T3/T4/T5)
sudah ada tetapi belum dinyalakan.

Komisi otomatis (`services/sales_force_service.py:192`, strategi bawaan `per_sku`):
1. Tarif per kategori barang (per PT atau "Semua PT"), mis. Rp 3.000 per satuan dasar.
2. Pesanan dihitung milik sales bila pelanggannya ditugaskan ke sales itu atau sales tercantum di tim pesanan, di PT itu.
3. Hanya bagian pesanan yang dibayar dalam bulan itu (fraksi terbayar = pembayaran dalam periode ÷ total pesanan).
4. Per baris: kuantitas terbayar × tarif × faktor diskon (diskon baris > 10% → ×0,5; bisa "potong Rp" atau hangus).
5. Dibatasi 50% laba kotor baris (`commission.default_margin_cap_pct`).
6. Akrual bulanan manual: Dr 6-5000 Beban insentif / Cr 2-1500 Hutang insentif; proses gaji menghitung ulang komisi untuk
   slip dan melunasi 2-1500 (`hr_payroll_service._commission_for`).
7. Strategi arsip `achievement_tiered`: persen pencairan bertingkat menurut capaian target + bonus pelanggan baru.

Kelemahan menurut audit: dihitung ulang tiap dibuka; tanpa keputusan atasan; tidak bisa dimatikan per PT (PY-06, kini
bisa); daftar sales tidak seragam (KM-07). Lembar Insentif: nominal diputuskan manajer dengan melihat Capaian, angka dasar
dipotret, disahkan, dijurnal saat disahkan, dibayar lewat gaji.

## 9. Temuan di luar cakupan unit (belum dikerjakan)

- `services/handheld_tasks.py` membaca nama PT dari `db.entities` (kosong) → kode PT mentah di handheld "Daftar Awal".
- `SoTrackerCard` masih memakai warna hex dan huruf < 12 px.
- `penalty_service.waive` memeriksa nama peran.
- Parameter `?today=` pada akrual denda.
- Daftar Pesanan sempit di 1024 px saat panel rincian terbuka; Pusat Amandemen di 1024 px.
- Beberapa tanggal bawaan memakai zona waktu peramban.
