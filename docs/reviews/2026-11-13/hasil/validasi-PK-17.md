Commit yang direview: 91a3ec0612952bfcc88335668ef2b3f601ba926a
Lingkungan: lapis B database tiruan (mongomock, aplikasi utuh) + backend hidup di 8001 dengan MongoDB asli lokal (`test_database`, data acuan `restore_local_demo.sh`) untuk cek akun demo. Docker tidak ada. Tanpa potret layar (pilihan pemilik sesi ini) — sisi layar (menu peran) TIDAK diperiksa.

# Validasi PK-17 — nominal keuangan hanya untuk yang berizin (batch B1)

Uji bantahan reviewer: `docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK17.py` (8 uji: 6 lulus, 2 gagal — dua yang gagal adalah bantahan yang berhasil, lihat IA-01 dan IA-03).

## IA-01 — Jejak Dokumen hanya dijaga izin "lihat dokumen"; pencarian lintas jenis dokumen memuat nominal

### Temuan asli
Dibaca di `cd6963a`: `backend/routers/documents.py:97` (`document_trace`) dan `backend/routers/documents.py:142` (`document_trace_search`) hanya memanggil `require_permission(request, "document", "view")` lalu mengembalikan simpul lengkap dengan `amount` untuk semua jenis dokumen (PO, tagihan, landed cost, kontrabon, kas).

### Perbaikan yang diperiksa
SHA unit `376bd219`. Berkas dibaca: `backend/services/doc_refs_service.py:100-232` (peta `DOC_TYPES`; kolom `perm` per jenis), `backend/services/doc_refs_service.py:405-425` (`SOURCE_PERMISSION` diturunkan dari `perm`; `may_see_amount`; `redact_node` mengosongkan `amount`, `can_open`, `pdf_doc_type`), `backend/routers/documents.py:92-161` (empat pintu jejak/cetak/rujukan/cari meneruskan `viewer_perms`), `backend/routers/documents.py:189-205` + `backend/services/document_relations_service.py:240-266` (graf relasi, pintu lain). Jenis yang TIDAK punya `perm` tidak disaring — termasuk `credit_note` (`doc_refs_service.py:182`).

### Pintu lain
```
grep -n "viewer_perms" -r backend/services backend/routers --include=*.py | grep -v doc_refs_service
grep -n "amount" backend/services/document_relations_service.py
python - <<'P'   # (di dalam uji) jenis dokumen tanpa perm
from services import doc_refs_service as r; print(sorted(t for t, m in r.DOC_TYPES.items() if not m.get("perm")))
P
```
Kesimpulan: empat pintu jejak memakai penyaring yang sama. Dua celah: (1) 19 jenis tanpa `perm`, satu di antaranya bernilai uang: `credit_note` (nota kredit/debit) — nominalnya tetap terbaca oleh peran ber-`document.view` saja; (2) `GET /documents/relations/purchase_order/{id}` (`document_relations_service.py:248` dan `:262`) mengirim `amount` landed cost/tagihan TANPA penyaring izin — saat ini tidak bocor hanya karena field yang dibaca (`total_amount`/`amount`) tidak ada di dokumen tagihan (`grand_total`), jadi kebetulan `None`, bukan dijaga.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK17_nominal_berizin.py -n 0 -q -k "U04 or U05 or U06"           # pelaksana: 3 lulus
cp docs/reviews/2026-11-13/hasil/bukti/review-B1/test_bantah_PK17.py backend/tests_mem/ && cd backend && python -m pytest tests_mem/test_bantah_PK17.py -n 0 -q -s -k IA01   # reviewer: 2 lulus, 1 gagal
```
Hasil: 5 lulus, 1 gagal. Yang gagal: `test_IA01_tanpa_izin_jenis_tanpa_perm_nota_kredit_dan_kontrabon`.

### Upaya membantah
- [jalur_lain] Pembaca ber-`purchase_order.view` + `document.view` membuka enam pintu (jejak PO, rujukan PO, cari, cetak, jejak berjangkar tagihan, rujukan tagihan) dan seluruh teks jawaban dicari angka 27.500.000 / 12.000.000. Hasil: tidak ada nominal tagihan/kontrabon di teks mana pun — tidak terbantah.
- [jalur_lain] Pembaca yang sama membuka `/api/documents/relations/purchase_order/po_x`. Hasil: 200 tanpa nominal tagihan (karena field salah baca, lihat Pintu lain) — tidak terbantah, tetapi tanpa penjaga.
- [tanpa_izin] Peran yang HANYA memegang `document.view` mencari "UJI" lewat `/api/documents/trace-search` sesudah nota kredit Rp 3.333.333 disisipkan. Hasil: simpul `credit_note` membawa `amount: 3333333.0` (PO/tagihan/kontrabon tersaring) — TERBANTAH untuk nota kredit.

### Putusan
Putusan: reopened
Alasan: penyaring `redact_node` (`backend/services/doc_refs_service.py:419-425`) benar untuk jenis ber-`perm` (uji U04–U06 lulus), tetapi `test_IA01_tanpa_izin_jenis_tanpa_perm_nota_kredit_dan_kontrabon` membuktikan nominal nota kredit masih terbaca tanpa izin keuangan karena `credit_note` tidak punya `perm` di `backend/services/doc_refs_service.py:182`. Reproduksi: peran dengan `document.view` saja → `GET /api/documents/trace-search?q=<nomor nota kredit>` → `amount` terisi. Arah: beri `perm` pada `credit_note` (dan tinjau `doc_amendment`), dan pasang penyaring yang sama di `document_relations_service` supaya tidak bergantung pada salah-baca field.

## IA-02 — Membuka dokumen tidak memeriksa menu peran; pagarnya tinggal izin API yang lebih lebar dari menu

### Temuan asli
Dibaca di `cd6963a`: `frontend/src/hooks/useAppNavigation.js:72` (`openDocument` langsung `handleNavSelect(link.nav_id || link.view, …)` tanpa cek menu peran); `backend/routers/bank.py:49` dan `backend/routers/bank.py:68` (buat/ubah rekening cukup `cash.create`); bawaan gudang memegang `vendor_bill.view`, `landed_cost.view`, `input_tax.view` tanpa menunya.

### Perbaikan yang diperiksa
SHA unit `376bd219`. Berkas dibaca: `backend/routers/bank.py:38-140` (buat/ubah rekening kini `cash.configure` di `:78` dan `:100`, pesan 403 untuk manusia), `backend/permissions_config.py:20-60` (bawaan admin; `interco_finance` "HANYA admin/manager" menurut komentarnya) + diff `git show 376bd219 -- backend/permissions_config.py` (`cash.configure` untuk admin/manajer/finance; `vendor_bill`/`landed_cost`/`input_tax` dicabut dari bawaan gudang), `backend/services/doc_refs_service.py:405-425` (tombol buka dimatikan `can_open: False` bila izin sumber tidak dipegang), `frontend/src/hooks/useAppNavigation.js:78-100` (menu diturunkan dari menu peran; layar di luar menu TETAP dibuka — "server yang menjaga datanya").

### Pintu lain
```
grep -n "require_permission\|require_any" backend/routers/bank.py
curl -s -o /dev/null -w '%{http_code}' localhost:8001/api/interco/margin-report -H "Authorization: Bearer <token finance@…>" -H 'X-Entity-Id: ent_ksc'    # 200
```
Kesimpulan: pintu rekening tertutup bagi pemegang `cash.create` saja (PATCH 403; tidak ada POST `bank-account-changes` langsung — 405). Dua hal tersisa: (1) matriks izin TERSIMPAN tidak ikut dicabut saat proses awal — butuh `scripts/apply_pk17_role_cleanup.py --apply` (titik henti H3); (2) bagian temuan asal "Finance melihat margin tanpa menunya" tidak disentuh unit ini: akun demo `finance@…` mendapat 200 di `/api/interco/margin-report` (izin bawaan `interco_finance.view`).

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK17_nominal_berizin.py -n 0 -q -k "U07 or U08 or U09 or U10 or U14"   # pelaksana: 5 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK17.py -n 0 -q -s -k IA02                                       # reviewer: 2 lulus
```
Hasil: 7 lulus, 0 gagal.

### Upaya membantah
- [tanpa_izin] `warehouse` dan `warehouse_admin` membuka `/api/vendor-bills`, `/api/vendor-bills/vb_x`, `/api/landed-cost`, `/api/input-tax-invoices`; pemegang `cash.view/create` mem-PATCH rekening. Hasil: semua 403/404; nama rekening tidak berubah — tidak terbantah.
- [data_lama] Matriks tersimpan diberi lagi `warehouse_admin.vendor_bill: ["view"]` (keadaan sebelum PK-17) lalu `bootstrap.run_bootstrap()`. Hasil: izin itu BERTAHAN sesudah start — sesuai dokumentasi unit (pencabutan = skrip `--apply`), jadi instalasi yang ada tetap bocor sampai skrip dijalankan.
- [layar] Tidak dijalankan (tanpa potret layar): apakah layar di luar menu peran masih bisa dibuka lewat tautan dokumen. Hasil: tidak diuji; kode `useAppNavigation.js:80` menyatakan layar tetap dibuka dan server yang menjaga.

### Putusan
Putusan: perlu_keputusan_pemilik
Alasan: bagian rekening dan bawaan gudang benar (`backend/routers/bank.py:78`, `test_PK17_U09_buat_rekening_butuh_cash_configure`, `test_PK17_U08_ekspor_tagihan_tertutup_bagi_gudang`, `test_IA02_tanpa_izin_gudang_pintu_tagihan_dan_rekening` lulus), tetapi dua hal butuh keputusan: (1) kapan `scripts/apply_pk17_role_cleanup.py --apply` dijalankan di data nyata — sebelum itu `test_IA02_data_lama_matriks_tersimpan_gudang` menunjukkan izin lama gudang bertahan; (2) bolehkah Finance melihat laporan margin antar-PT (hari ini 200 lewat `interco_finance.view`) — temuan asal menyebutnya, unit tidak mengubahnya.

## IA-03 — Papan Meja Finance hanya butuh login

### Temuan asli
Dibaca di `cd6963a`: `backend/routers/home.py:100` (`home_finance`) hanya memanggil `_own_entity` + `current_user` — tanpa pemeriksaan izin; nominal hutang dan nama pemasok terbuka ke semua peran se-PT.

### Perbaikan yang diperiksa
SHA unit `376bd219`. Berkas dibaca: `backend/routers/home.py:100-117` (`require_any_permission` `contra_bon.view` ATAU `vendor_bill.view`), `backend/services/home_service.py:273-330` (`FINANCE_BOARD_PERMISSION`; papan disaring per izin lihat modul sumber), `backend/services/approval_backlog_service.py:468-520` (baris papan kontrabon membawa `amount` dari `totals.net_payable`), `backend/routers/contra_bons.py:34-60` (pembanding: `KOLOM_NILAI`/`_kosongkan_nilai` — nominal kontrabon hanya untuk pemegang `vendor_bill.view`, uji pelaksana U12).

### Pintu lain
```
grep -n "@router\|require_\|current_user" backend/routers/home.py
grep -rn "finance_home\|FINANCE_BOARD_KEYS\|abl.boards(" backend/services backend/routers --include=*.py
```
Kesimpulan: `/home/admin` dan `/home/manager` dijaga `manager_home.view`; `/home/sales` dan `/home/warehouse` tidak membawa papan hutang (dicek dengan akun Sopir: tanpa nominal/nama pemasok). Papan kontrabon di `/home/finance` memakai gerbang `contra_bon.view` yang sama dengan layar Kontrabon, tetapi TIDAK memakai penyaring nominal layar itu.

### Uji yang dijalankan
```
cd backend && python -m pytest tests_mem/test_PK17_nominal_berizin.py -n 0 -q -k "U01 or U02 or U03 or U12 or U18"   # pelaksana: 5 lulus
cd backend && python -m pytest tests_mem/test_bantah_PK17.py -n 0 -q -s -k IA03                                       # reviewer: 2 lulus, 1 gagal
```
Hasil: 7 lulus, 1 gagal. Yang gagal: `test_IA03_tanpa_izin_gudang_papan_finance_kontrabon_bertotal`.

### Upaya membantah
- [pt_lain] Peran ber-`vendor_bill.view` + `contra_bon.view` yang ditugaskan di `ent_kanda` meminta `/api/home/finance?entity_id=ent_ksc`. Hasil: 403 — tidak terbantah.
- [tanpa_izin] Akun Sopir membuka `/api/home/sales`, `/home/warehouse`, `/home/admin`, `/home/manager`. Hasil: 200/200/403/403, tanpa nominal hutang atau nama pemasok — tidak terbantah.
- [tanpa_izin] Akun `warehouse` (bawaan `contra_bon.view`; di layar Kontrabon `net_payable` = null, `amount_hidden: true`) membuka `/api/home/finance` saat kontrabon membawa `totals.net_payable` 10.000.000 seperti dokumen nyata. Hasil: 200, baris papan `("KSC/CB-UJI-PK17", amount 10000000.0, "Pemasok PK17")` — TERBANTAH.

### Putusan
Putusan: reopened
Alasan: gerbang login-saja sudah ditutup (`backend/routers/home.py:112`, `test_PK17_U01_sopir_papan_finance_ditolak` lulus), tetapi `test_IA03_tanpa_izin_gudang_papan_finance_kontrabon_bertotal` membuktikan papan Meja Finance masih menampilkan nominal kontrabon + nama pemasok kepada peran gudang yang di layar Kontrabon sengaja TIDAK diberi nominal (U12). Reproduksi: login `warehouse@…` → `GET /api/home/finance` → `waiting_boards[].rows[].amount` terisi. Uji pelaksana tidak menangkapnya karena fixture kontrabon tanpa `totals` (amount 0). Arah: papan kontrabon memakai penyaring nominal yang sama dengan `routers/contra_bons.py`, yaitu nominal + nama pemasok papan kontrabon hanya untuk pemegang `vendor_bill.view`.
