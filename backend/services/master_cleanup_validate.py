"""PREP-A — validasi lembar perbaikan master produk (pratinjau, TIDAK menulis apa pun).

Masukan: baris hasil `master_cleanup_sheet.parse_sheet` (atau `actions` yang dikirim balik dari pratinjau).
Keluaran: rencana per baris + galat/peringatan berbahasa Indonesia + tanda tangan pratinjau. Tanda tangan
dicocokkan ulang saat Terapkan (pola `master_governance_service.apply_batch`): data yang berubah sejak
pratinjau → 409, pengguna wajib pratinjau ulang.

Tindakan (K-OPN-06): PERTAHANKAN | GANTI_NAMA | GANTI_KODE | GABUNG_KE | NONAKTIFKAN.
SKU tidak pernah diubah: GANTI_KODE membuat produk baru berkode benar, kode lama dinonaktifkan +
`superseded_by`. Produk berdokumen TERBUKA tidak boleh GANTI_KODE/GABUNG_KE/NONAKTIFKAN.
"""
import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from pymongo.collation import Collation

from core_utils import qty_dual
from db import db
from role_registry import role_in
from services import line_scope
from services import master_cleanup_refs as refs
from services.catalog_access import visible_query
from services.master_usage_service import LIFECYCLE_ROLES

KEEP, RENAME, RECODE, MERGE, DEACTIVATE = "PERTAHANKAN", "GANTI_NAMA", "GANTI_KODE", "GABUNG_KE", "NONAKTIFKAN"
ACTIONS = (KEEP, RENAME, RECODE, MERGE, DEACTIVATE)
RETIRING = (RECODE, MERGE, DEACTIVATE)          # mengakhiri SKU lama → dicek dokumen terbuka & peran
ORDER = {RENAME: 0, RECODE: 1, MERGE: 2, DEACTIVATE: 3}
SKU_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]{0,79}$")
MAX_ROWS = 20000
FIELDS = ("tindakan", "nama_benar", "kode_benar", "digantikan_oleh_sku", "catatan")
_PROJ = {"_id": 0, "id": 1, "sku": 1, "name": 1, "status": 1, "superseded_by": 1, "updated_at": 1,
         "template_id": 1, "base_unit": 1, "stage": 1, "fabric_type": 1, "line_code": 1, "saga_lock": 1}


def normalize_action(raw: Any) -> str:
    s = re.sub(r"[\s\-]+", "_", str(raw or "").strip().upper())
    return s or KEEP


def _txt(v: Any) -> str:
    return str(v if v is not None else "").strip()


def _clean_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for i, r in enumerate(rows[:MAX_ROWS]):
        out.append({"row": int(r.get("row") or i + 2), "id": _txt(r.get("id") or r.get("product_id")),
                    "sku": _txt(r.get("sku")), "tindakan": normalize_action(r.get("tindakan")),
                    **{f: _txt(r.get(f)) for f in FIELDS if f != "tindakan"}})
    return out


async def _load(actor: Dict[str, Any], rows: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
    ids = sorted({r["id"] for r in rows if r["id"]})
    skus = sorted({r["sku"] for r in rows if r["sku"]} | {r["digantikan_oleh_sku"] for r in rows if r["digantikan_oleh_sku"]})
    ors = ([{"id": {"$in": ids}}] if ids else []) + ([{"sku": {"$in": skus}}] if skus else [])
    if not ors:
        return {}, {}
    found = await db.products.find(visible_query(actor, {"$or": ors}), _PROJ).to_list(2 * MAX_ROWS)
    return {p["id"]: p for p in found}, {p["sku"]: p for p in found}


async def _codes_taken(codes: List[str]) -> Dict[str, Dict[str, Any]]:
    """Kode yang sudah dipakai produk MANA PUN (termasuk yang tak terlihat user / nonaktif)."""
    if not codes:
        return {}
    # satu pemindaian `$in` tanpa beda huruf besar/kecil (collation strength 2), bukan N regex
    rows = await db.products.find({"sku": {"$in": codes}}, {"_id": 0, "id": 1, "sku": 1, "status": 1},
                                  collation=Collation(locale="en", strength=2)).to_list(len(codes) * 3 + 5)
    return {str(r["sku"]).upper(): r for r in rows}


def _stock_note(s: Optional[Dict[str, Any]], unit: str) -> str:
    if not s:
        return ""
    return (f"Stok lama {qty_dual(s.get('rolls'), s.get('qty'), unit)} tetap tercatat di SKU lama (tidak dipindah) — "
            "didaftarkan ulang dari fisik lewat opname awal.")


async def validate(actor: Dict[str, Any], raw_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = _clean_rows(raw_rows)
    keep = [r for r in rows if r["tindakan"] == KEEP]
    acts = [r for r in rows if r["tindakan"] != KEEP]
    by_id, by_sku = await _load(actor, acts)
    out_rows: List[Dict[str, Any]] = []
    plan: List[Dict[str, Any]] = []
    seen: Dict[str, int] = {}
    targets_new: Dict[str, int] = {}          # kode_benar (UPPER) → baris GANTI_KODE
    new_src: Dict[str, Dict[str, Any]] = {}   # kode_benar (UPPER) → produk lama yang diganti kodenya
    retiring_in_sheet: Dict[str, Tuple[int, str, str]] = {}   # product_id → (baris, tindakan, target sku)
    resolved: List[Tuple[Dict[str, Any], Optional[Dict[str, Any]]]] = []
    for r in acts:
        res = {"row": r["row"], "sku": r["sku"], "name": "", "tindakan": r["tindakan"], "detail": "",
               "errors": [], "warnings": [], "product_id": ""}
        p = None
        if r["tindakan"] not in ACTIONS:
            res["errors"].append(f"Tindakan '{r['tindakan']}' tidak dikenal — pilih salah satu: {', '.join(ACTIONS)}.")
        if not r["id"] and not r["sku"]:
            res["errors"].append("Kolom wajib kosong: id atau sku.")
        elif r["id"]:
            p = by_id.get(r["id"])
            if not p:
                res["errors"].append(f"ID produk {r['id']} tidak dikenal (atau di luar akses Anda).")
            elif r["sku"] and r["sku"] != p.get("sku"):
                res["errors"].append(f"ID dan SKU tidak cocok: ID ini milik SKU {p.get('sku')} — baris tergeser/tercampur?")
                p = None
        else:
            p = by_sku.get(r["sku"])
            if not p:
                res["errors"].append(f"SKU {r['sku']} tidak dikenal (atau di luar akses Anda).")
        if p:
            res.update(product_id=p["id"], sku=p.get("sku"), name=p.get("name", ""))
            if p["id"] in seen:
                res["errors"].append(f"Produk ini sudah punya tindakan di baris {seen[p['id']]} — satu produk satu tindakan.")
            else:
                seen[p["id"]] = r["row"]
            if p.get("saga_lock"):
                res["errors"].append("SKU sedang diproses (kunci saga) — tunggu lalu pratinjau ulang.")
            if not line_scope.can_touch(actor, p):
                res["errors"].append("SKU di luar lini akses Anda.")
        if r["tindakan"] == RECODE and r["kode_benar"]:
            targets_new.setdefault(r["kode_benar"].upper(), r["row"])
            if p:
                new_src.setdefault(r["kode_benar"].upper(), p)
        if p and r["tindakan"] in RETIRING:
            retiring_in_sheet[p["id"]] = (r["row"], r["tindakan"], r["digantikan_oleh_sku"] or r["kode_benar"])
        resolved.append((r, p))
        out_rows.append(res)
    pids = [p["id"] for _, p in resolved if p]
    docs = (await refs.open_docs_by_product(pids))["by_product"]
    stock = await refs.stock_by_product(pids)
    taken = await _codes_taken(sorted({r["kode_benar"] for r, _ in resolved if r["tindakan"] == RECODE and r["kode_benar"]}))
    tpl_ids = sorted({p.get("template_id") for _, p in resolved if p and p.get("template_id")})
    tpls = {t["id"]: t for t in await db.product_templates.find(
        {"id": {"$in": tpl_ids}}, {"_id": 0, "id": 1, "name": 1, "status": 1}).to_list(len(tpl_ids) + 1)}
    code_rows: Dict[str, List[int]] = {}
    for r, _ in resolved:
        if r["tindakan"] == RECODE and r["kode_benar"]:
            code_rows.setdefault(r["kode_benar"].upper(), []).append(r["row"])
    state: List[Any] = []
    for (r, p), res in zip(resolved, out_rows):
        t = r["tindakan"]
        if not p or t not in ACTIONS:
            continue
        E, W = res["errors"], res["warnings"]
        sup = p.get("superseded_by")
        state.append([p["id"], p.get("sku"), p.get("name"), p.get("status"), sup or "", p.get("updated_at")])
        own_docs = docs.get(p["id"], [])
        blocking = [d for d in own_docs if d.get("blocking", True)]
        step: Dict[str, Any] = {"row": r["row"], "tindakan": t, "product_id": p["id"], "sku": p.get("sku"),
                                "before_name": p.get("name"), "before_status": p.get("status", "active"),
                                "catatan": r["catatan"]}
        if t in RETIRING:
            if sup:
                E.append("SKU ini sudah digantikan sebelumnya — tidak bisa diproses lagi (batalkan batch lamanya dulu).")
            if blocking:
                E.append(f"Masih dipakai {len(blocking)} dokumen terbuka: {refs.docs_text(blocking)} — "
                         "selesaikan/alihkan dulu, lalu unggah ulang.")
            if len(blocking) != len(own_docs):
                W.append("Dokumen jangka panjang masih menunjuk SKU ini: "
                         f"{refs.docs_text([d for d in own_docs if not d.get('blocking', True)])} — perbarui sesudahnya.")
            note = _stock_note(stock.get(p["id"]), p.get("base_unit", ""))
            if note:
                W.append(note)
            state.append(["docs", p["id"], sorted(d["number"] for d in blocking)])
        if t == RENAME:
            if not r["nama_benar"]:
                E.append("Kolom wajib kosong: nama_benar untuk GANTI_NAMA.")
            elif len(r["nama_benar"]) > 200:
                E.append("nama_benar terlalu panjang (maks. 200 karakter).")
            elif r["nama_benar"] == (p.get("name") or "").strip():
                W.append("nama_benar sama dengan nama sekarang — baris dilewati.")
                step = {}
            else:
                res["detail"] = f"nama → {r['nama_benar']}"
                step["nama_benar"] = r["nama_benar"]
        elif t == RECODE:
            code = r["kode_benar"]
            if not code:
                E.append("Kolom wajib kosong: kode_benar untuk GANTI_KODE.")
            elif not SKU_RE.match(code):
                E.append(f"kode_benar '{code}' tidak sah — huruf/angka/. _ / - saja, tanpa spasi, maks. 80 karakter.")
            elif code.upper() == str(p.get("sku") or "").upper():
                E.append("kode_benar sama dengan SKU sekarang — pakai PERTAHANKAN/GANTI_NAMA.")
            elif code.upper() in taken:
                o = taken[code.upper()]
                E.append(f"kode_benar {code} sudah dipakai produk {o.get('sku')} ({o.get('status', 'active')}) — "
                         "bila produk itu memang induknya, pakai GABUNG_KE.")
            elif len(code_rows.get(code.upper(), [])) > 1:
                E.append(f"kode_benar {code} dipakai lebih dari satu baris: {', '.join(map(str, code_rows[code.upper()]))}.")
            tid = p.get("template_id")
            if tid and (tpls.get(tid) or {}).get("status", "") != "active":
                E.append("Induk/artikel produk ini tidak aktif atau tidak ditemukan — aktifkan induknya dulu.")
            if r["nama_benar"] and len(r["nama_benar"]) > 200:
                E.append("nama_benar terlalu panjang (maks. 200 karakter).")
            if r["digantikan_oleh_sku"]:
                W.append("digantikan_oleh_sku diabaikan untuk GANTI_KODE (pengganti = produk berkode benar).")
            res["detail"] = f"kode baru {code}" + (f" · nama {r['nama_benar']}" if r["nama_benar"] else "")
            step.update(kode_benar=code, nama_benar=r["nama_benar"], template_id=tid or "")
            state.append(["code", code.upper(), bool(taken.get(code.upper()))])
        elif t == MERGE:
            tgt_sku = r["digantikan_oleh_sku"]
            if not tgt_sku:
                E.append("Kolom wajib kosong: digantikan_oleh_sku untuk GABUNG_KE.")
            elif tgt_sku == p.get("sku"):
                E.append("digantikan_oleh_sku tidak boleh menunjuk dirinya sendiri.")
            elif tgt_sku.upper() in targets_new and tgt_sku not in by_sku:
                src = new_src.get(tgt_sku.upper()) or {}
                if src and (src.get("base_unit") or "") != (p.get("base_unit") or ""):
                    E.append(f"Satuan dasar berbeda ({p.get('base_unit') or '-'} vs {src.get('base_unit') or '-'}) — "
                             "tidak bisa digabung.")
                step.update(target_new_code=tgt_sku, target_sku=tgt_sku)
                res["detail"] = f"gabung ke {tgt_sku} (kode baru dari baris {targets_new[tgt_sku.upper()]})"
            else:
                tgt = by_sku.get(tgt_sku)
                if not tgt:
                    E.append(f"SKU target {tgt_sku} tidak dikenal (atau di luar akses Anda).")
                elif tgt.get("superseded_by"):
                    E.append(f"SKU target {tgt_sku} sudah digantikan — arahkan langsung ke SKU penggantinya.")
                elif tgt.get("status", "active") != "active":
                    E.append(f"SKU target {tgt_sku} nonaktif — pilih produk induk yang aktif.")
                elif tgt["id"] in retiring_in_sheet:
                    trow, tact, tnext = retiring_in_sheet[tgt["id"]]
                    if tnext and tnext == p.get("sku"):
                        E.append(f"Siklus 'digantikan oleh': {p.get('sku')} → {tgt_sku} → {p.get('sku')} (baris {trow}).")
                    else:
                        E.append(f"SKU target {tgt_sku} juga di-{tact} di baris {trow} — rantai tidak boleh; "
                                 f"arahkan langsung ke {tnext or 'SKU akhir'}.")
                else:
                    if (tgt.get("base_unit") or "") != (p.get("base_unit") or ""):
                        E.append(f"Satuan dasar berbeda ({p.get('base_unit') or '-'} vs {tgt.get('base_unit') or '-'}) — "
                                 "tidak bisa digabung.")
                    elif (tgt.get("stage"), tgt.get("fabric_type")) != (p.get("stage"), p.get("fabric_type")):
                        W.append("Stage/jenis kain target berbeda — pastikan memang produk yang sama.")
                    step.update(target_id=tgt["id"], target_sku=tgt_sku)
                    res["detail"] = f"gabung ke {tgt_sku} — {tgt.get('name', '')}"
                    state.append(["target", tgt["id"], tgt.get("status"), tgt.get("superseded_by") or "",
                                  tgt.get("updated_at")])
        elif t == DEACTIVATE:
            if p.get("status", "active") != "active" and not sup:
                W.append("SKU sudah nonaktif — baris dilewati.")
                step = {}
            else:
                res["detail"] = "nonaktif tanpa pengganti"
        if step and not E:
            plan.append(step)
    for r in keep:
        if any(r[f] for f in ("nama_benar", "kode_benar", "digantikan_oleh_sku")):
            out_rows.append({"row": r["row"], "sku": r["sku"], "name": "", "tindakan": KEEP, "detail": "",
                             "errors": [], "warnings": ["Kolom perbaikan diisi tetapi tindakan PERTAHANKAN — diabaikan."],
                             "product_id": r["id"]})
    general: List[str] = []
    if any(s["tindakan"] in RETIRING for s in plan) and not role_in(actor.get("role"), LIFECYCLE_ROLES):
        general.append("Hanya Admin atau MD yang boleh menonaktifkan/menggantikan SKU (GANTI_KODE, GABUNG_KE, NONAKTIFKAN).")
    if len(raw_rows) > MAX_ROWS:
        general.append(f"Lembar memuat {len(raw_rows)} baris — maks. {MAX_ROWS} per unggahan.")
    n_err = sum(len(x["errors"]) for x in out_rows) + len(general)
    summary = {a: sum(1 for s in plan if s["tindakan"] == a) for a in ACTIONS if a != KEEP}
    summary.update(rows_read=len(rows), pertahankan=len(keep), errors=n_err,
                   warnings=sum(len(x["warnings"]) for x in out_rows), changes=len(plan))
    actions = [{"row": r["row"], "id": r["id"], "sku": r["sku"], **{f: r[f] for f in FIELDS}} for r in acts]
    plan.sort(key=lambda s: (ORDER.get(s["tindakan"], 9), s["row"]))
    sig_src = json.dumps({"actions": actions, "plan": plan, "state": state, "errors": n_err}, sort_keys=True, default=str)
    return {"summary": summary, "rows": sorted(out_rows, key=lambda x: x["row"]), "general_errors": general,
            "can_apply": n_err == 0 and bool(plan), "actions": actions, "plan": plan,
            "preview_signature": hashlib.sha256(sig_src.encode()).hexdigest()[:24]}
