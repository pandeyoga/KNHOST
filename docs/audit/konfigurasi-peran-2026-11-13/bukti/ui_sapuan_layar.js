// Sapuan layar: masuk sebagai satu akun, buka tiap layar lewat tautan `?view=<id>`, catat panggilan API yang gagal,
// galat konsol, dan layar yang jatuh ke batas-galat.
//
//   node ui_sapuan_layar.js <keluaran.json> <views.json> [email] [folder-tangkapan]
//
// Prasyarat: backend `python serve_mem.py` di :8001 dan frontend `yarn start:dev` di :3000 (lihat serve_mem.py).
const { chromium } = require("playwright");
const fs = require("fs");

const BASE = process.env.KN_FE || "http://localhost:3000";
const [OUT, VIEWS_FILE, EMAIL = "admin@kainnusantara.id", SHOTS = ""] = process.argv.slice(2);
const VIEWS = JSON.parse(fs.readFileSync(VIEWS_FILE, "utf8"));
const TANGKAP = new Set((process.env.KN_SHOTS || "").split(",").filter(Boolean));

async function login(page, email) {
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-testid="login-email-input"]', { timeout: 120000 });
  await page.fill('[data-testid="login-email-input"]', email);
  await page.fill('[data-testid="login-password-input"]', "demo12345");
  await page.click('[data-testid="login-submit-button"]');
  await page.waitForSelector('[data-testid="login-screen"]', { state: "detached", timeout: 60000 });
  await page.waitForLoadState("networkidle", { timeout: 60000 }).catch(() => {});
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: "id-ID" });
  const page = await ctx.newPage();
  let bucket = null;
  page.on("response", (r) => {
    const u = r.url();
    if (!bucket || !u.includes("/api/")) return;
    bucket.api += 1;
    if (r.status() >= 400) bucket.gagal.push(`${r.status()} ${r.request().method()} ${u.replace(/^https?:\/\/[^/]+/, "").slice(0, 150)}`);
  });
  page.on("console", (m) => { if (bucket && m.type() === "error") bucket.konsol.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => { if (bucket) bucket.galat.push(String(e).slice(0, 200)); });

  await login(page, EMAIL);
  const hasil = {};
  for (const v of VIEWS) {
    bucket = { api: 0, gagal: [], konsol: [], galat: [] };
    try {
      await page.goto(`${BASE}/?view=${v}`, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle", { timeout: 25000 }).catch(() => {});
      await page.waitForTimeout(600);
      const info = await page.evaluate(() => {
        const t = document.body.innerText || "";
        const judul = (document.querySelector("h1, h2")?.innerText || "").slice(0, 80);
        return {
          panjang: t.length,
          judul,
          login: !!document.querySelector('[data-testid="login-screen"]'),
          batasGalat: /Terjadi kesalahan|Something went wrong|Layar ini gagal dimuat/i.test(t),
          viewAktif: new URLSearchParams(window.location.search).get("view"),
        };
      });
      hasil[v] = { ...info, ...bucket };
      if (SHOTS && (TANGKAP.has(v) || TANGKAP.has("*"))) {
        await page.screenshot({ path: `${SHOTS}/${EMAIL.split("@")[0]}__${v}.png`, fullPage: false });
      }
    } catch (e) {
      hasil[v] = { ...bucket, error: String(e).slice(0, 200) };
    }
    const h = hasil[v];
    if (h.gagal?.length || h.galat?.length || h.batasGalat || h.error) {
      console.log(v, "→", JSON.stringify({ gagal: h.gagal, galat: h.galat, batas: h.batasGalat, err: h.error }).slice(0, 400));
    }
  }
  fs.writeFileSync(OUT, JSON.stringify({ email: EMAIL, hasil }, null, 1));
  await browser.close();
  const n = Object.values(hasil);
  console.log(`layar: ${n.length} · dengan API gagal: ${n.filter((x) => x.gagal?.length).length} · galat halaman: ${n.filter((x) => x.galat?.length).length} · batas-galat: ${n.filter((x) => x.batasGalat).length}`);
})();
