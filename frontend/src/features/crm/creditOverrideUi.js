// CR-T3 — label izin kredit bersama (tanpa komponen berat, aman diimpor daftar & uji).
export const SCOPE_LABEL = { pesanan: "Pesanan ini", pelanggan: "Pelanggan ini" };
export const scopeLabel = (row) => SCOPE_LABEL[row?.scope === "pesanan" ? "pesanan" : "pelanggan"];
