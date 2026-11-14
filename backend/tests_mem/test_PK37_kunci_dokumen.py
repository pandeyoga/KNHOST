"""PK-37 serah-terima (b2) — `periksa_periode_dokumen` sebagai langkah PERIKSA di 20 titik panggil (U9–U13).

Persiapan bersama: fixture "bulan berjalan tertutup" = dokumen `period_closings` berstatus `closed` untuk bulan buku WIB
hari ini (`pembantu.tutup_periode`, disisipkan langsung karena PK-11 menolak menutup bulan berjalan lewat API).
Dokumen sumber tiap baris = fixture yang disisipkan langsung dengan isi secukupnya untuk lolos pemeriksaan yang ada
SEBELUM langkah periode; aksinya dijalankan lewat API (alur).

U9 — tiap baris tabel titik panggil (satu tes parametrik per baris; baris dengan beberapa fungsi menguji tiap fungsi):
409 dengan pesan "Periode … sudah ditutup, jadi {jenis} …"; dokumen sumber tidak berubah (seluruh isi dokumen sama);
tidak ada `inventory_movements`, `cash_transactions`, maupun `journal_entries` baru.
"""
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

from pembantu import tutup_periode
from services.book_date import periode_buku, tanggal_buku

pytestmark = pytest.mark.anyio   # tes berparameter: tanda anyio dipasang sebelum parametrisasi

KSC, KANDA = "ent_ksc", "ent_kanda"
HITUNG = ("inventory_movements", "cash_transactions", "journal_entries")
PENGAJU_LAIN = "usr_pengaju_pk37"   # pembuat dokumen ≠ admin penyetuju (kontrol dua orang KF-T6)


def pola(jenis: str) -> "re.Pattern[str]":
    return re.compile(r"^Periode .+ sudah ditutup, jadi " + re.escape(jenis) + r" bertanggal \d{1,2} \w+ \d{4} "
                      r"tidak bisa dicatat\. Pakai tanggal di periode yang masih terbuka, atau ajukan Buka Periode di "
                      r"menu Keuangan\.$")


def uid(awalan: str) -> str:
    return f"{awalan}_pk37_{uuid.uuid4().hex[:8]}"


@dataclass
class Kasus:
    nama: str
    method: str
    url: str
    jenis: str
    koleksi: str                      # koleksi dokumen sumber
    doc_id: str
    json: Optional[Dict[str, Any]] = None
    entitas: Tuple[str, ...] = (KSC,)   # PT yang bulan berjalannya ditutup
    kepala_pt: str = KSC                # X-Entity-Id permintaan
    kunci_doc: str = "id"
    kepala: Dict[str, str] = field(default_factory=dict)   # header tambahan (mis. Idempotency-Key)


async def _jumlah(db) -> Dict[str, int]:
    return {k: await db[k].count_documents({}) for k in HITUNG}


@pytest.fixture
async def tutup(db):
    ids: List[str] = []

    async def _tutup(*eids: str) -> None:
        for e in eids:
            ids.append((await tutup_periode(e, periode_buku()))["id"])
    yield _tutup
    await db.period_closings.delete_many({"id": {"$in": ids}})


# ── Fixture dokumen per baris ────────────────────────────────────────────────────────────────────────────────────────
async def _tagihan(db, status: str, eid: str = KSC, **lain) -> str:
    bid = uid("vb")
    await db.vendor_bills.insert_one({
        "id": bid, "bill_number": f"VB/{bid}", "entity_id": eid, "status": status, "po_id": "", "supplier_id": "sup_x",
        "supplier_name": "Pemasok Uji", "items": [], "subtotal": 1_000_000, "tax_amount": 0, "grand_total": 1_000_000,
        "total_amount": 1_000_000, "amount_paid": 0, "created_by": "Pengaju", "created_by_id": PENGAJU_LAIN,
        "approval_status": "pending" if status == "pending_approval" else "not_required", "timeline": [],
        "created_at": "2026-11-01T01:00:00+00:00", **lain})
    return bid


async def b01_setujui_tagihan(db) -> List[Kasus]:
    bid = await _tagihan(db, "pending_approval")
    return [Kasus("setujui", "POST", f"/api/vendor-bills/{bid}/approve", "tagihan pemasok", "vendor_bills", bid)]


async def b02_batalkan_tagihan(db) -> List[Kasus]:
    bid = await _tagihan(db, "posted", posted_at="2026-11-01T01:00:00+00:00")
    return [Kasus("batal", "POST", f"/api/vendor-bills/{bid}/cancel", "pembatalan tagihan", "vendor_bills", bid,
                  json={"notes": "uji batal PK-37"})]


async def _voucher(db, status: str) -> str:
    vid = uid("lcv")
    await db.landed_cost_vouchers.insert_one({
        "id": vid, "voucher_number": f"LC/{vid}", "entity_id": KSC, "status": status, "po_ids": ["po_tidak_ada"],
        "total_cost": 500_000, "amount_paid": 0, "basis": "value", "provider_name": "Ekspedisi Uji",
        "created_by": "Pengaju", "created_by_id": PENGAJU_LAIN, "timeline": [], "payments": []})
    return vid


async def b03_setujui_biaya_masuk(db) -> List[Kasus]:
    vid = await _voucher(db, "pending_approval")
    return [Kasus("setujui", "POST", f"/api/landed-costs/{vid}/approve", "biaya masuk (landed cost)",
                  "landed_cost_vouchers", vid)]


async def b04_bayar_biaya_masuk(db) -> List[Kasus]:
    vid = await _voucher(db, "applied")
    return [Kasus("bayar", "POST", f"/api/landed-costs/{vid}/pay", "pembayaran", "landed_cost_vouchers", vid,
                  json={"amount": 200_000, "cash_type": "kas_besar", "method": "transfer"})]


async def b05_surat_jalan(db) -> List[Kasus]:
    so, tid = uid("so"), uid("tsk")
    await db.sales_orders.insert_one({"id": so, "number": f"SO/{so}", "entity_id": KSC, "status": "confirmed",
                                      "customer_id": "cus_x", "items": [], "grand_total": 0})
    await db.wms_tasks.insert_one({
        "id": tid, "flow_type": "outbound", "status": "picked", "order_id": so, "order_number": f"SO/{so}",
        "product_id": "prd_pk37", "warehouse_id": "wh_pk37", "entity_id": KSC, "quantity": 10, "picked_qty": 10,
        "shipped_qty": 0, "unit": "meter"})
    return [Kasus("kirim", "POST", f"/api/outbound/tasks/{tid}/dispatch", "surat jalan", "wms_tasks", tid)]


async def b06_penerimaan_barang(db) -> List[Kasus]:
    po, tid = uid("po"), uid("tsk")
    await db.purchase_orders.insert_one({"id": po, "po_number": f"PO/{po}", "entity_id": KSC, "status": "approved",
                                         "items": []})
    await db.wms_tasks.insert_one({
        "id": tid, "flow_type": "inbound", "status": "qc_check", "po_id": po, "po_number": f"PO/{po}",
        "product_id": "prd_pk37", "warehouse_id": "wh_pk37", "entity_id": KSC, "quantity": 10, "received_qty": 10,
        "unit": "meter", "legacy_in_flight": True, "supplier_dn_number": "SJ-UJI"})
    return [Kasus("selesai", "POST", f"/api/inbound/tasks/{tid}/complete", "penerimaan barang", "wms_tasks", tid,
                  json={})]


async def _produk_gudang(db) -> Tuple[str, str]:
    pid, wid = uid("prd"), uid("wh")
    await db.products.insert_one({"id": pid, "name": "Kain Uji PK-37", "sku": f"SKU-{pid}", "base_unit": "meter",
                                  "harga_pokok": 10_000, "is_active": True})
    await db.warehouses.insert_one({"id": wid, "name": "Gudang Uji PK-37", "entity_id": KSC, "is_active": True})
    return pid, wid


async def b07_penyesuaian_stok(db) -> List[Kasus]:
    pid, wid = await _produk_gudang(db)
    s1, s2 = uid("cc"), uid("cc")
    await db.cycle_count_sessions.insert_many([
        {"id": s1, "name": "Opname uji", "entity_id": KSC, "warehouse_id": wid, "status": "submitted",
         "submitted_by_id": PENGAJU_LAIN, "submitted_by": "Pengaju",
         "items": [{"id": "it1", "product_id": pid, "owner_entity_id": KSC, "expected_qty": 0, "counted_qty": 2,
                    "sku": "SKU-UJI", "bin_id": ""}],
         "discrepancies": [{"item_id": "it1", "difference": 2}]},
        {"id": s2, "name": "Opname per roll uji", "entity_id": KSC, "warehouse_id": wid, "status": "open",
         "mode": "roll", "items": [],
         "roll_count": {"node_id": "", "bin_ids": [], "snapshot_at": "2026-11-01T01:00:00+00:00", "expected": [],
                        "scans": [{"id": "scan1", "code": "KODE-ASING", "bin_id": "", "measured_qty": 5}],
                        "duplicates": 0}}])
    return [Kasus("setujui opname", "POST", f"/api/cycle-count/sessions/{s1}/approve", "penyesuaian stok",
                  "cycle_count_sessions", s1, json={"reason": "uji opname PK-37"}),
            Kasus("finalisasi opname per roll", "POST", f"/api/cycle-count/sessions/{s2}/roll-finalize",
                  "penyesuaian stok", "cycle_count_sessions", s2,
                  json={"reason": "uji finalisasi PK-37", "new_rolls": [
                      {"scan_id": "scan1", "product_id": pid, "owner_entity_id": KSC, "qty": 5}]})]


async def b08_penghapusan_stok(db) -> List[Kasus]:
    pid, wid = await _produk_gudang(db)
    r_cut, r_bs, r_mdq, ret, ins = uid("roll"), uid("roll"), uid("roll"), uid("sr"), uid("ins")
    dasar = {"product_id": pid, "warehouse_id": wid, "owner_entity_id": KSC, "entity_id": KSC, "unit": "meter",
             "status": "available", "length_initial": 50, "length_remaining": 50, "unit_cost": 10_000,
             "base_unit_cost": 10_000, "grade": "A"}
    await db.inventory_rolls.insert_many([
        {**dasar, "id": r_cut, "roll_no": "R-CUT", "length_reserved": 5,
         "length_reservations": [{"id": "rsv1", "qty": 5, "ref": {"type": "sales_order", "id": "so_x"},
                                  "status": "reserved"}]},
        {**dasar, "id": r_bs, "roll_no": "R-BS", "grade": "BS", "return_id": ret, "origin_type": "return"},
        {**dasar, "id": r_mdq, "roll_no": "R-MDQ"}])
    await db.sales_returns.insert_one({"id": ret, "number": f"SR/{ret}", "entity_id": KSC, "status": "inspected",
                                       "items": [], "attachments": []})
    await db.inspections.insert_one({"id": ins, "number": f"INS/{ins}", "kind": "po_receipt", "status": "in_progress",
                                     "entity_id": KSC, "lines": [{"id": "ln1", "roll_id": r_mdq}]})
    return [Kasus("susut potong", "POST", f"/api/inventory/rolls/{r_cut}/reservations/rsv1/cut", "penghapusan stok",
                  "inventory_rolls", r_cut, json={"actual_length": 5, "waste": 0.5, "waste_reason": "susut uji PK-37"}),
            Kasus("buang BS retur", "POST", f"/api/sales-returns/{ret}/disposition/supplier", "penghapusan stok",
                  "inventory_rolls", r_bs, json={"roll_ids": [r_bs], "decision": "dispose", "reason": "BS uji PK-37"}),
            Kasus("potong uji MDQ", "POST", f"/api/inspections/{ins}/lines/ln1/mdq-cut", "penghapusan stok",
                  "inventory_rolls", r_mdq, json={"cut_yard": 0.25})]


async def b09_nota_kredit_retur(db) -> List[Kasus]:
    r1, r2 = uid("sr"), uid("sr")
    dasar = {"entity_id": KSC, "status": "inspected", "customer_id": "cus_x", "order_id": "so_x", "items": [],
             "attachments": []}
    await db.sales_returns.insert_many([
        {**dasar, "id": r1, "number": f"SR/{r1}"},
        {**dasar, "id": r2, "number": f"SR/{r2}", "settlements": [{"id": "rst1", "seq": 1, "status": "posting",
                                                                   "plan": {"rolls": []}}]}])
    return [Kasus("selesaikan retur", "POST", f"/api/sales-returns/{r1}/settle", "nota kredit retur", "sales_returns", r1,
                  json={"outcome": "refund"}),
            Kasus("selesaikan per roll", "POST", f"/api/sales-returns/{r1}/roll-settlement", "nota kredit retur",
                  "sales_returns", r1, json={"rolls": []}),
            Kasus("lengkapi per roll", "POST", f"/api/sales-returns/{r2}/roll-settlement/rst1/complete",
                  "nota kredit retur", "sales_returns", r2)]


async def b10_nota_kredit(db) -> List[Kasus]:
    so, amd, cn = uid("so"), uid("amd"), uid("cn")
    await db.sales_orders.insert_one({"id": so, "number": f"SO/{so}", "entity_id": KSC, "status": "dispatched",
                                      "customer_id": "cus_x", "items": [], "grand_total": 1_000_000,
                                      "created_by": "Admin"})
    await db.doc_amendments.insert_one({
        "id": amd, "number": f"AMD/{amd}", "status": "pending_approval", "method": "credit_note",
        "doc_type": "sales_order", "doc_id": so, "entity_id": KSC, "approval_permission": "finance_amendment.approve",
        "proposed_by": "Pengaju", "proposed_by_id": PENGAJU_LAIN, "impact": {"delta": -100_000},
        "policy_snapshot": {"admin_approval_above": 0}, "changes": [], "reason_code": "harga", "reason_label": "Harga"})
    await db.credit_notes.insert_one({
        "id": cn, "number": f"CN/{cn}", "kind": "credit_note", "source": "od_item_cancel", "status": "pending_finance",
        "order_id": so, "entity_id": KSC, "gross_amount": 100_000, "ppn_amount": 0, "net_amount": 100_000,
        "open_before": 100_000, "revenue_recognized": True})
    return [Kasus("setujui amandemen nota kredit", "POST", f"/api/amendments/{amd}/decision", "nota kredit",
                  "doc_amendments", amd, json={"action": "approve", "note": "uji PK-37"}),
            Kasus("terbitkan nota batal item", "POST", f"/api/credit-notes/{cn}/finance-review", "nota kredit",
                  "credit_notes", cn, json={"action": "issue", "note": "uji PK-37"})]


async def b11_makloon(db) -> List[Kasus]:
    pid, wid = await _produk_gudang(db)
    m1, m2, m3 = uid("mko"), uid("mko"), uid("mko")
    langkah = {"seq": 1, "status": "pending", "input_product_id": pid, "input_qty": 10, "output_product_id": pid,
               "process_type": "celup", "stage_label": "Celup", "partner_id": "mitra_x"}
    dasar = {"entity_id": KSC, "status": "in_progress", "from_warehouse_id": wid, "partner_id": "mitra_x",
             "partner_name": "Mitra Uji", "timeline": []}
    await db.makloon_orders.insert_many([
        {**dasar, "id": m1, "mko_number": f"MKO/{m1}", "steps": [{**langkah, "material_flow": "moves"}]},
        {**dasar, "id": m2, "mko_number": f"MKO/{m2}", "steps": [{**langkah, "material_flow": "service_only"}]},
        {**dasar, "id": m3, "mko_number": f"MKO/{m3}", "steps": [{**langkah, "material_flow": "moves",
                                                                   "status": "issued"}]}])
    return [Kasus("kirim bahan", "POST", f"/api/makloon-orders/{m1}/issue", "dokumen makloon", "makloon_orders", m1,
                  json={"step_seq": 1}),
            Kasus("catat jasa", "POST", f"/api/makloon-orders/{m2}/record-service", "dokumen makloon",
                  "makloon_orders", m2, json={"step_seq": 1, "tariff": 50_000}),
            Kasus("terima hasil", "POST", f"/api/makloon-orders/{m3}/receive", "dokumen makloon", "makloon_orders", m3,
                  json={"step_seq": 1, "actual_output_qty": 10})]


async def b12_nota_denda(db) -> List[Kasus]:
    d1, d2, d3, d4 = uid("pnl"), uid("pnl"), uid("pnl"), uid("pnl")
    dasar = {"entity_id": KSC, "customer_id": "cus_x", "customer_name": "Pelanggan Uji", "amount": 300_000,
             "paid_amount": 0, "payments": [], "adjustments": [], "created_by": "Pengaju",
             "created_by_id": PENGAJU_LAIN, "doc_number": "SO/X", "line_label": "Termin 1"}
    await db.penalties.insert_many([
        {**dasar, "id": d1, "number": f"PNL/{d1}", "status": "draft"},
        {**dasar, "id": d2, "number": f"PNL/{d2}", "status": "issued"},
        {**dasar, "id": d3, "number": f"PNL/{d3}", "status": "issued"},
        {**dasar, "id": d4, "number": f"PNL/{d4}", "status": "issued"}])
    return [Kasus("terbitkan", "POST", f"/api/penalties/{d1}/issue", "nota denda", "penalties", d1),
            Kasus("bebaskan", "POST", f"/api/penalties/{d2}/waive", "nota denda", "penalties", d2,
                  json={"reason_code": "nego", "note": "uji PK-37"}),
            Kasus("ubah nominal", "POST", f"/api/penalties/{d3}/adjust", "nota denda", "penalties", d3,
                  json={"reason_code": "nego", "note": "uji PK-37", "amount": 100_000}),
            Kasus("bayar", "POST", f"/api/penalties/{d4}/pay", "nota denda", "penalties", d4,
                  json={"amount": 100_000, "account_id": "acc_x"}, kepala={"Idempotency-Key": uid("k")})]


async def b13_selisih_bayar(db) -> List[Kasus]:
    rid = uid("rcp")
    await db.ar_receipts.insert_one({
        "id": rid, "number": f"RCP/{rid}", "entity_id": KSC, "status": "posted", "customer_id": "cus_x",
        "amount": 950_000, "receipt_date": tanggal_buku(), "created_by": "Pengaju",
        "variance": {"direction": "under", "delta": -50_000, "needs_decision": True}})
    return [Kasus("putuskan selisih kwitansi", "POST", f"/api/payment-variances/receipt/{rid}/decide",
                  "keputusan selisih bayar", "ar_receipts", rid, json={"kind": "writeoff", "reason_code": "x"})]


async def b14_hasil_produksi(db) -> List[Kasus]:
    pid, wid = await _produk_gudang(db)
    wo = uid("wo")
    await db.mfg_work_orders.insert_one({
        "id": wo, "wo_number": f"WO/{wo}", "entity_id": KSC, "warehouse_id": wid, "status": "released",
        "planned_qty": 10, "output_product_id": pid, "output_name": "Kain jadi",
        "bom_components": [{"material_product_id": pid, "sku": "SKU", "name": "Bahan", "unit": "meter",
                            "qty_per_unit": 1}]})
    return [Kasus("selesaikan WO", "POST", f"/api/production/work-orders/{wo}/complete", "hasil produksi",
                  "mfg_work_orders", wo)]


BA = "ba_pk37"


async def _baris_bank(db, arah: str, status: str = "unmatched", **lain) -> str:
    if not await db.bank_accounts.find_one({"id": BA}):
        await db.bank_accounts.insert_one({"id": BA, "name": "BCA PK37", "account_type": "bank", "cash_type": "bank",
                                           "bank_name": "BCA", "entity_id": KSC, "is_active": True,
                                           "status": "active", "opening_balance": 0})
    lid = uid("stl")
    await db.bank_statement_lines.insert_one({
        "id": lid, "bank_account_id": BA, "entity_id": KSC, "stmt_date": tanggal_buku(), "amount": 1_000_000.0,
        "direction": arah, "description": "mutasi uji PK-37", "counterparty": "", "desc_key": "", "ref": "",
        "external_id": lid, "balance": 0.0, "status": status, "match_kind": "", "matched_txn_id": "",
        "matched_txn_ids": [], "allocations": [], "score": 0, "score_explain": [], "suggestions": [],
        "holding": {}, "holding_allocated": [], "holding_remaining": 0.0, **lain})
    return lid


async def b15_transaksi_bank(db) -> List[Kasus]:
    l1 = await _baris_bank(db, "out")
    l2 = await _baris_bank(db, "in")
    l3 = await _baris_bank(db, "in", "holding", holding_remaining=1_000_000.0)
    so = uid("so")
    await db.customers.update_one({"id": "cus_pk37"}, {"$set": {"id": "cus_pk37", "name": "Toko PK37",
                                                                 "entity_id": KSC}}, upsert=True)
    await db.sales_orders.insert_one({"id": so, "number": f"SO/{so}", "entity_id": KSC, "customer_id": "cus_pk37",
                                      "customer_name": "Toko PK37", "grand_total": 2_000_000, "status": "confirmed",
                                      "payments": [], "paid_total": 0.0})
    base = "/api/bank-reconciliation/lines"
    return [Kasus("biaya bank", "POST", f"{base}/{l1}/book-charge", "transaksi bank", "bank_statement_lines", l1,
                  json={"kind": "charge"}),
            Kasus("titipan", "POST", f"{base}/{l2}/holding", "transaksi bank", "bank_statement_lines", l2,
                  json={"note": "uji PK-37"}),
            Kasus("alokasi titipan", "POST", f"{base}/{l3}/holding/allocate", "transaksi bank", "bank_statement_lines",
                  l3, json={"customer_id": "cus_pk37", "reason_code": "titipan_teridentifikasi", "note": "uji",
                            "allocations": [{"order_id": so, "amount": 500_000}]})]


async def _transfer(db) -> str:
    tid = uid("trf")
    await db.warehouse_transfers.insert_one({
        "id": tid, "number": f"TRF/{tid}", "transfer_kind": "inter_entity", "status": "waiting_approval",
        "entity_id": KSC, "source_entity_id": KSC, "dest_entity_id": KANDA, "from_warehouse_id": "",
        "to_warehouse_id": "", "items": [], "requested_by": "Pengaju", "requested_by_id": PENGAJU_LAIN,
        "timeline": []})
    return tid


async def b16_transfer_antar_pt(db) -> List[Kasus]:
    tid = await _transfer(db)
    return [Kasus("setujui transfer", "POST", f"/api/transfers/{tid}/approve", "transfer antar-PT",
                  "warehouse_transfers", tid, json={}, entitas=(KSC, KANDA))]


async def b17_bahan_sample(db) -> List[Kasus]:
    pid, wid = await _produk_gudang(db)
    smp, rid = uid("smp"), uid("roll")
    await db.md_samples.insert_one({"id": smp, "number": f"SMP/{smp}", "entity_id": KSC, "status": "in_progress"})
    await db.inventory_rolls.insert_one({"id": rid, "roll_no": "R-SMP", "product_id": pid, "warehouse_id": wid,
                                         "owner_entity_id": KSC, "status": "available", "length_remaining": 20,
                                         "unit": "meter", "unit_cost": 10_000})
    return [Kasus("ambil bahan", "POST", f"/api/rnd/samples/{smp}/issue-material", "pengeluaran bahan sample",
                  "inventory_rolls", rid, json={"roll_id": rid, "qty": 2})]


async def b18_klaim_makloon(db) -> List[Kasus]:
    pid, wid = await _produk_gudang(db)
    m1, m2 = uid("mko"), uid("mko")
    langkah = {"seq": 1, "status": "received", "input_product_id": pid, "input_qty": 10, "output_product_id": pid,
               "process_type": "celup", "stage_label": "Celup", "material_flow": "moves"}
    dasar = {"entity_id": KSC, "status": "in_progress", "from_warehouse_id": wid, "partner_id": "mitra_x",
             "partner_name": "Mitra Uji", "timeline": []}
    await db.makloon_orders.insert_many([
        {**dasar, "id": m1, "mko_number": f"MKO/{m1}", "steps": [{**langkah, "claim": {
            "status": "pending_approval", "action": "tagih_ganti", "amount": 100_000, "reason": "cacat",
            "proposed_by": "Pengaju", "proposed_by_id": PENGAJU_LAIN}}]},
        {**dasar, "id": m2, "mko_number": f"MKO/{m2}", "steps": [{**langkah, "status": "issued", "material_losses": [
            {"id": "mloss1", "status": "pending_approval", "roll_ids": [], "qty": 5, "within_qty": 0, "over_qty": 5,
             "recorded_by": "Pengaju", "recorded_by_id": PENGAJU_LAIN, "reason": "hilang di mitra"}]}]}])
    return [Kasus("setujui klaim", "POST", f"/api/makloon-orders/{m1}/claim/approve", "klaim makloon",
                  "makloon_orders", m1, json={"step_seq": 1, "note": "uji PK-37"}),
            Kasus("setujui susut", "POST", f"/api/makloon-orders/{m2}/steps/1/material-loss/mloss1/decide",
                  "klaim makloon", "makloon_orders", m2, json={"approve": True, "note": "uji PK-37"})]


async def b19_saldo_kredit(db) -> List[Kasus]:
    cus = uid("cus")
    await db.customers.insert_one({"id": cus, "name": "Pelanggan PK37", "entity_id": KSC, "status": "active"})
    return [Kasus("tambah saldo", "POST", "/api/store-credit/adjust", "saldo kredit pelanggan", "customers", cus,
                  json={"customer_id": cus, "amount": 50_000, "note": "uji PK-37"})]


async def b20_kasus_keuangan(db) -> List[Kasus]:
    from services import amendment_service
    await amendment_service.ensure_reasons()
    cid, so = uid("fcs"), uid("so")
    await db.sales_orders.insert_one({"id": so, "number": f"SO/{so}", "entity_id": KSC, "customer_id": "cus_x",
                                      "grand_total": 1_000_000, "status": "confirmed", "payments": []})
    await db.finance_cases.insert_one({"id": cid, "number": cid.upper(), "entity_id": KSC,
                                       "case_type": "selisih_biaya_bank", "status": "in_progress",
                                       "customer_id": "cus_x", "amount": 5_000, "documents": [], "attachments": []})
    return [Kasus("selesaikan kasus", "POST", f"/api/finance-cases/{cid}/resolve", "penyelesaian kasus",
                  "finance_cases", cid, json={"action": "bebankan_biaya_bank", "reason_code": "bank_charge",
                                              "order_id": so, "amount": 5_000})]


BARIS: Dict[int, Callable] = {
    1: b01_setujui_tagihan, 2: b02_batalkan_tagihan, 3: b03_setujui_biaya_masuk, 4: b04_bayar_biaya_masuk,
    5: b05_surat_jalan, 6: b06_penerimaan_barang, 7: b07_penyesuaian_stok, 8: b08_penghapusan_stok,
    9: b09_nota_kredit_retur, 10: b10_nota_kredit, 11: b11_makloon, 12: b12_nota_denda,
    13: b13_selisih_bayar, 14: b14_hasil_produksi, 15: b15_transaksi_bank, 16: b16_transfer_antar_pt,
    17: b17_bahan_sample, 18: b18_klaim_makloon, 19: b19_saldo_kredit, 20: b20_kasus_keuangan,
}


async def _jalankan(klien, kepala, db, k: Kasus):
    h = {**kepala, "X-Entity-Id": k.kepala_pt, **k.kepala}
    sebelum_doc = await db[k.koleksi].find_one({k.kunci_doc: k.doc_id}, {"_id": 0})
    assert sebelum_doc, f"fixture {k.koleksi}/{k.doc_id} tidak ada"
    sebelum = await _jumlah(db)
    r = await klien.request(k.method, k.url, headers=h, json=k.json)
    return r, sebelum_doc, sebelum


@pytest.mark.parametrize("baris", sorted(BARIS))
async def test_PK37_U9_titik_panggil_ditolak_di_muka(baris, klien, kepala_admin, db, tutup):
    kasus = await BARIS[baris](db)
    await tutup(*sorted({e for k in kasus for e in k.entitas}))
    for k in kasus:
        r, sebelum_doc, sebelum = await _jalankan(klien, kepala_admin, db, k)
        assert r.status_code == 409, (baris, k.nama, r.status_code, r.text)
        detail = r.json().get("detail")
        assert isinstance(detail, str) and pola(k.jenis).match(detail), (baris, k.nama, detail)
        assert await db[k.koleksi].find_one({k.kunci_doc: k.doc_id}, {"_id": 0}) == sebelum_doc, (baris, k.nama)
        assert await _jumlah(db) == sebelum, (baris, k.nama)


async def test_PK37_U9_b13_keputusan_selisih_tagihan_lapis_layanan(db, tutup):
    """Baris 13, fungsi kedua (`decide_bill`): hanya dipanggil di dalam bayar tagihan SESUDAH uang keluar (pembayaran
    sudah diperiksa periodenya oleh PK-05). Lapis layanan: periode tertutup → `VarianceError` berpesan sama, tanpa
    keputusan/jurnal (pemanggil mencatatnya di linimasa tagihan)."""
    from services import payment_variance_service as pvs
    await tutup(KSC)
    bid = await _tagihan(db, "posted")
    bill = await db.vendor_bills.find_one({"id": bid}, {"_id": 0})
    sebelum, n_kep = await _jumlah(db), await db.payment_variance_decisions.count_documents({})
    with pytest.raises(pvs.VarianceError) as e:
        await pvs.decide_bill(bill, {"direction": "under", "delta": -10_000, "entity_id": KSC, "policy": {}},
                              {"kind": "ap_writeoff", "reason_code": "x"}, {"name": "Admin", "role": "admin"})
    assert pola("keputusan selisih bayar").match(str(e.value)), str(e.value)
    assert await _jumlah(db) == sebelum
    assert await db.payment_variance_decisions.count_documents({}) == n_kep


# ── U10 — sakelar mati di lapisan PT `ent_ksc` → tidak ditolak di muka; PT lain tetap 409 ─────────────────────────
async def test_PK37_U10_sakelar_per_pt(klien, kepala_admin, db, tutup):
    await tutup(KSC, KANDA)
    b_ksc = await _tagihan(db, "pending_approval", KSC)
    b_kanda = await _tagihan(db, "pending_approval", KANDA)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "periode.kunci_dokumen", "value": False, "scope_type": "entity", "scope_id": KSC,
        "reason": "uji PK-37 U10"}]})
    assert r.status_code == 200, r.text
    try:
        je0 = await db.journal_entries.count_documents({})
        r = await klien.post(f"/api/vendor-bills/{b_ksc}/approve", headers={**kepala_admin, "X-Entity-Id": KSC})
        assert r.status_code == 200, r.text
        assert (await db.vendor_bills.find_one({"id": b_ksc}))["status"] == "posted"   # dokumen tersimpan
        assert await db.journal_entries.count_documents({}) == je0                     # jurnalnya tetap ditolak penjaga
        sebelum = await db.vendor_bills.find_one({"id": b_kanda}, {"_id": 0})
        r = await klien.post(f"/api/vendor-bills/{b_kanda}/approve", headers={**kepala_admin, "X-Entity-Id": KANDA})
        assert r.status_code == 409, r.text
        assert pola("tagihan pemasok").match(r.json()["detail"]), r.text
        assert await db.vendor_bills.find_one({"id": b_kanda}, {"_id": 0}) == sebelum
    finally:
        await klien.post("/api/config/values/clear", headers=kepala_admin, json={
            "key": "periode.kunci_dokumen", "scope_type": "entity", "scope_id": KSC, "reason": "pulihkan"})


# ── U11 — jendela Buka Periode aktif → penyesuaian stok diterima, jurnal bertanda ───────────────────────────────────
async def test_PK37_U11_jendela_buka_periode_meloloskan(klien, kepala_admin, db, tutup):
    import datetime
    from services import closing_service as cs
    await tutup(KSC)
    awal, akhir = await cs.period_bounds("month", periode_buku(), KSC)
    plu = uid("plu")
    await db.period_unlock_requests.insert_one({   # fixture: jendela buka periode yang sudah disetujui, berlaku 2 jam
        "id": plu, "entity_id": KSC, "status": "approved", "period_type": "month", "period_key": periode_buku(),
        "start_date": awal, "end_date": akhir, "reason": "uji PK-37 U11", "backdated_je_ids": [],
        "window_until": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()})
    try:
        k = (await b07_penyesuaian_stok(db))[0]
        r = await klien.post(k.url, headers=kepala_admin, json=k.json)
        assert r.status_code == 200, r.text
        # hitung tangan: selisih +2 m × harga pokok 10.000 = 20.000 → Dr 1-1300 Persediaan / Cr 4-9000
        je = await db.journal_entries.find_one({"source_type": "cycle_count_variance",
                                                "source_id": {"$regex": "^" + k.doc_id}}, {"_id": 0})
        assert je and je["backdated_in_unlock"] == plu, je
        assert je["date"] == tanggal_buku() and abs(je["total_debit"] - 20_000) < 0.005
    finally:
        await db.period_unlock_requests.delete_one({"id": plu})


# ── U12 — pengaturan mati tidak melonggarkan pemeriksa lama (kas manual) ────────────────────────────────────────────
async def test_PK37_U12_pemeriksa_lama_tetap_saat_sakelar_mati(klien, kepala_admin, db, tutup):
    await tutup(KSC)
    r = await klien.put("/api/config/values", headers=kepala_admin, json={"items": [{
        "key": "periode.kunci_dokumen", "value": False, "scope_type": "global", "scope_id": "",
        "reason": "uji PK-37 U12"}]})
    assert r.status_code == 200, r.text
    try:
        kas0 = await db.cash_transactions.count_documents({})
        r = await klien.post("/api/cash-transactions", headers={**kepala_admin, "Idempotency-Key": uid("k")}, json={
            "cash_type": "kas_besar", "direction": "out", "amount": 10_000, "category": "lain-lain",
            "description": "uji PK-37 U12", "txn_date": tanggal_buku()})
        assert r.status_code == 409, r.text
        assert "sudah DITUTUP" in r.json()["detail"], r.text                 # pesan pemeriksa lama (preflight_posting)
        assert await db.cash_transactions.count_documents({}) == kas0
    finally:
        await klien.post("/api/config/values/reset", headers=kepala_admin, json={
            "key": "periode.kunci_dokumen", "scope_type": "global", "reason": "pulihkan"})


# ── U13 — transfer antar-PT: hanya PT penerima yang tertutup → 409, stok PT pengirim tidak berubah ────────────────────
async def test_PK37_U13_transfer_penerima_tertutup(klien, kepala_admin, db, tutup):
    await tutup(KANDA)
    tid = await _transfer(db)
    pid, wid = await _produk_gudang(db)
    rid = uid("roll")
    await db.inventory_rolls.insert_one({"id": rid, "roll_no": "R-TRF", "product_id": pid, "warehouse_id": wid,
                                         "owner_entity_id": KSC, "status": "reserved", "length_remaining": 30,
                                         "unit": "meter", "unit_cost": 10_000,
                                         "reserved_ref": {"type": "transfer", "id": tid}})
    roll0, trf0, n0 = (await db.inventory_rolls.find_one({"id": rid}, {"_id": 0}),
                       await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0}), await _jumlah(db))
    r = await klien.post(f"/api/transfers/{tid}/approve", headers=kepala_admin, json={})
    assert r.status_code == 409, r.text
    assert pola("transfer antar-PT").match(r.json()["detail"]), r.text
    assert await db.inventory_rolls.find_one({"id": rid}, {"_id": 0}) == roll0       # milik & status roll tetap
    assert await db.warehouse_transfers.find_one({"id": tid}, {"_id": 0}) == trf0
    assert await _jumlah(db) == n0
