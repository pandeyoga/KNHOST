// K07 — Hak akses peran & aturan persetujuan. Pelatih (Admin) membaca peran Finance di Pengaturan › Pengguna & Hak Akses
// (wewenang = izin per modul, bukan nama peran), memperagakan CARA memberi izin (pilih tingkat → [Simpan] → ringkasan
// perubahan) lalu MEMBATALKANNYA tanpa menyimpan — peran bawaan tidak diubah. Lalu membaca Aturan Persetujuan yang
// menyentuh keuangan (PO, tagihan pemasok, uang muka/kas kecil, selisih bayar, kredit, buka periode) dan mencoba nilai.
// Peserta (Finance) membuktikan izinnya sendiri di layar (tombol yang tampil / tidak tampil).
//   node docs/pelatihan/2026-11-18_keuangan/uji/konfigurasi/K07_hak_akses_persetujuan.js     (bawaan peserta 11)
const { api, assert, peserta, akunPeserta, mongo } = require("../lib");
const k = require("./konfig_lib");

const MODUL_KEUANGAN = ["ar", "finance_ops", "payable", "petty_cash", "accounting", "settings"];
const KARTU_PERSETUJUAN = ["purchase_order", "vendor_bill", "cash_advance", "cash_advance_settlement", "payment_variance",
  "credit_override", "period_unlock"];
const potretIzin = () => k.tanpaWaktu({
  permission_settings: mongo(`return db.permission_settings.find({},{_id:0}).toArray()`),
  approval_policies: mongo(`return db.approval_policies.find({},{_id:0}).sort({id:1}).toArray()`),
  approval_rules: mongo(`return db.approval_rules.find({},{_id:0}).sort({id:1}).toArray()`),
});

(async () => {
  const no = peserta("11");
  const r = await k.mulai("K07", "Hak akses peran & aturan persetujuan");
  const fin = await api(akunPeserta(no));
  const t0 = new Date().toISOString();
  const sebelum = potretIzin();
  // Simpanan izin peran juga bisa berubah oleh sinkron modul saat backend dimuat ulang (agen lain menambah izin di kode).
  // Bukti "uji ini tidak menyimpan": tidak ada catatan audit simpan izin/peran sejak uji mulai.
  const simpanIzin = () => mongo(`return db.audit_logs.countDocuments({timestamp:{$gte:"${t0}"},
    action:{$in:["permissions_updated","role_access_updated","role_access_reset","role_followed_base","role_users_moved"]}})`);
  k.simpanJson(r, "sebelum.json", sebelum);
  const me = await fin.get("/auth/me");
  const izin = me.permissions || (me.user || {}).permissions || {};
  r.note(`Izin Finance (sesi peserta): accounting ${izin.accounting} · gl_mapping ${izin.gl_mapping} · cash ${izin.cash} · settings ${izin.settings || "-"}`);

  await r.step(1, "Admin (pelatih)", "Buka Pengaturan › Pengguna & Hak Akses › tab [[Peran & Hak Akses]]",
    "Kartu tiap peran; kartu Finance: 'Bawaan', jumlah akun, dan hitungan modul semua aksi · sebagian · lihat · tidak ada", async () => {
      await r.login("admin");
      await r.go("permission-matrix", `&entity=${k.KSC}`);
      await r.tid("role-card-finance").waitFor();
      await r.idle(800);
      const t = (await r.text("role-card-finance"));
      assert(/Finance/.test(t) && /akun/.test(t), `kartu Finance: ${t}`);
      await k.potret(r, r.tid("role-card-finance"), "kartu-peran-finance");
      return t;
    });

  await r.step(2, "Admin (pelatih)", "Klik kartu [[Finance]]",
    "Editor peran: daftar modul dengan tingkat Tidak ada · Lihat saja · Semua aksi (atau 'Sebagian n dari m aksi'); sejak K-FIN-01 tingkatnya sama dengan Manajer — Pusat Pengaturan 'Lihat saja'", async () => {
      await r.tid("role-card-finance").click();
      await r.tid("role-editor-drawer").waitFor();
      await r.tid("role-editor-matrix").waitFor();
      await r.idle(1200);
      const baris = [];
      for (const m of MODUL_KEUANGAN) {
        const row = r.tid(`role-module-row-${m}`);
        if (!(await row.count())) continue;
        baris.push((await row.innerText()).replace(/\s+/g, " ").replace(/Tidak ada Lihat( saja)? Semua aksi/, "").trim());
      }
      assert(baris.length >= 4, `modul keuangan di editor: ${baris.length}`);
      const set = (await r.tid("role-module-row-settings").innerText()).replace(/\s+/g, " ");
      // K-FIN-01: Finance memegang izin Manajer — Pusat Pengaturan tidak lagi 'Tidak ada'; dicatat.
      const lihat = await r.tid("role-level-settings-view").getAttribute("aria-pressed").catch(() => "");
      r.note(`K-FIN-01: Pusat Pengaturan Finance ${lihat === "true" ? "Lihat saja" : set.slice(0, 80)}`);
      await k.potret(r, r.tid("role-module-row-accounting"), "editor-peran-finance");
      return baris.join(" | ").slice(0, 400);
    });

  await r.step(3, "Admin (pelatih)", "Pada baris 'Akuntansi & Tutup Buku' klik ikon atur rinci",
    "Rincian aksi per halaman: sejak K-FIN-01 Finance memegang aksi Manajer — membuat jurnal, menganulir, dan mengelola bagan akun dicentang", async () => {
      await r.tid("role-module-advanced-accounting").click();
      await r.idle(600);
      await r.shot("rinci-akuntansi");
      const acc = izin.accounting || [];
      assert(["view", "create", "manage"].every((a) => acc.includes(a)), `izin accounting Finance (K-FIN-01) ${acc}`);
      await r.tid("role-module-advanced-accounting").click();
      return `izin server: accounting = ${JSON.stringify(izin.accounting)}`;
    });

  await r.step(4, "Admin (pelatih)", "Peragaan memberi izin: pada 'Akuntansi & Tutup Buku' klik [[Semua aksi]] → [[Simpan]] → baca ringkasan → [[Periksa lagi]] → [[Batal]] → [[Buang & tutup]]",
    "Baris ditandai berubah; ringkasan sebelum simpan menyebut perubahan dan peringatan izin peka; sesudah Buang & tutup tidak ada yang tersimpan (peran bawaan tetap)", async () => {
      await r.tid("role-level-accounting-manage").click();
      await r.tid("role-module-changed-accounting").waitFor({ timeout: 5000 });
      await k.potret(r, r.tid("role-editor-save"), "pilih-semua-aksi");
      await r.tid("role-editor-save").click();
      await r.tid("role-editor-confirm").waitFor();
      const ring = (await r.tid("role-editor-confirm").innerText()).replace(/\s+/g, " ");
      assert(/Akuntansi/.test(ring), `ringkasan tanpa Akuntansi: ${ring.slice(0, 200)}`);
      await k.potret(r, r.tid("role-editor-confirm-cancel"), "ringkasan-perubahan");
      await r.tid("role-editor-confirm-cancel").click();
      await r.tid("role-editor-cancel").click();
      await r.tid("role-editor-discard").waitFor();
      await k.potret(r, r.tid("role-editor-discard-confirm"), "buang-perubahan");
      await r.tid("role-editor-discard-confirm").click();
      await r.tid("role-editor-drawer").waitFor({ state: "detached", timeout: 8000 });
      assert(simpanIzin() === 0, "ada penyimpanan izin peran walau dibatalkan");
      return ring.slice(0, 240);
    });

  await r.step(5, "Admin (pelatih)", "Buka Pengaturan › Persetujuan › tab [[Aturan Persetujuan]] → baca kelompok Keuangan dan Pembelian",
    "Kartu per jenis dokumen dengan ringkasan aturan (siapa menyetujui, mulai nominal berapa) dan asal aturan: Pesanan pembelian, Tagihan pemasok, Uang muka & pertanggungjawaban (kas kecil), Selisih bayar, Izin kredit, Buka periode", async () => {
      await r.go("approval-rules", `&entity=${k.KSC}`);
      await r.tid("approval-policies-view").waitFor();
      await r.tid("appol-group-Keuangan").waitFor({ timeout: 20000 });
      await r.idle(800);
      const out = [];
      for (const kind of KARTU_PERSETUJUAN) {
        if (!(await r.tid(`appol-card-${kind}`).count())) continue;
        const lbl = (await r.tid(`appol-card-${kind}`).innerText()).split("\n")[0].trim();
        out.push(`${lbl}: ${await r.text(`appol-summary-${kind}`)}`);
      }
      assert(out.length >= 5, `kartu persetujuan keuangan ${out.length}`);
      await r.tid("appol-toggle-vendor_bill").click();
      await r.tid("appol-detail-vendor_bill").waitFor();
      await k.potret(r, r.tid("appol-card-vendor_bill"), "aturan-tagihan-pemasok");
      return out.join(" | ").slice(0, 500);
    });

  await r.step(6, "Admin (pelatih)", "Di 'Coba nilai': pilih [[Pesanan pembelian]], ketik nominal Rp 600.000.000 → [[Coba]]",
    "Hasil: jenjang persetujuan dan siapa yang lolos (mis. Jenjang 1 Manajer, Jenjang 2 Direksi untuk PO di atas Rp 500 juta) — tanpa membuat dokumen", async () => {
      await k.pilih(r, "appol-try-kind", /Pesanan pembelian|Purchase/i).catch(async () => k.pilihNilai(r, "appol-try-kind", "purchase_order"));
      await r.tid("appol-try-amount").fill("600000000");
      await r.tid("appol-try-btn").click();
      const res = r.tid("appol-try-result");
      await res.or(r.tid("appol-try-none")).first().waitFor({ timeout: 15000 });
      const t = (await res.or(r.tid("appol-try-none")).first().innerText()).replace(/\s+/g, " ");
      await k.potret(r, r.tid("appol-try"), "coba-nilai-po");
      assert(/Jenjang/.test(t), `hasil coba: ${t}`);
      return t;
    });

  await r.step(7, "Finance", "Masuk dengan akun peserta → buka grup Pengaturan di menu samping",
    "Menu Pengaturan Finance berisi Keuangan & Pajak dan menu lain yang juga dimiliki Manajer (K-FIN-01); Pengaturan umum tetap khusus Admin — menu mengikuti izin, bukan nama peran", async () => {
      await r.login(akunPeserta(no));
      await r.tid("finance-desk").waitFor();
      const grup = r.tid("nav-group-toggle-settings-hub");
      await grup.click();
      await r.tid("nav-settings-finance").waitFor();
      const items = await r.page.$$eval('[data-testid^="nav-settings-"]', (els) => els.map((e) => e.getAttribute("data-testid")));
      // K-FIN-01 (pemilik 17 Nov): Finance memegang semua izin Manajer — menu Pengaturan Manajer ikut tampil; dicatat.
      assert(items.includes("nav-settings-finance"), `menu Pengaturan Finance: ${items}`);
      r.note(`K-FIN-01: menu Pengaturan Finance = ${items.join(", ")}`);
      await k.potret(r, r.tid("nav-settings-finance"), "menu-pengaturan-finance");
      let st = 0;
      try { await fin.get("/access/roles"); } catch (e) { st = e.status; }
      return `menu Pengaturan: ${items.join(", ")} · API daftar peran untuk Finance → ${st || 200}`;
    });

  await r.step(8, "Pelatih", "Pastikan peran & aturan persetujuan tidak berubah",
    "Izin peran, kebijakan & aturan persetujuan sama persis dengan sebelum skenario", async () => {
      const sesudah = potretIzin();
      k.simpanJson(r, "sesudah.json", sesudah);
      assert(simpanIzin() === 0, "ada catatan audit simpan izin/peran selama uji");
      assert(JSON.stringify(sesudah.approval_policies) === JSON.stringify(sebelum.approval_policies), "kebijakan persetujuan berubah");
      assert(JSON.stringify(sesudah.approval_rules) === JSON.stringify(sebelum.approval_rules), "aturan persetujuan berubah");
      const sama = JSON.stringify(sesudah.permission_settings) === JSON.stringify(sebelum.permission_settings);
      if (!sama) r.note("permission_settings berubah selama uji TANPA simpan dari uji ini (sinkron modul oleh proses lain) — lihat sebelum/sesudah.json");
      return `approval_policies & approval_rules = sebelum · izin peran ${sama ? "= sebelum" : "berubah oleh proses lain"} · 0 simpan izin oleh uji`;
    });
  await r.finish();
})();
