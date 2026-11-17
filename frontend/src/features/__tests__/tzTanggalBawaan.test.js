// Perburuan 18 Nov (pukul 00.00–07.00 WIB) — tanggal bawaan layar keuangan = hari ini WIB (`todayWib`), bukan tanggal
// zona PERANGKAT. Jam dibekukan ke 17 Nov 18.00 UTC = 18 Nov 01.00 WIB; proses uji ber-zona UTC (seperti mesin uji
// layar dan perangkat yang zonanya salah) sehingga kode lama memberi 2026-11-17.
//   · Neraca Saldo (Buku Besar › Neraca Saldo): "per tanggal" bawaan → kueri as_of.
//   · Catat Refund antar-PT: tanggal refund bawaan (dijurnal di kedua PT).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { TrialBalanceTab } from "../finance/GeneralLedgerTabs";
import IntercoRefundModal from "../finance/interco/IntercoRefundModal";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import { AppNavProvider } from "../../context/AppNavContext";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), patch: () => Promise.resolve({ data: {} }),
    put: () => Promise.resolve({ data: {} }), delete: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
jest.mock("../../services/confirmService", () => ({
  __esModule: true, askConfirm: () => Promise.resolve(true), default: { askConfirm: () => Promise.resolve(true) },
}));
jest.mock("../../config/paymentMethods", () => ({
  __esModule: true,
  usePaymentMethods: () => ({ methods: [{ code: "transfer", name: "Transfer bank", needs_account: "bank" }] }),
}));
jest.mock("../../components/KNSelect", () => {
  const Sel = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onValueChange?.(e.target.value)}>
      <option value="">—</option>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: Sel, KNSelect: Sel };
});
jest.mock("../../components/KNDatePicker", () => ({
  __esModule: true,
  default: (p) => <input data-testid={p["data-testid"]} value={p.value || ""} onChange={(e) => p.onChange(e.target.value)} />,
}));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const SAAT = new Date("2026-11-17T18:00:00Z");   // 18 Nov 2026 01.00 WIB
const ENT = [{ id: "A", short_name: "PT A", name: "PT A" }, { id: "B", short_name: "PT B", name: "PT B" }];
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
let roots = [];

async function mountBeku(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  jest.useFakeTimers("modern");
  jest.setSystemTime(SAAT);
  try {
    await act(async () => {
      root.render(
        <AppNavProvider role="admin">
          <EntityScopeProvider selectedEntity="A" entities={ENT} canSwitch>{el}</EntityScopeProvider>
        </AppNavProvider>);
    });
  } finally {
    jest.useRealTimers();
  }
  for (let i = 0; i < 4; i += 1) await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
}

beforeEach(() => {
  mockGet.mockImplementation((url) => Promise.resolve({
    data: url.includes("/gl/trial-balance") ? { rows: [], total_debit: 0, total_credit: 0, balanced: true } : [] }));
  mockPost.mockImplementation(() => Promise.resolve({ data: {} }));
});
afterEach(async () => {
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  document.body.innerHTML = "";
  jest.useRealTimers();
});

test("proses uji ber-zona UTC: tanggal perangkat pada saat beku masih 17 Nov", () => {
  expect(SAAT.getDate()).toBe(17);
});

test("Neraca Saldo: per tanggal bawaan = 18 Nov (hari ini WIB), bukan 17 Nov", async () => {
  await mountBeku(<TrialBalanceTab refreshKey={0} onError={() => {}} onDrill={() => {}} selectedEntity="A" />);
  expect(q("gl-trial-asof").value).toBe("2026-11-18");
  const panggil = mockGet.mock.calls.find(([u]) => u.includes("/gl/trial-balance"));
  expect(panggil[1].params).toEqual({ as_of: "2026-11-18" });
});

test("Catat Refund antar-PT: tanggal refund bawaan = 18 Nov (hari ini WIB)", async () => {
  await mountBeku(<IntercoRefundModal entities={ENT} presetPayerEntityId="A" presetPayeeEntityId="B"
    onClose={() => {}} onCreated={() => {}} />);
  expect(q("interco-refund-date").value).toBe("2026-11-18");
});
