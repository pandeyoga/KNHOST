"""FASE R1 — Print job tag RFID (bulk dari GR/roll transit) + sesi verifikasi handheld.
PREP-F (9 Nov 2026) — hasil PER LABEL, job parsial, antrean tindak lanjut, pemulihan efek, cetak ulang teks vs ganti tag.

Prinsip:
- Print job TIDAK mengubah stok. Ia meng-encode tag (via rfid_service — SSOT tag)
  dan membawa payload ZPL untuk printer RFID (Chainway CP30EN, emulasi ZPL: ^RFW).
- EPC SELALU dibuat sistem (EPC bawaan tag dianggap TIDAK unik) lalu DITULIS ke chip oleh printer. EPC yang pernah
  terbit tidak pernah dipakai ulang — juga sesudah tag dipensiunkan (`allocate_epc` memeriksa SEMUA status).
- Tiap item job punya status sendiri: pending → started → confirmed | failed | unknown. Hanya item `confirmed` yang
  mengaktifkan tag & menaikkan journey; efek itu dicatat per item (`effects` pending → done) sehingga ACK yang sudah
  tersimpan tetapi efeknya gagal bisa dipulihkan TANPA cetak fisik ulang (`apply_item_effects`/`recover_pending_effects`).
- Hasil tidak pasti (`unknown`, hasil bertentangan, lease habis saat mencetak) masuk antrean tindak lanjut; operator
  berizin memutuskan dengan bukti (RFID sukses wajib bukti baca EPC oleh handheld/reader).
- Verifikasi = expected (EPC item terkonfirmasi) vs scanned (EPC dari handheld). Roll cocok naik journey tag_verified.
- Journey roll: field `inventory_rolls.journey` {stage, routing} — TIDAK menyentuh bucket status stok (Roll-as-SSOT).
"""
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from db import db
from core_utils import new_id, now_iso, next_doc_number, safe_doc
from services import rfid_service
from services import rfid_label_template as tpl
from services.epc import canonical_epc, normalize_reads
from services.zpl_text import zpl_field

JOURNEY_STAGES = [
    "received_transit", "tag_printed", "tag_verified", "label_verified", "cross_dock_ready",
    "putaway_assigned", "putaway_in_transit", "stored", "gate_exception",
]
STAGE_LABEL = {
    "received_transit": "Diterima di Transit", "tag_printed": "Tag Dicetak",
    "tag_verified": "Tag Terverifikasi", "label_verified": "Label QR Terverifikasi",
    "cross_dock_ready": "Cross-Dock (Langsung Kirim)",
    "putaway_assigned": "Masuk Putaway Order", "putaway_in_transit": "Menuju Gudang Simpan",
    "stored": "Tersimpan", "gate_exception": "Exception Gate",
}

# ─── PREP-F — model item & status job ─────────────────────────────────────────
ITEM_STATES = ("pending", "started", "confirmed", "failed", "unknown")
PRINT_STATUSES = ("confirmed", "failed", "unknown")
ENCODE_STATUSES = ("confirmed", "failed", "unknown", "not_applicable")
RFID_WRITE_KINDS = {"rfid_tag"}            # item menulis chip (^RFW)
PROFILE_KINDS = {"rfid_tag", "text_reprint"}  # dirender ulang dengan profil printer yang mengklaim
OPEN_PRINT_PHASE = ("queued", "printing")
JOB_STATUS_LABEL = {
    "queued": "Antre Cetak", "printing": "Sedang Dicetak", "printed": "Tercetak", "partial": "Tercetak Sebagian",
    "failed": "Gagal Cetak", "needs_review": "Perlu Ditinjau", "verified": "Terverifikasi",
    "verified_with_issues": "Verif. Bermasalah",
}
RESOLVE_ACTIONS = ("confirm_success", "confirm_failed", "reprint", "close")
EVIDENCE_TYPES = ("c72_scan", "visual_check", "printer_log", "other")
REPLACE_REASONS = {"damaged": "Tag rusak / tidak terbaca", "lost": "Label/tag hilang",
                   "wrong_roll": "Tertempel di roll yang salah", "print_issue": "Masalah hasil cetak",
                   "other": "Lainnya"}
REPRINT_REASONS = {"text_damaged": "Teks label rusak / pudar", "text_lost": "Label teks hilang (chip masih di roll)",
                   "qty_changed": "Isi label berubah (qty/lot)", "other": "Lainnya"}
_JOURNEY_PRINTABLE = [None, "receiving", "received_transit", "tag_printed", "cut_pending_tag"]
_IDX_DONE = False


async def ensure_indexes() -> None:
    global _IDX_DONE
    if _IDX_DONE:
        return
    try:
        await db.rfid_print_jobs.create_index([("warehouse_id", 1), ("status", 1), ("created_at", 1)],
                                              name="prep_f_wh_status")
        await db.rfid_print_jobs.create_index([("review_open", 1), ("warehouse_id", 1)], name="prep_f_review")
        await db.rfid_print_jobs.create_index([("effects_pending", 1)], name="prep_f_effects", sparse=True)
        await db.rfid_tag_events.create_index([("roll_id", 1), ("at", -1)], name="prep_f_roll")
        await db.rfid_tag_events.create_index("key", name="prep_f_event_key", unique=True, sparse=True)
        _IDX_DONE = True
    except Exception:  # noqa: BLE001 — indeks hanya optimasi; kegagalan tidak menghentikan alur
        pass


async def set_journey(roll_ids: List[str], stage: str, extra: Optional[Dict[str, Any]] = None,
                      only_from: Optional[List[Optional[str]]] = None) -> None:
    upd = {"journey.stage": stage, "journey.updated_at": now_iso(), "updated_at": now_iso()}
    for k, v in (extra or {}).items():
        upd[f"journey.{k}"] = v
    op: Dict[str, Any] = {"$set": upd}
    if stage in ("stored", "tag_verified"):  # bersihkan sisa exception dari siklus sebelumnya
        op["$unset"] = {"journey.exception_reason": ""}
    q: Dict[str, Any] = {"id": {"$in": roll_ids}}
    if only_from is not None:  # AX-08 — jangan mundurkan roll yang sudah di tahap lain
        q["journey.stage"] = {"$in": list(only_from)}
    await db.inventory_rolls.update_many(q, op)


# ─── Templat ──────────────────────────────────────────────────────────────────
def generate_rfid_zpl(epc: str, roll: Dict[str, Any], tag: Dict[str, Any],
                      profile: Optional[Dict[str, Any]] = None) -> str:
    """PREP-F — label RFID 70 × 22 mm (bawaan 203 dpi; profil printer bisa 300 dpi) + tulis EPC (^RFW,H).
    RF-01/RF-11 — EPC chip = EPC database (kanonik, divalidasi, TANPA potong); teks via ^FH."""
    snap = _snapshot(roll, tag.get("product_name", ""), tag.get("sku", ""), canonical_epc(epc))
    return tpl.render_zpl(snap, tpl.normalize_profile(profile), rfid=True)


def generate_qr_zpl(roll: Dict[str, Any], product_name: str = "") -> str:
    """ZPL label 58×40 mm (203dpi ≈ 464×320 dot) dengan QR NOMOR ROLL (tanpa encode RFID) —
    isi QR sama dengan label browser, jadi HP gudang memindainya lewat GET /rfid/lookup."""
    roll_no = zpl_field(roll.get("roll_no"), 30)
    name = zpl_field(product_name or roll.get("product_name"), 30)
    qty = zpl_field(f"{float(roll.get('length_remaining') or roll.get('length') or 0):g} {roll.get('unit', 'm')}", 20)
    lot = zpl_field(roll.get("lot") or roll.get("supplier_lot") or "-", 24)
    grade = zpl_field(roll.get("grade") or "A", 4)
    return (
        "^XA\n^CI28\n^PW464\n^LL320\n"
        f"^FO16,16^BQN,2,6^FH_^FDQA,{roll_no}^FS\n"
        f"^FO200,20^A0N,34,34^FH_^FD{roll_no}^FS\n"
        f"^FO200,64^A0N,22,22^FH_^FD{name}^FS\n"
        f"^FO200,96^A0N,24,24^FH_^FD{qty}  Grade {grade}^FS\n"
        f"^FO200,128^A0N,22,22^FH_^FDLot {lot}^FS\n"
        "^XZ"
    )


def _snapshot(roll: Dict[str, Any], product_name: str, sku: str, epc: Optional[str]) -> Dict[str, Any]:
    return {"product_name": product_name or "", "sku": sku or roll.get("sku", ""), "roll_no": roll.get("roll_no", ""),
            "lot": roll.get("lot") or roll.get("supplier_lot") or "", "qty": float(roll.get("length_remaining") or 0),
            "unit": roll.get("unit", "meter"), "grade": roll.get("grade") or "", "epc": epc or ""}


def _item_snapshot(it: Dict[str, Any]) -> Dict[str, Any]:
    """Snapshot isi label item (data job lama tanpa `label` → dibangun dari field item)."""
    return dict(it.get("label") or {
        "product_name": it.get("product_name", ""), "sku": it.get("sku", ""), "roll_no": it.get("roll_no", ""),
        "lot": it.get("lot", ""), "qty": it.get("qty", 0), "unit": it.get("unit", ""), "grade": it.get("grade", ""),
        "epc": it.get("epc") or ""})


def render_item(kind: str, it: Dict[str, Any], profile: Dict[str, Any]) -> str:
    return tpl.render_zpl(_item_snapshot(it), profile, rfid=kind in RFID_WRITE_KINDS)


def _new_item(kind: str, roll: Dict[str, Any], *, tag: Optional[Dict[str, Any]], product_name: str, sku: str,
              zpl: Optional[str] = None) -> Dict[str, Any]:
    epc = (tag or {}).get("epc")
    snap = _snapshot(roll, product_name, sku, epc)
    profile = tpl.normalize_profile(None)
    if zpl is None:
        zpl = tpl.render_zpl(snap, profile, rfid=kind in RFID_WRITE_KINDS)
    return {
        "item_id": new_id("rpi"), "roll_id": roll["id"], "roll_no": roll.get("roll_no", ""),
        "tag_id": (tag or {}).get("id"), "epc": epc, "sku": snap["sku"], "product_name": product_name,
        "lot": roll.get("lot", ""), "qty": snap["qty"], "unit": roll.get("unit", "meter"), "grade": snap["grade"],
        "label": snap, "zpl": zpl, "payload_sha256": tpl.payload_sha256(zpl), "profile_key": tpl.profile_key(profile),
        "status": "pending", "print_status": None, "encode_status": None, "results": [], "effects": None,
    }


async def allocate_epc() -> str:
    """EPC baru dari sistem yang BELUM PERNAH ada di `rfid_tags` (status apa pun) — EPC lama tak pernah dipakai ulang."""
    for _ in range(12):
        epc = rfid_service.generate_epc()
        if not await db.rfid_tags.find_one({"epc": epc}, {"_id": 1}):
            return epc
    raise HTTPException(status_code=500, detail="Gagal membuat EPC unik — coba lagi.")


async def _new_job(kind: str, items: List[Dict[str, Any]], wh_id: str, owner: Optional[str], actor_name: str,
                   source: str = "", extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    for it in items:
        it["reprint"] = bool(await _prints_count(it["roll_id"]))
    wh = await db.warehouses.find_one({"id": wh_id}, {"_id": 0, "name": 1}) or {}
    job = {
        "id": new_id("rpj"), "kind": kind, "source": source, "revision": 1,
        "job_number": await next_doc_number("rfid_print_jobs", "job_number", "PJ"),
        "warehouse_id": wh_id, "warehouse_name": wh.get("name", ""),
        "owner_entity_id": owner, "status": "queued",
        "items": items, "item_count": len(items),
        "counts": {"pending": len(items), "started": 0, "confirmed": 0, "failed": 0, "unknown": 0, "follow_up": 0},
        "review_open": 0, "print_attempts": 0, "attempts": [],
        "created_at": now_iso(), "created_by": actor_name, "printed_at": None, "verified_at": None,
        **(extra or {}),
    }
    await db.rfid_print_jobs.insert_one(dict(job))
    await ensure_indexes()
    return job


async def create_qr_label_job(roll_ids: List[str], scope_ids: List[str], actor_name: str,
                              source: str = "") -> Dict[str, Any]:
    """Antrean label QR (kind=qr_label) — satu antrean printer bersama dengan tag RFID, tanpa encode."""
    if not roll_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu roll")
    rolls = await db.inventory_rolls.find({"id": {"$in": roll_ids}}, {"_id": 0}).to_list(len(roll_ids) + 5)
    if len(rolls) != len(set(roll_ids)):
        raise HTTPException(status_code=404, detail="Sebagian roll tidak ditemukan")
    wh_id = rolls[0].get("warehouse_id")
    for roll in rolls:
        if roll.get("owner_entity_id") not in scope_ids:
            raise HTTPException(status_code=403, detail=f"Roll {roll.get('roll_no')} di luar entitas Anda")
        if roll.get("warehouse_id") != wh_id:
            raise HTTPException(status_code=400, detail="Semua roll dalam satu job harus di gudang yang sama")
    pids = list({r.get("product_id") for r in rolls})
    prods = {p["id"]: p for p in await db.products.find({"id": {"$in": pids}}, {"_id": 0, "id": 1, "name": 1, "sku": 1})
             .to_list(len(pids) or 1)}
    items = []
    for r in rolls:
        p = prods.get(r.get("product_id")) or {}
        items.append(_new_item("qr_label", r, tag=None, product_name=p.get("name", ""), sku=r.get("sku") or p.get("sku", ""),
                               zpl=generate_qr_zpl(r, p.get("name", ""))))
    job = await _new_job("qr_label", items, wh_id, rolls[0].get("owner_entity_id"), actor_name, source)
    return safe_doc(job)


async def _rollback_new_tags(tag_ids: List[str]) -> None:
    """RF-14 — job gagal di tengah: tag yang BARU lahir di job ini dicabut (roll kembali tanpa tag)."""
    for tid in tag_ids:
        t = await db.rfid_tags.find_one_and_delete({"id": tid, "status": "pending_print"}, projection={"_id": 0})
        if t:
            await db.inventory_rolls.update_one({"id": t["roll_id"], "rfid_tag_id": tid}, {"$set": {
                "rfid_tag_id": None, "tracking_mode": "barcode", "updated_at": now_iso()}})


async def create_print_job(roll_ids: List[str], scope_ids: List[str],
                           actor_name: str, source: str = "") -> Dict[str, Any]:
    if not roll_ids:
        raise HTTPException(status_code=400, detail="Pilih minimal satu roll")
    rolls = await db.inventory_rolls.find({"id": {"$in": roll_ids}}, {"_id": 0}).to_list(len(roll_ids) + 5)
    if len(rolls) != len(set(roll_ids)):
        raise HTTPException(status_code=404, detail="Sebagian roll tidak ditemukan")
    # AX-06 — validasi SELURUH roll sebelum efek samping (encode); satu job = satu owner + satu gudang
    for roll in rolls:
        if roll.get("owner_entity_id") not in scope_ids:
            raise HTTPException(status_code=403, detail=f"Roll {roll.get('roll_no')} di luar entitas Anda")
    if len({r.get("owner_entity_id") for r in rolls}) > 1:
        raise HTTPException(status_code=400, detail="Semua roll dalam satu job harus milik badan usaha yang sama")
    if len({r.get("warehouse_id") for r in rolls}) > 1:
        raise HTTPException(status_code=400, detail="Semua roll dalam satu job harus di gudang yang sama")
    items, wh_id, owner = [], rolls[0].get("warehouse_id"), rolls[0].get("owner_entity_id")
    born: List[str] = []
    try:
        for roll in rolls:
            tag = None
            if roll.get("rfid_tag_id"):
                tag = await db.rfid_tags.find_one({"id": roll["rfid_tag_id"],
                                                   "status": {"$in": list(rfid_service.LIVE_TAG_STATUSES)}}, {"_id": 0})
            if tag:
                # PREP-F — EPC yang sama tidak boleh ada di dua item terbuka (dua printer → dua chip EPC sama)
                busy = await _job_items_with_tag(tag["id"], ["pending", "started", "unknown"])
                if busy:
                    raise HTTPException(status_code=409, detail=(
                        f"Roll {roll.get('roll_no')} masih dalam antrean/tinjauan cetak "
                        f"{busy.get('job_number') or busy['id']} — selesaikan job itu dulu."))
            if not tag:
                # RF-14 — tag job baru = pending_print: belum dianggap ada sampai printer mengakui cetak.
                # PREP-F — EPC dibuat sistem & dijamin belum pernah terbit (tag bawaan dianggap tidak unik).
                tag = await rfid_service.encode_tag(roll["id"], scope_ids, epc=await allocate_epc(),
                                                    actor_name=actor_name, status="pending_print")
                born.append(tag["id"])
            try:
                canonical_epc(tag["epc"])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"Roll {roll.get('roll_no')}: {e} Retire & encode ulang tag ini.")
            items.append(_new_item("rfid_tag", roll, tag=tag, product_name=tag.get("product_name", ""),
                                   sku=tag.get("sku", "")))
        job = await _new_job("rfid_tag", items, wh_id, owner, actor_name, source)
    except Exception:
        await _rollback_new_tags(born)
        raise
    for it in items:
        if it["tag_id"] in born:
            await tag_event(it["roll_id"], it["tag_id"], it["epc"], "encoded", by=actor_name, job_id=job["id"],
                            item_id=it["item_id"], note="EPC dibuat sistem untuk dicetak")
    return safe_doc(job)


async def list_print_jobs(scope_ids: List[str], warehouse_id: Optional[str],
                          status: Optional[str], limit: int = 100) -> List[Dict[str, Any]]:
    q: Dict[str, Any] = {"owner_entity_id": {"$in": scope_ids}}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    if status:
        q["status"] = {"$in": status.split(",")} if "," in status else status
    jobs = await db.rfid_print_jobs.find(q, {"_id": 0, "items.zpl": 0, "items.results": 0}) \
        .sort("created_at", -1).to_list(limit)
    return [safe_doc(_decorate(j)) for j in jobs]


def _lease_live(job: Dict[str, Any], now: Optional[str] = None) -> bool:
    lease = job.get("lease") or {}
    return bool(lease) and (lease.get("expires_at") or "") >= (now or now_iso())


def _decorate(job: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan turunan untuk UI: label status, item basi (started tanpa lease hidup)."""
    now = now_iso()
    live = _lease_live(job, now)
    stale = 0
    for it in job.get("items") or []:
        if it.get("status") == "started" and not (live and (job.get("lease") or {}).get("attempt_id") == it.get("attempt_id")):
            it["stale"] = True
            stale += 1
    job["lease_live"] = live
    job["stale_items"] = stale
    job["status_label"] = JOB_STATUS_LABEL.get(job.get("status"), job.get("status"))
    return job


async def get_print_job(job_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    job = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Print job tidak ditemukan")
    if job.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="Print job di luar entitas Anda")
    return safe_doc(_decorate(job))


# ─── Item: migrasi job lama, agregat status ──────────────────────────────────
def _legacy_item_status(job_status: str) -> Tuple[str, Optional[str]]:
    if job_status in ("printed", "verified", "verified_with_issues"):
        return "confirmed", "done"
    return "pending", None


async def ensure_item_ids(job: Dict[str, Any]) -> Dict[str, Any]:
    """Job lama (sebelum PREP-F) tidak punya `item_id`/status item → dilengkapi sekali (CAS: hanya bila masih kosong)."""
    items = job.get("items") or []
    if all(i.get("item_id") for i in items):
        return job
    st, eff = _legacy_item_status(job.get("status", "queued"))
    full = await db.rfid_print_jobs.find_one({"id": job["id"]}, {"_id": 0})
    new_items = []
    for idx, it in enumerate((full or {}).get("items") or []):
        if not it.get("item_id"):
            it = {**it, "item_id": f"rpi_{job['id'][-10:]}_{idx}", "status": it.get("status") or st,
                  "effects": it.get("effects") or eff, "results": it.get("results") or []}
            if st == "confirmed":
                it.setdefault("print_status", "confirmed")
                it.setdefault("encode_status", "confirmed" if job.get("kind") in RFID_WRITE_KINDS else "not_applicable")
            if it.get("zpl") and not it.get("payload_sha256"):
                it["payload_sha256"] = tpl.payload_sha256(it["zpl"])
        new_items.append(it)
    await db.rfid_print_jobs.update_one({"id": job["id"], "items.item_id": {"$exists": False}},
                                        {"$set": {"items": new_items, "revision": job.get("revision") or 1}})
    return await db.rfid_print_jobs.find_one({"id": job["id"]}, {"_id": 0}) or job


def item_counts(items: List[Dict[str, Any]], lease_live: bool = True,
                lease_attempt: Optional[str] = None) -> Dict[str, int]:
    c = {k: 0 for k in ITEM_STATES}
    c["follow_up"] = 0
    c["conflict"] = 0
    for it in items:
        s = it.get("status") or "pending"
        c[s] = c.get(s, 0) + 1
        if it.get("conflict"):
            c["conflict"] += 1
        stale = s == "started" and not (lease_live and lease_attempt == it.get("attempt_id"))
        if s == "unknown" or it.get("conflict") or (s == "failed" and not it.get("resolution")) or stale:
            c["follow_up"] += 1
    return c


def compute_status(job: Dict[str, Any], items: List[Dict[str, Any]]) -> str:
    c = item_counts(items)
    if not items:
        return job.get("status") or "queued"
    if c["pending"] or c["started"]:
        progressed = c["started"] or c["confirmed"] or c["failed"] or c["unknown"]
        return "printing" if progressed else "queued"
    if c["unknown"] or c["conflict"]:
        return "needs_review"
    if c["failed"] == 0:
        phase = "printed"
    elif c["confirmed"]:
        phase = "partial"
    else:
        return "failed"
    lv = job.get("last_verify") or {}
    if lv.get("result") in ("clean", "with_issues"):
        covered = set(job.get("verify_covered_items") or [])
        confirmed = {i["item_id"] for i in items if i.get("status") == "confirmed"}
        if confirmed and confirmed <= covered:
            return "verified" if lv["result"] == "clean" else "verified_with_issues"
    return phase


async def refresh_job(job_id: str) -> Dict[str, Any]:
    """Hitung ulang status agregat + hitungan item (CAS `state_seq`, 5× coba) — tidak menimpa tulisan lebih baru."""
    for _ in range(5):
        job = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "items.zpl": 0})
        if not job:
            raise HTTPException(status_code=404, detail="Print job tidak ditemukan")
        items = job.get("items") or []
        if items and not all(i.get("item_id") for i in items):
            return job  # job lama belum dimigrasi — biarkan apa adanya
        lease = job.get("lease") or {}
        counts = item_counts(items, _lease_live(job), lease.get("attempt_id"))
        status = compute_status(job, items)
        st: Dict[str, Any] = {"status": status, "counts": counts, "review_open": counts["follow_up"],
                              "effects_pending": any(i.get("effects") == "pending" for i in items),
                              "updated_at": now_iso()}
        if counts["confirmed"] and not job.get("printed_at"):
            st["printed_at"] = now_iso()
        op: Dict[str, Any] = {"$set": st, "$inc": {"state_seq": 1}}
        if not counts["pending"] and not counts["started"] and job.get("lease"):
            op["$unset"] = {"lease": ""}   # tidak ada lagi yang perlu dicetak printer
        seq = job.get("state_seq")
        res = await db.rfid_print_jobs.update_one({"id": job_id, "state_seq": seq} if seq is not None
                                                  else {"id": job_id, "state_seq": {"$exists": False}}, op)
        if res.modified_count == 1:
            job.update(st)
            return job
    return job


# ─── LN-042-T03 — histori cetak label per roll (EPC sama, qty terkini dari ERP) ────────────
async def _prints_count(roll_id: str) -> int:
    return await db.roll_label_prints.count_documents({"roll_id": roll_id})


async def record_label_prints(items: List[Dict[str, Any]], *, kind: str, channel: str, actor_name: str,
                              job: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Append-only: satu baris per label tercetak. Idempoten per (job_id, roll_id) untuk jalur antrean."""
    out: List[Dict[str, Any]] = []
    for it in items:
        rid = it["roll_id"]
        if job and await db.roll_label_prints.find_one({"job_id": job["id"], "roll_id": rid}, {"_id": 1}):
            continue
        roll = await db.inventory_rolls.find_one({"id": rid}, {"_id": 0, "owner_entity_id": 1, "roll_no": 1}) or {}
        n = await _prints_count(rid)
        doc = {"id": new_id("rlp"), "roll_id": rid, "roll_no": it.get("roll_no") or roll.get("roll_no", ""),
               "owner_entity_id": roll.get("owner_entity_id"), "epc": it.get("epc"), "qty": float(it.get("qty") or 0),
               "unit": it.get("unit", ""), "kind": kind, "channel": channel, "reprint": n > 0, "print_seq": n + 1,
               "job_id": (job or {}).get("id"), "job_number": (job or {}).get("job_number"),
               "item_id": it.get("item_id"), "by": actor_name, "at": now_iso()}
        await db.roll_label_prints.insert_one(dict(doc))
        out.append(doc)
    return out


async def roll_print_history(roll: Dict[str, Any]) -> Dict[str, Any]:
    rows = await db.roll_label_prints.find({"roll_id": roll["id"]}, {"_id": 0}).sort("at", -1).to_list(200)
    tag = await db.rfid_tags.find_one({"id": roll.get("rfid_tag_id")}, {"_id": 0, "epc": 1, "status": 1})         if roll.get("rfid_tag_id") else None
    current = float(roll.get("length_remaining") or 0)
    last = rows[0] if rows else None
    return {"roll_id": roll["id"], "roll_no": roll.get("roll_no"), "epc": (tag or {}).get("epc"),
            "current_qty": current, "unit": roll.get("unit", ""), "prints": rows, "prints_count": len(rows),
            "last_printed_qty": (last or {}).get("qty"),
            "label_outdated": bool(last) and abs(float(last.get("qty") or 0) - current) > 1e-6}


# ─── Riwayat tag ↔ roll (append-only) ─────────────────────────────────────────
async def tag_event(roll_id: str, tag_id: Optional[str], epc: Optional[str], event: str, *, by: str = "",
                    reason: str = "", note: str = "", job_id: Optional[str] = None, item_id: Optional[str] = None,
                    key: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> None:
    """`key` = kunci idempoten (efek yang dipulihkan tidak menggandakan baris riwayat)."""
    from pymongo.errors import DuplicateKeyError
    doc = {"id": new_id("rte"), "roll_id": roll_id, "tag_id": tag_id, "epc": epc, "event": event, "reason": reason,
           "note": note, "job_id": job_id, "item_id": item_id, "by": by, "at": now_iso(), **(extra or {})}
    if key:
        doc["key"] = key
        if await db.rfid_tag_events.find_one({"key": key}, {"_id": 1}):
            return
    try:
        await db.rfid_tag_events.insert_one(doc)
    except DuplicateKeyError:
        return


async def roll_tag_history(roll: Dict[str, Any]) -> Dict[str, Any]:
    tags = await db.rfid_tags.find({"roll_id": roll["id"]}, {"_id": 0}).sort("encoded_at", 1).to_list(100)
    events = await db.rfid_tag_events.find({"roll_id": roll["id"]}, {"_id": 0}).sort("at", -1).to_list(300)
    return {"roll_id": roll["id"], "roll_no": roll.get("roll_no"), "current_tag_id": roll.get("rfid_tag_id"),
            "tags": [{k: t.get(k) for k in ("id", "epc", "status", "encoded_at", "encoded_by", "activated_at",
                                             "retired_at", "retire_reason", "replaced_by_tag_id", "replaces_tag_id")}
                     for t in tags],
            "events": events}


# ─── Efek SESUDAH item terkonfirmasi (idempoten, bisa dipulihkan) ─────────────
async def _item_effects(job: Dict[str, Any], items: List[Dict[str, Any]]) -> None:
    actor = job.get("printed_by") or job.get("created_by", "")
    await record_label_prints(items, kind=job.get("kind", "rfid_tag"), channel="print_queue", actor_name=actor, job=job)
    if job.get("kind") not in RFID_WRITE_KINDS:
        return
    # FIX-3b (RFID-3) — item tanpa bukti chip (tandai tercetak manual) tidak mengaktifkan tag; aktif saat verifikasi.
    unproven = [i for i in items if i.get("encode_status") == "unverified"]
    for it in unproven:
        await tag_event(it["roll_id"], it.get("tag_id"), it.get("epc"), "printed_unverified", by=actor,
                        job_id=job["id"], item_id=it.get("item_id"), key=f"printed_unverified:{it.get('tag_id')}:{job['id']}",
                        note="Ditandai tercetak manual — tag aktif sesudah EPC terbaca di sesi Verifikasi")
    items = [i for i in items if i.get("encode_status") != "unverified"]
    tag_ids = [i["tag_id"] for i in items if i.get("tag_id")]
    if tag_ids:
        await db.rfid_tags.update_many({"id": {"$in": tag_ids}, "status": "pending_print"},
                                       {"$set": {"status": "active", "activated_at": now_iso(),
                                                 "activated_by_job": job["id"]}})
    # roll yang tagnya sudah diganti sejak job dibuat TIDAK disentuh (journey milik tag yang sekarang)
    linked = {r["id"] async for r in db.inventory_rolls.find(
        {"id": {"$in": [i["roll_id"] for i in items]}, "rfid_tag_id": {"$in": tag_ids}}, {"_id": 0, "id": 1})}
    if linked:
        await set_journey(list(linked), "tag_printed", {"print_job_id": job["id"]}, only_from=_JOURNEY_PRINTABLE)
    for it in items:
        await tag_event(it["roll_id"], it.get("tag_id"), it.get("epc"), "activated", by=actor, job_id=job["id"],
                        item_id=it.get("item_id"), key=f"activated:{it.get('tag_id')}:{job['id']}",
                        note="Printer/ operator mengonfirmasi label tercetak & chip tertulis")


async def apply_item_effects(job_id: str, item_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """RF-14/RACC-30 — lengkapi efek item `confirmed` yang belum selesai. Aman diulang: tiap langkah idempoten."""
    job = await db.rfid_print_jobs.find_one({"id": job_id}, {"_id": 0, "items.zpl": 0})
    if not job:
        return {"applied": 0}
    targets = [i for i in job.get("items") or [] if i.get("status") == "confirmed" and i.get("effects") != "done"
               and (item_ids is None or i.get("item_id") in item_ids)]
    if not targets:
        return {"applied": 0}
    try:
        await _item_effects(job, targets)
    except Exception as e:  # noqa: BLE001 — status cetak sudah durable; efek dipulihkan kemudian
        await db.rfid_print_jobs.update_one({"id": job_id}, {"$set": {
            "effects_pending": True, "effects_error": str(e)[:300], "effects_error_at": now_iso()}})
        raise
    for it in targets:
        await db.rfid_print_jobs.update_one(
            {"id": job_id}, {"$set": {"items.$[it].effects": "done", "items.$[it].effects_at": now_iso()}},
            array_filters=[{"it.item_id": it["item_id"], "it.status": "confirmed"}])
    await db.rfid_print_jobs.update_one({"id": job_id}, {"$unset": {"effects_error": "", "effects_error_at": ""}})
    await refresh_job(job_id)
    return {"applied": len(targets)}


async def recover_pending_effects(warehouse_id: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
    """Sapu job yang status cetaknya tersimpan tetapi efeknya belum selesai (crash/galat di antara keduanya)."""
    q: Dict[str, Any] = {"effects_pending": True}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    done, failed = 0, []
    async for j in db.rfid_print_jobs.find(q, {"_id": 0, "id": 1}).limit(limit):
        try:
            done += (await apply_item_effects(j["id"]))["applied"]
        except Exception as e:  # noqa: BLE001
            failed.append({"job_id": j["id"], "error": str(e)[:200]})
    return {"recovered_items": done, "failed": failed}


async def on_printed(job: Dict[str, Any]) -> None:
    """RF-14 — efek SESUDAH printer/operator mengakui cetak (kompatibel lama): kini per item, idempoten."""
    await apply_item_effects(job["id"])


def _confirm_all_update(evidence: str, extra: Dict[str, Any]) -> Dict[str, Any]:
    """$set untuk menandai semua item pending/started `confirmed` (ACK tingkat job lama / tandai manual)."""
    now = now_iso()
    return {**extra,
            "items.$[p].status": "confirmed", "items.$[p].print_status": "confirmed",
            "items.$[p].encode_status": "confirmed", "items.$[p].result_at": now,
            "items.$[p].evidence": {"source": evidence, "at": now}, "items.$[p].effects": "pending"}


async def mark_printed(job_id: str, scope_ids: List[str], actor_name: str = "") -> Dict[str, Any]:
    job = await get_print_job(job_id, scope_ids)
    if job["status"] != "queued":
        raise HTTPException(status_code=400, detail=f"Job sudah berstatus {job['status']}")
    job = await ensure_item_ids(job)
    st = _confirm_all_update("operator_manual", {"status": "printed", "printed_at": now_iso(), "printed_via": "manual",
                                                 "printed_by": actor_name or job.get("created_by", ""),
                                                 "updated_at": now_iso(), "effects_pending": True})
    if job.get("kind") not in RFID_WRITE_KINDS:
        st["items.$[p].encode_status"] = "not_applicable"
    else:
        # FIX-3b (RFID-3, K-B2b-13, PREP-F §9.3/RACC-24) — "tandai tercetak" manual hanya bukti CETAK, bukan bukti
        # CHIP: tag tetap `pending_print` sampai EPC-nya terbaca di sesi Verifikasi (baca balik) — dulu tag langsung
        # `active` tanpa bukti chip tertulis.
        st["items.$[p].encode_status"] = "unverified"
    won = await db.rfid_print_jobs.find_one_and_update(
        {"id": job_id, "status": "queued", "items.status": {"$nin": ["started"]}},
        {"$set": st, "$unset": {"lease": ""}}, array_filters=[{"p.status": {"$in": ["pending", None]}}],
        projection={"_id": 0, "items.zpl": 0})
    if not won:
        raise HTTPException(status_code=409, detail="Job baru saja berubah status — muat ulang.")
    try:
        await apply_item_effects(job_id)
    except Exception:  # noqa: BLE001 — status tersimpan; efek dipulihkan sapuan berikutnya
        pass
    await refresh_job(job_id)
    return await get_print_job(job_id, scope_ids)


def job_zpl(job: Dict[str, Any]) -> str:
    return "\n".join(i.get("zpl", "") for i in job.get("items", []))


# ─── Sesi verifikasi bersama (print_verify | loading_check | cycle_count) ────
SCAN_SOURCES = {"manual", "device", "simulated"}


async def scan_session(session_id: str, epcs: List[str], scope_ids: Optional[List[str]], kinds: List[str],
                       source: str = "manual", actor: str = "", device_id: Optional[str] = None,
                       device_name: Optional[str] = None) -> Dict[str, Any]:
    """RF-10 — scan atomik ($addToSet) berprasyarat kind + open + belum diklaim complete.
    RF-07 — asal scan dicatat; scan 'simulated' tidak pernah menghasilkan hasil operasional."""
    if source not in SCAN_SOURCES:
        raise HTTPException(status_code=400, detail="Sumber scan tidak dikenal")
    sess = await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0, "expected": 0, "scanned_epcs": 0})
    if not sess or _kind(sess) not in kinds:
        raise HTTPException(status_code=404, detail="Sesi verifikasi tidak ditemukan")
    if scope_ids is not None:
        owners = list(sess.get("scope_entity_ids") or [sess.get("owner_entity_id")])
        if not all(owners) or not set(owners) <= set(scope_ids):
            raise HTTPException(status_code=403, detail="Sesi di luar entitas Anda")
    clean = normalize_reads(epcs)
    upd: Dict[str, Any] = {
        "$addToSet": {"scanned_epcs": {"$each": clean}, "scan_sources": source},
        "$set": {"updated_at": now_iso()},
        "$push": {"scan_log": {"$each": [{"at": now_iso(), "source": source, "by": actor, "device_id": device_id,
                                          "device_name": device_name, "count": len(clean),
                                          "epcs": clean[:50]}], "$slice": -200}},
    }
    if source == "simulated":
        upd["$addToSet"]["simulated_epcs"] = {"$each": clean}
    elif source == "manual":   # FIX-3b (K-B3b-02) — EPC ditempel/diketik: dicatat, bukan bukti perangkat
        upd["$addToSet"]["manual_epcs"] = {"$each": clean}
    else:
        upd["$addToSet"]["proof_epcs"] = {"$each": clean}
    res = await db.rfid_verify_sessions.update_one(
        {"id": session_id, "status": "open", "saga_lock": {"$exists": False}}, upd)
    if res.matched_count != 1:
        raise HTTPException(status_code=400, detail="Sesi sudah selesai / sedang diselesaikan — scan ditolak.")
    return await _verify_progress(session_id)


async def scan_verify(session_id: str, epcs: List[str], scope_ids: List[str],
                      kinds: Optional[List[str]] = None, source: str = "manual", actor: str = "") -> Dict[str, Any]:
    return await scan_session(session_id, epcs, scope_ids, kinds or ["print_verify"], source, actor)


def _kind(sess: Dict[str, Any]) -> str:
    return sess.get("kind") or ("print_verify" if sess.get("print_job_id") else "")


def evidence_result(sess: Dict[str, Any], clean: bool) -> str:
    """RF-07 — bukti simulasi = 'simulated' (tidak membuka dispatch / journey); selain itu clean|with_issues."""
    if "simulated" in (sess.get("scan_sources") or []):
        return "simulated"
    return "clean" if clean else "with_issues"


async def _verify_progress(session_id: str) -> Dict[str, Any]:
    sess = await db.rfid_verify_sessions.find_one({"id": session_id}, {"_id": 0})
    if not sess:
        raise HTTPException(status_code=404, detail="Sesi verifikasi tidak ditemukan")
    expected = {e["epc"] for e in sess.get("expected", [])}
    scanned = set(sess.get("scanned_epcs") or [])
    sess["kind"] = _kind(sess)
    sess["matched_count"] = len(expected & scanned)
    sess["expected_count"] = len(expected)
    sess["missing"] = sorted(expected - scanned)
    sess["extra"] = sorted(scanned - expected)
    sess["simulated"] = "simulated" in (sess.get("scan_sources") or [])
    return safe_doc(sess)


async def start_verify(job_id: str, scope_ids: List[str], actor_name: str) -> Dict[str, Any]:
    job = await get_print_job(job_id, scope_ids)
    if job.get("kind") in ("qr_label", "text_reprint"):
        raise HTTPException(status_code=400, detail="Label tanpa tulis chip tidak diverifikasi lewat RFID")
    if job["status"] == "queued":
        raise HTTPException(status_code=400, detail="Job belum dicetak — tandai tercetak / tunggu printer dulu.")
    if job["status"] == "printing":
        raise HTTPException(status_code=400, detail="Job masih dicetak printer — tunggu sampai semua label selesai.")
    job = await ensure_item_ids(job)
    confirmed = [i for i in job.get("items") or [] if i.get("status") == "confirmed"]
    if not confirmed:
        raise HTTPException(status_code=400, detail="Belum ada label yang terkonfirmasi tercetak — tinjau hasil cetak dulu.")
    # RF-14 — verifikasi bermasalah/simulasi boleh DIULANG (revisi baru); yang bersih tidak (kecuali ada label
    # terkonfirmasi baru yang belum tercakup verifikasi terakhir).
    covered = set(job.get("verify_covered_items") or [])
    uncovered = [i for i in confirmed if i["item_id"] not in covered]
    if job["status"] == "verified" and not uncovered:
        raise HTTPException(status_code=400, detail=f"Job berstatus {job['status']} — tidak bisa diverifikasi ulang")
    existing = await db.rfid_verify_sessions.find_one(
        {"print_job_id": job_id, "status": "open"}, {"_id": 0})
    if existing:
        return await _verify_progress(existing["id"])
    revision = await db.rfid_verify_sessions.count_documents({"print_job_id": job_id}) + 1
    sess = {
        "id": new_id("rvs"), "kind": "print_verify", "print_job_id": job_id, "job_number": job.get("job_number", ""),
        "revision": revision,
        "warehouse_id": job.get("warehouse_id"), "owner_entity_id": job.get("owner_entity_id"),
        "expected": [{"epc": i["epc"], "roll_id": i["roll_id"], "roll_no": i["roll_no"], "item_id": i["item_id"],
                      "sku": i.get("sku", ""), "product_name": i.get("product_name", "")} for i in confirmed],
        "scanned_epcs": [], "missing": [], "extra": [], "scan_sources": [],
        "status": "open", "created_at": now_iso(), "created_by": actor_name,
        "completed_at": None,
    }
    await db.rfid_verify_sessions.insert_one(dict(sess))
    return await _verify_progress(sess["id"])


async def _activate_proven_tags(prog: Dict[str, Any], job: Dict[str, Any], session_id: str) -> int:
    """FIX-3b (RFID-3) — item "tercetak manual" (`encode_status=unverified`) yang EPC-nya TERBACA di sesi verifikasi
    nyata: tag `pending_print → active` + item `encode_status=confirmed` (bukti: sesi verifikasi). EPC yang tidak
    terbaca tetap `pending_print` (gate tidak menganggapnya identitas sah)."""
    scanned = set(prog.get("scanned_epcs") or [])
    items = [i for i in job.get("items") or [] if i.get("encode_status") == "unverified" and i.get("epc") in scanned
             and i.get("tag_id")]
    n = 0
    for it in items:
        t = await db.rfid_tags.find_one_and_update(
            {"id": it["tag_id"], "status": "pending_print", "roll_id": it["roll_id"]},
            {"$set": {"status": "active", "activated_at": now_iso(), "activated_by_job": job["id"],
                      "activated_via": "verify_session", "activation_ref": session_id}}, projection={"_id": 0})
        await db.rfid_print_jobs.update_one(
            {"id": job["id"]}, {"$set": {"items.$[it].encode_status": "confirmed",
                                         "items.$[it].chip_evidence": {"source": "verify_session", "ref": session_id,
                                                                       "at": now_iso()}}},
            array_filters=[{"it.item_id": it.get("item_id")}])
        if t:
            n += 1
            await tag_event(it["roll_id"], it["tag_id"], it.get("epc"), "activated", by=job.get("printed_by", ""),
                            job_id=job["id"], item_id=it.get("item_id"), key=f"activated:{it['tag_id']}:{job['id']}",
                            note="EPC terbaca di sesi verifikasi (bukti chip) — tag aktif")
    return n


async def complete_verify(session_id: str, scope_ids: List[str]) -> Dict[str, Any]:
    prog = await _verify_progress(session_id)
    if prog["kind"] != "print_verify":
        raise HTTPException(status_code=400, detail="Bukan sesi verifikasi cetak")
    if prog.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="Sesi di luar entitas Anda")
    if prog["status"] != "open":
        raise HTTPException(status_code=400, detail="Sesi sudah selesai")
    # Sesi 14 — klaim saga sesi verifikasi (status open) sesudah validasi, sebelum job/journey ditulis.
    from services import atomic_claim as _saga
    await _saga.claim("rfid_verify_sessions", session_id, "verify_complete", actor="", precondition={"status": "open"})
    prog = await _verify_progress(session_id)  # RF-10 — snapshot SESUDAH klaim (scan terlambat ditolak)
    result = evidence_result(prog, not prog["missing"] and not prog["extra"])
    matched_rolls = [e["roll_id"] for e in prog["expected"] if e["epc"] in set(prog["scanned_epcs"])]
    try:
        if result == "simulated":  # RF-07 — tidak mengubah job/journey/identitas produksi
            await db.rfid_print_jobs.update_one({"id": prog["print_job_id"]}, {"$set": {
                "last_verify": {"session_id": session_id, "result": "simulated", "at": now_iso()}}})
        else:
            covered = [e.get("item_id") for e in prog["expected"] if e.get("item_id")]
            job_now = await db.rfid_print_jobs.find_one({"id": prog["print_job_id"]}, {"_id": 0, "items.zpl": 0}) or {}
            if not covered:  # sesi lama tanpa item_id → seluruh item terkonfirmasi dianggap tercakup
                covered = [i.get("item_id") for i in job_now.get("items") or [] if i.get("item_id")]
            await db.rfid_print_jobs.update_one({"id": prog["print_job_id"]}, {"$set": {
                "status": "verified" if result == "clean" else "verified_with_issues",
                "last_verify": {"session_id": session_id, "result": result, "at": now_iso()},
                "verify_covered_items": covered, "verified_at": now_iso(), "updated_at": now_iso()}})
            await refresh_job(prog["print_job_id"])  # item tinjauan terbuka → status tetap needs_review
            await _activate_proven_tags(prog, job_now, session_id)   # FIX-3b (RFID-3) — bukti baca EPC
            if matched_rolls:
                await set_journey(matched_rolls, "tag_verified", {"verify_session_id": session_id},
                                  only_from=[None, "received_transit", "tag_printed", "tag_verified", "cut_pending_tag"])
                # G3 D4-TAG-01 — bukti verifikasi terikat ke tag yang TERBACA (aktif & tertaut)
                epc_roll = {e["epc"]: e["roll_id"] for e in prog["expected"] if e["epc"] in set(prog["scanned_epcs"])}
                async for t in db.rfid_tags.find({"epc": {"$in": list(epc_roll)}, "status": "active"},
                                                 {"_id": 0, "id": 1, "epc": 1, "roll_id": 1}):
                    if t.get("roll_id") == epc_roll.get(t["epc"]):
                        await db.inventory_rolls.update_one(
                            {"id": t["roll_id"], "rfid_tag_id": t["id"]},
                            {"$set": {"journey.verified_tag_id": t["id"], "journey.verified_at": now_iso()}})
                from services.roll_service import mark_cut_identity_verified
                await mark_cut_identity_verified(matched_rolls, "rfid_verify", session_id)
    except Exception as e:
        await _saga.mark_failed("rfid_verify_sessions", session_id, str(e))
        raise
    await db.rfid_verify_sessions.update_one({"id": session_id}, _saga.finish_set({
        "status": "completed", "result": result, "missing": prog["missing"], "extra": prog["extra"],
        "completed_at": now_iso()}))
    return await _verify_progress(session_id)


async def set_routing(roll_ids: List[str], routing: str, scope_ids: List[str],
                      actor_name: str) -> Dict[str, Any]:
    """Keputusan admin: store (putaway) vs cross_dock (langsung kirim, tetap di transit)."""
    if routing not in ("store", "cross_dock"):
        raise HTTPException(status_code=400, detail="Routing harus 'store' atau 'cross_dock'")
    rolls = await db.inventory_rolls.find(
        {"id": {"$in": roll_ids}, "owner_entity_id": {"$in": scope_ids}},
        {"_id": 0, "id": 1, "journey": 1}).to_list(len(roll_ids) + 5)
    if len(rolls) != len(set(roll_ids)):
        raise HTTPException(status_code=403, detail="Sebagian roll tidak ditemukan / di luar entitas")
    now = now_iso()
    for r in rolls:
        stage = (r.get("journey") or {}).get("stage") or "received_transit"
        if routing == "cross_dock" and stage in ("tag_verified", "label_verified", "cross_dock_ready"):
            stage = "cross_dock_ready"
        elif routing == "store" and stage == "cross_dock_ready":
            stage = "label_verified" if (r.get("journey") or {}).get("verified_via") == "label_scan" else "tag_verified"
        await db.inventory_rolls.update_one({"id": r["id"]}, {"$set": {
            "journey.routing": routing, "journey.stage": stage,
            "journey.routing_by": actor_name, "journey.updated_at": now, "updated_at": now}})
    return {"updated": len(rolls), "routing": routing}


# ─── PREP-F — antrean tindak lanjut (hasil tidak pasti / gagal / bertentangan) ────────────
def _follow_up_reason(job: Dict[str, Any], it: Dict[str, Any], live: bool) -> Optional[str]:
    s = it.get("status")
    if it.get("conflict"):
        return "conflict"
    if s == "unknown":
        return "unknown"
    if s == "started" and not (live and (job.get("lease") or {}).get("attempt_id") == it.get("attempt_id")):
        return "stale_started"
    if s == "failed" and not it.get("resolution"):
        return "failed"
    return None


FOLLOW_UP_LABEL = {
    "unknown": "Hasil tidak pasti", "conflict": "Hasil bertentangan", "failed": "Gagal — perlu tindak lanjut",
    "stale_started": "Klaim printer habis saat mencetak",
}


async def follow_up_items(scope_ids: List[str], warehouse_id: Optional[str] = None,
                          limit: int = 500) -> List[Dict[str, Any]]:
    await ensure_indexes()
    now = now_iso()
    q: Dict[str, Any] = {"owner_entity_id": {"$in": scope_ids},
                         "$or": [{"review_open": {"$gt": 0}},
                                 {"status": "printing", "$or": [{"lease": {"$exists": False}},
                                                                {"lease.expires_at": {"$lt": now}}]}]}
    if warehouse_id:
        q["warehouse_id"] = warehouse_id
    rows: List[Dict[str, Any]] = []
    async for j in db.rfid_print_jobs.find(q, {"_id": 0, "items.zpl": 0}).sort("created_at", 1).limit(200):
        live = _lease_live(j, now)
        for it in j.get("items") or []:
            reason = _follow_up_reason(j, it, live)
            if not reason:
                continue
            last = (it.get("results") or [{}])[-1]
            rows.append({"job_id": j["id"], "job_number": j.get("job_number"), "kind": j.get("kind"),
                         "warehouse_id": j.get("warehouse_id"), "warehouse_name": j.get("warehouse_name"),
                         "item_id": it.get("item_id"), "roll_id": it.get("roll_id"), "roll_no": it.get("roll_no"),
                         "sku": it.get("sku"), "product_name": it.get("product_name"), "epc": it.get("epc"),
                         "status": it.get("status"), "print_status": it.get("print_status"),
                         "encode_status": it.get("encode_status"), "reason": reason,
                         "reason_label": FOLLOW_UP_LABEL[reason], "attempt_id": it.get("attempt_id"),
                         "device_id": it.get("start_device_id"), "started_at": it.get("started_at"),
                         "result_at": it.get("result_at"), "evidence": it.get("evidence") or last.get("evidence"),
                         "results_count": len(it.get("results") or []),
                         "chip_written": it.get("encode_status") == "confirmed" and it.get("print_status") == "failed"})
            if len(rows) >= limit:
                return rows
    return rows


async def _epc_read_since(epc: str, since: Optional[str]) -> Optional[Dict[str, Any]]:
    """Bukti baca EPC oleh handheld/reader sejak item mulai dicetak (sesi verifikasi atau rfid_reads)."""
    sess = await db.rfid_verify_sessions.find_one({"scanned_epcs": epc, **({"updated_at": {"$gte": since}} if since else {}),
                                                   "scan_sources": {"$ne": "simulated"}},
                                                  {"_id": 0, "id": 1, "kind": 1, "updated_at": 1})
    if sess:
        return {"source": "verify_session", "ref": sess["id"], "at": sess.get("updated_at")}
    read = await db.rfid_reads.find_one({"epc": epc, **({"timestamp": {"$gte": since}} if since else {}),
                                         "source": {"$ne": "simulated"}},
                                        {"_id": 0, "id": 1, "device_name": 1, "timestamp": 1})
    if read:
        return {"source": "rfid_read", "ref": read["id"], "at": read.get("timestamp"), "device": read.get("device_name")}
    return None


async def _retire_live_tag(tag_id: str, reason: str, actor: str, *, note: str = "",
                           job_id: Optional[str] = None, item_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Pensiunkan tag hidup (active/pending_print) + lepas dari roll. EPC-nya tidak pernah dipakai ulang."""
    t = await db.rfid_tags.find_one_and_update(
        {"id": tag_id, "status": {"$in": list(rfid_service.LIVE_TAG_STATUSES)}},
        {"$set": {"status": "retired", "retired_at": now_iso(), "retire_reason": reason, "retired_by": actor}},
        projection={"_id": 0})
    if not t:
        return None
    if t.get("roll_id"):
        await db.inventory_rolls.update_one(
            {"id": t["roll_id"], "rfid_tag_id": tag_id},
            {"$set": {"rfid_tag_id": None, "tracking_mode": "barcode", "updated_at": now_iso()},
             "$unset": {"journey.verified_tag_id": ""}})  # G3 D4-TAG-01 — bukti verifikasi gugur
        await tag_event(t["roll_id"], tag_id, t.get("epc"), "retired", by=actor, reason=reason, note=note,
                        job_id=job_id, item_id=item_id)
    return t


async def _assert_roll_not_moving(roll_id: str) -> None:
    moving = await db.inventory_rolls.find_one(
        {"id": roll_id, "active_movement.id": {"$exists": True}}, {"_id": 0, "active_movement": 1})
    if moving and (moving.get("active_movement") or {}).get("id"):
        mv = moving["active_movement"]
        raise HTTPException(status_code=409, detail=(
            f"Roll sedang dalam perpindahan {mv.get('number') or mv['id']} — selesaikan/batalkan dulu "
            "sebelum mengganti tag."))


async def _job_items_with_tag(tag_id: str, statuses: List[str]) -> Optional[Dict[str, Any]]:
    return await db.rfid_print_jobs.find_one(
        {"items": {"$elemMatch": {"tag_id": tag_id, "status": {"$in": statuses}}}},
        {"_id": 0, "id": 1, "job_number": 1})


async def resolve_item(job_id: str, item_id: str, scope_ids: List[str], actor: str, action: str, note: str,
                       evidence_type: str = "other", evidence_ref: str = "") -> Dict[str, Any]:
    """Keputusan operator berizin atas item tindak lanjut. Bukti & alasan wajib; seluruh hasil lama tetap berjejak."""
    if action not in RESOLVE_ACTIONS:
        raise HTTPException(status_code=400, detail="Tindakan tidak dikenal")
    if evidence_type not in EVIDENCE_TYPES:
        raise HTTPException(status_code=400, detail="Jenis bukti tidak dikenal")
    if len((note or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Catatan alasan wajib diisi (min. 5 huruf)")
    job = await get_print_job(job_id, scope_ids)
    job = await ensure_item_ids(job)
    it = next((i for i in job.get("items") or [] if i.get("item_id") == item_id), None)
    if not it:
        raise HTTPException(status_code=404, detail="Item job tidak ditemukan")
    live = _lease_live(job)
    reason = _follow_up_reason(job, it, live)
    if not reason:
        raise HTTPException(status_code=409, detail="Item ini tidak sedang menunggu tindak lanjut — muat ulang.")
    rfid = job.get("kind") in RFID_WRITE_KINDS
    if action == "close" and reason != "failed":
        raise HTTPException(status_code=400, detail="'Tutup' hanya untuk item gagal; hasil tidak pasti diputuskan dulu.")
    evidence: Dict[str, Any] = {"type": evidence_type, "ref": (evidence_ref or "")[:120]}
    if action == "confirm_success":
        if rfid:
            if evidence_type != "c72_scan":
                raise HTTPException(status_code=400, detail=(
                    "Konfirmasi sukses label RFID wajib bukti baca EPC oleh handheld/reader (pilih bukti 'Pindai C72')."))
            seen = await _epc_read_since(it.get("epc") or "", it.get("started_at") or job.get("created_at"))
            if not seen:
                raise HTTPException(status_code=400, detail=(
                    f"EPC {it.get('epc')} belum pernah terbaca handheld/reader sejak label dicetak — pindai labelnya "
                    "dulu (sesi verifikasi), lalu putuskan."))
            evidence["read"] = seen
        new_status, eff = "confirmed", "pending"
    elif action in ("confirm_failed", "reprint", "close"):
        new_status, eff = "failed", None
    resolution = {"action": action, "by": actor, "at": now_iso(), "note": note.strip()[:500], "evidence": evidence,
                  "previous_status": it.get("status"), "reason": reason}
    st = {"items.$[it].resolution": resolution, "items.$[it].conflict": False, "updated_at": now_iso()}
    if new_status != it.get("status"):
        st["items.$[it].status"] = new_status
        if new_status == "confirmed":
            st["items.$[it].effects"] = eff
            st["items.$[it].print_status"] = "confirmed"
            if rfid:
                st["items.$[it].encode_status"] = "confirmed"
    res = await db.rfid_print_jobs.update_one(
        {"id": job_id}, {"$set": st, "$inc": {"revision": 1}},
        array_filters=[{"it.item_id": item_id, "it.status": it.get("status")}])
    if res.modified_count != 1:
        raise HTTPException(status_code=409, detail="Item berubah bersamaan — muat ulang lalu putuskan lagi.")
    out: Dict[str, Any] = {"item_id": item_id, "action": action, "status": new_status}
    if new_status == "confirmed":
        try:
            await apply_item_effects(job_id, [item_id])
        except Exception:  # noqa: BLE001
            out["effects_pending"] = True
    elif rfid and it.get("tag_id"):
        # Item gagal/ditutup: tag EPC-nya TIDAK boleh tetap hidup (chip bisa saja tertulis) → pensiun.
        why = "print_uncertain" if reason in ("unknown", "stale_started", "conflict") else "print_failed"
        await _retire_live_tag(it["tag_id"], why, actor, note=note, job_id=job_id, item_id=item_id)
    if action == "reprint":
        roll = await db.inventory_rolls.find_one({"id": it["roll_id"]}, {"_id": 0})
        if not roll:
            raise HTTPException(status_code=404, detail="Roll item tidak ditemukan")
        if rfid:
            new_job = await create_print_job([roll["id"]], scope_ids, actor, source="reprint")
            new_tag = (new_job.get("items") or [{}])[0]
            await db.rfid_tags.update_one({"id": new_tag.get("tag_id")}, {"$set": {"replaces_tag_id": it.get("tag_id")}})
            if it.get("tag_id"):
                await db.rfid_tags.update_one({"id": it["tag_id"]}, {"$set": {"replaced_by_tag_id": new_tag.get("tag_id")}})
        elif job.get("kind") == "qr_label":
            new_job = await create_qr_label_job([roll["id"]], scope_ids, actor, source="reprint")
        else:
            new_job = await create_text_reprint_job(roll["id"], scope_ids, actor, "other", f"Cetak ulang: {note}")
        await db.rfid_print_jobs.update_one(
            {"id": job_id}, {"$set": {"items.$[it].superseded_by": {"job_id": new_job["id"],
                                                                     "job_number": new_job.get("job_number")}}},
            array_filters=[{"it.item_id": item_id}])
        await db.rfid_print_jobs.update_one({"id": new_job["id"]}, {"$set": {
            "reprint_of": {"job_id": job_id, "job_number": job.get("job_number"), "item_id": item_id}}})
        out["reprint_job"] = {"id": new_job["id"], "job_number": new_job.get("job_number"),
                              "epc": (new_job.get("items") or [{}])[0].get("epc")}
    await refresh_job(job_id)
    return out


# ─── PREP-F — cetak ulang teks vs ganti tag ───────────────────────────────────
async def create_text_reprint_job(roll_id: str, scope_ids: List[str], actor: str, reason_code: str,
                                  note: str) -> Dict[str, Any]:
    """Label pengganti TEKS SAJA untuk roll yang chip-nya masih baik: identitas (EPC) tetap, tanpa tulis chip."""
    if reason_code not in REPRINT_REASONS:
        raise HTTPException(status_code=400, detail="Alasan cetak ulang tidak dikenal")
    if len((note or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Catatan alasan wajib diisi (min. 5 huruf)")
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    if roll.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="Roll di luar entitas Anda")
    tag = await db.rfid_tags.find_one({"id": roll.get("rfid_tag_id"), "status": "active"}, {"_id": 0}) \
        if roll.get("rfid_tag_id") else None
    if not tag:
        raise HTTPException(status_code=400, detail=(
            "Roll belum punya tag RFID aktif — cetak ulang teks hanya untuk roll yang chip-nya masih baik. "
            "Gunakan Cetak tag / Ganti tag."))
    p = await db.products.find_one({"id": roll.get("product_id")}, {"_id": 0, "name": 1, "sku": 1}) or {}
    item = _new_item("text_reprint", roll, tag=tag, product_name=p.get("name", "") or tag.get("product_name", ""),
                     sku=tag.get("sku") or p.get("sku", ""))
    item["tag_id"] = None   # tidak menulis/mengaktifkan tag apa pun
    item["display_tag_id"] = tag["id"]
    job = await _new_job("text_reprint", [item], roll.get("warehouse_id"), roll.get("owner_entity_id"), actor,
                         source="text_reprint", extra={"reason_code": reason_code, "reason_note": note.strip()[:500]})
    await tag_event(roll_id, tag["id"], tag.get("epc"), "text_reprint_requested", by=actor, reason=reason_code,
                    note=note, job_id=job["id"], item_id=item["item_id"])
    return safe_doc(job)


async def replace_tag(roll_id: str, scope_ids: List[str], actor: str, reason_code: str,
                      note: str) -> Dict[str, Any]:
    """GANTI TAG: EPC baru (dibuat sistem) → print job baru; tag lama dipensiunkan (EPC tak pernah dipakai ulang).
    Pergerakan aktif tidak di-bypass; stok, pemilik & tahap journey tidak berubah (bukti verifikasi gugur)."""
    if reason_code not in REPLACE_REASONS:
        raise HTTPException(status_code=400, detail="Alasan ganti tag tidak dikenal")
    if len((note or "").strip()) < 5:
        raise HTTPException(status_code=400, detail="Catatan alasan wajib diisi (min. 5 huruf)")
    roll = await db.inventory_rolls.find_one({"id": roll_id}, {"_id": 0})
    if not roll:
        raise HTTPException(status_code=404, detail="Roll tidak ditemukan")
    if roll.get("owner_entity_id") not in scope_ids:
        raise HTTPException(status_code=403, detail="Roll di luar entitas Anda")
    await _assert_roll_not_moving(roll_id)
    old = await db.rfid_tags.find_one({"id": roll.get("rfid_tag_id"),
                                       "status": {"$in": list(rfid_service.LIVE_TAG_STATUSES)}}, {"_id": 0}) \
        if roll.get("rfid_tag_id") else None
    if old:
        busy = await _job_items_with_tag(old["id"], ["pending", "started", "unknown"])
        if busy:
            raise HTTPException(status_code=409, detail=(
                f"Tag roll ini masih dalam antrean/tinjauan cetak {busy.get('job_number') or busy['id']} — "
                "selesaikan lewat Antrean Printer (tindak lanjut) dulu."))
    if roll.get("status") not in rfid_service.PHYSICAL_STATUSES or (roll.get("length_remaining") or 0) <= 0:
        raise HTTPException(status_code=400, detail="Roll tidak dalam kondisi fisik untuk di-tag")
    full_note = f"{REPLACE_REASONS[reason_code]}: {note.strip()}"[:500]
    if old:
        retired = await _retire_live_tag(old["id"], f"replaced:{reason_code}", actor, note=full_note)
        if not retired:
            raise HTTPException(status_code=409, detail="Tag lama baru saja berubah — muat ulang.")
    try:
        job = await create_print_job([roll_id], scope_ids, actor, source="retag")
    except Exception:
        if old:  # kompensasi: tag lama dipulihkan bila tag baru gagal dibuat (roll tidak boleh kehilangan identitas)
            restored = await db.rfid_tags.update_one(
                {"id": old["id"], "status": "retired"}, {"$set": {"status": old["status"]},
                                                         "$unset": {"retired_at": "", "retire_reason": "", "retired_by": ""}})
            if restored.modified_count:
                await db.inventory_rolls.update_one({"id": roll_id, "rfid_tag_id": None}, {"$set": {
                    "rfid_tag_id": old["id"], "tracking_mode": "rfid", "updated_at": now_iso()}})
                await tag_event(roll_id, old["id"], old.get("epc"), "retire_reverted", by=actor,
                                note="Ganti tag gagal — tag lama dipulihkan")
        raise
    new_item = (job.get("items") or [{}])[0]
    if old:
        await db.rfid_tags.update_one({"id": old["id"]}, {"$set": {"replaced_by_tag_id": new_item.get("tag_id")}})
        await db.rfid_tags.update_one({"id": new_item.get("tag_id")}, {"$set": {"replaces_tag_id": old["id"]}})
    await db.rfid_print_jobs.update_one({"id": job["id"]}, {"$set": {
        "reason_code": reason_code, "reason_note": note.strip()[:500], "replaces_tag_id": (old or {}).get("id"),
        "replaces_epc": (old or {}).get("epc")}})
    await tag_event(roll_id, new_item.get("tag_id"), new_item.get("epc"), "replacement_issued", by=actor,
                    reason=reason_code, note=full_note, job_id=job["id"], item_id=new_item.get("item_id"),
                    extra={"old_tag_id": (old or {}).get("id"), "old_epc": (old or {}).get("epc")})
    return {"job": job, "old_tag": {k: (old or {}).get(k) for k in ("id", "epc", "status")} if old else None,
            "new_tag": {"id": new_item.get("tag_id"), "epc": new_item.get("epc"), "status": "pending_print"}}


# ─── PREP-F — antrean per gedung (UI) ─────────────────────────────────────────
async def queue_overview(scope_ids: List[str], warehouse_id: Optional[str], status: Optional[str],
                         limit: int = 300) -> Dict[str, Any]:
    await ensure_indexes()
    jobs = await list_print_jobs(scope_ids, warehouse_id, status, limit)
    totals: Dict[str, int] = {}
    for j in jobs:
        totals[j.get("status") or "-"] = totals.get(j.get("status") or "-", 0) + 1
    return {"count": len(jobs), "jobs": jobs, "status_counts": totals, "status_labels": JOB_STATUS_LABEL,
            "as_of": now_iso()}
