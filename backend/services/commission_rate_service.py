"""KA-8 — layanan layar "Skema & Tarif": daftar kategori/artikel/varian, ubah banyak, Excel, indeks draf simulasi.

Rancangan `docs/superpowers/specs/2026-11-23-komisi-per-artikel-design.md` §6.2, §6.6. Tarif yang tampil di layar dipilih
dengan `commission_rules.pilih_tarif` — fungsi yang sama dengan mesin komisi — jadi layar menunjukkan persis tarif yang akan
dipakai mesin. Penulisan (ubah banyak, terap Excel) memakai validasi yang sama dengan `POST /api/incentive-rates`
(`selesaikan`, `kembar`), satu salinan.

Artikel "aktif" = `product_templates.status` bukan `archived`/`inactive`/`discontinued` (katalog hanya memakai `active` dan
`archived`; dua lainnya ikut ditolak supaya aman bila status baru muncul).
"""
from __future__ import annotations

import io
import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso
from db import db
from services.commission_rules import aturan_pt, muat_indeks_tarif, periksa_nilai, pilih_tarif, rate_key

STATUS_TAK_AKTIF = ("archived", "inactive", "discontinued")
BATAS_BERKAS = 5 * 1024 * 1024
KOLOM = ["Kode artikel", "Nama artikel", "Kategori", "Kode varian", "Tarif per satuan dasar", "Batas margin %",
         "Asal tarif"]
_NAMA_PAKSA = {"price_bands": "commission.price_bands", "price_source_rules": "commission.price_source_rules"}
_TINGKAT = {"artikel": "Tarif artikel", "varian": "Tarif varian", "kategori": "Tarif kategori"}
_LINGKUP = {"pt": "PT ini", "semua_pt": "Semua PT"}


# ── Validasi sasaran tarif (dipakai juga oleh router POST/PATCH) ────────────
async def selesaikan(doc: Dict[str, Any]) -> None:
    """Lengkapi `doc` di tempat: validasi sasaran (artikel/varian/kategori), potret nama/kode/kategori, pita khusus,
    lalu `rate_key`. `HTTPException` 400 berpesan Indonesia bila tidak sah."""
    tpl = (doc.get("template_id") or "").strip()
    prd = (doc.get("product_id") or "").strip()
    if tpl and prd:
        raise HTTPException(status_code=400, detail="Pilih artikel atau varian, bukan keduanya.")
    doc["template_id"], doc["product_id"] = tpl, prd
    if prd:
        p = await db.products.find_one({"id": prd}, {"_id": 0, "id": 1, "name": 1, "sku": 1, "category": 1})
        if not p:
            raise HTTPException(status_code=400, detail="Varian tidak ditemukan.")
        doc.update({"category": p.get("category") or "", "target_name": p.get("name") or "",
                    "target_code": p.get("sku") or ""})
    elif tpl:
        t = await db.product_templates.find_one({"id": tpl}, {"_id": 0, "id": 1, "name": 1, "sku_prefix": 1, "category": 1})
        if not t:
            raise HTTPException(status_code=400, detail="Artikel tidak ditemukan.")
        doc.update({"category": t.get("category") or "", "target_name": t.get("name") or "",
                    "target_code": t.get("sku_prefix") or ""})
    else:
        if not (doc.get("category") or "").strip():
            raise HTTPException(status_code=400, detail="Kategori wajib diisi")
        doc.update({"target_name": "", "target_code": ""})
    for f, kunci in _NAMA_PAKSA.items():
        if doc.get(f) is not None:
            try:
                doc[f] = periksa_nilai(kunci, doc[f])
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    doc["rate_key"] = rate_key(doc)


def kembar(doc: Dict[str, Any]) -> HTTPException:
    nama = doc.get("target_name") or doc.get("category") or ""
    return HTTPException(status_code=409, detail=f"Tarif untuk {nama} di PT ini sudah ada.")


async def cek_kembar(doc: Dict[str, Any], kecuali_id: str = "") -> None:
    q: Dict[str, Any] = {"entity_id": doc["entity_id"], "rate_key": doc["rate_key"]}
    if kecuali_id:
        q["id"] = {"$ne": kecuali_id}
    if await db.incentive_rates.find_one(q, {"_id": 0, "id": 1}):
        raise kembar(doc)


def _angka_tarif(v: Any, nama: str, *, boleh_kosong: bool = False) -> Optional[float]:
    if v is None and boleh_kosong:
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) < 0:
        raise HTTPException(status_code=400, detail=f"{nama} harus berupa angka, tidak boleh negatif.")
    return float(v)


# ── Tampilan tarif ──────────────────────────────────────────────────────────
def _margin(tarif: Dict[str, Any], pt: Dict[str, Any]) -> Any:
    """Batas margin yang dipakai mesin: isian baris tarif bila kuncinya ada (juga None), selain itu bawaan PT."""
    return tarif["margin_cap_pct"] if "margin_cap_pct" in tarif else pt.get("default_margin_cap_pct")


def _ringkas(tarif: Optional[Dict[str, Any]], pt: Dict[str, Any], *, tingkat: bool = True) -> Optional[Dict[str, Any]]:
    if not tarif:
        return None
    out: Dict[str, Any] = {"per_unit_amount": float(tarif.get("per_unit_amount", 0) or 0),
                           "margin_cap_pct": _margin(tarif, pt)}
    if tingkat:
        out["asal_tingkat"] = tarif.get("asal_tingkat")
    out["asal_lingkup"] = tarif.get("asal_lingkup")
    out["rate_id"] = tarif.get("id")
    return out


def _teks_asal(tarif: Optional[Dict[str, Any]]) -> str:
    if not tarif:
        return "Tanpa tarif"
    dasar = _TINGKAT.get(tarif.get("asal_tingkat") or "", "Tarif")
    lingkup = _LINGKUP.get(tarif.get("asal_lingkup") or "")
    return f"{dasar} ({lingkup})" if lingkup else dasar


async def _artikel_aktif() -> List[Dict[str, Any]]:
    rows = await db.product_templates.find({"status": {"$nin": list(STATUS_TAK_AKTIF)}},
                                           {"_id": 0, "id": 1, "name": 1, "sku_prefix": 1, "category": 1}).to_list(None)
    rows.sort(key=lambda t: ((t.get("name") or "").lower(), t.get("id") or ""))
    return rows


def _varian_aktif_filter(**lebih: Any) -> Dict[str, Any]:
    return {"status": {"$nin": list(STATUS_TAK_AKTIF)}, "is_active": {"$ne": False}, **lebih}


async def daftar_kategori(entity_id: str) -> List[Dict[str, Any]]:
    indeks, pt = await muat_indeks_tarif(entity_id), await aturan_pt(entity_id)
    artikel = await _artikel_aktif()
    kat: Dict[str, Dict[str, int]] = {}
    for t in artikel:
        c = (t.get("category") or "").strip()
        if not c:
            continue
        k = kat.setdefault(c, {"articles": 0, "articles_own_rate": 0})
        k["articles"] += 1
        if f"artikel:{t['id']}" in indeks:
            k["articles_own_rate"] += 1
    for kunci in indeks:
        if kunci.startswith("kategori:") and kunci[9:]:
            kat.setdefault(kunci[9:], {"articles": 0, "articles_own_rate": 0})
    out = []
    for c in sorted(kat):
        tarif = pilih_tarif(indeks, product_id="", template_id="", category=c)
        out.append({"category": c, "rate": _ringkas(tarif, pt, tingkat=False), **kat[c]})
    return out


async def daftar_artikel(entity_id: str, *, search: str = "", category: str = "", page: int = 1,
                         page_size: int = 50) -> Dict[str, Any]:
    indeks, pt = await muat_indeks_tarif(entity_id), await aturan_pt(entity_id)
    q = (search or "").strip().lower()
    cat = (category or "").strip()
    rows = [t for t in await _artikel_aktif()
            if (not cat or (t.get("category") or "").strip() == cat)
            and (not q or q in (t.get("name") or "").lower() or q in (t.get("sku_prefix") or "").lower())]
    total = len(rows)
    halaman = rows[(page - 1) * page_size: page * page_size]
    pengecualian: Dict[str, int] = {}
    ids = [t["id"] for t in halaman]
    if ids:
        async for p in db.products.find(_varian_aktif_filter(template_id={"$in": ids}),
                                        {"_id": 0, "id": 1, "template_id": 1}):
            if f"varian:{p['id']}" in indeks:
                pengecualian[p["template_id"]] = pengecualian.get(p["template_id"], 0) + 1
    items = []
    for t in halaman:
        tarif = pilih_tarif(indeks, product_id="", template_id=t["id"], category=t.get("category") or "")
        sendiri = indeks.get(f"artikel:{t['id']}")
        items.append({"template_id": t["id"], "name": t.get("name") or "", "code": t.get("sku_prefix") or "",
                      "category": t.get("category") or "", "rate": _ringkas(tarif, pt),
                      "own_rate_id": sendiri.get("id") if sendiri else None,
                      "variant_exceptions": pengecualian.get(t["id"], 0)})
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def daftar_varian(entity_id: str, template_id: str) -> List[Dict[str, Any]]:
    t = await db.product_templates.find_one({"id": template_id}, {"_id": 0, "id": 1, "category": 1})
    if not t:
        raise HTTPException(status_code=404, detail="Artikel tidak ditemukan.")
    indeks, pt = await muat_indeks_tarif(entity_id), await aturan_pt(entity_id)
    rows = await db.products.find(_varian_aktif_filter(template_id=template_id),
                                  {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1}).to_list(None)
    rows.sort(key=lambda p: ((p.get("sku") or ""), p["id"]))
    out = []
    for p in rows:
        tarif = pilih_tarif(indeks, product_id=p["id"], template_id=template_id,
                            category=p.get("category") or t.get("category") or "")
        out.append({"product_id": p["id"], "sku": p.get("sku") or "", "name": p.get("name") or "",
                    "rate": _ringkas(tarif, pt),
                    "follows": tarif["asal_tingkat"] if tarif else "tanpa_tarif"})
    return out


# ── Simulasi ────────────────────────────────────────────────────────────────
async def indeks_dengan_draf(entity_id: str, draft_rates: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Indeks tarif sekarang ditimpa tarif draf (kunci `rate_key`, lingkup "pt"). Draf menimpa isian jumlah (dan batas margin
    bila disebut) pada tarif yang sudah ada di kunci itu; tanpa tarif yang sudah ada → tarif baru dengan bawaan PT.
    `HTTPException` 400 bila draf tidak sah."""
    indeks = await muat_indeks_tarif(entity_id)
    lihat = set()
    for i, d in enumerate(draft_rates or [], 1):
        doc = {"template_id": d.get("template_id") or "", "product_id": d.get("product_id") or "",
               "category": d.get("category") or ""}
        if doc["template_id"] or doc["product_id"]:
            doc["category"] = ""
        await selesaikan(doc)
        if doc["rate_key"] in lihat:
            raise HTTPException(status_code=400, detail=f"Draf tarif baris {i}: sasaran sama dengan draf lain.")
        lihat.add(doc["rate_key"])
        jumlah = _angka_tarif(d.get("per_unit_amount"), f"Tarif draf baris {i}")
        batas = _angka_tarif(d.get("margin_cap_pct"), f"Batas margin draf baris {i}", boleh_kosong=True)
        baru = {**(indeks.get(doc["rate_key"]) or {}), "id": "draf", "entity_id": entity_id, "rate_key": doc["rate_key"],
                "template_id": doc["template_id"], "product_id": doc["product_id"], "category": doc["category"],
                "per_unit_amount": jumlah, "status": "active", "_lingkup": "pt"}
        if batas is not None:
            baru["margin_cap_pct"] = batas
        indeks[doc["rate_key"]] = baru
    return indeks


# ── Tulis: ubah banyak & terap Excel ────────────────────────────────────────
async def terapkan_tarif(entity_id: str, sasaran: List[Dict[str, Any]], *, bawaan: Dict[str, Any], alasan: str,
                         aktor: str) -> Dict[str, int]:
    """Buat/ubah tarif per sasaran `{template_id|product_id, per_unit_amount, margin_cap_pct?}` untuk satu PT. Semua sasaran
    divalidasi dulu (satu galat = tidak ada yang tertulis). Tarif yang sudah ada di PT itu diubah jumlahnya (batas margin
    hanya bila disebut; tarif nonaktif diaktifkan lagi); yang belum ada dibuat dari `bawaan` (isian bawaan `RatePayload`,
    batas margin bawaan PT). Jejak audit per tarif memuat `alasan`."""
    from dependencies import audit
    pt = await aturan_pt(entity_id)
    rencana: List[Tuple[str, Dict[str, Any], Dict[str, Any]]] = []
    lihat = set()
    for i, s in enumerate(sasaran, 1):
        ada_t, ada_p = bool((s.get("template_id") or "").strip()), bool((s.get("product_id") or "").strip())
        if ada_t == ada_p:
            raise HTTPException(status_code=400, detail=f"Baris {i}: isi artikel atau varian (salah satu).")
        doc = {"entity_id": entity_id, "template_id": s.get("template_id") or "", "product_id": s.get("product_id") or "",
               "category": ""}
        await selesaikan(doc)
        if doc["rate_key"] in lihat:
            raise HTTPException(status_code=400, detail=f"Baris {i}: {doc['target_name']} muncul lebih dari sekali.")
        lihat.add(doc["rate_key"])
        jumlah = _angka_tarif(s.get("per_unit_amount"), f"Tarif baris {i}")
        batas = _angka_tarif(s.get("margin_cap_pct"), f"Batas margin baris {i}", boleh_kosong=True)
        lama = await db.incentive_rates.find_one({"entity_id": entity_id, "rate_key": doc["rate_key"]}, {"_id": 0})
        if lama:
            ubah = {"per_unit_amount": jumlah, "status": "active", "updated_at": now_iso()}
            if batas is not None:
                ubah["margin_cap_pct"] = batas
            rencana.append(("ubah", lama, ubah))
        else:
            baru = {**bawaan, **doc, "per_unit_amount": jumlah, "status": "active",
                    "margin_cap_pct": batas if batas is not None else pt.get("default_margin_cap_pct"),
                    "price_bands": None, "price_source_rules": None,
                    "id": new_id("irate"), "created_at": now_iso(), "updated_at": now_iso()}
            rencana.append(("buat", baru, {}))
    hasil = {"created": 0, "updated": 0}
    for jenis, doc, ubah in rencana:
        if jenis == "buat":
            try:
                await db.incentive_rates.insert_one(doc)
            except DuplicateKeyError:
                raise kembar(doc) from None
            hasil["created"] += 1
            await audit(aktor, "incentive_rate_created", "incentive_rate", doc["id"], doc, reason=alasan)
        else:
            sesudah = await db.incentive_rates.find_one_and_update(
                {"id": doc["id"]}, {"$set": ubah}, projection={"_id": 0}, return_document=ReturnDocument.AFTER)
            hasil["updated"] += 1
            await audit(aktor, "incentive_rate_updated", "incentive_rate", doc["id"], sesudah, reason=alasan, before=doc)
    return hasil


# ── Excel ───────────────────────────────────────────────────────────────────
async def ekspor_xlsx(entity_id: str) -> bytes:
    """Satu baris per artikel aktif (tarif yang berlaku, juga bila ikut kategori) + satu baris per pengecualian varian."""
    from openpyxl import Workbook
    from openpyxl.styles import Font
    indeks, pt = await muat_indeks_tarif(entity_id), await aturan_pt(entity_id)
    artikel = await _artikel_aktif()
    ids = [t["id"] for t in artikel]
    varian: Dict[str, List[Dict[str, Any]]] = {}
    pengecualian = [k[7:] for k in indeks if k.startswith("varian:")]
    if pengecualian:
        async for p in db.products.find(_varian_aktif_filter(id={"$in": pengecualian}, template_id={"$in": ids}),
                                        {"_id": 0, "id": 1, "sku": 1, "name": 1, "category": 1, "template_id": 1}):
            varian.setdefault(p["template_id"], []).append(p)
    wb = Workbook()
    ws = wb.active
    ws.title = "Tarif per artikel"
    ws.append(KOLOM)
    for c in ws[1]:
        c.font = Font(bold=True)

    def _baris(t: Dict[str, Any], tarif: Optional[Dict[str, Any]], nama: str, kode_varian: str) -> List[Any]:
        r = _ringkas(tarif, pt)
        return [t.get("sku_prefix") or "", nama, t.get("category") or "", kode_varian or None,
                r["per_unit_amount"] if r else None, r["margin_cap_pct"] if r else None, _teks_asal(tarif)]

    for t in artikel:
        cat = t.get("category") or ""
        ws.append(_baris(t, pilih_tarif(indeks, product_id="", template_id=t["id"], category=cat), t.get("name") or "", ""))
        for p in sorted(varian.get(t["id"], []), key=lambda x: x.get("sku") or ""):
            ws.append(_baris(t, pilih_tarif(indeks, product_id=p["id"], template_id=t["id"],
                                            category=p.get("category") or cat), p.get("name") or "", p.get("sku") or ""))
    for kolom, lebar in zip("ABCDEFG", (18, 32, 18, 20, 22, 16, 28)):
        ws.column_dimensions[kolom].width = lebar
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _sel_angka(v: Any, nama: str) -> Tuple[Optional[float], str]:
    """(angka, galat). Sel kosong → (None, ""); teks angka polos diterima; selebihnya galat."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None, ""
    if isinstance(v, bool):
        return None, f"{nama} harus berupa angka."
    try:
        n = float(v.strip().replace(",", ".") if isinstance(v, str) else v)
    except (TypeError, ValueError):
        return None, f"{nama} harus berupa angka."
    if not math.isfinite(n) or n < 0:
        return None, f"{nama} harus berupa angka, tidak boleh negatif."
    return n, ""


def _teks(v: Any) -> str:
    return "" if v is None else str(v).strip()


async def pratinjau_impor(entity_id: str, isi: bytes) -> List[Dict[str, Any]]:
    """Baca berkas `.xlsx` hasil unduhan (kolom dikenali dari judulnya) dan nilai tiap baris terhadap tarif yang berlaku.
    TIDAK menulis apa pun. Status: baru (belum ada tarif sendiri di PT ini) · ubah · sama · galat."""
    from openpyxl import load_workbook
    if len(isi) > BATAS_BERKAS:
        raise HTTPException(status_code=413, detail="Berkas terlalu besar (maksimal 5 MB).")
    try:
        ws = load_workbook(io.BytesIO(isi), read_only=True, data_only=True).active
        semua = list(ws.iter_rows(values_only=True))
    except Exception:  # noqa: BLE001 — berkas bukan xlsx / rusak
        raise HTTPException(status_code=400, detail="Berkas harus berupa Excel (.xlsx) hasil unduhan daftar tarif.") from None
    if not semua:
        raise HTTPException(status_code=400, detail="Berkas kosong.")
    judul = {_teks(h).lower(): i for i, h in enumerate(semua[0]) if h is not None}
    kolom: Dict[str, int] = {}
    for nama in KOLOM[:5] + [KOLOM[5]]:
        if nama.lower() in judul:
            kolom[nama] = judul[nama.lower()]
    for wajib in (KOLOM[0], KOLOM[4]):
        if wajib not in kolom:
            raise HTTPException(status_code=400, detail=f"Kolom “{wajib}” tidak ada di berkas.")
    indeks, pt = await muat_indeks_tarif(entity_id), await aturan_pt(entity_id)

    def _sel(row: tuple, nama: str) -> Any:
        i = kolom.get(nama)
        return row[i] if i is not None and i < len(row) else None

    out: List[Dict[str, Any]] = []
    for no, row in enumerate(semua[1:], 2):
        if all(c is None or _teks(c) == "" for c in row):
            continue
        kode_a, kode_v = _teks(_sel(row, KOLOM[0])), _teks(_sel(row, KOLOM[3]))
        r = {"baris": no, "kode_artikel": kode_a, "kode_varian": kode_v, "nama": _teks(_sel(row, KOLOM[1])),
             "lama": None, "baru": None, "lama_batas": None, "baru_batas": None, "status": "galat", "pesan": "",
             "template_id": "", "product_id": ""}
        out.append(r)
        tpl = await db.product_templates.find_one({"sku_prefix": kode_a}, {"_id": 0, "id": 1, "name": 1, "category": 1,
                                                                            "status": 1}) if kode_a else None
        if not tpl:
            r["pesan"] = f"Artikel {kode_a or '(kosong)'} tidak ditemukan."
            continue
        if tpl.get("status") in STATUS_TAK_AKTIF:
            r["pesan"] = f"Artikel {kode_a} tidak aktif."
            continue
        prod = None
        if kode_v:
            prod = await db.products.find_one({"sku": kode_v}, {"_id": 0, "id": 1, "name": 1, "category": 1, "template_id": 1})
            if not prod:
                r["pesan"] = f"Varian {kode_v} tidak ditemukan."
                continue
            if prod.get("template_id") != tpl["id"]:
                r["pesan"] = f"Varian {kode_v} bukan bagian dari artikel {kode_a}."
                continue
        r["template_id"], r["product_id"] = (("", prod["id"]) if prod else (tpl["id"], ""))
        r["nama"] = (prod or tpl).get("name") or r["nama"]
        baru, g1 = _sel_angka(_sel(row, KOLOM[4]), "Tarif per satuan dasar")
        batas, g2 = _sel_angka(_sel(row, KOLOM[5]), "Batas margin %")
        if g1 or g2:
            r["pesan"] = g1 or g2
            continue
        tarif = pilih_tarif(indeks, product_id=prod["id"] if prod else "", template_id=tpl["id"],
                            category=(prod or {}).get("category") or tpl.get("category") or "")
        lama = _ringkas(tarif, pt)
        r["lama"] = lama["per_unit_amount"] if lama else None
        r["lama_batas"] = lama["margin_cap_pct"] if lama else None
        r["baru"], r["baru_batas"] = baru, batas
        if baru is None:
            r.update(status="sama", pesan="Tarif dikosongkan, baris tidak diubah.")
            continue
        sendiri = indeks.get(rate_key({"template_id": r["template_id"], "product_id": r["product_id"]}))
        sama = lama is not None and lama["per_unit_amount"] == baru and (batas is None or lama["margin_cap_pct"] == batas)
        if sama:
            r.update(status="sama", pesan="")
        elif sendiri and sendiri.get("_lingkup") == "pt":
            r.update(status="ubah", pesan="")
        else:
            r.update(status="baru", pesan="Tarif sendiri baru untuk PT ini.")
    return out
