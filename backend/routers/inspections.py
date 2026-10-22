"""FASE I — **INSPEKSI & QC SEBAGAI DOKUMEN** (`/api/inspections`).

Pembagian izin (modul `inspection`, `permissions_config.DEFAULT_PERMISSIONS`):
  * `view`    — admin · manajer · gudang · Admin Sales (Admin Sales: memantau retur)
  * `create`  — admin · manajer (jalur normalnya OTOMATIS dari penerimaan PO)
  * `assign`  — admin · manajer
  * `inspect` — admin · manajer · **gudang** (petugas Bagian Inspect)
  * `decide`  — admin · manajer (tutup dengan keputusan; `tolak` wajib ber-alasan)
  * `reopen`  — admin · manajer (alasan wajib)

Pagar yang ditegakkan DI SINI (bukan di layar):
  * badan usaha — `resolve_list_scope` pada daftar, `assert_entity_access` pada detail
    (rute akar `POST /api/inspections` otomatis 409 di mode "Semua Entitas");
  * lini produk — `line_scope.narrow` + `assert_can_touch`, supaya petugas printing
    tidak memeriksa (atau memutuskan) pekerjaan woven;
  * **tahanan warna** — pelepasnya hanya manajer/admin, diperiksa di layanan supaya
    tidak ada jalur kedua yang lebih longgar.
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import pagination as pg
from db import db
from dependencies import audit, has_permission, require_any_permission, require_permission
from entity_scope import assert_active_entity_access, entity_ctx, resolve_list_scope
from schemas_inspection import (InspectionAssign, InspectionCreate, InspectionFinish,
                                InspectionLineInspect, InspectionReason, QcFourPointCreate, RandomCheckCreate)
from services import inspection_service as svc
from services import line_scope

router = APIRouter(prefix="/api")


def _fail(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


async def _guarded(ins_id: str, request: Request, actor: Dict[str, Any]) -> Dict[str, Any]:
    ctx = await entity_ctx(request)
    doc = await svc.get_one(ins_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokumen inspeksi tidak ditemukan.")
    # T3 audit training 2026-06 — detail/PDF seketat daftar: badan usaha AKTIF.
    assert_active_entity_access(doc, svc.COLL, ctx)
    line_scope.assert_can_touch(actor, doc)
    return doc


@router.get("/inspections/meta")
async def meta(request: Request, entity_id: str = Query("")) -> Dict[str, Any]:
    """Kosakata + kebijakan selisih warna/handfeel yang BERLAKU + daftar petugas."""
    actor = await require_permission(request, "inspection", "view")
    ctx = await entity_ctx(request)
    out = await svc.meta(entity_id or ctx.active_entity_id)
    # FE-04 — petugas = akun aktif berkemampuan inspect (termasuk peran kustom) di badan usaha ini.
    officers = await svc.eligible_officers(entity_id or ctx.active_entity_id or "")
    # Cek UI UAT v3 (S8) — dulu id peran mentah ("warehouse_admin", "md_quality") di pilihan petugas.
    from role_registry import role_label
    from config_divisions import division_name
    out["officers"] = [{"value": u["id"],
                        "label": f"{u.get('name', '')} · "
                                 f"{(division_name(u['division']) if u.get('division') else '') or role_label(u.get('role', ''))}"}
                       for u in officers]
    out["role"] = (actor or {}).get("role", "")
    out["can_release_hold"] = (actor or {}).get("role") in svc.HOLD_RELEASE_ROLES
    out["can_md_quality"] = await has_permission(actor, "md_quality", "inspect")
    out["can_md_quality_decide"] = await has_permission(actor, "md_quality", "decide")
    out["can_qc"] = await has_permission(actor, "qc", "inspect")
    out["can_random_check"] = await has_permission(actor, "qc", "random_check")
    out["can_qc_release"] = await has_permission(actor, "qc", "release")
    out["can_inspect_all"] = await has_permission(actor, "inspection", "inspect")
    return out


_PART_PERM = {"md_quality": ("md_quality", "inspect"), "qc": ("qc", "inspect"),
              "": ("inspection", "inspect")}


@router.post("/inspections/qc-4point")
async def create_qc_4point(payload: QcFourPointCreate, request: Request) -> Dict[str, Any]:
    """Trial 22 Okt (E9) — SPK QC 4-point tersendiri (kapan saja): dari SPK MD Quality / tugas penerimaan / roll."""
    actor = await require_permission(request, "qc", "inspect")
    ctx = await entity_ctx(request)
    try:
        doc = await svc.create_qc_4point(payload.model_dump(), actor, ctx.active_entity_id)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_qc4_created", "inspection", doc["id"],
                {"number": doc["number"], "rolls": len(doc.get("lines") or [])})
    return doc


@router.post("/inspections/random-check")
async def create_random_check(payload: RandomCheckCreate, request: Request) -> Dict[str, Any]:
    """P05 IMP-16 — random check QC: N roll Tersedia diambil acak & DITAHAN selama dicek."""
    actor = await require_permission(request, "qc", "random_check")
    ctx = await entity_ctx(request)
    try:
        doc = await svc.create_random_check(payload.model_dump(), actor, ctx.active_entity_id)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_random_check_created", "inspection", doc["id"],
                {"number": doc["number"], "rolls": len(doc.get("lines") or [])})
    return doc


@router.get("/inspections")
async def list_inspections(request: Request, entity_id: Optional[str] = Query(None),
                           kind: str = Query(""), status: str = Query(""),
                           assigned_to: str = Query(""), line: str = Query(""),
                           hold_only: bool = Query(False),
                           q: str = Query(""),
                           limit: int = Query(200, ge=1, le=500)) -> Dict[str, Any]:
    """Daftar inspeksi (berhalaman opsional, `?page=&page_size=` — kontrak P2)."""
    actor = await require_permission(request, "inspection", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope(svc.COLL, {}, ctx, entity_id)
    scope = line_scope.narrow(scope, actor, line)      # FASE L
    if pg.is_paged(request):
        page, page_size, q_param, _sort = pg.get_page_params(request)
        rows, total = await svc.list_inspections(
            scope, kind=kind, status=status, assigned_to=assigned_to,
            hold_only=hold_only, q=q or q_param,
            skip=(page - 1) * page_size, limit=page_size)
        return {"items": rows, "total": total, "page": page, "page_size": page_size,
                "has_more": (page * page_size) < total,
                "stats": await svc.stats(scope)}
    rows, total = await svc.list_inspections(
        scope, kind=kind, status=status, assigned_to=assigned_to,
        hold_only=hold_only, q=q, limit=limit)
    return {"items": rows, "count": len(rows), "total": total,
            "stats": await svc.stats(scope)}


@router.get("/inspections/export")
async def export_inspections(request: Request, entity_id: Optional[str] = Query(None),
                             kind: str = Query(""), status: str = Query(""),
                             line: str = Query("")) -> StreamingResponse:
    """Unduh CSV daftar inspeksi (`;` + BOM + desimal koma — gaya Indonesia)."""
    actor = await require_permission(request, "inspection", "view")
    ctx = await entity_ctx(request)
    scope = resolve_list_scope(svc.COLL, {}, ctx, entity_id)
    scope = line_scope.narrow(scope, actor, line)
    rows, _total = await svc.list_inspections(scope, kind=kind, status=status, limit=2000)

    def _num(v: Any) -> str:
        if v in (None, ""):
            return ""
        return f"{float(v):.2f}".replace(".", ",")

    def _rolls(v: Any) -> str:
        """Sel kolom Roll di CSV: KOSONG bila belum pernah diisi (bukan "0").

        Keputusan pemilik 2026-08-20 (FASE U): di CSV selnya dikosongkan — bukan "—" —
        supaya SUM di lembar kerja tetap bekerja. Yang dilarang keras adalah menulis
        "0", karena 0 roll adalah PERNYATAAN "tidak ada gulungan".
        """
        return "" if v in (None, "") else str(int(float(v)))

    head = ["Nomor", "Jenis", "Dokumen sumber", "Supplier/Pelanggan", "Petugas",
            "Tanggal SPK", "Status", "Baris", "Roll", "Ukuran", "Satuan",
            "Poin cacat", "Ditahan", "Keputusan"]
    lines_out = [";".join(head)]
    for r in rows:
        s = r.get("summary") or {}
        lines_out.append(";".join([
            r.get("number", ""), svc.KIND_LABEL.get(r.get("kind", ""), r.get("kind", "")),
            r.get("ref_doc_number", ""),
            r.get("supplier_name", "") or r.get("customer_name", ""),
            r.get("assigned_name", ""), r.get("spk_date", ""),
            svc.STATUS_LABEL.get(r.get("status", ""), r.get("status", "")),
            str(s.get("lines") or 0), _rolls(s.get("rolls")),
            _num(s.get("measure")), s.get("unit", ""),
            _num(s.get("points_total")), str(s.get("hold") or 0),
            r.get("decision_label", ""),
        ]))
    body = "\ufeff" + "\r\n".join(lines_out)
    return StreamingResponse(
        iter([body]), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="inspeksi.csv"'})


@router.get("/inspections/{ins_id}")
async def get_inspection(ins_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inspection", "view")
    return await _guarded(ins_id, request, actor)


@router.post("/inspections")
async def create_inspection(payload: InspectionCreate, request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inspection", "create")
    ctx = await entity_ctx(request)
    try:
        doc = await svc.create(payload.model_dump(), actor, ctx.active_entity_id)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_created", "inspection", doc["id"],
                {"number": doc["number"], "kind": doc["kind"],
                 "ref": doc.get("ref_doc_number", "")})
    return doc


@router.post("/inspections/{ins_id}/assign")
async def assign_inspection(ins_id: str, payload: InspectionAssign,
                            request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inspection", "assign")
    doc = await _guarded(ins_id, request, actor)
    try:
        out = await svc.assign(doc["id"], payload.model_dump(), actor)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_assigned", "inspection", doc["id"],
                {"number": doc["number"], "assigned_to": out.get("assigned_name", "")})
    return out


@router.post("/inspections/{ins_id}/start")
async def start_inspection(ins_id: str, request: Request) -> Dict[str, Any]:
    actor = await require_any_permission(request, [("inspection", "inspect"), ("qc", "inspect")])
    doc = await _guarded(ins_id, request, actor)
    try:
        return await svc.start(doc["id"], actor)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc


@router.post("/inspections/{ins_id}/lines/{line_id}/inspect")
async def inspect_line(ins_id: str, line_id: str, payload: InspectionLineInspect,
                       request: Request) -> Dict[str, Any]:
    part = (payload.part or "").strip().lower()
    if part not in _PART_PERM:
        raise HTTPException(status_code=400, detail="Bagian pemeriksaan harus md_quality atau qc.")
    actor = await require_permission(request, *_PART_PERM[part])
    doc = await _guarded(ins_id, request, actor)
    body = payload.model_dump()
    body["defects"] = [d for d in (body.get("defects") or [])]
    try:
        out = await svc.inspect_line(doc["id"], line_id, body, actor)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_line_inspected", "inspection", doc["id"],
                {"number": doc["number"], "line_id": line_id,
                 "color": body.get("color_result", ""),
                 "handfeel": body.get("handfeel_result", "")})
    return out


@router.post("/inspections/{ins_id}/lines/{line_id}/release-hold")
async def release_hold(ins_id: str, line_id: str, payload: InspectionReason,
                       request: Request) -> Dict[str, Any]:
    """Lepas tahanan barang (warna/handfeel menyimpang) — **manajer/admin**, alasan wajib."""
    actor = await require_any_permission(request, [("inspection", "decide"), ("md_quality", "decide")])
    doc = await _guarded(ins_id, request, actor)
    try:
        out = await svc.release_hold(doc["id"], line_id, payload.reason, actor,
                                     can_md_quality=await has_permission(actor, "md_quality", "decide"))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_hold_released", "inspection", doc["id"],
                {"number": doc["number"], "line_id": line_id, "reason": payload.reason})
    return out


@router.post("/inspections/{ins_id}/lines/{line_id}/reject-hold")
async def reject_hold(ins_id: str, line_id: str, payload: InspectionReason,
                      request: Request) -> Dict[str, Any]:
    """P05 IMP-16 — MD Quality menolak barang yang ditahan (roll tetap ditahan), alasan wajib."""
    actor = await require_any_permission(request, [("inspection", "decide"), ("md_quality", "decide")])
    doc = await _guarded(ins_id, request, actor)
    try:
        out = await svc.reject_hold(doc["id"], line_id, payload.reason, actor,
                                    can_md_quality=await has_permission(actor, "md_quality", "decide"))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_hold_rejected", "inspection", doc["id"],
                {"number": doc["number"], "line_id": line_id, "reason": payload.reason})
    return out


@router.post("/inspections/{ins_id}/finish")
async def finish_inspection(ins_id: str, payload: InspectionFinish,
                            request: Request) -> Dict[str, Any]:
    """Tutup inspeksi dengan KEPUTUSAN (antrean `inspection_hold` untuk yang ditahan)."""
    user_doc = await svc.get_one(ins_id)
    # F-14 (keputusan owner Q-03a) — SPK penerimaan PO kini SEKALIGUS memutus karantina, jadi pemutus karantina
    # (`qc.release`, bawaan QC/MD/Admin Gudang) boleh menutupnya — sama seperti random check.
    if user_doc and user_doc.get("kind") in (svc.KIND_RANDOM_CHECK, svc.KIND_PO_RECEIPT, svc.KIND_QC_4POINT):   # + SPK QC 4-point (Trial 22 Okt E9)
        actor = await require_any_permission(request, [("inspection", "decide"), ("qc", "release")])
    else:
        actor = await require_permission(request, "inspection", "decide")
    doc = await _guarded(ins_id, request, actor)
    try:
        out = await svc.finish(doc["id"], payload.decision, payload.remark, actor,
                               reject_disposition=payload.reject_disposition,
                               rejected_roll_ids=payload.rejected_roll_ids)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_finished", "inspection", doc["id"],
                {"number": doc["number"], "decision": payload.decision,
                 "remark": payload.remark})
    return out


@router.post("/inspections/{ins_id}/reopen")
async def reopen_inspection(ins_id: str, payload: InspectionReason,
                            request: Request) -> Dict[str, Any]:
    actor = await require_permission(request, "inspection", "reopen")
    doc = await _guarded(ins_id, request, actor)
    try:
        out = await svc.reopen(doc["id"], payload.reason, actor)
    except svc.InspectionError as exc:
        raise _fail(exc) from exc
    await audit(actor["name"], "inspection_reopened", "inspection", doc["id"],
                {"number": doc["number"], "reason": payload.reason})
    return out


@router.get("/inspections/meta/ref-docs")
async def ref_doc_options(request: Request, kind: str = Query(""),
                         entity_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Pilihan DOKUMEN SUMBER untuk pop-up "Buat SPK" — dilayani modul INI sendiri.

    Kenapa endpoint sendiri, bukan layar yang memanggil `/api/sales-returns` &
    `/api/makloon-orders` langsung (versi pertama layar ini melakukannya):
    `inspection.view` dimiliki **gudang**, sedangkan `sales_return.view` TIDAK.
    Akibatnya pemilih dokumen di layar inspeksi dijawab **403** untuk petugas gudang
    — panel mati, dan `audit_sales_roles_ux` memang memerah karenanya (terukur
    2026-08-23). Menambal dengan "sembunyikan pemilihnya untuk gudang" tidak cukup:
    penilaian layar memakai penutupan IMPOR, dan yang salah memang arsitekturnya —
    pelajaran FASE D ("endpoint baru jangan menumpang modul API bersama").

    Daftarnya sengaja RINGKAS (nomor + nama pihak): layar hanya butuh memilih, dan
    mengirim seluruh dokumen berarti membocorkan nilai transaksi ke peran yang tidak
    berhak melihatnya.
    """
    actor = await require_permission(request, "inspection", "view")
    ctx = await entity_ctx(request)
    want = (kind or "").strip().lower()
    out: List[Dict[str, str]] = []

    def _scoped(coll: str) -> Dict[str, Any]:
        return resolve_list_scope(coll, {}, ctx, entity_id)

    if want in (svc.KIND_RETURN_CUSTOMER, svc.KIND_REPLACEMENT):
        rows = await db.sales_returns.find(
            _scoped("sales_returns"),
            {"_id": 0, "id": 1, "number": 1, "customer_name": 1, "complaint_label": 1}
        ).sort("created_at", -1).to_list(150)
        out = [{"value": r["id"],
                "label": " · ".join(x for x in (r.get("number"), r.get("customer_name"),
                                                r.get("complaint_label")) if x)}
               for r in rows]
    elif want == svc.KIND_SALES_ORDER:
        # L05 LN-050-T01 — HANYA SO yang meminta QC di checkout & belum lulus QC.
        from services.loading_check_service import qc_uncovered
        q = {**_scoped("sales_orders"), "qc_request.mode": {"$in": ["full", "sampling"]},
             "status": {"$nin": ["cancelled", "shipped", "delivered", "completed", "done"]}}
        rows = await db.sales_orders.find(q, {"_id": 0, "id": 1, "number": 1, "customer_name": 1, "qc_request": 1}
                                          ).sort("created_at", -1).to_list(150)
        # Lulus → tidak ditawarkan, KECUALI mode seluruh dan alokasi berubah sesudah QC (roll baru belum di-QC).
        rows = [r for r in rows if r["qc_request"].get("status") != "passed"
                or (r["qc_request"]["mode"] == "full" and await qc_uncovered(r["id"]))]
        out = [{"value": r["id"], "label": " · ".join(x for x in (
            r.get("number"), r.get("customer_name"),
            "QC seluruh roll" if r["qc_request"]["mode"] == "full" else f"QC sampling {r['qc_request'].get('sample_pct', 10):g}%") if x)}
            for r in rows]
        for o in out:   # tanda SPK yang masih berjalan → layar memperingatkan, tidak membuat dobel
            open_spk = await db.inspections.find_one(
                {"kind": "sales_order", "ref_doc_id": o["value"], "status": {"$nin": ["done", "closed", "cancelled"]}},
                {"_id": 0, "number": 1, "status": 1}, sort=[("created_at", -1)])
            if open_spk:
                o.update({"spk_number": open_spk.get("number", ""), "spk_status": open_spk.get("status", "")})
    elif want == svc.KIND_RETURN_SUPPLIER:
        rows = await db.purchase_returns.find(
            _scoped("purchase_returns"),
            {"_id": 0, "id": 1, "number": 1, "supplier_name": 1}
        ).sort("created_at", -1).to_list(150)
        out = [{"value": r["id"],
                "label": " · ".join(x for x in (r.get("number"), r.get("supplier_name")) if x)}
               for r in rows]
    elif want == svc.KIND_MAKLOON_OUTPUT:
        # Proyeksi menyertakan `steps.*` karena nomor & mitra order makloon TIDAK ada di
        # akar dokumen (terukur: `mko_number`, dan `makloon_name` per tahap). Hanya
        # empat sub-field yang diambil — tarif, nilai, dan biaya jasa tidak dikirim ke
        # layar inspeksi.
        rows = await db.makloon_orders.find(
            _scoped("makloon_orders"),
            {"_id": 0, "id": 1, "mko_number": 1, "number": 1,
             "steps.seq": 1, "steps.makloon_id": 1, "steps.makloon_name": 1,
             "steps.output_lot_ids": 1, "steps.output_lot_id": 1}
        ).sort("created_at", -1).to_list(150)
        for r in rows:
            # Order makloon yang BELUM menyerahkan hasil tidak ditawarkan: SPK-nya akan
            # lahir NOL BARIS (terukur: MKO-00002 `in_process`, nol lot hasil), dan
            # dokumen tanpa barang tidak bisa diperiksa siapa pun. `create()` menolaknya
            # juga — pemilih hanya berhenti menawarkan jalan buntu.
            if not svc.makloon_output_lot_ids(r):
                continue
            out.append({"value": r["id"],
                        "label": " · ".join(x for x in (svc.makloon_ref_number(r),
                                                        svc.makloon_vendor(r)[1]) if x)})

    # ── Tandai dokumen yang SUDAH punya SPK jenis ini ────────────────────────────
    # Pemilih yang diam soal ini membuat kepala gudang menerbitkan SPK kedua atas barang
    # yang sama, lalu garis waktu retur menyebut nomor SPK yang berbeda dari yang ia
    # buka. `create()` menolak bila SPK lama masih BERJALAN; label di sini membuat
    # penolakan itu bisa diduga SEBELUM tombol ditekan (dan yang sudah diputuskan tetap
    # boleh dipilih — pemeriksaan ulang sesudah keputusan adalah kejadian nyata).
    if out:
        ada = await db[svc.COLL].find(
            {"kind": want, "ref_doc_id": {"$in": [o["value"] for o in out]}},
            {"_id": 0, "ref_doc_id": 1, "number": 1, "status": 1}).to_list(400)
        peta = {d.get("ref_doc_id"): d for d in ada}
        for o in out:
            d = peta.get(o["value"])
            if not d:
                continue
            berjalan = str(d.get("status")) in svc.OPEN_STATUSES
            o["spk_number"] = d.get("number", "")
            o["spk_status"] = d.get("status", "")
            o["label"] += (f" · sudah ada SPK {d.get('number')} "
                           + ("(masih berjalan)" if berjalan else "(sudah diputuskan)"))

    # Gudang boleh MEMBACA daftarnya (agar pemilih tidak mati), tetapi membuat SPK
    # tetap butuh `inspection.create` — pagarnya di `POST /api/inspections`, bukan di
    # sini. Menyembunyikan daftar tidak menambah keamanan, hanya menambah kebingungan.
    return {"items": out, "kind": want,
            "can_create": bool((actor or {}).get("role") in ("admin", "manager"))}


@router.get("/inspections/{ins_id}/pdf")
async def inspection_pdf(ins_id: str, request: Request,
                         download: bool = Query(True)):
    """Cetak SPK Inspeksi lewat PLATFORM DOKUMEN (G-4), bukan mesin PDF sendiri.

    Sengaja menumpang platform: kop surat per badan usaha, blok "Referensi Dokumen",
    QR Jejak Dokumen, dan tanda tangan elektronik sudah hidup di sana. Membuat mesin
    kedua berarti dokumen inspeksi akan berbeda rupa dari 22 dokumen lain — dan
    perbaikan kop surat harus dikejar di dua tempat.
    """
    actor = await require_permission(request, "inspection", "view")
    doc = await _guarded(ins_id, request, actor)
    from fastapi.responses import Response

    from services import pdf_service
    try:
        content, media, built = await pdf_service.render_document(
            "inspection_spk", doc["id"], doc.get("entity_id", ""), fmt="pdf")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500,
                            detail=f"Gagal mencetak SPK inspeksi: {exc}") from exc
    num = str(built["doc"].get("number") or doc["id"]).replace("/", "-")
    disp = "attachment" if download else "inline"
    return Response(content=content, media_type=media,
                    headers={"Content-Disposition": f'{disp}; filename="SPK-Inspeksi-{num}.pdf"'})


@router.get("/inspections/queue/qc-tasks")
async def qc_tasks_without_doc(request: Request) -> List[Dict[str, Any]]:
    """Tugas QC yang BELUM punya SPK inspeksi — jaring pengaman, bukan pintu kedua.

    Dokumen `po_receipt` lahir otomatis saat barang masuk antrean QC. Daftar ini ada
    supaya kalau otomatisasi itu pernah gagal (mis. penerimaan lama sebelum FASE I),
    kepala gudang MELIHATNYA dan bisa menerbitkan SPK-nya — bukan menemukannya
    setahun kemudian saat barang sudah terjual.
    """
    await require_permission(request, "inspection", "view")
    ctx = await entity_ctx(request)
    tasks = await db.wms_tasks.find(
        resolve_list_scope("wms_tasks",
                           {"flow_type": "inbound", "status": "qc_pending"}, ctx),
        {"_id": 0, "id": 1, "po_id": 1, "po_number": 1, "product_name": 1,
         "quantity": 1, "unit": 1, "updated_at": 1}).to_list(200)
    have = {d.get("task_id") for d in await db[svc.COLL].find(
        {"task_id": {"$ne": ""}}, {"_id": 0, "task_id": 1}).to_list(2000)}
    return [t for t in tasks if t["id"] not in have]


class MdqCutIn(BaseModel):
    cut_yard: float = 0.25
    weight_kg: Optional[float] = None
    reason: str = ""


@router.post("/inspections/{ins_id}/lines/{line_id}/mdq-cut")
async def mdq_cut_ep(ins_id: str, line_id: str, payload: MdqCutIn, request: Request) -> Dict[str, Any]:
    """L04 LN-042 — potong uji MD Quality (default 0,25 yard) sebagai mutasi pemakaian, idempoten per baris."""
    from services import mdq_cut_service as mcs
    actor = await require_permission(request, "md_quality", "inspect")
    doc = await db.inspections.find_one({"id": ins_id}, {"_id": 0, "id": 1, "entity_id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Inspeksi tidak ditemukan.")
    ctx = await entity_ctx(request)
    assert_active_entity_access(doc, "inspections", ctx)
    out = await mcs.cut(ins_id, line_id, cut_yard=payload.cut_yard, weight_kg=payload.weight_kg,
                        reason=payload.reason, actor=actor)
    if not out.get("replayed"):
        await audit(actor.get("name", ""), "mdq_cut", "inspections", ins_id,
                    {"line_id": line_id, "qty": out.get("qty"), "unit": out.get("unit"), "basis": out.get("basis")})
    return out
