"""Bank/Cash Accounts service (EPIC7-B) — multi-akun kas & bank + rekonsiliasi.

Koleksi kanonik: `bank_accounts` (master akun). Mutasi tetap memakai
`cash_transactions` (SSOT kas) dengan field opsional `account_id` yang
menautkan transaksi ke akun. Saldo akun = opening_balance + Σ(in) − Σ(out)
transaksi posted (non-void) milik akun tsb.

PK-21 (SL-10) — status "terekonsiliasi" punya SATU sumber: alokasi mutasi bank (`bank_recon_service`, field
`reconciled_amount`). Saldo terekonsiliasi & jumlah "belum dicocokkan" diturunkan dari angka itu
(`bank_recon_service.txn_reconciled`); tanda manual `reconciled` ya/tidak sudah dihapus (endpoint → 410).
"""
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, safe_doc, DEFAULT_ENTITY_ID
from services.bank_recon_service import txn_reconciled

VALID_ACCOUNT_TYPES = {"bank", "cash"}
CASH_TYPES = {"kas_kecil", "kas_besar"}


def account_cash_type(acc: Dict[str, Any]) -> str:
    """G3 D4-CASH-01 — jenis kas TETAP dari master rekening (bukan dari transaksi aktif)."""
    ct = acc.get("cash_type")
    if ct in CASH_TYPES:
        return ct
    return "kas_kecil" if acc.get("account_type") == "cash" else "kas_besar"


async def backfill_cash_type() -> int:
    """Isi `cash_type` rekening lama SEKALI (hanya yang belum punya): mayoritas jenis kas riwayat
    transaksinya (termasuk void), bila tak ada riwayat → dari `account_type`."""
    n = 0
    async for acc in db.bank_accounts.find({"cash_type": {"$nin": list(CASH_TYPES)}}, {"_id": 0}):
        counts = {ct: await db.cash_transactions.count_documents({"account_id": acc["id"], "cash_type": ct})
                  for ct in CASH_TYPES}
        if counts["kas_kecil"] or counts["kas_besar"]:
            ct = "kas_kecil" if counts["kas_kecil"] > counts["kas_besar"] else "kas_besar"
            src = "backfill_history"
        else:
            ct, src = account_cash_type(acc), "backfill_account_type"
        res = await db.bank_accounts.update_one(
            {"id": acc["id"], "cash_type": {"$nin": list(CASH_TYPES)}},
            {"$set": {"cash_type": ct, "cash_type_source": src}})
        n += res.modified_count
    return n


# ─── PM-T1 — atas nama, peruntukan, cara bayar yang dilayani, bawaan penerimaan per PT ────────────────────────────
#: Peruntukan rekening (urutan = urutan layar). Rekening lama dianggap boleh dipakai untuk semuanya (perilaku hari ini).
PERUNTUKAN = ("penerimaan_pelanggan", "pembayaran_pemasok", "gaji", "operasional")
BIDANG_PM = ("holder_name", "purposes", "payment_method_codes", "default_receiving_methods", "show_on_documents")


def _aktif(acc: Dict[str, Any]) -> bool:
    return acc.get("is_active") is not False and acc.get("status") != "inactive"


def _jenis(acc: Dict[str, Any]) -> str:
    return "cash" if acc.get("account_type") == "cash" else "bank"


def bidang_efektif(acc: Dict[str, Any], tunggal: bool = False) -> Dict[str, Any]:
    """Nilai lima field PM-T1 yang BERLAKU untuk rekening ini. Rekening lama (field belum ada) memakai nilai awal
    spesifikasi: empat peruntukan; cara bayar menurut jenisnya; bawaan penerimaan = cara bayar pertama jenisnya HANYA
    bila ia satu-satunya rekening aktif PT untuk jenisnya (`tunggal`); atas nama kosong; tidak tampil di dokumen."""
    from services.payment_method_service import kode_awal_rekening
    kode = kode_awal_rekening(_jenis(acc))
    return {
        "holder_name": acc.get("holder_name", ""),
        "purposes": list(acc["purposes"]) if "purposes" in acc else list(PERUNTUKAN),
        "payment_method_codes": list(acc["payment_method_codes"]) if "payment_method_codes" in acc else list(kode),
        "default_receiving_methods": (list(acc["default_receiving_methods"]) if "default_receiving_methods" in acc
                                      else (kode[:1] if tunggal and _aktif(acc) else [])),
        "show_on_documents": bool(acc.get("show_on_documents", False)),
    }


async def rekening_pt(entity_id: str) -> List[Dict[str, Any]]:
    """Semua rekening PT + `_efektif` (field PM-T1 yang berlaku). Ketunggalan dihitung per jenis di antara yang aktif."""
    accs = await db.bank_accounts.find({"entity_id": entity_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    hitung: Dict[str, int] = {}
    for a in accs:
        if _aktif(a):
            hitung[_jenis(a)] = hitung.get(_jenis(a), 0) + 1
    for a in accs:
        a["_efektif"] = bidang_efektif(a, tunggal=hitung.get(_jenis(a), 0) == 1)
    return accs


async def isi_awal_bidang_rekening(tulis: bool = False, entity_id: str = "") -> Dict[str, Any]:
    """PM-T1 — pengisian awal field baru rekening LAMA (idempoten). Hanya field yang BELUM ada yang diisi (syarat
    `$exists: False`), dengan nilai `bidang_efektif`. `tulis=False` (bawaan) = lapor saja.

    Bawaan penerimaan yang akan berbenturan dengan rekening lain PT itu (yang sudah bawaan untuk cara bayar yang sama)
    diisi `[]` — satu bawaan per (PT, cara bayar), dijaga indeks unik `uq_default_receiving`."""
    q: Dict[str, Any] = {"$or": [{f: {"$exists": False}} for f in BIDANG_PM]}
    if entity_id:
        q["entity_id"] = entity_id
    pts = sorted({a.get("entity_id") or "" async for a in db.bank_accounts.find(q, {"_id": 0, "entity_id": 1})})
    rincian: List[Dict[str, Any]] = []
    diubah = 0
    for eid in pts:
        accs = await rekening_pt(eid)
        terpakai = {m for a in accs if "default_receiving_methods" in a for m in a["default_receiving_methods"]}
        for a in accs:
            hilang = [f for f in BIDANG_PM if f not in a]
            if not hilang:
                continue
            isi = {f: a["_efektif"][f] for f in hilang}
            if "default_receiving_methods" in isi:
                isi["default_receiving_methods"] = [m for m in isi["default_receiving_methods"] if m not in terpakai]
                terpakai |= set(isi["default_receiving_methods"])
            rincian.append({"entity_id": eid, "account_id": a["id"], "name": a.get("name", ""), "isi": isi})
            if tulis:
                res = await db.bank_accounts.update_one(
                    {"id": a["id"], **{f: {"$exists": False} for f in hilang}}, {"$set": isi})
                diubah += res.modified_count
    return {"mode": "tulis" if tulis else "lapor", "diperiksa": len(rincian),
            "diubah": diubah if tulis else 0, "rincian": rincian}


def _posted(txn: Dict[str, Any]) -> bool:
    return txn.get("status") != "void"


async def sole_account_id(entity_id: str, cash_type: str) -> str:
    """Rekening SATU-SATUNYA milik PT untuk jenis kas ini (kas kecil / kas besar-bank), atau "" bila 0 / lebih dari 1."""
    if not entity_id or cash_type not in CASH_TYPES:
        return ""
    # PM-T1 — rekening dinonaktifkan lewat `is_active: False` (field `status` tidak pernah diisi layar ini).
    accs = [a async for a in db.bank_accounts.find({"entity_id": entity_id, "is_active": {"$ne": False},
                                                    "status": {"$ne": "inactive"}},
                                                    {"_id": 0, "id": 1, "cash_type": 1, "account_type": 1})]
    ids = [a["id"] for a in accs if account_cash_type(a) == cash_type]
    return ids[0] if len(ids) == 1 else ""


async def _txns_for(account_id: str) -> List[Dict[str, Any]]:
    """Mutasi rekening. UAT 24 Okt (audit UI 060↔061) — transaksi kas TANPA rekening (kas manual lama, kwitansi,
    refund) dulu tidak masuk saldo rekening mana pun sehingga saldo rekening ≠ ringkasan kas. Bila rekening ini
    satu-satunya rekening PT untuk jenis kasnya, transaksi tanpa rekening milik PT & jenis kas itu ikut dihitung."""
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0, "id": 1, "entity_id": 1, "cash_type": 1,
                                                                "account_type": 1}) or {}
    q: Dict[str, Any] = {"account_id": account_id, "status": {"$ne": "void"}}
    ct = account_cash_type(acc) if acc else ""
    if acc and await sole_account_id(acc.get("entity_id") or "", ct) == account_id:
        q = {"status": {"$ne": "void"}, "$or": [
            {"account_id": account_id},
            {"account_id": {"$in": [None, ""]}, "entity_id": acc.get("entity_id"), "cash_type": ct}]}
    return await db.cash_transactions.find(q, {"_id": 0}).sort("txn_date", -1).to_list(None)   # W2-021 — SELURUH mutasi


def _balance(opening: float, txns: List[Dict[str, Any]], reconciled_only: bool = False) -> float:
    bal = float(opening or 0)
    for t in txns:
        if reconciled_only and not txn_reconciled(t):   # PK-21 — dari angka pencocokan, bukan tanda tersimpan
            continue
        amt = float(t.get("amount", 0) or 0)
        bal += amt if t.get("direction") == "in" else -amt
    return round(bal, 2)


def _enrich(acc: Dict[str, Any], txns: List[Dict[str, Any]]) -> Dict[str, Any]:
    opening = float(acc.get("opening_balance", 0) or 0)
    inflow = round(sum(float(t.get("amount", 0) or 0) for t in txns if t.get("direction") == "in"), 2)
    outflow = round(sum(float(t.get("amount", 0) or 0) for t in txns if t.get("direction") == "out"), 2)
    reconciled = sum(1 for t in txns if txn_reconciled(t))   # PK-21
    return {
        **acc,
        "balance": _balance(opening, txns),
        "reconciled_balance": _balance(opening, txns, reconciled_only=True),
        "inflow": inflow,
        "outflow": outflow,
        "txn_count": len(txns),
        "unreconciled_count": len(txns) - reconciled,
    }


async def list_accounts(entity_id: Optional[str] = None,
                        scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = dict(scope) if scope is not None else {}
    if scope is None and entity_id and entity_id != "all":
        q["entity_id"] = entity_id
    accounts = await db.bank_accounts.find(q, {"_id": 0}).sort("created_at", 1).to_list(500)
    efektif: Dict[str, Dict[str, Any]] = {}   # PM-T1 — field atas nama/peruntukan/cara bayar yang BERLAKU
    for eid in sorted({a.get("entity_id") or "" for a in accounts}):
        for a in await rekening_pt(eid):
            efektif[a["id"]] = a["_efektif"]
    out = []
    for acc in accounts:
        txns = await _txns_for(acc["id"])
        out.append({**_enrich(acc, txns), **efektif.get(acc["id"], bidang_efektif(acc))})
    return out


async def unlinked_transactions(entity_ids: List[str]) -> Dict[str, Any]:
    """Transaksi kas (non-void) yang TIDAK masuk saldo rekening mana pun: tanpa `account_id` dan tidak terserap
    rekening tunggal PT untuk jenis kasnya (aturan `_txns_for`). Penjelas selisih buku besar vs total rekening."""
    out = {"count": 0, "inflow": 0.0, "outflow": 0.0, "net": 0.0}
    if not entity_ids:
        return out
    sole: Dict[Any, str] = {}
    q = {"entity_id": {"$in": list(entity_ids)}, "status": {"$ne": "void"},
         "$or": [{"account_id": {"$exists": False}}, {"account_id": {"$in": [None, ""]}}]}
    async for t in db.cash_transactions.find(q, {"_id": 0, "entity_id": 1, "cash_type": 1, "amount": 1,
                                                 "direction": 1}):
        key = (t.get("entity_id") or "", t.get("cash_type") or "")
        if key not in sole:
            sole[key] = await sole_account_id(key[0], key[1]) if key[1] in CASH_TYPES else ""
        if sole[key]:
            continue   # ikut dihitung di saldo rekening tunggal PT itu
        amt = float(t.get("amount", 0) or 0)
        out["count"] += 1
        if t.get("direction") == "in":
            out["inflow"] += amt
        else:
            out["outflow"] += amt
    out["inflow"], out["outflow"] = round(out["inflow"], 2), round(out["outflow"], 2)
    out["net"] = round(out["inflow"] - out["outflow"], 2)
    return out


async def cash_position(entity_ids: List[str]) -> Dict[str, Any]:
    """Keputusan pemilik K-02 (26 Okt) — angka utama "Kas & Bank" = saldo BUKU BESAR akun kas+bank (kode
    `CASH_CODES`, sumber yang sama dengan Dasbor Keuangan & Proyeksi Arus Kas). Rekening & Saldo = rincian per
    rekening; selisih keduanya dijelaskan lewat transaksi kas yang belum tertaut ke rekening."""
    from services import financial_statement_service as fs
    from services.cash_flow_service import CASH_CODES
    scope = {"entity_id": {"$in": list(entity_ids or [])}}
    amap = await fs._accounts_map(scope)   # noqa: SLF001 — helper laporan yang sama dipakai Dasbor Keuangan
    agg = await fs._aggregate(scope, None, include_closing=True)   # noqa: SLF001
    lines, total = [], 0.0
    for code in sorted(CASH_CODES):
        v = agg.get(code, {"debit": 0.0, "credit": 0.0})
        bal = round(float(v.get("debit", 0) or 0) - float(v.get("credit", 0) or 0), 2)
        total += bal
        lines.append({"code": code, "name": amap.get(code, {}).get("name", code), "balance": bal})
    return {"gl_total": round(total, 2), "gl_accounts": lines,
            "unlinked": await unlinked_transactions(entity_ids or []),
            "source_label": "Saldo buku besar akun kas & bank"}


async def _cabut_bawaan_lain(entity_id: str, account_id: str, methods: List[str]) -> None:
    """PM-T1 — satu bawaan penerimaan per (PT, cara bayar): rekening lain PT itu kehilangan tanda bawaan cara bayar
    yang sama (operasi yang sama dengan penulisan rekening ini)."""
    if not methods:
        return
    await db.bank_accounts.update_many(
        {"entity_id": entity_id, "id": {"$ne": account_id}, "default_receiving_methods": {"$in": list(methods)}},
        {"$pull": {"default_receiving_methods": {"$in": list(methods)}}})


async def _tulis_bawaan(entity_id: str, account_id: str, methods: List[str], tulis) -> Any:
    """Cabut bawaan lain lalu `tulis()`; benturan indeks unik (dua permintaan bersamaan) → ulangi (paling banyak 3×)."""
    from pymongo.errors import DuplicateKeyError
    for percobaan in range(3):
        await _cabut_bawaan_lain(entity_id, account_id, methods)
        try:
            return await tulis()
        except DuplicateKeyError:
            if percobaan == 2:
                raise
    return None


async def create_account(payload, actor: Dict[str, Any], bidang: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`bidang` = field PM-T1 yang sudah diperiksa (`bank_account_change_service.periksa_isian`)."""
    if payload.account_type not in VALID_ACCOUNT_TYPES:
        raise ValueError("account_type harus 'bank' atau 'cash'")
    doc = {
        "id": new_id("bank"),
        "name": payload.name.strip(),
        "account_type": payload.account_type,
        "cash_type": "",
        "cash_type_source": "explicit",
        "bank_name": (payload.bank_name or "").strip(),
        "account_number": (payload.account_number or "").strip(),
        "entity_id": payload.entity_id or DEFAULT_ENTITY_ID,
        "opening_balance": round(float(payload.opening_balance or 0), 2),
        "currency": payload.currency or "IDR",
        "note": (payload.note or "").strip(),
        "is_active": True,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    ct = getattr(payload, "cash_type", "") or ""
    if ct and ct not in CASH_TYPES:
        raise ValueError("cash_type harus 'kas_kecil' atau 'kas_besar'")
    doc["cash_type"] = ct or account_cash_type(doc)
    doc.update(bidang or bidang_efektif(doc))
    from services import gl_service as _gl
    if doc["opening_balance"]:
        await _gl.preflight_posting(doc["entity_id"], now_iso())
    await _tulis_bawaan(doc["entity_id"], doc["id"], doc.get("default_receiving_methods") or [],
                        lambda: db.bank_accounts.insert_one(dict(doc)))
    try:
        je = await _post_opening(doc, doc["opening_balance"], "bank_opening_balance", doc["id"])
    except Exception:
        await db.bank_accounts.delete_one({"id": doc["id"]})  # FN-08 — rekening + jurnal pembukaan satu operasi
        raise
    if je:
        await db.bank_accounts.update_one({"id": doc["id"]}, {"$set": {"opening_je_id": je["id"]}})
        doc["opening_je_id"] = je["id"]
    return _enrich(safe_doc(doc), [])


OPENING_EQUITY_ACC = "3-2900"


async def _post_opening(acc: Dict[str, Any], amount: float, source_type: str, source_id: str):
    """FN-08 — saldo awal rekening terikat GL: Dr Kas/Bank ↔ Cr Ekuitas Saldo Awal (tanda dibalik bila negatif)."""
    from services import gl_service as _gl
    amt = round(float(amount or 0), 2)
    if abs(amt) <= 0.005:
        return None
    cash_acc = "1-1110" if acc.get("account_type") == "cash" else "1-1100"
    dr, cr = (cash_acc, OPENING_EQUITY_ACC) if amt > 0 else (OPENING_EQUITY_ACC, cash_acc)
    await _gl.seed_default_coa()
    return await _gl._insert_entry(
        lines=[{"account_code": dr, "debit": abs(amt), "credit": 0.0, "description": f"Saldo awal {acc['name']}"},
               {"account_code": cr, "debit": 0.0, "credit": abs(amt), "description": f"Saldo awal {acc['name']}"}],
        description=f"Saldo awal rekening {acc['name']}", date=now_iso(), source_type=source_type,
        source_id=source_id, entity_id=acc.get("entity_id") or DEFAULT_ENTITY_ID, created_by="system",
        source_label=acc["name"])


class RekeningBerubah(ValueError):
    """PM-T1 — nilai yang diajukan sudah tidak sama dengan isi rekening sekarang (409)."""


async def update_account(account_id: str, patch: Dict[str, Any],
                         syarat: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """`syarat` (PM-T1) = nilai lama yang harus masih tersimpan (persetujuan perubahan) — beda → `RekeningBerubah`."""
    acc = await db.bank_accounts.find_one({"id": account_id, **(syarat or {})}, {"_id": 0})
    if not acc:
        if syarat and await db.bank_accounts.find_one({"id": account_id}, {"_id": 0, "id": 1}):
            raise RekeningBerubah("Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang.")
        return None
    upd = {k: v for k, v in patch.items() if v is not None}
    if "opening_balance" in upd:
        upd["opening_balance"] = round(float(upd["opening_balance"]), 2)
        delta = round(upd["opening_balance"] - float(acc.get("opening_balance") or 0), 2)
        if abs(delta) > 0.005:
            # FN-08 — saldo awal terkunci pada jurnal; koreksi = jurnal penyesuaian selisih (bukan edit diam-diam).
            if not acc.get("opening_je_id") and float(acc.get("opening_balance") or 0):
                raise ValueError("Saldo awal lama rekening ini belum terjurnal — koreksi lewat jurnal manual "
                                 "(Dr/Cr Kas-Bank ↔ 3-2900) oleh Keuangan, bukan edit saldo awal.")
            from services import gl_service as _gl
            await _gl.preflight_posting(acc.get("entity_id") or DEFAULT_ENTITY_ID, now_iso())
            n = await db.journal_entries.count_documents({"source_type": "bank_opening_adjustment",
                                                          "source_id": {"$regex": f"^{account_id}:"}})
            je = await _post_opening({**acc, **upd}, delta, "bank_opening_adjustment", f"{account_id}:{n + 1}")
            if not acc.get("opening_je_id") and je:
                upd["opening_je_id"] = je["id"]
        else:
            upd.pop("opening_balance")
    if "name" in upd:
        upd["name"] = str(upd["name"]).strip()
    upd["updated_at"] = now_iso()
    flt = {"id": account_id, **(syarat or {})}

    async def _tulis():
        res = await db.bank_accounts.update_one(flt, {"$set": upd})
        if syarat and not res.matched_count:
            raise RekeningBerubah("Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang.")
        return res
    await _tulis_bawaan(acc.get("entity_id") or "", account_id, upd.get("default_receiving_methods") or [], _tulis)
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    txns = await _txns_for(account_id)
    return {**_enrich(acc, txns), **bidang_efektif(acc)}


async def account_ledger(account_id: str) -> Optional[Dict[str, Any]]:
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    if not acc:
        return None
    txns = await _txns_for(account_id)
    # running balance (kronologis menaik)
    chron = sorted(txns, key=lambda t: (t.get("txn_date") or "", t.get("number") or ""))
    running = float(acc.get("opening_balance", 0) or 0)
    for t in chron:
        amt = float(t.get("amount", 0) or 0)
        running += amt if t.get("direction") == "in" else -amt
        t["running_balance"] = round(running, 2)
        # PK-21 — lencana layar (Terekonsiliasi / Sebagian / Belum) membaca turunan dari `reconciled_amount`; tanda
        # manual lama yang masih tersimpan tidak ditampilkan sebagai "terekonsiliasi".
        t["reconciled"] = txn_reconciled(t)
        t["reconciled_amount"] = round(float(t.get("reconciled_amount") or 0), 2)
    chron.reverse()  # tampilkan terbaru dulu
    return {**_enrich(acc, txns), "transactions": chron}
