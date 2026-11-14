"""PK-26 — jurnal landed cost dipecah menurut nasib roll: persediaan, makloon, atau sudah keluar (IV-01, K-05); susut
potong dan potong uji mutu dinilai dengan biaya roll termasuk landed cost (IV-10). Spesifikasi
`docs/blueprint/unit/PK-26.md`.

Persiapan bersama (fixture, disisipkan langsung): PO minimal milik PT; roll `acquired.ref_id = <PO>`, `length_initial`
100, `unit_cost = base_unit_cost = 10.000`; jurnal saldo awal Dr 1-1300 / Cr 3-2900 senilai roll yang berstatus
persediaan (rekonsiliasi mulai dari selisih 0). Alur (lewat API): voucher dibuat akun Manajer (`submit_now`), disetujui
`kepala_admin`, basis alokasi `value`. U14 = uji jalan layar (`features/__tests__/pk26LandedCost.test.js` = uji komponen).

Hitungan tangan dasar U1: dua roll berbobot sama (10.000 × 100) → 3.000.000 / 2 = 1.500.000 per roll = 15.000 per meter.
`r_stok` (sisa 100): 100 × (10.000 + 15.000) − 100 × 10.000 = 1.500.000 → 1-1300; `r_jual` (`delivered`, sisa 0) → 0;
keluar = 3.000.000 − 1.500.000 = 1.500.000 → HPP 5-1000. Cr 2-1100 3.000.000.
"""
import uuid
from typing import Dict, List, Tuple

import pytest

from core_utils import now_iso
from pembantu import jurnal, pt_uji, saldo_akun, tutup_periode
from services.book_date import periode_buku, tanggal_buku

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
HARGA = 10_000
KUNCI = "inventory.landed_cost_porsi_terjual"
PANEL = "/api/finance/posting-failures"
#: status roll yang dihitung rekonsiliasi 1-1300 (`gl_service.OWNED_ROLL_STATUSES`) — dipakai menghitung saldo awal fixture
STOK = {"available", "reserved", "committed", "picked", "packed", "hold", "wip", "quarantine", "blocked", "damaged",
        "in_transit_transfer"}

MENUNGGU_B = "IV-01 — jurnal landed cost dipecah saat persetujuan baru di serah-terima (b)"
MENUNGGU_B_SUSUT = "IV-10 — susut potong dan potong uji mutu dinilai biaya roll di serah-terima (b)"


def uid(awalan: str) -> str:
    return f"{awalan}_pk26_{uuid.uuid4().hex[:8]}"


def baris(je) -> Dict[str, Tuple[float, float]]:
    """{akun: (debit, kredit)} — satu jurnal."""
    out: Dict[str, Tuple[float, float]] = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


async def jurnal_aktif(source_type: str, source_id: str) -> List[dict]:
    from db import db
    return await db.journal_entries.find(
        {"source_type": source_type, "source_id": source_id, "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


def _roll_dok(rid: str, po: str, entitas: str, status: str, sisa: float, *, panjang: float = 100.0,
              harga: float = HARGA, pid: str = "prd_pk26", wid: str = "wh_pk26") -> dict:
    return {"id": rid, "roll_no": f"R-{rid[-8:]}", "product_id": pid, "warehouse_id": wid, "owner_entity_id": entitas,
            "entity_id": entitas, "unit": "meter", "status": status, "length_initial": panjang,
            "length_remaining": sisa, "unit_cost": harga, "base_unit_cost": harga, "grade": "A",
            "acquired": {"via": "po", "ref_type": "purchase_order", "ref_id": po}, "created_at": now_iso()}


async def siapkan(db, rolls, *, entitas: str = KSC) -> Tuple[str, Dict[str, str]]:
    """PO minimal + roll fixture + saldo awal 1-1300. `rolls` = [(nama, status, sisa[, panjang])]."""
    po = uid("po")
    await db.purchase_orders.insert_one({"id": po, "po_number": f"PO/PK26/{po[-8:]}", "entity_id": entitas,
                                         "status": "received", "supplier_name": "Pemasok Uji PK-26", "items": [],
                                         "created_at": now_iso()})
    ids: Dict[str, str] = {}
    stok = 0.0
    for nama, status, sisa, *lain in rolls:
        panjang = lain[0] if lain else 100.0
        rid = uid(nama)
        ids[nama] = rid
        await db.inventory_rolls.insert_one(_roll_dok(rid, po, entitas, status, sisa, panjang=panjang))
        if status in STOK:
            stok += sisa * HARGA
    if stok:
        await jurnal(entitas, tanggal_buku(), [("1-1300", round(stok, 2), 0), ("3-2900", 0, round(stok, 2))],
                     "saldo awal roll uji PK-26", uid("sa"))
    return po, ids


@pytest.fixture(scope="module")
async def manajer(akun, sesi):
    """Akun Manajer pembuat voucher (≠ penyetuju), berakses dua PT."""
    u = await akun("manager", entitas=(KSC, KANDA))
    return {KSC: await sesi(u, entitas=KSC), KANDA: await sesi(u, entitas=KANDA)}


@pytest.fixture(scope="module")
async def admin(sesi):
    return {KSC: await sesi("admin@kainnusantara.id", entitas=KSC),
            KANDA: await sesi("admin@kainnusantara.id", entitas=KANDA)}


async def buat_voucher(klien, h, po: str, total: float, *, entitas: str = KSC) -> dict:
    r = await klien.post("/api/landed-costs", headers=h, json={
        "po_ids": [po], "provider_name": "Ekspedisi Uji PK-26", "basis": "value", "entity_id": entitas,
        "cost_lines": [{"category": "freight", "description": "Ongkos angkut uji", "amount": total}],
        "submit_now": True, "created_by": ""})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["status"] == "pending_approval", v
    return v


async def setujui(klien, h, vid: str):
    return await klien.post(f"/api/landed-costs/{vid}/approve", headers=h)


async def rekon(klien, h, entitas: str = KSC) -> dict:
    """Baris `GET /api/gl/inventory-reconciliation` satu PT (`subledger_value`, `gl_balance`, `difference`)."""
    r = await klien.get("/api/gl/inventory-reconciliation", headers=h)
    assert r.status_code == 200, r.text
    return next(x for x in r.json()["rows"] if x["entity_id"] == entitas)


def _isi(key, value, scope_type, scope_id, reason="uji PK-26"):
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


# ═══ Uji murni `split_allocation` (serah-terima a) — roll = dokumen SEBELUM biaya dinaikkan ═══════════════════════════
def _roll_murni(i: str, status: str, sisa: float, panjang: float = 100.0, harga: float = HARGA) -> dict:
    return {"id": i, "roll_no": i, "product_id": "p", "status": status, "length_initial": panjang,
            "length_remaining": sisa, "unit_cost": harga, "base_unit_cost": harga}


def _pecah(rolls, total):
    from services import landed_cost_service as lcs
    alloc = lcs.compute_allocation(rolls, total, "value")
    return alloc, lcs.split_allocation(rolls, alloc["allocations"], alloc["allocated_total"])


def test_PK26_U1_murni_satu_roll_terjual():
    alloc, s = _pecah([_roll_murni("r_jual", "delivered", 0), _roll_murni("r_stok", "available", 100)], 3 * JT)
    assert [a["alloc_amount"] for a in alloc["allocations"]] == [1.5 * JT, 1.5 * JT]
    assert [a["per_unit"] for a in alloc["allocations"]] == [15_000, 15_000]
    assert (s["inventory_amount"], s["wip_amount"], s["expensed_amount"]) == (1.5 * JT, 0, 1.5 * JT)
    assert {p["roll_id"]: (p["treatment"], p["capitalized_amount"]) for p in s["per_roll"]} == {
        "r_jual": ("keluar", 0), "r_stok": ("persediaan", 1.5 * JT)}


def test_PK26_U2_murni_tiga_golongan():
    # 300.000 / 3 = 100.000 per roll = 1.000 per meter; roll di mitra (sisa 100) naik 100 × 1.000 = 100.000 → WIP.
    _, s = _pecah([_roll_murni("r_stok", "available", 100), _roll_murni("r_mitra", "subcon", 100),
                   _roll_murni("r_jual", "delivered", 0)], 300_000)
    assert (s["inventory_amount"], s["wip_amount"], s["expensed_amount"]) == (100_000, 100_000, 100_000)
    assert [p["treatment"] for p in s["per_roll"]] == ["persediaan", "wip", "keluar"]


def test_PK26_U3_murni_roll_sudah_susut():
    # 100.000 / 100 m awal = 1.000 per meter; sisa 98 → naik 98 × 1.000 = 98.000; 2 m yang sudah susut → 2.000 beban.
    _, s = _pecah([_roll_murni("r_susut", "available", 98)], 100_000)
    assert (s["inventory_amount"], s["wip_amount"], s["expensed_amount"]) == (98_000, 0, 2_000)


def test_PK26_U10_murni_pembulatan_sen():
    # Bobot 333.300 · 333.300 · 333.400 (Σ 1.000.000) → 333.300,00 · 333.300,00 · sisa 333.400,01 ke roll terakhir.
    rolls = [_roll_murni("ra", "available", 33.33, 33.33), _roll_murni("rb", "available", 33.33, 33.33),
             _roll_murni("rc", "available", 33.34, 33.34)]
    alloc, s = _pecah(rolls, 1_000_000.01)
    assert [a["alloc_amount"] for a in alloc["allocations"]] == [333_300.0, 333_300.0, 333_400.01]
    assert round(s["inventory_amount"] + s["wip_amount"] + s["expensed_amount"], 2) == 1_000_000.01
    assert 0 <= s["expensed_amount"] < 0.05


def test_PK26_murni_status_lain_dan_dalam_perjalanan():
    """Golongan: `in_transit_sales`, `returned_supplier`, `in_transit_intercompany` = keluar; `receiving` (status di luar
    tiga daftar) = persediaan (ASUMSI spesifikasi)."""
    from services import landed_cost_service as lcs
    assert [lcs.treatment_of({"status": s}) for s in (
        "in_transit_sales", "delivered", "returned_supplier", "in_transit_intercompany", "subcon", "available",
        "receiving", "in_transit_transfer")] == ["keluar"] * 4 + ["wip", "persediaan", "persediaan", "persediaan"]
    # Roll keluar yang sisa panjangnya belum 0 (masih di jalan ke pelanggan) tetap 0 kenaikan.
    _, s = _pecah([_roll_murni("r_jalan", "in_transit_sales", 100), _roll_murni("r_stok", "available", 100)], 200_000)
    assert (s["inventory_amount"], s["expensed_amount"]) == (100_000, 100_000)


def test_PK26_murni_negatif_ditolak():
    """Data roll rusak (sisa > panjang awal) → kenaikan melebihi alokasi → ValueError (persetujuan 409 tanpa tulisan)."""
    from services import landed_cost_service as lcs
    rolls = [_roll_murni("r_rusak", "available", 150)]
    alloc = lcs.compute_allocation(rolls, 100_000, "value")
    with pytest.raises(ValueError, match="Hitungan pembebanan landed cost negatif"):
        lcs.split_allocation(rolls, alloc["allocations"], alloc["allocated_total"])


def test_PK26_murni_lebih_satu_sen_karena_pembulatan_bukan_negatif():
    """Kenaikan nilai roll = selisih dua nilai yang masing-masing dibulatkan ke sen (`roll_value_cents` sebelum dan
    sesudah). Biaya roll yang sudah memuat landed cost lama (pecahan sen) bisa membuat kenaikan = alokasi + 1 sen: itu
    pembulatan, bukan data rusak — persetujuan tidak boleh ditolak (laporan: Menyimpang). Fixture (dicari dengan sapuan
    acak; ±0,1 % roll berbiaya pecahan mengalami ini): sisa = panjang 103,07 m, biaya 10.758,979771; voucher 29.502,72 →
    per meter round(29.502,72 / 103,07; 6) = 286,239643. Sebelum 103,07 × 10.758,979771 = 1.108.928,04;
    sesudah 103,07 × 11.045,219414 = 1.138.430,77 → naik 29.502,73 = alokasi + 0,01 → dibatasi 29.502,72, beban 0."""
    r = _roll_murni("r_sen", "available", 103.07, 103.07, harga=10_758.979771)
    alloc, s = _pecah([r], 29_502.72)
    assert alloc["allocations"][0]["per_unit"] == 286.239643
    assert (s["inventory_amount"], s["wip_amount"], s["expensed_amount"]) == (29_502.72, 0, 0)
    assert s["per_roll"][0]["capitalized_amount"] == 29_502.72


# ═══ `post_landed_cost` menerima `capitalization` (serah-terima a) ═══════════════════════════════════════════════════
async def test_PK26_a_post_landed_cost_dari_capitalization(db):
    """Langsung ke fungsi jurnal (PT uji sendiri supaya saldo `ent_ksc` untuk U9 tidak tersentuh)."""
    from services import gl_service as gl
    pt = await pt_uji("P26")
    vid = uid("lcv")
    cap = {"inventory_amount": 100_000.0, "wip_amount": 100_000.0, "expensed_amount": 100_000.0, "expensed_to": "hpp",
           "computed_at": now_iso()}
    je = await gl.post_landed_cost({"id": vid, "entity_id": pt, "capitalization": cap}, label="LC/PK26/A")
    assert baris(je) == {"1-1300": (100_000, 0), "1-1350": (100_000, 0), "5-1000": (100_000, 0), "2-1100": (0, 300_000)}
    assert {ln["account_code"]: ln.get("mapping_key") for ln in je["lines"]} == {
        "1-1300": "persediaan.persediaan", "1-1350": "makloon.wip_subcon", "5-1000": "persediaan.hpp",
        "2-1100": "pembelian.hutang"}
    assert je["source_type"] == "landed_cost" and je["source_id"] == vid
    # varians → akun biaya masuk pembelian; baris bernilai 0 tidak ditulis
    vid2 = uid("lcv")
    je2 = await gl.post_landed_cost({"id": vid2, "entity_id": pt, "capitalization": {
        "inventory_amount": 0.0, "wip_amount": 0.0, "expensed_amount": 50_000.0, "expensed_to": "varians"}},
        label="LC/PK26/B")
    assert baris(je2) == {"5-9000": (50_000, 0), "2-1100": (0, 50_000)}
    assert await gl.post_landed_cost({"id": vid2, "entity_id": pt, "capitalization": {
        "inventory_amount": 1.0, "wip_amount": 0.0, "expensed_amount": 0.0, "expensed_to": "hpp"}}) is None   # sekali


async def test_PK26_a_voucher_lama_tanpa_capitalization_tetap_seperti_lama(db):
    from services import gl_service as gl
    vid = uid("lcv")
    je = await gl.post_landed_cost({"id": vid, "entity_id": await pt_uji("P26")}, amount=3 * JT, label="LC/PK26/LAMA")
    assert baris(je) == {"1-1300": (3 * JT, 0), "2-1100": (0, 3 * JT)}


# ═══ Alur lewat API (serah-terima b) ════════════════════════════════════════════════════════════════════════════════
@pytest.fixture(scope="module")
async def alur_u1(klien, db, manajer, admin):
    """U1 sekali untuk U1, U8, U9: persiapan → rekonsiliasi sebelum → setujui → rekonsiliasi sesudah."""
    po, ids = await siapkan(db, [("r_jual", "delivered", 0.0), ("r_stok", "available", 100.0)])
    v = await buat_voucher(klien, manajer[KSC], po, 3 * JT)
    sebelum = await rekon(klien, admin[KSC])
    r = await setujui(klien, admin[KSC], v["id"])
    sesudah = await rekon(klien, admin[KSC])
    return {"po": po, "ids": ids, "v": v, "r": r, "sebelum": sebelum, "sesudah": sesudah}


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U1_roll_terjual_ke_hpp(alur_u1, db):
    r, ids = alur_u1["r"], alur_u1["ids"]
    assert r.status_code == 200, r.text
    vid = alur_u1["v"]["id"]
    jes = await jurnal_aktif("landed_cost", vid)
    assert len(jes) == 1
    assert baris(jes[0]) == {"1-1300": (1.5 * JT, 0), "5-1000": (1.5 * JT, 0), "2-1100": (0, 3 * JT)}
    stok = await db.inventory_rolls.find_one({"id": ids["r_stok"]})
    # 100 × 25.000 = 2.500.000 — naik 1.500.000 = debit 1-1300
    assert stok["unit_cost"] == 25_000 and round(stok["length_remaining"] * stok["unit_cost"], 2) == 2.5 * JT
    doc = await db.landed_cost_vouchers.find_one({"id": vid}, {"_id": 0})
    cap = doc["capitalization"]
    assert (cap["inventory_amount"], cap["wip_amount"], cap["expensed_amount"], cap["expensed_to"]) == (
        1.5 * JT, 0, 1.5 * JT, "hpp")
    assert cap.get("computed_at")
    assert {a["roll_id"]: (a["treatment"], a["capitalized_amount"]) for a in doc["allocations"]} == {
        ids["r_jual"]: ("keluar", 0), ids["r_stok"]: ("persediaan", 1.5 * JT)}
    # jawaban approve dan GET memuat capitalization + treatment; pratinjau saat dibuat sudah bergolongan
    assert r.json()["capitalization"]["expensed_amount"] == 1.5 * JT
    assert {a["roll_id"]: a["treatment"] for a in alur_u1["v"]["allocation_preview"]} == {
        ids["r_jual"]: "keluar", ids["r_stok"]: "persediaan"}


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U8_setujui_lagi_ditolak(alur_u1, klien, db, admin):
    vid = alur_u1["v"]["id"]
    r = await setujui(klien, admin[KSC], vid)
    assert r.status_code == 409, r.text
    assert len(await jurnal_aktif("landed_cost", vid)) == 1
    assert (await db.inventory_rolls.find_one({"id": alur_u1["ids"]["r_stok"]}))["unit_cost"] == 25_000
    g = await klien.get(f"/api/landed-costs/{vid}", headers=admin[KSC])
    assert g.status_code == 200 and g.json()["capitalization"]["inventory_amount"] == 1.5 * JT
    assert {a["treatment"] for a in g.json()["allocations"]} == {"keluar", "persediaan"}


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U9_rekonsiliasi_tetap_nol(alur_u1):
    """Aplikasi uji membawa jurnal seed 1-1300 Rp 750.000 di `ent_ksc` tanpa roll (selisih awal −750.000, bukan dari
    unit ini — laporan: usulan koreksi U9). Yang diuji: nilai roll naik 1.500.000 (`r_stok`), saldo 1-1300 naik
    1.500.000, selisih sesudah = sebelum. Kode lama: saldo 1-1300 naik 3.000.000 → selisih turun 1.500.000."""
    assert alur_u1["r"].status_code == 200
    s0, s1 = alur_u1["sebelum"], alur_u1["sesudah"]
    assert round(s1["subledger_value"] - s0["subledger_value"], 2) == 1.5 * JT
    assert round(s1["gl_balance"] - s0["gl_balance"], 2) == 1.5 * JT
    assert s1["difference"] == s0["difference"]


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U2_tiga_golongan(klien, db, manajer, admin):
    po, ids = await siapkan(db, [("r_stok", "available", 100.0), ("r_mitra", "subcon", 100.0),
                                 ("r_jual", "delivered", 0.0)])
    v = await buat_voucher(klien, manajer[KSC], po, 300_000)
    r = await setujui(klien, admin[KSC], v["id"])
    assert r.status_code == 200, r.text
    jes = await jurnal_aktif("landed_cost", v["id"])
    assert len(jes) == 1
    assert baris(jes[0]) == {"1-1300": (100_000, 0), "1-1350": (100_000, 0), "5-1000": (100_000, 0),
                             "2-1100": (0, 300_000)}
    doc = await db.landed_cost_vouchers.find_one({"id": v["id"]}, {"_id": 0})
    assert {a["roll_id"]: a["treatment"] for a in doc["allocations"]} == {
        ids["r_stok"]: "persediaan", ids["r_mitra"]: "wip", ids["r_jual"]: "keluar"}
    assert {a["roll_id"]: a["capitalized_amount"] for a in doc["allocations"]} == {
        ids["r_stok"]: 100_000, ids["r_mitra"]: 100_000, ids["r_jual"]: 0}


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U3_bagian_susut_dibebankan(klien, db, manajer, admin):
    po, _ = await siapkan(db, [("r_susut", "available", 98.0)])
    v = await buat_voucher(klien, manajer[KSC], po, 100_000)
    r = await setujui(klien, admin[KSC], v["id"])
    assert r.status_code == 200, r.text
    jes = await jurnal_aktif("landed_cost", v["id"])
    assert len(jes) == 1 and baris(jes[0]) == {"1-1300": (98_000, 0), "5-1000": (2_000, 0), "2-1100": (0, 100_000)}


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U4_varians_hanya_pt_yang_diatur(klien, db, manajer, admin, kepala_admin):
    await atur(klien, kepala_admin, KUNCI, "varians", "entity", KSC)
    try:
        po_k, _ = await siapkan(db, [("r_jual", "delivered", 0.0), ("r_stok", "available", 100.0)])
        po_d, _ = await siapkan(db, [("r_jual", "delivered", 0.0), ("r_stok", "available", 100.0)], entitas=KANDA)
        v_k = await buat_voucher(klien, manajer[KSC], po_k, 3 * JT)
        v_d = await buat_voucher(klien, manajer[KANDA], po_d, 3 * JT, entitas=KANDA)
        r_k = await setujui(klien, admin[KSC], v_k["id"])
        r_d = await setujui(klien, admin[KANDA], v_d["id"])
    finally:
        await pulihkan(klien, kepala_admin, KUNCI, "entity", KSC)
    assert r_k.status_code == 200, r_k.text
    assert r_d.status_code == 200, r_d.text
    (je_k,) = await jurnal_aktif("landed_cost", v_k["id"])
    (je_d,) = await jurnal_aktif("landed_cost", v_d["id"])
    assert baris(je_k) == {"1-1300": (1.5 * JT, 0), "5-9000": (1.5 * JT, 0), "2-1100": (0, 3 * JT)}
    assert baris(je_d) == {"1-1300": (1.5 * JT, 0), "5-1000": (1.5 * JT, 0), "2-1100": (0, 3 * JT)}
    assert je_k["entity_id"] == KSC and je_d["entity_id"] == KANDA
    assert (await db.landed_cost_vouchers.find_one({"id": v_k["id"]}))["capitalization"]["expensed_to"] == "varians"
    assert (await db.landed_cost_vouchers.find_one({"id": v_d["id"]}))["capitalization"]["expensed_to"] == "hpp"


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U5_akun_hpp_dari_pemetaan_pt(klien, db, manajer, admin, kepala_admin):
    r = await klien.post("/api/gl/accounts", headers=kepala_admin, params={"entity_id": KSC},
                         json={"code": "5-1900", "name": "HPP Biaya Masuk Uji PK-26", "type": "expense",
                               "parent_code": "5-0000"})
    assert r.status_code == 200, r.text
    r = await klien.put("/api/gl/account-mappings/persediaan.hpp", headers=kepala_admin,
                        json={"account_code": "5-1900", "entity_id": KSC, "reason": "uji PK-26 akun HPP per PT"})
    assert r.status_code == 200, r.text
    try:
        hpp0 = await saldo_akun("5-1000", KSC)
        po, _ = await siapkan(db, [("r_jual", "delivered", 0.0), ("r_stok", "available", 100.0)])
        v = await buat_voucher(klien, manajer[KSC], po, 3 * JT)
        rr = await setujui(klien, admin[KSC], v["id"])
        hpp1 = await saldo_akun("5-1000", KSC)
    finally:
        r = await klien.post("/api/gl/account-mappings/persediaan.hpp/reset", headers=kepala_admin,
                             json={"entity_id": KSC, "reason": "pulihkan uji PK-26"})
        assert r.status_code == 200, r.text
    assert rr.status_code == 200, rr.text
    (je,) = await jurnal_aktif("landed_cost", v["id"])
    assert baris(je) == {"1-1300": (1.5 * JT, 0), "5-1900": (1.5 * JT, 0), "2-1100": (0, 3 * JT)}
    assert next(ln for ln in je["lines"] if ln["account_code"] == "5-1900")["mapping_key"] == "persediaan.hpp"
    assert hpp1 == hpp0


async def test_PK26_U6_periode_tertutup_tanpa_tulisan(klien, db, manajer, admin):
    po, ids = await siapkan(db, [("r_jual", "delivered", 0.0), ("r_stok", "available", 100.0)])
    v = await buat_voucher(klien, manajer[KSC], po, 3 * JT)
    c = await tutup_periode(KSC, periode_buku())
    try:
        r = await setujui(klien, admin[KSC], v["id"])
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    assert "sudah ditutup" in r.json()["detail"] and "biaya masuk (landed cost)" in r.json()["detail"]
    assert (await db.landed_cost_vouchers.find_one({"id": v["id"]}))["status"] == "pending_approval"
    assert (await db.inventory_rolls.find_one({"id": ids["r_stok"]}))["unit_cost"] == HARGA
    assert await jurnal_aktif("landed_cost", v["id"]) == []


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U7_ulang_posting_memakai_angka_tersimpan(klien, db, manajer, admin, kepala_admin,
                                                             paksa_jurnal_gagal):
    po, ids = await siapkan(db, [("r_jual", "delivered", 0.0), ("r_stok", "available", 100.0)])
    v = await buat_voucher(klien, manajer[KSC], po, 3 * JT)
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="landed_cost") as gagal:
        r = await setujui(klien, admin[KSC], v["id"])
    assert r.status_code == 200, r.text
    assert len(gagal) == 1
    doc = await db.landed_cost_vouchers.find_one({"id": v["id"]}, {"_id": 0})
    assert doc["status"] == "applied" and doc["gl_status"] == "failed"
    assert doc["capitalization"]["inventory_amount"] == 1.5 * JT
    # fixture: roll stok terlanjur terkirim sebelum diulang — angka jurnal tetap dari capitalization tersimpan
    await db.inventory_rolls.update_one({"id": ids["r_stok"]}, {"$set": {"status": "delivered"}})
    r2 = await klien.post(f"{PANEL}/landed_cost/{v['id']}/retry", headers=kepala_admin)
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    (je,) = await jurnal_aktif("landed_cost", v["id"])
    assert baris(je) == {"1-1300": (1.5 * JT, 0), "5-1000": (1.5 * JT, 0), "2-1100": (0, 3 * JT)}


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B)
async def test_PK26_U10_pembulatan_sen_lewat_api(klien, db, manajer, admin):
    po, _ = await siapkan(db, [("ra", "available", 33.33, 33.33), ("rb", "available", 33.33, 33.33),
                               ("rc", "available", 33.34, 33.34)])
    v = await buat_voucher(klien, manajer[KSC], po, 1_000_000.01)
    r = await setujui(klien, admin[KSC], v["id"])
    assert r.status_code == 200, r.text
    cap = (await db.landed_cost_vouchers.find_one({"id": v["id"]}))["capitalization"]
    assert round(cap["inventory_amount"] + cap["wip_amount"] + cap["expensed_amount"], 2) == 1_000_000.01
    assert 0 <= cap["expensed_amount"] < 0.05
    (je,) = await jurnal_aktif("landed_cost", v["id"])
    assert je["total_debit"] == je["total_credit"] == 1_000_000.01


# ═══ IV-10 — susut potong dan potong uji mutu memakai biaya roll (termasuk landed cost) ═════════════════════════════
async def _roll_berlanded(db, **lain) -> str:
    """Roll `available` ber-`base_unit_cost` 10.000 dan `unit_cost` 11.000 (sudah menerima landed 1.000 per meter)."""
    rid = uid("roll")
    dok = _roll_dok(rid, uid("po"), KSC, "available", 50.0, panjang=50.0, pid=uid("prd"), wid=uid("wh"))
    dok.update({"unit_cost": 11_000, "base_unit_cost": 10_000, "lot": "LOT-PK26", **lain})
    await db.products.insert_one({"id": dok["product_id"], "name": "Kain Uji PK-26", "sku": f"SKU-{rid[-6:]}",
                                  "base_unit": "meter", "harga_pokok": 10_000, "is_active": True})
    await db.warehouses.insert_one({"id": dok["warehouse_id"], "name": "Gudang Uji PK-26", "entity_id": KSC,
                                    "is_active": True})
    await db.inventory_rolls.insert_one(dok)
    from services.roll_service import rebuild_balance
    await rebuild_balance(dok["product_id"], dok["warehouse_id"], KSC)
    return rid


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B_SUSUT)
async def test_PK26_U11_susut_potong_dinilai_biaya_roll(klien, db, kepala_admin):
    rsv = uid("rsv")
    rid = await _roll_berlanded(db, length_reserved=10, length_reservations=[
        {"id": rsv, "qty": 10, "ref": {"type": "manual", "id": uid("ref")}, "status": "reserved"}])
    r = await klien.post(f"/api/inventory/rolls/{rid}/reservations/{rsv}/cut", headers=kepala_admin,
                         json={"actual_length": 10, "waste": 2, "waste_reason": "susut uji PK-26 di ujung roll"})
    assert r.status_code == 200, r.text
    # 2 m × 11.000 = 22.000 (bukan 2 × 10.000 = 20.000)
    (je,) = await jurnal_aktif("inventory_writeoff", f"cutw:{rsv}")
    assert baris(je) == {"5-9500": (22_000, 0), "1-1300": (0, 22_000)}


@pytest.mark.xfail(strict=True, reason=MENUNGGU_B_SUSUT)
async def test_PK26_U12_potong_uji_mutu_dinilai_biaya_roll(klien, db, kepala_admin):
    rid = await _roll_berlanded(db)
    ins = uid("ins")
    await db.inspections.insert_one({"id": ins, "number": f"INS/PK26/{ins[-6:]}", "kind": "po_receipt",
                                     "status": "in_progress", "entity_id": KSC, "lines": [{"id": "ln1", "roll_id": rid}]})
    # 1,5 m = 1,5 / 0,9144 yard (layanan menghitung qty meter = round(yard × 0,9144, 4) = 1,5)
    r = await klien.post(f"/api/inspections/{ins}/lines/ln1/mdq-cut", headers=kepala_admin,
                         json={"cut_yard": 1.5 / 0.9144})
    assert r.status_code == 200, r.text
    assert r.json()["qty"] == 1.5
    # 1,5 × 11.000 = 16.500 (bukan 1,5 × 10.000 = 15.000)
    (je,) = await jurnal_aktif("inventory_writeoff", f"mdq:{ins}:ln1")
    assert baris(je) == {"5-9500": (16_500, 0), "1-1300": (0, 16_500)}


# ═══ U13 — kunci pengaturan baru (serah-terima a) ══════════════════════════════════════════════════════════════════
async def test_PK26_U13_putaran_t1_config(klien, kepala_admin):
    import config_registry as registry
    from services import landed_cost_service as lcs
    from services.config_resolver import value_of
    e = registry.require(KUNCI)
    assert (e["type"], e["default"], e["scopes"], e["permission"]) == ("enum", "hpp", ["global", "entity"],
                                                                         ["accounting", "manage"])
    assert [(o["value"], o["label"]) for o in e["options"]] == [
        ("hpp", "Bebankan ke HPP periode berjalan"), ("varians", "Catat di akun biaya masuk pembelian")]
    assert e["risk"] == "high" and e["requires_reason"] is True and e["status"] == "active"
    assert e["group"] == "pembelian"
    assert e["label"] == "Biaya masuk untuk barang yang sudah terjual"
    # pembaca = pembantu yang dipanggil `approve_landed_cost` (laporan: Menyimpang — spesifikasi menulis router)
    assert e["consumers"] == ["services/landed_cost_service.py:expensed_to_for"]
    assert await lcs.expensed_to_for(KSC) == "hpp"
    assert await value_of(KUNCI) == "hpp"                                    # bawaan K-05
    await atur(klien, kepala_admin, KUNCI, "varians", "global", "")
    assert await value_of(KUNCI) == "varians"
    r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": KUNCI})
    assert next(i for i in r.json()["items"] if i["key"] == KUNCI)["value"] == "varians"
    await atur(klien, kepala_admin, KUNCI, "hpp", "entity", KANDA)
    assert await value_of(KUNCI, {"entity_id": KANDA}) == "hpp"
    assert await value_of(KUNCI, {"entity_id": KSC}) == "varians"
    assert (await lcs.expensed_to_for(KANDA), await lcs.expensed_to_for(KSC)) == ("hpp", "varians")
    await pulihkan(klien, kepala_admin, KUNCI, scope_id=KANDA)
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(KUNCI, "lain", "global", ""))
    assert r.status_code == 400, r.text
    await pulihkan(klien, kepala_admin, KUNCI, "global")
    assert await value_of(KUNCI) == "hpp"
