"""FIX-9 (audit 9 Nov 2026 — B3a SSOT-4, FIX-2 §5 butir 1 & 5) — cadangan bahan makloon DIKUNCI PER ROLL.

Sebelumnya cadangan makloon (`material_reservations`) hanya angka produk × PT: angka stok dikurangi lewat
`stock_figures.allocate_makloon`, tetapi roll-nya tetap "tersedia" sehingga pemilih roll, alokasi SO/POS, tahan/WIP
dan issue MKO lain bisa mengambil roll yang sebenarnya dicadangkan untuk makloon.

MODEL (satu skema dengan reservasi potong WM-02 — tidak ada skema kedua)
* Kunci = entri `length_reservations` di roll nyata, dibuat lewat helper yang sama dengan reservasi potong
  (`roll_service._reserve_length`, CAS panjang bebas):
      {"id": "rsv_…", "ref": {"type": "makloon", "id": <id cadangan>, "number": "MKO-…"/"PR-…", "mko_id", "mko_number",
       "pr_id", "pr_number", "entity_id"}, "qty": <panjang terkunci>, "status": "reserved", "created_at"}
  Roll = SSOT panjang terkunci. `rebuild_balance` memasukkannya ke ember `reserved_qty` (seperti panjang dipesan
  potong) + penanda `makloon_locked_qty`; `stock_figures.segments` menampilkannya di kelompok "Cadangan makloon".
* Cadangan menyimpan CERMIN `locks[]` (roll, gudang, lot, qty) + `locked_qty`, dibangun ulang dari roll (`sync`)
  sesudah setiap perubahan. `qty − locked_qty` = "cadangan belum terkunci" (stok kurang saat mengunci) — hanya bagian
  ini yang masih dikurangkan `allocate_makloon` (bagian terkunci sudah keluar dari Tersedia lewat saldo).
* Bukan reservasi potong: `pending_cuts` & `confirm_cut` mengabaikan/menolak entri bertipe makloon.

ATURAN PILIH ROLL (`plan`)
* roll `available` milik PT cadangan, produk & satuan dasar sama, tidak diklaim perpindahan (PA), tidak ditahan
  inspeksi, tidak di-peg (earmark), di gudang yang dihitung (aktif, bukan data uji), panjang bebas > 0;
* gudang = gudang sumber (MKO `from_warehouse_id` / langkah 1; PR `warehouse_id`) bila ada — tidak meluber ke gudang
  lain (sisanya "belum terkunci"); bila kosong: gudang ber-panjang-bebas terbesar dulu (aturan `allocate_makloon`);
* urutan roll FIFO (diterima paling awal dulu, lalu nomor roll) — sama dengan urutan issue jalur jumlah (FEFO
  `move_rolls_by_qty`) dan daftar pilih roll issue, sehingga issue memakai roll yang memang dikunci. Roll utuh dikunci
  penuh; roll terakhir dikunci sebagian.

KONKURENSI & JEJAK
* CAS per roll terhadap panjang bebas (`_reserve_length`) → dua cadangan/pesanan tidak pernah mengunci panjang yang
  sama dua kali; pelepasan CAS terhadap isi `length_reservations` yang dibaca.
* Mutex per cadangan (`material_reservation_locks._id = "rl:<id>"`, kedaluwarsa 60 dtk) → dua panggilan `lock` untuk
  cadangan yang sama tidak mengunci dobel melebihi `qty`.
* Setiap perubahan: entri `history` cadangan + satu baris `audit_logs` (`material_reservations`).
"""
import asyncio
import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple

from pymongo.errors import DuplicateKeyError

from db import db
from core_utils import now_iso

logger = logging.getLogger(__name__)

LOCK_TYPE = "makloon"
LOCK_EPS = 0.01          # panjang kunci dibulatkan 2 desimal (`_reserve_length`)
MUTEX_TTL_S = 60
ROLL_PROJ = {"_id": 0, "id": 1, "roll_no": 1, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1, "lot": 1,
             "unit": 1, "status": 1, "length_remaining": 1, "length_reserved": 1, "length_reservations": 1,
             "active_movement": 1, "inspection": 1, "earmarked_for": 1, "received_date": 1, "created_at": 1}


# ── Pembaca entri kunci di roll ───────────────────────────────────────────────────────────────────────────────────

def is_lock(entry: Optional[Dict[str, Any]]) -> bool:
    return ((entry or {}).get("ref") or {}).get("type") == LOCK_TYPE


def roll_locks(roll: Dict[str, Any], res_ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    want = set(res_ids) if res_ids is not None else None
    return [x for x in (roll.get("length_reservations") or [])
            if is_lock(x) and (want is None or (x.get("ref") or {}).get("id") in want)]


def roll_locked_qty(roll: Dict[str, Any], res_ids: Optional[Iterable[str]] = None) -> float:
    return round(sum(float(x.get("qty") or 0) for x in roll_locks(roll, res_ids)), 4)


def foreign_reserved(roll: Dict[str, Any], own_ids: Iterable[str] = ()) -> float:
    """Panjang yang dipegang reservasi LAIN (potong SO, cadangan makloon lain) — bukan kunci cadangan `own_ids`."""
    return round(float(roll.get("length_reserved") or 0) - roll_locked_qty(roll, list(own_ids or [])), 4)


def free_length(roll: Dict[str, Any]) -> float:
    return round(float(roll.get("length_remaining") or 0) - float(roll.get("length_reserved") or 0), 4)


def doc_number(res: Dict[str, Any]) -> str:
    return str(res.get("mko_number") or res.get("pr_number") or "")


def lock_ref(res: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": LOCK_TYPE, "id": res["id"], "number": doc_number(res),
            "mko_id": res.get("mko_id") or "", "mko_number": res.get("mko_number") or "",
            "pr_id": res.get("pr_id") or "", "pr_number": res.get("pr_number") or "",
            "entity_id": res.get("owner_entity_id") or ""}


def lock_numbers(roll: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for x in roll_locks(roll):
        n = (x.get("ref") or {}).get("number") or ""
        if n and n not in out:
            out.append(n)
    return out


def hold_text(roll: Dict[str, Any], visible_entity_ids: Optional[Iterable[str]] = None) -> str:
    """Penjelasan singkat siapa yang memegang panjang roll — untuk pesan penolakan.

    Kunci makloon menyebut nomor MKO/PR pemiliknya; bila roll milik PT di luar izin penonton (B3a #7 / FIX-2: lintas
    PT hanya angka & identitas roll) nomor dokumen TIDAK disebut."""
    parts: List[str] = []
    mk = roll_locked_qty(roll)
    if mk > 0:
        vis = visible_entity_ids is None or (roll.get("owner_entity_id") in set(visible_entity_ids))
        nums = lock_numbers(roll) if vis else []
        parts.append("dicadangkan makloon" + (f" {', '.join(nums)}" if nums else " (PT lain)")
                     + f" {mk:g} {roll.get('unit') or ''}".rstrip())
    other = round(float(roll.get("length_reserved") or 0) - mk, 4)
    if other > LOCK_EPS:
        parts.append(f"dipesan potong {other:g} {roll.get('unit') or ''}".rstrip())
    return " · ".join(parts)


def roll_summary(roll: Dict[str, Any], visible: bool = True) -> Optional[Dict[str, Any]]:
    """Ringkasan kunci makloon untuk tampilan roll (`makloon_lock`), None bila tidak ada."""
    mk = roll_locked_qty(roll)
    if mk <= 0:
        return None
    return {"qty": round(mk, 2), "numbers": lock_numbers(roll) if visible else [], "visible": bool(visible)}


# ── Mutex per cadangan ────────────────────────────────────────────────────────────────────────────────────────────

async def _acquire(key: str) -> None:
    for _ in range(200):
        try:
            await db.material_reservation_locks.insert_one({"_id": key, "at": now_iso(), "exp": time.time() + MUTEX_TTL_S})
            return
        except DuplicateKeyError:
            # pemegang mati di tengah jalan → ambil alih sesudah kedaluwarsa
            await db.material_reservation_locks.delete_one({"_id": key, "exp": {"$lt": time.time()}})
            await asyncio.sleep(0.03)
    raise RuntimeError("Kunci cadangan makloon sedang diproses permintaan lain — coba lagi.")


async def _release_mutex(key: str) -> None:
    await db.material_reservation_locks.delete_one({"_id": key})


class _Mutex:
    def __init__(self, res_id: str):
        self.key = f"rl:{res_id}"

    async def __aenter__(self):
        await _acquire(self.key)
        return self

    async def __aexit__(self, *exc):
        await _release_mutex(self.key)
        return False


# ── Kandidat & rencana ───────────────────────────────────────────────────────────────────────────────────────────

def _fifo_key(r: Dict[str, Any]) -> Tuple[str, str, str]:
    return (str(r.get("received_date") or r.get("created_at") or ""), str(r.get("created_at") or ""),
            str(r.get("roll_no") or r.get("id") or ""))


def lockable(roll: Dict[str, Any], base_unit: str = "", counted: Optional[set] = None) -> bool:
    if roll.get("status") != "available" or (roll.get("active_movement") or {}).get("id"):
        return False
    if ((roll.get("inspection") or {}).get("hold") or {}).get("held"):
        return False
    ear = roll.get("earmarked_for")
    if isinstance(ear, dict) and ear.get("id"):
        return False
    if counted is not None and roll.get("warehouse_id") not in counted:
        return False
    if base_unit and (roll.get("unit") or base_unit).lower() != base_unit.lower():
        return False   # roll bersatuan lain (data lama/impor) tidak dikunci — panjang kunci = satuan dasar produk
    return free_length(roll) > LOCK_EPS


async def candidates(res: Dict[str, Any], warehouses: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    from services.stock_figures import counted_warehouse_ids
    q: Dict[str, Any] = {"product_id": res["product_id"], "owner_entity_id": res.get("owner_entity_id") or "",
                         "status": "available", "length_remaining": {"$gt": 0}}
    if warehouses:
        q["warehouse_id"] = {"$in": list(warehouses)}
    prod = await db.products.find_one({"id": res["product_id"]}, {"_id": 0, "base_unit": 1}) or {}
    counted = await counted_warehouse_ids()
    rows = await db.inventory_rolls.find(q, ROLL_PROJ).to_list(None)
    return [r for r in rows if lockable(r, prod.get("base_unit") or "", counted)]


def plan(rolls: List[Dict[str, Any]], need: float, source_wh: str = "") -> List[Tuple[Dict[str, Any], float]]:
    """[(roll, panjang dikunci)] menurut aturan modul (gudang sumber / bebas terbesar, FIFO). Tidak menulis apa pun."""
    need = round(float(need or 0), 2)
    if need <= LOCK_EPS:
        return []
    by_wh: Dict[str, List[Dict[str, Any]]] = {}
    for r in rolls:
        if source_wh and r.get("warehouse_id") != source_wh:
            continue
        by_wh.setdefault(r.get("warehouse_id") or "", []).append(r)
    wh_order = sorted(by_wh, key=lambda w: (-sum(free_length(x) for x in by_wh[w]), w))
    out: List[Tuple[Dict[str, Any], float]] = []
    left = need
    for w in wh_order:
        for r in sorted(by_wh[w], key=_fifo_key):
            take = round(min(free_length(r), left), 2)
            if take <= LOCK_EPS:
                continue
            out.append((r, take))
            left = round(left - take, 2)
            if left <= LOCK_EPS:
                return out
    return out


# ── Sinkron cermin & jejak ───────────────────────────────────────────────────────────────────────────────────────

async def actual_locks(res_id: str) -> List[Dict[str, Any]]:
    out = []
    async for r in db.inventory_rolls.find({"length_reservations.ref.id": res_id}, ROLL_PROJ):
        q = roll_locked_qty(r, [res_id])
        if q > 0:
            out.append({"roll_id": r["id"], "roll_no": r.get("roll_no") or "", "warehouse_id": r.get("warehouse_id"),
                        "lot": r.get("lot") or "", "unit": r.get("unit") or "", "qty": round(q, 2),
                        "status": r.get("status")})
    out.sort(key=lambda x: (x["warehouse_id"] or "", x["roll_no"]))
    return out


async def sync(res_id: str) -> Dict[str, Any]:
    """Bangun ulang cermin `locks`/`locked_qty` cadangan dari roll (idempoten)."""
    locks = await actual_locks(res_id)
    locked = round(sum(x["qty"] for x in locks), 3)
    await db.material_reservations.update_one({"id": res_id}, {"$set": {
        "locks": locks, "locked_qty": locked, "lock_synced_at": now_iso()}})
    return {"locked_qty": locked, "locks": locks}


async def _trail(res: Dict[str, Any], event: str, qty: float, rolls: List[Dict[str, Any]], actor: str,
                 reason: str = "", **extra: Any) -> None:
    if qty <= 0 and event not in ("lock_shortage",):
        return
    entry = {"at": now_iso(), "event": event, "qty": round(qty, 2), "by": actor or "Sistem",
             "rolls": [{"roll_no": x.get("roll_no") or x.get("roll_id"), "qty": round(float(x.get("qty") or 0), 2)}
                       for x in rolls[:30]], **({"reason": reason} if reason else {}), **extra}
    await db.material_reservations.update_one({"id": res["id"]}, {"$push": {"history": entry}})
    try:
        from dependencies import audit
        await audit(actor or "Sistem", f"makloon_{event}", "material_reservations", res["id"],
                    {"qty": round(qty, 2), "doc": doc_number(res), "product_id": res.get("product_id"),
                     "rolls": entry["rolls"], **({"reason": reason} if reason else {}), **extra},
                    reason=reason, scope_entity_id=res.get("owner_entity_id") or "", source="fix9_makloon_lock")
    except Exception as exc:  # noqa: BLE001 — jejak audit tidak boleh menggagalkan kunci stok
        logger.warning("[makloon_roll_lock] audit gagal: %s", exc)


async def _rebuild(segs: Iterable[Tuple[str, str, str]]) -> None:
    from services.roll_service import rebuild_balance
    for p, w, o in set(segs):
        await rebuild_balance(p, w, o)


# ── Kunci / lepas ────────────────────────────────────────────────────────────────────────────────────────────────

async def _lock_more(res: Dict[str, Any], amount: float, source_wh: str = "") -> List[Dict[str, Any]]:
    """Kunci hingga `amount` panjang bebas (CAS per roll). Mengembalikan entri yang benar-benar terkunci."""
    from services.roll_service import _reserve_length
    got: List[Dict[str, Any]] = []
    left = round(float(amount or 0), 2)
    for _attempt in range(3):          # CAS kalah (roll diambil proses lain) → rencanakan ulang dari data segar
        if left <= LOCK_EPS:
            break
        steps = plan(await candidates(res, [source_wh] if source_wh else None), left, source_wh)
        if not steps:
            break
        progressed = False
        for roll, take in steps:
            held = await _reserve_length(roll, take, res["id"], lock_ref(res))
            if not held:
                continue
            progressed = True
            got.append({"roll_id": roll["id"], "roll_no": roll.get("roll_no") or "", "qty": take,
                        "warehouse_id": roll.get("warehouse_id"), "rsv_id": held["reservation_id"],
                        "seg": (roll["product_id"], roll["warehouse_id"], roll["owner_entity_id"])})
            left = round(left - take, 2)
        if not progressed:
            break
    return got


async def _unlock_roll(roll_id: str, res_ids: List[str], qty: Optional[float] = None,
                       newest_first: bool = True) -> Tuple[float, Optional[Dict[str, Any]]]:
    """Lepas kunci cadangan `res_ids` di satu roll — semua (`qty=None`) atau sebagian. CAS isi `length_reservations`
    yang dibaca (dicoba ulang bila roll berubah di tengah). → (panjang dilepas, roll sesudahnya)."""
    for _ in range(8):
        roll = await db.inventory_rolls.find_one({"id": roll_id}, ROLL_PROJ)
        if not roll:
            return 0.0, None
        mine = roll_locks(roll, res_ids)
        have = round(sum(float(x.get("qty") or 0) for x in mine), 2)
        if have <= 0:
            return 0.0, roll
        want = have if qty is None else round(min(float(qty), have), 2)
        if want <= 0:
            return 0.0, roll
        cut: Dict[str, float] = {}
        left = want
        for x in sorted(mine, key=lambda e: str(e.get("created_at") or ""), reverse=newest_first):
            take = round(min(float(x.get("qty") or 0), left), 2)
            if take <= 0:
                continue
            cut[x["id"]] = take
            left = round(left - take, 2)
            if left <= 0:
                break
        new: List[Dict[str, Any]] = []
        for x in roll.get("length_reservations") or []:
            c = cut.get(x.get("id"))
            if c is None:
                new.append(x)
                continue
            rest = round(float(x.get("qty") or 0) - c, 2)
            if rest > LOCK_EPS:
                new.append({**x, "qty": rest})
        res = await db.inventory_rolls.update_one(
            {"id": roll_id, "length_reservations": roll.get("length_reservations") or []},
            {"$set": {"length_reservations": new,
                      "length_reserved": round(sum(float(x.get("qty") or 0) for x in new), 2),
                      "updated_at": now_iso()}})
        if res.modified_count:
            roll["length_reservations"] = new
            return round(sum(cut.values()), 2), roll
        await asyncio.sleep(0.01)
    raise RuntimeError(f"Roll {roll_id} terus berubah saat kunci makloon dilepas — coba lagi.")


async def _get(res_or_id: Any) -> Optional[Dict[str, Any]]:
    rid = res_or_id if isinstance(res_or_id, str) else (res_or_id or {}).get("id")
    return await db.material_reservations.find_one({"id": rid}, {"_id": 0, "history": 0}) if rid else None


async def source_warehouse(res: Dict[str, Any], save: bool = True) -> str:
    """Gudang sumber cadangan. Cadangan lama (lahir sebelum FIX-9) belum menyimpannya → diturunkan dari dokumennya:
    MKO `from_warehouse_id`/langkah 1, PR `warehouse_id` (`save` = simpan ke cadangan)."""
    if res.get("source_warehouse_id"):
        return res["source_warehouse_id"]
    src = ""
    if res.get("mko_id") or res.get("ref_type") == "makloon_order":
        from services.material_reservation_service import mko_source_warehouse
        mko = await db.makloon_orders.find_one({"id": res.get("mko_id") or res.get("ref_id")},
                                               {"_id": 0, "from_warehouse_id": 1, "steps": 1})
        src = mko_source_warehouse(mko or {})
    elif res.get("pr_id"):
        pr = await db.purchase_requisitions.find_one({"id": res["pr_id"]}, {"_id": 0, "warehouse_id": 1})
        src = (pr or {}).get("warehouse_id") or ""
    if src and save:
        await db.material_reservations.update_one({"id": res["id"]}, {"$set": {"source_warehouse_id": src}})
    return src


async def lock(res_or_id: Any, actor: str = "Sistem", reason: str = "") -> Dict[str, Any]:
    """Kunci cadangan AKTIF ke roll sampai `locked_qty = qty` (isi kekurangan saja → idempoten). Stok kurang → kunci
    sebanyak yang ada; sisanya tetap 'cadangan belum terkunci'. → {locked_qty, newly_locked, unlocked_qty, rolls}."""
    res = await _get(res_or_id)
    if not res or res.get("status") != "active":
        return {"locked_qty": 0.0, "newly_locked": 0.0, "unlocked_qty": 0.0, "rolls": []}
    async with _Mutex(res["id"]):
        res = await _get(res["id"])
        if not res or res.get("status") != "active":
            return {"locked_qty": 0.0, "newly_locked": 0.0, "unlocked_qty": 0.0, "rolls": []}
        have = round(sum(x["qty"] for x in await actual_locks(res["id"])), 2)
        need = round(float(res.get("qty") or 0) - have, 2)
        src = await source_warehouse(res) if need > LOCK_EPS else (res.get("source_warehouse_id") or "")
        res["source_warehouse_id"] = src
        got = await _lock_more(res, need, src) if need > LOCK_EPS else []
        await _rebuild(x["seg"] for x in got)
        st = await sync(res["id"])
        newly = round(sum(x["qty"] for x in got), 2)
        unlocked = round(max(float(res.get("qty") or 0) - st["locked_qty"], 0.0), 3)
        if newly > 0:
            await _trail(res, "locked", newly, got, actor, reason)
        # kekurangan dicatat sekali per angka (isi ulang berkala yang tetap kurang tidak membanjiri riwayat/audit)
        if unlocked > LOCK_EPS and need > LOCK_EPS                 and abs(unlocked - float(res.get("lock_shortage_qty") if res.get("lock_shortage_qty") is not None
                                         else -1)) > LOCK_EPS:
            await _trail(res, "lock_shortage", unlocked, [], actor,
                         reason or "stok roll bebas tidak cukup — sisa tetap cadangan belum terkunci",
                         source_warehouse_id=res.get("source_warehouse_id") or "")
        await db.material_reservations.update_one({"id": res["id"]}, {"$set": {"lock_shortage_qty": unlocked}})
        return {"locked_qty": st["locked_qty"], "newly_locked": newly, "unlocked_qty": unlocked, "rolls": got}


async def unlock(res_or_id: Any, actor: str = "Sistem", reason: str = "", qty: Optional[float] = None,
                 event: str = "unlocked", roll_ids: Optional[List[str]] = None,
                 outside_wh: str = "", **extra: Any) -> float:
    """Lepas kunci cadangan (semua, atau sebagian `qty` — kunci TERBARU dilepas dulu). `roll_ids` membatasi roll;
    `outside_wh` hanya roll di luar gudang itu. Idempoten (tidak ada kunci = 0)."""
    res = await _get(res_or_id)
    if not res:
        return 0.0
    async with _Mutex(res["id"]):
        rows = []
        q: Dict[str, Any] = {"length_reservations.ref.id": res["id"]}
        if roll_ids is not None:
            q["id"] = {"$in": list(roll_ids)}
        if outside_wh:
            q["warehouse_id"] = {"$ne": outside_wh}
        async for r in db.inventory_rolls.find(q, ROLL_PROJ):
            last = max([str(x.get("created_at") or "") for x in roll_locks(r, [res["id"]])] or [""])
            rows.append((last, r))
        rows.sort(key=lambda t: t[0], reverse=True)       # kunci terbaru dulu (LIFO)
        left = None if qty is None else round(float(qty), 2)
        freed: List[Dict[str, Any]] = []
        segs = set()
        for _last, r in rows:
            if left is not None and left <= LOCK_EPS:
                break
            got, after = await _unlock_roll(r["id"], [res["id"]], left)
            if got <= 0:
                continue
            freed.append({"roll_id": r["id"], "roll_no": r.get("roll_no") or "", "qty": got})
            segs.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
            if left is not None:
                left = round(left - got, 2)
        await _rebuild(segs)
        await sync(res["id"])
        total = round(sum(x["qty"] for x in freed), 2)
        await _trail(res, event, total, freed, actor, reason, **extra)
        return total


async def trim(res_or_id: Any, actor: str = "Sistem", reason: str = "") -> float:
    """Kunci melebihi cadangan yang tersisa (sesudah issue/konsumsi, atau cadangan tidak aktif) → lepas kelebihannya."""
    res = await _get(res_or_id)
    if not res:
        return 0.0
    have = round(sum(x["qty"] for x in await actual_locks(res["id"])), 2)
    keep = float(res.get("qty") or 0) if res.get("status") == "active" else 0.0
    excess = round(have - keep, 2)
    if excess <= LOCK_EPS:
        if have > 0 or res.get("locked_qty"):
            await sync(res["id"])
        return 0.0
    return await unlock(res, actor, reason or "kunci melebihi sisa cadangan dilepas", qty=excess, event="trimmed")


async def relock_to_source(res_or_id: Any, actor: str = "Sistem", reason: str = "") -> Dict[str, Any]:
    """Gudang sumber cadangan berubah (PR → MKO): kunci di gudang lain DIPINDAH ke gudang sumber sebanyak panjang
    bebas yang ada di sana (kunci baru dulu, baru kunci lama dilepas — tidak pernah ada celah tanpa kunci)."""
    res = await _get(res_or_id)
    src = (res or {}).get("source_warehouse_id") or ""
    if not res or res.get("status") != "active" or not src:
        return {"moved": 0.0}
    async with _Mutex(res["id"]):
        locks = await actual_locks(res["id"])
        elsewhere = round(sum(x["qty"] for x in locks if x["warehouse_id"] != src), 2)
        got = await _lock_more(res, elsewhere, src) if elsewhere > LOCK_EPS else []
        await _rebuild(x["seg"] for x in got)
    moved = round(sum(x["qty"] for x in got), 2)
    if moved > 0:
        await _trail(res, "locked", moved, got, actor, reason or "pindah ke gudang sumber MKO")
        await unlock(res, actor, reason or "pindah ke gudang sumber MKO", qty=moved, outside_wh=src)
    # sisa kekurangan (bila ada) diisi dari gudang sumber
    out = await lock(res["id"], actor, reason)
    return {"moved": moved, **out}


async def update_refs(res_or_id: Any) -> int:
    """Perbarui `ref` kunci di roll (nomor MKO sesudah PR direalisasi)."""
    res = await _get(res_or_id)
    if not res:
        return 0
    ref = lock_ref(res)
    r = await db.inventory_rolls.update_many(
        {"length_reservations.ref.id": res["id"]},
        {"$set": {f"length_reservations.$[x].ref.{k}": v for k, v in ref.items() if k not in ("type", "id")}},
        array_filters=[{"x.ref.id": res["id"]}])
    return r.modified_count


async def borrow_for_order(product_id: str, entity_id: str, need: float, order_id: str, actor: str = "Sistem",
                           roll_ids: Optional[List[str]] = None, order_number: str = "") -> float:
    """Mode `allocation.makloon_reserve_mode = approve` + persetujuan manajer: pesanan BOLEH memakai stok cadangan
    makloon → kunci DIPINJAM (dilepas) sebanyak `need` (kunci terbaru dulu; `roll_ids` = roll yang dipilih sales).
    Cadangan tetap (sisanya jadi 'belum terkunci'), sehingga angka stok tetap mengurangkannya dan persetujuan
    "makloon" pada pesanan menjadi jejaknya."""
    need = round(float(need or 0), 2)
    if need <= LOCK_EPS:
        return 0.0
    q: Dict[str, Any] = {"product_id": product_id, "owner_entity_id": entity_id,
                         "length_reservations.ref.type": LOCK_TYPE}
    if roll_ids is not None:
        q["id"] = {"$in": list(roll_ids)}
    per_res: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    async for r in db.inventory_rolls.find(q, ROLL_PROJ):
        for x in roll_locks(r):
            per_res.setdefault(x["ref"]["id"], []).append((str(x.get("created_at") or ""), r))
    order = sorted(per_res, key=lambda rid: max(t for t, _r in per_res[rid]), reverse=True)
    left = need
    for rid in order:
        if left <= LOCK_EPS:
            break
        ids = sorted({r["id"] for _t, r in per_res[rid]})
        got = await unlock(rid, actor, f"dipinjam pesanan {order_number or order_id} (persetujuan manajer)",
                           qty=left, event="borrowed", roll_ids=ids, order_id=order_id)
        left = round(left - got, 2)
    return round(need - max(left, 0.0), 2)


async def orphan_locks(fix: bool = False, actor: str = "Sistem",
                       only: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Kunci makloon di roll yang cadangannya tidak aktif lagi (proses mati di tengah) — dilaporkan / dilepas."""
    out: List[Dict[str, Any]] = []
    ids: Dict[str, List[Dict[str, Any]]] = {}
    q: Dict[str, Any] = {"length_reservations.ref.type": LOCK_TYPE}
    if only:
        q["length_reservations.ref.id"] = {"$in": list(only)}
    async for r in db.inventory_rolls.find(q, ROLL_PROJ):
        for x in roll_locks(r, only):
            ids.setdefault(x["ref"]["id"], []).append(r)
    if not ids:
        return out
    live = {m["id"] async for m in db.material_reservations.find(
        {"id": {"$in": list(ids)}, "status": "active"}, {"_id": 0, "id": 1})}
    for rid, rolls in ids.items():
        if rid in live:
            continue
        qty = round(sum(roll_locked_qty(r, [rid]) for r in rolls), 2)
        out.append({"reservation_id": rid, "qty": qty, "rolls": sorted({r.get("roll_no") or r["id"] for r in rolls})})
        if fix:
            if await db.material_reservations.find_one({"id": rid}, {"_id": 1}):
                await unlock(rid, actor, "kunci yatim (cadangan tidak aktif) dilepas")
            else:
                segs = set()
                for r in rolls:
                    got, _after = await _unlock_roll(r["id"], [rid])
                    if got > 0:
                        segs.add((r["product_id"], r["warehouse_id"], r["owner_entity_id"]))
                await _rebuild(segs)
    return out
