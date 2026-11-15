"""PY-T4 (PY-11; keputusan K-41, K-34) — bayar gaji dari rekening berperuntukan Gaji, dengan daftar transfer per karyawan.

* `pay_accounts(entity_id)` — rekening AKTIF milik PT yang peruntukannya (`purposes`, PM-T1; rekening lama tanpa field =
  keempat peruntukan) memuat `gaji`. Tanpa saldo.
* `pay_queue(scope, …)` — proses berstatus `posted` (berhalaman, tanpa rincian slip).
* `transfer_list(run)` — daftar transfer TIDAK disimpan: selalu diturunkan dari slip proses itu (`02` D1), jadi tidak bisa
  berbeda dari slip. Jumlahnya wajib = `totals.net` proses (penjaga, 409 — bukan keadaan normal).
* `transfer_xlsx(run)` — berkas `.xlsx` daftar transfer (kepala: PT, nomor, periode, rekening sumber, tanggal bayar).
* `pay_run(run_id, actor, account_id, paid_date)` — `02_STANDAR.md` §1:

    PERIKSA  status `posted` · tidak ada slip ber-gaji bersih negatif · daftar transfer = total bersih · rekening (aktif,
             milik PT proses, berperuntukan Gaji; kosong → satu-satunya rekening gaji PT) · tanggal bayar (bawaan hari
             ini WIB; tidak sebelum tanggal jurnal gaji) · `preflight_posting(PT, tanggal bayar)` · kontrol dua orang
             `kontrol.proses_gaji` (K-41, bawaan satu orang)          → gagal = tanpa tulisan apa pun
    NIAT     `posted → paying` bersyarat + `pay_account_id`, `paid_date`, `paid_by_id` (dua bayar bersamaan: satu menang)
    EFEK+JURNAL  satu kas keluar `cash_ledger.create_cash(ref_type="payroll_run", ref_id=id proses, …)` (PK-20) berlawan
             akun pemetaan `sdm.hutang_gaji` → jurnal kas tahan-gagal Dr hutang gaji / Cr kas rekening itu, bertanggal
             bayar. Kode akun dari isi permintaan (`cash_account`) tidak dibaca lagi.
    SELESAI  `paid` + `transfer_total`, `transfer_count`, `cash_txn_id`, `paid_journal_id`
    GAGAL    kas ditolak → kembali `posted`, niat dihapus; jurnal kas gagal → kembali `posted`, `pay_gl_status="failed"`,
             kas tersimpan (panel Posting Gagal, jenis Transaksi Kas)
    ULANG    Bayar lagi / ulang dari panel memakai kas (id tetap dari id proses) dan jurnal yang sama →
             `selesaikan_dari_kas` (dipanggil `posting_registry._retry_cash`)

Proses yang jurnal bayarnya terbit lewat jalur lama (`payroll_pay`, sebelum unit ini) tetapi kasnya gagal: kas baru
menumpang jurnal lama itu (`journal_by_parent`), tidak dijurnal dua kali.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Dict, List, Optional, Tuple

from core_utils import now_iso, rupiah, safe_doc
from db import db
from services.hr_payroll_service import PayrollConflict, _kontrol_dua_orang, _status_conflict

PERUNTUKAN_GAJI = "gaji"
PESAN_BUKAN_GAJI = ("Rekening {nama} tidak ditandai untuk pembayaran gaji. Pilih rekening lain, atau tambahkan "
                    "peruntukan Gaji di Rekening & Saldo.")
PESAN_PILIH = "Pilih rekening pembayaran gaji."
PESAN_TANPA_REKENING = ("Belum ada rekening berperuntukan Gaji di PT ini. Atur di Keuangan › Kas & Bank › "
                        "Rekening & Saldo.")
PESAN_PT_LAIN = "Rekening ini bukan rekening aktif PT penggajian."
PESAN_SUDAH = "Penggajian {nomor} sedang atau sudah dibayar. Muat ulang."
PESAN_BELUM_POSTING = "Daftar transfer tersedia setelah penggajian diposting."
PESAN_TIDAK_SAMA = ("Jumlah daftar transfer tidak sama dengan total gaji bersih. Hitung ulang tidak mungkin setelah "
                    "posting; hubungi Admin.")
PESAN_TANGGAL = "Tanggal bayar tidak dikenali (TTTT-BB-HH)."
_TGL = re.compile(r"^\d{4}-\d{2}-\d{2}$")
#: Field yang dikirim kembali oleh endpoint bayar — tanpa slip (pemegang `payroll.pay` tanpa `hr.view` tidak melihat
#: rincian slip, K-41).
FIELD_BAYAR = ("id", "number", "entity_id", "period", "run_type", "status", "journal_date", "journal_number",
               "pay_account_id", "pay_account_name", "paid_date", "paid_at", "paid_by", "paid_by_id", "transfer_total",
               "transfer_count", "cash_txn_id", "cash_txn_number", "paid_journal_id", "paid_journal_number",
               "pay_gl_status", "pay_gl_error")


def _r(v: Any) -> float:
    return round(float(v or 0), 2)


def _sen(v: Any) -> int:
    """Perbandingan uang dalam satuan bulat (`02` D5)."""
    return int(round(float(v or 0) * 100))


def bentuk_bayar(run: Dict[str, Any]) -> Dict[str, Any]:
    """Jawaban endpoint bayar: dokumen proses tanpa slip + `totals` ringkas (jumlah karyawan, gaji bersih)."""
    t = run.get("totals") or {}
    out = {k: run.get(k) for k in FIELD_BAYAR if k in run}
    out["totals"] = {"employees": int(t.get("employees") or 0), "net": _r(t.get("net"))}
    return safe_doc(out)


# ── Rekening pembayaran gaji ────────────────────────────────────────────────────────────────────────────────────────
def _ringkas_rekening(acc: Dict[str, Any]) -> Dict[str, Any]:
    from services import bank_service as bs
    eff = acc.get("_efektif") or bs.bidang_efektif(acc)
    return {"id": acc["id"], "name": acc.get("name", ""), "bank_name": acc.get("bank_name", ""),
            "account_number": acc.get("account_number", ""), "holder_name": eff.get("holder_name", ""),
            "cash_type": bs.account_cash_type(acc)}


async def pay_accounts(entity_id: str) -> List[Dict[str, Any]]:
    """`GET /api/hr/payroll/pay-accounts` — rekening aktif PT yang berperuntukan Gaji (tanpa saldo), urut nama."""
    from services import bank_service as bs
    out = [_ringkas_rekening(a) for a in await bs.rekening_pt(entity_id)
           if bs._aktif(a) and PERUNTUKAN_GAJI in a["_efektif"]["purposes"]]   # noqa: SLF001
    out.sort(key=lambda r: (r["name"].lower(), r["id"]))
    return out


async def pilih_rekening(entity_id: str, account_id: str = "") -> Dict[str, Any]:
    """Langkah PERIKSA rekening (tanpa tulisan). → ringkasan rekening (`_ringkas_rekening`). Galat → `ValueError` (400)."""
    from services import bank_service as bs
    gaji = await pay_accounts(entity_id)
    aid = (account_id or "").strip()
    if aid:
        acc = await db.bank_accounts.find_one({"id": aid}, {"_id": 0})
        if not acc or (acc.get("entity_id") or "") != entity_id or not bs._aktif(acc):   # noqa: SLF001
            raise ValueError(PESAN_PT_LAIN)
        pilih = next((a for a in gaji if a["id"] == aid), None)
        if not pilih:
            raise ValueError(PESAN_BUKAN_GAJI.format(nama=acc.get("name") or "ini"))
        return pilih
    if not gaji:
        raise ValueError(PESAN_TANPA_REKENING)
    if len(gaji) > 1:
        raise ValueError(PESAN_PILIH)
    return gaji[0]


# ── Antrean bayar ───────────────────────────────────────────────────────────────────────────────────────────────────
async def pay_queue(scope: Dict[str, Any], *, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """`GET /api/hr/payroll/pay-queue` — proses `posted` (periode terlama dulu), tanpa rincian slip. `entity_id` (PT
    proses) dan `journal_date` (batas awal tanggal bayar) ikut untuk pop-up Bayar."""
    q = {**(scope or {}), "status": "posted"}
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 50), 200))
    total = await db.hr_payroll_runs.count_documents(q)
    rows = await db.hr_payroll_runs.find(
        q, {"_id": 0, "id": 1, "number": 1, "period": 1, "run_type": 1, "totals": 1, "posted_at": 1, "entity_id": 1,
            "journal_date": 1}) \
        .sort([("period", 1), ("number", 1)]).skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    items = [{"id": r["id"], "number": r.get("number", ""), "period": r.get("period", ""),
              "run_type": r.get("run_type") or "regular", "employees": int((r.get("totals") or {}).get("employees") or 0),
              "net_total": _r((r.get("totals") or {}).get("net")), "posted_at": r.get("posted_at") or "",
              "entity_id": r.get("entity_id", ""), "journal_date": r.get("journal_date") or ""} for r in rows]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── Daftar transfer (diturunkan dari slip) ──────────────────────────────────────────────────────────────────────────
async def _baris_transfer(run_id: str) -> List[Dict[str, Any]]:
    slips = await db.hr_payslips.find(
        {"run_id": run_id}, {"_id": 0, "id": 1, "number": 1, "employee_id": 1, "employee_name": 1, "net": 1,
                             "bank": 1}).to_list(5000)
    slips.sort(key=lambda s: ((s.get("employee_name") or "").lower(), s.get("number") or ""))
    out = []
    for i, s in enumerate(slips, 1):
        bank = s.get("bank") or {}
        nomor = str(bank.get("acc_no") or "").strip()
        out.append({"no": i, "employee_id": s.get("employee_id", ""), "employee_name": s.get("employee_name", ""),
                    "slip_number": s.get("number", ""), "bank_name": str(bank.get("bank_name") or "").strip(),
                    "account_number": nomor, "account_holder": str(bank.get("acc_name") or "").strip(),
                    "amount": _r(s.get("net")), "cash": not nomor})
    return out


async def transfer_list(run: Dict[str, Any], items: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """`GET …/runs/{id}/transfer-list` — proses `posted`/`paid`; Σ nominal wajib = `totals.net` (selain itu 409).
    `items` = baris yang sudah dibaca pemanggil (langkah PERIKSA bayar), supaya slip tidak dibaca dua kali."""
    if run.get("status") not in ("posted", "paying", "paid"):
        raise PayrollConflict(PESAN_BELUM_POSTING)
    items = items if items is not None else await _baris_transfer(run["id"])
    total = _r(sum(it["amount"] for it in items))
    if _sen(total) != _sen((run.get("totals") or {}).get("net")):
        raise PayrollConflict(PESAN_TIDAK_SAMA)
    acc = None
    if run.get("pay_account_id"):
        doc = await db.bank_accounts.find_one({"id": run["pay_account_id"]}, {"_id": 0})
        acc = _ringkas_rekening(doc) if doc else {"id": run["pay_account_id"], "name": run.get("pay_account_name", ""),
                                                  "bank_name": "", "account_number": "", "holder_name": "",
                                                  "cash_type": ""}
    return {"run": {k: run.get(k) for k in ("id", "number", "period", "run_type", "status", "entity_id")},
            "pay_account": acc, "paid_date": run.get("paid_date") or "", "items": items, "count": len(items),
            "total": total, "without_account": sum(1 for it in items if it["cash"])}


async def _nama_pt(entity_id: str) -> str:
    e = await db.business_entities.find_one({"id": entity_id}, {"_id": 0, "legal_name": 1, "name": 1,
                                                                "short_name": 1}) or {}
    return e.get("legal_name") or e.get("name") or e.get("short_name") or entity_id


def _angka(v: float):
    return int(v) if float(v).is_integer() else v


async def transfer_xlsx(run: Dict[str, Any]) -> Tuple[bytes, str, Dict[str, Any]]:
    """Berkas `transfer-gaji-<nomor proses>.xlsx` → (isi, nama berkas, ringkasan untuk jejak audit tanpa nominal)."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font
    from services.periodic_posting import label_periode
    data = await transfer_list(run)
    pt = await _nama_pt(run.get("entity_id", ""))
    periode = label_periode(run["period"])
    berita = f"Gaji {periode} {pt}"
    acc = data["pay_account"]
    sumber = (" · ".join(x for x in (acc.get("name"), acc.get("bank_name"), acc.get("account_number")) if x)
              if acc else "Belum dipilih (gaji belum dibayar)")
    wb = Workbook()
    ws = wb.active
    ws.title = "Daftar transfer"
    for label, isi in (("PT", pt), ("Nomor proses", run.get("number", "")), ("Periode", periode),
                       ("Rekening sumber", sumber), ("Tanggal bayar", data["paid_date"] or "Belum dibayar")):
        ws.append([label, isi])
        ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])
    ws.append(["No.", "Nama penerima", "Bank", "Nomor rekening", "Nominal", "Berita"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for it in data["items"]:
        ws.append([it["no"], it["account_holder"] or it["employee_name"], it["bank_name"] or "Tunai",
                   it["account_number"] or "Tanpa rekening — bayar tunai", _angka(it["amount"]), berita])
        ws.cell(row=ws.max_row, column=5).number_format = "#,##0.00"
    ws.append([None, "Total", None, None, _angka(data["total"]), None])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    ws.cell(row=ws.max_row, column=5).number_format = "#,##0.00"
    for col, lebar in zip("ABCDEF", (8, 30, 14, 26, 18, 44)):
        ws.column_dimensions[col].width = lebar
    buf = io.BytesIO()
    wb.save(buf)
    nama = f"transfer-gaji-{re.sub(r'[^A-Za-z0-9._-]+', '-', run.get('number') or run['id'])}.xlsx"
    return buf.getvalue(), nama, {"number": run.get("number", ""), "period": run.get("period", ""),
                                  "count": data["count"], "without_account": data["without_account"]}


# ── Bayar ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _tanggal_jurnal_gaji(run: Dict[str, Any]) -> str:
    """Tanggal jurnal gaji proses: `journal_date` (PK-22) → tanggal jurnal gajinya → akhir periode (data lama)."""
    from services import gl_service as gl, periodic_posting
    if run.get("journal_date"):
        return str(run["journal_date"])[:10]
    je = await db.journal_entries.find_one({"id": run.get("journal_id") or "__none__"}, {"_id": 0, "date": 1}) or \
        await db.journal_entries.find_one({"source_type": "payroll_run", "source_id": await gl.payroll_source_id(run),
                                           "status": {"$ne": "void"}}, {"_id": 0, "date": 1}) or {}
    return (je.get("date") or "")[:10] or periodic_posting.akhir_periode(run["period"])


def _tanggal_bayar(paid_date: str) -> str:
    from services.book_date import tanggal_buku
    raw = (paid_date or "").strip()
    if not raw:
        return tanggal_buku()
    if not _TGL.match(raw):
        raise ValueError(PESAN_TANGGAL)
    try:
        _dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(PESAN_TANGGAL) from exc
    return raw


async def _kas_bayar(run: Dict[str, Any], acc: Dict[str, Any], tanggal: str, aktor: str) -> Dict[str, Any]:
    """EFEK + JURNAL: satu kas keluar ber-id tetap dari id proses (kirim ulang = kas yang sama)."""
    from services import cash_ledger, gl_service as gl
    from services.periodic_posting import label_periode
    eid = run["entity_id"]
    kw: Dict[str, Any] = dict(
        entity_id=eid, direction="out", amount=_r((run.get("totals") or {}).get("net")), ref_type="payroll_run",
        ref_id=run["id"], account_id=acc["id"], txn_date=tanggal, category="Pembayaran Gaji",
        description=f"Pembayaran gaji {label_periode(run['period'])} ({run.get('number', '')})", actor=aktor,
        extra={"payroll_period": run.get("period", "")})
    lama = await db.journal_entries.find_one(
        {"source_type": "payroll_pay", "source_id": await gl.payroll_source_id(run), "status": {"$ne": "void"}},
        {"_id": 0, "id": 1, "lines": 1})
    if lama:   # jurnal bayar jalur lama sudah terbit: kas menumpang jurnal itu (jenis kas = akun kas jurnal itu)
        kredit = next((ln.get("account_code") for ln in lama.get("lines") or [] if float(ln.get("credit") or 0) > 0),
                      gl.ACC_KAS_BESAR)
        kw.update(journal_by_parent=lama["id"], cash_type=cash_ledger.cash_type_for(kredit))
    else:
        kw["contra_account_code"] = await gl.account_for("sdm.hutang_gaji", eid)
    return await cash_ledger.create_cash(**kw)


async def _jurnal_bayar(txn: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not txn:
        return None
    je = await db.journal_entries.find_one({"source_type": "cash_transaction", "source_id": txn["id"],
                                            "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "number": 1})
    if not je and txn.get("parent_journal"):
        je = await db.journal_entries.find_one({"id": txn["parent_journal"]}, {"_id": 0, "id": 1, "number": 1})
    return je


async def _selesai(run_id: str, txn: Optional[Dict[str, Any]], count: int, total: float) -> Dict[str, Any]:
    """SELESAI: `paying → paid` (+ slip `paid`) dengan angka dari kas yang benar-benar tercatat."""
    je = await _jurnal_bayar(txn) if txn else None
    patch: Dict[str, Any] = {"status": "paid", "paid_at": now_iso(), "transfer_total": _r(total),
                             "transfer_count": int(count), "pay_gl_status": "posted" if je else "not_required",
                             "pay_gl_error": "", "updated_at": now_iso()}
    if txn:
        acc = await db.bank_accounts.find_one({"id": txn.get("account_id") or "__none__"}, {"_id": 0, "name": 1}) or {}
        patch.update({"cash_txn_id": txn["id"], "cash_txn_number": txn.get("number", ""),
                      "transfer_total": _r(txn.get("amount")), "pay_account_id": txn.get("account_id", ""),
                      "pay_account_name": acc.get("name", ""), "paid_date": str(txn.get("txn_date") or "")[:10]})
    if je:
        patch.update({"paid_journal_id": je["id"], "paid_journal_number": je.get("number", "")})
    await db.hr_payroll_runs.update_one({"id": run_id, "status": "paying"}, {"$set": patch})
    await db.hr_payslips.update_many({"run_id": run_id}, {"$set": {"status": "paid", "updated_at": now_iso()}})
    return bentuk_bayar(await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0}) or {})


async def pay_run(run_id: str, actor: Dict[str, Any], account_id: str = "", paid_date: str = "") -> Dict[str, Any]:
    """`POST /api/hr/payroll/runs/{id}/pay` — lihat docstring modul. Galat: `ValueError` 400, `PayrollConflict` 409,
    `ClosedPeriodError` 409, `cash_ledger.CashRejected` (HTTP) apa adanya."""
    from services import cash_ledger, gl_service as gl
    run = await db.hr_payroll_runs.find_one({"id": run_id}, {"_id": 0})
    if not run:
        raise ValueError("Payroll run tidak ditemukan.")
    # ── 1. PERIKSA (tanpa tulisan) ───────────────────────────────────────────────────────────────────────────────────
    if run.get("status") in ("paying", "paid"):
        raise PayrollConflict(PESAN_SUDAH.format(nomor=run.get("number") or run_id))
    if run.get("status") != "posted":
        raise _status_conflict(run, "dibayar")
    eid = run.get("entity_id", "")
    items = await _baris_transfer(run_id)
    minus = next((it for it in items if it["amount"] < 0), None)
    if minus:
        raise PayrollConflict(f"Gaji bersih {minus['employee_name']} negatif ({rupiah(minus['amount'])}). Perbaiki "
                              "potongannya lewat proses baru sebelum membayar.")
    data = await transfer_list(run, items)   # penjaga Σ daftar transfer = total gaji bersih
    net = _r((run.get("totals") or {}).get("net"))
    acc = await pilih_rekening(eid, account_id) if net > 0.005 else None
    tanggal = _tanggal_bayar(paid_date)
    batas = await _tanggal_jurnal_gaji(run)
    if tanggal < batas:
        raise ValueError(f"Tanggal bayar tidak boleh sebelum {batas}.")
    await gl.preflight_posting(eid, tanggal)
    await _kontrol_dua_orang(run, actor)
    # ── 2. NIAT ──────────────────────────────────────────────────────────────────────────────────────────────────────
    niat = {"pay_account_id": (acc or {}).get("id", ""), "pay_account_name": (acc or {}).get("name", ""),
            "paid_date": tanggal, "paid_by": actor.get("name", "system"), "paid_by_id": actor.get("id", ""),
            "pay_gl_status": "pending", "pay_gl_error": ""}
    res = await db.hr_payroll_runs.update_one({"id": run_id, "status": "posted"},
                                              {"$set": {"status": "paying", **niat, "updated_at": now_iso()}})
    if not res.matched_count:
        raise PayrollConflict(PESAN_SUDAH.format(nomor=run.get("number") or run_id))
    if not acc:   # gaji bersih nol: tidak ada uang yang keluar
        return await _selesai(run_id, None, data["count"], 0)
    # ── 3. EFEK + JURNAL ─────────────────────────────────────────────────────────────────────────────────────────────
    try:
        txn = await _kas_bayar(run, acc, tanggal, niat["paid_by"])
    except cash_ledger.CashPostingError as exc:
        await db.hr_payroll_runs.update_one({"id": run_id, "status": "paying"}, {"$set": {
            "status": "posted", "pay_gl_status": "failed", "pay_gl_error": str(exc.error)[:300],
            "pay_gl_failed_at": now_iso(), "cash_txn_id": exc.txn.get("id", ""),
            "cash_txn_number": exc.txn.get("number", ""), "updated_at": now_iso()}})
        raise PayrollConflict(f"Jurnal pembayaran gaji gagal: {exc.error}. Kas {exc.txn.get('number', '')} sudah "
                              "tersimpan — ulangi Bayar, atau ulang jurnalnya dari Posting Gagal.") from exc
    except Exception:
        await db.hr_payroll_runs.update_one(
            {"id": run_id, "status": "paying"},
            {"$set": {"status": "posted", "updated_at": now_iso()},
             "$unset": {k: "" for k in ("pay_account_id", "pay_account_name", "paid_date", "paid_by", "paid_by_id",
                                        "pay_gl_status", "pay_gl_error")}})
        raise
    # ── 4. SELESAI ───────────────────────────────────────────────────────────────────────────────────────────────────
    return await _selesai(run_id, txn, data["count"], data["total"])


async def selesaikan_dari_kas(txn: Dict[str, Any]) -> None:
    """ULANG dari panel Posting Gagal (jenis Transaksi Kas): jurnal kas bayar gaji kini terbit → proses yang tertahan
    `posted` dengan kas itu diselesaikan menjadi `paid`. Proses lain / kas lain → tidak ada perubahan."""
    run = await db.hr_payroll_runs.find_one({"id": txn.get("ref_id") or "__none__"}, {"_id": 0})
    if not run or run.get("status") != "posted" or (run.get("cash_txn_id") or "") != txn.get("id"):
        return
    fresh = await db.cash_transactions.find_one({"id": txn["id"]}, {"_id": 0}) or txn
    if fresh.get("status") == "void" or not await _jurnal_bayar(fresh):
        return
    items = await _baris_transfer(run["id"])
    res = await db.hr_payroll_runs.update_one({"id": run["id"], "status": "posted", "cash_txn_id": txn["id"]},
                                              {"$set": {"status": "paying", "updated_at": now_iso()}})
    if res.matched_count:
        await _selesai(run["id"], fresh, len(items), _r(fresh.get("amount")))


async def kas_bayar_hidup(run_id: str) -> Optional[Dict[str, Any]]:
    """Kas keluar pembayaran gaji proses ini yang belum dibatalkan (penghalang anulir proses)."""
    return await db.cash_transactions.find_one({"ref_type": "payroll_run", "ref_id": run_id, "direction": "out",
                                                "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "number": 1})
