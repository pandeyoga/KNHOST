"""W2-REQ-03 — uji wajib SKU hasil MD (keputusan pemilik 2026-10-04: PERINGATAN, bukan blokir).

Wajib = usulan master lini (woven/knit → labdip+handfeel · printing → proofing) ∪ jenis yang
diminta pada sample. Kurang ACC → aksi tetap boleh, asal alasan override diisi; alasan tercatat.
Bahan standar (create product langsung) tidak melewati modul ini.
"""
from typing import Any, Dict, List, Optional

from core_utils import now_iso, timeline_entry
from db import db
from services import master_registry as mreg
from services.rnd_spec_service import RndError

MIN_REASON = 5


class RequiredTestsMissing(RndError):
    http_status = 422

    def __init__(self, missing: List[str], what: str):
        self.missing = list(missing)
        super().__init__(
            f"Uji wajib belum ACC: {', '.join(missing)}. {what} tetap boleh dilanjutkan, "
            f"tetapi alasan override wajib diisi (min. {MIN_REASON} huruf) dan akan tercatat.")


def _types(sample: Dict[str, Any]) -> List[str]:
    raw = list(sample.get("sample_types") or [])
    if not raw and sample.get("sample_type"):
        raw = [sample["sample_type"]]
    return [str(v).strip().lower() for v in raw if str(v or "").strip()]


def _round_type(rnd: Dict[str, Any], sample: Dict[str, Any]) -> str:
    code = str(rnd.get("type_code") or "").strip().lower()
    if code:
        return code
    kinds = _types(sample)
    return kinds[0] if kinds else ""


async def _line_defaults(line_code: str, entity_id: str) -> List[str]:
    if not str(line_code or "").strip():
        return []
    return await mreg.default_sample_types_for_line(line_code, entity_id)


def _summary(required: List[str], acc: set) -> Dict[str, Any]:
    req = list(dict.fromkeys(required))
    return {"required": req, "acc": [t for t in req if t in acc],
            "missing": [t for t in req if t not in acc]}


async def for_sample(sample: Dict[str, Any], supplier_id: str = "") -> Dict[str, Any]:
    required = await _line_defaults(sample.get("line_code"), sample.get("entity_id", "")) + _types(sample)
    acc = {_round_type(r, sample) for r in sample.get("rounds") or []
           if r.get("result") == "acc" and (not supplier_id or r.get("supplier_id") == supplier_id)}
    return _summary(required, acc)


async def for_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    samples = await db.md_samples.find(
        {"spec_id": spec["id"], "status": {"$ne": "cancelled"}},
        {"_id": 0, "sample_types": 1, "sample_type": 1, "rounds": 1}).to_list(200)
    required = await _line_defaults(spec.get("line_code"), spec.get("entity_id", ""))
    acc: set = set()
    for s in samples:
        required += _types(s)
        acc |= {_round_type(r, s) for r in s.get("rounds") or [] if r.get("result") == "acc"}
    return _summary(required, acc)


def resolve(gap: Dict[str, Any], reason: Optional[str], actor_name: str,
            what: str) -> Optional[Dict[str, Any]]:
    """None bila lengkap; catatan override bila kurang + alasan; selain itu 422."""
    if not gap["missing"]:
        return None
    text = (reason or "").strip()
    if len(text) < MIN_REASON:
        raise RequiredTestsMissing(gap["missing"], what)
    return {"missing": gap["missing"], "required": gap["required"], "reason": text,
            "by": actor_name, "at": now_iso(), "action": what}


def timeline_of(override: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not override:
        return []
    return [timeline_entry(
        "required_tests_override",
        f"Uji wajib belum ACC ({', '.join(override['missing'])}) — {override['action']} "
        "dilanjutkan dengan alasan", override["by"], override["reason"])]
