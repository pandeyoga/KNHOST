/**
 * FIX-1 (audit WMS-RFID 9 Nov 2026) — sisi klien cakupan lokasi kerja & PT.
 *  · UI-39  — logout menghapus PT aktif & status klien per pengguna; login memilih PT BAWAAN akun.
 *  · UI-23  — sopir mendapat aplikasi HP Pengiriman saja (bukan aplikasi gudang ber-izin wms.view).
 *  · K-B1-02 — aksi dokumen dari daftar lintas PT dikirim atas nama PT dokumen (registri + interseptor).
 *  · K-B1-01 — bilah cakupan menampilkan cakupan aktif & anjuran bila lokasi kerja belum diatur.
 *  · UI-39  — antrean offline milik pengguna perekamnya.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import apiClient, { setActiveEntity, setLocationScope } from "../../services/apiClient";
import { rememberDocEntities, docEntityFor, forgetDocEntities } from "../../services/docEntityRegistry";
import { useAppActions } from "../../hooks/useAppActions";
import MobileAppSwitch from "../mobile/MobileAppSwitch";
import LocationScopeBar from "../../components/LocationScopeBar";
import { enqueue, pending, syncQueue } from "../../utils/offlineQueue";

jest.mock("../tanya/TanyaKnView", () => () => null);
jest.mock("../logistics/DriverTodayPanel", () => () => <div data-testid="stub-driver-today" />);
jest.mock("../logistics/DeliveryDetailModal", () => () => null);
jest.mock("../sales/mobile/MobilePwa", () => ({
  MobilePushBanner: () => null, MobilePushCard: () => null, MobileInstallCard: () => null,
  syncPushSubscription: () => {}, dropPushSubscription: async () => {},
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!window.matchMedia) window.matchMedia = () => ({ matches: false, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {} });

let captured = [];
let respond = () => ({ data: {} });
const realAdapter = axios.defaults.adapter;
beforeEach(() => {
  captured = [];
  respond = () => ({ data: {} });
  axios.defaults.adapter = async (config) => {
    captured.push(config);
    return { data: respond(config), status: 200, statusText: "OK", headers: {}, config };
  };
  localStorage.clear();
  forgetDocEntities();
  setActiveEntity("");
  setLocationScope("");
});
afterAll(() => { axios.defaults.adapter = realAdapter; });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
const hdr = (config, name) => (config.headers?.get ? config.headers.get(name) : config.headers?.[name]);

describe("K-B1-02 — aksi dokumen lintas PT atas nama PT dokumen", () => {
  test("registri mencocokkan id dokumen pada path", () => {
    rememberDocEntities([{ id: "pa_1", work_entity_id: "ent_kanda" }, { id: "trf_9", entity_id: "ent_ksc" }]);
    expect(docEntityFor("/api/putaway-orders/pa_1/dispatch")).toBe("ent_kanda");
    expect(docEntityFor("/api/transfers/trf_9?x=1")).toBe("ent_ksc");
    expect(docEntityFor("/api/transfers")).toBe("");
  });

  test("interseptor mengganti X-Entity-Id bawaan dengan PT dokumen yang ditugaskan; header eksplisit dihormati", async () => {
    localStorage.setItem("kn_entity_ctx", JSON.stringify({ allowed_entity_ids: ["ent_ksc", "ent_kanda"] }));
    setActiveEntity("ent_ksc");
    rememberDocEntities([{ id: "wms_7", work_entity_id: "ent_kanda" }, { id: "wms_8", work_entity_id: "ent_lain" }]);
    await apiClient.post("/api/inbound/tasks/wms_7/scan-receive", {});
    expect(hdr(captured[0], "X-Entity-Id")).toBe("ent_kanda");
    await apiClient.post("/api/inbound/tasks/wms_8/scan-receive", {});
    expect(hdr(captured[1], "X-Entity-Id")).toBe("ent_ksc");   // PT di luar penugasan → tidak dipakai
    await apiClient.post("/api/inbound/tasks/wms_7/scan-receive", {}, { headers: { "X-Entity-Id": "ent_x" } });
    expect(hdr(captured[2], "X-Entity-Id")).toBe("ent_x");    // eksplisit (mis. antrean offline) dihormati
  });

  test("header X-Location-Scope ikut setiap permintaan sesuai pilihan bilah cakupan", async () => {
    setLocationScope("all");
    await apiClient.get("/api/wms/tasks");
    expect(hdr(captured[0], "X-Location-Scope")).toBe("all");
    setLocationScope("");
    await apiClient.get("/api/wms/tasks");
    expect(hdr(captured[1], "X-Location-Scope")).toBeFalsy();
  });
});

function Harness({ onReady, state }) {
  const actions = useAppActions(state);
  onReady(actions);
  return null;
}
const noop = () => {};
const baseState = () => {
  const calls = {};
  const set = (name) => (v) => { calls[name] = v; };
  return {
    calls,
    state: {
      user: null, token: "", auditFilters: {}, selectedCustomer: null, selectedAddress: "", cart: [], data: {}, selectedEntity: "all",
      setUser: set("user"), setToken: set("token"), setActiveView: noop, setNotice: set("notice"), setOnboarding: noop, setShowOnboarding: noop,
      setData: noop, setTemplates: noop, setUoms: noop, setMovements: noop, setTasks: noop, setUsers: noop, setPermissions: noop, setAuditLogs: noop,
      setSelectedCustomer: noop, setSelectedAddress: noop, setSelectedProduct: noop, setBreakdown: noop,
      setCart: noop, setLastDocument: noop, setLastLabel: noop, setPreviewHtml: noop,
      setActiveDetail: noop, setLoading: noop, setEntities: noop, setNotifications: noop, setUnreadCount: noop,
      setNotifMeta: noop, setSettings: noop, setPaymentTerms: noop, setEntityContext: set("entityContext"),
      setSelectedEntity: set("selectedEntity"), setActiveNavId: noop, setLocationChoice: set("locationChoice"),
    },
  };
};

describe("UI-39 — sesi tidak bocor antar pengguna di perangkat yang sama", () => {
  test("logout menghapus PT aktif, konteks, cakupan lokasi & status HP pengguna", async () => {
    let actions; const { state, calls } = baseState();
    await mount(<Harness state={state} onReady={(a) => { actions = a; }} />);
    ["kn_token", "kn_user", "kn_entity", "kn_entity_ctx", "kn_loc_scope", "kn_my_bin", "kn_pos_ctx", "kn_reg_bin_s1", "kn.lineFilter.wms"]
      .forEach((k) => localStorage.setItem(k, "x"));
    localStorage.setItem("kn_sidebar_collapsed", "1");
    setActiveEntity("ent_kanda"); setLocationScope("site:s1");
    rememberDocEntities([{ id: "wms_1", work_entity_id: "ent_kanda" }]);
    act(() => actions.logout());
    ["kn_token", "kn_user", "kn_entity", "kn_entity_ctx", "kn_loc_scope", "kn_my_bin", "kn_pos_ctx", "kn_reg_bin_s1", "kn.lineFilter.wms"]
      .forEach((k) => expect(localStorage.getItem(k)).toBeNull());
    expect(localStorage.getItem("kn_sidebar_collapsed")).toBe("1");   // preferensi perangkat tetap
    expect(axios.defaults.headers.common["X-Entity-Id"]).toBeUndefined();
    expect(axios.defaults.headers.common["X-Location-Scope"]).toBeUndefined();
    expect(docEntityFor("/api/wms/tasks/wms_1/scan")).toBe("");
    expect(calls.selectedEntity).toBe("all");
    expect(calls.locationChoice).toBe("");
  });

  test("login memilih PT BAWAAN akun, bukan kn_entity sisa pengguna sebelumnya", async () => {
    let actions; const { state, calls } = baseState();
    await mount(<Harness state={state} onReady={(a) => { actions = a; }} />);
    localStorage.setItem("kn_entity", "ent_kanda");   // sisa petugas Soreang
    respond = (config) => (String(config.url).includes("/auth/login") ? {
      token: "t", user: { id: "u-drv", role: "driver", name: "Sopir" }, permissions: {},
      entity_context: { home_entity_id: "ent_ksc", allowed_entity_ids: ["ent_ksc", "ent_kanda", "ent_cst"], can_switch_entity: true, entities: [] },
    } : { progress_pct: 100 });
    await act(async () => { await actions.login("driver@x", "pw"); });
    expect(localStorage.getItem("kn_entity")).toBe("ent_ksc");
    expect(calls.selectedEntity).toBe("ent_ksc");
    expect(calls.locationChoice).toBe("");
  });
});

describe("UI-23 — aplikasi HP sopir = Pengiriman saja", () => {
  test("peran driver tidak mendapat aplikasi gudang", async () => {
    const user = { id: "u-drv", role: "driver", name: "Joko Sopir", permissions: { logistics: ["view", "update"] } };
    const { host } = await mount(<MobileAppSwitch user={user} entities={[]} selectedEntity="ent_ksc" actions={{}} />);
    expect(host.querySelector('[data-testid="mobile-driver-app"]')).not.toBeNull();
    expect(host.querySelector('[data-testid="mobile-warehouse-app"]')).toBeNull();
    expect(host.querySelector('[data-testid="stub-driver-today"]')).not.toBeNull();
    expect(host.textContent).not.toMatch(/Permission ditolak/);
    const tabs = [...host.querySelectorAll('[data-testid^="mobile-tab-btn-"]')].map((b) => b.getAttribute("data-testid"));
    expect(tabs).toEqual(["mobile-tab-btn-delivery", "mobile-tab-btn-more"]);
  });
});

describe("K-B1-01 — bilah cakupan selalu terlihat", () => {
  test("menampilkan cakupan aktif + anjuran bila lokasi kerja belum diatur", async () => {
    respond = () => ({ view: { mode: "unset", label: "Semua lokasi — lokasi kerja belum diatur", choice: "" }, restricted: false,
      home_set: false, options: [{ value: "", label: "Lokasi kerja saya", kind: "home" }, { value: "all", label: "Semua lokasi", kind: "all" }] });
    const onChange = jest.fn();
    const { host } = await mount(<LocationScopeBar value="" onChange={onChange} />);
    expect(host.querySelector('[data-testid="location-scope-bar-label"]').textContent).toContain("Semua lokasi");
    expect(host.querySelector('[data-testid="location-scope-bar-unset"]')).not.toBeNull();
    await act(async () => { host.querySelector('[data-testid="location-scope-bar-trigger"]').click(); });
    await act(async () => { host.querySelector('[data-testid="location-scope-bar-opt-all"]').click(); });
    expect(onChange).toHaveBeenCalledWith("all");
  });

  test("petugas berpagar: label lokasi tugas, tanpa pilihan 'Semua lokasi'", async () => {
    respond = () => ({ view: { mode: "restricted", label: "Soreang", choice: "" }, restricted: true, home_set: true, home_label: "Soreang",
      options: [{ value: "", label: "Lokasi kerja saya", kind: "home" }, { value: "wh:w1", label: "SRG-01 · Soreang", kind: "wh" }] });
    const { host } = await mount(<LocationScopeBar value="" onChange={() => {}} />);
    expect(host.querySelector('[data-testid="location-scope-bar-label"]').textContent).toBe("Lokasi: Soreang");
    await act(async () => { host.querySelector('[data-testid="location-scope-bar-trigger"]').click(); });
    expect(host.querySelector('[data-testid="location-scope-bar-opt-all"]')).toBeNull();
  });
});

describe("UI-39 — antrean offline milik pengguna perekamnya", () => {
  test("butir pengguna lain tidak dikirim dengan token pengguna sekarang", async () => {
    Object.defineProperty(window.navigator, "onLine", { value: true, configurable: true });
    localStorage.setItem("kn_user", JSON.stringify({ id: "u-a" }));
    setActiveEntity("ent_ksc");
    enqueue({ key: "k1", method: "post", url: "/api/rfid/roll-scans", data: { code: "R1" }, label: "pindai" });
    localStorage.setItem("kn_user", JSON.stringify({ id: "u-b" }));
    const res = await syncQueue();
    expect(res.sent).toBe(0);
    expect(captured.length).toBe(0);
    expect(pending().map((x) => x.key)).toEqual(["k1"]);
    localStorage.setItem("kn_user", JSON.stringify({ id: "u-a" }));
    const res2 = await syncQueue();
    expect(res2.sent).toBe(1);
    expect(pending()).toEqual([]);
  });
});
