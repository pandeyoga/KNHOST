// Cek UI UAT v3 (S14) — tautan giliran/notifikasi dari backend (TURN_MAP) memakai nama lama yang tidak punya
// layar: [Putuskan] retur di "Giliran saya" Manajer dulu membuka halaman kosong. Petakan ke layar yang dirender.
// Fase 3 · P1 — peta lama (approvals · finance · purchase-orders) dipindah ke registri tunggal
// `config/viewAliases.js` supaya notifikasi, deep link, sidebar & palet membaca SATU sumber.
import { aliasTarget } from "../config/viewAliases";

export function resolveView(view) {
  return aliasTarget(view);
}
