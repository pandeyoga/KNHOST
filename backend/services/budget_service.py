"""R6.3 — Budget Control penuh: Anggaran vs Komitmen vs Realisasi + enforcement.

Koleksi:
- `budgets` (prefix `budget_`) — anggaran per (entity_id, year, month, dimension, key).
  * `dimension` = "account" (kode akun COA) | "category" (kode kategori beban).
  * `month` 0 = anggaran TAHUNAN; 1..12 = anggaran BULANAN.
  * `key` = account_code | expense category code. `account_code` dipertahankan (legacy/back-compat).
  * PK-39 (FY-12, D7) — unik per (entity_id, year, month, dimension, key): indeks wajib `uq_budget_key`.
- `budget_history` (prefix `bgh_`) — PK-39: satu baris tiap buat/ubah/hapus pagu (sebelum · sesudah · alasan · oleh).
- `fin_budget_rules` (prefix `bgrule_`) — sakelar anggaran per ENTITAS:
  * `warn_threshold_pct` — ambang peringatan dini (default 85%)
  * `unbudgeted_action` = "allow" | "warn" | "block" (bila belum ada anggaran utk key tsb)
  * `enforce_po_create` / `enforce_po_approve` — dua titik PO.
  * PK-39 (K-12) — field `mode` TIDAK dibaca lagi: mode = pengaturan `budget.mode` (Pusat Pengaturan, global → PT).
    Nilai `mode` lama PT itu dipakai sampai lapisan PT kunci baru diisi (penimpa `mode_anggaran_lama`,
    `services/config_overrides.py`) — tanpa penulisan data saat pemasangan.

Sumber angka (semua diturunkan / derived — TIDAK ada materialized cache, GL-safe). PK-39 (FY-10, FY-11):
- **Realisasi (actual)** — bulan = bulan buku WIB tanggal jurnal (`book_date.periode_buku`, PK-37).
  * dimension=account → `journal_entries` (non-void, exclude closing) per akun & bulan:
    pendapatan = kredit − debit; beban = debit − kredit; ASET = Σ debit penerimaan barang (`goods_receipt`) − Σ kredit
    retur beli (`purchase_return`) — HPP, opname, transfer, dll. diabaikan (belanja tidak berkurang karena terjual).
  * dimension=category → jurnal LPJ (`petty_cash_settlement`) tahun itu; `category_totals` LPJ (`source_id`) dijumlah
    pada bulan JURNAL (bukan teks `periode` LPJ).
- **Komitmen (committed)**
  * PO terbuka (status di luar `CLOSED_PO_STATUSES`, termasuk `partial`) → key dari `budget_dimension`/`budget_key`
    PO (bila di-tag) atau akun persediaan hasil pemetaan `persediaan.persediaan`; nilai = SISA PO (`po_open_value`).
  * LPJ petty cash (`cash_advance_settlements` status draft/submitted) → per kategori, bulan `created_at` (WIB).
- Laporan dihitung PER PT pemilik pagu (mode gabungan = penjumlahan, belum dieliminasi).

Pemeriksaan: `enforce_budget()` (titik `po_create`, `po_approve`, `bill_approve`, `cash_out`, `lpj_submit`,
`lpj_approve`; `enforce_po_budget` = pembungkus PO). Mode `block` + melampaui → ValueError("Anggaran terlampaui: …")
(router → 400; PO setujui tetap 409); `warn` → daftar peringatan; `off` → lewati. `lpj_submit`: tolak = peringatan.
"""
from typing import Any, Dict, Iterable, List, Optional, Tuple

from db import db
from core_utils import now_iso, new_id, rupiah
from services import financial_statement_service as fs
from services.book_date import periode_buku, tanggal_buku

EPS = 0.005

DIM_ACCOUNT = "account"
DIM_CATEGORY = "category"
DIMENSIONS = (DIM_ACCOUNT, DIM_CATEGORY)

RULES_COLL = "fin_budget_rules"
HISTORY_COLL = "budget_history"
# PK-39 — PO terbuka = semua status KECUALI status akhir ini (sama dengan `routers/purchase_orders.TERMINAL_PO_STATUSES`;
# uji `test_PK39_angka.py` menjaga keduanya tetap sama). Dulu daftar status terbuka yang memuat `receiving` (dihitung
# dua kali dengan penerimaannya) tetapi tidak memuat `partial` (sisa PO hilang dari komitmen).
CLOSED_PO_STATUSES = ("cancelled", "rejected", "closed_short", "completed")
OPEN_STL_STATUSES = ["draft", "submitted"]     # LPJ belum diposting → komitmen
GR_SOURCE, PRET_SOURCE, STL_SOURCE = "goods_receipt", "purchase_return", "petty_cash_settlement"

DEFAULT_RULES = {
    "warn_threshold_pct": 85.0,
    "unbudgeted_action": "allow",
    "enforce_po_create": True,
    "enforce_po_approve": True,
}
VALID_UNBUDGETED = ("allow", "warn", "block")
# PK-39 — nilai pengaturan `budget.mode` ↔ kode mode lama (jawaban API & layar lama tetap terbaca).
MODE_FROM_SETTING = {"mati": "off", "peringatan": "warn", "blokir": "block"}
SETTING_FROM_MODE = {v: k for k, v in MODE_FROM_SETTING.items()}
PO_POINTS = {"po_create": "enforce_po_create", "po_approve": "enforce_po_approve"}
SOFT_POINTS = ("lpj_submit",)   # mode tolak = peringatan (pengaju tidak dihalangi; yang ditahan persetujuannya)
COMBINED_NOTE = "Penjumlahan pagu dan realisasi tiap PT; transaksi antar-PT belum dieliminasi."
DUPLICATE_MSG = "Pagu untuk PT, tahun, bulan, dan akun/kategori ini sudah ada. Ubah pagu yang ada."
HISTORY_FIELDS = ("amount", "year", "month", "note")


class DuplicateBudget(ValueError):
    """Pagu kembar (PT, tahun, bulan, dimensi, kunci) — router → 409."""


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


def _month_of(date_str: str) -> int:
    try:
        return int(str(date_str or "")[5:7] or 0)
    except (ValueError, TypeError):
        return 0


def _year_of(date_str: str) -> int:
    try:
        return int(str(date_str or "")[:4] or 0)
    except (ValueError, TypeError):
        return 0


def _periode(value: Any) -> Tuple[int, int]:
    """PK-39 (D6) — (tahun, bulan) buku WIB sebuah tanggal/stempel waktu. Kosong → (0, 0) (bukan "hari ini");
    teks yang tidak dikenali `periode_buku` → potongan `YYYY-MM` apa adanya (tahun 0 bila bukan angka)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return 0, 0
    try:
        p = periode_buku(value)
        return int(p[:4]), int(p[5:7])
    except ValueError:
        return _year_of(str(value)), _month_of(str(value))


def _tanggal(value: Any = None) -> str:
    """Tanggal buku WIB `YYYY-MM-DD` untuk pemeriksaan (kosong → hari ini)."""
    try:
        return tanggal_buku(value or None)
    except ValueError:
        return str(value or "")[:10] or tanggal_buku()


def _is_reversed(je: Dict[str, Any]) -> bool:
    """Jurnal yang sudah dibalik (PK-10 — penanda acuan / warisan) tidak dihitung sebagai belanja aset maupun LPJ."""
    rb = je.get("reversed_by_entry_id")
    return bool(je.get("reversed") is True or (rb and rb != "pending"))


async def _accounts_map() -> Dict[str, Dict[str, Any]]:
    return await fs._accounts_map()


async def _category_map(entity_id: str = "") -> Dict[str, Dict[str, Any]]:
    """Kategori biaya EFEKTIF untuk satu badan usaha (override → global).

    FASE E-4 (E4.3): satu kode kategori boleh dipetakan ke akun buku besar yang
    berbeda per badan usaha, jadi peta ini tidak boleh lagi dibaca tanpa lapisan.
    """
    from services import entity_master_service as ems
    rows = await ems.effective_rows("expense-categories", entity_id)
    return {r.get("code", ""): r for r in rows}


async def inventory_account(entity_id: str = "") -> str:
    """PK-39 (P9) — akun belanja persediaan bawaan PO yang tidak ditandai: pemetaan `persediaan.persediaan` PT itu
    (dulu konstanta `1-1300`)."""
    from services import gl_service as gl
    return await gl.account_for("persediaan.persediaan", entity_id or None)


async def _is_expense(code: str, entity_id: str = "") -> bool:
    from services import gl_service as gl
    acc = (await gl.effective_accounts([code], entity_id or None)).get(code) or {}
    return acc.get("type") == "expense"


# ═══ Aturan (rules) per entitas ══════════════════════════════════════════════
def _mode_option_label(value: str) -> str:
    import config_registry as registry
    for o in registry.require("budget.mode").get("options") or []:
        if isinstance(o, dict) and o.get("value") == value:
            return o.get("label") or value
    return value


def mode_moved_message() -> str:
    """Pesan 400 untuk `PUT /finance/budget-rules` yang masih mengirim `mode` (letak kunci dibaca dari registry)."""
    import config_registry as registry
    e = registry.require("budget.mode")
    grp = next((g for g in registry.GROUPS if g["id"] == e["group"]), {})
    sec = (registry.SECTION_IDS.get(e["group"], {}).get(e["section"]) or {}).get("label", "")
    letak = " › ".join(x for x in ("Pusat Pengaturan", grp.get("label", ""), sec) if x)
    return f"Mode anggaran sekarang diatur di {letak}."


async def get_rules(entity_id: str) -> Dict[str, Any]:
    from services.config_resolver import resolve
    import config_registry as registry
    doc = await db[RULES_COLL].find_one({"entity_id": entity_id}, {"_id": 0})
    out: Dict[str, Any] = {"entity_id": entity_id, **DEFAULT_RULES, "is_default": doc is None}
    if doc:
        for k in DEFAULT_RULES:
            if doc.get(k) is not None:
                out[k] = doc[k]
        out["updated_at"] = doc.get("updated_at", "")
        out["updated_by"] = doc.get("updated_by", "")
    # PK-39 (K-12) — mode dari Pusat Pengaturan (`budget.mode`, global → PT). Nilai lama `fin_budget_rules.mode` PT itu
    # tampil sebagai penimpa terdaftar sampai lapisan PT diisi (`config_overrides.mode_anggaran_lama`).
    res = await resolve("budget.mode", {"entity_id": entity_id} if entity_id and entity_id != "all" else {})
    nilai = res.get("value")
    if nilai not in MODE_FROM_SETTING:
        nilai = registry.require("budget.mode")["default"]
    out.update({"mode": MODE_FROM_SETTING[nilai], "mode_value": nilai, "mode_label": _mode_option_label(nilai),
                "mode_source": (res.get("overridden_by") or {}).get("label") or res.get("source_label", "")})
    return out


async def set_rules(entity_id: str, patch: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    if patch.get("mode") is not None:
        raise ValueError(mode_moved_message())   # PK-39 — satu editor: Pusat Pengaturan
    upd: Dict[str, Any] = {}
    if patch.get("unbudgeted_action") is not None:
        if patch["unbudgeted_action"] not in VALID_UNBUDGETED:
            raise ValueError(f"unbudgeted_action harus salah satu dari {', '.join(VALID_UNBUDGETED)}.")
        upd["unbudgeted_action"] = patch["unbudgeted_action"]
    if patch.get("warn_threshold_pct") is not None:
        pct = float(patch["warn_threshold_pct"])
        if pct < 0 or pct > 100:
            raise ValueError("warn_threshold_pct harus 0–100.")
        upd["warn_threshold_pct"] = round(pct, 1)
    for k in ("enforce_po_create", "enforce_po_approve"):
        if patch.get(k) is not None:
            upd[k] = bool(patch[k])
    if not upd:
        return await get_rules(entity_id)
    upd.update({"entity_id": entity_id, "updated_at": now_iso(),
                "updated_by": actor.get("name", "system")})
    await db[RULES_COLL].update_one({"entity_id": entity_id},
                                    {"$set": upd, "$setOnInsert": {"id": new_id("bgrule")}},
                                    upsert=True)
    return await get_rules(entity_id)


# ═══ CRUD anggaran ═══════════════════════════════════════════════════════════
async def backfill_dimensions() -> int:
    """Idempotent — dokumen `budgets` lama (tanpa dimension) → dimension=account."""
    res = await db.budgets.update_many(
        {"dimension": {"$exists": False}},
        [{"$set": {"dimension": DIM_ACCOUNT, "key": "$account_code",
                   "label": {"$ifNull": ["$account_name", "$account_code"]}}}])
    return res.modified_count


async def list_budgets(scope: Optional[Dict[str, Any]], year: Optional[int] = None,
                       dimension: Optional[str] = None) -> List[Dict[str, Any]]:
    await backfill_dimensions()
    q: Dict[str, Any] = {**(scope or {})}
    if year:
        q["year"] = int(year)
    if dimension:
        q["dimension"] = dimension
    return await db.budgets.find(q, {"_id": 0}).sort(
        [("year", -1), ("dimension", 1), ("key", 1), ("month", 1)]).to_list(5000)


async def resolve_key(dimension: str, key: str, entity_id: str = "") -> Tuple[str, str]:
    """Validasi key & ambil label. Return (key, label). Raise ValueError bila tak dikenal."""
    key = (key or "").strip()
    if not key:
        raise ValueError("Kunci anggaran (akun/kategori) wajib diisi.")
    if dimension == DIM_ACCOUNT:
        acc = (await _accounts_map()).get(key)
        if not acc:
            raise ValueError(f"Akun COA '{key}' tidak ditemukan.")
        return key, acc.get("name", key)
    cat = (await _category_map(entity_id)).get(key)
    if not cat:
        raise ValueError(f"Kategori beban '{key}' tidak ditemukan.")
    return key, cat.get("label", key)


def _snapshot(doc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return {f: (doc or {}).get(f) for f in HISTORY_FIELDS} if doc else {}


async def _write_history(budget: Dict[str, Any], action: str, before: Optional[Dict[str, Any]],
                         after: Optional[Dict[str, Any]], actor: Optional[Dict[str, Any]], reason: str = "") -> str:
    """PK-39 (FY-12) — satu baris riwayat pagu: `created` | `updated` | `deleted` (sebelum/sesudah: nominal, tahun,
    bulan, catatan)."""
    hid = new_id("bgh")
    await db[HISTORY_COLL].insert_one({
        "id": hid, "budget_id": budget.get("id", ""), "entity_id": budget.get("entity_id", ""),
        "dimension": budget.get("dimension", ""), "key": budget.get("key", ""), "label": budget.get("label", ""),
        "action": action, "before": _snapshot(before), "after": _snapshot(after),
        "reason": (reason or "").strip()[:500], "by": (actor or {}).get("name", "system"),
        "by_id": (actor or {}).get("id", ""), "at": now_iso()})
    return hid


def _is_dupe_key(exc: BaseException) -> bool:
    from indexes import is_duplicate_on
    return is_duplicate_on(exc, "entity_id", "year", "month", "dimension", "key")


async def create_budget(payload: Dict[str, Any], entity_id: str,
                        actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    dimension = (payload.get("dimension") or DIM_ACCOUNT).strip()
    if dimension not in DIMENSIONS:
        raise ValueError("dimension harus 'account' atau 'category'.")
    raw_key = payload.get("key") or payload.get("account_code") or payload.get("category_code") or ""
    key, label = await resolve_key(dimension, raw_key, entity_id)
    year = int(payload.get("year") or 0)
    if year < 2000 or year > 2999:
        raise ValueError("Tahun anggaran tidak valid.")
    month = int(payload.get("month", 0) or 0)
    if month < 0 or month > 12:
        raise ValueError("Bulan harus 0 (tahunan) atau 1–12.")
    amount = _r(payload.get("amount", 0))
    if amount <= 0:
        raise ValueError("Nominal anggaran harus > 0.")
    # Pesan ramah untuk kasus berurutan; keunikan sesungguhnya dijaga indeks `uq_budget_key` (PK-39, D7).
    dupe = await db.budgets.find_one({"entity_id": entity_id, "year": year, "month": month,
                                      "dimension": dimension, "key": key}, {"_id": 1})
    if dupe:
        raise DuplicateBudget(DUPLICATE_MSG)
    amap = await _accounts_map()
    acc_code = key if dimension == DIM_ACCOUNT else (await _category_map(entity_id)).get(key, {}).get("account_code", "")
    doc = {
        "id": new_id("budget"),
        "entity_id": entity_id,
        "year": year,
        "month": month,
        "dimension": dimension,
        "key": key,
        "label": label,
        "account_code": acc_code,
        "account_name": amap.get(acc_code, {}).get("name", acc_code),
        "account_type": amap.get(acc_code, {}).get("type", ""),
        "amount": amount,
        "note": payload.get("note", ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    try:
        await db.budgets.insert_one(dict(doc))
    except Exception as exc:  # noqa: BLE001 — dua simpan bersamaan: yang kalah kena indeks unik → 409
        if _is_dupe_key(exc):
            raise DuplicateBudget(DUPLICATE_MSG) from exc
        raise
    await _write_history(doc, "created", None, doc, actor)
    return doc


async def _audit(actor: Optional[Dict[str, Any]], action: str, budget: Dict[str, Any], before: Dict[str, Any],
                 after: Optional[Dict[str, Any]], reason: str) -> None:
    from dependencies import audit
    await audit((actor or {}).get("name", "system"), action, "budget", budget.get("id", ""),
                _snapshot(after) if after else None, reason=reason, before=before,
                scope_entity_id=budget.get("entity_id", ""))


async def update_budget(budget_id: str, patch: Dict[str, Any], scope: Optional[Dict[str, Any]],
                        actor: Optional[Dict[str, Any]] = None, reason: str = "") -> Optional[Dict[str, Any]]:
    """Ubah pagu → dokumen sesudah (None bila tak ada / diubah orang lain di sela). PK-39 — menulis `budget_history`
    (`updated`) dan jejak audit dengan nilai sebelum/sesudah + alasan."""
    q = {"id": budget_id, **(scope or {})}
    upd: Dict[str, Any] = {"updated_at": now_iso()}
    if patch.get("amount") is not None:
        amount = _r(patch["amount"])
        if amount <= 0:
            raise ValueError("Nominal anggaran harus > 0.")
        upd["amount"] = amount
    if patch.get("note") is not None:
        upd["note"] = patch["note"]
    for k in ("month", "year"):
        if patch.get(k) is not None:
            val = int(patch[k])
            if k == "month" and (val < 0 or val > 12):
                raise ValueError("Bulan harus 0 (tahunan) atau 1–12.")
            if k == "year" and (val < 2000 or val > 2999):  # G3 D4-BUD-EDIT-01 — batas sama dgn create
                raise ValueError("Tahun anggaran harus 2000–2999.")
            upd[k] = val
    cur = await db.budgets.find_one(q, {"_id": 0})
    if not cur:
        return None
    if "month" in upd or "year" in upd:
        merged = {f: upd.get(f, cur.get(f)) for f in ("entity_id", "year", "month", "dimension", "key")}
        if await db.budgets.find_one({**merged, "id": {"$ne": budget_id}}, {"_id": 1}):
            raise DuplicateBudget(DUPLICATE_MSG)
    # CAS: gagal (None → 404/muat ulang) bila nominal/periode diubah orang lain di sela baca & tulis.
    cas = {**q, "year": cur.get("year"), "month": cur.get("month"), "amount": cur.get("amount")}
    try:
        res = await db.budgets.find_one_and_update(cas, {"$set": upd}, return_document=True)
    except Exception as exc:  # noqa: BLE001
        if _is_dupe_key(exc):
            raise DuplicateBudget(DUPLICATE_MSG) from exc
        raise
    if res:
        res.pop("_id", None)
        await _write_history(res, "updated", cur, res, actor, reason)
        await _audit(actor, "budget_updated", res, _snapshot(cur), res, reason)
    return res


async def delete_budget(budget_id: str, scope: Optional[Dict[str, Any]],
                        actor: Optional[Dict[str, Any]] = None, reason: str = "") -> bool:
    """Hapus pagu. PK-39 — riwayat `deleted` ditulis SEBELUM dokumen dihapus; jejak audit memuat nilai sebelumnya."""
    cur = await db.budgets.find_one({"id": budget_id, **(scope or {})}, {"_id": 0})
    if not cur:
        return False
    hid = await _write_history(cur, "deleted", cur, None, actor, reason)
    res = await db.budgets.delete_one({"id": budget_id, **(scope or {})})
    if res.deleted_count == 0:   # sudah dihapus orang lain di sela → riwayat kita tidak berlaku
        await db[HISTORY_COLL].delete_one({"id": hid})
        return False
    await _audit(actor, "budget_deleted", cur, _snapshot(cur), None, reason)
    return True


async def budget_history(budget_id: str) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """(PT pagu | None bila id tak dikenal dan tak punya riwayat, riwayat terbaru dulu)."""
    rows = await db[HISTORY_COLL].find({"budget_id": budget_id}, {"_id": 0}).sort("at", -1).to_list(500)
    cur = await db.budgets.find_one({"id": budget_id}, {"_id": 0, "entity_id": 1})
    if not cur and not rows:
        return None, []
    return (cur or rows[0]).get("entity_id", ""), rows


# ═══ Realisasi (actual) ══════════════════════════════════════════════════════
def _year_range(year: int) -> Dict[str, str]:
    """Rentang teks `date` yang mungkin jatuh di tahun buku WIB `year` (± satu hari untuk stempel UTC)."""
    return {"$gte": f"{year - 1}-12-31", "$lte": f"{year + 1}-01-01T23:59:59.999999"}


def _bump_doc(docs: Dict[str, List[Dict[str, Any]]], code: str, item: Dict[str, Any]) -> None:
    lst = docs.setdefault(code, [])
    if len(lst) < 40:
        lst.append(item)


async def _actual_by_account(scope: Optional[Dict[str, Any]], year: int,
                             docs: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> Dict[str, Dict[int, float]]:
    """Realisasi per (account_code, month) dari jurnal operasional tahun buku WIB tsb (PK-39, FY-11).

    Pendapatan = kredit − debit; beban (dan jenis lain) = debit − kredit; ASET = debit penerimaan barang dikurangi
    kredit retur beli saja (HPP/opname/transfer mengkredit persediaan tanpa mengurangi belanja). `docs` (opsional)
    diisi jurnal penyumbang per akun untuk penelusuran (nomor, sumber, bulan, nilai)."""
    year = int(year)
    q: Dict[str, Any] = {"status": {"$ne": "void"}, "source_type": {"$ne": "closing"}, **(scope or {})}
    q["date"] = _year_range(year)
    amap = await _accounts_map()
    out: Dict[str, Dict[int, float]] = {}
    async for je in db.journal_entries.find(q, {"_id": 0, "date": 1, "lines": 1, "source_type": 1, "number": 1,
                                                "source_label": 1, "reversed": 1, "reversed_by_entry_id": 1}):
        yy, mm = _periode(je.get("date"))
        if yy != year:
            continue
        st = je.get("source_type") or ""
        for ln in je.get("lines", []):
            code = ln.get("account_code")
            if not code:
                continue
            atype = amap.get(code, {}).get("type", "")
            debit = _r(ln.get("debit", 0))
            credit = _r(ln.get("credit", 0))
            if atype == "income":
                val = credit - debit
            elif atype == "asset":
                if st == GR_SOURCE and not _is_reversed(je):
                    val = debit
                elif st == PRET_SOURCE and not _is_reversed(je):
                    val = -credit
                else:
                    continue
            else:
                val = debit - credit
            if abs(val) <= EPS:
                continue
            slot = out.setdefault(code, {})
            slot[mm] = round(slot.get(mm, 0.0) + val, 2)
            if docs is not None:
                _bump_doc(docs, code, {"ref": je.get("number", ""), "source_type": st,
                                       "label": je.get("source_label", ""), "month": mm, "amount": round(val, 2)})
    return out


async def _actual_by_category(scope: Optional[Dict[str, Any]], year: int,
                              docs: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> Dict[str, Dict[int, float]]:
    """Realisasi per (kategori beban, month) = LPJ yang dijurnal pada tahun buku tsb, pada bulan JURNALNYA (PK-39,
    FY-10). LPJ dicari lewat `source_id` jurnal; teks `periode` dan `created_at` LPJ tidak dipakai."""
    year = int(year)
    q: Dict[str, Any] = {"status": {"$ne": "void"}, "source_type": STL_SOURCE, **(scope or {})}
    q["date"] = _year_range(year)
    months: Dict[str, Tuple[int, str]] = {}
    async for je in db.journal_entries.find(q, {"_id": 0, "date": 1, "source_id": 1, "number": 1,
                                                "reversed": 1, "reversed_by_entry_id": 1}):
        yy, mm = _periode(je.get("date"))
        if yy != year or _is_reversed(je) or not je.get("source_id"):
            continue
        months[je["source_id"]] = (mm, je.get("number", ""))
    out: Dict[str, Dict[int, float]] = {}
    if not months:
        return out
    async for stl in db.cash_advance_settlements.find(
            {"id": {"$in": list(months)}}, {"_id": 0, "id": 1, "number": 1, "category_totals": 1}):
        mm, je_no = months[stl["id"]]
        for cat, amt in (stl.get("category_totals") or {}).items():
            if abs(_r(amt)) <= EPS:
                continue
            slot = out.setdefault(cat, {})
            slot[mm] = round(slot.get(mm, 0.0) + _r(amt), 2)
            if docs is not None:
                _bump_doc(docs, cat, {"ref": stl.get("number", ""), "source_type": STL_SOURCE, "label": je_no,
                                      "month": mm, "amount": _r(amt)})
    return out


# ═══ Komitmen (committed) ════════════════════════════════════════════════════
def po_open_value(po: Dict[str, Any]) -> float:
    """PK-39 (FY-11) — sisa PO yang belum diterima: `net_subtotal × (1 − nilai_diterima / nilai_dipesan)`.

    nilai_dipesan = Σ quantity × price; nilai_diterima = Σ min(received_qty, quantity) × price per baris. Hasil ≥ 0,
    dua desimal. PO tanpa baris bernilai → `net_subtotal` utuh (belum ada yang bisa diterima)."""
    base = _r(po.get("net_subtotal") or po.get("dpp") or po.get("total_amount") or 0)
    ordered = received = 0.0
    for it in po.get("items") or []:
        qty = max(float(it.get("quantity") or 0), 0.0)
        price = float(it.get("price") or 0)
        got = min(max(float(it.get("received_qty") or 0), 0.0), qty)
        ordered += qty * price
        received += got * price
    if ordered <= EPS:
        return max(base, 0.0)
    return round(max(base * (1 - received / ordered), 0.0), 2)


def po_budget_targets(po: Dict[str, Any], default_account: str) -> List[Dict[str, Any]]:
    """Target anggaran sebuah PO. Nilai = DPP/net subtotal (excl PPN) agar setara beban. PO tanpa tanda anggaran →
    `default_account` (akun persediaan hasil pemetaan, lihat `inventory_account`)."""
    amount = _r(po.get("net_subtotal") or po.get("dpp") or po.get("total_amount") or 0)
    dim = (po.get("budget_dimension") or "").strip()
    key = (po.get("budget_key") or "").strip()
    if dim in DIMENSIONS and key:
        return [{"dimension": dim, "key": key, "amount": amount}]
    return [{"dimension": DIM_ACCOUNT, "key": default_account, "amount": amount}]


async def _commitment_map(scope: Optional[Dict[str, Any]], year: int, exclude_po_id: str = "",
                          exclude_stl_id: str = "") -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Komitmen per (dimension, key) → {'total', 'by_month', 'docs'} dari SISA PO terbuka + LPJ belum disetujui."""
    year = int(year)
    out: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def _bump(dim: str, key: str, month: int, amt: float, label: str, ref: str, kind: str):
        slot = out.setdefault((dim, key), {"total": 0.0, "by_month": {}, "docs": []})
        slot["total"] = round(slot["total"] + amt, 2)
        slot["by_month"][month] = round(slot["by_month"].get(month, 0.0) + amt, 2)
        if len(slot["docs"]) < 25:
            slot["docs"].append({"ref": ref, "label": label, "amount": amt, "kind": kind, "month": month})

    inv: Dict[str, str] = {}
    po_q: Dict[str, Any] = {"status": {"$nin": list(CLOSED_PO_STATUSES)}, **(scope or {})}
    if exclude_po_id:
        po_q["id"] = {"$ne": exclude_po_id}
    async for po in db.purchase_orders.find(po_q, {
            "_id": 0, "id": 1, "po_number": 1, "entity_id": 1, "net_subtotal": 1, "dpp": 1, "total_amount": 1,
            "items": 1, "budget_dimension": 1, "budget_key": 1, "expected_delivery_date": 1,
            "created_at": 1, "supplier_name": 1}):
        yy, mm = _periode(po.get("expected_delivery_date") or po.get("created_at"))
        if yy != year:
            continue
        sisa = po_open_value(po)
        if sisa <= EPS:
            continue
        eid = po.get("entity_id") or ""
        if eid not in inv:
            inv[eid] = await inventory_account(eid)
        for t in po_budget_targets(po, inv[eid]):
            _bump(t["dimension"], t["key"], mm, sisa, po.get("supplier_name", ""), po.get("po_number", ""), "po")

    stl_q: Dict[str, Any] = {"status": {"$in": OPEN_STL_STATUSES}, **(scope or {})}
    if exclude_stl_id:
        stl_q["id"] = {"$ne": exclude_stl_id}
    async for stl in db.cash_advance_settlements.find(stl_q, {
            "_id": 0, "number": 1, "created_at": 1, "category_totals": 1, "divisi": 1}):
        yy, mm = _periode(stl.get("created_at"))
        if yy != year:
            continue
        for cat, amt in (stl.get("category_totals") or {}).items():
            if _r(amt) <= EPS:
                continue
            _bump(DIM_CATEGORY, cat, mm, _r(amt), stl.get("divisi", ""), stl.get("number", ""), "lpj")
    return out


# ═══ Laporan Anggaran vs Komitmen vs Realisasi ═══════════════════════════════
def _status_of(budget: float, spent: float, warn_pct: float) -> str:
    if budget <= EPS:
        return "ok"
    pct = spent / budget * 100
    if spent > budget + EPS:
        return "over"
    return "warning" if pct >= warn_pct else "ok"


def _warn_pct(rules: Dict[str, Any]) -> float:
    # G3 D4-BUD-THRESHOLD-01 — 0 adalah ambang sah; hanya None/missing yang memakai bawaan 85.
    wp = rules.get("warn_threshold_pct")
    return float(DEFAULT_RULES["warn_threshold_pct"] if wp is None or wp == "" else wp)


def _scope_entity_ids(scope: Optional[Dict[str, Any]], budgets: Iterable[Dict[str, Any]]) -> List[str]:
    """PT dalam cakupan laporan: dari saringan `entity_id` (satu / `$in`), else PT pemilik pagu."""
    val = (scope or {}).get("entity_id")
    if isinstance(val, str):
        ids = [val]
    elif isinstance(val, dict) and isinstance(val.get("$in"), (list, tuple)):
        ids = list(val["$in"])
    else:
        ids = sorted({b.get("entity_id") for b in budgets if b.get("entity_id")})
    return [i for i in dict.fromkeys(ids) if i and i != "all"]


def _docs_for(docs: List[Dict[str, Any]], month: int) -> List[Dict[str, Any]]:
    pick = [d for d in docs if month <= 0 or d.get("month") == month]
    return sorted(pick, key=lambda d: -abs(float(d.get("amount") or 0)))[:8]


async def budget_vs_actual(scope: Optional[Dict[str, Any]], year: int,
                           entity_id_for_rules: str = "") -> Dict[str, Any]:
    """PK-39 (FY-11) — realisasi & komitmen dihitung PER PT pemilik pagu (satu hitungan per PT, disimpan selama satu
    permintaan); tiap baris membawa `entity_id`/`entity_name`; mode gabungan = penjumlahan berlabel belum dieliminasi."""
    from services.work_labels import entity_names
    year = int(year)
    budgets = await list_budgets(scope, year)
    ids = _scope_entity_ids(scope, budgets)
    names = await entity_names(ids + [b.get("entity_id", "") for b in budgets])
    per_pt: Dict[str, Dict[str, Any]] = {}

    async def _pt(eid: str) -> Dict[str, Any]:
        if eid not in per_pt:
            sc = {"entity_id": eid}
            acc_docs: Dict[str, List[Dict[str, Any]]] = {}
            cat_docs: Dict[str, List[Dict[str, Any]]] = {}
            per_pt[eid] = {
                "acc": await _actual_by_account(sc, year, acc_docs), "acc_docs": acc_docs,
                "cat": await _actual_by_category(sc, year, cat_docs), "cat_docs": cat_docs,
                "cmt": await _commitment_map(sc, year), "rules": await get_rules(eid)}
        return per_pt[eid]

    rules = await get_rules(entity_id_for_rules or "")
    rows: List[Dict[str, Any]] = []
    tot = {"budget": 0.0, "committed": 0.0, "actual": 0.0}
    per_dim: Dict[str, Dict[str, float]] = {}
    for b in budgets:
        eid = b.get("entity_id", "")
        data = await _pt(eid)
        dim = b.get("dimension") or DIM_ACCOUNT
        key = b.get("key") or b.get("account_code") or ""
        month = int(b.get("month", 0) or 0)
        src, src_docs = (data["acc"], data["acc_docs"]) if dim == DIM_ACCOUNT else (data["cat"], data["cat_docs"])
        by_month = src.get(key, {})
        cmt = data["cmt"].get((dim, key), {"total": 0.0, "by_month": {}, "docs": []})
        if month > 0:
            actual = _r(by_month.get(month, 0.0))
            committed = _r(cmt["by_month"].get(month, 0.0))
        else:
            actual = _r(sum(by_month.values()))
            committed = _r(cmt["total"])
        budget_amt = _r(b.get("amount", 0))
        spent = round(actual + committed, 2)
        rows.append({
            "id": b["id"], "entity_id": eid, "entity_name": names.get(eid, eid),
            "dimension": dim, "key": key,
            "label": b.get("label") or b.get("account_name") or key,
            "account_code": b.get("account_code", ""), "account_type": b.get("account_type", ""),
            "month": month, "budget": budget_amt, "committed": committed, "actual": actual,
            "spent": spent,
            "remaining": round(budget_amt - spent, 2),
            "variance": round(budget_amt - actual, 2),
            "used_pct": round(actual / budget_amt * 100, 1) if budget_amt > EPS else None,
            "spent_pct": round(spent / budget_amt * 100, 1) if budget_amt > EPS else None,
            "status": _status_of(budget_amt, spent, _warn_pct(data["rules"])),
            "commitment_docs": _docs_for(cmt["docs"], month),
            "actual_docs": _docs_for(src_docs.get(key, []), month),
            "note": b.get("note", ""),
        })
        tot["budget"] += budget_amt
        tot["committed"] += committed
        tot["actual"] += actual
        d = per_dim.setdefault(dim, {"budget": 0.0, "committed": 0.0, "actual": 0.0, "rows": 0})
        d["budget"] += budget_amt
        d["committed"] += committed
        d["actual"] += actual
        d["rows"] += 1

    rows.sort(key=lambda r: (r["dimension"], r["key"], r["month"], r["entity_name"]))
    budgeted = {(r["entity_id"], r["dimension"], r["key"]) for r in rows}
    unbudgeted: List[Dict[str, Any]] = []
    for eid in ids:
        data = await _pt(eid)
        for (dim, key), v in data["cmt"].items():
            if (eid, dim, key) not in budgeted and v["total"] > EPS:
                unbudgeted.append({"entity_id": eid, "entity_name": names.get(eid, eid), "dimension": dim, "key": key,
                                   "committed": _r(v["total"]), "docs": v["docs"][:5]})
    unbudgeted.sort(key=lambda r: -r["committed"])
    spent_tot = round(tot["actual"] + tot["committed"], 2)
    for d in per_dim.values():
        for k in ("budget", "committed", "actual"):
            d[k] = _r(d[k])
        d["spent"] = round(d["actual"] + d["committed"], 2)
        d["remaining"] = round(d["budget"] - d["spent"], 2)
    combined = len(ids) > 1
    return {
        "year": year,
        "rows": rows,
        "by_dimension": per_dim,
        "unbudgeted_commitments": unbudgeted,
        "alerts": [r for r in rows if r["status"] in ("over", "warning")],
        "rules": rules,
        "is_combined": combined,
        "combined_note": COMBINED_NOTE if combined else "",
        "totals": {
            "budget": _r(tot["budget"]), "commitment": _r(tot["committed"]),
            "committed": _r(tot["committed"]), "actual": _r(tot["actual"]), "spent": spent_tot,
            "remaining": round(_r(tot["budget"]) - spent_tot, 2),
            "variance": round(_r(tot["budget"]) - _r(tot["actual"]), 2),
            "used_pct": round(tot["actual"] / tot["budget"] * 100, 1) if tot["budget"] > EPS else None,
            "spent_pct": round(spent_tot / tot["budget"] * 100, 1) if tot["budget"] > EPS else None,
            "over_count": sum(1 for r in rows if r["status"] == "over"),
        },
        "generated_at": now_iso(),
    }


# ═══ Pemeriksaan & penegakan (enforcement) ═══════════════════════════════════
async def check_budget(entity_id: str, dimension: str, key: str, amount: float,
                       date: str = "", exclude_po_id: str = "", *, exclude_stl_id: str = "",
                       rules: Optional[Dict[str, Any]] = None, strict_key: bool = True) -> Dict[str, Any]:
    """Cek satu target: sisa anggaran & apakah transaksi sebesar `amount` melampauinya. Bulan = bulan buku WIB
    `date` (kosong → hari ini). `strict_key=False` (titik pemeriksaan): kunci tanpa master tidak menggagalkan."""
    if dimension not in DIMENSIONS:
        raise ValueError("dimension harus 'account' atau 'category'.")
    ref = _tanggal(date)
    year, month = int(ref[:4]), int(ref[5:7])
    scope = {"entity_id": entity_id}
    rules = rules or await get_rules(entity_id)
    await backfill_dimensions()
    monthly = await db.budgets.find_one({**scope, "year": year, "month": month,
                                         "dimension": dimension, "key": key}, {"_id": 0})
    annual = None if monthly else await db.budgets.find_one(
        {**scope, "year": year, "month": 0, "dimension": dimension, "key": key}, {"_id": 0})
    bdoc = monthly or annual
    src = (await _actual_by_account(scope, year)) if dimension == DIM_ACCOUNT \
        else (await _actual_by_category(scope, year))
    by_month = src.get(key, {})
    cmt = (await _commitment_map(scope, year, exclude_po_id=exclude_po_id, exclude_stl_id=exclude_stl_id)).get(
        (dimension, key), {"total": 0.0, "by_month": {}})
    if monthly:
        actual = _r(by_month.get(month, 0.0))
        committed = _r(cmt["by_month"].get(month, 0.0))
    else:
        actual = _r(sum(by_month.values()))
        committed = _r(cmt["total"])
    if bdoc and bdoc.get("label"):
        label = bdoc["label"]
    else:
        try:
            _, label = await resolve_key(dimension, key, entity_id)
        except ValueError:
            if strict_key:
                raise
            label = key
    amount = _r(amount)
    budget_amt = _r((bdoc or {}).get("amount", 0))
    spent = round(actual + committed, 2)
    available = round(budget_amt - spent, 2)
    after = round(available - amount, 2)
    mode = rules["mode"]   # get_rules selalu mengisi mode (dari `budget.mode`)
    out = {
        "entity_id": entity_id, "dimension": dimension, "key": key, "label": label,
        "year": year, "month": month, "period_basis": "monthly" if monthly else "annual",
        "has_budget": bdoc is not None, "budget_id": (bdoc or {}).get("id", ""), "budget": budget_amt,
        "actual": actual, "committed": committed, "spent": spent, "available": available,
        "amount": amount, "available_after": after,
        "over": bool(bdoc) and after < -EPS,
        "over_amount": round(-after, 2) if (bdoc and after < -EPS) else 0.0,
        "used_pct_after": round((spent + amount) / budget_amt * 100, 1) if budget_amt > EPS else None,
        "mode": mode, "mode_label": rules.get("mode_label", ""),
        "unbudgeted_action": rules.get("unbudgeted_action", "allow"),
        "warn_threshold_pct": rules.get("warn_threshold_pct", DEFAULT_RULES["warn_threshold_pct"]),
    }
    jenis = "akun" if dimension == DIM_ACCOUNT else "kategori"
    if not bdoc:
        act = out["unbudgeted_action"]
        out["blocked"] = mode != "off" and act == "block"
        out["warning"] = (f"Belum ada anggaran {jenis} {label} untuk tahun {year}."
                          if (mode != "off" and act in ("warn", "block")) else "")
        return out
    near = out["used_pct_after"] is not None and out["used_pct_after"] >= float(out["warn_threshold_pct"])
    out["blocked"] = mode == "block" and out["over"]
    periode = f"bulan {month}/{year}" if monthly else f"tahunan {year}"
    if mode == "off":
        out["warning"] = ""
    elif out["over"]:
        out["warning"] = (f"Melampaui anggaran {label} ({key}): kebutuhan {rupiah(amount)} melebihi sisa "
                          f"{rupiah(available)} sebesar {rupiah(out['over_amount'])} (pagu {periode}).")
    elif near:
        out["warning"] = (f"Anggaran {label} ({key}) akan terpakai {out['used_pct_after']}% "
                          f"(ambang {out['warn_threshold_pct']}%, pagu {periode}).")
    else:
        out["warning"] = ""
    return out


async def enforce_budget(entity_id: str, targets: List[Dict[str, Any]], *, when: str, date: str,
                         actor: Dict[str, Any], exclude_po_id: str = "", exclude_stl_id: str = "") -> Dict[str, Any]:
    """PK-39 (FY-12, K-12) — pemeriksaan anggaran satu transaksi. Tiap target = `{"dimension", "key", "amount"}`.

    Mode `off` → `skipped`. Titik PO mengikuti sakelar `enforce_po_create`/`enforce_po_approve`. Mode `block` +
    melampaui → `ValueError("Anggaran terlampaui: …")`, kecuali titik di `SOFT_POINTS` (diperlakukan peringatan)."""
    rules = await get_rules(entity_id)
    result: Dict[str, Any] = {"mode": rules["mode"], "mode_label": rules.get("mode_label", ""),
                              "when": when, "checked_at": now_iso(), "warnings": [], "checks": [],
                              "blocked": False, "skipped": False}
    if rules["mode"] == "off":
        result["skipped"] = True
        return result
    flag = PO_POINTS.get(when)
    if flag and not rules.get(flag, True):
        result["skipped"] = True
        return result
    for t in targets or []:
        amt = _r(t.get("amount"))
        if amt <= EPS or not t.get("key"):
            continue
        chk = await check_budget(entity_id, t["dimension"], t["key"], amt, date=date, exclude_po_id=exclude_po_id,
                                 exclude_stl_id=exclude_stl_id, rules=rules, strict_key=False)
        result["checks"].append(chk)
        if chk.get("warning"):
            result["warnings"].append(chk["warning"])
        if chk.get("blocked"):
            result["blocked"] = True
    if result["blocked"]:
        if when in SOFT_POINTS:
            result["blocked"] = False
            result["held_at_approval"] = True
            result["warnings"].append("Persetujuan akan ditolak selama pagu belum dinaikkan.")
        else:
            raise ValueError("Anggaran terlampaui: " + " ".join(result["warnings"]))
    _ = actor
    return result


async def enforce_po_budget(po: Dict[str, Any], when: str, actor: Dict[str, Any],
                            exclude_po_id: str = "") -> Dict[str, Any]:
    """Pembungkus tipis `enforce_budget` untuk PO (nilai PO utuh; komitmen PO ini sendiri dikecualikan)."""
    entity_id = po.get("entity_id") or ""
    targets = po_budget_targets(po, await inventory_account(entity_id))
    return await enforce_budget(entity_id, targets, when=when,
                                date=po.get("expected_delivery_date") or po.get("created_at") or "",
                                actor=actor, exclude_po_id=exclude_po_id or po.get("id", ""))


async def bill_budget_targets(bill: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tagihan pemasok TANPA PO yang berakun beban (`expense_account_code`) → akun itu, nilai DPP. Tagihan ber-PO
    (dicakup komitmen PO) dan tagihan jasa makloon (lawan akunnya persediaan dalam proses) tidak diperiksa."""
    if bill.get("po_id"):
        return []
    code = (bill.get("expense_account_code") or "").strip()
    if not code or not await _is_expense(code, bill.get("entity_id") or ""):
        return []
    dpp = bill.get("dpp") or bill.get("net_subtotal") or \
        (float(bill.get("grand_total") or 0) - float(bill.get("ppn_amount") or 0))
    return [{"dimension": DIM_ACCOUNT, "key": code, "amount": _r(dpp)}]


async def cash_budget_targets(txn: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Kas KELUAR manual (tanpa `ref_type`) → akun lawan (`gl_service.cash_contra_account`) bila berjenis beban."""
    from services import gl_service as gl
    if txn.get("direction") != "out" or txn.get("ref_type"):
        return []
    code = gl.cash_contra_account(txn)
    if not code or not await _is_expense(code, txn.get("entity_id") or ""):
        return []
    return [{"dimension": DIM_ACCOUNT, "key": code, "amount": _r(txn.get("amount"))}]


def settlement_budget_targets(stl: Dict[str, Any]) -> List[Dict[str, Any]]:
    """LPJ → tiap kategori di `category_totals`."""
    return [{"dimension": DIM_CATEGORY, "key": cat, "amount": _r(amt)}
            for cat, amt in (stl.get("category_totals") or {}).items() if _r(amt) > EPS]
