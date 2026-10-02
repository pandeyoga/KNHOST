"""GRN — profil surat jalan per mitra (`supplier_dn_profiles`): format angka, nama lain, pemetaan barang.

Belajar HANYA dari data yang sudah dikonfirmasi manusia (GRN ditutup): baris OCR yang dicek, angka yang dipilih,
nama pengirim tercetak. Dipakai `map_extraction` supaya pembacaan berikutnya makin jarang ragu.
"""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso
from db import db
from services import dn_rules as R

MIN_CONFIRMED = 3          # locale dipakai otomatis sesudah ≥ 3 SJ terkonfirmasi (§4.8)
LOCALE_SHARE = 0.8         # dan ≥ 80% bukti menunjuk format yang sama
MAX_ALIASES = 10
MAX_CORRECTIONS = 30       # koreksi manusia terakhir per mitra yang disimpan
HINT_CORRECTIONS = 12      # yang dikirim ke AI sebagai petunjuk
_DN_FIELDS = (("number", "Nomor SJ"), ("date", "Tanggal SJ"), ("supplier_name_printed", "Nama pengirim tercetak"),
              ("po_refs", "Nomor PO di kepala SJ"))


def active_locale(prof: Dict[str, Any]) -> str:
    loc = prof.get("number_locale") or "unknown"
    if prof.get("locale_locked"):
        return loc
    return loc if int(prof.get("confirmed_count") or 0) >= MIN_CONFIRMED else "unknown"


def _decide_locale(votes: Dict[str, int]) -> str:
    total = sum(votes.values())
    for loc in ("id", "en"):
        if total >= 2 and votes.get(loc, 0) / total >= LOCALE_SHARE:
            return loc
    return "unknown"


def _locale_evidence(grn: Dict[str, Any]) -> Dict[str, int]:
    """Bukti format angka dari baris OCR yang sudah dicek: teks tegas (1.250,00) + angka ambigu yang DIPILIH manusia."""
    out = {"id": 0, "en": 0}
    for ln in grn.get("lines") or []:
        if (ln.get("read") or {}).get("source") != "ocr" or not ln.get("verified") or ln.get("decision") == "reject_line":
            continue
        chosen = (ln.get("declared") or {}).get("qty")
        for q in (ln.get("read") or {}).get("quantities") or []:
            loc = R.infer_locale(q.get("qty_text"))
            if not loc and chosen is not None and str(q.get("role", "")).startswith("delivered"):
                p = R.parse_doc_number(q.get("qty_text"))
                if p["ambiguous"] and chosen in p["candidates"]:
                    sep = "." if "." in str(q.get("qty_text")) else ","
                    thousands = chosen == p["candidates"][0]
                    loc = ("id" if sep == "." else "en") if thousands else ("en" if sep == "." else "id")
            if loc:
                out[loc] += 1
    return out


def _alias_to_add(prof: Dict[str, Any], grn: Dict[str, Any]) -> str:
    alias = ((grn.get("dn") or {}).get("supplier_name_printed") or "").strip()
    known = [grn.get("partner_name") or "", *(prof.get("aliases") or [])]
    if not alias or len(prof.get("aliases") or []) >= MAX_ALIASES:
        return ""
    return alias if R.name_mismatch(alias, known) else ""   # hanya varian yang tadinya memicu peringatan


def _item_learnings(grn: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Baris OCR dicek + target terkonfirmasi → kunci (kode/deskripsi) → produk."""
    out: Dict[str, Dict[str, Any]] = {}
    for ln in grn.get("lines") or []:
        tgt = ln.get("target") or {}
        if (ln.get("read") or {}).get("source") != "ocr" or not ln.get("verified") or not tgt.get("product_id"):
            continue
        key = R.desc_key(ln["read"])
        if key:
            out[key] = {"product_id": tgt["product_id"], "product_name": tgt.get("product_name", ""),
                        "text": (ln["read"].get("item_code") or ln["read"].get("description") or "")[:120]}
    return out


def _fmt_val(v: Any) -> str:
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) or "(kosong)"
    return "(kosong)" if v in (None, "") else str(v)


def corrections_from_grn(grn: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Beda hasil baca AI vs nilai akhir yang dicek manusia (kepala SJ + qty/satuan/roll baris OCR)."""
    from services.goods_receipt_service import norm_dn
    out: List[Dict[str, Any]] = []
    dn, ocr = grn.get("dn") or {}, (grn.get("dn") or {}).get("ocr") or {}
    base = {"grn_id": grn["id"], "grn_number": grn.get("number", ""), "at": now_iso()}
    if dn.get("source") == "ocr":
        for k, label in _DN_FIELDS:
            a, b = ocr.get(k), dn.get(k)
            if k == "number" and norm_dn(a) == norm_dn(b):
                continue
            if (sorted(a or []) if k == "po_refs" else (a or "")) != (sorted(b or []) if k == "po_refs" else (b or "")):
                out.append({**base, "field": label, "ocr": _fmt_val(a), "final": _fmt_val(b), "context": ""})
    for ln in grn.get("lines") or []:
        if (ln.get("read") or {}).get("source") != "ocr" or ln.get("decision") == "reject_line":
            continue
        a, b = ln.get("ocr_declared") or {}, ln.get("declared") or {}
        ctx = ((ln.get("read") or {}).get("description") or (ln.get("read") or {}).get("row_text") or "")[:80]
        if "ocr_po_ref" in ln and norm_dn(ln["ocr_po_ref"]) != norm_dn(ln["read"].get("po_ref")):
            out.append({**base, "field": f"Baris {ln['line_no']} nomor PO", "ocr": _fmt_val(ln["ocr_po_ref"]),
                        "final": _fmt_val(ln["read"].get("po_ref")), "context": ctx})
        for k, label in (("qty", "qty"), ("unit", "satuan"), ("rolls", "jumlah roll/pcs")):
            if a.get(k) != b.get(k) and b.get(k) not in (None, ""):
                out.append({**base, "field": f"Baris {ln['line_no']} {label}", "ocr": _fmt_val(a.get(k)),
                            "final": _fmt_val(b.get(k)), "context": ctx})
    return out


async def record_corrections(grn: Dict[str, Any]) -> int:
    """Simpan koreksi manusia ke profil mitra (idempoten per GRN: koreksi lama GRN yang sama diganti)."""
    rows = corrections_from_grn(grn)
    flt = {"entity_id": grn["entity_id"], "partner_id": grn["partner_id"]}
    await db.supplier_dn_profiles.update_one(flt, {"$pull": {"corrections": {"grn_id": grn["id"]}}})
    if rows:
        await db.supplier_dn_profiles.update_one(flt, {
            "$setOnInsert": {"id": new_id("sdp"), "entity_id": grn["entity_id"], "partner_id": grn["partner_id"],
                             "partner_name": grn.get("partner_name", ""), "partner_type": grn.get("partner_type"),
                             "created_at": now_iso()},
            "$push": {"corrections": {"$each": rows, "$slice": -MAX_CORRECTIONS}}}, upsert=True)
    return len(rows)


async def hints_for(entity_id: str, partner_id: str, exclude_grn_id: str = "") -> Dict[str, Any]:
    """Petunjuk untuk AI dari SJ mitra ini yang sudah dicek manusia (belajar dari koreksi, tanpa melatih ulang model)."""
    prof = await db.supplier_dn_profiles.find_one({"entity_id": entity_id, "partner_id": partner_id}, {"_id": 0}) or {}
    corr = [c for c in prof.get("corrections") or [] if c.get("grn_id") != exclude_grn_id][-HINT_CORRECTIONS:]
    parts: List[str] = []
    if prof.get("aliases"):
        parts.append("Nama pengirim yang pernah tercetak di SJ mitra ini: " + ", ".join(prof["aliases"]) + ".")
    loc = active_locale(prof) if prof else "unknown"
    if loc != "unknown":
        parts.append("Format angka mitra ini: " + ("Indonesia (titik = ribuan, koma = desimal)." if loc == "id"
                                                    else "Inggris (koma = ribuan, titik = desimal)."))
    if (prof.get("format_notes") or "").strip():
        parts.append("Catatan admin tentang tata letak SJ mitra ini: " + prof["format_notes"].strip())
    if corr:
        parts.append("Koreksi manusia pada pembacaan SJ mitra ini sebelumnya (hindari kesalahan serupa):")
        if any("nomor PO" in c["field"] for c in corr):
            parts.append("(Nomor PO baris bisa tercetak tanpa label, mis. dalam kurung di keterangan atau kecil di bawah "
                         "nama barang — bila terlihat di baris itu, salin ke po_ref.)")
        parts += [f"- {c['field']}: terbaca «{c['ocr']}», yang benar «{c['final']}»"
                  + (f" (baris: {c['context']})" if c.get("context") else "") for c in corr]
    if not parts:
        return {"text": "", "corrections": 0, "notes": False}
    head = ("PETUNJUK DARI SURAT JALAN MITRA INI YANG SUDAH DICEK MANUSIA. Pakai hanya untuk memahami tata letak dan "
            "format; tetap salin apa yang benar-benar terlihat di foto ini, jangan menyalin nilai dari petunjuk.")
    return {"text": head + "\n" + "\n".join(parts), "corrections": len(corr),
            "notes": bool((prof.get("format_notes") or "").strip())}


async def learn_from_grn(grn: Dict[str, Any]) -> Dict[str, Any]:
    """Dipanggil saat GRN `closed`. Idempoten per GRN (`learned_grn_ids`)."""
    flt = {"entity_id": grn["entity_id"], "partner_id": grn["partner_id"]}
    prof = await db.supplier_dn_profiles.find_one(flt, {"_id": 0}) or {}
    if grn["id"] in (prof.get("learned_grn_ids") or []):
        return prof
    ev = _locale_evidence(grn)
    votes = {k: int((prof.get("locale_votes") or {}).get(k, 0)) + ev[k] for k in ("id", "en")}
    ocr_lines = [ln for ln in grn.get("lines") or [] if (ln.get("read") or {}).get("source") == "ocr"]
    corrected = sum(1 for ln in ocr_lines if ln.get("corrected"))
    set_: Dict[str, Any] = {"locale_votes": votes, "updated_at": now_iso(), "partner_type": grn.get("partner_type"),
                            "partner_name": grn.get("partner_name", ""), "last_grn_number": grn.get("number", "")}
    if not prof.get("locale_locked"):
        set_["number_locale"] = _decide_locale(votes)
    for key, val in _item_learnings(grn).items():
        prev = (prof.get("item_map") or {}).get(key) or {}
        n = int(prev.get("count") or 0) + 1 if prev.get("product_id") == val["product_id"] else 1
        set_[f"item_map.{key}"] = {**val, "count": n, "at": now_iso()}
    upd: Dict[str, Any] = {"$setOnInsert": {"id": new_id("sdp"), "entity_id": grn["entity_id"],
                                            "partner_id": grn["partner_id"], "created_at": now_iso()},
                           "$set": set_,
                           "$inc": {"confirmed_count": 1, "ocr_reads": 1 if ocr_lines else 0,
                                    "ocr_lines_total": len(ocr_lines), "ocr_lines_corrected": corrected},
                           "$push": {"learned_grn_ids": {"$each": [grn["id"]], "$slice": -200}}}
    alias = _alias_to_add(prof, grn)
    if alias:
        upd["$addToSet"] = {"aliases": alias}
    await db.supplier_dn_profiles.update_one(flt, upd, upsert=True)
    await record_corrections(grn)
    return await db.supplier_dn_profiles.find_one(flt, {"_id": 0})


def public(prof: Dict[str, Any]) -> Dict[str, Any]:
    total = int(prof.get("ocr_lines_total") or 0)
    items = [{"key": k, **v} for k, v in (prof.get("item_map") or {}).items()]
    return {"partner_id": prof["partner_id"], "partner_name": prof.get("partner_name", ""),
            "partner_type": prof.get("partner_type", ""), "number_locale": prof.get("number_locale") or "unknown",
            "active_locale": active_locale(prof), "locale_locked": bool(prof.get("locale_locked")),
            "locale_votes": prof.get("locale_votes") or {"id": 0, "en": 0},
            "confirmed_count": int(prof.get("confirmed_count") or 0), "aliases": prof.get("aliases") or [],
            "item_map": sorted(items, key=lambda x: -int(x.get("count") or 0)),
            "ocr_reads": int(prof.get("ocr_reads") or 0), "ocr_lines_total": total,
            "ocr_lines_corrected": int(prof.get("ocr_lines_corrected") or 0),
            "ocr_accuracy_pct": round(100 * (1 - int(prof.get("ocr_lines_corrected") or 0) / total), 1) if total else None,
            "last_grn_number": prof.get("last_grn_number", ""), "updated_at": prof.get("updated_at", ""),
            "format_notes": prof.get("format_notes") or "",
            "corrections": list(reversed(prof.get("corrections") or []))[:HINT_CORRECTIONS]}


async def list_profiles(entity_id: str) -> List[Dict[str, Any]]:
    rows = await db.supplier_dn_profiles.find({"entity_id": entity_id}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return [public(r) for r in rows]


async def get_profile(entity_id: str, partner_id: str) -> Optional[Dict[str, Any]]:
    prof = await db.supplier_dn_profiles.find_one({"entity_id": entity_id, "partner_id": partner_id}, {"_id": 0})
    return public(prof) if prof else None


async def patch_profile(entity_id: str, partner_id: str, body: Any) -> Dict[str, Any]:
    flt = {"entity_id": entity_id, "partner_id": partner_id}
    prof = await db.supplier_dn_profiles.find_one(flt, {"_id": 0})
    if not prof:
        raise HTTPException(status_code=404, detail="Profil surat jalan mitra ini belum ada.")
    set_: Dict[str, Any] = {"updated_at": now_iso()}
    unset: Dict[str, str] = {}
    if body.number_locale is not None:
        set_["number_locale"], set_["locale_locked"] = body.number_locale, body.number_locale != "unknown"
        if body.number_locale == "unknown":
            set_["locale_votes"] = {"id": 0, "en": 0}
    aliases = [a for a in prof.get("aliases") or [] if a != (body.remove_alias or "")]
    if body.add_alias and body.add_alias.strip() and body.add_alias.strip() not in aliases:
        aliases.append(body.add_alias.strip())
    set_["aliases"] = aliases[:MAX_ALIASES]
    if body.format_notes is not None:
        set_["format_notes"] = body.format_notes.strip()[:600]
    if body.clear_corrections:
        set_["corrections"] = []
    if body.remove_item_key:
        unset[f"item_map.{body.remove_item_key}"] = ""
    await db.supplier_dn_profiles.update_one(flt, {"$set": set_, **({"$unset": unset} if unset else {})})
    return public(await db.supplier_dn_profiles.find_one(flt, {"_id": 0}))
