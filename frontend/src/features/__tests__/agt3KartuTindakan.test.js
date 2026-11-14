// AG-T3 — kartu tindakan golongan A/B dan tab "Tindakan" Tanya KN. Uji komponen untuk U18 (uji jalan peramban
// terpisah): saringan & kolom sesuai teks; rencana "Hal · Sekarang · Sesudah" dengan rupiah utuh; tombol setujui mati
// dengan alasan TERTULIS (Semua PT, alasan/ketik ulang belum diisi); pop-up menyebut "Rp 5.000.000" dan nama PT;
// sesudahnya "Berhasil — Kwitansi …" + "Jurnal: terposting"; status ikon + teks + warna; tombol "Tanya soal layar ini"
// menurut izin `ai_finance.view`.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import EntityScopeContext from "../../context/EntityScopeContext";
import AppNavContext from "../../context/AppNavContext";

const mockFetch = jest.fn();
const mockConfirm = jest.fn();
const mockDismiss = jest.fn();
const mockList = jest.fn();
jest.mock("../tanya/tanyaApi", () => ({
  __esModule: true,
  fetchAction: (...a) => mockFetch(...a),
  confirmAction: (...a) => mockConfirm(...a),
  dismissAction: (...a) => mockDismiss(...a),
  fetchActions: (...a) => mockList(...a),
}));
const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
const mockAsk = jest.fn();
jest.mock("../../services/confirmService", () => ({ __esModule: true, askConfirm: (...a) => mockAsk(...a) }));
jest.mock("../../components/ui/dropdown-menu", () => {
  const P = ({ children }) => <>{children}</>;
  return { DropdownMenu: P, DropdownMenuContent: P, DropdownMenuItem: P, DropdownMenuLabel: P, DropdownMenuSeparator: () => null,
    DropdownMenuTrigger: P };
});

// eslint-disable-next-line import/first
import { TanyaActionCard } from "../tanya/TanyaActionCard";
// eslint-disable-next-line import/first
import { TanyaActions } from "../tanya/TanyaActions";
// eslint-disable-next-line import/first
import { AskKnButton } from "../../components/AskKnButton";
// eslint-disable-next-line import/first
import { setAccessContext } from "../../config/roles";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const ENTS = [{ id: "ent_ksc", short_name: "Sukacita" }, { id: "ent_kanda", short_name: "Kanda Fabric" }];
const KARTU = (over = {}) => ({
  id: "aiact_9", type: "ar_receipt_create", class: "B", risk: "high", status: "pending", title: "Catat kwitansi piutang",
  entity_id: "ent_ksc", entity_name: "Sukacita", created_at: "2026-11-14T02:00:00+00:00",
  expires_at: "2026-11-15T02:00:00+00:00", args: { receipt_date: "2026-11-14", method: "transfer", notes: "" },
  editable: [{ path: "receipt_date", label: "Tanggal", kind: "date" }, { path: "method", label: "Cara bayar", kind: "text" },
    { path: "notes", label: "Catatan", kind: "text" }],
  plan: { summary: "Catat kwitansi Rp 5.000.000 dari Toko Cahaya.", amount: 5000000, confirm_text: "5000000",
    note: "Jurnal dibuat sistem saat disimpan.",
    rows: [{ label: "Sisa tagihan SO-1", kind: "money", before: 8000000, after: 3000000 },
      { label: "Cara bayar", kind: "text", before: "—", after: "Transfer" },
      { label: "Tanggal kwitansi", kind: "date", before: "—", after: "2026-11-15" }] },
  ...over,
});
const BERHASIL = KARTU({ status: "confirmed", result: { status_code: 200, gl_status: "posted", message: "",
  document: { type: "ar_receipt", label: "Kwitansi Pelanggan", id: "arc_1", number: "AR-00007",
    link: { view: "collection-worklist", focus_type: "ar_receipt", focus_id: "arc_1" } } } });

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const txt = (el) => (el?.textContent || "").replace(/ /g, " ");
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
const nav = { role: "finance", go: jest.fn(), canOpen: () => true, openDocument: () => {} };
async function mount(el, scope = {}) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  const value = { selectedEntity: "ent_ksc", entities: ENTS, canWrite: true, writeBlockHint: "", pickEntity: () => {}, ...scope };
  await act(async () => {
    root.render(<AppNavContext.Provider value={nav}><EntityScopeContext.Provider value={value}>{el}</EntityScopeContext.Provider></AppNavContext.Provider>);
  });
  await flush();
  return host;
}
function ketik(el, v) {
  const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  set.call(el, v);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}

afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  jest.clearAllMocks();
});

test("kartu golongan B: kepala, PT + batas berlaku, tabel Rencana, catatan jurnal, rupiah utuh", async () => {
  mockFetch.mockResolvedValue(KARTU());
  await mount(<TanyaActionCard proposalId="aiact_9" />);
  expect(txt(q("tanya-action-aiact_9").querySelector(".tanya-kicker"))).toBe(" Kartu tindakan · Catat kwitansi piutang");
  expect(txt(q("tanya-action-meta"))).toMatch(/^PT: Sukacita · berlaku sampai .+ WIB$/);
  expect(txt(q("tanya-action-meta"))).not.toMatch(/WIB WIB/);
  const heads = [...q("tanya-card-plan").querySelectorAll("th")].map((th) => th.textContent);
  expect(heads).toEqual(["Hal", "Sekarang", "Sesudah"]);
  expect(q("tanya-card-plan").querySelector("table").className).toContain("head-wrap");
  const sel = [...q("tanya-card-row-0").querySelectorAll("td")].map(txt);
  expect(sel).toEqual(["Sisa tagihan SO-1", "Rp 8.000.000", "Rp 3.000.000"]);
  expect(q("tanya-card-row-0").querySelector(".whitespace-nowrap").textContent).toBe("8.000.000");   // angka tak dipatah
  // Cek layar AG-T3 (uji jalan 1280 px): tanggal rencana tampil "15 Nov 2026", bukan ISO mentah "2026-11-15".
  expect(txt(q("tanya-card-row-2").querySelectorAll("td")[2])).toBe("15 Nov 2026");
  expect(q("tanya-card-note").textContent).toBe("Jurnal dibuat sistem saat disimpan.");
  expect(q("tanya-card-reason").getAttribute("placeholder")).toBe("Mengapa tindakan ini dilakukan?");
  expect(q("tanya-card-retype").getAttribute("placeholder")).toBe("Ketik 5000000 untuk menyetujui.");
  const pill = q("tanya-action-pill");
  expect(pill.textContent).toBe("Menunggu");
  expect(pill.querySelector("svg")).not.toBeNull();
  expect(pill.className).toContain("text-kn-warning-text");
});

test("tombol setujui mati dengan alasan tertulis sampai alasan & ketik ulang benar; pop-up menyebut nominal dan PT", async () => {
  mockFetch.mockResolvedValue(KARTU());
  mockAsk.mockResolvedValue(true);
  mockConfirm.mockResolvedValue(BERHASIL);
  await mount(<TanyaActionCard proposalId="aiact_9" />);
  expect(q("tanya-action-confirm").disabled).toBe(true);
  expect(q("tanya-action-pt-hint").textContent).toBe("Tulis alasan (minimal 10 huruf) dan ketik ulang nominal untuk menyetujui.");
  await act(async () => { ketik(q("tanya-card-reason"), "pelanggan transfer pagi ini"); });
  expect(q("tanya-action-pt-hint").textContent).toBe("Ketik ulang nominal persis seperti di kartu untuk menyetujui.");
  await act(async () => { ketik(q("tanya-card-retype"), "500000"); });
  expect(q("tanya-action-confirm").disabled).toBe(true);
  await act(async () => { ketik(q("tanya-card-retype"), "5.000.000"); });
  expect(q("tanya-action-confirm").disabled).toBe(false);
  expect(q("tanya-action-pt-hint")).toBeNull();
  expect(q("tanya-action-confirm").textContent).toBe("Setujui dan jalankan");
  await act(async () => { q("tanya-action-confirm").click(); });
  await flush();
  const opts = mockAsk.mock.calls[0][0];
  expect(opts.message.replace(/ /g, " ")).toBe("Jalankan Catat kwitansi piutang sebesar Rp 5.000.000 untuk Sukacita?");
  expect([opts.confirmLabel, opts.cancelLabel]).toEqual(["Ya, jalankan", "Batal"]);
  expect(mockConfirm).toHaveBeenCalledWith("aiact_9", null, { reason: "pelanggan transfer pagi ini", retype: "5.000.000" });
  expect(q("tanya-card-success").textContent).toBe("Berhasil — Kwitansi Pelanggan AR-00007");
  expect(q("tanya-card-gl").textContent).toBe("Jurnal: terposting");
  expect(q("tanya-action-pill").textContent).toBe("Berhasil");
  await act(async () => { q("tanya-card-open").click(); });
  expect(nav.go).toHaveBeenCalledWith("collection-worklist", expect.objectContaining({
    focus: expect.objectContaining({ type: "ar_receipt", id: "arc_1" }) }));
});

test("pop-up dibatalkan → tidak ada yang dikirim; isian yang diubah ikut dikirim", async () => {
  mockFetch.mockResolvedValue(KARTU());
  mockAsk.mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  mockConfirm.mockResolvedValue(BERHASIL);
  await mount(<TanyaActionCard proposalId="aiact_9" />);
  await act(async () => { ketik(q("tanya-card-reason"), "pelanggan transfer pagi ini"); ketik(q("tanya-card-retype"), "5000000"); });
  await act(async () => { q("tanya-action-confirm").click(); });
  await flush();
  expect(mockConfirm).not.toHaveBeenCalled();
  await act(async () => { ketik(q("tanya-card-edit-notes"), "bukti BCA"); });
  await act(async () => { q("tanya-action-confirm").click(); });
  await flush();
  expect(mockConfirm).toHaveBeenCalledWith("aiact_9", { notes: "bukti BCA" }, { reason: "pelanggan transfer pagi ini", retype: "5000000" });
});

test("mode Semua PT: setujui mati dengan petunjuk tertulis; Abaikan tetap aktif", async () => {
  mockFetch.mockResolvedValue(KARTU());
  await mount(<TanyaActionCard proposalId="aiact_9" />, { selectedEntity: "all", canWrite: false });
  expect(q("tanya-action-confirm").disabled).toBe(true);
  expect(q("tanya-action-pt-hint").textContent).toBe("Pilih satu PT untuk menyetujui kartu.");
  expect(q("tanya-action-dismiss").disabled).toBe(false);
});

test("golongan A tingkat rendah: tanpa isian alasan, tanpa pop-up nominal", async () => {
  mockFetch.mockResolvedValue(KARTU({ type: "followup_note", class: "A", risk: "low", title: "Catat tindak lanjut penagihan",
    editable: [], plan: { summary: "Catat tindak lanjut.", amount: 0, confirm_text: "",
      rows: [{ label: "Catatan", kind: "text", before: "—", after: "sudah ditelepon" }] } }));
  mockConfirm.mockResolvedValue(KARTU({ status: "confirmed", class: "A", result: { gl_status: null,
    document: { label: "Tindak lanjut penagihan", number: "Toko Cahaya", link: {} } } }));
  await mount(<TanyaActionCard proposalId="aiact_9" />);
  expect(q("tanya-card-reason")).toBeNull();
  expect(q("tanya-card-retype")).toBeNull();
  expect(q("tanya-card-note")).toBeNull();
  await act(async () => { q("tanya-action-confirm").click(); });
  await flush();
  expect(mockAsk).not.toHaveBeenCalled();
  expect(q("tanya-card-success").textContent).toBe("Berhasil — Tindak lanjut penagihan Toko Cahaya");
  expect(q("tanya-card-gl")).toBeNull();
});

test.each([
  [{ status: "failed", error: "Data sudah berubah sejak kartu disiapkan. Minta asisten menyiapkannya lagi." },
    "Gagal: Data sudah berubah sejak kartu disiapkan. Minta asisten menyiapkannya lagi.", "Gagal", "text-kn-danger-text"],
  [{ status: "expired" }, "Kedaluwarsa", "Kedaluwarsa", "text-kn-neutral"],
  [{ status: "superseded" }, "Diganti kartu yang lebih baru", "Diganti", "text-kn-neutral"],
  [{ status: "dismissed" }, "Diabaikan", "Diabaikan", "text-kn-neutral"],
])("hasil kartu %#: teks hasil, pil ikon + teks + warna, tanpa tombol", async (over, hasil, pil, warna) => {
  mockFetch.mockResolvedValue(KARTU(over));
  await mount(<TanyaActionCard proposalId="aiact_9" />);
  expect(q("tanya-card-result").textContent).toBe(hasil);
  expect(q("tanya-action-pill").textContent).toBe(pil);
  expect(q("tanya-action-pill").className).toContain(warna);
  expect(q("tanya-action-pill").querySelector("svg")).not.toBeNull();
  expect(q("tanya-action-confirm")).toBeNull();
});

test("jurnal gagal sesudah berhasil → 'Jurnal gagal — lihat Posting Gagal'", async () => {
  mockFetch.mockResolvedValue({ ...BERHASIL, result: { ...BERHASIL.result, gl_status: "failed" } });
  await mount(<TanyaActionCard proposalId="aiact_9" />);
  expect(q("tanya-card-gl").textContent).toBe("Jurnal gagal — lihat Posting Gagal");
});

test("U18 — tab Tindakan: saringan & kolom sesuai teks; pilih baris → kartu; setujui dari sana", async () => {
  mockList.mockResolvedValue({ items: [KARTU()], total: 1, page: 1, page_size: 20 });
  mockFetch.mockResolvedValue(KARTU());
  mockAsk.mockResolvedValue(true);
  mockConfirm.mockResolvedValue(BERHASIL);
  await mount(<TanyaActions />);
  expect(mockList).toHaveBeenCalledWith("mine", 1, 20);
  const box = ["mine", "others", "done", "failed"].map((k) => q(`tanya-actions-box-${k}`).textContent);
  expect(box).toEqual(["Menunggu saya", "Menunggu orang lain", "Selesai", "Gagal"]);
  const cols = [...q("tanya-actions-table").querySelectorAll("th")].map((th) => th.textContent);
  expect(cols).toEqual(["Tindakan", "PT", "Nominal", "Dibuat", "Berlaku sampai", "Status"]);
  expect(q("tanya-actions-count").textContent).toBe("1 kartu");
  const sel = [...q("tanya-actions-row-aiact_9").querySelectorAll("td")].map(txt);
  expect(sel.slice(0, 3)).toEqual(["Catat kwitansi piutang", "Sukacita", "Rp 5.000.000"]);
  expect(q("tanya-actions-pill-aiact_9").textContent).toBe("Menunggu");
  await act(async () => { q("tanya-actions-open-aiact_9").click(); });
  await flush();
  // INV-UI-08 (gate 15 Nov): kartu yang dipilih tampil di pop-up, bukan diselipkan di bawah daftar.
  expect(q("tanya-actions-card-modal").contains(q("tanya-action-aiact_9"))).toBe(true);
  await act(async () => { ketik(q("tanya-card-reason"), "pelanggan transfer pagi ini"); ketik(q("tanya-card-retype"), "5000000"); });
  await act(async () => { q("tanya-action-confirm").click(); });
  await flush();
  expect(mockAsk.mock.calls[0][0].message.replace(/ /g, " ")).toContain("Rp 5.000.000 untuk Sukacita");
  expect(q("tanya-card-success").textContent).toBe("Berhasil — Kwitansi Pelanggan AR-00007");
  expect(mockList.mock.calls.length).toBeGreaterThanOrEqual(2);     // daftar dimuat ulang sesudah kartu berubah
  await act(async () => { q("tanya-actions-box-others").click(); });
  await flush();
  expect(mockList).toHaveBeenLastCalledWith("others", 1, 20);
});

test("tab Tindakan: memuat, kosong, galat dibedakan", async () => {
  let selesai;
  mockList.mockReturnValue(new Promise((r) => { selesai = r; }));
  await mount(<TanyaActions />);
  expect(q("tanya-actions-loading").textContent).toContain("Memuat kartu…");
  await act(async () => { selesai({ items: [], total: 0, page: 1, page_size: 20 }); });
  await flush();
  expect(q("tanya-actions-empty").textContent).toBe("Belum ada kartu tindakan.");
  expect(q("tanya-actions-table")).toBeNull();
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  mockList.mockReset();
  mockList.mockRejectedValue(new Error("x"));
  await mount(<TanyaActions />);
  expect(q("tanya-actions-error").textContent).toContain("Kartu tindakan tidak bisa dimuat. Coba lagi.");
  expect(q("tanya-actions-empty")).toBeNull();
});

describe("tombol 'Tanya soal layar ini' menurut izin ai_finance.view (bukan nama peran)", () => {
  const masuk = (user) => { setAccessContext(user); localStorage.setItem("kn_user", JSON.stringify(user)); };
  const html = (type = "journal_entry") => renderToStaticMarkup(
    <AskKnButton type={type} id="je_1" label="JU-00001" buttonLabel="Tanya soal layar ini" />);
  test("peran kustom ai.view + ai_finance.view → tampil", () => {
    masuk({ role: "cr_fin", permissions: { ai: ["view"], ai_finance: ["view"] } });
    expect(html()).toContain('data-testid="ask-kn-journal_entry"');
    expect(html()).toContain("Tanya soal layar ini");
  });
  test("ai.view tanpa ai_finance.view → konteks keuangan tidak tampil, konteks umum tetap", () => {
    masuk({ role: "cr_ai", permissions: { ai: ["view"] } });
    for (const t of ["journal_entry", "ar_receipt", "bank_line", "period"]) expect(html(t)).toBe("");
    expect(html("customer")).toContain('data-testid="ask-kn-customer"');
  });
});
