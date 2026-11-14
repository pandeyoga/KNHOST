"""AG-T4 — paket tutup buku bulanan Asisten Keuangan (docs/blueprint/unit/AG-T4.md, U1–U11, U15).

    python -m pytest backend/tests_mem/test_AGT4_paket.py -n 0 -q        # dari root repo

Tanpa layanan luar dan tanpa kunci: ringkasan model memakai `ScriptedProvider` (`set_test_provider`).

Persiapan (FIXTURE, disisipkan langsung): jurnal seed `ent_ksc`/`ent_kanda` dikosongkan; `ent_ksc` Februari 2026 —
pendapatan 500.000 (Dr 1-1100 / Cr 4-1000, 5 Feb) dan beban 200.000 (Dr 6-1100 / Cr 1-1100, 6 Feb) → laba
500.000 − 200.000 = 300.000; tiga jurnal manual Dr 1-1100 / Cr 3-1000 (bukan laba rugi): 10.000 (10 Feb), 20.000
(20 Feb), 30.000 (3 Mar); dua jurnal "uji" di atas = bukan manual. Piutang (Januari, tidak menyentuh laba rugi
Februari): pesanan kredit "Toko Agt Empat" 7.500.000 diakui (jurnal sumber pesanan Dr 1-1200 / Cr 4-1000) + jurnal
lain Dr 1-1200 / Cr 3-1000 500.000 → saldo buku besar piutang per 28 Feb = 7.500.000 + 500.000 = 8.000.000; umur
piutang = 7.500.000. `ent_kanda` pendapatan 900.000 (7 Feb).
ALUR (API): peran uji (`POST /api/access/roles`), sakelar akun (`PATCH /api/users/{id}`), pengaturan
(`PUT /api/config/values`), paket (`POST /api/ai/finance/closing-pack`), unduhan (`GET …/export.xlsx`).
"""
import datetime
import io
import json

import pytest

from pembantu import jurnal

KSC, KANDA = "ent_ksc", "ent_kanda"
FEB = "2026-02"
SIMPAN: dict = {}
IZIN_FIN = {"ai": ["view"], "ai_finance": ["view"], "accounting": ["view"], "cash": ["view"],
            "interco_finance": ["view"], "gl_mapping": ["view"]}


async def _atur(klien, h, key, value):
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": key, "value": value, "scope_type": "global", "scope_id": "", "reason": "uji AG-T4"}]})
    assert r.status_code == 200, r.text


async def _sakelar(klien, h_admin, uid, nyala: bool):
    r = await klien.patch(f"/api/users/{uid}", headers=h_admin, json={"data": {"ai_finance": {"enabled": nyala}}})
    assert r.status_code == 200, r.text


async def _entri(eid, tgl, baris, ket, source_type, source_id):
    from services import gl_service as gl
    return await gl._insert_entry(lines=[{"account_code": k, "debit": d, "credit": c} for k, d, c in baris],
                                  description=ket, date=tgl, source_type=source_type, source_id=source_id,
                                  entity_id=eid, created_by="uji")


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan):
    if SIMPAN:
        return SIMPAN
    await db.journal_entries.delete_many({"entity_id": {"$in": [KSC, KANDA]}})
    await db.sales_orders.delete_many({"entity_id": KSC})
    await jurnal(KSC, "2026-02-05", [("1-1100", 500000, 0), ("4-1000", 0, 500000)], "Penjualan tunai uji", "agt4_jual")
    await jurnal(KSC, "2026-02-06", [("6-1100", 200000, 0), ("1-1100", 0, 200000)], "Beban uji", "agt4_beban")
    await jurnal(KANDA, "2026-02-07", [("1-1100", 900000, 0), ("4-1000", 0, 900000)], "Penjualan Kanda uji", "agt4_kanda")
    for tgl, nilai, sid in (("2026-02-10", 10000, "m1"), ("2026-02-20", 20000, "m2"), ("2026-03-03", 30000, "m3")):
        await _entri(KSC, tgl, [("1-1100", nilai, 0), ("3-1000", 0, nilai)], f"Jurnal manual uji {sid}", "manual",
                     f"agt4_{sid}")
    now = datetime.datetime.now(datetime.timezone.utc)
    await db.customers.insert_one({"id": "cus_agt4", "name": "Toko Agt Empat", "entity_id": KSC, "status": "active",
                                   "payment_profile": {}, "created_at": now.isoformat()})
    await db.sales_orders.insert_one({
        "id": "so_agt4", "number": "SO-AGT4-1", "customer_id": "cus_agt4", "customer_name": "Toko Agt Empat",
        "entity_id": KSC, "status": "confirmed", "payment_status": "unpaid", "grand_total": 7_500_000,
        "total_amount": 7_500_000, "payments": [], "payment_term_days": 0, "payment_term_code": "NET30",
        "created_at": "2026-01-10T03:00:00+00:00"})
    await _entri(KSC, "2026-01-10", [("1-1200", 7_500_000, 0), ("4-1000", 0, 7_500_000)], "Penjualan kredit uji",
                 "sales_order", "so_agt4")
    await _entri(KSC, "2026-01-15", [("1-1200", 500_000, 0), ("3-1000", 0, 500_000)], "Piutang lain uji", "uji",
                 "agt4_piutang_lain")
    rid = await peran_tanpa_acuan(IZIN_FIN, label="AGT4 fin")
    fin = await akun(rid, entitas=(KSC,))
    await _sakelar(klien, kepala_admin, fin["id"], True)
    adm = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    await _sakelar(klien, kepala_admin, adm["id"], True)
    SIMPAN.update(fin=fin, h_fin=await sesi(fin), adm=adm, h_adm=kepala_admin)
    return SIMPAN


async def _paket(klien, h, period=FEB):
    r = await klien.post("/api/ai/finance/closing-pack", headers=h, json={"period": period})
    assert r.status_code == 200, r.text
    return r.json()


async def _hasil(klien, h, pack):
    r = await klien.get(f"/api/ai/finance/closing-pack/{pack['id']}", headers=h)
    assert r.status_code == 200, r.text
    doc = r.json()
    return doc, {s["key"]: doc["results"].get(s["result_id"]) for s in doc["sections"]}


# ── U2 — batas bulan ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_AGT4_U2_batas_bulan():
    from services.ai_finance_reports import month_bounds
    assert month_bounds("2026-02") == ("2026-02-01", "2026-02-28")
    assert month_bounds("2028-02") == ("2028-02-01", "2028-02-29")   # kabisat
    assert month_bounds("2026-12") == ("2026-12-01", "2026-12-31")


# ── U1 — laba-rugi paket = layar ─────────────────────────────────────────────────────────────────────────────────────
async def test_AGT4_U1_laba_rugi_sama_dengan_layar(klien, siap):
    pack = await _paket(klien, siap["h_fin"])
    SIMPAN["pack"] = pack
    _doc, res = await _hasil(klien, siap["h_fin"], pack)
    layar = (await klien.get("/api/finance/income-statement?start=2026-02-01&end=2026-02-28", headers=siap["h_fin"])).json()
    # Hitungan tangan: 500.000 − 200.000 = 300.000.
    assert res["laba_rugi"]["totals"]["net_income"] == layar["net_income"] == 300000
    assert pack["entity_id"] == KSC and pack["period"] == FEB and pack["id"].startswith("aipack_")


# ── U3 — pencocokan piutang: buku besar − buku pembantu ──────────────────────────────────────────────────────────────
async def test_AGT4_U3_pencocokan_piutang(klien, siap):
    _doc, res = await _hasil(klien, siap["h_fin"], SIMPAN["pack"])
    rows = res["pencocokan"]["rows"]
    piutang = next(r for r in rows if r["item"].startswith("Piutang usaha"))
    assert "(1-1200)" in piutang["item"]   # kode dari Pemetaan Akun (`penjualan.piutang`), bukan ditulis di kode
    # 8.000.000 − 7.500.000 = 500.000
    assert (piutang["gl"], piutang["sub"], piutang["difference"]) == (8_000_000, 7_500_000, 500_000)
    assert res["umur_piutang"]["totals"]["total"] == 7_500_000


async def test_AGT4_U3b_akun_kontrol_belum_dipetakan_tidak_ditebak(klien, siap, monkeypatch):
    """Kunci pemetaan tidak ditemukan → "Akun kontrol belum dipetakan", tanpa angka buku besar (H4)."""
    from services import ai_finance_reports as afr
    monkeypatch.setattr(afr, "CONTROL_KEYS", (("piutang", "kunci.tidak_ada", "Piutang usaha"),
                                              ("hutang", "pembelian.hutang", "Hutang usaha")))
    _doc, res = await _hasil(klien, siap["h_fin"], await _paket(klien, siap["h_fin"]))
    piutang = next(r for r in res["pencocokan"]["rows"] if r["item"].startswith("Piutang usaha"))
    assert piutang["note"] == afr.NOT_MAPPED and piutang["gl"] is None and piutang["difference"] is None


# ── U4 — bagian tanpa izin endpoint dilewati, bagian lain tetap ──────────────────────────────────────────────────────
async def test_AGT4_U4_tanpa_izin_hutang_dilewati(klien, siap):
    doc, res = await _hasil(klien, siap["h_fin"], SIMPAN["pack"])
    st = {s["key"]: s for s in doc["sections"]}
    assert len(st) == 12
    assert st["umur_hutang"]["status"] == "skipped"
    assert st["umur_hutang"]["note"] == ("Tidak disertakan: Anda belum punya akses Hutang Supplier & Kontrabon.")
    assert [k for k, s in st.items() if s["status"] != "ok"] == ["umur_hutang"]   # sebelas bagian lain `ok`
    ring = {r["item"]: r["value"] for r in res["ringkasan"]["rows"]}
    assert ring["Lembar tidak disertakan"] == "Umur Hutang"
    assert ring["Lembar 6 · Umur Hutang"] == st["umur_hutang"]["note"]


# ── U5 — mode Semua PT ditolak ───────────────────────────────────────────────────────────────────────────────────────
async def test_AGT4_U5_semua_pt_409(klien, db, siap):
    sebelum = await db.ai_finance_packs.count_documents({})
    for h in (siap["h_adm"], siap["h_fin"]):
        r = await klien.post("/api/ai/finance/closing-pack", headers={**h, "X-Entity-Id": "all"}, json={"period": FEB})
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == "Pilih satu PT. Paket tutup buku dibuat per PT."
    assert await db.ai_finance_packs.count_documents({}) == sebelum


# ── U6 — PT di luar penugasan 403; angka PT lain tidak ikut ──────────────────────────────────────────────────────────
async def test_AGT4_U6_pt_lain(klien, db, siap):
    r = await klien.post("/api/ai/finance/closing-pack", headers={**siap["h_fin"], "X-Entity-Id": KANDA},
                         json={"period": FEB})
    assert r.status_code == 403, r.text
    doc, res = await _hasil(klien, siap["h_fin"], SIMPAN["pack"])
    jejak = json.dumps([doc, res], ensure_ascii=False, default=str)
    assert "900000" not in jejak.replace(".0", "") and "900.000" not in jejak


# ── U9 — jurnal manual disaring bulan di kode ────────────────────────────────────────────────────────────────────────
async def test_AGT4_U9_jurnal_manual(klien, siap):
    _doc, res = await _hasil(klien, siap["h_fin"], SIMPAN["pack"])
    jm = res["jurnal_manual"]
    assert [r["date"] for r in jm["rows"]] == ["2026-02-10", "2026-02-20"]   # Maret & bukan manual tidak ikut
    assert jm["totals"] == {"count": 2, "total_debit": 30000}               # 10.000 + 20.000


# ── U10 — unduhan Excel 12 lembar ────────────────────────────────────────────────────────────────────────────────────
async def test_AGT4_U10_unduh_excel(klien, siap):
    from openpyxl import load_workbook
    pack = SIMPAN["pack"]
    r = await klien.get(f"/api/ai/finance/closing-pack/{pack['id']}/export.xlsx", headers=siap["h_fin"])
    assert r.status_code == 200, r.text
    assert f'filename="tutup-buku-' in r.headers["content-disposition"] and f'-{FEB}.xlsx"' in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Ringkasan", "Laba-Rugi", "Neraca", "Arus Kas", "Umur Piutang", "Umur Hutang", "Pencocokan",
                             "Antar-PT", "Kas & Bank", "Posting Gagal", "Jurnal Manual", "Status Periode"]
    a1 = str(wb["Ringkasan"]["A1"].value)
    assert pack["entity_label"] and pack["entity_label"] in a1 and "Februari 2026" in a1
    teks_hutang = " ".join(str(c.value) for row in wb["Umur Hutang"].iter_rows() for c in row if c.value)
    assert "Tidak disertakan" in teks_hutang
    lr = [[c.value for c in row] for row in wb["Laba-Rugi"].iter_rows()]
    assert ["Ringkasan", "Laba bersih", 300000] in lr


# ── U11 — bulan tidak sah / belum berakhir ───────────────────────────────────────────────────────────────────────────
async def test_AGT4_U11_bulan_tidak_sah(klien, siap):
    from services.analytics_time import now_wib
    bulan_ini = now_wib().strftime("%Y-%m")
    for p in ("2026-13", bulan_ini, "2099-01", "Feb 2026"):
        r = await klien.post("/api/ai/finance/closing-pack", headers=siap["h_fin"], json={"period": p})
        assert r.status_code == 400, (p, r.text)
        assert r.json()["detail"] == "Bulan harus berbentuk TTTT-BB dan sudah berakhir."


# ── U15 — paket milik orang lain ─────────────────────────────────────────────────────────────────────────────────────
async def test_AGT4_U15_paket_orang_lain_404(klien, siap):
    pid = SIMPAN["pack"]["id"]
    for path in (f"/api/ai/finance/closing-pack/{pid}", f"/api/ai/finance/closing-pack/{pid}/export.xlsx"):
        r = await klien.get(path, headers=siap["h_adm"])
        assert r.status_code == 404, r.text
        assert r.json()["detail"] == "Paket tidak ditemukan."


async def test_AGT4_gerbang_asisten_keuangan(klien, kepala_admin, akun, sesi, peran_tanpa_acuan, siap):
    """Tanpa `ai_finance.view` → pesan Z6; berizin tetapi sakelar akun mati → pesan sakelar (AG-T2)."""
    rid = await peran_tanpa_acuan({k: v for k, v in IZIN_FIN.items() if k != "ai_finance"}, label="AGT4 tanpa asisten")
    h = await sesi(await akun(rid, entitas=(KSC,)))
    r = await klien.post("/api/ai/finance/closing-pack", headers=h, json={"period": FEB})
    assert r.status_code == 403 and "Asisten Keuangan" in r.json()["detail"], r.text
    rid2 = await peran_tanpa_acuan(IZIN_FIN, label="AGT4 sakelar mati")
    h2 = await sesi(await akun(rid2, entitas=(KSC,)))
    r = await klien.post("/api/ai/finance/closing-pack", headers=h2, json={"period": FEB})
    assert r.status_code == 403 and "belum dinyalakan" in r.json()["detail"], r.text


async def test_AGT4_kemajuan_per_lembar(klien, siap):
    """`?stream=1` — 12 event kemajuan lalu `done` berisi paket (layar: "Menyusun paket… (i dari 12)")."""
    r = await klien.post("/api/ai/finance/closing-pack?stream=1", headers=siap["h_fin"], json={"period": FEB})
    assert r.status_code == 200, r.text
    ev = [json.loads(b[6:]) for b in r.text.split("\n\n") if b.startswith("data: ")]
    prog = [e for e in ev if e["type"] == "progress"]
    assert [e["done"] for e in prog] == list(range(1, 13)) and {e["total"] for e in prog} == {12}
    assert ev[-1]["type"] == "done" and ev[-1]["pack"]["id"].startswith("aipack_")


# ── U7 / U8 — ringkasan model hanya bila lolos pemeriksa angka ───────────────────────────────────────────────────────
async def _paket_dengan_model(klien, h, teks):
    from services import ai_provider
    from services.ai_provider_fake import ScriptedProvider
    tiruan = ScriptedProvider([{"text": teks}])
    ai_provider.set_test_provider(tiruan)
    try:
        return await _paket(klien, h), tiruan
    finally:
        ai_provider.set_test_provider(None)


async def test_AGT4_U7_angka_karangan_ditolak(klien, siap):
    await _atur(klien, siap["h_adm"], "ai.enabled", True)
    try:
        pack, tiruan = await _paket_dengan_model(klien, siap["h_fin"], "Laba Rp 999.999")
    finally:
        await _atur(klien, siap["h_adm"], "ai.enabled", False)
    assert len(tiruan.calls) == 1 and tiruan.calls[0]["kind"] == "short_text"
    assert "Toko Agt Empat" not in json.dumps(tiruan.calls, ensure_ascii=False)   # K-43 — nama pihak disamarkan
    assert pack["summary_source"] == "auto" and "999.999" not in pack["summary"]
    assert "Laba bersih: Rp 300.000." in pack["summary"]


async def test_AGT4_U8_angka_cocok_dipakai(klien, siap):
    await _atur(klien, siap["h_adm"], "ai.enabled", True)
    try:
        pack, _t = await _paket_dengan_model(klien, siap["h_fin"], "Laba bersih Rp 300.000")
    finally:
        await _atur(klien, siap["h_adm"], "ai.enabled", False)
    assert pack["summary_source"] == "model" and pack["summary"] == "Laba bersih Rp 300.000"
    assert pack["verification"]["ok"] is True and pack["verification"]["checked"] == 1


def test_AGT4_modul_tanpa_db_dan_tanpa_alat_tindakan():
    """Modul paket/ringkasan tidak mengimpor `db` dan tidak mengenal alat tindakan."""
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "services" / "ai_finance_reports.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = [(n.module or "", [a.name for a in n.names]) for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    imports += [("", [a.name for a in n.names]) for n in ast.walk(tree) if isinstance(n, ast.Import)]
    assert not any(m == "db" or "db" in names for m, names in imports), imports
    assert "propose_action" not in src and "ai_actions" not in src and '"POST"' not in src
