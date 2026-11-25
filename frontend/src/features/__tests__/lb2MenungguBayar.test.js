// Lapor Bayar CBD & DP · Tugas 2 — pesanan wajib bayar dulu ditahan sebelum gudang (rancangan
// docs/superpowers/specs/2026-11-25-lapor-bayar-cbd-design.md §5.1). "Periksa & lepas" yang tertahan bayar mengembalikan
// 200 `{ released: false, release_state: { waiting: "bayar" } }` — dialog menampilkan pesan langkah berikutnya, bukan
// galat; sub-status `menunggu_bayar` ("Menunggu bayar") menggantikan "Stok siap" (cermin backend so_status).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import VerifyOrderDialog from "../sales_admin/VerifyOrderDialog";
import { releaseMessage } from "../sales_admin/workDeskApi";
import { deriveStageSub, subStatusLabel } from "../../utils/soStatus";

const apiCalls = [];
jest.mock("../../services/apiClient", () => ({
  __esModule: true, API: "/api",
  default: {
    defaults: { headers: { common: {} } },
    get: (url) => {
      apiCalls.push(["get", url]);
      return Promise.resolve({ data: { verifiable: true, ready: true, checks: [], blocking_gaps: [], warnings: [],
        order_preview: { customer_name: "Toko Uji", items: [], totals: {} } } });
    },
    post: (url, body) => {
      apiCalls.push(["post", url, body]);
      return Promise.resolve({ data: { order: { number: "SO-CBD", status: "approved" }, released: false,
        release_state: { waiting: "bayar", hold: false, requested: true } } });
    },
  },
}));   // bukan jest.fn: resetMocks CRA
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const tick = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

test("Periksa & lepas pesanan CBD belum dibayar: pesan menunggu bayar, tanpa galat", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  let msg = "";
  let res = null;
  await act(async () => {
    root.render(<VerifyOrderDialog orderId="so1" orderNumber="SO-CBD" customerName="Toko Uji"
      onClose={() => {}} onVerified={(m, r) => { msg = m; res = r; }} />);
  });
  await tick();
  await act(async () => { q("verify-submit").click(); });
  await tick();
  expect(apiCalls.some(([m, url]) => m === "post" && url === "/api/sales-orders/so1/review-release")).toBe(true);
  expect(msg).toBe("SO-CBD diperiksa — menunggu pembayaran dicek Finance; dilepas ke gudang otomatis sesudah bayar "
    + "diterima.");
  expect(res.released).toBe(false);
  expect(document.body.textContent).not.toMatch(/Gagal memeriksa/);
  act(() => root.unmount());
  host.remove();
});

test("releaseMessage: menunggu bayar dibedakan dari ACC, tahan, dan dilepas", () => {
  const bayar = { order: { number: "SO-1", status: "approved" }, released: false, release_state: { waiting: "bayar" } };
  expect(releaseMessage(bayar)).toMatch(/menunggu pembayaran dicek Finance/);
  expect(releaseMessage({ ...bayar, release_state: { waiting: "acc" } })).toMatch(/menunggu ACC Manajer/);
  expect(releaseMessage({ released: true, order: { number: "SO-1", status: "confirmed" } })).toMatch(/dilepas ke gudang/);
});

test("sub-status menunggu_bayar (cermin backend): hanya pesanan Disetujui ber-pay_hold", () => {
  const hold = { since: "2026-11-25T00:00:00+00:00", required: 1000000 };
  expect(deriveStageSub({ status: "approved", pay_hold: hold })).toEqual(["Approved", ["menunggu_bayar"]]);
  expect(deriveStageSub({ status: "approved", pay_hold: hold, credit_hold: true }))
    .toEqual(["Approved", ["tahan_kredit", "menunggu_bayar"]]);
  expect(deriveStageSub({ status: "approved", pay_hold: hold, has_backorder: true }))
    .toEqual(["Approved", ["menunggu_bayar", "sebagian_menunggu_stok"]]);
  expect(deriveStageSub({ status: "approved" })).toEqual(["Approved", ["siap_confirm"]]);
  expect(deriveStageSub({ status: "confirmed", pay_hold: hold })).toEqual(["Confirmed", ["siap_pick"]]);
  expect(subStatusLabel("menunggu_bayar")).toBe("Menunggu bayar");
});
