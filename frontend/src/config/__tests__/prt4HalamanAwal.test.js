// PR-T4 — halaman awal semua peran (bawaan & kustom) diisi dari `home_view`/`home_nav_id` jawaban `GET /api/roles`;
// nilai tertulis `ROLE_HOME_REGISTRY` = cadangan sebelum jawaban datang.
import { ROLE_HOME_REGISTRY } from "../navMeta";
import { categoryOf, homeChangedByServer, registerDynamicRoles } from "../roles";
import { defaultNavIdForRole, defaultViewForRole } from "../navigationConfig";

const TERTULIS = JSON.parse(JSON.stringify(ROLE_HOME_REGISTRY));
const bawaan = (over = {}) => Object.keys(TERTULIS).map((id) => ({ id, custom: false, label: id,
  home_view: TERTULIS[id].view, home_nav_id: TERTULIS[id].navId, ...(over[id] || {}) }));

afterEach(() => { registerDynamicRoles(bawaan()); });

test("nilai server sama dengan tertulis → tidak ada yang berubah (id menu tertulis dipertahankan)", () => {
  // Desainer: server `design-requests`/`design-requests`, tertulis navId `designer-hub` → sorotan tetap.
  registerDynamicRoles(bawaan({ designer: { home_nav_id: "design-requests" } }));
  expect(ROLE_HOME_REGISTRY.designer).toEqual(TERTULIS.designer);
  expect(homeChangedByServer("designer")).toBe(false);
});

test("peran bawaan yang halaman awalnya diatur Admin mendarat di layar baru", () => {
  const changed = registerDynamicRoles(bawaan({ sales: { home_view: "my-desk", home_nav_id: "my-desk" } }));
  expect(changed).toBe(true);
  expect(defaultViewForRole("sales")).toBe("my-desk");
  expect(defaultNavIdForRole("sales")).toBe("my-desk");
  expect(homeChangedByServer("sales")).toBe(true);
  registerDynamicRoles(bawaan());
  expect(ROLE_HOME_REGISTRY.sales).toEqual(TERTULIS.sales);
});

test("peran kustom: halaman awal dari server; tanpa jawaban → peran dasar; tanpa peran dasar → Profil Saya", () => {
  registerDynamicRoles([...bawaan(),
    { id: "cr_kurir", custom: true, label: "Kurir", base_role: "", home_view: "logistics", home_nav_id: "logistics" },
    { id: "cr_sales_senior", custom: true, label: "Sales Senior", base_role: "sales", home_view: "sales-home",
      home_nav_id: "home" },
    { id: "cr_lama", custom: true, label: "Lama", base_role: "warehouse" },
    { id: "cr_kosong", custom: true, label: "Kosong", base_role: "" }]);
  expect(ROLE_HOME_REGISTRY.cr_kurir).toEqual({ view: "logistics", navId: "logistics" });
  expect(ROLE_HOME_REGISTRY.cr_sales_senior).toEqual(TERTULIS.sales);
  expect(ROLE_HOME_REGISTRY.cr_lama).toEqual(TERTULIS.warehouse);
  expect(ROLE_HOME_REGISTRY.cr_kosong).toEqual({ view: "hr-my-profile", navId: "hr-my-profile" });
});

test("kategori kerja dari server: peran kustom berdasar Sales = sales; Kurir tanpa peran dasar = sopir", () => {
  expect(categoryOf("warehouse")).toBe("gudang");
  expect(categoryOf("sales_admin")).toBe("");
  registerDynamicRoles([...bawaan(),
    { id: "cr_kurir", custom: true, label: "Kurir", base_role: "", kategori_kerja: "sopir" },
    { id: "cr_sales_senior", custom: true, label: "Sales Senior", base_role: "sales", kategori_kerja: "sales" },
    { id: "warehouse", custom: false, label: "Gudang", home_view: TERTULIS.warehouse.view, kategori_kerja: "" }]);
  expect(categoryOf("cr_kurir")).toBe("sopir");
  expect(categoryOf("cr_sales_senior")).toBe("sales");
  expect(categoryOf("warehouse")).toBe("");   // diubah Admin
  registerDynamicRoles([...bawaan(), { id: "warehouse", custom: false, home_view: TERTULIS.warehouse.view,
                                       kategori_kerja: "gudang" }]);
  expect(categoryOf("cr_kurir")).toBe("");    // peran kustom dihapus
});
