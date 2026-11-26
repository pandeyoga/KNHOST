# H4 — Perbandingan komisi sales SEBELUM vs SESUDAH BTP

**Vonis: SAMA.** Seluruh 75 kombinasi (sales x PT x bulan) memberi total komisi identik, dan rincian baris per-artikel (nama, SKU, qty, tarif, komisi) juga identik.

## Fungsi yang dipakai
- `services.sales_force_service.compute_commission(sales_id, period, entity_id)` — mesin komisi yang dipakai "Insentif saya" (`incentive_me.komisi_otomatis`), Lembar Insentif, dan slip gaji. Murni hitung (tidak menulis; saldo potongan baru ditulis saat bulan difinalkan).
- `services.hr_payroll_service._commission_for(emp, period, entity_id)` — jalur slip gaji. SEBELUM mengembalikan angka (float), SESUDAH mengembalikan dict `{total, commission_raw, carry_in, carry_out, computed_at}`; `total` dibandingkan.
- Skrip: `h4_komisi.py` (hitung), `cmp.py` (banding). Keluaran: `before.json`, `after.json`.
- Versi: SEBELUM `f14b559`, SESUDAH `4e98a42`, masing-masing di worktree sendiri dan salinan DB sendiri (`h4_before`, `h4_after`, salinan `test_database`; data acuan tidak ditulis).

## Cakupan
- Sales/user diperiksa: 5 (user_sales_01..04, user_sales_admin_01); PT: ent_ksc, ent_kanda, all; bulan: 2026-08..2026-12 (5 bulan; data hanya ada Okt dan Nov 2026).
- 75 kombinasi dihitung, 9 non-nol, 0 galat. 130 baris rincian dibandingkan.
- Pesanan di data: 10 (6 punya pembayaran; menghasilkan komisi). Pesanan batal / `closed_short` / `advance_to_deposit`: 0, `commission_carry_balances`: 0 dokumen. Jadi jalur koreksi BTP-5 tidak terpicu di data acuan (sesuai dugaan).
- Slip gaji (2 karyawan sales, Nov 2026, ent_ksc): total komisi identik (474.330,66 dan 80.093,94).

## Perbandingan (hanya baris non-nol; baris nol lain juga identik)
| Sales | PT | Bulan | Sebelum | Sesudah | Selisih |
|---|---|---|---|---|---|
| user_sales_01 | all | 2026-11 | 280,093.94 | 280,093.94 | 0 |
| user_sales_01 | ent_kanda | 2026-11 | 200,000.00 | 200,000.00 | 0 |
| user_sales_01 | ent_ksc | 2026-11 | 80,093.94 | 80,093.94 | 0 |
| user_sales_02 | all | 2026-11 | 474,330.66 | 474,330.66 | 0 |
| user_sales_02 | ent_ksc | 2026-11 | 474,330.66 | 474,330.66 | 0 |
| user_sales_03 | all | 2026-10 | 250,000.00 | 250,000.00 | 0 |
| user_sales_03 | all | 2026-11 | 75,000.73 | 75,000.73 | 0 |
| user_sales_03 | ent_ksc | 2026-10 | 250,000.00 | 250,000.00 | 0 |
| user_sales_03 | ent_ksc | 2026-11 | 75,000.73 | 75,000.73 | 0 |

## Beda yang ada hanya di SESUDAH (tambahan bidang, bukan perubahan angka)
- Hasil `compute_commission` punya bidang baru `commission_raw`, `carry_in`, `carry_out` (saldo potongan). Di data acuan: `carry_in = carry_out = 0` dan `commission_raw = total_incentive` untuk semua kombinasi.
- Slip gaji menyimpan `commission_engine` {commission_raw, carry_in, carry_out, computed_at} (hanya SESUDAH); nilainya karyawan 1: raw 474.330,66 / carry 0; karyawan 2: raw 80.093,94 / carry 0.
- Saldo potongan (BTP-5) belum terisi di data: 0 dokumen `commission_carry_balances` di kedua versi.

## Catatan
Tidak ada selisih yang perlu dijelaskan. Batasan: data acuan tidak memuat batal/tutup sisa, jadi uji ini membuktikan jalur lama tidak berubah, bukan kebenaran koreksi BTP-5 (itu dicakup `tests_mem/test_BTP5_komisi_koreksi.py`).
