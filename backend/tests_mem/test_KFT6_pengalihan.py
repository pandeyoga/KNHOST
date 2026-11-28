"""KF-T6 serah-terima (b) — titik lama dialihkan ke `services/dual_control.py` (docs/blueprint/unit/KF-T6.md).

Butir: U2, U3, U4, U5, U6, U7, U8, U9, U10, U12, U13, U14, U15. Fixture: `mgr`, `mgr2` (dua akun manager, PT ent_ksc +
ent_kanda), `adm` (admin seed), `adm2` (admin kedua). Dokumen disisipkan langsung dalam status menunggu persetujuan
dengan pengaju `mgr` (atau `adm`). Pengaturan yang diubah tiap uji dipulihkan di akhir uji.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest

from core_utils import now_iso
from pembantu import saldo_akun, tutup_periode
from services import config_resolver as resolver

pytestmark = pytest.mark.anyio

BACKEND = Path(__file__).resolve().parents[1]


def pesan(label: str) -> str:
    return (f"{label} harus diputuskan orang lain: Anda yang mengajukannya. Minta rekan yang berwenang. "
            "Admin dapat mengubah aturan ini di Pengaturan › Persetujuan › Kontrol dua orang.")


def _id(awal: str) -> str:
    return f"{awal}_kft6_{uuid.uuid4().hex[:8]}"


async def atur(key, value, ent="ent_ksc"):
    if ent:
        await resolver.set_value(key, value, scope_type="entity", scope_id=ent, reason="uji KF-T6", actor="uji")
    else:
        await resolver.set_value(key, value, scope_type="global", reason="uji KF-T6", actor="uji")


async def cabut(key, ent="ent_ksc"):
    if ent:
        await resolver.clear_layer(key, scope_type="entity", scope_id=ent, actor="uji", reason="uji KF-T6")
    else:
        e = __import__("config_registry").require(key)
        await resolver.set_value(key, e["default"], scope_type="global", reason="uji KF-T6 pulihkan", actor="uji")


@pytest.fixture(scope="module")
async def orang(akun, sesi, db):
    mgr = await akun("manager", entitas=("ent_ksc", "ent_kanda"))
    mgr2 = await akun("manager", entitas=("ent_ksc", "ent_kanda"))
    adm = await db.users.find_one({"email": "admin@kainnusantara.id"}, {"_id": 0})
    adm2 = await akun("admin", entitas=("ent_ksc", "ent_kanda"))
    return {"mgr": mgr, "mgr2": mgr2, "adm": adm, "adm2": adm2,
            "h_mgr": await sesi(mgr), "h_mgr2": await sesi(mgr2), "h_adm": await sesi(adm), "h_adm2": await sesi(adm2),
            "h_mgr_kanda": await sesi(mgr, entitas="ent_kanda")}


# ── PO (U2, U4) ──────────────────────────────────────────────────────────────────────────────────────────────────
async def _po(db, ent, pembuat, total=1000000):
    po = {"id": _id("po"), "po_number": f"PO-KFT6-{uuid.uuid4().hex[:5]}", "entity_id": ent,
          "status": "waiting_approval", "approval_status": "pending", "required_approval_role": "manager",
          "approval_chain": [{"level": 1, "label": "Manager", "required_role": "manager", "status": "pending",
                              "approved_by": "", "approved_by_id": "", "approved_at": ""}],
          "approval_level_current": 1, "created_by": pembuat["name"], "created_by_id": pembuat["id"],
          "supplier_id": "", "supplier_name": "Pemasok Uji", "items": [], "total_amount": total,
          "grand_total": total, "timeline": [], "created_at": now_iso(), "updated_at": now_iso()}
    await db.purchase_orders.insert_one(dict(po))
    return po


async def test_U02_po_per_pt(klien, db, orang):
    po_ksc = await _po(db, "ent_ksc", orang["mgr"])
    po_kanda = await _po(db, "ent_kanda", orang["mgr"])
    r = await klien.post(f"/api/purchase-orders/{po_ksc['id']}/approve", headers=orang["h_mgr"])
    assert (r.status_code, r.json().get("detail")) == (403, pesan("Persetujuan PO")), r.text
    await atur("kontrol.setujui_po.min_orang", "1", "ent_ksc")
    try:
        r = await klien.post(f"/api/purchase-orders/{po_ksc['id']}/approve", headers=orang["h_mgr"])
        assert r.status_code == 200, r.text
        r = await klien.post(f"/api/purchase-orders/{po_kanda['id']}/approve", headers=orang["h_mgr_kanda"])
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Persetujuan PO")), r.text
    finally:
        await cabut("kontrol.setujui_po.min_orang", "ent_ksc")


async def test_U04_admin_sendiri_dicatat_lalu_dimatikan(klien, db, orang):
    po1 = await _po(db, "ent_ksc", orang["adm"])
    r = await klien.post(f"/api/purchase-orders/{po1['id']}/approve", headers=orang["h_adm"])
    assert r.status_code == 200, r.text
    log = await db.approval_matrix_log.find({"doc_id": po1["id"]}, {"_id": 0}).to_list(10)
    assert [x["outcome"] for x in log] == ["diputuskan sendiri oleh admin"]
    await atur("kontrol.admin_boleh_sendiri", False, "")
    try:
        po2 = await _po(db, "ent_ksc", orang["adm"])
        r = await klien.post(f"/api/purchase-orders/{po2['id']}/approve", headers=orang["h_adm"])
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Persetujuan PO")), r.text
    finally:
        await cabut("kontrol.admin_boleh_sendiri", "")


# ── Uang muka (U3) ─────────────────────────────────────────────────────────────────────────────────────────────
async def _uang_muka(db, pemohon, total):
    doc = {"id": _id("ca"), "number": f"PD-KFT6-{uuid.uuid4().hex[:5]}", "entity_id": "ent_ksc",
           "status": "pending_atasan", "lines": [], "total_amount": total, "approvals": [],
           "created_by": pemohon["name"], "created_by_id": pemohon["id"], "created_at": now_iso()}
    await db.cash_advances.insert_one(dict(doc))
    return doc


async def test_U03_uang_muka_batas_nominal(klien, db, orang):
    kecil = await _uang_muka(db, orang["mgr"], 4000000)
    besar = await _uang_muka(db, orang["mgr"], 6000000)
    await atur("kontrol.uang_muka.batas_nominal", 5000000, "ent_ksc")
    try:
        r = await klien.post(f"/api/cash-advances/{kecil['id']}/approve", headers=orang["h_mgr"], json={"note": ""})
        assert r.status_code == 200, r.text
        r = await klien.post(f"/api/cash-advances/{besar['id']}/approve", headers=orang["h_mgr"], json={"note": ""})
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Uang muka / kasbon")), r.text
        r = await klien.post(f"/api/cash-advances/{besar['id']}/approve", headers=orang["h_mgr2"], json={"note": ""})
        assert r.status_code == 200, r.text
    finally:
        await cabut("kontrol.uang_muka.batas_nominal", "ent_ksc")


# ── Pengecualian retur (U5) ───────────────────────────────────────────────────────────────────────────────────────
async def _retur_dengan_pengecualian(db, pengaju):
    exc = {"id": _id("rex"), "kind": "window", "label": "Batas waktu", "reason": "uji", "attachment_ids": [],
           "status": "pending", "requested_by": pengaju["name"], "requested_by_id": pengaju["id"],
           "requested_at": now_iso()}
    ret = {"id": _id("sr"), "number": f"RJ-KFT6-{uuid.uuid4().hex[:5]}", "entity_id": "ent_ksc",
           "status": "pending_approval", "items": [], "exceptions": [exc], "created_at": now_iso()}
    await db.sales_returns.insert_one(dict(ret))
    return ret, exc


async def test_U05_pengecualian_retur_admin_tetap_dua_orang(klien, db, orang):
    ret, exc = await _retur_dengan_pengecualian(db, orang["adm"])
    url = f"/api/sales-returns/{ret['id']}/exceptions/{exc['id']}/decide"
    r = await klien.post(url, headers=orang["h_adm"], json={"approve": True, "note": "ok"})
    assert (r.status_code, r.json().get("detail")) == (403, pesan("Pengecualian retur")), r.text
    await atur("kontrol.admin_tetap_dua_orang", [], "")
    try:
        ret2, exc2 = await _retur_dengan_pengecualian(db, orang["adm"])
        r = await klien.post(f"/api/sales-returns/{ret2['id']}/exceptions/{exc2['id']}/decide",
                             headers=orang["h_adm"], json={"approve": True, "note": "ok"})
        assert r.status_code == 200, r.text
    finally:
        await cabut("kontrol.admin_tetap_dua_orang", "")


# ── Buka periode (U6) ─────────────────────────────────────────────────────────────────────────────────────────────
async def _usul_buka(db, pengusul, key):
    doc = {"id": _id("plu"), "entity_id": "ent_ksc", "period_type": "month", "period_key": key,
           "period_label": key, "start_date": f"{key}-01", "end_date": f"{key}-28", "closing_id": "",
           "reason": "koreksi uji", "status": "pending", "requested_by": pengusul["name"],
           "requested_by_id": pengusul["id"], "requested_at": now_iso(), "approved_by": None,
           "approved_by_id": None, "approved_at": None, "window_hours": None, "window_until": None,
           "reject_reason": "", "rejected_by": None, "rejected_at": None, "je_ids": [], "reclosed_at": None,
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.period_unlock_requests.insert_one(dict(doc))
    return doc


async def test_U06_buka_periode_bawaan_satu_orang(klien, db, orang):
    u1 = await _usul_buka(db, orang["mgr"], "2025-01")
    r = await klien.post(f"/api/finance/period-unlocks/{u1['id']}/approve", headers=orang["h_mgr"])
    assert r.status_code == 200, r.text
    await atur("kontrol.buka_periode.min_orang", "2", "ent_ksc")
    try:
        u2 = await _usul_buka(db, orang["mgr"], "2025-02")
        r = await klien.post(f"/api/finance/period-unlocks/{u2['id']}/approve", headers=orang["h_mgr"])
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Buka periode buku")), r.text
        r = await klien.post(f"/api/finance/period-unlocks/{u2['id']}/approve", headers=orang["h_mgr2"])
        assert r.status_code == 200, r.text
    finally:
        await cabut("kontrol.buka_periode.min_orang", "ent_ksc")


# ── Pengesahan gaji (U7) ──────────────────────────────────────────────────────────────────────────────────────────
async def _proses_gaji(db, pengaju, period):
    run = {"id": _id("prun"), "entity_id": "ent_ksc", "period": period, "status": "pending_approval",
           "submitted_by": pengaju["name"], "submitted_by_id": pengaju["id"], "submitted_at": now_iso(),
           "totals": {"gross": 8000000, "net": 7500000}, "created_at": now_iso()}
    await db.hr_payroll_runs.insert_one(dict(run))
    return run


async def test_U07_proses_gaji_per_pt(klien, db, orang):
    r1 = await _proses_gaji(db, orang["mgr"], "2026-01")
    r = await klien.post(f"/api/hr/payroll/runs/{r1['id']}/approve", headers=orang["h_mgr"])
    assert r.status_code == 200, r.text
    await atur("kontrol.proses_gaji.min_orang", "2", "ent_ksc")
    try:
        r2 = await _proses_gaji(db, orang["mgr"], "2026-02")
        r = await klien.post(f"/api/hr/payroll/runs/{r2['id']}/approve", headers=orang["h_mgr"])
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Pengesahan gaji")), r.text
        r = await klien.post(f"/api/hr/payroll/runs/{r2['id']}/approve", headers=orang["h_mgr2"])
        assert r.status_code == 200, r.text
    finally:
        await cabut("kontrol.proses_gaji.min_orang", "ent_ksc")


# ── Cuti (U8) ───────────────────────────────────────────────────────────────────────────────────────────────────
async def test_U08_cuti_milik_akun_pengaju(klien, db, orang):
    emp = {"id": _id("emp"), "name": orang["mgr"]["name"], "entity_id": "ent_ksc", "status": "active",
           "user_id": orang["mgr"]["id"], "created_at": now_iso()}
    await db.hr_employees.insert_one(dict(emp))
    lv = {"id": _id("leave"), "number": "LV-KFT6", "employee_id": emp["id"], "employee_name": emp["name"],
          "entity_id": "ent_ksc", "leave_type": "izin", "leave_label": "Izin", "date_from": "2026-03-02",
          "date_to": "2026-03-02", "days": 1, "work_dates": ["2026-03-02"], "reason": "uji", "status": "pending",
          "approver": "", "approved_at": "", "reject_reason": "", "created_by": "HR Uji", "created_at": now_iso()}
    await db.hr_leave_requests.insert_one(dict(lv))
    await atur("kontrol.cuti.min_orang", "2", "ent_ksc")
    try:
        r = await klien.post(f"/api/hr/leave-requests/{lv['id']}/approve", headers=orang["h_mgr"])
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Cuti")), r.text
        r = await klien.post(f"/api/hr/leave-requests/{lv['id']}/approve", headers=orang["h_mgr2"])
        assert r.status_code == 200, r.text
    finally:
        await cabut("kontrol.cuti.min_orang", "ent_ksc")


# ── Migrasi sakelar lama (U9, U10) ────────────────────────────────────────────────────────────────────────────────
async def _sisip_lama(db, key, value, scope_type, scope_id=""):
    """Keadaan SEBELUM migrasi: sakelar lama tersimpan (baris `config_values` langsung; sesudah migrasi kuncinya
    `not_used` sehingga tidak bisa ditulis lewat API)."""
    await db.config_values.insert_one({
        "id": _id("cfgv"), "key": key, "scope_type": scope_type, "scope_id": scope_id, "value": value,
        "effective_from": "2026-01-01T00:00:00+00:00", "reason": "uji KF-T6 keadaan lama", "changed_by": "uji",
        "created_at": "2026-01-01T00:00:00+00:00", "applied_at": "2026-01-01T00:00:00+00:00"})


async def _ulang_migrasi(db):
    from services import dual_control
    await db.system_settings.update_one({"scope": "__migrations__"}, {"$unset": {"kft6_kontrol": ""}})
    return dual_control


async def test_U09_migrasi_sakelar_pt(db):
    dc = await _ulang_migrasi(db)
    await _sisip_lama(db, "approval.matrix_sod", False, "entity", "ent_kanda")
    await dc.migrasi_sakelar_lama()
    k = "kontrol.permintaan_pembelian.min_orang"
    assert await resolver.value_of(k, {"entity_id": "ent_kanda"}) == "1"
    assert await resolver.value_of(k, {"entity_id": "ent_ksc"}) == "2"
    baris = await db.config_values.count_documents({})
    await dc.migrasi_sakelar_lama()
    assert await db.config_values.count_documents({}) == baris
    import config_registry as registry
    assert registry.require("approval.matrix_sod")["status"] == "not_used"
    assert registry.require("amendment.dual_control")["status"] == "not_used"
    for a in ("acc_desain", "acc_sample", "po_custom", "harga_khusus"):
        assert await resolver.value_of(f"kontrol.{a}.min_orang", {"entity_id": "ent_kanda"}) == "1"
    assert await resolver.value_of("kontrol.amandemen.min_orang", {"entity_id": "ent_kanda"}) == "2"
    for a in ("permintaan_pembelian", "acc_desain", "acc_sample", "po_custom", "harga_khusus"):
        await cabut(f"kontrol.{a}.min_orang", "ent_kanda")
    await db.config_values.delete_many({"key": "approval.matrix_sod"})


async def test_U10_migrasi_kontrol_ganda_grup(db):
    dc = await _ulang_migrasi(db)
    await _sisip_lama(db, "amendment.dual_control", False, "global")
    await dc.migrasi_sakelar_lama()
    assert await resolver.value_of("kontrol.amandemen.min_orang") == "1"
    from services import amendment_service
    assert (await amendment_service.policy_snapshot("ent_ksc"))["dual_control"] is False
    await cabut("kontrol.amandemen.min_orang", "")
    await db.config_values.delete_many({"key": "amendment.dual_control"})
    assert (await amendment_service.policy_snapshot("ent_ksc"))["dual_control"] is True


# ── Buka kembali tutup buku (U12) ─────────────────────────────────────────────────────────────────────────────────
async def test_U12_buka_kembali_dua_admin(klien, db, orang):
    c = await tutup_periode("ent_ksc", "2025-06")
    await atur("kontrol.buka_kembali_tutup_buku.min_orang", "2", "ent_ksc")
    try:
        url = f"/api/finance/closing/{c['id']}/reopen"
        r = await klien.post(url, headers=orang["h_adm"])
        assert r.status_code == 202, r.text
        assert r.json() == {"status": "menunggu_orang_kedua", "requested_by": orang["adm"]["name"]}
        rec = await db.period_closings.find_one({"id": c["id"]}, {"_id": 0})
        assert rec["status"] == "closed" and rec["reopen_request"]["by_id"] == orang["adm"]["id"]
        r = await klien.post(url, headers=orang["h_adm"])
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Buka kembali tutup buku")), r.text
        r = await klien.post(url, headers=orang["h_adm2"])
        assert r.status_code == 200, r.text
        rec = await db.period_closings.find_one({"id": c["id"]}, {"_id": 0})
        assert rec["status"] == "reopened" and "reopen_request" not in rec
    finally:
        await cabut("kontrol.buka_kembali_tutup_buku.min_orang", "ent_ksc")


# ── Jurnal manual (U13, U14) ──────────────────────────────────────────────────────────────────────────────────────
def _jurnal(nilai, ket="uji KF-T6"):
    return {"date": "2026-11-10", "description": ket, "entity_id": "ent_ksc",
            "lines": [{"account_code": "1-1100", "debit": nilai, "credit": 0, "description": ket},
                      {"account_code": "3-1000", "debit": 0, "credit": nilai, "description": ket}]}


async def test_U13_jurnal_manual_dua_orang(klien, db, orang):
    await atur("kontrol.jurnal_manual.min_orang", "2", "ent_ksc")
    try:
        je_awal = await db.journal_entries.count_documents({})
        kas0, modal0 = await saldo_akun("1-1100", "ent_ksc"), await saldo_akun("3-1000", "ent_ksc")
        r = await klien.post("/api/gl/journal", headers=orang["h_mgr"], json=_jurnal(1000000))
        assert r.status_code == 202, r.text
        assert r.json()["status"] == "menunggu_orang_kedua"
        pid = r.json()["proposal_id"]
        assert pid.startswith("jprop_")
        assert await db.journal_entries.count_documents({}) == je_awal
        assert (await saldo_akun("1-1100", "ent_ksc"), await saldo_akun("3-1000", "ent_ksc")) == (kas0, modal0)
        r = await klien.get("/api/gl/journal-proposals", headers=orang["h_mgr2"], params={"status": "pending"})
        assert r.status_code == 200 and pid in [x["id"] for x in r.json()["items"]], r.text
        r = await klien.post(f"/api/gl/journal-proposals/{pid}/approve", headers=orang["h_mgr"])
        assert (r.status_code, r.json().get("detail")) == (403, pesan("Jurnal manual")), r.text
        r = await klien.post(f"/api/gl/journal-proposals/{pid}/approve", headers=orang["h_mgr2"])
        assert r.status_code == 200, r.text
        je = await db.journal_entries.find_one({"id": r.json()["journal_id"]}, {"_id": 0})
        assert (je["status"], je["created_by"], je["approved_by"]) == ("posted", orang["mgr"]["name"],
                                                                      orang["mgr2"]["name"])
        assert await db.journal_entries.count_documents({}) == je_awal + 1
        assert await saldo_akun("1-1100", "ent_ksc") - kas0 == 1000000
        assert abs(await saldo_akun("3-1000", "ent_ksc") - modal0) == 1000000
        prop = await db.journal_proposals.find_one({"id": pid}, {"_id": 0})
        assert (prop["status"], prop["journal_id"], prop["decided_by_id"]) == ("posted", je["id"], orang["mgr2"]["id"])
        r = await klien.post(f"/api/gl/journal-proposals/{pid}/approve", headers=orang["h_mgr2"])
        assert (r.status_code, r.json().get("detail")) == (409, "Usulan jurnal ini sudah diputuskan."), r.text
        # tolak: alasan wajib
        r = await klien.post("/api/gl/journal", headers=orang["h_mgr"], json=_jurnal(250000))
        pid2 = r.json()["proposal_id"]
        r = await klien.post(f"/api/gl/journal-proposals/{pid2}/reject", headers=orang["h_mgr2"], json={"reason": ""})
        assert (r.status_code, r.json().get("detail")) == (400, "Alasan penolakan wajib diisi."), r.text
        r = await klien.post(f"/api/gl/journal-proposals/{pid2}/reject", headers=orang["h_mgr2"],
                             json={"reason": "Akun salah"})
        assert r.status_code == 200 and r.json()["status"] == "rejected", r.text
    finally:
        await cabut("kontrol.jurnal_manual.min_orang", "ent_ksc")


async def test_U14_jurnal_manual_batas_nominal(klien, db, orang):
    await atur("kontrol.jurnal_manual.batas_nominal", 10000000, "ent_ksc")
    try:
        r = await klien.post("/api/gl/journal", headers=orang["h_mgr"], json=_jurnal(5000000))
        assert r.status_code == 200 and r.json()["status"] == "posted", r.text
        r = await klien.post("/api/gl/journal", headers=orang["h_mgr"], json=_jurnal(15000000))
        assert r.status_code == 202 and r.json()["proposal_id"].startswith("jprop_"), r.text
    finally:
        await cabut("kontrol.jurnal_manual.batas_nominal", "ent_ksc")


# ── U15 statik ────────────────────────────────────────────────────────────────────────────────────────────────────
BERKAS_B = ["routers/purchase_orders.py", "routers/vendor_bills.py", "routers/landed_cost.py",
            "services/contra_bon_service.py", "services/marketing_cost_service.py",
            "services/interco_return_service.py", "services/period_unlock_service.py",
            "services/makloon_loss_service.py", "services/return_exception_service.py",
            "services/design_ownership_service.py", "services/initial_registration_service.py"]


def _kode(teks: str) -> str:
    """Tanpa komentar baris (`# …`)."""
    return "\n".join(ln.split("#", 1)[0] for ln in teks.splitlines())


def test_U15_statik():
    from config_catalog_kontrol import KONTROL_AKSI
    lama = re.compile(r"tidak boleh menyetujui|tidak boleh memutus|created_by_id\"?\]?\)? ?== ?actor|"
                      r"== ?actor\.get\(\"id\"\)|admin_override|sod_blocked")
    sisa = {f: lama.findall(_kode((BACKEND / f).read_text(encoding="utf-8"))) for f in BERKAS_B}
    assert {f: s for f, s in sisa.items() if s} == {}
    semua = "\n".join(_kode(p.read_text(encoding="utf-8")) for d in ("routers", "services")
                      for p in (BACKEND / d).glob("*.py"))
    # Empat tahap matriks (ACC desain/sample, PO custom, PR) dipasang lewat `approval_matrix_service.guard` dengan peta
    # `STAGE_AKSI` (literal aksi ada di sana); sisanya `tolak_bila_pelaku_sama("<aksi>"` langsung.
    matriks = _kode((BACKEND / "services/approval_matrix_service.py").read_text(encoding="utf-8"))
    # Kas & Bank 3 — aksi yang kuncinya sudah terdaftar tetapi titik pasangnya dibangun tugas berikutnya
    # (`_BELUM_DIPASANG`, kunci bertanda tidak dipakai). Daftar itu hanya bisa menyempit: aksi yang sudah punya titik
    # atau sudah dipasang di kode tetapi masih di daftar = merah.
    from config_catalog_kontrol import _BELUM_DIPASANG
    import config_registry as registry
    tanpa = [a["aksi"] for a in KONTROL_AKSI if f'tolak_bila_pelaku_sama("{a["aksi"]}"' not in semua
             and f'"{a["aksi"]}"' not in matriks]
    assert tanpa == sorted(_BELUM_DIPASANG, key=[a["aksi"] for a in KONTROL_AKSI].index)
    for a in KONTROL_AKSI:
        if a["aksi"] in _BELUM_DIPASANG:
            assert not a["titik"], a["aksi"]   # sudah punya titik → hapus dari `_BELUM_DIPASANG`
            assert registry.require(f"kontrol.{a['aksi']}.min_orang")["status"] == "not_used", a["aksi"]
            continue
        assert a["titik"], a["aksi"]          # katalog menyebut titik pasangnya (consumers registry)
