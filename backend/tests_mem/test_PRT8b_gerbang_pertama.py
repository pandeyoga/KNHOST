"""PR-T8b — 14 rute merah di penjaga matriks izin (`sapuan_izin.py`, temuan T8-01…T8-09 laporan PR-T8).

Kelompok B (T8-06…T8-09): pemeriksaan sesi + izin dipindah ke pernyataan pertama handler (`02_STANDAR.md` §3.1 Z1),
pesan 403 kalimat Z6. Di kode lama dokumen dimuat dulu: tanpa sesi dan tanpa izin sama-sama dijawab 404 (oracle
keberadaan id) — uji U1, U2, dan U7 merah di sana. U3–U6 menjaga aturan bisnis lama tetap berlaku sesudah gerbang
pertama (lulus di kode lama maupun baru).

Kelompok A (T8-01…T8-05): perilakunya sudah benar; putusan "cukup login" ditulis di `LOGIN_ONLY` (Z3). U8 merah di kode
lama (rute belum tercatat).

Fixture: peran dan akun lewat fixture baku `tests_mem` (peran lewat `POST /api/access/roles`); dokumen niat bayar dan
sesi pendaftaran disisipkan langsung (bentuk minimal yang dibaca handler); jadwal pengaturan lewat `PUT /api/config/values`.
"""
from __future__ import annotations

import datetime as dt
import re
from typing import Any, Dict, List, Optional, Tuple

import pytest

pytestmark = pytest.mark.anyio

ALASAN = "Uji gerbang izin PR-T8b"

#: (metode, jalur dengan id yang tidak ada, isi sah) — isi sah supaya validasi 422 tidak mendahului gerbang.
RUTE_B: List[Tuple[str, str, Optional[Dict[str, Any]]]] = [
    ("POST", "/api/ap-payments/api_tidak_ada/resume", None),
    ("POST", "/api/ap-payments/api_tidak_ada/cancel", {"reason": ALASAN}),
    ("POST", "/api/registration/sessions/sesi_tidak_ada/approve", {"reason": ALASAN}),
    ("POST", "/api/registration/sessions/sesi_tidak_ada/return", {"reason": ALASAN}),
    ("PATCH", "/api/registration/sessions/sesi_tidak_ada/lines/baris_x", {"note": ALASAN}),
    ("DELETE", "/api/registration/sessions/sesi_tidak_ada/lines/baris_x", None),
    ("POST", "/api/special-orders/od_tidak_ada/fulfillment/k/cancel", {"reason": ALASAN}),
    ("POST", "/api/config/values/cancel-scheduled", {"id": "cfgv_tidak_ada", "reason": ALASAN}),
]

#: Izin paling sempit yang tetap melewati gerbang pertama tiap rute (dokumen tidak ada → 404 seperti dulu).
IZIN_LOLOS: Dict[str, List[Dict[str, List[str]]]] = {
    "/api/ap-payments/api_tidak_ada/resume": [{"vendor_bill": ["pay"]}, {"contra_bon": ["pay"]}],
    "/api/ap-payments/api_tidak_ada/cancel": [{"vendor_bill": ["pay"]}, {"contra_bon": ["pay"]}],
    "/api/registration/sessions/sesi_tidak_ada/approve": [{"inventory": ["approve_count"]},
                                                          {"inventory": ["approve_value"]}],
    "/api/registration/sessions/sesi_tidak_ada/return": [{"inventory": ["approve_count"]},
                                                         {"inventory": ["approve_value"]}],
    "/api/registration/sessions/sesi_tidak_ada/lines/baris_x": [{"inventory": ["cycle_count"]},
                                                                {"inventory": ["approve_count"]}],
    "/api/special-orders/od_tidak_ada/fulfillment/k/cancel": [{"od_fulfillment": ["cancel"]}],
    "/api/config/values/cancel-scheduled": [{"settings": ["manage"]}, {"inventory": ["configure"]}],
}

POLA_TEKNIS = re.compile(r"\b[a-z_]+\.[a-z_]+\b")    # `x.y` sumber daya/aksi tidak boleh tampil (Z6)


def _detail(r) -> str:
    d = r.json().get("detail")
    return d if isinstance(d, str) else str(d)


async def _panggil(klien, metode: str, jalur: str, isi: Optional[Dict[str, Any]], headers: Dict[str, str]):
    return await klien.request(metode, jalur, headers=headers, json=isi)


async def _ta(akun, sesi, peran_tanpa_acuan, izin: Dict[str, List[str]], label: str) -> Dict[str, str]:
    return await sesi(await akun(await peran_tanpa_acuan(izin, label=label)))


# ── U1 — tanpa sesi: 401 sebelum dokumen dimuat (kode lama 404) ─────────────────────────────────────────────────────
@pytest.mark.parametrize("metode,jalur,isi", RUTE_B, ids=[f"{m} {j}" for m, j, _ in RUTE_B])
async def test_PRT8b_U1_tanpa_sesi_401(klien, metode, jalur, isi):
    r = await _panggil(klien, metode, jalur, isi, {"X-Entity-Id": "ent_ksc"})
    assert r.status_code == 401, (r.status_code, r.text)


# ── U2 — bersesi tanpa izin: 403 kalimat Z6 sebelum dokumen dimuat (kode lama 404) ─────────────────────────────────
async def test_PRT8b_U2_tanpa_izin_403_z6(klien, akun, sesi, peran_tanpa_acuan, peran_manajer_kosong, peran_sopir):
    kosong = await _ta(akun, sesi, peran_tanpa_acuan, {}, "TA U2 kosong")
    mk = await sesi(await akun(await peran_manajer_kosong()))
    sopir = await sesi(await akun(peran_sopir))
    salah = []
    for metode, jalur, isi in RUTE_B:
        for nama, h in (("kosong", kosong), ("mgr0", mk), ("sopir", sopir)):
            r = await _panggil(klien, metode, jalur, isi, h)
            if r.status_code != 403:
                salah.append((nama, metode, jalur, r.status_code, r.text[:80]))
                continue
            d = _detail(r)
            ok = (d.startswith("Anda belum punya akses untuk ") and "Minta Admin menambahkan akses '" in d
                  and not POLA_TEKNIS.search(d) and "Permission ditolak" not in d)
            if not ok:
                salah.append((nama, metode, jalur, 403, d))
    assert not salah, salah


# ── U3 — pemegang izin gerbang tetap sampai ke dokumen (404 seperti dulu) ───────────────────────────────────────────
async def test_PRT8b_U3_berizin_tetap_404(klien, akun, sesi, peran_tanpa_acuan):
    salah, kepala = [], {}
    for metode, jalur, isi in RUTE_B:
        for izin in IZIN_LOLOS[jalur]:
            (res, (aksi,)), = izin.items()
            if (res, aksi) not in kepala:                     # satu peran per izin (nama peran wajib unik)
                kepala[(res, aksi)] = await _ta(akun, sesi, peran_tanpa_acuan, izin, f"TA U3 {res} {aksi}")
            h = kepala[(res, aksi)]
            r = await _panggil(klien, metode, jalur, isi, h)
            if r.status_code != 404:
                salah.append((metode, jalur, izin, r.status_code, r.text[:120]))
    assert not salah, salah


# ── U4 — bayar hutang: izin tetap dipilih dari jenis niat ───────────────────────────────────────────────────────────
async def test_PRT8b_U4_niat_bayar_izin_per_jenis(klien, db, akun, sesi, peran_tanpa_acuan):
    """Fixture sisip: satu niat bayar faktur pemasok yang sudah selesai (status `done`)."""
    await db.ap_payment_intents.insert_one({"id": "api_uji_prt8b", "kind": "vendor_bill", "target_id": "vb_uji_prt8b",
                                            "entity_id": "ent_ksc", "status": "done", "step": "journal",
                                            "allocations": []})
    kb = await _ta(akun, sesi, peran_tanpa_acuan, {"contra_bon": ["pay"]}, "TA U4 kontrabon")
    vb = await _ta(akun, sesi, peran_tanpa_acuan, {"vendor_bill": ["pay"]}, "TA U4 faktur")
    for akhir, isi in (("resume", None), ("cancel", {"reason": ALASAN})):
        jalur = f"/api/ap-payments/api_uji_prt8b/{akhir}"
        r = await klien.post(jalur, headers=kb, json=isi)
        assert r.status_code == 403, (akhir, r.text)                       # niat faktur → butuh vendor_bill.pay
        r = await klien.post(jalur, headers=vb, json=isi)
        assert r.status_code == 409, (akhir, r.text)                       # lolos gerbang; status niat menolak


# ── U5 — sesi pendaftaran: izin tetap dipilih dari status sesi dan pengaturan PT ───────────────────────────────────
async def test_PRT8b_U5_sesi_pendaftaran_izin_per_keadaan(klien, db, akun, sesi, peran_tanpa_acuan):
    """Fixture sisip: satu sesi pendaftaran menunggu persetujuan (hitungan belum disetujui gudang)."""
    await db.cycle_count_sessions.insert_one({"id": "sesi_uji_prt8b", "mode": "registration",
                                              "status": "pending_approval", "entity_id": "ent_ksc",
                                              "warehouse_id": "wh_uji_prt8b", "registration": {}})
    hitung = await _ta(akun, sesi, peran_tanpa_acuan, {"inventory": ["cycle_count"]}, "TA U5 hitung")
    nilai = await _ta(akun, sesi, peran_tanpa_acuan, {"inventory": ["approve_value"]}, "TA U5 nilai")
    gudang = await _ta(akun, sesi, peran_tanpa_acuan, {"inventory": ["approve_count"]}, "TA U5 setuju hitung")
    dasar = "/api/registration/sessions/sesi_uji_prt8b"
    # menunggu persetujuan: ubah/batal baris hanya penyetuju hitungan (`_line_actor`)
    assert (await klien.patch(f"{dasar}/lines/baris_x", headers=hitung, json={"note": ALASAN})).status_code == 403
    assert (await klien.delete(f"{dasar}/lines/baris_x", headers=hitung)).status_code == 403
    r = await klien.delete(f"{dasar}/lines/baris_x", headers=gudang)
    assert r.status_code not in (401, 403), r.text
    # kembalikan sebelum hitungan disetujui: hanya penyetuju hitungan (Finance belum)
    assert (await klien.post(f"{dasar}/return", headers=nilai, json={"reason": ALASAN})).status_code == 403
    # setujui saat langkah Finance aktif (bawaan): penyetuju hitungan saja ditolak
    assert (await klien.post(f"{dasar}/approve", headers=gudang, json={"reason": ALASAN})).status_code == 403
    r = await klien.post(f"{dasar}/approve", headers=nilai, json={"reason": ALASAN})
    assert r.status_code == 400 and "Langkah 1 belum" in _detail(r), r.text   # lolos izin; langkah gudang dulu


# ── U6 — batal jadwal pengaturan: izin tetap per kunci baris jadwal ─────────────────────────────────────────────────
async def test_PRT8b_U6_jadwal_pengaturan_izin_per_kunci(klien, db, kepala_admin, akun, sesi, peran_tanpa_acuan):
    nanti = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).isoformat()
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "ar.grace_days", "value": 12, "scope_type": "global", "scope_id": "", "reason": ALASAN,
        "effective_from": nanti}]})
    assert r.status_code == 200, r.text
    row = r.json()["saved"][0]
    gudang = await _ta(akun, sesi, peran_tanpa_acuan, {"inventory": ["configure"]}, "TA U6 atur gudang")
    r = await klien.post("/api/config/values/cancel-scheduled", headers=gudang, json={"id": row["id"], "reason": ALASAN})
    assert r.status_code == 403, r.text                                   # `ar.grace_days` butuh settings.manage
    assert "Anda belum punya akses untuk mengubah pengaturan “" in _detail(r)
    assert "cancelled_at" not in (await db.config_values.find_one({"id": row["id"]}, {"_id": 0}))
    r = await klien.post("/api/config/values/cancel-scheduled", headers=kepala_admin,
                         json={"id": row["id"], "reason": ALASAN})
    assert r.status_code == 200, r.text


# ── U7 — batal pemenuhan pesanan khusus: hanya `od_fulfillment.cancel` (kode lama 404: dokumen dimuat dulu) ──────────
async def test_PRT8b_U7_batal_pemenuhan_hanya_izin_batal(klien, akun, sesi, peran_tanpa_acuan):
    jalur, isi = "/api/special-orders/od_tidak_ada/fulfillment/k/cancel", {"reason": ALASAN}
    for izin in ({"od_fulfillment": ["choose_route", "realize"]}, {"order": ["view", "update"]}):
        h = await _ta(akun, sesi, peran_tanpa_acuan, izin, f"TA U7 {sorted(izin)[0]}")
        r = await klien.post(jalur, headers=h, json=isi)
        assert r.status_code == 403, (izin, r.text)


# ── U8 — kelompok A: putusan login-saja tertulis ────────────────────────────────────────────────────────────────────
LOGIN_SAJA_BARU = {
    ("GET", "/api/dashboard"): "rujukan",
    ("GET", "/api/approval-policies/can-decide/me"): "milik_sendiri",
    ("GET", "/api/interco/prices/access"): "sesi",
    ("GET", "/api/hr/payslips/{slip_id}"): "milik_sendiri",
    ("GET", "/api/hr/payslips/{slip_id}/pdf"): "milik_sendiri",
    ("POST", "/api/hr/leave-requests/{leave_id}/cancel"): "milik_sendiri",
}


async def test_PRT8b_U8_login_saja_tertulis(aplikasi):
    import login_only_endpoints as lo
    rute = {(m, rt.path) for rt in aplikasi.routes for m in (getattr(rt, "methods", None) or ())}
    for k, alasan in LOGIN_SAJA_BARU.items():
        assert k in rute, k
        assert lo.LOGIN_ONLY.get(k) == alasan, (k, lo.LOGIN_ONLY.get(k))


# ── U9 — kelompok A: perilakunya tetap (tidak berubah oleh unit ini) ───────────────────────────────────────────────
async def test_PRT8b_U9_login_saja_perilaku_tetap(klien, akun, sesi, peran_tanpa_acuan):
    kosong = await _ta(akun, sesi, peran_tanpa_acuan, {}, "TA U9 kosong")
    # dasbor 200 dengan bagian kosong (PR-T3 S1); akses harga antar-PT = dua bendera milik pemanggil
    r = await klien.get("/api/dashboard", headers=kosong)
    assert r.status_code == 200 and r.json()["orders"] == [], r.text
    r = await klien.get("/api/interco/prices/access", headers=kosong)
    assert r.status_code == 200 and r.json() == {"can_view": False, "can_set": False}, r.text
    # boleh-tidaknya memutus: tanpa izin setujui → tidak boleh, kalimat Z6, tanpa nominal
    r = await klien.get("/api/approval-policies/can-decide/me", headers=kosong,
                        params={"doc_kind": "purchase_order", "amount": 1000})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["allowed"] is False and j["code"] == "izin" and "Minta Admin menambahkan akses" in j["message"]
    # slip gaji dan batal cuti: tetap disaring sesudah dokumen dimuat (pemilik atau berizin)
    for metode, jalur, isi in (("GET", "/api/hr/payslips/slip_tidak_ada", None),
                               ("GET", "/api/hr/payslips/slip_tidak_ada/pdf", None),
                               ("POST", "/api/hr/leave-requests/cuti_tidak_ada/cancel", {"reason": ALASAN})):
        r = await klien.request(metode, jalur, headers=kosong, json=isi)
        assert r.status_code == 404, (jalur, r.text)
        r = await klien.request(metode, jalur, headers={"X-Entity-Id": "ent_ksc"}, json=isi)
        assert r.status_code == 401, (jalur, r.text)
