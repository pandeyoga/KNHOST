// UAT 24 Okt (audit UI tahap 2) — G0-15 · P-02: kode keputusan/invarian/spesifikasi yang ikut tampil ke pengguna
// ("Menunggu KLX-03", "diputus sistem (KLR-05)", "(keputusan pemilik P7-K1)", "(KN-D16)", "Auto G-6:", "(INV-IC-02/INV-IC-03)",
// "(KN_17 §5.2)"). Hanya keluarga kode yang PASTI internal — kode warna/produk seperti "KN-BLU-01" dan nomor dokumen
// ("KSC/INV-00012") tidak tersentuh.
const CODE = String.raw`\b(?:KL[A-Z]-\d{2}|P\d{1,2}-K\d{1,2}|KN-D\d{1,3}|INV-[A-Z]{2,5}-\d{2}|KN_\d{2}(?:\s*§\s*[\d.]*\d)?)(?![\w-])`;
// Isi kurung yang hanya berisi kode + kata pengantar ("keputusan pemilik", "lihat", "invarian") → buang seluruh kurungnya.
const FILLER_RE = /\b(?:keputusan|pemilik|lihat|aturan|invarian|spesifikasi|fase|dan|atau|sesuai|ref|cek)\b|[\s/,;:·§.…&+-]+/gi;
const PHASE_CODE = String.raw`\bG-\d{1,2}\b`;

function stripDecisionCodes(t) {
  return t
    // (… KODE …) di dalam kurung
    .replace(/\s*\(([^()]*)\)/g, (m, inner) => {
      const hasCode = new RegExp(CODE).test(inner) || new RegExp(String.raw`^\s*${PHASE_CODE}\s*$`).test(inner);
      if (!hasCode) return m;
      const rest = inner.replace(new RegExp(CODE, "g"), "").replace(new RegExp(PHASE_CODE, "g"), "");
      if (!rest.replace(FILLER_RE, "").trim()) return "";
      return ` (${rest.replace(/^[\s/,;:·—-]+|[\s/,;:·—-]+$/g, "").replace(/\s{2,}/g, " ")})`;
    })
    // "Auto G-6: …" / "G-6 — …" (kode fase sebelum titik dua/pemisah)
    .replace(new RegExp(String.raw`${PHASE_CODE}\s*[:·—]\s*`, "g"), "")
    // kode lepas: ", KLX-03" · "Menunggu KLX-03" · "keputusan pemilik P7-K1:" · "INV-IC-02/INV-IC-03"
    .replace(new RegExp(String.raw`\s*[,;·—]?\s*(?:\b[Kk]eputusan\s+(?:pemilik\s+)?)?${CODE}(?:\s*/\s*${CODE})*\s*[:·—]?`, "g"), " ");
}

/** Buang kode penelusuran internal (FASE X, PS-0x, D-0x, MD-0x, KN_18 §…, KLX-03, KLR-05, P7-K1, KN-D16, G-6,
 *  INV-IC-02, KN_17 §…) dari teks yang tampil ke pengguna. */
export function stripInternalCodes(text) {
  if (!text) return text;
  return stripDecisionCodes(String(text))
    .replace(/\s*\((?:FASE|Fase)\s+[A-Z0-9][^)]*\)/g, "")
    .replace(/\s*\((?:PS|D|MD|E)-?\d+[^)]*\)/g, "")
    .replace(/\s*\(KN_18[^)]*\)/g, "")
    .replace(/(?:FASE|Fase)\s+[A-Z](?:-\d+)?\s*[:·—-]?\s*/g, "")
    .replace(/\b(?:PS|D|MD)-\d{2}(?:\/(?:PS|D|MD)-\d{2})*\s*[:·—-]?\s*/g, "")
    .replace(/KN_18\s*§?[\d.]*\s*/g, "")
    .replace(/\bkeputusan\s+(?=[.,)])/gi, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([.,;)])/g, "$1")
    .trim();
}
