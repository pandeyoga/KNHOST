# B — Makloon dari awal sampai akhir

HEAD: `91a3ec0`.

---

## MK-01 — Dua pintu pembuatan SPK makloon

- **Keparahan:** Tinggi
- **Jenis akar:** pintu ganda
- **Bukti:**
  - `frontend/src/features/purchasing/makloon/MakloonWizard.jsx:305` → `POST /purchase-requisitions/{pr_id}/realize-makloon` dan `:307` → `POST /makloon-orders` (alur dari kebutuhan/PR).
  - `frontend/src/features/purchasing/MakloonOrderCreateModal.jsx:192` → `POST /makloon-orders` (alur dari pilih resep → qty/gudang → forecast).
  - Keduanya bermuara ke endpoint `/makloon-orders` yang sama tetapi lewat UX berbeda dan pengisian berbeda.
- **Akibat:** pengalaman "kacau dari awal": dua pintu dengan prasyarat & default berbeda; mudah salah pintu, aturan bisa berbeda per pintu.
- **Langkah reproduksi:** buat SPK makloon dari Wizard (via PR) lalu dari Create-Modal (via resep); bandingkan field wajib, default stage/mitra, dan hasil di `MakloonOrderDetailPanel.jsx`.
- **Arah perbaikan:** satukan menjadi satu wizard dua-mode (dari PR / dari resep) dengan satu set aturan; matikan pintu lama (aturan anti-duplikasi R6).
- **Keputusan pemilik:** Pertanyaan #3.

---

## MK-02 — `from_stage` langkah tak ditegakkan terhadap bahan masuk

- **Keparahan:** Tinggi
- **Jenis akar:** aturan tidak ditegakkan
- **Bukti:** lihat **MS-04** (`MakloonStepEditor.jsx:67-68`, `makloon_order_service._resolve_stage`). Server merangkai rantai (`makloon_order_service.py:312` memaksa output langkah sebelumnya = input langkah ini) tetapi tidak memvalidasi stage bahan masuk vs `from_stage` langkah pertama.
- **Akibat:** langkah bisa memproses bahan salah-tahap (mis. printing atas grey/PFD).
- **Arah perbaikan:** validasi stage input vs `from_stage` di server; saring pilihan langkah di layar.

---

## MK-03 — Langkah mitra bisa disimpan tanpa mitra (peringatan, bukan penolakan)

- **Keparahan:** Sedang
- **Jenis akar:** status (risiko macet) — sebagian **keputusan pemilik**
- **Bukti:** `backend/services/makloon_order_service.py:291-299` — bila `needs_vendor` dan `mk_id` kosong, hanya menambah `order_warnings` (keputusan pemilik 3b: peringatan, bukan tolak).
- **Akibat:** SPK langkah mitra bisa tersimpan tanpa mitra; akan macet di Issue/Catat Jasa; UX terasa "kacau" karena blokir muncul belakangan.
- **Arah perbaikan:** jika pemilik ingin tetap izinkan (3b), tampilkan status "menunggu mitra" yang jelas + blok tindakan lanjutan dengan pesan yang menuntun; jika tidak, wajibkan mitra sejak simpan.
- **Keputusan pemilik:** Pertanyaan #6.

---

## Catatan alur (untuk telaah lanjutan di data acuan)

Alur lengkap yang perlu dijalankan sebagai pemakai (PR → SPK → kirim bahan `makloon_issue_rolls`/kunci FIX-9
`makloon_roll_lock` → terima per langkah `receive_step`/`makloon_receipt_qc` → susut `makloon_loss_service` → klaim
`makloon_claim_service` → buku bahan `makloon_material_ledger` → tagihan `record_service_step`/`makloon_calc_service` →
jurnal PK-18 → stok hasil → rekap/skor). Verifikasi nilai (bahan+jasa+susut) sampai ke HPP hasil memerlukan dataset
acuan; dicatat sebagai tindak lanjut saat stack acuan tersedia. Temuan struktural (MK-01/02/03) sudah cukup di tingkat kode.
