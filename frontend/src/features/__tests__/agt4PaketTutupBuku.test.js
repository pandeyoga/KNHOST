// AG-T4 — Paket tutup buku & ringkasan pagi keuangan di Tanya KN (uji komponen; uji jalan peramban U16 terpisah):
// kartu grup Keuangan (12 bulan yang sudah berakhir, banner PT, tombol mati + alasan di "Semua PT"); hasil (kemajuan
// "Menyusun paket… (i dari 12)", daftar lembar "Disertakan" / "Tidak disertakan — {alasan}", baris pemeriksa angka,
// rupiah tidak terpatah, Unduh Excel, galat + Coba lagi); tab Jadwal: tombol ringkasan pagi hanya bila Asisten Keuangan
// menyala, mati + alasan di "Semua PT", jadwal dikirim `kind: finance_morning` harian.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockCreateSchedule = jest.fn(() => Promise.resolve({ id: "aisch_1" }));
jest.mock("../tanya/tanyaApi", () => ({
  __esModule: true,
  createSchedule: (...a) => mockCreateSchedule(...a),
  createMyTemplate: jest.fn(),
  fetchSchedules: () => Promise.resolve([{ id: "s1", kind: "finance_morning", title: "Ringkasan pagi keuangan · PT Kain Suka Cita",
    frequency: "daily", time: "07:00", active: true, next_run_at: "2026-11-15T00:00:00+00:00" }]),
  fetchScheduleRuns: () => Promise.resolve([]),
  runScheduleNow: jest.fn(), updateSchedule: jest.fn(), deleteSchedule: jest.fn(),
}));
jest.mock("../../components/ui/button", () => ({ __esModule: true, Button: ({ children, ...p }) => <button type="button" {...p}>{children}</button> }));
jest.mock("../../components/ui/switch", () => ({ __esModule: true, Switch: () => null }));
jest.mock("../../components/ui/label", () => ({ __esModule: true, Label: ({ children }) => <span>{children}</span> }));
jest.mock("../../components/ui/dialog", () => ({
  __esModule: true,
  Dialog: ({ open, children }) => (open ? <div>{children}</div> : null),
  DialogContent: ({ children, ...p }) => <div {...p}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));
const mockToast = jest.fn();
jest.mock("../../hooks/use-toast", () => ({ __esModule: true, toast: (...a) => mockToast(...a) }));
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});

/* eslint-disable import/first */
import { endedMonths, TanyaClosingPackCard, TanyaClosingPackResult } from "../tanya/TanyaClosingPack";
import { TanyaSchedules } from "../tanya/TanyaSchedules";
import { TanyaTemplateGallery } from "../tanya/TanyaTemplateGallery";
/* eslint-enable import/first */

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
async function flush(n = 6) { for (let i = 0; i < n; i += 1) await act(async () => {}); }
let roots = [];
async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  roots.push(root);
  await act(async () => { root.render(el); });
  await flush();
  return host;
}
async function click(el) { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); }
afterEach(() => {
  roots.forEach((r) => act(() => r.unmount()));
  roots = [];
  document.body.innerHTML = "";
  jest.clearAllMocks();
});

const SECTIONS = [
  ["ringkasan", "Ringkasan"], ["laba_rugi", "Laba-Rugi"], ["neraca", "Neraca"], ["arus_kas", "Arus Kas"],
  ["umur_piutang", "Umur Piutang"], ["umur_hutang", "Umur Hutang"], ["pencocokan", "Pencocokan"], ["antar_pt", "Antar-PT"],
  ["kas_bank", "Kas & Bank"], ["posting_gagal", "Posting Gagal"], ["jurnal_manual", "Jurnal Manual"], ["status_periode", "Status Periode"],
].map(([key, title]) => (key === "umur_hutang"
  ? { key, title, status: "skipped", note: "Tidak disertakan: Anda belum punya akses Hutang Supplier & Kontrabon.", result_id: "r_h" }
  : { key, title, status: "ok", note: "", result_id: `r_${key}` }));
const PACK = (src) => ({ id: "aipack_1", period: "2026-02", period_label: "Februari 2026", entity_label: "PT Kain Suka Cita",
  entity_code: "KSC", sections: SECTIONS, summary: "Laba bersih: Rp 300.000. Total piutang: Rp 7.500.000.",
  summary_source: src, verification: { checked: 2, unmatched: [], ok: true } });

test("bulan pilihan: 12 bulan terakhir yang sudah berakhir (WIB), terbaru dulu", () => {
  const m = endedMonths(new Date("2026-03-01T01:00:00+07:00"));
  expect(m).toHaveLength(12);
  expect(m[0]).toEqual({ value: "2026-02", label: "Februari 2026" });
  expect(m[11]).toEqual({ value: "2025-03", label: "Maret 2025" });
  // 1 Maret 00.30 WIB masih 28 Februari UTC — bulan berjalan dihitung di WIB.
  expect(endedMonths(new Date("2026-02-28T17:30:00Z"))[0].value).toBe("2026-02");
});

test("kartu paket: banner PT, pilihan bulan, Buat paket mengirim bulan terpilih", async () => {
  const onBuild = jest.fn();
  await mount(<TanyaClosingPackCard combined={false} ptLabel="PT Kain Suka Cita" busy={false} onBuild={onBuild} />);
  expect(q("tanya-pack-scope").textContent).toBe("PT: PT Kain Suka Cita");
  const sel = q("tanya-pack-month");
  expect(sel.querySelectorAll("option")).toHaveLength(12);
  await act(async () => { sel.value = sel.options[2].value; sel.dispatchEvent(new Event("change", { bubbles: true })); });
  await click(q("tanya-pack-build"));
  expect(onBuild).toHaveBeenCalledWith(sel.options[2].value);
  expect(q("tanya-pack-combined-reason")).toBeNull();
  expect(q("tanya-pack-build").className).toContain("btn-sm");
});

test("kartu paket di Semua PT: tombol mati dengan alasan tertulis di sampingnya", async () => {
  const onBuild = jest.fn();
  await mount(<TanyaClosingPackCard combined ptLabel="" busy={false} onBuild={onBuild} />);
  expect(q("tanya-pack-build").disabled).toBe(true);
  expect(q("tanya-pack-combined-reason").textContent).toBe("Pilih satu PT. Paket dibuat per PT.");
  expect(q("tanya-pack-scope").textContent).toBe("Semua PT");
});

test("galeri: kartu paket tampil di grup Keuangan walau grup tanpa templat", async () => {
  await mount(<TanyaTemplateGallery groups={["Harian", "Keuangan"]} templates={[]} myTemplates={[]}
    financeCard={<div data-testid="kartu-uji">kartu</div>} />);
  expect(q("kartu-uji")).not.toBeNull();
  expect(document.body.textContent).toContain("Keuangan");
  expect(document.body.textContent).not.toContain("Harian");
});

test("hasil: kemajuan per lembar saat menyusun", async () => {
  await mount(<TanyaClosingPackResult state={{ status: "busy", done: 3, total: 12 }} />);
  expect(q("tanya-pack-busy").textContent).toContain("Menyusun paket… (3 dari 12)");
});

test("hasil: daftar lembar, alasan tidak disertakan, ringkasan otomatis, Unduh Excel", async () => {
  const onDownload = jest.fn();
  await mount(<TanyaClosingPackResult state={{ status: "done", pack: PACK("auto") }} onDownload={onDownload} />);
  expect(q("tanya-pack-sheet-status-laba_rugi").textContent).toBe("Disertakan");
  expect(q("tanya-pack-sheet-status-umur_hutang").textContent).toBe("Tidak disertakan");
  expect(q("tanya-pack-sheet-reason-umur_hutang").textContent).toBe("— Anda belum punya akses Hutang Supplier & Kontrabon.");
  expect(q("tanya-pack-sheet-status-umur_hutang").querySelector("svg")).not.toBeNull();   // ikon + teks + warna
  expect(q("tanya-pack-count").textContent).toBe("Lembar (11 dari 12 disertakan)");
  expect(q("tanya-pack-verify").textContent).toBe("Ringkasan otomatis (angka dari server)");
  expect(q("tanya-pack-result-scope").textContent).toBe("PT: PT Kain Suka Cita");
  // Rupiah: angka satu potong tanpa celah patah ("Rp 300.000" — hanya awalan Rp yang boleh turun baris).
  const nowrap = [...q("tanya-pack-summary-text").querySelectorAll(".whitespace-nowrap")].map((e) => e.textContent);
  expect(nowrap).toEqual(["300.000", "7.500.000"]);
  expect(q("tanya-pack-summary-text").textContent).toBe("Laba bersih: Rp 300.000. Total piutang: Rp 7.500.000.");
  await click(q("tanya-pack-download"));
  expect(onDownload).toHaveBeenCalledWith(expect.objectContaining({ id: "aipack_1" }));
});

test("hasil: ringkasan model terperiksa menyebut jumlah angka yang diperiksa", async () => {
  await mount(<TanyaClosingPackResult state={{ status: "done", pack: PACK("model") }} onDownload={() => {}} />);
  expect(q("tanya-pack-verify").textContent).toBe("Pemeriksa angka: 2 angka diperiksa, semua cocok");
});

test("hasil: galat dengan Coba lagi", async () => {
  const onRetry = jest.fn();
  await mount(<TanyaClosingPackResult state={{ status: "error", error: "Paket tidak bisa disusun. Coba lagi." }} onRetry={onRetry} />);
  expect(q("tanya-pack-error").textContent).toContain("Paket tidak bisa disusun. Coba lagi.");
  await click(q("tanya-pack-retry"));
  expect(onRetry).toHaveBeenCalled();
});

test("jadwal: tombol ringkasan pagi hanya bila Asisten Keuangan menyala; simpan = harian finance_morning", async () => {
  await mount(<TanyaSchedules refreshKey={0} onOpenRun={() => {}} finance={null} />);
  expect(q("tanya-morning-open")).toBeNull();
  expect(document.body.textContent).toContain("Ringkasan pagi keuangan · PT Kain Suka Cita");
  roots.forEach((r) => act(() => r.unmount())); roots = []; document.body.innerHTML = "";

  await mount(<TanyaSchedules refreshKey={0} onOpenRun={() => {}} finance={{ combined: false, label: "PT Kain Suka Cita" }} />);
  await click(q("tanya-morning-open"));
  expect(q("tanya-morning-pt").textContent).toBe("PT: PT Kain Suka Cita");
  expect(q("tanya-morning-time").value).toBe("07:00");
  await click(q("tanya-morning-save"));
  expect(mockCreateSchedule).toHaveBeenCalledWith({ kind: "finance_morning", frequency: "daily", time: "07:00" });
});

test("jadwal di Semua PT: tombol ringkasan pagi mati dengan alasan", async () => {
  await mount(<TanyaSchedules refreshKey={0} onOpenRun={() => {}} finance={{ combined: true, label: "" }} />);
  expect(q("tanya-morning-open").disabled).toBe(true);
  expect(q("tanya-morning-combined-reason").textContent).toBe("Pilih satu PT. Ringkasan pagi dibuat per PT.");
});
