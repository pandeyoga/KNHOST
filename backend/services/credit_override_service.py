"""CR-T3 (CR-04, K-28) — izin kredit (`credit_overrides`, awalan `cro_`): selalu bernominal, berlingkup, bisa bermasa
berlaku, diputus menurut jenjang (Aturan Persetujuan KP-T4) dan kontrol dua orang (KF-T6).

Satu layanan untuk dua pintu pengajuan (`POST /api/customers/{id}/credit-override` dan pembungkus per pesanan
`POST /api/sales-orders/{id}/request-credit-approval`) dan dua pintu keputusan (`POST /api/credit-overrides/{id}/decision`
dan entri persetujuan `kredit` di pesanan). Field (spesifikasi "Data"):

  scope            pesanan · pelanggan       pesanan: hanya `order_id`-nya; pelanggan: pesanan mana pun di PT itu
  amount           > 0                       wajib (PK-45)
  remaining_amount mulai = amount            dikurangi tiap pemakaian (`credit_gate.use_override`, bersyarat)
  valid_until      ISO | ""                  diisi saat disetujui = waktu putus + `ar.izin_kredit_masa_berlaku_hari`
  reason_code/label                          dari master alasan (`amendment_reasons`, applies_to `credit_override`)
  used_by          [{order_id, amount, at}]  jejak pemakaian
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from core_utils import new_id, now_iso, rupiah, safe_doc
from db import db

COLL = "credit_overrides"
AKSI_KONTROL = "lewat_batas_kredit"   # KF-T6 — aksi kontrol dua orang izin kredit (label "Izin kredit", CR-T3)
LINGKUP = ("pesanan", "pelanggan")
LABEL_LINGKUP = {"pesanan": "Pesanan ini", "pelanggan": "Pelanggan ini"}
APPLIES_TO = "credit_override"
PESAN_NOMINAL = "Nominal izin wajib lebih dari 0."
PESAN_SUDAH = "Izin kredit ini sudah diputus atau kedaluwarsa."
PESAN_ALASAN = "Pilih alasan izin kredit."
PESAN_CATATAN = "Alasan “Lainnya” wajib dijelaskan di catatan (minimal 5 huruf)."
PESAN_ORDER = "Izin lingkup pesanan wajib menyebut pesanannya."


async def reasons() -> List[Dict[str, Any]]:
    """Alasan izin kredit aktif (master alasan, `applies_to` memuat `credit_override`)."""
    from services import amendment_service as amd
    rows = await amd.list_reasons(APPLIES_TO)
    return [{"code": r.get("code"), "label": r.get("label"), "help": r.get("help", "")} for r in rows]


async def _alasan(code: str) -> Dict[str, Any]:
    code = (code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail=PESAN_ALASAN)
    row = next((r for r in await reasons() if r["code"] == code), None)
    if not row:
        raise HTTPException(status_code=400, detail="Alasan izin kredit tidak dikenal atau nonaktif.")
    return row


async def create(customer: Dict[str, Any], entity_id: str, *, scope: str, amount: float, reason_code: str,
                 note: str, actor: Dict[str, Any], order: Optional[Dict[str, Any]] = None,
                 evidence_url: str = "", rejection_id: str = "") -> Dict[str, Any]:
    """Ajukan izin kredit berstatus `pending`. Pemberitahuan ke pemegang `credit_override.approve` PT itu."""
    if float(amount or 0) <= 0:
        raise HTTPException(status_code=400, detail=PESAN_NOMINAL)
    scope = (scope or "pelanggan").strip()
    if scope not in LINGKUP:
        raise HTTPException(status_code=400, detail="Lingkup izin harus “Pesanan ini” atau “Pelanggan ini”.")
    if scope == "pesanan" and not order:
        raise HTTPException(status_code=400, detail=PESAN_ORDER)
    alasan = await _alasan(reason_code)
    note = (note or "").strip()
    if alasan["code"] == "cr_lain" and len(note) < 5:
        raise HTTPException(status_code=400, detail=PESAN_CATATAN)
    from services import credit_gate as cg
    from services.customer_service import compute_customer_credit
    gate = await cg.evaluate(customer_id=customer["id"], entity_id=entity_id, checkpoint=cg.PERIKSA_ULANG,
                             order=order, order_amount=0 if order else float(amount or 0))
    amt = round(float(amount), 2)
    doc = {
        "id": new_id("cro"), "customer_id": customer["id"], "customer_name": customer.get("name", ""),
        "entity_id": entity_id, "scope": scope,
        "order_id": (order or {}).get("id", "") if scope == "pesanan" else "",
        "order_number": (order or {}).get("number", "") if scope == "pesanan" else "",
        "amount": amt, "remaining_amount": amt, "valid_until": "", "used_by": [],
        "reason_code": alasan["code"], "reason_label": alasan["label"], "reason": note or alasan["label"],
        "evidence_url": evidence_url or "", "rejection_id": rejection_id or "",
        # D3 — potret angka dasar saat diajukan (tidak dihitung ulang)
        "credit_snapshot": await compute_customer_credit(customer, entity_id), "gate_snapshot": cg.ringkas(gate),
        "status": "pending", "requested_by": actor.get("name", ""), "requested_by_id": actor.get("id", ""),
        "created_at": now_iso(),
    }
    await db[COLL].insert_one(dict(doc))
    from dependencies import audit
    await audit(actor.get("name", ""), "credit_override_requested", "credit_override", doc["id"],
                {k: doc[k] for k in ("customer_id", "entity_id", "scope", "order_id", "amount", "reason_code")})
    await _beri_tahu_pemutus(doc)
    return safe_doc(doc)


async def _beri_tahu_pemutus(doc: Dict[str, Any]) -> None:
    try:
        from services.notification_service import create_addressed
        lingkup = f"pesanan {doc['order_number']}" if doc.get("scope") == "pesanan" else "pelanggan"
        await create_addressed(
            permission=("credit_override", "approve"), entity_id=doc.get("entity_id") or None,
            notif_type="credit_override_requested", ref=f"credit_override:{doc['id']}", severity="warning",
            link="credit-overrides", title=f"Izin kredit {doc.get('customer_name', '')} menunggu keputusan",
            body=(f"{rupiah(doc.get('amount'))} · lingkup {lingkup} · {doc.get('reason_label', '')} — diajukan "
                  f"{doc.get('requested_by', '')}."))
    except Exception:  # noqa: BLE001 — pemberitahuan pelengkap; pengajuan tetap tersimpan
        pass


async def _beri_tahu_pengaju(doc: Dict[str, Any], status: str) -> None:
    try:
        from services.notification_service import create_notification
        if not doc.get("requested_by_id"):
            return
        kata = "disetujui" if status == "approved" else "ditolak"
        tambahan = (f" Berlaku sampai {doc['valid_until'][:10]}." if status == "approved" and doc.get("valid_until")
                    else "")
        await create_notification(
            notif_type="credit_override_decided", title=f"Izin kredit {doc.get('customer_name', '')} {kata}",
            body=f"{rupiah(doc.get('amount'))} — diputus {doc.get('decided_by', '')}.{tambahan}", severity="info",
            link="customers-crm", entity_id=doc.get("entity_id") or None, recipient_role="",
            recipient_user=doc["requested_by_id"], dedupe=False)
    except Exception:  # noqa: BLE001
        pass


async def masa_berlaku(entity_id: str, decided_at: str) -> str:
    """`valid_until` = waktu putus + `ar.izin_kredit_masa_berlaku_hari` (0 = tanpa batas → "")."""
    from services.nilai_pengaturan import nilai
    hari = int(await nilai("ar.izin_kredit_masa_berlaku_hari", entity_id or ""))   # galat baca = bawaan registry
    if hari <= 0:
        return ""
    try:
        dt = datetime.fromisoformat(str(decided_at).replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.now(timezone.utc)
    return (dt + timedelta(days=hari)).isoformat()


def kedaluwarsa(doc: Dict[str, Any]) -> bool:
    vu = str(doc.get("valid_until") or "")
    return bool(vu) and vu <= now_iso()


async def decide(override_id: str, decision: str, reason: str, actor: Dict[str, Any], *,
                 check_policy: bool = True, dual: bool = True) -> Dict[str, Any]:
    """Putus izin kredit `pending`: jenjang (Aturan Persetujuan jenis `credit_override`, nominal izin) → kontrol dua
    orang (`kontrol.lewat_batas_kredit.*`) → tulis bersyarat status `pending`. Setuju: `valid_until`, `remaining_amount`,
    penolakan terbuka pelanggan ditandai `dilanjutkan`, pesanan yang ditahan diperiksa ulang. Sudah diputus → 409."""
    if decision not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Keputusan harus setujui atau tolak.")
    co = await db[COLL].find_one({"id": override_id}, {"_id": 0})
    if not co:
        raise HTTPException(status_code=404, detail="Izin kredit tidak ditemukan.")
    if co.get("status") != "pending":
        raise HTTPException(status_code=409, detail=PESAN_SUDAH)
    amt = float(co.get("amount") or 0)
    if check_policy:
        from services import approval_policy_service as aps
        await aps.assert_can_decide("credit_override", co.get("entity_id") or None, amt, actor,
                                    action="approve" if decision == "approve" else "reject", check_permission=False)
    if dual:
        from services import dual_control as dc
        await dc.tolak_bila_pelaku_sama("lewat_batas_kredit", co, actor, co.get("entity_id", ""), nominal=amt,
                                        pengaju=[co.get("requested_by_id")])
    now = now_iso()
    new_status = "approved" if decision == "approve" else "rejected"
    sets: Dict[str, Any] = {"status": new_status, "decided_by": actor.get("name", ""), "decided_by_id": actor.get("id", ""),
                            "decision_reason": (reason or "").strip(), "decided_at": now}
    if new_status == "approved":
        sets.update(valid_until=await masa_berlaku(co.get("entity_id", ""), now),
                    remaining_amount=round(amt, 2), scope=co.get("scope") or "pelanggan")
    updated = await db[COLL].find_one_and_update({"id": override_id, "status": "pending"}, {"$set": sets},
                                                 projection={"_id": 0}, return_document=True)
    if not updated:
        raise HTTPException(status_code=409, detail=PESAN_SUDAH)
    from dependencies import audit
    await audit(actor.get("name", ""), f"credit_override_{new_status}", "credit_override", override_id,
                {"reason": (reason or "").strip(), "amount": amt, "valid_until": sets.get("valid_until", "")})
    await _beri_tahu_pengaju(updated, new_status)
    if new_status == "approved":
        from services import credit_gate as cg
        await cg.tandai_penolakan_dilanjutkan(updated["customer_id"], updated.get("entity_id", ""), override_id)
        await cg.recheck_holds_safe(updated["customer_id"], updated.get("entity_id", ""), actor,
                                    "Izin kredit disetujui")
        updated = await db[COLL].find_one({"id": override_id}, {"_id": 0}) or updated
    return safe_doc(updated)


def tampil(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Baris layar: lingkup berlabel, sisa, berlaku sampai, status berlaku (izin lama ternormalisasi saat dibaca)."""
    from services import credit_gate as cg
    d = safe_doc(dict(doc))
    d["scope"] = cg.lingkup(d)
    d["scope_label"] = LABEL_LINGKUP[d["scope"]]
    d["remaining_amount"] = cg.sisa_izin(d)
    d["expired"] = d.get("status") == "approved" and kedaluwarsa(d)
    d["usable"] = d.get("status") == "approved" and not d["expired"] and d["remaining_amount"] > 0
    d["reason_label"] = d.get("reason_label") or ""
    d["used_by"] = list(d.get("used_by") or [])
    return d
