"""Regression: POST /api/transfers/{id}/receive with outcome='damaged' and note < 5 chars
must return 400 and NOT mutate any roll (all lines pre-validated before any landing).

Target data: KANDA/TRF-00003 (dispatched, 10 rolls in transit, ent_kanda).
Sends ONE bad request only, then verifies all 10 rolls still in_transit_transfer.
"""
import os
import sys
import asyncio
from pathlib import Path

import pytest
import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

WHADMIN = ("whadmin@kainnusantara.id", "demo1234")
ENT_KANDA = "ent_kanda"
TRF_CODE = "KANDA/TRF-00003"


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
            "X-Entity-Id": ENT_KANDA}


def test_damaged_short_note_does_not_mutate():
    from db import db

    tok = _login(*WHADMIN)

    async def _load():
        t = await db.warehouse_transfers.find_one({"code": TRF_CODE}, {"_id": 0})
        assert t, f"{TRF_CODE} missing"
        assert t["status"] == "dispatched", f"transfer status: {t['status']}"
        ids = [x["roll_id"] for it in (t.get("items") or []) for x in (it.get("rolls") or [])]
        assert len(ids) == 10, f"expected 10 rolls, got {len(ids)}"
        rolls_before = await db.inventory_rolls.find(
            {"id": {"$in": ids}}, {"_id": 0, "id": 1, "status": 1, "warehouse_id": 1}
        ).to_list(50)
        return t["id"], ids, rolls_before

    tid, roll_ids, before = asyncio.get_event_loop().run_until_complete(_load())
    assert all(b["status"] == "in_transit_transfer" for b in before), before

    # Fire ONE bad request: damaged with short note
    r = requests.post(
        f"{BASE_URL}/api/transfers/{tid}/receive",
        headers=_h(tok),
        json={"lines": [{"roll_id": roll_ids[0], "outcome": "damaged", "note": "x"}]},
        timeout=15,
    )
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"

    # Verify: all 10 rolls remain in_transit_transfer (no mutation)
    async def _after():
        return await db.inventory_rolls.find(
            {"id": {"$in": roll_ids}}, {"_id": 0, "id": 1, "status": 1, "warehouse_id": 1}
        ).to_list(50)

    after = asyncio.get_event_loop().run_until_complete(_after())
    bad = [x for x in after if x["status"] != "in_transit_transfer"]
    assert not bad, f"rolls mutated despite 400: {bad}"

    # Verify: transfer still dispatched (no partial state)
    async def _t():
        return await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0, "status": 1})

    t = asyncio.get_event_loop().run_until_complete(_t())
    assert t["status"] == "dispatched", f"transfer status mutated: {t}"

    # Verify: no damaged exception recorded
    s = requests.get(f"{BASE_URL}/api/transfers/{tid}/receipt", headers=_h(tok), timeout=15).json()
    damaged = [e for e in (s.get("exceptions") or []) if e["kind"] == "damaged" and e.get("roll_id") == roll_ids[0]]
    assert not damaged, f"unexpected damaged exception: {damaged}"
