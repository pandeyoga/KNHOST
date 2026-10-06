"""P17f — DESIGN-02: sample yang DISETUJUI (dimenangkan supplier barang) menjadi acuan QC yang tepat.

Usage: cd C:/Users/abc/Documents/Codex/2026-09-28/sya/work/KNHOST-data-audit-latest-2026-10-05/backend && python ../audit/iterations/2026-10-03-P17-planned-coverage/repro_p17f.py
Fixture: 3 md_samples (2 decided beda supplier + 1 dibatalkan lebih baru) → SPK inspeksi; semua dibuang.
"""
import asyncio
import json
import sys
import uuid

sys.path.insert(0, ".")
from dotenv import load_dotenv  # noqa: E402

load_dotenv(".env")
from poc_stock_guard import purge_new_ids, snapshot_new_ids  # noqa: E402

T = f"TEST_P17F_{uuid.uuid4().hex[:6]}"
ENT = "ent_ksc"
results = []


def check(fid, name, ok, detail=""):
    results.append({"id": fid, "invariant": name, "pass": bool(ok), "detail": str(detail)[:300]})


async def run(db):
    from services import inspection_service as ins
    pid = f"prod_{T.lower()}"
    mk = lambda n, sup, status, at: {  # noqa: E731
        "id": f"smp_{T.lower()}_{n}", "number": f"{T}/SMP-{n}", "entity_id": ENT, "product_id": pid, "spec_id": "",
        "status": status, "created_at": at, "color_target": {"name": f"Merah {n}", "code": f"R{n}"},
        "decision": ({"supplier_id": sup, "round_no": 2, "contract_id": f"sct_{n}", "result": "won"} if status == "decided" else {})}
    await db.md_samples.insert_many([mk("A", "sup_A", "decided", "2026-10-01T00:00:00+00:00"),
                                     mk("B", "sup_B", "decided", "2026-10-02T00:00:00+00:00"),
                                     mk("C", "sup_A", "cancelled", "2026-10-03T00:00:00+00:00")])
    a = await ins._baseline_for([pid], ENT, "sup_A")  # noqa: SLF001
    check("DESIGN-02", "barang supplier A diacu ke sample yang DIMENANGKAN A (bukan sample terbaru milik B)",
          a.get("baseline_sample_number") == f"{T}/SMP-A" and a.get("baseline_color") == "Merah A (RA)", a)
    check("DESIGN-02", "acuan membawa kontrak & round ACC pemenang", a.get("baseline_contract_id") == "sct_A" and a.get("baseline_round_no") == 2, a)
    b = await ins._baseline_for([pid], ENT, "sup_B")  # noqa: SLF001
    check("DESIGN-02", "barang supplier B → sample B", b.get("baseline_sample_number") == f"{T}/SMP-B", b)
    x = await ins._baseline_for([pid], ENT, "sup_X")  # noqa: SLF001
    check("DESIGN-02", "supplier tanpa sample sendiri → acuan standar terbaru yang disetujui (B), bukan yang dibatalkan",
          x.get("baseline_sample_number") == f"{T}/SMP-B", x)
    k = await ins._baseline_for([pid], "ent_kanda", "sup_A")  # noqa: SLF001
    check("DESIGN-02", "sample badan usaha lain tidak dipakai sebagai acuan", k == {}, k)
    doc = await ins._new_doc(kind=ins.KIND_PO_RECEIPT, entity_id=ENT, actor={"name": T}, supplier=("sup_A", "Supplier A"),  # noqa: SLF001
                             lines=[{"product_id": pid, "roll_id": "", "qty": 1}], remark=T)
    saved = await db.inspections.find_one({"id": doc["id"]}, {"_id": 0, "refs": 1}) or {}
    ref = any(r.get("doc_type") == "md_sample" and r.get("doc_id") == f"smp_{T.lower()}_A" for r in saved.get("refs") or [])
    check("DESIGN-02", "SPK inspeksi menyimpan acuan sample A + tautan dokumen 'references'",
          doc.get("baseline_sample_id") == f"smp_{T.lower()}_A" and bool(ref), (doc.get("baseline_sample_number"), bool(ref)))
    await db.md_samples.delete_many({"id": {"$regex": f"^smp_{T.lower()}"}})


async def main():
    from db import db
    ids = snapshot_new_ids(["inspections", "doc_refs", "audit_logs", "md_samples"])
    try:
        await run(db)
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        check("DESIGN-02", "eksekusi skenario", False, repr(exc)[:200])
    finally:
        purge_new_ids(ids, verbose=False)
    p = sum(r["pass"] for r in results)
    print(json.dumps(results, ensure_ascii=False, indent=1))
    print(f"pass={p} fail={len(results) - p}")


asyncio.run(main())
