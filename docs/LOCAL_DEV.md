# Development Lokal — Windows + Docker Desktop

Stack: **FastAPI** (Python 3.11) · **React** CRA/craco (Node 20, Yarn 1) · **MongoDB 7**.
Semua jalan di Docker, jadi Python/Node tidak wajib terpasang di Windows.
Produksi/VPS tetap memakai `deploy/docker-compose.yml` (lihat `docs/DEPLOY_VPS.md`).

| Layanan | Alamat | Catatan |
|---|---|---|
| Frontend (hot reload) | http://localhost:3000 | `craco start` |
| Backend API | http://localhost:8001/api/ | `uvicorn --reload` |
| MongoDB | mongodb://localhost:27017 | DB `test_database` |

Login demo (sesudah seed): `admin@kainnusantara.id` / `demo12345`
(juga `manager@`, `sales@`, `sales3@`, `warehouse@` … `@kainnusantara.id`).

---

## Persiapan sekali saja

1. **Docker Desktop** menyala (engine WSL 2). Cek: `docker version`.
2. **Line ending LF.** Script `.sh` dijalankan di container Linux; CRLF membuatnya gagal
   (`$'\r': command not found`). Di repo ini:
   ```bash
   git config core.autocrlf input
   ```
   Bila file di working tree masih CRLF (cek `git ls-files --eol scripts/gate.sh` → `w/crlf`),
   pada working tree yang **bersih** jalankan `git rm --cached -r -q .` lalu `git reset --hard`.
   Di VS Code set `"files.eol": "\n"`.
3. **Berkas env** (di-.gitignore — buat manual):

   `backend/.env`
   ```
   MONGO_URL=mongodb://localhost:27017
   DB_NAME=test_database
   CORS_ORIGINS=http://localhost:3000
   SESSION_COOKIE_SECURE=false
   SESSION_COOKIE_SAMESITE=lax
   PUBLIC_APP_URL=http://localhost:3000
   REACT_APP_BACKEND_URL=http://localhost:8001
   KN_DEMO_DATA=true
   SEED_DEMO_ENABLED=true
   TZ=Asia/Jakarta
   # OPENAI_API_KEY=      (opsional: Tanya KN / OCR)
   # GEMINI_API_KEY=
   # KN_SECRETS_KEY=      (opsional: kunci Fernet untuk API key terenkripsi di DB)
   ```
   `frontend/.env`
   ```
   REACT_APP_BACKEND_URL=http://localhost:8001
   WDS_SOCKET_PORT=3000
   ENABLE_HEALTH_CHECK=false
   ```
   Kenapa nilai-nilai ini penting:
   * `CORS_ORIGINS` wajib eksplisit — backend **menolak start** bila kosong atau `*`.
   * `SESSION_COOKIE_SECURE=false` — tanpa ini cookie login tidak tersimpan di `http://`.
   * `DB_NAME=test_database` — banyak script lama memakai nama ini.
   * `KN_DEMO_DATA=true` — akun awal bersandi `demo12345` (bukan sandi acak).

## Menjalankan

```bash
docker compose -f docker-compose.dev.yml up -d --build
docker compose -f docker-compose.dev.yml ps
```
Build pertama ±5–15 menit (pip + yarn). Kompilasi pertama frontend ±1–3 menit — pantau:
`docker compose -f docker-compose.dev.yml logs -f frontend` sampai muncul `Compiled`.

**Isi data demo** (sekali, atau kapan pun ingin reset ke data realistis; ±10 menit):
```bash
docker compose -f docker-compose.dev.yml exec backend python /app/seed_realistic.py
```
Lalu buka http://localhost:3000.

> **Git Bash:** path `/app/...` diubah otomatis menjadi path Windows
> (`can't open file '/app/backend/C:/Program Files/Git/app/...'`). Jalankan
> `export MSYS_NO_PATHCONV=1` sekali per terminal, atau pakai PowerShell.

## Perintah harian

| Tujuan | Perintah |
|---|---|
| Nyalakan | `docker compose -f docker-compose.dev.yml up -d` |
| Matikan (data tetap) | `docker compose -f docker-compose.dev.yml down` |
| Log backend / frontend | `docker compose -f docker-compose.dev.yml logs -f backend` |
| Shell di backend | `docker compose -f docker-compose.dev.yml exec backend bash` |
| Restart backend (bootstrap ulang) | `docker compose -f docker-compose.dev.yml restart backend` |
| Cek integritas data | `docker compose -f docker-compose.dev.yml exec backend python /app/scripts/verify_data_integrity.py` |
| Hapus SEMUA data (DB kosong) | `docker compose -f docker-compose.dev.yml down -v` lalu `up -d` + seed |

Di dalam container backend, repo ada di **`/app`** — persis seperti lingkungan Emergent,
jadi script dan dokumen yang menyebut `/app/...` tetap berlaku. Yang **tidak** berlaku:
`supervisorctl` (ganti dengan `docker compose ... restart backend`) dan
`scripts/rebuild_frontend.sh` (dev server sudah hot reload).

## Dependency berubah

* `backend/requirements.txt` berubah → `docker compose -f docker-compose.dev.yml up -d --build backend`
* `frontend/package.json` berubah → salin lock terbaru ke `deploy/frontend-yarnlock.txt`, lalu
  ```bash
  docker compose -f docker-compose.dev.yml build frontend
  docker compose -f docker-compose.dev.yml rm -sf frontend
  docker volume rm kn-dev_fe_node_modules
  docker compose -f docker-compose.dev.yml up -d frontend
  ```
  (`node_modules` disimpan di volume; volume lama harus dibuang supaya terisi dari image baru.)

## Masalah umum

| Gejala | Penyebab / obat |
|---|---|
| Backend restart terus, log `CORS_ORIGINS wajib di-set` | `backend/.env` belum ada / `CORS_ORIGINS` kosong |
| Login sukses tapi langsung terlempar ke halaman login | `SESSION_COOKIE_SECURE` bukan `false` |
| `bad interpreter` / `$'\r': command not found` | file `.sh` ber-CRLF — lihat Persiapan langkah 2 |
| COA / satuan / kategori biaya kosong | backend start sebelum Mongo siap → `restart backend` |
| Perubahan kode tidak ter-reload | pastikan `WATCHFILES_FORCE_POLLING` / `WATCHPACK_POLLING` aktif (sudah di compose) |
| Port 3000/8001/27017 bentrok | matikan proses lain di port itu, atau ubah sisi kiri `ports:` di compose |
