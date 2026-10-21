"""F-11-layar (uji pra-UAT 2026-10-21) — Gudang & QC membuka retur pelanggan untuk scan & QC.

Keputusan pemilik 2026-10-21 (opsi b, terbatas): pemegang `wms.scan` / `qc.inspect` yang TIDAK
memegang `sales_return.view` ("operator") boleh MELIHAT retur yang sedang mereka kerjakan,
bukan dokumen ber-uang:

* daftar & hitungan status hanya `approved` / `inspecting` (barang ditunggu / sedang diperiksa);
* detail & timeline hanya selama tahap itu, plus `inspected` supaya hasil QC yang baru disimpan
  tetap terbaca (status lain → 403);
* semua field uang dibuang (harga, nilai, kompensasi, nota kredit, ongkir, refund, …) dan jalur
  "Penyelesaian uang" timeline tidak dikirim;
* keputusan owner 2026-10-21: foto/video bukti keluhan boleh DIUNDUH (lampiran lain, mis. PDF, tidak).

Pemegang `sales_return.view` tidak tersentuh modul ini sama sekali.
"""
from typing import Any, Dict, Tuple

from fastapi import HTTPException, Request

from dependencies import has_permission, require_any_permission

READ_PERMS = [("sales_return", "view"), ("wms", "scan"), ("qc", "inspect")]
LIST_STATES = ("approved", "inspecting")
DETAIL_STATES = ("approved", "inspecting", "inspected")

# Kata (dipisah "_") yang menandai nilai rupiah atau keputusan uang pada nama field.
MONEY_TOKENS = frozenset({
    "price", "prices", "amount", "amounts", "total", "totals", "subtotal", "value", "values",
    "cost", "costs", "cogs", "hpp", "refund", "refunds", "credit", "credits", "writeoff", "writeoffs",
    "ppn", "vat", "tax", "dpp", "discount", "discounts", "fee", "fees", "compensation", "payout",
    "payment", "payments", "paid", "balance", "landed", "impairment", "obligation", "obligations",
    "grand", "nominal", "rupiah", "idr", "money", "margin", "cash", "journal", "je", "gl", "ar", "ap",
    "account", "settlement", "decision",
})
SAFE_KEYS = frozenset({"point_value", "total_points"})   # bobot & jumlah poin cacat 4-point, bukan rupiah


def is_money_key(key: Any) -> bool:
    k = str(key).lower()
    return k not in SAFE_KEYS and any(t in MONEY_TOKENS for t in k.split("_"))


def strip_money(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: strip_money(v) for k, v in obj.items() if not is_money_key(k)}
    if isinstance(obj, list):
        return [strip_money(v) for v in obj]
    return obj


async def is_operator(user: Dict[str, Any]) -> bool:
    return not await has_permission(user, "sales_return", "view")


async def reader(request: Request) -> Tuple[Dict[str, Any], bool]:
    """Pembaca retur: (pengguna, operator?). 403 bila tidak memegang satu pun izin baca."""
    user = await require_any_permission(request, READ_PERMS)
    return user, await is_operator(user)


def list_status(status: str) -> Dict[str, Any]:
    """Saringan status daftar operator — status di luar tahap kerja menghasilkan daftar kosong."""
    return {"$in": [s for s in LIST_STATES if not status or s == status]}


def assert_open_for_operator(doc: Dict[str, Any]) -> None:
    if doc.get("status") not in DETAIL_STATES:
        raise HTTPException(status_code=403, detail=(
            "Gudang/QC hanya membuka retur yang sedang menunggu terima barang atau diperiksa QC."))


MEDIA_PREFIXES = ("image/", "video/")


def assert_operator_download(att: Dict[str, Any]) -> None:
    if not str(att.get("content_type") or "").startswith(MEDIA_PREFIXES):
        raise HTTPException(status_code=403, detail=(
            "Gudang/QC hanya boleh mengunduh foto/video bukti keluhan — lampiran lain dibuka Sales/Admin."))


def operator_timeline(tl: Dict[str, Any]) -> Dict[str, Any]:
    lanes = {k: v for k, v in (tl.get("lanes") or {}).items() if k != "settlement"}
    events = [e for e in tl.get("events") or [] if e.get("lane") in lanes]
    return strip_money({**tl, "lanes": lanes, "events": events})
