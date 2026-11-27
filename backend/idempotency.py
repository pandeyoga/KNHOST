"""Idempotency-Key — aksi gudang dari HP (juga saat sinkron ulang dari antrean offline).

Kunci sama → balasan PERTAMA dikembalikan apa adanya (kode + body), efek samping tidak diulang.
Hanya aktif bila klien mengirim header `Idempotency-Key` pada POST. Kunci diikat ke metode+path+
user_id sesi sah+entitas; payload berbeda dengan kunci sama → 409 (GN-01). Rekaman kedaluwarsa 7 hari.
"""
import hashlib
import re
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from db import db
from core_utils import now_iso

HEADER = "idempotency-key"
# PK-12 — jawaban 4xx yang menandai keadaan SEMENTARA ("dokumen tercatat, jurnal gagal — kirim ulang"; "berubah saat
# diproses") membawa header ini dan TIDAK disimpan, supaya kirim ulang dengan kunci sama benar-benar dijalankan lagi.
RETRY_HEADER = "x-idempotency-retry"
TTL_DAYS = 7
IDEMPOTENT_PREFIXES = ("/api/inbound/", "/api/outbound/", "/api/wms/tasks/",
                       "/api/rfid/lookup", "/api/rfid/roll-scans", "/api/rfid/print-jobs",
                       "/api/hr/visits", "/api/sales-orders", "/api/price-approvals",
                       "/api/ar-receipts", "/api/sales-returns", "/api/special-orders",
                       "/api/marketing/campaigns/", "/api/goods-receipts/",
                       # PK-05 (SL-02) — bayar hutang: kirim ulang tidak boleh menggandakan kas keluar.
                       "/api/vendor-bills/", "/api/contra-bons/", "/api/ap-payments/",
                       # PK-06 — antar-PT: konfirmasi/pelunasan yang dikirim ulang tidak boleh ganda.
                       "/api/interco/",
                       # PK-12 (UX-01, UX-02, GL-08, FY-18) — semua form uang: klik ganda / kirim ulang = satu dokumen.
                       "/api/gl/", "/api/cash-transactions", "/api/vendor-bills", "/api/contra-bons",
                       "/api/fixed-assets", "/api/cash-advances", "/api/cash-advance-settlements",
                       "/api/payment-plans", "/api/penalties", "/api/payment-variances", "/api/finance-cases",
                       "/api/tax/pph-records", "/api/input-tax-invoices", "/api/tax-invoices",
                       "/api/bank-reconciliation/lines/",
                       # PM-T1 — rekening kas/bank dan putusan perubahannya: kirim ulang = satu rekening / satu putusan.
                       "/api/bank-accounts", "/api/bank-account-changes",
                       # CR-T1 — putusan/pembatalan pengajuan perubahan kredit.
                       "/api/credit-profile-requests",
                       # PK-28 — kliring GR/IR menerbitkan jurnal: kirim ulang = satu kliring.
                       "/api/finance/gr-ir",
                       # PK-22 — posting/anulir/bayar gaji dan setoran kewajiban: kirim ulang = satu jurnal/kas.
                       "/api/hr/payroll/",
                       # AG-T3 — pintu yang dipanggil kartu tindakan asisten (kunci = id kartu): kirim ulang = satu
                       # tulisan. Hanya berlaku bila klien mengirim kunci; layar yang ada tidak mengirimnya. Tindak
                       # lanjut penagihan (`/api/customers/{id}/followups`) lewat pola di bawah, bukan awalan
                       # `/api/customers/` yang luas (CR-T1 menjaga `/api/customers/{id}` tetap di luar).
                       "/api/bank-reconciliation/", "/api/finance/posting-failures/",
                       "/api/collection-reminders", "/api/purchase-orders",
                       # PY-T2 — sahkan/tolak riwayat kompensasi & penugasan PT (sahkan bisa menerbitkan masukan rapel).
                       "/api/hr/compensation/", "/api/hr/assignments/",
                       # PM-T4 — setoran titipan tunai sales: ajukan/terima/tolak/batal dikirim ulang = satu tulisan.
                       "/api/cash-deposits",
                       # CR-T3 — putusan izin kredit dikirim ulang = satu putusan.
                       "/api/credit-overrides",
                       # KM-T3 (N4) — Meja Insentif: buat lembar, ubah baris, ajukan, sahkan dikirim ulang = satu tulisan.
                       "/api/incentive/",
                       # LB-T3 — lapor bayar CBD & DP: unggah bukti / keputusan terima-tolak dikirim ulang = satu tulisan.
                       "/api/payment-reports",
                       # Kas & Bank 1 (Tugas 4) — Pindah Dana: buat/terima/setujui/batal dikirim ulang = satu dokumen,
                       # kas tidak ganda (layanan juga mengklaim per status).
                       "/api/fund-transfers",
                       # Kas & Bank 2 (C6) — putusan pengajuan kas keluar manual (setujui/tolak/batal) dikirim ulang =
                       # satu putusan, kas tidak ganda (layanan juga mengklaim per status). Pengajuannya sendiri lahir
                       # di `/api/cash-transactions` (202 tidak disimpan: kunci yang sama dijawab layanan, lihat
                       # `cash_out_request_service.jawab_diajukan`).
                       "/api/cash-out-requests")
#: CR-T1 — jalur ber-id di tengah yang tidak bisa dinyatakan sebagai awalan (`/api/customers/{id}/credit-profile-requests`:
#: mengajukan perubahan kredit). Dicocokkan penuh terhadap jalur permintaan.
IDEMPOTENT_PATTERNS = (re.compile(r"^/api/customers/[^/]+/credit-profile-requests/?$"),
                       # AG-T3 — tindak lanjut penagihan / janji bayar dari kartu tindakan asisten
                       re.compile(r"^/api/customers/[^/]+/followups/?$"),
                       # PY-T2 — usulan riwayat kompensasi / penugasan PT karyawan: kirim ulang = satu baris usulan
                       re.compile(r"^/api/hr/employees/[^/]+/(compensation|assignments)/?$"),
                       # CR-T3 — pengajuan izin kredit: klik ganda = satu izin
                       re.compile(r"^/api/customers/[^/]+/credit-override/?$"))


def is_idempotent_path(path: str) -> bool:
    return path.startswith(IDEMPOTENT_PREFIXES) or any(p.match(path) for p in IDEMPOTENT_PATTERNS)


async def _session_user_id(request: Request) -> str:
    """GN-01 — identitas stabil dari sesi SAH (cookie `session_token` / Bearer), bukan potongan token."""
    from dependencies import extract_token, _as_utc
    token = extract_token(request)
    if not token:
        return ""
    sess = await db.sessions.find_one({"token": token}, {"_id": 0, "user_id": 1, "expires_at": 1})
    if not sess:
        return ""
    exp = _as_utc(sess.get("expires_at"))
    if exp is not None and exp <= datetime.now(timezone.utc):
        return ""
    return sess.get("user_id") or ""


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        key = request.headers.get(HEADER, "").strip()
        if not key or request.method not in ("POST", "PUT", "PATCH", "DELETE") \
                or not is_idempotent_path(request.url.path):
            return await call_next(request)
        user_id = await _session_user_id(request)
        if not user_id:
            # GN-01 — tanpa sesi sah tidak ada lookup/replay; endpoint yang menolak (401)
            return await call_next(request)
        entity = (request.headers.get("X-Entity-Id") or "").strip()
        body_bytes = await request.body()
        ctype = request.headers.get("content-type", "")
        if ctype.lower().startswith("multipart/form-data") and "boundary=" in ctype:
            # LB-T3 — klien (axios/httpx) membuat batas multipart BARU tiap kirim, jadi kirim ulang unggahan yang sama
            # berisi beda byte. Batas dibuang dari sidik supaya kirim ulang = isi sama = jawaban diputar, bukan 409.
            batas = ctype.split("boundary=", 1)[1].split(";", 1)[0].strip().strip('"')
            if batas:
                body_bytes = body_bytes.replace(batas.encode(), b"")
        payload_hash = hashlib.sha256(
            request.url.query.encode() + b"\n" + body_bytes).hexdigest()
        doc_id = f"{key}|{request.method}|{request.url.path}|{user_id}|{entity}"
        now = datetime.now(timezone.utc)
        try:
            await db.idempotency_keys.insert_one({
                "_id": doc_id, "key": key, "path": request.url.path, "status": "in_progress",
                "user_id": user_id, "entity": entity, "payload_hash": payload_hash,
                "created_at": now_iso(), "expires_at": now + timedelta(days=TTL_DAYS)})
        except Exception:
            existing = await db.idempotency_keys.find_one({"_id": doc_id})
            if existing and existing.get("payload_hash") not in (None, payload_hash):
                return JSONResponse(status_code=409, content={"detail": {
                    "code": "IDEMPOTENCY_KEY_REUSED",
                    "message": "Kunci idempotensi sudah dipakai untuk isi permintaan yang berbeda."}})
            if existing and existing.get("status") == "done":
                resp = JSONResponse(status_code=existing["code"], content=existing["body"])
                resp.headers["X-Idempotent-Replay"] = "true"
                return resp
            return JSONResponse(status_code=409, content={"detail": {
                "code": "IDEMPOTENT_IN_PROGRESS",
                "message": "Permintaan dengan kunci yang sama masih diproses. Tunggu sebentar."}})
        try:
            response = await call_next(request)
        except Exception:
            await db.idempotency_keys.delete_one({"_id": doc_id})
            raise
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        parsed: Any = None
        try:
            parsed = json.loads(body.decode() or "null")
        except Exception:
            parsed = None
        retry = (response.headers.get(RETRY_HEADER) or "").lower() == "true"
        if parsed is not None and response.status_code < 500 and not retry:
            await db.idempotency_keys.update_one({"_id": doc_id}, {"$set": {
                "status": "done", "code": response.status_code, "body": parsed, "done_at": now_iso()}})
        else:
            await db.idempotency_keys.delete_one({"_id": doc_id})   # 5xx/non-JSON/sementara: biarkan klien coba lagi
        headers: Dict[str, str] = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(content=body, status_code=response.status_code, headers=headers,
                        media_type=response.media_type)


async def ensure_indexes() -> None:
    await db.idempotency_keys.create_index("expires_at", expireAfterSeconds=0)
