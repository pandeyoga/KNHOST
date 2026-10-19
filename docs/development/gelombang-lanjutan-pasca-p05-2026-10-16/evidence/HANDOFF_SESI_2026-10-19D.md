# Handoff sesi 2026-10-19D — keputusan CUT-01 & GL-01 dicatat, siap dikerjakan

Konteks: lanjutan sesi C (commit `e629d1c`, lihat HANDOFF_SESI_2026-10-19C.md). Sesi ini **hanya mencatat** keputusan owner dan menyusun rancangan + daftar persetujuan. Belum ada perubahan kode.

- Keputusan: [DECISIONS_OWNER_2026-10-19C.md](DECISIONS_OWNER_2026-10-19C.md)
- Rancangan: [RANCANGAN_PEMETAAN_AKUN_DAN_CUTLOSS.md](../RANCANGAN_PEMETAAN_AKUN_DAN_CUTLOSS.md)

## Rencana fase berikutnya (commit + push tiap fase, `scripts/push_github.sh`)
1. **Fase A — Registri & resolver akun**: `gl_mapping_registry.py`, koleksi `gl_account_mappings`, `gl_service.account_for()`; API `GET/PUT /api/gl/account-mappings` (+riwayat). Konstanta lama tetap jadi default → tidak ada perubahan perilaku. Uji: jurnal yang ada identik sebelum/sesudah.
2. **Fase B — UI Pemetaan Akun** (Pengaturan → Keuangan): grup per modul, combobox akun ter-filter jenis, contoh jurnal, scope Global/PT, alasan + riwayat, kartu "belum diatur".
3. **Fase C — Migrasi pemakai** konstanta → resolver, per modul (retur, persediaan, penjualan, pembelian, makloon, kas, payroll, aset, interco). Gate: trial balance seimbang, `verify_data_integrity` tanpa FAIL baru.
4. **Fase D — Jurnal ongkir retur** (GL-01 × KLR-11) memakai key `returns.logistics.*`, idempoten, jurnal balik saat ubah/batal.
5. **Fase E — Pemecahan roll cutloss** (CUT-01): pilihan BS/Dibuang, pratinjau potongan, child roll berurutan, disposal & jurnal.
6. **Fase F — Testing agent + handoff.**

Default sementara (dipakai bila pertanyaan di bawah belum dijawab, ditandai "asumsi" di UI/laporan): ongkir perusahaan → akun baru **6-4510 Beban Ongkir Retur** (anak 6-4500), lawan **Kas Kecil 1-1110**; ongkir customer → **Piutang 1-1200**; jurnal saat biaya disimpan; BS dinilai HPP proporsional panjang; potongan dibuang → **5-9500**; yang memilih BS/Dibuang = MD/QC (izin `sales_return.record_cutloss`); hanya admin mengubah pemetaan akun.

## Butuh persetujuan owner

### Baru dari keputusan ini
| ID | Pertanyaan | Default sementara |
|---|---|---|
| CUT-02 | Siapa yang memilih BS atau Dibuang: MD/QC saat input cacat, atau Finance saat memutus kompensasi? | MD/QC, Finance bisa mengubah sebelum diproses |
| CUT-03 | Nilai persediaan potongan BS: HPP proporsional panjang, nol (seluruhnya dihapus), atau harga BS master? | HPP proporsional |
| CUT-04 | Kapan roll dipecah fisik: langsung saat QC mencatat, atau setelah Finance memutus kompensasi? | Setelah Finance memutus |
| CUT-05 | Potongan baik yang dikembalikan ke customer: memakai SJ/pengiriman baru di modul Logistik, atau cukup dicatat? | SJ baru lewat alur pengiriman existing |
| GL-02 | Akun ongkir ditanggung perusahaan: buat akun baru "Beban Ongkir Retur" atau pakai 6-4500 Beban Kirim Dokumen & Ekspedisi? | Akun baru 6-4510 |
| GL-03 | Kapan ongkir dijurnal: saat biaya diisi, saat retur diselesaikan (settle), atau saat dibayar? | Saat biaya disimpan |
| GL-04 | Lawan ongkir perusahaan: kas kecil, bank, atau hutang ekspedisi (bayar belakangan)? | Kas kecil, bisa dipilih per kasus |
| GL-05 | Ongkir ditanggung customer: ditagih sebagai piutang terpisah, atau dipotong dari kompensasi/saldo retur? | Dipotong dari kompensasi; sisa → piutang |
| GL-06 | PPN atas ongkir (bila ekspedisi PKP) perlu dicatat sebagai PPN Masukan? | Tidak, nominal bruto |
| GL-07 | Ongkir perjalanan QC Jakarta–Rancamalang yang melibatkan dua PT (Sukacita/CST): dibebankan ke PT yang membayar saja, atau dibuat tagihan antar-PT? | PT yang membayar saja |
| GL-08 | Siapa boleh mengubah pemetaan akun dan perlukah persetujuan kedua (maker-checker)? Perubahan berlaku ke depan saja (jurnal lama tidak diposting ulang) — setuju? | Admin saja, tanpa maker-checker, berlaku ke depan |

### Dari sesi sebelumnya (masih terbuka)
| ID | Hal | Catatan |
|---|---|---|
| ACC-KP-01 | Sales boleh melihat daftar Keep/Pending? Tes lama mengharapkan 403, sistem kini 200. | Perlu kepastian agar tes atau kode disesuaikan |
| D1–D8 | Penggabungan duplikasi (jendela retur 4 tempat, batas poin grade 2 tempat, grade hardcode, sumber restock, panel perjalanan retur ganda, Meja Sample vs Cutting, 2 inbox persetujuan, docstring basi) | Lihat REVIEW_STATUS_DAN_DUPLIKASI_2026-10-19.md bagian C |
| DATA-01 | Dataset migrasi master bahan/supplier/warna | Menunggu file data |
| DES-02/03/04 | Contoh dokumen leg logistik, format rapor, konteks entitas MD | Menunggu contoh/persetujuan desain |
| HW-01/HW-02 | Perangkat Chainway RFID & absensi nyata untuk uji | Butuh perangkat fisik |
| HR-01 | Aturan HR/absensi final | Menunggu aturan |
| UAT-01 | Lingkungan pilot & persetujuan akhir | Menunggu jadwal |
| VAL-01 | Reviewer terpisah + approval owner untuk mengubah status BACKLOG ke validated | Aturan DEFINITION_OF_DONE |

Temuan teknis tanpa persetujuan (akan diperbaiki langsung): filter `?stage=` di `GET /api/products?paginate=true` tidak menyaring; baris tugas terima di Meja Saya menampilkan "0.0 yard" dan judul kartu masih "picking & packing".
