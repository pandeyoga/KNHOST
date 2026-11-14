/** Util izin peran di sisi klien — cermin `access_modules.py` (level_of / apply_levels). */

export const fullActions = (module, resource) => module.actions?.[resource] || [];

/** PR-T5 — tingkat yang berlaku untuk modul (dari server; cadangan: hitung dari aksi penuh seperti server). */
export function levelsAvailable(module) {
  if (Array.isArray(module?.levels_available) && module.levels_available.length) return module.levels_available;
  const acts = (module?.resources || []).map((r) => fullActions(module, r));
  if (!acts.some((a) => a.includes("view"))) return ["none", "manage"];
  if (acts.every((a) => a.every((x) => x === "view"))) return ["none", "view"];
  return ["none", "view", "manage"];
}

/** PR-T5 — jumlah aksi dipegang / aksi penuh modul (cermin `access_modules._held_total`). */
export function heldTotal(perms, module) {
  let held = 0; let total = 0;
  module.resources.forEach((r) => {
    const full = fullActions(module, r);
    const have = new Set(perms[r] || []);
    total += full.length;
    held += have.has("*") ? full.length : full.filter((a) => have.has(a)).length;
  });
  return { held, total };
}

export function levelOf(perms, module) {
  const { held, total } = heldTotal(perms, module);
  const acts = new Set();
  module.resources.forEach((r) => (perms[r] || []).forEach((a) => acts.add(a)));
  if (!acts.size) return { level: "none", partial: false, held: 0, total };
  if ([...acts].every((a) => a === "view")) return { level: "view", partial: false, held, total };
  const full = module.resources.every((r) => {
    const have = new Set(perms[r] || []);
    return fullActions(module, r).every((a) => have.has(a));
  });
  return { level: "manage", partial: !full, held, total };
}

/** PR-T5 — aksi yang ditambah & dicabut per halaman (sumber daya) satu modul: [{resource, added, removed}]. */
export function actionDiff(perms, original, module) {
  return module.resources.map((r) => {
    const now = new Set(perms[r] || []);
    const was = new Set(original[r] || []);
    const order = fullActions(module, r);
    const sorted = (xs) => [...xs].sort((a, b) => order.indexOf(a) - order.indexOf(b));
    return { resource: r, added: sorted([...now].filter((a) => !was.has(a))), removed: sorted([...was].filter((a) => !now.has(a))) };
  }).filter((d) => d.added.length || d.removed.length);
}

/** PR-T5 — kalimat aksi berisiko (`sensitive_actions` server) yang DITAMBAHKAN oleh perubahan ini, tanpa kembar. */
export function sensitiveAdded(perms, original, modules) {
  const out = [];
  modules.forEach((m) => actionDiff(perms, original, m).forEach(({ resource, added }) => added.forEach((a) => {
    const kalimat = m.sensitive_actions?.[resource]?.[a];
    if (kalimat && !out.includes(kalimat)) out.push(kalimat);
  })));
  return out;
}

export function applyLevel(perms, module, level) {
  const out = { ...perms };
  module.resources.forEach((r) => {
    const full = fullActions(module, r);
    if (level === "none") delete out[r];
    else if (level === "view") { if (full.includes("view")) out[r] = ["view"]; else delete out[r]; }
    else out[r] = [...full];
  });
  return out;
}

export function toggleAction(perms, module, resource, action) {
  const full = fullActions(module, resource);
  const have = new Set(perms[resource] || []);
  if (have.has(action)) {
    have.delete(action);
    if (action === "view") have.clear();           // tanpa Lihat, aksi lain tidak berarti
  } else {
    have.add(action);
    if (full.includes("view")) have.add("view");   // aksi apa pun menyiratkan Lihat
  }
  const out = { ...perms };
  const list = full.filter((a) => have.has(a));
  if (list.length) out[resource] = list; else delete out[resource];
  return out;
}

export function setResource(perms, module, resource, all) {
  const out = { ...perms };
  if (all) out[resource] = [...fullActions(module, resource)]; else delete out[resource];
  return out;
}

export const sameActions = (a = [], b = []) => [...a].sort().join(",") === [...b].sort().join(",");

export const moduleActionsChanged = (perms, original, module) =>
  module.resources.some((r) => !sameActions(perms[r], original[r]));
