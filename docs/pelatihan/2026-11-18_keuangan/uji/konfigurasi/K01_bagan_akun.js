// K01 — Bagan Akun (COA): susunan 1-aset … 6-beban, induk/anak, akun sistem & akun kontrol, siapa boleh menambah akun.
// Peserta (akun Finance) hanya MELIHAT; pelatih (Manajer) memperagakan Tambah Akun khusus Sukacita lalu menghapusnya.
// Bukti: layar (kelompok, saldo normal, rincian akun) + buku (daftar akun API = layar; akun latihan hilang lagi).
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K01_bagan_akun.js     (bawaan peserta 11; KN_PESERTA=12 …)
const { api, assert, peserta, akunPeserta, mongo } = require("../lib");
const k = require("./konfig_lib");

const KODE = "6-4950";
const AWAL = { asset: "1-", liability: "2-", equity: "3-", income: "4-", expense: ["5-", "6-"] };

(async () => {
  const no = peserta("11");
  const r = await k.mulai("K01", "Bagan Akun (COA)");
  const fin = await api(akunPeserta(no));
  const mgr = await api("manager");
  const akun = await fin.get(`/gl/accounts?entity_id=${k.KSC}`);
  const sebelum = mongo(`return db.gl_accounts.find({},{_id:0,code:1,entity_id:1,name:1,is_active:1}).sort({code:1,entity_id:1}).toArray()`);
  k.simpanJson(r, "sebelum.json", sebelum);
  const nama = `Beban Latihan Pelatihan ${no}`;
  assert(!sebelum.some((a) => a.code === KODE), `akun ${KODE} sudah ada sebelum uji — hapus dulu`);
  r.note(`Peserta ${no} · bagan Sukacita ${akun.length} akun (gl_accounts ${sebelum.length} baris)`);

  await r.step(1, "Finance", "Masuk dengan akun peserta, buka Akuntansi & Pajak › Buku Besar, klik tab [[Bagan Akun]]",
    "Judul 'Bagan Akun · Sukacita'; kartu Total akun sama dengan jumlah akun; lima kelompok Aset · Kewajiban · Ekuitas · Pendapatan · Beban", async () => {
      await r.login(akunPeserta(no));
      await r.tid("finance-desk").waitFor();
      await k.menuPotret(r, "akuntansi", "ledger", "menu-buku-besar");
      await k.klikPotret(r, r.tid("hub-tab-chart-of-accounts"), "tab-bagan-akun");
      await r.tid("coa-groups").waitFor();
      await r.idle(600);
      const judul = await r.text("coa-title");
      assert(/Bagan Akun/.test(judul) && /Sukacita/.test(judul), `judul "${judul}"`);
      const total = (await r.text("coa-kpi-total")).replace(/\D/g, "");
      assert(Number(total) === akun.length, `kartu Total akun ${total} ≠ ${akun.length}`);
      for (const t of Object.keys(AWAL)) await r.tid(`coa-group-${t}`).waitFor();
      await r.shot("bagan-akun-sukacita");
      return `${judul} · total ${total} · detail ${await r.text("coa-kpi-postable")}`;
    });

  await r.step(2, "Finance", "Baca awalan kode tiap kelompok dan kolom 'Jenis · Saldo Normal'",
    "1- Aset & 5-/6- Beban bersaldo normal Debit; 2- Kewajiban, 3- Ekuitas, 4- Pendapatan bersaldo normal Kredit; baris KELOMPOK (huruf besar) = induk, baris Detail = bisa dijurnal", async () => {
      const ringkas = [];
      for (const [t, awal] of Object.entries(AWAL)) {
        const rows = await r.page.$$eval(`[data-testid="coa-group-${t}"] [data-testid^="coa-row-"]`,
          (els) => els.map((e) => ({ id: e.getAttribute("data-testid").replace("coa-row-", ""), t: e.innerText.replace(/\s+/g, " ") })));
        const pre = [].concat(awal);
        assert(rows.length && rows.every((x) => pre.some((p) => x.id.startsWith(p))), `kelompok ${t}: kode di luar ${pre}`);
        const normal = ["asset", "expense"].includes(t) ? "Debit" : "Kredit";
        assert(rows.every((x) => x.t.includes(`· ${normal}`)), `kelompok ${t}: saldo normal bukan ${normal}`);
        ringkas.push(`${t} ${rows.length} (${pre.join("/")}, ${normal})`);
      }
      const induk = (await r.text("coa-row-1-1000"));
      assert(/Kelompok · Debit/.test(induk), `1-1000 bukan baris kelompok: ${induk}`);
      const kas = (await r.text("coa-row-1-1100"));
      assert(/Detail · Debit/.test(kas), `1-1100 bukan akun detail: ${kas}`);
      // Induk–anak di buku: setiap akun detail punya induk yang ada.
      const kodes = new Set(akun.map((a) => a.code));
      const yatim = akun.filter((a) => a.parent_code && !kodes.has(a.parent_code)).map((a) => a.code);
      assert(!yatim.length, `akun tanpa induk yang ada: ${yatim}`);
      await k.potret(r, r.tid("coa-row-1-1000"), "induk-dan-anak");
      return ringkas.join(" · ");
    });

  await r.step(3, "Finance", "Pilih *Semua tipe* → [[Kewajiban]]",
    "Hanya kelompok Kewajiban (kode 2-…) yang tampil, semua bersaldo normal Kredit", async () => {
      await k.pilih(r, "coa-filter-type", /^Kewajiban/);
      await r.idle(400);
      assert(await r.tid("coa-group-asset").count() === 0, "kelompok Aset masih tampil");
      const ids = await r.page.$$eval('[data-testid^="coa-row-"]', (els) => els.map((e) => e.getAttribute("data-testid")));
      assert(ids.length && ids.every((x) => x.startsWith("coa-row-2-")), `ada baris bukan 2-…: ${ids.slice(0, 5)}`);
      await k.potret(r, r.tid("coa-filter-type"), "saring-kewajiban");
      await k.pilih(r, "coa-filter-type", /^Semua tipe/);
      return `${ids.length} akun kewajiban`;
    });

  await r.step(4, "Finance", "Ketik 'piutang usaha' di kotak cari → klik ikon riwayat (jam) pada baris 1-1200",
    "Baris 1-1200 berlencana 'Akun kontrol'; rincian: Jenis Aset, Induk 1-1000, Saldo normal Debit, Detail (dapat dijurnal), Akun sistem Ya", async () => {
      await r.tid("coa-search").locator("input").first().fill("piutang usaha").catch(async () => r.tid("coa-search").fill("piutang usaha"));
      await r.idle(400);
      await r.tid("coa-badge-control-1-1200").waitFor();
      await k.klikPotret(r, r.tid("coa-detail-1-1200"), "cari-piutang-usaha");
      await r.tid("coa-detail-modal").waitFor();
      const info = await r.text("coa-detail-info");
      for (const s of ["1-1200", "Aset", "1-1000", "Debit", "Detail (dapat dijurnal)", "Akun sistem Ya"]) {
        assert(info.replace(/\s+/g, " ").includes(s) || (s === "Akun sistem Ya" && /Akun sistem\s*Ya/i.test(info)), `rincian tanpa "${s}": ${info}`);
      }
      const a = akun.find((x) => x.code === "1-1200");
      assert(a.is_control && a.normal_balance === "debit" && a.system, "buku: 1-1200 bukan akun kontrol/sistem bersaldo debit");
      await r.shot("rincian-1-1200");
      await r.page.keyboard.press("Escape");
      await r.tid("coa-detail-modal").waitFor({ state: "detached", timeout: 8000 }).catch(async () => {
        await r.tid("coa-detail-modal-close").click().catch(() => {});
      });
      return `${info.slice(0, 200)} · kontrol: ${a.control_ledger_label}`;
    });

  await r.step(5, "Finance", "Periksa tombol di bilah daftar dan baris akun",
    "Tidak ada tombol [[Tambah Akun]], ikon ubah, atau ikon hapus — Finance hanya melihat; server pun menolak (403)", async () => {
      assert(await r.tid("coa-add-toggle").count() === 0, "Finance melihat tombol Tambah Akun");
      assert(await r.page.locator('[data-testid^="coa-edit-"]').count() === 0, "Finance melihat ikon ubah");
      assert(await r.page.locator('[data-testid^="coa-delete-"]').count() === 0, "Finance melihat ikon hapus");
      let status = 0;
      try { await fin.post(`/gl/accounts?entity_id=${k.KSC}`, { code: KODE, name: "uji", type: "expense" }); } catch (e) { status = e.status; }
      assert(status === 403, `POST akun oleh Finance → ${status}`);
      await r.tid("coa-search").locator("input").first().fill("").catch(async () => r.tid("coa-search").fill(""));
      await r.idle(300);
      await k.potret(r, r.tid("coa-toolbar"), "finance-hanya-lihat");
      return "Tambah/ubah/hapus tidak tampil · API tambah akun → 403";
    });

  let dibuat = false;
  try {
    await r.step(6, "Manajer (pelatih)", `Masuk sebagai Manajer, PT Sukacita → Bagan Akun → [[Tambah Akun]]: Kode ${KODE}, Nama '${nama}', Tipe Beban, Induk 6-0000, Jenis Detail → [[Simpan Akun]]`,
      `Pop-up 'Akun akan dibuat khusus untuk PT Sukacita.'; sesudah simpan baris ${KODE} tampil di kelompok Beban berlencana 'khusus PT'`, async () => {
        await r.login("manager");
        await r.go("chart-of-accounts", `&entity=${k.KSC}`);
        await r.tid("coa-groups").waitFor();
        await k.klikPotret(r, r.tid("coa-add-toggle"), "manajer-tambah-akun");
        await r.tid("coa-add-form").waitFor();
        await r.tid("coa-form-code").fill(KODE);
        await r.tid("coa-form-name").fill(nama);
        await k.pilih(r, "coa-form-type", "Beban");
        await k.pilih(r, "coa-form-parent", /^6-0000/);
        const sub = (await r.tid("coa-add-form").innerText()).replace(/\s+/g, " ");
        assert(/khusus untuk PT Sukacita/.test(sub), `subjudul: ${sub.slice(0, 160)}`);
        await k.potret(r, r.tid("coa-form-submit"), "form-tambah-akun");
        await r.tid("coa-form-submit").click();
        await r.tid("coa-add-form").waitFor({ state: "detached", timeout: 15000 });
        dibuat = true;
        await r.tid(`coa-row-${KODE}`).waitFor({ timeout: 15000 });
        await r.tid(`coa-badge-override-${KODE}`).waitFor();
        const db = mongo(`return db.gl_accounts.findOne({code:"${KODE}"},{_id:0})`);
        assert(db && db.entity_id === k.KSC && db.type === "expense" && db.parent_code === "6-0000" && db.is_postable && !db.system,
          `buku: ${JSON.stringify(db)}`);
        await k.potret(r, r.tid(`coa-row-${KODE}`), "akun-baru-khusus-pt");
        const glob = await mgr.get("/gl/accounts");
        assert(!glob.some((a) => a.code === KODE), "akun latihan ikut masuk Template Global");
        return `${db.code} ${db.name} · PT ${db.entity_id} · saldo normal ${db.normal_balance} · tidak ada di Template Global`;
      });

    await r.step(7, "Finance", `Muat ulang Bagan Akun peserta (ikon muat ulang) dan cari ${KODE}`,
      "Akun baru langsung tampil juga di layar Finance (satu bagan untuk PT Sukacita)", async () => {
        const f = await fin.get(`/gl/accounts?entity_id=${k.KSC}`);
        assert(f.some((a) => a.code === KODE), "akun baru tidak tampil untuk Finance");
        return `bagan Sukacita kini ${f.length} akun`;
      });
  } finally {
    await r.step(8, "Manajer (pelatih)", `Klik ikon hapus (tempat sampah) pada baris ${KODE} → [[Hapus akun]] di konfirmasi`,
      "Konfirmasi menyebut 'PT lain tidak terpengaruh'; akun hilang; bagan akun sama persis dengan sebelum latihan", async () => {
        if (dibuat && (await r.tid(`coa-delete-${KODE}`).count())) {
          await k.klikPotret(r, r.tid(`coa-delete-${KODE}`), "hapus-akun-latihan");
          await r.tid("coa-delete-confirm").waitFor({ timeout: 8000 });
          const msg = (await r.tid("coa-delete-confirm").innerText()).replace(/\s+/g, " ");
          assert(/PT lain tidak terpengaruh/.test(msg), `konfirmasi: ${msg}`);
          await k.potret(r, r.tid("coa-delete-confirm-confirm"), "konfirmasi-hapus");
          await r.tid("coa-delete-confirm-confirm").click();
          await r.tid(`coa-row-${KODE}`).waitFor({ state: "detached", timeout: 15000 });
        }
        if (mongo(`return db.gl_accounts.countDocuments({code:"${KODE}"})`)) {
          await mgr.call("DELETE", `/gl/accounts/${KODE}?entity_id=${k.KSC}`);   // cadangan bila layar gagal
        }
        const sesudah = mongo(`return db.gl_accounts.find({},{_id:0,code:1,entity_id:1,name:1,is_active:1}).sort({code:1,entity_id:1}).toArray()`);
        k.simpanJson(r, "sesudah.json", sesudah);
        assert(JSON.stringify(sesudah) === JSON.stringify(sebelum), "gl_accounts berbeda dengan sebelum uji");
        // Akun baku warisan template tidak punya ikon hapus di bagan PT (perbaikan K01).
        assert(await r.tid("coa-delete-1-1100").count() === 0, "ikon hapus tampil pada akun baku 1-1100 di bagan PT");
        await r.shot("bagan-kembali");
        return `gl_accounts ${sesudah.length} baris = sebelum uji`;
      });
  }
  await r.finish();
})();
