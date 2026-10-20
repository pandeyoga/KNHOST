# ENV — data acuan dapat dipulihkan di lingkungan Docker lokal

- Commit awal: `870a807` · Commit perbaikan: `6e64b2c` · Branch: `main`
- ID ditangani: ENV-01, ENV-02 (diajukan implementer di [VALIDASI_TEMUAN.md](VALIDASI_TEMUAN.md)); ENV-03 tidak dikerjakan

## ENV-01 — rantai `restore_local_demo.sh` gagal 3/12 skrip (403)
- Berlaku di HEAD: ya — direproduksi berulang (`seed_p04_kn`: `POST /sales-orders/{id}/verify → 403 order.verify`).
- Akar masalah: **bukan regresi izin.** `dependencies.extract_token` mendahulukan cookie sesi
  daripada header Bearer (SEC-2). Klien ASGI skrip seed (`backend/scripts/demo_api.py`) memakai
  satu `httpx.AsyncClient` untuk banyak akun, sehingga cookie login akun terakhir ikut terkirim
  dan menimpa Bearer akun yang sedang dipakai (mis. `salesadmin.kanda` dibaca sebagai
  `sales.kanda` → 403). Di Emergent cookie ber-`Secure` (`SESSION_COOKIE_SECURE=true`) tidak
  dikirim lewat `http://demo.local`, jadi masalah tidak muncul; di dev lokal nilainya `false`.
  Bukti: panggilan identik lewat server HTTP biasa (tanpa cookie jar) → 200; matriks izin di DB
  sama dengan `permissions_config.py`.
- Perubahan perilaku: skrip seed memakai identitas akun yang dimaksud. Aturan keamanan produk
  (cookie diutamakan) **tidak** diubah.
- Berkas: `backend/scripts/demo_api.py` — cookie jar dikosongkan sesudah login dan sebelum tiap panggilan.
- Pengujian: restore penuh di Docker → 12/12 skrip `EXIT 0`, "semua skenario transaksi demo OK"
  (sebelumnya 9 skenario + `seed_p04_kn` + `seed_p05_kn` gagal).
- Status: implemented_pending_review

## ENV-02 — restore terikat lingkungan Emergent
- Perubahan: `scripts/restore_local_demo.sh` mendapat opsi `--seed-only`, drop DB membaca
  `MONGO_URL`/`DB_NAME`, dan melaporkan skrip yang gagal dengan exit ≠ 0 (perilaku bawaan untuk
  Emergent tetap). Baru `scripts/dev_restore_demo.sh` (jalan dari host): hentikan backend → drop
  DB → nyalakan backend (bootstrap fondasi) → rantai seed yang sama → verifikasi fondasi.
- Temuan saat menguji: drop DB ketika backend hidup membuat bootstrap/penjadwal yang sedang
  berjalan menulis akun peran ke DB kosong; bootstrap berikutnya lalu **tidak membuat akun admin**
  (`seed_data` hanya mengisi user bila koleksi kosong). Karena itu backend dihentikan dulu.
- Pengujian: `bash scripts/dev_restore_demo.sh` → RC 0; fondasi gl_accounts 77 · uoms 8 ·
  expense_categories 8 · business_entities 3 · users 21.
- Status: implemented_pending_review

## Keterbatasan
- ENV-03 (`seed_realistic.py` melewati Interco & SPK printing) belum disentuh; data acuan resmi
  kini lewat `dev_restore_demo.sh`.
- Tes/skrip lain yang memakai satu klien HTTP untuk banyak akun bisa terkena pola cookie yang sama
  di dev lokal; belum disisir.

## Yang perlu direview
- Apakah perilaku `extract_token` (cookie menang atas Bearer bila keduanya dikirim) memang
  diinginkan untuk klien API — saat ini dipertahankan.
