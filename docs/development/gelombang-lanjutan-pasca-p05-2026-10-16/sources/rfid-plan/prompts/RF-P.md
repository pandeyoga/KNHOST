# RF-P — Connector CP30EN, print-encode, verifikasi dan recovery

**Kebutuhan:** RFID-12, RFID-13, RFID-14, RFID-15  
**Dependensi:** RF00, RF01, RF02, P02

## Pekerjaan

- [ ] Pilih runtime connector berdasarkan SDK/koneksi dan rute jaringan: Windows/Linux edge/service atau server yang dapat menjangkau printer. Reuse host existing jika terbukti cocok; tidak mengasumsikan SDK CP30 berjalan pada Android reader.
- [ ] Implementasikan job polling, warehouse/capability routing, lease/attempt stabil, persistent spool ledger serta per-item outcome. Klaim job tidak langsung berarti label tercetak.
- [ ] Validasi command RFID, resolusi/media/template dan hasil EPC. Status printing/encoding/read verification berbeda; kegagalan parsial tidak memberi ACK sukses seluruh job.
- [ ] Tangani hasil tidak pasti melalui lookup status/readback/C72 dan review; printer yang telah selesai tetapi ACK hilang tidak dikirimi ulang payload otomatis.
- [ ] Implementasikan reprint/retag berizin dengan history dan penanganan tag lama, tanpa menambah stock atau melepas guardrail movement.
- [ ] Lengkapi UI antrean/error/attempt/printer health per gudang dan kaitkan proof C72; cetak dokumen SJ dipisahkan dari RFID encoding.
- [ ] Uji crash sebelum/sesudah kirim, encoder failure, lease expire/renew, partial batch, double connector dan kegagalan server setelah ACK durable.

## Acceptance

RACC-22, RACC-23, RACC-24, RACC-25, RACC-26, RACC-27, RACC-28, RACC-29, RACC-30. Baca [matriks acceptance](../ACCEPTANCE_RFID.md).

**Gate:** CP30EN nyata, connector, EPC chip, hasil per item, C72 verification dan recovery mempunyai evidence; physical output ambigu tidak ditutupi auto-reprint.

## Prompt agent

```text
Kerjakan tahap RF-P — Connector CP30EN, print-encode, verifikasi dan recovery pada repo ERP dan aplikasi Chainway yang benar-benar digunakan. Baca README, DEVELOPMENT_PLAN_RFID, API_CONTRACT, INTEGRATION_WITH_MAIN_PLAN, dan RFID_BACKLOG.json dalam folder addendum ini, serta instruksi repo.

Scope: RFID-12, RFID-13, RFID-14, RFID-15. Mulai setelah RF00, RF01, RF02, P02 atau kerjakan hanya bagian independen yang terdokumentasi. Catat commit aktual dan evaluasi implementasi existing sebelum menulis ulang. Pengguna menetapkan UR300, C72 dan CP30EN; validasi label/firmware/SDK/media, jangan mengganti nama varian diam-diam.

Laksanakan rincian pekerjaan pada file tahap ini, seluruh consumer API/UI/SDK yang relevan, compatibility data/client lama, serta scope device/operator/lokasi. Pertahankan SSOT roll dan dokumen ERP. Scan radio tidak menambah/mengurangi qty stok langsung.

Jalankan acceptance RACC-22, RACC-23, RACC-24, RACC-25, RACC-26, RACC-27, RACC-28, RACC-29, RACC-30 dan tes regresi yang relevan. Catat input/output, raw hardware read, build/APK/service/SDK, commit server, offline/retry/partial failure, metadata/ACK, dan evidence. Simulator atau paste EPC tidak memenuhi hardware validation.

Gate selesai: CP30EN nyata, connector, EPC chip, hasil per item, C72 verification dan recovery mempunyai evidence; physical output ambigu tidak ditutupi auto-reprint. Jika unit/SDK atau keputusan operasi belum ada, tandai item spesifik waiting_hardware/waiting_decision dan lanjutkan pekerjaan yang independen. Jangan memalsukan hasil atau menutup seluruh tahap dari build saja.

Simpan laporan dan bukti di evidence/RF-P/, update RFID_BACKLOG.json kemudian render TRACKER.md. Status setelah implementasi dan tes developer adalah implemented_pending_validation; validated memerlukan verifikasi hasil yang dapat diperiksa pada versi yang sama.

Serahkan commit/build, perubahan perilaku, kontrak API dan SDK, konfigurasi/migrasi, tes, issue terbuka serta batas validasi. Jangan membeli hardware, menghubungi vendor, push, atau deploy produksi otomatis tanpa otorisasi yang berlaku.
```

[Kontrak API](../API_CONTRACT.md) · [Tracker](../RFID_BACKLOG.json)
