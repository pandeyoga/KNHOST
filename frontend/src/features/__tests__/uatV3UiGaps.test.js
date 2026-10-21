// Cek UI UAT v3 (2026-10-21) — celah antarmuka dari skenario S1: daftar roll yang harus diambil di Barang Keluar,
// kartu antrean meja (ringkasan qty per satuan, keterangan bila baris dibatasi), lencana status tugas gudang.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import PickListPanel from "../wms/PickListPanel";
import DeskQueueCard from "../sales_admin/DeskQueueCard";
import { badgeLabel } from "../sales_admin/workDeskApi";

jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: jest.fn() }, API: "/api" }));
jest.mock("../documents/DocumentActionsBar", () => (p) => <span data-testid="doc-bar">{`${p.docType}:${p.sourceId}`}</span>);
const axios = require("../../services/apiClient").default;
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);

async function mount(el) {
  const host = document.createElement("div");
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await act(async () => {});
  return { host, root };
}

test("daftar ambil: roll teralokasi + potong dulu; [Ambil] mengisi kolom scan; Surat Pengambilan Barang", async () => {
  axios.get.mockResolvedValue({ data: { unit: "yard", rolls: [
    { id: "r1", roll_no: "RL-1", lot: "L1", bin_code: "A-01-02", length_remaining: 45.22, picked: false },
    { id: "r2", roll_no: "RL-2", lot: "L1", length_remaining: 30, picked: true }],
    pending_cuts: [{ roll_no: "RL-9", qty: 12.5 }] } });
  const onPick = jest.fn();
  const { host, root } = await mount(<PickListPanel task={{ id: "t1", order_id: "so1", order_number: "KSC/SO-1", picked_qty: 0 }} onPick={onPick} />);
  expect(axios.get).toHaveBeenCalledWith("/api/outbound/tasks/t1/pick-list");
  expect(q(host, "outbound-pick-roll-RL-1").textContent).toMatch(/lokasi A-01-02/);
  expect(q(host, "outbound-pick-roll-RL-2").textContent).toMatch(/sudah diambil/);
  expect(q(host, "outbound-pick-cuts").textContent).toMatch(/RL-9/);
  expect(q(host, "doc-bar").textContent).toBe("picking_list:so1");
  await act(async () => { q(host, "outbound-pick-take-RL-1").click(); });
  expect(onPick).toHaveBeenCalledWith("RL-1");
  await act(async () => { root.unmount(); });
});

test("kartu antrean qty: ringkasan per satuan, keterangan bila baris dibatasi", async () => {
  const queue = { id: "sj_belum_diangkut", label: "SJ", value_kind: "qty", count: 250, total_value: 99,
    rows: [{ ref_id: "a", number: "SJ-1", title: "T", value: 10, unit: "yard", age_days: 0 },
           { ref_id: "b", number: "SJ-2", title: "T", value: 5, unit: "kg", age_days: 0 }] };
  const { host, root } = await mount(<DeskQueueCard queue={queue} testPrefix="wh-desk" defaultOpen />);
  expect(host.textContent).toMatch(/5 kg · 10 yard/);                    // dulu: "15 yard"
  expect(q(host, "wh-desk-truncated-sj_belum_diangkut").textContent).toMatch(/2 tertua dari 250/);
  await act(async () => { root.unmount(); });
});

test("lencana status tugas gudang diterjemahkan", () => {
  expect(badgeLabel("created")).toBe("Siap diambil");
  expect(badgeLabel("staging")).toBe("Siap muat");
});
