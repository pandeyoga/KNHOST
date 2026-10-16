# Laporan Fase <Pxx> — <judul>

## Identitas

- Branch dan commit baseline:
- Commit implementasi:
- Commit yang diuji:
- Pelaksana dan reviewer/validator:
- Tanggal dan lingkungan uji:
- IMP serta DEV-F/DEV-G yang dicakup:
- Status: <in_progress / implemented_pending_validation / validated / reopened>

## Perubahan perilaku

Jelaskan trigger, perilaku sebelum/sesudah, input/output, peran serta layar terdampak. Bedakan fungsi existing yang dipertahankan dari kemampuan baru. Sertakan kontrak/data/status yang berubah.

## File dan consumer

| File/consumer | Perubahan | Alasan | Kebutuhan |
|---|---|---|---|
| <isi> | <isi> | <isi> | <IMP> |

## Keputusan bisnis

Cantumkan DEC yang relevan beserta sumber keputusan. Jika belum final, jelaskan bagian yang belum diaktifkan atau belum dapat divalidasi. Jangan menuliskan persetujuan yang belum diberikan.

## Migrasi dan rekonsiliasi

Catat preview, apply/checkpoint, jumlah record, ambiguity/exception, rerun, compatibility, rollback/forward-fix. Untuk stok, tampilkan roll/saldo/owner/unit/komitmen/dokumen serta jurnal/biaya yang relevan sebelum dan sesudah.

## Hasil pengujian

| ACC/test | Perintah/langkah dan lingkungan | Input/fixture | Expected vs actual | Hasil | Evidence |
|---|---|---|---|---|---|
| <isi> | <isi> | <isi> | <isi> | <pass/fail/not_run> | <path/link> |

Pisahkan tes terisolasi, API+DB, UI, E2E, dan perangkat nyata. Simpan output/exit, screenshot, serta contoh dokumen; baseline failure ditandai terpisah.

## Risiko dan issue terbuka

| Issue | Dampak | Bukti | IMP/DEC | Tindak lanjut |
|---|---|---|---|---|
| <isi> | <isi> | <isi> | <isi> | <isi> |

## Kesimpulan fase

Daftar item yang diimplementasikan, item yang telah divalidasi secara terpisah, batas validasi, dan pekerjaan yang kini siap dimulai. Cantumkan pembaruan BACKLOG.json. Jangan menutup seluruh fase berdasarkan satu endpoint atau build.
