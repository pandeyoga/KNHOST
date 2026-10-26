"""Fase 4 · R6 — sisa backend & lintas layar audit UI tahap 2: uji tingkat layanan (tanpa HTTP, tanpa restart).

Memakai event loop BERSAMA `tests/_shared_loop.py` dan data uji berawalan `r6t` + akhiran acak yang dibersihkan di
akhir tiap uji. Tidak mengubah setelan global.
Jalankan: cd /app/backend && python -m pytest tests/test_phase4_r6.py -p no:randomly -n 0 -q
"""
import os
import re
import sys
import uuid

from pymongo import MongoClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _shared_loop import run  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[os.environ.get("DB_NAME", "test_database")]
TAG = uuid.uuid4().hex[:8]
TECH = re.compile(r"^[a-z][a-z0-9]*_[0-9a-f]{6,}$")


# ─── 1. Nomor dokumen di Jejak Audit (G5-01) ───────────────────────────────────────────────────────────────────
def test_audit_rows_get_doc_number_not_tech_id():
    from services.doc_label_service import attach_doc_numbers
    so_id, ret_id = f"so_{TAG}aa", f"sret_{TAG}bb"
    DB.sales_orders.insert_one({"id": so_id, "number": f"R6T/SO-{TAG}"})
    DB.sales_returns.insert_one({"id": ret_id, "number": f"R6T/SRET-{TAG}", "order_number": "R6T/SO-INDUK"})
    try:
        rows = [
            {"id": "a1", "entity_type": "sales_order", "entity_id": so_id, "after": {"status": "confirmed"}},
            # nomor sudah ada di isi baris → dipakai tanpa query
            {"id": "a2", "entity_type": "purchase_order", "entity_id": "po_zz", "after": {"po_number": "R6T/PO-1"}},
            # retur: `order_number` di isi baris = nomor INDUK, bukan nomor retur → harus dicari nomornya sendiri
            {"id": "a3", "entity_type": "sales_return", "entity_id": ret_id, "after": {"order_number": "R6T/SO-INDUK"}},
            # bentuk seed lama (resource/resource_id/details)
            {"id": "a4", "resource": "sales_orders", "resource_id": so_id, "details": {}},
            # id yang sudah kode manusiawi (kode akun) → tampil apa adanya
            {"id": "a5", "entity_type": "gl_account", "entity_id": "1-1100", "after": {}},
            # dokumen sudah dihapus → tanpa label (bukan id teknis)
            {"id": "a6", "entity_type": "sales_order", "entity_id": f"so_{TAG}dead", "after": {}},
        ]
        out = {r["id"]: r.get("doc_number") for r in run(attach_doc_numbers(rows))}
        assert out["a1"] == f"R6T/SO-{TAG}"
        assert out["a2"] == "R6T/PO-1"
        assert out["a3"] == f"R6T/SRET-{TAG}", out
        assert out["a4"] == f"R6T/SO-{TAG}"
        assert out["a5"] == "1-1100"
        assert out["a6"] is None
        assert not any(v and TECH.match(v) for v in out.values())
    finally:
        DB.sales_orders.delete_one({"id": so_id})
        DB.sales_returns.delete_one({"id": ret_id})


# ─── 2. Nomor dokumen di Cek Peran (G5-02) ─────────────────────────────────────────────────────────────────────
def test_role_reality_sample_uses_doc_number():
    from services import role_reality_service as rr
    uid, name, so_id = f"user_r6t_{TAG}", f"R6T Penguji {TAG}", f"so_{TAG}cc"
    DB.sales_orders.insert_one({"id": so_id, "number": f"R6T/SO-C{TAG}"})
    DB.audit_logs.insert_one({"id": f"audit_r6t_{TAG}", "actor": name, "action": "order_confirmed",
                              "entity_type": "sales_order", "entity_id": so_id, "after": {"status": "confirmed"},
                              "timestamp": "2026-10-26T00:00:00+00:00"})
    try:
        hits, _ = run(rr._collect_from_audit({uid: {"id": uid, "name": name}}, {name.lower(): uid}))
        samples = hits[uid]["order_confirm"]["samples"]
        assert samples == [f"R6T/SO-C{TAG}"], samples
        allS = [s for acts in hits.values() for ev in acts.values() for s in ev["samples"]]
        assert not [s for s in allS if TECH.match(s)], "contoh dokumen masih berisi id teknis"
    finally:
        DB.sales_orders.delete_one({"id": so_id})
        DB.audit_logs.delete_one({"id": f"audit_r6t_{TAG}"})


# ─── 3. Host QR di PDF dari URL publik (G5-11 sisa) ────────────────────────────────────────────────────────────
class _Req:
    def __init__(self, origin):
        self.headers = {"origin": origin}


def test_public_app_url_prefers_operator_setting(monkeypatch):
    from services import app_url
    monkeypatch.setenv("PUBLIC_APP_URL", "https://erp.contoh.id/")
    assert app_url.public_app_url(_Req("http://localhost:3063")) == "https://erp.contoh.id"
    assert app_url.public_app_url(None) == "https://erp.contoh.id"
    monkeypatch.delenv("PUBLIC_APP_URL")
    monkeypatch.setenv("APP_URL", "https://cadangan.contoh.id")
    # tanpa setelan operator: host pemanggil tetap dipakai (perilaku lama untuk instalasi tanpa domain)
    assert app_url.public_app_url(_Req("http://192.168.1.5:3000")) == "http://192.168.1.5:3000"
    assert app_url.public_app_url(None) == "https://cadangan.contoh.id"


# ─── 4. Kode wilayah di ubah badan usaha (G5-25) ───────────────────────────────────────────────────────────────
def test_entity_patch_accepts_location_codes():
    from services import entity_lifecycle_service as L
    from services import entity_location_service as LOC
    from services import entity_provisioning_service as P
    for k in ("province_code", "city_code", "district_code", "postal_code", "country_code"):
        assert k in L.EDITABLE_FIELDS
    existing = {"legal_name": "PT Uji R6", "short_name": "UJIR6", "type": "PT", "default_tax_mode": "non_ppn",
                "city": "Jakarta"}
    # patch tanpa lokasi → tidak menyentuh lokasi
    assert LOC.normalize_location_patch(existing, {"phone": "0812"}) == {}
    # kota teks lama + pilih provinsi/kota dari pemilih wilayah → kode & nama ternormalisasi
    out = run(P.validate_entity_input({"province_code": "32", "city_code": "32.73", "city": "Kota Bandung"},
                                      entity_id="ent_r6t", existing=existing))
    assert out["province_code"] == "32" and out["city_code"] == "32.73" and out["province"] == "Jawa Barat"
    assert out["location_status"] in ("partial", "verified")
    # nama kota diubah TANPA kode → kode lama dibuang lalu dihitung ulang dari nama (bukan menimpa diam-diam)
    lama = {**existing, "province": "Jawa Barat", "province_code": "32", "city": "Kota Bandung", "city_code": "32.73"}
    out2 = LOC.normalize_location_patch(lama, {"city": "Kota Cimahi"})
    assert out2["city"] == "Kota Cimahi" and out2["city_code"] != "32.73" and out2["city_code"].startswith("32")
    # bentuk seragam membawa field lokasi (form ubah bisa memakai LocationFields)
    u = L.uniform_entity({"id": "ent_r6t", **lama})
    assert u["province_code"] == "32" and u["city_code"] == "32.73" and "postal_code" in u


def test_entity_patch_rejects_inconsistent_location():
    import pytest
    from fastapi import HTTPException
    from services import entity_location_service as LOC
    with pytest.raises(HTTPException) as exc:
        LOC.normalize_location_patch({}, {"province_code": "31", "city_code": "32.73"})   # Bandung bukan di DKI
    assert exc.value.status_code == 400


# ─── 5. Langkah verifikasi yang dilewati ditandai server (G2-20) ───────────────────────────────────────────────
def test_journey_marks_skipped_verification_on_server():
    from services import order_journey_service as oj
    o = {"id": f"so_{TAG}jj", "number": "R6T/SO-J", "status": "approved", "approved_at": "2026-10-20T01:00:00",
         "grand_total": 100, "items": [{}]}
    j = run(oj.journey(o))
    st = {s["key"]: s for s in j["steps"]}
    assert st["diverifikasi"]["state"] == "skipped" and not st["diverifikasi"]["done"]
    assert st["diverifikasi"]["detail"].startswith("Dilewati")
    assert j["current_step"] == "dikonfirmasi", j["current_step"]       # dulu "diverifikasi"
    assert j["progress"]["skipped"] == 1 and j["progress"]["done"] == 2
    assert j["progress"]["percent"] == round(100.0 * 3 / len(j["steps"]), 1)
    # pesanan batal: langkah yang dilewati tetap "dilewati", sisanya "dibatalkan"
    j2 = run(oj.journey(dict(o, status="cancelled")))
    st2 = {s["key"]: s for s in j2["steps"]}
    assert st2["diverifikasi"]["state"] == "skipped" and st2["dikonfirmasi"]["state"] == "cancelled"
    assert j2["current_step"] == "dibatalkan"
    # pesanan baru (belum ada langkah sesudahnya) → verifikasi BELUM dilewati
    j3 = run(oj.journey(dict(o, status="pending", approved_at="")))
    assert {s["key"]: s for s in j3["steps"]}["diverifikasi"]["state"] == "pending"
    assert j3["current_step"] == "diverifikasi"


def test_journey_partial_preparation_is_not_skipped():
    from services import order_journey_service as oj
    steps = [oj._step(k, k, d) for k, d in (("dipesan", True), ("diverifikasi", True), ("disetujui", True),
                                             ("dikonfirmasi", True), ("disiapkan", False), ("dikirim", True),
                                             ("diterima", False), ("ditagih", True), ("dibayar", False))]
    oj._mark_skipped(steps, tasks=[{"id": 1}, {"id": 2}], prepared=[{"id": 1}])
    st = {s["key"]: s["state"] for s in steps}
    assert st["disiapkan"] == "partial" and st["diterima"] == "pending" and st["dibayar"] == "pending"


# ─── 6. G1-33 — eliminasi basi terdeteksi (angka tidak diubah) ─────────────────────────────────────────────────
def test_stale_g6_elimination_is_flagged_not_changed():
    from services import consolidation_service as cons
    pid, eid = f"icp_r6t{TAG}", f"icelim_r6t{TAG}"
    DB.intercompany_eliminations.insert_one({
        "id": eid, "name": f"Eliminasi otomatis antar-PT R6T/IC-{TAG}", "source_g6_pair_id": pid,
        "auto_generated": True, "effective_date": "2026-10-26",
        "lines": [{"account_code": "2-1250", "debit": 1000.0, "credit": 0.0},
                  {"account_code": "1-1250", "debit": 0.0, "credit": 1000.0}]})
    try:
        stale = {s["pair_id"]: s for s in run(cons.stale_g6_eliminations())}
        assert pid in stale
        assert stale[pid]["ic_ar_eliminated"] == 1000.0 and stale[pid]["gl_entries_left"] == 0
        # pair hidup → tidak basi
        DB.interco_transactions.insert_one({"id": f"ict_r6t{TAG}", "pair_id": pid, "role": "seller",
                                            "status": "invoiced"})
        assert pid not in {s["pair_id"] for s in run(cons.stale_g6_eliminations())}
        # entri tetap ada (deteksi baca-murni, bukan menghapus)
        assert DB.intercompany_eliminations.count_documents({"id": eid}) == 1
    finally:
        DB.intercompany_eliminations.delete_one({"id": eid})
        DB.interco_transactions.delete_one({"id": f"ict_r6t{TAG}"})


# ─── 7. G5-09 — notifikasi nota kredit & desain menunjuk dokumennya ───────────────────────────────────────────
def test_notification_doc_refs_for_credit_note_and_design():
    from services.notification_doc_ref import attach_doc_refs
    cn, so, dsg, clm, fil = f"cn_r6t{TAG}", f"so_{TAG}nn", f"dsgn_r6t{TAG}", f"dclm_r6t{TAG}", f"dfile_r6t{TAG}"
    DB.credit_notes.insert_one({"id": cn, "number": f"R6T/CN-{TAG}", "order_id": so, "order_number": f"R6T/SO-N{TAG}"})
    DB.design_gallery.insert_one({"id": dsg, "code": f"R6T-DSG-{TAG}", "title": "Uji R6",
                                  "claims": [{"id": clm}], "files": [{"id": fil}]})
    try:
        rows = [
            {"id": "n1", "type": "od_cancel_credit_note", "ref": f"{cn}#user_x", "link": "orders"},
            {"id": "n2", "type": "design_lifecycle", "ref": f"{dsg}:submitted:1#user_x", "link": "rnd-designs"},
            {"id": "n3", "type": "design_claim_pending", "ref": f"dclaim:{clm}#user_x", "link": "design-gallery"},
            {"id": "n4", "type": "design_claim_decided", "ref": f"dclaim-done:{clm}", "link": "design-gallery"},
            {"id": "n5", "type": "design_ai_comment", "ref": f"{fil}:cmt_1#user_x", "link": "design-gallery"},
            {"id": "n6", "type": "turn", "ref": "turn:x", "link": "operations"},
            {"id": "n7", "type": "design_lifecycle", "ref": f"dsgn_hilang{TAG}:draft:1", "link": "rnd-designs"},
        ]
        out = {r["id"]: r for r in run(attach_doc_refs(rows))}
        assert out["n1"]["doc"] == {"ref_type": "sales_order", "ref_id": so, "number": f"R6T/SO-N{TAG}",
                                    "label": f"Nota kredit R6T/CN-{TAG} di R6T/SO-N{TAG}"}
        for k in ("n2", "n3", "n4", "n5"):
            assert out[k]["doc"]["ref_type"] == "design" and out[k]["doc"]["ref_id"] == dsg, k
            assert out[k]["link"] == "rnd-designs", k            # link lama "design-gallery" bukan id layar
        assert "doc" not in out["n6"] and "doc" not in out["n7"]
    finally:
        DB.credit_notes.delete_one({"id": cn})
        DB.design_gallery.delete_one({"id": dsg})


# ─── 9. POC E4 — pengecualian setelan OCR tingkat instalasi beralasan & tidak basi ──────────────────────────────
def test_e4_poc_ocr_exception_matches_registry_and_consumer():
    import inspect
    import config_registry as cr
    from services import goods_receipt_ocr_service as ocr
    from test_core_e4_master_layers_poc import OCR_GLOBAL_BY_DESIGN
    ops = [e for e in cr.all_entries() if e["key"].split(".")[0] in ("hr", "uom", "lot", "receiving", "makloon")]
    only_global = {e["key"] for e in ops if "entity" not in (e.get("scopes") or [])}
    assert only_global == set(OCR_GLOBAL_BY_DESIGN), sorted(only_global ^ set(OCR_GLOBAL_BY_DESIGN))
    # konsumen membaca kunci-kunci ini TANPA konteks badan usaha (alasan pengecualian masih berlaku)
    src = inspect.getsource(ocr.ocr_config)
    assert 'e if k in ("ocr_enabled", "ocr_extract_packing_list",' in src
    assert all(k.split(".", 1)[1] not in ("ocr_enabled", "ocr_extract_packing_list", "client_po_patterns")
               for k in OCR_GLOBAL_BY_DESIGN)


# ─── 10. Teks bantu master tanpa backtick (G5-61 sisa) ─────────────────────────────────────────────────────────
def test_master_hints_have_no_backticks():
    from services.entity_master_service import MASTERS
    bad = [k for k, s in MASTERS.items() if "`" in (s.hint or "")]
    assert not bad, bad
