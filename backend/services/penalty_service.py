"""FASE G-2 — **DENDA KETERLAMBATAN SEBAGAI DOKUMEN** (`penalties`).

MASALAH NYATA PEMILIK
---------------------
Denda hari ini hanya **angka estimasi** di laporan Umur Piutang: tidak bisa ditagih, tidak
bisa dinegosiasikan, tidak bisa dibebaskan dengan alasan, dan tidak pernah masuk pembukuan.
Akibatnya pembicaraan denda dengan pelanggan selalu di luar sistem.

DESAIN (kunci fleksibilitas)
----------------------------
Denda lahir sebagai **`draft`** — **TANPA jurnal**. Jadi bisa dinegosiasikan atau dibatalkan
tanpa pernah mengotori buku besar. Siklusnya:

    draft  ──terbitkan──>  issued   (Dr 1-1270 Piutang Denda / Cr 4-9300 Pendapatan Denda)
      │                        │
      │                        ├──bayar──>  paid    (Dr Kas / Cr Piutang Denda)
      │                        ├──bebaskan──> waived  (JE pembalik — ledger append-only)
      │                        └──ubah nominal──> adjusted (JE selisih)
      └──bebaskan / ubah nominal saat masih draft → cukup ubah dokumen (tak ada jurnal)

Pembebasan & perubahan nominal WAJIB: **label alasan** (taksonomi `amendment_reasons`
yang bisa ditambah admin, warisan FASE G-1) + **persetujuan** bila kebijakan mensyaratkan.

INVARIAN
--------
* **INV-PEN-01** denda `draft` tidak boleh punya jurnal.
* **INV-PEN-02** `waived` / `adjusted` wajib punya alasan; wajib penyetuju bila kebijakan
  `payment.penalty_waive_requires_approval` aktif.
* **INV-PEN-03** Σ denda terbit yang belum dibayar == saldo akun Piutang Denda di GL.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core_utils import new_id, next_doc_number, now_iso, safe_doc, rupiah
from db import db
from services import gl_service
from services import payment_plan_service as plans
from services.config_resolver import resolve
from role_registry import role_in, role_label, setara_untuk  # peran acuan dikenali (keputusan owner 2026-10-21)

COLL = "penalties"
EPS = 0.01
STATUSES = ("draft", "issued", "waived", "adjusted", "paid")
STATUS_LABEL = {
    "draft": "Usulan (belum berjurnal)",
    "issued": "Terbit (sudah berjurnal)",
    "waived": "Dibebaskan",
    "adjusted": "Nominal diubah",
    "paid": "Sudah dibayar",
}
REASON_DOC_TYPE = "penalty"        # `amendment_reasons.applies_to` — dikelola admin


class PenaltyError(ValueError):
    """Kesalahan denda dengan pesan siap tampil (Bahasa Indonesia)."""


class PenaltyConflict(PenaltyError):
    """PK-08 — keadaan berubah saat diproses / jurnal gagal sesudah kas tercatat → router menjawab 409."""


# ── Kebijakan (registry → profil kredit → rencana) ─────────────────────
#: CR-T4 — asal tiap unsur aturan denda (`policy_snapshot.sources`, layar "Aturan dari: …").
SRC_GLOBAL, SRC_PT, SRC_PELANGGAN, SRC_RENCANA = "global", "pt", "pelanggan", "rencana"
SOURCE_LABEL = {SRC_GLOBAL: "aturan grup", SRC_PT: "PT", SRC_PELANGGAN: "pelanggan", SRC_RENCANA: "rencana"}
#: Unsur aturan → kunci Pusat Pengaturan (lapisan global → PT; `scopes` lima kunci pertama tanpa `customer` sejak CR-T4).
POLICY_KEYS = {"mode": "payment.penalty_mode", "base": "payment.penalty_base", "cap_pct": "payment.penalty_cap_pct",
               "rate_pct_per_month": "ar.denda_rate_pct_per_month", "grace_days": "ar.grace_days",
               "min_amount": "payment.penalty_min_amount"}
#: Unsur yang bisa ditimpa profil kredit (`khusus`) dan rencana bayar (`plan.penalty`).
RULE_FIELDS = ("rate_pct_per_month", "cap_pct", "grace_days", "base")
_LAPISAN_PT = ("entity", "legacy_entity")
_TIPE = {"mode": str, "base": str, "grace_days": lambda v: int(float(v))}


def _cast(unsur: str, value: Any, key: str = "") -> Any:
    """Nilai unsur sesuai tipenya; kosong / tak terbaca → bawaan registry (`02` §2.2, tanpa cadangan lain)."""
    from config_registry import default_of
    key = key or POLICY_KEYS[unsur]
    fn = _TIPE.get(unsur, float)
    if value in (None, ""):
        value = default_of(key)
    try:
        return fn(value)
    except (TypeError, ValueError):
        return fn(default_of(key))


async def _customer_rule(customer_id: str, entity_id: str, today: str) -> Dict[str, Any]:
    """CR-T4 — `customer_credit_profiles.penalty_rule` pasangan (pelanggan, PT) yang BERLAKU hari `today`:
    `{mode: ikut_pt|khusus|bebas, …}`. Bebas denda yang tanggal berakhirnya lewat (atau tanpa alasan/tanggal) dibaca
    `ikut_pt` — tidak ada bebas selamanya."""
    if not customer_id or not entity_id:
        return {"mode": "ikut_pt"}
    from services import credit_profile_service as cps
    prof = await db[cps.COLL].find_one({"customer_id": customer_id, "entity_id": entity_id},
                                       {"_id": 0, "penalty_rule": 1}) or {}
    rule = prof.get("penalty_rule") or {}
    mode = str(rule.get("mode") or "ikut_pt")
    if mode == "bebas":
        valid = str(rule.get("valid_until") or "")[:10]
        if not valid or valid < today or not str(rule.get("reason") or "").strip():
            return {**rule, "mode": "ikut_pt", "expired_waiver": {"reason": rule.get("reason") or "",
                                                                  "valid_until": valid}}
    if mode not in ("khusus", "bebas"):
        return {"mode": "ikut_pt"}
    return {**rule, "mode": mode}


async def penalty_policy(entity_id: str = "", customer_id: str = "",
                         plan: Optional[Dict[str, Any]] = None, *, today: Optional[str] = None,
                         pt_cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Kebijakan denda yang BERLAKU, CR-T4 (`docs/blueprint/unit/CR-T4.md`) — urutan:

    1. aturan grup → PT lewat resolver dengan konteks `{"entity_id"}` saja (lapisan `customer` lima kunci dicabut);
    2. profil kredit pasangan (pelanggan, PT): `khusus` menimpa unsur yang terisi; `bebas` yang masih berlaku menyetel
       `mode: off` dan mengisi `waiver: {reason, valid_until}`;
    3. `plan.penalty` (rencana bayar) menimpa unsur yang terisi — tetap paling khusus.
    Jawaban membawa `sources` (asal tiap unsur: `global` · `pt` · `pelanggan` · `rencana`).

    Kunci yang dibaca (`POLICY_KEYS`): `payment.penalty_mode`, `payment.penalty_base`, `payment.penalty_cap_pct`,
    `ar.denda_rate_pct_per_month`, `ar.grace_days`, `payment.penalty_min_amount`, ditambah
    `payment.penalty_waive_requires_approval` dan `payment.penalty_waive_approver_role`.

    PT kosong + pelanggan terisi → PT pemilik data pelanggan (sama dengan `credit_profile_service.effective`). Bunga &
    tenggang memakai kunci laporan Umur Piutang (`ar.*`) — taksiran laporan dan nota denda satu aturan. `pt_cache`
    (opsional, per panggilan daftar) = aturan grup → PT dibaca sekali per PT.
    """
    from services.book_date import tanggal_buku
    day = (today or tanggal_buku())[:10]
    eid = entity_id if entity_id and entity_id != "all" else ""
    if not eid and customer_id:
        cust = await db.customers.find_one({"id": customer_id}, {"_id": 0, "entity_id": 1}) or {}
        eid = cust.get("entity_id") or ""
    if pt_cache is not None and eid in pt_cache:
        pol, sources = dict(pt_cache[eid][0]), dict(pt_cache[eid][1])
    else:
        ctx = {"entity_id": eid}
        pol, sources = {}, {}
        for unsur, key in POLICY_KEYS.items():
            res = await resolve(key, ctx)
            pol[unsur] = _cast(unsur, res["value"])
            sources[unsur] = SRC_PT if res.get("source_layer") in _LAPISAN_PT else SRC_GLOBAL
        pol["waive_requires_approval"] = bool((await resolve("payment.penalty_waive_requires_approval", ctx))["value"])
        pol["approver_role"] = _cast("mode", (await resolve("payment.penalty_waive_approver_role", ctx))["value"],
                                     "payment.penalty_waive_approver_role")
        if pt_cache is not None:
            pt_cache[eid] = (dict(pol), dict(sources))
    # 2. Profil kredit pelanggan di PT ini (satu pemilik lapisan pelanggan, D1).
    rule = await _customer_rule(customer_id or "", eid, day)
    waiver = None
    if rule["mode"] == "khusus":
        _timpa(pol, sources, rule, SRC_PELANGGAN)
    elif rule["mode"] == "bebas":
        pol["mode"], sources["mode"] = "off", SRC_PELANGGAN
        waiver = {"reason": str(rule.get("reason") or ""), "valid_until": str(rule.get("valid_until") or "")[:10]}
    # 3. Aturan khusus rencana pembayaran (kesepakatan satu pesanan).
    over = (plan or {}).get("penalty") or {}
    if over.get("mode"):
        pol["mode"], sources["mode"] = str(over["mode"]), SRC_RENCANA
    _timpa(pol, sources, over, SRC_RENCANA)
    pol["sources"] = sources
    pol["waiver"] = waiver if pol["mode"] == "off" and sources["mode"] == SRC_PELANGGAN else None
    pol["expired_waiver"] = rule.get("expired_waiver") or None
    pol["customer_rule_mode"] = rule["mode"]
    pol["entity_id"] = eid
    return pol


def _timpa(pol: Dict[str, Any], sources: Dict[str, str], rule: Dict[str, Any], asal: str) -> None:
    """Unsur `rule` yang TERISI (bukan None/"") menimpa `pol`; asalnya dicatat di `sources`."""
    for unsur in RULE_FIELDS:
        v = rule.get(unsur)
        if v in (None, ""):
            continue
        pol[unsur] = _cast(unsur, v)
        sources[unsur] = asal


def estimate(line_outstanding: float, days_late: int, policy: Dict[str, Any],
             order_outstanding: Optional[float] = None) -> float:
    """CR-T4 — taksiran denda SATU baris tagihan = nominal nota yang akan lahir untuk baris itu (aturan, dasar,
    tenggang, batas atas, dan minimum sama dengan `accrue_plan`; dipakai laporan Umur Piutang). Mode mati → 0."""
    if policy.get("mode") == "off" or int(days_late or 0) <= int(policy["grace_days"]):
        return 0.0
    base = float(line_outstanding or 0)
    if policy.get("base") != "installment":
        base = max(float(order_outstanding if order_outstanding is not None else line_outstanding or 0), 0.0)
    if base <= EPS:
        return 0.0
    calc = compute_amount(base, int(days_late), policy)
    if calc["billable_days"] <= 0 or calc["amount"] < float(policy["min_amount"]) - EPS:
        return 0.0
    return calc["amount"]


# ── Perhitungan (auditable) ───────────────────────────────────────────
def _days_late(due_date: str, today: str) -> int:
    try:
        d1 = datetime.strptime(str(due_date)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        d2 = datetime.strptime(str(today)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return 0
    return max(0, (d2 - d1).days)


def compute_amount(base_amount: float, days_late: int, policy: Dict[str, Any],
                   days_prior: int = 0) -> Dict[str, Any]:
    """Hitung denda + `explain[]` supaya angkanya bisa dipertanggungjawabkan ke pelanggan.

    PK-08 (FX-04) — `days_late` kumulatif sejak jatuh tempo; `days_prior` = hari kena denda yang SUDAH dimuat nota
    sebelumnya untuk baris yang sama. Nota ini hanya memuat sisanya, jadi hari telat tidak ditagih dua kali."""
    grace = int(policy["grace_days"])
    cumulative = max(0, days_late - grace)
    days_prior = max(0, int(days_prior or 0))
    billable = max(0, cumulative - days_prior)
    rate = float(policy["rate_pct_per_month"])
    raw = round(float(base_amount) * (rate / 100.0) * (billable / 30.0), 2)
    cap_pct = float(policy["cap_pct"] or 0)
    capped = raw
    if cap_pct > 0:
        limit = round(float(base_amount) * cap_pct / 100.0, 2)
        capped = min(raw, limit)
    explain = [
        f"Dasar denda {rupiah(float(base_amount))} "
        f"({'sisa tagihan yang telat' if policy['base'] == 'installment' else 'seluruh sisa pesanan'})",
        f"Telat {days_late} hari − tenggang {grace} hari = {cumulative} hari kena denda",
    ]
    if days_prior > 0:
        explain.append(f"Sudah dimuat nota sebelumnya {days_prior} hari → nota ini {billable} hari")
    explain.append(f"Bunga {rate:g}% / bulan × {billable}/30 hari → {rupiah(raw)}")
    if cap_pct > 0:
        explain.append(
            f"Batas maksimum {cap_pct:g}% dari dasar = {rupiah(round(float(base_amount) * cap_pct / 100.0))} → dipakai {rupiah(capped)}")
    return {"amount": capped, "raw_amount": raw, "days_late": days_late, "days_prior": days_prior,
            "billable_days": billable, "rate_pct_per_month": rate,
            "grace_days": grace, "cap_pct": cap_pct, "explain": explain}


def _period_key(due_date: str, today: str) -> str:
    """Kunci periode akrual: satu nota per baris per BULAN kalender berjalan.

    Ini yang membuat job harian idempotent: dijalankan 30× sebulan tetap satu nota,
    hanya nominalnya yang diperbarui selama masih `draft`.
    """
    return f"{str(due_date)[:10]}|{str(today)[:7]}"


async def _days_already_billed(*, plan_id: str, doc_id: str, line_seq: Any, due_date: str,
                               period_key: str) -> int:
    """PK-08 — Σ `billable_days` nota LAIN untuk baris jatuh tempo yang sama (periode berbeda), semua status."""
    flt: Dict[str, Any] = {"due_date": due_date, "period_key": {"$ne": period_key}}
    if plan_id:
        flt.update({"plan_id": plan_id, "line_seq": line_seq})
    else:
        flt.update({"doc_id": doc_id, "plan_id": "", "line_seq": 0})
    total = 0
    async for r in db[COLL].find(flt, {"_id": 0, "billable_days": 1}):
        total += int(r.get("billable_days") or 0)
    return total


# ── Akrual (dipakai job harian & tombol "hitung sekarang") ─────────────────
async def accrue_plan(plan: Dict[str, Any], today: Optional[str] = None,
                      actor_name: str = "system") -> List[Dict[str, Any]]:
    """Bentuk / perbarui nota denda untuk semua baris yang telat pada satu jadwal hidup.

    CR-T4 — jadwal apa pun asalnya: rencana cicilan buatan orang (`origin: manual`) maupun jadwal tagihan mesin
    (`origin: term`, CR-T2). Aturan dari `penalty_policy` (PT → profil kredit pelanggan → rencana); mode mati (termasuk
    pelanggan bebas denda yang masih berlaku) → tidak ada nota baru, nota draf yang sudah ada tidak disentuh. Jadwal
    mesin pesanan yang tidak ikut piutang (bertermin tunai, `report_basis.pesanan_piutang`) dilewati seperti sebelumnya.
    "Hari ini" = tanggal buku WIB (`book_date.tanggal_buku`)."""
    from services.book_date import tanggal_buku
    day = (today or tanggal_buku())[:10]
    policy = await penalty_policy(plan.get("entity_id") or "",
                                  plan.get("customer_id") or "", plan, today=day)
    if policy["mode"] == "off":
        return []
    order = await db.sales_orders.find_one({"id": plan.get("doc_id")}, {"_id": 0}) or {}
    if plan.get("origin") == plans.ORIGIN_TERM:
        from services.report_basis import pesanan_piutang
        if not order or not pesanan_piutang(order):
            return []
    outstanding = round(plans.source_total(safe_doc(order)) - plans.source_paid(safe_doc(order)), 2)
    out: List[Dict[str, Any]] = []

    for line in plans.overdue_lines(plan, day):
        days = _days_late(line.get("due_date", ""), day)
        if days <= int(policy["grace_days"]):
            continue
        line_out = round(float(line.get("amount") or 0) - float(line.get("paid_amount") or 0), 2)
        base_amount = line_out if policy["base"] == "installment" else max(outstanding, 0.0)
        if base_amount <= EPS:
            continue
        pkey = _period_key(line.get("due_date", ""), day)
        prior = await _days_already_billed(plan_id=plan["id"], doc_id=plan.get("doc_id", ""),
                                           line_seq=line["seq"], due_date=line.get("due_date", ""), period_key=pkey)
        calc = compute_amount(base_amount, days, policy, days_prior=prior)
        if calc["billable_days"] <= 0:
            continue
        if calc["amount"] < float(policy["min_amount"]) - EPS:
            continue

        existing = await db[COLL].find_one(
            {"plan_id": plan["id"], "line_seq": line["seq"], "period_key": pkey}, {"_id": 0})
        if existing:
            # Nota yang sudah diputus manusia TIDAK boleh ditimpa mesin.
            if existing.get("status") != "draft":
                out.append(safe_doc(existing))
                continue
            # CR-T4 — usulan yang belum diputus mengikuti aturan yang berlaku sekarang (potret aturan ikut diperbarui).
            await db[COLL].update_one({"id": existing["id"], "status": "draft"}, {"$set": {
                "amount": calc["amount"], "base_amount": base_amount, "base": policy["base"],
                "days_late": calc["days_late"], "billable_days": calc["billable_days"],
                "days_prior": calc["days_prior"], "rate_pct_per_month": calc["rate_pct_per_month"],
                "grace_days": calc["grace_days"], "cap_pct": calc["cap_pct"], "policy_snapshot": policy,
                "explain": calc["explain"], "updated_at": now_iso()}})
            out.append(await get(existing["id"]))
            continue

        doc = await _create(plan, line, calc, base_amount, pkey, policy, actor_name)
        if policy["mode"] == "auto":
            doc = await issue(doc["id"], {"name": actor_name, "role": "system"}, auto=True)
        out.append(doc)
    return out


async def _create(plan: Dict[str, Any], line: Dict[str, Any], calc: Dict[str, Any],
                  base_amount: float, period_key: str, policy: Dict[str, Any],
                  actor_name: str) -> Dict[str, Any]:
    entity_id = plan.get("entity_id") or ""
    number = await next_doc_number(COLL, "number", "DN-DENDA-", entity_id=entity_id or None)
    now = now_iso()
    doc = {
        "id": new_id("pnl"), "number": number, "entity_id": entity_id,
        "doc_type": plan.get("doc_type", "sales_order"), "doc_id": plan.get("doc_id", ""),
        "doc_number": plan.get("doc_number", ""),
        "plan_id": plan.get("id", ""), "plan_number": plan.get("number", ""),
        "line_seq": line.get("seq"), "line_label": line.get("label", ""),
        "due_date": line.get("due_date", ""), "period_key": period_key,
        "customer_id": plan.get("customer_id", ""), "customer_name": plan.get("customer_name", ""),
        "base_amount": round(float(base_amount), 2), "base": policy["base"],
        "amount": calc["amount"], "original_amount": calc["amount"],
        "days_late": calc["days_late"], "billable_days": calc["billable_days"],
        "days_prior": calc.get("days_prior", 0),
        "rate_pct_per_month": calc["rate_pct_per_month"], "grace_days": calc["grace_days"],
        "cap_pct": calc["cap_pct"],
        "status": "draft", "status_label": STATUS_LABEL["draft"],
        "paid_amount": 0.0, "je_id": "", "je_number": "",
        "reason_code": "", "reason_label": "", "decision_note": "",
        "decided_by": "", "decided_at": "", "approval_request_id": "",
        "policy_snapshot": policy, "explain": calc["explain"],
        "created_by": actor_name, "created_at": now, "updated_at": now, "refs": [],
    }
    try:
        await db[COLL].insert_one(dict(doc))
    except Exception as exc:  # noqa: BLE001
        # PK-14 (W6) — nota untuk baris & periode ini sudah ada (akrual bersamaan): kembalikan yang ada.
        from indexes import is_duplicate_on
        if is_duplicate_on(exc, "period_key"):
            prior = await db[COLL].find_one({"doc_id": doc["doc_id"], "plan_id": doc["plan_id"],
                                             "line_seq": doc["line_seq"], "period_key": period_key}, {"_id": 0})
            if prior:
                return safe_doc(prior)
        raise
    # FASE G-4 — nota denda WAJIB menyebut dokumen sumbernya (bisa ditelusuri dua arah).
    from services import doc_refs_service as _refs
    await _refs.safe_link(("penalty", doc["id"]), (doc["doc_type"], doc["doc_id"]),
                          "parent", note=f"denda keterlambatan {line.get('label', '')}")
    await _notify(doc)
    return safe_doc(doc)


async def accrue_for_order(order_id: str, today: Optional[str] = None,
                           actor_name: str = "system") -> List[Dict[str, Any]]:
    """CR-T4 — nota denda satu pesanan dari JADWAL HIDUP-nya (rencana cicilan atau jadwal tagihan mesin CR-T2).

    Pengganti `accrue_order` (D8, dihapus): jalur lama memperlakukan pesanan tanpa rencana sebagai satu baris
    bertempo "tanggal pesanan + termin profil"; kini setiap pesanan yang menimbulkan piutang punya jadwal tagihan per
    surat jalan, jadi denda selalu lahir dari baris jadwal (`accrue_plan`). Pesanan tanpa jadwal tersimpan (data lama
    sebelum `scripts/build_billing_schedule.py --apply`) belum melahirkan nota."""
    plan = await plans.get_active("sales_order", order_id or "")
    if not plan or plan.get("status") != "active":
        return []
    return await accrue_plan(plan, today=today, actor_name=actor_name)


async def accrue_customer(customer_id: str, today: Optional[str] = None,
                          actor_name: str = "system") -> List[Dict[str, Any]]:
    """Hitung denda untuk SEMUA jadwal hidup satu pelanggan (tombol "Buat Nota Denda" laporan Umur Piutang).

    CR-T4 — memindai jadwal `active` apa pun asalnya (`origin` `term` maupun `manual`); cabang "pesanan tanpa rencana"
    dihapus karena pesanan itu kini punya jadwal tagihan (CR-T2). Kolom denda estimasi berubah menjadi dokumen nyata
    yang bisa ditagih, dinegosiasikan, atau dibebaskan.
    """
    out: List[Dict[str, Any]] = []
    async for row in db[plans.COLL].find({"customer_id": customer_id, "status": "active"}, {"_id": 0}):
        out.extend(await accrue_plan(safe_doc(row), today=today, actor_name=actor_name))
    return out


async def for_docs(doc_ids: List[str]) -> Dict[str, List[Dict[str, Any]]]:
    """Nota denda per dokumen sumber (dipakai laporan Umur Piutang menautkan kolomnya)."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    if not doc_ids:
        return out
    async for r in db[COLL].find({"doc_id": {"$in": list(doc_ids)}}, {"_id": 0}):
        out.setdefault(r.get("doc_id", ""), []).append(safe_doc(r))
    for rows in out.values():
        rows.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return out


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ringkasan nota denda: berapa yang masih usulan, terbit, dibebaskan, dibayar."""
    draft = issued = waived = paid = 0.0
    counts = {s: 0 for s in STATUSES}
    for r in rows or []:
        st = r.get("status", "draft")
        counts[st] = counts.get(st, 0) + 1
        amt = float(r.get("amount") or 0)
        if st == "draft":
            draft += amt
        elif st in ("issued", "adjusted"):
            issued += amt - float(r.get("paid_amount") or 0)
        elif st == "waived":
            waived += float(r.get("waived_amount") or 0)
        elif st == "paid":
            paid += float(r.get("paid_amount") or amt)
    return {"count": len(rows or []), "counts": counts,
            "draft_amount": round(draft, 2), "issued_outstanding": round(issued, 2),
            "waived_amount": round(waived, 2), "paid_amount": round(paid, 2),
            "actual_amount": round(draft + issued, 2)}


async def _notify(doc: Dict[str, Any]) -> None:
    try:
        from services import notification_service as ns
        await ns.create_notification(
            notif_type="penalty_draft", severity="warning",
            title=f"Usulan denda {doc['number']} · {doc.get('customer_name', '')}",
            body=(f"{doc.get('line_label', '')} pada {doc.get('doc_number', '')} telat "
                  f"{doc.get('days_late', 0)} hari — usulan denda {rupiah(doc['amount'])}. "
                  "Masih bisa dinegosiasikan / dibebaskan.").replace(",", "."),
            link="payment-plans", entity_id=doc.get("entity_id"),
            recipient_role="manager", ref=doc["id"], dedupe_scope="day")
    except Exception:  # noqa: BLE001 — notifikasi best-effort
        return


# ── Siklus keputusan ──────────────────────────────────────────────────
async def _saldo(p: Dict[str, Any]) -> None:
    """CR-T2 — nota denda terbit, dibayar, dibebaskan, atau diubah → saldo piutang tersimpan pasangan dihitung ulang
    (turunan; galatnya tidak membatalkan nota)."""
    from services import customer_balance_service as _cbs
    await _cbs.refresh_safe(p.get("customer_id") or "", p.get("entity_id") or "")


async def get(penalty_id: str) -> Optional[Dict[str, Any]]:
    row = await db[COLL].find_one({"id": penalty_id}, {"_id": 0})
    return safe_doc(row) if row else None


async def _reason_or_fail(reason_code: str) -> Dict[str, Any]:
    code = (reason_code or "").strip()
    if not code:
        raise PenaltyError("Label alasan wajib dipilih — denda tidak boleh hilang tanpa sebab.")
    from services.amendment_service import ensure_reasons
    await ensure_reasons()
    row = await db.amendment_reasons.find_one({"code": code}, {"_id": 0})
    if not row or row.get("active") is False or row.get("status") not in (None, "active"):
        raise PenaltyError(f"Label alasan '{code}' tidak terdaftar / sudah tidak aktif.")
    applies = row.get("applies_to") or []
    if applies and REASON_DOC_TYPE not in applies:
        raise PenaltyError(f"Label alasan '{row['label']}' tidak berlaku untuk denda.")
    return safe_doc(row)


async def issue(penalty_id: str, actor: Dict[str, Any], auto: bool = False) -> Dict[str, Any]:
    """Terbitkan denda → jurnal Dr Piutang Denda / Cr Pendapatan Denda (sekali saja)."""
    p = await get(penalty_id)
    if not p:
        raise PenaltyError("Nota denda tidak ditemukan.")
    if p["status"] != "draft":
        raise PenaltyError(f"Nota denda sudah berstatus '{STATUS_LABEL.get(p['status'], p['status'])}'.")
    if float(p["amount"]) <= EPS:
        raise PenaltyError("Nominal denda nol — tidak ada yang bisa diterbitkan.")
    from services.book_date import periksa_periode_dokumen   # PK-37 (K-03) — PERIKSA periode jurnal terbit (hari ini)
    await periksa_periode_dokumen(p.get("entity_id", ""), None, jenis="nota denda")
    je = await gl_service.post_penalty_issue(
        penalty_id=p["id"], entity_id=p.get("entity_id", ""), amount=float(p["amount"]),
        label=f"{p['number']} · {p.get('customer_name', '')}",
        date=now_iso(), created_by=actor.get("name", "system"))
    await db[COLL].update_one({"id": p["id"]}, {"$set": {
        "status": "issued", "status_label": STATUS_LABEL["issued"],
        "je_id": (je or {}).get("id", ""), "je_number": (je or {}).get("number", ""),
        "issued_by": actor.get("name", "system"), "issued_at": now_iso(),
        "issued_auto": bool(auto), "updated_at": now_iso()}})
    await _saldo(p)   # CR-T2 — saldo piutang tersimpan pasangan (pelanggan, PT)
    return await get(p["id"])


def _pesan_penyetuju(aksi: str, peran: str) -> str:
    """§3 Z6 — pesan untuk manusia: label peran (bukan id `manager`), dan langkah yang benar-benar ada (belum ada alur
    "ajukan" untuk denda: yang membebaskan/mengubah harus pemegang peran penyetuju itu sendiri). Uji peran kustom
    18 Nov (agen A): pesan lama "wajib disetujui manager — ajukan lewat penyetuju"."""
    ids = [peran or "manager", "admin"]
    labels = list(dict.fromkeys(role_label(x) for x in ids + setara_untuk(ids)))   # K-FIN-01: + peran setara
    siapa = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " atau " + labels[-1]
    return (f"{aksi} wajib diputus {siapa}. Minta pemegang peran itu yang melakukannya "
            "(penyetujunya diatur Admin di Pengaturan: Pembayaran pelanggan › Denda telat bayar).")


async def _needs_approval(p: Dict[str, Any]) -> Dict[str, Any]:
    policy = await penalty_policy(p.get("entity_id", ""), p.get("customer_id", ""))
    return {"required": bool(policy["waive_requires_approval"]),
            "role": policy["approver_role"]}


async def waive(penalty_id: str, reason_code: str, note: str,
                actor: Dict[str, Any]) -> Dict[str, Any]:
    """Bebaskan denda. Bila sudah berjurnal → JE PEMBALIK (ledger append-only)."""
    p = await get(penalty_id)
    if not p:
        raise PenaltyError("Nota denda tidak ditemukan.")
    if p["status"] in ("waived", "paid"):
        raise PenaltyError(f"Nota denda sudah '{STATUS_LABEL.get(p['status'], p['status'])}'.")
    if p["status"] in ("issued", "adjusted"):   # PK-37 (K-03) — berjurnal pembalik hari ini: PERIKSA periode
        from services.book_date import periksa_periode_dokumen
        await periksa_periode_dokumen(p.get("entity_id", ""), None, jenis="nota denda")
    reason = await _reason_or_fail(reason_code)
    appr = await _needs_approval(p)
    if appr["required"] and not role_in((actor.get("role") or ""), (appr["role"], "admin")):
        raise PenaltyError(_pesan_penyetuju("Pembebasan denda", appr["role"]))
    # PK-08 (FX-03) — yang dibebaskan hanya SISA yang belum dibayar; bagian terbayar tetap pendapatan denda.
    paid = round(float(p.get("paid_amount") or 0), 2)
    rest = round(float(p.get("amount") or 0) - paid, 2)
    if rest <= EPS:
        raise PenaltyError("Nota denda sudah lunas — tidak ada sisa yang bisa dibebaskan.")
    # KF-T6 — penerbit nota denda ≠ yang membebaskannya dari `kontrol.pengurang_piutang.*` (bawaan satu orang). Diperiksa
    # sebelum jurnal pembalik. PK-38 — batas nominal kunci ini kini khusus pengurang piutang tanpa uang masuk
    # (`services/ar_reduction_guard.py:TANPA_KAS`, bawaan Rp 1.000.000); bebas denda tidak termasuk → jumlah orang saja.
    from services import dual_control as _dc
    await _dc.tolak_bila_pelaku_sama("pengurang_piutang", p, actor, p.get("entity_id", ""), nominal=0.0,
                                     pengaju=[p.get("created_by_id"), p.get("created_by")])
    je = None
    if p["status"] in ("issued", "adjusted"):
        je = await gl_service.post_penalty_reversal(
            penalty_id=p["id"], entity_id=p.get("entity_id", ""), amount=rest,
            label=f"Pembebasan denda {p['number']} · {reason['label']}",
            date=now_iso(), created_by=actor.get("name", "system"), suffix="waive")
    await db[COLL].update_one({"id": p["id"]}, {"$set": {
        "status": "waived", "status_label": STATUS_LABEL["waived"],
        "waived_amount": rest, "amount": paid,
        "reason_code": reason["code"], "reason_label": reason["label"],
        "decision_note": (note or "").strip(),
        "decided_by": actor.get("name", ""), "decided_at": now_iso(),
        "approver_role_required": appr["role"] if appr["required"] else "",
        "reversal_je_id": (je or {}).get("id", ""),
        "updated_at": now_iso()}})
    await _saldo(p)   # CR-T2 — saldo piutang tersimpan pasangan (pelanggan, PT)
    return await get(p["id"])


async def adjust(penalty_id: str, new_amount: float, reason_code: str, note: str,
                 actor: Dict[str, Any]) -> Dict[str, Any]:
    """Ubah nominal denda (negosiasi). Bila sudah berjurnal → JE SELISIH."""
    p = await get(penalty_id)
    if not p:
        raise PenaltyError("Nota denda tidak ditemukan.")
    if p["status"] in ("waived", "paid"):
        raise PenaltyError(f"Nota denda sudah '{STATUS_LABEL.get(p['status'], p['status'])}'.")
    amt = round(float(new_amount or 0), 2)
    if amt < 0:
        raise PenaltyError("Nominal denda tidak boleh negatif.")
    if amt > round(float(p["amount"]), 2) + EPS:
        raise PenaltyError("Nominal baru tidak boleh lebih besar dari denda semula — "
                           "terbitkan nota denda baru bila memang bertambah.")
    paid = round(float(p.get("paid_amount") or 0), 2)
    if amt < paid - EPS:   # PK-08 — tidak boleh di bawah yang sudah dibayar (piutang denda jadi minus)
        raise PenaltyError(f"Nominal baru tidak boleh lebih kecil dari yang sudah dibayar ({rupiah(paid)})."
                           .replace(",", "."))
    if p["status"] in ("issued", "adjusted") and round(float(p["amount"]) - amt, 2) > EPS:
        # PK-37 (K-03) — berjurnal selisih hari ini: PERIKSA periode sebelum apa pun ditulis.
        from services.book_date import periksa_periode_dokumen
        await periksa_periode_dokumen(p.get("entity_id", ""), None, jenis="nota denda")
    reason = await _reason_or_fail(reason_code)
    appr = await _needs_approval(p)
    if appr["required"] and not role_in((actor.get("role") or ""), (appr["role"], "admin")):
        raise PenaltyError(_pesan_penyetuju("Perubahan nominal denda", appr["role"]))
    delta = round(float(p["amount"]) - amt, 2)
    je = None
    issued = p["status"] in ("issued", "adjusted")
    seq = len(p.get("adjustments") or []) + 1
    if issued and delta > EPS:
        # PK-08 (FX-02) — kunci jurnal PER kejadian (`adjust:<seq>`): ubah nominal kedua tidak lagi dilewati.
        je = await gl_service.post_penalty_reversal(
            penalty_id=p["id"], entity_id=p.get("entity_id", ""), amount=delta,
            label=f"Penyesuaian denda {p['number']} · {reason['label']}",
            date=now_iso(), created_by=actor.get("name", "system"), suffix=f"adjust:{seq}")
    full = issued and paid > EPS and abs(amt - paid) <= EPS
    status = ("paid" if full else "adjusted") if issued else "draft"
    extra: Dict[str, Any] = {}
    if issued:
        extra["$push"] = {"adjustments": {
            "seq": seq, "from": float(p["amount"]), "to": amt, "delta": delta, "reason_code": reason["code"],
            "je_id": (je or {}).get("id", ""), "at": now_iso(), "by": actor.get("name", "")}}
    await db[COLL].update_one({"id": p["id"]}, {**extra, "$set": {
        "status": status, "status_label": STATUS_LABEL[status],
        **({"paid_at": now_iso()} if full else {}),
        "amount": amt, "adjusted_from": float(p["amount"]),
        "reason_code": reason["code"], "reason_label": reason["label"],
        "decision_note": (note or "").strip(),
        "decided_by": actor.get("name", ""), "decided_at": now_iso(),
        "approver_role_required": appr["role"] if appr["required"] else "",
        "adjust_je_id": (je or {}).get("id", ""),
        "updated_at": now_iso()}})
    await _saldo(p)   # CR-T2 — saldo piutang tersimpan pasangan (pelanggan, PT)
    return await get(p["id"])


def _pay_id(penalty_id: str, intent_key: str) -> str:
    import hashlib
    if intent_key:
        return "pnp_" + hashlib.sha256(f"{penalty_id}|{intent_key}".encode()).hexdigest()[:16]
    return new_id("pnp")


async def pay(penalty_id: str, amount: float, method: str, actor: Dict[str, Any], *,
              account_id: str = "", intent_key: str = "") -> Dict[str, Any]:
    """PK-08 (FX-02, D1) — terima pembayaran denda LEWAT KAS (02_STANDAR §1):

    PERIKSA (tanpa tulis) → NIAT (butir `payments` berstatus `pending`, bersyarat) → EFEK (kas `cash_pnl_<id>` lalu
    `paid_amount` + butir `applied`) → JURNAL (`post_cash_durable`: Dr Kas/Bank / Cr 1-1270, tahan-gagal) → SELESAI
    (butir `done`; lunas → `paid`). `Idempotency-Key` yang sama melanjutkan butir yang sama dari statusnya."""
    p = await get(penalty_id)
    if not p:
        raise PenaltyError("Nota denda tidak ditemukan.")
    pay_id = _pay_id(p["id"], intent_key)
    item = next((x for x in (p.get("payments") or []) if x.get("id") == pay_id), None)
    if item:
        return await _resume_payment(p, item, actor)
    # ── PERIKSA ─────────────────────────────────────────────────────────
    if p["status"] not in ("issued", "adjusted"):
        raise PenaltyError("Denda harus DITERBITKAN dulu sebelum bisa menerima pembayaran.")
    # PK-37 (K-03) — PERIKSA periode buku hari ini (sakelar per PT); `preflight_posting` di bawah tetap tanpa syarat.
    from services.book_date import periksa_periode_dokumen
    await periksa_periode_dokumen(p.get("entity_id", ""), None, jenis="nota denda")
    amt = round(float(amount or 0), 2)
    paid_read = round(float(p.get("paid_amount") or 0), 2)
    pending = round(sum(float(x.get("amount") or 0) for x in (p.get("payments") or [])
                        if x.get("status") == "pending"), 2)
    outstanding = round(float(p["amount"]) - paid_read - pending, 2)
    if amt <= EPS:
        raise PenaltyError("Nominal pembayaran harus lebih dari nol.")
    if amt > outstanding + EPS:
        raise PenaltyError(f"Pembayaran melebihi sisa denda ({rupiah(outstanding)})."
                           .replace(",", "."))
    # PM-T1 — cara bayar dari daftar induk (kata lama → kode kanonik; tak dikenal / nonaktif → galat) sebelum niat lahir.
    from services import payment_method_service as _pms
    try:
        method = (await _pms.wajib(p.get("entity_id", ""), method or "transfer", arah="masuk"))["code"]
    except _pms.CaraBayarError as exc:
        raise PenaltyError(str(exc)) from exc
    if not (account_id or "").strip():
        raise PenaltyError("Rekening penerima wajib dipilih.")
    acc = await db.bank_accounts.find_one({"id": account_id}, {"_id": 0})
    if (not acc or acc.get("status") == "inactive" or acc.get("is_active") is False
            or (acc.get("entity_id") or "") != (p.get("entity_id") or "")):
        raise PenaltyError("Rekening tidak ditemukan atau bukan milik PT nota denda ini.")
    from services import bank_service
    entity_id = p.get("entity_id", "")
    cash = {
        "id": f"cash_pnl_{pay_id}", "cash_type": bank_service.account_cash_type(acc), "direction": "in",
        "amount": amt, "category": "denda keterlambatan", "description": f"Pembayaran denda {p['number']}",
        "entity_id": entity_id, "owner_entity_id": entity_id, "ref_type": "penalty", "ref_id": p["id"],
        "account_id": account_id, "method": method or "transfer", "contra_account_code": gl_service.ACC_PIUTANG_DENDA,
        "reconciled": False, "status": "posted", "created_by": actor.get("name", "system"),
    }
    # Periode & akun diperiksa dengan baris yang SAMA dengan jurnal kas nanti (melempar ClosedPeriodError /
    # JournalValidationError → router 409, tanpa tulisan apa pun).
    await gl_service.preflight_posting(entity_id)
    await gl_service.account_for("penjualan.piutang_denda", entity_id)
    await gl_service.preflight_entry(
        lines=gl_service._balanced_pair(await gl_service._cash_account(cash), gl_service.ACC_PIUTANG_DENDA, amt,
                                        "preflight"),
        entity_id=entity_id, source_type="cash_transaction")
    # ── NIAT ────────────────────────────────────────────────────────────
    item = {"id": pay_id, "amount": amt, "method": method or "transfer", "account_id": account_id,
            "cash_txn_id": cash["id"], "status": "pending", "at": now_iso(), "by": actor.get("name", ""),
            "cash_doc": cash}
    res = await db[COLL].update_one(
        {"id": p["id"], "status": {"$in": ["issued", "adjusted"]}, "paid_amount": p.get("paid_amount") or 0.0,
         "payments.status": {"$ne": "pending"}, "payments.id": {"$ne": pay_id}},
        {"$push": {"payments": item}, "$set": {"updated_at": now_iso()}})
    if not res.matched_count:
        fresh = await get(p["id"]) or {}
        again = next((x for x in (fresh.get("payments") or []) if x.get("id") == pay_id), None)
        if again:
            return await _resume_payment(fresh, again, actor)
        raise PenaltyConflict("Nota denda berubah saat diproses — muat ulang lalu coba lagi.")
    return await _resume_payment(await get(p["id"]), item, actor)


async def _resume_payment(p: Dict[str, Any], item: Dict[str, Any], actor: Dict[str, Any]) -> Dict[str, Any]:
    """Lanjutkan satu butir pembayaran dari statusnya (`pending` → `applied` → `done`). Idempoten."""
    if item.get("status") == "done":
        return p
    cash = dict(item.get("cash_doc") or {})
    cid = item.get("cash_txn_id") or cash.get("id", "")
    from services import cash_ledger   # PK-20 — kas & jurnalnya lewat pembuat kas satu pintu (tahan-gagal)
    gl_err = ""
    # ── EFEK ────────────────────────────────────────────────────────────
    if item.get("status") == "pending":
        try:
            await cash_ledger.create_cash(
                entity_id=cash.get("entity_id", ""), direction="in", amount=float(item["amount"]), ref_type="penalty",
                ref_id=p["id"], seq=item["id"], txn_id=cid, account_id=cash.get("account_id", ""),
                cash_type=cash.get("cash_type", ""), category=cash.get("category", ""),
                description=cash.get("description", ""), contra_account_code=cash.get("contra_account_code", ""),
                owner_entity_id=cash.get("owner_entity_id", ""), actor=cash.get("created_by", "system"),
                extra={"method": cash.get("method") or "transfer"})
        except cash_ledger.CashPostingError as exc:   # kas tercatat `failed`; pembayaran tetap diterapkan
            gl_err = exc.error
        await db[COLL].update_one(
            {"id": p["id"], "payments": {"$elemMatch": {"id": item["id"], "status": "pending"}}},
            {"$inc": {"paid_amount": float(item["amount"])},
             "$set": {"payments.$.status": "applied", "updated_at": now_iso()}})
    else:
        # ── JURNAL (tahan-gagal) — butir `applied`: kas sudah ada, jurnalnya dipastikan ─────────────────────────
        try:
            await cash_ledger.ensure_posted(cid)
        except cash_ledger.CashPostingError as exc:
            gl_err = exc.error
    if gl_err:   # kas sudah tercatat; jurnal diulang dari panel atau kirim ulang
        raise PenaltyConflict(f"Pembayaran denda sudah tercatat, tetapi jurnalnya gagal: {gl_err[:200]}. "
                              "Ulangi dari Keuangan › Posting Gagal.")
    # ── SELESAI ─────────────────────────────────────────────────────────
    await db[COLL].update_one({"id": p["id"], "payments.id": item["id"]},
                              {"$set": {"payments.$.status": "done", "updated_at": now_iso()}})
    fresh = await get(p["id"]) or {}
    if fresh.get("status") in ("issued", "adjusted") and \
            float(fresh.get("paid_amount") or 0) >= round(float(fresh.get("amount") or 0), 2) - EPS:
        await db[COLL].update_one({"id": p["id"], "status": {"$in": ["issued", "adjusted"]}}, {"$set": {
            "status": "paid", "status_label": STATUS_LABEL["paid"], "paid_at": now_iso(), "updated_at": now_iso()}})
    await _saldo(p)   # CR-T2 — saldo piutang tersimpan pasangan (pelanggan, PT)
    return await get(p["id"])


# ── Pembacaan & invarian ──────────────────────────────────────────────
async def list_penalties(entity_id: str = "", status: str = "", doc_id: str = "",
                        q: str = "", limit: int = 200, customer_id: str = "") -> List[Dict[str, Any]]:
    flt: Dict[str, Any] = {}
    if customer_id:   # CR-T5 — kartu pelanggan › tab Tagihan (nota denda satu pelanggan)
        flt["customer_id"] = customer_id
    # FASE E-0 (L4) — dukung filter entitas siap-pakai dari `entity_scope.scope_value()`.
    if isinstance(entity_id, dict):
        flt["entity_id"] = entity_id
    elif entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    if status:
        flt["status"] = status
    if doc_id:
        flt["doc_id"] = doc_id
    if q:
        import re as _re
        rx = _re.compile(_re.escape(q), _re.I)
        flt["$or"] = [{"number": rx}, {"doc_number": rx}, {"customer_name": rx}]
    rows = await db[COLL].find(flt, {"_id": 0}).sort("created_at", -1).to_list(int(limit))
    return [safe_doc(r) for r in rows]


async def stats(entity_id: Any = "") -> Dict[str, Any]:
    flt: Dict[str, Any] = {}
    if isinstance(entity_id, dict):
        flt["entity_id"] = entity_id
    elif entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    out = {s: 0 for s in STATUSES}
    draft_amount = issued_outstanding = waived_amount = 0.0
    async for r in db[COLL].find(flt, {"_id": 0, "status": 1, "amount": 1, "paid_amount": 1,
                                       "waived_amount": 1}):
        st = r.get("status", "draft")
        out[st] = out.get(st, 0) + 1
        if st == "draft":
            draft_amount += float(r.get("amount") or 0)
        elif st in ("issued", "adjusted"):
            issued_outstanding += float(r.get("amount") or 0) - float(r.get("paid_amount") or 0)
        elif st == "waived":
            waived_amount += float(r.get("waived_amount") or 0)
    return {**out, "draft_amount": round(draft_amount, 2),
            "issued_outstanding": round(issued_outstanding, 2),
            "waived_amount": round(waived_amount, 2)}


async def outstanding_total(entity_id: str = "") -> float:
    """Σ denda terbit yang belum dibayar — bahan INV-PEN-03 (dibanding saldo GL)."""
    flt: Dict[str, Any] = {"status": {"$in": ["issued", "adjusted"]}}
    if entity_id and entity_id != "all":
        flt["entity_id"] = entity_id
    total = 0.0
    async for r in db[COLL].find(flt, {"_id": 0, "amount": 1, "paid_amount": 1}):
        total += float(r.get("amount") or 0) - float(r.get("paid_amount") or 0)
    return round(total, 2)


async def drafts_with_journal(limit: int = 20) -> List[Dict[str, Any]]:
    """Bahan INV-PEN-01: denda draft yang (salah) punya jurnal."""
    bad: List[Dict[str, Any]] = []
    async for r in db[COLL].find({"status": "draft"}, {"_id": 0, "id": 1, "number": 1}):
        if await db.journal_entries.find_one(
                {"source_type": "penalty", "source_id": r["id"], "status": {"$ne": "void"}},
                {"_id": 1}):
            bad.append({"id": r["id"], "number": r.get("number", r["id"])})
            if len(bad) >= limit:
                break
    return bad


async def decided_without_reason(limit: int = 20) -> List[Dict[str, Any]]:
    """Bahan INV-PEN-02: keputusan bebas/ubah tanpa alasan atau tanpa pemutus."""
    bad: List[Dict[str, Any]] = []
    async for r in db[COLL].find({"status": {"$in": ["waived", "adjusted"]}},
                                 {"_id": 0, "id": 1, "number": 1, "status": 1,
                                  "reason_code": 1, "decided_by": 1}):
        if not (r.get("reason_code") or "").strip() or not (r.get("decided_by") or "").strip():
            bad.append({"id": r["id"], "number": r.get("number", r["id"]),
                        "status": r.get("status")})
            if len(bad) >= limit:
                break
    return bad


# ── Job penjadwal ─────────────────────────────────────────────────────
async def job_penalty_accrual(today: Optional[str] = None) -> Dict[str, Any]:
    """Pindai seluruh jadwal hidup → bentuk/perbarui usulan denda. Idempotent per periode.

    CR-T4 — semua jadwal `active` (`origin` `term` jadwal tagihan CR-T2 maupun `manual` rencana cicilan), jadi pesanan
    tanpa rencana cicilan ikut terhitung. `today` kosong = tanggal buku WIB. Jawaban memuat jumlah per asal jadwal
    (`by_origin`) — bahan laporan RISIKO "putaran pertama" unit."""
    from services.book_date import tanggal_buku
    day = (today or tanggal_buku())[:10]
    created = updated = 0
    scanned = 0
    by_origin: Dict[str, Dict[str, int]] = {}
    async for row in db[plans.COLL].find({"status": "active"}, {"_id": 0}):
        plan = safe_doc(row)
        scanned += 1
        before = await db[COLL].count_documents({"plan_id": plan["id"]})
        rows = await accrue_plan(plan, today=day, actor_name="scheduler")
        after = await db[COLL].count_documents({"plan_id": plan["id"]})
        lahir = max(0, after - before)
        created += lahir
        updated += max(0, len(rows) - lahir)
        o = by_origin.setdefault(plan.get("origin") or "manual", {"scanned": 0, "created": 0})
        o["scanned"] += 1
        o["created"] += lahir
    return {"scanned_plans": scanned, "created": created, "updated": updated, "by_origin": by_origin, "as_of": day}
