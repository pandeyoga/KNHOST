// KP-T4 — pembantu murni layar Aturan Persetujuan (satu tabel kebijakan untuk semua antrean).
// Bentuk data = jawaban `GET /api/approval-policies` (`services/approval_policy_service.policy_view`).

export const GROUP_ORDER = ["Penjualan", "Pembelian", "Keuangan", "Gudang", "R&D", "SDM"];

// Pola UI 16 Nov (M43) — lencana asal pendek, sama dengan daftar pengaturan (Bawaan sistem · Aturan grup · Khusus PT);
// keterangan panjangnya di tooltip. Dulu "Aturan bawaan (belum disimpan)" memenuhi tiap kartu.
export const SOURCE_BADGE = {
  pt: { label: "Khusus PT ini", cls: "badge-purple", title: "Aturan khusus PT ini — PT lain tidak terpengaruh" },
  grup: { label: "Aturan grup", cls: "badge-blue",
    title: "Aturan grup — berlaku untuk semua PT yang tidak punya aturan sendiri" },
  bawaan: { label: "Bawaan sistem", cls: "badge-muted", title: "Aturan bawaan sistem — belum pernah disimpan" },
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

const tierAktif = (t) => Boolean(t.any_holder) || (t.roles || []).length > 0;

/** Pola UI 16 Nov — ringkasan SATU baris di daftar padat: "Tanpa persetujuan" · "mulai Rp 50.000.000 · Manajer,
 *  Finance" · "3 jenjang: Atasan Langsung → Pimpinan → Bagian Keuangan". Rentang tanpa peran tidak dihitung. */
export function ruleSummary(kind) {
  const levels = (kind?.levels || [])
    .map((lv) => ({ ...lv, tiers: (lv.tiers || []).filter(tierAktif) }))
    .filter((lv) => lv.tiers.length);
  if (!levels.length) return "Tanpa persetujuan";
  const terendah = Math.min(...levels.flatMap((lv) => lv.tiers.map((t) => Number(t.min_amount) || 0)));
  const mulai = kind.has_amount && terendah > 0 ? `mulai Rp ${fmtAngka(terendah)} · ` : "";
  if (levels.length === 1) {
    const tiers = levels[0].tiers;
    return tiers.length === 1 ? `${mulai}${approverText(tiers[0])}` : `${mulai}${tiers.length} rentang nilai`;
  }
  return `${mulai}${levels.length} jenjang: ${levels.map((lv) => lv.label || `Jenjang ${lv.level}`).join(" → ")}`;
}

/** Jumlah hal yang perlu dicek pada satu jenis: peringatan server + rentang berperan tanpa izin. */
export function issueCount(kind) {
  const noPerm = (kind?.levels || []).reduce((n, lv) => n
    + (lv.tiers || []).filter((t) => (t.no_permission_labels || []).length).length, 0);
  return (kind?.warnings || []).length + noPerm;
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
