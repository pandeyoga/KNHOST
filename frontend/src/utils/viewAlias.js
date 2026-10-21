// Cek UI UAT v3 (S14) — tautan giliran/notifikasi dari backend (TURN_MAP) memakai nama lama yang tidak punya
// layar: [Putuskan] retur di "Giliran saya" Manajer dulu membuka halaman kosong. Petakan ke layar yang dirender.
const VIEW_ALIAS = {
  approvals: "approval-inbox",
  finance: "finance-desk",
  "purchase-orders": "purchasing",
};

export function resolveView(view) {
  return VIEW_ALIAS[view] || view;
}
