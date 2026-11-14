"""PK-23 — aset tetap: periksa dulu, sumber dana wajib, pindah antar-PT yang utuh, susut tepat sampai habis
(docs/blueprint/unit/PK-23.md).

Persiapan bersama (fixture, disisipkan langsung): `ent_ksc` punya rekening bank R-B1 bersaldo awal Rp 50.000.000
(jurnal saldo awal Dr 1-1100 / Cr 3-2900 lewat `bank_service._post_opening`), `ent_kanda` punya rekening bank R-K1
bersaldo awal Rp 20.000.000; pemetaan `aset.sumber_hutang` → 2-1100 disimpan untuk `ent_ksc` saja. Aset yang dipakai
lebih dari satu tes (A1) lahir lewat API. U14 (dua permintaan pindah bersamaan) di MongoDB asli:
`backend/tests/test_bp_PK23_pindah_bersamaan_mongo.py`.
"""
import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, jumlah, tutup_periode
from services.book_date import tanggal_buku

KSC, KANDA = "ent_ksc", "ent_kanda"
JT = 1_000_000
URL = "/api/fixed-assets"
PANEL = "/api/finance/posting-failures"
REK_B1 = {"id": "rek_pk23_b1", "name": "R-B1 BCA KSC", "entity_id": KSC, "account_type": "bank",
          "cash_type": "kas_besar", "bank_name": "BCA", "account_number": "2301", "is_active": True,
          "opening_balance": 50 * JT}
REK_K1 = {"id": "rek_pk23_k1", "name": "R-K1 BCA Kanda", "entity_id": KANDA, "account_type": "bank",
          "cash_type": "kas_besar", "bank_name": "BCA", "account_number": "2302", "is_active": True,
          "opening_balance": 20 * JT}
SIMPAN: dict = {}


@pytest.fixture(scope="module")
async def siap(db):
    from services import bank_service
    from services import gl_mapping_service as glm
    for r in (REK_B1, REK_K1):
        await db.bank_accounts.insert_one(dict(r))
        await bank_service._post_opening(r, r["opening_balance"], "bank_opening_balance", r["id"])
    try:
        await glm.set_mapping("aset.sumber_hutang", KSC, "2-1100", "fixture uji PK-23", AKTOR_UJI)
    except KeyError:
        pass   # kode lama: kunci pemetaan belum ada (uji tetap jalan supaya merahnya terbaca)
    return True


def _isi(**kw):
    base = {"name": "Mesin potong PK-23", "category": "Peralatan & Mesin", "acquisition_cost": 12 * JT,
            "acquisition_date": tanggal_buku(), "useful_life_months": 48, "salvage_value": 0, "entity_id": KSC,
            "funding_source": "kas", "account_id": REK_B1["id"]}
    base.update(kw)
    return {k: v for k, v in base.items() if v is not None}


async def _jurnal(db, source_type: str, source_id: str):
    return await db.journal_entries.find({"source_type": source_type, "source_id": source_id,
                                          "status": {"$ne": "void"}}, {"_id": 0}).to_list(10)


def _baris(je):
    return {(ln["account_code"], round(ln["debit"], 2), round(ln["credit"], 2)) for ln in je["lines"]}


async def _mutasi(db, kode: str, entity_id: str) -> float:
    """Σ debit − kredit akun `kode` di jurnal tidak-void PT itu (tanda dihitung sendiri, bukan dari laporan)."""
    total = 0.0
    async for je in db.journal_entries.find({"entity_id": entity_id, "status": {"$ne": "void"}}, {"_id": 0}):
        for ln in je.get("lines") or []:
            if ln.get("account_code") == kode:
                total += float(ln.get("debit") or 0) - float(ln.get("credit") or 0)
    return round(total, 2)


async def _saldo_rekening(account_id: str) -> float:
    """Saldo awal rekening + Σ mutasi kas yang menunjuk rekening itu."""
    from services import bank_service
    led = await bank_service.account_ledger(account_id)
    sendiri = [t for t in led["transactions"] if t.get("account_id") == account_id]
    return round(float(led.get("opening_balance") or 0)
                 + sum(t["amount"] if t["direction"] == "in" else -t["amount"] for t in sendiri), 2)


async def _ulang(klien, kepala, kind, doc_id):
    return await klien.post(f"{PANEL}/{kind}/{doc_id}/retry", headers=kepala)


async def _susutkan(aid: str, periode: str):
    from services import fixed_asset_service as svc
    return await svc.run_depreciation(periode, AKTOR_UJI, asset_id=aid, scope={"entity_id": {"$in": [KSC, KANDA]}})


def _periode(awal: str, n: int) -> str:
    y, m = int(awal[:4]), int(awal[5:7])
    idx = y * 12 + m - 1 + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


# ── U1 — periode tertutup: tidak ada tulisan apa pun ─────────────────────────────────────────────────────────────────
async def test_PK23_U1_periode_tertutup_tanpa_tulisan(klien, kepala_admin, db, siap):
    c = await tutup_periode(KSC, "2026-10")
    n_aset, n_kas, n_je = (await jumlah("fin_fixed_assets", {}), await jumlah("cash_transactions", {}),
                           await jumlah("journal_entries", {}))
    try:
        r = await klien.post(URL, headers=kepala_admin, json=_isi(name="Mesin U1", acquisition_date="2026-10-15"))
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    assert "DITUTUP" in r.text
    assert (await jumlah("fin_fixed_assets", {}), await jumlah("cash_transactions", {}),
            await jumlah("journal_entries", {})) == (n_aset, n_kas, n_je)


# ── U2 — sumber kas: satu jurnal, satu kas di rekening, buku kas = buku besar ───────────────────────────────────────
async def test_PK23_U2_kas_satu_jurnal_satu_kas_saldo_sama(klien, kepala_admin, db, siap):
    gl0 = await _mutasi(db, "1-1100", KSC)
    r = await klien.post(URL, headers=kepala_admin, json=_isi(name="Mesin U2"))
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["funding_source"] == "kas" and a["gl_status"] == "posted" and a["account_id"] == REK_B1["id"]
    jes = await _jurnal(db, "fixed_asset_acquisition", a["id"])
    assert len(jes) == 1
    # Dr 1-2100 12.000.000 / Cr 1-1100 12.000.000
    assert _baris(jes[0]) == {("1-2100", 12 * JT, 0.0), ("1-1100", 0.0, 12 * JT)}
    kas = await db.cash_transactions.find({"ref_type": "fixed_asset", "ref_id": a["id"]}, {"_id": 0}).to_list(5)
    assert len(kas) == 1
    assert (kas[0]["direction"], kas[0]["amount"], kas[0]["account_id"], kas[0]["gl_status"]) == \
        ("out", 12 * JT, REK_B1["id"], "not_required")
    assert a["acquisition_cash_txn_id"] == kas[0]["id"]
    # saldo R-B1 = 50.000.000 − 12.000.000 = 38.000.000; buku besar 1-1100 ent_ksc turun 12.000.000 yang sama.
    # Seed tests_mem membawa satu kas lama ent_ksc tanpa rekening (Rp 100.000.000, dijurnal ke 1-1100) yang diserap
    # rekening bank tunggal PT (`bank_service._txns_for`) → buku rekening R-B1 seutuhnya = saldo 1-1100 PT itu.
    from services import bank_service
    assert await _saldo_rekening(REK_B1["id"]) == 38 * JT
    assert round(await _mutasi(db, "1-1100", KSC) - gl0, 2) == -12 * JT
    assert (await bank_service.account_ledger(REK_B1["id"]))["balance"] == await _mutasi(db, "1-1100", KSC)
    SIMPAN["u2"] = a["id"]


# ── U3 — jurnal gagal: aset tersimpan `failed`, dilewati penyusutan, diulang dari panel ─────────────────────────────
async def test_PK23_U3_jurnal_gagal_dilewati_susut_lalu_diulang(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    # Koreksi blueprint (laporan PK-23): persiapan "Akun 1-2100 nonaktif" ditolak PERIKSA (U6, 400) sebelum tulisan;
    # kegagalan jurnal dipaksa di pintu sisip (`paksa_jurnal_gagal("sisip")`), harapan lain tetap.
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="fixed_asset_acquisition"):
        r = await klien.post(URL, headers=kepala_admin, json=_isi(name="Mesin U3"))
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert r.json()["gl_status"] == "failed"
    panel = (await klien.get(PANEL, headers=kepala_admin, params={"kind": "fixed_asset"})).json()
    assert aid in {x["id"] for x in panel["items"]}
    periode = tanggal_buku()[:7]
    r1 = await klien.post(f"{URL}/run-depreciation", headers=kepala_admin,
                          json={"period": periode, "asset_id": aid, "entity_id": KSC})
    assert r1.status_code == 200, r1.text
    assert r1.json()["posted"] == 0
    alasan = {x["asset_id"]: x["reason"] for x in r1.json().get("skipped_assets", [])}
    assert "belum berjurnal" in alasan.get(aid, ""), r1.json()
    assert await jumlah("fin_depreciation_entries", {"asset_id": aid}) == 0
    r2 = await _ulang(klien, kepala_admin, "fixed_asset", aid)
    assert r2.status_code == 200 and r2.json()["gl_status"] == "posted", r2.text
    assert len(await _jurnal(db, "fixed_asset_acquisition", aid)) == 1
    assert await jumlah("cash_transactions", {"ref_type": "fixed_asset", "ref_id": aid}) == 1
    r3 = await klien.post(f"{URL}/run-depreciation", headers=kepala_admin,
                          json={"period": periode, "asset_id": aid, "entity_id": KSC})
    assert r3.status_code == 200 and r3.json()["posted"] == 1, r3.text
    assert await jumlah("fin_depreciation_entries", {"asset_id": aid}) == 1


# ── U4 — sumber hutang: tanpa kas, kas besar tidak berubah ──────────────────────────────────────────────────────────
async def test_PK23_U4_hutang_tanpa_kas(klien, kepala_admin, db, siap):
    kas0 = await _mutasi(db, "1-1100", KSC)
    r = await klien.post(URL, headers=kepala_admin,
                         json=_isi(name="Mesin U4", acquisition_cost=8 * JT, funding_source="hutang", account_id=None))
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["funding_source"] == "hutang" and a["funding_account"] == "2-1100"
    jes = await _jurnal(db, "fixed_asset_acquisition", a["id"])
    assert len(jes) == 1 and _baris(jes[0]) == {("1-2100", 8 * JT, 0.0), ("2-1100", 0.0, 8 * JT)}
    assert await jumlah("cash_transactions", {"ref_id": a["id"]}) == 0
    assert await _mutasi(db, "1-1100", KSC) == kas0


# ── U5 — hutang belum dipetakan (ent_kanda) & tanpa sumber dana ─────────────────────────────────────────────────────
async def test_PK23_U5_hutang_belum_dipetakan_dan_tanpa_sumber(klien, kepala_admin, db, siap):
    n0 = await jumlah("fin_fixed_assets", {})
    r = await klien.post(URL, headers=kepala_admin,
                         json=_isi(name="Mesin U5", entity_id=KANDA, funding_source="hutang", account_id=None))
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ('Sumber dana "Dibeli secara hutang" belum bisa dipakai karena akun lawannya belum '
                                  'ditetapkan di Pemetaan Akun.')
    r2 = await klien.post(URL, headers=kepala_admin, json=_isi(name="Mesin U5b", funding_source=None, account_id=None))
    assert r2.status_code == 400, r2.text
    assert r2.json()["detail"] == "Pilih sumber dana perolehan aset."
    assert await jumlah("fin_fixed_assets", {}) == n0


# ── U6 — akun aset bukan akun aset tetap ────────────────────────────────────────────────────────────────────────────
async def test_PK23_U6_akun_aset_tidak_sah(klien, kepala_admin, db, siap):
    n0 = await jumlah("fin_fixed_assets", {})
    r = await klien.post(URL, headers=kepala_admin, json=_isi(name="Mesin U6", gl_account_asset="6-1000"))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Akun 6-1000 bukan akun aset tetap yang aktif."
    # akumulasi penyusutan juga bukan akun aset
    r2 = await klien.post(URL, headers=kepala_admin, json=_isi(name="Mesin U6b", gl_account_asset="1-2900"))
    assert r2.status_code == 400 and "1-2900 bukan akun aset tetap" in r2.text, r2.text
    assert await jumlah("fin_fixed_assets", {}) == n0


# ── U7 — 48 bulan: bulan terakhir mengambil seluruh sisa ────────────────────────────────────────────────────────────
async def test_PK23_U7_susut_tepat_habis(klien, kepala_admin, db, siap):
    r = await klien.post(URL, headers=kepala_admin, json=_isi(
        name="Laptop U7", category="Inventaris & Perabot Kantor", acquisition_cost=1 * JT, useful_life_months=48,
        acquisition_date="2026-01-15", funding_source="hutang", account_id=None))
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    for i in range(48):
        await _susutkan(aid, _periode("2026-01", i))
    ents = await db.fin_depreciation_entries.find({"asset_id": aid}, {"_id": 0}).sort("period", 1).to_list(60)
    assert len(ents) == 48
    # bulanan = round(1.000.000 / 48, 2) = 20.833,33; Σ 47 bulan = 979.166,51; bulan 48 = 1.000.000 − 979.166,51
    assert all(e["amount"] == 20833.33 for e in ents[:47])
    assert round(sum(e["amount"] for e in ents[:47]), 2) == 979166.51
    assert ents[47]["amount"] == 20833.49
    assert round(sum(e["amount"] for e in ents), 2) == 1 * JT
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert (a["accumulated_depreciation"], a["book_value"], a["status"]) == (1 * JT, 0.0, "fully_depreciated")
    jadwal = (await klien.get(f"{URL}/{aid}", headers=kepala_admin)).json()["schedule"]
    assert jadwal[-1]["amount"] == 20833.49 and jadwal[-1]["book_value"] == 0.0


# ── U8 — pindah ke ent_kanda dengan nilai buku ──────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
async def a1(klien, kepala_admin, db, siap):
    """Aset A1 `ent_ksc` (perolehan 12.000.000, 12 bulan susut × 250.000 = akumulasi 3.000.000) dipindah ke
    `ent_kanda` tanpa harga, lewat API. Dipakai U8, U12, U13."""
    r = await klien.post(URL, headers=kepala_admin, json=_isi(
        name="Mesin A1", acquisition_date="2025-11-03", funding_source="hutang", account_id=None))
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    for i in range(12):
        await _susutkan(aid, _periode("2025-11", i))
    akum = (await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0}))["accumulated_depreciation"]
    ar0, ap0 = await _mutasi(db, "1-1250", KSC), await _mutasi(db, "2-1250", KANDA)
    r = await klien.post(f"{URL}/{aid}/transfer", headers=kepala_admin,
                         json={"to_entity_id": KANDA, "reason": "dipakai produksi Kanda mulai bulan ini"})
    return {"id": aid, "akum": akum, "ar0": ar0, "ap0": ap0, "status": r.status_code, "json": r.json()}


async def test_PK23_U8_pindah_nilai_buku(db, a1):
    from services import interco_money_service as money
    aid = a1["id"]
    assert a1["akum"] == 3 * JT
    assert a1["status"] == 200, a1["json"]
    baru = a1["json"]["new_asset"]
    assert baru["id"] == f"{aid}_tr" and baru["entity_id"] == KANDA and baru["funding_source"] == "antar_pt"
    assert baru["acquisition_cost"] == 9 * JT and baru["status"] == "active"
    kirim = await _jurnal(db, "fixed_asset_transfer", f"{aid}:from")
    terima = await _jurnal(db, "fixed_asset_acquisition", f"{aid}_tr")
    assert len(kirim) == 1 and len(terima) == 1
    assert kirim[0]["entity_id"] == KSC and terima[0]["entity_id"] == KANDA
    # ent_ksc: Dr 1-2900 3.000.000, Dr 1-1250 9.000.000 / Cr 1-2100 12.000.000
    assert _baris(kirim[0]) == {("1-2900", 3 * JT, 0.0), ("1-1250", 9 * JT, 0.0), ("1-2100", 0.0, 12 * JT)}
    # ent_kanda: Dr 1-2100 9.000.000 / Cr 2-1250 9.000.000
    assert _baris(terima[0]) == {("1-2100", 9 * JT, 0.0), ("2-1250", 0.0, 9 * JT)}
    lama = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert lama["status"] == "transferred" and lama["transfer"]["intent"]["status"] == "done"
    assert lama["transfer"]["settle_status"] == "none"
    # piutang antar-PT 9.000.000 = utang antar-PT 9.000.000
    assert await _mutasi(db, "1-1250", KSC) - a1["ar0"] == 9 * JT
    assert a1["ap0"] - await _mutasi(db, "2-1250", KANDA) == 9 * JT
    assert (await money.non_trade_outstanding(KSC, KANDA))["asset_transfer_outstanding"] == 9 * JT


# ── U9 — periode pengirim tertutup: tidak ada apa pun di kedua PT ───────────────────────────────────────────────────
async def test_PK23_U9_periode_pengirim_tertutup(klien, kepala_admin, db, siap):
    r = await klien.post(URL, headers=kepala_admin, json=_isi(
        name="Mesin A9", acquisition_date="2026-09-01", funding_source="hutang", account_id=None))
    assert r.status_code == 200, r.text
    a9 = r.json()["id"]
    c = await tutup_periode(KSC, "2026-10")
    try:
        r = await klien.post(f"{URL}/{a9}/transfer", headers=kepala_admin,
                             json={"to_entity_id": KANDA, "reason": "uji periode tertutup", "transfer_date": "2026-10-20"})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409, r.text
    a = await db.fin_fixed_assets.find_one({"id": a9}, {"_id": 0})
    assert a["status"] == "active" and not (a.get("transfer") or {}).get("intent")
    assert await jumlah("fin_fixed_assets", {"entity_id": KANDA, "name": "Mesin A9"}) == 0
    assert await jumlah("journal_entries", {"source_type": "fixed_asset_transfer", "source_id": f"{a9}:from"}) == 0
    assert await jumlah("journal_entries", {"source_type": "fixed_asset_acquisition", "source_id": f"{a9}_tr"}) == 0


# ── U10 — aset yang sudah pindah tidak bisa diubah, dilepas, atau disusutkan ────────────────────────────────────────
async def test_PK23_U10_aset_pindah_terkunci(klien, kepala_admin, db, siap):
    # fixture: aset `transferred` disisipkan langsung (alur pindah = U8)
    await db.fin_fixed_assets.insert_one({
        "id": "fa_pk23_u10", "number": "FA-U10", "name": "Mesin U10", "category": "Peralatan & Mesin",
        "acquisition_cost": 12 * JT, "acquisition_date": "2025-11-03", "useful_life_months": 48, "salvage_value": 0,
        "entity_id": KSC, "gl_account_asset": "1-2100", "gl_account_dep_exp": "6-6000", "gl_account_acc_dep": "1-2900",
        "funding_source": "hutang", "funding_account": "2-1100", "monthly_depreciation": 250000.0,
        "accumulated_depreciation": 3 * JT, "book_value": 0.0, "depreciated_months": 12, "status": "transferred",
        "gl_status": "posted", "transfer": {"to_entity_id": KANDA, "to_entity_name": "CV Kanda", "from_entity_id": KSC,
                                            "price": 9 * JT, "settled": False, "settle_status": "none"},
        "created_at": now_iso(), "updated_at": now_iso()})
    r = await klien.patch(f"{URL}/fa_pk23_u10", headers=kepala_admin, json={"name": "Nama baru"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == ("Aset FA-U10 sudah dipindahkan ke CV Kanda, jadi tidak bisa diubah, disusutkan, "
                                  "atau dilepas di sini.")
    r = await klien.post(f"{URL}/fa_pk23_u10/dispose", headers=kepala_admin, json={"proceeds": 1 * JT})
    assert r.status_code == 409 and "sudah dipindahkan ke CV Kanda" in r.text, r.text
    r = await klien.post(f"{URL}/run-depreciation", headers=kepala_admin,
                         json={"period": tanggal_buku()[:7], "asset_id": "fa_pk23_u10", "entity_id": KSC})
    assert r.status_code == 200 and r.json()["posted"] == 0, r.text
    a = await db.fin_fixed_assets.find_one({"id": "fa_pk23_u10"}, {"_id": 0})
    assert (a["status"], a["name"], a["accumulated_depreciation"]) == ("transferred", "Mesin U10", 3 * JT)
    assert await jumlah("journal_entries", {"source_id": "fa_pk23_u10"}) == 0


# ── U11 — sisi penerima ditolak pemeriksa awal; sesudah akun aktif: tepat sekali ────────────────────────────────────
async def test_PK23_U11_penerima_ditolak_pemeriksa_awal_lalu_sekali(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    r = await klien.post(URL, headers=kepala_admin, json=_isi(
        name="Mesin A11", acquisition_date="2026-09-01", funding_source="hutang", account_id=None))
    assert r.status_code == 200, r.text
    a11 = r.json()["id"]
    n_aset, n_je = await jumlah("fin_fixed_assets", {}), await jumlah("journal_entries", {})
    isi = {"to_entity_id": KANDA, "reason": "uji pemeriksa awal sisi penerima"}
    async with paksa_jurnal_gagal("akun", entity_id=KANDA, kode_akun="2-1250"):
        r = await klien.post(f"{URL}/{a11}/transfer", headers=kepala_admin, json=isi)
    assert r.status_code == 409, r.text
    assert (await jumlah("fin_fixed_assets", {}), await jumlah("journal_entries", {})) == (n_aset, n_je)
    assert (await db.fin_fixed_assets.find_one({"id": a11}))["status"] == "active"
    r = await klien.post(f"{URL}/{a11}/transfer", headers=kepala_admin, json=isi)
    assert r.status_code == 200, r.text
    assert await jumlah("fin_fixed_assets", {"id": f"{a11}_tr"}) == 1
    assert await jumlah("fin_fixed_assets", {}) == n_aset + 1
    assert len(await _jurnal(db, "fixed_asset_transfer", f"{a11}:from")) == 1
    assert len(await _jurnal(db, "fixed_asset_acquisition", f"{a11}_tr")) == 1


# ── U12 — catat bayar oleh pelaku tanpa akses di PT pembayar ────────────────────────────────────────────────────────
async def test_PK23_U12_bayar_tanpa_akses_pt_pembayar(klien, akun, sesi, peran_tanpa_acuan, db, a1):
    a1 = a1["id"]
    rid = await peran_tanpa_acuan({"fixed_asset": ["view", "update"]}, label="Aset Tetap KSC PK23")
    h = await sesi(await akun(rid, entitas=(KSC,)))
    r = await klien.post(f"{URL}/{a1}/transfer/settle", headers=h, json={"note": ""})
    assert r.status_code == 403, r.text
    tr = (await db.fin_fixed_assets.find_one({"id": a1}))["transfer"]
    assert r.json()["detail"] == f"Anda belum punya akses di {tr['to_entity_name']} untuk mencatat pembayaran ini."
    assert tr["settle_status"] == "none" and not tr["settled"]
    assert await jumlah("cash_transactions", {"ref_type": "fixed_asset_transfer", "ref_id": a1}) == 0


# ── U13 — catat bayar dua kali: sekali saja ─────────────────────────────────────────────────────────────────────────
async def test_PK23_U13_bayar_dua_kali_sekali(klien, kepala_admin, db, a1):
    a1 = a1["id"]
    ar0, ap0 = await _mutasi(db, "1-1250", KSC), await _mutasi(db, "2-1250", KANDA)
    r = await klien.post(f"{URL}/{a1}/transfer/settle", headers=kepala_admin, json={"note": ""})
    assert r.status_code == 200, r.text
    kas = await db.cash_transactions.find({"ref_type": "fixed_asset_transfer", "ref_id": a1}, {"_id": 0}).to_list(5)
    arah = {(k["entity_id"], k["direction"], k["amount"]) for k in kas}
    assert arah == {(KANDA, "out", 9 * JT), (KSC, "in", 9 * JT)}
    # piutang (ent_ksc) dan utang (ent_kanda) antar-PT dari pindah A1 = 0 sesudah dibayar
    assert round(await _mutasi(db, "1-1250", KSC) - ar0, 2) == -9 * JT
    assert round(await _mutasi(db, "2-1250", KANDA) - ap0, 2) == 9 * JT
    tr = (await db.fin_fixed_assets.find_one({"id": a1}))["transfer"]
    assert tr["settle_status"] == "settled" and tr["settled"] is True
    r2 = await klien.post(f"{URL}/{a1}/transfer/settle", headers=kepala_admin, json={"note": ""})
    assert r2.status_code in (400, 409), r2.text
    assert await jumlah("cash_transactions", {"ref_type": "fixed_asset_transfer", "ref_id": a1}) == 2


# ── Tambahan: pelepasan berklaim, penanda entri penyusutan, aset lama tanpa penanda ─────────────────────────────────
async def test_PK23_lepas_periode_tertutup_dan_jurnal_gagal_status_kembali(klien, kepala_admin, db, siap,
                                                                           paksa_jurnal_gagal):
    aid = SIMPAN["u2"]
    c = await tutup_periode(KSC, "2026-10")
    try:
        r = await klien.post(f"{URL}/{aid}/dispose", headers=kepala_admin, json={"proceeds": 0, "date": "2026-10-20"})
    finally:
        await db.period_closings.delete_one({"id": c["id"]})
    assert r.status_code == 409 and "DITUTUP" in r.text, r.text
    assert (await db.fin_fixed_assets.find_one({"id": aid}))["status"] == "active"
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="fixed_asset_disposal"):
        r = await klien.post(f"{URL}/{aid}/dispose", headers=kepala_admin, json={"proceeds": 0})
    assert r.status_code == 409 and "Jurnal pelepasan gagal" in r.text, r.text
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert a["status"] == "active" and not a.get("disposal") and not a.get("disposal_gl_status")
    assert await jumlah("journal_entries", {"source_type": "fixed_asset_disposal", "source_id": aid}) == 0
    r = await klien.post(f"{URL}/{aid}/dispose", headers=kepala_admin, json={"proceeds": 0})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "disposed"
    assert len(await _jurnal(db, "fixed_asset_disposal", aid)) == 1


async def test_PK23_entri_susut_gagal_dilaporkan_lalu_diulang(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    r = await klien.post(URL, headers=kepala_admin, json=_isi(
        name="Mesin susut gagal", acquisition_date="2026-09-01", funding_source="hutang", account_id=None))
    aid = r.json()["id"]
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="fixed_asset_depreciation"):
        r = await klien.post(f"{URL}/run-depreciation", headers=kepala_admin,
                             json={"period": "2026-09", "asset_id": aid, "entity_id": KSC})
    assert r.status_code == 200, r.text
    assert r.json()["posted"] == 0 and [f["asset_id"] for f in r.json()["failed"]] == [aid]
    e = await db.fin_depreciation_entries.find_one({"asset_id": aid, "period": "2026-09"}, {"_id": 0})
    assert e["gl_status"] == "failed"
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert a["accumulated_depreciation"] == 0 and a["depreciated_months"] == 0   # register menunggu jurnal
    # periode berikutnya menunggu periode yang belum berjurnal
    r = await klien.post(f"{URL}/run-depreciation", headers=kepala_admin,
                         json={"period": "2026-10", "asset_id": aid, "entity_id": KSC})
    assert r.json()["posted"] == 0 and "2026-09" in {x["asset_id"]: x["reason"]
                                                      for x in r.json()["skipped_assets"]}.get(aid, "")
    r = await _ulang(klien, kepala_admin, "asset_depreciation", e["id"])
    assert r.status_code == 200 and r.json()["gl_status"] == "posted", r.text
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert a["accumulated_depreciation"] == 250000.0 and a["depreciated_months"] == 1
    assert len(await _jurnal(db, "fixed_asset_depreciation", f"{aid}:2026-09")) == 1


async def test_PK23_aset_lama_tanpa_penanda_dianggap_berjurnal(klien, kepala_admin, db, siap):
    from services import gl_service as gl
    await db.fin_fixed_assets.insert_one({
        "id": "fa_pk23_lama", "number": "FA-LAMA", "name": "Mesin lama", "category": "Peralatan & Mesin",
        "acquisition_cost": 2 * JT, "acquisition_date": "2026-09-01", "useful_life_months": 24, "salvage_value": 0,
        "entity_id": KSC, "gl_account_asset": "1-2100", "gl_account_dep_exp": "6-6000", "gl_account_acc_dep": "1-2900",
        "funding_account": "1-1100", "monthly_depreciation": 83333.33, "accumulated_depreciation": 0.0,
        "book_value": 2 * JT, "depreciated_months": 0, "status": "active", "created_at": now_iso()})
    await gl.post_asset_acquisition(asset_id="fa_pk23_lama", entity_id=KSC, amount=2 * JT, asset_acc="1-2100",
                                    label="FA-LAMA", date="2026-09-01")
    r = await klien.post(f"{URL}/run-depreciation", headers=kepala_admin,
                         json={"period": "2026-09", "asset_id": "fa_pk23_lama", "entity_id": KSC})
    assert r.status_code == 200 and r.json()["posted"] == 1, r.text
    # tanpa jurnal perolehan → belum berjurnal
    await db.fin_fixed_assets.insert_one({"id": "fa_pk23_lama2", "number": "FA-LAMA2", "name": "Tanpa jurnal",
                                          "acquisition_cost": JT, "acquisition_date": "2026-09-01",
                                          "useful_life_months": 12, "entity_id": KSC, "status": "active"})
    r = await klien.post(f"{URL}/fa_pk23_lama2/dispose", headers=kepala_admin, json={"proceeds": 0})
    assert r.status_code == 409 and r.json()["detail"] == ("Aset FA-LAMA2 belum punya jurnal perolehan. Ulangi posting "
                                                           "di Posting Gagal dulu."), r.text


async def test_PK23_meta_sumber_dana_per_pt(klien, kepala_admin, siap):
    ksc = (await klien.get(f"{URL}/meta", headers=kepala_admin, params={"entity_id": KSC})).json()
    kanda = (await klien.get(f"{URL}/meta", headers=kepala_admin, params={"entity_id": KANDA})).json()
    pilih = {x["value"]: x for x in ksc["funding_sources"]}
    assert set(pilih) == {"kas", "hutang", "saldo_awal"}
    assert pilih["kas"]["available"] and pilih["hutang"]["available"] and not pilih["saldo_awal"]["available"]
    assert pilih["saldo_awal"]["reason"] == "Akun lawannya belum ditetapkan di Pemetaan Akun."
    assert not {x["value"]: x for x in kanda["funding_sources"]}["hutang"]["available"]


async def test_PK23_pindah_jurnal_gagal_niat_diteruskan_sekali(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    """Jurnal sisi penerima dipaksa gagal SESUDAH pemeriksa awal: aset tetap `transferring` + niat `pending`, aset
    pengganti `pending`/`failed`; panggilan ulang (pindah lagi / Ulang Posting) meneruskan niat yang sama → 1 aset
    pengganti, 1 jurnal per sisi."""
    r = await klien.post(URL, headers=kepala_admin, json=_isi(
        name="Mesin A15", acquisition_date="2026-09-01", funding_source="hutang", account_id=None))
    aid = r.json()["id"]
    isi = {"to_entity_id": KANDA, "reason": "uji niat pindah diteruskan"}
    async with paksa_jurnal_gagal("sisip", entity_id=KANDA, source_type="fixed_asset_acquisition"):
        r = await klien.post(f"{URL}/{aid}/transfer", headers=kepala_admin, json=isi)
    assert r.status_code == 409 and "belum selesai" in r.text, r.text
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert a["status"] == "transferring" and a["transfer"]["intent"]["status"] == "pending"
    assert a["gl_status_transfer"] == "posted"   # sisi pengirim sudah terbit (urutan sisi: pengirim dulu)
    baru = await db.fin_fixed_assets.find_one({"id": f"{aid}_tr"}, {"_id": 0})
    assert baru["gl_status"] == "failed" and baru["entity_id"] == KANDA
    # aset yang sedang dipindah tidak bisa dilepas / disusutkan
    r = await klien.post(f"{URL}/{aid}/dispose", headers=kepala_admin, json={"proceeds": 0})
    assert r.status_code == 409 and "sedang diproses" in r.text, r.text
    # Ulang Posting dari panel (baris aset pengganti di ent_kanda, jenis `fixed_asset`) → niat diteruskan, dua buku
    h_kanda = {**kepala_admin, "X-Entity-Id": KANDA}
    panel = (await klien.get(PANEL, headers=h_kanda, params={"kind": "fixed_asset"})).json()
    assert f"{aid}_tr" in {x["id"] for x in panel["items"]}
    r = await _ulang(klien, h_kanda, "fixed_asset", f"{aid}_tr")
    assert r.status_code == 200 and r.json()["gl_status"] == "posted", r.text
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert a["status"] == "transferred" and a["transfer"]["intent"]["status"] == "done"
    assert await jumlah("fin_fixed_assets", {"transfer_from.asset_id": aid}) == 1
    assert len(await _jurnal(db, "fixed_asset_transfer", f"{aid}:from")) == 1
    assert len(await _jurnal(db, "fixed_asset_acquisition", f"{aid}_tr")) == 1
    # pindah lagi atas aset yang sudah pindah → 409 berpesan
    r = await klien.post(f"{URL}/{aid}/transfer", headers=kepala_admin, json=isi)
    assert r.status_code == 409 and "sudah dipindahkan" in r.text, r.text


async def test_PK23_pindah_sisi_pengirim_gagal_diulang_dari_panel(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    r = await klien.post(URL, headers=kepala_admin, json=_isi(
        name="Mesin A16", acquisition_date="2026-09-01", funding_source="hutang", account_id=None))
    aid = r.json()["id"]
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="fixed_asset_transfer"):
        r = await klien.post(f"{URL}/{aid}/transfer", headers=kepala_admin,
                             json={"to_entity_id": KANDA, "reason": "uji sisi pengirim gagal"})
    assert r.status_code == 409, r.text
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert a["status"] == "transferring" and a["gl_status_transfer"] == "failed"
    # buku kedua PT sama-sama kosong (sisi penerima tidak dicoba)
    assert await jumlah("journal_entries", {"source_id": {"$in": [f"{aid}:from", f"{aid}_tr"]}}) == 0
    panel = (await klien.get(PANEL, headers=kepala_admin, params={"kind": "fixed_asset_transfer"})).json()
    assert aid in {x["id"] for x in panel["items"]}
    r = await _ulang(klien, kepala_admin, "fixed_asset_transfer", aid)
    assert r.status_code == 200, r.text
    a = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    assert a["status"] == "transferred" and a["gl_status_transfer"] == "posted"
    assert len(await _jurnal(db, "fixed_asset_transfer", f"{aid}:from")) == 1
    assert len(await _jurnal(db, "fixed_asset_acquisition", f"{aid}_tr")) == 1
    SIMPAN["a16"] = aid


async def test_PK23_bayar_jurnal_gagal_kas_dipakai_ulang(klien, kepala_admin, db, siap, paksa_jurnal_gagal):
    aid = SIMPAN["a16"]
    async with paksa_jurnal_gagal("sisip", entity_id=KSC, source_type="fixed_asset_transfer_settlement"):
        r = await klien.post(f"{URL}/{aid}/transfer/settle", headers=kepala_admin, json={"note": ""})
    assert r.status_code == 409 and "Kas pembayaran" in r.text, r.text
    tr = (await db.fin_fixed_assets.find_one({"id": aid}))["transfer"]
    assert tr["settle_status"] == "settling" and not tr["settled"]
    assert await jumlah("cash_transactions", {"ref_type": "fixed_asset_transfer", "ref_id": aid}) == 2
    panel = (await klien.get(PANEL, headers=kepala_admin, params={"kind": "fixed_asset_settle_payee"})).json()
    assert aid in {x["id"] for x in panel["items"]}
    r = await _ulang(klien, kepala_admin, "fixed_asset_settle_payee", aid)
    assert r.status_code == 200, r.text
    tr = (await db.fin_fixed_assets.find_one({"id": aid}))["transfer"]
    assert tr["settle_status"] == "settled" and tr["settled"] is True and len(tr["cash_txn_ids"]) == 2
    assert await jumlah("cash_transactions", {"ref_type": "fixed_asset_transfer", "ref_id": aid}) == 2
    assert len(await _jurnal(db, "fixed_asset_transfer_settlement", f"{aid}:settle:a")) == 1
    assert len(await _jurnal(db, "fixed_asset_transfer_settlement", f"{aid}:settle:b")) == 1
