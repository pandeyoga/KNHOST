"""R6.2 — Fixed Assets & Depresiasi (straight-line) + disposal gain/loss.

Koleksi:
- `fin_fixed_assets`       (prefix `fasset_`, number `FA-#####` per entitas) — master aset.
- `fin_depreciation_entries` (prefix `depe_`) — histori penyusutan per (asset, period).

Prinsip:
- Straight-line: penyusutan bulanan = (harga_perolehan − nilai_residu) / masa_manfaat_bulan; bulan terakhir umur
  mengambil SELURUH sisa (PK-23 · FY-20) sehingga Σ penyusutan = nilai yang disusutkan.
- Idempotent per (asset_id, period): rerun run_depreciation tidak menduplikasi.
- GL: Dr 6-6000 Beban Penyusutan / Cr 1-2900 Akumulasi Penyusutan (via gl_service.post_depreciation).
- Disposal: hitung book_value & gain/loss (proceeds − book_value), post JE self-balancing
  (via gl_service.post_asset_disposal). Aset → status 'disposed' (append-only, tak dihapus).

PK-23 (FY-01, FY-03, FY-05, FY-20; `02_STANDAR.md` §1) — tiap aksi berurutan PERIKSA (tanpa tulisan) → NIAT → EFEK →
JURNAL tahan-gagal (`gl_service.post_durable`):
- Perolehan: sumber dana wajib (`kas` · `hutang` · `saldo_awal`; `antar_pt` hanya dari pindah aset), akun kredit
  DITURUNKAN dari sumber dana (bukan isian klien), akun aset harus akun aset tetap aktif PT, periode diperiksa dulu;
  sumber `kas` → kas keluar lewat pembuat kas satu pintu (`cash_ledger.create_cash`, PK-20).
- Aset `transferred`/sedang diproses/belum berjurnal tidak bisa diubah, disusutkan, dilepas, atau dipindah.
- Entri penyusutan lahir `pending`; register baru diperbarui sesudah jurnalnya terbit (jenis `asset_depreciation`).
- Pelepasan berklaim (`disposing`); jurnal gagal → status dikembalikan, galat 409.
- Pindah antar-PT dan pembayarannya: `services/fixed_asset_transfer_service.py`.
"""
import hashlib
from datetime import datetime as _dt, timedelta as _td, timezone as _tz
from typing import Any, Dict, List, Optional

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc, DEFAULT_ENTITY_ID
from services import gl_service
from services.book_date import tanggal_buku

EPS = 0.01

# Kategori aset → akun GL aset default (boleh dioverride saat create).
CATEGORY_ACCOUNT = {
    "Peralatan & Mesin": "1-2100",
    "Kendaraan": "1-2200",
    "Inventaris & Perabot Kantor": "1-2300",
    "Bangunan": "1-2400",
}
DEFAULT_ASSET_ACC = "1-2100"
ASSET_CATEGORIES = list(CATEGORY_ACCOUNT.keys())

# ── PK-23 — sumber dana perolehan (FY-03) ───────────────────────────────────────────────────────────────────────────
#: Urutan = urutan pilihan di form. `antar_pt` tidak ditawarkan di form: hanya diisi fungsi pindah aset.
FUNDING_SOURCES = ("kas", "hutang", "saldo_awal", "antar_pt")
FUNDING_LABEL = {"kas": "Dibayar dari kas/bank", "hutang": "Dibeli secara hutang",
                 "saldo_awal": "Saldo awal (aset lama)", "antar_pt": "Pindah antar-PT"}
#: Sumber dana yang akun lawannya dari Pemetaan Akun (kunci `remap=False`) — hidup hanya bila pemetaannya DISIMPAN.
FUNDING_KEY = {"hutang": "aset.sumber_hutang", "saldo_awal": "aset.sumber_saldo_awal"}
FUNDING_NOT_MAPPED = "Akun lawannya belum ditetapkan di Pemetaan Akun."

#: Status antara (klaim) dan status akhir yang menutup aksi lain atas aset.
BUSY_STATUSES = ("transferring", "disposing")
CLOSED_STATUSES = ("disposed", "transferred") + BUSY_STATUSES
#: Klaim yang macet lebih lama dari ini (proses mati di tengah) boleh diambil alih — batas teknis, sama dengan
#: klaim penyusutan G3 D4-ASSET-01; bukan aturan bisnis.
STALE_MINUTES = 10


class AssetError(ValueError):
    """PK-23 — penolakan berkode HTTP (router: `status_code`), pesan siap tampil."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.status_code = status_code


def _stale_iso() -> str:
    return (_dt.now(_tz.utc) - _td(minutes=STALE_MINUTES)).isoformat()


async def _entity_name(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                "name": 1}) or {}
    return e.get("short_name") or e.get("legal_name") or e.get("name") or entity_id or "PT ini"


def _label(a: Dict[str, Any]) -> str:
    return f"{a.get('number', '')} {a.get('name', '')}".strip()


async def _preflight_period(entity_id: str, date: str) -> None:
    """Periode buku PT pada tanggal itu harus terbuka (P2) — sebelum tulisan apa pun. Pesan menyebut PT-nya."""
    try:
        await gl_service.preflight_posting(entity_id, date)
    except gl_service.ClosedPeriodError as exc:
        raise AssetError(f"{await _entity_name(entity_id)}: {exc}", 409) from exc


async def asset_accounts(entity_id: Optional[str]) -> List[Dict[str, str]]:
    """Akun aset tetap yang boleh dipakai PT: anak 1-2000 yang aktif dan boleh diposting, bukan akumulasi penyusutan
    (bawaan maupun hasil pemetaan `aset.akumulasi_penyusutan`). Satu sumber untuk form (meta) dan PERIKSA."""
    from services import gl_mapping_service as glm
    await gl_service.seed_default_coa()
    eid = entity_id if entity_id and entity_id != "all" else None
    akumulasi = {gl_service.ACC_FA_ACCUM_DEP, await glm.account_for("aset.akumulasi_penyusutan", eid)}
    accs = await gl_service.effective_accounts(None, eid)
    out = [{"code": c, "name": a.get("name", "")} for c, a in accs.items()
           if c.startswith("1-2") and a.get("is_postable") and a.get("is_active") is not False and c not in akumulasi]
    return sorted(out, key=lambda x: x["code"])


async def _check_asset_account(entity_id: str, code: str) -> None:
    if code not in {a["code"] for a in await asset_accounts(entity_id)}:
        raise AssetError(f"Akun {code} bukan akun aset tetap yang aktif.", 400)


async def funding_options(entity_id: Optional[str]) -> List[Dict[str, Any]]:
    """Pilihan sumber dana form Tambah Aset untuk PT itu: `available` + `reason` (pilihan mati wajib beralasan)."""
    from services import gl_mapping_service as glm
    eid = entity_id if entity_id and entity_id != "all" else None
    out: List[Dict[str, Any]] = []
    for src in ("kas", "hutang", "saldo_awal"):
        row: Dict[str, Any] = {"value": src, "label": FUNDING_LABEL[src], "available": True, "reason": "",
                               "account_code": ""}
        if src in FUNDING_KEY:
            r = await glm.resolve(FUNDING_KEY[src], eid)
            row["available"] = r["source"] in ("entity", "global")
            row["reason"] = "" if row["available"] else FUNDING_NOT_MAPPED
            row["account_code"] = r["account_code"] if row["available"] else ""
        out.append(row)
    return out


async def _resolve_funding(entity_id: str, source: str, account_id: str) -> Dict[str, Any]:
    """Sumber dana → akun kredit perolehan (+ rekening untuk `kas`). Tanpa tulisan. `antar_pt` tidak diterima di sini:
    aset pengganti pindah antar-PT dibuat `fixed_asset_transfer_service` (jurnalnya sisi penerima jurnal kembar)."""
    from services import cash_ledger, gl_mapping_service as glm
    source = (source or "").strip()
    if not source:
        raise AssetError("Pilih sumber dana perolehan aset.", 400)
    if source not in FUNDING_SOURCES:
        raise AssetError("Sumber dana tidak dikenal. Pilih kas/bank, hutang, atau saldo awal.", 400)
    if source == "antar_pt":
        raise AssetError("Sumber dana antar-PT hanya terbentuk dari Pindah PT.", 400)
    if source in FUNDING_KEY:
        r = await glm.resolve(FUNDING_KEY[source], entity_id)
        if r["source"] not in ("entity", "global"):
            raise AssetError(f'Sumber dana "{FUNDING_LABEL[source]}" belum bisa dipakai karena akun lawannya belum '
                             f"ditetapkan di Pemetaan Akun.", 409)
        return {"funding_account": r["account_code"], "account_id": "", "cash_type": ""}
    # kas: rekening aktif milik PT; kosong → satu-satunya rekening aktif PT (jenis apa pun)
    acc_id = (account_id or "").strip()
    if not acc_id:
        from services.bank_service import _aktif
        aktif = [a async for a in db.bank_accounts.find({"entity_id": entity_id}, {"_id": 0, "id": 1, "is_active": 1,
                                                                                    "status": 1}) if _aktif(a)]
        if len(aktif) == 1:
            acc_id = aktif[0]["id"]
    rek = await cash_ledger.periksa_rekening(entity_id, acc_id, "")   # CashRejected 409 bila tidak bisa ditentukan
    # Akun kas mengikuti jenis rekening (1-1100 Bank / 1-1110 Kas Kecil); jurnal memetakannya lewat
    # `kas_bank.kas_besar` / `kas_bank.kas_kecil` (gl_mapping_service.remap_lines) seperti jurnal kas lain.
    return {"funding_account": rek["account_code"], "account_id": rek["account_id"], "cash_type": rek["cash_type"]}


async def acquisition_posted(a: Dict[str, Any]) -> bool:
    """Jurnal perolehan sudah ada? Aset lama tanpa `gl_status` dianggap berjurnal bila jurnal perolehannya ada."""
    st = a.get("gl_status")
    if st in ("posted", "not_required"):
        return True
    if st:
        return False
    return bool(await db.journal_entries.find_one(
        {"source_type": "fixed_asset_acquisition", "source_id": a.get("id"), "status": {"$ne": "void"}},
        {"_id": 0, "id": 1}))


async def _assert_usable(a: Dict[str, Any]) -> None:
    """FY-01/FY-05 — aset yang sudah pindah, sedang diproses, atau belum berjurnal tidak bisa diubah/disusutkan/
    dilepas/dipindah."""
    nomor = a.get("number") or a.get("id")
    if a.get("status") == "transferred":
        tr = a.get("transfer") or {}
        nama = tr.get("to_entity_name") or await _entity_name(tr.get("to_entity_id", ""))
        raise AssetError(f"Aset {nomor} sudah dipindahkan ke {nama}, jadi tidak bisa diubah, disusutkan, atau "
                         f"dilepas di sini.")
    if a.get("status") in BUSY_STATUSES:
        raise AssetError(f"Aset {nomor} sedang diproses. Muat ulang.")
    if not await acquisition_posted(a):
        raise AssetError(f"Aset {nomor} belum punya jurnal perolehan. Ulangi posting di Posting Gagal dulu.")


async def _open_depreciation(asset_id: str, exclude_period: str = "") -> Optional[Dict[str, Any]]:
    """Entri penyusutan yang jurnalnya belum terbit (pending/failed) — menahan periode berikutnya, lepas, dan pindah."""
    q: Dict[str, Any] = {"asset_id": asset_id, "gl_status": {"$in": ["pending", "failed"]}}
    if exclude_period:
        q["period"] = {"$ne": exclude_period}
    return await db.fin_depreciation_entries.find_one(q, {"_id": 0, "id": 1, "period": 1}, sort=[("period", 1)])


async def _assert_no_open_depreciation(a: Dict[str, Any]) -> None:
    e = await _open_depreciation(a["id"])
    if e:
        raise AssetError(f"Aset {a.get('number') or a['id']} punya penyusutan {e['period']} yang belum berjurnal. "
                         f"Ulangi posting di Posting Gagal dulu.")


# ── Helpers periode (YYYY-MM) ────────────────────────────────────────────────
def _period_of(date_str: str) -> str:
    """Periode buku WIB. Dulu `(… or now_iso())[:7]`: tanggal perolehan berstempel UTC / kosong pukul 00.00–07.00 WIB
    tanggal 1 memulai penyusutan sebulan lebih awal."""
    try:
        return tanggal_buku(date_str or None)[:7]
    except ValueError:
        return str(date_str)[:7]


def _add_months(period: str, n: int) -> str:
    y, m = int(period[:4]), int(period[5:7])
    idx = (y * 12 + (m - 1)) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def _monthly_amount(cost: float, salvage: float, life: int) -> float:
    depreciable = max(round(float(cost or 0) - float(salvage or 0), 2), 0.0)
    if life <= 0:
        return 0.0
    return round(depreciable / life, 2)


def _period_amount(remaining: float, monthly: float, months_done: int, life: int) -> float:
    """PK-23 (FY-20) — nominal satu periode: bulan terakhir umur (`months_done == life − 1`) = SELURUH sisa (sisa
    pembulatan ikut habis); selain itu bulanan, atau sisa bila sisa ≤ bulanan."""
    if life > 0 and months_done >= life - 1:
        amt = remaining
    else:
        amt = monthly if remaining > monthly + EPS else remaining
    return round(max(amt, 0.0), 2)


def _recompute(asset: Dict[str, Any]) -> Dict[str, Any]:
    """Derive book_value & status dari accumulated (dipakai saat create/patch). PK-23 (FY-05) — status akhir/antara
    (`disposed`, `transferred`, `transferring`, `disposing`) tidak pernah dikembalikan ke `active`."""
    cost = round(float(asset.get("acquisition_cost", 0) or 0), 2)
    acc = round(float(asset.get("accumulated_depreciation", 0) or 0), 2)
    salvage = round(float(asset.get("salvage_value", 0) or 0), 2)
    depreciable = max(round(cost - salvage, 2), 0.0)
    asset["book_value"] = round(cost - acc, 2)
    if asset.get("status") not in CLOSED_STATUSES:
        asset["status"] = "fully_depreciated" if acc >= depreciable - EPS and depreciable > 0 else "active"
    return asset


# ── CRUD ─────────────────────────────────────────────────────────────────────
async def list_assets(scope: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    q = dict(scope or {})
    rows = await db.fin_fixed_assets.find(q, {"_id": 0}).sort("created_at", -1).to_list(5000)
    return [safe_doc(r) for r in rows]


async def get_asset(asset_id: str) -> Optional[Dict[str, Any]]:
    a = await db.fin_fixed_assets.find_one({"id": asset_id}, {"_id": 0})
    if not a:
        return None
    entries = await db.fin_depreciation_entries.find(
        {"asset_id": asset_id}, {"_id": 0}).sort("period", 1).to_list(2000)
    a["depreciation_entries"] = [safe_doc(e) for e in entries]
    a["schedule"] = depreciation_schedule(a, entries)
    return safe_doc(a)


def asset_id_for(entity_id: str, idem_key: str) -> str:
    """Id tetap aset dari kunci idempotensi (`02` §1 langkah 2): kirim ulang = aset yang sama, diteruskan."""
    return "fasset_" + hashlib.sha1(f"{entity_id}|{idem_key}".encode("utf-8")).hexdigest()[:24]


async def create_asset(payload: Dict[str, Any], actor: Dict[str, Any], *, entity_id: Optional[str] = None,
                       idem_key: str = "") -> Dict[str, Any]:
    """PK-23 (FY-01, FY-03) — perolehan aset: PERIKSA → NIAT (`gl_status: pending`) → EFEK (kas, sumber `kas`) →
    JURNAL (`post_durable`). `entity_id` = PT hasil `resolve_requested_entity` (router), bukan isi permintaan;
    `funding_account` klien diabaikan."""
    # ── 1. PERIKSA (tanpa tulisan) ─────────────────────────────────────────────────────────────────────────────────
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValueError("Nama aset wajib diisi.")
    cost = round(float(payload.get("acquisition_cost", 0) or 0), 2)
    if cost <= 0:
        raise ValueError("Harga perolehan harus > 0.")
    life = int(payload.get("useful_life_months", 0) or 0)
    if life <= 0:
        raise ValueError("Masa manfaat (bulan) harus > 0.")
    salvage = round(float(payload.get("salvage_value", 0) or 0), 2)
    if salvage < 0 or salvage >= cost:
        raise ValueError("Nilai residu harus ≥ 0 dan < harga perolehan.")
    category = (payload.get("category") or "Peralatan & Mesin").strip()
    ent = entity_id or payload.get("entity_id") or DEFAULT_ENTITY_ID
    source = (payload.get("funding_source") or "").strip()
    if not source:
        raise AssetError("Pilih sumber dana perolehan aset.", 400)
    asset_acc = (payload.get("gl_account_asset") or CATEGORY_ACCOUNT.get(category, DEFAULT_ASSET_ACC))
    await _check_asset_account(ent, asset_acc)
    fund = await _resolve_funding(ent, source, payload.get("account_id") or "")
    acq_date = tanggal_buku(payload.get("acquisition_date") or "")
    await _preflight_period(ent, acq_date)
    # ── 2. NIAT ───────────────────────────────────────────────────────────────────────────────────────────────────
    aid = asset_id_for(ent, idem_key) if idem_key else new_id("fasset")
    doc = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0})
    if doc is None:
        number = await next_doc_number("fin_fixed_assets", "number", "FA-", entity_id=ent)
        doc = {
            "id": aid,
            "number": number,
            "name": name,
            "category": category,
            "acquisition_cost": cost,
            "acquisition_date": acq_date,
            "useful_life_months": life,
            "salvage_value": salvage,
            "method": "straight_line",
            "entity_id": ent,
            "gl_account_asset": asset_acc,
            "gl_account_dep_exp": gl_service.ACC_DEP_EXPENSE,
            "gl_account_acc_dep": gl_service.ACC_FA_ACCUM_DEP,
            "funding_source": source,
            "funding_account": fund["funding_account"],   # PK-23 — diturunkan dari sumber dana
            "account_id": fund["account_id"],
            "funding_cash_type": fund["cash_type"],
            "acquisition_cash_txn_id": "",
            "monthly_depreciation": _monthly_amount(cost, salvage, life),
            "accumulated_depreciation": 0.0,
            "book_value": cost,
            "depreciated_months": 0,
            "last_depreciation_period": "",
            "status": "active",
            "acquisition_je": "",
            "gl_status": "pending",   # PK-18 — aset tersimpan, jurnal perolehan belum dicoba
            "gl_error": "",
            "disposal": None,
            "notes": (payload.get("notes") or "").strip(),
            "created_by": actor.get("name", "system"),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }
        try:
            await db.fin_fixed_assets.update_one({"id": aid}, {"$setOnInsert": doc}, upsert=True)
        except Exception as exc:  # noqa: BLE001 — balapan sisip id tetap: yang kalah memakai dokumen pemenang
            if "E11000" not in str(exc) and "duplicate key" not in str(exc).lower():
                raise
        doc = await db.fin_fixed_assets.find_one({"id": aid}, {"_id": 0}) or doc
    if doc.get("gl_status") in ("posted", "not_required"):
        return safe_doc(doc)   # kirim ulang sesudah selesai = hasil yang sama
    # ── 3. EFEK + 4. JURNAL ───────────────────────────────────────────────────────────────────────────────────────
    doc.update(await complete_acquisition(doc, actor))
    return safe_doc(doc)


async def _ensure_acquisition_cash(asset: Dict[str, Any], actor_name: str = "system") -> Optional[Dict[str, Any]]:
    """EFEK sumber `kas`: kas keluar SATU kali (id tetap dari rujukan `fixed_asset` · id aset) lewat pembuat kas PK-20.
    Jurnalnya milik dokumen induk (perolehan) → kas `not_required`."""
    if asset.get("funding_source") != "kas":
        return None
    from services import cash_ledger
    txn = await cash_ledger.create_cash(
        entity_id=asset.get("entity_id") or DEFAULT_ENTITY_ID, direction="out",
        amount=float(asset.get("acquisition_cost") or 0), ref_type="fixed_asset", ref_id=asset["id"],
        account_id=asset.get("account_id") or "", cash_type=asset.get("funding_cash_type") or "",
        txn_date=asset.get("acquisition_date") or "", category="aset tetap",
        description=f"Perolehan aset tetap {_label(asset)}", actor=actor_name or "system",
        contra_account_code=asset.get("gl_account_asset") or "",
        journal_by_parent=f"fixed_asset_acquisition:{asset['id']}")
    if txn.get("id") and asset.get("acquisition_cash_txn_id") != txn["id"]:
        await db.fin_fixed_assets.update_one({"id": asset["id"]}, {"$set": {"acquisition_cash_txn_id": txn["id"]}})
        asset["acquisition_cash_txn_id"] = txn["id"]
    return txn


async def complete_acquisition(asset: Dict[str, Any], actor: Optional[Dict[str, Any]] = None, *,
                               raise_on_fail: bool = False) -> Dict[str, Any]:
    """EFEK + JURNAL perolehan, idempoten (dipakai simpan aset DAN Ulang Posting). Kas gagal tercatat → aset `failed`
    dengan galatnya (bisa diulang dari panel)."""
    upd: Dict[str, Any] = {}
    try:
        await _ensure_acquisition_cash(asset, (actor or {}).get("name", "system"))
    except Exception as exc:  # noqa: BLE001 — aset sudah tersimpan: kegagalan kas dicatat, bukan ditelan
        pesan = getattr(exc, "detail", None) or str(exc) or exc.__class__.__name__
        upd = {"gl_status": "failed", "gl_error": f"Kas perolehan belum tercatat: {pesan}"[:300],
               "gl_failed_at": now_iso()}
        await db.fin_fixed_assets.update_one({"id": asset["id"]}, {"$set": {**upd, "updated_at": now_iso()}})
        if raise_on_fail:
            raise
        upd["acquisition_cash_txn_id"] = asset.get("acquisition_cash_txn_id", "")
        return upd
    upd = await post_acquisition_gl(asset, raise_on_fail=raise_on_fail)
    upd["acquisition_cash_txn_id"] = asset.get("acquisition_cash_txn_id", "")
    return upd


async def post_acquisition_gl(asset: Dict[str, Any], *, raise_on_fail: bool = False) -> Dict[str, Any]:
    """Posting perolehan → GL (Dr aset / Cr sumber dana), idempoten. PK-18 (GL-02) — lewat pintu tahan-gagal: jurnal
    gagal tercatat di `gl_status` aset. Akun dan tanggal dari yang tersimpan di aset. PK-23 — akun lawan sumber
    `hutang`/`saldo_awal` dipakai apa adanya (tidak dialihkan pemetaan lain); aset lama tanpa sumber dana = kas."""
    fixed = asset.get("funding_source") in FUNDING_KEY
    jr = await gl_service.post_durable(
        "fin_fixed_assets", asset["id"],
        lambda: gl_service.post_asset_acquisition(
            asset_id=asset["id"], entity_id=asset.get("entity_id") or DEFAULT_ENTITY_ID,
            amount=float(asset.get("acquisition_cost") or 0), asset_acc=asset.get("gl_account_asset") or DEFAULT_ASSET_ACC,
            funding_acc=asset.get("funding_account") or gl_service.ACC_KAS_BESAR, funding_fixed=fixed,
            label=_label(asset), date=asset.get("acquisition_date") or ""),
        source_type="fixed_asset_acquisition", source_id=asset["id"], raise_on_fail=raise_on_fail)
    upd = {"gl_status": jr["gl_status"], "gl_error": jr["gl_error"], "journal_entry_id": jr["journal_entry_id"]}
    if jr["journal_entry_id"]:
        je = await db.journal_entries.find_one({"id": jr["journal_entry_id"]}, {"_id": 0, "number": 1}) or {}
        upd["acquisition_je"] = je.get("number", "")
        await db.fin_fixed_assets.update_one({"id": asset["id"]}, {"$set": {"acquisition_je": upd["acquisition_je"]}})
        if asset.get("acquisition_cash_txn_id"):   # tautan kas perolehan → jurnal induknya (`02` L8)
            await db.cash_transactions.update_one(
                {"id": asset["acquisition_cash_txn_id"], "journal_entry_id": {"$in": ["", None]}},
                {"$set": {"journal_entry_id": jr["journal_entry_id"]}})
    return upd


async def retry_acquisition(asset: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """Jalur Ulang Posting jenis `fixed_asset` (registri posting). Aset pengganti pindah antar-PT yang jurnal sisi
    penerimanya gagal → niat pindah aset asalnya diteruskan (dua buku sekaligus, `fixed_asset_transfer_service`)."""
    if asset.get("funding_source") == "antar_pt" and (asset.get("transfer_from") or {}).get("asset_id"):
        from services.fixed_asset_transfer_service import resume_transfer
        await resume_transfer(asset, actor)
        return
    await complete_acquisition(asset, actor, raise_on_fail=True)


async def update_asset(asset_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    a = await db.fin_fixed_assets.find_one({"id": asset_id}, {"_id": 0})
    if not a:
        return None
    if a.get("status") == "disposed":
        raise ValueError("Aset sudah dilepas (disposed) — tidak bisa diubah.")
    await _assert_usable(a)   # PK-23 (FY-05) — sudah pindah / sedang diproses / belum berjurnal
    status_lama = a.get("status")
    allowed = {"name", "category", "notes"}
    upd: Dict[str, Any] = {k: patch[k] for k in allowed if k in patch and patch[k] is not None}
    # FN-12 — field finansial terkunci setelah kapitalisasi (jurnal perolehan ada): ubah lewat
    # reversal/amendment, bukan edit master yang membuat register ≠ GL.
    capitalized = bool(await db.journal_entries.find_one(
        {"source_type": "fixed_asset_acquisition", "source_id": asset_id, "status": {"$ne": "void"}},
        {"_id": 0, "id": 1}))
    locked_fin = ("acquisition_cost", "acquisition_date", "gl_account_asset")
    changed = [k for k in locked_fin if patch.get(k) is not None and patch.get(k) != a.get(k)]
    if capitalized and changed:
        raise ValueError(f"Aset sudah dikapitalisasi (jurnal perolehan terposting) — {', '.join(changed)} "
                         "tidak bisa diedit. Batalkan/koreksi jurnal perolehan lewat Keuangan.")
    if patch.get("gl_account_asset") is not None:
        if patch["gl_account_asset"] != a.get("gl_account_asset"):   # PK-23 (FY-03) — akun aset diperiksa
            await _check_asset_account(a.get("entity_id") or DEFAULT_ENTITY_ID, patch["gl_account_asset"])
        upd["gl_account_asset"] = patch["gl_account_asset"]
    # Ubah parameter penyusutan hanya bila belum ada penyusutan terposting.
    if a.get("depreciated_months", 0) == 0:
        for k in ("acquisition_cost", "useful_life_months", "salvage_value", "acquisition_date"):
            if patch.get(k) is not None:
                upd[k] = patch[k]
    elif any(patch.get(k) is not None and patch.get(k) != a.get(k)
             for k in ("useful_life_months", "salvage_value")):
        raise ValueError("Penyusutan sudah terposting — umur/nilai sisa tidak bisa diubah langsung.")
    if not upd:
        return safe_doc(a)
    a.update(upd)
    a["monthly_depreciation"] = _monthly_amount(
        a.get("acquisition_cost", 0), a.get("salvage_value", 0), int(a.get("useful_life_months", 0) or 0))
    _recompute(a)
    a["updated_at"] = now_iso()
    fields = {k: a[k] for k in (*upd.keys(), "monthly_depreciation", "book_value", "status", "updated_at")}
    # PK-23 (FY-05) — tulisan bersyarat status yang dibaca: klaim pindah/lepas di antaranya tidak tertimpa.
    res = await db.fin_fixed_assets.update_one({"id": asset_id, "status": status_lama}, {"$set": fields})
    if not res.matched_count:
        raise AssetError(f"Aset {a.get('number') or asset_id} sedang diproses. Muat ulang.")
    return safe_doc(a)


# ── Jadwal penyusutan (preview straight-line) ────────────────────────────────
def depreciation_schedule(asset: Dict[str, Any],
                          entries: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    cost = round(float(asset.get("acquisition_cost", 0) or 0), 2)
    salvage = round(float(asset.get("salvage_value", 0) or 0), 2)
    life = int(asset.get("useful_life_months", 0) or 0)
    start = _period_of(asset.get("acquisition_date", ""))
    monthly = _monthly_amount(cost, salvage, life)
    posted = {e["period"]: e for e in (entries or [])}
    out: List[Dict[str, Any]] = []
    acc = 0.0
    depreciable = max(round(cost - salvage, 2), 0.0)
    for i in range(life):
        period = _add_months(start, i)
        remaining = round(depreciable - acc, 2)
        amt = _period_amount(remaining, monthly, i, life)   # PK-23 (FY-20) — bulan terakhir = seluruh sisa
        acc = round(acc + amt, 2)
        e = posted.get(period) or {}
        out.append({
            "period": period,
            "amount": amt,
            "accumulated": acc,
            "book_value": round(cost - acc, 2),
            # PK-23 — "terposting" hanya bila jurnalnya terbit (entri lama tanpa penanda = terbit)
            "posted": bool(e) and e.get("gl_status") in (None, "", "posted", "not_required"),
            "gl_status": e.get("gl_status") or ("posted" if e else ""),
        })
    return out


# ── Jalankan penyusutan periode (idempotent per asset+period) ────────────────
def _skip_reason(a: Dict[str, Any]) -> str:
    st = a.get("status")
    if st == "transferred":
        return f"sudah dipindahkan ke {(a.get('transfer') or {}).get('to_entity_name') or 'PT lain'}"
    if st == "disposed":
        return "sudah dilepas"
    if st in BUSY_STATUSES:
        return "sedang diproses"
    if st == "fully_depreciated":
        return "sudah habis disusutkan"
    return ""


async def _post_dep_entry(a: Dict[str, Any], entry: Dict[str, Any], *, raise_on_fail: bool = False) -> Dict[str, Any]:
    """JURNAL satu entri penyusutan lewat pintu tahan-gagal; register aset diperbarui HANYA bila jurnalnya terbit."""
    aid, period, amt = a["id"], entry["period"], round(float(entry.get("amount") or 0), 2)
    jr = await gl_service.post_durable(
        "fin_depreciation_entries", entry["id"],
        lambda: gl_service.post_depreciation(
            asset_id=aid, period=period, entity_id=a.get("entity_id", ""), amount=amt, asset_label=_label(a),
            dep_exp_acc=a.get("gl_account_dep_exp", gl_service.ACC_DEP_EXPENSE),
            acc_dep_acc=a.get("gl_account_acc_dep", gl_service.ACC_FA_ACCUM_DEP),
            date=entry.get("journal_date") or ""),   # PK-22 (FY-02) — tanggal buku periodik yang dicatat di entri
        source_type="fixed_asset_depreciation", source_id=f"{aid}:{period}", raise_on_fail=raise_on_fail)
    if jr["gl_status"] != "posted":
        return {"status": jr["gl_status"], "error": jr["gl_error"]}
    je = await db.journal_entries.find_one({"id": jr["journal_entry_id"]}, {"_id": 0, "id": 1, "number": 1}) or {}
    await db.fin_depreciation_entries.update_one({"id": entry["id"]}, {"$set": {
        "je_id": je.get("id", ""), "je_number": je.get("number", "")}})
    cost = round(float(a.get("acquisition_cost", 0) or 0), 2)
    salvage = round(float(a.get("salvage_value", 0) or 0), 2)
    life = int(a.get("useful_life_months", 0) or 0)
    fresh = await _apply_dep_to_register(a, period, amt, max(round(cost - salvage, 2), 0.0), life)
    return {"status": "posted", "error": "", "fresh": fresh, "amount": amt}


async def repost_depreciation_entry(entry: Dict[str, Any], actor: Optional[Dict[str, Any]] = None) -> None:
    """Jalur Ulang Posting jenis `asset_depreciation`: jurnal entri yang gagal, lalu register diperbarui."""
    a = await db.fin_fixed_assets.find_one({"id": entry.get("asset_id")}, {"_id": 0})
    if not a:
        raise RuntimeError("Aset entri penyusutan ini tidak ditemukan.")
    if a.get("status") in ("transferred", "disposed"):
        raise RuntimeError(f"Aset {a.get('number', '')} {_skip_reason(a)}; penyusutan ini tidak bisa diterbitkan "
                           "lagi. Koreksi lewat jurnal.")
    await _post_dep_entry(a, entry, raise_on_fail=True)


async def run_depreciation(period: str, actor: Dict[str, Any],
                           asset_id: Optional[str] = None,
                           scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """PK-23 — entri lahir `pending`, jurnal lewat `post_durable`, register sesudah `posted`. Aset yang belum
    berjurnal / sudah pindah / punya penyusutan sebelumnya yang belum berjurnal dilewati beserta alasannya
    (`skipped_assets`); jurnal gagal satu aset tidak menghentikan aset lain (`failed`)."""
    period = (period or tanggal_buku())[:7]
    from services import periodic_posting
    periodic_posting.assert_period_started(period)   # PK-22 (FY-02) — periode depan ditolak
    q: Dict[str, Any] = dict(scope or {})
    if asset_id:
        q["id"] = asset_id   # aset tertentu: status apa pun dibaca supaya alasan lewatnya bisa dilaporkan
    else:
        q["status"] = "active"
    assets = await db.fin_fixed_assets.find(q, {"_id": 0}).to_list(5000)
    # PK-22 (FY-02, K-13) — tanggal buku per PT (hari terakhir periode, atau hari ini menurut
    # `gl.tanggal_jurnal_periodik`); periode tertutup ditolak SEBELUM aset mana pun diklaim (`02` §1 P2).
    tgl_pt: Dict[str, str] = {}
    for eid in sorted({a.get("entity_id", "") for a in assets if a.get("status") == "active"}):
        tgl_pt[eid] = await periodic_posting.journal_date(eid, period)
        await gl_service.preflight_posting(eid, tgl_pt[eid])
    posted: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    skipped_assets: List[Dict[str, Any]] = []
    skipped = 0
    total = 0.0

    def lewati(a: Dict[str, Any], alasan: str = "") -> None:
        nonlocal skipped
        skipped += 1
        if alasan:
            skipped_assets.append({"asset_id": a["id"], "number": a.get("number", ""), "reason": alasan})

    for a in assets:
        if a.get("status") != "active":
            lewati(a, _skip_reason(a))
            continue
        start = _period_of(a.get("acquisition_date", ""))
        if period < start:  # belum mulai disusutkan
            lewati(a)
            continue
        if not await acquisition_posted(a):   # PK-23 (FY-01) — aset tanpa jurnal perolehan tidak disusutkan
            lewati(a, "belum berjurnal perolehan — ulangi posting di Posting Gagal dulu")
            continue
        cost = round(float(a.get("acquisition_cost", 0) or 0), 2)
        salvage = round(float(a.get("salvage_value", 0) or 0), 2)
        life = int(a.get("useful_life_months", 0) or 0)
        acc = round(float(a.get("accumulated_depreciation", 0) or 0), 2)
        depreciable = max(round(cost - salvage, 2), 0.0)
        remaining = round(depreciable - acc, 2)
        if remaining <= EPS or a.get("depreciated_months", 0) >= life:
            lewati(a)
            continue
        # Idempotent: sudah ada entry utk periode ini? (G3 D4-ASSET-01: entri ada tapi register belum
        # menerapkannya → terapkan sekarang, jangan dilewati selamanya)
        done = await db.fin_depreciation_entries.find_one({"asset_id": a["id"], "period": period}, {"_id": 0})
        if done:
            st = done.get("gl_status")
            if st == "failed" or (st == "pending" and (done.get("created_at") or "") < _stale_iso()):
                res = await _post_dep_entry(a, done)   # PK-23 — jalankan ulang = ulangi jurnal entri yang gagal
                if res["status"] == "posted":
                    fresh = res["fresh"]
                    total = round(total + res["amount"], 2)
                    posted.append({"asset_id": a["id"], "number": a.get("number", ""), "name": a.get("name", ""),
                                   "amount": res["amount"], "accumulated": fresh.get("accumulated_depreciation"),
                                   "book_value": fresh.get("book_value"), "status": fresh.get("status")})
                else:
                    failed.append({"asset_id": a["id"], "number": a.get("number", ""), "error": res["error"]})
                continue
            if st in (None, "", "posted", "not_required") and period not in (a.get("applied_periods") or []) \
                    and float(done.get("amount") or 0) > EPS and a.get("applied_periods") is not None:
                await _apply_dep_to_register(a, period, float(done["amount"]), depreciable, life)
            lewati(a)
            continue
        blocker = await _open_depreciation(a["id"], exclude_period=period)
        if blocker:   # urutan periode dijaga: periode sebelumnya yang belum berjurnal diulang dulu
            lewati(a, f"penyusutan {blocker['period']} belum berjurnal — ulangi di Posting Gagal dulu")
            continue
        # PK-22 (FY-02) — periode harus = periode terakhir disusutkan + 1 bulan (pertama kali: bulan perolehan); periode
        # yang melompat tidak dijurnal, aset masuk `skipped_assets` beserta alasannya.
        harap = _expected_period(a, start)
        if period != harap:
            lewati(a, f"periode melompat — periode berikutnya untuk aset ini {harap}")
            skipped_assets[-1].update({"name": a.get("name", ""), "expected_period": harap})
            continue
        # INV-ATOMIC-01 — CAS per aset; G3 D4-ASSET-01 — klaim macet (>10 menit tanpa entri) boleh diambil alih.
        won = await db.fin_fixed_assets.find_one_and_update(
            {"id": a["id"], "status": a.get("status", "active"),
             "$or": [{"depreciation_periods": {"$ne": period}},
                     {f"depreciation_claims.{period}": {"$lt": _stale_iso()}}]},
            {"$addToSet": {"depreciation_periods": period},
             "$set": {f"depreciation_claims.{period}": now_iso()}},
            projection={"_id": 0, "id": 1})
        if not won:
            lewati(a)
            continue
        monthly = _monthly_amount(cost, salvage, life)
        amt = _period_amount(remaining, monthly, int(a.get("depreciated_months", 0) or 0), life)
        if amt <= EPS:
            lewati(a)
            continue
        new_acc = round(acc + amt, 2)
        eid = f"depe_{a['id']}_{period}"
        await db.fin_depreciation_entries.update_one({"id": eid}, {"$setOnInsert": {
            "id": eid,
            "asset_id": a["id"], "asset_number": a.get("number", ""),
            "entity_id": a.get("entity_id", ""), "period": period, "amount": amt,
            "accumulated_after": new_acc, "book_value_after": round(cost - new_acc, 2),
            "je_id": "", "je_number": "", "journal_date": tgl_pt.get(a.get("entity_id", ""), ""),   # PK-22
            "gl_status": "pending", "gl_error": "", "gl_label": f"{a.get('number', '')} · {period}",
            "created_by": actor.get("name", "system"), "created_at": now_iso(),
        }}, upsert=True)
        entry = await db.fin_depreciation_entries.find_one({"id": eid}, {"_id": 0})
        res = await _post_dep_entry(a, entry)
        if res["status"] != "posted":
            failed.append({"asset_id": a["id"], "number": a.get("number", ""), "error": res["error"]})
            continue
        fresh = res["fresh"]
        total = round(total + res["amount"], 2)
        posted.append({"asset_id": a["id"], "number": a.get("number", ""),
                       "name": a.get("name", ""), "amount": res["amount"],
                       "accumulated": round(float(fresh.get("accumulated_depreciation") or new_acc), 2),
                       "book_value": round(float(fresh.get("book_value") or 0), 2),
                       "status": fresh.get("status", "active")})
    return {"period": period, "posted": len(posted), "skipped": skipped,
            "total_amount": total, "assets": posted, "failed": failed, "skipped_assets": skipped_assets}


def _expected_period(a: Dict[str, Any], start: str) -> str:
    """PK-22 — periode penyusutan berikutnya yang sah: `last_depreciation_period` + 1 bulan; aset lama tanpa field itu
    tetapi sudah disusutkan → bulan perolehan + jumlah bulan tersusut; belum pernah → bulan perolehan."""
    last = str(a.get("last_depreciation_period") or "")[:7]
    if last:
        return _add_months(last, 1)
    n = int(a.get("depreciated_months", 0) or 0)
    return _add_months(start, n) if n > 0 else start


# ── Disposal (gain/loss) ─────────────────────────────────────────────────────
async def _apply_dep_to_register(a: Dict[str, Any], period: str, amt: float, depreciable: float,
                                 life: int) -> Dict[str, Any]:
    """G3 D4-ASSET-01/02 — register diperbarui ATOMIK (pipeline $add) & tepat sekali per periode
    (`applied_periods`), sehingga run Jan/Feb bersamaan tidak saling menimpa akumulasi. PK-23 (FY-05) — status hanya
    berubah `active` → `fully_depreciated`; status lain (mis. klaim pindah) tidak ditimpa."""
    await db.fin_fixed_assets.update_one(
        {"id": a["id"], "applied_periods": {"$ne": period}},
        [{"$set": {"accumulated_depreciation": {"$round": [{"$add": [{"$ifNull": ["$accumulated_depreciation", 0]}, amt]}, 2]},
                   "depreciated_months": {"$add": [{"$ifNull": ["$depreciated_months", 0]}, 1]},
                   "applied_periods": {"$concatArrays": [{"$ifNull": ["$applied_periods", []]}, [period]]},
                   "last_depreciation_period": {"$max": [{"$ifNull": ["$last_depreciation_period", ""]}, period]},
                   "updated_at": now_iso()}},
         {"$set": {"book_value": {"$round": [{"$subtract": [{"$ifNull": ["$acquisition_cost", 0]}, "$accumulated_depreciation"]}, 2]},
                   "status": {"$cond": [{"$and": [{"$eq": ["$status", "active"]},
                                                  {"$or": [{"$gte": ["$accumulated_depreciation", depreciable - EPS]},
                                                           {"$gte": ["$depreciated_months", life]}]}]},
                                         "fully_depreciated", "$status"]}}}])
    return await db.fin_fixed_assets.find_one({"id": a["id"]}, {"_id": 0}) or {}


async def _durable_disposal(a: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
    """JURNAL pelepasan lewat pintu tahan-gagal (status di `disposal_gl_status`); gagal → melempar."""
    cost = round(float(a.get("acquisition_cost", 0) or 0), 2)
    acc = round(float(a.get("accumulated_depreciation", 0) or 0), 2)
    return await gl_service.post_durable(
        "fin_fixed_assets", a["id"],
        lambda: gl_service.post_asset_disposal(
            asset_id=a["id"], entity_id=a.get("entity_id", ""), acquisition_cost=cost,
            accumulated=acc, proceeds=float(intent.get("proceeds") or 0),
            asset_acc=a.get("gl_account_asset", DEFAULT_ASSET_ACC),
            acc_dep_acc=a.get("gl_account_acc_dep", gl_service.ACC_FA_ACCUM_DEP),
            label=_label(a), date=intent.get("date") or ""),
        source_type="fixed_asset_disposal", source_id=a["id"], field="disposal_gl_status", raise_on_fail=True)


async def _finish_disposal(a: Dict[str, Any], intent: Dict[str, Any], jr: Dict[str, Any]) -> Dict[str, Any]:
    cost = round(float(a.get("acquisition_cost", 0) or 0), 2)
    acc = round(float(a.get("accumulated_depreciation", 0) or 0), 2)
    book_value = round(cost - acc, 2)
    proceeds = round(float(intent.get("proceeds") or 0), 2)
    gain_loss = round(proceeds - book_value, 2)
    je = jr.get("journal") or await db.journal_entries.find_one(
        {"source_type": "fixed_asset_disposal", "source_id": a["id"], "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "number": 1}) or {}
    disposal = {
        "date": intent.get("date") or tanggal_buku(), "proceeds": proceeds, "book_value": book_value,
        "gain_loss": gain_loss, "result": "gain" if gain_loss > EPS else ("loss" if gain_loss < -EPS else "impas"),
        "je_id": je.get("id", ""), "je_number": je.get("number", ""),
        "note": intent.get("note") or "", "by": intent.get("by") or "system", "at": now_iso(),
    }
    await db.fin_fixed_assets.update_one({"id": a["id"], "status": "disposing"}, {
        "$set": {"status": "disposed", "disposal": disposal, "updated_at": now_iso()},
        "$unset": {"disposal_intent": ""}})
    a = {**a, "status": "disposed", "disposal": disposal}
    a.pop("disposal_intent", None)
    return safe_doc(a)


async def dispose_asset(asset_id: str, proceeds: float, actor: Dict[str, Any],
                        date: str = "", note: str = "") -> Dict[str, Any]:
    """PK-23 — PERIKSA (status, jurnal perolehan, penyusutan terbuka, periode) → klaim `disposing` bersyarat status
    lama → jurnal `post_asset_disposal` (pintu tahan-gagal) → `disposed`. Jurnal gagal → status dikembalikan, 409."""
    a = await db.fin_fixed_assets.find_one({"id": asset_id}, {"_id": 0})
    if not a:
        raise ValueError("Aset tidak ditemukan.")
    if a.get("status") == "disposed":
        raise ValueError("Aset sudah dilepas (disposed).")
    proceeds = round(float(proceeds or 0), 2)
    if proceeds < 0:
        raise ValueError("Nilai jual/proceeds tidak boleh negatif.")
    status_lama = a.get("status")
    syarat: Dict[str, Any] = {"id": asset_id, "status": status_lama}
    lama = a.get("disposal_intent") or {}
    if status_lama == "disposing" and (lama.get("at") or "") < _stale_iso():
        # klaim lepas yang macet (proses mati sebelum jurnal/pengembalian) diambil alih
        status_lama = lama.get("prev_status") or "active"
        syarat = {"id": asset_id, "status": "disposing", "disposal_intent.at": lama.get("at")}
        a = {**a, "status": status_lama}
    await _assert_usable(a)
    await _assert_no_open_depreciation(a)
    ddate = tanggal_buku(date or "")
    await _preflight_period(a.get("entity_id") or DEFAULT_ENTITY_ID, ddate)
    intent = {"prev_status": status_lama, "proceeds": proceeds, "date": ddate, "note": (note or "").strip(),
              "by": actor.get("name", "system"), "at": now_iso()}
    won = await db.fin_fixed_assets.find_one_and_update(
        syarat, {"$set": {"status": "disposing", "disposal_intent": intent, "disposal_gl_status": "pending",
                          "updated_at": now_iso()}}, projection={"_id": 0, "id": 1})
    if not won:
        raise AssetError(f"Aset {a.get('number') or asset_id} sedang diproses. Muat ulang.")
    try:
        jr = await _durable_disposal(a, intent)
    except Exception as exc:  # noqa: BLE001 — jurnal gagal: pelepasan dibatalkan utuh (status lama kembali)
        await db.fin_fixed_assets.update_one({"id": asset_id, "status": "disposing"}, {
            "$set": {"status": status_lama, "updated_at": now_iso()},
            "$unset": {"disposal_intent": "", "disposal_gl_status": "", "disposal_gl_error": "",
                       "disposal_gl_failed_at": "", "disposal_journal_entry_id": ""}})
        raise AssetError(f"Jurnal pelepasan gagal: {str(exc)[:300]}. Aset tidak dilepas; perbaiki penyebabnya lalu "
                         f"ulangi.", 409) from exc
    return await _finish_disposal(a, intent, jr)


async def resume_disposal(a: Dict[str, Any], actor: Optional[Dict[str, Any]] = None) -> None:
    """Jalur Ulang Posting jenis `fixed_asset_disposal`: pelepasan yang macet di `disposing` dengan jurnal gagal
    (pengembalian status tidak sempat ditulis) diselesaikan dari niat yang tersimpan."""
    intent = a.get("disposal_intent") or {}
    if a.get("status") != "disposing" or not intent:
        raise RuntimeError("Aset ini tidak sedang dilepas.")
    await _finish_disposal(a, intent, await _durable_disposal(a, intent))


# ── Pindah antar-PT: `services/fixed_asset_transfer_service.py` (PK-23 · FY-04) ─────────────────────────────────────


# ── Ringkasan KPI ────────────────────────────────────────────────────────────
async def summary(scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    rows = await db.fin_fixed_assets.find(dict(scope or {}), {"_id": 0}).to_list(5000)
    # FASE E-7 (E7g) — aset yang SUDAH PINDAH ke badan usaha lain BUKAN milik badan usaha
    # ini lagi. Dulu hanya `disposed` yang dikeluarkan, sehingga buku penjual mengaku
    # masih memegang Rp 420 jt aset yang fisik & haknya sudah berpindah (dan nilai buku
    # barisnya sudah 0). Untuk urusan angka, mengaku punya yang tidak dipunya itu cacat.
    gone = {"disposed", "transferred"}
    owned = [r for r in rows if r.get("status") not in gone]
    gross = round(sum(float(r.get("acquisition_cost", 0) or 0) for r in owned), 2)
    accum = round(sum(float(r.get("accumulated_depreciation", 0) or 0) for r in owned), 2)
    net = round(gross - accum, 2)
    disposed = [r for r in rows if r.get("status") == "disposed"]
    transferred = [r for r in rows if r.get("status") == "transferred"]
    disposal_gain = round(sum(float((r.get("disposal") or {}).get("gain_loss", 0) or 0) for r in disposed), 2)
    # Nilai buku saat berpindah + apakah pembayarannya sudah dicatat — supaya layar bisa
    # menagih "utang antar-PT atas aset yang belum dibayar" tanpa menghitung ulang.
    tr_book = round(sum(float((r.get("transfer") or {}).get("book_value", 0) or 0) for r in transferred), 2)
    tr_unsettled = [r for r in transferred if not (r.get("transfer") or {}).get("settled")]
    return {
        "count": len(rows), "active": len(owned),
        "fully_depreciated": sum(1 for r in owned if r.get("status") == "fully_depreciated"),
        "disposed": len(disposed),
        "transferred": len(transferred),
        "transferred_book_value": tr_book,
        "transferred_unsettled": len(tr_unsettled),
        "gross_cost": gross, "accumulated_depreciation": accum, "net_book_value": net,
        "disposal_gain_loss": disposal_gain, "generated_at": now_iso(),
    }
