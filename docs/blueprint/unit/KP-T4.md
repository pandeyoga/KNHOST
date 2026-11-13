# KP-T4 — Satu tabel kebijakan persetujuan untuk semua antrean

| | |
|---|---|
| Gelombang | Jalur konfigurasi perusahaan (U) |
| Jenis | fitur |
| Risiko | tinggi (dua serah-terima) |
| Prasyarat | KF-T6, KP-T3, PR-T2 |
| Menutup temuan | KP-06, KP-07, KP-25, KP-26, PR-05 (bahan untuk PR-UX-02 dan PR-UX-24, yang layarnya ditutup PR-T6) |
| Keputusan | K-51, K-47; jawaban pemilik butir 2 dan 3 |
| Standar | §2.3, §3.1 (Z1, Z2, Z4, Z6), §3.2, §3.4 (N1), §4 (L1, L2, L5, L6), §5 (D1, D3, D8, D9), §6 |
| Lingkungan uji | B (keputusan dan izin); A (dua penyetuju bersamaan) |

## Tujuan

Satu layar menjawab "siapa menyetujui apa, mulai nominal berapa" untuk tiap PT, dan satu fungsi yang ditanya semua
pintu persetujuan. Yang boleh memutus ditentukan izin setujui + batas nominal peran yang tertulis di tabel, bukan
peringkat peran acuan dan bukan daftar peran di kode. Pada hari dipasang tidak ada keputusan yang berubah.

## Keadaan sekarang

Semua `[dibaca]` pada `3132cc4` kecuali yang ditandai. Papan antrean mendaftar 38 antrean —
`backend/services/approval_backlog_service.py:41` (`QUEUES`). Penentu penyetuju memakai tujuh mekanisme (huruf = audit):

| | Mekanisme | Jangkar |
|---|---|---|
| A | Tabel `approval_rules` → peran minimal menurut **peringkat** | `backend/services/config_service.py:315` (`evaluate_approval`); `backend/role_registry.py:365` (`role_satisfies`) |
| B | Tingkat tambahan `approval.extra_levels` (bawaan PO ≥ Rp500 jt → admin) | `backend/services/config_service.py:336` (`build_approval_chain`) |
| C | Matriks divisi ditulis mati; peran dicocokkan **nama persis**; admin selalu lolos | `backend/config_divisions.py:83` (`APPROVER_MATRIX`); `backend/services/approval_matrix_service.py:196` (`evaluate`) |
| D | Nama peran dari kunci registry per modul (sebagian peringkat, sebagian daftar) | `backend/services/contra_bon_service.py:988` (`role_rank`); `backend/services/interco_service.py:286` (`SELF_SERVE_BELOW_THRESHOLD`); `backend/services/amendment_service.py:729` (`role_in`); `backend/services/rnd_spec_service.py:343` (`allowed`); `backend/services/makloon_claim_service.py:145` (`roles`) |
| E | Entri `pending_approvals` SO dengan peran ditulis mati | `backend/routers/so_approvals.py:204` (`special_price`); `backend/routers/so_approvals.py:257` (`kredit`); `backend/routers/sales_orders.py:568` (`pembayaran_sampel`); `backend/routers/sales_orders.py:581` (`makloon`) |
| F | Rantai dan ambang di kode | `backend/services/cash_advance_service.py:34` (`APPROVAL_STAGES`); `backend/services/special_order_service.py:24` (`APPROVAL_THRESHOLD`); `backend/routers/vendor_bills.py:309` (`required_approval_role`); `backend/routers/landed_cost.py:180` (`required_approval_role`); `backend/services/marketing_cost_service.py:142` (`BILL_APPROVER_ROLES`); `backend/services/sample_sale_service.py:41` (`SAMPLE_PAYMENT_APPROVERS`); `backend/routers/crm.py:142` (`require_role`) |
| G | Izin saja | mis. `backend/routers/transfers.py:557` (`approve_transfer`) |

Cacat yang ditutup: persetujuan PO, tagihan pemasok, dan voucher biaya masuk hanya memeriksa peringkat, tanpa izin, dan
pesannya mencetak id peran — baris 2, 21, 22 di bawah (PR-05; `[dijalankan]` lewat
`docs/audit/konfigurasi-peran-2026-11-13/bukti/t10_setuju_tanpa_izin.py`: peran kustom beracuan Manajer dengan nol izin
menyetujui PO Rp250.000.000 dan tagihan pemasok Rp75.000.000, keduanya 200; skrip itu harus berubah hasilnya menjadi
403 setelah unit ini). Satu keputusan dinilai dua daftar (KP-07): PR — `backend/routers/purchase_requisitions.py:188`
(`guard`) dan layanan di baris 4; ACC desain — `backend/routers/rnd.py:291` (`guard`) dan kunci
`rnd.spec_approval_roles`. Pesanan khusus punya dua ambang, satu ditulis mati (KP-25). Dua tahap akhir uang muka hanya
untuk admin dan rantainya tidak bisa diubah (KP-26).

### Tabel lengkap: antrean → mekanisme → baris bawaan

Singkatan baris bawaan — **≥R**: semua peran (bawaan dan kustom) yang hari ini berperingkat ≥ peran R; **{…}**:
persis peran itu; **{…}+acuan**: peran itu dan peran kustom beracuan padanya; **izin**: siapa pun pemegang izinnya
(`any_holder`). Nilai ambang diambil dari nilai efektif saat migrasi (bawaan ditulis di kurung).

| # | Antrean (`doc_kind`) | Mek. | Izin yang diperiksa hari ini — pintunya | Baris bawaan (jenjang · rentang · penyetuju) |
|---|---|---|---|---|
| 1 | `sales_order` → `sales_order.nilai` · `.kredit` · `.harga_khusus` · `.bayar_sampel` · `.makloon` | A+E | `order.approve` (`.bayar_sampel` juga `sample_order.approve_payment`) — `backend/routers/so_approvals.py:293` (`role_satisfies`) | `.nilai`: salin `approval_rules` SO (benih: tanpa persetujuan); `.kredit`, `.harga_khusus`, `.makloon`: J1 · ≥ 0 · ≥manager; `.bayar_sampel`: J1 · ≥ 0 · ≥finance lewat pintu SO, {finance, sample_admin, manager, admin}+acuan lewat pintu sampel |
| 2 | `purchase_order` (+ `purchase_order.deviasi_harga`) | A+B | belum ada → `purchase_order.approve` / `.reject` — `backend/routers/purchase_orders.py:809` (`role_satisfies`) | Salin `approval_rules` PO (benih: J1 · ≥ 100 jt · ≥manager) + `approval.extra_levels` (benih: J2 "Direksi" · ≥ 500 jt · ≥admin); `.deviasi_harga`: J1 · ≥ 0 · ≥manager |
| 3 | `price` | G | `price_approval.approve` — `backend/routers/price_approvals.py:376` (`approve_price_approval`) | izin |
| 4 | `purchase_requisition` | A+C | `purchase_requisition.approve` — `backend/services/purchase_requisition_service.py:331` (`role_satisfies`) | Salin `approval_rules` PR (benih: J1 · ≥ 50 jt); penyetuju = ≥peran aturan **∩** {manager, admin} bila matriks ditegakkan untuk PT itu |
| 5 | `sales_return` | G | `sales_return.approve` — `backend/routers/sales_returns.py:350` (`approve_return`) | izin |
| 6 | `purchase_return` | G | `purchase_return.approve` — `backend/routers/purchase_returns.py:130` (`approve_purchase_return`) | izin |
| 7 | `amendment` | D | `finance_amendment.approve` (atau izin khusus di dokumen) — `backend/routers/amendments.py:172` (`decide`) | J1 · 0 – < `amendment.admin_approval_above` · {`amendment.approver_role`, admin}+acuan; di atasnya {admin}+acuan |
| 8 | `interco` | D | `interco.approve` — `backend/routers/interco.py:109` (`confirm_ict`) | J1 · 0 – < `antar_entitas.approval_threshold_rupiah` · ≥`antar_entitas.approval_role` ∪ {sales_admin}; di atasnya ≥`antar_entitas.high_value_approval_role` |
| 9 | `cycle_count` | G | `inventory.approve_count` (nilai registrasi awal: `inventory.approve_value`) — `backend/routers/cycle_count.py:294` (`approve_session`) | izin |
| 10 | `rnd_spec` | C+D | `rnd.assess` — `backend/routers/rnd.py:287` (`approve_spec`) | J1 · ≥ 0 · {manager, admin} ∩ `rnd.spec_approval_roles` |
| 11 | `rnd_sample` | C+D | `rnd.decide` — `backend/routers/rnd.py:719` (`sample_acc`) | J1 · ≥ 0 · {manager, md, admin} ∩ `rnd.sample_decision_roles` |
| 12 | `special_order` | C+F | `order.approve` — `backend/routers/special_orders.py:1050` (`po_custom`) | J1 · ≥ Rp10.000.000,01 · {manager, admin}; J2 "Direksi" · ≥ `approval.po_custom_direksi_min` (50 jt) · {admin} |
| 13 | `transfer` | G | `transfer.approve` — `backend/routers/transfers.py:557` (`approve_transfer`) | izin |
| 14 | `contra_bon_verify` | G | `contra_bon.verify` — `backend/routers/contra_bons.py:239` (`verify_contra_bon`) | izin |
| 15 | `contra_bon_approve` | D | `contra_bon.approve` — `backend/routers/contra_bons.py:251` (`approve_contra_bon`) | J1 · 0 – < `contra_bon.approval_threshold_rupiah` (50 jt) · ≥`contra_bon.approval_role`; di atasnya ≥`contra_bon.high_value_approval_role` |
| 16 | `contra_bon_dispute` | G | `contra_bon.update` — `backend/routers/contra_bons.py:214` (`decide`) | izin |
| 17 | `internal_request` | G | `internal_request.convert` / `.reject` — `backend/routers/internal_requests.py:180` (`convert`) | izin |
| 18 | `design_request` | G | `design_request.decide` — `backend/routers/design_requests.py:299` (`approve_request`) | izin |
| 19 | `inspection_hold` | G | `inspection.decide` atau `md_quality.decide` — `backend/routers/inspections.py:276` (`release-hold`) | izin |
| 20 | `interco_return` | G | `interco.approve` (wajib-terima: juga `interco.receive`) — `backend/routers/interco.py:434` (`approve_interco_return`) | izin |
| 21 | `vendor_bill` (+ `vendor_bill.kampanye`) | F | belum ada → `vendor_bill.approve` / `.reject` — `backend/routers/vendor_bills.py:455` (`role_satisfies`) | J1 · ≥ 0 · ≥manager; `.kampanye`: J1 · ≥ 0 · {finance, manager, admin} |
| 22 | `landed_cost` | F | belum ada → `landed_cost.approve` / `.reject` — `backend/routers/landed_cost.py:246` (`role_satisfies`) | J1 · ≥ 0 · ≥manager |
| 23 | `cash_advance` | F | `cash_advance.approve` — `backend/services/cash_advance_service.py:247` (`approve_cash_advance`) | J1 "Atasan Langsung" · {manager, admin}+acuan; J2 "Pimpinan" · {admin}+acuan; J3 "Bagian Keuangan" · {admin}+acuan |
| 24 | `cash_advance_settlement` | G | `cash_settlement.approve` — `backend/routers/cash_advances.py:159` (`approve_settlement`) | izin |
| 25 | `makloon_claim` | D | `makloon_order.claim_approve` — `backend/routers/makloon_orders.py:265` (`approve_claim`) | J1 · ≥ 0 · persis isi `makloon.claim_approval_roles` |
| 26 | `period_unlock` | G | `period.unlock` — `backend/routers/period_unlocks.py:86` (`approve_unlock`) | izin |
| 27 | `hr_leave` | G | `hr.manage_attendance` — `backend/routers/hr_leave.py:155` (`approve_leave_request`) | izin |
| 28 | `hr_overtime` | G | `hr.manage_attendance` — `backend/routers/hr_leave.py:254` (`approve_overtime_request`) | izin |
| 29 | `hr_payroll` | G | `hr.manage_payroll` — `backend/routers/hr_payroll.py:172` (`approve_payroll_run`) | izin |
| 30 | `design_gallery` | G | `rnd.assess` — `backend/routers/design_studio.py:118` (`_perm_assess`) | izin |
| 31 | `payment_variance` | D | `payment_variance.decide` — `backend/routers/payment_variance.py:148` (`decide`) | Hapus-sisa: J1 · ≥ 0 · {`payment.variance_writeoff_approver_role`, admin}+acuan; keputusan lain: izin |
| 32 | `so_verify` | G | `order.verify` — `backend/routers/work_desks.py:115` (`verify_order`) | izin |
| 33 | `design_claim` | G | `design_ownership.decide` — `backend/routers/design_gallery.py:204` (`design_claim_decide`) | izin |
| 34 | `credit_override` | F | izin hasil PR-T2 pada pintu itu — `backend/routers/crm.py:142` (`decide_credit_override`) | J1 · ≥ 0 · {manager, admin}+acuan |
| 35 | `od_cancel_credit_note` | G | `finance_amendment.review_credit_note` — `backend/routers/amendments.py:157` (`review_credit_note`) | izin |
| 36 | `makloon_loss` | G | `makloon_order.approve_loss` — `backend/routers/makloon_orders.py:376` (`approve_loss`) | izin |
| 37 | `po_variance` | G | `purchase_order.update` — `backend/routers/purchase_orders_extra.py:190` (`decide`) | izin |
| 38 | `sales_return_exception` | G | `sales_return.approve` — `backend/routers/sales_return_exceptions.py:51` (`decide`) | izin |

## Perubahan

### Data

Koleksi baru `approval_policies` (satu baris = satu rentang nominal pada satu jenjang):

| Field | Tipe | Wajib | Arti |
|---|---|---|---|
| `id`, `doc_kind`, `entity_id` | teks | ya | `appol_…`; kunci katalog jenis dokumen (kolom 2 tabel di atas); `"all"` (grup) atau id PT |
| `level`, `label` | bilangan ≥ 1; teks | ya / tidak | Jenjang berurutan dan namanya, mis. "Direksi" |
| `min_amount`, `max_amount` | angka ≥ 0; `max_amount` boleh kosong | ya / tidak | Berlaku bila `min_amount` ≤ nilai < `max_amount`. Jenis tanpa nominal: 0 dan kosong |
| `roles` | daftar id peran | ya | Peran yang boleh memutus pada rentang ini. Kosong = rentang ini tidak butuh persetujuan |
| `any_holder` | boolean | ya | Benar = siapa pun pemegang izinnya; `roles` diabaikan |
| `sort`, `active`, `source`, `version`, `created_*`, `updated_*`, `reason` | — | ya | `source`: `bawaan` · `migrasi` · `pengguna` |

Indeks: `(doc_kind, entity_id, level, sort)`; unik `id`. **Batas nominal sebuah peran** untuk satu jenis dokumen =
batas atas rentang tempat peran itu tercantum (K-51). Bila PT punya baris aktif untuk sebuah `doc_kind`, baris PT
menggantikan baris grup jenis itu (sama dengan `approval_pool` di KP-T3; peringatan celahnya dipakai ulang).

Katalog jenis dokumen (struktur, bukan nilai bisnis): berkas baru `backend/approval_kinds.py` — per `doc_kind`:
`label`, `group`, `queue_key`, `permissions` (izin setujui; lebih dari satu = salah satu), `amount_field` (kosong =
tanpa nominal), `level_status` (rantai berstatus seperti uang muka). INV-APPR-01 menuntut tiap kunci `QUEUES` ≥ 1 jenis.

Migrasi `scripts/migrate_kpt4_kebijakan_persetujuan.py` (hanya-lapor sebagai bawaan; data nyata: H3) memanggil
`build_default_rows(entity_id)` untuk grup dan tiap PT:

1. `approval_rules` aktif (SO, PO, PR) → satu baris per aturan, `roles` = semua peran berperingkat ≥ `required_role`.
2. `approval.extra_levels` (nilai grup dan tiap lapisan PT) → jenjang 2, 3, … Aturan mesin dipertahankan: jenjang di
   atas 1 hanya berlaku bila jenjang 1 berlaku.
3. Daftar di kode (C, E, F) dan kunci registry (D) → baris menurut tabel di atas, dengan nilai efektif tiap PT.
4. Izin (K-47): peran yang hari ini lolos peringkat untuk PO, tagihan pemasok, voucher biaya masuk tetapi belum
   memegang `purchase_order.approve|reject`, `vendor_bill.approve|reject`, `landed_cost.approve|reject` diberi izin
   itu; daftarnya ditulis di laporan.
5. Tujuh belas kunci registry yang isinya pindah ditandai "tidak dipakai — dipindah ke Aturan Persetujuan":
   `approval.` {`extra_levels`, `po_custom_direksi_min`, `matrix_enforcement`, `matrix_scope`, `matrix_effective_from`};
   `amendment.` {`approver_role`, `admin_approval_above`}; `antar_entitas.` dan `contra_bon.` masing-masing
   {`approval_role`, `high_value_approval_role`, `approval_threshold_rupiah`}; `payment.variance_writeoff_approver_role`;
   `rnd.` {`spec_approval_roles`, `sample_decision_roles`}; `makloon.claim_approval_roles`. Kunci pemicu tetap dipakai:
   `amendment.approval_threshold_*`, `payment.*_requires_approval`, `purchasing.price_deviation_approval_percent`.

Dokumen yang sedang menunggu saat pengalihan: jumlah jenjangnya tetap seperti tersimpan; siapa yang boleh memutus
dibaca dari tabel menurut jenis, PT, nilai, nomor jenjang. Dokumen baru menyimpan potret `roles` dan id baris (D3).

### Server

Berkas baru `backend/services/approval_policy_service.py`:

| Fungsi | Perilaku |
|---|---|
| `async def required_levels(doc_kind, entity_id, amount=0.0) -> list[dict]` | Jenjang yang wajib untuk nilai itu: `[{level, label, rule_id, roles, any_holder}]`; kosong = tidak butuh persetujuan |
| `async def can_decide(doc_kind, entity_id, amount, actor, level=1) -> dict` | `{allowed, code, message, who}`. Boleh bila aktor memegang salah satu `permissions` jenis itu **dan** (`any_holder` atau peran aktor ∈ `roles` baris yang memuat nilai itu). Tidak membaca peringkat maupun peran acuan. `assert_can_decide(…)` = sama, melempar 403 dengan `message` |
| `async def who_can_decide(doc_kind, entity_id, amount, level=1) -> list[str]` | Label peran yang lolos (untuk layar dan pesan) |
| `async def build_default_rows(entity_id) -> list[dict]` | Baris bawaan dari sumber lama (dipakai migrasi dan uji setara) |

Titik sambung KF-T6: fungsi di atas **tidak** memeriksa "pembuat ≠ penyetuju" maupun jumlah orang. Tiap pintu
memanggil `assert_can_decide` lalu `dual_control.tolak_bila_pelaku_sama(aksi, dokumen, aktor, entity_id)` yang
sudah dipasang KF-T6; larangan "orang yang sama di dua jenjang" pada PO tetap di tempatnya.

Endpoint (izin `settings.view` untuk baca, `settings.manage` untuk ubah; `entity_id` lewat `resolve_requested_entity`):

| Metode + path | Isi | Jawaban |
|---|---|---|
| `GET /api/approval-policies/kinds` | — | Katalog: `[{doc_kind, label, group, has_amount, permission_labels}]` |
| `GET /api/approval-policies?entity_id=&doc_kind=` | — | Per jenis: `{source, levels: [{level, label, tiers: [{id, min_amount, max_amount, roles, role_labels, any_holder}]}], unused_group_rows, warnings, version}` |
| `PUT /api/approval-policies/{doc_kind}` | `{entity_id, expected_version, reason, levels: […]}` | Mengganti seluruh baris (jenis, PT) itu sekaligus; jawaban seperti GET. `entity_id: "all"` = grup |
| `DELETE /api/approval-policies/{doc_kind}?entity_id=` | `reason` | Menghapus baris khusus PT (kembali ke grup) |
| `GET /api/approval-policies/check?doc_kind=&entity_id=&amount=` | — | `{levels: [{level, label, who: [label peran]}]}` |

Galat: 400 "Alasan perubahan wajib diisi."; 400 "Peran “{nilai}” tidak ada."; 400 "Rentang jenjang {n} tidak sah:
batas atas harus lebih besar dari batas bawah."; 409 "Aturan ini sudah diubah orang lain. Muat ulang."; 400 "Jenis
dokumen ini tidak memakai nominal." Peringatan (tidak menolak): celah, tumpang-tindih, lebih longgar dari grup,
"Tidak ada peran pada jenjang {n} yang memegang izin {nama modul}".

Pesan 403 dari `assert_can_decide` (tanpa id peran, tanpa `x.y`):

| `code` | Pesan |
|---|---|
| `izin` | "Anda belum punya akses untuk menyetujui {label jenis dokumen}. Minta Admin menambahkan akses '{nama modul}'." |
| `batas` | "{label jenis dokumen} senilai {Rp} pada jenjang {n} diputus oleh {label peran, …}. Peran Anda belum tercantum di Aturan Persetujuan." |

### Pengaturan

Tidak ada kunci baru. Tujuh belas kunci di butir migrasi 5 menjadi `not_used`; `kontrol.<aksi>.*` (KF-T6) tidak disentuh.

### Izin dan peran

Tidak ada pasangan baru. Enam pasangan yang sudah ada tetapi belum pernah diperiksa mulai ditegakkan: `approve` dan
`reject` untuk `purchase_order`, `vendor_bill`, `landed_cost` (pemegang bawaan: admin, manager; lihat butir migrasi 4).

### Layar

Tempat: Pengaturan › Persetujuan › **Aturan Persetujuan** (menggantikan isi layar KP-T3; tab "Divisi & Persetujuan
R&D" bagian matriks dan kunci persetujuan di "Persetujuan & Ambang" diarahkan ke sini).

- Pemilih **PT**; jenis dokumen berkelompok (Penjualan, Pembelian, Keuangan, Gudang, R&D, SDM). Per jenis satu kartu:
  lencana **Aturan grup** / **Aturan khusus PT ini**; tabel berkolom **Jenjang**, **Mulai dari (Rp)**, **Sampai di
  bawah (Rp)**, **Yang boleh menyetujui**, **Siapa saja yang lolos**. Kolom terakhir = label peran yang tercantum
  **dan** memegang izinnya; peran tercantum tanpa izin diberi tanda "belum punya akses {nama modul}".
- Pilihan penyetuju: semua peran dari registry (termasuk peran kustom), atau **Semua pemegang akses**.
- Tombol **Ubah** (pop-up baku; alasan wajib), **Buat aturan khusus PT ini**, **Kembali ke aturan grup**, dan
  **Coba nilai** (isian nominal → jenjang dan siapa yang lolos). Keterangan: "Jumlah orang dan boleh-tidaknya
  menyetujui dokumen sendiri diatur di Kontrol Dua Orang." (tautan).
- Layar keputusan (PO, tagihan pemasok, voucher biaya masuk, uang muka, pesanan khusus): tombol setujui/tolak mati
  dengan petunjuk dari `message` bila `can_decide` salah.

## Uji penerimaan

Persiapan bersama: seed lingkungan B; tiga peran uji baku (`02` §6); akun per peran bawaan.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | Belum ada baris | `build_default_rows("all")` | Memuat ≥ 1 baris untuk tiap kunci `QUEUES` (38 dari 38); PO: J1 ≥ 100.000.000 dan J2 ≥ 500.000.000 berlabel "Direksi" |
| U2 | B | Baris bawaan terpasang | **Setara:** untuk tiap `doc_kind` × semua peran bawaan + 3 peran uji × nilai {0; 9.999.999; 10.000.000; 10.000.000,01; 49.999.999; 50.000.000; 99.999.999; 100.000.000; 499.999.999; 500.000.000} × {`ent_ksc`, `ent_kanda`} × tiap jenjang: bandingkan penilai lama (fungsi yang dijangkar di "Keadaan sekarang") dengan `can_decide` | Sama di semua kombinasi; jumlah kombinasi dan nol selisih dicetak di laporan |
| U3 | B | seperti U2 | **Setara jenjang:** `build_approval_chain("purchase_order", x, PT)` vs `required_levels("purchase_order", PT, x)` untuk 10 nilai × 2 PT | Jumlah jenjang dan labelnya sama |
| U4 | B | Tanpa Acuan diberi `purchase_order.approve`; belum tercantum | Menyetujui PO Rp150 jt yang menunggu | 403 `batas`; pesan tidak memuat id peran maupun kata "role" |
| U5 | B | Admin `PUT …/purchase_order` menambahkan Tanpa Acuan pada J1 (`ent_ksc`) | Tanpa Acuan menyetujui PO Rp150 jt `ent_ksc`, lalu PO Rp150 jt `ent_kanda` | 200 (status `pending`); 403 (PT lain tidak berubah) |
| U6 | B | Manajer Kosong (tanpa izin apa pun) | Menyetujui PO, tagihan pemasok, voucher biaya masuk | 403 `izin` ×3 (dulu 200) |
| U7 | B | Peran kustom beracuan Manajer yang dibuat **sebelum** migrasi tanpa modul Pembelian | Jalankan migrasi; ia menyetujui PO Rp150 jt | 200; laporan migrasi menyebut peran itu diberi `purchase_order.approve` |
| U8 | B | `PUT …/cash_advance` untuk `ent_kanda`: J3 berisi {finance} | Akun finance menyetujui uang muka `ent_kanda` berstatus `pending_finance`; lalu yang milik `ent_ksc` | 200 (status `approved`); 403 |
| U9 | B | `PUT …/cash_advance` untuk `ent_kanda`: hanya J1 | Manajer menyetujui uang muka `pending_atasan` `ent_kanda` | Status langsung `approved` (jenjang tanpa baris dilewati) |
| U10 | B | Baris bawaan; lalu `PUT …/special_order` grup: J1 mulai 20.000.000 | Buat pesanan khusus Rp10.000.000 dan Rp10.000.000,01 (bawaan); lalu Rp15 jt dan Rp25 jt (sesudah PUT) | `draft`, `pending_approval` (sama dengan hari ini); lalu `draft`, `pending_approval` |
| U11 | B | `PUT` tanpa `reason`; dengan peran tak dikenal; dengan `expected_version` basi | — | 400; 400; 409 |
| U12 | B | PO dibuat sebelum pengalihan dengan rantai tersimpan [manager, admin] | Sesudah pengalihan: manajer menyetujui J1, admin J2 | Keduanya 200; PO `pending` |
| U13 | B | PR Rp60 jt; peran kustom beracuan Manajer berizin `purchase_requisition.approve` | Menyetujui sebelum dan sesudah ia ditambahkan ke baris PR | 403 (sama dengan hari ini: matriks menolak nama tak persis) → 200; hanya **satu** pesan penolakan, dari tabel |
| U14 | B | — | `GET /api/config/registry` | 17 kunci migrasi butir 5 ber-status tidak dipakai dengan alasan yang menyebut Aturan Persetujuan |
| U15 | A | PO Rp150 jt menunggu; dua manajer | Menyetujui bersamaan | Tepat satu 200, satu 409 (perilaku lama tetap) |
| U16 | layar (uji jalan) | Login admin | Buka Aturan Persetujuan, PT Kanda, kartu Uang Muka; tekan Coba nilai | Tiga jenjang dengan labelnya; "Siapa saja yang lolos" terisi label peran |

## Langkah kerja

**Serah-terima (a) — model, pembaca, uji setara; pintu lama belum disentuh.**

1. `approval_kinds.py` (38 antrean + sub-jenis); koleksi dan indeks; aturan baru INV-APPR-01.
2. `build_default_rows`; `required_levels`, `can_decide`, `who_can_decide`.
3. Uji U1–U3 (`backend/tests_mem/test_KPT4a_setara.py`); penilai lama dibungkus adaptor di berkas uji. Sebelumnya:
   telusuri tiap pintu 38 antrean untuk daftar peran yang belum ada di tabel unit ini; temuan baru → baris bawaan.
4. Endpoint baca (`kinds`, daftar, `check`) dan layar hanya-baca. Skrip migrasi mode hanya-lapor. Gate. **SHA (a).**

**Serah-terima (b) — pengalihan satu mekanisme per langkah, masing-masing hijau.**

5. Tulis baris bawaan di data acuan (skrip mode tulis) + pemberian izin butir 4.
6. PR-05: PO, tagihan pemasok (termasuk kampanye), voucher biaya masuk → `assert_can_decide` (U4–U7).
7. A+B: `evaluate_approval` dan `build_approval_chain` menjadi pembungkus `required_levels`; endpoint tulis
   `/api/approval-rules` dimatikan setelah layar pindah; SO (E) memakai sub-jenis.
8. C: PR, ACC desain, ACC sample, pesanan khusus; `APPROVER_MATRIX.levels` dan `APPROVAL_THRESHOLD` dihapus (U10, U13).
9. F: uang muka (jenjang dari tabel, status dipetakan lewat `level_status`), lewat-batas kredit, bayar sampel (U8, U9).
10. D: amandemen, antar-PT, kontrabon, selisih bayar, klaim makloon, R&D; tujuh belas kunci ditandai (U14).
11. Endpoint ubah, layar penuh, pesan; U11, U12, U15; `t10_setuju_tanpa_izin.py` menampilkan 403. Gate. **SHA (b).**

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`approval_policies`); `CODEBASE_MAP.md` (dua berkas baru); `memory/PRD.md`; glosarium ("jenjang").

## Di luar lingkup

- Jumlah orang (satu/dua), setuju-sendiri, tombol "Tim kecil" → KF-T6 (`kontrol.<aksi>.min_orang`, `dual_control`).
- Batas nominal pengurang piutang dan izin bayar terpisah → PK-38. Susunan tab hub Persetujuan → KP-T9.
- Batas persetujuan di editor peran → PR-T6. Nama aksi izin (`approve_count`, dsb.) → PR-T5. Pengingat antrean → KP-T7.

## Asumsi dan risiko

- `ASUMSI:` izin lama tiap pintu dipertahankan apa adanya sebagai "izin setujui" jenis itu, termasuk yang namanya
  bukan `approve`; hanya tiga pintu tanpa izin (PO, tagihan pemasok, voucher biaya masuk) yang mendapat pemeriksaan.
  Lewat-batas kredit dianggap sudah punya izin sendiri sesudah PR-T2; bila belum, dipakai `order.approve`.
- `ASUMSI:` admin dicantumkan di setiap baris bawaan (bukan dikecualikan di kode): tetap lolos, kini terlihat dan bisa dicabut.
- `ASUMSI:` mode matriks `off`/`warn` dan cakupan "hanya dokumen baru" tidak dipakai di data nyata; bila sebuah PT
  memakainya, baris bawaan PT itu dihitung tanpa irisan matriks dan dicatat di laporan migrasi.
- `ASUMSI:` batas atas rentang bersifat eksklusif ("di bawah"), mengikuti `approval_rules` hari ini.
- `RISIKO:` ada daftar peran ditulis mati yang luput dari tinjauan ini. Mitigasi: langkah 3 dan uji setara per pintu.
  Membatalkan satu langkah (b): kembalikan pemanggil ke penilai lama; tabel dan pembaca tidak perlu dicabut.
