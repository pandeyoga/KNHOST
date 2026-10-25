// F4 — SSOT Status SO 2-level (MIRROR backend services/so_status.py) untuk FE.
// STAGE (induk linear) + SUB-STATUS (anak kontekstual). Dipakai sebagai FALLBACK
// bila backend belum mengirim `stage`/`sub_status` (order legacy). Kode menang:
// bila BE mengirim field, FE memakainya apa adanya.

export const STAGE_FLOW = ["Reserved", "Approved", "Confirmed", "Picked", "Shipped", "Delivered"];
export const STAGE_CANCELLED = "Cancelled";

export const SUBSTATUS_LABELS = {
  menunggu_validasi: "Menunggu validasi admin",
  menunggu_approval_nilai: "Menunggu approval nilai",
  menunggu_approval_kredit: "Menunggu approval kredit",
  menunggu_approval_harga: "Menunggu approval harga khusus",
  menunggu_approval_makloon: "Menunggu approval stok cadangan makloon",
  menunggu_persetujuan_bayar_sample: "Menunggu persetujuan bayar sample (Finance/Admin Sample)",
  siap_disahkan: "Siap disahkan",
  menunggu_stok: "Menunggu stok (backorder)",
  siap_confirm: "Stok siap — bisa dikonfirmasi",
  siap_pick: "Siap diambil (gudang)",
  sedang_pick: "Sedang dipick",
  sebagian_dipick: "Sebagian dipick",
  siap_kirim: "Siap kirim",
  sebagian_dikirim: "Sebagian dikirim",
  dibatalkan: "Dibatalkan",
  kedaluwarsa: "Kedaluwarsa",
};

export function subStatusLabel(key) {
  return SUBSTATUS_LABELS[key] || String(key || "").replaceAll("_", " ");
}

// Meta stage: label tampil + class warna (mengikuti palet status-pill existing).
export const STAGE_META = {
  Reserved: { label: "Dipesan", cls: "stage-reserved" },
  Approved: { label: "Disetujui", cls: "stage-approved" },
  Confirmed: { label: "Terkonfirmasi", cls: "stage-confirmed" },
  Picked: { label: "Sudah Diambil", cls: "stage-picked" },
  // Cek UI UAT v3 (S2) — dulu tampil "Shipped"/"Delivered" (Inggris) di kolom TAHAP & lencana detail.
  Shipped: { label: "Dikirim", cls: "stage-shipped" },
  Delivered: { label: "Selesai", cls: "stage-delivered" },
  Cancelled: { label: "Dibatalkan", cls: "stage-cancelled" },
};

// Label panjang untuk timeline (lebih deskriptif).
export const STAGE_LABEL_LONG = {
  Reserved: "Dipesan",
  Approved: "Disetujui",
  Confirmed: "Terkonfirmasi (stok dikunci)",
  Picked: "Sudah diambil (siap kirim)",
  Shipped: "Dikirim",
  Delivered: "Selesai (diterima)",
};

export function stageMeta(stage) {
  return STAGE_META[stage] || { label: stage || "—", cls: "stage-reserved" };
}

export function stageIndex(stage) {
  return STAGE_FLOW.indexOf(stage); // -1 bila Cancelled / unknown
}

function approvalSubs(order) {
  const subs = [];
  const map = {
    nilai: "menunggu_approval_nilai",
    kredit: "menunggu_approval_kredit",
    special_price: "menunggu_approval_harga",
    makloon: "menunggu_approval_makloon",
    pembayaran_sampel: "menunggu_persetujuan_bayar_sample",
  };
  for (const pa of order.pending_approvals || []) {
    if (pa.status === "pending") subs.push(map[pa.type] || "menunggu_approval_nilai");
  }
  if (!subs.length && order.required_approval_role) subs.push("menunggu_approval_nilai");
  return subs.length ? subs : ["menunggu_validasi"];
}

// Mirror backend derive_stage_substatus(order) → [stage, [sub_status]].
export function deriveStageSub(order) {
  const o = order || {};
  const status = o.status || "reserved";
  // KN-D14 (mirror BE) — baris backorder `fulfilled` tetap di daftar: hitung yang sisa qty-nya > 0.
  const hasBo = Boolean(o.has_backorder)
    || (o.backorders || []).some((b) => Number(b.backorder_qty || 0) > 0.001 && b.status !== "fulfilled");
  const bo = hasBo ? ["menunggu_stok"] : [];   // Trial 22 Okt (E4) — sisa backorder SO yang sudah jalan di gudang
  const apprReq = Boolean(o.approval_required);
  switch (status) {
    case "cancelled": return ["Cancelled", ["dibatalkan"]];
    case "expired": return ["Cancelled", ["kedaluwarsa"]];
    case "done":
    case "delivered": return ["Delivered", []];
    case "shipped":
    case "dispatched": return ["Shipped", []];
    case "partially_shipped": return ["Shipped", ["sebagian_dikirim", ...bo]];
    case "picked": return ["Picked", ["siap_kirim"]];
    case "partially_picked": return ["Picked", ["sebagian_dipick", ...bo]];
    case "confirmed": return ["Confirmed", ["siap_pick", ...bo]];
    case "approved": return hasBo ? ["Approved", ["menunggu_stok"]] : ["Approved", ["siap_confirm"]];
    case "waiting_approval": return ["Reserved", approvalSubs(o)];
    case "waiting_stock": return ["Reserved", ["menunggu_stok"]];
    case "reserved":
    case "draft": return apprReq ? ["Reserved", ["menunggu_validasi"]] : ["Reserved", ["siap_disahkan"]];
    default: return ["Reserved", []];
  }
}

// Gunakan field BE bila ada (SSOT); jika tidak, derive (fallback aman).
export function getStage(order) {
  if (order && order.stage) return order.stage;
  return deriveStageSub(order)[0];
}

export function getSubStatus(order) {
  if (order && Array.isArray(order.sub_status)) return order.sub_status;
  return deriveStageSub(order)[1];
}
