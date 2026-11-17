"""Latihan Keuangan 17 Nov — Transaksi Kas kategori "Transfer / Top-up" lewat 1-1150 Kas Transit; jurnal dicari dgn no. kas.

Dulu: transfer keluar → beban 6-4000 (beban palsu), transfer masuk → Suspense 1-9999. Pindah dana antar kas/rekening
sendiri tidak mengubah laba: Dr Transit / Cr Kas (keluar) lalu Dr Kas tujuan / Cr Transit (masuk) → Transit kembali nol.
"""
import pytest

pytestmark = pytest.mark.anyio


async def _akun(db, ent):
    await db.bank_accounts.insert_many([
        {"id": f"ba_trf_{i}", "name": f"Kas Transfer Uji {i}", "account_type": "cash" if i == 1 else "bank",
         "cash_type": "kas_besar", "entity_id": ent, "is_active": True, "status": "active", "opening_balance": 0}
        for i in (1, 2)])


async def test_transfer_antar_kas_lewat_transit_dan_bisa_dicari(klien, db, kepala_admin):
    ent = (await db.business_entities.find_one({"status": "active"}, {"_id": 0, "id": 1}))["id"]
    await _akun(db, ent)
    h = {**kepala_admin, "X-Entity-Id": ent}
    r = await klien.post("/api/cash-transactions", headers=h, json={
        "cash_type": "kas_besar", "direction": "in", "amount": 500_000, "category": "modal",
        "description": "modal awal uji transfer", "account_id": "ba_trf_1"})
    assert r.status_code == 200, r.text
    r = await klien.post("/api/cash-transactions", headers=h, json={
        "cash_type": "kas_besar", "direction": "out", "amount": 200_000, "category": "transfer",
        "description": "setor kas toko ke bank (uji)", "account_id": "ba_trf_1"})
    assert r.status_code == 200, r.text
    keluar = r.json()
    r = await klien.post("/api/cash-transactions", headers=h, json={
        "cash_type": "kas_besar", "direction": "in", "amount": 200_000, "category": "transfer",
        "description": "terima setoran kas toko (uji)", "account_id": "ba_trf_2"})
    assert r.status_code == 200, r.text
    je = {j["source_id"]: j async for j in db.journal_entries.find({"source_type": "cash_transaction"}, {"_id": 0})}
    kode_keluar = {(ln["account_code"], ln["debit"] > 0) for ln in je[keluar["id"]]["lines"]}
    assert ("1-1150", True) in kode_keluar                     # Dr Kas Transit
    assert not any(c.startswith("6-") for c, _ in kode_keluar)  # bukan beban
    masuk = je[r.json()["id"]]
    assert {(ln["account_code"], ln["credit"] > 0) for ln in masuk["lines"]} >= {("1-1150", True)}   # Cr Kas Transit
    assert not any(ln["account_code"] == "1-9999" for ln in masuk["lines"])                           # bukan Suspense
    # jurnal bisa dicari dengan nomor transaksi kas (source_label)
    r = await klien.get("/api/gl/journal", headers=h, params={"q": keluar["number"], "page": 1, "page_size": 20})
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items", body) if isinstance(body, dict) else body
    assert any(it.get("source_id") == keluar["id"] for it in items), body
