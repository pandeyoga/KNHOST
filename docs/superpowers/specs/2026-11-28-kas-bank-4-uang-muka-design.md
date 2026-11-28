# Rancangan — Kas & Bank bagian 4: batas uang muka karyawan & tenggat LPJ (C7), akun uang muka pemasok terpisah (C8)

Tanggal: 28 Nov 2026 · Keputusan pemilik: `docs/keputusan/2026-11-25_DAFTAR_KEPUTUSAN_TERBUKA.md` §C — **C7 "Ya"** (maksimal 1 PD
terbuka per orang, LPJ wajib dalam 7 hari), **C8 "Ya"** (pisahkan akun uang muka pemasok dari uang muka karyawan; sekarang
satu akun 1-1400). Dasar temuan: `docs/audit/kas-bank-otomasi-2026-11-25/ANALISIS_TUNAI_BANK_OCR_OTOMASI.md` C7 (`:114`), C9
(`:116`), keputusan terbuka 6–7 (`:135-136`); `docs/finance/AUDIT_KEUANGAN_2026-11-13.md` `:256` (tiga wadah "uang dipegang
orang"). Keputusan builder di §7 dikerjakan tanpa menunggu (perintah pemilik "langsung lanjut kerjakan saja semua") dan
dilaporkan. Dibangun di atas cabang Kas & Bank 3 (`2627f52`).

## 1. Masalah

- **C7:** uang muka karyawan (Form PD, `cash_advances`) tidak punya batas terbuka per orang dan tidak punya tenggat LPJ.
  Satu orang bisa memegang beberapa PD sekaligus, dan PD yang sudah cair bisa menggantung di 1-1400 tanpa peringatan.
- **C8:** akun 1-1400 menampung uang muka karyawan (PD), uang muka ke pemasok (lebih bayar tagihan `ap_advance`, selisih
  bayar, kasus "lebih bayar pemasok", potongan kontrabon `supplier_advance`), dan biaya dibayar dimuka. Saldonya tidak bisa
  dicocokkan ke satu daftar.

## 2. Tujuan, bukan tujuan, anti-tujuan

**Tujuan:** (C7) PD baru tidak bisa diajukan selama pemohonnya masih memegang PD terbuka sebanyak batas PT (bawaan 1);
setiap PD yang cair punya tenggat LPJ (bawaan 7 hari) yang terlihat di daftar, di Meja Keuangan bila lewat, dan
diberitahukan ke pemohon. (C8) akun **Uang Muka Pemasok** sendiri; semua jalur uang muka pemasok memakai satu pembantu akun;
tiap PT pindah lewat **pindah saldo uang muka pemasok** (pratinjau → orang kedua setujui) sehingga sesudahnya 1-1400 hanya
uang muka karyawan (+ biaya dibayar dimuka) dan akun baru hanya uang muka pemasok; daftar uang muka terbuka per akun
dibandingkan dengan saldo akunnya.

**Bukan tujuan:** menautkan PD ke master karyawan HR (PD tetap milik pengguna pembuatnya); potong gaji untuk LPJ yang
menggantung (pengisi kasbon K-40 belum dibangun); memisah "biaya dibayar dimuka" dari 1-1400; mengubah alur LPJ, sisa
dikembalikan, atau reimburse; C4.

**Anti-tujuan:** pembaruan VPS yang memindah saldo atau mengubah PD/uang muka lama sendiri; PD lama yang sudah cair
mendadak "lewat tenggat" pada hari pembaruan; uang muka pemasok lama yang dipakai/dikembalikan sesudah PT pindah membebani
akun yang salah (saldo negatif di satu akun, lebih di akun lain); PT yang belum pindah berperilaku berbeda dari sekarang
(kecuali aturan C7 yang memang berlaku untuk semua PT).

## 3. Keadaan sekarang (recon 28 Nov)

- PD: `services/cash_advance_service.py` — status draf → rantai persetujuan (`approval_kinds["cash_advance"]`) → approved →
  `disbursed` → `settled`; ditolak bisa disunting ulang. Pemohon = `created_by` / `created_by_id` (pengguna); tidak ada
  bidang karyawan. Cair: Dr 1-1400 / Cr kas (`gl_service._cash_out_contra`, `ref_type="cash_advance"`). LPJ
  (`cash_advance_settlements`, satu per PD): disetujui → Dr beban / Cr 1-1400 (maks. nilai PD), lebih → Cr 2-1650; PD
  `settled` begitu LPJ terjurnal walau sisa belum dikembalikan (`sisa_dikembalikan.status` open/returning/returned/none);
  kembalikan sisa Dr kas / Cr `kas_bank.uang_muka_karyawan`. Tidak ada batas PD terbuka, tenggat, atau pengingat.
- 1-1400: konstanta `gl_service.ACC_UANG_MUKA`; satu kunci pemetaan `kas_bank.uang_muka_karyawan` (bawaan 1-1400). Jalur
  pemasok memakai konstanta langsung: `ap_payment_service` (lebih bayar → kas `ap_advance`, Dr 1-1400 / Cr kas, menambah
  `suppliers.advance_balance`), `payment_variance_service` (`:1288,1347,1391`), `finance_case_actions` (lebih bayar Dr 1-1400 /
  Cr 2-1100 `:1057-1083`, refund Dr kas / Cr 1-1400 `:1089-1103`), potongan kontrabon `supplier_advance` Dr 2-1100 / Cr 1-1400
  (`gl_service.py:2450-2466`, `contra_bon_service.available_credits`). Sub-ledger pemasok tersebar: `suppliers.advance_balance`
  (per pemasok) dan kas `ap_advance` belum dipakai (per PT, `ap_party_service._credits`).
- Tidak ada pencocokan 1-1400 ke daftar mana pun; daftar periksa tutup buku tidak punya butir uang muka.
- Pola yang dipakai ulang: pindah saldo per PT Kas & Bank 1 (`cash_account_cutover_service`, pratinjau/siapkan/setujui,
  sidik, penanda sekali tulis); pengaturan berregistri (`config_catalog_*`, `config_resolver.value_of`); antrean Meja Keuangan
  jatuh tempo (`cash_count_service.jatuh_tempo` + `work_desk_service`); pengingat berpenjadwal Lapor Bayar (LB-T5); penanda
  aktif sekali tulis (F1, Kas & Bank 3).

## 4. Pendekatan

**C7**
- **Dipilih: aturan di layanan PD** — hitung PD terbuka pemohon saat **ajukan** dan sekali lagi saat **cairkan** (penjaga
  balapan & data lama); tenggat LPJ **dipotret ke PD saat cair**; pembaca tenggat (daftar, meja, pengingat) satu fungsi.
- Ditolak: batas hanya saat cair (pemohon baru tahu sesudah rantai persetujuan berjalan — membuang kerja penyetuju).
- Ditolak: menautkan PD ke karyawan HR dulu (butuh isi data PD lama; "orang" = pengguna pemohon sudah cukup untuk C7).

**C8**
- **Dipilih: akun baru + satu pembantu akun + pindah saldo per PT (pola Kas & Bank 1).** Sebelum PT pindah, semua jalur
  pemasok tetap di 1-1400 (persis sekarang). Pindah = jurnal reklasifikasi Dr akun baru / Cr 1-1400 sebesar sub-ledger uang
  muka pemasok PT itu, disiapkan Finance, disetujui orang kedua (hitung ulang + sidik), lalu penanda PT; sesudahnya semua
  jalur pemasok (buat, pakai, kembalikan) memakai akun baru. Satu saat pindah untuk satu PT → tidak ada uang muka yang
  "dibuat di akun A, dipakai di akun B".
- Ditolak: akun mengikuti asal tiap uang muka (tidak ada satu dokumen sumber — jalur kasus tidak punya dokumen kas; setiap
  pemakai harus tahu akun asal; 1-1400 tidak pernah bersih).
- Ditolak: hanya mengganti Pemetaan Akun (saldo lama tertinggal di 1-1400; potongan/refund uang muka lama sesudah ganti
  pemetaan menghapus akun baru jadi negatif).

## 5. Rancangan

### 5.1 C7 — batas PD terbuka

- **Orang** = pemohon PD (`created_by_id`), **lintas PT** (uang di tangan satu orang). Batas dari pengaturan PT dokumen
  `kas.pd_terbuka_maks` (bawaan **1**; 0 = tanpa batas).
- **PD terbuka** = PD milik orang itu yang tidak draf, tidak ditolak/dibatalkan, dan belum tuntas: status diajukan / dalam
  persetujuan / disetujui / dicairkan, **atau** `settled` yang sisa dikembalikannya masih open/returning (uang masih di
  tangan). PD yang sedang diperiksa tidak dihitung dirinya sendiri.
- **Ajukan** PD baru saat PD terbuka orang itu ≥ batas → 409 berkalimat: "Anda masih memegang uang muka PD-… (Rp …, LPJ
  jatuh tempo …). Selesaikan LPJ-nya dulu sebelum mengajukan uang muka baru." Draf boleh disimpan. **Cairkan** memeriksa
  ulang (orang yang sudah memegang PD lain yang cair dan belum tuntas → 409); keadaan lama di VPS (orang dengan > batas PD
  terbuka) tidak dibatalkan — PD lama berjalan, PD baru tertahan sampai di bawah batas.
- Layar form PD: bila pemohon sudah di batas, tombol Ajukan mati + kalimat server (pola tombol mati beralasan).

### 5.2 C7 — tenggat LPJ

- Pengaturan `kas.lpj_tenggat_hari` (bawaan **7**, 1–90). Saat **dicairkan**, PD menyimpan `lpj_jatuh_tempo` = tanggal buku
  cair + N hari (pengaturan berubah tidak menggeser tenggat PD yang sudah cair).
- PD cair **sebelum fitur aktif** (tanpa potret): tenggat dihitung `max(tanggal cair, tanggal fitur aktif) + N` (penanda
  sekali tulis, pola F1/Kas & Bank 3) — tidak ada PD yang langsung lewat tenggat pada hari pembaruan.
- **Tenggat terpenuhi** bila LPJ PD itu berstatus diajukan, disetujui, atau terjurnal; LPJ ditolak → kembali dihitung.
- **Lewat tenggat:** (a) lencana di daftar PD / Kas Kecil ("LPJ jatuh tempo 5 Des" · "Lewat 3 hari"); (b) antrean Meja
  Keuangan **"LPJ uang muka lewat tenggat"** (per PD: pemohon, PT, nominal, hari lewat; buka PD); (c) pemberitahuan ke
  pemohon **H-1** dan **saat lewat** (sekali per PD per jenis, lewat penjadwal pola LB-T5; gagal → hanya log).

### 5.3 C8 — akun & pembantu

- Akun bawaan baru **`1-1410 Uang Muka Pemasok`** (aset, induk 1-1000), kunci pemetaan **`hutang.uang_muka_pemasok`** (bawaan
  1-1410). 1-1400 tetap untuk uang muka karyawan (`kas_bank.uang_muka_karyawan`) dan biaya dibayar dimuka; nama akun lama
  tidak diubah.
- **Satu pembantu** `gl_service.akun_uang_muka_pemasok(entity_id)`: PT belum pindah → `1-1400` (perilaku sekarang); PT
  sudah pindah → akun pemetaan PT (bawaan 1-1410). Semua jalur uang muka pemasok — lebih bayar tagihan (`ap_advance`),
  selisih bayar, kasus lebih bayar & refund, potongan kontrabon `supplier_advance`, pembaca saldo — memakai pembantu ini.
  Penjaga statis (pola `verify_akun_kas_satu_pintu`) menolak `ACC_UANG_MUKA` / "1-1400" harfiah di modul jalur pemasok.

### 5.4 C8 — pindah saldo uang muka pemasok per PT

- Dokumen per PT (pola `cash_account_cutover`): **pratinjau** = daftar uang muka pemasok terbuka PT itu per pemasok
  (sub-ledger yang sama dengan yang ditawarkan sebagai potongan kontrabon/refund) + total + saldo 1-1400 PT saat ini;
  **siapkan** (Finance, izin `accounting.manage`) membekukan isi + sidik; **setujui** (orang kedua; kontrol
  `kontrol.pindah_uang_muka_pemasok` bawaan 2 orang, masuk bawaan `kontrol.admin_tetap_dua_orang`) menghitung ulang, menolak
  bila berubah sejak disiapkan, menjurnal **Dr 1-1410 / Cr 1-1400** sebesar total bertanggal buku, lalu menyalakan penanda
  PT (sekali tulis). Total 0 → tetap boleh disetujui (penanda menyala tanpa jurnal). Tolak beralasan. Tanpa migrasi saat
  menyala; VPS tidak memindah apa pun sampai Finance PT itu melakukannya.
- Sumber sub-ledger yang tidak sepakat (mis. `suppliers.advance_balance` ≠ dokumen uang muka terbuka PT) → pratinjau
  menampilkan keduanya per pemasok dan **menahan** siapkan dengan kalimat (perbaiki dulu lewat kasus keuangan).

### 5.5 Daftar pencocokan

- **Uang muka terbuka** (baca saja, per PT): (a) karyawan — PD terbuka per pemohon (nominal cair, sudah di-LPJ, sisa di
  tangan, tenggat) dibanding saldo 1-1400 PT; (b) pemasok — uang muka terbuka per pemasok dibanding saldo akun pemasok PT
  (1-1410 bila PT sudah pindah; bila belum, ditampilkan bersama karyawan dengan catatan "1-1400 masih memuat uang muka
  pemasok sampai PT dipindah"). Selisih ditampilkan dengan penjelasan (1-1400 juga memuat biaya dibayar dimuka).
- Butir daftar periksa tutup buku **"Uang muka cocok"** bersifat peringatan (tidak menahan tutup buku): selisih akun vs
  daftar per PT, dan jumlah PD lewat tenggat.

### 5.6 Layar

- Kas Kecil › Pengajuan dana: lencana tenggat/lewat, tombol Ajukan mati beralasan, kolom tenggat; Meja Keuangan: kartu
  "LPJ uang muka lewat tenggat"; pemberitahuan pemohon.
- Uang muka terbuka (§5.5) dan Pindah saldo uang muka pemasok (§5.4): letak mengikuti layar pindah saldo Kas & Bank 1
  (tab/chip tersembunyi, tanpa menambah tab hub yang sudah 6); pratinjau dokumen + Jejak.

## 6. Aturan bersama

Wewenang = izin (`cash_advance.*`, `cash_settlement.*`, `accounting.manage`); nilai = pengaturan (`kas.pd_terbuka_maks`,
`kas.lpj_tenggat_hari`, `kontrol.pindah_uang_muka_pemasok`); satu pintu kas `create_cash`; jurnal lewat `gl_service`; tanpa
migrasi data saat menyala (penanda aktif sekali tulis dikecualikan); urutan PERIKSA → KLAIM → EFEK → SELESAI
(`docs/blueprint/02_STANDAR.md` §1).

## 7. Keputusan builder (periksa)

1. Orang = pengguna pemohon PD (`created_by_id`), batas dihitung lintas PT; batas & tenggat = pengaturan per PT dokumen.
2. PD terbuka termasuk PD dalam persetujuan dan PD `settled` yang sisanya belum kembali; draf tidak dihitung.
3. Diperiksa saat ajukan dan saat cairkan; keadaan lama tidak dibatalkan.
4. Tenggat dipotret saat cair; PD lama dihitung dari tanggal fitur aktif; terpenuhi saat LPJ diajukan (bukan disetujui).
5. Lewat tenggat = lencana + kartu Meja + pemberitahuan (H-1 & lewat); tidak memblokir apa pun selain aturan batas.
6. Akun `1-1410 Uang Muka Pemasok`, kunci `hutang.uang_muka_pemasok`; 1-1400 tetap uang muka karyawan.
7. Pindah per PT lewat pratinjau → siapkan → setujui orang kedua (kontrol baru bawaan 2); sumber sub-ledger yang tidak
   sepakat menahan siapkan.
8. Daftar pencocokan + butir tutup buku peringatan.
