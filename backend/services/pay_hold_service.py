"""Lapor Bayar CBD & DP — tahan bayar SEBELUM gudang (rancangan
`docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md` §5.1–§5.3, keputusan pemilik B1/B6).

KENAPA
======
Dulu pesanan CBD / bagian DP baru ditahan di surat jalan (`dispatch_payment_gate.guard`): gudang sudah mengambil dan
menyiapkan barang yang belum dibayar. Kini pesanan yang wajib bayar dulu BERHENTI di tahap "Bayar dicek Finance", di
antara "Disetujui" dan "Dilepas ke gudang".

ATURAN
======
* **Satu hitungan.** "Wajib bayar dulu" dan jumlahnya HANYA dari `dispatch_payment_gate.evaluate` (termin
  `dp_percent`, `type: cash` + `finance.tahan_kirim_tunai`, `pay_before_ship`, `is_sample` dikecualikan,
  `finance.dispatch_payment_gate = off` mematikan, dasar `finance.tahan_kirim_dasar_bayar`). Gerbang gudang dan gerbang
  surat jalan tidak pernah berbeda pendapat. Pesanan sample (`order_type: sample`) punya gerbang bayarnya sendiri di Meja
  Sample — tidak ditahan di sini.
* **Penanda, bukan status.** Pesanan tetap `approved` dengan `pay_hold = {since, due_at, required, basis}`; sub-status
  `menunggu_bayar` (`so_status`). Penanda hanya berarti selama status `approved`.
* **Mulai** (`start`) saat pesanan mencapai `approved` (ajukan otomatis, keputusan ACC, lanjut harga normal) dan sebagai
  cadangan di `confirm_core` sebelum menolak konfirmasi. Kode bayar ikut lahir (`payment_code_service.ensure_for_order`,
  B1: invoice berkode sejak disetujui). Idempoten: `since`/`due_at` tidak pernah ditimpa.
* **Dibuka** (`clear_if_paid`) begitu `evaluate` tidak lagi menahan — uang cukup (kwitansi dari Lapor Bayar yang
  diterima Finance, Tugas 4) atau pengecualian berizin "kirim tanpa lunas" (`dispatch_payment_gate.release`, B6). Lalu
  jalur lepas otomatis yang sama dengan sesudah ACC (`so_release_service.auto_release`).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from core_utils import now_iso, safe_doc
from db import db

logger = logging.getLogger(__name__)

PESAN_MENUNGGU_BAYAR = "Menunggu pembayaran dicek Finance — lapor bayar di rincian pesanan."
AKTOR_SISTEM = {"id": "", "name": "Sistem", "role": "system"}


class MenungguBayar(HTTPException):
    """409 pemandu dari `confirm_core` untuk pesanan yang wajib bayar dulu dan belum dibayar. Kelas sendiri supaya
    "Periksa & lepas" (`so_release_service.try_release`) bisa menangkapnya tanpa menelan 409 lain (kredit,
    verifikasi)."""

    def __init__(self) -> None:
        super().__init__(status_code=409, detail=PESAN_MENUNGGU_BAYAR)


async def due_at(entity_id: Optional[str], start: Optional[datetime] = None) -> datetime:
    """Kapan tahan bayar pesanan di PT `entity_id` jatuh tempo: `start` (bawaan sekarang) + `sales.batas_bayar_hari`
    (per PT, bawaan 3 hari). Satu-satunya pembaca pengaturan itu — layar tidak menghitung sendiri."""
    from services.nilai_pengaturan import nilai
    hari = int(await nilai("sales.batas_bayar_hari", entity_id))
    return (start or datetime.now(timezone.utc)) + timedelta(days=hari)


async def tenggang_sesudah_putusan(entity_id: Optional[str]) -> timedelta:
    """R18-c — tenggang sesudah Finance memutus laporan bayar pada pesanan yang batasnya sudah lewat:
    `sales.tenggang_sesudah_putusan_jam` (per PT, bawaan 24 jam). Satu-satunya pembaca pengaturan itu."""
    from services.nilai_pengaturan import nilai
    jam = int(await nilai("sales.tenggang_sesudah_putusan_jam", entity_id))
    return timedelta(hours=jam)


def _waktu(iso: Any) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


async def _muat(order_id: str) -> Dict[str, Any]:
    return safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0})) or {}


async def _segarkan_tahap(order_id: str) -> Dict[str, Any]:
    """`stage`/`sub_status` tersimpan mengikuti penanda (preseden `credit_gate._segarkan_tahap`)."""
    from services.so_status import stage_fields
    so = await _muat(order_id)
    if so:
        sf = stage_fields(so)
        await db.sales_orders.update_one({"id": order_id}, {"$set": sf})
        so.update(sf)
    return so


async def _status_gerbang(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Status `dispatch_payment_gate.evaluate` untuk pesanan yang bisa ditahan di gudang; `None` = di luar cakupan:
    pesanan sample (gerbang bayar Meja Sample) dan — ketetapan R6 — SO dari Pesanan Khusus (`source_special_order_id`):
    SO itu menunggu produksi berminggu-minggu di `approved` (penyapu batas bayar tidak boleh mengedarluwarsakannya) dan
    dilepas ke gudang oleh jalur OD sendiri; gerbang surat jalan tetap menjaganya seperti dulu."""
    if not order or order.get("order_type") == "sample" or order.get("source_special_order_id"):
        return None
    from services import dispatch_payment_gate as gate
    return await gate.evaluate(order)


async def status_wajib_bayar(order: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Status gerbang untuk LAYAR (Perjalanan): sama dengan yang dipakai `start`/`blocked` — `None` = pesanan di luar
    cakupan (sample, SO pesanan khusus). Layar tidak menghitung "wajib bayar" sendiri."""
    return await _status_gerbang(order or {})


async def persen_kode(order: Dict[str, Any]) -> Optional[float]:
    """Persen kode bayar tingkat pesanan dari gerbang (`evaluate.dp_percent`, termasuk K-27 dan tunai ditahan) bila
    gerbang berlaku untuk pesanan ini; `None` = biarkan `payment_code_service` memakai persen termin (PM-T2)."""
    st = await _status_gerbang(order)
    return float(st["dp_percent"]) if st and st["applies"] else None


async def blocked(order: Dict[str, Any]) -> bool:
    """Benar bila pesanan wajib bayar dulu, bagian wajibnya belum terbayar, dan tidak ada pengecualian berizin."""
    st = await _status_gerbang(order)
    return bool(st and st["applies"] and st["blocked"])


async def start(order: Dict[str, Any], actor: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Mulai tahan bayar untuk pesanan `approved` yang wajib bayar dulu: tulis `pay_hold`, segarkan sub-status,
    lahirkan kode bayar tingkat pesanan. Idempoten — penanda yang sudah ada hanya diperbarui `required`/`basis`-nya
    (nilai pesanan bisa berubah lewat override), `since`/`due_at` tetap. Kembalian = `pay_hold` tersimpan, atau `None`
    bila tidak ditahan."""
    oid = (order or {}).get("id")
    if not oid:
        return None
    so = await _muat(oid)   # baca ulang: pemanggil bisa membawa potret sebelum transisi
    if so.get("status") != "approved":
        return None
    st = await _status_gerbang(so)
    if not (st and st["applies"] and st["blocked"]):
        return None
    mulai = datetime.now(timezone.utc)
    hold = {"since": mulai.isoformat(), "due_at": (await due_at(so.get("entity_id"), mulai)).isoformat(),
            "required": st["required"], "basis": st["basis"]}
    res = await db.sales_orders.update_one(
        {"id": oid, "status": "approved", "$or": [{"pay_hold": {"$exists": False}}, {"pay_hold": None}]},
        {"$set": {"pay_hold": hold, "updated_at": now_iso()}})
    if res.modified_count:
        from dependencies import audit
        await audit((actor or AKTOR_SISTEM).get("name", ""), "pay_hold_started", "sales_order", oid,
                    {"required": st["required"], "basis": st["basis"], "term": st["term_code"],
                     "due_at": hold["due_at"], "order_number": so.get("number", "")})
    else:
        await db.sales_orders.update_one({"id": oid, "status": "approved", "pay_hold.since": {"$exists": True}},
                                         {"$set": {"pay_hold.required": st["required"], "pay_hold.basis": st["basis"]}})
    so = await _segarkan_tahap(oid)
    # B1 — kode bayar sejak disetujui (Konfirmasi Pesanan/Faktur Komersial memuat instruksi bayar). Gagal = dicatat;
    # tahan tetap berlaku (penanda sudah tertulis) dan `confirm_core` mencoba lagi.
    try:
        from services import payment_code_service as _pcs
        await _pcs.ensure_for_order(so, percent=st["dp_percent"])   # persen = gerbang (satu hitungan)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[pay_hold] kode bayar %s gagal dibuat: %s", oid, exc)
    return so.get("pay_hold")


#: R12 — status "belum dilepas ke gudang": pesanan yang wajib bayar dulu di status ini belum boleh menerima uang dari
#: pencatat tanpa `payment_report.decide` (pagar B3). R13 — termasuk `waiting_stock` (backorder murni: pesanan lahir di
#: sana, menerima alokasi, lalu naik ke `approved` + `start()` lewat `advance_so_if_all_approved`).
STATUS_SEBELUM_GUDANG = ("reserved", "waiting_approval", "waiting_stock", "approved")


async def wajib_bayar_sebelum_gudang(order: Optional[Dict[str, Any]]) -> bool:
    """Ketetapan R12 (pengendali, 26 Nov) — predikat pagar B3 (`ar_receipt_service.pagar_lapor_bayar`): pesanan WAJIB
    bayar dulu (`dispatch_payment_gate.evaluate(...).applies`; sample dan SO pesanan khusus dikecualikan persis seperti
    `start`) DAN belum dilepas ke gudang (status `STATUS_SEBELUM_GUDANG`) DAN tanpa pengecualian berizin
    `dispatch_payment_release` — ada atau belum penanda `pay_hold`. Dulu pagar hanya menilai penanda, jadi transfer yang
    dicatat sales SEBELUM disetujui (`reserved`/`waiting_approval`/`waiting_stock`) lolos; pada dasar `tercatat` uang itu
    langsung dihitung terbayar dan `start` tidak pernah menahan — pengecekan Finance terlompati. Bukan predikat buka
    tahan: `clear_if_paid` / `buka_tahan_bayar` tetap memakai penanda (`ditahan`)."""
    o = order or {}
    if o.get("status") not in STATUS_SEBELUM_GUDANG or o.get("dispatch_payment_release"):
        return False
    st = await _status_gerbang(o)
    return bool(st and st["applies"])


async def sisa_wajib_sebelum_gudang(order: Optional[Dict[str, Any]]) -> Optional[float]:
    """Ketetapan R19 (pengendali, 26 Nov) — berapa yang MASIH wajib dibayar sebelum pesanan dilepas ke gudang: bila
    predikat bersama `wajib_bayar_sebelum_gudang` benar, = `required − dibayar tercatat` dari gerbang yang sama
    (`dispatch_payment_gate.evaluate`; satu hitungan, sama dengan `pay_hold.required` bila penanda sudah ada). Dibayar
    TERCATAT, bukan terverifikasi: uang yang sudah dicatat tetapi belum cocok mutasi bank tidak boleh ditagih dua kali.
    `None` bila pesanan tidak wajib bayar dulu / sudah dilepas / bagian wajibnya sudah terpenuhi (penilaian lama berlaku).

    Pemakai: `payment_variance_service._order_due_now` (yang DIHARAPKAN penilaian selisih bayar — dipakai kwitansi Finance
    langsung maupun Terima lapor bayar) dan `ar_receipt_service.isi_tagih_sekarang` (isian bawaan form kwitansi). Dulu DP
    dibayar sesudah konfirmasi terhadap baris uang muka; kini pesanan ditahan SEBELUM konfirmasi sehingga baris itu belum
    lahir dan harapan jatuh ke seluruh sisa pesanan — bayar tepat DP terbaca "kurang bayar"."""
    if not await wajib_bayar_sebelum_gudang(order):
        return None
    st = await _status_gerbang(order or {})
    if not (st and st["applies"]):
        return None
    from services.dispatch_payment_gate import EPS
    sisa = round(max(float(st["required"]) - float(st["paid_recorded"]), 0.0), 2)
    return sisa if sisa > EPS else None


#: R18-c — batas mana yang digeser `perpanjang_sesudah_putusan`.
BATAS_BAYAR, BATAS_BOOKING = "bayar", "booking"


async def perpanjang_sesudah_putusan(order_id: str, actor: Optional[Dict[str, Any]] = None, *,
                                     laporan: str = "", putusan: str = "") -> Optional[Dict[str, str]]:
    """R18-c (pengendali, 26 Nov) — Finance baru saja memutus laporan bayar (`putusan` = "diterima"/"ditolak", nomor
    `laporan`) pada pesanan yang BATASNYA SUDAH LEWAT. Selama laporan menunggu, penyapu tidak mengedaluwarsakan pesanan
    (§7-2); tanpa tenggang, putaran penyapu berikutnya (≤ 30 menit) langsung mengedaluwarsakannya — sales tidak sempat
    melapor ulang sesudah ditolak, dan uang yang baru diterima menjadi titipan. Maka batasnya digeser ke sekarang +
    `tenggang_sesudah_putusan` (pengaturan per PT):

    * `approved` ber-`pay_hold` yang `due_at`-nya lewat dan MASIH kurang bayar (`blocked`) → `pay_hold.due_at` baru;
      yang tidak lagi kurang dibiarkan (penyapu membuka tahan basinya, `nasib_lewat_batas`);
    * `reserved` / `waiting_approval` wajib bayar dulu yang masa reservasinya lewat (dijaga laporan yang menunggu,
      putaran 1 penyapu) → `reservation_expires_at` baru — Terima pun tidak boleh berujung kedaluwarsa.

    Batas yang belum lewat tidak disentuh. Satu tulisan CAS pada batas lama (penyapu yang mengklaim memakai batas yang
    sama sebagai prasyarat) + riwayat status pesanan (`stage: batas_diperpanjang`) + jejak audit (`pay_hold_extended` /
    `reservation_extended`). → `{jenis, dari, sampai}` bila digeser, `None` bila tidak."""
    so = await _muat(order_id)
    status = so.get("status")
    if status == "approved" and so.get("pay_hold"):
        jenis, medan, lama = BATAS_BAYAR, "pay_hold.due_at", (so.get("pay_hold") or {}).get("due_at")
    else:
        from services.inventory_service import EXPIRABLE_SO_STATUSES
        if status not in EXPIRABLE_SO_STATUSES:
            return None
        jenis, medan, lama = BATAS_BOOKING, "reservation_expires_at", so.get("reservation_expires_at")
    sekarang = datetime.now(timezone.utc)
    batas_lama = _waktu(lama)
    if not batas_lama or batas_lama > sekarang:
        return None
    if jenis == BATAS_BAYAR:
        if not await blocked(so):
            return None
    else:
        st = await _status_gerbang(so)
        if not (st and st["applies"]):
            return None
    sampai = (sekarang + await tenggang_sesudah_putusan(so.get("entity_id"))).isoformat()
    pelaku = actor or AKTOR_SISTEM
    nama = "Batas bayar" if jenis == BATAS_BAYAR else "Masa reservasi"
    catatan = (f"{nama} diperpanjang sesudah laporan bayar {laporan or '-'} {putusan or 'diputus'} "
               f"(batas lama sudah lewat)")
    from services import status_history as sh
    res = await db.sales_orders.update_one(
        {"id": order_id, "status": status, medan: lama},
        {"$set": {medan: sampai, "updated_at": now_iso()},
         "$push": {"status_history": sh.entry(status, user=pelaku.get("name", ""), note=catatan,
                                              stage="batas_diperpanjang")}})
    if not res.modified_count:
        return None   # batas / status berubah oleh proses lain (penyapu, laporan lain) — biarkan pemiliknya
    await _segarkan_tahap(order_id)
    from dependencies import audit
    await audit(pelaku.get("name", ""), "pay_hold_extended" if jenis == BATAS_BAYAR else "reservation_extended",
                "sales_order", order_id, {"dari": lama, "sampai": sampai, "laporan": laporan, "putusan": putusan,
                                          "order_number": so.get("number", "")})
    return {"jenis": jenis, "dari": str(lama), "sampai": sampai}


#: LB-T5 — nasib pesanan tertahan yang batas bayarnya lewat (tanpa laporan bayar menunggu), lihat `nasib_lewat_batas`.
NASIB_KEDALUWARSA, NASIB_BUKA, NASIB_CEK_BANK = "kedaluwarsa", "buka", "cek_bank"


async def nasib_lewat_batas(order: Dict[str, Any]) -> str:
    """LB-T5 (§5.3) — apa yang dilakukan penyapu pada pesanan ber-`pay_hold` yang `due_at`-nya lewat dan TIDAK punya
    laporan bayar menunggu/memproses. Satu hitungan (`evaluate`):

    * `kedaluwarsa` — masih wajib bayar dan uang yang tercatat belum cukup → langkah kedaluwarsa cadangan;
    * `buka` — gerbang tidak lagi menahan (uang cukup, pengecualian berizin, gerbang dimatikan untuk PT) → tahan basi
      dibuka (`clear_if_paid`), pesanan TIDAK dikedaluwarsakan;
    * `cek_bank` — dasar `terverifikasi` dan uang tercatat sudah cukup, hanya belum cocok mutasi bank: yang terlambat
      pengecekan Finance, bukan pelanggan (§7-2) → tidak dikedaluwarsakan, Finance diberi tahu."""
    st = await _status_gerbang(order)
    if not (st and st["applies"] and st["blocked"]):
        return NASIB_BUKA
    from services.dispatch_payment_gate import EPS
    if st["basis"] == "terverifikasi" and st["required"] - st["paid_recorded"] <= EPS:
        return NASIB_CEK_BANK
    return NASIB_KEDALUWARSA


def ditahan(order: Optional[Dict[str, Any]]) -> bool:
    """SATU predikat "pesanan sedang ditahan bayar sebelum gudang" (penanda, bukan hitungan uang): `pay_hold` terisi
    atau `release.waiting == "bayar"`. Dipakai `clear_if_paid` dan pembuka tahan sesudah kwitansi / keputusan selisih /
    cocok mutasi bank (LB-T4) — pasangan Mongo-nya `saringan_ditahan()`. Pagar B3 memakai `wajib_bayar_sebelum_gudang`
    (R12: juga sebelum penanda ada)."""
    o = order or {}
    return o.get("pay_hold") is not None or (o.get("release") or {}).get("waiting") == "bayar"


def saringan_ditahan() -> Dict[str, Any]:
    """Saringan Mongo yang sama persis dengan `ditahan` (dokumen baru tiap panggilan; aman digabung ke saringan lain
    yang tidak memakai `$or`)."""
    return {"$or": [{"pay_hold": {"$exists": True, "$ne": None}}, {"release.waiting": "bayar"}]}


def _cabut(so: Dict[str, Any]) -> Dict[str, str]:
    """Isi `$unset` penanda: `pay_hold` + `release.waiting` (hanya bila `release` berupa dokumen)."""
    out = {"pay_hold": ""}
    if isinstance(so.get("release"), dict):
        out["release.waiting"] = ""
    return out


async def drop(order_id: str) -> None:
    """Hapus penanda tanpa memicu lepas (dipakai `confirm_core` sesudah pesanan benar-benar dilepas ke gudang)."""
    so = await _muat(order_id)
    if not so.get("pay_hold") and (so.get("release") or {}).get("waiting") is None:
        return
    await db.sales_orders.update_one({"id": order_id}, {"$unset": _cabut(so)})
    await _segarkan_tahap(order_id)


async def clear_if_paid(order_id: str, actor: Optional[Dict[str, Any]] = None, why: str = "bayar diterima") -> bool:
    """Buka tahan bila `evaluate` tidak lagi menahan (uang cukup atau ada pengecualian berizin), lalu jalankan lepas
    otomatis. Kembalian = pesanan benar-benar dilepas ke gudang (`confirmed`) oleh panggilan ini.

    Aturan R4 (pengendali, 25 Nov): lepas otomatis HANYA bila Admin Sales sudah menekan "Periksa & lepas"
    (`release.requested`, diperiksa `so_release_service.auto_release`). Tanpa itu pesanan cukup kehilangan tahannya dan
    menunggu Admin Sales seperti biasa — verifikasi Admin Sales tidak boleh dilompati oleh uang yang masuk."""
    so = await _muat(order_id)
    if not so:
        return False
    if not ditahan(so):
        return False   # tidak sedang ditahan (pesanan lama / non-CBD): tidak ada yang dibuka
    if await blocked(so):
        return False
    # Klaim: penanda ikut di saringan, jadi dari dua pemanggil bersamaan hanya satu yang membuka tahan, menulis jejak,
    # dan menjalankan lepas otomatis.
    res = await db.sales_orders.update_one(
        {"id": order_id, "status": so.get("status"), **saringan_ditahan()},
        {"$unset": _cabut(so), "$set": {"updated_at": now_iso()}})
    if not res.modified_count:
        return False   # penanda sudah dibuka / status berubah oleh proses lain — biarkan pemiliknya yang melanjutkan
    await _segarkan_tahap(order_id)
    from dependencies import audit
    pelaku = actor or AKTOR_SISTEM
    await audit(pelaku.get("name", ""), "pay_hold_cleared", "sales_order", order_id,
                {"why": why, "required": (so.get("pay_hold") or {}).get("required"),
                 "order_number": so.get("number", "")})
    from services import so_release_service as _rel
    return _rel.dilepas(await _rel.auto_release(order_id, pelaku, why=why))
