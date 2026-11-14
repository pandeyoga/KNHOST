/**
 * mobileLayout — PR-T7 (#24): TATA LETAK aplikasi HP dipilih dari SIFAT peran (halaman awal), bukan dari id peran.
 *
 * Ini tata letak, bukan wewenang: tombol di dalam aplikasi tetap dinyalakan izin (`can(...)`), server tetap menegakkan.
 * Dulu `roleIs(role, [...])`: peran tanpa peran dasar selalu mendapat aplikasi umum, dan memilih aplikasi berarti
 * menyunting daftar nama di beberapa berkas. Kini satu tabel halaman awal → aplikasi:
 *   · halaman awal `sales-home` / `sales-admin-desk`        → aplikasi HP sales (Admin Sales: meja di beranda HP);
 *   · `md-desk`                                              → aplikasi MD;
 *   · `logistics`                                            → aplikasi pengemudi;
 *   · `operations` / `warehouse-admin-desk`                  → aplikasi gudang;
 *   · selain itu                                             → aplikasi umum.
 * Peran kustom mewarisi halaman awal peran dasarnya (`registerDynamicRoles`), jadi hasilnya sama persis dengan
 * `roleIs` lama untuk 13 peran bawaan dan peran kustom berperan dasar. PR-T4 menambah "kategori kerja" peran
 * (`sales` / `sopir` / `gudang`) — saat itu kategori didahulukan di `mobileAppKind`, halaman awal tetap cadangan.
 */
import { ROLE_HOME_REGISTRY } from "../../config/navMeta";

/** Halaman awal peran ("" bila peran belum terdaftar — tidak jatuh ke beranda Sales). */
export const homeViewOf = (role) => ROLE_HOME_REGISTRY[role]?.view || "";

const HOME_APP = {
  "sales-home": "sales", "sales-admin-desk": "sales",
  "md-desk": "md",
  logistics: "driver",
  operations: "warehouse", "warehouse-admin-desk": "warehouse",
};

/** "sales" | "md" | "driver" | "warehouse" | "ops" */
export const mobileAppKind = (role) => HOME_APP[homeViewOf(role)] || "ops";

/** Aplikasi HP sales bertata letak Admin Sales (beranda = meja Admin Sales, label "Pesanan PT"). */
export const isSalesAdminLayout = (role) => homeViewOf(role) === "sales-admin-desk";

/** Peran rancangan menu HP sales (`roles:` pada MENU/GROUPS) yang dipakai peran ini: "sales_admin" / "sales" / id sendiri. */
export const salesMenuRole = (role) => ({ "sales-admin-desk": "sales_admin", "sales-home": "sales" })[homeViewOf(role)] || role;

/** Tab "Pintasan" aplikasi umum (rancangan HP Admin, Manajer, MD). Isi tiap tombol tetap dari izin. */
export const hasShortcutTab = (role) => ["admin-home", "manager-home", "md-desk"].includes(homeViewOf(role));

/** Ringkasan HP per peran (K-12): "designer" | "sample_admin" | "" (panel umum). */
export const summaryKindOf = (role) => ({ "design-requests": "designer", "sample-admin-desk": "sample_admin" })[homeViewOf(role)] || "";
