"""AUD-RND-01 / AUD-RND-02 (review 2026-10-19) — uji ulang supplier.

RND-01: "lulus" hanya bila round FINAL tiap jenis uji ACC; referensi keputusan = round-round final itu.
RND-02: versi artwork proofing ulang harus ada di riwayat versi desain dan sudah di-ACC.
Memakai helper & pembersihan tes LN-034 (siklus uji ulang dibuat lewat API; round hasil penilaian disiapkan
langsung seperti tes LN-034 — penilaian round bukan bagian temuan ini).
Jalankan: cd /app/backend && python -m pytest tests/test_aud_rnd_0102.py -p no:randomly -n 0 -q
"""
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import requests  # noqa: E402
import test_l03_ln034_revalidation as m  # noqa: E402

H = m.H
cleanup = m.cleanup
DB, BASE, TAG = m.DB, m.BASE, uuid.uuid4().hex[:6]


def _rounds(sid, sup, rows):
    DB.md_samples.update_one({"id": sid}, {"$set": {"status": "assessed", "rounds": [
        {"id": f"rnd_{uuid.uuid4().hex[:6]}", "round_no": no, "supplier_id": sup, "type_code": t, "result": res, "score": 1.5,
         "assessed_at": f"2026-10-2{no}T00:00:00"} for no, t, res in rows]}})


def _new(H, types=("labdip", "handfeel")):
    # siklus terbuka dari tes sebelumnya (SKU×supplier sama) memblokir siklus baru — aturan sah; bersihkan dulu
    DB.md_samples.delete_many({"revalidation.reason": {"$regex": TAG}, "status": {"$ne": "decided"}})
    r = m._create(H, m.SUP_A, types=types, reason=f"uji multi jenis {TAG}")
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


# ─── AUD-RND-01 ────────────────────────────────────────────────────────────────
def test_labdip_acc_handfeel_tolak_tidak_bisa_lulus(H):
    sid = _new(H)
    _rounds(sid, m.SUP_A, [(1, "labdip", "acc"), (2, "handfeel", "tolak")])
    r = m._decide(H, sid, "pass", note="ok")
    assert r.status_code == 400 and "handfeel" in r.text, r.text
    assert DB.md_samples.find_one({"id": sid})["status"] == "assessed"
    f = m._decide(H, sid, "fail", note="handfeel ditolak supplier")   # gagal tetap boleh dicatat
    assert f.status_code == 200, f.text
    dec = f.json()["decision"]
    assert {b["type"]: b["result"] for b in dec["basis_rounds"]} == {"labdip": "acc", "handfeel": "tolak"}
    DB.md_samples.delete_one({"id": sid})   # siklus menunggu PIC memblokir siklus baru SKU×supplier yang sama (aturan sah)


def test_jenis_uji_belum_dinilai_tidak_bisa_lulus(H):
    sid = _new(H)
    _rounds(sid, m.SUP_A, [(1, "labdip", "acc")])
    r = m._decide(H, sid, "pass", note="ok")
    assert r.status_code == 400 and "handfeel" in r.text, r.text


def test_revisi_acc_lulus_dengan_referensi_round_final(H):
    sid = _new(H)
    _rounds(sid, m.SUP_A, [(1, "labdip", "acc"), (2, "handfeel", "tolak"), (3, "handfeel", "acc")])
    r = m._decide(H, sid, "pass", note="ok setelah revisi")
    assert r.status_code == 200, r.text
    dec = r.json()["decision"]
    assert dec["result"] == "pass" and dec["round_no"] == 3
    assert {b["type"]: (b["round_no"], b["result"]) for b in dec["basis_rounds"]} == {"labdip": (1, "acc"), "handfeel": (3, "acc")}


def test_keputusan_bersamaan_hanya_satu(H):
    sid = _new(H, types=("labdip",))
    _rounds(sid, m.SUP_A, [(1, "labdip", "acc")])
    with ThreadPoolExecutor(2) as ex:
        codes = sorted(f.result().status_code for f in [ex.submit(m._decide, H, sid, "pass", "ok") for _ in range(2)])
    assert codes == [200, 400], codes
    assert len([x for x in DB.products.find_one({"id": m.PROD["id"]}).get("rnd_test_history") or [] if x["sample_id"] == sid]) == 1


# ─── AUD-RND-02 ────────────────────────────────────────────────────────────────
def _design(versions, approved_version=None, current=None):
    src = DB.design_gallery.find_one({"id": {"$not": {"$regex": "^dsgn_TEST_"}}}, {"_id": 0})
    did = f"dsgn_TEST_V_{TAG}_{uuid.uuid4().hex[:4]}"
    DB.design_gallery.insert_one({**src, "id": did, "code": f"TV-{TAG}", "status": "approved", "on_hold": False,
                                  "version": current or max(v for v, _ in versions),
                                  "versions": [{"version": v, "acc": acc} for v, acc in versions],
                                  **({"approved_version": approved_version} if approved_version else {})})
    DB.md_specs.delete_many({"id": m.SPEC_TEST})
    DB.md_specs.insert_one({"id": m.SPEC_TEST, "product_id": m.PROD["id"], "design_id": did, "design_version": None,
                            "created_at": "2099-01-01T00:00:00", "status": "approved", "title": f"TEST_{TAG}"})
    return did


def test_versi_artwork_tidak_ada_atau_belum_acc_ditolak_historis_sah_diterima(H):
    did = _design([(1, True), (2, False), (3, True)], approved_version=3)
    try:
        bad = m._create(H, m.SUP_A, types=("proofing",), reason=f"proofing v999 {TAG}", design_id=did, design_version=999)
        assert bad.status_code == 400 and "tidak ada" in bad.text, bad.text
        unacc = m._create(H, m.SUP_A, types=("proofing",), reason=f"proofing v2 {TAG}", design_id=did, design_version=2)
        assert unacc.status_code == 400 and "belum di-ACC" in unacc.text, unacc.text
        hist = m._create(H, m.SUP_A, types=("proofing",), reason=f"proofing v1 {TAG}", design_id=did, design_version=1)
        assert hist.status_code in (200, 201), hist.text
        assert hist.json()["design_version"] == 1
    finally:
        DB.design_gallery.delete_one({"id": did})
