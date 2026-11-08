# PREP-C — Fondasi gudang yang bisa dikonfigurasi · draf putaway otomatis · tiba bertahap

Tanggal: 9 Nov 2026 (WIB) · Pelaksana: Claude Code (implementer) · Dasar: `docs/rfid/KEPUTUSAN_GATE_RFID.md` §7
(K-GDG-01…11) + K-RFID-04/10 (keputusan pemilik 8 Nov 2026). Prinsip pemilik: **data lokasi & gedung belum valid →
semuanya bisa dikonfigurasi, tidak ditanam di kode.** Status: `implemented_pending_review` (belum diverifikasi reviewer).

## 1. Ringkasan
| # | Tujuan | Hasil |
|---|---|---|
| 1 | Profil gedung bisa diatur | Gate per gedung (`has_gate`, mode `gate`/`handheld`, pasangan IN/OUT dari `rfid_devices`, tata letak `terpisah`/`berdampingan_sekat`/`berdampingan`, catatan clear zone), peran `inspection` & `material`, `stock_mode` `roll_tagged`/`quantity`, `storage_form` `rack`/`floor` (gedung & zona), aturan `template_ids` (artikel) & `owner_entity_ids` (PT). Helper `warehouse_gate_policy(warehouse_id)` + `GET /api/warehouses/{id}/gate-policy`. Data lama `{physical_gate}` tetap terbaca (dicerminkan). Gudang baru bawaan **shared** (K-GDG-07). |
| 2 | Gedung tunggal (P9-K1) | Gedung ber-peran `storage`/`material` (termasuk yang merangkap transit/penerimaan pusat) → roll baru langsung `stored`. Berlaku untuk jalur PO dan hasil makloon (satu fungsi `inbound_qc_common.stage_for_roles`). |
| 3 | Inspeksi barang baru (K-GDG-04) | Penanda "minta inspeksi" = roll tercantum di **SPK QC 4-point (inspeksi per 15 yard) yang masih terbuka** → draf PA ke gedung `inspection` di lokasi yang sama (`purpose = inspection`). MD Quality tidak memindah barang. Tanpa gedung inspeksi di lokasi → perilaku lama. Retur: area QC = peran `inspection` atau `return` (dulu `{"return","qc"}` — `qc` bukan peran sah). |
| 4 | Draf putaway otomatis (K-GDG-10) | Sesudah keputusan QC lulus (antrean karantina **dan** tutup SPK MD Quality — keduanya lewat `qc_service.process_qc_decision`), GRN tanpa QC, atau SPK QC 4-point ditutup → DRAF PA per (gedung asal, PT, gedung tujuan, tujuan). Status `draft` sebelum `open`; admin cek/ubah → terbitkan. Pengaturan `putaway.auto_draft` (bool, bawaan aktif, per badan usaha). Idempoten. |
| 5 | Tiba bertahap (K-GDG-10, K-RFID-10) | `confirm_arrival_trip(order_id, epcs, source, actor)` + `POST …/arrival-trips`: satu panggilan = satu trip; status `partially_received`; roll yang belum terbaca tetap menunggu; penutupan `POST …/close` (sisa → kembali ke transit / pengecualian). Klaim saga, CAS roll, BTG pertama, mutasi ber-id deterministik tetap. **Belum disambungkan ke gate.** |
| 6 | Celah 27 Okt | `accept` pengecualian kini butuh `wms.approve` (setara konfirmasi manual); roll DITAHAN ditolak masuk PA (buat manual, klaim, kirim, draf); status akhir tanpa satu pun roll tiba = `returned`/`exception`, tidak pernah `completed`. |
| 7 | K-GDG-09 | Tidak ada pengecualian stok transit (P9.6 tidak dibangun). Draf **tidak** mengklaim roll → stok transit tetap bisa dialokasikan/dijual sampai draf diterbitkan. |

## 2. Berkas
Backend (milik C):
- `backend/services/warehouse_profile_service.py` — peran baru, `normalize_rules`, `normalize_gate_config` (baca kompatibel), `validate_profile` (+`stock_mode`, `storage_form`), `validate_zone_forms`, `assert_profile_refs` (perangkat gate milik gedung & arah cocok; artikel & PT ada), `gate_policy_of` / `warehouse_gate_policy`, blueprint (RCM-RETUR = inspeksi, tanpa gate).
- `backend/services/placement_rules.py` — aturan `template_ids`/`owner_entity_ids` di semua lapis (AND), `warehouse_violations(..., attrs=False)` untuk PA inspeksi, `storage_form` efektif (zona > gedung > rak).
- `backend/routers/warehouses.py` — PATCH allow-list `stock_mode`, `storage_form`; validasi rujukan; normalisasi zona (PATCH & PUT struktur); bawaan `shared`; `GET /warehouses/{id}/gate-policy`.
- `backend/services/putaway_order_service.py` — status hidup/arrival, blok roll ditahan, satu roll satu antrean (draf), komponen bersama (`roll_violation`, `claim_rolls`, `after_claim`, `qty_summary`, `return_items_to_transit`), tujuan `inspection` (tiba → kembali ke tahap terverifikasi), konfirmasi lama memakai mesin trip, status akhir dari status item.
- `backend/services/putaway_draft_service.py` (baru) — draf otomatis, routing inspeksi, detail/ubah/terbitkan/batal.
- `backend/services/putaway_arrival_service.py` (baru) — trip, penutupan sisa, `final_status`.
- `backend/routers/putaway_orders.py` — `POST /putaway-orders/auto-draft`, `GET /putaway-orders/{id}`, `PATCH …/{id}/draft`, `POST …/{id}/publish`, `POST …/{id}/cancel-draft`, `POST …/{id}/arrival-trips`, `POST …/{id}/close`; `resolve-exception` accept → `wms.approve`.
- `backend/services/inbound_qc_common.py` — `stage_for_roles` (gedung tunggal), `auto_draft_after_release` (best-effort).
- Kait kecil: `qc_service.py` (sesudah keputusan QC), `inbound_complete_service.py` (GRN tanpa QC), `inspection_service.py` (tutup SPK QC 4-point), `return_journey_service.py` (peran area QC).
- `backend/config_catalog_ops.py` — entri `putaway.auto_draft`.
- `backend/services/roll_timeline_service.py` — satu filter: draf/batal tidak tampil sebagai kejadian roll (di luar daftar milik C, satu baris).
- `scripts/guardrails/verify_atomic_claim.py` — entri REVIEWED untuk `dispatch`, `publish`, `arrival-trips`, `close`.
- `scripts/fix_data_2026_11_08_profil_gedung.py` (baru) — nilai awal profil (hanya `kn_test_trial`; DB lain ditolak; dry-run bawaan).

Frontend:
- `warehouses/WarehouseProfileDrawer.jsx` (+ baru `WarehouseGateSection.jsx`, `warehouseProfileUtils.js`), `warehouseApi.js`, `WarehouseMasterView.jsx` (ringkasan gate/aturan, bawaan shared).
- `location/NodeRulesEditor.jsx`, `StructureEditor.jsx`, `locUtils.js` (+ baru `useRuleRefs.js`) — bentuk simpan zona, aturan artikel/PT per node.
- `PutawayOrdersPanel.jsx` (+ baru `PutawayDraftsPanel.jsx`, `putawayUtils.js`) — panel draf, "Catat trip (tiba sebagian)", tutup sisa, status baru.

Uji: `backend/tests/test_prep_c_warehouse_putaway.py`, `frontend/src/features/__tests__/prepCWarehousePutaway.test.js`.

## 3. Perubahan perilaku untuk pengguna
- **Gedung tunggal (Soreang, Jakarta, atau gedung lain yang diberi peran Penyimpanan + Transit/Penerimaan Pusat):** roll
  baru langsung **Tersimpan** — cukup ditempatkan ke bin; tidak ada lagi roll "Diterima di Transit" yang menunggu PA ke
  gedung lain yang tidak ada. Roll lama yang sudah terlanjur `received_transit` tidak diubah (P9-K3 belum diputuskan).
- **Draf putaway otomatis:** sesudah QC lulus / GRN tanpa QC, menu Lokasi & Putaway menampilkan panel **"Draf Putaway
  otomatis"**: draf per gedung tujuan (aturan gedung: kategori, grade, jenis kain, artikel, PT; bahan → gudang bahan).
  Admin membuka draf → melihat roll siap/belum siap (tag/label belum terverifikasi) dan yang diminta inspeksi → boleh
  ganti tujuan / keluarkan roll → **Terbitkan** (semua siap) atau **Terbitkan yang siap** (sisanya pindah ke draf baru)
  → PA berstatus Terbuka seperti biasa (Kirim → Konfirmasi tiba). Tombol **Siapkan draf** mengisi draf untuk roll lama
  di gudang yang belum masuk PA mana pun. Pengaturan `putaway.auto_draft` (Pengaturan › stok) mematikannya per PT.
- Roll yang sudah ada di draf **tidak** muncul lagi di "Siap Simpan ke Rak" (saran manual) dan tidak bisa dibuatkan PA
  manual sebelum draf diterbitkan/roll dikeluarkan — satu roll satu antrean.
- **Tiba bertahap:** pada PA terbuka/dalam perjalanan, **Catat trip** mencatat muatan yang terbaca saja; roll lain tetap
  menunggu (status "Tiba Sebagian", BTG terbit saat trip pertama). Sisa diputuskan dengan **Kembali ke transit & tutup**
  atau **Jadikan exception & tutup** (alasan min. 10 huruf). Tombol lama **Validasi & tutup (BTG)** = perilaku lama
  (yang tidak terbaca menjadi exception).
- **Terima exception** kini butuh izin approve (Admin Gudang/Manajer/Admin); petugas gudang biasa ditolak 403.
- PA yang semua rollnya dikembalikan tanpa satu pun tiba berstatus **Dikembalikan ke Transit** (dulu "Selesai" tanpa BTG).
- Profil Gedung: peran Inspeksi & Gudang Bahan, mode stok (kuantitas = gate tidak berlaku), bentuk penyimpanan, artikel
  & PT pemilik pada aturan gabungan, gate per gedung dengan pasangan IN/OUT. Gudang baru bawaannya **dipakai bersama**.

## 4. Keputusan desain (implementer — mohon ditinjau)
1. **Roll belum `tag_verified`/`label_verified`** boleh masuk draf (ditandai "belum siap" + alasan); draf hanya bisa
   diterbitkan untuk roll yang siap. `split_unready=true` menerbitkan yang siap dan memindah sisanya ke draf baru
   (`split_from`). Klaim roll (`active_movement`, keluar ATP) baru terjadi saat **terbit**, bukan saat draf.
2. **Idempotensi draf:** `_id` dokumen draf = hash(pemicu + gudang asal + PT + tujuan + tujuan-PA + himpunan roll);
   retry pemicu yang sama tidak membuat draf kedua (draf yang sengaja dibatalkan juga tidak lahir ulang dari pemicu yang
   sama); roll yang sudah ada di PA hidup (draf/terbuka/jalan/tiba sebagian) dilewati untuk pemicu lain. Tombol "Siapkan
   draf" memakai pemicu per menit.
3. **Penanda minta inspeksi** = roll di SPK `qc_4point` berstatus draft/assigned/in_progress (tidak ada penanda lain di
   repo; tidak ditambah pengaturan baru). SPK QC 4-point yang dibuat **sesudah** draf terbit tidak memindah draf; layar
   detail draf memberi peringatan bila ada roll diminta inspeksi tetapi tujuan bukan gedung inspeksi.
4. **PA ke gedung inspeksi** (`purpose = inspection`): aturan SIMPAN tujuan (kategori/grade/…) tidak berlaku (roll hanya
   singgah), izin pakai gedung (shared/dedicated) tetap. Saat tiba roll kembali ke tahap terverifikasi asalnya
   (`journey.inspection_site`), sehingga sesudah SPK QC 4-point ditutup sistem menyiapkan draf ke gudang simpan; bila
   gedung inspeksi juga gudang simpan dan aturannya menerima roll itu, roll langsung `stored` di sana.
5. **BTG** tetap satu nomor per PA (terbit pada trip pertama yang memindah roll); setiap trip tercatat di
   `arrival_trips[]` (no. trip, sumber gate/handheld, roll tiba, sudah tiba, kode asing).
6. **Trip idempoten** lewat `passage_id` (gate) / `client_trip_id` (handheld). Trip tanpa roll baru tidak dicatat.
   Dua trip bersamaan → yang kedua 409 `SAGA_IN_PROGRESS` (paket gate perlu mengulang).
7. **Gate**: perangkat pasangan wajib reader `type=gate` milik gedung yang sama, arah cocok, tidak dipakai dua kali.
   Mode `gate` tanpa perangkat IN boleh disimpan (perangkat belum datang) — `gate_policy.gate_ready=false` + catatan.
   `effective_mode`: `gate` / `handheld` / `manual` (gedung mode kuantitas).
8. **Mode kuantitas**: hanya disimpan & ditandai; gedung kuantitas dilewati draf otomatis. Mesin stok kuantitas tidak dibangun.
9. Skrip nilai awal: gate = gedung **penyimpanan murni** di Rancamalang/Soreang (Woven, Knitting, Printing, SRG-01);
   **RCM-RETUR diberi peran inspeksi dan dianggap tanpa gate (handheld)** — asumsi, lihat §6.

## 5. Bukti uji (apa adanya)
Lingkungan: kontainer `kn-tmp-c-mongo` + `kn-tmp-c-be` (snapshot `kn_test_trial_2026-11-08`, DB `test_database`).
- Pytest baru `tests/test_prep_c_warehouse_putaway.py`: **15 passed** (profil + validasi tiap field, gate/perangkat/
  tata letak/legacy, aturan artikel/PT & bentuk simpan zona, peran area QC retur, gedung tunggal, routing inspeksi &
  idempoten, config off & roll ditahan, kait QC, kait GRN tanpa QC, ubah/terbit/split/batal draf, multi-trip + tutup
  kembali-transit, 0 tiba → `exception`/`returned` + accept butuh approve, `confirm_arrival_trip` gate, izin HTTP,
  endpoint siapkan draf). Residu nol (PA 2 dokumen lama, roll uji 0).
- Uji lama relevan, **sebelum vs sesudah identik** (tidak ada merah baru, tidak ada yang berubah hijau):
  - Batch 1 (iter263/264/265, p02_wms_putaway, p02_retest, uat24_f1/f2, g3_phase01/02b/04, inbound_complete_characterization,
    grn_phase2, l08_ln081_journey, iter267, iter278, fase_sl_scan_label): **32 failed, 111 passed, 29 skipped** sebelum
    dan sesudah — merah yang sama (sudah merah sebelum PREP-C: `test_fase_sl_scan_label` 17, `test_iter265` 6 (R3/R5),
    `test_p02_retest` 3, `test_iter267` 3, `test_iter278` 2, `test_p02_wms_putaway` 1).
  - Batch 2 (f11_f12, f14, iter12, iter258, l10 ×2, makloon_celup_rolls, p03_transfer_receipt, p05_imp16, p19_roll_hold,
    trial_22okt, uat24_f0/f3, uat26_d2, phase4_r6, role01, lanjutan_sched_returns, uat_v3_ui_gaps3):
    **20 failed, 146 passed, 9 skipped, 17 errors** sebelum dan sesudah — sama persis (merah lama: `test_iter258` 11,
    `test_p03_transfer_receipt` 11 error, `test_f11_f12` 6 error, `test_p19_roll_hold_release` 5, `test_l10_t1_review` 2,
    `test_l10_ln100_ln102` 1, `test_lanjutan_sched_returns_interco` 1).
  - Tambahan (iter117_p09, phase3_p2_settings_groups, g3_phase04_live, iter315_saga_locks, uat26_d3, return_per_roll):
    61 passed, 1 failed (`test_iter315…test_saga_locks_lists_new_collections`: pelepasan kunci saga butuh alasan ≥ 10 —
    tidak terkait PREP-C; baseline tidak diukur).
- Jest: `prepCWarehousePutaway` **5 passed**; `permissionGates` passed. ESLint berkas yang diubah: **0 error**, 1
  peringatan lama (`PutawayOrdersPanel.jsx` baris `eslint-disable-line` yang sudah ada).
- Guardrail (sesudah): custom_modals, error_notice, escape_layers, uom_vocab, knselect_contract, picker_portal,
  detail_modal, modal_dismiss, page_tabs, role_label, status_history **PASS**; auth_coverage **8**, atomic_claim **6**
  (114 cek; BELUM DITINJAU 77 → 75), to_list_bound **6**, qty_dual **5**, numeric_bounds **3**, ref_unlink **3** — sama
  dengan baseline, tidak naik. `verify_atomic_claim --self-test` merah 2 — sudah merah di HEAD.
- Skrip `fix_data_2026_11_08_profil_gedung.py`: `--db test_database` → DITOLAK (exit 2); dry-run `kn_test_trial` 13
  gedung; `--apply` di **salinan pribadi** `kn_test_trial` dalam kontainer uji (bukan DB koordinator) → 13 diperbarui;
  dry-run ulang 0 (idempoten). **Belum dijalankan di DB koordinator.**
- `verify_state_machine.py` tidak dijalankan (sesuai brief). CODEBASE_MAP.md tidak diregenerasi.

## 6. Sisa / butuh keputusan pemilik
1. **Gate di Gedung Retur RCM**: K-GDG-01 "gate hanya di gedung penyimpanan"; Gedung Retur juga menyimpan grade B/BS/C.
   Skrip & blueprint menganggap RCM-RETUR = gedung inspeksi **tanpa gate (handheld)**. Mohon konfirmasi.
2. **Hasil makloon tanpa QC** (`makloon_receipt_qc`, di luar berkas milik C) belum memicu draf otomatis; dengan QC
   (K-GDG-11, ikut setelan PO) sudah lewat keputusan QC. Perlu satu kait di `makloon_receipt_qc.py`.
3. **Gedung tunggal + gedung inspeksi di lokasi yang sama**: roll gedung tunggal lahir `stored`, sehingga tidak diarahkan
   ke gedung inspeksi otomatis (perilaku lama). Belum ada lokasi seperti itu menurut fakta pemilik.
4. **Roll lama `received_transit` di gedung simpan** (P9-K3) tidak diluruskan otomatis — tetap menunggu keputusan.
5. **Penamaan alamat rak/bin & clear zone per gate** (K-RFID-04) masih terbuka — kolom catatan clear zone disediakan.
6. `wms_health_service` (bukan milik C) belum menghitung PA `partially_received` sebagai PA terbuka di dasbor.
7. Paket gate (D1) tinggal memanggil `putaway_arrival_service.confirm_arrival_trip(order_id, epcs,
   {"type": "gate", "passage_id": …}, actor)` dan `warehouse_profile_service.warehouse_gate_policy(warehouse_id)`.
8. Paket B menambah kait pembekuan di `putaway_order_service.py` — titik yang wajar: `roll_violation` (dipakai buat manual
   & terbit draf), `dispatch`, dan `_land_items`.
