"""TX-T2 U17 — di MongoDB ASLI (lingkungan A): dua `draft_for_shipment` bersamaan untuk satu surat jalan.

Jalankan di container backend (database uji lokal `MONGO_URL`/`DB_NAME`, BUKAN database berisi data nyata). Layanan
dipanggil di dalam proses (motor ke MongoDB asli) supaya dua panggilan benar-benar bersamaan dan indeks unik parsial
`tax_invoices.uq_fkt_active` (PK-40) yang memutuskan — database tiruan lapis B tidak menegakkan balapan.

Persiapan (fixture, disisip langsung): PT uji PKP `ent_bp_txt2_<tag>` berpemicu `surat_jalan` (lapisan PT, lewat
`config_resolver.set_value`; dicabut sesudahnya), pelanggan ber-NPWP, pesanan T1 (10.000.000 + PPN 1.100.000), surat
jalan SJ-1 40 m berjurnal `shipment_revenue` Dr 1-1200 4.440.000 / Cr 4-1000 4.000.000 / Cr 2-1200 440.000.

  U17  dua panggilan serentak (beberapa putaran) → tepat satu draf ber-`active_key` `sj:{pesanan}:SJ-1`, keduanya
       mengembalikan dokumen ber-id sama, tanpa galat ke pemanggil.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _dunia(db, tag):
    eid, so, cus, shp = f"ent_bp_txt2_{tag}", f"so_bp_txt2_{tag}", f"cus_bp_txt2_{tag}", f"shp_bp_txt2_{tag}"
    await db.business_entities.insert_one({"id": eid, "code": f"BT{tag[:4]}", "name": f"PT Uji TX-T2 {tag}",
                                           "legal_name": f"PT Uji TX-T2 {tag}", "status": "active", "is_active": True,
                                           "default_tax_mode": "ppn", "created_at": _now()})
    await db.customers.insert_one({"id": cus, "name": f"Toko {tag}", "entity_id": eid, "status": "active",
                                   "npwp": "07.111.222.3-444.000",
                                   "addresses": [{"address": "Jl. Uji", "city": "Bandung", "is_primary": True}]})
    snap = {"ppn_rate": 12.0, "dpp_nilai_lain": True, "dpp_pembilang": 11, "dpp_penyebut": 12, "ppn_mode": "excluded",
            "pembulatan_tingkat": "dokumen", "pembulatan_satuan": "dua_desimal", "is_pkp": True, "berlaku_pada": _now()}
    await db.sales_orders.insert_one({
        "id": so, "number": f"SO-BPTX2-{tag}", "entity_id": eid, "customer_id": cus, "customer_name": f"Toko {tag}",
        "status": "partially_shipped", "items": [{"product_id": f"p_{tag}", "product_name": "Kain", "quantity": 100,
                                                   "unit": "meter", "price": 100_000, "line_total": 10_000_000}],
        "total_amount": 10_000_000.0, "net_subtotal": 10_000_000.0, "dpp": 9_166_666.67, "dpp_nilai_lain": True,
        "ppn_rate": 12.0, "ppn_mode": "excluded", "ppn_amount": 1_100_000.0, "grand_total": 11_100_000.0,
        "is_pkp": True, "tax_snapshot": snap, "payments": [], "created_at": _now()})
    await db.shipments.insert_one({"id": shp, "shipment_no": "SJ-1", "entity_id": eid, "order_id": so,
                                   "product_id": f"p_{tag}", "qty": 40, "unit": "meter", "status": "dispatched",
                                   "created_at": _now()})
    await db.journal_entries.insert_one({
        "id": f"je_bp_txt2_{tag}", "number": f"JE-BPTX2-{tag}", "date": _now()[:10], "status": "posted",
        "source": "shipment_revenue", "source_type": "shipment_revenue", "source_id": shp, "entity_id": eid,
        "ref": {"order_id": so},
        "lines": [{"account_code": "1-1200", "debit": 4_440_000.0, "credit": 0.0},
                  {"account_code": "4-1000", "debit": 0.0, "credit": 4_000_000.0},
                  {"account_code": "2-1200", "debit": 0.0, "credit": 440_000.0}],
        "total_debit": 4_440_000.0, "total_credit": 4_440_000.0, "created_by": "uji", "created_at": _now()})
    return eid, so


async def _putaran():
    from db import db
    from services import tax_invoice_service as tis
    from services.config_resolver import set_value, clear_layer
    tag = uuid.uuid4().hex[:8]
    eid, so = await _dunia(db, tag)
    await set_value("tax.pemicu_faktur", "surat_jalan", scope_type="entity", scope_id=eid, actor="uji",
                    reason="uji U17 TX-T2")
    try:
        hasil = await asyncio.gather(tis.draft_for_shipment(so, "SJ-1"), tis.draft_for_shipment(so, "SJ-1"),
                                     return_exceptions=True)
        assert not [h for h in hasil if isinstance(h, BaseException)], hasil
        assert hasil[0]["id"] == hasil[1]["id"], hasil
        n = await db.tax_invoices.count_documents({"order_id": so, "active_key": f"sj:{so}:SJ-1"})
        assert n == 1, n
        assert await db.tax_invoices.count_documents({"order_id": so}) == 1
    finally:
        await clear_layer("tax.pemicu_faktur", scope_type="entity", scope_id=eid, actor="uji", reason="uji U17 selesai")


def test_TXT2_U17_dua_draf_bersamaan_satu_draf():
    assert os.environ.get("MONGO_URL"), "lapis A: butuh MongoDB asli (MONGO_URL)"
    for _ in range(3):   # beberapa putaran: balapan tidak selalu muncul di satu percobaan
        asyncio.run(_putaran())
