// K03 — Profil PT, tahun buku & periode: identitas PT (nama, alamat, NPWP, PKP, kode dokumen) yang tercetak di dokumen,
// bulan tutup tahun buku, dan keadaan periode buka/tutup (tutup buku sendiri = Modul 4, F18). Hanya MEMBACA — tidak ada
// pengaturan yang diubah. Pelatih (Manajer) membuka Pengaturan; peserta (Finance) mencetak faktur dan mencocokkan kop.
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K03_profil_pt_periode.js     (bawaan peserta 11)
const { api, assert, peserta, akunPeserta, mongo } = require("../lib");
const dk = require("../dokumen/dokumen_lib");
const k = require("./konfig_lib");

const BULAN = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November",
  "Desember"];

(async () => {
  const no = peserta("11");
  const r = await k.mulai("K03", "Profil PT, tahun buku & periode");
  const fin = await api(akunPeserta(no));
  const mgr = await api("manager");
  const pt = mongo(`return db.business_entities.findOne({id:"${k.KSC}"},{_id:0})`);
  const sebelum = k.potretSystemSettings();
  const so = mongo(`return db.sales_orders.find({entity_id:"${k.KSC}",status:{$in:["done","shipped","delivered"]}},{_id:0,id:1,number:1}).sort({created_at:-1}).limit(1).toArray()[0]`);
  r.note(`PT ${pt.legal_name} · NPWP ${pt.npwp} · kode ${pt.doc_prefix} · faktur pembanding ${so && so.number}`);

  await r.step(1, "Manajer (pelatih)", "Buka Pengaturan › Perusahaan (PT) › tab [[Profil PT]]",
    "Daftar PT: baris Sukacita Textile — Jenis PT, Kode dokumen KSC (contoh KSC/SO-00001), Pajak PKP, Mata uang IDR, Kesiapan …% dan butir yang kurang", async () => {
      await r.login("manager");
      await r.go("settings-pt-profile", `&entity=${k.KSC}`);
      await r.tid("entity-list-table").waitFor();
      await r.idle(600);
      const row = (await r.text(`entity-row-${k.KSC}`));
      for (const s of [pt.legal_name, pt.doc_prefix, "IDR"]) assert(row.includes(s), `baris PT tanpa "${s}": ${row}`);
      assert(/PKP/.test(await r.text(`entity-pkp-${k.KSC}`)), "Sukacita tidak berlencana PKP");
      await k.potret(r, r.tid(`entity-row-${k.KSC}`), "daftar-pt");
      return row.slice(0, 220);
    });

  await r.step(2, "Manajer (pelatih)", "Klik baris Sukacita Textile",
    "Rincian PT: Nama legal, NPWP 01.234.567.8-901.000, alamat & kota, status pajak PKP (memungut PPN), 'Tahun buku: Januari–Desember (mengikuti pengaturan grup)', kode dokumen KSC terkunci", async () => {
      await r.tid(`entity-row-${k.KSC}`).click();
      await r.tid("entity-detail-drawer").waitFor();
      await r.idle(800);
      const npwp = await r.tid("entity-detail-npwp-input").inputValue();
      const alamat = await r.tid("entity-detail-address-input").inputValue();
      assert(npwp === pt.npwp, `NPWP layar ${npwp} ≠ ${pt.npwp}`);
      assert(alamat === pt.address, `alamat layar ${alamat} ≠ ${pt.address}`);
      const pajak = await r.text("entity-detail-tax-status");
      assert(/PKP/.test(pajak), `status pajak: ${pajak}`);
      const kunci = await r.tid("entity-detail-prefix-locked").count();
      await k.potret(r, r.tid("entity-detail-npwp-input"), "rincian-pt");
      const tb = await r.text("entity-detail-profile-fiscal");
      assert(/Januari.Desember/.test(tb), `tahun buku di rincian: ${tb}`);
      await k.potret(r, r.tid("entity-detail-profile"), "rincian-pt-tahun-buku");
      await r.tid("entity-detail-close").click();
      await r.tid("entity-detail-drawer").waitFor({ state: "detached", timeout: 8000 });
      return `NPWP ${npwp} · ${alamat} · pajak: ${pajak} · ${tb} · kode dokumen ${kunci ? "terkunci" : "masih bisa diubah"}`;
    });

  await r.step(3, "Manajer (pelatih)", "Klik tab [[Kesiapan PT]]",
    "Daftar periksa kelengkapan PT; butir yang belum lengkap (mis. Pemetaan akun, Kop surat & logo, Penanda tangan) ditulis dengan tautan perbaikannya", async () => {
      await k.klikPotret(r, r.tid("hub-tab-settings-pt-readiness"), "tab-kesiapan");
      await r.tid("entity-readiness-panel").waitFor();
      const list = r.page.locator('[data-testid$="-list"] li[data-ready]');
      await list.first().waitFor({ timeout: 20000 });
      await r.idle(600);
      const items = await r.page.$$eval('li[data-ready]', (els) => els.map((e) => ({
        ok: e.getAttribute("data-ready") === "ya", t: e.innerText.replace(/\s+/g, " ").trim() })));
      const kurang = items.filter((x) => !x.ok).map((x) => x.t.split(" ").slice(0, 6).join(" "));
      assert(items.length >= 3, `butir kesiapan ${items.length}`);
      await r.shot("kesiapan-pt", { full: true });
      return `${items.length} butir · belum lengkap: ${kurang.join(" | ")}`;
    });

  await r.step(4, "Finance", "Masuk dengan akun peserta → Pusat Dokumen › Cetak PDF & Label: jenis [[Faktur Komersial]], cari nomor SO dari pelatih, klik ikon [[Unduh PDF]]",
    "Kop faktur memuat nama PT, alamat, kota dan NPWP persis seperti Profil PT; nomor faktur berawalan KSC/", async () => {
      assert(so, "belum ada SO Sukacita yang terkirim");
      await r.login(akunPeserta(no));
      await r.go("document-center");
      await r.tid("document-center").waitFor();
      await k.pilihNilai(r, "dc-doctype-select", "invoice");
      await r.tid("dc-search").fill(so.number);
      await r.tid(`dc-row-${so.id}`).waitFor({ timeout: 20000 });
      await k.potret(r, r.tid(`dc-download-${so.id}`), "pusat-dokumen-faktur");
      const [dl] = await Promise.all([r.page.waitForEvent("download"), r.tid(`dc-download-${so.id}`).click()]);
      const d = dk.simpan(r, "faktur-kop", require("fs").readFileSync(await dl.path()));
      const kop = d.text.split("\n").slice(0, 4).join(" ").replace(/\s+/g, " ");
      for (const s of [pt.legal_name, pt.address, pt.city, `NPWP ${pt.npwp}`]) assert(kop.includes(s), `kop tanpa "${s}": ${kop}`);
      assert(new RegExp(`${pt.doc_prefix}/INV-\\d+`).test(d.text), "nomor faktur tidak berawalan kode PT");
      return `kop: ${kop.slice(0, 160)}`;
    });

  await r.step(5, "Manajer (pelatih)", "Pengaturan › Keuangan & Pajak › Aturan Keuangan & Pajak → chip [[Pajak, pembukuan & antar-PT]] → ketik 'tahun buku' di kotak cari → buka baris 'Bulan tutup tahun buku'",
    "Bulan tutup tahun buku = 12 (Desember) dan Mata uang pembukuan = IDR — berlaku untuk semua PT kecuali diatur khusus; Manajer hanya membaca (mengubah butuh izin kelola pengaturan)", async () => {
      await r.login("manager");
      await r.go("settings-cfg-finance", `&entity=${k.KSC}`);
      await r.tid("cfg-group-chips").waitFor();
      await r.tid("cfg-group-pajak-pembukuan").click();
      await r.idle(600);
      await r.tid("cfg-search").fill("tahun buku");
      await r.idle(1000);
      const key = "finance.fiscal_year_end_month";
      await r.tid(`cfg-card-${key}`).waitFor();
      const nilai = await r.text(`cfg-compact-value-${key}`);
      const v = await k.nilaiConfig(mgr, key);
      assert(String(v.value) === "12" && /12|Desember/.test(nilai), `bulan tutup ${v.value} / layar ${nilai}`);
      await r.tid(`cfg-card-toggle-${key}`).click();
      await r.idle(400);
      await k.potret(r, r.tid(`cfg-card-${key}`), "bulan-tutup-tahun-buku");
      const cur = await k.nilaiConfig(mgr, "finance.base_currency");
      const kunci = await k.nilaiConfig(mgr, "periode.kunci_dokumen");
      return `tahun buku berakhir ${BULAN[Number(v.value) - 1]} (${v.source_label || v.source}) · mata uang ${cur.value} · periode tertutup mengunci dokumen: ${kunci.value}`;
    });

  await r.step(6, "Manajer (pelatih)", "Buka Akuntansi & Pajak › Tutup Buku",
    "Kartu periode tertutup dan Riwayat Tutup Buku Sukacita: periode yang belum ditutup masih terbuka untuk transaksi (menutup periode = Modul 4)", async () => {
      await r.go("closing", `&entity=${k.KSC}`);
      await r.tid("closing-view").waitFor();
      await r.idle(1000);
      const tutup = mongo(`return db.period_closings.countDocuments({entity_id:"${k.KSC}",status:{$in:["closed","locked"]}})`);
      const kpi = await r.text("closing-kpi-closed");
      const kosong = await r.tid("closing-empty").count();
      await k.potret(r, r.tid("closing-kpi"), "tutup-buku-periode");
      assert(tutup > 0 || kosong, `DB ${tutup} periode tertutup tetapi layar tidak kosong`);
      return `kartu: ${kpi} · DB periode tertutup Sukacita ${tutup}${kosong ? " · Riwayat kosong (semua periode terbuka)" : ""}`;
    });

  await r.step(7, "Pelatih", "Pastikan tidak ada pengaturan yang berubah",
    "Pengaturan global & Sukacita sama dengan sebelum skenario", async () => {
      const sesudah = k.potretSystemSettings();
      assert(JSON.stringify(sesudah) === JSON.stringify(sebelum), `pengaturan berubah: ${k.beda(sebelum, sesudah)}`);
      const pt2 = mongo(`return db.business_entities.findOne({id:"${k.KSC}"},{_id:0})`);
      assert(JSON.stringify(k.tanpaWaktu(pt2)) === JSON.stringify(k.tanpaWaktu(pt)), "profil PT berubah");
      return "system_settings & profil PT tidak berubah";
    });
  await r.finish();
})();
