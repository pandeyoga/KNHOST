# KNHOST — audit dan perbaikan berulang

Mulai dari dokumen ini, bukan langsung menjalankan prompt arsip.

**Audit historis:** `d1fd56e4f0fbd1af1a46bc0b9932dc8545d78467`. **Dasar branch publikasi:** `3a7c40a51129aaa696e0fb5a092d9db90f1cb45f`. Main berubah setelah audit; temuan belum diperiksa ulang pada current main. Tidak ada source aplikasi yang diubah oleh paket dokumentasi ini. Seluruh flow belum tercakup dan tidak ada klaim enterprise/Finance sign-off.

## Cara kerja

1. Baca [workflow](WORKFLOW.md) dan [P00](phases/P00.md).
2. Pilih fase/ID dari [tracker.json](tracker.json), baca kartu dan koreksi; reproduce pada commit kerja saat ini.
3. Agent develop menjalankan prompt fase, mencatat perubahan dan menandai ready_for_validation dengan bukti.
4. Validator memeriksa ulang pada SHA kandidat, lalu verified_fixed atau reopened. Status implementasi bukan validasi.
5. Lanjutkan coverage dan penemuan baru secara terpisah melalui [coverage.json](coverage.json).

## Struktur dan SSOT

- tracker.json: 103 record historis (65 awal + 8 AX + 13 CX + 17 IX). **Bukan 103 bug unik**; AX dapat overlap, IX-02 alias HR-03, GN-06/E1 dan GN-07/E1 adalah pendalaman.
- findings/: kartu per ID dengan laporan awal, review koreksi dan rujukan pendalaman.
- domains/: indeks domain tanpa menduplikasi status.
- phases/: urutan dan dependensi, prompt develop siap pakai, exit gate.
- iterations/ + templates/: implementasi dan hasil validasi tiap putaran.
- archive/2026-09/: seluruh 30 laporan bernomor 00–29, paket reproduksi, hasil JSON dan manifest. Arsip adalah bukti baseline; instruksi terbaru di folder aktif mengungguli prompt lama.
- coverage.json: 96 kasus baseline, bukan semua kemungkinan aplikasi. Histori audit punya 59 skenario runtime dan 19 test bawaan; probe 1.353 endpoint bukan pengujian semua flow.
- policy-decisions.json: keputusan bisnis yang belum ditetapkan, termasuk PG01 sampling. Keputusan pemilik tidak digantikan dengan status bug fixed.

Koreksi/gap penting tetap dipertahankan: FN-14 tidak selalu zero-cost, RF-03 mempunyai guard tujuan yang sudah benar, IX-13 ditahan oleh discrepancy default pada fixture GRN, IX-02 tidak dihitung ulang. PG01 sampling adalah gap policy pada arsip 22, dibahas P06; bukan bug universal yang boleh dipatch tanpa kontrak bisnis. Pembanding enterprise dan UI/UX ada pada arsip 02/10. Jangan menjumlah hasil putaran sebagai jumlah bug unik.

## Fase

Urutan menempatkan scope dan core stok lebih dulu, lalu kontrak posting/nilai Finance, baru orkestrasi operasional dan gate. Fase dengan dependensi terpenuhi dapat dikerjakan secara terpisah; tidak perlu menunggu seluruh domain yang tidak terkait. Critical hotfix harus tetap memiliki evidence dan validasi.

| Fase | Lingkup | Dependensi |
|---|---|---|
| [P00](phases/P00.md) | Rebaseline dan fixture | — |
| [P01](phases/P01.md) | Scope, credentials dan request identity | P00 |
| [P02](phases/P02.md) | Core roll, split, provenance dan projection | P01 |
| [P03](phases/P03.md) | Cash, AR, bank, aset dan durable posting | P01, P02 |
| [P04](phases/P04.md) | Landed cost, costing dan AP match | P02, P03 |
| [P05](phases/P05.md) | COA, laporan dan period close | P03, P04 |
| [P06](phases/P06.md) | Putaway, transfer, QC dan lokasi | P02, P03 |
| [P07](phases/P07.md) | Pick, shipment manifest dan dispatch atomik | P02, P03, P06 |
| [P08](phases/P08.md) | Tag, printer dan typed verification | P01, P02, P06 |
| [P09](phases/P09.md) | Gate edge contract, evaluator dan kiosk | P07, P08 |
| [P10](phases/P10.md) | Count, opname dan adjustment financial | P02, P03, P04, P08 |
| [P11](phases/P11.md) | Mutasi alternatif dan konversi dokumen | P02, P03, P04, P06 |
| [P12](phases/P12.md) | Payroll, HR dan marketing | P01, P03 |
| [P13](phases/P13.md) | Audit trail, kandidat secret dan label ringan | P01 |
| [P14](phases/P14.md) | Coverage, UAT dan sign-off lintas flow | P01, P02, P03, P04, P05, P06, P07, P08, P09, P10, P11, P12, P13 |

## Validasi paket

Jalankan `python docs/audit/tools/validate.py` dari root repo (Python standard library). Pemeriksaan memvalidasi ID, fase, referensi bukti, baseline, syarat status verified_fixed dan hubungan dependensi. Ini memeriksa dokumentasi, **bukan mengetes aplikasi**. Perbarui history bersama setiap perubahan status.

Jalankan harness hanya setelah membaca README arsip, menggunakan clone/commit yang dinyatakan serta database sintetis. Snapshot source link tetap dipatok commit audit; bila SHA historis tidak tersedia di remote setelah rewrite, minta checkout audit yang sesuai, jangan diam-diam memakai main terbaru dan menyebut hasilnya reproduksi baseline.
