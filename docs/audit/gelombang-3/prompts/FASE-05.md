# Gelombang 3 · Fase 05 — Regresi, pembersihan duplikasi, dan validasi penutupan

Kerjakan Gelombang 3 dari commit repo saat ini. Baca README, findings-tracker.json, laporan detail, dan source terkait sebelum mengubah kode. Catat actual HEAD; commit audit hanya baseline bukti, bukan asumsi bahwa repo belum berubah. Periksa dulu apakah kasus sudah diperbaiki untuk menghindari patch ganda. Jangan menimpa dokumen Gelombang 1/2 atau mengubah hasil audit historis.

Untuk setiap ID: telusuri input UI → request/schema → permission/entity/lini → service → persist/ledger → projection/report → frontend, termasuk retry, concurrency, pembatalan dan reversal yang relevan. Pertahankan kuantitas fisik, unit, pemilik barang, source document, harga/HPP serta legal entity. Jangan mengubah expected menjadi hasil bug, menyembunyikan warning, atau menyimpulkan fixed hanya dari HTTP 200. Keputusan definisi bisnis yang belum tegas harus dicatat sebagai needs_business_decision.

Setelah implementasi, isi implementation_commit, implementation_evidence, daftar file, perbandingan expected/actual sebelum-sesudah, perintah uji, batas pengujian, dan risiko migrasi. Status agent paling jauh implemented_pending_validation; reviewer independen yang menetapkan verified_fixed setelah seluruh acceptance dan flow terkait lulus. Simpan proof baru terpisah, tanpa menimpa evidence baseline.

Prasyarat: 01, 02, 03, 04. Jumlah ID: 9.

## V3-DUP-01 — Helper _clean_perms didefinisikan dua kali

Prioritas **P3**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/custom_role_service.py#L60). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-DUP-01`.

**Penyebab:** AST seluruh backend menemukan dua definisi top-level identik pada baris60 dan67. Definisi kedua menimpa pertama; body kini sama sehingga ini maintainability debt, bukan beda perilaku akses.

**Prompt perbaikan:** Hapus definisi identik dengan satu canonical helper; tambahkan deteksi duplicate top-level definition dalam quality check yang sesuai, tanpa menggandakan business-rule tests.

**Kriteria validasi:** Satu definisi, custom permission normal/error contract tetap sama. Jangan menjadikan ini P1 atau menghitungnya sebagai bug akses yang sudah terbukti.

## V3-BUILD-01 — Dependency build frontend tidak mempunyai lockfile terlacak

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/package.json#L151). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `V3-BUILD-01`.

**Penyebab:** Repo mendeklarasikan Yarn1.22.22 tetapi tidak melacak yarn.lock, package-lock.json atau pnpm-lock.yaml. Fresh install harus meresolusikan dependency transitive; dua build tidak mempunyai dependency graph terkunci.

**Prompt perbaikan:** Commit satu lockfile canonical sesuai packageManager; pipeline harus gagal jika lock tidak ada/berbeda dan memakai frozen/immutable install. Simpan runtime versions dan dependency integrity. Jangan commit node_modules/build/.env.

**Kriteria validasi:** Fresh isolated install pada dua runner memakai graph/integrity sama. Build smoke lulus dari lock, lint warning relevan ditinjau; packageManager dan pipeline tidak saling memilih manager berbeda.

## D4-FE-01 — Grafik velocity Manager selalu memotong menjadi14hari

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L100). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-FE-01`.

**Penyebab:** Dataset velocity dari API dipotong slice(-14) tanpa mengikuti period pilihan.

**Prompt perbaikan:** Gunakan range period yang sama dengan request atau label last14days secara eksplisit jika itu tujuan grafik. Jangan memotong data tanpa indikasi.

**Kriteria validasi:** Periode7/30/90 menunjukkan dataset sesuai tanggalpilihan; emptydays tetapkontrak API, boundarydates/labeltooltip diperiksa diUI.

## D4-FE-02 — Respons periode lama dapat menimpa grafik setelah periode diganti

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/manager/ManagerDashboard.jsx#L69). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-FE-02`.

**Penyebab:** load/useEffect tidak membatalkan request lama atau menjaga generation. Pergantian periode tidak remount komponen; request30 yang selesai setelah90 menulis ulang data. App.js L528 memakai key selectedEntity, sehingga hipotesis awal pergantian entitas ditarik: probe lama melewati remount.

**Prompt perbaikan:** Implement generation guard/AbortController yang melindungi seluruh setters termasuk loading/error pada pergantian periode, aging days dan refresh. Data beberapa endpoint harus satu request generation. Pertahankan remount entitas yang sudah ada; audit pola halaman lain dengan bukti terpisah.

**Kriteria validasi:** Pada entitas sama, period30→90 dan respons out-of-order: grafik tetap90; respons/error/finally30 tidak mengubah state90. Uji aging-days, refresh, unmount dan partial failure. Uji browser diperlukan untuk validasi rendered UI.

## D4-TEST-01 — Tes konsistensi ATP dapat lulus walaupun mencatat mismatch

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/tests/test_iter149_audit.py#L116). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-TEST-01`.

**Penyebab:** test_stock_atp_sum_matches mengumpulkan bad_row/bad_wh dan menulis/print hasil tanpa assert terakhir yang menolak mismatch. Formula lama juga perlu diselaraskan dengan pendingdemandyang didokumentasikan.

**Prompt perbaikan:** Definisikan formulaavailability/ATP bersama timbisnis, buat independentoracle dengan fixture partialreserve/hold/pending/incoming. Tambahkan assertionmismatch dan test-negatif yangmemastikanoracle gagal terhadapmutasi.

**Kriteria validasi:** InjectwrongATP→testFAIL; correctformula→PASS. Uji fixture>100SKU, multiowner, pendingcut, externalincoming dan no-dependencydemoaccount.

## D4-PLAN-04 — Pesan kegagalan pemenuhan parsial terhapus oleh refresh otomatis

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx#L59). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-PLAN-04`.

**Penyebab:** submit menaruh pesan error lalu memanggil load; saat GET sukses load menjalankan setError kosong sehingga pesan kegagalan dan informasi bagian yang telah diproses hilang.

**Prompt perbaikan:** Pisahkan load error dari execution error dan pertahankan hasil partial sampai pengguna menutupnya. Refresh data tidak boleh menghapus pesan proses yang belum diakui. Jelaskan bagian sukses, gagal dan tindakan lanjutan.

**Kriteria validasi:** POST gagal parsial lalu GET sukses tetap menampilkan pesan dan bagian30 yang sukses. GET gagal harus menampilkan kedua konteks dengan jelas. Lengkapi browser test tanpa mengubah oracle.

## D4-ORDER-01 — Rata-rata pesanan membagi revenue seluruh pesanan dengan hanya 20 pesanan terbaru

Prioritas **P1**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/features/orders/OrderDashboard.jsx#L74). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-ORDER-01`.

**Penyebab:** Patch revenue memakai summary.revenue[period].grand_total seluruh pesanan, tetapi denominator recentOrders.length tetap dari window20. Server sudah menyediakan revenue.count untuk populasi dan status yang sama; consumer mengabaikannya. Top Customers dan status/pending/expiry juga memakai window lokal tanpa label cakupan. Halaman list memakai pagination dan summary server, sehingga list benar tidak membuktikan dasbor benar.

**Prompt perbaikan:** Gunakan revenue.count sebagai denominator jika rata-rata didefinisikan atas status terpenuhi; definisikan totalOrders terpisah bila mencakup semua status. Hitung Top Customers, distribusi status, pending dan expiry di server dengan scope entity/sales-owner/line/periode yang sama. Label setiap pengecualian periode atau dataset parsial. Jangan memuat seluruh dokumen di browser untuk memperbaiki agregat.

**Kriteria validasi:** 30 SO confirmed100 menghasilkan revenue3000/count30/avg100 dan customer revenue3000. Uji >20 dan >200, mix reserved/cancelled/fulfilled, periode7/30/90, sales-owner, line scope dan perubahan filter. Bandingkan seluruh widget dengan source query independen; Recent Orders tetap boleh10 dengan labelnya.

## D4-DOC-01 — Pratinjau Template Dokumen Dasar memanggil endpoint yang tidak tersedia dan mengabaikan jenis template

Prioritas **P2**. [Kode](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/frontend/src/hooks/useAppActions.js#L616). Detail lengkap dan bukti: `baseline-78/LAPORAN_LENGKAP.md`, cari ID `D4-DOC-01`.

**Penyebab:** Callback melakukan POST /document-templates/{id}/preview, tetapi aplikasi hanya menyediakan GET /documents/preview/{order_id} beserta CRUD template. Original hook juga mematok document_type invoice walaupun row yang dipilih adalah Surat Jalan. Jalur ini masih terhubung pada activeView doc-templates-basic, sehingga bukan hanya fungsi lama yang tidak pernah dipakai.

**Prompt perbaikan:** Satukan kontrak preview berdasarkan source document dan selected template ID/type. UI meneruskan jenis template yang dipilih; server memvalidasi entity, permissions, template effective layer dan kompatibilitas source tanpa membuat generated document/transaksi. Jangan sekadar mengganti endpoint ke GET yang mengabaikan selected ID. Pastikan template dasar dan PDF designer mempunyai batas fitur yang jelas dan dokumen yang benar-benar dicetak memakai format/field yang sama dengan preview.

**Kriteria validasi:** Admin membuka Template Dokumen Dasar dengan SO yang sah: Pratinjau template Surat Jalan/invoice/jenis lain memberi200 HTML untuk selected template dan document type yang tepat. Dua template tipe sama harus dapat dipratinjau berbeda sesuai ID, global vs entity override terkontrol, source berbeda entitas ditolak, disabled template ditangani jelas, tanpa generated-doc atau ledger side effect. Uji empty orders, permissions, invalid template/source, error recovery, iframe HTML dan output cetak.

## D4-CB-01 — Pemeriksa kontrabon dapat memberi hasil bersih karena hanya memeriksa 2.000 dokumen pertama

**Prioritas:** P2 · **Status:** open · **Jenis bukti:** `direct_original_scanner_or_migration_with_explicit_legacy_fixture`.

**Layar/alur:** Gate integritas kontrabon; cakupan validasi produksi/data lama.

**Rantai kejadian:** 2.000 kontrabon tanpa pelanggaran → dua kontrabon terakhir memakai bill sama → detector menghasilkan0 pelanggaran.

**Letak kesalahan dan penyebab:** Cursor dibatasi to_list(2000) tanpa pemeriksaan total/paginasi; dokumen di luar jendela tidak dievaluasi.

**Dampak, hasil reproduksi, dan batas klaim:** Fixture sengaja dibuat korup untuk menguji pemeriksa, bukan membuktikan producer publik dapat membuat kontrabon ganda. Pada dataset kecil duplicate aktif terdeteksi; cancelled dikecualikan. Pada2.002 live records, duplicate bill di tail terlewat dan detector memberi0.

**Lokasi source pada commit audit:**

- [backend/services/contra_bon_scan.py:24](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contra_bon_scan.py#L24) — `return await db[COLL].find(`.
- [backend/services/contra_bon_scan.py:29](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/backend/services/contra_bon_scan.py#L29) — `async def bills_in_multiple_contra_bons`.
- [scripts/verify_data_integrity.py:3642](https://github.com/pandeyoga/KNHOST/blob/a904d989b622f7da14c4892d03cf6ef0c43f3084/scripts/verify_data_integrity.py#L3642) — `async def layer_contra_bon_invariants`.

```python
22: async def _live_contra_bons() -> List[Dict[str, Any]]:
23:     """Kontrabon yang masih 'memegang' dokumen (semua kecuali `cancelled`)."""
24:     return await db[COLL].find(
25:         {"status": {"$in": list(svc.HOLDING_STATUSES)}}, {"_id": 0}).to_list(2000)
26: 
27: 
28: # ── INV-CB-01 ────────────────────────────────────────────────────────────────
29: async def bills_in_multiple_contra_bons() -> List[Dict[str, Any]]:
30:     """Satu faktur supplier tidak boleh berada di dua kontrabon yang belum dibatalkan.
```

**Bukti asli:** [evidence/repro/contra-bon-invariants90-results.json](evidence/repro/contra-bon-invariants90-results.json). Contoh observasi:

| Pemeriksaan | Seharusnya | Hasil aktual | Status |
|---|---|---|---|
| contra.scale_duplicate_2002 | 1 | 0 | observed_difference |

**Prompt agent development:**

Iterasi seluruh cursor/aggregation atau pagination stabil; jika harus membatasi, tampilkan incomplete dan jangan meluluskan gate. Terapkan pada seluruh detector yang memakai _live_contra_bons, serta batas lain yang belum dibuktikan.

**Kriteria penerimaan untuk reviewer:**

Duplicate yang berada pada awal/tengah/akhir dari >2.000 data harus terdeteksi. Fixture valid tidak memberi false positive, cancelled dikecualikan. Laporkan scanned/total dan pastikan incomplete tidak boleh berstatus hijau.

