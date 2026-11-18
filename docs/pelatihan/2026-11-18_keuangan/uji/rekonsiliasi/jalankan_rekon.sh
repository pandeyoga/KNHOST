#!/usr/bin/env bash
# Uji jalan REKONSILIASI BANK lanjutan R1–R9 (rekening koran Excel) untuk SATU peserta, berurutan (R8 memakai hasil R2,
# R9 memakai hasil R1–R8). Butuh Node + Playwright, backend :8001, frontend :3000, data & berkas Excel peserta:
#
#   cd backend && python scripts/seed_pelatihan_keuangan_kn.py --mulai 85 --peserta 85 --hanya a_dasar:akun,a_dasar:mitra,g_rekon
#   cd backend && python scripts/buat_mutasi_bank_latihan.py --mulai 85 --peserta 85 \
#        --keluar ../docs/pelatihan/2026-11-18_keuangan/rekonsiliasi/mutasi
#   KN_PESERTA=85 bash docs/pelatihan/2026-11-18_keuangan/uji/rekonsiliasi/jalankan_rekon.sh
#
# Mesin tanpa Node (Docker Desktop): lihat jalankan_rekon_docker.sh. Hasil: uji/hasil/R1…R9/hasil.json + tangkapan layar.
# KN_HANYA="R4 R5" → hanya skrip berawalan itu.
set -u
cd "$(dirname "$0")"
export KN_PESERTA="${KN_PESERTA:-85}"
GAGAL=()
for f in R1_kode_bayar R2_tanpa_kode R3_bayar_pemasok R4_pecah R5_gabung R6_biaya_bunga R7_titipan R8_lepas R9_impor_ulang; do
  if [ -n "${KN_HANYA:-}" ]; then
    cocok=0; for a in $KN_HANYA; do [[ "$f" == "$a"* ]] && cocok=1; done
    [ $cocok -eq 1 ] || continue
  fi
  echo "=== $f (peserta $KN_PESERTA)"
  node "$f.js" || GAGAL+=("$f")
done
echo
if [ ${#GAGAL[@]} -gt 0 ]; then echo "GAGAL: ${GAGAL[*]}"; exit 1; fi
echo "SEMUA LULUS (peserta $KN_PESERTA)"
