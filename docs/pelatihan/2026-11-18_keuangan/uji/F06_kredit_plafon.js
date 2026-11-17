// F06 — Kredit & Plafon (MEMBACA): antrean keputusan kredit, kartu pelanggan (plafon & eksposur), antrean jatuh tempo.
// Finance hanya melihat (izin `credit_profile.view/update`, `credit_override.view`); memutus = Manajer.
// Data: `b_piutang:izin_kredit` (izin kredit Rp 50 jt dari Sales) + pengajuan profil kredit saat pelanggan dibuat,
// dan `b_piutang:cicilan` (pelanggan kedua yang telat — antrean "Jatuh tempo").
//   node docs/pelatihan/2026-11-18_keuangan/uji/F06_kredit_plafon.js            (peserta bawaan 02)
//   KN_PESERTA=21 node docs/pelatihan/2026-11-18_keuangan/uji/F06_kredit_plafon.js
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp, sleep } = require("./lib");
const { KSC, pelangganPeserta, pilih, bukaMenu, sorot, lepas, klikSorot } = require("./piutang_lib");
const { bersihkanHasil } = require("./piutang_lib");

const NO = peserta("02");

/** Pencarian antrean berjeda (debounce + muat server): tunggu sampai semua baris memuat kata carinya. */
async function tungguSaring(r, q) {
  await r.page.waitForFunction((teks) => {
    const rows = [...document.querySelectorAll('[data-testid^="credit-desk-row-"]')];
    return rows.length > 0 && rows.every((x) => x.innerText.includes(teks));
  }, q, { timeout: 15000 });
  await r.idle(400);
}

(async () => {
  bersihkanHasil("F06");
  const r = await new Run("F06", "Kredit & Plafon — membaca antrean & kartu pelanggan").start();
  const k = kartu(NO);
  const izin = k["b_piutang:izin_kredit"];
  const cic = k["b_piutang:cicilan"];
  const cust = pelangganPeserta(NO);
  try {
    assert(izin && izin.izin_id && cust, `Kartu peserta ${NO} belum punya b_piutang:izin_kredit`);
    const st = mongo(`return (db.credit_overrides.findOne({id:"${izin.izin_id}"},{_id:0,status:1})||{}).status`);
    assert(st === "pending", `izin kredit peserta ${NO} sudah diputus (${st})`);
    const profil = mongo(`return db.credit_profile_requests.findOne({customer_id:"${cust.id}",status:"diajukan"},{_id:0,id:1})`);

    await r.step(1, "Finance", "Masuk → Keuangan › Piutang › Kredit & Plafon; antrean 'Menunggu keputusan', cari 'Latihan NN'",
      `Baris 'Izin kredit' ${rp(izin.nominal)} (pengaju Ayu Marketing)${profil ? " dan 'Ubah Profil' Rp 300.000.000" : ""}; tidak ada tombol Setujui/Tolak`,
      async () => {
        await r.login(akunPeserta(NO));
        await bukaMenu(r, "ar-aging", "credit-overrides", { nama: "menu-kredit" });
        await r.tid("credit-desk-view").waitFor();
        await r.tid("credit-desk-search").fill(`Latihan ${NO} · Toko Kain Peserta`);
        await tungguSaring(r, `Latihan ${NO} · Toko Kain Peserta`);
        const row = r.tid(`credit-desk-row-${izin.izin_id}`);
        await row.waitFor({ timeout: 15000 });
        await r.idle(800);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(/Izin kredit/i.test(t) && t.includes(rp(izin.nominal).replace("Rp ", "")) && /Ayu Marketing/.test(t), `baris izin: ${t}`);
        if (profil) {
          const tp = (await r.tid(`credit-desk-row-${profil.id}`).innerText()).replace(/\s+/g, " ");
          assert(/Ubah Profil/i.test(tp) && /300\.000\.000/.test(tp), `baris profil: ${tp}`);
        }
        assert(await r.page.locator('[data-testid^="credit-desk-approve-"]').count() === 0, "Finance melihat tombol Setujui");
        await sorot(row);
        await klikSorot(r, r.tid(`credit-desk-open-${izin.izin_id}`), "antrean-menunggu-keputusan");
        await lepas(row);
        return t;
      });

    await r.step(2, "Finance", "Klik tautan [Buka kartu pelanggan] pada baris izin kredit",
      "Kartu pelanggan terbuka: plafon kredit berlaku, piutang/eksposur, status kredit; pengajuan yang menunggu tercantum",
      async () => {
        await r.tid("customer-360-name").waitFor({ timeout: 20000 });
        await r.idle(1500);
        const body = (await r.page.locator("body").innerText()).replace(/\s+/g, " ");
        assert((await r.text("customer-360-name")).includes(cust.name), "kartu pelanggan tidak terbuka");
        assert(/EKSPOSUR/i.test(body) && /PLAFON/i.test(body), `isi kartu: ${body.slice(0, 300)}`);
        await r.shot("kartu-pelanggan");
        const fin = await api(akunPeserta(NO));
        const ex = await fin.get(`/customers/${cust.id}/exposure`, KSC);
        r.note("eksposur API: " + JSON.stringify(ex).slice(0, 400));
        return body.slice(0, 400);
      });

    await r.step(3, "Finance", "[Kembali ke daftar] → ganti antrean ke 'Jatuh tempo' → cari 'Cicilan NN'",
      "Pelanggan Cicilan tampil 'Telat 20 hari' dengan nominal cicilan yang lewat jatuh tempo", async () => {
        assert(cic && cic.pelanggan_id, "b_piutang:cicilan tidak ada");
        await klikSorot(r, r.tid("customer-360-back"), "kembali-ke-daftar");
        await r.tid("credit-desk-view").waitFor();
        await r.idle(800);
        await sorot(r.tid("credit-desk-chips"));
        await pilih(r, "credit-desk-chips", /Jatuh tempo/);
        await lepas(r.tid("credit-desk-chips"));
        await r.tid("credit-desk-search").fill(`Cicilan ${NO}`);
        await tungguSaring(r, `Cicilan ${NO}`);
        await r.tid("credit-desk-table-jatuh_tempo").waitFor({ timeout: 15000 });
        await r.idle(1000);
        const t = (await r.tid("credit-desk-table-jatuh_tempo").innerText()).replace(/\s+/g, " ");
        assert(t.includes(cic.pelanggan) && /Telat \d+ hari/i.test(t), `antrean jatuh tempo: ${t.slice(0, 300)}`);
        await r.shot("antrean-jatuh-tempo");
        return t.slice(0, 300);
      });

    await r.step(4, "Finance", "Buka 'Riwayat izin kredit & pengajuan profil' di bawah daftar",
      "Riwayat keputusan kredit PT (hanya baca)", async () => {
        await klikSorot(r, r.tid("credit-desk-history-toggle"), "buka-riwayat");
        await r.tid("credit-desk-history").waitFor({ timeout: 10000 });
        await r.idle(800);
        await r.tid("credit-desk-history").scrollIntoViewIfNeeded();
        await r.shot("riwayat-kredit");
        return (await r.tid("credit-desk-history").innerText()).replace(/\s+/g, " ").slice(0, 200);
      });
  } catch (e) {
    r.note("berhenti: " + e.message);
  }
  await sleep(10);
  await r.finish();
})();
