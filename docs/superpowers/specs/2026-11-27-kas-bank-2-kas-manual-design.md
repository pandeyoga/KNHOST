# Rancangan — Kas & Bank bagian 2: kas manual tanpa Pembelian/Gaji (C5) dan kas keluar besar butuh orang kedua (C6)

Tanggal: 27 Nov 2026 · Status: **keputusan pemilik C5 dan C6 disetujui 25 Nov** (`docs/keputusan/2026-11-25_DAFTAR_KEPUTUSAN_TERBUKA.md`
§C: C5 "Ya"; C6 "Ya, di atas Rp 1.000.000 (Bapak bisa ganti)"). Keputusan builder di §7 dikerjakan tanpa menunggu
(perintah pemilik "langsung lanjut kerjakan saja semua", 27 Nov "ya percepat") dan dilaporkan.
Dibangun di atas Kas & Bank bagian 1 (cabang `claude/nifty-carson-jjx3c8`, `336410d`).

## 1. Masalah

- **Kas manual berkategori "Pembelian"** dijurnal ke Persediaan (`1-1300`) tanpa barang masuk; **"Gaji"** dijurnal ke beban
  gaji (`6-1000`) di luar penggajian, sehingga gaji bisa terbeban dua kali. Kategori di server adalah teks bebas; pemetaan
  kategori → akun lawan memakai kata kunci (`gl_service.CASH_OUT_KEYWORDS`: `pembelian`/`beli`/`bahan` → 1-1300,
  `gaji`/`payroll` → 6-1000), jadi teks bebas seperti "Beli kain" atau "gaji harian" juga kena.
- **Kas keluar manual tanpa kontrol apa pun**: siapa pun pemegang `cash.create` bisa mengeluarkan uang berapa pun, langsung
  terjurnal. Pemilik menilai risikonya terbesar.

## 2. Tujuan dan bukan tujuan

**Tujuan:**
- C5: kas manual **baru** tidak bisa memakai kategori yang menjurnal ke Persediaan atau beban gaji. Pesan mengarahkan:
  barang lewat PO/tagihan pemasok, gaji lewat Proses Gaji, belanja kecil kebutuhan kantor pakai Operasional.
- C6: kas **keluar** manual dengan nominal **di atas** batas PT (bawaan Rp 1.000.000) menjadi **pengajuan** yang baru
  menjadi kas + jurnal sesudah **orang kedua** menyetujuinya. Di bawah/sama dengan batas → langsung seperti sekarang.
- Pengajuan tampil di Pusat Persetujuan dan di layar Transaksi Kas; pengaju diberi tahu hasilnya.

**Bukan tujuan:** kas masuk manual (C6 hanya kas keluar); kas yang lahir dari dokumen (bayar tagihan pemasok, gaji,
panjar/LPJ, Pindah Dana, refund) — punya kontrolnya sendiri; aturan kas kasir/kas kecil/opname (bagian 3); persetujuan
bertingkat (lebih dari dua orang).

**Anti-tujuan:** uang di atas batas terjurnal tanpa orang kedua; pengajuan yang belum disetujui ikut terhitung di saldo kas
atau buku kas rekening; jalur dokumen yang sah (bayar tagihan "pembelian", "Pembayaran Gaji") ikut tertolak; kas lama
berkategori Pembelian/Gaji tidak bisa dibatalkan/diposting ulang.

## 3. Keadaan sekarang (ringkas, recon 27 Nov di `336410d`)

- Pintu kas manual: `POST /api/cash-transactions` (`routers/cash.py create_cash_transaction`, izin `cash.create`) →
  periksa (jenis, arah, nominal, PT, kategori Transfer ditutup — Kas & Bank 1 Tugas 5, `ref_type` manual, rekening,
  preflight posting, anggaran untuk kas keluar) → `cash_ledger.create_cash(ref_type="manual", ref_id=Idempotency-Key atau
  id baru)` → jurnal langsung. Kartu Asisten `cash_manual` (`ai_cards._prep_cash_manual`) memanggil rute yang sama lewat
  SelfApi dan sudah punya kontrol dua orang sendiri (`kontrol.asisten_uang_keluar`).
- Kategori: teks bebas di server; layar `CashManagementView.jsx` menawarkan `CATEGORIES` = operasional, pembelian, gaji,
  modal, lain.
- Kontrol dua orang: `config_catalog_kontrol.py` (aksi → `kontrol.<aksi>.min_orang` + `batas_nominal` per PT),
  `services/dual_control.py` (`butuh_orang_kedua`, `tolak_bila_pelaku_sama`), contoh pola dokumen menunggu: Pindah Dana
  (`fund_transfer_service`: `menunggu_persetujuan` → `setujui` berklaim → `create_cash`), rute 202 pada perubahan rekening
  (`bank_account_change_service`).
- Kas yang lahir dari dokumen memanggil `create_cash` langsung (`ap_payment_service` kategori "pembelian",
  `hr_payroll_pay` "Pembayaran Gaji", `landed_cost`, panjar) — tidak lewat rute manual.

## 4. Pendekatan (C6)

- **A (dipilih): dokumen pengajuan sendiri** — koleksi baru `cash_out_requests`, status `menunggu_persetujuan` →
  `disetujui` (kas terbit lewat `create_cash`) / `ditolak` / `dibatalkan`. Rute manual menjawab **202 + pengajuan** bila
  orang kedua dibutuhkan (pola rekening). Saldo & buku kas tidak tersentuh sampai disetujui. Sama dengan pola Pindah Dana
  yang sudah ditinjau.
- B: status menunggu di dokumen kas `cash_transactions` — ditolak: semua pembaca saldo/daftar menyaring `status != void`,
  jadi pengajuan akan ikut terhitung (anti-tujuan) dan setiap pembaca harus diubah.
- C: usulan jurnal (`journal_proposals`) — ditolak: lapisan salah (dokumen kas + rekening + rekonsiliasi lahir dari kas,
  bukan dari jurnal).

## 5. Rancangan

### 5.1 C5 — kategori ditutup untuk kas manual baru

- Satu pembantu di `cash_ledger` (pola `kategori_transfer_ditutup`): kategori kas manual ditolak bila akun lawan yang
  **akan** dipilih kata kunci jurnal adalah akun persediaan (`1-1300`) atau beban gaji (`6-1000`) — dihitung dari daftar kata
  kunci yang sama (`gl_service`), bukan daftar kata kedua, supaya satu sumber kebenaran. Berlaku untuk kas masuk dan
  keluar manual (rute `create_cash_transaction` dan kartu Asisten), **tidak** untuk `create_cash`.
- Pesan: "Kategori Pembelian dan Gaji tidak lagi dipakai di kas manual: pembelian barang lewat PO/tagihan pemasok, gaji
  lewat Proses Gaji. Belanja kecil kebutuhan kantor pakai kategori Operasional."
- Layar: pilihan Pembelian dan Gaji hilang dari form; label lama tetap untuk baris lama.
- Kas lama berkategori itu tetap bisa dibatalkan dan diposting ulang (kata kunci jurnal tidak diubah).

### 5.2 C6 — kas keluar manual di atas batas = pengajuan

- **Pengaturan:** aksi kontrol baru `kas_keluar_manual` di `config_catalog_kontrol` (kelompok C, bagian Buku besar,
  `punya_nominal`), bawaan `min_orang` "1" dan `batas_nominal` **1.000.000** (per PT, bisa diubah di Pusat Pengaturan);
  aturan "di atas" = nominal > batas (perilaku `dual_control.butuh_orang_kedua`). `min_orang` "2" = semua kas keluar manual
  butuh orang kedua.
- **Ajukan:** `POST /api/cash-transactions` dengan arah keluar dan butuh orang kedua → semua pemeriksaan yang sama dengan kas
  langsung dijalankan (kategori, rekening, periode, preflight, anggaran) → simpan pengajuan `cash_out_requests` (nomor
  `PKK-` per PT, isian kas lengkap, pengaju, `Idempotency-Key` → kunci unik, jejak) → **202** `{request}`; tidak ada kas,
  tidak ada jurnal. Kas masuk dan kas keluar ≤ batas: 200 seperti sekarang.
- **Setujui:** `POST /api/cash-out-requests/{id}/approve` (izin `cash.approve`, `guard_door`, `tolak_bila_pelaku_sama`
  aksi `kas_keluar_manual`; pengaju tidak boleh menyetujui sendiri) → klaim berstatus (pola Pindah Dana `_terbit`) → periksa
  ulang (rekening aktif, periode terbuka, anggaran, kategori) → `create_cash(ref_type="manual", ref_id=<id pengajuan>)`
  dengan tanggal kas = tanggal yang diajukan → status `disetujui`, tautan ke kas, jejak. Gagal terbit → tetap menunggu dengan
  `terbit_error` berkalimat, bisa disetujui lagi (id kas tetap → tidak ganda).
- **Tolak:** `…/reject` (izin `cash.approve`, alasan wajib, bukan pengaju) → `ditolak`. **Batal:** `…/cancel` oleh pengaju
  (atau pemegang `cash.delete`) selama menunggu → `dibatalkan`.
- **Antrean & notifikasi:** jenis persetujuan + baris `QUEUES` "Kas keluar manual menunggu"; pemberitahuan ke pemegang
  `cash.approve` PT itu saat diajukan, ke pengaju saat diputus.
- **Kartu Asisten `cash_manual`:** hasil 202 dibaca sebagai "Diajukan — menunggu persetujuan kas keluar" (bukan gagal).

### 5.3 Layar (Kas & Bank › Transaksi Kas)

- Form Catat Transaksi: kategori tanpa Pembelian/Gaji; bila arah keluar dan nominal > batas PT → catatan "Di atas Rp … —
  akan diajukan untuk disetujui orang kedua" dan tombol "Ajukan"; hasil 202 → toast + baris di bagian "Menunggu
  persetujuan".
- Bagian/daftar "Menunggu persetujuan" (pengajuan PT itu): nomor, tanggal, rekening, kategori, nominal, pengaju; aksi
  Setujui/Tolak (pemegang `cash.approve`, mati untuk pengaju dengan alasan) dan Batal (pengaju). Nomor `PKK-` bisa diklik
  (pratinjau + jejak). Pusat Persetujuan membuka layar ini.

## 6. Aturan bersama

- Wewenang menurut izin (`cash.create` ajukan, `cash.approve` setujui/tolak, `cash.delete` batal oleh selain pengaju);
  nilai bisnis lewat pengaturan (`kontrol.kas_keluar_manual.*`).
- Satu pintu kas (`create_cash`), satu pembantu akun kas (`akun_kas`), tanpa migrasi saat menyala.

## 7. Keputusan builder (periksa)

1. **Dokumen pengajuan sendiri** (`cash_out_requests`, `PKK-`) — pendekatan A.
2. **C5 dihitung dari kata kunci jurnal** (akun lawan 1-1300 / 6-1000), berlaku kas masuk dan keluar manual.
3. **Batas bawaan Rp 1.000.000, "di atas" = lebih dari**; `min_orang` bawaan "1" (hanya di atas batas).
4. **Admin tidak boleh menyetujui kas keluar manualnya sendiri**: `kas_keluar_manual` masuk bawaan
   `kontrol.admin_tetap_dua_orang` (alasan pemilik di C6: jalur kas manual berisiko terbesar). Tetap pengaturan.
5. **Tanggal kas = tanggal yang diajukan**; periode tertutup saat disetujui → ditolak berkalimat, pengaju mengajukan ulang.
6. **Kartu Asisten** tetap dengan kontrolnya sendiri; bila kedua kontrol menyala dan nominal di atas kedua batas, uang baru
   keluar sesudah dua persetujuan (dicatat untuk pemilik).
7. Izin memakai `cash.create`/`cash.approve`/`cash.delete` yang ada; tidak ada izin baru.

## 8. Untuk pemilik (tidak menghalangi pembangunan)

- Batas Rp 1.000.000 berlaku sama untuk semua PT sampai diubah per PT di Pusat Pengaturan.
- Admin pun butuh orang kedua untuk kas keluar manual di atas batas (butir 7.4) — setuju?
