"""PK-33 (DB-01) — penjaga atomisitas INV-ATOMIC-01 hijau dan bermakna.

Lapis B. Bagian statik (U1, U3, U5, U6, U10) memanggil pencacah `scripts/inventaris_multi_koleksi.py` dan penjaga
`scripts/guardrails/verify_atomic_claim.py` (hanya membaca kode). Bagian HTTP (U7, U9) memakai aplikasi utuh di database
tiruan untuk dua endpoint golongan 4 ("tambah klaim"):

* `POST /api/sales-returns/{id}/roll-settlement/back-shipment` — klaim `sales_returns` berprasyarat roll masih
  `back_pending`, sebelum nomor surat jalan diambil;
* `POST /api/hr/leave-requests` (dan `/me`, layanan yang sama `hr_leave_service.submit_leave`) — klaim `hr_employees`
  sesudah validasi isian, sebelum cek tabrakan tanggal + reservasi saldo + sisip pengajuan.

Balapan dua permintaan dibuat DETERMINISTIK: pembuat nomor dokumen permintaan pertama ditukar pembungkus yang — sebelum
nomor diambil (sesudah semua cek permintaan pertama lolos, sebelum tulisannya) — menjalankan permintaan kedua sampai
selesai. Di kode lama permintaan kedua ikut lolos (dua surat jalan / dua pengajuan cuti untuk tanggal sama); di kode baru
ia kalah klaim (409 `SAGA_IN_PROGRESS`). Data induk (retur, roll, karyawan) = FIXTURE yang disisipkan langsung; aksinya
lewat API (alur) atau layanan (sisipan balapan). U8 (dua permintaan sungguh bersamaan) di MongoDB asli:
`backend/tests/test_bp_PK33_klaim_bersamaan.py`.
"""
import importlib.util
import pathlib
import subprocess
import sys
import uuid

import pytest
from fastapi import HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
pytestmark = pytest.mark.anyio


def _muat(nama: str, berkas: pathlib.Path):
    spec = importlib.util.spec_from_file_location(nama, berkas)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    sys.path.insert(0, str(SCRIPTS / "guardrails"))
    spec.loader.exec_module(mod)
    return mod


def _inv():
    return _muat("inv_pk33", SCRIPTS / "inventaris_multi_koleksi.py")


def _penjaga():
    return _muat("vac_pk33", SCRIPTS / "guardrails" / "verify_atomic_claim.py")


def uid(awalan: str) -> str:
    return f"{awalan}_pk33_{uuid.uuid4().hex[:8]}"


# ── U1 — pencacah: hasil sama di dua urutan berkas; tidak ada salah-atribusi nama polos ───────────────────────────
async def test_PK33_U1_pencacah_urutan_berkas_tidak_mengubah_hasil(monkeypatch):
    inv = _inv()
    biasa = inv.collect_rows()
    asli = pathlib.Path.glob
    monkeypatch.setattr(pathlib.Path, "glob", lambda self, pola: iter(sorted(asli(self, pola), reverse=True)))
    terbalik = inv.collect_rows()
    monkeypatch.setattr(pathlib.Path, "glob", lambda self, pola: iter(sorted(asli(self, pola))))
    urut = inv.collect_rows()
    assert terbalik == urut == biasa, (len(biasa), len(terbalik), len(urut))


@pytest.mark.parametrize("fungsi", ["ocr_sample_service.delete", "ocr_sample_service.update",
                                    "design_ownership_service.claim", "dispatch_payment_gate.release",
                                    "return_grade_impairment.record"])
async def test_PK33_U1_tidak_ada_salah_atribusi_nama_polos(fungsi):
    """Baris yang 'lewat layanan'-nya fungsi kembar-nama hanya boleh muncul bila router itu memang mengimpor modulnya."""
    inv = _inv()
    modul = fungsi.split(".")[0]
    salah = []
    for berkas, _ln, kunci, _l, via, _k in inv.collect_rows():
        if fungsi in via:
            src = (ROOT / "backend" / "routers" / berkas).read_text()
            if modul not in src:
                salah.append(f"{berkas} {kunci}")
    assert not salah, salah


# ── U3 / U5 — penjaga dan uji-dirinya ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("arg", [["--self-test"], []])
async def test_PK33_U3_U5_penjaga_atomic_claim_hijau(arg):
    p = subprocess.run([sys.executable, "scripts/guardrails/verify_atomic_claim.py", *arg], cwd=ROOT,
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stdout[-4000:] + p.stderr[-2000:]
    if arg:
        assert "SELF-TEST HIJAU" in p.stdout
        for kasus in ("TANPA impor layanan tidak dihitung", "path persis", "dua metode path sama", "unit: ID tak dikenal",
                      "unit: status selesai", "unit: ID dikenal, status dikerjakan"):
            assert kasus in p.stdout, f"kasus uji-diri B.5 hilang: {kasus}"
    else:
        assert "[PASS]" in p.stdout and "0 pelanggaran" in p.stdout, p.stdout[-2000:]


# ── U6 — mekanisme `unit` dengan unit yang sudah selesai → MERAH, pesannya menyebut unit sudah selesai ────────────
async def test_PK33_U6_unit_selesai_merah():
    vac = _penjaga()
    src = {("x.py", "POST /a"): "async def f():\n    await db.a.insert_one({})\n"}
    entri = {("x.py", "POST /a"): ("unit", "PK-19: jalur tulis ini diganti satu pintu alokasi kwitansi")}
    # Papan nyata: PK-19 berstatus `selesai` (atau sudah `tervalidasi`) di docs/blueprint/STATUS.md.
    st = vac.unit_statuses().get("PK-19")
    assert st in ("selesai", "tervalidasi"), st
    g = vac.check(src, entri, None, units=None)
    assert any(f"PK-19 sudah {st}" in v for v in g.violations), g.violations
    # Pembanding: unit yang belum selesai → hijau.
    g = vac.check(src, entri, None, units={"PK-19": "dikerjakan"})
    assert not g.violations, g.violations


# ── U10 — alasan `none` ≥ 20 huruf dan tidak hanya berbunyi "aman" ────────────────────────────────────────────────
async def test_PK33_U10_alasan_none_bermakna():
    vac = _penjaga()
    buruk = [f"{k[0]} {k[1]}" for k, e in vac.REVIEWED.items()
             if e[0] == "none" and (len(e[1].strip()) < 20 or len(vac._tanpa_aman(e[1])) < 20)]
    assert buruk == []


# ── Golongan 4 (a) — surat jalan kirim balik roll retur ───────────────────────────────────────────────────────────
async def _retur_kirim_balik(db, n_roll: int = 2):
    """FIXTURE: retur per roll dengan `n_roll` roll Diskon/Tolak klaim yang menunggu dikirim balik (back_pending)."""
    ret_id = uid("sret")
    rolls = [uid("roll") for _ in range(n_roll)]
    for i, r in enumerate(rolls):
        await db.inventory_rolls.insert_one({"id": r, "roll_no": f"R-{r[-12:]}", "unit": "yard", "product_id": "p_pk33",
                                             "status": "returned", "owner_entity_id": "ent_ksc"})
    await db.sales_returns.insert_one({
        "id": ret_id, "number": f"RET-{ret_id[-6:]}", "entity_id": "ent_ksc", "order_id": uid("so"),
        "order_number": "SO-PK33", "customer_id": "cust_pk33", "customer_name": "Pelanggan Uji PK-33",
        "status": "inspected", "return_type": "cutloss",
        "roll_outcomes": {r: {"outcome": "discount", "back_pending": True, "qty_back": 5.0} for r in rolls}})
    return ret_id, rolls


async def test_PK33_U7_kirim_balik_dua_kali_berurutan_satu_surat_jalan(klien, db, kepala_admin):
    # Hitungan: 2 roll menunggu → panggilan 1 = 1 surat jalan berisi 2 roll; panggilan 2 tidak ada yang menunggu → 400.
    ret_id, rolls = await _retur_kirim_balik(db)
    url = f"/api/sales-returns/{ret_id}/roll-settlement/back-shipment"
    r1 = await klien.post(url, headers=kepala_admin, json={"roll_ids": rolls})
    assert r1.status_code == 200, r1.text
    assert len(r1.json()["rolls"]) == 2
    r2 = await klien.post(url, headers=kepala_admin, json={"roll_ids": rolls})
    assert r2.status_code in (400, 409), r2.text
    assert await db.shipments.count_documents({"return_id": ret_id}) == 1
    ret = await db.sales_returns.find_one({"id": ret_id})
    assert "saga_lock" not in ret
    assert all(ret["roll_outcomes"][r]["back_pending"] is False for r in rolls)


async def test_PK33_U7_kirim_balik_dua_permintaan_bersela_satu_surat_jalan(klien, db, kepala_admin, monkeypatch):
    """Permintaan B dijalankan di sela permintaan A (sesudah cek A lolos, sebelum A menulis surat jalan).

    Hitungan: kode lama → A dan B sama-sama membaca 2 roll `back_pending` → 2 surat jalan untuk roll yang sama.
    Kode baru → A memegang klaim retur; B ditolak 409 SAGA_IN_PROGRESS → 1 surat jalan."""
    from services import return_roll_settlement_service as rrs
    from services import shipment_service
    ret_id, rolls = await _retur_kirim_balik(db)
    basi = await db.sales_returns.find_one({"id": ret_id}, {"_id": 0})   # dibaca kedua permintaan sebelum ada tulisan
    asli = shipment_service._next_shipment_no
    hasil_b = {}

    async def bersela(entity_id=None):
        if not hasil_b:
            hasil_b["mulai"] = True
            try:
                hasil_b["ok"] = await rrs.back_shipment(dict(basi), rolls, {"name": "Petugas B"})
            except HTTPException as e:
                hasil_b["galat"] = (e.status_code, e.detail)
        return await asli(entity_id)

    monkeypatch.setattr(shipment_service, "_next_shipment_no", bersela)
    a = await rrs.back_shipment(dict(basi), rolls, {"name": "Petugas A"})
    assert a["shipment_no"]
    assert hasil_b.get("mulai"), "pembungkus tidak terpanggil"
    assert "ok" not in hasil_b, f"permintaan B ikut membuat surat jalan {hasil_b.get('ok', {}).get('shipment_no')}"
    assert hasil_b["galat"][0] == 409 and hasil_b["galat"][1]["code"] == "SAGA_IN_PROGRESS", hasil_b
    assert await db.shipments.count_documents({"return_id": ret_id}) == 1
    assert "saga_lock" not in await db.sales_returns.find_one({"id": ret_id})


async def test_PK33_U9_kirim_balik_ditolak_validasi_tanpa_kunci(klien, db, kepala_admin):
    ret_id, rolls = await _retur_kirim_balik(db)
    r = await klien.post(f"/api/sales-returns/{ret_id}/roll-settlement/back-shipment", headers=kepala_admin,
                         json={"roll_ids": ["roll_tidak_ada"]})
    assert r.status_code == 400, r.text
    assert "saga_lock" not in await db.sales_returns.find_one({"id": ret_id})
    assert await db.shipments.count_documents({"return_id": ret_id}) == 0


# ── Golongan 4 (b) — pengajuan cuti ───────────────────────────────────────────────────────────────────────────────
async def _karyawan(db):
    emp = {"id": uid("emp"), "name": f"Karyawan Uji {uuid.uuid4().hex[:4]}", "entity_id": "ent_ksc", "status": "active",
           "created_at": "2026-01-01T00:00:00+00:00"}
    await db.hr_employees.insert_one(dict(emp))
    return emp


# Senin–Selasa 1–2 Maret 2027 (hari kerja) — jauh dari tanggal seed.
CUTI = {"leave_type": "cuti_tahunan", "date_from": "2027-03-01", "date_to": "2027-03-02", "reason": "uji PK-33"}


async def test_PK33_U7_cuti_dua_kali_berurutan_satu_pengajuan(klien, db, kepala_admin):
    # Hitungan: pengajuan 1 = 2 hari kerja (pending 2); pengajuan 2 tanggal sama → 400 tabrakan; pengajuan tetap 1.
    emp = await _karyawan(db)
    body = {**CUTI, "employee_id": emp["id"]}
    r1 = await klien.post("/api/hr/leave-requests", headers=kepala_admin, json=body)
    assert r1.status_code == 200, r1.text
    assert r1.json()["days"] == 2
    r2 = await klien.post("/api/hr/leave-requests", headers=kepala_admin, json=body)
    assert r2.status_code in (400, 409), r2.text
    assert await db.hr_leave_requests.count_documents({"employee_id": emp["id"]}) == 1
    bal = await db.hr_leave_balances.find_one({"employee_id": emp["id"], "year": 2027})
    assert bal["pending"] == 2
    assert "saga_lock" not in await db.hr_employees.find_one({"id": emp["id"]})


async def test_PK33_U7_cuti_dua_permintaan_bersela_satu_pengajuan(db, monkeypatch):
    """Permintaan B dijalankan di sela permintaan A (sesudah cek tabrakan + reservasi saldo A, sebelum A disisipkan).

    Hitungan: kode lama → B tidak melihat pengajuan A (belum tersisip), `recompute_balance` B menimpa `pending` A ke 0
    lalu memesan 2 hari lagi → 2 pengajuan untuk tanggal yang sama. Kode baru → B kalah klaim karyawan (409) → 1."""
    from services import hr_leave_service as lv
    emp = await _karyawan(db)
    asli = lv.next_doc_number
    hasil_b = {}

    async def bersela(*a, **kw):
        if a and a[0] == "hr_leave_requests" and not hasil_b:
            hasil_b["mulai"] = True
            try:
                hasil_b["ok"] = await lv.submit_leave(emp, dict(CUTI), "HR B")
            except HTTPException as e:
                hasil_b["galat"] = (e.status_code, e.detail)
            except ValueError as e:
                hasil_b["galat"] = (400, str(e))
        return await asli(*a, **kw)

    monkeypatch.setattr(lv, "next_doc_number", bersela)
    a = await lv.submit_leave(emp, dict(CUTI), "HR A")
    assert a["status"] == "pending"
    assert hasil_b.get("mulai"), "pembungkus tidak terpanggil"
    assert "ok" not in hasil_b, f"permintaan B ikut lolos: {hasil_b.get('ok', {}).get('number')}"
    assert hasil_b["galat"][0] == 409 and hasil_b["galat"][1]["code"] == "SAGA_IN_PROGRESS", hasil_b
    assert await db.hr_leave_requests.count_documents({"employee_id": emp["id"]}) == 1
    assert "saga_lock" not in await db.hr_employees.find_one({"id": emp["id"]})


@pytest.mark.parametrize("isian, pesan", [
    ({"leave_type": "tidak_ada"}, "Tipe cuti tidak dikenal"),
    ({"date_from": "bukan-tanggal", "date_to": ""}, "Tanggal mulai tidak valid"),
    ({"date_from": "2027-03-06", "date_to": "2027-03-07"}, "Rentang tanggal tidak valid"),   # Sabtu–Minggu
])
async def test_PK33_U9_cuti_ditolak_validasi_tanpa_kunci(klien, db, kepala_admin, isian, pesan):
    emp = await _karyawan(db)
    r = await klien.post("/api/hr/leave-requests", headers=kepala_admin, json={**CUTI, **isian, "employee_id": emp["id"]})
    assert r.status_code == 400 and pesan in r.text, r.text
    assert "saga_lock" not in await db.hr_employees.find_one({"id": emp["id"]})


async def test_PK33_U9_cuti_tabrakan_dan_saldo_kurang_kunci_dilepas(klien, db, kepala_admin):
    """Tabrakan tanggal dan saldo kurang diperiksa SESUDAH klaim (keduanya bagian dari cek-lalu-tulis yang dilindungi):
    kunci wajib dilepas, dan pengajuan berikutnya yang benar tetap diterima (bukan 409)."""
    emp = await _karyawan(db)
    ok = await klien.post("/api/hr/leave-requests", headers=kepala_admin, json={**CUTI, "employee_id": emp["id"]})
    assert ok.status_code == 200, ok.text
    tabrak = await klien.post("/api/hr/leave-requests", headers=kepala_admin, json={**CUTI, "employee_id": emp["id"]})
    assert tabrak.status_code == 400 and "bertabrakan" in tabrak.text, tabrak.text
    assert "saga_lock" not in await db.hr_employees.find_one({"id": emp["id"]})
    # Jatah bawaan 12 hari/tahun; sudah dipesan 2 → sisa 10; minta 15 hari kerja (8–26 Maret 2027) → saldo kurang.
    kurang = await klien.post("/api/hr/leave-requests", headers=kepala_admin,
                              json={**CUTI, "date_from": "2027-03-08", "date_to": "2027-03-26", "employee_id": emp["id"]})
    assert kurang.status_code == 400 and "Saldo cuti 2027 tidak cukup" in kurang.text, kurang.text
    assert "saga_lock" not in await db.hr_employees.find_one({"id": emp["id"]})
    lagi = await klien.post("/api/hr/leave-requests", headers=kepala_admin,
                            json={**CUTI, "date_from": "2027-03-03", "date_to": "2027-03-03", "employee_id": emp["id"]})
    assert lagi.status_code == 200, lagi.text
    assert await db.hr_leave_requests.count_documents({"employee_id": emp["id"]}) == 2
