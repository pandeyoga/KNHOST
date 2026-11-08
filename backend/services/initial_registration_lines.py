"""PREP-B — baris pendaftaran di lapangan (HP/handheld): EPC → produk → panjang → simpan & lanjut.

Satu baris = satu roll fisik + tag yang AKAN lahir saat disetujui. Aturan:
  · EPC kanonik (`services.epc`), unik terhadap tag hidup (`rfid_tags`) DAN baris hidup sesi mana pun. K-OPN-05 masih
    terbuka → per sesi: `read` (EPC bawaan tag dibaca) atau `system` (EPC dibuat sistem, tag ditandai
    `pending_write` sampai dikonfirmasi tertulis). EPC milik tag hidup ROLL LAMA di cakupan = roll lama itu (dipakai ulang).
  · Produk aktif & tidak tergantikan (baca defensif `superseded_by` — paket A); tergantikan → diarahkan ke penggantinya.
    Produk tanpa satuan dasar ditolak (penjaga satuan P18). "Produk belum dikenali" boleh disimpan dengan keterangan
    (+ foto) — tidak bisa disetujui sebelum dipetakan.
  · Panjang + satuan → satuan dasar produk; `length_verified` = dari label (K-OPN-04), selain itu "panjang belum
    terverifikasi" dan ikut ke roll.
  · Bin wajib di cakupan sesi; PT pemilik dalam akses pengguna; nomor roll lama opsional (dicocokkan ke roll lama).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso, safe_doc
from db import db
from services import initial_registration_plan as plan_svc
from services.epc import display_epc, try_canonical

LINES = "initial_registration_lines"   # sama dengan initial_registration_plan.LINES
LIVE_TAG = ("active", "pending_print")
EDITABLE = ("epc", "product_id", "qty", "unit", "length_from_label", "lot", "dye_lot", "grade", "owner_entity_id",
            "bin_id", "old_roll_no", "note", "unrecognized", "label_raw")


def split_codes(raw: Any) -> List[str]:
    """Tempel banyak kode (handheld mengetik seperti keyboard): pisah baris/spasi/koma/titik koma."""
    items = raw if isinstance(raw, list) else re.split(r"[\s,;]+", str(raw or ""))
    out: List[str] = []
    for x in items:
        s = str(x or "").strip()
        if s and s not in out:
            out.append(s)
    return out[:500]


def in_scope(session: Dict[str, Any], roll: Optional[Dict[str, Any]]) -> bool:
    """Predikat SAMA dengan `plan_svc.expected_rolls` untuk satu roll."""
    from services.roll_service import PHYSICAL_ROLL_STATUSES
    reg = session.get("registration") or {}
    if not roll or roll.get("warehouse_id") != session["warehouse_id"] or roll.get("status") not in PHYSICAL_ROLL_STATUSES:
        return False
    if float(roll.get("length_remaining") or 0) <= 0 or (roll.get("registration") or {}).get("session_id") == session["id"]:
        return False
    if reg.get("started_at") and roll.get("created_at") and roll["created_at"] >= reg["started_at"]:
        return False
    return bool(reg.get("full_scope")) or roll.get("bin_id") in set(reg.get("bin_ids") or [])


async def epc_status(session: Dict[str, Any], epc: str, line_id: str = "") -> Dict[str, Any]:
    """{ok, epc, message, matched_roll}: tag hidup roll lama di cakupan = cocok; tag hidup lain / baris lain = bentrok."""
    out: Dict[str, Any] = {"epc": epc, "epc_display": display_epc(epc), "ok": True, "message": "", "matched_roll": None}
    tag = await db.rfid_tags.find_one({"epc": epc, "status": {"$in": list(LIVE_TAG)}}, {"_id": 0, "id": 1, "roll_id": 1})
    if tag:
        roll = await db.inventory_rolls.find_one({"id": tag.get("roll_id")}, {**plan_svc.OLD_FIELDS, "registration": 1})
        if in_scope(session, roll):
            out["matched_roll"] = {k: roll.get(k) for k in ("id", "roll_no", "product_id", "owner_entity_id", "bin_code",
                                                              "length_remaining", "unit")}
            out["message"] = f"Tag lama roll {roll.get('roll_no')} — roll lama dipakai ulang bila produk & PT sama."
        else:
            where = f"roll {(roll or {}).get('roll_no') or tag.get('roll_id')}"
            out.update(ok=False, message=(f"EPC {display_epc(epc)} sudah dipakai tag aktif {where} di luar cakupan sesi ini "
                                          "— kemungkinan EPC tag tidak unik (K-OPN-05). Pakai tag lain / tulis ulang EPC."))
            return out
    other = await db[LINES].find_one({"epc": epc, "live": True, "id": {"$ne": line_id}},
                                     {"_id": 0, "session_id": 1, "bin_code": 1})
    if other:
        same = other["session_id"] == session["id"]
        out.update(ok=False, message=(f"EPC {display_epc(epc)} sudah didaftarkan di baris lain "
                                      f"({'sesi ini' if same else 'sesi lain'}, bin {other.get('bin_code') or '-'})."))
    return out


async def check_epcs(session: Dict[str, Any], raw: Any) -> List[Dict[str, Any]]:
    rows = []
    for code in split_codes(raw):
        epc = try_canonical(code)
        if not epc:
            rows.append({"raw": code, "ok": False, "message": "EPC tidak valid: wajib 24 karakter hex (0-9, A-F)."})
            continue
        rows.append({"raw": code, **await epc_status(session, epc)})
    return rows


async def _new_system_epc(session: Dict[str, Any]) -> str:
    from services.rfid_service import generate_epc
    for _ in range(8):
        epc = generate_epc()
        if (await epc_status(session, epc))["ok"]:
            return epc
    raise HTTPException(status_code=503, detail="Gagal membuat EPC unik — coba simpan lagi.")


def _superseded_ref(p: Dict[str, Any]) -> str:
    ref = p.get("superseded_by")
    if isinstance(ref, dict):
        ref = ref.get("id") or ref.get("product_id") or ref.get("sku")
    return str(ref or "").strip()


async def resolve_product(product_id: str) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Produk aktif + bersatuan dasar. Tergantikan (paket A `superseded_by`) → ikuti ke pengganti (≤5 langkah)."""
    from services.makloon_receipt_qc import require_unit
    p = await db.products.find_one({"id": product_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")
    first, hops = p, 0
    while _superseded_ref(p) and hops < 5:
        ref = _superseded_ref(p)
        nxt = await db.products.find_one({"$or": [{"id": ref}, {"sku": ref}]}, {"_id": 0})
        if not nxt:
            raise HTTPException(status_code=409, detail=f"Produk {p.get('sku')} digantikan oleh '{ref}' yang tidak ditemukan — rapikan master produk dulu.")
        p, hops = nxt, hops + 1
    if p.get("status", "active") != "active" or p.get("active") is False:
        raise HTTPException(status_code=400, detail=f"Produk {p.get('sku')} nonaktif — pilih produk aktif.")
    require_unit(p.get("base_unit"), p.get("sku"))
    return p, ({"id": first["id"], "sku": first.get("sku", ""), "name": first.get("name", "")} if hops else None)


async def decode_label(session: Dict[str, Any], raw: str, supplier_id: str = "") -> Dict[str, Any]:
    """Pindai label supplier (parser penerimaan dipakai ulang) → saran produk, panjang (terverifikasi), lot, no. roll."""
    from services import label_decoder_service as ldec
    from services import supplier_item_service as sis
    sup = await db.suppliers.find_one({"id": supplier_id}, {"_id": 0, "label_pattern": 1}) if supplier_id else None
    try:
        dec = ldec.decode(raw, (sup or {}).get("label_pattern"))
    except ldec.LabelDecodeError as exc:
        raise HTTPException(status_code=400, detail={"code": "UNDECODABLE", "message": str(exc)}) from exc
    sitem = None
    if dec.get("supplier_sku"):
        sitem = await sis.lookup(supplier_sku=dec["supplier_sku"], supplier_id=supplier_id, entity_id=session.get("entity_id", ""))
    if sitem is None and dec.get("gtin"):
        sitem = await db.supplier_items.find_one({"barcode": dec["gtin"], "status": "active"}, {"_id": 0})
    pid = (sitem or {}).get("product_id") or ""
    if not pid and dec.get("supplier_sku"):
        own = await db.products.find_one({"sku": dec["supplier_sku"]}, {"_id": 0, "id": 1})
        pid = (own or {}).get("id", "")
    product, redirected = None, None
    if pid:
        try:
            p, redirected = await resolve_product(pid)
            product = {"id": p["id"], "sku": p.get("sku"), "name": p.get("name"), "base_unit": p.get("base_unit")}
        except HTTPException as exc:
            dec["product_error"] = exc.detail
    return {"decoded": safe_doc(dec), "product": product, "redirected_from": redirected,
            "length": dec.get("length"), "length_unit": dec.get("length_unit"), "lot": dec.get("lot") or "",
            "old_roll_no": dec.get("roll_no") or "",
            "message": "" if product else "Produk dari label belum dikenali — pilih produk, atau simpan sebagai 'produk belum dikenali'."}


async def _match_old_no(session: Dict[str, Any], old_no: str) -> Tuple[Optional[Dict[str, Any]], str]:
    if not old_no:
        return None, ""
    rows = await db.inventory_rolls.find(
        {"warehouse_id": session["warehouse_id"], "$or": [{"roll_no": old_no}, {"id": old_no}, {"supplier_roll_no": old_no}]},
        {**plan_svc.OLD_FIELDS, "registration": 1}).to_list(10)
    hit = next((r for r in rows if in_scope(session, r)), None)
    if hit:
        return hit, ""
    return None, f"Nomor roll lama {old_no} tidak ditemukan di cakupan sesi — dicatat sebagai referensi saja."


async def build_line(session: Dict[str, Any], body: Dict[str, Any], actor: Dict[str, Any], allowed: Optional[List[str]],
                     existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validasi + susun dokumen baris (tambah & ubah memakai jalur yang sama)."""
    from services import placement_rules as pr
    from services.receiving_roll_service import conv_qty, uom_engine
    import domain_registry as dr
    reg = session["registration"]
    base = {**existing, "qty": existing.get("qty_input"), "unit": existing.get("unit_input")} if existing else {}
    cur = {**base, **{k: v for k, v in body.items() if k in EDITABLE and v is not None}}
    wh = await db.warehouses.find_one({"id": session["warehouse_id"]}, {"_id": 0}) or {}
    node = pr.resolve_bin(wh, str(cur.get("bin_id") or ""))
    if not node:
        raise HTTPException(status_code=400, detail="Bin wajib dipindai/dipilih (alamat rak tempat roll ditemukan).")
    if node["bin"]["id"] not in set(reg.get("bin_ids") or []):
        raise HTTPException(status_code=400, detail=f"Bin {node['bin'].get('code')} di luar cakupan sesi ini.")
    owner = (cur.get("owner_entity_id") or session.get("entity_id") or "").strip()
    if allowed is not None and owner not in allowed:
        raise HTTPException(status_code=403, detail=f"PT pemilik {owner} di luar akses Anda.")
    unrec = bool(cur.get("unrecognized")) and not body.get("product_id")
    note = str(cur.get("note") or "").strip()
    qty_in = cur.get("qty")
    try:
        qty_in = None if qty_in in (None, "") else float(qty_in)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Panjang roll harus angka.")
    if qty_in is not None and (qty_in != qty_in or qty_in <= 0 or qty_in > 100000):
        raise HTTPException(status_code=400, detail="Panjang roll wajib > 0 (dan masuk akal).")
    product, redirected, qty_base, base_unit = None, None, None, ""
    if unrec or not cur.get("product_id"):
        if len(note) < 3:
            raise HTTPException(status_code=400, detail="Produk belum dikenali: isi keterangan (warna/motif/kode di kain) minimal 3 huruf.")
        unrec = True
    else:
        product, redirected = await resolve_product(str(cur["product_id"]))
        if qty_in is None:
            raise HTTPException(status_code=400, detail="Panjang roll wajib diisi.")
        base_unit = product["base_unit"]
        qty_base = round(conv_qty(product, qty_in, cur.get("unit") or base_unit, base_unit, await uom_engine()), 4)
    try:
        grade = dr.require_grade(cur.get("grade"), "A")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    line_id = (existing or {}).get("id") or new_id("irl")
    epc, src = (existing or {}).get("epc"), (existing or {}).get("epc_source")
    if reg["epc_mode"] == "read":
        if not existing or (body.get("epc") and try_canonical(body["epc"]) != epc):
            epc = try_canonical(cur.get("epc"))
            if not epc:
                raise HTTPException(status_code=400, detail="EPC tidak valid: pindai tag (24 karakter hex).")
        src = "read"
    elif not epc:
        epc, src = await _new_system_epc(session), "system"
    st = await epc_status(session, epc, line_id)
    if not st["ok"]:
        raise HTTPException(status_code=409, detail={"code": "EPC_CONFLICT", "message": st["message"]})
    matched, note_match = (st["matched_roll"], "") if st["matched_roll"] else await _match_old_no(session, str(cur.get("old_roll_no") or "").strip())
    mid = (matched or {}).get("id") or ""
    length_verified = bool(cur.get("length_from_label")) and qty_base is not None
    return {
        "id": line_id, "session_id": session["id"], "entity_id": session.get("entity_id"), "warehouse_id": session["warehouse_id"],
        "epc": epc, "epc_display": display_epc(epc), "epc_source": src,
        "tag_state": "read" if src == "read" else ((existing or {}).get("tag_state") or "pending_write"),
        "product_id": product["id"] if product else "", "sku": (product or {}).get("sku", ""),
        "product_name": (product or {}).get("name", ""), "redirected_from": redirected,
        "qty": qty_base, "unit": base_unit, "qty_input": qty_in, "unit_input": cur.get("unit") or base_unit,
        "length_from_label": bool(cur.get("length_from_label")), "length_verified": length_verified,
        "lot": str(cur.get("lot") or "").strip(), "dye_lot": str(cur.get("dye_lot") or "").strip(), "grade": grade,
        "owner_entity_id": owner, "bin_id": node["bin"]["id"], "bin_code": node["bin"].get("code", ""),
        "rack_id": (node.get("rack") or {}).get("id") or "-", "zone_id": (node.get("zone") or {}).get("id"),
        "old_roll_no": str(cur.get("old_roll_no") or "").strip(), "matched_roll_id": mid,
        "matched_roll_no": (matched or {}).get("roll_no", ""), "match_source": ("epc" if st["matched_roll"] else "old_no") if mid else "",
        "match_note": note_match, "note": note, "label_raw": str(cur.get("label_raw") or "")[:500],
        "unrecognized": ({"note": note, "photo": ((existing or {}).get("unrecognized") or {}).get("photo")} if unrec else None),
        "status": "draft", "live": True, "created_by": (existing or {}).get("created_by") or actor["name"],
        "created_at": (existing or {}).get("created_at") or now_iso(), "updated_at": now_iso(), "updated_by": actor["name"],
    }


def _dup_message(exc: DuplicateKeyError) -> str:
    if "match_key" in str(exc):
        return "Roll lama ini sudah dicocokkan ke baris lain di sesi ini — periksa nomor roll lama."
    return "EPC ini baru saja didaftarkan di baris lain — pindai tag lain."


async def add_line(session: Dict[str, Any], body: Dict[str, Any], actor: Dict[str, Any], allowed) -> Dict[str, Any]:
    from services.initial_registration_service import assert_status, ensure_indexes
    assert_status(session, "running")
    await ensure_indexes()
    line = await build_line(session, body, actor, allowed)
    doc = {**line, **({"match_key": f"{session['id']}:{line['matched_roll_id']}"} if line["matched_roll_id"] else {})}
    try:
        await db[LINES].insert_one(dict(doc))
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail=_dup_message(exc)) from exc
    # Sesi diajukan/ditolak di antara validasi & simpan → baris dicabut (tidak menyusup ke rencana yang sudah beku).
    if not await db.cycle_count_sessions.find_one({"id": session["id"], "status": "running"}, {"_id": 1}):
        await db[LINES].delete_one({"id": line["id"], "status": "draft"})
        raise HTTPException(status_code=409, detail="Sesi baru saja diajukan/ditutup — baris tidak disimpan.")
    return safe_doc(doc)


async def update_line(session: Dict[str, Any], line_id: str, body: Dict[str, Any], actor: Dict[str, Any], allowed) -> Dict[str, Any]:
    cur = await db[LINES].find_one({"id": line_id, "session_id": session["id"]}, {"_id": 0})
    if not cur or cur.get("status") != "draft":
        raise HTTPException(status_code=404, detail="Baris tidak ditemukan / sudah diterapkan / dibatalkan.")
    if session["status"] == "pending_approval" and body.get("product_id") and cur.get("product_id") == "":
        key = plan_svc.gkey(body["product_id"], body.get("owner_entity_id") or cur.get("owner_entity_id") or "")
        if key in ((session.get("registration") or {}).get("groups") or {}):
            raise HTTPException(status_code=409, detail="Kelompok produk ini sudah disetujui — petakan sebelum menyetujui produknya.")
    line = await build_line(session, body, actor, allowed, existing=cur)
    upd: Dict[str, Any] = {"$set": line}
    if line["matched_roll_id"]:
        upd["$set"]["match_key"] = f"{session['id']}:{line['matched_roll_id']}"
    else:
        upd["$unset"] = {"match_key": ""}
    try:
        res = await db[LINES].update_one({"id": line_id, "status": "draft", "updated_at": cur["updated_at"]}, upd)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail=_dup_message(exc)) from exc
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Baris baru saja diubah orang lain — muat ulang.")
    return safe_doc(await db[LINES].find_one({"id": line_id}, {"_id": 0}))


async def void_line(session: Dict[str, Any], line_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    res = await db[LINES].update_one({"id": line_id, "session_id": session["id"], "status": "draft"},
                                     {"$set": {"status": "void", "live": False, "voided_by": actor["name"], "voided_at": now_iso()},
                                      "$unset": {"match_key": ""}})
    if res.modified_count != 1:
        raise HTTPException(status_code=404, detail="Baris tidak ditemukan / sudah diterapkan / sudah dibatalkan.")
    return {"ok": True, "line_id": line_id}


async def mark_written(session: Dict[str, Any], line_ids: List[str], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Mode EPC sistem: EPC sudah ditulis ke tag fisik. Baris sudah disetujui → tag `pending_print` diaktifkan."""
    ids = [i for i in dict.fromkeys(line_ids or []) if i][:500]
    rows = await db[LINES].find({"id": {"$in": ids}, "session_id": session["id"], "tag_state": "pending_write",
                                 "status": {"$in": ["draft", "applied"]}}, {"_id": 0, "id": 1, "result": 1}).to_list(500)
    done = [r["id"] for r in rows]
    if done:
        await db[LINES].update_many({"id": {"$in": done}, "tag_state": "pending_write"},
                                    {"$set": {"tag_state": "written", "tag_written_by": actor["name"], "tag_written_at": now_iso()}})
    tag_ids = [(r.get("result") or {}).get("tag_id") for r in rows if (r.get("result") or {}).get("tag_id")]
    if tag_ids:
        await db.rfid_tags.update_many({"id": {"$in": tag_ids}, "status": "pending_print"},
                                       {"$set": {"status": "active", "activated_at": now_iso(), "activated_by": actor["name"]}})
    return {"written": len(done), "activated_tags": len(tag_ids)}


async def list_lines(session_id: str, rack_id: str = "", bin_id: str = "", status: str = "", limit: int = 500) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"session_id": session_id, "status": {"$in": [status] if status else ["draft", "applied"]}}
    if rack_id:
        q["rack_id"] = rack_id
    if bin_id:
        q["bin_id"] = bin_id
    return await db[LINES].find(q, {"_id": 0}).sort("created_at", -1).to_list(min(max(int(limit or 500), 1), 2000))
