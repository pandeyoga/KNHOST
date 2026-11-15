"""PM-T4 (PM-06, K-36) — tunai yang diterima sales dicatat sebagai TITIPAN di tangan pencatatnya sampai disetor.

Bila PT memilih `pembayaran.sales_terima_tunai = titipan`, kwitansi tunai yang dicatat orang TANPA izin `cash.create`
(bukan pemegang kas) tidak membuat transaksi kas. Piutang pelanggan tetap turun lewat alokasi kwitansi biasa
(`ar_allocation_service.allocate(kind="kas")`) dan pelanggan tetap menerima kwitansi bernomor, tetapi uangnya tercatat
sebagai titipan (`cash_holdings`, nomor `TTP-`) dengan jurnal Dr Piutang titipan karyawan / Cr sisi kredit kwitansi biasa
(`gl_service.post_cash_holding`). Pemegang titipan mengajukan setoran (`cash_deposits`, nomor `STT-`); kasir/Finance
(`cash_holding.approve`, bukan pemegang titipan itu) menerimanya ke rekening kas/bank → satu transaksi kas lewat pembuat
kas satu pintu (`cash_ledger.create_cash(ref_type="cash_deposit")`, lawan akun piutang titipan karyawan).

Bawaan `kas_langsung` = perilaku hari ini (titik henti H5). Pemegang `cash.create` selalu `kas_langsung`.

Urutan menerima setoran (`02_STANDAR.md` §1): PERIKSA (status, pemegang ≠ penerima, rekening milik PT & aktif, periode,
titipan masih terbuka dan cukup) → NIAT (klaim setoran + `receive_intent` berid kas tetap) → EFEK (`deposited_amount` tiap
titipan naik dengan syarat tidak melewati `amount`; penanda `deposit_ids` membuat ulang tidak menggandakan) → JURNAL (kas
tahan-gagal: galat jurnal = kas tersimpan `gl_status: failed`, setoran `gl_status: failed`, ulang dari Posting Gagal) →
SELESAI (`diterima`).

Invarian INV-TTP-01 (`scripts/verify_data_integrity.py`, rumus di `rekonsiliasi`): per PT, Σ (amount − deposited_amount)
titipan tidak batal = Σ debit piutang titipan karyawan jurnal `cash_holding` − Σ kreditnya di pembalik
`cash_holding_reversal` − Σ kredit akun itu di jurnal kas ber-`ref_type: cash_deposit`.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, rupiah, safe_doc

logger = logging.getLogger(__name__)

EPS = 0.01
KEY_MODE = "pembayaran.sales_terima_tunai"
KEY_BATAS = "pembayaran.titipan_batas_nominal"
KEY_TENGGAT = "pembayaran.titipan_tenggat_setor_hari"
MODE_KAS, MODE_TITIPAN, MODE_DILARANG = "kas_langsung", "titipan", "dilarang"

#: Status titipan / setoran (spesifikasi `docs/blueprint/unit/PM-T4.md` §Data).
DIPEGANG, SEBAGIAN, DISETOR, BATAL = "dipegang", "sebagian_disetor", "disetor", "batal"
TERBUKA = (DIPEGANG, SEBAGIAN)
STATUS_TITIPAN = (DIPEGANG, SEBAGIAN, DISETOR, BATAL)
DIAJUKAN, DITERIMA, DITOLAK, DIBATALKAN = "diajukan", "diterima", "ditolak", "dibatalkan"
STATUS_SETORAN = (DIAJUKAN, DITERIMA, DITOLAK, DIBATALKAN)

PESAN_DILARANG = "PT ini tidak mengizinkan sales menerima tunai. Minta pelanggan transfer atau bayar ke kasir."
PESAN_BATAS = "Titipan tunai Anda {dipegang} sudah mencapai batas {batas}. Setor dulu sebelum menerima tunai lagi."
PESAN_LEBIH = "Setoran melebihi tunai yang Anda pegang ({dipegang})."
PESAN_PEMEGANG = "Setoran tidak bisa diterima oleh pemegang titipannya sendiri."
PESAN_DIPUTUS = "Setoran ini sudah diterima, ditolak, atau dibatalkan."
PESAN_BATAL_DISETOR = "Titipan kwitansi ini sudah disetor. Batalkan penerimaan setorannya dulu."
PESAN_BATAL_DIAJUKAN = "Titipan kwitansi ini sedang diajukan dalam setoran {nomor}. Tolak atau batalkan setorannya dulu."
PESAN_TANPA_PT = "Pilih satu PT dulu — setoran titipan dicatat per PT."
PESAN_REKENING = "Pilih rekening tujuan setoran."
PESAN_ALASAN = "Isi alasannya (paling sedikit 3 huruf)."
PESAN_BUKAN_PENYETOR = "Setoran hanya bisa dibatalkan oleh penyetornya sendiri."
PESAN_TITIPAN_BERUBAH = "Titipan {nomor} sudah berubah (dibatalkan atau disetor lewat setoran lain). Tolak setoran ini lalu ajukan ulang."
ALASAN_MIN = 3


def holding_id_for(receipt_id: str) -> str:
    """Id tetap titipan dari kwitansinya (satu titipan per kwitansi; ulang = dokumen yang sama)."""
    rid = str(receipt_id or "")
    return "cth_" + (rid[4:] if rid.startswith("arc_") else rid)


def _f(x: Any) -> float:
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _sisa(h: Dict[str, Any]) -> float:
    return round(_f(h.get("amount")) - _f(h.get("deposited_amount")), 2)


# ── Pengaturan ──────────────────────────────────────────────────────────────────────────────────────────────────────
async def _nilai(key: str, entity_id: str) -> Any:
    from services.config_resolver import value_of
    import config_registry
    try:
        return await value_of(key, {"entity_id": entity_id or ""})
    except Exception as exc:  # noqa: BLE001 — cadangan = bawaan registri (`02` §2.2, KF-06)
        logger.warning("[cash_holding] %s tidak terbaca: %s", key, exc)
        return config_registry.require(key)["default"]


async def _pemegang_kas(actor: Dict[str, Any]) -> bool:
    from dependencies import has_permission
    return await has_permission(actor or {}, "cash", "create")


async def mode_tunai(entity_id: str, actor: Dict[str, Any], cara: Dict[str, Any], amount: float) -> str:
    """PERIKSA kwitansi: `kas_langsung` | `titipan`; `dilarang` → 403 (tanpa tulisan apa pun).

    Hanya untuk cara bayar ber-`needs_account: kas` dengan uang baru, dicatat orang yang TIDAK memegang `cash.create`
    (`ASUMSI` unit: "sales" ditentukan dari izin, bukan nama peran). Selain itu selalu `kas_langsung`."""
    if (cara or {}).get("needs_account") != "kas" or _f(amount) <= EPS or await _pemegang_kas(actor):
        return MODE_KAS
    mode = str(await _nilai(KEY_MODE, entity_id) or MODE_KAS)
    if mode == MODE_DILARANG:
        raise HTTPException(status_code=403, detail=PESAN_DILARANG)
    return MODE_TITIPAN if mode == MODE_TITIPAN else MODE_KAS


async def mode_efektif(entity_id: str, actor: Dict[str, Any]) -> str:
    """Mode tunai yang berlaku untuk `actor` di PT itu (bahan layar; tanpa melempar)."""
    if await _pemegang_kas(actor):
        return MODE_KAS
    mode = str(await _nilai(KEY_MODE, entity_id) or MODE_KAS)
    return mode if mode in (MODE_KAS, MODE_TITIPAN, MODE_DILARANG) else MODE_KAS


async def tenggat_hari(entity_id: str) -> int:
    """`pembayaran.titipan_tenggat_setor_hari` PT (0 = tanpa tenggat). Hanya menandai, tidak menolak apa pun."""
    try:
        return max(int(await _nilai(KEY_TENGGAT, entity_id) or 0), 0)
    except (TypeError, ValueError):
        return 0


def _tambah_hari(iso: str, hari: int) -> str:
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (t + timedelta(days=hari)).astimezone(timezone.utc).isoformat()


async def dipegang(entity_id: str, holder_user_id: str) -> float:
    """Σ titipan terbuka (belum disetor) satu orang di satu PT."""
    total = 0.0
    async for h in db.cash_holdings.find({"entity_id": entity_id, "holder_user_id": holder_user_id,
                                          "status": {"$in": list(TERBUKA)}},
                                         {"_id": 0, "amount": 1, "deposited_amount": 1}):
        total += _sisa(h)
    return round(total, 2)


async def periksa_batas(entity_id: str, actor: Dict[str, Any], amount: float) -> None:
    """PERIKSA batas titipan per orang (`pembayaran.titipan_batas_nominal`, 0 = tanpa batas) → 409, tanpa tulisan."""
    batas = _f(await _nilai(KEY_BATAS, entity_id))
    if batas <= EPS:
        return
    sekarang = await dipegang(entity_id, (actor or {}).get("id") or "")
    if sekarang + _f(amount) > batas + EPS:
        raise HTTPException(status_code=409, detail=PESAN_BATAS.format(dipegang=rupiah(sekarang),
                                                                       batas=rupiah(batas)))


# ── Titipan lahir dari kwitansi ─────────────────────────────────────────────────────────────────────────────────────
async def _sinkron_kwitansi(holding_id: str, gl: Dict[str, Any]) -> None:
    """Status jurnal titipan dicerminkan ke kwitansinya (pola kas kwitansi: kwitansi & dokumen jurnalnya sama-sama
    `posted`/`failed`; ulang dari salah satu baris panel menuntaskan keduanya)."""
    h = await db.cash_holdings.find_one({"id": holding_id}, {"_id": 0, "receipt_id": 1, "journal_entry_id": 1})
    if not h:
        return
    st = gl.get("gl_status") or ""
    if st in ("posted", "not_required"):
        await db.cash_holdings.update_one({"id": holding_id}, {"$set": {"je_id": h.get("journal_entry_id") or ""}})
        await db.ar_receipts.update_one({"id": h.get("receipt_id")}, {"$set": {"gl_status": "posted", "gl_error": ""}})
    elif st == "failed":
        await db.ar_receipts.update_one({"id": h.get("receipt_id")}, {"$set": {
            "gl_status": "failed", "gl_error": (gl.get("gl_error") or "")[:300], "updated_at": now_iso()}})


async def _jurnal_titipan(holding: Dict[str, Any], created_by: str, *, raise_on_fail: bool) -> Dict[str, Any]:
    from services import gl_service as gl
    res = await gl.post_durable("cash_holdings", holding["id"], lambda: gl.post_cash_holding(holding, created_by),
                                source_type="cash_holding", source_id=holding["id"], raise_on_fail=raise_on_fail)
    await _sinkron_kwitansi(holding["id"], res)
    return res


async def buat_titipan(receipt: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """EFEK + JURNAL kwitansi titipan: satu `cash_holdings` (id tetap dari kwitansi, `$setOnInsert`) lalu jurnalnya lewat
    `post_durable` (gagal → `gl_status: failed` di titipan & kwitansi, kwitansi tetap sah). → titipan terbaru."""
    hid = receipt.get("cash_holding_id") or holding_id_for(receipt["id"])
    ent = receipt.get("entity_id") or ""
    received = receipt.get("receipt_date") or now_iso()
    hari = await tenggat_hari(ent)
    now = now_iso()
    if not await db.cash_holdings.find_one({"id": hid}, {"_id": 0, "id": 1}):
        doc = {
            "id": hid, "number": await next_doc_number("cash_holdings", "number", "TTP-", entity_id=ent),
            "entity_id": ent, "holder_user_id": (actor or {}).get("id") or "",
            "holder_name": (actor or {}).get("name") or "",
            "receipt_id": receipt["id"], "receipt_number": receipt.get("number") or "",
            "customer_id": receipt.get("customer_id") or "", "customer_name": receipt.get("customer_name") or "",
            "amount": _f(receipt.get("amount")), "deposited_amount": 0.0, "deposit_ids": [], "status": DIPEGANG,
            "received_at": received, "due_at": _tambah_hari(received, hari) if hari else "",
            "gl_status": "pending", "gl_error": "", "je_id": "", "journal_entry_id": "",
            "created_by": (actor or {}).get("name") or "", "created_at": now, "updated_at": now,
        }
        await db.cash_holdings.update_one({"id": hid}, {"$setOnInsert": doc}, upsert=True)
    holding = await db.cash_holdings.find_one({"id": hid}, {"_id": 0})
    await _jurnal_titipan(holding, (actor or {}).get("name") or "system", raise_on_fail=False)
    return await db.cash_holdings.find_one({"id": hid}, {"_id": 0}) or holding


async def ulang_jurnal(holding_id: str, created_by: str = "system") -> Dict[str, Any]:
    """Ulang jurnal titipan yang gagal (panel Posting Gagal / ulang kwitansi). Masih gagal → melempar."""
    h = await db.cash_holdings.find_one({"id": holding_id}, {"_id": 0})
    if not h:
        raise HTTPException(status_code=404, detail="Titipan tunai tidak ditemukan.")
    await _jurnal_titipan(h, created_by, raise_on_fail=True)
    return await db.cash_holdings.find_one({"id": holding_id}, {"_id": 0}) or h


async def periksa_batal_kwitansi(receipt: Dict[str, Any]) -> None:
    """PERIKSA pembatalan kwitansi ber-titipan: titipan yang sudah (sebagian) disetor → 409; titipan yang sedang
    diajukan dalam setoran → 409. Tanpa tulisan."""
    hid = receipt.get("cash_holding_id") or ""
    if not hid:
        return
    h = await db.cash_holdings.find_one({"id": hid}, {"_id": 0})
    if not h or h.get("status") == BATAL:
        return
    if _f(h.get("deposited_amount")) > EPS or h.get("deposit_ids"):
        raise HTTPException(status_code=409, detail=PESAN_BATAL_DISETOR)
    dep = await db.cash_deposits.find_one({"status": DIAJUKAN, "allocations.holding_id": hid},
                                          {"_id": 0, "number": 1})
    if dep:
        raise HTTPException(status_code=409, detail=PESAN_BATAL_DIAJUKAN.format(nomor=dep.get("number") or ""))


async def batalkan_untuk_kwitansi(receipt: Dict[str, Any], reason: str = "") -> None:
    """EFEK pembatalan kwitansi: titipan → `batal` dengan syarat belum disetor (`deposited_amount` 0, tanpa setoran).
    Kalah balapan dengan penerimaan setoran → 409 (belum ada efek lain yang ditulis: langkah ini yang pertama).
    Jurnal pembaliknya terbit di langkah JURNAL pembatalan (`posting_registry.post_receipt_void`)."""
    hid = receipt.get("cash_holding_id") or ""
    if not hid:
        return
    res = await db.cash_holdings.update_one(
        {"id": hid, "status": {"$in": list(TERBUKA)}, "deposited_amount": {"$lte": EPS},
         "deposit_ids": {"$size": 0}},
        {"$set": {"status": BATAL, "voided_at": now_iso(), "voided_reason": (reason or "")[:500],
                  "updated_at": now_iso()}})
    if res.matched_count:
        return
    h = await db.cash_holdings.find_one({"id": hid}, {"_id": 0, "status": 1})
    if h and h.get("status") != BATAL:
        raise HTTPException(status_code=409, detail=PESAN_BATAL_DISETOR)


async def batal_lahir(receipt_id: str) -> None:
    """Kompensasi kwitansi yang gagal lahir (`ar_receipt_service._rollback_unfinished_receipt`): titipannya `batal` dan
    jurnalnya dibalik lewat pintu tahan-gagal (`void_gl_status` di titipan)."""
    from services import gl_service as gl
    hid = holding_id_for(receipt_id)
    h = await db.cash_holdings.find_one({"id": hid}, {"_id": 0})
    if not h:
        return
    await db.cash_holdings.update_one({"id": hid}, {"$set": {"status": BATAL, "voided_at": now_iso(),
                                                             "voided_reason": "kwitansi gagal tercatat",
                                                             "updated_at": now_iso()}})
    await gl.post_durable("cash_holdings", hid,
                          lambda: gl.reverse_cash_holding(hid, label=f"rollback {receipt_id}", created_by="system"),
                          source_type="cash_holding_reversal", source_id=hid, field="void_gl_status")


# ── Setoran ─────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _diajukan_per_titipan(holder_user_id: str, entity_id: str) -> Dict[str, float]:
    """{id titipan: Σ alokasi setoran `diajukan`} — uang yang sudah diajukan tidak boleh diajukan dua kali."""
    out: Dict[str, float] = {}
    async for d in db.cash_deposits.find({"entity_id": entity_id, "holder_user_id": holder_user_id,
                                          "status": DIAJUKAN}, {"_id": 0, "allocations": 1}):
        for al in d.get("allocations") or []:
            out[al.get("holding_id") or ""] = round(out.get(al.get("holding_id") or "", 0.0) + _f(al.get("amount")), 2)
    return out


async def ajukan_setoran(entity_id: str, actor: Dict[str, Any], amount: float,
                         holding_ids: Optional[List[str]] = None, note: str = "") -> Dict[str, Any]:
    """`POST /api/cash-deposits` — setoran `diajukan`. Tanpa `holding_ids` dialokasikan ke titipan tertua lebih dulu.
    Yang bisa disetor = titipan terbuka milik penyetor di PT itu dikurangi yang sudah diajukan di setoran lain."""
    if not entity_id or entity_id == "all":
        raise HTTPException(status_code=400, detail=PESAN_TANPA_PT)
    amount = _f(amount)
    if amount <= EPS:
        raise HTTPException(status_code=400, detail="Jumlah setoran harus lebih dari 0.")
    uid = (actor or {}).get("id") or ""
    q: Dict[str, Any] = {"entity_id": entity_id, "holder_user_id": uid, "status": {"$in": list(TERBUKA)}}
    pilih = [str(x) for x in (holding_ids or []) if x]
    if pilih:
        q["id"] = {"$in": pilih}
    sudah = await _diajukan_per_titipan(uid, entity_id)
    rows: List[Dict[str, Any]] = []
    async for h in db.cash_holdings.find(q, {"_id": 0}).sort([("received_at", 1), ("id", 1)]):
        bisa = round(_sisa(h) - sudah.get(h["id"], 0.0), 2)
        if bisa > EPS:
            rows.append({**h, "_bisa": bisa})
    if pilih and len({r["id"] for r in rows}) != len(set(pilih)):
        found = {r["id"] for r in rows}
        if any(p not in found for p in pilih):
            # N2 — id dari klien harus titipan terbuka milik penyetor di PT ini.
            raise HTTPException(status_code=400, detail="Titipan yang dipilih bukan titipan terbuka milik Anda di PT ini.")
    tersedia = round(sum(r["_bisa"] for r in rows), 2)
    if amount > tersedia + EPS:
        raise HTTPException(status_code=400, detail=PESAN_LEBIH.format(dipegang=rupiah(tersedia)))
    alokasi, sisa = [], amount
    for r in rows:
        if sisa <= EPS:
            break
        ambil = round(min(sisa, r["_bisa"]), 2)
        alokasi.append({"holding_id": r["id"], "holding_number": r.get("number") or "",
                        "receipt_number": r.get("receipt_number") or "", "amount": ambil})
        sisa = round(sisa - ambil, 2)
    now = now_iso()
    doc = {
        "id": new_id("cdp"), "number": await next_doc_number("cash_deposits", "number", "STT-", entity_id=entity_id),
        "entity_id": entity_id, "holder_user_id": uid, "holder_name": (actor or {}).get("name") or "",
        "amount": amount, "allocations": alokasi, "note": str(note or "").strip()[:500], "status": DIAJUKAN,
        "account_id": "", "account_snapshot": {}, "received_by": "", "received_by_id": "", "received_at": "",
        "cash_txn_id": "", "gl_status": "", "gl_error": "", "journal_entry_id": "",
        "created_by": (actor or {}).get("name") or "", "created_at": now, "updated_at": now,
    }
    await db.cash_deposits.insert_one(dict(doc))
    return _bentuk_setoran(doc)


def _bentuk_setoran(d: Dict[str, Any]) -> Dict[str, Any]:
    out = safe_doc(dict(d))
    out["allocations"] = [{"holding_id": a.get("holding_id"), "amount": _f(a.get("amount")),
                           **({"holding_number": a["holding_number"]} if a.get("holding_number") else {}),
                           **({"receipt_number": a["receipt_number"]} if a.get("receipt_number") else {})}
                          for a in out.get("allocations") or []]
    out.pop("saga_lock", None)
    return out


async def _setoran(dep_id: str) -> Dict[str, Any]:
    d = await db.cash_deposits.find_one({"id": dep_id}, {"_id": 0})
    if not d:
        raise HTTPException(status_code=404, detail="Setoran tidak ditemukan.")
    return d


async def terima_setoran(dep_id: str, actor: Dict[str, Any], account_id: str) -> Dict[str, Any]:
    """`POST /api/cash-deposits/{id}/receive` — PERIKSA → NIAT → EFEK → JURNAL → SELESAI (lihat docstring modul)."""
    from services import atomic_claim as _saga
    from services import cash_ledger
    from services import gl_service as gl
    d = await _setoran(dep_id)
    # ── PERIKSA (tanpa tulisan) ──
    if d.get("status") != DIAJUKAN:
        raise HTTPException(status_code=409, detail=PESAN_DIPUTUS)
    if (d.get("holder_user_id") or "") == ((actor or {}).get("id") or "__tanpa__"):
        raise HTTPException(status_code=403, detail=PESAN_PEMEGANG)
    ent = d.get("entity_id") or ""
    intent = d.get("receive_intent") or {}
    acc_id = (intent.get("account_id") if intent.get("status") == "pending" else "") or (account_id or "").strip()
    if not acc_id:
        raise HTTPException(status_code=400, detail=PESAN_REKENING)
    try:
        await gl.preflight_posting(ent, now_iso())
    except gl.ClosedPeriodError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    rek = await cash_ledger.periksa_rekening(ent, acc_id, "")   # milik PT setoran & aktif, selain itu 409
    titipan: Dict[str, Dict[str, Any]] = {}
    for al in d.get("allocations") or []:
        h = await db.cash_holdings.find_one({"id": al.get("holding_id")}, {"_id": 0})
        if not h or (h.get("entity_id") or "") != ent:
            raise HTTPException(status_code=409, detail=PESAN_TITIPAN_BERUBAH.format(nomor=al.get("holding_id")))
        if dep_id not in (h.get("deposit_ids") or []) and (
                h.get("status") not in TERBUKA or _sisa(h) < _f(al.get("amount")) - EPS):
            raise HTTPException(status_code=409, detail=PESAN_TITIPAN_BERUBAH.format(nomor=h.get("number") or h["id"]))
        titipan[h["id"]] = h
    # ── NIAT ──
    lk = await _saga.claim("cash_deposits", dep_id, "cash_deposit_receive", precondition={"status": DIAJUKAN},
                           actor=(actor or {}).get("name") or "", detail=PESAN_DIPUTUS)
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        kas_id = cash_ledger.cash_id("cash_deposit", dep_id, "in")
        if intent.get("status") != "pending":
            intent = {"status": "pending", "account_id": rek["account_id"], "cash_txn_id": kas_id,
                      "by": (actor or {}).get("name") or "", "by_id": (actor or {}).get("id") or "", "at": now_iso()}
            await db.cash_deposits.update_one({"id": dep_id}, {"$set": {"receive_intent": intent,
                                                                        "updated_at": now_iso()}})
        # ── EFEK — titipan naik dengan syarat; penanda `deposit_ids` = ulang tidak menggandakan ──
        for al in d.get("allocations") or []:
            h = titipan[al["holding_id"]]
            amt = _f(al.get("amount"))
            res = await db.cash_holdings.update_one(
                {"id": h["id"], "deposit_ids": {"$ne": dep_id}, "status": {"$in": list(TERBUKA)},
                 "deposited_amount": {"$lte": round(_f(h.get("amount")) - amt + EPS, 2)}},
                {"$inc": {"deposited_amount": amt}, "$push": {"deposit_ids": dep_id},
                 "$set": {"updated_at": now_iso()}})
            fresh = await db.cash_holdings.find_one({"id": h["id"]}, {"_id": 0}) or {}
            if not res.matched_count and dep_id not in (fresh.get("deposit_ids") or []):
                raise HTTPException(status_code=409, detail=PESAN_TITIPAN_BERUBAH.format(nomor=h.get("number") or h["id"]))
            st = DISETOR if _sisa(fresh) <= EPS else SEBAGIAN
            await db.cash_holdings.update_one({"id": h["id"], "status": {"$in": list(TERBUKA)}},
                                              {"$set": {"status": st}})
        # ── JURNAL — kas tahan-gagal lewat pembuat kas satu pintu ──
        gl_status, gl_error = "posted", ""
        try:
            kas = await cash_ledger.create_cash(
                entity_id=ent, direction="in", amount=_f(d.get("amount")), ref_type="cash_deposit", ref_id=dep_id,
                account_id=intent["account_id"], txn_id=intent.get("cash_txn_id") or kas_id, txn_date=now_iso(),
                category="setoran tunai sales",
                description=f"Setoran {d.get('number', '')} — {d.get('holder_name', '')}",
                actor=(actor or {}).get("name") or "system", contra_account_code=gl.ACC_PIUTANG_KARYAWAN,
                extra={"counterparty_name": d.get("holder_name") or ""})
        except cash_ledger.CashPostingError as exc:
            kas, gl_status, gl_error = exc.txn, "failed", exc.error[:300]
        # ── SELESAI ──
        await db.cash_deposits.update_one({"id": dep_id}, _saga.finish_set({
            "status": DITERIMA, "account_id": rek["account_id"],
            "account_snapshot": {"name": rek["account"].get("name") or "",
                                 "bank_name": rek["account"].get("bank_name") or "",
                                 "account_number": rek["account"].get("account_number") or ""},
            "received_by": (actor or {}).get("name") or "", "received_by_id": (actor or {}).get("id") or "",
            "received_at": now_iso(), "cash_txn_id": (kas or {}).get("id") or kas_id,
            "gl_status": gl_status, "gl_error": gl_error,
            "journal_entry_id": (kas or {}).get("journal_entry_id") or "",
            "receive_intent.status": "done", "receive_intent.done_at": now_iso(), "updated_at": now_iso()}))
    finally:
        await _saga.release("cash_deposits", dep_id, token)
    return _bentuk_setoran(await _setoran(dep_id))


async def ulang_jurnal_setoran(dep: Dict[str, Any]) -> None:
    """Panel Posting Gagal jenis `cash_deposit`: jurnal kas setoran (kas yang sama, id tetap) → `gl_status` setoran."""
    from services import cash_ledger
    kas_id = dep.get("cash_txn_id") or ""
    if not kas_id:
        raise RuntimeError("Setoran belum punya transaksi kas — terima ulang setorannya dari tab Titipan Sales.")
    je = await cash_ledger.ensure_posted(kas_id)
    await db.cash_deposits.update_one({"id": dep["id"]}, {"$set": {
        "gl_status": "posted", "gl_error": "", "journal_entry_id": (je or {}).get("id") or "",
        "updated_at": now_iso()}})


async def tandai_jurnal_kas(kas: Dict[str, Any]) -> None:
    """Ulang dari baris kas (jenis `cash_transaction`) ikut menuntaskan penanda setorannya."""
    if kas.get("ref_type") != "cash_deposit" or not kas.get("ref_id"):
        return
    fresh = await db.cash_transactions.find_one({"id": kas["id"]}, {"_id": 0, "gl_status": 1,
                                                                    "journal_entry_id": 1}) or {}
    if fresh.get("gl_status") in ("posted", "not_required"):
        await db.cash_deposits.update_one({"id": kas["ref_id"]}, {"$set": {
            "gl_status": "posted", "gl_error": "", "journal_entry_id": fresh.get("journal_entry_id") or "",
            "updated_at": now_iso()}})


def _alasan(reason: str) -> str:
    teks = str(reason or "").strip()
    if len(teks) < ALASAN_MIN:
        raise HTTPException(status_code=400, detail=PESAN_ALASAN)
    return teks[:500]


async def _putus(dep_id: str, actor: Dict[str, Any], status: str, reason: str) -> Dict[str, Any]:
    """Tolak / batal: setoran `diajukan` (tanpa niat terima berjalan) → `ditolak` / `dibatalkan`. Titipan tidak berubah."""
    res = await db.cash_deposits.update_one(
        {"id": dep_id, "status": DIAJUKAN, "receive_intent.status": {"$ne": "pending"},
         "saga_lock": {"$exists": False}},
        {"$set": {"status": status, "decided_by": (actor or {}).get("name") or "",
                  "decided_by_id": (actor or {}).get("id") or "", "decided_at": now_iso(), "decision_reason": reason,
                  "updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail=PESAN_DIPUTUS)
    return _bentuk_setoran(await _setoran(dep_id))


async def tolak_setoran(dep_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    d = await _setoran(dep_id)
    if d.get("status") != DIAJUKAN:
        raise HTTPException(status_code=409, detail=PESAN_DIPUTUS)
    return await _putus(dep_id, actor, DITOLAK, _alasan(reason))


async def batalkan_setoran(dep_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    d = await _setoran(dep_id)
    if (d.get("holder_user_id") or "") != ((actor or {}).get("id") or "__tanpa__"):
        raise HTTPException(status_code=403, detail=PESAN_BUKAN_PENYETOR)
    if d.get("status") != DIAJUKAN:
        raise HTTPException(status_code=409, detail=PESAN_DIPUTUS)
    return await _putus(dep_id, actor, DIBATALKAN, _alasan(reason))


# ── Daftar & ringkasan ──────────────────────────────────────────────────────────────────────────────────────────────
TITIPAN_SORT = [("received_at", 1), ("id", 1)]
SETORAN_SORT = [("created_at", -1), ("id", -1)]
CARI_TITIPAN = ("number", "receipt_number", "customer_name", "holder_name")
CARI_SETORAN = ("number", "holder_name")


def _status_saring(status: Optional[str], semua: tuple, bawaan: tuple) -> Dict[str, Any]:
    teks = str(status or "").strip()
    if teks == "all":
        return {}
    pilih = [s for s in (teks.split(",") if teks else bawaan) if s in semua]
    if teks and not pilih:
        raise HTTPException(status_code=400, detail="Status tidak dikenal.")
    return {"status": {"$in": pilih}} if pilih else {}


async def _tenggat_peta(entity_ids: List[str]) -> Dict[str, int]:
    return {e: await tenggat_hari(e) for e in entity_ids if e}


def _lewat(h: Dict[str, Any], hari: int, sekarang: str) -> bool:
    if hari <= 0 or h.get("status") not in TERBUKA:
        return False
    batas = _tambah_hari(h.get("received_at") or "", hari)
    return bool(batas) and batas < sekarang


def _bentuk_titipan(h: Dict[str, Any], hari: int, sekarang: str) -> Dict[str, Any]:
    out = safe_doc(dict(h))
    out["outstanding"] = _sisa(h) if h.get("status") in TERBUKA else 0.0
    out["due_at"] = _tambah_hari(h.get("received_at") or "", hari) if hari else ""
    out["overdue"] = _lewat(h, hari, sekarang)
    return out


async def daftar_titipan(scope: Dict[str, Any], *, entity_ids: List[str], status: Optional[str] = None,
                         holder_user_id: str = "", overdue: bool = False, q: str = "", page: int = 1,
                         page_size: int = 50) -> Dict[str, Any]:
    """`GET /api/cash-holdings` — satu halaman titipan + jumlah total + ringkasan per pemegang (`holders`, dari SEMUA
    baris yang cocok saringan, bukan halaman ini). Bawaan status = terbuka; `overdue=true` = lewat tenggat PT-nya."""
    from pagination import build_search, envelope, merge_query
    query = merge_query(dict(scope or {}), _status_saring(status, STATUS_TITIPAN, TERBUKA))
    if holder_user_id:
        query["holder_user_id"] = holder_user_id
    query = merge_query(query, build_search(q, CARI_TITIPAN))
    tenggat = await _tenggat_peta(entity_ids)
    sekarang = now_iso()
    if overdue:
        cabang = [{"entity_id": e, "status": {"$in": list(TERBUKA)},
                   "received_at": {"$lt": (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()}}
                  for e, n in tenggat.items() if n > 0]
        query = merge_query(query, {"$or": cabang} if cabang else {"id": "__tanpa_tenggat__"})
    total = await db.cash_holdings.count_documents(query)
    rows = await db.cash_holdings.find(query, {"_id": 0}).sort(TITIPAN_SORT) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    holders: Dict[str, Dict[str, Any]] = {}
    async for h in db.cash_holdings.find(query, {"_id": 0, "holder_user_id": 1, "holder_name": 1, "amount": 1,
                                                 "deposited_amount": 1, "status": 1, "received_at": 1,
                                                 "entity_id": 1}):
        if h.get("status") not in TERBUKA:
            continue
        g = holders.setdefault(h.get("holder_user_id") or "", {
            "holder_user_id": h.get("holder_user_id") or "", "holder_name": h.get("holder_name") or "",
            "held_total": 0.0, "count": 0, "oldest_received_at": "", "overdue_count": 0})
        g["held_total"] = round(g["held_total"] + _sisa(h), 2)
        g["count"] += 1
        if not g["oldest_received_at"] or str(h.get("received_at") or "") < g["oldest_received_at"]:
            g["oldest_received_at"] = str(h.get("received_at") or "")
        if _lewat(h, tenggat.get(h.get("entity_id") or "", 0), sekarang):
            g["overdue_count"] += 1
    out = envelope([_bentuk_titipan(h, tenggat.get(h.get("entity_id") or "", 0), sekarang) for h in rows],
                   total, page, page_size)
    out["holders"] = sorted(holders.values(), key=lambda g: (-g["held_total"], g["holder_name"]))
    return out


async def daftar_setoran(scope: Dict[str, Any], *, status: Optional[str] = None, holder_user_id: str = "",
                         q: str = "", page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """`GET /api/cash-deposits` — satu halaman setoran (bawaan `diajukan`) + jumlah total + Σ nominal."""
    from pagination import build_search, envelope, merge_query
    query = merge_query(dict(scope or {}), _status_saring(status, STATUS_SETORAN, (DIAJUKAN,)))
    if holder_user_id:
        query["holder_user_id"] = holder_user_id
    query = merge_query(query, build_search(q, CARI_SETORAN))
    total = await db.cash_deposits.count_documents(query)
    rows = await db.cash_deposits.find(query, {"_id": 0}).sort(SETORAN_SORT) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    jumlah = 0.0
    async for d in db.cash_deposits.find(query, {"_id": 0, "amount": 1}):
        jumlah += _f(d.get("amount"))
    out = envelope([_bentuk_setoran(d) for d in rows], total, page, page_size)
    out["amount_total"] = round(jumlah, 2)
    return out


async def ringkasan_saya(entity_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`GET /api/cash-holdings/me/summary` (milik sendiri, Z3) — `{held_total, count, oldest_due_at, limit, mode,
    pending_total, available, overdue_count, tenggat_hari, entity_id}` untuk PT aktif. Batas =
    `pembayaran.titipan_batas_nominal`; mode = mode tunai yang berlaku untuk akun ini (pemegang kas = kas langsung)."""
    uid = (actor or {}).get("id") or ""
    if not entity_id or entity_id == "all":
        return {"entity_id": "", "held_total": 0.0, "count": 0, "oldest_due_at": "", "limit": 0.0, "mode": "",
                "pending_total": 0.0, "available": 0.0, "overdue_count": 0, "tenggat_hari": 0}
    hari = await tenggat_hari(entity_id)
    sekarang = now_iso()
    held, n, oldest, telat = 0.0, 0, "", 0
    async for h in db.cash_holdings.find({"entity_id": entity_id, "holder_user_id": uid,
                                          "status": {"$in": list(TERBUKA)}}, {"_id": 0}):
        held += _sisa(h)
        n += 1
        if hari:
            due = _tambah_hari(h.get("received_at") or "", hari)
            if due and (not oldest or due < oldest):
                oldest = due
            telat += 1 if _lewat(h, hari, sekarang) else 0
    pending = round(sum((await _diajukan_per_titipan(uid, entity_id)).values()), 2)
    return {"entity_id": entity_id, "held_total": round(held, 2), "count": n, "oldest_due_at": oldest,
            "limit": _f(await _nilai(KEY_BATAS, entity_id)), "mode": await mode_efektif(entity_id, actor),
            "pending_total": pending, "available": round(max(held - pending, 0.0), 2), "overdue_count": telat,
            "tenggat_hari": hari}


# ── INV-TTP-01 dan pembangun ulang ──────────────────────────────────────────────────────────────────────────────────
async def _kredit_debit(flt: Dict[str, Any], codes: List[str]) -> Dict[str, Dict[str, float]]:
    """{PT: {debit, credit}} akun `codes` di jurnal tidak-batal yang cocok `flt`."""
    out: Dict[str, Dict[str, float]] = {}
    async for je in db.journal_entries.find({**flt, "status": {"$ne": "void"}},
                                            {"_id": 0, "entity_id": 1, "lines": 1}):
        g = out.setdefault(je.get("entity_id") or "", {"debit": 0.0, "credit": 0.0})
        for ln in je.get("lines") or []:
            if ln.get("account_code") in codes:
                g["debit"] = round(g["debit"] + _f(ln.get("debit")), 2)
                g["credit"] = round(g["credit"] + _f(ln.get("credit")), 2)
    return out


async def rekonsiliasi() -> List[Dict[str, Any]]:
    """INV-TTP-01 per PT → baris berselisih (kosong = cocok): `{entity_id, titipan, jurnal, selisih}`.

    titipan = Σ (amount − deposited_amount) titipan tidak batal; jurnal = Σ debit piutang titipan karyawan jurnal
    `cash_holding` − Σ kredit akun itu di pembalik `cash_holding_reversal` − Σ kredit akun itu di jurnal kas setoran
    (`cash_transactions.ref_type = cash_deposit`). Dibandingkan per SUMBER jurnal, bukan saldo akun: akun yang sama
    dipakai Kasus Keuangan ("uang dipegang karyawan")."""
    from services import gl_mapping_service as glm
    codes = await glm.known_codes("kas_bank.piutang_karyawan")
    titipan: Dict[str, float] = {}
    async for h in db.cash_holdings.find({"status": {"$ne": BATAL}}, {"_id": 0, "entity_id": 1, "amount": 1,
                                                                      "deposited_amount": 1}):
        e = h.get("entity_id") or ""
        titipan[e] = round(titipan.get(e, 0.0) + _sisa(h), 2)
    debit = await _kredit_debit({"source_type": "cash_holding"}, codes)
    balik = await _kredit_debit({"source_type": "cash_holding_reversal"}, codes)
    kas_ids = [c["id"] async for c in db.cash_transactions.find({"ref_type": "cash_deposit"}, {"_id": 0, "id": 1})]
    setor = await _kredit_debit({"source_type": "cash_transaction", "source_id": {"$in": kas_ids}}, codes) \
        if kas_ids else {}
    bad = []
    for e in sorted(set(titipan) | set(debit) | set(balik) | set(setor)):
        jurnal = round((debit.get(e) or {}).get("debit", 0.0) - (balik.get(e) or {}).get("credit", 0.0)
                       - (setor.get(e) or {}).get("credit", 0.0), 2)
        if abs(jurnal - titipan.get(e, 0.0)) >= 1:
            bad.append({"entity_id": e, "titipan": titipan.get(e, 0.0), "jurnal": jurnal,
                        "selisih": round(titipan.get(e, 0.0) - jurnal, 2)})
    return bad


async def hitung_ulang_disetor(tulis: bool = False) -> List[Dict[str, Any]]:
    """Pembangun ulang `deposited_amount` (`02` D2): Σ alokasi setoran `diterima` per titipan. → titipan yang berbeda
    `{id, number, entity_id, tersimpan, seharusnya}`; `tulis=True` membetulkannya (status ikut). Bawaan = lapor saja."""
    harus: Dict[str, float] = {}
    async for d in db.cash_deposits.find({"status": DITERIMA}, {"_id": 0, "allocations": 1}):
        for al in d.get("allocations") or []:
            hid = al.get("holding_id") or ""
            harus[hid] = round(harus.get(hid, 0.0) + _f(al.get("amount")), 2)
    beda = []
    async for h in db.cash_holdings.find({}, {"_id": 0}):
        want = harus.get(h["id"], 0.0)
        if abs(_f(h.get("deposited_amount")) - want) < EPS:
            continue
        beda.append({"id": h["id"], "number": h.get("number") or "", "entity_id": h.get("entity_id") or "",
                     "tersimpan": _f(h.get("deposited_amount")), "seharusnya": want})
        if tulis and h.get("status") != BATAL:
            st = DISETOR if _f(h.get("amount")) - want <= EPS else (SEBAGIAN if want > EPS else DIPEGANG)
            await db.cash_holdings.update_one({"id": h["id"]}, {"$set": {"deposited_amount": want, "status": st,
                                                                         "updated_at": now_iso()}})
    return beda
