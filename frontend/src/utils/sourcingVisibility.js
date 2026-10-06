import { can } from "../config/roles";

const storedUser = () => {
  try { return JSON.parse(localStorage.getItem("kn_user") || "null"); } catch { return null; }
};

/** 2026-10 — info sumber stok (PT pemilik, transfer, ATP) hanya untuk pemutus pemenuhan (izin order.override). */
export const canSeeSourcing = (user) => can((user || storedUser())?.permissions, "order", "override");
