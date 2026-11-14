// PK-40 (SL-13, FY-16) — Pusat Pajak: lencana masa "Sudah/Belum dilaporkan", Tandai Sudah Dilaporkan (konfirmasi menyebut
// masa, PT, dan angka rekap), Buka Masa Pajak (pop-up alasan), pembanding buku besar di kartu PPN, dan baris PPh 21
// (dasar bruto kena pajak + beda dengan buku besar). Spesifikasi `docs/blueprint/unit/PK-40.md` bagian Layar / U17.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ConfirmHost from "../../components/ConfirmHost";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import TaxCenterView from "../finance/TaxCenterView";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../services/apiClient", () => ({
  __esModule: true,
  default: {
    get: (...a) => mockGet(...a), post: (...a) => mockPost(...a), delete: () => Promise.resolve({ data: {} }),
    patch: () => Promise.resolve({ data: {} }), put: () => Promise.resolve({ data: {} }),
    defaults: { headers: { common: {} } },
  },
  API: "/api",
  setAuthToken: () => {}, setActiveEntity: () => {}, setLocationScope: () => {},
}));
// Pemilih bawaan (cmdk/radix) diganti isian polos — yang diuji kepala masa dan kartunya.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => <select data-testid={p["data-testid"]} value={p.value || ""} onChange={() => {}} />;
  return { __esModule: true, default: S, KNSelect: S };
});
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};

const ENTS = [{ id: "ent_ksc", legal_name: "PT Kain Suka Cita", short_name: "Sukacita" }];
const MGR = { role: "manager", permissions: { accounting: ["view", "manage"] } };
const LIHAT = { role: "x", permissions: { accounting: ["view"] } };
// Hitungan tangan: keluaran 6.000 × 1.100 = 6.600.000; buku besar 6.601.000 → selisih −1.000; masukan 0.
const SUMMARY = {
  period: "2026-10", periods: ["2026-10"], config: { is_pkp: true },
  entity: { id: "ent_ksc", name: "PT Kain Suka Cita", is_pkp: true },
  ppn: {
    keluaran: { ppn: 6600000, dpp: 60000000, count: 6000, gl_ppn: 6601000, selisih: -1000 },
    masukan: { ppn: 0, dpp: 0, count: 0, gl_ppn: 0, selisih: 0 },
    net_ppn: 6600000, position: "kurang_bayar", masukan_by_supplier: [],
    selisih_note: "Selisih berarti ada jurnal PPN tanpa faktur pajak, atau faktur tanpa jurnal, pada masa ini.",
  },
  pph: { total: 150000, items: [
    { code: "pph21", name: "PPh 21 — Karyawan", basis: "payroll", rate: 0, dpp: 10300000, amount: 150000,
      gl_amount: 140000, selisih: 10000, count: 1, source: "1 penggajian terjurnal · dasar = penghasilan bruto kena pajak slip" },
  ] },
};

const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el, selectedEntity = "ent_ksc") {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => {
    root.render(
      <EntityScopeProvider selectedEntity={selectedEntity} entities={ENTS}>
        {el}
        <ConfirmHost />
      </EntityScopeProvider>);
  });
  await flush();
  return host;
}
async function click(el) {
  await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  await flush();
}
async function type(el, value) {
  const proto = el.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
  await act(async () => {
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}
function routeGet(map) {
  mockGet.mockImplementation((url) => {
    const hit = Object.keys(map).sort((a, b) => b.length - a.length).find((k) => url.endsWith(k));
    const v = hit ? map[hit] : [];
    return Promise.resolve({ data: typeof v === "function" ? v() : v });
  });
}

afterEach(async () => {
  const openCancel = document.body.querySelector(".modal-overlay [data-testid$='-cancel']");
  if (openCancel) await click(openCancel);
  for (const r of roots) await act(async () => { r.unmount(); });
  roots = [];
  mockGet.mockReset(); mockPost.mockReset();
  document.body.innerHTML = "";
});

describe("PK-40 — masa pajak di Pusat Pajak", () => {
  test("Tandai Sudah Dilaporkan: konfirmasi menyebut masa, PT, dan angka; lencana berubah", async () => {
    let terkunci = false;
    routeGet({
      "/tax/summary": SUMMARY,
      "/tax/periods": () => [{ period: "2026-10", locked: terkunci, reported_by: terkunci ? "Manajer Uji" : "",
        reported_at: terkunci ? "2026-11-14T03:00:00+00:00" : "" }],
    });
    mockPost.mockImplementation(() => { terkunci = true; return Promise.resolve({ data: { status: "reported" } }); });
    await mount(<TaxCenterView currentUser={MGR} selectedEntity="ent_ksc" />);
    expect(q("tax-masa-badge").textContent).toBe("Belum dilaporkan");
    await click(q("tax-lock-btn"));
    expect(mockPost).not.toHaveBeenCalled();
    expect(q("tax-lock-confirm-message").textContent).toBe(
      "Tandai masa Oktober 2026 PT Kain Suka Cita sudah dilaporkan? PPN keluaran Rp 6.600.000, PPN masukan Rp 0, "
      + "kurang bayar Rp 6.600.000. Sesudah ini faktur dan rekaman PPh masa ini tidak bisa diubah.");
    await click(q("tax-lock-confirm-cancel"));
    expect(mockPost).not.toHaveBeenCalled();
    await click(q("tax-lock-btn"));
    await click(q("tax-lock-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/tax/periods/2026-10/lock");
    expect(mockPost.mock.calls[0][1]).toEqual({ entity_id: "ent_ksc", note: "" });
    expect(q("tax-masa-badge").textContent).toBe("Sudah dilaporkan");
    expect(q("tax-masa-badge").getAttribute("title")).toMatch(/^oleh Manajer Uji, /);
    expect(q("tax-lock-btn")).toBeNull();
    expect(q("tax-unlock-btn")).not.toBeNull();
  });

  test("Buka Masa Pajak meminta alasan lalu mengirimnya; galat server tampil", async () => {
    routeGet({ "/tax/summary": SUMMARY, "/tax/periods": [{ period: "2026-10", locked: true, reported_by: "A" }] });
    mockPost.mockRejectedValue({ response: { status: 409, data: { detail: "Masa pajak ini baru saja diubah orang lain." } } });
    await mount(<TaxCenterView currentUser={MGR} selectedEntity="ent_ksc" />);
    await click(q("tax-unlock-btn"));
    expect(q("tax-unlock-confirm")).not.toBeNull();
    await type(q("tax-unlock-confirm-reason"), "pembetulan SPT");
    await click(q("tax-unlock-confirm-confirm"));
    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe("/api/tax/periods/2026-10/unlock");
    expect(mockPost.mock.calls[0][1]).toEqual({ entity_id: "ent_ksc", reason: "pembetulan SPT" });
    expect(q("tax-lock-error").textContent).toContain("Masa pajak ini baru saja diubah orang lain.");
  });

  test("Semua PT: tombol mati dengan petunjuk; tanpa accounting.manage: tidak ada tombol", async () => {
    routeGet({ "/tax/summary": { ...SUMMARY, entity: { name: "Semua Entitas" } }, "/tax/periods": [] });
    await mount(<TaxCenterView currentUser={MGR} selectedEntity="all" />, "all");
    expect(q("tax-lock-btn").disabled).toBe(true);
    expect(q("tax-lock-btn").getAttribute("title")).toBe("Pilih satu PT untuk menandai masa pajak");
    // Alasan juga tertulis di samping tombol (tooltip tidak terbaca di layar sentuh).
    expect(q("tax-lock-hint").textContent).toBe("Pilih satu PT untuk menandai masa pajak");
    expect(q("tax-masa-badge").querySelector("svg")).not.toBeNull();   // status = ikon + teks + warna
    for (const r of roots) await act(async () => { r.unmount(); });
    roots = [];
    document.body.innerHTML = "";
    routeGet({ "/tax/summary": SUMMARY, "/tax/periods": [] });
    await mount(<TaxCenterView currentUser={LIHAT} selectedEntity="ent_ksc" />);
    expect(q("tax-masa-badge").textContent).toBe("Belum dilaporkan");
    expect(q("tax-lock-btn")).toBeNull();
    expect(q("tax-unlock-btn")).toBeNull();
  });

  test("Kartu PPN: angka buku besar + selisih; PPh 21: dasar bruto kena pajak + beda dengan buku besar", async () => {
    routeGet({ "/tax/summary": SUMMARY, "/tax/periods": [] });
    await mount(<TaxCenterView currentUser={MGR} selectedEntity="ent_ksc" />);
    const gl = q("tax-kpi-keluaran-gl").textContent.replace(/ /g, " ");
    expect(gl).toContain("Menurut buku besar Rp 6.601.000");
    expect(q("tax-kpi-keluaran-gl-selisih").textContent.replace(/ /g, " ")).toContain("Selisih -Rp 1.000");
    expect(q("tax-kpi-keluaran-gl-selisih").getAttribute("title")).toBe(SUMMARY.ppn.selisih_note);
    expect(q("tax-kpi-masukan-gl")).not.toBeNull();
    expect(q("tax-kpi-masukan-gl-selisih")).toBeNull();
    await click(q("tax-tab-pph"));
    expect(q("tax-pph-basis-pph21").textContent).toBe("Dasar (bruto kena pajak)");
    expect(q("tax-pph-gl-pph21").textContent.replace(/ /g, " ")).toContain("Beda dengan buku besar Rp 10.000");
  });
});
