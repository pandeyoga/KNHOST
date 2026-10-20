"""L01 — REKAP SUSUT & KLAIM PER MITRA MAKLOON (baca saja).

Menggabungkan dua sumber klaim yang sudah ada di order makloon:
  * `steps[].material_losses` — susut/hilang bahan di mitra (MKO batal): beban wajar, klaim (piutang),
    potong tagihan jasa, menunggu persetujuan.
  * `steps[].claim` — selisih hasil saat terima (FASE D): diajukan/menunggu/disetujui per aksi.
Hasil: ringkasan per mitra + baris rinci untuk penagihan & evaluasi.

AUD-MKL-02 — ringkasan & rincian dihitung dari himpunan yang SAMA dan utuh: order dibaca lewat cursor (tanpa batas
5.000), rincian tidak dipotong diam-diam. Layar memakai halaman rincian (`rows_offset`/`rows_limit`) dengan
`rows_total`; Excel meminta semua rincian (`rows_limit=None`).
"""
from typing import Any, Dict, List, Optional

from db import db

EPS = 1e-6


def _in_range(at: str, date_from: str, date_to: str) -> bool:
    d = (at or "")[:10]
    return (not date_from or d >= date_from) and (not date_to or d <= date_to)


TOTAL_KEYS = ("loss_events", "loss_qty", "loss_expense", "loss_claim", "loss_deducted", "loss_pending",
              "variance_claims", "variance_claim_amount", "variance_pending", "receivable_total", "deducted_total")


async def recap(entity_filter: Optional[Dict[str, Any]] = None, *, date_from: str = "", date_to: str = "",
                makloon_id: str = "", rows_offset: int = 0, rows_limit: Optional[int] = 1000) -> Dict[str, Any]:
    q: Dict[str, Any] = dict(entity_filter or {})
    if makloon_id:
        q["steps.makloon_id"] = makloon_id
    orders = db.makloon_orders.find(q, {"_id": 0, "id": 1, "mko_number": 1, "entity_id": 1, "status": 1, "steps": 1})
    acc: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []

    def bucket(s: Dict[str, Any]) -> Dict[str, Any]:
        mid = s.get("makloon_id") or "-"
        return acc.setdefault(mid, {
            "makloon_id": mid, "makloon_name": s.get("makloon_name") or mid,
            "loss_events": 0, "loss_qty": 0.0, "loss_expense": 0.0, "loss_claim": 0.0, "loss_deducted": 0.0,
            "loss_pending": 0, "loss_pending_qty": 0.0,
            "variance_claims": 0, "variance_claim_amount": 0.0, "variance_pending": 0,
            "receivable_total": 0.0, "deducted_total": 0.0})

    async for o in orders:
        for s in o.get("steps") or []:
            if makloon_id and s.get("makloon_id") != makloon_id:
                continue
            for x in s.get("material_losses") or []:
                if not _in_range(x.get("recorded_at") or x.get("at") or "", date_from, date_to):
                    continue
                a = bucket(s)
                st = x.get("status")
                row = {"kind": "susut", "mko_id": o["id"], "mko_number": o.get("mko_number"), "step_seq": s.get("seq"),
                       "makloon_id": a["makloon_id"], "makloon_name": a["makloon_name"], "status": st,
                       "at": x.get("decided_at") or x.get("recorded_at") or "", "qty": x.get("qty"),
                       "unit": s.get("input_unit") or "", "reason": x.get("reason", ""),
                       "expense": 0.0, "claim": 0.0, "settle": x.get("settle") or "", "bill_id": x.get("bill_id") or ""}
                if st == "posted":
                    a["loss_events"] += 1
                    a["loss_qty"] += float(x.get("qty") or 0)
                    a["loss_expense"] += float(x.get("expense_value") or 0)
                    cv = float(x.get("claim_value") or 0)
                    row.update(expense=float(x.get("expense_value") or 0), claim=cv)
                    if x.get("settle") == "potong_bon":
                        a["loss_deducted"] += cv
                    else:
                        a["loss_claim"] += cv
                elif st == "pending_approval":
                    a["loss_pending"] += 1
                    a["loss_pending_qty"] += float(x.get("over_qty") or 0)
                rows.append(row)
            c = s.get("claim") or {}
            if c.get("status") in ("pending_approval", "approved") and \
                    _in_range(c.get("approved_at") or c.get("proposed_at") or "", date_from, date_to):
                a = bucket(s)
                amt = float(c.get("amount") or 0)
                if c["status"] == "approved":
                    a["variance_claims"] += 1
                    a["variance_claim_amount"] += amt
                    if c.get("action") == "potong_bon":
                        a["deducted_total"] += amt
                    elif c.get("action") == "tagih_ganti":
                        a["receivable_total"] += amt
                else:
                    a["variance_pending"] += 1
                rows.append({"kind": "selisih", "mko_id": o["id"], "mko_number": o.get("mko_number"),
                             "step_seq": s.get("seq"), "makloon_id": a["makloon_id"], "makloon_name": a["makloon_name"],
                             "status": c["status"], "at": c.get("approved_at") or c.get("proposed_at") or "",
                             "qty": c.get("variance_qty"), "unit": s.get("output_unit") or s.get("input_unit") or "",
                             "reason": c.get("reason", ""), "expense": 0.0,
                             "claim": amt, "settle": c.get("action") or "", "bill_id": ""})
    partners = []
    for a in acc.values():
        a["receivable_total"] += a["loss_claim"]
        a["deducted_total"] += a["loss_deducted"]
        partners.append({k: (round(v, 2) if isinstance(v, float) else v) for k, v in a.items()})
    partners.sort(key=lambda p: -(p["receivable_total"] + p["deducted_total"] + p["loss_expense"]))
    rows.sort(key=lambda r: r.get("at") or "", reverse=True)
    tot = {k: round(sum(p[k] for p in partners), 2) for k in TOTAL_KEYS}
    off = max(0, int(rows_offset or 0))
    page = rows[off:] if rows_limit is None else rows[off:off + max(0, int(rows_limit))]
    return {"partners": partners, "rows": page, "rows_total": len(rows), "rows_offset": off,
            "rows_limit": rows_limit, "totals": tot}
