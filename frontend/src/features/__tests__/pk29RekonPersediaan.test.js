// PK-29 (IV-05, IV-09, K-06) — tab Rekonsiliasi Persediaan tanpa peramban (U15 = uji komponen; uji jalan = integrator):
//  · banner dari server: "{n} PT belum sinkron: {nama}. Total selisih mutlak {rupiah}." (bukan dari jumlah aljabar);
//  · kolom Akun (akun persediaan per PT) + lencana Sinkron / Tidak sinkron (ikon + teks + warna);
//  · tombol Posting Saldo Awal hanya untuk PT aktif yang tidak sinkron dan `trueup_allowed`; alasan mati TERTULIS;
//  · dialog menyebut satu PT dan nominalnya; permintaan tanpa PT di isi (PT dari konteks).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import InventoryReconTab, { TEKS_PILIH_PT, TEKS_SUDAH_SINKRON, bannerText, trueupButtonState, trueupConfirmText }
  from "../finance/InventoryReconTab";

const mockGet = jest.fn();
const mockPost = jest.fn();
const mockAsk = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), defaults: { headers: { common: {} } } },
  API: "/api",
}));
jest.mock("@/services/confirmService", () => ({ askReason: (...a) => mockAsk(...a) }));
jest.mock("../finance/ZeroCostRollsSection", () => () => <div data-testid="zc-stub" />);
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const q = (host, id) => host.querySelector(`[data-testid="${id}"]`);
/** Intl id-ID memisahkan "Rp" dan angka dengan spasi tak-putus (U+00A0) — disamakan untuk perbandingan teks. */
const sp = (s) => String(s || "").replace(/\u00a0/g, " ");
const teks = (host, id) => sp(q(host, id).textContent);
async function settle() { for (let i = 0; i < 4; i += 1) await act(async () => {}); }
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  await settle();
  return { host, root };
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await settle();
}

const PESAN_K06 = "True-up persediaan hanya untuk pengisian saldo awal. PT Uji B sudah punya transaksi persediaan; "
  + "telusuri selisihnya lewat \"Jelaskan selisih\" lalu koreksi dokumennya.";
// Keadaan U1: A lebih 5.000 (masa saldo awal), B kurang 5.000 (sudah bertransaksi) → jumlah aljabar 0
const U1 = {
  rows: [
    { entity_id: "ent_a", entity_name: "PT Uji A", subledger_value: 10000000, gl_balance: 9995000, difference: 5000,
      rounding_only: false, reconciled: false, inventory_accounts: ["1-1300", "1-1301"], trueup_allowed: true,
      trueup_blocked_reason: "" },
    { entity_id: "ent_b", entity_name: "PT Uji B", subledger_value: 8000000, gl_balance: 8005000, difference: -5000,
      rounding_only: false, reconciled: false, inventory_accounts: ["1-1300"], trueup_allowed: false,
      trueup_blocked_reason: PESAN_K06 },
  ],
  total_difference: 0, total_abs_difference: 10000, rows_out_of_sync: 2, rounding_tolerance: 1, reconciled: false,
  roll_statuses: ["available", "in_transit_transfer"],
};
const SINKRON = {
  rows: [{ ...U1.rows[0], gl_balance: 10000000, difference: 0, reconciled: true }],
  total_difference: 0, total_abs_difference: 0, rows_out_of_sync: 0, rounding_tolerance: 1, reconciled: true,
};

function jawab(rekon) {
  mockGet.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/gl/inventory-reconciliation") ? rekon : [] }));
}
const noop = () => {};
const tab = (entity, props = {}) => (
  <InventoryReconTab selectedEntity={entity} entities={[]} onError={noop} onNotice={noop} onChanged={noop} {...props} />);

afterEach(() => { mockGet.mockReset(); mockPost.mockReset(); mockAsk.mockReset(); document.body.innerHTML = ""; });

test("U15 — U1: banner 2 PT belum sinkron (jumlah aljabar 0), lencana di kedua baris, kolom Akun", async () => {
  jawab(U1);
  const { host } = await mount(tab("ent_a"));
  expect(teks(host, "recon-status-banner")).toBe(
    "2 PT belum sinkron: PT Uji A, PT Uji B. Total selisih mutlak Rp 10.000.");
  expect(q(host, "recon-status-banner").querySelector("svg")).not.toBeNull();
  for (const id of ["ent_a", "ent_b"]) {
    const pil = q(host, `recon-sync-${id}`);
    expect(pil.textContent).toBe("Tidak sinkron");
    expect(pil.className).toContain("status-pill");
    expect(pil.querySelector("svg")).not.toBeNull();
    expect(q(host, `recon-explain-${id}`).textContent).toBe("Jelaskan selisih");
  }
  expect(q(host, "recon-accounts-ent_a").textContent).toBe("1-1300, 1-1301");
  const head = [...q(host, "recon-table").querySelectorAll("th")].map((t) => t.textContent);
  expect(head).toEqual(["PT", "Akun", "Nilai fisik (roll × HPP)", "Saldo buku besar", "Selisih", "Status", "Penjelasan"]);
  expect(q(host, "recon-table").className).toContain("head-wrap");
  // angka rupiah tidak terpatah
  expect(q(host, "recon-diff-ent_b").className).toContain("whitespace-nowrap");
  expect(q(host, "recon-diff-ent_b").textContent).toContain("5.000");
  // tombol: PT A aktif, tidak sinkron, boleh → aktif tanpa alasan
  expect(q(host, "recon-post-opening").disabled).toBe(false);
  expect(q(host, "recon-post-reason")).toBeNull();
  expect(q(host, "recon-footnote").textContent).toContain("tersedia, dalam transfer gudang");
  expect(host.textContent).not.toMatch(/in_transit_transfer|Kenapa berselisih/);
});

test("U15 — PT aktif sudah bertransaksi: tombol mati, alasan server tertulis di samping", async () => {
  jawab(U1);
  const { host } = await mount(tab("ent_b"));
  const btn = q(host, "recon-post-opening");
  expect(btn.disabled).toBe(true);
  expect(q(host, "recon-post-reason").textContent).toBe(PESAN_K06);
  expect(btn.getAttribute("aria-describedby")).toBe("recon-post-reason");
});

test("U15 — Semua PT: tombol mati dengan petunjuk; PT sinkron: mati dengan keterangan", async () => {
  jawab(U1);
  let m = await mount(tab("all"));
  expect(q(m.host, "recon-post-opening").disabled).toBe(true);
  expect(q(m.host, "recon-post-reason").textContent).toBe(TEKS_PILIH_PT);
  document.body.innerHTML = "";
  jawab(SINKRON);
  m = await mount(tab("ent_a"));
  expect(q(m.host, "recon-status-banner").textContent).toBe("GL Persediaan sinkron dengan subledger roll.");
  expect(q(m.host, "recon-sync-ent_a").textContent).toBe("Sinkron");
  expect(q(m.host, "recon-post-opening").disabled).toBe(true);
  expect(q(m.host, "recon-post-reason").textContent).toBe(TEKS_SUDAH_SINKRON);
});

test("U15 — dialog menyebut satu PT dan nominal; POST hanya membawa alasan (PT dari konteks)", async () => {
  jawab(U1);
  mockAsk.mockResolvedValue("stok awal gudang utama");
  mockPost.mockResolvedValue({ data: { posted: [{ entity_id: "ent_a", amount: 5000, journal_number: "JE-1" }], count: 1 } });
  const notice = jest.fn();
  const { host } = await mount(tab("ent_a", { onNotice: notice }));
  await click(q(host, "recon-post-opening"));
  const opsi = mockAsk.mock.calls[0][0];
  expect(sp(opsi.message)).toBe("GL Persediaan PT Uji A akan disamakan dengan nilai fisik roll (Rp 5.000), dengan lawan akun "
    + "Ekuitas Saldo Awal. Jurnalnya nyata dan masuk buku besar.");
  expect(opsi.message).not.toMatch(/PT Uji B/);
  const [url, body, cfg] = mockPost.mock.calls[0];
  expect(url).toBe("/api/gl/inventory-opening-balance");
  expect(body).toBeNull();
  expect(cfg.params).toEqual({ reason: "stok awal gudang utama" });
  expect(cfg.headers["Idempotency-Key"]).toMatch(/^invob-/);
  expect(notice).toHaveBeenCalledWith("Saldo awal diposting: 1 jurnal (JE-1).");
});

test("pembantu murni — banner, keadaan tombol, teks dialog", () => {
  expect(sp(bannerText(U1))).toBe("2 PT belum sinkron: PT Uji A, PT Uji B. Total selisih mutlak Rp 10.000.");
  expect(bannerText({ ...SINKRON, total_abs_difference: 0.4 })).toContain("hanya pembulatan sen");
  expect(trueupButtonState("ent_a", U1.rows)).toEqual({ enabled: true, reason: "" });
  expect(trueupButtonState("ent_b", U1.rows)).toEqual({ enabled: false, reason: PESAN_K06 });
  expect(trueupButtonState("all", U1.rows).reason).toBe(TEKS_PILIH_PT);
  expect(sp(trueupConfirmText(U1.rows[1]))).toContain("PT Uji B akan disamakan dengan nilai fisik roll (-Rp 5.000)");
});
