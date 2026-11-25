// MEJA-5 — kartu antrean ukuran tetap & baris ringkas (§5.2, §5.5). Review Focus #1, #2, #3, #4.
// R10: tinggi kartu dihitung dari tinggi nyata bagian-bagiannya (satu konstanta `DESK_CARD_CLASS`), bukan 404 px rencana.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import fs from "fs";
import path from "path";
import { EntityScopeProvider } from "../../context/EntityScopeContext";
import DeskQueueCard, {
  DESK_CARD_CLASS, DESK_ROW_CLASS, DeskQueueCardSkeleton, PAGE_ROWS, inPlaceOf,
} from "../sales_admin/DeskQueueCard";
import { cardStateKey, pageStateKey, readDeskState, writeDeskState } from "../desks/deskSession";

jest.mock("../../components/KNSelect", () => {
  const M = ({ value, onValueChange, options = [], "data-testid": tid, className }) => (
    <select data-testid={tid} className={className} value={value ?? ""} onChange={(e) => onValueChange(e.target.value)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>);
  return { __esModule: true, default: M, KNSelect: M };
});

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);
const teks = (el) => (el ? el.textContent.replace(/\s+/g, " ").trim() : "");
let roots = [];
async function mount(el) {
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(el); }); await act(async () => {});
  return host;
}
const klik = async (id) => act(async () => { q(id).dispatchEvent(new MouseEvent("click", { bubbles: true })); });
const lepasSemua = async () => { for (const r of roots) await act(async () => r.unmount()); roots = []; document.body.innerHTML = ""; };
afterEach(async () => { await lepasSemua(); sessionStorage.clear(); jest.restoreAllMocks(); });

const row = (i, extra = {}) => ({ ref_type: "sales_order", ref_id: `so${i}`, number: `SO-000${i}`, title: `Toko ${i}`,
  subtitle: `Keterangan panjang ${i}`, badge: "reserved", value: 1000 * i, age_days: i, entity_id: "ent_ksc",
  action: "Follow-up", action_kind: "open", ...extra });
const Q = (n, extra = {}) => ({ id: "q1", label: "Antrean Uji", hint: "Penjelasan antrean", count: n,
  rows: Array.from({ length: n }, (_, i) => row(i + 1)), ...extra });
const ENT = (sel, el) => <EntityScopeProvider selectedEntity={sel} entities={[{ id: "ent_ksc", short_name: "KSC" }]}>{el}</EntityScopeProvider>;
const TINGGI = String(DESK_CARD_CLASS || "").split(/\s+/).find((c) => /^sm:h-\[\d+px\]$/.test(c));

test("R10 — tinggi kartu = kepala + bilah saring + 5 baris + kaki (tinggi nyata, satu konstanta)", () => {
  expect(PAGE_ROWS).toBe(5);
  expect(DESK_ROW_CLASS).toBe("sm:h-14");                               // 56 px
  expect(TINGGI).toBeDefined();
  // bingkai 2 · kepala h-11 44 · garis 1 + bilah saring py-2 (16) + kontrol h-8 (32) · garis 1 + 5 × 56 · kaki h-9 36
  expect(Number(TINGGI.match(/\d+/)[0])).toBe(2 + 44 + (1 + 16 + 32) + (1 + PAGE_ROWS * 56) + 36);
});

test("RF#2 — tinggi tetap di semua keadaan; catatan & muat ulang di kaki", async () => {
  await mount(<>
    <DeskQueueCard testPrefix="a" queue={Q(0)} />
    <DeskQueueCard testPrefix="b" queue={Q(1)} />
    <DeskQueueCard testPrefix="c" queue={Q(5)} />
    <DeskQueueCard testPrefix="d" queue={{ ...Q(0), id: "q1" }} loading />
    <DeskQueueCard testPrefix="e" queue={Q(2, { count: 250 })} loading />
    <DeskQueueCard testPrefix="g" queue={Q(7, { count: 250 })} />
    <DeskQueueCardSkeleton testPrefix="f" />
  </>);
  for (const id of ["a-queue-q1", "b-queue-q1", "c-queue-q1", "d-queue-q1", "e-queue-q1", "g-queue-q1", "f-skeleton-0"]) {
    for (const c of String(DESK_CARD_CLASS).split(/\s+/)) expect(q(id).className.split(/\s+/)).toContain(c);
    expect(q(id).className).toContain(TINGGI);
    expect(q(id).className).not.toContain("h-full");
  }
  expect(q("d-loading-q1")).not.toBeNull();
  expect(q("d-loading-q1").querySelectorAll(".animate-pulse")).toHaveLength(5);
  expect(q("f-skeleton-0").querySelectorAll(".animate-pulse").length).toBeGreaterThanOrEqual(5);
  expect(q("a-empty-q1").textContent).toContain("bersih");
  expect(q("c-list-q1").querySelectorAll('[data-testid^="c-row-"]')).toHaveLength(5);
  expect(q("c-pager-q1")).toBeNull();                                   // tepat 5 baris → tanpa pager
  expect(q("e-truncated-q1").closest('[data-testid="e-foot-q1"]')).not.toBeNull();
  expect(teks(q("e-truncated-q1"))).toMatch(/2 tertua dari 250/);
  expect(q("e-truncated-q1").getAttribute("title")).toMatch(/layar daftar/);
  expect(q("e-refreshing-q1").closest('[data-testid="e-foot-q1"]')).not.toBeNull();
  expect(teks(q("e-refreshing-q1"))).toContain("Memuat ulang");
  // kaki satu baris: pager + catatan berdampingan di kaki setinggi tetap
  expect(q("g-pager-q1").closest('[data-testid="g-foot-q1"]')).not.toBeNull();
  expect(q("g-truncated-q1").closest('[data-testid="g-foot-q1"]')).not.toBeNull();
  expect(q("g-foot-q1").className).toContain("h-9");
  expect(q("g-truncated-q1").className).toContain("max-sm:whitespace-normal"); expect(q("g-truncated-q1").className).toContain("sm:truncate");
  for (const p of ["a", "b", "c", "d", "e", "g"]) expect(q(`${p}-foot-q1`)).not.toBeNull();
  // bilah saring tidak membungkus di kartu (≥ 640 px)
  expect(q("g-q-q1-filter").className).toContain("sm:flex-nowrap");
});

test("R18 — klik tetikus pada baris membuka rincian; baris bukan kontrol; Enter pada tombol nomor membuka sekali", async () => {
  await mount(<DeskQueueCard testPrefix="t" queue={Q(2)} />);
  const r1 = q("t-row-so1");
  expect(r1.getAttribute("role")).toBeNull();            // tanpa kontrol bersarang di dalam role=button (ARIA 4.1.2)
  expect(r1.getAttribute("tabindex")).toBeNull();
  expect(r1.getAttribute("aria-label")).toBeNull();
  expect(r1.className).toContain("cursor-pointer");
  expect(r1.className).toContain(DESK_ROW_CLASS);
  // tetikus: klik di area baris (nama pihak) membuka rincian
  await act(async () => { q("t-title-so1").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
  expect(teks(q("t-detail-title"))).toContain("SO-0001 · Toko 1");
  await act(async () => { q("t-detail-close-x").click(); });
  expect(q("t-detail")).toBeNull();
  // papan ketik: nomor dokumen = tombol yang bisa difokus; Enter (keydown lalu click di peramban) membuka SEKALI
  const num = q("t-number-so2");
  expect(num.tagName).toBe("BUTTON");
  expect(num.getAttribute("type")).toBe("button");
  expect(num.className).toContain("link-button");
  num.focus();
  expect(document.activeElement).toBe(num);
  await act(async () => {
    num.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    num.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  expect(document.body.querySelectorAll('[data-testid="t-detail"]')).toHaveLength(1);
  expect(teks(q("t-detail-title"))).toContain("SO-0002");
  await act(async () => { q("t-detail-close-x").click(); });
  // keydown pada baris (tanpa fokus) tidak membuka apa pun — baris bukan kontrol
  await act(async () => { q("t-row-so1").dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })); });
  expect(q("t-detail")).toBeNull();
});

test("RF#1 — tombol aksi, Enter pada tombol, dan tautan judul tidak membuka rincian baris", async () => {
  const onAction = jest.fn();
  const rows = [row(1, { action_kind: "verify", _titleNode: <button type="button" data-testid="judul-link">Toko 1</button> }),
    row(2, { action_kind: "verify", _titleNode: <a href="#x" data-testid="judul-a">Toko 2</a> })];
  await mount(<DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, rows }}
    inPlace={inPlaceOf(["verify"])} onAction={onAction} />);
  await klik("t-action-so1");
  expect(onAction).toHaveBeenCalledTimes(1); expect(q("t-detail")).toBeNull();
  expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), expect.objectContaining({ id: "q1" }));
  // Enter pada tombol: peramban mengirim keydown lalu click — baris tidak ikut membuka, aksi tetap sekali
  await act(async () => {
    const b = q("t-action-so1");
    b.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    b.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  });
  expect(q("t-detail")).toBeNull();
  expect(onAction).toHaveBeenCalledTimes(2);
  await klik("judul-link");
  expect(q("t-detail")).toBeNull();
  await act(async () => { q("judul-a").dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true })); });
  expect(q("t-detail")).toBeNull();
  expect(onAction).toHaveBeenCalledTimes(2);
});

test("aksi pindah layar membuka rincian dulu; aksi di dalam rincian yang menjalankan", async () => {
  const onAction = jest.fn();
  await mount(<DeskQueueCard testPrefix="t" queue={Q(1)} onAction={onAction} />);
  await klik("t-action-so1");
  expect(onAction).not.toHaveBeenCalled(); expect(q("t-detail-action-nav")).not.toBeNull();
  await klik("t-detail-action");
  expect(onAction).toHaveBeenCalledTimes(1);
  expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), expect.objectContaining({ id: "q1" }));
  expect(q("t-detail")).toBeNull();
});

test("baris tanpa aksi sendiri memakai aksi antrean — juga di dalam rincian; tanpa keduanya tanpa tombol", async () => {
  const onAction = jest.fn();
  const rows = [row(1, { action: "" }), row(2, { action: "" })];
  await mount(<DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, action_label: "Putuskan", rows }} onAction={onAction} />);
  expect(teks(q("t-action-so1"))).toBe("Putuskan");
  await klik("t-action-so1");
  expect(teks(q("t-detail-action"))).toContain("Putuskan");
  await klik("t-detail-action");
  expect(onAction).toHaveBeenCalledWith(expect.objectContaining({ ref_id: "so1" }), expect.objectContaining({ id: "q1" }));
  await lepasSemua();
  await mount(<DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 1, rows: [row(1, { action: "" })] }} />);
  expect(q("t-action-so1")).toBeNull();
});

test("tombol sibuk hanya untuk ref_id yang sedang diproses (ref_id kosong tidak ikut macet)", async () => {
  const rows = [row(1), row(2, { ref_id: "", row_key: "kosong" })];
  await mount(<DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, rows }} busyRef="so1" />);
  expect(q("t-action-so1").disabled).toBe(true);
  expect(teks(q("t-action-so1"))).toContain("Memproses");
  await lepasSemua();
  await mount(<DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, rows }} busyRef="" />);
  expect(q("t-action-kosong").disabled).toBe(false);
});

test("RF#3 — PT di baris hanya di mode Semua PT; baris tanpa PT tidak menulis apa pun", async () => {
  const rows = [row(1), row(2, { entity_id: "" })];
  await mount(ENT("all", <DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, rows }} />));
  expect(teks(q("t-entity-so1"))).toBe("KSC");
  expect(q("t-entity-so2")).toBeNull();
  expect(teks(q("t-row-so2"))).not.toMatch(/Semua Entitas|Entitas aktif/);
  await lepasSemua();
  await mount(ENT("ent_ksc", <DeskQueueCard testPrefix="t" queue={{ id: "q1", label: "U", count: 2, rows }} />));
  expect(q("t-entity-so1")).toBeNull();
  expect(teks(q("t-row-so1"))).not.toContain("KSC");
});

test("antrean jumlah: jumlah sekali, tanpa urut nilai; hint di ikon ?; umur lewat tempo; tanpa ±", async () => {
  await mount(<DeskQueueCard testPrefix="t" queue={{ ...Q(3), value_kind: "count",
    rows: [row(1, { age_kind: "overdue", age_days: 8 }), row(2), row(3)] }} />);
  expect(q("t-total-q1")).toBeNull();
  expect([...q("t-q-q1-sort").options].map((o) => o.value)).toEqual(["server", "newest"]);
  expect(document.body.textContent).not.toContain("Penjelasan antrean");
  expect(q("t-hint-q1")).not.toBeNull();
  await klik("t-hint-q1");
  expect(teks(q("t-hint-q1-text"))).toContain("Penjelasan antrean");
  expect(teks(q("t-age-so1"))).toBe("lewat 8 hari");
  expect(teks(q("t-row-so1"))).not.toMatch(/menunggu|masuk/i);
  expect(document.body.textContent).not.toMatch(/masuk ±|menunggu \d/);
  expect(teks(q("t-value-so1"))).toBe("");
  expect(teks(q("t-row-so1"))).not.toContain("Keterangan panjang");       // keterangan hanya di rincian
});

test("antrean uang: urut nilai tersedia; total bertitle label nilai, tanpa label huruf besar", async () => {
  await mount(<DeskQueueCard testPrefix="t" queue={{ ...Q(2), value_kind: "money", value_label: "Sisa tagihan", total_value: 3000 }} />);
  expect([...q("t-q-q1-sort").options].map((o) => o.value)).toEqual(["server", "newest", "value"]);
  expect(q("t-total-q1").getAttribute("title")).toBe("Sisa tagihan");
  expect(q("t-total-q1").className).toMatch(/text-fs-13/);
  expect(q("t-queue-q1").querySelector(".uppercase")).toBeNull();
  expect(teks(q("t-oldest-q1"))).toMatch(/tertua/);
  expect(teks(q("t-count-q1"))).toBe("2");
});

test("huruf: judul 14/600, maks. dua semi-tebal per baris, tanpa font-bold; kontrol saring sama tinggi", async () => {
  await mount(<DeskQueueCard testPrefix="t" queue={Q(2, { rows: [row(1, { badge: "reserved" }), row(2, { badge: "waiting_stock" })] })} />);
  expect(q("t-queue-q1").querySelector("h3").className).toMatch(/text-fs-14.*font-semibold|font-semibold.*text-fs-14/);
  expect(q("t-queue-q1").querySelectorAll(".font-bold")).toHaveLength(0);
  const r = q("t-row-so1");
  expect(r.querySelectorAll(".font-semibold").length).toBeLessThanOrEqual(2);
  expect(r.querySelectorAll(".font-bold").length).toBe(0);
  expect(q("t-number-so1").querySelector(".text-fs-13.font-semibold.text-kn-action")).not.toBeNull();   // 13/600 aksi
  expect(q("t-title-so1").className).not.toMatch(/font-semibold/);
  expect(q("t-badge-so1").className).toMatch(/text-fs-12/); expect(q("t-badge-so1").className).toMatch(/font-medium/);
  expect(q("t-age-so1").className).toMatch(/text-fs-12/); expect(q("t-age-so1").className).toMatch(/font-medium/);
  expect(q("t-action-so1").className).toMatch(/secondary-button/); expect(q("t-action-so1").className).toMatch(/btn-sm/);
  expect(q("t-search-q1").closest("label").className).toContain("h-8");
  expect(q("t-q-q1-status").className).toContain("!h-8");
  expect(q("t-q-q1-sort").className).toContain("!h-8");
});

test("RF#4 — cari/saring/halaman pulih dari sessionStorage walau baris tiba belakangan", async () => {
  const banyak = { id: "q1", label: "U", count: 12, rows: Array.from({ length: 12 }, (_, i) => row(i + 1)) };
  await mount(<DeskQueueCard testPrefix="t" stateKey="uji:q1" queue={banyak} />);
  await klik("t-pager-q1-next");
  expect(JSON.parse(sessionStorage.getItem("kn.meja.kartu.uji:q1")).page).toBe(2);
  await lepasSemua();
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host); roots.push(root);
  await act(async () => { root.render(<DeskQueueCard testPrefix="t" stateKey="uji:q1" loading queue={{ ...banyak, rows: [] }} />); });
  expect(q("t-loading-q1")).not.toBeNull();
  expect(JSON.parse(sessionStorage.getItem("kn.meja.kartu.uji:q1")).page).toBe(2);   // daftar kosong tidak menimpa halaman
  await act(async () => { root.render(<DeskQueueCard testPrefix="t" stateKey="uji:q1" queue={banyak} />); });
  expect(q("t-row-so6")).not.toBeNull();            // halaman 2 = baris 6–10
  expect(q("t-row-so1")).toBeNull();
  expect(JSON.parse(sessionStorage.getItem("kn.meja.kartu.uji:q1")).page).toBe(2);
  const input = q("t-search-q1");
  await act(async () => { Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "SO-0003");
    input.dispatchEvent(new Event("input", { bubbles: true })); });
  const s = JSON.parse(sessionStorage.getItem("kn.meja.kartu.uji:q1"));
  expect(s.q).toBe("SO-0003"); expect(s.page).toBe(1);
});

test("RF#4 — saringan status & urutan tersimpan dipakai saat kartu dipasang ulang; kartu lain tidak terpengaruh", async () => {
  const rows = [row(1, { badge: "reserved" }), row(2, { badge: "waiting_stock" }), row(3, { badge: "waiting_stock" })];
  writeDeskState(cardStateKey("uji:q1"), { st: "waiting_stock", sort: "newest", q: "" });
  await mount(<>
    <DeskQueueCard testPrefix="t" stateKey="uji:q1" queue={{ id: "q1", label: "U", count: 3, rows }} />
    <DeskQueueCard testPrefix="u" stateKey="uji:q2" queue={{ id: "q1", label: "U", count: 3, rows }} />
  </>);
  expect(q("t-q-q1-status").value).toBe("waiting_stock");
  expect(q("t-q-q1-sort").value).toBe("newest");
  const nums = (p) => [...document.body.querySelectorAll(`[data-testid^="${p}-number-"]`)].map((e) => teks(e));
  expect(nums("t")).toEqual(["SO-0002", "SO-0003"]);
  expect(nums("u")).toEqual(["SO-0001", "SO-0002", "SO-0003"]);
});

test("RF#4 — status tersimpan yang tidak ada lagi di baris dilepas; halaman tersimpan di luar jangkauan diabaikan", async () => {
  writeDeskState(cardStateKey("uji:q1"), { st: "hilang", page: 4 });
  await mount(<DeskQueueCard testPrefix="t" stateKey="uji:q1" queue={Q(7)} />);
  expect(q("t-row-so1")).not.toBeNull();
  await klik("t-pager-q1-next");
  expect(readDeskState(cardStateKey("uji:q1")).page).toBe(2);
  expect(readDeskState(cardStateKey("uji:q1")).st).toBe("");
});

test("deskSession: kunci baku; baca/tulis aman bila penyimpanan rusak atau diblokir", async () => {
  expect(cardStateKey("finance:uang_masuk")).toBe("kn.meja.kartu.finance:uang_masuk");
  expect(pageStateKey("finance")).toBe("kn.meja.finance");
  writeDeskState("kn.meja.uji", { a: 1 }); writeDeskState("kn.meja.uji", { b: 2 });
  expect(readDeskState("kn.meja.uji")).toEqual({ a: 1, b: 2 });
  sessionStorage.setItem("kn.meja.rusak", "{bukan json");
  expect(readDeskState("kn.meja.rusak")).toEqual({});
  sessionStorage.setItem("kn.meja.larik", "[1,2]");
  expect(readDeskState("kn.meja.larik")).toEqual({});
  jest.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("diblokir"); });
  jest.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("diblokir"); });
  expect(readDeskState("kn.meja.uji")).toEqual({});
  expect(() => writeDeskState("kn.meja.uji", { c: 3 })).not.toThrow();
  await mount(<DeskQueueCard testPrefix="t" stateKey="uji:q1" queue={Q(7)} />);
  await klik("t-pager-q1-next");
  expect(q("t-row-so6")).not.toBeNull();
});

test("tanpa px mentah dan hex di kartu & kamus meja", () => {
  for (const rel of ["../sales_admin/DeskQueueCard.jsx", "../sales_admin/workDeskApi.js", "../desks/DeskRowDetail.jsx",
    "../desks/DeskBadge.jsx", "../desks/deskSession.js"]) {
    const src = fs.readFileSync(path.join(__dirname, rel), "utf8");
    expect(src).not.toMatch(/text-\[\d/);
    expect(src).not.toMatch(/#[0-9A-Fa-f]{6}\b/);
  }
  expect(fs.readFileSync(path.join(__dirname, "../sales_admin/workDeskApi.js"), "utf8")).not.toMatch(/sinceFromAge/);
});
