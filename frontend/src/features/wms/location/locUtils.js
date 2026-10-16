// P02 — utilitas lokasi: istilah tampilan, normalisasi struktur lama/baru, format per satuan.
export const uid = (p) => `${p}_${Math.random().toString(36).slice(2, 9)}`;
const nf = new Intl.NumberFormat("id-ID");
export const q = (v) => nf.format(Math.round((v || 0) * 100) / 100);

// Istilah tampilan (tanpa hierarki kedua): Rak = "Lemari/Rak", Level = "Tingkat".
export const TERMS = { site: "Lokasi", warehouse: "Gudang", zone: "Zona", rack: "Lemari/Rak", level: "Tingkat", bin: "Bin" };

export const FUNCTION_OPTIONS = [
  { value: "", label: "Ikut induk" },
  { value: "storage", label: "Penyimpanan" },
  { value: "qc", label: "QC / Karantina" },
  { value: "staging", label: "Staging" },
  { value: "return", label: "Retur" },
];
export const FUNCTION_LABEL = { storage: "Penyimpanan", qc: "QC / Karantina", staging: "Staging", return: "Retur" };

const keep = (n) => ({ function: n.function || "", rules: n.rules || {} });

// Rak lama (rack.bins langsung) → satu Tingkat ber-id tetap `${rack.id}_lv1` (sama dengan skrip migrasi).
export function normalizeZones(zones) {
  return (zones || []).map((z) => ({
    ...keep(z), id: z.id || uid("zone"), name: z.name || "", code: z.code || "",
    racks: (z.racks || []).map((r) => {
      let levels = r.levels;
      if ((!levels || levels.length === 0) && (r.bins || []).length) {
        levels = [{ id: `${r.id}_lv1`, name: "Tingkat 1", bins: r.bins }];
      }
      return {
        ...keep(r), id: r.id || uid("rack"), name: r.name || "", code: r.code || "",
        levels: (levels || []).map((l) => ({
          ...keep(l), id: l.id || uid("level"), name: l.name || "", code: l.code || "",
          bins: (l.bins || []).map((b) => ({
            ...keep(b), id: b.id || uid("bin"), code: b.code || "",
            capacity: Number(b.capacity || 0), capacity_rolls: b.capacity_rolls || null,
          })),
        })),
      };
    }),
  }));
}

// Isi per satuan — meter, yard dan kg TIDAK pernah dijumlahkan (DEV-F03).
export function fmtUnits(byUnit) {
  const e = Object.entries(byUnit || {}).filter(([, v]) => v);
  return e.length ? e.map(([u, v]) => `${q(v)} ${u}`).join(" · ") : "—";
}

export function ruleSummary(rules) {
  const r = rules || {};
  const parts = [];
  if ((r.categories || []).length) parts.push(`Kategori: ${r.categories.join(", ")}`);
  if ((r.grades || []).length) parts.push(`Grade: ${r.grades.join(", ")}`);
  if ((r.fabric_types || []).length) parts.push(`Kain: ${r.fabric_types.join(", ")}`);
  if (r.single_lot) parts.push("1 lot per bin");
  else if (r.single_sku) parts.push("1 SKU per bin");
  return parts.join(" · ");
}
