"""KB-2 Tugas 3 (C6) — kartu Asisten `cash_manual` dan pemberitahuan pengajuan kas keluar manual.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` §5.2 (Antrean & notifikasi, Kartu Asisten),
§7.8 butir 7. Pengajuan baru → SATU pemberitahuan per pemegang `cash.approve` di PT itu (bukan pengaju, bukan PT lain,
tanpa siaran peran); diputus (setujui/tolak/batal oleh orang lain) → pengaju. Pemberitahuan yang gagal tidak pernah
membatalkan atau menggagalkan tindakan uangnya. Kartu di atas batas → "Diajukan — menunggu persetujuan kas keluar {nomor}".
"""
from __future__ import annotations

import pytest

from test_KB2_2_pengajuan import _ajukan, _kirim, _pt, URL_P

pytestmark = pytest.mark.anyio

DIAJUKAN, DIPUTUS = "kas_keluar_diajukan", "kas_keluar_diputus"
TOOL = "/api/ai/tools/prepare_action"
_PERAN_KARTU: dict = {}
IZIN_KARTU = {"ai": ["view"], "ai_finance": ["view", "pay"], "cash": ["view", "create"]}


@pytest.fixture(scope="module", autouse=True)
def _peran_segar(klien):
    """Peran uji disimpan per modul di `_PERAN` (KB2_2) — basi bila modul lain sudah memakainya di DB sebelumnya.
    Dikosongkan sebelum DAN sesudah modul ini (tiap modul mulai dari database kosong)."""
    import test_KB2_2_pengajuan as dua
    dua._PERAN.clear()
    _PERAN_KARTU.clear()
    yield
    dua._PERAN.clear()
    _PERAN_KARTU.clear()


async def _notif(db, jenis: str, rid: str) -> list:
    return await db.notifications.find({"type": jenis, "ref": {"$regex": f"^{rid}"}}, {"_id": 0}).to_list(50)


def _penerima(rows: list) -> list:
    return sorted(r["recipient_user"] for r in rows)


async def test_KB2_3_N1_pengajuan_memberi_tahu_pemegang_setujui_di_pt_itu(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    lain = await _pt(akun, sesi, peran_tanpa_acuan)      # PT lain: orang berizin di sana TIDAK diberi tahu
    req = await _ajukan(klien, pt, 3_000_000, kunci="kb23-n1")
    rows = await _notif(db, DIAJUKAN, req["id"])
    harap = sorted(pt["o"][k]["u"]["id"] for k in ("setuju", "setuju2"))
    assert _penerima(rows) == harap, rows               # bukan pengaju (aju punya cash.approve), bukan aju2/hapus/lihat
    for n in rows:
        assert n["recipient_role"] == "" and n["entity_id"] == pt["id"] and n["read"] is False
        assert req["number"] in n["title"] and "3.000.000" in n["body"] and pt["o"]["aju"]["u"]["name"] in n["body"]
        assert n["ref"].startswith(req["id"])
    assert not set(_penerima(rows)) & {lain["o"][k]["u"]["id"] for k in lain["o"]}
    # kiriman ulang berkunci sama = pengajuan yang sama → tidak ada pemberitahuan baru
    r = await _kirim(klien, pt, 3_000_000, kunci="kb23-n1")
    assert r.status_code == 202 and r.json()["request"]["id"] == req["id"]
    assert len(await _notif(db, DIAJUKAN, req["id"])) == 2


async def test_KB2_3_N2_putusan_memberi_tahu_pengaju(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    aju = pt["o"]["aju"]["u"]["id"]
    # setujui
    a = await _ajukan(klien, pt, 2_000_000, kunci="kb23-n2a")
    r = await klien.post(f"{URL_P}/{a['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200, r.text
    rows = await _notif(db, DIPUTUS, a["id"])
    assert _penerima(rows) == [aju]
    n = rows[0]
    assert n["recipient_role"] == "" and n["entity_id"] == pt["id"]
    assert "disetujui" in n["title"].lower() and a["number"] in n["title"]
    assert pt["o"]["setuju"]["u"]["name"] in n["body"] and r.json()["kas"]["number"] in n["body"]
    # tolak: alasan ikut
    b = await _ajukan(klien, pt, 2_500_000, kunci="kb23-n2b")
    r = await klien.post(f"{URL_P}/{b['id']}/reject", headers=pt["o"]["setuju"]["h"], json={"alasan": "bukan biaya kantor"})
    assert r.status_code == 200, r.text
    n = (await _notif(db, DIPUTUS, b["id"]))[0]
    assert n["recipient_user"] == aju and "ditolak" in n["title"].lower() and "bukan biaya kantor" in n["body"]
    # batal oleh pengaju sendiri: tidak memberi tahu dirinya; batal oleh pemegang cash.delete: memberi tahu pengaju
    c = await _ajukan(klien, pt, 2_200_000, kunci="kb23-n2c")
    assert (await klien.post(f"{URL_P}/{c['id']}/cancel", headers=pt["o"]["aju"]["h"], json={})).status_code == 200
    assert await _notif(db, DIPUTUS, c["id"]) == []
    d = await _ajukan(klien, pt, 2_300_000, kunci="kb23-n2d")
    assert (await klien.post(f"{URL_P}/{d['id']}/cancel", headers=pt["o"]["hapus"]["h"],
                             json={"alasan": "salah nominal"})).status_code == 200
    n = (await _notif(db, DIPUTUS, d["id"]))[0]
    assert n["recipient_user"] == aju and "dibatalkan" in n["title"].lower() and "salah nominal" in n["body"]


async def test_KB2_3_N3_notifikasi_gagal_tidak_mengganggu_uang(klien, db, akun, sesi, peran_tanpa_acuan, monkeypatch):
    from services import notification_service as ns

    async def _rusak(*a, **k):
        raise RuntimeError("notifikasi rusak")
    monkeypatch.setattr(ns, "create_addressed", _rusak)
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    a = await _ajukan(klien, pt, 3_000_000, kunci="kb23-n3")        # tetap 202 + pengajuan tersimpan
    assert await db.cash_out_requests.count_documents({"id": a["id"], "status": "menunggu_persetujuan"}) == 1
    r = await klien.post(f"{URL_P}/{a['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200 and r.json()["status"] == "disetujui" and r.json()["kas"]["number"], r.text
    b = await _ajukan(klien, pt, 3_100_000, kunci="kb23-n3b")
    r = await klien.post(f"{URL_P}/{b['id']}/reject", headers=pt["o"]["setuju"]["h"], json={"alasan": "tidak perlu"})
    assert r.status_code == 200 and r.json()["status"] == "ditolak"


# ═══ Kartu Asisten ═══════════════════════════════════════════════════════════════════════════════════════════════════
async def _siap_kartu(klien, akun, sesi, peran_tanpa_acuan, kepala_admin, pt) -> dict:
    if "kartu" not in _PERAN_KARTU:
        _PERAN_KARTU["kartu"] = await peran_tanpa_acuan(IZIN_KARTU, label="KB23 kartu")
    rid = _PERAN_KARTU["kartu"]
    u = await akun(rid, entitas=(pt["id"],))
    r = await klien.patch(f"/api/users/{u['id']}", headers=kepala_admin,
                          json={"data": {"ai_finance": {"enabled": True, "classes": ["B", "C"]}}})
    assert r.status_code == 200, r.text
    for key, val, tipe, sid in (("ai.tindakan_uang_keluar", True, "entity", pt["id"]),
                                ("ai.enabled", True, "global", "")):
        r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
            "key": key, "value": val, "scope_type": tipe, "scope_id": sid, "reason": "uji KB23"}]})
        assert r.status_code == 200, r.text
    return {"u": u, "h": await sesi(u, entitas=pt["id"])}


async def _kartu(klien, h, rek: str, nominal: int) -> dict:
    r = await klien.post(TOOL, headers=h, json={"action": "cash_manual", "user_request": "uji KB23", "session_id": "",
                                                "args": {"account_id": rek, "direction": "out", "amount": nominal,
                                                         "category": "operasional", "description": "biaya uji"}})
    assert r.status_code == 200, r.text
    return r.json()["card"]


async def _konfirmasi(klien, h, kartu: dict, nominal: int):
    return await klien.post(f"/api/ai/actions/{kartu['id']}/confirm", headers=h,
                            json={"reason": "uji kartu kas keluar", "retype": str(nominal)})


async def test_KB2_3_K1_kartu_di_atas_batas_menjadi_pengajuan(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    pg = await _siap_kartu(klien, akun, sesi, peran_tanpa_acuan, kepala_admin, pt)
    k = await _kartu(klien, pg["h"], pt["rek"]["BCA"], 3_000_000)
    # Perbaikan akhir (Minor 4) — rencana kartu mengatakan lebih dulu bahwa kas ini menjadi pengajuan
    rows = k["plan"]["rows"]
    assert (rows[0]["label"], rows[0]["after"]) == (
        "Persetujuan", "Di atas Rp 1.000.000 — akan diajukan untuk disetujui orang kedua."), rows
    assert rows[1]["label"].startswith("Saldo ") and rows[1]["label"].endswith(" (sesudah disetujui)"), rows
    jurnal0 = await db.journal_entries.count_documents({"entity_id": pt["id"]})   # jurnal saldo awal rekening
    r = await _konfirmasi(klien, pg["h"], k, 3_000_000)
    assert r.status_code == 200, r.text
    kartu = r.json()
    assert kartu["status"] == "confirmed", kartu          # bukan galat
    req = await db.cash_out_requests.find_one({"entity_id": pt["id"], "ai_card_id": k["id"]}, {"_id": 0})
    assert req and req["status"] == "menunggu_persetujuan" and req["pengaju"]["id"] == pg["u"]["id"]
    res = kartu["result"]
    assert res["status_code"] == 202 and res["gl_status"] is None
    assert res["message"] == f"Diajukan — menunggu persetujuan kas keluar {req['number']}"
    assert res["document"]["type"] == "cash_out_request" and res["document"]["id"] == req["id"]
    assert res["document"]["number"] == req["number"]
    assert res["document"]["link"] == {"view": "cash-management", "nav_id": "cash-bank", "tab": "",   # Minor 9
                                       "focus_type": "cash_out_request", "focus_id": req["id"], "number": req["number"]}
    assert await db.cash_transactions.count_documents({"entity_id": pt["id"], "ai_card_id": k["id"]}) == 0
    assert await db.journal_entries.count_documents({"entity_id": pt["id"]}) == jurnal0
    # pemegang cash.approve PT itu (aju, setuju, setuju2); pengaju kartu (tanpa izin itu) tidak termasuk
    assert _penerima(await _notif(db, DIAJUKAN, req["id"])) == sorted(
        pt["o"][x]["u"]["id"] for x in ("aju", "setuju", "setuju2"))


async def test_KB2_3_K2_kartu_di_bawah_batas_seperti_dulu(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    pg = await _siap_kartu(klien, akun, sesi, peran_tanpa_acuan, kepala_admin, pt)
    k = await _kartu(klien, pg["h"], pt["rek"]["BCA"], 250_000)
    assert [x["label"] for x in k["plan"]["rows"] if x["label"] == "Persetujuan"] == []   # langsung tercatat
    assert not k["plan"]["rows"][0]["label"].endswith("(sesudah disetujui)")
    r = await _konfirmasi(klien, pg["h"], k, 250_000)
    assert r.status_code == 200 and r.json()["status"] == "confirmed", r.text
    res = r.json()["result"]
    assert res["status_code"] == 200 and res["document"]["type"] == "cash_transaction" and res["gl_status"] == "posted"
    assert not res["message"]
    kas = await db.cash_transactions.find({"entity_id": pt["id"], "ai_card_id": k["id"]}, {"_id": 0}).to_list(5)
    assert len(kas) == 1 and kas[0]["amount"] == 250_000
    assert await db.cash_out_requests.count_documents({"entity_id": pt["id"]}) == 0
