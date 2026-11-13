# PM-T5 — Virtual account dan QRIS dinamis lewat penyedia pembayaran (tertahan)

| | |
|---|---|
| Gelombang | Modul cara bayar dan rekening |
| Jenis | fitur |
| Risiko | tinggi |
| Prasyarat | PM-T3 |
| Menutup temuan | — |
| Keputusan | K-35 |
| Standar | §1, §2, §3.4 (N1, N4), §5 (D7) |
| Lingkungan uji | A |

**Status awal `tahan` — titik henti H8** (butuh kunci API dan akses layanan luar) dan K-35 ("tahap 1 tanpa penyedia
pembayaran"). Berkas ini sengaja ringkas; rincian penuh ditulis setelah pemilik menjawab pertanyaan di bagian akhir.

## Tujuan

Pembayaran ke virtual account atau QRIS buatan sistem langsung menjadi kwitansi "Terverifikasi bank" tanpa diketik orang.

## Keadaan sekarang

`[dibaca]` pada `3132cc4`: tidak ada integrasi penyedia pembayaran. Cara bayar `va` disiapkan PM-T1 dalam keadaan
nonaktif; kwitansi dibuat di `backend/services/ar_receipt_service.py:419` (`create_receipt`); pencocokan mutasi di
`backend/services/bank_recon_service.py:673` (`auto_match`). Biaya dan syarat bank atau penyedia belum diperiksa
(`docs/finance/rencana-2026-11-13/07_PAJAK_DAN_PEMBAYARAN.md` §A3.8).

## Perubahan

Lingkup yang direncanakan (belum boleh dikerjakan):

- **Data:** nomor virtual account per (pelanggan, PT) atau per baris tagihan; catatan pemberitahuan berkunci unik.
- **Server:** lapisan penyedia yang bisa diganti; pembuat nomor VA / QRIS; penerima pemberitahuan yang idempoten,
  memeriksa tanda tangan, dan mengonfirmasi ulang ke penyedia sebelum memanggil `create_receipt` (`bank_verified: true`).
- **Pengaturan:** penyedia aktif dan rekening penampung per PT; rahasia lewat mekanisme rahasia hasil KP-T8.
- **Izin dan peran:** memakai `cash.configure`. **Layar:** blok instruksi bayar (PM-T2) mencetak nomor VA atau QRIS.

## Uji penerimaan

Ditulis saat unit dilepas. Syarat minimal yang sudah pasti: pemberitahuan yang sama dua kali → satu kwitansi; tanda
tangan salah → 401 tanpa tulisan; nominal ≠ tagihan → menjadi titipan, tidak dialokasikan otomatis; pemberitahuan untuk
PT-A tidak pernah membuat kwitansi di PT-B.

## Langkah kerja

Pemilik menjawab pertanyaan di bawah → reviewer mengubah status menjadi `siap` → berkas ini dilengkapi menjadi
spesifikasi penuh (bentuk seperti PM-T3) → dikerjakan di lingkungan uji penyedia dalam dua serah-terima.

## Di luar lingkup

Kartu / EDC (cara bayar `edc`), pembayaran keluar lewat penyedia, penagihan otomatis berulang.

## Asumsi dan risiko

Yang harus diputuskan pemilik: (1) apakah volume transfer membenarkan biaya penyedia; (2) bank atau penyedia mana dan
siapa penanda tangan kerja samanya; (3) virtual account per pelanggan (cocok untuk pembayaran gabungan) atau per
tagihan; (4) rekening penampung tiap PT dan pemegang kunci API; (5) apakah QRIS dinamis ikut.

- `ASUMSI:` kode bayar (PM-T2) dan status terverifikasi (PM-T3) sudah menutup sebagian besar risiko salah transfer.
- `RISIKO:` penerima pemberitahuan adalah pintu masuk dari internet; salah rancang berarti kwitansi palsu.
