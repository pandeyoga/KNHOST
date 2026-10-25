/**
 * viewAliases.js — REGISTRI ALIAS LAYAR (fase 3 · P1, pola "gabung" §1.1 rencana fase 3).
 *
 * KENAPA ADA: keputusan pemilik 26 Okt — layar duplikat TIDAK dihapus, melainkan menjadi
 * TAUTAN ke layar utama. Alamat lama (`?view=<lama>`, notifikasi, giliran, papan antrean,
 * bookmark) harus tetap mendarat di tempat yang benar. Satu registri ini dibaca oleh SEMUA
 * jalan masuk navigasi: sidebar/palet Ctrl+K/deep link (`navigationConfig.resolveDeepLinkTarget`),
 * `App.js` (`handleNavSelect` → preset), notifikasi (`utils/viewAlias.resolveView`).
 *
 * Bentuk entri:
 *   "<id lama>": {
 *     to: "<view utama>",        // WAJIB — view yang dirender AppViewRouter
 *     nav: "<navId utama>",      // opsional — menu yang disorot (bawaan: turunan dari `to`)
 *     preset: { tab: "…" },      // opsional — dibaca layar utama lewat `useViewPreset(to)`
 *     label: "Nama lama",        // opsional — palet Ctrl+K menampilkan "Nama lama → kini di <utama>"
 *     since: "D-06",             // asal keputusan (dokumentasi + guardrail)
 *     legacy: true,              // nama lama TANPA layar sendiri (tidak butuh rute cadangan)
 *   }
 *
 * Aturan (dijaga `scripts/guardrails/verify_view_aliases.py` + `config/__tests__/viewAliases.test.js`):
 *  · `to` bukan alias lagi (tanpa rantai) dan ada di menu;
 *  · alias non-`legacy` tetap punya rute cadangan `activeView === "<lama>"` di AppViewRouter;
 *  · peran yang dulu bisa membuka id lama ⊆ peran yang bisa membuka `to` (uji jangkauan peran).
 *
 * ISI AWAL (P1) hanya alias lama yang sudah ada di `utils/viewAlias.js` (Cek UI UAT v3 S14).
 * Alias penggabungan D-xx diaktifkan di P8 (tabel §6 rencana fase 3).
 */
export const VIEW_ALIASES = {
  // Cek UI UAT v3 (S14) — tautan giliran/notifikasi backend (TURN_MAP) memakai nama lama tanpa layar.
  approvals: { to: "approval-inbox", legacy: true, since: "S14" },
  finance: { to: "finance-desk", legacy: true, since: "S14" },
  "purchase-orders": { to: "purchasing", nav: "purchase-orders", legacy: true, since: "S14" },
};

/** Alias untuk `view` → `{ from, to, nav, preset, label, since, legacy }`, atau null bila bukan alias. */
export function resolveAlias(view) {
  if (typeof view !== "string" || !view) return null;
  const a = Object.prototype.hasOwnProperty.call(VIEW_ALIASES, view) ? VIEW_ALIASES[view] : null;
  if (!a || !a.to || a.to === view) return null;
  return {
    from: view,
    to: a.to,
    nav: a.nav || null,
    preset: a.preset || null,
    label: a.label || "",
    since: a.since || "",
    legacy: !!a.legacy,
  };
}

/** View utama untuk `view` (alias → tujuannya; selain itu view itu sendiri). */
export function aliasTarget(view) {
  return resolveAlias(view)?.to || view;
}

/** Semua alias yang menunjuk `view` (mis. untuk palet/breadcrumb). */
export function aliasesOf(view) {
  return Object.keys(VIEW_ALIASES).filter((k) => VIEW_ALIASES[k]?.to === view).map(resolveAlias).filter(Boolean);
}

/** Daftar semua alias (untuk uji & palet). */
export function listAliases() {
  return Object.keys(VIEW_ALIASES).map(resolveAlias).filter(Boolean);
}
