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
| Menunggu orang kedua | "Menunggu orang kedua" · "{n} jurnal manual menunggu orang kedua" · "Menunggu orang kedua — diajukan {nama}" | Pengajuan (jurnal manual, buka kembali tutup buku) sudah tercatat tetapi belum dijalankan; orang lain yang berwenang yang menjalankannya | KF-T6 · Buku Besar › Jurnal, Tutup Buku |

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
