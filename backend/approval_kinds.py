"""approval_kinds.py — katalog JENIS DOKUMEN persetujuan (unit KP-T4).

Satu baris = satu keputusan yang diputus orang: label untuk manusia, kelompok layar, antrean di Pusat Persetujuan
(`services/approval_backlog_service.QUEUES`), izin setujui yang diperiksa pintunya, field nominal (kosong = tanpa
nominal), dan peta jenjang → status untuk rantai berstatus (uang muka).

Ini STRUKTUR, bukan nilai bisnis: siapa yang memutus dan mulai nominal berapa ada di koleksi `approval_policies`
(layar Pengaturan › Persetujuan › Aturan Persetujuan), dibaca `services/approval_policy_service.py`.

Aturan:
- Tiap kunci `QUEUES` punya ≥ 1 jenis (`queue_key`) — dijaga INV-APPR-01 (`scripts/guardrails/verify_approval_queues.py`).
  `queue_key` kosong = keputusan langsung tanpa dokumen menunggu (bukan antrean), wajib ber-`note`.
- `permissions`: izin setujui; lebih dari satu = salah satu cukup. `reject_permissions`: izin pintu tolak bila berbeda.
- Sub-jenis (`induk.anak`) dipakai bila satu antrean memuat beberapa keputusan dengan aturan berbeda.
"""
from typing import Any, Dict, List, Optional, Tuple

#: Kelompok layar (urutan tampil).
GROUPS: Tuple[str, ...] = ("Penjualan", "Pembelian", "Keuangan", "Gudang", "R&D", "SDM")


def _k(label: str, group: str, queue_key: str, permissions: Tuple[str, ...], amount_field: str = "",
       reject_permissions: Tuple[str, ...] = (), level_status: Optional[Dict[int, str]] = None,
       level_labels: Optional[Dict[int, str]] = None, note: str = "") -> Dict[str, Any]:
    return {"label": label, "group": group, "queue_key": queue_key, "permissions": tuple(permissions),
            "reject_permissions": tuple(reject_permissions or ()), "amount_field": amount_field,
            "level_status": dict(level_status or {}), "level_labels": dict(level_labels or {}), "note": note}


APPROVAL_KINDS: Dict[str, Dict[str, Any]] = {
    # ── Penjualan ──────────────────────────────────────────────────────────────────────────────────────────────────
    "sales_order.nilai": _k("Pesanan Penjualan — nilai pesanan", "Penjualan", "sales_order", ("order.approve",),
                            amount_field="grand_total"),
    "sales_order.validasi": _k("Pesanan Penjualan — validasi admin (tanpa ambang nilai)", "Penjualan",
                               "sales_order", ("order.approve",),
                               note="Entri penanda validasi saat pesanan diajukan walau nilainya tidak butuh persetujuan."),
    "sales_order.kredit": _k("Pesanan Penjualan — lewat batas kredit", "Penjualan", "sales_order",
                             ("order.approve",), amount_field="grand_total"),
    "sales_order.harga_khusus": _k("Pesanan Penjualan — harga khusus", "Penjualan", "sales_order",
                                   ("order.approve",)),
    "sales_order.bayar_sampel": _k("Pesanan Sample — pembayaran (di Pusat Persetujuan)", "Penjualan", "sales_order",
                                   ("order.approve",), amount_field="grand_total",
                                   note="Pintu Setujui Bayar di layar Pesanan Sample cukup izin setujui bayar sample."),
    "sales_order.makloon": _k("Pesanan Penjualan — memakai stok makloon", "Penjualan", "sales_order",
                              ("order.approve",), amount_field="grand_total"),
    "price": _k("Permintaan harga khusus", "Penjualan", "price", ("price_approval.approve",)),
    "sales_return": _k("Retur penjualan", "Penjualan", "sales_return", ("sales_return.approve",)),
    "sales_return_exception": _k("Pengecualian retur", "Penjualan", "sales_return_exception",
                                 ("sales_return.approve",)),
    "amendment": _k("Koreksi & amandemen pesanan", "Penjualan", "amendment", ("finance_amendment.approve",),
                    amount_field="impact.delta"),
    "special_order": _k("Pesanan khusus (PO Custom)", "Penjualan", "special_order", ("order.approve",),
                        amount_field="total_amount"),
    "internal_request": _k("Permintaan internal antar-PT", "Penjualan", "internal_request",
                           ("internal_request.convert",), reject_permissions=("internal_request.reject",)),
    "so_verify": _k("Verifikasi administratif pesanan", "Penjualan", "so_verify", ("order.verify",)),
    "credit_override": _k("Izin lewat batas kredit pelanggan", "Penjualan", "credit_override",
                          ("credit_override.approve",), amount_field="amount"),
    # ── Pembelian ──────────────────────────────────────────────────────────────────────────────────────────────────
    "purchase_order": _k("Pesanan Pembelian", "Pembelian", "purchase_order", ("purchase_order.approve",),
                         amount_field="total_amount", reject_permissions=("purchase_order.reject",)),
    "purchase_order.deviasi_harga": _k("Pesanan Pembelian — penyimpangan harga / lewat kontrak", "Pembelian",
                                       "purchase_order", ("purchase_order.approve",), amount_field="total_amount",
                                       reject_permissions=("purchase_order.reject",)),
    "purchase_requisition": _k("Permintaan Pembelian (PR)", "Pembelian", "purchase_requisition",
                               ("purchase_requisition.approve",), amount_field="total_est_amount",
                               reject_permissions=("purchase_requisition.reject",)),
    "purchase_return": _k("Retur pembelian", "Pembelian", "purchase_return", ("purchase_return.approve",)),
    "po_variance": _k("Selisih penerimaan PO", "Pembelian", "po_variance", ("purchase_order.update",)),
    "makloon_claim": _k("Klaim selisih makloon", "Pembelian", "makloon_claim", ("makloon_order.claim_approve",),
                        amount_field="steps.claim.amount"),
    "makloon_loss": _k("Susut bahan di mitra makloon", "Pembelian", "makloon_loss", ("makloon_order.approve_loss",)),
    # ── Keuangan ───────────────────────────────────────────────────────────────────────────────────────────────────
    "vendor_bill": _k("Tagihan pemasok", "Keuangan", "vendor_bill", ("vendor_bill.approve",),
                      amount_field="grand_total", reject_permissions=("vendor_bill.reject",)),
    "vendor_bill.kampanye": _k("Tagihan pemasok — biaya kampanye", "Keuangan", "vendor_bill",
                               ("vendor_bill.approve",), amount_field="grand_total",
                               reject_permissions=("vendor_bill.reject",)),
    "landed_cost": _k("Voucher biaya masuk", "Keuangan", "landed_cost", ("landed_cost.approve",),
                      amount_field="total_cost", reject_permissions=("landed_cost.reject",)),
    "contra_bon_verify": _k("Verifikasi kontrabon", "Keuangan", "contra_bon_verify", ("contra_bon.verify",)),
    "contra_bon_approve": _k("Persetujuan kontrabon", "Keuangan", "contra_bon_approve", ("contra_bon.approve",),
                             amount_field="totals.net_payable"),
    "contra_bon_dispute": _k("Sengketa kontrabon", "Keuangan", "contra_bon_dispute", ("contra_bon.update",)),
    "interco": _k("Transaksi antar-PT", "Keuangan", "interco", ("interco.approve",), amount_field="grand_total"),
    "interco_return": _k("Retur antar-PT", "Keuangan", "interco_return", ("interco.approve",)),
    # Temuan cek ulang KP-T4: pencairan pinjaman antar-PT memakai ambang & peran `antar_entitas.*` yang sama dengan
    # peta peringkat pribadi (bukan antrean — pencairan langsung oleh yang berwenang, tanpa dokumen menunggu).
    "interco_loan": _k("Pencairan pinjaman antar-PT", "Keuangan", "", ("interco.approve",), amount_field="principal",
                       note="Bukan antrean: pencairan dijalankan langsung oleh peran yang tercantum."),
    "cash_advance": _k("Uang muka (panjar)", "Keuangan", "cash_advance", ("cash_advance.approve",),
                       amount_field="total_amount", reject_permissions=("cash_advance.reject",),
                       level_status={1: "pending_atasan", 2: "pending_pimpinan", 3: "pending_finance"},
                       level_labels={1: "Atasan Langsung", 2: "Pimpinan", 3: "Bagian Keuangan"}),
    "cash_advance_settlement": _k("Pertanggungjawaban uang muka", "Keuangan", "cash_advance_settlement",
                                  ("cash_settlement.approve",)),
    "payment_variance": _k("Selisih pembayaran", "Keuangan", "payment_variance", ("payment_variance.decide",),
                           amount_field="amount"),
    "payment_variance.hapus_sisa": _k("Selisih pembayaran — hapus sisa / refund", "Keuangan", "payment_variance",
                                      ("payment_variance.decide",), amount_field="amount",
                                      note="Hanya bila pengaturan 'hapus sisa wajib disetujui' aktif."),
    "period_unlock": _k("Buka periode", "Keuangan", "period_unlock", ("period.unlock",)),
    # KF-T6 (GL-06) — antrean `journal_proposal` lahir sesudah KP-T4 dirancang (perbaikan susulan KF-T6): pintu
    # `/gl/journal-proposals/{id}/approve|reject` = izin `accounting.create`; pengusul ≠ penyetuju dijaga KF-T6.
    "journal_proposal": _k("Jurnal manual — usulan menunggu orang kedua", "Keuangan", "journal_proposal",
                           ("accounting.create",), amount_field="total_debit",
                           note="Usulan hanya ada bila kontrol dua orang jurnal manual aktif untuk PT itu."),
    "od_cancel_credit_note": _k("Nota kredit batal item", "Keuangan", "od_cancel_credit_note",
                                ("finance_amendment.review_credit_note",)),
    # ── Gudang ─────────────────────────────────────────────────────────────────────────────────────────────────────
    "cycle_count": _k("Stock opname", "Gudang", "cycle_count", ("inventory.approve_count",)),
    "transfer": _k("Transfer gudang", "Gudang", "transfer", ("transfer.approve",)),
    "inspection_hold": _k("Lepas tahanan inspeksi", "Gudang", "inspection_hold",
                          ("inspection.decide", "md_quality.decide")),
    # ── R&D ────────────────────────────────────────────────────────────────────────────────────────────────────────
    "rnd_spec": _k("ACC spesifikasi desain (SKU lahir)", "R&D", "rnd_spec", ("rnd.assess",)),
    "rnd_spec.rilis": _k("Rilis produk ke produksi", "R&D", "rnd_spec", ("rnd.decide",),
                         note="Juga dipakai pemenuhan pesanan khusus untuk merilis SKU baru."),
    "rnd_sample": _k("ACC sample (pemenang)", "R&D", "rnd_sample", ("rnd.decide",)),
    "design_request": _k("Permintaan desain", "R&D", "design_request", ("design_request.decide",)),
    "design_gallery": _k("Pengesahan desain", "R&D", "design_gallery", ("rnd.assess",)),
    "design_claim": _k("Klaim kepemilikan desain", "R&D", "design_claim", ("design_ownership.decide",)),
    # ── SDM ────────────────────────────────────────────────────────────────────────────────────────────────────────
    "hr_leave": _k("Pengajuan cuti", "SDM", "hr_leave", ("hr.manage_attendance",)),
    "hr_overtime": _k("Pengajuan lembur", "SDM", "hr_overtime", ("hr.manage_attendance",)),
    "hr_payroll": _k("Pengesahan penggajian", "SDM", "hr_payroll", ("hr.manage_payroll",)),
}


def kind(doc_kind: str) -> Dict[str, Any]:
    """Jenis dokumen; tidak dikenal → `KeyError` (pemanggil yang salah ketik harus gagal keras)."""
    return APPROVAL_KINDS[doc_kind]


def has_amount(doc_kind: str) -> bool:
    return bool(APPROVAL_KINDS[doc_kind]["amount_field"])


def kinds_for_queue(queue_key: str) -> List[str]:
    return [k for k, v in APPROVAL_KINDS.items() if v["queue_key"] == queue_key]


def perm_pairs(doc_kind: str, action: str = "approve") -> List[Tuple[str, str]]:
    """Pasangan (sumber daya, aksi) izin pintu: `approve` = izin setujui; `reject` = izin tolak bila berbeda."""
    k = APPROVAL_KINDS[doc_kind]
    perms = k["reject_permissions"] if action == "reject" and k["reject_permissions"] else k["permissions"]
    return [tuple(p.split(".", 1)) for p in perms]   # type: ignore[misc]
