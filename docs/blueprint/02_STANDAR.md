# Standar lintas-unit

Setiap unit merujuk bagian di sini alih-alih mengulangnya. Bila sebuah unit bertentangan dengan standar, unit yang
menang **hanya** bila ia menulis "menyimpang dari standar §x karena …"; selain itu standar yang menang.

Asal standar: 139 temuan audit keuangan, 48 temuan riset modul, dan audit konfigurasi & peran 13 Nov 2026
(`docs/audit/konfigurasi-peran-2026-11-13/`). Tiap aturan menyebut temuan yang melahirkannya, supaya jelas untuk apa.

---

## §1 Kontrak posting — setiap aksi yang berakibat jurnal

```text
1. PERIKSA   izin · entitas · status dokumen · periode terbuka untuk SEMUA entitas dan tanggal yang terlibat
             · akun aktif · sisa/saldo cukup                         → gagal di sini = tidak ada tulisan apa pun
2. NIAT      simpan dokumen/niat berstatus `pending` dengan id tetap (dari kunci idempotensi atau dokumen induk)
3. EFEK      ubah buku pembantu (piutang, hutang, kas, stok) dengan operasi bersyarat nilai lama;
             id turunan (kas, alokasi) diturunkan dari id niat
4. JURNAL    lewat satu pintu tahan-gagal; hasilnya ditulis ke `gl_status` dokumen: posted | failed
5. SELESAI   niat → `done`
ULANG        panggilan ulang dengan id yang sama meneruskan dari langkah terakhir yang tercatat
```

| # | Aturan | Menutup |
|---|---|---|
| P1 | Jurnal hanya lewat `backend/services/gl_service.py` dan satu pintu tahan-gagal (`post_cash_durable` untuk kas; pembantu sejenis untuk jenis lain setelah PK-18). Tidak ada sisipan langsung ke `journal_entries` | GL-02, GL-03 |
| P2 | Periode diperiksa dengan `preflight_posting(entity_id, tanggal_dokumen)` di langkah 1, untuk tiap entitas | SL-01, IC-01, FY-01 |
| P3 | Tiap jenis dokumen yang menjurnal punya `gl_status` dan terdaftar di `routers/posting_failures.py` `SOURCES` dengan jalur ulang | GL-02, IV-04 |
| P4 | `source_type` + `source_id` jurnal unik **per kejadian** bila dokumen bisa dibayar/diubah lebih dari sekali | FX-02, SL-03 |
| P5 | Kas hanya dibuat lewat satu pembuat; rekening wajib; entitas dari dokumen | SL-11, SL-07 |
| P6 | Dua jurnal di dua PT hanya lewat pembantu jurnal kembar (lahir di PK-06) | IC-01, FY-04 |
| P7 | Pembalikan lewat satu mekanisme yang menandai jurnal asal | GL-01 |
| P8 | Jurnal periodik bertanggal akhir periodenya (K-13) | FY-02 |
| P9 | Akun diambil dari pemetaan akun per entitas (`services/gl_mapping_service.py`), tidak ditulis mati | IV-05, FY-13 |
| P10 | Modul baru tidak menjurnal ke akun kontrol kecuali ia pemilik buku pembantunya | IC-06 |

Uji wajib untuk tiap aksi posting: gagal di tiap langkah (periode tertutup; akun nonaktif; jurnal dipaksa gagal) →
diulang → hasil tunggal (satu dokumen, satu kas, satu jurnal).

---

## §2 Pengaturan — setiap nilai yang bersifat aturan bisnis

**Aturan dasar:** angka, ambang, hari, persen, daftar pilihan, dan sakelar yang menentukan perilaku bisnis **tidak
ditulis di kode**. Ia didaftarkan di registry Pusat Pengaturan dan dibaca dari sana.

### 2.1 Mendaftarkan kunci

Di `backend/config_catalog_<domain>.py` memakai `E(...)` dari `backend/config_registry.py`:

| Field | Aturan |
|---|---|
| `key` | `<domain>.<nama_snake_case>`; domain yang sudah ada dipakai ulang (`ar`, `payment`, `tax`, `hr`, `approval`, `periode`, …) |
| `group` | Salah satu id di `config_registry.GROUPS`; jangan membuat grup baru tanpa unit yang memintanya. Id kelompok lama diterima lewat `GROUP_ALIASES` (KF-T4) |
| `section` | **Wajib** (KF-T4): sub-judul yang terdaftar di `sections` kelompoknya; sub-judul biasa paling banyak 14 kunci, bagian teknis memakai sub-judul `advanced` ("Lanjutan (teknis)") |
| `type` | `bool` · `int` · `pct` · `money` · `decimal` · `enum` · `text` · `list` · `table` · `duration` |
| `items`, `ordered` | Untuk `list` (KF-T4): `options` (butir dari `options`) · `roles` (id peran yang dikenal) · `int_asc` (bulat > 0 menaik) · `text`; `ordered=True` = urutan bermakna. Server menolak butir tak sah/kembar; layar memakai centang/geser/baris, bukan kotak berkoma |
| `ref` | Untuk `text` yang merujuk master (KF-T4): `payment_term` · `uom` · `department` — layar menampilkan daftar pilih, server menolak nilai di luar daftar. Teks lain berformat: `value_format` `regex`, `json_map`, `date`, `multiline` |
| `default` | **Perilaku yang berjalan hari ini.** Untuk aturan baru: yang paling tidak membatasi (`00` §4.1) |
| `min`, `max`, `unit` | Wajib untuk tipe angka |
| `scopes` | `("global", "entity")` sebagai bawaan. Lapisan `customer`/`product` hanya bila layar pengaturnya ada (unit KF-T5) |
| `label` | Bahasa Indonesia, ≤ 45 karakter, tanpa istilah teknis, berbentuk pernyataan yang jelas arahnya ("Tahan pesanan bila telat lebih dari (hari)"); istilah glosarium `KN_32` §9.3 |
| `help` | 1–2 kalimat: apa yang diatur, untuk siapa. Sebut arti nilai khusus ("0 = tanpa batas"); kunci angka yang boleh 0 **wajib** menyebut akibat nyata nilai 0 |
| `impact` | Apa yang berubah bagi pengguna bila nilainya diubah |
| `example` | Contoh dengan angka |
| `risk`, `requires_reason` | `high` + `True` untuk yang mengubah uang, pajak, atau wewenang |
| `consumers` | `berkas.py:fungsi` yang **benar-benar** membaca kunci; fungsi harus ada |
| `permission` | Izin domain yang boleh mengubah, mis. `("accounting", "configure")`. **Jangan** memakai `roles=` atau mengandalkan `owner_role` (KF-01, KF-02) |
| `edit_at` | Opsional (KF-T4): `{view, preset, label}` bila kunci diubah di layar lain (kartu tanpa editor, mis. `receiving.mode`, `kontrol.*`) |

Penjaga `scripts/guardrails/verify_config_text.py` (INV-CFG-TXT, gate statik) menolak label > 45 huruf, label kembar,
kata teknis/id/kode HTTP/kode keputusan, kunci angka tanpa satuan, arti 0 yang tidak tertulis, istilah di luar glosarium,
dan sub-judul tak terdaftar/terlalu besar — hasil wajib 0 pelanggaran.

### 2.2 Membaca kunci

```python
from services.config_resolver import value_of
hari = await value_of("ar.overdue_block_days", {"entity_id": entity_id})
```

- Selalu dengan `entity_id` dokumen yang sedang diproses. Lapisan pelanggan/produk: sertakan `customer_id`/`product_id`.
- **Tidak ada nilai cadangan yang berbeda dari registry.** Bila perlu cadangan saat galat, ambil
  `config_registry.require(key)["default"]` (KF-06).
- Tidak membaca `system_settings` langsung dan tidak menambah kunci ke `DEFAULT_GLOBAL_SETTINGS`.
- Bila sebuah master menimpa pengaturan (mis. PT non-PKP memaksa tarif PPN 0), penimpaan itu didaftarkan sehingga layar
  bisa menampilkannya (KF-04).

### 2.3 Kontrol "harus dua orang"

Keputusan pemilik 13 Nov 2026: bisa diatur, bawaan **satu orang**.

| Kunci (per aksi) | Tipe | Bawaan | Arti |
|---|---|---|---|
| `kontrol.<aksi>.min_orang` | `enum` 1 · 2 | 1 | 1 = pelaku boleh menyelesaikan sendiri; 2 = pengaju ≠ penyetuju |
| `kontrol.<aksi>.batas_nominal` | `money` | 0 | Di atas nilai ini selalu dua orang walau `min_orang` = 1. 0 = tidak dipakai |

- Satu pembantu: `services/dual_control.py` → `await butuh_orang_kedua(aksi, entity_id, nominal)` dan
  `await tolak_bila_pelaku_sama(aksi, dokumen, aktor, entity_id)`. Lahir di unit KF-T6; unit lain memakainya.
- Nilai awal tiap aksi mengikuti `01_KEPUTUSAN.md` (jawaban pemilik butir 2): aksi yang hari ini sudah melarang
  setuju-sendiri mulai dengan 2; buka periode dan semua aksi lain mulai dengan 1.
- Pengecualian Admin yang berjalan hari ini (Admin boleh menyetujui dokumennya sendiri, dicatat di jejak) dijadikan
  pengaturan `kontrol.admin_boleh_sendiri` (`bool`, bawaan ya = perilaku hari ini).
- Aksi yang sudah punya sakelar sendiri (`approval.matrix_sod`, `amendment.dual_control`) dipindahkan ke keluarga
  `kontrol.*` dengan nilai yang sedang berlaku; sakelar lama menjadi alias sampai dihapus.

### 2.4 Uji wajib untuk kunci baru

1. Putaran `t1_config.py` untuk kunci itu lulus (tulis global → terbaca; lapisan PT → hanya PT itu; nilai tak sah → 400).
2. Uji perilaku: nilai A menghasilkan perilaku A, nilai B menghasilkan perilaku B, PT lain tidak ikut berubah.
3. `scripts/audit_config_wiring.py` tidak menambah baris merah.

---

## §3 Izin dan peran

Hasil uji jalan 13 Nov 2026 menunjukkan matriks izin ditegakkan konsisten di 786 rute baca × 16 peran, **kecuali** di
tempat wewenang ditentukan lewat nama peran. Standar ini menutup pintu itu.

### 3.1 Wewenang hanya dari izin

| # | Aturan | Menutup |
|---|---|---|
| Z1 | Setiap endpoint memanggil `require_permission(request, "<sumber_daya>", "<aksi>")` (atau `require_any_permission`) sebagai pernyataan pertama handler | PR-03, PR-04 |
| Z2 | Dilarang di kode baru: `require_role`, `role_in(...)`, `.get("role") == …`, `role_satisfies` untuk memutuskan boleh/tidak. Di layar: `roleIs(...)` dan perbandingan `role`. Pakai `can(perms, sumber_daya, aksi)` dari `frontend/src/config/roles.js` | PR-01, PR-03 |
| Z3 | Endpoint yang hanya butuh login harus termasuk salah satu: milik sendiri (jalur berakhir `/me` atau memfilter `user_id` aktor), data rujukan tanpa nominal (wilayah, enum), atau infrastruktur sesi. Selain itu wajib berizin | PR-04, IA-03 |
| Z4 | Wewenang menyetujui = izin `<sumber_daya>.approve` + batas nominal peran (unit KP-T4), bukan peringkat peran acuan | PR-05 |
| Z5 | Cakupan data ("hanya miliknya" / "timnya" / "semua") dibaca dari sifat peran `data_scope` (unit PR-T4), bukan dari `role_in(..., ("sales",))` | PR-01 |
| Z6 | Pesan 403 untuk manusia: "Anda belum punya akses untuk <aksi dalam bahasa sehari-hari>. Minta Admin menambahkan akses '<nama modul>'." Tidak menampilkan `x.y` maupun id peran | PR-09 |

### 3.2 Menambah izin baru

Satu izin baru berarti empat tempat, dalam commit yang sama:

1. `backend/permissions_config.py` → `DEFAULT_PERMISSIONS`: peran `admin` + peran bawaan yang memang berhak.
2. `backend/access_modules.py` → `MODULE_CATALOG`: sumber daya masuk tepat satu modul; id menu yang dibukanya masuk `nav`.
3. Endpoint yang memeriksanya (Z1) dan tombol layar yang memakainya (`can(...)`).
4. Uji: peran kustom **tanpa peran acuan** yang diberi izin itu → 200; peran kustom beracuan Manajer dengan semua modul
   "Tidak ada" → 403.

Kosakata aksi: `view` · `create` · `update` · `delete` · `approve` · `reject` · `post` · `pay` · `void` · `export` ·
`configure` · `release`. Aksi lain hanya bila tidak ada yang cocok, dan diberi label Indonesia di katalog modul.

Izin yang didefinisikan harus diperiksa server. Izin yang hanya dipakai layar, atau tidak dipakai sama sekali, tidak
boleh ada (41 izin demikian dibersihkan di unit PR-T5).

### 3.3 Menjaga agar hak tidak bisa dinaikkan sendiri

| # | Aturan | Menutup |
|---|---|---|
| E1 | Pengguna tidak bisa memberi, membuat, atau mengubah akun ke peran yang izinnya **melebihi** izin miliknya; peran `admin` hanya bisa diberikan oleh `admin` | PR-02 |
| E2 | Pengguna tidak bisa mereset sandi, mencabut sesi, atau mengubah akun yang perannya berizin lebih luas dari miliknya | PR-02 |
| E3 | Pengguna tidak bisa mengubah peran yang izinnya lebih luas dari miliknya, dan tidak bisa membuat peran dengan izin yang ia sendiri tidak punya | PR-02 |
| E4 | Mengubah peran sendiri tetap dilarang (sudah berjalan) | — |

"Lebih luas" = ada pasangan (sumber daya, aksi) yang dimiliki sasaran dan tidak dimiliki pelaku.

### 3.4 Entitas dan idempotensi (dari audit keuangan)

| # | Aturan | Menutup |
|---|---|---|
| N1 | Entitas tidak pernah diambil dari isi permintaan: `resolve_requested_entity(ctx, …)` (`backend/entity_scope.py:622`); untuk dokumen ber-id, entitas = entitas dokumen, lalu diadu dengan cakupan pengguna (`guard_doc`) | IC-05, FX-08, TX-03 |
| N2 | Setiap id dari klien dibuktikan milik entitas dan dokumen induk yang sama | FX-05 |
| N3 | Mode "Semua Entitas" hanya baca; angka lintas PT diberi keterangan sudah/belum dieliminasi | RC-01 |
| N4 | Setiap POST/PATCH berakibat uang: awalannya ada di `IDEMPOTENT_PREFIXES` (`backend/idempotency.py`) dan layarnya mengirim kunci (`frontend/src/hooks/useIntentKey.js`) serta menahan klik ganda | UX-01, UX-02 |
| N5 | Aksi uang di layar meminta konfirmasi yang menyebut nominal dan PT; pembatalan meminta alasan | UX-03 |

---

## §4 Layar dan bahasa

Rujukan yang sudah ada dan tetap berlaku: `docs/KN_08_UI_UX_STANDARDS.md`, `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md`,
`docs/KN_37_STANDAR_UI_GUDANG.md`. Tambahan dari audit:

| # | Aturan |
|---|---|
| L1 | Semua teks antarmuka berbahasa Indonesia sehari-hari. Kata yang dilarang tampil ke pengguna: id teknis (`ent_…`, `cr_…`, `x.y`), nama field, "scope", "override", "threshold", "fallback", "payload", "posting" tanpa penjelasan. Penjaga `scripts/audit_i18n_id.py` tidak boleh bertambah merah |
| L2 | Satu istilah untuk satu hal, mengikuti glosarium: **PT** (bukan entitas/badan usaha, kecuali di layar hukum), **pelanggan**, **pemasok**, **persetujuan**, **pengaturan**, **peran**, **izin** |
| L3 | Layar baru masuk sebagai **tab di hub yang ada**. Paling banyak enam tab per hub; tidak ada tab tingkat ketiga; tidak ada dasbor atau antrean baru (`rencana/01` §5) |
| L4 | Setiap layar uang: banner PT; tombol buat mati dengan petunjuk saat "Semua PT"; status memuat / galat / kosong dibedakan; daftar berhalaman dengan jumlah total; angka rupiah berpemisah ribuan; tanggal WIB |
| L5 | Setiap pengaturan atau izin yang tampil harus berefek. Yang tidak berefek dihapus atau diberi tanda "belum dipakai" beserta alasannya |
| L6 | Layar menampilkan nilai yang **dipakai mesin**. Bila nilai ditimpa aturan lain, tulis siapa yang menimpa |
| L7 | Form buat/ubah memakai pop-up baku (penjaga `scripts/audit_create_modal.py`), tab memakai `components/PageTabs` (penjaga `verify_page_tabs`) |
| L8 | Dari dokumen bisa membuka jurnalnya dan sebaliknya; angka di laporan bisa ditelusuri sampai dokumen |

---

## §5 Data dan angka

| # | Aturan | Menutup |
|---|---|---|
| D1 | Satu angka satu pemilik. Sebelum menambah field/koleksi, cari di `ENTITY_REGISTRY.md` dan peta sumber-kebenaran (audit keuangan §2.2) | Duplikasi §4 |
| D2 | Angka turunan yang disimpan wajib punya pembangun ulang dan satu invarian di `scripts/verify_data_integrity.py` | RP-01, RP-03 |
| D3 | Keputusan manusia atas angka disimpan bersama potret angka dasarnya; potret tidak dihitung ulang | KM-05 |
| D4 | Daftar tidak dipotong diam-diam: `to_list(n)` hanya dengan halaman atau saringan di kueri | RP-01, GL-13 |
| D5 | Uang dibulatkan di satu fungsi; perbandingan dalam satuan bulat; total = Σ baris | GL-07 |
| D6 | Tanggal buku dan batas periode WIB dari satu fungsi | GL-05 |
| D7 | Keunikan dijamin indeks unik yang terdaftar wajib-ada | GL-09 |
| D8 | Jalur lama dimatikan di unit yang melahirkan jalur baru, atau diberi tanggal mati | SL-05 |
| D9 | Koleksi baru dicatat di `ENTITY_REGISTRY.md` dan dikenali `scripts/verify_contract.py` | — |

---

## §6 Uji

| Lapis | Tempat | Dijalankan |
|---|---|---|
| HTTP di database tiruan (lingkungan B) | `backend/tests_mem/test_<ID>_<ringkas>.py`, dengan `conftest.py` yang mengimpor `boot_app` dan menyalakan `server.lifespan` | `python -m pytest backend/tests_mem -n 0` |
| HTTP di MongoDB asli (lingkungan A) | `backend/tests/test_bp_<ID>_<ringkas>.py`, mengikuti pola berkas uji yang ada (`requests` ke `REACT_APP_BACKEND_URL`) | di container backend |
| Layar | Uji komponen di samping komponennya; uji jalan dengan tangkapan layar di laporan | container frontend / peramban |

- `backend/tests_mem/` lahir di PK-02. Folder ini terpisah dari `backend/tests/` karena `backend/tests/conftest.py`
  membutuhkan MongoDB asli pada setiap tes.
- Nama tes menyebut ID uji dari tabel "Uji penerimaan" unit: `test_PK05_U3_dua_bayar_bersamaan_satu_pembayaran`.
- Angka harapan berasal dari hitungan tangan yang ditulis sebagai komentar di tes (masukan → langkah → hasil).
- Fixture yang disisipkan langsung ke database dicatat sebagai fixture; alur yang dijalankan lewat API dicatat sebagai
  alur. Keduanya bernilai bukti berbeda.
- Tiga peran uji baku untuk unit izin (dibuat lewat `POST /api/access/roles` di fixture):
  **Tanpa Acuan** (tanpa peran acuan; hanya izin yang diuji), **Manajer Kosong** (acuan Manajer; semua modul "Tidak
  ada"), **Sopir** (peran bawaan berizin paling sempit).

---

## §7 Dokumen yang ikut berubah

Di commit yang sama dengan kodenya, bila tersentuh: `CODEBASE_MAP.md` (modul/berkas baru), `ENTITY_REGISTRY.md` (koleksi/
field baru), `memory/PRD.md` (fitur baru), `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` (istilah baru),
`docs/KN_13_NAVIGATION_MAP.md` (menu berubah). Dokumen `KN_13`, `KN_14`, `KN_16` saat ini basi untuk keuangan; unit
MN-T1 memperbaruinya.
