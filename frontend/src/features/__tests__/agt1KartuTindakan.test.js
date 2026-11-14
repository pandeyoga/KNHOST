// AG-T1 — kartu tindakan Tanya KN (`TanyaActionCard`). Uji komponen untuk U18 (uji jalan peramban terpisah):
// kartu gagal menampilkan "Gagal: …", "Sudah dibuat sebelum gagal: …", tanpa tombol setujui; kartu kedaluwarsa;
// kartu menunggu menyebut PT + batas berlaku; tombol setujui mati dengan alasan TERTULIS saat PT aktif berbeda atau
// "Semua PT"; status selalu ikon + teks + warna; jawaban 200 berstatus gagal tidak diberi toast "berhasil".
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import EntityScopeContext from "../../context/EntityScopeContext";

const mockFetch = jest.fn();
const mockConfirm = jest.fn();
const mockDismiss = jest.fn();
jest.mock("../tanya/tanyaApi", () => ({
  __esModule: true,
  fetchAction: (...a) => mockFetch(...a),
  confirmAction: (...a) => mockConfirm(...a),
  dismissAction: (...a) => mockDismiss(...a),
}));
const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));

// eslint-disable-next-line import/first
import { TanyaActionCard } from "../tanya/TanyaActionCard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }, { id: "ent_kanda", short_name: "Kanda Fabric" }];
const PO = { pos: [{ supplier_name: "Sumber Satu", warehouse_name: "Gudang A", items: [
  { product_id: "p1", product_name: "Kain Satu", quantity: 10, unit: "meter", price: 1000 }] }] };
const KARTU = (over = {}) => ({
  id: "aiact_1", type: "draft_po", status: "pending", title: "Draf purchase order", reason: "stok menipis",
  payload: PO, entity_id: "ent_ksc", entity_name: "Sukacita", created_at: "2026-11-14T02:00:00+00:00",
  expires_at: "2026-11-15T02:00:00+00:00", ...over,
});

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(doc, scope = {}) {
  mockFetch.mockResolvedValue(doc);
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  const value = { selectedEntity: "ent_ksc", entities: ENTS, canWrite: true, writeBlockHint: "", pickEntity: () => {}, ...scope };
  await act(async () => {
    root.render(<EntityScopeContext.Provider value={value}><TanyaActionCard proposalId="aiact_1" /></EntityScopeContext.Provider>);
  });
  await flush();
}

afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  jest.clearAllMocks();
});

test("U18 — kartu gagal: pesan galat, hasil sebagian, tidak bisa diulang, tanpa tombol setujui", async () => {
  await mount(KARTU({ status: "failed", error: "Periode tertutup", result: ["KSC/PO-00001"] }));
  expect(q("tanya-action-error").textContent).toBe("Gagal: Periode tertutup");
  expect(q("tanya-action-partial").textContent).toBe("Sudah dibuat sebelum gagal: KSC/PO-00001");
  expect(q("tanya-action-status").textContent).toContain(
    "Kartu ini tidak bisa diulang. Minta asisten menyiapkan draf baru untuk sisanya.");
  expect(q("tanya-action-confirm")).toBeNull();
  expect(q("tanya-action-dismiss")).toBeNull();
  const pill = q("tanya-action-pill");
  expect(pill.textContent).toBe("Gagal");
  expect(pill.className).toContain("text-kn-danger-text");
  expect(pill.querySelector("svg")).not.toBeNull();            // ikon + teks + warna
  expect(q("tanya-action-meta").textContent).toBe("PT: Sukacita");
});

test("kartu gagal tanpa hasil sebagian tidak menampilkan baris 'Sudah dibuat'", async () => {
  await mount(KARTU({ status: "failed", error: "Proses berhenti sebelum selesai.", result: [] }));
  expect(q("tanya-action-partial")).toBeNull();
  expect(q("tanya-action-error").textContent).toBe("Gagal: Proses berhenti sebelum selesai.");
});

test("kartu kedaluwarsa: kalimat baku, tanpa tombol", async () => {
  await mount(KARTU({ status: "expired" }));
  expect(q("tanya-action-status").textContent).toBe("Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi.");
  expect(q("tanya-action-pill").textContent).toBe("Kedaluwarsa");
  expect(q("tanya-action-confirm")).toBeNull();
});

test("kartu menunggu: baris PT + berlaku sampai (WIB); label tombol tidak berubah", async () => {
  await mount(KARTU());
  // 2026-11-15T02:00Z = 15 Nov 2026 09.00 WIB
  expect(q("tanya-action-meta").textContent).toMatch(/^PT: Sukacita · berlaku sampai 15 Nov 2026,? 09[.:]00 WIB$/);
  expect(q("tanya-action-pill").textContent).toBe("Menunggu persetujuan");
  expect(q("tanya-action-confirm").textContent).toBe("Setujui & buat PO");
  expect(q("tanya-action-confirm").disabled).toBe(false);
  expect(q("tanya-action-pt-hint")).toBeNull();
  expect(q("tanya-action-dismiss").textContent.trim()).toBe("Abaikan");
});

test("PT aktif berbeda → tombol setujui mati dengan alasan tertulis; Abaikan tetap bisa", async () => {
  await mount(KARTU(), { selectedEntity: "ent_kanda" });
  expect(q("tanya-action-confirm").disabled).toBe(true);
  expect(q("tanya-action-pt-hint").textContent).toBe("Pindah ke Sukacita untuk menyetujui.");
  expect(q("tanya-action-dismiss").disabled).toBe(false);
});

test("mode Semua PT (akun berganti PT) → tombol setujui mati dengan alasan tertulis", async () => {
  await mount(KARTU(), { selectedEntity: "all", canWrite: false });
  expect(q("tanya-action-confirm").disabled).toBe(true);
  expect(q("tanya-action-pt-hint").textContent).toBe("Pindah ke Sukacita untuk menyetujui.");
});

test("akun satu-PT (header 'all' tetapi boleh menulis) → tombol setujui hidup", async () => {
  await mount(KARTU(), { selectedEntity: "all", canWrite: true });
  expect(q("tanya-action-confirm").disabled).toBe(false);
});

test("setujui → jawaban 200 berstatus gagal: kartu berganti ke tampilan gagal, toast galat (bukan 'berhasil')", async () => {
  await mount(KARTU());
  mockConfirm.mockResolvedValue(KARTU({ status: "failed", error: "Periode tertutup", result: ["KSC/PO-00001"],
                                        message: "Periode tertutup. Yang sudah dibuat: KSC/PO-00001." }));
  await act(async () => { q("tanya-action-confirm").click(); });
  await flush();
  expect(mockConfirm).toHaveBeenCalledWith("aiact_1", { pos: [{ items: [{ quantity: 10 }] }] });
  expect(q("tanya-action-error").textContent).toBe("Gagal: Periode tertutup");
  expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
    title: "Tindakan gagal", description: "Periode tertutup. Yang sudah dibuat: KSC/PO-00001.", variant: "destructive" }));
});

test("setujui ditolak 409 (kedaluwarsa) → kartu dimuat ulang dan menampilkan status terkini", async () => {
  await mount(KARTU());
  mockConfirm.mockRejectedValue({ response: { status: 409, data: { detail: "Draf ini sudah kedaluwarsa. Minta asisten menyiapkannya lagi." } } });
  mockFetch.mockResolvedValue(KARTU({ status: "expired" }));
  await act(async () => { q("tanya-action-confirm").click(); });
  await flush();
  expect(mockFetch).toHaveBeenCalledTimes(2);
  expect(q("tanya-action-pill").textContent).toBe("Kedaluwarsa");
  expect(q("tanya-action-confirm")).toBeNull();
});

test("status tak dikenal tidak tampil sebagai kode mentah", async () => {
  await mount(KARTU({ status: "on_hold" }));
  expect(q("tanya-action-pill").textContent).toBe("Ditahan");
  expect(q("tanya-action-confirm")).toBeNull();
});

test("kartu disetujui menampilkan nomor PO dan status ikon + teks", async () => {
  await mount(KARTU({ status: "confirmed", result: ["KSC/PO-00002"] }));
  expect(q("tanya-action-pill").textContent).toBe("Sudah disetujui");
  expect(q("tanya-action-status").textContent).toBe("PO dibuat: KSC/PO-00002");
});
