# CR-T5 — Daftar kerja "Kredit & Plafon", janji bayar, dan rekening koran pelanggan

| | |
|---|---|
| Gelombang | Modul piutang dan kredit |
| Jenis | fitur |
| Risiko | sedang |
| Prasyarat | CR-T2 |
| Menutup temuan | CR-08 |
| Keputusan | K-31 |
| Standar | §3.1 (Z1, Z2, Z5, Z6), §3.2, §3.4 (N1, N3), §4 (L1–L4, L6–L8), §5 (D1, D4, D6), §6, §7 |
| Lingkungan uji | B (server) + uji jalan layar di A |

## Tujuan

Pengendali kredit bekerja dari satu tab berisi enam antrean, bukan dari lima menu. Dari baris mana pun ia membuka kartu
pelanggan yang memuat eksposur, jadwal tagihan, janji bayar, dan rekening koran yang bisa diminta "per tanggal",
dicetak, dan dikirim ke pelanggan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| Fakta | Jangkar |
|---|---|
| "Piutang" adalah satu layar tanpa tab; hub Piutang belum ada (dibentuk MN-T1) | `frontend/src/config/navStructure.js:305` (`ar-aging`), `frontend/src/AppViewRouter.jsx:180` (`ARAgingView`) |
| Persetujuan izin kredit hidup di CRM, tab "Persetujuan Kredit" | `frontend/src/features/crm/CrmView.jsx:27` (`approvals`) |
| Tindak lanjut penagihan punya hasil `promised` dan `next_action_date`, tanpa nominal dan tanpa status janji | `backend/schemas_crm.py:85` (`outcome`), `backend/routers/crm.py:214` (`add_followup`) |
| Daftar tagih dan pengingat dihitung per pesanan dari surat jalan pertama (dialihkan CR-T2 ke baris tagihan) | `backend/services/customer_service.py:450` (`collection_worklist`), `backend/services/customer_service.py:542` (`collection_reminders`) |
| Pengingat jatuh tempo hanya pemberitahuan internal pada H-3, H-1, H, H+1 | `backend/services/alert_ops_service.py:54` (`AR_DUE_SOON_OFFSETS`), `backend/services/alert_ops_service.py:280` (`job_ar_due_soon`) |
| Kartu pelanggan memuat riwayat pesanan, dokumen, harga khusus, sample, penagihan, override kredit, dan 50 kwitansi terakhir; tidak ada rekening koran | `backend/services/customer_service.py:318` (`customer_360`), `frontend/src/features/crm/Customer360Panel.jsx:18` (`HIST_TABS`) |
| Akun piutang yang dikenal diambil dari pemetaan akun | `backend/services/gl_mapping_service.py:71` (`known_codes`) |
| Mesin PDF bisa dipanggil langsung dengan isi dokumen | `backend/services/pdf_service.py:12` (`render_html`) |
| Nota denda draf sudah bisa didaftar per PT dan status | `backend/services/penalty_service.py:502` (`list_penalties`) |
| Modul akses `ar` memuat menu `ar-aging` | `backend/access_modules.py:134` (`ar-aging`) |

## Perubahan

### Data

`collection_followups` — field baru: `promise_date` (`YYYY-MM-DD`), `promise_amount` (angka > 0). Keduanya wajib bila
`outcome == "promised"`. Status janji **dihitung saat dibaca**, tidak disimpan: `menunggu` (tanggal belum lewat),
`ditepati` (Σ kwitansi non-void pelanggan itu di PT itu, bertanggal dari tanggal catatan sampai `promise_date`, ≥
`promise_amount`), `ingkar` (tanggal lewat dan belum terpenuhi). Indeks `(entity_id, outcome, promise_date)`.

Tidak ada koleksi baru.

### Server

Berkas baru `backend/services/credit_desk_service.py` — `async def queue(name, entity_ids, actor, page, page_size, q)`
dan `async def summary(entity_ids, actor)`. Semua antrean disaring PT aktif dan cakupan pelanggan pengguna
(`can_access_customer`; setelah PR-T4, sifat peran `data_scope`).

| Antrean (`name`) | Sumber | Kolom jawaban | Urutan |
|---|---|---|---|
| `menunggu_keputusan` | `credit_overrides` berstatus `pending` + `credit_profile_requests` berstatus `diajukan` | `kind` (`izin_kredit` · `ubah_profil`), pelanggan, nominal, pengaju, umur (hari), ringkasan | Tertua dulu |
| `ditahan` | `sales_orders` ber-`credit_hold: true` + `credit_gate_rejections` berstatus `terbuka` (bila koleksinya ada — CR-T3) | `kind` (`pesanan_ditahan` · `pesanan_ditolak`), pelanggan, nomor pesanan, nilai, pesan alasan, sejak | Terbaru dulu |
| `jatuh_tempo` | `billing_schedule_service.open_lines` dengan `due_date` ≤ hari ini + 3 hari | Per pelanggan: jumlah baris, total sisa, telat terlama (hari), jatuh tempo terdekat; `lines[]` | Telat terlama dulu |
| `janji_bayar` | `collection_followups` ber-`outcome: promised` 90 hari terakhir | pelanggan, `promise_date`, `promise_amount`, status janji, pencatat | `ingkar` di atas, lalu tanggal janji |
| `kaji_ulang` | `customer_credit_profiles` ber-`limit_valid_until` ≤ hari ini + 14 hari, atau `penalty_rule.valid_until` dalam jendela yang sama | pelanggan, jenis (`plafon` · `bebas_denda`), tanggal berakhir, keadaan (`mendekati` · `lewat`), jumlah penolakan 90 hari | `lewat` di atas |
| `denda` | `penalties` berstatus `draft` | Seperti `list_penalties` | Terbaru dulu |

Berkas baru `backend/services/customer_statement_service.py` —
`async def statement(customer_id, entity_id, date_from, date_to) -> dict`. Rekening koran disusun dari **baris jurnal**
berakun piutang (`known_codes("penjualan.piutang")`) di PT itu yang sumbernya milik pelanggan itu, sehingga saldonya
sama dengan buku besar per tanggal berapa pun (RP-05). Pemetaan sumber → pelanggan ada di satu fungsi
`customer_of_journal(je)`: pengakuan penjualan (lewat pesanan), kas kwitansi (lewat kwitansi), nota kredit, keputusan
selisih bayar, kasus keuangan. Jurnal akun piutang yang tidak terpetakan tidak tampil dan sudah dilaporkan INV-BAL-02.

| Endpoint | Izin | Isi | Jawaban |
|---|---|---|---|
| `GET /api/credit-desk?queue=&page=&page_size=&q=` | `credit_profile.view` | — | `{items, total, page, page_size}`; `queue` tak dikenal → 400 "Antrean tidak dikenal." |
| `GET /api/credit-desk/summary` | `credit_profile.view` | — | `{menunggu_keputusan, ditahan, jatuh_tempo, janji_bayar, kaji_ulang, denda}` (jumlah) |
| `POST /api/customers/{id}/followups` (ada) | tetap | tambah `promise_date`, `promise_amount` | `promised` tanpa tanggal → 400 "Tanggal janji bayar wajib diisi."; tanpa nominal → 400 "Nominal janji bayar wajib lebih dari nol."; tanggal lampau → 400 "Tanggal janji bayar tidak boleh di masa lalu." |
| `GET /api/customers/{id}/statement?entity_id=&from=&to=` | salah satu: `credit_profile.view`, `ar_receipt.view` + `can_access_customer` | `to` bawaan hari ini (WIB); `from` bawaan tanggal 1 bulan `to` | `{customer, entity, from, to, opening_balance, rows[], closing_balance, penalties: {opening_balance, rows[], closing_balance}}` |
| `GET /api/customers/{id}/statement.pdf?…` | sama + `document.print` | sama | PDF berkop PT; `format=html` untuk uji |
| `GET /api/customers/{id}/reminder-text?entity_id=` | `order.view` + `can_collect_customer` | — | `{text}` — naskah siap salin |

Baris `rows[]`: `date`, `doc_type` (`surat_jalan` · `kwitansi` · `nota_kredit` · `penyesuaian`), `doc_number`, `doc_id`,
`description`, `debit` (tagihan), `credit` (pembayaran atau kredit), `balance`, `je_id`. `opening_balance` = Σ debit −
Σ kredit sebelum `from`. Bagian `penalties` memakai akun piutang denda dan tidak menambah saldo utama. PT selalu lewat
`resolve_requested_entity`; mode "Semua PT" ditolak 400 "Pilih satu PT untuk rekening koran."

Naskah pengingat (persis; baris rekening dan kode hanya ada setelah PM-T2):

```text
Yth. {nama pelanggan},
Berikut tagihan {nama PT} yang sudah atau akan jatuh tempo:
- {nomor pesanan} · Rp {sisa} · jatuh tempo {tanggal}
Total: Rp {total}
Mohon konfirmasi pembayarannya. Terima kasih.
```

### Pengaturan

Tidak ada.

### Izin dan peran

Tidak ada pasangan baru. Id menu baru `credit-desk` masuk `nav` modul akses `ar`. Finance melihat semua antrean (memegang
`credit_profile.view`) tanpa tombol putus; tombol putus mengikuti `credit_profile.approve` dan `credit_override.approve`.

### Layar

**Keuangan › Piutang › tab "Kredit & Plafon"** (view `credit-desk`, komponen baru `CreditDeskView.jsx`). Hub Piutang
dibentuk MN-T1; bila saat unit ini dikerjakan hub itu belum ada, buat kunci hub `piutang` di `hubTabs.js` berisi dua
tab — "Saldo & Umur" (`ar-aging`) dan "Kredit & Plafon" — dan catat di laporan agar MN-T1 melengkapinya.

- Banner PT; di mode "Semua PT" antrean hanya-baca berlabel "gabungan, belum dieliminasi" (N3).
- Enam chip antrean berlabel persis: **Menunggu keputusan**, **Ditahan**, **Jatuh tempo**, **Janji bayar**, **Kaji
  ulang**, **Denda** — masing-masing dengan jumlah. Daftar berhalaman dengan jumlah total dan kotak cari.
- Aksi per baris: "Buka kartu pelanggan" (semua); "Setujui" / "Tolak" (menunggu keputusan); "Periksa ulang kredit"
  (ditahan); "Salin pengingat" dan "Catat janji bayar" (jatuh tempo); "Terbitkan" / "Bebaskan" (denda, izin `penalty.*`).
- Kosong: "Tidak ada pekerjaan di antrean ini."; galat tampil di tempat daftar dengan tombol "Coba lagi".
- Tab "Persetujuan Kredit" di CRM menjadi tautan ke tab ini (D8); `CreditOverridesPanel` dipakai ulang di dalamnya.

**Kartu pelanggan** (`Customer360Panel.jsx`, komponen yang sama dibuka dari CRM dan dari Piutang):

- Kotak **Eksposur** menggantikan kotak kredit, baris berlabel persis: "Piutang barang terkirim", "Pesanan belum
  dikirim", "Giro belum cair", "Titipan & saldo kredit", "Eksposur", "Plafon", "Sisa plafon", dan terpisah "Denda belum
  dibayar (tidak mengurangi plafon)". Baris yang dimatikan pengaturan `ar.eksposur_*` ditulis "tidak dihitung" (L6).
- Tab menjadi: "Pesanan", "Dokumen", "Harga Khusus", "Sample", "Penagihan", "Kredit", "Tagihan", "Rekening Koran".
  "Override Kredit" pindah ke dalam tab "Kredit" sebagai bagian "Izin kredit". "Tagihan" = jadwal tagihan (kolom
  seperti rincian umur piutang CR-T2) + nota denda. "Penagihan" menampilkan janji bayar dengan lencana status.
- Tab **Rekening Koran**: isian "Dari", "Sampai", tombol "Tampilkan", "Cetak PDF", "Salin pengingat"; kolom "Tanggal",
  "Dokumen", "Keterangan", "Tagihan", "Pembayaran / Kredit", "Saldo"; baris pertama "Saldo awal", terakhir "Saldo
  akhir"; nomor dokumen membuka dokumen dan jurnalnya (L8); bagian kedua "Denda".
- Form tindak lanjut: saat hasil "Dijanjikan bayar" muncul isian wajib "Tanggal janji" dan "Nominal janji".

## Uji penerimaan

Fixture **R1** (`ent_kanda`, pelanggan P, jurnal disisipkan): 1 Okt 2026 surat jalan SJ-1 Dr piutang Rp 400.000;
15 Okt kwitansi Cr piutang Rp 400.000; 20 Okt SJ-2 Dr Rp 600.000; 25 Okt nota kredit Cr Rp 100.000; 5 Nov kwitansi
Cr Rp 500.000.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | R1 | `GET …/{P}/statement?entity_id=ent_kanda&from=2026-10-01&to=2026-10-31` (dijalankan setelah 5 Nov) | `opening_balance` 0; saldo berjalan 400.000 → 0 → 600.000 → 500.000; `closing_balance` 500.000 = Σ jurnal akun piutang P ≤ 31 Okt (400.000 + 600.000 − 400.000 − 100.000) |
| U2 | B | R1 | Sama, `from=2026-11-01&to=2026-11-30` | `opening_balance` 500.000; satu baris kwitansi 500.000; `closing_balance` 0 |
| U3 | B | R1 | Sama untuk `entity_id=ent_ksc`; lalu dengan konteks "Semua PT" | Kosong bersaldo 0 — PT lain tidak tercampur; 400 "Pilih satu PT…" |
| U4 | B | R1 | `GET …/statement.pdf?format=html&from=2026-10-01&to=2026-10-31` | Memuat "Rekening Koran Pelanggan", nama PT, "Saldo akhir", dan "500.000" |
| U5 | B | — | `POST …/{P}/followups` `outcome: "promised"` tanpa `promise_date`; lalu dengan tanggal lampau | 400; 400; tidak ada catatan |
| U6 | B | Janji Rp 500.000 untuk 10 Nov 2026 dicatat 6 Nov | Antrean `janji_bayar` pada tanggal uji 8 Nov; 12 Nov tanpa kwitansi; 12 Nov dengan kwitansi Rp 500.000 bertanggal 9 Nov | `menunggu`; `ingkar` di urutan pertama; `ditepati` |
| U7 | B | Satu izin kredit `pending` dan satu pengajuan profil `diajukan` di `ent_kanda` | `GET /api/credit-desk?queue=menunggu_keputusan` | 2 baris ber-`kind` berbeda; `total == 2` |
| U8 | B | Pesanan ber-`credit_hold: true` | Antrean `ditahan` | 1 baris `pesanan_ditahan` dengan pesan alasan |
| U9 | B | Baris tagihan P jatuh tempo hari ini + 2, hari ini + 5, hari ini − 10 | Antrean `jatuh_tempo` | Satu baris pelanggan P memuat 2 tagihan (yang + 5 hari tidak ikut); telat terlama 10 |
| U10 | B | Tiga profil: plafon berakhir hari ini + 10, hari ini − 1, hari ini + 40 | Antrean `kaji_ulang` | 2 baris: `lewat` di atas, lalu `mendekati` |
| U11 | B | U7–U10 | `GET /api/credit-desk/summary` | Angka tiap antrean = `total` antrean itu |
| U12 | B | U7 | Kepala `X-Entity-Id: ent_ksc` | `menunggu_keputusan` kosong — PT lain tidak melihat |
| U13 | B | `sls` pemilik pelanggan P saja; pengajuan untuk P dan untuk pelanggan lain | `sls`: antrean `menunggu_keputusan` | Hanya baris P |
| U14 | B | peran uji baku | **Tanpa Acuan** + `credit_profile.view`: `GET /api/credit-desk?queue=denda`; **Manajer Kosong**; **Sopir** | 200; 403; 403 |
| U15 | B | U9 | `GET …/{P}/reminder-text` | Naskah persis seperti templat, dua baris tagihan, total = jumlah keduanya |
| U16 | layar (uji jalan) | Data acuan | Finance membuka Piutang › Kredit & Plafon, lalu kartu pelanggan › Rekening Koran › Cetak PDF | Enam chip berjumlah; tidak ada tombol "Setujui" untuk Finance; PDF terunduh dengan saldo yang sama dengan layar |

## Langkah kerja

1. `backend/tests_mem/test_CRT5_meja_kredit.py`: U1–U15; merah.
2. `customer_statement_service` + endpoint + PDF. U1–U4 hijau.
3. Janji bayar (skema, validasi, status hitung). U5, U6 hijau.
4. `credit_desk_service` + endpoint + naskah pengingat. U7–U15 hijau.
5. Tab, kartu pelanggan, `nav` modul; U16; `verify_page_tabs` dan `audit_i18n_id` tidak bertambah merah; gate; laporan.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`collection_followups`), `CODEBASE_MAP.md` (dua layanan baru, `CreditDeskView.jsx`),
`memory/PRD.md`, `docs/KN_13_NAVIGATION_MAP.md` (tab baru), `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("rekening koran",
"janji bayar", "kaji ulang").

## Di luar lingkup

- Pengiriman pengingat otomatis ke pelanggan (WhatsApp terjadwal): menyusul; unit ini hanya naskah siap salin.
- Susunan penuh enam tab hub Piutang dan pemindahan Rencana Bayar, Uang Muka, Saldo Kredit, Kasus → MN-T1, MN-T2.
- Satu form pembayaran dari kartu pelanggan → MN-T3. Instruksi bayar dan kode bayar di naskah → PM-T2.

## Asumsi dan risiko

- `ASUMSI:` jendela antrean "Jatuh tempo" = H-3 (sama dengan pengingat yang ada) dan "Kaji ulang" = 14 hari sebelum
  tanggal berakhir. Keduanya parameter fungsi, bukan aturan bisnis yang menahan sesuatu.
- `ASUMSI:` "pelanggan yang sering lewat plafon" ditampilkan sebagai kolom jumlah penolakan 90 hari, tanpa ambang.
- `ASUMSI:` janji bayar dinilai terhadap seluruh kwitansi pelanggan di PT itu, tidak per pesanan.
- `RISIKO:` rekening koran dari jurnal tidak memuat uang muka sebelum barang dikirim (belum menjadi pengurang piutang
  di buku besar). Layar menulis catatan "Titipan dan uang muka ada di kotak Eksposur." Membatalkan: sembunyikan tab;
  tidak ada data yang ditulis unit ini selain dua field janji bayar.
