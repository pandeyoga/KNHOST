"""PM-T1 — membuat & mengubah rekening kas/bank: langsung berlaku, atau diajukan dan menunggu orang kedua.

Rekening menyimpan atas nama, peruntukan, cara bayar yang dilayani, bawaan penerimaan per (PT, cara bayar), dan tanda
"tampil di dokumen pelanggan" (`docs/blueprint/unit/PM-T1.md`). Perubahan field PEKA (nomor, bank, atas nama,
peruntukan, cara bayar, bawaan, tampil di dokumen, aktif/nonaktif) dan pembuatan rekening mengikuti kontrol dua orang
`kontrol.ubah_rekening.*` (KF-T6, bawaan satu orang): bila orang kedua dibutuhkan, perubahan TIDAK diterapkan dan
disimpan di `bank_account_changes` berstatus `menunggu`; orang lain pemegang `cash.approve` memutusnya. Setiap perubahan
yang diterapkan juga dicatat (`diterapkan`) supaya riwayat siapa mengubah apa ada di satu tempat.
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc
from db import db
from services import bank_service as bs
from services import payment_method_service as pms

COLL = "bank_account_changes"
AKSI = "ubah_rekening"
PEKA = ("account_number", "bank_name", "holder_name", "purposes", "payment_method_codes",
        "default_receiving_methods", "show_on_documents", "is_active",
        "cash_type", "dana_tetap", "location_id")   # Kas & Bank 3 — jenis kas, dana tetap, lokasi rekening
#: Kas & Bank 3 — field kas rekening (diperiksa `bank_service.periksa_bidang_kas`; jenis kas terkunci sesudah ada kas).
KAS = ("cash_type", "dana_tetap", "location_id")
#: Field dasar yang ikut dicatat (bukan peka: berlaku langsung walau dua orang).
DASAR = ("name", "bank_name", "account_number", "opening_balance", "is_active", "note")
PESAN_DIPUTUS = "Perubahan rekening ini sudah diputus atau datanya sudah berubah. Ajukan ulang."
PESAN_DOKUMEN = "Rekening yang tampil di dokumen wajib punya atas nama dan nomor rekening."
#: Kas & Bank 3 (C1, ketetapan R4) — di PT berkas kasir bawaan tunai selalu rekening kas kasir (`bs._bawaan_tunai_kasir`).
PESAN_BAWAAN_TUNAI_KASIR = ("PT ini punya rekening kas kasir, jadi bawaan penerimaan tunai selalu rekening kas kasir. "
                            "Hapus tunai dari bawaan penerimaan rekening ini.")
LABEL_PERUNTUKAN = {"penerimaan_pelanggan": "Penerimaan pelanggan", "pembayaran_pemasok": "Pembayaran pemasok",
                    "gaji": "Gaji", "operasional": "Operasional"}


async def _periksa_bawaan_tunai(entity_id: str, account_id: str, cash_type: str, methods: List[str]) -> None:
    """Kas & Bank 3 (ketetapan R4) — bawaan tunai di rekening BUKAN kas kasir tidak akan berlaku bila PT punya kas kasir
    penerima cara bayar itu; ditolak berkalimat daripada disimpan tanpa efek. Rekening kas kasir & PT tanpa kasir: lolos."""
    if cash_type == "kas_kasir" or not methods:
        return
    tunai = [m for m in methods if await pms.is_cash(entity_id, m)]
    if not tunai:
        return
    for a in await bs.rekening_pt(entity_id):
        e = a["_efektif"]
        if a["id"] != account_id and bs._aktif(a) and bs.account_cash_type(a) == "kas_kasir" \
                and "penerimaan_pelanggan" in e["purposes"] \
                and any(m in e["payment_method_codes"] for m in tunai):   # noqa: SLF001
            raise _galat(400, PESAN_BAWAAN_TUNAI_KASIR)


def _galat(status: int, pesan: str) -> HTTPException:
    return HTTPException(status_code=status, detail=pesan)


async def periksa_isian(entity_id: str, account_type: str, bidang: Dict[str, Any], *,
                        account_number: str) -> Dict[str, Any]:
    """Periksa & bersihkan lima field PM-T1 (nilai sesudah digabung). Galat → 400 berkalimat (tabel Galat spesifikasi)."""
    holder = str(bidang.get("holder_name") or "").strip()
    purposes = [str(p).strip() for p in (bidang.get("purposes") or []) if str(p).strip()]
    for p in purposes:
        if p not in bs.PERUNTUKAN:
            raise _galat(400, f"Peruntukan rekening tidak dikenal: {p}.")
    purposes = [p for p in bs.PERUNTUKAN if p in purposes]

    async def _kode(kata: Any) -> Tuple[str, Dict[str, Any]]:
        try:
            kode = pms.normalize(kata)
        except ValueError:
            await pms.muat_kamus()
            try:
                kode = pms.normalize(kata)
            except ValueError:
                raise _galat(400, f"Rekening ini tidak melayani cara bayar {str(kata or '').strip()}.")
        row = await pms._baris(entity_id, kode) or pms.BENIH_BY_CODE.get(kode) or {}   # noqa: SLF001
        return kode, row

    codes: List[str] = []
    for kata in bidang.get("payment_method_codes") or []:
        kode, row = await _kode(kata)
        if not pms.jenis_rekening_cocok(row, account_type):
            raise _galat(400, f"Rekening ini tidak melayani cara bayar {row.get('name') or kode}.")
        if kode not in codes:
            codes.append(kode)
    defaults: List[str] = []
    for kata in bidang.get("default_receiving_methods") or []:
        kode, row = await _kode(kata)
        if kode not in codes:
            raise _galat(400, f"Rekening ini tidak melayani cara bayar {row.get('name') or kode}.")
        if kode not in defaults:
            defaults.append(kode)
    show = bool(bidang.get("show_on_documents"))
    if show and (not holder or not str(account_number or "").strip() or account_type != "bank"):
        raise _galat(400, PESAN_DOKUMEN)
    return {"holder_name": holder, "purposes": purposes, "payment_method_codes": codes,
            "default_receiving_methods": defaults, "show_on_documents": show}


async def _nama_pt(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "name": 1,
                                                                 "legal_name": 1}) or {}
    return e.get("short_name") or e.get("name") or e.get("legal_name") or entity_id


async def _catat(*, entity_id: str, account_id: str, account_name: str, action: str,
                 changes: List[Dict[str, Any]], payload: Dict[str, Any], reason: str, status: str,
                 actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = {"id": new_id("bac"), "entity_id": entity_id, "entity_name": await _nama_pt(entity_id),
           "account_id": account_id, "account_name": account_name, "action": action, "changes": changes,
           "payload": payload, "reason": (reason or "").strip(), "status": status,
           "requested_by": actor.get("name", ""), "requested_by_id": actor.get("id", ""),
           "decided_by": actor.get("name", "") if status == "diterapkan" else "",
           "decided_by_id": actor.get("id", "") if status == "diterapkan" else "",
           "decision_note": "", "created_at": now_iso(),
           "decided_at": now_iso() if status == "diterapkan" else ""}
    await db[COLL].insert_one(dict(doc))
    return safe_doc(doc)


async def _dua_orang(entity_id: str) -> bool:
    from services.dual_control import butuh_orang_kedua
    return await butuh_orang_kedua("ubah_rekening", entity_id, 0)   # ASUMSI unit: perubahan rekening tidak bernominal


# ── Buat ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _payload_buat(payload) -> Dict[str, Any]:
    d = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
    return {k: d.get(k) for k in ("name", "account_type", "cash_type", "bank_name", "account_number", "entity_id",
                                  "opening_balance", "currency", "note", "gl_account_code",
                                  "dana_tetap", "location_id")}   # Kas & Bank 3


async def buat(payload, actor: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """POST /api/bank-accounts. 200 + rekening, atau 202 + `{change}` bila orang kedua dibutuhkan."""
    eid = payload.entity_id
    if payload.account_type not in bs.VALID_ACCOUNT_TYPES:
        raise _galat(400, "Jenis rekening harus rekening bank atau kas tunai.")
    from services.payment_method_service import kode_awal_rekening
    bidang = await periksa_isian(eid, payload.account_type, {
        "holder_name": payload.holder_name,
        "purposes": list(bs.PERUNTUKAN) if payload.purposes is None else payload.purposes,
        "payment_method_codes": (kode_awal_rekening(payload.account_type) if payload.payment_method_codes is None
                                 else payload.payment_method_codes),
        "default_receiving_methods": payload.default_receiving_methods or [],
        "show_on_documents": payload.show_on_documents}, account_number=payload.account_number)
    try:   # Kas & Bank 1 — akun buku besar pilihan diperiksa saat diajukan (dan sekali lagi saat diterapkan)
        await bs.periksa_akun_rekening_baru(eid, getattr(payload, "gl_account_code", "") or "")
        # Kas & Bank 3 — jenis kas, dana tetap, lokasi diperiksa saat diajukan (dan sekali lagi saat diterapkan).
        kas = await bs.periksa_bidang_kas({"entity_id": eid, "account_type": payload.account_type, "is_active": True,
                                           "cash_type": getattr(payload, "cash_type", "") or "",
                                           "dana_tetap": getattr(payload, "dana_tetap", 0) or 0,
                                           "location_id": getattr(payload, "location_id", "") or ""})
    except ValueError as exc:
        raise _galat(400, str(exc))
    await _periksa_bawaan_tunai(eid, "", kas["cash_type"], bidang["default_receiving_methods"])
    dasar = {**_payload_buat(payload), "dana_tetap": kas["dana_tetap"], "location_id": kas["location_id"]}
    # Tinjauan akhir KB3 (Important 4) — penyetuju melihat JENIS KAS rekening tunai baru (kas kasir memindahkan bawaan
    # penerimaan tunai PT, R4; jenisnya terkunci begitu ada kas): jenis yang akan berlaku, termasuk kas kecil bila
    # kosong. Rekening bank memakai isian apa adanya (kosong → tanpa baris, seperti dulu). `dasar` (yang diterapkan)
    # tidak berubah.
    tampil = {**dasar, **bidang}
    if payload.account_type == "cash":
        tampil["cash_type"] = kas["cash_type"]
    changes = [{"field": f, "from": None, "to": v} for f, v in tampil.items()
               if f not in ("entity_id", "currency") and v not in (None, "", [], False, 0, 0.0)]
    if await _dua_orang(eid):
        ch = await _catat(entity_id=eid, account_id="", account_name=dasar["name"], action="buat", changes=changes,
                          payload={**dasar, **bidang}, reason=getattr(payload, "reason", "") or "",
                          status="menunggu", actor=actor)
        return 202, {"change": ch}
    acc = await _terapkan_buat({**dasar, **bidang}, actor)
    await _catat(entity_id=eid, account_id=acc["id"], account_name=acc["name"], action="buat", changes=changes,
                 payload={**dasar, **bidang}, reason=getattr(payload, "reason", "") or "", status="diterapkan",
                 actor=actor)
    return 200, acc


async def _terapkan_buat(isi: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    from schemas import BankAccountCreate
    eid = isi["entity_id"]
    await bs.isi_awal_bidang_rekening(tulis=True, entity_id=eid)   # rekening lama PT ini: nilai berlaku → tersimpan
    payload = BankAccountCreate(**{k: v for k, v in isi.items() if k in BankAccountCreate.model_fields})
    payload.entity_id = eid
    try:
        return await bs.create_account(payload, actor, bidang={f: isi[f] for f in bs.BIDANG_PM})
    except ValueError as exc:
        raise _galat(400, str(exc))


# ── Ubah ─────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _nilai_sekarang(account_id: str, entity_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(dokumen tersimpan, nilai yang BERLAKU untuk DASAR + BIDANG_PM)."""
    accs = await bs.rekening_pt(entity_id)
    acc = next((a for a in accs if a["id"] == account_id), None)
    if not acc:
        raise _galat(404, "Akun tidak ditemukan")
    nilai = {"name": acc.get("name", ""), "bank_name": acc.get("bank_name", ""),
             "account_number": acc.get("account_number", ""),
             "opening_balance": round(float(acc.get("opening_balance") or 0), 2),
             "is_active": acc.get("is_active") is not False, "note": acc.get("note", ""), **acc["_efektif"],
             # Kas & Bank 3 — rekening lama tanpa bidang: jenis kas dari `account_type`, dana tetap 0, tanpa lokasi.
             "cash_type": bs.account_cash_type(acc), "dana_tetap": round(float(acc.get("dana_tetap") or 0), 2),
             "location_id": acc.get("location_id") or ""}
    acc.pop("_efektif", None)
    return acc, nilai


async def ubah(prev: Dict[str, Any], data: Dict[str, Any], actor: Dict[str, Any],
               reason: str = "") -> Tuple[int, Dict[str, Any]]:
    """PATCH /api/bank-accounts/{id}. 200 + rekening (langsung), atau 202 + `{change}`."""
    eid = prev.get("entity_id") or ""
    acc, lama = await _nilai_sekarang(prev["id"], eid)
    baru: Dict[str, Any] = {}
    for f in DASAR:
        if data.get(f) is not None:
            v = data[f]
            baru[f] = (round(float(v), 2) if f == "opening_balance" else bool(v) if f == "is_active"
                       else str(v).strip())
    pm = {f: (data[f] if data.get(f) is not None else lama[f]) for f in bs.BIDANG_PM}
    bersih = await periksa_isian(eid, acc.get("account_type", "bank"), pm,
                                 account_number=baru.get("account_number", lama["account_number"]))
    for f in bs.BIDANG_PM:
        if data.get(f) is not None:
            baru[f] = bersih[f]
    if any(data.get(f) is not None for f in (*KAS, "is_active")):
        # Kas & Bank 3 — jenis kas / dana tetap / lokasi: diperiksa pada nilai sesudah perubahan saat diajukan (dan
        # sekali lagi saat diterapkan, `bank_service.update_account`). Jenis kas terkunci bila rekening sudah punya kas.
        isian = {f: data[f] for f in KAS if data.get(f) is not None}
        try:
            kas = await bs.periksa_bidang_kas({**acc, **lama, **baru, **isian})
            if "cash_type" in isian and kas["cash_type"] != lama["cash_type"]:
                alasan = await bs.alasan_jenis_kas_terkunci(acc)
                if alasan:
                    raise ValueError(alasan)
        except ValueError as exc:
            raise _galat(400, str(exc))
        baru.update({f: kas[f] for f in isian})
    if "default_receiving_methods" in baru and baru["default_receiving_methods"] != lama["default_receiving_methods"]:
        await _periksa_bawaan_tunai(eid, prev["id"], baru.get("cash_type") or lama["cash_type"],
                                    baru["default_receiving_methods"])
    changes = [{"field": f, "from": lama.get(f), "to": v} for f, v in baru.items() if v != lama.get(f)]
    if not changes:
        txns = await bs._txns_for(prev["id"])   # noqa: SLF001
        return 200, {**bs._enrich(acc, txns), **{f: lama[f] for f in bs.BIDANG_PM}}   # noqa: SLF001
    if any(c["field"] in PEKA for c in changes) and await _dua_orang(eid):
        ch = await _catat(entity_id=eid, account_id=prev["id"], account_name=lama["name"], action="ubah",
                          changes=changes, payload={c["field"]: c["to"] for c in changes}, reason=reason,
                          status="menunggu", actor=actor)
        return 202, {"change": ch}
    hasil = await _terapkan_ubah(prev["id"], eid, changes, syarat_dari=None, actor=actor)
    await _catat(entity_id=eid, account_id=prev["id"], account_name=hasil.get("name", lama["name"]), action="ubah",
                 changes=changes, payload={c["field"]: c["to"] for c in changes}, reason=reason,
                 status="diterapkan", actor=actor)
    return 200, hasil


async def _terapkan_ubah(account_id: str, entity_id: str, changes: List[Dict[str, Any]],
                         syarat_dari: Optional[Dict[str, Any]],
                         actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    await bs.isi_awal_bidang_rekening(tulis=True, entity_id=entity_id)
    try:
        acc = await bs.update_account(account_id, {c["field"]: c["to"] for c in changes}, syarat=syarat_dari,
                                      actor=actor)
    except bs.RekeningBerubah:
        raise _galat(409, PESAN_DIPUTUS)
    except ValueError as exc:
        raise _galat(400, str(exc))
    if acc is None:
        raise _galat(404, "Akun tidak ditemukan")
    return acc


# ── Daftar & keputusan ───────────────────────────────────────────────────────────────────────────────────────────
async def daftar(scope: Dict[str, Any], status: str, page: int, page_size: int,
                 actor: Dict[str, Any]) -> Dict[str, Any]:
    from services import dual_control as dc
    q = dict(scope)
    if status:
        q["status"] = status
    total = await db[COLL].count_documents(q)
    page = max(1, int(page or 1))
    size = max(1, min(int(page_size or 25), 100))
    rows = await db[COLL].find(q, {"_id": 0, "payload": 0}).sort("created_at", -1).skip((page - 1) * size) \
        .limit(size).to_list(size)
    for r in rows:
        r["label_changes"] = [{**c, "label": LABEL_BIDANG.get(c["field"], c["field"])} for c in r.get("changes") or []]
        if r.get("status") == "menunggu":
            cek = await dc.periksa(AKSI, r, actor, r.get("entity_id") or "",
                                   pengaju=[r.get("requested_by_id"), r.get("requested_by")])
            r["blocked_reason"] = cek["pesan"]
    return {"items": rows, "total": total, "page": page, "page_size": size}


LABEL_BIDANG = {"name": "Nama akun", "bank_name": "Bank", "account_number": "Nomor rekening",
                "opening_balance": "Saldo awal", "is_active": "Aktif", "note": "Catatan",
                "holder_name": "Atas nama", "purposes": "Dipakai untuk", "payment_method_codes": "Cara bayar dilayani",
                "default_receiving_methods": "Bawaan penerimaan", "show_on_documents": "Tampil di dokumen pelanggan",
                "account_type": "Jenis", "cash_type": "Jenis kas",
                "gl_account_code": "Akun buku besar",   # Kas & Bank 1 — akun bagan PT pilihan saat rekening dibuat
                "dana_tetap": "Dana tetap", "location_id": "Lokasi"}   # Kas & Bank 3


async def putuskan(ch: Dict[str, Any], decision: str, note: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """POST /api/bank-account-changes/{id}/decision — setujui (terapkan, bila nilai lama masih sama) atau tolak."""
    from services.dual_control import tolak_bila_pelaku_sama
    if ch.get("status") != "menunggu":
        raise _galat(409, PESAN_DIPUTUS)
    if decision not in ("approve", "reject"):
        raise _galat(400, "Keputusan harus setujui atau tolak.")
    eid = ch.get("entity_id") or ""
    await tolak_bila_pelaku_sama("ubah_rekening", ch, actor, eid,
                                 pengaju=[ch.get("requested_by_id"), ch.get("requested_by")])
    putus = {"decided_by": actor.get("name", ""), "decided_by_id": actor.get("id", ""),
             "decision_note": (note or "").strip(), "decided_at": now_iso()}
    if decision == "reject":
        if not putus["decision_note"]:
            raise _galat(400, "Alasan penolakan wajib diisi.")
        res = await db[COLL].find_one_and_update({"id": ch["id"], "status": "menunggu"},
                                                 {"$set": {"status": "ditolak", **putus}}, projection={"_id": 0},
                                                 return_document=True)
        if not res:
            raise _galat(409, PESAN_DIPUTUS)
        return {"change": safe_doc(res)}
    syarat: Optional[Dict[str, Any]] = None
    if ch.get("action") == "ubah":
        await bs.isi_awal_bidang_rekening(tulis=True, entity_id=eid)
        try:
            acc, sekarang = await _nilai_sekarang(ch.get("account_id", ""), eid)
        except HTTPException:
            raise _galat(409, PESAN_DIPUTUS)
        for c in ch.get("changes") or []:
            if sekarang.get(c["field"]) != c.get("from"):
                raise _galat(409, PESAN_DIPUTUS)
        syarat = {c["field"]: acc[c["field"]] for c in ch.get("changes") or [] if c["field"] in acc}
    klaim = await db[COLL].find_one_and_update({"id": ch["id"], "status": "menunggu"},
                                               {"$set": {"status": "diterapkan", **putus}}, projection={"_id": 0},
                                               return_document=True)
    if not klaim:
        raise _galat(409, PESAN_DIPUTUS)
    try:
        if ch.get("action") == "ubah":
            hasil = await _terapkan_ubah(ch["account_id"], eid, ch.get("changes") or [], syarat_dari=syarat,
                                         actor=actor)
        else:
            hasil = await _terapkan_buat(dict(ch.get("payload") or {}), actor)
            await db[COLL].update_one({"id": ch["id"]}, {"$set": {"account_id": hasil["id"]}})
            klaim["account_id"] = hasil["id"]
    except BaseException:
        await db[COLL].update_one({"id": ch["id"], "status": "diterapkan"},
                                  {"$set": {"status": "menunggu", "decided_by": "", "decided_by_id": "",
                                            "decision_note": "", "decided_at": ""}})
        raise
    # Temuan tangkapan A (R7) — penetapan kas lama yang dipicu perubahan ini ikut di jawaban (juga di `account`).
    return {"change": safe_doc(klaim), "account": hasil,
            **{k: hasil[k] for k in ("kas_lama_ditetapkan", "kas_lama_tertinggal") if k in hasil}}


async def daftar_penerima(entity_id: str, method: str) -> List[Dict[str, Any]]:
    """GET /api/bank-accounts/receiving — rekening aktif PT yang dipakai menerima uang pelanggan dan melayani cara bayar
    itu. Tanpa saldo.

    Kas & Bank 3 (C1, §5.1, §7.8 butir 5, ketetapan R4) — `is_default` dari bawaan yang BERLAKU (`bs.rekening_pt`):
    di PT berkas kasir, kas kasir penerima tunggal selalu bawaan tunai (bawaan tunai tersimpan di rekening bukan kasir
    tidak berlaku); dua kasir atau lebih → bawaan tersimpan di salah satu kasir, selain itu tanpa bawaan (kasir memilih).
    PT tanpa kas kasir = persis seperti sebelumnya."""
    kode = await pms.kode_400(entity_id, method)
    out = []
    for a in await bs.rekening_pt(entity_id):
        e = a["_efektif"]
        if not bs._aktif(a) or "penerimaan_pelanggan" not in e["purposes"] \
                or kode not in e["payment_method_codes"]:   # noqa: SLF001
            continue
        out.append({"id": a["id"], "name": a.get("name", ""), "bank_name": a.get("bank_name", ""),
                    "account_number": a.get("account_number", ""), "holder_name": e["holder_name"],
                    "is_default": kode in e["default_receiving_methods"]})
    out.sort(key=lambda r: (not r["is_default"], r["name"]))
    return out
