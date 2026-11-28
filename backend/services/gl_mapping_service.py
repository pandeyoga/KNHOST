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
        fixed = ln.pop("fixed_account", False)
        if key:
            ln["account_code"] = await account_for(key, entity_id)
            ln["mapping_key"] = key
        elif remap and not fixed and ln.get("account_code") in reg.REMAP_BY_DEFAULT:
            k = reg.REMAP_BY_DEFAULT[ln["account_code"]]
            code = await account_for(k, entity_id)
            if code != ln["account_code"]:
                ln["account_code"], ln["mapping_key"] = code, k
        out.append(ln)
    return out


async def known_codes(key: str, entity_id: Optional[str] = None) -> List[str]:
    """Semua akun yang pernah dipakai kebutuhan ini (bawaan + pemetaan kini + riwayat) — untuk pembaca saldo
    supaya jurnal lama (akun lama) dan jurnal baru (akun pemetaan) sama-sama terbaca.

    PK-29 (IV-05) — dengan `entity_id`: bawaan registri ∪ pemetaan global ∪ pemetaan PT itu ∪ riwayat pemetaan global
    (ber-`entity_id` kosong) atau PT itu. Pemetaan dan riwayat PT LAIN tidak ikut. Tanpa `entity_id`: semua lapisan
    (perilaku lama, dipakai pembaca lintas-PT)."""
    eid = _eid(entity_id)
    codes = {reg.require(key)["default"]}
    codes |= {r["account_code"] for (k, e), r in (await _rows()).items()
              if k == key and (not eid or e in ("", eid))}
    flt: Dict[str, Any] = {"key": key}
    if eid:
        flt["entity_id"] = {"$in": ["", None, eid]}
    async for h in db[HIST].find(flt, {"_id": 0, "from_code": 1, "to_code": 1}):
        codes |= {h.get("from_code"), h.get("to_code")} - {None, ""}
    return sorted(codes)


async def control_accounts(entity_id: Optional[str]) -> Dict[str, str]:
    """PK-36 (IC-06) — peta {kode akun: id buku pembantu} akun kontrol satu PT (tanpa PT = lapisan global).

    Untuk tiap kebutuhan ber-`control`: kode bawaan registri ∪ akun pemetaan efektif (PT → global → bawaan) ∪ kode
    `from_code`/`to_code` riwayat pemetaan global atau PT itu. Kode lama tetap terhitung: saldo buku pembantunya masih di
    sana. Riwayat dibaca sekali per panggilan; pemetaan memakai cache `_rows`."""
    eid = _eid(entity_id)
    by_key = {e["key"]: e["control"] for e in reg.ENTRIES if e.get("control")}
    out: Dict[str, str] = {}
    for key, ledger in by_key.items():
        out.setdefault(reg.require(key)["default"], ledger)
        out.setdefault((await resolve(key, eid))["account_code"], ledger)
    lapisan: List[Any] = ["", None] + ([eid] if eid else [])
    async for h in db[HIST].find({"key": {"$in": list(by_key)}, "entity_id": {"$in": lapisan}},
                                 {"_id": 0, "key": 1, "from_code": 1, "to_code": 1}):
        for code in (h.get("from_code"), h.get("to_code")):
            if code:
                out.setdefault(code, by_key[h["key"]])
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
    # UAT 24 Okt (audit UI tahap 2) — G1-08: jenis akun dinormalkan (alias `revenue` → `income`).
    out = [{"code": c, "name": a.get("name", ""), "type": reg.norm_type(a.get("type"))} for c, a in accs.items()
           if reg.norm_type(a.get("type")) in entry["allowed_types"] and a.get("is_active") is not False
           and a.get("is_postable") is not False]
    return sorted(out, key=lambda x: x["code"])


async def _write_history(key: str, eid: str, before: str, after: str, reason: str, actor: Dict[str, Any], action: str):
    await db[HIST].insert_one({"id": new_id("glmh"), "key": key, "entity_id": eid, "scope_type": "entity" if eid else "global",
                               "from_code": before, "to_code": after, "action": action, "reason": reason,
                               "by": actor.get("name", ""), "by_id": actor.get("id", ""), "at": now_iso()})


async def _periksa_akun_terpisah(key: str, eid: str, code: str) -> None:
    """Kas & Bank 4 (C8, putaran 1) — `code` tidak boleh akun pasangan terpisah `key` (`reg.AKUN_TERPISAH`): bawaan,
    pemetaan, atau riwayat pasangan itu (`known_codes`; PT → lapisan PT itu + grup, grup → semua lapisan, karena
    pemetaan grup berlaku di PT yang tidak menimpanya)."""
    for a, b in reg.AKUN_TERPISAH:
        if key not in (a, b):
            continue
        lain = b if key == a else a
        if code in await known_codes(lain, eid or None):
            raise ValueError(f"Akun {code} dipakai (atau pernah dipakai) untuk \"{reg.require(lain)['label']}\" "
                             f"({lain}). Uang muka karyawan dan uang muka pemasok harus di akun berbeda supaya saldonya "
                             f"bisa dicocokkan — pilih akun lain.")


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
    if a.get("bank_account_id"):
        # Kas & Bank 1 — akun rekening hanya diisi lewat kas ber-rekening; pemetaan ke sana membuat jurnal lain menulis
        # akun rekening tanpa dokumen kas (saldo akun ≠ buku kas rekening).
        rek = await db.bank_accounts.find_one({"id": a["bank_account_id"]}, {"_id": 0, "name": 1}) or {}
        raise ValueError(f"Akun {code} adalah akun rekening {rek.get('name') or a.get('name') or code}; akun rekening "
                         f"hanya diisi lewat kas atau Pindah Dana, bukan lewat Pemetaan Akun.")
    if reg.norm_type(a.get("type")) not in entry["allowed_types"]:
        allowed = ", ".join(reg.TYPE_LABEL[t] for t in entry["allowed_types"])
        raise ValueError(f"Akun {code} berjenis {reg.TYPE_LABEL.get(a.get('type'), a.get('type'))}; kebutuhan ini hanya menerima {allowed}.")
    await _periksa_akun_terpisah(key, eid, code)
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
