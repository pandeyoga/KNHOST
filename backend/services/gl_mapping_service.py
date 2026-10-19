"""GL-01 — pemetaan akun terpusat. Resolver: mapping PT → mapping global → bawaan registri.
Perubahan hanya berlaku untuk jurnal baru (GL-08); jurnal lama tidak diposting ulang."""
import time
from typing import Any, Dict, List, Optional

from core_utils import new_id, now_iso
from db import db
from services import gl_mapping_registry as reg

COLL = "gl_account_mappings"
HIST = "gl_account_mapping_history"
# Jurnal yang harus mencerminkan aslinya / diketik manusia — tidak dialihkan.
NO_REMAP_SOURCES = {"manual", "manual_void", "reversal", "closing", "suspense_reclass", "preflight"}
_TTL = 10.0
_cache: Dict[str, Any] = {"at": 0.0, "rows": {}}


def invalidate() -> None:
    _cache["at"] = 0.0


async def _rows() -> Dict[tuple, Dict[str, Any]]:
    if time.monotonic() - _cache["at"] < _TTL:
        return _cache["rows"]
    rows = {}
    async for d in db[COLL].find({}, {"_id": 0}):
        rows[(d["key"], d.get("entity_id") or "")] = d
    _cache.update(at=time.monotonic(), rows=rows)
    return rows


def _eid(entity_id: Optional[str]) -> str:
    return "" if not entity_id or entity_id == "all" else entity_id


async def resolve(key: str, entity_id: Optional[str] = None) -> Dict[str, Any]:
    entry = reg.require(key)
    rows = await _rows()
    eid = _eid(entity_id)
    if eid and (key, eid) in rows:
        return {"account_code": rows[(key, eid)]["account_code"], "source": "entity", "row": rows[(key, eid)]}
    if (key, "") in rows:
        return {"account_code": rows[(key, "")]["account_code"], "source": "global", "row": rows[(key, "")]}
    return {"account_code": entry["default"], "source": "default", "row": None}


async def account_for(key: str, entity_id: Optional[str] = None) -> str:
    return (await resolve(key, entity_id))["account_code"]


async def remap_lines(lines: List[Dict[str, Any]], entity_id: str, source_type: str) -> List[Dict[str, Any]]:
    """Baris ber-`account_key` → akun pemetaan. Baris konstanta lama (kode bawaan) → akun pemetaan."""
    out = []
    remap = source_type not in NO_REMAP_SOURCES and "reversal" not in (source_type or "")
    for ln in lines:
        ln = dict(ln)
        key = ln.pop("account_key", None)
        if key:
            ln["account_code"] = await account_for(key, entity_id)
            ln["mapping_key"] = key
        elif remap and ln.get("account_code") in reg.REMAP_BY_DEFAULT:
            k = reg.REMAP_BY_DEFAULT[ln["account_code"]]
            code = await account_for(k, entity_id)
            if code != ln["account_code"]:
                ln["account_code"], ln["mapping_key"] = code, k
        out.append(ln)
    return out


async def _accounts(entity_id: str) -> Dict[str, Dict[str, Any]]:
    from services.gl_service import effective_accounts
    return await effective_accounts(None, entity_id or None)


def _status(code: str, accs: Dict[str, Dict[str, Any]]) -> str:
    a = accs.get(code)
    if not a:
        return "unset"
    if a.get("is_active") is False or a.get("is_postable") is False:
        return "inactive"
    return "ok"


async def list_mappings(entity_id: Optional[str]) -> Dict[str, Any]:
    eid = _eid(entity_id)
    accs = await _accounts(eid)
    rows = await _rows()
    out = []
    for e in reg.ENTRIES:
        r = await resolve(e["key"], eid)
        code = r["account_code"]
        a = accs.get(code) or {}
        g = rows.get((e["key"], ""))
        out.append({**{k: e[k] for k in ("key", "module", "label", "used_when", "used_by", "default", "required", "remap")},
                    "example": {"debit": e["example"][0], "credit": e["example"][1]},
                    "allowed_types": e["allowed_types"],
                    "allowed_type_labels": [reg.TYPE_LABEL[t] for t in e["allowed_types"]],
                    "account_code": code, "account_name": a.get("name", ""), "source": r["source"],
                    "global_code": (g or {}).get("account_code") or e["default"],
                    "status": _status(code, accs),
                    "updated_by": (r["row"] or {}).get("updated_by", ""),
                    "updated_at": (r["row"] or {}).get("updated_at", ""),
                    "version": (r["row"] or {}).get("version", 0)})
    summary = {"total": len(out), "unset": sum(1 for x in out if x["status"] != "ok"),
               "custom": sum(1 for x in out if x["source"] != "default"),
               "entity_override": sum(1 for x in out if x["source"] == "entity")}
    return {"entity_id": eid, "modules": [{"id": m, "label": l} for m, l in reg.MODULES],
            "rows": out, "summary": summary,
            "notice": "Perubahan berlaku untuk jurnal baru; jurnal lama tidak diposting ulang."}


async def candidates(key: str, entity_id: Optional[str]) -> List[Dict[str, Any]]:
    entry = reg.require(key)
    accs = await _accounts(_eid(entity_id))
    out = [{"code": c, "name": a.get("name", ""), "type": a.get("type", "")} for c, a in accs.items()
           if a.get("type") in entry["allowed_types"] and a.get("is_active") is not False
           and a.get("is_postable") is not False]
    return sorted(out, key=lambda x: x["code"])


async def _write_history(key: str, eid: str, before: str, after: str, reason: str, actor: Dict[str, Any], action: str):
    await db[HIST].insert_one({"id": new_id("glmh"), "key": key, "entity_id": eid, "scope_type": "entity" if eid else "global",
                               "from_code": before, "to_code": after, "action": action, "reason": reason,
                               "by": actor.get("name", ""), "by_id": actor.get("id", ""), "at": now_iso()})


async def set_mapping(key: str, entity_id: Optional[str], account_code: str, reason: str,
                      actor: Dict[str, Any]) -> Dict[str, Any]:
    entry = reg.require(key)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValueError("Alasan perubahan wajib diisi (minimal 5 huruf).")
    eid = _eid(entity_id)
    code = (account_code or "").strip()
    a = (await _accounts(eid)).get(code)
    if not a:
        raise ValueError(f"Akun {code} tidak ada di bagan akun.")
    if a.get("is_active") is False or a.get("is_postable") is False:
        raise ValueError(f"Akun {code} nonaktif atau akun induk — tidak bisa dipakai.")
    if a.get("type") not in entry["allowed_types"]:
        allowed = ", ".join(reg.TYPE_LABEL[t] for t in entry["allowed_types"])
        raise ValueError(f"Akun {code} berjenis {reg.TYPE_LABEL.get(a.get('type'), a.get('type'))}; kebutuhan ini hanya menerima {allowed}.")
    before = await account_for(key, eid)
    cur = await db[COLL].find_one({"key": key, "entity_id": eid}, {"_id": 0}) or {}
    doc = {"id": cur.get("id") or new_id("glm"), "key": key, "scope_type": "entity" if eid else "global",
           "entity_id": eid, "account_code": code, "reason": reason, "updated_by": actor.get("name", ""),
           "updated_by_id": actor.get("id", ""), "updated_at": now_iso(), "version": int(cur.get("version", 0)) + 1}
    await db[COLL].update_one({"key": key, "entity_id": eid}, {"$set": doc}, upsert=True)
    invalidate()
    await _write_history(key, eid, before, code, reason, actor, "set")
    return doc


async def reset_mapping(key: str, entity_id: Optional[str], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    reg.require(key)
    if len((reason or "").strip()) < 5:
        raise ValueError("Alasan wajib diisi (minimal 5 huruf).")
    eid = _eid(entity_id)
    before = await account_for(key, eid)
    res = await db[COLL].delete_one({"key": key, "entity_id": eid})
    if not res.deleted_count:
        raise ValueError("Tidak ada pemetaan khusus untuk dikembalikan.")
    invalidate()
    after = await account_for(key, eid)
    await _write_history(key, eid, before, after, reason.strip(), actor, "reset")
    return {"key": key, "entity_id": eid, "account_code": after}


async def history(key: Optional[str], entity_id: Optional[str], limit: int = 100) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {}
    if key:
        q["key"] = key
    if entity_id is not None:
        q["entity_id"] = _eid(entity_id)
    return await db[HIST].find(q, {"_id": 0}).sort("at", -1).to_list(limit)
