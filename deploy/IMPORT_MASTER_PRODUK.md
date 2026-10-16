# Update VPS · impor master produk · aktifkan AI (sekali jalan)

Syarat: VPS sudah pernah dipasang dengan `deploy/install_vps.sh` (ada `deploy/.env`), dan kode terbaru
sudah di-push ke GitHub (tombol **Save to GitHub** di Emergent).

```bash
cd /opt/kainnusantara
git fetch origin main && git reset --hard origin/main
OPENAI_API_KEY='sk-proj-KUNCI_ASLI' bash deploy/setup_vps_ai_import.sh
```
Jangan pakai `git pull`: Save to GitHub menulis ulang riwayat (force push) sehingga `git pull` gagal
"divergent branches". `deploy/.env` (rahasia) tidak tersentuh oleh `reset --hard`.
Kunci contoh (`sk-proj-...`, `KUNCI_ANDA`) ditolak skrip — tempel kunci asli.

Yang dikerjakan `deploy/setup_vps_ai_import.sh`:
1. Menyimpan `OPENAI_API_KEY` + membuat `KN_SECRETS_KEY` (kunci enkripsi) di `deploy/.env` (chmod 600, tidak ikut git).
2. `deploy/update.sh` — tarik kode, build image, restart (data tidak dihapus).
3. Impor `backend/data/import/TEST_MIGRASI_MASTER_PRODUK.xlsx` (dry-run dulu, lalu tulis) — 30 artikel, 268 SKU,
   harga MOCK (yard Rp 18–25 rb, kg Rp 40–45 rb). Idempoten.
   Lalu `backend/scripts/import_stok_awal_kn.py` — stok awal MOCK: tiap artikel 1.000–2.000 roll (±45 ribu roll),
   dibagi ke SKU dan entitas bertanda Y, panjang/berat roll = QTY_PER_ROLL ±5% (bawaan 25 kg / 50 yard), di gudang
   khusus entitas (dibuat "Gudang Utama <entitas>" bila belum ada), plus jurnal saldo awal persediaan
   (Dr Persediaan / Cr Ekuitas Saldo Awal). Idempoten — produk yang sudah punya stok awal dilewati.
4. `backend/scripts/vps_enable_ai.py` — simpan kunci terenkripsi, uji koneksi OpenAI, nyalakan
   `receiving.ocr_enabled`, `receiving.ocr_photo_check`, `ai.enabled`, `ai.anomaly_enabled`, bangun data analitik,
   pindai peringatan, lalu 1 pertanyaan uji ke model nyata (gpt-6-sol). Akhir: `SELESAI — semua langkah OK`.

Opsi: `XLSX=/root/MASTER_BARU.xlsx` (Excel lain berformat sama) · `ADMIN_PASSWORD=...` bila sandi admin
bukan yang ada di `deploy/.env`. Menjalankan ulang aman.

Cek manual sesudahnya: Master Produk → cari `KNKNT0007` · Tanya KN → tanya bebas · Kedatangan Barang → Baca otomatis.

## Pemeriksaan akhir (2026-09-29)
`setup_vps_ai_import.sh` kini menutup dengan langkah 5/5 `deploy/cek_vps.sh`: kontainer mongo/backend/web berjalan,
`https://DOMAIN` & `/api/` → 200, master produk ≥268 SKU, stok awal ada, OPENAI_API_KEY sampai ke backend,
integrasi OpenAI terverifikasi, dan `/api/inventory/rolls?limit=5` → ≤5 baris (perbaikan limit aktif).
Bisa dijalankan kapan saja: `cd /opt/kainnusantara && bash deploy/cek_vps.sh` → akhir `VPS AKTIF — semua pemeriksaan OK.`
