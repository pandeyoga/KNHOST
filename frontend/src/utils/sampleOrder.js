// REVISI SAMPEL — batas sample per baris (cermin backend `sample_sale_service.SAMPLE_LIMITS`):
// woven maks 5 yard · knitting maks 2 kg. Default qty saat pilih "Order Sample" = maksimum.
export const SAMPLE_LIMITS = {
  woven: { max_qty: 5, unit: "yard", label: "woven" },
  knit: { max_qty: 2, unit: "kg", label: "knitting" },
};

// L06 LN-060 — batas MAKSIMAL per jenis sample (cermin backend SAMPLE_KINDS); bukan qty wajib.
export const SAMPLE_KINDS = {
  standard: { label: "Standar", limits: { woven: 5, knit: 2 } },
  hanger: { label: "Hanger", limits: { woven: 0.5, knit: 2 } },
};

// Benang (tahap yarn) bukan kain — tidak bisa dipotong jadi sample (cermin backend SAMPLE_NOT_ALLOWED).
export const SAMPLE_BLOCKED_STAGES = ["yarn"];
export const canSample = (product) => !SAMPLE_BLOCKED_STAGES.includes(String(product?.stage || "").toLowerCase());

export function sampleLimit(product, kind = "standard") {
  const ft = String(product?.fabric_type || "woven").toLowerCase();
  const rule = SAMPLE_LIMITS[ft] || SAMPLE_LIMITS.woven;
  const max = (SAMPLE_KINDS[kind] || SAMPLE_KINDS.standard).limits[ft in SAMPLE_LIMITS ? ft : "woven"];
  return { ...rule, max_qty: max, kind, fabric_type: ft, base_unit: product?.base_unit || rule.unit };
}

export function clampSampleQty(product, qty, kind = "standard") {
  const { max_qty } = sampleLimit(product, kind);
  const n = Number(qty);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return Math.min(max_qty, Math.round(n * 100) / 100);
}

export const isSampleCart = (cart) => cart.length > 0 && cart.every((i) => i.is_sample);
export const isRegularCart = (cart) => cart.length > 0 && cart.every((i) => !i.is_sample);

export const SAMPLE_STATUS_LABEL = {
  waiting_approval: "Menunggu ACC bayar",
  approved: "Siap ke gudang",
  confirmed: "Di gudang (potong)",
  partially_picked: "Sebagian dipotong",
  picked: "Dipotong · packing",
  partially_shipped: "Sebagian dikirim",
  shipped: "Dikirim / diambil",
  delivered: "Diterima",
  done: "Selesai",
  cancelled: "Dibatalkan",
};
