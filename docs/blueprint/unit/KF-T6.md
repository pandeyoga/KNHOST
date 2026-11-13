# KF-T6 — Kontrol "harus dua orang" yang bisa diatur per PT

| | |
|---|---|
| Gelombang | Jalur pengaturan (sejajar gelombang 3–7) |
| Jenis | fitur + perbaikan |
| Risiko | tinggi — dua serah-terima (`00` §8) |
| Prasyarat | KF-T1 |
| Menutup temuan | KP-05, GL-06 |
| Keputusan | Jawaban pemilik butir 2; K-04, K-11, K-17, K-25, K-28, K-41, K-44 (nama kunci) |
| Standar | §2.1, §2.3, §2.4, §3.1 (Z6), §4 (L1, L3), §6 |
| Lingkungan uji | B; U12–U14 diulang di A |

## Tujuan

Setiap aturan "pengaju tidak boleh memutuskan sendiri" berasal dari satu tempat dan bisa diatur pemilik per PT lewat satu
tabel. Saat dipasang tidak ada kontrol yang melonggar diam-diam: yang hari ini melarang tetap melarang, kecuali buka
periode yang oleh pemilik diminta berbawaan satu orang. Tim kecil bisa menjadikan semuanya satu orang dengan satu tombol.

## Keadaan sekarang

Semua `[dibaca]` dan dicek ulang pada `3132cc4`. Tiga keadaan hidup bersamaan:

- **Sakelar**: `approval.matrix_sod` (`backend/config_catalog_approval_matrix.py:63`, `approval.matrix_sod`), dibaca
  `backend/services/approval_matrix_service.py:196` (`sod_blocked`) dan `:256` (`is_requester`); dan
  `amendment.dual_control` (`backend/config_catalog_finance.py:55`, `amendment.dual_control`).
- **Larangan ditulis mati** di 12 titik (tabel B).
- **Tanpa pemeriksaan** di 15 pintu (tabel C) — setuju-sendiri sudah boleh.
- Admin lolos lewat `backend/services/approval_matrix_service.py:181` (`admin_override`) di 13 titik, dan tidak
  lolos di 4 titik (ditandai †).
- GL-06: buka kembali tutup buku cukup satu Admin (`backend/routers/closing.py:105`, `reopen_period`); jurnal manual
  langsung berstatus `posted` (`backend/services/gl_service.py:706`, `create_manual_entry`).
- Tidak cocok dengan Lampiran C.1 audit: klaim makloon **tidak** melewati `guard`; ia masuk tabel C.

Kolom "Awal" = nilai bawaan `kontrol.<aksi>.min_orang`; "Rp" = aksi punya `batas_nominal`.

**A. Hari ini diatur sakelar (bawaan melarang)** — nilai awal mengikuti sakelar yang berlaku (lihat Migrasi):

| Aksi | Label di layar | Titik yang diganti | Pengaju | Awal | Rp |
|---|---|---|---|---|---|
| `acc_desain` | ACC desain | `backend/routers/rnd.py:291` (`design_acc`), `backend/routers/rnd.py:316` (`design_acc`) | pembuat dokumen | 2 | — |
| `acc_sample` | Keputusan sample | `backend/routers/rnd.py:719` (`sample_acc`) | pembuat dokumen | 2 | — |
| `po_custom` | Pesanan khusus (PO custom) | `backend/routers/special_orders.py:1050` (`po_custom`), `backend/routers/special_orders.py:1139` (`po_custom`) | pembuat dokumen | 2 | ya |
| `permintaan_pembelian` | Permintaan pembelian (PR) | `backend/routers/purchase_requisitions.py:188` (`purchase_request`), `backend/services/purchase_requisition_service.py:336` (`sod_blocked`) | pembuat dokumen | 2 | ya |
| `harga_khusus` | Harga khusus | `backend/routers/price_approvals.py:382` (`sod_blocked`), `backend/routers/price_approvals.py:475` (`sod_blocked`), `backend/routers/so_approvals.py:302` (`sod_blocked`) | `requested_by_id` | 2 | — |
| `amandemen` | Koreksi / amandemen dokumen | `backend/services/amendment_service.py:733` (`dual_control`) | `proposed_by_id` | 2 | ya |

**B. Hari ini melarang, ditulis mati:**

| Aksi | Label di layar | Titik yang diganti | Pengaju | Awal | Rp |
|---|---|---|---|---|---|
| `setujui_po` | Persetujuan PO | `backend/routers/purchase_orders.py:818` (`admin_override`) | `created_by_id` | 2 | ya |
| `po_tingkat_berikut` | PO berjenjang: tingkat berikutnya | `backend/routers/purchase_orders.py:840` (`approved_by_id`) | penyetuju tingkat sebelumnya | 2 | — |
| `tagihan_pemasok` | Tagihan pemasok | `backend/routers/vendor_bills.py:459` (`admin_override`) | `created_by_id` | 2 | ya |
| `biaya_masuk` | Voucher biaya masuk | `backend/routers/landed_cost.py:250` (`admin_override`) | `created_by_id` | 2 | ya |
| `kontrabon` | Kontrabon | `backend/services/contra_bon_service.py:995` (`created_by_id`) | `created_by_id` | 2 | ya |
| `tagihan_kampanye` | Tagihan kampanye | `backend/services/marketing_cost_service.py:224` (`admin_override`) | `created_by_id` | 2 | ya |
| `retur_antar_pt` | Retur antar-PT | `backend/services/interco_return_service.py:434` (`creator`) | `created_by` (nama) | 2 | ya |
| `buka_periode` | Buka periode buku | `backend/services/period_unlock_service.py:197` (`requested_by_id`) | `requested_by_id` | **1** (keputusan pemilik) | — |
| `susut_makloon` † | Susut bahan di mitra makloon | `backend/services/makloon_loss_service.py:242` (`recorded_by_id`) | `recorded_by_id` | 2 | ya |
| `pengecualian_retur` † | Pengecualian retur | `backend/services/return_exception_service.py:47` (`requested_by_id`) | `requested_by_id` | 2 | — |
| `klaim_desain` † | Klaim kepemilikan desain | `backend/services/design_ownership_service.py:224` (`by_id`) | `by_id` | 2 | — |
| `registrasi_stok_awal` † | Stok awal: penyetuju nilai ≠ penyetuju hitungan | `backend/services/initial_registration_service.py:210` (`count_approval`) | `count_approval.by_id` | 2 | — |

**C. Hari ini tanpa pemeriksaan (pemeriksaan baru dipasang, bawaan satu orang):**

| Aksi | Label di layar | Titik pasang | Pengaju | Awal | Rp |
|---|---|---|---|---|---|
| `transfer_gudang` | Transfer gudang / antar-PT | `backend/routers/transfers.py:550` (`approve_transfer`) | `requested_by` | 1 | — |
| `stok_opname` | Stok opname | `backend/routers/cycle_count.py:293` (`approve_session`) | `submitted_by` | 1 | — |
| `retur_penjualan` | Retur penjualan | `backend/services/return_service.py:773` (`approve_return`) | `created_by` | 1 | ya |
| `retur_pembelian` | Retur pembelian | `backend/services/purchase_return_service.py:276` (`approve_and_adjust_stock`) | `created_by` | 1 | ya |
| `cuti` | Cuti | `backend/services/hr_leave_service.py:250` (`approve_leave`) | akun yang tertaut ke `employee_id` | 1 | — |
| `lembur` | Lembur | `backend/services/hr_leave_service.py:363` (`approve_overtime`) | akun yang tertaut ke `employee_id` | 1 | — |
| `proses_gaji` | Pengesahan gaji | `backend/services/hr_payroll_service.py:475` (`approve_run`) | pengaju proses (`submit_run`) | 1 | ya |
| `uang_muka` | Uang muka / kasbon | `backend/services/cash_advance_service.py:241` (`approve_cash_advance`) | pemohon | 1 | ya |
| `lpj_uang_muka` | Pertanggungjawaban uang muka | `backend/services/cash_advance_service.py:484` (`approve_settlement`) | pemohon | 1 | ya |
| `pengurang_piutang` | Bebas denda dan hapus selisih bayar | `backend/services/penalty_service.py:400` (`waive`), `backend/services/payment_variance_service.py:678` (`decide_receipt`), `backend/services/payment_variance_service.py:1016` (`decide_bill`) | pengaju keputusan | 1 | ya |
| `lewat_batas_kredit` | Izin lewat batas kredit | `backend/routers/crm.py:141` (`decide_credit_override`) | `requested_by_id` | 1 | ya |
| `klaim_makloon` | Klaim selisih makloon | `backend/routers/makloon_orders.py:263` (`approve_claim`) | pengusul klaim | 1 | ya |
| `permintaan_internal` | Permintaan internal antar-PT | `backend/services/internal_request_service.py:392` (`convert`) | pembuat | 1 | — |
| `permintaan_desain` | Permintaan desain | `backend/services/design_request_service.py:421` (`approve`) | pembuat | 1 | — |
| `nilai_pesanan` | Persetujuan nilai pesanan | `backend/routers/sales_orders_extra.py:447` (`approve_order`) | `created_by` | 1 | ya |
| `buka_kembali_tutup_buku` | Buka kembali tutup buku | `backend/routers/closing.py:105` (`reopen_period`) | pengaju buka kembali | 1 | — |
| `jurnal_manual` | Jurnal manual | `backend/services/gl_service.py:655` (`create_manual_entry`) | pembuat jurnal | 1 | ya |

Bila dokumen sebuah aksi hanya menyimpan nama pengaju, pembanding nama dipakai (cara `is_requester`,
`backend/services/approval_matrix_service.py:132`), dan titik pengajuannya mulai menyimpan id (`…_by_id`).

## Perubahan

### Data

| Koleksi · field | Tipe | Arti |
|---|---|---|
| `period_closings.reopen_request` | objek `{by_id, by, at}` atau tidak ada | Pengajuan buka kembali yang menunggu orang kedua; dihapus saat dijalankan |
| `journal_proposals` (baru) | `id` (`jprop_…`), `entity_id`, `payload` (isi `JournalEntryCreate`), `total_debit`, `status` (`pending` · `posted` · `rejected`), `proposed_by_id`, `proposed_by`, `proposed_at`, `decided_by_id`, `decided_by`, `decided_at`, `reject_reason`, `journal_id` | Jurnal manual yang menunggu orang kedua. Indeks: `id` unik; `(entity_id, status, proposed_at)` |

Migrasi sekali jalan di proses awal, penanda `system_settings{scope: "__migrations__"}.kft6_kontrol`:

1. Untuk lapisan grup dan tiap PT: bila `approval.matrix_sod` efektif **tidak** atau `approval.matrix_enforcement` efektif
   `off`, tulis `kontrol.<aksi>.min_orang = "1"` pada lapisan itu untuk lima aksi sakelar di tabel A (lewat
   `config_resolver.set_value`, alasan "Pindahan dari sakelar pemisahan tugas"). Selain itu tidak menulis (bawaan "2").
2. Sama untuk `amendment.dual_control` tidak → `kontrol.amandemen.min_orang = "1"`.
3. `approval.matrix_sod` dan `amendment.dual_control` menjadi `not_used` dengan alasan "Dipindahkan ke Pengaturan ›
   Persetujuan › Kontrol dua orang." Sebagai alias: `approval_matrix_service.settings()["sod"]` dan
   `amendment_service.policy_snapshot()["dual_control"]` kini dihitung dari `butuh_orang_kedua`.

### Server

Berkas baru `backend/services/dual_control.py`:

| Fungsi | Perilaku |
|---|---|
| `async def butuh_orang_kedua(aksi: str, entity_id: str, nominal: float = 0.0) -> bool` | `True` bila `kontrol.<aksi>.min_orang` untuk PT itu = "2", atau `batas_nominal` > 0 dan `nominal` > `batas_nominal`. Aksi tak dikenal → `KeyError` |
| `def pelaku_sama(dokumen: dict, aktor: dict, pengaju: Optional[Iterable[str]] = None) -> bool` | Dengan `pengaju` (id, nama, atau email): cocokkan dengan id/nama/email aktor. Tanpa itu: `approval_matrix_service.is_requester` |
| `async def tolak_bila_pelaku_sama(aksi, dokumen, aktor, entity_id="", *, nominal=0.0, pengaju=None) -> dict` | (1) tidak butuh orang kedua, atau pelaku berbeda → lolos. (2) pelaku sama dan aktor Admin dan `kontrol.admin_boleh_sendiri` ya dan `aksi` tidak ada di `kontrol.admin_tetap_dua_orang` → lolos, dicatat lewat `approval_matrix_service.record(..., outcome="diputuskan sendiri oleh admin")`. (3) selain itu `HTTPException(403)`. Jawaban: `{"dua_orang": bool, "sendiri": bool, "admin_sendiri": bool}` |

Pesan 403: "{Label aksi} harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang berwenang. Admin dapat
mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang." Semua titik memakai kode 403 (sebelumnya sebagian
400 lewat `ValueError`).

Pemasangan: di tiap jangkar tabel A dan B, pembanding lama beserta `admin_override`/`sod_blocked` diganti satu panggilan
`tolak_bila_pelaku_sama("<aksi>", dok, aktor, dok["entity_id"], nominal=<nilai dokumen>, pengaju=<kolom Pengaju>)`; di tiap
jangkar tabel C panggilan yang sama ditambahkan sesudah pemeriksaan izin dan status. `approval_matrix_service.evaluate`
tidak lagi menilai pemisahan tugas; `guard` memanggil pembantu dengan aksi tahapnya (`design_acc` → `acc_desain`,
`sample_acc` → `acc_sample`, `po_custom` → `po_custom`, `purchase_request` → `permintaan_pembelian`).

| Endpoint | Izin | Perilaku |
|---|---|---|
| `GET /api/kontrol/aturan?entity_id=` (router baru `routers/kontrol.py`) | `settings.view` | `{"rows": [{"aksi", "label", "kelompok" (A·B·C), "punya_nominal", "min_orang", "batas_nominal", "sumber" ("entity" · "global" · "default")}], "admin_boleh_sendiri", "admin_tetap_dua_orang", "can_edit"}` |
| Simpan | — | Lewat `PUT /api/config/values` (banyak butir, satu alasan); tidak ada endpoint tulis baru |
| `POST /api/finance/closing/{id}/reopen` | tetap | Bila `butuh_orang_kedua("buka_kembali_tutup_buku", PT)`: panggilan pertama menyimpan `reopen_request` dan menjawab 202 `{"status": "menunggu_orang_kedua", "requested_by": nama}`; panggilan pengaju yang sama → 403; panggilan orang lain yang berwenang → dijalankan seperti sekarang |
| Buat jurnal manual (`backend/routers/gl.py:148`, `create_journal`) | tetap | Bila `butuh_orang_kedua("jurnal_manual", PT, total_debit)`: validasi dan `preflight_posting` tetap dijalankan, lalu simpan ke `journal_proposals` dan jawab 202 `{"status": "menunggu_orang_kedua", "proposal_id"}`; tidak ada baris `journal_entries`. Selain itu seperti sekarang |
| `GET /api/gl/journal-proposals?status=` | `accounting.view` | Daftar berhalaman per PT aktif |
| `POST /api/gl/journal-proposals/{id}/approve` | `accounting.create` | `tolak_bila_pelaku_sama("jurnal_manual", …, pengaju=[proposed_by_id])`; periksa periode ulang; `create_manual_entry` dengan `created_by` = pengusul dan `approved_by` = penyetuju; usulan → `posted` + `journal_id`. Usulan bukan `pending` → 409 "Usulan jurnal ini sudah diputuskan." |
| `POST /api/gl/journal-proposals/{id}/reject` | `accounting.create` | Isi `{"reason"}` wajib (400 "Alasan penolakan wajib diisi."); usulan → `rejected` |

### Pengaturan

Katalog baru `backend/config_catalog_kontrol.py` memuat `KONTROL_AKSI` (35 aksi di tabel A–C: `aksi`, `label`,
`kelompok`, `awal`, `punya_nominal`) dan mendaftarkan lewat satu putaran:

| key | group | type | default | min · max · unit | scopes | label | help | risk | permission | consumers |
|---|---|---|---|---|---|---|---|---|---|---|
| `kontrol.<aksi>.min_orang` (35) | `persetujuan` | `enum`: "1" Cukup satu orang · "2" Harus dua orang | kolom "Awal" (teks) | — | global, entity | "{Label}: jumlah orang" | "1 = orang yang mengajukan boleh memutuskan sendiri. 2 = harus diputuskan orang lain." | high, wajib alasan | `("settings", "manage")` | titik pasang aksi itu (`berkas.py:fungsi`) + `services/dual_control.py:butuh_orang_kedua` |
| `kontrol.<aksi>.batas_nominal` (18, kolom "Rp" = ya) | `persetujuan` | `money` | 0 | 0 · 1000000000000 · Rp | global, entity | "{Label}: dua orang di atas (Rp)" | "Di atas nilai ini selalu dua orang walau jumlah orang = 1. 0 = tidak dipakai." | high, wajib alasan | sama | sama |
| `kontrol.admin_boleh_sendiri` | `persetujuan` | `bool` | True | — | global, entity | "Admin boleh memutuskan dokumennya sendiri" | "Bila ya, Admin tidak terkena aturan dua orang; tiap kejadian dicatat di jejak persetujuan." | high | sama | `services/dual_control.py:tolak_bila_pelaku_sama` |
| `kontrol.admin_tetap_dua_orang` | `persetujuan` | `list` (nama aksi) | `["susut_makloon", "pengecualian_retur", "klaim_desain", "registrasi_stok_awal"]` | — | global, entity | "Aksi yang tetap dua orang walau Admin" | "Admin pun tidak boleh memutuskan sendiri untuk aksi di daftar ini." | high | sama | sama |

`impact` dan `example` per `02` §2.1 (contoh: "Rina membuat PO lalu menyetujuinya sendiri → ditolak bila 2"). Unit lain
menambah aksinya ke `KONTROL_AKSI` (`bayar_hutang`, `cairkan_uang_muka`, `lembar_insentif`, `ubah_profil_kredit`,
`asisten_uang_keluar`). `config_health` mengenali keluarga `kontrol.*` dari literal nama aksi di titik pasangnya.

### Izin dan peran

Tidak ada pasangan baru. Id menu `settings-dual-control` masuk `nav` modul `admin` dan
`VIEW_RESOURCE_OVERRIDES["settings-dual-control"] = ["settings"]`.

### Layar

Pengaturan › Persetujuan › tab baru **Kontrol dua orang** (tab ke-4 hub `settings-approval`; view
`settings-dual-control`; komponen `frontend/src/features/settings/kontrol/DualControlView.jsx`):

- Pemilih **Berlaku untuk**: "Semua PT" atau satu PT (aturan lapisan sama dengan Pusat Pengaturan).
- Tabel, dikelompokkan "Pembelian & hutang", "Penjualan & piutang", "Gudang & produksi", "SDM", "Buku besar", kolom:
  **Aksi** · **Jumlah orang** (pilihan "Cukup satu orang" / "Harus dua orang") · **Dua orang di atas (Rp)** (isian;
  "—" bila aksi tidak bernominal) · **Sumber** ("Aturan PT ini" / "Mengikuti semua PT" / "Bawaan").
- Di bawah tabel: sakelar **Admin boleh memutuskan dokumennya sendiri** dan daftar centang **Tetap dua orang walau Admin**.
- Tombol **Tim kecil — semua cukup satu orang**: konfirmasi "Semua aksi untuk {Semua PT | nama PT} akan cukup diputuskan
  satu orang. Batas nominal tidak diubah. Lanjutkan?" + isian alasan wajib; menyimpan "1" ke semua `min_orang` pada
  lapisan terpilih.
- Tombol **Simpan perubahan** (mati sampai ada perubahan; alasan wajib). Berhasil: "Aturan kontrol dua orang tersimpan."
- Memuat / galat (`ErrorNotice` + coba lagi) / hanya-baca bila `can_edit` salah.

Kunci `kontrol.*` disembunyikan dari daftar kartu umum (`excludeKeys: ["kontrol."]`, pola kunci komisi) dengan tautan ke
tab ini. Buku Besar › Jurnal: pita "{n} jurnal manual menunggu orang kedua" + saringan **Menunggu persetujuan** dengan
tombol **Setujui** dan **Tolak** (alasan). Tutup Buku: periode ber-`reopen_request` menampilkan "Menunggu orang kedua —
diajukan {nama}".

## Uji penerimaan

Fixture: `mgr`, `mgr2` (dua akun manager), `adm`; dokumen disisipkan dalam status menunggu persetujuan dengan pengaju `mgr`.

| ID | Lapis | Persiapan | Langkah | Hasil yang diharapkan |
|---|---|---|---|---|
| U1 | B | bawaan | `butuh_orang_kedua` untuk `setujui_po`, `transfer_gudang`, `buka_periode` di `ent_ksc` | `True`, `False`, `False` |
| U2 | B | PO buatan `mgr` di `ent_ksc` dan di `ent_kanda` | `mgr` menyetujui PO `ent_ksc`; Admin menyimpan `kontrol.setujui_po.min_orang="1"` lapisan PT `ent_ksc`; `mgr` mengulang di kedua PT | 403 pesan dua orang; lalu `ent_ksc` 200 dan `ent_kanda` tetap 403 |
| U3 | B | Dua uang muka milik `mgr`: 4.000.000 dan 6.000.000; `kontrol.uang_muka.batas_nominal=5000000` | `mgr` menyetujui keduanya | 200 (4 jt ≤ batas, satu orang cukup); 403 (6 jt > batas) |
| U4 | B | PO buatan `adm` | `adm` menyetujui; set `kontrol.admin_boleh_sendiri=false`; PO kedua buatan `adm`, `adm` menyetujui | 200 + satu baris `approval_matrix_log` ber-`outcome` "diputuskan sendiri oleh admin"; lalu 403 |
| U5 | B | Pengecualian retur diajukan `adm` | `adm` memutuskan; kosongkan `kontrol.admin_tetap_dua_orang`; ulangi pada pengecualian baru | 403; 200 |
| U6 | B | Usul buka periode oleh `mgr` | `mgr` menyetujui; set `kontrol.buka_periode.min_orang="2"`; usul baru, `mgr` menyetujui, lalu `mgr2` | 200 (bawaan satu orang); 403; 200 |
| U7 | B | Proses gaji diajukan `mgr` di `ent_ksc` | `mgr` mengesahkan; set `kontrol.proses_gaji.min_orang="2"` lapisan PT `ent_ksc`; proses baru: `mgr`, lalu `mgr2` | 200; 403; 200 |
| U8 | B | Cuti milik karyawan yang akunnya `mgr`; `kontrol.cuti.min_orang="2"` | `mgr` menyetujui; `mgr2` menyetujui | 403; 200 |
| U9 | B | Sebelum migrasi: `approval.matrix_sod=false` lapisan PT `ent_kanda` | Jalankan migrasi dua kali | `kontrol.permintaan_pembelian.min_orang`: `ent_kanda` "1", `ent_ksc` "2"; kedua sakelar lama `not_used`; jalan kedua tanpa baris baru |
| U10 | B | Sebelum migrasi: `amendment.dual_control=false` lapisan grup | Jalankan migrasi | `kontrol.amandemen.min_orang` grup = "1"; `policy_snapshot("ent_ksc")["dual_control"] is False` |
| U11 | B | — | Admin `PUT /api/config/values` berisi "1" untuk 35 kunci `min_orang` lapisan PT `ent_ksc`, satu alasan | 200; `butuh_orang_kedua(a, "ent_ksc")` salah untuk semua aksi; untuk `ent_kanda` `setujui_po` tetap benar |
| U12 | B, A | `kontrol.buka_kembali_tutup_buku.min_orang="2"`; satu periode tertutup | `adm` buka kembali; `adm` lagi; admin kedua | 202 dan periode tetap `closed`; 403; 200 dan periode `reopened`, `reopen_request` hilang |
| U13 | B, A | `kontrol.jurnal_manual.min_orang="2"` | `mgr` membuat jurnal 1.000.000 (D kas / K modal); `mgr` menyetujui usulannya; `mgr2` menyetujui | 202, jumlah `journal_entries` tetap, saldo akun tidak berubah; 403; 200, satu jurnal `posted` ber-`created_by` `mgr` dan `approved_by` `mgr2`, saldo kedua akun berubah 1.000.000 |
| U14 | B, A | `min_orang="1"`, `kontrol.jurnal_manual.batas_nominal=10000000` | Jurnal 5.000.000; jurnal 15.000.000 | Langsung `posted`; 202 usulan |
| U15 | statik | — | Cari di 12 berkas tabel B teks "tidak boleh menyetujui" dan pembanding `created_by_id == actor`; cari `tolak_bila_pelaku_sama("<aksi>"` untuk tiap aksi | 0 pembanding lama tersisa; tiap dari 35 aksi punya ≥ 1 titik pasang |
| U16 | B | Sopir (`02` §6) | `GET /api/kontrol/aturan`; `PUT` `kontrol.setujui_po.min_orang` | 403; 403 |
| U17 | B | — | Putaran `t1_config.py` untuk semua `kontrol.*` | Tulis grup dan PT terbaca; nilai "3" ditolak 400; tanpa alasan ditolak |
| U18 | layar (uji jalan) | Login Admin, PT `ent_ksc` | Tab Kontrol dua orang → Tim kecil → konfirmasi | Semua baris "Cukup satu orang", sumber "Aturan PT ini"; PT lain tidak berubah |

## Langkah kerja

**(a) Jalur baru, titik lama belum disentuh:** 1) `backend/tests_mem/test_KFT6_kontrol.py` U1, U3 (bagian pembantu), U11,
U16, U17 merah. 2) Katalog kunci + `dual_control.py` + `GET /api/kontrol/aturan`. 3) Layar tab. Gate; SHA.

**(b) Pengalihan:** 4) Uji U2–U10, U12–U15 merah. 5) Tabel A dan migrasi sakelar. 6) Tabel B, satu titik satu commit.
7) Tabel C. 8) Buka kembali tutup buku dan jurnal manual. 9) Gate penuh; laporan memuat SHA (a) dan (b) dan, untuk U13,
contoh angka jurnal → saldo (`00` §9).

## Dokumen ikut berubah

`ENTITY_REGISTRY.md` (`journal_proposals`, `period_closings.reopen_request`); `CODEBASE_MAP.md`
(`services/dual_control.py`, `config_catalog_kontrol.py`, `routers/kontrol.py`, `DualControlView.jsx`); `memory/PRD.md`;
`docs/KN_13_NAVIGATION_MAP.md` (tab baru); `docs/KN_32_GLOSARIUM_BAHASA_ANTARMUKA.md` ("kontrol dua orang").

## Di luar lingkup

- Siapa yang berwenang menyetujui dan pada nominal berapa (peringkat peran → izin + batas) → KP-T4.
- `bayar_hutang`, `cairkan_uang_muka`, satu batas pengurang piutang → PK-38; `ubah_profil_kredit` → CR-T1;
  `lembar_insentif` → KM-T3; tiga izin gaji terpisah → PY-T1; `asisten_uang_keluar` → AG-T5.
- Mengganti pemeriksaan nama peran Admin di `reopen_period` dengan izin → PR-T2.

## Asumsi dan risiko

- `ASUMSI:` empat titik † yang hari ini tidak mengecualikan Admin dipertahankan lewat `kontrol.admin_tetap_dua_orang`.
- `ASUMSI:` mode `warn` pada `approval.matrix_enforcement` dipindahkan sebagai "2" (pembantu selalu menolak; tidak ada
  mode "peringatkan saja" untuk kontrol dua orang).
- `ASUMSI:` `pengurang_piutang` memakai satu pasang kunci untuk bebas denda dan hapus selisih (K-11); batasnya diisi PK-38.
- `ASUMSI:` buka kembali tutup buku dan jurnal manual dua orang memakai pola "ajukan lalu dijalankan orang kedua" pada
  dokumennya sendiri, tanpa antrean baru di luar layar yang ada.
- `RISIKO:` titik tabel C yang dokumennya tidak menyimpan pengaju dengan andal membuat pilihan "2" tidak efektif. Tiap
  aksi tabel C punya tes "pengaju = pemutus → 403 saat 2"; aksi yang belum bisa lulus ditulis "belum teruji" di laporan
  dan pilihannya dikunci "Cukup satu orang" di layar.
- `RISIKO:` migrasi menulis ke data pengaturan saat proses awal; laporan menandainya untuk ditinjau sebelum rilis (H3).
  Membatalkan (b): kembalikan commit per titik; (a) tidak mengubah perilaku.
