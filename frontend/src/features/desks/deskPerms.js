/** Izin pengguna: `currentUser` dari App; cadangan lama `localStorage kn_user` (pemanggil tanpa prop). */
export function permsOf(currentUser) {
  if (currentUser?.permissions) return currentUser.permissions;
  try { return JSON.parse(localStorage.getItem("kn_user") || "null")?.permissions || {}; } catch { return {}; }
}
