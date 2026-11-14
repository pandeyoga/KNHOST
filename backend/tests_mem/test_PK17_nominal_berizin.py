"""PK-17 — nominal keuangan hanya untuk yang berizin (docs/blueprint/unit/PK-17.md, uji U1–U14, U18).

Persiapan bersama (fixture `siap`, disisipkan langsung ke database = FIXTURE, bukan alur):
  * `po_x` PO 25.000.000 (ent_ksc);
  * `vb_x` tagihan pemasok 27.500.000 berstatus `pending_approval`, bertaut ke `po_x` (relasi `parent` lewat
    `doc_refs_service.link`, satu-satunya jalur penaut);
  * `vb_y` tagihan terposting 12.000.000; `cb_x` kontrabon `submitted` berisi `vb_y` (`applied_amount` 12.000.000)
    dan potongan 2.000.000 → bersih 12.000.000 − 2.000.000 = 10.000.000;
  * akun berperan `driver` (Sopir), `warehouse`, `finance` — semuanya di `ent_ksc`.
Urutan uji penting (satu database per modul): U14 mengubah matriks tersimpan peran `warehouse` lalu memulihkannya.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import bootstrap
from services import doc_refs_service as refs

pytestmark = pytest.mark.anyio

JT = 1_000_000
ADMIN_EMAIL = "admin@kainnusantara.id"
PESAN_PAPAN = ("Anda belum punya akses untuk melihat antrean hutang pemasok. Minta Admin menambahkan akses "
               "'Hutang Supplier & Kontrabon'.")
PESAN_REKENING = ("Anda belum punya akses untuk mengelola rekening kas dan bank. Minta Admin menambahkan akses "
                  "'Kas, Bank & Kasus Keuangan'.")
SKRIP = Path(__file__).resolve().parents[2] / "scripts" / "apply_pk17_role_cleanup.py"
PASANGAN_GUDANG = ("vendor_bill", "landed_cost", "input_tax")
SEKARANG = "2026-11-13T02:00:00+00:00"


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


def _simpul(nodes, doc_id):
    return next(n for n in nodes if n.get("doc_id") == doc_id)


@pytest.fixture(scope="module")
async def siap(db, akun, sesi, peran_sopir):
    await db.suppliers.insert_one({"id": "sup_pk17", "code": "PK17", "name": "Pemasok PK17", "entity_id": "ent_ksc",
                                   "invoice_exchange": {"mode": "none"}, "created_at": SEKARANG})
    await db.purchase_orders.insert_one({
        "id": "po_x", "po_number": "PO-UJI-PK17", "entity_id": "ent_ksc", "supplier_id": "sup_pk17",
        "supplier_name": "Pemasok PK17", "status": "approved", "grand_total": 25 * JT, "items": [],
        "created_at": SEKARANG, "updated_at": SEKARANG})
    await db.vendor_bills.insert_many([
        {"id": "vb_x", "bill_number": "VB-UJI-PK17X", "entity_id": "ent_ksc", "supplier_id": "sup_pk17",
         "supplier_name": "Pemasok PK17", "po_id": "po_x", "po_number": "PO-UJI-PK17",
         "status": "pending_approval", "grand_total": 27.5 * JT, "amount_paid": 0, "outstanding": 27.5 * JT,
         "bill_date": "2026-11-10", "due_date": "2026-12-10", "created_at": SEKARANG},
        {"id": "vb_y", "bill_number": "VB-UJI-PK17Y", "entity_id": "ent_ksc", "supplier_id": "sup_pk17",
         "supplier_name": "Pemasok PK17", "status": "posted", "grand_total": 12 * JT, "amount_paid": 0,
         "outstanding": 12 * JT, "bill_date": "2026-11-01", "due_date": "2026-12-01", "created_at": SEKARANG},
    ])
    await refs.link(("vendor_bill", "vb_x"), ("purchase_order", "po_x"), "parent", force=True)
    await db.contra_bons.insert_one({
        "id": "cb_x", "number": "KSC/CB-UJI-PK17", "entity_id": "ent_ksc", "supplier_id": "sup_pk17",
        "supplier_name": "Pemasok PK17", "status": "submitted", "submitted_at": SEKARANG,
        "cycle_date": "2026-11-13", "due_date": "2026-12-13",
        "bills": [{"bill_id": "vb_y", "bill_number": "VB-UJI-PK17Y", "supplier_invoice_no": "INV-9",
                   "po_id": "", "po_number": "", "bill_date": "2026-11-01", "due_date": "2026-12-01",
                   "grand_total": 12 * JT, "outstanding_at_pick": 12 * JT, "applied_amount": 12 * JT,
                   "settled_amount": 0.0, "claim_deduction_info": 0.0,
                   "match": {"status": "matched", "exceptions": []}}],
        "deductions": [{"id": "ded_pk17", "kind": "purchase_return", "amount": 2 * JT, "reason_code": "retur",
                        "note": "retur beli"}],
        "decisions": [], "payments": [],
        "schedule": {"planned_payment_date": "", "method": "transfer", "bank_account_id": "", "notes": ""},
        "timeline": [{"event": "dibuat", "label": "Kontrabon dibuat", "actor": "Uji",
                      "note": "1 tagihan · Rp 12.000.000", "at": SEKARANG}],
        "created_at": SEKARANG, "updated_at": SEKARANG})
    sopir = await akun(peran_sopir)
    gudang = await akun("warehouse")
    keu = await akun("finance")
    return {"sopir_h": await sesi(sopir), "gudang_h": await sesi(gudang), "keu_h": await sesi(keu)}


# ── Papan Meja Finance (U1–U3) ───────────────────────────────────────────────
async def test_PK17_U01_sopir_papan_finance_ditolak(klien, siap):
    r = await klien.get("/api/home/finance", headers=siap["sopir_h"])
    assert r.status_code == 403, r.text
    assert _detail(r) == PESAN_PAPAN


async def test_PK17_U02_papan_disaring_per_izin(klien, akun, sesi, siap, peran_tanpa_acuan):
    kb = await akun(await peran_tanpa_acuan({"contra_bon": ["view"]}, label="PK17 Kontrabon"))
    r = await klien.get("/api/home/finance", headers=await sesi(kb))
    assert r.status_code == 200, r.text
    assert [b["key"] for b in r.json()["waiting_boards"]] == [
        "contra_bon_approve", "contra_bon_verify", "contra_bon_dispute"]
    vb = await akun(await peran_tanpa_acuan({"vendor_bill": ["view"]}, label="PK17 Tagihan"))
    r = await klien.get("/api/home/finance", headers=await sesi(vb))
    assert r.status_code == 200, r.text
    papan = r.json()["waiting_boards"]
    assert [b["key"] for b in papan] == ["vendor_bill"]
    assert [x["id"] for x in papan[0]["rows"]] == ["vb_x"]


async def test_PK17_U03_manajer_kosong_ditolak_admin_empat_papan(klien, akun, sesi, kepala_admin, siap,
                                                                   peran_manajer_kosong):
    mk = await akun(await peran_manajer_kosong())
    r = await klien.get("/api/home/finance", headers=await sesi(mk))
    assert r.status_code == 403, r.text
    r = await klien.get("/api/home/finance", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    assert len(j["waiting_boards"]) == 4
    # cb_x (submitted → verifikasi) + vb_x (pending_approval) = 2
    assert j["total_waiting"] == 2


# ── Jejak Dokumen (U4–U6) ────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def pembaca_po(akun, sesi, peran_tanpa_acuan):
    rid = await peran_tanpa_acuan({"document": ["view", "print"], "purchase_order": ["view"]}, label="PK17 PO")
    return await sesi(await akun(rid))


async def test_PK17_U04_jejak_nominal_tagihan_disembunyikan(klien, kepala_admin, siap, pembaca_po):
    r = await klien.get("/api/documents/trace/purchase_order/po_x", headers=pembaca_po)
    assert r.status_code == 200, r.text
    nodes = r.json()["nodes"]
    po, vb = _simpul(nodes, "po_x"), _simpul(nodes, "vb_x")
    assert po["amount"] == 25 * JT
    assert vb["amount"] is None
    assert vb["amount_hidden"] is True
    assert vb["can_open"] is False
    assert vb["pdf_doc_type"] == ""
    assert vb["number"] == "VB-UJI-PK17X" and vb["status"] == "pending_approval"
    r = await klien.get("/api/documents/trace/purchase_order/po_x", headers=kepala_admin)
    assert _simpul(r.json()["nodes"], "vb_x")["amount"] == 27.5 * JT


async def test_PK17_U05_cari_dan_rujukan_disembunyikan(klien, siap, pembaca_po):
    r = await klien.get("/api/documents/trace-search", params={"q": "VB-UJI-PK17X"}, headers=pembaca_po)
    assert r.status_code == 200, r.text
    vb = _simpul(r.json(), "vb_x")
    assert vb["amount"] is None and vb["amount_hidden"] is True
    r = await klien.get("/api/documents/refs/purchase_order/po_x", headers=pembaca_po)
    assert r.status_code == 200, r.text
    j = r.json()
    vb = next(x for x in j["refs"] if x.get("doc_id") == "vb_x")
    assert vb["amount"] is None and vb["amount_hidden"] is True
    assert j["anchor"]["amount"] == 25 * JT


async def test_PK17_U06_cetak_jejak_tanpa_nominal_tagihan(klien, kepala_admin, siap, pembaca_po):
    url = "/api/documents/trace/purchase_order/po_x/print"
    r = await klien.get(url, params={"format": "html"}, headers=pembaca_po)
    assert r.status_code == 200, r.text
    assert "27.500.000" not in r.text
    assert "25.000.000" in r.text
    r = await klien.get(url, params={"format": "html"}, headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert "27.500.000" in r.text and "25.000.000" in r.text


# ── Bawaan peran (U7, U8) ────────────────────────────────────────────────────
async def test_PK17_U07_bawaan_seed(db, siap):
    m = (await db.permission_settings.find_one({"id": "default"}))["matrix"]
    for peran in ("warehouse", "warehouse_admin"):
        for res in PASANGAN_GUDANG:
            assert res not in m[peran], (peran, res)
        assert m[peran]["contra_bon"] == ["view"]
    for peran in ("admin", "manager", "finance"):
        assert "configure" in m[peran]["cash"], peran
    # Matriks tersimpan sebelum PK-17 (tanpa `cash.configure`, belum tercatat di `defaults_applied`): proses awal
    # menambahkannya lewat buku izin bawaan PR-T9 (`sync_permission_modules`).
    tarik = {f"{bag}.{peran}.cash": "configure" for bag in ("matrix", "defaults_applied")
             for peran in ("admin", "manager", "finance")}
    await db.permission_settings.update_one({"id": "default"}, {"$pull": tarik})
    await bootstrap.run_bootstrap()
    m = (await db.permission_settings.find_one({"id": "default"}))["matrix"]
    for peran in ("admin", "manager", "finance"):
        assert "configure" in m[peran]["cash"], peran


async def test_PK17_U08_ekspor_tagihan_tertutup_bagi_gudang(klien, akun, sesi, siap):
    # Catatan cek ulang: untuk peran `warehouse` dataset ini sudah tertutup sebelum PK-17 oleh daftar putih berbasis
    # nama peran (`export_engine._role_whitelist`, FIX-4); kebocoran nyata ada di `warehouse_admin` (tanpa daftar
    # putih, memegang `data_export` + `vendor_bill.view`). Keduanya diuji.
    adm_gudang = await sesi(await akun("warehouse_admin"))
    for h in (siap["gudang_h"], adm_gudang):
        r = await klien.get("/api/export-center/datasets", headers=h)
        assert r.status_code == 200, r.text
        ids = {d["id"] for d in r.json()["datasets"]}
        assert "vendor_bills" not in ids and "landed_cost_vouchers" not in ids
        r = await klien.post("/api/export-center/preview", headers=h, json={"dataset": "vendor_bills"})
        assert r.status_code == 403, r.text


# ── Rekening (U9, U10) ───────────────────────────────────────────────────────
def _rekening(nama: str) -> dict:
    return {"name": nama, "account_type": "bank", "bank_name": "BCA", "account_number": "0001", "opening_balance": 0}


async def test_PK17_U09_buat_rekening_butuh_cash_configure(klien, akun, sesi, db, siap, peran_tanpa_acuan,
                                                            peran_manajer_kosong, peran_sopir):
    konf = await akun(await peran_tanpa_acuan({"cash": ["configure"]}, label="PK17 Kelola Rekening"))
    r = await klien.post("/api/bank-accounts", headers=await sesi(konf), json=_rekening("Rek PK17 A"))
    assert r.status_code == 200, r.text
    catat = await akun(await peran_tanpa_acuan({"cash": ["view", "create"]}, label="PK17 Catat Kas"))
    r = await klien.post("/api/bank-accounts", headers=await sesi(catat), json=_rekening("Rek PK17 B"))
    assert r.status_code == 403, r.text
    assert _detail(r) == PESAN_REKENING
    mk = await akun(await peran_manajer_kosong())
    r = await klien.post("/api/bank-accounts", headers=await sesi(mk), json=_rekening("Rek PK17 C"))
    assert r.status_code == 403, r.text
    r = await klien.post("/api/bank-accounts", headers=siap["sopir_h"], json=_rekening("Rek PK17 D"))
    assert r.status_code == 403, r.text
    r = await klien.post("/api/bank-accounts", headers=siap["keu_h"], json=_rekening("Rek PK17 E"))
    assert r.status_code == 200, r.text
    assert await db.bank_accounts.count_documents({"name": {"$in": ["Rek PK17 B", "Rek PK17 C", "Rek PK17 D"]}}) == 0


async def test_PK17_U10_ubah_rekening_pt_lain_404(klien, akun, sesi, db, siap, peran_tanpa_acuan):
    await db.bank_accounts.insert_one({"id": "ba_a", "name": "Rek A", "account_type": "bank", "entity_id": "ent_ksc",
                                       "opening_balance": 0, "is_active": True, "created_at": SEKARANG})
    rid = await peran_tanpa_acuan({"cash": ["configure"]}, label="PK17 Kelola Rekening Kanda")
    u = await akun(rid, entitas=("ent_kanda",))
    r = await klien.patch("/api/bank-accounts/ba_a", headers=await sesi(u, entitas="ent_kanda"), json={"name": "X"})
    assert r.status_code == 404, r.text
    assert (await db.bank_accounts.find_one({"id": "ba_a"}))["name"] == "Rek A"


# ── Ringkasan antar-PT (U11) ─────────────────────────────────────────────────
async def test_PK17_U11_ringkasan_antar_pt(klien, db, siap):
    await db.interco_transactions.insert_one({
        "id": "ict_pk17", "number": "KSC/ICT-UJI-PK17", "role": "seller", "entity_id": "ent_ksc",
        "seller_entity_id": "ent_ksc", "buyer_entity_id": "ent_kanda", "status": "invoiced",
        "grand_total": 22.2 * JT, "settled_amount": 0, "returned_amount": 0, "created_at": SEKARANG})
    baris = {"seller_entity_id": "ent_ksc", "buyer_entity_id": "ent_kanda", "outstanding": 22.2 * JT,
             "open_count": 1, "gross_amount": 22.2 * JT, "settled_amount": 0, "returned_amount": 0,
             "last_activity_at": SEKARANG}
    await db.interco_accounts.insert_many([
        {**baris, "id": "ica_pk17_r", "role": "receivable", "from_entity_id": "ent_ksc", "to_entity_id": "ent_kanda"},
        {**baris, "id": "ica_pk17_p", "role": "payable", "from_entity_id": "ent_kanda", "to_entity_id": "ent_ksc"},
    ])
    r = await klien.get("/api/interco/summary", params={"entity_id": "ent_ksc"}, headers=siap["gudang_h"])
    assert r.status_code == 200, r.text
    g = r.json()
    for f in ("net_payable", "net_receivable", "total_payable", "total_receivable"):
        assert g[f] is None, f
    assert g["net_pairs"] == []
    assert g["finance_hidden"] is True
    assert g["open_documents"] == 1
    r = await klien.get("/api/interco/summary", params={"entity_id": "ent_ksc"}, headers=siap["keu_h"])
    assert r.status_code == 200, r.text
    k = r.json()
    # KSC penjual: piutang bersih KSC atas Kanda = 22.200.000; utang KSC = 0.
    assert k["net_receivable"] == 22.2 * JT
    assert k["total_receivable"] == 22.2 * JT
    assert k["net_payable"] == 0
    assert "finance_hidden" not in k


# ── Kontrabon (U12, U13) ─────────────────────────────────────────────────────
async def _tiga_permintaan_kontrabon(klien, h):
    daftar = await klien.get("/api/contra-bons", headers=h)
    detail = await klien.get("/api/contra-bons/cb_x", headers=h)
    ring = await klien.get("/api/contra-bons/summary", headers=h)
    for r in (daftar, detail, ring):
        assert r.status_code == 200, r.text
    cb = next(x for x in daftar.json() if x["id"] == "cb_x")
    return cb, detail.json(), ring.json()


async def test_PK17_U12_kontrabon_gudang_tanpa_nominal(klien, siap):
    cb, det, ring = await _tiga_permintaan_kontrabon(klien, siap["gudang_h"])
    for x in (cb, det):
        assert x["totals"]["net_payable"] is None
        assert x["bills"][0]["applied_amount"] is None
        assert x["bills"][0]["grand_total"] is None
        assert x["deductions"][0]["amount"] is None
        assert x["amount_hidden"] is True
        assert x["number"] == "KSC/CB-UJI-PK17" and x["status"] == "submitted"
        assert "12.000.000" not in str(x)
    assert ring["waiting_count"] == 1
    assert ring["waiting_value"] is None
    assert all(v is None for k, v in ring.items() if k.endswith("_value"))
    r = await klien.get("/api/contra-bons/cb_x/receipt", headers=siap["gudang_h"])
    assert r.status_code == 200, r.text
    assert r.json()["contra_bon"]["totals"]["net_payable"] is None
    r = await klien.get("/api/contra-bons/unbilled-receipts", headers=siap["gudang_h"])
    assert r.status_code == 200, r.text
    assert r.json()["total_value"] is None
    # Tambahan di luar lima endpoint spesifikasi: tab "Jadwal Tukar Faktur" (terbuka bagi gudang) memuat nilai
    # tagihan siap dikontrabon per pemasok — disaring dengan aturan yang sama.
    r = await klien.get("/api/contra-bons/exchange-schedules", headers=siap["gudang_h"])
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["amount_hidden"] is True
    baris = next(x for x in j["rows"] if x["supplier_id"] == "sup_pk17")
    assert baris["billable_value"] is None and baris["unbilled_gr_value"] is None


async def test_PK17_U13_kontrabon_admin_bernominal(klien, kepala_admin, siap):
    cb, det, ring = await _tiga_permintaan_kontrabon(klien, kepala_admin)
    # bersih = 12.000.000 − 2.000.000
    assert cb["totals"]["net_payable"] == 10 * JT
    assert det["totals"]["net_payable"] == 10 * JT
    assert "amount_hidden" not in det
    assert ring["waiting_value"] == 10 * JT
    r = await klien.get("/api/contra-bons/exchange-schedules", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert "amount_hidden" not in r.json()
    baris = next(x for x in r.json()["rows"] if x["supplier_id"] == "sup_pk17")
    assert baris["billable_value"] is not None


# ── Skrip pembersih matriks tersimpan (U14) ──────────────────────────────────
def _muat_skrip():
    spec = importlib.util.spec_from_file_location("apply_pk17_role_cleanup", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_PK17_U14_skrip_pembersih_gudang(db, siap, capsys):
    assert SKRIP.exists(), f"skrip {SKRIP.name} belum ada"
    await db.permission_settings.update_one({"id": "default"}, {"$set": {
        f"matrix.warehouse.{res}": ["view"] for res in PASANGAN_GUDANG}})
    # Tidak ada pencabutan otomatis saat aplikasi mulai (K-47): matriks tersimpan tetap memuat ketiganya.
    await bootstrap.run_bootstrap()
    m = (await db.permission_settings.find_one({"id": "default"}))["matrix"]
    assert all(m["warehouse"].get(res) == ["view"] for res in PASANGAN_GUDANG)
    skrip = _muat_skrip()
    rencana = await skrip.rencana(db)
    assert sorted((x["role"], x["resource"]) for x in rencana["cabut"]) == [
        ("warehouse", res) for res in sorted(PASANGAN_GUDANG)]
    assert await skrip.main(["--report"]) == 0
    keluaran = capsys.readouterr().out
    assert "Pasangan yang akan dicabut: 3" in keluaran
    assert await db.permission_settings.count_documents({"matrix.warehouse.vendor_bill": ["view"]}) == 1  # baca saja
    assert await skrip.main(["--apply"]) == 0
    capsys.readouterr()
    assert await skrip.main(["--report"]) == 0
    assert "Pasangan yang akan dicabut: 0" in capsys.readouterr().out
    assert (await skrip.rencana(db))["cabut"] == []
    jejak = await db.audit_logs.find_one({"action": "permission_cleanup_pk17"})
    assert jejak, "jejak audit permission_cleanup_pk17 tidak ada"
    await bootstrap.run_bootstrap()
    m = (await db.permission_settings.find_one({"id": "default"}))["matrix"]
    for res in PASANGAN_GUDANG:
        assert res not in m["warehouse"], res
    assert m["warehouse"]["contra_bon"] == ["view"]
    assert (await skrip.rencana(db))["cabut"] == []


# ── Penjaga statis (U18) ─────────────────────────────────────────────────────
# Pelengkap `verify_auth_coverage.py` / `bukti/inv_endpoints.py` (dijalankan terpisah, keluaran di laporan): pernyataan
# pertama `home_finance` adalah pemeriksaan izin (Z1), jadi inventaris tidak lagi menggolongkannya "hanya login".
async def test_PK17_U18_papan_finance_berizin_secara_statis():
    import ast
    src = (Path(__file__).resolve().parents[1] / "routers" / "home.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src))
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "home_finance")
    pertama = next(s for s in fn.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)))
    panggil = pertama.value.value if isinstance(pertama.value, ast.Await) else None
    assert isinstance(panggil, ast.Call)
    nama = panggil.func.id if isinstance(panggil.func, ast.Name) else getattr(panggil.func, "attr", "")
    assert nama in ("require_permission", "require_any_permission"), nama
