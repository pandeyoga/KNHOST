// F17 — Laporan Keuangan (Manajer): Laba-Rugi bulan berjalan, Neraca, Arus Kas, Profitabilitas — PT Sukacita.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F17_laporan_keuangan.js
// Hanya membaca. Setiap angka layar dicocokkan dengan jurnal di Mongo (dihitung ulang di uji, bukan lewat layanan
// laporan aplikasi). Agent/peserta lain memposting bersamaan → baca ulang sampai cocok (`cocokBerulang`).
const { Run, assert, mongo, rp } = require("./lib");
const { KSC, potret, bersihkanGambar, menu, labaRugiDb, neracaDb, saldoAkun, uang, cocokBerulang, dekat, BULAN, pilih } = require("./buku_lib");

const now = new Date(Date.now() + 7 * 3600e3);   // tanggal buku WIB (server memakai WIB; mesin uji UTC)
const TAHUN = now.getUTCFullYear();
const BLN = now.getUTCMonth() + 1;
const AWAL_BULAN = `${TAHUN}-${String(BLN).padStart(2, "0")}-01`;
const HARI_INI = now.toISOString().slice(0, 10);
const AKHIR_BULAN = new Date(Date.UTC(TAHUN, BLN, 0)).toISOString().slice(0, 10);

(async () => {
  const r = await new Run("F17", "Laporan Keuangan — Laba-Rugi, Neraca, Arus Kas, Profitabilitas (Manajer)").start();
  bersihkanGambar(r);
  try {
    await r.step(1, "Manajer", "Masuk sebagai manajer → kotak PT di bilah atas: pilih 'Sukacita' → menu Akuntansi & Pajak › Laporan",
      "Tab hub 'Laba-Rugi, Neraca & Arus Kas' terbuka; pita 'Angka untuk Sukacita Textile'; empat tab: Laba-Rugi · Neraca · Arus Kas · Perubahan Ekuitas",
      async () => {
        await r.login("manager");
        const sw = r.tid("entity-switcher");
        if (await sw.count()) {
          const lbl = await r.text("entity-switcher");
          if (!/Sukacita/.test(lbl) || /Semua/.test(lbl)) {
            await sw.click();
            await r.tid(`entity-option-${KSC}`).click();
            await r.idle(1200);
          }
        }
        await menu(r, "akuntansi", "fin-reports");
        await r.tid("financial-statements-view").waitFor();
        await r.tid("fs-pl-kpi-revenue-value").waitFor();
        const pita = await r.text("entity-scope-banner");
        assert(/Sukacita/.test(pita), `pita PT: ${pita}`);
        const tabs = await r.text("fs-tab");
        assert(/Laba-Rugi/.test(tabs) && /Neraca/.test(tabs) && /Arus Kas/.test(tabs), `tab: ${tabs}`);
        await potret(r, "laporan-sukacita", [r.tid("entity-switcher"), r.tid("nav-fin-reports"), r.tid("entity-scope-banner")]);
        return `${pita} · ${tabs}`;
      });

    const lrBulan = () => labaRugiDb(AWAL_BULAN, AKHIR_BULAN);
    await r.step(2, "Manajer", `Tab Laba-Rugi → [Periode (Bulan/Tahun)] → *Tipe Periode* Bulanan · *Bulan* ${BULAN[BLN - 1]} · *Tahun* ${TAHUN}`,
      "Keterangan periode '01 … s/d 30 …'; tabel: Pendapatan (4-1000) · Beban Pokok Penjualan (5-1000) · Beban Operasional (6-…) · Laba Kotor · Laba Bersih — sama dengan jumlah jurnal bulan ini per kelompok akun",
      async () => {
        await r.tid("fs-pl-mode-period").click();
        await r.idle(500);
        await pilih(r, "fs-pl-period-type", "month");
        await pilih(r, "fs-pl-period-month", String(BLN).padStart(2, "0")).catch(async () => pilih(r, "fs-pl-period-month", String(BLN)));
        await pilih(r, "fs-pl-period-year", String(TAHUN));
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="fs-pl-loading"]'), null, { timeout: 20000 });
        await r.idle(800);
        const hint = await r.text("fs-pl-period-hint");
        const info = await cocokBerulang(async () => {
          const lr = lrBulan();
          const rev = uang(await r.text("fs-pl-section-revenue-total"));
          const cogs = uang(await r.text("fs-pl-section-cogs-total"));
          const opex = await r.tid("fs-pl-section-opex-total").count() ? uang(await r.text("fs-pl-section-opex-total")) : 0;
          const gross = uang(await r.text("fs-pl-kpi-gross-value"));
          const net = uang(await r.text("fs-pl-kpi-net-value"));
          const ok = dekat(rev, lr.revenue) && dekat(cogs, lr.cogs) && dekat(opex, lr.opex) && dekat(gross, lr.gross)
            && dekat(net, lr.net) && dekat(net, rev - cogs - opex, 2);
          return { ok, info: `${hint} · pendapatan ${rp(rev)} − HPP ${rp(cogs)} = laba kotor ${rp(gross)} − beban ${rp(opex)} = laba bersih ${rp(net)} (jurnal: ${rp(lr.revenue)} / ${rp(lr.cogs)} / ${rp(lr.opex)} / ${rp(lr.net)})` };
        }, { muatUlang: async () => { await pilih(r, "fs-pl-period-year", String(TAHUN)); await r.idle(1200); } });
        await potret(r, "laba-rugi-bulan-ini", [r.tid("fs-pl-mode-period"), r.tid("fs-pl-period-month"), r.tid("fs-pl-period-hint"), r.tid("fs-pl-kpi-net")]);
        return info;
      });

    await r.step(3, "Manajer", "Klik nama akun '4-1000 Pendapatan Penjualan' di tabel",
      "Pindah ke Buku Besar › tab Buku Besar akun 4-1000 dengan rentang bulan ini; tombol [← Kembali ke Laporan Keuangan]. Jumlah kredit di sana = angka pendapatan di Laba-Rugi",
      async () => {
        const rev = uang(await r.text("fs-pl-section-revenue-total"));
        await r.tid("fs-line-4-1000").click();
        await r.tid("gl-ledger").waitFor({ timeout: 20000 });
        await r.page.waitForFunction(() => document.querySelector('[data-testid="gl-ledger-balance"]'), null, { timeout: 20000 });
        await r.idle(800);
        const bal = await r.text("gl-ledger-balance");
        const back = await r.tid("gl-back-to-report").count();
        const s = saldoAkun(["4-1000"], { start: AWAL_BULAN, end: AKHIR_BULAN, tanpaPenutup: true })["4-1000"] || 0;
        await potret(r, "buku-besar-pendapatan", [r.tid("gl-back-to-report"), r.tid("gl-ledger-balance")]);
        assert(back, "tombol Kembali ke Laporan Keuangan tidak ada");
        await r.tid("gl-back-to-report").click();
        await r.tid("financial-statements-view").waitFor();
        await r.idle(800);
        return `${bal} · jurnal 4-1000 bulan ini ${rp(-s)} · layar L/R ${rp(rev)}`;
      });

    await r.step(4, "Manajer", "Tab [Neraca] (per hari ini)",
      "TOTAL ASET = TOTAL KEWAJIBAN + EKUITAS (✓, kartu 'Status Neraca: Seimbang'). Ekuitas memuat 'Laba Tahun Berjalan'. Baris 1-9999 Akun Sementara (Suspense) bernilai minus — wajib nol sebelum tutup buku",
      async () => {
        await r.tid("fs-tab-bs").click();
        await r.tid("fs-bs-total-assets").waitFor({ timeout: 20000 });
        await r.idle(800);
        const info = await cocokBerulang(async () => {
          const a = uang(await r.text("fs-bs-total-assets"));
          const l = uang(await r.text("fs-bs-total-liab"));
          const e = uang(await r.text("fs-bs-total-equity"));
          const le = uang(await r.text("fs-bs-total-liab-equity"));
          const st = await r.text("fs-bs-kpi-balanced-value");
          const nb = neracaDb(HARI_INI);
          const ok = st === "Seimbang" && dekat(a, le, 2) && dekat(l + e, le, 2) && dekat(a, nb.aset, 2) && dekat(l, nb.kewajiban, 2)
            && dekat(e, nb.ekuitas + nb.laba_berjalan, 2) && Math.abs(nb.selisih) < 1;
          return { ok, info: `aset ${rp(a)} = kewajiban ${rp(l)} + ekuitas ${rp(e)} (${rp(le)}) · ${st} · jurnal: aset ${rp(nb.aset)}, kewajiban ${rp(nb.kewajiban)}, ekuitas ${rp(nb.ekuitas)} + laba berjalan ${rp(nb.laba_berjalan)}` };
        }, { muatUlang: async () => { await r.tid("fs-bs-refresh").click(); await r.idle(1500); } });
        const sus = saldoAkun(["1-9999"])["1-9999"] || 0;
        if (Math.abs(sus) > 0.5) {
          const row = await r.tid("fs-bs-line-1-9999").count() ? await r.text("fs-bs-line-1-9999") : "(baris 1-9999 tidak tampil)";
          r.note(`Neraca: Suspense 1-9999 = ${rp(sus)} (${row}) — kas masuk demo tanpa akun lawan; menghalangi tutup buku bulan berjalan`);
        }
        await potret(r, "neraca", [r.tid("fs-tab-bs"), r.tid("fs-bs-kpi-balanced"), r.tid("fs-bs-line-1-9999"), r.tid("fs-bs-total-liab-equity")], { full: true });
        return info;
      });

    await r.step(5, "Manajer", "Tab [Arus Kas] (rentang bawaan awal tahun s/d hari ini)",
      "Kas Awal Periode + 'Saldo awal rekening yang didaftarkan periode ini' (baris di tabel / tulisan kecil di kartu Kas Awal) + Perubahan Kas Bersih = Kas Akhir Periode; Kas Akhir = saldo akun kas & bank (1-1100 + 1-1110) di buku; lencana hijau 'Terekonsiliasi'",
      async () => {
        await r.tid("fs-tab-cf").click();
        await r.tid("cf-kpi-end-value").waitFor({ timeout: 20000 });
        await r.idle(1000);
        const info = await cocokBerulang(async () => {
          const begin = uang(await r.text("cf-kpi-begin-value"));
          const chg = uang(await r.text("cf-kpi-netchange-value"));
          const end = uang(await r.text("cf-kpi-end-value"));
          const open = await r.tid("cf-opening").count() ? uang(await r.text("cf-opening")) : 0;
          const rec = await r.text("cf-reconcile").catch(() => "");
          const gl = saldoAkun(["1-1100", "1-1110"], { end: HARI_INI });
          const kas = (gl["1-1100"] || 0) + (gl["1-1110"] || 0);
          const ok = dekat(begin + open + chg, end, 2) && dekat(end, kas, 2) && /Terekonsiliasi/.test(rec);
          return { ok, info: `kas awal ${rp(begin)} + saldo awal rekening baru ${rp(open)} + perubahan ${rp(chg)} = kas akhir ${rp(end)} · buku kas ${rp(kas)} · ${rec}` };
        }, { muatUlang: async () => { await r.tid("cf-refresh").click(); await r.idle(1500); } });
        await potret(r, "arus-kas", [r.tid("fs-tab-cf"), r.tid("cf-reconcile"), r.tid("cf-opening-row"), r.tid("cf-kpi-end")], { full: true });
        return info;
      });

    await r.step(6, "Manajer", "Tab hub [Profitabilitas] → tab Realisasi (bawaan awal tahun s/d hari ini)",
      "Kartu Pendapatan (realisasi · terkirim), HPP, Marjin Kotor, Marjin %; tabel 'Pencocokan ke Laba-Rugi': marjin layar + penyesuaian persediaan + antar-PT + 'Pendapatan lain di Laba-Rugi (denda, bunga, klaim …)' = 'Laba kotor menurut Laba-Rugi', dengan 'Selisih belum dijelaskan Rp 0'",
      async () => {
        await r.tid("hub-tab-profitability").click();
        await r.tid("prof-reconciliation-table").waitFor({ timeout: 30000 });
        await r.idle(1000);
        const info = await cocokBerulang(async () => {
          const un = uang(await r.text("prof-rec-unexplained"));
          const gp = uang(await r.text("prof-rec-gross_profit_pl"));
          const mg = uang(await r.text("prof-kpi-margin-value"));
          const start = await r.tid("prof-start").inputValue().catch(() => `${TAHUN}-01-01`);
          const lr = labaRugiDb(/^\d{4}-\d\d-\d\d$/.test(start) ? start : `${TAHUN}-01-01`, HARI_INI);
          const ok = dekat(un, 0) && dekat(gp, lr.gross, 2);
          return { ok, info: `marjin kotor layar ${rp(mg)} · laba kotor L/R ${rp(gp)} (jurnal ${rp(lr.gross)}) · selisih belum dijelaskan ${rp(un)}` };
        }, { muatUlang: async () => { await r.tid("prof-refresh").click(); await r.idle(2000); } });
        await r.tid("prof-reconciliation").scrollIntoViewIfNeeded();
        await potret(r, "profitabilitas", [r.tid("hub-tab-profitability"), r.tid("prof-rec-other_income"), r.tid("prof-rec-unexplained")]);
        return info;
      });
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    await r.finish();
  }
})();
