"""P02 (IMP-22/24/25) — evaluator penempatan BERSAMA untuk semua jalur (putaway manual, scan
penerimaan, PA antar gedung, transfer) + resolver alamat modern/legacy + kapasitas roll + saran bin.

Keputusan pemilik (DEC-10, 2026-10-11):
- Kapasitas bin = JUMLAH ROLL (`capacity_rolls`). Kosong/0 = tanpa batas, utilisasi "belum diatur".
- Melebihi kapasitas = DITOLAK, kecuali supervisor gudang memberi pengecualian beralasan (tercatat).
- Roll QC/hold/rusak hanya ke area berfungsi `qc` (zona/lemari/tingkat/bin, diwarisi). In-transit,
  offsite, consumed selalu ditolak.
- Rules (kategori, grade, jenis kain) pada gudang/zona/lemari/tingkat/bin digabung AND; anak
  tidak bisa membuka larangan induk.
- Campur SKU/lot dalam satu bin BOLEH, kecuali node diberi aturan `single_sku` / `single_lot` (diwarisi).
- Saran bin: utamakan bin berisi SKU+lot sama, lalu SKU sama, lalu bin kosong, lalu sisanya.
- Struktur & kapasitas diubah oleh warehouse_admin, manager, admin.
"""
import time
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import now_iso

PLACEABLE = {"available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged"}
QC_STATUSES = {"quarantine", "hold", "blocked", "damaged"}
NODE_FUNCTIONS = {"storage", "qc", "staging", "return"}
SUPERVISOR_ROLES = {"warehouse_admin", "manager", "admin"}


def _norm(v: Any) -> str:
    return str(v or "").strip().lower()


def node_rules(node: Dict[str, Any]) -> Dict[str, Any]:
    r = (node or {}).get("rules") or {}
    return {"categories": [str(x).strip() for x in r.get("categories") or [] if str(x).strip()],
            "grades": [str(x).strip().upper() for x in r.get("grades") or [] if str(x).strip()],
            "fabric_types": [_norm(x) for x in r.get("fabric_types") or [] if _norm(x)],
            "single_sku": bool(r.get("single_sku")), "single_lot": bool(r.get("single_lot"))}


def warehouse_rules(wh: Dict[str, Any]) -> Dict[str, Any]:
    """Rules level gudang. DEV-G02: semua daftar yang terisi berlaku (AND), apa pun `mode`-nya."""
    sr = wh.get("storage_rules") or {}
    if (sr.get("mode") or "none") == "none":
        return node_rules({})
    return node_rules({"rules": sr})


def is_supervisor(actor: Optional[Dict[str, Any]]) -> bool:
    from role_registry import role_in
    return role_in((actor or {}).get("role"), SUPERVISOR_ROLES)


def assert_supervisor(actor: Optional[Dict[str, Any]], action: str) -> None:
    if not is_supervisor(actor):
        raise HTTPException(status_code=403, detail=f"Hanya Admin Gudang, Manajer, atau Admin yang boleh {action}.")


def flatten_nodes(wh: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Semua bin + rantai node induknya (zona → lemari/rak → tingkat → bin). Legacy rack.bins = tanpa tingkat."""
    out = []
    for z in wh.get("zones") or []:
        for rk in z.get("racks") or []:
            levels = rk.get("levels")
            groups = [(lv, lv.get("bins") or []) for lv in levels] if levels else [(None, rk.get("bins") or [])]
            for lv, bins in groups:
                for b in bins:
                    chain = [n for n in (z, rk, lv, b) if n is not None]
                    path = " / ".join(str(n.get("name") or n.get("code") or "") for n in chain)
                    out.append({"bin": b, "chain": chain, "zone": z, "rack": rk, "level": lv, "path": path})
    return out


def resolve_bin(wh: Dict[str, Any], ref: str) -> Optional[Dict[str, Any]]:
    """Satu resolver alamat (id atau kode/label, tanpa beda besar-kecil) untuk format lama & baru (DEV-F01)."""
    key = _norm(ref)
    if not key:
        return None
    for n in flatten_nodes(wh):
        b = n["bin"]
        if _norm(b.get("id")) == key or _norm(b.get("code")) == key:
            return n
    return None


def effective(wh: Dict[str, Any], node: Dict[str, Any]) -> Dict[str, Any]:
    wr = warehouse_rules(wh)
    layers = [("Gudang " + (wh.get("name") or ""), wr)]
    func, single_sku, single_lot = "storage", wr["single_sku"], wr["single_lot"]
    for n in node["chain"]:
        r = node_rules(n)
        layers.append((n.get("name") or n.get("code") or "", r))
        single_sku, single_lot = single_sku or r["single_sku"], single_lot or r["single_lot"]
        if _norm(n.get("function")) in NODE_FUNCTIONS:
            func = _norm(n.get("function"))
    cap = int((node["bin"].get("capacity_rolls") or 0) or 0)
    return {"layers": layers, "function": func, "capacity_rolls": cap if cap > 0 else None,
            "single_sku": single_sku or single_lot, "single_lot": single_lot}


def effective_view(wh: Dict[str, Any], node: Dict[str, Any]) -> Dict[str, Any]:
    """Rules efektif untuk UI (gabungan semua lapisan, tanpa efek samping)."""
    eff = effective(wh, node)
    return {"function": eff["function"], "capacity_rolls": eff["capacity_rolls"],
            "single_sku": eff["single_sku"], "single_lot": eff["single_lot"],
            "layers": [{"label": lbl, **{k: v for k, v in r.items() if v}} for lbl, r in eff["layers"]
                       if any(r.values())]}


def _attr_violations(layers, product: Dict[str, Any], grade: str) -> List[str]:
    cat, fab, g = str(product.get("category") or ""), _norm(product.get("fabric_type")), (grade or "A").upper()
    out = []
    for label, r in layers:
        if r["categories"] and cat not in r["categories"]:
            out.append(f"Kategori '{cat or '—'}' tidak diizinkan di {label} (hanya {', '.join(r['categories'])}).")
        if r["grades"] and g not in r["grades"]:
            out.append(f"Grade '{g}' tidak diizinkan di {label} (hanya grade {', '.join(r['grades'])}).")
        if r["fabric_types"] and fab not in r["fabric_types"]:
            out.append(f"Jenis kain '{fab or '—'}' tidak diizinkan di {label} (hanya {', '.join(r['fabric_types'])}).")
    return out


def is_held(roll: Dict[str, Any]) -> bool:
    return bool(((roll.get("inspection") or {}).get("hold") or {}).get("held")) or roll.get("status") in QC_STATUSES


def status_violation(roll: Dict[str, Any], extra_ok: tuple = ()) -> Optional[str]:
    st = roll.get("status") or ""
    if st in PLACEABLE or st in extra_ok:
        return None
    if st.startswith("in_transit"):
        return f"Roll {roll.get('roll_no', '')} masih dalam perjalanan ({st}) — terima dulu di gudang tujuan."
    return f"Roll {roll.get('roll_no', '')} berstatus {st or '—'} (bukan stok fisik di gudang) — tidak bisa ditempatkan."


async def warehouse_violations(wh: Dict[str, Any], roll: Dict[str, Any], product: Dict[str, Any]) -> List[str]:
    """Level gudang (dipakai PA & transfer): owner shared/dedicated + rules gudang (DEV-F05, DEV-G04)."""
    from services.warehouse_scope_service import is_usable
    out = []
    owner = roll.get("owner_entity_id")
    if owner and not is_usable(wh, owner):
        # Audit UI tahap 2 — nama badan usaha, bukan id mentah ("ent_kanda") & tanpa istilah "(dedicated)".
        ent = await db.business_entities.find_one({"id": owner}, {"_id": 0, "short_name": 1, "name": 1}) or {}
        owner_name = ent.get("short_name") or ent.get("name") or owner
        out.append(f"Gudang {wh.get('name', '')} khusus untuk badan usaha lain — barang milik {owner_name} tidak boleh masuk.")
    out += _attr_violations([("Gudang " + (wh.get("name") or ""), warehouse_rules(wh))], product, roll.get("grade", "A"))
    return out


async def bin_contents(warehouse_id: str, bin_ids: Optional[List[str]] = None, exclude_roll: str = "") -> Dict[str, Dict[str, Any]]:
    """Isi fisik per bin (SEMUA owner): jumlah roll + set SKU & (SKU, lot). Satu query untuk banyak bin."""
    q: Dict[str, Any] = {"warehouse_id": warehouse_id, "status": {"$in": sorted(PLACEABLE)},
                         "length_remaining": {"$gt": 0}, "bin_id": {"$in": bin_ids} if bin_ids else {"$nin": [None, ""]}}
    if exclude_roll:
        q["id"] = {"$ne": exclude_roll}
    out: Dict[str, Dict[str, Any]] = {}
    async for r in db.inventory_rolls.find(q, {"_id": 0, "bin_id": 1, "product_id": 1, "lot": 1}):
        c = out.setdefault(r["bin_id"], {"count": 0, "products": set(), "lots": set()})
        c["count"] += 1
        c["products"].add(r.get("product_id"))
        c["lots"].add((r.get("product_id"), r.get("lot") or ""))
    return out


EMPTY = {"count": 0, "products": set(), "lots": set()}


def evaluate_pure(wh: Dict[str, Any], node: Dict[str, Any], roll: Dict[str, Any], product: Dict[str, Any],
                  wh_blocks: List[str], contents: Dict[str, Any], extra_status_ok: tuple = ()) -> Dict[str, Any]:
    """Inti evaluasi (tanpa I/O) — SAMA untuk saran dan aksi akhir."""
    eff = effective(wh, node)
    blocks: List[str] = []
    sv = status_violation(roll, extra_status_ok)
    if sv:
        blocks.append(sv)
    if roll.get("warehouse_id") and roll["warehouse_id"] != wh.get("id"):
        blocks.append("Bin tujuan bukan di gudang roll ini — pindah gudang lewat transfer/PA.")
    blocks += wh_blocks
    blocks += _attr_violations(eff["layers"][1:], product, roll.get("grade", "A"))
    if is_held(roll) and eff["function"] != "qc":
        blocks.append(f"Roll {roll.get('roll_no', '')} sedang QC/ditahan — hanya boleh ke area berfungsi QC/karantina.")
    pid, lot = roll.get("product_id"), roll.get("lot") or ""
    if eff["single_sku"] and contents["products"] - {pid}:
        blocks.append(f"Bin {node['bin'].get('code', '')} khusus satu SKU dan sudah berisi SKU lain.")
    elif eff["single_lot"] and contents["lots"] - {(pid, lot)}:
        blocks.append(f"Bin {node['bin'].get('code', '')} khusus satu lot dan sudah berisi lot lain.")
    cap, count = eff["capacity_rolls"], contents["count"]
    over = cap is not None and count + 1 > cap
    return {"ok": not blocks and not over, "blocks": blocks, "function": eff["function"], "path": node["path"],
            "capacity": {"limit": cap, "count": count, "over": over},
            "same_lot": (pid, lot) in contents["lots"], "same_sku": pid in contents["products"]}


async def evaluate(wh: Dict[str, Any], node: Dict[str, Any], roll: Dict[str, Any], product: Dict[str, Any],
                   *, extra_status_ok: tuple = ()) -> Dict[str, Any]:
    """Hasil: {ok, blocks[], capacity:{limit,count,over}, function, path}. Tanpa efek samping."""
    bid = node["bin"]["id"]
    contents = (await bin_contents(wh["id"], [bid], exclude_roll=roll.get("id", ""))).get(bid, EMPTY)
    return evaluate_pure(wh, node, roll, product, await warehouse_violations(wh, roll, product), contents,
                         extra_status_ok)


async def recommend(wh: Dict[str, Any], roll: Dict[str, Any], product: Dict[str, Any], limit: int = 8,
                    extra_status_ok: tuple = ()) -> Dict[str, Any]:
    """Saran bin VALID (lolos evaluator yang sama). Urutan: SKU+lot sama → SKU sama → kosong → lainnya."""
    nodes = flatten_nodes(wh)
    contents = await bin_contents(wh["id"], exclude_roll=roll.get("id", ""))
    wh_blocks = await warehouse_violations(wh, roll, product)
    rows, rejected = [], 0
    for n in nodes:
        c = contents.get(n["bin"]["id"], EMPTY)
        res = evaluate_pure(wh, n, roll, product, wh_blocks, c, extra_status_ok)
        if not res["ok"]:
            rejected += 1
            continue
        tier = 0 if res["same_lot"] else 1 if res["same_sku"] else 2 if c["count"] == 0 else 3
        cap = res["capacity"]["limit"]
        rows.append({"bin_id": n["bin"]["id"], "bin_code": n["bin"].get("code", ""), "path": n["path"],
                     "function": res["function"], "tier": tier,
                     "reason": ["Berisi SKU & lot yang sama", "Berisi SKU yang sama", "Bin kosong", "Masih ada ruang"][tier],
                     "roll_count": c["count"], "capacity_rolls": cap,
                     "free_rolls": (cap - c["count"]) if cap else None})
    rows.sort(key=lambda r: (r["tier"], -(r["free_rolls"] if r["free_rolls"] is not None else 10 ** 6), r["bin_code"]))
    return {"suggestions": rows[:limit], "valid_count": len(rows), "rejected_count": rejected,
            "warehouse_blocks": wh_blocks}


# ─── Kunci per bin (MongoDB standalone tanpa transaksi) — cegah dua petugas melewati kapasitas ───
async def acquire_bin_lock(bin_id: str, holder: str) -> None:
    now = time.time()
    await db.bin_locks.delete_many({"bin_id": bin_id, "expires": {"$lt": now}})
    try:
        await db.bin_locks.insert_one({"_id": f"lock:{bin_id}", "bin_id": bin_id, "holder": holder,
                                       "expires": now + 15, "at": now_iso()})
    except Exception:
        raise HTTPException(status_code=409, detail="Bin ini sedang diisi petugas lain — coba lagi beberapa detik lagi.")


async def release_bin_lock(bin_id: str) -> None:
    await db.bin_locks.delete_one({"_id": f"lock:{bin_id}"})


def check_override(actor: Optional[Dict[str, Any]], override: Optional[Dict[str, Any]], res: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Kapasitas lebih → wajib pengecualian supervisor ber-alasan. Blok lain tidak bisa dikecualikan."""
    if res["blocks"]:
        raise HTTPException(status_code=400, detail=" | ".join(res["blocks"][:5]))
    if not res["capacity"]["over"]:
        return None
    reason = str((override or {}).get("reason") or "").strip()
    c = res["capacity"]
    if not reason:
        raise HTTPException(status_code=409, detail={
            "code": "BIN_CAPACITY_FULL", "limit": c["limit"], "count": c["count"],
            "message": f"Bin penuh: {c['count']}/{c['limit']} roll. Pilih bin lain atau minta supervisor gudang memberi pengecualian beralasan."})
    if not is_supervisor(actor):
        raise HTTPException(status_code=403, detail="Pengecualian kapasitas hanya oleh supervisor gudang, manajer, atau admin.")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Alasan pengecualian kapasitas minimal 5 karakter.")
    return {"by": actor.get("name"), "by_id": actor.get("id"), "reason": reason, "at": now_iso(),
            "limit": c["limit"], "count": c["count"]}
