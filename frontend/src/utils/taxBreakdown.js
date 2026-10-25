/**
 * taxBreakdown — rincian nilai dokumen penjualan/pembelian yang SERAGAM di layar & PDF.
 *
 * Keputusan pemilik K-03 (26 Okt, audit UI tahap 2):
 *   · "Total" dokumen = TERMASUK PPN; DPP (harga sebelum PPN) tampil sebagai rincian.
 *   · PPN 12% atas DPP nilai lain (11/12) → baris "DPP nilai lain (11/12)" ikut tampil.
 * Urutan baris: DPP (harga sebelum PPN) · [DPP nilai lain (11/12)] · PPN x% · Total (termasuk PPN).
 * Kembaran backend: `_total_rows` di `backend/services/pdf_resolvers.py` (PDF SO/PO/Faktur/Faktur Pajak).
 */

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};
const round2 = (n) => Math.round(n * 100) / 100;

/** Total dokumen (termasuk PPN bila ada). */
export function docGrandTotal(doc) {
  return num(doc?.grand_total ?? doc?.total_amount);
}

/** Nominal PPN dokumen (0 bila tidak ber-PPN). */
export function docPpn(doc) {
  return num(doc?.ppn_amount);
}

/** DPP = harga sebelum PPN (benar untuk harga belum/sudah termasuk PPN). */
export function docDpp(doc) {
  const ppn = docPpn(doc);
  if (ppn > 0) return round2(docGrandTotal(doc) - ppn);
  if (doc?.net_subtotal !== undefined && doc?.net_subtotal !== null) return num(doc.net_subtotal);
  return docGrandTotal(doc);
}

/** DPP nilai lain (11/12) dipakai? Bendera dokumen bila ada; dokumen lama tanpa bendera → DPP ≈ 11/12 × harga. */
export function usesDppNilaiLain(doc) {
  const dpp = num(doc?.dpp);
  if (dpp <= 0 || docPpn(doc) <= 0) return false;
  if (doc?.dpp_nilai_lain !== undefined && doc?.dpp_nilai_lain !== null) return !!doc.dpp_nilai_lain;
  const base = docDpp(doc);
  return base > 0 && Math.abs(dpp - (base * 11) / 12) <= 1 && Math.abs(dpp - base) > 1;
}

/** Tarif gaya Indonesia tanpa nol berlebih: 12 → "12", 11.5 → "11,5". */
export function formatRate(rate) {
  return num(rate).toLocaleString("id-ID", { maximumFractionDigits: 2 });
}

/**
 * Baris rincian: [{ key, label, value, strong? }] — `value` berupa angka (format di pemanggil).
 * @param {object} doc dokumen (grand_total, ppn_amount, ppn_rate, dpp, dpp_nilai_lain, ppn_mode, net_subtotal)
 * @param {{ppnLabel?: string}} opts mis. `{ ppnLabel: "PPN Masukan" }` untuk PO
 */
export function taxBreakdownRows(doc, opts = {}) {
  const ppnName = opts.ppnLabel || "PPN";
  const grand = docGrandTotal(doc);
  const ppn = docPpn(doc);
  if (ppn <= 0) return [{ key: "total", label: "Total", value: grand, strong: true }];
  const rate = num(doc?.ppn_rate) > 0 ? ` ${formatRate(doc.ppn_rate)}%` : "";
  const nl = usesDppNilaiLain(doc);
  const rows = [{ key: "dpp", label: "DPP (harga sebelum PPN)", value: docDpp(doc) }];
  if (nl) rows.push({ key: "dpp_nl", label: "DPP nilai lain (11/12)", value: num(doc.dpp) });
  let ppnLabel = `${ppnName}${rate}${nl ? " × DPP nilai lain" : ""}`;
  if (doc?.ppn_mode === "included") ppnLabel += " (sudah termasuk dalam harga)";
  rows.push({ key: "ppn", label: ppnLabel, value: ppn });
  rows.push({ key: "total", label: "Total (termasuk PPN)", value: grand, strong: true });
  return rows;
}
