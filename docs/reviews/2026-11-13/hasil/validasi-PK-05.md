Commit yang direview: 91a3ec0612952bfcc88335668ef2b3f601ba926a
Lingkungan: lapis B database tiruan (mongomock, aplikasi utuh, `backend/tests_mem`) + lapis A MongoDB asli lokal (`test_database`) dengan backend hidup di 8001 dan data acuan `restore_local_demo.sh`. Docker tidak ada (supervisor + mongod lokal). Tanpa potret layar (pilihan pemilik sesi ini: berkas:baris + reproduksi API).

# Validasi PK-05 — bayar hutang pemasok lewat satu pintu (batch B1)

Uji bantahan reviewer: `docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK05.py` (6 uji; disalin sementara ke `backend/tests_mem/`, tidak masuk gate). Hasil keseluruhan berkas itu: 4 lulus, 2 gagal — dua yang gagal adalah bantahan yang berhasil (lihat SL-01 dan SL-02).

## SL-01 — Bayar kontrabon: kas tanpa jurnal, potongan bisa terpakai dua kali, kas keluar kedua

### Temuan asli
Dibaca sendiri di `cd6963a`: `backend/services/contra_bon_service.py:1190` — urutan klaim → `_apply_deductions` → `_settle_bills` → `cash_transactions.insert_one` → `gl_service.post_cash_transaction` tanpa pengaman → catatan pembayaran → `_save`; gagal di jurnal meninggalkan kas "posted" + potongan terpakai + kunci tertinggal, dan mengulang menambah `amount_paid` lagi. `backend/routers/vendor_bills.py:501` (`/pay`) tidak menolak faktur yang sedang dipegang kontrabon.

### Perbaikan yang diperiksa
SHA unit `212b21c9`. Berkas dibaca: `backend/services/ap_payment_service.py:104-200` (cek rekening, `_preflight`, rencana faktur + penolakan faktur yang dipegang kontrabon), `backend/services/ap_payment_service.py:287-500` (`pay_payable`, `resume`, `cancel`, `_apply_allocations` ber-id tetap `payments.id $ne`, `_insert_cash` ber-`txn_id` turunan niat), `backend/services/ap_payment_service.py:550-640` (`_post_journals`, `_finish`, `_run` per langkah), `backend/routers/vendor_bills.py:613-712` (pemanggil tipis + pintu void pembayaran). Periksa-dulu (periode, akun) sebelum niat; tiap efek idempoten per id; kunci dilepas di `_finish`.

### Pintu lain
```
grep -rnE "ref_type\W+(vendor_bill|contra_bon)\b" backend/services backend/routers --include=*.py | grep -v "find\|count"
grep -rnE '"amount_paid"' backend/services backend/routers --include=*.py | grep -E '\$inc|\$set'
grep -rnE 'vendor-bills/[^ ]*/pay|contra-bons/[^ ]*/pay' frontend/src backend --include=*.jsx --include=*.js --include=*.py | grep -v "test\|seed\|poc"
```
Kesimpulan: pintu BAYAR tinggal satu (`ap_payment_service.py:455` satu-satunya `$inc amount_paid` positif untuk faktur; kas ber-`ref_type` vendor_bill/contra_bon hanya lahir di `ap_payment_service.py:172` dan `:268`). TETAPI ada pintu kedua yang menulis kas + hutang kontrabon tanpa lewat kontrabon: `POST /vendor-bills/{id}/payments/{pid}/void` (`backend/routers/vendor_bills.py:668-712`, `$inc amount_paid` negatif di `:695`) menerima baris pelunasan ber-`method: kontrabon` dan mem-void SELURUH kas kontrabon. Catatan di luar butir ini: `backend/routers/landed_cost.py:372-399` adalah pintu bayar tersendiri (voucher landed cost, bukan faktur) dengan `seq=pay_id` acak — milik temuan lain, tidak diputus di sini.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK05_bayar_hutang.py -n 0 -q                      # pelaksana: 15 lulus
cd backend && REACT_APP_BACKEND_URL=http://localhost:8001 python -m pytest -n0 -q tests/test_bp_PK05_bayar_hutang_mongo.py   # lapis A: 2 lulus
cp docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK05.py backend/tests_mem/ && cd backend && python -m pytest tests_mem/test_bantah_PK05.py -n 0 -q -s -k SL01   # reviewer: 1 lulus, 1 gagal
```
Hasil: 18 lulus, 1 gagal. Yang gagal: `test_SL01_jalur_lain_void_bayar_faktur_milik_kontrabon`.

### Upaya membantah
- [ulang] Kontrabon `cbx` (faktur 10 jt + 5 jt, potongan 1 jt) dibayar 14 jt dengan kunci `b1`, lalu dibayar lagi dengan kunci baru `b2`. Hasil: permintaan kedua ditolak 4xx; tetap 1 kas, 1 jurnal potongan, `amount_paid` faktur A tetap 10 jt — tidak terbantah.
- [jalur_lain] Sesudah kontrabon lunas, baris pelunasan faktur A (bagian kas 9 jt) di-void lewat pintu faktur `POST /api/vendor-bills/cbx_a/payments/{pid}/void`. Hasil: 200; kas kontrabon 14 jt berstatus `void` dan jurnalnya dibalik (saldo 2-1100 naik 14.000.000) tetapi buku pembantu hanya membuka 9.000.000 (faktur B tetap lunas 5 jt) dan kontrabon tetap `paid` — hutang buku besar ≠ buku pembantu selisih 5.000.000. TERBANTAH.
- [periode_tertutup] Bayar kontrabon bertanggal di periode tertutup (uji pelaksana U2 dijalankan ulang). Hasil: 409 tanpa tulisan, potongan tanpa `applied_at` — tidak terbantah.

### Putusan
Putusan: reopened
Alasan: pintu bayar sendiri sudah benar (`ap_payment_service.py:287-500`, uji U1–U16 + lapis A lulus), tetapi `test_SL01_jalur_lain_void_bayar_faktur_milik_kontrabon` membuktikan pintu void faktur (`backend/routers/vendor_bills.py:668`) tidak mengenali pelunasan milik kontrabon. Reproduksi: bayar kontrabon berisi 2 faktur dengan satu kas → `POST /api/vendor-bills/{faktur A}/payments/{id baris ber-cash_txn_id}/void` → kas 14 jt void + jurnal dibalik 14 jt, `amount_paid` hanya turun 9 jt, kontrabon tetap `paid`. Ini bentuk baru dari cacat asal "dua pintu hutang tidak saling mengunci". Arah perbaikan: tolak void dari pintu faktur bila `payments[].contra_bon_id` terisi (arahkan ke pembatalan pembayaran kontrabon), atau balik seluruh alokasi kas itu sekaligus.

## GL-03 — Bayar faktur supplier: hutang lunas, kas tanpa jurnal dan tanpa penanda

### Temuan asli
Dibaca di `cd6963a`: `backend/routers/vendor_bills.py:562` — `find_one_and_update` menaikkan `amount_paid` lebih dulu, lalu `cash_transactions.insert_one(cash_doc)` dan `gl_service.post_cash_transaction(cash_doc)` tanpa cek periode dan tanpa penanda gagal (`:583-584`): `paid_at` di periode tertutup → 500 sesudah hutang turun dan kas tersimpan.

### Perbaikan yang diperiksa
SHA unit `212b21c9`. Berkas dibaca: `backend/services/ap_payment_service.py:104-200` (`_preflight` memanggil `gl.preflight_cash` untuk kas dan kas uang muka sebelum niat lahir; `ClosedPeriodError`/`JournalValidationError` → 409 "Tidak ada yang berubah"), `backend/services/ap_payment_service.py:550-640` (jurnal lewat `cash_ledger.ensure_posted`; gagal → `gl_status: failed` di kas dan niat, bukan 500), `backend/routers/vendor_bills.py:613-712` (jawaban membawa `warning`; void memeriksa periode hari ini di `:687`).

### Pintu lain
```
grep -rnE "cash_transactions\.insert_one|create_cash\(" backend/services backend/routers --include=*.py | grep -v cash_ledger.py | wc -l     # 21 pemanggil
grep -n "post_cash_transaction\|ensure_posted\|preflight_cash" backend/services/ap_payment_service.py backend/routers/vendor_bills.py
```
Kesimpulan: untuk faktur pemasok tidak ada lagi sisip kas langsung — kas dibuat `cash_ledger.create_cash` (`ap_payment_service.py:475-494`) dan dijurnal lewat pintu tahan-gagal. Pola serupa yang disebut temuan asal di `payment_variance_service` (refund pelanggan) diperiksa di validasi PK-19.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK05_bayar_hutang.py -n 0 -q -k "U1_ or U3 or U4 or U6"       # 4 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK05.py -n 0 -q -s -k GL03                              # reviewer: 2 lulus
```
Hasil: 6 lulus, 0 gagal.

### Upaya membantah
- [periode_tertutup] Lebih bayar 3,5 jt atas faktur 3 jt dengan keputusan `ap_advance`, `paid_at` 2026-08-10 di periode tertutup (kas kedua "uang muka" ikut diperiksa?). Hasil: 409; `amount_paid` 0, 0 kas, 0 niat — tidak terbantah.
- [koreksi] Bayar 4 jt lalu void pembayaran itu. Hasil: kas `gl_status: posted` ber-`payment_intent_id`; sesudah void saldo 2-1100 kembali persis (Δ 0), faktur `posted` `amount_paid` 0 — tidak terbantah.
- [jurnal_gagal] Sisip jurnal kas dipaksa gagal (uji pelaksana U6 dijalankan ulang). Hasil: 200 ber-`warning`, kas `failed` terlihat, ulang dari panel → tepat 1 jurnal — tidak terbantah.

### Putusan
Putusan: verified
Alasan: periksa-periode sebelum efek terbukti di `backend/services/ap_payment_service.py:113-126` dan jurnal tahan-gagal di `:550-588`; `test_U1_periode_tertutup_faktur`, `test_U6_jurnal_kas_gagal_lalu_diulang`, `test_GL03_periode_tertutup_dengan_uang_muka`, `test_GL03_koreksi_bayar_lalu_void_saldo_kembali` lulus; tidak ada sisip kas langsung tersisa untuk faktur pemasok.

## SL-02 — Bayar faktur tanpa kunci idempotensi; entitas kas dari klien

### Temuan asli
Dibaca di `cd6963a`: `backend/routers/vendor_bills.py:536` — `cash_entity = _cash_owner(payload.entity_id, bill.get("entity_id"), …)` mendahulukan entitas kiriman klien; endpoint tidak mengenal kunci idempotensi sehingga dua kiriman nominal parsial = dua pembayaran (`:562-584`).

### Perbaikan yang diperiksa
SHA unit `212b21c9`. Berkas dibaca: `backend/services/ap_payment_service.py:287-369` (`intent_id_for(kind, target, key)`, `request_hash` → kunci sama isi beda 409, niat `done` → jawaban ulang; **tanpa kunci → `new_id("acak")`** di `:293`), `backend/services/ap_payment_service.py:140-193` (entitas kas = `bill.entity_id`; rekening wajib milik PT itu `:104-110`), `backend/idempotency.py:1-60` (awalan `/api/vendor-bills/`, `/api/contra-bons/` hanya aktif bila klien mengirim header), `backend/routers/vendor_bills.py:613-634`.

### Pintu lain
```
grep -rn "moneyPost\|Idempotency-Key" frontend/src/features/purchasing/VendorBillDetailPanel.jsx frontend/src/features/finance/payments/PaySupplierModal.jsx
grep -rnE 'vendor-bills/[^ ]*/pay|contra-bons/[^ ]*/pay' frontend/src backend --include=*.jsx --include=*.js --include=*.py | grep -v "test\|seed\|poc"
```
Kesimpulan: layar (`PaySupplierModal.jsx:142-144`, `moneyPost`) dan kartu asisten (`backend/services/ai_cards.py:842`) mengirim kunci. Server TIDAK mewajibkannya: pemanggil API tanpa header tetap diterima (asumsi tertulis di laporan unit).

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK05_bayar_hutang.py -n 0 -q -k "U5 or U12 or U14"            # 3 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK05.py -n 0 -q -s -k SL02                              # reviewer: 1 lulus, 1 gagal
```
Hasil: 4 lulus, 1 gagal. Yang gagal: `test_SL02_tanpa_kunci_klik_ganda`.

### Upaya membantah
- [pt_lain] Isi permintaan membawa `entity_id: ent_kanda`, `cash_type`, `created_by: penyusup` dengan rekening KSC. Hasil: kas tercatat di `ent_ksc`, `created_by` dari sesi, 0 jurnal di `ent_kanda`; rekening PT lain ditolak 400 — tidak terbantah.
- [ulang] Kunci `s1` dipakai ulang dengan nominal berbeda. Hasil: 409, tetap 1 kas — tidak terbantah.
- [ulang] Dua kiriman identik 500.000 TANPA header `Idempotency-Key`. Hasil: 200 dan 200, dua kas keluar (persis gejala asal "klik ganda nominal parsial → dua pembayaran") — terbantah untuk pemanggil tanpa kunci.

### Putusan
Putusan: perlu_keputusan_pemilik
Alasan: entitas kas dan kunci idempotensi benar bila kunci dikirim (`backend/services/ap_payment_service.py:293-304`, `test_U5_kirim_ulang_kunci_sama`, `test_SL02_kunci_sama_isi_beda_dan_entitas_dari_klien` lulus), tetapi `test_SL02_tanpa_kunci_klik_ganda` menunjukkan server masih menerima bayar tanpa kunci (dua kas). Pertanyaan untuk pemilik: apakah `POST /vendor-bills/{id}/pay` dan `/contra-bons/{id}/pay` harus MENOLAK (400) permintaan tanpa `Idempotency-Key`, atau cukup layar yang selalu mengirimnya (integrasi/skrip luar tetap bisa menggandakan)?
