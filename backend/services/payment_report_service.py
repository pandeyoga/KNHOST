"""Lapor Bayar CBD & DP (LB-T1, LB-T3, LB-T4) — layanan laporan bayar pelanggan.

Laporan bayar = sales/admin sales memberi tahu Finance bahwa pelanggan sudah membayar (bukti terlampir). Finance menerima
(lewat `ar_receipt_service.create_receipt`, satu-satunya pintu kas) atau menolak. Modul ini: konstanta status, penomoran,
bentuk tampil, pembuatan laporan (Tugas 3), dan keputusan terima/tolak (Tugas 4).

MESIN STATUS LAPORAN (LB-T4)
============================
    menunggu ──terima (klaim CAS)──→ memproses ──kwitansi tuntas──→ diterima
       ▲                                │
       └────── kwitansi gagal ──────────┘   (galat asli diteruskan; riwayat mencatat "Terima gagal: …")
    menunggu ──tolak (CAS, alasan ≥ 5 huruf)──→ ditolak
    memproses (klaim lebih tua dari KLAIM_BASI_MENIT) ──terima──→ memproses (klaim diambil alih) → …

* `memproses` = status SEMENTARA milik satu pemanggil (`claim.token`). Dua Terima bersamaan: hanya satu yang lolos CAS,
  yang lain 409 → tepat satu kwitansi (Review Focus 1).
* Kwitansi membawa rujukan balik (`source: "payment_report"`, `payment_report_id`), UNIK di basis data
  (`ar_receipts.uq_payment_report`, indeks wajib parsial): satu laporan = satu kwitansi walau klaim basi diambil alih
  dari proses yang masih hidup (yang kalah kena `DuplicateKeyError` → rollback `create_receipt`). Setiap klaim mencari
  kwitansi itu dulu: ada dan tuntas (`effects_done`) → laporan diselesaikan dengan kwitansi itu; ada tetapi setengah jadi
  → 409 (sementara), laporan tetap `memproses`.
* Gagal dan TIDAK ada kwitansi laporan ini (tidak lahir / dicabut rollback G3 V3-AR-01) → kembali `menunggu`, galat asli
  diteruskan (status & pesan utuh, Review Focus 2). Ada kwitansi tuntas + galat langkah turunan → `diterima` dengan
  kwitansi itu. Ada kwitansi (setengah jadi, atau tuntas tetapi penghentian paksa) → tetap `memproses`: laporan
  berkwitansi tidak pernah kembali bisa ditolak (tolak juga menolak laporan yang sudah berkwitansi).
* Sebelum klaim (tanpa tulisan): lampiran ≥ 1, pesanan hidup, nominal ≤ sisa tagihan pesanan (R10-b).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import math
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from core_utils import new_id, next_doc_number, now_iso
from db import db
from services import status_history

logger = logging.getLogger(__name__)

MENUNGGU = "menunggu"
MEMPROSES = "memproses"
DITERIMA = "diterima"
DITOLAK = "ditolak"

#: Klaim `memproses` yang lebih tua dari ini dianggap ditinggal proses yang mati (kwitansi normal selesai < 1 detik) dan
#: boleh diambil alih oleh Terima berikutnya. Sama dengan `bank_recon_service.MATCH_LOCK_STALE_MINUTES` (PK-21). Proses
#: yang masih hidup tetapi macet lebih lama BISA disalip; kwitansi keduanya ditolak indeks unik `uq_payment_report`.
KLAIM_BASI_MENIT = 10
ALASAN_MIN = 5

PESAN_TANPA_BUKTI = "Lampirkan bukti bayar dulu"
PESAN_LEBIH_SISA = ("Nominal melebihi sisa tagihan pesanan ({sisa}). Kelebihan bayar dicatat Finance lewat kwitansi + "
                    "keputusan selisih.")
PESAN_BERJATUH_TEMPO = ("Lapor bayar tidak untuk {nama} (cara bayar berjatuh tempo). Serahkan ke Finance untuk dicatat "
                        "sebagai kwitansi ber-jatuh tempo.")
PESAN_SUDAH_BERKWITANSI = "Laporan ini sudah punya kwitansi {nomor} — tidak bisa ditolak."
PESAN_KEMBAR = ("Kwitansi tidak jadi dibuat karena bentrok dengan data yang sudah ada. Muat ulang laporan ini lalu coba "
                "lagi; bila berulang, minta admin memeriksanya.")
PESAN_PESANAN_MATI = "Pesanan sudah batal/kedaluwarsa — tolak laporan ini"
PESAN_ALASAN = f"Alasan tolak wajib diisi (min. {ALASAN_MIN} huruf)."
PESAN_DIPROSES = "Laporan ini sedang diproses Finance lain. Tunggu sebentar lalu muat ulang."
PESAN_SUDAH = {DITERIMA: "Laporan ini sudah diterima.", DITOLAK: "Laporan ini sudah ditolak."}
PESAN_SETENGAH = ("Kwitansi {nomor} dari laporan ini belum tuntas. Tunggu sebentar lalu muat ulang; bila beberapa menit "
                  "kemudian masih begini, minta admin memeriksa kwitansi itu.")
#: Header PK-12: jawaban 4xx untuk keadaan SEMENTARA tidak disimpan penyimpan idempotensi (kirim ulang dijalankan lagi).
HEADER_ULANG = {"X-Idempotency-Retry": "true"}

#: Isian internal yang tidak pernah dikirim ke layar (kunci idempotensi dan klaim atomik).
_INTERNAL = ("_id", "idem_key", "claim")


async def next_number(entity_id: str) -> str:
    """Nomor laporan `LB-…` lewat penomoran baku dokumen (format & cara per PT dari tabel Penomoran Dokumen)."""
    return await next_doc_number("payment_reports", "number", "LB-", entity_id=entity_id)


def tampil(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Salinan dokumen untuk layar: tanpa `_id`, isian internal, dan `storage_path` lampiran (jalur penyimpanan tidak
    pernah keluar; berkas diambil lewat rute unduh yang berpagar)."""
    out = {k: v for k, v in (doc or {}).items() if k not in _INTERNAL}
    lampiran = [{k: v for k, v in a.items() if k != "storage_path"}
                for a in (out.get("attachments") or []) if not a.get("is_deleted")]
    out["attachments"] = lampiran
    out["attachment_count"] = len(lampiran)
    return out


async def _perlu_bayar(order: Dict[str, Any]) -> bool:
    """Pesanan sedang menunggu bayar: tahan aktif, atau gerbang bayar masih menunjukkan kekurangan (mis. DP sudah masuk,
    pelunasan sebelum surat jalan belum). Keduanya dari `pay_hold_service` / `dispatch_payment_gate` — tanpa hitungan
    kedua."""
    from services import dispatch_payment_gate as gate
    from services import pay_hold_service as phs
    if order.get("pay_hold") or await phs.blocked(order):
        return True
    st = await gate.evaluate(order)
    return bool(st.get("applies")) and float(st.get("shortfall") or 0) > 0


def sisa_tagihan(order: Dict[str, Any]) -> float:
    """Sisa tagihan pesanan = nilai tagihan (grand total + tagihan tambahan nota debit) − Σ pembayaran: pengertian yang
    sama dengan pemeriksa alokasi kwitansi (`ar_allocation_service.validate_targets`) dan nilai gerbang bayar."""
    from services.customer_service import _order_grand_total, _order_paid
    return round(_order_grand_total(order) - _order_paid(order), 2)


def _periksa_sisa(order: Dict[str, Any], amount: float) -> None:
    """LB-T4 (R10-b) — 409 pemandu bila nominal laporan melebihi sisa tagihan pesanan (laporan ganda / salah ketik;
    kelebihan bayar sungguhan dicatat Finance lewat kwitansi + keputusan selisih, bukan lewat Terima)."""
    from core_utils import rupiah
    sisa = sisa_tagihan(order)
    if amount > sisa + 0.01:
        raise HTTPException(status_code=409, detail=PESAN_LEBIH_SISA.format(sisa=rupiah(max(sisa, 0.0))))


async def create_report(order: Dict[str, Any], payload: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Buat laporan bayar `menunggu` untuk satu pesanan. Semua pemeriksaan DI SINI sebelum menulis apa pun; galat berkalimat
    (HTTPException). Pagar PT/pemilik/izin milik router."""
    from services import payment_method_service as pms
    from services.bank_account_change_service import daftar_penerima
    from services.customer_service import DEAD_STATUSES

    entity_id = order.get("entity_id") or ""
    if order.get("status") in DEAD_STATUSES:
        raise HTTPException(status_code=409, detail="Pesanan ini sudah tidak aktif")
    if not await _perlu_bayar(order):
        raise HTTPException(status_code=409, detail="Pesanan ini tidak menunggu bayar")
    try:
        amount = float(payload.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    if not math.isfinite(amount) or amount <= 0:
        raise HTTPException(status_code=400, detail="Nominal harus lebih dari nol")
    _periksa_sisa(order, amount)   # LB-T4 (R10-b) — nominal di atas sisa tagihan pesanan tidak diterima
    try:
        tgl = date.fromisoformat(str(payload.get("transfer_date") or "")[:10]).isoformat()
    except ValueError:
        raise HTTPException(status_code=400, detail="Tanggal transfer tidak sah (format YYYY-MM-DD)") from None
    # cara bayar: dari master PT, bukan tunai (uang tunai tidak punya bukti transfer; masuk lewat kasir/kas)
    try:
        cara = await pms.wajib(entity_id, str(payload.get("method") or ""), arah="masuk")
    except pms.CaraBayarError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kode = cara["code"]
    if await pms.is_cash(entity_id, kode):
        raise HTTPException(status_code=400, detail="Lapor bayar hanya untuk pembayaran non-tunai")
    if cara.get("needs_due_date"):
        # LB-T4 (R10-a) — cara bayar berjatuh tempo (giro/cek) belum menjadi uang saat dilaporkan: dicatat Finance
        # sebagai kwitansi ber-jatuh tempo, bukan lewat Lapor bayar.
        raise HTTPException(status_code=400, detail=PESAN_BERJATUH_TEMPO.format(nama=cara.get("name") or kode))
    rekening = next((a for a in await daftar_penerima(entity_id, kode) if a["id"] == payload.get("account_id")), None)
    if not rekening:
        raise HTTPException(status_code=400, detail="Rekening tujuan bukan rekening penerimaan PT pesanan ini")
    # LB-T4 (R10-a) — aturan isian uang masuk yang SAMA dengan kwitansi (satu pemeriksa, `ar_receipt_service`): nomor
    # referensi wajib bila PT memintanya; rekening ≠ rekening instruksi bayar pesanan → pelapor menulis alasannya (B7
    # tetap boleh memilih rekening penerimaan PT mana pun; alasannya tercatat dan ikut ke kwitansi saat Terima).
    from services import ar_receipt_service as ars
    syarat = await ars.syarat_uang_masuk(entity_id=entity_id, cara=cara, account_id=rekening["id"], orders=[order],
                                         reference_no=str(payload.get("reference_no") or ""),
                                         mismatch_note=str(payload.get("mismatch_note") or ""))
    if await db.payment_reports.find_one({"order_id": order["id"], "status": MENUNGGU, "amount": amount,
                                          "transfer_date": tgl}, {"_id": 1}):
        raise HTTPException(status_code=409, detail="Laporan yang sama masih menunggu dicek")
    now = now_iso()
    doc = {
        "id": new_id("lb"), "number": await next_number(entity_id), "entity_id": entity_id,
        "order_id": order["id"], "order_number": order.get("number", ""),
        "customer_id": order.get("customer_id", ""), "customer_name": order.get("customer_name", ""),
        "amount": amount, "transfer_date": tgl, "method": kode,
        "account_id": rekening["id"], "account_name": rekening.get("name", ""),
        "reference_no": str(payload.get("reference_no") or "").strip()[:100],
        "note": str(payload.get("note") or "").strip()[:500],
        "instruction_mismatch": bool(syarat["instruction_mismatch"]), "mismatch_note": syarat["mismatch_note"],
        "status": MENUNGGU, "attachments": [],
        "created_by": actor.get("id", ""), "created_by_name": actor.get("name", ""),
        "created_at": now, "updated_at": now,
        "status_history": [status_history.entry(MENUNGGU, user=actor.get("name", ""), note="Laporan dibuat")],
    }
    await db.payment_reports.insert_one(dict(doc))
    await _beritahu_finance(doc)
    return tampil(doc)


async def _beritahu_finance(doc: Dict[str, Any]) -> None:
    """Notifikasi `lapor_bayar_masuk` ke pemegang izin `payment_report.decide` di PT pesanan (satu per orang)."""
    from services import notification_service as ns
    from core_utils import rupiah
    await ns.create_addressed(
        permission=("payment_report", "decide"), notif_type="lapor_bayar_masuk",
        title=f"Lapor bayar masuk — {doc['order_number']}",
        body=f"{doc['customer_name']} melaporkan bayar {rupiah(doc['amount'])} ({doc['number']}). Cek bukti dan putuskan.",
        severity="info", link=f"/?view=orders&id={doc['order_id']}", entity_id=doc["entity_id"] or None,
        ref=doc["id"])


async def add_attachment(report: Dict[str, Any], att: Dict[str, Any]) -> Dict[str, Any]:
    """Tambah lampiran ke laporan yang masih `menunggu` (klaim atomik pada status). Kembalian = lampiran tanpa jalur
    penyimpanan."""
    res = await db.payment_reports.update_one(
        {"id": report["id"], "status": MENUNGGU},
        {"$push": {"attachments": att}, "$set": {"updated_at": now_iso()}})
    if not res.matched_count:
        raise HTTPException(status_code=409, detail="Laporan sudah diputus; lampiran tidak bisa ditambah")
    return {k: v for k, v in att.items() if k != "storage_path"}


async def list_for_order(order_id: str) -> List[Dict[str, Any]]:
    rows = await db.payment_reports.find({"order_id": order_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [tampil(r) for r in rows]


# ── LB-T4 — keputusan Finance: terima / tolak ────────────────────────────────────────────────────────────────────────
def _lampiran(report: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [a for a in (report.get("attachments") or []) if not a.get("is_deleted")]


def _basi_sebelum() -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=KLAIM_BASI_MENIT)).isoformat()


def _galat_status(status: Optional[str]) -> HTTPException:
    """409 untuk laporan yang tidak (lagi) bisa diputus. `memproses` = keadaan sementara (header kirim ulang)."""
    if status == MEMPROSES:
        return HTTPException(status_code=409, detail=PESAN_DIPROSES, headers=dict(HEADER_ULANG))
    return HTTPException(status_code=409, detail=PESAN_SUDAH.get(status or "", "Laporan ini sudah diputus."))


def _pelaku(actor: Dict[str, Any]) -> Dict[str, str]:
    return {"id": str(actor.get("id") or ""), "name": str(actor.get("name") or "")}


async def _kwitansi_laporan(report_id: str) -> Optional[Dict[str, Any]]:
    """Kwitansi hidup (`posted`, belum batal) yang lahir dari laporan ini — rujukan balik `payment_report_id`. Saringan
    sama dengan indeks unik parsial `ar_receipts.uq_payment_report`."""
    return await db.ar_receipts.find_one({"payment_report_id": report_id, "status": "posted"}, {"_id": 0})


def isi_kwitansi(report: Dict[str, Any], order: Dict[str, Any]) -> Dict[str, Any]:
    """Isian `create_receipt` dari laporan: kwitansi AR biasa (jurnal uang muka/piutang menurut pesanan), bertanggal
    transfer, ke rekening & cara bayar yang dilaporkan, bukti = lampiran pertama (rute unduh berpagar), dialokasikan
    penuh ke pesanan laporan. `payment_report_id`/`payment_report_number` = rujukan balik (isian opsional kwitansi)."""
    att0 = _lampiran(report)[0]
    return {
        "customer_id": report.get("customer_id") or order.get("customer_id") or "",
        "entity_id": report.get("entity_id") or order.get("entity_id") or "",
        "amount": float(report.get("amount") or 0),
        "method": report.get("method") or "",
        "account_id": report.get("account_id") or "",
        "receipt_date": report.get("transfer_date") or "",
        "reference_no": report.get("reference_no") or "",
        "proof_url": f"/api/payment-reports/{report['id']}/attachments/{att0['id']}",
        "allocations": [{"order_id": order["id"], "amount": float(report.get("amount") or 0)}],
        "notes": f"Lapor bayar {report.get('number', '')}".strip(),
        # R10-a — alasan pelapor bila rekening ≠ rekening instruksi bayar pesanan (diperiksa ulang `create_receipt`)
        "mismatch_note": report.get("mismatch_note") or "",
        "payment_report_id": report["id"],
        "payment_report_number": report.get("number", ""),
    }


async def _klaim(report_id: str, actor: Dict[str, Any]) -> tuple:
    """CAS `menunggu` (atau `memproses` basi) → `memproses` ber-token. Kalah → 409 sesuai status sekarang."""
    token = new_id("klaim")
    now = now_iso()
    rep = await db.payment_reports.find_one_and_update(
        {"id": report_id, "$or": [{"status": MENUNGGU},
                                  {"status": MEMPROSES, "claim.at": {"$lt": _basi_sebelum()}}]},
        {"$set": {"status": MEMPROSES, "updated_at": now,
                  "claim": {"token": token, "by": _pelaku(actor)["id"], "by_name": _pelaku(actor)["name"], "at": now}}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not rep:
        cur = await db.payment_reports.find_one({"id": report_id}, {"_id": 0, "status": 1}) or {}
        raise _galat_status(cur.get("status"))
    return rep, token


async def _selesai_diterima(report_id: str, token: str, receipt: Dict[str, Any],
                            actor: Dict[str, Any]) -> Dict[str, Any]:
    """Tulisan akhir: `memproses` (klaim milik pemanggil) → `diterima` + kwitansi + riwayat; klaim dicabut."""
    p = _pelaku(actor)
    now = now_iso()
    doc = await db.payment_reports.find_one_and_update(
        {"id": report_id, "status": MEMPROSES, "claim.token": token},
        {"$set": {"status": DITERIMA, "receipt_id": receipt.get("id", ""), "receipt_number": receipt.get("number", ""),
                  "decided_by": p["id"], "decided_by_name": p["name"], "decided_at": now, "updated_at": now},
         "$unset": {"claim": ""},
         "$push": {"status_history": status_history.entry(DITERIMA, user=p["name"],
                                                          note=f"Kwitansi {receipt.get('number', '')}")}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not doc:
        # Klaim diambil alih proses lain (lewat KLAIM_BASI_MENIT): ia menemukan kwitansi ini lewat rujukan balik dan
        # menyelesaikan laporan — tidak ada kwitansi kedua. Pemanggil ini TIDAK melaporkan sukses dan tidak mengirim
        # notifikasi/jejak (pemenang yang melakukannya): 409 dengan keadaan sebenarnya.
        logger.error("[payment_report] klaim %s atas laporan %s hilang sebelum selesai; kwitansi %s tetap sah",
                     token, report_id, receipt.get("number"))
        cur = await db.payment_reports.find_one({"id": report_id}, {"_id": 0, "status": 1}) or {}
        raise _galat_status(cur.get("status") if cur.get("status") in (DITERIMA, DITOLAK) else MEMPROSES)
    return doc


async def _kembali_menunggu(report_id: str, token: str, actor: Dict[str, Any], exc: BaseException) -> None:
    """Kwitansi gagal → laporan kembali `menunggu` (hanya bila klaim masih milik pemanggil). Tidak pernah melempar: galat
    asli yang diteruskan."""
    pesan = str(getattr(exc, "detail", "") or exc or exc.__class__.__name__)
    if isinstance(getattr(exc, "detail", None), dict):
        pesan = str(exc.detail.get("message") or exc.detail)
    try:
        await db.payment_reports.update_one(
            {"id": report_id, "status": MEMPROSES, "claim.token": token},
            {"$set": {"status": MENUNGGU, "updated_at": now_iso()}, "$unset": {"claim": ""},
             "$push": {"status_history": status_history.entry(MENUNGGU, user=_pelaku(actor)["name"],
                                                              note=f"Terima gagal: {pesan[:300]}")}})
    except Exception as err:  # noqa: BLE001
        logger.error("[payment_report] laporan %s gagal dikembalikan ke menunggu: %s", report_id, err)


async def _lepas(order_id: str, actor: Dict[str, Any]) -> bool:
    """Buka tahan + lepas otomatis untuk jalur pemulihan (kwitansi lama dipakai ulang). Efek samping: tidak melempar."""
    try:
        from services import pay_hold_service as phs
        return await phs.clear_if_paid(order_id, actor, why="lapor bayar diterima")
    except Exception as err:  # noqa: BLE001
        logger.warning("[payment_report] buka tahan %s gagal: %s", order_id, err)
        return False


async def _menunggu_bank(order_id: str) -> bool:
    """§7-5 — dasar `terverifikasi` dan pesanan masih tertahan sesudah kwitansi: menunggu cocok mutasi bank."""
    from services import dispatch_payment_gate as gate
    from services import pay_hold_service as phs
    so = await db.sales_orders.find_one({"id": order_id}, {"_id": 0})
    if not so:
        return False
    st = await gate.evaluate(so)
    return st.get("basis") == "terverifikasi" and await phs.blocked(so)


async def _beritahu_putusan(report: Dict[str, Any], order: Dict[str, Any], jenis: str, title: str, body: str) -> None:
    """Notifikasi ke pelapor + sales pemilik pesanan (per orang, `create_addressed`). Efek samping: tidak melempar."""
    from services import notification_service as ns
    orang = tuple(dict.fromkeys(x for x in (report.get("created_by"), order.get("sales_id"),
                                            order.get("assigned_sales_id")) if x))
    try:
        await ns.create_addressed(also_users=orang, notif_type=jenis, title=title, body=body, severity="info",
                                  link=f"/?view=orders&id={order.get('id', '')}",
                                  entity_id=report.get("entity_id") or None, ref=report["id"])
    except Exception as err:  # noqa: BLE001
        logger.warning("[payment_report] notifikasi %s laporan %s gagal: %s", jenis, report.get("id"), err)


async def terima(report: Dict[str, Any], order: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Finance menerima laporan: kwitansi AR lewat `create_receipt` (pintu kas satu-satunya; pencatat = Finance, jadi
    pagar B3 tidak menghalanginya), tahan bayar dibuka + lepas otomatis (di dalam `create_receipt`, R5), notifikasi.

    → `{report, receipt_number, released, waiting_bank}`. `released` = pesanan dilepas ke gudang oleh Terima ini;
    `waiting_bank` = PT berdasar `terverifikasi` dan pesanan masih tertahan (kwitansi belum cocok mutasi bank).
    Pagar izin/PT/pemilik milik router."""
    from services import ar_receipt_service as ars
    from services.customer_service import DEAD_STATUSES
    if report.get("status") in (DITERIMA, DITOLAK):
        raise _galat_status(report.get("status"))
    if report.get("status") == MEMPROSES and str((report.get("claim") or {}).get("at") or "") >= _basi_sebelum():
        raise _galat_status(MEMPROSES)   # klik kedua selagi Terima pertama berjalan: "sedang diproses", bukan sisa Rp 0
    if not _lampiran(report):
        # keadaan sementara (pelapor bisa melampirkan bukti): kirim ulang kunci sama dijalankan lagi (Minor-3)
        raise HTTPException(status_code=409, detail=PESAN_TANPA_BUKTI, headers=dict(HEADER_ULANG))
    if order.get("status") in DEAD_STATUSES:
        raise HTTPException(status_code=409, detail=PESAN_PESANAN_MATI)
    if not await _kwitansi_laporan(report["id"]):   # pemulihan (kwitansi sudah ada) sudah tercatat di sisa tagihan
        _periksa_sisa(order, float(report.get("amount") or 0))   # R10-b — sebelum klaim, tanpa tulisan
    rep, token = await _klaim(report["id"], actor)
    lama = await _kwitansi_laporan(rep["id"])
    if lama and lama.get("effects_done") is False:
        # Kwitansi setengah jadi (proses lain sedang membuatnya, atau mati di tengah): jangan menerbitkan yang kedua.
        # Laporan tetap `memproses` (klaim ini basi lagi sesudah KLAIM_BASI_MENIT; tidak bisa ditolak).
        raise HTTPException(status_code=409, detail=PESAN_SETENGAH.format(nomor=lama.get("number", "")),
                            headers=dict(HEADER_ULANG))
    released = False
    if lama:
        receipt = lama   # pemulihan: proses sebelumnya mati sesudah kwitansi tuntas
        released = await _lepas(order["id"], actor)
    else:
        try:
            receipt = await ars.create_receipt(isi_kwitansi(rep, order), actor)
            released = order["id"] in (receipt.get("released_order_ids") or [])
        except BaseException as exc:
            try:
                tuntas = await _kwitansi_laporan(rep["id"])
            except Exception as err:  # noqa: BLE001 — galat asli yang diteruskan
                logger.error("[payment_report] kwitansi laporan %s tidak bisa diperiksa: %s", rep["id"], err)
                tuntas = None
            if tuntas is None:
                # Kwitansi tidak pernah lahir / sudah dicabut rollback `create_receipt`: laporan kembali `menunggu`.
                await _kembali_menunggu(rep["id"], token, actor, exc)
                if isinstance(exc, DuplicateKeyError):   # R11 — data kembar (indeks unik) → 409 pemandu, bukan 500
                    raise HTTPException(status_code=409, detail=PESAN_KEMBAR, headers=dict(HEADER_ULANG)) from exc
                if isinstance(exc, HTTPException):
                    exc.headers = {**(exc.headers or {}), **HEADER_ULANG}   # laporan bisa diterima lagi: bukan putusan
                raise
            if not (isinstance(exc, Exception) and tuntas.get("effects_done")):
                # Kwitansi laporan ini ADA tetapi belum tuntas (proses lain sedang membuatnya — indeks unik
                # `uq_payment_report` menolak kwitansi kedua — atau rollback gagal), atau penghentian paksa sesudah
                # kwitansi tuntas: laporan TIDAK dikembalikan ke `menunggu` (tidak bisa ditolak / diterima dua kali);
                # tetap `memproses` sampai Terima berikutnya sesudah klaim basi memakai kwitansi itu.
                logger.error("[payment_report] Terima laporan %s terhenti dengan kwitansi %s (tuntas=%s): %s",
                             rep["id"], tuntas.get("number"), tuntas.get("effects_done"), exc)
                if isinstance(exc, Exception) and not tuntas.get("effects_done"):
                    raise HTTPException(status_code=409, detail=PESAN_SETENGAH.format(nomor=tuntas.get("number", "")),
                                        headers=dict(HEADER_ULANG)) from exc
                raise
            # Galat datang SESUDAH kwitansi tuntas (langkah turunan): uangnya sah, laporan diterima dengan kwitansi itu.
            logger.error("[payment_report] galat sesudah kwitansi %s tuntas (laporan %s): %s",
                         tuntas.get("number"), rep["id"], exc)
            receipt = tuntas
            released = await _lepas(order["id"], actor)
    doc = await _selesai_diterima(rep["id"], token, receipt, actor)
    from core_utils import rupiah
    await _beritahu_putusan(doc or rep, order, "lapor_bayar_diterima",
                            f"Lapor bayar diterima — {rep.get('order_number', '')}",
                            f"{rep.get('number', '')} {rupiah(rep.get('amount') or 0)} diterima Finance; kwitansi "
                            f"{receipt.get('number', '')}.")
    return {"report": tampil(doc), "receipt_number": receipt.get("number", ""), "released": bool(released),
            "waiting_bank": await _menunggu_bank(order["id"])}


async def tolak(report: Dict[str, Any], order: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    """Finance menolak laporan (alasan ≥ 5 huruf): CAS `menunggu` → `ditolak`, tanpa uang. Pesanan mati boleh ditolak.
    Sales diberi tahu alasannya dan boleh melapor ulang."""
    alasan = str(reason or "").strip()
    if len(alasan) < ALASAN_MIN:
        raise HTTPException(status_code=400, detail=PESAN_ALASAN)
    alasan = alasan[:500]
    kw = await _kwitansi_laporan(report["id"])
    if kw:   # Minor-1 — uang laporan ini sudah dibukukan: tolak tidak boleh membuka jalan ke kwitansi kedua
        raise HTTPException(status_code=409, detail=PESAN_SUDAH_BERKWITANSI.format(nomor=kw.get("number", "")))
    p = _pelaku(actor)
    now = now_iso()
    doc = await db.payment_reports.find_one_and_update(
        {"id": report["id"], "status": MENUNGGU},
        {"$set": {"status": DITOLAK, "reason": alasan, "decided_by": p["id"], "decided_by_name": p["name"],
                  "decided_at": now, "updated_at": now},
         "$push": {"status_history": status_history.entry(DITOLAK, user=p["name"], note=alasan)}},
        projection={"_id": 0}, return_document=ReturnDocument.AFTER)
    if not doc:
        cur = await db.payment_reports.find_one({"id": report["id"]}, {"_id": 0, "status": 1}) or {}
        raise _galat_status(cur.get("status"))
    from core_utils import rupiah
    await _beritahu_putusan(doc, order, "lapor_bayar_ditolak",
                            f"Lapor bayar ditolak — {doc.get('order_number', '')}",
                            f"{doc.get('number', '')} {rupiah(doc.get('amount') or 0)} ditolak Finance: {alasan}. "
                            "Periksa lalu lapor ulang bila perlu.")
    return tampil(doc)
