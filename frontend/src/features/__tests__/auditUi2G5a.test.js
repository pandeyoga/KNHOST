// Audit UI tahap 2 (UAT 24 Okt) — G5a: R&D / desain / desainer / SDM.
// G5-16 catatan tanpa kode keputusan · G5-38 bobot KPI dinormalkan · G5-39/G5-05 gambar gagal → teks fallback ·
// G5-42 dialog ACC tanpa nilai "0" terpilih · G5-29 pemilih karyawan aktif · G5-66 persen id-ID.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { cleanRndNote } from "../rnd/rndMeta";
import ScoreInput from "../rnd/design/ScoreInput";
import DesignImage, { IMAGE_FAIL_TEXT } from "../rnd/design/DesignImage";
import { gradeFormula, normalizedWeights } from "../designer/designerMeta";
import { employeeOptions } from "../hr/leaveUtils";
import { pct } from "../hr/payrollUtils";

// Bukan jest.fn: resetMocks CRA mengosongkan implementasinya sebelum tiap uji.
jest.mock("axios", () => ({ __esModule: true, default: { get: () => Promise.reject(new Error("404")) } }));
jest.mock("../../services/apiClient", () => ({ __esModule: true, default: { get: () => Promise.resolve({ data: {} }) }, API: "/api" }));
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  return { host, root, render: async (node) => { await act(async () => { root.render(node); }); } };
}

test("G5-16 — catatan jenis sample tanpa kode keputusan internal", () => {
  const note = "Hasilnya dinilai dari FOTO hasil cetak + catatan — tidak ada kolom ukur (keputusan pemilik, MD-05). Pemilik boleh menambah kolom ukur.";
  const out = cleanRndNote(note);
  expect(out).not.toMatch(/MD-05|keputusan pemilik/);
  expect(out).toContain("tidak ada kolom ukur. Pemilik boleh");
  expect(cleanRndNote("MEMPERINGATKAN (keputusan pemilik #5).")).toBe("MEMPERINGATKAN.");
  expect(cleanRndNote("")).toBe("");
});

test("G5-38 — porsi bobot nilai desainer dinormalkan ke 100% (setelan 40:40:20:20)", () => {
  const w = { on_time: 40, score: 40, acc: 20, design: 20, penalty_rework: 0.2, penalty_overdue: 0.3 };
  const n = normalizedWeights(w);
  expect(n.total).toBe(120);
  expect(Math.round((n.on_time + n.score + n.acc + n.design) * 10) / 10).toBeCloseTo(100, 0);
  const text = gradeFormula(w);
  expect(text).toContain("33,3%");
  expect(text).toContain("16,7%");
  expect(text).toContain("jumlah 120");
});

test("G5-42 — ScoreInput tanpa nilai: tidak ada segmen terpilih (dulu Number(null) === 0 → '0' terpilih)", async () => {
  const m = mount();
  await m.render(<ScoreInput value={null} onChange={() => {}} minAcc={1.5} testId="s" />);
  expect(m.host.querySelector('[data-testid="s-0"]').className).not.toMatch(/text-white/);
  await m.render(<ScoreInput value={0} onChange={() => {}} minAcc={1.5} testId="s" />);
  expect(m.host.querySelector('[data-testid="s-0"]').className).toMatch(/text-white/);
  act(() => m.root.unmount());
});

test("G5-39 — gambar desain gagal dimuat menampilkan teks fallback (mode ringkas: ikon + tooltip)", async () => {
  const m = mount();
  await m.render(<DesignImage src="/api/design-gallery/x/files/y" alt="Kawung Navy" data-testid="img" />);
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  const el = m.host.querySelector('[data-testid="img"]');
  expect(el.getAttribute("data-image-failed")).toBe("true");
  expect(el.textContent).toContain(IMAGE_FAIL_TEXT);
  expect(el.textContent).not.toContain("Kawung Navy");
  await m.render(<DesignImage src="/api/design-gallery/x/files/z" compact data-testid="img2" />);
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  const el2 = m.host.querySelector('[data-testid="img2"]');
  expect(el2.getAttribute("title")).toBe(IMAGE_FAIL_TEXT);
  act(() => m.root.unmount());
});

test("G5-29 — pemilih karyawan cuti/lembur hanya karyawan aktif", () => {
  const opts = employeeOptions([
    { id: "e1", name: "Budi", code: "K01", status: "active" },
    { id: "e2", name: "Ani", code: "K02", status: "resigned" },
    { id: "e3", name: "Citra", status: "inactive" },
    { id: "e4", name: "Dodi" },
  ]);
  expect(opts.map((o) => o.value)).toEqual(["e1", "e4"]);
  expect(opts[0].label).toBe("Budi (K01)");
});

test("G5-66 — tarif PPh 21 tampil id-ID", () => {
  expect(pct(0.0075)).toBe("0,75%");
  expect(pct(0.05)).toBe("5,00%");
});
