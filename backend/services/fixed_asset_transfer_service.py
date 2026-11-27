"""PK-23 (FY-04) — pindah aset tetap antar-PT dan pembayarannya: dua PT atau tidak sama sekali, tidak dua kali.

Dipisah dari `fixed_asset_service.py` (master, perolehan, penyusutan, pelepasan). Pola `02_STANDAR.md` §1 + P6:
PERIKSA kedua PT tanpa tulisan → NIAT berklaim (`transferring` + `transfer.intent`; pembayaran: `settle_status`
`none → settling`) → EFEK idempoten (aset pengganti ber-id turunan; kas kembar lewat pembuat kas PK-20) → JURNAL
kembar lewat `twin_journal.post_twin` (PK-06; status per sisi di aset masing-masing) → SELESAI. Panggilan ulang dan
Ulang Posting meneruskan niat yang tersimpan.
"""
from datetime import datetime as _dt, timedelta as _td, timezone as _tz
from typing import Any, Dict, List, Optional

from db import db
from core_utils import now_iso, next_doc_number, safe_doc, DEFAULT_ENTITY_ID
from services import gl_service
from services.book_date import tanggal_buku
from services.fixed_asset_service import (
    EPS, DEFAULT_ASSET_ACC, AssetError, _assert_no_open_depreciation, _assert_usable, _entity_name, _label,
    _monthly_amount, _preflight_period,
)


# ── Pindah antar-PT (PK-23 · FY-04) ─────────────────────────────────────────────────────────────────────────────────
TRANSFER_SOURCE = "fixed_asset_transfer"
SETTLE_SOURCE = "fixed_asset_transfer_settlement"
#: Jatah kerja satu permintaan atas niat pindah/bayar yang sedang berjalan. Permintaan lain menunggu (409) sampai
#: jatahnya dilepas (jurnal gagal) atau kedaluwarsa (proses mati di tengah). Batas teknis, bukan aturan bisnis.
LEASE_MINUTES = 2


def _lease_until() -> str:
    return (_dt.now(_tz.utc) + _td(minutes=LEASE_MINUTES)).isoformat()


def target_id_for(asset_id: str) -> str:
    """Id aset pengganti di PT penerima — turunan id aset lama (sisip bersyarat: pindah dua kali = satu aset)."""
    return f"{asset_id}_tr"


def _transfer_sides(a: Dict[str, Any], plan: Dict[str, Any], target: Optional[Dict[str, Any]]):
    """Rencana jurnal kembar pindah aset (kunci sisi sama dengan jalur lama: `fixed_asset_transfer` · `{id}:from`
    di pengirim; `fixed_asset_acquisition` · `{id aset baru}` di penerima — baris dan keterangannya sama dengan
    `gl_service.post_asset_acquisition`, jadi jurnal lama/ulang perolehan dikenali)."""
    from services.twin_journal import TwinSide
    nomor = a.get("number") or a["id"]
    cost, accum = plan["cost"], plan["accum"]
    price, gain = plan["price"], plan["gain"]
    lines_from: List[Dict[str, Any]] = []
    if accum > EPS:
        lines_from.append({"account_code": a.get("gl_account_acc_dep", gl_service.ACC_FA_ACCUM_DEP),
                           "debit": accum, "credit": 0.0, "description": f"Hapus akumulasi penyusutan {nomor}"})
    lines_from.append({"account_code": gl_service.ACC_IC_AR, "debit": price, "credit": 0.0,
                       "description": f"Piutang antar-PT pindah aset ke {plan['to_entity_name']}"})
    if gain < -EPS:
        lines_from.append({"account_code": gl_service.ACC_FA_LOSS, "debit": round(-gain, 2), "credit": 0.0,
                           "description": f"Rugi pindah aset {nomor}"})
    lines_from.append({"account_code": a.get("gl_account_asset", DEFAULT_ASSET_ACC), "debit": 0.0, "credit": cost,
                       "description": f"Hapus aset {nomor} (harga perolehan)"})
    if gain > EPS:
        lines_from.append({"account_code": gl_service.ACC_FA_GAIN, "debit": 0.0, "credit": gain,
                           "description": f"Laba pindah aset {nomor} (dieliminasi di grup)"})
    lbl = _label(target) if target else (a.get("name") or nomor)
    tid = target_id_for(a["id"])
    lines_to = [
        {"account_code": a.get("gl_account_asset") or DEFAULT_ASSET_ACC, "debit": price, "credit": 0.0,
         "description": f"Perolehan aset {lbl}"},
        {"account_code": gl_service.ACC_IC_AP, "debit": 0.0, "credit": price,
         "description": f"Pembayaran perolehan aset {lbl}"},
    ]
    label_from = f"Pindah aset {nomor} → {plan['to_entity_name']}"
    return [
        TwinSide("from", plan["from_entity_id"], lines_from, label_from, label_from, ("fin_fixed_assets", a["id"]),
                 "_transfer"),
        TwinSide("to", plan["to_entity_id"], lines_to, f"Perolehan aset tetap {lbl}", lbl, ("fin_fixed_assets", tid),
                 "", source_type="fixed_asset_acquisition", source_id=tid),
    ]


async def _create_transfer_target(a: Dict[str, Any], plan: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """EFEK — aset pengganti di PT penerima (id turunan, `funding_source: antar_pt`, `gl_status: pending`), sisip
    bersyarat belum ada. Jurnalnya sisi `to` jurnal kembar."""
    tid = target_id_for(a["id"])
    ada = await db.fin_fixed_assets.find_one({"id": tid}, {"_id": 0})
    if ada:
        return ada
    to_ent, price, life_left = plan["to_entity_id"], plan["price"], plan["life_left"]
    salvage = plan["salvage_new"]
    doc = {
        "id": tid, "number": await next_doc_number("fin_fixed_assets", "number", "FA-", entity_id=to_ent),
        "name": a.get("name", ""), "category": a.get("category", ""),
        "acquisition_cost": price, "acquisition_date": plan["transfer_date"], "useful_life_months": life_left,
        "salvage_value": salvage, "method": "straight_line", "entity_id": to_ent,
        "gl_account_asset": a.get("gl_account_asset") or DEFAULT_ASSET_ACC,
        "gl_account_dep_exp": gl_service.ACC_DEP_EXPENSE, "gl_account_acc_dep": gl_service.ACC_FA_ACCUM_DEP,
        "funding_source": "antar_pt", "funding_account": gl_service.ACC_IC_AP, "account_id": "",
        "funding_cash_type": "", "acquisition_cash_txn_id": "",
        "monthly_depreciation": _monthly_amount(price, salvage, life_left), "accumulated_depreciation": 0.0,
        "book_value": price, "depreciated_months": 0, "last_depreciation_period": "", "status": "active",
        "acquisition_je": "", "gl_status": "pending", "gl_error": "", "disposal": None,
        "transfer_from": {"asset_id": a["id"], "number": a.get("number", ""), "entity_id": plan["from_entity_id"],
                          "entity_name": plan["from_entity_name"]},
        "notes": (f"Pindah dari {plan['from_entity_name']} ({a.get('number')}) pada {plan['transfer_date']}. "
                  f"Nilai buku saat pindah {plan['book']} · harga pindah {price} · "
                  f"masa manfaat sisa {life_left} bulan. Alasan: {plan['reason']}"),
        "created_by": actor.get("name", "system"), "created_at": now_iso(), "updated_at": now_iso(),
    }
    try:
        await db.fin_fixed_assets.update_one({"id": tid}, {"$setOnInsert": doc}, upsert=True)
    except Exception as exc:  # noqa: BLE001 — balapan sisip id turunan: yang kalah memakai dokumen pemenang
        if "E11000" not in str(exc) and "duplicate key" not in str(exc).lower():
            raise
    return await db.fin_fixed_assets.find_one({"id": tid}, {"_id": 0}) or doc


async def transfer_to_entity(asset_id: str, payload: Dict[str, Any],
                             actor: Dict[str, Any]) -> Dict[str, Any]:
    """FASE E-7 (E7g) — **PINDAH ASET TETAP ANTAR-PT** (keputusan pemilik E7.7).

    Yang dijaga di sini (dan inilah sebabnya bukan sekadar mengganti `entity_id`):

    * **Nilai buku ikut pindah, bukan harga perolehan asli.** Aset lahir kembali di PT
      penerima dengan harga = harga pindah (bawaan: nilai buku) dan **masa manfaat SISA**,
      supaya penyusutannya tidak dimulai dari awal (itu akan mengecilkan beban bertahun-tahun).
    * **Akumulasi penyusutan di PT pengirim dihapus lewat jurnal**, tidak “dibawa” —
      buku pengirim harus bersih dari aset yang sudah bukan miliknya.
    * **Laba/rugi pindah dijurnal DAN dieliminasi** di konsolidasi: kalau dijual di atas
      nilai buku ke PT sendiri, laba itu tidak nyata bagi grup.
    * Aset lama TIDAK dihapus (append-only) → status `transferred` + jejak `transfer`.

    Jurnalnya (dua buku):
        pengirim : Dr Akum.Penyusutan + Dr IC-AR (harga) [+ Dr Rugi] / Cr Aset (perolehan)
                   [+ Cr Laba Pelepasan]
        penerima : Dr Aset (harga) / Cr IC-AP (harga)

    PK-23 (FY-04) — dua PT atau tidak sama sekali, dan tidak dua kali:
      1. PERIKSA tanpa tulisan: status & jurnal perolehan, periode PENGIRIM dan PENERIMA pada tanggal pindah, baris
         jurnal kedua sisi (`twin_journal.preflight_twin`: akun aktif + periode, tiap PT).
      2. NIAT: klaim `active`/`fully_depreciated` → `transferring` + `transfer.intent` (id tetap); kalah → 409.
      3. EFEK: aset pengganti `{id}_tr` di PT penerima (sisip bersyarat).
      4. JURNAL: dua sisi lewat `twin_journal.post_twin` (status per sisi di aset masing-masing).
      5. SELESAI: aset lama `transferred` + jejak; saldo pasangan PT + eliminasi; niat `done`.
    Panggilan ulang atas aset `transferring` meneruskan niat yang sama (isi permintaan baru diabaikan).
    """
    from services import interco_money_service as money, twin_journal as twin

    a = await db.fin_fixed_assets.find_one({"id": asset_id}, {"_id": 0})
    if not a:
        raise ValueError("Aset tetap tidak ditemukan.")
    if a.get("status") == "transferring" and ((a.get("transfer") or {}).get("intent") or {}).get("plan"):
        return await _run_transfer(a, actor, resume=True)
    if a.get("status") == "disposed":
        raise ValueError("Aset sudah dilepas (disposed) — tidak bisa dipindahkan.")
    await _assert_usable(a)                  # sudah pindah (409) / sedang diproses / belum berjurnal
    if (a.get("transfer") or {}).get("to_entity_id"):
        raise ValueError(
            f"Aset ini sudah pernah dipindahkan ke badan usaha lain "
            f"({(a.get('transfer') or {}).get('to_entity_name', '')}) — yang aktif sekarang "
            f"adalah aset penggantinya di badan usaha itu.")
    await _assert_no_open_depreciation(a)
    from_ent = a.get("entity_id") or DEFAULT_ENTITY_ID
    to_ent = (payload.get("to_entity_id") or "").strip()
    snaps = await money.assert_pair(from_ent, to_ent, what="Pindah aset tetap antar-PT")
    reason = (payload.get("reason") or "").strip()
    if len(reason) < 5:
        raise ValueError(
            "Alasan pindah wajib diisi (minimal 5 huruf) — pemindahan aset antar badan "
            "hukum harus bisa dijelaskan ke auditor & pemeriksa pajak.")

    cost = round(float(a.get("acquisition_cost") or 0), 2)
    accum = round(float(a.get("accumulated_depreciation") or 0), 2)
    book = round(cost - accum, 2)
    price = round(float(payload.get("transfer_price") or 0), 2) or book
    if price <= 0:
        raise ValueError("Harga pindah harus lebih dari 0 (atau kosongkan untuk memakai "
                         "nilai buku).")
    gain = round(price - book, 2)
    tdate = tanggal_buku(payload.get("transfer_date") or "")
    life_left = max(int(a.get("useful_life_months") or 0) - int(a.get("depreciated_months") or 0), 1)
    salvage_new = round(min(float(a.get("salvage_value") or 0), max(price - 1, 0.0)), 2)
    plan = {"from_entity_id": from_ent, "from_entity_name": snaps["a"]["name"], "to_entity_id": to_ent,
            "to_entity_name": snaps["b"]["name"], "transfer_date": tdate, "cost": cost, "accum": accum, "book": book,
            "price": price, "gain": gain, "reason": reason, "life_left": life_left, "salvage_new": salvage_new,
            "status_before": a.get("status")}

    # ── 1. PERIKSA (tanpa tulisan): periode kedua PT + baris jurnal kedua sisi ─────────────────────────────────────
    for ent in (from_ent, to_ent):
        await _preflight_period(ent, tdate)
    try:
        await twin.preflight_twin(source_type=TRANSFER_SOURCE, base_id=asset_id, date=tdate,
                                  sides=_transfer_sides(a, plan, None))
    except twin.TwinJournalError as exc:
        raise AssetError(str(exc), 409) from exc

    # ── 2. NIAT: klaim bersyarat status lama ───────────────────────────────────────────────────────────────────────
    intent = {"id": f"fatr_{asset_id}", "status": "pending",
              "steps": {"target_created": False, "journals": False, "source_marked": False},
              "plan": plan, "lease_until": _lease_until(), "by": actor.get("name", ""), "at": now_iso()}
    won = await db.fin_fixed_assets.find_one_and_update(
        {"id": asset_id, "status": a.get("status"), "transfer.intent": {"$exists": False}},
        {"$set": {"status": "transferring", "transfer": {"intent": intent, "settle_status": "none"},
                  "updated_at": now_iso()}}, projection={"_id": 0, "id": 1})
    if not won:
        raise AssetError(f"Aset {a.get('number') or asset_id} sedang diproses. Muat ulang.")
    fresh = await db.fin_fixed_assets.find_one({"id": asset_id}, {"_id": 0})
    return await _run_transfer(fresh, actor)


async def _run_transfer(a: Dict[str, Any], actor: Dict[str, Any], *, resume: bool = False) -> Dict[str, Any]:
    """Langkah 3–5 pindah aset dari niat yang tersimpan (permintaan pertama, panggilan ulang, Ulang Posting)."""
    from services import interco_money_service as money, twin_journal as twin
    intent = (a.get("transfer") or {}).get("intent") or {}
    plan = intent["plan"]
    nomor = a.get("number") or a["id"]
    if resume:   # jatah kerja: hanya satu permintaan yang meneruskan niat yang sama
        won = await db.fin_fixed_assets.find_one_and_update(
            {"id": a["id"], "status": "transferring", "transfer.intent.id": intent.get("id"),
             "$or": [{"transfer.intent.lease_until": {"$in": ["", None]}},
                     {"transfer.intent.lease_until": {"$lt": now_iso()}}]},
            {"$set": {"transfer.intent.lease_until": _lease_until(), "updated_at": now_iso()}},
            projection={"_id": 0, "id": 1})
        if not won:
            raise AssetError(f"Aset {nomor} sedang diproses. Muat ulang.")
    # ── 3. EFEK ──────────────────────────────────────────────────────────────────────────────────────────────────
    target = await _create_transfer_target(a, plan, actor)
    await db.fin_fixed_assets.update_one({"id": a["id"]}, {"$set": {"transfer.intent.steps.target_created": True}})
    # ── 4. JURNAL (dua buku, status per sisi) ────────────────────────────────────────────────────────────────────
    sides = _transfer_sides(a, plan, target)
    hasil = await twin.post_twin(source_type=TRANSFER_SOURCE, base_id=a["id"], date=plan["transfer_date"],
                                 sides=sides, created_by=actor.get("name", "system"))
    if any(v.get("status") == "failed" for v in hasil.values()):
        await db.fin_fixed_assets.update_one({"id": a["id"], "status": "transferring"}, {"$set": {
            "transfer.intent.lease_until": "", "updated_at": now_iso()}})
        raise AssetError(f"Pindah aset {nomor} belum selesai. {await twin.warning_for(hasil, sides)} Aset tetap "
                         f"tercatat di {plan['from_entity_name']} sampai kedua jurnalnya terbit.", 409)
    jid_to = (hasil.get("to") or {}).get("journal_id", "")
    je_to = await db.journal_entries.find_one({"id": jid_to}, {"_id": 0, "number": 1}) or {}
    await db.fin_fixed_assets.update_one({"id": target["id"]}, {"$set": {
        "journal_entry_id": jid_to, "acquisition_je": je_to.get("number", ""), "gl_error": ""}})
    # ── 5. SELESAI ───────────────────────────────────────────────────────────────────────────────────────────────
    from_ent, to_ent = plan["from_entity_id"], plan["to_entity_id"]
    transfer = {
        "from_entity_id": from_ent, "from_entity_name": plan["from_entity_name"],
        "to_entity_id": to_ent, "to_entity_name": plan["to_entity_name"],
        "transfer_date": plan["transfer_date"], "book_value": plan["book"], "price": plan["price"],
        "gain": plan["gain"], "reason": plan["reason"], "new_asset_id": target["id"],
        "new_asset_number": target.get("number", ""), "useful_life_left_months": plan["life_left"],
        "settled": False, "settle_status": "none", "settled_at": "", "cash_txn_ids": [],
        "by": intent.get("by") or actor.get("name", ""), "at": now_iso(),
        "intent": {**intent, "status": "done", "lease_until": "",
                   "steps": {"target_created": True, "journals": True, "source_marked": True}},
    }
    await db.fin_fixed_assets.update_one({"id": a["id"], "status": "transferring"}, {"$set": {
        "status": "transferred", "transfer": transfer, "book_value": 0.0, "updated_at": now_iso()}})
    gain = plan["gain"]
    await money.refresh_pair_exposure(from_ent, to_ent)
    await money.sync_non_trade_elimination(
        source_key=f"asset:{a['id']}", pair_id=a["id"],
        from_entity=from_ent, to_entity=to_ent, outstanding=plan["price"],
        label=f"pindah aset {a.get('number')} → {target.get('number')}",
        extra_note=(f"Laba pindah {gain} ikut dieliminasi karena penjualnya PT sendiri."
                    if gain > EPS else ""))
    # Laba pindah antar-PT BUKAN laba grup: dihapus dari laba konsolidasi sekaligus
    # menurunkan nilai aset yang ikut naik hanya karena berpindah tangan di dalam grup.
    # Entri ini TIDAK hilang saat utangnya dibayar — ia hidup selama asetnya dipegang.
    if gain > EPS:
        await money.sync_non_trade_elimination(
            source_key=f"asset_gain:{a['id']}", pair_id=a["id"],
            from_entity=from_ent, to_entity=to_ent, outstanding=gain,
            label=f"laba pindah aset {a.get('number')} → {target.get('number')}",
            accounts=(gl_service.ACC_FA_GAIN, target.get("gl_account_asset", DEFAULT_ASSET_ACC)),
            kind_note="laba pindah aset (bukan laba grup)",
            extra_note=("Harga pindah di atas nilai buku; selisihnya laba internal, jadi "
                        "dihapus dari laba grup dan dari nilai aset konsolidasi."))
    src = await db.fin_fixed_assets.find_one({"id": a["id"]}, {"_id": 0}) or {**a, "transfer": transfer}
    new_doc = await db.fin_fixed_assets.find_one({"id": target["id"]}, {"_id": 0}) or target
    return {"source": safe_doc(src), "new_asset": safe_doc(new_doc), "gain": gain, "book_value": plan["book"],
            "price": plan["price"]}


async def resume_transfer(asset: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """Jalur Ulang Posting jenis `fixed_asset_transfer` (sisi pengirim) dan `fixed_asset` untuk aset pengganti
    (sisi penerima): niat pindah diteruskan dari langkah yang tercatat."""
    src = asset
    if asset.get("funding_source") == "antar_pt":
        src = await db.fin_fixed_assets.find_one({"id": (asset.get("transfer_from") or {}).get("asset_id")},
                                                 {"_id": 0}) or {}
    if src.get("status") != "transferring":
        raise RuntimeError("Pindah aset ini tidak sedang menunggu jurnal. Muat ulang.")
    await _run_transfer(src, actor, resume=True)


def _settle_sides(a: Dict[str, Any], tr: Dict[str, Any], akun_bayar: str, akun_terima: str):
    """Rencana jurnal kembar pelunasan pindah aset. Kas & Bank 1 — `akun_bayar` / `akun_terima` = akun kas rekening
    pembayar / penerima (`interco_money_service.akun_kas_bank`; PT belum aktif: akun lama)."""
    from services import interco_money_service as money
    from services.twin_journal import TwinSide
    price = round(float(tr.get("price") or 0), 2)
    label = f"Pelunasan pindah aset {a.get('number')}"
    return [
        TwinSide("a", tr["to_entity_id"], money.pair_line(gl_service.ACC_IC_AP, akun_bayar, price,
                                                          f"Bayar pindah aset {a.get('number')}"),
                 label, label, ("fin_fixed_assets", a["id"]), "_settle_payer"),
        TwinSide("b", tr["from_entity_id"], money.pair_line(akun_terima, gl_service.ACC_IC_AR, price,
                                                            f"Terima pembayaran pindah aset {a.get('number')}"),
                 label, label, ("fin_fixed_assets", a["id"]), "_settle_payee"),
    ]


async def settle_transfer(asset_id: str, actor: Dict[str, Any], note: str = "", *,
                          allowed_entity_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """E7g — bayar utang antar-PT atas aset yang dipindah (uang benar-benar berpindah).

    Dipisah dari pemindahannya karena di lapangan aset sering pindah dulu, uangnya
    menyusul (atau di-netting). Selama belum dibayar, saldonya tampil sebagai
    **saldo non-dagang** di papan pasangan PT — bukan hilang.

    PK-23 (FY-04) — pelaku wajib berwenang di PT PEMBAYAR (`transfer.to_entity_id`, `allowed_entity_ids`) → 403;
    PERIKSA rekening & periode kedua PT dan baris jurnal kedua sisi; klaim `settle_status: none → settling` (kalah →
    409); kas kembar lewat pembuat kas (PK-20), jurnal kembar lewat `twin_journal.post_twin` (PK-06); `settled`.
    Panggilan ulang atas `settling` (jurnal gagal) meneruskan: kas dipakai ulang, sisi yang kurang diterbitkan.
    """
    from services import cash_ledger, interco_money_service as money, twin_journal as twin

    a = await db.fin_fixed_assets.find_one({"id": asset_id}, {"_id": 0})
    if not a:
        raise ValueError("Aset tetap tidak ditemukan.")
    tr = a.get("transfer") or {}
    if not tr.get("to_entity_id"):
        raise ValueError("Aset ini tidak pernah dipindahkan antar badan usaha.")
    nomor = a.get("number") or asset_id
    payer, payee = tr["to_entity_id"], tr["from_entity_id"]
    if allowed_entity_ids is not None and payer not in allowed_entity_ids:
        raise AssetError(f"Anda belum punya akses di {tr.get('to_entity_name') or await _entity_name(payer)} untuk "
                         f"mencatat pembayaran ini.", 403)
    if a.get("status") != "transferred":
        raise AssetError(f"Aset {nomor} sedang diproses. Muat ulang.")
    st = tr.get("settle_status") or ("settled" if tr.get("settled") else "none")
    if st == "settled" or tr.get("settled"):
        raise ValueError("Pembayaran pindah aset ini sudah dicatat.")
    price = round(float(tr.get("price") or 0), 2)
    tgl = tanggal_buku()
    base = f"{asset_id}:settle"
    if st == "settling":
        won = await db.fin_fixed_assets.find_one_and_update(
            {"id": asset_id, "transfer.settle_status": "settling",
             "$or": [{"transfer.settle_lease_until": {"$in": ["", None]}},
                     {"transfer.settle_lease_until": {"$lt": now_iso()}}]},
            {"$set": {"transfer.settle_lease_until": _lease_until()}}, projection={"_id": 0, "id": 1})
        if not won:
            raise AssetError(f"Aset {nomor} sedang diproses. Muat ulang.")
    else:
        # ── PERIKSA (tanpa tulisan): periode & rekening Bank kedua PT, baris jurnal kedua sisi ────────────────────
        rek = {}
        for ent in (payer, payee):
            await _preflight_period(ent, tgl)
            rek[ent] = (await cash_ledger.periksa_rekening(ent, await money.default_cash_account(ent),
                                                           "kas_besar"))["account_id"]
        try:
            await twin.preflight_twin(source_type=SETTLE_SOURCE, base_id=base, date=tgl, sides=_settle_sides(
                a, tr, await money.akun_kas_bank(payer, rek[payer]), await money.akun_kas_bank(payee, rek[payee])))
        except twin.TwinJournalError as exc:
            raise AssetError(str(exc), 409) from exc
        # ── NIAT: klaim none → settling ───────────────────────────────────────────────────────────────────────────
        won = await db.fin_fixed_assets.find_one_and_update(
            {"id": asset_id, "status": "transferred", "transfer.settled": {"$ne": True},
             "transfer.settle_status": {"$in": ["none", None]}},
            {"$set": {"transfer.settle_status": "settling", "transfer.settle_lease_until": _lease_until(),
                      "transfer.settle_by": actor.get("name", ""), "updated_at": now_iso()}},
            projection={"_id": 0, "id": 1})
        if not won:
            raise AssetError(f"Aset {nomor} sedang diproses. Muat ulang.")

    async def lepas() -> None:
        await db.fin_fixed_assets.update_one({"id": asset_id, "transfer.settle_status": "settling"},
                                             {"$set": {"transfer.settle_lease_until": "", "updated_at": now_iso()}})
    # ── EFEK: kas kembar (id tetap per arah; ulang = kas yang sama) ──────────────────────────────────────────────
    try:
        cash = await money.twin_cash(
            out_entity=payer, in_entity=payee, amount=price,
            category="pindah aset tetap antar-PT",
            description=(f"Pembayaran pindah aset {a.get('number')} ke {tr.get('from_entity_name')}"
                         + (f" — {note}" if note else "")),
            ref_type="fixed_asset_transfer", ref_id=asset_id, actor=actor.get("name", "system"))
    except Exception:
        await lepas()
        raise
    # ── JURNAL: dua buku, status per sisi di aset ────────────────────────────────────────────────────────────────
    sides = _settle_sides(a, tr, await money.akun_kas_dokumen(cash["out"]), await money.akun_kas_dokumen(cash["in"]))
    hasil = await twin.post_twin(source_type=SETTLE_SOURCE, base_id=base, date=tgl, sides=sides,
                                 created_by=actor.get("name", "system"))
    if any(v.get("status") == "failed" for v in hasil.values()):
        await lepas()
        raise AssetError(f"Kas pembayaran pindah aset {nomor} sudah tercatat, tetapi jurnalnya belum lengkap. "
                         f"{await twin.warning_for(hasil, sides)}", 409)
    # ── SELESAI ──────────────────────────────────────────────────────────────────────────────────────────────────
    await db.fin_fixed_assets.update_one({"id": asset_id}, {"$set": {
        "transfer.settled": True, "transfer.settle_status": "settled", "transfer.settled_at": now_iso(),
        "transfer.settled_by": actor.get("name", ""), "transfer.settle_lease_until": "",
        "transfer.cash_txn_ids": [cash["out"]["id"], cash["in"]["id"]],
        "updated_at": now_iso()}})
    await money.refresh_pair_exposure(payee, payer)
    await money.sync_non_trade_elimination(
        source_key=f"asset:{asset_id}", pair_id=asset_id, from_entity=payee,
        to_entity=payer, outstanding=0.0, label=f"pindah aset {a.get('number')}")
    return {"asset_id": asset_id, "paid": price,
            "cash": [cash["out"]["number"], cash["in"]["number"]]}


async def resume_settlement(asset: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """Jalur Ulang Posting jenis `fixed_asset_settle_payer` / `_payee`: pelunasan yang kasnya sudah tercatat tetapi
    jurnalnya belum lengkap diteruskan (kas dipakai ulang, sisi yang kurang diterbitkan)."""
    if ((asset.get("transfer") or {}).get("settle_status")) != "settling":
        raise RuntimeError("Pembayaran pindah aset ini tidak sedang menunggu jurnal. Muat ulang.")
    await settle_transfer(asset["id"], actor)
