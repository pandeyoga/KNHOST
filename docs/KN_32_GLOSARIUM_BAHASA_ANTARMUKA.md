# KN_32 — GLOSARIUM & KEBIJAKAN BAHASA ANTARMUKA

**Berlaku sejak:** 2026-07-29 · **Status:** ditegakkan oleh gate (bukan imbauan)
**Keputusan pemilik:** seluruh antarmuka memakai **Bahasa Indonesia**.

---

## 1. Masalah yang diselesaikan

Aplikasi ini dipakai bersama tim gudang, sales, dan keuangan yang bekerja dalam
Bahasa Indonesia. Sebelum sesi ini, "sudah Bahasa Indonesia" hanyalah **klaim prosa**:

* satu berkas diterjemahkan, berkas berikutnya kembali berbahasa Inggris;
* tidak ada satu pun alat yang bisa **GAGAL** ketika label Inggris masuk lagi;
* sebagian teks yang dilihat pengguna ternyata lahir di **backend**
  (`routers/onboarding.py`, judul dokumen cetak, pesan penjadwal) — bagian ini
  tidak pernah ikut diperiksa.

Akibat nyata di lapangan: operator gudang melihat `Available`, `Picked`,
`Quarantine`, `Putaway` — dan keraguan di gudang berujung salah kirim.

## 2. Bentuk penegakan (executable guardrail)

| Alat | Peran |
|---|---|
| `scripts/audit_i18n_id.py --strict` | **MEMERAH** bila ada istilah Inggris pada teks yang dilihat pengguna (FE **dan** BE) |
| `scripts/audit_i18n_id.py --self-test` | **bukti-merah**: 12 skenario membuktikan audit benar-benar bisa memerah, dan tidak salah-lapor pada `data-testid` / `className` / kunci objek / URL |
| `scripts/fix_i18n_id.py --apply` | codemod: menerjemahkan **hanya rentang teks pengguna** memakai pemindai yang sama |
| `scripts/fix_i18n_id.py --self-test` | **bukti-merah**: 11 skenario membuktikan codemod TIDAK menyentuh kunci objek, nilai status backend, `data-testid`, `className`, atau jalur impor |
| `scripts/i18n_table_id.py` | tabel terjemahan tingkat-frasa (data, bisa di-review seperti daftar kata) |

Ketiganya masuk `scripts/gate.sh` (blok STATIK) sehingga `bash scripts/gate.sh`
memerah bila ada regresi bahasa.

### 2.1 Yang dipindai (dan yang TIDAK)

**Dipindai** — hanya yang benar-benar tampil:

* teks JSX antar-tag `>Tersedia<`
* teks di **sekitar interpolasi** `>Onboarding — {peran}<` · `>{n}× pesanan<`
  (celah nyata yang pernah meloloskan 60+ label)
* potongan **template literal** `` sub={`${n} pesanan`} ``
* nilai prop teks: `label` · `title` · `placeholder` · `sub` · `description` · dst.
* di **backend**: nilai kunci `label` · `description` · `title` · `message` · `detail` · `note`

**Tidak dipindai** (supaya nol temuan palsu): `data-testid`, `className`, kunci
objek, nama field API, jalur impor, URL, komentar, dan berkas uji/POC/seed.

## 3. Kata yang WAJIB diterjemahkan (kamus)

134 istilah. Cetak lengkap: `python scripts/audit_i18n_id.py --list`. Contoh inti:

| Inggris | Indonesia | | Inggris | Indonesia |
|---|---|---|---|---|
| Available | Tersedia | | Pending | Menunggu |
| Reserved | Dipesan | | Approved | Disetujui |
| Committed | Dialokasikan | | Rejected | Ditolak |
| Picked | Sudah Diambil | | Cancelled | Dibatalkan |
| Packed | Sudah Dikemas | | Overdue | Lewat Jatuh Tempo |
| Quarantine | Karantina | | Outstanding | Belum Lunas |
| Blocked | Diblokir | | Inbound | Barang Masuk |
| Damaged | Rusak | | Outbound | Barang Keluar |
| Sold | Terjual | | Receiving | Penerimaan |
| Putaway | Penempatan Rak | | Picking | Pengambilan |
| In-Transit | Dalam Perjalanan | | Packing | Pengemasan |
| Draft | Draf | | Dispatch | Pengiriman |
| Order | Pesanan | | On Hand | Stok Fisik |
| Customer | Pelanggan | | Ledger | Mutasi |
| Invoice | Faktur | | Void | Anulir |
| Approval | Persetujuan | | Reversal | Pembalikan |
| Warehouse | Gudang | | Refund | Pengembalian Dana |
| Work Order | Perintah Kerja | | Cycle Count | Stock Opname |

## 4. Kata yang SENGAJA dibiarkan (43 istilah)

Menerjemahkan istilah berikut **memperburuk** kejelasan, bukan memperbaikinya.

### 4.1 Singkatan dokumen yang dipakai lisan sehari-hari
`PO` · `SO` · `PR` · `GR` · `RFQ` · `SKU` · `UOM` · `QC` · `WMS` · `CRM` · `POS` · `HPP` · `RFID`

### 4.2 Istilah tekstil / bahasa kerja industri
`Lot` · `Roll` · `Grade` · `Makloon` · `Finishing` · `Batch` · `Stock Opname` ·
`Landed Cost` · `Supplier` · `Item`

### 4.3 Kata yang memang Bahasa Indonesia / serapan baku
`Total` · `Status` · `Detail` · `Info` · `Transfer` · `Filter` · `Reset` ·
`Bank` · `Debit` · `Target` · `Email` · `Password` · `Scan` · `No.` · `Log` · `CSV`

### 4.4 Dua keputusan yang perlu penjelasan
| Kata | Alasan tetap Inggris |
|---|---|
| **Sales** | dalam praktik Indonesia berarti **orang/tim penjualan** ("tim sales", "kunjungan sales"). Menerjemahkan jadi "Penjualan" mengubah maknanya dari *orang* menjadi *proses*. |
| **Stage** | **enum domain tekstil** (`yarn → grey → finished`) yang divalidasi server (`domain_registry`, aturan transisi). Layar sengaja menyebut nama enumnya supaya cocok dengan pesan penolakan server. |
| **Unit** | sah dalam Bahasa Indonesia (unit organisasi/kerja). Untuk **satuan ukur** dipakai kata "Satuan". |

### 4.5 Istilah keuangan yang sudah jadi nama akun/laporan
`Store Credit` · `Petty Cash` · `Cash Advance` · `AR/AP Aging` · `Weighted Average Cost` ·
`Backorder` — menerjemahkannya memutus kaitan layar dengan nama akun GL & laporan
yang dipakai tim keuangan.

## 5. Izin khusus per-kalimat (`IZIN_KHUSUS`)

Beberapa kalimat **sengaja** memuat kata Inggris karena kata itu adalah **nilai
sistem**, bukan kalimat untuk dibaca. Contoh paling jelas: nama peran RBAC.

> "Hanya `manager/admin` yang dapat menyetujui."

Kalau layar menulis "manajer" sementara nilai di server `manager`, pengguna
mencari "manajer" di matriks izin dan tidak menemukannya. Karena itu setiap
pengecualian **wajib mencantumkan alasan** di `IZIN_KHUSUS` — daftarnya sengaja
pendek agar tidak berubah menjadi tempat sampah.

## 6. Cara menambah istilah baru

```bash
# 1) lihat apa yang masih Inggris
python scripts/audit_i18n_id.py

# 2) tambahkan pasangan istilah ke KAMUS (scripts/audit_i18n_id.py)
#    atau kalimat utuh ke TABEL (scripts/i18n_table_id.py)

# 3) terapkan + buktikan
python scripts/fix_i18n_id.py --apply
python scripts/audit_i18n_id.py --strict     # harus 0 temuan
python scripts/fix_i18n_id.py --self-test    # codemod tetap aman
bash scripts/rebuild_frontend.sh             # preview = bundel statis, WAJIB rebuild
```

## 7. Catatan operasional

* **Tidak ada hot-reload frontend** (lihat `memory/PREVIEW_STABLE_MODE.md`).
  Setiap perubahan `frontend/src` wajib `bash scripts/rebuild_frontend.sh`.
* Codemod **tidak** menyentuh `data-testid`, jadi seluruh skrip uji tetap jalan.
  Satu kasus khusus diperbaiki manual: `LoginScreen` dulu memakai satu nilai
  untuk label DAN testid (`demo-login-${role}`), kini dipisah `key` vs `label`.
* Angka acuan sesi ini: **757 penggantian** di **±230 berkas** (FE + BE),
  audit akhir **0 temuan**.

## 8. Istilah cakupan PT di laporan & form uang (PK-16 · K-15)

Laporan keuangan, form uang, dan berkas unduhan selalu menyebut PT yang angkanya ditampilkan
(`frontend/src/components/EntityScopeBanner.jsx`, field `scope_meta` di jawaban server). Kalimatnya baku —
jangan diganti sinonim di layar lain, supaya pengguna mengenali keadaan yang sama di semua laporan.

| Istilah | Arti | Dipakai di |
|---|---|---|
| **Penjumlahan semua PT** | Mode "Semua PT": angka laporan = jumlah buku tiap PT dalam cakupan pengguna, **bukan** angka grup. Selalu diikuti nama pendek PT-nya dalam kurung. | banner laporan mode gabungan; baris `Cakupan:` di unduhan CSV/XLSX |
| **belum dieliminasi** | Transaksi antar-PT (jual/beli, pinjaman, pelunasan antar-PT) masih ikut terhitung di kedua sisi; angka grup yang sudah dieliminasi hanya ada di **Konsolidasi Grup** (Akuntansi & Pajak › Laporan). Kalimat lengkap: "transaksi antar-PT **belum** dieliminasi". | banner laporan mode gabungan; label `scope_meta.label` |
| **Angka untuk {PT}** | Laporan satu PT; nama lengkap PT (bukan id, bukan singkatan). | banner laporan satu PT |
| **Dicatat di buku {PT}** | Form uang menyimpan ke buku PT di kepala aplikasi (bukan pilihan lokal di form). | form "Catat Transaksi Kas", form jurnal manual |
| **gabungan** | Penanda mode "Semua PT" pada **nama berkas** unduhan (`laba-rugi_gabungan_…csv`); satu PT memakai nama pendeknya (`laba-rugi_KSC_…csv`). | nama berkas CSV/XLSX laporan |

Mode gabungan memakai mesin konsolidasi (angka sudah dieliminasi) baru menyusul di PK-31; saat itu kalimat
"belum dieliminasi" diganti.

## 9. Istilah baku dari unit blueprint (PK-17)

Istilah yang lahir di unit `docs/blueprint/unit/<ID>.md`. Satu istilah untuk satu hal; teks layar dan pesan server
memakai kalimat persis di kolom "Teks".

| Istilah | Teks | Arti | Unit · tempat |
|---|---|---|---|
| Nilai disembunyikan | "Nilai disembunyikan" + petunjuk "Peran Anda tidak punya akses lihat modul dokumen ini." | Nominal dokumen yang modul sumbernya tidak boleh dilihat peran pembaca. Server mengirim `amount: null`, `amount_hidden: true`; nomor, jenis, status, dan tanggal tetap tampil, tombol buka dan cetak simpul itu mati. Kartu ringkasan yang nilainya disembunyikan menulis "—" | PK-17 · Jejak Dokumen (graf, pencarian, cetak), Referensi Dokumen, Kontrabon, kartu saldo Antar-PT ("Saldo antar-PT hanya untuk peran berizin keuangan antar-PT.") |
| Kelola rekening kas & bank | "Kelola rekening kas & bank" | Izin `cash.configure` (modul "Kas, Bank & Kasus Keuangan"): membuat dan mengubah rekening kas/bank. Terpisah dari mencatat transaksi kas (`cash.create`). Pesan 403: "Anda belum punya akses untuk mengelola rekening kas dan bank. Minta Admin menambahkan akses 'Kas, Bank & Kasus Keuangan'." | PK-17 · Peran & Hak Akses (label aksi), Kas & Bank › Rekening |
| Kontrol dua orang | "Kontrol dua orang" (tab Pengaturan › Persetujuan) · pilihan "Cukup satu orang" / "Harus dua orang" · kolom "Dua orang di atas (Rp)" · sumber "Aturan PT ini" / "Mengikuti semua PT" / "Aturan semua PT" / "Bawaan" | Aturan "pengaju tidak boleh memutuskan dokumennya sendiri", per aksi dan per PT. "Harus dua orang" = keputusan wajib oleh orang selain pengajunya; di atas batas nominal selalu dua orang. Pesan 403: "{Aksi} harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang berwenang. Admin dapat mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang." Jangan memakai "SoD", "segregation of duties", "dual control" di layar | KF-T6 · Pengaturan › Persetujuan › Kontrol dua orang, semua titik setuju/putus |
| Jenjang | "Jenjang 1 · Persetujuan", "Jenjang 2 · Direksi" · kolom "Jenjang", "Mulai dari (Rp)", "Sampai di bawah (Rp)", "Yang boleh menyetujui", "Siapa saja yang lolos" · lencana "Aturan grup" / "Aturan khusus PT ini" / "Aturan bawaan (belum disimpan)" · pilihan "Semua pemegang akses" · tombol "Ubah", "Buat aturan khusus PT ini", "Kembali ke aturan grup", "Coba nilai" | Urutan keputusan satu dokumen; tiap jenjang punya rentang nominal (batas atas eksklusif: "sampai di bawah") dan daftar peran yang boleh memutus. Yang lolos = peran tercantum DAN memegang izin setujui modulnya. Pesan 403: "Anda belum punya akses untuk menyetujui {jenis}. Minta Admin menambahkan akses '{modul}'." atau "{Jenis} senilai {Rp} pada jenjang {n} diputus oleh {peran}. Peran Anda belum tercantum di Aturan Persetujuan." Jangan memakai "tier", "level", "approver", "role", "threshold" di layar | KP-T4 · Pengaturan › Persetujuan › Aturan Persetujuan, semua pintu setuju/putus |
| Menunggu orang kedua | "Menunggu orang kedua" · "{n} jurnal manual menunggu orang kedua" · "Menunggu orang kedua — diajukan {nama}" | Pengajuan (jurnal manual, buka kembali tutup buku) sudah tercatat tetapi belum dijalankan; orang lain yang berwenang yang menjalankannya | KF-T6 · Buku Besar › Jurnal, Tutup Buku |
| PT induk (konsolidasi) | "PT induk (konsolidasi)" (sakelar di wizard & detail PT) · keterangan "PT induk tidak ikut dijumlahkan sebagai baris di laporan konsolidasi dan tidak muncul di pilihan PT pada tutup buku." | PT pemegang saham grup (`is_group`). Laporan konsolidasi menjumlahkan PT anggota, bukan PT induk; PT induk juga tidak ditawarkan di pemilih PT Tutup Buku, Buka Periode, Suspense, Eliminasi. Jangan memakai "holding" atau "parent" untuk teks baru | KP-T1 · Pengaturan › Badan Usaha & Akses › Badan Usaha |
| Persen kepemilikan | "Persen kepemilikan (%)" · keterangan "Belum memengaruhi angka — dipakai laporan konsolidasi setelah eliminasi per periode aktif." | Persen saham grup atas PT ini (> 0 sampai 100, bawaan 100; K-10). Mati bila PT induk. Saat ini hanya dicatat; hitungan konsolidasi memakainya mulai PK-31. Jangan memakai "ownership" | KP-T1 · Pengaturan › Badan Usaha & Akses › Badan Usaha |
| Ubah status PKP | Tombol "Ubah status PKP" · pop-up "Ubah Status PKP" ("Status baru", "Berlaku mulai", "NPWP", "Alasan", panel "Dampak") · "Akan menjadi {status} mulai {tanggal}" + "Batalkan jadwal" | Tindakan bertanggal berlaku dan beralasan untuk mengubah status PKP PT (PKP = memungut PPN, Non-PKP = tanpa PPN). Tanggal hari ini/lampau langsung berlaku; tanggal mendatang dijadwalkan. Dokumen yang sudah ada tidak dihitung ulang. Status PKP tidak diubah lewat "Simpan Perubahan" profil | KP-T1 · detail PT, bagian Pajak |
| Tahun buku & mata uang | "Tahun buku: {bulan awal}–{bulan akhir}" · "Mata uang pembukuan: {label}" · sumber "mengikuti pengaturan grup" / "khusus PT ini" · wizard "Tahun buku berakhir pada bulan" | Nilai yang dipakai laporan dan tutup buku tahunan (kunci Pusat Pengaturan, lapisan PT). Pakai "tahun buku", bukan "tahun fiskal"/"awal tahun fiskal", dan "mata uang pembukuan", bukan "mata uang" saja | KP-T1 · detail PT & wizard Tambah Badan Usaha |
| Batas retur umum | "Batas retur umum" (judul bagian) · baris hanya-baca "Batas retur umum: pelanggan {n} hari sejak surat jalan · pemasok {m} hari sejak barang diterima." | Batas hari retur yang berlaku bila kebijakan retur per kategori/pelanggan tidak menimpanya: pelanggan dihitung dari tanggal surat jalan, pemasok dari tanggal barang diterima gudang; plus pengingat ke pemasok, potong tagihan pesanan asal, dan harga per grade. Diatur di Pusat Pengaturan (kunci `returns.*`), bukan form sendiri. Jangan memakai "asumsi retur" di layar | KF-T2 · Penjualan › Retur › Kebijakan Retur |
| Aturan jadwal bayar | "Aturan jadwal bayar" (judul bagian) · "Tanggal tutup tagihan antar-PT" · "Tanggal bayar antar-PT" · "Tanggal acuan jadwal bayar antar-PT" · "Izinkan saling hapus hutang antar-PT" | Aturan yang menentukan periode dan tanggal bayar tiap transaksi antar-PT, pengingatnya, serta boleh-tidaknya saling hapus dan pelunasan sebagian — untuk semua PT atau satu PT pembayar. Pakai "saling hapus", bukan "netting", dan "tanggal tutup", bukan "cutoff", untuk teks baru | KF-T2 · Keuangan › Antar-PT › Jadwal Bayar |
| Aturan khusus | "Aturan khusus pelanggan ini" / "Aturan khusus barang ini" (judul bagian) · "Mengikuti aturan PT: {nilai}" · "Khusus pelanggan ini: {nilai} (aturan PT: {nilai})" · tombol "Atur khusus" / "Kembali ikut aturan PT" · "Bisa dibedakan per pelanggan — {n} pelanggan diatur khusus" | Nilai aturan Pusat Pengaturan yang berlaku hanya untuk satu pelanggan atau satu barang dan menang atas aturan PT-nya (mis. masa tenggang denda, toleransi selisih bayar, batas susut potong). Kosong = mengikuti aturan PT. Pakai "aturan khusus", bukan "override"/"lapisan pelanggan"; "barang" untuk teks baru (menu tetap "Produk") | KF-T5 · Penjualan › Pelanggan & CRM › detail pelanggan; Produk & Harga › Master Produk › ubah barang; kartu Pusat Pengaturan |
| Status rekonsiliasi transaksi kas | Lencana "Terekonsiliasi" · "Sebagian {rupiah}" (keterangan "Sudah dicocokkan {rupiah} dari {rupiah}") · "Belum" · tautan "Cocokkan di Rekonsiliasi Bank" · pesan 410 "Tanda rekonsiliasi manual sudah tidak dipakai. Cocokkan transaksi dengan mutasi bank di Keuangan › Rekonsiliasi Bank." · pesan 409 "Mutasi bank ini baru saja dilepas atau diubah proses lain. Muat ulang." | Seberapa jauh transaksi kas sudah dicocokkan dengan mutasi rekening koran: penuh, sebagian (angka yang sudah dicocokkan), atau belum sama sekali. Hanya lahir dari pencocokan di Rekonsiliasi Bank — tidak ada lagi tombol "Tandai". Pakai "Sebagian", bukan "parsial" | PK-21 · Keuangan › Kas & Bank › Rekening & Saldo (buku rekening), Rekonsiliasi Bank |
| Penerima & ambang pengingat | Kolom "Penerima" (mis. "Manajer", "Pemegang izin Tagihan Supplier — Bayar") dan "Ambang" (mis. "7 hari · 40 peringatan") + tautan "Ubah" di Penjadwal & Notifikasi · tabel "Penerima tiap pengingat" (kolom "Pengingat", "Cara menentukan": "Peran yang dipilih" / "Semua pemegang izin", "Peran", "Izin") | Siapa yang menerima tiap pengingat terjadwal dan batas kapan pengingat dikirim, untuk PT aktif (tabel PT menggantikan tabel grup). "Semua pemegang izin" = setiap akun aktif yang perannya memegang izin itu dan bertugas di PT dokumen. Pakai "ambang" (bukan "threshold") | KP-T7 · Pengaturan › Notifikasi & Penjadwal |
| Akun kontrol | Lencana "Akun kontrol" + petunjuk "Hanya berubah lewat dokumen {buku pembantu}" (Bagan Akun) · keterangan "Akun piutang, hutang, persediaan, dan antar-PT tidak ada di daftar ini karena saldonya dijaga dokumen. Koreksi lewat dokumennya." (Jurnal Manual Baru) · pesan 422 "Akun {kode} · {nama akun} adalah akun kontrol {buku pembantu} dan tidak menerima jurnal manual. Koreksi lewat {dokumen pengganti}." dan "Jurnal {nomor} berasal dari {sumber} dan menyentuh akun kontrol {buku pembantu}. Batalkan atau koreksi dokumen sumbernya; pembalikan manual ditolak." · pengaturan "Jurnal manual ke akun kontrol" (Tolak / Izinkan) | Akun buku besar yang saldonya dimiliki buku pembantu — piutang usaha, hutang usaha, persediaan, antar-PT — menurut Pemetaan Akun PT itu (termasuk akun lama di riwayat pemetaan). Hanya berubah lewat dokumennya; jurnal manual, reklasifikasi suspense, dan pembalikan manual jurnal otomatis ke akun itu ditolak kecuali pengaturan PT "Izinkan". Jangan memakai "control account" atau "akun rekonsiliasi" di layar | PK-36 · Jurnal & Buku Besar (Jurnal Manual Baru, Suspense, rincian jurnal), Bagan Akun, Pengaturan › Keuangan & Pajak |
| Jadwal teknis | "Jadwal teknis — tidak diubah dari layar." · "tiap [n] menit" / "tiap [n] jam" | Job penjadwal gerbang RFID yang selangnya dikunci (titik henti RFID); job lain diatur dalam satuan bawaannya (menit atau jam) | KP-T7 · Penjadwal & Notifikasi |

### 9.1 Modul akses & aksi pengganti nama peran (PR-T2)

Wewenang yang dulu ditentukan nama peran kini izin yang tampil di **Peran & Hak Akses** (`backend/access_modules.py`).
Label modul/sumber daya/aksi di bawah adalah teks layar editor peran; pesan 403 dipetakan pusat di PR-T6.

| Modul (grup) | Sumber daya — label | Aksi baru (label) |
|---|---|---|
| **Pengawasan Tim Sales & Kredit** (Penjualan) | `sales_force` — "Tim Sales: Target, Insentif & Penugasan"; `credit_override` — "Pengecualian Batas Kredit" | `sales_force.post` "Catat akrual ke buku besar", `sales_force.assign` "Pindahkan pelanggan ke sales lain" |
| **HPP & Margin Produk** (Alat, sensitif) | `costing` — "HPP & Margin Produk" | `view` — juga menentukan kolom biaya/HPP di jawaban server |
| **Beranda Manajer** (Alat) | `manager_home` — "Beranda Manajer" | `view` |
| **Kebersihan Data & Alat Sistem** (Organisasi, sensitif) | `system_tools` — "Kebersihan Data & Alat Sistem" | `configure` "Jalankan & kembalikan pembersihan, lepas kunci proses" |
| **Perangkat RFID & Handheld** (Gudang, sensitif) | `rfid_device` — "Perangkat RFID & Handheld" | `configure` "Daftarkan & atur perangkat", `revoke` "Cabut akses perangkat" |
| **Asisten Tanya KN** (Alat) | `ai` — "Asisten Tanya KN"; `ai_template` — "Templat Laporan Tanya KN" | `view_margin` "Lihat margin & laba kotor", `view_stock_value` "Lihat nilai persediaan", `ai.manage` "Lihat pemakaian & atur aturan asisten", `ai.configure` "Pengaturan teknis asisten & buka riwayat pengguna lain"; satu aksi per templat (label = judul templat) |

Aksi baru pada sumber daya lama: `rnd.manage_org` "Kelola divisi R&D", `rnd.report` "Laporan penilaian desainer & papan
SLA", `rnd.extend_rounds` "Buka ronde di atas batas", `goods_receipt.configure` "Ganti mode penerimaan",
`warehouse.configure` "Ubah struktur & profil gudang", `accounting.reopen` "Buka kembali periode & tembus blokir akun
sementara", `inspection.release` "Lepas / tolak tahanan barang", `product.retire` "Nonaktifkan / hapus permanen master",
`sales_return.treat_cutloss` "Pilih potongan cacat: masuk BS atau dibuang", `od_pricing.unlock` "Buka kunci harga final".
Pengaturan yang digantikan izin ini berstatus "tidak dipakai" dengan alasan "Diatur di Peran & Hak Akses › …"
(`ai.enabled_roles`, `ai.margin_roles`, `ai.stock_value_roles`, `returns.cutloss_treatment_roles`).

**Tingkat akses & modul organisasi (PR-T5).** Satu kamus label (`GET /api/access/labels`, sumber `access_modules.py`)
dipakai editor peran, pesan penolakan, dan jejak audit; perbaikan kata per label di PR-T6.

| Istilah | Teks layar | Arti |
|---|---|---|
| Tingkat akses | **Tidak ada** · **Lihat saja** · **Semua aksi** (dulu "Kelola penuh") | Hanya tingkat yang berlaku untuk modul itu yang ditawarkan. Modul tanpa aksi lihat = sakelar **Mati** · **Nyala** (mis. "Melihat grade, nomor lot & asal barang", "Perangkat RFID & Handheld"); modul yang satu-satunya aksinya lihat tidak punya "Semua aksi" (mis. "Pusat Persetujuan", "Beranda Manajer", "HPP & Margin Produk", "Laporan & Analitik"). Pesan 400: "Tingkat “{tingkat}” tidak berlaku untuk modul “{modul}”." |
| Sebagian | Lencana **"Sebagian ({n} dari {m} aksi)"** di kanan nama modul; tidak ada tombol tingkat yang menyala | Peran memegang sebagian aksi modul (diatur di "Menu, tab & aktivitas"). Kartu peran: "{n} semua aksi · {n} sebagian · {n} lihat · {n} tidak ada" |
| Tidak termasuk pada Lihat saja | "Tidak termasuk pada Lihat saja: {halaman}." | Halaman yang tidak punya aksi lihat ikut tercabut pada "Lihat saja" (mis. Periode & Tutup Buku, Amandemen Keuangan, Harga Pesanan Khusus) |
| Aksi berisiko | Ikon peringatan + petunjuk "Peran ini bisa {akibat}." · dialog simpan: "Perhatian — peran ini akan bisa: {akibat}; {akibat}." | Daftar `SENSITIVE_ACTIONS` (membuka periode, membayar pemasok, mengelola akun orang lain, …); hanya peringatan, izin tidak berubah |
| Modul organisasi | **Akun Pengguna** · **Peran & Hak Akses** · **Badan Usaha (PT)** · **Pusat Pengaturan** · **Penjadwal & Notifikasi Otomatis** | Pengganti modul gabungan "Pengaturan, Pengguna & Hak Akses": memberi "kelola akun" tidak lagi ikut memberi ubah peran, kelola PT, ubah pengaturan, dan penjadwal. Pesan 403 menyebut modul pemilik izinnya, mis. "Minta Admin menambahkan akses 'Pusat Pengaturan'." |

### 9.2 Sifat peran (PR-T4)

Empat hal yang dulu melekat pada nama peran dasar kini isian **Sifat peran** di editor Peran & Hak Akses
(`RoleTraitsPanel.jsx`; disimpan `permission_settings.role_traits`). Isian yang tidak diubah Admin tampil
"Mengikuti {peran dasar}" atau "Mengikuti bawaan sistem".

| Istilah | Teks layar | Arti |
|---|---|---|
| Cakupan data | Label isian **"Data yang terlihat"** · pilihan "Milik sendiri" / "Milik sendiri dan timnya" / "Semua di PT yang boleh dibuka" · keterangan "Berlaku untuk pelanggan, pesanan, pengajuan harga, prospek, pengiriman, dan permintaan desain." | Dokumen ber-pemilik siapa yang terlihat dan bisa diubah pemegang peran, di dalam PT yang boleh dibuka. "Timnya" = akun yang karyawannya berada di unit organisasi yang dikepalai karyawan pelaku. Pesan 403 bila diberi lebih luas: "Anda tidak bisa memberi cakupan data lebih luas dari cakupan peran Anda sendiri." Jangan memakai "scope" / "row-level" di layar |
| Halaman awal | Label **"Halaman awal"** · keterangan "Layar pertama setelah masuk." · pilihan yang izinnya belum dimiliki: "{layar} · Butuh akses yang belum dimiliki peran ini" | Layar pertama setelah masuk. Bila izin layar tersimpan dicabut, akun mendarat di Profil Saya. Pesan 400: "Halaman awal “{layar}” butuh akses yang belum dimiliki peran ini." |
| Kategori kerja | Label **"Kategori kerja"** · pilihan "Tidak ada" / "Sales" / "Sopir" / "Desainer" / "Petugas gudang" / "Pengawas" · kalimat akibat di bawah isian | Jenis pekerjaan pemegang peran: menentukan siapa yang muncul di daftar pilih sales/sopir/desainer, ikut papan peringkat, komisi dan akrual insentif, dibatasi lokasi kerja, dan jenis Meja Saya. Peran tanpa kategori: "Peran Anda belum punya meja kerja. Buka menu yang tersedia di samping." |
| Ikut menerima notifikasi | Label **"Ikut menerima notifikasi untuk"** · keterangan "Notifikasi giliran tetap mengikuti izin." | Notifikasi yang dialamatkan ke peran bawaan yang dicentang ikut sampai ke pemegang peran ini |
| KPI & komisi sales lain | Label aksi "Lihat KPI & komisi sales lain" (modul Pesanan Penjualan) | Izin `order.view_sales_kpi`: memilih sales lain di dasbor Tim Sales. Tanpa izin ini (dan untuk peran bercakupan "milik sendiri") permintaan KPI sales lain menampilkan KPI dirinya |

### 9.3 Bahasa kartu Pengaturan (KF-T4)

Satu istilah untuk teks registry Pengaturan (label, penjelasan, dampak, contoh, pilihan) dan layar `settings-cfg-*` /
"Semua pengaturan". Ditegakkan penjaga `scripts/guardrails/verify_config_text.py` (INV-CFG-TXT, aturan T1–T7, 0
pelanggaran): label ≤ 45 huruf, tanpa label kembar, tanpa kata teknis/id/kode HTTP/kode keputusan, kunci angka
bersatuan, arti angka 0 ditulis, dan kata di kolom "Menggantikan" tidak dipakai (label juga tanpa "ambang", "SJ", "GRN";
frasa yang persis label menu dikecualikan). Singkatan PO, QC, HPP, RFID tetap.

| Dipakai | Menggantikan |
|---|---|
| **PT**; "grup" = semua PT; "Semua PT" · **antar-PT** · **pelanggan** · **pemasok** ("mitra makloon" khusus makloon) · "PO kita" | entitas, badan usaha, perusahaan (badan hukum) · antar entitas · customer, pembeli, toko · supplier, vendor · klien |
| **persetujuan / disetujui** · **penyetuju** · **pengaju** | ACC (kecuali nama status tercetak di layar R&D), approval, disahkan · approver · pengusul |
| **Manajer** · **Admin (Direksi)** saat pertama disebut, lalu "Admin" · **peran** · **bawaan** | manager · Direksi, pemilik, owner · role · default |
| **toleransi** (selisih yang dimaafkan) · **batas** (angka tertinggi/terendah) · "**mulai** (nilai)" untuk persetujuan | ambang |
| **Biarkan / Beri peringatan / Tolak** (atau **Tahan** untuk barang); **ditolak** = aksi dibatalkan, **ditahan** = menunggu keputusan · **aktif / mati** | enam susunan kata lama; blokir, blok keras, block · hidup, nyala, OFF, nonaktif |
| **pesanan** · **PO**, **permintaan pembelian** · **jumlah** | SO, order, Sales Order · Purchase Order, PR, Purchase Requisition · qty |
| **tagihan** · **Faktur Pajak** (hanya pajak) · **kwitansi** · **surat jalan** (ditulis lengkap) · **penerimaan barang** | invoice, bill, faktur (bukan pajak) · SJ · GRN, GR, Barang Masuk (kecuali nama menu) |
| **syarat bayar**; "tempo" = lama kredit · **koreksi dokumen** · **pengembalian dana** · **saldo pelanggan** (nama akun Store Credit tetap, §4.5) · **biaya pokok (HPP)** | term, termin · amandemen · refund · deposit · WAC |
| **peringatan** (muncul saat itu) · **pengingat** (kiriman terjadwal) · "dalam … hari" · **dinaikkan ke atasan** · **tingkat** | warn · jendela, rentang, horizon · eskalasi · jenjang, level |
| **putaran** · **sample** · **departemen** (SDM; "divisi" hanya matriks R&D) · **penggajian / slip gaji** · **stok** / "persediaan" (nilai di pembukuan) · "**dicatat di pembukuan**" · **produk** (master) / **barang** (fisik) | round, ronde · sampel · payroll · jurnal, GL, Dr/Cr, posting · SKU, artikel (di label) |
| **Pengaturan** (menu), **pengaturan** (satu kartu), "Semua pengaturan" · "**Berlaku untuk**" | Pusat Pengaturan, setting, konfigurasi, setelan · cakupan, level, lapisan |

Teks layar baku:

| Istilah | Teks | Arti |
|---|---|---|
| Berlaku untuk | "Semua PT (aturan grup)" / "Satu PT" + "Pilih PT…" · pita "Anda sedang mengubah aturan grup — berlaku untuk semua PT yang tidak punya nilai sendiri." / "Anda sedang mengubah nilai khusus {PT}. PT lain tidak terpengaruh." / "Pilih PT dulu supaya perubahan tersimpan pada PT yang benar." | Lapisan yang diubah. Pada aturan grup kartu menampilkan nilai grup dan "PT dengan nilai sendiri: {PT} = {nilai}" |
| Asal nilai | lencana "Bawaan sistem" · "Aturan grup" · "Khusus {nama PT}" · "Mengikuti nilai grup" | Dari mana nilai yang berlaku datang |
| Ikuti nilai grup | tombol "Ikuti nilai grup" · dialog "'{label}' untuk {PT} kembali mengikuti nilai grup ({nilai grup}). Nilai khusus {PT} ({nilai sekarang}) dicabut." | Mencabut nilai khusus PT (`POST /api/config/values/clear`); alasan bawaan "Kembali mengikuti nilai grup" |
| Pakai nilai bawaan sistem | "Pakai nilai bawaan sistem" (aturan grup) / "Pakai nilai bawaan sistem untuk PT ini" · dialog menyebut nilai bawaan dan akibatnya | Menulis nilai bawaan pada lapisan itu (`/values/reset`); untuk PT, PT itu tidak lagi mengikuti grup. Alasan bawaan "Dikembalikan ke nilai bawaan sistem". Kunci berisiko tinggi tanpa alasan → "'{label}' berisiko tinggi — alasan wajib diisi." Jangan menulis "Default" |
| Lanjutan (teknis) | blok tertutup "Lanjutan (teknis): {sub-judul}" · tombol kartu "Detail teknis" | Sub-judul `advanced` (model & anggaran AI, baca surat jalan otomatis, RFID & proses macet) dan kunci/berkas pemakai |
| Kesehatan Pengaturan | tab "Kesehatan Pengaturan" · kolom "Tersambung ke sistem?" | Pengganti "Kesehatan Konfigurasi", "Status wiring" |
