#!/usr/bin/env bash
# Jalankan SEMUA skenario pelatihan berurutan (urutan kelas) untuk satu peserta, lalu potret navigasi & rekap.
#   KN_PESERTA=01 bash docs/pelatihan/2026-11-18_keuangan/uji/jalankan_semua.sh
# Butuh: data latihan peserta itu sudah disiapkan (backend/scripts/seed_pelatihan_keuangan_kn.py), backend :8001,
# frontend :3000, dan `python3` yang bisa menjalankan skrip backend (F04 langkah 7 = susulan pelatih).
set -u
cd "$(dirname "$0")"
export KN_PESERTA="${KN_PESERTA:-01}"
rm -rf hasil/F0* hasil/F1* hasil/_navigasi
URUT=(F01_orientasi F02_pelunasan_penuh F03_bayar_sebagian F04_lebih_bayar_titipan F05_rencana_denda F06_kredit_plafon
      F07_kas_kecil F08_titipan_sales F09_rekening_transaksi_kas F10_rekonsiliasi_bank
      F11_bayar_tagihan F12_kontrabon F13_faktur_pajak F14_sample_berbayar F15_setoran_gaji
      F16_buku_besar_jejak F17_laporan_keuangan F18_tutup_buku)
GAGAL=()
for f in "${URUT[@]}"; do
  echo "=== $f (peserta $KN_PESERTA)"
  if ! timeout 900 node "$f.js"; then GAGAL+=("$f"); fi
done
echo "=== potret navigasi"
timeout 900 node potret_navigasi.js | grep -c "✓" | sed 's/^/layar navigasi: /'
echo
if [ ${#GAGAL[@]} -gt 0 ]; then echo "GAGAL: ${GAGAL[*]}"; exit 1; fi
echo "SEMUA SKENARIO LULUS (peserta $KN_PESERTA)"
