"""AG-T5 (b) — kartu jurnal manual & balik jurnal, baris Pusat Persetujuan, larangan untuk SEMUA tulisan asisten
(docs/blueprint/unit/AG-T5.md, U12, U13 + U3 antrean + U14 tanpa golongan).

    python -m pytest backend/tests_mem/test_AGT5_jurnal_dan_antrean.py -n 0 -q        # dari root repo

Persiapan — ALUR (API): akun `mgr` (peran bawaan Manajer, PT `ent_ksc`) dan `fin` (Tanpa Acuan: `ai.view` +
`ai_finance.view/pay` + `vendor_bill.view/pay` + `cash.view/create` — TANPA `ai_finance.post`), sakelar akun
`classes: ["B", "C"]`, `ai.tindakan_uang_keluar` = ya untuk `ent_ksc`; kartu lewat `POST /api/ai/tools/prepare_action`,
persetujuan `…/confirm`. FIXTURE: tagihan pemasok (U3 antrean), jurnal manual yang akan dibalik dibuat lewat ALUR
`POST /api/gl/journal`.

Hitung tangan:
  U12  baris D 1-1100 100.000 · K 3-1000 90.000 → debit 100.000 ≠ kredit 90.000 → ditolak; diperbaiki K 100.000 →
       seimbang, total debit 100.000 → ketik ulang "100000". Disetujui: jurnal D 1-1100 100.000 / K 3-1000 100.000;
       saldo 1-1100 (normal debit) +100.000, 3-1000 (normal kredit) +100.000.
  U13  D 1-1200 Piutang Usaha 50.000 / K 4-1000 50.000 → pintu menolak akun kontrol (PK-36) → `failed`/`door`; jumlah
       jurnal tetap.
"""
from __future__ import annotations

import datetime
import json
import uuid

import pytest

from core_utils import now_iso
from pembantu import saldo_akun

pytestmark = pytest.mark.anyio

KSC = "ent_ksc"
TOOL = "/api/ai/tools/prepare_action"
ALASAN = "koreksi setoran modal bulan ini"
SIMPAN: dict = {}


async def _atur(klien, h, key, value, *, scope_type="entity", scope_id=KSC, reason="uji AG-T5 b"):
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]})
    assert r.status_code == 200, r.text


async def _sakelar(klien, h_admin, uid, **nilai):
    r = await klien.patch(f"/api/users/{uid}", headers=h_admin, json={"data": {"ai_finance": nilai}})
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan):
    if SIMPAN:
        return SIMPAN
    mgr = await akun("manager", entitas=(KSC,))
    rid = await peran_tanpa_acuan({"ai": ["view"], "ai_finance": ["view", "pay"], "vendor_bill": ["view", "pay"],
                                   "cash": ["view", "create"], "accounting": ["view", "create", "void"]},
                                  label="AGT5b tanpa post")
    fin = await akun(rid, entitas=(KSC,))
    for u in (mgr, fin):
        await _sakelar(klien, kepala_admin, u["id"], enabled=True, classes=["B", "C"])
    await _atur(klien, kepala_admin, "ai.tindakan_uang_keluar", True)
    SIMPAN.update(mgr=mgr, h_mgr=await sesi(mgr), fin=fin, h_fin=await sesi(fin), h_adm=kepala_admin)
    return SIMPAN


async def _siapkan(klien, h, action, args):
    return await klien.post(TOOL, headers=h, json={"action": action, "args": args, "user_request": "uji AG-T5 b",
                                                   "session_id": ""})


async def _setujui(klien, h, cid, retype, reason=ALASAN):
    return await klien.post(f"/api/ai/actions/{cid}/confirm", headers=h, json={"reason": reason, "retype": retype})


def _jurnal(d, k, ket="setoran modal (uji AG-T5)", akun_d="1-1100", akun_k="3-1000"):
    return {"date": now_iso()[:10], "description": ket,
            "lines": [{"account_code": akun_d, "debit": d, "credit": 0}, {"account_code": akun_k, "debit": 0, "credit": k}]}


# ── U12 — jurnal tidak seimbang ditolak; seimbang → kartu pending ber-confirm_text total debit ───────────────────────
async def test_AGT5_U12_jurnal_manual_seimbang(klien, db, siap):
    n = await db.ai_action_proposals.count_documents({})
    r = await _siapkan(klien, siap["h_mgr"], "journal_manual", _jurnal(100_000, 90_000))
    assert r.status_code == 400 and r.json()["detail"] == "Jurnal tidak seimbang: debit 100.000 ≠ kredit 90.000.", r.text
    assert await db.ai_action_proposals.count_documents({}) == n
    r = await _siapkan(klien, siap["h_mgr"], "journal_manual", _jurnal(100_000, 100_000))
    assert r.status_code == 200, r.text
    k = r.json()["card"]
    assert (k["status"], k["class"], k["risk"]) == ("pending", "C", "high")
    assert k["plan"]["confirm_text"] == "100000" and k["plan"]["amount"] == 100_000
    labels = [x["label"] for x in k["plan"]["rows"]]
    assert any(x.startswith("Debit 1-1100") for x in labels) and any(x.startswith("Kredit 3-1000") for x in labels)
    jml = await db.journal_entries.count_documents({"source_type": "manual"})
    d0, k0 = await saldo_akun("1-1100", KSC), await saldo_akun("3-1000", KSC)
    r = await _setujui(klien, siap["h_mgr"], k["id"], "100.000")
    assert r.status_code == 200 and r.json()["status"] == "confirmed", r.text
    je = await db.journal_entries.find_one({"ai_card_id": k["id"]}, {"_id": 0})
    assert je and je["source_type"] == "manual" and je["total_debit"] == 100_000
    assert await db.journal_entries.count_documents({"source_type": "manual"}) == jml + 1
    assert r.json()["result"]["document"]["number"] == je["number"]
    assert round(await saldo_akun("1-1100", KSC) - d0, 2) == 100_000
    assert round(await saldo_akun("3-1000", KSC) - k0, 2) == 100_000    # saldo normal kredit: kredit menambah
    SIMPAN.update(je=je)
    print("CONTOH_U12", json.dumps({"jurnal": je["number"], "lines": je["lines"], "saldo_1_1100": [d0, await saldo_akun(
        "1-1100", KSC)], "saldo_3_1000": [k0, await saldo_akun("3-1000", KSC)]}, ensure_ascii=False, default=str))


# ── U13 — akun kontrol piutang: pintu menolak (PK-36) → failed/door, jumlah jurnal tetap ─────────────────────────────
async def test_AGT5_U13_akun_kontrol_ditolak_pintu(klien, db, siap):
    r = await _siapkan(klien, siap["h_mgr"], "journal_manual", _jurnal(50_000, 50_000, akun_d="1-1200", akun_k="4-1000"))
    assert r.status_code == 200, r.text
    k = r.json()["card"]
    n = await db.journal_entries.count_documents({})
    langsung = await klien.post("/api/gl/journal", headers=siap["h_mgr"], json=_jurnal(50_000, 50_000, akun_d="1-1200",
                                                                                      akun_k="4-1000"))
    assert langsung.status_code == 422, langsung.text
    r = await _setujui(klien, siap["h_mgr"], k["id"], "50000")
    assert r.status_code == 200, r.text
    out = r.json()
    assert (out["status"], out["error_code"]) == ("failed", "door")
    assert out["error"] == langsung.json()["detail"] and out["result"]["status_code"] == 422
    assert await db.journal_entries.count_documents({}) == n


# ── balik jurnal: ketik ulang NOMOR jurnal; sidik membaca status jurnal ───────────────────────────────────────────────
async def test_AGT5_balik_jurnal(klien, db, siap):
    je = SIMPAN["je"]
    r = await _siapkan(klien, siap["h_mgr"], "journal_reverse", {"entry_id": je["id"], "date": now_iso()[:10],
                                                                 "reason": "salah catat setoran"})
    assert r.status_code == 200, r.text
    k = r.json()["card"]
    assert k["plan"]["confirm_text"] == je["number"] and k["retype_kind"] == "text"
    r = await _setujui(klien, siap["h_mgr"], k["id"], "JE-00001")
    assert r.status_code == 400 and r.json()["detail"] == "Ketik ulang nomor jurnal persis seperti di kartu.", r.text
    r = await _setujui(klien, siap["h_mgr"], k["id"], je["number"].lower())
    assert r.status_code == 200 and r.json()["status"] == "confirmed", r.text
    rev = await db.journal_entries.find_one({"ai_card_id": k["id"]}, {"_id": 0})
    assert rev and rev["source_type"] == "reversal" and rev["ref"]["reverses_entry_id"] == je["id"]
    asal = await db.journal_entries.find_one({"id": je["id"]}, {"_id": 0})
    assert asal["reversed_by_entry_id"] == rev["id"]
    # Jurnal yang sudah dibalik tidak bisa disiapkan lagi.
    r = await _siapkan(klien, siap["h_mgr"], "journal_reverse", {"entry_id": je["id"], "date": now_iso()[:10],
                                                                 "reason": "salah catat setoran"})
    assert r.status_code == 409 and "sudah dibalik" in r.json()["detail"], r.text


# ── izin kartu jurnal `ai_finance.post` (02 §3.2 butir 4) ────────────────────────────────────────────────────────────
async def test_AGT5_izin_post(klien, db, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, siap):
    from services.ai_cards import MSG_IZIN_C_POST
    r = await _siapkan(klien, siap["h_fin"], "journal_manual", _jurnal(10_000, 10_000))
    assert r.status_code == 403 and r.json()["detail"] == MSG_IZIN_C_POST, r.text
    rid = await peran_tanpa_acuan({"ai": ["view"], "ai_finance": ["view", "post"], "accounting": ["view", "create"]},
                                  label="AGT5b post saja")
    u = await akun(rid, entitas=(KSC,))
    await _sakelar(klien, siap["h_adm"], u["id"], enabled=True, classes=["B", "C"])
    r = await _siapkan(klien, await sesi(u), "journal_manual", _jurnal(10_000, 10_000))
    assert r.status_code == 200, r.text
    mk = await akun(await peran_manajer_kosong(), entitas=(KSC,))
    r = await _siapkan(klien, await sesi(mk), "journal_manual", _jurnal(10_000, 10_000))
    assert r.status_code == 403, r.text


# ── U3 (antrean) — Pusat Persetujuan: baris "Tindakan asisten menunggu orang kedua" ─────────────────────────────────
async def test_AGT5_U3_antrean_pusat_persetujuan(klien, db, siap):
    from services import approval_backlog_service as abl
    baris = next(q for q in abl.QUEUES if q[0] == "ai_card_second")
    assert baris[1:] == ("Tindakan asisten menunggu orang kedua", "tanya-kn", "ai_action_proposals",
                         {"status": "awaiting_second"})
    awal = (await abl.backlog(KSC))["all_items"]
    n0 = next(r["count"] for r in awal if r["key"] == "ai_card_second")
    await _atur(klien, siap["h_adm"], "kontrol.asisten_uang_keluar.min_orang", "2")
    try:
        r = await _siapkan(klien, siap["h_fin"], "cash_manual", {})
        assert r.status_code == 400   # isian wajib
        rek = f"rek_agt5b_{uuid.uuid4().hex[:6]}"
        await db.bank_accounts.insert_one({"id": rek, "name": "Kas AGT5b", "entity_id": KSC, "account_type": "bank",
                                           "cash_type": "kas_besar", "is_active": True, "opening_balance": 1_000_000})
        r = await _siapkan(klien, siap["h_fin"], "cash_manual", {"account_id": rek, "amount": 75_000,
                                                                 "category": "operasional", "direction": "out"})
        assert r.status_code == 200, r.text
        k = r.json()["card"]
        r = await _setujui(klien, siap["h_fin"], k["id"], "75000")
        assert r.status_code == 200 and r.json()["status"] == "awaiting_second", r.text
    finally:
        await _atur(klien, siap["h_adm"], "kontrol.asisten_uang_keluar.min_orang", "1")
    bl = await abl.backlog(KSC, with_oldest=True, oldest_limit=50)
    row = next(r for r in bl["all_items"] if r["key"] == "ai_card_second")
    assert row["count"] == n0 + 1 and row["view"] == "tanya-kn"
    assert row["preset"] == {"tab": "actions", "box": "others"}
    tua = [o for o in bl["oldest"] if o["key"] == "ai_card_second"]
    assert any(o["id"] == k["id"] for o in tua) and all(o.get("preset") for o in tua)
    r = await klien.get("/api/approvals/backlog", headers=siap["h_mgr"])
    assert r.status_code == 200, r.text
    assert next(x for x in r.json()["all_items"] if x["key"] == "ai_card_second")["count"] >= 1


# ── U14 (b) — larangan diperiksa untuk SEMUA panggilan tulis SelfApi (tanpa golongan, golongan A/B) ──────────────────
async def test_AGT5_U14b_larangan_semua_tulisan(aplikasi, siap):
    from tests_mem.test_AGT5_kartu_uang_keluar import CONTOH_LARANGAN
    from services.ai_card_rules import FORBIDDEN
    from services.ai_self_api import SelfApi, SelfApiError
    dipanggil = []

    async def pengintai(scope, receive, send):
        if scope.get("type") == "http":
            dipanggil.append(scope["path"])
        await aplikasi(scope, receive, send)
    alasan = {c: why for c, _p, _m, why in FORBIDDEN}
    for kelas in ("", "A", "B"):
        api = SelfApi(pengintai, token=siap["h_mgr"]["Authorization"].split(" ", 1)[1], entity_header=KSC,
                      read_only=False, card_id="aiact_x", card_class=kelas)
        try:
            for code, metode, jalur in CONTOH_LARANGAN:
                with pytest.raises(SelfApiError) as e:
                    await api.call(metode, jalur, json={})
                assert (e.value.status, e.value.message) == (403, alasan[code]), (kelas, code, e.value.message)
        finally:
            await api.aclose()
    assert dipanggil == []
    # Mode baca-saja tetap: GET ke `/api/ai/…` ditolak larangan L11 hanya di mode tulis; baca-saja = aturan jalur lama.
    api = SelfApi(pengintai, token=siap["h_mgr"]["Authorization"].split(" ", 1)[1], entity_header=KSC)
    try:
        with pytest.raises(SelfApiError) as e:
            await api.call("POST", "/api/users", json={})
        assert e.value.status == 403 and "hanya boleh membaca" in e.value.message
    finally:
        await api.aclose()


async def test_AGT5_U15b_registry_jurnal():
    from services import ai_cards
    assert {"journal_manual", "journal_reverse"} <= set(ai_cards.REGISTRY)
    assert ai_cards.REGISTRY["journal_manual"].door == ("accounting", "create")
    assert ai_cards.REGISTRY["journal_reverse"].door == ("accounting", "void")
    assert {a.card_perm for a in ai_cards.REGISTRY.values() if a.cls == "C"} == {"pay", "post"}
