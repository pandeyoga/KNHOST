"""Issue bahan makloon PER ROLL — kasus klien "20 roll Esmica Blue dikirim untuk dicelup hitam".

Dulu `makloon_order_service.issue_step` hanya mengenal JUMLAH: `stock_bucket_service.issue_to_subcon` memilih roll
sendiri (FEFO + belah roll). Roll yang dimuat ke truk bisa berbeda dengan roll yang dicatat keluar sistem — roll
fisik di truk masih `available` (gate OUT merah "tanpa dokumen"), sementara roll lain yang masih di rak tercatat
"di makloon". Modul ini memberi jalur kedua yang memakai roll TERTENTU:

  * `resolve_codes` — kode pindai/tempel (nomor roll, EPC tag RFID, atau id roll) → roll. Urutan pencocokan sama
    dengan `GET /rfid/lookup` (EPC kanonik dulu, lalu nomor roll / id).
  * `block_reason` — SATU aturan kelayakan, dipakai DUA permukaan: daftar pilihan di pop-up Issue
    (`issue_candidates`) dan validasi server (`pick_rolls`). Kalau keduanya menghitung sendiri, layar akan menawarkan
    roll yang lalu ditolak server.
  * `apply_issue_qty` — qty yang benar-benar dikirim ≠ rencana → estimasi hasil langkah ikut diskalakan (aturan
    P05 ACC-34 yang sebelumnya hanya ada di jalur konversi satuan dokumen) + catatan penyimpangan.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db

EPS = 0.005
MAX_PICK = 500
STATUS_LABEL = {
    "available": "Tersedia", "quarantine": "Karantina QC", "blocked": "Ditahan", "hold": "Ditahan (pesanan)",
    "reserved": "Dipesan", "committed": "Dikomit pesanan", "picked": "Sudah diambil", "packed": "Sudah dikemas",
    "wip": "Dalam proses/perbaikan", "subcon": "Di mitra makloon", "damaged": "Rusak", "consumed": "Terpakai",
    "delivered": "Terkirim", "receiving": "Sedang diterima",
}


def _tag(roll: Dict[str, Any]) -> str:
    return str(roll.get("roll_no") or roll.get("id") or "?")


def _holder(roll: Dict[str, Any]) -> str:
    """Dokumen lain yang memegang roll ini ('' = bebas)."""
    for key in ("reserved_ref", "earmarked_for", "committed_to"):
        ref = roll.get(key)
        if isinstance(ref, dict) and (ref.get("id") or ref.get("number")):
            return f"{ref.get('type') or key} {ref.get('number') or ref.get('id')}".strip()
        if isinstance(ref, str) and ref.strip():
            return ref.strip()
    return ""


def block_reason(roll: Dict[str, Any], *, product_id: str, warehouse_id: str,
                 owner_entity_id: str) -> Optional[Tuple[int, str]]:
    """(kode HTTP, alasan) bila roll TIDAK boleh dikirim ke mitra pada langkah ini; None = boleh.

    400 = roll salah alamat (produk/pemilik/gudang/habis) — memilihnya adalah kekeliruan input.
    409 = roll benar tetapi SEDANG dipegang keadaan lain (karantina, ditahan, dipesan, perpindahan, perbaikan).
    """
    tag = _tag(roll)
    if roll.get("product_id") != product_id:
        return 400, f"Roll {tag} bukan bahan langkah ini (produk lain) — pindai roll bahan yang benar."
    if roll.get("owner_entity_id") != owner_entity_id:
        return 400, f"Roll {tag} milik badan usaha lain — tidak bisa dikirim atas order ini."
    if roll.get("warehouse_id") != warehouse_id:
        return 400, f"Roll {tag} tercatat di gudang lain, bukan gudang sumber yang dipilih."
    if float(roll.get("length_remaining") or 0) <= EPS:
        return 400, f"Roll {tag} sudah habis (panjang tersisa 0)."
    st = str(roll.get("status") or "")
    if st != "available":
        if st in ("quarantine", "blocked"):
            return 409, (f"Roll {tag} sedang {STATUS_LABEL.get(st, st)} — lepas karantina/tahanan QC dulu "
                         "sebelum dikirim ke makloon.")
        return 409, (f"Roll {tag} berstatus {STATUS_LABEL.get(st, st)} — hanya roll Tersedia yang bisa "
                     "dikirim ke makloon.")
    if ((roll.get("inspection") or {}).get("hold") or {}).get("held") or roll.get("qc_hold_pending"):
        return 409, f"Roll {tag} DITAHAN hasil inspeksi QC — putuskan/lepas tahanannya dulu."
    holder = _holder(roll)
    if holder or float(roll.get("length_reserved") or 0) > EPS:
        return 409, (f"Roll {tag} sudah dicadangkan dokumen lain ({holder or 'reservasi potong'}) — "
                     "lepas cadangannya dulu atau pilih roll lain.")
    if (roll.get("active_movement") or {}).get("id"):
        am = roll["active_movement"]
        return 409, f"Roll {tag} sedang dalam perpindahan {am.get('number') or am.get('id')} — tunggu selesai."
    if roll.get("repair_open"):
        return 409, f"Roll {tag} masih tercatat di dokumen perbaikan yang berjalan."
    return None


async def resolve_codes(codes: List[str]) -> Tuple[List[str], List[str]]:
    """Kode pindai → (id roll, kode tak dikenal). EPC dinormalkan (separator/huruf kecil diterima)."""
    from services.epc import try_canonical
    ids: List[str] = []
    unknown: List[str] = []
    for raw in codes:
        code = str(raw or "").strip()
        if not code:
            continue
        tag = await db.rfid_tags.find_one({"epc": try_canonical(code) or code.upper()}, {"_id": 0, "roll_id": 1})
        rid = (tag or {}).get("roll_id")
        if not rid:
            row = await db.inventory_rolls.find_one({"$or": [{"roll_no": code}, {"id": code}]}, {"_id": 0, "id": 1})
            rid = (row or {}).get("id")
        if rid:
            ids.append(rid)
        else:
            unknown.append(code)
    return ids, unknown


async def pick_rolls(order: Dict[str, Any], step: Dict[str, Any], warehouse_id: str, *,
                     roll_ids: Optional[List[str]] = None,
                     roll_codes: Optional[List[str]] = None) -> Dict[str, Any]:
    """Validasi roll pilihan untuk issue langkah `step` → {rolls, qty, unit}. Satu roll gagal → seluruh issue ditolak
    dengan pesan yang MENYEBUT nomor rollnya (tidak ada issue sebagian diam-diam)."""
    ids = [str(x).strip() for x in (roll_ids or []) if str(x or "").strip()]
    if roll_codes:
        found, unknown = await resolve_codes(list(roll_codes))
        if unknown:
            raise HTTPException(status_code=400, detail=(
                f"Kode {', '.join(unknown[:5])}{' …' if len(unknown) > 5 else ''} tidak dikenal — bukan nomor roll "
                "maupun EPC tag yang terdaftar."))
        ids += found
    ids = list(dict.fromkeys(ids))
    if not ids:
        raise HTTPException(status_code=400, detail="Pilih atau pindai minimal satu roll bahan.")
    if len(ids) > MAX_PICK:
        raise HTTPException(status_code=400, detail=f"Maksimal {MAX_PICK} roll per issue.")
    rows = {r["id"]: r async for r in db.inventory_rolls.find({"id": {"$in": ids}}, {"_id": 0})}
    missing = [i for i in ids if i not in rows]
    if missing:
        raise HTTPException(status_code=400, detail=f"Roll {', '.join(missing[:5])} tidak ditemukan.")
    rolls = [rows[i] for i in ids]
    for r in rolls:
        bad = block_reason(r, product_id=step["input_product_id"], warehouse_id=warehouse_id,
                           owner_entity_id=order["entity_id"])
        if bad:
            raise HTTPException(status_code=bad[0], detail=bad[1])
    units = {str(r.get("unit") or "") for r in rolls}
    if len(units) > 1:
        raise HTTPException(status_code=400, detail=(
            f"Roll terpilih bersatuan campuran ({', '.join(sorted(u or '—' for u in units))}) — satu issue memakai "
            "satu satuan dasar produk."))
    qty = round(sum(float(r.get("length_remaining") or 0) for r in rolls), 2)
    return {"rolls": rolls, "qty": qty, "unit": units.pop() if units else ""}


def apply_issue_qty(step: Dict[str, Any], qty: float) -> Optional[Dict[str, Any]]:
    """Qty dikirim ≠ rencana langkah → skala estimasi hasil (P05 ACC-34) + kembalikan catatan penyimpangannya.

    Tanpa skala ini hasil wajar dari bahan yang dikirim terbaca "kurang dari estimasi" dan membuka klaim palsu."""
    old = float(step.get("input_qty") or 0)
    qty = round(float(qty), 3)
    dev = None
    if old > 0 and abs(old - qty) > 0.0005:
        ratio = qty / old
        for k in ("expected_output_qty", "expected_byproduct_qty"):
            if step.get(k) is not None:
                step[k] = round(float(step.get(k) or 0) * ratio, 3)
        diff = round(qty - old, 3)
        dev = {"planned_qty": round(old, 3), "issued_qty": qty, "diff": diff,
               "diff_pct": round(diff / old * 100, 2), "unit": step.get("input_unit") or ""}
    step["input_qty"] = qty
    return dev


async def issue_candidates(order: Dict[str, Any], step: Dict[str, Any], warehouse_id: str,
                           limit: int = 300) -> Dict[str, Any]:
    """Pop-up Issue mode "Pilih roll": roll bahan di gudang sumber milik entitas order — yang boleh dipilih
    (`rolls`) dan yang TERLIHAT tetapi tertahan beserta alasannya (`blocked`), supaya hasil pindai roll tertahan
    dijelaskan, bukan sekadar "tidak ditemukan"."""
    q = {"product_id": step.get("input_product_id"), "warehouse_id": warehouse_id,
         "owner_entity_id": order.get("entity_id"), "length_remaining": {"$gt": EPS},
         "status": {"$nin": ["consumed", "delivered", "returned_supplier", "subcon"]}}
    rows = await db.inventory_rolls.find(q, {"_id": 0}).sort([("received_date", 1), ("created_at", 1)]).to_list(limit)
    tag_ids = [r["rfid_tag_id"] for r in rows if r.get("rfid_tag_id")]
    from services.rfid_service import LIVE_TAG_STATUSES
    epc = {t["id"]: t.get("epc", "") async for t in db.rfid_tags.find(
        {"id": {"$in": tag_ids}, "status": {"$in": list(LIVE_TAG_STATUSES)}}, {"_id": 0, "id": 1, "epc": 1})}
    ok: List[Dict[str, Any]] = []
    blocked: List[Dict[str, Any]] = []
    for r in rows:
        item = {"id": r["id"], "roll_no": r.get("roll_no", ""), "lot": r.get("lot", ""),
                "dye_lot": r.get("dye_lot", ""), "grade": r.get("grade", ""),
                "length_remaining": round(float(r.get("length_remaining") or 0), 2), "unit": r.get("unit", ""),
                "epc": epc.get(r.get("rfid_tag_id") or "", ""), "status": r.get("status", "")}
        bad = block_reason(r, product_id=step.get("input_product_id"), warehouse_id=warehouse_id,
                           owner_entity_id=order.get("entity_id"))
        if bad:
            blocked.append({**item, "reason": bad[1]})
        else:
            ok.append(item)
    return {"seq": int(step.get("seq") or 0), "warehouse_id": warehouse_id, "unit": step.get("input_unit") or "",
            "planned_qty": float(step.get("input_qty") or 0), "rolls": ok, "blocked": blocked,
            "total_qty": round(sum(x["length_remaining"] for x in ok), 2)}


async def candidates_for(mko_id: str, seq: int, warehouse_id: str = "") -> Dict[str, Any]:
    """`GET /makloon-orders/{id}/steps/{seq}/issue-rolls` — gudang kosong = gudang sumber order."""
    order = await db.makloon_orders.find_one({"id": mko_id}, {"_id": 0, "id": 1, "entity_id": 1, "steps": 1,
                                                              "from_warehouse_id": 1})
    if not order:
        raise HTTPException(status_code=404, detail="Order makloon tidak ditemukan")
    step = next((s for s in order.get("steps") or [] if int(s.get("seq") or 0) == int(seq)), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {seq} tidak ada pada order")
    wh = warehouse_id or step.get("from_warehouse_id") or order.get("from_warehouse_id") or ""
    if not wh:
        raise HTTPException(status_code=400, detail="Pilih gudang sumber bahan dulu.")
    return await issue_candidates(order, step, wh)
