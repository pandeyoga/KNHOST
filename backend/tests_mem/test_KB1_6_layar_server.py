"""KB-1 Tugas 6 — bagian server untuk layar Kas & Bank: kolom "Akun buku besar" di daftar rekening, label perubahan
rekening, antrean persetujuan Pindah Dana & pindah saldo, Jejak Dokumen Pindah Dana, pratinjau refund ber-rekening.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.4 (layar), §5.2/§5.3 (perilaku).
Butir bawaan tinjauan sebelumnya (dispatch Tugas 6): label `gl_account_code` di layar persetujuan rekening, dua pintu
keputusan baru terdaftar di antrean Persetujuan Menunggu, pratinjau refund mengirim `refund_account_id`, jenis dokumen
`fund_transfer` di Jejak Dokumen.
"""
from __future__ import annotations

import itertools
from datetime import date, timedelta

import pytest

from pembantu import AKTOR_UJI, pt_uji

pytestmark = pytest.mark.anyio

PEMBUAT = {"id": "usr_kb6_buat", "name": "Rina Pembuat KB6", "role": "finance", "email": "rina.kb6@uji.id"}
PENYETUJU = {"id": "usr_kb6_setuju", "name": "Dodi Penyetuju KB6", "role": "finance", "email": "dodi.kb6@uji.id"}
_urut = itertools.count(1)


def _hari(geser: int = 0) -> str:
    from services.book_date import tanggal_buku
    return (date.fromisoformat(tanggal_buku()) + timedelta(days=geser)).isoformat()


async def _rekening(eid: str, nama: str, jenis_akun: str = "bank", jenis_kas: str = "", awal: float = 0.0) -> str:
    from schemas_finance import BankAccountCreate
    from services import bank_service
    acc = await bank_service.create_account(
        BankAccountCreate(name=nama, account_type=jenis_akun, cash_type=jenis_kas, entity_id=eid,
                          opening_balance=awal), AKTOR_UJI)
    return acc["id"]


async def _pt(aktif: bool) -> dict:
    from services import cash_account_mode as mode
    from services.entity_lifecycle_service import invalidate_status_cache
    kode = f"KB6{'A' if aktif else 'L'}{next(_urut)}"
    eid = await pt_uji(kode)
    if aktif:
        await mode.nyalakan(eid, "Uji KB6")
    rek = {"BCA": await _rekening(eid, f"BCA {kode}", awal=1_000_000),
           "MDR": await _rekening(eid, f"Mandiri {kode}")}
    invalidate_status_cache()
    return {"id": eid, "kode": kode, "rek": rek}


async def _atur(key: str, nilai, eid: str) -> None:
    from services import config_resolver as resolver
    await resolver.set_value(key, nilai, scope_type="entity", scope_id=eid, reason="uji KB6 kontrol", actor="uji")


# ── U1 — daftar rekening: akun buku besar (kode + nama) + penanda PT belum memakai akun per rekening ──────────────────
async def test_KB1_6_U1_daftar_rekening_akun_buku_besar_dan_penanda_pt(db):
    from services import bank_service
    aktif, lama = await _pt(True), await _pt(False)
    baris = {a["id"]: a for a in await bank_service.list_accounts(entity_id=aktif["id"])}
    bca = baris[aktif["rek"]["BCA"]]
    # PT aktif: sub-akun dibuat saat rekening lahir (1-1100-NN), nama akun = nama rekening.
    assert bca["gl_account_code"].startswith("1-1100-"), bca
    assert bca["gl_account_name"] == f"BCA {aktif['kode']}"
    assert bca["akun_per_rekening_aktif"] is True and bca["akun_per_rekening_sejak"]
    baris = {a["id"]: a for a in await bank_service.list_accounts(entity_id=lama["id"])}
    bca = baris[lama["rek"]["BCA"]]
    assert not bca.get("gl_account_code") and bca["gl_account_name"] == ""
    assert bca["akun_per_rekening_aktif"] is False and bca["akun_per_rekening_sejak"] == ""


# ── U2 — layar persetujuan perubahan rekening memberi label "Akun buku besar" pada `gl_account_code` ───────────────────
async def test_KB1_6_U2_label_perubahan_akun_buku_besar(db):
    from services import bank_account_change_service as bac
    await db.bank_account_changes.insert_one({
        "id": "bac_kb6_label", "entity_id": "ent_ksc", "status": "ditolak", "action": "buat",
        "changes": [{"field": "gl_account_code", "from": "", "to": "1-1100-07"}], "created_at": "2026-11-27T01:00:00"})
    out = await bac.daftar({"id": "bac_kb6_label"}, "", 1, 10, AKTOR_UJI)
    assert out["items"][0]["label_changes"] == [
        {"field": "gl_account_code", "from": "", "to": "1-1100-07", "label": "Akun buku besar"}]


# ── U3 — antrean Persetujuan Menunggu menghitung Pindah Dana menunggu & usulan pindah saldo menunggu ─────────────────
async def test_KB1_6_U3_antrean_pindah_dana_dan_pindah_saldo(db):
    from services import approval_backlog_service as abl
    from services import cash_account_cutover_service as cut
    from services import fund_transfer_service as fts
    import approval_kinds
    pt = await _pt(False)
    eid = pt["id"]
    await _atur("kontrol.pindah_dana.min_orang", "2", eid)
    menunggu = await fts.buat({"entity_id": eid, "rekening_asal_id": pt["rek"]["BCA"],
                               "rekening_tujuan_id": pt["rek"]["MDR"], "nominal": 250_000}, PEMBUAT)
    assert menunggu["status"] == "menunggu_persetujuan"
    usulan = await cut.siapkan(eid, {}, PEMBUAT)
    assert usulan["status"] == "menunggu"
    out = await abl.backlog(eid, with_oldest=True, oldest_limit=50)
    per = {r["key"]: r for r in out["all_items"]}
    assert per["fund_transfer"]["count"] == 1 and per["fund_transfer"]["view"] == "fund-transfers"
    # Pindah Dana dibuka dengan saringan "Menunggu persetujuan".
    assert per["fund_transfer"]["preset"] == {"status": "menunggu_persetujuan"}
    assert per["pindah_saldo_kas"]["count"] == 1 and per["pindah_saldo_kas"]["view"] == "kas-per-rekening"
    tua = {r["key"]: r for r in out["oldest"] if r["id"] in (menunggu["id"], usulan["id"])}
    assert tua["fund_transfer"]["number"] == menunggu["number"]
    assert tua["fund_transfer"]["title"] == f"BCA {pt['kode']}"
    assert tua["pindah_saldo_kas"]["number"] == usulan["label"]
    # Jenis dokumen Aturan Persetujuan: izin pintu yang sama, satu jenjang (pintu diputus satu orang).
    k_pd, k_ps = approval_kinds.APPROVAL_KINDS["fund_transfer"], approval_kinds.APPROVAL_KINDS["pindah_saldo_kas"]
    assert (k_pd["queue_key"], k_pd["permissions"], k_pd["amount_field"], k_pd["max_levels"]) == \
        ("fund_transfer", ("cash.approve",), "nominal", 1)
    assert (k_ps["queue_key"], k_ps["permissions"], k_ps["max_levels"]) == \
        ("pindah_saldo_kas", ("accounting.manage",), 1)
    # Sesudah diputus: tidak menunggu lagi.
    await fts.setujui(menunggu["id"], PENYETUJU)
    await cut.tolak(usulan["id"], "uji tolak KB6", PENYETUJU)
    per = {r["key"]: r for r in (await abl.backlog(eid))["all_items"]}
    assert per["fund_transfer"]["count"] == 0 and per["pindah_saldo_kas"]["count"] == 0


# ── U4 — Aturan Persetujuan berlaku di kedua pintu (bawaan: semua pemegang izin) ─────────────────────────────────────
async def test_KB1_6_U4_aturan_persetujuan_berlaku_di_pintu(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(False)
    eid = pt["id"]
    await _atur("kontrol.pindah_dana.min_orang", "2", eid)
    setuju = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view", "approve"]}, label="KB6 Setujui Kas"),
                                   entitas=(eid,)), entitas=eid)
    from services import fund_transfer_service as fts
    doc = await fts.buat({"entity_id": eid, "rekening_asal_id": pt["rek"]["BCA"],
                          "rekening_tujuan_id": pt["rek"]["MDR"], "nominal": 100_000}, PEMBUAT)
    # Admin membatasi pemutus Pindah Dana PT ini ke Admin saja → peran lain ditolak dengan kalimat aturan.
    await db.approval_policies.insert_one({
        "id": "apl_kb6_pd", "doc_kind": "fund_transfer", "entity_id": eid, "level": 1, "label": "Persetujuan",
        "min_amount": 0, "max_amount": None, "roles": ["admin"], "any_holder": False, "sort": 1, "active": True,
        "source": "uji"})
    r = await klien.post(f"/api/fund-transfers/{doc['id']}/approve", headers=setuju)
    assert r.status_code == 403, r.text
    assert "Peran Anda belum tercantum di Aturan Persetujuan" in r.json()["detail"]
    assert (await db.fund_transfers.find_one({"id": doc["id"]}, {"_id": 0}))["status"] == "menunggu_persetujuan"
    await db.approval_policies.delete_one({"id": "apl_kb6_pd"})
    r = await klien.post(f"/api/fund-transfers/{doc['id']}/approve", headers=setuju)
    assert r.status_code == 200 and r.json()["status"] == "selesai", r.text


# ── U5 — daftar Pindah Dana membawa penilaian kontrol dua orang untuk baris yang menunggu (tombol Setujui jujur) ─────
async def test_KB1_6_U5_daftar_pindah_dana_membawa_kontrol(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(False)
    eid = pt["id"]
    await _atur("kontrol.pindah_dana.min_orang", "2", eid)
    buat_u = await akun(await peran_tanpa_acuan({"cash": ["view", "create", "approve"]}, label="KB6 Buat Kas"),
                        entitas=(eid,))
    buat = await sesi(buat_u, entitas=eid)
    lain = await sesi(await akun(await peran_tanpa_acuan({"cash": ["view", "approve"]}, label="KB6 Rekan Kas"),
                                 entitas=(eid,)), entitas=eid)
    r = await klien.post("/api/fund-transfers", headers=buat, json={
        "entity_id": eid, "rekening_asal_id": pt["rek"]["BCA"], "rekening_tujuan_id": pt["rek"]["MDR"],
        "nominal": 75_000, "tanggal_kirim": _hari()})
    assert r.status_code == 200 and r.json()["status"] == "menunggu_persetujuan", r.text
    tid = r.json()["id"]
    sendiri = {x["id"]: x for x in (await klien.get("/api/fund-transfers", headers=buat)).json()["items"]}[tid]
    assert sendiri["kontrol"]["ditolak"] is True and "harus diputuskan orang lain" in sendiri["kontrol"]["pesan"]
    rekan = {x["id"]: x for x in (await klien.get("/api/fund-transfers", headers=lain)).json()["items"]}[tid]
    assert rekan["kontrol"]["ditolak"] is False


# ── U6 — Jejak Dokumen mengenal Pindah Dana (kas dokumen tampil sebagai turunannya) ──────────────────────────────────
async def test_KB1_6_U6_jejak_dokumen_pindah_dana(db):
    from services import doc_refs_service as refs
    from services import fund_transfer_service as fts
    meta = refs.DOC_TYPES["fund_transfer"]
    assert (meta["collection"], meta["view"], meta["focus_type"], meta["perm"]) == \
        ("fund_transfers", "fund-transfers", "fund_transfer", ("cash", "view"))
    pt = await _pt(False)
    doc = await fts.buat({"entity_id": pt["id"], "rekening_asal_id": pt["rek"]["BCA"],
                          "rekening_tujuan_id": pt["rek"]["MDR"], "nominal": 40_000, "biaya": 2_500}, PEMBUAT)
    jejak = await refs.trace("fund_transfer", doc["id"])
    assert jejak["anchor"]["number"] == doc["number"] and jejak["anchor"]["amount"] == 40_000
    kas = {n["doc_id"] for n in jejak["nodes"] if n["doc_type"] == "cash_transaction"}
    assert kas == set(doc["kas_ids"].values()), jejak["nodes"]
    # Dari sisi kas: induknya Pindah Dana.
    jejak_kas = await refs.trace("cash_transaction", doc["kas_ids"]["kirim"])
    assert any(n["doc_type"] == "fund_transfer" and n["doc_id"] == doc["id"] for n in jejak_kas["nodes"])


# ── U7 — Posting Gagal pindah saldo menautkan layar Akun per rekening ────────────────────────────────────────────────
async def test_KB1_6_U7_tautan_posting_gagal_pindah_saldo(db):
    from services import posting_registry as reg
    assert reg.KINDS["pindah_saldo_kas"]["link"]["view"] == "kas-per-rekening"
    assert reg.KINDS["fund_transfer_cancel"]["link"]["view"] == "fund-transfers"


# ── U8 — pratinjau keputusan retur meneruskan rekening refund pilihan layar ──────────────────────────────────────────
async def test_KB1_6_U8_pratinjau_refund_meneruskan_rekening(klien, db, kepala_admin, monkeypatch):
    from services import return_service
    tangkap = {}

    async def palsu(return_id, outcome, item_decisions=None, nego_payout="", refund_account_code="",
                    refund_account_id=""):
        tangkap.update(outcome=outcome, refund_account_code=refund_account_code, refund_account_id=refund_account_id)
        return {"problem": "", "journal": []}

    monkeypatch.setattr(return_service, "preview_settlement", palsu)
    await db.sales_returns.insert_one({"id": "sr_kb6_pv", "number": "RJ-KB6", "entity_id": "ent_ksc",
                                       "status": "approved", "items": [], "created_at": "2026-11-27T01:00:00"})
    r = await klien.post("/api/sales-returns/sr_kb6_pv/settle-preview", headers={**kepala_admin, "X-Entity-Id": "ent_ksc"},
                         json={"outcome": "refund", "refund_account_code": "1-1100", "refund_account_id": "bank_kb6_x"})
    assert r.status_code == 200, r.text
    assert tangkap == {"outcome": "refund", "refund_account_code": "1-1100", "refund_account_id": "bank_kb6_x"}


# ── U9 — daftar usulan pindah saldo membawa penilaian kontrol dua orang (tombol Setujui jujur) ───────────────────────
async def test_KB1_6_U9_daftar_usulan_membawa_kontrol(db):
    from services import cash_account_cutover_service as cut
    pt = await _pt(False)
    usulan = await cut.siapkan(pt["id"], {}, PEMBUAT)
    sendiri = {x["id"]: x for x in (await cut.daftar({"entity_id": pt["id"]}, actor=PEMBUAT))["items"]}[usulan["id"]]
    assert sendiri["kontrol"]["ditolak"] is True, sendiri["kontrol"]
    assert sendiri["kontrol"]["pesan"].startswith("Pindah saldo kas ke akun per rekening harus diputuskan orang lain")
    rekan = {x["id"]: x for x in (await cut.daftar({"entity_id": pt["id"]}, actor=PENYETUJU))["items"]}[usulan["id"]]
    assert rekan["kontrol"]["ditolak"] is False
    # Tanpa aktor (pemanggil sistem) tidak ada penilaian.
    assert "kontrol" not in (await cut.daftar({"entity_id": pt["id"]}))["items"][0]
