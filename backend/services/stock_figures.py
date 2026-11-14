"""FIX-2 (audit 9 Nov 2026 — B3a STK-1…14/SSOT-4/DUP-1…4, B1 UI-06/07/40) — SATU layanan angka stok.

Keinginan pemilik: "user bisa melihat jelas stok dari semua bahkan multi entitas sampai barang yang akan datang, tetapi
banyaknya angka membuat pusing — angka lain muncul ketika lihat detail". Maka setiap layar menampilkan DUA angka
(LOKAL + GLOBAL), dan rinciannya dibuka saat diklik. Semua endpoint yang mengeluarkan kuantitas stok mengambil angka
dari modul ini (langsung atau lewat pembungkus lama `stock_availability`), FE hanya MENAMPILKAN.

DEFINISI (tabel lengkap: docs/audit/2026-11-09-wms-rfid/hasil/FIX-2-ANGKA-STOK.md §2)
-----------------------------------------------------------------------------------
* Gudang yang dihitung   = gudang master `active != false` dan tidak ditandai data uji (`is_test: true`).
                           Saldo yatim (gudang tak terdaftar) tidak pernah ikut.
* Tersedia (K-04)        = Σ panjang roll status `available` yang tidak diklaim perpindahan (PA), dikurangi panjang
                           yang dipesan untuk potong & reservasi — yaitu ember `available_qty` saldo yang DIBANGUN
                           ULANG DARI ROLL (`roll_service.rebuild_balance`; tahan QC/karantina/blokir/hold/MD Quality
                           = status ≠ available, jadi otomatis keluar) — DIKURANGI cadangan bahan makloon aktif
                           (`material_reservations`). Cadangan makloon per produk×PT dialokasikan ke gudang PT itu
                           dengan SATU aturan: gudang bertersedia terbesar dulu (aturan lama `deduct_makloon`).
* Roll tersedia          = jumlah roll yang masih punya panjang bebas (saldo `roll_count`). Cadangan makloon belum
                           dikunci per roll, jadi jumlah roll tidak dikurangi cadangan (dicatat: langkah lanjut).
* LOKAL                  = Tersedia di cakupan kerja pengguna: PT aktif (mode gabungan: semua PT yang diizinkan) ∩
                           site kerja (sales: site POS tersimpan di server; gudang: lokasi tugas; selain itu: semua site,
                           atau `?site_id=`). Titik kait FIX-1: `location_scope.work_site_ids(user)` bila tersedia.
* GLOBAL                 = Tersedia benar-benar total: semua PT & semua gudang yang dihitung (agregat angka saja untuk
                           PT di luar izin — keputusan B3a #7).
* Satuan                 = satuan dasar produk; tidak pernah dijumlah lintas satuan. Urutan tampil: roll lalu panjang.
"""
from typing import Any, Dict, Iterable, List, Optional, Set

from db import db
from core_utils import DEFAULT_ENTITY_ID

EPS = 0.001

# Ember saldo → kelompok tampilan (nama dari KN_32). Ember fisik tetap mengikuti `roll_service.PHYSICAL_STATUS_TO_BUCKET`.
STATUS_GROUPS: List[Dict[str, Any]] = [
    {"key": "available", "label": "Tersedia", "buckets": ("available_qty",),
     "hint": "Roll siap jual dikurangi panjang dipesan potong, reservasi, dan cadangan makloon (K-04)."},
    {"key": "makloon", "label": "Cadangan makloon", "buckets": (),
     "hint": "Bahan yang dicadangkan untuk order makloon — fisik ada, tidak boleh dijual."},
    {"key": "reserved", "label": "Dipesan", "buckets": ("reserved_qty",),
     "hint": "Dikunci pesanan (termasuk panjang yang dipesan untuk dipotong)."},
    {"key": "committed", "label": "Dialokasikan", "buckets": ("committed_qty", "picked_qty", "packed_qty"),
     "hint": "Sudah dialokasikan, diambil, atau dikemas untuk pesanan."},
    {"key": "hold", "label": "Ditahan / QC", "buckets": ("quarantine_qty", "blocked_qty", "hold_qty", "damaged_qty"),
     "hint": "Karantina, diblokir (termasuk tahan QC & MD Quality), ditahan, rusak, atau sedang dipindah (PA)."},
    {"key": "wip", "label": "Dalam proses", "buckets": ("wip_qty",),
     "hint": "Sedang diproses/dipotong di gudang."},
    {"key": "subcon", "label": "Di makloon", "buckets": ("subcon_qty",),
     "hint": "Milik sendiri, fisik sedang di mitra makloon."},
    {"key": "in_transit", "label": "Dalam Perjalanan",
     "buckets": ("in_transit_transfer_qty", "in_transit_intercompany_qty", "in_transit_inbound_qty"),
     "hint": "Transfer antar gudang (angka di gudang ASAL; gudang tujuan tampil di 'Akan datang'), antar-PT, dan "
             "barang masuk yang sudah jadi roll."},
    {"key": "in_transit_sales", "label": "Dikirim ke pelanggan", "buckets": ("in_transit_sales_qty",),
     "hint": "Sudah keluar gudang menuju pelanggan, belum diterima."},
]
BUCKET_FIELDS = sorted({b for g in STATUS_GROUPS for b in g["buckets"]} | {"on_hand_qty"})
PHYSICAL_GROUPS = ("available", "makloon", "reserved", "committed", "hold", "wip")

DEFINITIONS: Dict[str, str] = {
    "available": STATUS_GROUPS[0]["hint"],
    "local": "Tersedia di cakupan kerja Anda: PT aktif × site kerja (POS: lokasi jualan; gudang: lokasi tugas).",
    "global": "Tersedia benar-benar total: semua PT dan semua gudang aktif (bukan data uji).",
    "on_hand": "Stok Fisik = Tersedia + Cadangan makloon + Dipesan + Dialokasikan + Ditahan/QC + Dalam proses.",
    "incoming": "Akan datang: PO terbuka (sisa belum diterima, satuan dasar), transfer dalam perjalanan (ke gudang "
                "tujuan), antar-PT dikonfirmasi, hasil makloon berjalan, retur disetujui belum diterima.",
    "atp": "ATP = Tersedia + barang masuk dalam horizon (PO, roll menuju gudang, antar-PT dikonfirmasi) − sisa "
           "pesanan yang menunggu (backorder). Antar-PT tidak dihitung di angka GLOBAL (sudah ada di stok PT penjual).",
}


def is_test_doc(doc: Optional[Dict[str, Any]]) -> bool:
    """Data uji yang DITANDAI (`is_test: true`). Keputusan implementer FIX-2: TIDAK menebak dari nama ("TEST_WH …") —
    puluhan uji otomatis membuat gudang bernama TEST lalu memeriksa angkanya; gudang uji tertinggal di data acuan
    (B3a §8) tidak berisi roll/saldo, jadi angka tidak berubah. Pembersihan data uji = tugas data, bukan rumus."""
    return (doc or {}).get("is_test") is True


async def warehouse_map() -> Dict[str, Dict[str, Any]]:
    """Semua gudang master + `counted` (dihitung di angka stok) + nama site. Dibaca segar tiap panggilan (≤ puluhan
    dokumen) — cache membuat gudang yang baru diubah/dinonaktifkan salah hitung sampai kedaluwarsa."""
    sites = {s["id"]: s async for s in db.warehouse_sites.find({}, {"_id": 0, "id": 1, "name": 1, "code": 1,
                                                                    "active": 1, "is_test": 1})}
    out: Dict[str, Dict[str, Any]] = {}
    async for w in db.warehouses.find({}, {"_id": 0, "id": 1, "code": 1, "name": 1, "city": 1, "active": 1,
                                           "site_id": 1, "sharing_mode": 1, "is_test": 1}):
        if not w.get("id"):
            continue
        site = sites.get(w.get("site_id") or "") or {}
        w["site_name"] = site.get("name") or ""
        w["counted"] = w.get("active") is not False and not is_test_doc(w) and not is_test_doc(site)
        out[w["id"]] = w
    return out


async def counted_warehouse_ids() -> Set[str]:
    return {wid for wid, w in (await warehouse_map()).items() if w["counted"]}


async def makloon_by_product_entity(product_ids: Optional[Iterable[str]] = None) -> Dict[tuple, float]:
    """{(product_id, owner_entity_id): qty} cadangan makloon aktif — SATU pembaca `material_reservations`."""
    q: Dict[str, Any] = {"status": "active"}
    ids = [p for p in (product_ids or []) if p]
    if ids:
        q["product_id"] = {"$in": ids}
    out: Dict[tuple, float] = {}
    async for m in db.material_reservations.find(q, {"_id": 0, "product_id": 1, "owner_entity_id": 1, "qty": 1}):
        k = (m.get("product_id"), m.get("owner_entity_id") or DEFAULT_ENTITY_ID)
        out[k] = round(out.get(k, 0.0) + float(m.get("qty") or 0), 4)
    return out


def allocate_makloon(segs: List[Dict[str, Any]], makloon: Dict[tuple, float]) -> None:
    """SATU aturan alokasi cadangan makloon ke segmen (gudang bertersedia terbesar dulu). Mengubah `segs` di tempat:
    `makloon_reserved_qty` per segmen, `available_qty` dikurangi; sisa yang tak tertutup → `makloon_shortfall_qty`."""
    by_pe: Dict[tuple, List[Dict[str, Any]]] = {}
    for s in segs:
        s.setdefault("makloon_reserved_qty", 0.0)
        by_pe.setdefault((s["product_id"], s["owner_entity_id"]), []).append(s)
    for key, qty in makloon.items():
        left = float(qty or 0)
        for s in sorted(by_pe.get(key, []), key=lambda x: (-x["available_qty"], x["warehouse_id"])):
            cut = min(left, max(s["available_qty"], 0.0))
            if cut <= 0:
                continue
            s["available_qty"] = round(s["available_qty"] - cut, 4)
            s["makloon_reserved_qty"] = round(s["makloon_reserved_qty"] + cut, 4)
            left -= cut
            if left <= EPS:
                break
        if left > EPS and by_pe.get(key):
            seg = by_pe[key][0]
            seg["makloon_shortfall_qty"] = round(seg.get("makloon_shortfall_qty", 0.0) + left, 4)


async def segments(product_ids: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """Segmen saldo (produk × gudang × PT) di gudang yang dihitung, SESUDAH cadangan makloon dialokasikan.
    Alokasi selalu memakai seluruh gudang PT itu (bukan hanya yang disaring pemanggil) agar angka tidak bergantung
    pada saringan. Pemanggil menyaring sendiri sesudahnya."""
    whmap = await warehouse_map()
    ids = [p for p in (product_ids or []) if p]
    q: Dict[str, Any] = {"product_id": {"$in": ids}} if ids else {}
    proj = {"_id": 0, "product_id": 1, "warehouse_id": 1, "owner_entity_id": 1, "roll_count": 1,
            "on_hand_roll_count": 1, "roll_counts": 1, **{f: 1 for f in BUCKET_FIELDS}}
    segs: List[Dict[str, Any]] = []
    async for b in db.inventory_balances.find(q, proj):
        pid, wid = b.get("product_id"), b.get("warehouse_id")
        w = whmap.get(wid or "")
        if not pid or not w or not w["counted"]:
            continue
        s = {"product_id": pid, "warehouse_id": wid, "owner_entity_id": b.get("owner_entity_id") or DEFAULT_ENTITY_ID,
             "site_id": w.get("site_id") or "",
             "available_rolls": int(b.get("roll_count") or 0), "on_hand_rolls": int(b.get("on_hand_roll_count") or 0),
             "roll_counts": dict(b.get("roll_counts") or {})}
        for f in BUCKET_FIELDS:
            s[f] = float(b.get(f) or 0)
        s["balance_available_qty"] = s["available_qty"]
        segs.append(s)
    allocate_makloon(segs, await makloon_by_product_entity(ids or None))
    return segs


def _empty_totals() -> Dict[str, float]:
    t = {f: 0.0 for f in BUCKET_FIELDS}
    t.update(available_rolls=0, on_hand_rolls=0, makloon_reserved_qty=0.0, balance_available_qty=0.0)
    return t


def sum_segments(segs: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    t = _empty_totals()
    rc: Dict[str, int] = {}
    for s in segs:
        for f in BUCKET_FIELDS:
            t[f] += s.get(f, 0.0)
        t["makloon_reserved_qty"] += s.get("makloon_reserved_qty", 0.0)
        t["balance_available_qty"] += s.get("balance_available_qty", 0.0)
        t["available_rolls"] += s.get("available_rolls", 0)
        t["on_hand_rolls"] += s.get("on_hand_rolls", 0)
        for k, v in (s.get("roll_counts") or {}).items():
            rc[k] = rc.get(k, 0) + int(v or 0)
    out = {k: (round(v, 2) if isinstance(v, float) else v) for k, v in t.items()}
    out["available_qty"] = round(max(out["available_qty"], 0.0), 2)
    out["roll_counts"] = rc
    return out


def status_rows(tot: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rincian per status (kelompok KN_32) dari total segmen."""
    rc = tot.get("roll_counts") or {}
    rows = []
    for g in STATUS_GROUPS:
        if g["key"] == "makloon":
            qty, rolls = float(tot.get("makloon_reserved_qty") or 0), None
        else:
            qty = sum(float(tot.get(b) or 0) for b in g["buckets"])
            rolls = sum(int(rc.get(b) or 0) for b in g["buckets"])
            if g["key"] == "available":
                rolls = int(tot.get("available_rolls") or 0)
        rows.append({"key": g["key"], "label": g["label"], "qty": round(qty, 2), "rolls": rolls, "hint": g["hint"],
                     "physical": g["key"] in PHYSICAL_GROUPS})
    return rows


# ── Cakupan LOKAL ────────────────────────────────────────────────────────────



async def _work_site_ids(user: Dict[str, Any]) -> Optional[List[str]]:
    """Site kerja pengguna untuk angka LOKAL (BUKAN pagar akses — pagar tetap `location_scope`/FIX-1).
    None = tanpa batas site. Titik kait FIX-1: bila `location_scope.work_site_ids(user)` ada, dipakai."""
    from services import location_scope as _ls
    hook = getattr(_ls, "work_site_ids", None)
    if hook is not None:
        res = hook(user)
        if hasattr(res, "__await__"):
            res = await res
        if res is not None:
            return list(res)
    from dependencies import has_permission
    from role_registry import category_of
    sites = [s for s in (user.get("location_site_ids") or []) if s]
    pos_site = (user.get("pos_site_id") or "").strip()
    # PR-T4 — lokasi jualan bawaan untuk yang MENJUAL: pemegang `order.create` yang bukan pengawas (dulu nama peran
    # sales/sales_admin).
    if category_of(user.get("role")) != "pengawas" and await has_permission(user, "order", "create"):
        if pos_site:
            return [pos_site]
        return sites[:1] or None
    if sites:
        return sites
    whs = [w for w in (user.get("location_warehouse_ids") or []) if w]
    if whs:
        wm = await warehouse_map()
        return sorted({wm[w]["site_id"] for w in whs if w in wm and wm[w].get("site_id")}) or None
    return [pos_site] if pos_site else None


async def viewer_scope(ctx: Any, site_id: str = "", entity_id: str = "") -> Dict[str, Any]:
    """Cakupan LOKAL pengguna → {entity_ids, site_ids|None, warehouse_ids|None, label, basis}."""
    user = getattr(ctx, "user", None) or {}
    allowed = list(getattr(ctx, "allowed_entity_ids", None) or [])
    active = getattr(ctx, "active_entity_id", "") or ""
    if entity_id and entity_id != "all":
        ents = [entity_id] if (not allowed or entity_id in allowed) else []
    elif entity_id == "all" or getattr(ctx, "view_all", False) or not active or active == "all":
        ents = allowed or ([active] if active and active != "all" else [])
    else:
        ents = [active]
    wm = await warehouse_map()
    if site_id:
        sites, basis = [site_id], "param"
    else:
        sites = await _work_site_ids(user)
        basis = "work_site" if sites else "none"
    whs = None
    narrow = [w for w in (user.get("location_warehouse_ids") or []) if w] if basis == "work_site" else []
    if sites is not None:
        whs = sorted(wid for wid, w in wm.items() if w["counted"] and (w.get("site_id") or "") in sites)
        if narrow:
            whs = [w for w in whs if w in narrow] or whs
    ent_names = await entity_names()
    site_names = sorted({w["site_name"] for w in wm.values() if (w.get("site_id") or "") in (sites or []) and w["site_name"]})
    ent_label = (", ".join(ent_names.get(e, e) for e in ents) if len(ents) <= 2 else f"{len(ents)} PT") or "—"
    label = (" · ".join(site_names) + " · " if site_names else "") + ent_label
    return {"entity_ids": ents, "site_ids": sites, "warehouse_ids": whs, "label": label, "basis": basis,
            "site_names": site_names}


def in_local(seg: Dict[str, Any], scope: Dict[str, Any]) -> bool:
    if seg["owner_entity_id"] not in (scope.get("entity_ids") or []):
        return False
    whs = scope.get("warehouse_ids")
    return whs is None or seg["warehouse_id"] in whs


async def entity_names() -> Dict[str, str]:
    return {e["id"]: (e.get("short_name") or e.get("name") or e.get("legal_name") or e["id"])
            async for e in db.business_entities.find({}, {"_id": 0, "id": 1, "short_name": 1, "name": 1,
                                                          "legal_name": 1})}


# ── Dua angka ────────────────────────────────────────────────────────────────

def stock_state(qty: float) -> str:
    """"habis" (0) · "rendah" (0 < Tersedia < ambang K-04, `stock_availability.LOW_STOCK_QTY`) · "ada" — SATU aturan;
    FE tidak lagi memakai ambang sendiri (B3a STK-10: ≤ 40 di POS vs < 100 di server)."""
    from services.stock_availability import is_low_stock
    q = float(qty or 0)
    if q <= EPS:
        return "habis"
    return "rendah" if is_low_stock(q) else "ada"


def _pair(tot: Dict[str, Any]) -> Dict[str, Any]:
    qty = round(float(tot.get("available_qty") or 0), 2)
    return {"rolls": int(tot.get("available_rolls") or 0), "qty": qty, "state": stock_state(qty)}


async def figures_for(product_ids: List[str], scope: Dict[str, Any],
                      segs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Dict[str, Any]]:
    """{product_id: {"unit", "local": {rolls, qty}, "global": {rolls, qty}}} — dua angka per produk."""
    ids = [p for p in dict.fromkeys(product_ids or []) if p]
    if not ids:
        return {}
    segs = segs if segs is not None else await segments(ids)
    units = {p["id"]: p.get("base_unit") or "" async for p in db.products.find(
        {"id": {"$in": ids}}, {"_id": 0, "id": 1, "base_unit": 1})}
    per: Dict[str, Dict[str, List[Dict[str, Any]]]] = {pid: {"local": [], "global": []} for pid in ids}
    for s in segs:
        slot = per.get(s["product_id"])
        if slot is None:
            continue
        slot["global"].append(s)
        if in_local(s, scope):
            slot["local"].append(s)
    from services.stock_availability import LOW_STOCK_QTY
    return {pid: {"unit": units.get(pid, ""), "low_stock_qty": LOW_STOCK_QTY, "local": _pair(sum_segments(v["local"])),
                  "global": _pair(sum_segments(v["global"]))} for pid, v in per.items()}


def scope_public(scope: Dict[str, Any]) -> Dict[str, Any]:
    return {"label": scope.get("label"), "basis": scope.get("basis"), "entity_ids": scope.get("entity_ids"),
            "site_ids": scope.get("site_ids"), "site_names": scope.get("site_names")}


# ── Barang akan datang (SATU pembaca dokumen pasokan) ───────────────────────

INCOMING_INTERCO_CONFIRMED = ["confirmed", "shipped"]
INCOMING_INTERCO_TENTATIVE = ["draft"]
TRANSIT_TRANSFER_STATUSES = ["dispatched", "in_transit", "shipped"]
RUNNING_MKO_STATUSES = ["in_process"]
RETURN_PENDING_STATUSES = ["approved"]


def po_open_base_qty(it: Dict[str, Any]) -> float:
    """Sisa PO belum diterima dalam SATUAN DASAR: (qty − diterima) × quantity_base/qty (SCH-3/STK-3/STK-4)."""
    q_doc = float(it.get("quantity", it.get("qty", 0)) or 0)
    open_doc = q_doc - float(it.get("received_qty", 0) or 0)
    if open_doc <= 0:
        return 0.0
    base = float(it.get("quantity_base") or it.get("base_quantity") or 0)
    if base > 0 and q_doc > 0:
        return round(open_doc * base / q_doc, 4)
    return round(open_doc, 4)


async def incoming_rows(product_ids: Optional[Iterable[str]] = None, *,
                        include_tentative: bool = False,
                        sources: Iterable[str] = ("po", "interco", "transfer", "makloon", "return")
                        ) -> List[Dict[str, Any]]:
    """Semua pasokan yang sedang berjalan per baris dokumen. Bendera per baris:
    `in_atp` (dihitung ATP menurut `atp_policy`), `in_global` (pasokan baru bagi grup), `tentative` (draf)."""
    from services.roll_service import OPEN_PO_STATUSES
    ids = [p for p in dict.fromkeys(product_ids or []) if p]
    idset = set(ids)
    want = set(sources)
    rows: List[Dict[str, Any]] = []

    def ok(pid: Optional[str]) -> bool:
        return bool(pid) and (not idset or pid in idset)

    item_q: Dict[str, Any] = {"items.product_id": {"$in": ids}} if ids else {}
    if "po" in want:
        async for po in db.purchase_orders.find({"status": {"$in": OPEN_PO_STATUSES}, **item_q},
                                                {"_id": 0, "id": 1, "po_number": 1, "items": 1, "entity_id": 1,
                                                 "warehouse_id": 1, "expected_delivery_date": 1, "source_so_ids": 1,
                                                 "status": 1}):
            for it in po.get("items") or []:
                if not ok(it.get("product_id")):
                    continue
                qty = po_open_base_qty(it)
                if qty <= 0.01:
                    continue
                rows.append({"source": "po", "label": "PO terbuka", "number": po.get("po_number", ""),
                             "doc_id": po.get("id", ""), "status": po.get("status", ""),
                             "product_id": it["product_id"], "owner_entity_id": po.get("entity_id") or "",
                             "warehouse_id": po.get("warehouse_id") or "", "eta": po.get("expected_delivery_date") or "",
                             "qty": round(qty, 2), "bound_so": bool(po.get("source_so_ids") or it.get("source_so_id")),
                             "in_atp": True, "in_global": True, "tentative": False})
    if "interco" in want:
        sts = INCOMING_INTERCO_CONFIRMED + (INCOMING_INTERCO_TENTATIVE if include_tentative else [])
        async for d in db.interco_transactions.find({"role": "buyer", "status": {"$in": sts}, **item_q},
                                                    {"_id": 0, "id": 1, "number": 1, "items": 1, "status": 1,
                                                     "buyer_entity_id": 1, "seller_entity_id": 1,
                                                     "seller_entity_name": 1, "due_date": 1, "doc_date": 1,
                                                     "source_order_id": 1, "source_order_number": 1}):
            tentative = d.get("status") in INCOMING_INTERCO_TENTATIVE
            for it in d.get("items") or []:
                if not ok(it.get("product_id")):
                    continue
                qty = float(it.get("quantity_base") or it.get("quantity", it.get("qty", 0)) or 0)
                if qty <= 0.01:
                    continue
                rows.append({"source": "interco", "label": "Antar-PT" + (" (draf)" if tentative else ""),
                             "number": d.get("number", ""), "doc_id": d.get("id", ""), "status": d.get("status", ""),
                             "product_id": it["product_id"], "owner_entity_id": d.get("buyer_entity_id") or "",
                             "from_entity_id": d.get("seller_entity_id") or "",
                             "from_entity_name": d.get("seller_entity_name") or "",
                             "source_order_id": d.get("source_order_id") or "",
                             "source_order_number": d.get("source_order_number") or "",
                             "warehouse_id": "", "eta": d.get("due_date") or d.get("doc_date") or "",
                             "qty": round(qty, 2), "bound_so": bool(d.get("source_order_id")),
                             "in_atp": not tentative, "in_global": False, "tentative": tentative})
    if "transfer" in want:
        rq: Dict[str, Any] = {"status": "in_transit_transfer", "transfer_ref.id": {"$nin": [None, ""]}}
        if ids:
            rq["product_id"] = {"$in": ids}
        agg: Dict[tuple, Dict[str, Any]] = {}
        async for r in db.inventory_rolls.find(rq, {"_id": 0, "product_id": 1, "owner_entity_id": 1,
                                                    "transfer_ref": 1, "length_remaining": 1, "warehouse_id": 1}):
            k = ((r.get("transfer_ref") or {}).get("id"), r.get("product_id"), r.get("owner_entity_id") or "")
            a = agg.setdefault(k, {"qty": 0.0, "rolls": 0, "from_wh": r.get("warehouse_id") or ""})
            a["qty"] += float(r.get("length_remaining") or 0)
            a["rolls"] += 1
        trf_ids = list({k[0] for k in agg})
        trfs = {t["id"]: t async for t in db.warehouse_transfers.find(
            {"id": {"$in": trf_ids}}, {"_id": 0, "id": 1, "number": 1, "status": 1, "dest_warehouse_id": 1,
                                       "source_warehouse_id": 1, "expected_arrival_date": 1, "eta": 1})} if trf_ids else {}
        for (tid, pid, owner), a in agg.items():
            t = trfs.get(tid) or {}
            rows.append({"source": "transfer", "label": "Transfer dalam perjalanan", "number": t.get("number", ""),
                         "doc_id": tid, "status": t.get("status", ""), "product_id": pid, "owner_entity_id": owner,
                         "warehouse_id": t.get("dest_warehouse_id") or "",
                         "from_warehouse_id": t.get("source_warehouse_id") or a["from_wh"],
                         "eta": t.get("expected_arrival_date") or t.get("eta") or "",
                         "qty": round(a["qty"], 2), "rolls": a["rolls"], "bound_so": False,
                         "in_atp": False, "in_global": False, "tentative": False})
    if "makloon" in want:
        mq: Dict[str, Any] = {"status": {"$in": RUNNING_MKO_STATUSES}}
        async for m in db.makloon_orders.find(mq, {"_id": 0, "id": 1, "mko_number": 1, "status": 1, "entity_id": 1,
                                                   "target_warehouse_id": 1, "final_output_product_id": 1,
                                                   "expected_date": 1, "due_date": 1, "steps": 1}):
            steps = sorted(m.get("steps") or [], key=lambda s: int(s.get("seq") or 0))
            last = steps[-1] if steps else {}
            pid = last.get("output_product_id") or m.get("final_output_product_id")
            if not ok(pid) or last.get("status") in ("received", "completed", "cancelled"):
                continue
            qty = float(last.get("expected_output_qty") or 0) - float(last.get("actual_output_qty") or 0)
            if qty <= 0.01:
                continue
            rows.append({"source": "makloon", "label": "Makloon berjalan", "number": m.get("mko_number", ""),
                         "doc_id": m.get("id", ""), "status": m.get("status", ""), "product_id": pid,
                         "owner_entity_id": m.get("entity_id") or "",
                         "warehouse_id": last.get("output_warehouse_id") or m.get("target_warehouse_id") or "",
                         "eta": m.get("expected_date") or m.get("due_date") or "", "qty": round(qty, 2),
                         "bound_so": False, "in_atp": False, "in_global": True, "tentative": False})
    if "return" in want:
        async for rt in db.sales_returns.find({"status": {"$in": RETURN_PENDING_STATUSES}, **item_q},
                                              {"_id": 0, "id": 1, "number": 1, "status": 1, "entity_id": 1,
                                               "warehouse_id": 1, "items": 1, "expected_date": 1}):
            for it in rt.get("items") or []:
                if not ok(it.get("product_id")):
                    continue
                qty = float(it.get("quantity_base") or it.get("quantity_returned") or it.get("quantity") or 0)
                if qty <= 0.01:
                    continue
                rows.append({"source": "return", "label": "Retur disetujui, belum diterima",
                             "number": rt.get("number", ""), "doc_id": rt.get("id", ""), "status": rt.get("status", ""),
                             "product_id": it["product_id"], "owner_entity_id": rt.get("entity_id") or "",
                             "warehouse_id": rt.get("warehouse_id") or "", "eta": rt.get("expected_date") or "",
                             "qty": round(qty, 2), "condition": it.get("condition") or "", "bound_so": False,
                             "in_atp": False, "in_global": True, "tentative": False})
    rows.sort(key=lambda r: (r["eta"] or "9999-12-31", r["source"], r["number"]))
    return rows


def incoming_in_scope(row: Dict[str, Any], scope: Dict[str, Any]) -> bool:
    if row.get("owner_entity_id") not in (scope.get("entity_ids") or []):
        return False
    whs = scope.get("warehouse_ids")
    return whs is None or not row.get("warehouse_id") or row["warehouse_id"] in whs


# ── ATP & rincian ────────────────────────────────────────────────────────────

async def atp_pair(product_id: str, segs: List[Dict[str, Any]], incoming: List[Dict[str, Any]],
                   scope: Dict[str, Any]) -> Dict[str, Any]:
    """ATP LOKAL & GLOBAL dengan rumus tunggal `atp_policy` (horizon = setelan)."""
    from services import atp_policy as _atp
    days = await _atp.horizon_days()
    bmap = await _atp.backorder_map([product_id])
    inbound = lambda ss: sum(float(s.get("in_transit_inbound_qty") or 0) for s in ss)  # noqa: E731
    local_segs = [s for s in segs if s["product_id"] == product_id and in_local(s, scope)]
    glob_segs = [s for s in segs if s["product_id"] == product_id]
    inc_local = [r for r in incoming if r["product_id"] == product_id and r["in_atp"] and incoming_in_scope(r, scope)
                 and _atp.within_horizon(r.get("eta"), horizon_days=days)]
    inc_glob = [r for r in incoming if r["product_id"] == product_id and r["in_atp"] and r["in_global"]
                and _atp.within_horizon(r.get("eta"), horizon_days=days)]
    whs = scope.get("warehouse_ids")
    dem_local = 0.0
    dem_glob = 0.0
    for (pid, eid), rec in bmap.items():
        if pid != product_id:
            continue
        dem_glob += float(rec.get("total") or 0)
        if eid in (scope.get("entity_ids") or []):
            if whs is None:
                dem_local += float(rec.get("total") or 0)
            else:
                dem_local += float(rec.get("unassigned") or 0) + sum(
                    float(q or 0) for w, q in (rec.get("by_wh") or {}).items() if w in whs)
    av_l = sum_segments(local_segs)["available_qty"]
    av_g = sum_segments(glob_segs)["available_qty"]
    il = round(sum(r["qty"] for r in inc_local) + inbound(local_segs), 2)
    ig = round(sum(r["qty"] for r in inc_glob) + inbound(glob_segs), 2)
    return {"horizon_days": days,
            "local": {"available": av_l, "incoming_in_horizon": il, "pending_demand": round(dem_local, 2),
                      "atp": _atp.compute_atp(av_l, il, dem_local)},
            "global": {"available": av_g, "incoming_in_horizon": ig, "pending_demand": round(dem_glob, 2),
                       "atp": _atp.compute_atp(av_g, ig, dem_glob)}}


async def detail(product_id: str, scope: Dict[str, Any], visible_entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Rincian satu produk saat angka diklik: per site/gudang, per PT, per status, transit (ke gudang tujuan),
    akan datang, ATP. PT di luar `visible_entity_ids` tetap tampil sebagai ANGKA (tanpa dokumen roll/HPP)."""
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "base_unit": 1}) or {}
    segs = await segments([product_id])
    wm = await warehouse_map()
    names = await entity_names()
    incoming = await incoming_rows([product_id], include_tentative=True)
    tot_g = sum_segments(segs)
    tot_l = sum_segments([s for s in segs if in_local(s, scope)])
    visible = set(visible_entity_ids or [])

    # per site → gudang
    by_site: Dict[str, Dict[str, Any]] = {}
    for s in segs:
        w = wm.get(s["warehouse_id"], {})
        site = by_site.setdefault(s["site_id"], {"site_id": s["site_id"], "site_name": w.get("site_name") or "Tanpa site",
                                                 "_segs": [], "warehouses": {}})
        site["_segs"].append(s)
        site["warehouses"].setdefault(s["warehouse_id"], []).append(s)
    sites_out = []
    for site in by_site.values():
        t = sum_segments(site["_segs"])
        whs_out = []
        for wid, ss in site["warehouses"].items():
            tw = sum_segments(ss)
            w = wm.get(wid, {})
            whs_out.append({"warehouse_id": wid, "code": w.get("code") or "", "name": w.get("name") or wid,
                            "local": any(in_local(x, scope) for x in ss), **_brief(tw),
                            "by_entity": [{"entity_id": x["owner_entity_id"],
                                           "entity_name": names.get(x["owner_entity_id"], x["owner_entity_id"]),
                                           **_brief(sum_segments([x]))} for x in ss]})
        whs_out.sort(key=lambda r: -r["available_qty"])
        sites_out.append({"site_id": site["site_id"], "site_name": site["site_name"],
                          "local": site["site_id"] in (scope.get("site_ids") or []), **_brief(t),
                          "warehouses": whs_out})
    sites_out.sort(key=lambda r: (not r["local"], -r["available_qty"]))

    by_ent: Dict[str, List[Dict[str, Any]]] = {}
    for s in segs:
        by_ent.setdefault(s["owner_entity_id"], []).append(s)
    ents_out = [{"entity_id": eid, "entity_name": names.get(eid, eid), "own": eid in (scope.get("entity_ids") or []),
                 "visible": (not visible) or eid in visible, **_brief(sum_segments(ss))} for eid, ss in by_ent.items()]
    ents_out.sort(key=lambda r: (not r["own"], -r["available_qty"]))

    for r in incoming:
        w = wm.get(r.get("warehouse_id") or "", {})
        r["warehouse_name"] = w.get("name") or ("" if not r.get("warehouse_id") else r["warehouse_id"])
        r["warehouse_active"] = bool(w) and w.get("active") is not False
        r["site_name"] = w.get("site_name") or ""
        r["owner_entity_name"] = names.get(r.get("owner_entity_id") or "", r.get("owner_entity_id") or "")
        r["local"] = incoming_in_scope(r, scope)
        if visible and r.get("owner_entity_id") not in visible:   # B3a #7 — PT di luar izin: angka saja
            for k in ("doc_id", "number", "source_order_id", "source_order_number"):
                r[k] = ""
    atp = await atp_pair(product_id, segs, incoming, scope)
    return {"product_id": product_id, "sku": prod.get("sku", ""), "product_name": prod.get("name", ""),
            "unit": prod.get("base_unit") or "", "scope": scope_public(scope),
            "local": _pair(tot_l), "global": _pair(tot_g),
            "local_status": status_rows(tot_l), "global_status": status_rows(tot_g),
            "on_hand": {"local": {"qty": tot_l["on_hand_qty"], "rolls": tot_l["on_hand_rolls"]},
                        "global": {"qty": tot_g["on_hand_qty"], "rolls": tot_g["on_hand_rolls"]}},
            "by_site": sites_out, "by_entity": ents_out, "incoming": incoming, "atp": atp,
            "definitions": DEFINITIONS}


def _brief(t: Dict[str, Any]) -> Dict[str, Any]:
    rc = t.get("roll_counts") or {}
    grp = {g["key"]: g for g in STATUS_GROUPS}

    def q(key):
        return round(sum(float(t.get(b) or 0) for b in grp[key]["buckets"]), 2)

    def n(key):
        return sum(int(rc.get(b) or 0) for b in grp[key]["buckets"])
    return {"available_qty": t["available_qty"], "available_rolls": t["available_rolls"],
            "makloon_reserved_qty": t["makloon_reserved_qty"], "reserved_qty": q("reserved"),
            "committed_qty": q("committed"), "hold_qty": q("hold"), "hold_rolls": n("hold"), "wip_qty": q("wip"),
            "subcon_qty": q("subcon"), "in_transit_qty": q("in_transit"), "on_hand_qty": t["on_hand_qty"],
            "on_hand_rolls": t["on_hand_rolls"]}


# ── Pembungkus untuk endpoint lama ──────────────────────────────────────────

async def available_by_owner(product_ids: Optional[Iterable[str]] = None,
                             warehouse_ids: Optional[Iterable[str]] = None) -> Dict[tuple, Dict[str, float]]:
    """{(product_id, owner_entity_id): {"qty", "rolls"}} Tersedia (definisi tunggal), opsional disaring gudang."""
    segs = await segments(product_ids)
    whs = set(warehouse_ids) if warehouse_ids is not None else None
    out: Dict[tuple, Dict[str, float]] = {}
    for s in segs:
        if whs is not None and s["warehouse_id"] not in whs:
            continue
        k = (s["product_id"], s["owner_entity_id"])
        o = out.setdefault(k, {"qty": 0.0, "rolls": 0})
        o["qty"] = round(o["qty"] + max(s["available_qty"], 0.0), 4)
        o["rolls"] += s["available_rolls"]
    return out


def segment_index(segs: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    """{(product_id, warehouse_id, owner_entity_id): segmen} — untuk endpoint yang menampilkan baris saldo."""
    return {(s["product_id"], s["warehouse_id"], s["owner_entity_id"]): s for s in segs}


def adjust_balance_row(b: Dict[str, Any], idx: Dict[tuple, Dict[str, Any]]) -> Dict[str, Any]:
    """Baris saldo mentah → `available_qty` menurut definisi tunggal (cadangan makloon dikurangi). Baris di gudang
    yang tidak dihitung (non-aktif / uji / yatim) diberi `counted=false` dan Tersedia 0."""
    k = (b.get("product_id"), b.get("warehouse_id"), b.get("owner_entity_id") or DEFAULT_ENTITY_ID)
    s = idx.get(k)
    b["balance_available_qty"] = round(float(b.get("available_qty") or 0), 2)
    if s is None:
        b["counted"] = False
        b["makloon_reserved_qty"] = 0.0
        b["available_qty"] = 0.0
        return b
    b["counted"] = True
    b["makloon_reserved_qty"] = round(s.get("makloon_reserved_qty", 0.0), 2)
    b["available_qty"] = round(max(s["available_qty"], 0.0), 2)
    return b
