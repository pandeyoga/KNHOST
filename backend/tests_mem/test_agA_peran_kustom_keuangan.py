"""Uji peran kustom 18 Nov 2026 (agen A, perburuan cacat) — gerbang NAMA PERAN yang tersisa di keuangan.

Langkah ulang di layar (lingkungan lokal, peserta latihan 93): peran kustom "UJI-KUSTOM Salinan Finance" (TANPA peran dasar,
izin disalin dari Finance → memegang `penalty.waive`) membuka Keuangan › Piutang › Rencana & Denda › Antrean Denda →
[Bebaskan] tampil → simpan → 400 "Pembebasan denda wajib disetujui manager — ajukan lewat penyetuju.". Peran kustom
ber-dasar Manajer dengan izin yang sama berhasil membebaskan nota yang sama (200).

U1  pesan penolakan (§3 Z6): label peran manusia (Manajer, Admin, Finance), bukan id `manager`/`admin`, dan tanpa
    "ajukan lewat penyetuju" (alur pengajuan bebas-denda tidak ada) — bebas & ubah nominal denda, penyelesaian kasus.
U2  TEMUAN TERBUKA (xfail ketat): pemegang izin `penalty.waive` tanpa peran dasar tetap ditolak karena
    `penalty_service.waive` memutus dari `role_in(peran, (payment.penalty_waive_approver_role, "admin"))`. Perbaikan yang
    benar memindahkan penyetuju ke Aturan Persetujuan (jenis dokumen baru di `approval_policy_service`, wilayah lain) —
    begitu diperbaiki, xfail ini menjadi merah dan wajib dibalik menjadi uji biasa.
"""
import datetime
import itertools
import re

import pytest

pytestmark = pytest.mark.anyio
E1 = "ent_ksc"
_n = itertools.count(1)
TANPA_DASAR = {"id": "u_agA", "name": "Uji Kustom", "role": "cr_agA_tanpa_dasar"}
ID_MENTAH = re.compile(r"\b(manager|admin)\b")


@pytest.fixture(scope="module")
async def alasan(aplikasi, db):
    from services import amendment_service
    await amendment_service.ensure_reasons()


async def _nota(db) -> str:
    i = next(_n)
    nid = f"pnl_agA_{i}"
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await db.penalties.insert_one({
        "id": nid, "number": f"DN-DENDA-AGA-{i}", "entity_id": E1, "doc_type": "sales_order",
        "doc_id": f"so_aga_{i}", "doc_number": f"SO-AGA-{i}", "plan_id": "", "line_seq": 0,
        "due_date": "2026-10-01", "period_key": "2026-10-01|2026-11", "customer_id": "cus_aga",
        "customer_name": "Toko Uji Peran", "base_amount": 5000000, "base": "installment", "amount": 100000.0,
        "original_amount": 100000.0, "days_late": 30, "billable_days": 30, "rate_pct_per_month": 2.0,
        "grace_days": 0, "cap_pct": 0, "status": "draft", "status_label": "Usulan", "paid_amount": 0.0,
        "je_id": "", "explain": [], "created_by": "uji", "created_at": now, "updated_at": now, "refs": []})
    return nid


def _pesan_manusia(msg: str) -> None:
    assert not ID_MENTAH.search(msg), msg
    assert "Manajer" in msg and "Admin" in msg and "Finance" in msg, msg
    assert "ajukan lewat penyetuju" not in msg, msg


async def test_U1_pesan_bebas_dan_ubah_denda_berlabel(db, alasan):
    from services import penalty_service as ps
    nid = await _nota(db)
    with pytest.raises(ps.PenaltyError) as e:
        await ps.waive(nid, "penalty_waiver", "uji", TANPA_DASAR)
    _pesan_manusia(str(e.value))
    assert str(e.value).startswith("Pembebasan denda wajib diputus")
    with pytest.raises(ps.PenaltyError) as e:
        await ps.adjust(nid, 50000, "penalty_waiver", "uji", TANPA_DASAR)
    _pesan_manusia(str(e.value))
    assert (await db.penalties.find_one({"id": nid}))["status"] == "draft"


def test_U1_pesan_kasus_di_atas_ambang_berlabel():
    from services.finance_case_service import CaseError, _assert_authority
    pol = {"approver_role": "manager", "approval_above": 5_000_000, "refund_max": 10_000_000}
    with pytest.raises(CaseError) as e:
        _assert_authority({"sensitive": False}, 6_000_000, pol, TANPA_DASAR)
    _pesan_manusia(str(e.value))
    with pytest.raises(CaseError) as e:   # di atas batas pengembalian dana: hanya Admin
        _assert_authority({"sensitive": True}, 12_000_000, pol, {"role": "manager"})
    assert not ID_MENTAH.search(str(e.value)) and "Manajer" in str(e.value), str(e.value)


@pytest.mark.xfail(strict=True, reason="KU-01 — bebas denda diputus nama peran (penalty_service.waive → role_in), "
                                        "bukan izin/Aturan Persetujuan: peran kustom tanpa peran dasar ditolak")
async def test_U2_pemegang_izin_bebas_denda_tanpa_peran_dasar(db, alasan):
    from services import penalty_service as ps
    nid = await _nota(db)
    await ps.waive(nid, "penalty_waiver", "uji", TANPA_DASAR)
    assert (await db.penalties.find_one({"id": nid}))["status"] == "waived"
