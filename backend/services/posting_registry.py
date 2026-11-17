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
  per_step         (opsional) satu baris panel per unsur larik yang gagal; id baris = `<id dokumen>:<seq>`. Lariknya
                   `items_field` (bawaan `steps`), nominal unsur `item_amount` (bawaan `makloon_step_amount`), sebutan
                   unsur di nomor baris `item_label` (bawaan "langkah") — PK-28 memakai `grir_clearings[]`
  link             (opsional) tujuan tautan tetap bila jenis dokumennya tidak ada di `DOC_TYPES`; `link_id_field`
                   (opsional) = field id dokumen tujuan (bawaan `id`), mis. entri penyusutan → asetnya

`KINDS` sengaja berupa literal: penjaga statik membacanya tanpa mengimpor aplikasi. Jenis dari PK-05 (`contra_bon`),
PK-06 (`interco_*`) dan PK-30 (`interco_adj`) dipindahkan dari `routers/posting_failures.py` apa adanya.
"""
from typing import Any, Dict, List, Optional

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
    if doc.get("ref_type") == "statutory_remittance" and doc.get("ref_id"):   # PK-22 — setoran kewajiban selesai
        from services.hr_remittance_service import finish_remittance
        await finish_remittance(doc["ref_id"])
    if doc.get("ref_type") == "payroll_run" and doc.get("ref_id"):   # PY-T4 — kas bayar gaji: proses menjadi Dibayar
        from services.hr_payroll_pay import selesaikan_dari_kas
        await selesaikan_dari_kas(doc)
    if doc.get("ref_type") == "cash_deposit" and doc.get("ref_id"):   # PM-T4 — penanda jurnal setoran titipan ikut
        from services.cash_holding_service import tandai_jurnal_kas
        await tandai_jurnal_kas(doc)


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
    """PK-18 (GL-12) — `posted` hanya bila jurnal pendapatan surat jalan (`shipment_revenue`) memang ada."""
    from services import gl_service as gl
    await gl.post_durable("shipments", doc["id"], lambda: gl.post_order_revenue_and_cogs(doc["order_id"]),
                          source_type="shipment_revenue", source_id=doc["id"], raise_on_fail=True)
    from services import billing_schedule_service as bss   # CR-T2 — baris tagihan lahir dari jurnal yang baru terbit
    await bss.after_shipment_journal(doc)


async def _retry_shipment_billing(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """CR-T2 — jurnal surat jalan sudah terbit tetapi baris jadwal tagihannya gagal dibuat: kait diulang."""
    from services import billing_schedule_service as bss
    await bss.retry_shipment_billing(doc, actor)


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


# ── PK-18 — resep posting yang memanggil BEBERAPA fungsi `post_*` (dipakai aksi dokumen DAN ulang) ─────────────────────
def step_of(order: Dict[str, Any], seq: int, field: str = "steps") -> Dict[str, Any]:
    return next((s for s in order.get(field) or [] if int(s.get("seq") or 0) == int(seq)), {})


def _moves(step: Dict[str, Any]) -> bool:
    return str(step.get("material_flow") or "moves") != "service_only"


def makloon_step_source(order: Dict[str, Any], seq: int) -> tuple:
    """(source_type, source_id) jurnal UTAMA langkah makloon menurut keadaannya — untuk `post_durable`."""
    step, src = step_of(order, seq), f"{order['id']}:{seq}"
    rets = step.get("material_returns") or []
    if rets:
        part = rets[-1].get("gl_part") or ""
        return "subcon_issue_reversal", src + (f":{part}" if part else "")
    if step.get("status") == "received":
        return ("subcon_receipt", src) if _moves(step) else ("subcon_service", step.get("service_bill_id") or "")
    return "subcon_issue", src


def makloon_step_amount(step: Dict[str, Any]) -> float:
    if step.get("status") == "received":
        if _moves(step):
            return round(float(step.get("output_value") or 0) + float(step.get("byproduct_value") or 0), 2)
        return round(float(step.get("service_value") or 0), 2)
    return round(float(step.get("material_value") or 0), 2)


async def post_makloon_step(order: Dict[str, Any], seq: int) -> None:
    """Semua jurnal langkah `seq` dari nilai yang TERSIMPAN di langkahnya: kirim bahan (Dr 1-1350 / Cr 1-1300 sebesar
    `material_value`), jasa (tagihan `service_bill_id`), terima hasil (Dr 1-1300 / Cr 1-1350 sebesar output + sisa),
    retur bahan (pembalik per retur, `gl_part`). Tiap fungsi idempoten → yang sudah terbit tidak diterbitkan lagi."""
    from services import gl_service as gl
    step = step_of(order, seq)
    mko, eid = order["id"], order.get("entity_id", "")
    label = f"{order.get('mko_number')} step{seq}"
    if _moves(step) and step.get("status") in ("issued", "received", "returned"):
        await gl.post_subcon_issue(mko_id=mko, step_seq=int(seq), entity_id=eid,
                                   amount=float(step.get("material_value") or 0), label=label)
    if step.get("service_bill_id"):
        bill = await db.vendor_bills.find_one({"id": step["service_bill_id"]}, {"_id": 0}) or {}
        if bill:
            await gl.post_subcon_service(
                bill_id=bill["id"], mko_id=mko, step_seq=int(seq), entity_id=eid,
                net_amount=float(bill.get("net_amount") or 0) + (float(bill.get("claim_deduction") or 0)
                                                                 if bill.get("ap_mode") == "saat_faktur" else 0),
                ppn=float(bill.get("ppn_amount") or 0),
                grand_total=float(bill.get("grand_total") or 0), makloon_name=step.get("makloon_name") or "",
                label=label, ap_mode=bill.get("ap_mode") or "")
            # MP-T4b (K-78) — faktur mitra sudah dicocokkan → GR/IR ke hutang (nilai tagihan sesudah potongan klaim).
            if bill.get("ap_mode") == "saat_faktur" and bill.get("status") in ("posted", "paid", "partially_paid") \
                    and bill.get("invoice_matched_at"):
                await gl.post_subcon_service_invoice(
                    bill_id=bill["id"], entity_id=eid, net_amount=float(bill.get("net_amount") or 0),
                    ppn=float(bill.get("ppn_amount") or 0), makloon_name=step.get("makloon_name") or "",
                    label=label, invoice_no=bill.get("supplier_invoice_no") or "", mko_id=mko)
    if _moves(step) and step.get("status") == "received":
        await gl.post_subcon_receipt(mko_id=mko, step_seq=int(seq), entity_id=eid,
                                     amount=makloon_step_amount(step), label=label)
    for ret in step.get("material_returns") or []:
        await gl.reverse_subcon_issue(mko_id=mko, step_seq=int(seq), entity_id=eid,
                                      amount=float(ret.get("value") or 0), label=label, part=ret.get("gl_part") or "")


async def durable_makloon_step(order: Dict[str, Any], seq: int, *, raise_on_fail: bool = False) -> Dict[str, Any]:
    """Pintu tahan-gagal satu langkah makloon: hasil ditulis ke `steps.$.gl_status` langkah itu."""
    from services import gl_service as gl
    st, sid = makloon_step_source(order, seq)
    return await gl.post_durable("makloon_orders", order["id"], lambda: post_makloon_step(order, seq),
                                 source_type=st, source_id=sid, field="steps.$.gl_status",
                                 match={"steps.seq": int(seq)}, raise_on_fail=raise_on_fail)


async def _receipt_cash_ids(receipt_id: str) -> List[str]:
    return [c["id"] async for c in db.cash_transactions.find(
        {"ref_type": "ar_receipt", "ref_id": receipt_id}, {"_id": 0, "id": 1}).sort("id", 1)]


def tanggal_pembalik(nilai: Any) -> str:
    """Pelatihan 18 Nov (uji adversarial, kelas V-09) — tanggal jurnal pembalik dokumen yang dibatalkan: tanggal dokumen
    asal bila masih DI DEPAN tanggal buku hari ini (pembalik tidak boleh mendahului jurnal aslinya — aturan yang sama
    dengan `gl_service.reverse_entry` dan batal-bayar tagihan supplier), selain itu "" = hari ini (perilaku lama).
    Hasilnya tanggal buku WIB `YYYY-MM-DD` (sama dengan tanggal jurnal asal; teks ISO ber-zona dari pemilih tanggal
    layar, mis. "2026-12-15T00:00:00.000Z", tidak dipotong mentah)."""
    from services.book_date import tanggal_buku
    if not nilai:
        return ""
    try:
        tgl = tanggal_buku(nilai)
    except (TypeError, ValueError):
        return ""
    return tgl if tgl > tanggal_buku() else ""


async def post_receipt_void(receipt: Dict[str, Any], created_by: str = "system") -> Optional[Dict[str, Any]]:
    """Pembalik kwitansi yang dibatalkan: (PK-19) pembalik reklas uang muka tiap pesanan yang uang mukanya sudah
    direklas ke Piutang (KEB-PDPT), jurnal pembalik tiap kas kwitansi, lalu pembalik reklas deposit. → jurnal
    pembalik pertama (termasuk pembalik yang SUDAH ada, mis. dibalik manual lebih dulu — PK-10). Semua fungsinya
    idempoten per sumber, jadi ulang dari panel tidak menggandakan jurnal.

    Pelatihan 18 Nov (uji adversarial) — kas kwitansi bertanggal MAJU dibalik pada tanggal kasnya (`tanggal_pembalik`);
    dulu selalu hari ini → bulan berjalan mendapat Dr Piutang / Cr Bank tanpa jurnal asalnya."""
    from services import gl_service as gl
    label = f"void {receipt.get('number', '')}"
    hasil: List[Optional[Dict[str, Any]]] = []
    for oid in dict.fromkeys(a.get("order_id") for a in receipt.get("allocations") or [] if a.get("order_id")):
        order = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
        if not order:
            continue
        adv = round(sum(float(p.get("amount") or 0) for p in order.get("payments") or []
                        if p.get("receipt_id") == receipt["id"] and p.get("gl_bucket") == gl.ADVANCE_BUCKET
                        and float(p.get("amount") or 0) > 0 and not p.get("reverses")), 2)
        if adv > 0.01:
            hasil.append(await gl.post_advance_reclass_reversal(order, receipt["id"], adv, label=label))
    for cid in await _receipt_cash_ids(receipt["id"]):
        kas = await db.cash_transactions.find_one({"id": cid}, {"_id": 0, "txn_date": 1}) or {}
        hasil.append(await gl.post_cash_void(cid, label=label, created_by=created_by,
                                             date=tanggal_pembalik(kas.get("txn_date"))))
    if receipt.get("cash_holding_id"):   # PM-T4 — kwitansi titipan: pembalik jurnal titipannya (bukan kas)
        hasil.append(await gl.reverse_cash_holding(receipt["cash_holding_id"], label=label, created_by=created_by))
    hasil.append(await gl.reverse_deposit_only_receipt(receipt["id"], label=label, created_by=created_by))
    return next((je for je in hasil if isinstance(je, dict) and je.get("id")), None)


async def durable_receipt_void(receipt: Dict[str, Any], created_by: str = "system", *,
                               raise_on_fail: bool = False) -> Dict[str, Any]:
    from services import gl_service as gl
    kas = await _receipt_cash_ids(receipt["id"])
    st, sid = ("cash_transaction_void", kas[0]) if kas else ("ar_receipt_deposit_void", receipt["id"])
    if not kas and receipt.get("cash_holding_id") and await gl._already_posted("cash_holding",
                                                                               receipt["cash_holding_id"]):
        st, sid = "cash_holding_reversal", receipt["cash_holding_id"]   # PM-T4
    return await gl.post_durable("ar_receipts", receipt["id"], lambda: post_receipt_void(receipt, created_by),
                                 source_type=st, source_id=sid, field="void_gl_status", raise_on_fail=raise_on_fail)


async def _komisi_proses_lain(run: Dict[str, Any]) -> float:
    """Σ komisi slip (bagian yang diakru, tanpa baris Lembar Insentif) proses gaji LAIN di PT·periode yang sama yang
    sudah diposting (`posted`/`paying`/`paid`) dengan mode akru `accrue_then_settle`. Proses batal/void/draf tidak."""
    from services.hr_pay_components import commission_parts
    total = 0.0
    async for other in db.hr_payroll_runs.find(
            {"entity_id": run.get("entity_id"), "period": run.get("period"), "id": {"$ne": run.get("id")},
             "status": {"$in": ["posted", "paying", "paid"]}}, {"_id": 0, "id": 1, "commission_mode": 1}):
        if (other.get("commission_mode") or "accrue_then_settle") != "accrue_then_settle":
            continue
        slips = await db.hr_payslips.find({"run_id": other["id"]}, {"_id": 0}).to_list(5000)
        total += commission_parts(slips)[0]
    return round(total, 2)


async def post_payroll(run: Dict[str, Any], created_by: str = "system") -> Optional[Dict[str, Any]]:
    """PK-22 (FY-06, FY-08) — resep posting gaji: (1) bila slip berkomisi dan mode proses `accrue_then_settle`, akrual
    insentif = Σ komisi SLIP (bukan dihitung ulang dari akun sales) bertanggal buku jurnal gaji — galatnya menggagalkan
    posting (dulu ditelan); (2) jurnal gaji bertanggal `run["journal_date"]`. Keduanya idempoten, jadi ulang dari panel
    tidak menggandakan jurnal. → jurnal gaji (+ `incentive_journal_id`)."""
    from services import gl_service as gl
    slips = run.get("payslips")
    if slips is None:
        slips = await db.hr_payslips.find({"run_id": run["id"]}, {"_id": 0}).to_list(5000)
    date = run.get("journal_date") or ""
    # KM-T4 — baris Lembar Insentif sudah dibebankan saat lembar disahkan: tidak ikut diakru di sini (bukan beban ganda).
    from services.hr_pay_components import commission_parts
    commission, _lembar = commission_parts(slips)
    incentive_je_id = ""
    if commission > 0.005 and run.get("commission_mode", "accrue_then_settle") == "accrue_then_settle":
        # Pelatihan 18 Nov (uji variasi V7) — `post_incentive_accrual(total=…)` menyamakan akrual PT·periode dengan
        # `total`. Dulu `total` = komisi proses INI saja: proses susulan kedua di bulan yang sama "mengoreksi" akrual
        # turun/naik ke komisi susulan itu, padahal jurnal gajinya tetap mendebit Hutang Insentif sebesar komisinya →
        # Beban Insentif kurang dan 2-1500 bersaldo debit. Kini total = Σ komisi slip semua proses PT·periode yang
        # sudah diposting (reguler + susulan, mode akru) + proses ini.
        commission = round(commission + await _komisi_proses_lain(run), 2)
        inc = await gl.post_incentive_accrual(run["entity_id"], run["period"], created_by, total=commission, date=date)
        incentive_je_id = (inc or {}).get("id", "")
        if not incentive_je_id:
            st = await gl.incentive_accrual_status(run["entity_id"], run["period"])
            incentive_je_id = st.get("journal_id") or ""
    je = await gl.post_payroll_run(run, slips, created_by, date=date)
    if je:
        je["incentive_journal_id"] = incentive_je_id
    return je


async def _retry_incentive_sheet(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """KM-T4 — Lembar Insentif disahkan di PT bermode `sheet` yang jurnalnya gagal: masukan gaji dipastikan ada
    (idempoten per baris), lalu jurnal beban/hutang insentif sekali (`incentive_payroll.ulang_jurnal`)."""
    from services.incentive_payroll import ulang_jurnal
    await ulang_jurnal(doc, actor)


async def _retry_interco_incentive_charge(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """KM-T4 (K-26) — tagihan insentif antar-PT: jurnal PT tertagih, pelunasan yang macet, atau pembalik anulir yang
    gagal diterbitkan lagi (`interco_charge_service.ulang`)."""
    from services.interco_charge_service import ulang
    await ulang(doc, actor)


async def _retry_payroll_run(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services.hr_payroll_service import post_run_gl
    run = await post_run_gl(doc["id"], actor)
    if run.get("gl_status") == "failed":
        raise RuntimeError(run.get("gl_error") or "jurnal gaji gagal")


# ── PK-19 — keputusan selisih bayar (`payment_variance_decisions`) ───────────────────────────────────────────────────
async def _je(source_type: str, source_id: str) -> Optional[Dict[str, Any]]:
    return await db.journal_entries.find_one({"source_type": source_type, "source_id": source_id,
                                              "status": {"$ne": "void"}}, {"_id": 0, "id": 1, "number": 1})


def _variance_label(d: Dict[str, Any]) -> str:
    return f"{d.get('number', '')} · {d.get('receipt_number') or d.get('bill_number') or ''}"


def _alloc_rows(d: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Baris alih deposit keputusan: rencana PK-19 yang sudah teralokasi; keputusan lama → `orders`."""
    if d.get("plan"):
        return [r for r in d["plan"] if r.get("allocated")]
    return [{"order_id": o.get("order_id"), "amount": float(o.get("applied") or o.get("amount") or 0)}
            for o in d.get("orders") or [] if o.get("order_id")]


def variance_decision_source(d: Dict[str, Any]) -> tuple:
    """(source_type, source_id) jurnal UTAMA keputusan — untuk `post_durable`."""
    kind = d.get("kind")
    if kind in ("writeoff", "rounding_writeoff"):
        return "payment_variance_writeoff", d["id"]
    if kind == "allocate":
        ar = next((r["order_id"] for r in _alloc_rows(d) if r.get("ar")), "-")
        return "payment_variance_alloc", f"{d['id']}:{ar}"
    if kind == "refund":
        return "cash_transaction", ((d.get("effect") or {}).get("refund") or {}).get("cash_txn_id") or "-"
    return "ap_variance_writeoff", d["id"]


async def post_variance_decision(d: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Jurnal keputusan selisih dari isi keputusan yang TERSIMPAN (dipakai keputusan dan ulang): hapus sisa Dr 6-9100 /
    Cr 1-1200 satu per keputusan; alih deposit Dr 2-1400 / Cr 1-1200 per baris (`<id>:<id pesanan>`) untuk pesanan
    yang pendapatannya sudah diakui; refund = jurnal kas `ar_refund` (Dr 2-1400 / Cr kas) lewat pembuat kas; tutup sisa
    hutang Dr 2-1100 / Cr 4-9000. Semua fungsi idempoten per sumber."""
    from services import gl_service as gl
    kind, eid, by = d.get("kind"), d.get("entity_id") or "", d.get("decided_by") or "system"
    if kind in ("writeoff", "rounding_writeoff"):
        return await gl.post_variance_writeoff(decision_id=d["id"], entity_id=eid, amount=float(d.get("amount") or 0),
                                               label=_variance_label(d), created_by=by) \
            or await _je("payment_variance_writeoff", d["id"])
    if kind == "allocate":
        first = None
        for row in _alloc_rows(d):
            if not row.get("ar"):
                continue
            sid = f"{d['id']}:{row['order_id']}"
            je = await gl.post_variance_reallocation(
                decision_id=sid, entity_id=eid, amount=float(row.get("amount") or 0),
                label=f"{d.get('number', '')} · kelebihan bayar dialihkan ke {row.get('order_number') or row['order_id']}",
                created_by=by) or await _je("payment_variance_alloc", sid)
            first = first or je
        return first
    if kind == "refund":
        cash_id = ((d.get("effect") or {}).get("refund") or {}).get("cash_txn_id") or ""
        if not cash_id:
            return None
        from services import cash_ledger
        await cash_ledger.ensure_posted(cash_id)
        return await _je("cash_transaction", cash_id)
    if kind in ("ap_writeoff", "ap_rounding_writeoff"):
        return await gl.post_ap_variance_writeoff(decision_id=d["id"], entity_id=eid,
                                                  amount=float(d.get("amount") or 0), label=_variance_label(d),
                                                  created_by=by) or await _je("ap_variance_writeoff", d["id"])
    return None


async def durable_variance_decision(d: Dict[str, Any], *, raise_on_fail: bool = False) -> Dict[str, Any]:
    from services import gl_service as gl
    st, sid = variance_decision_source(d)
    return await gl.post_durable("payment_variance_decisions", d["id"], lambda: post_variance_decision(d),
                                 source_type=st, source_id=sid, raise_on_fail=raise_on_fail)


async def post_variance_decision_reversal(d: Dict[str, Any], created_by: str = "system") -> Optional[Dict[str, Any]]:
    """Pembalik jurnal keputusan — hanya yang pernah terbit, kebalikan persis jurnal asalnya: hapus sisa Dr 1-1200 /
    Cr 6-9100; alih deposit Dr 1-1200 / Cr 2-1400 (Σ baris berjurnal) + pembalik reklas uang muka untuk baris yang
    uang mukanya sudah direklas; refund = pembalik jurnal kasnya (PK-10); tutup sisa hutang Dr 4-9000 / Cr 2-1100."""
    from services import gl_service as gl
    kind, eid, did = d.get("kind"), d.get("entity_id") or "", d["id"]
    amount = round(float(d.get("amount") or 0), 2)
    label = f"{d.get('number', '')} · {d.get('reversed_reason') or 'keputusan dianulir'}"
    rev = ("payment_variance_reversal", f"{did}:rev")
    if kind in ("writeoff", "rounding_writeoff"):
        if not await gl._already_posted("payment_variance_writeoff", did):
            return None
        return await gl.post_variance_reversal(decision_id=did, entity_id=eid, amount=amount,
                                               debit_acc=gl.ACC_PIUTANG, credit_acc=gl.ACC_SELISIH_BAYAR,
                                               label=label, created_by=created_by) or await _je(*rev)
    if kind == "allocate":
        first, moved = None, 0.0
        legacy = await gl._already_posted("payment_variance_alloc", did)
        for row in _alloc_rows(d):
            oid, amt = row["order_id"], round(float(row.get("amount") or 0), 2)
            if await gl._already_posted("payment_variance_alloc", f"{did}:{oid}"):
                moved = round(moved + amt, 2)
                continue
            order = await db.sales_orders.find_one({"id": oid}, {"_id": 0})
            if not order:
                continue
            asal = [p for p in order.get("payments") or [] if p.get("receipt_id") == did
                    and float(p.get("amount") or 0) > 0 and not p.get("reverses")]
            adv = round(sum(float(p["amount"]) for p in asal if p.get("gl_bucket") == gl.ADVANCE_BUCKET), 2)
            if legacy:
                moved = round(moved + sum(float(p["amount"]) for p in asal if p.get("gl_bucket") != gl.ADVANCE_BUCKET), 2)
            if adv > 0.01 and await gl._already_posted("advance_reclass", oid):
                first = first or await gl.post_advance_reclass_reversal(order, did, adv, label=label)
        if moved > 0.01:
            je = await gl.post_variance_reversal(decision_id=did, entity_id=eid, amount=moved,
                                                 debit_acc=gl.ACC_PIUTANG, credit_acc=gl.ACC_UANG_MUKA_PELANGGAN,
                                                 label=label, created_by=created_by) or await _je(*rev)
            first = je or first
        return first
    if kind == "refund":
        cash_id = ((d.get("effect") or {}).get("refund") or {}).get("cash_txn_id") or ""
        return await gl.post_cash_void(cash_id, label=label, created_by=created_by) if cash_id else None
    if kind in ("ap_writeoff", "ap_rounding_writeoff"):
        if not await gl._already_posted("ap_variance_writeoff", did):
            return None
        return await gl.post_variance_reversal(decision_id=did, entity_id=eid, amount=amount,
                                               debit_acc=gl.ACC_PENDAPATAN_LAIN, credit_acc=gl.ACC_HUTANG,
                                               label=label, created_by=created_by) or await _je(*rev)
    return None


async def durable_variance_reversal(d: Dict[str, Any], created_by: str = "system", *,
                                    raise_on_fail: bool = False) -> Dict[str, Any]:
    from services import gl_service as gl
    if d.get("kind") == "refund":
        st, sid = "cash_transaction_void", ((d.get("effect") or {}).get("refund") or {}).get("cash_txn_id") or "-"
    else:
        st, sid = "payment_variance_reversal", f"{d['id']}:rev"
    return await gl.post_durable("payment_variance_decisions", d["id"],
                                 lambda: post_variance_decision_reversal(d, created_by),
                                 source_type=st, source_id=sid, field="reversal_gl_status", raise_on_fail=raise_on_fail)


async def _retry_payment_variance(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    if doc.get("gl_status") == "failed":
        if doc.get("status") in ("pending", "failed"):
            raise RuntimeError("Keputusan ini belum tuntas. Kirim keputusan yang sama lagi dari antrean Selisih Bayar "
                               "untuk melanjutkannya.")
        jr = await durable_variance_decision(doc, raise_on_fail=True)
        je = jr.get("journal") or await db.journal_entries.find_one(
            {"id": jr.get("journal_entry_id") or "-"}, {"_id": 0, "id": 1, "number": 1}) or {}
        await db.payment_variance_decisions.update_one({"id": doc["id"]}, {"$set": {
            "je_id": je.get("id", ""), "je_number": je.get("number", "")}})
    if doc.get("reversal_gl_status") == "failed":
        await durable_variance_reversal(doc, actor.get("name", "system"), raise_on_fail=True)


async def _retry_vendor_bill(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services import gl_service as gl
    await gl.post_durable("vendor_bills", doc["id"], lambda: gl.post_vendor_bill(doc), source_type="vendor_bill",
                          source_id=doc["id"], raise_on_fail=True)


async def _retry_landed_cost(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services import gl_service as gl
    if doc.get("allocated_total") is None:
        raise RuntimeError("Nominal kapitalisasi voucher tidak tersimpan — tidak bisa diulang otomatis.")
    await gl.post_durable("landed_cost_vouchers", doc["id"],
                          lambda: gl.post_landed_cost(doc, amount=float(doc["allocated_total"]),
                                                      label=doc.get("voucher_number") or doc["id"]),
                          source_type="landed_cost", source_id=doc["id"], raise_on_fail=True)


async def _retry_makloon_step(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    seq = int(str(doc["_baris"]).rsplit(":", 1)[1])
    await durable_makloon_step(doc, seq, raise_on_fail=True)


async def _retry_cut_waste(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    from services import gl_service as gl
    sid = doc.get("gl_source_id") or f"cutw:{doc['id'].removeprefix('mov_cutw_')}"
    await gl.post_durable("inventory_movements", doc["id"],
                          lambda: gl.post_inventory_writeoff(
                              roll_id=doc.get("roll_id") or "", entity_id=doc.get("owner_entity_id") or "",
                              amount=float(doc.get("gl_amount") or 0), reason=doc.get("gl_reason") or "",
                              label=doc.get("gl_label") or "", source_id=sid),
                          source_type="inventory_writeoff", source_id=sid, raise_on_fail=True)


async def _retry_receipt_void(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    await durable_receipt_void(doc, actor.get("name", "system"), raise_on_fail=True)


async def _retry_fixed_asset(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-23 — kas perolehan (sumber `kas`, id tetap) dipastikan ada, lalu jurnal perolehan."""
    from services.fixed_asset_service import retry_acquisition
    await retry_acquisition(doc, actor)


async def _retry_asset_depreciation(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-23 — jurnal entri penyusutan yang gagal; register aset diperbarui sesudah terbit."""
    from services.fixed_asset_service import repost_depreciation_entry
    await repost_depreciation_entry(doc, actor)


async def _retry_fixed_asset_transfer(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-23 — niat pindah aset antar-PT yang jurnal kembarnya belum lengkap diteruskan (dua buku)."""
    from services.fixed_asset_transfer_service import resume_transfer
    await resume_transfer(doc, actor)


async def _retry_fixed_asset_settlement(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-23 — pembayaran pindah aset yang kasnya tercatat tetapi jurnal kembarnya belum lengkap diteruskan."""
    from services.fixed_asset_transfer_service import resume_settlement
    await resume_settlement(doc, actor)


async def _retry_fixed_asset_disposal(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-23 — pelepasan yang macet di `disposing` dengan jurnal gagal diselesaikan dari niatnya."""
    from services.fixed_asset_service import resume_disposal
    await resume_disposal(doc, actor)


async def _retry_credit_note(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-32 — semua sumber nota (retur per barang, retur per roll, amandemen, batal item, nota debit): ulang = mesin
    nota menuntaskan langkah yang belum `done` (nota lama tanpa `effects`: hanya jurnalnya)."""
    from services.credit_note_service import settle
    await settle(doc["id"], actor, raise_on_fail=True)


async def durable_grir_clearing(po: Dict[str, Any], clearing: Dict[str, Any], *,
                                raise_on_fail: bool = False) -> Dict[str, Any]:
    """PK-28 — pintu tahan-gagal satu kliring GR/IR: hasil ditulis ke `grir_clearings.$.gl_status` unsur itu."""
    from services import gl_service as gl
    seq = int(clearing["seq"])
    return await gl.post_durable("purchase_orders", po["id"], lambda: gl.post_grir_clearing(po, clearing),
                                 source_type="grir_clearing", source_id=f"{po['id']}:{seq}",
                                 field="grir_clearings.$.gl_status", match={"grir_clearings.seq": seq},
                                 raise_on_fail=raise_on_fail)


def grir_clearing_amount(clearing: Dict[str, Any]) -> float:
    return round(float(clearing.get("amount") or 0), 2)


async def _retry_grir_clearing(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    seq = int(str(doc["_baris"]).rsplit(":", 1)[1])
    clearing = step_of(doc, seq, "grir_clearings")
    if not clearing:
        raise RuntimeError("Unsur kliring GR/IR tidak ditemukan.")
    await durable_grir_clearing(doc, clearing, raise_on_fail=True)


async def _retry_petty_cash_settlement(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-24 — LPJ disetujui yang jurnalnya gagal: diteruskan dari langkah JURNAL (`repost_settlement`), lalu SELESAI
    (status `posted_to_gl`, hutang reimburse / sisa dikembalikan, PD induk `settled`)."""
    from services.cash_advance_service import repost_settlement
    await repost_settlement(doc["id"], actor)


async def _retry_cash_holding(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PM-T4 — jurnal titipan tunai sales yang gagal (Dr piutang titipan karyawan / Cr sisi kredit kwitansi): diulang
    lewat pintu yang sama; status kwitansinya ikut diperbarui."""
    from services.cash_holding_service import ulang_jurnal
    await ulang_jurnal(doc["id"], actor.get("name", "system"))


async def _retry_cash_deposit(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PM-T4 — setoran titipan yang kasnya tercatat tetapi jurnal kasnya gagal: jurnal kas yang sama (id tetap)."""
    from services.cash_holding_service import ulang_jurnal_setoran
    await ulang_jurnal_setoran(doc)


async def _retry_finance_case(doc: Dict[str, Any], actor: Dict[str, Any]) -> None:
    """PK-25 — kasus keuangan yang penyelesaiannya tersimpan (niat `pending`) tetapi jurnalnya gagal: `resolve` dipanggil
    lagi dengan isi niat yang tersimpan — efek yang sudah jadi dipakai ulang (id tetap), jurnal ber-kunci per kejadian
    diadopsi bila sudah ada. Masih gagal → melempar (panel: 409 "Posting masih gagal: …")."""
    from services.finance_case_service import resume_resolution
    await resume_resolution(doc, actor)


# ── Registri ─────────────────────────────────────────────────────────────────────────────────────────────────────────
KINDS: Dict[str, Dict[str, Any]] = {
    # PK-20 — jurnal kas lewat pintu `post_cash_durable` (fungsi pribadi `_post_cash_transaction`, bukan `post_*`).
    "cash_transaction": {
        "label": "Transaksi Kas", "collection": "cash_transactions", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": _NOMINAL_LAMA,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "cash_transaction", "posters": (), "retry": _retry_cash},
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
    # CR-T2 — jadwal tagihan surat jalan (bukan jurnal: kait sesudah jurnal pendapatan `shipment_revenue` terbit)
    "shipment_billing": {
        "label": "Jadwal Tagihan Surat Jalan", "collection": "shipments", "failed_query": {"billing_status": "failed"},
        "entity_field": "entity_id", "number_field": "shipment_no", "amount_field": _NOMINAL_LAMA,
        "status_field": "billing_status", "error_field": "billing_error", "failed_at_field": "billing_failed_at",
        "doc_type": "shipment", "posters": (), "retry": _retry_shipment_billing},
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
    # ── PK-18 — jenis baru (baris 6–12 tabel spesifikasi) ──
    "credit_note": {
        "label": "Nota Kredit", "collection": "credit_notes", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "gross_amount",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "credit_note",
        "posters": ("post_sales_return", "post_sales_return_settlement", "post_amendment_credit_note",
                    "post_amendment_debit_note"),
        "retry": _retry_credit_note},
    "vendor_bill": {
        "label": "Faktur Pemasok", "collection": "vendor_bills", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "bill_number", "amount_field": "grand_total",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "vendor_bill", "posters": ("post_vendor_bill",), "retry": _retry_vendor_bill},
    "landed_cost": {
        "label": "Landed Cost", "collection": "landed_cost_vouchers", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "voucher_number", "amount_field": "allocated_total",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "landed_cost", "posters": ("post_landed_cost",), "retry": _retry_landed_cost},
    "makloon_step": {
        "label": "Langkah Makloon", "collection": "makloon_orders", "failed_query": {"steps.gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "mko_number", "amount_field": "steps",
        "status_field": "steps.$.gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "makloon_order", "per_step": True,
        "posters": ("post_subcon_issue", "post_subcon_service", "post_subcon_receipt", "reverse_subcon_issue",
                    "post_subcon_service_invoice"),   # MP-T4b (K-78) — faktur mitra dicocokkan: GR/IR → hutang
        "retry": _retry_makloon_step},
    "cut_waste": {
        "label": "Susut Potong", "collection": "inventory_movements",
        "failed_query": {"movement_type": "cut_waste", "gl_status": "failed"}, "entity_field": "owner_entity_id",
        "number_field": "gl_label", "amount_field": "gl_amount", "status_field": "gl_status",
        "error_field": "gl_error", "failed_at_field": "gl_failed_at", "doc_type": "",
        "posters": ("post_inventory_writeoff",), "retry": _retry_cut_waste},
    "ar_receipt_void": {
        "label": "Pembatalan Kwitansi", "collection": "ar_receipts", "failed_query": {"void_gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "amount",
        "status_field": "void_gl_status", "error_field": "void_gl_error", "failed_at_field": "void_gl_failed_at",
        "doc_type": "ar_receipt",
        "posters": ("post_cash_void", "reverse_deposit_only_receipt", "post_advance_reclass_reversal",
                    "reverse_cash_holding"),   # PM-T4 — pembalik jurnal titipan kwitansi yang dibatalkan
        "retry": _retry_receipt_void},
    "fixed_asset": {
        "label": "Aset Tetap", "collection": "fin_fixed_assets", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "acquisition_cost",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "", "link": {"view": "fixed-assets", "tab": "", "focus_type": "fixed_asset"},
        "posters": ("post_asset_acquisition",), "retry": _retry_fixed_asset},
    # ── PK-22 — jurnal gaji (proses tetap `approved` saat gagal; ulang = posting lagi). Void gagal → status kembali
    # (`posted`) dan galat tampil di layar penggajian (`void_gl_status`; butuh alasan, tidak menunggu di panel).
    # PY-T4 — bayar gaji = kas keluar lewat pembuat kas: jurnalnya yang gagal tampil sebagai Transaksi Kas; ulangnya
    # menyelesaikan proses (`_retry_cash` → `hr_payroll_pay.selesaikan_dari_kas`).
    "payroll_run": {
        "label": "Penggajian", "collection": "hr_payroll_runs",
        "failed_query": {"gl_status": "failed", "status": "approved"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "totals.net",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "payroll_run", "posters": ("post_payroll_run", "post_incentive_accrual"),
        "retry": _retry_payroll_run},
    # ── KM-T4 — Lembar Insentif disahkan di PT bermode `sheet` (gagal → tetap `approved`, ulang = masukan + jurnal) dan
    #    tagihan insentif antar-PT (jurnal PT tertagih lewat `twin_journal.post_twin`, pelunasan, pembalik anulir) ──
    "incentive_sheet": {
        "label": "Lembar Insentif", "collection": "incentive_sheets",
        "failed_query": {"gl_status": "failed", "status": {"$in": ["approved", "paid"]}},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "totals.amount", "amount_abs": True,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at", "doc_type": "",
        "link": {"view": "incentive-sheets", "tab": "", "focus_type": "incentive_sheet"},
        "posters": ("post_incentive_sheet",), "retry": _retry_incentive_sheet},
    "interco_incentive_charge": {
        "label": "Tagihan Insentif Antar-PT", "collection": "interco_charges",
        "failed_query": {"$or": [{"gl_status": "failed"}, {"gl_status_settle_payer": "failed"},
                                 {"gl_status_settle_payee": "failed"}, {"void_gl_status": "failed"}]},
        "entity_field": "to_entity_id", "number_field": "number", "amount_field": "amount", "amount_abs": True,
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at", "doc_type": "",
        "link": {"view": "interco", "tab": "loans", "focus_type": "interco_charge"},
        "posters": (), "retry": _retry_interco_incentive_charge},
    # ── PK-24 — pertanggungjawaban kas kecil (LPJ) yang disetujui; jurnal beban per kategori / Cr uang muka ──
    "petty_cash_settlement": {
        "label": "Pertanggungjawaban Kas Kecil (LPJ)", "collection": "cash_advance_settlements",
        "failed_query": {"gl_status": "failed"}, "entity_field": "entity_id", "number_field": "number",
        "amount_field": "total_pengeluaran", "status_field": "gl_status", "error_field": "gl_error",
        "failed_at_field": "gl_failed_at", "doc_type": "cash_settlement",
        "posters": ("post_petty_cash_settlement",), "retry": _retry_petty_cash_settlement},
    # ── PK-23 — penyusutan per (aset, periode) dan pelepasan aset ──
    "asset_depreciation": {
        "label": "Penyusutan Aset", "collection": "fin_depreciation_entries", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "gl_label", "amount_field": "amount",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "", "link": {"view": "fixed-assets", "tab": "", "focus_type": "fixed_asset"},
        "link_id_field": "asset_id", "posters": ("post_depreciation",), "retry": _retry_asset_depreciation},
    # Jurnal pelepasan gagal → status aset DIKEMBALIKAN (409 di layar). Baris panel hanya untuk pelepasan yang macet
    # di `disposing` (pengembalian status tidak sempat ditulis); ulang = selesaikan pelepasan dari niatnya.
    "fixed_asset_disposal": {
        "label": "Pelepasan Aset", "collection": "fin_fixed_assets",
        "failed_query": {"status": "disposing", "disposal_gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "book_value",
        "status_field": "disposal_gl_status", "error_field": "disposal_gl_error",
        "failed_at_field": "disposal_gl_failed_at", "doc_type": "",
        "link": {"view": "fixed-assets", "tab": "", "focus_type": "fixed_asset"},
        "posters": ("post_asset_disposal",), "retry": _retry_fixed_asset_disposal},
    # Pindah antar-PT: jurnal kembar lewat `twin_journal.post_twin` (PK-06). Sisi pengirim di aset lama
    # (`gl_status_transfer`); sisi penerima = jurnal perolehan aset pengganti (jenis `fixed_asset`). Pembayaran: satu
    # baris per sisi (pembayar = PT penerima aset, penerima uang = PT pengirim).
    "fixed_asset_transfer": {
        "label": "Pindah Aset Antar-PT", "collection": "fin_fixed_assets",
        "failed_query": {"gl_status_transfer": "failed"}, "entity_field": "entity_id", "number_field": "number",
        "amount_field": "transfer.intent.plan.price", "status_field": "gl_status_transfer",
        "error_field": "gl_error_transfer", "failed_at_field": "updated_at", "doc_type": "",
        "link": {"view": "fixed-assets", "tab": "", "focus_type": "fixed_asset"},
        "posters": (), "retry": _retry_fixed_asset_transfer},
    "fixed_asset_settle_payer": {
        "label": "Bayar Pindah Aset (pembayar)", "collection": "fin_fixed_assets",
        "failed_query": {"gl_status_settle_payer": "failed"}, "entity_field": "transfer.to_entity_id",
        "number_field": "number", "amount_field": "transfer.price", "status_field": "gl_status_settle_payer",
        "error_field": "gl_error_settle_payer", "failed_at_field": "updated_at", "doc_type": "",
        "link": {"view": "fixed-assets", "tab": "", "focus_type": "fixed_asset"},
        "posters": (), "retry": _retry_fixed_asset_settlement},
    "fixed_asset_settle_payee": {
        "label": "Bayar Pindah Aset (penerima)", "collection": "fin_fixed_assets",
        "failed_query": {"gl_status_settle_payee": "failed"}, "entity_field": "transfer.from_entity_id",
        "number_field": "number", "amount_field": "transfer.price", "status_field": "gl_status_settle_payee",
        "error_field": "gl_error_settle_payee", "failed_at_field": "updated_at", "doc_type": "",
        "link": {"view": "fixed-assets", "tab": "", "focus_type": "fixed_asset"},
        "posters": (), "retry": _retry_fixed_asset_settlement},
    # ── PK-19 — keputusan selisih bayar: jurnal keputusan (`gl_status`) dan pembaliknya (`reversal_gl_status`) ──
    "payment_variance": {
        "label": "Keputusan Selisih Bayar", "collection": "payment_variance_decisions",
        "failed_query": {"$or": [{"gl_status": "failed"}, {"reversal_gl_status": "failed"}]},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "amount",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "payment_variance",
        "posters": ("post_variance_writeoff", "post_variance_reallocation", "post_ap_variance_writeoff",
                    "post_variance_reversal"),
        "retry": _retry_payment_variance},
    # ── PK-28 — kliring sisa GR/IR: satu baris panel per unsur `grir_clearings[]` yang gagal ──
    "grir_clearing": {
        "label": "Kliring GR/IR", "collection": "purchase_orders", "failed_query": {"grir_clearings.gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "po_number", "amount_field": "grir_clearings",
        "status_field": "grir_clearings.$.gl_status", "error_field": "gl_error", "failed_at_field": "updated_at",
        "doc_type": "purchase_order", "per_step": True, "items_field": "grir_clearings",
        "item_amount": grir_clearing_amount, "item_label": "kliring",
        "posters": ("post_grir_clearing",), "retry": _retry_grir_clearing},
    # ── PK-25 — penyelesaian kasus keuangan: jurnal kasus (dan jurnal kembar salah PT) gagal → kasus tetap terbuka,
    #    niat `pending`; ulang = lanjutkan penyelesaian dengan isi niat yang tersimpan ──
    "finance_case": {
        "label": "Kasus Keuangan", "collection": "finance_cases", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": ("resolution_intent.payload.amount",
                                                                               "amount"),
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at",
        "doc_type": "finance_case", "posters": ("post_finance_case",), "retry": _retry_finance_case},
    # ── PM-T4 — titipan tunai sales (jurnal titipan) dan setorannya (jurnal kas lewat pembuat kas satu pintu) ──
    "cash_holding": {
        "label": "Titipan Tunai Sales", "collection": "cash_holdings", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "amount",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "gl_failed_at", "doc_type": "",
        "link": {"view": "cash-holdings", "tab": "", "focus_type": "cash_holding"},
        "posters": ("post_cash_holding",), "retry": _retry_cash_holding},
    "cash_deposit": {
        "label": "Setoran Titipan Tunai", "collection": "cash_deposits", "failed_query": {"gl_status": "failed"},
        "entity_field": "entity_id", "number_field": "number", "amount_field": "amount",
        "status_field": "gl_status", "error_field": "gl_error", "failed_at_field": "updated_at", "doc_type": "",
        "link": {"view": "cash-holdings", "tab": "", "focus_type": "cash_deposit"},
        "posters": (), "retry": _retry_cash_deposit},
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


def _link(spec: Dict[str, Any], doc: Dict[str, Any], number: str) -> Dict[str, Any]:
    from services import doc_refs_service as _refs
    if spec.get("doc_type") in _refs.DOC_TYPES:
        link = _refs.link_of(spec["doc_type"], doc)
        link["number"] = link.get("number") or number
        return link
    if spec.get("link"):   # `link_id_field` (PK-23): id dokumen tujuan bila beda dari dokumen gagalnya
        return {**spec["link"], "focus_id": pick(doc, spec.get("link_id_field") or "id") or doc["id"], "number": number}
    return {}


def rows_of(kind: str, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Baris panel untuk dokumen gagal `doc` jenis `kind` (`02` L8: `link` = tujuan tautan dokumennya). Jenis
    `per_step`: satu baris per langkah yang gagal, id baris `<id dokumen>:<seq>`."""
    spec = KINDS[kind]
    number = pick(doc, spec["number_field"]) or doc.get("number") or doc["id"]
    base = {"kind": kind, "kind_label": spec["label"], "entity_id": pick(doc, spec["entity_field"]) or "",
            "updated_at": doc.get("updated_at") or doc.get("created_at") or "", "link": _link(spec, doc, number)}
    if spec.get("per_step"):
        amount_of, unsur = spec.get("item_amount") or makloon_step_amount, spec.get("item_label") or "langkah"
        return [{**base, "id": f"{doc['id']}:{st.get('seq')}", "number": f"{number} · {unsur} {st.get('seq')}",
                 "amount": amount_of(st), "error": st.get("gl_error") or "",
                 "failed_at": st.get("gl_failed_at") or base["updated_at"]}
                for st in doc.get(_items_field(spec)) or [] if st.get("gl_status") == "failed"]
    return [{**base, "id": doc["id"], "number": number, "amount": _amount(spec, doc),
             "error": pick(doc, spec["error_field"]) or doc.get("gl_error") or doc.get("reversal_gl_error") or "",
             "failed_at": pick(doc, spec["failed_at_field"]) or base["updated_at"]}]


def lookup(kind: str, row_id: str) -> Dict[str, Any]:
    """Saringan dokumen untuk id baris panel (jenis `per_step`: `<id>:<seq>` → langkah itu yang gagal)."""
    if KINDS[kind].get("per_step"):
        doc_id, _, seq = str(row_id).rpartition(":")
        if not doc_id or not seq.isdigit():
            return {"id": "__tidak_ada__"}
        return {"id": doc_id, _items_field(KINDS[kind]): {"$elemMatch": {"seq": int(seq), "gl_status": "failed"}}}
    return {"id": row_id}


def _items_field(spec: Dict[str, Any]) -> str:
    return spec.get("items_field") or "steps"


def count_pipeline(kind: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Hitungan baris (bukan dokumen) untuk jenis `per_step`."""
    arr = _items_field(KINDS[kind])
    return [{"$match": query}, {"$unwind": f"${arr}"}, {"$match": {f"{arr}.gl_status": "failed"}}, {"$count": "n"}]


def sort_spec(kind: str) -> List[tuple]:
    return [(KINDS[kind]["failed_at_field"], -1), ("id", -1)]


def sort_key(kind: str, doc: Dict[str, Any]) -> tuple:
    """Kunci urut yang SAMA dengan `sort_spec` (gabungan antar-jenis tetap konsisten dengan urutan kueri)."""
    return (str(pick(doc, KINDS[kind]["failed_at_field"]) or ""), str(doc.get("id") or ""))


def status_of(kind: str, doc: Dict[str, Any], row_id: str = "") -> Dict[str, Any]:
    spec = KINDS[kind]
    if spec.get("per_step"):
        st = step_of(doc, int(str(row_id).rpartition(":")[2] or 0), _items_field(spec))
        return {"gl_status": st.get("gl_status"), "journal_entry_id": st.get("journal_entry_id") or ""}
    f = spec["status_field"]
    jfield = f[:-len("gl_status")] + "journal_entry_id" if f.endswith("gl_status") else "journal_entry_id"
    return {"gl_status": pick(doc, f), "journal_entry_id": pick(doc, jfield) or ""}
