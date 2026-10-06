# Kontrak frontend–backend pada pratinjau template dasar

**Temuan D4-DOC-01, prioritas P2.** Source `a904d989b622f7da14c4892d03cf6ef0c43f3084`. Jalur masih tersedia untuk admin melalui Pengaturan → Template Dokumen Dasar, dengan activeView doc-templates-basic. Ini hasil source trace, original public API dan original hook function; browser/iframe DOM belum diuji.

## Flow yang ditemukan

```text
Admin pilih Template Dokumen Dasar
  → AdminView only templates memuat template aktif
  → ada SO pada data.orders[0], tombol Pratinjau tersedia
  → klik baris template, meneruskan templateId + orderId
  → useAppActions.previewTemplate POST /document-templates/<id>/preview
  → route tidak terdaftar, HTTP404
  → catch memberi notice Not Found
  → setPreviewHtml tidak dijalankan, iframe tidak mendapat HTML
```

| Pemeriksaan | Expected | Actual |
|---|---|---|
| Template dari original creator dapat dibaca |200 dan template ditemukan |Lulus |
| Endpoint yang dipanggil tombol |200 HTML untuk selected template/source |404 Not Found |
| Jenis template Surat Jalan yang dipilih |surat_jalan |Callback selalu mengirim invoice |
| Original callback sesudah respons API |HTML pratinjau terisi |Tidak ada HTML; notice error |
| Existing GET /documents/preview/<orderId> untuk Surat Jalan |200 text/html |Lulus pada fixture yang sama |

Template dibuat melalui original public POST; SO berupa fixture read-state eksplisit yang sah dan milik entitasA. Ini tidak menguji seluruh SO→pengiriman atau hasil printer. Control GET yang lulus membatasi kesimpulan: masalah spesifik ada pada kontrak tombol template dasar. Keberhasilan tersebut juga belum membuktikan semua angka/data yang tercetak benar.

## Arah perbaikan

Kontrak harus menerima selected template ID, jenis dokumen dan source yang cocok. Callback harus membawa document_type dari baris template. Server memvalidasi permission, source legal entity, effective global/entity layer dan status template. Mengganti URL ke GET lama saja belum mempertahankan pilihan template, karena GET itu tidak menerima selected template ID.

Pratinjau harus memakai renderer dan data contract yang sama dengan hasil cetak yang nantinya digunakan. Bila perusahaan mempertahankan template dasar dan designer PDF sebagai fitur terpisah, jelaskan output yang diatur masing-masing agar operator tidak mengubah satu format lalu mencetak format lain. Ini perlu pemeriksaan consumer; tidak disimpulkan semua PDF sekarang gagal.

Acceptance lengkap ada pada tracker dan **FASE-05**. Uji dua template tipe sama dengan konten berbeda, Surat Jalan versus invoice, override per entitas, source/template invalid, tanpa SO, hak akses, recovery sesudah error, iframe dan printer/export. Preview tidak boleh membuat dokumen generated atau mengubah transaksi.

## Lokasi dan bukti

[frontend/src/hooks/useAppActions.js:616](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/hooks/useAppActions.js#L616). Rantai tambahan:

- [frontend/src/features/admin/AdminView.jsx:542](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/admin/AdminView.jsx#L542)
- [frontend/src/AppViewRouter.jsx:260](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/AppViewRouter.jsx#L260)
- [backend/routers/documents.py:283](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/routers/documents.py#L283)

`latest/repro/document_preview_probes.py`, `document-preview-api-results.json`, `document_preview_probes.cjs` dan `document-preview-js-results.json` menyimpan fixture, API response, original-function execution serta expected/actual. Script tidak memperbaiki source aplikasi.
