// AG-T2 — Asisten Keuangan di Tanya KN (uji komponen; uji jalan peramban U18 terpisah):
// pilihan Mode hanya bila `finance_enabled`; banner "Menjawab untuk: {PT}" / "Semua PT — angka gabungan belum
// dieliminasi"; jawaban keuangan: bagian Sumber "{judul} · {PT} · {periode}" + catatan + tombol "Buka di layar"; lencana
// pemeriksa angka (ikon + teks + warna); permintaan mode Keuangan mengirim `mode`; sakelar akun "Asisten Keuangan"
// hanya-baca tanpa `ai.configure` (alasan tertulis) dan hanya dikirim bila berubah.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { AppNavProvider } from "../../context/AppNavContext";

const mockAskChat = jest.fn();
jest.mock("../tanya/tanyaApi", () => ({
  __esModule: true,
  askChat: (...a) => mockAskChat(...a),
  fetchResult: () => Promise.resolve(null),
  fetchSession: () => Promise.resolve({ turns: [] }),
  downloadAnswerXlsx: () => Promise.resolve(),
  chatErrorText: () => "galat",
}));
jest.mock("../../components/ui/button", () => ({ __esModule: true, Button: ({ children, ...p }) => <button type="button" {...p}>{children}</button> }));
jest.mock("../tanya/TanyaChart", () => ({ TanyaChart: () => null }));
jest.mock("../tanya/TanyaFeedback", () => ({ TanyaFeedback: () => null }));
jest.mock("../tanya/TanyaNarrative", () => ({ TanyaNarrative: () => null }));
jest.mock("../tanya/TanyaActionCard", () => ({ TanyaActionCard: () => null }));
jest.mock("../tanya/TanyaMarkdown", () => ({ TanyaMarkdown: ({ text }) => <p data-testid="md">{text}</p> }));
const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
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
jest.mock("../../services/confirmService", () => ({ askConfirm: () => Promise.resolve(true) }));

/* eslint-disable import/first */
import { TanyaChatBox } from "../tanya/TanyaChatBox";
import { TanyaAnswer } from "../tanya/TanyaAnswer";
import { useTanyaChat } from "../tanya/useTanyaChat";
import AccountFormDrawer from "../settings/entities/AccountFormDrawer";
/* eslint-enable import/first */
const api = require("../settings/entities/entityApi");

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
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
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  jest.clearAllMocks();
});

const ST = (on) => ({ chat_enabled: true, finance_enabled: on });

test("kotak tanya: pilihan Mode hanya tampil bila Asisten Keuangan menyala untuk akun ini", async () => {
  await mount(<TanyaChatBox status={ST(false)} onAsk={() => {}} mode="umum" onMode={() => {}} financeScope={{ label: "PT Kain Suka Cita" }} />);
  expect(q("tanya-mode-bar")).toBeNull();
  roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";
  const onMode = jest.fn();
  await mount(<TanyaChatBox status={ST(true)} onAsk={() => {}} mode="umum" onMode={onMode} financeScope={{ label: "PT Kain Suka Cita" }} />);
  expect(q("tanya-mode-umum").textContent).toBe("Umum");
  expect(q("tanya-mode-keuangan").textContent).toBe("Keuangan");
  expect(q("tanya-mode-umum").getAttribute("aria-checked")).toBe("true");
  expect(q("tanya-finance-scope")).toBeNull();
  await click(q("tanya-mode-keuangan"));
  expect(onMode).toHaveBeenCalledWith("keuangan");
});

test("mode Keuangan: banner menyebut PT; mode gabungan menyebut belum dieliminasi", async () => {
  await mount(<TanyaChatBox status={ST(true)} onAsk={() => {}} mode="keuangan" onMode={() => {}}
    financeScope={{ combined: false, label: "PT Kain Suka Cita" }} />);
  expect(q("tanya-finance-scope").textContent).toBe("Menjawab untuk: PT Kain Suka Cita");
  expect(q("tanya-chat-status").textContent).toBe("Angka diperiksa terhadap data sebelum jawaban ditampilkan.");
  roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";
  await mount(<TanyaChatBox status={ST(true)} onAsk={() => {}} mode="keuangan" onMode={() => {}}
    financeScope={{ combined: true, label: "" }} />);
  expect(q("tanya-finance-scope").textContent).toBe("Semua PT — angka gabungan belum dieliminasi");
  expect(q("tanya-finance-scope").className).toContain("combined");
});

const SRC = [{ result_id: "r_1", title: "Laba rugi", entity_label: "PT Kain Suka Cita", period_label: "Bulan ini (1 Nov 2026 – 14 Nov 2026)",
  notes: ["Periode 1 Nov 2026 – 14 Nov 2026", "Tanpa jurnal penutup"], link: { view: "financial-statements", nav_id: "fin-reports", tab: "pl" } }];
const JAWAB = (ver, sources = SRC) => ({ kind: "chat", mode: "keuangan", question: "berapa laba bulan ini", text: "Laba Rp 300.000",
  verification: ver, resultIds: [], sources });

test("jawaban keuangan: Sumber berisi judul · PT · periode, catatan, dan tombol Buka di layar ke laporannya", async () => {
  const nav = jest.fn();
  await mount(<AppNavProvider role="admin" onNavigateTo={nav}>
    <TanyaAnswer answer={JAWAB({ ok: true, checked: 1, unmatched_count: 0 })} entityLabel="Sukacita" onFollowup={() => {}} />
  </AppNavProvider>);
  expect(q("tanya-source-title-0").textContent).toBe("Laba rugi · PT Kain Suka Cita · Bulan ini (1 Nov 2026 – 14 Nov 2026)");
  expect(q("tanya-source-notes-0").textContent).toContain("Tanpa jurnal penutup");
  expect(q("tanya-finance-verify").textContent).toBe("Angka diperiksa: semua cocok dengan data");
  expect(q("tanya-finance-verify").querySelector("svg")).not.toBeNull();   // ikon + teks + warna
  expect(q("tanya-verification")).toBeNull();
  expect(q("tanya-source-open-0").textContent.trim()).toBe("Buka di layar");
  await click(q("tanya-source-open-0"));
  expect(nav).toHaveBeenCalledWith("financial-statements", { preset: { tab: "pl" }, tab: undefined, navId: "fin-reports" });
});

test("jawaban keuangan tak terpastikan: lencana 'Angka tidak bisa dipastikan', tanpa daftar angka; tanpa tombol bila layar tak terbuka", async () => {
  await mount(<AppNavProvider role="" onNavigateTo={() => {}}>
    <TanyaAnswer answer={{ ...JAWAB({ ok: false, checked: 1, unmatched_count: 1, replaced: true }),
      text: "Saya tidak bisa memastikan angka untuk pertanyaan ini. Data yang berhasil diambil ada di tabel di bawah." }}
    entityLabel="Sukacita" onFollowup={() => {}} />
  </AppNavProvider>);
  expect(q("tanya-finance-verify").textContent).toBe("Angka tidak bisa dipastikan");
  expect(q("tanya-source-open-0")).toBeNull();
  expect(document.body.textContent).not.toMatch(/undefined|unmatched/);
});

function Pemakai({ onReady }) {
  const chat = useTanyaChat(() => {});
  onReady(chat);
  return <div data-testid="n">{chat.thread.length}</div>;
}

test("permintaan mode Keuangan mengirim mode; jawaban membawa sumber dari server", async () => {
  let chat;
  mockAskChat.mockImplementation(async (payload, onEvent) => {
    onEvent({ type: "status", text: "Memeriksa angka…" });
    onEvent({ type: "done", mode: "keuangan", text: "Laba Rp 300.000", verification: { ok: true }, sources: SRC, result_ids: ["r_1"], session_id: "s1" });
  });
  await mount(<Pemakai onReady={(c) => { chat = c; }} />);
  await act(async () => { await chat.ask("berapa laba bulan ini", null, "keuangan"); });
  await flush();
  expect(mockAskChat.mock.calls[0][0]).toEqual({ question: "berapa laba bulan ini", session_id: null, mode: "keuangan" });
  const a = chat.thread[0].answer;
  expect(a.mode).toBe("keuangan");
  expect(a.sources).toEqual(SRC);
  mockAskChat.mockClear();
  await act(async () => { await chat.ask("halo"); });
  expect(mockAskChat.mock.calls[0][0]).not.toHaveProperty("mode");
});

const USER = { id: "u1", name: "Rina", email: "r@x.id", role: "finance", home_entity_id: "ent_ksc", allowed_entity_ids: ["ent_ksc"] };
async function drawer(props) {
  api.publicRoles.mockResolvedValue([{ id: "finance", label: "Finance", custom: false, cross_entity: false }]);
  api.manageableRoles.mockResolvedValue({ all: true });
  api.availableEmployees.mockResolvedValue([]);
  api.patchUser.mockResolvedValue({ name: "Rina" });
  await mount(<AccountFormDrawer entities={[{ id: "ent_ksc", legal_name: "KSC" }]} onClose={() => {}} onSaved={() => {}} {...props} />);
}

test("Akun & Akses: sakelar Asisten Keuangan hanya-baca tanpa ai.configure, alasannya tertulis", async () => {
  await drawer({ user: USER, canConfigureAi: false });
  const sw = q("account-form-ai-finance-switch");
  expect(sw.disabled).toBe(true);
  expect(sw.checked).toBe(false);
  expect(q("account-form-ai-finance").textContent).toContain("Mati = akun ini tidak bisa bertanya soal keuangan lewat Tanya KN.");
  expect(q("account-form-ai-finance-readonly").textContent).toContain("Hanya-baca");
  await click(q("account-form-submit"));
  expect(api.patchUser.mock.calls[0][1]).not.toHaveProperty("ai_finance");
});

test("Akun & Akses: pemegang ai.configure menyalakan sakelar → dikirim {ai_finance: {enabled: true}}", async () => {
  await drawer({ user: USER, canConfigureAi: true });
  expect(q("account-form-ai-finance-readonly")).toBeNull();
  await click(q("account-form-ai-finance-switch"));
  expect(q("account-form-ai-finance-state").textContent).toBe("Menyala");
  await click(q("account-form-submit"));
  expect(api.patchUser.mock.calls[0][1].ai_finance).toEqual({ enabled: true });
});

test("Akun & Akses: sakelar tidak tampil di formulir akun baru (akun belum ada)", async () => {
  await drawer({ user: null, canConfigureAi: true });
  expect(q("account-form-ai-finance")).toBeNull();
});
