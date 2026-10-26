/**
 * Tampilan papan "menunggu keputusan" per antrean (ikon · warna · teks kosong).
 *
 * Yang BUKAN di sini: judul, tujuan klik, jumlah, umur tunggu — semuanya datang dari
 * backend (`approval_backlog_service`) supaya layar tak pernah punya pendapat sendiri.
 * Daftar antrean mana yang diberi papan juga milik backend (`HOME_BOARD_KEYS`);
 * berkas ini hanya menjawab "papan ini digambar seperti apa".
 */
import { Scissors, ReceiptText, PackageOpen, Clock, FileCheck2, Tags,
  ArrowLeftRight, ClipboardCheck, ShieldAlert } from "lucide-react";

export const BOARD_LOOK = {
  special_order: {
    // Fase 3 · P1 — `focusType`: jenis dokumen untuk `openDocument` saat papan dalam mode tautan (D-07/D-28).
    focusType: "special_order",
    // Fase 3 · P3 (D-07) — papan beranda = TAUTAN ke layar keputusan satu-satunya (Pesanan Khusus); aksen biru baku.
    icon: Scissors, accent: "#0058CC",
    title: "Papan PO Custom — menunggu keputusan",
    goto: "Buka Pesanan Khusus →",
    empty: "Tidak ada PO custom yang menunggu keputusan",
  },
  contra_bon_dispute: {
    icon: ReceiptText, accent: "#C0392B",
    title: "Kontrabon bersengketa — menunggu keputusan",
    goto: "Buka Kontrabon →",
    empty: "Tidak ada kontrabon bersengketa",
  },
  interco_return: {
    icon: PackageOpen, accent: "#0058CC",
    title: "Retur antar-PT — menunggu persetujuan",
    goto: "Buka Antar Entitas →",
    empty: "Tidak ada retur antar-PT yang menunggu persetujuan",
  },
  // ── Papan SALES (2026-06) ────────────────────────────────────────────────
  sales_order: {
    icon: FileCheck2, accent: "#1B7F4B",
    title: "Pesanan menunggu ACC — pelanggan sudah dijanjikan",
    goto: "Buka Pusat Persetujuan →",
    empty: "Tidak ada pesanan yang tertahan di persetujuan",
  },
  price: {
    icon: Tags, accent: "#B26A00",
    title: "Permintaan harga khusus — menunggu keputusan",
    goto: "Buka Persetujuan Harga →",
    empty: "Tidak ada permintaan harga khusus yang menggantung",
  },
  // ── Papan GUDANG (2026-06) ───────────────────────────────────────────────
  transfer: {
    icon: ArrowLeftRight, accent: "#0058CC",
    title: "Transfer gudang menunggu ACC — barang belum boleh jalan",
    goto: "Buka tab Transfer →",
    empty: "Tidak ada tugas transfer yang menunggu persetujuan",
  },
  cycle_count: {
    icon: ClipboardCheck, accent: "#6C3FD1",
    title: "Stock opname menunggu ACC",
    goto: "Buka tab Stock Opname →",
    empty: "Tidak ada hasil opname yang menunggu persetujuan",
  },
  inspection_hold: {
    focusType: "inspection",
    icon: ShieldAlert, accent: "#C0392B",
    title: "Barang ditahan QC — hanya manajer boleh melepas",
    goto: "Buka Inspeksi →",
    empty: "Tidak ada barang yang ditahan QC",
  },
  // ── Papan KEUANGAN (2026-06) — dokumen yang MENAHAN UANG ─────────────────
  contra_bon_approve: {
    icon: ReceiptText, accent: "#0058CC",
    title: "Kontrabon menunggu persetujuan — pemasok belum bisa dibayar",
    goto: "Buka Kontrabon →",
    empty: "Tidak ada kontrabon yang menunggu persetujuan",
  },
  contra_bon_verify: {
    icon: FileCheck2, accent: "#B26A00",
    title: "Kontrabon menunggu verifikasi berkas",
    goto: "Buka Kontrabon →",
    empty: "Tidak ada kontrabon yang menunggu verifikasi",
  },
  vendor_bill: {
    icon: ReceiptText, accent: "#6C3FD1",
    title: "Tagihan supplier menunggu ACC",
    goto: "Buka Tagihan Supplier →",
    empty: "Tidak ada tagihan supplier yang menunggu ACC",
  },
};

/**
 * Fase 3 · P1 — tautan dokumen untuk SATU baris papan (mode tautan): `openDocument(boardRowLink(board, row))`
 * membuka layar utama papan (`board.view` dari server) dengan dokumen baris itu terfokus. Papan tanpa
 * `focusType` → hanya membuka layarnya.
 */
export function boardRowLink(board, row) {
  const look = BOARD_LOOK[board?.key] || {};
  const link = { view: board?.view };
  if (look.focusType && row?.id) Object.assign(link, { focus_type: look.focusType, focus_id: row.id, number: row.number || "" });
  return link;
}

/**
 * Fase 3 · P3 (D-07/D-28, keputusan pemilik 26 Okt) — papan BERANDA yang hanya TAUTAN: PO Custom & Barang ditahan
 * QC. Keputusannya hanya di layar utama (Pesanan Khusus · SPK Inspeksi) dengan satu dialog; baris papan membuka
 * dokumennya (`boardRowLink`). Papan lain (kontrabon, retur antar-PT, tagihan, opname, transfer) tetap bisa
 * ditindak. Dipakai Control Tower, Dasbor Manajer, Beranda Sales — dan beranda HP (P7) memakai daftar yang sama.
 */
export const HOME_LINK_BOARDS = ["special_order", "inspection_hold"];
export const isLinkBoard = (key) => HOME_LINK_BOARDS.includes(key);

/**
 * Preset layar tujuan tombol "Buka …" papan tautan: Pesanan Khusus langsung di tab Menunggu Persetujuan; SPK
 * Inspeksi langsung bersaring "hanya ditahan" (preset `{ hold: true }` dibaca layar Inspeksi, P5 D-28).
 */
export const LINK_BOARD_PRESET = { special_order: { status: "pending_approval" }, inspection_hold: { hold: true } };

export const boardLook = (key) => BOARD_LOOK[key] || {
  icon: Clock, accent: "#6B6B73", goto: "Buka layarnya →",
  empty: "Tidak ada dokumen yang menunggu keputusan",
};

/**
 * Papan mana yang digambar — SATU pemilih untuk semua beranda.
 *
 * REGRESI B5 YANG DITUTUP (temuan agen uji, 2026-06): dulu tiap beranda menyaring
 * sendiri `waiting_boards`, dan penyaringnya menghasilkan daftar KOSONG ketika
 * pemuatan gagal (`data === null`). Akibatnya papan hilang total — jadi keadaan
 * "tidak bisa dibaca" yang justru dibuat untuk kegagalan TIDAK PERNAH tampil, dan
 * layar kembali terasa seperti kabar baik. Karena itu:
 *   · gagal dibaca  → tetap kembalikan KERANGKA papan utama (papannya harus ADA
 *     supaya bisa berkata "tidak bisa dibaca" + tombol Coba lagi);
 *   · terbaca       → papan utama selalu tampil, papan lain hanya bila berisi
 *     (tiga papan nol berturut-turut membuat yang penting ikut terabaikan).
 *
 * `primaryKey` = papan yang tetap tampil walau kosong. Beranda pemilik/manajer/sales
 * memakai `special_order` (kain custom tak bisa dialihkan ke pelanggan lain); layar
 * Operasi memakai `transfer` (barang berhenti bergerak).
 */
export function selectWaitingBoards(data, unreadable = false,
                                    primaryKey = "special_order") {
  const all = data?.waiting_boards
    || (data?.special_orders_waiting
      ? [{ key: "special_order", ...data.special_orders_waiting }] : []);
  if (unreadable) {
    const utama = all.filter((b) => b.key === primaryKey);
    return utama.length ? utama : [{ key: primaryKey }];
  }
  return all.filter((b) => b.key === primaryKey || (b.count ?? 0) > 0);
}
