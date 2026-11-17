// Pembantu bersama skenario bagian C — HUTANG, PAJAK, SAMPLE BERBAYAR, SETORAN GAJI (F11–F15).
// Hanya membaca layar/DB; perubahan data dikerjakan lewat layar di berkas skenario.
const { assert, mongo, sleep } = require("./lib");

const KSC = "ent_ksc";
const REK_BCA = "BCA Operasional KSC";

/** Pilih opsi KNSelect (Radix Select / combobox cmdk) berdasarkan teks label. */
async function pilih(r, testId, label) {
  await r.tid(testId).click();
  const opt = r.page.getByRole("option", { name: label }).first();
  await opt.waitFor({ timeout: 8000 });
  await opt.click();
  await sleep(300);
}

/** Klik tombol "Ya" pada dialog konfirmasi baku (`askConfirm` → testId `<prefix>-confirm`). */
async function setuju(r, prefix) {
  const b = r.tid(`${prefix}-confirm`);
  await b.waitFor({ timeout: 8000 });
  await b.click();
}

/** Jurnal (tidak void) yang bersumber dari id-id ini, urut terbit. */
function jurnalDari(ids) {
  return mongo(`return db.journal_entries.find({source_id:{$in:${JSON.stringify(ids.filter(Boolean))}},status:{$ne:"void"}},{_id:0})
    .sort({created_at:1}).toArray()`) || [];
}

/** Jurnal seimbang + baris yang diharapkan: [[kode, "D"|"K", nominal], …] (±0,01). Kembalikan ringkasan teks. */
function cekJurnal(je, harap) {
  assert(je && (je.lines || []).length, "jurnal tidak ditemukan");
  const d = je.lines.reduce((s, l) => s + Number(l.debit || 0), 0);
  const k = je.lines.reduce((s, l) => s + Number(l.credit || 0), 0);
  assert(Math.abs(d - k) < 0.01, `jurnal ${je.number} tidak seimbang: D ${d} ≠ K ${k}`);
  for (const [kode, sisi, nom] of harap) {
    const tot = je.lines.filter((l) => l.account_code === kode)
      .reduce((s, l) => s + Number(sisi === "D" ? l.debit || 0 : l.credit || 0), 0);
    assert(Math.abs(tot - nom) < 0.01, `jurnal ${je.number}: akun ${kode} sisi ${sisi} = ${tot}, diharapkan ${nom}`);
  }
  return `${je.number} seimbang D=K=${Math.round(d)} [` + je.lines.map((l) =>
    `${l.account_code} ${l.account_name || ""} ${Number(l.debit) ? "D " + Math.round(l.debit) : "K " + Math.round(l.credit)}`)
    .join(" · ") + "]";
}

/** Kode akun bank/kas di jurnal untuk rekening (lewat pemetaan kas: baris debit/kredit yang bukan lawan). */
function rekening(nama) {
  return mongo(`return db.bank_accounts.findOne({entity_id:"${KSC}",name:${JSON.stringify(nama)}},{_id:0})`);
}

/** Tunggu sampai teks muncul di elemen ber-testid (polling layar). */
async function tungguTeks(r, testId, re, timeout = 15000) {
  const t0 = Date.now();
  let last = "";
  while (Date.now() - t0 < timeout) {
    try { last = (await r.tid(testId).first().innerText()).replace(/\s+/g, " ").trim(); } catch (_) { last = ""; }
    if (re.test(last)) return last;
    await sleep(300);
  }
  throw new Error(`teks ${re} tidak muncul di ${testId} (terakhir: "${last.slice(0, 200)}")`);
}

/** Klik menu samping: buka grup dulu bila itemnya tersembunyi (grup tertutup). */
async function menu(r, groupId, itemId) {
  const item = r.tid(`nav-${itemId}`);
  if (!(await item.isVisible().catch(() => false))) {
    await r.tid(`nav-group-toggle-${groupId}`).click();
    await item.waitFor({ timeout: 8000 });
  }
  await item.click();
  await r.idle(600);
}

/** Sorot elemen yang akan diklik (garis merah) supaya peserta melihat tombolnya di tangkapan layar. */
async function sorot(loc) {
  await loc.first().evaluate((e) => {
    e.scrollIntoView({ block: "center", inline: "nearest" });
    e.style.outline = "3px solid #DC2626"; e.style.outlineOffset = "2px";
  }).catch(() => {});
}
async function lepas(loc) {
  await loc.first().evaluate((e) => { e.style.outline = ""; e.style.outlineOffset = ""; }).catch(() => {});
}
/** Sorot → potret (nama berkas) → lepas sorotan → klik. `opts` diteruskan ke r.shot (mis. {locator}). */
async function klikPotret(r, loc, name, opts = {}) {
  await sorot(loc);
  await r.shot(name, opts);
  await lepas(loc);
  await loc.first().click();
}

module.exports = { KSC, REK_BCA, pilih, setuju, jurnalDari, cekJurnal, rekening, tungguTeks, menu, sorot, lepas, klikPotret };
