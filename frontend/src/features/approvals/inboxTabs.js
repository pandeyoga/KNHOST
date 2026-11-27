/**
 * inboxTabs — tab Pusat Persetujuan & pemetaan antrean server → tab (fase 3 · P3, D-06).
 *
 * Satu sumber untuk: tab di `ApprovalInbox`, chip per jenis di Control Tower / Dasbor Manajer (membuka inbox di tab
 * jenisnya lewat preset `{ tab }`), dan alias `my-approvals` → `{ tab: "matrix" }` (P8, `config/viewAliases.js`).
 */
import { roleCanSee } from "../../config/roles";

/** Tab daftar inbox (urutan tampil). `matrix` = panel Matriks divisi (dulu layar "Persetujuan Saya"). */
export const INBOX_TABS = [
  { key: "all", label: "Semua" },
  { key: "sales_order", label: "Pesanan Penjualan" },
  { key: "amendment", label: "Amandemen" },
  { key: "po", label: "Pembelian (PO)" },
  { key: "price", label: "Harga Khusus" },
  { key: "returns", label: "Retur" },
  { key: "cycle", label: "Stok Opname" },
  { key: "credit", label: "Kredit Pelanggan" },
  { key: "so_cancel", label: "Pembatalan Pesanan" },
  { key: "matrix", label: "Matriks divisi" },
];

/** Kunci antrean server (`approval_backlog_service.QUEUES`) → tab inbox yang MEMUAT daftarnya. */
export const BACKLOG_INBOX_TAB = {
  sales_order: "sales_order",
  purchase_order: "po",
  price: "price",
  sales_return: "returns",
  purchase_return: "returns",
  cycle_count: "cycle",
  amendment: "amendment",
  // Fase 4 · R5 — override kredit MANDIRI kini baris antrean server sendiri (dulu tak terhitung KPI).
  credit_override: "credit",
  // BTP-7 — permintaan batal / tutup sisa pesanan menunggu persetujuan (keputusan di rincian pesanan).
  so_cancel: "so_cancel",
};

/**
 * Antrean yang DAFTARNYA dirender inbox. Amandemen sengaja TIDAK (D-06: keputusan amandemen hanya di Pusat
 * Amandemen; tab Amandemen = kartu tautan berhitungan) — jadi ia dihitung "ditangani di layar lain".
 */
export const LISTED_IN_INBOX = ["sales_order", "purchase_order", "price", "sales_return", "purchase_return", "cycle_count",
  "credit_override", "so_cancel"];

/**
 * Kunci antrean server → jenis pratinjau dokumen (`documents/preview/docPreviewRegistry.js`): nomor dokumen di daftar
 * "Menunggu di layar lain" menjadi `DocLink` (pola UI §1 butir 8) — klik membuka pop-up pratinjau, "Buka layarnya" tetap
 * pindah ke layar keputusannya. Kas & Bank 2 (Tugas 4): pengajuan kas keluar; Kas & Bank 1: Pindah Dana.
 */
export const QUEUE_DOC_TYPE = { cash_out_request: "cash_out_request", fund_transfer: "fund_transfer" };

/** Fase 4 · R5 — SO mati: entri `pending_approvals` basi tidak menunggu siapa pun (sama dengan server SO_DEAD_STATUSES). */
export const SO_DEAD_STATUSES = ["cancelled", "expired", "rejected", "void", "done"];

/** Tab Matriks divisi hanya untuk peran yang dulu membuka `my-approvals` (manager/admin + overlay/hidden_views). */
export const canSeeMatrix = (role) => roleCanSee(["manager", "admin"], role, "my-approvals");

/**
 * Tujuan klik chip antrean di beranda: inbox di tab jenisnya bila daftarnya ada di inbox & peran boleh membuka
 * inbox; selain itu layar kerja antrean itu sendiri (`view` dari server) dengan preset saringannya bila server
 * mengirimnya (`approval_backlog_service.QUEUE_PRESETS`, mis. Pindah Dana → status "Menunggu persetujuan").
 *   → { view, preset } | { view }
 */
export function queueLink(q, canOpen = () => false) {
  const tab = BACKLOG_INBOX_TAB[q?.key];
  if (tab && tab !== "amendment" && canOpen("approval-inbox")) return { view: "approval-inbox", preset: { tab } };
  return q?.preset ? { view: q?.view, preset: q.preset } : { view: q?.view };
}
