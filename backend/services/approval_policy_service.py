"""services/approval_policy_service.py — SATU tabel kebijakan persetujuan untuk semua antrean (unit KP-T4).

Satu baris `approval_policies` = satu rentang nominal pada satu jenjang satu jenis dokumen (`approval_kinds.py`),
untuk grup (`entity_id = "all"`) atau satu PT. Yang boleh memutus = pemegang izin setujui jenis itu **dan**
(`any_holder` atau perannya tercantum di `roles` rentang yang memuat nilai dokumen). Tidak ada peringkat peran dan
tidak ada peran acuan di sini (K-51, standar Z4).

Sumber baris untuk (jenis, PT):
  1. baris aktif khusus PT itu  → sumber `pt`   (menggantikan seluruh baris grup jenis itu, seperti KP-T3);
  2. baris aktif grup            → sumber `grup`;
  3. belum ada baris sama sekali → sumber `bawaan`: baris dihitung dari sumber lama (`build_default_rows`) dengan nilai
     efektif PT itu — keputusan sama persis dengan sebelum unit ini sampai migrasi
     (`scripts/migrate_kpt4_kebijakan_persetujuan.py`) menuliskannya.

Fungsi ini TIDAK memeriksa "pembuat ≠ penyetuju" maupun jumlah orang (`services/dual_control.py`, KF-T6).
"""
import math
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from approval_kinds import APPROVAL_KINDS, GROUPS, has_amount, kind, perm_pairs
from core_utils import new_id, now_iso
from db import db

COLL = "approval_policies"
_INF = float("inf")
SOURCES = ("bawaan", "migrasi", "pengguna")


# ── Peran ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _registry():
    import role_registry
    return role_registry


def role_label(rid: str) -> str:
    return _registry().role_label(rid)


def _ordered(ids) -> List[str]:
    reg = _registry()
    want = set(ids)
    return [r for r in reg.role_ids() if r in want]


def roles_rank_at_least(required: str, unknown_as_manager: bool = True) -> Tuple[List[str], bool]:
    """Semua peran (bawaan + kustom) yang HARI INI lolos peringkat `required` → (roles, any_holder).

    Dipakai HANYA untuk membentuk baris bawaan dari sumber lama (setara peringkat hari ini, K-51). `unknown_as_manager`
    meniru `role_registry.required_rank` (nilai tak dikenal = peringkat Manajer); False meniru `rank_of` (= 0)."""
    reg = _registry()
    if not required:
        return [], False
    need = reg.ROLE_RANK.get(required, reg._DEFAULT_REQUIRED_RANK if unknown_as_manager else 0)
    if need <= 0:
        return [], True
    return [r for r in reg.role_ids() if reg.ROLES[r]["rank"] >= need], False


def roles_with_base(ids) -> List[str]:
    """Peran itu sendiri + peran kustom beracuan padanya (meniru `role_registry.role_in`)."""
    reg = _registry()
    want = {str(i).strip() for i in ids if str(i or "").strip()}
    return [r for r in reg.role_ids()
            if r in want or ((reg.ROLES[r].get("base_role") or "") in want)]


def roles_exact(ids) -> List[str]:
    return _ordered({str(i).strip().lower() for i in ids if str(i or "").strip()})


# ── Angka & rentang ────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    v = float(x)
    return int(v) if v == int(v) else v


def _bounds(row: Dict[str, Any]) -> Tuple[float, float]:
    lo = float(row.get("min_amount") or 0)
    hi = row.get("max_amount")
    return lo, (float(hi) if hi not in (None, "") else _INF)


def _contains(row: Dict[str, Any], amount: float) -> bool:
    lo, hi = _bounds(row)
    return lo <= amount < hi or (amount == hi == _INF)


def rp(x: float) -> str:
    v = round(float(x or 0), 2)
    if v == int(v):
        return "Rp" + f"{int(v):,}".replace(",", ".")
    return "Rp" + f"{v:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")


def _needs(row: Optional[Dict[str, Any]]) -> bool:
    return bool(row) and (bool(row.get("any_holder")) or bool(row.get("roles")))


def _row(doc_kind: str, entity_id: str, level: int, roles: List[str], *, any_holder: bool = False,
         min_amount: float = 0.0, max_amount: Optional[float] = None, label: str = "", sort: int = 1,
         legacy_role: str = "", setara: bool = True) -> Dict[str, Any]:
    """`legacy_role` = peran tunggal sumber lama (mis. `required_role` aturan SO/PO/PR) — HANYA untuk field kompatibel
    `required_role` / `required_approval_role` yang masih dibaca tampilan & notifikasi; tidak pernah untuk memutus.

    K-FIN-01 — baris bawaan yang menyebut Manajer ikut menyebut Finance (dan peran kustom ber-dasar Finance):
    `role_registry.SETARA_PERAN`. Baris yang hanya menyebut Admin tidak berubah. `setara=False` = baris isian Admin
    (`_parse_levels`): disimpan persis seperti dipilih (review K-FIN-01 R-KF-01 — dulu Finance ditambahkan diam-diam
    sehingga Admin tidak bisa menyimpan "Manajer saja")."""
    if setara and not any_holder and roles:
        roles = _ordered({*roles, *_registry().setara_untuk(roles)})
    return {"doc_kind": doc_kind, "entity_id": entity_id or "all", "level": int(level),
            "label": label or (kind(doc_kind)["level_labels"].get(int(level)) or "Persetujuan"),
            "min_amount": _num(min_amount) or 0, "max_amount": _num(max_amount),
            "roles": [] if any_holder else list(roles), "any_holder": bool(any_holder), "sort": int(sort),
            "active": True, "source": "bawaan", "legacy_role": legacy_role or ""}


# ── Baris bawaan dari sumber lama (setara keputusan hari ini) ──────────────────────────────────────────────────────
# KP-T4 (b) — daftar & ambang yang dulu ditulis di kode pintu kini HANYA sumber baris bawaan (dibaca saat tabel belum
# punya baris untuk jenis itu, mis. sebelum migrasi). Pintunya sendiri bertanya ke tabel. Nilainya = perilaku sebelum
# unit ini (jangkar asal di laporan KP-T4). (`special_order_service.APPROVAL_THRESHOLD` dihapus tanpa pengganti: ia
# tidak pernah menentukan siapa memutus — lihat `default_rows_for("special_order")`.)
BAWAAN_UANG_MUKA = (("Atasan Langsung", ("manager", "admin")),   # dulu cash_advance_service.APPROVAL_STAGES
                    ("Pimpinan", ("admin",)), ("Bagian Keuangan", ("admin",)))
BAWAAN_ANTAR_PT_TANPA_ACC = ("sales_admin",)        # dulu interco_service.SELF_SERVE_BELOW_THRESHOLD (nama persis)
BAWAAN_TAGIHAN_KAMPANYE = ("finance", "manager", "admin")   # dulu marketing_cost_service.BILL_APPROVER_ROLES
async def _value(key: str, ent: str) -> Any:
    from services.config_resolver import value_of
    return await value_of(key, {"entity_id": "" if ent in ("", "all") else ent})


async def _matrix_enforced(ent: str) -> bool:
    """Matriks divisi lama ditegakkan untuk PT ini (mode `enforce`, cakupan semua dokumen)?"""
    mode = str(await _value("approval.matrix_enforcement", ent) or "enforce").strip().lower()
    scope = str(await _value("approval.matrix_scope", ent) or "all_pending").strip().lower()
    return mode in ("enforce", "") and scope in ("all_pending", "")


async def _rules_rows(doc_kind: str, doc_type: str, ent: str, limit_to: Optional[List[str]] = None) -> List[Dict]:
    """`approval_rules` (SO/PO/PR, pemilih KP-T3 `approval_pool`) → baris jenjang 1."""
    from services.config_service import approval_pool
    pool = (await approval_pool(doc_type, None if ent == "all" else ent))["rules"]
    out: List[Dict[str, Any]] = []
    for n, r in enumerate(pool, 1):
        roles, anyh = roles_rank_at_least(r.get("required_role") or "")
        if limit_to is not None and (roles or anyh):
            roles, anyh = [x for x in (roles if not anyh else _registry().role_ids()) if x in limit_to], False
        hi = r.get("max_amount")
        out.append(_row(doc_kind, ent, 1, roles, any_holder=anyh, min_amount=float(r.get("min_amount") or 0),
                        max_amount=(float(hi) if hi is not None else None), sort=n,
                        legacy_role=r.get("required_role") or ""))
    if not out:
        out.append(_row(doc_kind, ent, 1, []))
    return out


async def _extra_level_rows(ent: str) -> List[Dict[str, Any]]:
    """`approval.extra_levels.purchase_order` efektif PT → jenjang 2, 3, … (hanya berlaku bila jenjang 1 berlaku)."""
    from services.config_service import get_effective_settings
    settings = await get_effective_settings(None if ent == "all" else ent)
    extra = (((settings.get("approval") or {}).get("extra_levels") or {}).get("purchase_order") or [])
    out: List[Dict[str, Any]] = []
    for lv in extra if isinstance(extra, list) else []:
        if not isinstance(lv, dict):
            continue
        role = str(lv.get("role") or "").strip()
        if not role:
            continue
        try:
            mn = float(lv.get("min_amount", 0) or 0)
        except (TypeError, ValueError):
            mn = 0.0
        roles, anyh = roles_rank_at_least(role)
        out.append(_row("purchase_order", ent, len(out) + 2, roles, any_holder=anyh, min_amount=mn,
                        label=lv.get("label") or role.title(), legacy_role=role))
    return out


def _only(ent: str, doc_kind: str, roles: List[str], **kw) -> List[Dict[str, Any]]:
    return [_row(doc_kind, ent, 1, roles, **kw)]


async def default_rows_for(doc_kind: str, entity_id: str = "all") -> List[Dict[str, Any]]:
    """Baris bawaan SATU jenis untuk grup (`"all"`) atau satu PT, dari sumber lama dengan nilai efektif PT itu.

    Tabel jangkar: `docs/blueprint/unit/KP-T4.md` "Tabel lengkap" (dicek ulang di laporan unit)."""
    ent = entity_id or "all"
    kind(doc_kind)   # KeyError bila jenis tidak dikenal
    k = doc_kind
    if k == "sales_order.nilai":
        return await _rules_rows(k, "sales_order", ent)
    if k in ("sales_order.kredit", "sales_order.harga_khusus", "sales_order.makloon", "sales_order.validasi",
             "purchase_order.deviasi_harga", "vendor_bill", "landed_cost"):
        return _only(ent, k, roles_rank_at_least("manager")[0])
    if k == "sales_order.bayar_sampel":
        return _only(ent, k, roles_rank_at_least("finance")[0])
    if k == "purchase_order":
        return await _rules_rows(k, "purchase_order", ent) + await _extra_level_rows(ent)
    if k == "purchase_requisition":
        limit = ["manager", "admin"] if await _matrix_enforced(ent) else None
        return await _rules_rows(k, "purchase_requisition", ent, limit_to=limit)
    if k == "special_order":
        enforced = await _matrix_enforced(ent)
        direksi = float(await _value("approval.po_custom_direksi_min", ent) or 0)
        # Cek ulang KP-T4: pesanan khusus yang diajukan SELALU lewat jenjang 1 (matriks lama tanpa ambang tingkat 1);
        # ambang Rp10 jt di kode hanya mengisi field tampilan `requires_approval` yang tidak dibaca layar mana pun.
        return [_row(k, ent, 1, roles_exact(["manager", "admin"]), label="Manager", legacy_role="manager"),
                _row(k, ent, 2, roles_exact(["admin"] if enforced else ["manager", "admin"]),
                     min_amount=max(direksi, 0.0), label="Direksi", legacy_role="admin")]
    if k in ("rnd_spec", "rnd_sample"):
        key = "rnd.spec_approval_roles" if k == "rnd_spec" else "rnd.sample_decision_roles"
        listed = await _value(key, ent) or []
        if isinstance(listed, str):
            listed = [x.strip() for x in listed.split(",") if x.strip()]
        matrix = (["manager", "admin"] if k == "rnd_spec" else ["manager", "md", "admin"]) \
            if await _matrix_enforced(ent) else None
        if matrix is None and not listed:
            return _only(ent, k, [], any_holder=True)
        allowed = set(matrix if matrix is not None else _registry().role_ids())
        if listed:
            allowed &= set(listed)
        return _only(ent, k, roles_exact(allowed))
    if k == "rnd_spec.rilis":
        listed = await _value("rnd.spec_approval_roles", ent) or []
        if isinstance(listed, str):
            listed = [x.strip() for x in listed.split(",") if x.strip()]
        return _only(ent, k, roles_exact(listed)) if listed else _only(ent, k, [], any_holder=True)
    if k == "amendment":
        need = str(await _value("amendment.approver_role", ent) or "manager")
        above = float(await _value("amendment.admin_approval_above", ent) or 0)
        low = _ordered({"admin", *roles_with_base([need])})
        high = _ordered({"admin", *roles_with_base(["admin"])})
        if above > 0:
            return [_row(k, ent, 1, low, max_amount=above, sort=1, legacy_role=need),
                    _row(k, ent, 1, high, min_amount=above, sort=2, legacy_role="admin")]
        return _only(ent, k, low, legacy_role=need)
    if k == "interco":
        th = float(await _value("antar_entitas.approval_threshold_rupiah", ent) or 0)
        hi_role = str(await _value("antar_entitas.high_value_approval_role", ent) or "admin")
        lo_role = str(await _value("antar_entitas.approval_role", ent) or "manager")
        hi_roles, hi_any = roles_rank_at_least(hi_role)
        lo_roles, lo_any = roles_rank_at_least(lo_role)
        if th <= 0:
            return _only(ent, k, hi_roles, any_holder=hi_any)
        lo_roles = lo_roles if lo_any else _ordered({*lo_roles, *roles_exact(BAWAAN_ANTAR_PT_TANPA_ACC)})
        return [_row(k, ent, 1, lo_roles, any_holder=lo_any, max_amount=th, sort=1),
                _row(k, ent, 1, hi_roles, any_holder=hi_any, min_amount=th, sort=2)]
    if k == "interco_loan":
        # dulu `interco_loan_service._approval_gate`: peta peringkat pribadi {manager 1, admin 2, lainnya 0} → nama persis
        th = float(await _value("antar_entitas.approval_threshold_rupiah", ent) or 0)
        hi_role = str(await _value("antar_entitas.high_value_approval_role", ent) or "admin")
        lo_role = str(await _value("antar_entitas.approval_role", ent) or "manager")
        pribadi = {"manager": 1, "admin": 2}

        def _lolos(need: str) -> List[str]:
            return roles_exact([r for r, n in pribadi.items() if n >= pribadi.get(need, 1)])
        if th > 0:
            return [_row(k, ent, 1, _lolos(lo_role), max_amount=th, sort=1, legacy_role=lo_role),
                    _row(k, ent, 1, _lolos(hi_role), min_amount=th, sort=2, legacy_role=hi_role)]
        return _only(ent, k, _lolos(lo_role), legacy_role=lo_role)
    if k == "contra_bon_approve":
        th = float(await _value("contra_bon.approval_threshold_rupiah", ent) or 0)
        lo_role = str(await _value("contra_bon.approval_role", ent) or "manager").lower()
        hi_role = str(await _value("contra_bon.high_value_approval_role", ent) or "admin").lower()
        lo_roles, lo_any = roles_rank_at_least(lo_role, unknown_as_manager=False)
        hi_roles, hi_any = roles_rank_at_least(hi_role, unknown_as_manager=False)
        if th > 0:
            return [_row(k, ent, 1, lo_roles, any_holder=lo_any, max_amount=th, sort=1),
                    _row(k, ent, 1, hi_roles, any_holder=hi_any, min_amount=th, sort=2)]
        return _only(ent, k, lo_roles, any_holder=lo_any)
    if k == "vendor_bill.kampanye":
        return _only(ent, k, _ordered({"admin", *roles_with_base(BAWAAN_TAGIHAN_KAMPANYE)}))
    if k == "cash_advance":
        return [_row(k, ent, n, _ordered({"admin", *roles_with_base(roles)}), label=label)
                for n, (label, roles) in enumerate(BAWAAN_UANG_MUKA, 1)]
    if k == "makloon_claim":
        from services import contract_service as cs
        roles = (await cs.get_settings()).get("claim_approval_roles", ["manager", "admin"])
        return _only(ent, k, roles_exact(roles or []))
    if k == "payment_variance.hapus_sisa":
        need = str(await _value("payment.variance_writeoff_approver_role", ent) or "manager").lower()
        return _only(ent, k, roles_with_base([need, "admin"]), legacy_role=need)
    # Mekanisme G (izin saja) — termasuk lewat-batas kredit sesudah PR-T2: siapa pun pemegang izinnya.
    return _only(ent, k, [], any_holder=True)


async def build_default_rows(entity_id: str = "all") -> List[Dict[str, Any]]:
    """Baris bawaan SEMUA jenis untuk grup atau satu PT (dipakai migrasi dan uji setara)."""
    out: List[Dict[str, Any]] = []
    for k in APPROVAL_KINDS:
        out.extend(await default_rows_for(k, entity_id))
    return out


# ── Membaca tabel ──────────────────────────────────────────────────────────────────────────────────────────────────
def _sort_key(r: Dict[str, Any]) -> tuple:
    return (int(r.get("level") or 1), int(r.get("sort") or 0), _bounds(r)[0])


async def rows_for(doc_kind: str, entity_id: Optional[str]) -> Dict[str, Any]:
    """Baris yang BERLAKU untuk (jenis, PT): `{source, rows, group_rows}` (urut jenjang, `sort`, batas bawah)."""
    kind(doc_kind)
    ent = entity_id if entity_id and entity_id != "all" else "all"
    found = await db[COLL].find({"doc_kind": doc_kind, "active": True,
                                 "entity_id": {"$in": list({ent, "all"})}}, {"_id": 0}).to_list(500)
    pt = sorted([r for r in found if r.get("entity_id") == ent and ent != "all"], key=_sort_key)
    grp = sorted([r for r in found if r.get("entity_id") == "all"], key=_sort_key)
    if pt:
        return {"source": "pt", "rows": pt, "group_rows": grp}
    if grp:
        return {"source": "grup", "rows": grp, "group_rows": grp}
    return {"source": "bawaan", "rows": sorted(await default_rows_for(doc_kind, ent), key=_sort_key),
            "group_rows": []}


def _tier(rows: List[Dict[str, Any]], level: int, amount: float) -> Optional[Dict[str, Any]]:
    for r in rows:
        if int(r.get("level") or 1) == int(level) and _contains(r, amount):
            return r
    return None


def _levels(rows: List[Dict[str, Any]]) -> List[int]:
    return sorted({int(r.get("level") or 1) for r in rows})


def _amt(doc_kind: str, amount: Any) -> float:
    if not has_amount(doc_kind):
        return 0.0
    try:
        v = float(amount or 0)
    except (TypeError, ValueError):
        return 0.0
    return v if math.isfinite(v) else 0.0


def _level_label(doc_kind: str, row: Optional[Dict[str, Any]], level: int) -> str:
    return (row or {}).get("label") or kind(doc_kind)["level_labels"].get(level) or "Persetujuan"


def levels_from_rows(doc_kind: str, rows: List[Dict[str, Any]], amount: float,
                     require_level1: bool = True) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for lv in _levels(rows):
        t = _tier(rows, lv, amount)
        if not _needs(t):
            if lv == 1 and require_level1:
                return []   # jenjang di atas 1 hanya berlaku bila jenjang 1 berlaku (aturan mesin lama)
            continue
        out.append({"level": lv, "label": _level_label(doc_kind, t, lv), "rule_id": t.get("id") or "",
                    "roles": list(t.get("roles") or []), "any_holder": bool(t.get("any_holder")),
                    "legacy_role": t.get("legacy_role") or ""})
    return out


def compat_role(level: Dict[str, Any]) -> str:
    """Nilai field kompatibel `required_role` (tampilan/notifikasi lama) untuk satu jenjang — BUKAN untuk memutus."""
    if not level:
        return ""
    return level.get("legacy_role") or (list(level.get("roles") or [""])[0] if level.get("roles") else "")


async def required_levels(doc_kind: str, entity_id: Optional[str], amount: float = 0.0,
                          require_level1: bool = True) -> List[Dict[str, Any]]:
    """Jenjang yang wajib untuk nilai itu: `[{level, label, rule_id, roles, any_holder}]`; kosong = tanpa persetujuan.
    `require_level1=False` hanya untuk rantai PO yang jenjang 1-nya dipaksa (penyimpangan harga / lewat kontrak)."""
    src = await rows_for(doc_kind, entity_id)
    return levels_from_rows(doc_kind, src["rows"], _amt(doc_kind, amount), require_level1)


def _decider_row(doc_kind: str, rows: List[Dict[str, Any]], level: int, amount: float) -> Tuple[Optional[Dict], str]:
    """Rentang yang menentukan siapa memutus pada jenjang itu → (baris, keadaan).

    keadaan: `rentang` (rentang memuat nilai) · `terendah` (nilai tidak butuh persetujuan pada jenjang ini, pintu tetap
    dijaga penyetuju rentang terendah jenjang itu — persetujuan lebih awal, mis. PR draf) · `bebas` (jenis ini tidak
    punya penyetuju sama sekali) · `kosong` (jenjang ini tidak punya penyetuju)."""
    t = _tier(rows, level, amount)
    if _needs(t):
        return t, "rentang"
    lv_rows = sorted([r for r in rows if int(r.get("level") or 1) == int(level) and _needs(r)],
                     key=lambda r: _bounds(r)[0])
    if lv_rows:
        return lv_rows[0], "terendah"
    if not any(_needs(r) for r in rows):
        return None, "bebas"
    return None, "kosong"


async def _module_label(resource: str) -> str:
    from access_modules import MODULE_CATALOG
    for m in MODULE_CATALOG:
        if resource in m["resources"]:
            return m["label"]
    return resource


def _labels(roles: List[str]) -> List[str]:
    return [role_label(r) for r in roles]


def _join(labels: List[str]) -> str:
    if not labels:
        return "—"
    return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " atau " + labels[-1]


async def _holds(actor: Dict[str, Any], pairs: List[Tuple[str, str]]) -> bool:
    from dependencies import has_permission
    for res, act in pairs:
        if await has_permission(actor or {}, res, act):
            return True
    return False


async def can_decide(doc_kind: str, entity_id: Optional[str], amount: float, actor: Dict[str, Any],
                     level: int = 1, *, action: str = "approve", check_permission: bool = True,
                     snapshot_roles: Optional[List[str]] = None) -> Dict[str, Any]:
    """`{allowed, code, message, who}`. Boleh bila aktor memegang salah satu izin jenis itu **dan** (`any_holder` atau
    perannya ∈ `roles` baris yang memuat nilai itu). Tidak membaca peringkat maupun peran acuan.

    `check_permission=False` hanya untuk pintu yang sengaja menilai batas peran tanpa izin setujui (mis. lepas
    transaksi antar-PT saat dibuat). `snapshot_roles` = potret `roles` jenjang tersimpan di dokumen (D3), dipakai bila
    jenjang itu kini tidak punya penyetuju."""
    k = kind(doc_kind)
    amt = _amt(doc_kind, amount)
    pairs = perm_pairs(doc_kind, action)
    label = k["label"]
    if check_permission and not await _holds(actor, pairs):
        mod = await _module_label(pairs[0][0])
        return {"allowed": False, "code": "izin", "who": [],
                "message": (f"Anda belum punya akses untuk menyetujui {label}. "
                            f"Minta Admin menambahkan akses '{mod}'.")}
    src = await rows_for(doc_kind, entity_id)
    row, state = _decider_row(doc_kind, src["rows"], int(level or 1), amt)
    if state == "bebas":
        return {"allowed": True, "code": "", "message": "", "who": [], "rule_id": ""}
    if row is None:
        roles = list(snapshot_roles or [])
        if not roles:
            return {"allowed": False, "code": "batas", "who": [], "rule_id": "",
                    "message": (f"{label} pada jenjang {int(level or 1)} belum punya penyetuju. "
                                "Minta Admin mengatur Aturan Persetujuan.")}
        row = {"roles": roles, "any_holder": False, "id": ""}
    who = ["Semua pemegang akses"] if row.get("any_holder") else _labels(list(row.get("roles") or []))
    role = str((actor or {}).get("role") or "")
    if row.get("any_holder") or role in (row.get("roles") or []):
        return {"allowed": True, "code": "", "message": "", "who": who, "rule_id": row.get("id") or ""}
    senilai = f" senilai {rp(amt)}" if has_amount(doc_kind) else ""
    return {"allowed": False, "code": "batas", "who": who, "rule_id": row.get("id") or "",
            "message": (f"{label}{senilai} pada jenjang {int(level or 1)} diputus oleh {_join(who)}. "
                        "Peran Anda belum tercantum di Aturan Persetujuan.")}


async def assert_can_decide(doc_kind: str, entity_id: Optional[str], amount: float, actor: Dict[str, Any],
                            level: int = 1, **kw) -> Dict[str, Any]:
    """Sama dengan `can_decide`, melempar 403 berpesan manusia (tanpa id peran, tanpa `x.y`)."""
    res = await can_decide(doc_kind, entity_id, amount, actor, level, **kw)
    if not res["allowed"]:
        raise HTTPException(status_code=403, detail=res["message"])
    return res


async def who_can_decide(doc_kind: str, entity_id: Optional[str], amount: float, level: int = 1) -> List[str]:
    """Label peran yang lolos pada (jenis, PT, nilai, jenjang) — untuk layar dan pesan."""
    src = await rows_for(doc_kind, entity_id)
    row, state = _decider_row(doc_kind, src["rows"], int(level or 1), _amt(doc_kind, amount))
    if state == "bebas" or (row and row.get("any_holder")):
        return ["Semua pemegang akses"]
    return _labels(list((row or {}).get("roles") or []))


async def roles_allowed(doc_kind: str, entity_id: Optional[str], amount: float = 0.0, level: int = 1) -> List[str]:
    """Id peran yang tercantum (untuk tujuan notifikasi lama ber-peran); `any_holder` → daftar kosong."""
    src = await rows_for(doc_kind, entity_id)
    row, _state = _decider_row(doc_kind, src["rows"], int(level or 1), _amt(doc_kind, amount))
    return [] if not row or row.get("any_holder") else list(row.get("roles") or [])


# ── Tampilan layar ─────────────────────────────────────────────────────────────────────────────────────────────────
async def _role_permission_index(pairs: List[Tuple[str, str]]) -> Dict[str, bool]:
    from dependencies import permission_matrix
    matrix = await permission_matrix()
    out: Dict[str, bool] = {}
    for rid in _registry().role_ids():
        perms = matrix.get(rid, {}) or {}
        out[rid] = any(a in (perms.get(r) or []) or "*" in (perms.get(r) or []) for r, a in pairs)
    return out


async def kinds_catalog() -> List[Dict[str, Any]]:
    out = []
    for k, v in APPROVAL_KINDS.items():
        labels = []
        for res, act in perm_pairs(k):
            labels.append(await _module_label(res))
        out.append({"doc_kind": k, "label": v["label"], "group": v["group"], "queue_key": v["queue_key"],
                    "has_amount": has_amount(k), "permission_labels": sorted(set(labels)),
                    "level_labels": {str(a): b for a, b in v["level_labels"].items()}, "note": v["note"]})
    order = {g: i for i, g in enumerate(GROUPS)}
    return sorted(out, key=lambda x: order.get(x["group"], 99))


def _segments(rows: List[Dict[str, Any]]) -> List[Tuple[float, float, Dict[str, Any]]]:
    return [(*_bounds(r), r) for r in rows]


def warnings_for(doc_kind: str, source: str, rows: List[Dict[str, Any]], group_rows: List[Dict[str, Any]],
                 holders: Dict[str, bool], module: str) -> List[Dict[str, Any]]:
    """Peringatan (tidak menolak simpan): celah, tumpang-tindih, lebih longgar dari grup, peran tanpa izin."""
    out: List[Dict[str, Any]] = []
    amount_kind = has_amount(doc_kind)
    for lv in _levels(rows):
        lv_rows = sorted([r for r in rows if int(r.get("level") or 1) == lv], key=lambda r: _bounds(r)[0])
        if amount_kind and lv == 1 and lv_rows:
            cur = 0.0
            for lo, hi, _r in _segments(lv_rows):
                if lo > cur + 1e-9:
                    out.append({"code": "celah", "level": lv,
                                "message": (f"Jenjang {lv}: nilai {rp(cur)} s/d di bawah {rp(lo)} tidak tercakup — "
                                            "dokumen di rentang itu tidak butuh persetujuan.")})
                cur = max(cur, hi)
        for i, a in enumerate(lv_rows):
            for b in lv_rows[i + 1:]:
                lo = max(_bounds(a)[0], _bounds(b)[0])
                hi = min(_bounds(a)[1], _bounds(b)[1])
                if lo < hi:
                    rng = f"{rp(lo)} ke atas" if hi == _INF else f"{rp(lo)} s/d di bawah {rp(hi)}"
                    out.append({"code": "tumpang_tindih", "level": lv,
                                "message": (f"Jenjang {lv}: rentang {rng} tercantum dua kali — "
                                            "yang dipakai baris pertama.")})
        named = sorted({x for r in lv_rows for x in (r.get("roles") or [])})
        if named and not any(r.get("any_holder") for r in lv_rows) and not any(holders.get(x) for x in named):
            out.append({"code": "tanpa_izin", "level": lv,
                        "message": f"Tidak ada peran pada jenjang {lv} yang memegang izin {module}."})
    if source == "pt" and group_rows:
        pts = sorted({_bounds(r)[0] for r in rows + group_rows} | {0.0})
        for lv in _levels(rows):
            for p in pts:
                mine = _tier(rows, lv, p)
                grp = _tier(group_rows, lv, p)
                if not _needs(grp):
                    continue
                extra = (not _needs(mine)) or (bool(mine.get("any_holder")) and not grp.get("any_holder")) or \
                    (not mine.get("any_holder") and not grp.get("any_holder")
                     and set(mine.get("roles") or []) - set(grp.get("roles") or []))
                if extra:
                    out.append({"code": "lebih_longgar_dari_grup", "level": lv,
                                "message": (f"Jenjang {lv} mulai {rp(p)}: aturan PT ini lebih longgar dari aturan grup "
                                            "(ada peran atau nilai yang di grup tidak diizinkan).")})
                    break
    return out


async def policy_view(doc_kind: str, entity_id: Optional[str]) -> Dict[str, Any]:
    """Bentuk jawaban `GET /api/approval-policies` untuk satu jenis."""
    k = kind(doc_kind)
    src = await rows_for(doc_kind, entity_id)
    pairs = perm_pairs(doc_kind)
    holders = await _role_permission_index(pairs)
    module = await _module_label(pairs[0][0])
    levels: List[Dict[str, Any]] = []
    for lv in _levels(src["rows"]):
        tiers = []
        for r in [x for x in src["rows"] if int(x.get("level") or 1) == lv]:
            roles = list(r.get("roles") or [])
            tiers.append({"id": r.get("id") or "", "min_amount": _num(r.get("min_amount") or 0),
                          "max_amount": _num(r.get("max_amount")), "roles": roles, "role_labels": _labels(roles),
                          "any_holder": bool(r.get("any_holder")),
                          "passing_labels": (["Semua pemegang akses"] if r.get("any_holder")
                                             else [role_label(x) for x in roles if holders.get(x)]),
                          "no_permission_labels": [] if r.get("any_holder")
                          else [role_label(x) for x in roles if not holders.get(x)],
                          "source": r.get("source") or "bawaan"})
        first = next((x for x in src["rows"] if int(x.get("level") or 1) == lv), None)
        levels.append({"level": lv, "label": _level_label(doc_kind, first, lv), "tiers": tiers})
    unused = []
    if src["source"] == "pt":
        unused = [{"id": r.get("id"), "level": r.get("level"), "min_amount": _num(r.get("min_amount") or 0),
                   "max_amount": _num(r.get("max_amount")), "role_labels": _labels(list(r.get("roles") or [])),
                   "any_holder": bool(r.get("any_holder"))} for r in src["group_rows"]]
    version = max([int(r.get("version") or 0) for r in src["rows"]] or [0]) if src["source"] != "bawaan" else 0
    return {"doc_kind": doc_kind, "label": k["label"], "group": k["group"], "has_amount": has_amount(doc_kind),
            "permission_label": module, "source": src["source"], "levels": levels, "unused_group_rows": unused,
            "warnings": warnings_for(doc_kind, src["source"], src["rows"], src["group_rows"], holders, module),
            "version": version, "note": k["note"]}


async def check_view(doc_kind: str, entity_id: Optional[str], amount: float) -> Dict[str, Any]:
    """Coba nilai: jenjang yang berlaku dan siapa yang lolos (peran tercantum DAN memegang izinnya)."""
    src = await rows_for(doc_kind, entity_id)
    amt = _amt(doc_kind, amount)
    holders = await _role_permission_index(perm_pairs(doc_kind))
    out = []
    for lv in levels_from_rows(doc_kind, src["rows"], amt):
        who = (["Semua pemegang akses"] if lv["any_holder"]
               else [role_label(x) for x in lv["roles"] if holders.get(x)])
        out.append({"level": lv["level"], "label": lv["label"], "who": who})
    return {"doc_kind": doc_kind, "amount": _num(amt), "source": src["source"], "levels": out}


# ── Mengubah tabel (layar Aturan Persetujuan) ──────────────────────────────────────────────────────────────────────
def _bad(msg: str, code: int = 400) -> HTTPException:
    return HTTPException(status_code=code, detail=msg)


def _parse_levels(doc_kind: str, levels: Any) -> List[Dict[str, Any]]:
    """Isi `PUT` → baris tervalidasi (tanpa id). Melempar 400 berpesan manusia."""
    reg = _registry()
    amount_kind = has_amount(doc_kind)
    k = kind(doc_kind)
    maks = int(k.get("max_levels") or 0)   # R26 — jenis berpenyetuju tunggal (mis. pembatalan pesanan)
    if not isinstance(levels, list):
        raise _bad("Isi jenjang tidak sah.")
    out: List[Dict[str, Any]] = []
    for n, lv in enumerate(levels, 1):
        if not isinstance(lv, dict):
            raise _bad("Isi jenjang tidak sah.")
        level = int(lv.get("level") or n)
        if level < 1:
            raise _bad("Nomor jenjang harus 1 atau lebih.")
        if maks and level > maks:
            raise _bad(k.get("max_levels_message") or f"{k['label']} paling banyak {maks} jenjang persetujuan.")
        label = str(lv.get("label") or "").strip()[:60]
        tiers = lv.get("tiers") or []
        if not isinstance(tiers, list) or not tiers:
            raise _bad(f"Jenjang {level} belum punya rentang.")
        for i, t in enumerate(tiers, 1):
            if not isinstance(t, dict):
                raise _bad("Isi jenjang tidak sah.")
            try:
                lo = float(t.get("min_amount") or 0)
                hi_raw = t.get("max_amount")
                hi = None if hi_raw in (None, "") else float(hi_raw)
            except (TypeError, ValueError):
                raise _bad(f"Rentang jenjang {level} tidak sah: batas harus angka.")
            if not math.isfinite(lo) or lo < 0 or (hi is not None and not math.isfinite(hi)):
                raise _bad(f"Rentang jenjang {level} tidak sah: batas harus angka 0 atau lebih.")
            if not amount_kind and (lo != 0 or hi is not None):
                raise _bad("Jenis dokumen ini tidak memakai nominal.")
            if hi is not None and hi <= lo:
                raise _bad(f"Rentang jenjang {level} tidak sah: batas atas harus lebih besar dari batas bawah.")
            any_holder = bool(t.get("any_holder"))
            roles: List[str] = []
            for rid in ([] if any_holder else (t.get("roles") or [])):
                rid = str(rid or "").strip()
                if not reg.is_role(rid):
                    raise _bad(f"Peran “{rid}” tidak ada.")
                if rid not in roles:
                    roles.append(rid)
            out.append(_row(doc_kind, "all", level, _ordered(roles), any_holder=any_holder, min_amount=lo,
                            max_amount=hi, label=label, sort=i, setara=False))
    return out


async def _layer_rows(doc_kind: str, ent: str) -> List[Dict[str, Any]]:
    return await db[COLL].find({"doc_kind": doc_kind, "entity_id": ent, "active": True},
                               {"_id": 0}).to_list(500)


async def replace_rows(doc_kind: str, entity_id: str, levels: Any, *, expected_version: Optional[int],
                       reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Mengganti SELURUH baris (jenis, lapisan) sekaligus. `entity_id = "all"` = grup. Jawaban seperti `policy_view`.

    Versi = angka `version` baris aktif lapisan itu (0 bila belum ada baris tersimpan, termasuk saat masih memakai
    aturan bawaan). `expected_version` basi → 409. Baris lama dinonaktifkan (jejak tetap ada), tidak dihapus."""
    kind(doc_kind)
    if not (reason or "").strip():
        raise _bad("Alasan perubahan wajib diisi.")
    ent = entity_id or "all"
    rows = _parse_levels(doc_kind, levels)
    cur = await _layer_rows(doc_kind, ent)
    version = max([int(r.get("version") or 0) for r in cur] or [0])
    if expected_version is not None and int(expected_version) != version:
        raise _bad("Aturan ini sudah diubah orang lain. Muat ulang.", 409)
    now = now_iso()
    who = (actor or {}).get("name", "")
    if cur:
        res = await db[COLL].update_many(
            {"doc_kind": doc_kind, "entity_id": ent, "active": True, "version": version},
            {"$set": {"active": False, "replaced_at": now, "replaced_by": who, "updated_at": now}})
        if res.modified_count != len(cur):
            raise _bad("Aturan ini sudah diubah orang lain. Muat ulang.", 409)
    lama = {(int(r.get("level") or 1), float(r.get("min_amount") or 0)): r.get("legacy_role") or "" for r in cur}
    docs = []
    for r in rows:
        key = (r["level"], float(r["min_amount"] or 0))
        legacy = lama.get(key) or (r["roles"][0] if r["roles"] else "")
        docs.append({**r, "id": new_id("appol"), "entity_id": ent, "source": "pengguna", "version": version + 1,
                     "legacy_role": legacy, "reason": reason.strip()[:400], "created_at": now, "created_by": who,
                     "updated_at": now, "updated_by": who})
    if docs:
        await db[COLL].insert_many([dict(d) for d in docs])
    try:
        from dependencies import audit
        await audit(who, "approval_policy_replaced", COLL, f"{doc_kind}:{ent}",
                    {"doc_kind": doc_kind, "entity_id": ent, "version": version + 1, "rows": len(docs)},
                    reason=reason.strip()[:400])
    except Exception:  # noqa: BLE001 — jejak tambahan; baris sudah tersimpan
        pass
    return await policy_view(doc_kind, ent)


async def delete_pt_rows(doc_kind: str, entity_id: str, *, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Menghapus baris khusus PT (kembali ke aturan grup). Baris lama dinonaktifkan, tidak dihapus."""
    kind(doc_kind)
    if not (reason or "").strip():
        raise _bad("Alasan perubahan wajib diisi.")
    if not entity_id or entity_id == "all":
        raise _bad("Pilih PT yang aturan khususnya akan dihapus.")
    now = now_iso()
    who = (actor or {}).get("name", "")
    await db[COLL].update_many({"doc_kind": doc_kind, "entity_id": entity_id, "active": True},
                               {"$set": {"active": False, "replaced_at": now, "replaced_by": who,
                                         "replaced_reason": reason.strip()[:400], "updated_at": now}})
    try:
        from dependencies import audit
        await audit(who, "approval_policy_reset_to_group", COLL, f"{doc_kind}:{entity_id}",
                    {"doc_kind": doc_kind, "entity_id": entity_id}, reason=reason.strip()[:400])
    except Exception:  # noqa: BLE001
        pass
    return await policy_view(doc_kind, entity_id)


# ── Pembantu pintu ─────────────────────────────────────────────────────────────────────────────────────────────────
#: `doc_type` lama mesin `approval_rules` → jenis dokumen kebijakan (dipakai pembungkus `config_service`).
DOC_TYPE_KIND = {"sales_order": "sales_order.nilai", "purchase_order": "purchase_order",
                 "purchase_requisition": "purchase_requisition"}


async def chain_for(doc_kind: str, entity_id: Optional[str], amount: float,
                    force_kind: str = "") -> List[Dict[str, Any]]:
    """Rantai jenjang yang disimpan dokumen baru (potret `roles` + id baris, D3). `force_kind`: bila jenis utama tidak
    menuntut persetujuan pada nilai itu, jenjang 1 diambil dari jenis paksa (mis. penyimpangan harga PO) dan jenjang
    berikutnya dari jenis utama yang memuat nilai itu (perilaku `build_approval_chain` lama)."""
    levels = await required_levels(doc_kind, entity_id, amount)
    kinds = {lv["level"]: doc_kind for lv in levels}
    if not levels and force_kind:
        first = (await required_levels(force_kind, entity_id, amount))[:1]
        rest = [lv for lv in await required_levels(doc_kind, entity_id, amount, require_level1=False)
                if lv["level"] >= 2]
        levels = first + rest
        kinds = {lv["level"]: (force_kind if lv in first else doc_kind) for lv in levels}
    return [{"level": lv["level"], "required_role": compat_role(lv), "label": lv["label"],
             "roles": list(lv["roles"]), "any_holder": bool(lv["any_holder"]), "rule_id": lv["rule_id"],
             "policy_kind": kinds[lv["level"]], "status": "pending", "approved_by": "", "approved_by_id": "",
             "approved_at": ""} for lv in levels]


async def lowest_threshold(doc_kind: str, entity_id: Optional[str]) -> float:
    """Batas bawah rentang jenjang 1 terendah yang butuh persetujuan (tampilan "butuh persetujuan mulai …")."""
    rows = (await rows_for(doc_kind, entity_id))["rows"]
    mins = sorted(_bounds(r)[0] for r in rows if int(r.get("level") or 1) == 1 and _needs(r))
    return mins[0] if mins else 0.0


async def guard_door(doc_kind: str, actor: Dict[str, Any], *, doc: Optional[Dict[str, Any]] = None,
                     collection: str = "", doc_id: str = "", amount: float = 0.0, action: str = "approve") -> None:
    """Pintu bermekanisme "izin saja" (G): sesudah izin & dokumen diperiksa router, tanyakan Aturan Persetujuan
    (bawaan: semua pemegang izin → tidak ada keputusan yang berubah; bila Admin membatasi peran di tabel, pintu ini
    ikut). PT = PT dokumen (`doc` atau dibaca dari `collection` + `doc_id`)."""
    ent = (doc or {}).get("entity_id")
    if doc is None and collection and doc_id:
        d = await db[collection].find_one({"id": doc_id}, {"_id": 0, "entity_id": 1})
        ent = (d or {}).get("entity_id")
    await assert_can_decide(doc_kind, ent or None, amount, actor, action=action, check_permission=False)
