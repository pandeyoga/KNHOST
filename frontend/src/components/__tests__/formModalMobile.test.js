// Fase 3 · P1 (L-03/L-04/L-10) — FormModal/DetailModal LAYAR PENUH di HP (kontrak kelas + CSS), FormSection bernomor
// yang dilipat TANPA melepas isian, dan DesktopOnlyNotice (L-04 kelas C).
import React, { act, useState } from "react";
import fs from "fs";
import path from "path";
import { createRoot } from "react-dom/client";
import FormModal from "../FormModal";
import DetailModal from "../DetailModal";
import FormSection from "../FormSection";
import DesktopOnlyNotice from "../DesktopOnlyNotice";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host; let root;
async function mount(el) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => { root.render(el); });
}
afterEach(async () => { await act(async () => { root.unmount(); }); host.remove(); });
const q = (id) => document.body.querySelector(`[data-testid="${id}"]`);

const CSS = fs.readFileSync(path.join(__dirname, "../../styles/components.css"), "utf8");
/** Isi semua blok `@media (max-width: 640px) { … }` (kurung kurawal bersarang dihitung). */
function mobileBlocks(css) {
  const out = [];
  const re = /@media\s*\(max-width:\s*640px\)\s*\{/g;
  let m;
  while ((m = re.exec(css))) {
    let depth = 1; let i = re.lastIndex;
    while (i < css.length && depth > 0) { if (css[i] === "{") depth += 1; else if (css[i] === "}") depth -= 1; i += 1; }
    out.push(css.slice(re.lastIndex, i - 1));
  }
  return out.join("\n");
}
const ruleOf = (block, selector) => {
  const i = block.indexOf(selector);
  return i < 0 ? "" : block.slice(i, block.indexOf("}", i));
};

test("FormModal: kelas kait layar penuh (kepala/badan/kaki) — API & perilaku lama tetap", async () => {
  const submitted = [];
  await mount(
    <FormModal open title="Pelanggan Baru" testId="cust" onClose={() => {}} onSubmit={() => submitted.push(1)}>
      <div className="grid gap-2 sm:grid-cols-2"><input data-testid="nama" /><input data-testid="npwp" /></div>
    </FormModal>);
  expect(q("cust-overlay").className).toMatch(/\bmodal-overlay\b.*\bkn-modal-overlay\b/);
  expect(q("cust").className).toMatch(/\bkn-modal-card\b/);
  expect(q("cust").querySelector(".kn-modal-head")).not.toBeNull();
  const main = q("cust").querySelector(".kn-modal-main");
  expect(main.tagName).toBe("FORM");                       // onSubmit → satu <form>
  expect(q("cust-body").className).toMatch(/\bkn-modal-body\b/);
  expect(q("cust").querySelector(".kn-modal-foot")).not.toBeNull();
  await act(async () => { q("cust-submit").click(); });
  expect(submitted).toEqual([1]);
  // Isian lengkap: kedua input tetap ada (HP tidak meringkas form).
  expect(q("nama")).not.toBeNull();
  expect(q("npwp")).not.toBeNull();
});

test("FormModal tanpa onSubmit tidak membungkus <form> (komponen ber-form sendiri — tanpa form bersarang)", async () => {
  await mount(<FormModal open title="Aturan" testId="rule" onClose={() => {}}><form data-testid="inner" /></FormModal>);
  expect(q("rule").querySelector(".kn-modal-main").tagName).toBe("DIV");
  expect(q("rule").querySelectorAll("form").length).toBe(1);
});

test("DetailModal: framed & tanpa bingkai mendapat kelas layar penuh, tombol × tetap ada", async () => {
  await mount(<DetailModal framed testId="po" onClose={() => {}}><p>isi</p></DetailModal>);
  expect(q("po-overlay").className).toMatch(/\bkn-modal-overlay\b/);
  expect(q("po").className).toMatch(/\bkn-detail-modal\b.*\bkn-detail-framed\b/);
  expect(q("po").querySelector(".kn-detail-frame")).not.toBeNull();
  expect(q("po-close-x").className).toMatch(/\bkn-detail-close\b/);
  await act(async () => { root.render(<DetailModal testId="ar" onClose={() => {}}><section className="section-card">x</section></DetailModal>); });
  expect(q("ar").className).toMatch(/\bkn-detail-modal\b/);
  expect(q("ar").className).not.toMatch(/kn-detail-framed/);
});

test("CSS ≤640 px: pop-up 100dvh tanpa sudut, kepala/kaki tetap, badan bergulir, grid sm: tanpa kolom dasar → 1 kolom", () => {
  const mobile = mobileBlocks(CSS);
  expect(ruleOf(mobile, ".kn-modal-overlay")).toMatch(/padding:\s*0/);
  const card = ruleOf(mobile, ".kn-modal-card {");
  expect(card).toMatch(/height:\s*100dvh/);
  expect(card).toMatch(/max-width:\s*100%/);
  expect(card).toMatch(/border-radius:\s*0/);
  expect(ruleOf(mobile, ".kn-modal-body {")).toMatch(/max-height:\s*none/);
  expect(ruleOf(mobile, ".kn-modal-foot {")).toMatch(/flex-shrink:\s*0/);
  expect(mobile).toMatch(/\.kn-modal-body :is\(\.sm\\:grid-cols-2/);
  expect(ruleOf(mobile, ".kn-detail-frame {")).toMatch(/height:\s*100dvh/);
  expect(ruleOf(mobile, ".tab-bar {")).toMatch(/flex-wrap:\s*nowrap/);
  expect(ruleOf(mobile, ".tab-bar {")).toMatch(/overflow-x:\s*auto/);
  // Banner kelas C hanya di HP.
  expect(CSS).toMatch(/\.desktop-only-notice \{ display: none; \}/);
  expect(ruleOf(mobile, ".desktop-only-notice {")).toMatch(/display:\s*flex/);
});

test("FormSection: bernomor, dilipat = disembunyikan (isian & nilainya TIDAK dilepas), ringkasan saat terlipat", async () => {
  function Form() {
    const [nama, setNama] = useState("");
    return (
      <FormSection number={2} title="Syarat bayar" subtitle="Termin & limit" collapsible required
        summary="30 hari" testId="sec">
        <input data-testid="termin" value={nama} onChange={(e) => setNama(e.target.value)} />
      </FormSection>
    );
  }
  await mount(<Form />);
  expect(q("sec").querySelector(".form-section-num").textContent).toBe("2");
  expect(q("sec-toggle").getAttribute("aria-expanded")).toBe("true");
  expect(q("sec-summary")).toBeNull();
  await act(async () => {
    const input = q("termin");
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input, "45");
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await act(async () => { q("sec-toggle").click(); });
  expect(q("sec-toggle").getAttribute("aria-expanded")).toBe("false");
  expect(q("sec-body").hidden).toBe(true);
  expect(q("termin")).not.toBeNull();                      // tetap terpasang
  expect(q("sec-summary").textContent).toBe("30 hari");
  await act(async () => { q("sec-toggle").click(); });
  expect(q("termin").value).toBe("45");                    // nilai tidak hilang
});

test("FormSection tanpa collapsible selalu terbuka (tanpa tombol lipat)", async () => {
  await mount(<FormSection number={1} title="Identitas" testId="s1"><input data-testid="a" /></FormSection>);
  expect(q("s1-toggle")).toBeNull();
  expect(q("s1-body").hidden).toBe(false);
});

test("DesktopOnlyNotice: kalimat baku, bisa disembunyikan untuk sesi ini", async () => {
  sessionStorage.clear();
  await mount(<DesktopOnlyNotice testId="coa-notice" />);
  expect(q("coa-notice").getAttribute("role")).toBe("note");
  expect(q("coa-notice").textContent).toMatch(/Layar ini paling nyaman di desktop\./);
  await act(async () => { q("coa-notice-close").click(); });
  expect(q("coa-notice")).toBeNull();
  await act(async () => { root.render(<div><DesktopOnlyNotice testId="coa-notice" /><DesktopOnlyNotice testId="lain" what="Konsolidasi grup" /></div>); });
  expect(q("coa-notice")).toBeNull();
  expect(q("lain").textContent).toMatch(/Konsolidasi grup paling nyaman di desktop\./);
});
