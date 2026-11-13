# Lingkungan dan cara menguji

Dibaca agen pelaksana sebelum unit pertama. Semua perintah di sini sudah pernah dijalankan pada `dca195b`, kecuali
yang ditandai "belum dijalankan di sesi perancangan".

## 1. Dua lingkungan

| Lingkungan | Dipakai untuk | Cara menyalakan | Batas |
|---|---|---|---|
| **A. Docker dev** (resmi) | Semua uji yang butuh MongoDB asli: indeks unik, dua permintaan bersamaan, gate penuh, uji layar | `docker compose -f docker-compose.dev.yml up -d` lalu `bash scripts/dev_restore_demo.sh` (lihat `docs/LOCAL_DEV.md`) | Butuh Docker; data acuan ±5 menit |
| **B. Aplikasi utuh di database tiruan** | Uji cepat tingkat HTTP tanpa Docker: izin, entitas, isi jawaban, urutan tulis | Impor `docs/audit/konfigurasi-peran-2026-11-13/bukti/boot_app.py` lalu jalankan `server.lifespan` (contoh di §3) | Tidak menguji indeks unik, balapan, transaksi; data hanya seed awal (4 akun, 3 PT) |

Aturan pemakaian: butir uji yang menyebut "bersamaan", "indeks", "ditolak oleh database", atau "uji jalan layar" hanya
sah di lingkungan A. Butir lain boleh di B, dan sebaiknya di B dulu karena satu putaran hanya beberapa detik.

Path lama `/app/...` di skrip repo berasal dari lingkungan sebelumnya. Di container backend repo memang berada di `/app`.
Di luar container, buat tautan `ln -s <root-repo> /app` sebelum menjalankan skrip di `scripts/`.

## 2. Lingkungan A — perintah baku

```bash
docker compose -f docker-compose.dev.yml up -d
bash scripts/dev_restore_demo.sh                                   # data acuan; MENGHAPUS isi DB lokal
docker compose -f docker-compose.dev.yml exec backend bash          # di dalamnya repo = /app
```

Di dalam container backend:

```bash
bash scripts/gate.sh --quick      # gate statik (tanpa DB), ±3 menit berurutan
bash scripts/gate.sh              # statik + seed + invarian + runtime
python scripts/verify_data_integrity.py            # 229 invarian data
python -m pytest tests/<berkas>.py -n 0             # satu berkas uji, berurutan
```

- Uji `backend/tests/` adalah uji HTTP terhadap backend yang sedang berjalan; alamatnya dari `REACT_APP_BACKEND_URL`.
- `backend/pytest.ini` memasang `-n 2 --dist loadscope`; **jangan diubah**. Untuk berurutan pakai `-n 0`.
- Login uji: `admin@kainnusantara.id` / `demo12345`; semua akun seed bersandi sama.
- Jangan menjalankan dua gate atau dua POC bersamaan (sebagian mengubah pengaturan global sementara).

## 3. Lingkungan B — aplikasi utuh di database tiruan

Persiapan sekali (Python 3.11):

```bash
python3.11 -m venv /tmp/venv-kn && . /tmp/venv-kn/bin/activate
grep -v -i "emergent\|litellm" backend/requirements.txt > /tmp/req.txt      # dua paket itu dari host privat
pip install -r /tmp/req.txt mongomock-motor==0.0.36
```

**Untuk tes unit blueprint pakai kerangka `backend/tests_mem/` (unit PK-02)**: fixture `aplikasi`, `klien`, `akun`, `sesi`,
tiga peran uji, `paksa_jurnal_gagal`, dan pembantu `pt_uji`, `jurnal`, `tutup_periode`, `saldo_akun`. Kontraknya di
[`backend/tests_mem/README.md`](../../backend/tests_mem/README.md). Jalankan `python -m pytest backend/tests_mem -n 0`.
Pola di bawah ini untuk skrip lepas (seperti bukti audit), bukan untuk tes unit.

Pola satu uji (skrip lepas):

```python
import boot_app, asyncio, datetime, httpx, server      # boot_app HARUS diimpor paling dulu
from db import db

async def main():
    async with server.lifespan(server.app):             # bootstrap + seed + muat registry peran
        admin = await db.users.find_one({"email": "admin@kainnusantara.id"})
        await db.sessions.insert_one({"token": "tok_admin", "user_id": admin["id"],
            "expires_at": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)})
        tr = httpx.ASGITransport(app=server.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=tr, base_url="http://uji") as c:
            r = await c.get("/api/config/registry",
                            headers={"Authorization": "Bearer tok_admin", "X-Entity-Id": "ent_ksc"})
            assert r.status_code == 200
asyncio.run(main())
```

Hal yang perlu diketahui:

- Sesi dibuat dengan menyisipkan dokumen ke `sessions` (login lewat API juga bisa, tetapi sandi seed acak kecuali
  `KN_DEMO_DATA=true`).
- Isi permintaan divalidasi **sebelum** gerbang izin di dalam handler dijalankan. Permintaan tulis dengan isi kosong
  menghasilkan 422, bukan 403 — untuk menguji izin pada endpoint tulis, kirim isi yang sah bentuknya. Fungsi
  `isi_dan_query(path, method)` di `t9_tulis_tanpa_izin.py` membuat isi itu otomatis dari skema dan boleh dipakai ulang.
- PT seed: `ent_ksc` (PKP), `ent_kanda` (non-PKP), dan satu PT ketiga. Akun seed: admin, manager, sales, warehouse.
- Tiap proses mulai dari database kosong; tidak ada yang tersisa di antara dua kali jalan.
- Label alasan baku (`amendment_reasons`) tidak ikut seed awal: panggil `services.amendment_service.ensure_reasons()`
  di fixture bila alurnya membutuhkan label alasan.
- **Klaim atomik sudah ditambal.** Database tiruan mengembalikan `None` untuk `find_one_and_update(...,
  return_document=AFTER)` bila pembaruan membuat saringan tidak cocok lagi — persis pola `services/atomic_claim.claim`
  (kunci belum ada → diisi). `boot_app.py` menambal perilaku itu supaya sama dengan MongoDB asli, sehingga alur ber-klaim
  (penyelesaian kasus keuangan, bayar kontrabon, dan lain-lain) bisa diuji lewat API di lingkungan B. Tanpa mengimpor
  `boot_app`, alur itu selalu gagal dengan "sedang/baru saja diselesaikan proses lain".

Skrip siap pakai di `docs/audit/konfigurasi-peran-2026-11-13/bukti/`:

| Skrip | Isi | Lama |
|---|---|---|
| `inv_endpoints.py <keluaran.json>` | Inventaris statik 1.749 endpoint beserta jenis gerbangnya | ±12 dtk |
| `t1_config.py <keluaran.json>` | Tiap kunci Pusat Pengaturan: tulis → baca lewat 3 jalur → lapisan PT → nilai tak sah → pulihkan | ±1 mnt |
| `t2_roles.py <keluaran.json> <inventaris.json>` lalu `t2_analyze.py <folder>` | 16 peran (termasuk 4 peran kustom uji) × 786 rute GET, dibandingkan dengan matriks izin | ±12 mnt |
| `t3_escalation.py`, `t3b_eskalasi_akun.py` | Siapa bisa mengubah pengaturan; peran kustom menaikkan haknya sendiri | ±10 dtk |
| `t4_peran_bawaan.py`, `t5_jadwal_pengaturan.py` | Izin peran bawaan setelah proses awal diulang; pindah-massal akun Admin; perubahan pengaturan berjadwal | ±10 dtk |
| `t6_fx01_setoran_ganda.py` | Temuan FX-01 lewat API: setoran karyawan pada kasus keuangan | ±5 dtk |
| `t7_tx01_faktur_pengganti.py` | Temuan TX-01 lewat API: rekap PPN setelah faktur pajak diganti | ±5 dtk |
| `t8_cr01_plafon_oleh_sales.py` | Temuan CR-01 lewat API: Sales mengubah plafon dan status blokir pelanggannya | ±5 dtk |
| `t9_tulis_tanpa_izin.py <keluaran.json> <inventaris.json>` lalu `t9_analyze.py <keluaran.json>` | 962 rute tulis × 3 akun tanpa izin; isi permintaan dibuat otomatis dari skema OpenAPI | ±30 dtk |
| `t10_setuju_tanpa_izin.py` | Persetujuan PO dan tagihan pemasok oleh peran tanpa izin; persetujuan PO lintas PT | ±5 dtk |
| `fe_be_routes.py <inventaris.json>` | Tiap panggilan API di layar punya rute dengan metode yang sama | ±5 dtk |

Skrip-skrip ini adalah bahan baku tes regresi untuk unit `KF-*` dan `PR-*`: tiap unit menyebut skrip mana yang harus
berubah hasilnya.

## 4. Garis dasar gate statik (`bash scripts/gate.sh --quick`, 13 Nov 2026, `dca195b`)

Dijalankan di luar Docker dengan tautan `/app` dan tanpa MongoDB. Gate yang butuh database dicatat "tidak dinilai".

| Gate | Hasil | Isi singkat |
|---|---|---|
| `guard:auth_coverage` (INV-AUTH-01) | MERAH | 28 endpoint dilaporkan tanpa penegak auth yang dikenali (sebagian besar `handheld.py` yang memakai kunci perangkat; juga `design_gallery` submit/approve/reject, `ai_assist` actions) |
| `guard:atomic_claim` (INV-ATOMIC-01) | MERAH | 97 endpoint tulis multi-koleksi belum ditinjau + 5 ketidakcocokan (temuan audit DB-01) |
| `config_wiring` (INV-CFG-01/04) | MERAH | 7 kunci mati (positif palsu: `returns.grade_price_factors.*` dibaca mesin tetapi belum beregistry — dibereskan KF-T2), 2 kunci tanpa layar, 2 editor ganda |
| `audit_i18n_id` | MERAH | 113 teks antarmuka belum berbahasa Indonesia di 66 berkas |
| `guard:create_modal` (INV-UI-05) | MERAH | 4 form buat masih sebaris; 2 tombol mati, termasuk `gl-reverse-submit` di `JournalDetailModal.jsx:109` |
| `guard:warehouse_scope` | MERAH | 8 endpoint tulis memilih gudang tanpa pagar badan usaha |
| `guard:to_list_bound` (INV-PERF-01) | MERAH | 3 `to_list(50000)`; 3 entri daftar-izin basi |
| `guard:ref_unlink` (INV-REF-04) | MERAH | 3 penghapusan dokumen tanpa menyapu tautan balik (`routers/cash.py:178`, `amendment_service.py:774`, `ar_receipt_service.py:502`) |
| `guard:numeric_bounds` (INV-NUM-01) | MERAH | 3 isian tanpa batas di `SoOverrideLineIn` |
| `guard:entity_label` (INV-UI-02) | MERAH | 2 tempat mencetak id badan usaha mentah |
| `guard:page_tabs` (INV-UI-12) | MERAH | 1 berkas baru memakai tab buatan sendiri |
| `ux_audit --strict`, `validate_compliance` | MERAH | Rincian belum dibaca |
| `audit_entity_isolation` self-test | tidak dinilai | Butuh MongoDB |
| Gate statik lain (±90 baris ✓) | HIJAU | — |

Arti untuk pelaksana: **garis dasar repo saat ini merah.** Unit PK-01 mengulang pengukuran ini di lingkungan A dan
menyimpannya; sejak itu aturannya "tidak boleh lebih merah". Unit tertentu ditugasi menghijaukan gate tertentu (lihat
kolom "Gate" di `STATUS.md`).

### 4.1 Garis dasar lingkungan A (PK-01)

Diukur 13–14 Nov 2026 pada `fb6bc75` dengan MongoDB 7 asli (kontainer `mongo:7`) dan backend dijalankan di host
(Python 3.11, `uvicorn server:app`), setara lingkungan A tanpa kontainer backend. Keluaran mentah dan kuitansi:
`docs/reviews/2026-11-13/garis-dasar/`. **Gate penuh (`--ci`): 120 gate, 43 merah. Gate statik (`--quick`): 56 gate, 16 merah.**
Rantai data acuan (`restore_local_demo.sh`) sudah gagal di 3 dari 12 skrip sebelum blueprint mengubah apa pun
(`00_restore.log`).

Pembanding untuk tiap unit (keluar 1 bila ada gate yang lebih merah dari garis dasar):

```bash
python docs/reviews/2026-11-13/garis-dasar/bandingkan_gate.py            # membaca memory/GATE_RECEIPT.md
```

| Gate | Hasil | Isi singkat | Sama dengan §4? |
|---|---|---|---|
| guard:auth_coverage (INV-AUTH-01) | MERAH | 28 endpoint dilaporkan tanpa penegak auth yang dikenali (sebagian besar `handheld.py` yang memakai kunci perangkat; juga `design_gallery` submit/approve/reject, `ai_assist` actions) | ya |
| guard:auth_coverage SELF-TEST (bukti-merah penjaga auth) | HIJAU | 28 endpoint dilaporkan tanpa penegak auth yang dikenali (sebagian besar `handheld.py` yang memakai kunci perangkat; juga `design_gallery` submit/approve/reject, `ai_assist` actions) | tidak (§4: MERAH) |
| validate_compliance (file/naming/docs/api/env) | MERAH | lihat `08_gate_ci.log` | — |
| check_nav_map (navigasi vs SSOT) | HIJAU |  | — |
| guard:modal_dismiss (INV-UI-01, modal auto-close) | HIJAU |  | — |
| guard:knselect_contract (FE-02, pilihan wajib onValueChange) | HIJAU |  | — |
| guard:access_catalog_nav (FE-03, katalog modul ↔ menu) | HIJAU |  | — |
| guard:desk_targets (FE-06, target antrean ke layar nyata) | HIJAU |  | — |
| guard:create_modal SELF-TEST (bukti-merah penjaga create pop-up) | HIJAU | 4 form buat masih sebaris; 2 tombol mati, termasuk `gl-reverse-submit` di `JournalDetailModal.jsx:109` | tidak (§4: MERAH) |
| guard:create_modal (INV-UI-05, tombol Buat = pop-up konsisten) | MERAH | 4 form buat masih sebaris; 2 tombol mati, termasuk `gl-reverse-submit` di `JournalDetailModal.jsx:109` | ya |
| guard:blocking_dialogs SELF-TEST (bukti-merah + anti tuduh palsu) | HIJAU |  | — |
| guard:blocking_dialogs (INV-UI-06, alert/confirm/prompt dilarang) | HIJAU |  | — |
| guard:list_export SELF-TEST (bukti-merah + CSV rusak harus memerah) | HIJAU |  | — |
| guard:list_export (INV-UI-07, daftar berhalaman wajib bisa diunduh) | HIJAU |  | — |
| guard:detail_modal SELF-TEST (bukti-merah + anti tuduh palsu) | HIJAU |  | — |
| guard:detail_modal (INV-UI-08, panel rincian wajib pop-up) | HIJAU |  | — |
| guard:picker_portal SELF-TEST (bukti-merah + anti tuduh palsu, 16 kasus) | HIJAU |  | — |
| guard:picker_portal (INV-UI-09, pemilih wajib ber-portal · pop-up bukan anak <label>) | HIJAU |  | — |
| guard:escape_layers SELF-TEST (bukti-merah + anti tuduh palsu, 13 kasus) | HIJAU |  | — |
| guard:escape_layers (INV-UI-10, Esc menutup lapisan teratas saja) | HIJAU |  | — |
| guard:custom_modals SELF-TEST (ratchet dua arah, 9 kasus) | HIJAU |  | — |
| guard:custom_modals (INV-UI-11, pop-up buatan sendiri hanya boleh berkurang) | HIJAU |  | — |
| guard:page_tabs SELF-TEST (ratchet dua arah, 7 kasus) | HIJAU | 1 berkas baru memakai tab buatan sendiri | tidak (§4: MERAH) |
| guard:page_tabs (INV-UI-12, tab maks 2 tingkat — tab/pil buatan sendiri hanya berkurang) | MERAH | 1 berkas baru memakai tab buatan sendiri | ya |
| guard:view_aliases SELF-TEST (bukti-merah dua arah, 8 kasus) | HIJAU |  | — |
| guard:view_aliases (INV-NAV-02, alias layar tidak memutus pintu/hak) | HIJAU |  | — |
| guard:to_list_bound SELF-TEST (bukti-merah dua arah, 11 kasus) | MERAH | 3 `to_list(50000)`; 3 entri daftar-izin basi | ya |
| guard:to_list_bound (INV-PERF-01, to_list(n>20000) dilarang) | MERAH | 3 `to_list(50000)`; 3 entri daftar-izin basi | ya |
| guard:codebase_map SELF-TEST (bukti-merah dua arah, 6 kasus) | HIJAU |  | — |
| guard:codebase_map (INV-DOC-01, CODEBASE_MAP.md selaras kode) | HIJAU |  | — |
| guard:atomic_claim SELF-TEST (bukti-merah dua arah, 10 kasus) | MERAH | 97 endpoint tulis multi-koleksi belum ditinjau + 5 ketidakcocokan (temuan audit DB-01) | ya |
| guard:atomic_claim (INV-ATOMIC-01, saga/CAS endpoint multi-koleksi) | MERAH | 97 endpoint belum ditinjau + 5 tidak cocok (DB-01) | ya |
| ux_audit SELF-TEST (bukti-merah baseline UX + anti tuduh palsu) | HIJAU |  | — |
| ux_audit --strict (INV-UX-01, loading/empty/chart baseline) | MERAH | Rincian belum dibaca | ya |
| config_wiring (INV-CFG-01/04, satu sumber kebenaran) | MERAH | 9 kunci "mati" (7 positif palsu retur) + 2 layar menulis di luar Pusat Pengaturan | ya |
| config_wiring SELF-TEST (bukti-merah guardrail) | MERAH | 7 kunci mati (positif palsu: `returns.grade_price_factors.*` dibaca mesin tetapi belum beregistry — dibereskan KF-T2), 2 kunci tanpa layar, 2 editor ganda | ya |
| audit_doc_refs SELF-TEST (bukti-merah relasi dokumen) | HIJAU |  | — |
| guard:ref_unlink SELF-TEST (bukti-merah dua arah, 8 kasus) | HIJAU | 3 penghapusan dokumen tanpa menyapu tautan balik (`routers/cash.py:178`, `amendment_service.py:774`, `ar_receipt_service.py:502`) | tidak (§4: MERAH) |
| guard:ref_unlink (INV-REF-04, hapus dokumen wajib sapu tautan balik) | MERAH | 3 penghapusan dokumen tanpa menyapu tautan balik (`routers/cash.py:178`, `amendment_service.py:774`, `ar_receipt_service.py:502`) | ya |
| guard:notif_audience SELF-TEST (bukti-merah dua arah, 14 kasus) | HIJAU |  | — |
| guard:notif_audience (INV-NOTIF-02, alamat notifikasi dari WEWENANG) | HIJAU |  | — |
| audit_i18n_id (label antarmuka Bahasa Indonesia) | MERAH | 113 teks belum berbahasa Indonesia | ya |
| audit_i18n_id SELF-TEST (bukti-merah guardrail bahasa) | HIJAU | 113 teks antarmuka belum berbahasa Indonesia di 66 berkas | tidak (§4: MERAH) |
| fix_i18n_id SELF-TEST (codemod tak boleh sentuh kode) | HIJAU |  | — |
| guard:entity_label (INV-UI-02, id entitas tak boleh tampil) | MERAH | 2 tempat mencetak id badan usaha mentah | ya |
| guard:error_notice (INV-UI-03, error tak boleh senyap) | HIJAU |  | — |
| guard:role_label (INV-ROLE-01, peran dari registry & izin) | HIJAU |  | — |
| guard:derived_fields (INV-UI-04, field turunan tak boleh dari respons daftar) | HIJAU |  | — |
| audit_entity_isolation SELF-TEST (bukti-merah pagar isolasi) | HIJAU | Butuh MongoDB | ya |
| guard:write_scope SELF-TEST (INV-ENTITY-02, mode gabungan hanya-lihat) | HIJAU |  | — |
| guard:warehouse_scope SELF-TEST (E4.1, gudang khusus badan usaha) | MERAH | 8 endpoint tulis memilih gudang tanpa pagar badan usaha | ya |
| guard:numeric_bounds (INV-NUM-01, statik+runtime) | MERAH | 3 isian tanpa batas di `SoOverrideLineIn` | ya |
| seed_realistic (data uji bersih) | HIJAU |  | — |
| verify_data_integrity (229 invarian domain/GL/alert/ledger/config/relasi/pembayaran/selisih/bank/kasus/kontrabon/antar-entitas) | MERAH | 231 lulus, 6 gagal: 2 koleksi tak terdaftar, purchase_returns kosong, stok awal ganda 177 pasang, lot campur 2 SO, INV-CFG-01/04 | — |
| verify_entity_scoping (F0-C, DB + STATIK anti-kebocoran PT) | HIJAU |  | — |
| audit_doc_refs (INV-REF cakupan data + kesehatan tautan) | MERAH | lihat `08_gate_ci.log` | — |
| guard:roll_identity SELF-TEST (bukti-merah + anti tuduh palsu) | HIJAU |  | — |
| guard:roll_identity (INV-ROLL-01, satu nomor untuk satu roll) | HIJAU |  | — |
| guard:rfid_tag_unique SELF-TEST (bukti-merah dua arah, 7 kasus) | HIJAU |  | — |
| guard:rfid_tag_unique (INV-RFID-01, satu tag untuk satu roll aktif) | HIJAU |  | — |
| guard:cross_entity (INV-ENTITY-01, IDOR multi-PT) | HIJAU |  | — |
| guard:nonfinancial_sweep (INV-ENTITY-01+, IDOR non-finansial) | HIJAU |  | — |
| audit_2026_09_21 (penjaga entitas aksi tulis · R-3a sampel · konstanta bersama) | MERAH | lihat `08_gate_ci.log` | — |
| POC F0-C (isolasi lintas-entitas: kartu asal · roll retur · jejak UoM) | HIJAU |  | — |
| audit_entity_isolation (E0.9/E0.10 — 0 kebocoran lintas-entitas) | MERAH | Butuh MongoDB | tidak (§4: tidak dinilai) |
| POC FASE E-0 (bukti-merah L1–L21: notifikasi·denda·audit·lot·AR·transfer·dokumen·pratinjau) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE E-3 (mode “Semua Entitas” hanya-lihat: 409 menuntun · master bersama tetap boleh) | HIJAU |  | — |
| POC FASE E-4 (gudang bersama/khusus · harga per badan usaha · CSV) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE E-4 master berlapis (global→badan usaha · override · kop surat per PT) | HIJAU |  | — |
| POC FASE E-5 (papan stok agregat · pegging · mutasi lintas-PT nama singkat · kartu riwayat) | HIJAU |  | — |
| POC FASE E-7 (pagar entitas grup · HPP taksiran berlabel · permintaan internal · kas grup dihapus · pinjaman & pindah aset antar-PT) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE E-8 G1 (peran sales_admin & finance · pemisahan tugas · penugasan entitas) | HIJAU |  | — |
| POC FASE E-8 G2/G3 (meja admin sales & finance · verifikasi · keputusan pemenuhan) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE E-9 (rantai jual→beli internal antar-PT→retur berantai · 41 pemeriksaan) | MERAH | lihat `08_gate_ci.log` | — |
| POC Cek Kenyataan Peran (utang migrasi ii E-8 · usulan peran dari jejak nyata) | HIJAU |  | — |
| audit_sales_roles_ux SELF-TEST (bukti-merah penilaian layar mati) | HIJAU |  | — |
| audit_sales_roles_ux (SEMUA peran: nol layar & panel mati) | MERAH | lihat `08_gate_ci.log` | — |
| POC F-2 Akses & UI/UX per peran (izin baca · pagar · KPI jujur · bukti-merah) | HIJAU |  | — |
| POC F-1b Migrasi kas tingkat grup (utang migrasi i · 4 lapis bukti · idempotent) | HIJAU |  | — |
| POC Pengingat Antrean Persetujuan (umur tunggu · eskalasi · idempotent · ambang pemilik) | HIJAU |  | — |
| POC FASE F-6 (pensiun mesin generik · 14 antrean nyata · anti dobel-hitung) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE F-6.7 (langkah Ajukan payroll & desain · selisih bayar · verifikasi SO) | MERAH | lihat `08_gate_ci.log` | — |
| guard:home_kpi SELF-TEST (bukti-merah penjaga KPI beranda) | HIJAU |  | — |
| guard:home_kpi (INV-HOME-01, KPI beranda = antrean nyata) | HIJAU |  | — |
| guard:aging_fields SELF-TEST (bukti-merah field umur ditebak) | HIJAU |  | — |
| guard:aging_fields (INV-AGING-01, field umur tunggu wajib nyata) | HIJAU |  | — |
| guard:status_history SELF-TEST (bukti-merah bentuk riwayat ke-dua) | HIJAU |  | — |
| guard:status_history (INV-HIST-01, satu bentuk riwayat status) | HIJAU |  | — |
| POC Papan PO Custom (umur tunggu bukan tebakan · yang tertua ikut · jujur saat dipotong · nol residu) | HIJAU |  | — |
| POC Sesi 2026-06 (true-up persediaan · papan manajer · umur tunggu antrean lain · satu bentuk riwayat) | MERAH | lihat `08_gate_ci.log` | — |
| guard:approval_queues SELF-TEST (bukti-merah penjaga antrean keputusan) | HIJAU |  | — |
| guard:approval_queues (INV-APPR-01, tiap pintu keputusan punya antrean) | MERAH | lihat `08_gate_ci.log` | — |
| guard:concurrency (INV-CONC-01, race/TOCTOU uang) | HIJAU |  | — |
| guard:state_machine (INV-STATE-01, transisi SO) | HIJAU |  | — |
| guard:line_scope SELF-TEST (bukti-merah pagar lini, 15 kasus dua arah) | HIJAU |  | — |
| guard:line_scope (INV-LINE-01/02, kode dikenal · turunan jujur · snapshot lengkap) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE L (lini produk: master bertambah · pagar keras · snapshot · isolasi PT) | MERAH | lihat `08_gate_ci.log` | — |
| guard:master_stages SELF-TEST (bukti-merah tahapan proses, 20 kasus dua arah) | HIJAU |  | — |
| guard:master_stages (INV-DOMAIN-06, master tahapan vs registry domain) | HIJAU |  | — |
| POC FASE T (tahapan proses: master bertambah · screen tak ubah kain · regresi identik) | MERAH | lihat `08_gate_ci.log` | — |
| guard:uom_vocab SELF-TEST (bukti-merah kosakata satuan, 23 kasus dua arah) | HIJAU |  | — |
| guard:uom_vocab (INV-UOM-02, satuan dokumen ⊆ master uoms · alias tak kembar · pemilih satuan dari master) | HIJAU |  | — |
| guard:qty_dual SELF-TEST (bukti-merah dua satuan, 32 kasus dua arah) | MERAH | lihat `08_gate_ci.log` | — |
| guard:qty_dual (INV-QTY-01, dua satuan satu arti di layar · PDF · CSV) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE U (dua satuan: PO→terima→PDF/CSV · retur turun serentak · satuan lini · dokumen lama "—") | MERAH | lihat `08_gate_ci.log` | — |
| guard:doc_origin SELF-TEST (bukti-merah asal dokumen PO, 26 kasus dua arah) | HIJAU |  | — |
| guard:doc_origin (INV-ORIG-01, satu definisi asal PO · sales dirunut bukan diketik · refs dua arah) | HIJAU |  | — |
| POC P-0 (asal dokumen PO: PO→PR→SO · Nama Sales dirunut · PO rutin kosong-jujur · nol residu) | MERAH | lihat `08_gate_ci.log` | — |
| guard:po_board SELF-TEST (bukti-merah papan PO, 22 kasus dua arah) | HIJAU |  | — |
| guard:po_board (INV-STAGE-01, tahap dari master · inspect turunan · tanda tahap ber-jejak) | HIJAU |  | — |
| POC FASE P (papan PO per lini: tahap dari master · sales dirunut · inspect turunan · terima dihitung · nol residu) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE D · PERMINTAAN DESAIN (DSR) (tugas→serah→revisi ber-alasan→ACC · rapor = hitung-ulang · peran ke-7 sempit tapi jujur) | MERAH | lihat `08_gate_ci.log` | — |
| guard:sample_types SELF-TEST (bukti-merah jenis sampling, 37 kasus dua arah) | HIJAU |  | — |
| guard:sample_types (INV-SAMPLE-01, jenis dari master · satu sumber · hasil ukur dinamis · jadi→kirim) | HIJAU |  | — |
| POC FASE S (sampling: dua jenis paralel · ukur dari master · jadi→kirim · nol residu) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE I (inspeksi & QC: SPK otomatis · grade dari mesin lama · tahanan warna dilepas manajer · nol residu) | MERAH | lihat `08_gate_ci.log` | — |
| POC FASE N (notifikasi beralamat: izin & divisi · dedupe per orang · nol siaran 'all') | HIJAU |  | — |
| audit_endpoint_sweep (semua GET → 5xx · paralel) | MERAH | 1 rute 500: /api/entities/count (KP-17) | — |
| health_check (isi endpoint kritis) | HIJAU |  | — |
| INV-GATE-01 anti-residu (gate tak boleh merusak data) | MERAH | lihat `08_gate_ci.log` | — |

## 5. Uji layar

Di sesi perancangan uji layar dijalankan untuk Pusat Pengaturan dan Peran & Hak Akses (21 langkah) serta sapuan
buka-layar; penilaian layar lain berasal dari membaca kode. Cara yang dipakai, tanpa Docker:

```bash
cd docs/audit/konfigurasi-peran-2026-11-13/bukti
python serve_mem.py &                                   # backend :8001, database tiruan, sandi demo12345
cp -r <root-repo>/frontend /tmp/fe && cd /tmp/fe && yarn install --registry https://registry.npmjs.org
REACT_APP_BACKEND_URL=http://localhost:8001 BROWSER=none PORT=3000 yarn start:dev &
node <bukti>/ui_pengaturan_peran.js /tmp/tangkapan       # contoh skenario; tiap langkah mencetak OK/BEDA/GAGAL
```

Pola yang dipakai skrip itu: tiap layar punya tautan `/?view=<id>`; hampir semua tombol punya `data-testid`; tiap langkah
membandingkan yang tampil di layar dengan jawaban API. Untuk butir bertanda "uji jalan layar": pakai cara ini atau
lingkungan A, login sebagai peran yang disebut, ikuti langkahnya, dan simpan tangkapan layar di laporan unit.

Uji komponen frontend: `yarn test --watchAll=false <pola>` di container frontend (belum dijalankan di sesi perancangan).
