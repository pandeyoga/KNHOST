// AG-T5 (b) — kartu balik jurnal (ketik ulang NOMOR jurnal), kartu jurnal manual yang berakhir sebagai usulan (pintu
// jurnal menuntut dua orang), dan baris Pusat Persetujuan "Tindakan asisten menunggu orang kedua" yang membuka Tanya KN ›
// Tindakan › Menunggu orang lain (preset dari server ikut dikirim ke navigasi). Uji komponen; uji jalan peramban terpisah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import EntityScopeContext from "../../context/EntityScopeContext";
import AppNavContext, { AppNavProvider } from "../../context/AppNavContext";

const mockFetch = jest.fn();
const mockConfirm = jest.fn();
jest.mock("../tanya/tanyaApi", () => ({
  __esModule: true,
  fetchAction: (...a) => mockFetch(...a),
  confirmAction: (...a) => mockConfirm(...a),
  dismissAction: jest.fn(),
  fetchActions: jest.fn(),
  secondAction: jest.fn(),
}));
const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: jest.fn(() => Promise.resolve({ data: {} })),
    patch: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: jest.fn() }));
const mockAsk = jest.fn();
jest.mock("../../services/confirmService", () => ({
  __esModule: true, REASON_MIN_LENGTH: 5, askConfirm: (...a) => mockAsk(...a), askReason: jest.fn(), askText: jest.fn(),
  askChoice: jest.fn(), default: {},
}));
jest.mock("../approvals/MyApprovalsPanel", () => () => null);

/* eslint-disable import/first */
import { TanyaActionCard } from "../tanya/TanyaActionCard";
import ApprovalInbox from "../approvals/ApprovalInbox";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const txt = (el) => String(el?.textContent || "").replace(/ /g, " ");
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  const value = { selectedEntity: "ent_ksc", entities: ENTS, canWrite: true, writeBlockHint: "", pickEntity: () => {} };
  const nav = { role: "manager", go: jest.fn(), canOpen: () => true, openDocument: () => {} };
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

const BALIK = {
  id: "aiact_r1", type: "journal_reverse", class: "C", risk: "high", status: "pending", title: "Balik jurnal",
  retype_kind: "text", entity_id: "ent_ksc", entity_name: "Sukacita", expires_at: "2026-11-16T02:00:00+00:00",
  args: {}, editable: [], is_maker: true,
  plan: { summary: "Balik jurnal KSC/JE-00005 (Rp 100.000).", amount: 100000, confirm_text: "KSC/JE-00005",
    rows: [{ label: "Jurnal KSC/JE-00005", kind: "text", before: "Terposting", after: "Dibalik" }] },
};

test("balik jurnal: isian 'Ketik ulang nomor jurnal'; nomor huruf kecil diterima, digit saja ditolak", async () => {
  mockFetch.mockResolvedValue(BALIK);
  await mount(<TanyaActionCard proposalId="aiact_r1" />);
  expect(q("tanya-card-retype").closest("label").textContent).toContain("Ketik ulang nomor jurnal");
  await act(async () => { ketik(q("tanya-card-reason"), "salah catat setoran modal"); ketik(q("tanya-card-retype"), "00005"); });
  await flush();
  expect(q("tanya-action-confirm").disabled).toBe(true);
  expect(txt(q("tanya-action-pt-hint"))).toBe("Ketik ulang nomor jurnal persis seperti di kartu untuk menyetujui.");
  await act(async () => { ketik(q("tanya-card-retype"), "ksc/je-00005"); });
  await flush();
  expect(q("tanya-action-confirm").disabled).toBe(false);
});

test("jurnal manual yang menjadi usulan (pintu jurnal dua orang): hasil menyebut layar Jurnal", async () => {
  mockFetch.mockResolvedValue({ ...BALIK, id: "aiact_j1", type: "journal_manual", title: "Catat jurnal manual",
    retype_kind: "amount", status: "confirmed",
    result: { status_code: 202, gl_status: null, message: "Usulan jurnal menunggu persetujuan di layar Jurnal",
      document: { type: "journal_proposal", label: "Usulan jurnal manual", id: "jprop_1", number: "", link: {} } } });
  await mount(<TanyaActionCard proposalId="aiact_j1" />);
  expect(txt(q("tanya-card-success"))).toBe("Berhasil — Usulan jurnal manual");
  expect(txt(q("tanya-card-message"))).toBe("Usulan jurnal menunggu persetujuan di layar Jurnal");
});

test("Pusat Persetujuan: baris 'Tindakan asisten menunggu orang kedua' membuka Tanya KN dengan preset kotak", async () => {
  const PRESET = { tab: "actions", box: "others" };
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/approvals/backlog") ? {
    total: 1, items: [{ key: "ai_card_second", label: "Tindakan asisten menunggu orang kedua", view: "tanya-kn", count: 1,
      preset: PRESET }],
    all_items: [{ key: "ai_card_second", count: 1 }],
    oldest: [{ key: "ai_card_second", id: "aiact_c1", number: "Bayar tagihan pemasok", title: "Fina",
      queue_label: "Tindakan asisten menunggu orang kedua", view: "tanya-kn", days_waiting: 0, preset: PRESET }],
  } : [] }));
  const onNavigate = jest.fn();
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(<AppNavProvider role="manager" onNavigateTo={() => {}} onOpenDocument={() => {}}>
      <ApprovalInbox currentUser={{ role: "manager", permissions: { approval: ["view"], ai: ["view"] } }} onNavigate={onNavigate} />
    </AppNavProvider>);
  });
  await flush();
  const chip = q("approval-inbox-backlog-ai_card_second");
  expect(chip).not.toBeNull();
  expect(txt(chip)).toContain("Tindakan asisten menunggu orang kedua");
  await click(chip);
  expect(onNavigate).toHaveBeenCalled();
  const call = onNavigate.mock.calls[0];
  expect(call[1]).toBe("tanya-kn");
  expect(call[3]).toEqual({ preset: PRESET });
  await click(q("approval-inbox-other-open-aiact_c1"));
  expect(onNavigate.mock.calls.at(-1)[3]).toEqual({ preset: PRESET });
});
