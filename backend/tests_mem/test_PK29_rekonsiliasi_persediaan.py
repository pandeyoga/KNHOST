"""PK-29 (IV-05, IV-09, GL-13; K-06) — rekonsiliasi persediaan dinilai per PT dengan akun hasil pemetaan; true-up hanya
untuk saldo awal, per PT, dengan alasan. Spesifikasi `docs/blueprint/unit/PK-29.md`.

Persiapan bersama (fixture, disisipkan langsung): PT uji `pt_uji(...)` tersendiri per uji (aplikasi uji + seed membawa
selisih awal PT seed yang bukan dari unit ini, dan tiap uji true-up butuh keadaan "masa saldo awal" sendiri); roll
fixture `available`; jurnal lewat `pembantu.jurnal` (sumber `uji` = jurnal persediaan biasa, bukan saldo awal) atau
`gl_service.post_goods_receipt` (jurnal operasional penerimaan). Alur lewat API: rekonsiliasi, penjelas selisih, true-up,
pengaturan. U4 memakai tiruan kursor Motor (lihat `_KursorMotor`): `mongomock_motor` mengabaikan `to_list(n)` sehingga
batas 100.000 tidak bisa direproduksi dengan 150.000 dokumen tiruan (dan 150.000 dokumen butuh ±6 menit) — alur 150.000
roll asli = lapis A `tests/test_bp_PK29_rekonsiliasi_persediaan_mongo.py`.

Angka harapan dihitung tangan di komentar tiap uji (masukan → langkah → hasil).
"""
import importlib
import itertools
import re
import sys
import uuid
from pathlib import Path
from typing import Any, Dict

import pytest

from core_utils import now_iso
from pembantu import AKTOR_UJI, jurnal, pt_uji, tutup_periode
from services.book_date import periode_buku, tanggal_buku

KUNCI = "inventory.trueup_hanya_saldo_awal"
PERSEDIAAN, EKUITAS, AKUN_PETA = "1-1300", "3-2900", "1-1301"
ADMIN = "admin@kainnusantara.id"
ALASAN = "stok awal gudang utama"
PESAN_ALASAN = "Alasan true-up wajib diisi (minimal 5 huruf)."
PESAN_SEMUA_PT = "Pilih satu PT untuk memposting saldo awal persediaan."
PESAN_PT_LAIN = ("Anda belum punya akses untuk melihat persediaan PT ini. Minta Admin menambahkan akses "
                 "'Akuntansi & Tutup Buku'.")
#: id PT yang dipakai uji lanjutan (U12 ← U3, U7 ← U6)
BAG: Dict[str, str] = {}


async def pt(kode: str) -> str:
    """`pt_uji` + buang cache status PT (20 detik) supaya penjaga `X-Entity-Id` mengenali PT baru."""
    from services.entity_lifecycle_service import invalidate_status_cache
    eid = await pt_uji(kode)
    invalidate_status_cache()
    return eid


def uid(awalan: str) -> str:
    return f"{awalan}_pk29_{uuid.uuid4().hex[:8]}"


def baris_je(je) -> Dict[str, tuple]:
    """{akun: (debit, kredit)} — satu jurnal."""
    out: Dict[str, tuple] = {}
    for ln in je["lines"]:
        d, c = out.get(ln["account_code"], (0.0, 0.0))
        out[ln["account_code"]] = (round(d + float(ln.get("debit") or 0), 2), round(c + float(ln.get("credit") or 0), 2))
    return out


async def roll(db, eid: str, panjang: float, biaya: float, *, status: str = "available") -> str:
    rid = uid("rl")
    await db.inventory_rolls.insert_one({
        "id": rid, "roll_no": f"R29-{rid[-8:].upper()}", "product_id": "prd_pk29", "warehouse_id": "wh_pk29",
        "owner_entity_id": eid, "entity_id": eid, "unit": "meter", "status": status, "length_initial": panjang,
        "length_remaining": panjang, "unit_cost": biaya, "base_unit_cost": biaya, "grade": "A",
        "acquired": {"via": "inbound", "ref_type": "purchase_order", "ref_id": uid("po"), "date": now_iso()},
        "created_at": now_iso()})
    return rid


async def jurnal_persediaan(eid: str, nilai: float) -> None:
    """Jurnal persediaan biasa (bukan saldo awal): Dr 1-1300 / Cr 3-2900."""
    await jurnal(eid, tanggal_buku(), [(PERSEDIAAN, nilai, 0), (EKUITAS, 0, nilai)], "jurnal persediaan uji PK-29",
                 uid("je"))


async def terima_barang(eid: str, nilai: float) -> None:
    """Jurnal operasional penerimaan barang (Dr persediaan / Cr GR/IR) lewat fungsi yang dipakai penutupan GRN."""
    from services import gl_service
    je = await gl_service.post_goods_receipt(task_id=uid("task"), entity_id=eid, amount=nilai, label="uji PK-29")
    assert je, "jurnal penerimaan tidak terbit"


async def rekon(klien, h) -> Dict[str, Any]:
    r = await klien.get("/api/gl/inventory-reconciliation", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def baris(klien, h) -> Dict[str, Dict[str, Any]]:
    return {x["entity_id"]: x for x in (await rekon(klien, h))["rows"]}


async def trueup(klien, h, reason: Any = ALASAN):
    params = {} if reason is None else {"reason": reason}
    return await klien.post("/api/gl/inventory-opening-balance", headers=h, params=params)


async def jurnal_saldo_awal(db, eid: str):
    return await db.journal_entries.find({"source_type": "inventory_opening", "entity_id": eid,
                                          "status": {"$ne": "void"}}, {"_id": 0}).to_list(50)


def _isi(key, value, scope_type, scope_id, reason="uji PK-29"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


async def atur(klien, h, key, value, scope_type="entity", scope_id=""):
    r = await klien.put("/api/config/values", headers=h, json=_isi(key, value, scope_type, scope_id))
    assert r.status_code == 200, r.text


async def pulihkan(klien, h, key, scope_type="entity", scope_id=""):
    if scope_type == "entity":
        r = await klien.post("/api/config/values/clear", headers=h,
                             json={"key": key, "scope_type": "entity", "scope_id": scope_id, "reason": "pulihkan"})
    else:
        r = await klien.post("/api/config/values/reset", headers=h,
                             json={"key": key, "scope_type": "global", "reason": "pulihkan"})
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
async def pembaca(peran_tanpa_acuan):
    """Peran kustom tanpa acuan, hanya `accounting.view` (penugasan PT diatur per akun)."""
    return await peran_tanpa_acuan({"accounting": ["view"]}, label="Lihat Akuntansi PK-29")


# ═══ U1–U2 — `reconciled` per baris; tingkat atas = SEMUA baris sinkron (IV-09) ═════════════════════════════════════
async def test_PK29_U1_selisih_berlawanan_tidak_sinkron(klien, db, sesi, akun, pembaca):
    a, b = await pt("P29U1A"), await pt("P29U1B")
    # A: roll 1.000 m × 10.000 = 10.000.000; jurnal 9.995.000 → selisih +5.000
    await roll(db, a, 1000, 10_000)
    await jurnal_persediaan(a, 9_995_000)
    # B: roll 800 m × 10.000 = 8.000.000; jurnal 8.005.000 → selisih −5.000
    await roll(db, b, 800, 10_000)
    await jurnal_persediaan(b, 8_005_000)
    # Akun yang hanya ditugaskan ke A dan B (PT aktif A): tingkat atas hanya menghitung dua baris itu.
    h = await sesi(await akun(pembaca, entitas=(a, b)), entitas=a)
    j = await rekon(klien, h)
    # Σ selisih = 5.000 − 5.000 = 0 → kode lama menyatakan "sinkron" (reconciled = |0| ≤ 1)
    assert j["reconciled"] is False, j
    assert [r["entity_id"] for r in j["rows"]] == [a, b]
    assert (j["rows_out_of_sync"], j["total_difference"], j["total_abs_difference"]) == (2, 0, 10_000)
    ra, rb = j["rows"]
    assert (ra["subledger_value"], ra["gl_balance"], ra["difference"], ra["reconciled"]) == (
        10_000_000, 9_995_000, 5_000, False)
    assert (rb["subledger_value"], rb["gl_balance"], rb["difference"], rb["reconciled"]) == (
        8_000_000, 8_005_000, -5_000, False)
    # Admin (penugasan semua PT): baris yang sama
    rows = await baris(klien, await sesi(ADMIN, entitas=a))
    assert (rows[a]["difference"], rows[a]["reconciled"], rows[b]["difference"], rows[b]["reconciled"]) == (
        5_000, False, -5_000, False)


async def test_PK29_U2_jurnal_tepat_sinkron(klien, db, sesi, akun, pembaca):
    a, b = await pt("P29U2A"), await pt("P29U2B")
    await roll(db, a, 1000, 10_000)
    await jurnal_persediaan(a, 10_000_000)
    await roll(db, b, 800, 10_000)
    await jurnal_persediaan(b, 8_000_000)
    j = await rekon(klien, await sesi(await akun(pembaca, entitas=(a, b)), entitas=a))
    assert j["reconciled"] is True, j
    assert (j["rows_out_of_sync"], j["total_difference"], j["total_abs_difference"]) == (0, 0, 0)
    assert [(r["difference"], r["reconciled"]) for r in j["rows"]] == [(0, True), (0, True)]


# ═══ U3, U12 — saldo dari akun hasil pemetaan per PT (IV-05) ═════════════════════════════════════════════════════════
async def test_PK29_U3_akun_pemetaan_pt_terbaca(klien, db, sesi):
    from services import gl_mapping_service as glm
    a = await pt("P29U3A")
    BAG["U3"] = a
    if not await db.gl_accounts.find_one({"code": AKUN_PETA}):
        await db.gl_accounts.insert_one({
            "id": uid("gla"), "code": AKUN_PETA, "name": "Persediaan Uji PK-29", "type": "asset",
            "normal_balance": "debit", "parent_code": "1-1000", "is_postable": True, "is_active": True,
            "entity_id": None, "created_at": now_iso()})
    await glm.set_mapping("persediaan.persediaan", a, AKUN_PETA, "uji PK-29 akun persediaan PT", AKTOR_UJI)
    await roll(db, a, 100, 10_000)                     # 100 × 10.000 = 1.000.000
    await terima_barang(a, 1_000_000)
    (je,) = await db.journal_entries.find({"source_type": "goods_receipt", "entity_id": a}, {"_id": 0}).to_list(5)
    assert baris_je(je)[AKUN_PETA] == (1_000_000, 0)   # jurnal terima mendebit 1-1301 (pemetaan PT)
    assert PERSEDIAAN not in baris_je(je)
    r = (await baris(klien, await sesi(ADMIN, entitas=a)))[a]
    # kode lama membaca 1-1300 saja: gl_balance 0, difference 1.000.000
    assert (r["gl_balance"], r["difference"]) == (1_000_000, 0), r
    assert r["reconciled"] is True
    assert {PERSEDIAAN, AKUN_PETA} <= set(r["inventory_accounts"])


async def test_PK29_U12_penjelas_selisih_membaca_akun_pemetaan(klien, sesi):
    a = BAG["U3"]
    r = await klien.get("/api/gl/inventory-drift-explain", headers=await sesi(ADMIN, entitas=a),
                        params={"entity_id": a})
    assert r.status_code == 200, r.text
    j = r.json()
    # kode lama: saldo dari 1-1300 = 0 → selisih 1.000.000
    assert (j["subledger_value"], j["gl_balance"], j["difference"]) == (1_000_000, 1_000_000, 0), j
    assert {x["source"]: x["net"] for x in j["gl_by_source"]} == {"goods_receipt": 1_000_000}


# ═══ U4 — nilai roll tanpa batas (GL-13) ═══════════════════════════════════════════════════════════════════════════
class _KursorMotor:
    """Tiruan kursor Motor untuk SATU PT: `async for` membaca semua dokumen; `to_list(n)` memotong di n seperti Motor /
    MongoDB asli (mongomock_motor mengabaikan n, jadi batas `to_list(100000)` lama tidak terlihat di database tiruan)."""

    def __init__(self, n: int, doc: Dict[str, Any]):
        self.n, self.doc = n, doc

    def _semua(self):
        return ({**self.doc, "id": f"r{i}", "roll_no": f"R29-{i:06d}"} for i in range(self.n))

    def __aiter__(self):
        self._it = self._semua()
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration

    async def to_list(self, length=None):
        return list(itertools.islice(self._semua(), length) if length else self._semua())


class _RollTiruan:
    def __init__(self, asli, eid: str, n: int, doc: Dict[str, Any]):
        self._asli, self._eid, self._n, self._doc = asli, eid, n, doc

    def find(self, q=None, *a, **kw):
        if (q or {}).get("owner_entity_id") == self._eid:
            return _KursorMotor(self._n, self._doc)
        return self._asli.find(q, *a, **kw)

    def __getattr__(self, k):
        return getattr(self._asli, k)


class _DbTiruan:
    def __init__(self, asli, rolls):
        self._asli, self._rolls = asli, rolls

    def __getattr__(self, k):
        return self._rolls if k == "inventory_rolls" else getattr(self._asli, k)

    def __getitem__(self, k):
        return self._rolls if k == "inventory_rolls" else self._asli[k]


async def test_PK29_U4_nilai_roll_tanpa_batas(klien, sesi, monkeypatch):
    from services import gl_service
    a = await pt("P29U4A")
    doc = {"owner_entity_id": a, "status": "available", "length_remaining": 10.0, "unit_cost": 1234.56,
           "base_unit_cost": 1234.56, "acquired": {"via": "inbound", "date": "2026-11-01"}}
    monkeypatch.setattr(gl_service, "db", _DbTiruan(gl_service.db, _RollTiruan(gl_service.db.inventory_rolls, a,
                                                                                150_000, doc)))
    h = await sesi(ADMIN, entitas=a)
    r = (await baris(klien, h))[a]
    # 150.000 roll × (10 × 1.234,56 = 12.345,60) = 1.851.840.000,00 (kode lama: 100.000 × 12.345,60 = 1.234.560.000)
    assert r["subledger_value"] == 1_851_840_000.00, r
    assert r["difference"] == 1_851_840_000.00
    x = await klien.get("/api/gl/inventory-drift-explain", headers=h, params={"entity_id": a})
    assert x.status_code == 200, x.text
    assert x.json()["subledger_value"] == 1_851_840_000.00
    assert x.json()["physical_by_origin"][0]["rolls"] == 150_000


# ═══ U5–U10 — true-up per PT, beralasan, hanya saldo awal (IV-09, K-06) ══════════════════════════════════════════════
async def test_PK29_U5_trueup_hanya_pt_aktif(klien, db, sesi):
    a, b = await pt("P29U5A"), await pt("P29U5B")
    await roll(db, a, 200, 10_000)     # 200 × 10.000 = 2.000.000, tanpa jurnal (masa saldo awal)
    await roll(db, b, 50, 10_000)      # B berselisih 500.000
    r = await trueup(klien, await sesi(ADMIN, entitas=a), ALASAN)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 1 and [p["entity_id"] for p in r.json()["posted"]] == [a]
    (je,) = await jurnal_saldo_awal(db, a)
    assert baris_je(je) == {PERSEDIAAN: (2_000_000, 0), EKUITAS: (0, 2_000_000)}
    assert je["reason"] == ALASAN
    assert await jurnal_saldo_awal(db, b) == []          # kode lama: B ikut disamakan
    rows = await baris(klien, await sesi(ADMIN, entitas=a))
    assert (rows[a]["difference"], rows[a]["reconciled"]) == (0, True)
    assert rows[b]["difference"] == 500_000
    # sesudah true-up, A masih masa saldo awal (hanya jurnal saldo awal) → tetap boleh
    assert rows[a]["trueup_allowed"] is True and rows[a]["trueup_blocked_reason"] == ""


async def test_PK29_U6_pt_bertransaksi_ditolak(klien, db, sesi):
    a = await pt("P29U6A")
    BAG["U6"] = a
    await terima_barang(a, 1_000_000)          # jurnal operasional
    await roll(db, a, 100.5, 10_000)           # 100,5 × 10.000 = 1.005.000 → selisih 5.000
    h = await sesi(ADMIN, entitas=a)
    n = await db.journal_entries.count_documents({"entity_id": a})
    r = await trueup(klien, h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == (
        "True-up persediaan hanya untuk pengisian saldo awal. PT Uji P29U6A sudah punya transaksi persediaan; "
        "telusuri selisihnya lewat \"Jelaskan selisih\" lalu koreksi dokumennya.")
    assert await db.journal_entries.count_documents({"entity_id": a}) == n
    row = (await baris(klien, h))[a]
    assert (row["difference"], row["trueup_allowed"]) == (5_000, False)
    assert row["trueup_blocked_reason"] == r.json()["detail"]


async def test_PK29_U7_pengaturan_pt_dimatikan(klien, db, sesi, kepala_admin):
    a = BAG["U6"]
    b = await pt("P29U7B")
    await terima_barang(b, 1_000_000)
    await roll(db, b, 100.5, 10_000)
    await atur(klien, kepala_admin, KUNCI, False, "entity", a)
    try:
        r = await trueup(klien, await sesi(ADMIN, entitas=a))
        assert r.status_code == 200, r.text
        (je,) = await jurnal_saldo_awal(db, a)
        assert baris_je(je) == {PERSEDIAAN: (5_000, 0), EKUITAS: (0, 5_000)}
        # pengaturan PT A tidak ikut ke B
        hb = await sesi(ADMIN, entitas=b)
        r = await trueup(klien, hb)
        assert r.status_code == 409, r.text
        assert "hanya untuk pengisian saldo awal" in r.json()["detail"]
        assert await jurnal_saldo_awal(db, b) == []
        rows = await baris(klien, hb)
        assert (rows[a]["trueup_allowed"], rows[b]["trueup_allowed"]) == (True, False)
    finally:
        await pulihkan(klien, kepala_admin, KUNCI, "entity", a)


async def test_PK29_U8_alasan_wajib(klien, db, sesi):
    a = await pt("P29U8A")
    await roll(db, a, 200, 10_000)              # selisih 2.000.000, masa saldo awal
    h = await sesi(ADMIN, entitas=a)
    for alasan in (None, "abc"):
        r = await trueup(klien, h, alasan)
        assert r.status_code == 400, r.text
        assert r.json()["detail"] == PESAN_ALASAN
    assert await jurnal_saldo_awal(db, a) == []


async def test_PK29_U9_semua_pt_ditolak(klien, db, sesi, monkeypatch):
    a = await pt("P29U9A")
    await roll(db, a, 200, 10_000)
    n = await db.journal_entries.count_documents({"source_type": "inventory_opening"})
    r = await trueup(klien, await sesi(ADMIN, entitas="all"))
    # Pagar tulis mode "Semua PT" (`entity_write_guard`, middleware, deny-by-default) menolak SEBELUM handler: 409 dengan
    # pesannya sendiri. Handler punya pemeriksaan sendiri (400 `PESAN_SEMUA_PT`) sebagai lapis kedua — laporan
    # "Menyimpang" + usulan koreksi U9.
    from entity_write_guard import MESSAGE
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == MESSAGE
    assert await db.journal_entries.count_documents({"source_type": "inventory_opening"}) == n
    # lapis kedua di handler: konteks gabungan yang lolos pagar → 400 dengan pesan unit
    from routers import gl as gl_router
    asli = gl_router.entity_ctx

    async def _gabungan(request):
        ctx = await asli(request)
        ctx.view_all = True
        return ctx
    monkeypatch.setattr(gl_router, "entity_ctx", _gabungan)
    r = await trueup(klien, await sesi(ADMIN, entitas=a))
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == PESAN_SEMUA_PT
    assert await db.journal_entries.count_documents({"source_type": "inventory_opening"}) == n


async def test_PK29_U10_periode_tertutup(klien, db, sesi):
    a = await pt("P29U10A")
    await roll(db, a, 200, 10_000)
    c = await tutup_periode(a, periode_buku())
    try:
        r = await trueup(klien, await sesi(ADMIN, entitas=a))
        assert r.status_code == 409, r.text
        assert "sudah DITUTUP" in r.json()["detail"]
        assert await jurnal_saldo_awal(db, a) == []
    finally:
        await db.period_closings.delete_one({"id": c["id"]})


# ═══ U11 — cakupan pengguna ════════════════════════════════════════════════════════════════════════════════════════
async def test_PK29_U11_hanya_pt_yang_ditugaskan(klien, db, sesi, akun, pembaca):
    a, b = await pt("P29U11A"), await pt("P29U11B")
    await roll(db, a, 10, 10_000)
    await roll(db, b, 10, 10_000)
    h = await sesi(await akun(pembaca, entitas=(a,)), entitas=a)
    j = await rekon(klien, h)
    assert [r["entity_id"] for r in j["rows"]] == [a], [r["entity_id"] for r in j["rows"]]
    r = await klien.get("/api/gl/inventory-drift-explain", headers=h, params={"entity_id": b})
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == PESAN_PT_LAIN


# ═══ U13 — kunci pengaturan baru + penjaga `to_list` ════════════════════════════════════════════════════════════════
async def test_PK29_U13_putaran_t1_config_dan_penjaga(klien, kepala_admin):
    import config_registry as registry
    from services import gl_service
    from services.config_resolver import value_of
    e = registry.require(KUNCI)
    assert (e["type"], e["default"], e["scopes"], e["permission"]) == ("bool", True, ["global", "entity"],
                                                                         ["accounting", "manage"])
    assert e["risk"] == "high" and e["requires_reason"] is True and e["status"] == "active"
    assert (e["group"], e["section"]) == ("pajak-pembukuan", "tutup-buku")    # = kelompok lama "keuangan-dasar"
    assert e["label"] == "True-up persediaan hanya untuk saldo awal"
    assert e["consumers"] == ["services/gl_service.py:assert_trueup_allowed"]
    a, b = await pt("P29U13A"), await pt("P29U13B")
    assert await value_of(KUNCI) is True
    await atur(klien, kepala_admin, KUNCI, False, "global", "")
    try:
        assert await value_of(KUNCI) is False
        r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": KUNCI})
        assert next(i for i in r.json()["items"] if i["key"] == KUNCI)["value"] is False
        await atur(klien, kepala_admin, KUNCI, True, "entity", a)
        assert (await value_of(KUNCI, {"entity_id": a}), await value_of(KUNCI, {"entity_id": b})) == (True, False)
        await pulihkan(klien, kepala_admin, KUNCI, "entity", a)
        assert await value_of(KUNCI, {"entity_id": a}) is False
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(KUNCI, "lain", "global", ""))
        assert r.status_code == 400, r.text
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(KUNCI, True, "global", "", reason=""))
        assert r.status_code == 400, r.text                   # wajib alasan
    finally:
        await pulihkan(klien, kepala_admin, KUNCI, "global")
    assert await value_of(KUNCI) is True
    assert callable(gl_service.assert_trueup_allowed)
    # penjaga `to_list`: entri 100.000 gl_service sudah tidak ada dan kodenya tidak memakai to_list(100000)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "guardrails"))
    tlb = importlib.import_module("verify_to_list_bound")
    assert ("services/gl_service.py", 100000) not in tlb.ALLOWLIST
    assert ("services/gl_service.py", 100000) not in tlb.scan()


# ═══ Invarian data (`02` D1/D2) — `scripts/verify_data_integrity.py` GL-3 memakai fungsi bersama ═════════════════════
async def test_PK29_invarian_GL3_satu_rumus(db, capsys):
    """GL-3 = `inventory_reconciliation()`: jumlah PT berselisih di keluaran penjaga = `rows_out_of_sync`. Kode lama
    menghitung sendiri (status tanpa `in_transit_transfer`/`damaged`, kode 1-1300 saja) → PT U3 (akun 1-1301) dan PT
    fixture di bawah (roll `in_transit_transfer`) ikut dilaporkan berselisih."""
    from services import gl_service
    g = await pt("P29GL3")
    await roll(db, g, 10, 10_000, status="in_transit_transfer")   # 10 × 10.000 = 100.000
    await jurnal_persediaan(g, 100_000)
    recon = await gl_service.inventory_reconciliation()
    berselisih = sum(1 for r in recon["rows"] if abs(r["difference"]) > recon["rounding_tolerance"])
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    vdi = importlib.import_module("verify_data_integrity")
    await vdi.layer_gl_invariants(db)
    keluar = capsys.readouterr().out
    m = re.search(r"GL: (\d+) PT berselisih persediaan", keluar)
    assert berselisih > 0 and m and int(m.group(1)) == berselisih, keluar[-1500:]
    assert berselisih == recon["rows_out_of_sync"]
    assert next(r for r in recon["rows"] if r["entity_id"] == g)["reconciled"] is True


# ═══ Skrip data nyata (H3) — baca-saja bawaan, `--apply` satu PT ════════════════════════════════════════════════════
async def test_PK29_skrip_baca_saja_dan_apply(db, capsys):
    """`scripts/pk29_trueup_persediaan.py`: baca-saja tidak menulis dan mendaftar true-up lama sesudah transaksi;
    `--apply` hanya untuk PT yang disebut, beralasan, menolak PT bertransaksi tanpa bendera pemilik, aman diulang."""
    from services import gl_service
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    skrip = importlib.import_module("pk29_trueup_persediaan")
    a, lama = await pt("P29SKA"), await pt("P29SKL")
    await roll(db, a, 200, 10_000)                       # masa saldo awal, selisih 2.000.000
    await terima_barang(lama, 1_000_000)                 # PT bertransaksi …
    await roll(db, lama, 100.5, 10_000)
    await gl_service.post_inventory_opening_balance(actor_name="uji", reason="true-up lama", entity_ids=[lama])
    n = await db.journal_entries.count_documents({})
    assert await skrip.jalankan([]) == 0
    keluar = capsys.readouterr().out
    assert await db.journal_entries.count_documents({}) == n
    assert re.search(r"PT Uji P29SKA \(ent_uji_p29ska\) · nilai roll 2\.000\.000 · buku besar 0 \(akun 1-1300\) · "
                     r"selisih 2\.000\.000 · TIDAK sinkron · boleh true-up", keluar), keluar[-2000:]
    assert re.search(r"True-up lama \S+ \d{4}-\d\d-\d\d · 5\.000 · sesudah jurnal persediaan operasional", keluar)
    assert "Mode baca-saja" in keluar
    # --apply tanpa alasan / tanpa PT → ditolak, tanpa jurnal
    assert await skrip.jalankan(["--apply", "--pt", a]) == 2
    assert await skrip.jalankan(["--apply", "--alasan", "stok awal"]) == 2
    assert await db.journal_entries.count_documents({}) == n
    # PT bertransaksi: ditolak tanpa bendera pemilik
    await roll(db, lama, 1, 10_000)                      # selisih baru 10.000
    assert await skrip.jalankan(["--apply", "--pt", lama, "--alasan", "koreksi stok"]) == 2
    assert "hanya untuk pengisian saldo awal" in capsys.readouterr().out
    assert await db.journal_entries.count_documents({}) == n
    # PT masa saldo awal: satu jurnal untuk PT itu saja; jalan kedua tanpa perubahan
    assert await skrip.jalankan(["--apply", "--pt", a, "--alasan", "impor stok awal gudang"]) == 0
    assert "Diterapkan: jurnal" in capsys.readouterr().out
    (je,) = await jurnal_saldo_awal(db, a)
    assert baris_je(je) == {PERSEDIAAN: (2_000_000, 0), EKUITAS: (0, 2_000_000)} and je["reason"] == "impor stok awal gudang"
    assert await db.journal_entries.count_documents({}) == n + 1
    assert await skrip.jalankan(["--apply", "--pt", a, "--alasan", "impor stok awal gudang"]) == 0
    assert "Tanpa perubahan" in capsys.readouterr().out
    # bendera pemilik → PT bertransaksi diproses
    assert await skrip.jalankan(["--apply", "--pt", lama, "--alasan", "keputusan pemilik", "--abaikan-aturan-saldo-awal"]) == 0
    assert len(await jurnal_saldo_awal(db, lama)) == 2


# ═══ U14 — fungsi layanan (skrip impor stok awal, seed) tidak menegakkan aturan ═════════════════════════════════════
async def test_PK29_U14_fungsi_layanan_tanpa_aturan(db):
    """Terakhir di modul: tanpa `entity_ids` fungsi ini menyamakan SEMUA PT (perilaku skrip impor & seed)."""
    from services import gl_service
    a = await pt("P29U14A")
    await terima_barang(a, 1_000_000)
    await roll(db, a, 100.5, 10_000)          # keadaan U6: PT bertransaksi, selisih 5.000 (endpoint: 409)
    hasil = await gl_service.post_inventory_opening_balance(actor_name="uji", reason="impor")
    assert a in [p["entity_id"] for p in hasil["posted"]]
    (je,) = await jurnal_saldo_awal(db, a)
    assert baris_je(je) == {PERSEDIAAN: (5_000, 0), EKUITAS: (0, 5_000)}
