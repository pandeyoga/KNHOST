#!/usr/bin/env bash
# Jalankan SEMUA materi pelatihan berurutan mengikuti kurikulum (src/kurikulum.json), seperti di kelas:
#   Bagian 0 Pengantar → 1 Fondasi & Konfigurasi → 2 Alur ujung ke ujung → 3 Praktik per siklus → 4 Manajer,
# lalu potret navigasi. Setiap skrip login lewat LAYAR dengan akun peran dan mencocokkan buku (jurnal, saldo, status).
#
#   KN_PESERTA=01 bash docs/pelatihan/2026-11-18_keuangan/uji/jalankan_semua.sh
#
# Peserta:
#   KN_PESERTA      peserta kelas — semua praktik Finance (F, K, H) berurutan di akun yang SAMA (bawaan 01)
#   KN_PESERTA_A1   peserta peraga alur Pesanan sampai Uang Masuk (bawaan 21; pelanggan segar)
#   KN_PESERTA_A2   peserta peraga alur Pengadaan sampai Bayar (bawaan 31; akun + pemasok saja)
#   KN_PESERTA_A3J  peserta peraga retur penjualan (bawaan 41) · KN_PESERTA_A3B retur pembelian (42) ·
#   KN_PESERTA_A3T  tukar barang (43) — alur 2 diperagakan pelatih dengan akun tiap peran, jadi dokumennya terpisah
#                   dari dokumen latihan peserta kelas.
#   KN_PESERTA_S1…S4  situasi khusus bagian 5 (bawaan 61, 66, 72, 76; peserta peraga tersendiri). S2: akun + pemasok
#                   saja; S3: hanya --hanya a_dasar:akun, a_dasar:mitra, a_dasar:so_ (dua SO terkirim BELUM dibayar).
# Data: backend/scripts/seed_pelatihan_keuangan_kn.py --mulai NN --peserta NN untuk peserta kelas, A1, A3*;
#       --hanya a_dasar:akun lalu --hanya a_dasar:mitra untuk A2. Peserta yang sudah dipakai tidak bisa diulang.
# Butuh backend :8001, frontend :3000, dan `python3` (KN_PY) yang bisa menjalankan skrip backend (F04 langkah 9).
# KN_HANYA="K0 H0" → hanya skrip yang namanya diawali salah satu awalan itu (untuk mengulang sebagian).
set -u
cd "$(dirname "$0")"
export KN_PESERTA="${KN_PESERTA:-01}"
A1="${KN_PESERTA_A1:-21}"; A2="${KN_PESERTA_A2:-31}"
A3J="${KN_PESERTA_A3J:-41}"; A3B="${KN_PESERTA_A3B:-42}"; A3T="${KN_PESERTA_A3T:-43}"
S1="${KN_PESERTA_S1:-61}"; S2="${KN_PESERTA_S2:-66}"; S3="${KN_PESERTA_S3:-72}"; S4="${KN_PESERTA_S4:-76}"

# berkas[@peserta] — urutan = kurikulum
URUT=(
  # 0 · Pengantar
  F01_orientasi
  # 1 · Fondasi & Konfigurasi
  konfigurasi/K01_bagan_akun konfigurasi/K02_pemetaan_akun konfigurasi/K03_profil_pt_periode
  konfigurasi/K04_rekening_kas_bank konfigurasi/K05_aturan_keuangan_pajak konfigurasi/K06_termin_plafon
  konfigurasi/K07_hak_akses_persetujuan konfigurasi/K08_nomor_naskah_dokumen sdm/K09_konfigurasi_sdm
  # 2 · Alur ujung ke ujung (peraga pelatih; A4 = SDM, diuji di 3.4; A5 = ringkasan, diuji di 3.3/3.5/4)
  "e2e/A1_order_to_cash@$A1" "e2e/A2_procure_to_pay@$A2"
  "e2e/A3_retur_penjualan@$A3J" "e2e/A3_retur_pembelian@$A3B" "e2e/A3_retur_tukar@$A3T"
  # 3.1 Piutang
  F02_pelunasan_penuh F03_bayar_sebagian F04_lebih_bayar_titipan F05_rencana_denda F06_kredit_plafon
  F13_faktur_pajak F14_sample_berbayar
  # 3.2 Hutang
  F11_bayar_tagihan F12_kontrabon
  # 3.3 Kas & Bank
  F07_kas_kecil F08_titipan_sales F09_rekening_transaksi_kas F10_rekonsiliasi_bank
  # 3.4 SDM & Gaji
  sdm/H01_karyawan_baru sdm/H02_masukan_gaji sdm/H03_proses_gaji sdm/H04_bayar_gaji_slip F15_setoran_gaji
  # 3.5 Buku Besar & Dokumen
  F16_buku_besar_jejak
  # 4 · Manajer
  F17_laporan_keuangan F18_tutup_buku
  # 5 · Situasi khusus & koreksi (peraga; peserta tersendiri)
  "situasi/S1_amandemen_penjualan@$S1" "situasi/S2_amandemen_pembelian@$S2"
  "situasi/S3_situasi_penjualan@$S3" "situasi/S4_koreksi_pembatalan@$S4"
)

pilih() {   # true bila skrip termasuk KN_HANYA (kosong = semua)
  [ -z "${KN_HANYA:-}" ] && return 0
  local nama; nama="$(basename "$1")"
  for a in $KN_HANYA; do case "$nama" in "$a"*) return 0 ;; esac; done
  return 1
}

if [ -z "${KN_HANYA:-}" ]; then rm -rf hasil/F[0-9]* hasil/K[0-9]* hasil/H[0-9]* hasil/A[0-9]* hasil/S[0-9]* hasil/_navigasi; fi
GAGAL=(); LULUS=0
mulai_semua=$(date +%s)
for item in "${URUT[@]}"; do
  f="${item%@*}"; p="$KN_PESERTA"; [ "$item" != "$f" ] && p="${item#*@}"
  pilih "$f" || continue
  echo "=== $f (peserta $p) $(date +%H:%M:%S)"
  if KN_PESERTA="$p" timeout 1500 node "$f.js"; then LULUS=$((LULUS + 1)); else GAGAL+=("$f@$p"); fi
done
if [ -z "${KN_HANYA:-}" ]; then
  echo "=== potret navigasi"
  timeout 900 node potret_navigasi.js | grep -c "✓" | sed 's/^/layar navigasi: /'
fi
echo
echo "lulus: $LULUS skrip · waktu: $(( ($(date +%s) - mulai_semua) / 60 )) menit"
if [ ${#GAGAL[@]} -gt 0 ]; then echo "GAGAL: ${GAGAL[*]}"; exit 1; fi
echo "SEMUA MATERI LULUS (peserta kelas $KN_PESERTA)"
