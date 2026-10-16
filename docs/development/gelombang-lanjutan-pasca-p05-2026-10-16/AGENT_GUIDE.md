# Panduan agent development

1. Baca aturan repo target dan mulai dari L00. Cek commit aktual; jika lebih baru dari baseline, baca diff terlebih dahulu dan perbarui evidence baseline. Jangan checkout/reset paksa pekerjaan pengguna.
2. BACKLOG.json adalah SSOT status. TRACKER.md, COVERAGE.md, ACCEPTANCE_MATRIX.md dan DECISIONS_PENDING.md dirender dari sana. File sumber adalah snapshot konteks; status di dalamnya tidak menjadi otorisasi baru.
3. Pilih requirement, telusuri source code aktual dan UI yang terkait, lalu tulis apakah cukup konfigurasi/reuse atau memerlukan perubahan. Jangan membuat flow kedua untuk kemampuan yang sudah benar.
4. Setiap aksi bisnis baru didaftarkan pada custom role/authority beserta scope entitas/lokasi. Jangan hardcode nama staf atau `role == admin` sebagai satu-satunya cara akses.
5. Sebelum perubahan saldo atau dokumen, tentukan atomic boundary, idempotency key, state transition dan recovery. Gunakan mekanisme transaksi/ledger existing yang benar; jangan buat ledger paralel.
6. Kerjakan acceptance sesuai phase prompt. Rekam fixture, input, tindakan, output aktual, expected result, commit dan bukti. Screenshot membuktikan UI; API/data/ledger membuktikan efek. Pilih bukti yang relevan, bukan checklist kosong untuk semua kasus.
7. Jika rule pending memengaruhi nominal, keputusan grade, supplier deadline atau stock availability, jangan isi asumsi. Catat `blocked_by_decision` pada requirement terkait dan lanjutkan bagian independen. Fase keseluruhan belum tervalidasi sampai dependency required selesai.
8. Jangan menambah auto variance/tolerance pada alokasi yard/roll. Jangan memaksa sumber restock, menampilkan grade ke Sales saat trial, atau menganggap semua grade punya harga sama.
9. Jangan membangun middleware/APK dalam tugas ERP ini. Reconcile kontrak dan uji integrasi dengan workstream middleware sesuai dokumen. Jangan mengganti bukti hardware dengan simulator.
10. Ketika implementasi dan tes developer lengkap, set `implemented_pending_validation`. Reviewer yang berbeda memeriksa evidence dan owner memberi referensi persetujuan. Status `validated` bukan hasil self-claim implementer.
11. Pada commit final L14, ulangi chain lintas modul dan tes dampak perubahan terakhir. Bukti commit lama memerlukan retest atau alasan impact assessment yang ditandatangani reviewer; tidak otomatis lulus.

## Perintah pengelolaan paket

Jalankan dari folder paket setelah import:

```text
python scripts/render_tracking.py
python scripts/validate_package.py
python scripts/validate_package.py --closure
```

Validator biasa memeriksa konsistensi dokumen/tracker. Exit 0 tidak berarti ERP sudah benar. `--closure` menolak penutupan bila requirement belum tervalidasi, acceptance belum pass, keputusan blocker belum resolved, bukti tidak ada, perangkat belum terbukti atau persetujuan final belum tercatat.

Status requirement/fase: `not_started`, `in_progress`, `blocked_by_decision`, `blocked_by_hardware`, `implemented_pending_validation`, `validated`, `reopened`. Status acceptance: `not_run`, `pass`, `fail`, `blocked`. `pass` harus mempunyai result, commit, reviewer dan file evidence yang nyata. Status decision: `pending` atau `resolved`, dengan jawaban dan sumber persetujuan.

SCOPE_BASELINE.json menjaga daftar fase, requirement, skenario, hubungan keputusan dan kebutuhan perangkat. Renderer tidak mengubah file ini. Jika ada revisi lingkup yang disetujui owner, catat persetujuannya lalu tinjau perubahan inventory ini secara eksplisit; jangan membangunnya ulang dari tracker yang sengaja dikurangi.

Tidak ada status waived otomatis. Jika owner mengubah lingkup, tambah keputusan scope tertulis, perbarui requirement/source map secara terbuka dan beri nama revisi lingkup. Jangan menghapus requirement atau acceptance agar closure hijau.

## Pengisian bukti

Simpan `evidence/Lxx/report.md`, fixtures/hasil teranonimkan dan UI/API/ledger evidence yang relevan. `evidence` berisi path relatif dari root paket. `reviewer` berisi identitas orang/reviewer aktual. `owner_approval_ref` berisi path catatan persetujuan owner yang memuat kandidat commit dan lingkup. Jangan isi nama/approval fiktif.

Isi `target_commit` di root BACKLOG pada kandidat final. `implementation_commit` dan `verified_commit` tiap item harus dapat dicocokkan dengan repo. `final_review` memuat `reviewer`, `implementer`, `owner_approval_ref`, `reconciliation_ref`, `migration_ref`, `hardware_ref`, dan `verified_commit`.

Jika bukti dari commit lebih lama tetap dipakai karena perilakunya tidak terdampak, reviewer wajib membuat impact assessment pada kandidat final. Isi `assessed_target_commit` dan `impact_assessment_ref` di item terkait; assessment menyebut diff/ancestry, alasan tidak perlu retest serta identitas reviewer. Perilaku yang berubah wajib diuji ulang. Ini mencegah pengujian ulang tanpa alasan sekaligus menjaga relevansi bukti.

## Tambahan implementasi revisi 1.2 — produksi supplier dan makloon

Wajib baca [rancangan implementasi produksi](IMPLEMENTASI_PRODUKSI_SUPPLIER_MAKLOON.md). LN-033 ditambahkan pada L03 dan LN-143 pada L14, dengan 18 skenario acceptance baru. Total paket: 54 requirement, 214 acceptance, 15 fase; 24 topik pending lama tetap dipertahankan.

Urutan dependency berubah: fondasi L04 harus tervalidasi sebelum L03 ditutup. Pekerjaan desain/round L03 dapat dipersiapkan sebelumnya. Rilis master bukan order produksi; kedua sumber pemenuhan wajib memiliki hubungan dokumen yang benar sampai penerimaan dan pengiriman. Penambahan ini disetujui owner dalam chat 16 Oktober 2026. Semua status lama dipertahankan; requirement baru belum diimplementasikan.

## Revisi 1.3 — hak akses rinci dan pengujian ulang R&D

Wajib baca [rancangan custom role dan revalidasi R&D](CUSTOM_ROLE_DAN_REVALIDASI_RND_REV1_3.md). Tambahan LN-015 (L01) dan LN-034 (L03), 16 acceptance baru; total 56 requirement dan 230 acceptance. Keputusan owner: hasil uji ulang gagal menunggu keputusan PIC; tidak otomatis menghentikan produksi atau membatalkan stok lama. L14 wajib membuktikan integrasi kedua tambahan ini. Hak akses mencakup aktivitas, scope dan field, bukan hanya menu terlihat. Versi ini menggantikan paket 1.2 untuk import baru; status lama dan 24 topik pending tetap dipertahankan.
