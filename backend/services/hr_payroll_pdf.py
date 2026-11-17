"""HRD H4 — Payslip PDF (reportlab). Slip gaji ringkas, profesional, Bahasa Indonesia.

PY-T1 — isi slip dari fungsi murni `payslip_pdf_rows(slip)`: satu baris per komponen (persen BPJS dari `rate` komponen
di slip, bukan ditulis mati), dikelompokkan PENERIMAAN · POTONGAN · GAJI BERSIH DITERIMA · TANGGUNGAN PERUSAHAAN
(INFORMASI). Masa pajak terakhir berlabel "PPh 21 (hitung ulang tahunan)". Slip lama tanpa `components` dibaca dari
kolomnya (baris tetap seperti dulu, tanpa persen).
"""
from io import BytesIO
from typing import Any, Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from core_utils import rupiah

NAVY = colors.HexColor("#0058CC")
GRAY = colors.HexColor("#6B6B73")
DARK = colors.HexColor("#1A1A1F")
LINE = colors.HexColor("#E1E4E8")


def _rp(v: Any) -> str:
    """Alias tipis ke `core_utils.rupiah` — satu sumber format uang untuk seluruh backend."""
    return rupiah(v)


SEC_IN, SEC_OUT, SEC_NET, SEC_ER = ("PENERIMAAN", "POTONGAN", "GAJI BERSIH DITERIMA",
                                    "TANGGUNGAN PERUSAHAAN (INFORMASI)")
LBL_GROSS, LBL_DED, LBL_NET = "Penghasilan bruto", "Total potongan", "Gaji bersih diterima"


def _pct_id(v: Any) -> str:
    """1.0 → "1%", 3.7 → "3,7%", 1.75 → "1,75%" (persen Indonesia, tanpa nol tak berarti)."""
    t = f"{float(v or 0):.2f}".rstrip("0").rstrip(".")
    return f"{t.replace('.', ',')}%"


def _pph_label(slip: Dict[str, Any], comp: Dict[str, Any]) -> str:
    if (comp.get("method") or slip.get("pph21_method")) == "annual_pasal17":
        return "PPh 21 (hitung ulang tahunan)"
    rate = comp.get("rate")
    if rate is None:
        rate = float(slip.get("pph21_rate", 0) or 0) * 100
    detail = slip.get("pph21_month_detail") or {}
    if float(detail.get("prior_pph21") or 0):
        return f"PPh 21 (TER {_pct_id(rate)} atas bruto sebulan, dikurangi yang sudah dipotong)"
    return f"PPh 21 (TER {_pct_id(rate)})"


def _label(slip: Dict[str, Any], c: Dict[str, Any]) -> str:
    if c.get("statutory_code") == "pph21":
        return _pph_label(slip, c)
    lbl = c.get("label") or c.get("name") or c.get("code") or ""
    if c.get("statutory_code") and c.get("rate") not in (None, ""):
        return f"{lbl} ({_pct_id(c['rate'])})"
    return lbl


def payslip_pdf_rows(slip: Dict[str, Any]) -> List[Tuple[str, str, float]]:
    """Baris slip PDF `(bagian, label, nilai)` — fungsi murni (tanpa database), dipakai `payslip_pdf_bytes`."""
    rows: List[Tuple[str, str, float]] = []
    comps = slip.get("components") or []
    num = lambda v: round(float(v or 0), 2)   # noqa: E731
    if comps:
        for c in comps:
            if c.get("kind") == "pendapatan":
                rows.append((SEC_IN, _label(slip, c), num(c.get("amount"))))
        rows.append((SEC_IN, LBL_GROSS, num(slip.get("gross"))))
        ded = 0.0
        for c in comps:
            if c.get("kind") == "potongan":
                rows.append((SEC_OUT, _label(slip, c), num(c.get("amount"))))
                ded += float(c.get("amount") or 0)
        rows.append((SEC_OUT, LBL_DED, num(ded)))
        rows.append((SEC_NET, LBL_NET, num(slip.get("net"))))
        for c in comps:
            if c.get("kind") == "tanggungan_perusahaan":
                rows.append((SEC_ER, _label(slip, c), num(c.get("amount"))))
        return rows
    # Slip lama (sebelum PY-T1): baris tetap dari kolom.
    rows += [(SEC_IN, "Gaji Pokok", num(slip.get("base_salary"))), (SEC_IN, "Tunjangan", num(slip.get("allowances"))),
             (SEC_IN, "Lembur", num(slip.get("overtime")))]
    if float(slip.get("commission", 0) or 0) > 0:
        rows.append((SEC_IN, "Komisi / insentif penjualan", num(slip.get("commission"))))
    rows.append((SEC_IN, LBL_GROSS, num(slip.get("gross"))))
    emp_b = slip.get("bpjs_emp", {}) or {}
    rows += [(SEC_OUT, "BPJS Kesehatan", num(emp_b.get("kesehatan"))), (SEC_OUT, "BPJS JHT", num(emp_b.get("jht"))),
             (SEC_OUT, "BPJS JP", num(emp_b.get("jp"))), (SEC_OUT, _pph_label(slip, {}), num(slip.get("pph21"))),
             (SEC_OUT, LBL_DED, num(float(slip.get("bpjs_emp_total", 0) or 0) + float(slip.get("pph21", 0) or 0)))]
    rows.append((SEC_NET, LBL_NET, num(slip.get("net"))))
    er_b = slip.get("bpjs_er", {}) or {}
    rows += [(SEC_ER, "BPJS Kesehatan (perusahaan)", num(er_b.get("kesehatan"))),
             (SEC_ER, "BPJS JHT + JP (perusahaan)", num(float(er_b.get("jht", 0) or 0) + float(er_b.get("jp", 0) or 0))),
             (SEC_ER, "BPJS JKK + JKM", num(float(er_b.get("jkk", 0) or 0) + float(er_b.get("jkm", 0) or 0)))]
    return rows


def _masa(period: str) -> str:
    """K-SDM-01 (audit pelatihan 18 Nov) — slip dibaca karyawan: "Oktober 2026", bukan kode "2026-10"."""
    try:
        from services.periodic_posting import label_periode
        return label_periode(period)
    except Exception:  # noqa: BLE001 — periode lama/tak sah tetap tercetak apa adanya
        return str(period or "")


def payslip_pdf_bytes(slip: Dict[str, Any], entity_name: str = "Kain Nusantara") -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    x0 = 18 * mm
    y = h - 20 * mm

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(x0, y, "SLIP GAJI")
    c.setFillColor(GRAY)
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 18 * mm, y, entity_name)
    c.drawRightString(w - 18 * mm, y - 12, f"No. {slip.get('number', '')}")
    y -= 26
    c.setStrokeColor(NAVY)
    c.setLineWidth(2)
    c.line(x0, y, w - 18 * mm, y)
    y -= 18

    # Info karyawan
    c.setFillColor(DARK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x0, y, slip.get("employee_name", ""))
    c.setFont("Helvetica", 9)
    c.setFillColor(GRAY)
    jenis = {"thr": "  ·  Proses THR", "susulan": "  ·  Proses susulan"}.get(slip.get("run_type") or "", "")
    c.drawString(x0, y - 13, f"Periode: {_masa(slip.get('period', ''))}   ·   PTKP: {slip.get('ptkp_status', '')}   ·   "
                             f"TER-{slip.get('ter_category', '')}{jenis}")
    bank = slip.get("bank", {}) or {}
    if bank.get("acc_no"):
        c.drawString(x0, y - 26, f"Bank: {bank.get('bank_name', '')} {bank.get('acc_no', '')} a.n. {bank.get('acc_name', '')}")
    y -= 44

    def section(title: str, yy: float) -> float:
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x0, yy, title)
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(x0, yy - 4, w - 18 * mm, yy - 4)
        return yy - 18

    def row(label: str, value: Any, yy: float, bold: bool = False) -> float:
        c.setFillColor(DARK)
        c.setFont("Helvetica-Bold" if bold else "Helvetica", 9.5)
        c.drawString(x0 + 4, yy, label)
        c.drawRightString(w - 18 * mm, yy, _rp(value))
        return yy - 15

    rows = payslip_pdf_rows(slip)
    for sec in (SEC_IN, SEC_OUT):
        y = section(sec, y)
        for _, label, value in (r for r in rows if r[0] == sec):
            y = row(label, value, y, bold=label in (LBL_GROSS, LBL_DED))
        y -= 10

    # Gaji bersih diterima
    net = next((v for s_, _, v in rows if s_ == SEC_NET), slip.get("net"))
    c.setFillColor(NAVY)
    c.rect(x0, y - 6, w - 36 * mm, 24, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(x0 + 6, y + 2, SEC_NET)
    c.drawRightString(w - 20 * mm, y + 2, _rp(net))
    y -= 34

    er_rows = [r for r in rows if r[0] == SEC_ER]
    if er_rows:
        y = section(SEC_ER, y)
        for _, label, value in er_rows:
            y = row(label, value, y)

    c.setFillColor(GRAY)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(x0, 18 * mm, "Slip ini dihasilkan otomatis oleh sistem ERP Kain Nusantara. Rahasia & hanya untuk karyawan bersangkutan.")
    c.showPage()
    c.save()
    return buf.getvalue()
