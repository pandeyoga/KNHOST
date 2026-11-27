"""F1 — kwitansi otomatis dari mutasi bank: fondasi (konstanta, waktu aktif, pembaca pengaturan), penilai baris, dan
pelaksana (jalur A/B/C, proses impor & rekening, pemberitahuan).

Rancangan `docs/superpowers/specs/2026-11-27-kwitansi-otomatis-mutasi-design.md` §5.1–§5.4, §5.7, §5.8. Uang tetap lewat
pintu yang ada: kwitansi `ar_receipt_service.create_receipt` / `payment_report_service.terima`, tautan mutasi
`bank_recon_service._link` (tidak ada posting jurnal baru).

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

PELAKSANA (`proses_baris`, `proses_impor`, `proses_rekening`)
=============================================================
Satu baris = satu operasi server: nilai (tanpa tulisan; `lewati` berhenti di sini) → KLAIM baris dengan `match_lock`
yang sama dengan `bank_recon_service._link` (kalah klaim → `lewati` `sedang_diproses`, tanpa tulisan) → nilai ULANG di
bawah kunci → tindak:

* **A** — tautkan mutasi ke kas kwitansi yang sudah ada (`match_type = auto`), tanpa kwitansi baru.
* **B** — `payment_report_service.terima(..., bank_line=baris)` (lampiran tidak wajib; kwitansi bersumber mutasi) lalu
  tautkan ke kas kwitansinya (`auto_receipt`).
* **C** — `ar_receipt_service.create_receipt` berisian mutasi (§5.3) lalu tautkan (`auto_receipt`).
* **kartu** — penanda `f1` berkode + kalimat, kunci dilepas, tanpa uang.

Kunci diserahkan ke `_link(..., op=kunci)`; sesudah tautan kwitansi terverifikasi bank dan tahan bayar dibuka (jalur
`_link` yang ada). Tidak ganda: indeks unik `uq_bank_line_receipt` (`DuplicateKeyError` → kwitansi pemenang ditautkan) +
pemulihan (kwitansi ber-`bank_line_id` sudah ada tetapi baris belum tertaut → hanya tautkan). Galat tak terduga →
kartu `galat` berkalimat; kwitansi setengah jadi dicabut rollback `create_receipt`; batch berlanjut ke baris berikutnya.
Penanda baris `f1 = {status otomatis|kartu|dibatalkan, jalur, alasan_kode, alasan, dinilai_at, receipt_id, order_id,
report_id, pernah_otomatis, dilepas_at}`; `pernah_otomatis` tidak pernah dihapus (`_unlink` mengisi `dilepas_at`).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, now_iso, qty_num_id, rupiah
from db import db
from services import bank_recon_service as brs

logger = logging.getLogger(__name__)

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
#: Kode alasan kartu milik pelaksana: galat tak terduga saat bertindak (kalimatnya memuat galat itu).
KODE_GALAT = "galat"
#: Kode alasan kartu — string tetap, dipakai layar (antrean Meja Keuangan, Rekonsiliasi). Penilai memakai semua kecuali
#: `galat` (pelaksana).
KODE_KARTU = ("pt_tidak_jelas", "kode_ganda", "pesanan_mati", "sudah_lunas", "nominal_beda", "rekening_beda",
              "rekening_tolak_cara", "periode_tutup", "laporan_beda", "laporan_diproses", "laporan_dan_kwitansi",
              "selisih_perlu_putusan", "otomatis_mati", KODE_GALAT)
#: Kode alasan keputusan cocok sempurna (jalur A/B/C).
KODE_COCOK = "cocok"
#: "Cocok sempurna" — selisih nominal di bawah Rp 1 (transfer selalu rupiah bulat; tagihan DP bisa berpecahan).
SELISIH_COCOK = 1.0
# Kwitansi calon jalur A harus sama persis dengan mutasi (≤ `brs.EPS`, 1 sen): CAS kapasitas kas `brs._link`.
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
    if baris is not None and baris > brs.EPS:
        out.append(round(baris, 2))
    out.append(round(sisa, 2))
    return out


async def _kas_di_buku(line: Dict[str, Any], kas_ids: List[str]) -> set:
    """Id kas (dari `kas_ids`) yang termasuk buku rekening mutasi — saringan YANG SAMA dengan kandidat pencocokan
    (`bank_recon_service._book_query`): kas ber-`account_id` rekening itu, plus kas lama tanpa rekening bila rekening
    itu satu-satunya rekening aktif PT untuk jenis kasnya (`bank_service.sole_account_id`, R5-M1)."""
    acc = await db.bank_accounts.find_one({"id": line.get("bank_account_id") or ""}, {"_id": 0})
    if not acc or not kas_ids:
        return set()
    q = {"$and": [{"id": {"$in": kas_ids}}, await brs._book_query(acc, None)]}
    return {t["id"] async for t in db.cash_transactions.find(q, {"_id": 0, "id": 1})}


async def _calon_kwitansi(order_id: str, line: Dict[str, Any], amount: float) -> Tuple[list, list, list, list]:
    """Kwitansi terbuka pesanan (tidak batal, belum terverifikasi bank, kas tidak batal dan belum cocok penuh), urut
    tanggal: → (sama persis di buku rekening mutasi, sama persis di rekening lain, berselisih pecahan < Rp 1, semua
    kwitansi terbuka). Kwitansi yang lahir dari mutasi LAIN (`bank_line_id` ≠ baris ini) milik mutasi itu: bukan calon,
    hanya ikut terhitung terbuka."""
    rows = await db.ar_receipts.find(
        {"allocations.order_id": order_id, "status": {"$ne": "void"}, "bank_verified": {"$ne": True},
         "amount": {"$gt": brs.EPS}, "cash_txn_id": {"$nin": ["", None]}}, {"_id": 0}).to_list(200)
    rows.sort(key=lambda r: (str(r.get("receipt_date") or ""), str(r.get("created_at") or "")))
    kas = {t["id"]: t async for t in db.cash_transactions.find(
        {"id": {"$in": [r["cash_txn_id"] for r in rows]}, "status": {"$ne": "void"}}, {"_id": 0})} if rows else {}
    buku = await _kas_di_buku(line, list(kas))
    sama, lain, pecahan, terbuka = [], [], [], []
    for rc in rows:
        t = kas.get(rc["cash_txn_id"])
        if not t:
            continue
        terbuka.append(rc)
        if rc.get("bank_line_id") and rc["bank_line_id"] != line.get("id"):
            continue
        nilai = round(float(t.get("amount") or 0), 2)
        ruang = round(nilai - float(t.get("reconciled_amount") or 0), 2)
        beda = abs(nilai - amount)
        if beda <= brs.EPS and ruang + brs.EPS >= amount:
            (sama if t["id"] in buku else lain).append((rc, t))
        elif brs.EPS < beda < SELISIH_COCOK and ruang > brs.EPS:
            pecahan.append((rc, t))
    return sama, lain, pecahan, terbuka


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
    if sisa > brs.EPS:   # sisa 0: tidak ada alokasi baru untuk diperiksa (jalur A, atau kartu sudah lunas)
        from services import ar_allocation_service as aas
        try:
            await aas.validate_targets("kas", [{"order_id": order["id"], "amount": min(amount, sisa)}],
                                       customer_id=customer_id, entity_id=ent)
        except HTTPException as exc:
            return _kartu("pt_tidak_jelas" if exc.status_code == 403 else "pesanan_mati", str(exc.detail),
                          order=order)

    # 4. calon jalur A — kwitansi terbuka bernominal sama (sebelum harapan, R3)
    sama, lain, pecahan, terbuka = await _calon_kwitansi(order["id"], line, amount)
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
        tujuan = nama.get(kas.get("account_id")) if kas.get("account_id") else "(tanpa rekening)"
        return _kartu("rekening_beda", f"Kwitansi {rc.get('number', '')} {_rp(kas.get('amount'))} tercatat ke rekening "
                                       f"{tujuan or '-'} ≠ rekening mutasi "
                                       f"{nama.get(line.get('bank_account_id'), '-')}", order=order, receipt=rc)
    if pecahan:
        rc, kas = pecahan[0]
        nilai = round(float(kas.get("amount") or 0), 2)
        return _kartu("nominal_beda", f"Kwitansi {rc.get('number', '')} {_rp(nilai)} berbeda "
                                      f"{_rp(abs(nilai - amount))} dari mutasi {_rp(amount)}", order=order, receipt=rc)

    # 5. nominal = salah satu harapan (selisih < Rp 1)
    if sisa < SELISIH_COCOK:
        if terbuka:   # R5-M2 — lunas karena kwitansi yang belum cocok mutasi (nominal ≠ mutasi): uangnya mungkin sama
            return _kartu("sudah_lunas", f"Pesanan {nomor} sudah lunas oleh kwitansi "
                                         f"{', '.join(r.get('number', '') for r in terbuka)} yang belum cocok mutasi",
                          order=order, receipt=terbuka[0])
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
    except gl.ClosedPeriodError:
        from services.book_date import tanggal_panjang   # R5-M8 — kalimat pendek: "Periode Oktober 2026 sudah ditutup"
        bulan = tanggal_panjang(line.get("stmt_date") or "").split(" ", 1)[1]
        return _kartu("periode_tutup", f"Periode {bulan} sudah ditutup", order=order, harapan=harapan)

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


# ── Pelaksana (Tugas 3) ──────────────────────────────────────────────────────────────────────────────────────────────
#: Kode lewati milik pelaksana: baris sedang diklaim proses lain (pencocokan di Rekonsiliasi, atau F1 lain).
KODE_DIKLAIM = "sedang_diproses"
#: `match_type` tautan per jalur: A = pita otomatis yang sudah ada; B/C = kwitansi lahir dari mutasi ini.
MATCH_TYPE = {"A": "auto", "B": "auto_receipt", "C": "auto_receipt"}


class _GagalTindak(Exception):
    """Galat saat bertindak, sudah berkalimat untuk kartu `galat` (tahap yang gagal + galat aslinya)."""

    def __init__(self, alasan: str) -> None:
        super().__init__(alasan)
        self.alasan = alasan


def _pesan(exc: BaseException) -> str:
    detail = getattr(exc, "detail", None)
    if isinstance(detail, dict):
        detail = detail.get("message") or detail.get("detail") or ""
    teks = str(detail or exc or "").strip() or exc.__class__.__name__
    return teks[:300].rstrip(" .")


def _kalimat_galat(tahap: str, exc: BaseException, nomor: str = "") -> str:
    pesan = _pesan(exc)
    if tahap == "C":
        return f"Kwitansi otomatis gagal dibuat: {pesan}. Catat manual dari kartu ini."
    if tahap == "B":
        return f"Laporan bayar {nomor} gagal diterima otomatis: {pesan}. Putuskan laporan itu dari kartu ini."
    if tahap == "tautan":
        return (f"Mutasi gagal ditautkan otomatis ke kwitansi {nomor}: {pesan}. Cocokkan manual di Rekonsiliasi "
                "Bank.")
    return f"Mutasi gagal diproses otomatis: {pesan}."


async def label_mutasi(line: Dict[str, Any]) -> str:
    """"{tanggal mutasi} · {rekening}" — jejak kwitansi / laporan yang lahir dari satu baris mutasi bank."""
    from services.book_date import tanggal_panjang
    rek = line.get("bank_account_id") or ""
    nama = await _nama_rekening(rek)
    try:
        tgl = tanggal_panjang(line.get("stmt_date") or "")
    except ValueError:
        tgl = str(line.get("stmt_date") or "-")
    return f"{tgl} · {nama.get(rek, '-')}"


def _keluaran(line_id: str, hasil: str, *, jalur: str = "", receipt: Optional[Dict[str, Any]] = None,
              order: Optional[Dict[str, Any]] = None, kode: str = "", alasan: str = "",
              released: bool = False) -> Dict[str, Any]:
    rc, so = receipt or {}, order or {}
    return {"line_id": line_id, "hasil": hasil, "jalur": jalur, "receipt_id": rc.get("id", ""),
            "receipt_number": rc.get("number", ""), "order_id": so.get("id", ""), "order_number": so.get("number", ""),
            "alasan_kode": kode, "alasan": alasan, "released": bool(released)}


def _penanda(status: str, *, jalur: str = "", kode: str = "", alasan: str = "", receipt_id: str = "",
             order_id: str = "", report_id: str = "") -> Dict[str, Any]:
    return {"status": status, "jalur": jalur, "alasan_kode": kode, "alasan": alasan, "dinilai_at": now_iso(),
            "receipt_id": receipt_id, "order_id": order_id, "report_id": report_id,
            "pernah_otomatis": status == "otomatis", "dilepas_at": ""}


def _penanda_kartu(h: Dict[str, Any]) -> Dict[str, Any]:
    return _penanda("kartu", kode=h["alasan_kode"], alasan=h["alasan"],
                    receipt_id=(h.get("receipt") or {}).get("id", ""), order_id=(h.get("order") or {}).get("id", ""),
                    report_id=(h.get("report") or {}).get("id", ""))


async def _klaim(line_id: str) -> str:
    """Klaim baris dengan `match_lock` yang sama dengan `bank_recon_service._link` (kosong atau basi). → kunci, atau ""
    bila baris bukan `unmatched` lagi / sedang dipegang proses lain."""
    op = new_id("f1klaim")
    got = await db.bank_statement_lines.update_one(
        {"id": line_id, "status": "unmatched",
         "$or": [{"match_lock": {"$exists": False}}, {"match_lock_at": {"$lt": brs._stale_before()}}]},
        {"$set": {"match_lock": op, "match_lock_at": now_iso()}})
    return op if got.modified_count == 1 else ""


async def _lepas_kunci(line_id: str, op: str) -> None:
    await db.bank_statement_lines.update_one({"id": line_id, "match_lock": op},
                                             {"$unset": {"match_lock": "", "match_lock_at": ""}})


async def _tulis_kartu(line_id: str, op: str, penanda: Dict[str, Any]) -> None:
    """Penanda kartu + lepas kunci: hanya baris yang masih `unmatched` dan kuncinya milik operasi ini (atau sudah
    dicabut — `_link` mencabut kunci saat gagal)."""
    await db.bank_statement_lines.update_one(
        {"id": line_id, "status": "unmatched", "$or": [{"match_lock": op or "-"}, {"match_lock": {"$exists": False}}]},
        {"$set": {"f1": penanda, "updated_at": now_iso()}, "$unset": {"match_lock": "", "match_lock_at": ""}})


async def _kwitansi_baris(line_id: str) -> Optional[Dict[str, Any]]:
    """Kwitansi hidup yang lahir dari baris ini — saringan sama dengan indeks unik parsial `uq_bank_line_receipt`."""
    return await db.ar_receipts.find_one({"bank_line_id": line_id, "status": "posted"}, {"_id": 0})


async def _tautkan(line: Dict[str, Any], receipt: Dict[str, Any], op: str, match_type: str) -> None:
    """Tautkan seluruh nominal mutasi ke kas kwitansi lewat `bank_recon_service._link` (kunci milik pemanggil)."""
    kas = receipt.get("cash_txn_id") or ""
    if not kas:
        raise ValueError(f"Kwitansi {receipt.get('number', '')} belum punya transaksi kas")
    await brs._link(line, [{"txn_id": kas, "amount": brs._round(line.get("amount"))}], AKTOR_MUTASI["name"],
                    match_type, "1:1", op=op)


async def _kwitansi_c(line: Dict[str, Any], h: Dict[str, Any]) -> Dict[str, Any]:
    """Jalur C (§5.3): kwitansi baru berisian mutasi lewat `create_receipt`. Alokasi = harapan, paling banyak nominal
    mutasi (alokasi tidak boleh melebihi dana); selisih pecahan < Rp 1 diputus aturan pembulatan selisih bayar.
    `DuplicateKeyError` (`uq_bank_line_receipt`: proses lain sudah melahirkan kwitansi baris ini) → kwitansi
    pemenang."""
    from services import ar_receipt_service as ars
    order = h["order"]
    hits = line.get("pay_code_hits") or await brs.pay_code_hits(line)
    kode = (hits[0] if hits else {}).get("code") or ""
    amount = brs._round(line.get("amount"))
    payload = {
        "customer_id": order.get("customer_id") or (hits[0] if hits else {}).get("customer_id") or "",
        "entity_id": line.get("entity_id") or order.get("entity_id") or "", "amount": amount, "method": "transfer",
        "account_id": line.get("bank_account_id") or "", "receipt_date": line.get("stmt_date") or "",
        "reference_no": (line.get("ref") or "").strip() or kode,
        "allocations": [{"order_id": order["id"], "amount": round(min(float(h["harapan"]), amount), 2)}],
        "notes": f"Kwitansi otomatis dari mutasi bank {await label_mutasi(line)} · {kode}",
        "source": SUMBER, "bank_line_id": line["id"]}
    try:
        return await ars.create_receipt(payload, dict(AKTOR_MUTASI))
    except DuplicateKeyError:
        menang = await _kwitansi_baris(line["id"])
        if not menang:
            raise
        logger.info("[F1] kwitansi baris %s sudah dibuat proses lain (%s) — hanya ditautkan", line["id"],
                    menang.get("number"))
        return menang


async def _sesudah_tautan(line: Dict[str, Any], *, jalur: str, receipt: Dict[str, Any],
                          order: Optional[Dict[str, Any]], tertahan: bool, alasan: str, pemicu: str,
                          report: Optional[Dict[str, Any]] = None, kirim: bool = True) -> Dict[str, Any]:
    """Sesudah tautan berhasil: penanda `f1` otomatis, kirim kwitansi WhatsApp (kwitansi baru), jejak audit, notifikasi
    sales (hanya pesanan yang tadinya tertahan bayar). Semua efek samping: galatnya dicatat, tidak mengubah hasil."""
    from services import pay_hold_service as phs
    from services.customer_service import DEAD_STATUSES
    lid = line["id"]
    ent = line.get("entity_id") or ""
    report_id = (report or {}).get("id") or receipt.get("payment_report_id") or ""
    try:
        await db.bank_statement_lines.update_one({"id": lid, "status": "matched"}, {"$set": {"f1": _penanda(
            "otomatis", jalur=jalur, kode=KODE_COCOK, alasan=alasan, receipt_id=receipt.get("id", ""),
            order_id=(order or {}).get("id", ""), report_id=report_id)}})
    except Exception as exc:  # noqa: BLE001 — tautan sudah sah
        logger.error("[F1] penanda otomatis baris %s gagal ditulis: %s", lid, exc)
    sesudah = await db.sales_orders.find_one({"id": order["id"]}, {"_id": 0}) if order else None
    released = bool(tertahan and sesudah and sesudah.get("status") not in phs.STATUS_SEBELUM_GUDANG
                    and sesudah.get("status") not in DEAD_STATUSES)
    if kirim:   # sama dengan `POST /ar-receipts`: kirim kwitansi WhatsApp bila ada aturan aktif
        try:
            from services import delivery_service as ds
            await ds.dispatch_event("ar_receipt", receipt["id"], "created", ent or None, AKTOR_MUTASI["name"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[F1] kirim kwitansi %s gagal diabaikan: %s", receipt.get("number"), exc)
    try:
        from dependencies import audit
        await audit(AKTOR_MUTASI["name"], "bank_auto_receipt", "bank_statement_line", lid, {
            "line_id": lid, "receipt_id": receipt.get("id", ""), "receipt_number": receipt.get("number", ""),
            "order_id": (order or {}).get("id", ""), "order_number": (order or {}).get("number", ""), "jalur": jalur,
            "pemicu": pemicu, "amount": brs._round(line.get("amount")), "report_id": report_id,
            "released": released}, scope_entity_id=ent)
        if jalur == "B" and report:
            await audit(AKTOR_MUTASI["name"], "payment_report_accepted", "payment_report", report["id"], {
                "number": report.get("number", ""), "order_id": (order or {}).get("id", ""),
                "amount": report.get("amount"), "receipt_number": receipt.get("number", ""), "released": released,
                "auto": True, "source": SUMBER, "bank_line_id": lid}, scope_entity_id=ent)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[F1] jejak audit baris %s gagal: %s", lid, exc)
    if tertahan and sesudah:
        try:
            from services import notification_service as ns
            keadaan = "dilepas" if released else ("tertahan" if phs.ditahan(sesudah) else "admin")
            await ns.notify_bayar_masuk_mutasi(sesudah, amount=brs._round(line.get("amount")),
                                               receipt_number=receipt.get("number", ""), keadaan=keadaan, line_id=lid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[F1] notifikasi sales baris %s gagal: %s", lid, exc)
    return _keluaran(lid, "otomatis", jalur=jalur, receipt=receipt, order=order, kode=KODE_COCOK, alasan=alasan,
                     released=released)


async def _pulihkan(line: Dict[str, Any], receipt: Dict[str, Any], op: str, pemicu: str) -> Dict[str, Any]:
    """Pemulihan (§5.3): kwitansi baris ini sudah lahir (proses sebelumnya terputus sebelum tautan, atau kalah indeks
    unik) → hanya tautkan; tidak ada kwitansi kedua."""
    from services import pay_hold_service as phs
    nomor = receipt.get("number", "")
    if receipt.get("effects_done") is False:
        raise _GagalTindak(f"Kwitansi {nomor} dari mutasi ini belum tuntas dibuat. Tunggu sebentar lalu tekan "
                           "\"Cocokkan otomatis\" lagi.")
    oid = next((a.get("order_id") for a in receipt.get("allocations") or [] if a.get("order_id")), "")
    order = await db.sales_orders.find_one({"id": oid}, {"_id": 0}) if oid else None
    tertahan = phs.ditahan(order)
    try:
        await _tautkan(line, receipt, op, "auto_receipt")
    except Exception as exc:  # noqa: BLE001
        raise _GagalTindak(_kalimat_galat("tautan", exc, nomor)) from exc
    jalur = "B" if receipt.get("payment_report_id") else "C"
    return await _sesudah_tautan(line, jalur=jalur, receipt=receipt, order=order, tertahan=tertahan,
                                 alasan=f"Kwitansi {nomor} yang lahir dari mutasi ini ditautkan (pemulihan)",
                                 pemicu=pemicu)


async def _bertindak(line: Dict[str, Any], h: Dict[str, Any], op: str, pemicu: str) -> Dict[str, Any]:
    """Jalur A/B/C di bawah kunci `op` → hasil otomatis, atau `_GagalTindak` berkalimat."""
    from services import pay_hold_service as phs
    from services import payment_report_service as prs
    jalur, order, report = h["keputusan"], h["order"], h.get("report")
    tertahan = phs.ditahan(order)
    try:
        if jalur == "A":
            receipt = h["receipt"]
        elif jalur == "B":
            out = await prs.terima(report, order, dict(AKTOR_MUTASI), bank_line=line)
            receipt = await db.ar_receipts.find_one({"id": (out.get("report") or {}).get("receipt_id") or ""},
                                                    {"_id": 0})
            if not receipt:
                raise ValueError("kwitansi laporan tidak ditemukan sesudah diterima")
        else:
            receipt = await _kwitansi_c(line, h)
    except Exception as exc:  # noqa: BLE001
        raise _GagalTindak(_kalimat_galat(jalur, exc, (report or {}).get("number", ""))) from exc
    try:
        await _tautkan(line, receipt, op, MATCH_TYPE[jalur])
    except Exception as exc:  # noqa: BLE001
        raise _GagalTindak(_kalimat_galat("tautan", exc, receipt.get("number", ""))) from exc
    return await _sesudah_tautan(line, jalur=jalur, receipt=receipt, order=order, tertahan=tertahan,
                                 alasan=h["alasan"], pemicu=pemicu, report=report, kirim=jalur != "A")


async def _galat(line: Dict[str, Any], op: str, exc: BaseException, pemicu: str, *, pulihkan: bool) -> Dict[str, Any]:
    """Galat saat bertindak → kartu `galat` berkalimat. Bila kwitansi baris ini ternyata sudah lahir dan tuntas
    (galat datang sesudahnya), pemulihan menautkannya lebih dulu — tidak ada kwitansi tanpa tautan yang tertinggal."""
    lid = line["id"]
    alasan = exc.alasan if isinstance(exc, _GagalTindak) else _kalimat_galat("", exc)
    logger.warning("[F1] baris %s → kartu galat: %s", lid, alasan, exc_info=not isinstance(exc, _GagalTindak))
    if pulihkan:
        lama = await _kwitansi_baris(lid)
        if lama and lama.get("effects_done") is not False:
            masih = await db.bank_statement_lines.find_one({"id": lid, "match_lock": op}, {"_id": 1})
            kunci = op if masih else await _klaim(lid)
            if kunci:
                op = kunci
                try:
                    fresh = await db.bank_statement_lines.find_one({"id": lid}, {"_id": 0}) or line
                    return await _pulihkan(fresh, lama, op, pemicu)
                except Exception as err:  # noqa: BLE001
                    alasan = err.alasan if isinstance(err, _GagalTindak) else _kalimat_galat("", err)
    hits = line.get("pay_code_hits") or []
    order_id = (hits[0].get("order_id") or "") if len(hits) == 1 else ""
    await _tulis_kartu(lid, op, _penanda("kartu", kode=KODE_GALAT, alasan=alasan, order_id=order_id))
    return _keluaran(lid, "kartu", kode=KODE_GALAT, alasan=alasan)


async def _proses(line_id: str, pemicu: str) -> Dict[str, Any]:
    line = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0})
    if not line:
        return _keluaran(line_id, "lewati", kode="tidak_ada", alasan="Mutasi tidak ditemukan")
    awal = await nilai_baris(line)
    if awal["keputusan"] == "lewati":
        return _keluaran(line_id, "lewati", kode=awal["alasan_kode"], alasan=awal["alasan"])
    op = await _klaim(line_id)
    if not op:
        return _keluaran(line_id, "lewati", kode=KODE_DIKLAIM, alasan="Mutasi ini sedang diproses pencocokan lain")
    pulihkan = True
    try:
        line = await db.bank_statement_lines.find_one({"id": line_id}, {"_id": 0}) or line
        lama = await _kwitansi_baris(line_id)
        if lama:
            pulihkan = False
            return await _pulihkan(line, lama, op, pemicu)
        h = await nilai_baris(line)   # dinilai ULANG di bawah kunci: keadaan pesanan bisa berubah sejak penilaian awal
        if h["keputusan"] == "lewati":
            await _lepas_kunci(line_id, op)
            return _keluaran(line_id, "lewati", kode=h["alasan_kode"], alasan=h["alasan"])
        if h["keputusan"] == "kartu":
            await _tulis_kartu(line_id, op, _penanda_kartu(h))
            return _keluaran(line_id, "kartu", order=h.get("order"), kode=h["alasan_kode"], alasan=h["alasan"])
        return await _bertindak(line, h, op, pemicu)
    except Exception as exc:  # noqa: BLE001 — satu baris tidak pernah menghentikan batch
        return await _galat(line, op, exc, pemicu, pulihkan=pulihkan)


async def proses_baris(line: Dict[str, Any], pemicu: str) -> Dict[str, Any]:
    """Proses SATU baris mutasi (§5.3): dinilai, lalu kwitansi/laporan/tautan otomatis (jalur A/B/C), kartu beralasan,
    atau dilewati. `pemicu` = siapa/apa yang memicu (pengimpor, tombol "Cocokkan otomatis") — dicatat di jejak.

    → `{line_id, hasil: otomatis|kartu|lewati, jalur: A|B|C|"", receipt_id, receipt_number, order_id, order_number,
    alasan_kode, alasan, released}`. Tidak pernah melempar: galat tak terduga = kartu `galat`."""
    lid = str((line or {}).get("id") or "")
    try:
        return await _proses(lid, pemicu)
    except Exception as exc:  # noqa: BLE001 — pagar terakhir (galat sebelum klaim, mis. saat menilai)
        logger.exception("[F1] baris %s gagal diproses: %s", lid, exc)
        alasan = _kalimat_galat("", exc)
        try:
            await _tulis_kartu(lid, "", _penanda("kartu", kode=KODE_GALAT, alasan=alasan))
        except Exception as err:  # noqa: BLE001
            logger.error("[F1] penanda galat baris %s gagal ditulis: %s", lid, err)
        return _keluaran(lid, "kartu", kode=KODE_GALAT, alasan=alasan)


def _urut(lines: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Tanggal mutasi naik, lalu urutan sisip (`created_at` per baris saat impor; sort stabil untuk yang sama)."""
    return sorted(lines, key=lambda ln: (str(ln.get("stmt_date") or ""), str(ln.get("created_at") or "")))


async def _proses_daftar(lines: List[Dict[str, Any]], pemicu: str) -> Dict[str, Any]:
    rincian = [await proses_baris(ln, pemicu) for ln in _urut(lines)]
    nominal = {ln["id"]: brs._round(ln.get("amount")) for ln in lines}
    otomatis = [r for r in rincian if r["hasil"] == "otomatis"]
    return {"kwitansi_otomatis": len(otomatis), "kartu": sum(1 for r in rincian if r["hasil"] == "kartu"),
            "nilai_otomatis": round(sum(nominal.get(r["line_id"], 0.0) for r in otomatis), 2), "rincian": rincian}


async def proses_impor(import_batch: str, pemicu: str) -> Dict[str, Any]:
    """§5.1 — saat impor: semua baris batch itu (yang berkode, masuk, `unmatched` diproses; sisanya dilewati), urut
    tanggal mutasi naik lalu urutan berkas. Satu ringkasan ke Finance (pemegang `payment_report.decide` di PT baris, per
    orang) bila ada kwitansi otomatis atau kartu. → `{kwitansi_otomatis, kartu, nilai_otomatis, rincian}`."""
    lines = await db.bank_statement_lines.find({"import_batch": import_batch}, {"_id": 0}).to_list(20000) \
        if import_batch else []
    out = await _proses_daftar(lines, pemicu)
    if lines and out["kwitansi_otomatis"] + out["kartu"] > 0:
        try:
            from services import notification_service as ns
            rek = lines[0].get("bank_account_id") or ""
            await ns.notify_ringkasan_mutasi_otomatis(
                entity_id=lines[0].get("entity_id") or "", rekening=(await _nama_rekening(rek)).get(rek, "-"),
                import_batch=import_batch, jumlah=out["kwitansi_otomatis"], nilai=out["nilai_otomatis"],
                kartu=out["kartu"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("[F1] ringkasan impor %s gagal: %s", import_batch, exc)
    return out


async def proses_rekening(bank_account_id: str, entity_ids: Optional[List[str]], pemicu: str) -> Dict[str, Any]:
    """§5.1 — "Cocokkan otomatis": baris masuk `unmatched` berkode di rekening itu (dalam cakupan PT pengguna) yang
    belum pernah diproses atau berstatus kartu. Baris yang dilewati penilai (pernah otomatis, kwitansi otomatisnya
    dibatalkan, diimpor sebelum waktu aktif, sedang diklaim proses lain) tidak disentuh dan tidak masuk `rincian`. Tanpa
    ringkasan Finance (layar menampilkan jumlahnya). → bentuk sama dengan `proses_impor`."""
    await brs._account(bank_account_id, entity_ids)   # 403 untuk rekening PT lain
    lines = await db.bank_statement_lines.find(
        {"bank_account_id": bank_account_id, "status": "unmatched", "direction": "in",
         "pay_code_hits.0": {"$exists": True}, **brs._scope_q(entity_ids)}, {"_id": 0}).to_list(20000)
    out = await _proses_daftar(lines, pemicu)
    out["rincian"] = [r for r in out["rincian"] if r["hasil"] != "lewati"]
    return out
