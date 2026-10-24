// UAT 24 Okt — fase F3: P4.4/P3.5 warna labdip (Pantone wajib) · P5.1 kode nilai sumbu baru · P1.3 visibilitas SKU
// eksklusif di katalog · P1.5 lencana kepemilikan desain.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { colorProblem, PANTONE_RE } from "../rnd/ColorTargetsEditor";
import { newOptionCode } from "../catalog/SpecVariantFields";
import { visibleToCustomer } from "../../utils/variants";
import { OwnershipBadge } from "../hr/DesignOwnershipPanel";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: () => Promise.resolve({ data: {} }) }, API: "/api" }));
jest.mock("../../components/KNSelect", () => () => null);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("P3.5/P4.4 — warna baru labdip wajib nama, hex, dan kode Pantone yang sah; warna Pustaka cukup id-nya", () => {
  expect(colorProblem({ name: "Navy", hex: "#1F3A93", pantone_code: "19-4052 TCX" })).toBe("");
  expect(colorProblem({ name: "Navy", hex: "#1F3A93", pantone_code: "" })).toBe("kode Pantone");
  expect(colorProblem({ name: "Navy", hex: "1F3A9", pantone_code: "19-4052 TCX" })).toBe("hex");
  expect(colorProblem({ name: "", hex: "#1F3A93", pantone_code: "19-4052 TCX" })).toBe("nama warna");
  expect(colorProblem({ color_id: "col_1" })).toBe("");
  expect(PANTONE_RE.test("Cool Gray 11 C")).toBe(true);
  expect(PANTONE_RE.test("biru muda")).toBe(false);
});

test("P5.1 — kode nilai sumbu baru 4 huruf, unik terhadap kode yang sudah ada", () => {
  expect(newOptionCode("Navy Blazer", new Set(["ABUX"]))).toBe("NAVY");
  expect(newOptionCode("Navy", new Set(["NAVY"]))).toBe("NAV1");
  expect(newOptionCode("Ab", new Set())).toBe("ABXX");
});

test("P1.3 — SKU eksklusif pelanggan lain tersembunyi; pemilik & pembeli lama tetap melihat", () => {
  const p = { exclusive_customer_id: "c_owner", exclusive_allow_customer_ids: ["c_old"] };
  expect(visibleToCustomer(p, "c_owner")).toBe(true);
  expect(visibleToCustomer(p, "c_old")).toBe(true);
  expect(visibleToCustomer(p, "c_lain")).toBe(false);
  expect(visibleToCustomer({}, "c_lain")).toBe(true);
});

test("P1.5 — lencana kepemilikan: white label / customer label + klaim menunggu", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<OwnershipBadge d={{ ownership: "customer", owner_customer_name: "Butik Bali", claim_pending: false }} testId="b1" />); });
  expect(document.querySelector('[data-testid="b1"]').textContent).toBe("Customer label · Butik Bali");
  await act(async () => { root.render(<OwnershipBadge d={{ ownership: "white", claim_pending: true }} testId="b1" />); });
  expect(document.querySelector('[data-testid="b1"]').textContent).toMatch(/^White label.*klaim menunggu/);
  act(() => root.unmount());
});
