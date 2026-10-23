"""QC 4-Point Inspection service — Fase 6.2 (P1).

Inspeksi objektif per-roll saat QC (task qc_pending): hitung total poin defect
(metode 4-point sederhana) → tentukan Grade (A/B/C) via ambang configurable, dan
catat GSM & lebar AKTUAL per roll.

Keputusan desain owner:
  - Skor: TOTAL poin defect saja (Σ point_value × count) — tanpa normalisasi per luas.
  - Grade (Fase A · D-01): poin ≤ a_max → A, ≤ a1_max → A1, ≤ a2_max → A2,
    ≤ b_max → B, > b_max → BS. Ambang dari Settings `qc.grade_thresholds`;
    konfigurasi lama (hanya a_max & b_max) di-interpolasi agar batas A & B TIDAK berubah.
  - GSM/Lebar aktual: dicatat saja (tanpa pass/fail otomatis).
  - Hasil: set `roll.grade` dari inspeksi (tanpa aksi karantina otomatis).
"""
from typing import Any, Dict, List, Optional
from db import db
from core_utils import now_iso, safe_doc
from services.config_service import get_effective_settings

VALID_POINTS = {1, 2, 3, 4}


async def grade_thresholds(entity_id: Optional[str] = None) -> Dict[str, float]:
    """Ambang poin → grade (5 tingkat, D-01).

    Backward-compatible: bila Settings hanya berisi `a_max` & `b_max` (skema lama
    A/B/C), ambang A1 & A2 di-interpolasi merata di antara keduanya sehingga batas
    grade A dan grade B TETAP sama seperti sebelumnya.
    """
    settings = await get_effective_settings(entity_id)
    qc = settings.get("qc", {}) or {}
    th = qc.get("grade_thresholds", {}) or {}
    a_max = float(th.get("a_max", 20.0) or 20.0)
    b_max = float(th.get("b_max", 40.0) or 40.0)
    span = max(b_max - a_max, 0.0)
    a1_max = float(th.get("a1_max") or (a_max + span / 3.0))
    a2_max = float(th.get("a2_max") or (a_max + 2.0 * span / 3.0))
    return {"a_max": a_max, "a1_max": round(a1_max, 2), "a2_max": round(a2_max, 2),
            "b_max": b_max}


def compute_points(defects: List[Dict[str, Any]]) -> float:
    """Total poin = Σ (point_value × count). point_value harus 1..4."""
    total = 0.0
    for d in defects or []:
        pv = int(d.get("point_value", 0) or 0)
        cnt = int(d.get("count", 0) or 0)
        if pv in VALID_POINTS and cnt > 0:
            total += pv * cnt
    return round(total, 2)


# ─── L05 LN-051/052 — form inspect per interval 15 yard (tanpa batas 150) + versi aturan ──────
INTERVAL_YARD = 15.0
MIN_INTERVALS = 10           # form kertas: 0–150 yard; roll lebih panjang → interval berlanjut
RULE_VERSION = "4point_sum_v1"
# KLX-02 (owner 2026-10-19): kode cacat, poin & grade DIISI USER di form; sistem hanya menyimpan + memberi saran.
RULE_STATUS = "manual_user_input"


class IntervalError(ValueError):
    pass


def interval_count(inspect_length_yard: Optional[float]) -> int:
    import math
    n = math.ceil(float(inspect_length_yard or 0) / INTERVAL_YARD - 1e-9)
    return max(MIN_INTERVALS, n)


def normalize_interval_defects(defects: List[Dict[str, Any]], inspect_length_yard: Optional[float]) -> List[Dict[str, Any]]:
    """Setiap kejadian disimpan apa adanya (tidak digabung/ditimpa). `interval` = indeks 0-based (0 = 0–15 yd)."""
    n = interval_count(inspect_length_yard)
    out = []
    for d in defects or []:
        pv, cnt = int(d.get("point_value", 0) or 0), int(d.get("count", 0) or 0)
        if cnt == 0 and pv in VALID_POINTS:
            continue
        if pv not in VALID_POINTS or cnt < 0:
            raise IntervalError(f"Cacat tidak sah: poin harus 1–4 dan jumlah ≥ 1 (dapat poin {pv}, jumlah {cnt}).")
        row: Dict[str, Any] = {"point_value": pv, "count": cnt, "note": d.get("note", ""),
                               "code": str(d.get("code") or "").strip().upper()[:20]}
        if d.get("interval") not in (None, ""):
            iv = int(d["interval"])
            if iv < 0 or iv >= n:
                raise IntervalError(f"Interval {iv + 1} di luar panjang inspect ({n} interval × 15 yard).")
            row.update({"interval": iv, "from_yard": iv * INTERVAL_YARD, "to_yard": (iv + 1) * INTERVAL_YARD})
        out.append(row)
    return out


class GradeRequired(Exception):
    """Trial 22 Okt (F5) — grade roll wajib diisi petugas QC selama `qc.grade_from_points` mati."""


async def grade_auto(entity_id: Optional[str]) -> bool:
    """`qc.grade_from_points` — hidup: grade kosong diisi sistem dari total poin; mati (bawaan): grade diisi petugas."""
    from services.config_resolver import value_of
    try:
        return bool(await value_of("qc.grade_from_points", {"entity_id": entity_id or ""}))
    except Exception:   # noqa: BLE001 — registry belum termuat: anggap mati (grade manual = tidak ada grade tebakan)
        return False


def grade_from_points(points: float, th: Dict[str, float]) -> str:
    """Poin defect → grade AKTIF dari master (L01 LN-012). Batas per grade = `max_points` di master,
    atau ambang Settings lama (`a_max`, `a1_max`, `a2_max`, `b_max`). Grade aktif terburuk = sisa."""
    import domain_registry as _dr
    active = [g for g in _dr.GRADES if g.get("active", True) is not False]
    if not active:
        return "BS"
    for g in active[:-1]:
        limit = g.get("max_points")
        if limit is None:
            limit = th.get(f"{g['value'].lower()}_max")
        if limit is not None and points <= float(limit):
            return g["value"]
    return active[-1]["value"]


def quality_hold(color_res: str, hand_res: str, color_action: str, handfeel_action: str,
                 baseline_sample_number: str, actor: Dict[str, Any]):
    """Kebijakan tahan/peringatkan atas hasil warna & handfeel → (hold, peringatan)."""
    qc_warnings: List[str] = []
    hold_source = ""
    if color_res and color_res != "sesuai":
        if str(color_action).lower() == "tahan":
            hold_source = "color"
        elif str(color_action).lower() == "peringatkan":
            qc_warnings.append("Warna berbeda dari sample yang di-ACC — kebijakan hanya "
                               "MEMPERINGATKAN, barang tetap boleh masuk gudang.")
    if hand_res and hand_res != "sesuai":
        if str(handfeel_action).lower() == "tahan" and not hold_source:
            hold_source = "handfeel"
        elif str(handfeel_action).lower() != "abaikan":
            qc_warnings.append("Handfeel berbeda dari sample yang di-ACC — kebijakan "
                               "MEMPERINGATKAN, barang tetap boleh masuk gudang.")
    hold: Dict[str, Any] = {"held": False, "reason": "", "source": "", "by": "", "at": ""}
    if hold_source:
        reason = ("Warna beda dari sample yang di-ACC" if hold_source == "color"
                  else "Handfeel beda dari sample yang di-ACC")
        if baseline_sample_number:
            reason += f" ({baseline_sample_number})"
        reason += " — barang DITAHAN sampai MD Quality memutuskan."
        hold = {"held": True, "reason": reason, "source": hold_source,
                "by": actor.get("name", ""), "at": now_iso()}
        qc_warnings.append(reason)
    return hold, qc_warnings


async def record_quality(roll: Dict[str, Any], *, color_result: str, handfeel_result: str,
                         handfeel_score: Optional[float], delta_e: Optional[float],
                         baseline_sample_id: str, baseline_sample_number: str,
                         color_action: str, handfeel_action: str, actor: Dict[str, Any],
                         inspection_id: str = "", inspection_number: str = "") -> Dict[str, Any]:
    """P05 IMP-16 — hasil MD Quality saja: poin cacat & grade roll TIDAK diubah.
    Tahanan yang sudah ada tidak dilepas diam-diam; pelepasan lewat keputusan MD Quality."""
    prev = roll.get("inspection") or {}
    hold, warnings = quality_hold(color_result, handfeel_result, color_action, handfeel_action,
                                  baseline_sample_number, actor)
    if not hold["held"] and (prev.get("hold") or {}).get("held"):
        hold = prev["hold"]
    sets = {f"inspection.{k}": v for k, v in {
        "color_result": color_result, "handfeel_result": handfeel_result,
        "handfeel_score": handfeel_score, "delta_e": delta_e,
        "baseline_sample_id": baseline_sample_id, "baseline_sample_number": baseline_sample_number,
        "inspection_doc_id": inspection_id, "inspection_doc_number": inspection_number,
        "hold": hold, "md_quality_by": actor.get("name", ""), "md_quality_at": now_iso(),
        # P11.5 — acuan SPK MD sendiri (inspection_doc_* ikut berganti saat 4-point disimpan).
        "md_quality_doc_id": inspection_id, "md_quality_doc_number": inspection_number}.items()}
    if not isinstance(roll.get("inspection"), dict):
        sets = {"inspection": {k.split(".", 1)[1]: v for k, v in sets.items()}}
    sets["updated_at"] = now_iso()
    sets.update(md_flag_fields(actor, inspection_number))
    await db.inventory_rolls.update_one({"id": roll["id"]}, {"$set": sets,
                                                             "$unset": {"md_quality_via_sampling": ""}})
    return {"hold": hold, "qc_warnings": warnings}


def md_flag_fields(actor: Dict[str, Any], spk_number: str = "") -> Dict[str, Any]:
    """UAT 24 Okt (P11.1) — penanda DATAR "sudah dicek MD Quality" (dulu hanya bisa diturunkan dari `inspection.*`
    bersarang, sehingga daftar/filter stok tidak bisa menjawab "roll mana yang belum dicek")."""
    return {"md_quality_checked": True, "md_quality_checked_at": now_iso(),
            "md_quality_checked_by": actor.get("name", ""), "md_quality_spk": spk_number or ""}


def four_point_flag_fields(actor: Dict[str, Any], spk_number: str = "") -> Dict[str, Any]:
    """P11.1 — penanda DATAR "sudah diinspeksi 4-point"."""
    return {"inspected_4point": True, "inspected_4point_at": now_iso(),
            "inspected_4point_by": actor.get("name", ""), "inspected_4point_spk": spk_number or ""}


async def inspect_roll(roll: Dict[str, Any], defects: List[Dict[str, Any]],
                       gsm_actual: Optional[float], width_actual: Optional[float],
                       note: str, actor: Dict[str, Any],
                       supplier_lot: str = "", dye_lot: str = "",
                       shade_ref: str = "",
                       # ─── FASE I — banding terhadap SAMPLE yang di-ACC ──────────
                       color_result: str = "", handfeel_result: str = "",
                       handfeel_score: Optional[float] = None,
                       delta_e: Optional[float] = None,
                       baseline_sample_id: str = "", baseline_sample_number: str = "",
                       color_action: str = "tahan", handfeel_action: str = "peringatkan",
                       inspection_id: str = "", inspection_number: str = "",
                       quality_from_roll: bool = False,
                       inspect_length_yard: Optional[float] = None,
                       header: Optional[Dict[str, Any]] = None,
                       grade_input: str = "",
                       ) -> Dict[str, Any]:
    """Catat inspeksi 4-point pada 1 roll → hitung poin & grade → update roll.

    FASE C (D-10/PS-10) — inspeksi adalah titik input LOT kedua setelah penerimaan:
    `supplier_lot` / `dye_lot` / `shade_ref` yang diisi petugas QC disimpan ke lot
    (SSOT `inventory_lots`) dan roll, plus jejak `lot_id` di dokumen inspeksi.
    Penegakan mengikuti pengaturan (`warn` = hanya peringatan, `block` = menolak).

    FASE I (§3.4) — hasil **warna** & **handfeel** dibanding sample yang di-ACC ikut
    disimpan DI ROLL (`inventory_rolls.inspection`), bukan hanya di dokumen inspeksi.
    Alasannya satu dan menentukan: pertanyaan *"roll ini warnanya beda dari sample,
    boleh masuk gudang?"* ditanyakan **di roll**, dan di sanalah pagar putaway
    (`location_service.putaway_roll`) membacanya. Menyimpannya hanya di dokumen
    membuat pagar itu harus menebak — atau tidak ada sama sekali.

    Kebijakan `color_action`/`handfeel_action` (`abaikan|peringatkan|tahan`) datang dari
    Pusat Pengaturan lewat pemanggilnya (`inspection_service`), sehingga tidak ada
    ambang yang tertanam di kode ini.
    """
    # Trial 22 Okt (F5, keputusan pemilik) — grade ditentukan petugas QC dari total poin; sistem tidak mengisi
    # otomatis (dicek SEBELUM apa pun ditulis).
    if not (grade_input or "").strip() and not await grade_auto(roll.get("owner_entity_id")):
        raise GradeRequired(f"Isi grade roll {roll.get('roll_no') or ''} — grade ditentukan petugas QC dari total poin "
                            f"({compute_points(defects)} poin); sistem tidak mengisi grade otomatis.")
    from services import lot_service as lots
    lot_settings = await lots.get_settings()
    lot_doc: Dict[str, Any] = {}
    if roll.get("lot_id"):
        try:
            lot_doc = await lots.get_lot(roll["lot_id"])
        except lots.LotError:
            lot_doc = {}
    eff_supplier_lot = (supplier_lot or "").strip() or lot_doc.get("supplier_lot", "") or \
        roll.get("supplier_lot", "")
    eff_dye_lot = (dye_lot or "").strip() or roll.get("dye_lot", "") or lot_doc.get("dye_lot", "")
    lot_warnings = await lots.guard_capture(eff_supplier_lot, eff_dye_lot, lot_settings)
    if lot_doc:
        patch: Dict[str, Any] = {}
        if (supplier_lot or "").strip():
            patch["supplier_lot"] = supplier_lot.strip()
        if (dye_lot or "").strip():
            patch["dye_lot"] = dye_lot.strip()
        if (shade_ref or "").strip():
            patch["shade_ref"] = shade_ref.strip()
        if patch:
            lot_doc = await lots.patch_lot(lot_doc["id"], patch,
                                           actor.get("name", "QC"))
    if (supplier_lot or "").strip():
        await db.inventory_rolls.update_one(
            {"id": roll["id"]}, {"$set": {"supplier_lot": supplier_lot.strip(),
                                          "updated_at": now_iso()}})

    th = await grade_thresholds(roll.get("owner_entity_id"))
    points = compute_points(defects)
    suggested = grade_from_points(points, th)
    from services import grade_service as _gs
    grade = _gs.normalize_or_raise(grade_input, "Grade QC") if (grade_input or "").strip() else suggested

    norm_defects = normalize_interval_defects(defects, inspect_length_yard)

    # ─── FASE I — banding terhadap sample yang di-ACC + kebijakan tahan/peringatkan ──
    prev = roll.get("inspection") or {}
    if quality_from_roll:
        # P05 IMP-16 — QC hanya mengisi 4-point: hasil MD Quality & tahanannya TIDAK disentuh.
        color_res, hand_res = prev.get("color_result", ""), prev.get("handfeel_result", "")
        handfeel_score, delta_e = prev.get("handfeel_score"), prev.get("delta_e")
        baseline_sample_id = prev.get("baseline_sample_id", baseline_sample_id)
        baseline_sample_number = prev.get("baseline_sample_number", baseline_sample_number)
        hold = prev.get("hold") or {"held": False, "reason": "", "source": "", "by": "", "at": ""}
        qc_warnings: List[str] = []
    else:
        color_res = str(color_result or "").strip().lower()
        hand_res = str(handfeel_result or "").strip().lower()
        hold, qc_warnings = quality_hold(color_res, hand_res, color_action, handfeel_action,
                                         baseline_sample_number, actor)

    import domain_registry as _dr
    form = {   # LN-051 — satuan stok TIDAK diubah; posisi cacat selalu yard
        "inspect_length_yard": (round(float(inspect_length_yard), 2) if inspect_length_yard not in (None, "") else None),
        "interval_yard": INTERVAL_YARD, "intervals": interval_count(inspect_length_yard),
        "stock_qty": float(roll.get("length_remaining") or 0), "stock_unit": roll.get("unit", ""),
        "header": {k: v for k, v in (header or {}).items() if v not in (None, "")},
    }
    rule = {"version": RULE_VERSION, "status": RULE_STATUS, "decision": "KLX-02",
            "grade_source": "user" if (grade_input or "").strip() else "system_suggestion", "suggested_grade": suggested,
            "thresholds": th, "grades": [g["value"] for g in _dr.GRADES if g.get("active", True) is not False]}
    inspection = {
        "points": points, "grade": grade,
        "defects": norm_defects, "form": form, "rule": rule,
        "raw_defects_input": [dict(d) for d in (defects or [])],
        "gsm_actual": (float(gsm_actual) if gsm_actual not in (None, "") else None),
        "width_actual": (float(width_actual) if width_actual not in (None, "") else None),
        "thresholds": th, "note": note or "",
        # FASE C — jejak lot pada dokumen inspeksi (PS-10: inspeksi wajib berlot)
        "lot_id": lot_doc.get("id", "") or roll.get("lot_id", ""),
        "lot_number": lot_doc.get("lot_number", "") or roll.get("lot", ""),
        "supplier_lot": eff_supplier_lot, "dye_lot": eff_dye_lot,
        "shade_ref": (shade_ref or "").strip() or lot_doc.get("shade_ref", ""),
        "lot_warnings": lot_warnings,
        # FASE I — hasil banding + acuannya + tahanan (dibaca pagar putaway)
        "color_result": color_res, "handfeel_result": hand_res,
        "handfeel_score": (float(handfeel_score) if handfeel_score not in (None, "") else None),
        "delta_e": (float(delta_e) if delta_e not in (None, "") else None),
        "baseline_sample_id": baseline_sample_id,
        "baseline_sample_number": baseline_sample_number,
        "inspection_doc_id": inspection_id, "inspection_doc_number": inspection_number,
        "hold": hold,
        "inspected_by": actor.get("name", "Admin"),
        "inspected_by_id": actor.get("id", ""),
        "inspected_at": now_iso(),
    }
    # Fase A · PS-09/D-23 — grade HANYA berubah lewat jalur tercatat:
    # tulis riwayat (before → after) + audit lewat `grade_service` (SSOT grade roll).
    from services import grade_service
    grade_result = await grade_service.set_roll_grade(
        roll["id"], grade, source="qc_inspection",
        reason=(f"Inspeksi 4-point: {points} poin · grade diisi QC" if (grade_input or "").strip() else
                f"Inspeksi 4-point: {points} poin (saran sistem, ambang A≤{th['a_max']}, B≤{th['b_max']})"),
        actor=actor, extra={"points": points, "inspection_note": note or ""})
    # UAT 24 Okt (P11.5) — tulis PER FIELD: menimpa seluruh objek `inspection` menghapus jejak MD Quality
    # (`md_quality_at/by/doc`) yang ditulis `record_quality`. Objek kosong/null → boleh ditulis utuh.
    sets = ({f"inspection.{k}": v for k, v in inspection.items()} if isinstance(roll.get("inspection"), dict)
            else {"inspection": inspection})
    # P11.1 — penanda datar 4-point (+ MD Quality bila hasil warna/handfeel ikut diisi di form gabungan).
    sets.update(four_point_flag_fields(actor, inspection_number))
    unset: Dict[str, Any] = {"four_point_pending": ""}
    if (color_res or hand_res) and not quality_from_roll:
        sets.update(md_flag_fields(actor, inspection_number))
        unset["md_quality_via_sampling"] = ""
    updated = await db.inventory_rolls.find_one_and_update(
        {"id": roll["id"]},
        {"$set": {"defects": norm_defects, **sets, "updated_at": now_iso()}, "$unset": unset},
        projection={"_id": 0}, return_document=True)
    return {"roll": safe_doc(updated), "points": points, "grade": grade, "thresholds": th,
            "grade_before": grade_result["grade_before"],
            "grade_history_entry": grade_result["history_entry"],
            # FASE C — lot & peringatan kelengkapan ditampilkan di panel inspeksi
            "lot": {"id": inspection["lot_id"], "lot_number": inspection["lot_number"],
                    "supplier_lot": inspection["supplier_lot"],
                    "dye_lot": inspection["dye_lot"], "shade_ref": inspection["shade_ref"],
                    "lot_status": lot_doc.get("lot_status", "")},
            "lot_warnings": lot_warnings,
            # FASE I — tahanan & peringatan selisih warna/handfeel (dipakai layar
            # inspeksi DAN pagar putaway; keduanya membaca satu hasil yang sama)
            "hold": hold, "qc_warnings": qc_warnings}


async def rolls_for_task(task_id: str) -> List[Dict[str, Any]]:
    """Roll yang menunggu/inspeksi untuk sebuah inbound task (per qc_task_id)."""
    rolls = await db.inventory_rolls.find(
        {"qc_task_id": task_id}, {"_id": 0}).sort("roll_no", 1).to_list(500)
    prod_ids = list({r.get("product_id") for r in rolls if r.get("product_id")})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": prod_ids}}, {"_id": 0}).to_list(500)}
    lot_ids = list({r.get("lot_id") for r in rolls if r.get("lot_id")})
    lots = {l["id"]: l for l in await db.inventory_lots.find(
        {"id": {"$in": lot_ids}},
        {"_id": 0, "id": 1, "lot_number": 1, "supplier_lot": 1, "dye_lot": 1,
         "shade_ref": 1, "lot_status": 1}).to_list(500)}
    out = []
    for r in rolls:
        prod = prods.get(r.get("product_id"), {})
        insp = r.get("inspection") or {}
        lot = lots.get(r.get("lot_id"), {})
        out.append({
            "id": r["id"], "roll_no": r.get("roll_no"),
            "product_id": r.get("product_id"), "sku": prod.get("sku", ""),
            "product_name": prod.get("name", ""),
            "gsm_standard": prod.get("gramasi", None), "width_standard": prod.get("lebar", None),
            "length_initial": r.get("length_initial"), "unit": r.get("unit"),
            "grade": r.get("grade", ""), "status": r.get("status", ""),
            "hold": r.get("hold") or {},
            "inspected": bool(insp.get("inspected_at")),
            "inspection": insp,
            # FASE C — identitas lot per roll (dipakai form inspeksi QC)
            "lot_id": r.get("lot_id", ""),
            "lot_number": lot.get("lot_number", "") or r.get("lot", ""),
            "supplier_lot": r.get("supplier_lot", "") or lot.get("supplier_lot", ""),
            "dye_lot": r.get("dye_lot", "") or lot.get("dye_lot", ""),
            "shade_ref": lot.get("shade_ref", ""),
            "lot_status": lot.get("lot_status", ""),
        })
    return out
