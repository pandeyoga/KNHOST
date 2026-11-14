"""AG-T1 — lapisan penyedia model: putaran alat diuji dengan pelaksana tiruan, pustaka klien hanya di modul pelaksana.

    python -m pytest backend/tests_mem/test_AGT1_penyedia.py -n 0 -q        # dari root repo

Tidak ada panggilan ke layanan luar dan tidak ada kunci API: `set_test_provider(ScriptedProvider([...]))` memasang
pelaksana tiruan (`services/ai_provider_fake.py`) yang mencatat setiap permintaan di `.calls`.
Persiapan (FIXTURE, disisipkan langsung): pemasok S1 (kode "S1", ent_ksc). Alur: `POST /api/ai/chat` (SSE).
"""
import ast
import datetime
import json
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
#: Pustaka klien penyedia model (nama paket teratas yang diimpor).
PUSTAKA_PENYEDIA = {"openai", "anthropic"}
#: Modul pelaksana penyedia yang boleh mengimpor pustaka klien. Dua yang terakhir milik fitur lain (di luar AG-T1).
PELAKSANA = {
    "ai_provider.py": "AG-T1 — lapisan penyedia model Tanya KN",
    "ocr_openai_client.py": "pelaksana baca surat jalan otomatis (GRN Fase 4) — di luar lingkup AG-T1",
    "hr_ai_service.py": "pengenal gambar desain (KP-T8) — di luar lingkup AG-T1",
}


def _ev(teks: str):
    return [json.loads(b[6:]) for b in teks.split("\n\n") if b.startswith("data: ")]


@pytest.fixture(scope="module")
async def siap(db):
    await db.suppliers.insert_one({"id": "sup_agt1p_s1", "code": "S1", "name": "Sumber Satu", "entity_id": "ent_ksc",
                                   "status": "active",
                                   "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()})
    return True


async def _atur(klien, h, key, value, reason="uji AG-T1 U15"):
    r = await klien.put("/api/config/values", headers=h, json={"items": [{
        "key": key, "value": value, "scope_type": "global", "scope_id": "", "reason": reason}]})
    assert r.status_code == 200, r.text


# ── U15 — putaran alat lewat pelaksana tiruan ────────────────────────────────────────────────────────────────────────
async def test_AGT1_U15_putaran_alat_dengan_pelaksana_tiruan(klien, kepala_admin, db, siap):
    from services import ai_provider
    from services.ai_provider_fake import ScriptedProvider
    tiruan = ScriptedProvider([{"tool": "find_entities", "args": {"kind": "supplier", "query": "s1"}},
                               {"text": "Ada satu pemasok."}])
    await _atur(klien, kepala_admin, "ai.enabled", True)
    ai_provider.set_test_provider(tiruan)
    log_sebelum = await db.ai_usage_log.count_documents({"feature": "bi_chat"})
    try:
        r = await klien.post("/api/ai/chat", headers=kepala_admin,
                             json={"question": "Berapa banyak pemasok bernama s1 di PT ini?"})
    finally:
        ai_provider.set_test_provider(None)
        await _atur(klien, kepala_admin, "ai.enabled", False, "pulihkan sesudah uji AG-T1")
    assert r.status_code == 200, r.text
    ev = _ev(r.text)
    alat = [e for e in ev if e["type"] == "tool"]
    assert [e["name"] for e in alat] == ["find_entities"], ev
    assert alat[0]["arguments"] == {"kind": "supplier", "query": "s1"}
    done = [e for e in ev if e["type"] == "done"]
    assert len(done) == 1 and not done[0].get("error"), done
    assert done[0]["text"] == "Ada satu pemasok."
    # Hitungan: giliran 1 = model meminta alat; giliran 2 = model menjawab teks → tepat 2 permintaan ke penyedia.
    assert len(tiruan.calls) == 2, tiruan.calls
    pertama, kedua = tiruan.calls
    assert [t["name"] for t in pertama["tools"]][:2] == ["query_metrics", "analyze_change"]
    assert len(pertama["instructions"]) == 3 and "KONTEKS SESI" in pertama["instructions"][2]
    assert pertama["conversation"][-1] == {"role": "user", "content": "Berapa banyak pemasok bernama s1 di PT ini?"}
    hasil = [it for it in kedua["conversation"] if isinstance(it, dict) and it.get("type") == "tool_result"]
    assert len(hasil) == 1 and json.loads(hasil[0]["output"])["candidates"][0]["id"] == "sup_agt1p_s1"
    log = await db.ai_usage_log.find({"feature": "bi_chat"}, {"_id": 0}).to_list(20)
    assert len(log) == log_sebelum + 1 and log[-1]["status"] == "done", log


async def test_AGT1_U15b_status_dan_narasi_memakai_lapisan(klien, kepala_admin, siap):
    """`GET /api/ai/status` menganggap pelaksana terpasang = kunci ada; narasi template memakai `short_text`."""
    from services import ai_narrative, ai_provider
    from services.ai_provider_fake import ScriptedProvider
    tiruan = ScriptedProvider([{"text": "Penjualan Rp 1.000."}])
    ai_provider.set_test_provider(tiruan)
    await _atur(klien, kepala_admin, "ai.enabled", True)
    try:
        r = await klien.get("/api/ai/status", headers=kepala_admin)
        assert r.status_code == 200 and r.json()["has_key"] is True and r.json()["chat_enabled"] is True, r.text
        hasil = [{"title": "Penjualan", "columns": [{"key": "v", "label": "Nilai", "type": "metric", "unit": "idr"}],
                  "rows": [{"v": 1000}], "totals": {"v": 1000}}]
        out = await ai_narrative.narrate({"id": "tpl_uji", "title": "Uji", "narrative": "luna"}, hasil,
                                         {"id": "user_admin_01"})
        assert out["source"] == "ai" and out["text"] == "Penjualan Rp 1.000.", out
        assert [c["kind"] for c in tiruan.calls] == ["short_text"]
    finally:
        ai_provider.set_test_provider(None)
        await _atur(klien, kepala_admin, "ai.enabled", False, "pulihkan sesudah uji AG-T1")
    r = await klien.get("/api/ai/status", headers=kepala_admin)
    assert r.json()["chat_enabled"] is False


async def test_AGT1_U15c_pemanasan_memakai_lapisan(klien, kepala_admin, db, siap, monkeypatch):
    """Pemanggil ketiga (`job_ai_prewarm`): hari kerja + sakelar aktif → satu `prewarm` ke pelaksana (instruksi sistem +
    katalog, daftar alat lengkap) dan satu baris `ai_usage_log` `bi_prewarm` berbiaya 0 (pelaksana tiruan tanpa harga)."""
    from services import ai_chat_service, ai_provider
    from services.ai_provider_fake import ScriptedProvider
    senin = datetime.datetime(2026, 11, 16, 6, 55, tzinfo=datetime.timezone(datetime.timedelta(hours=7)))
    monkeypatch.setattr(ai_chat_service, "now_wib", lambda: senin)
    tiruan = ScriptedProvider([])
    await _atur(klien, kepala_admin, "ai.enabled", True)
    await _atur(klien, kepala_admin, "ai.prewarm_enabled", True)
    ai_provider.set_test_provider(tiruan)
    try:
        out = await ai_chat_service.job_ai_prewarm()
    finally:
        ai_provider.set_test_provider(None)
        await _atur(klien, kepala_admin, "ai.enabled", False, "pulihkan sesudah uji AG-T1")
        await _atur(klien, kepala_admin, "ai.prewarm_enabled", False, "pulihkan sesudah uji AG-T1")
    assert out["scanned"] == 1, out
    assert [c["kind"] for c in tiruan.calls] == ["prewarm"]
    assert tiruan.calls[0]["instructions"] == [ai_chat_service.SYSTEM_PROMPT_V1, ai_chat_service.CATALOG_V1]
    assert len(tiruan.calls[0]["tools"]) == len(ai_chat_service.TOOLS_V1)
    log = await db.ai_usage_log.find({"feature": "bi_prewarm"}, {"_id": 0}).to_list(5)
    assert len(log) == 1 and log[0]["cost_usd"] == 0.0, log


# ── U16 — pustaka klien penyedia hanya di modul pelaksana (uji statik) ───────────────────────────────────────────────
def _pengimpor() -> dict:
    out = {}
    for f in sorted((BACKEND / "services").rglob("*.py")):
        pohon = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(pohon):
            nama = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                [node.module or ""] if isinstance(node, ast.ImportFrom) and not node.level else []
            for n in nama:
                if n.split(".")[0] in PUSTAKA_PENYEDIA:
                    out.setdefault(f.relative_to(BACKEND / "services").as_posix(), set()).add(n.split(".")[0])
    return out


def test_AGT1_U16_pustaka_penyedia_hanya_di_modul_pelaksana():
    pengimpor = _pengimpor()
    assert set(pengimpor) == set(PELAKSANA), pengimpor
    for f in ("ai_chat_service.py", "ai_narrative.py", "ai_cost.py", "ai_provider_fake.py"):
        assert f not in pengimpor, f
