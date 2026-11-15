"""CR-T3 serah-terima (a) — mesin gerbang kredit `services/credit_gate.evaluate` diuji LANGSUNG (U1–U3, U11–U13) +
tes pembanding 20 kombinasi terhadap gerbang lama (`docs/blueprint/unit/CR-T3.md`, langkah kerja 1–2).

Fixture G1 (`pembantu_crt3.g1`, SISIP): plafon khusus Rp 10.000.000; terkirim 6.000.000 + belum dikirim 2.000.000 −
titipan 500.000 = eksposur 7.500.000. Hitung tangan di tiap uji. Semua kunci bawaan kecuali disebut.
"""
from __future__ import annotations

import pytest

from pembantu_crt3 import JUTA, KANDA, KSC, atur, cabut, g1, kode, pesanan_terbuka, pesanan_terkirim, profil, uid

pytestmark = pytest.mark.anyio


async def _nilai(cid: str, entitas: str, jumlah: float, term: str = "NET30", titik: str = "pesanan_dibuat"):
    from services import credit_gate as cg
    return await cg.evaluate(customer_id=cid, entity_id=entitas, checkpoint=titik, order_amount=jumlah,
                             term_code=term)


# ── U1 — mendekati plafon = peringatan ───────────────────────────────────────────────────────────────────────────────
async def test_CRT3_U1_mendekati_plafon_peringatan(db):
    f = await g1(db)
    h = await _nilai(f["cid"], KANDA, 2 * JUTA)
    # 7.500.000 + 2.000.000 = 9.500.000 ≥ 80 % × 10.000.000 = 8.000.000 → peringatan; 9.500.000 ≤ 10.000.000 → bukan tahan
    assert h["checked"] is True
    assert h["result"] == "peringatan", h["reasons"]
    assert kode(h) == ["MENDEKATI_PLAFON"]
    e = h["exposure"]
    assert (e["ar_delivered"], e["open_orders"], e["deposit"], e["this_order"], e["total"]) == \
        (6 * JUTA, 2 * JUTA, 500_000, 2 * JUTA, 9_500_000)
    assert h["limit"]["credit_limit"] == 10 * JUTA and h["limit"]["available"] == 500_000
    assert h["reasons"][0]["message"] == "Eksposur sudah 95 % dari plafon."


# ── U2 — lewat plafon = tahan ────────────────────────────────────────────────────────────────────────────────────────
async def test_CRT3_U2_lewat_plafon_tahan(db):
    f = await g1(db)
    h = await _nilai(f["cid"], KANDA, 3 * JUTA)
    # 7.500.000 + 3.000.000 = 10.500.000 > 10.000.000 → LEWAT_PLAFON → tahan
    assert h["result"] == "tahan" and "LEWAT_PLAFON" in kode(h), h["reasons"]
    assert h["exposure"]["total"] == 10_500_000
    msg = next(r["message"] for r in h["reasons"] if r["code"] == "LEWAT_PLAFON")
    assert msg == "Eksposur Rp 10.500.000 melewati plafon Rp 10.000.000."
    assert h["override"] is None and h["pay_before_ship"] is False


# ── U3 — titipan tidak mengurangi di satu PT; PT lain tidak berubah ─────────────────────────────────────────────────
async def test_CRT3_U3_titipan_per_pt(db):
    p = await g1(db, entitas=KANDA)
    q = await g1(db, entitas=KSC)
    await atur("ar.eksposur_titipan_mengurangi", False, KANDA)
    try:
        hp = await _nilai(p["cid"], KANDA, 2_500_000)
        hq = await _nilai(q["cid"], KSC, 2_500_000)
    finally:
        await cabut("ar.eksposur_titipan_mengurangi", KANDA)
    # P: 6.000.000 + 2.000.000 (titipan tidak dihitung) + 2.500.000 = 10.500.000 > 10.000.000 → tahan
    assert hp["result"] == "tahan" and hp["exposure"]["total"] == 10_500_000 and hp["exposure"]["deposit"] == 0
    assert hp["counted"]["deposit"] is False
    # Q (ent_ksc, kunci bawaan): 7.500.000 + 2.500.000 = 10.000.000 → tidak melewati (> 10.000.000 salah)
    assert hq["result"] == "peringatan" and hq["exposure"]["total"] == 10 * JUTA, hq["reasons"]
    assert "LEWAT_PLAFON" not in kode(hq)


# ── U11 — blokir manual: tahan, izin kredit tidak melepas ────────────────────────────────────────────────────────────
async def test_CRT3_U11_blokir_manual_izin_tidak_terpakai(db):
    from services import credit_gate as cg
    f = await g1(db, credit_status="blokir_manual", block_reason="Cek ditolak bank")
    cro = uid("cro")
    await db.credit_overrides.insert_one({
        "id": cro, "customer_id": f["cid"], "entity_id": KANDA, "status": "approved", "scope": "pelanggan",
        "amount": 5 * JUTA, "remaining_amount": 5 * JUTA, "valid_until": "", "used_by": [], "decided_at": "2026-11-01"})
    h = await _nilai(f["cid"], KANDA, 1 * JUTA)
    assert h["result"] == "tahan" and kode(h)[0] == "BLOKIR_MANUAL", h["reasons"]
    assert h["reasons"][0]["message"] == "Pelanggan diblokir manual: Cek ditolak bank."
    assert h["override"] is None
    assert cg.sisa_izin(await db.credit_overrides.find_one({"id": cro})) == 5 * JUTA


# ── U12 — termin di luar daftar = tolak ─────────────────────────────────────────────────────────────────────────────
async def test_CRT3_U12_termin_tidak_diizinkan(db):
    f = await g1(db, allowed_term_codes=["CASH", "NET14"])
    h = await _nilai(f["cid"], KANDA, 1 * JUTA, term="NET30")
    # tolak menang atas peringatan (8.500.000 ≥ 8.000.000 → MENDEKATI_PLAFON ikut tercatat)
    assert h["result"] == "tolak" and kode(h) == ["TERMIN_TIDAK_DIIZINKAN", "MENDEKATI_PLAFON"], h["reasons"]
    assert h["reasons"][0]["message"] == ("Termin Kredit NET 30 Hari tidak diizinkan untuk pelanggan ini. Termin yang "
                                          "diizinkan: Tunai / POS, Kredit NET 14 Hari.")
    h2 = await _nilai(f["cid"], KANDA, 1 * JUTA, term="NET14")
    # 7.500.000 + 1.000.000 = 8.500.000 ≥ 8.000.000 → peringatan (lolos dibuat)
    assert h2["result"] == "peringatan", h2["reasons"]


# ── U13 — telat > hari blokir: CBD lolos bayar penuh dulu (K-27); NET30 tahan ──────────────────────────────────────
async def test_CRT3_U13_telat_cbd_bayar_dulu(db):
    f = await g1(db, telat=20)
    h = await _nilai(f["cid"], KANDA, 1 * JUTA, term="CBD")
    # telat 20 hari > 14 (bawaan `ar.overdue_block_days`) → TELAT tahan; CBD (dp 100 %) → lolos, bayar penuh dulu
    assert h["raw_result"] == "tahan" and "TELAT" in kode(h)
    assert h["result"] == "lolos" and h["pay_before_ship"] is True
    assert next(r["message"] for r in h["reasons"] if r["code"] == "TELAT") == \
        "Ada tagihan telat 20 hari (batas 14 hari) senilai Rp 6.000.000."
    h2 = await _nilai(f["cid"], KANDA, 1 * JUTA, term="NET30")
    assert h2["result"] == "tahan" and "TELAT" in kode(h2) and h2["pay_before_ship"] is False
    # K-27 hanya di titik "pesanan dibuat"
    h3 = await _nilai(f["cid"], KANDA, 1 * JUTA, term="CBD", titik="periksa_ulang")
    assert h3["result"] == "tahan"


async def test_CRT3_titik_mati_tidak_memeriksa(db):
    """Langkah 1 `evaluate` — titik periksa mati untuk PT itu → lolos tanpa diperiksa; titik bawaan lain mati."""
    f = await g1(db)
    await atur("ar.periksa_kredit_pesanan_dibuat", False, KANDA)
    try:
        h = await _nilai(f["cid"], KANDA, 5 * JUTA)
    finally:
        await cabut("ar.periksa_kredit_pesanan_dibuat", KANDA)
    assert (h["result"], h["checked"]) == ("lolos", False)
    for titik in ("pesanan_diubah", "lepas_gudang", "surat_jalan"):
        h = await _nilai(f["cid"], KANDA, 5 * JUTA, titik=titik)
        assert (h["result"], h["checked"]) == ("lolos", False), titik


async def test_CRT3_plafon_kedaluwarsa_keterangan(db):
    f = await g1(db, limit_valid_until="2026-01-31")
    h = await _nilai(f["cid"], KANDA, 1 * JUTA)
    # plafon khusus kedaluwarsa → plafon bawaan PT (0 = tanpa batas) → tidak ada alasan plafon; satu keterangan
    assert h["limit"]["limit_source"] == "kedaluwarsa" and h["result"] == "lolos"
    assert kode(h) == ["PLAFON_KEDALUWARSA"]
    assert h["reasons"][0]["message"] == "Plafon khusus berakhir 31 Jan 2026; dipakai plafon bawaan PT."


async def test_CRT3_giro_belum_cair_menambah_eksposur(db):
    f = await g1(db)
    await db.ar_receipts.insert_one({"id": uid("rcp"), "customer_id": f["cid"], "entity_id": KANDA, "amount": 3 * JUTA,
                                     "method": "giro", "status": "posted", "bank_verified": False,
                                     "receipt_date": "2026-11-10", "created_at": "2026-11-10T08:00:00+00:00"})
    h = await _nilai(f["cid"], KANDA, 0)
    # 6.000.000 + 2.000.000 + giro 3.000.000 − 500.000 = 10.500.000 > 10.000.000 → tahan
    assert h["exposure"]["giro_outstanding"] == 3 * JUTA and h["exposure"]["total"] == 10_500_000
    assert h["result"] == "tahan"
    await atur("ar.eksposur_giro_belum_cair", False, KANDA)
    try:
        h2 = await _nilai(f["cid"], KANDA, 0)
    finally:
        await cabut("ar.eksposur_giro_belum_cair", KANDA)
    assert h2["exposure"]["total"] == 7_500_000 and h2["result"] == "lolos"


# ── Tes pembanding (langkah kerja 2): 20 kombinasi, kunci bawaan, titik "pesanan dibuat" ────────────────────────────
L = 10 * JUTA
#: (plafon, terkirim, belum dikirim, telat hari, nilai pesanan) → tingkat gerbang lama. Satu PT, tanpa titipan/giro
#: (selisih yang didaftar di bagian risiko: PT dan titipan). Aturan lama: blocked bila plafon > 0 dan (piutang + pesanan >
#: plafon atau piutang ≥ plafon) atau telat > 14; warning bila (piutang + pesanan ≥ 80 % plafon) atau telat ≥ 1.
KOMBINASI = [
    ((0, 0, 0, 0, 1 * JUTA), "ok"),
    ((0, 6 * JUTA, 2 * JUTA, 0, 3 * JUTA), "ok"),              # tanpa plafon
    ((0, 6 * JUTA, 0, 10, 1 * JUTA), "warning"),               # telat 10 ≤ 14
    ((0, 6 * JUTA, 0, 20, 1 * JUTA), "blocked"),               # telat 20 > 14
    ((L, 0, 0, 0, 1 * JUTA), "ok"),                            # 1 jt < 8 jt
    ((L, 6 * JUTA, 0, 0, 1 * JUTA), "ok"),                     # 7 jt < 8 jt
    ((L, 6 * JUTA, 2 * JUTA, 0, 0), "warning"),                # 8 jt ≥ 8 jt
    ((L, 6 * JUTA, 2 * JUTA, 0, 1_900_000), "warning"),        # 9,9 jt
    ((L, 6 * JUTA, 2 * JUTA, 0, 2 * JUTA), "warning"),         # 10 jt tidak > 10 jt; piutang 8 jt < 10 jt
    ((L, 6 * JUTA, 2 * JUTA, 0, 2_500_000), "blocked"),        # 10,5 jt > 10 jt
    ((L, 9 * JUTA, 0, 0, 500_000), "warning"),                 # 9,5 jt
    ((L, 9 * JUTA, 1 * JUTA, 0, 0), "blocked"),                # piutang 10 jt ≥ 10 jt
    ((L, 4 * JUTA, 0, 0, 4 * JUTA), "warning"),                # 8 jt ≥ 8 jt
    ((L, 4 * JUTA, 0, 0, 3_900_000), "ok"),                    # 7,9 jt
    ((L, 4 * JUTA, 0, 5, 0), "warning"),                       # telat 5
    ((L, 4 * JUTA, 0, 14, 1 * JUTA), "warning"),               # telat 14 tidak > 14
    ((L, 4 * JUTA, 0, 15, 1 * JUTA), "blocked"),               # telat 15 > 14
    ((L, 6 * JUTA, 2 * JUTA, 10, 2_500_000), "blocked"),       # plafon
    ((L, 0, 2 * JUTA, 0, 7 * JUTA), "warning"),                # 9 jt
    ((L, 0, 2 * JUTA, 0, 9 * JUTA), "blocked"),                # 11 jt > 10 jt
]
SETARA = {"ok": ("lolos",), "warning": ("peringatan",), "blocked": ("tahan", "tolak")}


@pytest.mark.parametrize("nomor", range(len(KOMBINASI)))
async def test_CRT3_pembanding_gerbang_lama(db, nomor):
    (plafon, kirim, buka, telat, jumlah), lama_harap = KOMBINASI[nomor]
    cid = uid("cus")
    await db.customers.insert_one({"id": cid, "name": f"Toko Pembanding {nomor}", "entity_id": KSC, "status": "active"})
    if plafon:
        await profil(db, cid, KSC, plafon=plafon)
    if kirim:
        await pesanan_terkirim(db, cid, KSC, kirim, telat=telat)
    if buka:
        await pesanan_terbuka(db, cid, KSC, buka)
    h = await _nilai(cid, KSC, jumlah)
    assert h["result"] in SETARA[lama_harap], (KOMBINASI[nomor], h["result"], h["reasons"])
    try:   # serah-terima (a): gerbang lama masih ada → dibandingkan langsung; (b) menghapusnya (D8) → tabel beku di atas
        from services.customer_service import evaluate_credit_gate
    except ImportError:
        return
    cust = await db.customers.find_one({"id": cid}, {"_id": 0})
    lama = await evaluate_credit_gate(cust, jumlah)
    assert lama["level"] == lama_harap, (KOMBINASI[nomor], lama)
