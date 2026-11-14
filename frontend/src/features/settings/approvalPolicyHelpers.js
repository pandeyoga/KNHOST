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
