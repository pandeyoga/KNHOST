# Meja Gelombang 1 — Kerangka Meja Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Semua meja desktop memakai satu kerangka: satu kepala (TopBar) dengan ikon ? di samping judul, tab Antrean/Pantau,
kartu antrean berukuran tetap (5 baris, termasuk kosong/memuat) dengan baris ringkas yang bisa diklik dan membuka pop-up
rincian umum, aksi berakibat besar lewat pratinjau + konfirmasi di komponen bersama, satu skala huruf ≥ 12 px, satu nama per
meja, isian server yang utuh dan jujur, hapus ganda antar kartu, serta baris HP yang bisa disentuh.

**Architecture:** Server (`work_desk_service`, `role_desk_service`, `so_tracker_service`, router `sample_orders`) mengirim
baris lengkap (`entity_id`, `age_kind`, `at` nyata, teks utuh, isian aksi di tempat). Layar memakai satu kartu
`DeskQueueCard` (ukuran tetap, status di `sessionStorage`) yang membuka `DeskRowDetail` (`DetailModal`) — isinya dipilih
registri `ref_type → panel` (kosong di gelombang 1, jatuh ke panel umum). Kerangka `DeskFrame` menaruh tab Antrean/Pantau,
ikon ? (lewat `PageHelpContext` ke `TopBar`), pemulihan gulir, dan sinyal muat ulang global; konfirmasi aksi besar
(`TaxIssueDialog`, `ReleaseToWarehouseDialog`, `SamplePaymentApproveDialog`) adalah komponen bersama yang dipakai meja dan
layar asalnya.

**Tech Stack:** FastAPI + Motor (MongoDB), uji `backend/tests_mem` (mongomock-motor); React 18 (craco/jest, tanpa
testing-library: `createRoot` + `act` + `querySelector` testid), Tailwind token `text-fs-*` / `kn-*`.

**Spec:** docs/superpowers/specs/2026-11-25-meja-kerja-di-tempat-design.md

Bukti dasar: `docs/audit/meja-2026-11-25/LAPORAN_AUDIT_MEJA.md`, `LAMPIRAN_A_AUDIT_KODE.md` (dibaca di `db0a20f`; rujukan
`berkas:baris` dalam rencana ini sudah dicek ulang di `HEAD 7c32c3f`). Cakupan = **gelombang 1 saja** (§6): §5.1, §5.2, §5.3
(panel umum + registri kosong), §5.4, §5.5 untuk kerangka meja, §5.6, §5.8, §5.9.

## Global Constraints

- Bahasa Indonesia untuk teks layar, pesan galat, isi dokumen, dan pesan commit; pengenal kode tetap Inggris.
- Wewenang dari izin (`can(perms, sumber, aksi)` di layar; `require_permission`/`has_permission` di server); dilarang membandingkan nama peran.
- Nilai aturan bisnis = pengaturan (Pusat Pengaturan), bukan konstanta baru; ukuran tampilan (tinggi kartu, baris/halaman) bukan aturan bisnis.
- Line ending LF untuk semua berkas baru/diubah.
- Jangan sentuh `deploy/` (compose & Dockerfile produksi).
- Tidak ada nama model di berkas repo; baris trailer commit diberikan pengendali, tidak ditulis di rencana.
- Pop-up hanya lewat `components/DetailModal.jsx` / `components/FormModal.jsx` / `components/DetailPopup.jsx` (+ `askConfirm` yang sudah ada); penjaga `custom_modals` INV-UI-11, `create_modal` INV-UI-05, `detail_modal` INV-UI-08, `page_tabs` INV-UI-12/13/14 dan ratchet `verify_ui_standard.py` tidak boleh bertambah pelanggaran (berkas baru: semua metrik 0 — tanpa hex, tanpa `text-[Npx]`, tombol berkelas baku `primary-button`/`secondary-button`/`danger-button`/`link-button`/`icon-button` + `btn-sm`, tanpa `|| x.id` sebagai label).
- Aksi di pop-up memanggil endpoint dan pemeriksaan yang sama dengan layar asalnya; tidak ada endpoint baru untuk aksi yang sudah ada (perubahan server hanya menambah isian baris antrean).
- Nama tunggal (menu = breadcrumb = judul): **Meja Admin Sales · Meja Keuangan · Meja Gudang · Meja Sample · Meja MD · Meja Saya**; tab hub "Perlu Tindakan" → "Meja Keuangan"; teks "Meja Finance" → "Meja Keuangan".
- Kartu antrean desktop (≥ 640 px) tinggi tetap `sm:h-[404px]` = kepala `h-11` (44) + bilah saring `h-11` (44) + 5 baris × `sm:h-14` (56) + kaki `h-9` (36); sama untuk kartu berisi, < 5 baris, kosong ("bersih" di tengah), memuat (kerangka); grid `items-start` (kartu tidak diregangkan).
- 5 baris per halaman kartu (`PAGE_ROWS = 5`); urutan kartu: berisi menurut `compareFilledQueues`, lalu kosong (Meja Keuangan tetap tidak menggambar kelompok kosong, MN-T2).
- Huruf hanya `text-fs-12 | text-fs-13 | text-fs-14 | text-fs-16 | text-fs-20`; minimum 12 px termasuk label kolom.
- Peran huruf (§5.5): judul kartu 14/600 (`text-fs-14 font-semibold`) · nomor dokumen 13/600 warna aksi (`text-fs-13 font-semibold text-kn-action`) · nama pihak 13/400 · nilai 13/600 · lencana & umur 12/500 (`font-medium`) · label kolom Pelacak 12/600 tanpa huruf besar · teks lain 12–13/400 · maks. dua unsur `font-semibold` per baris, tanpa `font-bold` di baris.
- Warna hanya token `kn-*` / `var(--kn-*)` di berkas meja yang disentuh.
- Kunci `sessionStorage`: kartu `kn.meja.kartu.<deskKey>:<queueId>` → `{q, st, sort, page}`; meja `kn.meja.<deskKey>` → `{tab, scrollY, returnPending}`; setiap baca/tulis dibungkus try/catch.
- `deskKey` / `testPrefix`: `sales_admin`/`desk`, `finance`/`fin-desk`, `md`/`md-desk`, `warehouse_admin`/`wh-desk`, `me`/`my-desk`, `sample_admin`/`sample-desk`.
- Antrean pantau (tab Pantau): `sales_admin` → `menunggu_manajer`; `sample_admin` → `di_gudang`, `kirim_ambil`, `selesai`; Pelacak SO di Pantau semua meja bila `can(perms,"order","view")`.
- Pesan hasil aksi: di dalam pop-up aksi (galat) atau `toast({ title })` dari `@/hooks/use-toast` (sukses); tidak ada `notice-bar` hasil aksi di puncak halaman.
- HP (§5.8): huruf ≥ 12 px, baris bisa disentuh → `DeskRowDetail` yang sama (layar penuh ≤ 640 px bawaan `DetailModal`), kartu HP tetap bisa dibuka-tutup.
- Di luar cakupan (gelombang 2–3): panel per jenis dokumen + aksinya, `decide_variance`/`issue_penalty` di tempat, rincian dokumen layar Keuangan (§5.7a), konversi token panel yang dipakai ulang (termasuk isi `VerifyOrderDialog`/`FulfillmentDecisionDialog`/`OrderPreviewCard`). Gelombang 1 hanya menyediakan registri `DESK_PANELS`.
- Uji hemat: uji terarah per tugas; `tests_mem` penuh + jest penuh sekali di Task 17; gate `--quick` sekali di Task 17 dibandingkan per pelanggaran dengan garis dasar Task 1 Step 0.
- Perintah uji backend: `cd /home/user/KNHOST/backend && /tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/venv/bin/python -m pytest tests_mem/<berkas> -q -p no:cacheprovider` (selanjutnya ditulis `$PYT tests_mem/<berkas>`).
- Perintah jest: `cd /home/user/KNHOST/frontend && (ulimit -s 65536; CI=true node --stack-size=16000 node_modules/@craco/craco/dist/scripts/test.js --watchAll=false <jalur>)` (selanjutnya `$JEST <jalur>`); plugin babel penyunting visual menyisipkan rentang `x-file-name` — cari elemen lewat `data-testid` dan periksa teks dengan `textContent` + `toContain`/`toMatch`, bukan kesamaan persis teks panjang.
- Penjaga UI (selanjutnya `$GUARD`): `cd /home/user/KNHOST && python3 scripts/guardrails/verify_custom_modals.py && python3 scripts/guardrails/verify_ui_standard.py && python3 scripts/guardrails/verify_detail_modal.py && python3 scripts/guardrails/verify_page_tabs.py && python3 scripts/guardrails/verify_desk_targets.py && python3 scripts/audit_create_modal.py`.
- Lebih dari satu agen bisa bekerja di repo: `git status` sebelum mulai tiap tugas dan sebelum commit; jangan menyunting berkas yang sedang diubah agen lain.

## Review Focus

1. **Klik/Enter pada elemen interaktif di dalam baris** — tombol aksi, tautan kartu pelanggan (`_titleNode`), atau Enter pada tombol aksi tidak boleh ikut membuka pop-up baris (dan aksi tidak terpanggil dua kali). → uji pengunci di Task 5.
2. **Tinggi kartu tetap di semua keadaan** — memuat tanpa baris, kerangka, kosong, 1 baris, 5 baris, dan saat catatan "n tertua dari m" / "Memuat ulang…" tampil (keduanya di kaki tetap, bukan baris tambahan). → Task 5.
3. **Mode "Semua PT"** — baris menyebut PT pendek hanya di mode Semua PT; pop-up selalu menyebut PT; baris tanpa `entity_id` (atau PT tak dikenal) tidak menulis "tidak dikenal". → Task 5 (baris) dan Task 4 (pop-up).
4. **Kembali dari "Buka layar penuh"** — cari/saring/urut/halaman kartu pulih walau baris baru tiba sesudah render pertama (halaman tidak direset ke 1 oleh daftar kosong saat memuat); tab Antrean/Pantau pulih; posisi gulir pulih hanya bila keluar lewat navigasi meja. → Task 5 (kartu) dan Task 6 (tab, gulir).
5. **Hapus ganda berpagar izin** — baris lewat tempo pindah ke kartu Piutang hanya bila kartu itu terlihat; "Terima pembayaran" di pop-up Piutang hanya bila kartu Uang masuk terlihat; jumlah/nilai/umur kartu Uang masuk dihitung ulang; "Giliran saya" yang habis dihapus ganda tetap tampil sebagai kartu kosong berukuran tetap. → Task 13.

---

## File Structure

**Backend**
- `backend/services/work_desk_service.py` — kontrak baris `_row` (`entity_id`, `age_kind`), teks utuh, `at` nyata, isian aksi di tempat (`_lines_of`, `_order_lines_by_id`, `_so_extra`), jenis aksi `print`/`create_qc_spk`, nama "Meja Keuangan".
- `backend/services/role_desk_service.py` — `entity_id` di baris, teks utuh, `so_acc` tanpa pesanan sample, "Giliran saya" manajer/admin tanpa pesanan sample.
- `backend/services/so_tracker_service.py` — SOS memakai `sample_next_step` di semua meja; baris membawa `order_type`, `entity_id`.
- `backend/services/customer_service.py` — baris `collection_worklist` membawa `entity_id`.
- `backend/routers/sample_orders.py` — baris meja sample: `entity_id`, `at`, semua barang, isian bayar & `order_lines`, nama "Meja Sample"/"Meja Keuangan".
- `backend/role_registry.py`, `backend/services/dispatch_payment_gate.py`, `backend/config_catalog_core.py` — nama tunggal di teks yang tampil.
- Uji: `backend/tests_mem/test_MEJA1_baris_meja.py`, `test_MEJA2_sample_bukan_giliran_manajer.py`, `test_MEJA3_isian_aksi_di_tempat.py`, `test_MEJA8_nama_meja.py`; penyesuaian `test_PRT4_sifat_peran.py`.

**Frontend — kerangka bersama (baru)**
- `frontend/src/features/desks/deskPanels.js` — registri `ref_type → komponen panel` (kosong).
- `frontend/src/features/desks/DeskRowDetail.jsx` — pop-up rincian baris (`DetailModal`) + panel umum.
- `frontend/src/features/desks/deskSession.js` — status kartu/meja di `sessionStorage`, pemulihan gulir.
- `frontend/src/features/desks/DeskFrame.jsx` — tab Antrean/Pantau, ? halaman, sinyal muat ulang, gulir.
- `frontend/src/features/desks/deskDedupe.js` — hapus ganda Keuangan & Giliran saya.
- `frontend/src/context/PageHelpContext.jsx` — isi ikon ? di samping judul `TopBar`.
- `frontend/src/utils/refreshSignal.js` — peristiwa muat ulang global.
- `frontend/src/features/finance/TaxIssueDialog.jsx` — pop-up "Terbitkan" faktur pajak bersama.
- `frontend/src/features/sales_admin/ReleaseToWarehouseDialog.jsx` — pratinjau + konfirmasi lepas/teruskan ke gudang.
- `frontend/src/features/samples/samplePayment.js` — pemeriksaan uang masuk sample (satu fungsi).
- `frontend/src/features/samples/SamplePaymentApproveDialog.jsx` — pratinjau + konfirmasi setujui bayar sample.
- `frontend/src/features/documents/orderPrintDocs.js` — daftar dokumen cetak pesanan (satu sumber).
- `frontend/src/features/documents/OrderPrintModal.jsx` — pop-up cetak SJ/Invoice pesanan.
- `frontend/src/features/samples/CuttingReceiveDialog.jsx` — terima hasil potong (lokasi + satu/semua baris).

**Frontend — diubah**
- `features/sales_admin/DeskQueueCard.jsx` (kartu tetap + baris ringkas + rincian), `workDeskApi.js` (token, `ageText`, `soTrackerLink` sample, `issueTaxInvoice(body)`), `deskQueueOrder.js` (`orderDeskQueues`, `splitPantau`), `components/TableFilter.jsx` (`initial`, tinggi kontrol sama).
- Meja: `features/sales_admin/SalesAdminDesk.jsx`, `features/finance/FinanceDesk.jsx`, `features/desks/RoleDesk.jsx`, `features/samples/SampleAdminDesk.jsx`, `features/samples/CuttingDesk.jsx`, `AppViewRouter.jsx`, `App.js`, `components/CoreWidgets.jsx`.
- Pantau: `features/sales_admin/SoTrackerCard.jsx`, `KeepPendingPanel.jsx`, `CustomerGradeRulesCard.jsx`, `features/home/ReturnDeskSummaryCard.jsx`.
- Layar asal konfirmasi: `features/finance/TaxInvoices.jsx`, `features/orders/OrderDetailPanel.jsx`, `features/samples/SampleOrdersView.jsx`, `features/sales/mobile/MobileOrders.jsx`.
- Dialog ke `FormModal`: `features/sales_admin/VerifyOrderDialog.jsx`, `FulfillmentDecisionDialog.jsx`.
- SPK QC: `features/inspections/InspectionFormModal.jsx`.
- Nama: `config/navMeta.js`, `config/hubTabs.js`, `features/mobile/MobileRoleSummary.jsx`.
- HP: `features/sales/mobile/MobileSalesAdminDesk.jsx`, `features/sales/mobile/MobileMdViews.jsx` (fungsi `MobileMdDesk`).
- Standar: `docs/blueprint/04_POLA_UI.md`.
- Uji baru: `frontend/src/features/__tests__/meja*.test.js` (per tugas).

**Hasil**: `docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/` (log gate, `tangkap_meja.py`, tangkapan) dan
`docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil.md` (laporan).

---

### Task 1: Server — kontrak baris meja (PT, waktu masuk nyata, teks utuh)

**Files:**
- Modify: `backend/services/work_desk_service.py` (`_row` :106-116; semua pemanggil `_row`; pemotongan :264, :352, :747, :799, :863, :958 (`_delivery_subtitle`), :1004; `at` di :282 jatuh tempo Admin Sales, :474 uang masuk, :549 jatuh tempo Keuangan, :579 hutang)
- Modify: `backend/services/role_desk_service.py` (semua pemanggil `_row`; pemotongan :235 brief, :299 alasan eskalasi)
- Modify: `backend/routers/sample_orders.py` (`_rows` :136-149: semua barang, `at`, `entity_id`)
- Modify: `backend/services/customer_service.py` (`collection_worklist`: baris membawa `"entity_id": o.get("entity_id", "")`)
- Test: `backend/tests_mem/test_MEJA1_baris_meja.py`

**Interfaces:**
- Produces: `_row(*, ref_type, ref_id, number, title, subtitle="", value=0.0, age_days=0, badge="", action="", action_kind="open", extra=None, at="", entity_id: str = "", age_kind: str = "wait") -> Dict` — keluaran selalu memuat `"entity_id"` dan `"age_kind"` (`"wait"` | `"overdue"`); `"at"` hanya bila ada.
- Produces: aturan `at`/`age_kind` — baris lewat jatuh tempo (`jatuh_tempo` kedua meja, `uang_masuk` dengan `overdue`, `hutang_jatuh_tempo` dengan `late > 0`): `at` = tanggal jatuh tempo (`due_date` / `payment_due_date`), `age_kind="overdue"`, `age_days` = hari telat; baris tagihan belum lewat tempo dan tunai belum dicatat: tanpa `at`, `age_kind="wait"`; baris sample: `at = updated_at or created_at`.
- Produces: setiap pemanggil `_row` di tiga berkas memberi kata kunci `entity_id=` **dan** `at=` (nilai kosong `""` bila memang tidak ada waktu nyata).
- Produces: `collection_worklist` baris + `"entity_id"`.

- [ ] **Step 0: Garis dasar (sekali, sebelum perubahan apa pun)**

```bash
cd /home/user/KNHOST && git status --short && git rev-parse --short HEAD   # catat sebagai <awal> di laporan
mkdir -p docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil
bash scripts/gate.sh --quick > docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/gate_awal.log 2>&1; \
  git checkout -- memory/GATE_RECEIPT.md memory/GATE_RECEIPT.json
git diff --stat db0a20f HEAD -- frontend/src/features/sales_admin frontend/src/features/desks \
  frontend/src/features/finance/FinanceDesk.jsx frontend/src/features/samples frontend/src/features/sales/mobile \
  backend/services/work_desk_service.py backend/services/role_desk_service.py backend/routers/sample_orders.py
```
Gate berjalan di latar bila > 5 menit. Bila `git diff --stat` kosong, tangkapan audit `docs/audit/meja-2026-11-25/tangkapan/01–10`
dipakai sebagai "sebelum" di laporan; bila tidak kosong, catat commit yang mengubah berkas meja di laporan.

- [ ] **Step 1: Tulis uji gagal** `backend/tests_mem/test_MEJA1_baris_meja.py`:

```python
"""MEJA-1 — kontrak baris meja (rancangan meja-kerja-di-tempat §5.6): entity_id, age_kind, at nyata, teks utuh."""
from __future__ import annotations
import ast, inspect, re
from pathlib import Path
import pytest
from core_utils import now_iso

pytestmark = pytest.mark.anyio
ROOT = Path(__file__).resolve().parents[1]
BERKAS = ["services/work_desk_service.py", "services/role_desk_service.py", "routers/sample_orders.py"]
PANJANG = "Butuh kain untuk pesanan pelanggan besar di Medan — " * 3   # ±150 huruf


def test_row_membawa_entity_id_dan_age_kind():
    from services.work_desk_service import _row
    r = _row(ref_type="x", ref_id="1", number="N", title="T", entity_id="ent_ksc", age_kind="overdue")
    assert r["entity_id"] == "ent_ksc" and r["age_kind"] == "overdue"
    d = _row(ref_type="x", ref_id="1", number="N", title="T")
    assert d["entity_id"] == "" and d["age_kind"] == "wait" and "at" not in d


@pytest.mark.parametrize("rel", BERKAS)
def test_setiap_row_memberi_entity_id_dan_at(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    kurang = [(n.lineno, k) for n in ast.walk(tree)
              if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_row"
              for k in ("entity_id", "at") if k not in {kw.arg for kw in n.keywords}]
    assert kurang == []


def test_server_tidak_memotong_teks():
    wd = (ROOT / "services/work_desk_service.py").read_text(encoding="utf-8")
    rd = (ROOT / "services/role_desk_service.py").read_text(encoding="utf-8")
    assert set(re.findall(r"\[:(\d+)\]", wd)) <= {"10"}      # hanya potong tanggal ISO
    assert set(re.findall(r"\[:(\d+)\]", rd)) <= {"2"}       # hanya pecah `koleksi:id`
    from routers import sample_orders
    assert "[:" not in inspect.getsource(sample_orders._rows)


def test_collection_worklist_membawa_entity_id():
    from services import customer_service
    assert '"entity_id": o.get("entity_id"' in inspect.getsource(customer_service.collection_worklist)


async def test_alasan_permintaan_internal_utuh(klien, db, kepala_admin):
    await db.internal_requests.insert_one({"id": "pin_meja1", "number": "PIN-MEJA1", "reason": PANJANG,
                                           "status": "submitted", "entity_id": "ent_ksc", "created_at": now_iso(), "items": []})
    r = await klien.get("/api/sales-admin/desk", headers=kepala_admin)
    assert r.status_code == 200, r.text
    q = next(q for q in r.json()["queues"] if q["id"] == "permintaan_internal")
    row = next(x for x in q["rows"] if x["ref_id"] == "pin_meja1")
    assert row["title"] == PANJANG and row["entity_id"] == "ent_ksc"


async def test_barang_kurang_semua_baris(klien, kepala_admin, monkeypatch):
    async def papan(scope):
        return [{"order_id": "so_kurang", "order_number": "SO-KURANG", "customer_name": "Toko K", "created_at": now_iso(),
                 "coverage": "uncovered", "product_name": f"Kain {i}", "backorder_qty": 5, "unit": "yard"} for i in (1, 2, 3)]
    monkeypatch.setattr("services.stock_bucket_service.pending_so_board", papan)
    r = await klien.get("/api/sales-admin/desk", headers=kepala_admin)
    row = next(x for q in r.json()["queues"] if q["id"] == "perlu_dipenuhi" for x in q["rows"] if x["ref_id"] == "so_kurang")
    for i in (1, 2, 3):
        assert f"Kain {i} kurang 5 yard" in row["subtitle"]


async def test_jatuh_tempo_at_nyata_dan_lewat(klien, kepala_admin, monkeypatch):
    async def tagih(actor, days_ahead=30, sales_id=None, entity_id=None):
        return [{"order_id": "so_jt", "order_number": "SO-JT", "customer_id": "cus_jt", "customer_name": "Toko JT",
                 "outstanding": 500000, "days_late": 8, "overdue": True, "due_date": "2026-11-17", "sales_name": "Ayu",
                 "entity_id": "ent_ksc"},
                {"order_id": "so_nanti", "order_number": "SO-NANTI", "customer_id": "cus_jt", "customer_name": "Toko JT",
                 "outstanding": 100000, "days_late": -3, "overdue": False, "due_date": "2026-11-28", "sales_name": "Ayu",
                 "entity_id": "ent_ksc"}]
    monkeypatch.setattr("services.customer_service.collection_reminders", tagih)
    fin = (await klien.get("/api/finance/desk", headers=kepala_admin)).json()["queues"]
    jt = next(x for q in fin if q["id"] == "jatuh_tempo" for x in q["rows"] if x["ref_id"] == "so_jt")
    assert jt["at"].startswith("2026-11-17") and jt["age_kind"] == "overdue" and jt["age_days"] == 8
    assert jt["entity_id"] == "ent_ksc"
    um = {x["order_id"]: x for q in fin if q["id"] == "uang_masuk" for x in q["rows"]}
    assert um["so_jt"]["age_kind"] == "overdue" and um["so_jt"]["at"].startswith("2026-11-17")
    assert um["so_nanti"]["age_kind"] == "wait" and um["so_nanti"].get("at", "") == ""
    sa = (await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json()["queues"]
    sajt = next(x for q in sa if q["id"] == "jatuh_tempo" for x in q["rows"] if x["ref_id"] == "so_jt")
    assert sajt["age_kind"] == "overdue" and sajt["at"].startswith("2026-11-17")


async def test_baris_sample_semua_barang_dan_at(klien, db, kepala_admin):
    t = now_iso()
    await db.sales_orders.insert_one({
        "id": "sos_meja1", "number": "KSC/SOS-M1", "order_type": "sample", "status": "approved", "sample_billing": "free",
        "grand_total": 0, "customer_name": "Toko Sample", "entity_id": "ent_ksc", "created_at": t, "updated_at": t,
        "items": [{"product_id": f"p{i}", "product_name": f"Sample {i}", "quantity": 1, "unit": "meter"} for i in range(1, 5)]})
    r = await klien.get("/api/sample-orders/desk", headers=kepala_admin)
    row = next(x for q in r.json()["queues"] if q["id"] == "siap_gudang" for x in q["rows"] if x["ref_id"] == "sos_meja1")
    assert all(f"Sample {i}" in row["subtitle"] for i in range(1, 5))
    assert row["at"] == t and row["entity_id"] == "ent_ksc"
```

- [ ] **Step 2: Jalankan, harus GAGAL**

Run: `$PYT tests_mem/test_MEJA1_baris_meja.py`
Expected: FAIL (`KeyError: 'entity_id'`, daftar `kurang` tidak kosong, `[:70]` masih ada, `Kain 3` tidak ada di subjudul).

- [ ] **Step 3: Terapkan**
  - `_row`: tambah kata kunci `entity_id: str = ""` dan `age_kind: str = "wait"`; tulis keduanya ke keluaran sebelum `**(extra or {})`.
  - Semua pemanggil `_row` (56 di tiga berkas): `entity_id=<dokumen>.get("entity_id", "")`; tambahkan `"entity_id": 1` ke proyeksi kueri yang belum memuatnya (mis. `pin`, `ret`, `denda`, `sos`, desain, sample MD, PR, makloon, SJ, tugas WMS, notifikasi giliran memakai `n.get("entity_id", "")`); baris `uang_masuk`/`jatuh_tempo` memakai `r.get("entity_id", "")` dari `collection_reminders` (sumbernya `collection_worklist` yang kini membawa `entity_id`); baris tunai belum dicatat memakai `o.get("entity_id", "")` (tambah ke proyeksi kueri tunai).
  - Hapus pemotongan: `r.get("reason") or "—"` (:352), `r.get("brief") or ""` (:747), `" · ".join(...)` tanpa `[:110]` (:799, :863, `_delivery_subtitle`), subjudul SJ tanpa `[:80]` (:1004), `d.get("customer_name") or d.get("brief") or ""` (role :235), alasan eskalasi tanpa `[:80]` (role :299), `v["lines"]` tanpa `[:2]` (:264), `items` tanpa `[:3]` (`sample_orders._rows`).
  - `at`/`age_kind` sesuai Interfaces di :282, :474 (tunai/belum lewat tempo `at=""`), :549, :579 (`at=p["payment_due_date"] if late > 0 else ""`), `sample_orders._rows` (`at=o.get("updated_at") or o.get("created_at") or ""`).
  - `collection_worklist`: tambah `"entity_id": o.get("entity_id", "")` di dict baris.

- [ ] **Step 4: Jalankan, harus LULUS** — `$PYT tests_mem/test_MEJA1_baris_meja.py` → PASS. Regresi terarah:
  `$PYT tests_mem/test_masukan16Nov_fungsi.py tests_mem/test_KFIN01_finance_setara_manajer.py tests_mem/test_latih_keuangan_bagian_d.py tests_mem/test_TXT2_pemicu_faktur.py tests_mem/test_PRT4_sapuan.py` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/work_desk_service.py backend/services/role_desk_service.py backend/routers/sample_orders.py \
  backend/services/customer_service.py backend/tests_mem/test_MEJA1_baris_meja.py \
  docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/gate_awal.log
git commit -m "feat(meja): baris meja membawa PT, waktu masuk nyata, umur lewat tempo, dan teks utuh"
```

---

### Task 2: Server — pesanan sample bukan giliran manajer; Pelacak SO memakai tahap sample

**Files:**
- Modify: `backend/services/so_tracker_service.py` (`so_tracker` :98-124: filter `order_type`, `sample_next_step` per baris, baris + `order_type`, `entity_id`)
- Modify: `backend/services/role_desk_service.py` (`manager_queues` :90: `so` tanpa sample; `_turn_queue` :43; `role_desk` :315)
- Test: `backend/tests_mem/test_MEJA2_sample_bukan_giliran_manajer.py`

**Interfaces:**
- Produces: `so_tracker(desk, actor, scope)` — meja `sample_admin` menyaring `{"order_type": "sample"}`; meja lain memuat SO biasa **dan** SOS; tahap baris = `sample_next_step(o)` bila `o.order_type == "sample"`, selain itu `next_step(o, hold)`; baris + `"order_type": o.get("order_type") or "regular"`, `"entity_id": o.get("entity_id", "")` (proyeksi + `order_type`).
- Produces: `_turn_queue(actor, *, skip_sample_orders: bool = False)` — bila benar, baris giliran berkoleksi `sales_orders` yang dokumennya `order_type == "sample"` dilewati; `role_desk` memanggilnya dengan `skip_sample_orders=role in ("manager", "admin")`.
- Produces: `manager_queues` — kueri `so` = `{**sq, "status": "waiting_approval", "order_type": {"$ne": "sample"}}`.

- [ ] **Step 1: Tulis uji gagal** `backend/tests_mem/test_MEJA2_sample_bukan_giliran_manajer.py`:

```python
"""MEJA-2 — §5.6: SOS tidak tampil sebagai giliran manajer; Pelacak SO memakai sample_next_step untuk SOS."""
from __future__ import annotations
import pytest
from core_utils import now_iso

pytestmark = pytest.mark.anyio


async def _dua_pesanan(db, akhir: str):
    t = now_iso()
    so = {"id": f"so_m2{akhir}", "number": f"SO-M2{akhir}", "status": "waiting_approval", "entity_id": "ent_ksc",
          "grand_total": 1000, "customer_name": "Toko Biasa", "created_at": t, "updated_at": t, "items": []}
    sos = {"id": f"sos_m2{akhir}", "number": f"KSC/SOS-M2{akhir}", "status": "waiting_approval", "order_type": "sample",
           "sample_billing": "paid", "entity_id": "ent_ksc", "grand_total": 83250, "customer_name": "Toko Sample",
           "created_at": t, "updated_at": t, "items": []}
    await db.sales_orders.insert_many([dict(so), dict(sos)])
    return so, sos


async def test_pelacak_sos_tahap_sample(klien, db, kepala_admin):
    so, sos = await _dua_pesanan(db, "a")
    rows = (await klien.get("/api/desks/so-tracker", headers=kepala_admin, params={"desk": "sales_admin"})).json()["rows"]
    s = next(r for r in rows if r["id"] == sos["id"])
    assert s["next_step"] == "Persetujuan pembayaran sample" and s["order_type"] == "sample"
    assert s["entity_id"] == "ent_ksc"
    assert next(r for r in rows if r["id"] == so["id"])["order_type"] == "regular"
    smp = (await klien.get("/api/desks/so-tracker", headers=kepala_admin, params={"desk": "sample_admin"})).json()["rows"]
    ids = {r["id"] for r in smp}
    assert sos["id"] in ids and so["id"] not in ids


async def test_meja_manajer_tanpa_pesanan_sample(klien, db, akun, sesi):
    so, sos = await _dua_pesanan(db, "b")
    mgr = await akun("manager")
    for doc in (so, sos):
        await db.notifications.insert_one({
            "id": f"ntf_{doc['id']}", "recipient_user": mgr["id"], "type": "turn", "read": False,
            "ref": f"turn:sales_orders:{doc['id']}:waiting_approval#{mgr['id']}", "action_id": f"sales_orders:{doc['id']}",
            "title": f"Giliran Anda — Setujui pesanan: {doc['number']}", "created_at": now_iso(), "severity": "info"})
    qs = {q["id"]: q for q in (await klien.get("/api/desks/me", headers=await sesi(mgr))).json()["queues"]}
    assert {r["ref_id"] for r in qs["so_acc"]["rows"]} >= {so["id"]}
    assert sos["id"] not in {r["ref_id"] for r in qs["so_acc"]["rows"]}
    giliran = {r["ref_id"] for r in qs["giliran_saya"]["rows"]}
    assert so["id"] in giliran and sos["id"] not in giliran


async def test_turn_queue_bawaan_tidak_menyaring(db, akun):
    from services.role_desk_service import _turn_queue
    _, sos = await _dua_pesanan(db, "c")
    u = await akun("sales")
    await db.notifications.insert_one({
        "id": f"ntf_sales_{sos['id']}", "recipient_user": u["id"], "type": "turn", "read": False,
        "ref": f"turn:sales_orders:{sos['id']}:waiting_approval#{u['id']}", "action_id": f"sales_orders:{sos['id']}",
        "title": "Giliran Anda — Uji: X", "created_at": now_iso(), "severity": "info"})
    assert sos["id"] in {r["ref_id"] for r in (await _turn_queue(u))["rows"]}
    assert sos["id"] not in {r["ref_id"] for r in (await _turn_queue(u, skip_sample_orders=True))["rows"]}
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$PYT tests_mem/test_MEJA2_sample_bukan_giliran_manajer.py` → FAIL
  (`next_step` = "Diputuskan Manajer", `KeyError: 'order_type'`, SOS ada di `so_acc`, `TypeError` kata kunci `skip_sample_orders`).

- [ ] **Step 3: Terapkan** sesuai Interfaces. `_turn_queue`: saat mengisi `now_status` untuk koleksi `sales_orders`,
  proyeksikan juga `order_type` dan kumpulkan id SOS; lewati baris SOS bila `skip_sample_orders`.

- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji di atas PASS; regresi `$PYT tests_mem/test_masukan16Nov_fungsi.py tests_mem/test_KFIN01_finance_setara_manajer.py tests_mem/test_PRT4_sapuan.py` PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/services/so_tracker_service.py backend/services/role_desk_service.py \
  backend/tests_mem/test_MEJA2_sample_bukan_giliran_manajer.py
git commit -m "fix(meja): pesanan sample tidak lagi giliran manajer; Pelacak SO memakai tahap sample"
```

---

### Task 3: Server — isian baris untuk aksi di tempat dan pop-up

**Files:**
- Modify: `backend/services/work_desk_service.py` (helper baru; `sales_admin_desk` antrean SO; `finance_desk` `siap_faktur_pajak`; `warehouse_admin_desk` `qc_pesanan`; `_orders` proyeksi + `"dpp": 1, "customer_id": 1`)
- Modify: `backend/services/role_desk_service.py` (`_so_rows`: `extra=_so_extra(o)`)
- Modify: `backend/routers/sample_orders.py` (`_rows` extra)
- Test: `backend/tests_mem/test_MEJA3_isian_aksi_di_tempat.py`

**Interfaces:**
- Produces (`work_desk_service`):
  - `_lines_of(order: Dict) -> List[Dict]` → per barang `{"product_name", "sku", "quantity": float, "unit", "warehouse": str}`; `warehouse` = nama gudang unik (urutan muncul) dari `item.allocations[].warehouse_name` + `item.warehouse_name`, digabung `", "`; kosong bila tak ada.
  - `async _order_lines_by_id(order_ids: List[str]) -> Dict[str, List[Dict]]` — satu kueri `sales_orders` (`id`, `items`) lalu `_lines_of`.
  - `_so_extra(o: Dict) -> Dict` → `{"sales_name": o.get("sales_name") or "", "customer_city": o.get("customer_city") or "", "booking_until": o.get("reservation_expires_at") or ""}`.
- Produces (isian baris):
  - Admin Sales `perlu_verifikasi`, `siap_dikonfirmasi`, `menunggu_manajer`, `siap_cetak_dokumen`, `harga_ditolak`: `extra` ⊇ `_so_extra(o)`; `siap_dikonfirmasi` + `"order_lines"`; `siap_cetak_dokumen` `action_kind="print"`.
  - Meja Saya `_so_rows`: `extra=_so_extra(o)`.
  - Keuangan `siap_faktur_pajak`: `extra={"ppn_amount": float, "dpp": float|None (o.get("dpp")), "customer_id", "customer_npwp": npwp pelanggan dari koleksi customers ("" bila tidak ada)}`.
  - Gudang `qc_pesanan`: `action_kind="create_qc_spk"` (tetap `extra.link_view="inspections"` untuk "Buka layar penuh").
  - Sample `_rows`: `extra` + `{"sample_billing", "grand_total": float, "paid_total": float, "sample_payment_status", "order_lines": _lines_of(o)}`.

- [ ] **Step 1: Tulis uji gagal** `backend/tests_mem/test_MEJA3_isian_aksi_di_tempat.py`:

```python
"""MEJA-3 — isian baris untuk pratinjau konfirmasi & pop-up (§5.3, §5.4, §5.6)."""
from __future__ import annotations
import pytest
from core_utils import now_iso

pytestmark = pytest.mark.anyio


def _baris(desk_json, qid, ref_id):
    return next(x for q in desk_json["queues"] if q["id"] == qid for x in q["rows"] if x["ref_id"] == ref_id)


async def test_ditahan_membawa_baris_dan_gudang(klien, db, kepala_admin):
    t = now_iso()
    await db.sales_orders.insert_one({
        "id": "so_m3_hold", "number": "SO-M3H", "status": "approved", "entity_id": "ent_ksc", "customer_name": "Toko H",
        "customer_city": "Bandung", "sales_name": "Ayu", "reservation_expires_at": "2026-11-30T10:00:00+00:00",
        "grand_total": 250000, "created_at": t, "release": {"requested": True, "hold": True, "by": "Admin"},
        "items": [{"product_id": "p1", "product_name": "Kain A", "sku": "KA-1", "quantity": 10, "unit": "yard",
                   "allocations": [{"warehouse_name": "Gudang Woven"}, {"warehouse_name": "Gudang Knit"}]}]})
    row = _baris((await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json(), "siap_dikonfirmasi", "so_m3_hold")
    assert row["order_lines"] == [{"product_name": "Kain A", "sku": "KA-1", "quantity": 10.0, "unit": "yard",
                                   "warehouse": "Gudang Woven, Gudang Knit"}]
    assert (row["sales_name"], row["customer_city"], row["booking_until"]) == ("Ayu", "Bandung", "2026-11-30T10:00:00+00:00")


async def test_siap_cetak_aksi_print(klien, db, kepala_admin):
    await db.sales_orders.insert_one({"id": "so_m3_cetak", "number": "SO-M3C", "status": "confirmed", "entity_id": "ent_ksc",
                                      "customer_name": "Toko C", "grand_total": 1, "created_at": now_iso(), "items": []})
    row = _baris((await klien.get("/api/sales-admin/desk", headers=kepala_admin)).json(), "siap_cetak_dokumen", "so_m3_cetak")
    assert row["action_kind"] == "print"


async def test_faktur_pajak_membawa_ppn_dpp_npwp(klien, db, kepala_admin):
    await db.customers.insert_one({"id": "cus_m3", "name": "Toko Pajak", "npwp": "01.234.567.8-901.000", "entity_id": "ent_ksc"})
    await db.sales_orders.insert_one({
        "id": "so_m3_pajak", "number": "SO-M3P", "status": "confirmed", "entity_id": "ent_ksc", "customer_id": "cus_m3",
        "customer_name": "Toko Pajak", "is_pkp": True, "ppn_amount": 110000, "dpp": 1000000, "grand_total": 1110000,
        "created_at": now_iso(), "items": []})
    row = _baris((await klien.get("/api/finance/desk", headers=kepala_admin)).json(), "siap_faktur_pajak", "so_m3_pajak")
    assert (row["ppn_amount"], row["dpp"], row["customer_npwp"]) == (110000.0, 1000000.0, "01.234.567.8-901.000")


async def test_qc_pesanan_aksi_spk_di_tempat(klien, db, kepala_admin):
    await db.sales_orders.insert_one({"id": "so_m3_qc", "number": "SO-M3Q", "status": "confirmed", "entity_id": "ent_ksc",
                                      "customer_name": "Toko Q", "qc_request": {"mode": "full", "status": "requested"},
                                      "created_at": now_iso(), "items": []})
    row = _baris((await klien.get("/api/warehouse-admin/desk", headers=kepala_admin)).json(), "qc_pesanan", "so_m3_qc")
    assert row["action_kind"] == "create_qc_spk" and row["link_view"] == "inspections"


async def test_sample_bayar_membawa_uang_masuk(klien, db, kepala_admin):
    t = now_iso()
    await db.sales_orders.insert_one({
        "id": "sos_m3", "number": "KSC/SOS-M3", "order_type": "sample", "status": "waiting_approval", "sample_billing": "paid",
        "grand_total": 83250, "paid_total": 50000, "entity_id": "ent_ksc", "customer_name": "Toko S", "created_at": t,
        "updated_at": t, "items": [{"product_id": "p1", "product_name": "Sample A", "sku": "SA", "quantity": 1, "unit": "meter"}]})
    row = _baris((await klien.get("/api/sample-orders/desk", headers=kepala_admin)).json(), "bayar_sampel", "sos_m3")
    assert (row["sample_billing"], row["grand_total"], row["paid_total"]) == ("paid", 83250.0, 50000.0)
    assert row["order_lines"][0]["product_name"] == "Sample A"
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$PYT tests_mem/test_MEJA3_isian_aksi_di_tempat.py` → FAIL (`KeyError: 'order_lines'`, `action_kind == "open"`, …).
- [ ] **Step 3: Terapkan** sesuai Interfaces (npwp: satu kueri `db.customers.find({"id": {"$in": [...]}}, {"_id": 0, "id": 1, "npwp": 1})` untuk kandidat faktur).
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$PYT tests_mem/test_MEJA1_baris_meja.py tests_mem/test_TXT2_pemicu_faktur.py tests_mem/test_masukan16Nov_fungsi.py` PASS.
- [ ] **Step 5: Commit**

```bash
git add backend/services/work_desk_service.py backend/services/role_desk_service.py backend/routers/sample_orders.py \
  backend/tests_mem/test_MEJA3_isian_aksi_di_tempat.py
git commit -m "feat(meja): baris membawa isian pratinjau aksi (barang & gudang, pajak, uang masuk sample, cetak, SPK QC)"
```

---

### Task 4: Pop-up rincian umum `DeskRowDetail` + registri panel

**Files:**
- Create: `frontend/src/features/desks/deskPanels.js`
- Create: `frontend/src/features/desks/DeskRowDetail.jsx`
- Modify: `frontend/src/features/sales_admin/workDeskApi.js` (tambah `ageText`)
- Test: `frontend/src/features/__tests__/mejaDeskRowDetail.test.js`

**Interfaces:**
- Produces `deskPanels.js`: `export const DESK_PANELS = {}` (kosong; gelombang 2–3 mengisi `ref_type → Komponen`); `export function panelFor(refType) → Komponen | null`. Kontrak props panel: `{ row, queue, onAction(row, queue), onClose(), onOpenFull(row, queue) }`.
- Produces `workDeskApi.ageText(row) → string`: `age_kind === "overdue"` → `` `lewat ${d} hari` `` (d = 0 → `"jatuh tempo hari ini"`); selain itu `ageTone(row.age_days).label` (`"8 hari"`, `"< 1 hari"`).
- Produces `DeskRowDetail({ row, queue, testPrefix = "desk", inPlace = () => false, onAction, onOpenFull, onClose })`:
  - cangkang `<DetailModal framed size="md" testId={`${testPrefix}-detail`} label={`Rincian ${row.number}`} onClose>`;
  - judul `${p}-detail-title` = `` `${row.number} · ${row.title}` `` (`text-fs-16 font-semibold`); subjudul `${p}-detail-subtitle` = [PT pendek, `badgeLabel(badge)`, `ageText(row)`] yang ada, digabung `" · "`;
  - isi: `panelFor(row.ref_type)` bila ada (dirender dengan kontrak di atas), selain itu panel umum: `<dl>` dengan `data-testid={`${p}-detail-field-${key}`}` untuk kunci berisi saja, urutan: `subtitle` "Keterangan" (utuh, `whitespace-pre-line break-words`), `badge` "Status", `entity_id` "PT", `value` (`queue.value_label || "Nilai"`; rupiah / qty+satuan / tidak ada untuk `count`), `age` ("Menunggu" | "Lewat jatuh tempo"), `at` ("Masuk" | "Jatuh tempo" bila `age_kind === "overdue"`; `fmtWhen`), `sales_name` "Sales", `customer_city` "Kota", `booking_until` "Batas cadangan" (`formatDateTime`), `payment_due_date` "Jatuh tempo bayar" (`formatDate`), `order_number` "Pesanan", `fulfillment_method` "Cara terima" (`kirim`→"Dikirim", `ambil`→"Diambil"); tabel `order_lines` (`${p}-detail-lines`, baris `${p}-detail-line-${i}`: barang · SKU, qty satuan, gudang) dan tabel `lines` "Barang kurang" (`product_name`, `backorder_qty` `unit`) — semua baris, tanpa potong; isian `extra` lain tidak ditampilkan;
  - kaki: tombol aksi `${p}-detail-action` (`primary-button btn-sm`) hanya bila `row.action`; bila `!inPlace(row)` berikon `ExternalLink` `data-testid={`${p}-detail-action-nav`}` + `title="Pindah ke layar lain"`; klik → `onClose(); onAction(row, queue)`. Untuk tiap `row._moreActions[i] = { label, row: baris }`: tombol `${p}-detail-action-${i}` (`secondary-button btn-sm`) → `onClose(); onAction(a.row, queue)`. Tautan sekunder `${p}-detail-open-full` "Buka layar penuh" (`link-button`) bila `onOpenFull` → `onClose(); onOpenFull(row, queue)`;
  - PT: `entityShortById(useEntityScope().entities, row.entity_id, "")`; kosong → bidang PT tidak dirender.
  - Lencana status memakai `DeskBadge` (Task 5) — sampai Task 5 ada, render teks `badgeLabel` biasa; Task 5 menggantinya.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaDeskRowDetail.test.js`:

```javascript
// MEJA-4 — pop-up rincian umum (§5.3): teks utuh, PT, waktu nyata, registri panel, aksi & "Buka layar penuh".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import DeskRowDetail from "../desks/DeskRowDetail";
import { DESK_PANELS } from "../desks/deskPanels";
import { ageText } from "../sales_admin/workDeskApi";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
afterEach(async () => { for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = ""; });
const ENTS = [{ id: "ent_ksc", short_name: "KSC" }];
const PANJANG = "Pelanggan minta kirim Senin pagi, alamat gudang baru di Jl. Raya Bandung no. 17, hubungi Pak Ujang dulu. ".repeat(2);
const ROW = { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko A", subtitle: PANJANG, badge: "reserved",
  value: 1500000, age_days: 4, age_kind: "wait", at: "2026-11-20T03:00:00Z", entity_id: "ent_ksc", sales_name: "Ayu",
  booking_until: "2026-11-30T10:00:00Z", action: "Follow-up", action_kind: "open",
  order_lines: [{ product_name: "Kain A", sku: "KA-1", quantity: 10, unit: "yard", warehouse: "Gudang Woven" },
                { product_name: "Kain B", sku: "KB-1", quantity: 5, unit: "yard", warehouse: "" }] };
const QUEUE = { id: "jatuh_tempo", label: "Jatuh tempo", value_label: "Sisa tagihan" };
const wrap = (el) => <EntityScopeProvider selectedEntity="all" entities={ENTS}>{el}</EntityScopeProvider>;

test("panel umum: teks utuh, PT, masuk nyata, batas cadangan, semua barang", async () => {
  await mount(wrap(<DeskRowDetail row={ROW} queue={QUEUE} onClose={() => {}} onAction={() => {}} />));
  expect(teks(q("desk-detail-title"))).toContain("SO-1 · Toko A");
  expect(teks(q("desk-detail-subtitle"))).toContain("KSC");
  expect(q("desk-detail-field-subtitle").textContent).toContain(PANJANG.trim());
  expect(teks(q("desk-detail-field-entity_id"))).toContain("KSC");
  expect(teks(q("desk-detail-field-at"))).toMatch(/Masuk/);
  expect(teks(q("desk-detail-field-booking_until"))).toMatch(/Batas cadangan/);
  expect(teks(q("desk-detail-field-value"))).toMatch(/Sisa tagihan/);
  expect(document.body.querySelectorAll('[data-testid^="desk-detail-line-"]')).toHaveLength(2);
  expect(document.body.textContent).not.toMatch(/±/);
});

test("baris lewat tempo: 'lewat n hari' dan label Jatuh tempo; tanpa at → tidak ada bidang waktu; tanpa PT → tidak ada bidang PT", async () => {
  expect(ageText({ age_days: 8, age_kind: "overdue" })).toBe("lewat 8 hari");
  expect(ageText({ age_days: 0, age_kind: "overdue" })).toBe("jatuh tempo hari ini");
  expect(ageText({ age_days: 8 })).toBe("8 hari");
  await mount(wrap(<DeskRowDetail row={{ ...ROW, age_kind: "overdue", age_days: 8 }} queue={QUEUE} onClose={() => {}} />));
  expect(teks(q("desk-detail-field-at"))).toMatch(/Jatuh tempo/);
  expect(teks(q("desk-detail-field-age"))).toMatch(/lewat 8 hari/);
  for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = "";
  await mount(wrap(<DeskRowDetail row={{ ...ROW, at: "", entity_id: "" }} queue={QUEUE} onClose={() => {}} />));
  expect(q("desk-detail-field-at")).toBeNull();
  expect(q("desk-detail-field-entity_id")).toBeNull();
  expect(document.body.textContent).not.toMatch(/tidak dikenal/i);
});

test("registri: jenis yang punya panel memakai panel itu, bukan panel umum", async () => {
  DESK_PANELS.sales_order = ({ row }) => <div data-testid="panel-uji">{row.number}</div>;
  try {
    await mount(wrap(<DeskRowDetail row={ROW} queue={QUEUE} onClose={() => {}} />));
    expect(teks(q("panel-uji"))).toBe("SO-1");
    expect(q("desk-detail-field-subtitle")).toBeNull();
  } finally { delete DESK_PANELS.sales_order; }
});

test("aksi pindah layar bertanda ikon; klik menutup lalu menjalankan aksi; Buka layar penuh; aksi tambahan", async () => {
  const onAction = jest.fn(); const onClose = jest.fn(); const onOpenFull = jest.fn();
  const lain = { ref_type: "customer", ref_id: "c1", action_kind: "receipt" };
  await mount(wrap(<DeskRowDetail row={{ ...ROW, _moreActions: [{ label: "Terima pembayaran", row: lain }] }} queue={QUEUE}
    inPlace={(r) => r.action_kind === "receipt"} onAction={onAction} onClose={onClose} onOpenFull={onOpenFull} />));
  expect(q("desk-detail-action-nav")).not.toBeNull();
  await klik("desk-detail-action");
  expect(onClose).toHaveBeenCalled(); expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), QUEUE);
  await klik("desk-detail-action-0");
  expect(onAction).toHaveBeenLastCalledWith(lain, QUEUE);
  await klik("desk-detail-open-full");
  expect(onOpenFull).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), QUEUE);
});

test("baris tanpa aksi: tidak ada tombol aksi", async () => {
  await mount(wrap(<DeskRowDetail row={{ ...ROW, action: "" }} queue={QUEUE} onClose={() => {}} onOpenFull={() => {}} />));
  expect(q("desk-detail-action")).toBeNull();
  expect(q("desk-detail-open-full")).not.toBeNull();
});
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaDeskRowDetail.test.js` → FAIL (modul `../desks/DeskRowDetail` tidak ada).
- [ ] **Step 3: Terapkan** sesuai Interfaces (kelas: label bidang `text-fs-12 text-kn-text-2`, isi `text-fs-13 text-kn-text`; tanpa hex, tanpa `text-[`).
- [ ] **Step 4: Jalankan, harus LULUS** — uji di atas PASS; `$GUARD` tanpa pelanggaran baru (`verify_detail_modal`, `verify_ui_standard`).
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/desks/deskPanels.js frontend/src/features/desks/DeskRowDetail.jsx \
  frontend/src/features/sales_admin/workDeskApi.js frontend/src/features/__tests__/mejaDeskRowDetail.test.js
git commit -m "feat(meja): pop-up rincian baris umum dan registri panel per jenis dokumen"
```

---

### Task 5: `DeskQueueCard` — ukuran tetap, baris ringkas yang bisa diklik, status tersimpan

**Files:**
- Modify: `frontend/src/features/sales_admin/DeskQueueCard.jsx` (tulis ulang isi; nama ekspor bawaan tetap)
- Modify: `frontend/src/features/sales_admin/workDeskApi.js` (`QUEUE_META`, `DEFAULT_QUEUE_META`, `BADGE_TONE` → token; hapus `sinceFromAge`)
- Modify: `frontend/src/components/TableFilter.jsx` (`useTableFilter` opsi `initial`; kontrol `h-8` + `text-fs-12`)
- Create: `frontend/src/features/desks/deskSession.js`
- Modify: `frontend/src/features/desks/DeskRowDetail.jsx` (lencana memakai `DeskBadge`)
- Modify (uji lama yang mengunci "aksi langsung pindah layar"): `frontend/src/features/__tests__/phase4R6.test.js` (`my-desk-action-so_1` → klik lalu `my-desk-detail-action`), `frontend/src/features/__tests__/mnt2LayarKeuangan.test.js` (kontrabon → klik lalu `fin-desk-detail-action`)
- Test: `frontend/src/features/__tests__/mejaDeskQueueCard.test.js`

**Interfaces:**
- Consumes: `DeskRowDetail`, `ageText` (Task 4).
- Produces `DeskQueueCard({ queue, onAction, busyRef = "", testPrefix = "desk", rowTestPrefix, loading = false, stateKey = "", inPlace = () => false, onOpenFull, defaultOpen /* diabaikan */ })`.
- Produces ekspor bernama: `PAGE_ROWS = 5`; `DESK_CARD_CLASS = "flex flex-col sm:h-[404px]"`; `DESK_ROW_CLASS = "sm:h-14"`; `inPlaceOf(kinds: string[]) → (row) => kinds.includes(row?.action_kind)`; `DeskBadge({ badge, testId })` (lencana `text-fs-12 font-medium` + `badgeClass`); `DeskQueueCardSkeleton({ testPrefix = "desk", index = 0 })` (`${p}-skeleton-${index}`, kelas `DESK_CARD_CLASS`, 5 bilah `animate-pulse` setinggi baris).
- Susunan kartu (`section` `${p}-queue-${id}`, kelas `section-card` + `DESK_CARD_CLASS`, **tanpa** `h-full`):
  - kepala `h-11` satu baris: ikon · `h3` `text-fs-14 font-semibold` · lencana jumlah `${p}-count-${id}` · "tertua n hari" `${p}-oldest-${id}` (bila count > 0) · `HelpTip` `${p}-hint-${id}` berisi `queue.hint` · di kanan nilai `${p}-total-${id}` `text-fs-13 font-semibold` dengan `title={queue.value_label}` — **tidak dirender** untuk `value_kind === "count"`; tanpa label huruf besar;
  - bilah saring `h-11` (`TableFilterBar`) hanya bila ada baris; pilihan urut = `{server, newest}` untuk `count`, `{server, newest, value}` selain itu;
  - daftar `${p}-list-${id}` `flex-1 overflow-hidden`: kerangka 5 bilah (`${p}-loading-${id}`) bila `loading && rows.length === 0`; "Antrean ini bersih — tidak ada yang perlu ditindak." di tengah (`${p}-empty-${id}`) bila kosong; "Tidak ada baris yang cocok." (`${p}-search-empty-${id}`); selain itu baris;
  - kaki `${p}-foot-${id}` `h-9` selalu ada: pager `${p}-pager-${id}` (bila > 5 baris tersaring), catatan `${p}-truncated-${id}` = `` `${rows.length} tertua dari ${queue.count} ditampilkan` `` (bila `count > rows.length`, `title` berisi saran buka layar daftar), `${p}-refreshing-${id}` "Memuat ulang…" (bila `loading && rows.length > 0`).
- Baris (`${rp}-row-${rk}`, `rk = row.row_key || row.ref_id`, `rp = rowTestPrefix || testPrefix`): `div role="button" tabIndex={0}` kelas `DESK_ROW_CLASS` + `cursor-pointer hover:bg-kn-neutral-soft` + grid `sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_auto]`; kiri: nomor `${rp}-number-${rk}` (`text-fs-13 font-semibold text-kn-action truncate`) + pihak `${rp}-title-${rk}` (`text-fs-13 text-kn-text truncate`, isi `row._titleNode || row.title`); tengah: `DeskBadge` `${rp}-badge-${rk}` + PT `${rp}-entity-${rk}` (hanya bila `useEntityScope().selectedEntity === "all"` dan nama PT ada) + umur `${rp}-age-${rk}` = `ageText(row)` (`text-fs-12 font-medium`); kanan: nilai `${rp}-value-${rk}` (`text-fs-13 font-semibold`, kosong untuk `count`) + tombol aksi `${rp}-action-${rk}` (`secondary-button btn-sm`) hanya bila `row.action || queue.action_label`; tidak ada keterangan/"masuk" di baris.
  - Klik baris → buka `DeskRowDetail` (diabaikan bila `e.target.closest("button, a, input, select, textarea")`); Enter/Spasi pada baris (hanya bila `e.target === e.currentTarget`) → buka; tombol aksi `stopPropagation`: `inPlace(row)` → `onAction(row, queue)`, selain itu buka `DeskRowDetail` (aksi di dalamnya). `DeskRowDetail` diberi `testPrefix`, `inPlace`, `onAction`, `onOpenFull`.
- Produces `deskSession.js`: `cardStateKey(stateKey) → "kn.meja.kartu." + stateKey`; `pageStateKey(deskKey) → "kn.meja." + deskKey`; `readDeskState(key) → object` (`{}` bila gagal); `writeDeskState(key, patch)` (gabung, try/catch). Kartu dengan `stateKey`: nilai awal `q/st/sort` dari simpanan; `page` tersimpan > 1 diterapkan **sekali** ketika `shownRows.length > (page − 1) × 5` (bukan pada render pertama), dan penulisan `page` ditahan sampai pemulihan itu terjadi.
- Produces `useTableFilter(rows, { text, status, statusLabel, sorts, initial = {} })` — `initial.q`, `initial.st`, `initial.sort` (hanya bila kunci ada di `sorts`). `TableFilterBar`: pembungkus cari kelas `h-8`, kedua `KNSelect` `!h-8 … text-fs-12` (menggantikan `!h-auto`).
- Token `workDeskApi`: `BADGE_TONE.danger = "border-kn-danger-soft bg-kn-danger-soft text-kn-danger-text"`, `warn → kn-warning-*`, `ok → kn-success-soft/kn-success-text`, `info → kn-action-soft/kn-action`, `mute → kn-neutral-soft/kn-text-2`; `QUEUE_META` tone/bg → `var(--kn-…-text)` / `var(--kn-…-soft)` sesuai rona lama (ungu → `special`).

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaDeskQueueCard.test.js` (pembantu `mount/q/teks/klik/afterEach` sama dengan Task 4 Step 1; KNSelect ditiru):

```javascript
// MEJA-5 — kartu antrean ukuran tetap & baris ringkas (§5.2, §5.5). Review Focus #1, #2, #3, #4.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import fs from "fs";
import path from "path";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import DeskQueueCard, { DeskQueueCardSkeleton, inPlaceOf } from "../sales_admin/DeskQueueCard";

jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, className }) => (
    <select data-testid={tid} className={className} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});
// … pembantu mount/q/teks/klik/afterEach seperti Task 4, + `sessionStorage.clear()` di afterEach …
const row = (i, extra = {}) => ({ ref_type: "sales_order", ref_id: `so${i}`, number: `SO-000${i}`, title: `Toko ${i}`,
  subtitle: `Keterangan panjang ${i}`, badge: "reserved", value: 1000 * i, age_days: i, entity_id: "ent_ksc",
  action: "Follow-up", action_kind: "open", ...extra });
const Q = (n, extra = {}) => ({ id: "q1", label: "Antrean Uji", hint: "Penjelasan antrean", count: n,
  rows: Array.from({ length: n }, (_, i) => row(i + 1)), ...extra });
const ENT = (sel, el) => <EntityScopeProvider selectedEntity={sel} entities={[{ id: "ent_ksc", short_name: "KSC" }]}>{el}</EntityScopeProvider>;

test("RF#2 — tinggi tetap di semua keadaan; catatan & muat ulang di kaki", async () => {
  await mount(<>
    <DeskQueueCard testPrefix="a" queue={Q(0)} />
    <DeskQueueCard testPrefix="b" queue={Q(1)} />
    <DeskQueueCard testPrefix="c" queue={Q(5)} />
    <DeskQueueCard testPrefix="d" queue={{ ...Q(0), id: "q1" }} loading />
    <DeskQueueCard testPrefix="e" queue={Q(2, { count: 250 })} loading />
    <DeskQueueCardSkeleton testPrefix="f" />
  </>);
  for (const id of ["a-queue-q1", "b-queue-q1", "c-queue-q1", "d-queue-q1", "e-queue-q1", "f-skeleton-0"]) {
    expect(q(id).className).toContain("sm:h-[404px]");
    expect(q(id).className).not.toContain("h-full");
  }
  expect(q("d-loading-q1")).not.toBeNull();
  expect(q("a-empty-q1").textContent).toContain("bersih");
  expect(q("e-truncated-q1").closest('[data-testid="e-foot-q1"]')).not.toBeNull();
  expect(teks(q("e-truncated-q1"))).toMatch(/2 tertua dari 250/);
  expect(q("e-refreshing-q1").closest('[data-testid="e-foot-q1"]')).not.toBeNull();
});

test("klik baris membuka rincian; Enter pada baris membuka; kursor tangan hanya di baris", async () => {
  await mount(<DeskQueueCard testPrefix="t" queue={Q(2)} />);
  expect(q("t-row-so1").getAttribute("tabindex")).toBe("0");
  expect(q("t-row-so1").className).toContain("cursor-pointer");
  await klik("t-row-so1");
  expect(teks(q("t-detail-title"))).toContain("SO-0001 · Toko 1");
  await act(async () => { q("t-detail-close-x").click(); });
  await act(async () => { q("t-row-so2").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
  expect(teks(q("t-detail-title"))).toContain("SO-0002");
});

test("RF#1 — tombol aksi, Enter pada tombol, dan tautan judul tidak membuka rincian baris", async () => {
  const onAction = jest.fn();
  const rows = [row(1, { action_kind: "verify", _titleNode: <button type="button" data-testid="judul-link">Toko 1</button> })];
  await mount(<DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 1, rows }}
    inPlace={inPlaceOf(["verify"])} onAction={onAction} />);
  await klik("t-action-so1");
  expect(onAction).toHaveBeenCalledTimes(1); expect(q("t-detail")).toBeNull();
  await act(async () => { q("t-action-so1").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
  expect(q("t-detail")).toBeNull();
  await klik("judul-link");
  expect(q("t-detail")).toBeNull();
});

test("aksi pindah layar membuka rincian dulu; aksi di dalam rincian yang menjalankan", async () => {
  const onAction = jest.fn();
  await mount(<DeskQueueCard testPrefix="t" queue={Q(1)} onAction={onAction} />);
  await klik("t-action-so1");
  expect(onAction).not.toHaveBeenCalled(); expect(q("t-detail-action-nav")).not.toBeNull();
  await klik("t-detail-action");
  expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), expect.objectContaining({ id: "q1" }));
  expect(q("t-detail")).toBeNull();
});

test("RF#3 — PT di baris hanya di mode Semua PT; baris tanpa PT tidak menulis apa pun", async () => {
  const rows = [row(1), row(2, { entity_id: "" })];
  await mount(ENT("all", <DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, rows }} />));
  expect(teks(q("t-entity-so1"))).toBe("KSC");
  expect(q("t-entity-so2")).toBeNull();
  for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = "";
  await mount(ENT("ent_ksc", <DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, rows }} />));
  expect(q("t-entity-so1")).toBeNull();
});

test("antrean jumlah: jumlah sekali, tanpa urut nilai; hint di ikon ?; umur lewat tempo; tanpa ±", async () => {
  await mount(<DeskQueueCard testPrefix="t" queue={{ ...Q(3), value_kind: "count",
    rows: [row(1, { age_kind: "overdue", age_days: 8 }), row(2), row(3)] }} />);
  expect(q("t-total-q1")).toBeNull();
  expect([...q("t-q-q1-sort").options].map((o) => o.value)).toEqual(["server", "newest"]);
  expect(document.body.textContent).not.toContain("Penjelasan antrean");
  expect(q("t-hint-q1")).not.toBeNull();
  expect(teks(q("t-age-so1"))).toBe("lewat 8 hari");
  expect(document.body.textContent).not.toMatch(/masuk ±|menunggu \d/);
});

test("huruf: judul 14/600, maks. dua semi-tebal per baris, tanpa font-bold; kontrol saring sama tinggi", async () => {
  await mount(<DeskQueueCard testPrefix="t" queue={Q(2, { rows: [row(1, { badge: "reserved" }), row(2, { badge: "waiting_stock" })] })} />);
  expect(q("t-queue-q1").querySelector("h3").className).toMatch(/text-fs-14.*font-semibold|font-semibold.*text-fs-14/);
  const r = q("t-row-so1");
  expect(r.querySelectorAll(".font-semibold").length).toBeLessThanOrEqual(2);
  expect(r.querySelectorAll(".font-bold").length).toBe(0);
  expect(q("t-search-q1").closest("label").className).toContain("h-8");
  expect(q("t-q-q1-status").className).toContain("!h-8");
});

test("RF#4 — cari/saring/halaman pulih dari sessionStorage walau baris tiba belakangan", async () => {
  const banyak = { id: "q1", label: "U", count: 12, rows: Array.from({ length: 12 }, (_, i) => row(i + 1)) };
  const a = await mount(<DeskQueueCard testPrefix="t" stateKey="uji:q1" queue={banyak} />);
  await klik("t-pager-q1-next");
  expect(JSON.parse(sessionStorage.getItem("kn.meja.kartu.uji:q1")).page).toBe(2);
  for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = "";
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(<DeskQueueCard testPrefix="t" stateKey="uji:q1" loading queue={{ ...banyak, rows: [] }} />); });
  await act(async () => { root.render(<DeskQueueCard testPrefix="t" stateKey="uji:q1" queue={banyak} />); });
  expect(q("t-row-so6")).not.toBeNull();            // halaman 2 = baris 6–10
  const input = q("t-search-q1");
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "SO-0003");
    input.dispatchEvent(new Event("input", { bubbles: true })); });
  expect(JSON.parse(sessionStorage.getItem("kn.meja.kartu.uji:q1")).q).toBe("SO-0003");
});

test("tanpa px mentah dan hex di kartu & kamus meja", () => {
  for (const rel of ["../sales_admin/DeskQueueCard.jsx", "../sales_admin/workDeskApi.js", "../desks/DeskRowDetail.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/text-\[\d/);
    expect(src).not.toMatch(/#[0-9A-Fa-f]{6}\b/);
  }
});
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaDeskQueueCard.test.js` → FAIL (`DeskQueueCardSkeleton` tidak ada, `h-full`, dll.).
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi:
  `$JEST src/features/__tests__/mejaDeskRowDetail.test.js src/features/__tests__/trial22Okt.test.js src/features/__tests__/uatV3UiGaps.test.js src/features/__tests__/uatV3S2Cbd.test.js src/features/__tests__/phase4R6.test.js src/features/__tests__/mnt2LayarKeuangan.test.js src/features/__tests__/pk17NominalBerizin.test.js src/features/__tests__/financeDeskTidy.test.js src/features/__tests__/deskReturnQueue.test.js`
  → PASS setelah menyesuaikan `phase4R6` dan `mnt2LayarKeuangan` (klik aksi pindah layar → `*-detail-action`). `$GUARD` tanpa pelanggaran baru.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/sales_admin/DeskQueueCard.jsx frontend/src/features/sales_admin/workDeskApi.js \
  frontend/src/components/TableFilter.jsx frontend/src/features/desks/deskSession.js frontend/src/features/desks/DeskRowDetail.jsx \
  frontend/src/features/__tests__/mejaDeskQueueCard.test.js frontend/src/features/__tests__/phase4R6.test.js \
  frontend/src/features/__tests__/mnt2LayarKeuangan.test.js
git commit -m "feat(meja): kartu antrean ukuran tetap, baris ringkas yang bisa diklik, status kartu tersimpan"
```

---

### Task 6: Kerangka meja `DeskFrame` — satu kepala, ikon ?, tab Antrean/Pantau, gulir, muat ulang global

**Files:**
- Create: `frontend/src/context/PageHelpContext.jsx`
- Create: `frontend/src/utils/refreshSignal.js`
- Create: `frontend/src/features/desks/DeskFrame.jsx`
- Modify: `frontend/src/features/desks/deskSession.js` (`markDeskReturn`, `useDeskScrollRestore`)
- Modify: `frontend/src/features/sales_admin/deskQueueOrder.js` (`orderDeskQueues`, `PANTAU_QUEUE_IDS`, `splitPantau`)
- Modify: `frontend/src/components/CoreWidgets.jsx` (`TopBar` prop `titleAddon`)
- Modify: `frontend/src/App.js` (`PageHelpProvider` membungkus `app-main`; `titleAddon={<PageHelpButton />}`; `onSync` :319 → `() => { loadAll(); kirimMuatUlang(); }`)
- Modify: `frontend/src/AppViewRouter.jsx` (:254 daftar `ReturnDeskSummaryCard` → `["admin-home", "manager-home"]`; tiga `RoleDesk` + `currentUser={user}`)
- Modify: `frontend/src/features/sales_admin/SalesAdminDesk.jsx`, `frontend/src/features/finance/FinanceDesk.jsx`, `frontend/src/features/desks/RoleDesk.jsx`, `frontend/src/features/samples/SampleAdminDesk.jsx`
- Test: `frontend/src/features/__tests__/mejaDeskFrame.test.js`

**Interfaces:**
- Produces `refreshSignal.js`: `export const MUAT_ULANG_EVENT = "kn:muat-ulang"`; `export function kirimMuatUlang()` (`window.dispatchEvent(new Event(MUAT_ULANG_EVENT))`).
- Produces `PageHelpContext.jsx`: `PageHelpProvider({ children })`; `usePageHelp(node, key: string)` — selama terpasang isi ? halaman = `node`; efek hanya bergantung pada `key` (bukan `node`) agar tidak berputar; dilepas saat unmount; di luar provider tidak berbuat apa-apa; `PageHelpButton()` → `<HelpTip text={help} testId="page-help" label="Tentang layar ini" />` (null bila kosong). `TopBar`: `h1.page-title` + `titleAddon` dalam satu baris `flex min-w-0 items-center gap-1.5`.
- Produces `deskSession.js`: `markDeskReturn(deskKey)` → `writeDeskState(pageStateKey(deskKey), { scrollY: window.scrollY || 0, returnPending: true })`; `useDeskScrollRestore(deskKey, ready: boolean)` → saat `ready` pertama kali benar dan `returnPending`, `window.scrollTo(0, scrollY)` lalu `returnPending: false`.
- Produces `deskQueueOrder.js`: `orderDeskQueues(queues) → [...filled terurut compareFilledQueues, ...empty urutan server]`; `PANTAU_QUEUE_IDS = { sales_admin: ["menunggu_manajer"], sample_admin: ["di_gudang", "kirim_ambil", "selesai"] }`; `splitPantau(queues, deskKey) → { antrean: Queue[], pantau: Queue[] }`.
- Produces `DeskFrame({ deskKey, testPrefix, help, notMine = [], antrean, pantau = null, ready = true, onReload })`; ekspor `DESK_GRID_CLASS = "grid grid-cols-1 items-start gap-3 xl:grid-cols-2"`:
  - `PageTabs` `testId={`${testPrefix}-tabs`}` dengan tab `antrean` "Antrean" (bawaan) dan `pantau` "Pantau"; tab aktif disimpan di kunci `kn.meja.<deskKey>` (bidang `tab`); hanya panel aktif yang dirender: `${p}-antrean` / `${p}-pantau`; Pantau tanpa isi → `${p}-pantau-empty` "Tidak ada pantauan untuk meja ini.";
  - `usePageHelp(<>{help}{notMine.length > 0 && <><br/><b>Bukan wewenang meja ini:</b> {notMine.join(" · ")}</>}</>, `${deskKey}|${notMine.join("|")}`)`;
  - mendengarkan `MUAT_ULANG_EVENT` → `onReload()`; `useDeskScrollRestore(deskKey, ready)`.
- Perilaku keempat meja (sesudah tugas ini):
  - **Dihapus:** `section-card` kepala meja (ikon, `kicker`, `h2` `*-title`, tombol muat ulang), paragraf alur, ketiga `Metric` + `*-metrics`, kotak "Paling lama menunggu" (`*-oldest-card`, `focusId`), kotak `*-not-mine`, `notice-bar`/div toast (`desk-toast`, `fin-desk-toast`, `sample-desk-toast`); kata "badan usaha" di teks kosong → "PT".
  - **Antrean:** `DESK_GRID_CLASS` berisi `DeskQueueCard` urutan `orderDeskQueues(split.antrean)` (Keuangan: urutan lama, tanpa kelompok kosong), `stateKey={`${deskKey}:${q.id}`}`, `inPlace`, `onOpenFull`; memuat awal → `${p}-loading` berisi 4 `DeskQueueCardSkeleton`.
  - **Pantau:** Admin Sales = `SoTrackerCard` (bila `can(perms,"order","view")`) + `KeepPendingPanel` + `CustomerGradeRulesCard` + kartu `menunggu_manajer`; Keuangan = `ReturnDeskSummaryCard` + `SoTrackerCard` (izin `order.view`); Gudang = `ReturnDeskSummaryCard` + `SoTrackerCard` (izin); MD & Meja Saya = `SoTrackerCard` (izin); Sample = `SoTrackerCard` (izin) + kartu `di_gudang`, `kirim_ambil`, `selesai`. `ReturnDeskSummaryCard onNavigate={(t) => go(t)}` (`useAppNav`). `SoTrackerCard` menerima `refreshKey={tick}`.
  - **Izin Pelacak:** `RoleDesk` membaca `currentUser?.permissions` (cadangan lama `localStorage kn_user` tetap).
  - **Aksi:** `inPlace` — Admin Sales `inPlaceOf(["verify", "fulfill", "release"])`; Keuangan `["issue_tax", "receipt", "supplier_card"]`; Sample `["approve_payment", "confirm"]`; MD/Gudang/Meja Saya `[]`. Navigasi (aksi pindah layar, "Buka layar penuh", tautan Pelacak) selalu lewat `markDeskReturn(deskKey)` lalu `onOpenDocument`.
  - **Sesudah aksi sukses:** `toast({ title: pesan })`, lalu `reloadQueue(queueId)` — memuat ulang data meja tanpa mengosongkan halaman; hanya kartu `queueId` yang diberi `loading` sampai data tiba (state `refreshingId`); Admin Sales juga menaikkan `trackerTick`.
  - **Muat ulang global:** `onReload` = muat ulang data meja + naikkan `tick`.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaDeskFrame.test.js` (pembantu seperti Task 4; `apiClient` ditiru dengan peta URL → data; tiruan stub: `SoTrackerCard` → `<div data-testid="so-tracker-stub"/>`, `KeepPendingPanel` → `kp-stub`, `CustomerGradeRulesCard` → `grade-stub`, `ReturnDeskSummaryCard` → `return-desk-stub`, `VerifyOrderDialog`/`FulfillmentDecisionDialog` → `null`; `jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }))`):

```javascript
// MEJA-6 — kerangka meja (§5.1): satu kepala, ? di samping judul, tab Antrean/Pantau, urutan kartu, toast, muat ulang
// impor: SalesAdminDesk, FinanceDesk ("../finance/FinanceDesk"), RoleDesk ("../desks/RoleDesk"), SampleAdminDesk,
//        { PageHelpProvider, PageHelpButton } dari "../../context/PageHelpContext"
// per kartu, muat ulang global, pemulihan tab & gulir (Review Focus #4).
const DESK = { queues: [
  { id: "perlu_verifikasi", label: "Perlu diperiksa", count: 0, rows: [] },
  { id: "siap_dikonfirmasi", label: "Ditahan", count: 1, oldest_age_days: 2, rows: [
    { ref_type: "sales_order", ref_id: "so7", number: "SO-7", title: "Toko T", value: 1, age_days: 2,
      action: "Lepas ke gudang", action_kind: "release", entity_id: "ent_ksc" }] },
  { id: "jatuh_tempo", label: "Jatuh tempo", count: 1, oldest_age_days: 9, rows: [
    { ref_type: "sales_order", ref_id: "so9", number: "SO-9", title: "Toko J", value: 5, age_days: 9, age_kind: "overdue",
      action: "Follow-up", action_kind: "open", entity_id: "ent_ksc" }] },
  { id: "menunggu_manajer", label: "Menunggu manajer", count: 0, rows: [] }],
  not_my_desk: ["Faktur Pajak keluaran", "Pencatatan uang masuk (kwitansi AR)"] };
const USER = { permissions: { order: ["view", "confirm"] } };

test("satu kepala: tanpa h2/kartu angka/'Paling lama'; ? berisi alur + bukan wewenang", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<PageHelpProvider><PageHelpButton /><SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} /></PageHelpProvider>);
  expect(q("desk-title")).toBeNull(); expect(q("desk-metrics")).toBeNull();
  expect(document.body.textContent).not.toMatch(/Paling lama menunggu|Bukan wewenang meja ini/);
  await klik("page-help");
  expect(teks(q("page-help-text"))).toMatch(/Bukan wewenang meja ini: Faktur Pajak keluaran · Pencatatan uang masuk/);
  expect(teks(q("page-help-text"))).not.toMatch(/Meja Finance/);
});

test("urutan kartu: berisi paling mendesak dulu, lalu kosong; grid tidak meregang; menunggu_manajer hanya di Pantau", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  const ids = [...document.body.querySelectorAll('[data-testid^="desk-queue-"]')].map((e) => e.getAttribute("data-testid"));
  expect(ids).toEqual(["desk-queue-jatuh_tempo", "desk-queue-siap_dikonfirmasi", "desk-queue-perlu_verifikasi"]);
  expect(q("desk-antrean").firstElementChild.className).toContain("items-start");
  expect(q("so-tracker-stub")).toBeNull();
  await klik("desk-tabs-pantau");
  expect(q("so-tracker-stub")).not.toBeNull(); expect(q("kp-stub")).not.toBeNull(); expect(q("grade-stub")).not.toBeNull();
  expect(q("desk-queue-menunggu_manajer")).not.toBeNull();
});

test("Pelacak SO di Pantau hanya dengan izin order.view (RoleDesk MD)", async () => {
  routeGet({ "/md/desk": { queues: [] } });
  await mount(<RoleDesk desk="md" currentUser={{ permissions: { design_request: ["view"] } }} onOpenDocument={() => {}} />);
  expect(q("md-desk-title")).toBeNull(); expect(q("md-desk-oldest-card")).toBeNull();
  await klik("md-desk-tabs-pantau");
  expect(q("so-tracker-stub")).toBeNull(); expect(q("md-desk-pantau-empty")).not.toBeNull();
});

test("Keuangan: kartu retur internal & Pelacak SO pindah ke Pantau", async () => {
  routeGet({ "/finance/desk": { queues: [], not_my_desk: [] } });
  await mount(<FinanceDesk currentUser={{ permissions: { payment_variance: ["decide"], order: ["view"] } }} selectedEntity="ent_ksc" />);
  expect(q("fin-desk-title")).toBeNull(); expect(q("return-desk-stub")).toBeNull();
  await klik("fin-desk-tabs-pantau");
  expect(q("return-desk-stub")).not.toBeNull(); expect(q("so-tracker-stub")).not.toBeNull();
});

test("aksi sukses: toast (bukan bilah puncak) dan hanya kartu terkait dimuat ulang", async () => {
  let lepasMuat;
  mockGet.mockResolvedValueOnce({ data: DESK }).mockImplementationOnce(() => new Promise((r) => { lepasMuat = r; }));
  mockPost.mockResolvedValue({ data: { released: true, order: { number: "SO-7", status: "confirmed" } } });
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  await klik("desk-action-so7");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so7/release");
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("SO-7") }));
  expect(q("desk-toast")).toBeNull();
  expect(q("desk-refreshing-siap_dikonfirmasi")).not.toBeNull();
  expect(q("desk-refreshing-jatuh_tempo")).toBeNull();
  await act(async () => lepasMuat({ data: DESK }));
});

test("muat ulang global memuat ulang meja", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={() => {}} />);
  const n = mockGet.mock.calls.filter(([u]) => u.includes("/sales-admin/desk")).length;
  await act(async () => { window.dispatchEvent(new Event("kn:muat-ulang")); });
  expect(mockGet.mock.calls.filter(([u]) => u.includes("/sales-admin/desk")).length).toBe(n + 1);
});

test("RF#4 — tab & gulir pulih sesudah 'Buka layar penuh'; tanpa tanda kembali tidak menggulir", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  window.scrollTo = jest.fn();
  Object.defineProperty(window, "scrollY", { value: 640, configurable: true });
  const open = jest.fn();
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={open} />);
  await klik("desk-tabs-pantau"); await klik("desk-tabs-antrean");
  await klik("desk-row-so9"); await klik("desk-detail-open-full");
  expect(open).toHaveBeenCalledWith(expect.objectContaining({ view: "orders", focus_id: "so9" }));
  expect(JSON.parse(sessionStorage.getItem("kn.meja.sales_admin"))).toMatchObject({ scrollY: 640, returnPending: true, tab: "antrean" });
  for (const r of roots) await act(async () => r.unmount()); roots = [];
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={open} />);
  expect(window.scrollTo).toHaveBeenCalledWith(0, 640);
  expect(JSON.parse(sessionStorage.getItem("kn.meja.sales_admin")).returnPending).toBe(false);
  window.scrollTo.mockClear();
  for (const r of roots) await act(async () => r.unmount()); roots = [];
  await mount(<SalesAdminDesk currentUser={USER} onOpenDocument={open} />);
  expect(window.scrollTo).not.toHaveBeenCalled();
});

test("Sample: antrean pantau di tab Pantau", async () => {
  routeGet({ "/sample-orders/desk": { queues: [
    { id: "bayar_sampel", label: "Bayar", count: 0, rows: [] }, { id: "di_gudang", label: "Di gudang", count: 0, rows: [] }] } });
  await mount(<SampleAdminDesk currentUser={{ permissions: { sample_order: ["view"] } }} onOpenDocument={() => {}} />);
  expect(q("sample-desk-queue-di_gudang")).toBeNull();
  await klik("sample-desk-tabs-pantau");
  expect(q("sample-desk-queue-di_gudang")).not.toBeNull();
});
```
(`routeGet(peta)` = `mockGet.mockImplementation((u) => { const k = Object.keys(peta).find((x) => u.includes(x)); return Promise.resolve({ data: k ? peta[k] : [] }); })`; `afterEach` juga `sessionStorage.clear()`.)

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaDeskFrame.test.js` → FAIL (`PageHelpContext` tidak ada, `desk-title` masih ada, …).
- [ ] **Step 3: Terapkan** sesuai Interfaces. Teks `help`: Admin Sales = paragraf alur lama `SalesAdminDesk.jsx:111-116`; Keuangan = paragraf `FinanceDesk.jsx:224-226`; MD/Gudang/Meja Saya = `DESKS[desk].intro`; Sample = paragraf `SampleAdminDesk.jsx:74`. `notMine` = `data.not_my_desk` (Admin Sales, Keuangan `src.desk?.not_my_desk`, Sample, RoleDesk).
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi:
  `$JEST src/features/__tests__/mejaDeskQueueCard.test.js src/features/__tests__/mnt2LayarKeuangan.test.js src/features/__tests__/pk17NominalBerizin.test.js src/features/__tests__/phase4R6.test.js src/features/__tests__/financeDeskTidy.test.js src/features/__tests__/deskReturnQueue.test.js src/features/__tests__/uatV3S2Cbd.test.js src/features/__tests__/odCancelCreditNote.test.js src/features/__tests__/a1AlurPesanan.test.js src/components/__tests__/tourMenuPlacement.test.js`
  → PASS (sesuaikan uji yang mencari elemen yang memang dihapus: kepala/kartu angka/Pelacak di tab Antrean — klik `*-tabs-pantau` dulu). `$GUARD` tanpa pelanggaran baru; catat di laporan bahwa tab Antrean/Pantau di Meja Keuangan (tab hub Beranda Keuangan) adalah tingkat tab ketiga untuk admin/manajer (keputusan pemilik §5.1 mengalahkan INV-UI-14; penjaga tidak memerah karena tab ada di `DeskFrame.jsx`).
- [ ] **Step 5: Commit**

```bash
git add frontend/src/context/PageHelpContext.jsx frontend/src/utils/refreshSignal.js frontend/src/features/desks/DeskFrame.jsx \
  frontend/src/features/desks/deskSession.js frontend/src/features/sales_admin/deskQueueOrder.js \
  frontend/src/components/CoreWidgets.jsx frontend/src/App.js frontend/src/AppViewRouter.jsx \
  frontend/src/features/sales_admin/SalesAdminDesk.jsx frontend/src/features/finance/FinanceDesk.jsx \
  frontend/src/features/desks/RoleDesk.jsx frontend/src/features/samples/SampleAdminDesk.jsx \
  frontend/src/features/__tests__/mejaDeskFrame.test.js
git status --short frontend/src   # tambahkan juga setiap berkas uji regresi Step 4 yang disesuaikan (git add <berkas itu>)
git commit -m "feat(meja): satu kepala dengan ikon ?, tab Antrean/Pantau, toast hasil aksi, muat ulang per kartu dan pemulihan gulir"
```

---

### Task 7: Isi tab Pantau — token huruf/warna, baris Pelacak SO bisa dibuka

**Files:**
- Modify: `frontend/src/features/sales_admin/SoTrackerCard.jsx`
- Modify: `frontend/src/features/sales_admin/KeepPendingPanel.jsx`, `frontend/src/features/sales_admin/CustomerGradeRulesCard.jsx`, `frontend/src/features/home/ReturnDeskSummaryCard.jsx` (token saja)
- Modify: `frontend/src/features/sales_admin/workDeskApi.js` (`soTrackerLink` cabang sample)
- Modify: keempat meja (props `SoTrackerCard`)
- Test: `frontend/src/features/__tests__/mejaPantau.test.js`

**Interfaces:**
- Consumes: `DeskRowDetail` (Task 4), `markDeskReturn` (Task 6), baris pelacak + `order_type`, `entity_id` (Task 2).
- Produces `trackerRowToDeskRow(r) → row` (ekspor `SoTrackerCard.jsx`): `{ ref_type: "sales_order", ref_id: r.id, number: r.number, title: r.customer_name, subtitle: `${r.next_step} · oleh ${r.owner_label}`, value: r.grand_total, age_days: r.idle_days, at: r.created_at, badge: r.status, entity_id: r.entity_id || "", sales_name: r.sales_name, action: r.can_act ? r.action : "", action_kind: "tracker", _tracker: r }`.
- Produces `SoTrackerCard({ desk, selectedEntity, onOpen, onOpenFull, testPrefix, refreshKey, showRefresh = true, inPlaceActions = [] })`: baris `tr` bisa diklik/Enter (`cursor-pointer`, `tabIndex=0`) → `DeskRowDetail` `testPrefix={`${testPrefix}-so-tracker`}` dengan `inPlace={(row) => inPlaceActions.includes(row._tracker.action)}`, `onAction={(row) => onOpen?.(row._tracker)}`, `onOpenFull={(row) => onOpenFull?.(row._tracker)}`; tombol aksi sel `stopPropagation`; paragraf penjelasan → `HelpTip` `${p}-so-tracker-help` di samping `h2`; kepala kolom `tr` `${p}-so-tracker-head` = `text-fs-12 font-semibold text-kn-text-2` tanpa `uppercase`; tabel `text-fs-12`/`text-fs-13`; lencana diam `text-fs-12 font-medium`; `showRefresh=false` → tombol `${p}-so-tracker-refresh` tidak dirender.
- Produces `soTrackerLink(r)`: `r.order_type === "sample"` → `{ view: "sample-orders", nav_id: "sample-orders", focus_type: "sample_order", focus_id: r.id, number: r.number }` (sebelum cabang lain).
- Meja desktop memanggil `SoTrackerCard … showRefresh={false} onOpenFull={(r) => { markDeskReturn(deskKey); onOpenDocument?.(soTrackerLink(r)); }}` (Admin Sales menambah `inPlaceActions={["Atur pemenuhan", "Periksa & lepas", "Lepas ke gudang"]}`); `KeepPendingPanel` diberi `showRefresh={false}` (prop baru, bawaan `true`, HP tetap).
- Token: semua `text-[Npx]` → `text-fs-12`/`text-fs-13`/`text-fs-14`/`text-fs-16`; hex → kelas `kn-*`; `ReturnDeskSummaryCard`: judul `text-fs-14 font-semibold`, angka `text-fs-16 font-semibold` (bukan `text-2xl`), label `text-fs-12`, tombol `secondary-button btn-sm`, tanpa `mb-4`.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaPantau.test.js`:

```javascript
// MEJA-7 — tab Pantau (§5.1, §5.5): baris Pelacak SO bisa dibuka (termasuk yang bukan wewenang meja), huruf ≥ 12 px.
// impor: SoTrackerCard ("../sales_admin/SoTrackerCard"), { soTrackerLink } dari "../sales_admin/workDeskApi", fs, path
const TRACK = { count: 2, actionable: 1, rows: [
  { id: "so1", number: "SO-1", customer_name: "Toko A", status: "reserved", status_label: "Dicadangkan", next_step: "Diperiksa & dilepas",
    owner_label: "Admin Sales", owner_roles: ["sales_admin"], can_act: true, action: "Periksa & lepas", grand_total: 1000,
    created_at: "2026-11-20T03:00:00Z", updated_at: "2026-11-21T03:00:00Z", idle_days: 4, entity_id: "ent_ksc", order_type: "regular" },
  { id: "so2", number: "SO-2", customer_name: "Toko B", status: "confirmed", status_label: "Dikonfirmasi", next_step: "Diambil",
    owner_label: "Admin Gudang", owner_roles: ["warehouse_admin"], can_act: false, grand_total: 2000,
    created_at: "2026-11-20T03:00:00Z", updated_at: "2026-11-21T03:00:00Z", idle_days: 4, entity_id: "ent_ksc", order_type: "regular" }] };

test("baris bukan wewenang meja tetap bisa dibuka: rincian tanpa aksi, dengan Buka layar penuh", async () => {
  mockGet.mockResolvedValue({ data: TRACK });
  const onOpen = jest.fn(); const onOpenFull = jest.fn();
  await mount(<SoTrackerCard desk="sales_admin" testPrefix="desk" onOpen={onOpen} onOpenFull={onOpenFull} showRefresh={false} />);
  expect(q("desk-so-tracker-refresh")).toBeNull();
  await klik("desk-so-tracker-row-so2");
  expect(teks(q("desk-so-tracker-detail-title"))).toContain("SO-2 · Toko B");
  expect(q("desk-so-tracker-detail-action")).toBeNull();
  await klik("desk-so-tracker-detail-open-full");
  expect(onOpenFull).toHaveBeenCalledWith(expect.objectContaining({ id: "so2" }));
});

test("tombol aksi di sel tidak membuka rincian; aksi di rincian memanggil onOpen dengan baris pelacak", async () => {
  mockGet.mockResolvedValue({ data: TRACK });
  const onOpen = jest.fn();
  await mount(<SoTrackerCard desk="sales_admin" testPrefix="desk" onOpen={onOpen} />);
  await klik("desk-so-tracker-action-so1");
  expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "so1" })); expect(q("desk-so-tracker-detail")).toBeNull();
  await klik("desk-so-tracker-row-so1"); await klik("desk-so-tracker-detail-action");
  expect(onOpen).toHaveBeenCalledTimes(2);
});

test("label kolom 12 px tanpa huruf besar; tautan SOS ke Pesanan Sample", async () => {
  mockGet.mockResolvedValue({ data: TRACK });
  await mount(<SoTrackerCard desk="sales_admin" testPrefix="desk" />);
  const head = q("desk-so-tracker-head");
  expect(head.className).toContain("text-fs-12"); expect(head.className).not.toContain("uppercase");
  expect(soTrackerLink({ id: "s1", number: "SOS-1", order_type: "sample", owner_roles: ["sample_admin"] }))
    .toMatchObject({ view: "sample-orders", focus_type: "sample_order", focus_id: "s1" });
});

test("berkas Pantau tanpa px mentah & hex", () => {
  for (const rel of ["../sales_admin/SoTrackerCard.jsx", "../sales_admin/KeepPendingPanel.jsx",
                     "../sales_admin/CustomerGradeRulesCard.jsx", "../home/ReturnDeskSummaryCard.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/text-\[\d/); expect(src).not.toMatch(/#[0-9A-Fa-f]{6}\b/); expect(src).not.toMatch(/text-2xl/);
  }
});
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaPantau.test.js` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/a1AlurPesanan.test.js src/features/__tests__/mejaDeskFrame.test.js src/features/__tests__/f15SamplePaymentReapproval.test.js` PASS; `$GUARD` tanpa pelanggaran baru (jumlah `chip_custom`/`font_lt12`/`hex` per berkas hanya turun).
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/sales_admin/SoTrackerCard.jsx frontend/src/features/sales_admin/KeepPendingPanel.jsx \
  frontend/src/features/sales_admin/CustomerGradeRulesCard.jsx frontend/src/features/home/ReturnDeskSummaryCard.jsx \
  frontend/src/features/sales_admin/workDeskApi.js frontend/src/features/sales_admin/SalesAdminDesk.jsx \
  frontend/src/features/finance/FinanceDesk.jsx frontend/src/features/desks/RoleDesk.jsx \
  frontend/src/features/samples/SampleAdminDesk.jsx frontend/src/features/__tests__/mejaPantau.test.js
git commit -m "feat(meja): isi tab Pantau seragam huruf dan warna; baris Pelacak SO membuka rincian"
```

---

### Task 8: Satu nama per meja

**Files:**
- Modify: `frontend/src/config/navMeta.js` (:23-30), `frontend/src/config/hubTabs.js` (:262), `frontend/src/features/desks/RoleDesk.jsx` (`DESKS.warehouse_admin.title`), `frontend/src/features/samples/SampleAdminDesk.jsx` (pesan galat), `frontend/src/features/mobile/MobileRoleSummary.jsx` (:73-74), `frontend/src/features/sales/mobile/MobileSalesAdminDesk.jsx` (:183 teks "Meja Finance" → "Meja Keuangan"; kotaknya dipindah ke ? di Task 16)
- Modify: `backend/services/work_desk_service.py` (:281 hint, :679 `desk_label`), `backend/routers/sample_orders.py` (:169 `title`, :184 `not_my_desk`), `backend/role_registry.py` (:359-364 label `HOME_CHOICES`), `backend/services/dispatch_payment_gate.py` (:174), `backend/config_catalog_core.py` (:313)
- Modify (uji lama): `frontend/src/config/__tests__/mnt1MenuKeuangan.test.js` (:62 label), `frontend/src/features/__tests__/decisionsD3.test.js` (:141), `backend/tests_mem/test_PRT4_sifat_peran.py` (:100, :112)
- Test: `frontend/src/features/__tests__/mejaNamaTunggal.test.js`, `backend/tests_mem/test_MEJA8_nama_meja.py`

**Interfaces:**
- Produces `PAGE_META` judul: `sales-admin-desk` "Meja Admin Sales", `finance-desk` "Meja Keuangan", `md-desk` "Meja MD", `my-desk` "Meja Saya", `warehouse-admin-desk` "Meja Gudang", `sample-admin-desk` "Meja Sample" (kicker tetap); tab hub `finance-tower[0].label` "Meja Keuangan"; label menu `navStructure.js` sudah sesuai (tidak diubah).
- Produces server: `finance_desk()["desk_label"] == "Meja Keuangan"`; hint `jatuh_tempo` "… di Meja Keuangan."; sample desk `title == "Meja Sample"`, `not_my_desk` ["Pesanan roll/yard biasa (SO-) → Meja Admin Sales", "Uang masuk & faktur pajak → Meja Keuangan"]; `HOME_CHOICES` label `finance-desk` "Meja Keuangan", `warehouse-admin-desk` "Meja Gudang", `sample-admin-desk` "Meja Sample".

- [ ] **Step 1: Tulis uji gagal**

`frontend/src/features/__tests__/mejaNamaTunggal.test.js`:
```javascript
// MEJA-8 — satu nama per meja (§5.1): menu = breadcrumb = judul.
import fs from "fs"; import path from "path";
import { PAGE_META, breadcrumbFor } from "../../config/navigationConfig";
import { HUB_TABS } from "../../config/hubTabs";

test.each([["sales-admin-desk", "Meja Admin Sales"], ["finance-desk", "Meja Keuangan"], ["md-desk", "Meja MD"],
  ["my-desk", "Meja Saya"], ["warehouse-admin-desk", "Meja Gudang"], ["sample-admin-desk", "Meja Sample"]])("%s → %s", (v, nama) => {
  expect(PAGE_META[v].title).toBe(nama);
});
test("breadcrumb Meja Keuangan = judul = tab hub", () => {
  expect(HUB_TABS["finance-tower"][0].label).toBe("Meja Keuangan");
  expect(breadcrumbFor("finance-desk", "finance-tower", "admin").slice(-1)[0]).toBe("Meja Keuangan");
});
test("tidak ada nama usang di kode layar (string & teks JSX; komentar diabaikan)", () => {
  const usang = /Meja Finance|Meja Admin Sample|Meja Admin Gudang|Perlu Tindakan/;
  const salah = [];
  const telusur = (d) => fs.readdirSync(d, { withFileTypes: true }).forEach((e) => {
    const p = path.join(d, e.name);
    if (e.isDirectory()) { if (e.name !== "__tests__") telusur(p); return; }
    if (!/\.(js|jsx)$/.test(e.name)) return;
    const kode = fs.readFileSync(p, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|\s)\/\/[^\n]*/g, "$1");
    if (usang.test(kode)) salah.push(path.relative(path.join(__dirname, "../.."), p));
  });
  telusur(path.join(__dirname, "../.."));
  expect(salah).toEqual([]);
});
```
(Komentar blok `/* */` termasuk `{/* */}` JSX dan komentar `//` yang didahului spasi/awal baris dibuang; `http://` tidak terbuang.
Uji ini juga menangkap teks JSX `MobileSalesAdminDesk.jsx:183` — Task 8 sudah mengganti teks itu menjadi "Meja Keuangan" bila
Task 16 belum memindahkannya ke ikon ?.)

`backend/tests_mem/test_MEJA8_nama_meja.py`:
```python
"""MEJA-8 — nama tunggal di keluaran server."""
from __future__ import annotations
import ast
from pathlib import Path
import pytest

pytestmark = pytest.mark.anyio
ROOT = Path(__file__).resolve().parents[1]
USANG = ("Meja Finance", "Meja Admin Sample", "Meja Admin Gudang")


async def test_label_meja(klien, kepala_admin):
    assert (await klien.get("/api/finance/desk", headers=kepala_admin)).json()["desk_label"] == "Meja Keuangan"
    smp = (await klien.get("/api/sample-orders/desk", headers=kepala_admin)).json()
    assert smp["title"] == "Meja Sample" and any("Meja Keuangan" in x for x in smp["not_my_desk"])
    import role_registry as reg
    assert {c["view"]: c["label"] for c in reg.HOME_CHOICES}["warehouse-admin-desk"] == "Meja Gudang"


@pytest.mark.parametrize("rel", ["services/work_desk_service.py", "routers/sample_orders.py", "role_registry.py",
                                 "services/dispatch_payment_gate.py", "config_catalog_core.py"])
def test_tanpa_nama_usang_di_teks_tampil(rel):
    tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
    doc = {id(n.body[0].value) for n in ast.walk(tree)
           if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
           and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    teks = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc]
    assert [t for t in teks if any(u in t for u in USANG)] == []
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaNamaTunggal.test.js` dan `$PYT tests_mem/test_MEJA8_nama_meja.py` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces (komentar & docstring sejarah dibiarkan).
- [ ] **Step 4: Jalankan, harus LULUS** — kedua uji PASS; regresi `$JEST src/config/__tests__/mnt1MenuKeuangan.test.js src/config/__tests__/roleReach.test.js src/config/__tests__/navAccess.test.js src/config/__tests__/prt4HalamanAwal.test.js src/features/__tests__/decisionsD3.test.js` dan `$PYT tests_mem/test_PRT4_sifat_peran.py tests_mem/test_KFIN01_finance_setara_manajer.py` PASS; `cd /home/user/KNHOST && python3 scripts/check_nav_map.py` hijau.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/config/navMeta.js frontend/src/config/hubTabs.js frontend/src/features/desks/RoleDesk.jsx \
  frontend/src/features/samples/SampleAdminDesk.jsx frontend/src/features/mobile/MobileRoleSummary.jsx \
  frontend/src/features/sales/mobile/MobileSalesAdminDesk.jsx \
  backend/services/work_desk_service.py backend/routers/sample_orders.py backend/role_registry.py \
  backend/services/dispatch_payment_gate.py backend/config_catalog_core.py \
  frontend/src/config/__tests__/mnt1MenuKeuangan.test.js frontend/src/features/__tests__/decisionsD3.test.js \
  backend/tests_mem/test_PRT4_sifat_peran.py frontend/src/features/__tests__/mejaNamaTunggal.test.js \
  backend/tests_mem/test_MEJA8_nama_meja.py
git commit -m "fix(meja): satu nama per meja di menu, breadcrumb, judul, dan teks server (Meja Keuangan, Meja Gudang, Meja Sample)"
```

---

### Task 9: Konfirmasi terbit faktur pajak — pop-up "Terbitkan" bersama

**Files:**
- Create: `frontend/src/features/finance/TaxIssueDialog.jsx`
- Modify: `frontend/src/features/finance/TaxInvoices.jsx` (cabang `modal.type === "issue"` :492-507 → `TaxIssueDialog`)
- Modify: `frontend/src/features/finance/FinanceDesk.jsx` (`doIssueTax` :174-183 → dialog)
- Modify: `frontend/src/features/orders/OrderDetailPanel.jsx` (`handleIssueTax` :163-173 → buka dialog)
- Modify: `frontend/src/features/sales_admin/workDeskApi.js` (`issueTaxInvoice(orderId, body = {})` → `POST /sales-orders/{id}/tax-invoice` dengan `body`)
- Test: `frontend/src/features/__tests__/mejaKonfirmasiPajak.test.js`

**Interfaces:**
- Produces `TaxIssueDialog({ target, submit, onClose, onDone, testId = "fkt-modal" })`:
  - `target = { kind: "draft" | "order", id, number, orderNumber, customerName, npwp = "", entityId, dpp = null, ppnAmount, total = null, kodeTransaksi = "", fakturDate = "", nsfp = "", isRetur = false }`;
  - `submit(body) → Promise<faktur>`; `body = { faktur_date: string | null, kode_transaksi: string | null, nsfp: string | null }`; nilai kosong → `null`;
  - `FormModal size="sm" icon={Send}` judul draf = judul lama (`"Terbitkan Draf Faktur"` / `"Terbitkan Dokumen Pajak Retur"`), pesanan = `"Terbitkan Faktur Pajak"`; subjudul `` `${number} · ${orderNumber || "—"}` ``;
  - isian (testid lama dipertahankan): `fkt-issue-date` (bawaan draf = `fakturDate`, pesanan = `todayWib()`), `fkt-kode-select` (opsi dari `GET /settings/effective?entity_id=` → `tax.kode_transaksi_diizinkan`; untuk `order` tambah opsi pertama `{ value: "", label: "Bawaan (ditentukan sistem)" }`), `fkt-issue-nsfp`;
  - pratinjau `fkt-issue-preview`: Pesanan, Pelanggan, NPWP (`npwp || "Belum tercatat"`), DPP (hanya bila `dpp != null`), PPN, Total (bila ada) — angka hanya dari `target`, tanpa hitungan;
  - kalimat dampak `fkt-issue-confirm` = `moneyMessage(...)` seperti sekarang; tombol `fkt-modal-submit` "Terbitkan"; galat `submit` (tolak/nilai palsu → "Gagal menerbitkan Faktur Pajak.") tampil di dalam (`fkt-modal-error`), dialog tetap terbuka; sukses → `onDone(faktur)`.
- `TaxInvoices` draf: `submit = (body) => issueIntent.send({ id, aksi: "issue", ...body }, (k) => moneyPost(`${API}/tax-invoices/${id}/issue`, body, k))`, `onDone = () => { closeModal(); load(); }`.
- `FinanceDesk` `issue_tax`: `target` dari baris (`id: row.ref_id, number: row.number, orderNumber: row.number, customerName: row.title, npwp: row.customer_npwp, entityId: row.entity_id, dpp: row.dpp ?? null, ppnAmount: row.ppn_amount, total: row.value`), `submit = (body) => issueTaxInvoice(row.ref_id, body)`, `onDone` → `toast({ title: `Faktur Pajak ${f.number} diterbitkan untuk ${row.number}.` })` + `reloadQueue("faktur_pajak")`.
- `OrderDetailPanel`: tombol `issue-tax-invoice-btn` membuka dialog (`target` dari `sel`: `dpp`, `ppn_amount`, `grand_total`, `customer_npwp`); `submit = (body) => onIssueTaxInvoice(sel.id, body)`; `onDone` → muat ulang daftar faktur pesanan.
- Aturan pemanggil: setiap berkas `src/**` (bukan uji) yang memuat `issueTaxInvoice(`, `onIssueTaxInvoice(`, atau `` tax-invoices/${…}/issue `` juga memuat `TaxIssueDialog`.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaKonfirmasiPajak.test.js` (tiruan: `apiClient`, `KNSelect`, `KNDatePicker` → `<input data-testid={…} value onChange>`, `use-toast`; untuk `OrderDetailPanel` salin daftar `jest.mock` dari `latihS1Amandemen.test.js:27-40`):

```javascript
// MEJA-9 — §5.4: terbit faktur pajak selalu lewat pratinjau + konfirmasi, di meja dan di layar asal.
// impor: FinanceDesk, { OrderDetailPanel } dari "../orders/OrderDetailPanel"
const BARIS = { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko A", value: 1110000, ppn_amount: 110000,
  dpp: 1000000, customer_npwp: "01.234.567.8-901.000", entity_id: "ent_ksc", action: "Terbitkan", action_kind: "issue_tax", age_days: 1 };
const DESK = { queues: [{ id: "siap_faktur_pajak", label: "Faktur", count: 1, rows: [BARIS] }], not_my_desk: [] };
const FIN = { permissions: { payment_variance: ["decide"], tax_invoice: ["create"] } };

test("meja: klik Terbitkan membuka pratinjau, belum menerbitkan; Terbitkan di pop-up memanggil endpoint yang sama", async () => {
  routeGet({ "/finance/desk": DESK, "/settings/effective": { tax: { kode_transaksi_diizinkan: ["01", "04"] } } });
  mockPost.mockResolvedValue({ data: { number: "KSC/FKT-00009" } });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-faktur_pajak-action-so1");
  expect(mockPost).not.toHaveBeenCalled();
  const pv = teks(q("fkt-issue-preview"));
  for (const s of ["SO-1", "Toko A", "01.234.567.8-901.000", "110.000", "1.000.000", "1.110.000"]) expect(pv).toContain(s);
  await klik("fkt-modal-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so1/tax-invoice",
    expect.objectContaining({ kode_transaksi: null, nsfp: null, faktur_date: expect.any(String) }));
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("KSC/FKT-00009") }));
  expect(q("fkt-modal")).toBeNull();
});

test("galat server tampil di dalam pop-up; pop-up tetap terbuka", async () => {
  routeGet({ "/finance/desk": DESK, "/settings/effective": {} });
  mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Masa pajak November sudah dilaporkan." } } });
  await mount(<FinanceDesk currentUser={FIN} selectedEntity="ent_ksc" />);
  await klik("fin-desk-faktur_pajak-action-so1"); await klik("fkt-modal-submit");
  expect(teks(q("fkt-modal-error"))).toContain("Masa pajak November sudah dilaporkan.");
  expect(q("fkt-modal")).not.toBeNull();
});

test("layar asal (rincian pesanan): tombol Terbitkan Faktur Pajak membuka pop-up yang sama dulu", async () => {
  const onIssue = jest.fn().mockResolvedValue({ number: "KSC/FKT-00010" });
  routeGet({ "/tax-invoices": [], "/settings/effective": { tax: { pemicu_faktur: "pesanan" } } });
  const SO = { id: "so_s1", number: "KSC/SO-S1", customer_name: "Toko S1", status: "done", entity_id: "ent_ksc", is_pkp: true,
    items: [], total_amount: 250000, net_subtotal: 250000, dpp: 250000, ppn_amount: 27500, grand_total: 277500 };
  await mount(<OrderDetailPanel order={SO} user={{ role: "finance", permissions: { tax_invoice: ["view", "create"], order: ["view"] } }}
    embedded onIssueTaxInvoice={onIssue} />);
  await klik("issue-tax-invoice-btn");
  expect(onIssue).not.toHaveBeenCalled(); expect(q("fkt-issue-preview")).not.toBeNull();
  await klik("fkt-modal-submit");
  expect(onIssue).toHaveBeenCalledWith("so_s1", expect.objectContaining({ kode_transaksi: null }));
});

test("setiap pemanggil terbit faktur memakai TaxIssueDialog", () => {
  const pola = /\bissueTaxInvoice\(|\bonIssueTaxInvoice\(|tax-invoices\/\$\{[^}]+\}\/issue/;
  const salah = berkasSumber().filter((f) => pola.test(baca(f)) && !baca(f).includes("TaxIssueDialog"));
  expect(salah).toEqual([]);
});
```
(`berkasSumber()` = semua `.js/.jsx` di `src` kecuali `__tests__`; `baca(f)` = isi berkas — tulis kedua pembantu di berkas uji ini.)

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaKonfirmasiPajak.test.js` → FAIL (POST langsung terkirim saat klik).
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/txt1PengaturanPajak.test.js src/features/__tests__/txt2FakturDraf.test.js src/features/__tests__/pk12MoneyIntentC.test.js src/features/__tests__/latihS1Amandemen.test.js src/features/__tests__/mnt2LayarKeuangan.test.js src/features/__tests__/mejaDeskFrame.test.js` PASS; `$GUARD` bersih.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/finance/TaxIssueDialog.jsx frontend/src/features/finance/TaxInvoices.jsx \
  frontend/src/features/finance/FinanceDesk.jsx frontend/src/features/orders/OrderDetailPanel.jsx \
  frontend/src/features/sales_admin/workDeskApi.js frontend/src/features/__tests__/mejaKonfirmasiPajak.test.js
git commit -m "feat(meja): terbit faktur pajak lewat pratinjau dan konfirmasi bersama di meja dan rincian pesanan"
```

---

### Task 10: Konfirmasi lepas ke gudang (Ditahan) dan teruskan ke gudang (sample)

**Files:**
- Create: `frontend/src/features/sales_admin/ReleaseToWarehouseDialog.jsx`
- Modify: `frontend/src/features/sales_admin/SalesAdminDesk.jsx` (`doRelease` + aksi Pelacak "Lepas ke gudang")
- Modify: `frontend/src/features/orders/OrderDetailPanel.jsx` (:108 lepas tahanan)
- Modify: `frontend/src/features/sales/mobile/MobileOrders.jsx` (:55-59), `frontend/src/features/sales/mobile/MobileSalesAdminDesk.jsx` (:122-129)
- Modify: `frontend/src/features/samples/SampleAdminDesk.jsx` (`confirm`), `frontend/src/features/samples/SampleOrdersView.jsx` (:287 "Teruskan ke Gudang")
- Modify (uji Task 6): `frontend/src/features/__tests__/mejaDeskFrame.test.js` (uji toast/muat ulang per kartu: klik `release-confirm-submit` sebelum memeriksa POST)
- Test: `frontend/src/features/__tests__/mejaKonfirmasiGudang.test.js`

**Interfaces:**
- Produces `orderLinesOf(order) → [{ product_name, sku, quantity, unit, warehouse }]` (ekspor bernama): `order.order_lines` bila ada; selain itu dari `order.items` (gudang unik `allocations[].warehouse_name` + `warehouse_name`, digabung `", "`; satuan `base_unit || unit`).
- Produces `ReleaseToWarehouseDialog({ order, mode = "release", run, onClose, onDone, testId = "release-confirm" })`: `order = { id, number, title, entity_id, order_lines?, items? }`; `mode` `"release"` → judul "Lepas ke gudang?" tombol "Lepas ke gudang"; `"forward"` → "Teruskan ke gudang?" / "Teruskan ke gudang"; `FormModal` `onSubmit` menjalankan `run()` (busy, galat di dalam `error`), sukses → `onDone(hasil)`; pratinjau: `${testId}-order` (`number · title`), `${testId}-pt` (PT pendek), `${testId}-warehouse` (gudang unik semua baris, "—" bila tidak ada), `${testId}-line-${i}` (semua baris); tombol kirim `${testId}-submit`.
- Pemakai: Admin Sales `release` (desktop & Pelacak; baris Pelacak mencari baris `siap_dikonfirmasi` ber-id sama untuk `order_lines`, bila tidak ada memakai baris pelacak tanpa baris barang) → `run = () => releaseOrder(id)`, `onDone(res)` → `toast({ title: releaseMessage(res, number) })` + `reloadQueue("siap_dikonfirmasi")` + `trackerTick`; `OrderDetailPanel` & `MobileOrders` & `MobileSalesAdminDesk` → dialog yang sama dari pesanan/baris; Sample `confirm` (meja & daftar) → `mode="forward"`, `run = () => confirmSampleOrder(id)`, pesan `` `${number} diteruskan ke gudang — ${r.tasks_created ?? ""} tugas potong lahir.` ``.
- Aturan pemanggil: setiap berkas `src/**` (bukan uji, bukan `workDeskApi.js`/`sampleApi.js`) yang memuat `releaseOrder(` atau `confirmSampleOrder(` juga memuat `ReleaseToWarehouseDialog`.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaKonfirmasiGudang.test.js` (pembantu `mount/q/teks/klik/routeGet`
  dan tiruan `apiClient`/`KNSelect`/`use-toast` seperti Task 6; `berkasSumber/baca` seperti Task 9):

```javascript
// MEJA-10 — §5.4: lepas/teruskan ke gudang dengan pratinjau (pesanan, PT, gudang, baris) + konfirmasi.
// impor: SalesAdminDesk, SampleAdminDesk, ReleaseToWarehouseDialog + { orderLinesOf } dari "../sales_admin/ReleaseToWarehouseDialog"
const BARIS = { ref_type: "sales_order", ref_id: "so7", number: "SO-7", title: "Toko T", entity_id: "ent_ksc", value: 1, age_days: 2,
  action: "Lepas ke gudang", action_kind: "release",
  order_lines: [{ product_name: "Kain A", sku: "KA-1", quantity: 10, unit: "yard", warehouse: "Gudang Woven" },
                { product_name: "Kain B", sku: "KB-1", quantity: 5, unit: "yard", warehouse: "Gudang Knit" }] };

test("meja Admin Sales: Lepas ke gudang membuka pratinjau; endpoint baru dipanggil sesudah konfirmasi", async () => {
  routeGet({ "/sales-admin/desk": { queues: [{ id: "siap_dikonfirmasi", label: "Ditahan", count: 1, rows: [BARIS] }] } });
  mockPost.mockResolvedValue({ data: { released: true, order: { number: "SO-7", status: "confirmed" } } });
  await mount(wrapEnt(<SalesAdminDesk currentUser={{ permissions: { order: ["view", "confirm"] } }} onOpenDocument={() => {}} />));
  await klik("desk-action-so7");
  expect(mockPost).not.toHaveBeenCalled();
  expect(teks(q("release-confirm-order"))).toContain("SO-7 · Toko T");
  expect(teks(q("release-confirm-pt"))).toBe("KSC");
  expect(teks(q("release-confirm-warehouse"))).toContain("Gudang Woven, Gudang Knit");
  expect(document.body.querySelectorAll('[data-testid^="release-confirm-line-"]')).toHaveLength(2);
  await klik("release-confirm-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so7/release");
});

test("galat di dalam pop-up", async () => {
  const run = jest.fn().mockRejectedValue({ response: { data: { detail: "Stok sudah dipakai pesanan lain." } } });
  await mount(wrapEnt(<ReleaseToWarehouseDialog order={BARIS} run={run} onClose={() => {}} onDone={() => {}} />));
  await klik("release-confirm-submit");
  expect(document.body.textContent).toContain("Stok sudah dipakai pesanan lain.");
});

test("sample: Teruskan ke gudang di meja & di daftar lewat pop-up yang sama", async () => {
  const sos = { ref_type: "sample_order", ref_id: "sos1", number: "KSC/SOS-1", title: "Toko S", entity_id: "ent_ksc", age_days: 0,
    action: "Teruskan ke Gudang", action_kind: "confirm", order_lines: [{ product_name: "Sample A", quantity: 1, unit: "meter", warehouse: "" }] };
  routeGet({ "/sample-orders/desk": { queues: [{ id: "siap_gudang", label: "Siap", count: 1, value_kind: "count", rows: [sos] }] } });
  mockPost.mockResolvedValue({ data: { tasks_created: 1 } });
  await mount(wrapEnt(<SampleAdminDesk currentUser={{ permissions: { sample_order: ["view", "confirm"] } }} onOpenDocument={() => {}} />));
  await klik("sample-desk-action-sos1");
  expect(mockPost).not.toHaveBeenCalled();
  expect(teks(q("release-confirm-warehouse"))).toBe("—");
  await klik("release-confirm-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sample-orders/sos1/confirm");
});

test("orderLinesOf dari items pesanan", () => {
  expect(orderLinesOf({ items: [{ product_name: "K", sku: "S", quantity: 3, unit: "yard",
    allocations: [{ warehouse_name: "G1" }, { warehouse_name: "G1" }, { warehouse_name: "G2" }] }] }))
    .toEqual([{ product_name: "K", sku: "S", quantity: 3, unit: "yard", warehouse: "G1, G2" }]);
});

test("setiap pemanggil lepas/teruskan memakai ReleaseToWarehouseDialog", () => {
  const pola = /\breleaseOrder\(|\bconfirmSampleOrder\(/;
  const kecuali = ["features/sales_admin/workDeskApi.js", "features/samples/sampleApi.js"];
  const salah = berkasSumber().filter((f) => !kecuali.some((k) => f.endsWith(k)) && pola.test(baca(f))
    && !baca(f).includes("ReleaseToWarehouseDialog"));
  expect(salah).toEqual([]);
});
```
(`wrapEnt(el)` = `EntityScopeProvider selectedEntity="all" entities=[{id:"ent_ksc", short_name:"KSC"}]`; `SampleOrdersView` "Teruskan ke Gudang" ditutup oleh uji pemanggil di atas + regresi `f15`.)

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaKonfirmasiGudang.test.js` → FAIL (POST langsung).
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/mejaDeskFrame.test.js src/features/__tests__/f15SamplePaymentReapproval.test.js src/features/__tests__/a1AlurPesanan.test.js src/features/__tests__/trial22Okt.test.js src/features/__tests__/mobileShell.test.js` PASS; `$GUARD` bersih.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/sales_admin/ReleaseToWarehouseDialog.jsx frontend/src/features/sales_admin/SalesAdminDesk.jsx \
  frontend/src/features/orders/OrderDetailPanel.jsx frontend/src/features/sales/mobile/MobileOrders.jsx \
  frontend/src/features/sales/mobile/MobileSalesAdminDesk.jsx frontend/src/features/samples/SampleAdminDesk.jsx \
  frontend/src/features/samples/SampleOrdersView.jsx frontend/src/features/__tests__/mejaKonfirmasiGudang.test.js \
  frontend/src/features/__tests__/mejaDeskFrame.test.js
git commit -m "feat(meja): lepas dan teruskan ke gudang lewat pratinjau pesanan, PT, gudang, dan baris"
```

---

### Task 11: Setujui bayar sample — satu pemeriksaan uang masuk untuk daftar dan meja

**Files:**
- Create: `frontend/src/features/samples/samplePayment.js`
- Create: `frontend/src/features/samples/SamplePaymentApproveDialog.jsx`
- Modify: `frontend/src/features/samples/SampleOrdersView.jsx` (`sampleKurangBayar` :37-42 pindah, diekspor ulang; `setujuiBayar` :141-153 dan "Setujui Ulang" :284 → dialog; impor `askConfirm` dihapus bila tak terpakai)
- Modify: `frontend/src/features/samples/SampleAdminDesk.jsx` (`approve_payment` → dialog)
- Modify (uji lama): `frontend/src/features/__tests__/f15SamplePaymentReapproval.test.js` (klik `sample-detail-reapprove-payment` lalu `sample-approve-submit`)
- Test: `frontend/src/features/__tests__/mejaBayarSample.test.js`

**Interfaces:**
- Produces `samplePayment.js`: `sampleKurangBayar(o) → number` (perilaku sama persis dengan versi lama); `cekUangMasukSample(o) → { total: Number(o.grand_total) || 0, masuk: Number(o.paid_total) || 0, kurang: sampleKurangBayar(o) }`. `SampleOrdersView.jsx` mempertahankan `export { sampleKurangBayar } from "./samplePayment"`.
- Produces `SamplePaymentApproveDialog({ order, onClose, onDone, testId = "sample-approve" })`: `order = { id, number, title | customer_name, sample_billing, grand_total, paid_total, sample_payment_status }`; `FormModal` judul "Setujui pembayaran sample?" (ulang: "Setujui ulang tagihan sample?"); pratinjau `${testId}-total`, `${testId}-paid`, `${testId}-short-amount` (atau "lunas"); bila `kurang > 0`: kotak `${testId}-short` berbunyi pesan lama (`Uang yang tercatat masuk untuk {number} baru {masuk} dari {total} (kurang {kurang}). Tetap setujui pembayaran dan lepas ke gudang?`) dan tombol `${testId}-submit` "Tetap setujui" bergaya bahaya; selain itu "Setujui pembayaran"; kirim → `approveSamplePayment(order.id)`; galat di dalam; sukses → `onDone(hasil)`.
- Pemakai: meja (`row` membawa `sample_billing`, `grand_total`, `paid_total` dari Task 3) → `onDone` → `toast` pesan lama (`persetujuan ulang` → "tagihan baru disetujui — kiriman sample dilepas.") + `reloadQueue("bayar_sampel")`; daftar (`sel`) → `flash` + `load()` seperti sekarang.
- Aturan pemanggil: setiap berkas `src/**` (bukan uji, bukan `sampleApi.js`) yang memuat `approveSamplePayment(` juga memuat `SamplePaymentApproveDialog`.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaBayarSample.test.js` (pembantu `mount/q/teks/klik`
  seperti Task 4; `berkasSumber/baca` seperti Task 9; `use-toast` ditiru → `mockToast`; modul API sample ditiru utuh):

```javascript
// MEJA-11 — §5.4: setujui bayar sample = cek uang masuk + konfirmasi, sama di daftar & meja.
jest.mock("../samples/sampleApi", () => ({
  sampleDesk: jest.fn(), approveSamplePayment: jest.fn(), confirmSampleOrder: jest.fn(), listSampleOrders: jest.fn(),
  sampleStats: jest.fn().mockResolvedValue({}), cancelSampleOrder: jest.fn(),
}));
jest.mock("../samples/CatalogueCreateModal", () => () => null);
jest.mock("../samples/CatalogueComponents", () => () => null);
jest.mock("../samples/CuttingDesk", () => () => null);
jest.mock("../samples/CuttingLocations", () => () => null);
const api = require("../samples/sampleApi");
// impor: SampleAdminDesk, SampleOrdersView, SamplePaymentApproveDialog, { cekUangMasukSample } dari "../samples/samplePayment"

test("cekUangMasukSample", () => {
  expect(cekUangMasukSample({ sample_billing: "paid", grand_total: 83250, paid_total: 50000 }))
    .toEqual({ total: 83250, masuk: 50000, kurang: 33250 });
  expect(cekUangMasukSample({ sample_billing: "free", grand_total: 0 }).kurang).toBe(0);
});

test("meja: uang kurang → peringatan & 'Tetap setujui'; endpoint dipanggil sesudah konfirmasi", async () => {
  const baris = { ref_type: "sample_order", ref_id: "sos1", number: "KSC/SOS-1", title: "Toko S", age_days: 1, entity_id: "ent_ksc",
    action: "Setujui Bayar", action_kind: "approve_payment", sample_billing: "paid", grand_total: 83250, paid_total: 50000, badge: "waiting_approval" };
  api.sampleDesk.mockResolvedValue({ queues: [{ id: "bayar_sampel", label: "Bayar", count: 1, rows: [baris] }] });
  api.approveSamplePayment.mockResolvedValue({});
  await mount(<SampleAdminDesk currentUser={{ permissions: { sample_order: ["view", "approve_payment"] } }} onOpenDocument={() => {}} />);
  await klik("sample-desk-action-sos1");
  expect(api.approveSamplePayment).not.toHaveBeenCalled();
  expect(teks(q("sample-approve-short"))).toMatch(/kurang Rp\s?33\.250/);
  expect(teks(q("sample-approve-submit"))).toBe("Tetap setujui");
  await klik("sample-approve-submit");
  expect(api.approveSamplePayment).toHaveBeenCalledWith("sos1");
  expect(mockToast).toHaveBeenCalled();
});

test("lunas: tanpa peringatan, tombol 'Setujui pembayaran'", async () => {
  await mount(<SamplePaymentApproveDialog order={{ id: "s2", number: "SOS-2", sample_billing: "paid", grand_total: 10000, paid_total: 10000 }}
    onClose={() => {}} onDone={() => {}} />);
  expect(q("sample-approve-short")).toBeNull();
  expect(teks(q("sample-approve-submit"))).toBe("Setujui pembayaran");
});

test("daftar Pesanan Sample memakai pop-up yang sama (bukan askConfirm)", async () => {
  api.approveSamplePayment.mockClear();
  api.listSampleOrders.mockResolvedValue([{ id: "so1", number: "KSC/SOS-00029", customer_name: "Toko Kain Sejahtera",
    sample_billing: "paid", status: "waiting_approval", grand_total: 83250, paid_total: 50000, items: [], fulfillment_method: "kirim" }]);
  await mount(<SampleOrdersView user={{ role: "finance", permissions: { sample_order: ["view", "approve_payment"] } }}
    focusDoc={{ focus_type: "sample_order", focus_id: "so1" }} onClearFocus={() => {}} />);
  await klik("sample-detail-approve-payment");
  expect(q("sample-approve")).not.toBeNull();
  expect(q("sample-approve-short")).not.toBeNull();
  expect(api.approveSamplePayment).not.toHaveBeenCalled();
});

test("setiap pemanggil setujui bayar memakai SamplePaymentApproveDialog", () => {
  const salah = berkasSumber().filter((f) => !f.endsWith("features/samples/sampleApi.js") && /\bapproveSamplePayment\(/.test(baca(f))
    && !baca(f).includes("SamplePaymentApproveDialog"));
  expect(salah).toEqual([]);
});
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaBayarSample.test.js` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/f15SamplePaymentReapproval.test.js src/features/__tests__/latihVariasiHpg.test.js src/features/__tests__/decisionsD3.test.js src/features/__tests__/mejaKonfirmasiGudang.test.js` PASS; `$GUARD` bersih.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/samples/samplePayment.js frontend/src/features/samples/SamplePaymentApproveDialog.jsx \
  frontend/src/features/samples/SampleOrdersView.jsx frontend/src/features/samples/SampleAdminDesk.jsx \
  frontend/src/features/__tests__/f15SamplePaymentReapproval.test.js frontend/src/features/__tests__/mejaBayarSample.test.js
git commit -m "feat(meja): setujui bayar sample lewat satu pemeriksaan uang masuk dan konfirmasi di daftar dan meja"
```

---

### Task 12: Pop-up periksa & pemenuhan pindah ke `FormModal`

**Files:**
- Modify: `frontend/src/features/sales_admin/VerifyOrderDialog.jsx` (cangkang :63-67, :170-187; hapus `useEscapeClose` sendiri)
- Modify: `frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx` (cangkang :101-103 dan kaki)
- Test: `frontend/src/features/__tests__/mejaDialogFormModal.test.js`

**Interfaces:**
- Produces: kedua dialog dirender `<FormModal open onClose size="xl" testId="verify-dialog" | "fulfill-dialog" title subtitle icon error footer>`; testid lama tetap (`verify-dialog`, `verify-dialog-title`, `verify-cancel`, `verify-submit`, `verify-open-full`, `fulfill-dialog`, `fulfill-dialog-title`, …) — `*-title` kini dari `FormModal`; tombol "Buka Pesanan Lengkap" di baris pertama badan; galat aksi tetap di dalam pop-up. Isi (data pesanan, daftar periksa, kartu baris) tidak diubah — token isinya = gelombang 2.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaDialogFormModal.test.js`:

```javascript
// MEJA-12 — §5.3: pop-up periksa & pemenuhan memakai FormModal (INV-UI-11 turun), Esc menutup, aksi tetap sama.
// impor: VerifyOrderDialog, FulfillmentDecisionDialog ("../sales_admin/…"), fs, path
test("VerifyOrderDialog: cangkang FormModal, Esc menutup, kirim memanggil review-release", async () => {
  routeGet({ "/sales-orders/so1/verification": { verifiable: true, ready: true, checks: [], order_preview: null } });
  mockPost.mockResolvedValue({ data: { released: true, order: { number: "SO-1", status: "confirmed" } } });
  const onClose = jest.fn(); const onVerified = jest.fn();
  await mount(<VerifyOrderDialog orderId="so1" orderNumber="SO-1" customerName="Toko A" onClose={onClose} onVerified={onVerified} />);
  expect(q("verify-dialog").className).toContain("kn-form-modal");
  expect(teks(q("verify-dialog-title"))).toContain("SO-1");
  await klik("verify-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so1/review-release", { note: "", hold: false });
  await act(async () => { document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })); });
  expect(onClose).toHaveBeenCalled();
});

test("FulfillmentDecisionDialog: cangkang FormModal", async () => {
  routeGet({ "/sales-admin/orders/so1/fulfillment-plan": { lines: [] } });
  await mount(<FulfillmentDecisionDialog orderId="so1" orderNumber="SO-1" customerName="Toko A" onClose={() => {}} onDecided={() => {}} />);
  expect(q("fulfill-dialog").className).toContain("kn-form-modal");
  expect(q("fulfill-dialog-close")).not.toBeNull();
});

test("tanpa modal-card/modal-overlay buatan sendiri", () => {
  for (const rel of ["../sales_admin/VerifyOrderDialog.jsx", "../sales_admin/FulfillmentDecisionDialog.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/modal-card|modal-overlay/);
  }
});
```
(Pastikan URL rencana pemenuhan sesuai yang dimuat dialog — lihat `fulfillmentPlan` di `workDeskApi.js`.)

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaDialogFormModal.test.js` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/trial22Okt.test.js src/features/__tests__/uat24F2.test.js src/features/__tests__/phase4R1.test.js` PASS; `python3 scripts/guardrails/verify_custom_modals.py` menunjukkan dua berkas itu turun 1 → 0 (tanpa `--update`); `$GUARD` bersih.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/sales_admin/VerifyOrderDialog.jsx frontend/src/features/sales_admin/FulfillmentDecisionDialog.jsx \
  frontend/src/features/__tests__/mejaDialogFormModal.test.js
git commit -m "refactor(meja): pop-up periksa dan pemenuhan memakai FormModal baku"
```

---

### Task 13: Hapus ganda antar kartu (Keuangan, Giliran saya)

**Files:**
- Create: `frontend/src/features/desks/deskDedupe.js`
- Modify: `frontend/src/features/finance/FinanceDesk.jsx` (kelompok → `dedupeFinanceGroups` sebelum diurutkan)
- Modify: `frontend/src/features/desks/RoleDesk.jsx` (`humanizeQueueRows(dedupeTurnQueue(data.queues))`)
- Test: `frontend/src/features/__tests__/mejaDedupe.test.js`

**Interfaces:**
- Produces `dedupeFinanceGroups(groups) → groups` (masukan tidak diubah): bila kelompok `piutang_lewat_tempo` **dan** `uang_masuk` sama-sama ada: id pesanan Piutang = `r.order_id || r.ref_id`; baris `uang_masuk` dengan `order_id` di himpunan itu dihapus; tiap baris Piutang yang punya pasangan diberi `_moreActions: [{ label: "Terima pembayaran", row: <baris uang_masuk itu> }]`; `uang_masuk.count = max(0, count − terhapus)`, `total_value` = Σ nilai baris tersisa (2 desimal), `oldest_age_days` = maks `age_days` baris tersisa (0 bila kosong); kelompok yang menjadi 0 baris & 0 jumlah dibuang (Keuangan tidak menggambar kelompok kosong). Tanpa salah satu kelompok → tidak berubah.
- Produces `dedupeTurnQueue(queues) → queues`: baris `giliran_saya` yang kunci `` `${ref_type}:${ref_id}` ``-nya ada di antrean lain dihapus; `count` dikurangi; kartu tetap ada walau kosong.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaDedupe.test.js` (pembantu & tiruan seperti Task 6, ditambah
  `jest.mock("../finance/payments/ReceivePaymentModal", () => (p) => <div data-testid="rpm-stub">{p.preselectOrderId}</div>)`):

```javascript
// MEJA-13 — §5.6 hapus ganda, Review Focus #5.
// impor: { dedupeFinanceGroups, dedupeTurnQueue } dari "../desks/deskDedupe", FinanceDesk, RoleDesk
const UM = (oid, lewat, extra = {}) => ({ ref_type: "customer", ref_id: "cus1", row_key: oid, order_id: oid, number: oid, title: "Toko A",
  value: 100, age_days: lewat ? 8 : 0, age_kind: lewat ? "overdue" : "wait", badge: lewat ? "lewat" : "segera",
  action: "Terima pembayaran", action_kind: "receipt", _queue: "uang_masuk", ...extra });
const JT = (oid) => ({ ref_type: "sales_order", ref_id: oid, order_id: oid, customer_id: "cus1", number: oid, title: "Toko A",
  value: 100, age_days: 8, age_kind: "overdue", badge: "lewat", action: "Tagih", action_kind: "open", _queue: "jatuh_tempo" });
const G = (id, rows, count = rows.length) => ({ id, label: id, rows, count, total_value: rows.length * 100,
  oldest_age_days: Math.max(0, ...rows.map((r) => r.age_days)) });

test("kedua kartu terlihat: lewat tempo hanya di Piutang, dengan Terima pembayaran; Uang masuk dihitung ulang", () => {
  const out = dedupeFinanceGroups([G("uang_masuk", [UM("so1", true), UM("so2", false)]), G("piutang_lewat_tempo", [JT("so1")])]);
  const um = out.find((g) => g.id === "uang_masuk"); const pt = out.find((g) => g.id === "piutang_lewat_tempo");
  expect(um.rows.map((r) => r.order_id)).toEqual(["so2"]);
  expect([um.count, um.total_value, um.oldest_age_days]).toEqual([1, 100, 0]);
  expect(pt.rows[0]._moreActions).toEqual([{ label: "Terima pembayaran", row: expect.objectContaining({ order_id: "so1", action_kind: "receipt" }) }]);
});

test("kartu Piutang tidak terlihat (tanpa izin): lewat tempo tetap di Uang masuk", () => {
  const masuk = [G("uang_masuk", [UM("so1", true)])];
  expect(dedupeFinanceGroups(masuk)).toEqual(masuk);
});

test("Uang masuk tidak terlihat: Piutang tanpa 'Terima pembayaran'", () => {
  const out = dedupeFinanceGroups([G("piutang_lewat_tempo", [JT("so1")])]);
  expect(out[0].rows[0]._moreActions).toBeUndefined();
});

test("Uang masuk habis → kelompoknya tidak digambar", () => {
  const out = dedupeFinanceGroups([G("uang_masuk", [UM("so1", true)]), G("piutang_lewat_tempo", [JT("so1")])]);
  expect(out.map((g) => g.id)).toEqual(["piutang_lewat_tempo"]);
});

test("Giliran saya tidak mengulang dokumen antrean lain; kartu tetap ada walau kosong", () => {
  const out = dedupeTurnQueue([{ id: "giliran_saya", count: 1, rows: [{ ref_type: "sales_order", ref_id: "so_1" }] },
                               { id: "so_acc", count: 1, rows: [{ ref_type: "sales_order", ref_id: "so_1" }] }]);
  expect(out[0]).toMatchObject({ id: "giliran_saya", count: 0, rows: [] });
});

test("FinanceDesk: pop-up Piutang menawarkan Terima pembayaran → ReceivePaymentModal", async () => {
  const tanpaQueue = ({ _queue, ...r }) => r;   // baris server belum ber-`_queue` (ditambah FinanceDesk)
  routeGet({ "/finance/desk": { queues: [
    { id: "uang_masuk", count: 1, rows: [tanpaQueue(UM("so1", true))] },
    { id: "jatuh_tempo", count: 1, rows: [tanpaQueue(JT("so1"))] }], not_my_desk: [] } });
  await mount(<FinanceDesk currentUser={{ permissions: { payment_variance: ["decide"], ar_receipt: ["create"], accounting: ["view"] } }}
    selectedEntity="ent_ksc" />);
  expect(q("fin-desk-uang_masuk-row-so1")).toBeNull();
  await klik("fin-desk-piutang_lewat_tempo-row-so1");
  expect(teks(q("fin-desk-detail-action-0"))).toContain("Terima pembayaran");
  await klik("fin-desk-detail-action-0");
  expect(teks(q("rpm-stub"))).toBe("so1");
});

test("RoleDesk: satu dokumen hanya sekali", async () => {
  routeGet({ "/desks/me": { queues: [
    { id: "giliran_saya", label: "Giliran saya", count: 1, value_kind: "count", rows: [{ ref_type: "sales_order", ref_id: "so_1", number: "SO-1", title: "G", age_days: 0, action: "Buka" }] },
    { id: "so_acc", label: "ACC", count: 1, rows: [{ ref_type: "sales_order", ref_id: "so_1", number: "SO-1", title: "Toko", age_days: 0, action: "Putuskan" }] }] } });
  await mount(<RoleDesk desk="me" currentUser={{ permissions: {} }} onOpenDocument={() => {}} />);
  expect(document.body.querySelectorAll('[data-testid="my-desk-row-so_1"]')).toHaveLength(1);
  expect(teks(q("my-desk-count-giliran_saya"))).toBe("0");
  expect(q("my-desk-queue-giliran_saya").className).toContain("sm:h-[404px]");
});
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaDedupe.test.js` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/mnt2LayarKeuangan.test.js src/features/__tests__/financeDeskTidy.test.js src/features/__tests__/phase4R6.test.js src/features/__tests__/mejaDeskFrame.test.js` PASS; `$GUARD` bersih.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/desks/deskDedupe.js frontend/src/features/finance/FinanceDesk.jsx \
  frontend/src/features/desks/RoleDesk.jsx frontend/src/features/__tests__/mejaDedupe.test.js
git commit -m "feat(meja): satu baris hanya di satu kartu — piutang lewat tempo dan giliran saya tidak berulang"
```

---

### Task 14: "Cetak" di tempat dan "Buat SPK QC" dengan pesanan terpilih

**Files:**
- Create: `frontend/src/features/documents/orderPrintDocs.js`
- Create: `frontend/src/features/documents/OrderPrintModal.jsx`
- Modify: `frontend/src/features/orders/OrderDetailPanel.jsx` (:210-223 `docs` → `ORDER_PRINT_DOCS`)
- Modify: `frontend/src/features/sales_admin/SalesAdminDesk.jsx` (`print` di tempat)
- Modify: `frontend/src/features/inspections/InspectionFormModal.jsx` (props awal)
- Modify: `frontend/src/features/desks/RoleDesk.jsx` (`create_qc_spk` di tempat untuk `warehouse_admin`)
- Test: `frontend/src/features/__tests__/mejaCetakSpk.test.js`

**Interfaces:**
- Produces `ORDER_PRINT_DOCS = [{ docType: "picking_list", label: "Surat Pengambilan Barang" }, { docType: "packing_list", label: "Daftar Kemasan" }, { docType: "delivery_note", label: "Surat Jalan Pengiriman" }, { docType: "invoice", label: "Faktur Komersial" }]` (dipakai `OrderDetailPanel` dan `OrderPrintModal`).
- Produces `OrderPrintModal({ order: { id, number, title, entity_id }, currentUser, onClose })` → `<DetailModal framed size="md" testId="order-print">` berjudul `` `Cetak dokumen · ${number}` `` (`order-print-title`) berisi `<RelatedDocsPanel title="Cetak Dokumen · Gudang & Penagihan" docs={ORDER_PRINT_DOCS} sourceId={id} entityId={entity_id} number={number} currentUser={currentUser} />`.
- Admin Sales: `inPlace` + `"print"`; aksi → `OrderPrintModal`; tanpa navigasi.
- Produces `InspectionFormModal({ open, onClose, onCreated, meta, orphanTasks = [], initialKind = "return_customer", initialRefId = "" })`: saat `open` menjadi benar, `kind = initialKind`, `refId = initialRefId`; pengosongan `refId/taskId` hanya saat pengguna mengganti jenis (penangan `pilihJenis`), bukan efek `[kind]`.
- Gudang: `inPlace` = `inPlaceOf(can(perms, "inspection", "create") ? ["create_qc_spk"] : [])`; aksi → `inspectionsMeta(selectedEntity)` lalu `<InspectionFormModal open meta initialKind="sales_order" initialRefId={row.ref_id} onCreated={(doc) => { toast({ title: `SPK QC ${doc?.number || ""} untuk ${row.number} diterbitkan.` }); reloadQueue("qc_pesanan"); }} />`; tanpa izin → pop-up rincian dengan "Buka layar penuh" (daftar Inspeksi).

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaCetakSpk.test.js` (pembantu & tiruan seperti Task 6, `routeGet`
  mencocokkan kunci terpanjang dulu; tiruan `RelatedDocsPanel` → `(p) => <div data-testid="rdp-stub" data-source={p.sourceId}>{p.docs.map((d) => d.docType).join(",")}</div>`):

```javascript
// MEJA-14 — §5.6: Cetak membuka pop-up dokumen pesanan; Buat SPK QC membuka pembuatan SPK dengan pesanan terpilih.
// impor: SalesAdminDesk, RoleDesk
test("Cetak: pop-up dokumen pesanan di tempat, tanpa pindah ke daftar Pesanan", async () => {
  const open = jest.fn();
  routeGet({ "/sales-admin/desk": { queues: [{ id: "siap_cetak_dokumen", label: "Siap cetak", count: 1, rows: [
    { ref_type: "sales_order", ref_id: "so9", number: "SO-9", title: "Toko C", entity_id: "ent_ksc", age_days: 1,
      action: "Cetak", action_kind: "print" }] }] } });
  await mount(<SalesAdminDesk currentUser={{ permissions: { order: ["view", "confirm"] } }} onOpenDocument={open} />);
  await klik("desk-action-so9");
  expect(open).not.toHaveBeenCalled();
  expect(teks(q("order-print-title"))).toContain("SO-9");
  expect(q("rdp-stub").getAttribute("data-source")).toBe("so9");
  expect(teks(q("rdp-stub"))).toBe("picking_list,packing_list,delivery_note,invoice");
});

const WH = { "/warehouse-admin/desk": { queues: [{ id: "qc_pesanan", label: "QC", count: 1, value_kind: "count", rows: [
    { ref_type: "sales_order", ref_id: "so5", number: "SO-5", title: "Toko Q", entity_id: "ent_ksc", age_days: 0,
      action: "Buat SPK QC", action_kind: "create_qc_spk", link_view: "inspections" }] }] },
  "/inspections/meta/ref-docs": { items: [{ value: "so5", label: "SO-5 · Toko Q" }] },
  "/inspections/meta": { kinds: [{ value: "sales_order", label: "QC Permintaan Pesanan (SO)" }], officers: [] } };

test("Buat SPK QC: pembuatan SPK terbuka dengan jenis QC Pesanan dan pesanan terpilih", async () => {
  routeGet(WH);
  mockPost.mockResolvedValue({ data: { id: "ins1", number: "INS-1" } });
  await mount(<RoleDesk desk="warehouse_admin" currentUser={{ permissions: { wms: ["view"], inspection: ["create"] } }} onOpenDocument={() => {}} />);
  await klik("wh-desk-action-so5");
  expect(q("ins-kind-select").value).toBe("sales_order");
  expect(q("ins-ref-select").value).toBe("so5");
  await klik("ins-create-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/inspections", expect.objectContaining({ kind: "sales_order", ref_doc_id: "so5" }));
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: expect.stringContaining("SO-5") }));
});

test("tanpa izin inspection.create: aksi membuka rincian, bukan pembuatan SPK", async () => {
  routeGet(WH);
  await mount(<RoleDesk desk="warehouse_admin" currentUser={{ permissions: { wms: ["view"] } }} onOpenDocument={() => {}} />);
  await klik("wh-desk-action-so5");
  expect(q("ins-create-modal")).toBeNull(); expect(q("wh-desk-detail")).not.toBeNull();
});
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaCetakSpk.test.js` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/latihS1Amandemen.test.js src/features/__tests__/decisionsD4.test.js src/features/__tests__/pk44JejakDokumen.test.js src/features/__tests__/mejaDeskFrame.test.js` dan uji inspeksi yang ada (`grep -l InspectionFormModal frontend/src -r --include=*.test.js`) PASS; `$GUARD` bersih (`verify_desk_targets` tetap hijau).
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/documents/orderPrintDocs.js frontend/src/features/documents/OrderPrintModal.jsx \
  frontend/src/features/orders/OrderDetailPanel.jsx frontend/src/features/sales_admin/SalesAdminDesk.jsx \
  frontend/src/features/inspections/InspectionFormModal.jsx frontend/src/features/desks/RoleDesk.jsx \
  frontend/src/features/__tests__/mejaCetakSpk.test.js
git commit -m "feat(meja): Cetak membuka dokumen pesanan di tempat; Buat SPK QC dengan pesanan terpilih"
```

---

### Task 15: Meja Cutting memakai `DeskQueueCard` dengan pelanggan dan SKU

**Files:**
- Modify: `frontend/src/features/samples/CuttingDesk.jsx`
- Create: `frontend/src/features/samples/CuttingReceiveDialog.jsx`
- Modify (uji lama): `frontend/src/features/__tests__/phase3P3b.test.js` (:187 `cutting-receive-t9` → `cutting-action-t9`)
- Test: `frontend/src/features/__tests__/mejaCutting.test.js`

**Interfaces:**
- Produces `toCuttingQueues(data, { canReceive }) → Queue[]` (ekspor bernama `CuttingDesk.jsx`) untuk kunci `awaiting_internal`, `to_receive`, `ready` (urutan server; `to_cut` tetap `ToCutSummary`, keputusan D-24a): baris `{ ref_type: "wms_task", ref_id: r.task_id, row_key: r.task_id, number: r.order_number, title: r.customer_name || "—", subtitle: [produk · SKU, jenis sample, `${formatQty(qty)} ${unit}`, gudang, info potongan/roll, stok PT lain, diterima oleh, menunggu transfer].filter(Boolean).join(" · "), value: Number(r.quantity) || 0, unit: r.unit, age_days: Math.floor((r.wait_minutes || 0) / 1440), at: r.cut_at || "", entity_id: r.roll_owner_entity_id || "", order_id: r.order_id, warehouse_id: r.warehouse_id, roll_owner_entity_id: r.roll_owner_entity_id, action: key === "to_receive" && canReceive ? "Terima" : "", action_kind: "receive_cut" }`; antrean `{ id: key, label, count: rows.length, value_kind: "qty", value_label: "Qty", action_label: "", rows }`.
- `CuttingDesk`: grid `DESK_GRID_CLASS` berisi `ToCutSummary` + `DeskQueueCard testPrefix="cutting" stateKey={`cutting:${id}`} inPlace={inPlaceOf(["receive_cut"])}`; paragraf → `HelpTip` `cutting-desk-help`; `cutting-late-alert` & `ListLimitNote` tetap (token); muat ulang otomatis 60 dtk tetap.
- Produces `CuttingReceiveDialog({ row, locations, siblings, onClose, onDone })` — `FormModal` "Terima hasil potong"; `KNSelect` `cutting-dest` (opsi = `destFor(locations, row.roll_owner_entity_id)`, bawaan `row.warehouse_id`); bila `siblings > 1` kotak centang `cutting-receive-all` "Terima semua potongan {number} ({siblings} baris)"; kirim → `receiveOrderCuts(order_id, dest)` (centang) atau `receiveCut(task_id, dest)`; `transfer_required` → `onDone(pesan)` sebagai toast; `failed` → galat di dalam pop-up.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaCutting.test.js` (pembantu & tiruan `apiClient`/`KNSelect` seperti
  Task 6; `fs`/`path` diimpor):

```javascript
// MEJA-15 — §5.6: Meja Cutting memakai DeskQueueCard; pelanggan & SKU tampil; terima hasil potong lewat pop-up.
// impor: CuttingDesk ("../samples/CuttingDesk")
const DATA = { wait_thresholds: { warn_minutes: 60, late_minutes: 240 }, late_count: 0, queues: [
  { key: "to_cut", label: "Menunggu dipotong gudang", rows: [] },
  { key: "to_receive", label: "Hasil potong — menunggu diterima", rows: [
    { task_id: "t9", order_id: "o1", order_number: "SOS-9", customer_name: "Butik Melati", product_name: "Kain Batik", sku: "KB-9",
      sample_kind: "standard", quantity: 1.5, unit: "meter", warehouse_id: "w1", warehouse_name: "Gudang A", wait_minutes: 30,
      roll_owner_entity_id: "ent_ksc", cut_at: "2026-11-25T02:00:00Z" },
    { task_id: "t10", order_id: "o1", order_number: "SOS-9", customer_name: "Butik Melati", product_name: "Kain Lurik", sku: "KL-1",
      sample_kind: "standard", quantity: 1, unit: "meter", warehouse_id: "w1", warehouse_name: "Gudang A", wait_minutes: 20,
      roll_owner_entity_id: "ent_ksc" }] }] };

test("baris menyebut pelanggan; rincian menyebut SKU; kartu ukuran tetap", async () => {
  routeGet({ "/cutting/desk": DATA, "/cutting/locations": [{ id: "w1", name: "Gudang A" }] });
  await mount(<CuttingDesk canReceive />);
  expect(teks(q("cutting-title-t9"))).toBe("Butik Melati");
  expect(q("cutting-queue-to_receive").className).toContain("sm:h-[404px]");
  await klik("cutting-row-t9");
  expect(teks(q("cutting-detail-field-subtitle"))).toMatch(/Kain Batik · KB-9/);
});

test("Terima: pop-up lokasi + terima semua potongan pesanan", async () => {
  routeGet({ "/cutting/desk": DATA, "/cutting/locations": [{ id: "w1", name: "Gudang A" }] });
  mockPost.mockResolvedValue({ data: { received: 2, failed: [] } });
  await mount(<CuttingDesk canReceive />);
  await klik("cutting-action-t9");
  expect(mockPost).not.toHaveBeenCalled();
  await klik("cutting-receive-all");
  await klik("cutting-receive-submit");
  expect(mockPost).toHaveBeenCalledWith("/api/cutting/orders/o1/receive", { to_warehouse_id: "w1" });
});

test("tanpa izin terima: tidak ada tombol aksi", async () => {
  routeGet({ "/cutting/desk": DATA, "/cutting/locations": [] });
  await mount(<CuttingDesk canReceive={false} />);
  expect(q("cutting-action-t9")).toBeNull();
});

test("tanpa px mentah & hex", () => {
  for (const rel of ["../samples/CuttingDesk.jsx", "../samples/CuttingReceiveDialog.jsx"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/text-\[\d/); expect(src).not.toMatch(/#[0-9A-Fa-f]{6}\b/);
  }
});
```
(`submitTestId="cutting-receive-submit"` pada `FormModal`.)

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaCutting.test.js` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/phase3P3b.test.js src/features/__tests__/f15SamplePaymentReapproval.test.js` PASS; `$GUARD` bersih (`CuttingDesk.jsx` `id_fallback`/`hex`/`font_lt12` hanya turun).
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/samples/CuttingDesk.jsx frontend/src/features/samples/CuttingReceiveDialog.jsx \
  frontend/src/features/__tests__/phase3P3b.test.js frontend/src/features/__tests__/mejaCutting.test.js
git commit -m "feat(meja): Meja Cutting memakai kartu antrean bersama dengan pelanggan dan SKU"
```

---

### Task 16: HP — baris Admin Sales bisa disentuh, huruf ≥ 12 px

**Files:**
- Modify: `frontend/src/features/sales/mobile/MobileSalesAdminDesk.jsx`
- Modify: `frontend/src/features/sales/mobile/MobileMdViews.jsx` (fungsi `MobileMdDesk` :35-95 saja)
- Test: `frontend/src/features/__tests__/mejaHp.test.js`

**Interfaces:**
- Consumes: `DeskRowDetail` (Task 4), `ReleaseToWarehouseDialog` (Task 10, sudah terpasang), `inPlaceOf` (Task 5).
- Produces `MobileSalesAdminDesk`: `DeskRow` = `div role="button" tabIndex={0}` (`m-desk-row-${queue.id}-${rk}`), sentuh/Enter → `DeskRowDetail testPrefix="m-desk"` (`inPlace={inPlaceOf(["verify", "fulfill", "release"])}`, `onAction={handleAction}`, `onOpenFull={(row, queue) => openRow(row, queue)}`); tombol aksi `stopPropagation`; teks tetap terpotong di baris, utuh di pop-up; paragraf alur + kotak `m-desk-not-mine` → `HelpTip` `m-desk-help` di samping `h2` (isi: alur + "Bukan wewenang meja ini: …" dari `not_my_desk`); toast hasil (`m-desk-toast` dihapus); kartu tetap bisa dibuka-tutup (`m-desk-queue-toggle-*`); semua ukuran `text-[Npx]` → `text-fs-12`/`text-fs-13` (kartu angka tetap ada, label `text-fs-12`, nilai `text-fs-13`).
- Produces `MobileMdDesk`: ukuran < 12 px → `text-fs-12`; `text-[12.5px]`/`[13px]` → `text-fs-13`; `text-[20px]` → `text-fs-20`; perilaku tidak berubah.

- [ ] **Step 1: Tulis uji gagal** `frontend/src/features/__tests__/mejaHp.test.js` (tiruan: `VerifyOrderDialog` → `(p) => <div data-testid="verify-stub">{p.orderId}</div>`, `FulfillmentDecisionDialog` → `null`, `KeepPendingPanel` → `null`, `use-toast`):

```javascript
// MEJA-16 — §5.8: baris HP bisa disentuh → pop-up rincian yang sama; huruf ≥ 12 px; kartu tetap bisa dibuka-tutup.
// impor: MobileSalesAdminDesk ("../sales/mobile/MobileSalesAdminDesk"), fs, path
const PANJANG = "Alamat kirim pindah ke gudang baru di Jl. Raya Soekarno-Hatta 117, minta telepon dulu sebelum antar.";
const DESK = { not_my_desk: ["Faktur Pajak keluaran"], queues: [{ id: "perlu_verifikasi", label: "Perlu diperiksa", count: 1, rows: [
  { ref_type: "sales_order", ref_id: "so1", number: "SO-1", title: "Toko A", subtitle: PANJANG, age_days: 1, value: 1000,
    action: "Periksa & lepas", action_kind: "verify", entity_id: "ent_ksc" }] }] };

test("sentuh baris → rincian utuh; tombol aksi tidak membuka rincian", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" />);
  await klik("m-desk-row-perlu_verifikasi-so1");
  expect(q("m-desk-detail-field-subtitle").textContent).toContain(PANJANG);
  await act(async () => { q("m-desk-detail-close-x").click(); });
  await klik("m-desk-action-perlu_verifikasi-so1");
  expect(q("m-desk-detail")).toBeNull(); expect(teks(q("verify-stub"))).toBe("so1");
});

test("kartu tetap bisa dibuka-tutup; ? menggantikan kotak 'Meja Finance'", async () => {
  routeGet({ "/sales-admin/desk": DESK });
  await mount(<MobileSalesAdminDesk selectedEntity="ent_ksc" />);
  expect(q("m-desk-not-mine")).toBeNull();
  await klik("m-desk-help");
  expect(teks(q("m-desk-help-text"))).toMatch(/Bukan wewenang meja ini: Faktur Pajak keluaran/);
  expect(document.body.textContent).not.toContain("Meja Finance");
  await klik("m-desk-queue-toggle-perlu_verifikasi");
  expect(q("m-desk-row-perlu_verifikasi-so1")).toBeNull();
});

test("huruf ≥ 12 px di meja HP Admin Sales & HP MD", () => {
  const as = fs.readFileSync(path.join(__dirname, "../sales/mobile/MobileSalesAdminDesk.jsx"), "utf8");
  expect(as).not.toMatch(/text-\[\d/);
  const md = fs.readFileSync(path.join(__dirname, "../sales/mobile/MobileMdViews.jsx"), "utf8");
  const blok = md.slice(md.indexOf("export function MobileMdDesk"), md.indexOf("export const mdRowTarget"));
  expect(blok).not.toMatch(/text-\[(?:\d|1[01])(?:\.\d+)?px\]/);
});
```

- [ ] **Step 2: Jalankan, harus GAGAL** — `$JEST src/features/__tests__/mejaHp.test.js` → FAIL.
- [ ] **Step 3: Terapkan** sesuai Interfaces.
- [ ] **Step 4: Jalankan, harus LULUS** — berkas uji PASS; regresi `$JEST src/features/__tests__/mobileShell.test.js src/features/__tests__/mejaKonfirmasiGudang.test.js` dan uji HP MD yang ada (`grep -l MobileMdDesk -r frontend/src --include=*.test.js`) PASS; `$GUARD` bersih.
- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/sales/mobile/MobileSalesAdminDesk.jsx frontend/src/features/sales/mobile/MobileMdViews.jsx \
  frontend/src/features/__tests__/mejaHp.test.js
git commit -m "feat(meja): baris meja HP bisa disentuh ke rincian utuh; huruf HP minimal 12 px"
```

---

### Task 17: Standar `04_POLA_UI.md`, uji penuh, gate, tangkapan, laporan — lalu BERHENTI

**Files:**
- Modify: `docs/blueprint/04_POLA_UI.md` (§1 butir 6, §2.B, §3, §4)
- Create: `docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/tangkap_meja.py`, tangkapan `sesudah_*.png`, `gate_akhir.log`, `tests_mem_penuh.log`, `jest_penuh.log`
- Create: `docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil.md`

**Interfaces:**
- Produces `04_POLA_UI.md` (catat asal: "keputusan pemilik 25 Nov, rancangan `2026-11-25-meja-kerja-di-tempat-design.md`"):
  - §1 butir 6 → "Rincian dari daftar meja = pop-up `DetailModal` (klik baris); pesan hasil aksi tampil di pop-up aksi atau toast, tidak di puncak halaman."
  - §2.B → kartu ukuran tetap 5 baris (`sm:h-[404px]`) termasuk kosong & memuat, grid tidak meregang; baris ringkas dua baris teks (nomor + pihak · satu lencana + umur · nilai + satu aksi) yang bisa diklik/Enter; satu kepala (TopBar) + ikon ? di samping judul; tab **Antrean**/**Pantau** (Pantau: Pelacak SO, Keep & Pending, Aturan Grade, retur internal, antrean pantauan; boleh ditindak bila berizin) — termasuk Meja Keuangan di hub Beranda Keuangan; tanpa kartu angka; urutan kartu mendesak → kosong; komponen `DeskFrame` + `DeskQueueCard` + `DeskRowDetail`.
  - §3 baris huruf → "12–13 px; label kolom 12 px semi-tebal tanpa huruf besar; minimum 12 px untuk semua teks".
  - §4 → hapus larangan pop-up untuk rincian meja; larangan pop-up buatan sendiri tetap; kartu buka-tutup diperbolehkan di HP saja (desktop tetap terbuka, ukuran tetap).

- [ ] **Step 1: Perbarui `04_POLA_UI.md`** sesuai Interfaces; `git diff docs/blueprint/04_POLA_UI.md` hanya menyentuh empat bagian itu.
- [ ] **Step 2: Penjaga** — `$GUARD` + `python3 scripts/check_nav_map.py` → tanpa pelanggaran baru; catat penurunan per berkas (`custom_modals`, `font_lt12`, `hex`) di laporan. Jangan menjalankan `--update`.
- [ ] **Step 3: Uji penuh sekali di pohon akhir (di latar)**

```bash
cd /home/user/KNHOST/backend && /tmp/claude-0/-home-user-KNHOST/eae71b8b-a870-5a6b-a6d8-0d7c84ba5037/scratchpad/venv/bin/python \
  -m pytest tests_mem -q -p no:cacheprovider > ../docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/tests_mem_penuh.log 2>&1
cd /home/user/KNHOST/frontend && (ulimit -s 65536; CI=true node --stack-size=16000 node_modules/@craco/craco/dist/scripts/test.js \
  --watchAll=false) > ../docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/jest_penuh.log 2>&1
```
Expected: tidak ada kegagalan baru dibanding garis dasar lingkungan (`03_LINGKUNGAN_UJI.md` §6: suite jest yang gagal dimuat karena `cmdk`/`@radix-ui`, `phase4R2` stack babel, `odItemCancel` teks terpecah). Kegagalan lain diperbaiki di tugas pemiliknya, lalu hanya berkas uji itu yang diulang.

- [ ] **Step 4: Gate sekali + banding per pelanggaran**

```bash
cd /home/user/KNHOST && bash scripts/gate.sh --quick > docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/gate_akhir.log 2>&1; \
  git checkout -- memory/GATE_RECEIPT.md memory/GATE_RECEIPT.json
python3 scripts/blueprint/bandingkan_pelanggaran_gate.py \
  docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/gate_awal.log docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/gate_akhir.log
```
Expected: exit 0 (tidak ada pelanggaran baru). Pelanggaran baru = merah, diperbaiki, gate diulang sekali.

- [ ] **Step 5: Tangkapan sesudah** — tulis `tangkap_meja.py` (pola `scripts/ui_smoke.py`: `PLAYWRIGHT_BROWSERS_PATH=/pw-browsers`, `wait_until="domcontentloaded"`, tunggu selektor testid, jangan `networkidle`). Garis besar:
  - aplikasi lokal `docker compose -f docker-compose.dev.yml up -d` + data acuan `bash scripts/dev_restore_demo.sh`; basis `http://localhost:3000`;
  - akun (sandi `demo12345`, isian `login-email-input`/`login-password-input`/`login-submit-button`): `salesadmin@` → `?view=sales-admin-desk` (`desk-tabs`), `finance@` → `?view=finance-desk` (`fin-desk-tabs`), `manager@` → `?view=my-desk` (`my-desk-tabs`), `md@` → `?view=md-desk`, `wh.admin@` → `?view=warehouse-admin-desk`, `sampleadmin@` → `?view=sample-admin-desk`, `sales@` → `?view=my-desk`;
  - per akun pada 1440×900: halaman penuh tab Antrean (`sesudah_<meja>_1440.png`), pop-up baris pertama (klik `[data-testid*="-row-"]` pertama → `sesudah_<meja>_popup.png`), tab Pantau (`sesudah_<meja>_pantau.png`), konfirmasi aksi besar bila ada barisnya (faktur pajak, lepas ke gudang, setujui bayar sample, teruskan ke gudang);
  - 390×844: `salesadmin@` tab Meja HP (`m-sales-admin-desk`) + pop-up baris, `md@` (`m-md-desk`) → `sesudah_hp_<meja>.png`;
  - catat tinggi halaman tiap meja (`document.documentElement.scrollHeight`) untuk dibandingkan dengan Lampiran B audit.
  Bila lingkungan A sibuk/rusak, catat apa adanya di laporan (jangan menandai selesai tanpa tangkapan; minta pengendali).
- [ ] **Step 6: Laporan** `docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil.md`: commit awal & akhir; tabel tugas → commit → uji; angka `tests_mem`/jest apa adanya (merah ditulis merah); hasil penjaga & gate (per pelanggaran); tangkapan sebelum (`docs/audit/meja-2026-11-25/tangkapan/01–10`, sah bila Task 1 Step 0 tidak menemukan perubahan berkas meja) ↔ sesudah, serta tinggi halaman; keputusan builder untuk diperiksa pemilik — spesifikasi §9 butir 1–8 ditambah: (a) ikon ? halaman ditaruh di `TopBar` lewat `PageHelpContext`; (b) tab Antrean/Pantau di Meja Keuangan = tab tingkat ketiga bagi admin/manajer; (c) label nilai kartu ("Total (termasuk PPN)") pindah ke `title` kepala dan pop-up; (d) "Menunggu dipotong gudang" di Meja Cutting tetap ringkasan (D-24a); (e) Meja Keuangan tetap tidak menggambar kelompok kosong; (f) kartu angka HP tetap ada; (g) isi `VerifyOrderDialog`/`FulfillmentDecisionDialog` belum ditokenkan (gelombang 2); (h) konfirmasi lepas/teruskan juga di rincian pesanan, HP Pesanan, dan daftar Pesanan Sample; (i) Terbitkan denda tetap pindah ke Rencana & Denda yang sudah ber-`askConfirm` sampai gelombang 2; (j) tombol muat ulang global kini juga memuat ulang meja.
- [ ] **Step 7: Commit**

```bash
git add docs/blueprint/04_POLA_UI.md docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil.md \
  docs/superpowers/plans/2026-11-25-meja-gelombang-1-hasil/
git commit -m "docs(meja): standar pola meja diperbarui, hasil gelombang 1 dan tangkapan sebelum/sesudah"
```

- [ ] **Step 8: BERHENTI untuk validasi pemilik.** Jangan memulai gelombang 2 (§5.7, §5.7a). Kirim ringkasan + tautan laporan
  dan tangkapan ke pengendali; status = "selesai, menunggu validasi pemilik".
