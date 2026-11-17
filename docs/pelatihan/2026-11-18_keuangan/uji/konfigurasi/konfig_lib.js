// Pembantu bersama MODUL 1 — Fondasi & Konfigurasi (K01–K08), Pelatihan Keuangan 18 Nov 2026.
//
// Pola sama dengan skenario F: login lewat LAYAR dengan akun peran, klik tombol yang sama dengan peserta, lalu cocokkan
// LAYAR dan BUKU/PENGATURAN (API atau Mongo). Langkah yang mengubah pengaturan BERSAMA (aturan, pemetaan, naskah, peran)
// selalu memotret keadaan sebelum, mengembalikannya di `finally`, lalu membuktikan keadaan sesudah = sebelum.
//
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K01_bagan_akun.js       (bawaan peserta 11; KN_PESERTA=12 …)
const fs = require("fs");
const path = require("path");
const lib = require("../lib");
const hl = require("../hutang_lib");
const kb = require("../kasbank_lib");

const { mongo, assert, sleep } = lib;
const KSC = "ent_ksc";

/** Tunggu backend menjawab (lingkungan bersama: backend dimuat ulang saat agen lain mengubah kode). */
async function siapServer(batas = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < batas) {
    try { const res = await fetch(lib.API + "/"); if (res.ok) return true; } catch (e) { /* belum siap */ }
    await sleep(1500);
  }
  return false;
}

/** Mulai skenario dengan folder hasil yang bersih (potret lama dari putaran sebelumnya dihapus). Setiap langkah
 * menunggu backend siap dulu, supaya muat-ulang backend di antara langkah tidak terbaca sebagai kegagalan layar. */
async function mulai(code, title) {
  const dir = path.join(process.env.KN_OUT || path.join(__dirname, "..", "hasil"), code);
  fs.rmSync(dir, { recursive: true, force: true });
  await siapServer();
  const r = await new lib.Run(code, title).start();
  const asli = r.step.bind(r);
  r.step = async (...a) => { await siapServer(); return asli(...a); };
  // Halaman yang terbuka tepat saat backend dimuat ulang menampilkan "Tidak bisa menghubungi server" — tunggu backend
  // lalu muat ulang halaman (sekali), supaya langkah tidak gagal karena lingkungan.
  const goAsli = r.go.bind(r);
  r.go = async (...a) => {
    await siapServer();
    await goAsli(...a);
    const putus = await r.page.getByText("Tidak bisa menghubungi server").first().isVisible().catch(() => false);
    if (putus) { await siapServer(); await r.page.reload(); await r.idle(); }
  };
  return r;
}

/** Sorot elemen → potret → lepas sorotan (tanpa klik). */
async function potret(r, loc, name, opts = {}) {
  await hl.sorot(loc);
  const f = await r.shot(name, opts);
  await hl.lepas(loc);
  return f;
}

/** Buka grup menu samping lalu item menu (grup tertutup → buka dulu), dengan potret sorotan item menu. */
async function menuPotret(r, groupId, itemId, name) {
  const item = r.tid(`nav-${itemId}`);
  if (!(await item.isVisible().catch(() => false))) {
    await r.tid(`nav-group-toggle-${groupId}`).click();
    await item.waitFor({ timeout: 8000 });
  }
  await hl.klikPotret(r, item, name);
  await r.idle(800);
}

/** Simpan objek JSON ke folder hasil skenario (bukti sebelum/sesudah). */
function simpanJson(r, nama, data) {
  fs.writeFileSync(path.join(r.dir, nama), JSON.stringify(data, null, 2));
}

/** Bandingkan dua potret (JSON stabil) — kembalikan daftar beda singkat. */
function beda(a, b) {
  const sa = JSON.stringify(a);
  const sb = JSON.stringify(b);
  if (sa === sb) return [];
  const out = [];
  const ka = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
  for (const k of ka) if (JSON.stringify((a || {})[k]) !== JSON.stringify((b || {})[k])) out.push(k);
  return out.length ? out : ["(isi berbeda)"];
}

/** Hapus kunci waktu (updated_at/created_at/updated_by) supaya potret bisa dibandingkan isinya. */
function tanpaWaktu(o) {
  if (Array.isArray(o)) return o.map(tanpaWaktu);
  if (o && typeof o === "object") {
    const out = {};
    for (const k of Object.keys(o).sort()) {
      if (["updated_at", "created_at", "updated_by"].includes(k)) continue;
      out[k] = tanpaWaktu(o[k]);
    }
    return out;
  }
  return o;
}

/** Nilai efektif satu kunci pengaturan untuk PT (lewat API admin, sama dengan yang dibaca mesin). */
async function nilaiConfig(admin, key, entityId = KSC) {
  const d = await admin.get(`/config/effective?q=${encodeURIComponent(key)}&entity_id=${entityId}`);
  const it = (d.items || []).find((x) => x.key === key);
  assert(it, `kunci ${key} tidak ditemukan`);
  return it;
}

/** Potret lapisan simpanan pengaturan PT + global (system_settings) tanpa stempel waktu. */
function potretSystemSettings(scopes = ["global", KSC]) {
  return tanpaWaktu(mongo(`return db.system_settings.find({scope:{$in:${JSON.stringify(scopes)}}},{_id:0}).sort({scope:1}).toArray()`));
}

/** Ulangi panggilan API bila koneksi keep-alive ditutup server ("fetch failed" / "other side closed"). */
async function ulang(fn, kali = 3) {
  for (let i = 1; ; i += 1) {
    try { return await fn(); } catch (e) {
      const putus = /fetch failed|other side closed|ECONNRESET|socket/i.test(String(e && (e.message + (e.cause || ""))));
      if (!putus || i >= kali) throw e;
      await sleep(1500);
    }
  }
}

/** Tunggu sampai kondisi fungsi bernilai benar (polling). */
async function tunggu(fn, pesan, timeout = 15000) {
  const t0 = Date.now();
  let last;
  while (Date.now() - t0 < timeout) {
    try { last = await fn(); if (last) return last; } catch (e) { last = e.message; }
    await sleep(400);
  }
  throw new Error(`${pesan} (terakhir: ${String(last).slice(0, 200)})`);
}

module.exports = { ...hl, pilihNilai: kb.pilih, mulai, siapServer, potret, menuPotret, simpanJson, beda, tanpaWaktu, nilaiConfig, potretSystemSettings, tunggu, ulang, KSC };
