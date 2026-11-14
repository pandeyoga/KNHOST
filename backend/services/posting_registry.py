"""PK-18 (GL-02, GL-12, IV-04) — registri jenis dokumen yang menjurnal: SATU tempat panel Posting Gagal membaca
koleksi, saringan "jurnal gagal", nomor, nominal, dan jalur ulang tiap jenis (`02_STANDAR.md` §1 P3).

`KINDS[kind]`:
  label            judul tab panel
  collection       koleksi dokumen sumber (dikenal `scripts/verify_contract.py`)
  failed_query     saringan dokumen yang jurnalnya gagal
  entity_field     field PT dokumen (cakupan pengguna)
  number_field     field nomor dokumen; amount_field = field nominal (str, atau tuple: yang pertama terisi)
  status_field     field status jurnal (`gl_status` dan kerabatnya); error_field = pesan galat terakhir
  failed_at_field  urutan panel (terbaru dulu)
  doc_type         jenis dokumen di `doc_refs_service.DOC_TYPES` (tautan ke dokumennya, `02` L8)
  posters          nama fungsi `gl_service` yang dicakup jenis ini (dibaca penjaga `verify_posting_coverage`)
  retry            `async retry(doc, actor) -> None` — menerbitkan jurnal yang kurang TEPAT SEKALI: semua fungsi
                   `post_*` yang dipanggil memeriksa `_already_posted`, jadi ulang tidak menggandakan jurnal. Gagal lagi →
                   melempar (router: 409 "Posting masih gagal: …", penanda galat diperbarui `post_durable`)

`KINDS` sengaja berupa literal: penjaga statik membacanya tanpa mengimpor aplikasi. Jenis dari PK-05 (`contra_bon`),
PK-06 (`interco_*`) dan PK-30 (`interco_adj`) dipindahkan dari `routers/posting_failures.py` apa adanya.
"""
from typing import Any, Dict, List

from core_utils import now_iso
from db import db

#: Jenis lama yang nominalnya diambil dari field pertama yang terisi (perilaku panel sebelum PK-18).
_NOMINAL_LAMA = ("amount", "grand_total", "total_applied", "gl_posting.amount", "qty")


def pick(doc: Dict[str, Any], dotted: str) -> Any:
    for k in dotted.split("."):
        doc = (doc or {}).get(k) if isinstance(doc, dict) else None
    return doc


def _gagal_dari(res: Dict[str, Any]) -> None:
    """Hasil ulang jurnal kembar (PK-06) per sisi → lempar bila masih ada sisi yang gagal."""
    gagal = [v.get("error") for v in (res or {}).values() if isinstance(v, dict) and v.get("status") == "failed"]
    if gagal:
        raise RuntimeError("; ".join(str(g) for g in gagal))


# ── Jalur ulang per jenis ────────────────────────────────────────────────────────────────────────────────────────────
async def _retry_cash(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services import gl_service as gl
    await gl.post_cash_durable(doc)
    if doc.get("ref_type") == "ar_receipt" and doc.get("ref_id"):
        await db.ar_receipts.update_one({"id": doc["ref_id"]}, {"$set": {"gl_status": "posted", "gl_error": ""}})
    if doc.get("payment_intent_id"):   # PK-05 — ringkasan jurnal di niat bayar ikut diperbarui
        from services.ap_payment_service import refresh_gl_status
        await refresh_gl_status(doc["payment_intent_id"])


async def _retry_ar_receipt(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.ar_receipt_service import repost_receipt
    await repost_receipt(doc["id"])


async def _retry_purchase_return(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.purchase_return_service import approve_and_adjust_stock
    await approve_and_adjust_stock(doc["id"], approved_by=actor["name"])


async def _retry_goods_receipt(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.goods_receipt_close_service import _ensure_gr_posted
    await _ensure_gr_posted(doc["id"])


async def _retry_shipment(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services import gl_service as gl
    await gl.post_order_revenue_and_cogs(doc["order_id"])
    await db.shipments.update_one({"id": doc["id"]}, {"$set": {"gl_status": "posted", "gl_error": "",
                                                               "updated_at": now_iso()}})


async def _retry_contra_bon(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.ap_payment_service import repost_contra_bon
    await repost_contra_bon(doc["id"])


async def _retry_interco_transaction(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.interco_service import repost_gl
    _gagal_dari(await repost_gl(doc["pair_id"], actor["name"]))


async def _retry_interco_adj(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.interco_service import repost_length_adjustment
    _gagal_dari(await repost_length_adjustment(doc["pair_id"], actor["name"]))


async def _retry_interco_return(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.interco_return_service import repost_gl
    _gagal_dari(await repost_gl(doc["return_pair_id"], actor["name"]))


async def _retry_interco_settlement(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.interco_service import repost_settlement_gl
    _gagal_dari(await repost_settlement_gl(doc["id"], actor["name"]))


# ── Registri ─────────────────────────────────────────────────────────────────────────────────────────────────────────
KINDS: Dict[str, Dict[str, Any]] = {
    "cash_transaction": {
        "label": "Transaksi Kas", "collection": "cash_transactions", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "cash_transaction", "posters": ("post_cash_transaction",), "retry": _retry_cash},
    "ar_receipt": {
        "label": "Kwitansi AR", "collection": "ar_receipts", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "ar_receipt", "posters": ("post_deposit_only_receipt",), "retry": _retry_ar_receipt},
    "purchase_return": {
        "label": "Retur Beli", "collection": "purchase_returns", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "purchase_return", "posters": ("post_purchase_return",), "retry": _retry_purchase_return},
    "goods_receipt": {
        "label": "Penerimaan Barang (GR)", "collection": "wms_tasks", "failed_query": {"gl_posting.status": "failed"},
        "entity_field": "gl_posting.entity_id", "number_field": "po_number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_posting.status", "error_field": "gl_posting.error", "failed_at_field": "gl_posting.at",
        "doc_type": "grn", "posters": ("post_goods_receipt",), "retry": _retry_goods_receipt},
    "shipment": {
        "label": "Surat Jalan", "collection": "shipments", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "shipment_no", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "shipment",
        "posters": ("post_order_revenue_and_cogs", "post_shipment_revenue", "post_shipment_cogs", "post_sales_order",
                    "post_order_cogs", "post_advance_reclass"),
        "retry": _retry_shipment},
    "contra_bon": {   # PK-05 — jurnal potongan
        "label": "Kontrabon (jurnal potongan)", "collection": "contra_bons", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "contra_bon", "posters": ("post_contra_bon_deduction",), "retry": _retry_contra_bon},
    # PK-06 — jurnal kembar antar-PT, satu baris per SISI (PT) yang gagal; jurnalnya lewat `twin_journal.post_twin`
    "interco_transaction": {
        "label": "Transaksi Antar-PT", "collection": "interco_transactions", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "interco_transaction", "posters": (), "retry": _retry_interco_transaction},
    "interco_return": {
        "label": "Retur Antar-PT", "collection": "interco_returns", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "interco_return", "posters": (), "retry": _retry_interco_return},
    "interco_settlement_payer": {
        "label": "Pelunasan Antar-PT (pembayar)", "collection": "interco_settlements",
        "failed_query": {"gl_status_payer": "failed"}, "entity_field": "payer_entity_id", "number_field": "number",
        "amount_field": _NOMINAL_LAMA, "status_field": "gl_status_payer", "error_field": "gl_error_payer",
        "failed_at_field": "updated_at", "doc_type": "interco_settlement", "posters": (),
        "retry": _retry_interco_settlement},
    "interco_settlement_payee": {
        "label": "Pelunasan Antar-PT (penerima)", "collection": "interco_settlements",
        "failed_query": {"gl_status_payee": "failed"}, "entity_field": "payee_entity_id", "number_field": "number",
        "amount_field": _NOMINAL_LAMA, "status_field": "gl_status_payee", "error_field": "gl_error_payee",
        "failed_at_field": "updated_at", "doc_type": "interco_settlement", "posters": (),
        "retry": _retry_interco_settlement},
    # PK-30 — jurnal penyesuaian panjang roll antar-PT; nominal & galat milik jurnal penyesuaian, bukan konfirmasi
    "interco_adj": {
        "label": "Penyesuaian Panjang Antar-PT", "collection": "interco_transactions",
        "failed_query": {"gl_status_adj": "failed"}, "entity_field": "entity_id", "number_field": "number",
        "amount_field": "length_adjustment.delta_total", "amount_abs": True, "status_field": "gl_status_adj",
        "error_field": "gl_error_adj", "failed_at_field": "updated_at", "doc_type": "interco_transaction",
        "posters": (), "retry": _retry_interco_adj},
}

LABELS: Dict[str, str] = {k: v["label"] for k, v in KINDS.items()}


# ── Pembaca yang dipakai router ──────────────────────────────────────────────────────────────────────────────────────
def _amount(spec: Dict[str, Any], doc: Dict[str, Any]) -> float:
    fields = spec["amount_field"]
    for f in (fields if isinstance(fields, tuple) else (fields,)):
        v = pick(doc, f)
        if v:
            try:
                n = float(v)
            except (TypeError, ValueError):
                continue
            return abs(n) if spec.get("amount_abs") else n
    return 0.0


def row_of(kind: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    """Satu baris panel untuk dokumen gagal `doc` jenis `kind` (`02` L8: `link` = tujuan tautan dokumennya)."""
    spec = KINDS[kind]
    from services import doc_refs_service as _refs
    number = pick(doc, spec["number_field"]) or doc.get("number") or doc["id"]
    link = _refs.link_of(spec["doc_type"], doc) if spec.get("doc_type") in _refs.DOC_TYPES else {}
    if link:
        link["number"] = link.get("number") or number
    return {"kind": kind, "kind_label": spec["label"], "id": doc["id"], "number": number,
            "entity_id": pick(doc, spec["entity_field"]) or "", "amount": _amount(spec, doc),
            "error": pick(doc, spec["error_field"]) or doc.get("gl_error") or "",
            "failed_at": pick(doc, spec["failed_at_field"]) or doc.get("updated_at") or doc.get("created_at") or "",
            "updated_at": doc.get("updated_at") or doc.get("created_at") or "", "link": link}


def sort_spec(kind: str) -> List[tuple]:
    return [(KINDS[kind]["failed_at_field"], -1), ("id", -1)]


def sort_key(kind: str, doc: Dict[str, Any]) -> tuple:
    """Kunci urut yang SAMA dengan `sort_spec` (gabungan antar-jenis tetap konsisten dengan urutan kueri)."""
    return (str(pick(doc, KINDS[kind]["failed_at_field"]) or ""), str(doc.get("id") or ""))


def status_of(kind: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    spec = KINDS[kind]
    st = spec["status_field"]
    jfield = st[:-len("gl_status")] + "journal_entry_id" if st.endswith("gl_status") else "journal_entry_id"
    return {"gl_status": pick(doc, st), "journal_entry_id": pick(doc, jfield) or ""}
