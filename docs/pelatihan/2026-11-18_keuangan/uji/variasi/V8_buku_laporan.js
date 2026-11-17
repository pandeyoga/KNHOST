// V8 — Variasi isian BUKU BESAR (F16), LAPORAN KEUANGAN (F17), TUTUP BUKU (F18).
//   KN_PESERTA=79 KN_PESERTA_TAGIHAN=78 node docs/pelatihan/2026-11-18_keuangan/uji/variasi/V8_buku_laporan.js
// Buku Besar: cari jurnal dengan berbagai bentuk nomor; Buku Besar akun & Neraca Saldo dihitung ulang dari jurnal.
// Laporan (Manajer): Laba-Rugi / Neraca / Arus Kas bulan ini, Oktober, satu hari — dihitung ulang dari `journal_entries`.
// Tutup Buku: hanya September 2026 (diperiksa KOSONG dulu) → tutup → bayar tagihan bertanggal September ditolak →
// usul buka periode tanpa alasan ditolak → Admin buka kembali → keadaan periode SAMA dengan sebelum uji.
const { Run, assert, rp, kartu, akunPeserta, mongo, api, sleep } = require("../lib");
const { KSC, menu, saldoAkun, labaRugiDb, neracaDb, uang, cocokBerulang, dekat, pilih } = require("../buku_lib");
const { REK_BCA, pilih: pilihOpsi } = require("../hutang_lib");
const { ketik, pilihTanggal, Tabel } = require("./hpg_lib");

const NO = String(process.env.KN_PESERTA || "79").padStart(2, "0");
const NO_TG = String(process.env.KN_PESERTA_TAGIHAN || "78").padStart(2, "0");
const tabel = new Tabel("V8");
const last = (r) => r.steps[r.steps.length - 1];
const catat = (r, row) => tabel.add({ ...row, hasil: last(r).ok ? (row.hasil || "lulus") : "gagal",
  catatan: (row.catatan || "") + (last(r).ok ? "" : ` · GAGAL: ${last(r).info}`) });
const HARI_INI = new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 10);
const AWAL_BULAN = HARI_INI.slice(0, 8) + "01";
const TUTUP = process.env.KN_TUTUP || "2026-09";

async function tungguTotal(r) {
  await r.page.waitForFunction(() => !document.querySelector('[data-testid="gl-journal-loading"]'), null, { timeout: 15000 }).catch(() => {});
  await r.idle(900);
  return (await r.text("gl-journal-total")).trim();
}

/** Neraca saldo dari jurnal sampai tanggal: Σ saldo debit / Σ saldo kredit per akun (sama dengan kolom layar). */
function neracaSaldo(end) {
  const net = Object.values(saldoAkun(null, { end }));
  return { d: net.filter((v) => v > 0).reduce((a, v) => a + v, 0), c: -net.filter((v) => v < 0).reduce((a, v) => a + v, 0) };
}

async function bukuBesar(r) {
  const LAYAR = "Akuntansi & Pajak › Buku Besar";
  const j = kartu(NO)["e_buku:so_jejak"];
  const jeRcp = j.jurnal_terima.split(",")[0].trim();
  const je = mongo(`return db.journal_entries.findOne({number:"${jeRcp}",entity_id:"${KSC}"},{_id:0,id:1,number:1})`);
  await r.step("B1", "Finance", `Login peserta ${NO} → Akuntansi & Pajak › Buku Besar (tab Jurnal)`, "Daftar jurnal tampil", async () => {
    await r.login(akunPeserta(NO));
    await menu(r, "akuntansi", "ledger");
    await r.tid("gl-view").waitFor();
    return await tungguTotal(r);
  });
  const nomor = j.kwitansi;                  // KSC/AR-000NN
  const tanpaAwalan = nomor.replace(/^KSC\//, "");
  const angka = nomor.replace(/^.*-/, "");
  const kasus = [
    [nomor, "persis", true, "lulus"],
    [nomor.toLowerCase(), "huruf kecil", true, "lulus"],
    [tanpaAwalan, "tanpa awalan PT", true, "lulus"],
    [angka, "angka saja (sebagian)", true, "lulus"],
    [`  ${nomor}  `, "dengan spasi di depan/belakang", true, "lulus"],
    [jeRcp.replace(/^KSC\//, "").toLowerCase(), "nomor jurnal tanpa awalan, huruf kecil", true, "lulus"],
    ["zzz-tidak-ada", "tidak ada yang cocok", false, "lulus"],
  ];
  let i = 2;
  for (const [masukan, ket, ada, hasil] of kasus) {
    await r.step(`B${i++}`, "Finance", `*Cari nomor jurnal / keterangan…*: "${masukan}" (${ket})`,
      ada ? `Jurnal ${jeRcp} tampil` : "Pesan kosong \"Tidak ada jurnal yang cocok dengan …\" (tanpa galat)", async () => {
        await r.tid("gl-journal-search").fill(masukan);
        const tot = await tungguTotal(r);
        if (!ada) {
          const t = await r.text("gl-journal-empty");
          assert(/Tidak ada jurnal yang cocok/.test(t), `layar: ${t}`);
          return `${tot} · ${t}`;
        }
        await r.tid(`gl-journal-row-${je.id}`).waitFor({ timeout: 8000 });
        return `${tot} · ${jeRcp} tampil`;
      });
    catat(r, { layar: `${LAYAR} › Jurnal`, isian: "Cari", masukan: JSON.stringify(masukan), harap: ada ? `${jeRcp} ditemukan` : "kosong, pesan jelas", hasil,
      catatan: last(r).info });
  }
  await r.tid("gl-journal-search").fill("");

  await r.step(`B${i++}`, "Finance", "Tab [Buku Besar] → akun 1-1200 → *Dari* 1 bulan ini, *Sampai* hari ini",
    "Saldo akhir = saldo 1-1200 di jurnal s/d hari ini; Saldo awal = saldo s/d kemarin bulan lalu", async () => {
      await r.tid("gl-tab-ledger").click();
      await r.idle(500);
      await pilih(r, "gl-ledger-account", "1-1200", "1-1200");
      await pilihTanggal(r, "gl-ledger-start", AWAL_BULAN);
      await pilihTanggal(r, "gl-ledger-end", HARI_INI);
      return await cocokBerulang(async () => {
        await r.idle(800);
        const bal = await r.text("gl-ledger-balance");
        const v = uang((bal.match(/Saldo akhir\s+(.*)$/) || [])[1] || bal);
        const gl = saldoAkun(["1-1200"], { end: HARI_INI })["1-1200"] || 0;
        return { ok: dekat(v, gl, 2), info: `${bal} · jurnal 1-1200 s/d ${HARI_INI} ${rp(gl)}` };
      }, { muatUlang: async () => { await r.tid("gl-refresh").click(); await r.idle(1200); } });
    });
  catat(r, { layar: `${LAYAR} › Buku Besar`, isian: "Akun + rentang", masukan: `1-1200 · ${AWAL_BULAN} s/d ${HARI_INI}`, harap: "saldo akhir = jurnal" });

  await r.step(`B${i++}`, "Finance", `Coba pilih *Dari* sesudah *Sampai* (rentang terbalik)`, "Tanggal sesudah 'Sampai' tidak bisa dipilih di kalender", async () => {
    const besok = new Date(Date.parse(HARI_INI) + 86400e3).toISOString().slice(0, 10);
    let pesan = "";
    try { await pilihTanggal(r, "gl-ledger-start", besok); } catch (e) { pesan = e.message; }
    await r.page.keyboard.press("Escape");
    assert(/dikunci kalender/.test(pesan), `tanggal ${besok} bisa dipilih sebagai 'Dari' padahal 'Sampai' ${HARI_INI}`);
    return pesan;
  });
  catat(r, { layar: `${LAYAR} › Buku Besar`, isian: "Dari > Sampai", masukan: "besok s/d hari ini", harap: "tidak bisa dipilih" });

  await r.step(`B${i++}`, "Finance", "Tab [Neraca Saldo] per hari ini, lalu per 31 Oktober 2026",
    "Total Debit = Total Kredit = Σ saldo debit (dan Σ saldo kredit) semua akun dari jurnal", async () => {
      await r.tid("gl-tab-trial").click();
      await r.tid("gl-trial-total-debit").waitFor();
      const out = [];
      for (const tgl of [HARI_INI, "2026-10-31"]) {
        if (tgl !== HARI_INI) await pilihTanggal(r, "gl-trial-asof", tgl);
        out.push(await cocokBerulang(async () => {
          await r.idle(1000);
          const d = uang(await r.text("gl-trial-total-debit"));
          const c = uang(await r.text("gl-trial-total-credit"));
          const ns = neracaSaldo(tgl);
          return { ok: dekat(d, c) && dekat(d, ns.d, 2) && dekat(c, ns.c, 2), info: `${tgl}: layar D ${rp(d)} / K ${rp(c)} · jurnal D ${rp(ns.d)} / K ${rp(ns.c)}` };
        }, { muatUlang: async () => { await r.tid("gl-refresh").click(); await r.idle(1200); } }));
      }
      return out.join(" · ");
    });
  catat(r, { layar: `${LAYAR} › Neraca Saldo`, isian: "Per tanggal", masukan: `${HARI_INI} dan 2026-10-31`, harap: "total = hitung ulang jurnal" });
}

async function laporan(r) {
  const LAYAR = "Akuntansi & Pajak › Laporan";
  await r.step("L1", "Manajer", "Login manager → PT Sukacita → Laporan › Laba-Rugi → [Rentang Tanggal] 1 Oktober – 31 Oktober 2026",
    "Pendapatan, HPP, Beban, Laba Bersih = jumlah jurnal Oktober per kelompok akun", async () => {
      await r.login("manager");
      const sw = r.tid("entity-switcher");
      if (await sw.count()) {
        const lbl = await r.text("entity-switcher");
        if (!/Sukacita/.test(lbl) || /Semua/.test(lbl)) { await sw.click(); await r.tid(`entity-option-${KSC}`).click(); await r.idle(1200); }
      }
      await menu(r, "akuntansi", "fin-reports");
      await r.tid("financial-statements-view").waitFor();
      await r.tid("fs-pl-mode-range").click();
      await pilihTanggal(r, "fs-pl-start", "2026-10-01");
      await pilihTanggal(r, "fs-pl-end", "2026-10-31");
      return await bandingLR(r, "2026-10-01", "2026-10-31");
    });
  catat(r, { layar: `${LAYAR} › Laba-Rugi`, isian: "Rentang tanggal", masukan: "2026-10-01 s/d 2026-10-31", harap: "= jurnal Oktober" });

  await r.step("L2", "Manajer", `Laba-Rugi satu hari: *Dari* = *Sampai* = ${HARI_INI}`, "= jurnal hari ini", async () => {
    await pilihTanggal(r, "fs-pl-end", HARI_INI);
    await pilihTanggal(r, "fs-pl-start", HARI_INI);
    return await bandingLR(r, HARI_INI, HARI_INI);
  });
  catat(r, { layar: `${LAYAR} › Laba-Rugi`, isian: "Rentang tanggal", masukan: `${HARI_INI} s/d ${HARI_INI}`, harap: "= jurnal satu hari" });

  await r.step("L3", "Manajer", "Coba *Dari* sesudah *Sampai* (rentang terbalik)", "Tanggal tidak bisa dipilih (dulu bisa → semua angka Rp 0 tanpa pesan); API menolak \"Tanggal awal tidak boleh sesudah tanggal akhir.\"", async () => {
    await pilihTanggal(r, "fs-pl-start", "2026-10-01");
    await pilihTanggal(r, "fs-pl-end", "2026-10-31");
    let pesan = "";
    try { await pilihTanggal(r, "fs-pl-start", "2026-11-05"); } catch (e) { pesan = e.message; }
    await r.page.keyboard.press("Escape");
    assert(/dikunci kalender/.test(pesan), "tanggal awal sesudah tanggal akhir masih bisa dipilih");
    const m = await api("manager");
    let api400 = "";
    try { await m.get(`/finance/income-statement?entity_id=${KSC}&start=2026-11-05&end=2026-10-31`, KSC); } catch (e) { api400 = `${e.status} ${e.detail}`; }
    assert(/^400 Tanggal awal tidak boleh sesudah tanggal akhir/.test(api400), `API: ${api400 || "diterima"}`);
    return `${pesan} · API ${api400}`;
  });
  catat(r, { layar: `${LAYAR} › Laba-Rugi / Arus Kas / Perubahan Ekuitas`, isian: "Dari > Sampai", masukan: "2026-11-05 s/d 2026-10-31", harap: "tidak bisa dipilih / ditolak jelas",
    hasil: "diperbaiki", catatan: "dulu kalender 'Dari' tanpa batas → laporan Rp 0 semua tanpa pesan; kini max = Sampai (3 tab) + server 400" });

  for (const [kode, tgl] of [["L4", HARI_INI], ["L5", "2026-10-31"]]) {
    await r.step(kode, "Manajer", `Tab [Neraca] per ${tgl}`, "Total Aset = Kewajiban + Ekuitas (termasuk laba berjalan) = hitung ulang jurnal", async () => {
      await r.tid("fs-tab-bs").click();
      await r.tid("fs-bs-total-assets").waitFor({ timeout: 20000 });
      if (tgl !== HARI_INI) await pilihTanggal(r, "fs-bs-asof", tgl);
      return await cocokBerulang(async () => {
        await r.idle(1000);
        const a = uang(await r.text("fs-bs-total-assets"));
        const l = uang(await r.text("fs-bs-total-liab"));
        const e = uang(await r.text("fs-bs-total-equity"));
        const nb = neracaDb(tgl);
        const ok = dekat(a, l + e, 2) && dekat(a, nb.aset, 2) && dekat(l, nb.kewajiban, 2) && dekat(e, nb.ekuitas + nb.laba_berjalan, 2);
        return { ok, info: `aset ${rp(a)} = kewajiban ${rp(l)} + ekuitas ${rp(e)} · jurnal: ${rp(nb.aset)} = ${rp(nb.kewajiban)} + ${rp(nb.ekuitas)} + laba ${rp(nb.laba_berjalan)} (selisih ${rp(nb.selisih)})` };
      }, { muatUlang: async () => { await r.tid("fs-bs-refresh").click(); await r.idle(1500); } });
    });
    catat(r, { layar: `${LAYAR} › Neraca`, isian: "Per tanggal", masukan: tgl, harap: "A = L + E = jurnal" });
  }

  await r.step("L6", "Manajer", "Tab [Arus Kas] rentang 1 Oktober – 31 Oktober 2026, lalu 1 Januari – hari ini",
    "Kas awal + saldo awal rekening baru + perubahan = kas akhir = saldo akun kas & bank (1-1100 + 1-1110) di jurnal per tanggal akhir", async () => {
      await r.tid("fs-tab-cf").click();
      await r.tid("cf-kpi-end-value").waitFor({ timeout: 20000 });
      const out = [];
      for (const [s, e] of [["2026-10-01", "2026-10-31"], [`${HARI_INI.slice(0, 4)}-01-01`, HARI_INI]]) {
        await pilihTanggal(r, "cf-end", e);
        await pilihTanggal(r, "cf-start", s);
        out.push(await cocokBerulang(async () => {
          await r.idle(1200);
          const begin = uang(await r.text("cf-kpi-begin-value"));
          const chg = uang(await r.text("cf-kpi-netchange-value"));
          const end = uang(await r.text("cf-kpi-end-value"));
          const open = await r.tid("cf-opening").count() ? uang(await r.text("cf-opening")) : 0;
          const gl = saldoAkun(["1-1100", "1-1110"], { end: e });
          const kas = (gl["1-1100"] || 0) + (gl["1-1110"] || 0);
          return { ok: dekat(begin + open + chg, end, 2) && dekat(end, kas, 2), info: `${s}…${e}: ${rp(begin)} + ${rp(open)} + ${rp(chg)} = ${rp(end)} · jurnal kas ${rp(kas)}` };
        }, { muatUlang: async () => { await r.tid("cf-refresh").click(); await r.idle(1500); } }));
      }
      return out.join(" · ");
    });
  catat(r, { layar: `${LAYAR} › Arus Kas`, isian: "Rentang tanggal", masukan: "Oktober; 1 Jan – hari ini", harap: "kas akhir = jurnal kas" });
}

async function bandingLR(r, start, end) {
  return cocokBerulang(async () => {
    await r.page.waitForFunction(() => !document.querySelector('[data-testid="fs-pl-loading"]'), null, { timeout: 20000 }).catch(() => {});
    await r.idle(800);
    const lr = labaRugiDb(start, end);
    const rev = await r.tid("fs-pl-section-revenue-total").count() ? uang(await r.text("fs-pl-section-revenue-total")) : 0;
    const cogs = await r.tid("fs-pl-section-cogs-total").count() ? uang(await r.text("fs-pl-section-cogs-total")) : 0;
    const opex = await r.tid("fs-pl-section-opex-total").count() ? uang(await r.text("fs-pl-section-opex-total")) : 0;
    const net = uang(await r.text("fs-pl-kpi-net-value"));
    const ok = dekat(rev, lr.revenue, 2) && dekat(cogs, lr.cogs, 2) && dekat(opex, lr.opex, 2) && dekat(net, lr.net, 2);
    return { ok, info: `${start}…${end}: pendapatan ${rp(rev)} − HPP ${rp(cogs)} − beban ${rp(opex)} = laba ${rp(net)} (jurnal ${rp(lr.revenue)} / ${rp(lr.cogs)} / ${rp(lr.opex)} / ${rp(lr.net)})` };
  });
}

async function tutupBuku(r) {
  const LAYAR = "Akuntansi & Pajak › Tutup Buku";
  const [TY, TM] = TUTUP.split("-");
  const LBL = `September ${TY}`;
  const adm = await api("admin");
  const keadaan = async () => {
    const cl = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
    const ul = await adm.get(`/finance/period-unlocks?entity_id=${KSC}`, KSC);
    return { tertutup: cl.filter((c) => c.status === "closed").map((c) => c.period_key).sort(),
      usul: ul.filter((u) => ["pending", "approved"].includes(u.status)).map((u) => u.period_key).sort(), cl };
  };
  const awal = await keadaan();
  const jeSep = mongo(`return db.journal_entries.countDocuments({entity_id:"${KSC}",status:{$ne:"void"},date:{$gte:"${TUTUP}-01",$lte:"${TUTUP}-30T23:59:59"}})`);
  if (awal.tertutup.includes(TUTUP) || jeSep) { r.note(`${LBL} sudah tertutup / berisi ${jeSep} jurnal — bagian tutup buku dilewati`); return; }
  let closingId = "";
  try {
    await r.step("T1", "Manajer", `Tutup Buku → Bulanan · ${LBL} (kosong) → [Pratinjau] → [Tutup Buku] → dialog [Tutup Buku]`, `${LBL} tertutup`, async () => {
      await r.login("manager");
      const sw = r.tid("entity-switcher");
      if (await sw.count()) {
        const lbl = await r.text("entity-switcher");
        if (!/Sukacita/.test(lbl) || /Semua/.test(lbl)) { await sw.click(); await r.tid(`entity-option-${KSC}`).click(); await r.idle(1200); }
      }
      await menu(r, "akuntansi", "closing");
      await r.tid("closing-view").waitFor();
      await pilih(r, "closing-period-type", "month");
      await pilih(r, "closing-month", TM);
      await pilih(r, "closing-year", TY);
      await r.tid("closing-preview-btn").click();
      await r.tid("closing-preview").waitFor({ timeout: 20000 });
      await r.tid("closing-close-btn").click();
      await r.tid("closing-confirm-confirm").click();
      await r.tid("closing-notice").waitFor({ timeout: 30000 });
      const cl = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
      closingId = (cl.find((c) => c.period_key === TUTUP && c.status === "closed") || {}).id || "";
      assert(closingId, "periode tidak tertutup di server");
      return await r.text("closing-notice");
    });

    await r.step("T2", "Finance", `Peserta ${NO_TG}: Bayar tagihan supplier dengan *Tanggal bayar* 15 ${LBL} (periode tertutup)`,
      "Ditolak dengan pesan Indonesia tentang periode tertutup; tagihan tidak berubah, tidak ada kas/jurnal", async () => {
        const tg = kartu(NO_TG)["a_dasar:tagihan_bayar"];
        const before = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0,amount_paid:1,status:1})`);
        await r.login(akunPeserta(NO_TG));
        await r.go("vendor-bills", "&entity=ent_ksc");
        await r.tid("vb-search").fill(`Latihan ${NO_TG}`);
        await r.idle(900);
        await r.tid(`vb-open-${tg.tagihan_id}`).click();
        await r.tid("vb-action-pay").click();
        await r.tid("pay-supplier-number").waitFor();
        await pilihOpsi(r, "pay-supplier-account", REK_BCA);
        await ketik(r, "pay-supplier-amount", "100.000");
        await pilihTanggal(r, "pay-supplier-date", `${TUTUP}-15`);
        await r.tid("pay-supplier-submit").click();
        await r.tid("pay-supplier-confirm-confirm").click();
        await r.tid("pay-supplier-error").waitFor({ timeout: 20000 });
        const e = await r.text("pay-supplier-error");
        await r.tid("pay-supplier-cancel").click();
        const after = mongo(`return db.vendor_bills.findOne({id:"${tg.tagihan_id}"},{_id:0,amount_paid:1,status:1})`);
        const kas = mongo(`return db.cash_transactions.countDocuments({ref_id:"${tg.tagihan_id}"})`);
        assert(/tutup|tertutup|periode/i.test(e) && !/\b(error|closed)\b/i.test(e), `pesan: ${e}`);
        assert(Number(after.amount_paid) === Number(before.amount_paid) && kas === 0, `tagihan berubah ${JSON.stringify(after)} kas ${kas}`);
        return e;
      });
    catat(r, { layar: "Hutang › Tagihan › Bayar pemasok", isian: "Tanggal bayar", masukan: `${TUTUP}-15 (periode tertutup)`, harap: "ditolak, tidak ada yang berubah" });

    await r.step("T3", "Manajer", `Tutup Buku › Buka Periode: pilih ${LBL}, *Alasan* kosong / spasi saja → [Ajukan Usul]`,
      "Ditolak: \"Alasan membuka periode WAJIB diisi.\"; tidak ada usul tersimpan", async () => {
        await r.login("manager");
        await r.go("period-unlock");
        await r.tid("period-unlock-view").waitFor();
        await r.idle(800);
        await pilih(r, "plu-period-select", `month:${TUTUP}`);
        const out = [];
        for (const isi of ["", "   "]) {
          await r.tid("plu-reason-input").fill(isi);
          await r.tid("plu-request-btn").click();
          const e = await r.text("plu-error");
          assert(/Alasan membuka periode WAJIB diisi/.test(e), `"${isi}" → ${e}`);
          out.push(`"${isi}" → ${e}`);
        }
        const ul = await adm.get(`/finance/period-unlocks?entity_id=${KSC}`, KSC);
        assert(!ul.some((u) => u.period_key === TUTUP && u.status === "pending"), "usul tersimpan");
        return out.join(" · ");
      });
    catat(r, { layar: `${LAYAR} › Buka Periode`, isian: "Alasan (wajib)", masukan: "kosong; spasi saja", harap: "ditolak",
      catatan: "alasan 1 huruf masih diterima (server hanya cek tidak kosong) — usul minimal 5 huruf seperti alasan pembalikan jurnal (keputusan pemilik)" });

    await r.step("T4", "Admin", `Daftar Periksa & Tutup › Riwayat: ${LBL} → [Buka Kembali] → dialog`,
      "Dialog konfirmasi TANPA isian alasan → periode dibuka kembali (catat: buka kembali tidak meminta alasan)", async () => {
        await r.login("admin");
        await r.go("closing");
        await r.tid(`closing-row-${closingId}`).waitFor({ timeout: 20000 });
        await r.tid(`closing-reopen-${closingId}`).click();
        await r.tid("confirm-modal").waitFor();
        const adaAlasan = await r.tid("confirm-modal-reason").count();
        await r.tid("confirm-modal-confirm").click();
        await r.tid("closing-notice").waitFor({ timeout: 30000 });
        return `${await r.text("closing-notice")} · isian alasan di dialog: ${adaAlasan ? "ada" : "TIDAK ADA"}`;
      });
    catat(r, { layar: `${LAYAR} › Riwayat › Buka Kembali`, isian: "Alasan", masukan: "(tidak diminta)", harap: "buka kembali beralasan wajib?", hasil: "keputusan",
      catatan: `${last(r).info} — usul: wajibkan alasan ≥ 5 huruf & simpan di riwayat (sama dengan pembalikan jurnal)` });
  } finally {
    const cl = await adm.get(`/finance/closing?entity_id=${KSC}`, KSC);
    for (const c of cl.filter((x) => x.status === "closed" && x.period_key === TUTUP && !awal.tertutup.includes(TUTUP))) {
      await adm.post(`/finance/closing/${c.id}/reopen`, {}, KSC);
      r.note(`pengaman: ${c.period_label} dibuka kembali`);
    }
    await sleep(500);
    const akhir = await keadaan();
    await r.step("T5", "Pemeriksa", "Keadaan periode PT Sukacita dibanding sebelum uji", "Sama persis", async () => {
      assert(JSON.stringify(akhir.tertutup) === JSON.stringify(awal.tertutup), `tertutup ${awal.tertutup} → ${akhir.tertutup}`);
      assert(JSON.stringify(akhir.usul) === JSON.stringify(awal.usul), `usul ${awal.usul} → ${akhir.usul}`);
      return `tertutup [${akhir.tertutup.join(", ") || "—"}] · usul hidup [${akhir.usul.join(", ") || "—"}]`;
    });
  }
}

(async () => {
  const r = await new Run("V8", "Variasi isian — buku besar, laporan, tutup buku (F16–F18)").start();
  const bagian = (process.env.KN_BAGIAN || "buku,laporan,tutup").split(",");
  try {
    if (bagian.includes("buku")) await bukuBesar(r);
    if (bagian.includes("laporan")) await laporan(r);
    if (bagian.includes("tutup")) await tutupBuku(r);
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    tabel.simpan();
    await r.finish();
  }
})();
