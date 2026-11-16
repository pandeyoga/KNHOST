# B — Makloon dari awal sampai akhir

HEAD: `91a3ec0`.


> **Status domain: BELUM DIKERJAKAN.** Skenario wajib §8 dan inventaris form domain ini belum dijalankan. Semua isi di bawah berlabel **dugaan (baca kode)** sampai diuji lewat layar/API pada sesi domainnya.
---

## MK-01 — Dua pintu AKTIF pembuatan SPK makloon

- **Keparahan:** Sedang · **Jenis akar:** pintu ganda
- **Tingkat bukti:** dugaan (baca kode)
- **Bukti terverifikasi (dua-duanya dirender/terjangkau):**
  - `MakloonWizard` dirender di `frontend/src/features/purchasing/MakloonOrdersView.jsx` dan `frontend/src/features/purchasing/PrSourcingPanel.jsx`; `MakloonWizard.jsx:305` → `POST /purchase-requisitions/{pr_id}/realize-makloon`, `:307` → `POST /makloon-orders` (alur dari PR).
  - `MakloonOrderCreateModal` dirender di `frontend/src/features/admin/PurchaseOrderManagement.jsx`; `MakloonOrderCreateModal.jsx:192` → `POST /makloon-orders` (alur dari pilih resep → qty/gudang → forecast).
- **Akibat:** dua pintu dengan prasyarat/default/UX berbeda bermuara ke endpoint sama; mudah salah pintu, aturan bisa beda per pintu — akar rasa "makloon kacau dari awal".
- **Langkah reproduksi:** buat SPK dari Wizard (via PR) & dari Create-Modal (via resep); bandingkan field wajib, default stage/mitra, dan tampilan `MakloonOrderDetailPanel.jsx`.
- **Arah perbaikan:** satu wizard dua-mode (dari PR / dari resep), satu set aturan; matikan pintu lama (R6).
- **Keputusan pemilik:** Pertanyaan #4.

---

## MK-02 — `from_stage`/`to_stage` langkah tak ditegakkan terhadap bahan & output

- **Keparahan:** Tinggi · **Jenis akar:** aturan tidak ditegakkan
- **Tingkat bukti:** dugaan (baca kode)
- **Bukti:** lihat **MS-02 & MS-04**. `receive_step` (`makloon_order_service.py:1019`) memakai `output_product_id` apa adanya; tak ada pembanding stage roll input vs `from_stage`, maupun stage produk output vs `to_stage`. Rantai antar-langkah dipaksa (`:312` output langkah sebelumnya = input langkah ini) tetapi **stage** tidak.
- **Akibat:** bahan salah-tahap bisa diproses; produk output bisa ber-stage yang tak cocok dengan langkah.
- **Arah perbaikan:** validasi stage input/output per langkah lewat validator transisi tunggal.

---

## MK-03 — Langkah mitra bisa disimpan tanpa mitra (peringatan, keputusan pemilik 3b)

- **Keparahan:** Sedang · **Jenis akar:** status / keputusan pemilik
- **Tingkat bukti:** dugaan (baca kode)
- **Bukti:** `backend/services/makloon_order_service.py:291-299` — `needs_vendor` tanpa `mk_id` hanya menambah `order_warnings` (keputusan pemilik 3b: peringatan, bukan tolak; gate INV-DOMAIN-06 tetap memerah bila tak ada mitra terdaftar untuk prosesnya).
- **Akibat:** SPK langkah mitra tersimpan tanpa mitra lalu macet di Issue/Catat Jasa; blokir muncul belakangan → terasa membingungkan.
- **Arah perbaikan:** jika tetap diizinkan (3b), tampilkan status "menunggu mitra" yang jelas + blok tindakan lanjutan dengan pesan menuntun; jika tidak, wajibkan mitra sejak simpan.
- **Keputusan pemilik:** Pertanyaan #6.

---

## Catatan pelengkap dari data acuan (BUKAN uji skenario)

Status: **dugaan (baca kode)** — belum ada SPK yang dibuat/dijalankan lewat layar atau API. Data acuan berisi 3 makloon_orders (tenun/rajut/celup).
- **MK-02 (tetap dugaan):** proyeksi `db.makloon_orders` menunjukkan `steps[]` hanya menyimpan `seq`, `process_type`, `stage_label` — **tidak ada field `from_stage`/`to_stage` tersimpan pada langkah**. Jadi transisi stage per langkah memang nominal (tak ada data stage yang bisa diadu dengan roll input). Konsisten dengan temuan kode.
- **MK-01:** kedua endpoint pembuatan (`/makloon-orders` dari dua pintu UI) terjangkau; belum dibuat SPK baru (menghindari mutasi tak perlu). Terkonfirmasi tingkat kode + kedua pintu dirender.
- Alur nilai/HPP/terima-sebagian: perlu membuat SPK baru (mutasi) → tidak dijalankan di sesi baca-saja ini; dicatat untuk pendalaman lanjutan.

## Tindak lanjut (butuh data acuan)

Alur nilai (bahan+jasa+susut → HPP hasil), terima sebagian, kirim balik, perbaikan, batal di tengah, mitra beda per
langkah, antar-PT — perlu dataset acuan untuk reproduksi runtime penuh & cek efek uang (rujuk `docs/finance/AUDIT_KEUANGAN_2026-11-13.md`).
Temuan struktural (MK-01/02/03) sudah tegak di tingkat kode.
