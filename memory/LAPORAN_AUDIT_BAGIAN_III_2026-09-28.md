# Validasi & Perbaikan — Audit Kode KNHOST Bagian III (2026-09-28)

Semua temuan dibaca ulang terhadap kode. Status: **BENAR+DIPERBAIKI**, **SEBAGIAN** (bagian yang terbukti diperbaiki, sisa dicatat), **PERLU KEPUTUSAN** (butuh keputusan bisnis/pemilik).
Penanda di kode: `KN-Exx` / "temuan lama #n".

## E.1 Koreksi pesanan
| ID | Status | Perbaikan |
|---|---|---|
| E01 | BENAR+DIPERBAIKI | sales_name tidak lagi hardcode (FE `useAppActions.js`, `schemas.py`); server isi dari PIC sales_team → user login; kepemilikan hanya via id (created_by, sales_id, sales_team.sales_id), bukan nama; sales tak bisa PATCH sales_name. Skrip data lama: `scripts/fix_sales_name_e01.py [--apply]`. |
| E02 | BENAR+DIPERBAIKI | `routers/amendments.py::_guard_doc` — preview/propose/detail/doc/decision cek entitas + pemilik. |
| E03 | BENAR+DIPERBAIKI | Ambang dihitung dari total AWAL + akumulasi Σ|delta| amandemen; harga baru lewat price_guard (di bawah lantai → wajib approval); harga 0 ditolak kecuali baris sampel. |
| E04 | BENAR+DIPERBAIKI | (a) tax_override pesanan diteruskan; (b) diff diterapkan ke baris TERKINI; (c) CAS status `pending_approval` (klik ganda → 1 nota); (d) qty → base_quantity & backorder ikut, tak boleh di bawah reservasi. Sisa: dokumen `backorders` terpisah tidak disesuaikan. |

## E.2 GRN
| ID | Status | Perbaikan |
|---|---|---|
| E05 | BENAR+DIPERBAIKI | `refresh_counted` CAS versi yang dibaca + retry baca ulang. |
| E06 | BENAR+DIPERBAIKI | Preflight sebelum `closing` (tugas, PO terminal, lot mode blokir, langkah MKO); endpoint + tombol `return-to-reconcile`; PO cancel/short-close menolak tugas dipegang GRN (cancel juga tak lagi membatalkan tugas completed). |
| E07 | BENAR+DIPERBAIKI | start-count menolak langkah MKO yang sudah diterima / sedang dihitung GRN lain. **Terima bertahap**: GRN makloon ditandai "Terima sebagian" (`POST /goods-receipts/{id}/mko-partial`) → kiriman ditahan di `steps[].partial_receipts`; kiriman terakhir (GRN atau layar lama) memposting semua roll sekaligus (satu konsumsi WIP & satu tagihan jasa). |
| E08 | BENAR+DIPERBAIKI | confirm-measure menolak roll GRN + guard mode GRN. |
| E09 | BENAR+DIPERBAIKI | Roll terakhir dibatalkan → tugas kembali `waiting_goods`; guard legacy hanya bila ada roll lama tanpa grn_id. |
| E10 | BENAR+DIPERBAIKI | Eskalasi lewat guard GRN & tidak untuk tugas dipegang GRN; resolve tanpa barang kembali ke status asal, bukan qc_check. |
| E11 | BENAR+DIPERBAIKI | Resolusi selisih hanya terbawa bila angka (detail) sama. |
| E12 | BENAR+DIPERBAIKI | Parser token angka (Yds., ",-", rentang → ambigu, tak pernah raise); read_grn tangkap semua galat → review+read_failed; baca ulang dari review; gambar/PDF rusak ditolak jelas. |
| E13 | BENAR+DIPERBAIKI | Batal toleran roll sudah terhapus, release_tasks di finally, batal bisa diulang. |
| E14 | BENAR+DIPERBAIKI | colors/repeats langkah + output_warehouse_id = gudang GRN. |
| E15 | BENAR+DIPERBAIKI | complete_task via GRN tanpa roll → 409 (tak buat roll fiktif). |
| E16 | BENAR+DIPERBAIKI | Klaim atomik `supplier_roll_claims` (_id unik supplier|no roll). |
| E17 | BENAR+DIPERBAIKI | POST /wms/tasks inbound ditolak di mode GRN. |
| E18 | BENAR+DIPERBAIKI | expected_qty tugas = sisa PO. |
| E19 | BENAR+DIPERBAIKI | declared_qty_total sekali per GRN (`declared_grn_ids`). |
| E20 | BENAR+DIPERBAIKI | Angka 1% tertulis mati dihapus: roll_check memakai `receiving.line_qty_tolerance_pct`. `purchasing.receive_tolerance_percent` tetap terpisah karena kebijakannya berbeda (batas lebih-terima per PO, bukan selisih per roll). |
| E21 | BENAR+DIPERBAIKI | Tag RFID roll dibatalkan di-retire. |
| E22 | BENAR+DIPERBAIKI | Hitung buta: stub roll belum diukur tidak dikirim. |
| E23 | BENAR+DIPERBAIKI | re.escape pencarian GRN. |

## E.3 OCR
| E24 | BENAR+DIPERBAIKI | Model tanpa harga ditolak (OCR_PRICE) sebelum memanggil AI; anggaran dicek ulang sebelum pembaca kedua. |
| E25 | BENAR+DIPERBAIKI | Hitung halaman sebelum render; render di `asyncio.to_thread`. |
| E26 | BENAR+DIPERBAIKI | Detak `reading_heartbeat`; hasil run yang disapu tetap disimpan (swept_run_id). |
| E27 | BENAR+DIPERBAIKI | ocr_eval: kasus gagal dihitung salah & gerbang gagal, baris hilang = salah tak ditandai, baris karangan dihitung, pola halaman `sj1` ≠ `sj10`. |
| E28 | BENAR+DIPERBAIKI | Cocok "pasti" hanya token utuh. |
| E29 | BENAR+DIPERBAIKI | Nama fixture disanitasi; hasil `is_mock` + lencana UI. |
| E30 | BENAR+DIPERBAIKI | Berkas fisik dihapus, berkas yatim dibersihkan, cek magic byte, nosniff, gambar rusak ditolak; `sha256_original` = hash berkas ASLI dihitung di HP, `sha256_processed` = berkas tersimpan. |

## E.4 Tanya KN
| E31 | BENAR+DIPERBAIKI | pending_approvals: SO ber-apply_scope, PO hanya dengan purchase_order.view; shipments & returns disaring milik sales. |
| E32 | BENAR+DIPERBAIKI | `_safe_cell` apostrof untuk = + - @. |
| E33 | BENAR+DIPERBAIKI | Reservasi kuota atomik sebelum model; pemakaian dicatat di `finally`. |
| E34 | BENAR+DIPERBAIKI | Total/pembanding qty lintas satuan = kosong, porsi per satuan; analyze_change qty wajib per produk/satu satuan. |
| E35 | BENAR+DIPERBAIKI | Mode PPN included: gross & diskon tanpa PPN (berlaku setelah rebuild fakta). |
| E36 | BENAR+DIPERBAIKI | Peringatan eksplisit saat memakai posisi hari ini (AR, stok, AP). |
| E37 | BENAR+DIPERBAIKI | list_records menerapkan filters (dimensi tak didukung ditolak jujur), limit untuk semua jenis; run_report teruskan filters & as_of. |
| E38 | BENAR+DIPERBAIKI | "all" hanya bila berhak semua PT; commission-history lewat _kpi_scope; lihat sales lain hanya admin/manager/sales_admin/finance. |
| E39 | BENAR+DIPERBAIKI | Minus dibaca, tahun hanya konteks tanggal, toleransi = pembulatan tampilan, "m" (meter) bukan miliar. |
| E40 | BENAR+DIPERBAIKI | Konteks tanpa jam:menit, entitas terurut, riwayat dibatasi 60 item di batas pesan user. |
| E41 | BENAR+DIPERBAIKI | Jendela tumpang 10 menit, kunci sinkron, payment_status menyentuh updated_at, rebuild penuh tidak di request pengguna. |
| E42 | BENAR+DIPERBAIKI | Pagar lini untuk received/returns/low_stock/pencarian produk; atribusi list_records = fakta (created_by/sales_id/anggota sales_team). |
| E43 | BENAR+DIPERBAIKI | Markdown tidak merender gambar. |
| E44 | BENAR+DIPERBAIKI | Mock chat butuh env `AI_ALLOW_MOCK` (bawaan 1 di dev — set 0 di produksi); /narrative ikut kuota; /usage/daily non-admin hanya milik sendiri; analyze_change compare none → 400; blok kn-* rusak dibatasi ErrorBoundary. |

## E.5
| E45 | BENAR+DIPERBAIKI | PUT /settings: scope hanya global/id entitas, respons hanya seksi pengaturan. Kunci API dienkripsi Fernet (`KN_SECRETS_KEY` di backend/.env, migrasi malas). |
| E46 | BENAR+DIPERBAIKI | Cek entitas, cek pemasok grup, rnd_gate baris baru, cap supplier dipertahankan/di-resolve ulang, produk dimuat per id. |
| E47 | BENAR+DIPERBAIKI | generate varian memanggil color_lock.assert_can_use; ubah pemilik warna eksklusif hanya admin/manajer. |
| E48 | BENAR+DIPERBAIKI | RFQ→PO memakai duplicate_line_message. |
| E49 | BENAR+DIPERBAIKI | Idempotency-Key per niat + qty dikosongkan setelah kirim/antre. |
| E50 | BENAR+DIPERBAIKI | Semua tugas aktif dikirim; produk/gudang dimuat per id. |
| E51 | BENAR+DIPERBAIKI | Cek entitas buat pelanggan; keputusan izin warna: pagar entitas + CAS status; regex handle di-escape; qty pick HP kosong. |

## Temuan lama
| #12 | BENAR+DIPERBAIKI | Stok awal menerima HPP & berat; roll tanpa HPP ditandai dan muncul di peringatan "roll stok awal belum punya HPP" (isi cepat per roll); nomor roll unik. |
| #17 | BENAR+DIPERBAIKI | Payroll menghormati `bpjs_kes_enabled`/`bpjs_tk_enabled` per karyawan. |
| #18 | BENAR+DIPERBAIKI | Lihat E45. |
| #11 | BENAR+DIPERBAIKI | Ringkasan/velocity/top pelanggan: omzet NETO tanpa PPN, hanya pesanan terjual (tanpa draft/reservasi/menunggu approval), hari menurut WIB. |
| #13 | BENAR+DIPERBAIKI | Impor pelanggan: kode atomik & unik (kolom `code` opsional, indeks unik), sales penanggung jawab (`sales_email`/`sales_name`, wajib untuk baru), ganda dalam file ditolak, cek entitas grup; ekspor berformat sama & ter-scope entitas. |
| #14 | BENAR+DIPERBAIKI | Data CONTOH SDM/galeri/SO + akun demo hanya bila `KN_DEMO_DATA=true`; sandi akun awal dari `KN_INITIAL_PASSWORD` (mode non-demo tanpa env → sandi acak dicetak sekali di log). |
| #15 | BENAR+DIPERBAIKI | Sumbu varian "Lebar (cm)": nilai cm dikonversi ke meter saat generate varian (master produk menyimpan meter). |
| #16 | BENAR+DIPERBAIKI | PPN antar-PT mengikuti pajak penjualan PT penjual (12% × DPP Nilai Lain 11/12 = efektif 11%); faktur internal mencatat tarif nominal 12%, DPP 11/12 & flag DPP Nilai Lain; `antar_entitas.ppn_rate_percent` > 0 hanya untuk tarif flat khusus. |
| #19 | BENAR+DIPERBAIKI | Registri `USER_SCOPED_COLLECTIONS` / `SYSTEM_AI_COLLECTIONS` di entity_scope + tes `tests/test_registry_ai_collections.py`. |
| #6 / #8 | Tertutup oleh E46/E48 (#6); #8 jalur lama supplier_dn tidak diubah (GRN sudah mencatatnya). |
