"""PREP-A — lembar perbaikan master produk: susun baris (unduh) & baca unggahan.

Unduh: XLSX (`openpyxl`; sheet "Produk" + "Petunjuk", kolom tindakan berwarna + daftar pilihan) atau CSV
UTF-8 ber-BOM (cadangan bila openpyxl tidak ada / `format=csv`). Hanya produk yang TERLIHAT oleh user
(`catalog_access.visible_query`) dan kolom yang boleh dilihat (field visibility, mis. grade).
Unggah: XLSX/CSV dari lembar yang sama; baris kepala dicari otomatis (kolom `sku` + `tindakan`).
"""
import csv
import io
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

import domain_registry as dr
from core_utils import qty_dual
from db import db
from services import master_cleanup_refs as refs
from services import product_supersede as ps
from services.catalog_access import visible_query

try:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    XLSX_AVAILABLE = True
except ImportError:  # pragma: no cover — image backend memuat openpyxl
    XLSX_AVAILABLE = False

MAX_UPLOAD = 10 * 1024 * 1024
MAX_PRODUCTS = 20000
IDENT = ["id", "sku", "nama", "artikel", "kategori", "stage", "lini", "jenis_kain", "warna", "kode_warna", "motif",
         "grade", "gramasi", "lebar", "satuan_dasar", "status", "digantikan_oleh_saat_ini"]
REFS = ["stok_roll", "stok_qty", "stok_ringkas", "stok_per_gudang", "dok_terbuka", "dok_terbuka_nomor"]
SARAN = ["kelompok_duplikat", "alasan_duplikat", "saran_kode_induk"]
ACTION_COLS = ["tindakan", "nama_benar", "kode_benar", "digantikan_oleh_sku", "catatan"]
ACTION_CHOICES = ["PERTAHANKAN", "GANTI_NAMA", "GANTI_KODE", "GABUNG_KE", "NONAKTIFKAN"]
PETUNJUK = [
    "LEMBAR PERBAIKAN MASTER PRODUK (K-OPN-06) — isi HANYA kolom kuning: tindakan, nama_benar, kode_benar, digantikan_oleh_sku, catatan.",
    "Jangan ubah kolom id & sku: dipakai mencocokkan baris. Baris boleh dihapus/diurutkan; kolom referensi hanya bacaan.",
    "PERTAHANKAN (atau kosong) = tidak ada perubahan.",
    "GANTI_NAMA = perbaiki typo nama; isi nama_benar. SKU tetap, riwayat nama tercatat.",
    "GANTI_KODE = kode SKU salah; isi kode_benar (opsional nama_benar). SKU lama TIDAK diubah: dibuat produk baru "
    "berkode benar (atribut, induk, harga, alias supplier ikut), SKU lama dinonaktifkan & ditandai 'digantikan oleh' kode baru.",
    "GABUNG_KE = produk ini duplikat; isi digantikan_oleh_sku = SKU induk yang dipertahankan (boleh kode_benar baris GANTI_KODE "
    "di lembar yang sama). SKU ini dinonaktifkan & ditandai 'digantikan oleh' induk.",
    "NONAKTIFKAN = produk tidak dipakai lagi, tanpa pengganti.",
    "Stok TIDAK dipindah: stok lama akan didaftarkan ulang dari fisik (opname awal). Dokumen lama tidak diubah.",
    "Produk yang masih dipakai dokumen TERBUKA (kolom dok_terbuka) tidak bisa GANTI_KODE/GABUNG_KE/NONAKTIFKAN — selesaikan/alihkan dulu.",
    "kelompok_duplikat & saran_kode_induk hanya SARAN (atribut kanonik sama / nama mirip); keputusan tetap di kolom tindakan.",
    "Sesudah diisi: unggah di Master Produk → Tata kelola master → Perbaikan master. Sistem menampilkan pratinjau & galat "
    "per baris tanpa mengubah data; Terapkan = satu batch yang bisa dibatalkan.",
]
_PROJ = {"_id": 0, "id": 1, "sku": 1, "name": 1, "template_id": 1, "template_name": 1, "category": 1, "stage": 1,
         "line_code": 1, "fabric_type": 1, "color": 1, "color_name": 1, "color_code": 1, "motif": 1, "grade": 1,
         "gramasi": 1, "lebar": 1, "base_unit": 1, "status": 1, "superseded_by": 1, "catalog_version": 1,
         "created_at": 1}


async def hidden_columns(actor: Dict[str, Any]) -> set:
    from services.field_visibility import KEYS, hidden_for_user
    hidden = await hidden_for_user(actor)
    drop = set().union(*(KEYS[h] for h in hidden)) if hidden else set()
    return {c for c in IDENT if c in drop}


def _label(enum: str, v: Any) -> str:
    if not v:
        return ""
    try:
        return dr.label_of(enum, v) or str(v)
    except Exception:  # noqa: BLE001 — nilai lama di luar kosakata tetap ditampilkan apa adanya
        return str(v)


async def build_rows(actor: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, Any]]:
    products = await db.products.find(visible_query(actor), _PROJ).sort("sku", 1).to_list(MAX_PRODUCTS)
    tpl_ids = sorted({p["template_id"] for p in products if p.get("template_id")})
    tpls = {t["id"]: t.get("name", "") for t in await db.product_templates.find(
        {"id": {"$in": tpl_ids}}, {"_id": 0, "id": 1, "name": 1}).to_list(len(tpl_ids) + 1)}
    lines = {x["code"]: x.get("name", x["code"]) for x in await db.product_lines.find(
        {}, {"_id": 0, "code": 1, "name": 1}).to_list(200)}
    ids = [p["id"] for p in products]
    stock = await refs.stock_by_product(ids)
    od = await refs.open_docs_by_product(None)
    docs = {pid: v for pid, v in od["by_product"].items() if pid in set(ids)}
    usage = {pid: len(docs.get(pid, [])) * 10 + (stock.get(pid) or {}).get("rolls", 0) for pid in ids}
    dups = refs.duplicate_groups(products, usage)
    sup = await ps.sku_map([p.get("superseded_by") for p in products if p.get("superseded_by")])
    hide = await hidden_columns(actor)
    cols = [c for c in IDENT if c not in hide] + REFS + SARAN + ACTION_COLS
    rows = []
    for p in products:
        s = stock.get(p["id"]) or {}
        unit = p.get("base_unit") or ""
        d = sorted(docs.get(p["id"], []), key=lambda x: not x.get("blocking", True))   # memblokir dulu, kontrak di belakang
        n_block = sum(1 for x in d if x.get("blocking", True))
        g = dups.get(p["id"]) or {}
        status = "aktif" if p.get("status", "active") == "active" else "nonaktif"
        rows.append({
            "id": p["id"], "sku": p.get("sku", ""), "nama": p.get("name", ""),
            "artikel": tpls.get(p.get("template_id") or "", p.get("template_name", "")),
            "kategori": p.get("category", ""), "stage": _label("stage", p.get("stage")),
            "lini": lines.get(p.get("line_code") or "", p.get("line_code") or ""),
            "jenis_kain": _label("fabric_type", p.get("fabric_type")),
            "warna": p.get("color_name") or p.get("color") or "", "kode_warna": p.get("color_code", ""),
            "motif": p.get("motif", ""), "grade": p.get("grade", ""), "gramasi": p.get("gramasi", ""),
            "lebar": p.get("lebar", ""), "satuan_dasar": unit,
            "status": status + (" (digantikan)" if p.get("superseded_by") else ""),
            "digantikan_oleh_saat_ini": sup.get(p.get("superseded_by") or "", ""),
            "stok_roll": s.get("rolls", "") if s else "", "stok_qty": s.get("qty", "") if s else "",
            "stok_ringkas": qty_dual(s.get("rolls"), s.get("qty"), unit) if s else "",
            "stok_per_gudang": "; ".join(f"{w['code']} {qty_dual(w['rolls'], w['qty'], unit)}"
                                         for w in s.get("per_warehouse", [])[:6]),
            "dok_terbuka": n_block or "", "dok_terbuka_nomor": refs.docs_text(d),
            "kelompok_duplikat": g.get("group", ""), "alasan_duplikat": "; ".join(g.get("reasons", [])),
            "saran_kode_induk": ("(induk)" if g.get("is_parent") else g.get("parent_sku", "")) if g else "",
            **{c: "" for c in ACTION_COLS}})
    meta = {"products": len(products), "duplicate_groups": len({g["group"] for g in dups.values()}),
            "with_open_docs": sum(1 for v in docs.values() if any(x.get("blocking", True) for x in v)), "with_stock": len(stock), "truncated_sources": od["truncated"],
            "hidden_columns": sorted(hide)}
    return cols, rows, meta


def _xlsx_cell(ws, r: int, c: int, value: Any) -> None:
    cell = ws.cell(row=r, column=c, value=value)
    if isinstance(value, str) and value.startswith("="):
        cell.data_type = "s"        # anti formula injection: teks diawali "=" tetap teks


def render_xlsx(cols: List[str], rows: List[Dict[str, Any]], meta: Dict[str, Any]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Produk"
    head_fill, act_fill = PatternFill("solid", fgColor="E8E1F0"), PatternFill("solid", fgColor="FFF4C2")
    for j, c in enumerate(cols, 1):
        cell = ws.cell(row=1, column=j, value=c)
        cell.font = Font(bold=True)
        cell.fill = act_fill if c in ACTION_COLS else head_fill
        ws.column_dimensions[cell.column_letter].width = {"id": 20, "sku": 26, "nama": 38, "artikel": 28,
                                                          "dok_terbuka_nomor": 40, "stok_per_gudang": 36,
                                                          "alasan_duplikat": 34, "catatan": 30,
                                                          "nama_benar": 34}.get(c, 14)
    for i, row in enumerate(rows, 2):
        for j, c in enumerate(cols, 1):
            _xlsx_cell(ws, i, j, row.get(c, ""))
            if c in ACTION_COLS:
                ws.cell(row=i, column=j).fill = act_fill
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    t_col = cols.index("tindakan") + 1
    letter = ws.cell(row=1, column=t_col).column_letter
    dv = DataValidation(type="list", formula1='"' + ",".join(ACTION_CHOICES) + '"', allow_blank=True,
                        errorTitle="Tindakan tidak dikenal", error="Pilih: " + ", ".join(ACTION_CHOICES))
    ws.add_data_validation(dv)
    dv.add(f"{letter}2:{letter}{max(len(rows) + 1, 2)}")
    info = wb.create_sheet("Petunjuk")
    info.column_dimensions["A"].width = 140
    for i, line in enumerate(PETUNJUK, 1):
        info.cell(row=i, column=1, value=line).alignment = Alignment(wrap_text=True)
    n = len(PETUNJUK) + 2
    info.cell(row=n, column=1, value=(f"Ringkasan: {meta['products']} produk · {meta['duplicate_groups']} kelompok calon "
                                      f"duplikat · {meta['with_open_docs']} produk berdokumen terbuka · "
                                      f"{meta['with_stock']} produk berstok."))
    if meta.get("hidden_columns"):
        info.cell(row=n + 1, column=1, value="Kolom disembunyikan sesuai hak lihat Anda: " + ", ".join(meta["hidden_columns"]))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def render_csv(cols: List[str], rows: List[Dict[str, Any]]) -> bytes:
    out = io.StringIO()
    note = csv.writer(out, lineterminator="\r\n")
    for line in PETUNJUK[:3]:            # satu sel per baris petunjuk; dilewati saat dibaca (kepala dicari otomatis)
        note.writerow(["# " + line])
    w = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore", lineterminator="\r\n")
    w.writeheader()
    for r in rows:
        w.writerow({c: (("'" + str(v)) if str(v)[:1] in _FORMULA else v) for c, v in ((c, r.get(c, "")) for c in cols)})
    return ("﻿" + out.getvalue()).encode("utf-8")


# ─── baca unggahan ────────────────────────────────────────────────────────────
def _cell(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = str(v).strip()
    if len(s) > 1 and s[0] == "'" and s[1] in _FORMULA:
        s = s[1:]
    return s


def _rows_from_table(table: List[List[Any]]) -> List[Dict[str, Any]]:
    head_idx, header = None, []
    for i, row in enumerate(table[:30]):
        names = [_cell(c).lower() for c in row]
        if "sku" in names and "tindakan" in names:
            head_idx, header = i, names
            break
    if head_idx is None:
        raise HTTPException(status_code=400, detail="Kolom wajib tidak ditemukan: sku dan tindakan — pakai lembar unduhan terbaru.")
    keep = {"id", "sku"} | set(ACTION_COLS)
    out = []
    for k, row in enumerate(table[head_idx + 1:], head_idx + 2):
        rec = {h: _cell(row[j]) if j < len(row) else "" for j, h in enumerate(header) if h in keep}
        if rec.get("id") or rec.get("sku"):
            out.append({"row": k, **rec})
    return out


def parse_sheet(content: bytes, filename: str) -> List[Dict[str, Any]]:
    if not content:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    if len(content) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail="Berkas terlalu besar (maks. 10 MB).")
    name = (filename or "").lower()
    if name.endswith(".xlsx") or content[:2] == b"PK":
        if not XLSX_AVAILABLE:
            raise HTTPException(status_code=400, detail="Server belum mendukung XLSX — unggah sebagai CSV UTF-8.")
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Berkas XLSX tidak valid atau rusak.")
        ws = wb["Produk"] if "Produk" in wb.sheetnames else wb.active
        table = [list(r) for _, r in zip(range(MAX_PRODUCTS + 50), ws.iter_rows(values_only=True))]
        return _rows_from_table(table)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Berkas bukan UTF-8. Simpan ulang sebagai CSV UTF-8 atau XLSX.")
    lines = text.splitlines()            # baris petunjuk TETAP dihitung → nomor baris = nomor baris di Excel
    head = next((ln for ln in lines[:30] if not ln.lstrip('"').startswith("#")
                 and "sku" in ln.lower() and "tindakan" in ln.lower()), "")
    delim = max([",", ";", "\t"], key=head.count) if head else ","
    return _rows_from_table(list(csv.reader(io.StringIO(text), delimiter=delim)))   # sel berbaris-baru tetap utuh
