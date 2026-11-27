"""F1 — kwitansi otomatis dari mutasi bank: fondasi (konstanta, waktu aktif, pembaca pengaturan) dan penilai baris.

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.1–§5.4, §5.7. Pelaksana ditambahkan
di tugas berikutnya pada modul ini; uang tetap lewat `ar_receipt_service.create_receipt` (satu pintu kas).

PENILAI (`nilai_baris`, tanpa tulisan apa pun)
==============================================
Satu baris mutasi → keputusan `A` (tautkan kwitansi yang sudah ada), `B` (terima laporan bayar menunggu), `C` (kwitansi
baru), `kartu` (Finance memutuskan; kode alasan tetap `KODE_KARTU` + kalimat), atau `lewati` (bukan urusan F1).
Urutan: lewati → PT/kode → pesanan → calon jalur A → nominal → laporan → rekening → periode → selisih bayar →
pengaturan.

* **Calon jalur A dicari sebelum nominal harapan** (ketetapan pengendali R3): kwitansi yang belum terverifikasi bank
  sudah menulis `payments[]`, jadi semua harapan (sisa wajib, sisa baris jadwal, sisa tagihan) sudah dikurangi uangnya —
  kwitansi Rp 1 jt untuk CBD Rp 1 jt membuat sisa 0. Calon = kwitansi pesanan itu, tidak batal, belum terverifikasi,
  kasnya masih punya ruang cocok dan bernominal sama persis (≤ 1 sen — `_link` tidak menautkan melebihi kapasitas kas).
  Calon di rekening lain → kartu `rekening_beda`; kwitansi berselisih pecahan (< Rp 1) → kartu `nominal_beda` (bukan C,
  karena uangnya mungkin sama). Jalur A hanya diperiksa aturan laporan dan pengaturan: harapan, rekening instruksi,
  periode, dan selisih bayar sudah dilalui kwitansinya saat dibuat.
* **Cocok sempurna** = `abs(nominal − harapan) < Rp 1` terhadap salah satu harapan, menurut urutan: sisa wajib sebelum
  gudang (R19), sisa baris jadwal milik kode itu, sisa tagihan pesanan. Definisi F1, bukan pengaturan.
* Pemeriksa yang dipakai semuanya pemeriksa tanpa tulisan yang sudah ada (`validate_targets`, `periksa_uang_masuk`,
  `gl_service.preflight_posting`, `payment_variance_service.pre_assess`); galatnya dipetakan ke kode alasan.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from core_utils import now_iso, qty_num_id, rupiah
from db import db

SUMBER = "mutasi_bank"
# Pelaku sistem: satu-satunya yang dikecualikan dari B3 (`ar_receipt_service._pagar_lapor_bayar`), dan hanya bila
# kwitansinya juga bersumber `SUMBER`.
AKTOR_MUTASI = {"id": "", "name": "Sistem (mutasi bank)", "role": "system", "sistem": SUMBER}
PENANDA_AKTIF = "f1_kwitansi_mutasi_aktif_sejak"


async def ensure_aktif_sejak() -> str:
    """Tulis waktu aktif F1 sekali saja (saat backend pertama menyala); panggilan berikutnya tidak menimpa."""
    await db.system_settings.update_one(
        {"scope": "__migrations__", PENANDA_AKTIF: {"$exists": False}},
        {"$set": {PENANDA_AKTIF: now_iso()}}, upsert=True)
    return await aktif_sejak()


async def aktif_sejak() -> str:
    """Waktu aktif F1 (ISO); kosong bila belum pernah ditulis."""
    doc = await db.system_settings.find_one({"scope": "__migrations__"}, {"_id": 0, PENANDA_AKTIF: 1}) or {}
    return doc.get(PENANDA_AKTIF) or ""


async def menyala(entity_id: Optional[str]) -> bool:
    """Apakah PT `entity_id` memakai kwitansi otomatis dari mutasi bank (`bank.kwitansi_otomatis_mutasi`)."""
    from services.nilai_pengaturan import nilai
    return bool(await nilai("bank.kwitansi_otomatis_mutasi", entity_id))


# ── Penilai baris mutasi (Tugas 2) ───────────────────────────────────────────────────────────────────────────────────
#: Kode alasan kartu — string tetap, dipakai layar (antrean Meja Keuangan, Rekonsiliasi).
KODE_KARTU = ("pt_tidak_jelas", "kode_ganda", "pesanan_mati", "sudah_lunas", "nominal_beda", "rekening_beda",
              "rekening_tolak_cara", "periode_tutup", "laporan_beda", "laporan_diproses", "laporan_dan_kwitansi",
              "selisih_perlu_putusan", "otomatis_mati")
#: Kode alasan keputusan cocok sempurna (jalur A/B/C).
KODE_COCOK = "cocok"
#: "Cocok sempurna" — selisih nominal di bawah Rp 1 (transfer selalu rupiah bulat; tagihan DP bisa berpecahan).
SELISIH_COCOK = 1.0
#: Sen: kwitansi calon jalur A harus sama persis dengan mutasi (CAS kapasitas kas `bank_recon_service._link`).
SEN = 0.01
_ANGKA = {2: "Dua", 3: "Tiga", 4: "Empat"}


def _rp(nilai: Any) -> str:
    """`core_utils.rupiah` untuk nominal bulat; nominal berpecahan ditulis dengan desimalnya ("Rp 173.437,5") supaya
    selisih pecahan tidak terbaca nol."""
    v = round(float(nilai or 0), 2)
    if abs(v - round(v)) < 0.005:
        return rupiah(v)
    return f"{'-' if v < 0 else ''}Rp {qty_num_id(abs(v))}"


def _hasil(keputusan: str, kode: str, alasan: str, *, order: Optional[Dict[str, Any]] = None,
           harapan: Optional[float] = None, receipt: Optional[Dict[str, Any]] = None,
           report: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"keputusan": keputusan, "alasan_kode": kode, "alasan": alasan, "order": order, "harapan": harapan,
            "receipt": receipt, "report": report}


def _lewati(kode: str, alasan: str) -> Dict[str, Any]:
    return _hasil("lewati", kode, alasan)


def _kartu(kode: str, alasan: str, **isi: Any) -> Dict[str, Any]:
    return _hasil("kartu", kode, alasan, **isi)


async def _nama_rekening(*ids: str) -> Dict[str, str]:
    ids_ = [i for i in dict.fromkeys(ids) if i]
    if not ids_:
        return {}
    proyeksi = {"_id": 0, "id": 1, "name": 1, "account_number": 1}
    return {a["id"]: a.get("name") or a.get("account_number") or a["id"]
            async for a in db.bank_accounts.find({"id": {"$in": ids_}}, proyeksi)}


async def _sisa_baris_jadwal(order: Dict[str, Any], kode: str) -> Optional[float]:
    """Sisa baris jadwal tagihan (`payment_plans.lines[]` ber-`pay_code == kode`) dari pembaca jatuh tempo tunggal
    `billing_schedule_service.lines_for_orders` (pembayaran dialokasikan ke baris). `None` = kode bukan milik baris."""
    plan = await db.payment_plans.find_one({"doc_type": "sales_order", "doc_id": order["id"],
                                            "status": {"$ne": "void"}, "lines.pay_code": kode},
                                           {"_id": 0, "id": 1, "lines": 1})
    if not plan:
        return None
    line_id = next((ln.get("line_id") for ln in plan.get("lines") or [] if ln.get("pay_code") == kode), "")
    from services import billing_schedule_service as bss
    rows = ((await bss.lines_for_orders([order])).get(order["id"]) or {}).get("rows") or []
    row = next((r for r in rows if r.get("plan_id") == plan["id"] and r.get("line_id") == line_id), None)
    return float(row["outstanding"]) if row else None


async def _harapan(order: Dict[str, Any], kode: str, sisa: float) -> List[float]:
    """Nominal harapan yang berlaku, urutan §5.2-4: sisa wajib sebelum gudang (R19) → sisa baris jadwal kode itu →
    sisa tagihan pesanan."""
    from services import pay_hold_service as phs
    out: List[float] = []
    wajib = await phs.sisa_wajib_sebelum_gudang(order)
    if wajib:
        out.append(round(float(wajib), 2))
    baris = await _sisa_baris_jadwal(order, kode)
    if baris is not None and baris > SEN:
        out.append(round(baris, 2))
    out.append(round(sisa, 2))
    return out


async def _calon_kwitansi(order_id: str, line: Dict[str, Any], amount: float) -> Tuple[list, list, list]:
    """Kwitansi terbuka pesanan (tidak batal, belum terverifikasi bank, kas tidak batal dan belum cocok penuh), urut
    tanggal: → (sama persis di rekening mutasi, sama persis di rekening lain, berselisih pecahan < Rp 1)."""
    rows = await db.ar_receipts.find(
        {"allocations.order_id": order_id, "status": {"$ne": "void"}, "bank_verified": {"$ne": True},
         "amount": {"$gt": SEN}, "cash_txn_id": {"$nin": ["", None]}}, {"_id": 0}).to_list(200)
    rows.sort(key=lambda r: (str(r.get("receipt_date") or ""), str(r.get("created_at") or "")))
    kas = {t["id"]: t async for t in db.cash_transactions.find(
        {"id": {"$in": [r["cash_txn_id"] for r in rows]}, "status": {"$ne": "void"}}, {"_id": 0})} if rows else {}
    sama, lain, pecahan = [], [], []
    for rc in rows:
        t = kas.get(rc["cash_txn_id"])
        if not t:
            continue
        nilai = round(float(t.get("amount") or 0), 2)
        ruang = round(nilai - float(t.get("reconciled_amount") or 0), 2)
        beda = abs(nilai - amount)
        if beda <= SEN and ruang + SEN >= amount:
            (sama if t.get("account_id") == line.get("bank_account_id") else lain).append((rc, t))
        elif SEN < beda < SELISIH_COCOK and ruang > SEN:
            pecahan.append((rc, t))
    return sama, lain, pecahan


async def _laporan_tertunda(order_id: str) -> Tuple[list, list]:
    """Laporan bayar pesanan yang menunggu keputusan Finance → (`menunggu`, `memproses`)."""
    from services import payment_report_service as prs
    rows = await db.payment_reports.find({"order_id": order_id, "status": {"$in": list(prs.TERTUNDA)}},
                                         {"_id": 0}).sort("created_at", 1).to_list(50)
    return ([r for r in rows if r.get("status") == prs.MENUNGGU], [r for r in rows if r.get("status") == prs.MEMPROSES])


def _nomor_laporan(rows: list) -> str:
    return ", ".join(r.get("number") or r.get("id", "") for r in rows)


async def _laporan_beda(menunggu: list, line: Dict[str, Any], amount: float) -> str:
    if len(menunggu) > 1:
        return f"{_ANGKA.get(len(menunggu), len(menunggu))} laporan bayar menunggu: {_nomor_laporan(menunggu)}"
    rep = menunggu[0]
    if abs(float(rep.get("amount") or 0) - amount) >= SELISIH_COCOK:
        return (f"Laporan bayar {rep.get('number', '')} menunggu dengan nominal {_rp(rep.get('amount'))} ≠ mutasi "
                f"{_rp(amount)}")
    nama = await _nama_rekening(rep.get("account_id") or "", line.get("bank_account_id") or "")
    return (f"Laporan bayar {rep.get('number', '')} menunggu ke rekening "
            f"{nama.get(rep.get('account_id'), rep.get('account_name') or '-')} ≠ rekening mutasi "
            f"{nama.get(line.get('bank_account_id'), '-')}")


async def _periksa_rekening(line: Dict[str, Any], order: Dict[str, Any], entity_id: str, amount: float,
                            harapan: float, customer_id: str, kode: str) -> Optional[Dict[str, Any]]:
    """Rekening mutasi menerima transfer pelanggan dan sama dengan rekening instruksi pesanan — pemeriksa kwitansi yang
    sama (`ar_receipt_service.periksa_uang_masuk`, tanpa tulisan). → kartu atau `None`."""
    from services import ar_receipt_service as ars
    from services import payment_method_service as pms
    try:
        cara = await pms.wajib(entity_id, "transfer", arah="masuk")
    except pms.CaraBayarError as exc:
        return _kartu("rekening_tolak_cara", str(exc), order=order, harapan=harapan)
    payload = {"account_id": line.get("bank_account_id") or "", "reference_no": line.get("ref") or kode,
               "allocations": [{"order_id": order["id"], "amount": harapan}]}
    try:
        await ars.periksa_uang_masuk(payload, entity_id=entity_id, cara=cara, amount=amount, customer_id=customer_id,
                                     total_funds=amount)
    except HTTPException as exc:
        if exc.detail != ars.PESAN_TIDAK_SESUAI:
            return _kartu("rekening_tolak_cara", str(exc.detail), order=order, harapan=harapan)
        from services.payment_code_service import teks_rekening
        nama = await _nama_rekening(line.get("bank_account_id") or "", order.get("receiving_account_id") or "")
        instruksi = nama.get(order.get("receiving_account_id")) or teks_rekening(order.get("receiving_account"))
        return _kartu("rekening_beda", f"Rekening mutasi {nama.get(line.get('bank_account_id'), '-')} ≠ rekening "
                                       f"instruksi pesanan {instruksi}", order=order, harapan=harapan)
    return None


async def _bila_menyala(jalur: str, entity_id: str, nomor: str, rincian: str, **isi: Any) -> Dict[str, Any]:
    """Langkah terakhir: pengaturan PT mati → kartu `otomatis_mati` yang menyebut keputusan bila menyala."""
    if not await menyala(entity_id):
        return _kartu("otomatis_mati", f"Kwitansi otomatis mati untuk PT ini — mutasi ini cocok sempurna dengan "
                                       f"{nomor} ({rincian})", **isi)
    return _hasil(jalur, KODE_COCOK, f"Cocok sempurna dengan {nomor} — {rincian}", **isi)


async def nilai_baris(line: Dict[str, Any]) -> Dict[str, Any]:
    """Nilai satu baris mutasi bank TANPA menulis apa pun (rancangan §5.1–§5.2, R3). →
    `{keputusan: "A"|"B"|"C"|"kartu"|"lewati", alasan_kode, alasan, order, harapan, receipt, report}`."""
    from services import bank_recon_service as brs
    from services import payment_report_service as prs
    from services.customer_service import DEAD_STATUSES

    # 1. lewati — bukan urusan F1
    if (line.get("direction") or "") != "in":
        return _lewati("bukan_masuk", "Mutasi keluar — bukan uang masuk pelanggan")
    if line.get("status") != "unmatched":
        return _lewati("bukan_unmatched", f"Mutasi berstatus {line.get('status') or '-'} — sudah ditangani")
    f1 = line.get("f1") or {}
    if f1.get("pernah_otomatis"):
        return _lewati("pernah_otomatis", "Mutasi ini pernah ditautkan otomatis — tidak diproses otomatis lagi")
    if f1.get("status") == "dibatalkan":
        return _lewati("dibatalkan", "Kwitansi otomatis mutasi ini pernah dibatalkan — tidak diproses otomatis lagi")
    aktif = await aktif_sejak()
    if not aktif or str(line.get("created_at") or "") < aktif:
        return _lewati("sebelum_aktif", "Mutasi diimpor sebelum kwitansi otomatis aktif")
    hits = line.get("pay_code_hits") or await brs.pay_code_hits(line)
    if not hits:
        return _lewati("tanpa_kode", "Tidak ada kode bayar di berita transfer")

    # 2. PT & kode
    ent = line.get("entity_id") or ""
    if not ent or ent == brs.GROUP_ENTITY:
        return _kartu("pt_tidak_jelas", "Mutasi tercatat di tingkat grup — PT penerima belum jelas")
    if len(hits) > 1:
        return _kartu("kode_ganda", f"{_ANGKA.get(len(hits), len(hits))} kode bayar di berita transfer: "
                                    f"{', '.join(h.get('code', '') for h in hits)}")
    hit = hits[0]
    kode = hit.get("code") or ""

    # 3. pesanan hidup & menerima kwitansi
    order = await db.sales_orders.find_one({"id": hit.get("order_id")}, {"_id": 0})
    nomor = (order or {}).get("number") or hit.get("order_number") or hit.get("order_id") or "-"
    if not order:
        return _kartu("pesanan_mati", f"Pesanan {nomor} tidak ditemukan")
    if order.get("status") in DEAD_STATUSES:
        from services.pdf_engine import status_label
        return _kartu("pesanan_mati", f"Pesanan {nomor} berstatus {status_label(order['status']) or order['status']} "
                                      f"— tidak menerima pembayaran", order=order)
    amount = round(float(line.get("amount") or 0), 2)
    sisa = prs.sisa_tagihan(order)
    customer_id = hit.get("customer_id") or order.get("customer_id") or ""
    if sisa > SEN:   # sisa 0: tidak ada alokasi baru untuk diperiksa (jalur A, atau kartu sudah lunas)
        from services import ar_allocation_service as aas
        try:
            await aas.validate_targets("kas", [{"order_id": order["id"], "amount": min(amount, sisa)}],
                                       customer_id=customer_id, entity_id=ent)
        except HTTPException as exc:
            return _kartu("pt_tidak_jelas" if exc.status_code == 403 else "pesanan_mati", str(exc.detail),
                          order=order)

    # 4. calon jalur A — kwitansi terbuka bernominal sama (sebelum harapan, R3)
    sama, lain, pecahan = await _calon_kwitansi(order["id"], line, amount)
    menunggu, memproses = await _laporan_tertunda(order["id"])
    if sama:
        rc, kas = sama[0]
        setara = [r for r in menunggu if abs(float(r.get("amount") or 0) - amount) < SELISIH_COCOK]
        if setara:
            return _kartu("laporan_dan_kwitansi", f"Kwitansi {rc.get('number', '')} dan laporan "
                                                  f"{setara[0].get('number', '')} sama-sama menunggu — putuskan",
                          order=order, receipt=rc, report=setara[0])
        if memproses:
            return _kartu("laporan_diproses", f"Laporan bayar {_nomor_laporan(memproses)} sedang diproses Finance",
                          order=order, receipt=rc)
        if menunggu:
            return _kartu("laporan_beda", await _laporan_beda(menunggu, line, amount), order=order, receipt=rc)
        nilai = round(float(kas.get("amount") or 0), 2)
        return await _bila_menyala("A", ent, nomor, f"tautkan ke kwitansi {rc.get('number', '')} ({_rp(nilai)}) yang "
                                                    f"belum terverifikasi bank", order=order, harapan=nilai, receipt=rc)
    if lain:
        rc, kas = lain[0]
        nama = await _nama_rekening(kas.get("account_id") or "", line.get("bank_account_id") or "")
        return _kartu("rekening_beda", f"Kwitansi {rc.get('number', '')} {_rp(kas.get('amount'))} tercatat ke rekening "
                                       f"{nama.get(kas.get('account_id'), '-')} ≠ rekening mutasi "
                                       f"{nama.get(line.get('bank_account_id'), '-')}", order=order, receipt=rc)
    if pecahan:
        rc, kas = pecahan[0]
        nilai = round(float(kas.get("amount") or 0), 2)
        return _kartu("nominal_beda", f"Kwitansi {rc.get('number', '')} {_rp(nilai)} berbeda "
                                      f"{_rp(abs(nilai - amount))} dari mutasi {_rp(amount)}", order=order, receipt=rc)

    # 5. nominal = salah satu harapan (selisih < Rp 1)
    if sisa < SELISIH_COCOK:
        return _kartu("sudah_lunas", f"Pesanan {nomor} sudah lunas", order=order)
    daftar = await _harapan(order, kode, sisa)
    harapan = next((h for h in daftar if abs(amount - h) < SELISIH_COCOK), None)
    if harapan is None:
        beda = round(amount - daftar[0], 2)
        return _kartu("nominal_beda", f"Nominal mutasi {_rp(amount)} ≠ tagihan {_rp(daftar[0])} "
                                      f"({'lebih' if beda > 0 else 'kurang'} {_rp(abs(beda))})", order=order)

    # 6. laporan bayar: tepat satu menunggu bernominal & berekening sama → jalur B
    report = None
    if memproses:
        return _kartu("laporan_diproses", f"Laporan bayar {_nomor_laporan(memproses)} sedang diproses Finance",
                      order=order, harapan=harapan)
    if menunggu:
        rep = menunggu[0]
        if (len(menunggu) == 1 and abs(float(rep.get("amount") or 0) - amount) < SELISIH_COCOK
                and rep.get("account_id") == line.get("bank_account_id")):
            report = rep
        else:
            return _kartu("laporan_beda", await _laporan_beda(menunggu, line, amount), order=order, harapan=harapan)

    # 7. rekening mutasi menerima transfer & sama dengan rekening instruksi pesanan
    kartu = await _periksa_rekening(line, order, ent, amount, harapan, customer_id, kode)
    if kartu:
        return kartu

    # 8. periode buku tanggal mutasi
    from services import gl_service as gl
    try:
        await gl.preflight_posting(ent, line.get("stmt_date") or "")
    except gl.ClosedPeriodError as exc:
        return _kartu("periode_tutup", str(exc), order=order, harapan=harapan)

    # 9. selisih bayar tidak meminta keputusan
    from services import payment_variance_service as pvs
    selisih = await pvs.pre_assess(customer_id, amount, [{"order_id": order["id"], "amount": harapan}],
                                   as_of=line.get("stmt_date") or "", entity_id=ent)
    if selisih.get("needs_decision"):
        delta = float(selisih.get("delta") or 0)
        arah = "lebih" if delta > 0 else "kurang"
        return _kartu("selisih_perlu_putusan", f"Selisih {_rp(abs(delta))} {arah} bayar melewati toleransi "
                                               f"{_rp(selisih.get('tolerance'))} — perlu putusan Finance",
                      order=order, harapan=harapan, report=report)

    # 10. pengaturan PT
    if report:
        return await _bila_menyala("B", ent, nomor, f"terima laporan bayar {report.get('number', '')} "
                                                    f"({_rp(report.get('amount'))})", order=order, harapan=harapan,
                                   report=report)
    return await _bila_menyala("C", ent, nomor, f"kwitansi baru {_rp(harapan)}", order=order, harapan=harapan)
