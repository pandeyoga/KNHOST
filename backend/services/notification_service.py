"""Notification service — pembuatan notifikasi + generator dari event REAL.

Tidak ada data mock: notifikasi dihitung dari kondisi nyata di
`inventory_balances` (stok menipis) dan `sales_orders` (reservasi mendekati
kedaluwarsa). Dedupe berbasis `ref` agar tidak menumpuk duplikat.
"""
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from db import db
from core_utils import new_id, now_iso, safe_doc, rupiah
from services.inventory_service import product_summary
logger = logging.getLogger(__name__)

# KF-T7 (#45, #47) — batas stok menipis barang tanpa titik pesan ulang (dulu 100) dan jendela "reservasi mendekati
# kedaluwarsa" (dulu 24 jam) kini pengaturan `inventory.low_stock_default_qty` / `notif.reservation_expiry_warn_hours`.


async def _has_unread(notif_type: str, ref: str) -> bool:
    return bool(await db.notifications.find_one(
        {"type": notif_type, "ref": ref, "read": False}, {"_id": 1}
    ))


async def create_addressed(
    *, permission: Optional[tuple] = None, division: str = "",
    roles: tuple = (), also_users: tuple = (), **kw: Any,
) -> List[Dict[str, Any]]:
    """FASE N — kirim notifikasi ke ORANG yang berwenang, satu per orang.

    Kenapa fan-out per orang dan bukan satu dokumen ber-"query izin": penyaring
    pembaca memakai **OR** (`recipient_role ∈ {peran, "all"}` OR `recipient_user`),
    jadi satu-satunya alamat yang benar-benar sempit adalah `recipient_user` SENDIRI.
    Menulis `recipient_role` bersama `recipient_user` justru MENYIARKAN ke seluruh
    peran itu — cacat yang terukur di `ar_due_soon` & `internal_request_decided`
    sebelum FASE N. Lihat `services/notification_audience.py` untuk alasan lengkap.

    `ref` diberi akhiran `#<user_id>` supaya **dedupe berjalan per orang**: kalau job
    yang sama jalan dua kali, tiap orang tetap punya satu pesan (bukan "orang pertama
    dapat, sisanya hilang karena ref-nya sudah terpakai").

    Return: daftar notifikasi yang BENAR-BENAR dibuat (yang ter-dedupe tidak masuk).
    Daftar KOSONG berarti tidak ada penerima berwenang — pemanggil yang memutuskan
    apakah itu wajar. Sengaja TIDAK ada jalan mundur ke `recipient_role="all"`.
    """
    from services import notification_audience as aud

    people = await aud.resolve_recipients(
        permission=permission, division=division, roles=roles,
        entity_id=kw.get("entity_id"), also_users=also_users)
    base_ref = str(kw.pop("ref", "") or "")
    out: List[Dict[str, Any]] = []
    for person in people:
        uid = str(person.get("id") or "")
        if not uid:
            continue
        note = await create_notification(
            **{**kw, "recipient_role": "", "recipient_user": uid,
               "ref": f"{base_ref}#{uid}" if base_ref else ""})
        if note:
            out.append(note)
    return out


async def create_notification(
    *, notif_type: str, title: str, body: str, severity: str = "info",
    link: str = "", entity_id: Optional[str] = None, recipient_role: str = "all",
    recipient_user: Optional[str] = None, ref: str = "", dedupe: bool = True,
    dedupe_scope: str = "unread",
    action_type: str = "", action_id: str = "", action_role: str = "",
) -> Optional[Dict[str, Any]]:
    """Buat 1 notifikasi. Return None bila di-dedupe.

    `dedupe_scope`:
    - `"unread"` (default, perilaku lama) → dilewati bila masih ada notifikasi
      SAMA yang BELUM dibaca.
    - `"day"` (R6.5, dipakai job scheduler) → dilewati bila notifikasi sama sudah
      pernah dibuat HARI INI (dibaca atau belum) → job boleh dijalankan berkali-kali
      dalam sehari tanpa menduplikasi.
    - `"ever"` (A2 · 2026-08-25) → dilewati bila notifikasi sama PERNAH dibuat, dibaca
      atau belum. Dipakai job yang hanya **MELAHIRKAN** pemberitahuan sekali untuk
      dokumen yang belum pernah punya penerima; PENAGIHAN BERULANG-nya milik satu
      mesin lain (`services/approval_reminder.py`). Tanpa `"ever"`, `"unread"` akan
      menagih lagi begitu pesannya dibaca — dan dua mesin kembali menagih dokumen
      yang sama tiap hari (kotak yang isinya berulang berhenti dibaca orang).

    `action_type`/`action_id`/`action_role` → aksi inline (mis. approve PO langsung
    dari kartu notifikasi). `action_role` = role minimum yang boleh aksi.
    """
    day = now_iso()[:10]
    dedupe_key = f"{notif_type}:{ref}:{day}" if ref else ""
    if dedupe and ref:
        if dedupe_scope == "day":
            if await db.notifications.find_one({"dedupe_key": dedupe_key}, {"_id": 1}):
                return None
        elif dedupe_scope == "ever":
            if await db.notifications.find_one({"type": notif_type, "ref": ref},
                                               {"_id": 1}):
                return None
        elif await _has_unread(notif_type, ref):
            return None
    doc = {
        "id": new_id("ntf"), "entity_id": entity_id,
        "recipient_role": recipient_role, "recipient_user": recipient_user,
        "type": notif_type, "title": title, "body": body, "link": link,
        "severity": severity, "ref": ref, "dedupe_key": dedupe_key,
        "read": False, "created_at": now_iso(),
        "action_type": action_type, "action_id": action_id, "action_role": action_role,
    }
    await db.notifications.insert_one(doc)
    clean = safe_doc(doc)
    # R6.5 — kanal WhatsApp (best-effort; TIDAK pernah menggagalkan pembuatan notifikasi).
    try:
        from services import wa_alert_service
        await wa_alert_service.push_notification(clean)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[create_notification] efek samping gagal diabaikan: %s", exc)  # KN-C10
    # Web Push (PWA HP) — best-effort, audiens sama dengan lonceng.
    try:
        from services import web_push_service
        await web_push_service.push_notification(clean)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[create_notification] web push gagal diabaikan: %s", exc)
    return clean


async def resolve_action(action_type: str, action_id: str, *, outcome: str = "",
                         actor: str = "") -> int:
    """Tutup notifikasi AKSI yang permintaannya sudah diputus.

    MASALAH YANG DISELESAIKAN: notifikasi "menunggu persetujuan" tetap menyala di
    lonceng walaupun dokumennya sudah disetujui/ditolak. Penerima mengklik tombol
    aksi yang PASTI gagal — bentuk lain dari tombol palsu, dan membuat pengguna
    tidak lagi percaya pada lonceng.

    Notifikasi TIDAK dihapus (jejak audit tetap utuh): ditandai `read` + diberi
    `resolved_at`/`resolution` sehingga aksi inline hilang tetapi riwayat tetap
    bisa dibaca. Aman dipanggil berkali-kali (idempotent) dan tidak pernah
    menggagalkan alur pemanggilnya.
    """
    if not action_type or not action_id:
        return 0
    try:
        res = await db.notifications.update_many(
            {"action_type": action_type, "action_id": action_id,
             "resolved_at": {"$exists": False}},
            {"$set": {"read": True, "read_at": now_iso(), "resolved_at": now_iso(),
                      "resolution": (outcome or "selesai")[:120], "resolved_by": actor}},
        )
        return int(res.modified_count or 0)
    except Exception:  # noqa: BLE001
        return 0


async def notify_po_awaiting_approval(po: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Depth #3 — notifikasi ke role approver saat PO masuk waiting_approval.

    Ditujukan ke `required_approval_role` (mis. manager). Dedupe via ref po_appr:<id>.
    Menyertakan alasan deviasi harga bila ada + aksi approve inline.
    """
    role = po.get("required_approval_role") or "manager"
    dev = po.get("price_deviation") or {}
    extra = ""
    if dev.get("flagged"):
        extra = f" Harga di atas price-list (+{dev.get('max_deviation_pct')}%)."
    return await create_notification(
        notif_type="po_approval", ref=f"po_appr:{po.get('id', '')}",
        title=f"PO menunggu persetujuan: {po.get('po_number', '')}",
        body=(f"{po.get('supplier_name', '')} · {rupiah(float(po.get('total_amount', 0)))}.{extra} "
              f"Perlu persetujuan {role}."),
        severity="warning" if dev.get("flagged") else "info",
        link="purchase-approval", entity_id=po.get("entity_id"), recipient_role=role,
        action_type="po_approve", action_id=po.get("id", ""), action_role=role,
    )


async def generate_system_notifications() -> int:
    """Pindai kondisi nyata sistem & buat notifikasi. Return jumlah yang dibuat.

    FASE N — alamat tiap peristiwa diturunkan dari WEWENANG, bukan disiarkan ke
    `recipient_role="all"`. Terukur sebelum fase ini: 9 dari 11 notifikasi ber-alamat
    "all" berasal dari fungsi ini (semuanya `low_stock`), sehingga Finance & Sales
    membuka kotaknya dan menemukan sembilan pesan stok kain. Lihat
    `services/notification_audience.py` untuk alasan lengkap.
    """
    from services.config_resolver import value_of

    created = 0

    # 1) Stok menipis — ambang batas per produk (`reorder_point`, konfigurasi NYATA
    #    di master produk); fallback ke ambang default bila produk belum diatur.
    #    ALAMAT (FASE N): pemegang `purchase_order.create` — karena pertanyaannya
    #    "siapa yang bisa BERTINDAK atas pesan ini?" — plus divisi tambahan bila
    #    pemilik mengisinya (`notif.low_stock_division`, bawaan kosong).
    from services.nilai_pengaturan import nilai
    division = str(await value_of("notif.low_stock_division", {"entity_id": ""}) or "").strip()
    bawaan_qty = float(await nilai("inventory.low_stock_default_qty"))   # KF-T7 — barang tanpa titik pesan ulang
    products = await db.products.find({"status": "active"}, {"_id": 0}).to_list(300)
    for product in products:
        summary = await product_summary(product["id"])
        threshold = float(product.get("reorder_point") or 0) or bawaan_qty
        if summary["available_qty"] < threshold:
            notes = await create_addressed(
                permission=("purchase_order", "create"), division=division,
                notif_type="low_stock", ref=f"low_stock:{product['id']}",
                title=f"Stok menipis: {product['name']}",
                body=(f"Available {summary['available_qty']:.0f} "
                      f"{product.get('base_unit', 'meter')} (< ambang {threshold:.0f}). "
                      f"Pertimbangkan buat PO ulang."),
                severity="warning", link="reorder", entity_id=product.get("entity_id"),
                dedupe_scope="day",
            )
            created += len(notes)

    # 2) Reservasi mendekati kedaluwarsa (<= `notif.reservation_expiry_warn_hours`, bawaan 24 jam) dari sales_orders
    #    ALAMAT: yang boleh MENGONFIRMASI pesanan (`order.confirm`) + sales pemegang
    #    akunnya. Dulu "all" — padahal gudang & finance tak bisa berbuat apa pun.
    jam_ingat = int(await nilai("notif.reservation_expiry_warn_hours"))
    sekarang = datetime.now(timezone.utc)
    soon = (sekarang + timedelta(hours=jam_ingat)).isoformat()
    from services.inventory_service import EXPIRABLE_SO_STATUSES
    orders = await db.sales_orders.find(
        # LB-T5 — hanya status yang memang dikedaluwarsakan penyapu cadangan (`inventory_service.EXPIRABLE_SO_STATUSES`).
        # Dulu (KN-D13) `approved`/`waiting_stock` ikut diperingatkan "pesanan gugur" padahal tidak pernah gugur karena
        # cadangan (FIX-3b / K-B2b-12); pesanan `approved` yang wajib bayar dulu kini diingatkan batas BAYAR-nya (2b).
        {"status": {"$in": list(EXPIRABLE_SO_STATUSES)},
         "reservation_expires_at": {"$lte": soon}}, {"_id": 0}
    ).to_list(200)
    # LB-T5 — pesanan yang laporan bayarnya masih menunggu Finance tidak gugur (penyapu menahannya): tanpa pengingat.
    from services import payment_report_service as _prs
    _dilapor = await _prs.laporan_tertunda([o["id"] for o in orders])
    orders = [o for o in orders if o["id"] not in _dilapor]
    from services.analytics_time import WIB

    def _wib(iso: Any) -> str:
        try:
            return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(WIB).strftime("%d/%m %H:%M WIB")
        except (TypeError, ValueError):
            return ""
    for order in orders:
        # Trial 22 Okt (E10) — pengingat H-1 juga ke sales pemilik (dulu `assigned_sales_id` yang tak pernah diisi) dan,
        # bila masih ada keputusan Manajer yang ditunggu, ke pemegang `order.approve`: merekalah yang menahan pesanan.
        waiting_mgr = any(p.get("status") == "pending" for p in order.get("pending_approvals") or [])
        nasib = ("menunggu keputusan Manajer" if waiting_mgr else "belum diperiksa & dilepas Admin Sales")
        kw = dict(notif_type="reservation_expiring", ref=f"resv:{order['id']}",
                  title=f"Booking stok segera habis: {order.get('number', '')}",
                  body=(f"{order.get('number', '')} ({order.get('customer_name', '')}) {nasib}. Booking stok berakhir "
                        f"{_wib(order.get('reservation_expires_at')) or f'≤ {jam_ingat} jam'} — lewat batas, pesanan gugur "
                        f"dan stok dilepas."),
                  severity="warning", link="orders", entity_id=order.get("entity_id"))
        sales_user = order.get("sales_id") or order.get("assigned_sales_id") or ""
        notes = await create_addressed(permission=("order", "confirm"), also_users=(sales_user,), **kw)
        if waiting_mgr:
            notes += await create_addressed(permission=("order", "approve"), **kw)
        created += len(notes)

    # 2b) LB-T5 — batas BAYAR segera habis (pesanan wajib bayar dulu yang tertahan, `pay_hold.due_at` dalam jendela yang
    #     sama, belum lewat). ALAMAT sama dengan (2): sales pemilik + pemegang `order.confirm`. Pesanan yang laporan
    #     bayarnya masih menunggu Finance dilewati — ia tidak gugur (§7-2). Satu pengingat per pesanan per orang
    #     (`ever`): job pindai berjalan tiap beberapa jam, dan batas bayar satu tahan tidak pernah berubah.
    created += await _notify_pay_due_soon(sekarang.isoformat(), soon)

    # 3) Order menunggu persetujuan (actionable, dari sales_orders)
    #    ALAMAT: pemegang `order.approve` — orang yang tombolnya memang ada.
    pending = await db.sales_orders.find({"status": "waiting_approval"}, {"_id": 0}).to_list(200)
    for order in pending:
        notes = await create_addressed(
            permission=("order", "approve"),
            notif_type="order_approval", ref=f"appr:{order['id']}",
            title=f"Order menunggu persetujuan: {order.get('number', '')}",
            body=(f"{order.get('customer_name', '')} · {rupiah(float(order.get('total_amount', 0)))}. "
                  f"Memerlukan persetujuan manajer."),
            severity="info", link="orders", entity_id=order.get("entity_id"),
        )
        created += len(notes)

    # 4) Order split antar gudang (informasi fulfillment)
    #    ALAMAT: yang mengerjakan barangnya — pemegang `wms.dispatch`.
    splits = await db.sales_orders.find(
        {"is_split_warehouse": True, "status": {"$nin": ["cancelled", "expired", "done"]}}, {"_id": 0}
    ).to_list(200)
    for order in splits:
        notes = await create_addressed(
            permission=("wms", "dispatch"),
            notif_type="order_split", ref=f"split:{order['id']}",
            title=f"Order split antar gudang: {order.get('number', '')}",
            body=(f"Order {order.get('number', '')} dipenuhi dari beberapa gudang. "
                  f"Koordinasikan pengiriman gabungan."),
            severity="info", link="operations", entity_id=order.get("entity_id"),
        )
        created += len(notes)

    # 5) PO menunggu persetujuan (Depth #3 — approver notification, deduped)
    pending_po = await db.purchase_orders.find(
        {"status": "waiting_approval"}, {"_id": 0}).to_list(200)
    for po in pending_po:
        note = await notify_po_awaiting_approval(po)
        if note:
            created += 1

    # 6) FASE N — TAHAP PO MACET. Papan PO per Lini (FASE P) sudah menampilkan progres
    #    tahap, tetapi tidak ada yang MEMBERI TAHU ketika satu tahap berhenti bergerak;
    #    selama ini kemacetan hanya terlihat oleh orang yang kebetulan membuka papannya.
    #    Ambang hari datang dari config (`notif.po_stage_stuck_days`), bukan angka di kode.
    created += await _notify_stuck_po_stages()

    # 7) FASE N — PO CUSTOM MENUNGGU KEPUTUSAN (`special_orders`).
    #    Endpoint pembuatannya sudah memberi tahu (routers/special_orders.py), tetapi
    #    itu hanya berlaku untuk dokumen yang lahir SESUDAH FASE N. Dokumen yang sudah
    #    menunggu sebelum itu — termasuk seluruh data demo (terukur: 3 dokumen, 0
    #    notifikasi) — tidak akan pernah punya penerima, dan justru dokumen inilah yang
    #    paling mahal bila terlambat (kain dipesan khusus, tak bisa dijual ke orang lain).
    #    Job ini menutupnya dari sisi KEADAAN (bukan kejadian): apa pun asal dokumennya,
    #    selama statusnya masih menunggu keputusan, pemegang wewenangnya diberi tahu.
    created += await _notify_pending_special_orders()

    return created


#: LB-T5 — jenis notifikasi batas bayar (rancangan Lapor Bayar §5.3).
PAY_DUE_SOON_TYPE = "pay_due_soon"
PAY_OVERDUE_PENDING_TYPE = "lapor_bayar_lewat_batas"


def _jam_wib(iso: Any) -> str:
    """'2026-11-27T03:00:00+00:00' → '27/11 10:00 WIB'; kosong bila tidak terbaca."""
    from services.analytics_time import WIB
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(WIB).strftime("%d/%m %H:%M WIB")
    except (TypeError, ValueError):
        return ""


async def _notify_pay_due_soon(now_iso_: str, soon_iso: str) -> int:
    """LB-T5 — pengingat H-1 `pay_due_soon`: pesanan `approved` ber-`pay_hold` yang batas bayarnya jatuh dalam
    (sekarang, sekarang + `notif.reservation_expiry_warn_hours`], tanpa laporan bayar menunggu. Ke sales pemilik +
    pemegang `order.confirm` (per orang), sekali per pesanan (`dedupe_scope="ever"`). → jumlah notifikasi dibuat."""
    from services import dispatch_payment_gate as gate
    from services import pay_hold_service as phs
    from services import payment_report_service as prs
    orders = await db.sales_orders.find(
        {"status": "approved", "pay_hold.due_at": {"$gt": now_iso_, "$lte": soon_iso}}, {"_id": 0}).to_list(200)
    dilapor = await prs.laporan_tertunda([o["id"] for o in orders])
    created = 0
    for order in orders:
        # hanya pesanan yang BENAR-BENAR gugur saat batas lewat (nasib penyapu yang sama): bukan yang laporannya menunggu,
        # yang sudah terbayar / tidak lagi wajib bayar, atau yang uangnya tercatat menunggu cocok mutasi bank
        if order["id"] in dilapor or await phs.nasib_lewat_batas(order) != phs.NASIB_KEDALUWARSA:
            continue
        st = await gate.evaluate(order)
        nomor = order.get("number", "")
        batas = _jam_wib((order.get("pay_hold") or {}).get("due_at"))
        notes = await create_addressed(
            permission=("order", "confirm"),
            also_users=(order.get("sales_id") or order.get("assigned_sales_id") or "",),
            notif_type=PAY_DUE_SOON_TYPE, ref=f"paydue:{order['id']}", dedupe_scope="ever",
            title=f"Batas bayar segera habis: {nomor}",
            body=(f"{nomor} ({order.get('customer_name', '')}) belum dibayar {_rupiah_aman(st.get('shortfall'))}. "
                  f"Batas bayar {batas} — lewat batas tanpa laporan bayar, pesanan gugur dan stok dilepas. Lapor bayar "
                  "di rincian pesanan."),
            severity="warning", link=f"/?view=orders&id={order['id']}", entity_id=order.get("entity_id"))
        created += len(notes)
    return created


async def notify_pay_overdue_pending(order: Dict[str, Any], *, sebab: str, batas_iso: str = "",
                                     report_numbers: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """LB-T5 (§5.3, §7-2) — SATU penyusun `lapor_bayar_lewat_batas`: pesanan sudah lewat batas (bayar atau masa booking
    stok) tetapi TIDAK dikedaluwarsakan penyapu karena pembayarannya menunggu dicek Finance — `sebab="laporan"` (laporan
    bayar `menunggu`/`memproses`) atau `"cek_bank"` (dasar `terverifikasi`, uang tercatat cukup, belum cocok mutasi
    bank). Ke pemegang `payment_report.decide` di PT pesanan (per orang), satu per pesanan per hari (`dedupe_scope="day"`;
    penyapu berjalan tiap 30 menit)."""
    nomor = order.get("number") or order.get("id") or ""
    pelanggan = order.get("customer_name") or "-"
    jam = _jam_wib(batas_iso)
    jenis_batas = "Batas bayar" if order.get("status") == "approved" else "Masa booking stok"
    lewat = f"{jenis_batas} {jam} sudah lewat" if jam else f"{jenis_batas} sudah lewat"
    if sebab == "cek_bank":
        title = f"Lewat batas bayar, menunggu cocok mutasi bank — {nomor}"
        body = (f"{pelanggan} — {lewat}. Pembayaran sudah tercatat tetapi belum cocok dengan mutasi bank; pesanan tidak "
                "dikedaluwarsakan. Cocokkan di Rekonsiliasi Bank.")
    else:
        daftar = ", ".join(n for n in (report_numbers or []) if n) or "laporan bayar"
        title = f"Lapor bayar menunggu melewati batas — {nomor}"
        body = (f"{pelanggan} — {lewat}, tetapi {daftar} masih menunggu dicek Finance. Pesanan tidak dikedaluwarsakan "
                "sampai laporannya diputus.")
    return await create_addressed(
        permission=("payment_report", "decide"), notif_type=PAY_OVERDUE_PENDING_TYPE,
        ref=f"lapor_lewat:{order.get('id', '')}", dedupe_scope="day", title=title, body=body[:400],
        severity="warning", link=f"/?view=orders&id={order.get('id', '')}", entity_id=order.get("entity_id") or None)


#: F1 — kwitansi otomatis dari mutasi bank (rancangan `2026-11-27-kwitansi-otomatis-mutasi` §5.8).
BAYAR_MASUK_MUTASI_TYPE = "bayar_masuk_mutasi"
RINGKASAN_MUTASI_TYPE = "ringkasan_mutasi_otomatis"
#: Keadaan pesanan sesudah kwitansi otomatis → akhir kalimat notifikasi sales.
KEADAAN_SESUDAH_MUTASI = {
    "dilepas": "pesanan dilepas ke gudang",
    "admin": "pesanan menunggu Admin Sales",
    "tertahan": "pesanan masih tertahan bayar",
}


async def notify_bayar_masuk_mutasi(order: Dict[str, Any], *, amount: float, receipt_number: str, keadaan: str,
                                    line_id: str) -> List[Dict[str, Any]]:
    """F1 (§5.8) — SATU penyusun `bayar_masuk_mutasi`: pembayaran pesanan yang SEDANG tertahan bayar masuk lewat mutasi
    bank dan menjadi kwitansi otomatis. Ke sales pemilik pesanan (per orang), sekali per baris mutasi
    (`dedupe_scope="ever"`). `keadaan` ∈ `KEADAAN_SESUDAH_MUTASI` (dilepas ke gudang / menunggu Admin Sales / masih
    tertahan). Pesanan yang tidak tertahan tidak diberi tahu (pemanggil yang memutuskan)."""
    sales = tuple(dict.fromkeys(x for x in (order.get("sales_id"), order.get("assigned_sales_id")) if x))
    if not sales:
        return []
    nomor = order.get("number") or order.get("id") or ""
    akhir = KEADAAN_SESUDAH_MUTASI.get(keadaan, KEADAAN_SESUDAH_MUTASI["admin"])
    return await create_addressed(
        also_users=sales, notif_type=BAYAR_MASUK_MUTASI_TYPE, ref=f"f1_bayar:{line_id}", dedupe_scope="ever",
        title=f"Pembayaran masuk — {nomor}",
        body=(f"Pembayaran {nomor} {_rupiah_aman(amount)} masuk lewat mutasi bank (kwitansi {receipt_number}); "
              f"{akhir}"),
        severity="info", link=f"/?view=orders&id={order.get('id', '')}", entity_id=order.get("entity_id") or None)


async def notify_ringkasan_mutasi_otomatis(*, entity_id: str, rekening: str, import_batch: str, jumlah: int,
                                           nilai: float, kartu: int) -> List[Dict[str, Any]]:
    """F1 (§5.8) — SATU penyusun `ringkasan_mutasi_otomatis`: satu notifikasi per impor mutasi ke pemegang
    `payment_report.decide` di PT baris (per orang, sekali per batch impor). Tidak dikirim bila keduanya 0."""
    if not jumlah and not kartu:
        return []
    kalimat = (f"Impor mutasi {rekening}: {jumlah} kwitansi otomatis ({_rupiah_aman(nilai)}), {kartu} mutasi berkode "
               "perlu dicek")
    body = kalimat + (". Lihat antrean \"Mutasi berkode perlu dicek\" di Meja Keuangan." if kartu else ".")
    return await create_addressed(
        permission=("payment_report", "decide"), notif_type=RINGKASAN_MUTASI_TYPE, ref=f"f1_impor:{import_batch}",
        dedupe_scope="ever", title=f"Impor mutasi {rekening}", body=body[:400],
        severity="warning" if kartu else "info", link="/?view=finance-desk", entity_id=entity_id or None)


#: Jenis notifikasi "PO custom menunggu keputusan". Hanya SATU fungsi di seluruh
#: backend yang boleh menyusunnya (dijaga INV-NOTIF-02 aturan K3).
SPECIAL_ORDER_WAITING_TYPE = "special_order_approval"


def _rupiah_aman(value: Any) -> str:
    """`rupiah()` yang tidak bisa menjatuhkan job/endpoint pemanggilnya.

    B4 (2026-08-25): `total_amount` bisa berupa TEKS di dokumen lama/hasil impor
    (mis. `"43.500.000"`). `float()` mentah melempar `ValueError` → job notifikasi
    berhenti di tengah jalan dan sisa dokumennya tak pernah diberitahukan.
    """
    try:
        return rupiah(float(value))
    except (TypeError, ValueError):
        return rupiah(0.0)


async def notify_special_order_waiting(
    so: Dict[str, Any], *, actor_name: str = "",
    dedupe_scope: str = "ever",
) -> List[Dict[str, Any]]:
    """SATU-SATUNYA penyusun pesan "PO custom menunggu keputusan".

    A1 DIBAYAR (2026-08-25): judul/isi/tautan/keparahan dulu diketik di DUA tempat —
    `routers/special_orders.py` (saat dokumen LAHIR) dan `_notify_pending_special_orders`
    (job, saat KEADAAN masih menunggu) — dan keduanya sudah tidak identik (versi
    endpoint menyebut "Diajukan oleh …", versi job tidak). Kelas cacat "dua layar
    bicara beda" yang persis sama dengan `approval_requests` dulu. Sekarang pesannya
    lahir di sini saja; pemanggil hanya memberi dokumen + siapa yang mengajukan.

    Alamatnya BUKAN "manager" yang diketik: peran yang memang diminta rantai
    persetujuan dokumen (`required_approval_role`, bisa Direksi untuk nilai besar) +
    pemegang `order.approve`, supaya tak pernah ada dokumen menunggu tanpa penerima.

    A2 — `dedupe_scope` bawaannya `"ever"`: fungsi ini hanya **MELAHIRKAN** pesan
    SEKALI untuk satu dokumen (dibaca atau belum, ia tidak menagih lagi). PENAGIHAN
    BERULANG harian adalah milik `services/approval_reminder.py` — SATU pemilik
    pengingat. Sebelum ini job memakai `dedupe_scope="day"`, sehingga satu PO custum
    yang menggantung menghasilkan DUA pesan tiap hari dari dua mesin berbeda
    (`special_order_approval` + `approval_backlog`) yang menyebut dokumen yang sama.
    """
    need_role = str(so.get("required_approval_role") or "")
    diajukan = f" Diajukan oleh {actor_name}." if actor_name else ""
    return await create_addressed(
        permission=("order", "approve"),
        roles=((need_role,) if need_role else ()),
        notif_type=SPECIAL_ORDER_WAITING_TYPE,
        ref=f"so_custom_appr:{so.get('id', '')}",
        title=f"PO custom menunggu persetujuan: {so.get('number', '')}",
        body=(f"{so.get('customer_name', '')} · "
              f"{_rupiah_aman(so.get('total_amount'))}.{diajukan} Perlu persetujuan "
              f"{need_role or 'manajer'}."),
        severity="warning", link="special-orders",
        entity_id=so.get("entity_id"), dedupe_scope=dedupe_scope,
    )


async def _notify_pending_special_orders() -> int:
    """Lahirkan pemberitahuan untuk PO custom menunggu yang BELUM punya penerima.

    Dokumen yang sudah menunggu sebelum FASE N — termasuk seluruh data demo — tidak
    akan pernah punya penerima kalau hanya endpoint pembuatannya yang memberi tahu.
    Job ini menutupnya dari sisi KEADAAN. Pesannya disusun `notify_special_order_waiting`
    (satu penyusun) dengan `dedupe_scope="ever"`: sekali lahir, tidak menagih lagi —
    penagihan berulang tetap milik `approval_reminder` (A2 di HANDOFF audit).
    """
    created = 0
    rows = await db.special_orders.find(
        {"status": "pending_approval"},
        {"_id": 0, "id": 1, "number": 1, "entity_id": 1, "customer_name": 1,
         "total_amount": 1, "required_approval_role": 1},
    ).to_list(200)
    for so in rows:
        created += len(await notify_special_order_waiting(so))
    return created


async def _notify_stuck_po_stages() -> int:
    """Beri tahu pemegang wewenang PO bila satu tahap proses berhenti bergerak.

    Ambang: `notif.po_stage_stuck_days` (bawaan 7 hari).

    BENTUK DATA — DIUKUR, bukan ditebak (2026-08-24). Versi pertama fungsi ini membaca
    `started_at` / `done_at` / `label`, dan **ketiganya tidak ada**. Baris
    `stage_progress` yang nyata berisi `stage_code` · `status` · `at` · `note` · `by`
    (3 PO memakainya di data demo). Kalau salah baca, fungsinya tidak error — ia hanya
    **diam selamanya**, kelas cacat termahal di repo ini (bandingkan SPK hasil makloon
    yang lahir nol baris karena `mko_number` dicari sebagai `number`). Nama tahap yang
    dibaca manusia diambil dari MASTER `process_stages`, bukan kode teknisnya.
    """
    from services.config_resolver import value_of

    created = 0
    from config_registry import default_of
    # KF-T3 (KF-10) — ambang dibaca PER PT tiap PO (lapisan PT berlaku), disimpan sementara selama satu putaran job.
    _ambang: Dict[str, tuple] = {}

    async def _ambang_pt(entity_id: str) -> tuple:
        if entity_id not in _ambang:
            try:
                hari = int(float(await value_of("notif.po_stage_stuck_days", {"entity_id": entity_id})
                                 or default_of("notif.po_stage_stuck_days")))
            except (TypeError, ValueError):
                hari = int(default_of("notif.po_stage_stuck_days"))
            hari = max(1, hari)
            _ambang[entity_id] = (hari, (datetime.now(timezone.utc) - timedelta(days=hari)).isoformat())
        return _ambang[entity_id]

    stages = await db.process_stages.find({}, {"_id": 0, "code": 1, "name": 1}).to_list(200)
    label_of = {str(s.get("code")): str(s.get("name") or s.get("code")) for s in stages}

    rows = await db.purchase_orders.find(
        {"stage_progress": {"$exists": True, "$ne": []}},
        {"_id": 0, "id": 1, "po_number": 1, "entity_id": 1, "supplier_name": 1,
         "stage_progress": 1},
    ).to_list(500)
    for po in rows:
        limit_days, batas = await _ambang_pt(str(po.get("entity_id") or ""))
        for st in (po.get("stage_progress") or []):
            if str(st.get("status") or "") != "in_progress":
                continue
            sejak = str(st.get("at") or "")
            if not sejak or sejak > batas:
                continue
            code = str(st.get("stage_code") or "")
            stage_label = label_of.get(code, code or "tahap")
            notes = await create_addressed(
                permission=("purchase_order", "create"),
                notif_type="po_stage_stuck",
                ref=f"po_stuck:{po['id']}:{code}",
                title=f"Tahap PO macet: {po.get('po_number', '')} · {stage_label}",
                body=(f"Tahap '{stage_label}' pada {po.get('po_number', '')} "
                      f"({po.get('supplier_name', '')}) berjalan sejak {sejak[:10]} dan "
                      f"belum selesai — lebih dari {limit_days} hari. "
                      f"Periksa Papan PO per Lini."),
                severity="warning", link="purchase-orders", entity_id=po.get("entity_id"),
                dedupe_scope="day",
            )
            created += len(notes)
    return created


async def notify_cycle_count_hit_reservation(*, product_id: str, warehouse_id: str, entity_id: str,
                                             order_ids: List[str], shortage_qty: float,
                                             session_number: str = "") -> List[Dict[str, Any]]:
    """Opname susut memotong roll yang sudah DIRESERVASI pesanan — sales pemilik pesanan
    (dan peran sales secara umum) harus tahu agar alokasi dicek/dipesankan ulang."""
    out: List[Dict[str, Any]] = []
    prod = await db.products.find_one({"id": product_id}, {"_id": 0, "name": 1, "sku": 1}) or {}
    label = prod.get("name") or prod.get("sku") or product_id
    for oid in order_ids:
        so = await db.sales_orders.find_one({"id": oid}, {"_id": 0, "number": 1, "sales_id": 1,
                                                          "assigned_sales_id": 1, "created_by_id": 1,
                                                          "created_by": 1, "sales_name": 1,
                                                          "entity_id": 1, "customer_name": 1})
        if not so:
            continue
        recipient_user = so.get("sales_id") or so.get("assigned_sales_id") or so.get("created_by_id")
        if not recipient_user:
            # SO lama hanya menyimpan NAMA sales/pembuat — petakan ke akun bila unik.
            nm = so.get("sales_name") or so.get("created_by")
            if nm:
                u = await db.users.find_one({"name": nm, "active": {"$ne": False}}, {"_id": 0, "id": 1})
                recipient_user = (u or {}).get("id")
        n = await create_notification(
            notif_type="cycle_count_reservation_hit",
            ref=f"cc_res:{oid}:{product_id}:{warehouse_id}",
            title=f"Stok reservasi pesanan {so.get('number', oid)} terpangkas opname",
            body=(f"Susut opname {session_number or ''} pada {label} mengambil roll yang sudah "
                  f"direservasi untuk {so.get('customer_name', '') or 'pelanggan'} "
                  f"(susut {shortage_qty:g}). Cek alokasi & hubungi pelanggan bila perlu."),
            severity="warning", link="orders", entity_id=so.get("entity_id") or entity_id,
            # INV-NOTIF-02 — beralamat ke PEMILIK pesanan; peran `sales_admin` hanya bila
            # pemiliknya tak dikenal (bukan siaran ke seluruh sales).
            **({"recipient_user": recipient_user} if recipient_user else {"recipient_role": "sales_admin"}),
            action_type="order_open", action_id=oid, action_role="sales",
        )
        if n:
            out.append(n)
    return out
