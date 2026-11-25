"""services/so_close_remaining_service.py — tutup sisa pesanan yang dikirim sebagian (BTP-4).

Rancangan `docs/superpowers/specs/2026-11-25-batal-tutup-sisa-pesanan-design.md` §5.6 "Tutup sisa" langkah 1–8 dan §5.2
(keputusan pemilik A1-1…A1-5, 25 Nov 2026). Dulu pesanan `partially_shipped` yang sisanya tidak diinginkan pelanggan
menggantung selamanya: roll tetap dipesan, plafon kredit tetap terpakai, gerbang CBD menagih nilai penuh, dan komisi
dihitung dari jumlah yang dipesan. Sekarang sisanya ditutup:

1. Penolak (versi pertama, §7 butir 9): status bukan `partially_shipped`; Faktur Pajak aktif yang bukan per Surat Jalan;
   nota amandemen / tagihan tambahan; pendapatan berjurnal per pesanan (jalur lama); Surat Jalan yang belum berjurnal;
   produk sama di dua baris; baris terkirim melebihi pesanan; baris Pesanan Khusus belum terkirim penuh. → 409 berpesan,
   tanpa satu tulisan pun.
2. Jumlah terkirim per produk = Σ `shipped_qty` tugas outbound pesanan (tugas `cancelled` diabaikan) — sumber yang sama
   dengan `fulfillment_status.recompute_so_status`.
3. Tugas gudang terbuka: belum mengirim apa pun → `cancelled`; sudah mengirim sebagian → ditutup ke qty terkirimnya
   (`dispatched`). Roll sisa dilepas (`release_order_rolls`; yang sudah diambil → antrean Penempatan Rak). Backorder
   terbuka ditutup (A1-5).
4. Baris turun ke jumlah terkirim (`quantity_ordered_original` / `base_quantity_ordered_original` disimpan
   sekali); baris terkirim 0 keluar dari `items` ke `closed_lines[]`.
5. NILAI BARU = YANG SUDAH DIBUKUKAN per Surat Jalan (`gl_service.order_revenue_recognized`): `grand_total`,
   `ppn_amount`, `approval_amount` dipaksa sama dengan pendapatan + PPN jurnal Surat Jalan, sehingga piutang buku = sisa
   tagihan pesanan dan TIDAK ADA JURNAL BARU (A1-3). Mesin harga (`compute_order_pricing`, potret pajak pesanan) hanya
   untuk rincian baris; DPP/subtotal mengikuti `grand_total − PPN`; selisih pembulatan ke baris terakhir. Selisih hitung
   ulang vs dibukukan di atas toleransi pembulatan → ditolak (jangan menebak).
6. Kelebihan uang = `min(uang muka belum diakui, terbayar − nilai baru)` → titipan pelanggan lewat inti yang sama
   dengan pesanan batal (`ar_receipt_service.pindah_uang_muka_ke_titipan`, tanpa jurnal: uang muka & titipan sama-sama
   2-1400) + Finance diberi tahu (A1-2).
7. Status → `shipped` (aturan `recompute_so_status`; `done` tetap manual); `closed_short` (+ dasar komisi asli untuk
   koreksi komisi di bulan penutupan, Tugas 5).
8. Audit + linimasa + notifikasi sales pemilik.

Eksekusi bersaga (INV-ATOMIC-01): klaim pesanan → klaim setiap tugas terbuka (pengiriman yang sedang berjalan menang,
tutup sisa 409) → rencana dihitung ulang dari keadaan terkunci → tulisan. Galat di tengah tulisan → kunci ditandai gagal
(terlihat di Kunci Saga); rencana dibaca ulang dari dokumen, jadi ulangan sesudah kunci dilepas menghasilkan akhir yang
sama.
"""
import logging
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

from core_utils import now_iso, rupiah, safe_doc
from db import db

logger = logging.getLogger(__name__)

STATUS_BOLEH = "partially_shipped"
TASK_TERMINAL = ("dispatched", "cancelled", "completed")
SAGA_ACTION = "order_close_remaining"
EPS = 0.01
#: Batas TEKNIS pembulatan (bukan aturan bisnis): selisih hitung ulang mesin harga vs nilai yang dibukukan per Surat
#: Jalan yang masih dianggap pembulatan, per baris pesanan (rancangan §5.6 langkah 5; keputusan implementer §7 butir 8).
TOLERANSI_PER_BARIS = 1.0
#: Presisi jumlah satuan jual baris sesudah ditutup: harga × jumlah harus = nilai yang dibukukan dalam toleransi
#: di atas.
#: Konversi yard/meter jarang bulat; dua desimal (0,005 yard × Rp 100.000) bisa menggeser nilai ratusan rupiah.
PRESISI_JUMLAH_JUAL = 6
SUMBER_TITIPAN = "tutup_sisa_titipan"
#: Label status yang tidak ada di `so_tracker_service.STATUS_LABEL` (pesanan tertutup), untuk pesan penolakan.
STATUS_MATI_LABEL = {"done": "Selesai", "cancelled": "Dibatalkan", "expired": "Kedaluwarsa"}
KATA_TITIPAN = "sisa ditutup"

PESAN_STATUS = "Tutup sisa hanya untuk pesanan yang sudah dikirim sebagian (status pesanan ini: {status})."
PESAN_TANPA_KIRIM = "Belum ada barang pesanan ini yang terkirim — pakai Batalkan, bukan Tutup sisa."
PESAN_FAKTUR = ("Pesanan ini punya Faktur Pajak per pesanan yang masih aktif ({nomor}). Batalkan atau ganti Faktur "
                "Pajak itu dulu (menu Faktur Pajak, alasan wajib), lalu tutup sisa.")
PESAN_NOTA = ("Pesanan ini punya nota kredit/debit amandemen ({nomor}). Tutup sisa belum bisa dipakai untuk pesanan "
              "bernota amandemen — hubungi Finance.")
PESAN_TAGIHAN_TAMBAHAN = ("Pesanan ini punya tagihan tambahan dari nota debit. Tutup sisa belum bisa dipakai untuk "
                          "pesanan bertagihan tambahan — hubungi Finance.")
PESAN_JURNAL_PESANAN = ("Pendapatan pesanan ini dibukukan per pesanan (jurnal lama), bukan per Surat Jalan. Tutup sisa "
                        "belum bisa dipakai untuk pesanan seperti ini — hubungi Finance.")
PESAN_SJ_BELUM_JURNAL = ("Surat Jalan {nomor} belum berjurnal pendapatan. Selesaikan posting gagalnya dulu, lalu tutup "
                         "sisa.")
PESAN_PRODUK_GANDA = ("Produk {produk} ada di lebih dari satu baris pesanan — jumlah terkirimnya tidak bisa dibagi "
                      "otomatis per baris. Minta Admin Sales merapikan pesanan dulu.")
PESAN_LEBIH_KIRIM = ("Produk {produk} terkirim {kirim:g} {satuan}, lebih banyak dari yang dipesan ({pesan:g} "
                     "{satuan}). Rapikan pesanan lewat amandemen dulu.")
PESAN_PESANAN_KHUSUS = ("Baris {produk} berasal dari Pesanan Khusus dan belum terkirim penuh. Batalkan sisa item itu "
                        "lewat Batal item Pesanan Khusus, lalu tutup sisa.")
PESAN_SELISIH = ("Nilai baru hasil hitung ulang ({hitung}) berbeda dari nilai yang sudah dibukukan per Surat Jalan "
                 "({buku}) lebih dari toleransi pembulatan. Tutup sisa tidak dijalankan — hubungi Finance untuk "
                 "memeriksa pesanan ini.")
PESAN_TUGAS_SIBUK = ("Tugas gudang pesanan ini sedang diproses (mis. sedang dikirim). Tunggu sebentar, muat ulang, "
                     "lalu coba lagi.")
PESAN_TITIPAN_GAGAL = "Kelebihan uang pesanan ini belum terpindah ke titipan pelanggan — hubungi Finance."


# ── Pembaca ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _base(it: Dict[str, Any]) -> float:
    return round(float(it.get("base_quantity", it.get("quantity", 0)) or 0), 2)


def _nama(it: Dict[str, Any]) -> str:
    return str(it.get("product_name") or it.get("sku") or it.get("product_id") or "-")


def _satuan_dasar(it: Dict[str, Any]) -> str:
    return str(it.get("base_unit") or it.get("unit") or "")


def _gagal(blockers: List[str]) -> HTTPException:
    return HTTPException(status_code=409, detail=" ".join(blockers))


async def _load(order_id: str) -> Dict[str, Any]:
    order = safe_doc(await db.sales_orders.find_one({"id": order_id}, {"_id": 0}))
    if not order:
        raise HTTPException(status_code=404, detail="Order tidak ditemukan")
    return order


async def _tasks(order_id: str) -> List[Dict[str, Any]]:
    return await db.wms_tasks.find({"order_id": order_id, "flow_type": "outbound"}, {"_id": 0}).to_list(1000)


def _shipped_by_product(tasks: List[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for t in tasks:
        if t.get("status") == "cancelled":
            continue
        pid = t.get("product_id") or ""
        out[pid] = round(out.get(pid, 0.0) + float(t.get("shipped_qty") or 0), 2)
    return out


async def _blockers(order: Dict[str, Any], shipped: Dict[str, float]) -> List[str]:
    """Penolak §5.6 langkah 1 + §7 butir 9 (dibaca tanpa tulisan)."""
    st = order.get("status") or ""
    if st != STATUS_BOLEH:
        from services.so_tracker_service import STATUS_LABEL
        label = STATUS_MATI_LABEL.get(st) or STATUS_LABEL.get(st, st)
        return [PESAN_STATUS.format(status=label or "-")]
    from services.tax_invoice_service import STATUS_TERBIT
    oid, out = order["id"], []
    async for f in db.tax_invoices.find({"order_id": oid, "status": {"$in": list(STATUS_TERBIT)},
                                         "doc_kind": {"$ne": "retur"}}, {"_id": 0, "number": 1, "items": 1}):
        baris = [b for b in f.get("items") or [] if isinstance(b, dict)]
        if not (baris and all(b.get("shipment_id") for b in baris)):   # faktur per Surat Jalan: semua baris ber-SJ
            out.append(PESAN_FAKTUR.format(nomor=f.get("number") or "-"))
            break
    nota = await db.credit_notes.find_one(
        {"order_id": oid, "status": {"$ne": "void"},
         "$or": [{"source": "amendment"}, {"amendment_id": {"$nin": [None, ""]}}]}, {"_id": 0, "number": 1})
    if nota:
        out.append(PESAN_NOTA.format(nomor=nota.get("number") or "-"))
    if any(isinstance(x, dict) for x in order.get("extra_billing_lines") or []):
        out.append(PESAN_TAGIHAN_TAMBAHAN)
    if await db.journal_entries.find_one({"source_type": "sales_order", "source_id": oid, "status": {"$ne": "void"}},
                                         {"_id": 0, "id": 1}):
        out.append(PESAN_JURNAL_PESANAN)
    async for sh in db.shipments.find({"order_id": oid, "status": {"$nin": ["cancelled", "void"]}},
                                      {"_id": 0, "id": 1, "shipment_no": 1, "gl_status": 1}):
        if sh.get("gl_status") == "not_required":
            continue
        if not await db.journal_entries.find_one(
                {"source_type": "shipment_revenue", "source_id": sh.get("id"), "status": {"$ne": "void"}},
                {"_id": 0, "id": 1}):
            out.append(PESAN_SJ_BELUM_JURNAL.format(nomor=sh.get("shipment_no") or sh.get("id")))
            break
    items = order.get("items") or []
    jumlah_baris: Dict[str, int] = {}
    for it in items:
        jumlah_baris[it.get("product_id") or ""] = jumlah_baris.get(it.get("product_id") or "", 0) + 1
    ganda_disebut = set()
    for it in items:
        pid = it.get("product_id") or ""
        if jumlah_baris[pid] > 1:
            if pid not in ganda_disebut:   # sekali per produk
                ganda_disebut.add(pid)
                out.append(PESAN_PRODUK_GANDA.format(produk=_nama(it)))
            continue
        b, s = _base(it), shipped.get(pid, 0.0)
        if s > b + EPS:
            out.append(PESAN_LEBIH_KIRIM.format(produk=_nama(it), kirim=s, pesan=b, satuan=_satuan_dasar(it)))
        elif it.get("special_order_item_id") and s + EPS < b:
            out.append(PESAN_PESANAN_KHUSUS.format(produk=_nama(it)))
    for pid, s in shipped.items():
        if s > EPS and pid not in jumlah_baris:
            out.append(PESAN_LEBIH_KIRIM.format(produk=pid or "-", kirim=s, pesan=0, satuan=""))
    if not out and not any(s > EPS for s in shipped.values()):
        out.append(PESAN_TANPA_KIRIM)
    return out


# ── Rencana (murni, tanpa tulisan) ───────────────────────────────────────────────────────────────────────────────────
def _baris_baru(items: List[Dict[str, Any]],
                shipped: Dict[str, float]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """(baris yang tetap — jumlah turun ke terkirim, baris terkirim 0 yang keluar)."""
    tetap, keluar = [], []
    for it in items:
        b, s = _base(it), round(shipped.get(it.get("product_id") or "", 0.0), 2)
        if s <= EPS:
            keluar.append(it)
            continue
        n = dict(it)
        n.setdefault("quantity_ordered_original", it.get("quantity"))   # sekali, tidak pernah ditimpa
        n.setdefault("base_quantity_ordered_original", b)
        jual_per_dasar = float(it.get("quantity") or 0) / b if b > 0 else 1.0   # pola outbound_picking (sell_per_base)
        n["base_quantity"] = s
        n["quantity"] = round(s * jual_per_dasar, PRESISI_JUMLAH_JUAL)
        if "reserved_qty" in n:   # invarian L4-BO: base_qty == reserved + backorder + interco
            n["reserved_qty"] = s
        for k in ("backorder_qty", "intercompany_pending_qty"):
            if k in n:
                n[k] = 0.0
        tetap.append(n)
    return tetap, keluar


def _paksa_dibukukan(priced: Dict[str, Any], booked: Dict[str, float]) -> Dict[str, Any]:
    """Angka pesanan = yang dibukukan per Surat Jalan: `grand_total` = pendapatan + PPN jurnal, `ppn_amount` = PPN
    jurnal. `net_subtotal` mengikuti (`grand − PPN`, atau `grand` bila harga termasuk PPN); selisih pembulatannya
    ditaruh di baris terakhir (`line_total` naik/turun, `discount_amount` menampung supaya `subtotal` = harga × jumlah
    tetap). DPP digeser sebanding selisih harga jual (DPP nilai lain ikut faktornya)."""
    grand = round(float(booked["revenue"]) + float(booked["ppn"]), 2)
    ppn = round(float(booked["ppn"]), 2)
    net = grand if priced.get("ppn_mode") == "included" else round(grand - ppn, 2)
    d_net = round(net - float(priced["net_subtotal"]), 2)
    d_ppn = round(ppn - float(priced["ppn_amount"]), 2)
    items = [dict(i) for i in priced["items"]]
    last = items[-1]
    if d_net:
        last["line_total"] = round(float(last.get("line_total") or 0) + d_net, 2)
        last["discount_amount"] = round(float(last.get("discount_amount") or 0) - d_net, 2)
    if d_ppn and "ppn_amount" in last:   # PPN dibulatkan per baris (TX-T1)
        last["ppn_amount"] = round(float(last["ppn_amount"]) + d_ppn, 2)
    jual_hitung = round(float(priced["grand_total"]) - float(priced["ppn_amount"]), 2)
    faktor = float(priced["dpp"]) / jual_hitung if jual_hitung > EPS else 1.0
    dpp = round(float(priced["dpp"]) + (round(grand - ppn, 2) - jual_hitung) * faktor, 2)
    return {"items": items, "total_amount": priced["total_amount"],
            "items_discount_total": round(float(priced["items_discount_total"]) - d_net, 2),
            "order_discount_amount": priced["order_discount_amount"],
            "discount_total": round(float(priced["discount_total"]) - d_net, 2),
            "net_subtotal": net, "dpp": dpp, "dpp_nilai_lain": priced.get("dpp_nilai_lain", False),
            "effective_rate": priced.get("effective_rate", priced.get("ppn_rate")),
            "ppn_amount": ppn, "grand_total": grand, "approval_amount": grand}


async def _rencana(order: Dict[str, Any]) -> Dict[str, Any]:
    """Semua angka tutup sisa dari dokumen saat ini — TANPA tulisan. `blockers` tidak kosong = tidak boleh jalan."""
    from services import gl_service as gl
    from services.customer_service import _order_paid as order_paid
    oid = order["id"]
    tasks = await _tasks(oid)
    shipped = _shipped_by_product(tasks)
    items = order.get("items") or []
    blockers = await _blockers(order, shipped)
    lines = []
    for it in items:
        b = _base(it)
        jual_per_dasar = float(it.get("quantity") or 0) / b if b > 0 else 1.0
        lines.append({"product_id": it.get("product_id") or "", "product_name": it.get("product_name") or "",
                      "unit": str(it.get("unit") or it.get("base_unit") or ""),
                      "qty_ordered": float(it.get("quantity") or 0),
                      "qty_shipped": round(shipped.get(it.get("product_id") or "", 0.0) * jual_per_dasar,
                                           PRESISI_JUMLAH_JUAL)})
    booked = await gl.order_revenue_recognized(oid)
    before = round(float(order.get("grand_total") or 0), 2)
    after = round(float(booked["revenue"]) + float(booked["ppn"]), 2)
    paid = round(order_paid(order), 2)
    excess = round(max(0.0, min(await gl.order_advance_unrecognized(order), paid - after)), 2)
    plan: Dict[str, Any] = {"blockers": blockers, "lines": lines, "tasks": tasks, "shipped": shipped,
                            "booked": booked, "totals": None, "closed": [],
                            "grand_total_before": before, "grand_total_after": after,
                            "remaining_value": round(before - after, 2), "excess_to_deposit": excess, "paid": paid}
    if blockers:
        return plan
    tetap, keluar = _baris_baru(items, shipped)
    from services.config_service import compute_order_pricing
    from services.tax_config_service import potret_dokumen
    priced = await compute_order_pricing(
        tetap, order.get("entity_id"), float(order.get("order_discount_percent", 0) or 0),
        tax_override=(order.get("tax_override") or "").strip().lower() or None,
        snapshot=potret_dokumen(order))   # TX-T1 — aturan pajak saat pesanan dibuat
    batas = TOLERANSI_PER_BARIS * max(1, len(tetap)) + 1e-9
    if abs(after - float(priced["grand_total"])) > batas or \
            abs(float(booked["ppn"]) - float(priced["ppn_amount"])) > batas:
        blockers.append(PESAN_SELISIH.format(hitung=rupiah(priced["grand_total"]), buku=rupiah(after)))
        return plan
    plan.update({"totals": _paksa_dibukukan(priced, booked), "closed": keluar})
    return plan


def _ringkas(plan: Dict[str, Any]) -> Dict[str, Any]:
    return {"allowed": not plan["blockers"], "blockers": list(plan["blockers"]), "lines": plan["lines"],
            "grand_total_before": plan["grand_total_before"], "grand_total_after": plan["grand_total_after"],
            "remaining_value": plan["remaining_value"], "excess_to_deposit": plan["excess_to_deposit"]}


async def preview(order: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan sebelum-sesudah untuk dialog: `{allowed, blockers, lines[{product_id, product_name, unit, qty_ordered,
    qty_shipped}], grand_total_before, grand_total_after, remaining_value, excess_to_deposit}`. Tanpa tulisan."""
    return _ringkas(await _rencana(order))


async def assess(order: Dict[str, Any]) -> Dict[str, Any]:
    """Penilai `so_cancel_service.ASSESSORS["close_remaining"]`: nominal kebijakan = nilai sisa (§5.2), kelebihan uang
    ke titipan, pratinjau. Tidak mungkin ditutup → 409 berpesan."""
    plan = await _rencana(order)
    if plan["blockers"]:
        raise _gagal(plan["blockers"])
    return {"amount": plan["remaining_value"], "excess": plan["excess_to_deposit"], "preview": _ringkas(plan)}


# ── Eksekusi ─────────────────────────────────────────────────────────────────────────────────────────────────────────
async def _klaim_tugas(order_id: str, actor_name: str) -> Dict[str, str]:
    """Klaim setiap tugas outbound terbuka pesanan ini → {id tugas: token}. Pengiriman yang sedang berjalan memegang
    kunci tugasnya, dan eskalasi yang sedang diselesaikan (`resolving`) sedang menulis pesanan → 409 (semua klaim yang
    sudah didapat dilepas)."""
    from services import atomic_claim as _saga
    tokens: Dict[str, str] = {}
    async for t in db.wms_tasks.find({"order_id": order_id, "flow_type": "outbound",
                                      "status": {"$nin": list(TASK_TERMINAL)}}, {"_id": 0, "id": 1, "status": 1}):
        try:
            doc = await _saga.claim("wms_tasks", t["id"], SAGA_ACTION, actor=actor_name,
                                    precondition={"status": t["status"], "escalation.status": {"$ne": "resolving"}})
        except HTTPException as exc:
            await _lepas_tugas(tokens)
            raise HTTPException(status_code=409, detail=PESAN_TUGAS_SIBUK) from exc
        tokens[t["id"]] = doc[_saga.LOCK]["token"]
    return tokens


async def _lepas_tugas(tokens: Dict[str, str]) -> None:
    from services import atomic_claim as _saga
    for tid, tok in tokens.items():
        await _saga.release("wms_tasks", tid, tok)


async def _tutup_tugas(plan: Dict[str, Any], tokens: Dict[str, str], actor_name: str, reason: str) -> Dict[str, Any]:
    """Tugas terbuka: terkirim 0 → `cancelled`; terkirim sebagian → qty = terkirim, `dispatched`. Eskalasi yang menunggu
    ikut ditutup. → {cancelled, closed, picked_ids (roll sudah diambil tetapi belum berangkat)}."""
    from services import atomic_claim as _saga
    from services import outbound_task_state as _ots
    now, why = now_iso(), f"Sisa pesanan ditutup: {reason}"
    out: Dict[str, Any] = {"cancelled": 0, "closed": 0, "picked_ids": []}
    for t in plan["tasks"]:
        tok = tokens.get(t["id"])
        if not tok:
            continue
        out["picked_ids"] += [e.get("roll_id") for e in t.get("scan_log") or []
                              if e.get("scan_type") == "pick" and e.get("roll_id")]
        if t.get("task_subtype") == "sample_cut" and t.get("roll_id"):
            out["picked_ids"].append(t["roll_id"])
        shipped = round(float(t.get("shipped_qty") or 0), 2)
        jejak = {"at": now, "by": actor_name, "reason": reason, "quantity_before": t.get("quantity"),
                 "shipped_qty": shipped}
        fields: Dict[str, Any] = {"close_remaining": jejak}
        if (t.get("escalation") or {}).get("status") in ("pending_review", "open"):
            fields.update({"escalation.status": "cancelled", "escalation.cancelled_at": now,
                           "escalation.resolution_notes": f"Eskalasi ditutup: {why}"})
        if shipped > EPS:
            fields["quantity"] = shipped
            to = "dispatched"
        else:
            fields.update({"cancel_reason": why, "cancelled_by": actor_name, "cancelled_at": now})
            to = "cancelled"
        got = await _ots.transition(t["id"], "close_remaining", to, actor_name=actor_name, set_fields=fields,
                                    extra_filter={f"{_saga.LOCK}.token": tok}, unset=[_saga.LOCK], note=why,
                                    prev_status=t.get("status"))
        if not got:
            raise RuntimeError(f"tugas {t['id']} berubah saat sisa pesanan ditutup")
        tokens.pop(t["id"], None)
        out["closed" if to == "dispatched" else "cancelled"] += 1
    return out


def _alokasi(order: Dict[str, Any], tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Alokasi bertugas → qty = terkirim tugasnya (0 → keluar); alokasi tanpa tugas tertaut dibiarkan (data lama)."""
    tertaut = {t.get("allocation_id") for t in tasks if t.get("allocation_id")}
    kirim: Dict[str, float] = {}
    for t in tasks:
        if t.get("allocation_id") and t.get("status") != "cancelled":
            kirim[t["allocation_id"]] = round(kirim.get(t["allocation_id"], 0.0) + float(t.get("shipped_qty") or 0), 2)
    out = []
    for a in order.get("allocations") or []:
        aid = a.get("id")
        if not aid or aid not in tertaut:
            out.append(a)
        elif kirim.get(aid, 0.0) > EPS:
            out.append({**a, "quantity": kirim[aid]})
    return out


def _backorder_ditutup(order: Dict[str, Any], now: str) -> List[Dict[str, Any]]:
    out = []
    for b in order.get("backorders") or []:
        qty = round(float(b.get("backorder_qty") or 0), 2)
        if b.get("status") != "fulfilled" and qty > EPS:
            out.append({**b, "backorder_qty": 0.0, "status": "closed", "closed_qty": qty, "closed_at": now,
                        "updated_at": now})
        else:
            out.append(b)
    return out


def _patch(order: Dict[str, Any], plan: Dict[str, Any], actor: Dict[str, Any], reason: str, request_id: str,
           now: str) -> Dict[str, Any]:
    from services.ar_allocation_service import payment_status
    name = str(actor.get("name") or "")
    totals = plan["totals"]
    keluar = [{**it, "closed_at": now, "closed_by": name, "closed_reason": reason, "request_id": request_id}
              for it in plan["closed"]]
    patch: Dict[str, Any] = {
        **totals,
        "payment_status": payment_status(totals["grand_total"], plan["paid"]),
        "closed_lines": [*(order.get("closed_lines") or []), *keluar],
        "backorders": _backorder_ditutup(order, now), "has_backorder": False,
        "allocations": _alokasi(order, plan["tasks"]),
        "closed_short": {
            "at": now, "by": name, "by_id": str(actor.get("id") or ""), "reason": reason, "request_id": request_id,
            "grand_total_before": plan["grand_total_before"], "grand_total_after": plan["grand_total_after"],
            "remaining_value": plan["remaining_value"], "excess_to_deposit": plan["excess_to_deposit"],
            # Tugas 5 — komisi bulan penutupan dikoreksi dari dasar ASLI pesanan (bukan hitungan ulang).
            "commission_basis": {"grand_total": plan["grand_total_before"],
                                 "items": [{"product_id": it.get("product_id"), "base_quantity": _base(it)}
                                           for it in order.get("items") or []]}},
        "updated_at": now}
    if request_id:
        patch["cancel_request_id"] = request_id   # penanda eksekusi permintaan ini — dibaca `so_cancel_service`
    return patch


async def _pindah_kelebihan(order_id: str, actor: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Langkah 6 — kelebihan = min(uang muka belum diakui, terbayar − nilai baru) → titipan (inti pesanan batal)."""
    from services import ar_receipt_service as _ar
    from services import gl_service as gl
    from services.customer_service import _order_paid as order_paid
    fresh = await _load(order_id)
    kelebihan = 0.0
    if not fresh.get("advance_to_deposit"):
        kelebihan = max(0.0, min(await gl.order_advance_unrecognized(fresh),
                                 round(order_paid(fresh), 2) - float(fresh.get("grand_total") or 0)))
    try:
        moved = await _ar.pindah_uang_muka_ke_titipan(fresh, actor, reason, round(kelebihan, 2),
                                                      f"{SUMBER_TITIPAN}:{order_id}", KATA_TITIPAN)
        return {"advance_to_deposit": moved}
    except Exception as exc:  # noqa: BLE001 — sisa sudah ditutup; pemindahan aman diulang (Finance sudah diberi tahu)
        logger.error("Kelebihan uang pesanan %s (tutup sisa) gagal dipindah ke titipan: %s", order_id, exc)
        return {"advance_to_deposit": 0.0, "advance_to_deposit_error": PESAN_TITIPAN_GAGAL}


async def execute_close_remaining(order_id: str, actor: Dict[str, Any], reason: str,
                                  request_id: str = "") -> Dict[str, Any]:
    """Tutup sisa pesanan `partially_shipped` — §5.6 langkah 1–8 (lihat kepala modul). Izin, kepemilikan, dan alasan
    sudah diperiksa pemanggil; penolak diperiksa LAGI di sini (keadaan bisa berubah selama permintaan menunggu).
    → dokumen pesanan sesudahnya + ringkasan (`advance_to_deposit`, `closed_value`, `released_qty`, `tasks_*`)."""
    from services import atomic_claim as _saga
    from services.fulfillment_status import recompute_so_status
    from services.roll_service import release_order_rolls
    from services.sales_order_helpers import so_transition
    name = str(actor.get("name") or "")
    plan = await _rencana(await _load(order_id))
    if plan["blockers"]:
        raise _gagal(plan["blockers"])
    claimed = await _saga.claim("sales_orders", order_id, SAGA_ACTION, precondition={"status": STATUS_BOLEH},
                                actor=name)
    so_token = claimed[_saga.LOCK]["token"]
    tokens: Dict[str, str] = {}
    try:
        tokens = await _klaim_tugas(order_id, name)
        plan = await _rencana(claimed)   # dari keadaan terkunci: pengiriman di antaranya ikut terhitung
        if plan["blockers"]:
            raise _gagal(plan["blockers"])
    except Exception:
        await _lepas_tugas(tokens)
        await _saga.release("sales_orders", order_id, so_token)
        raise
    now = now_iso()
    try:
        tugas = await _tutup_tugas(plan, tokens, name, reason)
        released = await release_order_rolls(order_id, return_to_rack_ids=tugas["picked_ids"],
                                             why=f"Sisa pesanan ditutup: {reason}")
        await so_transition(order_id, [STATUS_BOLEH], "shipped", name, SAGA_ACTION,
                            _patch(claimed, plan, actor, reason, request_id, now))
    except Exception as exc:
        for tid in tokens:   # tugas yang belum tertutup tetap terkunci: pesanan setengah tertutup tidak boleh dikirim
            await _saga.mark_failed("wms_tasks", tid, f"tutup sisa pesanan terhenti: {exc}")
        await _saga.mark_failed("sales_orders", order_id, f"tutup sisa terhenti sesudah tulisan pertama: {exc}")
        raise
    await recompute_so_status(order_id)   # `fulfillment` + status turunan (semua tugas kini terminal → shipped)
    hasil = await _pindah_kelebihan(order_id, actor, reason)
    await _sesudah(claimed, plan, actor, reason, request_id, released, tugas, hasil)
    out = await _load(order_id)
    out.update(hasil)
    # 2026-10 — dokumen pemenuhan (transfer/PR) TIDAK ikut ditutup otomatis (A3, di luar cakupan): disebut di respons.
    refs = {p.get("ref_number") for d in (claimed.get("fulfillment_decisions") or [])
            for p in (d.get("parts") or []) if p.get("ref_number")}
    out.update({"closed_value": plan["remaining_value"], "released_qty": released,
                "tasks_cancelled": tugas["cancelled"], "tasks_closed": tugas["closed"],
                "open_fulfillment_refs": sorted(refs)})
    return out


async def _sesudah(order: Dict[str, Any], plan: Dict[str, Any], actor: Dict[str, Any], reason: str, request_id: str,
                   released: float, tugas: Dict[str, Any], hasil: Dict[str, Any]) -> None:
    """Langkah 8 + turunan: jadwal tagihan & saldo pelanggan, linimasa, audit, notifikasi sales pemilik. Best-effort —
    sisa pesanan sudah tertutup."""
    from dependencies import audit
    from services import billing_schedule_service as _bss
    from services import customer_balance_service as _cbs
    from services.so_override_service import notify_sales
    oid, name = order["id"], str(actor.get("name") or "")
    await _bss.kait_aman("tutup sisa pesanan", _bss.on_order_changed, oid)
    await _cbs.refresh_safe(order.get("customer_id") or "", order.get("entity_id") or "")
    ringkas = (f"Nilai pesanan {rupiah(plan['grand_total_before'])} → {rupiah(plan['grand_total_after'])} "
               f"(sisa {rupiah(plan['remaining_value'])} ditutup).")
    titipan = float(hasil.get("advance_to_deposit") or 0)
    if titipan:
        ringkas += f" Kelebihan {rupiah(titipan)} jadi titipan pelanggan."
    try:
        await db.sales_orders.update_one({"id": oid}, {"$push": {"timeline": {
            "event": "remaining_closed", "label": "Dikirim — sisa ditutup", "actor": name, "at": now_iso(),
            "note": f"{ringkas} Alasan: {reason}"}}})
    except Exception as exc:  # noqa: BLE001
        logger.warning("Linimasa tutup sisa pesanan %s gagal: %s", oid, exc)
    await audit(name, "so_remaining_closed", "sales_order", oid,
                {"request_id": request_id, "grand_total_before": plan["grand_total_before"],
                 "grand_total_after": plan["grand_total_after"], "remaining_value": plan["remaining_value"],
                 "closed_lines": [it.get("product_id") for it in plan["closed"]], "released_qty": released,
                 "tasks_cancelled": tugas["cancelled"], "tasks_closed": tugas["closed"],
                 "advance_to_deposit": titipan}, reason)
    try:
        await notify_sales(order, actor, f"{order.get('number')} — sisa pesanan ditutup oleh {name}",
                           f"{ringkas} Alasan: {reason or '-'}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Notifikasi sales tutup sisa pesanan %s gagal: %s", oid, exc)
