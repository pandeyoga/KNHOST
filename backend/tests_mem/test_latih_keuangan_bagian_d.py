"""Pelatihan Keuangan 18 Nov — temuan uji jalan bagian D (orientasi, buku besar & jejak dokumen).

U1 (F01) — kartu "Selisih bayar perlu diputus" di Beranda Keuangan › Perlu Tindakan.

Temuan uji jalan: baris antrean `selisih_bayar` (`GET /api/finance/desk`) dibangun dari kunci yang tidak dikirim
`payment_variance_service.pending` (`id`, `variance.amount`, `created_at`), sehingga `ref_id` kosong → tombol baris macet
"Memproses…" (DeskQueueCard: busyRef "" === ref_id "") dan NILAI Rp 0.

FIXTURE (disisipkan langsung): satu kwitansi KSC kurang bayar — dana 9.618.461, tagihan tujuan 24.046.152.
Hitung tangan: selisih = 9.618.461 − 24.046.152 = −14.427.691 → nilai baris = |−14.427.691| = 14.427.691, arah "under"
→ keterangan "kurang bayar"; ref_id = id kwitansi.

U3 (F17) — Profitabilitas › Pencocokan ke Laba-Rugi: pendapatan di luar penjualan barang (denda 4-9300) dulu jatuh ke
"Selisih belum dijelaskan". FIXTURE: PT `ent_uji_rec`, 15 Okt: Dr 1-1200 1.000.000 / Cr 4-1000 1.000.000 (kirim),
Dr 5-1000 600.000 / Cr 1-1300 600.000 (HPP), Dr 1-1270 50.000 / Cr 4-9300 50.000 (denda). Marjin layar = 400.000.
Hitung tangan: laba kotor L/R = (1.000.000 + 50.000) − 600.000 = 450.000; pendapatan lain = 50.000;
selisih = 450.000 − (400.000 + 0 + 0 + 50.000) = 0.

U2 (F16) — simpul Jurnal di Jejak Dokumen membawa nilai jurnal (`total_debit`); dulu 0 → layar tidak menulis nilai.
Hitung tangan: jurnal penerimaan Dr 1-1100 3.273.390 / Cr 1-1200 3.273.390 → nilai simpul 3.273.390.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.anyio

ADMIN = "admin@kainnusantara.id"


async def test_baris_selisih_bayar_berid_dan_bernilai(klien, db, sesi):
    await db.ar_receipts.insert_one({
        "id": "arc_uji_selisih", "number": "KSC/AR-UJI01", "entity_id": "ent_ksc", "customer_id": "cust_uji",
        "customer_name": "Pelanggan Uji Selisih", "receipt_date": "2026-11-17T05:09:38+00:00", "method": "transfer",
        "status": "posted", "total_funds": 9618461, "applied_total": 9618461, "unapplied_amount": 0,
        "created_at": "2026-11-17T05:09:38+00:00",
        "variance": {"expected": 24046152, "funds": 9618461, "delta": -14427691, "direction": "under",
                     "needs_decision": True, "target_order_ids": ["so_uji"], "decision_id": "", "explain": []}})
    h = await sesi(ADMIN)
    r = await klien.get("/api/finance/desk", headers=h, params={"entity_id": "ent_ksc"})
    assert r.status_code == 200, r.text
    q = {x["id"]: x for x in r.json()["queues"]}["selisih_bayar"]
    row = next(x for x in q["rows"] if x["number"] == "KSC/AR-UJI01")
    assert row["ref_id"] == "arc_uji_selisih"
    assert row["value"] == 14427691
    assert row["subtitle"] == "kurang bayar"
    assert row["action_kind"] == "decide_variance"
    assert q["total_value"] >= 14427691


def test_simpul_jurnal_jejak_dokumen_bernilai():
    from services import doc_refs_service as refs
    je = {"id": "je_uji", "number": "KSC/JE-UJI", "entity_id": "ent_ksc", "status": "posted", "date": "2026-11-17",
          "total_debit": 3273390.0, "total_credit": 3273390.0,
          "lines": [{"account_code": "1-1100", "debit": 3273390.0, "credit": 0},
                    {"account_code": "1-1200", "debit": 0, "credit": 3273390.0}]}
    assert refs.node_of("journal_entry", je)["amount"] == 3273390.0
    # dokumen lain tetap memakai kolom nilainya sendiri (grand_total didahulukan)
    assert refs.node_of("sales_order", {"id": "so_x", "number": "SO-X", "grand_total": 10.0, "total_debit": 99})["amount"] == 10.0


async def test_pencocokan_profitabilitas_menjelaskan_pendapatan_denda(db):
    from services import profitability_service as ps
    eid = "ent_uji_rec"
    for i, (lines, st) in enumerate([
            ([("1-1200", 1_000_000, 0), ("4-1000", 0, 1_000_000)], "shipment_revenue"),
            ([("5-1000", 600_000, 0), ("1-1300", 0, 600_000)], "shipment_cogs"),
            ([("1-1270", 50_000, 0), ("4-9300", 0, 50_000)], "penalty")]):
        await db.journal_entries.insert_one({
            "id": f"je_rec_{i}", "number": f"REC-{i}", "entity_id": eid, "status": "posted", "date": "2026-10-15",
            "source_type": st, "source_id": f"src_{i}",
            "lines": [{"account_code": c, "debit": d, "credit": k} for c, d, k in lines],
            "total_debit": sum(d for _, d, _ in lines), "total_credit": sum(k for _, _, k in lines)})
    rows = await ps._reconciliation("2026-10-01", "2026-10-31", {"entity_id": eid}, 400_000)
    got = {r["key"]: r["amount"] for r in rows}
    assert [r["key"] for r in rows] == ["margin", "inventory_adjustments", "interco", "other_income", "unexplained",
                                        "gross_profit_pl"]
    assert got["gross_profit_pl"] == 450_000
    assert got["other_income"] == 50_000
    assert got["unexplained"] == 0
