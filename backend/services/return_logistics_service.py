"""GL-01 × KLR-11 — biaya logistik retur: cara kirim, penanggung, dan jurnal otomatis.

Owner 2026-10-19D: jurnal saat biaya dicatat di awal pengiriman (GL-03); Finance memilih akun pembayaran
kas/bank/hutang (GL-04); cara kirim: diambil customer, armada KN (gratis / customer bayar → ditagih terpisah),
ekspedisi pihak ketiga (ditanggung KN / customer bayar sendiri) (GL-05); PPN ongkir lewat pengaturan (GL-06);
PT pembeban dipilih per pengiriman (GL-07). Idempoten per (retur, jenis biaya); ubah = jurnal balik + baru.
"""
from typing import Any, Dict, List, Optional

from core_utils import now_iso
from db import db
from services import gl_service

TYPES = {"customer_return": "Ongkir retur dari customer", "qc_trip": "Perjalanan Jakarta–Rancamalang (QC)",
         "replacement_shipping": "Kirim barang pengganti"}
MODES = {"pickup": "Diambil customer / kurir customer", "own_fleet": "Armada KN", "third_party": "Ekspedisi pihak ketiga"}
BEARER_LABEL = {
    ("pickup", "customer"): "Customer mengurus sendiri",
    ("own_fleet", "company"): "Gratis (ditanggung KN)",
    ("own_fleet", "customer"): "Customer bayar — ditagih terpisah",
    ("third_party", "company"): "Ditanggung KN",
    ("third_party", "customer"): "Customer bayar sendiri ke ekspedisi",
}
VAT_KEY = "returns.logistics_vat_enabled"
SOURCE = "return_logistics"


async def vat_enabled(entity_id: str) -> bool:
    from services import config_resolver
    return bool(await config_resolver.value_of(VAT_KEY, {"entity_id": entity_id} if entity_id else None))


async def pay_accounts(entity_id: str) -> List[Dict[str, Any]]:
    """Pilihan akun pembayaran ongkir: kas/bank (1-11xx) dan kewajiban (hutang ekspedisi dsb.)."""
    accs = await gl_service.effective_accounts(None, entity_id or None)
    out = [{"code": c, "name": a.get("name", ""), "kind": "kas_bank" if c.startswith("1-11") else "hutang"}
           for c, a in accs.items() if a.get("is_active") is not False and a.get("is_postable") is not False
           and (c.startswith("1-11") or (a.get("type") == "liability" and c.startswith("2-1")))]
    return sorted(out, key=lambda x: x["code"])


def _norm(c: Dict[str, Any], ret: Dict[str, Any]) -> Dict[str, Any]:
    t, mode, bearer = c.get("type"), c.get("mode") or "third_party", c.get("bearer") or "company"
    if t not in TYPES or mode not in MODES:
        raise ValueError("Jenis biaya / cara kirim tidak dikenal")
    if mode == "pickup":
        bearer = "customer"
    if (mode, bearer) not in BEARER_LABEL:
        raise ValueError("Penanggung biaya tidak dikenal")
    amount = 0.0 if mode == "pickup" else round(float(c.get("amount") or 0), 2)
    vat = round(float(c.get("vat_amount") or 0), 2) if bearer == "company" else 0.0
    if amount < 0 or vat < 0:
        raise ValueError("Nominal tidak boleh negatif")
    if mode == "own_fleet" and bearer == "customer" and amount <= 0:
        raise ValueError("Armada KN dibayar customer: isi nominal yang ditagihkan")
    return {"type": t, "label": TYPES[t], "mode": mode, "mode_label": MODES[mode], "bearer": bearer,
            "bearer_label": BEARER_LABEL[(mode, bearer)], "amount": amount, "vat_amount": vat,
            "note": (c.get("note") or "").strip(), "pay_account_code": (c.get("pay_account_code") or "").strip(),
            "charged_entity_id": c.get("charged_entity_id") or ret.get("entity_id") or ""}


async def _desired_lines(ret: Dict[str, Any], r: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    num = ret.get("number", "")
    desc = f"{r['label']} · retur {num}"
    if r["mode"] == "pickup" or r["amount"] <= 0:
        return None
    if r["bearer"] == "customer":
        if r["mode"] != "own_fleet":
            return None  # customer membayar ekspedisi langsung — tidak lewat buku KN
        return [{"account_key": "retur.ongkir_piutang_customer", "debit": r["amount"], "credit": 0.0,
                 "description": f"Tagihan ongkir ke {ret.get('customer_name', 'customer')} · {desc}"},
                {"account_key": "retur.ongkir_pendapatan", "debit": 0.0, "credit": r["amount"], "description": desc}]
    lines = [{"account_key": "retur.ongkir_perusahaan", "debit": r["amount"], "credit": 0.0, "description": desc}]
    if r["vat_amount"] > 0:
        lines.append({"account_key": "retur.ongkir_ppn_masukan", "debit": r["vat_amount"], "credit": 0.0,
                      "description": f"PPN masukan ongkir · {desc}"})
    pay = {"account_code": r["pay_account_code"], "fixed_account": True} if r["pay_account_code"] \
        else {"account_key": "retur.ongkir_pembayaran"}
    lines.append({**pay, "debit": 0.0, "credit": round(r["amount"] + r["vat_amount"], 2),
                  "description": f"Pembayaran {desc}"})
    return lines


def _sig(entity: str, lines: List[Dict[str, Any]]) -> tuple:
    return (entity, tuple(sorted((ln["account_code"], round(ln.get("debit", 0), 2), round(ln.get("credit", 0), 2))
                                 for ln in lines if ln.get("debit") or ln.get("credit"))))


async def _active(ret_id: str, t: str) -> Optional[Dict[str, Any]]:
    return await db.journal_entries.find_one(
        {"source_type": SOURCE, "ref.return_id": ret_id, "ref.cost_type": t, "status": {"$ne": "void"},
         "reversed_by_entry_id": {"$exists": False}}, {"_id": 0})


async def _reverse(je: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> None:
    await gl_service.reverse_entry(je["id"], now_iso()[:10], reason, actor)


async def sync_journals(ret: Dict[str, Any], rows: List[Dict[str, Any]], actor: Dict[str, Any]) -> None:
    from services import gl_mapping_service as glm
    by_type = {r["type"]: r for r in rows}
    for t in TYPES:
        r = by_type.get(t)
        cur = await _active(ret["id"], t)
        want = await _desired_lines(ret, r) if r else None
        if want:
            resolved = await glm.remap_lines(want, r["charged_entity_id"], SOURCE)
            if cur and _sig(cur["entity_id"], cur["lines"]) == _sig(r["charged_entity_id"], resolved):
                r.update(journal_entry_id=cur["id"], journal_entry_number=cur.get("number", ""))
                continue
        if cur:
            await _reverse(cur, f"Biaya logistik retur {ret.get('number', '')} diubah", actor)
        if not want:
            if r:
                r.update(journal_entry_id="", journal_entry_number="")
            continue
        seq = await db.journal_entries.count_documents({"source_type": SOURCE, "ref.return_id": ret["id"], "ref.cost_type": t})
        je = await gl_service._insert_entry(
            lines=want, description=f"{r['label']} · retur {ret.get('number', '')} ({r['bearer_label']})",
            date=now_iso(), source_type=SOURCE, source_id=f"{ret['id']}:{t}:{seq + 1}", entity_id=r["charged_entity_id"],
            created_by=actor.get("name", "system"), source_label=f"Ongkir retur {ret.get('number', '')}",
            ref={"return_id": ret["id"], "return_number": ret.get("number", ""), "cost_type": t})
        r.update(journal_entry_id=je["id"], journal_entry_number=je.get("number", ""))


async def save(ret: Dict[str, Any], costs: List[Dict[str, Any]], actor: Dict[str, Any], can_post: bool) -> Dict[str, Any]:
    rows, seen = [], set()
    prev = {c["type"]: c for c in (ret.get("logistics_costs") or {}).get("costs", [])}
    vat_on = await vat_enabled(ret.get("entity_id", ""))
    for c in costs:
        r = _norm(c, ret)
        if r["type"] in seen:
            raise ValueError(f"{r['label']} diisi dua kali")
        seen.add(r["type"])
        if not vat_on:
            r["vat_amount"] = 0.0
        old = prev.get(r["type"]) or {}
        if not can_post and r["pay_account_code"] != (old.get("pay_account_code") or ""):
            raise PermissionError("Hanya Finance yang boleh memilih akun pembayaran ongkir")
        if r["pay_account_code"] and r["pay_account_code"] not in {a["code"] for a in await pay_accounts(r["charged_entity_id"])}:
            raise ValueError(f"Akun pembayaran {r['pay_account_code']} bukan akun kas/bank/hutang yang aktif")
        rows.append(r)
    await sync_journals(ret, rows, actor)
    doc = {"costs": rows, "customer_total": round(sum(r["amount"] for r in rows if r["bearer"] == "customer"), 2),
           "company_total": round(sum(r["amount"] for r in rows if r["bearer"] == "company"), 2),
           "vat_enabled": vat_on, "updated_by": actor.get("name", ""), "updated_at": now_iso()}
    await db.sales_returns.update_one({"id": ret["id"]}, {"$set": {"logistics_costs": doc}})
    return doc


async def reverse_all(ret: Dict[str, Any], reason: str, actor: Dict[str, Any]) -> int:
    n = 0
    for t in TYPES:
        cur = await _active(ret["id"], t)
        if cur:
            await _reverse(cur, reason, actor)
            n += 1
    return n
