"""CR-T5 (CR-08; keputusan K-31) — DAFTAR KERJA "Kredit & Plafon": enam antrean pengendali kredit, janji bayar, naskah
pengingat, dan kotak Eksposur kartu pelanggan (`docs/blueprint/unit/CR-T5.md`).

Satu layar (Keuangan › Piutang › tab "Kredit & Plafon", `CreditDeskView.jsx`) menggantikan lima menu. Semua antrean
disaring PT (`entity_ids` dari konteks — N1; mode "Semua PT" = gabungan hanya-baca, N3) dan cakupan pelanggan pengguna
(sifat peran `data_scope`, PR-T4 — sama dengan `customer_service.can_access_customer`):

| Antrean | Sumber | Urutan |
|---|---|---|
| `menunggu_keputusan` | `credit_overrides` `pending` + `credit_profile_requests` `diajukan` | tertua dulu |
| `ditahan` | `sales_orders` ber-`credit_hold` + `credit_gate_rejections` `terbuka` (koleksi CR-T3; kosong bila belum ada) | terbaru dulu |
| `jatuh_tempo` | `billing_schedule_service.open_lines`, jatuh tempo ≤ hari ini + `JENDELA_JATUH_TEMPO`, per pelanggan | telat terlama dulu |
| `janji_bayar` | `collection_followups` `promised` bertanggal janji, dicatat `JENDELA_JANJI` hari terakhir | `ingkar` dulu, lalu tanggal janji |
| `kaji_ulang` | `customer_credit_profiles`: plafon khusus / bebas denda berakhir ≤ hari ini + `JENDELA_KAJI_ULANG` | `lewat` dulu |
| `denda` | `penalties` `draft` (+ `plan_void`: jadwal tagihannya sudah di-void — usul CR-T4, hari telat bisa tertagih dua kali) | terbaru dulu |

Status janji bayar DIHITUNG SAAT DIBACA (tidak disimpan): `ditepati` bila Σ kwitansi tidak-batal pelanggan itu di PT itu,
bertanggal dari tanggal catatan sampai `promise_date`, ≥ `promise_amount`; selain itu `menunggu` (tanggal belum lewat)
atau `ingkar`. Hari ini = `book_date.tanggal_buku()` (WIB, `02` D6). Uang dalam sen bulat (`02` D5).

Kotak Eksposur (K-31, L6): angka yang dipakai mesin. Bila gerbang kredit CR-T3 (`services/credit_gate.py`) ada, eksposur
& baris yang dihitung (kunci `ar.eksposur_*`) dibaca dari `credit_gate.evaluate` (satu pemilik angka, `02` D1); tanpa
gerbang = perilaku `customer_service.compute_customer_credit` (pesanan belum dikirim dihitung, giro dan titipan tidak).
Baris yang tidak dihitung ditulis "tidak dihitung".
"""
from __future__ import annotations

import importlib.util
import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from fastapi import HTTPException

from core_utils import from_cents, rupiah, safe_doc, to_cents
from db import db
from services.book_date import tanggal_buku, tanggal_panjang

logger = logging.getLogger(__name__)

QUEUES: Tuple[str, ...] = ("menunggu_keputusan", "ditahan", "jatuh_tempo", "janji_bayar", "kaji_ulang", "denda")
#: ASUMSI unit — jendela antrean (parameter fungsi, bukan aturan bisnis yang menahan sesuatu).
JENDELA_JATUH_TEMPO = 3      # = pengingat H-3 bawaan (`notif.ar_due_soon_offsets`, `alert_ops_service.job_ar_due_soon`)
JENDELA_KAJI_ULANG = 14
JENDELA_JANJI = 90
JENDELA_PENOLAKAN = 90
EPS_SEN = 1

PESAN_ANTREAN = "Antrean tidak dikenal."
PESAN_JANJI_TANGGAL = "Tanggal janji bayar wajib diisi."
PESAN_JANJI_FORMAT = "Tanggal janji bayar harus berupa tanggal yang sah (tahun-bulan-tanggal)."
PESAN_JANJI_NOMINAL = "Nominal janji bayar wajib lebih dari nol."
PESAN_JANJI_LAMPAU = "Tanggal janji bayar tidak boleh di masa lalu."
PESAN_TAHAN_BAWAAN = "Menunggu keputusan izin kredit."
PESAN_TANPA_TAGIHAN = "Tidak ada tagihan yang sudah atau akan jatuh tempo."

ST_MENUNGGU, ST_DITEPATI, ST_INGKAR = "menunggu", "ditepati", "ingkar"
_TGL = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class AntreanTakDikenal(ValueError):
    """Nama antrean di luar `QUEUES` (router → 400 `PESAN_ANTREAN`)."""


def _hari_ini(today: Optional[str] = None) -> str:
    return tanggal_buku(today or None)


def _geser(tanggal: str, hari: int) -> str:
    return (date.fromisoformat(tanggal) + timedelta(days=hari)).isoformat()


def _tgl(nilai: Any) -> str:
    """Tanggal buku `YYYY-MM-DD` dari isian/stempel, "" bila kosong atau tidak dikenali (data lama)."""
    if nilai in (None, ""):
        return ""
    try:
        return tanggal_buku(nilai)
    except ValueError:
        return ""


def _hari_antara(dari: str, ke: str) -> int:
    return (date.fromisoformat(ke) - date.fromisoformat(dari)).days


# ── Janji bayar ──────────────────────────────────────────────────────────────────────────────────────────────────────
def promise_fields(outcome: Any, promise_date: Any, promise_amount: Any, today: Optional[str] = None) -> Dict[str, Any]:
    """Isian janji bayar catatan tindak lanjut (`POST /api/customers/{id}/followups`). Hasil selain `promised` → {}.
    `promised` → `{promise_date, promise_amount}` setelah diperiksa; galat → 400 berkalimat (tanpa tulisan apa pun)."""
    if str(outcome or "") != "promised":
        return {}
    tgl = str(promise_date or "").strip()
    if not tgl:
        raise HTTPException(status_code=400, detail=PESAN_JANJI_TANGGAL)
    if not _TGL.match(tgl):
        raise HTTPException(status_code=400, detail=PESAN_JANJI_FORMAT)
    try:
        date.fromisoformat(tgl)
    except ValueError:
        raise HTTPException(status_code=400, detail=PESAN_JANJI_FORMAT) from None
    try:
        nominal = float(promise_amount)
    except (TypeError, ValueError):
        nominal = 0.0
    if isinstance(promise_amount, bool) or not nominal > 0 or nominal != nominal:
        raise HTTPException(status_code=400, detail=PESAN_JANJI_NOMINAL)
    if tgl < _hari_ini(today):
        raise HTTPException(status_code=400, detail=PESAN_JANJI_LAMPAU)
    return {"promise_date": tgl, "promise_amount": from_cents(to_cents(nominal))}


async def _kwitansi_sen(pairs: Iterable[Tuple[str, str]]) -> Dict[Tuple[str, str], List[Tuple[str, int]]]:
    """{(pelanggan, PT): [(tanggal kwitansi, sen)]} kwitansi tidak-batal."""
    out: Dict[Tuple[str, str], List[Tuple[str, int]]] = {}
    for cid, eid in set(pairs):
        rows: List[Tuple[str, int]] = []
        async for rc in db.ar_receipts.find({"customer_id": cid, "entity_id": eid, "status": {"$ne": "void"}},
                                            {"_id": 0, "amount": 1, "receipt_date": 1, "created_at": 1}):
            rows.append((_tgl(rc.get("receipt_date") or rc.get("created_at")), to_cents(float(rc.get("amount") or 0))))
        out[(cid, eid)] = rows
    return out


def promise_status(fu: Dict[str, Any], kwitansi: List[Tuple[str, int]], today: str) -> Tuple[str, float]:
    """(status janji, Σ kwitansi dalam jendela janji). Jendela = tanggal catatan s.d. `promise_date` (ASUMSI unit: seluruh
    kwitansi pelanggan di PT itu, tidak per pesanan)."""
    dari, sampai = _tgl(fu.get("created_at")), str(fu.get("promise_date") or "")
    paid = sum(s for t, s in kwitansi if t and dari <= t <= sampai)
    if paid + EPS_SEN >= to_cents(float(fu.get("promise_amount") or 0)):
        return ST_DITEPATI, from_cents(paid)
    return (ST_MENUNGGU if today <= sampai else ST_INGKAR), from_cents(paid)


async def with_promise_status(followups: List[Dict[str, Any]], today: Optional[str] = None) -> List[Dict[str, Any]]:
    """Catatan tindak lanjut + `promise_status` (dan `promise_paid`) untuk yang berjanji bayar (kartu pelanggan, tab
    Penagihan). Catatan lama tanpa `promise_date` tidak diberi status."""
    hari = _hari_ini(today)
    berjanji = [f for f in followups if f.get("outcome") == "promised" and f.get("promise_date")]
    kw = await _kwitansi_sen((f.get("customer_id") or "", f.get("entity_id") or "") for f in berjanji)
    out = []
    for f in followups:
        if f in berjanji:
            st, paid = promise_status(f, kw.get((f.get("customer_id") or "", f.get("entity_id") or ""), []), hari)
            f = {**f, "promise_status": st, "promise_paid": paid}
        out.append(f)
    return out


# ── Cakupan ──────────────────────────────────────────────────────────────────────────────────────────────────────────
async def customer_scope(actor: Optional[Dict[str, Any]]) -> Optional[Set[str]]:
    """Pelanggan yang boleh dilihat pengguna: None = tanpa batas (cakupan "semua"); selain itu himpunan id pelanggan
    dalam cakupannya (`customer_service.scope_query`, aturan yang sama dengan `can_access_customer`)."""
    from services.data_scope import own_scoped
    if not actor or not own_scoped(actor):
        return None
    from services.customer_service import scope_query
    return set(await db.customers.distinct("id", scope_query(actor, {})))


def _dalam(scope: Optional[Set[str]], cid: Any) -> bool:
    return scope is None or (cid or "") in scope


async def _nama_pelanggan(ids: Iterable[str]) -> Dict[str, str]:
    ids = sorted({i for i in ids if i})
    out: Dict[str, str] = {}
    for i in range(0, len(ids), 500):
        async for c in db.customers.find({"id": {"$in": ids[i:i + 500]}}, {"_id": 0, "id": 1, "name": 1}):
            out[c["id"]] = c.get("name") or ""
    return out


# ── Antrean ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def _ringkas_perubahan(changes: Iterable[Dict[str, Any]]) -> str:
    from services import credit_profile_service as cps
    bagian = []
    for c in changes or []:
        f, v = c.get("field"), c.get("to")
        if f == "credit_limit":
            teks = rupiah(v) if v not in (None, "") and float(v or 0) > 0 else "tanpa batas"
        elif f == "limit_valid_until":
            teks = tanggal_panjang(v) if v else "tanpa batas waktu"
        elif f == "credit_status":
            teks = "diblokir manual" if v == cps.STATUS_BLOKIR else "normal"
        elif f == "limit_mode":
            teks = {"ikut_pt": "ikut PT", "khusus": "khusus", "tanpa_batas": "tanpa batas"}.get(v, "diubah")
        elif f == "overdue_block_days":
            teks = f"{v} hari" if v not in (None, "") else "ikut PT"
        else:
            teks = "diubah"
        bagian.append(f"{cps.LABEL.get(f, 'Profil kredit')}: {teks}")
    return " · ".join(bagian)


async def _menunggu_keputusan(ents: List[str], scope: Optional[Set[str]], today: str,
                              actor: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from services import credit_profile_service as cps
    from services import dual_control as dc
    rows: List[Dict[str, Any]] = []
    async for co in db.credit_overrides.find({"entity_id": {"$in": ents}, "status": "pending"},
                                             {"_id": 0, "credit_snapshot": 0}):
        if not _dalam(scope, co.get("customer_id")):
            continue
        cek = await dc.periksa("lewat_batas_kredit", co, actor or {}, co.get("entity_id") or "",
                               nominal=float(co.get("amount") or 0), pengaju=[co.get("requested_by_id")])
        rows.append({"kind": "izin_kredit", "id": co["id"], "number": co.get("order_number") or "",
                     "customer_id": co.get("customer_id") or "", "customer_name": co.get("customer_name") or "",
                     "entity_id": co.get("entity_id") or "", "amount": round(float(co.get("amount") or 0), 2),
                     "order_id": co.get("order_id") or "", "order_number": co.get("order_number") or "",
                     "requested_by": co.get("requested_by") or "", "requested_by_id": co.get("requested_by_id") or "",
                     "created_at": co.get("created_at") or "",
                     # CR-T3 (bila ada): label alasan baku + lingkup izin (pesanan/pelanggan)
                     "summary": " — ".join(x for x in dict.fromkeys((co.get("reason_label") or "", co.get("reason") or ""))
                                           if x),
                     "scope": co.get("scope") or "", "blocked_reason": cek.get("pesan") or ""})
    async for rq in db[cps.COLL_REQ].find({"entity_id": {"$in": ents}, "status": cps.ST_DIAJUKAN},
                                          {"_id": 0, "credit_snapshot": 0}):
        if not _dalam(scope, rq.get("customer_id")):
            continue
        ringkas = _ringkas_perubahan(rq.get("changes"))
        rows.append({"kind": "ubah_profil", "id": rq["id"], "number": rq.get("number") or "",
                     "customer_id": rq.get("customer_id") or "", "customer_name": rq.get("customer_name") or "",
                     "entity_id": rq.get("entity_id") or "", "amount": round(cps.nominal_dari(rq), 2),
                     "order_id": "", "order_number": "",
                     "requested_by": rq.get("requested_by") or "", "requested_by_id": rq.get("requested_by_id") or "",
                     "created_at": rq.get("created_at") or "",
                     "summary": " · ".join(x for x in (ringkas, rq.get("reason") or "") if x),
                     "blocked_reason": await cps.periksa_putus(rq, actor or {})})
    for r in rows:
        dibuat = _tgl(r["created_at"])
        r["age_days"] = max(0, _hari_antara(dibuat, today)) if dibuat else 0
    rows.sort(key=lambda r: (str(r["created_at"]), r["id"]))
    return rows


def _alasan_tahan(o: Dict[str, Any]) -> Tuple[str, str]:
    """(pesan alasan, sejak) pesanan ber-`credit_hold`: `credit_hold_info` (CR-T3) → entri persetujuan kredit yang
    menunggu (jalur `request-credit-approval`) → kalimat bawaan."""
    info = o.get("credit_hold_info") or {}
    reasons = info.get("reasons") or []
    msg = ""
    if reasons:
        r0 = reasons[0]
        msg = str((r0.get("message") if isinstance(r0, dict) else r0) or "")
    entri = next((p for p in reversed(o.get("pending_approvals") or [])
                  if isinstance(p, dict) and p.get("type") == "kredit" and p.get("status") == "pending"), None) or {}
    msg = msg or str(entri.get("reason") or "") or PESAN_TAHAN_BAWAAN
    sejak = info.get("since") or entri.get("requested_at") or entri.get("created_at") or o.get("updated_at") \
        or o.get("created_at") or ""
    return msg, str(sejak)


async def _ditahan(ents: List[str], scope: Optional[Set[str]], today: str,
                   actor: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from services.customer_service import DEAD_STATUSES, _order_grand_total
    recheck = importlib.util.find_spec("services.credit_gate") is not None   # CR-T3: POST …/credit-recheck
    rows: List[Dict[str, Any]] = []
    async for o in db.sales_orders.find({"entity_id": {"$in": ents}, "credit_hold": True,
                                         "status": {"$nin": sorted(DEAD_STATUSES)}},
                                        {"_id": 0, "id": 1, "number": 1, "customer_id": 1, "customer_name": 1,
                                         "entity_id": 1, "grand_total": 1, "total_amount": 1, "extra_billing_lines": 1,
                                         "credit_hold_info": 1, "pending_approvals": 1, "created_at": 1,
                                         "updated_at": 1}):
        if not _dalam(scope, o.get("customer_id")):
            continue
        msg, sejak = _alasan_tahan(o)
        rows.append({"kind": "pesanan_ditahan", "id": o["id"], "order_id": o["id"], "order_number": o.get("number") or "",
                     "customer_id": o.get("customer_id") or "", "customer_name": o.get("customer_name") or "",
                     "entity_id": o.get("entity_id") or "", "amount": round(_order_grand_total(o), 2),
                     "message": msg, "since": sejak, "recheck_available": recheck})
    async for g in db.credit_gate_rejections.find({"entity_id": {"$in": ents}, "status": "terbuka"},
                                                  {"_id": 0, "payload_snapshot": 0}):
        if not _dalam(scope, g.get("customer_id")):
            continue
        r0 = (g.get("reasons") or [{}])[0]
        rows.append({"kind": "pesanan_ditolak", "id": g["id"], "order_id": "", "order_number": "",
                     "customer_id": g.get("customer_id") or "", "customer_name": g.get("customer_name") or "",
                     "entity_id": g.get("entity_id") or "", "amount": round(float(g.get("amount") or 0), 2),
                     "message": str((r0.get("message") if isinstance(r0, dict) else r0) or ""),
                     "since": str(g.get("created_at") or ""), "recheck_available": False})
    rows.sort(key=lambda r: (r["since"], r["id"]), reverse=True)
    return rows


async def due_lines(ents: List[str], customer_ids: Optional[Iterable[str]], today: str,
                    window: int = JENDELA_JATUH_TEMPO) -> List[Dict[str, Any]]:
    """Baris tagihan terbuka (`billing_schedule_service.open_lines` — satu pembaca jatuh tempo) yang jatuh tempo
    ≤ hari ini + `window` hari, jatuh tempo tertua dulu."""
    from services import billing_schedule_service as bss
    batas = _geser(today, window)
    # posisi = hari ini WIB (tanpa `as_of`: hanya pesanan belum lunas; `tanggal_buku()` = hari ini yang sama)
    lines = await bss.open_lines(entity_ids=ents, customer_ids=sorted(customer_ids) if customer_ids is not None
                                 else None)
    return [ln for ln in lines if ln.get("due_date") and ln["due_date"] <= batas]


async def _jatuh_tempo(ents: List[str], scope: Optional[Set[str]], today: str,
                       actor: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lines = await due_lines(ents, scope, today)
    grup: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for ln in lines:
        grup.setdefault((ln.get("customer_id") or "", ln.get("entity_id") or ""), []).append(ln)
    names = await _nama_pelanggan(c for c, _ in grup)
    rows = []
    for (cid, eid), lns in grup.items():
        lns.sort(key=lambda x: (x["due_date"], x.get("order_number") or "", int(x.get("seq") or 0)))
        akan = [x["due_date"] for x in lns if x["due_date"] >= today]
        rows.append({"id": f"{cid}:{eid}", "customer_id": cid, "customer_name": names.get(cid, ""), "entity_id": eid,
                     "line_count": len(lns),
                     "total_outstanding": from_cents(sum(to_cents(x["outstanding"]) for x in lns)),
                     "max_days_late": max(int(x.get("days_late") or 0) for x in lns),
                     "oldest_due_date": lns[0]["due_date"], "next_due_date": min(akan) if akan else None,
                     "lines": [{"order_id": x["order_id"], "order_number": x.get("order_number") or "",
                                "line_id": x.get("line_id") or "", "kind": x.get("kind") or "",
                                "label": x.get("label") or "", "due_date": x["due_date"],
                                "outstanding": x["outstanding"], "days_late": int(x.get("days_late") or 0)}
                               for x in lns]})
    rows.sort(key=lambda r: (-r["max_days_late"], r["oldest_due_date"], r["customer_name"]))
    return rows


async def _janji_bayar(ents: List[str], scope: Optional[Set[str]], today: str,
                       actor: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    batas = _geser(today, -JENDELA_JANJI)
    fus = []
    async for f in db.collection_followups.find({"entity_id": {"$in": ents}, "outcome": "promised",
                                                 "promise_date": {"$type": "string", "$gt": ""}}, {"_id": 0}):
        if _dalam(scope, f.get("customer_id")) and _tgl(f.get("created_at")) >= batas:
            fus.append(f)
    kw = await _kwitansi_sen((f.get("customer_id") or "", f.get("entity_id") or "") for f in fus)
    rows = []
    for f in fus:
        st, paid = promise_status(f, kw.get((f.get("customer_id") or "", f.get("entity_id") or ""), []), today)
        rows.append({"id": f["id"], "customer_id": f.get("customer_id") or "",
                     "customer_name": f.get("customer_name") or "", "entity_id": f.get("entity_id") or "",
                     "order_id": f.get("order_id") or "", "promise_date": f["promise_date"],
                     "promise_amount": round(float(f.get("promise_amount") or 0), 2), "paid_amount": paid,
                     "status": st, "note": f.get("note") or "", "created_by": f.get("created_by") or "",
                     "created_at": f.get("created_at") or ""})
    rows.sort(key=lambda r: (r["status"] != ST_INGKAR, r["promise_date"], r["customer_name"]))
    return rows


async def _kaji_ulang(ents: List[str], scope: Optional[Set[str]], today: str,
                      actor: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from services import credit_profile_service as cps
    batas = _geser(today, JENDELA_KAJI_ULANG)
    calon = []
    async for p in db[cps.COLL].find({"entity_id": {"$in": ents}}, {"_id": 0}):
        if not _dalam(scope, p.get("customer_id")):
            continue
        akhir = str(p.get("limit_valid_until") or "")
        if p.get("limit_mode") == cps.MODE_KHUSUS and akhir and akhir <= batas:
            calon.append((p, "plafon", akhir))
        aturan = p.get("penalty_rule") or {}
        akhir_d = str(aturan.get("valid_until") or "") if isinstance(aturan, dict) else ""
        if akhir_d and akhir_d <= batas:
            calon.append((p, "bebas_denda", akhir_d))
    names = await _nama_pelanggan(p.get("customer_id") for p, _, _ in calon)
    sejak = f"{_geser(today, -JENDELA_PENOLAKAN)}"
    tolak: Dict[Tuple[str, str], int] = {}
    rows = []
    for p, jenis, akhir in calon:
        key = (p.get("customer_id") or "", p.get("entity_id") or "")
        if key not in tolak:
            tolak[key] = await db.credit_gate_rejections.count_documents(
                {"customer_id": key[0], "entity_id": key[1], "created_at": {"$gte": sejak}})
        rows.append({"id": f"{p.get('id') or key[0]}:{jenis}", "customer_id": key[0],
                     "customer_name": names.get(key[0], ""), "entity_id": key[1], "kind": jenis, "valid_until": akhir,
                     "state": "lewat" if akhir < today else "mendekati", "rejections_90d": tolak[key],
                     "credit_limit": (round(float(p.get("credit_limit") or 0), 2) if jenis == "plafon" else None)})
    rows.sort(key=lambda r: (r["state"] != "lewat", r["valid_until"], r["customer_name"]))
    return rows


async def _denda(ents: List[str], scope: Optional[Set[str]], today: str,
                 actor: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from services import penalty_service
    pens = [p async for p in db[penalty_service.COLL].find({"entity_id": {"$in": ents}, "status": "draft"}, {"_id": 0})
            if _dalam(scope, p.get("customer_id"))]
    plan_ids = sorted({p.get("plan_id") for p in pens if p.get("plan_id")})
    void: Set[str] = set()
    for i in range(0, len(plan_ids), 500):
        async for pl in db.payment_plans.find({"id": {"$in": plan_ids[i:i + 500]}, "status": "void"},
                                              {"_id": 0, "id": 1}):
            void.add(pl["id"])
    rows = [{**safe_doc(p), "plan_void": p.get("plan_id") in void} for p in pens]
    rows.sort(key=lambda r: (str(r.get("created_at") or ""), r.get("id") or ""), reverse=True)
    return rows


_PEMBANGUN = {"menunggu_keputusan": _menunggu_keputusan, "ditahan": _ditahan, "jatuh_tempo": _jatuh_tempo,
              "janji_bayar": _janji_bayar, "kaji_ulang": _kaji_ulang, "denda": _denda}
#: Isian yang dicari kotak cari (`q`).
_CARI = ("customer_name", "number", "order_number", "doc_number", "summary", "message", "requested_by", "note")


def _cocok(row: Dict[str, Any], kata: str) -> bool:
    teks = " ".join(str(row.get(k) or "") for k in _CARI).lower()
    teks += " " + " ".join(str(ln.get("order_number") or "") for ln in row.get("lines") or []).lower()
    return kata in teks


async def _rows(name: str, entity_ids: List[str], actor: Optional[Dict[str, Any]], q: str = "",
                today: Optional[str] = None, scope: Any = ...) -> List[Dict[str, Any]]:
    if name not in _PEMBANGUN:
        raise AntreanTakDikenal(PESAN_ANTREAN)
    ents = [e for e in (entity_ids or []) if e and e != "all"]
    if not ents:
        return []
    if scope is ...:
        scope = await customer_scope(actor)
    rows = await _PEMBANGUN[name](ents, scope, _hari_ini(today), actor)
    kata = str(q or "").strip().lower()
    return [r for r in rows if _cocok(r, kata)] if kata else rows


async def queue(name: str, entity_ids: List[str], actor: Optional[Dict[str, Any]], page: int = 1,
                page_size: int = 25, q: str = "", today: Optional[str] = None) -> Dict[str, Any]:
    """Satu antrean, berhalaman: `{items, total, page, page_size}` (daftar tidak dipotong diam-diam, `02` D4)."""
    rows = await _rows(name, entity_ids, actor, q, today)
    page, page_size = max(1, int(page or 1)), max(1, int(page_size or 25))
    start = (page - 1) * page_size
    return {"items": rows[start:start + page_size], "total": len(rows), "page": page, "page_size": page_size}


async def summary(entity_ids: List[str], actor: Optional[Dict[str, Any]], today: Optional[str] = None) -> Dict[str, int]:
    """Jumlah baris tiap antrean — selalu = `total` antrean itu (dihitung dengan pembangun yang sama)."""
    scope = await customer_scope(actor)
    return {n: len(await _rows(n, entity_ids, actor, "", today, scope)) for n in QUEUES}


# ── Naskah pengingat ─────────────────────────────────────────────────────────────────────────────────────────────────
async def reminder_text(customer: Dict[str, Any], entity_id: str, today: Optional[str] = None) -> Dict[str, Any]:
    """Naskah pengingat siap salin (templat unit, persis) untuk tagihan pelanggan yang sudah atau akan jatuh tempo
    (baris antrean "Jatuh tempo"). PM-T2 sudah ada: baris tagihan berkode bayar aktif menambah " · kode bayar {kode}",
    dan rekening tujuan pesanan yang boleh tampil di dokumen ditulis "Transfer ke: {rekening}" sesudah total (aturan
    `payment_code_service.instruction_for`). → `{text, lines, total, note}`."""
    from services import payment_code_service as pcs
    from services import credit_profile_service as cps
    hari = _hari_ini(today)
    lines = await due_lines([entity_id], [customer["id"]], hari)
    pt = (await cps.ringkas_pt([entity_id]) or [{}])[0]
    nama_pt = pt.get("legal_name") or pt.get("short_name") or "PT"
    if not lines:
        return {"text": "", "lines": 0, "total": 0.0, "note": PESAN_TANPA_TAGIHAN}
    kode: Dict[Tuple[str, str], str] = {}
    async for c in db[pcs.COLL].find({"order_id": {"$in": sorted({x["order_id"] for x in lines})}, "status": "aktif",
                                      "line_id": {"$in": sorted({x["line_id"] for x in lines if x.get("line_id")})}},
                                     {"_id": 0, "order_id": 1, "line_id": 1, "code": 1}):
        kode[(c["order_id"], c["line_id"])] = c.get("code") or ""
    teks = [f"Yth. {customer.get('name') or 'Pelanggan'},",
            f"Berikut tagihan {nama_pt} yang sudah atau akan jatuh tempo:"]
    total = 0
    for x in lines:
        k = kode.get((x["order_id"], x.get("line_id") or ""))
        teks.append(f"- {x.get('order_number') or ''} · {rupiah(x['outstanding'])} · jatuh tempo "
                    f"{tanggal_panjang(x['due_date'])}" + (f" · kode bayar {k}" if k else ""))
        total += to_cents(x["outstanding"])
    teks.append(f"Total: {rupiah(from_cents(total))}")
    rekening: List[str] = []
    async for o in db.sales_orders.find({"id": {"$in": sorted({x["order_id"] for x in lines})},
                                         "receiving_account_id": {"$type": "string", "$gt": ""}},
                                        {"_id": 0, "receiving_account_id": 1, "receiving_account": 1}):
        acc = await db.bank_accounts.find_one({"id": o["receiving_account_id"]}, {"_id": 0, "show_on_documents": 1})
        t = pcs.teks_rekening(pcs.potret_rekening(o.get("receiving_account"))) if (acc or {}).get("show_on_documents") \
            else ""
        if t and t not in rekening:
            rekening.append(t)
    teks += [f"Transfer ke: {t}" for t in rekening]
    teks.append("Mohon konfirmasi pembayarannya. Terima kasih.")
    return {"text": "\n".join(teks), "lines": len(lines), "total": from_cents(total), "note": ""}


# ── Kotak Eksposur (K-31, L6) ────────────────────────────────────────────────────────────────────────────────────────
#: (baris, kunci CR-T3, nilai yang dipakai mesin selama gerbang kredit CR-T3 belum ada = perilaku
#: `customer_service.compute_customer_credit`: pesanan belum dikirim dihitung, giro dan titipan tidak).
KUNCI_EKSPOSUR: Tuple[Tuple[str, str, bool], ...] = (
    ("belum_kirim", "ar.eksposur_pesanan_belum_kirim", True),
    ("giro", "ar.eksposur_giro_belum_cair", False),
    ("titipan", "ar.eksposur_titipan_mengurangi", False),
)
#: `credit_gate.evaluate(...)["counted"]` → baris kotak.
_DARI_GERBANG = {"belum_kirim": "open_orders", "giro": "giro", "titipan": "deposit"}


def _gerbang():
    """Modul gerbang kredit CR-T3 bila sudah ada (SATU pemilik angka eksposur, `02` D1); None bila belum."""
    try:
        from services import credit_gate
    except ImportError:
        return None
    return credit_gate


async def exposure(customer: Dict[str, Any], entity_id: str) -> Dict[str, Any]:
    """Kotak Eksposur kartu pelanggan untuk (pelanggan, PT): baris berlabel tetap (unit), angka = yang DIPAKAI mesin.

    Dengan gerbang kredit (CR-T3): eksposur, baris yang dihitung (`ar.eksposur_*`, `finance.tahan_kirim_tunai`), dan
    plafon dari `credit_gate.evaluate` titik "periksa ulang" (pesanan baru Rp 0 — tanpa tulisan). Tanpa gerbang: rumus
    `compute_customer_credit` hari ini. Angka mentah tiap baris dari saldo piutang tersimpan (`customer_balance_service`);
    baris yang tidak dihitung ditulis "tidak dihitung". Titipan yang mengurangi = titipan pelanggan; saldo kredit toko
    tidak mengurangi eksposur (ditulis di keterangan)."""
    from services import credit_profile_service as cps
    from services import customer_balance_service as cbs
    cid = customer["id"]
    bal = await cbs.get(cid, entity_id)
    gate = _gerbang()
    hasil = None
    if gate is not None:
        hasil = await gate.evaluate(customer_id=cid, entity_id=entity_id, checkpoint=gate.PERIKSA_ULANG,
                                    order_amount=0.0)
        hitung = hasil.get("counted") or {}
        counted = {b: bool(hitung.get(k)) for b, k in _DARI_GERBANG.items()}
        tunai_ikut = bool(hitung.get("cash_term"))
        plafon = to_cents((hasil.get("limit") or {}).get("credit_limit") or 0)
        limit_source = (hasil.get("limit") or {}).get("limit_source")
    else:
        counted = {b: hari_ini for b, _k, hari_ini in KUNCI_EKSPOSUR}
        tunai_ikut = False
        eff = await cps.effective(cid, entity_id, customer=customer)
        plafon = to_cents(eff.get("credit_limit") or 0)
        limit_source = eff.get("limit_source")
    terkirim = to_cents(bal.get("ar_delivered") or 0) - (0 if tunai_ikut else to_cents(bal.get("cash_term_amount") or 0))
    belum = to_cents(bal.get("open_orders_amount") or 0) - to_cents(bal.get("cash_term_open_amount") or 0)
    giro = to_cents(bal.get("giro_outstanding") or 0)
    titipan = to_cents(bal.get("deposit_balance") or 0)
    toko = to_cents(bal.get("store_credit_balance") or 0)
    eks = terkirim + (belum if counted["belum_kirim"] else 0) + (giro if counted["giro"] else 0) \
        - (titipan if counted["titipan"] else 0)
    if hasil is not None:
        eks = to_cents((hasil.get("exposure") or {}).get("total") or 0)   # angka gerbang (satu pemilik)

    def baris(key: str, label: str, sen: Optional[int], *, counted_: bool = True, sign: str = "+",
              note: str = "") -> Dict[str, Any]:
        return {"key": key, "label": label, "amount": None if sen is None else from_cents(sen), "counted": counted_,
                "sign": sign, "note": note if note else ("" if counted_ else "tidak dihitung")}

    rows = [
        baris("terkirim", "Piutang barang terkirim", terkirim),
        baris("belum_kirim", "Pesanan belum dikirim", belum, counted_=counted["belum_kirim"]),
        baris("giro", "Giro belum cair", giro, counted_=counted["giro"]),
        baris("titipan", "Titipan & saldo kredit", titipan, counted_=counted["titipan"], sign="-"),
        baris("eksposur", "Eksposur", eks, sign="="),
        baris("plafon", "Plafon", plafon if plafon > 0 else None, sign="",
              note="" if plafon > 0 else "tanpa batas"),
        baris("sisa", "Sisa plafon", (plafon - eks) if plafon > 0 else None, sign="",
              note="" if plafon > 0 else "tanpa batas"),
    ]
    catatan = [] if tunai_ikut else ["Pesanan bertermin tunai tidak dihitung dalam eksposur."]
    if toko > 0:
        catatan.append(f"Saldo kredit toko {rupiah(from_cents(toko))} tidak mengurangi eksposur.")
    pt = (await cps.ringkas_pt([entity_id]) or [{"id": entity_id}])[0]
    return {"customer_id": cid, "entity_id": entity_id, "entity": pt, "rows": rows,
            "penalty": {"label": "Denda belum dibayar (tidak mengurangi plafon)",
                        "amount": round(float(bal.get("penalty_outstanding") or 0), 2)},
            "limit_source": limit_source, "source": "gerbang_kredit" if hasil is not None else "bawaan",
            "note": " ".join(catatan)}
