"""Seed Sampel Uji OCR dari foto SJ nyata pemilik (tests/fixtures_sj) + kunci jawaban yang disalin manual.

Idempoten per label. Jalankan: cd /app/backend && python ../scripts/seed_ocr_samples.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

from db import db  # noqa: E402
from services import ocr_sample_service as svc  # noqa: E402
from services import storage_service as st  # noqa: E402

DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures_sj"
KSC, CSG = "ent_ksc", "ent_b92565b69e9e"


def L(qty, unit, rolls, po=None, desc=""):
    return {"qty": qty, "unit": unit, "rolls": rolls, "po_ref": po, "description": desc, "is_non_stock": False}


SAMPLES = [
    (KSC, "sj1.jpeg", "SJ pink 26/SEP/PCK/SRJL/405 (miring 90°)", "", {
        "dn_number": "26/SEP/PCK/SRJL/405", "dn_date": "2026-09-24", "lines": [
            L(994, "yard", 8, "3374/SCB/0926", "KAIN JAQUARD ALEEZA BUNGA BORDIR 14098"),
            L(1202, "yard", 8, "3351/SCB/0926", "KAIN JAQUARD AMIRA CASHMERE 14237"),
            L(1240, "yard", 8, "3382/SCB/0926", "KAIN JAQUARD ALEEZA BUNGA ABSTRAK 14097")]}),
    (KSC, "sj4.jpeg", "ADETEX AF/PD/LF/07-005/26 (miring, pudar)", "ADETEX", {
        "dn_number": "AF/PD/LF/07-005/26", "dn_date": "", "lines": [L(4849, "yard", 47), L(495, "yard", 5)]}),
    (CSG, "n_e.jpeg", "SJ Makloon ID1-26/08/0139 RIBKNIT (kg + pcs 2 baris)", "", {
        "dn_number": "ID1-26/08/0139", "dn_date": "2026-08-07", "lines": [
            L(123.05, "kg", 5, None, "RIBKNIT/CST HITAM TUA (1A) lot 071225"),
            L(295.35, "kg", 12, None, "RIBKNIT/CST HITAM TUA (1A) lot 071225A"),
            L(600.9, "kg", 24, None, "RIBKNIT/CST HITAM TUA (1A) lot 071225B")]}),
    (CSG, "n_d.jpeg", "CV SURITEX 09/VIII/26/SJ/DOM ODEZA TWILL (+ sample tulisan tangan)", "C.V. SURITEX", {
        "dn_number": "09/VIII/26/SJ/DOM", "dn_date": "2026-08-04", "lines": [
            L(2186, "yard", 21, "7460/CST/0726", "ODEZA TWILL"), L(19, "yard", 6, "7460/CST/0726", "ODEZA TWILL BS"),
            {"description": "Sample 12 bks + 50 amplop (tulisan tangan)", "qty": None, "unit": "", "rolls": None,
             "po_ref": None, "is_non_stock": True}]}),
    (CSG, "n_c.jpeg", "SJ-3171/08/2026 POKKA PFD MUSI (miring, rincian 19 roll)", "", {
        "dn_number": "SJ-3171/08/2026", "dn_date": "2026-08-29", "lines": [L(2131, "yard", 19, None, "POKKA PFD MUSI TAUPE")]}),
    (CSG, "n_b.jpeg", "PT GRAHA SINAR ANUGRAH DO.000275/CSG-TRD6 (DO + SJ satu lembar)", "PT.GRAHA SINAR ANUGRAH", {
        "dn_number": "DO.000275/CSG-TRD6", "dn_date": "2026-08-13", "lines": [L(143.7, "kg", 6, None, "SNOWFLAKE KNITT INSIGNIA BLUE A")]}),
    (CSG, "n_a.jpeg", "MKC260-052 CHINNO COTTON (asal greige meter vs kirim yard)", "", {
        "dn_number": "MKC260-052", "dn_date": "2026-08-26", "lines": [
            L(1824, "yard", 31, "7424/CST/0726", "M14504 CHINNO COTTON - BW"),
            L(1678, "yard", 26, "7425/CST/0726", "M14505 CHINNO COTTON - Cream")]}),
]


async def main():
    made = 0
    for ent, fname, label, supplier, answer in SAMPLES:
        if await db.ocr_samples.find_one({"entity_id": ent, "label": label}):
            continue
        data = (DIR / fname).read_bytes()
        path = st.build_path(f"ocr_samples/{ent}", "jpg")
        await st.put_object(path, data, "image/jpeg")
        await svc.create(ent, label=label, partner_id="", partner_name=supplier,
                         files=[{"page": 1, "path": path, "content_type": "image/jpeg"}],
                         answer={**answer, "supplier_name": supplier}, actor="Seed sampel OCR")
        made += 1
    print(f"sampel baru: {made} · total: {await db.ocr_samples.count_documents({})}")


asyncio.run(main())
