"""Regresi P08 fase 1 — W2-025 (turunan), W2-REQ-01 (pelaksana), W2-REQ-03 (uji wajib = peringatan).
Data sintetis TEST_P08_*, self-clean. Jalankan dari /app/backend: python <file>."""
import json
import os
import sys
import uuid

import bcrypt
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/backend/.env")
BASE = "http://localhost:8001/api"
A = "ent_ksc"
T = f"TEST_P08_{uuid.uuid4().hex[:6]}"
PWD = "demo12345"
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
results, users = [], []
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regression_p08_fase1_results.json")


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


def session_for(email):
    s = requests.Session()
    r = s.post(f"{BASE}/auth/login", json={"email": email, "password": PWD}, timeout=30)
    assert r.status_code == 200, r.text[:200]
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}", "X-Entity-Id": A})
    return s


def user(role, **extra):
    uid = f"user_{T}_{role}_{len(users)}".lower()
    db.users.insert_one({"id": uid, "email": f"{uid}@synthetic.test", "name": f"{T} {role} {len(users)}", "role": role,
                         "status": "active", "home_entity_id": A, "allowed_entity_ids": [A],
                         "password_hash": bcrypt.hashpw(PWD.encode(), bcrypt.gensalt()).decode(), **extra})
    users.append(uid)
    return uid, session_for(f"{uid}@synthetic.test")


def rnd(rid, sup, tcode, result="", status="open", attach=True):
    return {"id": rid, "round_no": 1, "supplier_id": sup, "supplier_name": "SUP", "type_code": tcode,
            "status": status, "result": result, "score": 90 if result == "acc" else None,
            "attachments": [{"id": "f1", "filename": "b.png"}] if attach else []}


def sample(sid, line, types, rounds, color="", spec_id=""):
    db.md_samples.insert_one({"id": sid, "number": sid, "title": sid, "entity_id": A, "line_code": line,
                              "status": "in_progress", "sample_types": types, "rounds": rounds, "spec_id": spec_id,
                              "participants": [{"supplier_id": rounds[0]["supplier_id"], "supplier_name": "SUP"}] if rounds else [],
                              "color_target": {"color_id": color} if color else {}, "timeline": [],
                              "created_at": "2099-01-01T00:00:00"})


def main():
    adm = session_for("admin@kainnusantara.id")
    sup = f"{T}_sup"
    db.suppliers.insert_one({"id": sup, "name": f"{T} supplier", "entity_id": A, "status": "active"})
    color = f"{T}_color"
    woven_id, woven = user("md", allowed_line_codes=["woven"])
    print_id, _ = user("md", allowed_line_codes=["printing"])

    # W2-025 — riwayat labdip & laporan pelaksana ikut pagar lini
    sample(f"{T}_HW", "woven", ["labdip"], [rnd("r1", sup, "labdip", "acc", "assessed")], color)
    sample(f"{T}_HP", "printing", ["labdip"], [rnd("r1", sup, "labdip", "acc", "assessed")], color)
    r = woven.get(f"{BASE}/rnd/labdip-history", params={"color_id": color}, timeout=30)
    ids = {x["sample_id"] for x in r.json().get("items", [])} if r.status_code == 200 else set()
    check("W2-025", "riwayat labdip woven-only tidak memuat sample printing", r.status_code == 200 and f"{T}_HP" not in ids and f"{T}_HW" in ids, (r.status_code, ids))
    r = adm.get(f"{BASE}/rnd/labdip-history", params={"color_id": color}, timeout=30)
    ids = {x["sample_id"] for x in r.json().get("items", [])}
    check("W2-025", "akun tanpa batas lini tetap melihat keduanya (kontrol)", {f"{T}_HW", f"{T}_HP"} <= ids, ids)
    r = woven.get(f"{BASE}/rnd/samples/{T}_HP/required-tests", timeout=30)
    check("W2-025", "endpoint turunan baru (required-tests) ikut ditolak lintas lini", r.status_code in (403, 404), r.status_code)

    # W2-REQ-01 — pelaksana fisik vs penginput
    sid = f"{T}_S1"
    sample(sid, "woven", ["labdip", "handfeel"], [rnd("rl", sup, "labdip"), rnd("rh", sup, "handfeel")])
    r = adm.get(f"{BASE}/rnd/samples/{sid}/performers", timeout=30)
    pids = {u["id"] for u in r.json().get("items", [])} if r.status_code == 200 else set()
    check("W2-REQ-01", "daftar pelaksana memuat MD woven, tidak memuat MD printing", woven_id in pids and print_id not in pids, (r.status_code, len(pids)))
    types = {t["value"]: t for t in adm.get(f"{BASE}/rnd/meta", timeout=30).json()["sample_types"]}
    meas = {f: (0.8 if f == "delta_e" else 4) for f in types["labdip"].get("measurement_fields") or []}
    r = adm.post(f"{BASE}/rnd/samples/{sid}/rounds/rl/submit", json={"note": "hasil", "measurements": meas}, timeout=30)
    check("W2-REQ-01", "setor tanpa pelaksana ditolak 422 tanpa mutasi", r.status_code == 422 and db.md_samples.find_one({"id": sid})["rounds"][0]["status"] == "open", (r.status_code, r.text[:150]))
    r = adm.post(f"{BASE}/rnd/samples/{sid}/rounds/rl/submit", json={"note": "hasil", "measurements": meas, "performed_by_user_id": print_id}, timeout=30)
    check("W2-REQ-01", "pelaksana di luar lini sample ditolak 422", r.status_code == 422, (r.status_code, r.text[:150]))
    r = adm.post(f"{BASE}/rnd/samples/{sid}/rounds/rl/submit", json={"note": "hasil", "measurements": meas, "performed_by_user_id": woven_id}, timeout=30)
    rd = next(x for x in db.md_samples.find_one({"id": sid})["rounds"] if x["id"] == "rl")
    if r.status_code != 200:
        print("submit detail:", r.text[:300])
    check("W2-REQ-01", "admin menginput untuk MD woven → performed_by=MD, recorded_by=admin",
          r.status_code == 200 and rd.get("performed_by_user_id") == woven_id and rd.get("recorded_by") and rd.get("recorded_by") != rd.get("performed_by"),
          (r.status_code, rd.get("performed_by"), rd.get("recorded_by")))

    # W2-REQ-03 — uji wajib = peringatan
    sid2 = f"{T}_S2"
    sample(sid2, "woven", ["labdip"], [rnd("ra", sup, "labdip", "acc", "assessed")])
    r = adm.get(f"{BASE}/rnd/samples/{sid2}/required-tests", params={"supplier_id": sup}, timeout=30)
    check("W2-REQ-03", "woven wajib labdip+handfeel (dari master lini); handfeel terdeteksi kurang", r.status_code == 200 and r.json().get("missing") == ["handfeel"], r.text[:200])
    body = {"supplier_id": sup, "reason_code": "warna_paling_dekat", "price": 1000}
    r = adm.post(f"{BASE}/rnd/samples/{sid2}/decide", json=body, timeout=60)
    check("W2-REQ-03", "keputusan tanpa alasan override → 422, status tetap", r.status_code == 422 and db.md_samples.find_one({"id": sid2})["status"] == "in_progress", (r.status_code, r.text[:150]))
    r = adm.post(f"{BASE}/rnd/samples/{sid2}/decide", json={**body, "override_reason": "Handfeel disetujui pelanggan langsung"}, timeout=60)
    doc = db.md_samples.find_one({"id": sid2})
    ov = (doc.get("decision") or {}).get("required_tests_override") or {}
    check("W2-REQ-03", "dengan alasan → diputus + override & timeline tercatat",
          r.status_code == 200 and doc["status"] == "decided" and ov.get("missing") == ["handfeel"] and any(t.get("event") == "required_tests_override" for t in doc.get("timeline") or []),
          (r.status_code, r.text[:150] if r.status_code != 200 else ov))
    sid3 = f"{T}_S3"
    sample(sid3, "woven", ["labdip", "handfeel"], [rnd("ra", sup, "labdip", "acc", "assessed"), rnd("rb", sup, "handfeel", "acc", "assessed")])
    r = adm.post(f"{BASE}/rnd/samples/{sid3}/decide", json=body, timeout=60)
    doc = db.md_samples.find_one({"id": sid3})
    check("W2-REQ-03", "semua uji wajib ACC → diputus tanpa alasan & tanpa override", r.status_code == 200 and not (doc.get("decision") or {}).get("required_tests_override"), (r.status_code, r.text[:150]))

    spec = f"{T}_SPEC"
    db.md_specs.insert_one({"id": spec, "number": spec, "title": spec, "entity_id": A, "line_code": "printing", "status": "review", "timeline": []})
    r = adm.get(f"{BASE}/rnd/specs/{spec}/required-tests", timeout=30)
    check("W2-REQ-03", "spesifikasi printing tanpa sample → uji wajib lini terdeteksi kurang", r.status_code == 200 and "proofing" in r.json().get("missing", []), r.text[:200])
    r = adm.post(f"{BASE}/rnd/specs/{spec}/approve", json={"note": "x"}, timeout=30)
    check("W2-REQ-03", "ACC spesifikasi tanpa alasan → 422, status tetap review", r.status_code == 422 and db.md_specs.find_one({"id": spec})["status"] == "review", (r.status_code, r.text[:150]))
    db.md_specs.update_one({"id": spec}, {"$set": {"status": "approved", "product_id": f"{T}_prod", "lifecycle": "disetujui"}})
    r = adm.post(f"{BASE}/rnd/specs/{spec}/release-product", json={"reason": "rilis uji"}, timeout=30)
    check("W2-REQ-03", "rilis tanpa alasan override → 422, lifecycle tetap", r.status_code == 422 and db.md_specs.find_one({"id": spec})["lifecycle"] == "disetujui", (r.status_code, r.text[:150]))
    legacy = f"{T}_SPEC_L"
    db.md_specs.insert_one({"id": legacy, "number": legacy, "entity_id": A, "line_code": "", "status": "review"})
    r = adm.get(f"{BASE}/rnd/specs/{legacy}/required-tests", timeout=30)
    check("W2-REQ-03", "spesifikasi legacy tanpa lini & tanpa sample → tidak ada uji wajib", r.status_code == 200 and r.json().get("missing") == [], r.text[:200])


def cleanup():
    nums = [d["number"] for d in db.md_samples.find({"id": {"$regex": f"^{T}"}}, {"number": 1})]
    db.supplier_contracts.delete_many({"sample_ref": {"$in": nums}})
    db.supplier_items.delete_many({"supplier_id": f"{T}_sup"})
    db.md_samples.delete_many({"id": {"$regex": f"^{T}"}})
    db.md_specs.delete_many({"id": {"$regex": f"^{T}"}})
    db.suppliers.delete_many({"id": f"{T}_sup"})
    db.audit_logs.delete_many({"entity_id": {"$regex": f"^{T}"}})
    db.approval_records.delete_many({"doc_id": {"$regex": f"^{T}"}})
    db.users.delete_many({"id": {"$in": users}})
    db.user_sessions.delete_many({"user_id": {"$in": users}})


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    with open(OUT, "w") as fh:
        json.dump({"tag": T, "results": results}, fh, indent=2, ensure_ascii=False)
    bad = [x for x in results if not x["pass"]]
    for x in results:
        print("PASS" if x["pass"] else "FAIL", x["id"], x["invariant"], "" if x["pass"] else x["detail"])
    print(f"{len(results) - len(bad)}/{len(results)} pass")
    sys.exit(1 if bad else 0)
