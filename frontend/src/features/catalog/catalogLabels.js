/**
 * UAT 24 Okt (audit UI tahap 2) — G4-19: label manusia untuk jenis kain, tahap bahan & sumbu varian di
 * layar Produk & Varian. Dulu subjudul/kartu/tab Informasi mencetak kode mentah ("woven"), sumbu
 * "color × size × material", dan satu tahap bernama tiga cara ("Kain Jadi", "Finished (…)", "Kain jadi").
 * Sumber label = registri domain (`useDomainEnums`) supaya SAMA dengan isian form & filter.
 */
import useDomainEnums from "../../hooks/useDomainEnums";

// Nilai tahap lama di data induk → kode registri.
const LEGACY_STAGE = { greige: "grey", dyed: "finished" };
// Cadangan selama registri belum termuat (label sama dengan registri backend).
const FALLBACK = {
  fabric_type: { woven: "Woven (Tenun)", knit: "Knit (Rajut)" },
  stage: { yarn: "Benang (Yarn)", grey: "Grey / Greige (Kain Mentah)", finished: "Finished (Jadi — dyed/printed)" },
};
// Sumbu varian yang labelnya masih kunci Inggris.
const AXIS_LABEL = {
  color: "Warna", colour: "Warna", warna: "Warna", size: "Ukuran", material: "Material", grade: "Grade",
  lebar: "Lebar", width: "Lebar", motif: "Motif", gramasi: "Gramasi", pattern: "Motif",
};

export const axisLabel = (a) => {
  const raw = String(a?.label || "").trim();
  const key = String(a?.key || "").trim().toLowerCase();
  return AXIS_LABEL[raw.toLowerCase()] || (raw && raw.toLowerCase() !== key ? raw : AXIS_LABEL[key] || raw || key);
};

export const axesText = (axes) => (axes || []).map(axisLabel).join(" × ");

export function useCatalogLabels() {
  const { labelOf } = useDomainEnums();
  const label = (name, v) => {
    if (!v) return "—";
    const hit = labelOf(name, v);
    return hit && hit !== v ? hit : FALLBACK[name]?.[v] || v;
  };
  return {
    stageLabel: (v) => label("stage", LEGACY_STAGE[v] || v),
    fabricLabel: (v) => label("fabric_type", v),
  };
}
