"""L04 LN-040 — acceptance dengan OCR SUNGGUHAN (OpenAI): SJ 10 roll total 960 vs PO 1000.

T01: OCR → draf 10 roll + qty masing-masing → user koreksi → hitung fisik → tutup → 10 identitas roll, total 960,
     roll yang terbaca ragu ditandai. T02: kirim ulang (roll/close/finish) tidak menggandakan roll/stok/notifikasi;
     selisih 40 terhadap PO tetap terlihat. Lewati bila kunci OpenAI tidak ada.
"""
import io
import os
import sys
import uuid

import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "/app/backend")
sys.path.insert(0, "/app/backend/tests")
import test_grn_phase2 as _p2  # noqa: E402,F401
from test_grn_phase2 import BASE, _ok, admin, env, mdb, _supplier  # noqa: E402,F401
import requests  # noqa: E402


@pytest.fixture(scope="module")
def wh():
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": "warehouse@kainnusantara.id", "password": "demo12345"}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['token']}"
    return s

LENGTHS = [100, 98, 95, 97, 96, 94, 99, 93, 92, 96]          # Σ 960
FONT = "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
FONT_B = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"


def _has_key():
    env_txt = open("/app/backend/.env").read()
    return "OPENAI_API_KEY" in env_txt or os.environ.get("OPENAI_API_KEY")


def sj_image(po_number, product, dn_no, smudge_seq=None):
    img = Image.new("RGB", (1654, 2339), "white")
    d = ImageDraw.Draw(img)
    f, fb, fs = ImageFont.truetype(FONT, 34), ImageFont.truetype(FONT_B, 44), ImageFont.truetype(FONT, 30)
    d.text((90, 80), "PT ALICE KNIT TEXTILE", font=fb, fill="black")
    d.text((90, 140), "Jl. Industri Raya 12, Bandung", font=fs, fill="black")
    d.text((1000, 80), "SURAT JALAN", font=fb, fill="black")
    d.text((1000, 150), f"No: {dn_no}", font=f, fill="black")
    d.text((1000, 200), "Tanggal: 16-10-2026", font=f, fill="black")
    d.text((90, 260), "Kepada: PT KAIN NUSANTARA (KSC)", font=f, fill="black")
    d.text((90, 310), f"No. PO: {po_number}", font=f, fill="black")
    y = 400
    d.line((90, y, 1560, y), fill="black", width=3)
    for x, h in ((100, "No"), (200, "Nama Barang"), (900, "Roll"), (1100, "Qty"), (1350, "Satuan")):
        d.text((x, y + 15), h, font=fb, fill="black")
    d.line((90, y + 75, 1560, y + 75), fill="black", width=2)
    d.text((100, y + 95), "1", font=f, fill="black")
    d.text((200, y + 95), product, font=f, fill="black")
    d.text((900, y + 95), "10", font=f, fill="black")
    d.text((1100, y + 95), "960,00", font=f, fill="black")
    d.text((1350, y + 95), "YARD", font=f, fill="black")
    d.line((90, y + 160, 1560, y + 160), fill="black", width=2)
    d.text((800, y + 180), "TOTAL:  10 ROLL   960,00 YARD", font=fb, fill="black")
    y = 760
    d.text((90, y), f"PACKING LIST — {product}", font=fb, fill="black")
    y += 80
    d.text((120, y), "Roll", font=fb, fill="black"); d.text((420, y), "Panjang (yard)", font=fb, fill="black")
    for i, ln in enumerate(LENGTHS, 1):
        yy = y + 60 * i
        d.text((120, yy), str(i), font=f, fill="black")
        d.text((420, yy), f"{ln},00", font=f, fill="black")
        if i == smudge_seq:   # bekas coretan tinta → angka ragu
            for k in range(12):
                d.line((400 + k * 12, yy - 5, 430 + k * 12, yy + 45), fill=(60, 60, 60), width=7)
    d.text((120, y + 60 * 11 + 20), "Subtotal: 960,00 yard", font=fb, fill="black")
    d.text((90, 2150), "Penerima: ____________        Pengirim: ____________", font=f, fill="black")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


def _cfg(s, values):
    items = [{"key": k, "value": v, "scope_type": "global", "reason": "TEST_ LN-040"} for k, v in values.items()]
    _ok(s.put(f"{BASE}/config/values", json={"items": items}))


@pytest.mark.skipif(not _has_key(), reason="kunci OpenAI tidak ada")
def test_ln040_real_ocr_ten_rolls_correct_commit_and_resend(admin, wh, mdb, env):  # noqa: F811
    keep, clone = env
    seed = mdb.wms_tasks.find_one({"flow_type": "inbound", "entity_id": "ent_ksc", "unit": "yard", "po_id": {"$gt": ""},
                                   "status": {"$in": ["waiting_goods", "receiving"]}}, {"_id": 0, "product_id": 1})
    if not seed:
        pytest.skip("tak ada tugas inbound yard")
    t = clone(product_id=seed["product_id"], park_seed=True)
    keep("purchase_orders", t["po_id"])
    mdb.wms_tasks.update_one({"id": t["id"]}, {"$set": {"expected_qty": 1000.0, "received_qty": 0.0, "unit": "yard"}})
    po = mdb.purchase_orders.find_one({"id": t["po_id"]}, {"_id": 0})
    po_no = po.get("po_number") or po.get("number") or t.get("po_number")
    items = _ok(admin.get(f"{BASE}/config/effective", params={"group": "penerimaan"}))["items"]
    keys = ("receiving.ocr_enabled", "receiving.ocr_extract_packing_list", "receiving.ocr_second_reader_mode")
    prev = {i["key"]: i.get("value") for i in items if i["key"] in keys}
    _cfg(admin, {"receiving.ocr_enabled": True, "receiving.ocr_extract_packing_list": True,
                 "receiving.ocr_second_reader_mode": "off"})
    try:
        dn_no = f"SJ/AK/{uuid.uuid4().hex[:5].upper()}"
        g = _ok(admin.post(f"{BASE}/goods-receipts", json={"partner_type": "supplier", "partner_id": _supplier(mdb, t),
                                                           "warehouse_id": t["warehouse_id"], "po_ids": [t["po_id"]]}))
        g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/files",
                           files={"file": ("sj.jpg", sj_image(po_no, t["product_name"], dn_no, smudge_seq=7), "image/jpeg")},
                           data={"expected_version": str(g["version"])}))["grn"]
        g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/read", json={"expected_version": g["version"]}))
        assert not g.get("extraction", {}).get("is_mock")
        stock = [ln for ln in g["lines"] if not ln.get("is_non_stock")]
        assert len(stock) == 1, g["lines"]
        ln = stock[0]
        er = ln.get("expected_rolls") or []
        print("OCR rolls:", [(r["seq"], r.get("length"), r.get("doc_status")) for r in er], "warnings:", g["extraction"].get("warnings"))
        # T01 — draf per roll dari OCR (bukan posting)
        assert len(er) == 10 and g["status"] == "review" and ln["verified"] is False
        assert ln["declared"]["rolls"] == 10 and ln["declared"]["qty"] == 960
        ok_seqs = [r["seq"] for r in er if r["seq"] != 7]
        assert [r.get("length") for r in er if r["seq"] in ok_seqs] == [LENGTHS[s - 1] for s in ok_seqs]
        flagged = [r for r in er if r.get("doc_status") != "ok" or r.get("length") != LENGTHS[r["seq"] - 1]]
        # Roll #7 dicoret: harus ditandai ragu ATAU terbaca benar; tak boleh diam-diam salah tanpa tanda.
        r7 = er[6]
        assert r7.get("length") == LENGTHS[6] or r7.get("doc_status") != "ok" or (ln.get("pl_check") or {}).get("uncertain") \
            or (ln.get("pl_check") or {}).get("subtotal_match") is False, r7
        # user koreksi → semua roll benar (roll #7 = 99)
        target = {"type": "po_task", "task_id": t["id"]}
        g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/lines/{ln['line_no']}", json={
            "expected_version": g["version"], "target": target,
            "expected_rolls": [{"length": v, "length_unit": "yard"} for v in LENGTHS]}))
        if not g["dn"].get("verified"):
            g = _ok(admin.patch(f"{BASE}/goods-receipts/{g['id']}/dn", json={"expected_version": g["version"], "number": dn_no}))
        ln = next(x for x in g["lines"] if x["line_no"] == ln["line_no"])
        assert ln["verified"] is True and sum(r["length"] for r in ln["expected_rolls"]) == 960
        assert any(r.get("corrected") for r in ln["expected_rolls"]) == bool(flagged)
        g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/start-count", json={"expected_version": g["version"]}))
        lno = ln["line_no"]
        for seq, length in enumerate(LENGTHS, 1):
            body = {"length": length, "lot": "LOT-AK-1016", "grade": "A", "expected_seq": seq}
            res = _ok(wh.post(f"{BASE}/goods-receipts/{g['id']}/lines/{lno}/rolls", json=body,
                              headers={"Idempotency-Key": f"TEST-ln040-{g['id']}-{seq}"}))
            if seq == 3:   # T02 — HP mengirim ulang permintaan yang sama
                rep = wh.post(f"{BASE}/goods-receipts/{g['id']}/lines/{lno}/rolls", json=body,
                              headers={"Idempotency-Key": f"TEST-ln040-{g['id']}-{seq}"})
                assert rep.status_code == 200 and rep.headers.get("X-Idempotent-Replay") == "true"
                assert rep.json()["roll"]["id"] == res["roll"]["id"]
                assert wh.post(f"{BASE}/goods-receipts/{g['id']}/lines/{lno}/rolls", json=body).status_code == 409
        rolls = list(mdb.inventory_rolls.find({"grn_id": g["id"]}, {"_id": 0}))
        assert len(rolls) == 10 and len({r["roll_no"] for r in rolls}) == 10
        assert round(sum(r["length_initial"] for r in rolls), 2) == 960
        g = _ok(wh.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": res["grn"]["version"]}))
        assert wh.post(f"{BASE}/goods-receipts/{g['id']}/finish-count", json={"expected_version": g["version"] - 1}).status_code == 409
        g = _ok(admin.get(f"{BASE}/goods-receipts/{g['id']}"))
        for dsc in [x for x in g.get("discrepancies") or [] if x.get("blocking") and x.get("status") == "open"]:
            g = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/discrepancies/{dsc['key']}/resolve", json={
                "expected_version": g["version"], "action": "accept_note", "reason": "TEST_ selisih"}))
        notif0 = mdb.notifications.count_documents({})
        out = _ok(admin.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": g["version"]}))
        assert out["grn"]["status"] == "closed"
        notif1 = mdb.notifications.count_documents({})
        r = admin.post(f"{BASE}/goods-receipts/{g['id']}/close", json={"expected_version": out["grn"]["version"]})
        assert r.status_code == 409
        assert mdb.notifications.count_documents({}) == notif1 and notif1 >= notif0
        assert mdb.inventory_rolls.count_documents({"grn_id": g["id"]}) == 10
        assert mdb.journal_entries.count_documents({"source_type": "goods_receipt", "source_id": t["id"]}) == 1
        task = mdb.wms_tasks.find_one({"id": t["id"]})
        assert task["received_qty"] == 960
        # selisih 40 terhadap PO tetap terlihat (sisa tugas / remainder)
        rem = list(mdb.wms_tasks.find({"remainder_of": t["id"]}, {"_id": 0, "expected_qty": 1}))
        assert (task["expected_qty"] - task["received_qty"] == 40) or (rem and rem[0]["expected_qty"] == 40), (task, rem)
        print("PASS LN-040", g["number"], "rolls", len(rolls), "flagged", [r["seq"] for r in flagged])
    finally:
        _cfg(admin, {k: v for k, v in prev.items() if v is not None} or {"receiving.ocr_enabled": False})
