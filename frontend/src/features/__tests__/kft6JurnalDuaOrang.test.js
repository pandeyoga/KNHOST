// KF-T6 (GL-06) — layar jurnal manual & tutup buku dengan aturan dua orang.
//  · Buku Besar › Jurnal: pita "{n} jurnal manual menunggu orang kedua"; daftar usulan; Setujui = konfirmasi nominal + PT
//    lalu satu POST ber-Idempotency-Key; Tolak = alasan wajib.
//  · Tutup Buku: periode ber-`reopen_request` menampilkan "Menunggu orang kedua — diajukan {nama}"; jawaban 202 reopen
//    menampilkan pemberitahuan pengajuan (bukan "dibuka kembali").
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});

// eslint-disable-next-line import/first
import JournalProposalsPanel, { JournalProposalBanner } from "../finance/JournalProposalsPanel";
// eslint-disable-next-line import/first
import ClosingView from "../finance/ClosingView";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
const PROP = {
  id: "jprop_1", entity_id: "ent_ksc", total_debit: 1000000, status: "pending", proposed_by: "Rina",
  proposed_at: "2026-11-10T03:00:00+00:00",
  payload: { date: "2026-11-10", description: "Setoran modal", lines: [] },
};
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<>{el}<ConfirmHost /></>); });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value").set;
  await act(async () => { setter.call(el, value); el.dispatchEvent(new Event("input", { bubbles: true })); });
}
afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

test("pita menyebut jumlah usulan yang menunggu; kosong = tidak tampil", async () => {
  mockGet.mockResolvedValueOnce({ data: { items: [PROP], total: 3 } });
  const onOpen = jest.fn();
  await mount(<JournalProposalBanner refreshKey={0} onOpen={onOpen} />);
  expect(mockGet.mock.calls[0][0]).toBe("/api/gl/journal-proposals");
  expect(q("gl-proposal-banner").textContent).toContain("3 jurnal manual menunggu orang kedua");
  await click(q("gl-proposal-banner-open"));
  expect(onOpen).toHaveBeenCalled();
});

test("Setujui: dialog menyebut nominal & PT; Batal = 0 POST; lanjut = 1 POST ber-Idempotency-Key", async () => {
  mockGet.mockResolvedValue({ data: { items: [PROP], total: 1, page: 1, page_size: 20, has_more: false } });
  mockPost.mockResolvedValue({ data: { status: "posted", journal_number: "KSC/JE-00009" } });
  await mount(<JournalProposalsPanel refreshKey={0} entities={ENTS} />);
  expect(q("gl-proposal-row-jprop_1").textContent).toContain("Setoran modal");
  await click(q("gl-proposal-approve-jprop_1"));
  const msg = q("jprop-approve-confirm-message");
  expect([...msg.querySelectorAll("strong")].map((s) => s.textContent)).toEqual(["Rp 1.000.000", "PT Kain Suka Cita"]);
  expect(msg.textContent).not.toContain("ent_ksc");
  await click(q("jprop-approve-confirm-cancel"));
  expect(mockPost).not.toHaveBeenCalled();
  await click(q("gl-proposal-approve-jprop_1"));
  await click(q("jprop-approve-confirm-confirm"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/gl/journal-proposals/jprop_1/approve");
  expect(body).toBeUndefined();
  expect(cfg.headers["Idempotency-Key"]).toBeTruthy();
});

test("Tolak: alasan wajib, dikirim di body", async () => {
  mockGet.mockResolvedValue({ data: { items: [PROP], total: 1, page: 1, page_size: 20, has_more: false } });
  mockPost.mockResolvedValue({ data: { status: "rejected" } });
  await mount(<JournalProposalsPanel refreshKey={0} entities={ENTS} />);
  await click(q("gl-proposal-reject-jprop_1"));
  expect(q("jprop-reject-confirm-confirm").disabled).toBe(true);
  await type(q("jprop-reject-confirm-reason"), "Akun salah pilih");
  await click(q("jprop-reject-confirm-confirm"));
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/api/gl/journal-proposals/jprop_1/reject");
  expect(mockPost.mock.calls[0][1]).toEqual({ reason: "Akun salah pilih" });
});

test("Tutup Buku: periode ber-pengajuan menampilkan 'Menunggu orang kedua'; reopen 202 = pemberitahuan pengajuan", async () => {
  const rec = { id: "pc1", entity_id: "ent_ksc", period_type: "month", period_key: "2026-06", period_label: "Juni 2026",
    status: "closed", net_income: 0, journal_entry_number: "", closed_by: "Budi", closed_at: "2026-07-01T00:00:00Z",
    reopen_request: { by_id: "u1", by: "Budi Santoso", at: "2026-07-02T00:00:00Z" } };
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/finance/closing") ? [rec] : {} }));
  mockPost.mockResolvedValue({ status: 202, data: { status: "menunggu_orang_kedua", requested_by: "Budi Santoso" } });
  // PR-T7 — buka kembali = accounting.manage + accounting.reopen (izin bawaan Admin), bukan nama peran.
  const admin = { role: "admin", permissions: { accounting: ["view", "manage", "reopen"] } };
  await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={admin} />);
  expect(q("closing-reopen-pending-pc1").textContent).toBe("Menunggu orang kedua — diajukan Budi Santoso");
  await click(q("closing-reopen-pc1"));
  const confirm = document.body.querySelector(".modal-overlay [data-testid$='-confirm']");
  await click(confirm);
  expect(mockPost).toHaveBeenCalledWith("/api/finance/closing/pc1/reopen");
  expect(document.body.textContent).toContain("Pengajuan buka kembali Juni 2026 tercatat — menunggu orang kedua");
});
