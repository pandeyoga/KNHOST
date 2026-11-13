# CR-T3 — Satu mesin gerbang kredit di empat titik periksa, status "Tahan kredit", dan izin kredit yang terbatas

| | |
|---|---|
| Gelombang | Modul piutang dan kredit |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | CR-T1, CR-T2, PK-38 |
| Menutup temuan | CR-02, CR-04, CR-05 |
| Keputusan | K-14, K-27, K-28, K-29, K-31 |
| Standar | §2 (2.1–2.4), §3.1 (Z1, Z2, Z4, Z6), §3.2, §3.4 (N1, N2, N4, N5), §4 (L1, L4, L6), §5 (D3, D7, D8, D9), §6 |
| Lingkungan uji | keduanya |

Titik henti **H5**: unit dikerjakan sampai selesai dengan nilai bawaan (= perilaku hari ini). Menyalakan titik periksa
baru, tahan-kirim tunai, atau masa berlaku izin untuk PT nyata = keputusan pemilik (tulis pertanyaannya di `STATUS.md`).

## Tujuan

Kredit pelanggan diperiksa oleh satu fungsi yang sama saat pesanan dibuat, diubah, dilepas ke gudang, dan dikirim —
titik mana yang aktif diatur per PT. Pesanan yang sudah ada dan gagal diperiksa **ditahan**, bukan dibatalkan. Izin
kredit selalu bernominal, bisa bermasa berlaku, diputus menurut jenjang, dan pesanan yang ditolak meninggalkan catatan.

## Keadaan sekarang

Semua butir `[dibaca]` pada `3132cc4`.

| Fakta | Jangkar |
|---|---|
| Gerbang kredit hanya dipanggil saat pesanan dibuat dan dari pratinjau checkout | `backend/routers/sales_orders.py:363` (`evaluate_credit_gate`), `backend/routers/crm.py:176` (`evaluate_credit_gate`) |
| Pelanggan terblokir → pesanan ditolak 409 `CREDIT_BLOCKED` (keputusan pemilik 22 Okt; dipertahankan) | `backend/routers/sales_orders.py:372` (`CREDIT_BLOCKED`) |
| Alasan gerbang berupa kalimat bebas, bukan kode | `backend/services/customer_service.py:298` (`reasons`) |
| Izin kredit: yang terbaru menang; nominal 0 berarti tak terbatas; tanpa masa berlaku; sekali pakai | `backend/services/customer_service.py:523` (`credit_overrides`), `backend/routers/sales_orders.py:703` (`consumed`) |
| Mengajukan izin kredit memakai izin `order.create`; memutus memakai nama peran | `backend/routers/crm.py:93` (`request_credit_override`), `backend/routers/crm.py:142` (`decide_credit_override`) |
| Ada jalur kedua izin kredit **per pesanan** yang tidak disebut rancangan: membuat `credit_overrides` + entri persetujuan `kredit` berperan "manager" dan menyetel `credit_hold: true` | `backend/routers/so_approvals.py:231` (`request_credit_approval`), `backend/routers/so_approvals.py:262` (`credit_hold`) |
| Pesanan dengan entri persetujuan menunggu tidak bisa dilepas ke gudang; sub-status "Menunggu approval kredit" sudah ada | `backend/services/so_lifecycle_service.py:62` (`confirm_core`), `backend/services/so_status.py:48` (`menunggu_approval_kredit`) |
| Termin dari isi permintaan hanya dicek keberadaannya; tidak diadu dengan pelanggan | `backend/routers/sales_orders.py:353` (`term_code`), `backend/services/so_override_service.py:87` (`payment_term_code`) |
| Ubah jumlah, tambah baris, ganti termin lewat override tidak memeriksa kredit | `backend/services/so_override_service.py:306` (`apply`) |
| Tahan-kirim hanya untuk termin ber-`dp_percent` > 0; termin tunai (`CASH`, `dp_percent` 0) lolos | `backend/services/dispatch_payment_gate.py:66` (`applies`), `backend/services/config_service.py:150` (`CASH`) |
| Pagar kirim satu pintu untuk semua jalur kirim | `backend/services/loading_check_service.py:304` (`dispatch_guard`) |
| Pengecualian kirim memakai izin `order.release_unpaid` | `backend/routers/sales_orders_extra.py:979` (`dispatch_payment_release`), `backend/permissions_config.py:693` (`release_unpaid`) |
| Checkout mematikan tombol dari `credit.blocked`; kartu pelanggan punya pop-up "Ajukan Override Kredit" | `frontend/src/features/pos/CheckoutDrawer.jsx:189` (`creditBlocked`), `frontend/src/features/crm/Customer360Panel.jsx:322` (`OverrideModal`) |

## Perubahan

### Data

`credit_overrides` (izin kredit) — field baru:

| Field | Tipe | Arti |
|---|---|---|
| `scope` | `pesanan` · `pelanggan` | `pesanan`: hanya untuk `order_id`-nya. `pelanggan`: pesanan mana pun pelanggan itu di PT itu sampai nominal habis |
| `amount` | angka > 0 | Wajib (PK-45). Izin lama bernominal 0 yang belum dipakai dianggap kedaluwarsa; laporan memuat kueri pencarinya |
| `remaining_amount` | angka | Mulai = `amount`; dikurangi tiap pemakaian dengan pembaruan bersyarat |
| `valid_until` | ISO atau `""` | Diisi saat disetujui = waktu putus + `ar.izin_kredit_masa_berlaku_hari`; `""` = tanpa batas |
| `reason_code`, `reason_label` | string | Dari `amendment_reasons` ber-`applies_to` memuat `credit_override` |
| `used_by` | daftar `{order_id, amount, at}` | Jejak pemakaian; tampil di kartu pelanggan dan di pesanan |

Koleksi baru `credit_gate_rejections` (awalan id `cgr_`) — pesanan yang ditolak saat dibuat: `entity_id`,
`customer_id`, `customer_name`, `actor_id`, `actor_name`, `amount`, `term_code`, `reasons[]`, `exposure` (potret, D3),
`payload_snapshot` (isi permintaan pesanan), `status` (`terbuka` · `dilanjutkan` · `kedaluwarsa`), `override_id`,
`created_at`; indeks `(entity_id, status, created_at)`. `sales_orders` — field baru: `credit_hold_info`
`{since, checkpoint, reasons[]}`, `credit_hold_history[]`, `pay_before_ship` (bool), `credit_gate_at_order` (potret
hasil gerbang saat dibuat). `credit_hold` (sudah ada) menjadi penanda tunggal "Tahan kredit".

### Server

Berkas baru `backend/services/credit_gate.py`:

```python
async def evaluate(*, customer_id: str, entity_id: str, checkpoint: str, order_id: str = "",
                   order_amount: float = 0.0, term_code: str = "", actor: Optional[dict] = None) -> dict
# checkpoint: "pesanan_dibuat" | "pesanan_diubah" | "lepas_gudang" | "surat_jalan"
# → {"result": "lolos"|"peringatan"|"tahan"|"tolak", "checked": bool, "reasons": [{"code", "message", "data"}],
#    "exposure": {"ar_delivered", "open_orders", "giro_outstanding", "deposit", "this_order", "total"},
#    "limit": {"credit_limit", "limit_source", "available"}, "overdue": {"amount", "days", "block_days"},
#    "override": dict | None, "pay_before_ship": bool}
async def use_override(override_id: str, order_id: str, amount: float) -> bool   # pembaruan bersyarat sisa + masa berlaku
async def hold(order_id: str, result: dict, actor: Optional[dict]) -> dict      # credit_hold: true + info + sub-status
async def recheck_holds(customer_id: str, entity_id: str) -> list               # melepas yang kini lolos, tertua dulu
```

Urutan dan aturan `evaluate` (angka dari `customer_balance_service.get` dan `credit_profile_service.effective` untuk
PT itu saja — K-29):

1. Titik periksa mati untuk PT itu → `{"result": "lolos", "checked": false}`.
2. `eksposur` = `ar_delivered` + `open_orders` (bila `ar.eksposur_pesanan_belum_kirim`) + `giro_outstanding` (bila
   `ar.eksposur_giro_belum_cair`) − `deposit` (bila `ar.eksposur_titipan_mengurangi`) + `order_amount`.
3. Alasan dan hasil:

| Kode alasan | Syarat | Hasil | Pesan |
|---|---|---|---|
| `BLOKIR_MANUAL` | `credit_status == blokir_manual` | tahan; tidak bisa dilepas izin kredit | "Pelanggan diblokir manual: {alasan}." |
| `TERMIN_TIDAK_DIIZINKAN` | `allowed_term_codes` terisi dan termin di luar daftar | tolak | "Termin {nama} tidak diizinkan untuk pelanggan ini. Termin yang diizinkan: {daftar}." |
| `LEWAT_PLAFON` | plafon > 0 dan (eksposur > plafon atau eksposur tanpa pesanan ini ≥ plafon) | tahan | "Eksposur {Rp} melewati plafon {Rp}." |
| `TELAT` | telat terlama > hari blokir | tahan | "Ada tagihan telat {n} hari (batas {m} hari) senilai {Rp}." |
| `MENDEKATI_PLAFON` | eksposur ≥ `ar.credit_warning_pct` % × plafon | peringatan | "Eksposur sudah {p} % dari plafon." |
| `TELAT_RINGAN` | telat 1 hari sampai hari blokir | peringatan | "Ada tagihan telat {n} hari senilai {Rp}." |
| `PLAFON_KEDALUWARSA` | `limit_source == kedaluwarsa` | menambah keterangan saja | "Plafon khusus berakhir {tanggal}; dipakai plafon bawaan PT." |

4. Hasil `tahan` tanpa `BLOKIR_MANUAL` menjadi `lolos` bila ada izin kredit `approved`, belum lewat `valid_until`, dan
   (`scope: pesanan` dengan `order_id` sama, atau `scope: pelanggan` dengan `remaining_amount` ≥ nilai pesanan).
5. K-27: di titik `pesanan_dibuat`, hasil `tahan` tanpa `BLOKIR_MANUAL` untuk termin bayar-penuh-sebelum-kirim
   (`type: cash` atau `dp_percent == 100`) menjadi `lolos` dengan `pay_before_ship: true`.

Pemasangan (serah-terima b):

| Titik | Tempat | Bila `tahan` / `tolak` |
|---|---|---|
| `pesanan_dibuat` | `create_order`, menggantikan `evaluate_credit_gate` | 409 berbentuk sama dengan hari ini (`code: CREDIT_BLOCKED`, `reasons` kini berisi kode + pesan, tambah `rejection_id`); satu dokumen `credit_gate_rejections`. `tolak` → 400 `code: TERM_NOT_ALLOWED` |
| `pesanan_diubah` | `so_override_service.apply` dan penerapan amandemen, **setelah** perubahan tersimpan, hanya bila nilai pesanan naik atau `net_days` termin baru lebih besar | Perubahan tetap berlaku; `hold(...)`. `tolak` → perubahan termin ditolak dengan pesan di atas |
| `lepas_gudang` | `confirm_core`, sebelum transisi | `hold(...)` lalu 409 |
| `surat_jalan` | `dispatch_guard`, sesudah gerbang bayar | `hold(...)` lalu 409 |

Pesanan ber-`credit_hold: true` ditolak di `confirm_core` dan `dispatch_guard` walau titik periksanya mati: 409
"Pesanan {nomor} ditahan kredit — {pesan alasan pertama}. Ajukan izin kredit atau catat pembayaran dulu." Sub-status
baru `tahan_kredit` berlabel **Tahan kredit** di `so_status.SUBSTATUS_LABELS`. Pelepasan: `recheck_holds` dipanggil
`customer_balance_service.refresh` (pembayaran melepas sendiri), keputusan izin kredit, dan
`POST /api/sales-orders/{id}/credit-recheck` (izin `order.update`). Tahan-kirim tunai: `dispatch_payment_gate.evaluate`
memakai persen wajib bayar 100 bila `pay_before_ship`, atau bila termin ber-`type: cash` dan `finance.tahan_kirim_tunai`
menyala; saat kunci itu menyala, baris tagihan tunai yang terkirim lewat pengecualian `order.release_unpaid` ikut
dihitung sebagai piutang dan telat (mencabut pengecualian tunai yang ditinggalkan CR-T2).

| Endpoint | Izin | Perubahan |
|---|---|---|
| `POST /api/customers/{id}/credit-override` | `credit_override.create` (dulu `order.create`) | Isi tambah `scope`, `order_id` (wajib bila `pesanan`), `reason_code` (wajib); `amount` ≤ 0 → 400 "Nominal izin wajib lebih dari 0." (pesan PK-45) |
| `POST /api/sales-orders/{id}/request-credit-approval` | `credit_override.create` | Menjadi pembungkus: membuat izin `scope: pesanan` lewat layanan yang sama; entri persetujuan `kredit` tetap ditulis |
| `GET /api/credit-overrides`, `GET …/{id}` | `credit_override.view` | Tambah saringan `scope`, `valid`; cakupan PT dan pelanggan |
| `POST /api/credit-overrides/{id}/decision` | `credit_override.approve` + `approval_policy_service.can_decide("credit_override", entity_id, amount, actor)` (tabel kebijakan persetujuan hasil KP-T4) | `tolak_bila_pelaku_sama("izin_kredit", …)` bila `butuh_orang_kedua`; kedaluwarsa atau sudah diputus → 409 "Izin kredit ini sudah diputus atau kedaluwarsa." |
| `GET /api/customers/{id}/credit-status?amount=&term_code=&entity_id=` | tetap | Field lama dipertahankan; tambah `gate` (hasil `evaluate`) |
| `GET /api/credit-gate-rejections?status=&customer_id=`, `GET …/{id}` | `credit_override.view`; pembuatnya sendiri selalu boleh | Daftar berhalaman; rincian memuat `payload_snapshot` |

Pemberitahuan: izin diajukan → pemegang `credit_override.approve` PT itu (`create_addressed`); diputus → pengaju.
`evaluate_credit_gate` dan `check_credit_for_order` dihapus setelah tanpa pemanggil (D8).

### Pengaturan

Semua: group `uang-masuk`, scopes `("global", "entity")`, risk `high`, `requires_reason` ya, permission
`("credit_profile", "approve")`, consumers `services/credit_gate.py:evaluate` (kunci terakhir:
`services/dispatch_payment_gate.py:evaluate`).

| key | type · default | label | help → impact → example |
|---|---|---|---|
| `ar.periksa_kredit_pesanan_dibuat` | `bool` · ya | "Periksa kredit saat pesanan dibuat" | Pelanggan terblokir tidak bisa membuat pesanan tempo. → Mati = tidak ada pemeriksaan saat checkout. → "Plafon Rp 10 jt, eksposur Rp 10,5 jt → pesanan ditolak" |
| `ar.periksa_kredit_pesanan_diubah` | `bool` · tidak | "Periksa kredit saat nilai pesanan naik" | Berlaku saat jumlah ditambah atau termin dilonggarkan. → Nyala = pesanan yang melewati plafon ditahan. → "Pesanan Rp 2 jt dinaikkan ke Rp 5 jt → Tahan kredit" |
| `ar.periksa_kredit_lepas_gudang` | `bool` · tidak | "Periksa kredit saat pesanan dilepas ke gudang" | Diperiksa ulang sebelum gudang mulai menyiapkan. → Nyala = pesanan pelanggan yang kini telat tidak dilepas. → "Telat 20 hari saat dilepas → Tahan kredit" |
| `ar.periksa_kredit_surat_jalan` | `bool` · tidak | "Periksa kredit saat barang dikirim" | Diperiksa ulang sebelum surat jalan terbit. → Nyala = barang tidak keluar untuk pelanggan yang terblokir. → sama |
| `ar.eksposur_pesanan_belum_kirim` | `bool` · ya | "Hitung pesanan belum dikirim dalam eksposur" | → Mati = hanya barang terkirim yang mengurangi sisa plafon. → "Terkirim Rp 6 jt + belum kirim Rp 2 jt = Rp 8 jt" |
| `ar.eksposur_giro_belum_cair` | `bool` · ya | "Hitung giro belum cair dalam eksposur" | Baru berpengaruh setelah PM-T3. → Mati = giro dianggap lunas saat diterima. → "Giro Rp 3 jt belum cair menambah eksposur Rp 3 jt" |
| `ar.eksposur_titipan_mengurangi` | `bool` · ya | "Titipan pelanggan mengurangi eksposur" | → Mati = titipan tidak menambah sisa plafon. → "Eksposur Rp 8 jt − titipan Rp 0,5 jt = Rp 7,5 jt" |
| `ar.izin_kredit_masa_berlaku_hari` | `int` · 0 (min 0, max 90, hari) | "Izin kredit berlaku selama (hari)" | 0 = tidak kedaluwarsa. → Angka > 0 membuat izin yang tidak dipakai hangus. → "3 · disetujui Senin → hangus Kamis" |
| `finance.tahan_kirim_tunai` | `bool` · tidak | "Tahan pengiriman pesanan tunai sampai lunas" | Termin tunai diperlakukan seperti bayar-dulu 100 %. → Nyala = pesanan tunai tidak bisa dikirim sebelum dibayar, kecuali dengan pengecualian berizin. → "Tunai Rp 1 jt belum dibayar → tertahan" |

Aksi `izin_kredit` ditambahkan ke `KONTROL_AKSI` (hasil KF-T6): label "Izin kredit", kelompok C, awal "1", bernominal.

### Izin dan peran

Sumber daya `credit_override` lahir di PR-T2 dengan satu aksi `approve` (admin, manager); unit ini menambah dua aksi.
Modul aksesnya tetap seperti yang ditetapkan PR-T2; id menu `customers-crm`.

| Pasangan | Peran bawaan (setara akses hari ini) |
|---|---|
| `credit_override.view` | pemegang `customer.view` hari ini: admin, manager, sales, sales_admin, finance |
| `credit_override.create` | pemegang `order.create` hari ini: admin, manager, sales, sales_admin |
| `credit_override.approve` (sudah ada) | admin, manager — tidak diubah |

### Layar

- Checkout (`CheckoutDrawer.jsx`, juga keranjang HP): "Termin Pembayaran" hanya memuat termin yang diizinkan; kotak
  kredit menampilkan empat baris eksposur, "Plafon", "Sisa plafon", dan pesan alasan. Saat ditolak: tombol **Ajukan
  izin kredit** (pop-up: "Lingkup" [Pesanan ini · Pelanggan ini], "Nominal", "Alasan" [pilihan], "Catatan") dan
  keterangan "Keranjang disimpan. Setelah izin disetujui, buka lagi dari Pesanan tertunda."
- Detail pesanan: lencana **Tahan kredit** + alasan + tombol **Periksa ulang kredit**; "Izin kredit dipakai: {nomor} ·
  {Rp}"; untuk `pay_before_ship`: "Bayar penuh sebelum kirim (pelanggan sedang ditahan)". `CreditOverridesPanel.jsx`:
  kolom "Lingkup", "Sisa", "Berlaku sampai", "Alasan"; konfirmasi menyebut pelanggan, PT, dan nominal (N5).

## Uji penerimaan

Fixture **G1** di `ent_kanda`: pelanggan P, plafon khusus Rp 10.000.000; saldo tersimpan `ar_delivered` 6.000.000,
`open_orders_amount` 2.000.000, `deposit_balance` 500.000 → eksposur = 6.000.000 + 2.000.000 − 500.000 = 7.500.000.
Pelanggan Q di `ent_ksc` berangka sama. Semua kunci bawaan kecuali disebut.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | G1 | `sls`: pesanan baru Rp 2.000.000 termin NET30 | 200; `gate.result == "peringatan"`, kode `MENDEKATI_PLAFON` (9.500.000 ≥ 0,8 × 10.000.000) |
| U2 | B | G1 | Pesanan baru Rp 3.000.000 | 409 `CREDIT_BLOCKED`, alasan `LEWAT_PLAFON` (10.500.000 > 10.000.000); tidak ada pesanan; satu `credit_gate_rejections` beramount 3.000.000 |
| U3 | B | G1; `ar.eksposur_titipan_mengurangi` = tidak pada `ent_kanda` | P: pesanan Rp 2.500.000; Q (`ent_ksc`): pesanan Rp 2.500.000 | P 409 (8.000.000 + 2.500.000 = 10.500.000); Q 200 (7.500.000 + 2.500.000 = 10.000.000, tidak melewati) — PT lain tidak berubah |
| U4 | B | G1; `ar.izin_kredit_masa_berlaku_hari` = 3 | `sls` mengajukan izin `pelanggan` Rp 3.000.000; `mgr` menyetujui; `sls` membuat pesanan Rp 3.000.000 | Izin ber-`valid_until` = waktu putus + 3 hari; pesanan 200; `remaining_amount` 0; `used_by` 1 baris; pesanan menyimpan `credit_override_id` |
| U5 | B | U4 tanpa pesanan; `valid_until` digeser ke kemarin | Pesanan Rp 3.000.000 | 409 `CREDIT_BLOCKED` |
| U6 | B | G1 | Pengajuan izin `amount: 0`; lalu `kontrol.izin_kredit.min_orang` = 2 dan `mgr` mengajukan + memutus sendiri | 400; 403 |
| U7 | B | G1 dengan pesanan S Rp 2.000.000 (bagian dari `open_orders_amount`); `ar.periksa_kredit_pesanan_diubah` = ya | Override S menjadi Rp 5.000.000 | 200; nilai tersimpan; `credit_hold: true`, alasan `LEWAT_PLAFON` (6.000.000 + 5.000.000 − 500.000 = 10.500.000); sub-status "Tahan kredit" |
| U8 | B | G1 seperti U7 tetapi kunci bawaan (tidak) | Override yang sama | 200; `credit_hold: false` |
| U9 | B | U7 | Lepas pesanan S ke gudang | 409 "Pesanan … ditahan kredit — …"; status pesanan tidak berubah |
| U10 | B | U7 | Kwitansi Rp 1.000.000 untuk tagihan terkirim | Eksposur 9.500.000 ≤ plafon → `credit_hold: false` otomatis; `credit_hold_history` 1 baris |
| U11 | B | G1; profil `blokir_manual`; izin kredit `approved` Rp 5.000.000 | Pesanan Rp 1.000.000 | 409, alasan `BLOKIR_MANUAL`; izin tidak terpakai |
| U12 | B | G1; profil `allowed_term_codes: ["CASH", "NET14"]` | Pesanan termin NET30; lalu NET14 | 400 `TERM_NOT_ALLOWED`; 200 |
| U13 | B | G1 + tagihan telat 20 hari (> 14) | Pesanan termin CBD; kirim sebelum bayar; pesanan termin NET30 | 200 dengan `pay_before_ship: true`; kirim 409 dari gerbang bayar; NET30 409 alasan `TELAT` |
| U14 | B | Pesanan termin CASH Rp 1.000.000 belum dibayar di `ent_kanda` dan di `ent_ksc`; `finance.tahan_kirim_tunai` = ya pada `ent_kanda` | `dispatch_guard` untuk keduanya | `ent_kanda` 409 "…kurang Rp 1.000.000…"; `ent_ksc` lolos |
| U15 | B | peran uji baku; izin kredit `pending` | **Tanpa Acuan** + `credit_override.approve`: putus; **Manajer Kosong**; **Sopir** | 200; 403; 403 |
| U16 | B | — | Putaran `t1_config.py` untuk sembilan kunci | Lulus |
| U17 | A | Izin `pelanggan` Rp 3.000.000 | Dua pesanan Rp 3.000.000 bersamaan | Satu 200, satu 409; `remaining_amount` 0, tidak negatif |
| U18 | layar (uji jalan) | U2 | `sls` di checkout lalu `mgr` di panel izin kredit | Empat baris eksposur dan pesan alasan tampil; pengajuan muncul dengan lingkup, sisa, masa berlaku |

## Langkah kerja

**Serah-terima (a) — mesin baru di samping jalur lama.**

1. `backend/tests_mem/test_CRT3_gerbang.py`: U1–U3, U11–U13 terhadap `credit_gate.evaluate` langsung; merah.
2. `credit_gate.evaluate` + sembilan kunci. Tes pembanding: untuk 20 kombinasi fixture, hasil `evaluate` di titik
   `pesanan_dibuat` dengan kunci bawaan sama dengan `evaluate_credit_gate` lama (blok/peringatan/lolos), kecuali
   selisih yang didaftar di bagian risiko.
3. Field izin kredit, `use_override`, izin baru di empat tempat, jenjang dan kontrol dua orang. U4–U6, U15 hijau.

**Serah-terima (b) — alihkan pemanggil, matikan jalur lama.**

4. Pasang empat titik; `credit_gate_rejections`; `hold`, `recheck_holds`; tahan-kirim tunai. U7–U10, U14 hijau.
5. Alihkan pratinjau dan `request-credit-approval`; hapus dua fungsi lama dan cadangan `data_lama` dari CR-T1.
6. Layar; U17 di lingkungan A; U18; gate penuh; laporan + pertanyaan H5 di `STATUS.md`.

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`credit_overrides`, `credit_gate_rejections`, field pesanan), `CODEBASE_MAP.md`, `memory/PRD.md`,
`docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("Tahan kredit", "izin kredit", "eksposur").

## Di luar lingkup

- Izin setara pelepasan untuk ganti termin yang lebih longgar (FX-16) → PK-38. Termin bawaan PT dibaca per PT (KP-11)
  → KF-T3. Antrean "Ditahan" dan "Menunggu keputusan" → CR-T5. Kelompok kredit lintas PT → belum ada unitnya.

## Asumsi dan risiko

- `ASUMSI:` rancangan mengusulkan keempat titik "Periksa" dan masa berlaku izin 3 hari. Menurut `00` §4.1 nilai awal =
  perilaku hari ini: hanya `pesanan_dibuat`, izin tanpa kedaluwarsa. Pemilik menyalakan sisanya (H5).
- `ASUMSI:` K-27 tidak berlaku untuk blokir manual (rancangan: "tidak bisa dilepas otomatis").
- `ASUMSI:` benih kode alasan izin kredit: `cr_riwayat_baik` "Riwayat bayar baik", `cr_jaminan` "Ada jaminan atau giro
  mundur", `cr_lain` "Lainnya (jelaskan di catatan)". Admin bisa mengubahnya di master alasan.
- `ASUMSI:` KP-T4 bukan prasyarat di indeks. Bila `approval_policy_service` belum ada, keputusan izin kredit hanya
  memakai izin `credit_override.approve` tanpa batas nominal peran; laporan mencatatnya sebagai sisa pekerjaan.
- `RISIKO:` hasil gerbang berubah untuk pelanggan yang bertransaksi di lebih dari satu PT (dulu piutang dijumlah lintas
  PT, kini per PT — K-29) dan karena titipan kini mengurangi eksposur (K-31). Laporan memuat daftar pelanggan yang
  hasilnya berbeda pada data acuan. Membatalkan (b): kembalikan `create_order` ke fungsi lama; field baru tidak dibaca.
