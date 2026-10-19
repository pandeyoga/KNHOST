# Handoff sesi 2026-10-19 → sesi berikutnya

Baca dulu: `evidence/DECISIONS_OWNER_2026-10-19.md` (jawaban owner), `REVIEW_STATUS_DAN_DUPLIKASI_2026-10-19.md` (status plan + duplikasi D1–D8).

## Instruksi owner
"Catat ini, biarkan di sesi berikutnya untuk dianalisa." → Sesi ini **hanya mencatat** jawaban (BACKLOG status `resolved` + sumber). Belum ada kode yang diubah berdasarkan jawaban ini. Sesi berikutnya: analisa dampak, tunjukkan rencana ke owner, baru implementasi.

## Requirement yang terbuka karena jawaban ini (usulan urutan)
| # | Requirement | Keputusan | Yang perlu dianalisa/dibuat | Catatan kode existing |
|---|---|---|---|---|
| 1 | LN-083 batas waktu & syarat klaim | KLR-08, KLR-09 | End-event customer = tanggal pengajuan; supplier = tanggal klaim dikirim. Hangtag/potong → checklist + warning, Finance putus (ganti blokir/settle 409 yang sekarang) | `return_policy_service`, `ReturnAssumptionsPanel`; sekaligus pertimbangkan duplikasi D1 (jendela retur di 4 tempat) |
| 2 | LN-092 cutloss & discount | KLR-01, 02, 06, 07 | Cutloss: MD input yard cacat (bukan kelipatan), konversi otomatis ke kg untuk produk kg, kompensasi = harga transaksi awal × qty cacat; customer menerima 2 potong (roll dipecah). Discount: nominal rupiah per item untuk qty cacat, boleh tanpa barang (foto/video), nilai final oleh Finance | Parameter "asumsi" `cutloss_return_part` dkk di Kebijakan Retur → ganti jadi aturan pasti |
| 3 | LN-090 tukar barang (T02/T03) | KLR-03, 04, 05 | Kewajiban pengganti dalam yard dari qty aktual QC; lebih → tagih selisih (harga asal); kurang → refund/saldo | Order pengganti nyata belum ada |
| 4 | LN-091 settlement | KLR-10, KLR-11 | Refund/saldo pilihan customer walau ada utang SO lain; opsi penanggung ongkir (3 jenis biaya) per kasus | |
| 5 | LN-093 interco return | KLR-09 | Deadline mengikuti tanggal pengajuan | |
| 6 | LN-014 / LN-040 LOT | KLX-01 | Dua kode LOT (pabrik + KN), LOT KN baru tiap SJ, nama diisi user | |
| 7 | LN-052 inspeksi | KLX-02 | Form manual (kode cacat/poin/grade diisi user); hasil tidak lagi "kandidat"; terkait D2/D3 (grade di 2 tempat & hardcode) | |
| 8 | LN-024 pembayaran interco | KLX-03 | Cutoff, tanggal bayar, acuan periode configurable | Pengingat belum jalan sebelum dikonfigurasi |
| 9 | LN-101 opname | OPS-01 | Tanpa batas nilai kerugian; cek tidak ada threshold tersisa | evidence/L10/report.md |

## Masih pending (owner minta dijelaskan dulu, dengan bahasa sederhana + contoh)
DATA-01 (file acuan migrasi master), DES-02 (dokumen per leg Bandung–Jakarta–customer), DES-03 (format rapor & arti angka penjualan), DES-04 (MD membuat PO dari antrean gabungan), HW-01 (perangkat RFID), HW-02 (mesin absensi), HR-01 (aturan shift), UAT-01 (uji terima).

## Duplikasi menunggu persetujuan owner
D1–D8 di REVIEW_STATUS_DAN_DUPLIKASI_2026-10-19.md. D1, D2, D3 beririsan langsung dengan item #1, #2, #7 di atas: sebaiknya diputuskan bersamaan.

## Kondisi lingkungan
- Data demo: `scripts/restore_local_demo.sh` (backend/.env perlu `KN_DEMO_DATA="true"`, `SEED_DEMO_ENABLED="true"`).
- Frontend = bundle statis; setelah ubah FE jalankan `bash scripts/rebuild_frontend.sh`.
- Push: `GH_TOKEN=... bash scripts/push_github.sh main "pesan"` (token tidak disimpan).
