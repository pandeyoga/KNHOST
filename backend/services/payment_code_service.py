"""PM-T2 — cara bayar & rekening tujuan di pesanan, kode bayar, dan instruksi bayar (`docs/blueprint/unit/PM-T2.md`,
keputusan K-34, K-35).

Pelanggan menerima dokumen yang menyebut KE REKENING MANA harus membayar dan DENGAN KODE APA, diambil dari master
(PM-T1: daftar induk cara bayar + rekening ber-peruntukan) — bukan nomor yang diketik sales di naskah templat. Rekening PT
lain tidak mungkin terpilih (`resolve_destination`). Kode bayar (`payment_codes`, awalan id `pyc_`) menjadi kunci
pencocokan mutasi bank di PM-T3 (`find_in_text`).

Kode: `{awalan}-{5 karakter}` dari `ALFABET` (tanpa 0, 1, I, O), dibuat `secrets`, unik LINTAS PT (indeks wajib
`payment_codes.uq_pay_code`); tabrakan → diulang paling banyak `MAKS_ULANG` kali. Satu kode per (pesanan, baris tagihan)
(`uq_pay_code_line`). Kode tingkat pesanan lahir saat pesanan bayar-dulu dikonfirmasi (`ensure_for_order`, dari
`so_lifecycle_service.confirm_core`); kode per baris tagihan lahir lewat `ensure_for_line` (dipanggil modul jadwal
tagihan CR-T2 bila sudah ada — belum ada di HEAD).

VA/QRIS dinamis = PM-T5 (`tahan`, K-35): kode di sini hanya teks berita transfer, tanpa penyedia pembayaran.
"""
from __future__ import annotations

import logging
import re
import secrets
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso, rupiah
from db import db

logger = logging.getLogger(__name__)

COLL = "payment_codes"
ALFABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"   # tanpa 0, 1, I, O (mudah tertukar saat diketik di berita transfer)
PANJANG = 5
MAKS_ULANG = 5
STATUS = ("aktif", "lunas", "batal")
PERUNTUKAN = "penerimaan_pelanggan"
AWALAN_KEY = "payment.kode_bayar_awalan"
TUTUP = ("cancelled", "rejected", "void", "expired")
EPS = 1.0   # toleransi pembulatan Rupiah (sama dengan gerbang bayar-sebelum-kirim)

PESAN_WAJIB = "Pilih cara bayar untuk pesanan ini."
PESAN_PT_LAIN = "Rekening tujuan bukan milik PT pesanan ini."
PESAN_TIDAK_ADA = "Rekening tujuan tidak ditemukan."
PESAN_TIDAK_MENERIMA = "Rekening ini tidak bisa menerima pembayaran pelanggan lewat {nama}."
LABEL_SEBELUM_KIRIM = "sebelum barang dikirim"
CATATAN = {
    "tutup": "Pesanan sudah ditutup — tidak ada tagihan yang perlu dibayar.",
    "bayar_dulu": "Instruksi bayar tersedia setelah pesanan dikonfirmasi.",
    "tempo": "Instruksi bayar tersedia setelah barang dikirim.",
    "tanpa_cara": "Cara bayar pesanan ini belum ditentukan.",
    "bukan_bank": "Cara bayar pesanan ini tidak memakai rekening bank — instruksi transfer tidak dibuat.",
    "tanpa_rekening": "Rekening tujuan belum dipilih — pilih lewat Edit / Override SO.",
    "tidak_tampil": ("Rekening tujuan belum ditandai tampil di dokumen pelanggan — minta Finance mengaturnya di Kas & "
                     "Bank."),
    "lunas": "Semua tagihan berkode pesanan ini sudah dibayar.",
}
_BULAN = ("Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des")


class KodeBayarError(RuntimeError):
    """Kode bayar tidak bisa dibuat (tabrakan berulang)."""


def _acak() -> str:
    return "".join(secrets.choice(ALFABET) for _ in range(PANJANG))


def _bersih(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    return {k: v for k, v in doc.items() if k != "_id"}


# ── Cara bayar & rekening tujuan pesanan (langkah 1–4 spesifikasi) ─────────────────────────────────────────────────
def potret_rekening(row: Optional[Dict[str, Any]]) -> Dict[str, str]:
    """Potret rekening tujuan yang disimpan di pesanan (D3): dokumen lama tetap menyebut rekening saat itu."""
    r = row or {}
    return {"bank_name": str(r.get("bank_name") or ""), "account_number": str(r.get("account_number") or ""),
            "holder_name": str(r.get("holder_name") or "")}


def teks_rekening(acc: Optional[Dict[str, Any]]) -> str:
    """"{bank} {nomor} a.n. {atas nama}" (tanpa atas nama: "{bank} {nomor} ({nama rekening})")."""
    a = acc or {}
    head = " ".join(x for x in (str(a.get("bank_name") or "").strip(), str(a.get("account_number") or "").strip()) if x)
    holder = str(a.get("holder_name") or "").strip()
    if head and holder:
        return f"{head} a.n. {holder}"
    name = str(a.get("name") or "").strip()
    return f"{head} ({name})" if head and name else (head or holder or name)


async def resolve_destination(entity_id: str, method: str, account_id: str, *, wajib: bool = False) -> Dict[str, Any]:
    """Cara bayar + rekening tujuan pesanan PT `entity_id`, sebelum apa pun ditulis. Galat → 400 berkalimat.

    1. Cara bayar kosong: `wajib` → 400; selain itu keduanya kosong (rekening yang dikirim diabaikan).
    2. Kode/alias → kanonik; harus aktif untuk PT itu dan dipakai untuk penerimaan (pesan PM-T1).
    3. Cara bayar ber-rekening bank tanpa rekening → rekening bawaan (PT, cara bayar) PM-T1; tanpa bawaan → kosong.
    4. Rekening terisi: milik PT pesanan, aktif, peruntukan penerimaan pelanggan, melayani cara bayar itu → potret."""
    from services import bank_account_change_service as bacs
    from services import payment_method_service as pms
    method, account_id = (method or "").strip(), (account_id or "").strip()
    if not method:
        if wajib:
            raise HTTPException(status_code=400, detail=PESAN_WAJIB)
        return {"payment_method_code": "", "receiving_account_id": "", "receiving_account": {}}
    try:
        row = await pms.wajib(entity_id, method, arah="masuk")
    except pms.CaraBayarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kode = row["code"]
    if account_id:
        acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0, "id": 1, "entity_id": 1})
        if not acc:
            raise HTTPException(status_code=400, detail=PESAN_TIDAK_ADA)
        if (acc.get("entity_id") or "") != (entity_id or ""):
            raise HTTPException(status_code=400, detail=PESAN_PT_LAIN)
    penerima = await bacs.daftar_penerima(entity_id, kode)   # aktif · penerimaan pelanggan · melayani cara bayar ini
    if not account_id:
        if row.get("needs_account") != "bank":
            return {"payment_method_code": kode, "receiving_account_id": "", "receiving_account": {}}
        bawaan = next((r for r in penerima if r.get("is_default")), None)
        if not bawaan:
            return {"payment_method_code": kode, "receiving_account_id": "", "receiving_account": {}}
        account_id = bawaan["id"]
    pilih = next((r for r in penerima if r["id"] == account_id), None)
    if not pilih:
        raise HTTPException(status_code=400, detail=PESAN_TIDAK_MENERIMA.format(nama=row.get("name") or kode))
    return {"payment_method_code": kode, "receiving_account_id": pilih["id"], "receiving_account": potret_rekening(pilih)}


async def receiving_options(entity_id: str) -> Dict[str, Any]:
    """Pilihan form override: cara bayar penerimaan aktif PT + rekening penerima per cara bayar ber-rekening."""
    from services import bank_account_change_service as bacs
    from services import payment_method_service as pms
    metode = await pms.active_for(entity_id, "masuk")
    akun: Dict[str, List[Dict[str, Any]]] = {}
    for m in metode:
        if m.get("needs_account") in ("bank", "kas"):
            akun[m["code"]] = await bacs.daftar_penerima(entity_id, m["code"])
    return {"payment_methods": [pms.untuk_layar(m) for m in metode], "receiving_accounts": akun}


# ── Termin bayar-dulu ─────────────────────────────────────────────────────────────────────────────────────────────
async def _termin(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    from services import entity_master_service as ems
    code = str(order.get("payment_term_code") or order.get("payment_term") or "")
    if not code:
        return None
    return await ems.resolve_row("payment-terms", code, order.get("entity_id") or "", include_inactive=True)


def persen_bayar_dulu(term: Optional[Dict[str, Any]]) -> float:
    """Persen nilai pesanan yang wajib dibayar sebelum kirim: termin ber-DP = persen DP; termin tunai tanpa DP = 100 %;
    termin tempo = 0 (belum ada kode sampai jadwal tagihan CR-T2)."""
    if not term:
        return 0.0
    dp = float(term.get("dp_percent") or 0)
    if dp > 0:
        return min(dp, 100.0)
    return 100.0 if str(term.get("type") or "") == "cash" else 0.0


# ── Kode bayar ────────────────────────────────────────────────────────────────────────────────────────────────────
async def _sisip(awalan: str, isi: Dict[str, Any], kunci: Dict[str, Any]) -> Dict[str, Any]:
    """Sisip satu kode acak; tabrakan indeks `code` → ulang (≤ `MAKS_ULANG`). Tabrakan indeks (pesanan, baris) = proses
    lain sudah membuat kode untuk tagihan yang sama → kode itu yang dipakai (idempoten di bawah balapan)."""
    from indexes import is_duplicate_on
    for _ in range(MAKS_ULANG):
        doc = {**isi, "id": new_id("pyc"), "code": f"{awalan}-{_acak()}"}
        try:
            await db[COLL].insert_one(dict(doc))
            return doc
        except DuplicateKeyError as exc:
            if is_duplicate_on(exc, "code"):
                continue
            ada = await db[COLL].find_one(kunci, {"_id": 0})
            if ada:
                return ada
            raise
    raise KodeBayarError(f"Kode bayar tidak bisa dibuat sesudah {MAKS_ULANG} kali mencoba (kode bertabrakan).")


def _awalan_bersih(nilai: Any) -> str:
    from config_registry import default_of
    teks = str(nilai or "").strip()
    return teks if re.fullmatch(r"[A-Z]{2,4}", teks) else str(default_of(AWALAN_KEY))


def _isi_kode(order: Dict[str, Any], *, amount: float, due_date: str, plan_id: str, line_id: str,
              order_level: bool, percent: float = 0.0) -> Dict[str, Any]:
    return {"entity_id": order.get("entity_id") or "", "order_id": order["id"],
            "order_number": order.get("number") or "", "customer_id": order.get("customer_id") or "",
            "plan_id": plan_id, "line_id": line_id, "order_level": order_level, "percent": percent,
            "amount": round(float(amount or 0), 2), "due_date": due_date or "", "status": "aktif",
            "created_at": now_iso(), "updated_at": now_iso()}


async def ensure_for_order(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Kode tingkat pesanan untuk pesanan BAYAR-DULU (termin tunai atau ber-DP); idempoten per pesanan. Pesanan tempo
    → `None`. `amount` = nilai pesanan × persen wajib (potret saat kode lahir). Dipanggil sesudah `confirm_core`."""
    from services.config_resolver import value_of
    if not order or not order.get("id"):
        return None
    pct = persen_bayar_dulu(await _termin(order))
    if pct <= 0:
        return None
    ada = await db[COLL].find_one({"order_id": order["id"], "order_level": True}, {"_id": 0})
    if ada:
        return ada
    awalan = _awalan_bersih(await value_of(AWALAN_KEY, {"entity_id": order.get("entity_id") or ""}))
    grand = float(order.get("grand_total") if order.get("grand_total") is not None else order.get("total_amount") or 0)
    grand += sum(float(x.get("gross") or 0) for x in order.get("extra_billing_lines") or [])   # PK-32 — nilai tagihan
    isi = _isi_kode(order, amount=round(grand * pct / 100.0, 2), due_date="", plan_id="", line_id="",
                    order_level=True, percent=pct)
    kode = await _sisip(awalan, isi, {"order_id": order["id"], "order_level": True})
    await db.sales_orders.update_one(
        {"id": order["id"], "$or": [{"payment_code": {"$exists": False}}, {"payment_code": ""}, {"payment_code": None}]},
        {"$set": {"payment_code": kode["code"]}})
    return kode


async def _tandai_baris(plan_id: str, line_id: str, code: str) -> None:
    await db.payment_plans.update_one({"id": plan_id, "lines.line_id": line_id}, {"$set": {"lines.$.pay_code": code}})


async def ensure_for_line(plan: Dict[str, Any], line: Dict[str, Any]) -> Dict[str, Any]:
    """Kode per baris tagihan (`payment_plans.lines[]`), idempoten per (pesanan, `line_id`). Baris `dp` memakai ulang
    kode tingkat pesanan (diisi `plan_id`, `line_id`). Baris mendapat `pay_code`."""
    from services.config_resolver import value_of
    order_id = str(plan.get("doc_id") or plan.get("order_id") or "")
    line_id = str(line.get("line_id") or "")
    if not order_id or not line_id:
        raise ValueError("Baris tagihan tanpa pesanan atau tanpa line_id.")
    ada = await db[COLL].find_one({"order_id": order_id, "line_id": line_id}, {"_id": 0})
    if ada:
        await _tandai_baris(plan["id"], line_id, ada["code"])
        return ada
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0}) or {"id": order_id}
    if line.get("kind") == "dp":
        res = await db[COLL].update_one({"order_id": order_id, "order_level": True, "line_id": ""},
                                        {"$set": {"plan_id": plan["id"], "line_id": line_id, "updated_at": now_iso()}})
        if res.modified_count:
            kode = await db[COLL].find_one({"order_id": order_id, "line_id": line_id}, {"_id": 0})
            await _tandai_baris(plan["id"], line_id, kode["code"])
            return kode
    awalan = _awalan_bersih(await value_of(AWALAN_KEY, {"entity_id": order.get("entity_id") or ""}))
    isi = _isi_kode(order, amount=float(line.get("amount") or 0), due_date=str(line.get("due_date") or "")[:10],
                    plan_id=str(plan["id"]), line_id=line_id, order_level=False)
    kode = await _sisip(awalan, isi, {"order_id": order_id, "line_id": line_id})
    await _tandai_baris(plan["id"], line_id, kode["code"])
    return kode


def _calon_kode(text: str) -> List[str]:
    """Calon kode dalam teks berita transfer: awalan 2–4 huruf, pemisah opsional (`-`, spasi, `.`, `_`, `/`), lima
    karakter `ALFABET`. Huruf kecil diterima ("kn 7f3k2")."""
    t = (text or "").upper()
    out: List[str] = []
    for n in (2, 3, 4):
        pola = re.compile(rf"(?<![A-Z0-9])([A-Z]{{{n}}})[\s\-_./]?([{ALFABET}]{{{PANJANG}}})(?![A-Z0-9])")
        for m in pola.finditer(t):
            k = f"{m.group(1)}-{m.group(2)}"
            if k not in out:
                out.append(k)
    return out


async def find_in_text(text: str) -> list:
    """Kode bayar (dokumen `payment_codes`) yang muncul dalam sebuah teks — untuk pencocokan mutasi bank (PM-T3)."""
    calon = _calon_kode(text)
    if not calon:
        return []
    rows = await db[COLL].find({"code": {"$in": calon}}, {"_id": 0}).to_list(len(calon) + 1)
    urut = {k: i for i, k in enumerate(calon)}
    return sorted(rows, key=lambda r: urut.get(r.get("code"), 99))


# ── Instruksi bayar ───────────────────────────────────────────────────────────────────────────────────────────────
def label_tanggal(iso: str) -> str:
    """"2026-12-15" → "15 Des 2026" (tanggal kalender, tanpa geser zona)."""
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", str(iso or ""))
    if not m:
        return str(iso or "")
    return f"{int(m.group(3))} {_BULAN[int(m.group(2)) - 1]} {m.group(1)}"


def _teks_blok(nomor: str, item: Dict[str, Any], account: Dict[str, Any]) -> str:
    return "\n".join([
        f"Pembayaran untuk pesanan {nomor}",
        f"Jumlah        : {rupiah(item['amount'])}",
        f"Jatuh tempo   : {item['due_label']}",
        f"Transfer ke   : {teks_rekening(account)}",
        f"Berita/kode   : {item['pay_code']}",
    ])


async def _baris_rencana(codes: List[Dict[str, Any]]) -> Dict[tuple, Dict[str, Any]]:
    ids = sorted({c["plan_id"] for c in codes if c.get("plan_id")})
    if not ids:
        return {}
    out: Dict[tuple, Dict[str, Any]] = {}
    async for p in db.payment_plans.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "lines": 1}):
        for ln in p.get("lines") or []:
            if ln.get("line_id"):
                out[(p["id"], ln["line_id"])] = ln
    return out


def _label_kode(c: Dict[str, Any], baris: Optional[Dict[str, Any]]) -> str:
    if baris and baris.get("label"):
        return str(baris["label"])
    pct = float(c.get("percent") or 0)
    if c.get("order_level") and 0 < pct < 100:
        return f"Uang muka {pct:g}%"
    return "Pembayaran sebelum kirim" if c.get("order_level") else "Tagihan"


async def instruction_for(order: Dict[str, Any]) -> Dict[str, Any]:
    """Instruksi bayar pesanan (sudah dimuat): `{order_number, method_name, account, items, text, note}`.

    `items` = satu blok per kode bayar AKTIF yang belum lunas, hanya bila cara bayar ber-rekening bank dan rekening tujuan
    ber-`show_on_documents` (aturan yang sama untuk dokumen cetak, salin, dan WhatsApp). `note` = sebab bila kosong."""
    from services import payment_method_service as pms
    eid = order.get("entity_id") or ""
    kode_cb = str(order.get("payment_method_code") or "")
    account = potret_rekening(order.get("receiving_account")) if order.get("receiving_account_id") else {}
    out: Dict[str, Any] = {"order_number": order.get("number") or "", "method_name": "", "account": account,
                           "items": [], "text": "", "note": ""}
    cara = None
    if kode_cb:
        out["method_name"] = await pms.nama(eid, kode_cb)
        cara = await pms._baris(eid, kode_cb) or pms.BENIH_BY_CODE.get(kode_cb)   # noqa: SLF001 — termasuk nonaktif
    if order.get("status") in TUTUP:
        out["note"] = CATATAN["tutup"]
        return out
    codes = await db[COLL].find({"order_id": order.get("id"), "status": "aktif"}, {"_id": 0}).to_list(200)
    if not codes:
        out["note"] = CATATAN["bayar_dulu" if persen_bayar_dulu(await _termin(order)) > 0 else "tempo"]
        return out
    if not kode_cb:
        out["note"] = CATATAN["tanpa_cara"]
        return out
    if (cara or {}).get("needs_account") != "bank":
        out["note"] = CATATAN["bukan_bank"]
        return out
    if not order.get("receiving_account_id"):
        out["note"] = CATATAN["tanpa_rekening"]
        return out
    acc = await db.bank_accounts.find_one({"id": order["receiving_account_id"]}, {"_id": 0, "show_on_documents": 1})
    if not (acc or {}).get("show_on_documents"):
        out["note"] = CATATAN["tidak_tampil"]
        return out
    baris = await _baris_rencana(codes)
    dibayar = float(order.get("paid_total") or 0)
    codes.sort(key=lambda c: (not c.get("order_level"), c.get("due_date") or "", c.get("created_at") or ""))
    for c in codes:
        ln = baris.get((c.get("plan_id"), c.get("line_id"))) if c.get("plan_id") else None
        if ln is not None and ln.get("status") == "paid":
            continue
        if ln is None and c.get("order_level") and dibayar + EPS >= float(c.get("amount") or 0):
            continue   # tagihan bayar-dulu sudah terpenuhi pembayaran pesanan (status kode diurus PM-T3)
        due = str(c.get("due_date") or "")
        out["items"].append({"label": _label_kode(c, ln), "amount": round(float(c.get("amount") or 0), 2),
                             "due_date": due, "due_label": label_tanggal(due) if due else LABEL_SEBELUM_KIRIM,
                             "pay_code": c["code"]})
    if not out["items"]:
        out["note"] = CATATAN["lunas"]
        return out
    out["text"] = "\n\n".join(_teks_blok(out["order_number"], it, account) for it in out["items"])
    return out


async def instruction(order_id: str) -> dict:
    """`{order_number, method_name, account, items: [{label, amount, due_date, due_label, pay_code}], text, note}` untuk
    tagihan berkode yang belum lunas; `items` kosong bila belum ada kode atau rekening."""
    order = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        return {"order_number": "", "method_name": "", "account": {}, "items": [], "text": "", "note": ""}
    return await instruction_for(order)


async def blocks_for_document(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Blok cetak `payment_instruction` (Konfirmasi Pesanan, Faktur): satu blok per tagihan berkode yang belum lunas."""
    try:
        ins = await instruction_for(order)
    except Exception as exc:  # noqa: BLE001 — dokumen tetap tercetak; blok instruksi dilewati dan dicatat
        logger.warning("[PM-T2] instruksi bayar gagal disusun untuk %s: %s", order.get("id"), exc)
        return []
    return [{"label": it["label"], "pay_code": it["pay_code"],
             "lines": _teks_blok(ins["order_number"], it, ins["account"]).split("\n")} for it in ins["items"]]


async def rekening_bank_token(entity_id: Optional[str], doc: Dict[str, Any]) -> str:
    """Penyedia token naskah `{{rekening_bank}}` (KP-T6): potret rekening tujuan pesanan, lalu rekening bawaan
    `transfer` PT; tanpa keduanya kosong."""
    acc = (doc or {}).get("_receiving_account") or {}
    if acc.get("account_number"):
        return teks_rekening(acc)
    if not entity_id:
        return ""
    from services import bank_account_change_service as bacs
    try:
        rows = await bacs.daftar_penerima(entity_id, "transfer")
    except HTTPException:
        return ""   # cara bayar transfer dimatikan untuk PT ini
    bawaan = next((r for r in rows if r.get("is_default")), None)
    return teks_rekening(bawaan) if bawaan else ""
