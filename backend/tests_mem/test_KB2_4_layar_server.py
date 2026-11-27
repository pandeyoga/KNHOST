"""KB-2 Tugas 4 (C6) — bagian server untuk layar Kas & Bank › Transaksi Kas dan antrean persetujuan.

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-2-kas-manual-design.md` §5.2 (Antrean & notifikasi), §5.3
(layar).
Butir: antrean Persetujuan Menunggu "Kas keluar manual menunggu" (umur tunggu, preset layar, jenis Aturan Persetujuan
satu jenjang), Aturan Persetujuan ditegakkan di pintu Setujui/Tolak (`guard_door`), batas PT efektif untuk catatan form
("Di atas Rp …"), kalimat tolak-sendiri untuk tombol Tolak, notifikasi membawa dokumen pengajuan, Jejak Dokumen mengenal
pengajuan (kas yang terbit = turunannya), dataset Pusat Export daftar pengajuan.
"""
from __future__ import annotations

import pytest

from test_KB2_2_pengajuan import _ajukan, _atur, _pt, URL_P

pytestmark = pytest.mark.anyio

URL_BATAS = f"{URL_P}/batas"
PESAN_TOLAK_SENDIRI = "Pengajuan ini Anda ajukan sendiri, jadi tidak bisa Anda tolak. Pakai Batal bila tidak jadi."


@pytest.fixture(scope="module", autouse=True)
def _peran_segar(klien):
    """Peran uji disimpan per modul di `_PERAN` (KB2_2) — basi bila modul lain sudah memakainya di DB sebelumnya.
    Dikosongkan sebelum DAN sesudah modul ini (tiap modul mulai dari database kosong), supaya modul berikutnya di proses
    yang sama — termasuk KB2_2 sendiri — tidak membawa id peran dari database modul ini."""
    import test_KB2_2_pengajuan as dua
    dua._PERAN.clear()
    yield
    dua._PERAN.clear()


# ── U1 — antrean Persetujuan Menunggu menghitung pengajuan menunggu; jenis Aturan Persetujuan satu jenjang ────────────
async def test_KB2_4_U1_antrean_dan_jenis_persetujuan(klien, db, akun, sesi, peran_tanpa_acuan):
    import approval_kinds
    from services import approval_backlog_service as abl
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    eid = pt["id"]
    a = await _ajukan(klien, pt, 3_000_000, kunci="kb24-u1a", description="Sewa tenda acara")
    b = await _ajukan(klien, pt, 2_000_000, kunci="kb24-u1b")
    out = await abl.backlog(eid, with_oldest=True, oldest_limit=50)
    per = {r["key"]: r for r in out["all_items"]}
    q = per["cash_out_request"]
    assert (q["count"], q["view"], q["label"]) == (2, "cash-management", "Kas keluar manual menunggu"), q
    # Pusat Persetujuan membuka Transaksi Kas di bagian "Menunggu persetujuan".
    assert q["preset"] == {"status": "menunggu_persetujuan"}
    tua = {r["id"]: r for r in out["oldest"] if r["key"] == "cash_out_request"}
    assert tua[a["id"]]["number"] == a["number"] and tua[a["id"]]["title"] == "Sewa tenda acara"
    assert tua[a["id"]]["entity_id"] == eid
    k = approval_kinds.APPROVAL_KINDS["cash_out_request"]
    assert (k["queue_key"], k["permissions"], k["amount_field"], k["max_levels"], k["group"]) == \
        ("cash_out_request", ("cash.approve",), "amount", 1, "Keuangan")
    # Sesudah diputus: tidak menunggu lagi.
    assert (await klien.post(f"{URL_P}/{a['id']}/approve", headers=pt["o"]["setuju"]["h"])).status_code == 200
    r = await klien.post(f"{URL_P}/{b['id']}/reject", headers=pt["o"]["setuju"]["h"], json={"alasan": "uji tolak KB24"})
    assert r.status_code == 200, r.text
    per = {r["key"]: r for r in (await abl.backlog(eid))["all_items"]}
    assert per["cash_out_request"]["count"] == 0


# ── U2 — Aturan Persetujuan berlaku di pintu Setujui & Tolak (bawaan: semua pemegang cash.approve) ───────────────────
async def test_KB2_4_U2_aturan_persetujuan_di_pintu(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 4_000_000, kunci="kb24-u2")
    await db.approval_policies.insert_one({
        "id": "apl_kb24_cor", "doc_kind": "cash_out_request", "entity_id": pt["id"], "level": 1, "label": "Persetujuan",
        "min_amount": 0, "max_amount": None, "roles": ["admin"], "any_holder": False, "sort": 1, "active": True,
        "source": "uji"})
    try:
        h = pt["o"]["setuju"]["h"]
        r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=h)
        assert r.status_code == 403 and "Peran Anda belum tercantum di Aturan Persetujuan" in r.json()["detail"], r.text
        r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=h, json={"alasan": "uji aturan KB24"})
        assert r.status_code == 403 and "Aturan Persetujuan" in r.json()["detail"], r.text
        doc = await db.cash_out_requests.find_one({"id": p["id"]}, {"_id": 0})
        assert doc["status"] == "menunggu_persetujuan" and not doc.get("cash_id")
        assert await db.cash_transactions.count_documents({"ref_type": "manual", "ref_id": p["id"]}) == 0
    finally:
        await db.approval_policies.delete_one({"id": "apl_kb24_cor"})
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200 and r.json()["status"] == "disetujui", r.text


# ── U3 — batas PT efektif untuk catatan form (pemegang cash.view; PT dalam penugasan) ────────────────────────────────
async def test_KB2_4_U3_batas_pt_efektif(klien, db, akun, sesi, peran_tanpa_acuan):
    pt, lain = await _pt(akun, sesi, peran_tanpa_acuan), await _pt(akun, sesi, peran_tanpa_acuan)
    h = pt["o"]["aju2"]["h"]
    r = await klien.get(URL_BATAS, headers=h, params={"entity_id": pt["id"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"entity_id": pt["id"], "min_orang": "1", "batas_nominal": 1_000_000, "semua": False}
    await _atur("kontrol.kas_keluar_manual.batas_nominal", 5_000_000, pt["id"])
    r = await klien.get(URL_BATAS, headers=h, params={"entity_id": pt["id"]})
    assert (r.json()["batas_nominal"], r.json()["semua"]) == (5_000_000, False)
    await _atur("kontrol.kas_keluar_manual.min_orang", "2", pt["id"])
    r = await klien.get(URL_BATAS, headers=h)            # tanpa entity_id = PT aktif di kepala aplikasi
    assert r.json() == {"entity_id": pt["id"], "min_orang": "2", "batas_nominal": 5_000_000, "semua": True}
    # PT lain tidak ikut berubah
    r = await klien.get(URL_BATAS, headers=lain["o"]["aju2"]["h"], params={"entity_id": lain["id"]})
    assert r.json()["batas_nominal"] == 1_000_000 and r.json()["min_orang"] == "1"
    # PT di luar penugasan → 403; tanpa izin kas → 403
    r = await klien.get(URL_BATAS, headers=h, params={"entity_id": lain["id"]})
    assert r.status_code == 403, r.text
    tanpa = await sesi(await akun(await peran_tanpa_acuan({"customer": ["view"]}, label="KB24 Tanpa Kas"),
                                  entitas=(pt["id"],)), entitas=pt["id"])
    r = await klien.get(URL_BATAS, headers=tanpa, params={"entity_id": pt["id"]})
    assert r.status_code == 403 and r.headers.get("X-Permission-Denied") == "cash.view", r.text


# ── U4 — penilaian kontrol baris menunggu membawa kalimat tolak-sendiri (tombol Tolak nonaktif dengan alasan) ────────
async def test_KB2_4_U4_kontrol_membawa_kalimat_tolak_sendiri(klien, db, akun, sesi, peran_tanpa_acuan):
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 2_500_000, kunci="kb24-u4")
    sendiri = {x["id"]: x for x in (await klien.get(URL_P, headers=pt["o"]["aju"]["h"])).json()["items"]}[p["id"]]
    assert sendiri["kontrol"]["sendiri"] is True and sendiri["kontrol"]["ditolak"] is True
    assert sendiri["kontrol"]["tolak_pesan"] == PESAN_TOLAK_SENDIRI
    rekan = {x["id"]: x for x in (await klien.get(URL_P, headers=pt["o"]["setuju"]["h"])).json()["items"]}[p["id"]]
    assert rekan["kontrol"]["sendiri"] is False and rekan["kontrol"]["tolak_pesan"] == ""
    rinci = (await klien.get(f"{URL_P}/{p['id']}", headers=pt["o"]["aju"]["h"])).json()
    assert rinci["kontrol"]["tolak_pesan"] == PESAN_TOLAK_SENDIRI


# ── U5 — notifikasi diajukan/diputus membawa dokumen pengajuan (klik membuka pengajuannya) ───────────────────────────
async def test_KB2_4_U5_notifikasi_membawa_dokumen(klien, db, akun, sesi, peran_tanpa_acuan):
    from services.notification_doc_ref import attach_doc_refs
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 3_300_000, kunci="kb24-u5")
    r = await klien.post(f"{URL_P}/{p['id']}/reject", headers=pt["o"]["setuju"]["h"],
                         json={"alasan": "bukan biaya kantor"})
    assert r.status_code == 200, r.text
    rows = await db.notifications.find({"ref": {"$regex": f"^{p['id']}"}}, {"_id": 0}).to_list(20)
    assert {n["type"] for n in rows} == {"kas_keluar_diajukan", "kas_keluar_diputus"}, rows
    harap = {"ref_type": "cash_out_request", "ref_id": p["id"], "number": p["number"],
             "label": f"Pengajuan kas keluar {p['number']}"}
    for n in await attach_doc_refs([dict(x) for x in rows]):
        assert n["doc"] == harap, n
    # Lewat rute: pengaju melihat notifikasi putusan dengan dokumennya.
    r = await klien.get("/api/notifications", headers=pt["o"]["aju"]["h"])
    assert r.status_code == 200, r.text
    putus = [n for n in r.json() if n["type"] == "kas_keluar_diputus" and n["ref"].startswith(p["id"])]
    assert putus and putus[0]["doc"] == harap, r.json()


# ── U6 — Jejak Dokumen: pengajuan → kas yang terbit (turunan); dari kas → pengajuannya ────────────────────────────────
async def test_KB2_4_U6_jejak_dokumen_pengajuan(klien, db, akun, sesi, peran_tanpa_acuan):
    from services import doc_refs_service as refs
    meta = refs.DOC_TYPES["cash_out_request"]
    assert (meta["collection"], meta["view"], meta["focus_type"], meta["perm"], meta["label"]) == \
        ("cash_out_requests", "cash-management", "cash_out_request", ("cash", "view"), "Pengajuan kas keluar")
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    p = await _ajukan(klien, pt, 1_750_000, kunci="kb24-u6")
    r = await klien.post(f"{URL_P}/{p['id']}/approve", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200, r.text
    kas = r.json()["kas"]
    jejak = await refs.trace("cash_out_request", p["id"])
    assert jejak["anchor"]["number"] == p["number"] and jejak["anchor"]["amount"] == 1_750_000
    assert {n["doc_id"] for n in jejak["nodes"] if n["doc_type"] == "cash_transaction"} == {kas["id"]}, jejak["nodes"]
    jejak_kas = await refs.trace("cash_transaction", kas["id"])
    assert any(n["doc_type"] == "cash_out_request" and n["doc_id"] == p["id"] for n in jejak_kas["nodes"]), \
        jejak_kas["nodes"]


# ── U7 — dataset Pusat Export daftar pengajuan (tombol baku Unduh) ────────────────────────────────────────────────────
async def test_KB2_4_U7_dataset_export_pengajuan(db):
    from services import export_registry
    ds = {d["id"]: d for d in export_registry.DATASETS}["cash_out_requests"]
    assert (ds["collection"], ds["perm"]) == ("cash_out_requests", ("cash", "view"))
    # = `cash_out_request_service.daftar` `q` (nomor / keterangan / kategori / nama pengaju)
    assert ds["search_fields"] == ["number", "description", "category", "pengaju.name"]
    kolom = {c["path"] for c in ds["columns"]}
    assert {"number", "txn_date", "account_name", "category", "amount", "status", "pengaju.name"} <= kolom
