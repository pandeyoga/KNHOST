"""UAT 24 Okt (P3/P4) — aturan alur R&D produk baru yang dipakai `rnd_sample_service` & router.

* P4.2 rantai tahap: handfeel → labdip (wajib merujuk handfeel ACC) → produk baru; proofing hanya di atas kain dasar
  yang sudah lolos. Pengecualian: uji ulang SKU & sampel yang lahir dari pesanan khusus (OD).
* P4.4 Pustaka Warna = KELUARAN labdip: warna target boleh "bebas" (nama + hex + Pantone); saat ACC sistem membuat
  entri Pustaka (kode KN otomatis) atau menautkan ke entri ber-Pantone sama.
* P3.4/P3.5 proofing hanya dari desain ACC berkas lengkap (PNG cetak); labdip wajib Pantone saat dikirim ke supplier.
* P4.6 supplier uji ulang = yang berkontrak untuk produk/induknya; "pernah PO" sebagai pilihan kedua (P4-K1).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from core_utils import new_id, now_iso
from db import db

# Pantone TCX/TPX/TPG (mis. 19-4052 TCX) atau kode coated/uncoated (mis. 186 C, Cool Gray 11 C, Black 6 U).
_PANTONE_FHI = re.compile(r"^\d{2}-\d{4}\s?(TCX|TPX|TPG|TN)$", re.I)
_PANTONE_CU = re.compile(r"^[A-Z0-9][A-Z0-9 .-]{0,24}\s(C|U|CP|UP)$", re.I)
ACC_DESIGN = ("approved", "final_submitted", "active")
#: K-16 (26 Okt) — alasan minimum untuk melanjutkan labdip tanpa handfeel ACC (seragam K-14: 5 huruf).
CHAIN_OVERRIDE_MIN_REASON = 5


class FlowError(ValueError):
    pass


def normalize_pantone(code: str) -> str:
    c = re.sub(r"\s+", " ", str(code or "").strip()).upper()
    if not c:
        return ""
    if c.upper().startswith("PANTONE "):
        c = c[8:].strip()
    if not (_PANTONE_FHI.match(c) or _PANTONE_CU.match(c)):
        raise FlowError(f"Kode Pantone '{code}' tidak sah — contoh: 19-4052 TCX, 14-1064 TPX, 186 C, Cool Gray 11 C.")
    return c


def pantone_of(color: Dict[str, Any]) -> str:
    """Pantone sebuah warna target/pustaka: field `pantone_code`, atau kodenya sendiri bila sistemnya Pantone."""
    c = color or {}
    if c.get("pantone_code"):
        return str(c["pantone_code"]).upper()
    if (c.get("system") or "").upper() in ("TCX", "TPX", "C", "U") and c.get("code"):
        return str(c["code"]).upper()
    return ""


def exempt(payload_or_doc: Dict[str, Any]) -> bool:
    """Aturan rantai produk baru (P4.2) & syarat desain ACC hanya untuk R&D produk baru INISIATIF MD. Tidak berlaku
    untuk uji ulang SKU dan sampel milik pelanggan (pesanan khusus / pesanan penjualan — ber-`customer_id`/`so_id`),
    yang alurnya diatur pesanan itu sendiri."""
    d = payload_or_doc or {}
    return d.get("purpose") == "revalidation" or bool(d.get("product_id") and d.get("revalidation")) \
        or bool(d.get("special_order_id") or d.get("customer_id") or d.get("so_id"))


async def _sample_has_acc(sample: Dict[str, Any], type_code: str) -> bool:
    if sample.get("status") == "decided":
        return True
    return any(r.get("result") == "acc" and (r.get("type_code") or "") in ("", type_code)
               for r in sample.get("rounds") or [])


async def assert_stage_chain(payload: Dict[str, Any], stypes: List[str], spec: Optional[Dict[str, Any]],
                             entity_id: str) -> Dict[str, Any]:
    """P4.2 — kembalikan field rantai (`parent_sample_*`, `stage`) atau tolak urutan yang dilompati."""
    from services import rnd_gate
    stage = "proofing" if "proofing" in stypes else "labdip" if "labdip" in stypes else (stypes[0] if stypes else "")
    out: Dict[str, Any] = {"stage": stage}
    parent_id = str(payload.get("parent_sample_id") or "").strip()
    parent = await db.md_samples.find_one({"id": parent_id}, {"_id": 0}) if parent_id else None
    if parent_id and not parent:
        raise FlowError("Sampel induk tidak ditemukan.")
    if parent:
        if entity_id and parent.get("entity_id") and parent["entity_id"] != entity_id:
            raise FlowError("Sampel induk milik badan usaha lain.")
        out.update({"parent_sample_id": parent["id"], "parent_sample_number": parent.get("number", ""),
                    "parent_stage": parent.get("stage") or ("handfeel" if "handfeel" in (parent.get("sample_types") or []) else "")})
    pol = await rnd_gate.policy(entity_id)
    if exempt(payload) or not bool(pol.get("require_stage_chain", True)):
        return out
    if "labdip" in stypes and "handfeel" not in stypes:
        if not parent or "handfeel" not in (parent.get("sample_types") or []) or not await _sample_has_acc(parent, "handfeel"):
            # Keputusan pemilik K-16 (26 Okt) — labdip produk baru TANPA handfeel ACC BOLEH, dengan peringatan + alasan
            # wajib yang tercatat (dulu form buntu). Tanpa alasan → tetap ditolak dengan pesan yang menyebut jalan keluarnya.
            why = str(payload.get("chain_override_reason") or "").strip()
            if len(why) < CHAIN_OVERRIDE_MIN_REASON:
                raise FlowError(
                    "Labdip produk baru semestinya berasal dari HANDFEEL yang sudah ACC (urutan: handfeel → labdip → "
                    "produk baru). Pilih sampel handfeel induknya, sertakan handfeel di permintaan ini, atau lanjutkan "
                    f"TANPA handfeel ACC dengan menulis alasannya (minimal {CHAIN_OVERRIDE_MIN_REASON} huruf).")
            out["chain_override"] = {
                "missing": "handfeel_acc",
                "label": "Labdip tanpa handfeel ACC",
                "reason": why,
                "parent_sample_id": (parent or {}).get("id", ""),
                "at": now_iso(),
            }
    if "proofing" in stypes:
        tpl_id = (spec or {}).get("base_fabric_template_id") or ""
        if not tpl_id:
            raise FlowError("Proofing/printing wajib memilih KAIN DASAR (woven/knit) yang sudah lolos handfeel/labdip "
                            "atau sudah diproduksi.")
        if not await base_fabric_passed(tpl_id):
            raise FlowError("Kain dasar yang dipilih belum lolos — pilih induk woven/knit yang sudah punya SKU produksi "
                            "atau sampel handfeel/labdip yang sudah ACC.")
    return out


async def base_fabric_passed(template_id: str) -> bool:
    """P4.8 — induk kain dasar "lolos": punya SKU berjalan (disetujui/produksi) atau sampel handfeel/labdip ACC."""
    if await db.products.find_one({"template_id": template_id, "lifecycle": {"$in": ["disetujui", "produksi"]}},
                                  {"_id": 0, "id": 1}):
        return True
    spec_ids = [s["id"] async for s in db.md_specs.find({"template_id": template_id}, {"_id": 0, "id": 1})]
    if not spec_ids:
        return False
    return bool(await db.md_samples.find_one(
        {"spec_id": {"$in": spec_ids}, "sample_types": {"$in": ["handfeel", "labdip"]},
         "$or": [{"status": "decided"}, {"rounds.result": "acc"}]}, {"_id": 0, "id": 1}))


async def passed_base_fabrics() -> List[Dict[str, Any]]:
    """Daftar induk woven/knit yang boleh jadi kain dasar proofing (untuk pemilih di form)."""
    out = []
    async for t in db.product_templates.find({"status": "active"}, {"_id": 0, "id": 1, "name": 1, "sku_prefix": 1,
                                                                     "fabric_type": 1, "stage": 1}):
        if await base_fabric_passed(t["id"]):
            out.append(t)
    return out


async def assert_design_usable(design_id: str, *, for_send: bool) -> None:
    """P3.4 — proofing hanya dari desain ACC; saat dikirim ke supplier, berkas final + PNG cetak wajib lengkap."""
    if not design_id:
        return
    d = await db.design_gallery.find_one({"id": design_id}, {"_id": 0})
    if not d:
        raise FlowError("Desain proofing tidak ditemukan.")
    if (d.get("status") or "draft") not in ACC_DESIGN:
        raise FlowError(f"Desain {d.get('code') or ''} belum ACC — proofing hanya dari desain yang sudah disetujui.")
    if for_send:
        from services import design_studio_service as studio
        req = studio.final_requirement(d)
        if (d.get("status") == "approved") or not req.get("complete"):
            raise FlowError(
                f"Desain {d.get('code') or ''} belum menyerahkan berkas final lengkap (mockup, file asli, dan PNG cetak). "
                "Surat perintah proofing ke supplier wajib membawa gambar pattern yang dicetak.")


async def assert_labdip_pantone(sample: Dict[str, Any]) -> None:
    """P3.5 — warna labdip wajib ber-kode Pantone sebelum dikirim ke supplier."""
    ct = sample.get("color_target") or {}
    p = pantone_of(ct)
    if not p and ct.get("color_id"):
        p = pantone_of(await db.color_library.find_one({"id": ct["color_id"]}, {"_id": 0}) or {})
    if not p:
        where = (f"lengkapi kode Pantone warna {ct.get('code')} di Pustaka Warna" if ct.get("color_id")
                 else "isi kode Pantone pada warna target permintaan ini")
        raise FlowError(f"Labdip {sample.get('number', '')}: kode Pantone warna target WAJIB jelas sebelum dikirim ke "
                        f"supplier (mis. 19-4052 TCX) — {where}.")


async def _next_kn_code(name: str) -> str:
    base = re.sub(r"[^A-Z]", "", (name or "").upper())[:3] or "WRN"
    n = 1
    while True:
        code = f"KN-{base}-{n:02d}"
        if not await db.color_library.find_one({"code": code}, {"_id": 0, "id": 1}):
            return code
        n += 1


async def color_from_labdip(sample: Dict[str, Any], actor_name: str) -> Optional[Dict[str, Any]]:
    """P4.4 — warna target bebas di labdip yang di-ACC → entri Pustaka Warna (atau tautan ke Pantone yang sama).
    Mengembalikan snapshot warna baru untuk `color_target` sampel & spesifikasinya; None bila tidak perlu."""
    ct = sample.get("color_target") or {}
    if ct.get("color_id") or not (ct.get("name") or ct.get("hex")):
        return None
    pantone = pantone_of(ct)
    existing = await db.color_library.find_one({"pantone_code": pantone, "status": {"$ne": "inactive"}}, {"_id": 0}) \
        if pantone else None
    linked = bool(existing)
    if not existing:
        from services import color_service
        existing = await color_service.create_color({
            "code": await _next_kn_code(ct.get("name") or ""), "name": ct.get("name") or pantone or "Warna labdip",
            "hex": ct.get("hex") or "#888888", "system": "KN", "pantone_code": pantone,
            "family": ct.get("family") or ""}, actor_name)
        await db.color_library.update_one({"id": existing["id"]}, {"$set": {
            "source": {"kind": "labdip", "sample_id": sample["id"], "sample_number": sample.get("number", ""),
                       "at": now_iso()}}})
    snap = {"color_id": existing["id"], "code": existing.get("code", ""), "name": existing.get("name", ""),
            "hex": existing.get("hex", ""), "pantone_code": pantone or existing.get("pantone_code", "")}
    await db.md_samples.update_one({"id": sample["id"]}, {"$set": {"color_target": snap, "updated_at": now_iso()}})
    if sample.get("spec_id"):
        await db.md_specs.update_one({"id": sample["spec_id"]}, {"$set": {"color_target": snap, "updated_at": now_iso()}})
    return {**snap, "linked_existing": linked}


async def contract_partners(product_id: str, q: str = "") -> List[Dict[str, Any]]:
    """P4.6/P4-K1 — supplier uji ulang: yang BERKONTRAK untuk produk/induknya, lalu yang PERNAH PO (berlabel)."""
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "template_id": 1}) if product_id else None
    if not prod:
        return []
    keys = [prod["id"]] + ([prod["template_id"]] if prod.get("template_id") else [])
    out: Dict[str, Dict[str, Any]] = {}
    async for c in db.supplier_contracts.find(
            {"$or": [{"product_id": {"$in": keys}}, {"template_id": {"$in": keys}}],
             "status": {"$nin": ["cancelled", "expired", "inactive"]},
             "contract_type": {"$in": ["purchase", "makloon", None, ""]}},
            {"_id": 0, "partner_id": 1, "supplier_id": 1, "partner_name": 1, "supplier_name": 1, "number": 1,
             "contract_number": 1, "contract_type": 1, "partner_kind": 1}):
        pid = c.get("partner_id") or c.get("supplier_id")
        if pid and pid not in out:
            kind = c.get("partner_kind") or ("makloon" if c.get("contract_type") == "makloon" else "supplier")
            out[pid] = {"id": pid, "name": c.get("partner_name") or c.get("supplier_name") or pid, "partner_kind": kind,
                        "basis": "contract", "basis_label": f"Kontrak {c.get('number') or c.get('contract_number') or ''}".strip()}
    async for po in db.purchase_orders.find({"items.product_id": prod["id"], "status": {"$nin": ["cancelled", "draft"]}},
                                            {"_id": 0, "supplier_id": 1, "supplier_name": 1, "po_number": 1}).sort("created_at", -1):
        sid = po.get("supplier_id")
        if sid and sid not in out:
            out[sid] = {"id": sid, "name": po.get("supplier_name") or sid, "partner_kind": "supplier",
                        "basis": "po_history", "basis_label": f"Pernah PO ({po.get('po_number') or ''}) — tanpa kontrak"}
    rows = list(out.values())
    if q:
        rows = [r for r in rows if q.lower() in (r["name"] or "").lower()]
    if rows:
        codes = {s["id"]: s.get("code", "") async for s in db.suppliers.find({"id": {"$in": [r["id"] for r in rows]}},
                                                                            {"_id": 0, "id": 1, "code": 1})}
        for r in rows:
            r["code"] = codes.get(r["id"], "")
    return sorted(rows, key=lambda r: (r["basis"] != "contract", r["name"]))
