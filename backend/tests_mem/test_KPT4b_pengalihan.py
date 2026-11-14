"""KP-T4 (b) — pintu persetujuan bertanya ke satu tabel kebijakan (docs/blueprint/unit/KP-T4.md U4–U14).

Satu database per modul; tes berurutan dan memakai keadaan tes sebelumnya (urutan ditulis per tes).
Fixture (sisip langsung, bukan alur): dokumen yang menunggu persetujuan (PO, tagihan pemasok, voucher biaya masuk, uang
muka, pesanan khusus draf, PR, transfer) disisipkan dengan pengaju orang lain dari pemutus. Alur lewat API: peran
kustom (`POST /api/access/roles`), Aturan Persetujuan (`PUT/DELETE /api/approval-policies/...`), keputusan.

Hitungan tangan (benih lingkungan B, `config_service.DEFAULT_APPROVAL_RULES` + `approval.extra_levels`):
  PO grup: [0, 100 jt) tanpa persetujuan · [100 jt, ∞) J1 peran berperingkat ≥ Manajer · [500 jt, ∞) J2 "Direksi" Admin
  → PO Rp150 jt = satu jenjang (J1); PO Rp600 jt = dua jenjang.
  PR grup: [50 jt, ∞) J1 = ≥ Manajer ∩ matriks {manager, admin} = {Admin, Manajer} → PR Rp60 jt butuh J1.
  Uang muka: J1 Atasan Langsung {Admin, Manajer + acuan}, J2 Pimpinan {Admin}, J3 Bagian Keuangan {Admin}.
"""
from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/migrate_kpt4_kebijakan_persetujuan.py"
JT = 1_000_000
K: dict = {}


def _id(awal: str) -> str:
    return f"{awal}_kpt4_{uuid.uuid4().hex[:8]}"


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kpt4_kebijakan_persetujuan", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def _po(db, ent, pembuat, total, chain=None):
    from services.config_service import build_approval_chain
    if chain is None:
        chain = (await build_approval_chain("purchase_order", total, ent))["approval_chain"]
    po = {"id": _id("po"), "po_number": f"PO-KPT4-{uuid.uuid4().hex[:5]}", "entity_id": ent,
          "status": "waiting_approval", "approval_status": "pending",
          "required_approval_role": chain[0].get("required_role", "manager"), "approval_chain": chain,
          "approval_level_current": chain[0]["level"], "created_by": pembuat["name"], "created_by_id": pembuat["id"],
          "supplier_id": "", "supplier_name": "Pemasok Uji", "items": [], "total_amount": total, "grand_total": total,
          "timeline": [], "created_at": now_iso(), "updated_at": now_iso()}
    await db.purchase_orders.insert_one(dict(po))
    return po


async def _kebijakan(klien, h, doc_kind, ent):
    r = await klien.get("/api/approval-policies", headers=h, params={"entity_id": ent, "doc_kind": doc_kind})
    assert r.status_code == 200, r.text
    return r.json()["kinds"][0]


def _levels_dari(view, ubah=None):
    """Isi PUT dari tampilan server; `ubah(level, tier)` boleh mengubah tier di tempat."""
    out = []
    for lv in view["levels"]:
        tiers = []
        for t in lv["tiers"]:
            tt = {"min_amount": t["min_amount"], "max_amount": t["max_amount"], "roles": list(t["roles"]),
                  "any_holder": t["any_holder"]}
            if ubah:
                ubah(lv["level"], tt)
            tiers.append(tt)
        out.append({"level": lv["level"], "label": lv["label"], "tiers": tiers})
    return out


async def _put(klien, h, doc_kind, ent, levels, version, reason="uji KP-T4"):
    return await klien.put(f"/api/approval-policies/{doc_kind}", headers=h,
                           json={"entity_id": ent, "expected_version": version, "reason": reason, "levels": levels})


@pytest.fixture(scope="module")
async def orang(akun, sesi, db, klien, kepala_admin, peran_tanpa_acuan):
    mgr = await akun("manager", entitas=("ent_ksc", "ent_kanda"))
    mgr2 = await akun("manager", entitas=("ent_ksc", "ent_kanda"))
    fin = await akun("finance", entitas=("ent_ksc", "ent_kanda"))
    adm = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    tanpa = await peran_tanpa_acuan({"purchase_order": ["view", "approve", "reject"], "transfer": ["view", "approve"]},
                                    label="Tanpa Acuan KP-T4b")
    ta = await akun(tanpa, entitas=("ent_ksc", "ent_kanda"))
    return {"mgr": mgr, "mgr2": mgr2, "fin": fin, "adm": adm, "tanpa": tanpa, "ta": ta,
            "h_mgr": await sesi(mgr), "h_mgr2": await sesi(mgr2), "h_fin": await sesi(fin),
            "h_fin_kanda": await sesi(fin, entitas="ent_kanda"), "h_mgr_kanda": await sesi(mgr, entitas="ent_kanda"),
            "h_adm": kepala_admin, "h_ta": await sesi(ta), "h_ta_kanda": await sesi(ta, entitas="ent_kanda")}


# ── U4 — izin saja tidak cukup: peran harus tercantum ──────────────────────────────────────────────────────────────
async def test_KPT4_U4_izin_tanpa_tercantum_403_batas(klien, db, orang):
    po = await _po(db, "ent_ksc", orang["mgr2"], 150 * JT)
    r = await klien.post(f"/api/purchase-orders/{po['id']}/approve", headers=orang["h_ta"])
    assert r.status_code == 403, r.text
    pesan = _detail(r)
    assert pesan.startswith("Pesanan Pembelian senilai Rp150.000.000 pada jenjang 1 diputus oleh "), pesan
    assert pesan.endswith("Peran Anda belum tercantum di Aturan Persetujuan."), pesan
    assert "role" not in pesan.lower() and orang["tanpa"] not in pesan and "manager" not in pesan, pesan
    K["po_u4"] = po


# ── U5 — tambahkan Tanpa Acuan di J1 PT ksc: ksc 200, kanda tetap 403 ─────────────────────────────────────────────
async def test_KPT4_U5_tercantum_di_pt_ini_saja(klien, db, orang):
    h = orang["h_adm"]
    view = await _kebijakan(klien, h, "purchase_order", "ent_ksc")
    assert view["source"] == "bawaan" and view["version"] == 0

    def tambah(level, t):
        if level == 1 and t["roles"]:
            t["roles"].append(orang["tanpa"])
    r = await _put(klien, h, "purchase_order", "ent_ksc", _levels_dari(view, tambah), 0)
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "pt" and r.json()["version"] == 1
    r = await klien.post(f"/api/purchase-orders/{K['po_u4']['id']}/approve", headers=orang["h_ta"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"
    po_kanda = await _po(db, "ent_kanda", orang["mgr2"], 150 * JT)
    r = await klien.post(f"/api/purchase-orders/{po_kanda['id']}/approve", headers=orang["h_ta_kanda"])
    assert r.status_code == 403, r.text
    assert "belum tercantum" in _detail(r)


# ── U6 — Manajer Kosong (nol izin): PO, tagihan pemasok, voucher biaya masuk → 403 izin ×3 ─────────────────────────
async def test_KPT4_U6_manajer_kosong_tiga_pintu_403_izin(klien, db, orang, akun, sesi, peran_manajer_kosong):
    kosong = await peran_manajer_kosong()
    h = await sesi(await akun(kosong, entitas=("ent_ksc",)))
    po = await _po(db, "ent_ksc", orang["mgr2"], 150 * JT)
    vb = {"id": _id("vb"), "bill_number": "VB-KPT4", "entity_id": "ent_ksc", "status": "pending_approval",
          "approval_required": True, "required_approval_role": "manager", "grand_total": 75 * JT,
          "total_amount": 75 * JT, "items": [], "created_by": orang["mgr2"]["name"],
          "created_by_id": orang["mgr2"]["id"], "created_at": now_iso()}
    lc = {"id": _id("lcv"), "voucher_number": "LC-KPT4", "entity_id": "ent_ksc", "status": "pending_approval",
          "required_approval_role": "manager", "total_cost": 5 * JT, "po_ids": [], "created_by": orang["mgr2"]["name"],
          "created_by_id": orang["mgr2"]["id"], "created_at": now_iso()}
    await db.vendor_bills.insert_one(dict(vb))
    await db.landed_cost_vouchers.insert_one(dict(lc))
    hasil = []
    for url, label, modul in ((f"/api/purchase-orders/{po['id']}/approve", "Pesanan Pembelian", "Pembelian & Pengadaan"),
                              (f"/api/vendor-bills/{vb['id']}/approve", "Tagihan pemasok", "Hutang Supplier & Kontrabon"),
                              (f"/api/landed-costs/{lc['id']}/approve", "Voucher biaya masuk",
                               "Hutang Supplier & Kontrabon")):
        r = await klien.post(url, headers=h, json={})
        hasil.append(r.status_code)
        assert r.status_code == 403, (url, r.text)
        assert _detail(r) == (f"Anda belum punya akses untuk menyetujui {label}. "
                              f"Minta Admin menambahkan akses '{modul}'."), _detail(r)
    assert hasil == [403, 403, 403]


# ── U7 — peran kustom beracuan Manajer dibuat SEBELUM migrasi, tanpa modul Pembelian ──────────────────────────────────
async def test_KPT4_U7_migrasi_memberi_izin_setara(klien, db, orang, akun, sesi, kepala_admin):
    mods = (await klien.get("/api/access/modules", headers=kepala_admin)).json()
    mods = mods.get("modules", mods) if isinstance(mods, dict) else mods
    levels = {m["id"]: "manage" for m in mods}
    levels["purchasing"] = "none"
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Manajer Tanpa Pembelian", "base_role": "manager", "description": "peran uji", "levels": levels})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    hasil = await _skrip().jalankan(tulis=True, aktor="uji KP-T4")
    assert set(hasil["izin"].get(rid, {}).get("purchase_order", [])) == {"approve", "reject"}
    assert hasil["ditulis"]["baris"] > 0
    u = await akun(rid, entitas=("ent_kanda",))
    po = await _po(db, "ent_kanda", orang["mgr2"], 150 * JT)
    r = await klien.post(f"/api/purchase-orders/{po['id']}/approve", headers=await sesi(u, entitas="ent_kanda"))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"


# ── U8 — uang muka ent_kanda: J3 {finance} ──────────────────────────────────────────────────────────────────────────
async def _uang_muka(db, ent, pemohon, status, total=2 * JT):
    doc = {"id": _id("ca"), "number": f"PD-KPT4-{uuid.uuid4().hex[:5]}", "entity_id": ent, "status": status,
           "lines": [], "total_amount": total, "approvals": [], "created_by": pemohon["name"],
           "created_by_id": pemohon["id"], "created_at": now_iso()}
    await db.cash_advances.insert_one(dict(doc))
    return doc


async def test_KPT4_U8_uang_muka_jenjang3_finance_per_pt(klien, db, orang):
    # Persiapan tambahan (lihat laporan): Finance bawaan TIDAK memegang `cash_advance.approve` → diberi lewat matriks.
    rec = await db.permission_settings.find_one({"id": "default"}, {"_id": 0, "matrix": 1})
    m = rec["matrix"]
    m.setdefault("finance", {}).setdefault("cash_advance", [])
    m["finance"]["cash_advance"] = sorted(set(m["finance"]["cash_advance"]) | {"approve"})
    await db.permission_settings.update_one({"id": "default"}, {"$set": {"matrix": m}})
    h = orang["h_adm"]
    view = await _kebijakan(klien, h, "cash_advance", "ent_kanda")

    def j3(level, t):
        if level == 3:
            t["roles"] = ["finance"]
    r = await _put(klien, h, "cash_advance", "ent_kanda", _levels_dari(view, j3), view["version"] if view["source"]
                   == "pt" else 0)
    assert r.status_code == 200, r.text
    kanda = await _uang_muka(db, "ent_kanda", orang["mgr2"], "pending_finance")
    ksc = await _uang_muka(db, "ent_ksc", orang["mgr2"], "pending_finance")
    r = await klien.post(f"/api/cash-advances/{kanda['id']}/approve", headers=orang["h_fin_kanda"], json={"note": ""})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"
    r = await klien.post(f"/api/cash-advances/{ksc['id']}/approve", headers=orang["h_fin"], json={"note": ""})
    assert r.status_code == 403, r.text
    K["ca_kanda_version"] = (await _kebijakan(klien, h, "cash_advance", "ent_kanda"))["version"]


# ── U9 — uang muka ent_kanda hanya J1: Manajer menyetujui → langsung disetujui ─────────────────────────────────────
async def test_KPT4_U9_jenjang_tanpa_baris_dilewati(klien, db, orang):
    h = orang["h_adm"]
    view = await _kebijakan(klien, h, "cash_advance", "ent_kanda")
    satu = [lv for lv in _levels_dari(view) if lv["level"] == 1]
    r = await _put(klien, h, "cash_advance", "ent_kanda", satu, view["version"])
    assert r.status_code == 200, r.text
    doc = await _uang_muka(db, "ent_kanda", orang["mgr2"], "pending_atasan")
    r = await klien.post(f"/api/cash-advances/{doc['id']}/approve", headers=orang["h_mgr_kanda"], json={"note": ""})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


# ── U11 — validasi PUT ─────────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT4_U11_put_tanpa_alasan_peran_asing_versi_basi(klien, orang):
    h = orang["h_adm"]
    view = await _kebijakan(klien, h, "landed_cost", "ent_ksc")
    lv = _levels_dari(view)
    r = await _put(klien, h, "landed_cost", "ent_ksc", lv, 0, reason="  ")
    assert (r.status_code, _detail(r)) == (400, "Alasan perubahan wajib diisi."), r.text
    bad = [{"level": 1, "label": "", "tiers": [{"min_amount": 0, "max_amount": None, "roles": ["direktur"]}]}]
    r = await _put(klien, h, "landed_cost", "ent_ksc", bad, 0)
    assert (r.status_code, _detail(r)) == (400, "Peran “direktur” tidak ada."), r.text
    rentang = [{"level": 1, "label": "", "tiers": [{"min_amount": 10 * JT, "max_amount": 5 * JT, "roles": ["admin"]}]}]
    r = await _put(klien, h, "landed_cost", "ent_ksc", rentang, 0)
    assert (r.status_code, _detail(r)) == (
        400, "Rentang jenjang 1 tidak sah: batas atas harus lebih besar dari batas bawah."), r.text
    nominal = [{"level": 1, "label": "", "tiers": [{"min_amount": 5, "roles": ["admin"]}]}]
    r = await klien.put("/api/approval-policies/transfer", headers=h,
                        json={"entity_id": "ent_ksc", "expected_version": 0, "reason": "uji", "levels": nominal})
    assert (r.status_code, _detail(r)) == (400, "Jenis dokumen ini tidak memakai nominal."), r.text
    r = await _put(klien, h, "landed_cost", "ent_ksc", lv, 0)
    assert r.status_code == 200, r.text
    r = await _put(klien, h, "landed_cost", "ent_ksc", lv, 0)   # versi basi (sekarang 1)
    assert (r.status_code, _detail(r)) == (409, "Aturan ini sudah diubah orang lain. Muat ulang."), r.text


# ── U12 — PO lama dengan rantai tersimpan [manager, admin] ─────────────────────────────────────────────────────────
async def test_KPT4_U12_po_lama_rantai_tersimpan(klien, db, orang):
    chain = [{"level": 1, "label": "Persetujuan", "required_role": "manager", "status": "pending", "approved_by": "",
              "approved_by_id": "", "approved_at": ""},
             {"level": 2, "label": "Direksi", "required_role": "admin", "status": "pending", "approved_by": "",
              "approved_by_id": "", "approved_at": ""}]
    po = await _po(db, "ent_ksc", orang["mgr2"], 600 * JT, chain=chain)
    r = await klien.post(f"/api/purchase-orders/{po['id']}/approve", headers=orang["h_mgr"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "waiting_approval" and r.json()["approval_level_current"] == 2
    r = await klien.post(f"/api/purchase-orders/{po['id']}/approve", headers=orang["h_adm"])
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "pending"


# ── U13 — PR Rp60 jt: peran kustom beracuan Manajer ─────────────────────────────────────────────────────────────────
async def test_KPT4_U13_pr_satu_pesan_dari_tabel(klien, db, orang, akun, sesi, kepala_admin):
    r = await klien.post("/api/access/roles", headers=kepala_admin, json={
        "label": "Manajer PR", "base_role": "manager", "description": "peran uji",
        "permissions": {"purchase_requisition": ["view", "approve", "reject"]}})
    assert r.status_code == 200, r.text
    rid = (r.json().get("role") or r.json())["id"]
    h = await sesi(await akun(rid, entitas=("ent_ksc",)))
    pr = {"id": _id("pr"), "number": "PR-KPT4", "entity_id": "ent_ksc", "status": "pending_approval",
          "approval_required": True, "required_approval_role": "manager", "items": [], "total_est_amount": 60 * JT,
          "created_by": orang["mgr2"]["name"], "created_by_id": orang["mgr2"]["id"], "created_at": now_iso()}
    await db.purchase_requisitions.insert_one(dict(pr))
    r = await klien.post(f"/api/purchase-requisitions/{pr['id']}/approve", headers=h, json={})
    assert r.status_code == 403, r.text
    pesan = _detail(r)
    assert pesan.startswith("Permintaan Pembelian (PR) senilai Rp60.000.000 pada jenjang 1 diputus oleh "), pesan
    assert pesan.count("Peran Anda") == 1 and "matriks" not in pesan and "minimal" not in pesan, pesan
    view = await _kebijakan(klien, orang["h_adm"], "purchase_requisition", "ent_ksc")

    def tambah(level, t):
        if t["roles"]:
            t["roles"].append(rid)
    r = await _put(klien, orang["h_adm"], "purchase_requisition", "ent_ksc", _levels_dari(view, tambah),
                   view["version"] if view["source"] == "pt" else 0)
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/purchase-requisitions/{pr['id']}/approve", headers=h, json={})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


# ── U14 — tujuh belas kunci tidak dipakai ──────────────────────────────────────────────────────────────────────────
async def test_KPT4_U14_tujuh_belas_kunci_tidak_dipakai(klien, kepala_admin):
    kunci = _skrip().KUNCI_DIPINDAH
    assert len(kunci) == 17
    r = await klien.get("/api/config/registry", headers=kepala_admin)
    assert r.status_code == 200, r.text
    data = r.json()
    items = data.get("items") or data.get("entries") or data
    by = {e["key"]: e for e in items}
    for k in kunci:
        assert by[k]["status"] == "not_used", k
        assert "Aturan Persetujuan" in by[k]["not_used_reason"], k


# ── Pintu "izin saja" ikut tabel; tombol layar keputusan ───────────────────────────────────────────────────────────
async def test_KPT4_pintu_izin_saja_bertanya_tabel(klien, db, orang):
    t = {"id": _id("trf"), "code": "TRF-KPT4", "entity_id": "ent_ksc", "status": "waiting_approval", "items": [],
         "source_warehouse_id": "", "dest_warehouse_id": "", "requested_by": orang["mgr2"]["name"],
         "requested_by_id": orang["mgr2"]["id"], "created_at": now_iso()}
    await db.warehouse_transfers.insert_one(dict(t))
    h = orang["h_adm"]
    view = await _kebijakan(klien, h, "transfer", "ent_ksc")
    assert view["levels"][0]["tiers"][0]["any_holder"] is True
    r = await _put(klien, h, "transfer", "ent_ksc",
                   [{"level": 1, "label": "", "tiers": [{"min_amount": 0, "roles": ["admin"]}]}],
                   view["version"] if view["source"] == "pt" else 0)
    assert r.status_code == 200, r.text
    r = await klien.post(f"/api/transfers/{t['id']}/approve", headers=orang["h_mgr"], json={"approved_by": "x"})
    assert r.status_code == 403, r.text
    assert "Transfer gudang" in _detail(r) and "belum tercantum" in _detail(r)
    r = await klien.delete("/api/approval-policies/transfer", headers=h,
                           params={"entity_id": "ent_ksc", "reason": "kembali ke grup"})
    assert r.status_code == 200 and r.json()["source"] in ("grup", "bawaan"), r.text
    r = await klien.post(f"/api/transfers/{t['id']}/approve", headers=orang["h_mgr"], json={"approved_by": "x"})
    assert r.status_code != 403 or "belum tercantum" not in _detail(r), r.text


async def test_KPT4_can_decide_me_untuk_tombol(klien, orang):
    r = await klien.get("/api/approval-policies/can-decide/me", headers=orang["h_ta"],
                        params={"doc_kind": "vendor_bill", "entity_id": "ent_ksc", "amount": 10 * JT})
    assert r.status_code == 200, r.text
    assert r.json()["allowed"] is False and r.json()["code"] == "izin"
    r = await klien.get("/api/approval-policies/can-decide/me", headers=orang["h_mgr"],
                        params={"doc_kind": "vendor_bill", "entity_id": "ent_ksc", "amount": 10 * JT})
    assert r.json()["allowed"] is True


# ── U10 — pesanan khusus (lihat laporan: koreksi harapan blueprint) ────────────────────────────────────────────────
async def _od(db, total):
    od = {"id": _id("sord"), "number": f"OD-KPT4-{uuid.uuid4().hex[:5]}", "status": "draft", "type": "special_order",
          "entity_id": "ent_ksc", "total_amount": total, "items": [], "request_types": [], "customer_id": "",
          "customer_name": "Pelanggan Uji", "custom_item": {"description": "Kain uji", "quantity": 1, "unit": "m",
                                                            "target_price": total},
          "status_history": [{"status": "draft", "timestamp": now_iso(), "user": "uji@uji.id"}],
          "created_by": "uji@uji.id", "created_at": now_iso(), "updated_at": now_iso()}
    await db.special_orders.insert_one(dict(od))
    return od


async def test_KPT4_U10_pesanan_khusus_jenjang_dari_tabel(klien, db, orang):
    h = orang["h_adm"]
    hasil = {}
    for nilai in (10 * JT, 10 * JT + 0.01):
        od = await _od(db, nilai)
        r = await klien.post(f"/api/special-orders/{od['id']}/submit", headers=h)
        assert r.status_code == 200, r.text
        hasil[nilai] = (r.json()["status"], len(r.json().get("approval_chain") or []))
    # Sama dengan hari ini: pesanan khusus yang diajukan SELALU menunggu jenjang 1 (Manager) — ambang Rp10 jt lama tidak
    # pernah menentukan status (koreksi harapan U10 di laporan).
    assert hasil == {10 * JT: ("pending_approval", 1), 10 * JT + 0.01: ("pending_approval", 1)}
    view = await _kebijakan(klien, h, "special_order", "all")

    def mulai_20jt(level, t):
        if level == 1:
            t["min_amount"] = 20 * JT
    r = await _put(klien, h, "special_order", "all", _levels_dari(view, mulai_20jt),
                   view["version"] if view["source"] == "grup" else 0)
    assert r.status_code == 200, r.text
    hasil = {}
    for nilai in (15 * JT, 25 * JT):
        od = await _od(db, nilai)
        r = await klien.post(f"/api/special-orders/{od['id']}/submit", headers=h)
        assert r.status_code == 200, r.text
        hasil[nilai] = r.json()["status"]
    # 15 jt tidak butuh persetujuan lagi → disetujui otomatis; 25 jt menunggu jenjang 1.
    assert hasil == {15 * JT: "confirmed", 25 * JT: "pending_approval"}
