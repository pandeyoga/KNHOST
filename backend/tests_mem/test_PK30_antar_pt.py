"""PK-30 — antar-PT: dokumen mengikuti panjang roll aktual (IC-02), jalur transfer lama ditutup (IC-09), harga dan PPN di
luar kontrak hanya dengan izin + alasan, penjual non-PKP tidak memungut PPN (IC-10). Spesifikasi
`docs/blueprint/unit/PK-30.md`. U15 (dua persetujuan tugas gudang bersamaan) di MongoDB asli:
`backend/tests/test_bp_PK30_persetujuan_bersamaan.py`; U16 = uji jalan layar.

Persiapan bersama (fixture `siap`, disisipkan langsung): produk `prd_pk30` (meter), gudang bersama `wh_pk30`, kontrak
internal Rp 25.000/m untuk KSC→Kanda, Kanda→KSC, dan KSC→PT uji ketiga (PKP); roll penjual berbiaya Rp 18.000/m;
`antar_entitas.ppn_mode` lapisan `ent_ksc` = `tanpa_ppn` (lewat API Pusat Pengaturan).
Alur (lewat API): Manajer membuat dan mengonfirmasi transaksi; roll pilihan dipasang di baris dokumen (fixture — isian
`preferred_roll_ids` hanya lahir dari Permintaan Internal); Manajer menerbitkan tugas gudang; Admin Gudang menyetujuinya.

Hitungan tangan dasar: pesan 100 m × Rp 25.000 = Rp 2.500.000. Roll 130 m → 130 × 25.000 = Rp 3.250.000, selisih
30 × 25.000 = Rp 750.000; HPP penjual 130 × 18.000 = Rp 2.340.000. Roll 90 m → 90 × 25.000 = Rp 2.250.000, selisih
−10 × 25.000 = −Rp 250.000. PPN antar-PT = 12 % × DPP 11/12 = tarif efektif 11 %.

Uji `test_PK30_a_*` memanggil dua fungsi baru langsung (serah-terima a): transaksi lewat API, reservasi roll
disisipkan langsung (fixture).
"""
import re
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import pt_uji, tutup_periode
from services import interco_service as ics
from services.book_date import periode_buku

JT = 1_000_000
KSC, KANDA = "ent_ksc", "ent_kanda"
P1, WH = "prd_pk30", "wh_pk30"
HARGA, BIAYA = 25_000, 18_000
KUNCI = "antar_entitas.selisih_panjang"
ROOT = Path(__file__).resolve().parents[2]

PESAN_403 = ("Anda belum punya akses untuk mengubah harga atau PPN antar-PT di luar kontrak. Minta Admin menambahkan "
             "akses 'Transaksi Antar Badan Usaha'.")
PESAN_ALASAN = "Alasan mengubah harga atau PPN wajib diisi (minimal 5 huruf)."
PESAN_410 = ("Transfer antar-PT lewat jalur ini sudah ditutup. Buat Permintaan Internal dari keranjang, atau transaksi "
             "di menu Antar-PT.")
PESAN_409_LAMA = ("Transfer antar-PT ini dibuat lewat jalur lama yang sudah ditutup. Tolak transfer ini, lalu buat "
                  "Permintaan Internal atau transaksi Antar-PT.")


def pesan_panjang(aktual: str, pesanan: str) -> str:
    return (f"Panjang roll yang dipilih ({aktual} meter) tidak sama dengan jumlah pada transaksi antar-PT ({pesanan} "
            "meter). Pilih roll lain, atau ubah pengaturan \"Bila panjang roll beda dari pesanan antar-PT\".")


def _isi(key, value, scope_type, scope_id, reason="uji PK-30"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


async def atur(klien, h, key, value, scope_type="entity", scope_id=KSC):
    r = await klien.put("/api/config/values", headers=h, json=_isi(key, value, scope_type, scope_id))
    assert r.status_code == 200, r.text


async def pulihkan(klien, h, key, scope_type="entity", scope_id=KSC):
    if scope_type == "entity":
        r = await klien.post("/api/config/values/clear", headers=h,
                             json={"key": key, "scope_type": "entity", "scope_id": scope_id, "reason": "pulihkan"})
    else:
        r = await klien.post("/api/config/values/reset", headers=h,
                             json={"key": key, "scope_type": "global", "reason": "pulihkan"})
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
async def siap(klien, kepala_admin, db, akun, sesi):
    pt3 = await pt_uji("TGA")   # PT ketiga ber-PKP (U3)
    await db.products.insert_one({"id": P1, "sku": "PK30-001", "name": "Kain Uji PK-30", "base_unit": "meter",
                                  "is_active": True, "status": "active", "created_at": now_iso()})
    await db.warehouses.insert_one({"id": WH, "code": "WH-PK30", "name": "Gudang Bersama PK-30", "is_active": True,
                                    "status": "active", "created_at": now_iso()})
    for i, (s, b) in enumerate(((KSC, KANDA), (KANDA, KSC), (KSC, pt3))):
        await db.supplier_contracts.insert_one({
            "id": f"ctr_pk30_{i}", "contract_number": f"KTR-PK30-{i}", "entity_id": s, "partner_kind": "entity",
            "partner_id": b, "product_id": P1, "status": "active", "tariff_rate": HARGA, "valid_from": "2026-01-01",
            "created_at": now_iso()})
    await atur(klien, kepala_admin, "antar_entitas.ppn_mode", "tanpa_ppn")
    mgr = await akun("manager", entitas=(KSC, KANDA, pt3))
    gdg = await akun("warehouse_admin", entitas=(KSC, KANDA))
    sa = await akun("sales_admin", entitas=(KSC, KANDA))
    return {"pt3": pt3, "mgr": await sesi(mgr), "gdg": await sesi(gdg), "sa": await sesi(sa)}


async def buat_roll(db, panjang, *, ref_transfer: str = "") -> str:
    rid = f"roll_pk30_{uuid.uuid4().hex[:8]}"
    await db.inventory_rolls.insert_one({
        "id": rid, "roll_no": f"R-{rid[-6:]}", "product_id": P1, "warehouse_id": WH, "owner_entity_id": KSC,
        "status": "reserved" if ref_transfer else "available",
        "reserved_ref": {"type": "transfer", "id": ref_transfer} if ref_transfer else None,
        "length_initial": float(panjang), "length_remaining": float(panjang), "unit": "meter", "unit_cost": BIAYA,
        "base_unit_cost": BIAYA, "lot": "LOT-PK30", "active_movement": None, "created_at": now_iso()})
    return rid


def isi_transaksi(qty=100, *, seller=KSC, buyer=KANDA, **lain):
    baris = {"product_id": P1, "quantity": qty}
    if "unit_price" in lain:
        baris["unit_price"] = lain.pop("unit_price")
    return {"seller_entity_id": seller, "buyer_entity_id": buyer, "items": [baris], **lain}


async def transaksi_terkonfirmasi(klien, db, siap, qty, *, buyer=KANDA, roll_ids=()):
    r = await klien.post("/api/interco/transactions", headers=siap["mgr"], json=isi_transaksi(qty, buyer=buyer))
    assert r.status_code == 200, r.text
    pair = r.json()
    pid, sid = pair["pair_id"], pair["seller"]["id"]
    if roll_ids:
        await db.interco_transactions.update_many({"pair_id": pid},
                                                  {"$set": {"items.0.preferred_roll_ids": list(roll_ids)}})
    r = await klien.post(f"/api/interco/transactions/{sid}/confirm", headers=siap["mgr"], json={"note": ""})
    assert r.status_code == 200 and not r.json().get("warning"), r.text
    return pid, sid, pair["buyer"]["id"]


async def alur(klien, db, siap, qty, panjang, *, buyer=KANDA, setujui=True):
    rid = await buat_roll(db, panjang)
    pid, sid, bid = await transaksi_terkonfirmasi(klien, db, siap, qty, buyer=buyer, roll_ids=[rid])
    out = {"pid": pid, "sid": sid, "bid": bid, "rid": rid}
    out["task"] = await klien.post(f"/api/interco/transactions/{sid}/warehouse-task", headers=siap["mgr"],
                                   json={"note": ""})
    if out["task"].status_code == 200:
        out["tid"] = out["task"].json()["id"]
        if setujui:
            out["approve"] = await setujui_tugas(klien, siap, out["tid"])
    return out


async def setujui_tugas(klien, siap, tid):
    return await klien.post(f"/api/transfers/{tid}/approve", headers=siap["gdg"], json={"approved_by": "Admin Gudang"})


async def baris(db, pid, akhiran):
    """Jurnal `{pid}:{akhiran}` → (PT, {akun: (debit, kredit)}) atau None."""
    je = await db.journal_entries.find_one({"source_type": "interco_transaction", "source_id": f"{pid}:{akhiran}",
                                            "status": {"$ne": "void"}}, {"_id": 0})
    if not je:
        return None
    out = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return je["entity_id"], out


async def saldo_pasangan(db, pid, entity_id, akun):
    """Saldo (debit − kredit) satu akun dari SEMUA jurnal pasangan ini di satu PT."""
    total = 0.0
    async for je in db.journal_entries.find({"source_type": "interco_transaction", "entity_id": entity_id,
                                             "status": {"$ne": "void"},
                                             "source_id": {"$regex": "^" + re.escape(pid) + ":"}}):
        for ln in je["lines"]:
            if ln["account_code"] == akun:
                total += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(total, 2)


async def jumlah_je_pasangan(db, pid):
    return await db.journal_entries.count_documents({"source_type": "interco_transaction", "status": {"$ne": "void"},
                                                     "source_id": {"$regex": "^" + re.escape(pid) + ":"}})


async def dokumen(db, pid):
    return {d["role"]: d async for d in db.interco_transactions.find({"pair_id": pid}, {"_id": 0})}


XFAIL_A_IC02 = pytest.mark.xfail(strict=True, reason="IC-02 — pemanggil belum dialihkan ke fungsi baru (serah-terima b)")
XFAIL_A_IC09 = pytest.mark.xfail(strict=True, reason="IC-09 — jalur transfer lama belum ditutup (serah-terima b)")


# ═══ Serah-terima (a): dua fungsi baru diuji langsung (angka U1–U3) ═══════════════════════════════════════════════════
async def siapkan_langsung(klien, db, siap, qty, panjang, *, buyer=KANDA):
    """Transaksi dikonfirmasi lewat API; roll penjual direservasi untuk tugas gudang tiruan (fixture)."""
    pid, sid, bid = await transaksi_terkonfirmasi(klien, db, siap, qty, buyer=buyer)
    tid = f"trn_pk30_{uuid.uuid4().hex[:8]}"
    rid = await buat_roll(db, panjang, ref_transfer=tid)
    transfer = {"id": tid, "code": f"TRF/{tid}", "interco_pair_id": pid, "source_entity_id": KSC,
                "dest_entity_id": buyer, "items": [{"product_id": P1, "qty": qty, "rolls": [{"roll_id": rid}]}]}
    return pid, sid, bid, transfer


async def test_PK30_a_U1_fungsi_langsung_roll_lebih_panjang(klien, db, siap):
    pid, sid, bid, trf = await siapkan_langsung(klien, db, siap, 100, 130)
    n0 = await jumlah_je_pasangan(db, pid)                         # 2 jurnal konfirmasi
    pre = await ics.precheck_warehouse_task(trf)
    assert pre == {"actual": {P1: 130.0}, "differs": True}
    assert await jumlah_je_pasangan(db, pid) == n0                  # pemeriksaan tanpa tulisan
    assert "length_adjustment" not in (await dokumen(db, pid))["seller"]
    res = await ics.apply_length_adjustment(pid, pre["actual"], trf, "Uji PK-30")
    assert res["adjusted"] is True
    # 30 m × 25.000 = 750.000 (tanpa PPN: lapisan ent_ksc = tanpa_ppn)
    assert await baris(db, pid, "adj:seller") == (KSC, {"1-1250": (750_000, 0), "4-1000": (0, 750_000)})
    assert await baris(db, pid, "adj:buyer") == (KANDA, {"1-1310": (750_000, 0), "2-1250": (0, 750_000)})
    docs = await dokumen(db, pid)
    for d in docs.values():
        it = d["items"][0]
        assert (it["quantity_ordered"], it["quantity"], it["line_subtotal"]) == (100, 130, 3_250_000)
        assert (d["subtotal"], d["tax_amount"], d["grand_total"]) == (3_250_000, 0, 3_250_000)
        la = d["length_adjustment"]
        assert la["transfer_id"] == trf["id"]
        assert (la["from_subtotal"], la["to_subtotal"], la["delta_subtotal"], la["delta_tax"], la["delta_total"]) == \
            (2_500_000, 3_250_000, 750_000, 0, 750_000)
        assert la["lines"] == [{"product_id": P1, "from_qty": 100, "to_qty": 130}]
        assert la["by"] == "Uji PK-30" and la["at"]
        assert d["gl_status_adj"] == "posted"
    # ulang: dokumen sudah ber-`length_adjustment.transfer_id` yang sama → apa adanya, tanpa jurnal baru
    res2 = await ics.apply_length_adjustment(pid, pre["actual"], trf, "Uji PK-30")
    assert res2["adjusted"] is False
    await ics.repost_length_adjustment(pid, "Uji PK-30")
    assert await jumlah_je_pasangan(db, pid) == n0 + 2
    assert (await dokumen(db, pid))["seller"]["grand_total"] == 3_250_000
    # saldo antar-PT mengikuti nilai baru
    ica = await db.interco_accounts.find_one({"id": ics.ica_ar_id(KSC, KANDA)}, {"_id": 0})
    assert ica["gross_amount"] >= 3_250_000


async def test_PK30_a_U2_fungsi_langsung_roll_lebih_pendek_dan_pas(klien, db, siap):
    pid, _, _, trf = await siapkan_langsung(klien, db, siap, 100, 90)
    pre = await ics.precheck_warehouse_task(trf)
    assert pre == {"actual": {P1: 90.0}, "differs": True}
    await ics.apply_length_adjustment(pid, pre["actual"], trf, "Uji PK-30")
    # −10 m × 25.000 = −250.000 → arah dibalik, nilai mutlak
    assert await baris(db, pid, "adj:seller") == (KSC, {"4-1000": (250_000, 0), "1-1250": (0, 250_000)})
    assert await baris(db, pid, "adj:buyer") == (KANDA, {"2-1250": (250_000, 0), "1-1310": (0, 250_000)})
    s = (await dokumen(db, pid))["seller"]
    assert (s["items"][0]["quantity"], s["grand_total"], s["length_adjustment"]["delta_total"]) == (90, 2_250_000,
                                                                                                    -250_000)
    # roll pas 100 m: tidak berbeda → tanpa `length_adjustment` dan tanpa jurnal `:adj:`
    pid2, _, _, trf2 = await siapkan_langsung(klien, db, siap, 100, 100)
    pre2 = await ics.precheck_warehouse_task(trf2)
    assert pre2 == {"actual": {P1: 100.0}, "differs": False}
    res = await ics.apply_length_adjustment(pid2, pre2["actual"], trf2, "Uji PK-30")
    assert res["adjusted"] is False
    assert "length_adjustment" not in (await dokumen(db, pid2))["seller"]
    assert await baris(db, pid2, "adj:seller") is None and await baris(db, pid2, "adj:buyer") is None


async def test_PK30_a_U3_fungsi_langsung_ber_ppn(klien, kepala_admin, db, siap):
    await atur(klien, kepala_admin, "antar_entitas.ppn_mode", "ikut_pkp")
    try:
        pid, _, _, trf = await siapkan_langsung(klien, db, siap, 100, 130, buyer=siap["pt3"])
        s = (await dokumen(db, pid))["seller"]
        assert (s["tax_rate"], s["tax_amount"], s["grand_total"]) == (11.0, 275_000, 2_775_000)
        pre = await ics.precheck_warehouse_task(trf)
        await ics.apply_length_adjustment(pid, pre["actual"], trf, "Uji PK-30")
        # DPP 3.250.000 × 11 % = 357.500; selisih PPN 357.500 − 275.000 = 82.500; selisih total 832.500
        la = (await dokumen(db, pid))["seller"]["length_adjustment"]
        assert (la["delta_subtotal"], la["delta_tax"], la["delta_total"]) == (750_000, 82_500, 832_500)
        assert await baris(db, pid, "adj:seller") == (KSC, {"1-1250": (832_500, 0), "4-1000": (0, 750_000),
                                                            "2-1200": (0, 82_500)})
        assert await baris(db, pid, "adj:buyer") == (siap["pt3"], {"1-1310": (750_000, 0), "1-1500": (82_500, 0),
                                                                   "2-1250": (0, 832_500)})
    finally:
        await atur(klien, kepala_admin, "antar_entitas.ppn_mode", "tanpa_ppn")


async def test_PK30_a_U4_fungsi_langsung_tolak_dan_periode(klien, kepala_admin, db, siap):
    pid, _, _, trf = await siapkan_langsung(klien, db, siap, 100, 130)
    await atur(klien, kepala_admin, KUNCI, "tolak")
    try:
        with pytest.raises(ics.IntercoError) as e:
            await ics.precheck_warehouse_task(trf)
        assert str(e.value) == pesan_panjang("130", "100")
    finally:
        await pulihkan(klien, kepala_admin, KUNCI)
    # periode PT pembeli tertutup → pemeriksaan jurnal penyesuaian gagal sebelum ada tulisan
    from services.twin_journal import TwinJournalError
    c = await tutup_periode(KANDA, periode_buku())
    try:
        with pytest.raises(TwinJournalError):
            await ics.precheck_warehouse_task(trf)
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert "length_adjustment" not in (await dokumen(db, pid))["seller"]
    assert await baris(db, pid, "adj:seller") is None


async def test_PK30_a_U6_sisi_pembeli_gagal_diulang_lewat_panel(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    pid, sid, bid, trf = await siapkan_langsung(klien, db, siap, 100, 130)
    pre = await ics.precheck_warehouse_task(trf)
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="interco_transaction", kali=1):
        await ics.apply_length_adjustment(pid, pre["actual"], trf, "Uji PK-30")
    docs = await dokumen(db, pid)
    assert docs["seller"]["gl_status_adj"] == "posted" and docs["buyer"]["gl_status_adj"] == "failed"
    assert await baris(db, pid, "adj:seller") is not None and await baris(db, pid, "adj:buyer") is None
    h = {**kepala_admin, "X-Entity-Id": KANDA}
    panel = (await klien.get("/api/finance/posting-failures", headers=h)).json()
    assert any(i["id"] == bid and i["kind"] == "interco_adj" for i in panel["items"]), panel
    assert panel["labels"]["interco_adj"] == "Penyesuaian Panjang Antar-PT"
    r = await klien.post(f"/api/finance/posting-failures/interco_adj/{bid}/retry", headers=h)
    assert r.status_code == 200 and r.json()["gl_status"] == "posted", r.text
    for akhiran in ("seller", "buyer", "adj:seller", "adj:buyer"):
        assert await db.journal_entries.count_documents({"source_type": "interco_transaction",
                                                         "source_id": f"{pid}:{akhiran}"}) == 1, akhiran


# ═══ U1–U8: alur lewat API ════════════════════════════════════════════════════════════════════════════════════════════
@XFAIL_A_IC02
async def test_PK30_U1_roll_lebih_panjang_dokumen_dan_jurnal_menyesuaikan(klien, db, siap):
    a = await alur(klien, db, siap, 100, 130)
    assert a["task"].status_code == 200, a["task"].text
    assert a["approve"].status_code == 200, a["approve"].text
    pid = a["pid"]
    # konfirmasi (jumlah pesanan)
    assert await baris(db, pid, "seller") == (KSC, {"1-1250": (2_500_000, 0), "4-1000": (0, 2_500_000)})
    assert await baris(db, pid, "buyer") == (KANDA, {"1-1310": (2_500_000, 0), "2-1250": (0, 2_500_000)})
    # penyesuaian 30 × 25.000 = 750.000
    assert await baris(db, pid, "adj:seller") == (KSC, {"1-1250": (750_000, 0), "4-1000": (0, 750_000)})
    assert await baris(db, pid, "adj:buyer") == (KANDA, {"1-1310": (750_000, 0), "2-1250": (0, 750_000)})
    # barang: HPP 130 × 18.000 = 2.340.000; penerimaan = subtotal baru 3.250.000
    assert await baris(db, pid, "cogs") == (KSC, {"5-1000": (2_340_000, 0), "1-1300": (0, 2_340_000)})
    assert await baris(db, pid, "receipt") == (KANDA, {"1-1300": (3_250_000, 0), "1-1310": (0, 3_250_000)})
    roll = await db.inventory_rolls.find_one({"id": a["rid"]}, {"_id": 0})
    assert roll["owner_entity_id"] == KANDA and roll["unit_cost"] == HARGA
    nilai_roll = round(roll["length_remaining"] * roll["unit_cost"], 2)          # 130 × 25.000
    assert nilai_roll == 3_250_000 == await saldo_pasangan(db, pid, KANDA, "1-1300")
    assert await saldo_pasangan(db, pid, KANDA, "1-1310") == 0                   # 2,5 jt + 0,75 jt − 3,25 jt
    assert await saldo_pasangan(db, pid, KSC, "1-1250") == 3_250_000
    assert -await saldo_pasangan(db, pid, KANDA, "2-1250") == 3_250_000
    for d in (await dokumen(db, pid)).values():
        assert d["grand_total"] == 3_250_000
        assert (d["items"][0]["quantity_ordered"], d["items"][0]["quantity"]) == (100, 130)
        assert d["length_adjustment"]["transfer_id"] == a["tid"]


@XFAIL_A_IC02
async def test_PK30_U2_roll_lebih_pendek_dan_roll_pas(klien, db, siap):
    a = await alur(klien, db, siap, 100, 90)
    assert a["task"].status_code == 200, a["task"].text
    assert a["approve"].status_code == 200, a["approve"].text
    pid = a["pid"]
    assert await baris(db, pid, "adj:seller") == (KSC, {"4-1000": (250_000, 0), "1-1250": (0, 250_000)})
    assert await baris(db, pid, "adj:buyer") == (KANDA, {"2-1250": (250_000, 0), "1-1310": (0, 250_000)})
    assert await saldo_pasangan(db, pid, KSC, "1-1250") == 2_250_000
    assert -await saldo_pasangan(db, pid, KANDA, "2-1250") == 2_250_000
    roll = await db.inventory_rolls.find_one({"id": a["rid"]}, {"_id": 0})
    assert round(roll["length_remaining"] * roll["unit_cost"], 2) == 2_250_000 == \
        await saldo_pasangan(db, pid, KANDA, "1-1300")                           # 90 × 25.000
    assert await saldo_pasangan(db, pid, KANDA, "1-1310") == 0
    b = await alur(klien, db, siap, 100, 100)
    assert b["approve"].status_code == 200, b["approve"].text
    assert "length_adjustment" not in (await dokumen(db, b["pid"]))["seller"]
    assert await db.journal_entries.count_documents({"source_type": "interco_transaction",
                                                     "source_id": {"$regex": f"^{b['pid']}:adj:"}}) == 0


@XFAIL_A_IC02
async def test_PK30_U3_ber_ppn_pembeli_pkp(klien, kepala_admin, db, siap):
    await atur(klien, kepala_admin, "antar_entitas.ppn_mode", "ikut_pkp")
    try:
        a = await alur(klien, db, siap, 100, 130, buyer=siap["pt3"])
        assert a["approve"].status_code == 200, a["approve"].text
        pid = a["pid"]
        assert await baris(db, pid, "seller") == (KSC, {"1-1250": (2_775_000, 0), "4-1000": (0, 2_500_000),
                                                        "2-1200": (0, 275_000)})
        la = (await dokumen(db, pid))["seller"]["length_adjustment"]
        assert (la["delta_subtotal"], la["delta_tax"], la["delta_total"]) == (750_000, 82_500, 832_500)
        assert await baris(db, pid, "adj:seller") == (KSC, {"1-1250": (832_500, 0), "4-1000": (0, 750_000),
                                                            "2-1200": (0, 82_500)})
        assert await baris(db, pid, "adj:buyer") == (siap["pt3"], {"1-1310": (750_000, 0), "1-1500": (82_500, 0),
                                                                   "2-1250": (0, 832_500)})
    finally:
        await atur(klien, kepala_admin, "antar_entitas.ppn_mode", "tanpa_ppn")


@XFAIL_A_IC02
async def test_PK30_U4_mode_tolak_tugas_gudang_tidak_terbit(klien, kepala_admin, db, siap):
    await atur(klien, kepala_admin, KUNCI, "tolak")
    try:
        a = await alur(klien, db, siap, 100, 130, setujui=False)
    finally:
        await pulihkan(klien, kepala_admin, KUNCI)
    assert a["task"].status_code == 409, a["task"].text
    assert a["task"].json()["detail"] == pesan_panjang("130", "100")
    roll = await db.inventory_rolls.find_one({"id": a["rid"]}, {"_id": 0})
    assert roll["status"] == "available" and not roll.get("reserved_ref") and roll["owner_entity_id"] == KSC
    assert await db.warehouse_transfers.count_documents({"interco_pair_id": a["pid"]}) == 0


async def test_PK30_U5_periode_pembeli_tertutup(klien, db, siap):
    a = await alur(klien, db, siap, 100, 130, setujui=False)
    n0 = await db.journal_entries.count_documents({})
    c = await tutup_periode(KANDA, periode_buku())
    try:
        r = await setujui_tugas(klien, siap, a["tid"])
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    assert "sudah ditutup" in r.json()["detail"], r.text
    assert (await db.inventory_rolls.find_one({"id": a["rid"]}))["owner_entity_id"] == KSC
    assert "length_adjustment" not in (await dokumen(db, a["pid"]))["seller"]
    assert await db.journal_entries.count_documents({}) == n0


@XFAIL_A_IC02
async def test_PK30_U5b_periode_tertutup_tanpa_kunci_dokumen(klien, kepala_admin, db, siap):
    """Tambahan: sakelar PK-37 `periode.kunci_dokumen` dimatikan untuk PT pembeli — pemeriksaan jurnal penyesuaian,
    HPP, dan penerimaan (`precheck_warehouse_task`) tetap menolak sebelum kepemilikan roll pindah."""
    a = await alur(klien, db, siap, 100, 130, setujui=False)
    n0 = await db.journal_entries.count_documents({})
    await atur(klien, kepala_admin, "periode.kunci_dokumen", False, scope_id=KANDA)
    c = await tutup_periode(KANDA, periode_buku())
    try:
        r = await setujui_tugas(klien, siap, a["tid"])
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
        await pulihkan(klien, kepala_admin, "periode.kunci_dokumen", scope_id=KANDA)
    assert r.status_code == 409, r.text
    assert (await db.inventory_rolls.find_one({"id": a["rid"]}))["owner_entity_id"] == KSC
    assert (await db.warehouse_transfers.find_one({"id": a["tid"]}))["status"] == "waiting_approval"
    assert "length_adjustment" not in (await dokumen(db, a["pid"]))["seller"]
    assert await db.journal_entries.count_documents({}) == n0


@XFAIL_A_IC02
async def test_PK30_U6_sisi_pembeli_gagal_lalu_diulang(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    a = await alur(klien, db, siap, 100, 130, setujui=False)
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="interco_transaction", kali=1):
        r = await setujui_tugas(klien, siap, a["tid"])
    assert r.status_code == 200, r.text
    pid = a["pid"]
    assert (await db.warehouse_transfers.find_one({"id": a["tid"]}))["status"] == "completed"
    docs = await dokumen(db, pid)
    assert docs["buyer"]["gl_status_adj"] == "failed"
    assert await baris(db, pid, "adj:seller") is not None and await baris(db, pid, "adj:buyer") is None
    r = await klien.post(f"/api/finance/posting-failures/interco_adj/{a['bid']}/retry",
                         headers={**kepala_admin, "X-Entity-Id": KANDA})
    assert r.status_code == 200, r.text
    for akhiran in ("seller", "buyer", "adj:seller", "adj:buyer", "cogs", "receipt"):
        assert await db.journal_entries.count_documents({"source_type": "interco_transaction",
                                                         "source_id": f"{pid}:{akhiran}"}) == 1, akhiran
    for d in (await dokumen(db, pid)).values():
        assert (d["items"][0]["quantity"], d["grand_total"]) == (130, 3_250_000)   # disesuaikan sekali
        assert d["length_adjustment"]["delta_total"] == 750_000


@XFAIL_A_IC09
async def test_PK30_U7_jalur_lama_410(klien, kepala_admin, db, siap):
    rid = await buat_roll(db, 50)
    n0 = await db.warehouse_transfers.count_documents({})
    r = await klien.post("/api/transfers/inter-company", headers=kepala_admin, json={
        "source_entity_id": KSC, "dest_entity_id": KANDA,
        "items": [{"product_id": P1, "quantity": 10, "unit": "meter"}], "notes": "uji PK-30"})
    assert r.status_code == 410, r.text
    assert r.json()["detail"] == PESAN_410
    assert await db.warehouse_transfers.count_documents({}) == n0
    roll = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert roll["status"] == "available" and not roll.get("reserved_ref")
    # statik: layar tidak lagi memanggil jalur lama; jurnal harga pokok hanya dari pindah kepemilikan roll retur
    fe = [p for p in (ROOT / "frontend/src").rglob("*.js*") if "transfers/inter-company" in p.read_text("utf-8")]
    assert fe == []
    pemanggil = []
    for p in (ROOT / "backend").rglob("*.py"):
        rel = p.relative_to(ROOT / "backend").as_posix()
        if rel.startswith(("tests/", "tests_mem/")):
            continue
        for ln in p.read_text("utf-8").splitlines():
            if re.search(r"post_intercompany_transfer\(", ln) and "def post_intercompany_transfer" not in ln:
                pemanggil.append(rel)
    assert pemanggil == ["services/return_service.py"]


@XFAIL_A_IC09
async def test_PK30_U8_transfer_lama_tidak_bisa_disetujui_tetap_bisa_ditolak(klien, db, siap):
    tid = f"trn_pk30_lama_{uuid.uuid4().hex[:6]}"
    rid = await buat_roll(db, 20, ref_transfer=tid)
    await db.warehouse_transfers.insert_one({
        "id": tid, "code": f"TRF/{tid}", "transfer_kind": "inter_entity", "status": "waiting_approval",
        "entity_id": KSC, "source_entity_id": KSC, "dest_entity_id": KANDA, "source_warehouse_id": WH,
        "dest_warehouse_id": WH, "items": [{"product_id": P1, "qty": 20, "unit": "meter",
                                            "rolls": [{"roll_id": rid, "length": 20}]}],
        "interco_pair_id": None, "requested_by": "Kasir Lama", "requested_by_id": "usr_kasir_lama",
        "created_at": now_iso(), "updated_at": now_iso()})
    r = await setujui_tugas(klien, siap, tid)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == PESAN_409_LAMA
    assert (await db.inventory_rolls.find_one({"id": rid}))["owner_entity_id"] == KSC
    r = await klien.post(f"/api/transfers/{tid}/reject", headers=siap["gdg"],
                         json={"rejected_by": "Admin Gudang", "reason": "jalur lama ditutup"})
    assert r.status_code == 200, r.text
    roll = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0})
    assert roll["status"] == "available" and roll["owner_entity_id"] == KSC
    assert await db.journal_entries.count_documents({"source_type": "inter_company_transfer"}) == 0


# ═══ U9–U13: harga, mode PPN, dan PKP di `create()` ═══════════════════════════════════════════════════════════════════
async def test_PK30_U9_admin_sales_tanpa_izin_ubah_harga(klien, db, siap):
    n0 = await db.interco_transactions.count_documents({})
    r = await klien.post("/api/interco/transactions", headers=siap["sa"], json=isi_transaksi(unit_price=20_000))
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == PESAN_403
    r = await klien.post("/api/interco/transactions", headers=siap["sa"], json=isi_transaksi(ppn_mode="dengan_ppn"))
    assert r.status_code == 403, r.text
    assert await db.interco_transactions.count_documents({}) == n0
    r = await klien.post("/api/interco/transactions", headers=siap["sa"], json=isi_transaksi())
    assert r.status_code == 200, r.text
    assert r.json()["seller"]["items"][0]["unit_price"] == HARGA
    assert not r.json()["seller"].get("terms_override")


async def test_PK30_U10_manajer_wajib_alasan(klien, db, siap):
    r = await klien.post("/api/interco/transactions", headers=siap["mgr"], json=isi_transaksi(unit_price=20_000))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == PESAN_ALASAN
    r = await klien.post("/api/interco/transactions", headers=siap["mgr"],
                         json=isi_transaksi(unit_price=20_000, override_reason="harga cuci gudang"))
    assert r.status_code == 200, r.text
    s = r.json()["seller"]
    to = s["terms_override"]
    assert to["lines"][0] == {"product_id": P1, "standard_price": 25_000, "used_price": 20_000}
    assert to["reason"] == "harga cuci gudang" and to["by"] and to["at"]
    assert to["pricing_mode"] is None and to["ppn_mode"] is None
    assert s["items"][0]["unit_price"] == 20_000 and s["subtotal"] == 2 * JT
    assert r.json()["buyer"]["terms_override"] == to                                # kedua dokumen kembar
    jejak = await db.audit_logs.find_one({"action": "interco_terms_overridden", "entity_id": r.json()["pair_id"]})
    assert jejak and jejak["reason"] == "harga cuci gudang"


async def test_PK30_U11_peran_kustom_tanpa_acuan_dan_manajer_kosong(klien, akun, sesi, peran_tanpa_acuan,
                                                                     peran_manajer_kosong, siap):
    rid = await peran_tanpa_acuan({"interco": ["view", "create", "override_terms"]}, label="Ubah Harga Antar-PT")
    h = await sesi(await akun(rid, entitas=(KSC, KANDA)))
    r = await klien.post("/api/interco/transactions", headers=h,
                         json=isi_transaksi(unit_price=21_000, override_reason="harga promosi"))
    assert r.status_code == 200, r.text
    assert r.json()["seller"]["terms_override"]["lines"][0]["used_price"] == 21_000
    h0 = await sesi(await akun(await peran_manajer_kosong(), entitas=(KSC, KANDA)))
    r = await klien.post("/api/interco/transactions", headers=h0,
                         json=isi_transaksi(unit_price=21_000, override_reason="harga promosi"))
    assert r.status_code == 403, r.text


async def test_PK30_U12_penjual_non_pkp_tidak_boleh_memungut_ppn(klien, db, siap):
    n0 = await db.interco_transactions.count_documents({})
    r = await klien.post("/api/interco/transactions", headers=siap["mgr"],
                         json=isi_transaksi(seller=KANDA, buyer=KSC, ppn_mode="dengan_ppn",
                                            override_reason="uji PPN paksa"))
    assert r.status_code == 400, r.text
    assert re.fullmatch(r"PT penjual .+ bukan PKP, jadi transaksi ini tidak boleh memungut PPN\. Pilih mode PPN "
                        r"\"Tanpa PPN\"\.", r.json()["detail"]), r.text
    ent = await db.business_entities.find_one({"id": KANDA}, {"_id": 0})
    assert (ent.get("name") or ent.get("legal_name")) in r.json()["detail"]
    assert await db.interco_transactions.count_documents({}) == n0


async def test_PK30_U13_pembeli_non_pkp_diberi_tanda(klien, kepala_admin, siap):
    await atur(klien, kepala_admin, "antar_entitas.ppn_mode", "ikut_pkp")
    try:
        r = await klien.post("/api/interco/transactions", headers=siap["mgr"], json=isi_transaksi())
    finally:
        await atur(klien, kepala_admin, "antar_entitas.ppn_mode", "tanpa_ppn")
    assert r.status_code == 200, r.text
    s = r.json()["seller"]
    assert s["tax_amount"] == 275_000                                                # 2.500.000 × 11 %
    assert (s["seller_is_pkp"], s["buyer_is_pkp"], s["tax_warning"]) == (True, False, "pembeli_non_pkp")
    assert r.json()["buyer"]["tax_warning"] == "pembeli_non_pkp"


# ═══ U14: kunci pengaturan baru ═══════════════════════════════════════════════════════════════════════════════════════
async def test_PK30_U14_putaran_t1_config(klien, kepala_admin):
    import config_registry as registry
    from services.config_resolver import value_of
    e = registry.require(KUNCI)
    assert (e["type"], e["default"], e["scopes"], e["permission"]) == ("enum", "sesuaikan", ["global", "entity"],
                                                                         ["accounting", "manage"])
    assert [o["value"] for o in e["options"]] == ["sesuaikan", "tolak"]
    assert e["risk"] == "high" and e["requires_reason"] is True and e["status"] == "active"
    assert e["group"] == "pajak-pembukuan" and e["section"] == "antar-pt"    # alias KF-T4 dari "antar-entitas"
    assert e["label"] == "Bila panjang roll beda dari pesanan antar-PT"
    assert e["consumers"] == ["services/interco_service.py:precheck_warehouse_task"]
    assert await value_of(KUNCI) == "sesuaikan"                              # bawaan K-07
    await atur(klien, kepala_admin, KUNCI, "tolak", "global", "")
    assert await value_of(KUNCI) == "tolak"
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": KUNCI})
    assert next(i for i in r.json()["items"] if i["key"] == KUNCI)["value"] == "tolak"
    await atur(klien, kepala_admin, KUNCI, "sesuaikan", "entity", KANDA)
    assert await value_of(KUNCI, {"entity_id": KANDA}) == "sesuaikan"
    assert await value_of(KUNCI, {"entity_id": KSC}) == "tolak"
    await pulihkan(klien, kepala_admin, KUNCI, scope_id=KANDA)
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(KUNCI, "potong", "global", ""))
    assert r.status_code == 400, r.text
    await pulihkan(klien, kepala_admin, KUNCI, "global")
    assert await value_of(KUNCI) == "sesuaikan"


@XFAIL_A_IC02
async def test_PK30_U14_yang_dibaca_pt_penjual(klien, kepala_admin, db, siap):
    await atur(klien, kepala_admin, KUNCI, "tolak", scope_id=KANDA)        # lapisan PT PEMBELI
    try:
        a = await alur(klien, db, siap, 100, 130)
    finally:
        await pulihkan(klien, kepala_admin, KUNCI, scope_id=KANDA)
    assert a["task"].status_code == 200, a["task"].text
    assert a["approve"].status_code == 200, a["approve"].text
    assert (await dokumen(db, a["pid"]))["seller"]["length_adjustment"]["delta_total"] == 750_000
