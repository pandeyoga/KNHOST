/**
 * PREP-C (keputusan pemilik 8 Nov 2026, K-GDG-01…08 + K-RFID-04) — utilitas murni profil gedung.
 * Data lokasi & gedung belum tervalidasi → semuanya diatur di profil; bentuk data = backend
 * `warehouse_profile_service.normalize_gate_config` / `validate_profile`.
 */
export const STOCK_MODES = [
  { value: "roll_tagged", label: "Per roll bertag (RFID / label QR)" },
  { value: "quantity", label: "Kuantitas tanpa tag (gate tidak berlaku)" },
];
export const STORAGE_FORMS = [
  { value: "rack", label: "Rak bertingkat" },
  { value: "floor", label: "Petak lantai (tumpukan stacker)" },
];
export const CONFIRM_MODES = [
  { value: "gate", label: "Gate — lintasan gate mencatat gerak (handheld cadangan)" },
  { value: "handheld", label: "Handheld — scan genggam" },
];
export const GATE_LAYOUTS = [
  { value: "", label: "Belum ditentukan" },
  { value: "terpisah", label: "Pintu IN/OUT berjauhan" },
  { value: "berdampingan_sekat", label: "Berdampingan dengan sekat" },
  { value: "berdampingan", label: "Berdampingan tanpa sekat" },
];

/** gate_config tersimpan (baru atau lama `{physical_gate}`) → bentuk baku untuk form. */
export function normalizeGate(gc) {
  const g = gc || {};
  const hasGate = "has_gate" in g ? !!g.has_gate : !!g.physical_gate;
  const mode = hasGate ? (g.confirm_mode === "handheld" ? "handheld" : "gate") : "handheld";
  return {
    has_gate: hasGate,
    confirm_mode: mode,
    pairs: (g.pairs || []).map((p, i) => ({
      id: p.id || "", name: p.name || `Gate ${i + 1}`, in_device_id: p.in_device_id || "",
      out_device_id: p.out_device_id || "", layout: p.layout || "", clear_zone_note: p.clear_zone_note || "",
    })),
  };
}

/** Bentuk kiriman PATCH gate_config (tanpa gate → mode handheld; physical_gate dicerminkan backend). */
export function gatePayload(gate) {
  const g = normalizeGate(gate);
  return { has_gate: g.has_gate, confirm_mode: g.has_gate ? gate.confirm_mode || "gate" : "handheld", pairs: g.pairs };
}

/** Ringkasan satu baris untuk tabel master gudang. */
export function gateSummary(w) {
  if ((w || {}).stock_mode === "quantity") return "mode kuantitas (gate tidak berlaku)";
  const g = normalizeGate((w || {}).gate_config);
  if (!g.has_gate) return "pindai genggam";
  if (g.confirm_mode === "handheld") return "gate terpasang · konfirmasi handheld";
  const n = g.pairs.length;
  return n ? `gerbang pindai fisik · ${n} pasang` : "gerbang pindai fisik · perangkat belum tertaut";
}

/** Butuh aturan penengah? (pasangan IN/OUT berdampingan — K-RFID-04). */
export const needsArbitration = (gate) =>
  normalizeGate(gate).pairs.some((p) => p.layout === "berdampingan" || p.layout === "berdampingan_sekat");

/** Ringkasan aturan simpan gudang (kategori, grade, jenis kain, artikel, PT). */
export function rulesSummary(rules, names = {}) {
  const r = rules || {};
  if ((r.mode || "none") === "none") return "tanpa aturan simpan";
  const parts = [];
  if ((r.categories || []).length) parts.push(`kategori ${r.categories.join(", ")}`);
  if ((r.grades || []).length) parts.push(`grade ${r.grades.join("/")}`);
  if ((r.fabric_types || []).length) parts.push(`kain ${r.fabric_types.join(", ")}`);
  if ((r.template_ids || []).length) parts.push(`${r.template_ids.length} artikel`);
  if ((r.owner_entity_ids || []).length) parts.push(`PT ${r.owner_entity_ids.map((e) => names[e] || e).join(", ")}`);
  return parts.length ? `aturan simpan: ${parts.join(" · ")}` : "aturan simpan: semua barang";
}

export const toggleIn = (list, val) => ((list || []).includes(val) ? list.filter((x) => x !== val) : [...(list || []), val]);
