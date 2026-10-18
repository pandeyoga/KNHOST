"""LN-083/LN-092 — pengecualian retur (alasan + bukti foto + keputusan berwenang) dan gerbang settle."""
from typing import Any, Dict

from core_utils import new_id, now_iso
from db import db

KINDS = {
    "window": "Di luar batas waktu retur",
    "condition": "Kondisi barang (hangtag hilang / kain dipotong)",
    "discount_no_goods": "Diskon tanpa barang kembali (pengecualian QC fisik Rancamalang)",
}
IMAGE_TYPES = ("image/",)


def approved(ret: Dict[str, Any], kind: str) -> bool:
    return any(x.get("kind") == kind and x.get("status") == "approved" for x in ret.get("exceptions") or [])


async def request(ret: Dict[str, Any], kind: str, reason: str, attachment_ids, actor: Dict[str, Any]) -> Dict[str, Any]:
    if kind not in KINDS:
        raise ValueError("Jenis pengecualian tidak dikenal")
    if len((reason or "").strip()) < 10:
        raise ValueError("Alasan pengecualian minimal 10 karakter")
    atts = {a["id"]: a for a in ret.get("attachments") or [] if not a.get("is_deleted")}
    picked = [atts[i] for i in attachment_ids or [] if i in atts]
    if not picked or not any((a.get("content_type") or "").startswith(IMAGE_TYPES) for a in picked):
        raise ValueError("Lampirkan minimal satu foto bukti (unggah di Lampiran retur lalu pilih).")
    if any(x.get("kind") == kind and x.get("status") == "pending" for x in ret.get("exceptions") or []):
        raise ValueError("Masih ada pengajuan pengecualian jenis ini yang menunggu keputusan")
    elig = ret.get("policy_eligibility") or {}
    exc = {"id": new_id("rex"), "kind": kind, "label": KINDS[kind], "reason": reason.strip(),
           "attachment_ids": [a["id"] for a in picked], "status": "pending",
           "requested_by": actor.get("name", ""), "requested_by_id": actor.get("id", ""), "requested_at": now_iso(),
           # tanggal histori TIDAK diubah — hanya potret kondisi saat pengajuan
           "eligibility_snapshot": {k: elig.get(k) for k in ("decision", "deadline", "reference_source", "pending_decisions")}}
    await db.sales_returns.update_one({"id": ret["id"]}, {"$push": {"exceptions": exc}, "$set": {"updated_at": now_iso()}})
    return exc


async def decide(ret: Dict[str, Any], exc_id: str, approve: bool, note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    exc = next((x for x in ret.get("exceptions") or [] if x["id"] == exc_id), None)
    if not exc:
        raise LookupError("Pengecualian tidak ditemukan")
    if exc["status"] != "pending":
        raise ValueError(f"Pengecualian sudah {exc['status']}")
    if exc.get("requested_by_id") and exc["requested_by_id"] == actor.get("id"):
        raise ValueError("Pengaju tidak boleh memutuskan pengecualiannya sendiri")
    if not approve and len((note or "").strip()) < 5:
        raise ValueError("Alasan penolakan wajib diisi")
    upd = {"status": "approved" if approve else "rejected", "decided_by": actor.get("name", ""),
           "decided_by_id": actor.get("id", ""), "decided_at": now_iso(), "decision_note": (note or "").strip()}
    res = await db.sales_returns.update_one({"id": ret["id"], "exceptions": {"$elemMatch": {"id": exc_id, "status": "pending"}}},
                                            {"$set": {f"exceptions.$.{k}": v for k, v in upd.items()}})
    if not res.modified_count:
        raise ValueError("Pengecualian sudah diputuskan pihak lain")
    return {**exc, **upd}


async def assert_settle_allowed(ret: Dict[str, Any], outcome: str) -> None:
    from services.return_policy_service import return_assumptions
    elig = ret.get("policy_eligibility") or {}
    pend = {p.get("code") for p in elig.get("pending_decisions") or []}
    if "KLR-08" in pend and not approved(ret, "condition"):
        raise ValueError("Kondisi hangtag hilang / kain dipotong belum punya aturan final (KLR-08). "
                         "Ajukan pengecualian 'kondisi' dengan foto dan minta persetujuan sebelum diselesaikan.")
    if elig.get("decision") in ("outside_window", "blocked") and not approved(ret, "window"):
        raise ValueError("Retur di luar batas waktu. Ajukan pengecualian 'batas waktu' dengan alasan & foto.")
    if outcome == "nego":
        assume = await return_assumptions(ret.get("entity_id", ""))
        if assume.get("discount_mode", "pending") == "pending" and not approved(ret, "discount_no_goods"):
            raise ValueError("Diskon tanpa barang kembali belum punya kebijakan final (KLR-06/07). "
                             "Wajib pengecualian QC yang disetujui beserta foto bukti.")
