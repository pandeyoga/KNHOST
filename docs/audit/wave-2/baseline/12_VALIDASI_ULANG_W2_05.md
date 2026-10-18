# Validasi ulang putaran RFID terakhir — W2-010–012

Tanggal 1 Oktober 2026. Scope hanya putaran W2-05 sebelumnya; tidak memvalidasi ulang W2-001–009 atau seluruh Gelombang 1. Snapshot tetap `ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63`, checkout source aplikasi bersih. Ini review keabsahan temuan, **bukan validasi perbaikan**. Semua ID tetap berstatus `open`.

## Keputusan review

| Temuan | Keputusan | Koreksi |
|---|---|---|
| W2-010 | **Valid, scope dipersempit; P1** | Histori `rfid_reads` B bocor ke user A. Klaim bahwa semua akses insiden, ringkasan, dan health B pasti melanggar otorisasi ditarik. |
| W2-011 | **Valid; prioritas P2** | Race ack versus resolve terbukti dari dua sesi operator berbeda. Tidak ada bukti bahwa race ini sendiri mengubah stok atau mengizinkan gate keluar, sehingga P1 sebelumnya terlalu tinggi untuk dampak yang dibuktikan. |
| W2-012 | **Valid; P2, terkait RF-16** | Dua HTTP ingest dengan read ID berbeda menghasilkan dua insiden dan dua notifikasi. Terulang pula tanpa barrier. Tetap tiket stabil untuk race insiden, bukan klaim akar masalah yang sepenuhnya independen dari RF-16. |

## Apa yang keliru dalam kesimpulan sebelumnya

1. **Insiden memang dirancang SHARED.** [entity_scope.py:38](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/entity_scope.py#L38) menetapkan reads mengikuti owner, tetapi [L45–47](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/entity_scope.py#L45) menyebut log keamanan lintas entitas dan menetapkan incidents SHARED. [rfid_service.py:190](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/rfid_service.py#L190) menyatakan device infra bersama. HTTP200 dari A pada insiden B membuktikan perilaku, tetapi tidak cukup untuk menuduh pelanggaran terhadap kontrak yang justru global. Akses keamanan pusat tetap dapat menimbulkan risiko produk; batas operator lokal/pusat perlu kontrak yang jelas sebelum patch.
2. **Fixture gudang awal bukan dedicated B.** Field `entity_id=B` tidak mendefinisikan kepemilikan gudang; kontrak memakai `sharing_mode` dan `entity_ids`. [warehouse_scope_service.py:54–75](https://github.com/pandeyoga/KNHOST/blob/ea874d3b86ecdbaeacded1d2e1c35b71d3fa1b63/backend/services/warehouse_scope_service.py#L54) menganggap gudang tanpa field sharing sebagai shared. Interpretasi awal diperbaiki; runtime awal tidak dihapus.
3. **Kontrol C09 tidak membuktikan data A lengkap.** Setelah 500 EPC asing dimasukkan, list default100 didominasi row owner null. Hasil tidak ber-owner B hanya membuktikan penyaringan warehouse pada baris yang dikembalikan. Uji ulang memakai perbandingan API tags dan reads untuk roll sama sebagai kontrol scope yang lebih kuat.
4. **Race insiden dan izin keluar gate punya dampak berbeda.** W2-011 tetap cacat, tetapi prioritas tidak boleh diturunkan dari risiko RF-02/03 yang berbeda akar. Prompt dan tracker W2-011 dikoreksi menjadi P2.
5. **RF-16 serial replay tidak selalu membuat incident baru.** Pengujian E01 menunjukkan dua raw reads tetapi satu insiden hits2 ketika kedua batch serial dan insiden masih open. RF-16 tetap gap event/passage identity; raw read berulang sendiri tidak selalu salah karena dapat merepresentasikan observasi sensor yang sah. Duplikasi insiden konkuren dibuktikan secara khusus oleh W2-012.

## Metode dan hasil tambahan

[Harness independen](repro/validate_w2_rfid.py) memakai database sintetis baru dengan network outbound diblokir. Bootstrap `ensure_performance_indexes()` dijalankan: 210 indeks reguler dibuat, penghitung indeks nomor dokumen unik25, tanpa kegagalan yang dilaporkan. Ini bootstrap indeks yang tersedia di kode; bukan inspeksi indeks database produksi. Lifespan/scheduler dan hardware tidak diaktifkan.

- Gudang SH shared dan DB dedicated B dibuat dengan field yang benar. `is_usable(DB,A)` false, `is_usable(SH,A)` true. Produk fixture, roll inbound, tag dan device dibuat melalui service aplikasi asli. Tidak memakai data pengguna.
- **W2-010:** pada SH dan DB, user A mendapat nol tag B dari `/rfid/tags`, tetapi mendapat row ownerB dari `/rfid/reads`. Meminta tags dengan header B ditolak403. Jadi temuan raw reads tetap valid setelah memperbaiki fixture.
- **Observasi kebijakan:** list/ack/resolve insiden, health dan shrinkage lintas owner tetap200, termasuk pada dedicated B yang benar. Ini dicatat sebagai kontrak keamanan bersama yang perlu diperjelas, bukan enam bukti pelanggaran baru.
- **W2-011:** insiden dibuat ingest asli; user1 mulai ack, ditahan sebelum update, user2 menyelesaikan; ack lalu lanjut. Kedua200, status akhir acknowledged, resolved_by tetap user2. Barrier hanya menahan operasi tulis Mongo asli. Kontrol serial resolve lalu ack menghasilkan200/400.
- **W2-012:** dua request ingest HTTP tanpa sesi user, hanya device key fixture, memicu dua read ID berbeda. Dengan barrier pada pembacaan dedupe, dua insiden open hits1 dan dua notifikasi tercipta. Koleksi insiden memiliki indeks `_id` saja setelah bootstrap. Kontrol serial menghasilkan satu insiden hits2.
- **Tanpa instrumentasi:** 10 pasangan HTTP ingest bersamaan menghasilkan jumlah insiden `[2,2,2,2,2,2,2,1,2,2]`. Jadi sembilan pasangan mereproduksi bug alami dalam lingkungan lokal ini. Ini bukan estimasi frekuensi di produksi atau uji beban.

Semua hasil dan parameter tersimpan di [results.json](validation/W2-05-review/results.json). Sepuluh probe review merupakan pendalaman bukti, tidak menambah total coverage aplikasi.

## Replay seluruh putaran sebelumnya

Seluruh24 skenario harness awal dijalankan ulang tanpa mengubah aturan bisnis/asersi dan menghasilkan observasi sama: [replay-original-results.json](validation/W2-05-review/replay-original-results.json). Ini mengonfirmasi hasil runtime awal, **bukan otomatis membenarkan label defect**. Bukti awal [rfid-results.json](rfid-results.json) dipertahankan utuh; klasifikasi terbarunya disimpan terpisah pada [classification.json](validation/W2-05-review/classification.json).

F02–F07 direklasifikasi dari `defect` ke `policy_observation`; F01/F08/F09 tetap defect. Karena itu W2-05 berisi10 kontrol, tiga reproduksi cacat, enam observasi kebijakan, lima pendalaman Gelombang1. Kumulatif seluruh Gelombang2 tetap63 skenario:38 kontrol,14 reproduksi cacat W2,6 observasi kebijakan,5 pendalaman Gelombang1. Jumlah ID tracker tetap12 karena inti W2-010 masih valid. Jangan menyamakan12 ID tiket dengan12 akar masalah yang semuanya independen.

## Arahan implementasi setelah koreksi

Gunakan [prompt revisi](11_PROMPT_RFID_GATE_DAN_INSIDEN.md). W2-010 memperbaiki scope raw reads sesuai registry, tanpa otomatis mengubah keamanan global menjadi per-owner. W2-011 memperbaiki transisi atomik, W2-012 memperbaiki dedupe atomik serta notifikasi dan berkoordinasi dengan RF-16. Sampai kontrak akses pusat/lokal disepakati, perubahan policy insiden/device/laporan dipisahkan dari tiga patch tersebut. UI diperiksa dari source saja; belum ada browser UAT, perangkat fisik, atau validasi build perbaikan.
