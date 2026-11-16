# Paket review 2026-11-16 — temuan baru dari validasi batch B1

Reviewer: sesi review 16 Nov 2026 · HEAD yang diperiksa: `91a3ec0` (cabang `main`) · cabang hasil: `review/2026-11-16`.

Paket ini hanya memuat **temuan baru** yang muncul saat memvalidasi batch B1 (keuangan Kritis/Tinggi — kas, pembayaran,
piutang & hutang). Putusan atas 17 butir B1 sendiri ada di `docs/reviews/2026-11-13/hasil/validasi-PK-05.md`,
`-PK-15.md`, `-PK-17.md`, `-PK-19.md`, `-PK-31.md`, `-PK-38.md`.

| Berkas | Isi |
|---|---|
| [`TEMUAN_BARU_B1.md`](TEMUAN_BARU_B1.md) | RV-01, RV-02, RV-03 — lensa, berkas:baris di HEAD, reproduksi, tingkat bukti, arah perbaikan |
| [`USULAN_PERBAIKAN_B1.md`](USULAN_PERBAIKAN_B1.md) | Usulan perbaikan untuk 4 butir dibuka lagi, 3 keputusan pemilik, dan RV-01…05 (tanpa perubahan kode) |
| [`RINGKASAN_PEMILIK_B1.md`](RINGKASAN_PEMILIK_B1.md) | Ringkasan untuk pemilik: yang aman, yang harus diperbaiki dulu, keputusan yang ditunggu |

Uji bantahan reviewer (lapis B, tidak masuk gate): `docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK*.py`.
Cara menjalankan: salin satu berkas ke `backend/tests_mem/`, jalankan `python -m pytest tests_mem/<berkas> -n 0 -q -s`,
lalu hapus salinannya. Uji-uji itu hanya menyentuh database tiruan (mongomock) — termasuk `delete_one` pembersih
fixture — dan tidak pernah dijalankan terhadap MongoDB asli.

Semua temuan terdaftar di `docs/reviews/TRACKER.md` bagian "Review B1 — temuan baru reviewer" berstatus `open`.
Tidak ada kode produksi yang diubah.
