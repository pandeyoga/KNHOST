// FE-04 (review 2026-10-20) — tombol Setujui/Tolak transfer mengikuti izin efektif, bukan nama peran.
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import TransferDetailModal from "../TransferDetailModal";

const transfer = { id: "trf_1", transfer_number: "TRF-1", status: "waiting_approval", items: [],
  from_warehouse_name: "A", to_warehouse_name: "B", status_history: [] };
const render = (user) => renderToStaticMarkup(
  <TransferDetailModal transfer={transfer} user={user} onClose={() => {}} onApprove={() => {}} onReject={() => {}}
    onUpdateStatus={() => {}} onCancel={() => {}} />);

test.each([
  ["admin berizin", { role: "admin", permissions: { transfer: ["approve", "reject"] } }, true, true],
  ["peran kustom berizin approve saja", { role: "cr_gudang", permissions: { transfer: ["approve"] } }, true, false],
  ["manager yang izinnya dicabut", { role: "manager", permissions: { transfer: ["view"] } }, false, false],
])("%s", (_n, user, approve, reject) => {
  const html = render(user);
  expect(html.includes("approve-transfer-button")).toBe(approve);
  expect(html.includes("reject-transfer-button")).toBe(reject);
});
