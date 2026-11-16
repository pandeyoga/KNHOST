"""MP-T4b — hutang jasa makloon & hasil klaim (keputusan pemilik K-63, K-64, K-78…K-81, 16 Nov 2026).

Sakelar per PT `makloon.jasa_jadi_hutang`:
  * `saat_terima` (bawaan, cara lama): tagihan jasa langsung `posted` saat hasil diterima (Dr 1-1350 / Cr 2-1100),
    klaim potong bon/ganti rugi selalu ke Pendapatan Klaim 4-9200.
  * `saat_faktur`: tagihan jasa `awaiting_invoice` saat hasil diterima — Dr 1-1350 / Cr GR/IR 2-1150 (tanpa PPN); hutang
    lahir saat faktur mitra dicocokkan (Dr 2-1150 + Dr PPN 1-1500 / Cr 2-1100). Klaim dibagi menurut keadaan roll hasil
    langkahnya: masih di stok → Cr Persediaan 1-1300 (biaya roll turun), dikirim lagi ke mitra (WIP) → Cr 1-1350,
    sudah keluar/terjual/susut → Cr 4-9200.
Mode dipotret di tagihan (`ap_mode`) saat lahir, sehingga jurnal ulang tidak berubah walau sakelar PT diubah kemudian.
"""
from typing import Any, Dict, List

from core_utils import from_cents, now_iso, to_cents
from db import db

MODE_LAMA, MODE_FAKTUR = "saat_terima", "saat_faktur"
_OUT_STATUSES = frozenset({"in_transit_sales", "delivered", "returned_supplier", "in_transit_intercompany", "sold",
                           "consumed", "scrapped", "written_off"})


async def ap_mode(entity_id: str) -> str:
    from services.config_resolver import value_of
    v = await value_of("makloon.jasa_jadi_hutang", {"entity_id": entity_id or ""})
    return v if v in (MODE_LAMA, MODE_FAKTUR) else MODE_LAMA


def _treatment(roll: Dict[str, Any]) -> str:
    st = str(roll.get("status") or "")
    if st == "subcon":
        return "wip"
    if st in _OUT_STATUSES or float(roll.get("length_remaining") or 0) <= 0:
        return "keluar"
    return "persediaan"


async def claim_split(step: Dict[str, Any], amount: float) -> Dict[str, Any]:
    """Bagi nilai klaim ke roll hasil langkah (asli + potongannya) menurut panjang awal hasil.

    tarif = klaim ÷ Σ panjang awal roll hasil. Roll hidup: penurunan = nilai sekarang − sisa × (biaya − tarif), biaya
    tidak boleh di bawah 0. Sisa klaim (bagian yang sudah keluar, susut, pembulatan) = pendapatan klaim."""
    ids = [x.get("roll_id") for x in step.get("lots") or [] if x.get("roll_id")]
    originals = await db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0}).to_list(2000) if ids else []
    total_len = sum(float(r.get("length_initial") or r.get("length") or 0) for r in originals)
    amount_c = to_cents(amount)
    if total_len <= 0 or amount_c <= 0:
        return {"rate": 0.0, "inventory_amount": 0.0, "wip_amount": 0.0, "income_amount": from_cents(amount_c),
                "per_roll": []}
    rate = amount / total_len
    family = await db.inventory_rolls.find(
        {"$or": [{"id": {"$in": ids}}, {"root_roll_id": {"$in": ids}}, {"parent_roll_id": {"$in": ids}}]},
        {"_id": 0}).to_list(5000)
    sen = {"persediaan": 0, "wip": 0}
    per_roll: List[Dict[str, Any]] = []
    for r in family:
        golongan = _treatment(r)
        if golongan == "keluar":
            continue
        sisa = float(r.get("length_remaining") or 0)
        biaya = float(r.get("unit_cost") or r.get("base_unit_cost") or 0)
        turun_per = min(rate, biaya)
        turun = to_cents(sisa * biaya) - to_cents(sisa * (biaya - turun_per))
        if turun <= 0:
            continue
        sen[golongan] += turun
        per_roll.append({"roll_id": r["id"], "treatment": golongan, "per_unit": round(turun_per, 6),
                         "value": from_cents(turun)})
    income = amount_c - sen["persediaan"] - sen["wip"]
    if income < 0:   # pembulatan sen ke atas — kurangi dari porsi persediaan, jangan biarkan pendapatan negatif
        sen["persediaan"] += income
        income = 0
    return {"rate": round(rate, 6), "inventory_amount": from_cents(sen["persediaan"]),
            "wip_amount": from_cents(sen["wip"]), "income_amount": from_cents(income), "per_roll": per_roll}


async def apply_claim_to_rolls(ref: str, per_roll: List[Dict[str, Any]], *, actor: str, undo: bool = False) -> int:
    """Turunkan (atau, `undo`, kembalikan) biaya roll sebesar porsi klaimnya. Idempoten per `ref` (SPK:langkah)."""
    from services import roll_cost_history
    n = 0
    for a in per_roll:
        sign = 1 if undo else -1
        cond = {"id": a["roll_id"], "claim_refs": ref} if undo else {"id": a["roll_id"], "claim_refs": {"$ne": ref}}
        before = await db.inventory_rolls.find_one({"id": a["roll_id"]}, {"_id": 0})
        upd = {"$inc": {"unit_cost": sign * float(a["per_unit"]), "claim_value_total": -sign * float(a["value"])},
               "$set": {"updated_at": now_iso()}}
        upd["$pull" if undo else "$push"] = {"claim_refs": ref}
        res = await db.inventory_rolls.update_one(cond, upd)
        if before and res.modified_count:
            await roll_cost_history.record(before, float(before.get("unit_cost") or 0) + sign * float(a["per_unit"]),
                                           "makloon_claim" if not undo else "makloon_claim_undo", actor=actor,
                                           ref_type="makloon_claim", ref_id=ref, ref_number=ref)
        n += res.modified_count
    return n


async def match_invoice(mko_id: str, seq: int, data: Dict[str, Any], *, actor_name: str = "system") -> Dict[str, Any]:
    """MP-T4b (K-78) — cocokkan faktur mitra ke tagihan jasa langkah yang `awaiting_invoice`.

    Nilai jasa di faktur (tanpa PPN) WAJIB sama dengan nilai tagihan sesudah potongan klaim (toleransi Rp 1) —
    selisih diselesaikan dulu lewat tarif/klaim, bukan diserap diam-diam. Tagihan menjadi `posted` (masuk hutang,
    bisa dibayar); jurnal Dr GR/IR 2-1150 + Dr PPN Masukan 1-1500 / Cr Hutang 2-1100 lewat jalur posting durable."""
    from fastapi import HTTPException
    from services.book_date import periksa_periode_dokumen_409
    order = await db.makloon_orders.find_one({"id": mko_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order makloon tidak ditemukan")
    step = next((s for s in order.get("steps") or [] if int(s.get("seq") or 0) == int(seq)), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Langkah {seq} tidak ditemukan")
    bill = await db.vendor_bills.find_one({"id": step.get("service_bill_id") or "-"}, {"_id": 0})
    if not bill or bill.get("ap_mode") != MODE_FAKTUR:
        raise HTTPException(status_code=409, detail=f"Langkah {seq} tidak punya tagihan jasa yang menunggu faktur.")
    if bill.get("status") != "awaiting_invoice":
        raise HTTPException(status_code=409, detail=f"Tagihan {bill.get('bill_number')} sudah dicocokkan dengan faktur "
                                                    f"{bill.get('supplier_invoice_no') or ''}.".replace(" .", "."))
    inv_no = str(data.get("supplier_invoice_no") or "").strip()
    if not inv_no:
        raise HTTPException(status_code=400, detail="Isi nomor faktur mitra.")
    net, ppn = round(float(data.get("net_amount") or 0), 2), round(float(data.get("ppn_amount") or 0), 2)
    if ppn < 0:
        raise HTTPException(status_code=400, detail="PPN tidak boleh negatif.")
    expected = round(float(bill.get("net_amount") or 0), 2)
    if abs(net - expected) > 1.0:
        from core_utils import rupiah
        raise HTTPException(status_code=400, detail=(
            f"Nilai jasa di faktur {rupiah(net)} tidak sama dengan nilai yang diterima {rupiah(expected)} "
            f"(sesudah potongan klaim). Selesaikan selisihnya dulu — ubah tarif atau ajukan klaim."))
    entity_id = bill.get("entity_id") or order.get("entity_id") or ""
    await periksa_periode_dokumen_409(entity_id, data.get("invoice_date") or None, jenis="faktur jasa makloon")
    now = now_iso()
    patch = {"status": "posted", "supplier_invoice_no": inv_no, "invoice_date": data.get("invoice_date") or "",
             "ppn_amount": ppn, "grand_total": round(expected + ppn, 2), "invoice_matched_at": now,
             "invoice_matched_by": actor_name, "updated_at": now}
    # CAS: hanya pemenang yang memindah tagihan dari `awaiting_invoice`; SPK & jurnal sesudahnya idempoten.
    res = await db.vendor_bills.update_one({"id": bill["id"], "status": "awaiting_invoice"}, {"$set": patch})
    if not res.modified_count:
        raise HTTPException(status_code=409, detail="Tagihan berubah — muat ulang.")
    await db.makloon_orders.update_one(
        {"id": mko_id, "steps.seq": int(seq)},
        {"$set": {"steps.$.service_invoice_status": "cocok", "steps.$.supplier_invoice_no": inv_no, "updated_at": now},
         "$push": {"timeline": {"at": now, "event": "service_invoice_matched",
                                "note": f"Langkah {seq}: faktur {inv_no} dicocokkan ke {bill.get('bill_number')} "
                                        f"oleh {actor_name}"}}})
    from services import posting_registry as _preg
    order = await db.makloon_orders.find_one({"id": mko_id}, {"_id": 0})
    jr = await _preg.durable_makloon_step(order, int(seq))
    return {"bill_id": bill["id"], "status": "posted", "grand_total": round(expected + ppn, 2),
            "gl_status": jr.get("gl_status"), "gl_error": jr.get("gl_error")}
