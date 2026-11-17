"""K-SDM-01 (audit pelatihan 18 Nov) — slip gaji PDF menulis masa gaji "Oktober 2026", bukan kode "2026-10"."""
import base64
import re
import zlib

from services.hr_payroll_pdf import payslip_pdf_bytes


def _teks(pdf: bytes) -> str:
    """Isi aliran halaman reportlab (ASCII85 + Flate) tanpa pustaka PDF tambahan."""
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        raw = m.group(1).strip()
        for dec in (lambda b: zlib.decompress(base64.a85decode(b, adobe=b.endswith(b"~>") and b.startswith(b"<~"))),
                    lambda b: zlib.decompress(base64.a85decode(b.rstrip(b"~>").rstrip())), zlib.decompress):
            try:
                out.append(dec(raw).decode("latin-1"))
                break
            except Exception:  # noqa: BLE001
                continue
    return "\n".join(out)


def test_slip_menulis_masa_gaji_dengan_nama_bulan():
    slip = {"number": "KSC/SLIP-1", "period": "2026-10", "employee_name": "Andi Pratama", "ptkp_status": "K1",
            "ter_category": "B", "run_type": "susulan", "net": 7_920_000}
    t = _teks(payslip_pdf_bytes(slip, "Sukacita Textile"))
    assert "Periode: Oktober 2026" in t, t[:400]
    assert "2026-10" not in t
