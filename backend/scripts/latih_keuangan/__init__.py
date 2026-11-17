"""Data latihan Pelatihan Keuangan (18 Nov 2026) — per peserta, lewat ENDPOINT RESMI (aturan, jurnal, saldo, audit asli).

Tiap modul `*.py` di paket ini memuat `PREPS = [(kunci, fungsi_async(ctx, peserta) -> dict)]`. Skrip induk
`scripts/seed_pelatihan_keuangan_kn.py` menjalankan semua PREPS untuk tiap peserta (urut nama modul, lalu urut daftar),
mencatat hasilnya di `migrations.pelatihan_keuangan` sehingga dijalankan ulang tidak menggandakan.

Kontrak fungsi prep: `async def fn(lc: LatihCtx, p: Peserta) -> dict` — dict hasil (nomor dokumen, nominal, catatan)
disimpan di kartu peserta dan dicetak di akhir (Kartu Peserta). Gagal = lempar exception (skrip lanjut ke prep lain).
"""
