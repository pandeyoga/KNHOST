# Jawaban owner — 2026-10-19 (sesi C, lanjutan)

Sumber: chat sesi E1 dengan owner (pandeyoga), 2026-10-19. Dicatat apa adanya. **Belum diimplementasi**; rancangan ada di [RANCANGAN_PEMETAAN_AKUN_DAN_CUTLOSS.md](../RANCANGAN_PEMETAAN_AKUN_DAN_CUTLOSS.md), rencana kerja di [HANDOFF_SESI_2026-10-19D.md](HANDOFF_SESI_2026-10-19D.md).

| ID | Pertanyaan | Jawaban owner (kutipan/ringkas setia) | Requirement |
|---|---|---|---|
| CUT-01 | Potongan cacat cutloss (mis. 15 yd dari roll 120 yd) masuk stok BS atau dibuang? | "masuk sebagai BS atau dibuang, **user dapat memilih**" — pilihan per kasus, bukan aturan tetap. Sistem memecah roll di stok. | LN-092 (lanjutan KLR-01) |
| GL-01 | Akun pembukuan ongkir retur (KLR-11) | "buatkan **konfigurasi** dimana **semua kebutuhan fitur yang disambungkan ke akun**; fitur UI-nya harus **user friendly**." Ongkir retur langsung tercatat di jurnal sesuai penanggung yang dipilih per kasus. | LN-091 (lanjutan KLR-11), lintas modul |

Hal yang belum dijawab di dua keputusan ini dicatat sebagai pertanyaan baru CUT-02..05 dan GL-02..08 di bagian "Butuh persetujuan" pada HANDOFF_SESI_2026-10-19D.md. Selama belum dijawab, development memakai default yang tertulis di sana dan menandainya sebagai asumsi, bukan kebijakan.
