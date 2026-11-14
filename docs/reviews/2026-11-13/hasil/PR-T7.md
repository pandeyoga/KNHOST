# PR-T7 — Tombol dan panggilan data di layar mengikuti izin, bukan nama peran

- Commit awal: `3224848` (dikerjakan) · digabung di atas `db7e563` (sesudah PR-T3, PR-T4 dan perbaikan susulan)        - Commit akhir: `2d164c9` (koreksi blueprint `3612b73`)        - Branch: `claude/nifty-carson-jjx3c8`
- ID ditangani: PR-11, PR-16 (beserta butir layar PR-UX-08; ikut: PR-UX-41, PR-UX-42) — K-47
- Koreksi blueprint (commit terpisah `[PR-T7] Koreksi blueprint: …`): `docs/blueprint/unit/PR-T7.md` — field
  `view_actions` tidak ada di `GET /api/auth/me` (lihat "Menyimpang dari blueprint" 1)

## Cek ulang "Keadaan sekarang" (di `3224848`)

| # | Hasil |
|---|---|
| 1 | Berlaku. `roleIs(` 52 pemakaian di 36 berkas (sama persis); `can(` 300 di luar `config/` (blueprint: 282); `roles.js:156` (`roleIs`), `:445` (`can`). Penjaga baru menghitung 96 gerbang nama peran di 65 berkas (52 `roleIs` + 6 `roleSatisfies` + 20 `.includes(…role)` + 18 `role === "<id>"`) — `bukti/PR-T7/role_gate_ui_daftar_awal.tsv` |
| 2 | Berlaku. `roles.js:156`; `ProductionParts.jsx:12` (`prodPerms(role)` daftar tertulis) |
| 3 | Berlaku; bergeser: `verify_role_label.py:57` (`ROLE_IDS`, enam id), `AUTHORITY_ENDPOINTS` kini baris 72 |
| 4 | Berlaku. `roles.js:451` (`canCurrent` → `!ACCESS.current \|\| …`), `:354` (`setAccessContext` butuh `view_resources`); `routers/auth.py` login tanpa `view_resources`/`hidden_views` |
| 5 | Berlaku. `CoreWidgets.jsx:8`, `KeepPendingPanel.jsx:30`, `EmployeeSelfService.jsx:153`. Tambahan temuan: di data acuan **0 dari 17** akun aktif punya `users.employee_id`, 14 tertaut hanya lewat `hr_employees.user_id` (proses awal `bootstrap.py:1360` tidak mengisi `users.employee_id`) — lihat Menyimpang 2 |
| 6 | Berlaku; bergeser: `approvalInboxData.js:41` (`grab`), panggilan di 45–57 |
| 7 | Berlaku, tidak diubah: `RoleMenuPreview.jsx:28` |
| 8 | Berlaku. `AskKnButton.jsx:4` + `:20` (`canAsk` membaca `localStorage`), `App.js:310`, `MobileOpsApp.jsx:138` |
| 9 | Berlaku. `MobileAppSwitch.jsx:48` |

Tabel 3, jangkar yang bergeser: #11 `VendorBillsView.jsx:76`; #18 `CashAdvanceDetail.jsx:47`; #22 `ClosingView.jsx:60`;
#22b `SettingsHub.jsx:391` (KF-T1 sudah selesai: simpan per kunci memakai `can_edit` server; `isAdmin` yang tersisa
menjaga tab Kunci Saga & aksi Data Hygiene). #21 tidak berlaku lagi — `routers/inspections.py:74, 464` sudah
`has_permission(actor, "inspection", "release" | "create")` sejak PR-T2 (layar tidak berubah, sesuai spesifikasi).

## Perubahan

### Server

| Berkas | Isi |
|---|---|
| `backend/routers/auth.py` | `POST /api/auth/login` kini membawa `hidden_views`, `view_resources` (= `_my_nav`, sama dengan `/auth/me`) dan `roles` (= `GET /api/roles`, sesudah `sync_registry`); `user.employee_id` di login dan `/auth/me` = id karyawan dari `hr_employees.user_id` (sumber yang sama dengan `/hr/employees/me`), `""` bila tidak tertaut |
| `backend/services/rnd_spec_service.py` | `_policy_roles` + `role_allowed(actor, policy_key, entity_id)` (jawaban tanpa melempar); `_assert_role` memakainya — aturan tidak berubah |
| `backend/services/rnd_sample_service.py` | `caps_for(doc, actor)` → `{pick_winner, approve_spec}`: kebijakan `rnd.sample_decision_roles` (sample uji ulang selalu boleh, seperti `decide_sample`) dan `rnd.spec_approval_roles` pada PT spesifikasinya |
| `backend/routers/rnd.py` | `GET /api/rnd/samples/{id}` menambah `caps` |

Tidak ada endpoint baru, izin baru, atau perubahan matriks (`permissions_config.py`/`access_modules.py` tidak disentuh,
fixture akses frontend tidak perlu dibangkitkan ulang).

### Layar — konteks izin dan kerangka (tabel 1–2)

| Berkas | Isi |
|---|---|
| `config/roles.js` | `setAccessContext` mencatat peran & izin walau `view_resources` belum ada; `canCurrent` = **tidak** bila konteks belum dimuat dan peran bukan Admin |
| `hooks/useAppActions.js` | login: `registerDynamicRoles(response.roles)` sebelum layar pertama; `view_resources`/`hidden_views` disimpan di objek akun (beranda peran kustom langsung benar — PR-UX-41) |
| `components/CoreWidgets.jsx` | lencana jurnal gagal: tanpa `accounting.view` tidak memanggil; dihitung ulang bila izin berubah |
| `features/sales_admin/KeepPendingPanel.jsx` | tanpa `order.verify`/`order.view` tidak memanggil dan tidak menggambar |
| `features/hr/EmployeeSelfService.jsx` | `employee_id === ""` → tidak memanggil `/hr/employees/me`; tampil "Akun ini belum ditautkan ke data karyawan. Minta Admin menautkannya di Akun & Akses." (field tidak ada = sesi lama → perilaku lama) |
| `features/approvals/approvalInboxData.js`, `ApprovalInbox.jsx` | `loadInbox(perms)`: hanya kategori yang izin lihatnya dipegang dipanggil (`CATEGORY_PERMS` = gerbang endpoint); kategori lain tidak dihitung "belum lengkap" |

### Layar — tabel penggantian (berkas:baris · gerbang lama · izin baru · endpoint yang dijaga)

| # | Berkas:baris (sesudah) | Gerbang lama | Izin / bendera baru | Endpoint |
|---|---|---|---|---|
| 1 | `rnd/SampleDetailPanel.jsx:79` (`sampleButtonPerms`) | `roleIs` enam daftar | Kirim/ronde/selesai `rnd.submit` · Nilai `rnd.assess` atau `rnd.assess_<jenis>` semua jenis · Putuskan `rnd.decide` (uji ulang: + `rnd.decide_<jenis>`) · PIC `rnd.pic_decide` · paksa lulus `rnd.override_fail` · Batalkan `rnd.manage` · Ubah `rnd.create` | `/rnd/samples/{id}/send\|rounds\|finish\|deliver\|issue-material`, `…/assess` (`_require_typed`), `…/decide`, `…/pic-decision`, `…/cancel`, `PATCH /rnd/samples/{id}`, `…/spec` |
| 2 | `rnd/SampleDetailPanel.jsx:94-95`; `rnd/SampleMasterDataPanel.jsx:16` | daftar peran pengaturan dicocokkan nama | `caps.pick_winner`; ACC spesifikasi `rnd.assess` + `caps.approve_spec`; rilis `rnd.decide` + `caps.approve_spec` | `…/decide`, `/rnd/specs/{id}/approve`, `…/release-product` |
| 3 | `design/DesignRequestDetailPanel.jsx:72-79` | `roleIs` | `design_request.decide` · `.assign` · `.update` (kategori) · `.deliver` · `.create` (rujukan, Ajukan) · `.cancel` | `/design-requests/{id}/approve\|reject\|assign\|start\|link-design\|references\|submit\|cancel`, `PATCH` |
| 4 | `design/DesignRequestsView.jsx:133-134` | `roleIs` | `design_request.create` · `.report` | `POST /design-requests`, `/design/reports/by-designer` |
| 5 | `rnd/RndDesignsView.jsx:76-77`; `rnd/design/DesignDetailPage.jsx:49-51` | `roleIs(admin, manager)` | penilai `rnd.assess`; master kategori `rnd.manage`; ubah/buat `rnd.manage \| hr.manage_attendance \| design_request.deliver` | `design_studio.py` (`_perm_assess`, `/design-studio/categories`), `_perm_manage` |
| 6 | `production/ProductionParts.jsx:14`; `ProductionView.jsx:20` | daftar tertulis | `production.manage_bom/create/release/complete/cancel` | `routers/production.py:95-214` |
| 7 | `documents/DocumentCenter.jsx:49-50`; `DocumentActionsBar.jsx:45` | `ESIGN_ROLES`, `WA_MANAGE_ROLES` | `esign.sign` · `document_delivery.manage` | `/esign/request`, `/deliveries/whatsapp/settings` |
| 8 | `finance/amendments/AmendmentTrailPanel.jsx:37` | `PROPOSER_ROLES` | `finance_amendment.propose` | `POST /amendments` |
| 9 | `catalog/CatalogWorkspace.jsx:45` | `["admin","md"]` | `product.view` + `product.retire` | `DELETE /master/{kind}/{id}/purge` (`may_retire`) |
| 10, 11 | PO, tagihan pemasok, voucher biaya masuk | `roleSatisfies` | **tidak diubah** — KP-T4 belum selesai (status `menunggu`) | — |
| 12 | `crm/CrmView.jsx:21-22` | `roleIs(admin, manager)` | Skema `sales_force.view` · Persetujuan Kredit `credit_override.approve` | `/sales-targets`…, `/credit-overrides/{id}/decision` |
| 13 | `crm/Customer360Panel.jsx:35` | `roleIs` | `sales_force.assign` | `POST /customers/{id}/reassign` |
| 14 | `crm/SalesForceDashboard.jsx:18-20` | `roleIs` | tim/papan/status GL `sales_force.view` · Set Target `.update` · posting akrual `.post` | `/sales/leaderboard`, `/sales/incentive/gl-status\|post-gl`, `/sales-targets` |
| 14b | `crm/IncentiveSchemeEditor.jsx:18` | `roleIs` | `sales_force.update` (pesan tolak bentuk Z6) | `POST /sales-targets`, `/sales-incentives` |
| 15 | `marketing/PostDetailModal.jsx:28` | `roleIs(admin, manager)` | `marketing.update` + `marketing.approve` | transisi `approved` (`marketing_service`) |
| 16 | `marketing/TemplatePicker.jsx:16` (Campaigns: KP-T4) | daftar tertulis | `marketing.update` + (pembuat atau `marketing.delete`) | `DELETE /marketing/templates/{id}` |
| 17 | `samples/SampleOrdersView.jsx:70` | izin + `roleIs` | `sample_order.approve_payment` saja | `POST /sample-orders/{id}/approve-payment` |
| 18 | kas kecil | `roleIs` tahap | **tidak diubah** — KP-T4 | — |
| 19 | `sales/SalesPortal.jsx:322` | `user.role === "sales"` | `roleIs(role, ["sales"])` (= `role_in` server) sampai PR-T4 | `POST /sales-orders` (pilih roll) |
| 20 | `wms/grn/GoodsReceiptsView.jsx:43-44`; `settings/ReceivingOcrSettings.jsx:13-18` | daftar tertulis | tab mode lama `wms.update`; pintasan = salah satu izin tab tujuan; tab Profil SJ & Sample OCR `goods_receipt.review`, Biaya OCR `.approve`, Mode `.configure` | `/inbound/tasks/*`, `/goods-receipts/dn-profiles`, `/ocr-samples`, `/goods-receipts/usage`, `PUT /goods-receipts/mode` |
| 22 | `finance/ClosingView.jsx:60` | `role === "admin"` | `accounting.manage` + `accounting.reopen` | `/finance/closing/{id}/reopen`, tembus Suspense di `/close` |
| 22b | `settings/config/SettingsHub.jsx:392` | `role === "admin"` | `system_tools.configure` (tab Kunci Saga, aksi Data Hygiene) | `/saga-locks`, `/data-hygiene/run\|revert\|unlock` |
| 23 | `components/AskKnButton.jsx:21-22`; `App.js:310`; `mobile/MobileOpsApp.jsx:216` | daftar tertulis | `ai.view` | asisten Tanya KN |
| 24 | `mobile/MobileAppSwitch.jsx:49`; `mobile/mobileLayout.js` (baru); `sales/mobile/MobileSalesApp.jsx:36`, `MobileOrders.jsx:45`, `MobileMore.jsx:64,196`; `mobile/MobileRoleSummary.jsx:21` | `roleIs` memilih aplikasi | tata letak dari halaman awal peran (tabel di `mobileLayout.js`; PR-T4 menambah kategori kerja) | — |
| 25 | `settings/entities/AccountFormDrawer.jsx:49` | `CROSS_ROLES` | **tidak diubah** — PR-T6 | — |

Sisa menurut tabel 4:

| Berkas:baris | Gerbang lama | Pengganti | Endpoint |
|---|---|---|---|
| `App.js:324` | `roleIs(admin, manager)` (`canGenerate`) | `system_tools.update` | `POST /notifications/generate` |
| `rnd/RndSamplesView.jsx:80-81` | `roleIs` | Buat `rnd.create`; antrean PIC `rnd.assess` | `POST /rnd/samples`, `/rnd/revalidation/pic-queue` |
| `rnd/RndReportsView.jsx:48`; `designer/DesignerKpiView.jsx:69` | `roleIs(admin, manager)` | `rnd.manage` | ubah kunci `rnd.*` (izin kunci), `POST /rnd/sla/escalate` |
| `designer/DivisionsView.jsx:56` | `roleIs(admin, manager)` | `rnd.manage_org` | `PUT /rnd/divisions/members` |
| `orders/SoApprovalsPanel.jsx:35-37` | `roleIs(sales, sales_admin) \|\| penyetuju` | ajukan harga `price_approval.create` · minta kredit/lanjut harga normal `order.update` · batalkan `order.cancel` | `/price-approvals`, `/sales-orders/{id}/request-credit-approval`, `…/continue-normal-price`, `…/cancel` |
| `sales/SpecialOrderPricingPanel.jsx:170, 181` | `roleIs(admin)`; `roleIs(manager, admin)` bila ada catatan pengadaan | buka kunci `order.update` + `od_pricing.unlock`; realisasi = izin endpoint saja | `…/unlock-price`, `…/procure` |
| `sales/mobile/MobileOrders.jsx:46-47` | `roleIs(sales_admin)` | `order.confirm` (+ `internal_request.convert` untuk pemenuhan) | `…/review-release`, `…/release`, `/sales-admin/orders/{id}/fulfillment-plan` |
| `mobile/MobileOpsApp.jsx:153, 200-208` | `roleIs(sample_admin)`; `["admin","manager","md"]`; `role !== "md"` | SORD `order.approve` + tata letak K-11 dari halaman awal; tab Pintasan dari halaman awal, tiap tombol `product.view`/`rnd.view`/`goods_receipt.view` | `/special-orders/{id}/approve`, layar tujuan |
| `wms/LocationPutawayView.jsx:46`; `wms/transfer/TransferReceiptPanel.jsx:29` | `roleIs(SUPERVISORS)` | `wms.approve` (= `placement_rules.is_supervisor` sejak PR-T2) | struktur bin, pengecualian putaway/terima |
| `settings/config/PriceCorrectionsView.jsx:17` | `role === "admin" \|\| …` | `product.update` | `POST /config/impact-apply` |
| `desks/RoleDesk.jsx:38` | `role === "admin" \|\| …` | `order.view` | daftar pesanan |
| `finance/cases/CasePlaybookWizard.jsx:358` | `approver_role === "admin" ? "admin" : "manager"` (id mentah tampil) | label `roleLabel(...)` | — (teks) |
| `inspections/InspectLineModal.jsx:35` | peta judul berisi label peran ditulis tangan | `roleLabel(...)` (penjaga INV-ROLE-01 kini mengenal 13 peran) | — (teks) |
| `hr/MyDesignerKpiSection.jsx:25,30,31`; `rnd/design/FeedbackThread.jsx:49` | `roleIs`/`===` | tetap, berpenanda `// tata-letak:` (bagian KPI milik sendiri; teks petunjuk) | — |

### Penjaga

- Baru `scripts/guardrails/verify_role_gate_ui.py` (INV-ROLE-02, ratchet, pola `verify_custom_modals.py` + `_ratchet.py`):
  menghitung per berkas `roleIs(`, `roleSatisfies(`, `roleRank(`, `.includes(<argumen berakhiran role>)` (termasuk
  `JSON.parse(…)?.role`), `<x>role ===|!==|==|!= "<id>"` dan kebalikannya; 13 id dibaca dari `backend/role_registry.py`;
  pengecualian sesuai spesifikasi + baris `// tata-letak: <alasan>` (penanda tanpa alasan tidak diakui). `--init`,
  `--update` (menjaga catatan `pemegang`), `--list`, `--self-test` (20 cek; salinan berkas nyata disisipi dua gerbang →
  merah; satu baris tata letak lolos).
- Garis dasar `scripts/guardrails/baselines/role_gate_ui.json`: awal 96 gerbang / 65 berkas → akhir **29 / 23**, tiap
  berkas dengan catatan pemegang (tabel di "Menyimpang" 4).
- `scripts/gate.sh` bagian statik: `guard:role_gate_ui SELF-TEST …` dan `guard:role_gate_ui (INV-ROLE-02, tombol dari izin)`.
- `verify_role_label.py`: `ROLE_IDS` dibaca dari registry (13 peran).

### Dokumen

`docs/KN_08_UI_UX_STANDARDS.md` (bagian "Tombol dari izin, panggilan kerangka dijaga izin" + butir daftar periksa);
`CODEBASE_MAP.md` dihasilkan ulang (`scripts/gen_codebase_map.py`). Arsip audit tidak diubah.

## Uji penerimaan

| ID | Lapis | Merah di kode lama | Hasil |
|---|---|---|---|
| U1 | B | ya (penjaga belum ada) | Lulus — `verify_role_gate_ui.py` keluar 0; `--self-test` 20/20 (2 sisipan tertangkap, baris tata letak lolos) |
| U2 | B | ya (52 `roleIs`) | Sebagian — sisa `roleIs` di luar pengecualian: baris berpenanda `// tata-letak:` + garis dasar 29 gerbang/23 berkas. Garis dasar memuat KP-T4 (9 berkas), PR-T6 (2), **juga** PR-T4 cakupan data/kategori kerja (7), H7 RFID (4), 1 berkas yatim — lihat Menyimpang 4 |
| U3 | B | ya (tanpa `view_resources`) | Lulus — `tests_mem/test_PRT7_layar_izin.py::test_PRT7_U3_…` (`view_resources`, `hidden_views`, `permissions` = `/auth/me`; `roles` = `/api/roles`, memuat peran kustom, `home_view` `hr-my-profile`) |
| U3b | B | ya (tanpa `employee_id`) | Lulus — akun tanpa karyawan `""` + `/hr/employees/me` 404; tertaut lewat sisi HR → terisi + 200 |
| U4 | B | ya (`caps` tidak ada) | Lulus — manajer `pick_winner` benar; "Tanpa Acuan" + `rnd.view`+`rnd.decide` = jawaban `_assert_role` (salah); Sopir 403. U4b: `approve_spec` = kebijakan; uji ulang selalu boleh |
| U5 | komponen | ya | Lulus — tanpa konteks / peran tanpa izin → `false`; Admin → `true` |
| U6 | komponen | ya | Lulus — `{production:[view,create]}` → hanya `createWo` |
| U7 | komponen | ya | Lulus — kustom tanpa acuan + `credit_override.approve`: tab Persetujuan Kredit ada, Skema tidak |
| U8 | komponen | ya (kedua tab ada) | Lulus — berdasar Manajer + `{customer:[view]}`: kedua tab tidak ada |
| U9 | komponen | ya | Lulus — `{ai:[view]}` kustom tampil; Manajer tanpa `ai` tidak |
| Tabel 2 | komponen | ya (3 dari 5) | Lulus — Keep & Pending tidak memanggil tanpa izin; Profil Saya tidak memanggil bila `employee_id` kosong; Pusat Persetujuan hanya memanggil 3 kategori, `unavailable` kosong |
| #1/#2, #24 | komponen | ya (fitur belum ada) | Lulus — tombol sample dari izin + `caps`; aplikasi HP 13 peran bawaan = pemilihan lama, peran kustom ikut halaman awal |
| U14 (padanan B) | komponen | — | Lulus — dengan izin bawaan (`access_builtin_fixture.json`) 23 gerbang: Manajer & Admin tidak kehilangan tombol; satu-satunya yang hilang `md:dsr.batal` (MD tidak memegang `design_request.cancel` → server 403) |
| U10–U15 | A (peramban) | — | **Belum dijalankan** (tanpa backend/peramban di lingkungan kerja ini). Uji lapis A HTTP ditulis: `backend/tests/test_bp_PRT7_layar_izin.py` (U3, U3b, U4 di MongoDB asli) — belum dijalankan |

Bukti: `bukti/PR-T7/tests_mem_PRT7_merah_kode_lama.log` (4 gagal: tanpa `view_resources`, tanpa `employee_id`,
`KeyError: 'caps'` ×2) → `tests_mem_PRT7_hijau_kode_baru.log` (4 lulus); `jest_prt7_merah_kode_lama.log` (11 dari 14 gagal;
3 yang lulus = kasus kontrol) dan `jest_prt7_lengkap_kode_lama.log` (berkas lengkap: `mobileLayout` belum ada) →
`jest_prt7_hijau_kode_baru.log` (23/23).

`backend/tests_mem` seluruhnya: **364 lulus / 2 dilewati / 3 xfail → 368 lulus / 2 dilewati / 3 xfail**
(`bukti/PR-T7/tests_mem_sebelum.log`, `tests_mem_sesudah.log`) di salinan kerja. Sesudah digabung di atas PR-T4:
**396 → 400 lulus** / 2 / 3. Lapis A `backend/tests/test_bp_PRT7_layar_izin.py` (U3, U3b, U4): **3 lulus** di
lingkungan A (MongoDB 7 asli, backend `2d164c9`, data acuan).

## Penggabungan dengan PR-T4

PR-T4 (`6d7dacf`, `39cdd4b`) masuk lebih dulu. Konflik tiga arah (basis `3224848`) hanya di
`frontend/src/features/crm/SalesForceDashboard.jsx`: PR-T4 memasang `canPickSales = can(perms, "order",
"view_sales_kpi")`, PR-T7 mengganti `isManager` nama peran dengan `sales_force.view` dan menambah `canSetTarget`/`canPostGl`.
Keduanya dipertahankan. `config/roles.js` tergabung otomatis. Garis dasar `verify_role_gate_ui` dikencangkan dengan
`--update` karena PR-T4 sudah menghapus gerbang di 4 berkas (`CustomerFormModal`, `LogisticsView`,
`AccountLocationScope`, `WarehouseMasterView`): **29 → 25 gerbang, 23 → 19 berkas**. Jest sesudah digabung
(`src/config`, `src/features`, `src/hooks`, `src/components`): 460/460 uji lulus; 34 suite gagal dimuat karena
`@radix-ui/primitive/is-development` (kendala lingkungan). Hitungan penjaga statik berhitung sama dengan sebelum
penggabungan.

Jest seluruhnya (`bukti/PR-T7/jest_ringkasan_lengkap.log`): tanpa tiruan — lama 442 lulus (35 suite gagal dimuat:
`@radix-ui/primitive/is-development`, kendala lingkungan), baru 465 lulus (35 suite yang sama). Dengan tiruan pemilih
radix/cmdk disisipkan ke salinan suite di folder uji (pola PK-13/KP-T3): lama 691/691 (2 suite gagal dimuat: `knSelect`,
`TransferDetailModal`), baru **714/714** (2 suite yang sama).

## Penjaga statis (sebelum → sesudah)

| Penjaga | Sebelum | Sesudah |
|---|---|---|
| `verify_auth_coverage` | 28 (merah) | 28 (daftar sama) |
| `verify_access_catalog_nav` | 0 | 0 |
| `verify_money_idempotency` | hijau | hijau |
| `verify_custom_modals` | hijau (51) | hijau (51) |
| `verify_ui_standard` | 26 (merah) | 26 |
| `verify_error_notice` | hijau | hijau |
| `verify_knselect_contract` | 0 | 0 |
| `audit_i18n_id` | 113 | 113 |
| `verify_codebase_map` | hijau | hijau |
| `verify_role_label` + `--self-test` | hijau (6 id) | hijau (13 id) |
| `verify_role_gate_ui` + `--self-test` | — | hijau (29/23) |

Tambahan (lama vs baru, sama): `verify_view_aliases`, `verify_scope_guard`, `verify_escape_layers`, `verify_page_tabs` (1),
`verify_blocking_dialogs`, `verify_modal_dismiss`, `verify_derived_fields`, `verify_detail_modal`, `verify_entity_label` (2),
`verify_picker_portal`, `verify_desk_targets`, `verify_notification_audience` — `bukti/PR-T7/penjaga_*.log`.
ESLint berkas berubah: tidak ada `no-undef`/`react/jsx-no-undef`; pesan `no-unused-vars` sama dengan kode lama.

## Gate

Dijalankan di lingkungan A (MongoDB 7 asli + backend `2d164c9`), sesudah `restore_demo` (data acuan; tiga skrip seed
yang sama seperti garis dasar gagal: `seed_demo_transaksi_kn`, `seed_p03_kn`, `seed_p05_kn`):

| Gate | Hasil | Garis dasar | Lebih merah | Menjadi hijau |
|---|---|---|---|---|
| `gate.sh --quick` | 16 FAIL | 16 | 0 | 0 |
| `gate.sh --ci` | 43 FAIL | 43 | 0 | 0 |

Dua baris gate baru unit ini — `guard:role_gate_ui SELF-TEST` dan `guard:role_gate_ui (INV-ROLE-02)` — PASS di kedua mode.

## Menyimpang dari blueprint

1. **`view_actions` tidak ada** — `GET /api/auth/me` hanya membawa `view_resources` + `hidden_views`; field itu tidak
   didefinisikan di mana pun. Login membawa persis bentuk `/auth/me` (sesuai kolom "Dihitung dari"). U3 diuji tanpa
   `view_actions`; berkas unit dikoreksi (commit terpisah).
2. **`employee_id` dihitung server** — memakai `users.employee_id` apa adanya akan menyembunyikan Profil Saya bagi 14
   akun data acuan yang tertaut hanya dari sisi HR. Login & `/auth/me` kini mengisi `user.employee_id` dari
   `hr_employees.user_id` (sumber yang sama dengan `/hr/employees/me`) — tambahan field di jawaban yang sudah ada.
3. **Pasangan izin mengikuti kode HEAD** (ASUMSI unit): #1 Override = `rnd.override_fail` (bukan `rnd.manage`;
   `pic-decision` memeriksa `override_fail`), Batalkan sample = `rnd.manage` (endpoint `cancel`); #20 tab mode lama =
   `wms.update` (bukan `wms.create`; pemindaian `POST /inbound/tasks/*`); tab Profil SJ & Sample OCR = `goods_receipt.review`
   (izin ubah panel itu — hasil untuk peran bawaan sama dengan daftar lama; `view` akan menampilkan panel yang tombolnya
   ditolak); pintasan OCR = salah satu izin tab tujuan (bukan hanya `configure`, supaya Admin Gudang tidak kehilangan
   pintasannya).
4. **Garis dasar akhir lebih dari #10/#11/#16/#18/#22b/#25** (29 gerbang, 23 berkas, semua bercatatan `pemegang`):
   - KP-T4 (jenjang persetujuan per dokumen): `admin/po/POCompactPanel`, `PODetailPanel`, `purchasing/PurchaseApprovalView`
     (termasuk pembuat ≠ penyetuju), `VendorBillsView`, `LandedCostView`, `marketing/Campaigns`, `pettycash/CashAdvanceDetail`,
     `components/NotificationCenter` (setujui dari lonceng), `finance/amendments/AmendmentDetailPanel` (`amendment.approver_role`,
     baris 7 KP-T4).
   - PR-T6: `settings/entities/AccountFormDrawer` (#25), `AccountLocationScope` (teks bantuan formulir akun).
   - PR-T4 (dikerjakan pihak lain; arahan: cakupan data jangan disentuh): `crm/CustomerFormModal`, `crm/CustomerList`,
     `hr/VisitsView`, `logistics/LogisticsView`, `wms/warehouses/WarehouseMasterView`, `sales/mobile/MobileSalesHome`
     (cermin `role_in` cakupan data server) dan `sales/SalesPortal` (#19, sementara `roleIs` = `role_in` server).
   - H7 (RFID): `rfid/RfidDevicesView`, `RfidGateMonitorView`, `RfidTagsView` (alat khusus Admin; pengganti
     `rfid_device.configure` dll. setelah pemilik melepas H7), `wms/StockOpnameTab` (metode Sapu RFID, keputusan D-15).
   - `hr/AiIllustrationPanel.jsx` — berkas yatim (tidak diimpor, `phase4R4.test.js`); aturan servernya
     (`design_gallery_service.py:620`, `role != "admin"`) masih nama peran → PR-T6.
5. **Tata letak sebelum PR-T4**: #24 dan K-11 (Admin Sample tidak memutus SORD di HP) dibaca dari halaman awal peran
   (`sales-home`/`sales-admin-desk` → HP sales, `md-desk` → MD, `logistics` → pengemudi, `operations`/`warehouse-admin-desk`
   → gudang, `sample-admin-desk` → tanpa SORD) karena kategori kerja belum ada; hasil 13 peran bawaan identik (diuji).
6. **Uji lama disesuaikan fixture-nya** (harapan tidak diubah): 13 berkas uji memodelkan akun dengan peran saja atau
   bergantung pada `canCurrent` = "boleh" tanpa konteks. Fixture diberi izin bawaan peran itu (`trial22Okt`, `kft6JurnalDuaOrang`,
   `phase4R5`, `mobileShell`, `phase3P3`, `phase3P6Kpi`, `phase3P6Rnd`, `phase4R1`) atau konteks Admin yang sudah masuk
   (`pk16ScopeBanner`, `phase3P4Finance`, `phase3P8Activation`, `prepBInitialRegistration`, `prepD1GateV2` — yang terakhir
   uji panel RFID: hanya penyiapan uji, logika RFID tidak disentuh).
7. Tambahan di luar tabel spesifikasi: tombol "Ajukan" permintaan desain kini juga `design_request.create` (dulu tanpa
   gerbang); "Realisasi pengadaan" OD tidak lagi khusus Manajer/Admin bila ada catatan pengadaan (aturan itu tidak ada di
   server); `IncentiveSchemeEditor` berpesan tolak bentuk Z6.

## Asumsi / keraguan

- `ASUMSI` unit dipakai: akun tak tertaut tidak punya karyawan di `hr_employees` (dibuktikan U3b).
- Perubahan tombol peran bawaan (dihitung dari izin bawaan): **hilang** hanya MD "Batalkan" permintaan desain (server
  403). **Baru tampil** (server memang mengizinkan): Admin Gudang Kirim/ronde sample & Buat/Rilis/Selesai WO; MD master
  kategori desain, penilai desain, pintasan SLA/bobot KPI; Finance, Admin Sales, Admin Gudang tanda tangan elektronik;
  Finance & Admin Sales usul amandemen.
- Item server yang laporan PR-T2 serahkan ke PR-T7 — `location_scope.is_supervisor` (`role_in` cakupan lokasi) dan
  `internal_requests.py:43` (`role_in(…, CROSS_ENTITY_ROLES)`) — tidak dikerjakan: keduanya cakupan data (Z5, PR-T4) dan
  tidak ada di spesifikasi PR-T7.
- `canCurrent` "tidak" tanpa konteks: aplikasi selalu memasang konteks dari objek akun (`App.js`); sesi tersimpan
  sebelum perubahan ini tetap punya `permissions` sehingga izin terbaca walau `view_resources` belum ada.

## Hambatan lingkungan

- Tanpa peramban: U10–U15 (uji jalan layar) belum dijalankan. Lapis A HTTP dan gate dijalankan saat penggabungan.
- Jest lokal: 35 suite gagal dimuat (`@radix-ui/primitive/is-development`) di kode lama maupun baru; dengan tiruan
  pemilih di salinan suite (folder uji, bukan repo) semua kecuali `knSelect` & `TransferDetailModal` termuat.

## Yang perlu direview

- Daftar sisa garis dasar dan pemegangnya (Menyimpang 4), terutama klasifikasi "cakupan data → PR-T4" dan H7.
- Tambahan field `employee_id` pada login & `/auth/me` (Menyimpang 2).
- Penyesuaian fixture 13 uji lama (Menyimpang 6).

Status: implemented_pending_review.
