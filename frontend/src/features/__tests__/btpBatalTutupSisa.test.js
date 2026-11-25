// BTP-6 — layar ajukan batal & tutup sisa: dialog menilai `cancel-check`, ringkasan sebelum-sesudah, bilah menunggu
// persetujuan, dan pemanggil lama (Panel Persetujuan SO) membaca 202 sebagai "diajukan", bukan "dibatalkan".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import CancelOrderDialog from "../orders/CancelOrderDialog";
import CloseRemainingDialog from "../orders/CloseRemainingDialog";
import CancelRequestBar from "../orders/CancelRequestBar";
import SoApprovalsPanel from "../orders/SoApprovalsPanel";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
async function settle() { await act(async () => {}); await act(async () => {}); }
async function klik(id) { await act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await settle(); }
async function isi(id, v) {
  const ta = q(id);
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
  await act(async () => { setter.call(ta, v); ta.dispatchEvent(new Event("input", { bubbles: true })); });
}
async function render(el) {
  document.body.innerHTML = "";
  const host = document.createElement("div");
  document.body.appendChild(host);
  act(() => { createRoot(host).render(el); });
  await settle();
}

const PESANAN = { id: "so_1", number: "KSC/SO-00100", paid_total: 5000000, status: "partially_shipped" };
const MENUNGGU = "Permintaan diajukan — menunggu persetujuan.";

beforeEach(() => {
  mockGet.mockReset(); mockPost.mockReset();
});

describe("dialog batal", () => {
  test("wajib setuju karena sudah dibayar: tombol Ajukan pembatalan, 202 -> pesan menunggu persetujuan", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: true, basis: ["paid"], can_self_approve: false, amount: 5000000 } });
    mockPost.mockResolvedValue({ status: 202, data: { request: { id: "scr_1" }, order_status: "approved", message: MENUNGGU } });
    const onDone = jest.fn();
    await render(<CancelOrderDialog order={PESANAN} onClose={() => {}} onDone={onDone} />);
    expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so_1/cancel-check", { params: { action: "cancel" } });
    expect(teks(q("cancel-order-confirm"))).toBe("Ajukan pembatalan");
    expect(teks(q("cancel-order-approval-note"))).toMatch(/sudah ada pembayaran/i);
    await isi("cancel-order-reason", "Pelanggan membatalkan");
    await klik("cancel-order-confirm");
    expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so_1/cancel", { reason: "Pelanggan membatalkan" });
    expect(onDone.mock.calls[0][0]).toMatch(/menunggu persetujuan/);
    expect(onDone.mock.calls[0][0]).not.toMatch(/dibatalkan, stok/);
  });

  test("tidak wajib setuju: tombol lama 'Ya, Batalkan SO'", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: false, basis: [], can_self_approve: false, amount: 0 } });
    await render(<CancelOrderDialog order={{ ...PESANAN, paid_total: 0 }} onClose={() => {}} onDone={() => {}} />);
    expect(teks(q("cancel-order-confirm"))).toBe("Ya, Batalkan SO");
    expect(q("cancel-order-approval-note")).toBeNull();
  });

  test("barang sudah disiapkan gudang disebut sebagai alasan", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: true, basis: ["prepared"], can_self_approve: false, amount: 1 } });
    await render(<CancelOrderDialog order={{ ...PESANAN, paid_total: 0 }} onClose={() => {}} onDone={() => {}} />);
    expect(teks(q("cancel-order-approval-note"))).toMatch(/sudah disiapkan gudang/i);
  });
});

describe("dialog tutup sisa", () => {
  const PREVIEW = {
    allowed: true, blockers: [],
    lines: [{ product_id: "p1", product_name: "Kain Uji", unit: "meter", qty_ordered: 100, qty_shipped: 40.123456 }],
    grand_total_before: 11100000, grand_total_after: 4440000, remaining_value: 6660000, excess_to_deposit: 6660000,
  };

  test("ringkasan sebelum-sesudah: 100 -> 40 (maks. 2 desimal), nilai lama -> baru, jadi titipan", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: true, basis: ["excess"], can_self_approve: false, amount: 6660000, preview: PREVIEW } });
    await render(<CloseRemainingDialog order={PESANAN} onClose={() => {}} onDone={() => {}} />);
    expect(mockGet).toHaveBeenCalledWith("/api/sales-orders/so_1/cancel-check", { params: { action: "close_remaining" } });
    const baris = teks(q("close-remaining-lines"));
    expect(baris).toMatch(/100 → 40,12/);
    expect(baris).not.toMatch(/40,123/);
    expect(teks(q("close-remaining-total"))).toMatch(/Rp\s?11\.100\.000.*→.*Rp\s?4\.440\.000/);
    expect(teks(q("close-remaining-deposit"))).toMatch(/jadi titipan/i);
    expect(teks(q("close-remaining-confirm"))).toBe("Ajukan tutup sisa");
  });

  test("tanpa kelebihan: tidak ada kalimat titipan; tidak wajib setuju -> 'Ya, Tutup Sisa'", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: false, basis: [], can_self_approve: false, amount: 0,
      preview: { ...PREVIEW, excess_to_deposit: 0 } } });
    await render(<CloseRemainingDialog order={PESANAN} onClose={() => {}} onDone={() => {}} />);
    expect(q("close-remaining-deposit")).toBeNull();
    expect(teks(q("close-remaining-confirm"))).toBe("Ya, Tutup Sisa");
  });

  test("terhalang: daftar penghalang tampil dan tombol nonaktif", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: false, basis: [], can_self_approve: false, amount: 0,
      preview: { ...PREVIEW, allowed: false, blockers: ["Sudah ada Faktur Pajak per pesanan."] } } });
    await render(<CloseRemainingDialog order={PESANAN} onClose={() => {}} onDone={() => {}} />);
    expect(teks(q("close-remaining-blockers"))).toMatch(/Faktur Pajak/);
    await isi("close-remaining-reason", "Pelanggan hanya mau sebagian");
    expect(q("close-remaining-confirm").disabled).toBe(true);
  });

  test("200: pesan hasil memuat titipan, galat pemindahan titipan, dan dokumen pemenuhan (I3)", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: false, basis: [], can_self_approve: false, amount: 0, preview: PREVIEW } });
    mockPost.mockResolvedValue({ status: 200, data: { status: "shipped", advance_to_deposit: 0,
      advance_to_deposit_error: "Kelebihan uang pesanan ini belum terpindah ke titipan pelanggan — hubungi Finance.",
      open_fulfillment_refs: ["KSC/TRF-00009"] } });
    const onDone = jest.fn();
    await render(<CloseRemainingDialog order={PESANAN} onClose={() => {}} onDone={onDone} />);
    await isi("close-remaining-reason", "Pelanggan hanya mau sebagian");
    await klik("close-remaining-confirm");
    const m = onDone.mock.calls[0][0];
    expect(m).toMatch(/sisa pesanan ditutup/);
    expect(m).toMatch(/belum terpindah ke titipan pelanggan — hubungi Finance/);
    expect(m).toMatch(/Tindak lanjuti dokumen pemenuhan: KSC\/TRF-00009/);
    expect(m).not.toMatch(/menjadi titipan pelanggan\./);
  });

  test("kirim: 202 -> pesan menunggu persetujuan; 200 -> pesan sisa ditutup", async () => {
    mockGet.mockResolvedValue({ data: { needs_approval: true, basis: ["excess"], can_self_approve: false, amount: 1, preview: PREVIEW } });
    mockPost.mockResolvedValue({ status: 202, data: { request: { id: "scr_2" }, message: MENUNGGU } });
    const onDone = jest.fn();
    await render(<CloseRemainingDialog order={PESANAN} onClose={() => {}} onDone={onDone} />);
    await isi("close-remaining-reason", "Pelanggan hanya mau sebagian");
    await klik("close-remaining-confirm");
    expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so_1/close-remaining", { reason: "Pelanggan hanya mau sebagian" });
    expect(onDone.mock.calls[0][0]).toMatch(/menunggu persetujuan/);
  });
});

describe("bilah menunggu persetujuan", () => {
  const REQ = { id: "scr_9", action: "cancel", status: "pending", reason: "Pelanggan batal", requested_by: "Rina",
    requested_by_id: "u_rina", requested_at: "2026-11-25T03:00:00+00:00", approval_basis: ["paid"], amount: 5000000 };
  const order = { ...PESANAN, cancel_request: REQ };

  test("pemegang approve_cancel (bukan pengaju): Setujui/Tolak; Tolak tanpa alasan nonaktif", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { status: "cancelled" } });
    const onDone = jest.fn();
    await render(<CancelRequestBar order={order} perms={{ order: ["approve_cancel"] }} userId="u_budi" onDone={onDone} />);
    expect(teks(q("cancel-request-bar"))).toMatch(/Rina/);
    expect(teks(q("cancel-request-bar"))).toMatch(/Pelanggan batal/);
    expect(q("cancel-request-approve")).not.toBeNull();
    expect(q("cancel-request-withdraw")).toBeNull();
    expect(q("cancel-request-reject").disabled).toBe(true);
    await isi("cancel-request-note", "Belum bisa");
    expect(q("cancel-request-reject").disabled).toBe(false);
    await klik("cancel-request-reject");
    expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so_1/cancel-request/decision", { decision: "reject", note: "Belum bisa" });
    expect(onDone).toHaveBeenCalled();
  });

  test("Setujui: pesan memuat hasil eksekusi — titipan, galat titipan, dokumen pemenuhan (I3)", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { order_status: "cancelled", message: "Permintaan disetujui — pesanan dibatalkan.",
      request: { id: "scr_9", status: "approved" },
      result: { status: "cancelled", advance_to_deposit: 5000000,
        advance_to_deposit_error: "Uang muka pesanan ini belum terpindah ke titipan pelanggan — hubungi Finance.",
        open_fulfillment_refs: ["KSC/PR-00012", "KSC/TRF-00003"] } } });
    const onDone = jest.fn();
    await render(<CancelRequestBar order={order} perms={{ order: ["approve_cancel"] }} userId="u_budi" onDone={onDone} />);
    await klik("cancel-request-approve");
    const m = onDone.mock.calls[0][0].replace(/\s+/g, " ");
    expect(m).toMatch(/KSC\/SO-00100: permintaan pembatalan disetujui/);
    expect(m).toMatch(/Uang muka Rp\s?5\.000\.000 menjadi titipan pelanggan/);
    expect(m).toMatch(/belum terpindah ke titipan pelanggan — hubungi Finance/);
    expect(m).toMatch(/Tindak lanjuti dokumen pemenuhan: KSC\/PR-00012, KSC\/TRF-00003/);
  });

  test("Setujui tutup sisa: kelebihan yang jadi titipan disebut", async () => {
    mockPost.mockResolvedValue({ status: 200, data: { order_status: "shipped", request: { id: "scr_8", status: "approved" },
      result: { status: "shipped", advance_to_deposit: 6660000, open_fulfillment_refs: [] } } });
    const onDone = jest.fn();
    const tutup = { ...PESANAN, cancel_request: { ...REQ, id: "scr_8", action: "close_remaining", approval_basis: ["excess"] } };
    await render(<CancelRequestBar order={tutup} perms={{ order: ["approve_cancel"] }} userId="u_budi" onDone={onDone} />);
    await klik("cancel-request-approve");
    const m = onDone.mock.calls[0][0].replace(/\s+/g, " ");
    expect(m).toMatch(/permintaan tutup sisa disetujui/);
    expect(m).toMatch(/Rp\s?6\.660\.000 menjadi titipan pelanggan/);
    expect(m).not.toMatch(/Tindak lanjuti/);
  });

  test("pengaju melihat Tarik, bukan Setujui", async () => {
    mockPost.mockResolvedValue({ status: 200, data: {} });
    await render(<CancelRequestBar order={order} perms={{ order: ["cancel", "approve_cancel"] }} userId="u_rina" onDone={() => {}} />);
    expect(q("cancel-request-approve")).toBeNull();
    await klik("cancel-request-withdraw");
    expect(mockPost).toHaveBeenCalledWith("/api/sales-orders/so_1/cancel-request/withdraw");
  });

  test("tanpa permintaan menunggu: tidak tampil", async () => {
    await render(<CancelRequestBar order={PESANAN} perms={{ order: ["cancel"] }} onDone={() => {}} />);
    expect(q("cancel-request-bar")).toBeNull();
  });
});

describe("pemanggil lama (Review Focus 3)", () => {
  test("Panel Persetujuan SO: 202 dibaca 'diajukan', bukan 'dibatalkan'", async () => {
    mockPost.mockResolvedValue({ status: 202, data: { request: { id: "scr_3" }, order_status: "waiting_approval", message: MENUNGGU } });
    const order = { id: "so_7", number: "KSC/SO-00107", status: "waiting_approval", items: [],
      pending_approvals: [{ id: "ap1", type: "special_price", status: "rejected", product_id: "p1" }] };
    await render(<SoApprovalsPanel order={order} user={{ permissions: { order: ["cancel"], price_approval: ["create"] } }} onRefresh={async () => {}} />);
    await klik("so-appr-cancel-order-ap1");
    await isi("so-appr-cancel-reason", "Pelanggan tidak setuju harga");
    await klik("so-appr-cancel-submit");
    const m = teks(q("so-appr-msg"));
    expect(m).toMatch(/diajukan/i);
    expect(m).toMatch(/menunggu persetujuan/);
    expect(m).not.toMatch(/dibatalkan/);
  });
});
