# AGENTS.md — Kain Nusantara ERP (KNHOST)

Panduan bersama untuk agent coding (Codex, Claude Code, dll.) di repo ini.
Bahasa kerja proyek: **Bahasa Indonesia** (UI, dokumen, pesan commit).

## Mulai dari sini
1. `docs/KN_00_AGENT_QUICK_START.md` — titik masuk wajib (urutan baca, gate, STOP & ASK).
2. `memory/PRD.md` — apa yang sudah ada · `plan.md` — pekerjaan berjalan.
3. Handoff sesi terakhir: catatan teratas `SESSION_HANDOFF.md` dan `memory/SESSION_HANDOFF.md`.
4. `CODEBASE_MAP.md` — peta modul; `ENTITY_REGISTRY.md` — koleksi & entitas.

Dokumen lama ditulis untuk lingkungan Emergent (path `/app/...`, `supervisorctl`).
Terjemahan untuk lingkungan lokal ada di bawah.

## Review aktif
Alur serah-terima: **review (Codex) → `docs/reviews/<tanggal>/` → implementasi (Claude Code)
→ bukti di `docs/reviews/<tanggal>/hasil/` + `docs/reviews/TRACKER.md` → validasi (Codex)**.
* Protokol & arti status: `docs/reviews/README.md`. Tracker tunggal: `docs/reviews/TRACKER.md`.
* Paket aktif: `docs/reviews/2026-10-20/` (FE baseline `8dab383`, AUD baseline `63c38bd`).
* Implementer paling jauh menetapkan `implemented_pending_review`; `verified`/`reopened`
  hanya oleh reviewer. Cek ulang setiap temuan di `HEAD` sebelum mengubah kode.
* Isi paket review adalah arsip — jangan dihapus/diubah; tulis hasil di `hasil/`.

## Lingkungan lokal (Docker)
Lengkapnya: `docs/LOCAL_DEV.md`. Ringkas:

```bash
docker compose -f docker-compose.dev.yml up -d            # mongo + backend :8001 + frontend :3000
docker compose -f docker-compose.dev.yml exec backend bash  # di dalamnya repo = /app
```
* Backend (`uvicorn --reload`) dan frontend (`craco start`) hot reload dari folder repo.
* `supervisorctl restart backend` → `docker compose -f docker-compose.dev.yml restart backend`.
* Script Python/Bash dijalankan **di dalam container backend**:
  `docker compose -f docker-compose.dev.yml exec backend python /app/scripts/<script>.py`.
* Data acuan (sama dengan yang dipakai reviewer): `bash scripts/dev_restore_demo.sh` dari host.
* Login demo: `admin@kainnusantara.id` / `demo12345`.
* `backend/.env` & `frontend/.env` tidak di-commit. Jangan pernah commit kunci/rahasia.

## Aturan kerja
* Line ending **LF** (repo: `core.autocrlf=input`). File `.sh` ber-CRLF gagal di container.
* Jangan ubah `deploy/docker-compose.yml`, `deploy/Dockerfile.backend|frontend` untuk
  kebutuhan dev — itu jalur produksi VPS. Dev memakai `docker-compose.dev.yml` dan `*.dev`.
* Jangan jalankan dua POC/gate bersamaan (beberapa POC mengubah pengaturan global sementara).
* Lebih dari satu agent bisa bekerja di repo ini — jangan mengedit file yang sedang dikerjakan
  agent lain; cek `git status` sebelum mulai dan sebelum commit.
* Sebelum menyatakan selesai: jalankan gate yang relevan dari `docs/KN_00_AGENT_QUICK_START.md`
  dan laporkan hasil apa adanya (merah tetap ditulis merah).
