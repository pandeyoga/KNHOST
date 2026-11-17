"""PR-T4 U13 — sapuan kode jawaban dan jumlah baris 13 peran bawaan (docs/blueprint/unit/PR-T4.md).

`data/isi_sebelum_PRT4.json` dibuat dari kode SEBELUM unit ini (langkah kerja 1) di basis data tiruan baru dengan
fixture di `siapkan()` (fixture sisip: dua akun sales `sA`/`sB` masing-masing satu pelanggan, satu pesanan, satu
pengajuan harga, satu permohonan kredit; satu permintaan desain untuk akun Desainer; empat notifikasi tanpa tautan
beralamat peran). Isi: untuk tiap (peran bawaan, rute) kode jawaban dan "jumlah baris" (`ringkas()`). Sesudah unit
harus SAMA — nilai awal sifat peran (cakupan data, kategori kerja, meja, alamat notifikasi) = perilaku hari ini.

Membuat ulang berkas "sebelum" (hanya dari kode lama): `KN_TULIS_SEBELUM_PRT4=1 python -m pytest
tests_mem/test_PRT4_sapuan.py -p no:cacheprovider` — tes menulis berkas lalu dilewati.
Modul sendiri (basis data sendiri): uji lain yang mengubah sifat peran tidak memengaruhi sapuan ini.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytestmark = pytest.mark.anyio

BERKAS_SEBELUM = Path(__file__).parent / "data" / "isi_sebelum_PRT4.json"

PERAN_BAWAAN = ["admin", "sales", "manager", "sales_admin", "finance", "warehouse", "designer", "md",
                "warehouse_admin", "driver", "sample_admin", "md_quality", "qc"]

RUTE = ["/api/customers", "/api/sales-orders", "/api/price-approvals", "/api/credit-overrides",
        "/api/design-requests", "/api/sales/kpi?sales_id={sA}", "/api/warehouses?scope=all", "/api/desks/me",
        "/api/notifications"]

WAKTU = "2026-11-10T03:00:00+00:00"


async def siapkan(db, akun) -> Dict[str, Dict[str, Any]]:
    """Akun per peran bawaan + dua akun sales (`sA`, `sB`) dan dokumen ber-pemilik untuk keduanya (fixture sisip)."""
    akun_peran = {p: await akun(p, email=f"prt4.{p}@uji.id") for p in PERAN_BAWAAN}
    sA = await akun("sales", email="prt4.sa@uji.id")
    sB = await akun("sales", email="prt4.sb@uji.id")
    for kode, s in (("A", sA), ("B", sB)):
        await db.customers.insert_one({
            "id": f"cust_prt4_{kode}", "code": f"CUST-PRT4{kode}", "name": f"Pelanggan PRT4 {kode}",
            "entity_id": "ent_ksc", "assigned_sales_id": s["id"], "assigned_sales_name": s["name"], "status": "active",
            "segment": "retail", "created_at": WAKTU, "updated_at": WAKTU})
        await db.sales_orders.insert_one({
            "id": f"so_prt4_{kode}", "number": f"SO-PRT4-{kode}", "entity_id": "ent_ksc", "order_type": "regular",
            "customer_id": f"cust_prt4_{kode}", "customer_name": f"Pelanggan PRT4 {kode}", "created_by": s["id"],
            "sales_id": s["id"], "sales_name": s["name"], "status": "waiting_approval", "items": [],
            "grand_total": 1_000_000, "created_at": WAKTU, "updated_at": WAKTU})
        await db.price_approvals.insert_one({
            "id": f"pra_prt4_{kode}", "entity_id": "ent_ksc", "customer_id": f"cust_prt4_{kode}",
            "customer_name": f"Pelanggan PRT4 {kode}", "product_id": "prd_prt4", "requested_by": s["id"],
            "requested_by_name": s["name"], "status": "pending", "normal_price": 50_000, "requested_price": 45_000,
            "created_at": WAKTU})
        await db.credit_overrides.insert_one({
            "id": f"cro_prt4_{kode}", "entity_id": "ent_ksc", "customer_id": f"cust_prt4_{kode}",
            "requested_by_id": s["id"], "requested_by": s["name"], "status": "pending", "created_at": WAKTU})
    await db.design_requests.insert_one({
        "id": "dr_prt4_1", "number": "DR-PRT4-1", "entity_id": "ent_ksc", "status": "assigned",
        "assigned_to": akun_peran["designer"]["id"], "assigned_name": akun_peran["designer"]["name"],
        "brief": "uji PR-T4", "created_at": WAKTU, "updated_at": WAKTU})
    await db.design_requests.insert_one({
        "id": "dr_prt4_2", "number": "DR-PRT4-2", "entity_id": "ent_ksc", "status": "submitted", "assigned_to": "",
        "brief": "uji PR-T4 belum ditugaskan", "created_at": WAKTU, "updated_at": WAKTU})
    for peran in ("warehouse", "sales", "manager", "all"):
        await db.notifications.insert_one({
            "id": f"ntf_prt4_{peran}", "type": "info", "title": f"Uji PR-T4 untuk {peran}", "body": "",
            "recipient_role": peran, "recipient_user": "", "entity_id": "ent_ksc", "severity": "info",
            "read": False, "created_at": WAKTU})
    return {"peran": akun_peran, "sA": sA, "sB": sB}


def ringkas(rute: str, data: Any, diri: str, sA: str) -> Any:
    """"Jumlah baris" satu jawaban (bentuk sama di kode lama dan baru)."""
    if rute.startswith("/api/sales/kpi"):
        sid = (data or {}).get("sales_id")
        return {"untuk": "sA" if sid == sA else ("diri" if sid == diri else "lain"),
                "pesanan": (data or {}).get("orders_count")}
    if rute == "/api/desks/me":
        return {"judul": data.get("title"), "antrean": len(data.get("queues") or []),
                "item": data.get("total_items")}
    if isinstance(data, list):
        return len(data)
    if isinstance(data, dict):
        for k in ("items", "rows", "data"):
            if isinstance(data.get(k), list):
                return len(data[k])
    return None


async def sapu(klien, sesi, siap) -> Dict[str, Dict[str, List[Any]]]:
    out: Dict[str, Dict[str, List[Any]]] = {}
    sA = siap["sA"]["id"]
    for peran in [*PERAN_BAWAAN, "sales:sA"]:   # + akun sA: pemilik dokumen melihat miliknya
        u = siap["sA"] if peran == "sales:sA" else siap["peran"][peran]
        h = await sesi(u)
        isi: Dict[str, List[Any]] = {}
        for rute in RUTE:
            r = await klien.get(rute.format(sA=sA), headers=h)
            n = ringkas(rute, r.json(), u["id"], sA) if r.status_code == 200 else None
            isi[rute] = [r.status_code, n]
        out[peran] = isi
    return out


async def test_U13_kode_dan_jumlah_baris_peran_bawaan_sama_dengan_sebelum(klien, akun, sesi, db):
    siap = await siapkan(db, akun)
    sesudah = await sapu(klien, sesi, siap)
    if os.environ.get("KN_TULIS_SEBELUM_PRT4") == "1":
        BERKAS_SEBELUM.write_text(json.dumps(sesudah, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
        pytest.skip("berkas 'sebelum' ditulis")
    sebelum = json.loads(BERKAS_SEBELUM.read_text())
    assert sorted(sebelum) == sorted([*PERAN_BAWAAN, "sales:sA"])
    # K-FIN-01 (pemilik 17 Nov 2026 malam: Finance memegang akses yang sama dengan Manajer) — kode Finance = kode Manajer.
    beda = [(p, rute, sebelum[p].get(rute), v) for p, rutes in sesudah.items() for rute, v in rutes.items()
            if sebelum[p].get(rute) != v and not (p == "finance" and v == sesudah["manager"].get(rute))]
    assert not beda, beda
    # Bunyi U13 — Manajer termasuk: melihat KPI sA dan kedua pelanggan sA/sB; Sales melihat miliknya saja.
    assert sesudah["manager"]["/api/sales/kpi?sales_id={sA}"][1]["untuk"] == "sA"
    assert sesudah["sales"]["/api/sales/kpi?sales_id={sA}"][1]["untuk"] == "diri"
    assert sesudah["sales:sA"]["/api/customers"] == [200, 1]
