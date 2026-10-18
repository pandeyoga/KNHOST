"""G3 Fase 05 — regresi, duplikasi, validasi penutupan.

    cd /app/backend && DB_NAME=g3_audit_phase05 python -m pytest tests/test_g3_phase05.py -q -n 0
"""
import ast
import asyncio
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DB_NAME", "").startswith("g3_audit"):
    pytest.skip("Set DB_NAME=g3_audit_*", allow_module_level=True)

sys.path.insert(0, os.path.dirname(__file__))
from db import db  # noqa: E402
from atp_oracle import atp_mismatches  # noqa: E402

BACKEND = pathlib.Path(__file__).resolve().parents[1]


def run(c):
    return asyncio.get_event_loop().run_until_complete(c)


@pytest.fixture(autouse=True)
def _clean():
    async def wipe():
        for c in await db.list_collection_names():
            await db[c].delete_many({})
    run(wipe())
    yield


# V3-DUP-01 — quality check: tidak ada definisi top-level ganda di backend
def test_no_duplicate_top_level_defs():
    dups = []
    for f in BACKEND.rglob("*.py"):
        if any(p in f.parts for p in ("tests", "node_modules", ".venv", "__pycache__")):
            continue
        names = {}
        for node in ast.parse(f.read_text(encoding="utf-8")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.setdefault(node.name, []).append(node.lineno)
        dups += [f"{f.relative_to(BACKEND)}:{n}{ls}" for n, ls in names.items() if len(ls) > 1]
    assert not dups, dups


def test_custom_role_clean_perms_contract():
    from fastapi import HTTPException
    from services.custom_role_service import _clean_perms
    with pytest.raises(HTTPException) as e:
        _clean_perms({"order": "bukan-level"})
    assert e.value.status_code == 400


# V3-BUILD-01 — lockfile canonical tidak diabaikan git
def test_yarn_lock_not_gitignored():
    gi = (BACKEND.parent / ".gitignore").read_text().splitlines()
    assert "frontend/yarn.lock" not in [x.strip() for x in gi]
    assert (BACKEND.parent / "frontend" / "yarn.lock").exists()
    assert not (BACKEND.parent / "frontend" / "package-lock.json").exists()
    # salinan untuk build VPS (platform tidak mem-push *.lock) harus identik
    assert (BACKEND.parent / "deploy" / "frontend-yarnlock.txt").read_bytes() == \
        (BACKEND.parent / "frontend" / "yarn.lock").read_bytes()


# D4-CB-01 — duplikat di awal/tengah/akhir > 2.000 kontrabon terdeteksi
@pytest.mark.parametrize("pos", [0, 1200, 2101])
def test_contra_bon_scan_full_cursor(pos):
    from services import contra_bon_scan as cbn
    from services import contra_bon_service as svc
    live = sorted(svc.HOLDING_STATUSES)[0]

    async def go():
        docs = [{"id": f"cb{i}", "number": f"CB-{i}", "status": live,
                 "bills": [{"bill_id": f"b{i}", "applied_amount": 1}]} for i in range(2102)]
        docs.append({"id": "cbX", "number": "CB-X", "status": "cancelled",
                     "bills": [{"bill_id": "b5", "applied_amount": 1}]})
        docs[pos]["bills"].append({"bill_id": "bDUP", "applied_amount": 1})
        docs[(pos + 1) % 2102]["bills"].append({"bill_id": "bDUP", "applied_amount": 1})
        await db[cbn.COLL].insert_many(docs)
        return await cbn.bills_in_multiple_contra_bons(), await cbn.stats()
    dup, st = run(go())
    assert [d["bill_id"] for d in dup] == ["bDUP"]
    assert st["scanned"] == st["live_total"] == 2102 and st["complete"] is True


# D4-TEST-01 — oracle ATP independen dari fixture (>100 SKU, multi-owner, hold, pending, incoming)
def test_atp_oracle_against_fixture():
    from services import fulfillment_service as fs
    from services import atp_policy as ap

    async def go():
        n = 105
        now = datetime.now(timezone.utc)
        await db.products.insert_many([{"id": f"p{i}", "sku": f"S{i}"} for i in range(n)])
        bals, pos, sos, expect = [], [], [], {}
        for i in range(n):
            for ent, wh in (("A", "wA"), ("B", "wB")):
                av, rsv, hold = 10.0 + i, float(i % 3), float(i % 4)
                bals.append({"product_id": f"p{i}", "owner_entity_id": ent, "warehouse_id": wh,
                             "available_qty": av, "reserved_qty": rsv, "on_hand_qty": av + rsv + hold})
                inc = 5.0 if i % 2 == 0 else 0.0
                if inc:
                    pos.append({"id": f"po{i}{ent}", "status": "approved", "entity_id": ent, "warehouse_id": wh,
                                "expected_delivery_date": (now + timedelta(days=3)).isoformat(),
                                "items": [{"product_id": f"p{i}", "quantity": 8, "received_qty": 3}]})
                pos.append({"id": f"pof{i}{ent}", "status": "approved", "entity_id": ent, "warehouse_id": wh,
                            "expected_delivery_date": (now + timedelta(days=ap.ATP_HORIZON_DAYS + 30)).isoformat(),
                            "items": [{"product_id": f"p{i}", "quantity": 99, "received_qty": 0}]})
                pend = 2.0 if i % 5 == 0 else 0.0
                if pend:
                    sos.append({"id": f"so{i}{ent}", "entity_id": ent, "has_backorder": True,
                                "status": ap.ACTIVE_BACKORDER_STATUSES[0],
                                "backorders": [{"product_id": f"p{i}", "backorder_qty": pend, "warehouse_id": wh}]})
                expect[(f"S{i}", ent)] = av + inc - pend
        await db.inventory_balances.insert_many(bals)
        await db.purchase_orders.insert_many(pos)
        await db.sales_orders.insert_many(sos)
        return await fs.status_board(), expect
    rows, expect = run(go())
    assert len(rows) == 105
    got = {(r["sku"], e["entity_id"]): e["atp"] for r in rows for e in r["by_entity"]}
    assert {k: round(v, 2) for k, v in got.items()} == {k: round(v, 2) for k, v in expect.items()}
    assert atp_mismatches(rows) == []
    bad = [dict(r) for r in rows]
    bad[50] = {**bad[50], "total_atp": bad[50]["total_atp"] + float(bad[50]["total_reserved"] or 1)}
    assert atp_mismatches(bad), "oracle wajib GAGAL terhadap ATP yang dimutasi"
