/**
 * FIX-8 (audit WMS-RFID 9 Nov 2026) — Standar UI Gudang v1 tahap 2 + tampilan tersimpan, sisi klien.
 *  · StatusBadge + kosakata status tunggal (ikon + teks + warna token; istilah lama tidak berubah — K-13).
 *  · EmptyState: memuat / kosong / saringan kosong / galat / TANPA IZIN (B1b UI-49: 403 ≠ kosong; UI-50: memuat ≠ "0").
 *  · Satu pager (KNPager/PagedRows → PaginationBar) & satu kotak cari/tab status.
 *  · Waktu WIB lewat formatter tunggal (B3b INP-15 · G-OUT-01), tanpa id mentah (G-OUT-02), nomor dokumen satu skema
 *    tampilan (UI-58), kepala detail sebaris baku (UI-60).
 *  · Tampilan tersimpan (K-B4-12): pulih bawaan saat dibuka, tanda berubah `*`, simpan tanpa kunci cakupan.
 */
import { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import fs from "fs";
import path from "path";
import StatusBadge from "../../components/StatusBadge";
import EmptyState, { listStateKind, isForbidden } from "../../components/EmptyState";
import PaginationBar from "../../components/PaginationBar";
import KNPager from "../../components/KNPager";
import PagedRows from "../../components/PagedRows";
import ResponsiveTable from "../../components/ResponsiveTable";
import DocNumber, { docNumberText, splitDocNumber } from "../../components/DocNumber";
import SavedViewsMenu from "../../components/SavedViewsMenu";
import useSavedViews, { normalizeViewState, sameViewState } from "../../hooks/useSavedViews";
import { GradeLoadNote } from "../../hooks/useGrades";
import { SearchBox as LcSearchBox, StatusTabs as LcStatusTabs } from "../../components/ListControls";
import { SearchBox as LpSearchBox } from "../../components/ListPageParts";
import { DOMAIN_LABELS, LEGACY_TONE, statusLabel, statusMeta, statusTone } from "../../utils/statusVocab";
import { formatDateTime, formatTime } from "../../utils/formatters";
import { fmtTime, Pill } from "../rfid/rfidShared";
import { rollStatusLabel, RollStatusBadge } from "../wms/inventory/inventoryConstants";
import { statusLabel as transferStatusLabel } from "../wms/transfer/transferConstants";
import { PA_STATUS, statusOf } from "../wms/putawayUtils";
import { shortDateTime } from "../inventory/lots/lotApi";
import { localTs } from "../inspections/InspectionDetailParts";
import TransferList from "../wms/transfer/TransferList";
import RollsTable from "../wms/inventory/RollsTable";
import MakloonPartnerScorePanel from "../purchasing/makloon/MakloonPartnerScorePanel";
import GatePassageHistory from "../rfid/GatePassageHistory";
import PutawayOrdersPanel from "../wms/PutawayOrdersPanel";
import { setAccessContext } from "../../config/roles";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};   // jsdom

let captured = [];
let respond = () => ({ status: 200, data: {} });
const realAdapter = axios.defaults.adapter;
beforeEach(() => {
  captured = [];
  axios.defaults.adapter = async (config) => {
    captured.push(config);
    const r = await respond(config);
    if (r.status >= 400) {
      const err = new Error(`HTTP ${r.status}`);
      err.response = { status: r.status, data: r.data, headers: {}, config };
      err.config = config;
      throw err;
    }
    return { data: r.data, status: r.status, statusText: "OK", headers: r.headers || {}, config };
  };
  setAccessContext({ role: "warehouse", permissions: { data_export: ["view", "export"], wms: ["view"] }, view_resources: {}, hidden_views: [] });
  localStorage.setItem("kn_entity_ctx", JSON.stringify({ entities: [{ id: "ent_ksc", short_name: "Sukacita", doc_prefix: "KSC" }] }));
});
afterEach(() => { setAccessContext(null); localStorage.removeItem("kn_entity_ctx"); document.body.innerHTML = ""; });
afterAll(() => { axios.defaults.adapter = realAdapter; });

async function mount(el) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(el); });
  return { host, root };
}
const $ = (host, sel) => host.querySelector(sel);
const tid = (host, id) => host.querySelector(`[data-testid="${id}"]`);
const click = async (node) => { await act(async () => { node.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };
const flush = async () => { for (let i = 0; i < 6; i += 1) await act(async () => {}); };
const forbidden = { status: 403, data: { detail: "Permission ditolak: grade_master.view" } };
const read = (rel) => fs.readFileSync(path.join(__dirname, "..", "..", rel), "utf8");

describe("Kosakata status tunggal (statusVocab) — istilah lama tidak berubah", () => {
  test("label ranah sama persis dengan peta lama; kode tak dikenal tidak pernah mentah", () => {
    expect(rollStatusLabel("in_transit_transfer")).toBe("Dalam Perjalanan (Transfer)");
    expect(transferStatusLabel("returning")).toBe("Batal — kembali ke asal");
    expect(statusOf({ status: "partially_received" })[1]).toBe("Tiba Sebagian");
    expect(PA_STATUS.draft[1]).toMatch(/Draf/);
    expect(statusLabel("waiting_goods", "task_in")).toBe("Menunggu barang");
    expect(statusLabel("weird_new_code", "roll")).toBe("Weird new code");
    expect(statusLabel("", "roll")).toBe("—");
    expect(Object.keys(DOMAIN_LABELS)).toEqual(expect.arrayContaining(["roll", "transfer", "task_out", "grn", "putaway", "inspection"]));
  });
  test("nada: selesai = berhasil, menunggu = perhatian, ditolak = bahaya, draf = netral, dipesan = khusus; per ranah", () => {
    expect(statusTone("completed")).toBe("success");
    expect(statusTone("waiting_approval")).toBe("warning");
    expect(statusTone("rejected")).toBe("danger");
    expect(statusTone("draft")).toBe("neutral");
    expect(statusTone("reserved", "roll")).toBe("special");
    expect(statusTone("dispatched", "task_out")).toBe("success");
    expect(statusTone("closed", "grn")).toBe("success");
    expect(statusMeta("quarantine", { domain: "roll" })).toEqual({ label: "Karantina", tone: "warning", icon: "shield" });
    expect(LEGACY_TONE["pill-purple"]).toBe("special");
  });
});

describe("StatusBadge — ikon + teks + warna token (tidak pernah warna saja)", () => {
  test("lencana: kelas baku, nada, ikon svg, teks; label layar menang; testid", async () => {
    const { host } = await mount(<div>
      <StatusBadge status="quarantine" domain="roll" testId="a" />
      <StatusBadge status="waiting_approval" label="Menunggu ACC Manajer" testId="b" />
      <StatusBadge tone="special" icon="tag" testId="c">Antar PT</StatusBadge>
    </div>);
    const a = tid(host, "a");
    expect(a.className).toContain("kn-badge");
    expect(a.className).toContain("tone-warning");
    expect(a.querySelector("svg")).not.toBeNull();
    expect(a.textContent).toBe("Karantina");
    expect(tid(host, "b").textContent).toBe("Menunggu ACC Manajer");
    expect(tid(host, "c").getAttribute("data-tone")).toBe("special");
  });
  test("pembungkus lama memakai StatusBadge: Pill RFID, RollStatusBadge", async () => {
    const { host } = await mount(<div><Pill color="red" testId="p">DITAHAN</Pill><RollStatusBadge status="available" /></div>);
    expect(tid(host, "p").className).toContain("tone-danger");
    expect(tid(host, "p").getAttribute("style")).toBeNull();          // dulu warna hex inline
    expect(tid(host, "roll-status-available").className).toContain("tone-success");
  });
  test("CSS lencana memakai token AA (bukan hex)", () => {
    const css = read("styles/standard.css");
    expect(css).toMatch(/\.kn-badge\.tone-warning \{ background: var\(--kn-warning-soft\); color: var\(--kn-warning-text\); \}/);
    expect(css).toMatch(/\.kn-badge\.tone-danger \{ background: var\(--kn-danger-soft\); color: var\(--kn-danger-text\); \}/);
  });
});

describe("EmptyState — memuat ≠ kosong (UI-50), 403 ≠ kosong (UI-49)", () => {
  test("listStateKind memilih keadaan dari state layar", () => {
    expect(listStateKind({ loading: true, count: 0 })).toBe("loading");
    expect(listStateKind({ loading: true, count: 3 })).toBeNull();
    expect(listStateKind({ count: 0 })).toBe("empty");
    expect(listStateKind({ count: 0, filtered: true })).toBe("filtered");
    expect(listStateKind({ error: { response: forbidden } })).toBe("forbidden");
    expect(listStateKind({ error: "Permission ditolak: wms.view" })).toBe("forbidden");
    expect(listStateKind({ error: { response: { status: 500, data: {} } } })).toBe("error");
    expect(isForbidden({ status: 403 })).toBe(true);
  });
  test("lima keadaan tampil berbeda; memuat tidak menyebut 'Belum ada'/'0'; tanpa izin menyebut akses", async () => {
    const retry = jest.fn();
    const reset = jest.fn();
    const { host } = await mount(<div>
      <EmptyState kind="loading" what="transfer" testId="l" />
      <EmptyState kind="empty" what="transfer" testId="e" />
      <EmptyState kind="filtered" what="transfer" onReset={reset} testId="f" />
      <EmptyState kind="error" what="transfer" error={{ response: { status: 500, data: { detail: "Server mati" } } }} onRetry={retry} testId="x" />
      <EmptyState kind="forbidden" what="daftar grade" error={{ response: forbidden }} testId="n" />
    </div>);
    expect(tid(host, "l").textContent).toContain("Memuat transfer");
    expect(tid(host, "l").textContent).not.toMatch(/Belum ada|\b0\b/);
    expect(tid(host, "e").textContent).toContain("Belum ada transfer");
    await click(tid(host, "f-reset"));
    expect(reset).toHaveBeenCalled();
    expect(tid(host, "x").textContent).toContain("Server mati");
    await click(tid(host, "x-retry"));
    expect(retry).toHaveBeenCalled();
    expect(tid(host, "n").textContent).toMatch(/tidak punya akses/i);
    expect(tid(host, "n").textContent).toContain("bukan daftar kosong");
    expect(tid(host, "n").textContent).not.toContain("grade_master.view");   // kode izin tidak bocor
  });
  test("ResponsiveTable: 403 → keadaan tanpa izin (bukan teks kosong); node kosong buatan layar tetap", async () => {
    const cols = [{ key: "a", header: "A" }];
    const { host } = await mount(<div>
      <ResponsiveTable testId="t1" columns={cols} rows={[]} error={{ response: forbidden }} empty="Belum ada data." />
      <ResponsiveTable testId="t2" columns={cols} rows={[]} empty={<span data-testid="own-empty">Kosong khusus</span>} />
      <ResponsiveTable testId="t3" columns={cols} rows={[]} loading />
    </div>);
    expect(tid(host, "t1-error").textContent).toMatch(/tidak punya akses/i);
    expect(tid(host, "t1-empty")).toBeNull();
    expect(tid(host, "own-empty").textContent).toBe("Kosong khusus");
    expect(tid(host, "t3-loading").textContent).toContain("Memuat");
  });
});

describe("Satu pager & satu kotak cari", () => {
  test("PaginationBar memuat pertama: 'Memuat …', bukan 'Tidak ada …' (UI-50 Lot & Silsilah)", async () => {
    const { host } = await mount(<PaginationBar testId="pg" label="lot" total={0} loading />);
    expect(tid(host, "pg-info").textContent).toBe("Memuat lot…");
    const { host: h2 } = await mount(<PaginationBar testId="pg2" label="lot" total={0} />);
    expect(tid(h2, "pg2-info").textContent).toBe("Tidak ada lot");
  });
  test("KNPager & PagedRows merender PaginationBar baku (kelas kn-pager), API lama tetap", async () => {
    const onChange = jest.fn();
    const { host } = await mount(<KNPager page={1} pageSize={10} total={35} onChange={onChange} testId="kp" />);
    expect($(host, ".kn-pager")).not.toBeNull();
    expect(tid(host, "kp-info").textContent).toContain("1–10");
    await click(tid(host, "kp-next"));
    expect(onChange).toHaveBeenCalledWith(2);
    const rows = Array.from({ length: 30 }, (_, i) => ({ id: `r${i}` }));
    const { host: h2 } = await mount(<table><tbody><PagedRows rows={rows} testId="pr">{(r) => <tr key={r.id}><td>{r.id}</td></tr>}</PagedRows></tbody></table>);
    expect($(h2, ".kn-pager-row .kn-pager")).not.toBeNull();
    expect(read("components/KNPager.jsx")).toContain("PaginationBar");
    expect(read("components/KNPager.jsx")).not.toMatch(/className="[^"]*(btn-xs|#6E6E73)/);
  });
  test("ListControls memakai implementasi ListPageParts (satu kotak cari, satu tab status)", async () => {
    const { host } = await mount(<div>
      <LcSearchBox value="ab" onChange={() => {}} testId="s1" placeholder="Cari" />
      <LpSearchBox value="ab" onChange={() => {}} testId="s2" placeholder="Cari" />
      <LcStatusTabs tabs={[{ key: "", label: "Semua", count: 0 }]} value="" onChange={() => {}} testIdPrefix="st" />
    </div>);
    expect(tid(host, "s1").closest(".search-box")).not.toBeNull();
    expect(tid(host, "s2").closest(".search-box")).not.toBeNull();
    expect(tid(host, "s1").getAttribute("aria-label")).toBe("Cari");
    expect(tid(host, "st-all").textContent).toBe("Semua0");            // ListControls lama: angka 0 tetap tampil
    expect(read("components/ListControls.jsx")).not.toMatch(/<input/);
  });
});

describe("Waktu WIB, tanpa id mentah, nomor dokumen satu skema", () => {
  test("formatter tunggal WIB: 22.30 UTC = 05.30 WIB hari berikutnya; RFID/lot/SPK ikut", () => {
    const iso = "2026-11-09T22:30:00Z";
    expect(formatDateTime(iso)).toMatch(/^10 Nov 2026,? 05[.:]30 WIB$/);
    expect(formatTime(iso)).toMatch(/^05[.:]30 WIB$/);
    expect(fmtTime(iso)).toBe(formatDateTime(iso));
    expect(shortDateTime(iso)).toBe(formatDateTime(iso));
    expect(localTs(iso)).toBe(formatDateTime(iso));
    expect(fmtTime("")).toBe("—");
  });
  test("DocNumber: [PT] NOMOR untuk kedua skema; teks = nomor tersimpan; PT tak dikenal → tanpa lencana (bukan id)", async () => {
    expect(splitDocNumber("KSC/PO-00166")).toEqual({ pt: "KSC", no: "PO-00166" });
    expect(docNumberText("PRET-00070", "ent_ksc")).toBe("KSC · PRET-00070");
    const { host } = await mount(<div>
      <DocNumber number="KSC/GRN-00023" testId="d1" />
      <DocNumber number="PRET-00070" entityId="ent_ksc" testId="d2" />
      <DocNumber number="SRET-00167" entityId="ent_lain" testId="d3" />
    </div>);
    expect($(tid(host, "d1"), ".kn-docno-pt").textContent).toBe("KSC");
    expect(tid(host, "d1").textContent).toBe("KSC/GRN-00023");
    expect($(tid(host, "d2"), ".kn-docno-pt").textContent).toBe("KSC");
    expect(tid(host, "d2").getAttribute("title")).toBe("PRET-00070");
    expect($(tid(host, "d3"), ".kn-docno-pt")).toBeNull();
    expect(tid(host, "d3").textContent).not.toContain("ent_");
  });
  test("tidak ada lagi tanggal zona perangkat & cadangan id mentah di berkas yang disentuh", () => {
    for (const rel of ["features/rfid/rfidShared.jsx", "features/wms/RollJourneyPopup.jsx", "features/wms/LoadingCheckPanel.jsx",
      "features/inventory/CycleCount.jsx", "features/inventory/registration/RegistrationDetail.jsx",
      "features/mobile/MobileWarehouseApp.jsx", "features/manager/EscalationManagement.jsx"]) {
      const src = read(rel);
      expect([rel, /new Date\([^)]*\)\.toLocale(Date|Time)?String\(/.test(src)]).toEqual([rel, false]);
      expect([rel, /_at\??\.slice\(0, 1[06]\)/.test(src)]).toEqual([rel, false]);
    }
    expect(read("features/mobile/MobileWarehouseApp.jsx")).not.toMatch(/\|\| (t|r)\.product_id\b/);
    expect(read("features/wms/QCInspection.jsx")).not.toMatch(/\|\| t\.(product|warehouse)_id\b/);
    expect(read("features/inventory/registration/RegistrationDetail.jsx")).not.toMatch(/\{g\.owner_entity_id\}/);
  });
  test("UI-60 — GRN memakai kepala detail sebaris baku; aksi merusak terpisah", () => {
    const src = read("features/wms/grn/GrnDetail.jsx");
    expect(src).toContain("<DetailHeader");
    expect(src).toContain("dangerActions=");
    expect(src).not.toMatch(/<ArrowLeft size=\{16\}/);
    expect(read("components/DetailParts.jsx")).toContain("kn-detail-danger");
  });
});

describe("Layar WMS-RFID — keadaan memuat/galat/tanpa izin", () => {
  test("UI-49 — Skor mitra makloon: 403 tampil 'tanpa akses', bukan 'Belum ada penerimaan'", async () => {
    respond = (c) => (c.url.includes("scorecard") ? forbidden : { status: 200, data: [] });
    const { host } = await mount(<MakloonPartnerScorePanel selectedEntity="ent_ksc" />);
    await flush();
    expect(tid(host, "partner-scorecard-error").textContent).toMatch(/tidak punya akses/i);
    expect(host.textContent).not.toContain("Belum ada penerimaan makloon");
  });
  test("UI-49 — pemilih grade: 403 Master Grade diberi catatan, bukan pilihan kosong diam", async () => {
    const { host } = await mount(<GradeLoadNote error={{ response: forbidden }} testId="g" />);
    expect(tid(host, "g").textContent).toContain("Anda tidak punya akses ke Master Grade Mutu");
    const { host: h2 } = await mount(<GradeLoadNote error={null} testId="g2" />);
    expect(tid(h2, "g2")).toBeNull();
    expect(read("features/inspections/InspectSheetGrid.jsx")).not.toMatch(/catch\(\(\) => setGrades\(\[\]\)\)/);
  });
  test("UI-50 — Riwayat lintasan gerbang: memuat dulu, galat 403 = tanpa akses", async () => {
    let release;
    respond = () => new Promise((r) => { release = r; });
    const { host } = await mount(<GatePassageHistory whId="wh1" />);
    expect(tid(host, "rfid-passage-state").getAttribute("data-kind")).toBe("loading");
    expect(host.textContent).not.toContain("Belum ada rombongan");
    await act(async () => { release({ status: 403, data: { detail: "Permission ditolak: rfid.view" } }); });
    await flush();
    expect(tid(host, "rfid-passage-state").getAttribute("data-kind")).toBe("forbidden");
  });
  test("UI-50 — Perintah Simpan ke Rak: sebelum data datang 'Memuat …', bukan 'Belum ada'", async () => {
    respond = () => new Promise(() => {});
    const { host } = await mount(<PutawayOrdersPanel whId="" selectedEntity="all" />);
    expect(tid(host, "pa-list-state").getAttribute("data-kind")).toBe("loading");
    expect(host.textContent).not.toContain("Belum ada Perintah Simpan ke Rak");
  });
  test("TransferList: 403 → tanpa akses; saringan kosong → Reset; kolom tersembunyi hilang; nomor satu skema", async () => {
    const reset = jest.fn();
    const { host } = await mount(<div>
      <div id="a"><TransferList rows={[]} error={{ response: forbidden }} /></div>
      <div id="b"><TransferList rows={[]} filtered onReset={reset} emptyText="Tidak ada transfer yang cocok dengan saringan." /></div>
    </div>);
    expect($(host, "#a").textContent).toMatch(/tidak punya akses/i);
    await click($(host, "#b [data-testid='transfer-list-state-reset']"));
    expect(reset).toHaveBeenCalled();
    const rows = [{ id: "t1", code: "KSC/TRF-00001", status: "waiting_approval", items: [{ product_name: "Katun" }], requested_by: "Ani" }];
    const { host: h2 } = await mount(<TransferList rows={rows} hidden={["requested_by", "approved_by"]} />);
    expect(h2.textContent).not.toContain("Diajukan");
    expect($(h2, "[data-testid='transfer-code-t1'] .kn-docno-pt").textContent).toBe("KSC");
    expect($(h2, "[data-testid='transfer-status-badge']").className).toContain("kn-badge");
  });
  test("RollsTable: memuat = baris EmptyState, kolom tersembunyi lewat tampilan", async () => {
    const { host } = await mount(<RollsTable loading rolls={[]} />);
    expect(tid(host, "rolls-table-state").getAttribute("data-kind")).toBe("loading");
    const roll = { id: "r1", roll_no: "R-1", product_name: "Katun", status: "available", owner_entity_name: "Sukacita", length_remaining: 10, unit: "m" };
    const { host: h2 } = await mount(<RollsTable rolls={[roll]} hidden={["owner", "pegging"]} />);
    const heads = [...h2.querySelectorAll("th")].map((th) => th.textContent);
    expect(heads).not.toContain("Pemilik");
    expect(heads).not.toContain("Pegging");
    expect(heads).toContain("Lot");
  });
});

describe("Tampilan tersimpan (K-B4-12)", () => {
  function Harness({ onApply }) {
    const [state, setState] = require("react").useState({ filters: {}, sort: null, columns: [], mode: "" });
    const sv = useSavedViews("wms.transfers", {
      state, base: { filters: {}, sort: null, columns: [], mode: "" },
      apply: (st) => { onApply(st); setState(st); },
    });
    return (
      <div>
        <button type="button" data-testid="change" onClick={() => setState((s) => ({ ...s, filters: { status: "approved" } }))}>x</button>
        <SavedViewsMenu sv={sv} testId="sv" columns={[{ key: "items", label: "Barang" }]} hidden={state.columns}
          onColumnsChange={(cols) => setState((s) => ({ ...s, columns: cols }))} />
      </div>
    );
  }
  test("normalisasi: nilai kosong/'all'/false dibuang, kolom diurut", () => {
    expect(normalizeViewState({ filters: { status: "all", line: "", kind: "so", peg_only: false }, columns: ["b", "a"] }))
      .toEqual({ filters: { kind: "so" }, sort: null, columns: ["a", "b"], mode: "" });
    expect(sameViewState({ filters: { status: "all" } }, {})).toBe(true);
  });
  test("bawaan dipulihkan saat daftar dibuka; berubah → '*'; simpan baru mengirim state tanpa kunci cakupan", async () => {
    const view = { id: "sv_1", name: "Menunggu ACC", mine: true, is_default: true, can_edit: true, shared: false,
      state: { filters: { status: "waiting_approval" }, sort: { key: "created_at", dir: "asc" }, columns: [], mode: "" } };
    respond = (c) => {
      if (c.method === "get") return { status: 200, data: { items: [view], default_id: "sv_1", can_share: false } };
      if (c.method === "post") return { status: 200, data: { ...view, id: "sv_2", name: "Disetujui", is_default: false } };
      return { status: 200, data: {} };
    };
    const onApply = jest.fn();
    const { host } = await mount(<Harness onApply={onApply} />);
    await flush();
    expect(onApply).toHaveBeenCalledWith(expect.objectContaining({ filters: { status: "waiting_approval" } }));
    expect(captured[0].params).toEqual({ list_key: "wms.transfers" });
    expect(tid(host, "sv-button").textContent).toContain("Menunggu ACC");
    expect(tid(host, "sv-dirty")).toBeNull();
    await click(tid(host, "change"));
    expect(tid(host, "sv-dirty")).not.toBeNull();
    await click(tid(host, "sv-button"));
    await click(tid(host, "sv-new"));
    const input = tid(host, "sv-name");
    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
      setter.call(input, "Disetujui");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => { tid(host, "sv-form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
    await flush();
    const post = captured.find((c) => c.method === "post");
    const body = JSON.parse(post.data);
    expect(body).toMatchObject({ list_key: "wms.transfers", name: "Disetujui",
      state: { filters: { status: "approved" }, sort: { key: "created_at", dir: "asc" }, columns: [], mode: "" } });
    expect(JSON.stringify(body)).not.toMatch(/entity_id|location/);
  });
  test("pilihan kolom mengubah state tampilan (kolom tersembunyi)", async () => {
    respond = () => ({ status: 200, data: { items: [], default_id: "" } });
    const { host } = await mount(<Harness onApply={() => {}} />);
    await flush();
    await click(tid(host, "sv-button"));
    await click(tid(host, "sv-col-items"));
    expect(tid(host, "sv-col-items").checked).toBe(false);
    expect(tid(host, "sv-dirty")).not.toBeNull();
  });
  test("daftar utama gudang memasang tampilan tersimpan", () => {
    expect(read("features/wms/InventoryStockView.jsx")).toContain('useSavedViews("wms.inventory_rolls"');
    expect(read("features/wms/TransferManagement.jsx")).toContain('useSavedViews("wms.transfers"');
    expect(read("features/wms/OutboundScanInterface.jsx")).toContain('useSavedViews("wms.outbound_tasks"');
  });
});
