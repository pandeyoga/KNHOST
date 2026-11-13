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

Pola satu uji:

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
  menghasilkan 422, bukan 403 — untuk menguji izin pada endpoint tulis, kirim isi yang sah bentuknya.
- PT seed: `ent_ksc` (PKP), `ent_kanda` (non-PKP), dan satu PT ketiga. Akun seed: admin, manager, sales, warehouse.
- Tiap proses mulai dari database kosong; tidak ada yang tersisa di antara dua kali jalan.

Skrip siap pakai di `docs/audit/konfigurasi-peran-2026-11-13/bukti/`:

| Skrip | Isi | Lama |
|---|---|---|
| `inv_endpoints.py <keluaran.json>` | Inventaris statik 1.749 endpoint beserta jenis gerbangnya | ±12 dtk |
| `t1_config.py <keluaran.json>` | Tiap kunci Pusat Pengaturan: tulis → baca lewat 3 jalur → lapisan PT → nilai tak sah → pulihkan | ±1 mnt |
| `t2_roles.py <keluaran.json> <inventaris.json>` lalu `t2_analyze.py <folder>` | 16 peran (termasuk 4 peran kustom uji) × 786 rute GET, dibandingkan dengan matriks izin | ±12 mnt |
| `t3_escalation.py`, `t3b_eskalasi_akun.py` | Siapa bisa mengubah pengaturan; peran kustom menaikkan haknya sendiri | ±10 dtk |
| `fe_be_routes.py <inventaris.json>` | Tiap panggilan API di layar punya rute dengan metode yang sama | ±5 dtk |

Skrip-skrip ini adalah bahan baku tes regresi untuk unit `KF-*` dan `PR-*`: tiap unit menyebut skrip mana yang harus
berubah hasilnya.

## 4. Garis dasar gate statik (`bash scripts/gate.sh --quick`, 13 Nov 2026, `dca195b`)

Dijalankan di luar Docker dengan tautan `/app` dan tanpa MongoDB. Gate yang butuh database dicatat "tidak dinilai".

| Gate | Hasil | Isi singkat |
|---|---|---|
| `guard:auth_coverage` (INV-AUTH-01) | MERAH | 28 endpoint dilaporkan tanpa penegak auth yang dikenali (sebagian besar `handheld.py` yang memakai kunci perangkat; juga `design_gallery` submit/approve/reject, `ai_assist` actions) |
| `guard:atomic_claim` (INV-ATOMIC-01) | MERAH | 97 endpoint tulis multi-koleksi belum ditinjau + 5 ketidakcocokan (temuan audit DB-01) |
| `config_wiring` (INV-CFG-01/04) | MERAH | 7 kunci mati, 2 kunci tanpa layar, 2 editor ganda |
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

## 5. Uji layar

Tidak ada uji layar yang dijalankan di sesi perancangan; seluruh penilaian layar berasal dari membaca kode. Untuk butir
bertanda "uji jalan layar": jalankan di lingkungan A dengan peramban (Playwright tersedia di banyak lingkungan agen),
login sebagai peran yang disebut, ikuti langkahnya, dan simpan tangkapan layar di laporan unit.

Uji komponen frontend: `yarn test --watchAll=false <pola>` di container frontend (belum dijalankan di sesi perancangan).
