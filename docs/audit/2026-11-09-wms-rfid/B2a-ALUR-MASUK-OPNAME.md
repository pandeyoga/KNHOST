# Audit B2a — Logika alur BARANG MASUK, penyimpanan & opname (end-to-end, per cabang)

- Tanggal: 9 Nov 2026 (WIB) · Pelaksana: Claude Code (auditor paket B2a) · Jenis: **audit, tanpa perubahan kode aplikasi**.
- Basis kode: worktree audit di-*fast-forward* ke `main` (`8d4b6cd`, berisi gelombang 2 PREP + laporan B3b/B4).
- Lingkungan: stack sementara `kn-tmp-b2a-mongo` + `kn-tmp-b2a-be` (kode disalin ke kontainer, tanpa mount), DB
  `test_database` = salinan snapshot `kn_test_trial_2026-11-08`. Semua alur dijalankan **lewat API** sebagai akun peran
  demo (petugas Soreang/Rancamalang/Jakarta, admin gudang, MD Quality, QC, manajer, admin). Potret DB sebelum/sesudah
  tiap langkah ada di [`bukti-B2a/`](bukti-B2a/) (keluaran apa adanya); skrip uji di `scripts/audit/b2a/`
  (**hanya untuk stack sementara** — skrip mengubah data).
- Lampiran: **[`B2a-TRANSISI-STATUS.md`](B2a-TRANSISI-STATUS.md)** — 112 transisi status dari kode (10 dokumen), 86
  dijalankan, 34 menyimpang.
- Silang paket lain: B3b (form/isian — INP-01 bin teks bebas, INP-02 bin opname, FRM-02 HP vs desktop, FRM-23),
  B4 (standar UI WMS — patokan "satu tugas = satu gedung, pindai per dokumen"), B1 (UI per peran), B3a (SSOT angka).

> Catatan data: snapshot 8 Nov **belum** memuat profil gedung PREP-C (skrip `fix_data_2026_11_08_profil_gedung.py`
> belum dijalankan di DB koordinator). Untuk cabang gedung inspeksi, RCM-RETUR diberi peran `inspection` lewat API admin
> (`PATCH /warehouses/{id}`) — sama dengan isi skrip itu. Mode penerimaan: KSC dialihkan ke `grn` untuk alur B,
> Kanda tetap `legacy`. OCR mati di semua PT (tanpa kunci API) — jalur "isi manual" yang diuji.

---

## 0. Ringkasan

### 0.1 Alur & cabang yang dijalankan (sampai dokumen tertutup)
| Kode | Alur | Cabang | Hasil akhir | Bukti |
|---|---|---|---|---|
| A | PO KSC → Rancamalang (legacy, **jalur HP**) → selesai → karantina + SPK MD Quality → tutup "terima" → **draf PA otomatis** → ubah tujuan → verifikasi label → terbit → kirim → trip → simpan ke bin | gedung transit → gedung simpan | PA `completed` + BTG, roll `stored` di bin | `fa_legacy`, `fa2`, `fa3` |
| B | PO KSC (mode **GRN**): foto SJ, OCR (mati) → isi manual, satuan SJ ≠ PO, kiriman **parsial** 2/3 roll, hitung roll, selisih, tutup → karantina → tugas **sisa** → GRN ke-2 (SJ sama → tolak) → SPK → draf → terbit **tanpa kirim** → **trip 1 tiba sebagian** → ulang trip (idempoten) → **tutup sisa kembali ke transit** | parsial, satuan berbeda, multi-trip | GRN `closed` ×2, PO `completed`, PA `completed` (1 tiba + 1 kembali) | `fb_grn`, `fb2_trips` |
| C | PO Kanda → Soreang SRG-01 (**gedung tunggal**), 3 roll lewat payload desktop, bin teks bebas | gedung tunggal; PO KSC ke Soreang | roll langsung `stored` (tanpa PA); PO KSC ditolak | `fc_single`, `fc2` |
| D | Roll **ditahan** saat karantina → tutup SPK "terima" (B1) / "terima sebagian" / antrean → lepas tahanan → terima; SPK **QC 4-point**; gedung **inspeksi** (RCM-RETUR) | roll ditahan, inspeksi per 15 yard | draf PA ke gedung inspeksi; roll gagal 4-point ditahan | `fd_hold`, `fd2` |
| G | **Batal di tengah**: batal PO sesudah pindai label · eskalasi kiriman kurang + pindai saat eskalasi · SPK **tolak + retur supplier** · batal PO saat GRN dihitung · **batal GRN** | batal, tolak, retur | lihat temuan | `fg_cancel`, `fg2` |
| H | **Transfer masuk** RCM-WOVEN → WH-JKT: terima per roll (parsial) oleh petugas lokasi lain, ulang terima, roll hilang → kembali ke asal; transfer 0 diterima | parsial, selesai | `completed` | `fh_transfer`, `fh2` |
| I | **Retur penjualan terima barang** SRET-00167: pindai diterima di Gedung Retur → inspeksi grade A → settle (store credit) → karantina → lepas | grade A di gedung grade B/BS/C | roll `available` di Gedung Retur | `fi_return` |
| J | **Opname per roll** WH-JKT (satu bin): potret → pindai (cocok, roll tanpa bin, kode asing, petugas lokasi lain) → hitung ulang → ACC (hapus + temuan + jurnal) · roll ber-tag dihapus | hilang/surplus | `approved_with_exceptions` | `fj0`, `fj_opname`, `fj2`, `fm_misc` |
| K | **Pendaftaran awal** SRG-01 rak W01 (beku per rak, EPC sistem): uji pembekuan (place_roll, terima PO, opname biasa) → baris lapangan (roll lama cocok, roll baru, produk belum dikenali) → ajukan → kembalikan → petakan → ACC massal | beku zona | `approved`, 66/67 roll lama dihapus, 3 jurnal | `fk_reg`, `fk2` |
| L | **Daftar tugas** masuk/QC/PA/GRN/opname/pendaftaran/SPK/transfer × 7 akun × konteks PT bawaan & "Semua" | siapa melihat apa | matriks | `fl_lists` |
| M/O | Sesi pendaftaran ditolak lalu dibuka lewat opname biasa · **tugas `qc_rejected` diterima ulang dari HP** | — | lihat temuan | `fm_misc`, `fo_reopen` |

Tidak dijalankan (kode saja, ditandai *kandidat*): gate V2 nyata (butuh perangkat terdaftar + amplop HMAC — paket D2
punya uji sendiri 11/11), hasil makloon & perbaikan kembali, OCR dengan kunci API, konkurensi (dua pindai bersamaan).

### 0.2 Temuan per keparahan
| Keparahan | Jumlah | ID |
|---|---|---|
| **P0** | 4 | FLW-IN-01, OPN-01, STM-IN-01, STM-IN-02 |
| **P1** | 11 | FLW-IN-02, FLW-IN-03, FLW-IN-04, FLW-IN-05, FLW-IN-06, FLW-IN-07, FLW-IN-08, FLW-IN-09, OPN-02, OPN-03, STM-IN-03 |
| **P2** | 16 | FLW-IN-10 … FLW-IN-19, OPN-04 … OPN-07, STM-IN-04, STM-IN-05 |
| **P3** | 4 | FLW-IN-20, FLW-IN-21, STM-IN-06, STM-IN-07 |
| **Total** | **35** | 29 terverifikasi (dijalankan), 6 kandidat (kode) |

### 0.3 Sepuluh pola teratas (rincian §5)
1. **Penjaga status berbentuk daftar-larang** ("selain completed/cancelled boleh") → status yang lahir belakangan
   (`qc_pending`, `qc_rejected`, `escalated`) lolos → tugas tertutup bisa diterima ulang (FLW-IN-01, -06).
2. **Cakupan lokasi hanya di daftar & pembuatan**, tidak di aksi lanjutan (terbit/kirim/tiba/tutup/terima/pindai)
   (STM-IN-02, STM-IN-03).
3. **Kait pembekuan per titik gerak** — jalur lama/sampingan lupa dikait (terima PO, opname biasa, pengecualian PA)
   → stok ganda (OPN-01, OPN-05).
4. **Isian teks bebas mengisi rujukan stok** (bin, "Roll ID" → `rfid_tag_id`) dan melompati evaluator tunggal
   `place_roll` (FLW-IN-08, OPN-01; silang INP-01).
5. **"Aturan diisi" dianggap "aturan spesifik"** — `storage_rules.mode=category` dengan daftar kosong memenangkan
   peringkat → roll salah gedung (FLW-IN-02).
6. **Status akhir tanpa memeriksa apa yang benar-benar terjadi** (transfer `completed` 0 diterima, PO `completed`
   padahal semua ditolak, SPK "terima sebagian" padahal semua tolak) (FLW-IN-10, -11, -12).
7. **Satu roll fisik ≠ satu roll data** di jalur HP (qty saja) → label, tag, opname per roll tidak bermakna
   (FLW-IN-04).
8. **Empat konsep "tahan" & dua jalur QC/inspeksi yang tidak sinkron** (`blocked+hold`, `inspection.hold`,
   `qc_hold_pending`, `hold` transfer; antrean vs SPK; inspeksi retur vs SPK retur) (FLW-IN-03, -09, STM-IN-04).
9. **Visibilitas pekerjaan fisik dipagari PT aktif, bukan gedung** — petugas harus ganti PT atau melihat "Semua"
   tanpa label PT; jenis tugas tidak dibedakan (FLW-IN-07).
10. **Efek hilir yang tidak dibereskan** saat dokumen hulu berubah (roll `receiving` yatim, draf PA inspeksi
    menggantung, SPK retur `draft`, tag pada roll terhapus) (FLW-IN-05, -12, OPN-04).

### 0.4 Butir keputusan (rincian §6)
D1 visibilitas tugas per gedung lintas PT (K-GDG-07) · D2 tolak QC + retur → PO dibuka lagi? · D3 B1 untuk roll yang
ditahan saat karantina · D4 konversi satuan baku SJ ≠ PO · D5 kapan barang retur masuk stok · D6 arah roll retur
sesudah lepas karantina · D7 langkah "Kirim" PA wajib/opsional · D8 roll tanpa bin dalam opname · D9 satu SJ multi-PT ·
D10 status transfer 0 diterima.

---

## 1. Temuan alur barang masuk (FLW-IN)

### FLW-IN-01 — Tugas masuk yang sudah diputus QC (`qc_rejected`) / sedang QC (`qc_pending`) bisa "Terima" + "Selesai" lagi dari HP → roll baru, PO berlebih, tanpa jurnal
- **Alur/langkah/endpoint:** HP › Masuk › kartu tugas › Terima (`POST /inbound/tasks/{id}/scan-receive`) → Selesai
  (`POST /inbound/tasks/{id}/complete`).
- **Peran:** petugas gudang (Soreang).
- **Klasifikasi:** bug · **Keparahan: P0** (stok & jurnal salah).
- **Bukti (dijalankan, `bukti-B2a/fo_reopen.py.txt`):** tugas `wms_1ae06c013f7c` (KANDA/PO-00006, 50 yd) berstatus
  `qc_rejected` sesudah SPK "tolak + retur supplier" (alur G3). Daftar HP (`GET /wms/tasks`, disaring klien seperti
  `MobileWarehouseApp.jsx:49`) memuat status `qc_check, qc_pending, qc_rejected, waiting_goods` → tugas ini tampil
  sebagai tugas terbuka. Terima 1 yd → **200, status → `qc_check`, `received_qty` 51**; Selesai → **200, roll baru
  RL-46687 51 yd `quarantine`**, SPK baru. Selisih DB: `inventory_rolls +1`, `inventory_movements +1`,
  `journal_entries +0`; PO `received_qty` **50 → 101** (PO hanya memesan 50), status tetap `completed`. Jurnal GR tugas
  tetap 1.050.000 (idempoten per tugas) → **stok +51 yd tanpa Dr Persediaan / Cr GR-IR**.
- **Akar:** penjaga `scan-receive` daftar-larang `["completed", "cancelled"]` (`routers/inbound_receiving.py:66`) lalu
  `received ≥ expected → status = qc_check` (`:134-136`) menimpa status apa pun; `complete_task` menerima `qc_check`
  (`services/inbound_complete_service.py:51`). Perbaikan KN-C01 hanya menutup jalur eskalasi (`:200`), bukan
  `scan-receive`. Jalur `qc_pending` identik (status ditimpa `qc_check` → selesai lagi → roll ganda) — *dari kode*.
- **Aturan dilanggar:** invarian saldo = Σ roll dan jurnal GR = nilai barang diterima; satu baris PO tidak boleh
  diterima melebihi qty+toleransi (`receiving.block_over_remaining`, dicek dari `received_qty` tugas, bukan PO).
- **Dampak:** stok fiktif tanpa nilai buku, PO berlebih, SPK & tugas QC baru; mudah terpicu karena kartu tetap muncul.
- **Rekomendasi:** penjaga daftar-boleh `status ∈ {waiting_goods, receiving}` di filter tulis (CAS) untuk
  `scan-receive`/`scan-label`; HP menyaring hanya status yang bisa diterima; status QC tampil di layar QC, bukan
  "Tugas barang masuk"; uji regresi "qc_rejected/qc_pending tidak bisa diterima ulang".
- **Status:** terverifikasi.

### FLW-IN-02 — Draf PA otomatis mengirim roll **Woven** ke **Gudang Knitting** (peringkat tujuan salah)
- **Alur:** keputusan QC lulus / tutup SPK / "Siapkan draf" → `putaway_draft_service.auto_draft` →
  `choose_destination` → `_rank`.
- **Peran:** sistem (draf), admin/petugas gudang (yang menerbitkan).
- **Klasifikasi:** bug (logika peringkat) + data konfigurasi · **Keparahan: P1**.
- **Bukti (dijalankan):** 5 draf beruntun — PA00012 (RL-46670), PA00013 (RL-46671/72), PA00014, PA00016
  (RL-46685/86), PA00017 (pemicu manual) — semuanya **"Rancamalang · Gudang Knitting"** untuk produk `DMO-GRY-WVN-001`
  (kategori *Woven*, `line_code woven`) dari RCM-TRANSIT (`fa2`, `fd_hold`, `fd2`, `fb2_trips`). Data gedung:
  RCM-WOVEN/KNITTING/PRINTING `storage_rules {"mode":"category","categories":[]}`; RCM-RETUR `grades:[B,BS,C]`.
  `_rank` (`services/putaway_draft_service.py:78-84`) menilai gedung "spesifik" bila **ada daftar terisi ATAU
  `mode != none`** → ketiga gedung sama-sama "spesifik" dengan daftar kosong (= menerima semua, `placement_rules.warehouse_rules`
  `:47-52`), seri dipecah **urut kode** → `RCM-KNITTING` < `RCM-PRINTING` < `RCM-WOVEN`.
- **Aturan dilanggar:** K-GDG-10 (draf "sesuai aturan zona/gedung"), K-GDG-08.
- **Dampak:** admin harus mengubah tujuan setiap draf; bila diterbitkan apa adanya, roll tersimpan di gedung yang
  salah (gate IN Knitting akan "hijau" karena dokumen memang menyebut Knitting).
- **Rekomendasi:** `specific` = ada daftar aturan **terisi** (abaikan `mode` tanpa daftar); validasi profil:
  `mode=category` wajib berisi kategori; tambahkan pencocokan `line_code` produk ↔ peran/lini gedung; layar draf
  menandai "tujuan dipilih karena urutan kode (tidak ada aturan cocok)".
- **Status:** terverifikasi.

### FLW-IN-03 — B1 "diterima seluruhnya saat roll ditahan = peringatan" tidak berlaku untuk roll yang ditahan saat karantina; "terima sebagian" juga tidak bisa menolaknya
- **Alur:** tahan roll karantina (`POST /inventory/rolls/{id}/hold`) → tutup SPK MD Quality
  (`POST /inspections/{id}/finish`).
- **Peran:** petugas gudang (menahan), MD Quality (menutup), manajer (melepas).
- **Klasifikasi:** inkonsistensi dengan keputusan pemilik · **Keparahan: P1** (alur QC macet sampai manajer turun).
- **Bukti (`fd_hold.py.txt`):** RL-46671 ditahan (`quarantine → blocked`, `qc_task_id` tetap). Tutup KSC/INS-00145
  "terima" → **400 "Roll RL-46671 sedang DITAHAN — lepas tahanan dulu sebelum keputusan QC."** (bukan peringatan);
  "terima_sebagian" dengan roll itu sebagai tolak → **400 "Roll yang ditandai tolak tidak ada di karantina tugas ini"**;
  antrean karantina → 409 "ikut SPK". Baru setelah manajer melepas (`/release`) SPK bisa ditutup.
  Kode: `qc_service.process_qc_decision` menolak bila `held_rolls_for_task` (`services/qc_service.py:296-300`);
  `_release_quarantine` hanya mengenal roll `status=quarantine` (`inspection_service.py:1264-1279`), sedangkan
  kebijakan B1 (`:1366-1376`, bawaan `peringatkan`) dicek **sebelumnya** dan dianggap lolos.
- **Aturan dilanggar:** keputusan pemilik audit UI 2 **B1 = warn** (lihat memori "B1 warn"; `qc.accept_all_with_hold_action`).
- **Dampak:** satu roll ditahan petugas mengunci keputusan QC seluruh kedatangan; roll yang ditahan tidak bisa
  ditolak/diretur lewat SPK.
- **Rekomendasi:** saat B1 = peringatkan, putus karantina roll lain dan **biarkan roll yang ditahan tetap ditahan
  (tidak ikut keputusan)**; "terima sebagian" boleh memilih roll ditahan sebagai tolak; satukan penjaga di satu fungsi
  (lihat pola 8). Butuh konfirmasi D3.
- **Status:** terverifikasi.

### FLW-IN-04 — Jalur HP "Terima/Selesai" melahirkan **satu** roll untuk seluruh qty (3 roll fisik → 1 roll 300 yd) dan mencatat "roll kurang 2"
- **Alur:** HP › Masuk › Terima (qty saja) → Selesai (lot & dye saja) — `MobileTaskActions.jsx:38,46`.
- **Peran:** petugas gudang.
- **Klasifikasi:** bug alur / hambatan UX · **Keparahan: P1** (identitas roll = dasar label, tag, PA, opname).
- **Bukti (`fa_legacy.py.txt`):** KSC/PO-00169 300 yd, rencana 3 roll → satu roll **RL-46670 300 yd**;
  `received_rolls 1`; tugas & PO mencatat `receipt_variance {diff_rolls: -2, note: "roll kurang 2"}` padahal yang
  datang 3 roll (yang hilang adalah datanya). Kode: tanpa `payload.rolls` & tanpa roll pindai label →
  "satu roll default" (`inbound_complete_service.py:168-178`, cabang sesudah `elif via_grn` `:164`).
- **Aturan dilanggar:** KN_15 roll-as-SSOT, K-RFID (tag per roll), keluhan pemilik "pindai satu per satu/per
  dokumen" (HP tidak menawarkan pindai label per roll sama sekali). Silang B3b FRM-02.
- **Dampak:** label/tag/opname per roll mustahil untuk barang yang diterima lewat HP; klaim "roll kurang" palsu ke
  supplier.
- **Rekomendasi:** HP "Terima" = pindai label per roll (mesin `scan-label` yang sudah ada) atau isi jumlah roll + panjang
  per roll; tolak "Selesai" tanpa roll bila `expected_rolls > 1`.
- **Status:** terverifikasi.

### FLW-IN-05 — Batal PO meninggalkan roll `receiving` hasil pindai label (yatim selamanya)
- **Alur:** pindai label (`POST /inbound/tasks/{id}/scan-label`) → batal PO (`POST /purchase-orders/{id}/cancel`).
- **Peran:** petugas gudang, admin/pembelian.
- **Klasifikasi:** bug (pembalikan tidak lengkap) · **Keparahan: P1**.
- **Bukti (`fg_cancel.py.txt` G1):** 2 roll RL-46681/82 `receiving` di SRG-01 → batal PO → tugas `cancelled`, **kedua
  roll tetap `receiving` 50 yd**. Batal PO hanya `update_many` status tugas (`routers/purchase_orders_extra.py:268-271`);
  tidak ada `undo_receiving_roll` seperti batal GRN (`goods_receipt_close_service.py:157-168`, terbukti benar di `fg2`).
- **Aturan dilanggar:** pembalikan saat batal (KN_16 §7 transisi); satu roll fisik satu data.
- **Dampak:** roll hantu ber-nomor (label sudah dicetak), muncul di pencarian kode/RFID; tidak di saldo sehingga tak
  terlihat di angka.
- **Rekomendasi:** batal PO memanggil pembatalan roll `receiving` per tugas (seperti batal GRN) atau ditolak bila
  ada roll `receiving`.
- **Status:** terverifikasi.

### FLW-IN-06 — Pindai-terima saat tugas **dieskalasi** melompati eskalasi
- **Alur:** kiriman kurang → Eskalasi (`POST …/escalate`) → pindai-terima lagi.
- **Peran:** petugas gudang (manajer seharusnya memutus).
- **Klasifikasi:** bug (penjaga status) · **Keparahan: P1**.
- **Bukti (`fg_cancel.py.txt` G2):** 60/100 yd → selesai ditolak (benar) → eskalasi → pindai 40 yd → **200, status
  `escalated → qc_check`, `received_qty` 100, `escalation.status` tetap `pending_review`**. Akar sama dengan FLW-IN-01
  (`inbound_receiving.py:66,134-136`).
- **Aturan dilanggar:** KN-C01 (eskalasi = keputusan manajer).
- **Dampak:** antrean eskalasi manajer berisi tugas yang sudah selesai/berjalan; keputusan manajer bisa menimpa
  `expected_qty` sesudahnya.
- **Rekomendasi:** sama dengan FLW-IN-01 (daftar-boleh + CAS).
- **Status:** terverifikasi.

### FLW-IN-07 — Daftar tugas gudang dipagari **PT aktif**, bukan gedung/lokasi; HP tidak menampilkan PT maupun jenis tugas
- **Alur:** `GET /wms/tasks`, `/inbound/tasks`, `/putaway-orders`, `/inbound/qc/queue`; HP `MobileWarehouseApp.jsx:49-110`.
- **Peran:** petugas Soreang/Rancamalang/Jakarta, admin gudang, manajer.
- **Klasifikasi:** butuh keputusan + hambatan UX · **Keparahan: P1** (keluhan pemilik "tercampur semua PT/gudang").
- **Bukti (`fa_legacy`, `fl_lists`, `fc2`):**
  - Petugas Rancamalang (PT rumah Cipta Sandang): konteks bawaan **tidak melihat** tugas PO KSC di RCM-TRANSIT
    (n=5, PT CST saja); konteks "Semua" → 15 tugas CST + KSC bercampur; kartu HP hanya menampilkan produk · gudang ·
    qty · nomor PO/SO (tanpa PT).
  - Petugas Soreang hanya bertugas `ent_kanda` dan SRG-01 `dedicated` Kanda → PO KSC ke Soreang ditolak saat dibuat
    ("Lokasi Soreang belum punya gudang penerimaan…") — bertentangan dengan K-GDG-07 "semua gedung dipakai bersama".
  - Admin gudang/manajer konteks bawaan melihat 248 tugas (Jakarta 171, 67 di gudang uji tanpa lokasi) — tanpa
    saringan gedung di daftar HP.
  - Jenis tugas: inbound PO, inbound hasil makloon (karantina), status QC (`qc_pending/qc_rejected`) dan "terima"
    tampil dalam satu daftar "Tugas barang masuk" dengan aksi yang sama (lihat FLW-IN-01).
- **Aturan dilanggar:** K-GDG-07; keluhan pemilik (tugas tercampur, jenis tidak dibedakan); B4 (satu antrean per
  gedung, tipe tugas eksplisit).
- **Dampak:** tugas PT lain di gedung yang sama terlewat, atau semua PT tercampur tanpa penanda.
- **Rekomendasi (D1):** daftar tugas fisik = **per gedung dalam lokasi tugas, lintas PT**, dengan kolom/lencana PT &
  jenis tugas (Terima PO · Terima makloon · Putaway · Transfer masuk · Retur · Opname); aksi tetap dicek terhadap PT
  dokumen. Data: ubah SRG-01/WH-JKT ke `shared` dan penugasan PT petugas sesuai K-GDG-07.
- **Status:** terverifikasi.

### FLW-IN-08 — Gedung tunggal: roll lahir `stored` dengan **bin dari isian bebas** (bin tidak ada) — langkah "simpan ke bin" terlewati
- **Alur:** `scan-receive` dengan `bin_id` → `complete` di SRG-01 (peran `storage`).
- **Peran:** petugas gudang.
- **Klasifikasi:** bug · **Keparahan: P1** (lokasi stok fiktif). Silang **B3b INP-01** (isian bebas) — di sini
  dampaknya pada alur.
- **Bukti (`fc_single.py.txt`, `fj0.py.txt`):** 3 roll RL-46673..75 `bin_id = "TIDAK-ADA-BIN"`, `journey.stage =
  stored` (tanpa PA, tanpa `place_roll`) → SRG-01 kini punya 3 roll dengan bin tak dikenal struktur. Kode: `bin_id =
  _ex.bin_id or task.bin_id` (`inbound_complete_service.py:364`), `rfid_tag_id = task.roll_id` (isian "Roll ID",
  `:408`).
- **Aturan dilanggar:** evaluator tunggal penempatan (`place_roll`: struktur bin, aturan zona, kapasitas, pembekuan).
- **Dampak:** opname per roll tidak menemukan roll ini (bin di luar struktur), gate/handheld menautkan "tag" yang
  sebenarnya teks bebas.
- **Rekomendasi:** `complete_task` tidak menulis bin; penempatan selalu lewat `place_roll` sesudah tiba; `roll_id`
  isian tidak pernah jadi `rfid_tag_id`.
- **Status:** terverifikasi.

### FLW-IN-09 — Retur penjualan: barang yang sudah dipindai diterima tidak ada di stok sampai "settle"; sesudah lepas karantina roll grade A tertinggal di Gedung Retur (aturan B/BS/C), `received_transit` ditulis keras, tanpa draf PA; SPK retur menggantung
- **Alur:** `POST /sales-returns/{id}/journey/scan` (received) → inspect start/complete → `settle` → `quarantine/release`.
- **Peran:** petugas Rancamalang, admin gudang, manajer.
- **Klasifikasi:** inkonsistensi + fitur belum ada · **Keparahan: P1**.
- **Bukti (`fi_return.py.txt`):** pindai di RCM-RETUR → selisih DB hanya `audit_logs +2`; roll RL-35759 tetap
  `delivered` di **wh_jakarta**. Settle → roll anak **RL-35759-1 2 yd** `quarantine` di RCM-RETUR, lot baru, tanpa
  tag, `journey.stage received_transit` (`return_service.py:1122`). Lepas karantina grade **A** → `available` di
  Gedung Retur (aturan gudang `grades [B,BS,C]` tidak dicek — tidak ada `warehouse_violations` di layanan retur),
  **tanpa draf PA**. SPK `KSC/INS-00129` (`return_customer`) tetap **`draft`** sesudah retur `credit_settled`.
- **Aturan dilanggar:** K-GDG-04 (Gedung Retur = tempat inspeksi), K-GDG-10 (draf otomatis sesudah lepas), aturan
  grade gedung.
- **Dampak:** stok fisik di gedung tak terlihat berhari-hari (opname akan menyebutnya surplus); grade A menumpuk di
  gedung grade B; dua jalur inspeksi retur (form retur vs SPK) tidak sinkron.
- **Rekomendasi (D5, D6):** pindai "diterima" membuat roll `quarantine`/`retur_diterima` di gedung scan (bukan menunggu
  settle) atau tampilkan sebagai "barang retur di gudang"; lepas karantina memanggil `auto_draft_after_release` dengan
  aturan grade; tutup SPK retur saat retur diinspeksi lewat form.
- **Status:** terverifikasi.

### FLW-IN-10 — Transfer dengan **0 roll diterima** (semua dikembalikan ke asal) berstatus `completed` "actual_receipt"
- **Alur:** transfer → kirim → pengecualian `missing` → `return_to_source`.
- **Peran:** petugas Jakarta, admin gudang.
- **Klasifikasi:** inkonsistensi status · **Keparahan: P2**.
- **Bukti (`fh2.py.txt`):** KSC/TRF-00019 (1 roll) → kembali ke asal → **`completed`, `completion_basis:
  actual_receipt`**, ringkasan `counts {returned: 1}`. Kode `_refresh_status` (`transfer_receipt_service.py:241-245`)
  = "tidak ada roll transit ⇒ completed". PA sudah memakai `returned` untuk kasus yang sama (PREP-C).
- **Dampak:** laporan transfer selesai menyesatkan; sesi gate IN dinilai "selesai".
- **Rekomendasi (D10):** status `returned` bila 0 diterima (selaras PA).
- **Status:** terverifikasi.

### FLW-IN-11 — QC tolak + retur ke supplier: PO tetap `completed` (diterima penuh), tidak ada tugas sisa/pengganti
- **Alur:** SPK `tolak` + `reject_disposition=return` → nota retur PRET-00071 `pending_approval`.
- **Peran:** MD Quality, pembelian.
- **Klasifikasi:** butuh keputusan · **Keparahan: P2**.
- **Bukti (`fg_cancel.py.txt` G3):** roll RL-46683 → `returned_supplier`; PO KANDA/PO-00006 `completed`,
  `received_qty 50` (tidak dikurangi); tugas `qc_rejected`; jurnal GR 1.050.000 tetap; nota retur `stock_adjusted:true`.
  Inilah status yang kemudian membuka FLW-IN-01.
- **Dampak:** pembelian tidak punya tugas "menunggu barang pengganti"; papan PO menyatakan lengkap.
- **Rekomendasi (D2):** tolak + retur → `received_qty` dikurangi saat nota retur disetujui dan tugas sisa dibuat bila
  retur bertipe "ganti barang"; PO `partial` sampai diputus.
- **Status:** terverifikasi.

### FLW-IN-12 — SPK QC 4-point bisa ditutup sebelum roll dipindah ke gedung inspeksi; draf PA inspeksi menggantung; "terima sebagian" padahal semua baris tolak
- **Alur:** SPK 4-point dibuat saat karantina → draf PA `purpose=inspection` ke RCM-RETUR → QC menutup SPK.
- **Peran:** QC, admin gudang.
- **Klasifikasi:** inkonsistensi · **Keparahan: P2**.
- **Bukti (`fd2.py.txt`):** PA00015 (RL-46672 → Gudang Retur, `inspection`) `draft`; SPK KSC/INS-00146 ditutup
  "terima_sebagian" dengan satu-satunya baris `tolak` → `done`, roll `blocked` grade B; **PA00015 tetap `draft`**
  dengan roll yang kini ditahan (akan gagal terbit, dan memblok "satu roll satu antrean").
- **Aturan dilanggar:** K-GDG-04 (inspeksi = di gedung inspeksi; urutan pindah → periksa).
- **Rekomendasi:** tutup SPK 4-point membatalkan/mengalihkan draf PA inspeksi rollnya; keputusan "terima sebagian"
  ditolak bila tidak ada baris lulus.
- **Status:** terverifikasi.

### FLW-IN-13 — Satuan SJ berbeda dari PO (meter vs yard) ditolak walau konversi baku ada
- **Alur:** GRN › baris SJ `182,88 meter` untuk PO yard → `start-count`.
- **Peran:** admin gudang (peninjau).
- **Klasifikasi:** butuh keputusan (kebijakan) · **Keparahan: P2**.
- **Bukti (`fb_grn` putaran 2):** `checks.uom = uom_unknown`: "Satuan 'meter' belum sah … Barang supplier 'SUP-UJI-1'
  terdaftar dengan satuan '-'"; aturan global `yard→meter 0,9144` aktif. Kebijakan
  `require_supplier_item_for_supplier_uom` (bawaan true, `receiving_uom_service.py:232-238`) mewajibkan satuan
  terdaftar di barang supplier, bahkan untuk konversi panjang baku.
- **Rekomendasi (D4):** izinkan konversi baku (panjang/berat) tanpa barang supplier, tetap catat jejak; barang supplier
  tanpa satuan → peringatan master data.
- **Status:** terverifikasi.

### FLW-IN-14 — Satu SJ untuk dua PT harus dipecah menjadi dua GRN
- **Alur:** `POST /goods-receipts` (`goods_receipt_service.create_grn:151-160`).
- **Klasifikasi:** hambatan UX / butuh keputusan · **Keparahan: P2** · **Status:** kandidat (kode; tidak dijalankan).
- **Bukti:** GRN wajib satu PT aktif (`view_all` ditolak), PO dari PT lain tidak masuk `open_pos(ent, …)`; kunci SJ
  `active_key = PT|mitra|SJ|tahun` → SJ yang sama boleh dicatat di dua PT (dua foto, dua hitung buta).
- **Rekomendasi (D9):** GRN lintas PT dalam satu lokasi (baris per PO, PT per baris) — kepemilikan roll tetap dari PO.

### FLW-IN-15 — PA bisa tiba tanpa "Kirim" (`dispatched_at` kosong) dan memperoleh BTG
- **Bukti (`fb2_trips.py.txt`):** PA00016 `open` → trip 1 → `partially_received`, `dispatched_at None`; ditutup →
  `completed` + BTG00006. `ARRIVAL_STATUSES` memuat `open` (`putaway_order_service.py:27`).
- **Klasifikasi:** inkonsistensi (maksud "terbit → kirim → tiba") · **Keparahan: P2** · **Status:** terverifikasi.
- **Rekomendasi (D7):** tetapkan apakah "Kirim" wajib; bila opsional, catat `dispatched_at` implisit saat trip pertama.

### FLW-IN-16 — Mengulang trip terakhir (`client_trip_id` sama) sesudah PA selesai → 400, bukan respons duplikat
- **Bukti (`fa3.py.txt`):** trip `b2a-trip-1` menutup PA00012 → kirim ulang trip yang sama → **400 "PA berstatus
  completed — tidak menerima trip tiba."** Cek status (`putaway_arrival_service.py:194`) mendahului cek duplikat
  (`:201-204`). Antrean offline HP (`offlineQueue.js`) akan menandai aksi gagal padahal sudah tercatat.
- **Klasifikasi:** bug (idempotensi) · **Keparahan: P2** · **Status:** terverifikasi.
- **Rekomendasi:** cek trip duplikat sebelum cek status.

### FLW-IN-17 — "Verifikasi label" cukup mengirim nomor roll; tidak terikat bukti cetak label
- **Bukti (`fa3.py.txt`):** `POST /putaway-orders/verify-labels {codes:["RL-46670"]}` → `label_verified` tanpa satu
  pun `roll_label_prints`/`rfid_print_jobs` untuk roll itu (`putaway_order_service.verify_labels:571-593`).
- **Klasifikasi:** inkonsistensi (maksud "verifikasi cetak") · **Keparahan: P2** · **Status:** terverifikasi.
- **Rekomendasi:** verifikasi label hanya untuk roll yang punya catatan cetak (atau tandai "tanpa bukti cetak").

### FLW-IN-18 — Hasil makloon tanpa QC & hasil perbaikan tidak membuat draf PA; terima perbaikan tidak atomik & melewati QC
- **Bukti (kode, peta subagen + PREP-C §6 butir 2):** jalur makloon tanpa QC tidak memanggil `auto_draft_after_release`
  (bandingkan GRN tanpa QC `inbound_complete_service.py:597-598`); `repair_order_service.receive` menulis roll &
  jurnal (`:283-322`) sebelum CAS dokumen (`:324-328`), jurnal tanpa kunci idempoten, roll dipaksa `available` apa pun
  status sebelumnya.
- **Klasifikasi:** fitur belum ada / bug · **Keparahan: P2** · **Status:** kandidat.

### FLW-IN-19 — Roll tiba dari transfer: journey tidak dihitung ulang, bin kosong, tanpa draf PA
- **Bukti (`fh_transfer.py.txt`):** RL-38018 tiba di WH-JKT → `available`, `bin_id None`, `journey None`, tidak ada PA;
  `_land` (`transfer_receipt_service.py:204-234`) tidak menulis `journey`.
- **Klasifikasi:** fitur belum ada · **Keparahan: P2** · **Status:** terverifikasi.
- **Rekomendasi:** tiba transfer = tahap awal sesuai peran gudang tujuan (`stage_for_roles`) + draf PA bila tujuan
  gedung transit.

### FLW-IN-20 — Data profil gedung belum sesuai keputusan (K-GDG-07, PREP-C)
- **Bukti:** SRG-01 & WH-JKT `sharing_mode: dedicated`; RCM-RETUR tanpa peran `inspection`; tiga gedung simpan
  Rancamalang `mode category` tanpa kategori; `gate_config` masih format lama `{physical_gate}` (`fc2`, kueri DB §0).
- **Klasifikasi:** data/konfigurasi (dokumen/data basi) · **Keparahan: P3** · **Status:** terverifikasi.
- **Rekomendasi:** jalankan skrip nilai awal PREP-C setelah ditinjau + tambah langkah `sharing_mode` & kategori.

### FLW-IN-21 — Pesan galat PO ke lokasi menyesatkan; status `put_away` tugas masuk tidak pernah ditulis
- **Bukti:** PO KSC ke Soreang: "belum punya gudang penerimaan (peran Transit / Penerimaan Pusat)" padahal penyebabnya
  gudang `dedicated` (Kanda memakai SRG-01 yang juga tanpa peran transit). `put_away` dibaca 5 tempat
  (`ACTIVE_TASK`, `INBOUND_LIVE`, …) tetapi tidak pernah ditulis.
- **Klasifikasi:** hambatan UX / inkonsistensi · **Keparahan: P3** · **Status:** terverifikasi.

---

## 2. Temuan mesin status & penjaga (STM-IN)

### STM-IN-01 — Pembekuan pendaftaran awal ditembus penerimaan PO jalur lama → lihat OPN-01 (akar: kait pembekuan tidak di `complete_task`)
Dicatat di OPN-01 (dampak stok ganda). Daftar jalur tulis bin/status tanpa kait pembekuan (kode, peta subagen):
`complete_task` (`inbound_complete_service.py:364`), opname biasa (`routers/cycle_count.py` seluruhnya),
`putaway_order_service.resolve_exception → _land_items` (`:540-568`), restock retur (`return_identity_service.py:124-129`),
`transfer_receipt_service.resolve(return_to_source)` (`:377-380`), `cutting_service.receive`, `repair_order_service`.
**Keparahan: P0** (karena terbukti menghasilkan stok ganda) · **Status:** terverifikasi untuk terima PO & opname biasa,
kandidat untuk sisanya.

### STM-IN-02 — Cakupan lokasi (IMP-20) tidak ditegakkan pada **aksi tulis** alur masuk
- **Alur/endpoint:** PA `publish`, `dispatch`, `arrival-trips`, `close`, `resolve-exception`, `cancel-draft`,
  `confirm-arrival` (`routers/putaway_orders.py:96-235` — hanya cek PT pemilik); `POST /transfers/{id}/receive`;
  `POST /cycle-count/sessions/{id}/roll-scans` dan seluruh opname/pendaftaran.
- **Peran:** petugas gudang ber-lokasi.
- **Klasifikasi:** bug (kebocoran lokasi) · **Keparahan: P0**.
- **Bukti (dijalankan):**
  - Petugas **Jakarta** (lokasi Jakarta): `GET /putaway-orders/{PA00012}` → **403 "PA di luar lokasi tugas Anda"**,
    tetapi `publish` → **200 open**, `dispatch` → **200 in_transit**, `arrival-trips` → **200 completed** (PA
    Rancamalang transit → Woven) (`fa3.py.txt`).
  - Petugas **Rancamalang** menerima transfer di **WH-JKT** → 200, roll mendarat di Jakarta (`fh_transfer.py.txt`).
  - Petugas Rancamalang memindai di sesi opname **Jakarta** → 200 (`fj_opname.py.txt`).
  - Daftar tanpa pagar lokasi (`fl_lists.py.txt`): `/transfers` (Soreang melihat 14 transfer Jakarta), `/cycle-count/sessions`
    & `/registration/sessions` (Rancamalang "Semua" melihat sesi Soreang & Jakarta), `/inspections` (118 SPK lintas lokasi).
- **Aturan dilanggar:** IMP-20/P01 (`services/location_scope.py`), P9.5 (PA hanya di lokasi tugas), invarian guardrail
  kebocoran lokasi.
- **Dampak:** stok berpindah/diterima oleh orang yang tidak di gedung itu; bukti tiba palsu; opname gedung lain.
- **Rekomendasi:** satu penjaga `location_scope.assert_warehouse` di lapisan layanan untuk setiap aksi dokumen gudang
  (PA: gudang asal untuk terbit/kirim, tujuan untuk tiba/tutup; transfer: tujuan; opname: gudang sesi); `cycle_count_sessions`,
  `inspections` (gudang roll), `warehouse_transfers` (sudah terdaftar tetapi tidak dipakai) di `WAREHOUSE_FIELDS`;
  guardrail statik "endpoint tulis gudang tanpa cek lokasi".
- **Status:** terverifikasi.

### STM-IN-03 — Sesi pendaftaran awal yang **ditolak** bisa dibuka lewat "reopen" opname biasa lalu menjadi opname per roll
- **Bukti (`fm_misc.py.txt`):** KANDA/REG-00002 `rejected` → `POST /cycle-count/sessions/{id}/reopen` → **200, status
  `open`, mode `registration`** → `roll-scope` → mode **`roll`**. `reopen_session` tidak menyaring `mode` dan menerima
  `rejected` (`routers/cycle_count.py:221-244`), plus `$unset saga_lock`.
- **Klasifikasi:** bug (mesin status bercampur) · **Keparahan: P1** · **Status:** terverifikasi.
- **Rekomendasi:** endpoint opname biasa menolak `mode=registration`; penolakan pendaftaran final (sesuai PREP-B §5.8).

### STM-IN-04 — Status `hold` dari terima transfer (pelanggaran aturan + override) tanpa jalan keluar & berbeda dari `blocked`
- **Bukti (kode):** `transfer_receipt_service.py:210,297-305` menulis `status: "hold"`; pelepasan tahanan
  (`roll_hold_service.release_roll`) hanya mengenal `blocked + hold{held}`; `hold` di tempat lain berarti ember
  "soft-hold pesanan" (`roll_service.py:209`).
- **Klasifikasi:** inkonsistensi · **Keparahan: P2** · **Status:** kandidat.

### STM-IN-05 — `resolve-exception` PA: klaim tanpa prasyarat status, tanpa cek pembekuan & lokasi, tanpa menutup sesi gate
- **Bukti (kode):** `putaway_order_service.resolve_exception:540-568` (`_saga.claim` tanpa `precondition`, dokumen dibaca
  sebelum klaim); tidak memanggil `registration_freeze` maupun `gate_session_hook`.
- **Klasifikasi:** bug kandidat · **Keparahan: P2** · **Status:** kandidat.

### STM-IN-06 — `scan-receive` read-then-write: dua pindai bersamaan saling menimpa `received_qty`
- **Bukti (kode):** `received_qty` baru dihitung dari dokumen yang dibaca (`receiving_uom_service.preflight_scan:468`)
  lalu `$set` dengan filter `{id}` saja (`inbound_receiving.py:142-149`).
- **Klasifikasi:** bug kandidat (konkurensi tidak diuji) · **Keparahan: P3** (jalur lama, satu petugas per tugas) ·
  **Status:** kandidat. Rekomendasi: `$inc` + CAS status.

### STM-IN-07 — Jejak status per dokumen tidak seragam
- **Bukti:** `status_history` (SSOT `services/status_history.py`) tidak dipakai satu pun dokumen alur masuk; jejak
  tersebar di `audit_logs` (tugas, GRN, PA), `history[]` (SPK), `timeline` (PO), `arrival_trips` (PA),
  `receipt_events` (transfer), `journey_events` (retur). Draf PA otomatis lahir tanpa audit (hanya `auto.trigger`).
- **Klasifikasi:** inkonsistensi · **Keparahan: P3** · **Status:** terverifikasi (kode + data).

---

## 3. Temuan opname & pendaftaran awal (OPN)

### OPN-01 — Pembekuan ditembus terima PO jalur lama → roll lahir di rak beku → pendaftaran mencatatnya lagi → **stok ganda + jurnal temuan**
- **Alur:** sesi KANDA/REG-00001 (SRG-01 rak W01, beku per rak) `running` → PO Kanda diterima jalur lama dengan
  `bin_id` rak beku → tim lapangan mendaftarkan roll fisik itu (nomor lama RL-46677) → ACC.
- **Peran:** petugas Soreang (lapangan & penerimaan), admin gudang (penyetuju).
- **Klasifikasi:** bug · **Keparahan: P0** (stok & jurnal salah).
- **Bukti (`fk_reg.py.txt`, `fk2.py.txt`):**
  - `place_roll` ke bin beku → **409 REGISTRATION_FREEZE** (benar), tetapi `scan-receive(bin_id=bin_sim_srg_01_w01_01)`
    + `complete` → **200, RL-46677 40 yd lahir di bin beku**.
  - Baris pendaftaran `old_roll_no: RL-46677` → tidak dicocokkan (`match_key` kosong) karena pencocokan hanya roll yang
    lahir **sebelum** sesi mulai (`initial_registration_plan.py:62-64`).
  - ACC → roll baru **RL-46680 40 yd** (`old_roll_no RL-46677`, biaya 12.373,11/yd, jurnal kelompok) **dan RL-46677
    tetap ada** (`quarantine`, 40 yd, bin beku) → 80 yd tercatat untuk 40 yd fisik.
  - Docstring `registration_freeze.py:12-14` menyatakan "roll GRN lahir tanpa bin" — tidak berlaku untuk jalur lama.
- **Aturan dilanggar:** K-OPN-03 (pembekuan), K-OPN-01 (data dari fisik menggantikan data lama), invarian saldo.
- **Dampak:** stok & persediaan ganda yang lolos ke "area terverifikasi pendaftaran".
- **Rekomendasi:** kait `assert_movable` di `complete_task` (atau larang bin saat terima, lihat FLW-IN-08); baris
  pendaftaran yang menyebut nomor roll yang **ada di cakupan** (lahir kapan pun) → pengecualian "roll lahir saat beku",
  bukan roll baru.
- **Status:** terverifikasi.

### OPN-02 — ±20 % roll fisik tanpa bin tidak pernah masuk potret opname per roll
- **Alur:** `POST /cycle-count/sessions/{id}/roll-scope` → `stock_count_roll_service.make_snapshot:79-95`
  (`bin_id ∈ bin cakupan`).
- **Peran:** petugas/admin gudang.
- **Klasifikasi:** bug desain (cakupan) · **Keparahan: P1**.
- **Bukti (`fj0.py.txt`):** roll fisik tanpa bin: WH-JKT **4.701/23.185**, RCM-WOVEN 2.052/9.939, RCM-KNITTING
  2.108/10.374, SRG-01 517/2.893 (+3 bin tak dikenal), RCM-RETUR 14/71. Semua alur tiba (PA, transfer, retur) mendarat
  `bin_id None` (FLW-IN-19, #47 tabel transisi). Cakupan "seluruh gedung" pun memakai daftar bin struktur → roll tanpa
  bin tidak diharapkan, sehingga **tidak bisa terdeteksi hilang**. Bila dipindai, roll itu dianggap "asing" lalu
  dipindah ke bin (benar, `fj2`).
- **Aturan dilanggar:** opname per roll = rekonsiliasi seluruh roll fisik gedung (KN_16 §4, K-OPN).
- **Rekomendasi (D8):** cakupan seluruh gedung memasukkan roll tanpa bin sebagai "harus ditemukan"; dasbor "roll tanpa
  bin" per gedung; opsi wajib bin sebelum PA ditutup.
- **Status:** terverifikasi.

### OPN-03 — Nilai barang temuan mengabaikan `harga_pokok` master (field biaya yang dipakai modul lain)
- **Alur:** ACC opname per roll / pendaftaran awal → `stock_count_service.surplus_unit_cost:55-69`.
- **Klasifikasi:** bug (fallback beda field) · **Keparahan: P1** (persediaan & jurnal kurang saji).
- **Bukti:** fallback master membaca `standard_cost/cost_price/purchase_price/base_price_cost`; data: 279 produk punya
  `harga_pokok` > 0, **0** produk `standard_cost`, 9 `cost_price`. `costing_service.wac_for_product` (`services/costing_service.py:91-98`) dan
  penerimaan (`inbound_complete_service.py:284`) memakai `harga_pokok`. Di `fj2`: roll temuan RL-46676 `unit_cost None`,
  **tanpa jurnal**, ACC menuntut "alasan biaya nol". (Produk uji kebetulan tanpa `harga_pokok` — jalur kode terbukti,
  nilai untuk produk ber-`harga_pokok` disimpulkan dari kode + data.)
- **Aturan dilanggar:** K-OPN-02 (rata-rata gudang → rata-rata pemilik → **harga master produk**).
- **Rekomendasi:** satu resolver biaya (`costing_service`) untuk temuan opname/pendaftaran.
- **Status:** terverifikasi (kode + data).

### OPN-04 — Hapus roll hilang di opname per roll tidak mencabut tag RFID
- **Bukti (`fm_misc.py.txt` M2):** RL-05000 (tag `E2121E0C…`) dihapus lewat opname → roll `consumed` 0 yd, **tag tetap
  `active`** menunjuk roll mati. Pendaftaran awal mencabut tag (`initial_registration_approve.py:165-166`), opname tidak
  (`stock_count_roll_service.write_off_missing:346-377`).
- **Klasifikasi:** inkonsistensi · **Keparahan: P2** (gate/handheld masih mengenali tag) · **Status:** terverifikasi.

### OPN-05 — Opname biasa (per item) tidak tunduk pembekuan pendaftaran
- **Bukti (`fk_reg.py.txt`):** saat rak W01 beku, `POST /cycle-count/sessions/{id}/items` dengan `bin_id` beku → 200.
  `routers/cycle_count.py` tidak memanggil `registration_freeze` di mana pun (persetujuan bisa menulis surplus/kurang
  di bin beku).
- **Klasifikasi:** bug · **Keparahan: P2** · **Status:** terverifikasi (penambahan item); ACC dari kode.

### OPN-06 — Roll hilang tanpa hitung ulang tetap tersedia sesudah ACC "approved_with_exceptions"; tidak ada tindak lanjut
- **Bukti (`fj2.py.txt`):** 4 roll (RL-19006/07/08, RL-00015) tidak dipindai & tidak dihitung ulang → tetap
  `available`/`blocked`; sesi terminal; tidak ada endpoint lanjutan (`reopen` hanya `submitted/rejected`).
- **Klasifikasi:** fitur belum ada · **Keparahan: P2** · **Status:** terverifikasi.
- **Rekomendasi:** ACC per roll ditolak bila ada roll hilang tanpa keputusan, atau sesi turunan "hitung ulang".

### OPN-07 — Pendaftaran: baris "produk belum dikenali" kehilangan qty; sesi bisa diajukan dengan rak belum "selesai"
- **Bukti (`fk_reg`, kueri baris):** baris `unrecognized` dikirim `qty 20` → tersimpan `qty null` (penyetuju harus
  mengisi ulang qty); `submit` 200 dengan `racks_done 0/1`.
- **Klasifikasi:** bug kecil / hambatan · **Keparahan: P2** · **Status:** terverifikasi.

---

## 4. Peta alur nyata vs maksud

| Langkah | Maksud (sumber) | Nyata (HEAD) | Selisih |
|---|---|---|---|
| Terima PO di HP | per roll, label & tag per roll (KN_15, K-RFID) | qty saja → 1 roll | **bug kode** (FLW-IN-04) |
| Tugas tertutup QC | tidak bisa diterima lagi | bisa (daftar-larang) | **bug kode** (FLW-IN-01) |
| Draf PA ke gedung sesuai aturan | K-GDG-08/10 | peringkat urut kode | **bug kode + data** (FLW-IN-02) |
| B1 roll ditahan | peringatan (keputusan 26 Okt) | blokir | **bug kode** (FLW-IN-03) |
| Gedung tunggal langsung tersimpan | P9-K1/PREP-C | `stored` + bin teks bebas | **bug kode** (FLW-IN-08) |
| Gedung inspeksi RCM-RETUR | K-GDG-04 | data belum diberi peran; bila diberi, routing jalan | **data basi** (FLW-IN-20) |
| QC 4-point di gedung inspeksi | pindah → periksa | bisa ditutup sebelum pindah | **belum diputuskan/bug** (FLW-IN-12) |
| Terbit → kirim → tiba bertahap | K-GDG-10, K-RFID-10 | tiba tanpa kirim sah | **belum diputuskan** (FLW-IN-15) |
| Gate IN memvalidasi PA/transfer | K-GDG-02 | ada (D2), tetapi aksi handheld/desktop tanpa cek lokasi | **bug kode** (STM-IN-02) |
| Transfer masuk | terima per roll, parsial | jalan; 0 diterima = completed; tanpa journey/PA | **bug kode** (FLW-IN-10/19) |
| Retur terima barang → Gedung Retur → inspeksi → grade | K-GDG-04 | stok baru ada saat settle; grade A tinggal di Gedung Retur | **fitur belum ada / belum diputuskan** (FLW-IN-09) |
| Semua gedung dipakai bersama | K-GDG-07 | SRG-01/WH-JKT dedicated; petugas satu PT | **data basi + belum diputuskan** (FLW-IN-07/20) |
| Opname per roll | seluruh roll fisik | hanya roll ber-bin | **bug desain** (OPN-02) |
| Pendaftaran awal: beku | K-OPN-03 | jalur lama & opname biasa menembus | **bug kode** (OPN-01/05) |
| Nilai temuan | K-OPN-02 rata-rata → master | master = field yang tidak dipakai | **bug kode** (OPN-03) |
| Dokumen KN_16 §3/§7 | `on_order → in_transit_inbound → receiving → available` | status `in_transit_inbound`/`on_order` tidak dipakai di jalur PO; tahap nyata = tugas `waiting_goods`/`receiving`/`qc_pending` + roll `receiving/quarantine` | **dokumen basi** (KN_16 v1.2 belum memuat GRN, SPK, PA, gate) |

---

## 5. Pola kesalahan (urut dampak)
1. **Daftar-larang status** (`not in [completed, cancelled]`) di tulis tugas (FLW-IN-01, -06) → status baru lolos.
   Perbaikan sistemik: tiap transisi = daftar-boleh di filter CAS; guardrail statik yang mencari `status in [...]`
   negatif pada endpoint tulis.
2. **Lokasi hanya di baca/buat** — 12 endpoint aksi tanpa `assert_warehouse` (STM-IN-02).
3. **Kait pembekuan tersebar per titik** — tiap jalur baru wajib mengingat kait; jalur lama lupa (STM-IN-01, OPN-01/05).
   Usulan: satu "pintu gerak roll" (bin/gudang/status) yang memeriksa pembekuan + lokasi + evaluator bin.
4. **Teks bebas → rujukan** (bin, roll_id → tag) tanpa evaluator (FLW-IN-08; B3b INP-01/02/03).
5. **Konfigurasi "kosong tetapi bermode"** dianggap aturan (FLW-IN-02, OPN-03 fallback field lain).
6. **Status akhir tidak mencerminkan isi** (transfer 0 terima, PO lengkap padahal ditolak, SPK "terima sebagian" 0 lulus).
7. **Identitas roll hilang di jalur HP** (qty-only) — merusak semua langkah per roll sesudahnya.
8. **Banyak konsep tahan & jalur QC paralel** (4 bentuk tahan; antrean vs SPK; inspeksi retur form vs SPK).
9. **Visibilitas berbasis PT, bukan gedung** untuk pekerjaan fisik (FLW-IN-07).
10. **Efek hilir tidak dibereskan** saat hulu berubah (roll `receiving` yatim, draf inspeksi, SPK retur, tag roll mati).

---

## 6. Butir keputusan pemilik + rekomendasi
| ID | Pertanyaan | Rekomendasi auditor |
|---|---|---|
| D1 | Daftar tugas fisik per **gedung lintas PT** (dengan label PT & jenis tugas) atau tetap per PT aktif? | Per gedung lintas PT (K-GDG-07); aksi tetap dicek PT dokumen; ubah SRG-01/WH-JKT ke `shared` |
| D2 | QC tolak + retur supplier: PO dibuka lagi (menunggu barang pengganti) atau ditutup? | Bergantung tipe nota retur: "ganti barang" → tugas sisa otomatis; "potong tagihan" → PO `closed_short` |
| D3 | B1 untuk roll yang **ditahan** saat karantina | Peringatan: putuskan roll lain, roll ditahan tetap ditahan & bisa ditolak lewat "terima sebagian" |
| D4 | SJ satuan baku berbeda dari PO (meter vs yard) | Izinkan konversi baku tanpa barang supplier, catat jejak |
| D5 | Barang retur masuk stok saat dipindai di gudang atau saat settle? | Saat dipindai (karantina retur), dinilai saat settle |
| D6 | Roll retur sesudah lepas karantina | Draf PA otomatis sesuai grade (A → gudang simpan, B/BS/C → Gedung Retur) |
| D7 | Langkah "Kirim" PA | Opsional di gedung tanpa gate OUT di transit; trip pertama mengisi `dispatched_at` |
| D8 | Roll tanpa bin di opname per roll | Masuk potret "harus ditemukan"; PA belum dianggap selesai sebelum bin diisi (opsional per gedung) |
| D9 | Satu SJ untuk dua PT | GRN per lokasi lintas PT (baris per PO) |
| D10 | Transfer 0 diterima | Status `returned` (selaras PA) |

Butir lama yang masih terbuka dan disentuh audit ini: gate Gedung Retur RCM (PREP gelombang 1), penanda "minta
inspeksi" (kini = SPK 4-point terbuka — FLW-IN-12 menunjukkan perlu aturan urutan), persetujuan Finance untuk
pendaftaran awal (66/67 roll lama dihapus + 3 jurnal Rp 40 jt hanya dengan `approve_count` admin gudang).

---

## 7. Yang berjalan benar (kontrol positif)
- Batal GRN saat menghitung membereskan roll `receiving` dan melepas tugas (`fg2`); batal PO ditolak saat GRN aktif.
- SJ yang sama di GRN kedua ditolak `DN_DUPLICATE`; trip ulang (belum selesai) idempoten; tutup sisa `return_transit`
  mengembalikan roll ke `label_verified` di transit dan "Siapkan draf" memunculkannya lagi.
- `place_roll` menolak bin beku; ACC pendaftaran idempoten per kelompok, tag `pending_print`, area terverifikasi,
  beku dilepas; opname per roll memindah roll "asing" ke bin tempat ditemukan dan menjurnal yang hilang (5-9500/1-1300).
- Routing gedung inspeksi berjalan bila profil benar (PA00015 `purpose=inspection`).

## 8. Kebersihan & batasan
- Stack `kn-tmp-b2a-*` dihapus sesudah audit; tidak ada perubahan pada stack bersama `kn-uji-*` maupun DB koordinator.
- Tidak menjalankan `scripts/verify_state_machine.py` (sesuai aturan bersama); tidak memakai peramban.
- Konkurensi, gate V2 dengan perangkat, OCR berkunci, makloon/perbaikan: hanya dibaca dari kode (ditandai kandidat).
