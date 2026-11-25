// F01 — Orientasi Finance: masuk, Beranda Keuangan (Meja Keuangan · Posisi · Analisis), bilah atas, Profil Saya, Tanya KN.
//   node docs/pelatihan/2026-11-18_keuangan/uji/F01_orientasi.js           (peserta bawaan 05)
//   KN_PESERTA=07 node docs/pelatihan/2026-11-18_keuangan/uji/F01_orientasi.js
// Tidak mencatat apa pun: semua langkah hanya membaca. Angka Posisi/Analisis dicocokkan dengan jurnal di Mongo.
const { Run, api, assert, kartu, peserta, akunPeserta, mongo, rp } = require("./lib");
const { KSC, potret, bersihkanGambar, menu, saldoAkun, labaRugiDb, uang, cocokBerulang, dekat } = require("./buku_lib");

const NO = peserta("05");
const TAHUN = new Date().getFullYear();

(async () => {
  const r = await new Run("F01", "Orientasi Finance — Beranda Keuangan, bilah atas, profil").start();
  bersihkanGambar(r);
  const k = kartu(NO);
  const soL = k["a_dasar:so_lunas"], soS = k["a_dasar:so_sebagian"];
  try {
    assert(soL && soS, `Kartu peserta ${NO} belum lengkap — jalankan seed_pelatihan_keuangan_kn.py`);
    const fin = await api(akunPeserta(NO));

    await r.step(1, "Finance", "Masuk dengan akun peserta (email + sandi di Kartu Peserta) → [Masuk]",
      "Langsung mendarat di Keuangan › Beranda Keuangan, tab 'Meja Keuangan'; tiga tab: Meja Keuangan · Posisi · Analisis",
      async () => {
        await r.login(akunPeserta(NO));
        await r.tid("finance-desk").waitFor();
        assert(/view=finance-desk/.test(r.page.url()), `mendarat di ${r.page.url()}`);
        for (const t of ["finance-desk", "finance-tower", "bi-finance"]) await r.tid(`hub-tab-${t}`).waitFor();
        const tabs = await r.text("hub-tabs-finance-tower");
        assert(/Meja Keuangan/.test(tabs) && /Posisi/.test(tabs) && /Analisis/.test(tabs), `tab: ${tabs}`);
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="fin-desk-loading"]'), null, { timeout: 20000 });
        await potret(r, "beranda-perlu-tindakan", [r.tid("hub-tab-finance-desk")]);
        return `${r.who} → ${r.page.url().replace(/^.*\?/, "?")}`;
      });

    await r.step(2, "Finance", "Baca bilah atas: kotak PT, bilah Lokasi, lonceng, tombol Tanya KN",
      "Kotak PT bertuliskan 'Sukacita · Finance'. Sejak K-FIN-01 akun Finance lintas PT seperti Manajer, jadi kotak PT bisa dibuka — di latihan tetap bekerja di PT Sukacita. Bilah 'Lokasi: Semua lokasi' + tulisan oranye 'Lokasi kerja belum diatur' (abaikan — tidak berpengaruh ke keuangan)",
      async () => {
        const kotak = (await r.tid("entity-switcher-locked").count()) ? "entity-switcher-locked" : "entity-switcher";
        const pt = await r.text(kotak);
        assert(/Sukacita/.test(pt) && /Finance/.test(pt), `kotak PT: ${pt}`);
        const me = await fin.get("/auth/me");
        const u = me.user || me;
        const ctx = u.entity_context || {};
        assert(ctx.active_entity_id === KSC || u.home_entity_id === KSC, `PT aktif: ${ctx.active_entity_id || u.home_entity_id}`);
        r.note(`K-FIN-01: kotak PT ${kotak === "entity-switcher" ? "bisa dibuka" : "terkunci"} · PT terjangkau ${(ctx.allowed_entity_ids || u.allowed_entity_ids || []).length}`);
        const lok = await r.text("location-scope-bar");
        const unset = await r.tid("location-scope-bar-unset").count();
        await potret(r, "bilah-atas", [r.tid(kotak), r.tid("location-scope-bar-unset")], { locator: r.page.locator("header").first() });
        r.note(`TEMUAN F01-a: bilah Lokasi tampil untuk Finance ('${lok}'${unset ? " + 'Lokasi kerja belum diatur'" : ""}) karena izin product.view/logistics.view — tidak relevan bagi kasir, membingungkan`);
        return `PT: ${pt} · ${lok}${unset ? " · peringatan 'Lokasi kerja belum diatur'" : ""}`;
      });

    // ── Meja Keuangan ────────────────────────────────────────────────────────────────────────────────────────
    const desk = await fin.get(`/finance/desk?entity_id=${KSC}`);
    const q = Object.fromEntries((desk.queues || []).map((x) => [x.id, x]));

    await r.step(3, "Finance", "Meja Keuangan: baca kepala tiap kartu (judul · jumlah · 'tertua …' · NILAI)",
      "Kartu 'Faktur pajak perlu terbit', 'Uang masuk perlu dicatat' (dan 'Selisih bayar perlu diputus' bila ada) — angka jumlah sama dengan isi antrean",
      async () => {
        const cek = [["faktur_pajak", ["siap_faktur_pajak"]], ["uang_masuk", ["uang_masuk", "bayar_sebelum_kirim"]],
          ["selisih_bayar", ["selisih_bayar"]]];
        const out = [];
        for (const [card, ids] of cek) {
          const harap = ids.reduce((s, id) => s + Number((q[id] || {}).count || 0), 0);
          const ada = await r.tid(`fin-desk-queue-${card}`).count();
          if (!harap) { assert(!ada, `kartu ${card} tampil padahal antrean kosong`); continue; }
          assert(ada, `kartu ${card} tidak tampil (antrean ${harap})`);
          const n = Number(await r.text(`fin-desk-count-${card}`));
          // antrean bisa bertambah oleh peserta lain di antara dua baca → toleransi kecil, dicatat
          assert(Math.abs(n - harap) <= 2, `kartu ${card}: layar ${n} ≠ API ${harap}`);
          out.push(`${card}=${n}`);
        }
        // Meja gelombang 1 (§5.1) — ringkasan "n dokumen · n kelompok" di kepala meja dihapus (satu kepala = judul halaman).
        await potret(r, "kepala-kartu", [r.tid("fin-desk-count-faktur_pajak"), r.tid("fin-desk-count-uang_masuk"),
          r.tid("fin-desk-total-uang_masuk")]);
        return out.join(" · ");
      });

    await r.step(4, "Finance", "Kartu 'Uang masuk perlu dicatat': ketik nama pelanggan Anda di kotak *Cari* (mis. 'Toko Kain Peserta " + NO + "')",
      `Hanya dua baris milik Anda: ${soL.so} dan ${soS.so} (Latihan ${NO} · Toko Kain Peserta ${NO}), masing-masing bertombol [Terima pembayaran]`,
      async () => {
        const box = r.tid("fin-desk-search-uang_masuk");
        await box.fill(`Toko Kain Peserta ${NO}`);   // "Latihan NN" juga menemukan pelanggan cicilan peserta (F05)
        await r.idle(500);
        const card = r.tid("fin-desk-queue-uang_masuk");
        const rows = card.locator('[data-testid^="fin-desk-uang_masuk-row-"]');
        const n = await rows.count();
        const txt = (await card.innerText()).replace(/\s+/g, " ");
        const sisa = (id) => mongo(`const o=db.sales_orders.findOne({id:"${id}"},{_id:0,grand_total:1,payments:1});
          return Math.round((o.grand_total-(o.payments||[]).reduce((s,p)=>s+(p.amount||0),0))*100)/100`);
        const harap = [soL, soS].filter((s) => sisa(s.so_id) > 0.01);
        assert(n === harap.length, `baris tersaring ${n}, harap ${harap.length} (${harap.map((s) => s.so).join(", ")})`);
        for (const s of harap) {
          assert(txt.includes(s.so), `${s.so} tidak ada di kartu: ${txt.slice(0, 300)}`);
          const v = uang(await r.text(`fin-desk-uang_masuk-value-${s.so_id}`));
          assert(dekat(v, sisa(s.so_id)), `${s.so}: nilai layar ${v} ≠ sisa tagihan ${sisa(s.so_id)}`);
          assert(/Terima pembayaran/.test(await r.text(`fin-desk-uang_masuk-action-${s.so_id}`)), "tombol aksi bukan 'Terima pembayaran'");
        }
        await potret(r, "cari-uang-masuk", [box], { locator: card });
        return harap.map((s) => `${s.so} ${rp(sisa(s.so_id))}`).join(" · ");
      });

    await r.step(5, "Finance", `Klik [Terima pembayaran] pada ${soL.so} → lihat formnya → [Batal] (JANGAN simpan — dicatat di F02)`,
      "Form 'Terima pembayaran' terbuka dengan nama pelanggan Anda; tombol [Batal] menutup tanpa mencatat apa pun",
      async () => {
        const sebelum = mongo(`return db.ar_receipts.countDocuments({entity_id:"${KSC}"})`);
        // Meja gelombang 1 — "Terima pembayaran" aksi DI TEMPAT (`receipt`): tombol baris langsung membuka formnya.
        await r.tid(`fin-desk-uang_masuk-action-${soL.so_id}`).click();
        await r.tid("ar-receipt-customer-name").waitFor();
        await r.idle(800);
        const nm = await r.text("ar-receipt-customer-name");
        assert(nm.includes(`Latihan ${NO}`), `pelanggan di form: ${nm}`);
        await potret(r, "form-terima-pembayaran", [r.tid("ar-receipt-cancel")]);
        await r.tid("ar-receipt-cancel").click();
        await r.tid("ar-receipt-customer-name").waitFor({ state: "detached" });
        const sesudah = mongo(`return db.ar_receipts.countDocuments({entity_id:"${KSC}"})`);
        assert(sesudah >= sebelum, "jumlah kwitansi berkurang?");
        await r.tid("fin-desk-search-uang_masuk").fill("");
        return nm;
      });

    await r.step(6, "Finance", "Kartu 'Faktur pajak perlu terbit': klik [Berikutnya ›] di bawah kartu (halaman 2)",
      "Keterangan berubah menjadi 'Menampilkan 6–10 dari … baris' dan 'Hal 2 / …'; 5 baris per halaman. JANGAN klik [Terbitkan] (langsung menerbitkan faktur pajak)",
      async () => {
        const n = Number(await r.text("fin-desk-count-faktur_pajak"));
        if (n <= 5) return `hanya ${n} baris — tanpa halaman 2`;
        await r.tid("fin-desk-pager-faktur_pajak-next").click();
        await r.idle(300);
        const info = await r.text("fin-desk-pager-faktur_pajak-info");
        const hal = await r.text("fin-desk-pager-faktur_pajak-page");
        assert(/Menampilkan 6–\d+ dari \d+/.test(info), `info halaman: ${info}`);
        assert(/Hal 2 \/ \d+/.test(hal), `nomor halaman: ${hal}`);
        const rows = await r.tid("fin-desk-queue-faktur_pajak").locator('[data-testid^="fin-desk-faktur_pajak-row-"]').count();
        assert(rows >= 1 && rows <= 5, `baris per halaman ${rows}`);
        await potret(r, "faktur-pajak-halaman-2", [r.tid("fin-desk-pager-faktur_pajak-next"), r.tid("fin-desk-pager-faktur_pajak-info")], { locator: r.tid("fin-desk-queue-faktur_pajak") });
        await r.tid("fin-desk-pager-faktur_pajak-prev").click();
        return `${info} · ${hal}`;
      });

    await r.step(7, "Finance", "Kartu 'Selisih bayar perlu diputus' (bila tampil): baca baris kwitansi, nilai selisih, tombol [Putuskan]",
      "Baris kwitansi menunjukkan arah selisih (kurang/lebih bayar) dan NILAI selisihnya; tombol [Putuskan] aktif (bukan 'Memproses…')",
      async () => {
        const rows = (q.selisih_bayar || {}).rows || [];
        if (!rows.length) return "tidak ada selisih bayar — kartu tidak tampil (benar)";
        const out = [];
        for (const row of rows.slice(0, 5)) {
          assert(row.ref_id, `baris ${row.number} tanpa ref_id (tombol macet 'Memproses…')`);
          const act = await r.text(`fin-desk-selisih_bayar-action-${row.ref_id}`);
          assert(/Putuskan/.test(act), `tombol baris ${row.number}: '${act}'`);
          const rc = mongo(`return db.ar_receipts.findOne({id:"${row.ref_id}"},{_id:0,number:1,variance:1})`);
          const v = uang(await r.text(`fin-desk-selisih_bayar-value-${row.ref_id}`));
          assert(dekat(v, Math.abs(rc.variance.delta)), `${rc.number}: nilai layar ${v} ≠ selisih ${rc.variance.delta}`);
          out.push(`${rc.number} ${rp(Math.abs(rc.variance.delta))} ${rc.variance.direction}`);
        }
        await potret(r, "selisih-bayar", [r.tid(`fin-desk-selisih_bayar-action-${rows[0].ref_id}`)], { locator: r.tid("fin-desk-queue-selisih_bayar") });
        return out.join(" · ");
      });

    // ── Posisi ────────────────────────────────────────────────────────────────────────────────────────────────
    await r.step(8, "Finance", "Klik tab [Posisi]: baca empat kartu POSISI KAS · PIUTANG (AR) · HUTANG (AP) · MODAL KERJA BERSIH",
      "Posisi Kas = saldo buku besar akun kas & bank; Piutang 'tercatat' = saldo akun Piutang Usaha; Hutang = saldo Hutang Usaha; Modal kerja = Kas + piutang tercatat − hutang",
      async () => {
        await r.tid("hub-tab-finance-tower").click();
        await r.tid("tower-kpi-cash-value").waitFor();
        await r.idle(800);
        const info = await cocokBerulang(async () => {
          const kas = uang(await r.text("tower-kpi-cash-value"));
          const ar = uang(await r.text("tower-kpi-ar-value"));
          const arSub = await r.text("tower-kpi-ar-sub");
          const ap = uang(await r.text("tower-kpi-ap-value"));
          const wc = uang(await r.text("tower-kpi-wc-value"));
          const m = arSub.match(/tercatat\s+(Rp\s*[\d.]+)/);
          const arTercatat = m ? uang(m[1]) : NaN;
          const gl = saldoAkun(["1-1100", "1-1110", "1-1200", "2-1100"]);
          const glKas = (gl["1-1100"] || 0) + (gl["1-1110"] || 0);
          const ok = dekat(kas, glKas) && dekat(arTercatat, gl["1-1200"] || 0) && dekat(ap, -(gl["2-1100"] || 0))
            && dekat(wc, kas + arTercatat - ap, 2);
          return { ok, info: `kas ${rp(kas)} (GL ${rp(glKas)}) · piutang ${rp(ar)} [${arSub}] (GL 1-1200 ${rp(gl["1-1200"])}) · hutang ${rp(ap)} (GL 2-1100 ${rp(-(gl["2-1100"] || 0))}) · modal kerja ${rp(wc)}` };
        }, { muatUlang: async () => { await r.tid("tower-refresh").click(); await r.idle(1200); } });
        await potret(r, "posisi-kartu", [r.tid("hub-tab-finance-tower"), r.tid("tower-kpi-ar-sub")]);
        return info;
      });

    await r.step(9, "Finance", "Gulir ke 'Rincian Kas per Akun (GL)' dan kartu Laba-Rugi YTD",
      "Rincian per akun (1-1100 Kas Besar / Bank, 1-1110 Kas Kecil) dijumlah = Posisi Kas. Pendapatan & Laba Bersih YTD = jurnal tahun berjalan",
      async () => {
        const info = await cocokBerulang(async () => {
          const panel = (await r.text("tower-cash-panel"));
          const kas = uang(await r.text("tower-kpi-cash-value"));
          const vals = [...panel.matchAll(/(1-11\d0)[^R]*?(Rp\s*[\d.]+)/g)].map((m) => [m[1], uang(m[2])]);
          const jml = vals.reduce((s, [, v]) => s + v, 0);
          const rev = uang(await r.text("tower-kpi-rev-ytd-value"));
          const net = uang(await r.text("tower-kpi-net-ytd-value"));
          const lr = labaRugiDb(`${TAHUN}-01-01`, new Date(Date.now() + 7 * 3600e3).toISOString().slice(0, 10));
          const ok = vals.length >= 2 && dekat(jml, kas, 2) && dekat(rev, lr.revenue) && dekat(net, lr.net);
          return { ok, info: `${vals.map(([c, v]) => `${c} ${rp(v)}`).join(" + ")} = ${rp(jml)} · pendapatan YTD ${rp(rev)} (jurnal ${rp(lr.revenue)}) · laba bersih ${rp(net)} (jurnal ${rp(lr.net)})` };
        }, { muatUlang: async () => { await r.tid("tower-refresh").click(); await r.idle(1200); } });
        await r.tid("tower-cash-panel").scrollIntoViewIfNeeded();
        await r.shot("posisi-rincian-kas", { locator: r.tid("tower-cash-panel") });
        return info;
      });

    await r.step(10, "Finance", "Klik tab [Analisis]: tren bulanan, rasio keuangan, tabel per PT",
      "Baris 'Sukacita' di tabel: Pendapatan · Beban · Laba Bersih · Marjin — Pendapatan & Laba Bersih sama dengan kartu Laba-Rugi YTD di tab Posisi",
      async () => {
        await r.tid("hub-tab-bi-finance").click();
        await r.tid(`bi-entity-row-${KSC}`).waitFor();
        await r.idle(800);
        const info = await cocokBerulang(async () => {
          const row = await r.text(`bi-entity-row-${KSC}`);
          // "-Rp 12.816.924" = rugi: tanda minus ikut dibaca (dulu hilang → laba rugi dibandingkan positif)
          const v = [...row.matchAll(/(-?)Rp\s*([\d.]+)/g)].map((m) => (m[1] ? -1 : 1) * uang(`Rp ${m[2]}`));
          const lr = labaRugiDb(`${TAHUN}-01-01`, `${TAHUN}-12-31`);
          const ok = v.length >= 3 && dekat(v[0], lr.revenue) && dekat(v[1], lr.cogs + lr.opex) && dekat(v[2], lr.net);
          return { ok, info: `${row} · jurnal: pendapatan ${rp(lr.revenue)}, beban ${rp(lr.cogs + lr.opex)}, laba ${rp(lr.net)}` };
        }, { muatUlang: async () => { await r.tid("bi-refresh").click(); await r.idle(1200); } });
        await potret(r, "analisis", [r.tid("hub-tab-bi-finance"), r.tid(`bi-entity-row-${KSC}`)]);
        return info;
      });

    // ── Profil Saya & Tanya KN ────────────────────────────────────────────────────────────────────────────────
    await r.step(11, "Finance", "Menu samping bawah: [Profil Saya]",
      "Kartu profil karyawan Anda (nama 'Peserta Keuangan " + NO + "', nomor EMP-…, absen hari ini, cuti & lembur). Ganti sandi TIDAK ada di aplikasi — bila lupa sandi, minta Admin mereset (Pengaturan › Pengguna & Hak Akses)",
      async () => {
        await menu(r, "akun", "hr-my-profile");
        await r.tid("ess-view").waitFor();
        await r.page.waitForFunction(() => !document.querySelector('[data-testid="ess-loading"]'), null, { timeout: 15000 });
        await r.idle(500);
        const t = await r.text("ess-view");
        const unlinked = await r.tid("ess-unlinked").count();
        if (unlinked) {
          assert(/belum ditautkan ke data karyawan/.test(t), `pesan profil: ${t.slice(0, 120)}`);
        } else {
          assert(t.includes(`Peserta Keuangan ${NO}`), `nama peserta tidak tampil: ${t.slice(0, 160)}`);
          const emp = mongo(`const u=db.users.findOne({email:"${akunPeserta(NO)}@kainnusantara.id"},{_id:0,id:1});
            const e=db.hr_employees.findOne({user_id:u.id},{_id:0,code:1,position_id:1}); return e`);
          if (emp && /manajer/.test(emp.position_id || ""))
            r.note(`TEMUAN F01-c: akun Finance latihan tertaut otomatis ke karyawan ${emp.code} berjabatan 'Manajer' (bootstrap.seed_hr_foundation: ROLE_TO_ORG tanpa 'finance' → bawaan manajemen/manajer)`);
        }
        assert(!/ganti sandi|ubah sandi|kata sandi/i.test(t), "ternyata ada isian sandi — perbarui panduan");
        await potret(r, "profil-saya", [r.tid("nav-hr-my-profile")]);
        r.note("TEMUAN F01-b: tidak ada fitur ganti sandi sendiri (tak ada layar maupun endpoint /auth/…)");
        return (unlinked ? "belum tertaut · " : "tertaut · ") + t.slice(0, 140);
      });

    await r.step(12, "Finance", "Klik [Tanya KN] (menu samping) → pilih contoh 'Posisi kas & bank'",
      "Jawaban berisi tabel/angka posisi kas & bank hari ini; total sama dengan Posisi Kas di Beranda Keuangan. Kotak 'CHAT AI: Menunggu kunci penyedia model' = chat bebas belum aktif, contoh laporan tetap jalan",
      async () => {
        await menu(r, "modul", "tanya-kn");
        await r.tid("tanya-kn-page").waitFor();
        const ai = await r.text("tanya-ai-status").catch(() => "");
        await r.tid("tanya-template-cash_position").click();
        await r.page.waitForFunction(() => {
          const t = document.querySelector('[data-testid="tanya-chat-scroll"]');
          return t && /Rp\s?[\d.]{5,}/.test(t.innerText) && !/Menghitung|Memproses|sedang/i.test(t.innerText.slice(-200));
        }, null, { timeout: 45000 });
        await r.idle(1500);
        const t = (await r.text("tanya-chat-scroll"));
        const gl = saldoAkun(["1-1100", "1-1110"]);
        const glKas = (gl["1-1100"] || 0) + (gl["1-1110"] || 0);
        const angka = [...t.matchAll(/Rp\s?[\d.]+/g)].map((m) => uang(m[0]));
        await potret(r, "tanya-kn-posisi-kas", [r.tid("nav-tanya-kn"), r.tid("tanya-template-cash_position")]);
        const cocok = angka.some((v) => dekat(v, glKas, 2));
        if (!cocok) r.note(`Tanya KN 'Posisi kas & bank': tidak ada angka = GL kas ${rp(glKas)} — angka: ${angka.slice(0, 6).map(rp).join(", ")}`);
        return `${ai} · ${angka.length} angka; total GL kas ${rp(glKas)} ${cocok ? "ADA" : "TIDAK ada"} di jawaban`;
      });
  } catch (e) {
    r.note("GALAT: " + (e && e.message ? e.message : e));
  } finally {
    await r.finish();
  }
})();
