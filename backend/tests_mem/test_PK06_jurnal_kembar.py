"""PK-06 — jurnal kembar antar-PT yang utuh dan bisa diulang per sisi (U1–U16, U18 di database tiruan).

U17 (dua pelunasan bersamaan) di MongoDB asli: backend/tests/test_bp_PK06_jurnal_kembar_mongo.py.
"""
import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, aktifkan_akun, jumlah, nonaktifkan_akun, pt_uji, saldo_akun, tutup_periode
from services import interco_return_service as icret
from services import interco_service as ics
from services import twin_journal as twin

JT = 1_000_000
KSC, KANDA = "ent_ksc", "ent_kanda"


def pasangan(pid, total=20 * JT, status="draft", seller=KSC, buyer=KANDA):
    base = {"pair_id": pid, "seller_entity_id": seller, "buyer_entity_id": buyer, "seller_entity_name": "PT Penjual",
            "buyer_entity_name": "PT Pembeli", "subtotal": total, "tax_amount": 0.0, "grand_total": total,
            "settled_amount": 0.0, "returned_amount": 0.0, "status": status, "items": [], "timeline": [],
            "created_at": now_iso(), "created_by": "Orang Lain"}
    return [{**base, "id": f"{pid}_s", "number": f"S/{pid}", "role": "seller", "entity_id": seller,
             "counterpart_id": f"{pid}_b", "counterpart_number": f"B/{pid}"},
            {**base, "id": f"{pid}_b", "number": f"B/{pid}", "role": "buyer", "entity_id": buyer,
             "counterpart_id": f"{pid}_s", "counterpart_number": f"S/{pid}"}]


@pytest.fixture(scope="module")
async def data(db):
    await db.bank_accounts.insert_many([
        {"id": "rek_ksc", "name": "Bank KSC", "entity_id": KSC, "account_type": "bank", "cash_type": "kas_besar",
         "is_active": True},
        {"id": "rek_kanda", "name": "Bank Kanda", "entity_id": KANDA, "account_type": "bank",
         "cash_type": "kas_besar", "is_active": True}])
    for pid in ("p5", "p6", "p7", "p10", "p11", "p12", "p13", "p14", "p15", "p16", "p18"):
        await db.interco_transactions.insert_many(pasangan(pid))
    return True


async def konfirmasi(klien, h, pid):
    return await klien.post(f"/api/interco/transactions/{pid}_s/confirm", headers=h, json={"note": ""})


async def jumlah_je(source_type, prefix):
    return await jumlah("journal_entries", {"source_type": source_type, "status": {"$ne": "void"},
                                            "source_id": {"$regex": f"^{prefix}:"}})


async def bersih(klien, h, pid):
    r = await konfirmasi(klien, h, pid)
    assert r.status_code == 200 and not r.json().get("warning"), r.text


# ── U1–U4: pembantu jurnal kembar ──────────────────────────────────────────────────────────────────────
def sisi(base, ent_a=KSC, ent_b=KANDA, akun_b="2-1250"):
    a = twin.TwinSide("seller", ent_a, [{"account_code": "1-1250", "debit": 1000, "credit": 0},
                                        {"account_code": "4-1000", "debit": 0, "credit": 1000}],
                      "uji A", "UJI", ("uji_twin", f"{base}_a"))
    b = twin.TwinSide("buyer", ent_b, [{"account_code": "1-1310", "debit": 1000, "credit": 0},
                                       {"account_code": akun_b, "debit": 0, "credit": 1000}],
                      "uji B", "UJI", ("uji_twin", f"{base}_b"))
    return [a, b]


async def test_U1_post_twin_idempoten(db, data):
    await db.uji_twin.insert_many([{"id": "t1_a"}, {"id": "t1_b"}])
    await twin.post_twin(source_type="uji_twin", base_id="T1", date="2026-11-05", sides=sisi("t1"))
    assert await jumlah_je("uji_twin", "T1") == 2
    assert {d["gl_status"] async for d in db.uji_twin.find({"id": {"$in": ["t1_a", "t1_b"]}})} == {"posted"}
    await twin.post_twin(source_type="uji_twin", base_id="T1", date="2026-11-05", sides=sisi("t1"))
    assert await jumlah_je("uji_twin", "T1") == 2


async def test_U2_hanya_sisi_yang_kurang(db, data):
    await db.uji_twin.insert_many([{"id": "x_a"}, {"id": "x_b"}])
    await twin.post_twin(source_type="uji_twin", base_id="X", date="2026-11-05", sides=sisi("x")[:1])
    await twin.post_twin(source_type="uji_twin", base_id="X", date="2026-11-05", sides=sisi("x"))
    assert await jumlah("journal_entries", {"source_type": "uji_twin", "source_id": "X:seller"}) == 1
    assert await jumlah("journal_entries", {"source_type": "uji_twin", "source_id": "X:buyer"}) == 1


async def test_U3_gagal_sisi_pertama_lalu_ulang(db, data, paksa_jurnal_gagal):
    await db.uji_twin.insert_many([{"id": "t3_a"}, {"id": "t3_b"}])
    async with paksa_jurnal_gagal("sisip", entity_id=KSC):
        res = await twin.post_twin(source_type="uji_twin", base_id="T3", date="2026-11-05", sides=sisi("t3"))
    assert res["seller"]["status"] == res["buyer"]["status"] == "failed"
    assert "Belum dicoba" in (await db.uji_twin.find_one({"id": "t3_b"}))["gl_error"]
    assert await jumlah_je("uji_twin", "T3") == 0
    await twin.post_twin(source_type="uji_twin", base_id="T3", date="2026-11-05", sides=sisi("t3"))
    assert await jumlah_je("uji_twin", "T3") == 2
    assert {d["gl_status"] async for d in db.uji_twin.find({"id": {"$in": ["t3_a", "t3_b"]}})} == {"posted"}


async def test_U4_preflight_sisi_kedua(db, data, paksa_jurnal_gagal):
    await db.uji_twin.insert_many([{"id": "t4_a"}, {"id": "t4_b"}])
    async with paksa_jurnal_gagal("akun", entity_id=KANDA, kode_akun="2-1250"):
        with pytest.raises(twin.TwinJournalError) as e:
            await twin.preflight_twin(source_type="uji_twin", base_id="T4", date="2026-11-05", sides=sisi("t4"))
    assert e.value.side == "buyer" and e.value.cause == "account"
    assert "gl_status" not in await db.uji_twin.find_one({"id": "t4_a"})


# ── U5–U9: konfirmasi ─────────────────────────────────────────────────────────────────────────────────
async def test_U5_konfirmasi_ditolak_bila_akun_pembeli_nonaktif(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    async with paksa_jurnal_gagal("akun", entity_id=KANDA, kode_akun="2-1250"):
        r = await konfirmasi(klien, kepala_admin, "p5")
    assert r.status_code == 409, r.text
    docs = await db.interco_transactions.find({"pair_id": "p5"}).to_list(2)
    assert {d["status"] for d in docs} == {"draft"} and not any("saga_lock" in d for d in docs)
    assert await jumlah_je("interco_transaction", "p5") == 0


async def test_U6_konfirmasi_bersih(klien, kepala_admin, db, data):
    ar0, ap0 = await saldo_akun("1-1250", KSC), await saldo_akun("2-1250", KANDA)
    r = await konfirmasi(klien, kepala_admin, "p6")
    assert r.status_code == 200, r.text
    docs = {d["role"]: d for d in await db.interco_transactions.find({"pair_id": "p6"}).to_list(2)}
    assert docs["seller"]["status"] == docs["buyer"]["status"] == "confirmed"
    assert docs["seller"]["gl_status"] == docs["buyer"]["gl_status"] == "posted"
    js = await db.journal_entries.find({"source_type": "interco_transaction",
                                        "source_id": {"$regex": "^p6:"}}).to_list(5)
    assert sorted((j["source_id"], j["entity_id"], j["total_debit"]) for j in js) == [
        ("p6:buyer", KANDA, 20 * JT), ("p6:seller", KSC, 20 * JT)]
    assert round(await saldo_akun("1-1250", KSC) - ar0, 2) == 20 * JT
    assert round(await saldo_akun("2-1250", KANDA) - ap0, 2) == 20 * JT


async def test_U7_sisi_pembeli_gagal_lalu_diulang(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="interco_transaction"):
        r = await konfirmasi(klien, kepala_admin, "p7")
    assert r.status_code == 200 and r.json()["warning"], r.text
    s, b = await db.interco_transactions.find_one({"id": "p7_s"}), await db.interco_transactions.find_one({"id": "p7_b"})
    assert s["gl_status"] == "posted" and b["gl_status"] == "failed"
    panel = (await klien.get("/api/finance/posting-failures", headers={**kepala_admin, "X-Entity-Id": KANDA})).json()
    assert any(i["id"] == "p7_b" and i["kind"] == "interco_transaction" for i in panel["items"])
    r2 = await klien.post("/api/finance/posting-failures/interco_transaction/p7_b/retry",
                          headers={**kepala_admin, "X-Entity-Id": KANDA})
    assert r2.status_code == 200, r2.text
    assert await jumlah("journal_entries", {"source_type": "interco_transaction", "source_id": "p7:buyer"}) == 1
    assert await jumlah("journal_entries", {"source_type": "interco_transaction", "source_id": "p7:seller"}) == 1
    assert {d["gl_status"] async for d in db.interco_transactions.find({"pair_id": "p7"})} == {"posted"}


async def test_U8_konfirmasi_ulang_ditolak(klien, kepala_admin, data):
    r = await konfirmasi(klien, kepala_admin, "p6")
    assert r.status_code == 400 and "Hanya draf" in r.text
    await ics.repost_gl("p6", "uji")
    assert await jumlah_je("interco_transaction", "p6") == 2


async def test_U9_buat_dan_konfirmasi_ditolak_sebelum_sisip(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    await db.products.insert_one({"id": "prd_x", "name": "Kain Uji X", "code": "PRD-X", "uom": "m", "base_uom": "m",
                                  "status": "active", "lifecycle": "produksi"})
    n0 = await jumlah("interco_transactions", {})
    async with paksa_jurnal_gagal("akun", entity_id=KANDA, kode_akun="2-1250"):
        r = await klien.post("/api/interco/transactions", headers=kepala_admin, json={
            "seller_entity_id": KSC, "buyer_entity_id": KANDA, "ppn_mode": "tanpa_ppn", "submit_now": True,
            # PK-30 (IC-10) — harga ketikan tanpa kontrak & mode PPN di luar pengaturan PT = penyimpangan: wajib alasan
            "override_reason": "uji PK-06 harga manual",
            "items": [{"product_id": "prd_x", "quantity": 10, "unit_price": 100000}]})
    assert r.status_code == 409, r.text
    assert await jumlah("interco_transactions", {}) == n0


# ── U10–U11: retur ────────────────────────────────────────────────────────────────────────────────────
def retur(rp, origin, total=5 * JT):
    base = {"return_pair_id": rp, "origin_pair_id": origin, "seller_entity_id": KSC, "buyer_entity_id": KANDA,
            "subtotal": total, "tax_amount": 0.0, "grand_total": total, "status": "draft", "items": [],
            "timeline": [], "created_by": "Orang Lain", "created_at": now_iso()}
    return [{**base, "id": f"{rp}_ret", "role": "returner", "entity_id": KANDA, "number": f"RB/{rp}"},
            {**base, "id": f"{rp}_rcv", "role": "receiver", "entity_id": KSC, "number": f"RK/{rp}"}]


async def test_U10_setuju_retur_ditolak_bila_akun_penjual_nonaktif(klien, kepala_admin, db, data):
    await bersih(klien, kepala_admin, "p10")
    await db.interco_returns.insert_many(retur("rp10", "p10"))
    await nonaktifkan_akun(KSC, "1-1250")
    try:
        with pytest.raises(twin.TwinJournalError):
            await icret.approve("rp10_ret", AKTOR_UJI)
    finally:
        await aktifkan_akun(KSC, "1-1250")
    assert {d["status"] async for d in db.interco_returns.find({"return_pair_id": "rp10"})} == {"draft"}
    assert await jumlah_je("interco_return", "rp10") == 0


async def test_U11_retur_sisi_gagal_lalu_diulang(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    await bersih(klien, kepala_admin, "p11")
    await db.interco_returns.insert_many(retur("rp11", "p11"))
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="interco_return"):
        res = await icret.approve("rp11_ret", AKTOR_UJI)
    assert res["warning"]
    assert {d["status"] async for d in db.interco_returns.find({"return_pair_id": "rp11"})} == {"approved"}
    r = await klien.post("/api/finance/posting-failures/interco_return/rp11_ret/retry",
                         headers={**kepala_admin, "X-Entity-Id": KANDA})
    assert r.status_code == 200, r.text
    js = await db.journal_entries.find({"source_type": "interco_return", "source_id": {"$regex": "^rp11:"}}).to_list(5)
    assert sorted((j["source_id"], j["total_debit"]) for j in js) == [("rp11:buyer", 5 * JT), ("rp11:seller", 5 * JT)]


# ── U12–U16: pelunasan ────────────────────────────────────────────────────────────────────────────────
async def lunasi(klien, h, pid, *, tanggal=None, key=None, rek="rek_kanda"):
    hh = {**h, "X-Entity-Id": KANDA}
    if key:
        hh["Idempotency-Key"] = key
    return await klien.post("/api/interco/settlements", headers=hh, json={
        "payer_entity_id": KANDA, "payee_entity_id": KSC, "transactions": [{"interco_id": f"{pid}_s"}],
        "settle_date": tanggal or now_iso()[:10], "method": "transfer", "bank_account_id": rek})


async def test_U12_pelunasan_periode_tertutup(klien, kepala_admin, db, data):
    await bersih(klien, kepala_admin, "p12")
    c = await tutup_periode(KSC, "2026-09")
    try:
        r = await lunasi(klien, kepala_admin, "p12", tanggal="2026-09-20")
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    ent = await db.business_entities.find_one({"id": KSC})
    nama = ent.get("short_name") or ent.get("legal_name") or ent.get("name")
    assert r.status_code == 409 and nama in r.text, r.text   # pesan menyebut PT penerima yang periodenya tertutup
    assert (await db.interco_transactions.find_one({"id": "p12_s"}))["settled_amount"] == 0
    assert await jumlah("interco_settlements", {"applied.pair_id": "p12"}) == 0
    assert await jumlah("cash_transactions", {"ref_type": "interco_settlement"}) == 0


async def test_U13_pelunasan_bersih(klien, kepala_admin, db, data):
    ar0, ap0 = await saldo_akun("1-1250", KSC), await saldo_akun("2-1250", KANDA)
    await bersih(klien, kepala_admin, "p13")
    r = await lunasi(klien, kepala_admin, "p13", key="s1")
    assert r.status_code == 200, r.text
    st = r.json()
    assert st["status"] == "posted" and st["gl_status"] == "posted"
    keluar = await db.cash_transactions.find_one({"ref_id": st["id"], "direction": "out"})
    masuk = await db.cash_transactions.find_one({"ref_id": st["id"], "direction": "in"})
    assert (keluar["entity_id"], keluar["account_id"], keluar["amount"]) == (KANDA, "rek_kanda", 20 * JT)
    assert (masuk["entity_id"], masuk["account_id"], masuk["amount"]) == (KSC, "rek_ksc", 20 * JT)
    docs = await db.interco_transactions.find({"pair_id": "p13"}).to_list(2)
    assert all(d["settled_amount"] == 20 * JT and d["status"] == "settled" for d in docs)
    assert round(await saldo_akun("1-1250", KSC) - ar0, 2) == 0
    assert round(await saldo_akun("2-1250", KANDA) - ap0, 2) == 0


async def test_U14_gagal_di_kas_lalu_diulang(klien, kepala_admin, db, data, monkeypatch):
    from services import interco_money_service as icm
    await bersih(klien, kepala_admin, "p14")
    asli = icm.twin_cash
    state = {"n": 1}

    async def gagal_sekali(**kw):
        if state["n"]:
            state["n"] -= 1
            raise RuntimeError("uji: kas kembar dipaksa gagal")
        return await asli(**kw)
    monkeypatch.setattr(icm, "twin_cash", gagal_sekali)
    assert (await lunasi(klien, kepala_admin, "p14", key="s2")).status_code == 500
    st = await db.interco_settlements.find_one({"applied.pair_id": "p14"})
    assert st["status"] == "pending"
    assert (await lunasi(klien, kepala_admin, "p14", key="s2")).status_code == 200
    r3 = await lunasi(klien, kepala_admin, "p14", key="s2")
    assert r3.status_code == 200
    docs = await db.interco_transactions.find({"pair_id": "p14"}).to_list(2)
    assert all(d["settled_amount"] == 20 * JT for d in docs)
    assert await jumlah("cash_transactions", {"ref_id": st["id"]}) == 2
    assert await jumlah_je("interco_settlement", st["id"]) == 2


async def test_U15_sisi_penerima_gagal_lalu_diulang(klien, kepala_admin, db, data, paksa_jurnal_gagal):
    await bersih(klien, kepala_admin, "p15")
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="interco_settlement"):
        r = await lunasi(klien, kepala_admin, "p15", key="s3")
    assert r.status_code == 200 and r.json()["warning"], r.text
    st = await db.interco_settlements.find_one({"id": r.json()["id"]})
    assert st["gl_status_payer"] == "posted" and st["gl_status_payee"] == "failed"
    panel = (await klien.get("/api/finance/posting-failures", headers={**kepala_admin, "X-Entity-Id": KSC})).json()
    assert any(i["id"] == st["id"] and i["kind"] == "interco_settlement_payee" for i in panel["items"])
    r2 = await klien.post(f"/api/finance/posting-failures/interco_settlement_payee/{st['id']}/retry",
                          headers={**kepala_admin, "X-Entity-Id": KSC})
    assert r2.status_code == 200, r2.text
    assert await jumlah("journal_entries", {"source_type": "interco_settlement", "source_id": f"{st['id']}:payee"}) == 1
    assert await jumlah("journal_entries", {"source_type": "interco_settlement", "source_id": f"{st['id']}:payer"}) == 1


async def test_U16_sudah_lunas_dan_jurnal_gagal(klien, kepala_admin, db, data):
    n0 = await jumlah("interco_settlements", {})
    r = await lunasi(klien, kepala_admin, "p13")
    assert r.status_code == 400 and "lunas" in r.text, r.text
    await bersih(klien, kepala_admin, "p16")
    await db.interco_transactions.update_one({"id": "p16_b"}, {"$set": {"gl_status": "failed"}})
    r = await lunasi(klien, kepala_admin, "p16")
    assert r.status_code == 409 and "jurnal yang gagal terbit" in r.text, r.text
    assert await jumlah("interco_settlements", {}) == n0


async def test_U18_pengguna_bukan_pihak(klien, akun, sesi, peran_tanpa_acuan, db, data):
    zzz = await pt_uji("ZZZ")
    p = await peran_tanpa_acuan({"interco": ["view", "approve", "settle"]})
    h = await sesi(await akun(p, entitas=(zzz,)), entitas=zzz)
    r = await klien.post("/api/interco/transactions/p18_s/confirm", headers=h, json={"note": ""})
    assert r.status_code == 404, r.text
    r = await klien.post("/api/interco/settlements", headers=h, json={
        "payer_entity_id": KANDA, "payee_entity_id": KSC, "transactions": [{"interco_id": "p18_s"}],
        "method": "transfer"})
    assert r.status_code == 403, r.text
    assert {d["status"] async for d in db.interco_transactions.find({"pair_id": "p18"})} == {"draft"}
