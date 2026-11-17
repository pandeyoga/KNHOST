// Potret PANDUAN NAVIGASI untuk dokumen pelatihan: tiap layar keuangan dibuka lewat menu kiri seperti peserta, lalu
// menu yang diklik ditandai ① (grup), ② (menu), ③ (tab) dengan bingkai merah. Hasil: uji/hasil/_navigasi/<nav>__<tab>.png
// + indeks.json. Daftar layar = NAV di bawah + entri "navigasi" dari src/skenario/*.json.
//   node docs/pelatihan/2026-11-18_keuangan/uji/potret_navigasi.js
const fs = require("fs");
const path = require("path");
const { Run, akunPeserta, peserta } = require("./lib.js");

// [peran, nav_id, tab view id (atau ""), jalur menu]
const NAV = [
  ["finance", "finance-tower", "finance-desk", "Keuangan › Beranda Keuangan › Perlu Tindakan"],
  ["finance", "finance-tower", "finance-tower", "Keuangan › Beranda Keuangan › Posisi"],
  ["finance", "ar-aging", "ar-aging", "Keuangan › Piutang › Saldo & Umur"],
  ["finance", "ar-aging", "collection-worklist", "Keuangan › Piutang › Penagihan & Penerimaan"],
  ["finance", "ar-aging", "payment-plans", "Keuangan › Piutang › Rencana & Denda"],
  ["finance", "ar-aging", "customer-credit", "Keuangan › Piutang › Titipan & Saldo Kredit"],
  ["finance", "ar-aging", "credit-overrides", "Keuangan › Piutang › Kredit & Plafon"],
  ["finance", "accounts-payable", "vendor-bills", "Keuangan › Hutang › Tagihan"],
  ["finance", "accounts-payable", "contra-bons", "Keuangan › Hutang › Kontrabon"],
  ["finance", "accounts-payable", "gr-ir", "Keuangan › Hutang › GR/IR"],
  ["finance", "cash-bank", "bank-accounts", "Keuangan › Kas & Bank › Rekening & Saldo"],
  ["finance", "cash-bank", "cash-management", "Keuangan › Kas & Bank › Transaksi Kas"],
  ["finance", "cash-bank", "bank-reconciliation", "Keuangan › Kas & Bank › Rekonsiliasi"],
  ["finance", "cash-bank", "petty-cash", "Keuangan › Kas & Bank › Kas Kecil"],
  ["finance", "cash-bank", "cash-holdings", "Keuangan › Kas & Bank › Titipan Sales"],
  ["finance", "ledger", "general-ledger", "Akuntansi & Pajak › Buku Besar › Jurnal"],
  ["finance", "ledger", "chart-of-accounts", "Akuntansi & Pajak › Buku Besar › Bagan Akun"],
  ["finance", "tax-hub", "", "Akuntansi & Pajak › Pajak (Faktur Keluaran)"],
  ["finance", "sample-orders", "", "Penjualan › Pesanan Sample"],
  ["finance", "hr-payroll-hub", "", "SDM › Penggajian › Setoran & Pajak"],
  ["finance", "document-center", "doc-trace", "Pusat Dokumen › Jejak Dokumen"],
  ["manager", "closing", "closing", "Akuntansi & Pajak › Tutup Buku › Daftar Periksa & Tutup"],
  ["manager", "closing", "period-unlock", "Akuntansi & Pajak › Tutup Buku › Buka Periode"],
  ["manager", "fin-reports", "financial-statements", "Akuntansi & Pajak › Laporan › Laba-Rugi, Neraca & Arus Kas"],
];

function fromScenarios() {
  const dir = path.join(__dirname, "..", "src", "skenario");
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const f of fs.readdirSync(dir).filter((x) => /^F\d+\.json$/.test(x))) {
    const d = JSON.parse(fs.readFileSync(path.join(dir, f), "utf8"));
    const role = (d.bagian === "B" || /manaj/i.test(d.peran || "")) ? "manager" : "finance";
    for (const n of d.navigasi || []) if (n.nav_id) out.push([n.peran ? (/manaj/i.test(n.peran) ? "manager" : "finance") : role, n.nav_id, n.tab || "", n.menu || ""]);
  }
  return out;
}

// nav_id → groupId sidebar (anak grup yang tertutup tidak dirender, jadi grupnya harus dibuka dulu)
const GROUP = { "finance-tower": "keuangan", "ar-aging": "keuangan", "accounts-payable": "keuangan", "cash-bank": "keuangan",
  "interco-transactions": "keuangan", ledger: "akuntansi", closing: "akuntansi", "fin-reports": "akuntansi", "tax-hub": "akuntansi",
  "fixed-assets": "akuntansi", "sales-orders": "penjualan", "sample-orders": "penjualan", "customers-crm": "penjualan",
  "hr-payroll-hub": "hrd", "hr-kpi-hub": "hrd", "purchase-orders": "pembelian" };

async function mark(page, locator, n) {
  const box = await locator.boundingBox();
  if (!box) return;
  await page.evaluate(({ b, n }) => {
    const o = document.createElement("div");
    o.className = "kn-latih-mark";
    Object.assign(o.style, { position: "fixed", left: `${b.x - 3}px`, top: `${b.y - 3}px`, width: `${b.width + 6}px`,
      height: `${b.height + 6}px`, border: "3px solid #DC2626", borderRadius: "8px", zIndex: 99999, pointerEvents: "none",
      boxShadow: "0 0 0 3px rgba(220,38,38,.18)" });
    const s = document.createElement("div");
    s.className = "kn-latih-mark";
    s.textContent = String(n);
    Object.assign(s.style, { position: "fixed", left: `${b.x + b.width - 6}px`, top: `${b.y - 12}px`, width: "24px", height: "24px",
      borderRadius: "12px", background: "#DC2626", color: "#FFF", font: "700 14px/24px Arial", textAlign: "center",
      zIndex: 100000, pointerEvents: "none", boxShadow: "0 1px 3px rgba(0,0,0,.35)" });
    document.body.appendChild(o); document.body.appendChild(s);
  }, { b: box, n });
}

async function clearMarks(page) {
  await page.evaluate(() => document.querySelectorAll(".kn-latih-mark").forEach((e) => e.remove()));
}

(async () => {
  const seen = new Set();
  const list = [...NAV, ...fromScenarios()].filter(([role, nav, tab]) => {
    const k = `${role}|${nav}|${tab}`;
    if (seen.has(k)) return false;
    seen.add(k); return true;
  });
  const OUT = path.join(__dirname, "hasil", "_navigasi");
  fs.mkdirSync(OUT, { recursive: true });
  const index = {};
  const r = await new Run("_navigasi", "Panduan navigasi").start();
  let who = "";
  for (const [role, nav, tab, menu] of list) {
    const p = r.page;
    try {
      const acct = role === "manager" ? "manager" : akunPeserta(peserta("01"));
      if (who !== acct) { await r.login(acct); who = acct; }
      else { await r.go(role === "manager" ? "manager-home" : "finance-desk"); }
      await clearMarks(p);
      const item = p.getByTestId(`nav-${nav}`).first();
      const grpTog = p.getByTestId(`nav-group-toggle-${GROUP[nav] || "_"}`).first();
      // buka grupnya bila tertutup
      if (!(await item.isVisible().catch(() => false)) && (await grpTog.count())) {
        await grpTog.click();
        await r.idle(400);
      }
      await item.scrollIntoViewIfNeeded();
      await item.click();
      await r.idle(700);
      let n = 1;
      if (await grpTog.count()) await mark(p, grpTog, n++);
      await mark(p, p.getByTestId(`nav-${nav}`).first(), n++);
      if (tab) {
        const t = p.getByTestId(`hub-tab-${tab}`).first();
        if (await t.count()) {
          await t.click(); await r.idle(700);
          await clearMarks(p);
          n = 1;
          if (await grpTog.count()) await mark(p, grpTog, n++);
          await mark(p, p.getByTestId(`nav-${nav}`).first(), n++);
          await mark(p, p.getByTestId(`hub-tab-${tab}`).first(), n++);
        }
      }
      const file = `${role}__${nav}__${tab || "utama"}.png`;
      await p.screenshot({ path: path.join(OUT, file) });
      index[`${role}|${nav}|${tab}`] = { file: `uji/hasil/_navigasi/${file}`, menu, role };
      console.log("✓", menu || `${nav} ${tab}`);
    } catch (e) {
      console.log("✗", menu || `${nav} ${tab}`, String(e.message || e).split("\n")[0]);
    }
  }
  fs.writeFileSync(path.join(OUT, "indeks.json"), JSON.stringify(index, null, 2));
  await r.browser.close();
})();
