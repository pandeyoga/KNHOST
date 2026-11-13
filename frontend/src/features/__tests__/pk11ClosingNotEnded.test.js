// PK-11 — periode yang belum berakhir tidak bisa ditutup: pratinjau menampilkan peringatan dan tombol Tutup Buku mati;
// catatan berstatus `closing` tampil "Sedang ditutup" tanpa tombol aksi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ClosingView, { notEndedText } from "../finance/ClosingView";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true,
  askConfirm: jest.fn(async () => true),
  askReason: jest.fn(async () => null),
  askText: jest.fn(async () => null),
  askChoice: jest.fn(async () => null),
  default: {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos — yang diuji di sini logika layar, bukan komponen pilihannya.
jest.mock("../../components/KNSelect", () => (p) => <select data-testid={p["data-testid"]} value={p.value} onChange={() => {}} />);
jest.mock("../../components/PeriodUnlockCard", () => () => null);
jest.mock("../../components/OpeningCostBanner", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  await act(async () => {});
  return { host, root };
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).find((k) => url.includes(k));
    return Promise.resolve({ data: hit ? map[hit] : [] });
  });
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await act(async () => {});
  await act(async () => {});
}

const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }];
const ADMIN = { role: "admin", permissions: { accounting: ["*"] } };
const PREVIEW_BELUM = {
  can_close: false, period_ended: false, earliest_close_date: "2026-12-01", blocking_closing: null,
  suspense_warning: false, suspense_blocks_close: false, suspense_balance: 0, suspense_override_min_len: 5,
  net_income: 0, residual_net_income: 0, closing_lines: [], revenue_total: 0, expense_total: 0,
  period_label: "November 2026",
};

afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

test("notEndedText: tanggal ditulis penuh; kosong bila periode sudah berakhir", () => {
  expect(notEndedText(PREVIEW_BELUM))
    .toBe("Periode ini belum berakhir. Tutup buku baru bisa dilakukan mulai 1 Desember 2026.");
  expect(notEndedText({ ...PREVIEW_BELUM, period_ended: true })).toBe("");
  expect(notEndedText(null)).toBe("");
});

test("pratinjau periode berjalan: peringatan tampil, teks tumpang tindih tidak, tombol Tutup Buku mati", async () => {
  routeGet({ "/finance/closing/preview": PREVIEW_BELUM, "/finance/closing": [] });
  const { host } = await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={ADMIN} />);
  await click(q(host, "closing-preview-btn"));
  expect(q(host, "closing-preview-not-ended").textContent).toContain("mulai 1 Desember 2026");
  expect(q(host, "closing-preview-block")).toBeNull();
  const btn = q(host, "closing-close-btn");
  expect(btn.disabled).toBe(true);
  expect(btn.getAttribute("title")).toContain("belum berakhir");
  await click(btn);
  expect(mockPost).not.toHaveBeenCalled();
});

test("riwayat: catatan `closing` berlencana Sedang ditutup tanpa tombol aksi", async () => {
  routeGet({ "/finance/closing": [{ id: "c1", status: "closing", period_type: "month", period_key: "2026-10",
    period_label: "Oktober 2026", net_income: 0, journal_entry_number: null, stale: false }] });
  const { host } = await mount(<ClosingView selectedEntity="ent_ksc" entities={ENTS} currentUser={ADMIN} />);
  expect(q(host, "closing-in-progress-c1").textContent).toContain("Sedang ditutup");
  expect(q(host, "closing-reopen-c1")).toBeNull();
  expect(q(host, "closing-reclose-c1")).toBeNull();
});
