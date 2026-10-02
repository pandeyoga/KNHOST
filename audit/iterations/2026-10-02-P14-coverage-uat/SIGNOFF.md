# SIGN-OFF P14 — status: TIDAK DAPAT DITANDATANGANI (belum lengkap)

Dokumen ini adalah checklist sign-off, bukan persetujuan. Sesuai [P14](../../phases/P14.md), sign-off menunggu seluruh prasyarat di bawah, validator independen, dan pemilik proses.

## Prasyarat wajib

| Prasyarat | Status | Bukti / catatan |
|---|---|---|
| Dataset acuan order-to-cash | partial | SALE-01/03/04/05, APAR-02 (harness P03/P07). Belum ada dataset acuan dengan angka yang disetujui Finance. |
| Dataset acuan procure-to-pay | partial | GRN-01, PRET-01..06, APAR-01 (P03/P04/P06/P11). |
| Inventory / production | partial | INV-01/05, PROD-01/03 tested_pass; PROD-04/06, INV-06 planned. |
| Record-to-report | partial | GL-02/03/04 tested_pass; GL-01/05 partial; GL-06 planned. |
| Payroll | partial | HR-02 tested_pass; HR-04 butuh validasi legal tabel PPh21/BPJS. |
| Browser UAT nyata | partial | [UAT.md](UAT.md) — otomatis, bukan pengguna bisnis. |
| Worker / crash / retry | partial | OPS-02/04 partial (durable posting & saga); injeksi crash per tahap belum. |
| Deployment / index checks | partial | OPS-01: semua `INDEX_SPECS` ada di DB preview; produksi belum diperiksa. |
| RFID printer/reader/gate commissioning | blocked | RFID-06: perlu perangkat & firmware; hasil simulasi bukan akurasi hardware. |
| Rekonsiliasi saldo pembukaan, subledger, GL, pajak, laporan | partial | FN-08/FN-15/CX-09 harness; rekonsiliasi angka nyata belum. |
| Backup/restore | blocked | OPS-05: perlu lingkungan & kebijakan pemilik. |
| Validator independen untuk 101 temuan `ready_for_validation` | belum | Tidak ada temuan `verified_fixed`. GN-15 masih `open`. |

## Lingkungan yang tercatat

- Commit dasar `8fcb9dc9588cf14d9eeb534be38168a1c50f23d3` + patch P14; preview Emergent; Mongo `test_database` sintetis.
- Perangkat/firmware RFID: tidak ada (simulasi software saja).

## Pengecualian (exception) yang diusulkan — menunggu keputusan pemilik

| ID | Alasan | Pemilik keputusan | Dampak | Tinjau ulang |
|---|---|---|---|---|
| EX-P14-01 RFID-06 | Tidak ada perangkat fisik di lingkungan agent | Pemilik operasional gudang | Akurasi gate/printer belum terbukti | 2026-11-02 |
| EX-P14-02 OPS-05 | Backup/restore butuh target non-preview | Pemilik infrastruktur | Pemulihan data belum terbukti | 2026-11-02 |
| EX-P14-03 HR-04 | Tabel pajak/BPJS butuh review legal/akuntan | Pemilik HR & Finance | Risiko salah hitung akhir tahun | 2026-11-02 |
| EX-P14-04 Arsip link | 5 tautan ke `*.log/*.lock` arsip tidak ada di repo | Pemilik repo | validate.py merah pada arsip | 2026-10-16 |
| EX-P14-05 Riwayat git | Token lama masih di riwayat publik | Pemilik repo | Risiko kebocoran sesi lama | Segera |

Pengecualian bukan status fixed. Tanda tangan: — (kosong sampai semua baris di atas memiliki keputusan tercatat).
