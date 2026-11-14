// PK-20 — isian Rekening pada form yang melahirkan kas (`components/CashAccountField`).
// Uji komponen (U14 bagian layar; uji jalan peramban terpisah): rekening aktif PT dokumen untuk jenis kas terpilih,
// label "{nama} · {bank} {nomor}", satu rekening → terisi otomatis & terkunci + keterangan, kosong → pesan + simpan
// mati, gagal memuat → pesan tanpa mematikan simpan.
import React, { act, useState } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti <select> polos.
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

// eslint-disable-next-line import/first
import CashAccountField, { accountCashType, cashAccountBlocked, cashAccountLabel } from "../../components/CashAccountField";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const REK = [
  { id: "rek_k", name: "Kas Kecil KSC", entity_id: "ent_ksc", account_type: "cash", cash_type: "kas_kecil" },
  { id: "rek_b1", name: "BCA KSC", bank_name: "BCA", account_number: "111", entity_id: "ent_ksc",
    account_type: "bank", cash_type: "kas_besar" },
  { id: "rek_b2", name: "Mandiri KSC", bank_name: "Mandiri", account_number: "222", entity_id: "ent_ksc",
    account_type: "bank", cash_type: "kas_besar" },
  { id: "rek_off", name: "Bank Lama", entity_id: "ent_ksc", account_type: "bank", cash_type: "kas_besar",
    is_active: false },
  { id: "rek_x", name: "BCA Kanda", entity_id: "ent_kanda", account_type: "bank", cash_type: "kas_besar" },
];

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
let last = {};
function Wadah({ cashType, entityId = "ent_ksc" }) {
  const [v, setV] = useState("");
  const [st, setSt] = useState("");
  last = { value: v, state: st, blocked: cashAccountBlocked(st, v) };
  return <CashAccountField entityId={entityId} cashType={cashType} value={v} onChange={setV} onState={setSt}
    testId="rek" />;
}
async function mount(props) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(<Wadah {...props} />); });
  await flush();
  return host;
}

beforeEach(() => { mockGet.mockReset(); last = {}; });
afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
});

test("U14: transfer (Bank) menawarkan R-B1 dan R-B2 milik PT itu; wajib dipilih", async () => {
  mockGet.mockResolvedValue({ data: REK });
  await mount({ cashType: "kas_besar" });
  expect(mockGet).toHaveBeenCalledWith("/api/bank-accounts", { params: { entity_id: "ent_ksc" } });
  const opsi = [...q("rek-select").querySelectorAll("option")].filter((o) => o.value).map((o) => o.textContent);
  expect(opsi).toEqual(["BCA KSC · BCA 111", "Mandiri KSC · Mandiri 222"]);   // nonaktif & PT lain tidak ditawarkan
  expect(q("rek-select").disabled).toBe(false);
  expect(last.state).toBe("pilih");
  expect(last.blocked).toBe(true);                       // simpan mati sampai dipilih
  await act(async () => {
    q("rek-select").value = "rek_b2";
    q("rek-select").dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
  expect(last.value).toBe("rek_b2");
  expect(last.blocked).toBe(false);
});

test("U14: tunai (Kas Kecil) → terisi R-K dan terkunci dengan keterangan", async () => {
  mockGet.mockResolvedValue({ data: REK });
  await mount({ cashType: "kas_kecil" });
  expect(last.state).toBe("tunggal");
  expect(last.value).toBe("rek_k");
  expect(q("rek-select").disabled).toBe(true);
  expect(q("rek-sole").textContent).toContain("Satu-satunya rekening Kas Kecil");
  expect(last.blocked).toBe(false);
});

test("PT tanpa rekening jenis itu → pesan arahan, simpan mati", async () => {
  mockGet.mockResolvedValue({ data: REK.filter((r) => r.cash_type !== "kas_kecil") });
  await mount({ cashType: "kas_kecil" });
  expect(last.state).toBe("kosong");
  expect(q("rek-none").textContent).toContain("Belum ada rekening Kas Kecil untuk");
  expect(q("rek-none").textContent).toContain("Tambahkan di Kas & Bank › Rekening & Saldo.");
  expect(last.blocked).toBe(true);
});

test("gagal memuat → pesan galat, simpan TIDAK dimatikan (server yang menentukan)", async () => {
  mockGet.mockRejectedValue({ response: { status: 403, data: { detail: "Akses ditolak" } } });
  await mount({ cashType: "kas_besar" });
  expect(last.state).toBe("galat");
  expect(q("rek-error")).not.toBeNull();
  expect(last.blocked).toBe(false);
});

test("pembantu: jenis kas dari master rekening & label", () => {
  expect(accountCashType({ account_type: "cash" })).toBe("kas_kecil");
  expect(accountCashType({ account_type: "bank" })).toBe("kas_besar");
  expect(accountCashType({ account_type: "bank", cash_type: "kas_kecil" })).toBe("kas_kecil");
  expect(cashAccountLabel({ name: "Kas Toko" })).toBe("Kas Toko");
  expect(cashAccountBlocked("memuat", "")).toBe(true);
  expect(cashAccountBlocked("tanpa_pt", "")).toBe(false);
});
