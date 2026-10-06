"""CX-10 invariants — e-sign bound to document content version. Real service functions, LOCAL synthetic DB.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-01-P01-ix06-cx10/repro_cx10.py
Fixture: clone of one sales order (invoice doc_type) with synthetic id; mutated after signing; all removed after.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
results = []


def check(name, ok, detail=""):
    results.append({"id": "CX-10", "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def sign(es, db, doc_type, sid, ent, signer):
    r = await es.create_request(doc_type, sid, ent, signer, "Direktur", "", "audit-cx10", "simulated")
    await db.esign_requests.update_one({"id": r["request_id"]}, {"$set": {"otp_hash": es.hash_otp("123456")}})
    return await es.verify_and_sign(r["request_id"], "123456", "data:image/png;base64,AAAA")


async def main():
    from db import db
    from services import esign_service as es
    from services import pdf_service as pdf
    T = f"audit_cx10_{uuid.uuid4().hex[:6]}"
    base = await db.sales_orders.find_one({"entity_id": "ent_ksc", "items.0": {"$exists": True}}, {"_id": 0})
    so = {**base, "id": f"so_{T}", "number": f"SO-{T}"}
    await db.sales_orders.insert_one(dict(so))
    try:
        s1 = await sign(es, db, "invoice", so["id"], "ent_ksc", "Signer Versi 1")
        b1 = await pdf.build_document("invoice", so["id"], "ent_ksc")
        check("control: signed version carries esign block", (b1["doc"].get("esign") or {}).get("code") == s1["verification_code"],
              b1["doc"].get("esign"))
        v1 = await es.public_verify(s1["verification_code"])
        check("control: verify on unchanged doc = current", v1.get("version_status") == "current", v1.get("version_status"))
        await db.sales_orders.update_one({"id": so["id"]}, {"$set": {"customer_name": "PENERIMA DIUBAH SETELAH TTD",
                                                                    "items.0.qty": float(base["items"][0].get("qty", 1)) + 7}})
        b2 = await pdf.build_document("invoice", so["id"], "ent_ksc")
        check("changed doc does NOT carry old signature", not b2["doc"].get("esign"), b2["doc"].get("esign"))
        check("changed doc marked esign_superseded", bool(b2["doc"].get("esign_superseded")), b2["doc"].get("esign_superseded"))
        v2 = await es.public_verify(s1["verification_code"])
        check("old QR reports superseded (verifies old artifact only)",
              v2.get("valid") and v2.get("version_status") == "superseded" and v2.get("doc_hash") == s1["doc_hash"], v2.get("version_status"))
        s2 = await sign(es, db, "invoice", so["id"], "ent_ksc", "Signer Versi 2")
        check("new version gets NEW verification code", s2["verification_code"] != s1["verification_code"],
              [s1["verification_code"], s2["verification_code"]])
        v1b = await es.public_verify(s1["verification_code"])
        check("old code not mixed with new signer", [x["name"] for x in v1b.get("signers", [])] == ["Signer Versi 1"], v1b.get("signers"))
        b3 = await pdf.build_document("invoice", so["id"], "ent_ksc")
        check("new PDF carries only new-version signature", (b3["doc"].get("esign") or {}).get("code") == s2["verification_code"]
              and "Signer Versi 1" not in (b3["doc"].get("esign") or {}).get("signers", ""), b3["doc"].get("esign"))
        snap = await db.document_signatures.find_one({"verification_code": s1["verification_code"]}, {"_id": 0, "doc_snapshot": 1})
        check("signed snapshot stored immutably with old content", "PENERIMA DIUBAH" not in (snap or {}).get("doc_snapshot", "PENERIMA DIUBAH"),
              bool((snap or {}).get("doc_snapshot")))
        h_a = (await pdf.build_document("invoice", so["id"], "ent_ksc"))["content_hash"]
        await asyncio.sleep(1.2)
        h_b = (await pdf.build_document("invoice", so["id"], "ent_ksc"))["content_hash"]
        check("content hash stable across prints (no print timestamp)", h_a == h_b, [h_a[:12], h_b[:12]])
    except Exception as exc:  # noqa: BLE001
        check("script error", False, repr(exc))
    finally:
        await db.sales_orders.delete_one({"id": so["id"]})
        await db.document_signatures.delete_many({"source_id": so["id"]})
        await db.esign_requests.delete_many({"source_id": so["id"]})


asyncio.run(main())
print(json.dumps(results, indent=1, ensure_ascii=False))
print(f"SUMMARY pass={sum(r['pass'] for r in results)} fail={sum(not r['pass'] for r in results)}")
sys.exit(0 if all(r["pass"] for r in results) else 1)
