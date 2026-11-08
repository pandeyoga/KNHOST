"""Utilitas bersama protokol gate U300 V2 (dipakai rfid_v2_service & modul pendukungnya)."""
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from pymongo.write_concern import WriteConcern

from db import db


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    except ValueError:
        return None


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def compact_size(value: Any) -> int:
    """AUD-MW-18 — ukuran dihitung dengan separator ringkas (sama dengan agent Java), bukan json.dumps berspasi."""
    return len(json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode())


def fail(status: int, code: str, message: str, retryable: Optional[bool] = None,
         details: Optional[Dict[str, Any]] = None):
    """Galat terstruktur `detail.code` (AUD-MW-06) — agent memutuskan penanganan dari kode, bukan status HTTP."""
    body: Dict[str, Any] = {'code': code, 'message': message,
                            'retryable': status >= 500 if retryable is None else bool(retryable)}
    if details:
        body['details'] = details
    raise HTTPException(status, detail=body)


def collection(name: str):
    # ACK berarti tulisan journaled mayoritas, bukan sekadar antre di proses Python ini.
    return db.get_collection(name, write_concern=WriteConcern(w='majority', j=True, wtimeout=5000))
