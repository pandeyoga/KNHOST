"""MN-T2 — penyatuan layar keuangan (docs/blueprint/unit/MN-T2.md), lapis B (database tiruan).

U3–U7, U11: `GET /api/petty-cash/worklist` (daftar kerja Kas Kecil satu baris per pengajuan dana).
U8: tautan butir `suspense_nol` dan `stok_cocok` daftar periksa tutup buku menunjuk seksi di layar Tutup Buku.

Persiapan bersama (FIXTURE, disisipkan langsung; ALUR LPJ/pencairan sudah diuji PK-24): di `ent_ksc`
  PD-1 Rp 1.000.000 `approved` (belum cair)                         → tahap diajukan
  PD-2 Rp 2.000.000 `disbursed`, tanpa LPJ                          → tahap dicairkan
  PD-3 Rp 1.500.000 `settled`, LPJ-3 `posted_to_gl` Rp 1.800.000; hutang reimburse 1.800.000 − 1.500.000 = 300.000
       `open`                                                        → tahap dipertanggungjawabkan
  PD-4 Rp 750.000 `settled`, LPJ-4 `posted_to_gl` Rp 750.000; sisa 0 dan hutang 0 (`none`) → tahap selesai
Satu PD tambahan di `ent_kanda` (PD-K, `draft`) hanya untuk U11 (mode Semua PT): di mode satu PT KSC ia tidak terlihat.
Hitungan U3: 4 baris di KSC = 1 + 1 + 1 + 1 per tahap.
"""
from __future__ import annotations

import pytest

from core_utils import now_iso

pytestmark = pytest.mark.anyio

KSC, KANDA = "ent_ksc", "ent_kanda"
WL = "/api/petty-cash/worklist"
PEMILIK = {"id": "usr_mnt2_pemilik", "name": "Pemilik PD MNT2"}
STAF = {"id": "usr_mnt2_staf", "name": "Staf MNT2"}


def _pd(pid, nomor, nilai, status, *, entity=KSC, pemohon=STAF, waktu="2026-11-01T08:00:00+00:00"):
    return {"id": pid, "number": nomor, "entity_id": entity, "status": status, "kegiatan": f"keperluan {nomor}",
            "divisi": "Umum", "lines": [{"description": "uang muka", "qty": 1, "unit_price": nilai, "amount": nilai}],
            "total_amount": float(nilai), "approvals": [], "payment_method": "cash", "created_by": pemohon["name"],
            "created_by_id": pemohon["id"], "created_at": waktu, "updated_at": waktu}


def _lpj(sid, nomor, pd, uang_muka, keluar, *, reimburse=(0.0, "none"), sisa=(0.0, "none")):
    return {"id": sid, "number": nomor, "entity_id": KSC, "cash_advance_id": pd, "cash_advance_number": "",
            "status": "posted_to_gl", "total_pettycash": float(uang_muka), "total_pengeluaran": float(keluar),
            "sisa_kurang_dana": float(uang_muka - keluar), "expense_lines": [], "dibuat_oleh": STAF["name"],
            "hutang_reimburse": {"amount": reimburse[0], "status": reimburse[1]},
            "sisa_dikembalikan": {"amount": sisa[0], "status": sisa[1]},
            "created_by": STAF["name"], "created_by_id": STAF["id"],
            "created_at": "2026-11-05T08:00:00+00:00", "updated_at": "2026-11-05T09:00:00+00:00"}


@pytest.fixture(scope="module")
async def siap(db):
    if not await db.cash_advances.find_one({"id": "ca_mnt2_1"}):
        await db.cash_advances.insert_many([
            _pd("ca_mnt2_1", "PD-MNT2-1", 1_000_000, "approved", pemohon=PEMILIK),
            _pd("ca_mnt2_2", "PD-MNT2-2", 2_000_000, "disbursed"),
            _pd("ca_mnt2_3", "PD-MNT2-3", 1_500_000, "settled"),
            _pd("ca_mnt2_4", "PD-MNT2-4", 750_000, "settled"),
            _pd("ca_mnt2_k", "PD-MNT2-K", 400_000, "draft", entity=KANDA),
        ])
        await db.cash_advance_settlements.insert_many([
            _lpj("stl_mnt2_3", "STL-MNT2-3", "ca_mnt2_3", 1_500_000, 1_800_000, reimburse=(300_000.0, "open")),
            _lpj("stl_mnt2_4", "STL-MNT2-4", "ca_mnt2_4", 750_000, 750_000),
        ])
    return True


def _per_nomor(j):
    return {r["number"]: r for r in j["items"]}


# ── U3 — admin: empat baris, satu per tahap ───────────────────────────────────────────────────────────────────────
async def test_MNT2_U3_worklist_admin_empat_tahap(klien, kepala_admin, siap):
    r = await klien.get(WL, headers=kepala_admin)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["total"] == 4, j
    assert j["stage_counts"] == {"diajukan": 1, "dicairkan": 1, "dipertanggungjawabkan": 1, "selesai": 1}
    assert (j["page"], j["page_size"]) == (1, 25)
    b = _per_nomor(j)
    assert {n: x["stage"] for n, x in b.items()} == {
        "PD-MNT2-1": "diajukan", "PD-MNT2-2": "dicairkan", "PD-MNT2-3": "dipertanggungjawabkan",
        "PD-MNT2-4": "selesai"}
    assert b["PD-MNT2-1"]["settlement"] is None and b["PD-MNT2-2"]["settlement"] is None
    assert b["PD-MNT2-1"]["requester"] == PEMILIK["name"] and b["PD-MNT2-1"]["amount"] == 1_000_000
    assert set(b["PD-MNT2-4"]) >= {"id", "number", "requester", "purpose", "amount", "stage", "status", "settlement",
                                   "updated_at", "entity_id"}
    s4 = b["PD-MNT2-4"]["settlement"]
    assert (s4["spent"], s4["refund_due"], s4["reimburse_due"]) == (750_000, 0, 0), s4
    # Halaman: 4 baris, ukuran 3 → halaman 2 berisi 1 baris; total tetap 4.
    r = await klien.get(WL, headers=kepala_admin, params={"page": 2, "page_size": 3})
    assert r.status_code == 200 and r.json()["total"] == 4 and len(r.json()["items"]) == 1, r.text


# ── U4 — saringan tahap: satu baris PD-3, hutang reimburse 1.800.000 − 1.500.000 = 300.000 ───────────────────────────
async def test_MNT2_U4_saring_dipertanggungjawabkan(klien, kepala_admin, siap):
    r = await klien.get(WL, headers=kepala_admin, params={"stage": "dipertanggungjawabkan"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["total"] == 1 and [x["number"] for x in j["items"]] == ["PD-MNT2-3"], j
    s = j["items"][0]["settlement"]
    assert s["number"] == "STL-MNT2-3" and s["status"] == "posted_to_gl"
    assert s["spent"] == 1_800_000 and s["refund_due"] == 0
    assert s["reimburse_due"] == 300_000 == 1_800_000 - 1_500_000
    # jumlah per tahap tetap seluruh daftar (chip), bukan hanya tahap terpilih
    assert sum(j["stage_counts"].values()) == 4


# ── U5 — Tanpa Acuan ber-cash_advance.view saja (pemilik PD-1): baris = GET /api/cash-advances; reimburse null ────────
async def test_MNT2_U5_tanpa_acuan_hanya_cash_advance_view(klien, db, sesi, peran_tanpa_acuan, siap):
    rid = await peran_tanpa_acuan({"cash_advance": ["view"]}, label="Tanpa Acuan PD lihat MNT2")
    u = {**PEMILIK, "email": "pemilik.mnt2@uji.id", "role": rid, "status": "active", "home_entity_id": KSC,
         "allowed_entity_ids": [KSC], "created_at": now_iso()}
    if not await db.users.find_one({"id": u["id"]}):
        await db.users.insert_one(dict(u))
    h = await sesi(u)
    r = await klien.get(WL, headers=h)
    assert r.status_code == 200, r.text
    ref = await klien.get("/api/cash-advances", headers=h)
    assert ref.status_code == 200, ref.text
    assert {x["id"] for x in r.json()["items"]} == {x["id"] for x in ref.json()}, (r.json(), ref.json())
    assert any(x["number"] == "PD-MNT2-1" for x in r.json()["items"])
    for x in r.json()["items"]:
        if x["settlement"]:
            assert x["settlement"]["reimburse_due"] is None, x


# ── U6 — Sopir: 403 ───────────────────────────────────────────────────────────────────────────────────────────────
async def test_MNT2_U6_sopir_ditolak(klien, akun, sesi, peran_sopir, siap):
    r = await klien.get(WL, headers=await sesi(await akun(peran_sopir)))
    assert r.status_code == 403, r.text
    assert "cash_advance" not in r.json()["detail"]   # pesan untuk manusia (Z6), tanpa kode izin


# ── U7 — tahap tidak dikenal: 400 ─────────────────────────────────────────────────────────────────────────────────
async def test_MNT2_U7_tahap_aneh_400(klien, kepala_admin, siap):
    r = await klien.get(WL, headers=kepala_admin, params={"stage": "aneh"})
    assert r.status_code == 400 and r.json()["detail"] == "Tahap tidak dikenal.", r.text


# ── U11 — Manajer Kosong 403; admin mode Semua PT 200 dengan baris berlabel PT ─────────────────────────────────────
async def test_MNT2_U11_manajer_kosong_dan_semua_pt(klien, akun, sesi, peran_manajer_kosong, kepala_admin, siap):
    h = await sesi(await akun(await peran_manajer_kosong()))
    assert (await klien.get(WL, headers=h)).status_code == 403
    r = await klien.get(WL, headers={**kepala_admin, "X-Entity-Id": "all"})
    assert r.status_code == 200, r.text
    j = r.json()
    pt = {x["number"]: x["entity_id"] for x in j["items"]}
    assert pt["PD-MNT2-K"] == KANDA and pt["PD-MNT2-1"] == KSC, pt
    assert all(x["entity_id"] for x in j["items"])
    assert j["total"] == 5   # 4 KSC + 1 KANDA


# ── U8 — daftar periksa: dua tautan menunjuk seksi Tutup Buku; butir & aturan penghalang tetap ──────────────────────
CEKLIS_PK43 = ["periode_berakhir", "tidak_bentrok", "suspense_nol", "posting_gagal", "neraca_saldo", "stok_cocok",
               "bank_cocok", "dana_dalam_perjalanan", "antar_pt_cocok", "buka_periode_aktif", "penyusutan",
               "gaji"]   # Kas & Bank 1 (Tugas 4) — + butir dana dalam perjalanan


async def test_MNT2_U8_tautan_daftar_periksa_ke_seksi_tutup_buku(klien, kepala_admin):
    r = await klien.get("/api/finance/closing/checklist", headers=kepala_admin,
                        params={"period_type": "month", "period_key": "2026-02", "entity_id": KSC})
    assert r.status_code == 200, r.text
    j = r.json()
    butir = {it["key"]: it for it in j["items"]}
    assert [it["key"] for it in j["items"]] == CEKLIS_PK43
    assert butir["suspense_nol"]["link"] == {"view": "closing", "preset": {"seksi": "akun-sementara"}}
    assert butir["stok_cocok"]["link"] == {"view": "closing", "preset": {"seksi": "persediaan"}}
    assert butir["posting_gagal"]["link"]["view"] == "posting-failures"
    assert butir["buka_periode_aktif"]["link"]["view"] == "period-unlock"
    # Status dan aturan penghalang tidak berubah: database bersih → akun penampung 0 (beres), periode Feb 2026 sudah
    # berakhir; `can_close` = tidak ada butir `blocking` (aturan PK-43).
    assert butir["suspense_nol"]["status"] == "ok" and butir["periode_berakhir"]["status"] == "ok"
    assert j["can_close"] is (not any(it["status"] == "blocking" for it in j["items"]))
    assert "Tutup Buku" in butir["suspense_nol"]["detail"] or butir["suspense_nol"]["status"] == "ok"
