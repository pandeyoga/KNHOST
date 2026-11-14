"""KP-T7 — pengingat dan penjadwal yang bisa diatur: selang menit, penerima, dan ambang per PT
(docs/blueprint/unit/KP-T7.md). U5 (setara) di `test_KPT7_setara.py` (basis data sendiri).

Persiapan bersama: seed lingkungan B; akun admin (`kepala_admin`); penjadwal dinyalakan dengan PEMICU TIRUAN
(`_Penjadwal`: `_apply_jobs` mendaftarkan pemicu APScheduler asli ke objek tiruan — diperiksa lewat daftar pemicu, bukan
menunggu waktu). Fixture sisip: tagihan pemasok, pelanggan + pesanan + surat jalan, notifikasi lama, posting konten,
antrean label, permintaan desain. Alur lewat API: `PUT /api/scheduler/settings`, `PUT /api/config/values`.
Tiap uji memakai id dokumen sendiri dan mengembalikan pengaturan yang diubahnya (`_pulihkan`).
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest

pytestmark = pytest.mark.anyio

ROOT = Path(__file__).resolve().parents[2]
SKRIP = ROOT / "scripts/migrate_kpt7_jadwal.py"
KSC, KANDA = "ent_ksc", "ent_kanda"

KUNCI_BARU = ["notif.ap_due_soon_days", "notif.wo_released_stale_days", "notif.wo_draft_stale_days",
              "notif.warehouse_task_stale_days", "notif.ar_due_soon_offsets", "notif.po_arrival_lookback_hours",
              "notif.max_alerts_per_run", "notif.turn_stale_days", "notif.content_reminder_window_minutes",
              "notif.content_on_time_grace_minutes", "notif.campaign_budget_near_pct", "notif.printer_stuck_minutes",
              "inventory.drift_critical_multiplier", "approval.reminder_max_listed", "rnd.design_due_soon_days",
              "notif.reminder_recipients", "notif.escalation_chain", "notif.wa_broadcast_roles",
              "notif.wa_pic_number"]


# ── pembantu ───────────────────────────────────────────────────────────────────────────────────────────────────────
class _Penjadwal:
    """Pemicu tiruan: menyimpan pemicu yang didaftarkan `_apply_jobs` (APScheduler asli tidak dinyalakan)."""
    running = True

    def __init__(self) -> None:
        self.pemicu: Dict[str, Any] = {}

    def add_job(self, fn, trigger=None, id=None, **kw):  # noqa: A002 — tanda tangan APScheduler
        self.pemicu[id] = trigger

    def remove_job(self, job_id):
        self.pemicu.pop(job_id)

    def get_job(self, job_id):
        return None

    def shutdown(self, wait=False):
        self.running = False


@pytest.fixture
async def penjadwal(db, monkeypatch):
    from services import scheduler_service as sch
    p = _Penjadwal()
    monkeypatch.setattr(sch, "_scheduler", p)
    await db.system_settings.update_one({"scope": "alerts"}, {"$unset": {"jobs": ""}})
    await sch._apply_jobs()
    return p


def _menit(p: _Penjadwal, job_id: str) -> float:
    return p.pemicu[job_id].interval.total_seconds() / 60


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


def _isi(key, value, scope_type="global", scope_id="", reason="uji KP-T7"):
    return {"items": [{"key": key, "value": value, "scope_type": scope_type, "scope_id": scope_id, "reason": reason}]}


async def _simpan(klien, h, key, value, scope_type="global", scope_id=""):
    r = await klien.put("/api/config/values", headers=h, json=_isi(key, value, scope_type, scope_id))
    assert r.status_code == 200, r.text
    return r


async def _pulihkan(klien, h, key, *pt):
    for eid in pt:
        r = await klien.post("/api/config/values/clear", headers=h,
                             json={"key": key, "scope_type": "entity", "scope_id": eid, "reason": "pulihkan"})
        assert r.status_code == 200, r.text
    r = await klien.post("/api/config/values/reset", headers=h,
                         json={"key": key, "scope_type": "global", "reason": "pulihkan"})
    assert r.status_code == 200, r.text


async def _notif(db, **q) -> List[Dict[str, Any]]:
    return await db.notifications.find(q, {"_id": 0}).to_list(None)


def _tgl(d: int) -> str:
    from services.analytics_time import now_wib
    return (now_wib().date() + timedelta(days=d)).isoformat()


async def _tagihan(db, bid: str, entity_id: str, hari: int) -> None:
    """Tagihan posted, pemasok tanpa termin → jatuh tempo = tanggal tagihan (`hari` dari hari ini, WIB)."""
    await db.vendor_bills.insert_one({"id": bid, "bill_number": f"VB-{bid}", "bill_date": _tgl(hari),
                                      "grand_total": 1_000_000, "amount_paid": 0, "supplier_id": "kpt7_sup",
                                      "supplier_name": "Pemasok KP-T7", "entity_id": entity_id, "status": "posted"})


def _job(job_id: str, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return next(j for j in rows if j["id"] == job_id)


# ── U1–U4 — selang menit ───────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT7_U1_selang_menit_disimpan_dan_dipakai_pemicu(klien, kepala_admin, penjadwal):
    assert _menit(penjadwal, "reservation_expiry") == 30
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"jobs": {"reservation_expiry": {"interval_minutes": 120}}})
    assert r.status_code == 200, r.text
    assert _menit(penjadwal, "reservation_expiry") == 120          # reschedule() memakai nilai baru
    r = await klien.get("/api/scheduler/jobs", headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = _job("reservation_expiry", r.json()["jobs"])
    assert (j["interval_unit"], j["interval_value"], j["schedule_label"]) == ("menit", 120, "Setiap 120 menit")
    assert j["locked"] is False
    # job bersatuan jam & harian
    oj = _job("ops_stalled", r.json()["jobs"])
    assert (oj["interval_unit"], oj["interval_value"], oj["schedule_label"]) == ("jam", 4, "Setiap 4 jam")
    assert (_job("ap_due", r.json()["jobs"])["interval_unit"], _job("ap_due", r.json()["jobs"])["interval_value"]) \
        == ("", None)


async def test_KPT7_U2_job_menit_menolak_selang_jam(klien, kepala_admin, penjadwal, db):
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"jobs": {"reservation_expiry": {"interval_hours": 2}}})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Jadwal “Kedaluwarsa Reservasi Pesanan” diatur dalam menit."
    assert _menit(penjadwal, "reservation_expiry") == 30
    doc = await db.system_settings.find_one({"scope": "alerts"}, {"_id": 0}) or {}
    assert "reservation_expiry" not in (doc.get("jobs") or {})


async def test_KPT7_U3_job_jam_dan_job_terkunci_menolak(klien, kepala_admin, penjadwal):
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"jobs": {"ops_stalled": {"interval_minutes": 10}}})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Jadwal “Tugas Gudang Tertunda” diatur dalam jam."
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"jobs": {"rfid_gate_txn_retry": {"interval_minutes": 5}}})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Jadwal “Ulang Transaksi Gate RFID” tidak bisa diubah dari layar."
    assert _menit(penjadwal, "rfid_gate_txn_retry") == 2 and _menit(penjadwal, "ops_stalled") == 240
    # tambahan: job harian; job bersatuan jam tetap menerima jam; kedua job gerbang ditandai terkunci
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"jobs": {"ap_due": {"interval_hours": 3}}})
    assert r.status_code == 400, r.text
    assert _detail(r) == "Jadwal “Hutang Supplier Jatuh Tempo (AP)” diatur dengan jam dan menit harian."
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin,
                        json={"jobs": {"ops_stalled": {"interval_hours": 6}}})
    assert r.status_code == 200, r.text
    assert _menit(penjadwal, "ops_stalled") == 360
    rows = (await klien.get("/api/scheduler/jobs", headers=kepala_admin)).json()["jobs"]
    assert sorted(j["id"] for j in rows if j["locked"]) == ["rfid_gate_txn_retry", "rfid_reader_health_watch"]


def _skrip():
    spec = importlib.util.spec_from_file_location("migrate_kpt7_jadwal", SKRIP)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def test_KPT7_U4_migrasi_membuang_sisa_selang_jam(db, penjadwal):
    from services import scheduler_service as sch
    # fixture sisip: sisa lama layar (interval_hours untuk job bersatuan menit) + satu nilai jam sah (tidak disentuh)
    await db.system_settings.update_one(
        {"scope": "alerts"}, {"$set": {"jobs.turn_scan": {"enabled": True, "interval_hours": 4},
                                       "jobs.event_scan": {"interval_hours": 6}}}, upsert=True)
    await sch._apply_jobs()
    assert _menit(penjadwal, "turn_scan") == 5                       # sebelum: jam tersimpan tidak dipakai
    mod = _skrip()
    assert mod.main(["--salah"]) == 2                                # argumen tak dikenal: keluar sebelum basis data
    assert mod.main(["--apply", "--dry-run"]) == 2
    lapor = await mod.jalankan(tulis=False)
    assert [s["job_id"] for s in lapor["sisa_interval_hours"]] == ["turn_scan"]
    cetak: list = []
    mod._cetak(lapor, cetak.append)
    print("\n".join(cetak))
    doc = await db.system_settings.find_one({"scope": "alerts"}, {"_id": 0})
    assert doc["jobs"]["turn_scan"]["interval_hours"] == 4           # lapor: tidak menulis
    tulis = await mod.jalankan(tulis=True)
    assert (tulis["mode"], tulis["ditulis"]) == ("tulis", 1)
    doc = await db.system_settings.find_one({"scope": "alerts"}, {"_id": 0})
    assert "interval_hours" not in doc["jobs"]["turn_scan"] and doc["jobs"]["turn_scan"]["enabled"] is True
    assert doc["jobs"]["event_scan"] == {"interval_hours": 6}
    await sch._apply_jobs()
    assert _menit(penjadwal, "turn_scan") == 5                       # sesudah: sama
    assert (await mod.jalankan(tulis=True))["ditulis"] == 0          # ulang tanpa perubahan


# ── U6–U7 — ambang & penerima per PT ───────────────────────────────────────────────────────────────────────────────
async def test_KPT7_U6_ambang_hutang_per_pt(klien, kepala_admin, db):
    from services import alert_service
    await _tagihan(db, "u6_ksc", KSC, 10)
    await _tagihan(db, "u6_kanda", KANDA, 10)
    await _simpan(klien, kepala_admin, "notif.ap_due_soon_days", 14, "entity", KANDA)
    await db.notifications.delete_many({})
    await alert_service.job_ap_due()
    refs = {n["ref"] for n in await _notif(db, type="ap_due")}
    # 10 ≤ 14 (Kanda) → diingatkan; 10 > 7 (KSC, bawaan) → tidak
    assert "ap_due:u6_kanda" in refs and "ap_due:u6_ksc" not in refs
    await _pulihkan(klien, kepala_admin, "notif.ap_due_soon_days", KANDA)
    await db.vendor_bills.delete_many({"id": {"$in": ["u6_ksc", "u6_kanda"]}})


async def test_KPT7_U7_penerima_pemegang_izin_per_pt(klien, kepala_admin, db, akun, peran_tanpa_acuan):
    from services import alert_service
    rid = await peran_tanpa_acuan({"vendor_bill": ["view", "pay"]}, label="Bayar Tagihan KP-T7")
    orang = await akun(rid, entitas=(KANDA,))
    await _tagihan(db, "u7_kanda", KANDA, 2)
    await _tagihan(db, "u7_ksc", KSC, 2)
    await _simpan(klien, kepala_admin, "notif.reminder_recipients",
                  [{"reminder": "ap_due", "mode": "izin", "roles": [], "permission": "vendor_bill.pay"}],
                  "entity", KANDA)
    await db.notifications.delete_many({})
    await alert_service.job_ap_due()
    kanda = [n for n in await _notif(db, type="ap_due") if n["ref"].split("#")[0] == "ap_due:u7_kanda"]
    ksc = [n for n in await _notif(db, type="ap_due") if n["ref"] == "ap_due:u7_ksc"]
    assert orang["id"] in {n["recipient_user"] for n in kanda}, kanda
    assert all(n["recipient_role"] == "" and n["recipient_user"] for n in kanda), kanda
    assert not any(n["recipient_role"] == "manager" for n in kanda)
    # pemegang izin lain di PT itu (Admin & Manajer seed memegang vendor_bill.pay dan bertugas di Kanda)
    assert {"user_admin_01", "user_manager_01"} <= {n["recipient_user"] for n in kanda}
    assert [(n["recipient_role"], n["recipient_user"]) for n in ksc] == [("manager", None)]
    r = await klien.get("/api/scheduler/jobs", headers=await _sesi_kanda(kepala_admin))
    assert _job("ap_due", r.json()["jobs"])["recipients"] == "Pemegang izin Tagihan Supplier — Bayar"
    r = await klien.get("/api/scheduler/jobs", headers=kepala_admin)
    ap = _job("ap_due", r.json()["jobs"])
    assert ap["recipients"] == "Manajer"
    assert [(t["key"], t["value"], t["unit"]) for t in ap["thresholds"]] == [
        ("notif.ap_due_soon_days", 7, "hari"), ("notif.max_alerts_per_run", 40, "peringatan")]
    await _pulihkan(klien, kepala_admin, "notif.reminder_recipients", KANDA)
    await db.vendor_bills.delete_many({"id": {"$in": ["u7_ksc", "u7_kanda"]}})


async def _sesi_kanda(h: Dict[str, str]) -> Dict[str, str]:
    return {**h, "X-Entity-Id": KANDA}


# ── U8 — pemeriksaan tabel penerima ────────────────────────────────────────────────────────────────────────────────
async def test_KPT7_U8_peran_tak_dikenal_ditolak(klien, kepala_admin, db):
    sebelum = await db.config_values.count_documents({"key": "notif.reminder_recipients"})
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(
        "notif.reminder_recipients", [{"reminder": "ap_due", "mode": "peran", "roles": ["direktur"]}]))
    assert r.status_code == 400, r.text
    assert _detail(r) == "Peran “direktur” tidak ada."
    # tambahan: pesan lain spesifikasi + rantai eskalasi & peran siaran memakai pesan peran yang sama
    for nilai, pesan in (
            ([{"reminder": "gaji", "mode": "peran", "roles": ["manager"]}], "Pengingat “gaji” tidak dikenal."),
            ([{"reminder": "ap_due", "mode": "izin", "permission": "vendor_bill.terbang"}],
             "Izin “vendor_bill.terbang” tidak ada."),
            ([{"reminder": "ap_due", "mode": "peran", "roles": []}], "Baris 1: pilih paling sedikit satu peran.")):
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("notif.reminder_recipients", nilai))
        assert (r.status_code, _detail(r)) == (400, pesan), r.text
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("notif.escalation_chain", {"warehouse": "direktur"}))
    assert (r.status_code, _detail(r)) == (400, "Peran “direktur” tidak ada."), r.text
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("notif.wa_broadcast_roles", ["admin", "direktur"]))
    assert (r.status_code, _detail(r)) == (400, "Peran “direktur” tidak ada."), r.text
    assert await db.config_values.count_documents({"key": "notif.reminder_recipients"}) == sebelum


# ── U9 — hari pengingat piutang ────────────────────────────────────────────────────────────────────────────────────
async def test_KPT7_U9_hari_pengingat_piutang(klien, kepala_admin, db):
    from services import alert_ops_service
    now = datetime.now(timezone.utc)
    await db.customers.insert_one({"id": "u9_c", "name": "Pelanggan U9", "entity_id": KSC, "assigned_sales_id": "",
                                   "payment_profile": {}, "status": "active"})
    so = {"status": "confirmed", "payment_term_days": 30, "payments": [], "customer_id": "u9_c",
          "customer_name": "Pelanggan U9", "grand_total": 900_000, "entity_id": KSC}
    await db.sales_orders.insert_many([{**so, "id": "u9_so7", "number": "SO-U9-7"},
                                       {**so, "id": "u9_so3", "number": "SO-U9-3"}])
    # surat jalan pertama + termin 30 hari → jatuh tempo 7 hari lagi / 3 hari lagi
    await db.shipments.insert_many([
        {"id": "u9_sj7", "order_id": "u9_so7", "status": "delivered", "created_at": (now - timedelta(days=23)).isoformat()},
        {"id": "u9_sj3", "order_id": "u9_so3", "status": "delivered", "created_at": (now - timedelta(days=27)).isoformat()}])
    await _simpan(klien, kepala_admin, "notif.ar_due_soon_offsets", [-7, 0])
    await db.notifications.delete_many({})
    await alert_ops_service.job_ar_due_soon()
    refs = {n["ref"].split("#")[0] for n in await _notif(db, type="ar_due_soon")}
    assert "ar_due_team:u9_so7:H-7" in refs
    assert not any(r.startswith("ar_due_team:u9_so3") or r.startswith("ar_due:u9_so3") for r in refs), refs
    # bawaan [-3, -1, 0, 1] → kebalikannya
    await _pulihkan(klien, kepala_admin, "notif.ar_due_soon_offsets")
    await db.notifications.delete_many({})
    await alert_ops_service.job_ar_due_soon()
    refs = {n["ref"].split("#")[0] for n in await _notif(db, type="ar_due_soon")}
    assert "ar_due_team:u9_so3:H-3" in refs and not any(r.startswith("ar_due_team:u9_so7") for r in refs)
    # nilai butir di luar −30…30 ditolak
    r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi("notif.ar_due_soon_offsets", [-45]))
    assert r.status_code == 400 and "butir 1" in _detail(r), r.text


# ── U10 — rantai eskalasi ──────────────────────────────────────────────────────────────────────────────────────────
async def test_KPT7_U10_rantai_eskalasi_dari_pengaturan(klien, kepala_admin, db):
    from services import escalation_service
    rantai = {"sales": "manager", "warehouse": "warehouse_admin", "manager": "admin", "all": "admin", "": "admin"}
    await _simpan(klien, kepala_admin, "notif.escalation_chain", rantai)
    await db.notifications.delete_many({})
    lama = (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat()
    await db.notifications.insert_one({"id": "u10_n", "type": "ops_stalled", "ref": "u10:gudang", "title": "Tugas U10",
                                       "body": "u10", "severity": "warning", "recipient_role": "warehouse",
                                       "recipient_user": None, "entity_id": KSC, "read": False, "created_at": lama,
                                       "link": "operations", "dedupe_key": ""})
    await escalation_service.job_escalation_scan()
    esk = await _notif(db, type="escalation", escalated_from="u10_n")
    assert [e["recipient_role"] for e in esk] == ["warehouse_admin"], esk
    await _pulihkan(klien, kepala_admin, "notif.escalation_chain")


# ── U11 — nomor PIC WhatsApp per PT ────────────────────────────────────────────────────────────────────────────────
async def test_KPT7_U11_nomor_pic_per_pt(klien, kepala_admin, db):
    from services import wa_alert_service as wa
    r = await klien.put("/api/scheduler/settings", headers=kepala_admin, json={"wa": {"pic_number": "081111111111"}})
    assert r.status_code == 200, r.text
    await _simpan(klien, kepala_admin, "notif.wa_pic_number", "081222222222", "entity", KANDA)
    cfg = (await wa.raw_settings())["wa"]

    async def _pic(eid):
        out = await wa.resolve_recipients({"entity_id": eid, "recipient_role": "manager"}, cfg)
        return [x["phone"] for x in out if x["role"] == "pic"]

    assert await _pic(KANDA) == ["6281222222222"]
    assert await _pic(KSC) == ["6281111111111"]
    r = await klien.put("/api/config/values", headers=kepala_admin,
                        json=_isi("notif.wa_pic_number", "abc", "entity", KANDA))
    assert (r.status_code, _detail(r)) == (400, "Nomor WhatsApp PIC tidak valid. Contoh: 081234567890."), r.text
    await _pulihkan(klien, kepala_admin, "notif.wa_pic_number", KANDA)


# ── U12 — wewenang dari izin ───────────────────────────────────────────────────────────────────────────────────────
async def test_KPT7_U12_wewenang_dari_izin(klien, akun, sesi, peran_manajer_kosong, peran_tanpa_acuan,
                                           kepala_admin):
    kosong = await akun(await peran_manajer_kosong())
    r = await klien.put("/api/config/values", headers=await sesi(kosong),
                        json=_isi("notif.ap_due_soon_days", 9, "entity", KSC))
    assert r.status_code == 403, r.text
    assert "notif" not in _detail(r) and "scheduler" not in _detail(r)
    rid = await peran_tanpa_acuan({"scheduler": ["view", "configure"]}, label="Atur Penjadwal KP-T7")
    r = await klien.put("/api/config/values", headers=await sesi(await akun(rid)),
                        json=_isi("notif.ap_due_soon_days", 9, "entity", KSC))
    assert r.status_code == 200, r.text
    await _pulihkan(klien, kepala_admin, "notif.ap_due_soon_days", KSC)


# ── U13 — putaran t1_config untuk 19 kunci baru ────────────────────────────────────────────────────────────────────
def _contoh(e: Dict[str, Any]):
    """(nilai grup, nilai PT, nilai tak sah, bentuk tersimpan) — mengikuti `t1_config.py` (alt_value/bad_value)."""
    k, t = e["key"], e["type"]
    if k == "notif.ar_due_soon_offsets":
        return [-5, 0], [-2], [99], lambda v: sorted(set(v))
    if k == "notif.reminder_recipients":
        return ([{"reminder": "ap_due", "mode": "peran", "roles": ["finance"], "permission": ""}],
                [{"reminder": "ap_due", "mode": "izin", "roles": [], "permission": "vendor_bill.pay"}],
                "bukan-daftar", lambda v: v)
    if k == "notif.escalation_chain":
        return ({"sales": "sales_admin", "warehouse": "manager", "manager": "admin", "all": "admin", "": "admin"},
                None, "bukan-daftar", lambda v: v)
    if k == "notif.wa_broadcast_roles":
        return ["admin"], None, "bukan-daftar", lambda v: v
    if k == "notif.wa_pic_number":
        return "081234567890", "081298765432", "abc", lambda v: "62" + v[1:]
    d, hi = e["default"], e["max"]
    v1 = d + 1 if d + 1 <= hi else d - 1
    v2 = v1 + 1 if v1 + 1 <= hi else v1 - 1
    return v1, v2, hi + 1000000, lambda v: v


async def test_KPT7_U13_putaran_t1_config_19_kunci(klien, kepala_admin):
    import config_registry as registry
    from services.config_resolver import value_of
    entries = [registry.require(k) for k in KUNCI_BARU]
    assert len(entries) == 19
    assert all(e["permission"] == ["scheduler", "configure"] and e["status"] == "active" for e in entries)
    for e in entries:
        key = e["key"]
        v1, v2, salah, bentuk = _contoh(e)
        await _simpan(klien, kepala_admin, key, v1)
        assert await value_of(key) == bentuk(v1), key
        r = await klien.get("/api/config/effective", headers=kepala_admin, params={"q": key})
        assert next(i for i in r.json()["items"] if i["key"] == key)["value"] == bentuk(v1), key
        if "entity" in e["scopes"]:
            await _simpan(klien, kepala_admin, key, v2, "entity", KANDA)
            assert await value_of(key, {"entity_id": KANDA}) == bentuk(v2), key
            assert await value_of(key, {"entity_id": KSC}) == bentuk(v1), key       # PT lain tidak ikut
            await _pulihkan(klien, kepala_admin, key, KANDA)
        else:
            r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(key, v1, "entity", KANDA))
            assert r.status_code == 400, (key, r.text)                                 # lapisan PT tidak didukung
        r = await klien.put("/api/config/values", headers=kepala_admin, json=_isi(key, salah))
        assert r.status_code == 400, (key, r.text)
        await _pulihkan(klien, kepala_admin, key)
        assert await value_of(key) == e["default"], key


# ── Tambahan (02 §2.4 butir 2: nilai A → perilaku A, nilai B → perilaku B, PT lain tetap) ──────────────────────────
async def test_KPT7_U15_perintah_kerja_dan_tugas_gudang_per_pt(klien, kepala_admin, db):
    from services import alert_service
    now = datetime.now(timezone.utc)
    wo = {"status": "released", "released_at": (now - timedelta(days=5)).isoformat(), "material_plan": [],
          "output_name": "Kain", "planned_qty": 1, "output_unit": "m", "warehouse_name": "G"}
    await db.mfg_work_orders.insert_many([{**wo, "id": "u15_wo_ksc", "wo_number": "WO-U15-1", "entity_id": KSC},
                                          {**wo, "id": "u15_wo_kanda", "wo_number": "WO-U15-2", "entity_id": KANDA}])
    t = {"flow_type": "outbound", "status": "pending", "created_at": (now - timedelta(days=3)).isoformat()}
    await db.wms_tasks.insert_many([{**t, "id": "u15_t_ksc", "warehouse_id": "u15_whs", "entity_id": KSC},
                                    {**t, "id": "u15_t_kanda", "warehouse_id": "u15_whk", "entity_id": KANDA}])
    await _simpan(klien, kepala_admin, "notif.wo_released_stale_days", 10, "entity", KANDA)
    await _simpan(klien, kepala_admin, "notif.warehouse_task_stale_days", 5, "entity", KANDA)
    await db.notifications.delete_many({})
    await alert_service.job_production_stalled()
    await alert_service.job_ops_stalled()
    refs = {n["ref"] for n in await _notif(db)}
    assert "wo_stalled:u15_wo_ksc" in refs and "wo_stalled:u15_wo_kanda" not in refs        # 5 > 3; 5 < 10
    assert "task_stalled:u15_whs:outbound" in refs and "task_stalled:u15_whk:outbound" not in refs   # 3 > 2; 3 < 5
    await _pulihkan(klien, kepala_admin, "notif.wo_released_stale_days", KANDA)
    await _pulihkan(klien, kepala_admin, "notif.warehouse_task_stale_days", KANDA)
    await db.mfg_work_orders.delete_many({"id": {"$regex": "^u15_"}})
    await db.wms_tasks.delete_many({"id": {"$regex": "^u15_"}})


async def test_KPT7_U16_jendela_barang_po_dan_batas_per_jalan(klien, kepala_admin, db):
    from services import alert_ops_service, alert_service
    now = datetime.now(timezone.utc)
    t = {"flow_type": "inbound", "source_type": "purchase_order", "status": "completed",
         "completed_at": (now - timedelta(hours=2)).isoformat(), "po_number": "PO-U16"}
    await db.wms_tasks.insert_many([{**t, "id": "u16_ksc", "entity_id": KSC},
                                    {**t, "id": "u16_kanda", "entity_id": KANDA}])
    await _simpan(klien, kepala_admin, "notif.po_arrival_lookback_hours", 1, "entity", KANDA)
    await db.notifications.delete_many({})
    await alert_ops_service.job_po_arrival()
    refs = {n["ref"] for n in await _notif(db, type="po_arrival")}
    assert "po_arrival:u16_ksc" in refs and "po_arrival:u16_kanda" not in refs               # 2 jam ≤ 24; 2 jam > 1
    await _pulihkan(klien, kepala_admin, "notif.po_arrival_lookback_hours", KANDA)
    await db.wms_tasks.delete_many({"id": {"$regex": "^u16_"}})
    for i in range(3):
        await _tagihan(db, f"u16_vb{i}", KSC, 1)
    await _simpan(klien, kepala_admin, "notif.max_alerts_per_run", 1)
    await db.notifications.delete_many({})
    res = await alert_service.job_ap_due()
    assert res["created"] == 1 and len(await _notif(db, type="ap_due")) == 1
    await _pulihkan(klien, kepala_admin, "notif.max_alerts_per_run")
    await db.vendor_bills.delete_many({"id": {"$regex": "^u16_"}})


async def test_KPT7_U17_giliran_konten_dan_toleransi_per_pt(klien, kepala_admin, db, monkeypatch):
    from services import marketing_ext, marketing_service, turn_notification_service as turn
    # giliran: ambang dokumen diam dibaca per PT dokumen
    await db.sales_orders.insert_many([
        {"id": "u17_so_ksc", "number": "SO-U17-1", "status": "waiting_approval", "entity_id": KSC,
         "updated_at": "2026-01-01T00:00:00+00:00"},
        {"id": "u17_so_kanda", "number": "SO-U17-2", "status": "waiting_approval", "entity_id": KANDA,
         "updated_at": "2026-01-01T00:00:00+00:00"}])
    await _simpan(klien, kepala_admin, "notif.turn_stale_days", 30, "entity", KANDA)
    dipakai: Dict[str, int] = {}

    async def _catat(coll, doc, *, stale_days=0):
        dipakai[doc.get("id")] = stale_days
        return 0
    monkeypatch.setattr(turn, "notify_turn", _catat)
    await turn.scan()
    assert (dipakai["u17_so_ksc"], dipakai["u17_so_kanda"]) == (7, 30)
    await _pulihkan(klien, kepala_admin, "notif.turn_stale_days", KANDA)
    # pengingat tayang: posting 90 menit lagi → diingatkan bila jarak PT 120, tidak bila bawaan 60
    wib = timezone(timedelta(hours=7))
    jam = (datetime.now(wib) + timedelta(minutes=90)).strftime("%Y-%m-%dT%H:%M")
    post = {"status": "scheduled", "publish_at": jam, "reminder_sent_at": "", "title": "Post U17", "platforms": []}
    await db.mkt_posts.insert_many([{**post, "id": "u17_p_ksc", "entity_id": KSC},
                                    {**post, "id": "u17_p_kanda", "entity_id": KANDA}])
    await _simpan(klien, kepala_admin, "notif.content_reminder_window_minutes", 120, "entity", KANDA)
    await marketing_service.job_content_reminder()
    sudah = {p["id"] for p in await db.mkt_posts.find({"reminder_sent_at": {"$ne": ""}}, {"_id": 0, "id": 1})
             .to_list(None)}
    assert "u17_p_kanda" in sudah and "u17_p_ksc" not in sudah
    await _pulihkan(klien, kepala_admin, "notif.content_reminder_window_minutes", KANDA)
    # toleransi tepat waktu: tayang 30 menit sesudah jadwal → tepat waktu (60) di KSC, terlambat (0) di Kanda
    pub = {"status": "published", "publish_at": "2026-11-01T10:00", "published_at": "2026-11-01T03:30:00+00:00"}
    rows = [{**pub, "entity_id": KSC}, {**pub, "entity_id": KANDA}]
    await _simpan(klien, kepala_admin, "notif.content_on_time_grace_minutes", 0, "entity", KANDA)
    toleransi = await marketing_ext._toleransi_per_pt(rows)
    assert toleransi == {"": 60, KSC: 60, KANDA: 0}
    assert (marketing_ext._kpi(rows[:1], toleransi)["on_time"], marketing_ext._kpi(rows[1:], toleransi)["late"]) == (1, 1)
    await _pulihkan(klien, kepala_admin, "notif.content_on_time_grace_minutes", KANDA)


async def test_KPT7_U18_anggaran_kampanye_label_dan_selisih_persediaan(klien, kepala_admin, db, monkeypatch):
    from services import gl_service, inventory_drift_watch, marketing_cost_service, printer_stuck_watch
    # anggaran kampanye: terpakai 60% → "hampir habis" bila ambang PT 50, tidak bila bawaan 80
    async def _realisasi(ids):
        return {i: 600_000.0 for i in ids}
    monkeypatch.setattr(marketing_cost_service, "realized_by_campaign", _realisasi)
    kampanye = [{"id": "u18_c_ksc", "name": "K1", "budget": 1_000_000, "entity_id": KSC, "start_date": "2026-11-01"},
                {"id": "u18_c_kanda", "name": "K2", "budget": 1_000_000, "entity_id": KANDA, "start_date": "2026-11-01"}]
    await _simpan(klien, kepala_admin, "notif.campaign_budget_near_pct", 50, "entity", KANDA)
    res = await marketing_cost_service.budget_summary(kampanye)
    assert [a["campaign_id"] for a in res["alerts"]] == ["u18_c_kanda"] and res["near_pct"] == 80.0
    assert (await marketing_cost_service.budget_summary(kampanye[1:]))["near_pct"] == 50.0
    await _pulihkan(klien, kepala_admin, "notif.campaign_budget_near_pct", KANDA)
    # label tertahan: antrean 40 menit → diberitakan bila batas 30 (KSC), tidak bila batas PT 60 (Kanda)
    now = datetime.now(timezone.utc)
    job = {"status": "queued", "item_count": 3, "created_at": (now - timedelta(minutes=40)).isoformat()}
    await db.rfid_print_jobs.insert_many([{**job, "id": "u18_pj1", "warehouse_id": "u18_whs", "owner_entity_id": KSC},
                                          {**job, "id": "u18_pj2", "warehouse_id": "u18_whk", "owner_entity_id": KANDA}])
    await _simpan(klien, kepala_admin, "notif.printer_stuck_minutes", 60, "entity", KANDA)
    res = await printer_stuck_watch.scan()
    assert [s["warehouse_id"] for s in res["stuck"]] == ["u18_whs"]
    await _pulihkan(klien, kepala_admin, "notif.printer_stuck_minutes", KANDA)
    res = await printer_stuck_watch.scan()
    assert sorted(s["warehouse_id"] for s in res["stuck"]) == ["u18_whk", "u18_whs"]
    await db.rfid_print_jobs.delete_many({"id": {"$regex": "^u18_"}})
    # selisih persediaan: Rp5.000 dengan ambang Rp1.000 → kritis bila kelipatan PT 2, peringatan bila bawaan 10
    async def _rekon():
        return {"rows": [{"entity_id": KSC, "entity_name": "KSC", "difference": 5000.0, "subledger_value": 10000.0,
                          "gl_balance": 5000.0},
                         {"entity_id": KANDA, "entity_name": "Kanda", "difference": 5000.0, "subledger_value": 10000.0,
                          "gl_balance": 5000.0}]}
    monkeypatch.setattr(gl_service, "inventory_reconciliation", _rekon)
    await _simpan(klien, kepala_admin, "inventory.drift_critical_multiplier", 2, "entity", KANDA)
    await db.notifications.delete_many({})
    await inventory_drift_watch.scan()
    sev = {n["entity_id"]: n["severity"] for n in await _notif(db, type="inventory_drift")}
    assert sev == {KSC: "warning", KANDA: "critical"}, sev
    await _pulihkan(klien, kepala_admin, "inventory.drift_critical_multiplier", KANDA)


async def test_KPT7_U19_pengingat_persetujuan_tenggat_desain_peran_siaran(klien, kepala_admin, db):
    from services import approval_reminder, design_request_service as drs, wa_alert_service as wa
    rows = [{"number": f"PO-{i}", "queue_label": "PO menunggu ACC", "title": f"Dokumen {i}", "days_waiting": 9 - i}
            for i in range(5)]
    await _simpan(klien, kepala_admin, "approval.reminder_max_listed", 1, "entity", KANDA)
    assert (await approval_reminder._ringkas(rows, KANDA)).count("•") == 2           # 1 disebut + "+4 lain"
    assert (await approval_reminder._ringkas(rows, KSC)).count("•") == 4             # 3 disebut + "+2 lain"
    await _pulihkan(klien, kepala_admin, "approval.reminder_max_listed", KANDA)
    # tenggat desain 7 hari lagi: dekat bila batas PT 10, tidak bila bawaan 3
    await db.design_requests.insert_many([
        {"id": "u19_dr_ksc", "status": "assigned", "entity_id": KSC, "due_date": _tgl(7)},
        {"id": "u19_dr_kanda", "status": "assigned", "entity_id": KANDA, "due_date": _tgl(7)}])
    await _simpan(klien, kepala_admin, "rnd.design_due_soon_days", 10, "entity", KANDA)
    s_kanda = await drs.summary({"entity_id": KANDA, "id": {"$regex": "^u19_"}})
    s_ksc = await drs.summary({"entity_id": KSC, "id": {"$regex": "^u19_"}})
    assert (s_kanda["due_soon"], s_kanda["due_soon_days"], s_ksc["due_soon"], s_ksc["due_soon_days"]) == (1, 10, 0, 3)
    await _pulihkan(klien, kepala_admin, "rnd.design_due_soon_days", KANDA)
    # peran penerima siaran WhatsApp
    await db.users.update_one({"id": "user_wh_01"}, {"$set": {"phone": "081333333333"}})
    await db.users.update_one({"id": "user_manager_01"}, {"$set": {"phone": "081444444444"}})
    cfg = {**(await wa.raw_settings())["wa"], "pic_number": ""}
    siaran = {"recipient_role": "all", "entity_id": KSC}
    assert "6281444444444" in [x["phone"] for x in await wa.resolve_recipients(siaran, cfg)]
    await _simpan(klien, kepala_admin, "notif.wa_broadcast_roles", ["warehouse"])
    nomor = [x["phone"] for x in await wa.resolve_recipients(siaran, cfg)]
    assert "6281333333333" in nomor and "6281444444444" not in nomor
    await _pulihkan(klien, kepala_admin, "notif.wa_broadcast_roles")


async def test_KPT7_U20_pengingat_lintas_pt_hanya_tabel_grup(klien, kepala_admin):
    from services import reminder_policy
    await _simpan(klien, kepala_admin, "notif.reminder_recipients",
                  [{"reminder": "ar_overdue", "mode": "peran", "roles": ["finance"]},
                   {"reminder": "budget_alert", "mode": "peran", "roles": ["finance", "manager"]}], "entity", KANDA)
    # piutang jatuh tempo: notifikasinya tidak ber-PT → baris PT diabaikan; anggaran ber-PT → baris PT dipakai
    assert (await reminder_policy.recipients_for("ar_overdue", KANDA))["roles"] == ["manager"]
    assert (await reminder_policy.recipients_for("budget_alert", KANDA))["roles"] == ["finance", "manager"]
    assert (await reminder_policy.recipients_for("budget_alert", KSC))["roles"] == ["manager"]
    # beberapa peran → satu notifikasi per orang (create_addressed), bukan recipient_role
    made = await reminder_policy.notify("budget_alert", KANDA, notif_type="budget_alert", ref="u20:anggaran",
                                        title="Uji U20", body="u20", severity="warning", link="budget",
                                        dedupe_scope="day")
    assert made and all(n["recipient_role"] == "" and n["recipient_user"] and n["entity_id"] == KANDA for n in made)
    satu = await reminder_policy.notify("budget_alert", KSC, notif_type="budget_alert", ref="u20:anggaran_ksc",
                                        title="Uji U20", body="u20", severity="warning", link="budget",
                                        dedupe_scope="day")
    assert [(n["recipient_role"], n["recipient_user"]) for n in satu] == [("manager", None)]
    # pengingat yang tidak ada di tabel PT → baris grup, lalu bawaan
    await _simpan(klien, kepala_admin, "notif.reminder_recipients",
                  [{"reminder": "ops_stalled", "mode": "peran", "roles": ["warehouse_admin"]}])
    assert (await reminder_policy.recipients_for("ops_stalled", KANDA))["roles"] == ["warehouse_admin"]
    assert (await reminder_policy.recipients_for("ap_due", KANDA))["roles"] == ["manager"]
    await _pulihkan(klien, kepala_admin, "notif.reminder_recipients", KANDA)
