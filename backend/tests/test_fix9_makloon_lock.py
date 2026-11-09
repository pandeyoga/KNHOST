"""FIX-9 (audit 9 Nov 2026 — B3a SSOT-4; FIX-2 §5 butir 1 & 5) — cadangan bahan makloon DIKUNCI PER ROLL.

Uji tingkat LAYANAN (tanpa HTTP), data sendiri bertanda TEST_FIX9 (PT, gudang, produk, mitra uji), dibersihkan di akhir.
Semua uji GAGAL di kode sebelum FIX-9 (cadangan tidak pernah menempel di roll; fungsi kunci tidak ada) dan LULUS sesudah.

Cakupan:
  1. kunci saat cadangan lahir (MKO dibuat; PR disetujui) — gudang sumber, FIFO, roll utuh dulu, cermin `locks`;
  2. angka stok TIDAK dobel-kurang (`stock_figures` segmen, dua angka, Total grup) — sebelum/sesudah kunci sama;
  3. stok kurang → kunci sebanyak yang ada, sisanya "belum terkunci" (hanya bagian ini di `allocate_makloon`);
  4. issue: roll terkunci sendiri boleh dikirim (kunci lepas atomik), roll lain menggantikan kunci (kunci lama
     dilepas sejumlah itu), issue jalur jumlah memakai roll terkunci dulu, MKO lain ditolak menyebut nomor MKO;
  5. release (MKO batal) melepas semua, idempoten;
  6. paralel: dua cadangan bersamaan tidak mengunci panjang yang sama; `lock` ganda tidak melebihi qty;
  7. pemilih roll / alokasi SO / beli per roll / transfer / tahan / pengambilan menolak panjang terkunci (pesan
     menyebut MKO); mode approve + persetujuan manajer meminjam kunci;
  8. PR → MKO: kunci pindah ke gudang sumber MKO & rujukan bernomor MKO;
  9. skrip migrasi: dry-run tidak menulis, apply mengunci, ulang = idempoten, undo, pagar DB.

Jalankan (kontainer backend, DB uji):
  cd /app/backend && python -m pytest -q -p no:cacheprovider -n0 tests/test_fix9_makloon_lock.py
"""
import asyncio
import os
import subprocess
import sys
import uuid

import pytest
from fastapi import HTTPException
from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import roll_service  # noqa: E402

DB_NAME = os.environ.get("DB_NAME", "test_database")
DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[DB_NAME]
TAG = uuid.uuid4().hex[:8]
ENT = f"ent_TEST_FIX9_{TAG}"
WH_A, WH_B = (f"wh_TEST_FIX9_{TAG}_{k}" for k in ("a", "b"))
P = f"prod_TEST_FIX9_{TAG}"
P_OUT = f"prod_TEST_FIX9_{TAG}_out"
MAK = f"mak_TEST_FIX9_{TAG}"
_N = {"n": 0}
REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _nx() -> int:
    _N["n"] += 1
    return _N["n"]


@pytest.fixture(scope="module", autouse=True)
def seed():
    DB.business_entities.insert_one({"id": ENT, "short_name": f"UJI9-{TAG}", "code": f"N{TAG[:4].upper()}",
                                     "legal_name": "PT Uji FIX-9"})
    DB.warehouses.insert_many([
        {"id": WH_A, "name": f"Gudang Sumber {TAG}", "code": f"GA{TAG[:4]}", "roles": ["storage"],
         "sharing_mode": "shared", "active": True},
        {"id": WH_B, "name": f"Gudang Lain {TAG}", "code": f"GB{TAG[:4]}", "roles": ["storage"],
         "sharing_mode": "shared", "active": True}])
    base = {"harga_pokok": 0, "status": "active", "stage": "greige", "fabric_type": "woven", "base_unit": "yard"}
    DB.products.insert_many([{**base, "id": P, "sku": f"FIX9-GREIGE-{TAG}", "name": "Greige Uji FIX-9"},
                             {**base, "id": P_OUT, "sku": f"FIX9-OUT-{TAG}", "name": "Hasil Uji FIX-9"}])
    DB.makloons.insert_one({"id": MAK, "name": "Mitra Uji FIX-9", "entity_id": ENT})
    yield
    rns = [r["roll_no"] for r in DB.inventory_rolls.find({"owner_entity_id": ENT}, {"roll_no": 1}) if r.get("roll_no")]
    DB.number_sequences.delete_many({"doc_type": {"$in": [f"ROLL_CHILD:{rn}" for rn in rns]}})
    for coll in ("inventory_rolls", "inventory_lots", "inventory_movements", "inventory_balances",
                 "material_reservations"):
        DB[coll].delete_many({"owner_entity_id": ENT})
    for coll in ("wms_tasks", "makloon_orders", "journal_entries", "purchase_requisitions", "number_sequences",
                 "inventory_lots", "notifications", "sales_orders"):
        DB[coll].delete_many({"entity_id": ENT})
    DB.audit_logs.delete_many({"scope_entity_id": ENT})
    DB.products.delete_many({"id": {"$in": [P, P_OUT]}})
    DB.warehouses.delete_many({"id": {"$in": [WH_A, WH_B]}})
    DB.makloons.delete_many({"id": MAK})
    DB.business_entities.delete_many({"id": ENT})
    DB.migrations.update_one({"id": "fix_data_2026_11_10_fix9_kunci_makloon"},
                             {"$pull": {"runs": {"only": {"$regex": TAG}}}})


@pytest.fixture(autouse=True)
def clean_case():
    """Setiap uji mulai dari gudang kosong (roll/saldo/cadangan PT uji dihapus)."""
    for coll in ("inventory_rolls", "inventory_balances", "material_reservations", "inventory_movements"):
        DB[coll].delete_many({"owner_entity_id": ENT})
    DB.makloon_orders.delete_many({"entity_id": ENT})
    DB.material_reservation_locks.delete_many({"_id": {"$regex": f"^(rl:mres_mko_TEST_FIX9_{TAG}|{P})"}})
    yield


def _roll(wh, qty, day, **extra):
    r = run(roll_service.create_inbound_roll(P, wh, ENT, qty, lot=f"LOT-{TAG}-{_nx()}", unit="yard",
                                             unit_cost=1000.0, created_by="uji"))
    DB.inventory_rolls.update_one({"id": r["id"]}, {"$set": {"received_date": f"2026-10-{day:02d}T00:00:00+00:00",
                                                             **extra}})
    run(roll_service.rebuild_balance(P, wh, ENT))
    return DB.inventory_rolls.find_one({"id": r["id"]}, {"_id": 0})


def _step(oid, qty):
    return {"seq": 1, "status": "pending", "issue_ref": f"{oid}:1", "makloon_id": MAK, "makloon_name": "Mitra Uji",
            "material_flow": "moves", "process_type": "dyeing", "stage_label": "Celup", "changes_stage": True,
            "input_product_id": P, "input_name": "Greige", "input_unit": "yard", "input_qty": qty,
            "output_product_id": P_OUT, "output_name": "Hasil", "output_unit": "yard", "output_sku": "OUT",
            "expected_output_qty": qty, "expected_byproduct_qty": 0, "tariff_basis": "lumpsum", "tariff_rate": 0,
            "tolerance_pct": 5, "shrinkage_pct": 0, "aux_cost": 0}


def _mko(qty, wh=WH_A, reserve=True):
    from services import material_reservation_service as mres
    oid = f"mko_TEST_FIX9_{TAG}_{_nx()}"
    doc = {"id": oid, "mko_number": f"UJI9/MKO-{TAG}-{_N['n']}", "entity_id": ENT, "mode": "process_only",
           "status": "draft", "from_warehouse_id": wh, "target_warehouse_id": wh, "material_product_id": P,
           "material_qty": qty, "steps": [_step(oid, qty)], "timeline": [], "costing": {"steps": []},
           "claim_summary": {}, "service_absorption_pending": 0.0, "created_at": "2026-11-10T00:00:00+00:00"}
    DB.makloon_orders.insert_one(dict(doc))
    if reserve:
        run(mres.reserve_for_mko(doc, "uji"))
    return doc


def _res(mko_id):
    return DB.material_reservations.find_one({"ref_id": mko_id, "status": {"$in": ["active", "consumed"]}},
                                             {"_id": 0})


def _r(rid):
    return DB.inventory_rolls.find_one({"id": rid}, {"_id": 0})


def _locked(roll, res_id=None):
    return round(sum(float(x["qty"]) for x in roll.get("length_reservations") or []
                     if (x.get("ref") or {}).get("type") == "makloon"
                     and (res_id is None or x["ref"]["id"] == res_id)), 2)


def _avail():
    from services import stock_figures as sf
    return sf.sum_segments([s for s in run(sf.segments([P])) if s["owner_entity_id"] == ENT])


def _no_overlock():
    for r in DB.inventory_rolls.find({"owner_entity_id": ENT, "product_id": P}, {"_id": 0}):
        tot = round(sum(float(x["qty"]) for x in r.get("length_reservations") or []), 2)
        assert tot <= float(r["length_remaining"]) + 0.01, r
        assert abs(tot - float(r.get("length_reserved") or 0)) <= 0.01, r


def _err(coro):
    with pytest.raises(HTTPException) as ei:
        run(coro)
    return ei.value


def _text(e):
    d = e.detail
    return d.get("message", "") if isinstance(d, dict) else str(d)


# ── 1. Kunci saat lahir ─────────────────────────────────────────────────────────────────────────────────────────
def test_kunci_saat_mko_lahir_gudang_sumber_fifo_roll_utuh_dulu():
    r_old = _roll(WH_A, 40, 1)
    r_mid = _roll(WH_A, 30, 2)
    r_new = _roll(WH_A, 50, 3)
    r_b = _roll(WH_B, 100, 1)                         # gudang lain — tidak dikunci (gudang sumber = A)
    mko = _mko(60)
    res = _res(mko["id"])
    assert res["locked_qty"] == 60 and res["qty"] == 60
    assert _locked(_r(r_old["id"])) == 40             # roll tertua dikunci utuh
    assert _locked(_r(r_mid["id"])) == 20             # roll berikutnya sebagian
    assert _locked(_r(r_new["id"])) == 0 and _locked(_r(r_b["id"])) == 0
    assert sorted((x["roll_id"], x["qty"]) for x in res["locks"]) == sorted([(r_old["id"], 40), (r_mid["id"], 20)])
    ref = next(x for x in _r(r_old["id"])["length_reservations"])["ref"]
    assert ref["type"] == "makloon" and ref["number"] == mko["mko_number"] and ref["id"] == res["id"]
    bal = DB.inventory_balances.find_one({"product_id": P, "warehouse_id": WH_A, "owner_entity_id": ENT})
    assert bal["makloon_locked_qty"] == 60 and bal["available_qty"] == 60      # 120 − 60
    assert any(h["event"] == "locked" for h in DB.material_reservations.find_one({"id": res["id"]})["history"])
    # bukan reservasi potong: tidak muncul di antrean potong & tidak bisa "dipotong"
    assert not [x for x in run(roll_service.pending_cuts(scope_ids=[ENT])) if x["roll_id"] == r_old["id"]]
    rsv_id = _r(r_old["id"])["length_reservations"][0]["id"]
    assert _err(roll_service.confirm_cut(r_old["id"], rsv_id, actor="uji")).status_code == 409
    _no_overlock()


def test_pr_disetujui_mengunci_dengan_gudang_pr(monkeypatch):
    """"Saat disetujui": cadangan PR lahir di `approve_requisition` → langsung dikunci (gudang = gudang PR)."""
    from services import pr_sourcing_service as prs
    from services import purchase_requisition_service as prsvc
    _roll(WH_A, 25, 1)
    rb = _roll(WH_B, 80, 1)
    pr_id = f"pr_TEST_FIX9_{TAG}_{_nx()}"
    DB.purchase_requisitions.insert_one({
        "id": pr_id, "number": f"UJI9/PR-{TAG}", "entity_id": ENT, "status": "pending_approval",
        "approval_status": "pending", "required_approval_role": "manager", "warehouse_id": WH_B,
        "created_by": "Pembuat", "created_by_id": "usr_pembuat_fix9",
        "items": [{"line_no": 1, "product_id": P_OUT, "fulfillment_mode": "makloon", "qty": 40}],
        "created_at": "2026-11-10T00:00:00+00:00"})

    async def fake_prefill(pid, line_no):
        return {"ready": True, "target_output_qty": 40, "recipe": {"id": "rcp"},
                "payload": {"material_product_id": P, "material_qty": 50}}
    monkeypatch.setattr(prs, "makloon_prefill", fake_prefill)
    run(prsvc.approve_requisition(pr_id, {"name": "Manajer Uji", "id": "usr_mgr_fix9", "role": "manager"}))
    res = DB.material_reservations.find_one({"pr_id": pr_id, "status": "active"}, {"_id": 0})
    assert res and res["qty"] == 50 and res["source_warehouse_id"] == WH_B
    assert res["locked_qty"] == 50 and _locked(_r(rb["id"])) == 50
    # replan (lepas → cadangkan ulang): dulu DuplicateKey (id sama dengan cadangan yang dilepas, index unik uq_id FIX-5)
    from services import material_reservation_service as mres
    run(mres.release(pr_id, "replan qty baris 1", "uji"))
    assert _locked(_r(rb["id"])) == 0
    run(mres.reserve_for_pr(pr_id, "uji"))
    again = DB.material_reservations.find_one({"pr_id": pr_id, "status": "active"}, {"_id": 0})
    assert again["id"] != res["id"] and again["locked_qty"] == 50 and _locked(_r(rb["id"])) == 50
    DB.purchase_requisitions.delete_many({"id": pr_id})


# ── 2. Angka stok tidak dobel-kurang ────────────────────────────────────────────────────────────────────────────
def test_stock_figures_tidak_dobel_kurang_termasuk_total_grup():
    from services import makloon_roll_lock as L
    from services import stock_figures as sf
    _roll(WH_A, 40, 1)
    _roll(WH_A, 30, 2)
    _roll(WH_B, 100, 1)
    mko = _mko(60, reserve=False)
    # cadangan GAYA LAMA (belum terkunci) — rumus FIX-2: Tersedia = 170 − 60
    DB.material_reservations.insert_one({"id": f"mres_{mko['id']}", "product_id": P, "owner_entity_id": ENT,
                                         "ref_type": "makloon_order", "ref_id": mko["id"], "mko_id": mko["id"],
                                         "mko_number": mko["mko_number"], "qty": 60, "required_qty": 60,
                                         "status": "active", "source_warehouse_id": WH_A, "history": []})
    before = _avail()
    scope = {"entity_ids": [ENT], "site_ids": None}
    fig_before = run(sf.figures_for([P], scope))[P]
    assert before["available_qty"] == 110 and before["makloon_reserved_qty"] == 60
    run(L.lock(f"mres_{mko['id']}", "uji"))
    after = _avail()
    fig_after = run(sf.figures_for([P], scope))[P]
    assert after["available_qty"] == before["available_qty"] == 110                 # tidak dobel-kurang
    assert after["makloon_reserved_qty"] == 60 and after["makloon_locked_qty"] == 60
    assert after["reserved_qty"] == before["reserved_qty"] == 0                      # kunci tampil di "Cadangan makloon"
    assert after["on_hand_qty"] == before["on_hand_qty"] == 170
    assert fig_after["global"]["qty"] == fig_before["global"]["qty"]                 # Total grup sama
    assert fig_after["local"]["qty"] == fig_before["local"]["qty"]
    assert fig_after["global"]["rolls"] == 2                                         # roll 40 terkunci penuh keluar
    assert run(sf.makloon_by_product_entity([P])).get((P, ENT), 0.0) == 0.0          # kontribusi agregat 0
    rows = {r["key"]: r["qty"] for r in sf.status_rows(after)}
    assert rows["available"] == 110 and rows["makloon"] == 60 and rows["reserved"] == 0
    # baris saldo yang ditampilkan endpoint lama mengikuti definisi tunggal
    idx = sf.segment_index(run(sf.segments([P])))
    b = sf.adjust_balance_row(dict(DB.inventory_balances.find_one(
        {"product_id": P, "warehouse_id": WH_A, "owner_entity_id": ENT}, {"_id": 0})), idx)
    assert b["available_qty"] == 10 and b["makloon_reserved_qty"] == 60 and b["reserved_qty"] == 0


# ── 3. Stok kurang → sisa belum terkunci ────────────────────────────────────────────────────────────────────────
def test_kekurangan_stok_sisa_belum_terkunci_hanya_itu_yang_dialokasikan():
    from services import material_reservation_service as mres
    from services import stock_figures as sf
    _roll(WH_A, 50, 1)
    _roll(WH_B, 100, 1)
    mko = _mko(80)                                    # gudang sumber A hanya 50 bebas
    res = _res(mko["id"])
    assert res["qty"] == 80 and res["locked_qty"] == 50
    assert mres.unlocked_qty(res) == 30
    assert run(sf.makloon_by_product_entity([P]))[(P, ENT)] == 30
    t = _avail()
    assert t["available_qty"] == 150 - 80 and t["makloon_reserved_qty"] == 80
    assert any(h["event"] == "lock_shortage" for h in DB.material_reservations.find_one({"id": res["id"]})["history"])
    # pengaman komitmen hanya mengurangkan sisa belum terkunci (tidak dobel)
    assert run(mres.unlocked_by_others(P, ENT)) == 30
    assert run(mres.free_for_commitment(P, ENT)) == 70


# ── 4. Issue ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_issue_roll_terkunci_sendiri_lepas_atomik_dan_roll_lain_menggantikan_kunci():
    from services import makloon_order_service as mko_svc
    r1 = _roll(WH_A, 40, 1)
    r2 = _roll(WH_A, 30, 2)
    r3 = _roll(WH_A, 50, 3)
    mko = _mko(60)
    rid = _res(mko["id"])["id"]
    # issue parsial dengan roll yang TIDAK dikunci (r3 50): menggantikan kunci → kunci lama dilepas 50 (terbaru dulu)
    run(mko_svc.issue_step(mko["id"], 1, from_warehouse_id=WH_A, roll_ids=[r3["id"]], actor_name="uji"))
    res = DB.material_reservations.find_one({"id": rid}, {"_id": 0})
    assert res["status"] == "active" and res["qty"] == 10 and res["consumed_qty"] == 50
    assert res["locked_qty"] == 10
    assert _locked(_r(r1["id"])) + _locked(_r(r2["id"])) == 10
    assert _r(r3["id"])["status"] == "subcon" and not _r(r3["id"]).get("length_reservations")
    assert any(h["event"] == "trimmed" for h in res["history"])
    _no_overlock()


def test_issue_pilih_roll_terkunci_sendiri_boleh_dan_mko_lain_ditolak_menyebut_nomor():
    from services import makloon_order_service as mko_svc
    r1 = _roll(WH_A, 40, 1)
    r2 = _roll(WH_A, 30, 2)
    _roll(WH_A, 60, 3)
    mko_a = _mko(60)
    mko_b = _mko(10, reserve=False)
    # stok sumber di layar Issue: kunci MKO A dihitung tersedia untuk MKO A sendiri, tidak untuk MKO lain
    src_a = next(r for r in run(mko_svc._source_stock_rows(P, ENT, mko_a["id"])) if r["warehouse_id"] == WH_A)
    src_b = next(r for r in run(mko_svc._source_stock_rows(P, ENT, mko_b["id"])) if r["warehouse_id"] == WH_A)
    assert src_a["available_qty"] == 130 and src_a["locked_for_this_qty"] == 60
    assert src_b["available_qty"] == 70 and "locked_for_this_qty" not in src_b
    # MKO lain memilih roll yang dikunci MKO A → 409 menyebut nomor MKO A
    e = _err(mko_svc.issue_step(mko_b["id"], 1, from_warehouse_id=WH_A, roll_ids=[r1["id"]], actor_name="uji"))
    assert e.status_code == 409 and mko_a["mko_number"] in _text(e)
    # MKO A sendiri: roll terkunci boleh dikirim, kuncinya lepas di tulisan yang sama
    run(mko_svc.issue_step(mko_a["id"], 1, from_warehouse_id=WH_A, roll_ids=[r1["id"]], actor_name="uji"))
    assert _r(r1["id"])["status"] == "subcon" and _locked(_r(r1["id"])) == 0
    res = _res(mko_a["id"])
    assert res["qty"] == 20 and res["locked_qty"] == 20 and _locked(_r(r2["id"])) == 20
    _no_overlock()


def test_issue_jalur_jumlah_memakai_roll_terkunci_dulu():
    from services import makloon_order_service as mko_svc
    r_free_old = _roll(WH_A, 45, 1, length_reservations=[], length_reserved=0)
    mko_x = _mko(45)                                  # mengunci roll tertua (45)
    r_new = _roll(WH_A, 45, 5)
    # MKO lain jalur jumlah 40: roll terkunci MKO X tidak boleh dipakai → hanya r_new
    mko_y = _mko(40, reserve=False)
    run(mko_svc.issue_step(mko_y["id"], 1, from_warehouse_id=WH_A, actor_name="uji"))
    assert _r(r_free_old["id"])["status"] == "available" and _locked(_r(r_free_old["id"])) == 45
    # MKO X jalur jumlah: roll yang dikuncinya dipakai dulu
    run(mko_svc.issue_step(mko_x["id"], 1, from_warehouse_id=WH_A, actor_name="uji"))
    assert _r(r_free_old["id"])["status"] == "subcon" and _locked(_r(r_free_old["id"])) == 0
    assert _res(mko_x["id"])["status"] == "consumed" and _res(mko_x["id"])["locked_qty"] == 0
    _no_overlock()


# ── 5. Release ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_release_mko_batal_melepas_semua_idempoten():
    from services import makloon_order_service as mko_svc
    from services import material_reservation_service as mres
    r1 = _roll(WH_A, 40, 1)
    r2 = _roll(WH_A, 30, 2)
    mko = _mko(60)
    rid = _res(mko["id"])["id"]
    before = _avail()["available_qty"]
    run(mko_svc.cancel_order(mko["id"], reason="uji batal", actor_name="uji"))
    res = DB.material_reservations.find_one({"id": rid}, {"_id": 0})
    assert res["status"] == "released" and res["locked_qty"] == 0 and res["locks"] == []
    assert _locked(_r(r1["id"])) == 0 and _locked(_r(r2["id"])) == 0
    assert before == 10 and _avail()["available_qty"] == 70             # 60 terkunci kembali bebas
    assert any(h["event"] == "released_lock" for h in res["history"])
    assert run(mres.release(mko["id"], "ulang", "uji")) == 0        # idempoten
    _no_overlock()


# ── 6. Paralel (CAS) ─────────────────────────────────────────────────────────────────────────────────────────────
def test_paralel_dua_cadangan_tidak_mengunci_panjang_yang_sama():
    from services import material_reservation_service as mres
    from services import makloon_roll_lock as L
    _roll(WH_A, 40, 1)
    _roll(WH_A, 40, 2)
    a, b = _mko(50, reserve=False), _mko(50, reserve=False)

    async def both():
        return await asyncio.gather(mres.reserve_for_mko(a, "uji-a"), mres.reserve_for_mko(b, "uji-b"))
    run(both())
    ra, rb = _res(a["id"]), _res(b["id"])
    assert round(ra["qty"] + rb["qty"], 2) == 80                      # stok bebas 80 dibagi, tidak dijanjikan dua kali
    assert round(ra["locked_qty"] + rb["locked_qty"], 2) == 80
    _no_overlock()

    # kunci ulang paralel cadangan yang SAMA (klik ganda / skrip + issue) tidak melebihi qty
    run(L.unlock(ra["id"], "uji", qty=10))

    async def many():
        return await asyncio.gather(*[L.lock(ra["id"], "uji") for _ in range(5)])
    run(many())
    _no_overlock()
    assert round(sum(x["qty"] for x in run(L.actual_locks(ra["id"]))), 2) <= ra["qty"] + 0.01


# ── 7. Pemilih roll / SO / POS / transfer / tahan / pengambilan ─────────────────────────────────────────────────
def test_pemilih_roll_dan_so_menolak_panjang_terkunci_menyebut_mko():
    from services import sales_order_helpers as soh
    from services import stock_bucket_service as sb
    r1 = _roll(WH_A, 40, 1)
    r2 = _roll(WH_A, 30, 2)
    mko = _mko(60)                                    # r1 terkunci penuh, r2 terkunci 20 (bebas 10)
    # pemilih roll (desktop & HP memakai endpoint yang sama)
    out = run(roll_service.list_available_rolls(P, owner_entity_id=ENT))
    ids = {i["id"]: i for i in out["items"]}
    assert r1["id"] not in ids and ids[r2["id"]]["length_remaining"] == 10
    assert ids[r2["id"]]["makloon_lock"]["numbers"] == [mko["mko_number"]]
    assert out["makloon_unlocked_qty"] == 0
    # lintas PT: tanpa nomor dokumen
    hidden = run(roll_service.list_available_rolls(P, all_entities=True, visible_entity_ids=["ent_lain"]))
    assert next(i for i in hidden["items"] if i["id"] == r2["id"])["makloon_lock"]["numbers"] == []
    # alokasi SO / POS (mode Blokir): panjang terkunci tidak bisa diambil
    oid = f"so_TEST_FIX9_{TAG}_{_nx()}"
    e = _err(roll_service.allocate_and_reserve_rolls(P, 30, "", ENT, oid, policy={"makloon_reserve_mode": "block"}))
    assert e.status_code == 409
    assert _locked(_r(r1["id"])) == 40
    # beli per roll: minta lebih dari panjang bebas roll terkunci → 409 menyebut MKO
    e = _err(soh.reserve_roll_mode_item(oid, P, [{"roll_id": r2["id"], "take_qty": 25}], ENT, "uji", {}, {},
                                        policy={"makloon_reserve_mode": "block"}))
    assert e.status_code == 409 and mko["mko_number"] in _text(e)
    # transfer / pilihan roll utuh lain
    e = _err(roll_service.reserve_specific_rolls([{"roll_id": r1["id"], "take_qty": 0}],
                                                 {"type": "transfer", "id": f"trf_{TAG}"}, product_id=P))
    assert e.status_code == 409 and mko["mko_number"] in _text(e)
    # tahan/WIP (jalur jumlah) tidak mengambil roll terkunci
    e = _err(sb.hold_stock({"product_id": P, "warehouse_id": WH_A, "owner_entity_id": ENT, "quantity": 20},
                           "uji"))
    assert e.status_code == 409 and mko["mko_number"] in _text(e)
    assert _r(r1["id"])["status"] == "available"
    # pengambilan: roll terkunci dipindai untuk SO → ditolak menyebut MKO
    from routers.outbound_picking import _resolve_pick_roll
    task = {"product_id": P, "warehouse_id": WH_A, "entity_id": ENT, "order_id": oid}
    e = _err(_resolve_pick_roll(task, r1["roll_no"], "", "", None))
    assert e.status_code == 400 and mko["mko_number"] in _text(e)
    _no_overlock()


def test_mode_approve_persetujuan_manajer_meminjam_kunci():
    from services import material_reservation_service as mres
    from services import sales_order_helpers as soh
    r1 = _roll(WH_A, 40, 1)
    r2 = _roll(WH_A, 30, 2)
    mko = _mko(60)
    rid = _res(mko["id"])["id"]
    pol = {"makloon_reserve_mode": "approve"}
    oid = f"so_TEST_FIX9_{TAG}_{_nx()}"
    # tanpa persetujuan → minta persetujuan (409 MAKLOON_RESERVED_APPROVAL), kunci utuh
    e = _err(soh.reserve_roll_mode_item(oid, P, [{"roll_id": r2["id"], "take_qty": 25}], ENT, "uji", {}, {},
                                        policy=pol))
    assert e.detail["code"] == "MAKLOON_RESERVED_APPROVAL" and mko["mko_number"] in e.detail["message"]
    assert _res(mko["id"])["locked_qty"] == 60
    # dengan persetujuan (alokasi otomatis) → kunci DIPINJAM sebanyak kekurangan
    allocs = run(roll_service.allocate_and_reserve_rolls(P, 30, "", ENT, oid, policy=pol, makloon_override=True,
                                                         makloon_prompt=True))
    assert round(sum(a["quantity"] for a in allocs), 2) == 30
    assert allocs[0].get("makloon_overlap_qty", 0) > 0
    res = DB.material_reservations.find_one({"id": rid}, {"_id": 0})
    assert res["qty"] == 60 and res["locked_qty"] == 40                  # 20 dipinjam → sisa belum terkunci 20
    assert any(h["event"] == "borrowed" and h.get("order_id") == oid for h in res["history"])
    _no_overlock()
    run(roll_service.release_order_rolls(oid))
    assert run(mres.lock(rid, "uji"))["locked_qty"] == 60               # kunci bisa diisi lagi (idempoten)
    _no_overlock()
    assert _locked(_r(r1["id"])) + _locked(_r(r2["id"])) == 60


# ── 8. PR → MKO ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_pr_ke_mko_kunci_pindah_ke_gudang_sumber_dan_bernomor_mko():
    from services import makloon_roll_lock as L
    from services import material_reservation_service as mres
    rb = _roll(WH_B, 100, 1)                          # PR tanpa gudang → gudang bebas terbesar (B)
    ra = _roll(WH_A, 70, 1)
    pr_id = f"pr_TEST_FIX9_{TAG}_{_nx()}"
    rid = f"mres_{pr_id}_1"
    DB.material_reservations.insert_one({"id": rid, "product_id": P, "owner_entity_id": ENT,
                                         "ref_type": "purchase_requisition", "ref_id": pr_id, "pr_id": pr_id,
                                         "pr_number": "UJI9/PR-1", "pr_line_no": 1, "qty": 50, "required_qty": 50,
                                         "status": "active", "source_warehouse_id": "", "history": []})
    run(L.lock(rid, "uji"))
    assert _locked(_r(rb["id"])) == 50 and _locked(_r(ra["id"])) == 0
    mko = _mko(50, wh=WH_A, reserve=False)
    run(mres.transfer_to_mko(pr_id, 1, mko))
    res = DB.material_reservations.find_one({"id": rid}, {"_id": 0})
    assert res["ref_id"] == mko["id"] and res["source_warehouse_id"] == WH_A
    assert _locked(_r(ra["id"])) == 50 and _locked(_r(rb["id"])) == 0 and res["locked_qty"] == 50
    assert _r(ra["id"])["length_reservations"][0]["ref"]["number"] == mko["mko_number"]
    _no_overlock()


# ── 9. Skrip migrasi ────────────────────────────────────────────────────────────────────────────────────────────
SCRIPT = os.path.join(REPO, "scripts", "fix_data_2026_11_10_fix9_kunci_makloon.py")


def _script(*args):
    env = {**os.environ}
    p = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, timeout=300)
    return p.returncode, p.stdout + p.stderr


def test_skrip_migrasi_dryrun_apply_idempoten_undo_dan_pagar():
    r1 = _roll(WH_A, 40, 1)
    _roll(WH_A, 30, 2)
    mko = _mko(60, reserve=False)
    rid = f"mres_{mko['id']}"
    DB.material_reservations.insert_one({"id": rid, "product_id": P, "owner_entity_id": ENT,
                                         "ref_type": "makloon_order", "ref_id": mko["id"], "mko_id": mko["id"],
                                         "mko_number": mko["mko_number"], "qty": 60, "required_qty": 60,
                                         "status": "active", "history": []})          # cadangan lama tanpa kunci
    before = _avail()["available_qty"]
    code, out = _script("--db", DB_NAME, "--only", rid)
    assert code == 0, out
    assert "DRY-RUN" in out and r1["roll_no"] in out and mko["mko_number"] in out
    assert _locked(_r(r1["id"])) == 0 and not DB.material_reservations.find_one({"id": rid}).get("locked_qty")
    code, out = _script("--db", DB_NAME, "--only", rid, "--apply")
    assert code == 0, out
    assert DB.material_reservations.find_one({"id": rid})["locked_qty"] == 60 and _locked(_r(r1["id"])) == 40
    assert _avail()["available_qty"] == before                                        # angka Tersedia tetap
    assert DB.audit_logs.find_one({"entity_id": rid, "action": "data_fix_applied"})
    code, out = _script("--db", DB_NAME, "--only", rid, "--apply")                    # idempoten
    assert code == 0 and "qty_locked_new 0" in out, out
    code, out = _script("--db", DB_NAME, "--undo", "--apply")
    assert code == 0, out
    assert _locked(_r(r1["id"])) == 0 and DB.material_reservations.find_one({"id": rid})["locked_qty"] == 0
    # pagar DB
    assert _script("--db", "kainnusantara")[0] == 2
    assert _script("--db", "kainnusantara", "--production")[0] == 2               # tanpa bukti backup
    assert _script("--db", "db_lain")[0] == 2
