# Protokol Review ↔ Development

Folder ini adalah tempat serah-terima antara **reviewer** (Codex) dan **implementer**
(Claude Code). Riwayat chat masing-masing tidak dibagikan; semua yang perlu diketahui
pihak lain harus ada di repo.

```
review (Codex) → paket di docs/reviews/<tanggal>/ → implementasi (Claude Code)
→ bukti di docs/reviews/<tanggal>/hasil/ + TRACKER.md → validasi (Codex)
```

## Isi folder

| Path | Isi | Siapa yang mengubah |
|---|---|---|
| `TRACKER.md` | Satu tracker untuk SEMUA temuan, ID tetap | keduanya (lihat aturan status) |
| `<tanggal>/` | Paket review apa adanya: laporan, prompt per fase, bukti, reproduksi | **tidak diubah** (arsip historis) |
| `<tanggal>/hasil/<FASE>.md` | Laporan implementasi per fase | implementer |
| `<tanggal>/hasil/validasi-<FASE>.md` | Hasil review ulang | reviewer |

## Status temuan

| Status | Arti | Ditetapkan oleh |
|---|---|---|
| `open` | Belum ditangani | reviewer (saat paket masuk) |
| `in_progress` | Sedang dikerjakan | implementer |
| `implemented_pending_review` | Implementasi & pengujian selesai, menunggu review | implementer |
| `verified` | Perbaikan sudah divalidasi | **hanya reviewer** |
| `reopened` | Perbaikan belum memadai / menimbulkan masalah terkait | **hanya reviewer** |
| `pending_decision` | Menunggu keputusan bisnis owner | keduanya |

Implementer boleh menyatakan implementasinya selesai, tetapi **penutupan (`verified`)
hanya lewat validasi reviewer**. "Tes lulus" tidak otomatis berarti seluruh flow benar.

## Aturan untuk implementer

1. **Catat commit awal** (SHA `HEAD`) di laporan fase sebelum mengubah kode.
2. **Cek ulang setiap temuan di kode terkini** sebelum memperbaikinya. Baseline paket bisa
   tertinggal dari `HEAD`. Hasilnya diisi di kolom "Berlaku di HEAD" pada tracker:
   `ya` · `sebagian` · `tidak — sudah diperbaiki di <SHA>` (wajib bukti kode + uji) ·
   `tidak dapat direproduksi` (wajib langkah yang dicoba).
3. Kerjakan **sesuai urutan fase dan "titik selesai"** di prompt paket. Pertahankan keputusan
   bisnis yang sudah disahkan; jangan menambah toleransi/kewenangan/aturan berdasar asumsi.
4. Temuan yang butuh keputusan → `pending_decision`, tulis pertanyaannya di tracker, lanjutkan
   pekerjaan lain yang tidak bergantung padanya.
5. **Jangan menghapus atau mengubah laporan audit historis.** Temuan lama tetap tercatat beserta
   hasil cek ulangnya.
6. Jangan mengubah expected result agar tes lulus. Hambatan lingkungan dicatat sebagai hambatan.
7. Perubahan kode + catatan disinkronkan lewat Git (commit, lalu push bila reviewer memakai
   checkout lain).

## Templat laporan fase (`<tanggal>/hasil/<FASE>.md`)

```markdown
# <FASE> — <judul>

- Commit awal: <SHA>        - Commit akhir: <SHA>        - Branch: <nama>
- ID ditangani: FE-xx, FE-yy

## FE-xx — <judul temuan>
- Berlaku di HEAD: ya / sebagian / tidak (bukti)
- Akar masalah:
- Perubahan perilaku (sebelum → sesudah):
- Berkas berubah:
- Commit:
- Pengujian: perintah, hasil sebelum/sesudah, tes regresi baru
- Bukti UI (screenshot/rekaman) bila diuji lewat browser:
- Fixture disiapkan langsung vs proses bisnis dijalankan:
- Dampak pada modul terkait:
- Keterbatasan / yang belum diuji:
- Status: implemented_pending_review

## Hambatan lingkungan
## Yang perlu direview
```
