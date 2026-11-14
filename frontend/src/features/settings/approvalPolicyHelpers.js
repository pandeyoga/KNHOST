// KP-T4 — pembantu murni layar Aturan Persetujuan (satu tabel kebijakan untuk semua antrean).
// Bentuk data = jawaban `GET /api/approval-policies` (`services/approval_policy_service.policy_view`).

export const GROUP_ORDER = ["Penjualan", "Pembelian", "Keuangan", "Gudang", "R&D", "SDM"];

export const SOURCE_BADGE = {
  pt: { label: "Aturan khusus PT ini", cls: "badge-purple" },
  grup: { label: "Aturan grup", cls: "badge-blue" },
  bawaan: { label: "Aturan bawaan (belum disimpan)", cls: "badge-gray" },
};

export const ANY_HOLDER_LABEL = "Semua pemegang akses";

export function fmtAngka(n) {
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 }).format(Number(n) || 0);
}

export function fmtBatasAtas(max) {
  return max === null || max === undefined || max === "" ? "Tanpa batas" : fmtAngka(max);
}

/** Kelompokkan jenis dokumen per kelompok layar, urut `GROUP_ORDER`. */
export function groupKinds(kinds) {
  const out = [];
  GROUP_ORDER.forEach((g) => {
    const items = (kinds || []).filter((k) => k.group === g);
    if (items.length) out.push({ group: g, items });
  });
  const rest = (kinds || []).filter((k) => !GROUP_ORDER.includes(k.group));
  if (rest.length) out.push({ group: "Lainnya", items: rest });
  return out;
}

/** Teks kolom "Yang boleh menyetujui". */
export function approverText(tier) {
  if (tier.any_holder) return ANY_HOLDER_LABEL;
  if (!tier.roles || tier.roles.length === 0) return "Tanpa persetujuan";
  return (tier.role_labels || tier.roles).join(", ");
}

/** Teks kolom "Siapa saja yang lolos" (peran tercantum DAN memegang izinnya). */
export function passingText(tier) {
  if (tier.any_holder) return ANY_HOLDER_LABEL;
  if (!tier.roles || tier.roles.length === 0) return "—";
  return (tier.passing_labels || []).length ? tier.passing_labels.join(", ") : "Belum ada";
}

/** Baris tabel datar untuk satu jenis: [{key, level, label, tier, first}] (sel jenjang hanya di baris pertama). */
export function tableRows(kindView) {
  const rows = [];
  (kindView?.levels || []).forEach((lv) => {
    (lv.tiers || []).forEach((t, i) => {
      rows.push({ key: `${lv.level}-${t.id || i}-${t.min_amount}`, level: lv.level, label: lv.label, tier: t,
        first: i === 0, span: lv.tiers.length });
    });
  });
  return rows;
}

/** Isi editor dari tampilan server (satu jenis): [{level, label, tiers: [{min, max, roles, any_holder}]}]. */
export function draftFromView(kindView) {
  return (kindView?.levels || []).map((lv) => ({
    level: lv.level, label: lv.label || "",
    tiers: (lv.tiers || []).map((t) => ({
      min: t.min_amount === null || t.min_amount === undefined ? "" : String(t.min_amount),
      max: t.max_amount === null || t.max_amount === undefined ? "" : String(t.max_amount),
      roles: [...(t.roles || [])], any_holder: !!t.any_holder,
    })),
  }));
}

/** Isi `PUT /api/approval-policies/{doc_kind}` dari draf editor. */
export function payloadFromDraft(draft, { entityId, version, reason, hasAmount, parse = Number }) {
  return {
    entity_id: entityId || "all", expected_version: version ?? 0, reason,
    levels: (draft || []).map((lv, i) => ({
      level: Number(lv.level) || i + 1, label: (lv.label || "").trim(),
      tiers: (lv.tiers || []).map((t) => ({
        min_amount: hasAmount ? (parse(String(t.min || "0")) || 0) : 0,
        max_amount: hasAmount && String(t.max || "").trim() !== "" ? parse(String(t.max)) : null,
        roles: t.any_holder ? [] : [...(t.roles || [])], any_holder: !!t.any_holder,
      })),
    })),
  };
}
