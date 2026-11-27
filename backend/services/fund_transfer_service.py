"""Kas & Bank bagian 1 (D2) — dokumen **Pindah Dana** (`fund_transfers`, nomor `PDN-`): uang pindah antar dua rekening
SATU PT sebagai pasangan kas biasa lewat pintu kas tunggal `cash_ledger.create_cash` (antar-PT tetap lewat Antar-PT).

Rancangan: `docs/superpowers/specs/2026-11-27-kas-bank-1-rekening-pindah-dana-design.md` §5.2, §6, §7 butir 4–5, 7.

Kas dokumen — semua `ref_type="fund_transfer"`, `ref_id` = id dokumen, id kas tetap dari `seq` (kirim ulang memakai kas
yang sama, tidak menggandakan):
  * `kirim`  kas KELUAR rekening asal, lawan akun dana dalam perjalanan (`kas_bank.kas_transit`, bawaan 1-1150):
             Dr transit / Cr kas asal;
  * `biaya`  kas KELUAR rekening asal sebesar biaya transfer (hanya bila > 0), lawan akun beban bank
             (`kas_bank.beban_bank`): Dr beban bank / Cr kas asal;
  * `terima` kas MASUK rekening tujuan, lawan akun transit yang SAMA dengan kas `kirim`: Dr kas tujuan / Cr transit.
Lawan akun dinyatakan lewat `contra_account_code` dokumen kas; akun kas tiap jurnal dipilih pintu kas lewat
`gl_service.akun_kas` (akun lama di PT yang belum memakai akun per rekening, sub-akun rekening di PT yang sudah) — modul
ini tidak pernah menulis kode akun kas dan tidak memposting jurnal sendiri.

* **Sekali jalan** (tanggal terima kosong / sama dengan tanggal kirim): ketiga kas terbit bersamaan → jurnal bersih
  Dr tujuan / Cr asal (transit kembali 0) + Dr beban bank / Cr asal; status `selesai`.
* **Dua tahap** (tanggal terima > tanggal kirim): saat terbit hanya `kirim` (+ `biaya`), status `dalam_perjalanan`;
  aksi **Terima** (tanggal uang diterima, ≥ tanggal kirim) menerbitkan `terima`, status `selesai`.
* **Kontrol** `kontrol.pindah_dana` (jumlah orang + batas nominal per PT, bawaan satu orang): bila butuh orang kedua,
  dokumen `menunggu_persetujuan` dan kas baru terbit saat disetujui orang lain (`dual_control.tolak_bila_pelaku_sama`,
  pembanding = pembuat).
* **Batal** (alasan ≥ 5 huruf): ditolak bila salah satu kas dokumen sudah dicocokkan dengan mutasi bank ("lepas dulu di
  Rekonsiliasi"); semua kas tidak-batal dibalik lewat pembalik kas yang ada (`gl_service.post_cash_void` di pintu
  tahan-gagal, tanggal `posting_registry.tanggal_pembalik`), terakhir-terbit dulu. Dokumen yang masih menunggu (tanpa
  kas) cukup ditandai batal. Pembalik gagal di tengah → dokumen tetap `batal`, `batal_gl_status: failed`, tampil di
  Posting Gagal (jenis `fund_transfer_cancel`); ulang (atau Batal lagi) meneruskan kas yang belum dibalik.

Urutan tiap aksi (`02_STANDAR.md` §1): PERIKSA tanpa tulisan (rekening, nominal, tanggal, periode, akun jurnal) → KLAIM
(`atomic_claim.claim` berprasyarat status) → EFEK (kas ber-id tetap) → SELESAI (`finish_set`, kunci dicabut). Kirim
ulang aksi yang sama → status sudah berubah → 409; kas tidak pernah ganda.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import from_cents, new_id, now_iso, safe_doc, to_cents
from db import db

COLL = "fund_transfers"
REF_TYPE = "fund_transfer"
MENUNGGU, PERJALANAN, SELESAI, BATAL = "menunggu_persetujuan", "dalam_perjalanan", "selesai", "batal"
STATUS_LABEL = {MENUNGGU: "Menunggu persetujuan", PERJALANAN: "Dalam perjalanan", SELESAI: "Selesai", BATAL: "Batal"}
HIDUP = (MENUNGGU, PERJALANAN, SELESAI)
SEQ_KIRIM, SEQ_BIAYA, SEQ_TERIMA = "kirim", "biaya", "terima"
URUT_SEQ = (SEQ_KIRIM, SEQ_BIAYA, SEQ_TERIMA)
PERAN_KAS = {SEQ_KIRIM: "Kas keluar rekening asal", SEQ_BIAYA: "Biaya transfer",
             SEQ_TERIMA: "Kas masuk rekening tujuan"}
ALASAN_MIN = 5   # K-14 (26 Okt) — alasan minimum seragam 5 huruf
EPS = 0.005

PESAN_TIDAK_ADA = "Pindah Dana tidak ditemukan."
PESAN_PILIH = "Pilih rekening asal dan rekening tujuan."
PESAN_SAMA = "Rekening asal dan tujuan tidak boleh sama."
PESAN_LINTAS_PT = ("Rekening asal dan tujuan harus milik PT yang sama. Pindah dana antar-PT dicatat lewat menu "
                   "Antar-PT.")
PESAN_NOMINAL = "Nominal pindah dana harus lebih dari 0."
PESAN_BIAYA = "Biaya transfer tidak boleh negatif."
PESAN_TANGGAL = "Tanggal terima tidak boleh sebelum tanggal kirim."
PESAN_ALASAN = f"Alasan pembatalan wajib diisi (minimal {ALASAN_MIN} huruf)."


def _galat(status: int, pesan: str) -> HTTPException:
    return HTTPException(status_code=status, detail=pesan)


def _f(x: Any) -> float:
    return round(float(x or 0), 2)


async def _nama_pt(entity_id: str) -> str:
    from services.cash_ledger import _nama_pt as nama
    return await nama(entity_id)


def _tanggal(nilai: Any, label: str) -> str:
    """Tanggal buku WIB `YYYY-MM-DD` (kosong = hari ini). Bentuk tak dikenal → 400."""
    from services.book_date import tanggal_buku
    try:
        return tanggal_buku(nilai)
    except (TypeError, ValueError):
        raise _galat(400, f"Tanggal {label} tidak dikenali: {nilai}.") from None


def _isi(payload: Any) -> Dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    return dict(payload or {})


def _jejak(aksi: str, actor: Dict[str, Any], catatan: str = "") -> Dict[str, Any]:
    return {"aksi": aksi, "oleh": (actor or {}).get("name", ""), "oleh_id": (actor or {}).get("id", ""),
            "pada": now_iso(), "catatan": catatan}


# ── PERIKSA (tanpa tulisan) ──────────────────────────────────────────────────────────────────────────────────────────
async def _rekening(rid: str, peran: str) -> Dict[str, Any]:
    acc = await db.bank_accounts.find_one({"id": rid or "__none__"}, {"_id": 0})
    if not acc:
        raise _galat(400, f"Rekening {peran} tidak ditemukan.")
    return acc


async def _periksa_milik(entity_id: str, acc: Dict[str, Any]) -> None:
    """Rekening `acc` milik PT `entity_id` dan aktif — selain itu 400 berkalimat."""
    from services import bank_service as bs
    nama = acc.get("name") or acc.get("id")
    if (acc.get("entity_id") or "") != entity_id:
        raise _galat(400, f"Rekening {nama} bukan rekening {await _nama_pt(entity_id)}.")
    if not bs._aktif(acc):
        raise _galat(400, f"Rekening {nama} tidak aktif. Aktifkan dulu di Rekening & Saldo atau pilih rekening lain.")


async def _periksa_pasangan(entity_id: str, asal_id: str, tujuan_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Rekening asal ≠ tujuan, keduanya ada, satu PT (= PT dokumen), aktif."""
    asal_id, tujuan_id = (asal_id or "").strip(), (tujuan_id or "").strip()
    if not asal_id or not tujuan_id:
        raise _galat(400, PESAN_PILIH)
    if asal_id == tujuan_id:
        raise _galat(400, PESAN_SAMA)
    asal, tujuan = await _rekening(asal_id, "asal"), await _rekening(tujuan_id, "tujuan")
    if (asal.get("entity_id") or "") != (tujuan.get("entity_id") or ""):
        raise _galat(400, PESAN_LINTAS_PT)
    for acc in (asal, tujuan):
        await _periksa_milik(entity_id, acc)
    return asal, tujuan


async def _akun_lawan(entity_id: str) -> Dict[str, str]:
    """Akun lawan kas Pindah Dana menurut Pemetaan Akun PT (dibaca saat kas terbit)."""
    from services import gl_mapping_service as glm
    return {"transit": await glm.account_for("kas_bank.kas_transit", entity_id),
            "beban_bank": await glm.account_for("kas_bank.beban_bank", entity_id)}


def _rencana(doc: Dict[str, Any], tahap: str, akun: Dict[str, str]) -> List[Dict[str, Any]]:
    """Kas yang akan terbit untuk `tahap` (`terbit` | `terima`). Murni."""
    nomor = doc.get("number") or ""
    asal_n, tujuan_n = doc.get("rekening_asal_nama") or "", doc.get("rekening_tujuan_nama") or ""
    catatan = f" — {doc['catatan']}" if doc.get("catatan") else ""
    transit = doc.get("akun_transit") or akun["transit"]
    out: List[Dict[str, Any]] = []
    if tahap == "terbit":
        out.append({"seq": SEQ_KIRIM, "direction": "out", "amount": _f(doc["nominal"]),
                    "account_id": doc["rekening_asal_id"], "txn_date": doc["tanggal_kirim"], "contra": transit,
                    "category": "pindah dana", "description": f"Pindah dana {nomor} ke {tujuan_n}{catatan}"})
        if _f(doc.get("biaya")) > EPS:
            out.append({"seq": SEQ_BIAYA, "direction": "out", "amount": _f(doc["biaya"]),
                        "account_id": doc["rekening_asal_id"], "txn_date": doc["tanggal_kirim"],
                        "contra": akun["beban_bank"], "category": "biaya bank",
                        "description": f"Biaya transfer {nomor} ({asal_n} → {tujuan_n})"})
    if tahap == "terima" or (tahap == "terbit" and not doc.get("dua_tahap")):
        out.append({"seq": SEQ_TERIMA, "direction": "in", "amount": _f(doc["nominal"]),
                    "account_id": doc["rekening_tujuan_id"],
                    "txn_date": doc.get("tanggal_diterima") or doc["tanggal_terima"], "contra": transit,
                    "category": "pindah dana", "description": f"Pindah dana {nomor} dari {asal_n}{catatan}"})
    return out


async def _periksa_jurnal(entity_id: str, rencana: List[Dict[str, Any]]) -> None:
    """Jurnal kas yang akan terbit diperiksa dengan pemeriksa yang SAMA dengan `_insert_entry` (akun aktif & bisa
    diposting, periode) tanpa tulisan. Akun kas lewat `akun_kas` (pembantu yang sama dengan pintu kas)."""
    from services import bank_service as bs
    from services import gl_service as gl
    for r in rencana:
        acc = await db.bank_accounts.find_one({"id": r["account_id"]}, {"_id": 0}) or {}
        kas = await gl.akun_kas(entity_id, r["account_id"], bs.account_cash_type(acc))
        dr, cr = (kas, r["contra"]) if r["direction"] == "in" else (r["contra"], kas)
        lines = [{"account_code": dr, "debit": r["amount"], "credit": 0.0, "description": r["description"]},
                 {"account_code": cr, "debit": 0.0, "credit": r["amount"], "description": r["description"]}]
        try:
            await gl.preflight_entry(lines=lines, entity_id=entity_id, date=r["txn_date"],
                                     source_type="cash_transaction")
        except gl.ClosedPeriodError as exc:
            raise _galat(409, str(exc)) from exc
        except ValueError as exc:   # JournalValidationError dkk.
            raise _galat(409, f"Jurnal Pindah Dana belum bisa diterbitkan: {exc}") from exc


async def _ambil(doc_id: str) -> Dict[str, Any]:
    doc = await db[COLL].find_one({"id": doc_id or "__none__"}, {"_id": 0})
    if not doc:
        raise _galat(404, PESAN_TIDAK_ADA)
    return doc


def _pesan_status(doc: Dict[str, Any], aksi: str) -> str:
    nomor, st = doc.get("number") or doc.get("id"), doc.get("status")
    if st == BATAL:
        return f"Pindah Dana {nomor} sudah dibatalkan."
    if aksi == "terima":
        if st == SELESAI:
            return f"Pindah Dana {nomor} sudah diterima."
        if st == MENUNGGU:
            return f"Pindah Dana {nomor} belum disetujui, jadi belum bisa diterima."
    return f"Pindah Dana {nomor} berstatus {STATUS_LABEL.get(st, st)}, jadi tidak bisa disetujui."


def _pesan_berubah(doc: Dict[str, Any]) -> str:
    """Kalah klaim (status berubah di antara PERIKSA dan KLAIM)."""
    return f"Pindah Dana {doc.get('number') or doc.get('id')} baru saja diubah orang lain. Muat ulang lalu periksa."


# ── Kas & ringkasan jurnal ───────────────────────────────────────────────────────────────────────────────────────────
async def _kas_dokumen(doc_id: str) -> List[Dict[str, Any]]:
    """Kas dokumen (semua status), urut kirim → biaya → terima."""
    rows = [t async for t in db.cash_transactions.find({"ref_type": REF_TYPE, "ref_id": doc_id}, {"_id": 0})]
    return sorted(rows, key=lambda t: (URUT_SEQ.index(t["seq"]) if t.get("seq") in URUT_SEQ else 9,
                                       t.get("created_at") or ""))


def _ringkas_gl(kas: Iterable[Dict[str, Any]]) -> Dict[str, str]:
    gagal = [t for t in kas if t.get("status") != "void" and t.get("gl_status") == "failed"]
    if gagal:
        return {"gl_status": "failed",
                "gl_error": "; ".join(f"{t.get('number', '')}: {t.get('gl_error', '')}" for t in gagal)[:300]}
    return {"gl_status": "posted", "gl_error": ""}


async def segarkan_jurnal(doc_id: str) -> None:
    """Ringkasan jurnal kas di dokumen (`gl_status`/`gl_error`) dibaca ulang dari kasnya — dipanggil ulang posting kas
    dari panel Posting Gagal (`posting_registry._retry_cash`)."""
    if await db[COLL].find_one({"id": doc_id or "__none__"}, {"_id": 0, "id": 1}):
        await db[COLL].update_one({"id": doc_id}, {"$set": {**_ringkas_gl(await _kas_dokumen(doc_id)),
                                                            "updated_at": now_iso()}})


async def _terbitkan(doc: Dict[str, Any], rencana: List[Dict[str, Any]], actor: Dict[str, Any]) -> Dict[str, str]:
    """Kas `rencana` lewat pintu kas tunggal. Jurnal gagal (`CashPostingError`) = kas TETAP tercatat (Posting Gagal);
    kas ditolak (`CashRejected`, mis. rekening dinonaktifkan di sela PERIKSA) dilempar ke pemanggil. → {seq: id kas}."""
    from services import cash_ledger
    ids: Dict[str, str] = {}
    for r in rencana:
        try:
            kas = await cash_ledger.create_cash(
                entity_id=doc["entity_id"], direction=r["direction"], amount=r["amount"], ref_type=REF_TYPE,
                ref_id=doc["id"], account_id=r["account_id"], seq=r["seq"], txn_date=r["txn_date"],
                category=r["category"], description=r["description"], actor=(actor or {}).get("name") or "system",
                contra_account_code=r["contra"], extra={"fund_transfer_number": doc.get("number") or ""})
        except cash_ledger.CashPostingError as exc:
            kas = exc.txn
        ids[r["seq"]] = kas.get("id") or ""
    return ids


# ── Pembentuk jawaban ────────────────────────────────────────────────────────────────────────────────────────────────
def _bentuk(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = safe_doc(dict(doc))
    d.pop("saga_lock", None)
    d["status_label"] = STATUS_LABEL.get(d.get("status"), d.get("status") or "")
    d["rekening_asal"] = d.get("rekening_asal_nama") or ""
    d["rekening_tujuan"] = d.get("rekening_tujuan_nama") or ""
    d["dalam_proses"] = bool(doc.get("saga_lock"))
    d["batal_tertunda"] = d.get("status") == BATAL and d.get("batal_gl_status") in ("pending", "failed")
    return d


async def rincian(doc_id: str, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dokumen + kasnya (peran, nomor, rekening, tanggal, status, jurnal, nominal tercocok) + penilaian kontrol dua
    orang untuk `actor` (tombol Setujui jujur: `kontrol.ditolak`/`pesan`)."""
    from services import dual_control
    doc = await _ambil(doc_id)
    out = _bentuk(doc)
    kas = await _kas_dokumen(doc_id)
    jids = [t.get("journal_entry_id") for t in kas if t.get("journal_entry_id")] + \
           [t.get("void_journal_entry_id") for t in kas if t.get("void_journal_entry_id")]
    nomor_je = {j["id"]: j.get("number", "") async for j in db.journal_entries.find(
        {"id": {"$in": jids}}, {"_id": 0, "id": 1, "number": 1})} if jids else {}
    nama_rek = {doc.get("rekening_asal_id"): doc.get("rekening_asal_nama"),
                doc.get("rekening_tujuan_id"): doc.get("rekening_tujuan_nama")}
    out["kas"] = [{"id": t["id"], "number": t.get("number", ""), "seq": t.get("seq", ""),
                   "peran": PERAN_KAS.get(t.get("seq"), t.get("seq", "")), "direction": t.get("direction"),
                   "amount": _f(t.get("amount")), "account_id": t.get("account_id", ""),
                   "account_name": nama_rek.get(t.get("account_id")) or "", "txn_date": t.get("txn_date", ""),
                   "status": t.get("status", ""), "gl_status": t.get("gl_status", ""),
                   "gl_error": t.get("gl_error", ""), "journal_entry_id": t.get("journal_entry_id", ""),
                   "journal_number": nomor_je.get(t.get("journal_entry_id"), ""),
                   "void_journal_entry_id": t.get("void_journal_entry_id", ""),
                   "void_journal_number": nomor_je.get(t.get("void_journal_entry_id"), ""),
                   "reconciled_amount": _f(t.get("reconciled_amount"))} for t in kas]
    if actor is not None:
        out["kontrol"] = await dual_control.periksa("pindah_dana", doc, actor, doc.get("entity_id") or "",
                                                    nominal=_f(doc.get("nominal")), pengaju=_pengaju(doc))
    return out


def _pengaju(doc: Dict[str, Any]) -> List[str]:
    """Pembanding kontrol dua orang = pembuat dokumen (id; nama hanya bila id kosong — nama bisa kembar)."""
    return [doc.get("created_by_id") or doc.get("created_by") or ""]


async def daftar(entity_ids: List[str], *, status: str = "", q: str = "", page: int = 1,
                 page_size: int = 25, actor: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """`GET /api/fund-transfers` — Pindah Dana PT dalam cakupan (terbaru dulu), berhalaman. `q` = nomor / catatan /
    nama rekening. Baris yang menunggu persetujuan membawa penilaian kontrol dua orang untuk `actor` (`kontrol`, sama
    dengan rincian) supaya tombol Setujui di daftar nonaktif dengan alasan tertulis (Tugas 6)."""
    from services import dual_control
    query: Dict[str, Any] = {"entity_id": {"$in": list(entity_ids or [])}}
    if status:
        query["status"] = status
    teks = (q or "").strip()
    if teks:
        rx = {"$regex": re.escape(teks), "$options": "i"}
        query["$or"] = [{"number": rx}, {"catatan": rx}, {"rekening_asal_nama": rx}, {"rekening_tujuan_nama": rx}]
    page, page_size = max(1, int(page or 1)), max(1, min(int(page_size or 25), 100))
    total = await db[COLL].count_documents(query)
    rows = await db[COLL].find(query, {"_id": 0}).sort([("tanggal_kirim", -1), ("created_at", -1), ("id", -1)]) \
        .skip((page - 1) * page_size).to_list(page_size)
    items = []
    for r in rows:
        d = _bentuk(r)
        if actor is not None and r.get("status") == MENUNGGU:
            d["kontrol"] = await dual_control.periksa("pindah_dana", r, actor, r.get("entity_id") or "",
                                                      nominal=_f(r.get("nominal")), pengaju=_pengaju(r))
        items.append(d)
    return {"items": items, "total": total, "page": page, "page_size": page_size,
            "has_more": page * page_size < total,
            "statuses": [{"value": k, "label": v} for k, v in STATUS_LABEL.items()]}


# ── Buat ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
async def buat(payload: Any, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/fund-transfers`. PT = `entity_id` isian (router sudah memastikan PT dalam penugasan). Kontrol dua
    orang → `menunggu_persetujuan` tanpa kas; selain itu kas langsung terbit (`dalam_perjalanan` / `selesai`)."""
    from services import dual_control
    from services.cash_entity_service import assert_owned
    from core_utils import next_doc_number
    p = _isi(payload)
    eid = assert_owned((p.get("entity_id") or "").strip(), what="Pindah Dana")
    # ── PERIKSA ──
    asal, tujuan = await _periksa_pasangan(eid, p.get("rekening_asal_id"), p.get("rekening_tujuan_id"))
    nominal, biaya = _f(p.get("nominal")), _f(p.get("biaya"))
    if nominal <= EPS:
        raise _galat(400, PESAN_NOMINAL)
    if biaya < 0:
        raise _galat(400, PESAN_BIAYA)
    kirim = _tanggal(p.get("tanggal_kirim"), "kirim")
    terima = _tanggal(p.get("tanggal_terima"), "terima") if str(p.get("tanggal_terima") or "").strip() else kirim
    if terima < kirim:
        raise _galat(400, PESAN_TANGGAL)
    now = now_iso()
    doc: Dict[str, Any] = {
        "id": new_id("pdn"), "number": "", "entity_id": eid, "status": MENUNGGU,
        "rekening_asal_id": asal["id"], "rekening_asal_nama": asal.get("name") or "",
        "rekening_tujuan_id": tujuan["id"], "rekening_tujuan_nama": tujuan.get("name") or "",
        "nominal": nominal, "biaya": biaya, "tanggal_kirim": kirim, "tanggal_terima": terima,
        "tanggal_diterima": "", "dua_tahap": terima > kirim, "catatan": str(p.get("catatan") or "").strip()[:500],
        "butuh_persetujuan": False, "kas_ids": {}, "akun_transit": "", "akun_beban_bank": "",
        "gl_status": "", "gl_error": "", "terbit_error": "",
        "created_by": (actor or {}).get("name") or "", "created_by_id": (actor or {}).get("id") or "",
        "created_at": now, "updated_at": now,
    }
    await _periksa_jurnal(eid, _rencana(doc, "terbit", await _akun_lawan(eid)))
    doc["butuh_persetujuan"] = await dual_control.butuh_orang_kedua("pindah_dana", eid, nominal)
    # ── NIAT ──
    doc["number"] = await next_doc_number(COLL, "number", "PDN-", entity_id=eid)
    doc["jejak"] = [_jejak("buat", actor, "menunggu persetujuan orang kedua" if doc["butuh_persetujuan"] else "")]
    await db[COLL].insert_one(dict(doc))
    if doc["butuh_persetujuan"]:
        return _bentuk(doc)
    return await _terbit(doc["id"], actor, disetujui=False)


# ── Setujui / terbit ─────────────────────────────────────────────────────────────────────────────────────────────────
async def setujui(doc_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/fund-transfers/{id}/approve` — orang kedua (bila `kontrol.pindah_dana` mensyaratkannya); kas terbit.
    Juga meneruskan dokumen menunggu yang kasnya gagal terbit (`terbit_error`)."""
    from services import dual_control
    doc = await _ambil(doc_id)
    if doc.get("status") != MENUNGGU:
        raise _galat(409, _pesan_status(doc, "setujui"))
    await dual_control.tolak_bila_pelaku_sama("pindah_dana", doc, actor, doc.get("entity_id") or "",
                                              nominal=_f(doc.get("nominal")), pengaju=_pengaju(doc))
    return await _terbit(doc_id, actor, disetujui=True)


async def _terbit(doc_id: str, actor: Dict[str, Any], *, disetujui: bool) -> Dict[str, Any]:
    """Kas tahap kirim (+ terima bila sekali jalan) terbit; status `dalam_perjalanan` / `selesai`."""
    from services import atomic_claim as _saga
    from services import cash_ledger
    doc = await _ambil(doc_id)
    eid = doc.get("entity_id") or ""
    # ── PERIKSA (rekening masih layak, periode & akun jurnal) ──
    if doc.get("status") != MENUNGGU:
        raise _galat(409, _pesan_status(doc, "setujui"))
    await _periksa_pasangan(eid, doc["rekening_asal_id"], doc["rekening_tujuan_id"])
    akun = await _akun_lawan(eid)
    # Percobaan terbit sebelumnya yang terhenti sudah menyimpan akun transitnya: kas berikutnya memakai akun yang sama
    # (kas `kirim` yang sudah ada tidak berubah), supaya transit dokumen ini tetap kembali nol walau pemetaan berubah.
    akun["transit"] = doc.get("akun_transit") or akun["transit"]
    rencana = _rencana(doc, "terbit", akun)
    await _periksa_jurnal(eid, rencana)
    # ── KLAIM ──
    nama = (actor or {}).get("name") or ""
    lk = await _saga.claim(COLL, doc_id, "fund_transfer_issue", precondition={"status": MENUNGGU}, actor=nama,
                           detail=_pesan_berubah(doc))
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        await db[COLL].update_one({"id": doc_id, f"{_saga.LOCK}.token": token},
                                  {"$set": {"akun_transit": akun["transit"], "updated_at": now_iso()}})
        doc = {**lk, "akun_transit": akun["transit"]}
        try:
            ids = await _terbitkan(doc, rencana, actor)
        except cash_ledger.CashRejected as exc:
            sudah = [t for t in await _kas_dokumen(doc_id) if t.get("status") != "void"]
            # Tinjauan akhir Minor 7 — kas yang sudah terbit dicatat di `kas_ids` (layar Batal menyebut kasnya dibalik,
            # bukan "kasnya belum terbit"); terbit berikutnya menggabungkannya.
            await db[COLL].update_one({"id": doc_id}, {"$set": {
                "terbit_error": str(exc.detail)[:300], "updated_at": now_iso(),
                "kas_ids": {**(doc.get("kas_ids") or {}), **{t["seq"]: t["id"] for t in sudah if t.get("seq")}}}})
            lanjut = ("Kas yang sudah terbit tetap tercatat; ulangi lewat Setujui atau batalkan Pindah Dana ini."
                      if sudah else "Belum ada kas yang terbit; ulangi lewat Setujui atau batalkan Pindah Dana ini.")
            raise _galat(409, f"Kas Pindah Dana {doc.get('number')} belum terbit: {exc.detail} {lanjut}") from exc
        selesai = not doc.get("dua_tahap")
        now = now_iso()
        isi: Dict[str, Any] = {
            "status": SELESAI if selesai else PERJALANAN, "akun_transit": akun["transit"],
            "akun_beban_bank": akun["beban_bank"] if _f(doc.get("biaya")) > EPS else "",
            "kas_ids": {**(doc.get("kas_ids") or {}), **ids}, "terbit_pada": now, "terbit_error": "",
            **_ringkas_gl(await _kas_dokumen(doc_id)), "updated_at": now}
        jejak = []
        if disetujui:
            isi.update({"disetujui_oleh": nama, "disetujui_oleh_id": (actor or {}).get("id", ""),
                        "disetujui_pada": now})
            jejak.append(_jejak("setujui", actor))
        if selesai:
            isi.update({"tanggal_diterima": doc["tanggal_terima"], "diterima_oleh": nama,
                        "diterima_oleh_id": (actor or {}).get("id", ""), "diterima_pada": now})
        jejak.append(_jejak("terbit", actor, "sekali jalan" if selesai else "dalam perjalanan"))
        upd = _saga.finish_set(isi)
        upd["$push"] = {"jejak": {"$each": jejak}}
        await db[COLL].update_one({"id": doc_id}, upd)
    finally:
        await _saga.release(COLL, doc_id, token)
    return _bentuk(await _ambil(doc_id))


# ── Terima ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def terima(doc_id: str, tanggal: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/fund-transfers/{id}/receive` — dana dalam perjalanan diterima rekening tujuan pada `tanggal` (kosong =
    tanggal terima rencana): kas masuk tujuan, Dr tujuan / Cr transit (akun transit yang sama dengan kas kirim)."""
    from services import atomic_claim as _saga
    from services import cash_ledger
    doc = await _ambil(doc_id)
    eid = doc.get("entity_id") or ""
    # ── PERIKSA ──
    if doc.get("status") != PERJALANAN:
        raise _galat(409, _pesan_status(doc, "terima"))
    tgl = _tanggal(tanggal, "terima") if str(tanggal or "").strip() else doc.get("tanggal_terima") or _tanggal("", "")
    if tgl < (doc.get("tanggal_kirim") or ""):
        raise _galat(400, PESAN_TANGGAL)
    await _periksa_milik(eid, await _rekening(doc["rekening_tujuan_id"], "tujuan"))
    akun = await _akun_lawan(eid)
    rencana = _rencana({**doc, "tanggal_diterima": tgl}, "terima", akun)
    await _periksa_jurnal(eid, rencana)
    # ── KLAIM ──
    nama = (actor or {}).get("name") or ""
    lk = await _saga.claim(COLL, doc_id, "fund_transfer_receive", precondition={"status": PERJALANAN}, actor=nama,
                           detail=_pesan_berubah(doc))
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        try:
            ids = await _terbitkan(lk, rencana, actor)
        except cash_ledger.CashRejected as exc:
            raise _galat(409, f"Kas masuk Pindah Dana {doc.get('number')} belum terbit: {exc.detail} Dokumen tetap "
                              "dalam perjalanan.") from exc
        now = now_iso()
        upd = _saga.finish_set({
            "status": SELESAI, "tanggal_diterima": tgl, "diterima_oleh": nama,
            "diterima_oleh_id": (actor or {}).get("id", ""), "diterima_pada": now,
            "kas_ids": {**(lk.get("kas_ids") or {}), **ids}, **_ringkas_gl(await _kas_dokumen(doc_id)),
            "updated_at": now})
        upd["$push"] = {"jejak": _jejak("terima", actor, f"diterima {tgl}")}
        await db[COLL].update_one({"id": doc_id}, upd)
    finally:
        await _saga.release(COLL, doc_id, token)
    return _bentuk(await _ambil(doc_id))


# ── Batal ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _tolak_bila_tercocok(kas: List[Dict[str, Any]], nomor: str) -> None:
    """Kas yang sudah dicocokkan dengan mutasi bank (`reconciled_amount` > 0, PK-21) tidak dibalik dari sini."""
    for t in kas:
        if _f(t.get("reconciled_amount")) > 0:
            raise _galat(409, f"Kas {t.get('number', '')} dari Pindah Dana {nomor} sudah dicocokkan dengan mutasi "
                              "bank — lepas dulu di Rekonsiliasi, lalu batalkan.")


async def _periksa_pembalik(entity_id: str, kas: List[Dict[str, Any]], nomor: str) -> None:
    """Tiap kas yang akan dibalik: belum dicocokkan mutasi bank; periode tanggal pembalik terbuka; baris pembaliknya
    (akun kas dialihkan seperti `_reverse_once_ex`) lolos pemeriksa jurnal. Tanpa tulisan."""
    from services import gl_service as gl
    from services.posting_registry import tanggal_pembalik
    _tolak_bila_tercocok(kas, nomor)
    for t in kas:
        tgl = tanggal_pembalik(t.get("txn_date")) or now_iso()
        je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": t["id"],
                                                "status": {"$ne": "void"}}, {"_id": 0})
        try:
            if not je:
                await gl.preflight_posting(entity_id, tgl)
                continue
            alih = await gl.baris_kas_rekening(je)
            lines = [{"account_code": (alih.get(i) or {}).get("akun") or ln["account_code"],
                      "debit": float(ln.get("credit") or 0), "credit": float(ln.get("debit") or 0),
                      "description": ln.get("description", "")} for i, ln in enumerate(je.get("lines") or [])]
            await gl.preflight_entry(lines=lines, entity_id=je.get("entity_id") or entity_id, date=tgl,
                                     source_type="cash_transaction_void")
        except gl.ClosedPeriodError as exc:
            raise _galat(409, str(exc)) from exc
        except ValueError as exc:
            raise _galat(409, f"Jurnal pembalik kas {t.get('number', '')} belum bisa diterbitkan: {exc}") from exc


async def _balik_kas(doc: Dict[str, Any], kas: List[Dict[str, Any]], actor: Dict[str, Any]) -> List[str]:
    """Balik tiap kas lewat pembalik kas yang ada (pintu tahan-gagal) lalu tandai `void`; terakhir-terbit dulu. Gagal →
    `batal_gl_status: failed` di dokumen + 409 (kas yang sudah dibalik tetap dibalik; ulang meneruskan sisanya)."""
    from services import cash_ledger
    from services import gl_service as gl
    from services.posting_registry import tanggal_pembalik
    nama = (actor or {}).get("name") or "system"
    alasan = doc.get("alasan_batal") or ""
    label = f"batal {doc.get('number', '')}"
    hasil: List[str] = []
    for t in reversed(kas):
        cid = t["id"]
        try:
            await cash_ledger.ensure_posted(cid)
            res = await gl.post_durable(
                "cash_transactions", cid,
                lambda cid=cid, tgl=tanggal_pembalik(t.get("txn_date")): gl.post_cash_void(
                    cid, label=label, created_by=nama, date=tgl),
                source_type="cash_transaction_void", source_id=cid, field="void_gl_status", raise_on_fail=True)
            rev = res.get("journal") or ({"id": res["journal_entry_id"]} if res.get("journal_entry_id") else {})
            await db.cash_transactions.update_one({"id": cid, "status": {"$ne": "void"}}, {"$set": {
                "status": "void", "void_journal_entry_id": rev.get("id", ""), "void_reason": alasan,
                "voided_by": nama, "voided_at": now_iso(), "updated_at": now_iso()}})
            hasil.append(rev.get("id", ""))
        except Exception as exc:  # noqa: BLE001 — jurnal pembalik gagal: dokumen tetap batal, sisa kas diteruskan nanti
            pesan = getattr(exc, "error", None) or str(exc) or exc.__class__.__name__
            await db[COLL].update_one({"id": doc["id"]}, {"$set": {
                "batal_gl_status": "failed", "batal_gl_error": f"{t.get('number', '')}: {pesan}"[:300],
                "batal_gl_failed_at": now_iso(), "updated_at": now_iso()}})
            raise _galat(409, f"Pindah Dana {doc.get('number')} sudah dibatalkan, tetapi jurnal pembalik kas "
                              f"{t.get('number', '')} gagal: {pesan}. Ulangi dari Keuangan › Posting Gagal.") from exc
    return hasil


async def batal(doc_id: str, alasan: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """`POST /api/fund-transfers/{id}/cancel` — batalkan Pindah Dana beralasan: semua kas tidak-batal dibalik (ditolak
    bila ada yang tercocok mutasi bank). Dokumen batal yang pembaliknya belum tuntas → diteruskan.

    Tinjauan T4 putaran 1 (I1) — klaim berprasyarat status yang DILIHAT PERIKSA (bukan sembarang status hidup): Terima /
    Setujui yang selesai di sela PERIKSA dan KLAIM membuat batal kalah (409 muat ulang, tidak ada yang berubah). Kas
    dibaca ulang SESUDAH klaim (selama kunci dipegang tidak ada kas baru untuk dokumen ini); himpunan kas yang berbeda
    dari yang diperiksa (mis. terbit yang diteruskan di sela tanpa mengubah status) → 409 yang sama; kas segar diperiksa
    ulang rekonsiliasinya lalu SEMUANYA dibalik."""
    from services import atomic_claim as _saga
    teks = (alasan or "").strip()
    if len(teks) < ALASAN_MIN:
        raise _galat(400, PESAN_ALASAN)
    doc = await _ambil(doc_id)
    eid = doc.get("entity_id") or ""
    lanjut = doc.get("status") == BATAL and doc.get("batal_gl_status") in ("pending", "failed")
    # ── PERIKSA ──
    if doc.get("status") not in HIDUP and not lanjut:
        raise _galat(409, _pesan_status(doc, "batal"))
    nomor = doc.get("number") or doc_id
    kas = [t for t in await _kas_dokumen(doc_id) if t.get("status") != "void"]
    await _periksa_pembalik(eid, kas, nomor)
    # ── KLAIM (status persis seperti yang diperiksa) ──
    nama = (actor or {}).get("name") or ""
    syarat = ({"status": BATAL, "batal_gl_status": doc.get("batal_gl_status")} if lanjut
              else {"status": doc.get("status")})
    try:
        lk = await _saga.claim(COLL, doc_id, "fund_transfer_cancel", precondition=syarat, actor=nama,
                               detail=_pesan_berubah(doc))
    except HTTPException as exc:
        segar = await db[COLL].find_one({"id": doc_id}, {"_id": 0}) or {}
        if isinstance(exc.detail, str) and segar.get("status") == BATAL and not lanjut:
            raise _galat(409, _pesan_status(segar, "batal")) from exc   # batal lain menang lebih dulu
        raise
    token = (lk.get(_saga.LOCK) or {}).get("token", "")
    try:
        segar = [t for t in await _kas_dokumen(doc_id) if t.get("status") != "void"]
        if {t["id"] for t in segar} != {t["id"] for t in kas}:
            raise _galat(409, _pesan_berubah(doc))   # kunci dilepas di `finally`; belum ada yang ditulis
        _tolak_bila_tercocok(segar, nomor)
        kas = segar
        if not lanjut:
            niat = {"status": BATAL, "status_sebelum_batal": lk.get("status"), "alasan_batal": teks[:500],
                    "dibatalkan_oleh": nama, "dibatalkan_oleh_id": (actor or {}).get("id", ""),
                    "dibatalkan_pada": now_iso(), "batal_gl_status": "pending" if kas else "", "batal_gl_error": "",
                    "updated_at": now_iso()}
            await db[COLL].update_one({"id": doc_id, f"{_saga.LOCK}.token": token},
                                      {"$set": niat, "$push": {"jejak": _jejak("batal", actor, teks[:500])}})
            lk = {**lk, **niat}
        balik = await _balik_kas(lk, kas, actor)
        upd = _saga.finish_set({"batal_gl_status": "posted" if (kas or lanjut) else "", "batal_gl_error": "",
                                "batal_selesai_pada": now_iso(), "updated_at": now_iso()})
        if balik:
            upd["$push"] = {"void_journal_entry_ids": {"$each": [j for j in balik if j]}}
        if lanjut:
            upd.setdefault("$push", {})["jejak"] = _jejak("batal_diteruskan", actor)
        await db[COLL].update_one({"id": doc_id}, upd)
    finally:
        await _saga.release(COLL, doc_id, token)
    return _bentuk(await _ambil(doc_id))


async def lanjut_batal(doc_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Panel Posting Gagal jenis `fund_transfer_cancel`: teruskan pembalik kas dokumen batal yang belum tuntas."""
    doc = await _ambil(doc_id)
    return await batal(doc_id, doc.get("alasan_batal") or "diteruskan dari Posting Gagal", actor)


# ── Butir tutup buku ─────────────────────────────────────────────────────────────────────────────────────────────────
async def dalam_perjalanan(entity_id: str, per: str) -> Dict[str, Any]:
    """Pindah Dana PT yang uangnya masih di jalan per tanggal `per` (`YYYY-MM-DD`): kas kirim sudah terbit (tanggal
    kirim ≤ `per`) tetapi kas terima belum (belum diterima, atau diterima sesudah `per`). Dokumen batal tidak dihitung
    (keadaan dokumen hari ini). → `{jumlah, total (Rp), nomor: [≤ 5 nomor pertama]}`."""
    q = {"entity_id": entity_id, "dua_tahap": True, "status": {"$in": [PERJALANAN, SELESAI]},
         "tanggal_kirim": {"$lte": per}}
    n, sen, nomor = 0, 0, []
    async for d in db[COLL].find(q, {"_id": 0, "number": 1, "nominal": 1, "status": 1, "tanggal_diterima": 1}) \
            .sort("tanggal_kirim", 1):
        if d.get("status") == SELESAI and (d.get("tanggal_diterima") or "") <= per:
            continue
        n += 1
        sen += to_cents(_f(d.get("nominal")))
        if len(nomor) < 5:
            nomor.append(d.get("number") or "")
    return {"jumlah": n, "total": from_cents(sen), "nomor": nomor}
