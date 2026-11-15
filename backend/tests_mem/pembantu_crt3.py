"""CR-T3 — pembantu fixture uji gerbang kredit (`docs/blueprint/unit/CR-T3.md`, fixture **G1**).

G1 (FIXTURE SISIP, database tiruan): pelanggan P di PT `entitas`, profil kredit plafon khusus Rp 10.000.000; saldo
tersimpan dari dokumen — pesanan O1 terkirim Rp 6.000.000 (jurnal surat jalan Dr 1-1200, NET30 belum jatuh tempo, atau
telat `telat` hari), pesanan O2 belum dikirim Rp 2.000.000, titipan pelanggan Rp 500.000 →
eksposur = 6.000.000 + 2.000.000 − 500.000 = 7.500.000.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

KSC, KANDA = "ent_ksc", "ent_kanda"
JUTA = 1_000_000


def uid(awal: str) -> str:
    return f"{awal}_crt3_{uuid.uuid4().hex[:8]}"


def iso(dt: datetime) -> str:
    return dt.isoformat()


async def jurnal_kirim(oid: str, entitas: str, nilai: float, tanggal: str, sj: str) -> None:
    """Jurnal pendapatan surat jalan (bentuk `post_shipment_revenue`: Dr piutang / Cr pendapatan, `ref.order_id`)."""
    from services import gl_service as gl
    await gl._insert_entry(lines=[{"account_code": "1-1200", "debit": nilai, "credit": 0.0},   # noqa: SLF001
                                  {"account_code": "4-1000", "debit": 0.0, "credit": nilai}],
                           description=f"Pengakuan penjualan {oid} · {sj}", date=tanggal, source_type="shipment_revenue",
                           source_id=sj, entity_id=entitas, created_by="uji", source_label=sj,
                           ref={"order_id": oid, "order_number": f"SO-{oid}"})


def tanggal_mundur(hari: int) -> str:
    from services.book_date import tanggal_buku
    return (datetime.fromisoformat(tanggal_buku()) - timedelta(days=hari)).date().isoformat()


async def pesanan_terkirim(db, cid: str, entitas: str, nilai: float, *, telat: int = 0, term: str = "NET30",
                           oid: str = "") -> str:
    """Pesanan terkirim seluruhnya `nilai` belum dibayar. `telat` > 0 → syarat 0 hari dan surat jalan `telat` hari lalu
    (telat tepat `telat` hari); 0 → NET30, surat jalan kemarin (belum jatuh tempo)."""
    oid = oid or uid("so")
    now = datetime.now(timezone.utc)
    await db.sales_orders.insert_one({
        "id": oid, "number": f"SO-{oid}", "customer_id": cid, "customer_name": cid, "entity_id": entitas,
        "status": "shipped", "payment_status": "unpaid", "grand_total": nilai, "total_amount": nilai,
        "payments": [], "payment_term_days": 0 if telat else 30, "payment_term_code": term,
        "created_at": iso(now - timedelta(days=max(telat, 1) + 2)), "updated_at": iso(now)})
    await jurnal_kirim(oid, entitas, nilai, tanggal_mundur(telat if telat else 1), f"sj_{oid}")
    return oid


async def pesanan_terbuka(db, cid: str, entitas: str, nilai: float, *, term: str = "NET30", oid: str = "",
                          status: str = "confirmed") -> str:
    """Pesanan hidup belum dikirim senilai `nilai` (bagian `open_orders_amount`)."""
    oid = oid or uid("so")
    now = datetime.now(timezone.utc)
    await db.sales_orders.insert_one({
        "id": oid, "number": f"SO-{oid}", "customer_id": cid, "customer_name": cid, "entity_id": entitas,
        "status": status, "payment_status": "unpaid", "grand_total": nilai, "total_amount": nilai, "payments": [],
        "payment_term_code": term, "payment_term_days": 30, "items": [], "created_at": iso(now), "updated_at": iso(now)})
    return oid


async def profil(db, cid: str, entitas: str, *, plafon: Optional[float] = 10 * JUTA, **lain: Any) -> None:
    """Profil kredit tersimpan (FIXTURE): plafon khusus + isian lain (`credit_status`, `allowed_term_codes`, …)."""
    from services import credit_profile_service as cps
    doc = {**cps.DASAR, "id": uid("ccp"), "customer_id": cid, "entity_id": entitas, "version": 1,
           "created_at": iso(datetime.now(timezone.utc)), **lain}
    if plafon is not None:
        doc.update(limit_mode=cps.MODE_KHUSUS, credit_limit=float(plafon))
    await db.customer_credit_profiles.update_one({"customer_id": cid, "entity_id": entitas}, {"$set": doc},
                                                 upsert=True)


async def g1(db, *, entitas: str = KANDA, nama: str = "", telat: int = 0, sales_id: str = "",
             titipan: float = 500_000, terkirim: float = 6 * JUTA, terbuka: Optional[float] = 2 * JUTA,
             plafon: Optional[float] = 10 * JUTA, **profil_lain: Any) -> Dict[str, Any]:
    """Fixture G1 (lihat kepala modul). `terbuka=None` = tanpa O2 (dibuat lewat API oleh pemanggil)."""
    cid = uid("cus")
    adr = uid("adr")
    await db.customers.insert_one({
        "id": cid, "name": nama or f"Toko G1 {cid[-4:]}", "entity_id": entitas, "status": "active",
        "assigned_sales_id": sales_id, "deposit_balance": float(titipan),
        "addresses": [{"id": adr, "label": "Utama", "city": "Bandung", "address": "Jl. Uji Kredit 3",
                       "recipient_name": "Bu Uji", "phone": "081200000000"}],
        "created_at": iso(datetime.now(timezone.utc))})
    if plafon is not None or profil_lain:
        await profil(db, cid, entitas, plafon=plafon, **profil_lain)
    o1 = await pesanan_terkirim(db, cid, entitas, terkirim, telat=telat) if terkirim else ""
    o2 = await pesanan_terbuka(db, cid, entitas, terbuka) if terbuka else ""
    return {"cid": cid, "adr": adr, "o1": o1, "o2": o2, "entitas": entitas}


async def atur(key: str, nilai: Any, entitas: str = KANDA) -> None:
    from services import config_resolver as resolver
    await resolver.set_value(key, nilai, scope_type="entity", scope_id=entitas, reason="uji CR-T3", actor="uji")


async def cabut(key: str, entitas: str = KANDA) -> None:
    from services import config_resolver as resolver
    await resolver.clear_layer(key, scope_type="entity", scope_id=entitas, actor="uji", reason="pulihkan uji CR-T3")


def kode(hasil: Dict[str, Any]) -> list:
    return [r["code"] for r in hasil.get("reasons") or []]
