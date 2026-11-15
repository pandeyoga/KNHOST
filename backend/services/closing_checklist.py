"""PK-43 (UX-16) — DAFTAR PERIKSA SEBELUM TUTUP BUKU: angka diambil dari sistem, satu PT, satu periode.

`GET /api/finance/closing/checklist` (router `closing.py`) memanggil `build(...)`. Tiap butir = satu fungsi di `CHECKS`
(berurutan; unit lain MENAMBAH butir dengan dekorator `@butir(...)` tanpa mengubah endpoint). Satu butir gagal dihitung
tidak menggagalkan butir lain: galat atau lewat batas waktu → `status="unknown"`, `detail` berisi sebabnya.

Bentuk butir: `{key, label, status, value, detail, link}`; `status` ∈ `ok` · `warning` · `blocking` · `unknown`;
`link` = `{view, preset}` (layar tujuan + preset `useViewPreset`) atau `None`. `can_close` = tidak ada butir `blocking`.
Hanya tiga butir yang menghalangi (periode berakhir, tidak bentrok, suspense nol) — ketiganya sudah aturan server
`close_period` (PK-11, K-15). Butir lain memperingatkan saja; aturan tutup buku di server tidak diubah.

Sumber angka tiap butir memakai fungsi pemilik angkanya (`02` D1): `closing_service` (batas periode, bentrok, hari ini
WIB), `gl_service` (suspense, neraca saldo, rekonsiliasi persediaan, saldo akun per tanggal), `posting_registry`
(jenis dokumen gagal posting), `interco_service` (rumus sisa & refund), `period_unlock_service`, `fixed_asset_service`.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from core_utils import from_cents, rupiah, to_cents
from db import db
from services import closing_service as cs
from services import gl_service as gl

#: Batas waktu teknis per butir (detik) — bukan aturan bisnis: hitungan berat (neraca saldo, rekonsiliasi persediaan)
#: yang melewatinya jatuh ke `unknown` supaya butir lain tetap tampil.
BATAS_DETIK = 20.0

#: Field tanggal dokumen gagal posting (urutan pencarian; jenis dokumen di registri memakai nama berbeda).
FIELD_TANGGAL = ("tanggal_buku", "txn_date", "receipt_date", "bill_date", "settle_date", "return_date", "doc_date",
                 "date", "acquisition_date", "period", "created_at")


@dataclass
class Konteks:
    entity_id: str
    period_type: str
    period_key: str
    start: str
    end: str
    today: str


Fungsi = Callable[[Konteks], Awaitable[Dict[str, Any]]]
#: Daftar butir berurutan: (key, label, link, hanya_bulanan, fungsi).
CHECKS: List[tuple] = []


def butir(key: str, label: str, link: Optional[Dict[str, Any]] = None, *, hanya_bulanan: bool = False):
    """Daftarkan satu butir daftar periksa (urutan = urutan pendaftaran)."""
    def _daftar(fn: Fungsi) -> Fungsi:
        CHECKS.append((key, label, link, hanya_bulanan, fn))
        return fn
    return _daftar


def _hasil(status: str, value: Any = None, detail: str = "") -> Dict[str, Any]:
    return {"status": status, "value": value, "detail": detail}


def _tgl(iso: str) -> str:
    from services.book_date import tanggal_panjang
    try:
        return tanggal_panjang(iso)
    except Exception:  # noqa: BLE001 — teks pesan saja
        return iso


def _pick(doc: Dict[str, Any], dotted: str) -> Any:
    cur: Any = doc
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


# ── 1–3: butir yang menghalangi (aturan server yang sudah ada) ─────────────────────────────────────────────────────
@butir("periode_berakhir", "Periode sudah berakhir")
async def _periode_berakhir(k: Konteks) -> Dict[str, Any]:
    if k.end < k.today:
        return _hasil("ok", None, f"Periode berakhir {_tgl(k.end)}.")
    return _hasil("blocking", None, cs._not_ended_message(k.period_type, k.period_key, k.end))


@butir("tidak_bentrok", "Tidak bentrok dengan penutupan lain")
async def _tidak_bentrok(k: Konteks) -> Dict[str, Any]:
    rec = await cs._blocking_closing(k.entity_id, k.period_type, k.start, k.end)
    if not rec:
        return _hasil("ok", None, "Tidak ada penutupan aktif yang tumpang tindih.")
    label = rec.get("period_label") or rec.get("period_key") or ""
    return _hasil("blocking", label, f"Bentrok dengan penutupan {label} yang masih aktif. Buka kembali dulu "
                                     "untuk menutup ulang.")


# MN-T2 — dua butir membuka seksinya di layar Tutup Buku (dulu tab Suspense / Rekonsiliasi di Jurnal & Buku Besar).
@butir("suspense_nol", "Saldo akun penampung nol", {"view": "closing", "preset": {"seksi": "akun-sementara"}})
async def _suspense_nol(k: Konteks) -> Dict[str, Any]:
    saldo = await gl.suspense_balance(k.entity_id, k.end)
    if abs(saldo) <= cs.EPS:
        return _hasil("ok", 0.0, f"Saldo akun penampung (Suspense) per {_tgl(k.end)} Rp 0.")
    return _hasil("blocking", saldo, f"Saldo akun penampung (Suspense) per {_tgl(k.end)} {rupiah(saldo)} — "
                                     "reklasifikasi dulu di seksi Akun sementara (Tutup Buku).")


# ── 4–11: butir peringatan ─────────────────────────────────────────────────────────────────────────────────────────
@butir("posting_gagal", "Tidak ada jurnal yang gagal diposting", {"view": "posting-failures", "preset": None})
async def _posting_gagal(k: Konteks) -> Dict[str, Any]:
    from services import posting_registry as reg
    per_jenis: Dict[str, int] = {}
    for kind, spec in reg.KINDS.items():
        q = {**spec["failed_query"], spec["entity_field"]: k.entity_id}
        proj = {"_id": 0, **{f: 1 for f in FIELD_TANGGAL}}
        if spec.get("per_step"):
            proj[spec.get("items_field") or "steps"] = 1
        n = 0
        async for d in db[spec["collection"]].find(q, proj):
            tgl = next((str(v) for v in (_pick(d, f) for f in FIELD_TANGGAL) if v), "")
            if tgl and tgl[:10] > k.end:
                continue   # dokumen sesudah periode ini
            if spec.get("per_step"):
                n += sum(1 for st in d.get(spec.get("items_field") or "steps") or [] if st.get("gl_status") == "failed")
            else:
                n += 1
        if n:
            per_jenis[spec["label"]] = n
    total = sum(per_jenis.values())
    if not total:
        return _hasil("ok", 0, f"Tidak ada dokumen bertanggal sampai {_tgl(k.end)} yang jurnalnya gagal.")
    rinci = ", ".join(f"{lbl} {n}" for lbl, n in per_jenis.items())
    return _hasil("warning", total, f"{total} dokumen bertanggal sampai {_tgl(k.end)} jurnalnya gagal ({rinci}). "
                                    "Ulangi di Posting Gagal.")


@butir("neraca_saldo", "Neraca saldo seimbang", {"view": "general-ledger", "preset": {"tab": "trial"}})
async def _neraca_saldo(k: Konteks) -> Dict[str, Any]:
    tb = await gl.trial_balance(as_of=k.end, scope={"entity_id": k.entity_id})
    selisih = round(float(tb.get("total_debit") or 0) - float(tb.get("total_credit") or 0), 2)
    if tb.get("balanced"):
        return _hasil("ok", selisih, f"Debit = kredit per {_tgl(k.end)} ({rupiah(tb.get('total_debit') or 0)}).")
    return _hasil("warning", selisih, f"Debit − kredit per {_tgl(k.end)} berselisih {rupiah(selisih)}.")


@butir("stok_cocok", "Nilai stok sama dengan akun persediaan", {"view": "closing", "preset": {"seksi": "persediaan"}})
async def _stok_cocok(k: Konteks) -> Dict[str, Any]:
    rec = await gl.inventory_reconciliation([k.entity_id])
    row = next((r for r in rec.get("rows") or [] if r.get("entity_id") == k.entity_id), None)
    if row is None:
        return _hasil("unknown", None, "PT ini tidak ditemukan di rekonsiliasi persediaan.")
    teks = (f"Nilai stok {rupiah(row['subledger_value'])} · akun persediaan {rupiah(row['gl_balance'])} · selisih "
            f"{rupiah(row['difference'])} (keadaan hari ini).")
    return _hasil("ok" if row.get("reconciled") else "warning", row.get("difference"), teks)


@butir("bank_cocok", "Mutasi bank sampai akhir periode sudah dicocokkan", {"view": "bank-reconciliation", "preset": None})
async def _bank_cocok(k: Konteks) -> Dict[str, Any]:
    n = await db.bank_statement_lines.count_documents({"entity_id": k.entity_id, "status": "unmatched",
                                                       "stmt_date": {"$lte": gl._gl_day_end(k.end)}})
    if not n:
        return _hasil("ok", 0, f"Tidak ada mutasi bank sampai {_tgl(k.end)} yang belum dicocokkan.")
    return _hasil("warning", n, f"{n} mutasi bank sampai {_tgl(k.end)} belum dicocokkan.")


async def _sisa_dokumen_antar_pt(entity_id: str) -> Dict[str, int]:
    """Σ sisa dokumen antar-PT TERBUKA (keadaan hari ini, sen) — rumus `interco_service`: dagang (sisa − refund yang
    belum dibayar), pinjaman (`outstanding`), pindah aset belum dibayar (`transfer.price`). Sisi piutang = PT ini
    penjual / pemberi pinjaman / pengirim aset; sisi utang = pembeli / peminjam / penerima aset."""
    from services import interco_service as ics
    out = {"piutang": 0, "utang": 0}
    for sisi, fld in (("piutang", "seller_entity_id"), ("utang", "buyer_entity_id")):
        async for d in db.interco_transactions.find({"role": "seller", fld: entity_id,
                                                     "status": {"$nin": ["draft", "cancelled"]}}, {"_id": 0}):
            if d.get("status") in ics.OPEN_STATUSES:
                sisa = (float(d.get("grand_total") or 0) - float(d.get("settled_amount") or 0)
                        - float(d.get("returned_amount") or 0))
                out[sisi] += to_cents(sisa)
            out[sisi] -= to_cents(ics.refund_left_of(d))   # retur sesudah lunas: penjual berutang kembali (PK-31)
    for sisi, fld in (("piutang", "lender_entity_id"), ("utang", "borrower_entity_id")):
        async for r in db.interco_loans.find({"role": "lender", fld: entity_id,
                                              "status": {"$in": ["disbursed", "partially_repaid"]}},
                                             {"_id": 0, "outstanding": 1}):
            out[sisi] += to_cents(float(r.get("outstanding") or 0))
    for sisi, fld in (("piutang", "transfer.from_entity_id"), ("utang", "transfer.to_entity_id")):
        async for a in db.fin_fixed_assets.find({fld: entity_id, "transfer.settled": False}, {"_id": 0, "transfer": 1}):
            out[sisi] += to_cents(float((a.get("transfer") or {}).get("price") or 0))
    return out


@butir("antar_pt_cocok", "Saldo antar-PT di buku besar sama dengan dokumennya",
       {"view": "interco-transactions", "preset": {"tab": "balances"}})
async def _antar_pt_cocok(k: Konteks) -> Dict[str, Any]:
    from services import gl_mapping_service as glm
    from services.nilai_pengaturan import nilai
    tol = to_cents(float(await nilai("finance.rounding_tolerance_rupiah", k.entity_id)))   # KF-T7 — ambang sen
    gl_ar = await gl.accounts_balance_cents(await glm.known_codes("antar_pt.piutang_ic", k.entity_id), k.entity_id,
                                            as_of=k.end)
    gl_ap = -await gl.accounts_balance_cents(await glm.known_codes("antar_pt.utang_ic", k.entity_id), k.entity_id,
                                             as_of=k.end)
    dok = await _sisa_dokumen_antar_pt(k.entity_id)
    s_ar, s_ap = gl_ar - dok["piutang"], gl_ap - dok["utang"]
    value = {"gl_receivable": from_cents(gl_ar), "doc_receivable": from_cents(dok["piutang"]),
             "gl_payable": from_cents(gl_ap), "doc_payable": from_cents(dok["utang"])}
    detail = (f"Piutang: buku {rupiah(from_cents(gl_ar))} · dokumen {rupiah(from_cents(dok['piutang']))} · selisih "
              f"{rupiah(from_cents(s_ar))} — Utang: buku {rupiah(from_cents(gl_ap))} · dokumen "
              f"{rupiah(from_cents(dok['utang']))} · selisih {rupiah(from_cents(s_ap))}. Buku per {_tgl(k.end)}, "
              "dokumen keadaan hari ini.")
    return _hasil("ok" if abs(s_ar) <= tol and abs(s_ap) <= tol else "warning", value, detail)


@butir("buka_periode_aktif", "Tidak ada izin Buka Periode yang masih berlaku", {"view": "period-unlock", "preset": None})
async def _buka_periode_aktif(k: Konteks) -> Dict[str, Any]:
    from services import period_unlock_service as pus
    aktif = await pus.active_unlocks([k.entity_id])
    if not aktif:
        return _hasil("ok", 0, "Tidak ada izin Buka Periode yang masih berlaku.")
    rinci = ", ".join(r.get("period_label") or r.get("period_key") or "" for r in aktif)
    return _hasil("warning", len(aktif), f"{len(aktif)} izin Buka Periode masih berlaku ({rinci}).")


@butir("penyusutan", "Penyusutan aset periode ini sudah dijalankan", {"view": "fixed-assets", "preset": None},
       hanya_bulanan=True)
async def _penyusutan(k: Konteks) -> Dict[str, Any]:
    from services import fixed_asset_service as fas
    period = k.period_key[:7]
    belum = 0
    async for a in db.fin_fixed_assets.find({"entity_id": k.entity_id, "status": "active"}, {"_id": 0}):
        if fas._period_of(a.get("acquisition_date", "")) > period:
            continue   # belum mulai disusutkan
        sisa = (max(round(float(a.get("acquisition_cost") or 0) - float(a.get("salvage_value") or 0), 2), 0.0)
                - float(a.get("accumulated_depreciation") or 0))
        if sisa <= cs.EPS or int(a.get("depreciated_months") or 0) >= int(a.get("useful_life_months") or 0):
            continue   # sudah habis disusutkan
        if not await db.fin_depreciation_entries.find_one({"asset_id": a["id"], "period": period}, {"_id": 1}):
            belum += 1
    if not belum:
        return _hasil("ok", 0, "Semua aset aktif sudah disusutkan untuk periode ini (atau tidak ada yang perlu).")
    return _hasil("warning", belum, f"{belum} aset belum disusutkan untuk {cs._period_label('month', period)}.")


@butir("gaji", "Penggajian periode ini sudah diposting", {"view": "hr-payroll-runs", "preset": None},
       hanya_bulanan=True)
async def _gaji(k: Konteks) -> Dict[str, Any]:
    from services import hr_payroll_service as hps
    runs = [r async for r in db.hr_payroll_runs.find(
        {"entity_id": k.entity_id, "period": k.period_key[:7], "status": {"$nin": list(hps.DEAD_STATUSES)}},
        {"_id": 0, "number": 1, "status": 1})]
    if not runs:
        return _hasil("ok", 0, "Tidak ada penggajian periode ini")
    belum = [r for r in runs if r.get("status") not in ("posted", "paying", "paid")]
    if not belum:
        return _hasil("ok", len(runs), "Penggajian periode ini sudah diposting.")
    rinci = ", ".join(f"{r.get('number') or '—'} ({hps.RUN_STATUS_LABEL.get(r.get('status'), r.get('status'))})"
                      for r in belum)
    return _hasil("warning", len(belum), f"Penggajian belum diposting: {rinci}.")


# ── Penyusun ───────────────────────────────────────────────────────────────────────────────────────────────────────
async def _jalankan(fn: Fungsi, k: Konteks) -> Dict[str, Any]:
    try:
        return await asyncio.wait_for(fn(k), timeout=BATAS_DETIK)
    except asyncio.TimeoutError:
        return _hasil("unknown", None, f"Tidak terbaca: hitungan melewati batas waktu {int(BATAS_DETIK)} detik.")
    except Exception as exc:  # noqa: BLE001 — satu butir gagal tidak menggagalkan butir lain
        return _hasil("unknown", None, f"Tidak terbaca: {exc}")


async def build(period_type: str, period_key: str, entity_id: str) -> Dict[str, Any]:
    start, end = await cs.period_bounds(period_type, period_key, entity_id)
    k = Konteks(entity_id=entity_id, period_type=period_type, period_key=period_key, start=start, end=end,
                today=cs._today_wib())
    items: List[Dict[str, Any]] = []
    for key, label, link, hanya_bulanan, fn in CHECKS:
        if hanya_bulanan and period_type != "month":
            continue
        items.append({"key": key, "label": label, **await _jalankan(fn, k), "link": link})
    return {"period_type": period_type, "period_key": period_key,
            "period_label": cs._period_label(period_type, period_key), "start_date": start, "end_date": end,
            "entity_id": entity_id, "can_close": not any(it["status"] == "blocking" for it in items),
            "items": items}
