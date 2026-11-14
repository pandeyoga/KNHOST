// KF-T7 — layar memakai angka yang dipakai server untuk nilai yang dulu ditulis mati di kedua sisi:
// lembar cacat per interval (jarak & jumlah minimum titik inspeksi dari `/inspections/meta` → `policy.inspection_points`)
// dan kelompok Pengaturan baru "Keamanan akun & sesi" di layar Integrasi & Sistem.
import React, { act } from "react";
import { createRoot } from "react-dom/client";

// Pemilih bawaan (cmdk/radix) diganti <select> polos.
jest.mock("../../components/KNSelect", () => {
  const S = (p) => (
    <select data-testid={p["data-testid"]} value={p.value || ""} disabled={p.disabled}
      onChange={(e) => p.onValueChange && p.onValueChange(e.target.value)}>
      {(p.options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
  return { __esModule: true, default: S, KNSelect: S };
});

// eslint-disable-next-line import/first
import IntervalDefectGrid, { intervalCount } from "../inspections/IntervalDefectGrid";
// eslint-disable-next-line import/first
import { configViewForGroup, CONFIG_GROUP_VIEWS } from "../settings/config/configGroupViews";
// eslint-disable-next-line import/first
import { CONFIG_GROUPS, groupForKey } from "../settings/config/configDeepLink";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mount(el) {
  const div = document.createElement("div");
  document.body.appendChild(div);
  const root = createRoot(div);
  await act(async () => { root.render(el); });
  return { div, root };
}

describe("KF-T7 — lembar cacat per interval mengikuti Pengaturan", () => {
  test("rumus jumlah titik = server: ⌈panjang ÷ jarak⌉, paling sedikit minimum", () => {
    expect(intervalCount(200)).toBe(14);            // bawaan 15 yard / 10 titik (cadangan)
    expect(intervalCount(200, 10, 10)).toBe(20);    // ⌈200 ÷ 10⌉
    expect(intervalCount(90, 15, 10)).toBe(10);     // ⌈90 ÷ 15⌉ = 6 → minimum 10
    expect(intervalCount(90, 15, 4)).toBe(6);
  });

  test("label kolom & keterangan memakai jarak dari server", async () => {
    const { div, root } = await mount(
      <IntervalDefectGrid length="200" setLength={() => {}} rows={[]} setRows={() => {}} stockUnit="yard" stockQty={200}
        intervalYard={10} minPoints={10} />);
    const note = div.querySelector('[data-testid="ins-stock-unit-note"]').textContent;
    expect(note).toContain("20 interval × 10 yard");
    expect(note).toContain("berlanjut melewati 100");
    expect(div.querySelector('[data-testid="ins-interval-summary"]').textContent).toContain("190–200");
    await act(async () => root.unmount());
  });

  test("tanpa data server: cadangan 15 yard / 10 titik (perilaku lama)", async () => {
    const { div, root } = await mount(
      <IntervalDefectGrid length="150" setLength={() => {}} rows={[]} setRows={() => {}} stockUnit="yard" stockQty={150} />);
    expect(div.querySelector('[data-testid="ins-stock-unit-note"]').textContent).toContain("10 interval × 15 yard");
    await act(async () => root.unmount());
  });
});

describe("KF-T7 — kelompok Keamanan akun & sesi punya rumah", () => {
  test("kelompok `keamanan` di layar Integrasi & Sistem, kuncinya dikenal indeks", () => {
    expect(CONFIG_GROUPS.map((g) => g.id)).toContain("keamanan");
    expect(configViewForGroup("keamanan")).toBe("settings-cfg-system");
    expect(CONFIG_GROUP_VIEWS["settings-cfg-system"].groups).toEqual(["sistem", "keamanan"]);
    expect(groupForKey("keamanan.umur_sesi_jam")).toBe("keamanan");
    expect(groupForKey("ar.overdue_block_days")).toBe("pembayaran-pelanggan");
  });
});
