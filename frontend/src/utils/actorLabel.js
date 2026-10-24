/**
 * UAT 24 Okt (audit UI) — nama pelaku/pengaju untuk layar: akun teknis (seed/sistem) tidak ditampilkan mentah
 * ("system-seed", "seed", "system") — diganti "Sistem (data awal)" / "Sistem".
 */
const TECH = {
  "system-seed": "Sistem (data awal)", seed: "Sistem (data awal)", "seed-script": "Sistem (data awal)",
  system: "Sistem", sistem: "Sistem", scheduler: "Sistem (penjadwal)", cron: "Sistem (penjadwal)",
};

export function actorLabel(name, fallback = "—") {
  const s = String(name ?? "").trim();
  if (!s) return fallback;
  return TECH[s.toLowerCase()] || s;
}

/** Akun teknis tidak dihitung sebagai orang (mis. "Desainer aktif", peringkat KPI). */
export function isTechActor(name) {
  return Object.prototype.hasOwnProperty.call(TECH, String(name ?? "").trim().toLowerCase());
}
