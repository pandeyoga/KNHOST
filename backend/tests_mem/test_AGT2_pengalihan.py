"""AG-T2 serah-terima (b) — jalur lama dialihkan (docs/blueprint/unit/AG-T2.md, U16 + langkah 5–6).

    python -m pytest backend/tests_mem/test_AGT2_pengalihan.py -n 0 -q        # dari root repo

- U16: izin metrik keuangan asisten = izin endpoint layarnya (Admin Sales: metrik `ar_outstanding` ditolak DAN
  `GET /api/ar/aging` 403 — keduanya sepakat).
- `run_report` `income_statement` / `cash_position` / `cashflow_forecast` memanggil endpoint layarnya lewat pintu aplikasi
  sendiri (gerbang nama peran dicabut): izin & angka = layar; tanpa permintaan HTTP (jadwal) memakai sesi sementara.
- Penyamaran nama pihak juga di mode umum (teks mengalir dikembalikan ke nama asli) dan di narasi templat.
- 120 pertanyaan lama mode `engine`: hak akses tidak lebih longgar daripada kode sebelum unit ini
  (`data/eval120_sebelum_AGT2.json`, dibuat dari kode `c3eb0a2` di database tiruan yang sama).
Tanpa layanan luar: `ScriptedProvider`. FIXTURE (disisip): pelanggan "Toko Maju Jaya" + satu pesanan kredit belum lunas.
"""
import datetime
import json
import re
from pathlib import Path

import pytest

KSC = "ent_ksc"
BACKEND = Path(__file__).resolve().parents[1]
SIMPAN: dict = {}
#: Izin metrik SEBELUM unit ini (analytics_catalog `_AR` dst.), untuk tabel peran × metrik yang berubah.
SEBELUM = {"ar_outstanding": (("ar_receipt", "view"), ("order", "view")),
           "ar_overdue": (("ar_receipt", "view"), ("order", "view")),
           "collections_amount": (("ar_receipt", "view"), ("order", "view")),
           "ap_outstanding": (("vendor_bill", "view"),), "ap_due": (("vendor_bill", "view"),),
           "recognized_revenue": (("accounting", "view"),)}
EMAIL = {"admin": "admin@kainnusantara.id", "sales": "sales@kainnusantara.id", "finance": "finance@kainnusantara.id",
         "warehouse_admin": "warehouse@kainnusantara.id", "sales_admin": "salesadmin@kainnusantara.id",
         "md": "md@kainnusantara.id"}


def _ev(teks: str):
    return [json.loads(b[6:]) for b in teks.split("\n\n") if b.startswith("data: ")]


async def _atur(klien, h, key, value):
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": key, "value": value, "scope_type": "global", "scope_id": "", "reason": "uji AG-T2 (b)"}]})
    assert r.status_code == 200, r.text


@pytest.fixture(scope="module")
async def siap(klien, db, kepala_admin, akun):
    if SIMPAN:
        return SIMPAN
    now = datetime.datetime.now(datetime.timezone.utc)
    await db.customers.insert_one({"id": "cus_agt2b", "name": "Toko Maju Jaya", "entity_id": KSC, "status": "active",
                                   "payment_profile": {}, "created_at": now.isoformat()})
    await db.sales_orders.insert_one({"id": "so_agt2b", "number": "SO-AGT2B", "customer_id": "cus_agt2b",
                                      "customer_name": "Toko Maju Jaya", "entity_id": KSC, "status": "confirmed",
                                      "payment_status": "unpaid", "grand_total": 5_000_000, "total_amount": 5_000_000,
                                      "payments": [], "payment_term_days": 0, "payment_term_code": "NET30",
                                      "created_at": (now - datetime.timedelta(days=3)).isoformat()})
    for peran in ("finance", "md", "sales_admin"):
        if not await db.users.find_one({"email": EMAIL[peran]}):
            await akun(peran, entitas=(KSC,), email=EMAIL[peran])
    await _atur(klien, kepala_admin, "ai.enabled", True)
    SIMPAN["ok"] = True
    return SIMPAN


async def _ctx(user, entity=KSC):
    from services.ai_schedules import ctx_for
    return await ctx_for(user, entity, False)


# ── U16 — metrik piutang asisten dan layar Umur Piutang sepakat ──────────────────────────────────────────────────────
async def test_AGT2_U16_admin_sales_metrik_piutang_dan_layar_sepakat(klien, db, sesi, siap):
    u = await db.users.find_one({"email": EMAIL["sales_admin"]}, {"_id": 0})
    from dependencies import has_permission
    assert await has_permission(u, "order", "view")
    assert not await has_permission(u, "accounting", "view") and not await has_permission(u, "penalty", "issue")
    h = await sesi(u)
    r = await klien.post("/api/ai/query", headers=h, json={"metrics": ["ar_outstanding"], "group_by": [], "period": None})
    assert r.status_code == 400 and "ar_outstanding" in r.json()["detail"], r.text    # metrik masuk `denied`
    r2 = await klien.post("/api/ai/query", headers=h, json={"metrics": ["ar_outstanding", "orders_count"], "group_by": []})
    assert r2.status_code == 200 and r2.json()["denied"] == ["ar_outstanding"], r2.text
    assert (await klien.get("/api/ar/aging", headers=h)).status_code == 403


def _izin_router(berkas: str, fungsi: str):
    src = (BACKEND / "routers" / berkas).read_text(encoding="utf-8")
    badan = src.split(f"async def {fungsi}(", 1)[1].split("\n@router", 1)[0]
    return tuple(re.findall(r'require_permission\(request, "([a-z_]+)", "([a-z_]+)"', badan)[:1])


def test_AGT2_U16b_izin_metrik_keuangan_sama_dengan_endpoint_layar():
    from routers.ar_aging import AGING_READ
    from services.analytics_catalog import METRICS
    harap = {"ar_outstanding": tuple(AGING_READ), "ar_overdue": tuple(AGING_READ),
             "collections_amount": _izin_router("ar_receipts.py", "list_receipts"),
             "ap_outstanding": _izin_router("vendor_bills.py", "vendor_bill_payables"),
             "ap_due": _izin_router("vendor_bills.py", "vendor_bill_payables"),
             "recognized_revenue": _izin_router("gl.py", "list_journal")}
    assert harap["collections_amount"] == (("ar_receipt", "view"),)
    for m, izin in harap.items():
        assert tuple(tuple(p) for p in METRICS[m]["perms"]) == tuple(tuple(p) for p in izin), m


async def test_AGT2_U16c_tabel_peran_metrik_hanya_menyempit(db, siap):
    """Tiap peran bawaan: metrik yang dulu tertolak tetap tertolak; yang berubah hanya dari boleh → ditolak."""
    from permissions_config import DEFAULT_PERMISSIONS
    from services.analytics_catalog import METRICS

    def boleh(peran, izin):
        m = DEFAULT_PERMISSIONS.get(peran, {})
        return any(a in (m.get(r) or []) or "*" in (m.get(r) or []) for r, a in izin)
    berubah = []
    for peran in sorted(DEFAULT_PERMISSIONS):
        if "view" not in (DEFAULT_PERMISSIONS[peran].get("ai") or []):
            continue
        for metrik, lama in SEBELUM.items():
            dulu, kini = boleh(peran, lama), boleh(peran, METRICS[metrik]["perms"])
            assert not (kini and not dulu), (peran, metrik)   # tidak pernah lebih longgar
            if dulu != kini:
                berubah.append((peran, metrik))
    # Hitungan: Sales, Admin Sales (order.view/ar_receipt.view tanpa accounting.view/penalty.issue) kehilangan dua metrik
    # piutang; Admin Sales juga uang masuk bila tanpa ar_receipt.view; MD & Admin Gudang (order.view) idem.
    assert ("sales_admin", "ar_outstanding") in berubah and ("sales", "ar_outstanding") in berubah
    assert all(m in ("ar_outstanding", "ar_overdue", "collections_amount") for _, m in berubah), berubah
    SIMPAN["berubah"] = berubah


# ── run_report: tiga laporan keuangan lewat endpoint layarnya ────────────────────────────────────────────────────────
async def test_AGT2_b_laba_rugi_tanpa_gerbang_nama_peran(klien, akun, sesi, peran_tanpa_acuan, siap):
    rid = await peran_tanpa_acuan({"ai": ["view"], "accounting": ["view"]}, label="AGT2b akuntansi")
    u = await akun(rid, entitas=(KSC,))
    h = await sesi(u)
    r = await klien.post("/api/ai/tools/run_report", headers=h, json={"report": "income_statement",
                                                                     "period": {"preset": "mtd", "from": None, "to": None}})
    assert r.status_code == 200, r.text
    st = r.json()["sections"]["statement"]
    p = st["period"]
    layar = (await klien.get(f"/api/finance/income-statement?start={p['from']}&end={p['to']}", headers=h)).json()
    assert st["totals"]["amount"] == layar["net_income"]
    # Posisi kas menuntut izin layarnya (`cash.view`): pemegang `accounting.view` saja kini ditolak, pesannya dari layar.
    r = await klien.post("/api/ai/tools/run_report", headers=h, json={"report": "cash_position"})
    layar_kas = await klien.get("/api/bank-accounts/position", headers=h)
    assert layar_kas.status_code == 403 and r.status_code == 400 and r.json()["detail"] == layar_kas.json()["detail"]


async def test_AGT2_b_posisi_kas_dan_proyeksi_sama_dengan_layar(klien, akun, sesi, peran_tanpa_acuan, siap):
    rid = await peran_tanpa_acuan({"ai": ["view"], "cash": ["view"], "accounting": ["view"]}, label="AGT2b kas")
    h = await sesi(await akun(rid, entitas=(KSC,)))
    r = await klien.post("/api/ai/tools/run_report", headers=h, json={"report": "cash_position"})
    assert r.status_code == 200, r.text
    layar = (await klien.get("/api/bank-accounts/position", headers=h)).json()
    assert r.json()["sections"]["kpi"]["totals"]["balance"] == layar["gl_total"]
    r = await klien.post("/api/ai/tools/run_report", headers=h, json={"report": "cashflow_forecast"})
    assert r.status_code == 200, r.text
    layar = (await klien.get("/api/finance/cashflow-forecast", headers=h)).json()
    assert len(r.json()["sections"]["weeks"]["rows"]) == len(layar.get("buckets") or layar.get("weeks") or [])


async def test_AGT2_b_jadwal_tanpa_permintaan_memakai_sesi_sementara(db, siap):
    from services import ai_tools
    from services.ai_self_api import current
    u = await db.users.find_one({"email": EMAIL["admin"]}, {"_id": 0})
    assert current() is None
    out = await ai_tools.run_report({"report": "income_statement", "period": None}, u, await _ctx(u), "jadwal")
    assert "statement" in out["sections"], out
    assert await db.sessions.count_documents({"purpose": "ai_schedule"}) == 0   # sesi sementara dihapus


# ── penyamaran di mode umum & narasi ─────────────────────────────────────────────────────────────────────────────────
async def test_AGT2_b_mode_umum_nama_pihak_disamarkan(klien, db, kepala_admin, siap):
    from services import ai_provider
    from services.ai_provider_fake import ScriptedProvider
    tiruan = ScriptedProvider([{"tool": "list_records", "args": {"record_type": "ar_open_items", "period": None, "filters": [],
                                                                 "sort": None, "limit": 20}},
                               {"text": "PLG-001 masih punya tagihan Rp 5.000.000"}])
    ai_provider.set_test_provider(tiruan)
    try:
        r = await klien.post("/api/ai/chat", headers=kepala_admin, json={"question": "siapa yang masih punya tagihan?"})
    finally:
        ai_provider.set_test_provider(None)
    assert r.status_code == 200, r.text
    terkirim = json.dumps(tiruan.calls, ensure_ascii=False, default=str)
    assert "Toko Maju Jaya" not in terkirim and "PLG-001" in terkirim and "Budi Santoso" not in terkirim
    assert "Pengguna: Pengguna" in tiruan.calls[0]["instructions"][2]
    ev = _ev(r.text)
    mengalir = "".join(e["text"] for e in ev if e["type"] == "delta")
    assert "Toko Maju Jaya" in mengalir and "PLG-" not in mengalir, mengalir
    done = [e for e in ev if e["type"] == "done"][0]
    assert done["text"] == "Toko Maju Jaya masih punya tagihan Rp 5.000.000" and done["verification"]["ok"] is True
    s = await db.ai_chat_sessions.find_one({"id": done["session_id"]}, {"_id": 0})
    assert s["alias_map"]["by_name"]["Toko Maju Jaya"] == "PLG-001" and s["turns"][-1]["content"] == done["text"]


def test_AGT2_b_pengalir_tidak_memecah_kode():
    from services.ai_chat_service import _StreamUnmask
    from services.ai_privacy import NameMasker
    m = NameMasker({"by_name": {"Toko Maju Jaya": "PLG-001"}, "counters": {"PLG": 1}})
    u = _StreamUnmask(m)
    keluar = "".join([u.feed("Pelanggan PL"), u.feed("G-0"), u.feed("01 menunggak"), u.flush()])
    assert keluar == "Pelanggan Toko Maju Jaya menunggak"


async def test_AGT2_b_narasi_templat_disamarkan(klien, kepala_admin, siap):
    from services import ai_narrative, ai_provider
    from services.ai_provider_fake import ScriptedProvider
    tiruan = ScriptedProvider([{"text": "PLG-001 tertinggi Rp 5.000.000."}])
    ai_provider.set_test_provider(tiruan)
    try:
        hasil = [{"title": "Piutang", "columns": [{"key": "customer", "label": "Pelanggan", "type": "dimension", "unit": ""},
                                                  {"key": "v", "label": "Nilai", "type": "metric", "unit": "idr"}],
                  "rows": [{"customer": "Toko Maju Jaya", "v": 5000000, "base_salary": 1}], "totals": {"v": 5000000}}]
        out = await ai_narrative.narrate({"id": "tpl_uji", "title": "Uji", "narrative": "luna"}, hasil,
                                         {"id": "user_admin_01", "home_entity_id": KSC, "allowed_entity_ids": [KSC]})
    finally:
        ai_provider.set_test_provider(None)
    isi = tiruan.calls[0]["content"]
    assert "Toko Maju Jaya" not in isi and "PLG-001" in isi and "base_salary" not in isi
    assert out["text"] == "Toko Maju Jaya tertinggi Rp 5.000.000."


# ── 120 pertanyaan lama mode engine: hak akses tidak lebih longgar ───────────────────────────────────────────────────
def _tertolak(v) -> bool:
    return bool(v.get("denied")) or "tidak tersedia" in str(v.get("error") or "")


async def test_AGT2_b_120_pertanyaan_lama_tidak_lebih_longgar(db, siap):
    from services import ai_tools
    lama = json.loads((BACKEND / "tests_mem" / "data" / "eval120_sebelum_AGT2.json").read_text(encoding="utf-8"))
    qs = json.loads((BACKEND / "tools" / "ai_eval" / "questions_v1.json").read_text(encoding="utf-8"))["questions"]
    baru = {}
    for q in qs:
        if not q["expected"]:
            continue
        u = await db.users.find_one({"email": EMAIL[q["role"]]}, {"_id": 0, "password_hash": 0})
        try:
            res = await ai_tools.execute(q["expected"]["tool"], q["expected"]["args"], u, await _ctx(u, u["home_entity_id"]),
                                         "eval")
        except Exception as exc:  # noqa: BLE001 — ekspresi agregasi yang tidak didukung database tiruan (sama di kode lama)
            res = {"error": f"TIRUAN: {type(exc).__name__}"}
        den = sorted(set(res.get("denied") or []) | {m for s in (res.get("sections") or {}).values()
                                                     for m in (s.get("denied") or [])})
        baru[q["id"]] = {"error": res.get("error"), "denied": den}
    assert set(baru) == set(lama) and len(baru) == 110
    longgar = [k for k in lama if _tertolak(lama[k]) and not _tertolak(baru[k])]
    # K-FIN-01 (pemilik 17 Nov 2026 malam: Finance memegang akses yang sama dengan Manajer) — Finance kini memegang
    # `ai.view_margin` Manajer, jadi "Laba kotor per pelanggan" (q099, peran finance) terjawab. Bukan pelonggaran diam.
    assert sorted(longgar) == ["q099"], longgar
    menyempit = sorted(k for k in lama if _tertolak(baru[k]) and not _tertolak(lama[k]))
    SIMPAN["menyempit"] = menyempit
    # Yang menyempit hanya pertanyaan metrik/laporan keuangan (piutang, uang masuk, laporan keuangan).
    for k in menyempit:
        assert set(baru[k]["denied"]) <= {"ar_outstanding", "ar_overdue", "collections_amount"} or baru[k]["error"], k
