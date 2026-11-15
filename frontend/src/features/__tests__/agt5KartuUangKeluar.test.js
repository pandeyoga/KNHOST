// AG-T5 (a) — kartu tindakan golongan C (uang keluar) & orang kedua di Tanya KN (uji komponen; uji jalan peramban
// terpisah): kartu `pending` yang akan menunggu orang kedua menulis kalimatnya di bawah tombol; kartu `awaiting_second`
// menampilkan "Menunggu orang kedua · disetujui {pembuat}, {tanggal jam} WIB"; orang kedua mendapat isian Alasan (wajib
// saat menolak), "Setujui dan jalankan" (pop-up menyebut nominal, PT, dan nama pembuat) dan "Tolak"; yang tidak bisa
// memutus mendapat alasan tertulis; status ikon + teks + warna; kotak awal "Menunggu orang lain"; sakelar akun tiga
// pilihan golongan ("Baca saja" · "Uang masuk" · "Uang masuk, uang keluar, dan jurnal").
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import EntityScopeContext from "../../context/EntityScopeContext";
import AppNavContext from "../../context/AppNavContext";

const mockFetch = jest.fn();
const mockConfirm = jest.fn();
const mockDismiss = jest.fn();
const mockList = jest.fn();
const mockSecond = jest.fn();
jest.mock("../tanya/tanyaApi", () => ({
  __esModule: true,
  fetchAction: (...a) => mockFetch(...a),
  confirmAction: (...a) => mockConfirm(...a),
  dismissAction: (...a) => mockDismiss(...a),
  fetchActions: (...a) => mockList(...a),
  secondAction: (...a) => mockSecond(...a),
}));
const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
const mockAsk = jest.fn();
jest.mock("../../services/confirmService", () => ({ __esModule: true, askConfirm: (...a) => mockAsk(...a) }));
jest.mock("../settings/entities/entityApi", () => ({
  publicRoles: jest.fn(), manageableRoles: jest.fn(), availableEmployees: jest.fn(), createUser: jest.fn(),
  patchUser: jest.fn(), ROLE_OPTIONS: [], errText: (e, f) => f,
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      <option value="">{p.placeholder || ""}</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});
jest.mock("../settings/entities/AccountLocationScope", () => ({ AccountLocationScope: () => null }));
jest.mock("../settings/entities/AccountRoleSummary", () => () => null);
jest.mock("../../hooks/useDomainEnums", () => () => ({ options: () => [] }));

/* eslint-disable import/first */
import { TanyaActionCard } from "../tanya/TanyaActionCard";
import { TanyaActions } from "../tanya/TanyaActions";
import AccountFormDrawer from "../settings/entities/AccountFormDrawer";
/* eslint-enable import/first */
const api = require("../settings/entities/entityApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }, { id: "ent_kanda", short_name: "Kanda Fabric" }];
const KARTU = (over = {}) => ({
  id: "aiact_c1", type: "vendor_bill_pay", class: "C", risk: "high", status: "pending", title: "Bayar tagihan pemasok",
  entity_id: "ent_ksc", entity_name: "Sukacita", user_name: "Fina", created_at: "2026-11-14T02:00:00+00:00",
  expires_at: "2026-11-15T02:00:00+00:00", args: {}, editable: [], is_maker: true, can_second: false, second_block: "",
  plan: { summary: "Bayar Rp 7.000.000 untuk tagihan VB-1 (Pemasok A).", amount: 7000000, confirm_text: "7000000",
    note: "Jurnal dibuat sistem saat disimpan.",
    rows: [{ label: "Sisa hutang VB-1", kind: "money", before: 7000000, after: 0 },
      { label: "Rekening sumber", kind: "text", before: "—", after: "BCA KSC" }] },
  ...over,
});
const MENUNGGU = (over = {}) => KARTU({
  status: "awaiting_second", reason: "pemasok minta dilunasi hari ini", first_by: { id: "u_fin", name: "Fina" },
  first_at: "2026-11-14T03:15:00+00:00", second_required: { needed: true, basis: "min_orang" }, ...over,
});

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const nb = (v) => String(v || "").replace(/\u00a0/g, " ");   // Rp 7.000.000 memakai spasi tak-putus
const txt = (el) => nb(el?.textContent);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const nav = { role: "manager", go: jest.fn(), canOpen: () => true, openDocument: () => {} };
async function mount(el, scope = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  const value = { selectedEntity: "ent_ksc", entities: ENTS, canWrite: true, writeBlockHint: "", pickEntity: () => {}, ...scope };
  await act(async () => {
    root.render(<AppNavContext.Provider value={nav}><EntityScopeContext.Provider value={value}>{el}</EntityScopeContext.Provider></AppNavContext.Provider>);
  });
  await flush();
  return host;
}
function ketik(el, v) {
  const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  set.call(el, v);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
async function click(el) { await act(async () => { el.click(); }); await flush(); }

afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  jest.clearAllMocks();
});

test("kartu pending yang akan menunggu orang kedua: kalimatnya tertulis di bawah tombol; ketik ulang nominal", async () => {
  mockFetch.mockResolvedValue(KARTU({ second_preview: true }));
  await mount(<TanyaActionCard proposalId="aiact_c1" />);
  expect(txt(q("tanya-card-second-preview"))).toBe("Kartu ini akan menunggu persetujuan orang kedua sebelum dijalankan.");
  expect(txt(q("tanya-card-plan"))).toContain("Sisa hutang VB-1");
  expect(q("tanya-card-retype").closest("label").textContent).toContain("Ketik ulang nominal");
  expect(q("tanya-action-confirm").disabled).toBe(true);
  expect(txt(q("tanya-action-pt-hint"))).toContain("Tulis alasan (minimal 10 huruf) dan ketik ulang nominal");
  mockConfirm.mockResolvedValue(MENUNGGU());
  mockAsk.mockResolvedValue(true);
  await act(async () => { ketik(q("tanya-card-reason"), "pemasok minta dilunasi hari ini"); ketik(q("tanya-card-retype"), "7.000.000"); });
  await flush();
  await click(q("tanya-action-confirm"));
  expect(nb(mockAsk.mock.calls[0][0].message)).toBe("Jalankan Bayar tagihan pemasok sebesar Rp 7.000.000 untuk Sukacita?");
  expect(mockToast.mock.calls.at(-1)[0].title).toBe("Kartu menunggu persetujuan orang kedua");
  expect(txt(q("tanya-card-first"))).toMatch(/^Menunggu orang kedua · disetujui Fina, 14 Nov 2026,? 10\.15 WIB$/);
  expect(txt(q("tanya-action-pill"))).toBe("Menunggu orang kedua");
  expect(q("tanya-action-pill").querySelector("svg")).not.toBeNull();
});

test("tanpa aturan dua orang: tidak ada kalimat menunggu orang kedua", async () => {
  mockFetch.mockResolvedValue(KARTU({ second_preview: false }));
  await mount(<TanyaActionCard proposalId="aiact_c1" />);
  expect(q("tanya-card-second-preview")).toBeNull();
});

test("orang kedua: alasan pembuat, Tolak butuh alasan tertulis, Setujui → pop-up nominal + PT + pembuat", async () => {
  mockFetch.mockResolvedValue(MENUNGGU({ is_maker: false, can_second: true }));
  await mount(<TanyaActionCard proposalId="aiact_c1" />);
  expect(txt(q("tanya-card-maker-reason"))).toBe("Alasan pembuat: pemasok minta dilunasi hari ini");
  expect(q("tanya-card-second-reject").disabled).toBe(true);
  expect(txt(q("tanya-card-second-hint"))).toBe("Tulis alasan (minimal 10 huruf) untuk menolak.");
  expect(q("tanya-action-confirm")).toBeNull();
  mockAsk.mockResolvedValue(true);
  mockSecond.mockResolvedValue(MENUNGGU({ status: "confirmed", second_by: { id: "u_mgr", name: "Mira" },
    second_at: "2026-11-14T04:00:00+00:00", result: { status_code: 200, gl_status: "posted",
      document: { type: "vendor_bill", label: "Tagihan Pemasok", id: "vb_1", number: "VB-1", link: {} } } }));
  await click(q("tanya-card-second-approve"));
  expect(mockAsk.mock.calls[0][0]).toMatchObject({ confirmLabel: "Ya, jalankan", cancelLabel: "Batal" });
  expect(nb(mockAsk.mock.calls[0][0].message))
    .toBe("Jalankan Bayar tagihan pemasok sebesar Rp 7.000.000 untuk Sukacita atas permintaan Fina?");
  expect(mockSecond).toHaveBeenCalledWith("aiact_c1", "approve", "");
  expect(txt(q("tanya-card-success"))).toBe("Berhasil — Tagihan Pemasok VB-1");
  expect(txt(q("tanya-card-first"))).toContain("orang kedua Mira");
});

test("orang kedua menolak dengan alasan", async () => {
  mockFetch.mockResolvedValue(MENUNGGU({ is_maker: false, can_second: true }));
  mockSecond.mockResolvedValue(MENUNGGU({ status: "dismissed" }));
  await mount(<TanyaActionCard proposalId="aiact_c1" />);
  await act(async () => { ketik(q("tanya-card-second-reason"), "faktur belum diterima"); });
  await flush();
  expect(q("tanya-card-second-reject").disabled).toBe(false);
  await click(q("tanya-card-second-reject"));
  expect(mockSecond).toHaveBeenCalledWith("aiact_c1", "reject", "faktur belum diterima");
  expect(txt(q("tanya-card-result"))).toBe("Diabaikan");
});

test("pembuat & pengguna tanpa wewenang: tanpa tombol putus, alasan tertulis; pembuat bisa menarik kartu", async () => {
  mockFetch.mockResolvedValue(MENUNGGU({ is_maker: true, can_second: false,
    second_block: "Tindakan uang keluar dan jurnal lewat asisten harus diputuskan orang lain: Anda yang mengajukannya." }));
  await mount(<TanyaActionCard proposalId="aiact_c1" />);
  expect(q("tanya-card-second-approve")).toBeNull();
  expect(txt(q("tanya-card-second-block"))).toBe("Kartu ini dijalankan sesudah orang lain yang berwenang menyetujuinya.");
  expect(q("tanya-action-dismiss")).not.toBeNull();
  act(() => roots.forEach((r) => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  mockFetch.mockResolvedValue(MENUNGGU({ is_maker: false, can_second: false,
    second_block: "Anda belum punya akses untuk membayar Tagihan Pemasok. Minta Admin menambahkan akses 'Hutang'." }));
  await mount(<TanyaActionCard proposalId="aiact_c1" />);
  expect(txt(q("tanya-card-second-block"))).toContain("Anda belum punya akses untuk membayar Tagihan Pemasok.");
  expect(q("tanya-action-dismiss")).toBeNull();
});

test("tab Tindakan dibuka di kotak 'Menunggu orang lain'; kolom Berlaku sampai terisi untuk kartu menunggu", async () => {
  mockList.mockResolvedValue({ items: [MENUNGGU({ is_maker: false })], total: 1, page: 1, page_size: 20 });
  await mount(<TanyaActions initialBox="others" />);
  expect(mockList.mock.calls[0][0]).toBe("others");
  const row = q("tanya-actions-row-aiact_c1");
  expect(row.querySelectorAll("td")[4].textContent).toContain("15 Nov 2026");
  expect(txt(q("tanya-actions-pill-aiact_c1"))).toBe("Menunggu orang kedua");
});

const USER = { id: "u1", name: "Rina", email: "r@x.id", role: "finance", home_entity_id: "ent_ksc", allowed_entity_ids: ["ent_ksc"],
  ai_finance: { enabled: true, classes: ["B"] } };
async function drawer(props) {
  api.publicRoles.mockResolvedValue([{ id: "finance", label: "Finance", custom: false, cross_entity: false }]);
  api.manageableRoles.mockResolvedValue({ all: true });
  api.availableEmployees.mockResolvedValue([]);
  api.patchUser.mockResolvedValue({ name: "Rina" });
  await mount(<AccountFormDrawer entities={[{ id: "ent_ksc", legal_name: "KSC" }]} onClose={() => {}} onSaved={() => {}} {...props} />);
}

test("Akun & Akses: tiga pilihan golongan; memilih uang keluar dan jurnal mengirim classes B + C", async () => {
  await drawer({ user: USER, canConfigureAi: true });
  const box = q("account-form-ai-level");
  expect([...box.querySelectorAll("label")].map((l) => l.textContent.trim()))
    .toEqual(["Baca saja", "Uang masuk", "Uang masuk, uang keluar, dan jurnal"]);
  expect(q("account-form-ai-level-B").checked).toBe(true);
  await click(q("account-form-ai-level-C"));
  await click(q("account-form-submit"));
  expect(api.patchUser.mock.calls[0][1].ai_finance).toEqual({ classes: ["B", "C"] });
});

test("Akun & Akses: tanpa ai.configure pilihan golongan hanya-baca", async () => {
  await drawer({ user: { ...USER, ai_finance: { enabled: true, classes: ["B", "C"] } }, canConfigureAi: false });
  expect(q("account-form-ai-level").disabled).toBe(true);
  expect(q("account-form-ai-level-C").checked).toBe(true);
  expect(q("account-form-ai-finance-readonly").textContent).toContain("Hanya-baca");
});
