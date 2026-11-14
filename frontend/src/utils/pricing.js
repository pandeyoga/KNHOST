// Fase 1B — preview pricing di sisi klien (CERMIN backend services/config_service.compute_order_pricing).
// Tujuan: tampilkan ringkasan diskon + PPN sebelum order dibuat. Backend tetap
// otoritatif saat menyimpan; util ini hanya untuk preview UX.
// F-10 Coretax — dukung DPP Nilai Lain (PPN efektif = tarif × pembilang/penyebut; TX-T1: dari pengaturan PT).

// KN-D21 — SATU cermin `compute_order_pricing` untuk keranjang, checkout, PO buat & PO ubah.
// `opts.cfgSection` ("sales" | "purchasing") memilih sakelar diskon yang dihormati server;
// `opts.taxOverride` ("non_ppn" | "ppn") = parameter tax_override server. Pembulatan
// bertahap (2 desimal per baris/tahap) mengikuti server supaya angka layar == tersimpan.
const r2 = (n) => Math.round((Number(n) + Number.EPSILON) * 100) / 100;

// TX-T1 — cara bulat PPN mengikuti pengaturan PT (`tax.pembulatan_satuan`): dua desimal (bawaan) atau rupiah penuh.
// Cermin `tax_config_service.round_money` (setengah ke atas).
export function roundTax(n, satuan) {
  return satuan === "rupiah_penuh" ? Math.round(Number(n) + Number.EPSILON) : r2(n);
}

// Bila server lama belum mengirim kuncinya: bawaan registry (`tax.dpp_nilai_lain_pembilang` 11 / `_penyebut` 12).
const BAWAAN_REGISTRY = { pembilang: 11, penyebut: 12 };

/**
 * TX-T1 — aturan pajak pratinjau dari `GET /settings/effective` bagian `tax` (server mengisinya dengan nilai yang DIPAKAI
 * mesin, termasuk bawaan registry). Faktor DPP nilai lain & cara bulat dulu ditulis mati di sini (11/12, dua desimal).
 */
export function taxRules(tax = {}) {
  const pembilang = Number(tax.dpp_nilai_lain_pembilang) || BAWAAN_REGISTRY.pembilang;
  const penyebut = Number(tax.dpp_nilai_lain_penyebut) || BAWAAN_REGISTRY.penyebut;
  return {
    pembilang, penyebut,
    factor: pembilang / penyebut,
    satuan: tax.pembulatan_satuan || "dua_desimal",
    tingkat: tax.pembulatan_tingkat || "dokumen",
  };
}

export function computeOrderPreview(items, orderDiscountPercent, settings, opts = {}) {
  const section = opts.cfgSection || "sales";
  const disc = (settings && settings[section]) || {};
  const tax = (settings && settings.tax) || {};
  const allowItem = disc.allow_item_discount !== false;
  const allowOrder = disc.allow_order_discount !== false;
  const isPkp = opts.taxOverride === "non_ppn" ? false : (opts.taxOverride === "ppn" ? true : tax.is_pkp !== false);
  const rate = isPkp ? Number(tax.ppn_rate || 0) : 0;
  const mode = tax.ppn_mode || "excluded";
  const useNL = rate > 0 && tax.dpp_nilai_lain === true;
  const rules = taxRules(tax);
  const dppFactor = useNL ? rules.factor : 1;
  const effRate = rate * dppFactor;
  const bulat = (n) => roundTax(n, rules.satuan);

  let gross = 0;
  let itemsDisc = 0;
  const lineTotals = [];
  (items || []).forEach((it) => {
    const price = Number((it.product && it.product.price) || it.price || 0);
    const qty = Number(it.quantity || 0);
    const subtotal = r2(price * qty);
    const dp = allowItem ? Math.max(0, Math.min(100, Number(it.discount_percent || 0))) : 0;
    gross += subtotal;
    itemsDisc += r2((subtotal * dp) / 100);
    lineTotals.push(r2(subtotal - r2((subtotal * dp) / 100)));
  });
  gross = r2(gross); itemsDisc = r2(itemsDisc);

  const afterItem = r2(gross - itemsDisc);
  const odp = allowOrder ? Math.max(0, Math.min(100, Number(orderDiscountPercent || 0))) : 0;
  const orderDisc = r2((afterItem * odp) / 100);
  const net = r2(afterItem - orderDisc);

  // PPN atas satu dasar — urutan sama dengan server `ppn_breakdown` (dua desimal: harga jual dulu; rupiah penuh: PPN dulu).
  const ppnOf = (base) => {
    if (mode === "included") {
      if (rules.satuan === "dua_desimal") return r2(base - bulat(base / (1 + effRate / 100)));
      return bulat(base - base / (1 + effRate / 100));
    }
    return bulat((base * effRate) / 100);
  };

  let dpp;
  let ppn;
  let grand;
  if (!isPkp || rate <= 0) {
    dpp = net; ppn = 0; grand = net;
  } else {
    if (rules.tingkat === "baris" && lineTotals.length) {
      // TX-T1 — PPN tiap baris lalu dijumlah; diskon pesanan dibagi sebanding nilai baris (sisa di baris terakhir).
      let bases = lineTotals;
      if (Math.abs(net - afterItem) >= 0.005 && afterItem > 0) {
        bases = lineTotals.slice(0, -1).map((t) => r2((t * net) / afterItem));
        bases.push(r2(net - bases.reduce((a, b) => a + b, 0)));
      }
      ppn = r2(bases.reduce((a, b) => a + ppnOf(b), 0));
    } else {
      ppn = ppnOf(net);
    }
    const hargaJual = mode === "included" ? r2(net - ppn) : net;
    dpp = bulat(hargaJual * dppFactor);
    grand = mode === "included" ? net : r2(net + ppn);
  }

  return {
    gross,
    itemsDisc,
    orderDisc,
    discountTotal: itemsDisc + orderDisc,
    net,
    dpp,
    ppnRate: rate,
    effectiveRate: effRate,
    dppNilaiLain: useNL,
    dppFactorLabel: `${rules.pembilang}/${rules.penyebut}`,
    rounding: rules.satuan,
    ppn,
    grand,
    mode,
    isPkp,
    allowItem,
    allowOrder,
  };
}
