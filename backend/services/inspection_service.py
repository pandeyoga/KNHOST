"""FASE I — **INSPEKSI & QC SEBAGAI DOKUMEN** (`<ENT>/INS-#####`).

## Lubang nyata yang ditutup
Angka cacat & grade sudah dihitung `qc_inspection_service` (4-point) dan tersimpan di
roll. Yang TIDAK pernah ada: **SPK-nya**. Praktik pemilik memakai lembar kertas
"Inspect PO", "Inspect Retur (per PT)", "Inspect retur & replacement" — berisi petugas,
tanggal, milestone, hasil **warna** & **handfeel** dibanding sample yang di-ACC, lalu
keputusan. Tanpa dokumennya, tiga pertanyaan pemilik tak terjawab: siapa memeriksa,
kapan, dan atas dasar apa barang diterima/ditolak.

## Aturan yang dijaga di sini (BUKAN di layar) — §3.4 rencana MD-ERP
1. **Bukan pintu ke-3 untuk grade.** Poin cacat & grade tetap dihitung
   `qc_inspection_service.inspect_roll()`, dan grade tetap hanya berubah lewat
   `grade_service.set_roll_grade(source="qc_inspection")`. `lines[]` di dokumen ini
   adalah **RINGKASAN + keputusan**; `points_snapshot`/`grade_after` disalin dari hasil
   pemanggilan itu, tidak dihitung ulang. Kalau ia menghitung sendiri, dua angka akan
   berbeda dan tak ada cara memilih mana yang benar.
2. **Warna & handfeel disimpan DI ROLL** (`inventory_rolls.inspection`), karena
   pertanyaannya ("roll ini warnanya beda dari sample — boleh masuk gudang?")
   ditanyakan di roll, dan di sanalah pagar putaway membacanya.
3. **Melengkapi, bukan menggantikan** tugas `qc_pending`: dokumen `po_receipt` LAHIR
   OTOMATIS saat tugas penerimaan masuk antrean QC (`ensure_for_qc_task`), idempotent.
4. **Retur**: SSOT hasil per barang tetap `sales_returns.items[].inspection`
   (`return_service`). Dokumen `inspections(kind=return_customer)` adalah SPK +
   milestone + ringkasan — lines-nya menunjuk barang retur, tidak menyalin hasilnya.
5. **Keputusan `tolak` WAJIB ber-alasan** dan alasannya tersimpan di DOKUMEN (bukan
   hanya di audit log, yang tidak pernah dibaca orang yang sedang bertanya).

## Kebijakan selisih (keputusan pemilik #5)
`qc.color_mismatch_action` bawaan **tahan** · `qc.handfeel_mismatch_action` bawaan
**peringatkan** (`abaikan|peringatkan|tahan`). Roll yang DITAHAN tidak boleh putaway
sampai **manajer** melepasnya ber-alasan (`release_hold`).
"""
from __future__ import annotations
import logging

from typing import Any, Dict, List, Optional, Tuple

from core_utils import new_id, next_doc_number, now_iso, safe_doc, timeline_entry
from db import db
from services import line_scope
from role_registry import role_in  # peran acuan dikenali (keputusan owner 2026-10-21)
logger = logging.getLogger(__name__)


COLL = "inspections"

# ─── Jenis dokumen (pembeda `kind`, satu koleksi) ────────────────────────────
KIND_PO_RECEIPT = "po_receipt"
KIND_MAKLOON_OUTPUT = "makloon_output"
KIND_RETURN_CUSTOMER = "return_customer"
KIND_RETURN_SUPPLIER = "return_supplier"
KIND_REPLACEMENT = "replacement"
# P05 IMP-16 — random check QC atas roll yang sudah di stok (roll ditahan selama dicek).
KIND_RANDOM_CHECK = "random_check"
# L05 LN-050-T01 — QC atas permintaan checkout SO (seluruh / sampling) atas roll alokasi TERBARU.
KIND_SALES_ORDER = "sales_order"
# Trial 22 Okt 2026 (E9, keputusan pemilik) — SPK QC 4-point BERDIRI SENDIRI (dulu bagian dari SPK penerimaan): bisa
# dibuat kapan saja (dari kedatangan, dari SPK MD Quality, atau roll stok); baris DITOLAK menahan roll.
KIND_QC_4POINT = "qc_4point"
QC4_HOLD_PREFIX = "QC 4-point GAGAL"
#: Jenis yang hasil warna & handfeel-nya milik MD Quality (DEC-06, pemilik 2026-10-12).
MD_QUALITY_KINDS: Tuple[str, ...] = ("po_receipt", "makloon_output")

KIND_LABEL: Dict[str, str] = {
    KIND_PO_RECEIPT: "Inspeksi Penerimaan PO",
    KIND_MAKLOON_OUTPUT: "Inspeksi Hasil Makloon",
    KIND_RETURN_CUSTOMER: "Inspeksi Retur Pelanggan",
    KIND_RETURN_SUPPLIER: "Inspeksi Retur ke Supplier",
    KIND_REPLACEMENT: "Inspeksi Barang Pengganti",
    KIND_RANDOM_CHECK: "Random Check Stok (QC)",
    KIND_SALES_ORDER: "QC Permintaan Pesanan (SO)",
    KIND_QC_4POINT: "SPK QC 4-point",
}

# ─── Mesin keadaan (sengaja pendek) ──────────────────────────────────────────
STATUS_DRAFT = "draft"
STATUS_ASSIGNED = "assigned"
STATUS_IN_PROGRESS = "in_progress"
STATUS_DONE = "done"
STATUS_CLOSED = "closed"

STATUS_LABEL: Dict[str, str] = {
    STATUS_DRAFT: "Draf (belum ditugaskan)",
    STATUS_ASSIGNED: "Ditugaskan",
    STATUS_IN_PROGRESS: "Sedang diperiksa",
    STATUS_DONE: "Selesai (sudah diputuskan)",
    STATUS_CLOSED: "Ditutup",
}
BOARD_ORDER: Tuple[str, ...] = (STATUS_DRAFT, STATUS_ASSIGNED, STATUS_IN_PROGRESS,
                               STATUS_DONE, STATUS_CLOSED)
OPEN_STATUSES: Tuple[str, ...] = (STATUS_DRAFT, STATUS_ASSIGNED, STATUS_IN_PROGRESS)

DECISIONS: Dict[str, str] = {
    "terima": "Diterima seluruhnya",
    "terima_sebagian": "Diterima sebagian",
    "turun_grade": "Diterima dengan turun grade",
    "tolak": "Ditolak",
}
COLOR_RESULTS: Dict[str, str] = {
    "sesuai": "Sesuai sample",
    "beda_shade": "Beda shade (warna menyimpang)",
    "tolak": "Warna tidak bisa diterima",
}
HANDFEEL_RESULTS: Dict[str, str] = {
    "sesuai": "Sesuai sample",
    "beda": "Beda rasa/konstruksi",
    "tolak": "Handfeel tidak bisa diterima",
}
MISMATCH_ACTIONS: Dict[str, str] = {
    "abaikan": "Diabaikan",
    "peringatkan": "Diberi peringatan",
    "tahan": "Barang DITAHAN sampai ada keputusan",
}
#: Panjang MINIMUM alasan wajib (tolak · buka kembali · lepas tahanan).
#:
#: Angkanya bukan selera: rencana §I.E menuntut "alasan wajib (minimal satu kalimat)",
#: dan ambang lama (5 huruf) meloloskan "jelek" — kata yang secara teknis mengisi kolom
#: tetapi tidak menjawab apa pun bagi supplier yang menerima klaimnya, maupun bagi
#: manajer yang setahun kemudian bertanya "kenapa barang ini dulu ditolak?". Alasan
#: yang tidak bisa dipakai orang lain sama saja dengan kolom kosong yang terisi.
MIN_REASON = 15
#: Peran yang boleh melepas tahanan (keputusan pemilik #5: **manajer**).
HOLD_RELEASE_ROLES: Tuple[str, ...] = ("admin", "manager")


class InspectionError(ValueError):
    """Kesalahan ber-kalimat siap tampil (Bahasa Indonesia)."""


# ═════════════════════════════════════════════════════════════════════════════
#  Util
# ═════════════════════════════════════════════════════════════════════════════
def _today() -> str:
    # Cek UI UAT v3 (S8) — Tanggal SPK = hari kerja WIB (dulu potongan ISO UTC: SPK 22 Okt dini hari tertulis 21 Okt).
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat()


async def _policy(entity_id: str) -> Dict[str, str]:
    """Kebijakan selisih warna & handfeel yang BERLAKU (config, bukan `if` di kode)."""
    from services.config_resolver import value_of
    ctx = {"entity_id": entity_id or ""}
    color = str(await value_of("qc.color_mismatch_action", ctx) or "tahan").lower()
    hand = str(await value_of("qc.handfeel_mismatch_action", ctx) or "peringatkan").lower()
    if color not in MISMATCH_ACTIONS:
        color = "tahan"
    if hand not in MISMATCH_ACTIONS:
        hand = "peringatkan"
    return {"color": color, "handfeel": hand}


def required_checks(total: int, pct: int, minimum: int) -> int:
    """UAT 24 Okt (P11.2/P11.3) — jumlah roll minimal yang wajib dicek dari `total` (persen dibulatkan ke atas, tidak
    kurang dari `minimum`, tidak lebih dari `total`, minimal 1). pct ≥ 100 → semua."""
    import math
    if total <= 0:
        return 0
    if pct >= 100:
        return total
    need = max(math.ceil(total * max(pct, 0) / 100.0), int(minimum or 1), 1)
    return min(need, total)


async def sampling_rule(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Rencana sampling yang BERLAKU untuk satu SPK: MD Quality (`md_only`) atau QC 4-point. Lainnya: semua roll."""
    from services.config_resolver import value_of
    ctx = {"entity_id": doc.get("entity_id") or ""}
    lines = [ln for ln in doc.get("lines") or [] if ln.get("roll_id")]
    total = len(lines)
    if doc.get("md_only"):
        pct = int(await value_of("qc.md_sampling_pct", ctx) or 0)
        mn = int(await value_of("qc.md_sampling_min", ctx) or 1)
        checked = sum(1 for ln in lines if ln.get("md_quality_at"))
        part = "md_quality"
    elif doc.get("kind") == KIND_QC_4POINT:
        raw = await value_of("qc.sampling_pct", ctx)
        pct = 100 if raw in (None, "") else int(raw)
        mn = int(await value_of("qc.sampling_min", ctx) or 1)
        checked = sum(1 for ln in lines if ln.get("qc_at"))
        part = "qc"
    else:
        return {"part": "", "total": total, "required": total, "checked": 0, "pct": 100, "min": total}
    return {"part": part, "total": total, "required": required_checks(total, pct, mn), "checked": checked,
            "pct": pct, "min": mn}


async def get_one(ins_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLL].find_one({"id": ins_id}, {"_id": 0})
    return safe_doc(doc) if doc else None


async def _load(ins_id: str) -> Dict[str, Any]:
    doc = await db[COLL].find_one({"id": ins_id}, {"_id": 0})
    if not doc:
        raise InspectionError("Dokumen inspeksi tidak ditemukan.")
    return doc


def _line_of(doc: Dict[str, Any], line_id: str) -> Dict[str, Any]:
    for ln in (doc.get("lines") or []):
        if ln.get("id") == line_id:
            return ln
    raise InspectionError("Baris inspeksi tidak ditemukan di dokumen ini.")


def _assert_status(doc: Dict[str, Any], allowed: Tuple[str, ...], what: str) -> None:
    if str(doc.get("status") or "") not in allowed:
        raise InspectionError(
            f"Inspeksi berstatus \u201c{STATUS_LABEL.get(doc.get('status'), doc.get('status'))}\u201d "
            f"tidak bisa {what}.")


def stdrt_points(points: Any, length_yard: Any, width_cm: Any) -> Optional[float]:
    """Trial 22 Okt (F5) — STDRT kertas inspect = poin per 100 yard persegi = poin × 3600 ÷ (yard diinspeksi × lebar
    inci). None bila panjang/lebar belum ada (lebar disimpan cm → inci = cm ÷ 2,54)."""
    try:
        p, ln, w = float(points or 0), float(length_yard or 0), float(width_cm or 0) / 2.54
    except (TypeError, ValueError):
        return None
    if ln <= 0 or w <= 0:
        return None
    return round(p * 3600.0 / (ln * w), 2)


def summarize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan dokumen — DIHITUNG dari `lines[]`, tidak pernah dikirim klien.

    Dua satuan (FASE U) memakai bentuk KANONIK repo ini: `qty_rolls` + `quantity` +
    `unit` **datar** di setiap baris — bukan objek `qty{}` tersendiri. Alasannya bukan
    selera: `dual_qty_service.stamp()`, `core_utils.qty_dual()`, `<QtyDual/>`,
    `qtyDualCsv`, mesin PDF, dan penjaga `INV-QTY-01` semuanya membaca nama field itu.
    Bentuk ketiga untuk fakta yang sama = tepat kelas bug yang FASE U tutup.

    `rolls` dijumlahkan dari `qty_rolls` (None = "belum diisi", jadi tidak ikut dan
    tidak dipalsukan menjadi 0). `measure` dijumlahkan HANYA bila satuan seluruh baris
    sama — mencampur meter dengan kilogram menghasilkan angka yang terlihat benar dan
    menyesatkan.
    """
    lines = doc.get("lines") or []
    units = {str(ln.get("unit") or "") for ln in lines}
    units.discard("")
    measure = None
    if len(units) == 1:
        measure = round(sum(float(ln.get("quantity") or 0) for ln in lines), 2)
    roll_vals = [ln.get("qty_rolls") for ln in lines
                 if ln.get("qty_rolls") not in (None, "")]
    grades: Dict[str, int] = {}
    for ln in lines:
        g = str(ln.get("grade_after") or "").strip()
        if g:
            grades[g] = grades.get(g, 0) + 1
    return {
        "lines": len(lines),
        "rolls": (int(sum(float(v) for v in roll_vals)) if roll_vals else None),
        "measure": measure,
        "unit": (list(units)[0] if len(units) == 1 else ""),
        "points_total": round(sum(float(ln.get("points_snapshot") or 0)
                                  for ln in lines), 2),
        "grade_after_counts": grades,
        "inspected": sum(1 for ln in lines if ln.get("inspected_at")),
        # UAT 24 Okt (P11) — `inspected` mencampur MD & QC; dua hitungan terpisah untuk indikator sampling.
        "md_checked": sum(1 for ln in lines if ln.get("md_quality_at")),
        "qc_checked": sum(1 for ln in lines if ln.get("qc_at")),
        "color_mismatch": sum(1 for ln in lines
                              if str(ln.get("color_result") or "") not in ("", "sesuai")),
        "handfeel_mismatch": sum(1 for ln in lines
                                 if str(ln.get("handfeel_result") or "") not in ("", "sesuai")),
        "hold": sum(1 for ln in lines if ln.get("hold")),
        "rejected": sum(1 for ln in lines if str(ln.get("decision") or "") == "tolak"),
    }


async def _save(doc: Dict[str, Any], event: str, label: str, actor: Dict[str, Any],
                note: str = "", **fields: Any) -> Dict[str, Any]:
    """Satu pintu simpan: ringkasan selalu ikut dihitung, riwayat selalu bertambah."""
    merged = {**doc, **fields}
    fields["summary"] = summarize(merged)
    fields["updated_at"] = now_iso()
    await db[COLL].update_one(
        {"id": doc["id"]},
        {"$set": fields,
         "$push": {"history": timeline_entry(event, label, actor.get("name", ""), note)}})
    return safe_doc(await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}))


# ═════════════════════════════════════════════════════════════════════════════
#  Baris dokumen — dibangun dari kenyataan (roll / barang retur), bukan diketik
# ═════════════════════════════════════════════════════════════════════════════
async def _lines_from_rolls(rolls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    pids = list({r.get("product_id") for r in rolls if r.get("product_id")})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}},
        {"_id": 0, "id": 1, "sku": 1, "name": 1, "gramasi": 1, "lebar": 1,
         "color_id": 1, "color_code": 1, "line_code": 1}).to_list(2000)}
    out: List[Dict[str, Any]] = []
    for r in sorted(rolls, key=lambda x: str(x.get("roll_no") or "")):
        p = prods.get(r.get("product_id"), {})
        insp = r.get("inspection") or {}
        out.append({
            "id": new_id("insl"),
            "roll_id": r.get("id", ""), "roll_no": r.get("roll_no", ""),
            "lot": r.get("lot", ""), "dye_lot": r.get("dye_lot", ""),
            "product_id": r.get("product_id", ""), "sku": p.get("sku", ""),
            "article": p.get("name", ""),
            "color_id": p.get("color_id", ""), "color_code": p.get("color_code", ""),
            "gsm_standard": p.get("gramasi"), "width_standard": p.get("lebar"),
            # FASE U — dua satuan dalam bentuk KANONIK & datar: satu baris = satu roll
            # fisik (`qty_rolls`) + ukurannya (`quantity` + `unit`). Nama field ini
            # dibaca `<QtyDual/>`, `qtyDualCsv`, mesin PDF, dan INV-QTY-01.
            "qty_rolls": 1,
            "quantity": float(r.get("length_remaining") or r.get("length_initial") or 0),
            "unit": r.get("unit", "meter"),
            "points_snapshot": insp.get("points"),
            "grade_before": r.get("grade", ""), "grade_after": "",
            "gsm_actual": insp.get("gsm_actual"), "width_actual": insp.get("width_actual"),
            "color_result": "", "handfeel_result": "", "handfeel_score": None,
            "delta_e": None, "decision": "", "remark": "",
            "hold": False, "hold_reason": "",
            "inspected_by": "", "inspected_at": "",
        })
    return out


async def _lines_from_return_rolls(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    """23 Okt (permintaan pemilik) — SPK retur PELANGGAN: SATU BARIS PER ROLL klaim, diperiksa dengan form 4-point
    yang sama dengan QC penerimaan. Baris retur tanpa roll (data lama) tetap satu baris per barang.
    Hasil per roll ditulis ke retur saat SPK ditutup (`return_service.complete_inspection_from_spk`)."""
    rids = [r for it in ret.get("items") or [] for r in (it.get("roll_ids") or [])]
    rolls = {r["id"]: r for r in await db.inventory_rolls.find(
        {"id": {"$in": rids}}, {"_id": 0, "id": 1, "roll_no": 1, "lot": 1, "dye_lot": 1, "grade": 1}).to_list(len(rids) + 1)}
    pids = list({it.get("product_id") for it in ret.get("items") or [] if it.get("product_id")})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": pids}}, {"_id": 0, "id": 1, "sku": 1, "name": 1, "gramasi": 1, "lebar": 1,
                                "color_id": 1, "color_code": 1}).to_list(len(pids) + 1)}
    out: List[Dict[str, Any]] = []
    for idx, it in enumerate(ret.get("items") or []):
        if not it.get("roll_ids"):
            for ln in _lines_from_return_items({"items": [it]}):
                ln["return_item_index"] = idx
                out.append(ln)
            continue
        p = prods.get(it.get("product_id"), {})
        det = it.get("roll_details") or {}
        for rid in it["roll_ids"]:
            r = rolls.get(rid, {})
            d = det.get(rid) or {}
            out.append({
                "id": new_id("insl"), "roll_id": rid, "roll_no": r.get("roll_no", "") or rid,
                "return_item_index": idx, "lot": r.get("lot", ""), "dye_lot": r.get("dye_lot", ""),
                "product_id": it.get("product_id", ""), "sku": p.get("sku", "") or it.get("sku", ""),
                "article": p.get("name", "") or it.get("product_name", ""),
                "color_id": p.get("color_id", ""), "color_code": p.get("color_code", ""),
                "gsm_standard": p.get("gramasi"), "width_standard": p.get("lebar"),
                "qty_rolls": 1, "quantity": float((it.get("roll_qtys") or {}).get(rid) or 0),
                "unit": it.get("unit", "meter"),
                # Klaim pelanggan atas roll ini — konteks bagi petugas QC (bukan hasil QC).
                "claim": {k: d.get(k) for k in ("reason", "condition", "hangtag_missing", "cut_by_customer") if k in d},
                "points_snapshot": None, "grade_before": r.get("grade", ""), "grade_after": "",
                "gsm_actual": None, "width_actual": None,
                "color_result": "", "handfeel_result": "", "handfeel_score": None,
                "delta_e": None, "decision": "", "remark": "", "hold": False, "hold_reason": "",
                "inspected_by": "", "inspected_at": "",
            })
    return out


def _lines_from_return_items(ret: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Baris untuk retur — MENUNJUK barang retur, tidak menyalin hasil inspeksinya.

    SSOT hasil per barang tetap `sales_returns.items[].inspection` (`return_service`).
    Yang hidup di sini hanya pekerjaan pemeriksaannya (siapa, kapan, keputusan).
    """
    out: List[Dict[str, Any]] = []
    for idx, it in enumerate(ret.get("items") or []):
        out.append({
            "id": new_id("insl"),
            "roll_id": "", "roll_no": "",
            "return_item_index": idx,
            "lot": it.get("lot", ""), "dye_lot": it.get("dye_lot", ""),
            "product_id": it.get("product_id", ""), "sku": it.get("sku", ""),
            "article": it.get("product_name", "") or it.get("name", ""),
            "color_id": "", "color_code": "",
            "gsm_standard": None, "width_standard": None,
            # FASE U — bentuk kanonik & datar. `qty_rolls` boleh None: retur LAMA
            # memang tidak menyebut jumlah gulungan, dan "—" lebih jujur dari "0 roll".
            "qty_rolls": (None if it.get("qty_rolls") in (None, "")
                          else int(it.get("qty_rolls"))),
            # 23 Okt — retur jual menyimpan `quantity_returned`; dulu hanya `quantity` dibaca → baris SPK retur 0.
            "quantity": float(it.get("quantity") or it.get("quantity_returned") or 0),
            "unit": it.get("unit", "meter"),
            "points_snapshot": None,
            "grade_before": (it.get("inspection") or {}).get("grade", ""),
            "grade_after": "",
            "gsm_actual": None, "width_actual": None,
            "color_result": "", "handfeel_result": "", "handfeel_score": None,
            "delta_e": None, "decision": "", "remark": "",
            "hold": False, "hold_reason": "",
            "inspected_by": "", "inspected_at": "",
        })
    return out


# ═════════════════════════════════════════════════════════════════════════════
#  Order makloon — SATU definisi untuk "nomor · mitra · barang hasilnya"
# ═════════════════════════════════════════════════════════════════════════════
# Ketiga fakta ini dibaca DUA permukaan: pemilih dokumen di pop-up "Buat SPK"
# (`GET /api/inspections/meta/ref-docs`) dan pembuat dokumennya (`create`). Ditulis
# SEKALI di sini supaya label yang dilihat kepala gudang sama dengan isi dokumen yang
# lahir — kalau dua tempat menghitungnya masing-masing, pemilih bisa berkata
# "MKO-00003 · CV Celup Warna Abadi" sementara SPK-nya lahir tanpa nama mitra.
#
# TERUKUR 2026-08-23 (kenapa helper ini ada, bukan selera gaya): versi pertama
# `create()` membaca `mko["number"]`, `mko["makloon_name"]`, dan mencari roll lewat
# `inventory_rolls.makloon_order_id`. **Ketiganya tidak ada:**
#   * nomor order makloon disimpan di **`mko_number`** (`number` = 0 dokumen);
#   * `makloon_id`/`makloon_name` hidup di **`steps[]`** — mitra bisa berbeda per tahap
#     (MKO-00004 lewat 3 mitra);
#   * `inventory_rolls` **tidak punya** `makloon_order_id` (0 dari 66 roll). Penaut yang
#     nyata: `steps[].output_lot_ids` → `inventory_rolls.lot_id`.
# Akibatnya SPK hasil makloon lahir tanpa nomor acuan, tanpa nama mitra, dan **NOL
# BARIS** (diukur: `KSC/INS-00005` lahir `lines=[]`) — dokumen yang tidak bisa
# diperiksa siapa pun, dan tidak ada galat yang memberi tahu. Persis kelas cacat yang
# paling mahal di repo ini: bukan error, tetapi dokumen yang tenang-tenang kosong.
def makloon_ref_number(mko: Dict[str, Any]) -> str:
    """Nomor order makloon: **`mko_number`** (`number` hanya cadangan dokumen lama)."""
    return str(mko.get("mko_number") or mko.get("number") or "")


def makloon_output_lot_ids(mko: Dict[str, Any]) -> List[str]:
    """Lot HASIL order makloon — satu-satunya penaut nyata ke roll fisiknya."""
    out: List[str] = []
    for s in (mko.get("steps") or []):
        out.extend(str(x) for x in (s.get("output_lot_ids") or []) if x)
        if s.get("output_lot_id"):
            out.append(str(s["output_lot_id"]))
    return sorted(set(out))


def makloon_vendor(mko: Dict[str, Any]) -> Tuple[str, str]:
    """Mitra yang MENYERAHKAN hasil akhir (tahap ber-output dengan `seq` terbesar).

    Order makloon berantai bisa melewati beberapa mitra. Yang diinspeksi adalah barang
    yang DISERAHKAN, jadi nama yang wajib tercetak di SPK adalah mitra tahap terakhir
    yang benar-benar mengeluarkan hasil — bukan mitra tahap pertama (yang mungkin hanya
    menenun bahan setengah jadi dan sudah dinilai di SPK sebelumnya).
    """
    steps = sorted((mko.get("steps") or []), key=lambda s: int(s.get("seq") or 0))
    pilih: Dict[str, Any] = {}
    for s in steps:
        if (s.get("output_lot_ids") or s.get("output_lot_id")) and s.get("makloon_name"):
            pilih = s
    if not pilih:
        for s in steps:
            if s.get("makloon_name"):
                pilih = s
    return (str(pilih.get("makloon_id") or ""), str(pilih.get("makloon_name") or ""))


async def spk_for_ref(kind: str, ref_id: str,
                      statuses: Optional[Tuple[str, ...]] = None) -> Dict[str, Any]:
    """SPK yang SUDAH ADA untuk dokumen sumber ini (dict kosong bila belum ada).

    Dipakai dua arah: pemilih dokumen MENANDAINYA ("sudah ada SPK …") dan `create()`
    MENOLAK menerbitkan SPK kedua selama SPK lamanya masih terbuka. Tanpa pagar ini
    `sales_returns.inspection_id` — satu field, satu nilai — akan menunjuk SPK terbaru
    dan SPK lama jadi yatim yang tetap mengaku memeriksa retur itu; garis waktu retur
    lalu menyebut nomor yang salah tanpa satu pun galat muncul.
    """
    if not (kind and ref_id):
        return {}
    q: Dict[str, Any] = {"kind": kind, "ref_doc_id": ref_id}
    if statuses:
        q["status"] = {"$in": list(statuses)}
    return await db[COLL].find_one(
        q, {"_id": 0, "id": 1, "number": 1, "status": 1, "kind": 1}) or {}


async def _baseline_for(product_ids: List[str], entity_id: str, supplier_id: str = "") -> Dict[str, str]:
    """Acuan sample yang di-ACC untuk produk ini (FASE S → `md_samples` + kontraknya).

    Petugas inspect butuh tahu "dibandingkan dengan apa". Tanpa acuan yang disebut
    NAMANYA, kolom "warna sesuai?" hanya jadi pendapat. P17 DESIGN-02 — bila supplier
    barang diketahui, sample yang DIMENANGKAN supplier itu didahulukan (bukan sekadar
    sample terbaru produk yang mungkin dimenangkan supplier lain).
    """
    if not product_ids:
        return {}
    q = {"status": "decided", "entity_id": entity_id}
    rows = await db.md_samples.find(
        q, {"_id": 0, "id": 1, "number": 1, "product_id": 1, "spec_id": 1,
            "color_target": 1, "decision": 1, "sample_types": 1}
    ).sort("created_at", -1).to_list(300)
    specs = {}
    spec_ids = [r.get("spec_id") for r in rows if r.get("spec_id")]
    if spec_ids:
        specs = {s["id"]: s for s in await db.md_specs.find(
            {"id": {"$in": spec_ids}},
            {"_id": 0, "id": 1, "product_id": 1}).to_list(300)}
    matches = [r for r in rows
               if (r.get("product_id") or (specs.get(r.get("spec_id"), {}) or {}).get("product_id")) in product_ids]
    own = [r for r in matches if supplier_id and (r.get("decision") or {}).get("supplier_id") == supplier_id]
    for r in own or matches:
        color = r.get("color_target") or {}
        return {
            "baseline_sample_id": r.get("id", ""),
            "baseline_sample_number": r.get("number", ""),
            "baseline_contract_id": (r.get("decision") or {}).get("contract_id", ""),
            "baseline_round_no": (r.get("decision") or {}).get("round_no"),
            "baseline_supplier_id": (r.get("decision") or {}).get("supplier_id", ""),
            "baseline_color": (f"{color.get('name', '')}"
                               f"{' (' + color.get('code', '') + ')' if color.get('code') else ''}"
                               ).strip(),
        }
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
#  LAHIR: manual (SPK) & OTOMATIS (penerimaan PO masuk antrean QC)
# ═══════════════════════════════════════════════════════════════════════════════
async def _new_doc(*, kind: str, entity_id: str, actor: Dict[str, Any],
                   ref_doc_type: str = "", ref_doc_id: str = "", ref_doc_number: str = "",
                   task_id: str = "", supplier: Tuple[str, str] = ("", ""),
                   customer: Tuple[str, str] = ("", ""), line_code: str = "",
                   lines: Optional[List[Dict[str, Any]]] = None,
                   spk_date: str = "", assigned: Tuple[str, str, str] = ("", "", ""),
                   remark: str = "") -> Dict[str, Any]:
    """Rakit + simpan satu dokumen inspeksi (satu jalan lahir, dipakai kedua pintu)."""
    if not entity_id or entity_id == "all":
        raise InspectionError(
            "Pilih satu badan usaha dulu — dokumen inspeksi selalu milik satu badan usaha.")
    if kind not in KIND_LABEL:
        raise InspectionError(f"Jenis inspeksi harus salah satu: {', '.join(KIND_LABEL)}.")
    rows = list(lines or [])
    baseline = await _baseline_for([r.get("product_id") for r in rows if r.get("product_id")],
                                  entity_id, supplier[0])
    now = now_iso()
    assigned_id, assigned_name, bagian = assigned
    doc: Dict[str, Any] = {
        "id": new_id("ins"),
        "number": await next_doc_number(COLL, "number", "INS-", entity_id=entity_id),
        "entity_id": entity_id,
        # FASE L — snapshot lini: papan printing tidak boleh menampilkan pekerjaan woven.
        "line_code": line_scope.norm(line_code),
        "kind": kind,
        "ref_doc_type": ref_doc_type, "ref_doc_id": ref_doc_id,
        "ref_doc_number": ref_doc_number,
        "task_id": task_id,
        "supplier_id": supplier[0], "supplier_name": supplier[1],
        "customer_id": customer[0], "customer_name": customer[1],
        "spk_date": (spk_date or "").strip() or _today(),
        "assigned_to": assigned_id, "assigned_name": assigned_name,
        "bagian": (bagian or "").strip() or "Bagian Inspect",
        "started_at": "", "finished_at": "",
        "status": STATUS_ASSIGNED if assigned_id else STATUS_DRAFT,
        **{"baseline_sample_id": "", "baseline_sample_number": "",
           "baseline_contract_id": "", "baseline_color": ""},
        **baseline,
        "lines": rows,
        # Trial 22 Okt (E9) — SPK penerimaan PO/makloon BARU = SPK MD Quality saja (warna/handfeel); QC 4-point dibuat
        # sebagai SPK tersendiri. Dokumen lama (tanpa penanda) tetap berisi dua bagian seperti sebelumnya.
        "md_only": kind in MD_QUALITY_KINDS,
        "decision": "", "decision_label": "", "remark": (remark or "").strip(),
        "reject_reason": "", "reopen_reason": "",
        "created_by": actor.get("name", ""), "created_by_id": actor.get("id", ""),
        "created_at": now, "updated_at": now,
        "history": [timeline_entry("created", f"{KIND_LABEL[kind]} dibuat",
                                   actor.get("name", ""),
                                   ref_doc_number or task_id or "")],
    }
    doc["summary"] = summarize(doc)
    if assigned_id:
        doc["history"].append(timeline_entry(
            "assigned", f"Ditugaskan ke {assigned_name}", actor.get("name", ""),
            doc["bagian"]))
    await db[COLL].insert_one(dict(doc))
    # FASE G-4 — jejak dua arah ke dokumen sumbernya, supaya "inspeksi ini milik PO
    # mana" bisa dijawab dari dua sisi (dan `INV-REF-01` tidak menuduh yatim).
    if ref_doc_type and ref_doc_id:
        try:
            from services import doc_refs_service as _refs
            await _refs.safe_link(("inspection", doc["id"]), (ref_doc_type, ref_doc_id),
                                  "parent", note="inspeksi atas dokumen ini")
        except Exception:  # noqa: BLE001 — relasi hilang tak boleh menggagalkan SPK
            import logging
            logging.getLogger(__name__).warning(
                "INS: gagal menaut %s -> %s/%s", doc["number"], ref_doc_type, ref_doc_id)
    # Acuan sample yang di-ACC ikut tertaut — supaya pertanyaan "atas dasar apa warna
    # ini dinilai?" bisa dijawab dari DUA sisi (dokumen inspeksi ⇄ sample). Relasinya
    # `references`, BUKAN `parent`: inspeksi tidak lahir dari sample.
    if doc.get("baseline_sample_id"):
        try:
            from services import doc_refs_service as _refs
            await _refs.safe_link(("inspection", doc["id"]),
                                  ("md_sample", doc["baseline_sample_id"]),
                                  "references",
                                  note=f"acuan {doc.get('baseline_sample_number') or 'sample'}")
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).warning(
                "INS: gagal menaut acuan sample %s", doc.get("baseline_sample_number"))
    return safe_doc(doc)


# FE-04 (review 2026-10-20) — petugas inspeksi = akun AKTIF yang perannya (termasuk peran kustom)
# punya kemampuan inspect, dan ditugaskan di badan usaha dokumen. Dulu daftar nama peran tetap.
INSPECT_CAPABILITIES = (("inspection", "inspect"), ("qc", "inspect"), ("md_quality", "inspect"))
_OFFICER_PROJ = {"_id": 0, "id": 1, "name": 1, "division": 1, "role": 1, "status": 1,
                 "home_entity_id": 1, "allowed_entity_ids": 1}


async def officer_roles() -> set:
    from dependencies import permission_matrix
    matrix = await permission_matrix()

    def capable(perms: Dict[str, Any]) -> bool:
        return any(a in (perms.get(r) or []) or "*" in (perms.get(r) or []) for r, a in INSPECT_CAPABILITIES)
    return {role for role, perms in matrix.items() if capable(perms or {})}


async def _officer_ok(u: Dict[str, Any], roles: set, entity_id: str) -> bool:
    from entity_scope import allowed_entities_for
    if (u.get("status") or "active") != "active" or u.get("role") not in roles:
        return False
    return not entity_id or entity_id in await allowed_entities_for(u)


async def eligible_officers(entity_id: str) -> List[Dict[str, Any]]:
    roles = await officer_roles()
    out = []
    async for u in db.users.find({"role": {"$in": sorted(roles)}, "status": "active"}, _OFFICER_PROJ).sort("name", 1):
        if await _officer_ok(u, roles, entity_id):
            out.append(u)
    return out


async def _resolve_assignee(user_id: str, entity_id: str = "") -> Tuple[str, str, str]:
    if not (user_id or "").strip():
        return "", "", ""
    u = await db.users.find_one({"id": user_id}, _OFFICER_PROJ)
    if not u:
        raise InspectionError("Petugas yang dipilih tidak ditemukan.")
    if not await _officer_ok(u, await officer_roles(), entity_id):
        raise InspectionError(f"{u.get('name') or 'Akun ini'} tidak berwenang/tidak ditugaskan sebagai petugas inspeksi "
                              "di badan usaha ini.")
    return u.get("id", ""), u.get("name", ""), u.get("division", "") or ""


async def create(payload: Dict[str, Any], actor: Dict[str, Any],
                 entity_id: str) -> Dict[str, Any]:
    """SPK inspeksi manual (mis. inspeksi retur, barang pengganti, hasil makloon)."""
    kind = str(payload.get("kind") or "").strip().lower()
    ref_type = str(payload.get("ref_doc_type") or "").strip()
    ref_id = str(payload.get("ref_doc_id") or "").strip()
    task_id = str(payload.get("task_id") or "").strip()
    lines: List[Dict[str, Any]] = []
    ref_number = supplier = customer = None
    supplier = ("", "")
    customer = ("", "")
    ref_number = ""
    line_code = str(payload.get("line_code") or "")

    if kind == KIND_PO_RECEIPT:
        if not task_id:
            raise InspectionError(
                "Inspeksi penerimaan PO lahir dari TUGAS penerimaan — sebutkan tugasnya "
                "(biasanya dokumen ini dibuat otomatis saat barang masuk antrean QC).")
        task = await db.wms_tasks.find_one({"id": task_id}, {"_id": 0})
        if not task:
            raise InspectionError("Tugas penerimaan tidak ditemukan.")
        return await ensure_for_qc_task(task, actor, force=True)

    if kind in (KIND_RETURN_CUSTOMER, KIND_REPLACEMENT):
        if not ref_id:
            raise InspectionError("Sebutkan nomor retur yang mau diperiksa.")
        ret = await db.sales_returns.find_one({"id": ref_id}, {"_id": 0})
        if not ret:
            raise InspectionError("Dokumen retur tidak ditemukan.")
        if (ret.get("entity_id") or "") != entity_id:
            raise InspectionError(
                "Retur itu milik badan usaha lain — inspeksinya harus dibuat dari badan "
                "usaha pemilik returnya.")
        ref_type, ref_number = "sales_return", ret.get("number", "")
        customer = (ret.get("customer_id", ""), ret.get("customer_name", ""))
        lines = await _lines_from_return_rolls(ret) if kind == KIND_RETURN_CUSTOMER else _lines_from_return_items(ret)
        if kind == KIND_REPLACEMENT:
            # L05 LN-050-T02 — SPK pengganti memeriksa ROLL PENGGANTI (dipilih/scan), bukan barang returnya.
            rids = [str(x) for x in (payload.get("roll_ids") or []) if x]
            if not rids:
                raise InspectionError("Pilih/scan roll PENGGANTI yang mau diperiksa (bukan roll returnya).")
            returned = {str(it.get("roll_id")) for it in ret.get("items") or [] if it.get("roll_id")}
            rolls = await db.inventory_rolls.find({"$or": [{"id": {"$in": rids}}, {"roll_no": {"$in": rids}}],
                                                   "owner_entity_id": entity_id}, {"_id": 0}).to_list(len(rids) * 2)
            if returned & {r["id"] for r in rolls}:
                raise InspectionError("Roll retur tidak boleh diperiksa sebagai barang pengganti.")
            matched = {t for t in rids if any(t in (r["id"], r.get("roll_no")) for r in rolls)}
            bad = [r.get("roll_no") for r in rolls if r.get("status") not in ("available", "reserved", "quarantine", "hold")]
            if bad:
                raise InspectionError(f"Roll pengganti berstatus tidak bisa diperiksa (terjual/terpakai): {', '.join(bad)}.")
            if matched != set(rids):
                raise InspectionError("Sebagian roll pengganti tidak ditemukan / di luar badan usaha ini.")
            lines = await _lines_from_rolls(rolls)
        line_code = line_code or str(ret.get("line_code") or "")
    elif kind == KIND_SALES_ORDER:
        so = await db.sales_orders.find_one({"id": ref_id}, {"_id": 0, "id": 1, "number": 1, "entity_id": 1,
                                                          "customer_id": 1, "customer_name": 1, "qc_request": 1})
        if not so:
            raise InspectionError("Pesanan (SO) tidak ditemukan.")
        qr = so.get("qc_request") or {}
        if qr.get("mode") not in ("full", "sampling"):
            raise InspectionError("Pesanan ini tidak meminta QC saat checkout — tidak ada kebutuhan QC.")
        dup = await db[COLL].find_one({"kind": KIND_SALES_ORDER, "ref_doc_id": so["id"],
                                       "status": {"$nin": [STATUS_DONE, STATUS_CLOSED, "cancelled"]}}, {"_id": 0, "number": 1})
        if dup:
            raise InspectionError(f"SPK QC pesanan {dup.get('number')} masih berjalan — selesaikan dulu.")
        from services.loading_check_service import so_alloc_rolls
        rolls = await so_alloc_rolls(so["id"])
        if not rolls:
            raise InspectionError("Belum ada roll teralokasi untuk pesanan ini — alokasikan dulu.")
        if qr["mode"] == "sampling":
            import math
            import random
            n = max(1, math.ceil(len(rolls) * float(qr.get("sample_pct") or 10) / 100))
            rolls = random.sample(rolls, min(n, len(rolls)))
        ref_type, ref_number = "sales_order", so.get("number", "")
        customer = (so.get("customer_id", ""), so.get("customer_name", ""))
        lines = await _lines_from_rolls(rolls)
    elif kind == KIND_RETURN_SUPPLIER:
        if not ref_id:
            raise InspectionError("Sebutkan nomor retur pembelian yang mau diperiksa.")
        pret = await db.purchase_returns.find_one({"id": ref_id}, {"_id": 0})
        if not pret:
            raise InspectionError("Dokumen retur pembelian tidak ditemukan.")
        # Pagar badan usaha yang SAMA dengan jalur retur jual di atas. Sempat hanya ada
        # di satu dari tiga jalur — dan pagar yang berlubang di satu jalur bukan pagar:
        # payload bisa menyebut id dokumen PT lain meski pemilihnya sudah ter-scope.
        if (pret.get("entity_id") or "") != entity_id:
            raise InspectionError(
                "Retur pembelian itu milik badan usaha lain — inspeksinya harus dibuat "
                "dari badan usaha pemilik dokumennya.")
        ref_type, ref_number = "purchase_return", pret.get("number", "")
        supplier = (pret.get("supplier_id", ""), pret.get("supplier_name", ""))
        lines = _lines_from_return_items(pret)
        line_code = line_code or str(pret.get("line_code") or "")
    elif kind == KIND_MAKLOON_OUTPUT:
        if not ref_id:
            raise InspectionError("Sebutkan order makloon yang hasilnya mau diperiksa.")
        mko = await db.makloon_orders.find_one({"id": ref_id}, {"_id": 0})
        if not mko:
            raise InspectionError("Order makloon tidak ditemukan.")
        if (mko.get("entity_id") or "") != entity_id:
            raise InspectionError(
                "Order makloon itu milik badan usaha lain — inspeksinya harus dibuat "
                "dari badan usaha pemilik dokumennya.")
        ref_type = "makloon_order"
        ref_number = makloon_ref_number(mko)
        supplier = makloon_vendor(mko)
        lot_ids = makloon_output_lot_ids(mko)
        rolls = (await db.inventory_rolls.find(
            {"lot_id": {"$in": lot_ids}}, {"_id": 0}).to_list(500)) if lot_ids else []
        if not rolls:
            # SPK tanpa barang adalah dokumen yang tidak bisa diperiksa siapa pun.
            # Lebih baik menolak dengan kalimat menuntun daripada menerbitkan dokumen
            # kosong yang baru terasa salah saat petugas membukanya di gudang.
            raise InspectionError(
                f"Order makloon {ref_number or '(tanpa nomor)'} belum menyerahkan hasil "
                "apa pun — belum ada gulungan yang bisa diperiksa. Terima dulu hasilnya "
                "di layar Order Makloon, lalu terbitkan SPK inspeksinya.")
        lines = await _lines_from_rolls(rolls)
        line_code = line_code or str(mko.get("line_code") or "")
    else:
        raise InspectionError(f"Jenis inspeksi harus salah satu: {', '.join(KIND_LABEL)}.")

    # ─── SPK kedua atas dokumen yang sama: DITOLAK selama yang lama masih terbuka ──
    # Pemeriksaan ulang punya pintunya sendiri (`reopen`, ber-alasan wajib). Tanpa pagar
    # ini dua SPK memeriksa barang yang sama, dan `sales_returns.inspection_id` (satu
    # field) hanya bisa menunjuk satu di antaranya — yang lain menjadi yatim yang tetap
    # mengaku memeriksa retur itu.
    lama = await spk_for_ref(kind, ref_id, OPEN_STATUSES)
    if lama:
        raise InspectionError(
            f"Dokumen ini sudah punya SPK yang masih berjalan: {lama.get('number')} "
            f"({STATUS_LABEL.get(str(lama.get('status')), '-')}). Lanjutkan SPK itu — "
            "atau buka kembali (reopen) bila sudah diputuskan — supaya tidak ada dua "
            "SPK memeriksa barang yang sama.")

    assigned = await _resolve_assignee(str(payload.get("assigned_to") or ""), entity_id)
    doc = await _new_doc(kind=kind, entity_id=entity_id, actor=actor,
                         ref_doc_type=ref_type, ref_doc_id=ref_id,
                         ref_doc_number=ref_number, supplier=supplier,
                         customer=customer, line_code=line_code, lines=lines,
                         spk_date=str(payload.get("spk_date") or ""),
                         assigned=assigned, remark=str(payload.get("remark") or ""))
    # FASE I.F — retur menyimpan SPK yang memeriksanya supaya garis waktu retur bisa
    # menyebut nomornya. Ditulis dari SINI saja (satu penulis untuk satu fakta).
    #
    # HANYA untuk `return_customer`: field `sales_returns.inspection_id` berarti "SPK
    # yang memeriksa BARANG RETURNYA", dan tonggak `inspect_done_at` diturunkan darinya.
    # SPK `replacement` memeriksa barang PENGGANTI — kejadian fisik yang lain — jadi
    # menulisinya ke field yang sama akan menggeser garis waktu retur ke dokumen yang
    # bukan pemeriksa returnya. Jejak dua arahnya tidak hilang: `_new_doc` sudah
    # menautkannya lewat `doc_refs_service` (terlihat di Jejak Dokumen).
    if kind == KIND_RETURN_CUSTOMER and ref_type == "sales_return" and ref_id:
        from services import return_service as _ret
        await _ret.attach_inspection(ref_id, doc["id"], doc.get("number", ""))
    return doc


async def ensure_for_qc_task(task: Dict[str, Any], actor: Dict[str, Any],
                             force: bool = False) -> Dict[str, Any]:
    """**IDEMPOTENT**: pastikan tugas penerimaan yang masuk antrean QC punya SPK-nya.

    Dipanggil dari jalur penerimaan (`inbound_receiving`) tepat saat tugas menjadi
    `qc_pending`. Kepala gudang tidak perlu membuat dokumen dari nol — user story I.1.
    Idempotent karena penerimaan bisa diselesaikan ulang / dipanggil ulang oleh POC;
    dokumen kedua untuk tugas yang sama akan membuat dua SPK atas barang yang sama.
    """
    task_id = str(task.get("id") or "")
    if not task_id:
        raise InspectionError("Tugas penerimaan tanpa id — tidak bisa dibuat SPK.")
    existing = await db[COLL].find_one({"task_id": task_id}, {"_id": 0})
    if existing and not force:
        return safe_doc(existing)
    if existing and force:
        return safe_doc(existing)

    po = None
    if task.get("po_id"):
        po = await db.purchase_orders.find_one(
            {"id": task["po_id"]},
            {"_id": 0, "id": 1, "po_number": 1, "supplier_id": 1, "supplier_name": 1,
             "entity_id": 1, "line_code": 1})
    entity_id = (po or {}).get("entity_id") or task.get("owner_entity_id") \
        or task.get("entity_id") or ""
    rolls = await db.inventory_rolls.find({"qc_task_id": task_id}, {"_id": 0}).to_list(500)
    lines = await _lines_from_rolls(rolls)
    return await _new_doc(
        kind=KIND_PO_RECEIPT, entity_id=entity_id, actor=actor,
        ref_doc_type="purchase_order" if po else "", ref_doc_id=(po or {}).get("id", ""),
        ref_doc_number=(po or {}).get("po_number", "") or task.get("po_number", ""),
        task_id=task_id,
        supplier=((po or {}).get("supplier_id", ""), (po or {}).get("supplier_name", "")),
        line_code=(po or {}).get("line_code", "") or task.get("line_code", ""),
        lines=lines,
        remark="SPK lahir otomatis saat barang masuk antrean QC.")


# ═══════════════════════════════════════════════════════════════════════════════
#  Alur: tugaskan → mulai → periksa baris → tutup dengan keputusan
# ═══════════════════════════════════════════════════════════════════════════════
async def assign(ins_id: str, payload: Dict[str, Any],
                 actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await _load(ins_id)
    _assert_status(doc, OPEN_STATUSES, "ditugaskan ulang")
    aid, aname, _div = await _resolve_assignee(str(payload.get("assigned_to") or ""), doc.get("entity_id") or "")
    if not aid:
        raise InspectionError("Pilih petugas inspect-nya dulu.")
    bagian = str(payload.get("bagian") or "").strip() or doc.get("bagian") or "Bagian Inspect"
    spk = str(payload.get("spk_date") or "").strip() or doc.get("spk_date") or _today()
    status = doc.get("status")
    if status == STATUS_DRAFT:
        status = STATUS_ASSIGNED
    saved = await _save(doc, "assigned", f"Ditugaskan ke {aname}", actor, bagian,
                        assigned_to=aid, assigned_name=aname, bagian=bagian,
                        spk_date=spk, status=status)
    # FASE N butir 4 — "SPK inspeksi ditugaskan ke SAYA". Sampai FASE I ditutup,
    # penugasan hanya terlihat bila petugasnya kebetulan membuka layar SPK Inspeksi;
    # tidak ada satu pun pemberitahuan. Alamatnya jelas dan tunggal (orang yang
    # ditugaskan), jadi ini justru contoh peristiwa yang TIDAK boleh ber-`recipient_role`
    # sama sekali — cukup `recipient_user`.
    try:
        from services import notification_service as notif
        await notif.create_notification(
            notif_type="inspection_assigned",
            title=f"SPK Inspeksi untuk Anda: {saved.get('number', '')}",
            body=(f"{KIND_LABEL.get(str(saved.get('kind') or ''), 'Inspeksi')} · "
                  f"{len(saved.get('lines') or [])} baris · bagian {bagian}. "
                  f"Ditugaskan oleh {actor.get('name', '')}."),
            severity="info", link="inspections",
            entity_id=saved.get("entity_id"),
            recipient_role="", recipient_user=aid,
            ref=f"ins_assigned:{saved.get('id', '')}:{aid}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("[assign] efek samping gagal diabaikan: %s", exc)  # KN-C10
    return saved


async def start(ins_id: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await _load(ins_id)
    _assert_status(doc, (STATUS_DRAFT, STATUS_ASSIGNED), "dimulai")
    if not doc.get("assigned_to"):
        raise InspectionError(
            "Tugaskan petugasnya dulu — SPK tanpa nama tidak bisa dipertanggungjawabkan.")
    return await _save(doc, "started", "Pemeriksaan dimulai", actor,
                       status=STATUS_IN_PROGRESS, started_at=now_iso())


async def inspect_line(ins_id: str, line_id: str, payload: Dict[str, Any],
                       actor: Dict[str, Any]) -> Dict[str, Any]:
    """Isi hasil SATU baris. Angka cacat & grade DIHITUNG mesin lama, bukan di sini.
    P05 IMP-16 — `part`: md_quality (warna/handfeel saja) · qc (4-point/ukur saja) · "" keduanya."""
    doc = await _load(ins_id)
    part = str(payload.get("part") or "").strip().lower()
    if part not in ("", "md_quality", "qc"):
        raise InspectionError("Bagian pemeriksaan harus md_quality atau qc.")
    if part == "md_quality" and doc.get("kind") in (KIND_RANDOM_CHECK, KIND_QC_4POINT):
        raise InspectionError("SPK ini hanya berisi pemeriksaan QC (4-point).")
    if doc.get("md_only"):
        if part == "qc":
            raise InspectionError("QC 4-point dikerjakan di SPK QC 4-point tersendiri — buat dari tombol "
                                  "'Buat SPK QC 4-point' di SPK ini.")
        part = "md_quality"
    elif doc.get("kind") == KIND_QC_4POINT:
        part = "qc"
    # F-13 (uji pra-UAT 2026-10-21, keputusan owner Q-06b) — MD Quality (seperti QC) baru boleh mengisi SESUDAH SPK
    # ditugaskan; dulu bagian md_quality boleh diisi saat SPK masih draft (hasil tanpa penanggung jawab).
    allowed = (STATUS_ASSIGNED, STATUS_IN_PROGRESS)
    if doc.get("status") == STATUS_DRAFT:
        raise InspectionError(
            f"SPK {doc.get('number', '')} belum ditugaskan — tugaskan petugas inspect dulu; MD Quality & QC baru bisa "
            "mengisi hasil sesudah SPK ditugaskan.")
    _assert_status(doc, allowed, "diisi hasilnya")
    line = _line_of(doc, line_id)
    color = str(payload.get("color_result") or "").strip().lower()
    hand = str(payload.get("handfeel_result") or "").strip().lower()
    if part == "qc":
        color = hand = ""
        payload = {**payload, "handfeel_score": None, "delta_e": None}
    if color and color not in COLOR_RESULTS:
        raise InspectionError(f"Hasil warna harus salah satu: {', '.join(COLOR_RESULTS)}.")
    if hand and hand not in HANDFEEL_RESULTS:
        raise InspectionError(f"Hasil handfeel harus salah satu: {', '.join(HANDFEEL_RESULTS)}.")
    decision = str(payload.get("decision") or "").strip().lower()
    if decision and decision not in DECISIONS:
        raise InspectionError(f"Keputusan baris harus salah satu: {', '.join(DECISIONS)}.")
    score = payload.get("handfeel_score")
    if score not in (None, "") and not (1 <= float(score) <= 5):
        raise InspectionError("Skor handfeel di luar batas wajar (1–5). Periksa angkanya.")

    pol = await _policy(doc.get("entity_id", ""))
    patch: Dict[str, Any] = {
        "color_result": color or line.get("color_result", ""),
        "handfeel_result": hand or line.get("handfeel_result", ""),
        "handfeel_score": (float(score) if score not in (None, "") else line.get("handfeel_score")),
        "delta_e": (float(payload["delta_e"]) if payload.get("delta_e") not in (None, "")
                    else line.get("delta_e")),
        "decision": decision or line.get("decision", ""),
        "inspected_by": actor.get("name", ""), "inspected_at": now_iso(),
    }
    # Trial 22 Okt (F4) — catatan MD Quality & QC disimpan TERPISAH (dulu satu `remark` → catatan QC menimpa MD).
    remark_key = {"md_quality": "md_remark", "qc": "qc_remark"}.get(part, "remark")
    patch[remark_key] = str(payload.get("remark") or line.get(remark_key, "") or "")
    if part == "":
        patch["remark"] = patch[remark_key]
    if part in ("", "qc"):
        # Trial 22 Okt (F5) — kolom kertas inspect: yard per grade (A/A1/B) & perbaikan (dicatat; grade roll tetap
        # dari aturan yang berlaku sampai pemilik memutuskan pecahan grade per yard).
        ys = payload.get("yard_split") or {}
        if ys:
            patch["yard_split"] = {k: round(float(ys.get(k) or 0), 2) for k in ("A", "A1", "B")}
        if payload.get("repair_note") is not None:
            patch["repair_note"] = str(payload.get("repair_note") or "")[:300]
    if part in ("", "md_quality"):
        patch.update({"md_quality_by": actor.get("name", ""), "md_quality_at": now_iso()})
    if part in ("", "qc"):
        patch.update({"qc_by": actor.get("name", ""), "qc_at": now_iso()})
    warnings: List[str] = []

    if line.get("roll_id") and doc.get("kind") != KIND_RETURN_CUSTOMER and part == "md_quality":
        roll = await db.inventory_rolls.find_one({"id": line["roll_id"]}, {"_id": 0})
        if not roll:
            raise InspectionError("Roll pada baris ini sudah tidak ada di gudang.")
        from services import qc_inspection_service as qc
        result = await qc.record_quality(
            roll, color_result=patch["color_result"], handfeel_result=patch["handfeel_result"],
            handfeel_score=patch["handfeel_score"], delta_e=patch["delta_e"],
            baseline_sample_id=doc.get("baseline_sample_id", ""),
            baseline_sample_number=doc.get("baseline_sample_number", ""),
            color_action=pol["color"], handfeel_action=pol["handfeel"], actor=actor,
            inspection_id=doc.get("id", ""), inspection_number=doc.get("number", ""))
        patch.update({"hold": bool(result["hold"].get("held")), "hold_reason": result["hold"].get("reason", "")})
        warnings = list(result.get("qc_warnings") or [])
    elif line.get("roll_id") and doc.get("kind") != KIND_RETURN_CUSTOMER:
        roll = await db.inventory_rolls.find_one({"id": line["roll_id"]}, {"_id": 0})
        if not roll:
            raise InspectionError("Roll pada baris ini sudah tidak ada di gudang.")
        from services import qc_inspection_service as qc
        hdr = await _form_header(doc, roll)
        try:
            qc.normalize_interval_defects(payload.get("defects") or [], payload.get("inspect_length_yard"))
        except qc.IntervalError as exc:
            raise InspectionError(str(exc)) from exc
        if str(payload.get("grade") or "").strip():   # KLX-02 — grade diisi user, wajib dari master aktif
            from services import grade_service as _gs
            try:
                _gs.normalize_or_raise(payload.get("grade"), "Grade QC")
            except Exception as exc:  # noqa: BLE001
                raise InspectionError(str(exc)) from exc
        try:
            result = await qc.inspect_roll(
                safe_doc(roll), [d for d in (payload.get("defects") or [])],
                payload.get("gsm_actual"), payload.get("width_actual"),
                str(payload.get("remark") or ""), actor,
                supplier_lot=str(payload.get("supplier_lot") or ""),
                dye_lot=str(payload.get("dye_lot") or ""),
                shade_ref=str(payload.get("shade_ref") or ""),
                color_result=patch["color_result"], handfeel_result=patch["handfeel_result"],
                handfeel_score=patch["handfeel_score"], delta_e=patch["delta_e"],
                baseline_sample_id=doc.get("baseline_sample_id", ""),
                baseline_sample_number=doc.get("baseline_sample_number", ""),
                color_action=pol["color"], handfeel_action=pol["handfeel"],
                inspection_id=doc.get("id", ""), inspection_number=doc.get("number", ""),
                quality_from_roll=(part == "qc"),
                inspect_length_yard=payload.get("inspect_length_yard"),
                header=hdr, grade_input=str(payload.get("grade") or ""))
        except qc.GradeRequired as exc:   # Trial 22 Okt (F5) — grade wajib diisi petugas QC
            raise InspectionError(str(exc)) from exc
        # RINGKASAN, bukan sumber angka: disalin dari hasil pemanggilan di atas.
        patch.update({
            "points_snapshot": result.get("points"),
            # L05 LN-051/052 — kejadian per interval, form & versi aturan disalin ke baris (riwayat tidak berubah
            # walau roll diinspeksi ulang / aturan grade diganti).
            "defects": (result.get("roll") or {}).get("inspection", {}).get("defects", []),
            "inspect_form": (result.get("roll") or {}).get("inspection", {}).get("form"),
            "grade_rule": (result.get("roll") or {}).get("inspection", {}).get("rule"),
            "grade_before": result.get("grade_before", line.get("grade_before", "")),
            "grade_after": result.get("grade", ""),
            "gsm_actual": (result.get("roll") or {}).get("inspection", {}).get("gsm_actual"),
            "width_actual": (result.get("roll") or {}).get("inspection", {}).get("width_actual"),
            "hold": bool((result.get("hold") or {}).get("held")),
            "hold_reason": (result.get("hold") or {}).get("reason", ""),
        })
        patch["stdrt"] = stdrt_points(result.get("points"), payload.get("inspect_length_yard"),
                                      patch.get("width_actual") or line.get("width_standard"))
        warnings = list(result.get("qc_warnings") or [])
    else:
        # Baris retur: hasil disimpan di BARIS SPK; hasil per barang/roll tetap milik `sales_returns`.
        # 23 Okt — SPK retur pelanggan: baris per roll diisi form 4-point yang sama (grade, kondisi, qty aktual) TANPA
        # mengubah roll (masih milik pelanggan sampai restock karantina); MD Quality hanya warna/handfeel.
        if doc.get("kind") == KIND_RETURN_CUSTOMER and part != "md_quality":
            patch.update(await _inspect_return_roll(doc, line, payload, actor, part))
        if patch["color_result"] not in ("", "sesuai") and pol["color"] == "tahan":
            patch["hold"] = True
            patch["hold_reason"] = ("Warna beda dari sample yang di-ACC — barang ditahan "
                                    "sampai manajer memutuskan.")
            warnings.append(patch["hold_reason"])
        elif patch["handfeel_result"] not in ("", "sesuai") and pol["handfeel"] == "tahan":
            patch["hold"] = True
            patch["hold_reason"] = ("Handfeel beda dari sample yang di-ACC — barang ditahan "
                                    "sampai manajer memutuskan.")
            warnings.append(patch["hold_reason"])

    note_bits = [b for b in (
        f"warna {COLOR_RESULTS.get(patch['color_result'], patch['color_result'] or '—')}",
        f"handfeel {HANDFEEL_RESULTS.get(patch['handfeel_result'], patch['handfeel_result'] or '—')}",
        (f"grade {patch.get('grade_after')}" if patch.get("grade_after") else ""),
    ) if b]
    # P16f (QC-05) — tulis HANYA baris ini secara atomik (dulu seluruh array `lines` ditimpa dari
    # salinan basi → dua inspector bersamaan saling menghapus hasil). Status dicek ulang di filter.
    sets = {f"lines.$[l].{k}": v for k, v in patch.items()}
    sets["updated_at"] = now_iso()
    if not doc.get("started_at"):
        sets["started_at"] = now_iso()
    if doc.get("status") in (STATUS_DRAFT, STATUS_ASSIGNED) and part != "md_quality":
        sets["status"] = STATUS_IN_PROGRESS
    res = await db[COLL].update_one(
        {"id": doc["id"], "status": {"$in": list(allowed)}},
        {"$set": sets, "$push": {"history": timeline_entry(
            "line_inspected", f"Baris {line.get('roll_no') or line.get('sku') or '—'} diperiksa",
            actor.get("name", ""), " · ".join(note_bits))}},
        array_filters=[{"l.id": line_id}])
    if not res.matched_count:
        raise InspectionError("Inspeksi ini baru saja ditutup/diubah orang lain. Muat ulang layar.")
    fresh = await db[COLL].find_one({"id": doc["id"]}, {"_id": 0})
    await db[COLL].update_one({"id": doc["id"]}, {"$set": {"summary": summarize(fresh)}})
    out = safe_doc(await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}))
    out["warnings"] = warnings
    return out


RETURN_CONDITIONS = ("ok", "minor", "damaged")


async def close_unneeded_return_spk(return_id: str, actor: Dict[str, Any], reason: str) -> Optional[Dict[str, Any]]:
    """UAT 23 Okt — SPK QC retur yang lahir otomatis saat ACC tetapi tidak lagi diperlukan (retur diselesaikan diskon
    dari foto, barang tidak kembali) DITUTUP dengan alasan — dulu menggantung sebagai Draf di papan QC.
    Hanya SPK yang belum ada satu baris pun diperiksa."""
    ref = await spk_for_ref(KIND_RETURN_CUSTOMER, return_id, OPEN_STATUSES)
    doc = await db[COLL].find_one({"id": ref["id"]}, {"_id": 0}) if ref else None
    if not doc or any(ln.get("inspected_at") for ln in doc.get("lines") or []):
        return None
    return await _save(doc, "closed", "Ditutup — QC tidak diperlukan", actor, reason,
                       status=STATUS_CLOSED, closed_reason=reason, closed_at=now_iso())


async def _inspect_return_roll(doc: Dict[str, Any], line: Dict[str, Any], payload: Dict[str, Any],
                               actor: Dict[str, Any], part: str) -> Dict[str, Any]:
    """23 Okt — isi satu baris SPK retur pelanggan dengan form 4-point yang sama (cacat per interval, poin, grade
    DIISI PETUGAS, gramasi/lebar) + kondisi & qty aktual. Pagar: retur sudah disetujui & belum diselesaikan,
    roll masih termasuk klaim, dan barangnya SUDAH diterima gudang (F-12, per roll)."""
    from services import qc_inspection_service as qc
    from services import return_journey_service as _journey
    ret = await db.sales_returns.find_one({"id": doc.get("ref_doc_id")}, {"_id": 0})
    if not ret:
        raise InspectionError("Dokumen retur SPK ini tidak ditemukan.")
    if ret.get("status") not in ("approved", "inspecting"):
        raise InspectionError(f"Retur {ret.get('number', '')} berstatus '{ret.get('status')}' — QC retur hanya sesudah "
                              "retur disetujui dan sebelum diinspeksi selesai.")
    rid = line.get("roll_id") or ""
    if rid:
        if rid not in {r for it in ret.get("items") or [] for r in (it.get("roll_ids") or [])}:
            raise InspectionError("Roll ini sudah tidak termasuk klaim retur (ditolak) — muat ulang SPK.")
        why = _journey.roll_not_ready_for_qc(ret, rid)
        if why:
            raise InspectionError(why)
    else:
        try:
            _journey.assert_ready_for_qc(ret)
        except ValueError as exc:
            raise InspectionError(str(exc)) from exc
    try:
        defects = qc.normalize_interval_defects(payload.get("defects") or [], payload.get("inspect_length_yard"))
    except qc.IntervalError as exc:
        raise InspectionError(str(exc)) from exc
    points = qc.compute_points(defects)
    th = await qc.grade_thresholds(ret.get("entity_id"))
    grade_in = str(payload.get("grade") or "").strip()
    if grade_in:
        from services import grade_service as _gs
        try:
            grade = _gs.normalize_or_raise(grade_in, "Grade QC retur")
        except Exception as exc:  # noqa: BLE001
            raise InspectionError(str(exc)) from exc
    elif await qc.grade_auto(ret.get("entity_id")):
        grade = qc.grade_from_points(points, th)
    else:
        raise InspectionError(f"Pilih grade {line.get('roll_no') or 'barang'} — grade ditentukan petugas QC dari total "
                              f"poin ({points:g} poin); sistem tidak mengisi grade otomatis.")
    cond = str(payload.get("condition") or (line.get("claim") or {}).get("condition") or "ok").strip().lower()
    if cond not in RETURN_CONDITIONS:
        raise InspectionError("Kondisi harus salah satu: Baik, Cacat ringan, Rusak.")
    actual = payload.get("actual_qty")
    actual = round(float(actual), 2) if actual not in (None, "") else float(line.get("quantity") or 0)
    if actual < 0:
        raise InspectionError("Qty aktual tidak boleh negatif.")
    if ret.get("status") == "approved":
        from services import return_service as _ret
        await _ret.mark_inspecting(ret["id"], actor.get("name", ""))
    num = lambda v: (float(v) if v not in (None, "") else None)  # noqa: E731
    return {
        "defects": defects, "points_snapshot": points, "grade_after": grade, "condition": cond, "actual_qty": actual,
        "gsm_actual": num(payload.get("gsm_actual")), "width_actual": num(payload.get("width_actual")),
        "inspect_form": {"inspect_length_yard": num(payload.get("inspect_length_yard")),
                         "interval_yard": qc.INTERVAL_YARD, "intervals": qc.interval_count(payload.get("inspect_length_yard"))},
        "grade_rule": {"version": qc.RULE_VERSION, "status": qc.RULE_STATUS,
                       "grade_source": "user" if grade_in else "system_suggestion",
                       "suggested_grade": qc.grade_from_points(points, th), "thresholds": th},
        "stdrt": stdrt_points(points, payload.get("inspect_length_yard"),
                              num(payload.get("width_actual")) or line.get("width_standard")),
    }


async def _release_quarantine(doc: Dict[str, Any], dec: str, note: str, actor: Dict[str, Any],
                              reject_disposition: str, rejected_roll_ids: Optional[List[str]]) -> Optional[Dict[str, Any]]:
    """F-14 (uji pra-UAT 2026-10-21, keputusan owner Q-03a) — SATU keputusan: menutup SPK penerimaan PO
    sekaligus memutus karantina tugas penerimaannya (roll diterima → tersedia, ditolak → retur supplier/rusak)
    lewat mesin yang sama dengan antrean karantina (`qc_service.process_qc_decision`).
    None bila tidak ada karantina yang menunggu (tugas sudah diputus lewat jalur lama / tanpa tugas)."""
    task = await db.wms_tasks.find_one({"id": doc.get("task_id")}, {"_id": 0})
    if not task or task.get("status") != "qc_pending":
        return None
    from services import qc_service
    qrolls = await qc_service.get_quarantine_rolls(task["id"])
    if not qrolls:
        return None
    lines = {ln.get("roll_id"): ln for ln in (doc.get("lines") or []) if ln.get("roll_id")}
    ids = [r["id"] for r in qrolls]
    marked = {rid for rid, ln in lines.items() if ln.get("decision") == "tolak"}
    if dec == "tolak":
        rejected = set(ids)
    elif dec == "terima_sebagian":
        rejected = set(rejected_roll_ids or []) | marked
        unknown = rejected - set(ids)
        if unknown:
            raise InspectionError("Roll yang ditandai tolak tidak ada di karantina tugas ini — muat ulang SPK.")
        if not rejected or rejected == set(ids):
            raise InspectionError("Diterima sebagian: tandai roll yang DITOLAK (minimal satu, tidak semuanya).")
    else:
        if marked:
            nos = ", ".join(str(lines[r].get("roll_no") or r) for r in sorted(marked))
            raise InspectionError(f"Baris {nos} ditandai tolak — pilih keputusan 'Diterima sebagian' atau 'Ditolak'.")
        rejected = set()
    accepted = [rid for rid in ids if rid not in rejected]
    length = {r["id"]: float(r.get("length_remaining") or 0) for r in qrolls}
    acc_qty = round(sum(length[r] for r in accepted), 2)
    rej_qty = round(sum(length[r] for r in rejected), 2)
    disp = (reject_disposition or "").strip().lower()
    if rej_qty > 0.01 and disp not in ("damaged", "return"):
        raise InspectionError("Pilih tindakan untuk roll yang ditolak: retur ke supplier (Nota Debit) atau barang rusak.")
    from services import grade_service
    grades: Dict[str, str] = {}
    by_id = {r["id"]: r for r in qrolls}
    for rid in accepted:
        g = (lines.get(rid) or {}).get("grade_after") or by_id[rid].get("grade") or "A"
        try:
            grades[rid] = grade_service.normalize_or_raise(g, "Grade")
        except Exception:  # noqa: BLE001 — grade lama tak sah → bawaan A
            grades[rid] = "A"
    reason = note or f"SPK {doc.get('number', '')}: {DECISIONS.get(dec, dec)}"
    try:
        res = await qc_service.process_qc_decision(
            task, acc_qty, rej_qty, disp, reason, actor, accept_grade="A",
            roll_order=accepted + [r for r in ids if r in rejected], roll_grades=grades)
    except ValueError as exc:
        raise InspectionError(str(exc)) from exc
    # UAT 24 Okt (P11.3) — roll yang diterima TANPA dicek MD Quality ditandai "lolos lewat sampling" (dulu tidak bisa
    # dibedakan dari roll yang memang dicek & lolos).
    if doc.get("md_only"):
        checked_ids = {rid for rid, ln in lines.items() if ln.get("md_quality_at")}
        lewat = [rid for rid in accepted if rid not in checked_ids]
        if lewat:
            await db.inventory_rolls.update_many(
                {"id": {"$in": lewat}, "md_quality_checked": {"$ne": True}},
                {"$set": {"md_quality_via_sampling": {"spk": doc.get("number", ""), "spk_id": doc.get("id", ""),
                                                      "checked": len(checked_ids), "total": len(ids),
                                                      "at": now_iso()}}})
    # Trial 22 Okt (E9) — roll yang GAGAL di SPK QC 4-point saat masih karantina: lepas karantina → langsung DITAHAN.
    from services import roll_hold_service as _rh
    for r in await db.inventory_rolls.find({"id": {"$in": accepted}, "qc_hold_pending": {"$exists": True}},
                                           {"_id": 0}).to_list(500):
        try:
            await _rh.hold_roll(r, (r.get("qc_hold_pending") or {}).get("reason") or QC4_HOLD_PREFIX, actor)
            await db.inventory_rolls.update_one({"id": r["id"]}, {"$unset": {"qc_hold_pending": ""}})
        except ValueError:
            pass
    return {"task_id": task["id"], "accepted_qty": res.get("accepted_qty", 0.0), "rejected_qty": res.get("rejected_qty", 0.0),
            "reject_disposition": res.get("reject_disposition"), "purchase_return": res.get("purchase_return"),
            "task_status": res.get("task_status"), "rejected_roll_ids": sorted(rejected), "at": now_iso(),
            "by": actor.get("name", "")}


async def finish(ins_id: str, decision: str, remark: str,
                 actor: Dict[str, Any], reject_disposition: str = "",
                 rejected_roll_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """Tutup inspeksi dengan KEPUTUSAN. `tolak` wajib ber-alasan (tersimpan di dokumen).
    F-14 — SPK penerimaan PO: keputusan ini sekaligus memutus karantina (`_release_quarantine`)."""
    doc = await _load(ins_id)
    _assert_status(doc, (STATUS_ASSIGNED, STATUS_IN_PROGRESS), "ditutup")
    dec = str(decision or "").strip().lower()
    if dec not in DECISIONS:
        raise InspectionError(f"Keputusan harus salah satu: {', '.join(DECISIONS)}.")
    note = (remark or "").strip()
    if dec == "tolak" and len(note) < MIN_REASON:
        raise InspectionError(
            "Menolak hasil inspeksi WAJIB ber-alasan — tulis satu kalimat utuh "
            f"(minimal {MIN_REASON} huruf). Alasan ini dibaca supplier/mitra dan "
            "menjadi dasar klaim, jadi “jelek” tidak cukup.")
    lines = doc.get("lines") or []
    if lines and not any(ln.get("inspected_at") for ln in lines):
        raise InspectionError(
            "Belum ada satu baris pun yang diperiksa — keputusan tanpa pemeriksaan "
            "membuat tanggalnya jadi bukti palsu.")
    if doc.get("kind") == KIND_RANDOM_CHECK and any(not ln.get("qc_at") for ln in lines):
        raise InspectionError("Random check: periksa SEMUA roll dulu — roll yang belum dicek tetap ditahan.")
    # UAT 24 Okt (P11.2/P11.3) — sampling: MD Quality & QC 4-point cukup memeriksa sebagian roll sesuai pengaturan
    # (`qc.md_sampling_*` / `qc.sampling_*`). Dulu QC 4-point dipaksa SEMUA roll.
    rule = await sampling_rule(doc)
    if rule["part"] and rule["checked"] < rule["required"]:
        apa = "dicek MD Quality" if rule["part"] == "md_quality" else "diperiksa QC 4-point"
        raise InspectionError(
            f"Baru {rule['checked']} dari {rule['total']} roll {apa} — wajib minimal {rule['required']} roll "
            f"(sampling {rule['pct']}%, minimal {rule['min']} roll) sebelum SPK ditutup.")
    if doc.get("kind") == KIND_QC_4POINT and rule["checked"] < rule["total"]:
        # Roll yang TIDAK diperiksa dikeluarkan dari SPK (tetap "belum 4-point"), bukan diluluskan.
        keep = [ln for ln in lines if ln.get("qc_at") or not ln.get("roll_id")]
        out_lines = [ln for ln in lines if ln.get("roll_id") and not ln.get("qc_at")]
        await db[COLL].update_one({"id": doc["id"]}, {"$set": {
            "lines": keep, "excluded_lines": (doc.get("excluded_lines") or []) + [
                {**ln, "excluded_at": now_iso(), "excluded_reason": "tidak diperiksa (sampling)"} for ln in out_lines]}})
        doc = {**doc, "lines": keep}
        lines = keep
    ret_live = None
    if doc.get("kind") == KIND_RETURN_CUSTOMER and doc.get("ref_doc_id"):
        ret_live = await db.sales_returns.find_one({"id": doc["ref_doc_id"]}, {"_id": 0, "status": 1, "items": 1})
        if ret_live and ret_live.get("status") in ("approved", "inspecting"):
            claimed = {r for it in ret_live.get("items") or [] for r in (it.get("roll_ids") or [])}
            todo = [ln.get("roll_no") or ln.get("sku") or "—" for ln in lines
                    if (ln.get("roll_id") in claimed or not ln.get("roll_id")) and not ln.get("grade_after")]
            if todo:
                raise InspectionError(f"Periksa SEMUA roll retur dulu (grade belum diisi: {', '.join(todo[:6])}"
                                      f"{' …' if len(todo) > 6 else ''}).")
    qres = None
    if doc.get("kind") == KIND_PO_RECEIPT and doc.get("task_id"):
        # Karantina diputus DULU: bila gagal (roll ditahan, cakupan belum terpenuhi, …) SPK tetap terbuka —
        # tidak ada lagi "SPK ditutup terima tetapi roll masih karantina" (F-14).
        qres = await _release_quarantine(doc, dec, note, actor, reject_disposition, rejected_roll_ids)
    extra = {"quarantine_result": qres} if qres else {}
    out = await _save(doc, "finished", f"Keputusan: {DECISIONS[dec]}", actor, note,
                      status=STATUS_DONE, decision=dec, decision_label=DECISIONS[dec],
                      remark=note, reject_reason=(note if dec == "tolak" else ""),
                      finished_at=now_iso(),
                      decided_by=actor.get("name", ""), decided_at=now_iso(), **extra)
    if doc.get("kind") == KIND_RANDOM_CHECK:
        await _close_random_check(out, dec, actor)
        out = safe_doc(await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}))
    if doc.get("kind") == KIND_QC_4POINT:
        await _close_qc_4point(out, dec, actor)
        out = safe_doc(await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}))
    # FASE I.F — `sales_returns.inspect_done_at` DITURUNKAN dari sini, tidak pernah
    # diketik: dua tanggal "inspeksi selesai" yang bisa berbeda adalah kelas bug
    # yang paling sering menipu di repo ini.
    if doc.get("kind") == KIND_SALES_ORDER and doc.get("ref_doc_id"):   # L05 LN-050-T01
        await db.sales_orders.update_one({"id": doc["ref_doc_id"], "qc_request.mode": {"$in": ["full", "sampling"]}}, {"$set": {
            "qc_request.status": "passed" if dec in ("terima", "turun_grade") else "failed",
            "qc_request.inspection_id": doc["id"], "qc_request.inspection_number": doc.get("number", ""),
            "qc_request.decided_at": now_iso()}})
    # L05 LN-050-T02 — SPK PENGGANTI tidak boleh menandai barang retur sudah diinspeksi.
    if doc.get("ref_doc_type") == "sales_return" and doc.get("ref_doc_id") and doc.get("kind") == KIND_RETURN_CUSTOMER:
        from services import return_service as _ret
        if ret_live and ret_live.get("status") in ("approved", "inspecting"):
            # 23 Okt — hasil per roll dari SPK menjadi hasil inspeksi retur (status → Diinspeksi).
            try:
                await _ret.complete_inspection_from_spk(doc["ref_doc_id"], out.get("lines") or [],
                                                        actor.get("name", ""), note)
            except ValueError as exc:
                logger.warning("[inspection.finish] hasil SPK %s belum bisa ditulis ke retur: %s", doc.get("number"), exc)
                await db[COLL].update_one({"id": doc["id"]}, {"$set": {"return_writeback_error": str(exc)[:300]}})
        await _ret.mark_inspected_by_document(doc["ref_doc_id"],
                                              out.get("finished_at", ""))
    return out


# ═══════════════════════════════════════════════════════════════════════════════
#  P05 IMP-16 — Random check QC atas roll di stok
# ═══════════════════════════════════════════════════════════════════════════════
RANDOM_CHECK_HOLD_PREFIX = "Random check QC"


async def create_random_check(payload: Dict[str, Any], actor: Dict[str, Any],
                              entity_id: str) -> Dict[str, Any]:
    """Ambil N roll Tersedia secara acak dari satu gudang, TAHAN selama dicek, terbitkan SPK."""
    from services import roll_hold_service as rh
    if not entity_id or entity_id == "all":
        raise InspectionError("Pilih satu badan usaha dulu — random check milik satu badan usaha.")
    scan = str(payload.get("scan_code") or "").strip()
    if scan:   # L05 LN-050-T03 — random dimulai dari SCAN roll fisik: identitas & lokasi dari hasil scan sah
        tag = await db.rfid_tags.find_one({"epc": scan.upper(), "status": {"$ne": "void"}}, {"_id": 0, "roll_id": 1})
        q = {"id": tag["roll_id"]} if tag and tag.get("roll_id") else {"$or": [{"roll_no": scan}, {"id": scan}]}
        roll = await db.inventory_rolls.find_one(q, {"_id": 0})
        if not roll:
            raise InspectionError(f"Kode '{scan}' tidak dikenali sebagai roll.")
        if roll.get("owner_entity_id") != entity_id:
            raise InspectionError("Roll hasil scan di luar badan usaha/cakupan Anda — tidak bisa di-random check.")
        if roll.get("status") != "available" or roll.get("earmarked_for"):
            raise InspectionError(f"Roll {roll.get('roll_no')} berstatus '{roll.get('status')}' / sudah dipesan — tidak bisa di-random check.")
        payload = {**payload, "warehouse_id": roll["warehouse_id"], "count": 1, "product_id": roll["product_id"],
                   "_roll_id": roll["id"]}
    wh_id = str(payload.get("warehouse_id") or "").strip()
    if not wh_id:
        raise InspectionError("Pilih gudang yang mau di-random check.")
    count = max(1, min(int(payload.get("count") or 3), 30))
    flt: Dict[str, Any] = {"warehouse_id": wh_id, "status": "available",
                           "owner_entity_id": entity_id,
                           "earmarked_for": {"$in": [None, ""]}}
    if payload.get("product_id"):
        flt["product_id"] = str(payload["product_id"])
    if payload.get("_roll_id"):
        flt["id"] = payload["_roll_id"]
    picked = await db.inventory_rolls.aggregate(
        [{"$match": flt}, {"$sample": {"size": count}}, {"$project": {"_id": 0}}]).to_list(count)
    if not picked:
        raise InspectionError("Tidak ada roll Tersedia (bebas peg) di gudang itu untuk di-random check.")
    held: List[Dict[str, Any]] = []
    for r in picked:
        try:
            held.append(await rh.hold_roll(r, f"{RANDOM_CHECK_HOLD_PREFIX} — ditahan selama dicek", actor))
        except ValueError:
            continue
    if not held:
        raise InspectionError("Roll terpilih berubah status bersamaan — coba lagi.")
    wh = await db.warehouses.find_one({"id": wh_id}, {"_id": 0, "name": 1, "code": 1}) or {}
    assigned = await _resolve_assignee(str(payload.get("assigned_to") or actor.get("id") or ""), entity_id)
    doc = await _new_doc(kind=KIND_RANDOM_CHECK, entity_id=entity_id, actor=actor,
                         ref_doc_type="warehouse", ref_doc_id=wh_id,
                         ref_doc_number=wh.get("code") or wh.get("name", ""),
                         lines=await _lines_from_rolls(held), assigned=assigned,
                         remark=str(payload.get("remark") or "") or
                         (f"Random check dari scan {scan} — roll DITAHAN sampai SPK diputuskan." if scan else
                          f"Random check {len(held)} roll — roll DITAHAN sampai SPK diputuskan."))
    await db.inventory_rolls.update_many({"id": {"$in": [r["id"] for r in held]}},
                                         {"$set": {"random_check_id": doc["id"]}})
    return doc


async def _close_random_check(doc: Dict[str, Any], dec: str, actor: Dict[str, Any]) -> None:
    """Roll lulus dilepas; roll gagal (baris `tolak` / keputusan `tolak`) tetap ditahan.
    Grade hasil 4-point sudah ditulis `grade_service` saat baris diperiksa."""
    from services import roll_hold_service as rh
    note = f"Random check {doc.get('number', '')} lulus — {DECISIONS.get(dec, dec)}"
    lines = []
    for ln in (doc.get("lines") or []):
        failed = dec == "tolak" or str(ln.get("decision") or "") == "tolak"
        roll = await db.inventory_rolls.find_one({"id": ln.get("roll_id")}, {"_id": 0}) \
            if ln.get("roll_id") else None
        released = False
        if roll and not failed and (roll.get("hold") or {}).get("held") \
                and str((roll.get("hold") or {}).get("reason", "")).startswith(RANDOM_CHECK_HOLD_PREFIX):
            try:
                await rh.release_roll(roll, note, actor)
                released = True
            except ValueError:
                released = False
        lines.append({**ln, "hold": bool(failed or (roll and not released)),
                      "hold_reason": ("Random check GAGAL — roll tetap ditahan." if failed
                                      else ln.get("hold_reason", "")),
                      "random_check_result": "gagal" if failed else "lulus"})
    await _save(doc, "random_check_closed",
                f"Random check ditutup: {sum(1 for x in lines if x['random_check_result'] == 'lulus')} lulus, "
                f"{sum(1 for x in lines if x['random_check_result'] == 'gagal')} gagal", actor, lines=lines)


async def create_qc_4point(payload: Dict[str, Any], actor: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    """Trial 22 Okt (E9) — SPK QC 4-point tersendiri, kapan saja: roll dari SPK MD Quality (`inspection_id`), dari tugas
    penerimaan (`task_id`), atau daftar roll (`roll_ids`). Tidak menahan roll saat dibuat (QC tidak menghambat alur);
    baris DITOLAK saat SPK ditutup → roll ditahan (`_close_qc_4point`)."""
    src_ins = str(payload.get("inspection_id") or "").strip()
    task_id = str(payload.get("task_id") or "").strip()
    roll_ids = [str(r) for r in payload.get("roll_ids") or [] if r]
    ref = ("", "", "")
    picked = set(roll_ids)
    if src_ins:
        src = await _load(src_ins)
        entity_id = src.get("entity_id") or entity_id
        roll_ids = [ln["roll_id"] for ln in src.get("lines") or [] if ln.get("roll_id")]
        ref = ("inspection", src["id"], src.get("number", ""))
    elif task_id:
        task = await db.wms_tasks.find_one({"id": task_id}, {"_id": 0, "id": 1, "po_number": 1, "entity_id": 1})
        if not task:
            raise InspectionError("Tugas penerimaan tidak ditemukan.")
        roll_ids = [r["id"] async for r in db.inventory_rolls.find({"qc_task_id": task_id}, {"_id": 0, "id": 1})]
        ref = ("", "", task.get("po_number", ""))
    if picked and (src_ins or task_id):
        # UAT 24 Okt (P11.2) — SPK 4-point boleh untuk SEBAGIAN roll kedatangan (dulu selalu semua).
        asing = picked - set(roll_ids)
        if asing:
            raise InspectionError("Ada roll pilihan yang bukan bagian dari SPK/kedatangan sumber — muat ulang.")
        roll_ids = [r for r in roll_ids if r in picked]
    if not entity_id or entity_id == "all":
        raise InspectionError("Pilih satu badan usaha dulu — SPK QC milik satu badan usaha.")
    rolls = await db.inventory_rolls.find({"id": {"$in": roll_ids}, "owner_entity_id": entity_id},
                                          {"_id": 0}).to_list(500)
    if not rolls:
        raise InspectionError("Tidak ada roll untuk diperiksa QC 4-point.")
    assigned = await _resolve_assignee(str(payload.get("assigned_to") or actor.get("id") or ""), entity_id)
    doc = await _new_doc(kind=KIND_QC_4POINT, entity_id=entity_id, actor=actor,
                         ref_doc_type=ref[0], ref_doc_id=ref[1], ref_doc_number=ref[2],
                         lines=await _lines_from_rolls(rolls), assigned=assigned,
                         remark=str(payload.get("remark") or "") or (f"QC 4-point {len(rolls)} roll"
                                + (f" dari {ref[2]}" if ref[2] else "") + " — baris ditolak menahan roll."))
    await db[COLL].update_one({"id": doc["id"]}, {"$set": {"source_inspection_id": src_ins, "source_task_id": task_id}})
    return safe_doc(await db[COLL].find_one({"id": doc["id"]}, {"_id": 0}))


async def _close_qc_4point(doc: Dict[str, Any], dec: str, actor: Dict[str, Any]) -> None:
    """Roll GAGAL (baris `tolak` / keputusan `tolak`) DITAHAN: tersedia → ditahan sekarang; masih karantina → ditahan
    saat SPK MD Quality melepas karantina; status lain (sudah terikat pesanan/terkirim) → ditandai gagal untuk
    diputus manual. Roll lulus tidak disentuh (grade 4-point sudah ditulis saat baris diperiksa)."""
    from services import roll_hold_service as rh
    lines = []
    for ln in doc.get("lines") or []:
        failed = dec == "tolak" or str(ln.get("decision") or "") == "tolak"
        result = "lulus"
        if failed and ln.get("roll_id"):
            note = ln.get("qc_remark") or ln.get("remark") or ""
            reason = f"{QC4_HOLD_PREFIX} — SPK {doc.get('number', '')}" + (f": {note}" if note else "")
            roll = await db.inventory_rolls.find_one({"id": ln["roll_id"]}, {"_id": 0}) or {}
            if roll.get("status") == "available" and not roll.get("earmarked_for"):
                try:
                    await rh.hold_roll(roll, reason, actor)
                    result = "ditahan"
                except ValueError:
                    result = "gagal — putuskan manual"
            elif roll.get("status") == "quarantine":
                await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": {"qc_hold_pending": {
                    "reason": reason, "spk": doc.get("number", ""), "at": now_iso()}}})
                result = "ditahan saat lepas karantina"
            else:
                await db.inventory_rolls.update_one({"id": ln["roll_id"]}, {"$set": {"qc_failed": {
                    "reason": reason, "spk": doc.get("number", ""), "at": now_iso()}}})
                result = f"gagal — roll berstatus {roll.get('status') or '-'}, putuskan manual"
        lines.append({**ln, "hold": failed, "qc4_result": result})
    lulus = sum(1 for x in lines if x["qc4_result"] == "lulus")
    await _save(doc, "qc4_closed", f"QC 4-point ditutup: {lulus} lulus, {len(lines) - lulus} gagal", actor, lines=lines)


async def reopen(ins_id: str, reason: str, actor: Dict[str, Any]) -> Dict[str, Any]:
    doc = await _load(ins_id)
    _assert_status(doc, (STATUS_DONE,), "dibuka kembali")
    if doc.get("kind") in (KIND_RANDOM_CHECK, KIND_QC_4POINT):
        raise InspectionError("SPK QC yang sudah ditutup tidak bisa dibuka — buat SPK QC baru.")
    if doc.get("quarantine_result"):   # F-14 — stok sudah dilepas/diretur oleh keputusan SPK ini
        raise InspectionError(
            "Keputusan SPK ini sudah memutus karantina (stok diterima/ditolak) — tidak bisa dibuka kembali. "
            "Koreksi lewat retur pembelian atau penyesuaian stok.")
    why = (reason or "").strip()
    if len(why) < MIN_REASON:
        raise InspectionError(
            "Membuka kembali inspeksi WAJIB ber-alasan — tulis satu kalimat utuh "
            f"(minimal {MIN_REASON} huruf). Keputusan yang dianulir tanpa alasan "
            "menghapus jejak tanggung jawab.")
    out = await _save(doc, "reopened", "Dibuka kembali", actor, why,
                       status=STATUS_IN_PROGRESS, reopen_reason=why,
                       decision="", decision_label="", finished_at="",
                       # `reject_reason` IKUT dikosongkan — ia milik keputusan yang baru
                       # saja dianulir. Terukur 2026-08-23 di peramban: sesudah dibuka
                       # kembali, panel "ALASAN PENOLAKAN" tetap terpampang sementara
                       # kepala dokumen berkata "Belum diputuskan" — dua pernyataan yang
                       # bertentangan pada satu layar, dan pembaca tidak punya cara tahu
                       # mana yang berlaku. Alasannya TIDAK hilang: baris riwayat
                       # "Keputusan: Ditolak … — <alasan>" tetap ada selamanya.
                       reject_reason="")
    # IX-09 — proyeksi tonggak retur ikut dibatalkan: SPK dibuka lagi = belum selesai diperiksa.
    if doc.get("ref_doc_type") == "sales_return" and doc.get("ref_doc_id"):
        from services import return_service as _ret
        await _ret.unmark_inspected_by_document(doc["ref_doc_id"], why)
    return out


async def release_hold(ins_id: str, line_id: str, reason: str,
                       actor: Dict[str, Any], can_md_quality: bool = False) -> Dict[str, Any]:
    """Lepas tahanan satu baris — MD Quality (penerimaan PO/hasil makloon) atau manajer/admin (cadangan)."""
    doc = await _load(ins_id)
    line = _line_of(doc, line_id)
    md_ok = can_md_quality and doc.get("kind") in MD_QUALITY_KINDS
    if not role_in((actor or {}).get("role"), HOLD_RELEASE_ROLES) and not md_ok:
        raise PermissionError(
            "Hanya MD Quality (penerimaan PO/hasil makloon) atau MANAJER yang boleh melepas "
            "tahanan barang yang warnanya beda dari sample.")
    if not line.get("hold"):
        raise InspectionError("Baris ini tidak sedang ditahan.")
    why = (reason or "").strip()
    if len(why) < MIN_REASON:
        raise InspectionError(
            "Melepas tahanan WAJIB ber-alasan — tulis satu kalimat utuh (minimal "
            f"{MIN_REASON} huruf). Inilah satu-satunya catatan mengapa barang yang "
            "menyimpang tetap masuk gudang.")
    if doc.get("kind") == KIND_RANDOM_CHECK:
        raise InspectionError("Tahanan random check dilepas saat SPK diputuskan (roll lulus otomatis dilepas).")
    if line.get("roll_id"):
        await db.inventory_rolls.update_one(
            {"id": line["roll_id"]},
            {"$set": {"inspection.hold.held": False,
                      "inspection.hold.released_by": actor.get("name", ""),
                      "inspection.hold.released_at": now_iso(),
                      "inspection.hold.release_reason": why,
                      "updated_at": now_iso()}})
    lines = [({**ln, "hold": False, "hold_released_by": actor.get("name", ""),
               "hold_released_at": now_iso(), "hold_release_reason": why,
               "md_quality_decision": {"action": "release", "reason": why, "by": actor.get("name", ""),
                                       "role": actor.get("role", ""), "at": now_iso()}}
              if ln.get("id") == line_id else ln) for ln in (doc.get("lines") or [])]
    return await _save(doc, "hold_released",
                       f"Tahanan baris {line.get('roll_no') or line.get('sku') or '—'} dilepas",
                       actor, why, lines=lines)


async def reject_hold(ins_id: str, line_id: str, reason: str, actor: Dict[str, Any],
                      can_md_quality: bool = False) -> Dict[str, Any]:
    """MD Quality MENOLAK barang yang ditahan: baris jadi `tolak`, roll TETAP ditahan."""
    doc = await _load(ins_id)
    line = _line_of(doc, line_id)
    md_ok = can_md_quality and doc.get("kind") in MD_QUALITY_KINDS
    if not role_in((actor or {}).get("role"), HOLD_RELEASE_ROLES) and not md_ok:
        raise PermissionError("Hanya MD Quality (penerimaan PO/hasil makloon) atau MANAJER yang boleh "
                              "menolak barang yang ditahan.")
    if not line.get("hold"):
        raise InspectionError("Baris ini tidak sedang ditahan.")
    why = (reason or "").strip()
    if len(why) < MIN_REASON:
        raise InspectionError(f"Menolak barang WAJIB ber-alasan — minimal {MIN_REASON} huruf.")
    lines = [({**ln, "decision": "tolak",
               "md_quality_decision": {"action": "reject", "reason": why, "by": actor.get("name", ""),
                                       "role": actor.get("role", ""), "at": now_iso()}}
              if ln.get("id") == line_id else ln) for ln in (doc.get("lines") or [])]
    if line.get("roll_id"):
        await db.inventory_rolls.update_one(
            {"id": line["roll_id"]},
            {"$set": {"inspection.hold.md_quality_rejected": True,
                      "inspection.hold.rejected_by": actor.get("name", ""),
                      "inspection.hold.rejected_at": now_iso(),
                      "inspection.hold.reject_reason": why, "updated_at": now_iso()}})
    return await _save(doc, "hold_rejected",
                       f"Barang baris {line.get('roll_no') or line.get('sku') or '—'} DITOLAK MD Quality",
                       actor, why, lines=lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  Daftar & statistik
# ═══════════════════════════════════════════════════════════════════════════════
async def _form_header(doc: Dict[str, Any], roll: Dict[str, Any]) -> Dict[str, Any]:
    """LN-051/T03 — header form dari SUMBER (dokumen, roll, produk), bukan ketikan ulang."""
    prod = await db.products.find_one({"id": roll.get("product_id")}, {"_id": 0, "name": 1, "sku": 1, "fabric_type": 1,
                                                                     "category": 1, "color": 1, "color_name": 1,
                                                                     "supplier": 1, "supplier_color": 1}) or {}
    cust = doc.get("customer") or {}
    sup = doc.get("supplier") or {}
    return {"customer_name": cust.get("name") if isinstance(cust, dict) else cust,
            "supplier_name": (sup.get("name") if isinstance(sup, dict) else sup) or prod.get("supplier"),
            "fabric_type": roll.get("fabric_type") or prod.get("fabric_type") or (prod.get("category") or "").lower(),
            "article": prod.get("name"), "sku": prod.get("sku"), "roll_no": roll.get("roll_no"),
            "color_internal": prod.get("color_name") or prod.get("color"),
            "color_supplier": prod.get("supplier_color") or roll.get("supplier_color"),
            "inspected_date": now_iso()[:10], "source_kind": doc.get("kind"), "source_ref": doc.get("ref_doc_number")}


async def list_inspections(scope: Dict[str, Any], *, kind: str = "", status: str = "",
                           assigned_to: str = "", q: str = "", hold_only: bool = False,
                           skip: int = 0, limit: int = 200) -> Tuple[List[Dict[str, Any]], int]:
    flt: Dict[str, Any] = dict(scope or {})
    if kind:
        flt["kind"] = kind
    if status:
        flt["status"] = status
    if assigned_to:
        flt["assigned_to"] = assigned_to
    if hold_only:
        flt["lines.hold"] = True
    if q:
        rx = {"$regex": q.strip(), "$options": "i"}
        flt["$or"] = [{"number": rx}, {"ref_doc_number": rx}, {"supplier_name": rx},
                      {"customer_name": rx}, {"assigned_name": rx}]
    total = await db[COLL].count_documents(flt)
    rows = await db[COLL].find(flt, {"_id": 0}).sort("created_at", -1) \
        .skip(int(skip)).limit(int(limit)).to_list(int(limit))
    return [safe_doc(r) for r in rows], int(total)


async def stats(scope: Dict[str, Any]) -> Dict[str, Any]:
    flt = dict(scope or {})
    out: Dict[str, Any] = {}
    for st in BOARD_ORDER:
        out[st] = await db[COLL].count_documents({**flt, "status": st})
    out["total"] = await db[COLL].count_documents(flt)
    out["hold"] = await db[COLL].count_documents({**flt, "lines.hold": True})
    out["rejected"] = await db[COLL].count_documents({**flt, "decision": "tolak"})
    return out


# Trial 22 Okt (F5) — kode cacat di kertas "DATA HASIL INSPECT" pemilik. Arti tiap kode diisi pemilik di Pengaturan
# (`qc.defect_codes` = [{code, label}]); sampai itu, kode tampil apa adanya sebagai legenda & saran isian.
DEFAULT_DEFECT_CODES = [{"code": c, "label": ""} for c in ("CG", "KO", "BL", "M", "CR", "BT")]


async def defect_codes(entity_id: str = "") -> List[Dict[str, str]]:
    try:
        from services.config_service import get_effective_settings
        rows = ((await get_effective_settings(entity_id or None)).get("qc") or {}).get("defect_codes") or []
        rows = [{"code": str(r.get("code") or "").strip().upper(), "label": str(r.get("label") or "")}
                for r in rows if isinstance(r, dict) and r.get("code")]
        return rows or DEFAULT_DEFECT_CODES
    except Exception:  # noqa: BLE001 — legenda tidak boleh menggagalkan meta
        return DEFAULT_DEFECT_CODES


async def meta(entity_id: str = "") -> Dict[str, Any]:
    """Kosakata + kebijakan yang BERLAKU — layar tidak boleh menebak keduanya."""
    pol = await _policy(entity_id)
    from services import qc_inspection_service as _qc
    return {
        "defect_codes": await defect_codes(entity_id),
        # Trial 22 Okt (F5) — mati (bawaan) = grade roll diisi petugas QC; layar mewajibkan kolom grade.
        "grade_auto": await _qc.grade_auto(entity_id),
        "kinds": [{"value": k, "label": v} for k, v in KIND_LABEL.items() if k not in (KIND_RANDOM_CHECK, KIND_QC_4POINT)],
        "all_kinds": [{"value": k, "label": v} for k, v in KIND_LABEL.items()],
        "md_quality_kinds": list(MD_QUALITY_KINDS),
        "statuses": [{"value": s, "label": STATUS_LABEL[s]} for s in BOARD_ORDER],
        "decisions": [{"value": k, "label": v} for k, v in DECISIONS.items()],
        "color_results": [{"value": k, "label": v} for k, v in COLOR_RESULTS.items()],
        "handfeel_results": [{"value": k, "label": v} for k, v in HANDFEEL_RESULTS.items()],
        "policy": {
            "color_mismatch_action": pol["color"],
            "color_mismatch_label": MISMATCH_ACTIONS[pol["color"]],
            "handfeel_mismatch_action": pol["handfeel"],
            "handfeel_mismatch_label": MISMATCH_ACTIONS[pol["handfeel"]],
            "hold_release_roles": list(HOLD_RELEASE_ROLES),
            # Panjang MINIMUM alasan wajib — dikirim supaya layar tidak menebaknya.
            # Terukur 2026-08-23 di peramban: pop-up alasan hanya menolak isian
            # KOSONG, jadi alasan "pendek" (6 huruf) lolos di layar lalu dijawab
            # **400** oleh server. Pengguna melihat galat merah untuk aturan yang
            # seharusnya sudah terlihat SEBELUM tombolnya bisa ditekan. Ambangnya
            # tetap milik server (`MIN_REASON`); layar hanya menampilkannya.
            "min_reason_length": MIN_REASON,
        },
    }
