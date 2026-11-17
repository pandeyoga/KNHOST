"""Pelatihan 18 Nov (audit dokumen cetak) — kop slip gaji = nama PT di Profil PT (dulu field `name` yang tidak ada →
selalu "Kain Nusantara")."""
import pytest

import routers.hr_payroll as R

pytestmark = pytest.mark.anyio


async def test_kop_slip_gaji_memakai_nama_pt(klien, kepala_admin, db, monkeypatch):
    await db.business_entities.insert_one({"id": "ent_kop_uji", "status": "active", "legal_name": "PT Kop Uji Tekstil",
                                           "short_name": "Kop Uji"})
    slip = {"id": "slip_kop_uji", "number": "SLIP-KOP-1", "entity_id": "ent_kop_uji"}
    dipakai = {}

    async def _slip(_id):
        return slip

    async def _boleh(*_a, **_k):
        return True

    def _pdf(s, nama):
        dipakai["nama"] = nama
        return b"%PDF-1.4 uji"

    monkeypatch.setattr(R.pay, "get_payslip", _slip)
    monkeypatch.setattr(R, "_can_view_slip", _boleh)
    monkeypatch.setattr(R, "payslip_pdf_bytes", _pdf)
    r = await klien.get("/api/hr/payslips/slip_kop_uji/pdf", headers=kepala_admin)
    assert r.status_code == 200, r.text
    assert dipakai["nama"] == "PT Kop Uji Tekstil"
