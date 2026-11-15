"""FASE G-9 — EKSEKUTOR AKSI PLAYBOOK KASUS KEUANGAN.

Di sini uang benar-benar berpindah. Setiap fungsi `act_*`:
* memakai **service yang sudah ada** (rekonsiliasi bank G-8, kwitansi AR, store credit,
  denda G-2, buku besar) — tidak menulis ulang mekanika uang;
* mengembalikan daftar **dokumen turunan** (`documents[]`) yang benar-benar lahir,
  supaya `INV-CASE-01` bisa membuktikan kasus `resolved` tidak kosong;
* tidak pernah mengubah dokumen finansial lama (ledger tambah-saja) — koreksi selalu
  lewat jurnal/baris baru.

Bentuk dokumen turunan: `{"kind","id","number","label"}`.

PK-25 (FX-09, FX-11) — tiap aksi dipecah menjadi PEMERIKSA (`_cek_*`, lewat `precheck`, tanpa tulisan) dan PELAKSANA
(`act_*`, lewat `execute`). Urutan pelaksana mengikuti `02_STANDAR.md` §1: EFEK (pelunasan lewat `allocate` ber-id
tetap, kas lewat pembuat kas ber-id tetap, deposit/titipan/saldo dengan operasi bersyarat yang ditandai di
`finance_cases.resolution_intent.steps`) → JURNAL lewat `gl_service.post_durable` atas kasus (kunci per kejadian
`{suffix}:{n}`, `n` dari `op_id`) atau pembantu jurnal kembar PK-06 untuk dua PT. Jurnal gagal TIDAK melempar:
hasilnya dikembalikan di `gl` supaya `finance_case_service` menahan kasus (niat tetap `pending`, tampil di panel
Posting Gagal).
"""
import contextvars
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso, safe_doc, rupiah
from db import db
from services import gl_service as gl
logger = logging.getLogger(__name__)


EPS = 0.01

#: PK-25 — kalimat penolakan rencana tanpa jurnal untuk aksi yang memindahkan uang (`02` §1 langkah PERIKSA).
PESAN_TANPA_JURNAL = "Penyelesaian ini tidak menghasilkan jurnal. Periksa nominal dan pesanan yang dipilih."


class CaseActionError(ValueError):
    """Kesalahan aksi kasus dengan pesan siap tampil (Bahasa Indonesia)."""


class CaseConflict(CaseActionError):
    """PK-25 — penolakan PERIKSA yang berkode 409 (periode salah satu PT tertutup). Tidak ada tulisan apa pun."""

    status_code = 409


def _rp(v: Any) -> str:
    """Alias tipis ke `core_utils.rupiah` — satu sumber format uang untuk seluruh backend."""
    return rupiah(v)


def _doc(kind: str, doc_id: str, number: str, label: str) -> Dict[str, Any]:
    return {"kind": kind, "id": doc_id or "", "number": number or "", "label": label}


def _je_doc(je: Optional[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    if not je:
        return []
    return [_doc("journal_entry", je.get("id", ""), je.get("number", je.get("id", "")), label)]


def _amt(v: Any) -> float:
    return round(float(v or 0), 2)


# ═════════════════════════════════════════════════════════════════════════════
#  KONTEKS SATU PENYELESAIAN (op_id, urutan id turunan, penanda efek)
# ═════════════════════════════════════════════════════════════════════════════
_CASE_ID: contextvars.ContextVar = contextvars.ContextVar("case_id", default="")
_CASE_OP: contextvars.ContextVar = contextvars.ContextVar("case_op", default="")
_CASE_N: contextvars.ContextVar = contextvars.ContextVar("case_n", default="")
_CASE_OP_SEQ: contextvars.ContextVar = contextvars.ContextVar("case_op_seq", default=0)
_CASE_PAY_SEQ: contextvars.ContextVar = contextvars.ContextVar("case_pay_seq", default=0)   # PK-19
_CASE_EFEK: contextvars.ContextVar = contextvars.ContextVar("case_efek", default=None)       # PK-25
_CASE_GL: contextvars.ContextVar = contextvars.ContextVar("case_gl", default=None)           # PK-25


def op_id_of(case: Dict[str, Any], action: str) -> str:
    """`{id kasus}_{aksi}_{jumlah dokumen kasus saat mulai}` — rumus id kas aksi kasus sejak G3 D4-CASE-02."""
    return f"{case['id']}_{action}_{len(case.get('documents') or [])}"


def _sfx(base: str) -> str:
    """PK-25 (FX-09) — kunci jurnal per kejadian: `{suffix}:{n}`, `n` = nomor penyelesaian dari `op_id`."""
    n = _CASE_N.get()
    return f"{base}:{n}" if n != "" else base


def _jadi(nama: str) -> None:
    """Catat bahwa satu efek SUDAH tertulis (dipakai `finance_case_service` memutuskan nasib niat bila gagal)."""
    efek = _CASE_EFEK.get()
    if efek is not None:
        efek.append(nama)


async def _sekali(nama: str, fn: Callable[[], Awaitable[Any]]) -> Any:
    """Efek yang TIDAK aman diulang sendiri (deposit, titipan, saldo kredit, uang muka pemasok, alokasi titipan, batal
    kwitansi) dijalankan sekali per niat penyelesaian: penanda `resolution_intent.steps.<nama>` (berisi hasilnya)
    ditulis SESUDAH efeknya jadi; niat yang diteruskan mengembalikan hasil tersimpan tanpa menjalankan efeknya lagi.
    Proses yang mati di antara efek dan penandanya mengulang efek itu sekali (pola PK-19)."""
    cid, op = _CASE_ID.get(), _CASE_OP.get()
    if not (cid and op):
        hasil = await fn()
        _jadi(nama)
        return hasil
    c = await db.finance_cases.find_one({"id": cid, "resolution_intent.op_id": op},
                                        {"_id": 0, "resolution_intent": 1}) or {}
    langkah = ((c.get("resolution_intent") or {}).get("steps") or {}).get(nama)
    if langkah is not None:
        return (langkah or {}).get("hasil")
    hasil = await fn()
    _jadi(nama)
    await db.finance_cases.update_one({"id": cid, "resolution_intent.op_id": op}, {"$set": {
        f"resolution_intent.steps.{nama}": {"hasil": safe_doc(hasil) if isinstance(hasil, dict) else hasil,
                                            "at": now_iso()}}})
    return hasil


async def _jurnal(case: Dict[str, Any], *, entity_id: str, amount: float, debit_acc: str, credit_acc: str,
                  label: str, suffix: str, actor: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """JURNAL kasus lewat pintu tahan-gagal (`post_durable` atas `finance_cases`, field `gl_status`). Kunci per
    kejadian; jurnal yang sudah ada diadopsi. Gagal TIDAK melempar — hasilnya dicatat untuk penyelesai."""
    sfx = _sfx(suffix)
    res = await gl.post_durable(
        "finance_cases", case["id"],
        lambda: gl.post_finance_case(case_id=case["id"], entity_id=entity_id, amount=amount, debit_acc=debit_acc,
                                     credit_acc=credit_acc, label=label, suffix=sfx,
                                     created_by=actor.get("name", "system")),
        source_type="finance_case", source_id=f"{case['id']}:{sfx}")
    hasil = _CASE_GL.get()
    if hasil is not None:
        hasil.append({"status": res["gl_status"], "error": res.get("gl_error") or "",
                      "journal_entry_id": res.get("journal_entry_id") or ""})
    if res["gl_status"] != "posted":
        return None
    return res.get("journal") or await db.journal_entries.find_one({"id": res["journal_entry_id"]}, {"_id": 0})


async def _cash_txn(*, direction: str, amount: float, category: str, description: str,
                    entity_id: str, account_id: str = "", cash_type: str = "kas_besar",
                    ref_type: str = "", ref_id: str = "", contra: str = "",
                    owner_entity_id: str = "", actor: str = "system") -> Dict[str, Any]:
    """Catat mutasi kas NYATA + jurnalnya lewat pembuat kas satu pintu (PK-20, `cash_ledger.create_cash`).

    Memakai koleksi & bentuk dokumen yang sama dengan layar Transaksi Kas supaya saldo rekening di layar Kas & Bank ikut
    bergerak. Rekening = `account_id` aksi (dibuktikan milik PT kasus oleh pembuat kas), kosong = rekening tunggal PT.
    G3 D4-CASE-02 — id kas DETERMINISTIK per (kasus, aksi, langkah, urutan) (`cash_case_{op}_{n}`, `seq="{op}:{n}"`) →
    aksi yang diulang MENGADOPSI kas + jurnal yang sudah ada; jurnal gagal → aksi gagal, kas tertinggal `failed` dan
    dipakai ulang saat aksi diulang."""
    amount = round(float(amount or 0), 2)
    if amount <= EPS:
        raise CaseActionError("Nominal harus lebih dari 0")
    # FASE E-7 (E7.4) — kas grup dihapus: uang kasus keuangan tetap milik badan usaha
    # kasusnya. `kas_besar` di sini hanya berarti "lewat bank", bukan "milik grup".
    from services.cash_entity_service import resolve_owner
    cash_owner = resolve_owner(entity_id, owner_entity_id, what="Kas kasus keuangan")
    op = _CASE_OP.get()
    if op:
        n = _CASE_OP_SEQ.get() + 1
        _CASE_OP_SEQ.set(n)
        txn_id, seq = f"cash_case_{op}_{n}", f"{op}:{n}"
    else:
        txn_id, seq = "", new_id("seq")
    from services import cash_ledger
    try:
        txn = await cash_ledger.create_cash(
            entity_id=cash_owner, direction=direction, amount=amount, ref_type=ref_type or "finance_case",
            ref_id=ref_id or cash_owner, seq=seq, txn_id=txn_id, account_id=account_id,
            cash_type=cash_type if cash_type in ("kas_besar", "kas_kecil") else "kas_besar", category=category,
            description=description, contra_account_code=contra, owner_entity_id=owner_entity_id, actor=actor)
    except cash_ledger.CashPostingError as exc:
        _jadi(f"kas:{seq}")   # kas TERSIMPAN (gl_status failed) — niat tidak boleh dicabut
        raise CaseActionError(f"Kas {exc.txn.get('number', '')} tercatat, tetapi jurnalnya gagal: {exc.error}. "
                              "Ulangi aksi ini untuk melanjutkan (kas yang sama dipakai ulang).") from exc
    _jadi(f"kas:{seq}")
    je = await db.journal_entries.find_one(
        {"source_type": "cash_transaction", "source_id": txn["id"], "status": {"$ne": "void"}}, {"_id": 0})
    out = [_doc("cash_transaction", txn["id"], txn.get("number", ""),
                f"Kas {'masuk' if direction == 'in' else 'keluar'} {_rp(amount)}")]
    return {"txn": safe_doc(txn), "documents": out + _je_doc(je, f"Jurnal kas {txn.get('number', '')}")}


async def _order_or_fail(order_id: str) -> Dict[str, Any]:
    o = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not o:
        raise CaseActionError(f"Pesanan {order_id} tidak ditemukan")
    return o


def _pay_seq() -> str:
    """PK-19 — urutan baris pembayaran dalam satu aksi kasus: id baris tetap per (kasus, aksi, langkah, urutan), jadi
    aksi yang diulang memakai baris yang sama (pola `cash_case_{op}_{n}` di `_cash_txn`)."""
    op = _CASE_OP.get()
    if not op:
        return new_id("seq")
    n = _CASE_PAY_SEQ.get() + 1
    _CASE_PAY_SEQ.set(n)
    return f"{op}:{n}"


async def _apply_payment(order_id: str, amount: float, case: Dict[str, Any],
                         method: str, *, customer_id: str = "", entity_id: str = "") -> List[Dict[str, Any]]:
    """Tempelkan pelunasan ke pesanan (piutang berkurang) TANPA kas baru — lewat SATU fungsi alokasi (PK-19): pesanan
    harus milik pelanggan kasus & PT kasus (salah PT: PT pemilik tagihan), berstatus hidup, dan muat di sisa
    tagihannya. Id baris tetap per (kasus, aksi, langkah, urutan) → diulang = baris yang sama."""
    from services import ar_allocation_service as aas
    o = await _order_or_fail(order_id)
    res = await aas.allocate(
        kind="kasus", order_id=order_id, amount=amount, source_id=case["id"],
        source_number=f"{case.get('number') or case['id']} (kasus keuangan)",
        customer_id=customer_id or case.get("customer_id") or o.get("customer_id") or "",
        entity_id=entity_id or case.get("entity_id") or o.get("entity_id") or "", date=now_iso(),
        actor="kasus keuangan", method=method, seq=_pay_seq())
    _jadi(f"bayar:{order_id}")
    return [_doc("order_payment", order_id, res.get("order_number", order_id),
                 f"Pelunasan {_rp(amount)} menempel di pesanan "
                 f"{res.get('order_number', order_id)}")]


# ═════════════════════════════════════════════════════════════════════════════
#  PEMERIKSA PER AKSI (tanpa tulisan) — PK-25
# ═════════════════════════════════════════════════════════════════════════════
def _rencana(entities: List[str]) -> Dict[str, Any]:
    return {"entities": [e for i, e in enumerate(entities) if e and e not in entities[:i]],
            "allocations": [], "journals": [], "cash": [], "twin": False}


def _j(entity_id: str, debit_acc: str, credit_acc: str, amount: float, suffix: str = "",
       via: str = "kasus") -> Dict[str, Any]:
    return {"entity_id": entity_id, "debit_acc": debit_acc, "credit_acc": credit_acc, "amount": _amt(amount),
            "suffix": suffix, "via": via}


def _nominal(p: Dict[str, Any]) -> float:
    amt = _amt(p.get("amount"))
    if amt <= EPS:
        raise CaseActionError("Nominal harus lebih dari 0")
    return amt


async def _targets(kind: str, rows: List[Dict[str, Any]], *, customer_id: str, entity_id: str) -> None:
    """Target pelunasan diperiksa SATU pemeriksa alokasi PK-19 (pelanggan, PT, status, sisa). Galatnya (400/403/409)
    diteruskan apa adanya."""
    from services import ar_allocation_service as aas
    await aas.validate_targets(kind, rows, customer_id=customer_id, entity_id=entity_id)


async def _rekening(entity_id: str, account_id: str, cash_type: str) -> Dict[str, Any]:
    from services import cash_ledger
    return await cash_ledger.periksa_rekening(entity_id, account_id,
                                              cash_type if cash_type in ("kas_besar", "kas_kecil") else "kas_besar")


async def _holding_line(case: Dict[str, Any]) -> Dict[str, Any]:
    line_id = (case.get("source") or {}).get("id") or ""
    ln = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}) if line_id else None
    if not ln or ln.get("status") != "holding":
        raise CaseActionError("Sumber kasus bukan titipan dana yang masih aktif")
    return ln


async def _cek_alokasi_titipan(case, p):
    line_id = (case.get("source") or {}).get("id") or ""
    if not line_id:
        raise CaseActionError(
            "Kasus ini belum menunjuk baris titipan dana. Buka kasus dari layar "
            "Rekonsiliasi Bank → Dana Titipan supaya sumber dananya jelas.")
    ln = await _holding_line(case)
    allocs = [{"order_id": a.get("order_id"), "amount": _amt(a.get("amount"))} for a in (p.get("allocations") or [])]
    if not allocs:
        raise CaseActionError("Pilih pesanan yang dilunasi beserta nominalnya")
    total = _amt(sum(a["amount"] for a in allocs))
    sisa = _amt(_amt(ln.get("holding_remaining", ln.get("amount"))) - sum(
        _amt(it.get("amount")) for it in (ln.get("holding_allocated") or []) if it.get("status") == "pending"))
    if total > sisa + EPS:
        raise CaseActionError(f"Σ alokasi {_rp(total)} melebihi sisa titipan {_rp(sisa)}")
    ent = ln.get("entity_id") or case.get("entity_id") or ""
    await _targets("titipan_bank", allocs, customer_id=p.get("customer_id") or case.get("customer_id") or "",
                   entity_id=ent)
    plan = _rencana([ent])
    plan["allocations"] = [{**a, "kind": "titipan_bank"} for a in allocs]
    plan["journals"] = [_j(ent, gl.ACC_TITIPAN_DANA, gl.ACC_PIUTANG, a["amount"], via="titipan") for a in allocs]
    return plan


async def _cek_refund_titipan(case, p):
    amount = _nominal(p)
    ln = await _holding_line(case)
    remaining = _amt(ln.get("holding_remaining", ln.get("amount")))
    if amount > remaining + EPS:
        raise CaseActionError(f"Pengembalian {_rp(amount)} melebihi sisa titipan {_rp(remaining)}")
    ent = case.get("entity_id") or ""
    rek = await _rekening(ent, ln.get("bank_account_id", ""), "kas_besar")
    plan = _rencana([ent])
    plan["cash"] = [{"entity_id": ent, "direction": "out", "amount": amount, "account_id": rek["account_id"]}]
    plan["journals"] = [_j(ent, gl.ACC_TITIPAN_DANA, rek["account_code"], amount, via="kas")]
    return plan


async def _cek_alokasi_uang_muka(case, p):
    from services import ar_receipt_service as ar
    cust = p.get("customer_id") or case.get("customer_id") or ""
    allocs = [{"order_id": a.get("order_id"), "amount": _amt(a.get("amount"))} for a in (p.get("allocations") or [])]
    total = _amt(sum(a["amount"] for a in allocs))
    if total <= EPS:
        raise CaseActionError("Pilih pesanan yang dilunasi beserta nominalnya")
    dep = await ar.get_deposit_balance(cust)
    if total > dep + EPS:
        raise CaseActionError(f"Alokasi {_rp(total)} melebihi saldo uang muka pelanggan {_rp(dep)}")
    ent = case.get("entity_id") or ""
    await _targets("kasus", allocs, customer_id=cust, entity_id=ent)
    plan = _rencana([ent])
    plan["allocations"] = [{**a, "kind": "kasus"} for a in allocs]
    plan["journals"] = [_j(ent, gl.ACC_UANG_MUKA_PELANGGAN, gl.ACC_PIUTANG, total, "alloc")]
    return plan


async def _cek_refund_pelanggan(case, p):
    from services import ar_receipt_service as ar
    cust = p.get("customer_id") or case.get("customer_id") or ""
    amount = _nominal(p)
    dep = await ar.get_deposit_balance(cust)
    if amount > dep + EPS:
        raise CaseActionError(f"Pengembalian {_rp(amount)} melebihi saldo uang muka pelanggan {_rp(dep)}")
    ent = case.get("entity_id") or ""
    rek = await _rekening(ent, p.get("account_id", ""), p.get("cash_type") or "kas_besar")
    plan = _rencana([ent])
    plan["cash"] = [{"entity_id": ent, "direction": "out", "amount": amount, "account_id": rek["account_id"]}]
    plan["journals"] = [_j(ent, gl.ACC_UANG_MUKA_PELANGGAN, rek["account_code"], amount, via="kas")]
    return plan


async def _cek_refund_store_credit(case, p):
    from services import store_credit_service as sc
    cust = p.get("customer_id") or case.get("customer_id") or ""
    amount = _nominal(p)
    ent = case.get("entity_id") or ""
    bal = await sc.balance(cust, ent)
    if amount > bal + EPS:
        raise CaseActionError(f"Pengembalian {_rp(amount)} melebihi saldo kredit toko {_rp(bal)}")
    rek = await _rekening(ent, p.get("account_id", ""), p.get("cash_type") or "kas_besar")
    plan = _rencana([ent])
    plan["cash"] = [{"entity_id": ent, "direction": "out", "amount": amount, "account_id": rek["account_id"]}]
    plan["journals"] = [_j(ent, gl.ACC_STORE_CREDIT, rek["account_code"], amount, via="kas")]
    return plan


async def _rekening_pindah_buku(case, p):
    to_acc = p.get("to_account_id") or ""
    src = (case.get("source") or {})
    from_acc = p.get("account_id") or ""
    if not from_acc and src.get("kind") in ("bank_holding", "bank_line") and src.get("id"):
        ln = await db.bank_statement_lines.find_one({"id": src["id"]}, {"_id": 0})
        from_acc = (ln or {}).get("bank_account_id", "")
    if not (from_acc and to_acc):
        raise CaseActionError("Rekening asal dan rekening tujuan wajib dipilih")
    if from_acc == to_acc:
        raise CaseActionError("Rekening asal dan tujuan tidak boleh sama")
    return from_acc, to_acc


async def _cek_pindah_buku(case, p):
    amount = _nominal(p)
    from_acc, to_acc = await _rekening_pindah_buku(case, p)
    ent = case.get("entity_id") or ""
    asal, tuju = await _rekening(ent, from_acc, ""), await _rekening(ent, to_acc, "")
    plan = _rencana([ent])
    plan["cash"] = [{"entity_id": ent, "direction": "out", "amount": amount, "account_id": from_acc},
                    {"entity_id": ent, "direction": "in", "amount": amount, "account_id": to_acc}]
    plan["journals"] = [_j(ent, gl.ACC_KAS_TRANSIT, asal["account_code"], amount, via="kas"),
                        _j(ent, tuju["account_code"], gl.ACC_KAS_TRANSIT, amount, via="kas")]
    return plan


async def _cek_akui_dipegang_karyawan(case, p):
    amount = _nominal(p)
    if not (p.get("employee_name") or "").strip():
        raise CaseActionError("Nama karyawan yang memegang uang wajib diisi")
    order_id = p.get("order_id") or (case.get("order_ids") or [""])[0]
    o = await _order_or_fail(order_id)
    ent = case.get("entity_id") or o.get("entity_id") or ""
    await _targets("kasus", [{"order_id": order_id, "amount": amount}],
                   customer_id=case.get("customer_id") or o.get("customer_id") or "", entity_id=ent)
    je_ent = o.get("entity_id") or ent
    plan = _rencana([ent, je_ent])
    plan["allocations"] = [{"order_id": order_id, "amount": amount, "kind": "kasus"}]
    plan["journals"] = [_j(je_ent, gl.ACC_PIUTANG_KARYAWAN, gl.ACC_PIUTANG, amount, "emp1")]
    return plan


async def _cek_setor_dari_karyawan(case, p):
    amount = _nominal(p)
    r = case.get("resolution") or {}
    ex = r.get("extra") or {}
    if case.get("status") != "in_progress" or ex.get("step") not in (1, 2):
        raise CaseActionError("Setoran karyawan hanya bisa sesudah langkah 1 (akui uang dipegang karyawan) berhasil.")
    held = _amt(ex.get("held_amount") or r.get("amount"))
    remaining = _amt(held - _amt(ex.get("settled_amount")))
    surplus = _amt(amount - remaining) if amount > remaining + EPS else 0.0
    if surplus and not (case.get("customer_id") or p.get("customer_id")):
        raise CaseActionError(
            f"Setoran {_rp(amount)} melebihi sisa piutang karyawan {_rp(remaining)} dan kasus tanpa pelanggan "
            "— kelebihan tidak bisa dijadikan kredit toko.")
    ent = case.get("entity_id") or ""
    rek = await _rekening(ent, p.get("account_id", ""), p.get("cash_type") or "kas_besar")
    plan = _rencana([ent])
    to_emp = _amt(amount - surplus)
    if to_emp > EPS:
        plan["journals"].append(_j(ent, rek["account_code"], gl.ACC_PIUTANG_KARYAWAN, to_emp, via="kas"))
    if surplus:
        plan["journals"].append(_j(ent, rek["account_code"], gl.ACC_STORE_CREDIT, surplus, via="kas"))
    plan["cash"] = [{"entity_id": ent, "direction": "in", "amount": j["amount"], "account_id": rek["account_id"]}
                    for j in plan["journals"]]
    return plan


async def _cek_realokasi_pesanan(case, p):
    from services.customer_service import _order_paid
    amount = _nominal(p)
    src_id, dst_id = p.get("from_order_id") or "", p.get("to_order_id") or ""
    if not (src_id and dst_id) or src_id == dst_id:
        raise CaseActionError("Pesanan asal dan pesanan tujuan wajib berbeda dan terisi")
    src, dst = await _order_or_fail(src_id), await _order_or_fail(dst_id)
    if src.get("customer_id") != dst.get("customer_id"):
        raise CaseActionError(
            "Realokasi hanya boleh antar pesanan pelanggan yang SAMA. Untuk pelanggan "
            "berbeda, kembalikan dananya lalu terima pembayaran baru.")
    if (src.get("entity_id") or "") != (dst.get("entity_id") or ""):
        raise CaseActionError(
            "Realokasi hanya boleh antar pesanan pada PT yang sama — perpindahan uang "
            "antar PT memakai playbook 'Pelanggan bayar ke PT yang salah'.")
    if _amt(_order_paid(src)) < amount - EPS:
        raise CaseActionError(f"Pesanan {src.get('number') or src_id} hanya terbayar {_rp(_order_paid(src))} — "
                              f"tidak bisa dipindahkan {_rp(amount)}.")
    ent = case.get("entity_id") or ""
    await _targets("kasus", [{"order_id": dst_id, "amount": amount}], customer_id=src.get("customer_id") or "",
                   entity_id=ent)
    plan = _rencana([ent])
    plan["allocations"] = [{"order_id": dst_id, "amount": amount, "kind": "kasus"}]
    return plan


async def _cek_bank_charge(case, p):
    amount = _nominal(p)
    order_id = p.get("order_id") or (case.get("order_ids") or [""])[0]
    o = await _order_or_fail(order_id)
    ent = case.get("entity_id") or o.get("entity_id") or ""
    await _targets("kasus", [{"order_id": order_id, "amount": amount}],
                   customer_id=case.get("customer_id") or o.get("customer_id") or "", entity_id=ent)
    je_ent = o.get("entity_id") or ent
    plan = _rencana([ent, je_ent])
    plan["allocations"] = [{"order_id": order_id, "amount": amount, "kind": "kasus"}]
    plan["journals"] = [_j(je_ent, gl.ACC_BEBAN_BANK, gl.ACC_PIUTANG, amount, "chg")]
    return plan


async def _kas_kwitansi(rec: Dict[str, Any]) -> List[str]:
    ids = [c.get("id") for c in (rec.get("cash_transactions") or [])] + [rec.get("cash_txn_id", "")]
    ids += [t["id"] async for t in db.cash_transactions.find({"ref_type": "ar_receipt", "ref_id": rec["id"]},
                                                             {"_id": 0, "id": 1})]
    return sorted({i for i in ids if i})


async def _cek_batalkan_kwitansi(case, p):
    rid = p.get("receipt_id") or (case.get("source") or {}).get("id") or ""
    if not rid:
        raise CaseActionError("Kwitansi yang dibatalkan wajib ditunjuk")
    rec = await db.ar_receipts.find_one({"id": rid}, {"_id": 0})
    if not rec:
        raise CaseActionError("Kwitansi tidak ditemukan")
    if rec.get("status") == "void":
        raise CaseActionError("Kwitansi ini sudah dibatalkan sebelumnya")
    ent = rec.get("entity_id") or case.get("entity_id") or ""
    plan = _rencana([ent])
    # Jurnal pembalik = kebalikan jurnal asal kwitansi (kas, atau kwitansi deposit saja); tanpa jurnal asal tidak ada
    # yang dibalik — penyelesaian ditolak di sini, bukan sesudah kwitansinya dibatalkan.
    kas = await _kas_kwitansi(rec)
    async for je in db.journal_entries.find(
            {"status": {"$ne": "void"}, "$or": [{"source_type": "cash_transaction", "source_id": {"$in": kas}},
                                                {"source_type": "ar_receipt_deposit", "source_id": rid}]},
            {"_id": 0, "id": 1, "total_debit": 1}):
        plan["journals"].append({"entity_id": ent, "amount": _amt(je.get("total_debit")), "via": "pembalik",
                                 "reverses": je["id"]})
    return plan


def _sisi_salah_pt(case: Dict[str, Any], *, owner: str, receiver: str, amount: float,
                   kunci_lama: Optional[Dict[str, str]] = None) -> list:
    """Dua sisi jurnal kembar (PK-06) kasus salah PT. Kunci tiap sisi = `{id kasus}:ic_ap:{n}` / `{id}:ic_ar:{n}`
    (akun dan arah sama dengan sebelum PK-25); `kunci_lama` = kunci tanpa nomor yang sudah berjurnal (n = 0)."""
    from services.twin_journal import TwinSide
    num = case.get("number") or case["id"]
    lama = kunci_lama or {}
    ap = [{"account_code": gl.ACC_TITIPAN_DANA, "debit": amount, "credit": 0.0,
           "description": f"Kasus keuangan {num} · utang ke PT pemilik tagihan"},
          {"account_code": gl.ACC_IC_AP, "debit": 0.0, "credit": amount,
           "description": f"Kasus keuangan {num} · utang ke PT pemilik tagihan"}]
    ar = [{"account_code": gl.ACC_IC_AR, "debit": amount, "credit": 0.0,
           "description": f"Kasus keuangan {num} · piutang antar-perusahaan"},
          {"account_code": gl.ACC_PIUTANG, "debit": 0.0, "credit": amount,
           "description": f"Kasus keuangan {num} · piutang antar-perusahaan"}]
    return [
        TwinSide(_sfx("ic_ap"), receiver, ap, f"Penyelesaian kasus keuangan · {num} · utang ke PT pemilik tagihan",
                 num, ("finance_cases", case["id"]), "_ic_ap", source_id=lama.get("ic_ap", "")),
        TwinSide(_sfx("ic_ar"), owner, ar, f"Penyelesaian kasus keuangan · {num} · piutang antar-perusahaan",
                 num, ("finance_cases", case["id"]), "_ic_ar", source_id=lama.get("ic_ar", "")),
    ]


async def _kunci_lama_salah_pt(case: Dict[str, Any]) -> Dict[str, str]:
    """Kasus lama yang sudah berjurnal dengan kunci tanpa nomor (sebelum PK-25) dikenali untuk `n = 0`."""
    if _CASE_N.get() not in ("", "0"):
        return {}
    out = {}
    for base in ("ic_ap", "ic_ar"):
        sid = f"{case['id']}:{base}"
        if await db.journal_entries.find_one({"source_type": "finance_case", "source_id": sid,
                                              "status": {"$ne": "void"}}, {"_id": 1}):
            out[base] = sid
    return out


async def _cek_settlement_antar_entitas(case, p):
    from services import interco_money_service as money
    from services import twin_journal as twin
    amount = _nominal(p)
    owner = (p.get("owner_entity_id") or "").strip()
    order_id = p.get("order_id") or (case.get("order_ids") or [""])[0]
    receiver = case.get("entity_id") or ""
    if not owner:
        raise CaseActionError("PT pemilik tagihan wajib dipilih")
    if owner == receiver:
        raise CaseActionError(
            "PT penerima uang dan PT pemilik tagihan sama — ini bukan kasus salah entitas")
    o = await _order_or_fail(order_id)
    if (o.get("entity_id") or "") != owner:
        raise CaseActionError(
            f"Pesanan {o.get('number')} bukan milik PT pemilik tagihan yang dipilih")
    try:
        await money.assert_pair(owner, receiver, what="Dokumen antar-PT salah transfer")
    except money.IntercoMoneyError as exc:
        raise CaseActionError(str(exc)) from exc
    if (case.get("source") or {}).get("id") and (case.get("source") or {}).get("kind") == "bank_holding":
        ln = await _holding_line(case)
        sisa = _amt(ln.get("holding_remaining", ln.get("amount")))
        if amount > sisa + EPS:
            raise CaseActionError(f"Nominal {_rp(amount)} melebihi sisa titipan {_rp(sisa)}")
    await _targets("kasus", [{"order_id": order_id, "amount": amount}],
                   customer_id=case.get("customer_id") or o.get("customer_id") or "", entity_id=owner)
    sisi = _sisi_salah_pt(case, owner=owner, receiver=receiver, amount=amount,
                          kunci_lama=await _kunci_lama_salah_pt(case))
    try:   # PK-06 — akun & periode KEDUA buku diperiksa sebelum efek pertama
        await twin.preflight_twin(source_type="finance_case", base_id=case["id"], date="", sides=sisi)
    except twin.TwinJournalError as exc:
        if exc.cause == "period":
            raise CaseConflict(str(exc)) from exc
        raise CaseActionError(str(exc)) from exc
    plan = _rencana([receiver, owner])
    plan["allocations"] = [{"order_id": order_id, "amount": amount, "kind": "kasus", "entity_id": owner}]
    plan["journals"] = [_j(receiver, gl.ACC_TITIPAN_DANA, gl.ACC_IC_AP, amount, "ic_ap"),
                        _j(owner, gl.ACC_IC_AR, gl.ACC_PIUTANG, amount, "ic_ar")]
    plan["twin"] = True
    return plan


async def _supplier(case, p) -> Dict[str, Any]:
    sup = await db.suppliers.find_one({"id": p.get("supplier_id") or case.get("supplier_id") or ""}, {"_id": 0})
    if not sup:
        raise CaseActionError("Supplier tidak ditemukan")
    return sup


async def _cek_uang_muka_supplier(case, p):
    amount = _nominal(p)
    await _supplier(case, p)
    ent = case.get("entity_id") or ""
    plan = _rencana([ent])
    plan["journals"] = [_j(ent, gl.ACC_UANG_MUKA, gl.ACC_HUTANG, amount, "ap_adv")]
    return plan


async def _cek_terima_refund_supplier(case, p):
    amount = _nominal(p)
    sup = await _supplier(case, p)
    adv = _amt(sup.get("advance_balance"))
    if amount > adv + EPS:
        raise CaseActionError(f"Pengembalian {_rp(amount)} melebihi saldo uang muka supplier {_rp(adv)}")
    ent = case.get("entity_id") or ""
    rek = await _rekening(ent, p.get("account_id", ""), p.get("cash_type") or "kas_besar")
    plan = _rencana([ent])
    plan["cash"] = [{"entity_id": ent, "direction": "in", "amount": amount, "account_id": rek["account_id"]}]
    plan["journals"] = [_j(ent, rek["account_code"], gl.ACC_UANG_MUKA, amount, via="kas")]
    return plan


async def _entity_name(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "short_name": 1, "legal_name": 1,
                                                                "name": 1}) or {}
    return e.get("short_name") or e.get("legal_name") or e.get("name") or entity_id


def entities_of(action: str, case: Dict[str, Any], payload: Dict[str, Any]) -> List[str]:
    """PT yang bukunya disentuh aksi: PT kasus, ditambah PT pemilik tagihan untuk kasus salah PT."""
    out = [case.get("entity_id") or ""]
    if action == "settlement_antar_entitas" and (payload.get("owner_entity_id") or "").strip():
        out.append(payload["owner_entity_id"].strip())
    return [e for i, e in enumerate(out) if e and e not in out[:i]]


async def precheck(action: str, case: Dict[str, Any], payload: Dict[str, Any], *,
                   lanjutan: bool = False, op_id: str = "") -> Dict[str, Any]:
    """PK-25 (FX-09) — langkah PERIKSA penyelesaian, TANPA tulisan apa pun → rencana
    `{"entities", "allocations", "journals": [{entity_id, debit_acc, credit_acc, amount, suffix}], "cash", "twin"}`.

    Menjalankan pemeriksa aksi (isi permintaan, target pelunasan lewat `validate_targets` PK-19, saldo deposit/titipan/
    saldo kredit/uang muka cukup, rekening, nominal > 0; kasus salah PT: akun & periode kedua buku lewat
    `twin_journal.preflight_twin`), lalu `preflight_posting(PT, hari ini)` untuk SETIAP PT di `entities`. Aksi pada
    playbook yang memindahkan uang wajib punya minimal satu jurnal di rencana. `lanjutan=True` (niat `pending`
    diteruskan): efek sebagian sudah jadi, jadi hanya periode yang diperiksa ulang — efek berikutnya tetap bersyarat.
    Penolakan: `CaseActionError` (400), `CaseConflict` (409, periode), `HTTPException` dari pemeriksa PK-19/PK-20."""
    from services.finance_case_playbooks import BY_CODE
    fn = PRECHECKS.get(action)
    if not fn:
        raise CaseActionError(f"Aksi '{action}' belum punya pelaksana")
    if lanjutan:
        plan = _rencana(entities_of(action, case, payload))
    else:
        op = op_id or op_id_of(case, action)
        t_id, t_n = _CASE_ID.set(case["id"]), _CASE_N.set(op.rsplit("_", 1)[-1])   # kunci jurnal = kunci pelaksana
        try:
            plan = await fn(case, payload)
        finally:
            _CASE_N.reset(t_n)
            _CASE_ID.reset(t_id)
        if (BY_CODE.get(case.get("case_type") or "") or {}).get("moves_cash", True) and not plan["journals"]:
            raise CaseActionError(PESAN_TANPA_JURNAL)
    for eid in plan["entities"]:
        try:
            await gl.preflight_posting(eid)
        except gl.ClosedPeriodError as exc:
            raise CaseConflict(f"{await _entity_name(eid)}: {exc}") from exc
    return plan


# ═════════════════════════════════════════════════════════════════════════════
#  AKSI PER PLAYBOOK (PELAKSANA)
# ═════════════════════════════════════════════════════════════════════════════
async def act_alokasi_titipan(case: Dict[str, Any], p: Dict[str, Any],
                              actor: Dict[str, Any]) -> Dict[str, Any]:
    """Titipan dana G-8 → melunasi pesanan pelanggan (Dr 2-1950 / Cr 1-1200)."""
    from services import bank_recon_service as bank
    line_id = (case.get("source") or {}).get("id") or ""
    if not line_id:
        raise CaseActionError(
            "Kasus ini belum menunjuk baris titipan dana. Buka kasus dari layar "
            "Rekonsiliasi Bank → Dana Titipan supaya sumber dananya jelas.")
    allocs = [{"order_id": a["order_id"], "amount": float(a["amount"])}
              for a in (p.get("allocations") or [])]
    if not allocs:
        raise CaseActionError("Pilih pesanan yang dilunasi beserta nominalnya")

    async def _alokasi():
        res = await bank.allocate_holding(
            line_id, allocs, p.get("customer_id") or case.get("customer_id") or "",
            p.get("reason_code") or "", p.get("note") or f"Kasus {case['number']}",
            actor.get("name", ""), None)
        # `allocate_holding` mengembalikan BARIS titipan setelah dialokasikan; alokasi yang
        # baru saja terjadi adalah N entri terakhir `holding_allocated[]` (append-only).
        return {"done": [{k: a.get(k) for k in ("je_id", "je_number", "order_id", "order_number", "amount")}
                         for a in (res.get("holding_allocated") or [])[-len(allocs):]]}

    done = ((await _sekali("alokasi_titipan", _alokasi)) or {}).get("done") or []
    docs: List[Dict[str, Any]] = []
    for a in done:
        if a.get("je_id"):
            docs.append(_doc("journal_entry", a["je_id"], a.get("je_number", ""),
                             "Jurnal Dr 2-1950 Titipan Dana / Cr 1-1200 Piutang"))
        docs.append(_doc("order_payment", a.get("order_id", ""), a.get("order_number", ""),
                         f"Pelunasan {_rp(a.get('amount'))} di pesanan "
                         f"{a.get('order_number', '')}"))
    if not any(d["kind"] == "journal_entry" for d in docs):
        raise CaseActionError(
            "Alokasi titipan tidak menghasilkan jurnal — kasus tidak ditutup supaya "
            "uangnya tidak hilang dari laporan. Periksa buku besar lalu coba lagi.")
    return {"documents": docs, "amount": round(sum(a["amount"] for a in allocs), 2)}


async def act_refund_titipan(case: Dict[str, Any], p: Dict[str, Any],
                             actor: Dict[str, Any]) -> Dict[str, Any]:
    """Dana tak dikenal dikembalikan ke pengirim (Dr 2-1950 / Cr Kas-Bank)."""
    line_id = (case.get("source") or {}).get("id") or ""
    amount = round(float(p.get("amount") or 0), 2)
    ln = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}) if line_id else None
    if not ln or ln.get("status") != "holding":
        raise CaseActionError("Sumber kasus bukan titipan dana yang masih aktif")
    res = await _cash_txn(
        direction="out", amount=amount, category="titipan",
        description=f"Pengembalian dana tak dikenal · {case['number']}",
        entity_id=case.get("entity_id", ""), account_id=ln.get("bank_account_id", ""),
        cash_type="kas_besar", ref_type="finance_case", ref_id=case["id"],
        contra=gl.ACC_TITIPAN_DANA, owner_entity_id=case.get("entity_id", ""),
        actor=actor.get("name", "system"))
    # Titipan berkurang: baris ditutup lewat service G-8 supaya INV-BNK-03 tetap sah (bersyarat sisa, sekali per niat).
    await _sekali("titipan_berkurang", lambda: _titipan_turun(line_id, amount, case, actor))
    return {"documents": res["documents"], "amount": amount}


async def _titipan_turun(line_id: str, amount: float, case: Dict[str, Any], actor: Dict[str, Any], *,
                         label: str = "pengembalian dana") -> Dict[str, Any]:
    """Sisa titipan baris mutasi turun (bersyarat, kunci = id niat penyelesaian → tidak dua kali)."""
    from services import bank_recon_service as bank
    await bank.holding_refunded(line_id, amount, case["number"], actor.get("name", ""), label=label,
                                ref_key=_CASE_OP.get() or case["id"])
    return {"line_id": line_id, "amount": round(float(amount or 0), 2)}


async def act_alokasi_uang_muka(case: Dict[str, Any], p: Dict[str, Any],
                                actor: Dict[str, Any]) -> Dict[str, Any]:
    """Kelebihan bayar (uang muka pelanggan) dipakai melunasi pesanan lain."""
    from services import ar_receipt_service as ar
    cust = p.get("customer_id") or case.get("customer_id") or ""
    allocs = p.get("allocations") or []
    total = round(sum(float(a["amount"]) for a in allocs), 2)
    if total <= EPS:
        raise CaseActionError("Pilih pesanan yang dilunasi beserta nominalnya")
    docs: List[Dict[str, Any]] = []
    for a in allocs:
        docs += await _apply_payment(a["order_id"], float(a["amount"]), case, "deposit", customer_id=cust)
    # Deposit berkurang bersyarat saldo cukup (CAS `_adjust_deposit`), sekali per niat penyelesaian.
    await _sekali("deposit_berkurang", lambda: ar.adjust_deposit(cust, -total))
    je = await _jurnal(case, entity_id=case.get("entity_id", ""), amount=total,
                       debit_acc=gl.ACC_UANG_MUKA_PELANGGAN, credit_acc=gl.ACC_PIUTANG,
                       label=f"{case['number']} · uang muka dipakai melunasi pesanan", suffix="alloc", actor=actor)
    docs += _je_doc(je, "Jurnal Dr 2-1400 Uang Muka Pelanggan / Cr 1-1200 Piutang")
    return {"documents": docs, "amount": total}


async def act_refund_pelanggan(case: Dict[str, Any], p: Dict[str, Any],
                               actor: Dict[str, Any]) -> Dict[str, Any]:
    """Uang muka pelanggan dikembalikan (Dr 2-1400 / Cr Kas-Bank)."""
    from services import ar_receipt_service as ar
    cust = p.get("customer_id") or case.get("customer_id") or ""
    amount = round(float(p.get("amount") or 0), 2)
    res = await _cash_txn(
        direction="out", amount=amount, category="refund pelanggan",
        description=f"Pengembalian dana pelanggan · {case['number']}",
        entity_id=case.get("entity_id", ""), account_id=p.get("account_id", ""),
        cash_type=p.get("cash_type") or "kas_besar", ref_type="ar_refund",
        ref_id=case["id"], owner_entity_id=case.get("entity_id", ""),
        actor=actor.get("name", "system"))
    await _sekali("deposit_berkurang", lambda: ar.adjust_deposit(cust, -amount))
    return {"documents": res["documents"], "amount": amount}


async def act_refund_store_credit(case: Dict[str, Any], p: Dict[str, Any],
                                  actor: Dict[str, Any]) -> Dict[str, Any]:
    """Saldo kredit toko dicairkan menjadi uang (Dr 2-1450 / Cr Kas-Bank)."""
    from services import store_credit_service as sc
    cust = p.get("customer_id") or case.get("customer_id") or ""
    amount = round(float(p.get("amount") or 0), 2)
    ent = case.get("entity_id") or ""
    # G3 D4-CASE-01 — BUKAN `adjust` (itu menjurnal Dr 2-1450 / Cr Pendapatan Lain = hangus saldo).
    # Pencairan = SATU jurnal Dr 2-1450 / Cr Kas (dari transaksi kas); baris buku saldo menunjuk kasus yang sama.
    entry = await _sekali("saldo_kredit_keluar", lambda: sc._append(
        customer_id=cust, entity_id=ent, kind="payout", amount_signed=-amount, ref_type="finance_case",
        ref_id=case["id"], ref_number=case.get("number", ""), note=f"Dicairkan lewat kasus {case['number']}",
        actor=actor))
    try:
        res = await _cash_txn(
            direction="out", amount=amount, category="refund store credit",
            description=f"Pencairan saldo kredit toko · {case['number']}",
            entity_id=ent, account_id=p.get("account_id", ""),
            cash_type=p.get("cash_type") or "kas_besar", ref_type="finance_case",
            ref_id=case["id"], contra=gl.ACC_STORE_CREDIT, owner_entity_id=ent,
            actor=actor.get("name", "system"))
    except cash_rejected_types() as exc:
        # Kas DITOLAK sebelum tertulis → saldo yang sudah dikurangi dikembalikan dan penandanya dicabut.
        await sc._append(customer_id=cust, entity_id=ent, kind="payout_reversal", amount_signed=amount,
                         ref_type="finance_case", ref_id=case["id"], ref_number=case.get("number", ""),
                         note=f"Pencairan gagal — saldo dikembalikan ({case['number']})", actor=actor)
        await _lepas_langkah("saldo_kredit_keluar")
        raise exc
    docs = res["documents"] + [
        _doc("store_credit_entry", (entry or {}).get("id", ""), "",
             f"Baris buku saldo kredit −{_rp(amount)}")]
    return {"documents": docs, "amount": amount}


def cash_rejected_types() -> tuple:
    from services import cash_ledger
    return (cash_ledger.CashRejected,)


async def _lepas_langkah(nama: str) -> None:
    cid, op = _CASE_ID.get(), _CASE_OP.get()
    if cid and op:
        await db.finance_cases.update_one({"id": cid, "resolution_intent.op_id": op},
                                          {"$unset": {f"resolution_intent.steps.{nama}": ""}})


async def act_pindah_buku(case: Dict[str, Any], p: Dict[str, Any],
                          actor: Dict[str, Any]) -> Dict[str, Any]:
    """Pindah-buku antar rekening sendiri lewat akun transit (akun transit kembali nol)."""
    amount = round(float(p.get("amount") or 0), 2)
    from_acc, to_acc = await _rekening_pindah_buku(case, p)
    names = {}
    for aid in (from_acc, to_acc):
        acc = await db.bank_accounts.find_one({"id": aid}, {"_id": 0})
        if not acc:
            raise CaseActionError(f"Rekening {aid} tidak ditemukan")
        names[aid] = acc.get("name") or acc.get("bank_name") or aid
    ent = case.get("entity_id", "")
    out = await _cash_txn(
        direction="out", amount=amount, category="pindah buku",
        description=f"Pindah-buku ke {names[to_acc]} · {case['number']}",
        entity_id=ent, account_id=from_acc, ref_type="finance_case", ref_id=case["id"],
        contra=gl.ACC_KAS_TRANSIT, owner_entity_id=ent, actor=actor.get("name", "system"))
    inn = await _cash_txn(
        direction="in", amount=amount, category="pindah buku",
        description=f"Pindah-buku dari {names[from_acc]} · {case['number']}",
        entity_id=ent, account_id=to_acc, ref_type="finance_case", ref_id=case["id"],
        contra=gl.ACC_KAS_TRANSIT, owner_entity_id=ent, actor=actor.get("name", "system"))
    return {"documents": out["documents"] + inn["documents"], "amount": amount,
            "extra": {"from_account_id": from_acc, "to_account_id": to_acc,
                      "from_account": names[from_acc], "to_account": names[to_acc]}}


async def act_akui_dipegang_karyawan(case: Dict[str, Any], p: Dict[str, Any],
                                     actor: Dict[str, Any]) -> Dict[str, Any]:
    """Langkah 1: piutang pelanggan lunas → berpindah jadi piutang karyawan."""
    amount = round(float(p.get("amount") or 0), 2)
    order_id = p.get("order_id") or (case.get("order_ids") or [""])[0]
    emp = (p.get("employee_name") or "").strip()
    if not emp:
        raise CaseActionError("Nama karyawan yang memegang uang wajib diisi")
    o = await _order_or_fail(order_id)
    docs = await _apply_payment(order_id, amount, case, "titipan_karyawan")
    je = await _jurnal(case, entity_id=o.get("entity_id") or case.get("entity_id", ""), amount=amount,
                       debit_acc=gl.ACC_PIUTANG_KARYAWAN, credit_acc=gl.ACC_PIUTANG,
                       label=f"{case['number']} · uang dipegang {emp}", suffix="emp1", actor=actor)
    docs += _je_doc(je, "Jurnal Dr 1-1280 Piutang Titipan Karyawan / Cr 1-1200 Piutang")
    return {"documents": docs, "amount": amount, "hold": True,
            "extra": {"employee_name": emp, "step": 1, "held_amount": amount, "settled_amount": 0.0},
            "next_action": "setor_dari_karyawan"}


async def act_setor_dari_karyawan(case: Dict[str, Any], p: Dict[str, Any],
                                  actor: Dict[str, Any]) -> Dict[str, Any]:
    """Langkah 2: karyawan menyetor → piutang karyawan berkurang (G3 D4-CASE-03: wajib sesudah langkah 1,
    dibatasi sisa piutang; setoran sebagian membiarkan kasus tetap berjalan)."""
    amount = round(float(p.get("amount") or 0), 2)
    r = case.get("resolution") or {}
    ex = r.get("extra") or {}
    if case.get("status") != "in_progress" or ex.get("step") not in (1, 2):
        raise CaseActionError("Setoran karyawan hanya bisa sesudah langkah 1 (akui uang dipegang karyawan) berhasil.")
    held = round(float(ex.get("held_amount") or r.get("amount") or 0), 2)
    settled = round(float(ex.get("settled_amount") or 0), 2)
    remaining = round(held - settled, 2)
    cust = case.get("customer_id") or p.get("customer_id") or ""
    surplus = round(amount - remaining, 2) if amount > remaining + EPS else 0.0
    if surplus and not cust:
        raise CaseActionError(
            f"Setoran {_rp(amount)} melebihi sisa piutang karyawan {_rp(remaining)} dan kasus tanpa pelanggan "
            "— kelebihan tidak bisa dijadikan kredit toko.")
    emp = (p.get("employee_name") or ex.get("employee_name") or "karyawan")
    # PK-07 (FX-01) — dulu ada panggilan kas senilai `amount` penuh di sini (hasilnya dibuang) SEBELUM kas bagian
    # piutang karyawan di bawah → kas & jurnal ganda, saldo 1-1280 minus. Kini satu kas per bagian setoran.
    to_emp = round(amount - surplus, 2)
    docs: List[Dict[str, Any]] = []
    if to_emp > EPS:
        res = await _cash_txn(
            direction="in", amount=to_emp, category="setoran karyawan",
            description=f"Setoran {emp} · {case['number']}",
            entity_id=case.get("entity_id", ""), account_id=p.get("account_id", ""),
            cash_type=p.get("cash_type") or "kas_besar", ref_type="finance_case",
            ref_id=case["id"], contra=gl.ACC_PIUTANG_KARYAWAN,
            owner_entity_id=case.get("entity_id", ""), actor=actor.get("name", "system"))
        docs += res["documents"]
    if surplus:
        # Keputusan user 2026-10-06 — kelebihan setoran = KREDIT TOKO pelanggan (Dr Kas / Cr 2-1450),
        # tercatat di buku saldo kredit toko yang sudah ada (satu jurnal dari transaksi kas).
        from services import store_credit_service as sc
        res2 = await _cash_txn(
            direction="in", amount=surplus, category="kelebihan setoran karyawan",
            description=f"Kelebihan setoran {emp} → kredit toko pelanggan · {case['number']}",
            entity_id=case.get("entity_id", ""), account_id=p.get("account_id", ""),
            cash_type=p.get("cash_type") or "kas_besar", ref_type="finance_case",
            ref_id=case["id"], contra=gl.ACC_STORE_CREDIT,
            owner_entity_id=case.get("entity_id", ""), actor=actor.get("name", "system"))
        entry = await sc.issue(customer_id=cust, entity_id=case.get("entity_id", ""), amount=surplus,
                               ref_type="finance_case_surplus", ref_id=res2["txn"]["id"],
                               ref_number=case.get("number", ""), actor=actor,
                               note=f"Kelebihan setoran karyawan · {case['number']}")
        _jadi("saldo_kredit_masuk")
        docs += res2["documents"] + [_doc("store_credit_entry", (entry or {}).get("id", ""), "",
                                          f"Kredit toko +{_rp(surplus)}")]
    new_settled = round(settled + to_emp, 2)
    left = round(held - new_settled, 2)
    return {"documents": docs, "amount": amount, "hold": left > EPS,
            "next_action": "setor_dari_karyawan" if left > EPS else "",
            "extra": {"employee_name": emp, "step": 2, "held_amount": held, "surplus_to_credit": surplus,
                      "settled_amount": new_settled, "remaining_amount": max(left, 0.0)}}


async def act_realokasi_pesanan(case: Dict[str, Any], p: Dict[str, Any],
                                actor: Dict[str, Any]) -> Dict[str, Any]:
    """Alokasi pembayaran berpindah antar pesanan (ledger tambah-saja, tanpa void)."""
    amount = round(float(p.get("amount") or 0), 2)
    src_id, dst_id = p.get("from_order_id") or "", p.get("to_order_id") or ""
    if not (src_id and dst_id) or src_id == dst_id:
        raise CaseActionError("Pesanan asal dan pesanan tujuan wajib berbeda dan terisi")
    src, dst = await _order_or_fail(src_id), await _order_or_fail(dst_id)
    if src.get("customer_id") != dst.get("customer_id"):
        raise CaseActionError(
            "Realokasi hanya boleh antar pesanan pelanggan yang SAMA. Untuk pelanggan "
            "berbeda, kembalikan dananya lalu terima pembayaran baru.")
    if (src.get("entity_id") or "") != (dst.get("entity_id") or ""):
        raise CaseActionError(
            "Realokasi hanya boleh antar pesanan pada PT yang sama — perpindahan uang "
            "antar PT memakai playbook 'Pelanggan bayar ke PT yang salah'.")
    # PK-19 — penarikan dari pesanan asal = baris negatif ber-sumber kasus (append-only) lewat modul alokasi.
    from services import ar_allocation_service as aas
    pulled = await aas.withdraw(
        kind="kasus", order_id=src_id, amount=amount, source_id=case["id"],
        source_number=f"{case.get('number') or case['id']} (dipindahkan lewat kasus)",
        customer_id=src.get("customer_id") or "", entity_id=src.get("entity_id") or "", date=now_iso(),
        actor=actor.get("name", "system"), method="realokasi", seq=_pay_seq(), note="dipindahkan lewat kasus")
    _jadi(f"tarik:{src_id}")
    docs = [_doc("order_payment", src_id, pulled.get("order_number", src_id),
                 f"Pengurang alokasi −{_rp(amount)} di pesanan "
                 f"{pulled.get('order_number', '')}")]
    docs += await _apply_payment(dst_id, amount, case, "realokasi", customer_id=src.get("customer_id") or "")
    return {"documents": docs, "amount": amount,
            "extra": {"from_order": src.get("number"), "to_order": dst.get("number")}}


async def act_bank_charge(case: Dict[str, Any], p: Dict[str, Any],
                          actor: Dict[str, Any]) -> Dict[str, Any]:
    """Selisih kecil karena biaya bank → Dr 6-8000 / Cr 1-1200 + pesanan ditutup."""
    amount = round(float(p.get("amount") or 0), 2)
    order_id = p.get("order_id") or (case.get("order_ids") or [""])[0]
    o = await _order_or_fail(order_id)
    docs = await _apply_payment(order_id, amount, case, "bank_charge")
    je = await _jurnal(case, entity_id=o.get("entity_id") or case.get("entity_id", ""), amount=amount,
                       debit_acc=gl.ACC_BEBAN_BANK, credit_acc=gl.ACC_PIUTANG,
                       label=f"{case['number']} · selisih biaya bank {o.get('number', '')}", suffix="chg",
                       actor=actor)
    docs += _je_doc(je, "Jurnal Dr 6-8000 Beban Administrasi Bank / Cr 1-1200 Piutang")
    return {"documents": docs, "amount": amount}


async def act_batalkan_kwitansi(case: Dict[str, Any], p: Dict[str, Any],
                                actor: Dict[str, Any]) -> Dict[str, Any]:
    """Giro ditolak → kwitansi dibatalkan (jurnal pembalik) + nota denda opsional."""
    from services import ar_receipt_service as ar
    rid = p.get("receipt_id") or (case.get("source") or {}).get("id") or ""
    if not rid:
        raise CaseActionError("Kwitansi yang dibatalkan wajib ditunjuk")
    rec = await db.ar_receipts.find_one({"id": rid}, {"_id": 0})
    if not rec:
        raise CaseActionError("Kwitansi tidak ditemukan")

    async def _batal():
        if rec.get("status") == "void":
            raise CaseActionError("Kwitansi ini sudah dibatalkan sebelumnya")
        voided = await ar.void_receipt(rid, actor)
        return {"status": (voided or {}).get("status", "void")}

    voided = await _sekali("batal_kwitansi", _batal)
    docs = [_doc("ar_receipt", rid, rec.get("number", rid),
                 f"Kwitansi {rec.get('number', rid)} dibatalkan (jurnal pembalik)")]
    # Jurnal PEMBALIK-nya diposting `void_receipt` lewat `gl.post_cash_void` / `reverse_deposit_only_receipt`
    # (append-only: jurnal asli tidak diubah). Kita ambil jurnal itu agar ikut tercatat sebagai dokumen turunan kasus —
    # tanpa ini INV-CASE-03 benar menolak menutup kasus karena tampak "memindahkan uang tanpa jurnal".
    kas = await _kas_kwitansi(rec)
    async for rev in db.journal_entries.find(
            {"$or": [{"source_type": "cash_transaction_void", "source_id": {"$in": kas}},
                     {"source_type": "ar_receipt_deposit_void", "source_id": rid}]}, {"_id": 0}):
        docs += _je_doc(rev, f"Jurnal pembalik {rev.get('number', '')}")
    if p.get("with_penalty"):
        from services import penalty_service as pen
        order_ids = [a.get("order_id") for a in (rec.get("allocations") or [])
                     if a.get("order_id")]
        for oid in order_ids:
            # CR-T4 — nota denda dari jadwal hidup pesanan (rencana cicilan / jadwal tagihan), bukan jalur lama
            # "pesanan tanpa rencana" (`accrue_order`, dihapus D8).
            for pn in (await pen.accrue_for_order(oid, actor_name=actor.get("name", "system")) or []):
                docs.append(_doc("penalty", pn.get("id", ""), pn.get("number", ""),
                                 f"Nota denda {pn.get('number', '')} "
                                 f"({_rp(pn.get('amount'))} · {pn.get('status', '')})"))
    return {"documents": docs, "amount": round(float(rec.get("amount") or 0), 2),
            "extra": {"voided_status": (voided or {}).get("status", "void")}}


async def act_settlement_antar_entitas(case: Dict[str, Any], p: Dict[str, Any],
                                       actor: Dict[str, Any]) -> Dict[str, Any]:
    """Uang masuk di PT lain → pelunasan pesanan di PT pemilik, jurnal KEMBAR di dua buku (PK-06), dan dokumen antar-PT
    `salah_transfer` (pinjaman antar-PT) supaya saldonya tampil di Saldo Antar-PT dan bisa dilunasi (PK-25, FX-11)."""
    from services import interco_loan_service as loans
    from services import twin_journal as twin
    amount = round(float(p.get("amount") or 0), 2)
    owner = (p.get("owner_entity_id") or "").strip()
    order_id = p.get("order_id") or (case.get("order_ids") or [""])[0]
    receiver = case.get("entity_id") or ""
    if not owner:
        raise CaseActionError("PT pemilik tagihan wajib dipilih")
    if owner == receiver:
        raise CaseActionError(
            "PT penerima uang dan PT pemilik tagihan sama — ini bukan kasus salah entitas")
    o = await _order_or_fail(order_id)
    if (o.get("entity_id") or "") != owner:
        raise CaseActionError(
            f"Pesanan {o.get('number')} bukan milik PT pemilik tagihan yang dipilih")
    # EFEK — piutang pesanan di PT PEMILIK tagihan lunas (satu fungsi alokasi, id baris tetap).
    docs = await _apply_payment(order_id, amount, case, "antar_entitas", entity_id=owner)
    # JURNAL — dua buku lewat pembantu jurnal kembar PK-06 (per sisi, bisa diulang; gagal = ditandai, tidak melempar).
    sisi = _sisi_salah_pt(case, owner=owner, receiver=receiver, amount=amount,
                          kunci_lama=await _kunci_lama_salah_pt(case))
    hasil = await twin.post_twin(source_type="finance_case", base_id=case["id"], date="", sides=sisi,
                                 created_by=actor.get("name", "system"))
    gagal = [hasil[s.key] for s in sisi if (hasil.get(s.key) or {}).get("status") != "posted"]
    catat = _CASE_GL.get()
    if gagal:
        pesan = next((g["error"] for g in gagal if not g["error"].startswith("Belum dicoba")), gagal[0]["error"])
        await db.finance_cases.update_one({"id": case["id"]}, {"$set": {
            "gl_status": "failed", "gl_error": pesan[:300], "gl_failed_at": now_iso(), "updated_at": now_iso()}})
        if catat is not None:
            catat.append({"status": "failed", "error": pesan, "journal_entry_id": ""})
        return {"documents": docs, "amount": amount}
    jids = [hasil[s.key]["journal_id"] for s in sisi]
    await db.finance_cases.update_one({"id": case["id"]}, {"$set": {
        "gl_status": "posted", "gl_error": "", "journal_entry_id": jids[0], "updated_at": now_iso()}})
    if catat is not None:
        catat += [{"status": "posted", "error": "", "journal_entry_id": j} for j in jids]
    jes = {j["id"]: j async for j in db.journal_entries.find({"id": {"$in": jids}}, {"_id": 0, "id": 1, "number": 1})}
    docs += _je_doc(jes.get(jids[0]), "Jurnal PT penerima: Dr 2-1950 Titipan / Cr 2-1250 Utang Antar-PT")
    docs += _je_doc(jes.get(jids[1]), "Jurnal PT pemilik: Dr 1-1250 Piutang Antar-PT / Cr 1-1200 Piutang")
    # DOKUMEN — sepasang dokumen antar-PT `salah_transfer` (tanpa kas, tanpa jurnal pencairan; id tetap per kasus).
    pair = await loans.create_from_case(case=case, owner_entity_id=owner, receiver_entity_id=receiver,
                                        amount=amount, actor=actor)
    _jadi("dokumen_antar_pt")
    mine = pair["borrower"]   # dokumen di PT kasus (PT penerima uang)
    docs.append(_doc("interco_loan", mine["id"], mine.get("number", ""),
                     f"Dokumen antar-PT {mine.get('number', '')} · titipan salah transfer {_rp(amount)}"))
    line_id = (case.get("source") or {}).get("id") or ""
    if line_id and (case.get("source") or {}).get("kind") == "bank_holding":
        await _sekali("titipan_berkurang", lambda: _titipan_turun(line_id, amount, case, actor,
                                                                  label="settlement antar entitas"))
    return {"documents": docs, "amount": amount,
            "extra": {"owner_entity_id": owner, "receiver_entity_id": receiver,
                      "interco_loan_id": mine["id"], "interco_loan_number": mine.get("number", ""),
                      "interco_pair_id": pair["pair_id"]}}


async def act_uang_muka_supplier(case: Dict[str, Any], p: Dict[str, Any],
                                 actor: Dict[str, Any]) -> Dict[str, Any]:
    """Kelebihan bayar supplier → uang muka (Dr 1-1400 / Cr 2-1100)."""
    amount = round(float(p.get("amount") or 0), 2)
    sup_id = p.get("supplier_id") or case.get("supplier_id") or ""
    sup = await db.suppliers.find_one({"id": sup_id}, {"_id": 0})
    if not sup:
        raise CaseActionError("Supplier tidak ditemukan")
    await _sekali("uang_muka_pemasok", lambda: _inc_uang_muka(sup_id, amount))
    je = await _jurnal(case, entity_id=case.get("entity_id", ""), amount=amount,
                       debit_acc=gl.ACC_UANG_MUKA, credit_acc=gl.ACC_HUTANG,
                       label=f"{case['number']} · uang muka supplier {sup.get('name', '')}",
                       suffix="ap_adv", actor=actor)
    docs = _je_doc(je, "Jurnal Dr 1-1400 Uang Muka / Cr 2-1100 Utang Usaha")
    docs.append(_doc("supplier_advance", sup_id, sup.get("code", ""),
                     f"Saldo uang muka {sup.get('name', '')} +{_rp(amount)}"))
    return {"documents": docs, "amount": amount}


async def _inc_uang_muka(sup_id: str, delta: float) -> Dict[str, Any]:
    """Saldo uang muka pemasok ± `delta`; pengurangan bersyarat saldo cukup (tidak bisa negatif)."""
    q: Dict[str, Any] = {"id": sup_id}
    if delta < 0:
        q["advance_balance"] = {"$gte": round(-delta, 2) - EPS}
    res = await db.suppliers.update_one(q, {"$inc": {"advance_balance": round(delta, 2)},
                                            "$set": {"updated_at": now_iso()}})
    if not res.matched_count:
        raise CaseActionError("Saldo uang muka supplier baru saja berubah dan tidak cukup. Muat ulang lalu coba lagi.")
    return {"delta": round(delta, 2)}


async def act_terima_refund_supplier(case: Dict[str, Any], p: Dict[str, Any],
                                     actor: Dict[str, Any]) -> Dict[str, Any]:
    """Supplier mengembalikan uang → Dr Kas-Bank / Cr 1-1400 Uang Muka."""
    amount = round(float(p.get("amount") or 0), 2)
    sup_id = p.get("supplier_id") or case.get("supplier_id") or ""
    sup = await db.suppliers.find_one({"id": sup_id}, {"_id": 0})
    if not sup:
        raise CaseActionError("Supplier tidak ditemukan")
    res = await _cash_txn(
        direction="in", amount=amount, category="refund supplier",
        description=f"Pengembalian dana dari {sup.get('name', '')} · {case['number']}",
        entity_id=case.get("entity_id", ""), account_id=p.get("account_id", ""),
        cash_type=p.get("cash_type") or "kas_besar", ref_type="finance_case",
        ref_id=case["id"], contra=gl.ACC_UANG_MUKA,
        owner_entity_id=case.get("entity_id", ""), actor=actor.get("name", "system"))
    await _sekali("uang_muka_pemasok", lambda: _inc_uang_muka(sup_id, -amount))
    return {"documents": res["documents"], "amount": amount}


EXECUTORS = {
    "alokasi_titipan": act_alokasi_titipan,
    "refund_titipan": act_refund_titipan,
    "alokasi_uang_muka": act_alokasi_uang_muka,
    "refund_pelanggan": act_refund_pelanggan,
    "refund_store_credit": act_refund_store_credit,
    "pindah_buku": act_pindah_buku,
    "akui_dipegang_karyawan": act_akui_dipegang_karyawan,
    "setor_dari_karyawan": act_setor_dari_karyawan,
    "realokasi_pesanan": act_realokasi_pesanan,
    "bebankan_biaya_bank": act_bank_charge,
    "batalkan_kwitansi": act_batalkan_kwitansi,
    "settlement_antar_entitas": act_settlement_antar_entitas,
    "uang_muka_supplier": act_uang_muka_supplier,
    "terima_refund_supplier": act_terima_refund_supplier,
}

#: PK-25 — pemeriksa per aksi (tanpa tulisan); kunci sama dengan `EXECUTORS`.
PRECHECKS = {
    "alokasi_titipan": _cek_alokasi_titipan,
    "refund_titipan": _cek_refund_titipan,
    "alokasi_uang_muka": _cek_alokasi_uang_muka,
    "refund_pelanggan": _cek_refund_pelanggan,
    "refund_store_credit": _cek_refund_store_credit,
    "pindah_buku": _cek_pindah_buku,
    "akui_dipegang_karyawan": _cek_akui_dipegang_karyawan,
    "setor_dari_karyawan": _cek_setor_dari_karyawan,
    "realokasi_pesanan": _cek_realokasi_pesanan,
    "bebankan_biaya_bank": _cek_bank_charge,
    "batalkan_kwitansi": _cek_batalkan_kwitansi,
    "settlement_antar_entitas": _cek_settlement_antar_entitas,
    "uang_muka_supplier": _cek_uang_muka_supplier,
    "terima_refund_supplier": _cek_terima_refund_supplier,
}


async def execute(action: str, case: Dict[str, Any], payload: Dict[str, Any],
                  actor: Dict[str, Any], *, op_id: str = "") -> Dict[str, Any]:
    """Jalankan pelaksana aksi. `op_id` = id niat penyelesaian (bawaan `op_id_of(case, action)`): id kas, baris
    pelunasan, penanda efek, dan nomor kunci jurnal diturunkan darinya, jadi pemanggilan ulang dengan `op_id` sama
    mengadopsi yang sudah ada. Hasil: `documents`, `amount`, … + `gl` (hasil tiap jurnal: status/galat) + `efek`
    (nama efek yang tertulis pada pemanggilan ini). Galat dilempar dengan atribut `efek_tertulis` (bool)."""
    fn = EXECUTORS.get(action)
    if not fn:
        raise CaseActionError(f"Aksi '{action}' belum punya pelaksana")
    op = op_id or op_id_of(case, action)
    efek: List[str] = []
    gl_hasil: List[Dict[str, Any]] = []
    tokens = [(_CASE_ID, _CASE_ID.set(case["id"])), (_CASE_OP, _CASE_OP.set(op)),
              (_CASE_N, _CASE_N.set(op.rsplit("_", 1)[-1])), (_CASE_OP_SEQ, _CASE_OP_SEQ.set(0)),
              (_CASE_PAY_SEQ, _CASE_PAY_SEQ.set(0)), (_CASE_EFEK, _CASE_EFEK.set(efek)),
              (_CASE_GL, _CASE_GL.set(gl_hasil))]
    try:
        res = await fn(case, payload, actor)
    except HTTPException as e:                      # pesan service lain tetap tampil apa adanya
        # PK-25 — kode 409 (balapan alokasi, deposit baru terpakai, kas ditolak) tetap 409; selain itu 400 seperti dulu.
        err = CaseConflict(str(e.detail)) if int(getattr(e, "status_code", 400) or 400) == 409 \
            else CaseActionError(str(e.detail))
        err.efek_tertulis = bool(efek)
        raise err from e
    except Exception as e:  # noqa: BLE001 — galat apa pun diteruskan, ditandai apakah efek sudah tertulis
        e.efek_tertulis = bool(efek)
        raise
    finally:
        for var, tok in reversed(tokens):
            var.reset(tok)
    return {**res, "gl": gl_hasil, "efek": efek}
