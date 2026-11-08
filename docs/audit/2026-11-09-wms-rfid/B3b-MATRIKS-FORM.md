# B3b — Lampiran A: Matriks Form WMS-RFID

Paket **B3b** (audit form, input/output, pemilih vs isian bebas, fitur daftar) · 9 Nov 2026 · HEAD audit `5f1e36e`
(cabang worktree di-*merge* dari `main`; sensus otomatis dijalankan di `70eb9fd` — berkas yang berubah sesudahnya,
yaitu `GateReviewQueue/GateReviewDetail.jsx` (D2) dan `LoadingCheckPanel.jsx`, dibaca manual).
Laporan utama: [`B3b-FORM-INPUT-DAFTAR.md`](B3b-FORM-INPUT-DAFTAR.md). Matriks daftar: [`B3b-MATRIKS-DAFTAR.md`](B3b-MATRIKS-DAFTAR.md).

Singkatan: **P** = pemilih terikat id (`KNSelect`, `ProductSelect`, `LocationFields`, `SiteSelect`, `RollPicker`,
`QcRequestPicker`, tanggal), **TB** = isian teks bebas yang **mengisi field rujukan master/dokumen**.
**DICT** = body `dict`/`_payload(request)` tanpa model Pydantic. **Q** = parameter dikirim lewat query string.
Kolom "dibuang/hilang" = kunci yang dikirim layar tapi tidak ada di skema (dibuang diam-diam — Pydantic v2 bawaan
`extra="ignore"`, **tidak satu pun model men-set `extra="forbid"`**) / field skema yang tidak punya isian di layar.
Rujukan temuan (FRM/INP/LST/EXP) ada di laporan utama.

## A.1 Sensus otomatis per berkas (ringkas)

Sumber: `scripts/audit/b3b_fe_census.js` (parser Babel, 478 berkas terjangkau dari 38 layar akar) →
`scripts/audit/b3b_form_census.py` (180 berkas cakupan yang memuat kontrol/tombol).

| Ukuran | Jumlah |
|---|---|
| Berkas cakupan berisi kontrol/tombol | 180 |
| Kontrol isian (input/select/pemilih) | 658 |
| — pemilih terikat id | 239 |
| — isian teks/angka (`input`/`textarea`/`DecimalInput`) | 364 |
| `<input type="number">` | 87, **50 tanpa `min`** |
| `DecimalInput` (desimal koma ID) | 7 |
| `<label>`/`<Label>` | 284 (≈ 0,43 per kontrol) |
| Atribut `required` | **1** |
| Atribut `maxLength` | **3** |
| Tanda wajib `*` (label + placeholder) | 44 (6 di placeholder) |
| Pembungkus | FormModal 43 · DetailModal 10 · ConfirmModal 7 · sisanya inline/kartu/drawer buatan sendiri |
| `FormSection` (bagian bernomor baku) | **0** di cakupan WMS-RFID |

Keluarga kelas tombol (668 tombol): `secondary-button` 171 · **Tailwind `bg-[#hex]`/`border-[#hex]` buatan sendiri 162** ·
`primary-button` 148 · kelas lain 124 · `btn-*` 29 · tanpa kelas 27 · ikon/ghost 24 · `danger-button` 9.
Keluarga kelas isian: `.field` 191 · tanpa kelas 57 · Tailwind mentah (`rounded-lg border p-2`) 55 · `.form-input` 31 · `.input` 7.

## A.2 Panggilan tulis FE → endpoint → skema (otomatis + verifikasi manual)

Sumber: `scripts/audit/b3b_crossref.py` (OpenAPI backend yang berjalan + AST router). **259 panggilan tulis** di
berkas cakupan → **291 endpoint tulis** di 39 router cakupan. 11 endpoint ber-body `dict` bebas, 13 endpoint V2
mem-parse body manual (`await _payload(request)`), ±9 endpoint tulis menerima nilai lewat **query string**
(`scan-pick`, `dispatch`, `escalate`, `resolve-escalation`, `dispatch-batch`, `loading-check/start`, …).

Kunci yang **dibuang skema** (terverifikasi manual): `assigned_to` di `POST /inspections/random-check`
(RandomCheckModal.jsx:29 → `RandomCheckCreate`, schemas_inspection.py:78-84); `country`/`country_code` di
`POST /warehouse-sites` (WarehouseMasterView.jsx:199 → `SitePayload`, warehouse_sites.py:15-23); `kunci_asing`
(uji umum, lihat laporan). Penanda DROP otomatis pada 5 endpoint `rfid_v2*` adalah positif palsu (dibaca manual
dari `_payload`). Penanda MISS `file`/`items`/`plate` adalah positif palsu (FormData / variabel).

## A.3 Penerimaan barang & QC

| # | Form | berkas:baris | Pembungkus | #isian | P / TB | Endpoint → model | Dibuang / hilang | Catatan (temuan) |
|---|---|---|---|---|---|---|---|---|
| 1 | Wizard Kedatangan | wms/grn/GrnCreateWizard.jsx:16-159 | FormModal + footer sendiri | 5 | 4 / 0 | POST /goods-receipts → GRNCreateIn (schemas_goods_receipt.py:9); /files; /read | – | tanpa `*`; unggah gagal → draf ganda (FRM-15) |
| 2 | Kepala SJ | grn/GrnReviewPanel.jsx:25-55 | kartu inline | 6 | 1 / 0 | PATCH /dn → GRNDnPatch (:26) | other_refs, date_text (khusus OCR) | teks tanpa max_length, `date` tanpa format (INP-11) |
| 3 | Tambah baris SJ | GrnReviewPanel.jsx:57-106 | inline | 13 | 4 / **1 (Satuan)** | POST /lines → GRNLineIn (:55) | – | number tanpa `min`; 422 tertelan (FRM-16); satuan teks (INP-04) |
| 4 | Ubah baris SJ (desktop & HP) | GrnLineRow.jsx:90-131 · GrnLineCard.jsx | inline, placeholder saja | 12 | 1 / **2 (Satuan, Satuan PL)** | PATCH /lines/{n} → GRNLinePatch (:74) | Bruto/Netto tak bisa diubah | HP kurang isian (FRM-04) |
| 5 | Simpan ke katalog supplier | GrnLineRow.jsx:60-87 | baris inline | 2 | 0 / 0 | POST save-catalog → GRNCatalogIn | – | hanya desktop |
| 6 | Hitung roll / scan | GrnCountPanel.jsx:11-95 | inline | 7 | 3 / 0 | POST /lines/{n}/rolls → GRNCountRollIn; /scan-label → GRNScanIn | `manual` (label tak terbaca) tidak ditawarkan | – |
| 7 | Selisih / Tolak / Batal GRN | GrnReconPanel.jsx:33-55 · GrnReviewPanel.jsx:119 · GrnDetail.jsx:35 | askReason | 1 | – | GRNResolveIn / GRNReasonIn (`min_length=5` tanpa strip) | – | 5 spasi lolos (FRM-09) |
| 8 | Mode penerimaan | GrnModePanel.jsx:27-45 | askReason | 1 | – | PUT /goods-receipts/mode → GRNModeIn | – | baik |
| 9 | Profil SJ | GrnProfilesPanel.jsx | kartu inline | 4 | 1 / 0 | PATCH dn-profiles → GRNProfilePatch | – | "Lupakan" tanpa konfirmasi (FRM-14) |
| 10 | Kunci jawaban sampel OCR | GrnOcrSampleEditor.jsx:19-64 | FormModal baku | 3 + 6/baris | 2 (satuan dari master) / 0 | PATCH /ocr-samples/{id} → SamplePatchIn (dict dibersihkan) | – | pembanding baik untuk INP-04 |
| 11 | Scan Terima per PO (mode lama) | wms/InboundScanForm.jsx:11-72 + ReceiveUomPanel.jsx | inline Tailwind mentah | 8 | 2 / **3 (bin_id, roll_id, lot)** | POST /inbound/tasks/{id}/scan-receive → POReceiveItem (schemas_purchasing.py:505) | – | "Bin Location *" tidak wajib di mana pun (INP-01) |
| 12 | Eskalasi inbound | InboundScanInterface.jsx:425-432 | FormModal sm | 1 | – | POST /escalate **Q** `reason` | – | tanpa min (FRM-09) |
| 13 | Selesaikan GR (catch-weight) | inbound/GRCatchWeightModal.jsx | FormModal, kaki [Selesaikan][Batal] | 4 + 4/roll | 1 / **1 (lot tempel)** | POST /complete → GRCompletePayload / GRRollLine | rolls[].defects tak di layar | "Tempel ke lot" tak berfungsi (INP-16) |
| 14 | Label tak terbaca | inbound/UnreadableLabelModal.jsx | FormModal baku | 8 | 3 / 0 | scan-label manual → ManualLabelIn | – | baik |
| 15 | Ukur / bin / tag RFID per roll | inbound/ScannedRollRow.jsx | inline warna kustom | 5 + alasan | 2 (grade, bin datalist + `resolve_bin`) / 0 | ConfirmMeasureIn / PutawayIn / TagRfidIn | defects tak di layar | grade nonaktif ikut tampil (FRM-18) |
| 16 | Keputusan QC kedatangan | wms/QCInspection.jsx:250-357 | FormModal [Batal][Simpan] | 6 + rencana | 2 / **1 (defects dipisah koma)** | POST qc-decision → QCDecision (schemas_purchasing.py:577) | – | tolak tanpa alasan (FRM-09); detail 422 → crash (FRM-16) |
| 17 | Rencana QC | QcPlanPanel.jsx | inline `.form-input` | 3 | – | PUT /inbound/qc/tasks/{id}/plan → **DICT** (qc_inspection.py:57; service cek 1–100) | – | "Tidak wajib" tanpa alasan (FRM-09) |
| 18 | Override grade roll | RollGradePanel.jsx:183-202 | FormModal + baris | 2 | 1 / 0 | POST grade-override → RollGradeOverrideIn (schemas.py:696) | – | alasan 1 huruf (FRM-09) |
| 19 | Inspeksi 4-point per roll | RollInspectionModal.jsx | FormModal tanpa kaki | 11 | 1 (grade dari `/master/grades`) / 0 | POST /inbound/rolls/{id}/inspect → RollInspectionInput | kode/interval cacat tak di layar ini | grade kosong bagi peran gudang (FRM-18) |
| 20 | Buat SPK | inspections/InspectionFormModal.jsx | FormModal baku | 5 | 3 / 0 | POST /inspections → InspectionCreate | spk_date, bagian, line_code diturunkan server | baik |
| 21 | Isi hasil baris SPK | InspectLineModal.jsx | FormModal baku | ±16 | 4 / 0 | POST …/inspect → InspectionLineInspect (:38) | yard_split, repair_note di layar lain | angka tanpa batas (INP-09) |
| 22 | Lembar inspect (grid) | InspectSheetGrid.jsx | tabel inline | 9 + sel | 1 / kode cacat bebas (keputusan F5) | idem | – | `Number("120,5")` → NaN → 0 (INP-10) |
| 23 | Random check | RandomCheckModal.jsx | FormModal baku | 5 | 2 / 0 | POST random-check → RandomCheckCreate (:78) | **`assigned_to` DIBUANG** | FRM-05 |
| 24 | Tugaskan / Tutup SPK | InspectionDetailPanel.jsx:322-420 | inline | 2 + 3 | 3 / **1 (bagian)** | InspectionAssign / InspectionFinish | spk_date tidak dikirim | tolak/buka ulang min 15 huruf (konsisten) |
| 25 | Potong uji MDQ | MdqCutBox.jsx | inline | 2 | – | POST mdq-cut → MdqCutIn (model di router) | reason tak di layar | service cek 0–5 yard |
| 26 | Master grade | settings/masters/GradeMasterView.jsx | tabel inline `.input` | 4 (+3) | – | GradeIn / GradePatch / GradeActiveIn (grade_master.py:13-31) | `description` tak di layar | `max_points` tanpa batas (INP-09) |
| 27 | Keputusan selisih PO | admin/po/POVarianceTasksPanel.jsx | inline | 1 (dipakai bersama semua baris) | – | **DICT** → service min 5 | – | satu state alasan untuk semua tugas |
| 28 | Tutup PO kurang terima | admin/PurchaseOrderManagement.jsx:277-292 | ConfirmModal withReason (min 0) | 1 | – | POST /close → POCloseRequest (`reason=""`) | – | FRM-09 |

## A.4 Putaway · lokasi & data gudang · transfer · opname · pendaftaran awal · stok awal · perbaikan · lot

| # | Form | berkas:baris | Pembungkus | #isian | P / TB | Endpoint → model | Dibuang / hilang | Catatan (temuan) |
|---|---|---|---|---|---|---|---|---|
| 29 | Verifikasi label QR (PA) | wms/PutawayOrdersPanel.jsx:148-151 | seksi inline | 1 | 0 / 0 | POST /putaway-orders/verify-labels → PAVerifyLabelsPayload (putaway_orders.py:44) | – | `codes` tanpa batas jumlah |
| 30 | Buat PA per kelompok | PutawayOrdersPanel.jsx:183-194 | inline | 1 | 1 / 0 | POST /putaway-orders → PACreatePayload | – | tombol kustom |
| 31 | Konfirmasi tiba / trip | PutawayOrdersPanel.jsx:238-270 | kotak inline | 1 + 4 tombol | 0 / 0 | confirm-arrival PAConfirmPayload; arrival-trips PATripPayload | – | **"Simulasi Scan Semua"** (FRM-10); "Validasi & tutup" kosong (FRM-14) |
| 32 | Tutup sisa PA | PutawayOrdersPanel.jsx:113-125 | askReason(10) | 1 | – | close PAClosePayload | – | server min 10 ✓ |
| 33 | Resolve exception PA | PutawayOrdersPanel.jsx:127-134 | tombol baris | 0 | – | resolve-exception PAResolvePayload | `reason` tidak dikirim | accept tanpa alasan (FRM-09) |
| 34 | Draf PA | wms/PutawayDraftsPanel.jsx:108-145 | expand + askConfirm/askReason(5) | 1 | 1 / 0 | PATCH …/draft; cancel-draft (min 5 ✓) | `purpose` tak di layar | – |
| 35 | Penempatan rak per roll | wms/location/PutawayRow.jsx:54-85 | inline | 2 | 1 / 0 | POST /inventory/putaway → PutawayPayload | – | override min 5 ✓ |
| 36 | Koreksi alamat yatim | location/OrphanPanel.jsx:43-49 | inline | 2 | 1 / 0 | POST …/fix-location → FixLocationPayload | – | `bin_id` mentah tampil (INP-19) |
| 37 | Struktur lokasi + aturan node | location/StructureEditor.jsx:195-295 · NodeRulesEditor.jsx:34-68 | pohon inline | nama, kode bin, kapasitas, aturan | 5 / **1 (kategori dipisah koma)** | PUT /warehouses/{id}/structure → StructurePayload (`zones: List[Dict]`) | – | hapus node tanpa konfirmasi; kapasitas 0 = tanpa batas (INP-08) |
| 38 | Gudang baru | warehouses/WarehouseCreateModal.jsx:19-87 | FormModal lg | 12 | 5 / 0 | POST /warehouses → WarehousePayload (schemas.py:331) | `bin_capacity` disimpan sbg `capacity` (FRM-07); `site_id` tak ada | lat/lng tanpa batas |
| 39 | Lokasi (site) baru | WarehouseMasterView.jsx:447-459 | FormModal sm | 6 | 5 / 0 | POST /warehouse-sites → SitePayload | **country/country_code dibuang** (FRM-06) | regex nama tanpa escape (INP-12) |
| 40 | Profil gedung + gate | WarehouseProfileDrawer.jsx:80-205 · WarehouseGateSection.jsx:27-66 | FormModal md, tombol "Tutup" | ±13 + 5/pasangan | semua pemilih; jenis kain hard-code | PATCH /warehouses → **GenericPatch {data: dict}** | – | label PT jatuh ke id (INP-19); nama pasangan dipotong 80 huruf diam |
| 41 | Mode pemakaian | WarehouseModeDrawer.jsx:63-90 | FormModal md | 2 | pemilih | GenericPatch | – | baik |
| 42 | Kebijakan cek muat (di tabel) | WarehouseMasterView.jsx:373-379 | KNSelect inline | 1 | 1 / 0 | GenericPatch | – | tanpa konfirmasi |
| 43 | Transfer baru | TransferManagement.jsx:303-335 + transfer/TransferCreateForm.jsx | FormModal lg | 6 | 5 / 0 | POST /transfers → TransferCreate (schemas.py:639) | `requested_by` dari klien disimpan (FRM-08) | RollPicker `entityId="all"` → roll PT lain → 409 |
| 44 | Setujui / Tolak / Batal transfer | TransferManagement.jsx:169-255 | askConfirm / askReason(5) | 1 | – | TransferApprove/Reject/StatusUpdate; DELETE **Q** reason | approved_by / rejected_by dari klien | server tanpa min (FRM-09) |
| 45 | Terima transfer per roll | transfer/TransferReceiptPanel.jsx:87-109 · ReceiptRollTable.jsx | inline | 6 | 2 / 0 | POST …/receive → TransferReceiveIn | `evidence` tak di layar | server min 5 ✓ |
| 46 | Exception transfer | transfer/ReceiptExceptions.jsx:140-189 | inline + askReason | 2 | 1 / 0 | TransferExceptionIn / ResolveIn | `code`, `evidence` tak di layar | tanggal UTC mentah |
| 47 | Sesi opname baru | inventory/CycleCount.jsx:433-449 | FormModal | 3 | 1 / 0 | POST /cycle-count/sessions → CycleCountSessionCreate | – | tanpa label (placeholder) |
| 48 | Tambah item opname | CycleCount.jsx:271-288 | inline | 2 | 1 / **1 (Bin ID)** | POST …/items → CycleCountItemCreate | owner tak di layar | **INP-02** |
| 49 | Qty aktual | CycleCount.jsx:320-330 | inline per baris | 1 | – | PATCH …/items/{id} → CycleCountItemUpdate (`Any`) | `notes` selalu "" | – |
| 50 | Setujui / Tolak opname | CycleCount.jsx:392-409 | input inline | 3 | – | CycleCountApprove (alasan bawaan) / Reject | – | FRM-09 |
| 51 | Opname per roll | inventory/RollCountPanel.jsx:77-105 + UnknownRollForm.jsx | inline | 5 + 3/kode + 2 | 6 / 0 | roll-scope / scans / finalize | `note` scan & recount tak dikirim | finalize min 5 ✓ |
| 52 | Sesi pendaftaran awal | registration/InitialRegistration.jsx:105-136 | FormModal | 6 | 4 / 0 | POST /registration/sessions → RegSessionCreate | – | placeholder sbg label |
| 53 | Persetujuan & pemetaan pendaftaran | registration/RegistrationDetail.jsx:41-74, 171 | askConfirm/askReason + ProductSelect | – | ✓ | RegApproveIn / RegReason / RegLineIn | – | **`g.owner_entity_id` mentah (:146) — guardrail INV-UI-02 MERAH di HEAD** |
| 54 | Daftar awal (HP) | mobile/MobileRegistration.jsx:145-197 | halaman HP | 14 | 5 / **1 (grade)** | POST …/lines → RegLineIn | `label_raw`, `owner_entity_id` tak dikirim | desktop tak bisa tambah/ubah baris (FRM-04) |
| 55 | Stok awal | InventoryStockView.jsx:432-458 + inventory/InitialStockForm.jsx | FormModal lg | 11 | 4 (grade hard-code) / 0 | POST /inventory/initial-stock → RollPayload (schemas.py:707) | bin_id, tracking_mode, ownership_type tak di layar | unit/grade/bin tak divalidasi (INP-05) |
| 56 | Tahan / lepas roll | inventory/RollHoldControl.jsx:43-56 | FormModal sm | 1 | – | qc_inspection.py:121/136 (**DICT**) | – | min 5 ✓ |
| 57 | Perbaikan baru | repair/RepairCreateModal.jsx:59-120 | FormModal lg | 12 | 5 / **1 (warna tujuan)** | POST /repair-orders → RepairCreate (repair_orders.py:44) | `cost.contract_id` tak di layar | SKU tujuan = pencarian ketik buatan sendiri (INP-08) |
| 58 | Terima hasil perbaikan | repair/RepairOrderDetail.jsx:~70-105 | inline tabel | 3/roll + biaya | grade pemilih; dye lot teks (lot baru) | RepairReceive | – | baik |
| 59 | Aksi lot (6 modal) | inventory/lots/LotActionModals.jsx | FormModal md | – | pemilih ✓ | lots.py / schemas_lots.py | `shade_ref` di state tanpa isian (:296) | alasan tak wajib (FRM-09) |

## A.5 Ambil (picking) · potong · pengiriman & cek muat · retur terima · makloon · eskalasi

| # | Form | berkas:baris | Pembungkus | #isian | P / TB | Endpoint → model | Dibuang / hilang | Catatan (temuan) |
|---|---|---|---|---|---|---|---|---|
| 60 | Ambil (scan-pick) desktop | wms/OutboundScanInterface.jsx:446-482 | inline | 1 kode roll | 1 / 0 | POST …/scan-pick **Q** (actual_qty, batch, lot, roll_id, bin_id) | – | server terima pick tanpa roll (FRM-03) |
| 61 | Kirim / sebagian / 1 SJ | OutboundScanInterface.jsx:515-545 | inline | 1 | – | /dispatch **Q** ship_qty; /dispatch-batch | – | ship_qty ≤0 = kirim semua; NaN (INP-09) |
| 62 | Eskalasi outbound | OutboundScanInterface.jsx:594-600 | FormModal sm | 1 | – | /escalate **Q** reason | – | alasan bawaan "Stock fisik…" |
| 63 | Pemeriksaan muat akhir | wms/LoadingCheckPanel.jsx:119-170 | inline (placeholder) | 4 | 0 / 0 | start (Q), scan, scan-label, override (**DICT**, outbound_picking.py:555-591) | – | `source` diisi klien (FRM-11); D2: info "gedung bergate" |
| 64 | Potong sample manual | wms/SampleCutPanel.jsx:218-238 | inline | 3 | 1 / 0 | POST …/cut-sample → SampleCutIn (sample_sales.py:24) | – | panjang tanpa batas atas (INP-09) |
| 65 | Potong semua paket | wms/CuttingOpsView.jsx:77-86 | tombol | 0 | – | /outbound/so/{id}/cut-samples → OrderCutIn | – | – |
| 66 | Konfirmasi potong SO | wms/PendingCutsPanel.jsx:90-110 | inline + askConfirm | 2 | 0 / 0 | …/reservations/{id}/cut → CutConfirmPayload (routers/inventory.py:549) | `note` tak di layar | susut tanpa batas & alasan (INP-09) |
| 67 | Verifikasi label roll anak | PendingCutsPanel.jsx:121-135 | inline | 1 | – | /verify-identity → LabelVerifyPayload | – | baik |
| 68 | Terima hasil potong | samples/CuttingDesk.jsx:99-108 | inline | 1 | 1 / 0 | /cutting/tasks\|orders/{id}/receive → ReceiveIn | – | baik |
| 69 | Kemampuan lokasi cutting | samples/CuttingLocations.jsx:185-190 | tabel centang langsung simpan | 3/lokasi | 3 / 0 | PUT /cutting/locations/{wid} → CapsIn | – | tanpa konfirmasi |
| 70 | Pesanan sample (bayar/teruskan/batal) | samples/SampleOrdersView.jsx:222-235 | tombol | 0 | – | approve-payment / confirm / cancel → NoteIn | catatan tak bisa diisi; alasan batal teks tetap | FRM-09 |
| 71 | Buat pengiriman | logistics/DeliveryCreateModal.jsx:85-165 | FormModal lg | 13 | 5 / **4 (kurir, plat manual, sopir manual, tujuan)** | POST /logistics/deliveries → DeliveryCreateIn (schemas_logistics.py:7) | – | plat manual melewati cek armada (INP-06) |
| 72 | Ubah data pengiriman | logistics/DeliveryDetailModal.jsx:189-207 | DetailModal, edit inline | 9 | 1 / **5** | PATCH /logistics/deliveries/{id} → DeliveryUpdateIn | vehicle_id/driver_user_id tak ikut berubah | desync id (INP-06) |
| 73 | Tahap pengiriman | DeliveryDetailModal.jsx:135-156 | tombol + askConfirm/askReason | 1 | – | /transition → TransitionIn | received_at & note tak di layar | alasan ≥5 di server ✓ |
| 74 | Catat posisi | DeliveryDetailModal.jsx:168-176 | inline | 3 | 0 / 1 (lokasi teks — wajar) | /positions → PositionIn (lat/lng berbatas) | – | baik |
| 75 | Serah terima ambil sendiri | logistics/PickupHandoverPanel.jsx:44-55 | inline | 4 | – (orang luar, wajar teks) | /pickup-handover → PickupHandoverIn (kode 4-12, nama 2-120) | – | note tanpa batas |
| 76 | Kendaraan armada | logistics/FleetPanel.jsx:134-143 | inline | 6 | 2 / 0 | POST/PATCH /fleet/vehicles → VehicleIn | – | catatan status min 5 hanya di FE |
| 77 | Perencana trip | logistics/TripPlannerPanel.jsx:66-78 | centang | n | n / 0 | /trip/picking-list, /trip/check → TripOrdersIn | – | – |
| 78 | Pengembalian barang retur | sales/ReturnShipmentPanel.jsx:91-134 | inline | 7 | 2 / **3 (ekspedisi, sopir, kendaraan)** | PUT /sales-returns/{id}/return-shipment → ReturnShipmentIn | shipped_at tak di layar | dipotong diam 120/60/40 huruf (return_service.py:703-714) |
| 79 | Tandai barang sampai | ReturnShipmentPanel.jsx:157-160 | tombol | 0 | – | /milestone → ReturnMilestoneInput (izin `sales_return.update`) | at & note | tombol tampil bagi gudang tapi ditolak server (FRM-22) |
| 80 | Scan perjalanan retur | sales/ReturnTimelinePanel.jsx:58-80 | inline | 5 | 3 / **1 (carrier)** | /journey/scan → JourneyScanPayload | note tak di layar | baik selain carrier |
| 81 | Karantina: release / scrap / regrade | sales/ReturnQuarantinePanel.jsx:111-121, 316-367 | tabel inline | 2/roll | 1 / 0 | /quarantine/release → QuarantineReleaseInput | `notes` selalu "" | scrap = write-off GL tanpa konfirmasi (FRM-14) |
| 82 | Transfer kepemilikan / teruskan ke supplier / batal write-off | ReturnQuarantinePanel.jsx:182-257 | FormModal sm ×3 | 1 / 1 / 1 | entitas, supplier / 0 | transfer-ownership; create-purchase-return; reverse-writeoff (reason Optional) | roll_ids, reason, gudang tak di layar | FRM-09 |
| 83 | Keputusan per roll / SPK / disposisi | ReturnRollsPanel.jsx:62 · ReturnSpkPanel.jsx:91 · ReturnDispositionPanel.jsx:50-110 | inline | 2 / 1 / 2 | terikat | roll-decisions / assign / disposition | – | min 5 di server ✓; "Buang BS" tanpa konfirmasi |
| 84 | Tolak / pembalikan retur jual | sales/ReturnDetail.jsx:398-424 | ConfirmModal | 1 | – | /reject, /reverse → SalesReturnDecision.notes | – | FE ≥5, server tanpa min (FRM-09) |
| 85 | RMA retur beli (kirim, terima, tolak, kembali) | purchasing/ReturnDetailPanel.jsx:234-345 · PurchaseReturns.jsx:572 | inline | ±5 | 2 / 0 | ship-to-supplier → SupplierShipInput (schemas_purchasing.py:465) | **carrier, tracking_no, notes tanpa isian (body `{}`)** | FRM-06 |
| 86 | Tolak retur beli | PurchaseReturns.jsx:581-592 | ConfirmModal (min 0) | 1 | – | /reject → PurchaseReturnDecision | – | FRM-09 |
| 87 | Retur antar-PT | finance/interco/IntercoReturnModal.jsx | FormModal lg | qty/roll, klaim, alasan | roll terikat | /interco/returns → IntercoReturnCreate (gt=0, alasan ≥5) | doc_date, source_sales_return_id | baik |
| 88 | Issue bahan makloon | purchasing/makloon/MkoStepModals.jsx:61-110 | FormModal | 5 | 4 (satuan dari master) / 0 | /issue → MakloonIssueIn | roll_codes tak dipakai | `doc_qty` `<input>` + `parseFloat` (INP-10) |
| 89 | Terima hasil makloon | MkoStepModals.jsx:116-232 | FormModal md | 11 + 4/roll | 3 / 0 | /receive → MakloonReceiveIn (schemas_makloon.py:167) | **supplier_dn & weight_kg tanpa isian** | LOT terisi otomatis padahal "WAJIB manual" (FRM-06) |
| 90 | Catat jasa | MkoStepModals.jsx:244-314 | FormModal md | 7 | 0 / 0 | /record-service → MakloonServiceIn | roll_count tak di layar | – |
| 91 | Retur/susut bahan MKO batal + toleransi | makloon/MakloonReturnMaterial.jsx:86-123 | inline | 4 | centang / 0 | return-material, material-loss (≥5), tolerance (0-100, ≥5) | – | alasan toleransi diisi otomatis |
| 92 | Putuskan susut / batal kiriman sebagian | MakloonLossList.jsx:51-62 · MakloonPartialReceipts.jsx | inline | 3 / 1 | 2 / 0 | LossDecisionIn / PartialCancelIn (≥5) | – | baik |
| 93 | Batalkan MKO | MakloonOrderDetailPanel.jsx:396 | ConfirmModal (min 1) | 1 | – | /cancel → MakloonOrderCancel.reason | – | FRM-09 |
| 94 | Selesaikan eskalasi (manajer) | manager/EscalationManagement.jsx:267-354 | FormModal md **tanpa `busy`** | 2 | – | /outbound\|inbound/tasks/{id}/resolve-escalation **Q** | – | qty inbound tanpa validasi (INP-09) |
| 95 | Ambil alih tugas | wms/TaskTakeoverButton.jsx | inline | 1 | – | /wms/tasks/{id}/takeover (**DICT**, ≥5) | – | **tidak terjangkau UI** (ScannerTaskPanel tak diimpor) |

## A.6 RFID · antrean periksa gate (D2) · perangkat · pengaturan gudang & mutu

| # | Form | berkas:baris | Pembungkus | #isian | P / TB | Endpoint → model | Dibuang / hilang | Catatan (temuan) |
|---|---|---|---|---|---|---|---|---|
| 96 | Perangkat baru | rfid/RfidDevicesView.jsx:185-210 | FormModal | 6 | 4 / **1 (lokasi = teks nama zona/dock)** | POST /rfid/devices → DevicePayload (rfid.py:33) | `status` tak dikirim → "online" + heartbeat palsu | arah/status tanpa enum; **tak ada form Ubah** (INP-07, FRM-12) |
| 97 | Aksi kartu perangkat | RfidDevicesView.jsx:99-121, 241-260 | tombol + askConfirm | 0 | – | PATCH DevicePatch / DELETE / POST api-key | – | "Nyalakan" = heartbeat palsu; hapus tanpa cek rujukan/alasan |
| 98 | Encode / encode otomatis / pensiun tag | rfid/RfidTagsView.jsx:57-87 | tombol + askConfirm | 0 | – | EncodePayload / AutoEncodePayload / DELETE | – | pensiun tanpa alasan |
| 99 | Buat print job | rfid/RfidPrintVerifyPanel.jsx:53-61, 157-182 | kartu + centang | pilih roll | id / 0 | POST /rfid/print-jobs → PrintJobPayload (rfid.py:61) | `kind` tak dikirim | `kind` tak divalidasi (INP-17) |
| 100 | Sesi verifikasi cetak | RfidPrintVerifyPanel.jsx:279-302 | inline di DetailModal | 1 textarea | – | VerifyScanPayload → `epc.normalize_reads` | – | hasil = EPC mentah |
| 101 | Routing SIMPAN/CROSS-DOCK | RfidPrintVerifyPanel.jsx:117-125 | tombol | 0 | – | RoutingPayload (enum ✓) | – | tanpa konfirmasi/alasan |
| 102 | Simulasi gate | rfid/RfidGateMonitorView.jsx:185-200 | kartu | 2 | 2 / 0 | GateSimPayload | – | baik |
| 103 | Akui alarm (kiosk lama) | rfid/GateLiveVerdict.jsx:99-105 | input mentah | 1 | – | POST /rfid/passages/{id}/acknowledge (**DICT**, ≥5) | – | tanpa batas panjang/label |
| 104 | Tindak insiden | rfid/RfidSecurityPanel.jsx:98-110 | inline | 1 (opsional) | – | IncidentNotePayload `note=""` | – | **catatan boleh kosong** (FRM-09) |
| 105 | Pindai area (simulasi) | rfid/RfidLocationsView.jsx:102-110 | kartu | 1 | 1 / 0 | ReaderScanPayload → `reader_scan` | – | menulis bacaan nyata (FRM-13) |
| 106 | Opname RFID kilat | rfid/CycleCountPanel.jsx:48-76 | kartu | 1 textarea | gudang dari header | CycleCountStartPayload / VerifyScanPayload | – | galat ditelan |
| 107 | U300: unggah profil | rfid/U300Operations.jsx:115-125 | input file | JSON | – | PUT v2/ops/devices/{id}/config (`_payload`) → rfid_v2_core.py:87 | – | arah profil ≠ arah perangkat tak dicek; → AUD-MW-10 |
| 108 | U300: buka kunci / catat periksa | U300Operations.jsx:18-39 · U300PassageList.jsx:68-76 | inline | 1 | – | `_payload` → rfid_v2_latch.py `_note` (≥5, ≤1000) | – | D2: butuh `wms.approve` ✓ |
| 109 | U300: pilih dokumen gate | rfid/U300DocSession.jsx:99-114 | KNSelect + centang | 1 + daftar | id / 0 | POST manifest (validasi sumber ✓) | – | pilihan ke-21 dibuang diam |
| 110 | U300: tutup sesi dokumen | U300DocSession.jsx:75-85 | askConfirm | 0 | – | rfid_v2_ops.py:71 → `gate_txn.close_document_session` | `note` **teks tetap** | FRM-09 |
| 111 | U300: simulator | U300Operations.jsx:179-186 | kartu | 1 | 1 / 0 | rfid_v2_ops.py:133 | – | `int(roll_limit)` → 500 bila bukan angka (INP-13) |
| 112 | **D2 Antrean periksa gate — tindakan** (terima / tolak / abaikan / pindai ulang / tutup kasus / akui kunci) | rfid/GateReviewDetail.jsx:20-37, 173-184 | **FormModal sm baku** (satu modal untuk 6 aksi) | 1 textarea | centang roll (≤500) | POST /rfid/v2/ops/reviews/{id}/rolls/accept\|reject\|rescan, /dismiss, /acknowledge-latch (rfid_v2_review.py:89-153, `_payload`) → gate_review_actions.py:31 `need_reason` (≥5 karakter, potong 500) | – | izin `wms.approve` ✓, audit ✓; hitungan karakter bukan huruf ("....." lolos); textarea tanpa `maxLength` (dipotong 500 diam); tanpa "pilih semua"; "Ulangi transaksi" tanpa konfirmasi (FRM-21) |
| 113 | D2 koreksi klaim crossing (lepas / pindah) | (belum ada layar) | – | – | – | POST /rfid/v2/ops/crossings/release\|move (alasan ≥10) | – | endpoint tanpa layar (FRM-21) |
| 114 | Gate per gedung | wms/warehouses/WarehouseGateSection.jsx:27-66 | di WarehouseProfileDrawer | toggle + 5/pasangan | IN/OUT id / 0 | PATCH /warehouses → warehouse_profile_service.py:85-185 | – | nama pasangan dipotong 80 huruf diam |
| 115 | Buat label barcode | components/LabelPrinterModal.jsx:113-163 | overlay buatan sendiri | 2 | 1 / 0 | POST /labels/generate → LabelGenerateRequest | – | qty kosong → 422 array dirender → crash (FRM-16) |
| 116 | Kartu setelan (gudang & mutu) | settings/config/SettingCard.jsx:160-232 · SettingEditor.jsx | kartu cfg | nilai + alasan + berlaku sejak | enum saja | PUT /config/values → config_resolver.py:318 → `coerce` (config_registry.py:302) | – | daftar dipecah koma (regex rusak), JSON di teks satu baris, angka tanpa batas, alasan 1 huruf (FRM-19, FRM-20) |
| 117 | HP: Terima | mobile/MobileTaskActions.jsx:60-66 | kartu HP | 1 | – | scan-receive → POReceiveItem | **hilang**: doc_uom/doc_qty, batch, lot, dye_lot, grade, roll_id, bin_id, alasan override | FRM-02 |
| 118 | HP: Selesai terima | MobileTaskActions.jsx:67-74 | kartu HP | 2 | – | complete → GRCompletePayload | **hilang**: rolls[], supplier_dn, lot_number, shade_ref, override | FRM-02 |
| 119 | HP: Ambil | MobileTaskActions.jsx:84-95 | kartu HP | 1 (qty diketik) | – | scan-pick **Q** `actual_qty` saja | **hilang**: roll_id, bin_id, lot, batch | FRM-03 |
| 120 | HP: Berangkatkan | MobileTaskActions.jsx:96-98 | kartu HP | 0 | – | dispatch | **hilang**: ship_qty, konfirmasi, gabung SJ, cek muat | FRM-04 |
| 121 | HP: Potong sample | MobileTaskActions.jsx:127-140 | kartu HP | 3 | – / 1 (EPC/no roll diketik, di-resolve server) | cut-sample → SampleCutIn | – | – |
| 122 | HP: Pindai roll + bin saya | mobile/MobileWarehouseApp.jsx:165-176 | – | 2 | – / **1 (bin)** | GET /rfid/lookup · POST /rfid/roll-scans | – | INP-03 |

## A.7 Paritas HP vs desktop (keputusan pemilik: form HP = form desktop)

| Tindakan | HP | Desktop | Yang hilang di HP |
|---|---|---|---|
| Terima barang | MobileTaskActions.jsx:35-42 | InboundScanInterface.jsx:149-178 | satuan dokumen + konversi, batch, lot, dye lot, grade, pindai roll, bin, alasan override toleransi |
| Selesai terima | MobileTaskActions.jsx:43-51 | InboundScanInterface.jsx:183-255 | rincian roll (panjang/berat/dye/grade), no. SJ supplier (mode `block` → HP buntu), lot, shade, alasan override, penjaga "diterima < pesanan" |
| Ambil | MobileTaskActions.jsx:86 | OutboundScanInterface.jsx:128-131 (roll **wajib** dipindai) | roll/bin/lot; qty diketik bebas |
| Kirim | MobileTaskActions.jsx:87 | OutboundScanInterface.jsx:146-238 | kirim parsial, konfirmasi, gabung SJ, cek muat (gudang `required` → ditolak) |
| Baris SJ GRN | GrnLineCard.jsx | GrnLineRow.jsx:162-199 | katalog supplier, ringkasan packing list, peringatan "SJ hanya total", peran, hasil konversi, bruto/netto |
| Pendaftaran awal | MobileRegistration.jsx (lengkap) | RegistrationDetail.jsx | **kebalikannya**: desktop tak bisa tambah/ubah/batal baris |
| Tidak ada di HP sama sekali | – | QC kedatangan, SPK, perintah putaway (verifikasi/tiba/tutup), terima transfer, opname rutin & RFID, cek muat, encode/print job/verifikasi/pensiun tag, monitor & antrean periksa gate, eskalasi, rilis tugas terjadwal, scan label supplier/ukur/simpan ke bin | seluruh fitur |
| Cetak label | popup peramban saja (MobileWarehouseApp.jsx:83,138) | RollLabelActions.jsx (popup + antrean printer + catat `label-prints`) | antrean printer & riwayat cetak |
