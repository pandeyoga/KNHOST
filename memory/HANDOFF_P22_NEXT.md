# HANDOFF — P22 (disiapkan 2026-10-04, akhir P21) → sesi berikutnya

> Bahasa user: **Indonesia**. Setup lingkungan: `memory/HANDOFF_P16_2026-10-09.md` §1 (seed dengan `KN_DISABLE_SCHEDULER=1`),
> lalu `memory/HANDOFF_P21_2026-10-04.md` §0 (kunci OpenAI di DB, `ai.enabled=true`, `POST /api/ai/facts/rebuild` sesudah seed).
> Wajib akhir sesi: `bash scripts/git_sync_check.sh --fix` (agen P21 TIDAK menjalankannya — git write), lalu user **Save to GitHub**.

## 0. Status saat serah terima
- Cakupan audit (`audit/coverage.json`): **tested_pass 93 · blocked 3 · partial 2 · n/a 1**. Validator `python3 audit/tools/validate.py` bersih (selain tautan arsip lama).
- Keputusan pemilik P21 tercatat di `audit/policy-decisions.json` PG04–PG08 (status `decided`) + `audit/owner-questions-P21.md`.
- Tanya KN live (gpt-6-sol / gpt-6-luna). Eval terakhir: tool 94,2 · argumen 90,0 · angka 98,3 · hak akses 15/15; 7 soal punya alternatif sah.
- Integritas data baseline: PASS 246 · FAIL 2 (KANDA/SO-00001 flag backorder + 1 bawaan seed) · WARN 0.

## 1. PRIORITAS SESI BERIKUT — COMM-04: posting GL biaya kampanye marketing (keputusan PG04)
**Keputusan:** jurnal **Beban Pemasaran** saat biaya kampanye **benar-benar keluar** (realisasi / tagihan vendor kampanye diposting); **dibalik** bila dibatalkan. Anggaran (`marketing_campaigns.budget`) TIDAK dijurnal.
**Kondisi kode sekarang:** kampanye hanya punya `budget` (`services/marketing_service.py::create_campaign/update_campaign`); tidak ada catatan biaya/realisasi; `vendor_bills` tidak punya `campaign_id`; GL: `services/gl_service.py` (`post_vendor_bill` L~1755, pola koreksi `post_incentive_accrual` L~2680, `post_petty_cash_settlement` L~2760).
**Rencana minimal (cek dulu CoA untuk akun beban pemasaran; bila belum ada, tambahkan lewat seed CoA/konfigurasi akun, jangan hardcode):**
1. Realisasi biaya kampanye: koleksi `marketing_campaign_costs` (id, campaign_id, entity_id, tanggal, uraian, amount, source=`direct|vendor_bill`, vendor_bill_id, status `posted|void`, journal_id) + endpoint `POST/GET /api/marketing/campaigns/{cid}/costs`, `POST .../costs/{id}/void` (izin finance/marketing manager — ikuti `require_permission` modul marketing/finance yang ada).
2. GL: `direct` → Dr Beban Pemasaran / Cr Kas-Bank (akun dipilih); `vendor_bill` → tagihan vendor dengan `campaign_id` memakai akun beban pemasaran pada barisnya (bukan persediaan) sehingga `post_vendor_bill` yang menjurnal (jangan jurnal dua kali). Void → jurnal balik (reversal) satu kali, idempoten (pakai `atomic_claim.claim` + daftarkan koleksi di `routers/saga_locks.py::LOCKED_COLLECTIONS` — test penjaga `tests/test_saga_lock_registry.py` akan gagal bila lupa).
3. Periode tutup: hormati penguncian periode GL yang ada (void di periode tertutup → reversal di periode berjalan).
4. Laporan kampanye: tampilkan Anggaran vs Realisasi (sisa anggaran) di halaman kampanye.
5. Bukti audit: harness `audit/iterations/<tanggal>-P22-.../repro_p22.py` (pola `repro_p21.py`, self-clean): posting → saldo akun beban naik tepat; void → kembali 0, tidak dobel saat void diulang/bersamaan; tagihan vendor kampanye dijurnal sekali; integritas tanpa pelanggaran baru. Lalu `audit/tools/set_status.py` → COMM-04 `tested_pass`.

## 2. Menunggu pihak luar (jangan dikerjakan tanpa input)
| Kasus | Status | Yang ditunggu | Cara menutup |
|---|---|---|---|
| HR-04 | blocked | 3–5 slip resmi konsultan pajak (Desember + 1 PHK) | Masukkan sebagai dataset acuan, cocokkan PPh21/BPJS per rupiah via harness; selisih → perbaiki rumus |
| OPS-01 | partial | Deploy produksi pertama | Sesudah deploy, jalankan validasi bootstrap & indeks di produksi, lampirkan hasil |
| RFID-05 | tested_pass (simulasi) | Perangkat RFID dipasang | Uji putus-sambung reader 10 menit; cek tak ada baca hilang/ganda |
| AUDIT-03 | tested_pass (lokal) | — | CI GitHub Actions = risiko diterima pemilik |

## 3. Backlog lain
- P1 test lama basi (bukan regresi): `test_iter39/40/test_design_studio_flow` (DESIGN_ID seed lama → cari ID dinamis), `test_iter314/315` (alasan lepas kunci ≥10 karakter), `test_iter302` (finance kini punya `approval.view` — sesuaikan dengan kebijakan).
- P2 Tanya KN: harga gpt-6-sol/luna masih "perkiraan" (`ai_cost`); nama field mentah kadang muncul di jawaban (mis. `completion_hold`) — pertimbangkan label ramah di `get_document`.
- P2 Fitur delegasi persetujuan (belum ada di sistem; DOC-03 mencatat n/a).

## 4. Yang dikerjakan P21 (jangan diregresi)
Lihat `memory/HANDOFF_P21_2026-10-04.md` §1 & §4 dan PRD bagian P21/P21b/P21c. Ringkas P21c: tombol Tanya KN + pertanyaan bawaan di detail **retur penjualan, retur pembelian, tagihan supplier, order makloon**; `get_document` mendukung `sales_return`/`purchase_return` + ringkasan bayar tagihan (`bill_financials`), langkah makloon, milestone retur (`tests/test_tanya_kn_doc_context.py`).
