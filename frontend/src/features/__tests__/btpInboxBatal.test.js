// BTP-7 — Pusat Persetujuan memuat antrean "Pembatalan Pesanan" + tanda "Ditahan" di layar gudang + label notifikasi.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { loadInbox, KIND_META, CATEGORY_PERMS, butuhLabel } from "../approvals/approvalInboxData";
import { INBOX_TABS, BACKLOG_INBOX_TAB, LISTED_IN_INBOX } from "../approvals/inboxTabs";
import { HeldMark } from "../wms/OutboundScanBadges";
import { TYPE_LABEL } from "../../components/NotificationCenter";

const mockGet = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: () => Promise.resolve({ data: {} }), defaults: { headers: { common: {} } } },
  API: "/api",
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const PERMINTAAN = {
  request_id: "cr_1", order_id: "so_9", number: "KSC/SO-00009", customer_name: "Toko Mawar", entity_id: "ent_ksc",
  action: "close_remaining", amount: 2500000, reason: "Pelanggan membatalkan sisa", requested_by: "sales@x",
  requested_at: "2026-11-25T01:00:00Z", approval_basis: "nilai",
};

beforeEach(() => {
  mockGet.mockReset();
  mockGet.mockImplementation((url) => Promise.resolve({
    data: url.includes("/sales-orders/cancel-requests") ? [PERMINTAAN] : [] }));
});

test("tab so_cancel ada, antrean server dipetakan & daftarnya dirender inbox", () => {
  expect(INBOX_TABS).toContainEqual({ key: "so_cancel", label: "Pembatalan Pesanan" });
  expect(BACKLOG_INBOX_TAB.so_cancel).toBe("so_cancel");
  expect(LISTED_IN_INBOX).toContain("so_cancel");
  expect(KIND_META.so_cancel.group).toBe("so_cancel");
  expect(CATEGORY_PERMS["Pembatalan Pesanan"]).toEqual([["order", "approve_cancel"]]);
});

test("satu permintaan jadi satu butir: nomor pesanan + pelanggan, jenis, nilai, alasan, pengaju; buka rincian pesanan", async () => {
  const res = await loadInbox({ order: ["approve_cancel"] });
  expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/cancel-requests", { params: { status: "pending" } });
  const it = res.items.find((i) => i.kind === "so_cancel");
  expect(it).toMatchObject({ id: "cr_1", orderId: "so_9", title: "KSC/SO-00009", subtitle: "Toko Mawar",
    amount: 2500000, requester: "sales@x", openOrder: true });
  expect(it.meta).toContain("Tutup sisa");
  expect(it.meta).toContain("Pelanggan membatalkan sisa");
});

test("jenis Batal bila action=cancel; tanpa izin approve_cancel tidak dipanggil", async () => {
  mockGet.mockImplementation(() => Promise.resolve({ data: [{ ...PERMINTAAN, action: "cancel" }] }));
  const res = await loadInbox({ order: ["approve_cancel"] });
  expect(res.items.find((i) => i.kind === "so_cancel").meta).toMatch(/^Batal/);
  mockGet.mockClear();
  const tanpa = await loadInbox({ order: ["view"] });
  expect(tanpa.items.find((i) => i.kind === "so_cancel")).toBeUndefined();
  expect(mockGet).not.toHaveBeenCalledWith("/api/sales-orders/cancel-requests", expect.anything());
});

test("tanda gudang: muncul bila held_reason, tidak bila kosong", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<div><HeldMark task={{ id: "t1", held_reason: "Ditahan: menunggu keputusan batal" }} /><HeldMark task={{ id: "t2", held_reason: null }} /></div>); });
  expect(host.querySelector('[data-testid="held-mark-t1"]').textContent).toContain("Ditahan: menunggu keputusan batal");
  expect(host.querySelector('[data-testid="held-mark-t2"]')).toBeNull();
});

test("label notifikasi permintaan batal pesanan", () => {
  expect(TYPE_LABEL.permintaan_batal_pesanan).toBe("Permintaan batal pesanan");
  expect(TYPE_LABEL.permintaan_batal_diputus).toBe("Keputusan batal pesanan");
  expect(TYPE_LABEL.titipan_pesanan_batal).toBe("Uang muka jadi titipan");
  expect(TYPE_LABEL.titipan_pesanan_batal_gagal).toBe("Uang muka gagal jadi titipan");
});

test("butir pembatalan tidak menyebut peran: teks berbasis izin (layar & ekspor); jenis lain tetap nama peran", async () => {
  const res = await loadInbox({ order: ["approve_cancel"] });
  const it = res.items.find((i) => i.kind === "so_cancel");
  expect(it.role).toBeUndefined();
  expect(butuhLabel(it)).toBe("persetujuan pembatalan");
  expect(butuhLabel(it)).not.toMatch(/Manajer/i);
  expect(butuhLabel({ kind: "po", role: "manager" })).toMatch(/Manajer/i);
  expect(butuhLabel({ kind: "po" })).toMatch(/Manajer/i);
});
