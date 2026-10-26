# Brief agen fase 4 (sisa audit UI 2 & fase 3)

Repo `C:\Users\abc\Documents\Codex\KNHOST` (Windows; Bash = Git Bash; PowerShell tersedia). Bahasa Indonesia.
Folder ini = S. HEAD awal: `5110452` (fase 3 selesai & ter-push).

## Wajib dibaca
1. `AGENTS.md`, `CLAUDE.md` di repo.
2. `S\phase3_brief.md` (aturan fase 3 + keputusan pemilik yang tetap mengikat) dan `S\fix_brief.md` (aturan kerja & uji).
3. `S\phase3\P1.md` — API komponen standar (FormModal/DetailModal layar penuh di HP, FormSection, PageTabs, FilterChips,
   ResponsiveTable, LinkCard, DesktopOnlyNotice, EntityRequiredNotice, `useViewPreset`, `useAppNav`).
4. Laporan fase 3 di repo: `docs/uat/2026-10-21/hasil/UAT24-AUDIT-UI-2-FASE3.md` (bagian "Belum dikerjakan") dan
   lampiran `docs/uat/2026-10-21/hasil/audit-ui-2/fase3/P*.md` yang relevan dengan paket Anda.

## Keputusan pemilik yang mengikat
* **Form INPUT di HP tidak boleh diringkas** — isian lengkap sama dengan desktop (tata letak HP boleh 1 kolom/bertahap);
  cara terbaik: HP memakai komponen form desktop (FormModal → otomatis layar penuh di ≤ 640 px).
* **Istilah UI tidak diubah** (K-13) kecuali menyamakan judul/label yang memang salah.
* Layar duplikat yang sudah digabung tetap tautan/alias (jangan memisah lagi). Papan beranda tetap seperti fase 3.

## Aturan kerja
* Hanya edit berkas di himpunan paket Anda (lihat prompt). Berkas bersama `config/*`, `AppViewRouter.jsx`,
  `appViewImports.js`, `App.js`, `components/**`, `hooks/**`, `context/**`, `utils/**`, `styles/components.css`,
  `styles/layout.css` — JANGAN diubah; tulis kebutuhannya di laporan bagian "Untuk koordinator".
* Pop-up buatan sendiri (`.modal-card`, `fixed inset-0`, overlay manual) → `FormModal` (form) / `DetailModal` (rincian);
  galat tampil di DALAM pop-up (`ErrorNotice`); konfirmasi pakai `askConfirm/askReason` (bukan `window.confirm/prompt`);
  testid lama dipertahankan bila dipakai uji/tur (cek `grep` di `frontend/src` & `data/tours`).
* Tata letak: tab berlapis → `PageTabs`/`FilterChips`; tabel mentah → `.data-table`/`ResponsiveTable`; kepala halaman
  → `PageHeader` + `.section-card`; KPI → gaya `MetricRow` baku (nilai 0 netral, tanpa garis kiri warna-warni, aksen
  ungu → biru baku); grid responsif SELALU punya kolom eksplisit di HP (`grid-cols-1 … lg:grid-cols-[…]`, jangan
  `grid gap-3 lg:grid-cols-[…]` saja — kolom `auto` melebarkan halaman di 390 px).
* Layar yang bisa dibuka dari HP harus layak 390 px: `document.documentElement.scrollWidth === clientWidth`.
* Batas 500 baris per berkas — ekstrak komponen bila perlu. Line ending LF. Jangan sentuh git. Jangan restart kontainer
  (backend uvicorn TANPA reload: perubahan backend baru berlaku setelah koordinator me-restart — tulis uji HTTP yang
  perlu dijalankan di laporan).
* Jangan ubah data DB selain lewat alur UI/uji biasa yang membersihkan dirinya.

## Uji (wajib, laporkan apa adanya — merah tetap ditulis merah)
* ESLint 0 error: `docker exec kn-uji-frontend sh -c "cd /app/frontend && npx eslint <berkas>"`.
* Jest SELALU `--maxWorkers=1` & hanya suite relevan + uji baru Anda:
  `docker exec kn-uji-frontend sh -c "cd /app/frontend && CI=true npx craco test --watchAll=false --maxWorkers=1 <pola>"`.
  Memori laptop sangat terbatas (pernah OOM) — satu proses Jest Anda pada satu waktu.
* Guardrail di `scripts/guardrails/` (jalankan di `kn-uji-backend`: `docker exec kn-uji-backend sh -c "cd /app && python
  scripts/guardrails/<x>.py"`): `verify_custom_modals`, `verify_page_tabs` (hitungan boleh turun, TIDAK boleh naik —
  jangan sunting baseline; koordinator yang `--update`), `verify_error_notice`, `verify_blocking_dialogs`,
  `verify_escape_layers`, `verify_modal_dismiss`, `verify_detail_modal`, `verify_entity_label`, `verify_uom_vocab`.
* Backend: pyflakes berkas yang diubah; pytest yang tidak butuh restart.
* `docker logs --tail 5 kn-uji-frontend` tidak "compiled with … error" (bila error padahal berkas benar → catat, jangan
  hapus cache sendiri).
* Cek peramban (stack uji http://localhost:3063, backend :8063) di 1440 px dan 390 px untuk layar yang Anda ubah.
  Pakai origin `127.0.0.1:3063` supaya sesi tab lain tidak tertimpa; ganti akun dengan menghapus token lokal, JANGAN
  klik "Keluar". Akun demo: sandi di `AGENTS.md` (jangan tulis sandi di laporan). Pop-up/form hanya dibuka lalu
  dibatalkan — jangan menyimpan data.

## Laporan
`S\phase4\<Rx>.md` (bertahap): per butir — status, berkas, cara cek, uji, perubahan perilaku; bagian "Untuk
koordinator" (kebutuhan berkas bersama / ratchet / uji HTTP) dan "Butuh paket lain". Jawaban akhir ringkas.
