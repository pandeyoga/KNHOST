"""Lampiran bukti retur — satu jalur untuk retur ke supplier & retur antar-PT (permintaan pemilik 23 Okt 2026).

Retur pelanggan sudah punya lampiran sendiri (`routers/sales_returns.py`); dua retur lainnya dulu tanpa bukti sama
sekali, padahal klaim ke supplier / PT penjual justru butuh foto cacat PER ROLL. Lampiran berlabel `roll_id`
adalah foto roll itu; kosong = bukti dokumen. Bentuk lampiran sama dengan retur pelanggan supaya satu panel
(`ReturnRollsPanel`) bisa menampilkan ketiganya.
"""
from typing import Any, Dict, Optional

from fastapi import UploadFile
from fastapi.responses import Response

from core_utils import new_id, now_iso
from db import db
from services import storage_service as storage


def claimed_roll_ids(doc: Dict[str, Any]) -> set:
    return {r for it in doc.get("items") or [] for r in (it.get("roll_ids") or [])}


async def store(coll: str, doc: Dict[str, Any], file: UploadFile, roll_id: str, actor_name: str,
                match: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Simpan satu berkas. `match` = filter dokumen yang ikut menerima lampiran (dokumen kembar antar-PT).
    ValueError → 400 di router."""
    roll_id = (roll_id or "").strip()
    if roll_id and roll_id not in claimed_roll_ids(doc):
        raise ValueError("Foto per roll: roll ini bukan roll klaim retur.")
    data = await file.read()
    content_type = storage.validate_upload(file.filename, file.content_type, len(data), data[:16])
    path = f"{coll}/{doc['id']}/{new_id('att')}-{file.filename}"
    result = await storage.put_object(path, data, content_type)
    att = {"id": new_id("att"), "filename": file.filename, "url": result.get("url", ""), "path": path,
           "size": len(data), "content_type": content_type, "uploaded_by": actor_name, "uploaded_at": now_iso(),
           "is_deleted": False, "roll_id": roll_id}
    await db[coll].update_many(match or {"id": doc["id"]},
                               {"$push": {"attachments": att}, "$set": {"updated_at": now_iso()}})
    return att


async def download(doc: Dict[str, Any], att_id: str) -> Response:
    att = next((a for a in (doc.get("attachments") or []) if a.get("id") == att_id and not a.get("is_deleted")), None)
    if not att:
        raise LookupError("Lampiran tidak ditemukan")
    data, _ = await storage.get_object(att["path"])
    return Response(content=data, media_type=att.get("content_type", "application/octet-stream"),
                    headers={"Content-Disposition": f'attachment; filename="{att["filename"]}"'})
