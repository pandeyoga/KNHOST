"""AG-T3 — mesin kartu tindakan asisten golongan A dan B lewat pintu aplikasi sendiri (K-44, K-45).

Asisten hanya **menyiapkan** kartu (`prepare`): rencana sebelum → sesudah dibaca lewat `SelfApi` baca-saja (GET ke
endpoint layar, dengan sesi & PT pengguna). Tidak ada yang tertulis sebelum pengguna menyetujui kartu; giliran model
berhenti di sini — tidak ada alat untuk menyetujui. Sesudah disetujui (`decide`), kartu memanggil **endpoint yang sama
dengan layar**, tepat sekali (`Idempotency-Key: <id kartu>`), dengan izin pengguna sendiri, lalu berakhir `confirmed`
atau `failed`. Tidak ada jalan pintas ke database untuk tulisan.

    kartu = await ai_cards.prepare("ar_receipt_create", {"customer_id": "cus_c", "amount": 5000000,
                                   "allocations": [{"order_id": "so_c1", "amount": 5000000}]},
                                   request=request, user=user, ctx=ctx, session_id="aichat_…", user_request="…")
    kartu = await ai_cards.decide(kartu["id"], request=request, user=user, ctx=ctx, decision="approve",
                                  reason="pelanggan transfer pagi ini", retype="5.000.000")

Status hanya maju: `pending → running → confirmed | failed`; `pending → dismissed | expired | superseded`. Kartu baru di
percakapan yang sama menandai kartu `pending` sebelumnya `superseded` (indeks unik parsial `uq_pending_session`).

Golongan A (tindak lanjut penagihan, janji bayar, tanda sudah diingatkan) tidak menuntut sakelar tambahan. Golongan B
(kwitansi piutang, pencocokan mutasi bank, alokasi titipan, ulang jurnal gagal) menuntut izin `ai_finance.create`,
golongan `B` di `users.ai_finance.classes`, dan `ai.tindakan_uang_masuk` menyala untuk PT kartu (bawaan mati, H5).

AG-T5 — golongan C (bayar tagihan pemasok, bayar kontrabon, kas manual: izin `ai_finance.pay`; jurnal manual, balik
jurnal: izin `ai_finance.post`) menuntut izin kartunya, golongan `C` di akun, dan `ai.tindakan_uang_keluar` menyala untuk PT kartu (bawaan mati, H5). Saat pembuat menyetujui, kontrol dua orang
`kontrol.asisten_uang_keluar.*` (KF-T6) diputus: tidak butuh → dijalankan seperti golongan A/B; butuh → kartu
`awaiting_second` (potret `second_required`, `first_by`), notifikasi ke pemegang `ai_finance.approve` di PT kartu, dan
baru dijalankan saat orang kedua menyetujui (`second`) — dengan SESI orang kedua, yang karena itu wajib memegang izin
pintunya. Transisi tambahan: `pending → awaiting_second → running → confirmed | failed`; `awaiting_second → dismissed |
expired`. Kode yang tidak terdaftar dijawab alasan daftar larangan (`services/ai_card_rules.py`) bila cocok.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException

from core_utils import new_id, now_iso, rupiah
from db import db
from dependencies import audit, denied, has_permission
from services.ai_self_api import ENTITY_MESSAGE, SelfApi, SelfApiError, _has_entity_key
from services.config_resolver import value_of

KUNCI_UANG_MASUK = "ai.tindakan_uang_masuk"
KUNCI_MAKS_HARIAN = "ai.tindakan_maks_per_hari"
KUNCI_MASA_BERLAKU = "ai.kartu_masa_berlaku_jam"   # AG-T1 — masa berlaku kartu per PT kartu
KUNCI_UANG_KELUAR = "ai.tindakan_uang_keluar"     # AG-T5 — sakelar PT golongan C (bawaan mati, H5)
AKSI_DUA_ORANG = "asisten_uang_keluar"            # AG-T5 — aksi kontrol dua orang (`config_catalog_kontrol`)
#: Validasi isian (bukan aturan bisnis, ASUMSI spesifikasi): panjang alasan minimal untuk tingkat `medium`/`high`.
REASON_MIN = 10
#: Batas teknis tampilan daftar kartu.
PAGE_SIZE_DEFAULT, PAGE_SIZE_MAX = 20, 100
#: Batas teknis pembacaan sidik berhalaman (`pages`): halaman paling banyak yang dibaca untuk menemukan baris.
FINGERPRINT_MAX_PAGES = 10

MSG_TIDAK_DIKENAL = "Tindakan ini tidak bisa dilakukan lewat asisten. Lakukan di layarnya."
MSG_SEMUA_PT = "Pilih satu PT dulu. Tindakan tidak bisa disiapkan dalam mode Semua PT."
MSG_AKUN_MATI = "Tindakan uang masuk lewat asisten belum dinyalakan untuk akun Anda."
MSG_IZIN_B = ("Anda belum punya akses untuk menyiapkan dan menyetujui tindakan lewat asisten. Minta Admin menambahkan "
              "akses 'Asisten Tanya KN'.")
MSG_ALASAN = "Tulis alasan singkat (minimal 10 huruf)."
MSG_KETIK = "Ketik ulang nominal persis seperti di kartu."
MSG_BATAS = "Batas tindakan asisten hari ini sudah tercapai ({n})."
MSG_STALE = "Data sudah berubah sejak kartu disiapkan. Minta asisten menyiapkannya lagi."
MSG_PEMBUAT = "Hanya pembuat kartu yang boleh menyetujui atau mengabaikannya."
MSG_TANPA_AKSES_PT = "Anda tidak lagi punya akses ke PT kartu ini."
MSG_TIDAK_PASTI = "Hasil tidak pasti: jawaban pintu tidak diterima. Periksa dokumennya sebelum meminta kartu baru."
MSG_SEDANG_DISIAPKAN = "Kartu lain di percakapan ini sedang disiapkan. Coba lagi."
# AG-T5 — golongan C (uang keluar) dan orang kedua
MSG_AKUN_MATI_C = "Tindakan uang keluar dan jurnal lewat asisten belum dinyalakan untuk akun Anda."
MSG_IZIN_C_PAY = ("Anda belum punya akses untuk menyiapkan dan menyetujui uang keluar lewat asisten. Minta Admin "
                  "menambahkan akses 'Asisten Tanya KN'.")
MSG_IZIN_C_POST = ("Anda belum punya akses untuk menyiapkan dan menyetujui jurnal lewat asisten. Minta Admin "
                   "menambahkan akses 'Asisten Tanya KN'.")
MSG_KETIK_NOMOR = "Ketik ulang nomor jurnal persis seperti di kartu."
MSG_JURNAL_USULAN = "Usulan jurnal menunggu persetujuan di layar Jurnal"
MSG_IZIN_KEDUA = ("Anda belum punya akses untuk menyetujui kartu asisten sebagai orang kedua. Minta Admin menambahkan "
                  "akses 'Asisten Tanya KN'.")
MSG_BUKAN_MENUNGGU = "Kartu ini tidak sedang menunggu orang kedua."
MSG_ALASAN_TOLAK = "Tulis alasan menolak (minimal 10 huruf)."
MSG_KEPUTUSAN_KEDUA = "Keputusan orang kedua harus setujui atau tolak."
MSG_REKENING = "Rekening itu bukan rekening aktif PT tagihan ini. Pilih rekening dari daftar rekening PT aktif."
MSG_REKENING_KAS = "Rekening itu bukan rekening aktif PT aktif. Pilih rekening dari daftar rekening PT aktif."
MSG_STATUS = {
    "confirmed": "Kartu ini sudah dijalankan.",
    "failed": "Kartu ini gagal dan tidak bisa diulang.",
    "superseded": "Kartu ini sudah diganti kartu yang lebih baru.",
    "dismissed": "Kartu ini sudah diabaikan.",
    "expired": "Kartu ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi.",
    "running": "Kartu ini sedang diproses.",
    "awaiting_second": "Kartu ini sedang menunggu persetujuan orang kedua.",   # AG-T5
}
METHOD_LABEL = {"transfer": "Transfer", "tunai": "Tunai", "cash": "Tunai", "giro": "Giro", "qris": "QRIS",
                "kartu": "Kartu debit/kredit", "cek": "Cek"}
HOLDING_REASONS = {"identified_customer": "Pengirim akhirnya teridentifikasi",
                   "customer_confirmation": "Dikonfirmasi pelanggan lewat bukti transfer",
                   "sales_confirmation": "Dikonfirmasi sales/penagih",
                   "partial_identification": "Sebagian teridentifikasi (sisanya masih ditelusuri)"}
FOLLOWUP_OUTCOMES = {"contacted": "Sudah dihubungi", "no_response": "Tidak menjawab", "escalated": "Dinaikkan ke atasan"}
NOTE_JURNAL = "Jurnal dibuat sistem saat disimpan."


def _err(status: int, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail=message)


# ── Tindakan terdaftar ────────────────────────────────────────────────────────────────────────────────────────────────
Prepare = Callable[[SelfApi, Dict[str, Any]], Awaitable[Dict[str, Any]]]
BuildRequest = Callable[[Dict[str, Any], Dict[str, Any]], Tuple[Dict[str, Any], Any]]
ResultOf = Callable[[Any, Dict[str, Any], Dict[str, Any]], Dict[str, Any]]


@dataclass
class CardAction:
    code: str
    label: str
    cls: str                 # "A" | "B"
    risk: str                # "low" | "medium" | "high"
    write_method: str
    write_path: str          # pola path, mis. "/api/customers/{customer_id}/followups"
    prepare: Prepare         # hanya GET; mengembalikan {args, plan, fingerprint_source}
    build_request: BuildRequest   # (args, plan) -> (path_params, json)
    result_of: ResultOf      # (jawaban endpoint, args, plan) -> {document, gl_status}
    editable: Tuple[Dict[str, str], ...] = field(default_factory=tuple)
    # AG-T5 — golongan C: izin pintu (yang juga wajib dipegang orang kedua) dan izin kartu (`ai_finance.<card_perm>`).
    door: Tuple[str, str] = ("", "")
    card_perm: str = ""
    retype_kind: str = "amount"   # "amount" = digit nominal · "text" = nomor dokumen persis (balik jurnal)


REGISTRY: Dict[str, CardAction] = {}


def _pattern(path: str) -> "re.Pattern[str]":
    return re.compile("^" + re.sub(r"\\\{[a-z_]+\\\}", "[^/]+", re.escape(path)) + "/?$")


#: Pintu tulis kartu lama yang dialihkan ke endpoint layar (serah-terima b): draf PO → `POST /api/purchase-orders`.
LEGACY_WRITE_PATHS: Tuple[Tuple[str, str], ...] = (("POST", "/api/purchase-orders"),)


def write_allowed(method: str, path: str) -> bool:
    """`SelfApi` mode tulis hanya menerima path yang cocok dengan `write_path` tindakan terdaftar."""
    pairs = [(a.write_method, a.write_path) for a in REGISTRY.values()] + list(LEGACY_WRITE_PATHS)
    return any(m.upper() == (method or "").upper() and _pattern(p).match(path or "") for m, p in pairs)


def _fill(path: str, params: Dict[str, Any]) -> str:
    def rep(m: "re.Match[str]") -> str:
        v = str(params.get(m.group(1)) or "")
        if not v or "/" in v or ".." in v or "?" in v or "#" in v:
            raise _err(400, "Isian kartu tidak lengkap.")
        return v
    return re.sub(r"\{([a-z_]+)\}", rep, path)


# ── Pembantu angka & teks ─────────────────────────────────────────────────────────────────────────────────────────────
def _money(v: Any) -> float:
    try:
        return round(float(v or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _norm(v: Any) -> Any:
    if isinstance(v, bool) or v is None:
        return v
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in sorted(v.items())}
    return str(v)


def confirm_text_of(amount: float) -> str:
    """Nominal tanpa pemisah ribuan untuk ketik ulang: 5000000 → "5000000"; 1500,5 → "1500,50"."""
    a = round(float(amount or 0), 2)
    return str(int(a)) if a == int(a) else f"{a:.2f}".replace(".", ",")


def _digits(v: Any) -> str:
    return re.sub(r"\D", "", str(v or ""))


def _norm_nomor(v: Any) -> str:
    """Nomor dokumen untuk ketik ulang: tanpa spasi, huruf besar ("ksc/je-00005" = "KSC/JE-00005")."""
    return re.sub(r"\s+", "", str(v or "")).upper()


def _clean_args(args: Any) -> Dict[str, Any]:
    """Isian alat dari model: `null` dibuang (skema ketat mewajibkan semua kunci)."""
    if not isinstance(args, dict):
        return {}
    return {k: v for k, v in args.items() if v is not None and v != ""}


def _text(v: Any, limit: int = 500) -> str:
    return str(v or "").strip()[:limit]


def _date(v: Any, label: str, *, required: bool = False) -> str:
    s = _text(v, 10)
    if not s:
        if required:
            raise _err(400, f"{label} wajib diisi.")
        return ""
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        raise _err(400, f"{label} harus berbentuk TTTT-BB-HH.")
    return s


def _today_wib() -> str:
    from services.analytics_time import now_wib
    return now_wib().date().isoformat()


def fingerprint(snapshots: List[Any]) -> str:
    """Sidik sha256 atas potret data dasar (D3): urutan kunci tetap, angka dibulatkan 2 desimal."""
    raw = json.dumps(_norm(snapshots), sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _at(obj: Any, dotted: str) -> Any:
    for k in [x for x in (dotted or "").split(".") if x]:
        obj = obj.get(k) if isinstance(obj, dict) else None
    return obj


def _pick(resp: Any, pick: Dict[str, Any]) -> Any:
    """Potong jawaban GET menjadi potret: daftar → baris ber-`key` dalam `ids` (yang hilang ditandai), objek → `fields`."""
    target = _at(resp, pick.get("at") or "")
    fields = list(pick.get("fields") or [])
    if isinstance(target, list):
        key = pick.get("key") or "id"
        ids = [str(i) for i in (pick.get("ids") or [])]
        rows = [r for r in target if isinstance(r, dict) and (not ids or str(r.get(key)) in ids)]
        out = [{key: str(r.get(key)), **{f: _norm(r.get(f)) for f in fields}} for r in rows]
        have = {r[key] for r in out}
        out += [{key: i, "missing": True} for i in ids if i not in have]
        return sorted(out, key=lambda r: str(r.get(key)))
    if isinstance(target, dict):
        return {f: _norm(target.get(f)) for f in fields}
    return _norm(target)


async def _get(api: SelfApi, src: Dict[str, Any], cache: Dict[str, Any]) -> Any:
    pick = src.get("pick") or {}
    ck = json.dumps([src.get("path"), src.get("params") or {}, pick.get("pages") or 0], sort_keys=True, default=str)
    if ck in cache:
        return cache[ck]
    params = dict(src.get("params") or {})
    if not pick.get("pages"):
        cache[ck] = await api.call("GET", src["path"], params=params)
        return cache[ck]
    # Berhalaman: baca halaman berikutnya sampai semua `ids` ditemukan atau daftar habis (batas teknis).
    ids = {str(i) for i in (pick.get("ids") or [])}
    key, at = pick.get("key") or "id", pick.get("at") or "items"
    acc: List[Any] = []
    for page in range(1, min(int(pick["pages"]), FINGERPRINT_MAX_PAGES) + 1):
        resp = await api.call("GET", src["path"], params={**params, "page": page})
        rows = _at(resp, at) or []
        acc += rows
        if not rows or ids <= {str(r.get(key)) for r in acc if isinstance(r, dict)}:
            break
    out: Dict[str, Any] = {}
    cur = out
    parts = [x for x in at.split(".") if x]
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = acc
    cache[ck] = out
    return out


async def read_fingerprint(api: SelfApi, sources: List[Dict[str, Any]]) -> Tuple[str, List[Any]]:
    """Baca ulang `fingerprint_source` lewat GET → (sidik, potret)."""
    cache: Dict[str, Any] = {}
    snaps = [_pick(await _get(api, s, cache), s.get("pick") or {}) for s in sources or []]
    return fingerprint(snaps), snaps


# ── Pembaca bersama (hanya GET lewat pintu baca-saja) ─────────────────────────────────────────────────────────────────
async def _customer_name(api: SelfApi, customer_id: str) -> str:
    """Nama pelanggan dari pesanan terbarunya di PT aktif (`GET /api/sales-orders`, izin `order.view`); "" bila tidak
    terbaca (tanpa izin / tanpa pesanan)."""
    try:
        res = await api.call("GET", "/api/sales-orders", params={"customer_id": customer_id, "page": 1, "page_size": 1})
    except SelfApiError:
        return ""
    items = (res or {}).get("items") if isinstance(res, dict) else res
    return str(((items or [{}])[0] or {}).get("customer_name") or "")


async def _customer_in_pt(api: SelfApi, customer_id: str) -> str:
    """Golongan A — pelanggan harus punya pesanan di PT aktif (pembacaan berizin `order.view`, cakupan PT dari sesi).
    Mengembalikan nama pelanggan."""
    if not customer_id:
        raise _err(400, "Pelanggan wajib dipilih.")
    res = await api.call("GET", "/api/sales-orders", params={"customer_id": customer_id, "page": 1, "page_size": 1})
    items = (res or {}).get("items") if isinstance(res, dict) else res
    if not items:
        raise _err(404, "Pelanggan ini tidak punya pesanan di PT aktif. Pilih pelanggan dari PT ini.")
    return str(items[0].get("customer_name") or "pelanggan")


async def _order_of(api: SelfApi, order_id: str, customer_id: str) -> Dict[str, Any]:
    o = await api.call("GET", f"/api/sales-orders/{order_id}")
    if str(o.get("customer_id") or "") != customer_id:
        raise _err(400, "Pesanan ini bukan milik pelanggan yang dipilih.")
    return o


async def _open_orders(api: SelfApi, customer_id: str) -> Dict[str, Dict[str, Any]]:
    rows = await api.call("GET", "/api/ar-receipts/open-orders", params={"customer_id": customer_id})
    return {str(r.get("order_id")): r for r in rows or [] if isinstance(r, dict)}


def _allocations(raw: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for a in raw or []:
        if not isinstance(a, dict):
            continue
        oid, amt = _text(a.get("order_id"), 80), _money(a.get("amount"))
        if not oid or amt <= 0:
            raise _err(400, "Setiap alokasi butuh pesanan dan nominal lebih dari 0.")
        if any(x["order_id"] == oid for x in out):
            raise _err(400, "Satu pesanan hanya boleh dialokasi satu kali di kartu.")
        out.append({"order_id": oid, "amount": amt})
    return out


def _alloc_rows(allocs: List[Dict[str, Any]], open_rows: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for a in allocs:
        o = open_rows.get(a["order_id"])
        if not o:
            raise _err(400, "Pesanan yang dialokasi tidak ada di tagihan terbuka pelanggan ini di PT aktif.")
        sisa = _money(o.get("outstanding"))
        if a["amount"] > sisa + 0.005:
            raise _err(400, f"Alokasi ke {o.get('number') or a['order_id']} melebihi sisa tagihannya ({rupiah(sisa)}).")
        rows.append({"label": f"Sisa tagihan {o.get('number') or a['order_id']}", "kind": "money",
                     "before": sisa, "after": round(sisa - a["amount"], 2)})
    return rows


def _row(label: str, before: Any, after: Any, kind: str = "text") -> Dict[str, Any]:
    return {"label": label, "kind": kind, "before": before, "after": after}


# ── Golongan A: tindak lanjut penagihan ───────────────────────────────────────────────────────────────────────────────
async def _followup_common(api: SelfApi, a: Dict[str, Any]) -> Tuple[str, str, List[Dict[str, Any]]]:
    cid = _text(a.get("customer_id"), 80)
    name = await _customer_in_pt(api, cid)
    oid = _text(a.get("order_id"), 80)
    rows = [_row("Pelanggan", "", name)]
    if oid:
        o = await _order_of(api, oid, cid)
        rows.append(_row("Pesanan", "", o.get("number") or oid))
    return cid, name, rows


async def _prep_followup(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    note = _text(a.get("note"))
    if not note:
        raise _err(400, "Tulis catatan tindak lanjut.")
    outcome = a.get("outcome") or "contacted"
    if outcome not in FOLLOWUP_OUTCOMES:
        raise _err(400, "Hasil tindak lanjut tidak dikenal.")
    nxt = _date(a.get("next_action_date"), "Tanggal tindak lanjut berikutnya")
    cid, name, rows = await _followup_common(api, a)
    rows += [_row("Hasil", "—", FOLLOWUP_OUTCOMES[outcome]), _row("Catatan", "—", note)]
    if nxt:
        rows.append(_row("Tindak lanjut berikutnya", "—", nxt, "date"))
    return {"args": {"customer_id": cid, "order_id": _text(a.get("order_id"), 80), "note": note, "outcome": outcome,
                     "next_action_date": nxt},
            "plan": {"summary": f"Catat tindak lanjut penagihan untuk {name}.", "rows": rows, "amount": 0,
                     "confirm_text": "", "meta": {"customer_name": name}},
            "fingerprint_source": []}


async def _prep_promise(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    tgl = _date(a.get("promise_date"), "Tanggal janji bayar", required=True)
    amount = _money(a.get("amount"))
    cid, name, rows = await _followup_common(api, a)
    note = _text(a.get("note")) or (f"Janji bayar {rupiah(amount)} pada {tgl}" if amount > 0 else f"Janji bayar pada {tgl}")
    rows += [_row("Hasil", "—", "Janji bayar"), _row("Tanggal janji bayar", "—", tgl, "date")]
    if amount > 0:
        rows.append(_row("Nominal dijanjikan", None, amount, "money"))
    rows.append(_row("Catatan", "—", note))
    return {"args": {"customer_id": cid, "order_id": _text(a.get("order_id"), 80), "note": note, "outcome": "promised",
                     "next_action_date": tgl},
            "plan": {"summary": f"Catat janji bayar {name} pada {tgl}.", "rows": rows, "amount": 0, "confirm_text": "",
                     "meta": {"customer_name": name}},
            "fingerprint_source": []}


async def _prep_reminder(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    cid, name, rows = await _followup_common(api, a)
    note = _text(a.get("note")) or "Pengingat penagihan dikirim"
    rows += [_row("Status pengingat", "Belum diingatkan", "Sudah diingatkan"), _row("Catatan", "—", note)]
    return {"args": {"customer_id": cid, "order_id": _text(a.get("order_id"), 80), "note": note,
                     "next_action_date": _date(a.get("next_action_date"), "Tanggal tindak lanjut berikutnya")},
            "plan": {"summary": f"Tandai {name} sudah diingatkan.", "rows": rows, "amount": 0, "confirm_text": "",
                     "meta": {"customer_name": name}},
            "fingerprint_source": []}


def _build_followup(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return ({"customer_id": args["customer_id"]},
            {k: args.get(k, "") for k in ("customer_id", "order_id", "note", "outcome", "next_action_date")})


def _build_reminder(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return ({}, {k: args.get(k, "") for k in ("customer_id", "order_id", "note", "next_action_date")})


def _followup_result(label: str) -> ResultOf:
    def _res(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        r = resp if isinstance(resp, dict) else {}
        return {"document": {"type": "collection_followup", "label": label, "id": r.get("id", ""),
                             "number": r.get("customer_name") or (plan.get("meta") or {}).get("customer_name", ""),
                             "link": {"view": "collection-worklist", "tab": "", "focus_type": "customer",
                                      "focus_id": args.get("customer_id", ""), "number": ""}},
                "gl_status": None}
    return _res


# ── Golongan B: kwitansi piutang ──────────────────────────────────────────────────────────────────────────────────────
async def _prep_receipt(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    cid = _text(a.get("customer_id"), 80)
    if not cid:
        raise _err(400, "Pelanggan wajib dipilih.")
    amount = _money(a.get("amount"))
    if amount <= 0:
        raise _err(400, "Nominal kwitansi harus lebih dari 0.")
    allocs = _allocations(a.get("allocations"))
    if not allocs:
        raise _err(400, "Kartu kwitansi butuh minimal satu alokasi ke pesanan.")
    total = round(sum(x["amount"] for x in allocs), 2)
    if total > amount + 0.005:
        raise _err(400, "Total alokasi melebihi nominal kwitansi.")
    method = _text(a.get("method"), 40) or "transfer"
    tgl = _date(a.get("receipt_date"), "Tanggal kwitansi") or _today_wib()
    open_rows = await _open_orders(api, cid)
    rows = _alloc_rows(allocs, open_rows)
    dep = await api.call("GET", "/api/ar-receipts/deposit", params={"customer_id": cid})
    dep_now = _money((dep or {}).get("deposit_balance"))
    sisa = round(amount - total, 2)
    if sisa > 0:
        rows.append(_row("Deposit pelanggan", dep_now, round(dep_now + sisa, 2), "money"))
    rows += [_row("Tanggal kwitansi", "—", tgl, "date"), _row("Cara bayar", "—", METHOD_LABEL.get(method, method))]
    notes = _text(a.get("notes"))
    if notes:
        rows.append(_row("Catatan", "—", notes))
    name = await _customer_name(api, cid)
    out_args = {"customer_id": cid, "amount": amount, "allocations": allocs, "method": method, "receipt_date": tgl,
                "notes": notes}
    if a.get("account_id"):
        out_args["account_id"] = _text(a.get("account_id"), 80)
    return {"args": out_args,
            "plan": {"summary": f"Catat kwitansi {rupiah(amount)}" + (f" dari {name}" if name else "") + ".",
                     "rows": rows, "amount": amount, "confirm_text": confirm_text_of(amount), "note": NOTE_JURNAL,
                     "meta": {"customer_name": name}},
            "fingerprint_source": [
                {"path": "/api/ar-receipts/open-orders", "params": {"customer_id": cid},
                 "pick": {"key": "order_id", "ids": [x["order_id"] for x in allocs], "fields": ["outstanding"]}},
                {"path": "/api/ar-receipts/deposit", "params": {"customer_id": cid},
                 "pick": {"fields": ["deposit_balance"]}}]}


def _build_receipt(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    body = {k: args[k] for k in ("customer_id", "amount", "method", "receipt_date", "notes", "allocations") if k in args}
    if args.get("account_id"):
        body["account_id"] = args["account_id"]
    return {}, body


def _receipt_result(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    from services.doc_refs_service import link_of
    r = resp if isinstance(resp, dict) else {}
    return {"document": {"type": "ar_receipt", "label": "Kwitansi Pelanggan", "id": r.get("id", ""),
                         "number": r.get("number", ""), "link": link_of("ar_receipt", r)},
            "gl_status": r.get("gl_status")}


# ── Golongan B: pencocokan mutasi bank ────────────────────────────────────────────────────────────────────────────────
def _line_label(ln: Dict[str, Any]) -> str:
    d = str(ln.get("stmt_date") or "")[:10]
    desc = _text(ln.get("description"), 60)
    return " · ".join(x for x in (d, desc) if x) or "mutasi bank"


async def _prep_bank_match(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    line_id, txn_id = _text(a.get("line_id"), 80), _text(a.get("txn_id"), 80)
    if not line_id or not txn_id:
        raise _err(400, "Kartu pencocokan butuh mutasi bank dan transaksi kas yang dicocokkan.")
    src_path = f"/api/bank-reconciliation/lines/{line_id}/candidates"
    res = await api.call("GET", src_path, params={"limit": 100})
    ln = (res or {}).get("line") or {}
    if ln.get("status") in ("matched", "ignored", "holding"):
        raise _err(409, "Mutasi bank ini sudah dicocokkan, diabaikan, atau dititipkan.")
    cand = next((c for c in (res or {}).get("candidates") or [] if str(c.get("id")) == txn_id), None)
    if not cand:
        raise _err(400, "Transaksi kas ini bukan kandidat pencocokan untuk mutasi tersebut.")
    amount = _money(ln.get("amount"))
    sisa = _money(cand.get("outstanding"))
    rows = [_row(f"Mutasi {_line_label(ln)}", "Belum cocok", "Cocok"),
            _row("Nominal mutasi", None, amount, "money"),
            _row(f"Sisa belum cocok {cand.get('number') or 'transaksi kas'}", sisa, round(sisa - amount, 2), "money")]
    return {"args": {"line_id": line_id, "txn_id": txn_id},
            "plan": {"summary": f"Cocokkan mutasi {rupiah(amount)} dengan {cand.get('number') or 'transaksi kas'}.",
                     "rows": rows, "amount": amount, "confirm_text": confirm_text_of(amount),
                     "meta": {"line_label": _line_label(ln)}},
            "fingerprint_source": [
                {"path": src_path, "params": {"limit": 100}, "pick": {"at": "line", "fields": ["status", "amount"]}},
                {"path": src_path, "params": {"limit": 100},
                 "pick": {"at": "candidates", "key": "id", "ids": [txn_id], "fields": ["outstanding"]}}]}


def _build_bank_match(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return {"line_id": args["line_id"]}, {"txn_id": args["txn_id"]}


def _bank_link(line_id: str) -> Dict[str, Any]:
    return {"view": "bank-reconciliation", "tab": "", "focus_type": "bank_statement_line", "focus_id": line_id,
            "number": ""}


def _bank_match_result(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    return {"document": {"type": "bank_statement_line", "label": "Pencocokan mutasi bank", "id": args["line_id"],
                         "number": (plan.get("meta") or {}).get("line_label", ""), "link": _bank_link(args["line_id"])},
            "gl_status": None}


# ── Golongan B: alokasi titipan bank ──────────────────────────────────────────────────────────────────────────────────
async def _prep_holding(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    line_id, cid = _text(a.get("line_id"), 80), _text(a.get("customer_id"), 80)
    if not line_id or not cid:
        raise _err(400, "Kartu alokasi titipan butuh baris titipan dan pelanggan.")
    reason = a.get("reason_code") or "identified_customer"
    if reason not in HOLDING_REASONS:
        raise _err(400, "Alasan alokasi titipan tidak dikenal.")
    allocs = _allocations(a.get("allocations"))
    if not allocs:
        raise _err(400, "Kartu alokasi titipan butuh minimal satu alokasi ke pesanan.")
    total = round(sum(x["amount"] for x in allocs), 2)
    hold = await api.call("GET", "/api/bank-reconciliation/holding")
    item = next((it for it in (hold or {}).get("items") or [] if str(it.get("id")) == line_id), None)
    if not item:
        raise _err(404, "Titipan dana ini tidak ditemukan di PT aktif (atau sudah tidak berstatus titipan).")
    remaining = _money(item.get("remaining"))
    if total > remaining + 0.005:
        raise _err(400, f"Total alokasi melebihi sisa titipan ({rupiah(remaining)}).")
    open_rows = await _open_orders(api, cid)
    rows = [_row("Sisa titipan", remaining, round(remaining - total, 2), "money")] + _alloc_rows(allocs, open_rows)
    rows.append(_row("Alasan", "—", HOLDING_REASONS[reason]))
    note = _text(a.get("note"))
    if note:
        rows.append(_row("Catatan", "—", note))
    name = await _customer_name(api, cid)
    return {"args": {"line_id": line_id, "customer_id": cid, "reason_code": reason, "note": note, "allocations": allocs},
            "plan": {"summary": f"Alokasikan titipan {rupiah(total)}" + (f" ke tagihan {name}" if name else "") + ".",
                     "rows": rows, "amount": total, "confirm_text": confirm_text_of(total), "note": NOTE_JURNAL,
                     "meta": {"line_label": _line_label(item), "customer_name": name}},
            "fingerprint_source": [
                {"path": "/api/bank-reconciliation/holding", "params": {},
                 "pick": {"at": "items", "key": "id", "ids": [line_id], "fields": ["remaining"]}},
                {"path": "/api/ar-receipts/open-orders", "params": {"customer_id": cid},
                 "pick": {"key": "order_id", "ids": [x["order_id"] for x in allocs], "fields": ["outstanding"]}}]}


def _build_holding(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return ({"line_id": args["line_id"]},
            {k: args[k] for k in ("customer_id", "reason_code", "note", "allocations")})


def _holding_result(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    r = resp if isinstance(resp, dict) else {}
    mine = [it for it in r.get("holding_allocated") or [] if it.get("ai_card_id") and it.get("ai_card_id") == r.get("_card")]
    gl = None
    items = mine or [it for it in r.get("holding_allocated") or [] if it.get("status") in ("applied", "done")]
    if items:
        gl = "failed" if any(it.get("gl_status") == "failed" for it in items) else "posted"
    return {"document": {"type": "bank_statement_line", "label": "Alokasi titipan bank", "id": args["line_id"],
                         "number": (plan.get("meta") or {}).get("line_label", ""), "link": _bank_link(args["line_id"])},
            "gl_status": gl}


# ── Golongan B: ulang jurnal yang gagal ───────────────────────────────────────────────────────────────────────────────
async def _prep_retry(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    kind, doc_id = _text(a.get("kind"), 60), _text(a.get("doc_id"), 120)
    if not kind or not doc_id:
        raise _err(400, "Kartu ulang jurnal butuh jenis dan dokumen yang gagal.")
    src = {"path": "/api/finance/posting-failures", "params": {"kind": kind, "page_size": 200},
           "pick": {"at": "items", "key": "id", "ids": [doc_id], "fields": ["number", "amount", "error"],
                    "pages": FINGERPRINT_MAX_PAGES}}
    got = await _get(api, src, {})
    row = next((r for r in _at(got, "items") or [] if str(r.get("id")) == doc_id), None)
    if not row:
        raise _err(404, "Dokumen ini tidak ada di daftar Posting Gagal PT aktif (mungkin sudah terposting).")
    label = row.get("kind_label") or "Dokumen"
    rows = [_row(f"{label} {row.get('number') or ''}".strip(), "Jurnal gagal", "Diulang"),
            _row("Galat terakhir", _text(row.get("error"), 200) or "—", "—")]
    amount = _money(row.get("amount"))
    if amount:
        rows.append(_row("Nominal dokumen", None, amount, "money"))
    return {"args": {"kind": kind, "doc_id": doc_id},
            "plan": {"summary": f"Ulang jurnal {label} {row.get('number') or ''}".strip() + ".", "rows": rows,
                     "amount": amount, "confirm_text": confirm_text_of(amount) if amount else "",
                     "meta": {"kind_label": label, "number": row.get("number") or "", "link": row.get("link") or {}}},
            "fingerprint_source": [src]}


def _build_retry(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return {"kind": args["kind"], "doc_id": args["doc_id"]}, None


def _retry_result(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    r = resp if isinstance(resp, dict) else {}
    meta = plan.get("meta") or {}
    return {"document": {"type": args["kind"], "label": meta.get("kind_label") or "Dokumen", "id": args["doc_id"],
                         "number": meta.get("number") or "", "link": meta.get("link") or {}},
            "gl_status": r.get("gl_status")}


_EDIT_RECEIPT = ({"path": "receipt_date", "label": "Tanggal", "kind": "date"},
                 {"path": "method", "label": "Cara bayar", "kind": "text"},
                 {"path": "notes", "label": "Catatan", "kind": "text"})

for _a in (
    CardAction("followup_note", "Catat tindak lanjut penagihan", "A", "low", "POST",
               "/api/customers/{customer_id}/followups", _prep_followup, _build_followup,
               _followup_result("Tindak lanjut penagihan")),
    CardAction("payment_promise", "Catat janji bayar", "A", "low", "POST",
               "/api/customers/{customer_id}/followups", _prep_promise, _build_followup, _followup_result("Janji bayar")),
    CardAction("collection_reminder", "Tandai sudah diingatkan", "A", "low", "POST", "/api/collection-reminders/mark",
               _prep_reminder, _build_reminder, _followup_result("Pengingat penagihan")),
    CardAction("ar_receipt_create", "Catat kwitansi piutang", "B", "high", "POST", "/api/ar-receipts",
               _prep_receipt, _build_receipt, _receipt_result, _EDIT_RECEIPT),
    CardAction("bank_match", "Cocokkan mutasi bank", "B", "low", "POST",
               "/api/bank-reconciliation/lines/{line_id}/match", _prep_bank_match, _build_bank_match, _bank_match_result),
    CardAction("holding_allocate", "Alokasikan titipan bank", "B", "low", "POST",
               "/api/bank-reconciliation/lines/{line_id}/holding/allocate", _prep_holding, _build_holding,
               _holding_result),
    CardAction("posting_retry", "Ulang jurnal yang gagal", "B", "low", "POST",
               "/api/finance/posting-failures/{kind}/{doc_id}/retry", _prep_retry, _build_retry, _retry_result),
):
    REGISTRY[_a.code] = _a
#: `attach_proof` (lampirkan bukti) TIDAK dibuka: belum ada endpoint lampiran kwitansi/tindak lanjut (spesifikasi
#: butir 8). Kode di luar REGISTRY dijawab alasan daftar larangan (AG-T5) atau `MSG_TIDAK_DIKENAL`.


# ── Golongan C (AG-T5): bayar tagihan pemasok, bayar kontrabon, kas manual ─────────────────────────────────────────────
def _same_pt(api: SelfApi, doc: Dict[str, Any], what: str) -> None:
    if str(doc.get("entity_id") or "") != api.entity_header:
        raise _err(400, f"{what} ini bukan milik PT aktif.")


async def _source_account(api: SelfApi, kind: str, target_id: str, account_id: str) -> Dict[str, Any]:
    """Rekening sumber pembayaran = rekening AKTIF milik PT dokumen (= PT kartu), dibaca dari pintu layar bayar
    (`GET /api/ap-payments/accounts`, izin bayar yang sama dengan pintunya)."""
    if not account_id:
        raise _err(400, "Pilih rekening sumber pembayaran.")
    rows = await api.call("GET", "/api/ap-payments/accounts", params={"kind": kind, "target_id": target_id})
    acc = next((r for r in rows or [] if isinstance(r, dict) and str(r.get("id")) == account_id), None)
    if not acc:
        raise _err(400, MSG_REKENING)
    return acc


def _acc_label(acc: Dict[str, Any]) -> str:
    return " · ".join(x for x in (_text(acc.get("name"), 80), _text(acc.get("account_number"), 40)) if x) or "rekening"


def _pay_common(a: Dict[str, Any]) -> Tuple[float, str, str, str, str]:
    amount = _money(a.get("amount"))
    if amount <= 0:
        raise _err(400, "Nominal pembayaran harus lebih dari 0.")
    paid_at = _date(a.get("paid_at"), "Tanggal bayar") or _today_wib()
    method = _text(a.get("method"), 40) or "transfer"
    return amount, _text(a.get("bank_account_id"), 80), paid_at, method, _text(a.get("notes"))


def _pay_rows(acc: Dict[str, Any], paid_at: str, method: str, notes: str) -> List[Dict[str, Any]]:
    rows = [_row("Rekening sumber", "—", _acc_label(acc)), _row("Tanggal bayar", "—", paid_at, "date"),
            _row("Cara bayar", "—", METHOD_LABEL.get(method, method))]
    if notes:
        rows.append(_row("Catatan", "—", notes))
    return rows


async def _prep_bill_pay(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    bid = _text(a.get("bill_id"), 80)
    if not bid:
        raise _err(400, "Tagihan pemasok wajib dipilih.")
    amount, rek, paid_at, method, notes = _pay_common(a)
    bill = await api.call("GET", f"/api/vendor-bills/{bid}")
    _same_pt(api, bill, "Tagihan pemasok")
    num = bill.get("bill_number") or bid
    if bill.get("status") != "posted":
        raise _err(409, f"Tagihan {num} belum bisa dibayar: hanya tagihan terposting yang belum lunas.")
    sisa = _money((bill.get("financials") or {}).get("outstanding"))
    if amount > sisa + 0.005:
        raise _err(400, f"Nominal melebihi sisa hutang {num} ({rupiah(sisa)}). Kartu asisten tidak memutus selisih "
                        "pembayaran; lakukan di layar Tagihan Pemasok.")
    acc = await _source_account(api, "vendor_bill", bid, rek)
    supplier = _text(bill.get("supplier_name"), 120)
    rows = [_row(f"Sisa hutang {num}", sisa, round(sisa - amount, 2), "money"), _row("Pemasok", "", supplier)]
    rows += _pay_rows(acc, paid_at, method, notes)
    return {"args": {"bill_id": bid, "amount": amount, "bank_account_id": rek, "paid_at": paid_at, "method": method,
                     "notes": notes},
            "plan": {"summary": f"Bayar {rupiah(amount)} untuk tagihan {num}" + (f" ({supplier})" if supplier else "")
                                + ".", "rows": rows, "amount": amount, "confirm_text": confirm_text_of(amount),
                     "note": NOTE_JURNAL, "meta": {"number": num, "supplier_name": supplier}},
            "fingerprint_source": [{"path": f"/api/vendor-bills/{bid}", "params": {},
                                    "pick": {"fields": ["status", "financials"]}}]}


def _build_pay(key: str) -> BuildRequest:
    def _b(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
        return ({key: args[key]},
                {k: args.get(k, "") for k in ("amount", "bank_account_id", "paid_at", "method", "notes")})
    return _b


def _pay_result(doc_type: str, label: str, key: str) -> ResultOf:
    def _res(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
        from services.doc_refs_service import link_of
        r = resp if isinstance(resp, dict) else {}
        num = r.get("bill_number") or r.get("number") or (plan.get("meta") or {}).get("number", "")
        return {"document": {"type": doc_type, "label": label, "id": args[key], "number": num,
                             "link": link_of(doc_type, {**r, "id": r.get("id") or args[key]})},
                "gl_status": (r.get("payment_intent") or {}).get("gl_status")}
    return _res


async def _prep_cb_pay(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    cbid = _text(a.get("cb_id"), 80)
    if not cbid:
        raise _err(400, "Kontrabon wajib dipilih.")
    cb = await api.call("GET", f"/api/contra-bons/{cbid}")
    _same_pt(api, cb, "Kontrabon")
    num = cb.get("number") or cbid
    totals = cb.get("totals")
    if not isinstance(totals, dict) or totals.get("outstanding") is None:
        raise denied([("vendor_bill", "view")])   # nilai kontrabon disembunyikan bagi yang tidak boleh melihat nominal
    sisa = _money(totals.get("outstanding"))
    if not a.get("amount"):
        a["amount"] = sisa
    amount, rek, paid_at, method, notes = _pay_common(a)
    if cb.get("status") not in ("verified", "approved", "scheduled_payment"):
        raise _err(409, f"Kontrabon {num} belum bisa dibayar ({cb.get('status_label') or 'belum disetujui'}).")
    if amount > sisa + 0.005:
        raise _err(400, f"Nominal melebihi sisa kontrabon {num} ({rupiah(sisa)}).")
    acc = await _source_account(api, "contra_bon", cbid, rek)
    supplier = _text(cb.get("supplier_name"), 120)
    rows = [_row(f"Sisa kontrabon {num}", sisa, round(sisa - amount, 2), "money"), _row("Pemasok", "", supplier),
            _row("Faktur di kontrabon", "", str(len(cb.get("bills") or [])))]
    rows += _pay_rows(acc, paid_at, method, notes)
    return {"args": {"cb_id": cbid, "amount": amount, "bank_account_id": rek, "paid_at": paid_at, "method": method,
                     "notes": notes},
            "plan": {"summary": f"Bayar {rupiah(amount)} untuk kontrabon {num}" + (f" ({supplier})" if supplier else "")
                                + ".", "rows": rows, "amount": amount, "confirm_text": confirm_text_of(amount),
                     "note": NOTE_JURNAL, "meta": {"number": num, "supplier_name": supplier}},
            "fingerprint_source": [{"path": f"/api/contra-bons/{cbid}", "params": {},
                                    "pick": {"fields": ["status", "totals"]}}]}


CASH_DIRECTION_LABEL = {"out": "Kas keluar", "in": "Kas masuk"}


async def _prep_cash_manual(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    from services.bank_service import account_cash_type
    a = _clean_args(args)
    acc_id = _text(a.get("account_id"), 80)
    if not acc_id:
        raise _err(400, "Pilih rekening kas/bank untuk transaksi ini.")
    direction = _text(a.get("direction"), 8) or "out"
    if direction not in CASH_DIRECTION_LABEL:
        raise _err(400, "Arah kas harus keluar atau masuk.")
    amount = _money(a.get("amount"))
    if amount <= 0:
        raise _err(400, "Nominal kas harus lebih dari 0.")
    category, desc = _text(a.get("category"), 80), _text(a.get("description"))
    tgl = _date(a.get("txn_date"), "Tanggal transaksi") or _today_wib()
    accs = await api.call("GET", "/api/bank-accounts")
    acc = next((x for x in accs or [] if isinstance(x, dict) and str(x.get("id")) == acc_id), None)
    if not acc or str(acc.get("entity_id") or "") != api.entity_header or acc.get("is_active") is False:
        raise _err(400, MSG_REKENING_KAS)
    saldo = _money(acc.get("balance"))
    after = round(saldo - amount if direction == "out" else saldo + amount, 2)
    rows = [_row(f"Saldo {_acc_label(acc)}", saldo, after, "money"),
            _row("Arah", "—", CASH_DIRECTION_LABEL[direction]), _row("Kategori", "—", category or "—"),
            _row("Keterangan", "—", desc or "—"), _row("Tanggal transaksi", "—", tgl, "date")]
    return {"args": {"account_id": acc_id, "cash_type": account_cash_type(acc), "direction": direction,
                     "amount": amount, "category": category, "description": desc, "txn_date": tgl},
            "plan": {"summary": f"{CASH_DIRECTION_LABEL[direction]} {rupiah(amount)} di {_acc_label(acc)}"
                                + (f" untuk {category}" if category else "") + ".",
                     "rows": rows, "amount": amount, "confirm_text": confirm_text_of(amount), "note": NOTE_JURNAL,
                     "meta": {"account": _acc_label(acc)}},
            "fingerprint_source": [{"path": "/api/bank-accounts", "params": {},
                                    "pick": {"key": "id", "ids": [acc_id],
                                             "fields": ["is_active", "entity_id", "cash_type"]}}]}


def _build_cash(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return {}, {k: args.get(k, "") for k in ("account_id", "cash_type", "direction", "amount", "category",
                                             "description", "txn_date")}


def _cash_result(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    from services.doc_refs_service import link_of
    r = resp if isinstance(resp, dict) else {}
    return {"document": {"type": "cash_transaction", "label": "Transaksi Kas", "id": r.get("id", ""),
                         "number": r.get("number", ""), "link": link_of("cash_transaction", r)},
            "gl_status": r.get("gl_status")}


for _a in (
    CardAction("vendor_bill_pay", "Bayar tagihan pemasok", "C", "high", "POST", "/api/vendor-bills/{bill_id}/pay",
               _prep_bill_pay, _build_pay("bill_id"), _pay_result("vendor_bill", "Tagihan Pemasok", "bill_id"),
               door=("vendor_bill", "pay"), card_perm="pay"),
    CardAction("contra_bon_pay", "Bayar kontrabon", "C", "high", "POST", "/api/contra-bons/{cb_id}/pay",
               _prep_cb_pay, _build_pay("cb_id"), _pay_result("contra_bon", "Kontrabon", "cb_id"),
               door=("contra_bon", "pay"), card_perm="pay"),
    CardAction("cash_manual", "Catat kas manual", "C", "high", "POST", "/api/cash-transactions",
               _prep_cash_manual, _build_cash, _cash_result, door=("cash", "create"), card_perm="pay"),
):
    REGISTRY[_a.code] = _a

# ── Golongan C (AG-T5 b): jurnal manual, balik jurnal ───────────────────────────────────────────────────────────────
def _ribuan(v: float) -> str:
    """100000 → "100.000" (pesan jurnal tidak seimbang, tanpa "Rp")."""
    a = round(float(v or 0), 2)
    t = f"{abs(a):,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return ("-" if a < 0 else "") + (t[:-3] if t.endswith(",00") else t)


async def _nama_akun(api: SelfApi) -> Dict[str, str]:
    """Nama akun untuk tampilan rencana (bagan akun PT aktif); tidak terbaca → kode saja. Akun TIDAK dipilih di sini."""
    try:
        rows = await api.call("GET", "/api/gl/accounts")
    except SelfApiError:
        return {}
    return {str(r.get("code")): str(r.get("name") or "") for r in rows or [] if isinstance(r, dict)}


async def _prep_journal(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    """Jurnal manual: total debit & kredit dihitung di sini (tidak seimbang → ditolak); akun dari permintaan pengguna dan
    diperiksa PINTU (periode, akun aktif, akun kontrol PK-36 / K-02)."""
    a = _clean_args(args)
    lines = []
    for ln in a.get("lines") or []:
        if not isinstance(ln, dict):
            continue
        code = _text(ln.get("account_code"), 40)
        d, k = _money(ln.get("debit")), _money(ln.get("credit"))
        if not code:
            raise _err(400, "Setiap baris jurnal harus memilih akun.")
        if d < 0 or k < 0 or (d > 0 and k > 0) or (d == 0 and k == 0):
            raise _err(400, "Setiap baris jurnal berisi debit ATAU kredit lebih dari 0.")
        lines.append({"account_code": code, "debit": d, "credit": k, "description": _text(ln.get("description"), 200)})
    if len(lines) < 2:
        raise _err(400, "Jurnal minimal 2 baris (debit & kredit).")
    total_d = round(sum(x["debit"] for x in lines), 2)
    total_k = round(sum(x["credit"] for x in lines), 2)
    if round(total_d * 100) != round(total_k * 100):
        raise _err(400, f"Jurnal tidak seimbang: debit {_ribuan(total_d)} ≠ kredit {_ribuan(total_k)}.")
    tgl = _date(a.get("date"), "Tanggal jurnal") or _today_wib()
    desc = _text(a.get("description")) or "Jurnal manual"
    nama = await _nama_akun(api)
    rows = [_row(f"{'Debit' if x['debit'] else 'Kredit'} {x['account_code']} {nama.get(x['account_code'], '')}".strip(),
                 None, x["debit"] or x["credit"], "money") for x in lines]
    rows += [_row("Total debit = total kredit", None, total_d, "money"), _row("Tanggal jurnal", "—", tgl, "date"),
             _row("Keterangan", "—", desc)]
    return {"args": {"date": tgl, "description": desc, "lines": lines},
            "plan": {"summary": f"Catat jurnal manual {rupiah(total_d)}: {desc}.", "rows": rows, "amount": total_d,
                     "confirm_text": confirm_text_of(total_d),
                     "note": "Akun diperiksa pintu jurnal: periode terbuka, akun aktif, bukan akun kontrol.",
                     "meta": {"description": desc}},
            "fingerprint_source": []}


def _build_journal(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return {}, {"date": args.get("date", ""), "description": args.get("description", ""),
                "lines": [dict(x) for x in args.get("lines") or []]}


def _journal_result(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    from services.doc_refs_service import link_of
    r = resp if isinstance(resp, dict) else {}
    if r.get("status") == "menunggu_orang_kedua":   # KF-T6 — pintu jurnal sendiri menuntut dua orang (202)
        return {"document": {"type": "journal_proposal", "label": "Usulan jurnal manual", "id": r.get("proposal_id", ""),
                             "number": "", "link": {"view": "general-ledger", "tab": "", "focus_type": "", "focus_id": "",
                                                    "number": ""}},
                "gl_status": None, "message": MSG_JURNAL_USULAN}
    return {"document": {"type": "journal_entry", "label": "Jurnal", "id": r.get("id", ""), "number": r.get("number", ""),
                         "link": link_of("journal_entry", r)},
            "gl_status": "posted" if r.get("status") == "posted" else r.get("status")}


async def _prep_reverse(api: SelfApi, args: Dict[str, Any]) -> Dict[str, Any]:
    a = _clean_args(args)
    eid = _text(a.get("entry_id"), 80)
    if not eid:
        raise _err(400, "Jurnal yang dibalik wajib dipilih.")
    reason = _text(a.get("reason"))
    if len(reason) < 5:
        raise _err(400, "Alasan pembalikan wajib diisi (minimal 5 huruf).")
    tgl = _date(a.get("date"), "Tanggal pembalik") or _today_wib()
    je = await api.call("GET", f"/api/gl/journal/{eid}")
    _same_pt(api, je, "Jurnal")
    num = je.get("number") or eid
    if je.get("status") == "void":
        raise _err(409, f"Jurnal {num} sudah dianulir — tidak bisa dibalik.")
    if je.get("reversed") or je.get("reversed_by_entry_id"):
        raise _err(409, f"Jurnal {num} sudah dibalik.")
    total = _money(je.get("total_debit"))
    rows = [_row(f"Jurnal {num}", "Terposting", "Dibalik"), _row("Nilai jurnal", None, total, "money"),
            _row("Tanggal pembalik", "—", tgl, "date"), _row("Alasan pembalikan", "—", reason)]
    return {"args": {"entry_id": eid, "date": tgl, "reason": reason},
            "plan": {"summary": f"Balik jurnal {num} ({rupiah(total)}) bertanggal {tgl}.", "rows": rows, "amount": total,
                     "confirm_text": num, "note": "Jurnal asal tetap; jurnal pembalik menukar debit dan kredit.",
                     "meta": {"number": num}},
            "fingerprint_source": [{"path": f"/api/gl/journal/{eid}", "params": {},
                                    "pick": {"fields": ["status", "reversed", "reversed_by_entry_id", "total_debit"]}}]}


def _build_reverse(args: Dict[str, Any], plan: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    return {"entry_id": args["entry_id"]}, {"date": args.get("date", ""), "reason": args.get("reason", "")}


def _reverse_result(resp: Any, args: Dict[str, Any], plan: Dict[str, Any]) -> Dict[str, Any]:
    from services.doc_refs_service import link_of
    r = resp if isinstance(resp, dict) else {}
    return {"document": {"type": "journal_entry", "label": "Jurnal pembalik", "id": r.get("id", ""),
                         "number": r.get("number", ""), "link": link_of("journal_entry", r)},
            "gl_status": "posted" if r.get("status") == "posted" else r.get("status")}


for _a in (
    CardAction("journal_manual", "Catat jurnal manual", "C", "high", "POST", "/api/gl/journal",
               _prep_journal, _build_journal, _journal_result, door=("accounting", "create"), card_perm="post"),
    CardAction("journal_reverse", "Balik jurnal", "C", "high", "POST", "/api/gl/journal/{entry_id}/reverse",
               _prep_reverse, _build_reverse, _reverse_result, door=("accounting", "void"), card_perm="post",
               retype_kind="text"),
):
    REGISTRY[_a.code] = _a

# AG-T5 — penegakan 2 daftar larangan: pintu tulis terdaftar tidak boleh terlarang dan wajib ber-idempotensi.
from services.ai_card_rules import check_write_paths as _cek_pintu  # noqa: E402

_cek_pintu([(x.code, x.write_method, x.write_path) for x in REGISTRY.values()]
           + [("draf_po", m, p) for m, p in LEGACY_WRITE_PATHS])


# ── Sakelar & batas ───────────────────────────────────────────────────────────────────────────────────────────────────
async def _nama_pt(entity_id: str) -> str:
    from services.ai_actions import _nama_pt as nama
    return await nama(entity_id)


async def _sakelar_b(user: Dict[str, Any], entity_id: str) -> None:
    """Golongan B: izin `ai_finance.create` → golongan `B` di akun → `ai.tindakan_uang_masuk` menyala untuk PT kartu."""
    if not await has_permission(user, "ai_finance", "create"):
        raise denied([("ai_finance", "create")], MSG_IZIN_B)
    if "B" not in list(((user.get("ai_finance") or {}).get("classes")) or []):
        raise _err(403, MSG_AKUN_MATI)
    if not await value_of(KUNCI_UANG_MASUK, {"entity_id": entity_id}):
        raise _err(409, f"Tindakan uang masuk lewat asisten belum dinyalakan untuk {await _nama_pt(entity_id)}.")


def _classes(user: Dict[str, Any]) -> List[str]:
    return list(((user.get("ai_finance") or {}).get("classes")) or [])


async def _sakelar_pt_c(entity_id: str) -> None:
    if not await value_of("ai.tindakan_uang_keluar", {"entity_id": entity_id}):
        raise _err(409, f"Tindakan uang keluar dan jurnal lewat asisten belum dinyalakan untuk "
                        f"{await _nama_pt(entity_id)}.")


async def _sakelar_c(user: Dict[str, Any], entity_id: str, action: "CardAction") -> None:
    """AG-T5 — golongan C: izin kartu (`ai_finance.pay` untuk tiga tindakan uang, `ai_finance.post` untuk dua tindakan
    jurnal) → golongan `C` di akun → `ai.tindakan_uang_keluar` menyala untuk PT kartu (bawaan mati, H5)."""
    if action.card_perm == "post":
        if not await has_permission(user, "ai_finance", "post"):
            raise denied([("ai_finance", "post")], MSG_IZIN_C_POST)
    elif not await has_permission(user, "ai_finance", "pay"):
        raise denied([("ai_finance", "pay")], MSG_IZIN_C_PAY)
    if "C" not in _classes(user):
        raise _err(403, MSG_AKUN_MATI_C)
    await _sakelar_pt_c(entity_id)


async def _batas_harian(user: Dict[str, Any], entity_id: str) -> None:
    """Batas `ai.tindakan_maks_per_hari` (PT kartu): dihitung dari kartu `confirmed` pengguna sejak 00.00 WIB."""
    n = int(await value_of(KUNCI_MAKS_HARIAN, {"entity_id": entity_id}) or 0)
    if n <= 0:
        return
    from services.analytics_time import now_wib, wib_midnight_utc
    awal = wib_midnight_utc(now_wib().date())
    done = await db.ai_action_proposals.count_documents(
        {"user_id": user["id"], "status": "confirmed", "confirmed_at": {"$gte": awal}})
    if done >= n:
        raise _err(409, MSG_BATAS.format(n=n))


async def _finance_gate(user: Dict[str, Any]) -> None:
    """Kartu disiapkan di Asisten Keuangan: izin `ai_finance.view` + sakelar akun menyala (AG-T2, K-45)."""
    from routers.ai_analytics import _DENY_FIN, _OFF_FIN
    if not await has_permission(user, "ai_finance", "view"):
        raise denied([("ai_finance", "view")], _DENY_FIN)
    if not (user.get("ai_finance") or {}).get("enabled"):
        raise _err(403, _OFF_FIN)


def _token_of(request: Any = None, api: Optional[SelfApi] = None) -> str:
    if api is not None and getattr(api, "token", ""):
        return api.token
    if request is not None:
        from dependencies import extract_token
        return extract_token(request)
    return ""


def _reader(token: str, entity_id: str) -> SelfApi:
    return SelfApi(None, token=token, entity_header=entity_id, read_only=True)


async def _run_prepare(action: CardAction, token: str, entity_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    api = _reader(token, entity_id)
    try:
        out = await action.prepare(api, args)
        fp, snaps = await read_fingerprint(api, out.get("fingerprint_source") or [])
    except SelfApiError as exc:
        raise _err(exc.status if exc.status in (400, 403, 404, 409) else 400, exc.message)
    finally:
        await api.aclose()
    return {**out, "fingerprint": fp, "snapshot": snaps}


# ── Satu kartu pending per percakapan ─────────────────────────────────────────────────────────────────────────────────
async def supersede_pending(session_id: str, user_id: str, new_card_id: str) -> int:
    if not session_id:
        return 0
    now = now_iso()
    res = await db.ai_action_proposals.update_many(
        {"session_id": session_id, "user_id": user_id, "status": "pending", "id": {"$ne": new_card_id}},
        {"$set": {"status": "superseded", "superseded_by": new_card_id, "finished_at": now, "updated_at": now}})
    return int(res.modified_count or 0)


async def insert_card(doc: Dict[str, Any]) -> None:
    """Tandai kartu `pending` lain di percakapan yang sama `superseded`, lalu sisip. Indeks `uq_pending_session` (A):
    dua penyiapan bersamaan → yang kalah diulang sekali."""
    from pymongo.errors import DuplicateKeyError
    for attempt in range(2):
        await supersede_pending(doc.get("session_id") or "", doc["user_id"], doc["id"])
        try:
            await db.ai_action_proposals.insert_one(dict(doc))
            return
        except DuplicateKeyError:
            if attempt:
                raise _err(409, MSG_SEDANG_DISIAPKAN)


# ── prepare ───────────────────────────────────────────────────────────────────────────────────────────────────────────
async def prepare(code: str, args: Dict[str, Any], *, request: Any = None, api: Optional[SelfApi] = None,
                  user: Dict[str, Any], ctx: Any, session_id: str = "", user_request: str = "") -> Dict[str, Any]:
    action = REGISTRY.get(str(code or ""))
    if action is None:
        # AG-T5 — penegakan 3: permintaan yang cocok dengan daftar larangan dijawab alasan barisnya.
        from services.ai_card_rules import reason_for_action
        raise _err(400, reason_for_action(str(code or ""), args if isinstance(args, dict) else {}) or MSG_TIDAK_DIKENAL)
    if getattr(ctx, "view_all", False) or ctx.active_entity_id in ("", "all"):
        raise _err(400, MSG_SEMUA_PT)
    if _has_entity_key(args):
        raise _err(400, ENTITY_MESSAGE)
    await _finance_gate(user)
    entity_id = ctx.active_entity_id
    if action.cls == "B":
        await _sakelar_b(user, entity_id)
    elif action.cls == "C":
        await _sakelar_c(user, entity_id, action)
    token = _token_of(request, api)
    out = await _run_prepare(action, token, entity_id, args if isinstance(args, dict) else {})
    jam = int(await value_of(KUNCI_MASA_BERLAKU, {"entity_id": entity_id}))
    dibuat = datetime.now(timezone.utc)
    cid = new_id("aiact")
    doc = {"id": cid, "type": action.code, "class": action.cls, "risk": action.risk, "status": "pending",
           "title": action.label, "request": _text(user_request), "args": out["args"],
           "args_initial": json.loads(json.dumps(out["args"], default=str)),
           "editable": [dict(e) for e in action.editable], "plan": out["plan"], "retype_kind": action.retype_kind,
           "fingerprint": out["fingerprint"], "fingerprint_source": out.get("fingerprint_source") or [],
           "fingerprint_snapshot": out["snapshot"], "reason": "", "edits": {},
           "user_id": user["id"], "user_name": user.get("name", ""), "entity_id": entity_id,
           "session_id": session_id or "", "created_at": dibuat.isoformat(), "updated_at": dibuat.isoformat(),
           "expires_at": (dibuat + timedelta(hours=jam)).isoformat()}
    await insert_card(doc)
    await audit(user.get("name", ""), "ai_card_prepared", "ai_action_proposals", cid,
                {"type": action.code, "amount": out["plan"].get("amount", 0)}, scope_entity_id=entity_id)
    return await decorate({**doc, "entity_name": await _nama_pt(entity_id)}, user, ctx)


def tool_result(card: Dict[str, Any]) -> Dict[str, Any]:
    """Hasil alat `prepare_action` untuk model: ringkasan rencana + blok kartu; tanpa jalur untuk menyetujui."""
    plan = card.get("plan") or {}
    # K-43 — nama pihak tidak ikut dikirim ke penyedia model: hanya baris nominal (label nomor dokumen) dan totalnya.
    rows = [{k: r.get(k) for k in ("label", "before", "after")} for r in plan.get("rows") or [] if r.get("kind") == "money"]
    return {"proposal_id": card["id"], "action": card["type"], "title": card.get("title", ""), "status": card["status"],
            "rows": rows, "amount": plan.get("amount", 0),
            "instruction": ("Kartu menunggu persetujuan pengguna di layar. Sisipkan blok ```kn-action\n"
                            f"{{\"proposal_id\": \"{card['id']}\"}}\n``` dan jangan menyatakan tindakan sudah dijalankan.")}


# ── decide ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def status_conflict(status: str) -> HTTPException:
    return _err(409, MSG_STATUS.get(status) or "Kartu ini sudah diproses.")


async def _load(card_id: str, user: Dict[str, Any]) -> Dict[str, Any]:
    from services.ai_actions import load
    doc = await load(card_id, user)
    if doc.get("user_id") != user["id"]:
        raise _err(403, MSG_PEMBUAT)
    return doc


async def _finish(card_id: str, status: str, **fields: Any) -> Dict[str, Any]:
    now = now_iso()
    upd = {"status": status, "finished_at": now, "updated_at": now, **fields}
    if status == "confirmed":
        upd["confirmed_at"] = now
    await db.ai_action_proposals.update_one({"id": card_id, "status": "running"}, {"$set": upd})
    return upd


async def is_card(card_id: str) -> bool:
    d = await db.ai_action_proposals.find_one({"id": card_id}, {"_id": 0, "type": 1})
    return bool(d) and d.get("type") in REGISTRY


async def dismiss(card_id: str, *, user: Dict[str, Any], reason: str = "") -> Dict[str, Any]:
    """Pembuat mengabaikan kartunya: `pending` (AG-T3), juga `awaiting_second` (AG-T5 — menarik kartu yang menunggu
    orang kedua)."""
    doc = await _load(card_id, user)
    if doc["status"] not in ("pending", "awaiting_second"):
        raise status_conflict(doc["status"])
    now = now_iso()
    upd = {"status": "dismissed", "reason": _text(reason) or doc.get("reason", ""), "finished_at": now,
           "updated_at": now, "decided_by": {"id": user["id"], "name": user.get("name", "")}, "decided_at": now}
    res = await db.ai_action_proposals.update_one({"id": card_id, "status": doc["status"]}, {"$set": upd})
    if not res.modified_count:
        fresh = await db.ai_action_proposals.find_one({"id": card_id}, {"_id": 0}) or doc
        raise status_conflict(fresh.get("status", ""))
    await audit(user.get("name", ""), "ai_card_dismissed", "ai_action_proposals", card_id, {"type": doc["type"]},
                scope_entity_id=doc.get("entity_id", ""))
    return {**doc, **upd}


async def _write(token: str, entity_id: str, card_id: str, method: str, path: str, body: Any,
                 card_class: str = "") -> Tuple[int, Any, str]:
    """SATU panggilan tulis (kunci = id kartu). Putus koneksi / batas waktu → ulang satu kali dengan kunci yang sama.
    Mengembalikan (kode, jawaban, kode galat kartu: "" | "door" | "uncertain"). AG-T5 — `card_class` diteruskan ke
    `SelfApi` (golongan C: daftar larangan diperiksa sebelum mengirim)."""
    api = SelfApi(None, token=token, entity_header=entity_id, read_only=False, card_id=card_id, card_class=card_class)
    try:
        for attempt in range(2):
            try:
                resp = await api.call(method, path, json=body, idempotency_key=card_id)
                return api.last_status or 200, resp, ""
            except SelfApiError as exc:
                if exc.status == 409 and "IDEMPOTENT_IN_PROGRESS" in exc.message:
                    return exc.status, {"message": MSG_TIDAK_PASTI}, "uncertain"
                return exc.status, {"message": exc.message}, "uncertain" if exc.status >= 500 else "door"
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt:
                    return 0, {"message": MSG_TIDAK_PASTI}, "uncertain"
            except Exception as exc:  # noqa: BLE001 — galat di dalam pintu (500): hasil tidak pasti, tidak diulang
                return 500, {"message": f"{MSG_TIDAK_PASTI} ({str(exc)[:200]})"}, "uncertain"
        return 0, {"message": MSG_TIDAK_PASTI}, "uncertain"
    finally:
        await api.aclose()


def _who(user: Dict[str, Any]) -> Dict[str, str]:
    return {"id": user["id"], "name": user.get("name", "")}


async def _basis_kedua(entity_id: str) -> str:
    """D3 — dasar keputusan "butuh orang kedua": aturan jumlah orang ("2") atau batas nominal."""
    from config_catalog_kontrol import kunci_min_orang
    return "min_orang" if str(await value_of(kunci_min_orang("asisten_uang_keluar"), {"entity_id": entity_id})
                              ).strip() == "2" else "batas_nominal"


async def _beri_tahu_orang_kedua(doc: Dict[str, Any], maker: Dict[str, Any]) -> int:
    """Satu notifikasi ke tiap pengguna yang memegang `ai_finance.approve`, bertugas di PT kartu, golongan `C` menyala
    di akunnya, dan bukan pembuat. Alamat per orang (`notification_audience`), tanpa siaran per peran."""
    from services.notification_audience import resolve_recipients
    from services.notification_service import create_notification
    eid = doc.get("entity_id") or ""
    calon = [u for u in await resolve_recipients(permission=("ai_finance", "approve"), entity_id=eid)
             if str(u.get("id")) != maker["id"]]
    if not calon:
        return 0
    kelas = {u["id"]: _classes(u) async for u in db.users.find(
        {"id": {"$in": [c["id"] for c in calon]}}, {"_id": 0, "id": 1, "ai_finance": 1})}
    plan = doc.get("plan") or {}
    pt = await _nama_pt(eid)
    n = 0
    for u in calon:
        if "C" not in kelas.get(u["id"], []):
            continue
        res = await create_notification(
            notif_type="ai_card_second", title="Kartu asisten menunggu persetujuan orang kedua",
            body=(f"{maker.get('name', '')} menyetujui “{doc.get('title', '')}” sebesar "
                  f"{rupiah(_money(plan.get('amount')))} untuk {pt}. Kartu baru dijalankan sesudah orang kedua "
                  "menyetujuinya di Tanya KN › Tindakan › Menunggu orang lain."),
            severity="warning", link="tanya-kn", entity_id=eid, recipient_role="", recipient_user=u["id"],
            ref=f"{doc['id']}:{u['id']}")
        n += 1 if res else 0
    return n


async def _await_second(doc: Dict[str, Any], user: Dict[str, Any], reason: str, args: Dict[str, Any],
                        plan: Dict[str, Any], edits: Dict[str, Any]) -> Dict[str, Any]:
    """AG-T5 — pembuat menyetujui kartu yang butuh orang kedua: `pending → awaiting_second` (atomik); masa berlaku
    dihitung ulang dari saat ini; potret keputusan kontrol (`second_required`, D3); notifikasi. Tidak ada yang
    ditulis ke pintu."""
    eid = doc.get("entity_id") or ""
    jam = int(await value_of(KUNCI_MASA_BERLAKU, {"entity_id": eid}))
    sekarang = datetime.now(timezone.utc)
    now = sekarang.isoformat()
    upd = {"status": "awaiting_second", "reason": reason, "edits": edits, "args": args, "plan": plan,
           "first_by": _who(user), "first_at": now, "updated_at": now,
           "second_required": {"needed": True, "basis": await _basis_kedua(eid)},
           "expires_at": (sekarang + timedelta(hours=jam)).isoformat()}
    res = await db.ai_action_proposals.update_one({"id": doc["id"], "status": "pending"}, {"$set": upd})
    if not res.modified_count:
        fresh = await db.ai_action_proposals.find_one({"id": doc["id"]}, {"_id": 0}) or doc
        raise status_conflict(fresh.get("status", ""))
    out = {**doc, **upd}
    await audit(user.get("name", ""), "ai_card_awaiting_second", "ai_action_proposals", doc["id"],
                {"type": doc.get("type"), "amount": plan.get("amount", 0), "basis": upd["second_required"]["basis"]},
                scope_entity_id=eid)
    await _beri_tahu_orang_kedua(out, user)
    return out


async def decide(card_id: str, *, request: Any, user: Dict[str, Any], ctx: Any, decision: str, reason: str = "",
                 retype: str = "", edits: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if decision == "dismiss":
        return await dismiss(card_id, user=user, reason=reason)
    if decision != "approve":
        raise _err(400, "Keputusan kartu harus setujui atau abaikan.")
    # 1. muat (kedaluwarsa diterapkan) · pembuat · status · PT kartu = PT aktif
    doc = await _load(card_id, user)
    if doc["status"] != "pending":
        raise status_conflict(doc["status"])
    action = REGISTRY.get(doc.get("type") or "")
    if action is None:
        raise _err(400, MSG_TIDAK_DIKENAL)
    eid = doc.get("entity_id") or ""
    if eid not in (ctx.allowed_entity_ids or []):
        raise _err(403, MSG_TANPA_AKSES_PT)
    if getattr(ctx, "view_all", False) or ctx.active_entity_id != eid:
        raise _err(409, f"Kartu ini disiapkan untuk {doc.get('entity_name') or await _nama_pt(eid)}. "
                        "Pindah ke PT itu lalu setujui lagi.")
    # 2. sakelar golongan B / C
    if action.cls == "B":
        await _sakelar_b(user, eid)
    elif action.cls == "C":
        await _sakelar_c(user, eid, action)
    # 3. konfirmasi menurut tingkat
    reason = _text(reason)
    plan = doc.get("plan") or {}
    if action.risk in ("medium", "high") and len(reason) < REASON_MIN:
        raise _err(400, MSG_ALASAN)
    if action.risk == "high" and action.retype_kind == "text":   # AG-T5 — balik jurnal: nomor jurnal persis
        if not _norm_nomor(retype) or _norm_nomor(retype) != _norm_nomor(plan.get("confirm_text")):
            raise _err(400, MSG_KETIK_NOMOR)
    elif action.risk == "high" and (not _digits(retype) or _digits(retype) != _digits(plan.get("confirm_text"))):
        raise _err(400, MSG_KETIK)
    # 4. isian yang boleh diubah → rencana disusun ulang (sidik tetap yang lama: perubahan data tetap terdeteksi)
    token = _token_of(request)
    args = doc.get("args") or {}
    edits = {k: v for k, v in (edits or {}).items()} if isinstance(edits, dict) else {}
    if edits:
        boleh = {e.get("path") for e in doc.get("editable") or []}
        salah = [k for k in edits if k not in boleh]
        if salah:
            raise _err(400, "Isian ini tidak bisa diubah di kartu. Minta asisten menyiapkan kartu baru.")
        if _has_entity_key(edits):
            raise _err(400, ENTITY_MESSAGE)
        ulang = await _run_prepare(action, token, eid, {**args, **edits})
        args, plan = ulang["args"], ulang["plan"]
    # 5. batas harian
    await _batas_harian(user, eid)
    # 5b. AG-T5 — orang kedua (golongan C): sesudah konfirmasi, sebelum klaim
    second_required = None
    if action.cls == "C":
        from services import dual_control as _dc
        if await _dc.butuh_orang_kedua("asisten_uang_keluar", eid, _money(plan.get("amount"))):
            return await _await_second(doc, user, reason, args, plan, edits)
        second_required = {"needed": False, "basis": ""}
    # 6. klaim atomik pending → running
    mulai = now_iso()
    klaim = {"status": "running", "started_at": mulai, "updated_at": mulai, "reason": reason, "edits": edits,
             "args": args, "plan": plan, "decided_by": _who(user), "decided_at": mulai, "executor_id": user["id"]}
    if second_required is not None:   # golongan C satu orang: pelaksana = pembuat (potret keputusan kontrol, D3)
        klaim.update(first_by=_who(user), first_at=mulai, second_required=second_required)
    claimed = await db.ai_action_proposals.find_one_and_update({"id": card_id, "status": "pending"}, {"$set": klaim})
    if not claimed:
        fresh = await db.ai_action_proposals.find_one({"id": card_id}, {"_id": 0}) or doc
        raise status_conflict(fresh.get("status", ""))
    return await _jalankan(user, {**doc, **klaim}, action, token, args, plan)


async def _jalankan(user: Dict[str, Any], out: Dict[str, Any], action: "CardAction", token: str, args: Dict[str, Any],
                    plan: Dict[str, Any]) -> Dict[str, Any]:
    """Langkah 7–9 (kartu sudah `running`): baca ulang sidik → SATU panggilan tulis dengan sesi `token` (pembuat, atau
    orang kedua untuk golongan C yang menunggu) → `confirmed` | `failed`."""
    card_id, eid = out["id"], out.get("entity_id") or ""
    # 7. baca ulang sidik
    api = _reader(token, eid)
    try:
        fp2, _snap = await read_fingerprint(api, out.get("fingerprint_source") or [])
    except SelfApiError as exc:
        upd = await _finish(card_id, "failed", error_code="door", error=exc.message[:500],
                            result={"status_code": exc.status, "document": None, "gl_status": None,
                                    "message": exc.message[:500]})
        return await _done(user, out, upd)
    finally:
        await api.aclose()
    if fp2 != out.get("fingerprint"):
        upd = await _finish(card_id, "failed", error_code="stale", error=MSG_STALE,
                            result={"status_code": 200, "document": None, "gl_status": None, "message": MSG_STALE})
        return await _done(user, out, upd)
    # 8. satu panggilan tulis lewat pintu aplikasi (izin pelaksana, kunci idempotensi = id kartu)
    path_params, body = action.build_request(args, plan)
    path = _fill(action.write_path, path_params)
    code, resp, err = await _write(token, eid, card_id, action.write_method, path, body, card_class=action.cls)
    # 9. 2xx → confirmed (gl_status dari jawaban pintu); selain itu → failed dengan pesan asli
    if not err and 200 <= code < 300:
        if isinstance(resp, dict):
            resp = {**resp, "_card": card_id}
        res = action.result_of(resp, args, plan)
        upd = await _finish(card_id, "confirmed", error_code="", error="",
                            result={"status_code": code, "document": res.get("document"),
                                    "gl_status": res.get("gl_status"), "message": res.get("message") or ""})
    else:
        msg = str((resp or {}).get("message") or MSG_TIDAK_PASTI)[:500]
        upd = await _finish(card_id, "failed", error_code=err or "door", error=msg,
                            result={"status_code": code, "document": None, "gl_status": None, "message": msg})
    return await _done(user, out, upd)


async def _done(user: Dict[str, Any], doc: Dict[str, Any], upd: Dict[str, Any]) -> Dict[str, Any]:
    # 10. jejak
    ok = upd.get("status") == "confirmed"
    res = upd.get("result") or {}
    await audit(user.get("name", ""), "ai_card_confirmed" if ok else "ai_card_failed", "ai_action_proposals", doc["id"],
                {"type": doc.get("type"), "status_code": res.get("status_code"),
                 "document": (res.get("document") or {}).get("number", ""), "gl_status": res.get("gl_status"),
                 **({} if ok else {"error_code": upd.get("error_code"), "error": upd.get("error", "")})},
                scope_entity_id=doc.get("entity_id", ""))
    return {**doc, **upd}


# ── AG-T5 — orang kedua ───────────────────────────────────────────────────────────────────────────────────────────────
async def _load_raw(card_id: str) -> Dict[str, Any]:
    """Kartu golongan C apa adanya (kedaluwarsa diterapkan), tanpa syarat pembuat — penjaga ada di pemanggil."""
    from services.ai_actions import _segarkan
    doc = await db.ai_action_proposals.find_one({"id": card_id}, {"_id": 0})
    act = REGISTRY.get((doc or {}).get("type") or "")
    if not doc or not act or act.cls != "C":
        raise _err(404, "Kartu tindakan tidak ditemukan.")
    doc = await _segarkan(doc)
    doc["entity_name"] = await _nama_pt(doc.get("entity_id") or "")
    return doc


def _pengaju(doc: Dict[str, Any]) -> List[str]:
    return [str((doc.get("first_by") or {}).get("id") or doc.get("user_id") or "")]


async def second(card_id: str, *, request: Any, user: Dict[str, Any], ctx: Any, decision: str,
                 reason: str = "") -> Dict[str, Any]:
    """`POST /api/ai/actions/{id}/second` — orang kedua memutus kartu golongan C yang `awaiting_second`.

    Urutan: golongan `C` di akun (izin `ai_finance.approve` diperiksa router) → kartu → PT kartu dalam akses (403) dan =
    PT aktif (409) → status `awaiting_second` (409) → sakelar PT (409) → pembuat ≠ orang kedua
    (`dual_control.tolak_bila_pelaku_sama`, pesan baku KF-T6, pengecualian Admin diurus pembantu) → orang kedua memegang
    izin PINTU tindakan (403, kartu tetap menunggu) → tolak (alasan wajib) | setujui: klaim atomik
    `awaiting_second → running`, baca ulang sidik, SATU panggilan tulis dengan sesi orang kedua."""
    from services import dual_control as _dc
    if "C" not in _classes(user):
        raise _err(403, MSG_AKUN_MATI_C)
    if decision not in ("approve", "reject"):
        raise _err(400, MSG_KEPUTUSAN_KEDUA)
    doc = await _load_raw(card_id)
    action = REGISTRY[doc["type"]]
    eid = doc.get("entity_id") or ""
    if eid not in (ctx.allowed_entity_ids or []):
        raise _err(403, MSG_TANPA_AKSES_PT)
    if getattr(ctx, "view_all", False) or ctx.active_entity_id != eid:
        raise _err(409, f"Kartu ini disiapkan untuk {doc.get('entity_name') or await _nama_pt(eid)}. "
                        "Pindah ke PT itu lalu putuskan lagi.")
    if doc["status"] != "awaiting_second":
        raise status_conflict("expired") if doc["status"] == "expired" else _err(409, MSG_BUKAN_MENUNGGU)
    await _sakelar_pt_c(eid)
    plan = doc.get("plan") or {}
    await _dc.tolak_bila_pelaku_sama("asisten_uang_keluar", doc, user, eid, nominal=_money(plan.get("amount")),
                                     pengaju=_pengaju(doc))
    if action.door[0] and not await has_permission(user, action.door[0], action.door[1]):
        raise denied([action.door])
    reason = _text(reason)
    now = now_iso()
    if decision == "reject":
        if len(reason) < REASON_MIN:
            raise _err(400, MSG_ALASAN_TOLAK)
        upd = {"status": "dismissed", "second_by": _who(user), "second_at": now, "second_reason": reason,
               "decided_by": _who(user), "decided_at": now, "finished_at": now, "updated_at": now}
        res = await db.ai_action_proposals.update_one({"id": card_id, "status": "awaiting_second"}, {"$set": upd})
        if not res.modified_count:
            raise _err(409, MSG_BUKAN_MENUNGGU)
        await audit(user.get("name", ""), "ai_card_second_rejected", "ai_action_proposals", card_id,
                    {"type": doc["type"], "first_by": (doc.get("first_by") or {}).get("name", "")},
                    reason=reason, scope_entity_id=eid)
        return {**doc, **upd}
    klaim = {"status": "running", "started_at": now, "updated_at": now, "second_by": _who(user), "second_at": now,
             "second_reason": reason, "decided_by": _who(user), "decided_at": now, "executor_id": user["id"]}
    claimed = await db.ai_action_proposals.find_one_and_update(
        {"id": card_id, "status": "awaiting_second", "expires_at": {"$gt": now}}, {"$set": klaim})
    if not claimed:
        fresh = await _load_raw(card_id)
        raise status_conflict("expired") if fresh["status"] in ("expired", "awaiting_second") \
            else _err(409, MSG_BUKAN_MENUNGGU)
    out = {**doc, **klaim}
    await audit(user.get("name", ""), "ai_card_second_approved", "ai_action_proposals", card_id,
                {"type": doc["type"], "first_by": (doc.get("first_by") or {}).get("name", "")},
                reason=reason, scope_entity_id=eid)
    return await _jalankan(user, out, action, _token_of(request), doc.get("args") or {}, plan)


async def _bisa_kedua(doc: Dict[str, Any], user: Dict[str, Any], ctx: Any) -> Tuple[bool, str]:
    """Penilaian tanpa efek untuk layar: (boleh memutus sebagai orang kedua, alasan tertulis bila tidak)."""
    from services import dual_control as _dc
    if doc.get("status") != "awaiting_second":
        return False, ""
    if not await has_permission(user, "ai_finance", "approve"):
        return False, MSG_IZIN_KEDUA
    if "C" not in _classes(user):
        return False, MSG_AKUN_MATI_C
    eid = doc.get("entity_id") or ""
    if ctx is None or eid not in (ctx.allowed_entity_ids or []):
        return False, MSG_TANPA_AKSES_PT
    if getattr(ctx, "view_all", False) or ctx.active_entity_id != eid:
        return False, f"Pindah ke {doc.get('entity_name') or await _nama_pt(eid)} untuk memutuskan kartu ini."
    if not await value_of("ai.tindakan_uang_keluar", {"entity_id": eid}):
        return False, f"Tindakan uang keluar dan jurnal lewat asisten belum dinyalakan untuk {await _nama_pt(eid)}."
    res = await _dc.periksa("asisten_uang_keluar", doc, user, eid, nominal=_money((doc.get("plan") or {}).get("amount")),
                            pengaju=_pengaju(doc))
    if res["ditolak"]:
        return False, res["pesan"]
    action = REGISTRY.get(doc.get("type") or "")
    if action and action.door[0] and not await has_permission(user, action.door[0], action.door[1]):
        from dependencies import denied_message
        return False, denied_message([action.door])
    return True, ""


async def decorate(doc: Dict[str, Any], user: Dict[str, Any], ctx: Any = None) -> Dict[str, Any]:
    """Isian layar kartu golongan C: `second_preview` (kartu `pending` akan menunggu orang kedua bila disetujui sekarang),
    `is_maker`, `can_second` + `second_block` (alasan tertulis bila tidak bisa memutus)."""
    action = REGISTRY.get(doc.get("type") or "")
    if not action or action.cls != "C":
        return doc
    out = {**doc, "is_maker": doc.get("user_id") == user.get("id")}
    if doc.get("status") == "pending":
        from services import dual_control as _dc
        out["second_preview"] = await _dc.butuh_orang_kedua("asisten_uang_keluar", doc.get("entity_id") or "",
                                                            _money((doc.get("plan") or {}).get("amount")))
    ok, why = await _bisa_kedua(doc, user, ctx)
    out.update(can_second=ok, second_block=why)
    return out


async def load_view(card_id: str, user: Dict[str, Any], ctx: Any) -> Dict[str, Any]:
    """`GET /api/ai/actions/{id}`: kartu milik pengguna (AG-T1/AG-T3), atau — AG-T5 — kartu golongan C orang lain yang
    menunggu orang kedua / sudah diputusnya, bagi pemegang `ai_finance.approve` yang bertugas di PT kartu."""
    from services.ai_actions import load
    raw = await db.ai_action_proposals.find_one({"id": card_id}, {"_id": 0, "user_id": 1, "type": 1, "status": 1,
                                                                  "entity_id": 1, "second_by": 1})
    act = REGISTRY.get((raw or {}).get("type") or "")
    if raw and act and act.cls == "C" and raw.get("user_id") != user["id"] \
            and (raw.get("status") == "awaiting_second" or (raw.get("second_by") or {}).get("id") == user["id"]) \
            and raw.get("entity_id") in (getattr(ctx, "allowed_entity_ids", None) or []) \
            and await has_permission(user, "ai_finance", "approve"):
        return await decorate(await _load_raw(card_id), user, ctx)
    return await decorate(await load(card_id, user), user, ctx)


# ── Daftar kartu (tab "Tindakan") ─────────────────────────────────────────────────────────────────────────────────────
#: AG-T5 — "Menunggu orang lain" (`others`) = kartu `awaiting_second` di PT aktif: semua kartu PT itu bagi yang boleh
#: menjadi orang kedua (izin `ai_finance.approve` + golongan `C`), kartu miliknya sendiri bagi pembuat.
BOXES = {"mine": ["pending", "running"], "others": ["awaiting_second"],
         "done": ["confirmed", "dismissed", "expired", "superseded"], "failed": ["failed"]}


async def list_cards(user: Dict[str, Any], box: str = "mine", page: int = 1, page_size: int = PAGE_SIZE_DEFAULT,
                     ctx: Any = None) -> Dict[str, Any]:
    """Kartu milik pengguna per kotak. "Menunggu orang lain" = kartu yang menunggu orang kedua di PT aktif (AG-T5);
    kotak Selesai/Gagal juga memuat kartu yang dijalankan pengguna sebagai orang kedua."""
    from services.ai_actions import _nama_pt as nama, _segarkan
    if box not in BOXES:
        raise _err(400, "Saringan kartu tidak dikenal.")
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or PAGE_SIZE_DEFAULT), PAGE_SIZE_MAX))
    now = now_iso()
    if box == "others":
        if ctx is None or getattr(ctx, "view_all", False):
            ents = list(getattr(ctx, "allowed_entity_ids", None) or [])
        else:
            ents = [ctx.active_entity_id]
        await db.ai_action_proposals.update_many(
            {"entity_id": {"$in": ents}, "status": "awaiting_second", "expires_at": {"$lte": now}},
            {"$set": {"status": "expired", "finished_at": now, "updated_at": now}})
        q: Dict[str, Any] = {"status": "awaiting_second", "entity_id": {"$in": ents}}
        if not (await has_permission(user, "ai_finance", "approve") and "C" in _classes(user)):
            q["user_id"] = user["id"]
    else:
        # Kedaluwarsa diterapkan dulu supaya jumlah per kotak benar (kartu lama tanpa `expires_at` di `_segarkan`).
        await db.ai_action_proposals.update_many(
            {"user_id": user["id"], "status": "pending", "expires_at": {"$lte": now}},
            {"$set": {"status": "expired", "finished_at": now, "updated_at": now}})
        q = {"user_id": user["id"], "status": {"$in": BOXES[box]}}
        if box in ("done", "failed"):
            q = {"status": {"$in": BOXES[box]}, "$or": [{"user_id": user["id"]}, {"second_by.id": user["id"]}]}
    total = await db.ai_action_proposals.count_documents(q)
    rows = await db.ai_action_proposals.find(q, {"_id": 0}).sort([("created_at", -1), ("id", -1)]) \
        .skip((page - 1) * page_size).limit(page_size).to_list(page_size)
    names: Dict[str, str] = {}
    items = []
    for r in rows:
        r = await _segarkan(r)
        eid = r.get("entity_id") or ""
        if eid not in names:
            names[eid] = await nama(eid)
        r["entity_name"] = names[eid]
        items.append(r)
    return {"items": items, "total": total, "page": page, "page_size": page_size}
