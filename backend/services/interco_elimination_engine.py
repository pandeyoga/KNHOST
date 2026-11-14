"""PK-31 (IC-03, IC-04, RP-10) — MESIN ELIMINASI ANTAR-PT PER PERIODE dari data BERTANGGAL.

Masalah lama: satu entri eliminasi per pasangan dokumen yang DITIMPA tiap kali angkanya berubah, dihitung dari keadaan
dokumen dan roll HARI INI, dengan satu `effective_date` (tanggal dokumen). Akibatnya laporan konsolidasi tanggal lama
berubah begitu barangnya dijual atau dilunasi, dan pendapatan (tanggal konfirmasi) serta HPP (saat barang pindah) yang
jatuh di dua tahun berbeda menghasilkan laba grup +M di tahun pertama dan −M di tahun kedua.

Mesin ini menghitung KEADAAN satu pasangan pada tanggal mana pun hanya dari data bertanggal ≤ tanggal itu:

  revenue      kredit − debit akun pendapatan pada jurnal `{pair}:seller`, `{pair}:adj:seller`, `{rp}:seller` (retur)
  cogs         debit − kredit akun HPP pada `{pair}:cogs` dan `{rp}:goods_in` (retur)
  delivered    ada jurnal `{pair}:receipt`
  moved_len    Σ panjang roll tugas gudang selesai − Σ jumlah retur selesai
  sold_len     Σ panjang di surat jalan (tidak batal) untuk roll ber-`cost_basis.chain` pasangan ini
  unsold_ratio 1 bila belum diterima / belum ada yang pindah; selain itu clamp(1 − sold ÷ moved, 0, 1)
  urp          belum diterima → revenue; sudah → max((revenue − cogs) × unsold_ratio, 0) — rugi tidak dieliminasi
  ic_balance   debit − kredit piutang antar-PT di jurnal pasangan buku penjual − pelunasan + refund (tanggal bayar)

Jurnal pembalik (`…:reversal` dan pembalik PK-10 `source_type="reversal"`) ikut dibaca supaya pembatalan nol bersih.
Baris eliminasi kumulatif sebuah keadaan (selalu seimbang):
  Dr Pendapatan revenue · Cr HPP (revenue − urp) · Cr Persediaan urp (1-1310 belum diterima, 1-1300 sudah)
  Dr Utang antar-PT / Cr Piutang antar-PT ic_balance (terbalik bila negatif)
Entri bulan = keadaan akhir bulan − keadaan akhir bulan sebelumnya, per akun. Entri bulan yang sudah ditutup di PT
penjual DAN pembeli disimpan `frozen` dan tidak pernah ditimpa; hitung ulang yang berbeda dilaporkan sebagai `stale`.
"""
from __future__ import annotations

import calendar
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from core_utils import new_id, now_iso, safe_doc
from db import db
from services.book_date import tanggal_buku

COLL = "intercompany_eliminations"
EPS = 0.005
LEN_EPS = 0.0001
SELAMANYA = "9999-12-31"
_BULAN = ("", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober",
          "November", "Desember")
#: status surat jalan yang tidak dihitung "keluar grup".
SHIPMENT_BATAL = ("cancelled", "void", "batal", "rejected")
#: field keadaan yang disimpan di entri (`cumulative`).
FIELD_KEADAAN = ("revenue", "cogs", "urp", "delivered", "unsold_ratio", "moved_len", "sold_len", "ic_balance")


# ═══════════════════════════════════════════════════════════════════════════
# Tanggal & bulan
# ═══════════════════════════════════════════════════════════════════════════
def _tgl(v: Any) -> str:
    """Tanggal buku WIB 10 huruf; nilai rusak → 10 huruf pertamanya (tidak pernah melempar)."""
    if not v:
        return ""
    try:
        return tanggal_buku(v)
    except ValueError:
        return str(v)[:10]


def akhir_bulan(period_key: str) -> str:
    y, m = int(period_key[:4]), int(period_key[5:7])
    return f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"


def akhir_bulan_sebelumnya(period_key: str) -> str:
    y, m = int(period_key[:4]), int(period_key[5:7])
    y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    return akhir_bulan(f"{y:04d}-{m:02d}")


def label_bulan(period_key: str) -> str:
    return f"{_BULAN[int(period_key[5:7])]} {period_key[:4]}"


def _sen(x: float) -> int:
    return int(round(float(x or 0) * 100))


# ═══════════════════════════════════════════════════════════════════════════
# Fakta bertanggal satu pasangan (dibaca SEKALI, keadaan dihitung di memori)
# ═══════════════════════════════════════════════════════════════════════════
def _akun() -> Dict[str, str]:
    from services import gl_service as gl
    return {"revenue": gl.ACC_PENDAPATAN, "cogs": gl.ACC_HPP, "inventory": gl.ACC_PERSEDIAAN,
            "inventory_transit": gl.ACC_PERSEDIAAN_TRANSIT, "ic_ar": gl.ACC_IC_AR, "ic_ap": gl.ACC_IC_AP}


async def _kode_akun() -> Dict[str, Set[str]]:
    """Akun yang DIBACA dari jurnal per peran — bawaan + pemetaan per PT + riwayatnya (`gl_mapping_service`)."""
    from services.gl_mapping_service import known_codes
    return {"revenue": set(await known_codes("penjualan.pendapatan")),
            "cogs": set(await known_codes("persediaan.hpp")),
            "ic_ar": set(await known_codes("antar_pt.piutang_ic"))}


def _roll_pasangan(pair_id: str) -> Dict[str, Any]:
    """Roll (dan potongannya — mewarisi `cost_basis`) yang pernah berpindah lewat pasangan ini. Roll lama tanpa
    `chain` dikenali dari `cost_basis.interco_pair_id` tingkat atas."""
    return {"$or": [{"cost_basis.chain.interco_pair_id": pair_id},
                    {"cost_basis.chain": {"$exists": False}, "cost_basis.interco_pair_id": pair_id}]}


async def facts(pair_id: str, seller: Optional[Dict[str, Any]] = None,
                kode: Optional[Dict[str, Set[str]]] = None) -> Optional[Dict[str, Any]]:
    """Semua fakta bertanggal pasangan: `[(tanggal, nilai)]` per besaran. `None` bila dokumen penjual tidak ada."""
    if seller is None:
        seller = await db.interco_transactions.find_one({"pair_id": pair_id, "role": "seller"}, {"_id": 0})
    if not seller:
        return None
    kode = kode or await _kode_akun()
    f: Dict[str, Any] = {"pair_id": pair_id, "seller": seller, "revenue": [], "cogs": [], "ic": [], "receipt": [],
                         "moved": [], "returned": [], "sold": []}
    rps: List[str] = []
    async for r in db.interco_returns.find({"origin_pair_id": pair_id, "role": "returner"},
                                           {"_id": 0, "return_pair_id": 1, "status": 1, "items": 1,
                                            "completed_at": 1, "updated_at": 1}):
        if r.get("return_pair_id"):
            rps.append(r["return_pair_id"])
        if r.get("status") == "completed":
            f["returned"].append((_tgl(r.get("completed_at") or r.get("updated_at")),
                                  sum(float(i.get("quantity") or 0) for i in r.get("items") or [])))
    # Jurnal: kunci → peran. Pembalik `…:reversal` memakai peran jurnal asalnya.
    peran: Dict[Tuple[str, str], str] = {}
    for k in ("seller", "adj:seller"):
        peran[("interco_transaction", f"{pair_id}:{k}")] = "jual"
    peran[("interco_transaction", f"{pair_id}:cogs")] = "hpp"
    peran[("interco_transaction", f"{pair_id}:receipt")] = "terima"
    for rp in rps:
        peran[("interco_return", f"{rp}:seller")] = "jual"
        peran[("interco_return", f"{rp}:goods_in")] = "hpp"
    for (st, sid), p in list(peran.items()):
        peran[(st, f"{sid}:reversal")] = p
    by_type: Dict[str, List[str]] = {}
    for st, sid in peran:
        by_type.setdefault(st, []).append(sid)
    jurnal: List[Tuple[str, Dict[str, Any]]] = []
    id_ke_peran: Dict[str, str] = {}
    async for je in db.journal_entries.find(
            {"status": {"$ne": "void"}, "$or": [{"source_type": t, "source_id": {"$in": ids}}
                                                for t, ids in by_type.items()]},
            {"_id": 0, "id": 1, "date": 1, "lines": 1, "source_type": 1, "source_id": 1}):
        p = peran.get((je.get("source_type"), je.get("source_id")))
        if p:
            jurnal.append((p if not str(je.get("source_id", "")).endswith(":reversal") else p + "-", je))
            id_ke_peran[je.get("id")] = p
    if id_ke_peran:   # PK-10 — pembalik generik: baris kebalikan, peran = peran jurnal asal
        async for je in db.journal_entries.find(
                {"status": {"$ne": "void"}, "source_type": "reversal", "source_id": {"$in": list(id_ke_peran)}},
                {"_id": 0, "date": 1, "lines": 1, "source_id": 1}):
            jurnal.append((id_ke_peran[je["source_id"]] + "-", je))
    for p, je in jurnal:
        d = _tgl(je.get("date"))
        base = p.rstrip("-")
        for ln in je.get("lines") or []:
            code = str(ln.get("account_code") or "")
            dr, cr = float(ln.get("debit") or 0), float(ln.get("credit") or 0)
            if base == "jual" and code in kode["revenue"]:
                f["revenue"].append((d, cr - dr))
            if base == "jual" and code in kode["ic_ar"]:
                f["ic"].append((d, dr - cr))
            if base == "hpp" and code in kode["cogs"]:
                f["cogs"].append((d, dr - cr))
        if base == "terima":
            f["receipt"].append((d, -1 if p.endswith("-") else 1))
    async for t in db.warehouse_transfers.find({"interco_pair_id": pair_id, "status": "completed"},
                                               {"_id": 0, "items": 1, "approved_at": 1, "updated_at": 1,
                                                "created_at": 1}):
        d = _tgl(t.get("approved_at") or t.get("updated_at") or t.get("created_at"))
        ln = 0.0
        for it in t.get("items") or []:
            rolls = it.get("rolls") or []
            ln += sum(float(r.get("length") or 0) for r in rolls) if rolls else float(it.get("qty") or 0)
        f["moved"].append((d, ln))
    roll_ids = [r["id"] async for r in db.inventory_rolls.find(_roll_pasangan(pair_id), {"_id": 0, "id": 1})]
    if roll_ids:
        ids = set(roll_ids)
        async for s in db.shipments.find({"rolls.roll_id": {"$in": roll_ids}, "status": {"$nin": list(SHIPMENT_BATAL)}},
                                         {"_id": 0, "rolls": 1, "shipped_at": 1, "created_at": 1}):
            d = _tgl(s.get("shipped_at") or s.get("created_at"))
            f["sold"].append((d, sum(float(r.get("length") or 0) for r in s.get("rolls") or []
                                     if r.get("roll_id") in ids)))
    async for st in db.interco_settlements.find(
            {"$or": [{"applied.pair_id": pair_id}, {"netted_against.pair_id": pair_id}],
             "status": {"$ne": "cancelled"}},
            {"_id": 0, "kind": 1, "status": 1, "settle_date": 1, "created_at": 1, "applied": 1, "netted_against": 1}):
        tanda = 1 if (st.get("kind") or "settlement") == "refund" else -1
        d = _tgl(st.get("settle_date") or st.get("created_at"))
        for row in (st.get("applied") or []) + (st.get("netted_against") or []):
            if row.get("pair_id") == pair_id and (st.get("status") == "posted" or row.get("applied_at")):
                f["ic"].append((d, tanda * float(row.get("applied_amount") or 0)))
    f["months"] = sorted({d[:7] for k in ("revenue", "cogs", "ic", "receipt", "moved", "returned", "sold")
                          for d, _v in f[k] if d})
    return f


def _sum(rows: Iterable[Tuple[str, float]], d: str) -> float:
    return sum(v for t, v in rows if t and t <= d)


def state_at(f: Dict[str, Any], as_of: str) -> Dict[str, Any]:
    """Keadaan pasangan pada tanggal `as_of` (10 huruf) dari fakta yang sudah dibaca."""
    d = (as_of or SELAMANYA)[:10]
    revenue = round(_sum(f["revenue"], d), 2)
    cogs = round(_sum(f["cogs"], d), 2)
    delivered = _sum(f["receipt"], d) > 0
    moved = round(max(_sum(f["moved"], d) - _sum(f["returned"], d), 0.0), 4)
    sold = round(_sum(f["sold"], d), 4)
    if not delivered or moved <= LEN_EPS:
        ratio = 1.0
    else:
        ratio = round(max(0.0, min(1.0, 1.0 - sold / moved)), 6)
    urp = revenue if not delivered else round(max((revenue - cogs) * ratio, 0.0), 2)
    return {"revenue": revenue, "cogs": cogs, "urp": round(urp, 2), "delivered": delivered, "unsold_ratio": ratio,
            "moved_len": moved, "sold_len": sold, "ic_balance": round(_sum(f["ic"], d), 2)}


def _neto(st: Dict[str, Any], acc: Dict[str, str]) -> Dict[str, int]:
    """Baris eliminasi KUMULATIF sebuah keadaan sebagai debit − kredit per akun (dalam sen; Σ = 0)."""
    n: Dict[str, int] = {}

    def add(code: str, sen: int) -> None:
        n[code] = n.get(code, 0) + sen
    rev, urp, ic = _sen(st["revenue"]), _sen(st["urp"]), _sen(st["ic_balance"])
    add(acc["revenue"], rev)
    add(acc["cogs"], -(rev - urp))
    add(acc["inventory"] if st["delivered"] else acc["inventory_transit"], -urp)
    add(acc["ic_ap"], ic)
    add(acc["ic_ar"], -ic)
    return n


_URUT = ("revenue", "cogs", "inventory_transit", "inventory", "ic_ap", "ic_ar")
_KET = {"revenue": "Eliminasi pendapatan antar-PT", "cogs": "Eliminasi HPP antar-PT",
        "inventory_transit": "Laba belum terealisasi di barang dalam perjalanan",
        "inventory": "Laba belum terealisasi di persediaan pembeli",
        "ic_ap": "Eliminasi utang antar-PT", "ic_ar": "Eliminasi piutang antar-PT"}


def lines_between(prev: Dict[str, Any], end: Dict[str, Any], label: str,
                  amap: Optional[Dict[str, Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Selisih baris kumulatif `end` − `prev` per akun → baris eliminasi (Dr/Cr), urutan tetap, nol dibuang."""
    acc = _akun()
    a, b = _neto(prev, acc), _neto(end, acc)
    out: List[Dict[str, Any]] = []
    for peran in _URUT:
        code = acc[peran]
        if any(x["account_code"] == code for x in out):
            continue
        delta = b.get(code, 0) - a.get(code, 0)
        if delta == 0:
            continue
        out.append({"account_code": code, "account_name": ((amap or {}).get(code) or {}).get("name", code),
                    "debit": round(delta / 100, 2) if delta > 0 else 0.0,
                    "credit": round(-delta / 100, 2) if delta < 0 else 0.0,
                    "description": f"{_KET[peran]} {label}"})
    return out


def _ringkas(st: Dict[str, Any]) -> Dict[str, Any]:
    return {k: st[k] for k in FIELD_KEADAAN}


async def _amap() -> Dict[str, Dict[str, Any]]:
    return {a["code"]: a async for a in db.gl_accounts.find({}, {"_id": 0, "code": 1, "name": 1, "type": 1})}


def _impact(lines: List[Dict[str, Any]], amap: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
    from services.consolidation_service import _blank, _classify_line
    total = _blank()
    for ln in lines:
        acc = amap.get(ln.get("account_code"), {})
        c = _classify_line(acc.get("type", ""), ln.get("account_code", ""), ln.get("debit", 0), ln.get("credit", 0))
        for k in total:
            total[k] += c[k]
    return {k: round(v, 2) for k, v in total.items()}


def _entry(f: Dict[str, Any], period_key: str, prev_date: str, end_date: str,
           amap: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    seller = f["seller"]
    nomor = seller.get("number") or f["pair_id"]
    label = f"{nomor} · {label_bulan(period_key)}"
    a, b = state_at(f, prev_date), state_at(f, end_date)
    lines = lines_between(a, b, label, amap)
    td = round(sum(x["debit"] for x in lines), 2)
    tc = round(sum(x["credit"] for x in lines), 2)
    return {
        "name": f"Eliminasi otomatis antar-PT {label}",
        "entity_from": seller.get("seller_entity_id"), "entity_to": seller.get("buyer_entity_id"),
        "effective_date": end_date, "period_key": period_key, "period_label": label_bulan(period_key),
        "note": ("Dihitung otomatis dari data antar-PT bertanggal sampai akhir bulan ini dikurangi keadaan akhir bulan "
                 "sebelumnya: pendapatan & HPP intra-grup, laba yang belum terealisasi (barang masih di dalam grup), "
                 "dan sisa piutang/utang antar-PT."),
        "lines": lines, "total_debit": td, "total_credit": tc,
        "balanced": sum(_sen(x["debit"]) for x in lines) == sum(_sen(x["credit"]) for x in lines),
        "impact": _impact(lines, amap),
        "auto_generated": True, "source_g6_pair_id": f["pair_id"], "source_status": seller.get("status", ""),
        "seller_number": nomor, "cumulative": _ringkas(b), "previous": _ringkas(a),
    }


# ═══════════════════════════════════════════════════════════════════════════
# API mesin
# ═══════════════════════════════════════════════════════════════════════════
async def pair_state(pair_id: str, as_of: str) -> Dict[str, Any]:
    """Keadaan pasangan pada `as_of` — hanya data bertanggal ≤ `as_of` (`[:10]`; kosong = semua data)."""
    f = await facts(pair_id)
    if f is None:
        return {"pair_id": pair_id, "as_of": (as_of or "")[:10], **{k: 0 for k in FIELD_KEADAAN},
                "delivered": False, "unsold_ratio": 1.0}
    return {"pair_id": pair_id, "as_of": (as_of or "")[:10], **state_at(f, as_of or SELAMANYA)}


async def period_entry(pair_id: str, period_key: str) -> Dict[str, Any]:
    """Entri bulan `period_key` (`YYYY-MM`) = keadaan akhir bulan − keadaan akhir bulan sebelumnya (selalu seimbang).
    Tidak menyimpan apa pun."""
    f = await facts(pair_id)
    if f is None:
        return {"source_g6_pair_id": pair_id, "period_key": period_key, "effective_date": akhir_bulan(period_key),
                "lines": [], "total_debit": 0.0, "total_credit": 0.0, "balanced": True}
    return _entry(f, period_key, akhir_bulan_sebelumnya(period_key), akhir_bulan(period_key), await _amap())


def baris_berbeda(old: Any, new: Any) -> bool:
    """Bandingkan baris (akun + nilai) — urutan & keterangan diabaikan."""
    def key(rows: Any) -> List[Tuple[str, int, int]]:
        return sorted((str(r.get("account_code")), _sen(r.get("debit")), _sen(r.get("credit"))) for r in (rows or []))
    return key(old) != key(new)


async def _bulan_tertutup(entity_id: str, period_key: str, cache: Dict[Tuple[str, str], bool]) -> bool:
    k = (entity_id or "", period_key)
    if k not in cache:
        from services.closing_service import status_for_date
        cache[k] = bool(entity_id) and bool((await status_for_date(akhir_bulan(period_key), entity_id)).get("closed"))
    return cache[k]


async def bulan_beku(seller_entity_id: str, buyer_entity_id: str, period_key: str,
                     cache: Optional[Dict[Tuple[str, str], bool]] = None) -> bool:
    """Bulan sudah ditutup di PT penjual DAN PT pembeli."""
    cache = {} if cache is None else cache
    return await _bulan_tertutup(seller_entity_id, period_key, cache) and \
        await _bulan_tertutup(buyer_entity_id, period_key, cache)


def _stale_row(f: Dict[str, Any], stored: Dict[str, Any], hitung: Dict[str, Any]) -> Dict[str, Any]:
    s = f["seller"]
    pk = stored.get("period_key", "")
    return {"pair_id": f["pair_id"], "number": s.get("number", ""), "period_key": pk,
            "period_label": label_bulan(pk) if pk else "", "entry_id": stored.get("id", ""),
            "seller_entity_id": s.get("seller_entity_id"), "buyer_entity_id": s.get("buyer_entity_id"),
            "stored_total": stored.get("total_debit", 0.0), "recomputed_total": hitung.get("total_debit", 0.0)}


async def sync_period(period_key: str = "", pair_id: str = "") -> Dict[str, Any]:
    """Pembangun ulang entri bulan (`02` D2). Menulis entri bulan yang BELUM beku (dibuat, diperbarui, atau dihapus bila
    kosong); bulan beku (tertutup di kedua PT) yang sudah tersimpan beku hanya dibandingkan — yang berbeda dari hitung
    ulang dikembalikan di `stale`. Bulan tertutup yang belum punya entri beku ditulis sekali dengan `frozen=True`.

    `period_key` kosong = semua bulan yang punya data; `pair_id` kosong = semua pasangan bukan draf. Entri lama tanpa
    `period_key` TIDAK disentuh (itu tugas skrip migrasi `scripts/migrasi_pk31_eliminasi_per_periode.py`, H3)."""
    from pymongo.errors import DuplicateKeyError
    q: Dict[str, Any] = {"role": "seller", "status": {"$ne": "draft"}}
    if pair_id:
        q["pair_id"] = pair_id
    amap = await _amap()
    kode = await _kode_akun()
    cache: Dict[Tuple[str, str], bool] = {}
    out: Dict[str, Any] = {"created": 0, "updated": 0, "removed": 0, "skipped_existing": 0, "frozen": 0,
                           "pairs_seen": 0, "stale": [], "entries": []}
    async for seller in db.interco_transactions.find(q, {"_id": 0}):
        pid = seller["pair_id"]
        f = await facts(pid, seller, kode)
        out["pairs_seen"] += 1
        qe: Dict[str, Any] = {"source_g6_pair_id": pid, "period_key": {"$exists": True, "$nin": [None, ""]}}
        if period_key:
            qe["period_key"] = period_key
        existing = {e["period_key"]: e async for e in db[COLL].find(qe, {"_id": 0})}
        months = [period_key] if period_key else sorted(set(f["months"]) | set(existing))
        for m in months:
            e = _entry(f, m, akhir_bulan_sebelumnya(m), akhir_bulan(m), amap)
            prev = existing.get(m)
            beku = await bulan_beku(seller.get("seller_entity_id"), seller.get("buyer_entity_id"), m, cache)
            if prev and prev.get("frozen") and beku:
                out["frozen"] += 1
                if baris_berbeda(prev.get("lines"), e["lines"]):
                    out["stale"].append(_stale_row(f, prev, e))
                continue
            if not e["lines"]:
                if prev:
                    await db[COLL].delete_one({"id": prev["id"]})
                    out["removed"] += 1
                continue
            doc = {**e, "frozen": beku, "updated_at": now_iso()}
            if prev:
                sama = (not baris_berbeda(prev.get("lines"), e["lines"]) and bool(prev.get("frozen")) == beku
                        and prev.get("cumulative") == e["cumulative"] and prev.get("name") == e["name"])
                if sama:
                    out["skipped_existing"] += 1
                    continue
                await db[COLL].update_one({"id": prev["id"]}, {"$set": doc})
                out["updated"] += 1
                out["entries"].append(safe_doc({**prev, **doc}))
                continue
            baru = {"id": new_id("icelim"), **doc, "created_by": "system", "created_by_id": None,
                    "created_at": now_iso()}
            try:
                await db[COLL].insert_one(dict(baru))
            except DuplicateKeyError:   # sinkron bersamaan (indeks unik pasangan+bulan): yang menang sudah menulis
                out["skipped_existing"] += 1
                continue
            out["created"] += 1
            out["entries"].append(safe_doc(baru))
    return out


async def pair_entries(f: Dict[str, Any], as_of: str,
                       amap: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Entri eliminasi SATU pasangan sampai `as_of` → `(entri, stale)` — aturan bulan sama dengan `eliminations_for`
    (dipakai laporan konsolidasi dan rapor margin, supaya keduanya membaca angka yang sama)."""
    as_of = (as_of or SELAMANYA)[:10]
    amap = amap if amap is not None else await _amap()
    pid = f["pair_id"]
    beku = {e["period_key"]: e async for e in db[COLL].find(
        {"source_g6_pair_id": pid, "frozen": True, "period_key": {"$exists": True, "$nin": [None, ""]}}, {"_id": 0})}
    months = sorted({m for m in f["months"] if m <= as_of[:7]} | {m for m in beku if akhir_bulan(m) <= as_of})
    out: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []
    for m in months:
        end = akhir_bulan(m)
        if end > as_of:
            e = {**_entry(f, m, akhir_bulan_sebelumnya(m), as_of, amap), "partial": True}
        elif m in beku:
            e = beku[m]
            hitung = _entry(f, m, akhir_bulan_sebelumnya(m), end, amap)
            if baris_berbeda(e.get("lines"), hitung["lines"]):
                stale.append(_stale_row(f, e, hitung))
        else:
            e = _entry(f, m, akhir_bulan_sebelumnya(m), end, amap)
        if e.get("lines"):
            out.append({**e, "frozen": bool(e.get("frozen"))})
    return out, stale


async def eliminations_for(as_of: str, year: int,
                           entity_ids: Optional[Iterable[str]] = None) -> Tuple[List[Dict[str, Any]], ...]:
    """Entri eliminasi antar-PT untuk laporan per `as_of` → `(pl, bs, semua, stale)`.

    * Bulan penuh ≤ `as_of`: entri BEKU dari koleksi bila ada (tidak dihitung ulang — angka yang sudah dilaporkan untuk
      bulan tertutup tidak berubah); selain itu dihitung dari data bertanggal (hasilnya sama kapan pun dibuka selama
      tidak ada data mundur).
    * Bulan berjalan (bulan `as_of` yang belum berakhir) dihitung langsung sampai `as_of` dan tidak disimpan.
    * `pl` = entri yang `effective_date`-nya di tahun `year`; `bs` = semua entri ≤ `as_of`.
    * `stale` = entri beku yang berbeda dari hitung ulang (ada jurnal mundur ke bulan tertutup).
    Baca murni — tidak menulis apa pun (CX-09)."""
    as_of = (as_of or tanggal_buku())[:10]
    perimeter = set(entity_ids) if entity_ids is not None else None
    amap = await _amap()
    kode = await _kode_akun()
    used: List[Dict[str, Any]] = []
    stale: List[Dict[str, Any]] = []
    seen: List[str] = []

    def dalam(a: Any, b: Any) -> bool:
        return perimeter is None or (a in perimeter and b in perimeter)
    async for seller in db.interco_transactions.find({"role": "seller", "status": {"$ne": "draft"}}, {"_id": 0}):
        if not dalam(seller.get("seller_entity_id"), seller.get("buyer_entity_id")):
            continue
        seen.append(seller["pair_id"])
        ent, st = await pair_entries(await facts(seller["pair_id"], seller, kode), as_of, amap)
        used.extend(ent)
        stale.extend(st)
    # Entri beku yang dokumennya sudah tidak ada tetap bagian laporan bulan tertutup (dilaporkan R6 sebagai basi).
    async for e in db[COLL].find({"frozen": True, "period_key": {"$exists": True, "$nin": [None, ""]},
                                  "source_g6_pair_id": {"$nin": seen}}, {"_id": 0}):
        if dalam(e.get("entity_from"), e.get("entity_to")) and (e.get("effective_date") or "") <= as_of:
            used.append(e)
    used.sort(key=lambda e: (e.get("effective_date") or "", e.get("seller_number") or "", e.get("source_g6_pair_id")))
    y0, y1 = f"{int(year):04d}-01-01", f"{int(year):04d}-12-31"
    pl = [e for e in used if y0 <= (e.get("effective_date") or "")[:10] <= y1]
    return pl, list(used), used, stale
