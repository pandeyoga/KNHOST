"""P09 — SATU evaluator gate (ingest perangkat, simulator, kiosk). Keputusan berbasis MOVEMENT aktif
(PA / transfer gudang / surat jalan SO / Order Makloon / Perbaikan) yang memuat roll, bukan status roll semata.
Makloon & perbaikan: `gate_doc_movements` (roll `subcon` ber-`bucket_ref` langkah MKO · roll `wip` ber-`repair_open`).

Hasil: {result green|red|info, code, reason, movement?}. Tidak ada fallback hijau: dokumen hilang,
status tidak aktif, gudang salah, roll bukan anggota manifest, atau keluar ulang → MERAH + kode.

PREP-H — `GateLookup` (opsional, `ctx=`): memo baca dokumen untuk penilaian SATU lintasan V2 (hapus N+1 —
beberapa query per roll menjadi satu `$in` per jenis dokumen). Tanpa `ctx` (jalur lama ingest/kiosk/simulator)
perilaku & query persis seperti sebelumnya.
"""
import hashlib
import json
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db import db
from services import gate_doc_movements as _docs

SHIPMENT_ACTIVE = {"dispatched", "in_transit", "partially_shipped"}
SO_DEAD = {"cancelled", "void", "rejected"}

# Proyeksi = gabungan proyeksi asli tiap pemakai (resolve_movement / gate_doc_movements) + `id` sebagai kunci memo.
_PROJ = {
    "putaway_orders": {"_id": 0, "id": 1, "pa_number": 1, "status": 1, "from_warehouse_id": 1, "to_warehouse_id": 1,
                       "items.roll_id": 1},
    "warehouse_transfers": {"_id": 0, "id": 1, "code": 1, "status": 1, "items.rolls.roll_id": 1,
                            "source_warehouse_id": 1, "dest_warehouse_id": 1},
    "sales_orders": {"_id": 0, "id": 1, "number": 1, "status": 1},
    "makloon_orders": {"_id": 0, "id": 1, "mko_number": 1, "status": 1, "steps": 1},
    "repair_orders": {"_id": 0, "id": 1, "number": 1, "status": 1, "lines": 1, "partner_name": 1},
}
_SHIPMENT_FIELDS = ("id", "shipment_no", "status", "warehouse_id")


def claim_key(source_type: str, source_id: str, direction: str, roll_id: str) -> str:
    """`_id` klaim crossing V2 (sama dengan `rfid_v2_sessions.claim_id`)."""
    return hashlib.sha256(json.dumps([source_type, source_id, direction, roll_id], sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def _linked_transfer(roll: Dict[str, Any], ref: Dict[str, Any]) -> bool:
    physical = roll.get("transfer_ref") or {}
    return (roll.get("status") == "in_transit_transfer" and ref.get("type") == "sales_order"
            and physical.get("type") == "wh_transfer" and physical.get("so_id") == ref["id"])


class GateLookup:
    """PREP-H — memo baca untuk penilaian satu lintasan (umur = satu panggilan `rfid_v2_policy.decide`).

    BUKAN cache lintas permintaan (tidak ada SSOT kedua): dibuat baru setiap close, diisi sekali per jenis dokumen
    dengan `$in` (`warm`, `warm_claims`), lalu `resolve_movement`/`evaluate` membaca dari memo. Query & proyeksi sama
    dengan jalur tanpa memo; dokumen yang tidak ter-`warm` dibaca langsung lalu disimpan (hasil tetap identik).
    Potret diambil sekali di awal penilaian — klaim crossing tetap dicek ulang atomik saat disisipkan
    (`rfid_v2_sessions.insert_claims`), sama seperti sebelumnya.
    """

    def __init__(self) -> None:
        self._docs: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}
        self._shipments: Dict[Tuple[str, str], Optional[Dict[str, Any]]] = {}
        self._claims: Dict[str, Optional[Dict[str, Any]]] = {}
        self._movements: Dict[str, Optional[Dict[str, Any]]] = {}
        self._members: Dict[Tuple[str, Any], set] = {}
        self.queries = 0

    async def _bulk(self, coll: str, ids: Iterable[Any]) -> None:
        want = [i for i in set(ids) if isinstance(i, str) and i and (coll, i) not in self._docs]
        for start in range(0, len(want), 1000):
            part = want[start:start + 1000]
            self.queries += 1
            rows = await db[coll].find({"id": {"$in": part}}, _PROJ[coll]).to_list(len(part) * 2 + 10)
            for row in rows:
                self._docs.setdefault((coll, row.get("id")), row)
            for i in part:
                self._docs.setdefault((coll, i), None)

    async def one(self, coll: str, doc_id: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(doc_id, str) or not doc_id:   # id kosong/aneh: query asli apa adanya, tanpa memo
            self.queries += 1
            return await db[coll].find_one({"id": doc_id}, _PROJ[coll])
        if (coll, doc_id) not in self._docs:
            self.queries += 1
            self._docs[(coll, doc_id)] = await db[coll].find_one({"id": doc_id}, _PROJ[coll])
        return self._docs[(coll, doc_id)]

    def members(self, coll: str, doc_id: Any, doc: Dict[str, Any]) -> set:
        """Himpunan roll anggota dokumen, dibangun SEKALI per dokumen (dulu per roll: O(roll²) untuk muatan besar)."""
        key = (coll, doc_id)
        if key not in self._members:
            if coll == "putaway_orders":
                self._members[key] = {i.get("roll_id") for i in doc.get("items") or []}
            else:
                self._members[key] = {r.get("roll_id") for i in doc.get("items", []) for r in i.get("rolls", [])}
        return self._members[key]

    async def shipment(self, order_id: str, roll_id: str) -> Optional[Dict[str, Any]]:
        key = (order_id, roll_id)
        if key not in self._shipments:
            self.queries += 1
            self._shipments[key] = await db.shipments.find_one(
                {"order_id": order_id, "rolls.roll_id": roll_id},
                {"_id": 0, **{k: 1 for k in _SHIPMENT_FIELDS}}, sort=[("created_at", -1)])
        return self._shipments[key]

    async def _bulk_shipments(self, pairs: List[Tuple[str, str]]) -> None:
        want = [p for p in set(pairs) if p not in self._shipments and all(isinstance(x, str) and x for x in p)]
        if not want:
            return
        orders = sorted({o for o, _ in want})
        rolls = sorted({r for _, r in want})
        wanted = set(want)
        self.queries += 1
        rows = await db.shipments.find({"order_id": {"$in": orders}, "rolls.roll_id": {"$in": rolls}},
                                       {"_id": 0, "order_id": 1, "rolls.roll_id": 1, **{k: 1 for k in _SHIPMENT_FIELDS}}
                                       ).sort("created_at", -1).to_list(None)
        for row in rows:   # urutan created_at menurun = find_one(sort created_at -1) per (SO, roll)
            for r in row.get("rolls") or []:
                key = (row.get("order_id"), r.get("roll_id"))
                if key in wanted and key not in self._shipments:
                    self._shipments[key] = {k: row[k] for k in _SHIPMENT_FIELDS if k in row}
        for key in want:
            self._shipments.setdefault(key, None)

    async def warm(self, rolls: Iterable[Dict[str, Any]]) -> None:
        """Isi memo dokumen untuk semua roll lintasan: satu `$in` per jenis dokumen."""
        ids: Dict[str, set] = {c: set() for c in _PROJ}
        pairs: List[Tuple[str, str]] = []
        for roll in rolls:
            am = roll.get("active_movement") or {}
            pa_id = am.get("id") if am.get("type") == "putaway" else (roll.get("journey") or {}).get("putaway_order_id")
            if pa_id:
                ids["putaway_orders"].add(pa_id)
            br = roll.get("bucket_ref") or {}
            if roll.get("status") == "subcon" and isinstance(br, dict) and br.get("type") == "subcon" and br.get("mko_id"):
                ids["makloon_orders"].add(br["mko_id"])
            if roll.get("repair_open"):
                ids["repair_orders"].add(roll["repair_open"])
            ref = roll.get("reserved_ref") or {}
            if not isinstance(ref, dict) or not ref.get("id"):
                continue
            linked = _linked_transfer(roll, ref)
            if ref.get("type") == "wh_transfer" or linked:
                ids["warehouse_transfers"].add((roll.get("transfer_ref") or {}).get("id") if linked else ref["id"])
                if linked:
                    ids["sales_orders"].add(ref["id"])
            elif ref.get("type") == "sales_order":
                ids["sales_orders"].add(ref["id"])
                pairs.append((ref["id"], roll.get("id")))
        for coll, wanted in ids.items():
            if wanted:
                await self._bulk(coll, wanted)
        await self._bulk_shipments(pairs)

    async def movement(self, roll: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        rid = roll.get("id")
        if rid not in self._movements:
            self._movements[rid] = await resolve_movement(roll, ctx=self)
        return self._movements[rid]

    async def warm_claims(self, rolls: Iterable[Dict[str, Any]], direction: str) -> None:
        keys = []
        for roll in rolls:
            key = _claim_key_for(await self.movement(roll), direction, roll)
            if key and key not in self._claims:
                keys.append(key)
        for start in range(0, len(keys), 1000):
            part = keys[start:start + 1000]
            self.queries += 1
            found = {c["_id"]: c for c in await db.rfid_v2_crossings.find({"_id": {"$in": part}}, {"passage": 1}).to_list(len(part))}
            for k in part:
                self._claims[k] = found.get(k)

    async def claim(self, key: str) -> Optional[Dict[str, Any]]:
        if key not in self._claims:
            self.queries += 1
            self._claims[key] = await db.rfid_v2_crossings.find_one({"_id": key})
        return self._claims[key]


def _claim_key_for(mv: Optional[Dict[str, Any]], direction: str, roll: Dict[str, Any]) -> Optional[str]:
    if not mv or mv.get("missing"):
        return None
    source_type = "shipment" if mv["type"] == "sales_order" else mv["type"]
    source_id = (mv.get("shipment") or {}).get("id") if source_type == "shipment" else mv.get("id")
    return claim_key(source_type, source_id, direction, roll["id"]) if source_id else None


# Saran tindakan untuk satpam per kode alasan (bahasa lapangan, satu kalimat).
ACTIONS = {
    "MOVEMENT_OUT": "Loloskan — cocokkan jumlah roll dengan surat jalan.",
    "MOVEMENT_IN": "Terima — arahkan ke area bongkar/putaway.",
    "LOCAL_ROLL": "Tidak perlu tindakan — roll milik gudang ini.",
    "INVENTORY": "Tidak perlu tindakan.",
    "NO_DOCUMENT": "Tahan barang — minta surat jalan / dokumen keluar ke admin gudang.",
    "DOC_MISSING": "Tahan barang — panggil supervisor, dokumen di sistem tidak ditemukan.",
    "NOT_RELEASED": "Tahan barang — minta admin gudang menyelesaikan dispatch di sistem dulu.",
    "NOT_IN_MANIFEST": "Tahan roll ini — tidak ada di surat jalan; cocokkan ulang muatan dengan checker.",
    "WRONG_WAREHOUSE": "Tahan barang — dokumen untuk gudang lain; panggil supervisor.",
    "WRONG_DESTINATION": "Tolak bongkar — barang untuk gudang lain; hubungi pengirim/supervisor.",
    "MOVEMENT_NOT_ACTIVE": "Tahan — dokumen belum dikirim di sistem; hubungi admin gudang asal.",
    "SO_CANCELLED": "Tahan barang — pesanan dibatalkan; kembalikan ke gudang & lapor supervisor.",
    "DOC_CANCELLED": "Tahan barang — dokumen keluarnya sudah dibatalkan; kembalikan ke gudang & lapor supervisor.",
    "ALREADY_OUT": "Tahan & panggil supervisor — roll tercatat sudah keluar/habis.",
    "REPLAY_EXIT": "Tahan & panggil supervisor — roll sudah pernah keluar dengan dokumen ini.",
    "QUARANTINE": "Tahan barang — roll karantina QC; kembalikan ke area karantina.",
    "SALES_TRANSIT_NOT_INBOUND": "Tolak bongkar — barang kiriman pelanggan; minta dokumen retur.",
    "UNKNOWN_EPC": "Tahan barang — tag tidak dikenal; panggil supervisor untuk cek fisik.",
}


def action_for(code: Optional[str]) -> str:
    return ACTIONS.get(code or "", "Tahan & panggil supervisor.")


def _v(result: str, code: str, reason: str, mv: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {"result": result, "code": code, "reason": reason, "action": action_for(code)}
    if mv:
        out["movement"] = {k: mv.get(k) for k in ("type", "id", "number", "source_wh", "dest_wh")}
    return out


async def resolve_movement(roll: Dict[str, Any], ctx: Optional[GateLookup] = None) -> Optional[Dict[str, Any]]:
    """Movement aktif yang memuat roll: {type, id, number, status, active, source_wh, dest_wh, member}.

    `ctx` (PREP-H) = memo satu lintasan; tanpa `ctx` query langsung seperti semula."""
    am = roll.get("active_movement") or {}
    pa_id = am.get("id") if am.get("type") == "putaway" else (roll.get("journey") or {}).get("putaway_order_id")
    if pa_id:
        pa = await ctx.one("putaway_orders", pa_id) if ctx else await db.putaway_orders.find_one(
            {"id": pa_id}, {"_id": 0, "pa_number": 1, "status": 1, "from_warehouse_id": 1, "to_warehouse_id": 1,
                            "items.roll_id": 1})
        # PREP-D2 — PA tiba sebagian (PREP-C, trip per lintasan) tetap movement aktif untuk roll yang belum tiba.
        if pa and pa.get("status") in ("open", "in_transit", "partially_received"):
            members = ctx.members("putaway_orders", pa_id, pa) if ctx else {i.get("roll_id") for i in pa.get("items") or []}
            return {"type": "putaway", "id": pa_id, "number": pa.get("pa_number"), "status": pa["status"],
                    "active": pa["status"] in ("in_transit", "partially_received"), "source_wh": pa.get("from_warehouse_id"),
                    "dest_wh": pa.get("to_warehouse_id"),
                    "member": roll["id"] in members}
    doc_mv = await _docs.doc_movement(roll, ctx)   # Order Makloon (roll di mitra) / Perbaikan (roll wip)
    if doc_mv:
        return doc_mv
    ref = roll.get("reserved_ref") or {}
    if not isinstance(ref, dict) or not ref.get("id"):
        return None
    physical = roll.get("transfer_ref") or {}
    linked = _linked_transfer(roll, ref)
    if ref.get("type") == "wh_transfer" or linked:
        transfer_id = physical.get("id") if linked else ref["id"]
        tr = await ctx.one("warehouse_transfers", transfer_id) if ctx else await db.warehouse_transfers.find_one(
            {"id": transfer_id}, {"_id": 0, "code": 1, "status": 1, "items.rolls.roll_id": 1, "source_warehouse_id": 1,
                                  "dest_warehouse_id": 1})
        if not tr:
            return {"type": "wh_transfer", "id": transfer_id, "missing": True}
        if not linked:
            committed_so = None
        elif ctx:
            committed_so = await ctx.one("sales_orders", ref["id"])
        else:
            committed_so = await db.sales_orders.find_one({"id": ref["id"]}, {"_id": 0, "status": 1})
        commitment_valid = not linked or bool(committed_so and committed_so.get("status") not in SO_DEAD | {"closed", "completed", "delivered"})
        members = ctx.members("warehouse_transfers", transfer_id, tr) if ctx else \
            {r.get("roll_id") for i in tr.get("items", []) for r in i.get("rolls", [])}
        return {"type": "wh_transfer", "id": transfer_id, "number": tr.get("code"), "status": tr.get("status"),
                "active": tr.get("status") in ("dispatched", "partially_received")   # PREP-D2 — terima bertahap
                and roll.get("status") == "in_transit_transfer" and commitment_valid,
                "source_wh": tr.get("source_warehouse_id"), "dest_wh": tr.get("dest_warehouse_id"),
                "member": roll["id"] in members}
    if ref.get("type") == "sales_order":
        so = await ctx.one("sales_orders", ref["id"]) if ctx else await db.sales_orders.find_one(
            {"id": ref["id"]}, {"_id": 0, "number": 1, "status": 1})
        if not so:
            return {"type": "sales_order", "id": ref["id"], "missing": True}
        shp = await ctx.shipment(ref["id"], roll["id"]) if ctx else await db.shipments.find_one(
            {"order_id": ref["id"], "rolls.roll_id": roll["id"]},
            {"_id": 0, "id": 1, "shipment_no": 1, "status": 1, "warehouse_id": 1}, sort=[("created_at", -1)])
        return {"type": "sales_order", "id": ref["id"], "number": so.get("number"), "status": so.get("status"),
                "so_dead": so.get("status") in SO_DEAD, "shipment": shp,
                "active": bool(shp and shp.get("status") in SHIPMENT_ACTIVE and roll.get("status") == "in_transit_sales"),
                "source_wh": (shp or {}).get("warehouse_id") or roll.get("warehouse_id"), "dest_wh": None,
                "member": bool(shp)}
    return None


async def evaluate(direction: str, warehouse_id: Optional[str], roll: Dict[str, Any], crossing_passage_id: Optional[str] = None,
                   expected_source: Optional[Dict[str, Any]] = None, ctx: Optional[GateLookup] = None) -> Dict[str, Any]:
    status = roll.get("status", "?")
    mv = await ctx.movement(roll) if ctx else await resolve_movement(roll)
    if expected_source:
        actual_type = 'shipment' if mv and mv.get('type') == 'sales_order' else (mv or {}).get('type')
        actual_id = ((mv or {}).get('shipment') or {}).get('id') if actual_type == 'shipment' else (mv or {}).get('id')
        if (actual_type, actual_id) != (expected_source.get('source_type'), expected_source.get('source_id')):
            return _v('red', 'SOURCE_CONTEXT_MISMATCH', 'Pergerakan aktif roll berbeda dari dokumen yang dipilih pada gate.', mv)
    # V2 crossing claims also apply to the legacy ingest/simulator/kiosk paths.
    # The caller resuming the SAME durable V2 close may reuse its own claim.
    claim_id = _claim_key_for(mv, direction, roll)
    if claim_id:
        claim = await ctx.claim(claim_id) if ctx else await db.rfid_v2_crossings.find_one({"_id": claim_id})
        if claim and claim.get("passage") != crossing_passage_id:
            return _v("red", "REPLAY_EXIT", "Roll sudah divalidasi pada lintasan V2 untuk dokumen dan arah ini.", mv)
    if mv and mv.get("missing"):
        return _v("red", "DOC_MISSING", f"Dokumen {mv['type']} {mv['id']} tidak ditemukan — exception, cek manual.")
    if direction == "in":
        if status == "in_transit_sales":
            return _v("red", "SALES_TRANSIT_NOT_INBOUND", "Roll dalam pengiriman penjualan — bukan transfer internal ke gudang ini.", mv)
        if mv and mv["type"] in ("makloon_order", "repair_order"):
            back = _docs.evaluate_in(mv, warehouse_id)   # kembali dari perbaikan / bahan MKO batal
            if back:
                return _v(*back, mv)
        if mv and mv["type"] in ("putaway", "wh_transfer"):
            if mv.get("dest_wh") != warehouse_id:
                return _v("red", "WRONG_DESTINATION", f"SALAH GUDANG — {mv.get('number')} menuju gudang lain, bukan gudang ini.", mv)
            if not mv.get("active") or not mv.get("member"):
                return _v("red", "MOVEMENT_NOT_ACTIVE", f"{mv.get('number')} belum dikirim / roll bukan anggota dokumen.", mv)
            return _v("green", "MOVEMENT_IN", f"Sesuai {mv.get('number')} — tujuan gudang ini.", mv)
        if status == "in_transit_transfer":
            return _v("red", "DOC_MISSING", "Roll transit tanpa dokumen tujuan yang aktif — exception.")
        if roll.get("warehouse_id") == warehouse_id:
            return _v("info", "LOCAL_ROLL", "Roll milik gudang ini terbaca di gate masuk.")
        return _v("red", "NO_DOCUMENT", "Tidak ada dokumen tujuan (PA/transfer) ke gudang ini.")

    # OUT
    if status == "quarantine":
        return _v("red", "QUARANTINE", "Roll KARANTINA (QC hold) — dilarang keluar.")
    if status in ("delivered", "consumed"):
        return _v("red", "ALREADY_OUT", f"Roll berstatus {status} — tidak boleh keluar lagi.")
    passed = roll.get("gate_exit") or {}
    if mv and passed.get("movement_id") == mv.get("id"):
        return _v("red", "REPLAY_EXIT", f"Roll sudah keluar untuk {mv.get('number')} ({passed.get('at')}) — keluar ulang ditahan.", mv)
    if not mv:
        if status == "available":
            return _v("red", "NO_DOCUMENT", "Roll masih AVAILABLE — tidak ada dokumen keluar (SO/transfer/PA). Keluar tak sah.")
        return _v("red", "NO_DOCUMENT", f"Status {status} tanpa dokumen keluar aktif — keluar tak sah.")
    if mv["type"] == "sales_order" and mv.get("so_dead"):
        return _v("red", "SO_CANCELLED", f"SO {mv.get('number')} berstatus {mv.get('status')} — keluar ditahan.", mv)
    if mv.get("cancelled"):
        return _v("red", "DOC_CANCELLED", f"{mv.get('number')} sudah DIBATALKAN — barang tidak boleh keluar atas dokumen ini.", mv)
    if mv.get("source_wh") != warehouse_id:
        return _v("red", "WRONG_WAREHOUSE", f"{mv.get('number')} berangkat dari gudang lain, bukan gudang ini.", mv)
    if not mv.get("member"):
        return _v("red", "NOT_IN_MANIFEST", f"Roll tidak tercantum di surat jalan/dokumen {mv.get('number')}.", mv)
    if not mv.get("active"):
        return _v("red", "NOT_RELEASED", mv.get("inactive_reason")
                  or f"{mv.get('number')} belum di-dispatch di sistem (status {status}) — tahan.", mv)
    to = f" → {mv['partner']}" if mv.get("partner") and mv["type"] in ("makloon_order", "repair_order") else ""
    return _v("green", "MOVEMENT_OUT", f"Keluar ter-otorisasi untuk {mv.get('number')}{to}.", mv)


async def stamp_exit(roll_id: str, decision: Dict[str, Any], device: Dict[str, Any], at: str) -> None:
    """Gate-out hijau dicatat di roll → pembacaan keluar berikutnya untuk movement yang sama = REPLAY_EXIT."""
    mv = decision.get("movement") or {}
    if decision.get("result") == "green" and decision.get("code") == "MOVEMENT_OUT" and mv.get("id"):
        await db.inventory_rolls.update_one({"id": roll_id}, {"$set": {"gate_exit": {
            "movement_id": mv["id"], "device_id": device["id"], "at": at}}})
