// F16 — Buku Besar & Jejak Dokumen (Finance, hanya membaca): jurnal dari transaksi nyata `e_buku:so_jejak`
// (SO terkirim → surat jalan → jurnal pendapatan & HPP; kwitansi → transaksi kas → jurnal penerimaan).
//   node docs/pelatihan/2026-11-18_keuangan/uji/F16_buku_besar_jejak.js        (peserta bawaan 05)
//   KN_PESERTA=07 node docs/pelatihan/2026-11-18_keuangan/uji/F16_buku_besar_jejak.js
const { Run, assert, kartu, peserta, akunPeserta, mongo, rp } = require("./lib");
const { KSC, potret, sorot, bersihkanGambar, menu, saldoAkun, uang, cocokBerulang, dekat, jurnal, seimbang, sisi, pilih } = require("./buku_lib");

const NO = peserta("05");

(async () => {
  const r = await new Run("F16", "Buku Besar & Jejak Dokumen — menelusuri jurnal transaksi").start();
  bersihkanGambar(r);
  const k = kartu(NO);
  const j = k["e_buku:so_jejak"];
  try {
    assert(j && j.so_id && j.kwitansi && j.jurnal_terima, `Kartu peserta ${NO} belum punya e_buku:so_jejak — jalankan `
      + `seed_pelatihan_keuangan_kn.py --mulai ${Number(NO)} --peserta ${Number(NO)} --hanya e_buku:`);
    const [jeRev, jeCogs] = j.jurnal_kirim.split(",").map((x) => x.trim());
    const jeRcp = j.jurnal_terima.split(",")[0].trim();
    const so = mongo(`return db.sales_orders.findOne({id:"${j.so_id}"},{_id:0,number:1,grand_total:1,subtotal:1,ppn_amount:1,payment_status:1,customer_name:1})`);
    r.note(`Peserta ${NO} · ${j.so} (${rp(j.total)}) · ${j.surat_jalan} · ${j.kwitansi} · jurnal ${jeRev}, ${jeCogs}, ${jeRcp}`);

    await r.step(1, "Finance", "Masuk dengan akun peserta → menu Akuntansi & Pajak › Buku Besar (tab Jurnal)",
      "Kartu atas: TOTAL JURNAL, TOTAL DEBIT = TOTAL KREDIT, STATUS BUKU 'Seimbang'. Tidak ada tombol [Jurnal Baru]/[Sinkronkan] — Finance hanya melihat",
      async () => {
        await r.login(akunPeserta(NO));
        await menu(r, "akuntansi", "ledger");
        await r.tid("gl-view").waitFor();
        await r.tid("gl-kpi-debit-value").waitFor();
        const info = await cocokBerulang(async () => {
          const d = uang(await r.text("gl-kpi-debit-value"));
          const c = uang(await r.text("gl-kpi-credit-value"));
          const st = await r.text("gl-kpi-balanced-value");
          // Kartu atas = total kolom Neraca Saldo (saldo bersih per akun: Σ saldo debit / Σ saldo kredit), bukan jumlah
          // semua baris jurnal — dihitung ulang dari jurnal di sini.
          const net = Object.values(saldoAkun(null));
          const db = { d: Math.round(net.filter((v) => v > 0).reduce((a, v) => a + v, 0)),
            c: Math.round(-net.filter((v) => v < 0).reduce((a, v) => a + v, 0)) };
          return { ok: st === "Seimbang" && dekat(d, c) && dekat(d, db.d, 2) && dekat(c, db.c, 2),
            info: `debit ${rp(d)} · kredit ${rp(c)} · ${st} (buku: D ${rp(db.d)} / K ${rp(db.c)})` };
        }, { muatUlang: async () => { await r.tid("gl-refresh").click(); await r.idle(1200); } });
        assert(!(await r.tid("gl-new-journal").count()), "tombol [Jurnal Baru] tampil untuk Finance (izin accounting hanya view)");
        assert(!(await r.tid("gl-sync").count()), "tombol [Sinkronkan] tampil untuk Finance");
        await potret(r, "buku-besar-jurnal", [r.tid("nav-ledger"), r.tid("gl-kpi-balanced")]);
        return info;
      });

    await r.step(2, "Finance", `Ketik nomor kwitansi ${j.kwitansi} di kotak *Cari nomor jurnal / keterangan…*`,
      `Tinggal satu baris: ${jeRcp} · sumber 'Transaksi Kas' ${j.kas} · keterangan 'Kas in · Penerimaan ${j.kwitansi} — Latihan ${NO} …' · nilai ${rp(j.total)} · Terposting`,
      async () => {
        await r.tid("gl-journal-search").fill(j.kwitansi);
        await r.page.waitForFunction((n) => {
          const t = document.querySelector('[data-testid="gl-journal-total"]');
          return t && /^1 jurnal/.test(t.textContent.trim()) && document.body.innerText.includes(n);
        }, jeRcp, { timeout: 15000 });
        const je = jurnal(jeRcp);
        const row = r.tid(`gl-journal-row-${je.id}`);
        const t = (await row.innerText()).replace(/\s+/g, " ");
        assert(t.includes(jeRcp) && t.includes(j.kwitansi) && t.includes(rp(j.total).replace("Rp ", "")), `baris: ${t}`);
        assert(/Terposting/.test(t), `status baris: ${t}`);
        await potret(r, "cari-kwitansi", [r.tid("gl-journal-search"), row]);
        return t;
      });

    await r.step(3, "Finance", `Klik baris ${jeRcp} → pop-up rincian jurnal`,
      `Dua baris: 1-1100 Kas Besar / Bank DEBIT ${rp(j.total)} · 1-1200 Piutang Usaha KREDIT ${rp(j.total)}; Total debit = total kredit; 'Dokumen sumber Transaksi Kas ${j.kas}'`,
      async () => {
        const je = jurnal(jeRcp);
        await r.tid(`gl-journal-row-${je.id}`).click();
        const m = r.tid("gl-journal-detail");
        await m.waitFor();
        await r.idle(800);
        const t = (await m.innerText()).replace(/\s+/g, " ");
        const tot = seimbang(je);
        assert(dekat(tot, j.total), `nilai jurnal ${tot} ≠ total SO ${j.total}`);
        assert(dekat(sisi(je, "1-1100", "D"), j.total) && dekat(sisi(je, "1-1200", "K"), j.total), "baris jurnal bukan Dr Kas / Cr Piutang");
        assert(t.includes("1-1100") && t.includes("1-1200") && t.includes("Kas Besar / Bank") && t.includes("Piutang Usaha"), `isi pop-up: ${t.slice(0, 300)}`);
        assert((t.match(new RegExp(rp(j.total).replace(/[.]/g, "\\."), "g")) || []).length >= 4, `nominal ${rp(j.total)} tidak muncul 4× (2 baris + 2 total)`);
        assert(!(await r.tid("gl-journal-reverse").count()), "tombol [Balik Jurnal] tampil untuk Finance");
        const src = await r.text("gl-journal-source").catch(() => "");
        await potret(r, "rincian-jurnal-penerimaan", [m.locator("tfoot")], { locator: m });
        await r.tid("gl-journal-detail-close").click();
        return `D 1-1100 ${rp(j.total)} / K 1-1200 ${rp(j.total)} · ${src}`;
      });

    await r.step(4, "Finance", `Ganti isi *Cari* dengan nomor SO ${j.so} → buka jurnal 'Pendapatan Kirim'`,
      `Dua jurnal surat jalan ${j.surat_jalan}: Pendapatan Kirim ${jeRev} (Dr 1-1200 Piutang ${rp(j.total)} · Cr 4-1000 Pendapatan + Cr 2-1200 PPN Keluaran) dan HPP Kirim ${jeCogs} (Dr 5-1000 HPP · Cr 1-1300 Persediaan)`,
      async () => {
        await r.tid("gl-journal-search").fill(j.so);
        await r.page.waitForFunction(() => /^2 jurnal/.test((document.querySelector('[data-testid="gl-journal-total"]') || {}).textContent || ""), null, { timeout: 15000 });
        const rev = jurnal(jeRev), cogs = jurnal(jeCogs);
        await r.tid(`gl-journal-row-${cogs.id}`).waitFor();
        await potret(r, "cari-so", [r.tid("gl-journal-search"), r.tid(`gl-journal-row-${rev.id}`)]);
        await r.tid(`gl-journal-row-${rev.id}`).click();
        const m = r.tid("gl-journal-detail");
        await m.waitFor();
        await r.idle(600);
        const t = (await m.innerText()).replace(/\s+/g, " ");
        seimbang(rev); seimbang(cogs);
        const ar = sisi(rev, "1-1200", "D"), pdp = sisi(rev, "4-1000", "K"), ppn = sisi(rev, "2-1200", "K");
        assert(dekat(ar, j.total) && dekat(pdp + ppn, j.total), `pendapatan: piutang ${ar}, pendapatan ${pdp} + PPN ${ppn} ≠ ${j.total}`);
        assert(dekat(pdp, so.subtotal || pdp) && dekat(ppn, so.ppn_amount || ppn), `DPP/PPN jurnal ≠ SO (${so.subtotal}/${so.ppn_amount})`);
        assert(t.includes("4-1000") && t.includes("2-1200") && t.includes(rp(pdp).replace("Rp ", "")), `isi pop-up: ${t.slice(0, 300)}`);
        assert(dekat(sisi(cogs, "5-1000", "D"), sisi(cogs, "1-1300", "K")), "HPP ≠ persediaan keluar");
        await potret(r, "rincian-jurnal-pendapatan", [m.locator("tfoot")], { locator: m });
        await r.tid("gl-journal-detail-close").click();
        return `${jeRev}: D piutang ${rp(ar)} = K pendapatan ${rp(pdp)} + K PPN ${rp(ppn)} · ${jeCogs}: HPP ${rp(sisi(cogs, "5-1000", "D"))}`;
      });

    await r.step(5, "Finance", "Tab [Buku Besar] → *Akun*: ketik '1-1200', pilih '1-1200 — Piutang Usaha'",
      `Daftar mutasi Piutang Usaha memuat ${jeRev} di kolom Debit dan ${jeRcp} di kolom Kredit (nilai sama → piutang SO ini nol); 'Saldo akhir' = saldo akun 1-1200 di buku`,
      async () => {
        await r.tid("gl-journal-search").fill("");
        await r.tid("gl-tab-ledger").click();
        await r.idle(500);
        await pilih(r, "gl-ledger-account", "1-1200", "1-1200");
        await r.tid(`gl-ledger-row-${jeRcp}`).waitFor({ timeout: 20000 });
        const rowR = (await r.tid(`gl-ledger-row-${jeRev}`).innerText()).replace(/\s+/g, " ");
        const rowC = (await r.tid(`gl-ledger-row-${jeRcp}`).innerText()).replace(/\s+/g, " ");
        assert(rowR.includes(rp(j.total).replace("Rp ", "")) && rowC.includes(rp(j.total).replace("Rp ", "")), `baris: ${rowR} | ${rowC}`);
        const info = await cocokBerulang(async () => {
          const bal = await r.text("gl-ledger-balance");
          const m = bal.match(/Saldo akhir\s+(.*)$/);
          const v = uang(m ? m[1] : bal);
          const gl = saldoAkun(["1-1200"])["1-1200"] || 0;
          return { ok: dekat(v, gl, 2), info: `${bal} (buku 1-1200 ${rp(gl)})` };
        }, { muatUlang: async () => { await r.tid("gl-refresh").click(); await r.idle(1500); } });
        await r.tid(`gl-ledger-row-${jeRcp}`).scrollIntoViewIfNeeded();
        await potret(r, "buku-besar-piutang", [r.tid("gl-tab-ledger"), r.tid("gl-ledger-account"), r.tid(`gl-ledger-row-${jeRev}`), r.tid(`gl-ledger-row-${jeRcp}`), r.tid("gl-ledger-balance")]);
        return `${jeRev} debit · ${jeRcp} kredit · ${info}`;
      });

    await r.step(6, "Finance", "Tab [Neraca Saldo]",
      "Semua akun bersaldo; baris Total: kolom Debit = kolom Kredit",
      async () => {
        await r.tid("gl-tab-trial").click();
        await r.tid("gl-trial-total-debit").waitFor();
        await r.idle(600);
        const d = uang(await r.text("gl-trial-total-debit"));
        const c = uang(await r.text("gl-trial-total-credit"));
        assert(d > 0 && dekat(d, c), `neraca saldo tidak seimbang: ${d} ≠ ${c}`);
        await potret(r, "neraca-saldo", [r.tid("gl-tab-trial"), r.tid("gl-trial-total-debit"), r.tid("gl-trial-total-credit")]);
        return `debit ${rp(d)} = kredit ${rp(c)}`;
      });

    await r.step(7, "Finance", "Tab hub [Bagan Akun] → *Cari kode / nama akun…*: ketik 'piutang'",
      "Akun 1-1200 Piutang Usaha · global · 'Akun kontrol' · 'Dipakai Sukacita' · Detail · Debit. Finance hanya melihat: tidak ada [Tambah Akun], ikon ubah/hapus",
      async () => {
        await r.tid("hub-tab-chart-of-accounts").click();
        await r.tid("coa-view").waitFor();
        await r.tid("coa-search").fill("piutang");
        await r.tid("coa-row-1-1200").waitFor();
        await r.idle(500);
        const t = (await r.tid("coa-row-1-1200").innerText()).replace(/\s+/g, " ");
        assert(/Piutang Usaha/.test(t) && /Akun kontrol/.test(t) && /Detail · Debit/.test(t), `baris 1-1200: ${t}`);
        assert(!(await r.tid("coa-add-toggle").count()), "tombol [Tambah Akun] tampil untuk Finance");
        assert(!(await r.tid("coa-edit-1-1200").count()) && !(await r.tid("coa-delete-1-1200").count()), "ikon ubah/hapus tampil untuk Finance");
        await potret(r, "bagan-akun-piutang", [r.tid("hub-tab-chart-of-accounts"), r.tid("coa-search"), r.tid("coa-row-1-1200")]);
        return t;
      });

    await r.step(8, "Finance", `Menu Pusat Dokumen › tab Jejak Dokumen → ketik ${j.so} di *Cari dokumen* → klik hasilnya → geser 'Rantai dokumen' ke kanan`,
      `Rantai lengkap: ${j.so} → tugas ambil → surat jalan ${j.surat_jalan} → jurnal ${jeRev} & ${jeCogs}; ${j.so} 'Dilunasi oleh' kwitansi ${j.kwitansi} → transaksi kas ${j.kas} → jurnal ${jeRcp}. Nilai SO = kwitansi = kas = jurnal penerimaan = ${rp(j.total)}`,
      async () => {
        await menu(r, "alat", "document-center", "doc-trace");
        await r.tid("doc-trace-view").waitFor();
        await r.tid("trace-search-input").fill(j.so);
        await r.tid(`trace-result-${j.so_id}`).click();
        await r.tid("trace-anchor-card").waitFor({ timeout: 20000 });
        await r.tid("trace-graph").waitFor();
        await r.idle(1200);
        const anchor = await r.text("trace-anchor-number");
        assert(anchor.includes(j.so), `titik mulai: ${anchor}`);
        const g = (await r.text("trace-graph"));
        const harus = [j.so, j.surat_jalan, j.kwitansi, j.kas, jeRev, jeCogs, jeRcp];
        const hilang = harus.filter((x) => !g.includes(x));
        assert(!hilang.length, `jejak tidak memuat: ${hilang.join(", ")}`);
        const rc = mongo(`return db.ar_receipts.findOne({id:"${j.kwitansi_id}"},{_id:0,id:1,amount:1})`);
        const kas = mongo(`return db.cash_transactions.findOne({number:"${j.kas}",entity_id:"${KSC}"},{_id:0,id:1,amount:1})`);
        const je = jurnal(jeRcp);
        for (const [id, v, nm] of [[j.so_id, so.grand_total, j.so], [rc.id, rc.amount, j.kwitansi], [kas.id, kas.amount, j.kas], [je.id, je.total_debit, jeRcp]]) {
          assert(dekat(v, j.total), `${nm}: nilai buku ${v} ≠ ${j.total}`);
          const node = (await r.text(`trace-node-${id}`));
          assert(node.includes(rp(j.total).replace("Rp ", "")), `simpul ${nm} tidak menulis ${rp(j.total)}: ${node}`);
        }
        await potret(r, "jejak-dokumen", [r.tid("hub-tab-doc-trace"), r.tid("trace-search-input"), r.tid("trace-kpi-amount")], { full: true });
        // Rantai lebih lebar dari layar: kwitansi, kas & jurnal ada di kanan — geser rantai ke kanan (seperti peserta).
        await r.page.evaluate(() => {
          const g = document.querySelector('[data-testid="trace-graph"]');
          for (const e of [g, ...g.querySelectorAll("*")]) if (e.scrollWidth > e.clientWidth + 10) e.scrollLeft = e.scrollWidth;
        });
        await r.idle(300);
        const je9 = jurnal(jeRcp);
        await potret(r, "jejak-dokumen-geser-kanan", [r.tid(`trace-node-${je9.id}`), r.tid(`trace-open-${je9.id}`)], { locator: r.tid("trace-graph") });
        return `${(await r.text("trace-kpis")).replace(/\s+/g, " ")}`;
      });

    await r.step(9, "Finance", `Pada kotak jurnal ${jeRcp} klik ikon buka (↗)`,
      `Layar pindah ke Buku Besar dan pop-up rincian ${jeRcp} langsung terbuka; tombol [Kembali ke Jejak ${j.so}] membawa kembali ke jejak`,
      async () => {
        const je = jurnal(jeRcp);
        await r.tid(`trace-open-${je.id}`).click();
        const m = r.tid("gl-journal-detail");
        await m.waitFor({ timeout: 20000 });
        await r.idle(800);
        const t = (await m.innerText()).replace(/\s+/g, " ");
        assert(t.includes(jeRcp), `pop-up bukan ${jeRcp}: ${t.slice(0, 120)}`);
        const back = r.tid("gl-journal-back-to-trace");
        assert(await back.count(), "tombol Kembali ke Jejak tidak ada");
        await potret(r, "jurnal-dari-jejak", [back], { locator: m });
        await back.click();
        await r.tid("trace-anchor-number").waitFor({ timeout: 20000 });
        const a = await r.text("trace-anchor-number");
        assert(a.includes(j.so), `kembali ke jejak: ${a}`);
        return `${jeRcp} → kembali ke ${a}`;
      });
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    await r.finish();
  }
})();
