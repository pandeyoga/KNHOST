// Rekonsiliasi Bank — modal Cocokkan, mode PECAH (uji rekonsiliasi R4, 18 Nov 2026): kandidat diminta dengan
// `mode=split`; kombinasi yang pas menutup transfer (`combos`) tampil dan "Isi alokasi" mengisi nominalnya; Simpan
// pemecahan mengirim alokasi itu ke match-split.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ReconMatchModal from "../ReconMatchModal";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a) },
  API: "/api",
}));
jest.mock("../../../../components/FormModal", () => ({ title, footer, children, testId }) => (
  <div data-testid={testId}><h2>{title}</h2>{children}{footer}</div>
));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
const q = (host, tid) => host.querySelector(`[data-testid="${tid}"]`);
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

const LINE = { id: "l4", amount: 3722262, direction: "in", stmt_date: "2026-11-18", description: "TRSF … DUA NOTA" };
const KAND = (id, number, sisa, score, label) => ({ id, number, amount: sisa, outstanding: sisa, txn_date: "2026-11-18",
  description: "Penerimaan", score, explain: [{ label, points: 40 }] });

beforeEach(() => {
  mockGet.mockReset(); mockPost.mockReset();
  mockGet.mockImplementation((url, cfg) => Promise.resolve({ data: cfg.params.mode === "split" ? {
    auto_min: 80, suggest_min: 60, mode: "split",
    candidates: [KAND("ka", "KSC/CASH-00019", 2262062, 75, "Bersama KSC/CASH-00020 pas menutup nominal transfer"),
      KAND("kb", "KSC/CASH-00020", 1460200, 75, "Bersama KSC/CASH-00019 pas menutup nominal transfer")],
    combos: [{ txn_ids: ["ka", "kb"], numbers: ["KSC/CASH-00019", "KSC/CASH-00020"], amounts: [2262062, 1460200],
      total: 3722262 }],
  } : { auto_min: 80, suggest_min: 60, mode: "single", candidates: [], combos: [] } }));
});

test("mode Pecah: kandidat split, kombinasi pas mengisi alokasi, simpan mengirim match-split", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const done = jest.fn();
  await act(async () => { createRoot(host).render(<ReconMatchModal line={LINE} onClose={() => {}} onDone={done} />); });
  await flush();
  expect(mockGet.mock.calls[0][1].params).toEqual({ limit: 25, mode: "single" });
  expect(q(host, "recon-cand-empty").textContent).toContain("Pecah ke beberapa transaksi");

  await act(async () => { q(host, "recon-mode-split").click(); });
  await flush();
  expect(mockGet.mock.calls.at(-1)[1].params).toEqual({ limit: 25, mode: "split" });
  expect(q(host, "recon-split-combo-0").textContent).toContain("KSC/CASH-00019");
  expect(q(host, "recon-split-submit").disabled).toBe(true);           // belum ada alokasi

  await act(async () => { q(host, "recon-split-combo-fill-0").click(); });
  expect(q(host, "recon-alloc-ka").value).toBe("2262062");
  expect(q(host, "recon-alloc-kb").value).toBe("1460200");
  expect(q(host, "recon-split-info").textContent).toMatch(/Rp\s*0/);   // sisa belum dialokasikan nol

  mockPost.mockResolvedValueOnce({ data: { allocated_total: 3722262 } });
  await act(async () => { q(host, "recon-split-submit").click(); });
  await flush();
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/bank-reconciliation/lines/l4/match-split");
  expect(body).toEqual({ allocations: [{ txn_id: "ka", amount: 2262062 }, { txn_id: "kb", amount: 1460200 }] });
  expect(cfg.headers["Idempotency-Key"]).toMatch(/^brsplit-/);
  expect(done).toHaveBeenCalledWith(expect.stringContaining("dipecah ke 2 transaksi"));
});
