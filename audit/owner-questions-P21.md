# Pertanyaan Keputusan Pemilik — 5 kasus audit terakhir (P21, 2026-10-04)

Kelima kasus ini sudah diuji sejauh yang bisa dilakukan di preview. Yang tersisa adalah keputusan bisnis, data acuan resmi,
atau perangkat/lingkungan nyata. Satu jawaban per kasus cukup untuk menutupnya (lulus, risiko diterima, atau dijadwalkan).

| Kasus | Yang sudah terbukti | Yang belum bisa dibuktikan tanpa pemilik |
|---|---|---|
| COMM-04 Komisi & biaya kampanye | Komisi naik/turun/batal terkoreksi di GL (7/7, P17) | Biaya kampanye marketing hanya anggaran — belum ada jurnal |
| HR-04 Pajak/BPJS akhir tahun & PHK | PPh21 TER masa terakhir & BPJS dihitung software (HR-01) | Kebenaran tarif/plafon 2026 & hasil Desember/PHK vs dataset resmi |
| RFID-05 Offline, baca ganda, arah lintas | Replay, baca ganda, arah lintas (RF-16) diuji simulasi | Putus-sambung perangkat reader/gate NYATA |
| OPS-01 Bootstrap & indeks deployment | Bootstrap & semua indeks lulus di preview | Eksekusi di database PRODUKSI |
| AUDIT-03 Pemindai secret pre-commit & CI | Skrip & `.github/workflows/secret-scan.yml` ada, uji lokal lulus | Run GitHub Actions nyata yang memblokir commit bersecret |

## Pertanyaan

1. **COMM-04 — Biaya kampanye marketing dicatat ke buku besar?**
   - (a) Ya: jurnal Beban Pemasaran saat tagihan vendor/realisasi biaya kampanye diposting, dibalik saat dibatalkan *(disarankan)*
   - (b) Ya, tapi akrual saat kampanye disetujui (sebesar anggaran), lalu disesuaikan ke realisasi
   - (c) Tidak — kampanye cukup anggaran; biaya tetap lewat tagihan vendor biasa (kasus ditutup sebagai "di luar cakupan GL")
2. **HR-04 — Siapa yang menyediakan dataset acuan pajak/BPJS?**
   - (a) Konsultan pajak/akuntan menyerahkan 3–5 slip contoh (Desember + 1 PHK) hasil hitung resmi; kami cocokkan per rupiah *(disarankan)*
   - (b) Pemilik mengonfirmasi tarif & plafon BPJS 2026 yang tertera di Pusat Pengaturan (Kesehatan 12 jt, JP 10.042.300) dan menerima hasil software
   - (c) Tunda sampai tutup tahun pertama (risiko diterima, dicatat)
3. **RFID-05 — Uji perangkat reader/gate nyata?**
   - (a) Jadwalkan uji lapangan: tim gudang mencabut jaringan reader 10 menit lalu menyambungkan lagi; kami cek tidak ada baca hilang/ganda *(disarankan)*
   - (b) Belum ada perangkat — tutup sebagai "diuji simulasi", uji nyata saat RFID dipasang
   - (c) RFID tidak dipakai dalam waktu dekat — tandai tidak berlaku
4. **OPS-01 — Validasi bootstrap & indeks di produksi?**
   - (a) Lakukan saat deploy pertama: jalankan validasi indeks sesudah deploy dan lampirkan hasilnya *(disarankan)*
   - (b) Belum akan deploy — tetap partial sampai deploy
5. **AUDIT-03 — Bukti pemindai secret di GitHub Actions?**
   - (a) Pemilik mengaktifkan Actions di repo, kami siapkan cabang uji berisi secret palsu; pemilik menekan Save to GitHub & mengirim tautan run yang gagal (= terblokir) *(disarankan)*
   - (b) Cukup uji lokal pre-commit — terima risiko CI
   - (c) Tunda
