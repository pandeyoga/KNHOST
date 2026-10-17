"""L08 LN-080-T03 — kewajiban bukti (lampiran) retur per tahap, dapat dikonfigurasi per badan usaha."""
from typing import Any, Dict, List, Optional

STAGES = {
    "submit": "diajukan untuk persetujuan",
    "approve": "disetujui",
    "inspect": "inspeksi diselesaikan",
    "settle": "diselesaikan",
}


async def policy(entity_id: Optional[str]) -> Dict[str, bool]:
    from services import config_resolver
    ctx = {"entity_id": entity_id} if entity_id and entity_id != "all" else None
    return {s: bool(await config_resolver.value_of(f"returns.evidence_required_{s}", ctx)) for s in STAGES}


def evidence_count(doc: Dict[str, Any]) -> int:
    return sum(1 for a in (doc.get("attachments") or []) if not a.get("is_deleted"))


async def describe(doc: Dict[str, Any]) -> Dict[str, Any]:
    pol = await policy(doc.get("entity_id"))
    n = evidence_count(doc)
    return {"required": pol, "count": n,
            "missing_for": [s for s, on in pol.items() if on and n == 0]}


async def assert_evidence(doc: Dict[str, Any], stage: str) -> None:
    pol = await policy(doc.get("entity_id"))
    if pol.get(stage) and evidence_count(doc) == 0:
        raise ValueError(
            f"Bukti foto wajib sebelum retur {STAGES[stage]}. Unggah minimal satu foto/dokumen "
            "di panel Lampiran bukti, lalu ulangi.")


def stages_requiring(pol: Dict[str, bool]) -> List[str]:
    return [s for s, on in pol.items() if on]
