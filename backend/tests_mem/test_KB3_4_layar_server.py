"""KB-3 Tugas 4b (C3) — bagian server untuk layar Kas & Bank › Opname Kas (tab tersembunyi `cash-counts`).

Rancangan: `docs/superpowers/specs/2026-11-28-kas-bank-3-kasir-dana-tetap-opname-design.md` §5.3, §5.4.
Butir: notifikasi opname (selisih menunggu → penyetuju; diputus → penghitung) membawa DOKUMEN opname (`doc`, pola KB-2
`notification_doc_ref`), Jejak Dokumen mengenal opname (kas penyesuaian = turunannya; dari kas → opnamenya; tautan ke
layar `cash-counts`), dan katalog akses membuka tab Opname Kas dengan izin `cash` (bukan seluruh modul).

Persiapan sama dengan `test_KB3_3_opname.py` (PT uji, rekening lewat ALUR layanan, opname & putusan lewat ALUR rute).
"""
from __future__ import annotations

import pytest

from test_KB3_3_opname import URL, _hitung, _pt, _putus

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="module", autouse=True)
def _peran_segar(klien):
    """Peran uji disimpan per modul di `_PERAN` (KB3_3) — basi bila modul lain sudah memakainya di database sebelumnya.
    Dikosongkan sebelum DAN sesudah modul ini (tiap modul mulai dari database kosong)."""
    import test_KB3_3_opname as tiga
    tiga._PERAN.clear()
    yield
    tiga._PERAN.clear()


# ── U1 — notifikasi opname menunggu & diputus membawa dokumen opnamenya ───────────────────────────────────────────────
async def test_KB3_4_U1_notifikasi_membawa_dokumen_opname(klien, db, akun, sesi, peran_tanpa_acuan):
    from services.notification_doc_ref import attach_doc_refs
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    o = await _hitung(klien, pt, 970_000)                     # kas kasir 1.000.000 → kurang 30.000, menunggu
    assert o["status"] == "menunggu_persetujuan", o
    await _putus(klien, pt, o["id"], "reject", alasan="hitung ulang besok pagi")
    rows = await db.notifications.find({"ref": {"$regex": f"^{o['id']}"}}, {"_id": 0}).to_list(20)
    assert {n["type"] for n in rows} == {"opname_kas_menunggu", "opname_kas_diputus"}, rows
    harap = {"ref_type": "cash_count", "ref_id": o["id"], "number": o["number"], "label": f"Opname kas {o['number']}"}
    for n in await attach_doc_refs([dict(x) for x in rows]):
        assert n["doc"] == harap, n
    # Lewat rute: penyetuju melihat "menunggu" dengan dokumennya; penghitung melihat putusannya dengan dokumennya.
    r = await klien.get("/api/notifications", headers=pt["o"]["setuju"]["h"])
    assert r.status_code == 200, r.text
    tunggu = [n for n in r.json() if n["type"] == "opname_kas_menunggu" and n["ref"].startswith(o["id"])]
    assert tunggu and tunggu[0]["doc"] == harap, r.json()
    r = await klien.get("/api/notifications", headers=pt["o"]["hitung"]["h"])
    assert r.status_code == 200, r.text
    putus = [n for n in r.json() if n["type"] == "opname_kas_diputus" and n["ref"].startswith(o["id"])]
    assert putus and putus[0]["doc"] == harap, r.json()
    # Opname yang tidak ada (dihapus / id lama) → notifikasi tetap tampil tanpa dokumen.
    hantu = await attach_doc_refs([{"type": "opname_kas_menunggu", "ref": "opk_tidak_ada#usr_x"}])
    assert "doc" not in hantu[0]


# ── U2 — Jejak Dokumen: opname → kas penyesuaian (turunan); dari kas → opnamenya ─────────────────────────────────────
async def test_KB3_4_U2_jejak_dokumen_opname(klien, db, akun, sesi, peran_tanpa_acuan, kepala_admin):
    from services import doc_refs_service as refs
    meta = refs.DOC_TYPES["cash_count"]
    isi = (meta["collection"], meta["view"], meta["focus_type"], meta["perm"], meta["label"], meta["needs_parent"])
    assert isi == ("cash_counts", "cash-counts", "cash_count", ("cash", "view"), "Opname kas", False)
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    o = await _hitung(klien, pt, 970_000)
    d = await _putus(klien, pt, o["id"], perlakuan="selisih_kas")
    kas = d["kas"]
    assert d["status"] == "disetujui" and kas and kas["direction"] == "out", d
    assert refs.link_of("cash_count", {"id": o["id"], "number": o["number"]}) == {
        "view": "cash-counts", "tab": "", "focus_type": "cash_count", "focus_id": o["id"], "number": o["number"]}
    jejak = await refs.trace("cash_count", o["id"])
    assert jejak["anchor"]["number"] == o["number"]
    assert {n["doc_id"] for n in jejak["nodes"] if n["doc_type"] == "cash_transaction"} == {kas["id"]}, jejak["nodes"]
    jejak_kas = await refs.trace("cash_transaction", kas["id"])
    assert any(n["doc_type"] == "cash_count" and n["doc_id"] == o["id"] for n in jejak_kas["nodes"]), jejak_kas["nodes"]
    # Lewat rute Jejak (`document.view`): simpul opname bertautan layar Opname Kas.
    r = await klien.get(f"/api/documents/trace/cash_count/{o['id']}",
                        headers={**kepala_admin, "X-Entity-Id": pt["id"]})
    assert r.status_code == 200, r.text
    simpul = next(n for n in r.json()["nodes"] if n["doc_type"] == "cash_count")
    assert (simpul["link"]["view"], simpul["link"]["focus_id"]) == ("cash-counts", o["id"]), simpul


# ── U4 — dataset Pusat Export daftar opname (tombol baku Unduh Excel/CSV) ────────────────────────────────────────────
async def test_KB3_4_U4_dataset_export_opname(db):
    from services import export_registry
    ds = {d["id"]: d for d in export_registry.DATASETS}["cash_counts"]
    assert (ds["collection"], ds["perm"]) == ("cash_counts", ("cash", "view"))
    # = `cash_count_service.daftar` `q` (nomor / rekening / penghitung / karyawan / catatan)
    assert ds["search_fields"] == ["number", "account_name", "penghitung.name", "karyawan_nama", "catatan"]
    kolom = {c["path"] for c in ds["columns"]}
    assert {"number", "dihitung_pada", "account_name", "saldo_buku", "jumlah_fisik", "selisih", "status",
            "perlakuan", "karyawan_nama", "penghitung.name", "account_id", "entity_id"} <= kolom


# ── U3 — katalog akses: tab Opname Kas dibuka izin `cash` (tab tersembunyi modul Kas, Bank & Kasus Keuangan) ─────────
async def test_KB3_4_U3_katalog_akses_tab_opname(klien, akun, sesi, peran_tanpa_acuan):
    from access_modules import MODULE_BY_ID, view_resources_index
    assert "cash-counts" in MODULE_BY_ID["finance_ops"]["nav"]
    assert view_resources_index()["cash-counts"] == ["cash"]
    pt = await _pt(akun, sesi, peran_tanpa_acuan)
    r = await klien.get(URL, headers=pt["o"]["lihat"]["h"], params={"entity_id": pt["id"]})
    assert r.status_code == 200, r.text
