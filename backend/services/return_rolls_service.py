"""L08 LN-080 — retur hanya dari barang yang BENAR-BENAR terkirim (roll per SJ) + batas kumulatif atomik per SO."""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Tuple

from pymongo.errors import DuplicateKeyError

from db import db
from core_utils import now_iso

EPS = 0.01
ACTIVE = ["draft", "pending_approval", "approved", "inspecting", "inspected",
          "refund_settled", "credit_settled", "nego_settled"]
LOCK_TTL_S = 60


@asynccontextmanager
async def order_lock(order_id: str):
    """Kunci per SO: dua klaim retur paralel tidak bisa sama-sama lolos cek batas."""
    stale = (datetime.now(timezone.utc) - timedelta(seconds=LOCK_TTL_S)).isoformat()
    await db.return_create_locks.delete_one({"_id": order_id, "at": {"$lt": stale}})
    try:
        await db.return_create_locks.insert_one({"_id": order_id, "at": now_iso()})
    except DuplicateKeyError:
        raise ValueError("Retur lain untuk pesanan ini sedang disimpan — coba lagi sebentar.")
    try:
        yield
    finally:
        await db.return_create_locks.delete_one({"_id": order_id})


def _roll_claims(item: Dict[str, Any], shipped_len: Dict[str, float]) -> Dict[str, float]:
    qtys = item.get("roll_qtys") or {}
    return {rid: float(qtys.get(rid) if qtys.get(rid) is not None else shipped_len.get(rid, 0)) for rid in item.get("roll_ids") or []}


async def returnable(order_id: str, exclude_id: str = "") -> Dict[str, Any]:
    ships = await db.shipments.find({"order_id": order_id, "status": {"$ne": "cancelled"}}, {"_id": 0}).to_list(500)
    pids = list({s["product_id"] for s in ships})
    prods = {p["id"]: p async for p in db.products.find({"id": {"$in": pids}},
                                                       {"_id": 0, "id": 1, "name": 1, "sku": 1, "color": 1, "base_unit": 1})}
    rows: List[Dict[str, Any]] = []
    for s in ships:
        for r in s.get("rolls") or []:
            rows.append({"roll_id": r["roll_id"], "shipment_id": s["id"], "shipment_no": s.get("shipment_no", ""),
                         "product_id": s["product_id"], "lot": r.get("lot", ""),
                         # Trial 22 Okt (D8) — panjang roll = SATUAN DASAR produk; dulu label jatuh ke satuan SJ (= satuan
                         # baris SO pada data lama) → "Qty aktual per roll (meter)" padahal angkanya yard.
                         "shipped_qty": round(float(r.get("length") or 0), 2),
                         "unit": (prods.get(s["product_id"]) or {}).get("base_unit") or r.get("unit") or s.get("unit")})
    rnos = {x["id"]: x.get("roll_no", "") async for x in db.inventory_rolls.find(
        {"id": {"$in": [r["roll_id"] for r in rows]}}, {"_id": 0, "id": 1, "roll_no": 1})}
    shipped_len = {r["roll_id"]: r["shipped_qty"] for r in rows}
    roll_ret: Dict[str, float] = {}
    prod_ret: Dict[str, float] = {}
    async for rt in db.sales_returns.find({"order_id": order_id, "status": {"$in": ACTIVE}}, {"_id": 0, "id": 1, "items": 1}):
        if rt["id"] == exclude_id:
            continue
        for it in rt.get("items") or []:
            prod_ret[it.get("product_id")] = prod_ret.get(it.get("product_id"), 0) + float(it.get("quantity_returned") or 0)
            for rid, q in _roll_claims(it, shipped_len).items():
                roll_ret[rid] = roll_ret.get(rid, 0) + q
    for r in rows:
        p = prods.get(r["product_id"]) or {}
        r.update({"roll_no": rnos.get(r["roll_id"], ""), "product_name": p.get("name", ""), "sku": p.get("sku", ""),
                  "color": p.get("color", ""), "returned_qty": round(roll_ret.get(r["roll_id"], 0), 2)})
        r["remaining"] = round(max(r["shipped_qty"] - r["returned_qty"], 0), 2)
    by_product: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        b = by_product.setdefault(r["product_id"], {"product_id": r["product_id"], "product_name": r["product_name"],
                                                    "sku": r["sku"], "color": r["color"], "unit": r["unit"],
                                                    "shipped_qty": 0.0, "roll_count": 0})
        b["shipped_qty"] = round(b["shipped_qty"] + r["shipped_qty"], 2)
        b["roll_count"] += 1
    for b in by_product.values():
        b["returned_qty"] = round(prod_ret.get(b["product_id"], 0), 2)
        b["remaining"] = round(max(b["shipped_qty"] - b["returned_qty"], 0), 2)
    return {"order_id": order_id, "rolls": rows, "products": list(by_product.values()),
            "note": "Hanya barang yang sudah keluar lewat Surat Jalan yang bisa diretur."}


async def assert_shipped_items(order_id: str, items: List[Dict[str, Any]]) -> None:
    """Produk/roll harus berasal dari SJ SO ini; qty (kumulatif dgn retur aktif lain) ≤ terkirim."""
    data = await returnable(order_id)
    prods = {p["product_id"]: p for p in data["products"]}
    rolls = {r["roll_id"]: r for r in data["rolls"]}
    if not prods:
        raise ValueError("Pesanan ini belum punya barang terkirim (Surat Jalan) — retur belum bisa dibuat.")
    want: Dict[str, float] = {}
    per_roll: Dict[str, float] = {}
    for it in items:
        pid = it.get("product_id")
        if pid not in prods:
            raise ValueError(f"Produk '{it.get('product_name') or pid}' tidak ada di Surat Jalan pesanan ini.")
        qty = float(it.get("quantity_returned") or 0)
        want[pid] = want.get(pid, 0) + qty
        rids = list(dict.fromkeys(it.get("roll_ids") or []))
        for rid in rids:
            r = rolls.get(rid)
            if not r or r["product_id"] != pid:
                raise ValueError(f"Roll {rid} bukan roll terkirim untuk produk ini di pesanan ini.")
        if not rids:
            continue
        given = it.get("roll_qtys") or {}
        if given:
            claims = {rid: float(given.get(rid) or 0) for rid in rids}
        else:   # qty dibagi ke roll terpilih sesuai sisa masing-masing (bukan panjang kirim penuh)
            claims, left = {}, qty
            for rid in rids:
                take = round(min(left, max(rolls[rid]["remaining"] - per_roll.get(rid, 0), 0)), 2)
                claims[rid], left = take, round(left - take, 2)
        if abs(sum(claims.values()) - qty) > EPS:
            raise ValueError(f"Qty retur {qty:g} tidak sama dengan jumlah klaim per roll {sum(claims.values()):g}.")
        it["roll_ids"], it["roll_qtys"] = rids, claims
        for rid, q in claims.items():
            per_roll[rid] = per_roll.get(rid, 0) + q
    for rid, q in per_roll.items():
        if q <= 0 or q > rolls[rid]["remaining"] + EPS:
            raise ValueError(f"Roll {rolls[rid]['roll_no'] or rid}: klaim {q:g} melebihi sisa yang bisa diretur "
                             f"{rolls[rid]['remaining']:g} {rolls[rid]['unit']}.")
    for pid, q in want.items():
        if q > prods[pid]["remaining"] + EPS:
            p = prods[pid]
            raise ValueError(f"Retur melebihi batas untuk '{p['product_name']}': diminta {q:g}, sudah diretur "
                             f"{p['returned_qty']:g}, terkirim {p['shipped_qty']:g} {p['unit']}.")



# ─── Detail & keputusan PER ROLL (permintaan pemilik 23 Okt) ───────────────────────────────────────────────
# Alasan, kondisi, checklist (hangtag hilang / sudah dipotong pelanggan) & foto dicatat PER ROLL — satu SKU bisa
# punya roll yang dipotong dan yang utuh. Pemegang izin `sales_return.decide_rolls` (bawaan Manajer & Admin Sales,
# dapat diatur di matriks akses) boleh menolak roll tertentu (mis. yang sudah dipotong) dan menerima sisanya.
ROLL_FLAGS = ("hangtag_missing", "cut_by_customer")


def normalize_roll_details(item: Dict[str, Any], summarize_reason: bool = True,
                           default_condition: str = "ok") -> None:
    """Rapikan `roll_details` baris retur (hanya roll yang diklaim) + ringkasan baris (kondisi & alasan).

    `summarize_reason=False` untuk retur supplier: `reason` baris di sana adalah KODE (cacat/salah_kirim/…),
    bukan kalimat — tidak boleh ditimpa gabungan alasan roll. `default_condition` dipakai bila roll tidak
    dikirim detailnya sama sekali (retur supplier lama: kondisi baris)."""
    raw = item.get("roll_details") or {}
    out: Dict[str, Dict[str, Any]] = {}
    for rid in list(item.get("roll_ids") or []):
        d = raw.get(rid) or {}
        cond = d.get("condition") or default_condition
        out[rid] = {"reason": str(d.get("reason") or "").strip()[:300],
                    "condition": "damaged" if cond == "damaged" else "ok",
                    "hangtag_missing": bool(d.get("hangtag_missing")), "cut_by_customer": bool(d.get("cut_by_customer")),
                    "note": str(d.get("note") or "").strip()[:300], "decision": "", "decision_reason": ""}
    item["roll_details"] = out
    if out and raw:
        item["condition"] = "damaged" if any(v["condition"] == "damaged" for v in out.values()) else "ok"
        if summarize_reason and not str(item.get("reason") or "").strip():
            item["reason"] = "; ".join(dict.fromkeys(v["reason"] for v in out.values() if v["reason"]))


def condition_flags_of(items: List[Dict[str, Any]], base: Dict[str, Any]) -> Dict[str, bool]:
    """Checklist kondisi tingkat dokumen = checklist kepala ATAU salah satu roll yang masih diklaim."""
    out = {k: bool((base or {}).get(k)) for k in (*ROLL_FLAGS, "replacement_proof")}
    for it in items:
        for rid, d in (it.get("roll_details") or {}).items():
            if rid in (it.get("roll_ids") or []):
                for k in ROLL_FLAGS:
                    out[k] = out[k] or bool(d.get(k))
    return out


async def prepare_roll_decisions(items: List[Dict[str, Any]], decisions: List[Dict[str, Any]],
                                 what: str = "retur") -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    """Validasi keputusan (roll harus termasuk klaim) + nomor roll untuk pesan & jejak."""
    want = {str(d.get("roll_id")): d for d in decisions or [] if d.get("roll_id")}
    if not want:
        raise ValueError("Tidak ada keputusan roll yang dikirim.")
    known = {rid for it in items for rid in (it.get("roll_ids") or [])}
    unknown = [rid for rid in want if rid not in known]
    if unknown:
        raise ValueError(f"Roll tidak termasuk klaim {what} ini (atau sudah ditolak): " + ", ".join(unknown))
    nos = {r["id"]: r.get("roll_no") or r["id"] async for r in db.inventory_rolls.find(
        {"id": {"$in": list(want)}}, {"_id": 0, "id": 1, "roll_no": 1})}
    return want, nos


def apply_roll_decisions(items: List[Dict[str, Any]], want: Dict[str, Dict[str, Any]], nos: Dict[str, str],
                         who: str, now: str, qty_key: str = "quantity_returned",
                         summarize_reason: bool = True) -> List[Dict[str, Any]]:
    """Terapkan Terima/Tolak per roll pada `items` (diubah di tempat). Roll DITOLAK keluar dari baris: roll_ids,
    roll_qtys, `rolls` (meta retur supplier) & qty baris; jejaknya di `rejected_rolls`. Return: log keputusan.

    Qty baris sesudah tolak = min(qty lama, total qty roll yang tersisa) bila semua qty roll diketahui — retur supplier
    boleh mengambil SEBAGIAN dari roll terpilih, jadi qty baris tidak selalu sama dengan jumlah panjang roll."""
    log: List[Dict[str, Any]] = []
    for it in items:
        details = dict(it.get("roll_details") or {})
        for rid in list(it.get("roll_ids") or []):
            d = want.get(rid)
            if not d:
                continue
            dec = str(d.get("decision") or "").strip().lower()
            reason = str(d.get("reason") or "").strip()
            info = dict(details.get(rid) or {})
            if dec == "accept":
                info.update(decision="accept", decision_reason=reason, decided_by=who, decided_at=now)
            elif dec == "reject":
                if len(reason) < 5:
                    raise ValueError(f"Alasan tolak roll {nos.get(rid, rid)} wajib diisi (min. 5 huruf).")
                qtys = it.get("roll_qtys") or {}
                qty = float(qtys.get(rid) or 0)
                it["roll_ids"] = [x for x in it["roll_ids"] if x != rid]
                it["roll_qtys"] = {k: v for k, v in qtys.items() if k != rid}
                if it.get("rolls"):
                    it["rolls"] = [r for r in it["rolls"] if r.get("roll_id") != rid]
                    it["lots"] = sorted({r.get("lot") for r in it["rolls"] if r.get("lot")})
                left = round(max(float(it.get(qty_key) or 0) - qty, 0.0), 2)
                if it["roll_ids"] and all(r in it["roll_qtys"] for r in it["roll_ids"]):
                    left = round(min(float(it.get(qty_key) or 0),
                                     sum(float(it["roll_qtys"][r] or 0) for r in it["roll_ids"])), 2)
                it[qty_key] = left if it["roll_ids"] else 0.0
                for k in ("quantity_returned_input", "quantity_input", "unit_input"):
                    it.pop(k, None)
                it["qty_rolls"] = len(it["roll_ids"]) or None
                it.setdefault("rejected_rolls", []).append({"roll_id": rid, "roll_no": nos.get(rid, rid), "qty": qty,
                                                           "unit": it.get("unit", ""), "reason": reason, "by": who,
                                                           "at": now})
                info.update(decision="reject", decision_reason=reason, decided_by=who, decided_at=now)
            else:
                raise ValueError(f"Keputusan roll {nos.get(rid, rid)} harus 'accept' atau 'reject'.")
            details[rid] = info
            log.append({"roll_id": rid, "roll_no": nos.get(rid, rid), "decision": dec, "reason": reason})
        it["roll_details"] = details
        kept = [details[r] for r in it.get("roll_ids") or [] if r in details]
        if kept and any(v.get("reason") or v.get("decision") for v in kept):   # ringkasan = roll yang masih diklaim
            it["condition"] = "damaged" if any(v.get("condition") == "damaged" for v in kept) else "ok"
            if summarize_reason and all(v.get("reason") for v in kept):
                it["reason"] = "; ".join(dict.fromkeys(v["reason"] for v in kept))
    return log


def rejected_summary(log: List[Dict[str, Any]]) -> str:
    return "; ".join(f"{x['roll_no']} — {x['reason']}" for x in log if x["decision"] == "reject")


def decision_log_entry(prev: List[Dict[str, Any]], actor: Dict[str, Any], now: str,
                       log: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return list(prev or []) + [{"by": actor.get("name", ""), "role": actor.get("role", ""), "at": now, "rolls": log}]


async def decide_rolls(ret: Dict[str, Any], decisions: List[Dict[str, Any]], actor: Dict[str, Any]) -> Dict[str, Any]:
    """RETUR PELANGGAN — terima / tolak roll klaim. Roll DITOLAK keluar dari retur (tetap milik pelanggan): tidak
    discan, tidak di-QC, tidak dihitung uang; klaim rollnya kembali bebas. Semua roll ditolak → retur ditolak."""
    from services import return_state as st
    if ret.get("status") not in ("draft", "pending_approval"):
        raise ValueError("Keputusan per roll hanya sebelum retur disetujui (draf / menunggu persetujuan).")
    items = [dict(it) for it in ret.get("items") or []]
    want, nos = await prepare_roll_decisions(items, decisions)
    now, who = now_iso(), actor.get("name", "")
    log = apply_roll_decisions(items, want, nos, who, now)
    for it in items:
        if it.get("rejected_rolls") and not it.get("roll_ids") and float(it.get("quantity_returned") or 0) <= 0:
            it["settle_outcome"] = "reject"
    base = {"replacement_proof": (ret.get("condition_flags") or {}).get("replacement_proof")}
    upd: Dict[str, Any] = {"items": items, "updated_at": now, "condition_flags": condition_flags_of(items, base),
                           "roll_decision_log": decision_log_entry(ret.get("roll_decision_log"), actor, now, log)}
    if not any(float(it.get("quantity_returned") or 0) > 0 for it in items):
        st.assert_transition(ret["status"], st.REJECTED)
        upd.update({"status": st.REJECTED, "rejected_by": who, "rejected_at": now,
                    "reject_reason": f"Semua roll klaim ditolak: {rejected_summary(log)}"})
    res = await db.sales_returns.update_one({"id": ret["id"], "status": ret["status"]}, {"$set": upd})
    if not res.matched_count:
        raise ValueError("Retur baru saja berubah oleh pengguna lain — muat ulang lalu ulangi keputusan.")
    return await db.sales_returns.find_one({"id": ret["id"]}, {"_id": 0})
