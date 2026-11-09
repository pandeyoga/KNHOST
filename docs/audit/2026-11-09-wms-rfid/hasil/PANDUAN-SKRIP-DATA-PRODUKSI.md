# Panduan — menjalankan skrip perbaikan data di PRODUKSI (VPS, DB `kainnusantara`)

- Paket: FIX-7 butir 6 (10 Nov 2026). Berlaku untuk 5 skrip:

| Skrip | Asal | Isi singkat |
|---|---|---|
| `scripts/fix_data_2026_11_09_tandai_data_uji.py` | FIX-1 (K-B1-10) | memberi penanda `is_test` pada gudang/site/PT bernama uji (`TEST-…`, `TEST_…`, `PT Uji Provisioning…`) — **tidak menghapus** |
| `scripts/fix_data_2026_11_09_gedung_bersama.py` | FIX-1 (K-GDG-07) | gedung aktif `dedicated` (khusus satu PT) → `shared` (dipakai bersama) |
| `backend/scripts/migrate_fix2_inspection_hold_status.py` | FIX-2 (B3a SSOT-3) | roll yang ditahan inspeksi tetapi masih `available`/`quarantine` → `blocked` (+ saldo dibangun ulang) |
| `scripts/fix_data_2026_11_09_fix3a_alur_masuk.py` | FIX-3a | transfer 0 roll diterima → `returned`; roll `hold` transfer → `blocked`; "Roll ID" teks bebas di `rfid_tag_id` → `supplier_roll_no`; tag roll habis-opname → `retired`; eskalasi atas barang terposting → status asal; + laporan PO diterima > 1,5× |
| `scripts/fix_data_2026_11_09_fix3b_alur_keluar.py` | FIX-3b | mode simulasi RFID PT nyata → mati; roll di SJ aktif yang `available` → `in_transit_sales`/`delivered`; reservasi milik SO mati → `available` (+ mutasi `release_reservation`); roll SJ ber-POD → `delivered`; eskalasi tugas terminal → `cancelled`; penanda transfer basi; roll habis "hidup lagi" → `consumed`; SO sampel berbayar batal → `refund_pending`; + laporan EPC ganda |
| `scripts/fix_data_2026_11_10_fix6_retur_masuk_stok.py` | FIX-6 (keputusan pemilik 10 Nov, D5/D2) | retur penjualan terbuka yang rollnya sudah dipindai tetapi masih `delivered` → karantina retur (nilai 0, jurnal tetap saat settle) lewat layanan pindai; + LAPORAN retur beli tolak-QC tanpa pilihan "ganti barang / potong tagihan". **Tanpa `--undo`** (pembalik = tolak retur di aplikasi). Pagar disamakan dengan modul ini saat integrasi (dulu `--allow-db`) |
| `scripts/fix_data_2026_11_10_fix9_kunci_makloon.py` | FIX-9 (B3a SSOT-4) | cadangan makloon aktif dikunci ke roll nyata (FIFO, gudang sumber MKO/PR); kunci yatim dilepas; cermin `locked_qty` dibangun ulang. Angka "Tersedia" tidak berubah; roll terkunci tidak bisa dipilih untuk SO/POS/transfer. Punya `--undo`; pagar setara (salinan aturan modul ini) |

Semua skrip **tidak** menyentuh jurnal/GL, nilai roll, atau data UAT "test" (`SORD-261023-0003`).

## 1. Pagar keamanan (apa yang dicek skrip)

| Aturan | Perilaku |
|---|---|
| DB uji (`kn_test_trial`, `test_database`) | diterima seperti dulu, tanpa flag tambahan |
| DB produksi `kainnusantara` | **wajib** `--production`; tanpa itu → `DITOLAK` (kode keluar 2) |
| DB lain | `DITOLAK` (migrasi FIX-2 dulu menulis ke DB apa pun yang ditunjuk `DB_NAME`) |
| Bukti backup (wajib untuk `--production`, juga dry-run) | salah satu: **(a)** berkas terlihat (`--backup-file <jalur>` atau otomatis dari `deploy/backups` / `--backup-dir`) → diperiksa nama `kainnusantara-…archive.gz`, umur berkas < 24 jam, ukuran ≥ 100 KB, gzip **utuh** (dibaca sampai habis) dan berisi arsip mongodump — arsip setengah jadi ditolak; **(b)** berkas tidak terlihat dari kontainer → `--backup-file kainnusantara-YYYY-MM-DD_HHMM.archive.gz` (nama keluaran `deploy/backup.sh`), cap waktu di nama dibaca sebagai WIB dan harus < 24 jam; **(c)** `--backup-confirmed "<nama berkas + siapa yang memeriksa>"` (≥ 5 huruf) — konfirmasi manual, dicatat apa adanya |
| Bawaan | **dry-run**: tidak menulis apa pun, mencetak daftar perubahan per dokumen (`koleksi id label: field: sebelum → sesudah`) dan jumlah per langkah |
| `--apply` | menulis perubahan + **jejak**: satu baris `audit_logs` per dokumen (aksi `data_fix_applied`, `before`/`after`, `source = <skrip>#<putaran>`, terlihat di layar Jejak Audit) + sumber undo di koleksi `migrations` (`<skrip>:changes:<putaran>:<n>`, nilai SEBELUM persis) + ringkasan putaran di `migrations.<skrip>.run_log` (DB, produksi, bukti backup, jumlah per langkah) |
| `--undo` (+ `--apply`) | membalik putaran `--apply` terakhir yang belum dibalik (atau `--run-id <putaran>`): field dipulihkan persis (field yang dulu tidak ada dihapus lagi), entri riwayat yang ditambahkan dicabut, mutasi `release_reservation` yang disisipkan dihapus, saldo segmen roll terkait dibangun ulang. Dokumen yang **sudah diubah orang lain sesudah skrip** dilewati (`LEWAT …`) — tidak ditimpa. Tanpa `--apply` = dry-run undo |
| Lain | `--show N` (baris contoh per langkah, 0 = semua), `--report /tmp/x.json` (laporan lengkap JSON) |

Catatan cap waktu: `deploy/backup.sh` memberi nama berkas dengan jam **host VPS**. Bila host ber-UTC, skrip (yang membaca nama
sebagai WIB) menghitung backup 7 jam lebih tua → aturan menjadi lebih ketat (backup ≤ ±17 jam), tidak pernah lebih longgar.

## 2. Prasyarat

1. Kode di VPS sudah memuat FIX-7 (modul `backend/services/data_fix_guard.py` ada di image):
   ```bash
   cd /opt/kainnusantara
   git log --oneline -1                     # pastikan commit FIX-7 sudah ada
   bash deploy/update.sh                    # bila belum: tarik kode & bangun ulang (data tidak dihapus)
   ```
   Bila image belum bisa dibangun ulang, salin modulnya sementara:
   `docker cp backend/services/data_fix_guard.py kn-backend:/app/backend/services/data_fix_guard.py`
   (dan `docker cp backend/scripts/migrate_fix2_inspection_hold_status.py kn-backend:/app/backend/scripts/`).
2. Kode perbaikan FIX-1/2/3a/3b sudah ter-deploy (sudah — `main` di produksi). Skrip data hanya merapikan sisa data lama;
   tanpa kode perbaikan, data salah bisa lahir lagi.
3. Jalankan saat gudang **sepi** (tidak ada penerimaan/gate/handheld berjalan) — pengecekan "tidak diubah orang lain"
   saat undo bergantung pada itu, dan saldo segmen dibangun ulang.
4. Satu operator, satu skrip pada satu waktu (jangan dua jendela menjalankan skrip yang sama bersamaan).

## 3. Langkah per skrip (contoh: fix3b)

Singkatan yang dipakai di bawah:
```bash
cd /opt/kainnusantara
DC="docker compose --env-file deploy/.env -f deploy/docker-compose.yml"
```

**Langkah 1 — backup baru** (wajib; < 24 jam):
```bash
bash deploy/backup.sh
B=$(ls -t deploy/backups/kainnusantara-*.archive.gz | head -1); echo "$B"; ls -lh "$B"
gzip -t "$B" && echo "arsip utuh"
```

**Langkah 2 — salin skrip ke kontainer** (kontainer produksi hanya berisi `/app/backend`; folder `scripts/` tidak ikut image):
```bash
$DC exec -T backend mkdir -p /app/scripts
docker cp scripts/fix_data_2026_11_09_fix3b_alur_keluar.py kn-backend:/app/scripts/
```
(`migrate_fix2_inspection_hold_status.py` sudah ada di image: `/app/backend/scripts/…`.)

**Langkah 3 — dry-run** (tidak menulis apa pun; baca daftarnya):
```bash
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py \
    --db kainnusantara --production --backup-file "$(basename "$B")" --show 0 --report /tmp/fix3b_dry.json \
  | tee "fix3b_dry_$(date +%F_%H%M).txt"
docker cp kn-backend:/tmp/fix3b_dry.json ./fix3b_dry.json          # simpan laporan lengkap
```
Contoh keluaran (salinan data acuan berganti nama `kainnusantara`):
```
== fix_data_2026_11_09_fix3b_alur_keluar · DRY-RUN · DB kainnusantara (PRODUKSI) · mongodb://mongo:27017
   bukti backup: name_stamp — kainnusantara-2026-11-10_0040.archive.gz (±0.06 jam)
   PERINGATAN: isi berkas backup TIDAK diperiksa skrip (berkas tidak terlihat dari proses ini; …)
   DRY-RUN: tidak ada yang ditulis. Tambah --apply untuk menerapkan.
  [rfid_simulation_off] 3 perubahan — mode simulasi RFID PT nyata/global → mati
      · config_values cfgv_32648d75f43b entity:ent_ksc: value: True → False; updated_by: ∅ → Sistem (FIX-3b …); note: ∅ → …
  [pod_rolls_in_transit] 6 perubahan — roll in_transit_sales pada SJ ber-POD → delivered
      · inventory_rolls roll_b123b1c8baa8 RL-00011: status: in_transit_sales → delivered; delivered_at: ∅ → …; delivered_via: ∅ → fix3b_pod_per_sj
  [epc_reuse_report] 0 (laporan saja, tidak diubah) — EPC dipakai >1 tag — cek fisik, tidak diubah otomatis
DRY-RUN (tidak ada yang diubah) — DB kainnusantara: 9 perubahan dokumen
```
Periksa: jumlah wajar? ada nomor yang Anda kenal sebagai transaksi aktif yang **tidak** boleh berubah? Bila ragu — berhenti.

**Langkah 4 — terapkan:**
```bash
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py \
    --db kainnusantara --production --backup-file "$(basename "$B")" --apply --show 0 \
  | tee "fix3b_apply_$(date +%F_%H%M).txt"
```
Catat nomor `putaran …` dari keluaran (dipakai untuk `--undo --run-id`).

**Langkah 5 — verifikasi:**
```bash
# a. jalankan dry-run lagi → semua langkah 0 perubahan (idempoten)
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py \
    --db kainnusantara --production --backup-file "$(basename "$B")" | grep -E "^\s+\[|DRY-RUN \("
# b. jejak audit putaran itu
$DC exec -T mongo mongosh kainnusantara --quiet --eval \
  'db.audit_logs.countDocuments({source: /^fix_data_2026_11_09_fix3b_alur_keluar#/})'
# c. ringkasan putaran
$DC exec -T mongo mongosh kainnusantara --quiet --eval \
  'printjson(db.migrations.findOne({id: "fix_data_2026_11_09_fix3b_alur_keluar"}, {_id: 0, run_log: 1}))'
```
Lalu cek di aplikasi: Stok › Roll (status roll yang berubah), papan stok (angka Tersedia segmen terkait), Pusat
Pengaturan › mode simulasi RFID per PT (fix3b), Master Gudang (fix1), Jejak Audit (cari aksi `data_fix_applied`).

**Langkah 6 — bila perlu dibalik:**
```bash
# dry-run undo dulu
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py \
    --db kainnusantara --production --backup-file "$(basename "$B")" --undo --run-id <putaran>
# terapkan undo
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py \
    --db kainnusantara --production --backup-file "$(basename "$B")" --undo --run-id <putaran> --apply
```
Baris `LEWAT …` = dokumen sudah diubah pengguna/sistem sesudah skrip — tidak ditimpa; tangani manual bila perlu.
Undo tidak tersedia untuk putaran yang dijalankan **sebelum** FIX-7 (tanpa nilai sebelum); `gedung_bersama` &
`tandai_data_uji` tetap bisa membalik putaran lama lewat jejak lama/penanda.

Perintah per skrip lain sama polanya — ganti nama berkas:
```bash
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_tandai_data_uji.py   --db kainnusantara --production --backup-file "$(basename "$B")" [--apply] [--undo]
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_gedung_bersama.py    --db kainnusantara --production --backup-file "$(basename "$B")" [--apply] [--undo]
$DC exec -T backend python /app/backend/scripts/migrate_fix2_inspection_hold_status.py --db kainnusantara --production --backup-file "$(basename "$B")" [--apply] [--undo]
$DC exec -T backend python /app/scripts/fix_data_2026_11_09_fix3a_alur_masuk.py  --db kainnusantara --production --backup-file "$(basename "$B")" [--apply] [--undo]
$DC exec -T backend python /app/scripts/fix_data_2026_11_10_fix6_retur_masuk_stok.py --db kainnusantara --production --backup-file "$(basename "$B")" [--apply]
$DC exec -T backend python /app/scripts/fix_data_2026_11_10_fix9_kunci_makloon.py   --db kainnusantara --production --backup-file "$(basename "$B")" [--apply] [--undo]
```

### Alternatif yang lebih ketat: kontainer sekali-pakai (backup diperiksa isinya)
Dengan `run --rm`, folder skrip & backup di-mount **baca-saja**, sehingga skrip bisa memeriksa isi backup (gzip utuh,
arsip mongodump, umur berkas) — tanpa menyalin apa pun ke kontainer yang sedang melayani pengguna:
```bash
$DC run --rm --no-deps \
    -v "$PWD/scripts:/app/scripts:ro" -v "$PWD/deploy/backups:/app/deploy/backups:ro" \
    backend python /app/scripts/fix_data_2026_11_09_fix3b_alur_keluar.py --db kainnusantara --production [--apply]
```
(tanpa `--backup-file`: skrip memilih backup `kainnusantara-*.archive.gz` terbaru di `/app/deploy/backups`; keluaran
`bukti backup: file_verified …`).

## 4. Urutan yang disarankan & alasannya

1. **`tandai_data_uji`** — hanya penanda, tidak menyentuh stok; di produksi kemungkinan 0 kandidat (data uji ada di DB uji).
   Periksa daftar: data NYATA yang kebetulan bernama `TEST…` akan ikut tertandai (bisa dibalik).
2. **`gedung_bersama`** — kebijakan gedung (K-GDG-07). Tidak mengubah stok; mengubah gedung yang boleh dipakai PT lain.
   Pastikan pemilik setuju gedung yang tercantum menjadi bersama.
3. **`migrate_fix2_inspection_hold_status`** — menyelaraskan status roll yang ditahan inspeksi (stok Tersedia turun untuk
   roll itu). Dijalankan sebelum fix3a/3b agar status roll sudah benar saat langkah berikutnya membaca roll.
4. **`fix3a_alur_masuk`** — data alur masuk (transfer, tahan, tag, eskalasi masuk).
5. **`fix3b_alur_keluar`** — data alur keluar (SJ, reservasi SO, POD, eskalasi ambil, sampel) + **mematikan mode simulasi
   RFID** untuk PT nyata — wajib sebelum reader gate sungguhan dipasang.
6. **`fix6_retur_masuk_stok`** — sesudah kode FIX-6 ter-deploy. Kemungkinan 0 roll di produksi; bagian laporan (retur
   beli tolak-QC tanpa pilihan penyelesaian) diteruskan ke bagian pembelian untuk diputuskan ulang bila perlu.
7. **`fix9_kunci_makloon`** — sesudah kode FIX-9 ter-deploy. Mengunci cadangan makloon yang sudah ada ke roll; jalankan
   di jam sepi (roll yang terkunci langsung hilang dari pemilih roll SO/POS).

Setiap skrip berdiri sendiri dan idempoten; urutan di atas meminimalkan langkah yang saling memengaruhi. Catatan fix3b:
dry-run menghitung tiap langkah atas data sekarang, sedangkan saat `--apply` langkah berikut melihat hasil langkah
sebelumnya (mis. roll yang dipulihkan langkah 2 bisa ikut langkah 4) — jumlah `--apply` bisa sedikit berbeda.

## 5. Risiko & mitigasi

| Risiko | Mitigasi |
|---|---|
| Salah DB | `--db kainnusantara` + `--production` wajib; DB lain ditolak; baris pertama keluaran menyebut DB & host |
| Tanpa backup / backup rusak | bukti backup < 24 jam wajib; dengan `run --rm` isi arsip diperiksa; selalu `gzip -t` sendiri |
| Data berubah di tengah | tulisan bersyarat (status lama) per dokumen; undo melewati dokumen yang sudah diubah orang lain |
| Saldo tidak cocok sesudah perubahan status roll | saldo segmen dibangun ulang otomatis (apply & undo); cek papan stok |
| Mode simulasi RFID dimatikan saat masih dipakai uji di PT nyata | fix3b langkah 1 — konfirmasi ke tim RFID; bisa dibalik dengan `--undo` |
| Cache setelan di backend | setelan yang diubah skrip (mode simulasi RFID) dibaca ulang backend sesudah cache setelan kedaluwarsa; bila ragu `$DC restart backend` di jam sepi |

## 6. Pulih total dari backup (pilihan terakhir)

`--undo` lebih aman. Pemulihan backup menimpa **seluruh** DB ke keadaan saat backup (transaksi sesudahnya hilang):
```bash
$DC stop backend
bash deploy/backup.sh restore deploy/backups/kainnusantara-YYYY-MM-DD_HHMM.archive.gz
$DC start backend
```

## 7. Uji yang sudah dijalankan (salinan data acuan berganti nama `kainnusantara`, 10 Nov 2026)
- tanpa `--production` → DITOLAK; `--production` tanpa bukti → DITOLAK; backup tua/terpotong/kecil/DB lain/bukan
  mongodump → DITOLAK; DB lain → DITOLAK; DB uji lama tanpa flag → diterima.
- dry-run → apply → apply ulang (0 perubahan) → undo semua skrip: dokumen di 11 koleksi yang disentuh **identik** dengan
  sebelum apply, kecuali `updated_at` 2 gedung (undo `gedung_bersama` sengaja memberi cap waktu baru) dan metadata
  rebuild 1 saldo (jumlah tidak berubah).
- `backend/tests/test_fix7_data_scripts.py` (7 uji: pagar, bukti backup, dry-run tidak menulis, jejak, undo persis termasuk
  field bertitik/riwayat/mutasi sisipan, undo melewati dokumen yang diubah sesudahnya).
