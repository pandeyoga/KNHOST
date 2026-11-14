"""P1 — Performance indexes (idempotent, non-fatal).

Membuat index untuk koleksi terpanas agar query umum menjadi IXSCAN
(bukan COLLSCAN). Dipanggil saat startup via bootstrap.run_bootstrap().

Aman dijalankan berulang: setiap index diberi nama deterministik; bila
sudah ada (atau field belum ada di data) proses tidak menggagalkan startup.
Semua index dibuat non-unique (kecuali yang sudah ada di tempat lain, mis.
products.sku) agar tidak bentrok dengan data seed/legacy.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List, Tuple

from pymongo import ASCENDING, DESCENDING

from db import db

logger = logging.getLogger("indexes")

# Tipe: daftar spesifikasi index per koleksi. Setiap index = list (field, arah).
IndexKeys = List[Tuple[str, int]]
A = ASCENDING
D = DESCENDING

INDEX_SPECS: Dict[str, List[IndexKeys]] = {
    # ── Inventory (paling panas) ──────────────────────────────────────────
    "inventory_rolls": [
        [("product_id", A), ("warehouse_id", A), ("owner_entity_id", A), ("status", A)],
        [("status", A), ("length_remaining", A)],
        [("warehouse_id", A), ("status", A)],
        [("owner_entity_id", A), ("status", A)],
        [("product_id", A), ("status", A)],
        [("reserved_ref", A)],
        [("earmarked_for", A)],
        [("rfid_tag_id", A)],
        [("roll_no", A)],
        [("dye_lot", A)],
        [("lot_id", A)],
        [("created_at", D)],
        [("line_code", A), ("status", A)],   # FASE L — penyaring lini di Daftar Roll
    ],
    # RF-12 — autentikasi device via hash key
    "rfid_devices": [
        [("api_key_hash", A)],
    ],
    # ── Fase C — Lot kelas satu (D-10/D-26) ───────────────────────────────
    "inventory_lots": [
        [("lot_number", A)],
        [("owner_entity_id", A), ("created_at", D)],
        [("product_id", A), ("owner_entity_id", A)],
        [("source_ref.id", A), ("product_id", A)],
        [("legacy_lot_codes", A)],
        [("dye_lot", A)],
        [("supplier_lot", A)],
        [("lot_status", A)],
        [("parent_lot_ids", A)],
        [("child_lot_ids", A)],
    ],
    # ── Fase D/E — Kontrak mitra & supplier (D-05/D-07/D-09) ──────────────
    "supplier_contracts": [
        [("contract_number", A)],
        [("entity_id", A), ("created_at", D)],
        [("contract_type", A), ("partner_id", A), ("status", A)],
        [("partner_id", A), ("process_type", A), ("product_id", A)],
        [("status", A), ("valid_to", A)],
    ],
    # ── Fase E — Barang Supplier (katalog versi supplier · E-01/E-02/E-03) ─
    "supplier_items": [
        [("entity_id", A), ("created_at", D)],
        [("supplier_id", A), ("product_id", A), ("status", A)],
        [("product_id", A)],
        [("supplier_sku", A)],
        [("barcode", A)],
    ],
    "inventory_movements": [
        [("product_id", A), ("warehouse_id", A), ("timestamp", D)],
        [("owner_entity_id", A), ("timestamp", D)],
        [("roll_id", A)],
        [("lot_id", A)],
        [("movement_type", A), ("timestamp", D)],
        [("timestamp", D)],
    ],
    "inventory_balances": [
        [("product_id", A), ("warehouse_id", A), ("owner_entity_id", A)],
        [("warehouse_id", A)],
        [("owner_entity_id", A)],
    ],
    # ── Sales & Purchase Orders ───────────────────────────────────────────
    "sales_orders": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("customer_id", A), ("created_at", D)],
        [("status", A), ("created_at", D)],
        [("number", A)],
        [("stage", A)],
        [("payment_status", A)],
        [("created_at", D)],
        # FASE L — penyaring lini di daftar & papan. `line_codes` adalah array
        # turunan dari baris; index multikey dipakai chip `?line=` supaya
        # penyaringan tidak COLLSCAN pada daftar terpanas.
        [("line_codes", A)],
        # Tanya KN F0.3 — analitik per entitas/sales/produk menurut tanggal pesanan.
        [("entity_id", A), ("created_at", A)],
        [("sales_id", A), ("created_at", A)],
        [("created_by", A), ("created_at", A)],
        [("items.product_id", A)],
        [("updated_at", A)],
    ],
    "shipments": [
        [("entity_id", A), ("created_at", A)],
    ],
    "credit_notes": [
        [("entity_id", A), ("created_at", A)],
    ],
    # Tanya KN F1 — tabel fakta penjualan.
    "fact_sales_lines": [
        [("entity_id", A), ("date_wib", A)],
        [("entity_id", A), ("sales_id", A), ("date_wib", A)],
        [("entity_id", A), ("customer_id", A), ("date_wib", A)],
        [("entity_id", A), ("product_id", A), ("date_wib", A)],
        [("so_id", A)],
    ],
    "purchase_orders": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("supplier_id", A), ("created_at", D)],
        [("status", A), ("created_at", D)],
        [("warehouse_id", A), ("status", A)],
        [("line_codes", A)],   # FASE L
        [("po_number", A)],
        [("payment_status", A)],
        [("created_at", D)],
    ],
    "goods_receipts": [   # GRN Fase 2
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("lines.target.task_id", A)],
        [("source.po_ids", A)],
        [("entity_id", A), ("files.sha256_original", A)],
    ],
    "supplier_dn_profiles": [[("entity_id", A), ("partner_id", A)]],
    "ocr_samples": [[("entity_id", A), ("created_at", A)], [("source_grn_id", A)]],
    "ocr_sample_runs": [[("entity_id", A), ("created_at", A)]],
    "wms_tasks": [
        [("flow_type", A), ("status", A)],
        [("entity_id", A), ("status", A)],
        [("warehouse_id", A), ("status", A)],
        [("po_id", A)],
        [("product_id", A)],
        [("source_type", A), ("status", A)],
        [("created_at", D)],
    ],
    # ── Finance / GL ──────────────────────────────────────────────────────
    "journal_entries": [
        [("entity_id", A), ("date", D)],
        [("source_type", A), ("source_id", A)],
        [("status", A), ("date", D)],
        [("entity_id", A), ("lines.account_code", A), ("date", A)],   # Tanya KN F0.3
        [("number", A)],
        [("date", D)],
    ],
    "gl_accounts": [
        [("entity_id", A), ("code", A)],
        [("type", A), ("is_active", A)],
        [("parent_code", A)],
    ],
    "gl_postings": [
        [("entity_id", A), ("account_code", A), ("date", D)],
        [("source_type", A), ("source_id", A)],
        [("date", D)],
    ],
    "ap_payment_intents": [          # PK-05 — niat bayar hutang
        [("kind", A), ("target_id", A), ("status", A)],
        [("entity_id", A), ("status", A), ("created_at", D)],
    ],
    "journal_proposals": [           # KF-T6 — usulan jurnal manual menunggu orang kedua (antrean per PT)
        [("entity_id", A), ("status", A), ("proposed_at", D)],
    ],
    "approval_policies": [           # KP-T4 — satu tabel kebijakan persetujuan (jenis, PT, jenjang, urutan)
        [("doc_kind", A), ("entity_id", A), ("level", A), ("sort", A)],
    ],
    "vendor_bills": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("supplier_id", A)],
        [("po_id", A)],
        [("makloon_order_id", A)],
        [("bill_number", A)],
        [("bill_date", D)],
    ],
    "ar_receipts": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("customer_id", A)],
        [("number", A)],
        [("receipt_date", D)],
    ],
    "tax_invoices": [
        [("entity_id", A), ("status", A)],
        [("customer_id", A)],
        [("order_id", A)],
        [("number", A)],
        [("faktur_date", D)],
    ],
    # ── Master data ───────────────────────────────────────────────────────
    "customers": [
        [("entity_id", A), ("status", A)],
        [("assigned_sales_id", A)],
        [("customer_group_id", A)],
        [("code", A)],
        [("segment", A)],
    ],
    "suppliers": [
        [("entity_id", A), ("status", A)],
        [("code", A)],
        [("goods_type", A)],
    ],
    "products": [
        [("status", A)],
        [("category", A)],
        [("template_id", A)],
        [("stage", A)],
        [("supplier", A)],
        # FASE L — pagar & penyaring lini dipakai di SETIAP daftar produk
        # (katalog, POS, Master Produk), jadi ini index terpanas fase ini.
        [("line_code", A), ("status", A)],
    ],
    # ── FASE L — master lini produk (berlapis global → badan usaha) ────────
    # `(entity_id, code)` melayani `resolve_list_scope_inherit` + keunikan kunci
    # per lapisan; `(sort, code)` melayani urutan tampilan master & dropdown.
    "product_lines": [
        [("entity_id", A), ("code", A)],
        [("sort", A), ("code", A)],
        [("active", A)],
    ],
    # ── FASE T — master tahapan proses (berlapis global → badan usaha) ────
    # `(entity_id, code)` melayani `resolve_list_scope_inherit` + keunikan kunci per
    # lapisan; `(seq, code)` melayani urutan papan & dropdown langkah SPK;
    # `(process_type)` melayani gate INV-DOMAIN-06 (mencari tahap per jenis proses).
    "process_stages": [
        [("entity_id", A), ("code", A)],
        [("seq", A), ("code", A)],
        [("active", A)],
        [("process_type", A)],
        [("kind", A)],
    ],
    # ── FASE S — master jenis sampling (berlapis global → badan usaha) ────
    # `(entity_id, code)` melayani `resolve_list_scope_inherit` + keunikan kunci per
    # lapisan; `(seq, code)` melayani urutan form & pemilih jenis; `(requires_design)`
    # melayani gate INV-SAMPLE-01 (mencari jenis yang menuntut kode desain).
    "sample_types": [
        [("entity_id", A), ("code", A)],
        [("seq", A), ("code", A)],
        [("active", A)],
        [("requires_design", A)],
    ],
    # ── Returns / Requisitions / Transfers / Cycle Count ──────────────────
    "purchase_returns": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("supplier_id", A)],
        [("po_id", A)],
        [("number", A)],
    ],
    "sales_returns": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("customer_id", A)],
        [("order_id", A)],
        [("number", A)],
    ],
    "purchase_requisitions": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("approval_status", A)],
        [("po_id", A)],
        [("number", A)],
        [("line_codes", A)],   # FASE L
    ],
    "special_orders": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("customer_id", A)],
        [("number", A)],
    ],
    "warehouse_transfers": [
        [("entity_id", A), ("status", A), ("created_at", D)],
        [("source_warehouse_id", A)],
        [("dest_warehouse_id", A)],
        [("code", A)],
    ],
    "cycle_count_sessions": [
        [("entity_id", A), ("status", A)],
        [("warehouse_id", A)],
        [("number", A)],
    ],
    "makloon_orders": [
        [("entity_id", A), ("status", A)],
        [("po_id", A)],
        [("mko_number", A)],
    ],
    # ── Audit & Notifications ─────────────────────────────────────────────
    "audit_logs": [
        [("entity_id", A), ("timestamp", D)],
        [("entity_type", A), ("entity_id", A), ("timestamp", D)],
        [("resource", A), ("resource_id", A)],
        [("user_id", A)],
        [("timestamp", D)],
    ],
    "notifications": [
        [("recipient_user", A), ("read", A)],
        [("recipient_role", A), ("read", A)],
        [("entity_id", A), ("created_at", D)],
        [("created_at", D)],
        [("dedupe_key", A)],          # R6.5 — dedupe notifikasi per (type, ref, hari)
        [("type", A), ("ref", A), ("read", A)],
    ],
    # ── R6.5 Scheduler & Outbox WhatsApp ──────────────────────────────────
    "sys_scheduler_runs": [
        [("job_id", A), ("started_at", D)],
        [("started_at", D)],
        [("status", A), ("started_at", D)],
    ],
    "sys_wa_outbox": [
        [("dedupe_key", A)],
        [("status", A), ("created_at", D)],
        [("created_at", D)],
        [("notification_id", A)],
    ],
    # FASE F — R&D: spesifikasi & permintaan sample (labdip/proofing)
    "md_specs": [
        [("entity_id", A), ("created_at", D)],
        [("status", A), ("created_at", D)],
        [("number", A)],
        [("product_id", A)],
    ],
    "md_samples": [
        [("entity_id", A), ("created_at", D)],
        [("status", A), ("created_at", D)],
        [("spec_id", A)],
        [("number", A)],
        # FASE S — `sample_types` adalah ARRAY (satu permintaan boleh menempuh
        # labdip + handfeel). Index multikey ini melayani penyaring jenis di layar
        # Permintaan Sample; index lama `sample_type` dibuang bersama fieldnya
        # supaya tidak ada index yang menunjuk field yang tak pernah ada lagi.
        [("sample_types", A), ("status", A)],
        # FASE S — tautan pesanan (user story S.F-2: dari layar pesanan bisa
        # melihat sample-nya) + penanda pelaksanaan.
        [("so_id", A)],
        [("delivered_at", D)],
    ],
    # ── FASE D — Permintaan Desain (papan kanban + rapor desainer) ─────────
    "design_requests": [
        [("entity_id", A), ("status", A)],
        [("entity_id", A), ("created_at", D)],
        [("assigned_to", A), ("status", A)],
        [("so_id", A)],
        [("number", A)],
        [("line_code", A), ("status", A)],
        [("due_date", A), ("status", A)],
    ],
    # ── FASE I — Inspeksi & QC sebagai dokumen (SPK + hasil warna/handfeel) ─
    "inspections": [
        [("entity_id", A), ("status", A)],
        [("entity_id", A), ("created_at", D)],
        [("kind", A), ("ref_doc_id", A)],
        [("task_id", A)],
        [("assigned_to", A), ("status", A)],
        [("line_code", A), ("status", A)],
        [("number", A)],
        [("lines.roll_id", A)],
    ],
    # ── FASE I — master alasan keluhan retur (berlapis global→badan usaha) ───
    "complaint_reasons": [
        [("entity_id", A), ("code", A)],
        [("entity_id", A), ("seq", A)],
        [("active", A)],
    ],
}


# KN-A12 — kolom nomor dokumen yang WAJIB unik (koleksi, field).
UNIQUE_DOC_NUMBER_FIELDS = [
    ("sales_orders", "number"), ("sales_returns", "number"), ("credit_notes", "number"),
    ("purchase_orders", "po_number"), ("purchase_returns", "number"),
    ("purchase_returns", "debit_note_number"), ("purchase_requisitions", "number"),
    ("vendor_bills", "bill_number"), ("landed_cost_vouchers", "voucher_number"),
    ("rfqs", "rfq_number"), ("makloon_orders", "mko_number"), ("mfg_work_orders", "wo_number"),
    ("inventory_rolls", "roll_no"),   # temuan lama #12 — nomor roll unik
    ("customers", "code"),            # temuan lama #13 — kode pelanggan unik
    ("ar_receipts", "number"), ("cash_transactions", "number"), ("journal_entries", "number"),
    ("contra_bons", "number"), ("special_orders", "number"), ("tax_invoices", "number"),
    ("store_credit_redemptions", "number"), ("hr_employees", "code"),
    ("suppliers", "code"), ("makloons", "code"),
    ("goods_receipts", "number"),   # GRN Fase 2
]


# ── FIX-5 (B3a SCH-9, PREP-H §9) — kunci aplikasi `id` ────────────────────────────────────────────────────────
# Dulu 131/132 koleksi tanpa index `id`: setiap `find_one/update_one({"id": …})` = COLLSCAN (roll 46.700 dok di data
# acuan, 346.700 di uji beban; mutasi 85 rb). Index `uq_id` = UNIK + PARSIAL `{id: {$gt: ""}}`:
#   * parsial `$gt ""` (bukan `$type`) — dipakai planner untuk `{id: "…"}` dan `{id: {$in: […]}}` (diuji `explain`,
#     Mongo 7); dokumen tanpa `id` / `id` null / kosong tidak ikut index → tidak saling bentrok;
#   * unik hanya bila data mengizinkan: bila sudah ada `id` kembar, pembuatan unik GAGAL → index NON-UNIK parsial
#     `kn_id_dupe` (tetap mempercepat) + galat berisik di log + daftar `id_dupes` di ringkasan (temuan data);
#   * index non-unik `kn_gate_id_1` (PREP-H) di koleksi yang sama dibuang sesudah `uq_id` ada (kunci identik).
# Cakupan: koleksi yang dicari per `id` di jalur WMS-RFID & stok + dokumen yang dirujuknya (sensus 9 Nov 2026: 0 `id`
# kembar di data acuan). Koleksi lain belum (sisa FIX-5).
ID_PARTIAL = {"id": {"$gt": ""}}
ID_INDEX_COLLECTIONS: List[str] = [
    # stok & roll
    "inventory_rolls", "inventory_movements", "inventory_balances", "inventory_lots", "material_reservations",
    "products", "warehouses", "warehouse_sites",
    # RFID
    "rfid_tags", "rfid_devices", "rfid_print_jobs", "rfid_verify_sessions", "rfid_incidents", "rfid_cycle_counts",
    "rfid_reads", "rfid_passages", "roll_label_prints",
    # dokumen WMS
    "putaway_orders", "warehouse_transfers", "shipments", "logistics_deliveries", "goods_receipts", "wms_tasks",
    "cycle_count_sessions", "inspections", "makloon_orders", "repair_orders", "mdq_cuts", "internal_requests",
    # dokumen order/mitra yang dibaca jalur gudang
    "sales_orders", "purchase_orders", "sales_returns", "purchase_returns", "special_orders",
    "interco_transactions", "interco_returns", "customers", "suppliers", "business_entities", "users",
    # PK-05 — id niat bayar = kunci idempotensi (turunan SHA-256): keunikannya dijaga database.
    "ap_payment_intents",
    # PK-06 — id settlement antar-PT turunan kunci idempotensi.
    "interco_settlements",
    # KF-T6 — usulan jurnal manual (`jprop_…`).
    "journal_proposals",
    # KP-T4 — baris kebijakan persetujuan (`appol_…`).
    "approval_policies",
]

# FIX-5 — rujukan bersarang roll yang dicari per nilai (B3a SCH-9: index `reserved_ref` utuh tidak terpakai oleh
# kueri `reserved_ref.id`). Parsial `$gt ""` → hanya roll yang punya rujukan itu yang masuk index (kecil).
ROLL_REF_FIELDS = ("reserved_ref.id", "transfer_ref.id", "last_transfer.ref_id", "returned_from_transfer.ref_id",
                   "active_movement.id", "bucket_ref.id", "length_reservations.id", "length_reservations.ref.id",
                   "earmarked_for.id", "acquired.ref_id")
# FIX-5 — index jalur panas lain (profil/explain uji beban FIX-5): non-unik, nama `kn_…` deterministik.
HOT_PATH_INDEXES: Dict[str, List[IndexKeys]] = {
    "putaway_orders": [[("status", A), ("created_at", D)]],          # PA hidup per roll (`rolls_in_live_orders`)
    "warehouse_transfers": [[("status", A), ("created_at", D)]],
    "wms_tasks": [[("allocation_id", A), ("flow_type", A), ("status", A)]],   # pindah alokasi saat terima transfer
    "material_reservations": [[("product_id", A), ("status", A)]],
    "rfid_tags": [[("epc", A)],
                  [("owner_entity_id", A), ("status", A), ("encoded_at", D)]],   # daftar tag (`/rfid/tags`) + jumlahnya
}


async def ensure_id_index(coll_name: str) -> str:
    """Index `id` satu koleksi (idempoten). → "existed" | "unique" | "non_unique_dupes" | "failed"."""
    from pymongo.errors import OperationFailure
    coll = db[coll_name]
    try:
        info = await coll.index_information()
    except Exception:  # noqa: BLE001
        info = {}
    state = "existed" if ("uq_id" in info or "kn_id_dupe" in info) else ""
    if not state:
        try:
            await coll.create_index([("id", ASCENDING)], name="uq_id", unique=True, background=True,
                                    partialFilterExpression=ID_PARTIAL)
            state = "unique"
        except OperationFailure as exc:
            if getattr(exc, "code", None) not in (11000, 11001) and "E11000" not in str(exc):
                logger.warning("[indexes] %s.uq_id gagal: %s", coll_name, exc)
                return "failed"
            logger.error("[indexes] UNIK %s.id GAGAL — ada `id` kembar di data (temuan data, FIX-5): %s", coll_name, exc)
            try:
                await coll.create_index([("id", ASCENDING)], name="kn_id_dupe", background=True,
                                        partialFilterExpression=ID_PARTIAL)
                state = "non_unique_dupes"
            except Exception as exc2:  # noqa: BLE001
                logger.warning("[indexes] %s.kn_id_dupe gagal: %s", coll_name, exc2)
                return "failed"
        except Exception as exc:  # noqa: BLE001
            logger.warning("[indexes] %s.uq_id gagal: %s", coll_name, exc)
            return "failed"
    if "kn_gate_id_1" in info:   # PREP-H — index non-unik penuh dengan kunci sama: tidak perlu dua
        try:
            await coll.drop_index("kn_gate_id_1")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[indexes] drop %s.kn_gate_id_1 dilewati: %s", coll_name, exc)
    return state


async def ensure_id_indexes() -> Dict[str, Any]:
    """FIX-5 — index `id` + rujukan bersarang roll + jalur panas. Non-fatal & idempoten.
    Hanya koleksi yang SUDAH ada (tidak membuat koleksi kosong); koleksi baru ikut di start berikutnya."""
    out: Dict[str, Any] = {"unique": [], "existed": 0, "id_dupes": [], "failed": []}
    try:
        present = set(await db.list_collection_names())
    except Exception:  # noqa: BLE001
        present = set(ID_INDEX_COLLECTIONS) | {"inventory_rolls"} | set(HOT_PATH_INDEXES)
    for name in ID_INDEX_COLLECTIONS:
        if name not in present:
            continue
        st = await ensure_id_index(name)
        if st == "unique":
            out["unique"].append(name)
        elif st == "existed":
            out["existed"] += 1
        elif st == "non_unique_dupes":
            out["id_dupes"].append(name)
        else:
            out["failed"].append(name)
    rolls = db.inventory_rolls
    try:
        have = set((await rolls.index_information()).keys())
    except Exception:  # noqa: BLE001
        have = set()
    for field in (ROLL_REF_FIELDS if "inventory_rolls" in present else ()):
        name = "kn_ref_" + field.replace(".", "_")
        if name in have:
            continue
        try:
            await rolls.create_index([(field, ASCENDING)], name=name, background=True,
                                     partialFilterExpression={field: {"$gt": ""}})
        except Exception as exc:  # noqa: BLE001
            out["failed"].append(f"inventory_rolls.{field}")
            logger.warning("[indexes] inventory_rolls.%s gagal: %s", field, exc)
    for coll_name, specs in HOT_PATH_INDEXES.items():
        if coll_name not in present:
            continue
        coll = db[coll_name]
        try:
            have = set((await coll.index_information()).keys())
        except Exception:  # noqa: BLE001
            have = set()
        for keys in specs:
            name = _index_name(keys)
            if name in have:
                continue
            try:
                await coll.create_index(keys, name=name, background=True)
            except Exception as exc:  # noqa: BLE001
                out["failed"].append(f"{coll_name}.{name}")
                logger.warning("[indexes] %s.%s gagal: %s", coll_name, name, exc)
    if out["id_dupes"]:
        logger.error("[indexes] FIX-5 — koleksi dengan `id` kembar (index non-unik dipakai): %s", out["id_dupes"])
    return out


def _index_name(keys: IndexKeys) -> str:
    """Nama index deterministik & pendek (< 128 char)."""
    parts = []
    for field, direction in keys:
        suffix = "1" if direction == ASCENDING else "-1"
        parts.append(f"{field}_{suffix}")
    name = "kn_" + "__".join(parts)
    return name[:120]


async def ensure_performance_indexes() -> dict:
    """Buat semua index performa. Non-fatal & idempotent.

    Return ringkasan {created, existed, failed} untuk logging/verifikasi.
    """
    created = existed = failed = 0
    for collection, specs in INDEX_SPECS.items():
        coll = db[collection]
        # Ambil daftar index yang sudah ada agar hemat & log akurat.
        try:
            existing = set((await coll.index_information()).keys())
        except Exception:  # noqa: BLE001
            existing = set()
        for keys in specs:
            name = _index_name(keys)
            if name in existing:
                existed += 1
                continue
            try:
                await coll.create_index(keys, name=name, background=True)
                created += 1
            except Exception as exc:  # noqa: BLE001 — index bentrok / field issue
                failed += 1
                logger.warning("[indexes] %s.%s gagal: %s", collection, name, exc)
    summary = {"created": created, "existed": existed, "failed": failed}
    try:   # FIX-5 — index `id` & rujukan roll (juga dipanggil di awal bootstrap; idempoten)
        summary["id_index"] = await ensure_id_indexes()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[indexes] ensure_id_indexes gagal: %s", exc)
    # D-01 — kunci UNIK pada sequence nomor: dua proses tak bisa membuat counter kembar.
    try:
        await db.number_sequences.create_index(
            [("entity_id", ASCENDING), ("doc_type", ASCENDING)],
            name="uq_entity_doctype", unique=True, background=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[indexes] number_sequences unique gagal: %s", exc)
    # KN-A12 / KN-B09 (audit 2026-09-21) — INDEKS UNIK pada nomor dokumen & idempotensi GL.
    # Dulu hanya satu unique=True di seluruh berkas: nomor kembar dan jurnal ganda tersimpan
    # tanpa ditolak. `partialFilterExpression` menjaga baris lama tanpa field / kosong tetap
    # sah; bila data lama sudah kembar, pembuatan indeks GAGAL BERISIK di log (startup tidak
    # mati) — duplikatnya harus dibereskan dulu, lalu indeks lahir di restart berikutnya.
    uq_summary = {"created": 0, "failed": []}
    for coll_name, field in UNIQUE_DOC_NUMBER_FIELDS:
        try:
            await db[coll_name].create_index(
                [(field, ASCENDING)], name=f"uq_{field}", unique=True, background=True,
                partialFilterExpression={field: {"$type": "string", "$gt": ""}})
            uq_summary["created"] += 1
        except Exception as exc:  # noqa: BLE001
            uq_summary["failed"].append(f"{coll_name}.{field}")
            logger.error("[indexes] UNIK %s.%s GAGAL (kemungkinan nomor kembar di data lama): %s",
                         coll_name, field, exc)
    # KN-B09 `uq_je_source_active` (satu jurnal aktif per sumber) pindah ke REQUIRED_UNIQUE_INDEXES (PK-14):
    # gagal dibuat = aplikasi tidak dijalankan, bukan sekadar baris log.
    try:
        # PK-05 (SL-12) — satu nomor faktur pemasok AKTIF per (PT, pemasok). Data lama kembar → gagal berisik (H6);
        # cek-lalu-sisip di router tetap berjalan.
        await db.vendor_bills.create_index(
            [("entity_id", ASCENDING), ("supplier_id", ASCENDING), ("supplier_invoice_no", ASCENDING)],
            name="uq_supplier_invoice", unique=True, background=True,
            partialFilterExpression={"supplier_invoice_no": {"$type": "string", "$gt": ""},
                                     "status": {"$in": ["draft", "pending_approval", "posted", "paid"]}})
    except Exception as exc:  # noqa: BLE001
        uq_summary["failed"].append("vendor_bills.supplier_invoice")
        logger.error("[indexes] UNIK vendor_bills(entity_id,supplier_id,supplier_invoice_no) GAGAL "
                     "(nomor faktur pemasok kembar di data lama): %s", exc)
    try:
        # GRN Fase 2 (§4.6) — satu SJ aktif per (entitas, mitra, nomor, tahun); dua GRN tak bisa dihitung bersamaan.
        await db.goods_receipts.create_index(
            [("active_key", ASCENDING)], name="uq_active_key", unique=True, background=True,
            partialFilterExpression={"active_key": {"$type": "string", "$gt": ""}})
    except Exception as exc:  # noqa: BLE001
        uq_summary["failed"].append("goods_receipts.active_key")
        logger.error("[indexes] UNIK goods_receipts.active_key GAGAL: %s", exc)
    try:
        # GRN Fase 0.7 — (supplier_id, supplier_sku) UNIK: lookup kode supplier tidak boleh ambigu.
        # Cek duplikat dulu: `python scripts/check_supplier_item_duplicates.py`.
        si_info = await db.supplier_items.index_information()
        if "supplier_id_1_supplier_sku_1" in si_info:
            await db.supplier_items.drop_index("supplier_id_1_supplier_sku_1")
        await db.supplier_items.create_index(
            [("supplier_id", ASCENDING), ("supplier_sku", ASCENDING)],
            name="uq_supplier_sku", unique=True, background=True,
            partialFilterExpression={"supplier_sku": {"$type": "string", "$gt": ""}})
    except Exception as exc:  # noqa: BLE001
        uq_summary["failed"].append("supplier_items.supplier_sku")
        logger.error("[indexes] UNIK supplier_items(supplier_id,supplier_sku) GAGAL — jalankan "
                     "scripts/check_supplier_item_duplicates.py: %s", exc)
    summary["unique"] = uq_summary
    logger.info(
        "[indexes] performance indexes → created=%d existed=%d failed=%d",
        created, existed, failed,
    )
    return summary



# ─── PK-14 (GL-09, IC-12, FX-19) — INDEKS UNIK KEUANGAN WAJIB ADA ────────────────────────────────────────────────
# Delapan keunikan yang dulu hanya dijaga "cek dulu, lalu sisip". Bila salah satunya tidak terpasang (mis. data lama
# kembar), `assert_required_indexes` menolak mulai (mode `enforce`, bawaan) dan menyebut indeks serta kueri pencari data
# kembarnya. Sakelar operasi `KN_REQUIRED_INDEX_MODE` = `enforce` | `warn` (lingkungan uji / darurat).
_NONEMPTY = {"$type": "string", "$gt": ""}


def _finder_dup(coll: str, match: str, group: str, push: str = "$number") -> str:
    return (f"db.{coll}.aggregate([{{$match:{match}}},{{$group:{{_id:{group},n:{{$sum:1}},nomor:{{$push:\"{push}\"}}}}}},"
            f"{{$match:{{n:{{$gt:1}}}}}}])")


REQUIRED_UNIQUE_INDEXES: List[Dict[str, Any]] = [
    {"collection": "journal_entries", "name": "uq_je_source_active", "label": "jurnal per sumber",
     "keys": [("source_type", 1), ("source_id", 1)],
     "partial": {"source_type": dict(_NONEMPTY), "source_id": dict(_NONEMPTY), "status": {"$in": ["posted", "draft"]}},
     "finder": _finder_dup("journal_entries",
                           '{source_type:{$type:"string",$gt:""},source_id:{$type:"string",$gt:""},'
                           'status:{$in:["posted","draft"]}}', '{t:"$source_type",s:"$source_id"}')},
] + [
    {"collection": c, "name": "uq_number", "label": f"nomor {lbl}", "keys": [("number", 1)],
     "partial": {"number": dict(_NONEMPTY)},
     "finder": _finder_dup(c, '{number:{$type:"string",$gt:""}}', '"$number"', "$id")}
    for c, lbl in (("interco_transactions", "transaksi antar-PT"), ("interco_settlements", "settlement antar-PT"),
                   ("interco_returns", "retur antar-PT"), ("interco_loans", "pinjaman antar-PT"))
] + [
    {"collection": "penalties", "name": "uq_penalty_line_period", "label": "nota denda per baris per periode",
     "keys": [("doc_id", 1), ("plan_id", 1), ("line_seq", 1), ("period_key", 1)],
     "partial": {"period_key": dict(_NONEMPTY)},
     "finder": _finder_dup("penalties", '{period_key:{$type:"string",$gt:""}}',
                           '{d:"$doc_id",p:"$plan_id",s:"$line_seq",k:"$period_key"}')},
    {"collection": "payment_plans", "name": "uq_plan_active_doc", "label": "satu rencana bayar aktif per dokumen",
     "keys": [("doc_type", 1), ("doc_id", 1)], "partial": {"status": "active"},
     "finder": _finder_dup("payment_plans", '{status:"active"}', '{t:"$doc_type",d:"$doc_id"}')},
    {"collection": "finance_cases", "name": "uq_case_open_source", "label": "satu kasus terbuka per sumber",
     "keys": [("case_type", 1), ("source.id", 1)],
     "partial": {"source.id": dict(_NONEMPTY), "status": {"$in": ["open", "in_progress"]}},
     "finder": _finder_dup("finance_cases", '{"source.id":{$type:"string",$gt:""},status:{$in:["open","in_progress"]}}',
                           '{t:"$case_type",s:"$source.id"}')},
]


class RequiredIndexError(RuntimeError):
    """Indeks unik wajib tidak terpasang — aplikasi tidak dijalankan (mode `enforce`)."""


def required_index_mode() -> str:
    return "warn" if (os.environ.get("KN_REQUIRED_INDEX_MODE") or "").strip().lower() == "warn" else "enforce"


def is_duplicate_on(exc: BaseException, *fields: str) -> bool:
    """`DuplicateKeyError` dari indeks yang memuat semua `fields` (dibaca dari `details["keyPattern"]`)."""
    from pymongo.errors import DuplicateKeyError
    if not isinstance(exc, DuplicateKeyError):
        return False
    kp = (getattr(exc, "details", None) or {}).get("keyPattern") or {}
    return all(f in kp for f in fields)


async def ensure_required_indexes() -> List[Dict[str, Any]]:
    """Buat tiap indeks wajib (idempoten). Mengembalikan butir yang GAGAL dibuat beserta teks galatnya."""
    failed: List[Dict[str, Any]] = []
    for it in REQUIRED_UNIQUE_INDEXES:
        try:
            await db[it["collection"]].create_index(
                list(it["keys"]), name=it["name"], unique=True, partialFilterExpression=it["partial"])
        except Exception as exc:  # noqa: BLE001 — dilaporkan lewat diff/assert
            failed.append({**it, "error": str(exc)[:300]})
    return failed


def _plain(v: Any) -> Any:
    if isinstance(v, dict) or hasattr(v, "items"):
        return {str(k): _plain(x) for k, x in dict(v).items()}
    if isinstance(v, (list, tuple)):
        return [_plain(x) for x in v]
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _keys(key: Any) -> List[Tuple[str, int]]:
    return [(str(k), int(d)) for k, d in (key or [])]


def diff_required(index_info_by_collection: Dict[str, Dict]) -> List[Dict[str, Any]]:
    """Fungsi murni: bandingkan `index_information()` per koleksi dengan daftar wajib.

    Tiap selisih: koleksi, nama, label, `problem` (`tidak ada` | `tidak unik` | `kunci berbeda` |
    `ekspresi parsial berbeda`), dan `finder` (kueri pencari data kembar)."""
    out: List[Dict[str, Any]] = []
    for it in REQUIRED_UNIQUE_INDEXES:
        info = (index_info_by_collection.get(it["collection"]) or {}).get(it["name"])
        if not info:
            problem = "tidak ada"
        elif not info.get("unique"):
            problem = "tidak unik"
        elif _keys(info.get("key")) != _keys(it["keys"]):
            problem = "kunci berbeda"
        elif json.dumps(_plain(info.get("partialFilterExpression") or {}), sort_keys=True) != \
                json.dumps(_plain(it["partial"]), sort_keys=True):
            problem = "ekspresi parsial berbeda"
        else:
            continue
        out.append({"collection": it["collection"], "name": it["name"], "label": it["label"],
                    "problem": problem, "finder": it["finder"]})
    return out


def required_index_message(diffs: List[Dict[str, Any]]) -> str:
    lines = ["INDEKS WAJIB BELUM TERPASANG — aplikasi tidak dijalankan."]
    for d in diffs:
        lines.append(f"- {d['collection']}.{d['name']} ({d['label']}): {d['problem']}")
        lines.append(f"  Cari data kembar: {d['finder']}")
    lines.append("Jangan menghapus atau menggabung data sendiri. Serahkan hasil kueri kepada pemilik data.")
    return "\n".join(lines)


async def required_index_diffs() -> List[Dict[str, Any]]:
    """`ensure` lalu `diff`; butir yang tidak ada karena gagal dibuat membawa teks galatnya."""
    failed = {(f["collection"], f["name"]): f["error"] for f in await ensure_required_indexes()}
    info: Dict[str, Dict] = {}
    for coll in sorted({it["collection"] for it in REQUIRED_UNIQUE_INDEXES}):
        try:
            info[coll] = await db[coll].index_information()
        except Exception:  # noqa: BLE001 — koleksi belum ada
            info[coll] = {}
    diffs = diff_required(info)
    for d in diffs:
        err = failed.get((d["collection"], d["name"]))
        if err and d["problem"] == "tidak ada":
            d["problem"] = f"gagal dibuat: {err}"
    return diffs


async def assert_required_indexes() -> None:
    """Dipanggil `run_bootstrap` DI LUAR try/except: mode `enforce` → `RequiredIndexError` (lifespan gagal, server tidak
    menerima permintaan); mode `warn` → galat di log, lanjut."""
    diffs = await required_index_diffs()
    if not diffs:
        return
    msg = required_index_message(diffs)
    print(msg, file=sys.stderr, flush=True)
    if required_index_mode() == "warn":
        logger.error(msg)
        return
    raise RequiredIndexError(msg)
