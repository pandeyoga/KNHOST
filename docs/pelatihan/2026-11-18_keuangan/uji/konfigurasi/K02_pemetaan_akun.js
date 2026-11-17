// K02 — Pemetaan Akun: setiap dokumen membuat jurnal lewat pemetaan (penjualan, piutang, PPN, kas/bank, hutang, persediaan,
// HPP, beban, titipan, GR/IR, selisih). Peserta (Finance) membaca pemetaan dan mencocokkannya dengan jurnal nyata; pelatih
// (akun Finance pelatih — Finance BOLEH mengubah pemetaan) memperagakan ubah pemetaan khusus Sukacita lalu kembali ke global.
// Pengaturan bersama dipotret sebelum, dikembalikan di `finally`, dan dibuktikan sama.
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K02_pemetaan_akun.js     (bawaan peserta 11)
const { api, assert, peserta, akunPeserta, mongo } = require("../lib");
const k = require("./konfig_lib");

const KUNCI = "kas_bank.beban_bank";      // demo: bukan akun kontrol, tidak dibaca lewat riwayat (aman dikembalikan)
const AKUN_DEMO = "6-9000";
const BACA = [   // kebutuhan inti yang dibaca peserta: [modul, kunci]
  ["penjualan", "penjualan.pendapatan"], ["penjualan", "penjualan.piutang"], ["penjualan", "penjualan.ppn_keluaran"],
  ["pembelian", "pembelian.hutang"], ["pembelian", "pembelian.gr_ir"], ["pembelian", "pembelian.ppn_masukan"],
  ["persediaan", "persediaan.persediaan"], ["persediaan", "persediaan.hpp"], ["kas_bank", "kas_bank.kas_besar"],
  ["kas_bank", "kas_bank.titipan_dana"], ["penjualan", "penjualan.selisih_bayar"], ["pembelian", "pembelian.selisih_harga"],
];
const petaPemetaan = () => k.tanpaWaktu(mongo(`return db.gl_account_mappings.find({},{_id:0}).sort({key:1,entity_id:1}).toArray()`));

(async () => {
  const no = peserta("11");
  const r = await k.mulai("K02", "Pemetaan Akun");
  const fin = await api(akunPeserta(no));
  const pelatih = await api("finance");
  const peta = await fin.get(`/gl/account-mappings?entity_id=${k.KSC}`);
  const baris = Object.fromEntries(peta.rows.map((x) => [x.key, x]));
  const sebelum = petaPemetaan();
  k.simpanJson(r, "sebelum.json", sebelum);
  r.note(`Pemetaan Sukacita: ${peta.summary.total} kebutuhan · belum diatur ${peta.summary.unset} · baris tersimpan ${sebelum.length}`);

  await r.step(1, "Finance", "Buka Pengaturan › Keuangan & Pajak → tab [[Pemetaan Akun]]",
    "Kartu 'Kebutuhan akun', 'Belum diatur', 'Diubah dari bawaan', 'Khusus PT ini'; kalimat 'Perubahan berlaku untuk jurnal baru; jurnal lama tidak diposting ulang.'", async () => {
      await r.login(akunPeserta(no));
      await r.tid("finance-desk").waitFor();
      await k.menuPotret(r, "settings-hub", "settings-finance", "menu-pengaturan-keuangan");
      // K-FIN-01: Finance kini memegang semua tab Keuangan & Pajak seperti Manajer — hub terbuka di tab pertama (Aturan),
      // jadi tab Pemetaan Akun diklik (dulu satu-satunya tab Finance).
      await r.tid("hub-tab-gl-account-mappings").click();
      await r.tid("gl-mapping-view").waitFor();
      // tunggu daftar selesai dimuat (kartu bernilai 0 selama "Memuat…")
      await r.page.waitForFunction(() => {
        const el = document.querySelector('[data-testid="glmap-kpi-total"]');
        return el && el.innerText.replace(/\D/g, "") !== "0";
      }, null, { timeout: 20000 }).catch(() => {});
      await r.idle(800);
      const tabs = await r.page.$$eval('[data-testid^="hub-tab-"]', (els) => els.map((e) => e.innerText.trim()));
      const total = (await r.text("glmap-kpi-total")).replace(/\D/g, "");
      assert(Number(total) === peta.summary.total, `kartu kebutuhan ${total} ≠ ${peta.summary.total}`);
      const note = await r.text("glmap-notice");
      assert(/jurnal baru/.test(note), `pemberitahuan: ${note}`);
      await r.shot("pemetaan-akun");
      return `tab terlihat: ${tabs.join(" · ") || "(satu layar)"} · kebutuhan ${total} · ${await r.text("glmap-kpi-unset")}`;
    });

  await r.step(2, "Finance", "Pilih *Berlaku untuk* [[Sukacita]] → *Modul* [[Penjualan]] → klik baris 'Piutang usaha'",
    "Piutang usaha 1-1200, Pendapatan penjualan 4-1000, PPN keluaran 2-1200 bersumber 'Bawaan'; rincian 'Contoh jurnal (Rp 100.000)': Dr Piutang / Cr Pendapatan", async () => {
      await k.pilih(r, "glmap-scope", "Sukacita");
      await r.idle(800);
      await k.pilih(r, "glmap-module", "Penjualan");
      await r.idle(300);
      for (const key of ["penjualan.pendapatan", "penjualan.piutang", "penjualan.ppn_keluaran"]) {
        const t = await r.text(`glmap-account-${key}`);
        assert(t.startsWith(baris[key].account_code), `${key}: layar ${t} ≠ ${baris[key].account_code}`);
      }
      await r.tid("glmap-expand-penjualan.piutang").click();
      const det = await r.text("glmap-detail-penjualan.piutang");
      assert(/Dr/.test(det) && /Cr/.test(det) && /100\.000/.test(det), `rincian: ${det}`);
      await k.potret(r, r.tid("glmap-detail-penjualan.piutang"), "penjualan-piutang");
      return det.slice(0, 220);
    });

  await r.step(3, "Finance", "Ganti *Modul* ke [[Pembelian]], lalu [[Persediaan]], lalu [[Kas & Bank]]",
    "Hutang usaha 2-1100 · GR/IR 2-1150 · PPN masukan 1-1500 · Selisih harga pembelian 'Belum dipilih'; Persediaan 1-1300 · HPP 5-1000; Kas besar 1-1100 · Titipan dana 2-1950", async () => {
      const hasil = [];
      for (const [mod, label] of [["pembelian", "Pembelian"], ["persediaan", "Persediaan"], ["kas_bank", "Kas & Bank"]]) {
        await k.pilih(r, "glmap-module", label);
        await r.idle(300);
        for (const [m, key] of BACA.filter((x) => x[0] === mod)) {
          const t = await r.text(`glmap-account-${key}`);
          const harap = baris[key].account_code || "Belum dipilih";
          assert(t.startsWith(harap), `${m}/${key}: layar "${t}" ≠ ${harap}`);
          hasil.push(`${baris[key].label}: ${t.split(" · ")[0]}`);
        }
        if (mod === "pembelian") await k.potret(r, r.tid("glmap-row-pembelian.selisih_harga"), "pembelian-selisih-belum-dipilih");
        if (mod === "kas_bank") await r.shot("kas-bank");
      }
      return hasil.join(" · ");
    });

  await r.step(4, "Finance", "Pilih *Modul* [[Semua modul]] → klik kartu [[Belum diatur]]",
    "Hanya kebutuhan tanpa akun yang tampil (Selisih harga pembelian, Selisih nilai retur beli) — keputusan pemilik; klik kartu lagi untuk menampilkan semua", async () => {
      await k.pilih(r, "glmap-module", "Semua modul");
      await r.tid("glmap-kpi-unset").click();
      await r.idle(300);
      const ids = await r.page.$$eval('[data-testid^="glmap-row-"]', (els) => els.map((e) => e.getAttribute("data-testid").replace("glmap-row-", "")));
      const unset = peta.rows.filter((x) => x.status !== "ok").map((x) => x.key);
      assert(JSON.stringify(ids.sort()) === JSON.stringify(unset.sort()), `baris ${ids} ≠ ${unset}`);
      await k.potret(r, r.tid("glmap-kpi-unset"), "belum-diatur");
      await r.tid("glmap-kpi-unset").click();
      return ids.map((x) => baris[x].label).join(" · ");
    });

  await r.step(5, "Finance", "Cek buku: buka Akuntansi & Pajak › Buku Besar, ketik nomor surat jalan terakhir Sukacita di cari, klik jurnal 'Pendapatan Kirim'",
    "Baris jurnal memakai akun yang sama dengan pemetaan: Piutang 1-1200 (D) · Pendapatan 4-1000 (K) · PPN keluaran 2-1200 (K) — seimbang", async () => {
      const je = mongo(`return db.journal_entries.find({entity_id:"${k.KSC}",status:{$ne:"void"},source_type:"shipment_revenue"},{_id:0}).sort({created_at:-1}).limit(1).toArray()[0]`);
      assert(je, "belum ada jurnal pendapatan kirim di Sukacita");
      const kode = new Set(je.lines.map((l) => l.account_code));
      for (const key of ["penjualan.piutang", "penjualan.pendapatan"]) assert(kode.has(baris[key].account_code), `jurnal ${je.number} tanpa ${baris[key].account_code}`);
      const ringkas = k.cekJurnal(je, []);
      await k.menuPotret(r, "akuntansi", "ledger", "menu-buku-besar");
      await r.tid("gl-view").waitFor();
      await r.tid("gl-journal-search").fill(je.source_label || je.number);
      await r.idle(1200);
      const row = r.tid(`gl-journal-row-${je.id}`);
      await row.waitFor({ timeout: 15000 });
      await k.klikPotret(r, row, "cari-jurnal-kirim");
      await r.tid("gl-journal-detail").waitFor();
      await r.idle(400);
      const det = (await r.tid("gl-journal-detail").innerText()).replace(/\s+/g, " ");
      for (const l of je.lines) assert(det.includes(l.account_code), `rincian jurnal tanpa ${l.account_code}`);
      await r.shot("jurnal-sesuai-pemetaan");
      await r.page.keyboard.press("Escape");
      // Tagihan pemasok: GR/IR (D) + PPN masukan (D) / Hutang (K) — sama dengan pemetaan Pembelian.
      const vb = mongo(`return db.journal_entries.find({entity_id:"${k.KSC}",status:{$ne:"void"},source_type:"vendor_bill"},{_id:0,number:1,lines:1}).sort({created_at:-1}).limit(1).toArray()[0]`);
      let vbTxt = "";
      if (vb) {
        const kv = new Set(vb.lines.map((l) => l.account_code));
        assert(kv.has(baris["pembelian.hutang"].account_code), `jurnal tagihan ${vb.number} tanpa akun hutang`);
        vbTxt = ` · tagihan ${vb.number}: ${[...kv].join(", ")}`;
      }
      return `${ringkas}${vbTxt}`;
    });

  let diubah = false;
  try {
    await r.step(6, "Pelatih (akun Finance)", `Pengaturan › Keuangan & Pajak › Pemetaan Akun · *Berlaku untuk* Sukacita · *Modul* Kas & Bank → baris 'Beban administrasi bank' [[Atur PT]] → *Akun* ${AKUN_DEMO} Beban Lain-lain · *Alasan* → [[Simpan]]`,
      "Dialog menulis 'Perubahan berlaku untuk jurnal baru; jurnal lama tidak diposting ulang.'; sesudah simpan baris berakun 6-9000 bersumber 'Khusus PT', kartu 'Khusus PT ini' = 1", async () => {
        await r.login("finance");
        await r.go("gl-account-mappings", `&entity=${k.KSC}`);
        await r.tid("gl-mapping-view").waitFor();
        await k.pilih(r, "glmap-scope", "Sukacita");
        await r.idle(800);
        await k.pilih(r, "glmap-module", "Kas & Bank");
        await k.klikPotret(r, r.tid(`glmap-edit-${KUNCI}`), "atur-pt-beban-bank");
        await r.tid("glmap-edit-modal").waitFor();
        assert(/Sukacita/.test(await r.text("glmap-edit-scope")), "dialog bukan untuk Sukacita");
        assert(/jurnal baru/.test(await r.text("glmap-edit-warning")), "peringatan jurnal baru tidak tampil");
        await k.pilih(r, "glmap-edit-account", new RegExp(`^${AKUN_DEMO}`));
        await r.tid("glmap-edit-reason").fill("Peragaan pelatihan K02 — dikembalikan sesudah demo");
        await k.potret(r, r.tid("glmap-edit-save"), "dialog-ubah-akun");
        await r.tid("glmap-edit-save").click();
        await r.tid("glmap-edit-modal").waitFor({ state: "detached", timeout: 15000 });
        diubah = true;
        await k.tungguTeks(r, `glmap-account-${KUNCI}`, new RegExp(`^${AKUN_DEMO}`));
        assert(/Khusus PT/.test(await r.text(`glmap-source-${KUNCI}`)), "sumber bukan Khusus PT");
        assert((await r.text("glmap-kpi-entity")).replace(/\D/g, "") === "1", "kartu Khusus PT ini ≠ 1");
        const efek = await pelatih.get(`/gl/account-mappings?entity_id=${k.KSC}`);
        const glob = await pelatih.get("/gl/account-mappings");
        const e1 = efek.rows.find((x) => x.key === KUNCI);
        const g1 = glob.rows.find((x) => x.key === KUNCI);
        assert(e1.account_code === AKUN_DEMO && g1.account_code === baris[KUNCI].account_code, `efektif ${e1.account_code} · global ${g1.account_code}`);
        await k.potret(r, r.tid(`glmap-row-${KUNCI}`), "pemetaan-khusus-pt");
        return `Sukacita: ${e1.account_code} ${e1.account_name} (${e1.source}) · Global tetap ${g1.account_code}`;
      });

    await r.step(7, "Pelatih (akun Finance)", "Klik ikon riwayat (jam) pada baris yang sama",
      "Riwayat menulis siapa, kapan, dari 6-8000 ke 6-9000, dan alasannya", async () => {
        await r.tid(`glmap-history-${KUNCI}`).click();
        await r.tid("glmap-history-modal").waitFor();
        await r.idle(600);
        const t = (await r.tid("glmap-history-modal").innerText()).replace(/\s+/g, " ");
        assert(t.includes(AKUN_DEMO) && /Peragaan pelatihan K02/.test(t), `riwayat: ${t.slice(0, 200)}`);
        await r.shot("riwayat-pemetaan");
        await r.tid("glmap-history-modal-close").click();
        return t.slice(0, 200);
      });
  } finally {
    await r.step(8, "Pelatih (akun Finance)", "[[Atur PT]] lagi → *Alasan* → [[Kembali ke global]]",
      "Baris kembali 6-8000 Beban Administrasi Bank bersumber 'Bawaan'; pemetaan tersimpan sama persis dengan sebelum peragaan", async () => {
        if (diubah && (await r.tid(`glmap-edit-${KUNCI}`).count())) {
          await r.tid(`glmap-edit-${KUNCI}`).click();
          await r.tid("glmap-edit-modal").waitFor();
          await r.tid("glmap-edit-reason").fill("Selesai peragaan pelatihan K02");
          await k.klikPotret(r, r.tid("glmap-edit-reset"), "kembali-ke-global");
          await r.tid("glmap-edit-modal").waitFor({ state: "detached", timeout: 15000 });
          await k.tungguTeks(r, `glmap-account-${KUNCI}`, new RegExp(`^${baris[KUNCI].account_code}`));
        }
        let sesudah = petaPemetaan();
        if (JSON.stringify(sesudah) !== JSON.stringify(sebelum)) {   // cadangan bila layar gagal
          await pelatih.post(`/gl/account-mappings/${KUNCI}/reset`, { entity_id: k.KSC, reason: "Pemulihan otomatis uji K02" }).catch(() => {});
          sesudah = petaPemetaan();
        }
        k.simpanJson(r, "sesudah.json", sesudah);
        assert(JSON.stringify(sesudah) === JSON.stringify(sebelum), `gl_account_mappings berbeda: ${k.beda(sebelum, sesudah)}`);
        const efek = (await pelatih.get(`/gl/account-mappings?entity_id=${k.KSC}`)).rows.find((x) => x.key === KUNCI);
        assert(efek.account_code === baris[KUNCI].account_code && efek.source === baris[KUNCI].source, `efektif ${efek.account_code} ${efek.source}`);
        await r.shot("pemetaan-kembali");
        return `${KUNCI} = ${efek.account_code} (${efek.source}); gl_account_mappings ${sesudah.length} baris = sebelum`;
      });
  }
  await r.finish();
})();
