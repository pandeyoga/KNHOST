/**
 * approvalInboxData — pemuat data Pusat Persetujuan (diekstrak dari `ApprovalInbox.jsx`, fase 3 · P3, < 500 baris).
 *
 * Satu panggilan `loadInbox()` → `{ items, amendments, backlog, unavailable }`:
 *  · `items`       — baris daftar inbox (SO nilai/kredit/harga, PO, harga khusus mandiri, retur, opname, kredit
 *                    pelanggan), terurut dari yang paling lama menunggu.
 *  · `amendments`  — amandemen menunggu keputusan. D-06: TIDAK masuk daftar (keputusannya hanya di Pusat Amandemen);
 *                    dipakai untuk hitungan kartu tautan tab "Amandemen".
 *  · `backlog`     — ringkasan SELURUH antrean (`GET /approvals/backlog`, sumber sama dengan KPI beranda).
 *  · `unavailable` — kategori yang GAGAL dibaca (izin/jaringan) — disebut di layar, bukan diam-diam kosong.
 */
import { Tag, ShoppingCart, RotateCcw, ClipboardCheck, ShieldCheck, CreditCard, FileEdit } from "lucide-react";
import axios, { API } from "../../services/apiClient";
import { formatCurrency } from "../../utils/formatters";
import { discountInfo } from "../sales/priceApprovals/priceApprovalText";
import { SO_DEAD_STATUSES } from "./inboxTabs";

// kind → tampilan (label, ikon, warna) + tab grup
export const KIND_META = {
  so_nilai:         { label: "SO · Nilai Pesanan",  icon: ShieldCheck,    fg: "#4F46E5", bg: "#EEF0FF", group: "sales_order" },
  so_kredit:        { label: "SO · Kredit",       icon: CreditCard,     fg: "#DC2626", bg: "#FEE2E2", group: "sales_order" },
  so_special_price: { label: "SO · Harga Khusus", icon: Tag,            fg: "#B45309", bg: "#FEF3C7", group: "sales_order" },
  po:              { label: "PO Pembelian",  icon: ShoppingCart,   fg: "#0058CC", bg: "#EFF4FF", group: "po" },
  price:           { label: "Harga Khusus",  icon: Tag,            fg: "#6D28D9", bg: "#F3EEFF", group: "price" },
  sales_return:    { label: "Retur Penjualan",    icon: RotateCcw,      fg: "#B45309", bg: "#FEF3C7", group: "returns" },
  purchase_return: { label: "Retur Pembelian",    icon: RotateCcw,      fg: "#0E7490", bg: "#E0F2FE", group: "returns" },
  cycle:           { label: "Stok Opname",   icon: ClipboardCheck, fg: "#15803D", bg: "#DCFCE7", group: "cycle" },
  // IA 2026-10 (B9) — override kredit pelanggan (dulu hanya di CRM › Persetujuan Kredit).
  credit:          { label: "Override Kredit", icon: CreditCard, fg: "#0058CC", bg: "#E8F1FF", group: "credit" },
  // FASE G-1 — koreksi angka dokumen keuangan; D-06: hanya untuk tampilan sisa (tidak dirender di daftar).
  amendment:       { label: "Amandemen Dokumen", icon: FileEdit,   fg: "#7A2CA0", bg: "#F3E9FA", group: "amendment" },
};

const SO_KIND_BY_TYPE = { nilai: "so_nilai", kredit: "so_kredit", special_price: "so_special_price" };
const arr = (d) => (Array.isArray(d) ? d : (Array.isArray(d?.items) ? d.items : []));
const byAt = (a, b) => new Date(a.at || 0) - new Date(b.at || 0);

export async function loadInbox() {
  const gagal = [];
  /** Ambil satu sumber; catat namanya bila tak boleh/gagal (bukan diam-diam kosong). */
  const grab = (label, promise) => promise.catch((e) => {
    gagal.push(label);
    return { data: [], _failed: e };
  });
  const [queueRes, poRes, prRes, srRes, purRes, ccRes, amdRes, blRes, coRes] = await Promise.all([
    grab("Pesanan Penjualan", axios.get(`${API}/approvals/queue`)),
    grab("Pembelian (PO)", axios.get(`${API}/purchase-orders`)),
    grab("Harga Khusus", axios.get(`${API}/price-approvals`, { params: { status: "pending" } })),
    grab("Retur Penjualan", axios.get(`${API}/sales-returns`, { params: { status: "pending_approval" } })),
    grab("Retur Pembelian", axios.get(`${API}/purchase-returns`)),
    grab("Stock Opname", axios.get(`${API}/cycle-count/sessions`)),
    grab("Amandemen", axios.get(`${API}/amendments`, { params: { status: "pending_approval" } })),
    // FASE F-6 — `?oldest=` sekalian membawa DOKUMEN paling lama menunggu dari SEMUA antrean (termasuk antrean
    // yang layar ini tidak muat: transfer gudang, kontrabon, permintaan internal, cuti, lembur, …).
    grab("Ringkasan Antrean", axios.get(`${API}/approvals/backlog`, { params: { oldest: 50 } })),
    grab("Kredit Pelanggan", axios.get(`${API}/credit-overrides`, { params: { status: "pending" } })),
  ]);

  // FASE 5 — Sales Order approvals (SSOT pending_approvals): nilai / kredit / harga khusus.
  // Fase 4 · R5 — entri milik SO mati (batal/kedaluwarsa) tidak ikut: sama dengan baris antrean `sales_order` server.
  const liveSo = arr(queueRes.data).filter((q) => !SO_DEAD_STATUSES.includes(q.order_status));
  const soApprovals = liveSo.map((q) => ({
    kind: SO_KIND_BY_TYPE[q.type] || "so_nilai",
    id: q.id, orderId: q.order_id,
    title: q.order_number || "Sales Order",
    subtitle: q.customer_name || "Customer",
    meta: q.type === "special_price"
      ? `${q.product_name || "Item"} · ${formatCurrency(q.normal_price)} → ${formatCurrency(q.requested_price)}`
      : (q.reason || q.type_label || ""),
    amount: q.type === "special_price" ? q.requested_price : (q.amount ?? q.grand_total),
    requester: q.requested_by, role: q.required_role || "manager",
    at: q.requested_at, isSO: true,
  }));
  // ID SO yang punya approval khusus harga lewat SSOT (untuk dedup dgn price_approvals lama).
  const soPriceRefIds = new Set(liveSo.filter((q) => q.type === "special_price").map((q) => q.ref_id));

  const pos = arr(poRes.data).filter((p) => p.status === "waiting_approval").map((p) => ({
    kind: "po", id: p.id, title: p.po_number, subtitle: p.supplier_name,
    meta: `${p.warehouse_name || ""} · ${p.items?.length || 0} item`,
    amount: p.total_amount, requester: p.created_by, role: p.required_approval_role,
    at: p.created_at, target: "purchase-approval",
  }));

  // Harga khusus STANDALONE saja (yang TIDAK tertaut SO) — yang tertaut SO tampil di grup Sales Order.
  const prices = arr(prRes.data).filter((p) => !p.so_id && !soPriceRefIds.has(p.id)).map((p) => ({
    kind: "price", id: p.id, title: p.product_name || p.sku, subtitle: p.customer_name,
    // UAT 24 Okt (audit UI tahap 2, dari G2-02) — harga di ATAS normal dulu "(--3064%)"; kini "+3.064% di atas harga normal".
    meta: `${formatCurrency(p.normal_price)} → ${formatCurrency(p.requested_price)}${discountInfo(p.discount_percent) ? ` (${discountInfo(p.discount_percent).long})` : ""}`,
    amount: p.requested_price, requester: p.requested_by_name || p.requested_by, role: "manager",
    at: p.created_at, target: "price-approvals",
  }));

  const salesReturns = arr(srRes.data).filter((r) => r.status === "pending_approval").map((r) => ({
    kind: "sales_return", id: r.id, title: r.number, subtitle: r.customer_name || "Customer",
    meta: `Order ${r.order_number || "—"} · ${r.items?.length || 0} item`,
    amount: null, requester: r.created_by, role: "manager",
    at: r.created_at, target: "returns",
  }));

  const purchaseReturns = arr(purRes.data).filter((r) => r.status === "pending_approval").map((r) => ({
    kind: "purchase_return", id: r.id, title: r.number, subtitle: r.supplier_name || "Supplier",
    meta: `${r.po_number ? `dari ${r.po_number} · ` : ""}${r.items?.length || 0} item`,
    amount: r.total_amount, requester: r.created_by, role: "manager",
    at: r.created_at, target: "purchase-returns",
  }));

  const cycleCounts = arr(ccRes.data).filter((s) => s.status === "submitted").map((s) => ({
    kind: "cycle", id: s.id, title: s.name || "Cycle Count", subtitle: s.warehouse_name || "Gudang",
    meta: `${s.items?.length || 0} item dihitung`,
    amount: null, requester: s.submitted_by || s.created_by, role: "manager",
    at: s.submitted_at || s.created_at, target: "wms-cycle", targetView: "operations", targetTab: "cycle",
  }));

  // Fase 4 · R5 — hanya override MANDIRI (tanpa SO). Yang tertaut SO = entri kredit SO itu (grup Pesanan Penjualan,
  // diputus lewat entri SO supaya status SO ikut) — dulu tampil DUA kali; sama dengan baris `credit_override` server.
  const credits = arr(coRes.data).filter((c) => !c.order_id).map((c) => ({
    kind: "credit", id: c.id, title: c.customer_name || "Pelanggan",
    subtitle: c.order_number || c.reason || "Override batas kredit",
    meta: c.reason || "", amount: c.amount ?? c.requested_amount ?? null,
    requester: c.requested_by, role: "manager", at: c.created_at,
    target: "customers-crm",
  }));

  const items = [...soApprovals, ...pos, ...prices, ...salesReturns, ...purchaseReturns, ...cycleCounts, ...credits]
    .sort(byAt);
  return {
    items,
    amendments: arr(amdRes.data),
    backlog: blRes?.data && !Array.isArray(blRes.data) ? blRes.data : null,
    unavailable: gagal,
  };
}
