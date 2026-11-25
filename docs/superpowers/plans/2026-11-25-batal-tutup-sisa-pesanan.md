# Tutup Sisa Pesanan & Persetujuan Pembatalan — Rencana Implementasi

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pesanan yang dikirim sebagian bisa ditutup sisanya, dan pembatalan/tutup sisa yang berisiko uang atau barang
lewat satu pintu persetujuan berbasis izin + tabel kebijakan, dengan komisi dikoreksi di bulan penutupan.

**Architecture:** Catatan `sales_orders.cancel_request` (satu aktif + riwayat `cancel_requests[]`) dinilai oleh layanan
baru `so_cancel_service` (wajib-setuju dari pengaturan + tabel kebijakan, siapa boleh memutus, setuju sendiri). Eksekusi
batal memakai inti `cancel_order` yang dipindah ke layanan; eksekusi tutup sisa di `so_close_remaining_service`.
Gudang ditahan lewat blok aksi. Mesin komisi membaca dasar asli pesanan yang ditutup dan baris tarik-ke-titipan sebagai
koreksi negatif, dengan saldo potongan terbawa.

**Tech Stack:** FastAPI + Motor (MongoDB), uji `backend/tests_mem` (mongomock-motor), React (craco/jest).

**Spec:** `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` (disetujui pemilik 25 Nov). Baca §1
(keputusan), §5 (rancangan), §7 (keputusan implementer) sebelum tugas mana pun.

## Global Constraints

- Bahasa kerja Indonesia: teks layar, pesan galat, pesan commit. Line ending LF.
- Wewenang dari izin (`require_permission` pernyataan pertama handler; layar `can(perms, …)`); dilarang `role ==`.
- Nilai aturan bisnis = pengaturan Pusat Pengaturan, bukan konstanta (`docs/blueprint/02_STANDAR.md` §2).
- Izin baru = empat tempat dalam satu commit (`02_STANDAR.md` §3.2).
- Tidak ada jurnal baru untuk tutup sisa; uang muka ↔ titipan sama-sama 2-1400.
- Logika gerbang RFID / `gate_evaluator` tidak diubah; pemeriksaan baru di `dispatch_guard` diletakkan sesudah gerbang bayar
  & kredit, sebelum pemeriksaan muat/RFID.
- Jangan ubah `deploy/docker-compose.yml`, `deploy/Dockerfile.*`; jangan commit `backend/.env`, `frontend/.env`,
  `memory/GATE_RECEIPT.*` (pulihkan dengan `git checkout -- memory/GATE_RECEIPT.md` sesudah gate).
- Commit diakhiri dua baris: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` dan
  `Claude-Session: https://claude.ai/code/session_01WetgRZMZjzXfrP6Zn8k4UK`. Tanpa nama model di berkas repo.
- Push hanya ke `claude/nifty-carson-jjx3c8`.
- Uji hemat: uji terarah per tugas; suite penuh + gate sekali di Tugas 8.
- Perintah uji backend (venv sesi): `V=/tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/venv;
  cd backend && $V/bin/python -m pytest tests_mem/<berkas> -n 0 -q -p no:cacheprovider`. Bila venv hilang: buat ulang
  (`python -m venv $V`, pasang `backend/requirements.txt` tanpa baris `emergentintegrations` + `tests_mem/requirements.txt`
  + `pytest pytest-xdist anyio`).
- Perintah uji frontend: `cd frontend && CI=true npx craco test --watchAll=false <berkas>`; `node_modules` belum terpasang
  di wadah ini → `cd frontend && yarn install` sekali sebelum uji jest pertama (tidak di-commit).
- Nama kunci pengaturan mengikuti ruang nama pesanan yang ada: **`sales.cancel_approval_when`** (spesifikasi menulis
  `order.cancel_approval_when`; isinya sama).

## Review Focus

1. **Klik ganda / dua orang bersamaan** — mengajukan dua kali saat sudah ada yang menunggu, atau dua penyetuju menekan
   Setujui bersamaan: hanya satu yang lolos (409 untuk yang lain), eksekusi tidak berjalan dua kali. → Tugas 2.
2. **Keadaan berubah selama menunggu** — Faktur Pajak terbit atau pesanan kedaluwarsa sesudah permintaan diajukan:
   persetujuan menolak 409 berpesan dan permintaan tetap/void sesuai keadaan, bukan membatalkan diam-diam. → Tugas 2.
3. **Layar lama menerima 202** — `SoApprovalsPanel` dan `OrdersView.onCancel` (AppViewRouter) dulu menampilkan
   "dibatalkan" untuk respons sukses apa pun: harus berkata "diajukan, menunggu persetujuan". → Tugas 6.
4. **Lintas PT** — penyetuju yang tidak bertugas di PT pesanan tidak bisa memutus dan tidak melihat permintaan di antrean.
   → Tugas 2.
5. **Bayar dan tarik di bulan yang sama** — CBD dibayar dan sisanya ditutup di bulan yang sama: komisi bersih = bagian
   terkirim, tanpa saldo potongan. → Tugas 5.

---

### Task 1: Fondasi — izin, jenis persetujuan, antrean, pengaturan

**Files:**
- Modify: `backend/permissions_config.py` (blok `admin`, `manager`, `finance`: `order` + `"approve_cancel"`)
- Modify: `backend/access_modules.py` (label aksi `"approve_cancel": "Setujui pembatalan & tutup sisa pesanan"`; masukkan
  `("order", "approve_cancel")` ke kelompok `_SENSITIVE_GROUPS` "mengirim barang sebelum lunas dan mengubah pesanan terkunci")
- Modify: `backend/approval_kinds.py` (jenis `sales_order.batal`)
- Modify: `backend/services/approval_backlog_service.py` (`QUEUES` baris `so_cancel`)
- Modify: `backend/config_catalog_core.py` (kunci `sales.cancel_approval_when`)
- Modify: `backend/tests_mem/test_KPT4a_setara.py:277` (41 → 42, komentar "+ `so_cancel`")
- Modify: `backend/tests_mem/test_KFT1_izin_pengaturan.py` (tambah konstanta `BTP_KUNCI = 1` ke kedua jumlah, pola `KA1_KUNCI`)
- Modify: `frontend/src/features/settings/config/configKeyIndex.json` (hasil `python scripts/gen_config_key_index.py`)
- Test: `backend/tests_mem/test_BTP1_fondasi.py`

**Interfaces:**
- Produces: izin `order.approve_cancel`; `APPROVAL_KINDS["sales_order.batal"]` (`queue_key="so_cancel"`,
  `permissions=("order.approve_cancel",)`, `amount_field="grand_total"`, grup "Penjualan", label
  "Pesanan Penjualan — pembatalan & tutup sisa"); antrean `("so_cancel", "Pembatalan/tutup sisa pesanan menunggu ACC",
  "approval-inbox", "sales_orders", {"cancel_request.status": "pending"})`; kunci `sales.cancel_approval_when`
  (enum `dibayar_atau_disiapkan` | `selalu` | `tidak_pernah`, bawaan `dibayar_atau_disiapkan`, cakupan global + entity,
  grup `penjualan`, seksi `alur-pesanan`, `consumers=("services/so_cancel_service.py:needs_approval",)`).

- [ ] **Step 1: Tulis uji gagal** `test_BTP1_fondasi.py`:
  - `test_BTP1_izin_bawaan`: `DEFAULT_PERMISSIONS[r]["order"]` memuat `approve_cancel` untuk `admin`, `manager`,
    `finance`; tidak untuk `sales`, `sales_admin`.
  - `test_BTP1_kebijakan_bawaan_semua_pemegang`: `await aps.required_levels("sales_order.batal", "ent_ksc", 5_000_000)`
    tidak kosong dan level 1 `any_holder is True`.
  - `test_BTP1_pengaturan_bawaan`: `await nilai("sales.cancel_approval_when", "ent_ksc") == "dibayar_atau_disiapkan"`.
  - `test_BTP1_antrean_menghitung_pending`: sisipkan SO `cancel_request.status="pending"` + satu `"rejected"` → hitungan
    antrean `so_cancel` dari `approval_backlog_service` = 1 (pakai fungsi hitung yang dipakai Beranda; cari namanya di
    modul itu).
- [ ] **Step 2: Jalankan — gagal** (KeyError jenis / izin tidak ada).
- [ ] **Step 3: Implementasi** lima berkas backend di atas sesuai Interfaces; teks `help`/`impact`/`example` kunci
  pengaturan dalam bahasa sehari-hari (contoh: "Pesanan CBD sudah dibayar Rp 2.000.000 → pembatalan diajukan ke
  penyetuju").
- [ ] **Step 4: Selaraskan penjaga**: perbarui `test_KPT4a_setara.py` (42) dan `test_KFT1` (+1); jalankan
  `python scripts/gen_config_key_index.py`; jalankan `python scripts/guardrails/verify_approval_queues.py` dan
  `python scripts/guardrails/verify_permission_checked.py` — boleh merah **hanya** karena `order.approve_cancel` belum
  diperiksa endpoint (dicatat, hijau di Tugas 2).
- [ ] **Step 5: Jalankan** `test_BTP1_fondasi.py test_KPT4a_setara.py test_KFT1_izin_pengaturan.py` → lulus.
- [ ] **Step 6: Commit** `feat(penjualan): fondasi persetujuan batal & tutup sisa — izin, jenis, antrean, pengaturan`.

### Task 2: Permintaan batal + persetujuan (server)

**Files:**
- Create: `backend/services/so_cancel_service.py`
- Modify: `backend/routers/sales_orders_extra.py:888-1000` (`cancel_order` menjadi pembungkus tipis; endpoint baru)
- Modify: `backend/services/inventory_service.py:~95` (pesanan kedaluwarsa → `void_pending`)
- Test: `backend/tests_mem/test_BTP2_permintaan_batal.py`

**Interfaces:**
- Consumes: Tugas 1 (izin, jenis, kunci); `services.notification_service.create_addressed`;
  `services.approval_policy_service.required_levels / can_decide`; `services.atomic_claim`.
- Produces (dipakai Tugas 3–6):
  - `async def execute_cancel(order_id: str, actor: Dict, reason: str) -> Dict` — isi lama `cancel_order` sesudah
    pemeriksaan izin/kepemilikan/alasan, **tanpa perubahan perilaku** (status terlarang, Faktur Pajak 409, klaim saga,
    roll, transisi, titipan, notifikasi, tugas gudang, jurnal balik, pengganti retur, sample berbayar).
  - `def is_order_sales(order: Dict, actor: Dict) -> bool` — `actor.id == order.sales_id` atau ada di
    `order.sales_team[].sales_id`.
  - `async def prepared_basis(order: Dict, remaining_only: bool = False) -> bool` — §5.2 "barang sudah disiapkan".
  - `async def needs_approval(order: Dict, action: str, *, amount: float, excess: float = 0.0) -> Dict` →
    `{"needs": bool, "basis": List[str], "amount": float}`; `action ∈ {"cancel","close_remaining"}`; `amount` =
    `grand_total` (batal) atau nilai sisa (tutup sisa); `basis` berisi `"paid"` (batal, `paid_total > 0`), `"excess"`
    (tutup sisa, `excess > 0`), `"prepared"` (`prepared_basis`, untuk tutup sisa `remaining_only=True`). `needs` = pengaturan
    menyatakan wajib (`selalu`, atau `dibayar_atau_disiapkan` dengan `basis` tidak kosong) **dan** `required_levels(
    "sales_order.batal", entity, amount)` tidak kosong.
  - `async def can_decide(order: Dict, req: Dict, actor: Dict) -> Dict` → `{"allowed": bool, "message": str}`
    (izin + kebijakan nominal + bukan pengaju + `not is_order_sales` + akses PT).
  - `async def submit(order_id: str, action: str, actor: Dict, reason: str) -> Tuple[int, Dict]` — 200 + hasil eksekusi
    (langsung / setuju sendiri, `self_approved=True` tercatat di `cancel_requests[]`) atau 202 +
    `{"request": cancel_request, "order_status": str, "message": "Permintaan diajukan — menunggu persetujuan."}`.
    Eksekutor per aksi didaftarkan lewat peta `EXECUTORS = {"cancel": execute_cancel}`; Tugas 4 menambah
    `"close_remaining"`.
  - `async def decide(order_id: str, actor: Dict, decision: str, note: str) -> Dict` (`approve` | `reject`, alasan wajib
    saat tolak; eksekusi ulang memeriksa status & faktur; galat eksekusi → permintaan tetap `pending`, 409 berpesan).
  - `async def withdraw(order_id: str, actor: Dict) -> Dict`.
  - `async def void_pending(order_id: str, reason: str, actor_name: str = "system") -> bool`.
  - `async def pending_of(order_id: str) -> Optional[Dict]` (dipakai Tugas 3).
  - Endpoint: `POST /api/sales-orders/{id}/cancel` (perilaku via `submit`, `order.cancel`), `POST
    /api/sales-orders/{id}/cancel-request/decision` (`order.approve_cancel`), `POST
    /api/sales-orders/{id}/cancel-request/withdraw` (`order.cancel`), `GET /api/sales-orders/cancel-requests?status=pending`
    (`order.approve_cancel`, tercakup PT aktor), `GET /api/sales-orders/{id}/cancel-check?action=cancel|close_remaining`
    (`order.cancel`) → `{"needs_approval", "basis", "can_self_approve", "amount"}` (Tugas 4 menambah `preview`).
  - Bentuk `cancel_request` persis §5.1 spesifikasi; keputusan/penarikan/void: objek final di-`$push` ke
    `cancel_requests[]`, `cancel_request` di-`$unset`. Semua transisi bersyarat `{"cancel_request.status": "pending",
    "cancel_request.id": <id>}`.

- [ ] **Step 1: Tulis uji gagal** `test_BTP2_permintaan_batal.py` (fixture seperti `test_batal_titipan_beri_tahu_finance.py`;
  akun `sales` sebagai `sales_id` pesanan, `finance`, `manager`):
  - `test_BTP2_belum_bayar_belum_siap_langsung_batal` — sales batal → 200 `status == "cancelled"`, tanpa `cancel_request`.
  - `test_BTP2_dibayar_jadi_permintaan` — dibayar Rp 1.000.000, sales batal → **202**, `request.status == "pending"`,
    `request.needs_approval is True`, `"paid" in request.approval_basis`; pesanan **tidak** batal; finance mendapat notifikasi
    `type == "permintaan_batal_pesanan"`.
  - `test_BTP2_setujui_menjalankan_batal_dan_titipan` — finance memutus approve → 200, pesanan `cancelled`,
    `advance_to_deposit` = 1.000.000, pengaju & sales diberi tahu (`type == "permintaan_batal_diputus"`),
    `cancel_requests[-1].status == "approved"`.
  - `test_BTP2_tolak_pesanan_lanjut` — reject tanpa alasan → 422; dengan alasan → pesanan status tetap, `cancel_request`
    hilang, riwayat `rejected`.
  - `test_BTP2_sales_tidak_bisa_menyetujui_miliknya` — peran kustom tanpa acuan `{"order": ["view","cancel",
    "approve_cancel"]}` diberi ke sales pemilik: pengajuannya **tidak** disetujui sendiri (202) dan keputusan olehnya → 403.
  - `test_BTP2_manager_disetujui_sendiri` — manager membatalkan pesanan dibayar → 200 `cancelled`,
    `cancel_requests[-1].self_approved is True`.
  - `test_BTP2_tarik_permintaan` — pengaju menarik → 200; status pesanan tetap; riwayat `withdrawn`.
  - `test_BTP2_pengaturan_selalu_dan_tidak_pernah` — set kunci per PT via API pengaturan: `selalu` → pesanan belum
    dibayar juga 202; `tidak_pernah` → dibayar langsung 200.
  - `test_BTP2_rentang_mulai_x_membebaskan` — tulis baris kebijakan PT mulai Rp 5.000.000: pesanan dibayar Rp 1.000.000 →
    200 langsung.
  - Review Focus 1: `test_BTP2_ajukan_dua_kali_409` dan `test_BTP2_dua_penyetuju_satu_lolos` (dua `decide` berurutan →
    kedua 409, eksekusi sekali: `advance_to_deposit` tetap 1×).
  - Review Focus 2: `test_BTP2_faktur_terbit_saat_menunggu` — sisipkan `tax_invoices` `status="normal"` sesudah pengajuan
    → approve 409 berpesan Faktur Pajak, `cancel_request.status` tetap `pending`.
  - Review Focus 4: `test_BTP2_lintas_pt` — finance hanya bertugas `ent_kanda` → keputusan 403/404 dan daftar
    `cancel-requests` tidak memuat pesanan `ent_ksc`.
  - `test_BTP2_kedaluwarsa_mem_void` — `void_pending` dipanggil jalur kedaluwarsa → riwayat `void`.
  - `test_BTP2_izin_baku` — peran tanpa acuan `{"order": ["view","approve_cancel"]}` → `GET cancel-requests` 200; peran
    acuan Manajer dengan modul "Tidak ada" → 403.
- [ ] **Step 2: Jalankan — gagal.**
- [ ] **Step 3: Implementasi** `so_cancel_service.py` + endpoint. Data dulu semua jalur server yang menulis
  `sales_orders.status = "cancelled"` (`grep -rn '"cancelled"' backend/services backend/routers | grep -i sales_orders`):
  selain `cancel_order` dan kedaluwarsa, tiap jalur dicatat di laporan beserta alasan dibiarkan/dialihkan. `cancel_order` lama memanggil `submit(..., "cancel", …)`
  dan mengembalikan `JSONResponse(status_code=202, …)` bila 202. Notifikasi: pending → `create_addressed(permission=("order",
  "approve_cancel"), entity_id=…, notif_type="permintaan_batal_pesanan", ref=f"permintaan_batal_pesanan:{req_id}",
  link="approval-inbox")`; putusan → `create_addressed(also_users=(pengaju, sales_id…), notif_type="permintaan_batal_diputus")`.
- [ ] **Step 4: Jalankan** `test_BTP2_*`, `test_latih_s3_batal_uang_muka.py`, `test_batal_titipan_beri_tahu_finance.py`
  → lulus (admin = setuju sendiri, jadi kedua uji lama tetap 200). Cari uji lain yang membatalkan pesanan dibayar sebagai
  sales (`grep -rln "/cancel\"" backend/tests_mem`), jalankan, dan sesuaikan harapan 200→202 hanya bila memang kasus
  wajib-setuju (sebut di laporan).
- [ ] **Step 5:** `python scripts/guardrails/verify_permission_checked.py` hijau. **Commit**
  `feat(penjualan): permintaan batal pesanan + persetujuan berbasis izin & kebijakan`.

### Task 3: Tahan gudang & jalur sejajar selama permintaan menunggu

**Files:**
- Modify: `backend/services/loading_check_service.py:307` (`dispatch_guard`, sesudah `credit_gate.gate_checkpoint`)
- Modify: `backend/routers/outbound_picking.py:215` (scan pick) dan `:363` (`resolve_outbound_escalation`)
- Modify: `backend/routers/wms.py:250` (`advance_task`, hanya tugas `flow_type == "outbound"`)
- Modify: `backend/services/so_line_cancel_service.py` (`check`)
- Test: `backend/tests_mem/test_BTP3_tahan_gudang.py`

**Interfaces:**
- Consumes: `so_cancel_service.pending_of(order_id)`.
- Produces: `async def assert_not_pending(order_id: str) -> None` di `so_cancel_service` — 409
  "Pesanan sedang diajukan batal/tutup sisa — tunggu keputusan." (satu teks dipakai semua pintu).

- [ ] **Step 1: Tulis uji gagal**: dengan `cancel_request` pending pada pesanan bertugas outbound —
  `test_BTP3_kirim_diblok` (panggil `dispatch_guard` → 409), `test_BTP3_ambil_diblok` (POST scan pick → 409),
  `test_BTP3_maju_tahap_diblok` (POST `/wms/tasks/{id}/advance` → 409), `test_BTP3_eskalasi_tutup_sisa_diblok`,
  `test_BTP3_batal_item_pesanan_khusus_diblok`; dan `test_BTP3_ditolak_pulih` (sesudah reject, `advance` → 200).
  Tambah `test_BTP3_eskalasi_dibayar_pesan_baru`: pesanan dibayar → eskalasi `close_remainder` 400 dengan pesan memuat
  "Tutup sisa".
- [ ] **Step 2: Jalankan — gagal.**
- [ ] **Step 3: Implementasi** `assert_not_pending` dan panggilannya di kelima pintu; ganti pesan eskalasi
  "penyesuaian qty harus lewat retur/credit note" menjadi "Pesanan sudah dibayar — tutup sisanya lewat tombol Tutup sisa
  di rincian pesanan." Tugas gudang di layar: tambahkan field turunan `held_reason` pada respons daftar tugas outbound bila
  pending (cari endpoint daftar tugas yang dipakai layar picking).
- [ ] **Step 4: Jalankan** `test_BTP3_*` + uji yang sudah ada untuk eskalasi dan batal item OD
  (`grep -rln "resolve-escalation\|items/.*/cancel" backend/tests_mem`) → lulus.
- [ ] **Step 5: Commit** `feat(gudang): tahan kirim/ambil/kemas selama pesanan diajukan batal`.

### Task 4: Eksekusi tutup sisa

**Files:**
- Create: `backend/services/so_close_remaining_service.py`
- Modify: `backend/services/ar_receipt_service.py` (`uang_muka_pesanan_batal_ke_titipan` → inti bersama)
- Modify: `backend/services/so_cancel_service.py` (`EXECUTORS["close_remaining"]`, `cancel-check` memuat `preview`)
- Modify: `backend/routers/sales_orders_extra.py` (`POST /api/sales-orders/{id}/close-remaining`, `order.cancel`)
- Test: `backend/tests_mem/test_BTP4_tutup_sisa.py`

**Interfaces:**
- Consumes: Tugas 2 `submit`; `gl_service.order_revenue_recognized`, `gl_service.order_advance_unrecognized`;
  `roll_service.release_order_rolls`; `outbound_task_state`; `fulfillment_status.recompute_so_status`;
  `config_service.compute_order_pricing`; `tax_config_service.potret_dokumen`.
- Produces:
  - `async def preview(order: Dict) -> Dict` → `{"allowed": bool, "blockers": [str], "lines": [{product_id,
    product_name, unit, qty_ordered, qty_shipped}], "grand_total_before", "grand_total_after", "remaining_value",
    "excess_to_deposit"}`.
  - `async def execute_close_remaining(order_id: str, actor: Dict, reason: str) -> Dict` — langkah §5.6 1–8 spesifikasi.
  - Di `ar_receipt_service`: `async def pindah_uang_muka_ke_titipan(order: Dict, actor: Any, reason: str, amount: float,
    source_id: str, kata: str) -> float` (inti: penanda `advance_to_deposit`, `withdraw` ber-`moved_to_deposit`,
    `_adjust_deposit`, notifikasi Finance); `uang_muka_pesanan_batal_ke_titipan` memanggilnya dengan
    `amount = min(unrecognized, paid)`, `source_id=f"batal_titipan:{id}"`, `kata` dari status; tutup sisa memakai
    `source_id=f"tutup_sisa_titipan:{id}"`, `kata="sisa ditutup"`. Syarat status `DEAD_STATUSES` dipindah ke pembungkus batal.
  - Field pesanan: `items[].quantity_ordered_original`, `items[].base_quantity_ordered_original`, `closed_lines[]`,
    `closed_short = {at, by, reason, request_id, commission_basis: {grand_total, items: [{product_id, base_quantity}]}}`.

- [ ] **Step 1: Tulis uji gagal** `test_BTP4_tutup_sisa.py` (bangun pesanan `partially_shipped` lewat alur nyata bila ada
  helper di `tests_mem` — cari `shipment_revenue` di uji yang ada; bila tidak, sisipkan tugas outbound ber-`shipped_qty` +
  panggil `gl_service.post_shipment_revenue` agar jurnal Surat Jalan nyata):
  - `test_BTP4_tempo_jumlah_turun_ke_terkirim` — 100 m dipesan, 40 terkirim, belum bayar: 200; `items[0].quantity == 40`,
    `quantity_ordered_original == 100`; `grand_total == revenue+ppn` jurnal Surat Jalan; jumlah `journal_entries` tidak
    bertambah; status `shipped`; `closed_short.reason` terisi; roll sisa `available`; tugas sisa `cancelled`.
  - `test_BTP4_plafon_kembali` — `open_orders_amount` pelanggan turun sebesar nilai sisa.
  - `test_BTP4_cbd_kelebihan_ke_titipan` — CBD dibayar penuh 100, 40 terkirim: sales mengajukan → 202 (`"excess"` di
    basis); finance setuju → titipan pelanggan naik tepat nilai 60 m; `order_advance_unrecognized` = 0; jurnal tidak
    bertambah; notifikasi Finance `titipan_pesanan_batal` berteks "sisa ditutup".
  - `test_BTP4_tempo_sudah_bayar_terkirim_tidak_wajib_setuju` — tempo, bagian terkirim sudah dibayar, sisa belum
    disiapkan → sales langsung 200.
  - `test_BTP4_tolak_*` — satu uji per penolak: Faktur Pajak per pesanan aktif (lolos bila semua baris faktur ber-
    `shipment_id`), nota amandemen/`extra_billing_lines`, jurnal `source_type="sales_order"`, baris terkirim > dipesan,
    produk sama di dua baris, baris `special_order_item_id` belum terkirim penuh, status bukan `partially_shipped` →
    409 berpesan; tidak ada perubahan pada pesanan.
  - `test_BTP4_satuan_jual_berbeda` — baris `quantity` yard vs `base_quantity` meter: `quantity` baru =
    `shipped_base × quantity/base_quantity` (pola `routers/outbound_picking.py:~475`).
  - `test_BTP4_selisih_hitung_ulang_ditolak` — paksa diskon pesanan berjenjang sehingga hitung ulang ≠ yang dibukukan
    lebih dari Rp 1/baris → 409, pesanan tidak berubah.
  - `test_BTP4_preview` — `GET cancel-check?action=close_remaining` memuat `preview.lines` & `excess_to_deposit`.
- [ ] **Step 2: Jalankan — gagal.**
- [ ] **Step 3: Implementasi** `so_close_remaining_service.py` + refaktor `ar_receipt_service` + endpoint. Klaim saga
  `atomic_claim.claim("sales_orders", id, "order_close_remaining", precondition={"status": "partially_shipped"})`.
  Totals dipaksa = yang dibukukan: `grand_total`, `ppn_amount`, `approval_amount`; DPP/subtotal mengikuti selisih
  `grand_total − ppn`; selisih pembulatan baris ke baris terakhir.
- [ ] **Step 4: Jalankan** `test_BTP4_*`, `test_BTP2_*`, `test_latih_s3_batal_uang_muka.py`,
  `test_batal_titipan_beri_tahu_finance.py` → lulus.
- [ ] **Step 5: Commit** `feat(penjualan): tutup sisa pesanan terkirim sebagian (nilai = yang dibukukan, kelebihan → titipan)`.

### Task 5: Komisi dipotong di bulan penutupan + saldo potongan

**Files:**
- Modify: `backend/services/sales_force_service.py:383-542` (`_compute_commission_per_sku`, `compute_commission`)
- Modify: `backend/services/commission_rules.py:322` (`hitung_baris` jalur koreksi) dan `_rincian_bersih` (simpan `carry_out`)
- Modify: `backend/services/gl_service.py:3668` (`incentive_accrual_rincian` meneruskan `carry_out`)
- Modify: `frontend/src/features/incentive/rincianKomisi.js` (label baris koreksi & potongan terbawa)
- Test: `backend/tests_mem/test_BTP5_komisi_koreksi.py`

**Interfaces:**
- Consumes: `closed_short.commission_basis` (Tugas 4); baris `payments[]` ber-`moved_to_deposit: True` (Tugas 4 &
  fungsi titipan lama); potret beku `commission_period_rules.sales[]`.
- Produces:
  - Aturan mesin: pesanan `DEAD_STATUSES` **ikut dihitung** hanya bila `advance_to_deposit.deposit_done` benar; pesanan
    ber-`closed_short` memakai `commission_basis` (jumlah dasar per baris & `grand_total` asli) sebagai dasar.
  - Pembayaran biasa di periode → `fraksi` seperti sekarang (tetap dipotong ≥ 0). Baris `moved_to_deposit` di periode →
    `fraksi_koreksi = Σ/gt_dasar` (negatif) → `hitung_koreksi(aturan, line, fraksi=abs(fraksi_koreksi), …)` dikalikan −1:
    `def hitung_koreksi(aturan: Dict, line: Dict, *, fraksi: float, bobot: float, biaya: float, biaya_diketahui: bool,
    pengali_capaian: float) -> Dict` mengembalikan bentuk sama dengan `hitung_baris` dengan `komisi ≤ 0`, tidak terpotong nol.
  - Rincian: baris koreksi digabung terpisah dengan `price_reason="koreksi_batal"` atau `"koreksi_tutup_sisa"`.
  - Hasil `compute_commission` (per_sku) menambah `carry_in`, `carry_out`, `commission_raw`; `total_incentive =
    max(0, commission_raw + carry_in)`; `carry_out = min(0, commission_raw + carry_in)`. `carry_in` = `carry_out` sales
    itu di potret beku PT bulan sebelumnya (0 bila tidak ada); hitungan `entity_id="all"` = jumlah per PT.

- [ ] **Step 1: Tulis uji gagal** `test_BTP5_komisi_koreksi.py` (tarif per artikel seperti `test_KA5_*`):
  - `test_BTP5_tutup_sisa_bulan_asal_tetap` — CBD 100 m dibayar 2026-10, akru 2026-10 (`post_incentive_accrual`); 40
    terkirim, tutup sisa 2026-11 → `compute_commission(…,"2026-10")` sama dengan sebelum tutup sisa; 2026-11 memuat baris
    koreksi = −(komisi 60 m) dan total bulan = `max(0, …)`.
  - `test_BTP5_koreksi_tidak_dipotong_margin` — tarif dengan `margin_cap_pct` aktif: koreksi tetap negatif.
  - `test_BTP5_saldo_terbawa` — bulan 2026-11 tanpa komisi lain: `total_incentive == 0`, `carry_out < 0`; bekukan 2026-11;
    2026-12 dengan komisi lain → `carry_in == carry_out bulan lalu` dan total berkurang.
  - `test_BTP5_batal_sesudah_bayar` — dibayar 2026-10 (akru), batal 2026-11: 2026-10 tetap; 2026-11 koreksi −penuh.
  - `test_BTP5_batal_sebelum_bayar_hilang` — pesanan dibatalkan tanpa pembayaran: tidak muncul di bulan mana pun.
  - `test_BTP5_batal_lama_tanpa_penanda_tetap_dikecualikan` — pesanan batal ber-pembayaran tanpa `advance_to_deposit`
    → tetap dikecualikan (perilaku lama).
  - Review Focus 5: `test_BTP5_bayar_dan_tutup_bulan_sama` — komisi bulan = bagian terkirim, `carry_out == 0`.
  - `test_BTP5_titipan_dipakai_pesanan_lain` — komisi pesanan baru normal, tanpa dobel.
- [ ] **Step 2: Jalankan — gagal.**
- [ ] **Step 3: Implementasi.** Jangan ubah pembulatan/perilaku pesanan yang tidak ber-`closed_short` dan tidak ber-
  `advance_to_deposit` (jalankan `scripts/komisi/banding_mesin_komisi.py` pada data acuan bila tersedia, catat hasilnya).
- [ ] **Step 4: Jalankan** `test_BTP5_*` + `test_KA*` + `test_KMT*` → lulus; `cd frontend && CI=true npx craco test
  --watchAll=false src/features/__tests__/kaRincianSales.test.js` → lulus (tambah satu kasus label koreksi).
- [ ] **Step 5: Commit** `feat(komisi): koreksi komisi di bulan penutupan untuk batal/tutup sisa + saldo potongan terbawa`.

### Task 6: Layar rincian pesanan — dialog, ringkasan, bilah menunggu

**Files:**
- Modify: `frontend/src/features/orders/CancelOrderDialog.jsx`
- Create: `frontend/src/features/orders/CloseRemainingDialog.jsx`
- Create: `frontend/src/features/orders/CancelRequestBar.jsx`
- Modify: `frontend/src/features/orders/OrderDetailPanel.jsx:~719` (tombol Tutup sisa, bilah)
- Modify: `frontend/src/features/orders/SoApprovalsPanel.jsx:94`, `frontend/src/AppViewRouter.jsx:270` (pesan 202)
- Test: `frontend/src/features/__tests__/btpBatalTutupSisa.test.js`

**Interfaces:**
- Consumes: endpoint Tugas 2 & 4 (`cancel-check`, `cancel`, `close-remaining`, `cancel-request/decision`,
  `cancel-request/withdraw`); izin layar `can(perms, "order", "cancel")`, `can(perms, "order", "approve_cancel")`.
- Produces: `CancelRequestBar({ order, perms, onDone })`, `CloseRemainingDialog({ order, onClose, onDone })`.

- [ ] **Step 1: Tulis uji gagal** `btpBatalTutupSisa.test.js` (pola `latihS3BatalUangMuka.test.js`, axios dimock):
  - dialog batal memanggil `cancel-check`; `needs_approval: true, basis: ["paid"]` → tombol bertuliskan "Ajukan
    pembatalan" dan teks alasan "sudah ada pembayaran"; respons 202 → `onDone` dengan pesan memuat "menunggu persetujuan".
  - `needs_approval: false` → tombol "Ya, Batalkan SO" (perilaku lama).
  - dialog tutup sisa menampilkan baris "100 → 40", nilai sebelum → sesudah, dan "jadi titipan" bila `excess_to_deposit > 0`;
    `allowed: false` → daftar `blockers` tampil dan tombol nonaktif.
  - bilah menunggu: pemegang `approve_cancel` (bukan pengaju) melihat Setujui/Tolak; Tolak tanpa alasan nonaktif; pengaju
    melihat Tarik.
  - Review Focus 3: `SoApprovalsPanel` menerima 202 → pesan "diajukan", bukan "dibatalkan".
- [ ] **Step 2: Jalankan — gagal.**
- [ ] **Step 3: Implementasi** mengikuti `docs/blueprint/04_POLA_UI.md`; tombol **Tutup sisa** tampil untuk
  `partially_shipped` + `order.cancel`; tombol Batalkan & Tutup sisa disembunyikan saat `cancel_request` pending.
- [ ] **Step 4: Jalankan** berkas uji baru + `latihS3BatalUangMuka.test.js` + uji `OrderDetailPanel` yang ada → lulus.
- [ ] **Step 5: Commit** `feat(layar): ajukan batal & tutup sisa, ringkasan sebelum-sesudah, bilah menunggu persetujuan`.

### Task 7: Pusat Persetujuan & tanda gudang

**Files:**
- Modify: `frontend/src/features/approvals/inboxTabs.js` (tab `so_cancel` "Pembatalan Pesanan", peta
  `BACKLOG_INBOX_TAB.so_cancel`, `LISTED_IN_INBOX`)
- Modify: `frontend/src/features/approvals/approvalInboxData.js` (grab `GET /sales-orders/cancel-requests`, izin
  `[["order","approve_cancel"]]`, butir `kind: "so_cancel"` membuka rincian pesanan)
- Modify: layar daftar tugas picking yang membaca `held_reason` (Tugas 3) — cari komponen yang memanggil endpoint
  daftar tugas outbound
- Test: `frontend/src/features/__tests__/btpInboxBatal.test.js`

**Interfaces:**
- Consumes: `GET /api/sales-orders/cancel-requests` (Tugas 2), `held_reason` (Tugas 3).

- [ ] **Step 1: Tulis uji gagal**: data inbox memetakan satu permintaan ke butir berjudul nomor pesanan + pelanggan, jenis
  "Batal"/"Tutup sisa", nilai, alasan, pengaju; tab `so_cancel` ada di `INBOX_TABS`; komponen tugas picking menampilkan
  "Ditahan: menunggu keputusan batal" bila `held_reason`.
- [ ] **Step 2: Jalankan — gagal.**
- [ ] **Step 3: Implementasi.**
- [ ] **Step 4: Jalankan** berkas uji baru + `src/features/__tests__` yang menyebut `inboxTabs` → lulus.
- [ ] **Step 5: Commit** `feat(persetujuan): antrean pembatalan pesanan di Pusat Persetujuan + tanda ditahan di gudang`.

### Task 8: Uji penuh, gate, laporan

**Files:**
- Create: `docs/superpowers/plans/2026-11-25-batal-tutup-sisa-pesanan-hasil.md`
- Modify: spesifikasi §8 bila ada keputusan builder baru (tambahkan di §7 sebagai "keputusan implementer").

- [ ] **Step 1:** `cd backend && $V/bin/python -m pytest tests_mem -q -p no:cacheprovider` (latar) → catat angka.
- [ ] **Step 2:** `cd frontend && CI=true npx craco test --watchAll=false` sekali → catat angka.
- [ ] **Step 3:** `bash scripts/gate.sh --quick` di pohon akhir dan di worktree garis dasar `25078cf` (salin `backend/.env`
  ke worktree, hapus sesudahnya) → `python3 scripts/blueprint/bandingkan_pelanggaran_gate.py <dasar> <baru>` = "tidak ada
  pelanggaran baru"; pulihkan `memory/GATE_RECEIPT.md`.
- [ ] **Step 4:** tulis laporan hasil: tabel tugas → commit → uji, keputusan builder, angka suite & gate apa adanya,
  langkah sebelum rilis VPS (tidak ada migrasi data; pesanan lama tanpa `closed_short`/penanda tidak berubah perilakunya).
- [ ] **Step 5: Commit & push** `docs(penjualan): laporan tutup sisa & persetujuan pembatalan`.
