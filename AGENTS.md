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

## Middleware & gate RFID
* Sebelum menyentuh `middleware/` (U300 Reader Agent), logika gate (`gate_evaluator`, `rfid_ingest_service`,
  `rfid_service`) atau patch `middleware/u300-erp-integration-0.5.0/`: baca **`docs/rfid/KEPUTUSAN_GATE_RFID.md`**
  (bacaan nyasar, photo-eye, fakta lapangan pemilik, keputusan K-RFID-01…10) dan audit kode Kubus
  **`docs/rfid/AUDIT_MIDDLEWARE_RFID_2026-11-08.md`** (temuan AUD-MW-xx, peta K-RFID-07).
* Pemilik: soal bacaan nyasar & photo-eye diselesaikan dulu sebelum membangun/merevisi — butir terbuka = STOP & ASK.

## Keuangan
* Sebelum mengubah jurnal/buku besar (`gl_service`), buku pembantu (piutang, hutang, kas, kontrabon), antar-PT
  (`interco_*`, `consolidation_service`), tutup buku, atau nilai persediaan ↔ jurnal: baca
  **`docs/finance/AUDIT_KEUANGAN_2026-11-13.md`** (139 temuan, bukti uji di `bukti-2026-11-13/`, peta sumber-kebenaran, gap vs ERP
  matang, rekomendasi database, keputusan pemilik §10, kueri cek data §12). Analisis kode di `cd6963a` — cek ulang
  di `HEAD` sebelum memperbaiki.
* Rencana perbaikan dan modul baru: **`docs/finance/rencana-2026-11-13/`** (mulai dari `README.md`). Paket kerja `PK-nn`
  ada di `02`, cara menjalankan satu paket di `03`, aturan wajib untuk modul apa pun yang menyentuh uang di `04`
  (kontrak posting, entitas, idempotensi, penjaga), keputusan pemilik di `10` — butir bertanda "menahan" = STOP & ASK.
  Rancangan insentif, piutang, pajak & pembayaran, asisten keuangan, HR & penggajian di `05`–`09` berstatus usulan.

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
* Login demo: `admin@kainnusantara.id` / `demo12345` — **semua** akun seed (akun peran data acuan,
  `wh.admin@`, tombol login cepat) memakai sandi yang sama `demo12345`.
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
