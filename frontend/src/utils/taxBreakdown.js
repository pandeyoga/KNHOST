/**
 * taxBreakdown — rincian nilai dokumen penjualan/pembelian yang SERAGAM di layar & PDF.
 *
 * Keputusan pemilik K-03 (26 Okt, audit UI tahap 2):
 *   · "Total" dokumen = TERMASUK PPN; DPP (harga sebelum PPN) tampil sebagai rincian.
 *   · PPN 12% atas DPP nilai lain (11/12) → baris "DPP nilai lain (11/12)" ikut tampil (TX-T1: pecahan dari potret
 *     pajak dokumen `tax_snapshot`).
 * Urutan baris: DPP (harga sebelum PPN) · [DPP nilai lain (11/12)] · PPN x% · Total (termasuk PPN).
 * Kembaran backend: `_total_rows` di `backend/services/pdf_resolvers.py` (PDF SO/PO/Faktur/Faktur Pajak).
 */

import { formatDate } from "./formatters";

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

/** DPP nilai lain dipakai? Potret pajak dokumen (TX-T1) / bendera dokumen bila ada; dokumen lama tanpa bendera →
 *  DPP ≈ 11/12 × harga (aturan sebelum faktornya bisa diatur). */
export function usesDppNilaiLain(doc) {
  const dpp = num(doc?.dpp);
  if (dpp <= 0 || docPpn(doc) <= 0) return false;
  const snap = doc?.tax_snapshot;
  if (snap && snap.dpp_nilai_lain !== undefined && snap.dpp_nilai_lain !== null) return !!snap.dpp_nilai_lain;
  if (doc?.dpp_nilai_lain !== undefined && doc?.dpp_nilai_lain !== null) return !!doc.dpp_nilai_lain;
  const base = docDpp(doc);
  return base > 0 && Math.abs(dpp - (base * 11) / 12) <= 1 && Math.abs(dpp - base) > 1;
}

/** TX-T1 — pecahan DPP nilai lain dokumen: dari potret pajaknya; dokumen lama (tanpa potret) = aturan lama 11/12. */
export function dppFactorText(doc) {
  const s = doc?.tax_snapshot || {};
  const p = num(s.dpp_pembilang);
  const q = num(s.dpp_penyebut);
  return p > 0 && q > 0 ? `${p}/${q}` : "11/12";
}

const SATUAN_LABEL = { dua_desimal: "dua angka di belakang koma", rupiah_penuh: "rupiah penuh" };
const TINGKAT_LABEL = { dokumen: "per dokumen", baris: "per baris" };

/**
 * TX-T1 — "Aturan pajak saat terbit/dibuat" dari potret dokumen (`tax_snapshot`) → [{ key, label, value }] berisi teks
 * siap tampil. `null` bila dokumen belum punya potret (dokumen lama: tampilkan dari field yang ada).
 */
export function taxRuleRows(doc) {
  const s = doc?.tax_snapshot;
  if (!s) return null;
  if (s.is_pkp === false) return [{ key: "pkp", label: "PPN", value: "Tanpa PPN (bukan PKP)" }];
  const rows = [{ key: "tarif", label: "Tarif PPN", value: `${formatRate(s.ppn_rate)}%` }];
  rows.push({ key: "faktor", label: "DPP nilai lain", value: s.dpp_nilai_lain ? dppFactorText(doc) : "Tidak dipakai" });
  rows.push({ key: "bulat", label: "Pembulatan", value: `${TINGKAT_LABEL[s.pembulatan_tingkat] || "per dokumen"}, `
    + `${SATUAN_LABEL[s.pembulatan_satuan] || "dua angka di belakang koma"}` });
  rows.push({ key: "mode", label: "Harga", value: s.ppn_mode === "included" ? "sudah termasuk PPN" : "belum termasuk PPN" });
  if (s.berlaku_pada) {
    rows.push({ key: "berlaku", label: s.asal === "dokumen_lama" ? "Aturan lama, dokumen dibuat" : "Aturan berlaku pada",
      value: formatDate(s.berlaku_pada) });
  }
  return rows;
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
  if (nl) rows.push({ key: "dpp_nl", label: `DPP nilai lain (${dppFactorText(doc)})`, value: num(doc.dpp) });
  let ppnLabel = `${ppnName}${rate}${nl ? " × DPP nilai lain" : ""}`;
  if (doc?.ppn_mode === "included") ppnLabel += " (sudah termasuk dalam harga)";
  rows.push({ key: "ppn", label: ppnLabel, value: ppn });
  rows.push({ key: "total", label: "Total (termasuk PPN)", value: grand, strong: true });
  return rows;
}
