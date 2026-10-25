// Fase 3 · P1 — UJI JANGKAUAN PERAN berbaseline (rencana fase 3 §0 & §1.1).
//
// Penggabungan layar duplikat (P2–P8) TIDAK boleh membuat peran bawaan kehilangan layar, dan TIDAK boleh diam-diam
// membuka layar baru. Baseline `fixtures/role_reach_baseline.json` dibuat dari konfigurasi SEBELUM fase 3 (HEAD
// b2c092e): untuk tiap peran, setiap id alamat (`?view=<id>`: view tab, id menu/hub, beranda, nama lama) → layar
// tempat ia mendarat. JANGAN membuat ulang baseline dari konfigurasi baru — itu menghapus bukti.
//
// Aturan:
//  1. Setiap id yang dulu sampai MASIH sampai, ke layar yang sama atau ke layar utama alias-nya (registri alias).
//  2. Tidak ada layar tujuan BARU untuk sebuah peran, kecuali tercatat di ROLE_REACH_ADDITIONS (tabel §6 rencana
//     fase 3 — diisi P8/P2 saat aktivasi, satu baris per keputusan).
import baseline from "./fixtures/role_reach_baseline.json";
import { HUB_TABS, NAV_STRUCTURE, ROLE_HOME_REGISTRY, resolveDeepLinkTarget } from "../navigationConfig";
import { ROLE_IDS } from "../roles";
import { aliasTarget, listAliases } from "../viewAliases";

/** Penambahan jangkauan yang SAH: { peran: ["view", …] } + alasan di komentar (rujuk D-xx / §6). */
export const ROLE_REACH_ADDITIONS = {
  // Contoh (diaktifkan P8): manager: ["approval-rules", "pdf-templates"],   // D-04 baca · D-01 tab dasar
  //                         warehouse: ["makloon-claim-recap"],            // D-22
};

function universe() {
  const ids = new Set(baseline.universe);
  Object.values(HUB_TABS).flat().forEach((t) => ids.add(t.view));
  NAV_STRUCTURE.forEach((e) => {
    if (e.type === "standalone") { ids.add(e.id); if (e.view) ids.add(e.view); if (e.hub) ids.add(e.hub); }
    else {
      ids.add(e.groupId);
      (e.items || []).forEach((i) => { if (i.type === "heading") return; ids.add(i.id); if (i.view) ids.add(i.view); if (i.hub) ids.add(i.hub); });
    }
  });
  Object.values(ROLE_HOME_REGISTRY).forEach((h) => { ids.add(h.view); ids.add(h.navId); });
  listAliases().forEach((a) => ids.add(a.from));
  return [...ids].filter(Boolean).sort();
}

const BUILTIN = ROLE_IDS.filter((r) => !String(r).startsWith("cr_") && r !== "__preview");

test("baseline mencakup semua peran bawaan (peran bawaan baru = baseline baru yang disengaja)", () => {
  expect(BUILTIN.filter((r) => !baseline.roles[r])).toEqual([]);
});

test("bukti-merah: mencabut peran dari sebuah tab TERDETEKSI sebagai jangkauan hilang", () => {
  const tab = HUB_TABS["sales-orders"].find((t) => t.view === "keep-pending");
  const roles = tab.roles;
  tab.roles = ["admin"];
  try {
    expect(baseline.roles.sales["keep-pending"]).toBe("keep-pending");
    expect(resolveDeepLinkTarget("keep-pending", "sales")).toBeNull();
  } finally { tab.roles = roles; }
  expect(resolveDeepLinkTarget("keep-pending", "sales")).toMatchObject({ view: "keep-pending" });
});

describe.each(BUILTIN)("peran %s", (role) => {
  test("setiap alamat yang dulu sampai, masih sampai ke layar yang sama / layar utama aliasnya", () => {
    const lost = [];
    for (const [id, view] of Object.entries(baseline.roles[role] || {})) {
      const t = resolveDeepLinkTarget(id, role);
      const ok = new Set([view, aliasTarget(view), aliasTarget(id)]);
      if (!t) lost.push(`${id} → (tidak sampai; dulu ${view})`);
      else if (!ok.has(t.view)) lost.push(`${id} → ${t.view} (dulu ${view})`);
    }
    expect(lost).toEqual([]);
  });

  test("tidak ada layar tujuan BARU selain penambahan tercatat", () => {
    const before = new Set(Object.values(baseline.roles[role] || {}).map(aliasTarget));
    const allowed = new Set(ROLE_REACH_ADDITIONS[role] || []);
    const extra = [];
    for (const id of universe()) {
      const t = resolveDeepLinkTarget(id, role);
      if (t && !before.has(t.view) && !allowed.has(t.view)) extra.push(`${id} → ${t.view}`);
    }
    expect(extra).toEqual([]);
  });
});
