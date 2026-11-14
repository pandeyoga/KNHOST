// KP-T8 — layar rahasia & perangkat (uji komponen; U16 uji jalan peramban terpisah):
//  · Mesin absen: tanpa "Salin token perangkat"; baris "Token berakhiran …"; tanda "Disarankan ganti"; Ganti token →
//    konfirmasi → pop-up "Token perangkat" (tampil sekali, tombol Salin); buat perangkat → pop-up yang sama.
//  · Integrasi: sakelar & model pengenal gambar dibuang (tautan ke Pusat Pengaturan); peringatan kunci enkripsi; kartu
//    WhatsApp (token hanya-tulis, "Dipakai oleh", kotak dua koneksi berbeda + alasan wajib).
//  · Penjadwal & Pusat Dokumen: setelah koneksi tunggal ada, isian koneksi → ringkasan + tautan; simpan tanpa field koneksi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
const mockPut = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), put: (...a) => mockPut(...a), post: (...a) => mockPost(...a),
    patch: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("@/components/KNTimePicker", () => () => <input data-testid="stub-time" />);
jest.mock("@/components/ui/switch", () => ({
  Switch: (p) => <input type="checkbox" data-testid={p["data-testid"]} checked={!!p.checked}
    onChange={(e) => p.onCheckedChange && p.onCheckedChange(e.target.checked)} />,
}));

/* eslint-disable import/first */
import AttendanceSetupView from "../hr/AttendanceSetupView";
import IntegrationsPanel from "../admin/IntegrationsPanel";
import WhatsAppConnectionPanel from "../admin/WhatsAppConnectionPanel";
import WhatsAppSettings from "../documents/WhatsAppSettings";
import { WaSettingsPanel } from "../admin/scheduler/SchedulerWa";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = () => document.body.textContent;
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const key = Object.keys(map).find((k) => url.endsWith(k));
    return key ? Promise.resolve({ data: map[key] }) : Promise.resolve({ data: {} });
  });
}

beforeEach(() => { mockGet.mockReset(); mockPut.mockReset(); mockPost.mockReset(); });
afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
});

const ADMIN = { role: "admin", permissions: { hr: ["view", "manage_attendance"], integration: ["manage"] } };
const DEVICES = [
  { id: "dev_a", name: "Mesin A", code: "", location: "", status: "active", entity_id: "ent_ksc", last_sync: "",
    device_token_hint: "9f3c", token_rotation_required: false },
  { id: "dev_lama", name: "Mesin Lama", code: "", location: "", status: "active", entity_id: "ent_ksc", last_sync: "",
    device_token_hint: "c123", token_rotation_required: true },
];

describe("KP-T8 mesin absen", () => {
  test("baris tanpa token; Ganti token → konfirmasi → token tampil sekali", async () => {
    routeGet({ "/hr/devices": DEVICES });
    mockPost.mockResolvedValue({ data: { device_id: "dev_a", device_token: "at_0123456789abcdef0123456789abcdef",
      device_token_hint: "cdef", shown_once: true } });
    await mount(<AttendanceSetupView currentUser={ADMIN} selectedEntity="ent_ksc" only="device" />);
    expect(teks()).not.toContain("Salin token perangkat");
    expect(q("device-token-dev_a").textContent).toContain("Token berakhiran …9f3c");
    expect(q("device-token-warn-dev_a")).toBeNull();
    expect(q("device-token-warn-dev_lama").textContent).toContain("Disarankan ganti — token lama pernah tampil di layar.");
    await click(q("device-rotate-dev_a"));
    expect(q("device-rotate-modal").textContent).toContain(
      "Ganti token Mesin A?");
    expect(q("device-rotate-modal-message").textContent).toBe(
      "Mesin yang masih memakai token lama berhenti mengirim absen sampai diisi token baru.");
    expect(mockPost).not.toHaveBeenCalled();
    await click(q("device-rotate-modal-confirm"));
    expect(mockPost).toHaveBeenCalledWith("/api/hr/devices/dev_a/rotate-token");
    expect(q("device-token-modal-title").textContent).toBe("Token perangkat");
    expect(q("device-token-value").textContent).toBe("at_0123456789abcdef0123456789abcdef");
    expect(q("device-token-copy")).not.toBeNull();
    expect(q("device-token-modal").textContent).toContain("Token hanya ditampilkan sekali. Simpan sekarang.");
    await click(q("device-token-done"));
    expect(q("device-token-modal")).toBeNull();
  });

  test("lihat saja: tanpa tombol Ganti token", async () => {
    routeGet({ "/hr/devices": DEVICES });
    await mount(<AttendanceSetupView currentUser={{ role: "x", permissions: { hr: ["view"] } }} selectedEntity="ent_ksc" only="device" />);
    expect(q("device-token-dev_a")).not.toBeNull();
    expect(q("device-rotate-dev_a")).toBeNull();
  });

  test("buat perangkat → pop-up token", async () => {
    routeGet({ "/hr/devices": [] });
    mockPost.mockResolvedValue({ data: { id: "dev_b", name: "Mesin B", device_token: "at_ffffffffffffffffffffffffffffffff",
      shown_once: true } });
    await mount(<AttendanceSetupView currentUser={ADMIN} selectedEntity="ent_ksc" only="device" />);
    await click(q("setup-create-button"));
    await type(q("setup-name"), "Mesin B");
    await click(q("setup-save"));
    expect(q("device-token-value").textContent).toBe("at_ffffffffffffffffffffffffffffffff");
  });
});

describe("KP-T8 integrasi", () => {
  test("kartu penyedia: tanpa sakelar & model; tautan ke Pusat Pengaturan; peringatan kunci enkripsi", async () => {
    routeGet({ "/admin/integrations": { secrets_key_configured: false,
      anthropic: { has_key: true, enabled: true, model: "m-1", models_available: ["m-1"] } } });
    await mount(<IntegrationsPanel canManage />);
    expect(q("integrations-model")).toBeNull();
    expect(q("integrations-enabled")).toBeNull();
    expect(q("integrations-registry-link-readonly") || q("integrations-registry-link")).not.toBeNull();
    expect(q("integrations-secrets-warning").textContent).toContain(
      "Kunci enkripsi server belum dipasang. Rahasia yang disimpan sekarang belum terenkripsi.");
    await type(q("integrations-apikey"), "kunci-palsu");
    mockPut.mockResolvedValue({ data: { secrets_key_configured: false, anthropic: { has_key: true } } });
    await click(q("integrations-save"));
    expect(mockPut).toHaveBeenCalledWith("/api/admin/integrations", { anthropic_api_key: "kunci-palsu" });
  });

  test("kartu WhatsApp: token hanya-tulis, dipakai oleh, dua koneksi berbeda + alasan wajib", async () => {
    const r = (provider, label, extra = {}) => ({ provider, provider_label: label, phone_number_id: "", sender_label: "",
      has_access_token: false, has_fonnte_token: false, ...extra });
    routeGet({ "/admin/integrations/whatsapp": {
      ...r("simulated", "Simulasi"), configured: false, used_by: { alerts: false, documents: false },
      conflict: { alerts: r("fonnte", "Fonnte", { has_fonnte_token: true }),
        documents: r("meta_cloud", "Meta WhatsApp Cloud", { phone_number_id: "1098", has_access_token: true }) },
      secrets_key_configured: true, secret_error: "" } });
    await mount(<WhatsAppConnectionPanel canManage />);
    expect(q("wa-connection-conflict").textContent).toContain("Ada dua koneksi WhatsApp berbeda");
    expect(q("wa-conflict-documents").textContent).toContain("nomor pengirim 1098");
    expect(teks()).not.toContain("Dipakai oleh: Pengingat · Kirim dokumen");
    await click(q("wa-adopt-alerts"));
    expect(q("wa-adopt-modal-confirm").disabled).toBe(true);        // alasan wajib
    await type(q("wa-adopt-modal-reason"), "Satu nomor");
    mockPost.mockResolvedValue({ data: { ...r("fonnte", "Fonnte", { has_fonnte_token: true }), configured: true,
      used_by: { alerts: true, documents: true }, conflict: null } });
    await click(q("wa-adopt-modal-confirm"));
    expect(mockPost).toHaveBeenCalledWith("/api/admin/integrations/whatsapp/adopt", { from: "alerts", reason: "Satu nomor" });
    expect(q("wa-connection-conflict")).toBeNull();
    expect(q("wa-connection-used-by").textContent).toBe("Dipakai oleh: Pengingat · Kirim dokumen");
    expect(q("wa-connection-token").value).toBe("");
    expect(q("wa-connection-token-state").textContent).toContain("Sudah terisi");
    mockPut.mockResolvedValue({ data: { ...r("fonnte", "Fonnte", { has_fonnte_token: true }), used_by: { alerts: true, documents: true } } });
    await type(q("wa-connection-label"), "KN Pusat");
    await click(q("wa-connection-save"));
    const [, body] = mockPut.mock.calls[0];
    expect(body.provider).toBe("fonnte");
    expect(body.sender_label).toBe("KN Pusat");
    expect("fonnte_token" in body || "access_token" in body).toBe(false);   // token kosong = tidak diubah
  });
});

describe("KP-T8 pemakai lama setelah koneksi tunggal", () => {
  test("Pusat Dokumen: ringkasan + tautan; simpan hanya isian pemakaian", async () => {
    routeGet({ "/deliveries/whatsapp/settings": { provider: "fonnte", simulate: false, enabled: true, has_token: true,
      sender_label: "KN", connection_managed: true, connection: { provider_label: "Fonnte" } },
      "/pdf/doc-types": [], "/deliveries/whatsapp/rules": { rules: [] } });
    mockPut.mockResolvedValue({ data: { provider: "fonnte", simulate: true, enabled: true, connection_managed: true } });
    await mount(<WhatsAppSettings open onClose={() => {}} />);
    expect(q("wa-set-connection-managed").textContent).toContain("Fonnte");
    expect(q("wa-set-provider")).toBeNull();
    expect(q("wa-set-token")).toBeNull();
    await click(q("wa-set-save"));
    expect(mockPut).toHaveBeenCalledWith("/api/deliveries/whatsapp/settings", { simulate: false, enabled: true });
  });

  test("Penjadwal: ringkasan + tautan; simpan tanpa penyedia", async () => {
    const onSave = jest.fn();
    await mount(<WaSettingsPanel perms={{ configure: true }} saving={false} onSave={onSave} onTest={() => {}} testing={false}
      wa={{ enabled: true, provider: "fonnte", connection_managed: true, has_fonnte_token: true,
        connection: { provider: "fonnte", provider_label: "Fonnte", has_fonnte_token: true } }} />);
    expect(q("wa-provider-select")).toBeNull();
    expect(q("wa-fonnte-token-input")).toBeNull();
    expect(q("wa-clear-tokens")).toBeNull();
    expect(q("wa-connection-managed").textContent).toContain("Fonnte");
    await click(q("wa-save-button"));
    const payload = onSave.mock.calls[0][0];
    expect(payload.provider).toBeUndefined();
    expect(payload.enabled).toBe(true);
  });
});
